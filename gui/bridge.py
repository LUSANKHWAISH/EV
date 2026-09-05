# GuiBridge for E.V.
# Thread-safe bridge between EVEventBus and Qt/QML.
# Uses queued Qt signal to update Qt state from any thread.

from typing import List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt

from core.events import EVEvent, EVEventBus
from core.experience import EVExperienceManager
from core.models import EVEventType, EVState


class GuiBridge(QObject):
    """
    Bridge that subscribes to EVEventBus and exposes state to QML.
    Thread-safe: uses queued Qt signal to update Qt state from any thread.
    """

    # Public signals for QML to bind to
    stateChanged = Signal(str)
    voiceStateChanged = Signal(str)
    currentTaskChanged = Signal(str)
    latestObservationChanged = Signal(str)
    taskSubmitted = Signal(str)
    approvalRequested = Signal(str, str, str, str)  # task_id, action, risk_level, reason
    approvalResolved = Signal(str, bool)             # task_id, approved
    approvalSubmitted = Signal(str, bool)            # task_id, approved (for orchestrator hook)
    experienceModeChanged = Signal(str)
    stylePresetChanged = Signal(str)
    systemAlertChanged = Signal(str)

    # Internal signal for safe cross-thread queued handoff
    _stateChangeRequested = Signal(object)
    _voiceStateChangeRequested = Signal(str)
    _currentTaskChangeRequested = Signal(str)
    _latestObservationChangeRequested = Signal(str)
    _approvalRequestQueued = Signal(str, str, str, str)
    _experienceModeChangeRequested = Signal(str)
    _stylePresetChangeRequested = Signal(str)
    _systemAlertChangeRequested = Signal(str)

    def __init__(
        self,
        event_bus: EVEventBus,
        experience_manager: Optional[EVExperienceManager] = None,
    ) -> None:
        super().__init__()
        self._event_bus: EVEventBus = event_bus
        self._experience_manager: Optional[EVExperienceManager] = experience_manager
        self._state: Optional[EVState] = event_bus.current_state
        self._voice_state: str = "IDLE"
        self._current_task: str = ""
        self._latest_observation: str = ""
        self._experience_mode: str = (
            experience_manager.current_mode.value if experience_manager else "STANDARD"
        )
        self._style_preset: str = (
            experience_manager.current_preset.value if experience_manager else "EV_CORE"
        )
        self._system_alert_message: str = ""
        self._subscription_tokens: List[str] = []
        self._setup_subscriptions()

    def set_experience_manager(self, experience_manager: Optional[EVExperienceManager]) -> None:
        """Attach an experience manager to the bridge after construction."""
        self._experience_manager = experience_manager
        if experience_manager is not None:
            self._experience_mode = experience_manager.current_mode.value
            self._style_preset = experience_manager.current_preset.value

    def _setup_subscriptions(self) -> None:
        """Connect internal signals and subscribe to EVEventBus."""
        self._stateChangeRequested.connect(
            self._on_state_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._voiceStateChangeRequested.connect(
            self._on_voice_state_changed_internal,
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
        self._approvalRequestQueued.connect(
            self._on_approval_requested_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._experienceModeChangeRequested.connect(
            self._on_experience_mode_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._stylePresetChangeRequested.connect(
            self._on_style_preset_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._systemAlertChangeRequested.connect(
            self._on_system_alert_changed_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )

        token = self._event_bus.subscribe(
            self._on_event_received,
            event_types=[
                EVEventType.STATE_CHANGED,
                EVEventType.VOICE_STATE_CHANGED,
                EVEventType.ACTION_STARTED,
                EVEventType.ACTION_COMPLETED,
                EVEventType.VERIFICATION_RESULT,
                EVEventType.APPROVAL_REQUIRED,
                EVEventType.STATUS,
                EVEventType.SYSTEM_ALERT,
                EVEventType.SYSTEM_ALERT_RECOVERED,
                EVEventType.EXPERIENCE_MODE_CHANGED,
                EVEventType.STYLE_PRESET_CHANGED,
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
        elif event.event_type == EVEventType.VOICE_STATE_CHANGED:
            voice_state = str(event.data.get("voice_state", "")) if event.data else ""
            if voice_state:
                self._voiceStateChangeRequested.emit(voice_state)
        elif event.event_type == EVEventType.ACTION_STARTED:
            msg = event.message if event.message else "Active"
            self._currentTaskChangeRequested.emit(msg)
        elif event.event_type == EVEventType.ACTION_COMPLETED:
            self._currentTaskChangeRequested.emit("")
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.VERIFICATION_RESULT:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.APPROVAL_REQUIRED:
            task_id = str(event.data.get("task_id") if event.data else event.correlation_id or "")
            action = str(event.data.get("action") if event.data else "")
            risk_level = str(event.data.get("risk_level") if event.data else "")
            reason = str(event.data.get("reason") if event.data else event.message or "")
            self._approvalRequestQueued.emit(task_id, action, risk_level, reason)
        elif event.event_type == EVEventType.STATUS:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type in (EVEventType.SYSTEM_ALERT, EVEventType.SYSTEM_ALERT_RECOVERED):
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
                self._systemAlertChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.EXPERIENCE_MODE_CHANGED:
            mode = str(event.data.get("current_mode", "")) if event.data else ""
            if mode:
                self._experienceModeChangeRequested.emit(mode)
        elif event.event_type == EVEventType.STYLE_PRESET_CHANGED:
            preset = str(event.data.get("current_preset", "")) if event.data else ""
            if preset:
                self._stylePresetChangeRequested.emit(preset)

    @Slot(object)
    def _on_state_changed_internal(self, new_state: EVState) -> None:
        """
        Slot executed in the Qt thread.
        Mutates internal state and emits public notification if state changed.
        """
        if self._state == new_state:
            return
        self._state = new_state
        val = new_state.value if hasattr(new_state, "value") else str(new_state)
        self.stateChanged.emit(val)

    @Slot(str)
    def _on_voice_state_changed_internal(self, voice_state: str) -> None:
        """
        Slot executed in the Qt thread.
        Mutates voice state and synchronizes display state when appropriate.
        """
        if self._voice_state == voice_state:
            return
        self._voice_state = voice_state
        self.voiceStateChanged.emit(voice_state)

        # Synchronize currentState so existing flagship HUD components
        # (EVStatusIndicator, EVTelemetryRail, EVIntelligenceCore) reflect voice interaction
        # unless a blocking system state (like AWAITING_APPROVAL) takes precedence.
        if self._state not in (EVState.AWAITING_APPROVAL,):
            try:
                new_state = EVState(voice_state)
                if self._state != new_state:
                    self._state = new_state
                    self.stateChanged.emit(new_state.value)
            except ValueError:
                current_val = self._state.value if hasattr(self._state, "value") else str(self._state or "")
                if current_val != voice_state:
                    self._state = voice_state  # type: ignore
                    self.stateChanged.emit(voice_state)

    @Property(str, notify=voiceStateChanged)
    def voiceState(self) -> str:
        """Current voice subsystem state for QML binding."""
        return self._voice_state

    @Property(bool, notify=voiceStateChanged)
    def isVoiceActive(self) -> bool:
        """True when the voice subsystem is actively interacting (not IDLE/PAUSED)."""
        return self._voice_state not in ("IDLE", "PAUSED", "")

    @Slot(str, str, str, str)
    def _on_approval_requested_internal(self, task_id: str, action: str, risk_level: str, reason: str) -> None:
        """Slot executed in Qt thread when approval is required."""
        self.approvalRequested.emit(task_id, action, risk_level, reason)

    @Property(str, notify=stateChanged)
    def currentState(self) -> str:
        """Current state of E.V. for QML binding."""
        if self._state is None:
            return ""
        return self._state.value if hasattr(self._state, "value") else str(self._state)

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
        descriptions = {
            "IDLE": "Ready and waiting for input",
            "VERIFYING_WAKE": "Verifying wake phrase...",
            "LISTENING": "Listening for voice commands",
            "TRANSCRIBING": "Transcribing speech...",
            "PROCESSING": "Processing command...",
            "PLANNING": "Formulating a plan",
            "AWAITING_APPROVAL": "Waiting for user approval",
            "EXECUTING": "Executing the planned action",
            "VERIFYING": "Verifying the results",
            "RECOVERING": "Recovering from an error",
            "SPEAKING": "Speaking response",
            "SUCCESS": "Task completed successfully",
            "FAILED": "Task failed",
            "STOPPED": "System stopped",
            "PAUSED": "Voice processing paused",
            "ERROR": "Error encountered",
        }
        return descriptions.get(state_str, "Invalid state")

    @Slot(str)
    def submitTask(self, command: str) -> None:
        """Called by QML to submit a user task."""
        self.taskSubmitted.emit(command)

    @Slot(str, bool)
    def submitApproval(self, task_id: str, approved: bool) -> None:
        """Called by QML or tests to submit user approval or denial."""
        self.approvalSubmitted.emit(task_id, approved)
        self.approvalResolved.emit(task_id, approved)

    # ------------------------------------------------------------------
    # Experience mode / style preset properties
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_experience_mode_changed_internal(self, mode: str) -> None:
        if self._experience_mode == mode:
            return
        self._experience_mode = mode
        self.experienceModeChanged.emit(mode)

    @Slot(str)
    def _on_style_preset_changed_internal(self, preset: str) -> None:
        if self._style_preset == preset:
            return
        self._style_preset = preset
        self.stylePresetChanged.emit(preset)

    @Slot(str)
    def _on_system_alert_changed_internal(self, message: str) -> None:
        if self._system_alert_message == message:
            return
        self._system_alert_message = message
        self.systemAlertChanged.emit(message)

    @Property(str, notify=experienceModeChanged)
    def experienceMode(self) -> str:
        """Current experience mode for QML binding."""
        return self._experience_mode

    @Property(str, notify=stylePresetChanged)
    def stylePreset(self) -> str:
        """Current visual style preset for QML binding."""
        return self._style_preset

    @Property(str, notify=systemAlertChanged)
    def systemAlertMessage(self) -> str:
        """Latest system alert message for QML binding."""
        return self._system_alert_message

    @Property(str, notify=experienceModeChanged)
    def experienceModeDescription(self) -> str:
        """Human-readable description of the current experience mode."""
        if self._experience_manager:
            return self._experience_manager.get_mode_description(self._experience_mode)
        return ""

    @Slot(str)
    def setExperienceMode(self, mode: str) -> None:
        """Called by QML to change the experience mode."""
        if self._experience_manager:
            try:
                from core.experience import EVExperienceMode
                self._experience_manager.set_mode(EVExperienceMode(mode))
            except (ValueError, KeyError):
                pass  # Invalid mode string — silently ignore from QML

    @Slot(str)
    def setStylePreset(self, preset: str) -> None:
        """Called by QML to change the visual style preset."""
        if self._experience_manager:
            try:
                from core.experience import EVCoreStylePreset
                self._experience_manager.set_style_preset(EVCoreStylePreset(preset))
            except (ValueError, KeyError):
                pass  # Invalid preset string — silently ignore from QML

    def shutdown(self) -> None:
        """Unsubscribe from the event bus. Idempotent."""
        for token in self._subscription_tokens:
            self._event_bus.unsubscribe(token)
        self._subscription_tokens.clear()