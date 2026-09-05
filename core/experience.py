# E.V. Experience Mode & Core Visual Preset Foundation
#
# Four independent dimensions:
#   1. Experience Mode   — WHAT context E.V. is in
#   2. Visual Preset     — HOW E.V. looks
#   3. Operational State — WHAT E.V. is doing  (EVState, managed elsewhere)
#   4. Autonomy Level    — HOW MUCH authority   (risk engine, managed elsewhere)
#
# Experience mode is NOT the same as autonomy level. They are orthogonal.
# The GUI is a presentation layer, NOT an execution authority.

import logging
import threading
from enum import Enum
from typing import Dict, Optional

from core.events import EVEventBus
from core.models import EVEventSeverity, EVEventType

logger = logging.getLogger(__name__)


class EVExperienceMode(str, Enum):
    """Context mode that describes WHAT E.V. is contextually focused on."""

    STANDARD = "STANDARD"
    AI = "AI"
    WORK = "WORK"
    MUSIC = "MUSIC"
    SYSTEM = "SYSTEM"
    APPROVAL = "APPROVAL"
    SLEEP = "SLEEP"


class EVCoreStylePreset(str, Enum):
    """Visual style preset that describes HOW E.V. presents itself."""

    EV_CORE = "EV_CORE"
    MINIMAL = "MINIMAL"
    AMBIENT = "AMBIENT"
    FOCUSED = "FOCUSED"
    ALERT = "ALERT"


EXPERIENCE_MODE_DESCRIPTIONS: Dict[EVExperienceMode, str] = {
    EVExperienceMode.STANDARD: "Default experience — general-purpose assistant",
    EVExperienceMode.AI: "AI-focused — model interaction and inference context",
    EVExperienceMode.WORK: "Work-focused — productivity and task management",
    EVExperienceMode.MUSIC: "Music — ambient audio and media context",
    EVExperienceMode.SYSTEM: "System — hardware monitoring and diagnostics",
    EVExperienceMode.APPROVAL: "Approval — pending user decision on risky action",
    EVExperienceMode.SLEEP: "Sleep — low-power ambient observation",
}

STYLE_PRESET_DESCRIPTIONS: Dict[EVCoreStylePreset, str] = {
    EVCoreStylePreset.EV_CORE: "Flagship E.V. visual identity — full detail",
    EVCoreStylePreset.MINIMAL: "Reduced visual density — clean and quiet",
    EVCoreStylePreset.AMBIENT: "Atmospheric — soft gradients, low contrast",
    EVCoreStylePreset.FOCUSED: "High contrast — sharp edges, bright accents",
    EVCoreStylePreset.ALERT: "Alert state — elevated urgency, warm tones",
}


class EVExperienceManager:
    """
    Manages the current experience mode and visual style preset.

    Thread-safe. Mode/preset transitions emit structured EVEvent
    notifications on EVEventBus.  This class has ZERO execution authority —
    it only manages presentation-layer state.
    """

    def __init__(
        self,
        event_bus: EVEventBus,
        initial_mode: EVExperienceMode = EVExperienceMode.STANDARD,
        initial_preset: EVCoreStylePreset = EVCoreStylePreset.EV_CORE,
    ) -> None:
        self._event_bus = event_bus
        self._mode: EVExperienceMode = initial_mode
        self._preset: EVCoreStylePreset = initial_preset
        self._lock = threading.Lock()

        logger.info(
            "EVExperienceManager initialized: mode=%s, preset=%s",
            self._mode.value,
            self._preset.value,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_mode(self) -> EVExperienceMode:
        """Current experience mode (read-only)."""
        with self._lock:
            return self._mode

    @property
    def current_preset(self) -> EVCoreStylePreset:
        """Current visual style preset (read-only)."""
        with self._lock:
            return self._preset

    # ------------------------------------------------------------------
    # Mode transitions
    # ------------------------------------------------------------------

    def set_mode(self, mode: EVExperienceMode) -> None:
        """
        Transition to a new experience mode.

        Validates the mode, emits EXPERIENCE_MODE_CHANGED, and logs the
        transition.  No-op if already in the requested mode.

        Args:
            mode: The target EVExperienceMode.

        Raises:
            ValueError: If mode is not a valid EVExperienceMode.
        """
        if not isinstance(mode, EVExperienceMode):
            # Attempt coercion from string
            try:
                mode = EVExperienceMode(mode)
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Invalid experience mode: {mode!r}. "
                    f"Valid modes: {[m.value for m in EVExperienceMode]}"
                ) from exc

        with self._lock:
            previous = self._mode
            if previous == mode:
                return
            self._mode = mode

        logger.info(
            "Experience mode transition: %s → %s",
            previous.value,
            mode.value,
        )

        self._event_bus.publish(
            EVEventType.EXPERIENCE_MODE_CHANGED,
            "experience_manager",
            severity=EVEventSeverity.INFO,
            message=f"Experience mode changed: {previous.value} → {mode.value}",
            data={
                "previous_mode": previous.value,
                "current_mode": mode.value,
                "description": EXPERIENCE_MODE_DESCRIPTIONS.get(mode, ""),
            },
        )

    def set_style_preset(self, preset: EVCoreStylePreset) -> None:
        """
        Transition to a new visual style preset.

        Validates the preset, emits STYLE_PRESET_CHANGED, and logs the
        transition.  No-op if already using the requested preset.

        Args:
            preset: The target EVCoreStylePreset.

        Raises:
            ValueError: If preset is not a valid EVCoreStylePreset.
        """
        if not isinstance(preset, EVCoreStylePreset):
            try:
                preset = EVCoreStylePreset(preset)
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Invalid style preset: {preset!r}. "
                    f"Valid presets: {[p.value for p in EVCoreStylePreset]}"
                ) from exc

        with self._lock:
            previous = self._preset
            if previous == preset:
                return
            self._preset = preset

        logger.info(
            "Style preset transition: %s → %s",
            previous.value,
            preset.value,
        )

        self._event_bus.publish(
            EVEventType.STYLE_PRESET_CHANGED,
            "experience_manager",
            severity=EVEventSeverity.INFO,
            message=f"Style preset changed: {previous.value} → {preset.value}",
            data={
                "previous_preset": previous.value,
                "current_preset": preset.value,
                "description": STYLE_PRESET_DESCRIPTIONS.get(preset, ""),
            },
        )

    # ------------------------------------------------------------------
    # Description accessors
    # ------------------------------------------------------------------

    @staticmethod
    def get_mode_description(mode: EVExperienceMode) -> str:
        """Return a human-readable description for an experience mode."""
        if isinstance(mode, str):
            try:
                mode = EVExperienceMode(mode)
            except (ValueError, KeyError):
                return "Unknown mode"
        return EXPERIENCE_MODE_DESCRIPTIONS.get(mode, "Unknown mode")

    @staticmethod
    def get_preset_description(preset: EVCoreStylePreset) -> str:
        """Return a human-readable description for a visual preset."""
        if isinstance(preset, str):
            try:
                preset = EVCoreStylePreset(preset)
            except (ValueError, KeyError):
                return "Unknown preset"
        return STYLE_PRESET_DESCRIPTIONS.get(preset, "Unknown preset")
