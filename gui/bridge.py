# GuiBridge for E.V.
# Thread-safe bridge between EVEventBus and Qt/QML.
# Uses queued Qt signal to update Qt state from any thread.

from typing import List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt

from core.events import EVEvent, EVEventBus
from core.models import EVEventType, EVState


class GuiBridge(QObject):
    """
    Bridge that subscribes to EVEventBus and exposes state to QML.
    Thread-safe: uses queued Qt signal to update Qt state from any thread.
    """

    # Public signals for QML to bind to
    stateChanged = Signal(str)
    currentTaskChanged = Signal(str)
    latestObservationChanged = Signal(str)

    # Internal signal for safe cross-thread queued handoff
    _stateChangeRequested = Signal(object)
    _currentTaskChangeRequested = Signal(str)
    _latestObservationChangeRequested = Signal(str)

    def __init__(self, event_bus: EVEventBus) -> None:
        super().__init__()
        self._event_bus: EVEventBus = event_bus
        self._state: Optional[EVState] = event_bus.current_state
        self._current_task: str = ""
        self._latest_observation: str = ""
        self._subscription_tokens: List[str] = []
        self._setup_subscriptions()

    def _setup_subscriptions(self) -> None:
        """Connect internal signals and subscribe to EVEventBus."""
        self._stateChangeRequested.connect(
            self._on_state_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._currentTaskChangeRequested.connect(
            self._on_current_task_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._latestObservationChangeRequested.connect(
            self._on_latest_observation_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )

        token = self._event_bus.subscribe(
            self._on_event_received,
            event_types=[
                EVEventType.STATE_CHANGED,
                EVEventType.ACTION_STARTED,
                EVEventType.ACTION_COMPLETED,
                EVEventType.STATUS,
            ],
        )
        self._subscription_tokens.append(token)

    def _on_event_received(self, event: EVEvent) -> None:
        """
        Callback from EVEventBus (may be called from any thread).
        Only emits internal Qt signals to hand off execution to the Qt thread.
        """
        if event.event_type == EVEventType.STATE_CHANGED:
            if event.state is not None:
                self._stateChangeRequested.emit(event.state)
        elif event.event_type == EVEventType.ACTION_STARTED:
            msg = event.message if event.message else "Active"
            self._currentTaskChangeRequested.emit(msg)
        elif event.event_type == EVEventType.ACTION_COMPLETED:
            self._currentTaskChangeRequested.emit("")
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.STATUS:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)

    @Slot(object)
    def _on_state_changed_internal(self, new_state: EVState) -> None:
        """
        Slot executed in the Qt thread.
        Mutates internal state and emits public notification if state changed.
        """
        if self._state == new_state:
            return
        self._state = new_state
        self.stateChanged.emit(new_state.value)

    @Property(str, notify=stateChanged)
    def currentState(self) -> str:
        """Current state of E.V. for QML binding."""
        return self._state.value if self._state is not None else ""

    @Slot(str)
    def _on_current_task_changed_internal(self, task: str) -> None:
        if self._current_task == task:
            return
        self._current_task = task
        self.currentTaskChanged.emit(task)

    @Property(str, notify=currentTaskChanged)
    def currentTask(self) -> str:
        return self._current_task

    @Slot(str)
    def _on_latest_observation_changed_internal(self, observation: str) -> None:
        if self._latest_observation == observation:
            return
        self._latest_observation = observation
        self.latestObservationChanged.emit(observation)

    @Property(str, notify=latestObservationChanged)
    def latestObservation(self) -> str:
        return self._latest_observation

    @Slot(str, result=str)
    def getStateDescription(self, state_str: str) -> str:
        """Return a user-friendly description for a given state string."""
        try:
            state = EVState(state_str)
            descriptions = {
                EVState.IDLE: "Ready and waiting for input",
                EVState.LISTENING: "Listening for voice commands",
                EVState.PLANNING: "Formulating a plan",
                EVState.AWAITING_APPROVAL: "Waiting for user approval",
                EVState.EXECUTING: "Executing the planned action",
                EVState.VERIFYING: "Verifying the results",
                EVState.RECOVERING: "Recovering from an error",
                EVState.SPEAKING: "Speaking response",
                EVState.SUCCESS: "Task completed successfully",
                EVState.FAILED: "Task failed",
                EVState.STOPPED: "System stopped",
            }
            return descriptions.get(state, "Invalid state")
        except (ValueError, KeyError):
            return "Invalid state"

    def shutdown(self) -> None:
        """Unsubscribe from the event bus. Idempotent."""
        for token in self._subscription_tokens:
            self._event_bus.unsubscribe(token)
        self._subscription_tokens.clear()