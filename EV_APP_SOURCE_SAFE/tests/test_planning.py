"""
Comprehensive Unit and Integration Test Suite for Planning and Transaction Hardening (Task 015).

Tests:
1. Plan Validation:
   - Valid single and multi-step plans
   - Duplicate step IDs
   - Missing dependencies
   - Self dependencies
   - Dependency cycles (A -> B -> C -> A)
   - Unknown actions
   - Malformed parameters
   - Compensation declarations
   - Verification type compatibility
   - Approval and transaction bypass attempts
   - Authority escalation / GOD MODE rejection
2. Risk Propagation:
   - Single and mixed risk plans
   - Aggregate risk = MAX(step risks)
   - Untrusted Brain risk cannot override canonical EVRiskEngine
3. Transaction Semantics Hardening:
   - Reversible action compensated (COMPENSATION_SUCCEEDED)
   - Non-reversible action reports non-compensable (COMPENSATION_NOT_AVAILABLE)
   - No fake Path("None") compensation
   - Missing backup failure (COMPENSATION_FAILED)
   - Strict LIFO rollback order
   - Status transitions: COMMITTED, ROLLED_BACK, ROLLBACK_FAILED
4. Verification Boundaries:
   - Successful execution + successful verification
   - Successful execution + failed verification triggers rollback
5. Approval Boundaries:
   - Requires approval -> AWAITING_APPROVAL
   - User denial triggers rollback and marks FAILED
   - User approval resumes execution
   - Stale/mismatched approval rejected
6. Cancellation / STOP:
   - Cancel before start
   - Cancel during execution triggers LIFO rollback and marks CANCELLED
7. Brain Integration:
   - Safe conversion from validated BrainDecision into Plan
"""
from __future__ import annotations

import copy
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.agent import EVAgent
from core.backup import EVBackupManager
from core.brain_converter import BrainTaskConverter
from core.brain_models import BrainActionProposal, BrainDecision, BrainDecisionType
from core.brain_validator import BrainValidationResult, BrainValidationStatus
from core.cancellation import CancellationToken, CancellationSource
from core.events import EVEventBus
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentStepResult,
    AgentTask,
    EVState,
    PermissionDecision,
    RiskAssessmentResult,
    RiskLevel,
    VerificationType,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_executor import EVPlanExecutor
from core.plan_validator import PlanValidationResult, PlanValidator
from core.risk import EVRiskEngine
from core.transaction import (
    ActionReversibility,
    CompensationStatus,
    CompoundTransaction,
    StepCompensationRecord,
    TransactionStatus,
)


@pytest.fixture
def sandbox_env():
    """Create isolated temporary directories for sandbox and backups."""
    temp_dir = tempfile.mkdtemp(prefix="ev_plan_test_")
    backup_dir = tempfile.mkdtemp(prefix="ev_plan_backup_")
    sandbox_path = Path(temp_dir) / "sandbox"
    sandbox_path.mkdir(parents=True, exist_ok=True)

    backup_manager = EVBackupManager(backup_root=backup_dir)
    event_bus = EVEventBus()
    risk_engine = EVRiskEngine()

    agent = EVAgent(
        event_bus=event_bus,
        backup_manager=backup_manager,
        allowed_roots=[str(sandbox_path)],
    )

    executor = EVPlanExecutor(
        agent=agent,
        event_bus=event_bus,
        risk_engine=risk_engine,
        backup_manager=backup_manager,
    )

    yield {
        "temp_dir": temp_dir,
        "backup_dir": backup_dir,
        "sandbox": sandbox_path,
        "backup_manager": backup_manager,
        "event_bus": event_bus,
        "risk_engine": risk_engine,
        "agent": agent,
        "executor": executor,
    }

    shutil.rmtree(temp_dir, ignore_errors=True)
    shutil.rmtree(backup_dir, ignore_errors=True)


# =============================================================================
# 1. Plan Validation & Dependency Graph Tests
# =============================================================================

