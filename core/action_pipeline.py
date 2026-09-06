"""
Canonical End-to-End Intelligent Action Pipeline for E.V.

This module unifies:
  Input (Voice, GUI, CLI, or System Condition)
  -> EVOrchestrator
  -> Deterministic Resolver / Brain Router
  -> Context & Memory (strictly non-authorizing)
  -> Diagnosis / Recovery Proposals (proposal-only)
  -> Canonical Plan Representation
  -> Fail-Closed PlanValidator
  -> Authoritative EVRiskEngine
  -> Human Approval Gate (when mutating)
  -> CompoundTransaction (LIFO rollback)
  -> EVAgent (sandbox enforced)
  -> EVVerifier (observation-only)
  -> Sanitized EventBus & Task History
  -> HUD State & TTS Audio Feedback

CANONICAL INVARIANTS:
1. VOICE != AUTHORITY
2. BRAIN != AUTHORITY
3. MEMORY != AUTHORITY
4. AWARENESS != AUTHORITY
5. DIAGNOSIS != AUTHORITY
6. RECOVERY PROPOSAL != AUTHORITY
7. EXECUTION SUCCEEDED + VERIFICATION FAILED = OVERALL FAILURE (triggers LIFO rollback).
8. UNKNOWN MUTATION = ZERO BLIND RETRY.
9. CANCELLED = ZERO AUTOMATIC CONTINUATION.
10. ZERO GOD MODE, ZERO AUTONOMOUS REPAIR LOOPS, ZERO PARALLEL EXECUTION.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Union
import uuid

from core.agent import EVAgent
from core.brain_router import BrainRouter, RouteType
from core.cancellation import CancellationSource, CancellationToken
from core.conversation import EVConversationContextStore
from core.events import EVEvent, EVEventBus
from core.history import EVTaskHistoryStore
from core.memory import EVConversationMemoryStore
from core.models import (
    ActionCategory,
    ActionReversibility,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    Diagnosis,
    EVEventSeverity,
    EVEventType,
    EVState,
    ExecutionResult,
    ExecutionStatus,
    PermissionDecision,
    RecoveryOption,
    RecoveryStage,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
    VerificationResult,
    VerificationStatus,
    VerificationType,
    sanitize_metadata,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.plan_executor import EVPlanExecutor
from core.plan_validator import PlanValidationResult, PlanValidator
from core.recovery import EVDiagnosticEngine, EVRecoveryPlanner
from core.resolver import CommandResolver
from core.risk import EVRiskEngine
from core.risk_intelligence import map_action_to_category
from core.verifier import EVVerifier

logger = logging.getLogger("ev.action_pipeline")


@dataclass
class ActionPipelineContext:
    """
    Contextual information for an action pipeline execution request.
    Strictly isolated: context data NEVER confers execution authority or approval.
    """
    pipeline_id: str
    source: str = "CLI"  # "VOICE", "GUI", "CLI", "SYSTEM_RECOVERY"
    command_text: Optional[str] = None
    cancellation_token: Optional[CancellationToken] = None
    correlation_id: Optional[str] = None
    diagnosis_id: Optional[str] = None
    condition_id: Optional[str] = None
    user_approved: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metadata = sanitize_metadata(self.metadata)


@dataclass
class ActionPipelineResult:
    """
    Authoritative, structured outcome of an end-to-end pipeline execution.
    Preserves execution status, verification status, overall outcome,
    error details, and rollback records without collapsing them into a simple boolean.
    """
    pipeline_id: str
    command_text: str
    status: PlanStatus
    execution_status: Optional[ExecutionStatus]
    verification_status: Optional[VerificationStatus]
    overall_success: bool
    requires_approval: bool
    approved: Optional[bool]
    rolled_back: bool
    plan: Optional[Plan] = None
    error: Optional[str] = None
    diagnosis: Optional[Diagnosis] = None
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Produce JSON-serializable dictionary representation."""
        return {
            "pipeline_id": self.pipeline_id,
            "command_text": self.command_text,
            "status": self.status.value,
            "execution_status": self.execution_status.value if self.execution_status else None,
            "verification_status": self.verification_status.value if self.verification_status else None,
            "overall_success": self.overall_success,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "rolled_back": self.rolled_back,
            "plan_id": self.plan.plan_id if self.plan else None,
            "error": self.error,
            "diagnosis_id": self.diagnosis.diagnosis_id if self.diagnosis else None,
            "duration_seconds": self.duration_seconds,
            "metadata": copy.deepcopy(self.metadata),
        }


