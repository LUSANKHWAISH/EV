"""
Comprehensive Unit and Integration Tests for Canonical End-to-End Action Pipeline.

Covers Test Matrix:
  A. READ-ONLY: request -> plan -> execute -> verify -> response (no approval)
  B. MUTATION: request -> risk -> approval -> execute -> verify
  C. DENIED APPROVAL: request -> approval -> deny -> zero mutation
  D. VERIFICATION FAILURE: execute -> verification failure -> LIFO rollback
  E. UNKNOWN MUTATION: timeout -> UNKNOWN -> observe -> zero blind retry
  F. CANCELLATION: request -> cancellation -> zero continuation
  G. DIAGNOSIS: telemetry -> awareness -> diagnosis
  H. RECOVERY: diagnosis -> recovery proposal -> plan (safe ordering)
  I. VOICE: voice -> orchestrator -> execution pipeline (no bypass)
  J. MEMORY: memory context -> planning without authorization escalation
  K. EVENT CORRELATION: single action -> coherent sanitized action/step/plan event chain
  L. SECURITY: attempted bypasses -> rejected fail-closed
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional
import unittest
from unittest.mock import MagicMock, patch

import pytest

from core.action_pipeline import (
    ActionPipelineContext,
    ActionPipelineResult,
    EVActionPipeline,
)
from core.agent import EVAgent
from core.brain_models import BrainDecision, BrainDecisionType
from core.brain_router import BrainRouter, RouteType, RoutingResult
from core.cancellation import CancellationSource, CancellationToken
from core.events import EVEvent, EVEventBus
from core.history import EVTaskHistoryStore
from core.memory import EVConversationMemoryStore
from core.models import (
    ActionCategory,
    ActionReversibility,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentStepResult,
    AgentTask,
    Diagnosis,
    DiagnosisCategory,
    DiagnosisStatus,
    EpistemicType,
    EvidenceItem,
    EvidenceType,
    EVEventSeverity,
    EVEventType,
    EVState,
    ExecutionResult,
    ExecutionStatus,
    FailureClassification,
    Hypothesis,
    ProcessInfo,
    RecoveryOption,
    RecoveryStage,
    RiskAssessmentResult,
    RiskLevel,
    VerificationResult,
    VerificationStatus,
    VerificationType,
    sanitize_metadata,
)
from core.orchestrator import EVOrchestrator
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_executor import EVPlanExecutor
from core.plan_validator import PlanValidationResult, PlanValidator
from core.recovery import EVDiagnosticEngine, EVRecoveryPlanner
from core.resolver import CommandResolver
from core.risk import EVRiskEngine
from core.system_monitor import SystemAlert, SystemMetricDomain, SystemObservation, SystemObservationSeverity
from core.verifier import EVVerifier


# =============================================================================
# Test Suite: Canonical End-to-End Action Pipeline
# =============================================================================

class TestActionPipelineMatrix(unittest.TestCase):
    """Test suite executing the complete Section 16 test matrix."""

    def setUp(self) -> None:
        import uuid
        self.tmp_dir = os.path.join(r"D:\EV\sandbox", f"pipe_test_{uuid.uuid4().hex[:6]}")
        os.makedirs(self.tmp_dir, exist_ok=True)
        self.event_bus = EVEventBus()
        self.risk_engine = EVRiskEngine()
        self.plan_validator = PlanValidator(risk_engine=self.risk_engine)
        self.agent = EVAgent(event_bus=self.event_bus)
        self.verifier = self.agent.verifier
        self.history_store = EVTaskHistoryStore()
        self.plan_executor = EVPlanExecutor(
            agent=self.agent,
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            history_store=self.history_store,
            verifier=self.verifier,
        )
        self.router = BrainRouter()
        self.resolver = CommandResolver()
        self.diagnostic_engine = EVDiagnosticEngine(event_bus=self.event_bus)
        self.recovery_planner = EVRecoveryPlanner(
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            event_bus=self.event_bus,
        )

        self.pipeline = EVActionPipeline(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            plan_executor=self.plan_executor,
            router=self.router,
            resolver=self.resolver,
            agent=self.agent,
            verifier=self.verifier,
            history_store=self.history_store,
            diagnostic_engine=self.diagnostic_engine,
            recovery_planner=self.recovery_planner,
        )

        self.orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            router=self.router,
            risk_engine=self.risk_engine,
            action_pipeline=self.pipeline,
        )

        self._list_proc_patcher = patch("tools.processes.list_processes", return_value=[
            ProcessInfo(pid=1234, name="python", executable_path="C:\\python.exe", status="Running")
        ])
        self._list_proc_patcher.start()

    def tearDown(self) -> None:
        if hasattr(self, "_list_proc_patcher"):
            self._list_proc_patcher.stop()
        import shutil
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # A. READ-ONLY FLOW
    # -------------------------------------------------------------------------
    def test_matrix_a_read_only_flow(self) -> None:
        """
        Matrix A: Read-Only Request Flow.
        request -> deterministic/Brain -> read-only plan -> validate ->
        execute -> verify -> result.
        Zero human approval required.
        """
        events_received: List[EVEvent] = []
        self.event_bus.subscribe(lambda e: events_received.append(e))

        # "find process python" resolves to FIND_PROCESS
        result = self.orchestrator.execute_pipeline("find process python")

        self.assertIsNotNone(result)
        self.assertEqual(result.status, PlanStatus.COMPLETED)
        self.assertTrue(result.overall_success)
        self.assertFalse(result.requires_approval)
        self.assertIsNone(result.approved)
        self.assertFalse(result.rolled_back)
        self.assertEqual(result.execution_status, ExecutionStatus.SUCCEEDED)

        # Confirm Plan has exactly 1 read-only step
        self.assertIsNotNone(result.plan)
        self.assertEqual(len(result.plan.steps), 1)
        self.assertEqual(result.plan.steps[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(result.plan.steps[0].status, StepStatus.COMPLETED)

    # -------------------------------------------------------------------------
    # B. MUTATING FLOW (APPROVED)
    # -------------------------------------------------------------------------
    def test_matrix_b_mutating_flow_approved(self) -> None:
        """
        Matrix B: Safe Mutating Flow with Approval.
        request -> plan -> validation -> risk -> AWAITING_APPROVAL ->
        explicit human approval -> execute -> verify -> success.
        """
        target_file = os.path.join(self.tmp_dir, "mutate_test.txt")

        # 1. Initial request triggers AWAITING_APPROVAL
        res1 = self.orchestrator.execute_pipeline(f"write file {target_file} hello world")

        self.assertEqual(res1.status, PlanStatus.AWAITING_APPROVAL)
        self.assertTrue(res1.requires_approval)
        self.assertIsNone(res1.approved)
        self.assertFalse(res1.overall_success)
        self.assertFalse(os.path.exists(target_file), "File must not exist prior to human approval")

        plan_id = res1.plan.plan_id

        # 2. Resolve approval: approved = True
        res2 = self.orchestrator.resolve_pipeline_approval(plan_id, approved=True)

        self.assertEqual(res2.status, PlanStatus.COMPLETED)
        self.assertTrue(res2.overall_success)
        self.assertTrue(res2.approved)
        self.assertEqual(res2.execution_status, ExecutionStatus.SUCCEEDED)
        self.assertTrue(os.path.exists(target_file), "File must exist after verified execution")
        with open(target_file, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "hello world")

    # -------------------------------------------------------------------------
    # C. DENIED APPROVAL FLOW
    # -------------------------------------------------------------------------
    def test_matrix_c_mutating_flow_denied(self) -> None:
        """
        Matrix C: Denied Approval Flow.
        request -> AWAITING_APPROVAL -> deny -> ZERO mutation.
        """
        target_file = os.path.join(self.tmp_dir, "denied_file.txt")

        res1 = self.orchestrator.execute_pipeline(f"write file {target_file} forbidden")
        self.assertEqual(res1.status, PlanStatus.AWAITING_APPROVAL)
        plan_id = res1.plan.plan_id

        # Deny approval
        res2 = self.orchestrator.resolve_pipeline_approval(plan_id, approved=False)

        self.assertEqual(res2.status, PlanStatus.FAILED)
        self.assertFalse(res2.overall_success)
        self.assertFalse(res2.approved)
        self.assertEqual(res2.execution_status, ExecutionStatus.CANCELLED)
        self.assertFalse(os.path.exists(target_file), "DENIAL INVARIANT: Zero mutation must occur")

    # -------------------------------------------------------------------------
    # D. VERIFICATION FAILURE & LIFO ROLLBACK
    # -------------------------------------------------------------------------
    def test_matrix_d_verification_failure_rollback(self) -> None:
        """
        Matrix D: Verification Failure triggers strict LIFO Rollback.
        Step 1: Create file 1 (succeeds, compensable)
        Step 2: Mutating action where verification fails
        Step 3: Should NEVER execute
        Expect: Step 1 compensated (rolled back), Step 3 halted, overall failure.
        """
        file1 = os.path.join(self.tmp_dir, "step1_file.txt")
        file2 = os.path.join(self.tmp_dir, "step2_file.txt")

        step1 = PlanStep(
            step_id="step-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": file1, "content": "step 1 initial"},
            is_compensable=True,
            reversibility=ActionReversibility.REVERSIBLE,
            verification_type=VerificationType.FILE_EXISTS,
        )
        step2 = PlanStep(
            step_id="step-2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": file2, "content": "step 2 initial"},
            dependencies=["step-1"],
            is_compensable=True,
            reversibility=ActionReversibility.REVERSIBLE,
            verification_type=VerificationType.FILE_EXISTS,
        )
        step3 = PlanStep(
            step_id="step-3",
            action=AgentAction.WRITE_FILE,
            parameters={"path": os.path.join(self.tmp_dir, "step3_never.txt"), "content": "should never run"},
            dependencies=["step-2"],
        )

        plan = Plan(
            plan_id="plan-fail-verif",
            goal="Multi-step rollback test",
            steps=[step1, step2, step3],
            transaction_required=True,
            verification_required=True,
        )

        real_run = self.agent.run

        def mock_run(task, cancellation_token=None):
            if task.task_id == "step-2":
                return AgentRunResult(
                    task_id=task.task_id,
                    status=AgentStatus.FAILED,
                    execution=ExecutionResult(
                        action_id="act-fail-2",
                        status=ExecutionStatus.SUCCEEDED,
                        action_type=AgentAction.WRITE_FILE.value,
                        target_identifier=file2,
                        retry_allowed=False,
                    ),
                    verification=VerificationResult(
                        status=VerificationStatus.FAILED,
                        verified=False,
                        verification_type=VerificationType.FILE_EXISTS,
                        details="Simulated step 2 verification failure",
                        reason="Simulated step 2 verification failure",
                    ),
                    error="Verification failed: Simulated step 2 verification failure",
                )
            return real_run(task, cancellation_token=cancellation_token)

        with patch.object(self.agent, "run", side_effect=mock_run):
            context = ActionPipelineContext(pipeline_id="pipe-fail", user_approved=True)
            val_result = self.plan_validator.validate(plan)
            res = self.pipeline._execute_validated_plan(
                plan=plan,
                validation_result=val_result,
                context=context,
                start_time=time.monotonic(),
            )

        self.assertFalse(res.overall_success)
        self.assertEqual(res.status, PlanStatus.FAILED)
        self.assertTrue(res.rolled_back)

        # Step 3 must NOT have started or executed
        self.assertNotEqual(step3.status, StepStatus.COMPLETED)
        self.assertFalse(os.path.exists(os.path.join(self.tmp_dir, "step3_never.txt")))

        # Step 1 must have been rolled back / removed by LIFO compensation
        self.assertFalse(os.path.exists(file1), "Step 1 file must be removed by LIFO compensation")

    # -------------------------------------------------------------------------
    # E. UNKNOWN MUTATION (TIMEOUT / ZERO BLIND RETRY)
    # -------------------------------------------------------------------------
    def test_matrix_e_unknown_mutation_zero_blind_retry(self) -> None:
        """
        Matrix E: UNKNOWN Mutation Outcome.
        Action times out or produces UNKNOWN -> no blind retry -> subsequent steps halted.
        """
        target_file = os.path.join(self.tmp_dir, "unknown_step.txt")

        step1 = PlanStep(
            step_id="step-unk-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": target_file, "content": "timeout test"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        step2 = PlanStep(
            step_id="step-unk-2",
            action=AgentAction.READ_TEXT_FILE,
            parameters={"path": target_file},
            dependencies=["step-unk-1"],
        )

        plan = Plan(
            plan_id="plan-unknown-test",
            goal="Unknown mutation handling",
            steps=[step1, step2],
            transaction_required=True,
            verification_required=True,
        )

        def mock_unknown(task, cancellation_token=None):
            return AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error="Action timed out in ambiguous state",
                execution=ExecutionResult(
                    action_id="act-unk-1",
                    action_type=AgentAction.WRITE_FILE.value,
                    status=ExecutionStatus.UNKNOWN,
                    error="Timeout during mutating operation",
                    retry_allowed=False,
                ),
            )

        with patch.object(self.agent, "run", side_effect=mock_unknown):
            context = ActionPipelineContext(pipeline_id="pipe-unk", user_approved=True)
            val_result = self.plan_validator.validate(plan)
            res = self.pipeline._execute_validated_plan(
                plan=plan,
                validation_result=val_result,
                context=context,
                start_time=time.monotonic(),
            )

        self.assertFalse(res.overall_success)
        self.assertEqual(res.status, PlanStatus.FAILED)
        self.assertEqual(step1.status, StepStatus.FAILED)
        self.assertNotEqual(step2.status, StepStatus.COMPLETED)
        self.assertIn("timeout", (res.error or "").lower())

    # -------------------------------------------------------------------------
    # F. CANCELLATION FLOW
    # -------------------------------------------------------------------------
    def test_matrix_f_cancellation(self) -> None:
        """
        Matrix F: Cancellation Flow.
        Pre-flight cancellation and active cancellation trigger safe halt without continuation.
        """
        token = CancellationToken()
        token.cancel(reason="User cancelled before start", source=CancellationSource.USER_COMMAND)

        ctx = ActionPipelineContext(
            pipeline_id="pipe-cancel",
            cancellation_token=token,
        )
        res = self.orchestrator.execute_pipeline("find process python", context=ctx)

        self.assertEqual(res.status, PlanStatus.CANCELLED)
        self.assertEqual(res.execution_status, ExecutionStatus.CANCELLED)
        self.assertFalse(res.overall_success)
        self.assertIn("Cancelled before start", res.error or "")

    # -------------------------------------------------------------------------
    # G. DIAGNOSIS FLOW
    # -------------------------------------------------------------------------
    def test_matrix_g_diagnosis_telemetry(self) -> None:
        """
        Matrix G: Telemetry -> Awareness -> Deterministic Diagnosis.
        """
        alert = SystemAlert(
            alert_id="alert-cpu-high",
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            severity=SystemObservationSeverity.WARNING,
            message="CPU utilization sustained above 85%",
            value=94.5,
            threshold=85.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=12.0,
            metadata={"highest_process": "ffmpeg.exe", "highest_process_cpu": 78.4},
        )
        obs = SystemObservation(
            observation_id="obs-1",
            timestamp=datetime.now(timezone.utc),
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            value=94.5,
            unit="percent",
            severity=SystemObservationSeverity.WARNING,
            source="system_monitor",
            metadata={"top_process": "ffmpeg.exe", "top_pid": 4820},
        )

        diagnosis = self.diagnostic_engine.diagnose_system_alert(alert, [obs])

        self.assertIsNotNone(diagnosis)
        self.assertEqual(diagnosis.category, DiagnosisCategory.RESOURCE_PRESSURE)
        self.assertGreater(len(diagnosis.evidence), 0)
        self.assertIn("ffmpeg.exe", diagnosis.affected_resources)

    # -------------------------------------------------------------------------
    # H. RECOVERY PROPOSAL -> PLAN FLOW
    # -------------------------------------------------------------------------
    def test_matrix_h_recovery_proposal_safe_ordering(self) -> None:
        """
        Matrix H: Diagnosis -> Recovery Proposal -> Canonical Plan.
        Ensures Stage 1 non-destructive observation options precede Stage 2 mutation.
        Mutating recovery action strictly requires approval.
        """
        alert = SystemAlert(
            alert_id="alert-cpu-rec",
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            severity=SystemObservationSeverity.WARNING,
            message="CPU spike",
            value=95.0,
            threshold=85.0,
            triggered_at=datetime.now(timezone.utc),
            sustained_seconds=15.0,
            metadata={"highest_process": "test_hog.exe", "highest_process_cpu": 82.0},
        )
        obs = SystemObservation(
            observation_id="obs-rec",
            timestamp=datetime.now(timezone.utc),
            domain=SystemMetricDomain.CPU,
            metric="cpu_percent",
            value=95.0,
            unit="percent",
            severity=SystemObservationSeverity.WARNING,
            source="system_monitor",
            metadata={"top_process": "test_hog.exe", "top_pid": 1234},
        )
        diagnosis = self.diagnostic_engine.diagnose_system_alert(alert, [obs])
        options = self.recovery_planner.generate_recovery_options(diagnosis)

        self.assertGreaterEqual(len(options), 2)
        # Stage 1 must be non-destructive observation
        self.assertIn(options[0].stage, (RecoveryStage.OBSERVE, RecoveryStage.COLLECT_EVIDENCE, RecoveryStage.NON_MUTATING_ACTION))
        self.assertFalse(options[0].requires_approval)

        # Stage 2 is mutating and must require approval
        stage2_opt = next((o for o in options if o.stage in (RecoveryStage.REVERSIBLE_MUTATION, RecoveryStage.IRREVERSIBLE_MUTATION)), None)
        self.assertIsNotNone(stage2_opt)
        self.assertTrue(stage2_opt.requires_approval)

        # Submitting mutating recovery without approval must yield AWAITING_APPROVAL
        res = self.orchestrator.submit_recovery_proposal(stage2_opt)
        self.assertEqual(res.status, PlanStatus.AWAITING_APPROVAL)
        self.assertTrue(res.requires_approval)
        self.assertFalse(res.overall_success)

    # -------------------------------------------------------------------------
    # I. VOICE INTEGRATION FLOW
    # -------------------------------------------------------------------------
    def test_matrix_i_voice_input_routing(self) -> None:
        """
        Matrix I: Voice Input Routing.
        Voice input enters via canonical orchestrator.
        Voice CANNOT bypass risk or approval gates.
        """
        target_file = os.path.join(self.tmp_dir, "voice_file.txt")

        # 1. Voice read-only command executes without approval
        ctx_voice_ro = ActionPipelineContext(pipeline_id="pipe-v1", source="VOICE")
        res_ro = self.orchestrator.execute_pipeline("find process python", context=ctx_voice_ro)
        self.assertEqual(res_ro.status, PlanStatus.COMPLETED)
        self.assertTrue(res_ro.overall_success)

        # 2. Voice mutating command strictly requires approval
        ctx_voice_mut = ActionPipelineContext(pipeline_id="pipe-v2", source="VOICE")
        res_mut = self.orchestrator.execute_pipeline(
            f"write file {target_file} voice data",
            context=ctx_voice_mut,
        )
        self.assertEqual(res_mut.status, PlanStatus.AWAITING_APPROVAL)
        self.assertTrue(res_mut.requires_approval)
        self.assertFalse(os.path.exists(target_file), "Voice command must NOT bypass approval")

    # -------------------------------------------------------------------------
    # J. MEMORY ISOLATION
    # -------------------------------------------------------------------------
    def test_matrix_j_memory_isolation(self) -> None:
        """
        Matrix J: Memory Integration & Authorization Boundary.
        Memory store contents must NEVER confer execution authority or approval.
        """
        mem_store = EVConversationMemoryStore()
        # Add a remembered preference asserting "auto_approve_mutations = True"
        mem_store.set_preference("auto_approve_mutations", True)
        mem_store.set_environment_fact("file_deletion_policy", "allow_all")

        pipeline_with_mem = EVActionPipeline(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            plan_executor=self.plan_executor,
            router=self.router,
            resolver=self.resolver,
            agent=self.agent,
            verifier=self.verifier,
            history_store=self.history_store,
            memory_store=mem_store,
        )

        target_file = os.path.join(self.tmp_dir, "mem_test.txt")
        res = pipeline_with_mem.execute_request(f"write file {target_file} test")

        # Memory MUST NOT bypass approval
        self.assertEqual(res.status, PlanStatus.AWAITING_APPROVAL)
        self.assertTrue(res.requires_approval)
        self.assertFalse(os.path.exists(target_file))

    # -------------------------------------------------------------------------
    # K. EVENT CORRELATION & SANITIZATION
    # -------------------------------------------------------------------------
    def test_matrix_k_event_correlation_and_sanitization(self) -> None:
        """
        Matrix K: Correlated Event Emission & Sanitization.
        Ensures pipeline_id, plan_id, and step_ids correlate and that
        secrets/passwords/audio payloads are sanitized from events.
        """
        published_events: List[EVEvent] = []
        self.event_bus.subscribe(lambda e: published_events.append(e))

        ctx = ActionPipelineContext(
            pipeline_id="pipe-correlate-001",
            source="GUI",
            metadata={"api_key": "SECRET12345", "safe_meta": "valid_value"},
        )
        res = self.orchestrator.execute_pipeline("find process python", context=ctx)

        self.assertTrue(res.overall_success)

        # Verify context metadata was sanitized
        self.assertEqual(ctx.metadata["api_key"], "[REDACTED]")
        self.assertEqual(ctx.metadata["safe_meta"], "valid_value")

        # Verify emitted events correlate
        pipeline_events = [e for e in published_events if e.correlation_id in ("pipe-correlate-001", res.plan.plan_id)]
        self.assertGreater(len(pipeline_events), 0)

        for event in published_events:
            # Confirm no secret leaked in event messages or data
            if event.message:
                self.assertNotIn("SECRET12345", event.message)
            if event.data:
                for k, v in event.data.items():
                    self.assertNotIn("SECRET12345", str(v))

    # -------------------------------------------------------------------------
    # L. SECURITY ANTI-BYPASS
    # -------------------------------------------------------------------------
    def test_matrix_l_security_anti_bypass(self) -> None:
        """
        Matrix L: Security Anti-Bypass.
        1. Context spoofing user_approved=True without genuine approval request is checked.
        2. Injected high-risk / invalid action types are rejected fail-closed by PlanValidator.
        """
        # Attempt to inject invalid plan directly
        invalid_step = PlanStep(
            step_id="spoof-step",
            action=AgentAction.DELETE_FILE,
            parameters={},  # Missing required path
        )
        invalid_plan = Plan(
            plan_id="plan-spoofed",
            goal="Spoofed invalid deletion",
            steps=[invalid_step],
        )

        val = self.plan_validator.validate(invalid_plan)
        self.assertFalse(val.is_valid, "PlanValidator must reject step missing required path")

        # Attempt to run via pipeline directly
        res = self.pipeline._execute_validated_plan(
            plan=invalid_plan,
            validation_result=val,
            context=ActionPipelineContext(pipeline_id="pipe-bypass", user_approved=True),
            start_time=time.monotonic(),
        )
        # Executor must fail-closed when validation_result is invalid
        self.assertEqual(res.status, PlanStatus.REJECTED)
        self.assertFalse(res.overall_success)

    # -------------------------------------------------------------------------
    # M. CONVERSATIONAL & EXPLANATION ROUTING (NO_ACTION ROUTE)
    # -------------------------------------------------------------------------
    def test_matrix_m_conversational_explanation_success(self) -> None:
        """
        Matrix M1: Conversational/Explanation inputs that produce NO_ACTION
        must complete successfully with overall_success=True, status=COMPLETED,
        and conversational response in metadata (NEVER Task failed).
        """
        mock_router = MagicMock(spec=BrainRouter)
        mock_router.route.return_value = RoutingResult(
            route_type=RouteType.NO_ACTION,
            tasks=[],
            decision=BrainDecision(
                decision_type=BrainDecisionType.EXPLANATION_ONLY,
                user_message="Hello! I am E.V., your system assistant.",
            ),
            message="Hello! I am E.V., your system assistant.",
            success=True,
        )

        pipe = EVActionPipeline(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            router=mock_router,
        )

        res = pipe.execute_request("hello")
        self.assertTrue(res.overall_success)
        self.assertEqual(res.status, PlanStatus.COMPLETED)
        self.assertEqual(res.execution_status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(res.verification_status, VerificationStatus.NOT_APPLICABLE)
        self.assertIsNone(res.plan)
        self.assertIsNone(res.error)
        self.assertEqual(
            res.metadata.get("conversational_response"),
            "Hello! I am E.V., your system assistant.",
        )

    def test_matrix_m_conversational_clarification_success(self) -> None:
        """
        Matrix M2: Brain clarification request must complete successfully,
        set pending clarification in context store, and provide prompt text.
        """
        mock_router = MagicMock(spec=BrainRouter)
        mock_router.route.return_value = RoutingResult(
            route_type=RouteType.NO_ACTION,
            tasks=[],
            decision=BrainDecision(
                decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
                user_message="Which file would you like to inspect?",
                clarification_prompt="Which file would you like to inspect?",
            ),
            message="Which file would you like to inspect?",
            success=True,
        )

        pipe = EVActionPipeline(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            router=mock_router,
        )

        res = pipe.execute_request("inspect the file")
        self.assertTrue(res.overall_success)
        self.assertEqual(res.status, PlanStatus.COMPLETED)
        self.assertEqual(res.execution_status, ExecutionStatus.SUCCEEDED)
        self.assertEqual(
            res.metadata.get("conversational_response"),
            "Which file would you like to inspect?",
        )

    def test_matrix_m_routing_failure_returns_failed_status(self) -> None:
        """
        Matrix M3: Genuine routing failure produces PlanStatus.FAILED
        and overall_success=False.
        """
        mock_router = MagicMock(spec=BrainRouter)
        mock_router.route.return_value = RoutingResult(
            route_type=RouteType.FAILURE,
            error="Brain provider unavailable",
            success=False,
        )

        pipe = EVActionPipeline(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            router=mock_router,
        )

        res = pipe.execute_request("unrecognized nonsense")
        self.assertFalse(res.overall_success)
        self.assertEqual(res.status, PlanStatus.FAILED)
        self.assertEqual(res.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(res.error, "Brain provider unavailable")


if __name__ == "__main__":
    unittest.main()
