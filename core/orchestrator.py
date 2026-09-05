import logging
import threading
from pathlib import Path
from typing import List, Optional, Union

from core.agent import EVAgent
from core.brain_models import BrainDecisionType
from core.brain_router import BrainRouter, RouteType
from core.cancellation import (
    CancellationSource,
    CancellationToken,
    OperationCancelledError,
)
from core.conversation import EVConversationContextStore, PendingClarificationContext
from core.events import EVEventBus, EVEvent
from core.history import EVTaskHistoryStore
from core.memory import EVConversationMemoryStore
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
from core.task_queue import (
    EVTaskQueue,
    QueuedCommand,
    QueueFullError,
    QueueItemStatus,
    TaskExecutionThread,
    TaskPriority,
)
try:
    from core.tts import AudioPriority as _AudioPriority
    from core.tts import EVTTSManager as _EVTTSManager
    _TTS_MODULE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TTS_MODULE_AVAILABLE = False
    _AudioPriority = None  # type: ignore[assignment,misc]
    _EVTTSManager = None  # type: ignore[assignment,misc]

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
    if action == AgentAction.STOP_PROCESS:
        return ActionCategory.PROCESS_STOP
    if action == AgentAction.RESTART_SERVICE:
        return ActionCategory.SERVICE_CONFIGURATION
    if action == AgentAction.FLUSH_DNS:
        return ActionCategory.NETWORK_CONFIGURATION
    return ActionCategory.UNKNOWN


