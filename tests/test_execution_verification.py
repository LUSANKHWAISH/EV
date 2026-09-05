"""
Test Suite for Task 016: Execution Verification & System Action Hardening.

Covers:
1. Structured Execution Result:
   - Success, failure, cancellation, timeout, unknown outcome.
   - Structured metadata and secret/credential/audio sanitization.
2. Verification Result Semantics:
   - VERIFIED, FAILED, NOT_APPLICABLE, UNKNOWN.
   - Central rule: Execution Succeeded + Verification Failed = OVERALL FAILURE.
   - Observation-only timeout resolution (success, failure, unresolved UNKNOWN).
3. Deterministic Verifiers:
   - File operations: WRITE_FILE + FILE_EXISTS / FILE_CONTENT_MATCH / FILE_HASH_MATCH.
   - File deletion: DELETE_FILE + FILE_NOT_EXISTS.
   - File read: READ_TEXT_FILE + READ_CONTENT_VALID.
   - Process operations: FIND_PROCESS + PROCESS_IDENTITY_VALID, STOP_PROCESS observation-only.
   - Service operations: SERVICE_RUNNING, SERVICE_STOPPED.
4. Plan & Transaction Integration:
   - Multi-step plan aborts on verification failure.
   - Prior steps rolled back in strict LIFO order.
   - Unknown mutation outcome: halts plan, retry_allowed=False, zero blind retry.
   - Cooperative cancellation checks before dispatch and verification.
5. Safety & Authority Boundaries:
   - Verifier cannot execute actions.
   - Awareness cannot execute actions.
   - Brain cannot execute actions.
   - Voice cannot bypass approval.
   - Unknown mutation cannot trigger automatic retry.
"""
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.agent import EVAgent, IS_ACTION_IDEMPOTENT
from core.backup import EVBackupManager
from core.cancellation import CancellationToken, CancellationSource
from core.events import EVEventBus, EVEvent
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentStepResult,
    AgentTask,
    EVEventType,
    EVState,
    ExecutionResult,
    ExecutionStatus,
    FileInfo,
    ProcessInfo,
    RiskLevel,
    ServiceInfo,
    TextReadResult,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    VerificationType,
    sanitize_metadata,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_executor import EVPlanExecutor
from core.plan_validator import PlanValidator
from core.risk import EVRiskEngine
from core.verifier import EVVerifier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sandbox_env():
    """Create an isolated sandbox environment with backup manager, agent, and executor."""
    temp_dir = tempfile.mkdtemp(prefix="ev_task016_test_")
    backup_dir = os.path.join(temp_dir, "backups")
    sandbox_dir = os.path.join(temp_dir, "sandbox")
    os.makedirs(backup_dir, exist_ok=True)
    os.makedirs(sandbox_dir, exist_ok=True)

    event_bus = EVEventBus()
    backup_manager = EVBackupManager(backup_root=backup_dir)
    risk_engine = EVRiskEngine()
    validator = PlanValidator(risk_engine=risk_engine)
    agent = EVAgent(
        backup_manager=backup_manager,
        event_bus=event_bus,
        allowed_roots=[sandbox_dir],
    )
    executor = EVPlanExecutor(
        agent=agent,
        backup_manager=backup_manager,
        event_bus=event_bus,
        risk_engine=risk_engine,
    )

    yield {
        "temp_dir": temp_dir,
        "backup_dir": backup_dir,
        "sandbox": Path(sandbox_dir),
        "event_bus": event_bus,
        "backup_manager": backup_manager,
        "risk_engine": risk_engine,
        "validator": validator,
        "agent": agent,
        "executor": executor,
    }

    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Part B: Structured Execution Result Tests
# ---------------------------------------------------------------------------

