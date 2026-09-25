"""Presentation-only visual state controller for the E.V. intelligence core."""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Mapping, Optional

from PySide6.QtCore import QElapsedTimer, QObject, QTimer, Signal


class EVVisualState(str, Enum):
    IDLE = "IDLE"
    AWARE = "AWARE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SLEEP = "SLEEP"


_PROFILES: Dict[EVVisualState, Dict[str, Any]] = {
    EVVisualState.IDLE: {"energy": 0.12, "motion": 0.16, "particles": 0.12, "nucleus": 0.18, "filaments": 0.14, "camera": 0.04, "lighting": 0.12, "transitionInMs": 700, "transitionOutMs": 900, "animationEnabled": True},
    EVVisualState.AWARE: {"energy": 0.24, "motion": 0.26, "particles": 0.20, "nucleus": 0.30, "filaments": 0.28, "camera": 0.08, "lighting": 0.22, "transitionInMs": 420, "transitionOutMs": 650, "animationEnabled": True},
    EVVisualState.LISTENING: {"energy": 0.38, "motion": 0.34, "particles": 0.30, "nucleus": 0.44, "filaments": 0.48, "camera": 0.12, "lighting": 0.36, "transitionInMs": 260, "transitionOutMs": 480, "animationEnabled": True},
    EVVisualState.THINKING: {"energy": 0.48, "motion": 0.44, "particles": 0.36, "nucleus": 0.60, "filaments": 0.58, "camera": 0.14, "lighting": 0.44, "transitionInMs": 380, "transitionOutMs": 520, "animationEnabled": True},
    EVVisualState.PROCESSING: {"energy": 0.62, "motion": 0.60, "particles": 0.54, "nucleus": 0.70, "filaments": 0.72, "camera": 0.18, "lighting": 0.60, "transitionInMs": 340, "transitionOutMs": 460, "animationEnabled": True},
    EVVisualState.SPEAKING: {"energy": 0.58, "motion": 0.50, "particles": 0.42, "nucleus": 0.70, "filaments": 0.62, "camera": 0.12, "lighting": 0.58, "transitionInMs": 240, "transitionOutMs": 450, "animationEnabled": True},
    EVVisualState.EXECUTING: {"energy": 0.82, "motion": 0.78, "particles": 0.68, "nucleus": 0.88, "filaments": 0.86, "camera": 0.24, "lighting": 0.80, "transitionInMs": 220, "transitionOutMs": 420, "animationEnabled": True},
    EVVisualState.VERIFYING: {"energy": 0.66, "motion": 0.52, "particles": 0.48, "nucleus": 0.72, "filaments": 0.68, "camera": 0.16, "lighting": 0.64, "transitionInMs": 300, "transitionOutMs": 440, "animationEnabled": True},
    EVVisualState.WAITING_FOR_APPROVAL: {"energy": 0.42, "motion": 0.18, "particles": 0.20, "nucleus": 0.52, "filaments": 0.32, "camera": 0.10, "lighting": 0.46, "transitionInMs": 380, "transitionOutMs": 380, "animationEnabled": True},
    EVVisualState.SUCCESS: {"energy": 0.40, "motion": 0.30, "particles": 0.32, "nucleus": 0.54, "filaments": 0.38, "camera": 0.08, "lighting": 0.40, "transitionInMs": 250, "transitionOutMs": 720, "animationEnabled": True},
    EVVisualState.WARNING: {"energy": 0.46, "motion": 0.28, "particles": 0.26, "nucleus": 0.48, "filaments": 0.34, "camera": 0.08, "lighting": 0.48, "transitionInMs": 300, "transitionOutMs": 600, "animationEnabled": True},
    EVVisualState.ERROR: {"energy": 0.54, "motion": 0.24, "particles": 0.20, "nucleus": 0.58, "filaments": 0.28, "camera": 0.06, "lighting": 0.56, "transitionInMs": 220, "transitionOutMs": 700, "animationEnabled": True},
    EVVisualState.SLEEP: {"energy": 0.03, "motion": 0.0, "particles": 0.02, "nucleus": 0.08, "filaments": 0.0, "camera": 0.0, "lighting": 0.04, "transitionInMs": 900, "transitionOutMs": 700, "animationEnabled": False},
}