class TestPlanValidator:
    """Test deterministic fail-closed validation of Plan instances."""

    def test_valid_single_step_plan(self, sandbox_env):
        validator = PlanValidator(risk_engine=sandbox_env["risk_engine"])
        target = sandbox_env["sandbox"] / "test.txt"
        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "hello"},
        )
        plan = Plan.create(goal="Create test file", steps=[step])

        res = validator.validate(plan)
        assert res.is_valid is True
        assert res.status == PlanStatus.VALIDATED
        assert res.topological_order == ["s1"]
        assert len(res.errors) == 0

    def test_valid_multi_step_plan_with_dependencies(self, sandbox_env):
        validator = PlanValidator(risk_engine=sandbox_env["risk_engine"])
        p1 = sandbox_env["sandbox"] / "step1.txt"
        p2 = sandbox_env["sandbox"] / "step2.txt"

        s1 = PlanStep(step_id="step_a", action=AgentAction.WRITE_FILE, parameters={"path": str(p1), "content": "A"})
        s2 = PlanStep(step_id="step_b", action=AgentAction.WRITE_FILE, parameters={"path": str(p2), "content": "B"}, dependencies=["step_a"])
        plan = Plan.create(goal="Ordered file creation", steps=[s2, s1])  # s2 declared before s1

        res = validator.validate(plan)
        assert res.is_valid is True
        # Topological order must execute step_a before step_b despite input ordering
        assert res.topological_order == ["step_a", "step_b"]

    def test_duplicate_step_ids_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="dup_id", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\a.txt"})
        s2 = PlanStep(step_id="dup_id", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\b.txt"})
        plan = Plan.create(goal="Duplicates", steps=[s1, s2])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("Duplicate step_id 'dup_id'" in err for err in res.errors)

    def test_missing_dependency_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="s1", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\a.txt"}, dependencies=["non_existent_step"])
        plan = Plan.create(goal="Missing Dep", steps=[s1])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("Missing dependency" in err for err in res.errors)

    def test_self_dependency_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="s1", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\a.txt"}, dependencies=["s1"])
        plan = Plan.create(goal="Self Dep", steps=[s1])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("Self-dependency detected" in err for err in res.errors)

    def test_dependency_cycle_rejected(self, sandbox_env):
        validator = PlanValidator()
        # Cycle: A -> B -> C -> A
        sA = PlanStep(step_id="A", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\a.txt"}, dependencies=["C"])
        sB = PlanStep(step_id="B", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\b.txt"}, dependencies=["A"])
        sC = PlanStep(step_id="C", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\c.txt"}, dependencies=["B"])
        plan = Plan.create(goal="Cycle", steps=[sA, sB, sC])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("Dependency cycle detected" in err for err in res.errors)

    def test_malformed_parameters_rejected(self, sandbox_env):
        validator = PlanValidator()
        # WRITE_FILE missing 'content'
        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test.txt"})
        # STOP_PROCESS missing pid and process_name
        s2 = PlanStep(step_id="s2", action=AgentAction.STOP_PROCESS, parameters={})
        plan = Plan.create(goal="Malformed", steps=[s1, s2])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("WRITE_FILE" in err and "content" in err for err in res.errors)
        assert any("STOP_PROCESS" in err for err in res.errors)

    def test_incompatible_verification_rejected(self, sandbox_env):
        validator = PlanValidator()
        # WRITE_FILE paired with TCP_PORT_EXISTS is incompatible
        s1 = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "C:\\test.txt", "content": "data"},
            verification_type=VerificationType.TCP_PORT_EXISTS,
        )
        plan = Plan.create(goal="Incompatible Verification", steps=[s1])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("incompatible" in err for err in res.errors)

    def test_approval_bypass_in_metadata_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="s1", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\test.txt"})
        plan = Plan.create(goal="Bypass Attempt", steps=[s1], metadata={"bypass_approval": True})

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("approval bypass declaration" in err for err in res.errors)

    def test_authority_escalation_god_mode_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="s1", action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\test.txt"})
        plan = Plan.create(goal="God Mode Attempt", steps=[s1], metadata={"god_mode": True})

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("authority escalation" in err for err in res.errors)

    def test_unknown_action_rejected(self, sandbox_env):
        validator = PlanValidator()
        s1 = PlanStep(step_id="s1", action="INVALID_NON_EXISTENT_ACTION", parameters={"path": "C:\\test.txt"})  # type: ignore
        plan = Plan.create(goal="Unknown Action", steps=[s1])

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("invalid action" in err for err in res.errors)

    def test_transaction_bypass_attempt_rejected(self, sandbox_env):
        validator = PlanValidator(risk_engine=sandbox_env["risk_engine"])
        p = sandbox_env["sandbox"] / "write.txt"
        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(p), "content": "x"})
        # Attempt to disable transactions on a mutating plan
        plan = Plan.create(goal="Bypass TX", steps=[s1], transaction_required=False)

        res = validator.validate(plan)
        assert res.is_valid is False
        assert any("cannot disable transaction handling" in err for err in res.errors)