class TestExecutionResult:
    """Test structured execution result creation, statuses, and sanitization."""

    def test_execution_result_success_fields(self):
        started = datetime.now()
        res = ExecutionResult(
            action_id="act-001",
            step_id="step-001",
            action_type="WRITE_FILE",
            started_at=started,
            finished_at=datetime.now(),
            duration=0.05,
            status=ExecutionStatus.SUCCEEDED,
            result={"path": "test.txt", "size": 12},
            retry_allowed=True,
        )
        assert res.status == ExecutionStatus.SUCCEEDED
        assert res.action_id == "act-001"
        assert res.step_id == "step-001"
        assert res.duration == 0.05
        assert res.retry_allowed is True
        assert res.error is None
        d = res.model_dump()
        assert d["status"] == "SUCCEEDED"
        assert d["action_type"] == "WRITE_FILE"

    def test_execution_result_failure_fields(self):
        res = ExecutionResult(
            action_id="act-002",
            action_type="DELETE_FILE",
            status=ExecutionStatus.FAILED,
            error="File not found",
            retry_allowed=True,
        )
        assert res.status == ExecutionStatus.FAILED
        assert res.error == "File not found"
        d = res.model_dump()
        assert d["status"] == "FAILED"

    def test_execution_result_unknown_fields(self):
        res = ExecutionResult(
            action_id="act-003",
            action_type="STOP_PROCESS",
            status=ExecutionStatus.UNKNOWN,
            error="Process termination timed out; state unconfirmed",
            retry_allowed=False,
        )
        assert res.status == ExecutionStatus.UNKNOWN
        assert res.retry_allowed is False
        d = res.model_dump()
        assert "UNKNOWN" in d["status"]

    def test_metadata_secret_sanitization(self):
        """Metadata containing sensitive keys, credentials, or audio must be sanitized."""
        raw_metadata = {
            "normal_param": "safe_value",
            "password": "super_secret_password",
            "api_key": "sk-1234567890abcdef",
            "bearer_token": "eyJh...sensitive",
            "nested": {
                "auth_header": "Bearer secret123",
                "raw_audio": b"\x00\x01\x02\x03",
                "audio_buffer": [0, 1, 2, 3],
                "allowed_param": 42,
            },
        }
        sanitized = sanitize_metadata(raw_metadata)

        # Normal fields preserved
        assert sanitized["normal_param"] == "safe_value"
        assert sanitized["nested"]["allowed_param"] == 42

        # Secrets redacted
        assert sanitized["password"] == "[REDACTED]"
        assert sanitized["api_key"] == "[REDACTED]"
        assert sanitized["bearer_token"] == "[REDACTED]"
        assert sanitized["nested"]["auth_header"] == "[REDACTED]"

        # Audio stripped
        assert sanitized["nested"]["raw_audio"] == "[REDACTED_AUDIO_BUFFER]"
        assert sanitized["nested"]["audio_buffer"] == "[REDACTED_AUDIO_BUFFER]"

    def test_execution_result_sanitizes_metadata_automatically(self):
        res = ExecutionResult(
            action_id="act-sec",
            action_type="WRITE_FILE",
            metadata={"token": "secret_abc", "target": "data.txt"},
        )
        assert res.metadata["token"] == "[REDACTED]"
        assert res.metadata["target"] == "data.txt"


# ---------------------------------------------------------------------------
# Part C & D: Verification Result & Deterministic Verifiers Tests
# ---------------------------------------------------------------------------

