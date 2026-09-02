import logging
import threading
from pathlib import Path
from typing import List, Optional

from core.agent import EVAgent
from core.brain_models import BrainDecisionType
from core.brain_router import BrainRouter, RouteType
from core.conversation import EVConversationContextStore, PendingClarificationContext
from core.events import EVEventBus, EVEvent
from core.history import EVTaskHistoryStore
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    EVEventType,
    EVState,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)
from core.resolver import CommandResolver
from core.risk import EVRiskEngine
from core.transaction import CompoundTransaction, TransactionStatus

logger = logging.getLogger(__name__)


def get_action_category(action: AgentAction, parameters: Optional[dict] = None) -> ActionCategory:
    """
    Deterministically map AgentAction to ActionCategory for risk evaluation.
    Current observation actions map to READ_ONLY_OBSERVATION.
    """
    if action in (
        AgentAction.FIND_PROCESS,
        AgentAction.FIND_TCP_PORT,
        AgentAction.GET_FILE_INFO,
        AgentAction.LIST_DIRECTORY,
        AgentAction.READ_TEXT_FILE,
        AgentAction.FIND_FILES,
        AgentAction.SEARCH_TEXT,
        AgentAction.FIND_SERVICE,
    ):
        return ActionCategory.READ_ONLY_OBSERVATION
    if action == AgentAction.WRITE_FILE:
        if parameters and "path" in parameters and isinstance(parameters["path"], str):
            try:
                if Path(parameters["path"]).exists():
                    return ActionCategory.FILE_MODIFY
            except Exception:
                pass
            return ActionCategory.FILE_CREATE
        return ActionCategory.FILE_MODIFY
    if action == AgentAction.DELETE_FILE:
        return ActionCategory.FILE_DELETE
    return ActionCategory.UNKNOWN