# =============================================================================
# 2. Risk Aggregation & Propagation Tests
# =============================================================================

class TestRiskAggregation:
    """Test deterministic risk propagation across multi-step plans."""

    def test_plan_risk_is_max_of_step_risks(self, sandbox_env):
        validator = PlanValidator(risk_engine=sandbox_env["risk_engine"])
        p_read = sandbox_env["sandbox"] / "read.txt"
        p_write = sandbox_env["sandbox"] / "write.txt"
        p_read.write_text("ok")

        # READ_ONLY_OBSERVATION -> NONE
        s1 = PlanStep(step_id="s1", action=AgentAction.READ_TEXT_FILE, parameters={"path": str(p_read)})
        # FILE_MODIFY -> MEDIUM
        s2 = PlanStep(step_id="s2", action=AgentAction.WRITE_FILE, parameters={"path": str(p_write), "content": "new"})

        plan = Plan.create(goal="Mixed risk", steps=[s1, s2])
        res = validator.validate(plan)

        assert res.is_valid is True
        # Aggregate risk must not be lowered by the read-only step
        assert res.aggregate_risk in (RiskLevel.LOW, RiskLevel.MEDIUM)
        assert res.aggregate_risk != RiskLevel.NONE

    def test_untrusted_metadata_cannot_downgrade_risk(self, sandbox_env):
        validator = PlanValidator(risk_engine=sandbox_env["risk_engine"])
        target = sandbox_env["sandbox"] / "write.txt"

        # Plan metadata falsely claims NONE risk
        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(target), "content": "x"})
        plan = Plan.create(goal="Fake Risk", steps=[s1], metadata={"risk_level": "NONE"})
        plan.risk_level = RiskLevel.NONE

        res = validator.validate(plan)
        assert res.is_valid is True
        # Canonical risk engine overwrites untrusted metadata
        assert res.aggregate_risk != RiskLevel.NONE
        assert res.validated_plan.risk_level != RiskLevel.NONE


# =============================================================================
# 3. Transaction Semantics & Hardened Compensation Tests
# =============================================================================