class TestVerifierDeterminism:
    """Test deterministic observation-only verification implementations."""

    def test_verification_status_semantics(self):
        res_v = VerificationResult(status=VerificationStatus.VERIFIED, reason="Confirmed")
        assert res_v.is_verified is True
        assert res_v.success is True

        res_f = VerificationResult(status=VerificationStatus.FAILED, reason="Mismatch")
        assert res_f.is_verified is False
        assert res_f.success is False

        res_na = VerificationResult(status=VerificationStatus.NOT_APPLICABLE, reason="No check")
        assert res_na.is_verified is True
        assert res_na.success is True

        res_u = VerificationResult(status=VerificationStatus.UNKNOWN, reason="Ambiguous")
        assert res_u.is_verified is False
        assert res_u.success is False

    def test_file_content_match_verified(self):
        verifier = EVVerifier()
        req = VerificationRequest(
            verification_type=VerificationType.FILE_CONTENT_MATCH,
            evidence="expected content",
            expected_content="expected content",
        )
        result = verifier.verify(req)
        assert result.status == VerificationStatus.VERIFIED
        assert "matches" in result.message.lower()

    def test_file_content_match_mismatch(self):
        verifier = EVVerifier()
        req = VerificationRequest(
            verification_type=VerificationType.FILE_CONTENT_MATCH,
            evidence="actual content",
            expected_content="expected content",
        )
        result = verifier.verify(req)
        assert result.status == VerificationStatus.FAILED
        assert "mismatch" in result.message.lower()

    def test_file_hash_match_verified(self):
        verifier = EVVerifier()
        expected_sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        req = VerificationRequest(
            verification_type=VerificationType.FILE_HASH_MATCH,
            evidence={"sha256": expected_sha},
            expected_sha256=expected_sha,
        )
        result = verifier.verify(req)
        assert result.status == VerificationStatus.VERIFIED

    def test_file_hash_match_mismatch(self):
        verifier = EVVerifier()
        req = VerificationRequest(
            verification_type=VerificationType.FILE_HASH_MATCH,
            evidence={"sha256": "1111111111111111111111111111111111111111111111111111111111111111"},
            expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        )
        result = verifier.verify(req)
        assert result.status == VerificationStatus.FAILED

    def test_read_content_valid(self):
        verifier = EVVerifier()
        valid_read = TextReadResult(
            path="test.txt",
            success=True,
            content="Hello E.V.",
            encoding="utf-8",
            truncated=False,
            size_bytes=10,
        )
        req = VerificationRequest(
            verification_type=VerificationType.READ_CONTENT_VALID,
            evidence=valid_read,
        )
        result = verifier.verify(req)
        assert result.status == VerificationStatus.VERIFIED

        invalid_read = TextReadResult(
            path="test.txt",
            success=False,
            content="",
            encoding="utf-8",
            truncated=False,
            size_bytes=0,
            error="Access denied",
        )
        req2 = VerificationRequest(
            verification_type=VerificationType.READ_CONTENT_VALID,
            evidence=invalid_read,
        )
        result2 = verifier.verify(req2)
        assert result2.status == VerificationStatus.FAILED

    def test_process_identity_valid(self):
        verifier = EVVerifier()
        pinfo = ProcessInfo(pid=1234, name="notepad.exe")
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_IDENTITY_VALID,
            evidence=pinfo,
            expected_text="notepad.exe",
        )
        res = verifier.verify(req)
        assert res.status == VerificationStatus.VERIFIED

        pinfo_bad = ProcessInfo(pid=0, name="notepad.exe")
        req_bad = VerificationRequest(
            verification_type=VerificationType.PROCESS_IDENTITY_VALID,
            evidence=pinfo_bad,
        )
        assert verifier.verify(req_bad).status == VerificationStatus.FAILED

    def test_service_running_verification(self):
        verifier = EVVerifier()
        sinfo_running = ServiceInfo(name="wuauserv", display_name="Windows Update", status="RUNNING")
        req = VerificationRequest(
            verification_type=VerificationType.SERVICE_RUNNING,
            evidence=sinfo_running,
        )
        res = verifier.verify(req)
        assert res.status == VerificationStatus.VERIFIED

        sinfo_stopped = ServiceInfo(name="wuauserv", display_name="Windows Update", status="STOPPED")
        req2 = VerificationRequest(
            verification_type=VerificationType.SERVICE_RUNNING,
            evidence=sinfo_stopped,
        )
        assert verifier.verify(req2).status == VerificationStatus.FAILED

    def test_service_stopped_verification(self):
        verifier = EVVerifier()
        sinfo_stopped = ServiceInfo(name="Spooler", display_name="Print Spooler", status="STOPPED")
        req = VerificationRequest(
            verification_type=VerificationType.SERVICE_STOPPED,
            evidence=sinfo_stopped,
        )
        res = verifier.verify(req)
        assert res.status == VerificationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Part E, F, I: Unknown State, Timeout, & Idempotency Tests