class EVOrchestrator:
    """
    Long-lived production execution owner for the E.V. agent.
    Manages the lifecycle of a single agent, coordinates intent routing,
    enforces risk and human-in-the-loop approval gating, manages multi-turn
    conversational context, and executes tasks in the background.
    """
    def __init__(
        self,
        event_bus: EVEventBus,
        router: Optional[BrainRouter] = None,
        risk_engine: Optional[EVRiskEngine] = None,
        context_store: Optional[EVConversationContextStore] = None,
    ):
        self.event_bus = event_bus
        self.history_store = EVTaskHistoryStore()
        self.context_store = context_store or EVConversationContextStore()
        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
        )
        self._execution_lock = threading.Lock()
        self.router = router or BrainRouter()
        self.risk_engine = risk_engine or EVRiskEngine()
        self._pending_lock = threading.RLock()
        self._pending_approval: Optional[dict] = None
        self._resolver = CommandResolver()

    def _assess_task_risk(self, task: AgentTask, user_approved: bool = False) -> RiskAssessmentResult:
        """
        Assess risk of an AgentTask using the authoritative EVRiskEngine.
        """
        category = get_action_category(task.action, task.parameters)
        target = None
        if task.parameters:
            target = str(
                task.parameters.get("name")
                or task.parameters.get("path")
                or task.parameters.get("port")
                or ""
            )

        # File actions in the EV runtime are backed up and reversible
        is_file_mutation = category in (
            ActionCategory.FILE_CREATE,
            ActionCategory.FILE_MODIFY,
            ActionCategory.FILE_DELETE,
            ActionCategory.FILE_RESTORE,
        )
        has_backup = is_file_mutation
        reversible = is_file_mutation

        req = RiskAssessmentRequest(
            action_category=category,
            target=target or None,
            description=f"Action {task.action.value}",
            user_approved=user_approved,
            has_backup=has_backup,
            reversible=reversible,
        )
        return self.risk_engine.assess(req)

    def _reconstruct_request(self, original_request: str, clarification_answer: str) -> str:
        """
        Deterministically combine an original request and clarification answer into a unified request.
        """
        orig = (original_request or "").strip()
        ans = (clarification_answer or "").strip()
        lower_orig = orig.lower()

        # Check common deterministic mutation/observation command templates
        candidates = []
        if "delete" in lower_orig or "remove" in lower_orig:
            candidates.append(f"delete file {ans}")

        if "write" in lower_orig or "create" in lower_orig:
            candidates.append(f"write file {ans}")
            candidates.append(f"{orig} {ans}")

        if "read" in lower_orig or "cat" in lower_orig or "show" in lower_orig:
            candidates.append(f"read file {ans}")

        if "dir" in lower_orig or "list" in lower_orig or "ls" in lower_orig:
            candidates.append(f"list dir {ans}")

        if "process" in lower_orig or "ps" in lower_orig:
            candidates.append(f"find process {ans}")

        if "service" in lower_orig:
            candidates.append(f"find service {ans}")

        if "port" in lower_orig:
            candidates.append(f"find port {ans}")

        # General raw concatenation candidate
        candidates.append(f"{orig} {ans}")

        # Test if any candidate can be deterministically resolved by fast path
        for cand in candidates:
            try:
                self._resolver.resolve(cand)
                return cand
            except ValueError:
                continue

        # Fallback to structured natural language context
        return f"{orig} (specified: {ans})"

    def submit_command(self, raw_text: str) -> Optional[threading.Thread]:
        """
        Routes a raw text string through BrainRouter, evaluates risk gate, and submits task(s).
        Integrates with EVConversationContextStore for multi-turn clarification.
        """
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return None

        cleaned_text = raw_text.strip()

        # Check for active pending clarification
        pending_clarification = self.context_store.get_pending_clarification()
        effective_text = cleaned_text

        if pending_clarification is not None:
            # 1. Check if user explicitly cancelled
            if self.context_store.is_cancellation(cleaned_text):
                self.context_store.clear_pending_clarification()
                logger.info("Pending clarification cancelled by user")
                self.event_bus.publish(
                    event_type=EVEventType.STATUS,
                    source="orchestrator",
                    message="Clarification request cancelled.",
                )
                self.context_store.add_turn(
                    user_message=cleaned_text,
                    assistant_message="Clarification request cancelled.",
                )
                return None

            # 2. Check if user provided an explicit, standalone command
            is_standalone_command = False
            try:
                self._resolver.resolve(cleaned_text)
                is_standalone_command = True
            except ValueError:
                is_standalone_command = False

            if is_standalone_command:
                logger.info("Explicit new command received; superseding pending clarification")
                self.context_store.clear_pending_clarification()
                effective_text = cleaned_text
            else:
                # 3. User supplied a clarification answer: reconstruct effective request
                effective_text = self._reconstruct_request(
                    pending_clarification.original_request,
                    cleaned_text,
                )
                logger.info(
                    "Reconstructed request from clarification: '%s' + '%s' -> '%s'",
                    pending_clarification.original_request,
                    cleaned_text,
                    effective_text,
                )
                self.context_store.clear_pending_clarification()

        recent_tasks = None
        try:
            recent_tasks = self.history_store.list_tasks(limit=10)
        except Exception as exc:
            logger.debug("Failed to query history store for routing context: %s", exc)

        routing_result = self.router.route(
            user_input=effective_text,
            current_state=self.event_bus.current_state or EVState.IDLE,
            recent_tasks=recent_tasks,
        )

        if not routing_result.success or routing_result.route_type == RouteType.FAILURE:
            if routing_result.error and "No Brain provider manager" not in routing_result.error and "non-empty string" not in routing_result.error:
                error_msg = f"Command failed: {routing_result.error}"
            else:
                error_msg = f"Unrecognized command: {effective_text}"
            logger.warning("Command routing failed: %s (error: %s)", effective_text, routing_result.error)
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=error_msg,
            )
            self.context_store.add_turn(user_message=cleaned_text, assistant_message=error_msg)
            return None

        if routing_result.route_type == RouteType.NO_ACTION:
            msg = routing_result.message or "No action required"
            # Check if Brain requested clarification
            if routing_result.decision and routing_result.decision.decision_type == BrainDecisionType.REQUEST_CLARIFICATION:
                clarification_msg = routing_result.decision.clarification_prompt or msg
                self.context_store.set_pending_clarification(
                    original_request=effective_text,
                    clarification_prompt=clarification_msg,
                )
                logger.info("Brain requested clarification: '%s' for request: '%s'", clarification_msg, effective_text)
                self.event_bus.publish(
                    event_type=EVEventType.STATUS,
                    source="orchestrator",
                    message=clarification_msg,
                    data={
                        "clarification_prompt": clarification_msg,
                        "original_request": effective_text,
                    },
                )
                self.context_store.add_turn(user_message=cleaned_text, assistant_message=clarification_msg)
                return None

            logger.info("Brain returned informational response: %s", msg)
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=msg,
            )
            self.context_store.add_turn(user_message=cleaned_text, assistant_message=msg)
            return None

        if not routing_result.tasks:
            logger.warning("Routing succeeded but produced 0 tasks")
            return None

        self.context_store.add_turn(user_message=cleaned_text, assistant_message=f"Dispatched {len(routing_result.tasks)} task(s)")
        return self._dispatch_tasks(routing_result.tasks)

    def _dispatch_tasks(self, tasks: List[AgentTask]) -> Optional[threading.Thread]:
        """
        Evaluate risk of the initial task and execute or request approval.
        """
        if not tasks:
            return None

        first_task = tasks[0]
        risk_result = self._assess_task_risk(first_task, user_approved=False)

        # Attach risk assessment to history
        try:
            self.history_store.record_task(first_task)
            self.history_store.attach_risk_assessment(first_task.task_id, risk_result)
        except Exception as exc:
            logger.debug("Failed to record task or attach risk assessment: %s", exc)

        if risk_result.decision == PermissionDecision.ALLOW:
            try:
                if len(tasks) == 1:
                    return self.execute_task(first_task)
                else:
                    tx = CompoundTransaction(tasks=tasks)
                    return self.execute_tasks(tasks, transaction=tx)
            except RuntimeError as e:
                logger.warning("Task submission rejected: %s", e)
                return None

        elif risk_result.decision == PermissionDecision.REQUIRE_APPROVAL:
            tx = CompoundTransaction(tasks=tasks)
            with self._pending_lock:
                self._pending_approval = {
                    "task": first_task,
                    "remaining_tasks": tasks[1:],
                    "risk_assessment": risk_result,
                    "transaction": tx,
                }
            logger.info(
                "Task %s requires approval (risk=%s, reason=%s)",
                first_task.task_id,
                risk_result.risk_level.value,
                risk_result.reason,
            )
            self.event_bus.set_state(
                EVState.AWAITING_APPROVAL,
                reason=f"Approval required: {risk_result.reason}",
                correlation_id=first_task.task_id,
            )
            self.event_bus.publish(
                event_type=EVEventType.APPROVAL_REQUIRED,
                source="orchestrator",
                correlation_id=first_task.task_id,
                message=f"Approval required for {first_task.action.value}: {risk_result.reason}",
                data={
                    "task_id": first_task.task_id,
                    "action": first_task.action.value,
                    "risk_level": risk_result.risk_level.value,
                    "reason": risk_result.reason,
                    "parameters": first_task.parameters,
                    "transaction_id": tx.transaction_id,
                },
            )
            return None

        else:
            # DENY or INDETERMINATE
            logger.warning(
                "Task %s denied by risk engine: %s",
                first_task.task_id,
                risk_result.reason,
            )
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                correlation_id=first_task.task_id,
                message=f"Action denied by security policy: {risk_result.reason}",
                data={
                    "task_id": first_task.task_id,
                    "action": first_task.action.value,
                    "risk_level": risk_result.risk_level.value,
                    "reason": risk_result.reason,
                },
            )
            return None

    def resolve_approval(self, task_id: str, approved: bool) -> bool:
        """
        Resolve a pending approval request for a task.

        Args:
            task_id: Unique task identifier matching the pending approval.
            approved: True if authorized by user, False if denied.

        Returns:
            True if pending approval matched and was processed, False otherwise.
        """
        with self._pending_lock:
            if self._pending_approval is None:
                logger.warning("resolve_approval called but no task is pending approval")
                return False

            pending_task = self._pending_approval.get("task")
            if pending_task is None or pending_task.task_id != task_id:
                logger.warning(
                    "resolve_approval task_id mismatch: expected '%s', got '%s'",
                    pending_task.task_id if pending_task else "None",
                    task_id,
                )
                return False

            # Atomically consume the pending approval state
            approval_data = self._pending_approval
            self._pending_approval = None
            remaining_tasks = approval_data.get("remaining_tasks") or []
            tx = approval_data.get("transaction")

        if not approved:
            # User Denial
            logger.info("Task %s denied by user", task_id)
            if tx:
                tx.rollback(
                    backup_manager=self.agent.backup_manager,
                    failed_step_index=0,
                    failure_reason="Execution denied by user",
                )
            try:
                self.history_store.record_task(pending_task)
                self.history_store.record_run(
                    pending_task,
                    AgentRunResult(
                        task_id=task_id,
                        status=AgentStatus.FAILED,
                        error="Execution denied by user",
                    ),
                )
            except Exception as exc:
                logger.debug("Failed to record denial in history: %s", exc)

            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                correlation_id=task_id,
                message=f"Task {task_id} authorization denied by user.",
                data={"task_id": task_id, "approved": False},
            )
            self.event_bus.set_state(EVState.IDLE)
            return True

        # User Approval: Re-assess risk with user_approved=True
        second_assessment = self._assess_task_risk(pending_task, user_approved=True)
        try:
            self.history_store.attach_risk_assessment(task_id, second_assessment)
        except Exception as exc:
            logger.debug("Failed to attach second risk assessment to history: %s", exc)

        if second_assessment.decision != PermissionDecision.ALLOW:
            logger.warning(
                "Task %s was approved by user but failed secondary risk evaluation: %s",
                task_id,
                second_assessment.reason,
            )
            if tx:
                tx.rollback(
                    backup_manager=self.agent.backup_manager,
                    failed_step_index=0,
                    failure_reason=f"Secondary risk denial: {second_assessment.reason}",
                )
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                correlation_id=task_id,
                message=f"Action denied by security policy: {second_assessment.reason}",
                data={"task_id": task_id, "reason": second_assessment.reason},
            )
            self.event_bus.set_state(EVState.FAILED)
            self.event_bus.set_state(EVState.IDLE)
            return True

        # Authorized: Execute approved task (and any remaining batch tasks)
        all_tasks = [pending_task] + remaining_tasks
        try:
            self.execute_tasks(all_tasks, transaction=tx)
            return True
        except Exception as exc:
            logger.exception("Failed to execute approved task %s: %s", task_id, exc)
            if tx:
                tx.rollback(
                    backup_manager=self.agent.backup_manager,
                    failed_step_index=0,
                    failure_reason=str(exc),
                )
            self.event_bus.set_state(EVState.FAILED)
            self.event_bus.set_state(EVState.IDLE)
            return True

    def execute_task(
        self,
        task: AgentTask,
        transaction: Optional[CompoundTransaction] = None,
    ) -> threading.Thread:
        """
        Submit a single task for background execution.
        Returns the daemon thread handle.
        """
        return self.execute_tasks([task], transaction=transaction)

    def execute_tasks(
        self,
        tasks: List[AgentTask],
        transaction: Optional[CompoundTransaction] = None,
    ) -> threading.Thread:
        """
        Submit a list of tasks for sequential background execution within a CompoundTransaction.
        Returns the daemon thread handle.
        """
        if not tasks:
            raise ValueError("Cannot execute empty task list")

        if not self._execution_lock.acquire(blocking=False):
            raise RuntimeError("Agent already executing a task")

        tx = transaction or CompoundTransaction(tasks=tasks)
        if tx.status == TransactionStatus.PENDING:
            tx.begin()

        def _run_wrapper() -> None:
            try:
                try:
                    self.event_bus.set_state(EVState.EXECUTING)
                    all_completed = True
                    for idx, task in enumerate(tasks):
                        # Gating check for subsequent tasks in batch
                        if idx > 0:
                            risk_result = self._assess_task_risk(task, user_approved=False)
                            try:
                                self.history_store.record_task(task)
                                self.history_store.attach_risk_assessment(task.task_id, risk_result)
                            except Exception as exc:
                                logger.debug("Failed to record batch task risk: %s", exc)

                            if risk_result.decision == PermissionDecision.REQUIRE_APPROVAL:
                                with self._pending_lock:
                                    self._pending_approval = {
                                        "task": task,
                                        "remaining_tasks": tasks[idx + 1:],
                                        "risk_assessment": risk_result,
                                        "transaction": tx,
                                    }
                                logger.info("Batch paused at task %s for user approval", task.task_id)
                                self.event_bus.set_state(
                                    EVState.AWAITING_APPROVAL,
                                    reason=f"Approval required: {risk_result.reason}",
                                    correlation_id=task.task_id,
                                )
                                self.event_bus.publish(
                                    event_type=EVEventType.APPROVAL_REQUIRED,
                                    source="orchestrator",
                                    correlation_id=task.task_id,
                                    message=f"Approval required for {task.action.value}: {risk_result.reason}",
                                    data={
                                        "task_id": task.task_id,
                                        "action": task.action.value,
                                        "risk_level": risk_result.risk_level.value,
                                        "reason": risk_result.reason,
                                        "parameters": task.parameters,
                                        "transaction_id": tx.transaction_id,
                                    },
                                )
                                return  # Release execution lock and await user approval

                            elif risk_result.decision != PermissionDecision.ALLOW:
                                logger.warning("Batch task %s denied by risk engine", task.task_id)
                                all_completed = False
                                tx.rollback(
                                    backup_manager=self.agent.backup_manager,
                                    failed_step_index=idx,
                                    failure_reason=f"Risk denial: {risk_result.reason}",
                                )
                                break

                        result = self.agent.run(task)
                        if result.status == AgentStatus.COMPLETED:
                            mutation_info = self.agent.get_task_mutation(task.task_id)
                            if mutation_info:
                                tx.record_mutation_step(
                                    step_index=idx,
                                    task=task,
                                    target_path=mutation_info["target_path"],
                                    target_existed_before=mutation_info["target_existed_before"],
                                    backup_path=mutation_info.get("backup_path"),
                                    original_sha256=mutation_info.get("original_sha256"),
                                )
                        else:
                            all_completed = False
                            tx.rollback(
                                backup_manager=self.agent.backup_manager,
                                failed_step_index=idx,
                                failure_reason=result.error or "Task execution failed",
                            )
                            break

                    if all_completed:
                        tx.commit()
                        self.event_bus.set_state(EVState.SUCCESS)
                    else:
                        self.event_bus.set_state(EVState.FAILED)
                except Exception as e:
                    logger.exception(f"Unexpected error in agent execution for tasks batch: {e}")
                    tx.rollback(
                        backup_manager=self.agent.backup_manager,
                        failed_step_index=idx if 'idx' in locals() else None,
                        failure_reason=str(e),
                    )
                    try:
                        self.event_bus.set_state(EVState.FAILED)
                    except Exception as nested_e:
                        logger.error(f"Failed to set FAILED state during exception handling: {nested_e}")
            finally:
                if self.event_bus.current_state != EVState.AWAITING_APPROVAL:
                    try:
                        self.event_bus.set_state(EVState.IDLE)
                    except Exception as final_e:
                        logger.error(f"Failed to set IDLE state in finally block: {final_e}")
                self._execution_lock.release()

        thread = threading.Thread(
            target=_run_wrapper,
            daemon=True,
            name=f"EVAgentBatchThread-{tasks[0].task_id}"
        )
        thread.start()
        return thread