class VisualStateController(QObject):
    """Maps observed presentation events to renderer-neutral visual state."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = EVVisualState.IDLE
        self._previous_state = EVVisualState.IDLE
        self._last_event = "INITIALIZED"
        self._transition_progress = 1.0
        self._simulation_active = False
        self._transition_clock = QElapsedTimer()
        self._transition_timer = QTimer(self)
        self._transition_timer.setInterval(16)
        self._transition_timer.timeout.connect(self._advance_transition)

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def previous_state(self) -> str:
        return self._previous_state.value

    @property
    def profile(self) -> Dict[str, Any]:
        return deepcopy(_PROFILES[self._state])

    @property
    def transition_progress(self) -> float:
        return self._transition_progress

    @property
    def animation_enabled(self) -> bool:
        return bool(_PROFILES[self._state]["animationEnabled"])

    @property
    def last_event(self) -> str:
        return self._last_event

    @property
    def simulation_active(self) -> bool:
        return self._simulation_active

    def set_state_for_simulation(self, state: str) -> None:
        self._simulation_active = True
        self._set_state(self._parse_state(state), "SIMULATION_STATE")

    def inject_voice_signal(self, *, activity: bool = False, speaking: bool = False) -> None:
        self._simulation_active = True
        if speaking:
            self._set_state(EVVisualState.SPEAKING, "SIMULATION_VOICE_SPEAKING")
        elif activity:
            self._set_state(EVVisualState.LISTENING, "SIMULATION_VOICE_LISTENING")
        else:
            self._set_state(EVVisualState.AWARE, "SIMULATION_VOICE_IDLE")

    def inject_action_event(self, event: str) -> None:
        self._simulation_active = True
        self._observe_event(str(event).upper(), {})
        self._last_event = f"SIMULATION_ACTION:{str(event).upper()}"
        self.changed.emit()

    def inject_execution_event(self, event: str) -> None:
        self._simulation_active = True
        self._observe_event(str(event).upper(), {})
        self._last_event = f"SIMULATION_EXECUTION:{str(event).upper()}"
        self.changed.emit()

    def inject_approval_event(self, pending: bool) -> None:
        self._simulation_active = True
        self._set_state(
            EVVisualState.WAITING_FOR_APPROVAL if pending else EVVisualState.WARNING,
            "SIMULATION_APPROVAL_PENDING" if pending else "SIMULATION_APPROVAL_CLEARED",
        )

    def clear_simulation(self) -> None:
        if not self._simulation_active:
            return
        self._simulation_active = False
        self._set_state(EVVisualState.IDLE, "SIMULATION_CLEARED")

    def advance_transition(self, progress: float) -> None:
        bounded = max(0.0, min(1.0, float(progress)))
        self._transition_timer.stop()
        if self._transition_progress == bounded:
            return
        self._transition_progress = bounded
        self.changed.emit()

    def observe_event(self, event_type: str, data: Optional[Mapping[str, Any]] = None, state: Optional[str] = None) -> None:
        if self._simulation_active:
            return
        event = str(event_type).upper()
        payload = dict(data or {})
        if event == "STATE_CHANGED" and state:
            self._map_backend_state(str(state))
            return
        self._observe_event(event, payload)

    def _observe_event(self, event: str, data: Mapping[str, Any]) -> None:
        if event == "VOICE_STATE_CHANGED":
            self._map_voice_state(str(data.get("voice_state", "")))
        elif event in ("APPROVAL_REQUIRED",):
            self._set_state(EVVisualState.WAITING_FOR_APPROVAL, event)
        elif event in ("ACTION_STARTED", "PLAN_STARTED"):
            self._set_state(EVVisualState.EXECUTING, event)
        elif event == "ACTION_VERIFYING":
            self._set_state(EVVisualState.VERIFYING, event)
        elif event in ("PLAN_CREATED",):
            self._set_state(EVVisualState.THINKING, event)
        elif event in ("PLAN_VALIDATED",):
            self._set_state(EVVisualState.PROCESSING, event)
        elif event in ("PLAN_COMPLETED",):
            self._set_state(EVVisualState.SUCCESS, event)
        elif event in ("PLAN_FAILED",):
            self._set_state(EVVisualState.ERROR, event)
        elif event in ("PLAN_CANCELLED", "PLAN_ROLLED_BACK", "SYSTEM_ALERT"):
            self._set_state(EVVisualState.WARNING, event)
        elif event == "SYSTEM_ALERT_RECOVERED":
            self._set_state(EVVisualState.AWARE, event)

    def _map_backend_state(self, state: str) -> None:
        mapping = {
            "IDLE": EVVisualState.IDLE,
            "VERIFYING_WAKE": EVVisualState.AWARE,
            "LISTENING": EVVisualState.LISTENING,
            "TRANSCRIBING": EVVisualState.THINKING,
            "PROCESSING": EVVisualState.PROCESSING,
            "PLANNING": EVVisualState.THINKING,
            "AWAITING_APPROVAL": EVVisualState.WAITING_FOR_APPROVAL,
            "EXECUTING": EVVisualState.EXECUTING,
            "VERIFYING": EVVisualState.VERIFYING,
            "RECOVERING": EVVisualState.WARNING,
            "SPEAKING": EVVisualState.SPEAKING,
            "SUCCESS": EVVisualState.SUCCESS,
            "FAILED": EVVisualState.ERROR,
            "STOPPED": EVVisualState.SLEEP,
        }
        mapped = mapping.get(state.upper())
        if mapped is not None:
            self._set_state(mapped, f"STATE_CHANGED:{state.upper()}")

    def _map_voice_state(self, state: str) -> None:
        mapping = {
            "IDLE": EVVisualState.IDLE,
            "VERIFYING_WAKE": EVVisualState.AWARE,
            "LISTENING": EVVisualState.LISTENING,
            "TRANSCRIBING": EVVisualState.THINKING,
            "PROCESSING": EVVisualState.PROCESSING,
            "SPEAKING": EVVisualState.SPEAKING,
            "PAUSED": EVVisualState.SLEEP,
            "ERROR": EVVisualState.ERROR,
        }
        mapped = mapping.get(state.upper())
        if mapped is not None:
            self._set_state(mapped, f"VOICE_STATE_CHANGED:{state.upper()}")

    def _set_state(self, state: EVVisualState, event: str) -> None:
        changed = self._state != state
        if changed:
            self._previous_state = self._state
            self._state = state
            self._transition_progress = 0.0
            self._transition_clock.restart()
            self._transition_timer.start()
        self._last_event = event
        self.changed.emit()

    def _advance_transition(self) -> None:
        duration = max(1, int(_PROFILES[self._state]["transitionInMs"]))
        progress = min(1.0, self._transition_clock.elapsed() / duration)
        if progress == self._transition_progress:
            return
        self._transition_progress = progress
        if progress >= 1.0:
            self._transition_timer.stop()
        self.changed.emit()

    @staticmethod
    def _parse_state(state: str) -> EVVisualState:
        try:
            return EVVisualState(str(state).upper())
        except ValueError as exc:
            raise ValueError(f"Unsupported visual state: {state}") from exc
