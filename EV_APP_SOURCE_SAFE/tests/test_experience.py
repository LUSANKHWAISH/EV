"""Tests for E.V. Task 014F-17: Experience Modes & Core Visual Preset Foundation."""

import threading
import time

import pytest

from core.events import EVEventBus
from core.experience import (
    EVCoreStylePreset,
    EVExperienceManager,
    EVExperienceMode,
    EXPERIENCE_MODE_DESCRIPTIONS,
    STYLE_PRESET_DESCRIPTIONS,
)
from core.models import EVEventSeverity, EVEventType, EVState


# ======================================================================
# Enum validation
# ======================================================================


class TestEVExperienceModeEnum:
    """Verify EVExperienceMode enum completeness."""

    def test_all_seven_modes_exist(self):
        expected = {"STANDARD", "AI", "WORK", "MUSIC", "SYSTEM", "APPROVAL", "SLEEP"}
        actual = {m.value for m in EVExperienceMode}
        assert actual == expected

    def test_modes_are_string_typed(self):
        for mode in EVExperienceMode:
            assert isinstance(mode, str)
            assert isinstance(mode.value, str)

    def test_mode_from_string(self):
        for mode in EVExperienceMode:
            assert EVExperienceMode(mode.value) == mode

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            EVExperienceMode("NONEXISTENT")


class TestEVCoreStylePresetEnum:
    """Verify EVCoreStylePreset enum completeness."""

    def test_all_five_presets_exist(self):
        expected = {"ASTRA", "ORIGINAL", "EV_CORE", "MINIMAL", "AMBIENT", "FOCUSED", "ALERT"}
        actual = {p.value for p in EVCoreStylePreset}
        assert actual == expected

    def test_presets_are_string_typed(self):
        for preset in EVCoreStylePreset:
            assert isinstance(preset, str)
            assert isinstance(preset.value, str)

    def test_preset_from_string(self):
        for preset in EVCoreStylePreset:
            assert EVCoreStylePreset(preset.value) == preset

    def test_invalid_preset_raises(self):
        with pytest.raises(ValueError):
            EVCoreStylePreset("NONEXISTENT")


# ======================================================================
# Description dictionaries
# ======================================================================


class TestDescriptions:
    """Verify every mode and preset has a description."""

    def test_every_mode_has_description(self):
        for mode in EVExperienceMode:
            assert mode in EXPERIENCE_MODE_DESCRIPTIONS
            desc = EXPERIENCE_MODE_DESCRIPTIONS[mode]
            assert isinstance(desc, str) and len(desc) > 0

    def test_every_preset_has_description(self):
        for preset in EVCoreStylePreset:
            assert preset in STYLE_PRESET_DESCRIPTIONS
            desc = STYLE_PRESET_DESCRIPTIONS[preset]
            assert isinstance(desc, str) and len(desc) > 0


# ======================================================================
# EVExperienceManager — lifecycle and transitions
# ======================================================================


class TestEVExperienceManagerLifecycle:
    """Core lifecycle tests for EVExperienceManager."""

    @pytest.fixture
    def bus(self):
        return EVEventBus(initial_state=EVState.IDLE)

    @pytest.fixture
    def manager(self, bus):
        return EVExperienceManager(bus)

    def test_default_mode_is_standard(self, manager):
        assert manager.current_mode == EVExperienceMode.STANDARD

    def test_default_preset_is_ev_core(self, manager):
        assert manager.current_preset == EVCoreStylePreset.EV_CORE

    def test_custom_initial_mode(self, bus):
        mgr = EVExperienceManager(bus, initial_mode=EVExperienceMode.AI)
        assert mgr.current_mode == EVExperienceMode.AI

    def test_custom_initial_preset(self, bus):
        mgr = EVExperienceManager(
            bus, initial_preset=EVCoreStylePreset.MINIMAL
        )
        assert mgr.current_preset == EVCoreStylePreset.MINIMAL

    def test_set_mode_transitions(self, manager):
        manager.set_mode(EVExperienceMode.WORK)
        assert manager.current_mode == EVExperienceMode.WORK

    def test_set_preset_transitions(self, manager):
        manager.set_style_preset(EVCoreStylePreset.FOCUSED)
        assert manager.current_preset == EVCoreStylePreset.FOCUSED

    def test_set_mode_noop_for_same(self, manager, bus):
        """No event emitted when setting the same mode."""
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            event_types=[EVEventType.EXPERIENCE_MODE_CHANGED],
        )
        manager.set_mode(EVExperienceMode.STANDARD)  # already STANDARD
        assert len(received) == 0

    def test_set_preset_noop_for_same(self, manager, bus):
        """No event emitted when setting the same preset."""
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            event_types=[EVEventType.STYLE_PRESET_CHANGED],
        )
        manager.set_style_preset(EVCoreStylePreset.EV_CORE)  # already EV_CORE
        assert len(received) == 0

    def test_set_mode_string_coercion(self, manager):
        """Accept raw string and coerce to enum."""
        manager.set_mode("AI")
        assert manager.current_mode == EVExperienceMode.AI

    def test_set_preset_string_coercion(self, manager):
        """Accept raw string and coerce to enum."""
        manager.set_style_preset("MINIMAL")
        assert manager.current_preset == EVCoreStylePreset.MINIMAL

    def test_set_mode_invalid_raises(self, manager):
        with pytest.raises(ValueError, match="Invalid experience mode"):
            manager.set_mode("NONEXISTENT")

    def test_set_preset_invalid_raises(self, manager):
        with pytest.raises(ValueError, match="Invalid style preset"):
            manager.set_style_preset("NONEXISTENT")

    def test_all_mode_transitions(self, manager):
        """Cycle through every mode transition."""
        for mode in EVExperienceMode:
            manager.set_mode(mode)
            assert manager.current_mode == mode

    def test_all_preset_transitions(self, manager):
        """Cycle through every preset transition."""
        for preset in EVCoreStylePreset:
            manager.set_style_preset(preset)
            assert manager.current_preset == preset