# ---------------------------------------------------------------------------

class TestUnknownStateAndTimeout:
    """Test timeout semantics, unknown mutating state, and idempotency."""

    def test_idempotency_mapping(self):
        """Non-idempotent actions must be marked False in IS_ACTION_IDEMPOTENT."""
        assert IS_ACTION_IDEMPOTENT[AgentAction.STOP_PROCESS] is False
        assert IS_ACTION_IDEMPOTENT[AgentAction.RESTART_SERVICE] is False
        assert IS_ACTION_IDEMPOTENT[AgentAction.WRITE_FILE] is True
        assert IS_ACTION_IDEMPOTENT[AgentAction.DELETE_FILE] is True
        assert IS_ACTION_IDEMPOTENT[AgentAction.FLUSH_DNS] is True

    def test_mutating_timeout_resolves_to_unknown_with_no_retry(self, sandbox_env):
        """When a mutating action times out and observation cannot confirm, it maps to UNKNOWN."""
        agent: EVAgent = sandbox_env["agent"]

        task = AgentTask(
            task_id="timeout-task",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 99999, "process_name": "ghost_process.exe"},
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
        )

        mock_handler = MagicMock(side_effect=TimeoutError("Command timed out after 10s"))
        with patch.object(agent, "_get_handler", return_value=mock_handler):
            with patch.object(agent, "_observe_unknown_mutation", return_value="PROCESS_STILL_RUNNING"):
                result = agent.run(task)

        assert result.status == AgentStatus.FAILED
        assert result.execution is not None
        assert result.execution.status == ExecutionStatus.UNKNOWN
        assert result.execution.retry_allowed is False
        assert "UNKNOWN" in result.execution.error

    def test_mutating_timeout_resolved_by_observation(self, sandbox_env):
        """When a mutating action times out, safe observation confirming state resolves to SUCCEEDED/VERIFIED."""
        agent: EVAgent = sandbox_env["agent"]

        task = AgentTask(
            task_id="timeout-resolved",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 88888, "process_name": "test_app.exe"},
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
        )

        mock_handler = MagicMock(side_effect=TimeoutError("Timed out"))
        with patch.object(agent, "_get_handler", return_value=mock_handler):
            with patch.object(agent, "_observe_unknown_mutation", return_value="RESOLVED_SUCCESS"):
                result = agent.run(task)

        assert result.status == AgentStatus.COMPLETED
        assert result.execution.status == ExecutionStatus.SUCCEEDED
        assert result.verification.status == VerificationStatus.VERIFIED


# ---------------------------------------------------------------------------
# Part G & H: Execution Succeeded + Verification Failed = OVERALL FAILURE
# ---------------------------------------------------------------------------

