"""
Event / State Bus for E.V.
"""
import threading
import uuid
import copy
from collections import deque
from datetime import datetime
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

from .models import (
    EVEventSeverity,
    EVEventType,
    EVState,
)


class EVEvent:
    """
    Immutable-style event model.
    """

    def __init__(
        self,
        event_type: EVEventType,
        source: str,
        *,
        event_id: Optional[str] = None,
        sequence: Optional[int] = None,
        severity: EVEventSeverity = EVEventSeverity.INFO,
        message: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        state: Optional[EVState] = None,
        previous_state: Optional[EVState] = None,
        correlation_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.event_id: str = event_id or str(uuid.uuid4())
        self.sequence: int = sequence if sequence is not None else 0
        self.event_type: EVEventType = event_type
        self.severity: EVEventSeverity = severity
        self.source: str = source
        self.message: Optional[str] = message
        self.timestamp: datetime = timestamp or datetime.now()
        self.state: Optional[EVState] = state
        self.previous_state: Optional[EVState] = previous_state
        self.correlation_id: Optional[str] = correlation_id
        self.data: Dict[str, Any] = copy.deepcopy(data) if data is not None else {}

    def __repr__(self) -> str:
        return (
            f"EVEvent(event_id={self.event_id}, sequence={self.sequence}, "
            f"event_type={self.event_type}, severity={self.severity}, "
            f"source='{self.source}', message={self.message}, "
            f"timestamp={self.timestamp}, state={self.state}, "
            f"previous_state={self.previous_state}, correlation_id={self.correlation_id}, "
            f"data={self.data})"
        )


class EventPublishResult:
    """
    Result of publishing an event.
    """

    def __init__(
        self,
        event: EVEvent,
        delivered_count: int,
        failed_count: int,
        subscriber_errors: List[Tuple[str, Exception]],
    ) -> None:
        self.event: EVEvent = copy.deepcopy(event)
        self.delivered_count: int = delivered_count
        self.failed_count: int = failed_count
        self.subscriber_errors: List[Tuple[str, Exception]] = subscriber_errors

    def __repr__(self) -> str:
        return (
            f"EventPublishResult(event={self.event.event_id}, "
            f"delivered={self.delivered_count}, failed={self.failed_count}, "
            f"errors={len(self.subscriber_errors)})"
        )


class StateChangeResult:
    """
    Result of a state change operation.
    """

    def __init__(
        self,
        changed: bool,
        previous_state: Optional[EVState],
        current_state: Optional[EVState],
        event: Optional[EVEvent],
        publish_result: Optional[EventPublishResult],
    ) -> None:
        self.changed: bool = changed
        self.previous_state: Optional[EVState] = previous_state
        self.current_state: Optional[EVState] = current_state
        self.event: Optional[EVEvent] = copy.deepcopy(event) if event is not None else None
        self.publish_result: Optional[EventPublishResult] = publish_result

    def __repr__(self) -> str:
        return (
            f"StateChangeResult(changed={self.changed}, "
            f"previous_state={self.previous_state}, current_state={self.current_state}, "
            f"event={self.event.event_id if self.event else None}, "
            f"publish_result={self.publish_result})"
        )


class EVEventBus:
    """
    Thread-safe in-memory event / state bus for E.V.
    """

    def __init__(
        self,
        initial_state: EVState = EVState.IDLE,
        history_limit: int = 500,
    ) -> None:
        if history_limit < 1:
            raise ValueError("history_limit must be >= 1")
        self._state: EVState = initial_state
        self._history_limit: int = history_limit
        self._history: Deque[EVEvent] = deque(maxlen=history_limit)
        self._sequence_counter: int = 0
        # subscription token -> (callback, event_types_filter)
        self._subscriptions: Dict[str, Tuple[Callable[[EVEvent], None], Optional[Set[EVEventType]]]] = {}
        self._lock: threading.RLock = threading.RLock()

    @property
    def current_state(self) -> EVState:
        with self._lock:
            return self._state

    def subscribe(
        self,
        callback: Callable[[EVEvent], None],
        event_types: Optional[List[EVEventType]] = None,
    ) -> str:
        if not callable(callback):
            raise TypeError("callback must be callable")
        with self._lock:
            token = str(uuid.uuid4())
            event_types_set: Optional[Set[EVEventType]] = (
                set(event_types) if event_types is not None else None
            )
            self._subscriptions[token] = (callback, event_types_set)
            return token

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                return True
            return False

    def _create_event_locked(
        self,
        event_type: EVEventType,
        source: str,
        *,
        message: Optional[str] = None,
        severity: EVEventSeverity = EVEventSeverity.INFO,
        data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        state: Optional[EVState] = None,
        previous_state: Optional[EVState] = None,
    ) -> Tuple[EVEvent, List[Tuple[str, Callable[[EVEvent], None], Optional[Set[EVEventType]]]]]:
        """
        Create an event while holding the lock.
        Returns the event and a snapshot of subscriptions.
        Does NOT append to history or increment sequence here; that is done by the caller.
        """
        event = EVEvent(
            event_type=event_type,
            source=source,
            event_id=str(uuid.uuid4()),  # temporary, will be overwritten by caller if needed
            sequence=0,                  # temporary
            severity=severity,
            message=message,
            timestamp=datetime.now(),    # temporary
            state=state,
            previous_state=previous_state,
            correlation_id=correlation_id,
            data=data,
        )
        # Snapshot subscriptions
        subscriptions: List[Tuple[str, Callable[[EVEvent], None], Optional[Set[EVEventType]]]] = [
            (token, cb, et) for token, (cb, et) in self._subscriptions.items()
        ]
        return event, subscriptions

    def publish(
        self,
        event_type: EVEventType,
        source: str,
        *,
        message: Optional[str] = None,
        severity: EVEventSeverity = EVEventSeverity.INFO,
        data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        state: Optional[EVState] = None,
        previous_state: Optional[EVState] = None,
    ) -> EventPublishResult:
        with self._lock:
            # Increment sequence and assign to event
            self._sequence_counter += 1
            seq = self._sequence_counter
            event, subscriptions = self._create_event_locked(
                event_type=event_type,
                source=source,
                message=message,
                severity=severity,
                data=data,
                correlation_id=correlation_id,
                state=state,
                previous_state=previous_state,
            )
            # Overwrite the temporary fields
            event.sequence = seq
            event.timestamp = datetime.now()
            # Append to history
            self._history.append(event)

        delivered_count = 0
        failed_count = 0
        subscriber_errors: List[Tuple[str, Exception]] = []

        for token, callback, event_types_filter in subscriptions:
            # Filter by event type if specified
            if event_types_filter is not None and event.event_type not in event_types_filter:
                continue
            try:
                # Deliver a copy of the event to avoid exposing internal mutable state
                event_copy = copy.deepcopy(event)
                callback(event_copy)
                delivered_count += 1
            except Exception as exc:  # pylint: disable=broad-except
                failed_count += 1
                subscriber_errors.append((token, exc))

        return EventPublishResult(
            event=event,
            delivered_count=delivered_count,
            failed_count=failed_count,
            subscriber_errors=subscriber_errors,
        )

    def set_state(
        self,
        new_state: EVState,
        *,
        source: str = "system",
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> StateChangeResult:
        with self._lock:
            if self._state == new_state:
                # No change
                return StateChangeResult(
                    changed=False,
                    previous_state=self._state,
                    current_state=self._state,
                    event=None,
                    publish_result=None,
                )
            previous_state = self._state
            self._state = new_state
            # Increment sequence and create the STATE_CHANGED event
            self._sequence_counter += 1
            seq = self._sequence_counter
            event, subscriptions = self._create_event_locked(
                event_type=EVEventType.STATE_CHANGED,
                source=source,
                message=reason or f"State changed from {previous_state} to {new_state}",
                severity=EVEventSeverity.INFO,
                data=data,
                correlation_id=correlation_id,
                state=new_state,
                previous_state=previous_state,
            )
            # Overwrite the temporary fields
            event.sequence = seq
            event.timestamp = datetime.now()
            # Append to history
            self._history.append(event)

        delivered_count = 0
        failed_count = 0
        subscriber_errors: List[Tuple[str, Exception]] = []

        for token, callback, event_types_filter in subscriptions:
            # Filter by event type if specified
            if event_types_filter is not None and event.event_type not in event_types_filter:
                continue
            try:
                # Deliver a copy of the event to avoid exposing internal mutable state
                event_copy = copy.deepcopy(event)
                callback(event_copy)
                delivered_count += 1
            except Exception as exc:  # pylint: disable=broad-except
                failed_count += 1
                subscriber_errors.append((token, exc))

        publish_result = EventPublishResult(
            event=event,
            delivered_count=delivered_count,
            failed_count=failed_count,
            subscriber_errors=subscriber_errors,
        )
        return StateChangeResult(
            changed=True,
            previous_state=previous_state,
            current_state=new_state,
            event=event,
            publish_result=publish_result,
        )

    def get_history(
        self,
        limit: Optional[int] = None,
        event_types: Optional[List[EVEventType]] = None,
    ) -> List[EVEvent]:
        if limit is not None and limit < 0:
            raise ValueError("limit must be non-negative or None")
        with self._lock:
            # Create a deep copy of the history for safety
            history_copy = copy.deepcopy(list(self._history))
        if event_types is not None:
            event_types_set = set(event_types)
            history_copy = [
                event for event in history_copy if event.event_type in event_types_set
            ]
        if limit is not None:
            if limit == 0:
                return []
            return history_copy[-limit:]
        return history_copy