# ======================================================================
# EVExperienceManager — event bus integration
# ======================================================================


class TestEVExperienceManagerEvents:
    """Verify event bus integration for mode/preset changes."""

    @pytest.fixture
    def bus(self):
        return EVEventBus(initial_state=EVState.IDLE)

    @pytest.fixture
    def manager(self, bus):
        return EVExperienceManager(bus)

    def test_mode_change_emits_event(self, manager, bus):
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            event_types=[EVEventType.EXPERIENCE_MODE_CHANGED],
        )
        manager.set_mode(EVExperienceMode.AI)

        assert len(received) == 1
        event = received[0]
        assert event.event_type == EVEventType.EXPERIENCE_MODE_CHANGED
        assert event.severity == EVEventSeverity.INFO
        assert event.data["previous_mode"] == "STANDARD"
        assert event.data["current_mode"] == "AI"
        assert event.source == "experience_manager"

    def test_preset_change_emits_event(self, manager, bus):
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            event_types=[EVEventType.STYLE_PRESET_CHANGED],
        )
        manager.set_style_preset(EVCoreStylePreset.ALERT)

        assert len(received) == 1
        event = received[0]
        assert event.event_type == EVEventType.STYLE_PRESET_CHANGED
        assert event.severity == EVEventSeverity.INFO
        assert event.data["previous_preset"] == "EV_CORE"
        assert event.data["current_preset"] == "ALERT"

    def test_rapid_transitions_produce_correct_event_count(self, manager, bus):
        received = []
        bus.subscribe(
            lambda e: received.append(e),
            event_types=[EVEventType.EXPERIENCE_MODE_CHANGED],
        )
        modes = list(EVExperienceMode)
        # Start from STANDARD → cycle to all others
        for mode in modes:
            if mode != EVExperienceMode.STANDARD:
                manager.set_mode(mode)

        # Should have emitted len(modes) - 1 events (skipping initial STANDARD)
        assert len(received) == len(modes) - 1


# ======================================================================
# EVExperienceManager — description accessors
# ======================================================================


class TestEVExperienceManagerDescriptions:
    """Verify static description accessors."""

    def test_get_mode_description_enum(self):
        desc = EVExperienceManager.get_mode_description(EVExperienceMode.AI)
        assert "AI" in desc or "intelligence" in desc.lower()

    def test_get_mode_description_string(self):
        desc = EVExperienceManager.get_mode_description("WORK")
        assert isinstance(desc, str) and len(desc) > 0

    def test_get_mode_description_invalid(self):
        desc = EVExperienceManager.get_mode_description("INVALID")
        assert desc == "Unknown mode"

    def test_get_preset_description_enum(self):
        desc = EVExperienceManager.get_preset_description(EVCoreStylePreset.MINIMAL)
        assert isinstance(desc, str) and len(desc) > 0

    def test_get_preset_description_string(self):
        desc = EVExperienceManager.get_preset_description("ALERT")
        assert isinstance(desc, str) and len(desc) > 0

    def test_get_preset_description_invalid(self):
        desc = EVExperienceManager.get_preset_description("INVALID")
        assert desc == "Unknown preset"


# ======================================================================
# Thread safety
# ======================================================================


class TestEVExperienceManagerThreadSafety:
    """Verify thread-safe concurrent access."""

    def test_concurrent_mode_changes(self):
        bus = EVEventBus(initial_state=EVState.IDLE)
        manager = EVExperienceManager(bus)
        errors = []

        def worker(modes):
            try:
                for mode in modes:
                    manager.set_mode(mode)
                    _ = manager.current_mode
            except Exception as exc:
                errors.append(exc)

        modes_a = [EVExperienceMode.AI, EVExperienceMode.WORK, EVExperienceMode.MUSIC] * 10
        modes_b = [EVExperienceMode.SYSTEM, EVExperienceMode.SLEEP, EVExperienceMode.STANDARD] * 10

        t1 = threading.Thread(target=worker, args=(modes_a,))
        t2 = threading.Thread(target=worker, args=(modes_b,))
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not errors, f"Thread safety errors: {errors}"
        # Final mode should be one of the valid modes
        assert manager.current_mode in EVExperienceMode

    def test_concurrent_preset_changes(self):
        bus = EVEventBus(initial_state=EVState.IDLE)
        manager = EVExperienceManager(bus)
        errors = []

        def worker(presets):
            try:
                for preset in presets:
                    manager.set_style_preset(preset)
                    _ = manager.current_preset
            except Exception as exc:
                errors.append(exc)

        presets_a = [EVCoreStylePreset.MINIMAL, EVCoreStylePreset.AMBIENT] * 15
        presets_b = [EVCoreStylePreset.FOCUSED, EVCoreStylePreset.ALERT] * 15

        t1 = threading.Thread(target=worker, args=(presets_a,))
        t2 = threading.Thread(target=worker, args=(presets_b,))
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        assert not errors
        assert manager.current_preset in EVCoreStylePreset