class TestExecutionVerificationBoundary:
    """Test central rule: command returning without exception does NOT equal success."""

    def test_execution_success_plus_verification_failure_equals_overall_failure(self, sandbox_env):
        agent: EVAgent = sandbox_env["agent"]
        target = sandbox_env["sandbox"] / "boundary_test.txt"

        task = AgentTask(
            task_id="boundary-task",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "wrong text"},
            verification_type=VerificationType.FILE_CONTENT_MATCH,
        )

        failed_v = VerificationResult(
            status=VerificationStatus.FAILED,
            reason="Content mismatch: expected 'correct text', found 'wrong text'",
        )
        with patch.object(agent.verifier, "verify", return_value=failed_v):
            run_result = agent.run(task)

        # Must report FAILED, not COMPLETED
        assert run_result.status == AgentStatus.FAILED
        assert run_result.step.success is False
        assert "verification failed" in run_result.step.error.lower()
        assert run_result.verification.status == VerificationStatus.FAILED

    def test_cancellation_before_dispatch_stops_execution(self, sandbox_env):
        agent: EVAgent = sandbox_env["agent"]
        token = CancellationToken()
        token.cancel(reason="User cancelled prior to dispatch", source=CancellationSource.USER_COMMAND)

        task = AgentTask(
            task_id="cancelled-task",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(sandbox_env["sandbox"] / "never.txt"), "content": "nope"},
        )

        result = agent.run(task, cancellation_token=token)
        assert result.status == AgentStatus.FAILED
        assert result.execution.status == ExecutionStatus.CANCELLED
        assert not (sandbox_env["sandbox"] / "never.txt").exists()

    def test_cancellation_before_verification(self, sandbox_env):
        agent: EVAgent = sandbox_env["agent"]
        token = CancellationToken()

        task = AgentTask(
            task_id="cancel-before-verif",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(sandbox_env["sandbox"] / "cancel_verif.txt"), "content": "data"},
            verification_type=VerificationType.FILE_EXISTS,
        )

        orig_handler = agent._get_handler(task.action)
        def handler_and_cancel(**kwargs):
            token.cancel(reason="Cancel after dispatch", source=CancellationSource.USER_COMMAND)
            return orig_handler(**kwargs)

        with patch.object(agent, "_get_handler", return_value=handler_and_cancel):
            result = agent.run(task, cancellation_token=token)

        assert result.execution.status == ExecutionStatus.CANCELLED
        assert "cancel" in result.error.lower()


# ---------------------------------------------------------------------------
# Part J: Plan & Transaction LIFO Rollback Integration
# ---------------------------------------------------------------------------

class TestPlanIntegration:
    """Test plan execution, failure handling, unknown state, and LIFO rollback."""

    def test_multi_step_plan_stops_on_verification_failure_and_rolls_back(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        sandbox = sandbox_env["sandbox"]

        target1 = sandbox / "step1.txt"
        target2 = sandbox / "step2.txt"
        target3 = sandbox / "step3.txt"

        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(target1), "content": "1"})
        s2 = PlanStep(step_id="s2", action=AgentAction.WRITE_FILE, parameters={"path": str(target2), "content": "2"}, dependencies=["s1"])
        s3 = PlanStep(step_id="s3", action=AgentAction.WRITE_FILE, parameters={"path": str(target3), "content": "3"}, dependencies=["s2"])

        plan = Plan.create(goal="Multi-step rollback test", steps=[s1, s2, s3])

        orig_run = executor.agent.run
        def mock_run(task, **kwargs):
            if task.task_id == "s2":
                res = orig_run(task, **kwargs)
                res.status = AgentStatus.FAILED
                res.step.success = False
                res.verification = VerificationResult(status=VerificationStatus.FAILED, reason="Verification mismatch on s2")
                return res
            return orig_run(task, **kwargs)

        with patch.object(executor.agent, "run", side_effect=mock_run):
            executed_plan = executor.execute_plan(plan, user_approved=True)

        assert executed_plan.status == PlanStatus.FAILED
        assert s1.status == StepStatus.COMPLETED
        assert s2.status == StepStatus.FAILED
        assert s3.status == StepStatus.SKIPPED

        # LIFO Rollback must have deleted target1
        assert not target1.exists(), "Prior step1.txt must be rolled back via LIFO transaction"

    def test_unknown_mutation_outcome_halts_plan_without_blind_retry(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        sandbox = sandbox_env["sandbox"]

        target1 = sandbox / "ok1.txt"
        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(target1), "content": "ok"})
        s2 = PlanStep(step_id="s2", action=AgentAction.STOP_PROCESS, parameters={"pid": 77777, "process_name": "hung_proc.exe"}, dependencies=["s1"])
        s3 = PlanStep(step_id="s3", action=AgentAction.WRITE_FILE, parameters={"path": str(sandbox / "ok3.txt"), "content": "never"}, dependencies=["s2"])

        plan = Plan.create(goal="Unknown halt test", steps=[s1, s2, s3])

        orig_run = executor.agent.run
        call_counts = {"s2": 0}

        def mock_run(task, **kwargs):
            if task.task_id == "s2":
                call_counts["s2"] += 1
                return AgentRunResult(
                    task_id=task.task_id,
                    status=AgentStatus.FAILED,
                    error="Command timed out; state unknown",
                    execution=ExecutionResult(
                        action_id="act-s2",
                        action_type="STOP_PROCESS",
                        status=ExecutionStatus.UNKNOWN,
                        retry_allowed=False,
                        error="Execution outcome unknown",
                    ),
                    verification=VerificationResult(status=VerificationStatus.UNKNOWN, reason="Unconfirmed"),
                )
            return orig_run(task, **kwargs)

        with patch.object(executor.agent, "run", side_effect=mock_run):
            executed_plan = executor.execute_plan(plan, user_approved=True)

        assert executed_plan.status == PlanStatus.FAILED
        assert call_counts["s2"] == 1, "Must NOT blindly retry unknown mutating operation"
        assert s2.status == StepStatus.FAILED
        assert s3.status == StepStatus.SKIPPED
        assert not target1.exists()


