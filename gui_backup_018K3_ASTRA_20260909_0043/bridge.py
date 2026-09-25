# GuiBridge for E.V.
# Thread-safe bridge between EVEventBus and Qt/QML.
# Uses queued Qt signal to update Qt state from any thread.

from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, Property, Signal, Slot, Qt

from core.events import EVEvent, EVEventBus
from core.experience import EVExperienceManager
from core.models import EVEventType, EVState

logger = logging.getLogger(__name__)

# Lifecycle stage index mapping and terminal stage set (Phase 018-E)
_STAGE_INDEX_MAP: Dict[str, int] = {
    "IDLE": 0,
    "THINKING": 1,
    "PLANNING": 2,
    "VALIDATING": 3,
    "RISK": 4,
    "APPROVAL": 5,
    "EXECUTE": 6,
    "EXECUTING": 6,
    "VERIFY": 7,
    "VERIFYING": 7,
    "SUCCESS": 8,
    "FAILED": 8,
    "ROLLED_BACK": 8,
    "CANCELLED": 8,
}
_TERMINAL_STAGES = {"SUCCESS", "FAILED", "ROLLED_BACK", "CANCELLED"}


class GuiBridge(QObject):
    """
    Bridge that subscribes to EVEventBus and exposes state to QML.
    Thread-safe: uses queued Qt signal to update Qt state from any thread.
    """

    # Public signals for QML to bind to
    stateChanged = Signal(str)
    voiceStateChanged = Signal(str)
    voiceLevelChanged = Signal(float)
    speechLevelChanged = Signal(float)
    voiceActivityChanged = Signal(bool)
    speakingActivityChanged = Signal(bool)
    currentTaskChanged = Signal(str)
    latestObservationChanged = Signal(str)
    taskSubmitted = Signal(str)
    approvalRequested = Signal(str, str, str, str)  # task_id, action, risk_level, reason
    approvalResolved = Signal(str, bool)             # task_id, approved
    approvalSubmitted = Signal(str, bool)            # task_id, approved (for orchestrator hook)
    approvalPendingChanged = Signal(bool)
    approvalTaskIdChanged = Signal(str)
    approvalActionChanged = Signal(str)
    approvalDescriptionChanged = Signal(str)
    approvalResourceChanged = Signal(str)
    approvalRiskLevelChanged = Signal(str)
    approvalReasonChanged = Signal(str)
    approvalReversibleChanged = Signal(bool)
    approvalRollbackAvailableChanged = Signal(bool)
    approvalResolvingChanged = Signal(bool)
    approvalFailed = Signal(str, str)  # task_id, error
    telemetryUpdated = Signal()
    telemetryAvailableChanged = Signal(bool)
    telemetryCpuPercentChanged = Signal(float)
    telemetryMemoryPercentChanged = Signal(float)
    telemetryMemoryUsedMbChanged = Signal(int)
    telemetryMemoryTotalMbChanged = Signal(int)
    telemetryDiskFreePercentChanged = Signal(float)
    telemetryDiskFreeGbChanged = Signal(float)
    telemetryProcessCountChanged = Signal(int)
    telemetryTopProcessNameChanged = Signal(str)
    telemetryTopProcessCpuPercentChanged = Signal(float)
    telemetryTopProcessMemoryMbChanged = Signal(int)
    telemetryNetworkConnectedChanged = Signal(bool)
    experienceModeChanged = Signal(str)
    stylePresetChanged = Signal(str)
    systemAlertChanged = Signal(str)
    awarenessEventChanged = Signal(str, str, str)  # awareness_id, title, message
    latestAwarenessTitleChanged = Signal(str)
    latestAwarenessMessageChanged = Signal(str)
    latestAwarenessSeverityChanged = Signal(str)
    taskResultChanged = Signal()

    # Lifecycle projection signals (Phase 018-E)
    lifecycleStageChanged = Signal(str)
    lifecycleStageIndexChanged = Signal(int)
    lifecycleActiveChanged = Signal(bool)
    lifecycleRollbackChanged = Signal(bool)

    # Internal signal for safe cross-thread queued handoff
    _stateChangeRequested = Signal(object)
    _voiceStateChangeRequested = Signal(str)
    _voiceTelemetryQueued = Signal(float, float, bool, bool)
    _currentTaskChangeRequested = Signal(str)
    _latestObservationChangeRequested = Signal(str)
    _approvalRequestQueued = Signal(dict)
    _approvalFailedQueued = Signal(str, str)
    _telemetryUpdated = Signal(dict)
    _experienceModeChangeRequested = Signal(str)
    _stylePresetChangeRequested = Signal(str)
    _systemAlertChangeRequested = Signal(str)
    _awarenessEventQueued = Signal(str, str, str, str)
    _taskResultQueued = Signal(str, str, bool)
    _lifecycleStageQueued = Signal(str, dict)

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
        self._voice_level: float = 0.0
        self._speech_level: float = 0.0
        self._voice_activity: bool = False
        self._speaking_activity: bool = False
        self._current_task: str = ""
        self._latest_observation: str = ""
        self._approval_pending: bool = False
        self._approval_resolving: bool = False
        self._approval_task_id: str = ""
        self._approval_action: str = ""
        self._approval_description: str = ""
        self._approval_resource: str = ""
        self._approval_risk_level: str = ""
        self._approval_reason: str = ""
        self._approval_reversible: bool = True
        self._approval_rollback_available: bool = True
        self._telemetry_available: bool = False
        self._telemetry_timestamp: Optional[datetime] = None
        self._telemetry_cpu_percent: float = 0.0
        self._telemetry_memory_percent: float = 0.0
        self._telemetry_memory_used_mb: int = 0
        self._telemetry_memory_total_mb: int = 0
        self._telemetry_disk_free_percent: float = 0.0
        self._telemetry_disk_free_gb: float = 0.0
        self._telemetry_process_count: int = 0
        self._telemetry_top_process_name: str = ""
        self._telemetry_top_process_cpu_percent: float = 0.0
        self._telemetry_top_process_memory_mb: int = 0
        self._telemetry_network_connected: bool = False
        self._experience_mode: str = (
            experience_manager.current_mode.value if experience_manager else "STANDARD"
        )
        self._style_preset: str = (
            experience_manager.current_preset.value if experience_manager else "EV_CORE"
        )
        self._system_alert_message: str = ""
        self._latest_awareness_title: str = ""
        self._latest_awareness_message: str = ""
        self._latest_awareness_severity: str = "INFO"
        self._task_result: str = ""
        self._task_result_status: str = "IDLE"
        self._task_result_success: bool = False
        self._task_result_available: bool = False
        self._lifecycle_stage: str = "IDLE"
        self._lifecycle_stage_index: int = 0
        self._lifecycle_max_stage_index: int = 0
        self._lifecycle_active: bool = False
        self._lifecycle_rollback: bool = False
        self._lifecycle_terminal: bool = False
        self._lifecycle_approval_required: bool = False
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
        self._voiceTelemetryQueued.connect(
            self._on_voice_telemetry_internal,
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
        self._approvalFailedQueued.connect(
            self._on_approval_failed_internal,
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
        self._awarenessEventQueued.connect(
            self._on_awareness_event_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._telemetryUpdated.connect(
            self._on_telemetry_updated_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._taskResultQueued.connect(
            self._on_task_result_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )
        self._lifecycleStageQueued.connect(
            self._on_lifecycle_stage_internal,
            type=Qt.ConnectionType.QueuedConnection,
        )

        token = self._event_bus.subscribe(
            self._on_event_received,
            event_types=[
                EVEventType.STATE_CHANGED,
                EVEventType.VOICE_STATE_CHANGED,
                EVEventType.VOICE_TELEMETRY,
                EVEventType.ACTION_STARTED,
                EVEventType.ACTION_COMPLETED,
                EVEventType.ACTION_VERIFYING,
                EVEventType.VERIFICATION_RESULT,
                EVEventType.APPROVAL_REQUIRED,
                EVEventType.PLAN_STARTED,
                EVEventType.PLAN_COMPLETED,
                EVEventType.PLAN_FAILED,
                EVEventType.PLAN_CANCELLED,
                EVEventType.PLAN_ROLLED_BACK,
                EVEventType.PLAN_CREATED,
                EVEventType.PLAN_VALIDATED,
                EVEventType.STATUS,
                EVEventType.SYSTEM_ALERT,
                EVEventType.SYSTEM_ALERT_RECOVERED,
                EVEventType.SYSTEM_OBSERVATION,
                EVEventType.EXPERIENCE_MODE_CHANGED,
                EVEventType.STYLE_PRESET_CHANGED,
                EVEventType.AWARENESS_EVENT,
                EVEventType.AWARENESS_RESOLVED,
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
                val = event.state.value if hasattr(event.state, "value") else str(event.state)
                if val == "AWAITING_APPROVAL":
                    self._lifecycleStageQueued.emit("APPROVAL", {})
                elif val == "EXECUTING":
                    self._lifecycleStageQueued.emit("EXECUTE", {})
        elif event.event_type == EVEventType.VOICE_STATE_CHANGED:
            voice_state = str(event.data.get("voice_state", "")) if event.data else ""
            if voice_state:
                self._voiceStateChangeRequested.emit(voice_state)
        elif event.event_type == EVEventType.VOICE_TELEMETRY:
            data = event.data or {}
            vl = float(data.get("voiceLevel", 0.0))
            sl = float(data.get("speechLevel", 0.0))
            va = bool(data.get("voiceActivity", False))
            sa = bool(data.get("speakingActivity", False))
            self._voiceTelemetryQueued.emit(vl, sl, va, sa)
        elif event.event_type == EVEventType.ACTION_STARTED:
            msg = event.message if event.message else "Active"
            self._currentTaskChangeRequested.emit(msg)
            self._lifecycleStageQueued.emit("EXECUTE", {})
        elif event.event_type == EVEventType.ACTION_COMPLETED:
            self._currentTaskChangeRequested.emit("")
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.ACTION_VERIFYING:
            self._lifecycleStageQueued.emit("VERIFY", {})
        elif event.event_type == EVEventType.VERIFICATION_RESULT:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.PLAN_STARTED:
            self._lifecycleStageQueued.emit("EXECUTE", {})
        elif event.event_type == EVEventType.PLAN_CREATED:
            self._lifecycleStageQueued.emit("PLANNING", {})
        elif event.event_type == EVEventType.PLAN_VALIDATED:
            self._lifecycleStageQueued.emit("VALIDATING", {})
        elif event.event_type == EVEventType.PLAN_ROLLED_BACK:
            self._lifecycleStageQueued.emit("ROLLED_BACK", {"rollback": True})
        elif event.event_type == EVEventType.PLAN_COMPLETED:
            self._lifecycleStageQueued.emit("SUCCESS", {})
        elif event.event_type == EVEventType.PLAN_FAILED:
            data_d = event.data or {}
            meta = data_d.get("metadata") or {}
            is_rb = bool(meta.get("rolled_back") or data_d.get("rolled_back"))
            if is_rb:
                self._lifecycleStageQueued.emit("ROLLED_BACK", {"rollback": True})
            else:
                self._lifecycleStageQueued.emit("FAILED", {})
        elif event.event_type == EVEventType.PLAN_CANCELLED:
            self._lifecycleStageQueued.emit("CANCELLED", {})
        elif event.event_type == EVEventType.APPROVAL_REQUIRED:
            data: Dict[str, Any] = event.data or {}
            task_id = str(data.get("task_id") or data.get("plan_id") or event.correlation_id or "")
            action = str(data.get("action") or "")
            risk_level = str(data.get("risk_level") or "")
            reason = str(data.get("reason") or event.message or "")
            description = str(data.get("description") or data.get("goal") or reason or action)

            # Extract affected resource if present in parameters or plan steps
            resource = str(data.get("resource") or "")
            if not resource and "parameters" in data and isinstance(data["parameters"], dict):
                p = data["parameters"]
                resource = str(p.get("target_path") or p.get("service_name") or p.get("process_name") or p.get("name") or p.get("host") or "")
            elif not resource and "steps" in data and isinstance(data["steps"], list) and data["steps"]:
                first_step = data["steps"][0]
                if isinstance(first_step, dict):
                    if not action:
                        action = str(first_step.get("action") or "")
                    if not description:
                        description = str(first_step.get("description") or "")
                    step_params = first_step.get("parameters") or {}
                    if isinstance(step_params, dict):
                        resource = str(step_params.get("target_path") or step_params.get("service_name") or step_params.get("process_name") or step_params.get("name") or step_params.get("host") or "")

            reversible = bool(data.get("reversible", True))
            rollback_available = bool(
                data.get("rollback_available", bool(data.get("transaction_id") or data.get("transaction_required", True)))
            )

            payload = {
                "task_id": task_id,
                "plan_id": task_id,
                "action": action,
                "description": description,
                "resource": resource,
                "risk_level": risk_level,
                "reason": reason,
                "reversible": reversible,
                "rollback_available": rollback_available,
            }
            self._approvalRequestQueued.emit(payload)
            self._lifecycleStageQueued.emit("APPROVAL", payload)
        elif event.event_type == EVEventType.STATUS:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
                msg_l = event.message.lower()
                if "resolving command" in msg_l:
                    self._lifecycleStageQueued.emit("THINKING", {})
                elif "planning" in msg_l:
                    self._lifecycleStageQueued.emit("PLANNING", {})
                elif "validat" in msg_l:
                    self._lifecycleStageQueued.emit("VALIDATING", {})
        elif event.event_type == EVEventType.SYSTEM_OBSERVATION:
            data: Dict[str, Any] = event.data or {}
            payload = self._parse_telemetry_data(data)
            if payload:
                if "timestamp" not in payload and event.timestamp:
                    payload["timestamp"] = event.timestamp
                self._telemetryUpdated.emit(payload)
        elif event.event_type == EVEventType.SYSTEM_ALERT:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
                self._systemAlertChangeRequested.emit(event.message)
        elif event.event_type == EVEventType.SYSTEM_ALERT_RECOVERED:
            if event.message:
                self._latestObservationChangeRequested.emit(event.message)
            self._systemAlertChangeRequested.emit("")
        elif event.event_type == EVEventType.EXPERIENCE_MODE_CHANGED:
            mode = str(event.data.get("current_mode", "")) if event.data else ""
            if mode:
                self._experienceModeChangeRequested.emit(mode)
        elif event.event_type == EVEventType.STYLE_PRESET_CHANGED:
            preset = str(event.data.get("current_preset", "")) if event.data else ""
            if preset:
                self._stylePresetChangeRequested.emit(preset)
        elif event.event_type == EVEventType.AWARENESS_EVENT:
            title = str(event.data.get("title", "")) if event.data else ""
            msg = str(event.data.get("message", event.message or "")) if event.data else str(event.message or "")
            aid = str(event.data.get("awareness_id", "")) if event.data else ""
            raw_sev = str(event.data.get("severity", "INFO")).upper() if event.data else "INFO"
            sev = raw_sev if raw_sev in ("INFO", "NOTICE", "WARNING", "CRITICAL") else "INFO"
            clean_title = title.strip()[:100]
            clean_msg = msg.strip()[:500]
            combined = f"{clean_title}: {clean_msg}" if clean_title and clean_msg else (clean_title or clean_msg)
            if combined:
                self._latestObservationChangeRequested.emit(combined)
                self._systemAlertChangeRequested.emit(combined)
            self._awarenessEventQueued.emit(aid, clean_title, clean_msg, sev)
        elif event.event_type == EVEventType.AWARENESS_RESOLVED:
            self._systemAlertChangeRequested.emit("")
            self._awarenessEventQueued.emit("", "", "", "INFO")

    @Slot(object)
    def _on_state_changed_internal(self, new_state: EVState) -> None:
        """
        Slot executed in the Qt thread.
        Mutates internal state and emits public notification if state changed.
        """
        if self._state == new_state:
            return
        self._state = new_state
        if new_state not in (EVState.AWAITING_APPROVAL,):
            self._clear_approval()
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

    @Slot(float, float, bool, bool)
    def _on_voice_telemetry_internal(self, voice_level: float, speech_level: float, voice_activity: bool, speaking_activity: bool) -> None:
        if self._voice_level != voice_level:
            self._voice_level = voice_level
            self.voiceLevelChanged.emit(voice_level)
        if self._speech_level != speech_level:
            self._speech_level = speech_level
            self.speechLevelChanged.emit(speech_level)
        if self._voice_activity != voice_activity:
            self._voice_activity = voice_activity
            self.voiceActivityChanged.emit(voice_activity)
        if self._speaking_activity != speaking_activity:
            self._speaking_activity = speaking_activity
            self.speakingActivityChanged.emit(speaking_activity)

    @Property(float, notify=voiceLevelChanged)
    def voiceLevel(self) -> float:
        return self._voice_level

    @Property(float, notify=speechLevelChanged)
    def speechLevel(self) -> float:
        return self._speech_level

    @Property(bool, notify=voiceActivityChanged)
    def voiceActivity(self) -> bool:
        return self._voice_activity

    @Property(bool, notify=speakingActivityChanged)
    def speakingActivity(self) -> bool:
        return self._speaking_activity

    @Slot(dict)
    def _on_approval_requested_internal(self, payload: dict) -> None:
        """Slot executed in Qt thread when approval is required."""
        task_id = str(payload.get("task_id") or payload.get("plan_id") or "")
        action = str(payload.get("action") or "")
        risk_level = str(payload.get("risk_level") or "")
        reason = str(payload.get("reason") or "")
        description = str(payload.get("description") or payload.get("goal") or reason or action)
        resource = str(payload.get("resource") or "")
        reversible = bool(payload.get("reversible", True))
        rollback_available = bool(payload.get("rollback_available", True))

        self._approval_pending = True
        self._approval_task_id = task_id
        self._approval_action = action
        self._approval_description = description
        self._approval_resource = resource
        self._approval_risk_level = risk_level
        self._approval_reason = reason
        self._approval_reversible = reversible
        self._approval_rollback_available = rollback_available

        self.approvalPendingChanged.emit(True)
        self.approvalTaskIdChanged.emit(task_id)
        self.approvalActionChanged.emit(action)
        self.approvalDescriptionChanged.emit(description)
        self.approvalResourceChanged.emit(resource)
        self.approvalRiskLevelChanged.emit(risk_level)
        self.approvalReasonChanged.emit(reason)
        self.approvalReversibleChanged.emit(reversible)
        self.approvalRollbackAvailableChanged.emit(rollback_available)

        # Existing 4-arg signal for backwards compatibility with existing handlers
        self.approvalRequested.emit(task_id, action, risk_level, reason)

    def _clear_approval(self) -> None:
        """Reset pending approval presentation state to safe defaults."""
        if not self._approval_pending:
            if self._approval_resolving:
                self._approval_resolving = False
                self.approvalResolvingChanged.emit(False)
            return
        self._approval_pending = False
        self._approval_resolving = False
        self._approval_task_id = ""
        self._approval_action = ""
        self._approval_description = ""
        self._approval_resource = ""
        self._approval_risk_level = ""
        self._approval_reason = ""
        self._approval_reversible = True
        self._approval_rollback_available = True

        self.approvalPendingChanged.emit(False)
        self.approvalResolvingChanged.emit(False)
        self.approvalTaskIdChanged.emit("")
        self.approvalActionChanged.emit("")
        self.approvalDescriptionChanged.emit("")
        self.approvalResourceChanged.emit("")
        self.approvalRiskLevelChanged.emit("")
        self.approvalReasonChanged.emit("")
        self.approvalReversibleChanged.emit(True)
        self.approvalRollbackAvailableChanged.emit(True)

    @Slot(str, str)
    def _on_approval_failed_internal(self, task_id: str, error: str) -> None:
        """Slot executed in Qt thread when approval resolution fails in backend."""
        self._approval_resolving = False
        self.approvalResolvingChanged.emit(False)
        self.approvalFailed.emit(task_id, error)

    def notifyApprovalFailed(self, task_id: str, error: str = "") -> None:
        """Thread-safe notification invoked when backend approval resolution fails."""
        self._approvalFailedQueued.emit(task_id, error)

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

    # ------------------------------------------------------------------
    # Lifecycle presentation projection (Phase 018-E)
    # ------------------------------------------------------------------

    @Slot(str, dict)
    def _on_lifecycle_stage_internal(self, stage: str, data: dict) -> None:
        """Slot executed in Qt thread when lifecycle stage update arrives."""
        self._apply_lifecycle_stage(stage, data)

    def _apply_lifecycle_stage(self, stage: str, data: Optional[dict] = None) -> None:
        """
        Deterministically update lifecycle projection state on Qt thread.
        Includes stale event / terminal state protection and monotonic index progression.
        """
        data = data or {}
        norm_stage = stage.upper()
        if norm_stage == "EXECUTING":
            norm_stage = "EXECUTE"
        elif norm_stage == "VERIFYING":
            norm_stage = "VERIFY"

        # Terminal protection: once terminal, ignore non-terminal stale updates
        if self._lifecycle_terminal and norm_stage not in _TERMINAL_STAGES and norm_stage != "IDLE":
            return

        idx = _STAGE_INDEX_MAP.get(norm_stage, self._lifecycle_stage_index)

        if norm_stage in _TERMINAL_STAGES:
            self._lifecycle_stage = norm_stage
            self._lifecycle_stage_index = 8
            self._lifecycle_active = False
            self._lifecycle_terminal = True
            if norm_stage == "SUCCESS":
                self._lifecycle_max_stage_index = max(self._lifecycle_max_stage_index, 7)
            if norm_stage == "ROLLED_BACK" or bool(data.get("rollback", False)):
                self._lifecycle_rollback = True
                self.lifecycleRollbackChanged.emit(True)
            self.lifecycleStageChanged.emit(norm_stage)
            self.lifecycleStageIndexChanged.emit(8)
            self.lifecycleActiveChanged.emit(False)
            return

        if norm_stage == "APPROVAL":
            self._lifecycle_approval_required = True

        # Monotonic progression: do not regress stage index during forward execution
        if idx < self._lifecycle_stage_index and norm_stage != "IDLE":
            return

        if self._lifecycle_stage == norm_stage and self._lifecycle_stage_index == idx:
            return

        self._lifecycle_stage = norm_stage
        self._lifecycle_stage_index = idx
        self._lifecycle_max_stage_index = max(self._lifecycle_max_stage_index, idx)
        self._lifecycle_active = (norm_stage != "IDLE")

        self.lifecycleStageChanged.emit(norm_stage)
        self.lifecycleStageIndexChanged.emit(idx)
        self.lifecycleActiveChanged.emit(self._lifecycle_active)

    def notifyLifecycleStage(self, stage: str, rollback: bool = False) -> None:
        """Thread-safe method called to publish lifecycle stage updates to Qt GUI."""
        self._lifecycleStageQueued.emit(stage, {"rollback": rollback})

    @Property(str, notify=lifecycleStageChanged)
    def lifecycleStage(self) -> str:
        """Current execution lifecycle stage projection."""
        return self._lifecycle_stage

    @Property(int, notify=lifecycleStageIndexChanged)
    def lifecycleStageIndex(self) -> int:
        """Numeric index of the current lifecycle stage (0=IDLE .. 8=TERMINAL)."""
        return self._lifecycle_stage_index

    @Property(int, notify=lifecycleStageIndexChanged)
    def lifecycleMaxStageIndex(self) -> int:
        """Maximum non-terminal lifecycle stage index reached."""
        return self._lifecycle_max_stage_index

    @Property(bool, notify=lifecycleActiveChanged)
    def lifecycleActive(self) -> bool:
        """Whether a task execution is actively progressing through lifecycle stages."""
        return self._lifecycle_active

    @Property(bool, notify=lifecycleRollbackChanged)
    def lifecycleRollback(self) -> bool:
        """Whether transaction rollback was performed for the current or latest task."""
        return self._lifecycle_rollback

    @Property(bool, notify=lifecycleStageChanged)
    def lifecycleApprovalRequired(self) -> bool:
        """Whether the current task encountered an approval gate."""
        return self._lifecycle_approval_required

    # ------------------------------------------------------------------
    # Task result handlers
    # ------------------------------------------------------------------

    @Slot(str)
    def submitTask(self, command: str) -> None:
        """Called by QML to submit a user task."""
        self._task_result = ""
        self._task_result_status = "RUNNING"
        self._task_result_success = False
        self._task_result_available = False
        self.taskResultChanged.emit()

        # Reset lifecycle projection for new task
        self._lifecycle_terminal = False
        self._lifecycle_rollback = False
        self._lifecycle_approval_required = False
        self._lifecycle_active = True
        self._lifecycle_stage = "THINKING"
        self._lifecycle_stage_index = 1
        self._lifecycle_max_stage_index = 1
        self.lifecycleStageChanged.emit("THINKING")
        self.lifecycleStageIndexChanged.emit(1)
        self.lifecycleActiveChanged.emit(True)
        self.lifecycleRollbackChanged.emit(False)

        self.taskSubmitted.emit(command)

    @Slot(str, str, bool)
    def _on_task_result_internal(self, result_text: str, status: str, success: bool) -> None:
        """Slot executed in Qt thread when task result arrives from a worker."""
        self._task_result = result_text
        self._task_result_status = status
        self._task_result_success = success
        self._task_result_available = (status in ("SUCCESS", "FAILED", "CANCELLED", "ROLLED_BACK"))
        self.taskResultChanged.emit()

        # Update terminal lifecycle projection based on final authoritative status
        norm_status = status.upper()
        if norm_status == "ROLLED_BACK" or (norm_status == "FAILED" and self._lifecycle_rollback):
            self._apply_lifecycle_stage("ROLLED_BACK", {"rollback": True})
        elif norm_status == "CANCELLED":
            self._apply_lifecycle_stage("CANCELLED")
        elif success or norm_status == "SUCCESS":
            self._apply_lifecycle_stage("SUCCESS")
        elif norm_status == "FAILED":
            self._apply_lifecycle_stage("FAILED")

    def notifyTaskResult(self, result_text: str, status: str = "SUCCESS", success: bool = True) -> None:
        """Thread-safe method called by workers to publish task results to Qt GUI."""
        self._taskResultQueued.emit(result_text, status, success)

    @Slot()
    def clearTaskResult(self) -> None:
        """Restore task result state to IDLE defaults."""
        self._task_result = ""
        self._task_result_status = "IDLE"
        self._task_result_success = False
        self._task_result_available = False
        self.taskResultChanged.emit()

        # Reset lifecycle projection to IDLE
        self._lifecycle_stage = "IDLE"
        self._lifecycle_stage_index = 0
        self._lifecycle_max_stage_index = 0
        self._lifecycle_active = False
        self._lifecycle_rollback = False
        self._lifecycle_terminal = False
        self._lifecycle_approval_required = False
        self.lifecycleStageChanged.emit("IDLE")
        self.lifecycleStageIndexChanged.emit(0)
        self.lifecycleActiveChanged.emit(False)
        self.lifecycleRollbackChanged.emit(False)

    @Property(str, notify=taskResultChanged)
    def taskResult(self) -> str:
        """Human-readable result or response text of the latest task execution."""
        return self._task_result

    @Property(str, notify=taskResultChanged)
    def taskResultStatus(self) -> str:
        """Lifecycle status of the latest task ('IDLE', 'RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED', 'ROLLED_BACK')."""
        return self._task_result_status

    @Property(bool, notify=taskResultChanged)
    def taskResultSuccess(self) -> bool:
        """Whether the latest task finished with overall success."""
        return self._task_result_success

    @Property(bool, notify=taskResultChanged)
    def taskResultAvailable(self) -> bool:
        """Whether a completed task result is ready to display."""
        return self._task_result_available

    @Slot(str, bool)
    def submitApproval(self, task_id: str, approved: bool) -> None:
        """Called by QML or tests to submit user approval or denial."""
        # Enforce active approval binding: reject mismatched task ID if approval is currently pending
        if self._approval_pending and self._approval_task_id and task_id != self._approval_task_id:
            logger.warning(
                "GuiBridge.submitApproval rejected mismatched task_id: expected '%s', got '%s'",
                self._approval_task_id,
                task_id,
            )
            return

        self._approval_resolving = True
        self.approvalResolvingChanged.emit(True)

        if approved:
            self._lifecycleStageQueued.emit("EXECUTE", {})
        else:
            self._lifecycleStageQueued.emit("CANCELLED", {})

        self._clear_approval()
        self.approvalSubmitted.emit(task_id, approved)
        self.approvalResolved.emit(task_id, approved)

    # ------------------------------------------------------------------
    # Read-only approval presentation properties (Contract Step 4)
    # ------------------------------------------------------------------

    @Property(bool, notify=approvalPendingChanged)
    def approvalPending(self) -> bool:
        """Whether an action or plan is currently awaiting user approval."""
        return self._approval_pending

    @Property(bool, notify=approvalResolvingChanged)
    def approvalResolving(self) -> bool:
        """Whether human approval decision is currently resolving with backend."""
        return self._approval_resolving

    @Property(str, notify=approvalTaskIdChanged)
    def approvalTaskId(self) -> str:
        """Identifier of the task or plan awaiting approval."""
        return self._approval_task_id

    @Property(str, notify=approvalTaskIdChanged)
    def approvalPlanId(self) -> str:
        """Identifier of the plan awaiting approval (alias for approvalTaskId)."""
        return self._approval_task_id

    @Property(str, notify=approvalActionChanged)
    def approvalAction(self) -> str:
        """The action requiring approval."""
        return self._approval_action

    @Property(str, notify=approvalDescriptionChanged)
    def approvalDescription(self) -> str:
        """Human-readable description of the action or plan goal."""
        return self._approval_description

    @Property(str, notify=approvalResourceChanged)
    def approvalResource(self) -> str:
        """Target resource or path affected by the action."""
        return self._approval_resource

    @Property(str, notify=approvalRiskLevelChanged)
    def approvalRiskLevel(self) -> str:
        """Risk level assessed by EVRiskEngine (e.g. LOW, MEDIUM, HIGH, CRITICAL)."""
        return self._approval_risk_level

    @Property(str, notify=approvalReasonChanged)
    def approvalReason(self) -> str:
        """Security reason explaining why approval is required."""
        return self._approval_reason

    @Property(bool, notify=approvalReversibleChanged)
    def approvalReversible(self) -> bool:
        """Whether the action is reversible."""
        return self._approval_reversible

    @Property(bool, notify=approvalRollbackAvailableChanged)
    def approvalRollbackAvailable(self) -> bool:
        """Whether transaction rollback is available if execution fails."""
        return self._approval_rollback_available

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

    @Slot(str, str, str, str)
    def _on_awareness_event_internal(self, aid: str, title: str, message: str, severity: str) -> None:
        self._latest_awareness_title = title
        self._latest_awareness_message = message
        self._latest_awareness_severity = severity
        self.latestAwarenessTitleChanged.emit(title)
        self.latestAwarenessMessageChanged.emit(message)
        self.latestAwarenessSeverityChanged.emit(severity)
        self.awarenessEventChanged.emit(aid, title, message)

    @Property(str, notify=latestAwarenessTitleChanged)
    def latestAwarenessTitle(self) -> str:
        """Latest proactive awareness title for QML binding."""
        return self._latest_awareness_title

    @Property(str, notify=latestAwarenessMessageChanged)
    def latestAwarenessMessage(self) -> str:
        """Latest proactive awareness message for QML binding."""
        return self._latest_awareness_message

    @Property(str, notify=latestAwarenessSeverityChanged)
    def latestAwarenessSeverity(self) -> str:
        """Latest proactive awareness severity ('INFO', 'NOTICE', 'WARNING', 'CRITICAL') for QML binding."""
        return self._latest_awareness_severity

    @Slot()
    def clearAwareness(self) -> None:
        """Clear GUI awareness presentation state only (presentation-only, no backend impact)."""
        if not self._latest_awareness_title and not self._latest_awareness_message and not self._system_alert_message:
            return
        self._latest_awareness_title = ""
        self._latest_awareness_message = ""
        self._latest_awareness_severity = "INFO"
        self._system_alert_message = ""
        self.latestAwarenessTitleChanged.emit("")
        self.latestAwarenessMessageChanged.emit("")
        self.latestAwarenessSeverityChanged.emit("INFO")
        self.systemAlertChanged.emit("")

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

    # ------------------------------------------------------------------
    # Telemetry presentation contract (Task 018-B)
    # ------------------------------------------------------------------

    def _parse_telemetry_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize, parse, and bound observational telemetry dictionary.
        Accepts backend snapshot dict, metrics mapping, or direct properties.
        """
        snapshot = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else {}
        metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}

        # 1. CPU Percent
        cpu_pct = (
            snapshot.get("cpu_percent")
            or metrics.get("cpu:utilization")
            or data.get("cpu_percent")
            or 0.0
        )
        try:
            cpu_pct = max(0.0, min(100.0, float(cpu_pct)))
        except (ValueError, TypeError):
            cpu_pct = 0.0

        # 2. Memory Percent & Byte counts
        mem_pct = (
            snapshot.get("memory_used_percent")
            or metrics.get("memory:used_percent")
            or data.get("memory_used_percent")
            or data.get("memory_percent")
            or 0.0
        )
        try:
            mem_pct = max(0.0, min(100.0, float(mem_pct)))
        except (ValueError, TypeError):
            mem_pct = 0.0

        total_bytes = snapshot.get("memory_total_bytes") or data.get("memory_total_bytes") or 0
        avail_bytes = snapshot.get("memory_available_bytes") or data.get("memory_available_bytes") or 0
        try:
            total_bytes = int(total_bytes)
            avail_bytes = int(avail_bytes)
        except (ValueError, TypeError):
            total_bytes = 0
            avail_bytes = 0

        total_mb = int(data.get("memory_total_mb", 0) or data.get("memoryTotalMb", 0))
        if not total_mb and total_bytes > 0:
            total_mb = int(round(total_bytes / (1024 * 1024)))

        used_mb = int(data.get("memory_used_mb", 0) or data.get("memoryUsedMb", 0))
        if not used_mb:
            if total_bytes > 0 and avail_bytes > 0:
                used_mb = int(round((total_bytes - avail_bytes) / (1024 * 1024)))
            elif total_mb > 0 and mem_pct > 0:
                used_mb = int(round(total_mb * (mem_pct / 100.0)))

        # 3. Disk Free Percent & Free GB
        disk_pct = (
            snapshot.get("disk_free_percent")
            or metrics.get("disk:free_percent")
            or data.get("disk_free_percent")
            or 0.0
        )
        try:
            disk_pct = max(0.0, min(100.0, float(disk_pct)))
        except (ValueError, TypeError):
            disk_pct = 0.0

        disk_free_gb = snapshot.get("disk_free_gb") or data.get("disk_free_gb") or data.get("diskFreeGb") or 0.0
        if not disk_free_gb:
            df_bytes = snapshot.get("disk_free_bytes") or data.get("disk_free_bytes") or 0
            try:
                disk_free_gb = round(float(df_bytes) / (1024**3), 2)
            except (ValueError, TypeError):
                disk_free_gb = 0.0
        else:
            try:
                disk_free_gb = round(float(disk_free_gb), 2)
            except (ValueError, TypeError):
                disk_free_gb = 0.0

        # 4. Process Count
        proc_count = (
            snapshot.get("process_count")
            or metrics.get("process:aggregate_processes")
            or data.get("process_count")
            or 0
        )
        try:
            proc_count = max(0, int(proc_count))
        except (ValueError, TypeError):
            proc_count = 0

        # 5. Top Process Name, CPU%, Memory MB
        top_name = snapshot.get("top_cpu_process") or data.get("top_process_name") or data.get("topProcessName") or ""
        top_cpu = snapshot.get("top_cpu_percent") or data.get("top_process_cpu_percent") or data.get("topProcessCpuPercent") or 0.0
        top_mem_mb = int(data.get("top_process_memory_mb", 0) or data.get("topProcessMemoryMb", 0))

        top_cpu_list = snapshot.get("top_cpu_list") or data.get("top_cpu_list") or []
        if isinstance(top_cpu_list, list) and top_cpu_list:
            first_proc = top_cpu_list[0]
            if isinstance(first_proc, dict):
                if not top_name or top_name == "None":
                    top_name = str(first_proc.get("name") or "")
                if not top_cpu:
                    top_cpu = float(first_proc.get("cpu_percent") or 0.0)
                if not top_mem_mb and total_mb > 0:
                    mem_p = float(first_proc.get("memory_percent") or 0.0)
                    top_mem_mb = int(round(total_mb * (mem_p / 100.0)))

        top_mem_list = snapshot.get("top_mem_list") or data.get("top_mem_list") or []
        if not top_mem_mb and isinstance(top_mem_list, list) and top_mem_list:
            first_mem = top_mem_list[0]
            if isinstance(first_mem, dict) and total_mb > 0:
                mem_p = float(first_mem.get("memory_percent") or 0.0)
                top_mem_mb = int(round(total_mb * (mem_p / 100.0)))

        try:
            top_cpu = max(0.0, float(top_cpu))
        except (ValueError, TypeError):
            top_cpu = 0.0

        if top_name == "None":
            top_name = ""

        # 6. Network Connected
        net_conn = snapshot.get("network_connected")
        if net_conn is None:
            net_conn = metrics.get("network:link_status")
        if net_conn is None:
            net_conn = data.get("network_connected", False)
        net_conn = bool(net_conn)

        return {
            "cpu_percent": round(cpu_pct, 1),
            "memory_percent": round(mem_pct, 1),
            "memory_used_mb": used_mb,
            "memory_total_mb": total_mb,
            "disk_free_percent": round(disk_pct, 1),
            "disk_free_gb": disk_free_gb,
            "process_count": proc_count,
            "top_process_name": top_name,
            "top_process_cpu_percent": round(top_cpu, 1),
            "top_process_memory_mb": top_mem_mb,
            "network_connected": net_conn,
        }

    @Slot(dict)
    def _on_telemetry_updated_internal(self, payload: dict) -> None:
        """Slot executed in Qt thread when telemetry observation arrives."""
        is_initial = not self._telemetry_available
        self._telemetry_available = True

        ts = payload.get("timestamp")
        if isinstance(ts, datetime):
            self._telemetry_timestamp = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        elif isinstance(ts, str):
            try:
                self._telemetry_timestamp = datetime.fromisoformat(ts)
            except Exception:
                self._telemetry_timestamp = datetime.now(timezone.utc)
        elif "age_ms" in payload:
            try:
                age_s = max(0.0, float(payload["age_ms"]) / 1000.0)
                self._telemetry_timestamp = datetime.now(timezone.utc) - timedelta(seconds=age_s)
            except Exception:
                self._telemetry_timestamp = datetime.now(timezone.utc)
        else:
            self._telemetry_timestamp = datetime.now(timezone.utc)

        new_cpu = float(payload.get("cpu_percent", 0.0))
        new_mem = float(payload.get("memory_percent", 0.0))
        new_used_mb = int(payload.get("memory_used_mb", 0))
        new_total_mb = int(payload.get("memory_total_mb", 0))
        new_disk_pct = float(payload.get("disk_free_percent", 0.0))
        new_disk_gb = float(payload.get("disk_free_gb", 0.0))
        new_proc_count = int(payload.get("process_count", 0))
        new_top_name = str(payload.get("top_process_name", ""))
        new_top_cpu = float(payload.get("top_process_cpu_percent", 0.0))
        new_top_mem = int(payload.get("top_process_memory_mb", 0))
        new_net = bool(payload.get("network_connected", False))

        if is_initial:
            self.telemetryAvailableChanged.emit(True)

        if is_initial or self._telemetry_cpu_percent != new_cpu:
            self._telemetry_cpu_percent = new_cpu
            self.telemetryCpuPercentChanged.emit(new_cpu)

        if is_initial or self._telemetry_memory_percent != new_mem:
            self._telemetry_memory_percent = new_mem
            self.telemetryMemoryPercentChanged.emit(new_mem)

        if is_initial or self._telemetry_memory_used_mb != new_used_mb:
            self._telemetry_memory_used_mb = new_used_mb
            self.telemetryMemoryUsedMbChanged.emit(new_used_mb)

        if is_initial or self._telemetry_memory_total_mb != new_total_mb:
            self._telemetry_memory_total_mb = new_total_mb
            self.telemetryMemoryTotalMbChanged.emit(new_total_mb)

        if is_initial or self._telemetry_disk_free_percent != new_disk_pct:
            self._telemetry_disk_free_percent = new_disk_pct
            self.telemetryDiskFreePercentChanged.emit(new_disk_pct)

        if is_initial or self._telemetry_disk_free_gb != new_disk_gb:
            self._telemetry_disk_free_gb = new_disk_gb
            self.telemetryDiskFreeGbChanged.emit(new_disk_gb)

        if is_initial or self._telemetry_process_count != new_proc_count:
            self._telemetry_process_count = new_proc_count
            self.telemetryProcessCountChanged.emit(new_proc_count)

        if is_initial or self._telemetry_top_process_name != new_top_name:
            self._telemetry_top_process_name = new_top_name
            self.telemetryTopProcessNameChanged.emit(new_top_name)

        if is_initial or self._telemetry_top_process_cpu_percent != new_top_cpu:
            self._telemetry_top_process_cpu_percent = new_top_cpu
            self.telemetryTopProcessCpuPercentChanged.emit(new_top_cpu)

        if is_initial or self._telemetry_top_process_memory_mb != new_top_mem:
            self._telemetry_top_process_memory_mb = new_top_mem
            self.telemetryTopProcessMemoryMbChanged.emit(new_top_mem)

        if is_initial or self._telemetry_network_connected != new_net:
            self._telemetry_network_connected = new_net
            self.telemetryNetworkConnectedChanged.emit(new_net)

        self.telemetryUpdated.emit()

    @Slot()
    def clearTelemetry(self) -> None:
        """Reset telemetry state to unmeasured/unavailable defaults."""
        if not self._telemetry_available:
            return
        self._telemetry_available = False
        self._telemetry_timestamp = None
        self._telemetry_cpu_percent = 0.0
        self._telemetry_memory_percent = 0.0
        self._telemetry_memory_used_mb = 0
        self._telemetry_memory_total_mb = 0
        self._telemetry_disk_free_percent = 0.0
        self._telemetry_disk_free_gb = 0.0
        self._telemetry_process_count = 0
        self._telemetry_top_process_name = ""
        self._telemetry_top_process_cpu_percent = 0.0
        self._telemetry_top_process_memory_mb = 0
        self._telemetry_network_connected = False

        self.telemetryAvailableChanged.emit(False)
        self.telemetryCpuPercentChanged.emit(0.0)
        self.telemetryMemoryPercentChanged.emit(0.0)
        self.telemetryMemoryUsedMbChanged.emit(0)
        self.telemetryMemoryTotalMbChanged.emit(0)
        self.telemetryDiskFreePercentChanged.emit(0.0)
        self.telemetryDiskFreeGbChanged.emit(0.0)
        self.telemetryProcessCountChanged.emit(0)
        self.telemetryTopProcessNameChanged.emit("")
        self.telemetryTopProcessCpuPercentChanged.emit(0.0)
        self.telemetryTopProcessMemoryMbChanged.emit(0)
        self.telemetryNetworkConnectedChanged.emit(False)
        self.telemetryUpdated.emit()

    @Property(bool, notify=telemetryAvailableChanged)
    def telemetryAvailable(self) -> bool:
        """Whether valid system telemetry has been received from the backend."""
        return self._telemetry_available

    @Property(str, notify=telemetryUpdated)
    def telemetryTimestamp(self) -> str:
        """ISO 8601 timestamp string of the latest telemetry sample, or empty if none."""
        if self._telemetry_timestamp is None:
            return ""
        return self._telemetry_timestamp.isoformat()

    @Property(int, notify=telemetryUpdated)
    def telemetryAgeMs(self) -> int:
        """Age in milliseconds of the latest telemetry observation, or -1 if unavailable."""
        if self._telemetry_timestamp is None:
            return -1
        delta = datetime.now(timezone.utc) - self._telemetry_timestamp
        return max(0, int(delta.total_seconds() * 1000))

    @Property(float, notify=telemetryCpuPercentChanged)
    def telemetryCpuPercent(self) -> float:
        """Current total CPU utilization percentage (0.0 - 100.0)."""
        return self._telemetry_cpu_percent

    @Property(float, notify=telemetryMemoryPercentChanged)
    def telemetryMemoryPercent(self) -> float:
        """Current virtual memory utilization percentage (0.0 - 100.0)."""
        return self._telemetry_memory_percent

    @Property(int, notify=telemetryMemoryUsedMbChanged)
    def telemetryMemoryUsedMb(self) -> int:
        """Current virtual memory used in megabytes."""
        return self._telemetry_memory_used_mb

    @Property(int, notify=telemetryMemoryTotalMbChanged)
    def telemetryMemoryTotalMb(self) -> int:
        """Total system virtual memory in megabytes."""
        return self._telemetry_memory_total_mb

    @Property(float, notify=telemetryDiskFreePercentChanged)
    def telemetryDiskFreePercent(self) -> float:
        """Free space percentage on primary volume (0.0 - 100.0)."""
        return self._telemetry_disk_free_percent

    @Property(float, notify=telemetryDiskFreeGbChanged)
    def telemetryDiskFreeGb(self) -> float:
        """Free space on primary volume in gigabytes."""
        return self._telemetry_disk_free_gb

    @Property(int, notify=telemetryProcessCountChanged)
    def telemetryProcessCount(self) -> int:
        """Total count of running system processes."""
        return self._telemetry_process_count

    @Property(str, notify=telemetryTopProcessNameChanged)
    def telemetryTopProcessName(self) -> str:
        """Name of the top CPU consuming process, or empty string."""
        return self._telemetry_top_process_name

    @Property(float, notify=telemetryTopProcessCpuPercentChanged)
    def telemetryTopProcessCpuPercent(self) -> float:
        """CPU utilization percentage of the top process."""
        return self._telemetry_top_process_cpu_percent

    @Property(int, notify=telemetryTopProcessMemoryMbChanged)
    def telemetryTopProcessMemoryMb(self) -> int:
        """Memory utilization in megabytes of the top process."""
        return self._telemetry_top_process_memory_mb

    @Property(bool, notify=telemetryNetworkConnectedChanged)
    def telemetryNetworkConnected(self) -> bool:
        """Whether an active network link/adapter is detected."""
        return self._telemetry_network_connected

    def shutdown(self) -> None:
        """Unsubscribe from the event bus. Idempotent."""
        self.clearTaskResult()
        self.clearTelemetry()
        self.clearAwareness()
        for token in self._subscription_tokens:
            self._event_bus.unsubscribe(token)
        self._subscription_tokens.clear()