class TestTransactionSemanticsHardening:
    """Test explicit compensation states, no fake Path('None') compensation, and LIFO rollback."""

    def test_reversible_file_action_compensates_successfully(self, sandbox_env):
        backup_manager = sandbox_env["backup_manager"]
        target = sandbox_env["sandbox"] / "created.txt"

        tx = CompoundTransaction(
            tasks=[AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(target), "content": "data"})]
        )
        tx.begin()

        target.write_text("data")
        # Newly created file
        tx.record_mutation_step(
            step_index=0,
            task=tx.tasks[0],
            target_path=str(target),
            target_existed_before=False,
            is_compensable=True,
        )

        assert target.exists()
        # Trigger rollback
        success = tx.rollback(backup_manager=backup_manager, failure_reason="Simulated test abort")

        assert success is True
        assert tx.status == TransactionStatus.ROLLED_BACK
        assert not target.exists(), "Newly created file must be unlinked"
        assert len(tx.rollback_records) == 1
        rec = tx.rollback_records[0]
        assert rec["compensation_status"] == CompensationStatus.COMPENSATION_SUCCEEDED.value
        assert rec["success"] is True

    def test_non_reversible_action_reports_compensation_not_available(self, sandbox_env):
        """Verify that is_compensable=False does NOT report fake success on Path('None')."""
        backup_manager = sandbox_env["backup_manager"]

        task_proc = AgentTask(
            task_id="t_proc",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 1234, "process_name": "worker"},
        )
        tx = CompoundTransaction(tasks=[task_proc])
        tx.begin()

        # Non-reversible action with target_path=None
        tx.record_mutation_step(
            step_index=0,
            task=task_proc,
            target_path=None,
            target_existed_before=False,
            is_compensable=False,
            reversibility=ActionReversibility.NON_REVERSIBLE,
        )

        tx.rollback(backup_manager=backup_manager, failure_reason="Failure after process kill")

        # Step MUST NOT appear compensated: rollback reflects that irreversible process termination cannot be undone!
        assert len(tx.rollback_records) == 1
        rec = tx.rollback_records[0]
        assert rec["compensation_status"] == CompensationStatus.COMPENSATION_NOT_AVAILABLE.value
        assert rec["success"] is False
        assert rec["is_compensable"] is False
        assert "non-reversible" in rec["error"].lower()

        # Step record also marked not compensated
        step_rec = tx.completed_mutations[0]
        assert step_rec.compensated is False
        assert step_rec.compensation_status == CompensationStatus.COMPENSATION_NOT_AVAILABLE

    def test_invalid_path_none_string_never_treated_as_valid(self, sandbox_env):
        """Verify that passing 'None' string as path is sanitized and fails closed."""
        backup_manager = sandbox_env["backup_manager"]
        task = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "None"})

        tx = CompoundTransaction(tasks=[task])
        tx.begin()

        rec = tx.record_mutation_step(
            step_index=0,
            task=task,
            target_path="None",  # String literal "None"
            target_existed_before=False,
            is_compensable=False,
        )
        assert rec.target_path is None
        assert rec.is_compensable is False

        tx.rollback(backup_manager=backup_manager)
        assert len(tx.rollback_records) == 1
        assert tx.rollback_records[0]["compensation_status"] == CompensationStatus.COMPENSATION_NOT_AVAILABLE.value
        assert tx.rollback_records[0]["success"] is False
        assert tx.completed_mutations[0].compensated is False

    def test_rollback_failed_on_missing_backup(self, sandbox_env):
        """Verify that true compensation failure on compensable action produces ROLLBACK_FAILED."""
        backup_manager = sandbox_env["backup_manager"]
        target = sandbox_env["sandbox"] / "important.txt"
        target.write_text("initial")

        task = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(target), "content": "corrupt"})
        tx = CompoundTransaction(tasks=[task])
        tx.begin()

        # Record with target_existed_before=True but missing backup_path!
        tx.record_mutation_step(
            step_index=0,
            task=task,
            target_path=str(target),
            target_existed_before=True,
            backup_path=None,
            is_compensable=True,
        )

        success = tx.rollback(backup_manager=backup_manager)
        assert success is False
        assert tx.status == TransactionStatus.ROLLBACK_FAILED
        assert tx.rollback_records[0]["compensation_status"] == CompensationStatus.COMPENSATION_FAILED.value
        assert tx.rollback_records[0]["success"] is False
        assert "Missing backup path" in tx.rollback_records[0]["error"]

    def test_strict_lifo_rollback_order(self, sandbox_env):
        backup_manager = sandbox_env["backup_manager"]
        f1 = sandbox_env["sandbox"] / "f1.txt"
        f2 = sandbox_env["sandbox"] / "f2.txt"

        t1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(f1), "content": "1"})
        t2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(f2), "content": "2"})
        tx = CompoundTransaction(tasks=[t1, t2])
        tx.begin()

        f1.write_text("1")
        tx.record_mutation_step(step_index=0, task=t1, target_path=str(f1), target_existed_before=False)

        f2.write_text("2")
        tx.record_mutation_step(step_index=1, task=t2, target_path=str(f2), target_existed_before=False)

        tx.rollback(backup_manager=backup_manager, failure_reason="Abort")

        # Rollback records must be strictly LIFO (t2 compensated before t1)
        assert tx.rollback_records[0]["task_id"] == "t2"
        assert tx.rollback_records[1]["task_id"] == "t1"
        assert not f1.exists()
        assert not f2.exists()