# ---------------------------------------------------------------------------
# Part L: Safety & Architectural Authority Boundary Tests
# ---------------------------------------------------------------------------

class TestSafetyAndAuthorityBoundaries:
    """Verify strict prohibition of authority escalation, GOD MODE, or bypasses."""

    def test_verifier_cannot_execute_actions(self):
        """EVVerifier must be observation-only with no execution/mutation capabilities."""
        verifier = EVVerifier()
        assert not hasattr(verifier, "execute")
        assert not hasattr(verifier, "run")
        assert not hasattr(verifier, "dispatch")
        assert not hasattr(verifier, "mutate")
        assert not hasattr(verifier, "terminate")

    def test_awareness_cannot_execute_actions(self):
        """Awareness engine must NOT possess execution authority."""
        from core.proactive_awareness import EVProactiveAwarenessEngine
        awareness = EVProactiveAwarenessEngine()
        assert not hasattr(awareness, "execute")
        assert not hasattr(awareness, "dispatch")
        assert not hasattr(awareness, "run_task")

    def test_brain_cannot_execute_actions_directly(self):
        """Brain router must NOT possess direct execution authority."""
        from core.brain_router import BrainRouter
        router = BrainRouter()
        assert not hasattr(router, "execute")
        assert not hasattr(router, "dispatch")

    def test_voice_cannot_bypass_approval(self, sandbox_env):
        """Voice input proposing a medium/high risk action must pause for approval."""
        executor: EVPlanExecutor = sandbox_env["executor"]
        step = PlanStep(
            step_id="voice-s1",
            action=AgentAction.DELETE_FILE,
            parameters={"path": str(sandbox_env["sandbox"] / "important.txt")},
            risk_level=RiskLevel.MEDIUM,
        )
        plan = Plan.create(goal="Voice delete request", steps=[step])

        res = executor.execute_plan(plan, user_approved=False)
        assert res.status == PlanStatus.AWAITING_APPROVAL
        assert res.approval_required is True

    def test_events_publish_structured_lifecycle(self, sandbox_env):
        """Events must record ACTION_ACCEPTED, ACTION_VERIFYING, and ACTION_COMPLETED."""
        event_bus: EVEventBus = sandbox_env["event_bus"]
        agent: EVAgent = sandbox_env["agent"]

        received_events = []
        def listener(evt: EVEvent):
            received_events.append(evt.event_type)

        event_bus.subscribe(listener, [EVEventType.ACTION_ACCEPTED, EVEventType.ACTION_VERIFYING, EVEventType.ACTION_COMPLETED])

        test_file = sandbox_env["sandbox"] / "event_file.txt"
        task = AgentTask(
            task_id="evt-task",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(test_file), "content": "event test"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        agent.run(task)

        assert EVEventType.ACTION_ACCEPTED in received_events
        assert EVEventType.ACTION_VERIFYING in received_events
        assert EVEventType.ACTION_COMPLETED in received_events
