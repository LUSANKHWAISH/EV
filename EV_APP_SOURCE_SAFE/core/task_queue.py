"""
Thread-safe, priority-ordered, bounded command queue for E.V. (Phase 6 Task 012).

Provides deterministic sequencing, strict priority ordering, monotonic FIFO
tie-breaking, and queue-local lifecycle states beneath the orchestrator.

Security & Architectural Invariants:
1. Orchestration only: Queue ordering NEVER constitutes authorization.
2. RAM-only: Queue state, sequence numbers, and tokens are ephemeral and NEVER persisted to SQLite.
3. Strict Priority: CONTROL (0) > APPROVAL_RESUME (1) > USER_INTERACTIVE (2) > SYSTEM_REPAIR (3) > BACKGROUND (4).
4. Deterministic FIFO: Monotonic sequence counter provides deterministic tie-breaking for equal priorities.
5. Fail Closed: Bounded capacity (max 50 items). Queue overflow raises QueueFullError and fails closed.
6. Cooperative Cancellation: Queued items cancel without rollback; active items cancel via Task 010 token with LIFO rollback.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Callable, List, Optional, Tuple, Union

from core.cancellation import CancellationSource, CancellationToken
from core.models import AgentTask
from core.transaction import CompoundTransaction

logger = logging.getLogger("ev.task_queue")


class TaskPriority(IntEnum):
    """
    Deterministic priority levels for queued E.V. commands.
    Lower numerical value indicates higher scheduling priority.
    """
    CONTROL = 0
    APPROVAL_RESUME = 1
    USER_INTERACTIVE = 2
    SYSTEM_REPAIR = 3
    BACKGROUND = 4


class QueueItemStatus(str, Enum):
    """
    Queue-local lifecycle states for queued commands.
    These states remain local to the queue runtime and do not alter global EVState.
    """
    QUEUED = "QUEUED"
    DISPATCHING = "DISPATCHING"
    EXECUTING = "EXECUTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class QueueFullError(Exception):
    """Raised when an enqueue operation exceeds maximum queue capacity."""

    def __init__(self, message: str = "Task queue capacity limit reached (max 50 items)") -> None:
        super().__init__(message)
        self.message = message


@dataclass
class QueuedCommand:
    """
    Represents a single queued command/task batch within EVTaskQueue.
    Contains immutable identity, scheduling metadata, and execution synchronization primitives.
    """
    command_id: str
    command_text: str
    tasks: List[AgentTask]
    priority: TaskPriority
    sequence: int
    created_at: float = field(default_factory=time.monotonic)
    source: str = "USER_COMMAND"
    transaction: Optional[CompoundTransaction] = None
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)
    status: QueueItemStatus = QueueItemStatus.QUEUED
    completion_event: threading.Event = field(default_factory=threading.Event)
    result: Optional[Any] = None
    error: Optional[str] = None
    status_reason: Optional[str] = None

    def order_key(self) -> Tuple[int, int]:
        """
        Deterministic ordering key: (priority, sequence).
        Ensures strict priority sorting with strict FIFO tie-breaking.
        """
        prio = self.priority.value if isinstance(self.priority, TaskPriority) else int(self.priority)
        return (prio, self.sequence)

    def is_terminal(self) -> bool:
        """Check if command reached a terminal lifecycle state."""
        return self.status in (
            QueueItemStatus.COMPLETED,
            QueueItemStatus.CANCELLED,
            QueueItemStatus.FAILED,
        )


class TaskExecutionThread(threading.Thread):
    """
    A lightweight, daemon thread handle wrapping a QueuedCommand.
    Provides standard threading.Thread semantics (is_alive(), join(timeout))
    for backward compatibility with existing tests and callers expecting a Thread handle.
    """

    def __init__(self, queued_command: QueuedCommand, name: Optional[str] = None) -> None:
        super().__init__(name=name or f"TaskExec-{queued_command.command_id}", daemon=True)
        self.queued_command = queued_command
        self.result: Optional[Any] = None
        self.start()

    def run(self) -> None:
        self.queued_command.completion_event.wait()
        self.result = self.queued_command.result


class EVTaskQueue:
    """
    Thread-safe, bounded, priority-ordered command queue for E.V.
    Guarantees strict priority ordering, FIFO tie-breaking, bounded capacity,
    and safe cooperative cancellation.
    """
    DEFAULT_CAPACITY: int = 50

    def __init__(self, max_capacity: int = DEFAULT_CAPACITY) -> None:
        self._max_capacity: int = max(1, max_capacity)
        self._lock: threading.RLock = threading.RLock()
        self._condition: threading.Condition = threading.Condition(self._lock)
        self._items: List[QueuedCommand] = []
        self._sequence_counter: int = 0
        self._is_shutdown: bool = False

    @property
    def condition(self) -> threading.Condition:
        """Access the synchronization condition variable."""
        return self._condition

    @property
    def max_capacity(self) -> int:
        """Maximum queue capacity."""
        return self._max_capacity

    def enqueue(
        self,
        command_text: str,
        tasks: List[AgentTask],
        priority: Union[TaskPriority, int] = TaskPriority.USER_INTERACTIVE,
        source: str = "USER_COMMAND",
        transaction: Optional[CompoundTransaction] = None,
        cancellation_token: Optional[CancellationToken] = None,
        command_id: Optional[str] = None,
    ) -> QueuedCommand:
        """
        Enqueue a command for sequential priority execution.

        Args:
            command_text: Original raw or cleaned command text.
            tasks: List of AgentTasks associated with the command.
            priority: Scheduling priority level (0 = highest).
            source: Origin of command (USER_COMMAND, GUI, BRAIN, etc.).
            transaction: Optional CompoundTransaction for multi-step execution.
            cancellation_token: Optional cooperative CancellationToken.
            command_id: Optional unique identifier.

        Returns:
            QueuedCommand instance placed in the queue.

        Raises:
            QueueFullError: If queue is at capacity (fails closed).
            RuntimeError: If queue is shut down.
        """
        if not tasks:
            raise ValueError("Cannot enqueue command with empty task list")

        # Normalize priority safely; external input cannot inject arbitrary out-of-range priority
        parsed_priority = TaskPriority.USER_INTERACTIVE
        if isinstance(priority, TaskPriority):
            parsed_priority = priority
        elif isinstance(priority, int):
            try:
                parsed_priority = TaskPriority(priority)
            except ValueError:
                parsed_priority = TaskPriority.USER_INTERACTIVE

        with self._lock:
            if self._is_shutdown:
                raise RuntimeError("Cannot enqueue into shutdown EVTaskQueue")

            if len(self._items) >= self._max_capacity:
                logger.warning(
                    "EVTaskQueue full (%d/%d items). Rejecting command '%s'",
                    len(self._items),
                    self._max_capacity,
                    command_text[:50],
                )
                raise QueueFullError(
                    f"Task queue capacity limit reached (max {self._max_capacity} items)"
                )

            self._sequence_counter += 1
            cid = command_id or f"cmd-{uuid.uuid4().hex[:10]}"
            token = cancellation_token or CancellationToken()

            item = QueuedCommand(
                command_id=cid,
                command_text=str(command_text),
                tasks=list(tasks),
                priority=parsed_priority,
                sequence=self._sequence_counter,
                source=str(source),
                transaction=transaction,
                cancellation_token=token,
                status=QueueItemStatus.QUEUED,
            )

            # Insert keeping self._items sorted by order_key: (priority, sequence)
            inserted = False
            for idx, existing in enumerate(self._items):
                if item.order_key() < existing.order_key():
                    self._items.insert(idx, item)
                    inserted = True
                    break
            if not inserted:
                self._items.append(item)

            logger.info(
                "Enqueued command %s [priority=%s, seq=%d, queue_len=%d]: '%s'",
                cid,
                parsed_priority.name,
                item.sequence,
                len(self._items),
                command_text[:50],
            )
            self._condition.notify()
            return item

    def pop(self) -> Optional[QueuedCommand]:
        """
        Pop and return the highest priority (and lowest sequence) queued command.
        Returns None if queue is empty.
        """
        with self._lock:
            if not self._items:
                return None
            item = self._items.pop(0)
            item.status = QueueItemStatus.DISPATCHING
            return item

    def peek(self) -> Optional[QueuedCommand]:
        """
        Inspect the highest priority queued command without removing it.
        """
        with self._lock:
            if not self._items:
                return None
            return self._items[0]

    def get(self, command_id: str) -> Optional[QueuedCommand]:
        """Retrieve a queued command by command_id without removing it."""
        with self._lock:
            for item in self._items:
                if item.command_id == command_id:
                    return item
            return None

    def cancel(
        self,
        command_id: str,
        reason: str = "Command cancelled",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Cancel a specific waiting command by command_id.
        Removes the item from the queue, marks it CANCELLED, triggers its token,
        and unblocks any completion waiters. Does NOT perform rollback because
        queued items have not begun execution.

        Returns:
            True if matching item was found in queue and cancelled; False otherwise.
        """
        with self._lock:
            for idx, item in enumerate(self._items):
                if item.command_id == command_id:
                    self._items.pop(idx)
                    item.status = QueueItemStatus.CANCELLED
                    item.status_reason = str(reason)
                    item.cancellation_token.cancel(reason=reason, source=source)
                    item.completion_event.set()
                    logger.info("Cancelled queued command %s: %s", command_id, reason)
                    return True
            return False

    def cancel_all(
        self,
        reason: str = "All queued commands cancelled",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> int:
        """
        Cancel and purge all waiting commands currently in the queue.
        Marks all items CANCELLED and unblocks all completion waiters.

        Returns:
            Number of queued items cancelled.
        """
        with self._lock:
            count = len(self._items)
            for item in self._items:
                item.status = QueueItemStatus.CANCELLED
                item.status_reason = str(reason)
                item.cancellation_token.cancel(reason=reason, source=source)
                item.completion_event.set()
            self._items.clear()
            if count > 0:
                logger.info("Purged and cancelled %d queued commands: %s", count, reason)
            return count

    def shutdown(
        self,
        reason: str = "Queue shutdown",
        source: Union[CancellationSource, str] = CancellationSource.SYSTEM_SHUTDOWN,
    ) -> int:
        """
        Shut down the queue, cancel all waiting items, and wake all waiting workers.
        """
        with self._lock:
            self._is_shutdown = True
            cancelled = self.cancel_all(reason=reason, source=source)
            self._condition.notify_all()
            return cancelled

    def size(self) -> int:
        """Current number of items in the queue."""
        with self._lock:
            return len(self._items)

    def is_empty(self) -> bool:
        """Check if queue is empty."""
        with self._lock:
            return len(self._items) == 0

    def is_full(self) -> bool:
        """Check if queue has reached maximum capacity."""
        with self._lock:
            return len(self._items) >= self._max_capacity

    def is_shutdown(self) -> bool:
        """Check if queue has been shut down."""
        with self._lock:
            return self._is_shutdown

    def list_items(self) -> List[QueuedCommand]:
        """Return a shallow copy of current queued items in priority order."""
        with self._lock:
            return list(self._items)

    def clear(self) -> List[QueuedCommand]:
        """Clear all items and return them without cancelling."""
        with self._lock:
            cleared = list(self._items)
            self._items.clear()
            return cleared