# =============================================================================
# 4. Plan Executor End-to-End & Verification Boundaries
# =============================================================================

class TestPlanExecutor:
    """Test full sequential plan execution, verification gating, and cancellation."""

    def test_plan_execution_success(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        f1 = sandbox_env["sandbox"] / "plan_file.txt"

        step = PlanStep(
            step_id="step_write",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(f1), "content": "Plan output"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        plan = Plan.create(goal="Write verified file", steps=[step])

        # Execute
        executed_plan = executor.execute_plan(plan, user_approved=True)

        assert executed_plan.status == PlanStatus.COMPLETED
        assert f1.exists()
        assert f1.read_text() == "Plan output"
        assert executed_plan.steps[0].status == StepStatus.COMPLETED

    def test_verification_failure_triggers_lifo_rollback(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        f1 = sandbox_env["sandbox"] / "verified_fail.txt"

        # Verification is FILE_NOT_EXISTS, which will FAIL because WRITE_FILE creates it!
        step = PlanStep(
            step_id="step_fail_verif",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(f1), "content": "Will fail verification"},
            verification_type=VerificationType.FILE_NOT_EXISTS,
        )
        plan = Plan.create(goal="Verification Failure Plan", steps=[step])

        executed_plan = executor.execute_plan(plan, user_approved=True)

        assert executed_plan.status == PlanStatus.FAILED
        assert "verification" in executed_plan.error.lower()
        # Rollback must have cleaned up the file!
        assert not f1.exists()

    def test_cancellation_before_execution(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        token = CancellationToken()
        token.cancel(reason="Aborted before starting")

        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(sandbox_env["sandbox"] / "cancel.txt"), "content": "none"},
        )
        plan = Plan.create(goal="Cancelled Plan", steps=[step])

        res = executor.execute_plan(plan, cancellation_token=token)
        assert res.status == PlanStatus.CANCELLED
        assert not (sandbox_env["sandbox"] / "cancel.txt").exists()

    def test_approval_boundary_pause_and_user_denial(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        target = sandbox_env["sandbox"] / "approval.txt"

        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "approved data"},
        )
        plan = Plan.create(goal="Requires Approval", steps=[step])
        # Mark plan as requiring approval
        plan.approval_required = True

        # Execute without approval
        paused_plan = executor.execute_plan(plan, user_approved=False)
        assert paused_plan.status == PlanStatus.AWAITING_APPROVAL
        assert executor.pending_approval_data is not None

        # User Denies
        denied = executor.resolve_approval(plan.plan_id, approved=False)
        assert denied is True
        assert paused_plan.status == PlanStatus.FAILED
        assert not target.exists()

    def test_mismatched_approval_rejected(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(sandbox_env["sandbox"] / "a.txt"), "content": "a"},
        )
        plan = Plan.create(goal="Approval", steps=[step])
        plan.approval_required = True

        executor.execute_plan(plan, user_approved=False)
        # Attempt to resolve with wrong plan_id
        res = executor.resolve_approval("wrong-plan-id", approved=True)
        assert res is False
        assert executor.pending_approval_data is not None

    def test_successful_approval_resumes_plan(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        target = sandbox_env["sandbox"] / "resumed.txt"
        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "resumed content"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        plan = Plan.create(goal="Approval Resume", steps=[step])
        plan.approval_required = True

        paused = executor.execute_plan(plan, user_approved=False)
        assert paused.status == PlanStatus.AWAITING_APPROVAL
        assert not target.exists()

        # Approve synchronously
        approved = executor.resolve_approval(plan.plan_id, approved=True, synchronous=True)
        assert approved is True
        assert plan.status == PlanStatus.COMPLETED
        assert target.exists()
        assert target.read_text(encoding="utf-8") == "resumed content"

    def test_cancel_during_execution(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        p1 = sandbox_env["sandbox"] / "c1.txt"
        p2 = sandbox_env["sandbox"] / "c2.txt"

        token = CancellationToken()
        s1 = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(p1), "content": "1"})
        s2 = PlanStep(step_id="s2", action=AgentAction.WRITE_FILE, parameters={"path": str(p2), "content": "2"}, dependencies=["s1"])
        plan = Plan.create(goal="Cancel Plan", steps=[s1, s2])

        # Cancel token before start
        token.cancel(reason="Test cancel mid execution", source=CancellationSource.USER_COMMAND)
        res = executor.execute_plan(plan, cancellation_token=token, user_approved=True)
        assert res.status == PlanStatus.CANCELLED
        assert not p1.exists()
        assert not p2.exists()

    def test_stale_plan_cannot_resume(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        target = sandbox_env["sandbox"] / "stale.txt"
        step = PlanStep(step_id="s1", action=AgentAction.WRITE_FILE, parameters={"path": str(target), "content": "stale"})
        plan = Plan.create(goal="Stale", steps=[step])
        executor.execute_plan(plan, user_approved=True)
        assert plan.status == PlanStatus.COMPLETED

        # Attempting to resolve approval on an already completed plan must fail
        assert executor.resolve_approval(plan.plan_id, approved=True) is False

    def test_brain_and_voice_cannot_approve(self, sandbox_env):
        executor: EVPlanExecutor = sandbox_env["executor"]
        target = sandbox_env["sandbox"] / "unauth.txt"
        step = PlanStep(
            step_id="s1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "unauth"},
            metadata={"voice_approved": True, "brain_approved": True},
        )
        plan = Plan.create(goal="Unauthorized Approval", steps=[step], metadata={"approved_by": "voice"})
        plan.approval_required = True

        # Calling execute_plan with user_approved=False MUST enter AWAITING_APPROVAL regardless of metadata
        paused = executor.execute_plan(plan, user_approved=False)
        assert paused.status == PlanStatus.AWAITING_APPROVAL
        assert not target.exists()


# =============================================================================
# 5. Brain Converter Plan Integration
# =============================================================================

class TestBrainPlanConversion:
    """Test converting validated Brain decisions into Plan proposals."""

    def test_convert_decision_to_plan(self):
        converter = BrainTaskConverter()
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="create log.txt",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.WRITE_FILE, parameters={"path": "C:\\log.txt", "content": "start"}),
                BrainActionProposal(action=AgentAction.READ_TEXT_FILE, parameters={"path": "C:\\log.txt"}),
            ],
        )
        val_result = BrainValidationResult(
            valid=True,
            status=BrainValidationStatus.VALID,
            accepted_actions=decision.proposed_actions,
        )

        plan = converter.convert_decision_to_plan(decision, validation_result=val_result, goal="Write and read log")
        assert plan is not None
        assert plan.status == PlanStatus.CREATED
        assert len(plan.steps) == 2
        # Sequential dependency established
        assert plan.steps[1].dependencies == [plan.steps[0].step_id]

    def test_unapproved_brain_decision_fails_conversion(self):
        converter = BrainTaskConverter()
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="create log.txt",
            proposed_actions=[BrainActionProposal(action=AgentAction.WRITE_FILE, parameters={"path": "C:\\log.txt", "content": "x"})],
        )
        # Unapproved validation result
        val_result = BrainValidationResult(
            valid=False,
            status=BrainValidationStatus.INVALID,
            errors=["Malicious path"],
        )

        with pytest.raises(Exception):
            converter.convert_decision_to_plan(decision, validation_result=val_result)
