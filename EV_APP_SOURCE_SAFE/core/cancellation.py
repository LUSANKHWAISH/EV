"""
Thread-safe cooperative cancellation contract for E.V. (Phase 5 Task 010).

Provides non-blocking, deterministic cancellation tokens, cancellation states,
and safe callback execution without thread killing or unsafe OS interruption.

Security & Architectural Invariants:
1. Pure in-memory cooperative coordination: zero subprocess, zero OS calls, zero disk I/O.
2. Idempotent: multiple cancel() calls do not trigger duplicate cancellation events.
3. Deadlock-free: registered callbacks are executed outside internal synchronization locks.
4. Non-authoritative: cancellation is a control signal and never authorizes or bypasses security policy.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Union

logger = logging.getLogger("ev.cancellation")


class CancellationSource(str, Enum):
    """Source that initiated the cancellation request."""
    USER_COMMAND = "USER_COMMAND"
    GUI_BUTTON = "GUI_BUTTON"
    TIMEOUT = "TIMEOUT"
    SUPERSEDED = "SUPERSEDED"
    SYSTEM_SHUTDOWN = "SYSTEM_SHUTDOWN"


class OperationCancelledError(Exception):
    """Exception raised when an operation is aborted via a CancellationToken."""

    def __init__(
        self,
        message: str = "Operation was cancelled",
        source: Optional[CancellationSource] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.source = source


@dataclass(frozen=True)
class CancellationState:
    """Immutable snapshot of a cancellation token's state."""
    cancellation_requested: bool = False
    timestamp: Optional[float] = None
    reason: Optional[str] = None
    source: Optional[CancellationSource] = None


class CancellationToken:
    """
    Thread-safe, cooperative cancellation token.

    Allows execution loops, long-running batch operations, and transactions to
    periodically check if cancellation has been requested, and register callbacks
    that execute immediately when cancellation occurs.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_cancelled = False
        self._timestamp: Optional[float] = None
        self._reason: Optional[str] = None
        self._source: Optional[CancellationSource] = None
        self._callbacks: List[Callable[[], None]] = []

    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        with self._lock:
            return self._is_cancelled

    @property
    def state(self) -> CancellationState:
        """Return an immutable snapshot of current cancellation state."""
        with self._lock:
            return CancellationState(
                cancellation_requested=self._is_cancelled,
                timestamp=self._timestamp,
                reason=self._reason,
                source=self._source,
            )

    def cancel(
        self,
        reason: str = "Operation cancelled",
        source: Union[CancellationSource, str] = CancellationSource.USER_COMMAND,
    ) -> bool:
        """
        Request cancellation of the associated operation.

        Args:
            reason: Human-readable explanation for cancellation.
            source: Origin of the cancellation request.

        Returns:
            True if this call transitioned the token to cancelled state;
            False if the token was already cancelled (idempotent).
        """
        parsed_source: CancellationSource = CancellationSource.USER_COMMAND
        if isinstance(source, CancellationSource):
            parsed_source = source
        elif isinstance(source, str):
            try:
                parsed_source = CancellationSource(source.upper())
            except (ValueError, KeyError):
                parsed_source = CancellationSource.USER_COMMAND

        callbacks_to_run: List[Callable[[], None]] = []

        with self._lock:
            if self._is_cancelled:
                return False

            self._is_cancelled = True
            self._timestamp = time.monotonic()
            self._reason = str(reason) if reason else "Operation cancelled"
            self._source = parsed_source
            callbacks_to_run = list(self._callbacks)
            self._callbacks.clear()

        # Execute callbacks outside the lock to prevent deadlocks
        for cb in callbacks_to_run:
            try:
                cb()
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Error in CancellationToken callback: %s", exc)

        logger.info("CancellationToken triggered: reason='%s', source=%s", self._reason, self._source.value)
        return True

    def register_callback(self, callback: Callable[[], None]) -> bool:
        """
        Register a callback to be invoked when cancellation is requested.

        If the token is already cancelled, the callback is executed immediately
        outside the lock.

        Returns:
            True if callback was registered for future execution;
            False if token was already cancelled and callback executed immediately.
        """
        if not callable(callback):
            raise TypeError("callback must be a callable")

        run_immediately = False
        with self._lock:
            if self._is_cancelled:
                run_immediately = True
            else:
                self._callbacks.append(callback)
                return True

        if run_immediately:
            try:
                callback()
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Error in immediately invoked CancellationToken callback: %s", exc)
            return False

        return True

    def throw_if_cancelled(self) -> None:
        """
        Raise OperationCancelledError if cancellation has been requested.
        """
        with self._lock:
            if self._is_cancelled:
                raise OperationCancelledError(
                    message=self._reason or "Operation was cancelled",
                    source=self._source,
                )