class EVActionPipeline:
    """
    Canonical coordinator for the E.V. intelligent action pipeline.

    Coordinates the cooperative interaction of existing subsystems:
      EVOrchestrator -> Resolver/Brain -> Plan -> PlanValidator ->
      EVRiskEngine -> Approval -> CompoundTransaction -> EVAgent -> EVVerifier -> Telemetry

    Contains ZERO independent execution mechanisms; all executions are routed through
    authoritative existing components.
    """

    def __init__(
        self,
        event_bus: Optional[EVEventBus] = None,
        risk_engine: Optional[EVRiskEngine] = None,
        plan_validator: Optional[PlanValidator] = None,
        plan_executor: Optional[EVPlanExecutor] = None,
        router: Optional[BrainRouter] = None,
        resolver: Optional[CommandResolver] = None,
        agent: Optional[EVAgent] = None,
        verifier: Optional[EVVerifier] = None,
        history_store: Optional[EVTaskHistoryStore] = None,
        memory_store: Optional[EVConversationMemoryStore] = None,
        diagnostic_engine: Optional[EVDiagnosticEngine] = None,
        recovery_planner: Optional[EVRecoveryPlanner] = None,
        tts_manager: Optional[Any] = None,
    ) -> None:
        self.event_bus: EVEventBus = event_bus or EVEventBus()
        self.risk_engine: EVRiskEngine = risk_engine or EVRiskEngine()
        self.plan_validator: PlanValidator = plan_validator or PlanValidator(self.risk_engine)
        self.agent: EVAgent = agent or EVAgent(event_bus=self.event_bus)
        self.verifier: EVVerifier = verifier or getattr(self.agent, "verifier", EVVerifier())
        self.history_store: EVTaskHistoryStore = history_store or EVTaskHistoryStore()
        self.plan_executor: EVPlanExecutor = plan_executor or EVPlanExecutor(
            agent=self.agent,
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
            history_store=self.history_store,
            verifier=self.verifier,
        )
        self.router: BrainRouter = router or BrainRouter()
        self._resolver: CommandResolver = resolver or CommandResolver()
        self.memory_store: Optional[EVConversationMemoryStore] = memory_store
        self.diagnostic_engine: EVDiagnosticEngine = diagnostic_engine or EVDiagnosticEngine(event_bus=self.event_bus)
        self.recovery_planner: EVRecoveryPlanner = recovery_planner or EVRecoveryPlanner(
            risk_engine=self.risk_engine,
            plan_validator=self.plan_validator,
            event_bus=self.event_bus,
        )
        self.tts_manager = tts_manager

        self._lock = threading.RLock()
        self._pending_pipeline_contexts: Dict[str, ActionPipelineContext] = {}
        self._pending_pipeline_plans: Dict[str, Plan] = {}

    # -------------------------------------------------------------------------
    # 1. Main Pipeline Entry Point: User Request
    # -------------------------------------------------------------------------
    def execute_request(
        self,
        raw_text: str,
        context: Optional[ActionPipelineContext] = None,
    ) -> ActionPipelineResult:
        """
        Execute an end-to-end request from user text (Voice, GUI, or CLI).

        1. Rejects empty text.
        2. Routes request via CommandResolver (deterministic) or BrainRouter.
        3. Converts tasks to canonical Plan.
        4. Validates Plan via fail-closed PlanValidator.
        5. Assesses authoritative risk via EVRiskEngine.
        6. Enforces Human Approval for mutating plans.
        7. Executes inside CompoundTransaction with LIFO rollback on failure.
        8. Verifies result via EVVerifier.
        9. Publishes sanitized events and returns structured ActionPipelineResult.
        """
        start_time = time.monotonic()
        p_id = context.pipeline_id if context else f"pipe-{uuid.uuid4().hex[:8]}"
        ctx = context or ActionPipelineContext(pipeline_id=p_id, command_text=raw_text)
        token = ctx.cancellation_token or CancellationToken()

        cleaned_text = (raw_text or "").strip()
        if not cleaned_text:
            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text="",
                status=PlanStatus.FAILED,
                execution_status=ExecutionStatus.FAILED,
                verification_status=VerificationStatus.FAILED,
                overall_success=False,
                requires_approval=False,
                approved=None,
                rolled_back=False,
                error="Empty command input",
                duration_seconds=0.0,
            )

        # 0. Pre-Flight Cancellation Check
        if token.is_cancelled():
            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=cleaned_text,
                status=PlanStatus.CANCELLED,
                execution_status=ExecutionStatus.CANCELLED,
                verification_status=VerificationStatus.NOT_APPLICABLE,
                overall_success=False,
                requires_approval=False,
                approved=None,
                rolled_back=False,
                error=f"Cancelled before start: {token.state.reason}",
                duration_seconds=time.monotonic() - start_time,
            )

        self._publish_status(f"Resolving command: {cleaned_text[:50]}", correlation_id=p_id)

        # 1. Resolution: Fast Path (CommandResolver) then Slow Path (BrainRouter)
        tasks: List[AgentTask] = []
        is_deterministic = False
        try:
            resolved = self._resolver.resolve(cleaned_text)
            if isinstance(resolved, AgentTask):
                tasks = [resolved]
            elif isinstance(resolved, (list, tuple)):
                tasks = list(resolved)
            is_deterministic = True
        except ValueError:
            tasks = []

        if not tasks:
            # Route through Brain
            routing_res = self.router.route(
                user_input=cleaned_text,
                current_state=self.event_bus.current_state or EVState.IDLE,
            )
            if not routing_res.success or routing_res.route_type in (RouteType.FAILURE, RouteType.NO_ACTION):
                err = routing_res.error or routing_res.message or "Unrecognized command"
                self._speak_if_enabled(err)
                return ActionPipelineResult(
                    pipeline_id=p_id,
                    command_text=cleaned_text,
                    status=PlanStatus.FAILED,
                    execution_status=ExecutionStatus.FAILED,
                    verification_status=VerificationStatus.NOT_APPLICABLE,
                    overall_success=False,
                    requires_approval=False,
                    approved=None,
                    rolled_back=False,
                    error=err,
                    duration_seconds=time.monotonic() - start_time,
                )
            tasks = routing_res.tasks or []

        if not tasks:
            err = f"No executable tasks could be resolved from: {cleaned_text}"
            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=cleaned_text,
                status=PlanStatus.FAILED,
                execution_status=ExecutionStatus.FAILED,
                verification_status=VerificationStatus.NOT_APPLICABLE,
                overall_success=False,
                requires_approval=False,
                approved=None,
                rolled_back=False,
                error=err,
                duration_seconds=time.monotonic() - start_time,
            )

        # 2. Construct Canonical Plan
        plan = self._build_plan_from_tasks(
            tasks=tasks,
            goal=cleaned_text,
            pipeline_id=p_id,
            source=ctx.source,
            correlation_id=ctx.correlation_id,
        )

        # 3. Validate Plan & Authoritative Risk Assessment via PlanValidator
        val_result = self.plan_validator.validate(plan)
        if not val_result.is_valid:
            err = f"Plan validation rejected: {'; '.join(val_result.errors)}"
            logger.warning(err)
            self._speak_if_enabled(err)
            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=cleaned_text,
                status=PlanStatus.REJECTED,
                execution_status=ExecutionStatus.FAILED,
                verification_status=VerificationStatus.FAILED,
                overall_success=False,
                requires_approval=val_result.approval_required,
                approved=None,
                rolled_back=False,
                plan=plan,
                error=err,
                duration_seconds=time.monotonic() - start_time,
            )

        validated_plan = val_result.validated_plan or plan

        # 4. Human Approval Gate
        requires_approval = validated_plan.approval_required
        if requires_approval and not ctx.user_approved:
            with self._lock:
                self._pending_pipeline_contexts[validated_plan.plan_id] = ctx
                self._pending_pipeline_plans[validated_plan.plan_id] = validated_plan

            # Register pending approval with authoritative plan_executor
            self.plan_executor.execute_plan(
                plan=validated_plan,
                validation_result=val_result,
                cancellation_token=ctx.cancellation_token,
                user_approved=False,
            )

            msg = f"Approval required for {validated_plan.goal} (risk={validated_plan.risk_level.value})"
            self._publish_approval_required(validated_plan, msg)
            self._speak_if_enabled(msg, priority="APPROVAL")

            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=cleaned_text,
                status=PlanStatus.AWAITING_APPROVAL,
                execution_status=ExecutionStatus.ACCEPTED,
                verification_status=VerificationStatus.NOT_APPLICABLE,
                overall_success=False,
                requires_approval=True,
                approved=None,
                rolled_back=False,
                plan=validated_plan,
                error=None,
                duration_seconds=time.monotonic() - start_time,
            )

        # 5. Execute Plan via Authoritative PlanExecutor
        return self._execute_validated_plan(
            plan=validated_plan,
            validation_result=val_result,
            context=ctx,
            start_time=start_time,
        )

    # -------------------------------------------------------------------------
    # 2. Approval Resolution Gate
    # -------------------------------------------------------------------------
    def resolve_approval(
        self,
        plan_id: str,
        approved: bool,
    ) -> ActionPipelineResult:
        """
        Resolve a pending human approval for a plan.

        If approved: resumes and executes the plan.
        If denied: marks the plan FAILED, guarantees ZERO mutation occurred,
                   emits denial events, and speaks notification.
        """
        start_time = time.monotonic()
        with self._lock:
            ctx = self._pending_pipeline_contexts.pop(plan_id, None)
            saved_plan = self._pending_pipeline_plans.pop(plan_id, None)

        p_id = ctx.pipeline_id if ctx else f"pipe-{plan_id}"
        cmd_text = ctx.command_text if ctx else (saved_plan.goal if saved_plan else f"Plan {plan_id}")

        if not approved:
            logger.info("Plan '%s' denied by human authorization", plan_id)
            self.plan_executor.resolve_approval(plan_id, approved=False)
            self.event_bus.set_state(EVState.IDLE, reason="Approval denied by user")
            msg = f"Action authorization denied: {cmd_text}"
            self._publish_status(msg, correlation_id=p_id)
            self._speak_if_enabled("Action cancelled: authorization denied.")

            if saved_plan:
                saved_plan.status = PlanStatus.FAILED
                saved_plan.error = "Authorization denied by human user"

            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=cmd_text,
                status=PlanStatus.FAILED,
                execution_status=ExecutionStatus.CANCELLED,
                verification_status=VerificationStatus.NOT_APPLICABLE,
                overall_success=False,
                requires_approval=True,
                approved=False,
                rolled_back=False,
                plan=saved_plan,
                error="Authorization denied by human user",
                duration_seconds=time.monotonic() - start_time,
            )

        # Approved: resume execution
        if ctx:
            ctx.user_approved = True

        res = self.plan_executor.resolve_approval(plan_id, approved=True, synchronous=True)
        active_plan = self.plan_executor.active_plan or saved_plan

        return self._build_result_from_plan(
            plan=active_plan,
            pipeline_id=p_id,
            command_text=cmd_text,
            requires_approval=True,
            approved=True,
            start_time=start_time,
        )

    # -------------------------------------------------------------------------
    # 3. Recovery Proposal Integration Flow
    # -------------------------------------------------------------------------
    def execute_recovery_proposal(
        self,
        recovery_option: RecoveryOption,
        context: Optional[ActionPipelineContext] = None,
    ) -> ActionPipelineResult:
        """
        Execute a structured RecoveryOption generated by EVRecoveryPlanner.

        SECURITY INVARIANTS:
        1. Diagnosis and Recovery are PROPOSAL-ONLY with ZERO direct execution authority.
        2. Mutating options strictly require human approval.
        3. Converts option to canonical Plan, validates, and routes through pipeline.
        """
        start_time = time.monotonic()
        p_id = context.pipeline_id if context else f"pipe-rec-{uuid.uuid4().hex[:8]}"
        ctx = context or ActionPipelineContext(
            pipeline_id=p_id,
            source="SYSTEM_RECOVERY",
            command_text=recovery_option.description,
            diagnosis_id=recovery_option.diagnosis_id,
        )

        # 1. Convert Option to Plan via Recovery Planner
        plan = self.recovery_planner.create_recovery_plan(recovery_option)

        # 2. Check Approval Gate for Mutating Recovery
        if plan.approval_required and not ctx.user_approved:
            with self._lock:
                self._pending_pipeline_contexts[plan.plan_id] = ctx
                self._pending_pipeline_plans[plan.plan_id] = plan

            val_result = self.plan_validator.validate(plan)
            self.plan_executor.execute_plan(
                plan=plan,
                validation_result=val_result,
                cancellation_token=ctx.cancellation_token,
                user_approved=False,
            )

            msg = f"Recovery action requires approval: {plan.goal}"
            self._publish_approval_required(plan, msg)
            self._speak_if_enabled(msg, priority="APPROVAL")

            return ActionPipelineResult(
                pipeline_id=p_id,
                command_text=recovery_option.description,
                status=PlanStatus.AWAITING_APPROVAL,
                execution_status=ExecutionStatus.ACCEPTED,
                verification_status=VerificationStatus.NOT_APPLICABLE,
                overall_success=False,
                requires_approval=True,
                approved=None,
                rolled_back=False,
                plan=plan,
                duration_seconds=time.monotonic() - start_time,
            )

        # 3. Execute Validated Plan
        val_result = self.plan_validator.validate(plan)
        return self._execute_validated_plan(
            plan=plan,
            validation_result=val_result,
            context=ctx,
            start_time=start_time,
        )

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------
    def _execute_validated_plan(
        self,
        plan: Plan,
        validation_result: PlanValidationResult,
        context: ActionPipelineContext,
        start_time: float,
    ) -> ActionPipelineResult:
        """Execute a validated plan and construct an authoritative ActionPipelineResult."""
        executed_plan = self.plan_executor.execute_plan(
            plan=plan,
            validation_result=validation_result,
            cancellation_token=context.cancellation_token,
            user_approved=context.user_approved,
        )

        return self._build_result_from_plan(
            plan=executed_plan,
            pipeline_id=context.pipeline_id,
            command_text=context.command_text or executed_plan.goal,
            requires_approval=executed_plan.approval_required,
            approved=context.user_approved if executed_plan.approval_required else None,
            start_time=start_time,
        )

    def _build_result_from_plan(
        self,
        plan: Optional[Plan],
        pipeline_id: str,
        command_text: str,
        requires_approval: bool,
        approved: Optional[bool],
        start_time: float,
    ) -> ActionPipelineResult:
        """Construct a structured ActionPipelineResult from plan execution state."""
        duration = time.monotonic() - start_time
        if plan is None:
            return ActionPipelineResult(
                pipeline_id=pipeline_id,
                command_text=command_text,
                status=PlanStatus.FAILED,
                execution_status=ExecutionStatus.FAILED,
                verification_status=VerificationStatus.FAILED,
                overall_success=False,
                requires_approval=requires_approval,
                approved=approved,
                rolled_back=False,
                error="Plan execution produced no plan reference",
                duration_seconds=duration,
            )

        # Evaluate Step Results
        has_failed_step = any(s.status == StepStatus.FAILED for s in plan.steps)
        has_cancelled_step = any(s.status == StepStatus.CANCELLED for s in plan.steps)
        is_completed = (plan.status == PlanStatus.COMPLETED)
        is_cancelled = (plan.status == PlanStatus.CANCELLED) or has_cancelled_step

        # Check for LIFO rollback in metadata or status
        rolled_back = (
            plan.metadata.get("rolled_back", False)
            or plan.metadata.get("rollback_status") is not None
            or plan.status == PlanStatus.ROLLING_BACK
        )

        # Determine composite execution and verification status
        exec_status = ExecutionStatus.SUCCEEDED if is_completed else (
            ExecutionStatus.CANCELLED if is_cancelled else ExecutionStatus.FAILED
        )

        # Check verification across steps
        verif_status = VerificationStatus.NOT_APPLICABLE
        for step in plan.steps:
            if step.verification_type is not None:
                if step.error and "verification failed" in step.error.lower():
                    verif_status = VerificationStatus.FAILED
                    break
                elif step.status == StepStatus.COMPLETED:
                    verif_status = VerificationStatus.VERIFIED

        # CENTRAL RULE: Execution Succeeded + Verification Failed = OVERALL FAILURE
        overall_success = is_completed and (verif_status != VerificationStatus.FAILED) and not has_failed_step

        # Speak outcome if applicable
        if overall_success:
            self._speak_if_enabled(f"Task completed: {plan.goal}")
        elif plan.error:
            self._speak_if_enabled(f"Task failed: {plan.error}")

        return ActionPipelineResult(
            pipeline_id=pipeline_id,
            command_text=command_text,
            status=plan.status,
            execution_status=exec_status,
            verification_status=verif_status,
            overall_success=overall_success,
            requires_approval=requires_approval,
            approved=approved,
            rolled_back=rolled_back,
            plan=plan,
            error=plan.error,
            duration_seconds=duration,
            metadata=sanitize_metadata(plan.metadata),
        )

    def _build_plan_from_tasks(
        self,
        tasks: List[AgentTask],
        goal: str,
        pipeline_id: str,
        source: str,
        correlation_id: Optional[str],
    ) -> Plan:
        """Convert a list of AgentTasks into a canonical Plan."""
        p_id = f"plan-{uuid.uuid4().hex[:8]}"
        steps: List[PlanStep] = []
        prev_id: Optional[str] = None

        for idx, task in enumerate(tasks):
            sid = f"step-{uuid.uuid4().hex[:6]}"
            cat = map_action_to_category(task.action, task.parameters)
            is_mutating = (task.action not in (
                AgentAction.FIND_PROCESS,
                AgentAction.FIND_TCP_PORT,
                AgentAction.GET_FILE_INFO,
                AgentAction.LIST_DIRECTORY,
                AgentAction.READ_TEXT_FILE,
                AgentAction.FIND_FILES,
                AgentAction.SEARCH_TEXT,
                AgentAction.FIND_SERVICE,
            ))

            step = PlanStep(
                step_id=sid,
                action=task.action,
                parameters=copy.deepcopy(task.parameters),
                dependencies=[prev_id] if prev_id else [],
                verification_type=task.verification_type,
                is_compensable=is_mutating and (task.action not in (
                    AgentAction.STOP_PROCESS,
                    AgentAction.RESTART_SERVICE,
                    AgentAction.FLUSH_DNS,
                )),
                reversibility=ActionReversibility.REVERSIBLE if is_mutating else ActionReversibility.NON_REVERSIBLE,
                description=f"Step {idx + 1}: {task.action.value}",
            )
            steps.append(step)
            prev_id = sid

        is_any_mutating = any(
            s.action in (AgentAction.WRITE_FILE, AgentAction.DELETE_FILE, AgentAction.STOP_PROCESS, AgentAction.RESTART_SERVICE, AgentAction.FLUSH_DNS)
            for s in steps
        )

        return Plan(
            plan_id=p_id,
            goal=goal,
            steps=steps,
            status=PlanStatus.CREATED,
            transaction_required=is_any_mutating,
            verification_required=any(s.verification_type is not None for s in steps),
            metadata={
                "pipeline_id": pipeline_id,
                "source": source,
                "correlation_id": correlation_id,
            },
        )

    def _publish_status(self, message: str, correlation_id: Optional[str] = None) -> None:
        """Publish status event to EVEventBus."""
        try:
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="action_pipeline",
                message=message,
                correlation_id=correlation_id,
            )
        except Exception as exc:
            logger.debug("Failed to publish status event: %s", exc)

    def _publish_approval_required(self, plan: Plan, message: str) -> None:
        """Publish approval required event to EVEventBus."""
        try:
            self.event_bus.set_state(
                EVState.AWAITING_APPROVAL,
                reason=message,
                correlation_id=plan.plan_id,
            )
            self.event_bus.publish(
                event_type=EVEventType.APPROVAL_REQUIRED,
                source="action_pipeline",
                correlation_id=plan.plan_id,
                message=message,
                data={
                    "task_id": plan.plan_id,
                    "plan_id": plan.plan_id,
                    "action": plan.steps[0].action.value if plan.steps else "MUTATE",
                    "reason": message,
                    "goal": plan.goal,
                    "risk_level": plan.risk_level.value,
                    "steps_count": len(plan.steps),
                },
            )
        except Exception as exc:
            logger.debug("Failed to publish approval required event: %s", exc)

    def _speak_if_enabled(self, text: str, priority: str = "INTERACTIVE") -> None:
        """Speak text via EVTTSManager if configured."""
        if not self.tts_manager or not text:
            return
        try:
            self.tts_manager.speak(text=text, priority=priority)
        except Exception as exc:
            logger.debug("Action pipeline speech output failed: %s", exc)
