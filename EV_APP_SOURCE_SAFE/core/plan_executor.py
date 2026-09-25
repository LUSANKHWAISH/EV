"""
Deterministic Plan Execution Coordinator for E.V. (Task 015).

This module coordinates the safe, sequential execution of validated plans within
an authoritative CompoundTransaction, enforcing human-in-the-loop approval gates,
LIFO rollback upon failure, explicit verification boundaries, and cooperative cancellation.

Security & Architectural Invariants:
1. Canonical Authority Chain:
   Plan -> PlanValidator -> EVRiskEngine -> Approval (when required) -> CompoundTransaction
   -> EVAgent -> EVVerifier -> Telemetry / History.
2. Zero Authority Expansion: This executor only runs actions permitted by EVRiskEngine
   and approved by the user. It contains zero autonomous approval or GOD MODE bypasses.
3. Verification Gating: A command that executes but fails verification fails closed and
   triggers LIFO rollback. Success is never falsely reported on verification failure.
4. LIFO Rollback: Completed mutations are compensated in strict reverse execution order.
   Non-reversible actions report COMPENSATION_NOT_AVAILABLE and mark rollback failed.
5. Cooperative Cancellation: Obeys CancellationToken at every phase boundary.
"""
from __future__ import annotations

import copy
from datetime import datetime
import logging
import threading
import time
from typing import Any, Dict, List, Optional

from core.agent import EVAgent
from core.backup import EVBackupManager
from core.cancellation import CancellationToken, CancellationSource
from core.events import EVEvent, EVEventBus
from core.history import EVTaskHistoryStore
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    EVEventSeverity,
    EVEventType,
    EVState,
    ExecutionStatus,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskLevel,
    VerificationStatus,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_validator import PlanValidationResult, PlanValidator
from core.risk import EVRiskEngine
from core.risk_intelligence import map_action_to_category
from core.transaction import (
    ActionReversibility,
    CompensationStatus,
    CompoundTransaction,
    TransactionStatus,
)
from core.verifier import EVVerifier

logger = logging.getLogger("ev.plan_executor")