# ======================================================================
# GuiBridge integration (non-QML, direct property access)
# ======================================================================


class TestGuiBridgeExperienceIntegration:
    """Verify GuiBridge exposes experience mode/preset properties."""

    @pytest.fixture
    def setup(self):
        """Create bus, manager, and bridge without Qt event loop."""
        import sys
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            app = QGuiApplication(sys.argv[:1])

        bus = EVEventBus(initial_state=EVState.IDLE)
        manager = EVExperienceManager(bus)

        from gui.bridge import GuiBridge
        bridge = GuiBridge(bus, experience_manager=manager)

        yield bus, manager, bridge, app

        bridge.shutdown()

    def test_initial_experience_mode(self, setup):
        _, _, bridge, _ = setup
        assert bridge.experienceMode == "STANDARD"

    def test_initial_style_preset(self, setup):
        _, _, bridge, _ = setup
        assert bridge.stylePreset == "EV_CORE"

    def test_experience_mode_description(self, setup):
        _, _, bridge, _ = setup
        desc = bridge.experienceModeDescription
        assert isinstance(desc, str) and len(desc) > 0

    def test_bridge_without_manager(self, monkeypatch):
        """Bridge works without an experience manager (backwards compatible)."""
        import sys
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication.instance()
        if app is None:
            app = QGuiApplication(sys.argv[:1])

        bus = EVEventBus(initial_state=EVState.IDLE)

        from gui.bridge import GuiBridge
        monkeypatch.setattr(GuiBridge, "_load_persisted_style_preset", lambda self: "EV_CORE")
        bridge = GuiBridge(bus)  # No experience_manager

        assert bridge.experienceMode == "STANDARD"
        assert bridge.stylePreset == "EV_CORE"
        assert bridge.experienceModeDescription == ""

        bridge.shutdown()

    def test_set_experience_mode_via_bridge(self, setup):
        bus, manager, bridge, app = setup

        bridge.setExperienceMode("AI")
        app.processEvents()

        assert manager.current_mode == EVExperienceMode.AI

    def test_set_style_preset_via_bridge(self, setup):
        bus, manager, bridge, app = setup

        bridge.setStylePreset("MINIMAL")
        app.processEvents()

        assert manager.current_preset == EVCoreStylePreset.MINIMAL

    def test_invalid_mode_from_qml_is_silently_ignored(self, setup):
        bus, manager, bridge, app = setup

        bridge.setExperienceMode("INVALID_MODE")
        app.processEvents()

        # Should remain at STANDARD
        assert manager.current_mode == EVExperienceMode.STANDARD

    def test_invalid_preset_from_qml_is_silently_ignored(self, setup):
        bus, manager, bridge, app = setup

        bridge.setStylePreset("INVALID_PRESET")
        app.processEvents()

        # Should remain at EV_CORE
        assert manager.current_preset == EVCoreStylePreset.EV_CORE

    def test_system_alert_message_property(self, setup):
        _, _, bridge, _ = setup
        assert bridge.systemAlertMessage == ""


# ======================================================================
# EVEventType additions
# ======================================================================


class TestEventTypeAdditions:
    """Verify the new event types exist in EVEventType."""

    def test_experience_mode_changed_exists(self):
        assert EVEventType.EXPERIENCE_MODE_CHANGED == "EXPERIENCE_MODE_CHANGED"

    def test_style_preset_changed_exists(self):
        assert EVEventType.STYLE_PRESET_CHANGED == "STYLE_PRESET_CHANGED"

    def test_existing_event_types_unchanged(self):
        """Existing event types must still be present."""
        expected = {
            "STATE_CHANGED",
            "VOICE_STATE_CHANGED",
            "STATUS",
            "APPROVAL_REQUIRED",
            "ACTION_STARTED",
            "ACTION_COMPLETED",
            "VERIFICATION_RESULT",
            "RECOVERY_RESULT",
            "ERROR",
            "SYSTEM_OBSERVATION",
            "SYSTEM_ALERT",
            "SYSTEM_ALERT_RECOVERED",
            "EXPERIENCE_MODE_CHANGED",
            "STYLE_PRESET_CHANGED",
        }
        actual = {e.value for e in EVEventType}
        assert expected.issubset(actual)
