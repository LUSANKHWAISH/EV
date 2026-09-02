import logging
import threading
from pathlib import Path
from typing import List, Optional

from core.agent import EVAgent
from core.brain_router import BrainRouter, RouteType
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
from core.risk import EVRiskEngine

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
    enforces risk and human-in-the-loop approval gating, and executes tasks in the background.
    """
    def __init__(
        self,
        event_bus: EVEventBus,
        router: Optional[BrainRouter] = None,
        risk_engine: Optional[EVRiskEngine] = None,
    ):
        self.event_bus = event_bus
        self.history_store = EVTaskHistoryStore()
        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
        )
        self._execution_lock = threading.Lock()
        self.router = router or BrainRouter()
        self.risk_engine = risk_engine or EVRiskEngine()
        self._pending_lock = threading.RLock()
        self._pending_approval: Optional[dict] = None

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

    def submit_command(self, raw_text: str) -> Optional[threading.Thread]:
        """
        Routes a raw text string through BrainRouter, evaluates risk gate, and submits task(s).
        """
        recent_tasks = None
        try:
            recent_tasks = self.history_store.list_tasks(limit=10)
        except Exception as exc:
            logger.debug("Failed to query history store for routing context: %s", exc)

        routing_result = self.router.route(
            user_input=raw_text,
            current_state=self.event_bus.current_state or EVState.IDLE,
            recent_tasks=recent_tasks,
        )

        if not routing_result.success or routing_result.route_type == RouteType.FAILURE:
            if routing_result.error and "No Brain provider manager" not in routing_result.error and "non-empty string" not in routing_result.error:
                error_msg = f"Command failed: {routing_result.error}"
            else:
                error_msg = f"Unrecognized command: {raw_text}"
            logger.warning("Command routing failed: %s (error: %s)", raw_text, routing_result.error)
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=error_msg,
            )
            return None

        if routing_result.route_type == RouteType.NO_ACTION:
            msg = routing_result.message or "No action required"
            logger.info("Brain returned informational response: %s", msg)
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=msg,
            )
            return None

        if not routing_result.tasks:
            logger.warning("Routing succeeded but produced 0 tasks")
            return None

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
                    return self.execute_tasks(tasks)
            except RuntimeError as e:
                logger.warning("Task submission rejected: %s", e)
                return None

        elif risk_result.decision == PermissionDecision.REQUIRE_APPROVAL:
            with self._pending_lock:
                self._pending_approval = {
                    "task": first_task,
                    "remaining_tasks": tasks[1:],
                    "risk_assessment": risk_result,
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

        if not approved:
            # User Denial
            logger.info("Task %s denied by user", task_id)
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
            if len(all_tasks) == 1:
                self.execute_task(pending_task)
            else:
                self.execute_tasks(all_tasks)
            return True
        except Exception as exc:
            logger.exception("Failed to execute approved task %s: %s", task_id, exc)
            self.event_bus.set_state(EVState.FAILED)
            self.event_bus.set_state(EVState.IDLE)
            return True

    def execute_task(self, task: AgentTask) -> threading.Thread:
        """
        Submit a single task for background execution.
        Returns the daemon thread handle.
        """
        if not self._execution_lock.acquire(blocking=False):
            raise RuntimeError("Agent already executing a task")

        def _run_wrapper() -> None:
            try:
                try:
                    self.event_bus.set_state(EVState.EXECUTING)
                    result = self.agent.run(task)
                    if result.status == AgentStatus.COMPLETED:
                        self.event_bus.set_state(EVState.SUCCESS)
                    else:
                        self.event_bus.set_state(EVState.FAILED)
                except Exception as e:
                    logger.exception(f"Unexpected error in agent execution for task {task.task_id}: {e}")
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
            name=f"EVAgentThread-{task.task_id}"
        )
        thread.start()
        return thread

    def execute_tasks(self, tasks: List[AgentTask]) -> threading.Thread:
        """
        Submit a list of tasks for sequential background execution.
        Returns the daemon thread handle.
        """
        if not tasks:
            raise ValueError("Cannot execute empty task list")

        if not self._execution_lock.acquire(blocking=False):
            raise RuntimeError("Agent already executing a task")

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
                                    },
                                )
                                return  # Release execution lock and await user approval

                            elif risk_result.decision != PermissionDecision.ALLOW:
                                logger.warning("Batch task %s denied by risk engine", task.task_id)
                                all_completed = False
                                break

                        result = self.agent.run(task)
                        if result.status != AgentStatus.COMPLETED:
                            all_completed = False
                            break

                    if all_completed:
                        self.event_bus.set_state(EVState.SUCCESS)
                    else:
                        self.event_bus.set_state(EVState.FAILED)
                except Exception as e:
                    logger.exception(f"Unexpected error in agent execution for tasks batch: {e}")
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