class EVPlanExecutor:
    """
    Coordinates execution of validated Plans across the canonical E.V. pipeline.
    """

    def __init__(
        self,
        agent: Optional[EVAgent] = None,
        event_bus: Optional[EVEventBus] = None,
        risk_engine: Optional[EVRiskEngine] = None,
        backup_manager: Optional[EVBackupManager] = None,
        history_store: Optional[EVTaskHistoryStore] = None,
        verifier: Optional[EVVerifier] = None,
    ) -> None:
        self.agent: EVAgent = agent or EVAgent()
        self.event_bus: Optional[EVEventBus] = event_bus
        self.risk_engine: EVRiskEngine = risk_engine or EVRiskEngine()
        self.backup_manager: EVBackupManager = backup_manager or self.agent.backup_manager
        self.history_store: Optional[EVTaskHistoryStore] = history_store or getattr(self.agent, "_history_store", None)
        self.verifier: EVVerifier = verifier or EVVerifier()

        self._lock = threading.RLock()
        self._active_plan: Optional[Plan] = None
        self._active_transaction: Optional[CompoundTransaction] = None
        self._active_token: Optional[CancellationToken] = None
        self._pending_approval: Optional[Dict[str, Any]] = None

    @property
    def active_plan(self) -> Optional[Plan]:
        """Return the currently executing or pending plan."""
        with self._lock:
            return self._active_plan

    @property
    def pending_approval_data(self) -> Optional[Dict[str, Any]]:
        """Return pending approval state if awaiting human authorization."""
        with self._lock:
            if not self._pending_approval:
                return None
            plan = self._pending_approval.get("plan")
            val_res = self._pending_approval.get("validation_result")
            return {
                "plan_id": plan.plan_id if plan else None,
                "goal": plan.goal if plan else None,
                "plan": plan,
                "validation_result": val_res,
                "approval_required": plan.approval_required if plan else True,
            }

    # -------------------------------------------------------------------------
    # Execution Entry Points
    # -------------------------------------------------------------------------

    def execute_plan(
        self,
        plan: Plan,
        validation_result: Optional[PlanValidationResult] = None,
        cancellation_token: Optional[CancellationToken] = None,
        user_approved: bool = False,
    ) -> Plan:
        """
        Execute a validated Plan synchronously on the calling thread.

        Args:
            plan: The Plan to execute.
            validation_result: Optional pre-computed PlanValidationResult.
            cancellation_token: Optional cooperative CancellationToken.
            user_approved: True if already authorized through human approval.

        Returns:
            The Plan object with updated status, step results, and timestamps.
        """
        token = cancellation_token or CancellationToken()

        # 1. Validation Gate
        if validation_result is None or not validation_result.is_valid:
            validator = PlanValidator(risk_engine=self.risk_engine)
            validation_result = validator.validate(plan)

        if not validation_result.is_valid:
            plan.status = PlanStatus.REJECTED
            plan.error = f"Validation failed: {'; '.join(validation_result.errors)}"
            self._publish_event(
                EVEventType.PLAN_FAILED,
                correlation_id=plan.plan_id,
                message=plan.error,
                severity=EVEventSeverity.ERROR,
                data=plan.to_dict(),
            )
            return plan

        execution_plan = validation_result.validated_plan or plan
        topo_order = validation_result.topological_order

        with self._lock:
            self._active_plan = execution_plan
            self._active_token = token

        # 2. Pre-Execution Cancellation Check
        if token.is_cancelled():
            execution_plan.status = PlanStatus.CANCELLED
            execution_plan.error = f"Cancelled before start: {token.state.reason}"
            self._publish_event(
                EVEventType.PLAN_CANCELLED,
                correlation_id=execution_plan.plan_id,
                message=execution_plan.error,
                data=execution_plan.to_dict(),
            )
            return execution_plan

        # 3. Approval Gate
        if execution_plan.approval_required and not user_approved:
            with self._lock:
                execution_plan.status = PlanStatus.AWAITING_APPROVAL
                self._pending_approval = {
                    "plan": execution_plan,
                    "validation_result": validation_result,
                    "cancellation_token": token,
                }

            logger.info("Plan '%s' paused for human approval (risk=%s)", execution_plan.plan_id, execution_plan.risk_level.value)
            if self.event_bus is not None:
                self.event_bus.set_state(
                    EVState.AWAITING_APPROVAL,
                    reason=f"Approval required for plan: {execution_plan.goal}",
                    correlation_id=execution_plan.plan_id,
                    data={"plan_id": execution_plan.plan_id, "risk_level": execution_plan.risk_level.value},
                )
                self.event_bus.publish(
                    event_type=EVEventType.APPROVAL_REQUIRED,
                    source="plan_executor",
                    correlation_id=execution_plan.plan_id,
                    message=f"Approval required for plan: {execution_plan.goal}",
                    data={
                        "plan_id": execution_plan.plan_id,
                        "goal": execution_plan.goal,
                        "risk_level": execution_plan.risk_level.value,
                        "steps": [s.to_dict() for s in execution_plan.steps],
                    },
                )
            return execution_plan

        # 4. Begin Execution Pipeline
        return self._run_execution_loop(execution_plan, topo_order, token)

    def resolve_approval(self, plan_id: str, approved: bool, synchronous: bool = False) -> bool:
        """
        Resolve a pending approval for a plan.

        Args:
            plan_id: The plan identifier matching pending approval.
            approved: True if authorized by user, False if denied.
            synchronous: If True, executes the resumed plan on the calling thread.

        Returns:
            True if matching pending approval was resolved, False otherwise.
        """
        with self._lock:
            if self._pending_approval is None:
                logger.warning("resolve_approval called but no plan is awaiting approval")
                return False

            pending_plan: Plan = self._pending_approval["plan"]
            if pending_plan.plan_id != plan_id:
                logger.warning(
                    "resolve_approval plan_id mismatch: expected '%s', got '%s'",
                    pending_plan.plan_id,
                    plan_id,
                )
                return False

            approval_data = self._pending_approval
            self._pending_approval = None

        if not approved:
            logger.info("Plan '%s' denied by human user", plan_id)
            pending_plan.status = PlanStatus.FAILED
            pending_plan.error = "Plan execution authorization denied by user"
            if self.event_bus is not None:
                self.event_bus.publish(
                    event_type=EVEventType.STATUS,
                    source="plan_executor",
                    correlation_id=plan_id,
                    message=f"Plan {plan_id} denied by user",
                    data={"plan_id": plan_id, "approved": False},
                )
                self.event_bus.set_state(EVState.IDLE)
            return True

        # User Approved: Resume execution
        logger.info("Plan '%s' approved by human user; resuming execution", plan_id)
        token = approval_data["cancellation_token"]
        validation_result = approval_data["validation_result"]

        if synchronous:
            self._run_execution_loop(pending_plan, validation_result.topological_order, token)
        else:
            thread = threading.Thread(
                target=self._run_execution_loop,
                args=(pending_plan, validation_result.topological_order, token),
                name=f"EVPlanExecutionThread-{plan_id}",
                daemon=True,
            )
            thread.start()
        return True

    def cancel_active_plan(self, reason: str = "Plan execution cancelled by user") -> bool:
        """
        Cooperatively cancel the currently active plan.
        """
        with self._lock:
            token = self._active_token
            plan = self._active_plan

        if token is None or token.is_cancelled():
            return False

        cancelled = token.cancel(reason=reason, source=CancellationSource.USER_COMMAND)
        if cancelled and plan:
            logger.info("Plan '%s' cancelled: %s", plan.plan_id, reason)
        return cancelled

    # -------------------------------------------------------------------------
    # Core Execution & Rollback Loop
    # -------------------------------------------------------------------------

    def _run_execution_loop(
        self, plan: Plan, topo_order: List[str], token: CancellationToken
    ) -> Plan:
        """Sequential execution across topologically ordered steps."""
        plan.status = PlanStatus.EXECUTING
        plan.started_at = plan.started_at or datetime.now()
        step_map = {s.step_id: s for s in plan.steps}

        # Build AgentTask list in topological order for transaction
        ordered_tasks = [step_map[sid].to_agent_task() for sid in topo_order]
        tx = CompoundTransaction(tasks=ordered_tasks, transaction_id=f"tx-{plan.plan_id}")

        with self._lock:
            self._active_transaction = tx

        tx.begin()

        if self.event_bus is not None:
            self.event_bus.set_state(EVState.EXECUTING)
            self._publish_event(
                EVEventType.PLAN_STARTED,
                correlation_id=plan.plan_id,
                message=f"Started executing plan: {plan.goal}",
                data=plan.to_dict(),
            )

        all_steps_succeeded = True
        failed_step_id: Optional[str] = None
        failure_reason: Optional[str] = None

        for idx, sid in enumerate(topo_order):
            step = step_map[sid]

            # 1. Cooperative Cancellation Check
            if token.is_cancelled():
                logger.info("Plan '%s' cancelled before step '%s': %s", plan.plan_id, sid, token.state.reason)
                all_steps_succeeded = False
                failed_step_id = sid
                failure_reason = f"Cancelled by user: {token.state.reason}"
                step.status = StepStatus.CANCELLED
                step.error = failure_reason

                # Mark remaining steps as SKIPPED
                for remaining_sid in topo_order[idx + 1:]:
                    step_map[remaining_sid].status = StepStatus.SKIPPED
                break

            # 2. Step Execution
            step.status = StepStatus.RUNNING
            step.started_at = datetime.now()
            task = step.to_agent_task()

            logger.info("Plan '%s' executing step %d/%d: '%s' (%s)", plan.plan_id, idx + 1, len(topo_order), sid, step.action.value)

            run_result: AgentRunResult = self.agent.run(task, cancellation_token=token)

            # 3. Verification & Execution Boundary Check
            step_verified = True
            verification_err = None

            if run_result.execution:
                step.metadata["execution_status"] = run_result.execution.status.value
                step.metadata["retry_allowed"] = run_result.execution.retry_allowed
                step.metadata["action_type"] = run_result.execution.action_type
            if run_result.verification:
                step.metadata["verification_status"] = run_result.verification.status.value

            # Evaluate execution & verification outcomes
            if token.is_cancelled() or (run_result.execution and run_result.execution.status == ExecutionStatus.CANCELLED):
                step.status = StepStatus.CANCELLED
                step_verified = False
                verification_err = f"Cancelled: {token.state.reason if token.is_cancelled() else run_result.error or 'Step cancelled'}"
            elif run_result.execution and run_result.execution.status == ExecutionStatus.UNKNOWN:
                step_verified = False
                verification_err = f"Execution outcome UNKNOWN: {run_result.execution.error or run_result.error or 'ambiguous outcome; blind retry prohibited'}"
                logger.warning("Step '%s' produced UNKNOWN execution status; halting plan without retry", sid)
            elif run_result.status == AgentStatus.COMPLETED:
                step.status = StepStatus.VERIFYING
                # Check explicit verification result
                if run_result.verification:
                    if run_result.verification.status not in (VerificationStatus.VERIFIED, VerificationStatus.NOT_APPLICABLE):
                        step_verified = False
                        verification_err = f"Verification failed: {run_result.verification.reason}"
                elif step.verification_type is not None:
                    # EVAgent run() already runs verification if task.verification_type is set.
                    # Double-check through task history or run result
                    if run_result.step and run_result.step.result is not None:
                        if not run_result.step.success:
                            step_verified = False
                            verification_err = run_result.step.error or "Verification check failed"
            else:
                step_verified = False
                verification_err = run_result.error or "Step execution failed"

            step.finished_at = datetime.now()
            step.duration_seconds = (step.finished_at - step.started_at).total_seconds()

            if run_result.status == AgentStatus.COMPLETED and step_verified:
                step.status = StepStatus.COMPLETED
                step.result = run_result.step.result if run_result.step else None

                # Record mutation in transaction if mutating
                mutation_info = self.agent.get_task_mutation(step.step_id)
                if mutation_info:
                    tx.record_mutation_step(
                        step_index=idx,
                        task=task,
                        target_path=mutation_info.get("target_path"),
                        target_existed_before=mutation_info.get("target_existed_before", False),
                        backup_path=mutation_info.get("backup_path"),
                        original_sha256=mutation_info.get("original_sha256"),
                        is_compensable=mutation_info.get("is_compensable", True),
                    )
            else:
                # Step failed or verification failed or execution unknown
                all_steps_succeeded = False
                failed_step_id = sid
                failure_reason = verification_err or run_result.error or "Step execution failed"
                if step.status != StepStatus.CANCELLED:
                    step.status = StepStatus.FAILED
                step.error = failure_reason

                logger.warning("Plan '%s' failed at step '%s': %s", plan.plan_id, sid, failure_reason)

                # Mark remaining steps as SKIPPED
                for remaining_sid in topo_order[idx + 1:]:
                    step_map[remaining_sid].status = StepStatus.SKIPPED
                break

        # 4. Transaction Resolution & LIFO Rollback
        plan.finished_at = datetime.now()

        if all_steps_succeeded:
            tx.commit()
            plan.status = PlanStatus.COMPLETED
            logger.info("Plan '%s' COMPLETED successfully (%d steps)", plan.plan_id, len(topo_order))
            if self.event_bus is not None:
                self.event_bus.set_state(EVState.SUCCESS)
                self._publish_event(
                    EVEventType.PLAN_COMPLETED,
                    correlation_id=plan.plan_id,
                    message=f"Plan completed successfully: {plan.goal}",
                    data=plan.to_dict(),
                )
                self.event_bus.set_state(EVState.IDLE)
        else:
            # Failure or cancellation -> trigger LIFO rollback
            plan.status = PlanStatus.CANCELLED if token.is_cancelled() else PlanStatus.FAILED
            plan.error = failure_reason

            logger.warning(
                "Plan '%s' %s; initiating LIFO transaction rollback",
                plan.plan_id,
                plan.status.value,
            )

            rollback_clean = tx.rollback(
                backup_manager=self.backup_manager,
                failed_step_index=topo_order.index(failed_step_id) if failed_step_id in topo_order else 0,
                failure_reason=failure_reason,
            )

            plan.metadata["rolled_back"] = True
            plan.metadata["rollback_clean"] = rollback_clean
            plan.metadata["transaction_status"] = tx.status.value

            if not rollback_clean:
                plan.error = f"{failure_reason} (WARNING: Rollback encountered uncompensated or non-reversible steps)"

            if self.event_bus is not None:
                self.event_bus.set_state(EVState.FAILED)
                event_type = EVEventType.PLAN_CANCELLED if token.is_cancelled() else EVEventType.PLAN_FAILED
                self._publish_event(
                    event_type,
                    correlation_id=plan.plan_id,
                    message=plan.error,
                    severity=EVEventSeverity.ERROR,
                    data=plan.to_dict(),
                )
                self.event_bus.set_state(EVState.IDLE)

        with self._lock:
            if self._active_plan is plan:
                self._active_plan = None
                self._active_transaction = None
                self._active_token = None

        return plan

    def _publish_event(
        self,
        event_type: EVEventType,
        correlation_id: str,
        message: Optional[str] = None,
        severity: EVEventSeverity = EVEventSeverity.INFO,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Publish plan events to EVEventBus if attached."""
        if self.event_bus is None:
            return
        try:
            self.event_bus.publish(
                event_type=event_type,
                source="plan_executor",
                correlation_id=correlation_id,
                message=message,
                severity=severity,
                data=data,
            )
        except Exception as exc:
            logger.debug("Failed to publish plan event: %s", exc)