class EVOrchestrator:
    """
    Central orchestration engine for E.V.
    Coordinates command resolution, risk management, agent execution,
    and event publishing.
    """
    def __init__(
        self,
        event_bus: EVEventBus,
        router: Optional[BrainRouter] = None,
        risk_engine: Optional[EVRiskEngine] = None,
        context_store: Optional[EVConversationContextStore] = None,
        memory_store: Optional[EVConversationMemoryStore] = None,
        task_queue: Optional[EVTaskQueue] = None,
        enable_queue: bool = False,
        tts_manager=None,
    ):
        self.event_bus = event_bus
        self.history_store = EVTaskHistoryStore()
        try:
            self.memory_store = memory_store or EVConversationMemoryStore()
        except Exception as exc:
            logger.warning("Failed to initialize persistent memory store; falling back to ephemeral: %s", exc)
            self.memory_store = None

        if context_store is not None:
            self.context_store = context_store
        else:
            self.context_store = EVConversationContextStore(memory_store=self.memory_store)

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
        self._active_cancellation_token: Optional[CancellationToken] = None
        self._token_lock = threading.Lock()

        # Task 012: Command Queue runtime integration
        self.task_queue: EVTaskQueue = task_queue or EVTaskQueue()
        self.enable_queue: bool = enable_queue
        self._shutdown_event: threading.Event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        if self.enable_queue:
            self.start_queue_worker()

        # Task 013: Optional TTS / Audio Feedback subsystem
        # Default is None — E.V. operates in text-only mode when not provided.
        # TTS is output presentation only; it cannot authorize actions or alter state.
        self._tts_manager = tts_manager

    def start_queue_worker(self) -> None:
        """Start the dedicated queue worker daemon thread if not already active."""
        with self.task_queue._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._shutdown_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._queue_worker_loop,
                    name="EVQueueWorker",
                    daemon=True,
                )
                self._worker_thread.start()
                logger.info("EVOrchestrator queue worker thread started")

    def _speak_if_enabled(self, text: str, priority_name: str = "INTERACTIVE") -> None:
        """
        Speak text via the TTS subsystem if one is configured.
        Failures are isolated and never propagate to the caller.
        Does NOT set EVState — state transitions remain EVOrchestrator's domain.
        TTS is strictly output presentation; this method has no execution authority.
        """
        if self._tts_manager is None:
            return
        if not text or not text.strip():
            return
        try:
            if _TTS_MODULE_AVAILABLE and _AudioPriority is not None:
                priority = getattr(_AudioPriority, priority_name, _AudioPriority.INTERACTIVE)
            else:
                return
            self._tts_manager.speak(text=text, priority=priority)
        except Exception as exc:
            logger.debug("EVOrchestrator._speak_if_enabled: TTS speak failed: %s", exc)

    def stop_queue_worker(self, timeout: float = 5.0) -> None:
        """Stop the dedicated queue worker daemon thread."""
        self._shutdown_event.set()
        with self.task_queue.condition:
            self.task_queue.condition.notify_all()
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            logger.info("EVOrchestrator queue worker thread stopped")

    def _queue_worker_loop(self) -> None:
        """
        Dedicated queue worker loop. Sequentially consumes items from EVTaskQueue,
        pausing execution while any command is awaiting approval.
        """
        logger.info("Queue worker loop initialized")
        while not self._shutdown_event.is_set():
            item: Optional[QueuedCommand] = None
            with self.task_queue.condition:
                while not self.task_queue._items and not self._shutdown_event.is_set():
                    self.task_queue.condition.wait(timeout=0.5)

                if self._shutdown_event.is_set():
                    break

                if self.task_queue._items:
                    # Check if currently awaiting approval or if active execution is in progress
                    with self._pending_lock:
                        is_awaiting = self._pending_approval is not None

                    if is_awaiting or self._execution_lock.locked():
                        # Queue worker MUST pause execution of later queued commands
                        # while awaiting approval or while another execution is running
                        self.task_queue.condition.wait(timeout=0.1)
                        continue

                    item = self.task_queue.pop()

            if item is None:
                continue

            if item.cancellation_token.is_cancelled() or item.status == QueueItemStatus.CANCELLED:
                item.completion_event.set()
                continue

            # Execute the dequeued command outside the queue lock
            self._execute_queued_item(item)

        logger.info("Queue worker loop terminated")

    def _execute_queued_item(self, item: QueuedCommand) -> None:
        """
        Execute a dequeued command: assess risk, check approval, or run tasks.
        """
        if not item.tasks:
            item.status = QueueItemStatus.COMPLETED
            item.completion_event.set()
            return

        item.status = QueueItemStatus.EXECUTING
        self.event_bus.publish(
            event_type=EVEventType.STATUS,
            source="orchestrator",
            message=f"Processing queued command: {item.command_text[:50]}",
            data={
                "event": "TASK_DEQUEUED",
                "command_id": item.command_id,
                "queue_size": self.task_queue.size(),
            },
        )

        first_task = item.tasks[0]
        risk_result = self._assess_task_risk(first_task, user_approved=False)

        try:
            self.history_store.record_task(first_task)
            self.history_store.attach_risk_assessment(first_task.task_id, risk_result)
        except Exception as exc:
            logger.debug("Failed to record task or attach risk assessment: %s", exc)

        if risk_result.decision == PermissionDecision.ALLOW:
            tx = item.transaction or CompoundTransaction(tasks=item.tasks)
            try:
                thread = None
                while not self._shutdown_event.is_set():
                    try:
                        thread = self.execute_tasks(
                            item.tasks,
                            transaction=tx,
                            cancellation_token=item.cancellation_token,
                        )
                        break
                    except RuntimeError as re:
                        if "Agent already executing a task" in str(re):
                            with self.task_queue.condition:
                                self.task_queue.condition.wait(timeout=0.1)
                            continue
                        raise

                if thread is not None:
                    thread.join()
                if item.cancellation_token.is_cancelled():
                    item.status = QueueItemStatus.CANCELLED
                elif tx.status == TransactionStatus.COMMITTED:
                    item.status = QueueItemStatus.COMPLETED
                else:
                    item.status = QueueItemStatus.FAILED
            except Exception as exc:
                logger.exception("Error executing queued command %s: %s", item.command_id, exc)
                item.status = QueueItemStatus.FAILED
                item.error = str(exc)
            finally:
                item.completion_event.set()

        elif risk_result.decision == PermissionDecision.REQUIRE_APPROVAL:
            tx = item.transaction or CompoundTransaction(tasks=item.tasks)
            item.status = QueueItemStatus.AWAITING_APPROVAL
            with self._pending_lock:
                self._pending_approval = {
                    "task": first_task,
                    "remaining_tasks": item.tasks[1:],
                    "risk_assessment": risk_result,
                    "transaction": tx,
                    "queued_command": item,
                }
            logger.info(
                "Queued task %s requires approval (risk=%s, reason=%s)",
                first_task.task_id,
                risk_result.risk_level.value,
                risk_result.reason,
            )
            self.event_bus.set_state(
                EVState.AWAITING_APPROVAL,
                reason=f"Approval required: {risk_result.reason}",
                correlation_id=first_task.task_id,
                data={
                    "transaction_id": tx.transaction_id,
                    "task_id": first_task.task_id,
                    "command_id": item.command_id,
                },
            )
            self.event_bus.publish(
                event_type=EVEventType.APPROVAL_REQUIRED,
                source="orchestrator",
                correlation_id=first_task.task_id,
                message=f"Approval required for {first_task.action.value}: {risk_result.reason}",
                data={
                    "task_id": first_task.task_id,
                    "command_id": item.command_id,
                    "action": first_task.action.value,
                    "risk_level": risk_result.risk_level.value,
                    "reason": risk_result.reason,
                    "parameters": first_task.parameters,
                    "transaction_id": tx.transaction_id,
                },
            )
            # Item completion_event will be signaled when approval is resolved or cancelled

        else:
            logger.warning("Queued task %s denied by risk engine: %s", first_task.task_id, risk_result.reason)
            item.status = QueueItemStatus.FAILED
            item.error = f"Security policy denial: {risk_result.reason}"
            item.completion_event.set()
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                correlation_id=first_task.task_id,
                message=f"Action denied by security policy: {risk_result.reason}",
                data={"task_id": first_task.task_id, "command_id": item.command_id, "reason": risk_result.reason},
            )

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

    def submit_command(
        self,
        raw_text: str,
        queue: Optional[bool] = None,
        priority: TaskPriority = TaskPriority.USER_INTERACTIVE,
    ) -> Optional[threading.Thread]:
        """
        Routes a raw text string through BrainRouter, evaluates risk gate, and submits task(s).
        Integrates with EVConversationContextStore for multi-turn clarification.
        Supports deterministic queueing when enabled, or direct execution.
        Deterministically intercepts STOP/CANCEL/ABORT control commands without Brain/LLM routing.
        """
        if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
            return None

        cleaned_text = raw_text.strip()
        lower_text = cleaned_text.lower()

        # Step 0: Deterministically intercept STOP / CANCEL / ABORT control commands
        if lower_text in ("stop", "cancel", "abort"):
            logger.info("Control command '%s' intercepted", lower_text)

            # Task 013: Cancel any active/pending TTS speech first (presentation layer)
            if self._tts_manager is not None:
                self._tts_manager.cancel_all(reason=f"STOP command: '{lower_text}'")

            # 0. Cancel queued commands
            self.task_queue.cancel_all(
                reason=f"Queued commands cancelled via '{lower_text}' command",
                source=CancellationSource.USER_COMMAND,
            )

            # 1. Cancel pending approval if present
            with self._pending_lock:
                has_pending = self._pending_approval is not None
            if has_pending:
                self.cancel_pending_approval(
                    reason=f"Pending approval cancelled via '{lower_text}' command",
                    source=CancellationSource.USER_COMMAND,
                )
                self.context_store.add_turn(
                    user_message=cleaned_text,
                    assistant_message="Pending approval cancelled.",
                )
                return None

            # 2. Cancel active background task if running
            with self._token_lock:
                active_token = self._active_cancellation_token
            if active_token is not None and not active_token.is_cancelled():
                self.cancel_active_task(
                    reason=f"Active execution cancelled via '{lower_text}' command",
                    source=CancellationSource.USER_COMMAND,
                )
                self.context_store.add_turn(
                    user_message=cleaned_text,
                    assistant_message="Execution cancellation requested.",
                )
                return None

            # 3. Cancel active pending clarification if present
            if self.context_store.has_pending_clarification():
                self.context_store.clear_pending_clarification()
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

            # 4. Harmless deterministic feedback when nothing active
            msg = "No active execution or pending approval to cancel."
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=msg,
            )
            self.context_store.add_turn(
                user_message=cleaned_text,
                assistant_message=msg,
            )
            return None

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
                # Task 013: Speak clarification prompt so user can respond hands-free
                self._speak_if_enabled(clarification_msg, priority_name="INTERACTIVE")
                return None

            logger.info("Brain returned informational response: %s", msg)
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=msg,
            )
            self.context_store.add_turn(user_message=cleaned_text, assistant_message=msg)
            # Task 013: Speak the informational response
            self._speak_if_enabled(msg, priority_name="INTERACTIVE")
            return None

        if not routing_result.tasks:
            logger.warning("Routing succeeded but produced 0 tasks")
            return None

        use_queue = queue if queue is not None else self.enable_queue
        if use_queue:
            self.start_queue_worker()
            try:
                queued_cmd = self.task_queue.enqueue(
                    command_text=cleaned_text,
                    tasks=routing_result.tasks,
                    priority=priority,
                    source="USER_COMMAND",
                )
            except QueueFullError as qfe:
                logger.warning("Queue overflow: %s", qfe)
                self.event_bus.publish(
                    event_type=EVEventType.STATUS,
                    source="orchestrator",
                    message=f"Command queue full: {qfe}",
                    data={"event": "QUEUE_FULL", "command": cleaned_text},
                )
                self.context_store.add_turn(
                    user_message=cleaned_text,
                    assistant_message="Command rejected: task queue is at capacity (50 items).",
                )
                return None

            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=f"Command queued: {cleaned_text[:50]}",
                data={
                    "event": "TASK_QUEUED",
                    "command_id": queued_cmd.command_id,
                    "queue_size": self.task_queue.size(),
                    "priority": queued_cmd.priority.name,
                },
            )
            self.context_store.add_turn(
                user_message=cleaned_text,
                assistant_message=f"Queued {len(routing_result.tasks)} task(s) [priority={queued_cmd.priority.name}]",
            )
            return TaskExecutionThread(queued_cmd)

        self.context_store.add_turn(user_message=cleaned_text, assistant_message=f"Dispatched {len(routing_result.tasks)} task(s)")
        return self._dispatch_tasks(routing_result.tasks)

    def queue_command(
        self,
        raw_text: str,
        priority: TaskPriority = TaskPriority.USER_INTERACTIVE,
    ) -> Optional[threading.Thread]:
        """
        Submit a command specifically through the task queue runtime.
        Returns a TaskExecutionThread handle for synchronization.
        """
        return self.submit_command(raw_text, queue=True, priority=priority)

    def cancel_queued_command(
        self,
        command_id: str,
        reason: str = "Queued command cancelled",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Cancel a specific waiting command in the queue by command_id.
        """
        return self.task_queue.cancel(command_id, reason=reason, source=source)

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
            self._speak_if_enabled(
                f"Approval required for {first_task.action.value}: {risk_result.reason}",
                priority_name="APPROVAL",
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
            self._speak_if_enabled(
                f"Action denied by security policy: {risk_result.reason}",
                priority_name="INTERACTIVE",
            )
            return None

    def cancel_active_task(
        self,
        reason: str = "Execution cancelled by user",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Request cooperative cancellation of the currently active background task or transaction.
        Does not forcefully kill threads; signals the CancellationToken for safe cooperative exit.
        """
        with self._token_lock:
            token = self._active_cancellation_token

        if token is None or token.is_cancelled():
            logger.debug("cancel_active_task called but no active cancellable token found")
            return False

        cancelled = token.cancel(reason=reason, source=source)
        if cancelled:
            self.event_bus.publish(
                event_type=EVEventType.STATUS,
                source="orchestrator",
                message=f"Cancellation requested: {reason}",
                data={"reason": reason, "source": str(source)},
            )
        return cancelled

    def cancel_pending_approval(
        self,
        reason: str = "Approval cancelled by user",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Atomically cancel any pending approval request and return orchestrator to IDLE state.
        Invalidates the pending task and prevents stale approvals from being accepted later.
        """
        with self._pending_lock:
            if self._pending_approval is None:
                return False
            approval_data = self._pending_approval
            self._pending_approval = None

        pending_task = approval_data.get("task")
        tx = approval_data.get("transaction")
        queued_cmd = approval_data.get("queued_command")
        task_id = pending_task.task_id if pending_task else "unknown"

        if queued_cmd is not None:
            queued_cmd.status = QueueItemStatus.CANCELLED
            queued_cmd.status_reason = reason
            queued_cmd.cancellation_token.cancel(reason=reason, source=source)
            queued_cmd.completion_event.set()

        with self.task_queue.condition:
            self.task_queue.condition.notify_all()

        if tx:
            tx.rollback(
                backup_manager=self.agent.backup_manager,
                failed_step_index=0,
                failure_reason=reason,
            )

        if pending_task:
            try:
                self.history_store.record_task(pending_task)
                self.history_store.record_run(
                    pending_task,
                    AgentRunResult(
                        task_id=task_id,
                        status=AgentStatus.FAILED,
                        error=reason,
                    ),
                )
            except Exception as exc:
                logger.debug("Failed to record cancellation in history: %s", exc)

        self.event_bus.publish(
            event_type=EVEventType.STATUS,
            source="orchestrator",
            correlation_id=task_id,
            message=f"Task {task_id} approval cancelled: {reason}",
            data={"task_id": task_id, "approved": False, "reason": reason, "source": str(source)},
        )
        self.event_bus.set_state(EVState.IDLE)
        return True

    def cancel_all(
        self,
        reason: str = "Operation cancelled by user",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Cancel pending approval, active background execution, and all queued tasks.
        """
        cancelled_pending = self.cancel_pending_approval(reason=reason, source=source)
        cancelled_active = self.cancel_active_task(reason=reason, source=source)
        cancelled_queued = self.task_queue.cancel_all(reason=reason, source=source) > 0
        return cancelled_pending or cancelled_active or cancelled_queued

    def shutdown(self, timeout: float = 5.0) -> None:
        """
        Clean deterministic shutdown of orchestrator, active tasks, queue worker, and TTS.
        """
        self._shutdown_event.set()
        self.cancel_all(reason="System shutdown", source=CancellationSource.SYSTEM_SHUTDOWN)
        self.task_queue.shutdown(reason="System shutdown", source=CancellationSource.SYSTEM_SHUTDOWN)
        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
        # Task 013: Shut down TTS subsystem cleanly (after task queue is drained)
        if self._tts_manager is not None:
            try:
                self._tts_manager.shutdown(timeout=2.0)
            except Exception as exc:
                logger.warning("TTS manager shutdown raised: %s", exc)
        self.event_bus.set_state(EVState.STOPPED)

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

            # Retrieve the pending approval state
            approval_data = self._pending_approval
            remaining_tasks = approval_data.get("remaining_tasks") or []
            tx = approval_data.get("transaction")
            queued_cmd = approval_data.get("queued_command")

        if not approved:
            with self._pending_lock:
                self._pending_approval = None
            # User Denial
            logger.info("Task %s denied by user", task_id)
            if queued_cmd is not None:
                queued_cmd.status = QueueItemStatus.FAILED
                queued_cmd.error = "Execution denied by user"
                queued_cmd.completion_event.set()

            with self.task_queue.condition:
                self.task_queue.condition.notify_all()

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
            with self._pending_lock:
                self._pending_approval = None
            logger.warning(
                "Task %s was approved by user but failed secondary risk evaluation: %s",
                task_id,
                second_assessment.reason,
            )
            if queued_cmd is not None:
                queued_cmd.status = QueueItemStatus.FAILED
                queued_cmd.error = f"Secondary risk denial: {second_assessment.reason}"
                queued_cmd.completion_event.set()

            with self.task_queue.condition:
                self.task_queue.condition.notify_all()

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
            thread = self.execute_tasks(all_tasks, transaction=tx)
            with self._pending_lock:
                self._pending_approval = None
            if queued_cmd is not None:
                def _wait_and_complete():
                    thread.join()
                    if queued_cmd.cancellation_token.is_cancelled():
                        queued_cmd.status = QueueItemStatus.CANCELLED
                    elif tx and tx.status == TransactionStatus.COMMITTED:
                        queued_cmd.status = QueueItemStatus.COMPLETED
                    else:
                        queued_cmd.status = QueueItemStatus.FAILED
                    queued_cmd.completion_event.set()
                    with self.task_queue.condition:
                        self.task_queue.condition.notify_all()
                threading.Thread(target=_wait_and_complete, daemon=True).start()
            else:
                with self.task_queue.condition:
                    self.task_queue.condition.notify_all()
            return True
        except Exception as exc:
            logger.exception("Failed to execute approved task %s: %s", task_id, exc)
            if queued_cmd is not None:
                queued_cmd.status = QueueItemStatus.FAILED
                queued_cmd.error = str(exc)
                queued_cmd.completion_event.set()
            with self.task_queue.condition:
                self.task_queue.condition.notify_all()
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
        cancellation_token: Optional[CancellationToken] = None,
    ) -> threading.Thread:
        """
        Submit a single task for background execution.
        Returns the daemon thread handle.
        """
        return self.execute_tasks([task], transaction=transaction, cancellation_token=cancellation_token)

    def execute_tasks(
        self,
        tasks: List[AgentTask],
        transaction: Optional[CompoundTransaction] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> threading.Thread:
        """
        Submit a list of tasks for sequential background execution within a CompoundTransaction.
        Supports cooperative cancellation via CancellationToken.
        Returns the daemon thread handle.
        """
        if not tasks:
            raise ValueError("Cannot execute empty task list")

        if not self._execution_lock.acquire(blocking=False):
            raise RuntimeError("Agent already executing a task")

        token = cancellation_token or CancellationToken()
        with self._token_lock:
            self._active_cancellation_token = token

        tx = transaction or CompoundTransaction(tasks=tasks)
        if tx.status == TransactionStatus.PENDING:
            tx.begin()

        def _run_wrapper() -> None:
            try:
                try:
                    self.event_bus.set_state(EVState.EXECUTING)
                    all_completed = True
                    completed_summaries: List[str] = []
                    for idx, task in enumerate(tasks):
                        # 1. Check for cooperative cancellation before beginning step
                        if token.is_cancelled():
                            logger.info(
                                "Batch execution aborted before step %d due to cancellation: %s",
                                idx,
                                token.state.reason,
                            )
                            all_completed = False
                            tx.rollback(
                                backup_manager=self.agent.backup_manager,
                                failed_step_index=idx,
                                failure_reason=f"Execution cancelled: {token.state.reason}",
                            )
                            self.event_bus.publish(
                                event_type=EVEventType.STATUS,
                                source="orchestrator",
                                correlation_id=task.task_id,
                                message=f"Execution cancelled: {token.state.reason}",
                                data={"task_id": task.task_id, "step_index": idx, "reason": token.state.reason},
                            )
                            break

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
                                with self._token_lock:
                                    if self._active_cancellation_token is token:
                                        self._active_cancellation_token = None
                                logger.info("Batch paused at task %s for user approval", task.task_id)
                                self.event_bus.set_state(
                                    EVState.AWAITING_APPROVAL,
                                    reason=f"Approval required: {risk_result.reason}",
                                    correlation_id=task.task_id,
                                    data={"transaction_id": tx.transaction_id, "task_id": task.task_id},
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
                            summary = self.agent._format_result_summary(task.action, result.step.result if result.step else None)
                            if summary:
                                completed_summaries.append(summary)
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
                        if completed_summaries:
                            self._speak_if_enabled(" ".join(completed_summaries), priority_name="INTERACTIVE")
                    else:
                        self.event_bus.set_state(EVState.FAILED)
                        fail_reason = result.error if 'result' in locals() and result and result.error else "Task execution failed"
                        self._speak_if_enabled(f"Command failed: {fail_reason}", priority_name="INTERACTIVE")
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
                with self._token_lock:
                    if self._active_cancellation_token is token:
                        self._active_cancellation_token = None
                if self.event_bus.current_state != EVState.AWAITING_APPROVAL:
                    try:
                        self.event_bus.set_state(EVState.IDLE)
                    except Exception as final_e:
                        logger.error(f"Failed to set IDLE state in finally block: {final_e}")
                self._execution_lock.release()
                with self.task_queue.condition:
                    self.task_queue.condition.notify_all()

        thread = threading.Thread(
            target=_run_wrapper,
            daemon=True,
            name=f"EVAgentBatchThread-{tasks[0].task_id}"
        )
        thread.start()
        return thread
