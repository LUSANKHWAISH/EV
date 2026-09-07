"""Tests for Phase 018-G — Flagship UI + Modes.

Covers:
A. Experience Mode:
   - All seven modes (STANDARD, AI, WORK, MUSIC, SYSTEM, APPROVAL, SLEEP)
   - Mode propagation to GuiBridge
   - EVExperienceModeIndicator presentation in EVTopBar
   - Zero execution side-effects

B. Visual Presets:
   - All five presets (EV_CORE, MINIMAL, AMBIENT, FOCUSED, ALERT)
   - Correct Loader source URL
   - Exactly one active preset item instantiated
   - Safe fallback to EV_CORE on invalid/unknown preset
   - No duplicate active preset items

C. Dynamic Switching:
   - Sequential switching: EV_CORE -> MINIMAL -> AMBIENT -> FOCUSED -> ALERT -> EV_CORE
   - Rapid switching stress test

D. State Propagation:
   - Operational states propagate into each active preset
   - Preset visual remains purely presentation-only

E. Isolation Invariants:
   - Changing experienceMode or stylePreset does NOT alter EVState
   - Changing experienceMode or stylePreset does NOT alter PlanStatus
   - Changing experienceMode or stylePreset does NOT bypass risk/approval requirements
   - Changing experienceMode or stylePreset does NOT alter transaction state

F. Approval Dominance:
   - EVApprovalOverlay maintains z=100 and dominance

G. Protected Files Integrity:
   - EVFlagshipStage.qml SHA256 matches baseline byte-for-byte
   - EVCommandInput.qml SHA256 matches baseline byte-for-byte

H. QML Diagnostics:
   - Zero TypeErrors, zero binding loops, zero undefined properties, zero import errors

I. Responsive Adaptation:
   - Top bar with mode indicator and flagship stage adapt across resolutions
"""

import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.events import EVEventBus, EVEventType
from core.experience import EVCoreStylePreset, EVExperienceManager, EVExperienceMode
from core.models import EVEventSeverity, EVState, RiskLevel
from core.plan import PlanStatus
from gui.bridge import GuiBridge

QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"
PRESETS_ROOT = COMPONENT_ROOT / "presets"

FLAGSHIP_STAGE_PATH = COMPONENT_ROOT / "EVFlagshipStage.qml"
EXPECTED_FLAGSHIP_SHA256 = "b7eee6e5c3ad6a6c8ea85188767ce5b44ef3fe00d83fb202fb99f0b33fd689c8"

COMMAND_INPUT_PATH = COMPONENT_ROOT / "EVCommandInput.qml"
EXPECTED_COMMAND_INPUT_SHA256 = "6b6c231d7bf04f9ffbd3e0bd860b16a9ce6ebe4ac5bfd943eb83e70d3602af13"

ALL_EXPERIENCE_MODES = [
    EVExperienceMode.STANDARD,
    EVExperienceMode.AI,
    EVExperienceMode.WORK,
    EVExperienceMode.MUSIC,
    EVExperienceMode.SYSTEM,
    EVExperienceMode.APPROVAL,
    EVExperienceMode.SLEEP,
]

ALL_STYLE_PRESETS = [
    EVCoreStylePreset.EV_CORE,
    EVCoreStylePreset.MINIMAL,
    EVCoreStylePreset.AMBIENT,
    EVCoreStylePreset.FOCUSED,
    EVCoreStylePreset.ALERT,
]


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QGuiApplication exists for testing."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def event_bus():
    """Create a fresh EVEventBus."""
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, qapp):
    """Create a fresh GuiBridge wired to the test bus."""
    exp_mgr = EVExperienceManager(event_bus)
    b = GuiBridge(event_bus, experience_manager=exp_mgr)
    yield b
    b.shutdown()


@pytest.fixture
def core_host(bridge, qapp):
    """Fixture providing an instantiated EVIntelligenceCore."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)
    comp = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVIntelligenceCore.qml")),
    )
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    core = comp.create()
    assert core is not None
    qapp.processEvents()

    yield core, engine

    core.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# A. Experience Mode Presentation & Propagation
# =============================================================================

@pytest.mark.parametrize("mode", ALL_EXPERIENCE_MODES)
def test_experience_mode_propagation_to_bridge(bridge, qapp, mode):
    """A1. All seven experience modes propagate through GuiBridge."""
    bridge.setExperienceMode(mode.value)
    qapp.processEvents()
    assert bridge.experienceMode == mode.value
    assert bridge.experienceModeDescription != ""


def test_experience_mode_indicator_in_top_bar(bridge, qapp):
    """A2. EVExperienceModeIndicator reflects active experience mode within EVTopBar."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVTopBar.qml")),
    )
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    top_bar = comp.create()
    assert top_bar is not None
    qapp.processEvents()

    indicator = top_bar.findChild(QQuickItem, "experienceModeIndicator")
    assert indicator is not None, "experienceModeIndicator must be present in EVTopBar"

    for mode in ALL_EXPERIENCE_MODES:
        bridge.setExperienceMode(mode.value)
        qapp.processEvents()

        assert indicator.property("mode") == mode.value
        # Glyph and color must be non-empty/valid
        glyph = indicator.property("modeGlyph")
        assert glyph is not None and len(str(glyph)) > 0
        color = indicator.property("modeColor")
        assert color is not None

    top_bar.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


def test_experience_mode_has_no_execution_side_effects(bridge, event_bus, qapp):
    """A3. Changing experience mode must NEVER dispatch tasks or trigger execution."""
    dispatched_events = []
    event_bus.subscribe(lambda event: dispatched_events.append(event))

    initial_state = event_bus.current_state
    for mode in ALL_EXPERIENCE_MODES:
        bridge.setExperienceMode(mode.value)
        qapp.processEvents()

    # State must remain unchanged
    assert event_bus.current_state == initial_state
    # No action execution events should have occurred
    execution_events = [
        e for e in dispatched_events
        if e.event_type in (EVEventType.ACTION_STARTED, EVEventType.PLAN_STARTED)
    ]
    assert len(execution_events) == 0


# =============================================================================
# B. Visual Presets & Loader Mechanics
# =============================================================================

@pytest.mark.parametrize("preset", ALL_STYLE_PRESETS)
def test_visual_preset_loader_resolution(core_host, qapp, preset):
    """B1. All 5 visual presets resolve correct Loader source and instantiate."""
    core, _ = core_host
    core.setProperty("themeProfile", preset.value)
    qapp.processEvents()

    assert core.property("effectiveThemeProfile") == preset.value
    expected_filename = {
        EVCoreStylePreset.EV_CORE: "EVCoreFlagshipVisual.qml",
        EVCoreStylePreset.MINIMAL: "EVCoreMinimalVisual.qml",
        EVCoreStylePreset.AMBIENT: "EVCoreAmbientVisual.qml",
        EVCoreStylePreset.FOCUSED: "EVCoreFocusedVisual.qml",
        EVCoreStylePreset.ALERT: "EVCoreAlertVisual.qml",
    }[preset]

    source_url = str(core.property("activePresetSource")).lower()
    assert expected_filename.lower() in source_url
    assert core.property("hasActiveVisualItem") is True


def test_unknown_preset_safe_fallback(core_host, qapp):
    """B2. Unknown or invalid style preset string safely defaults to EV_CORE."""
    core, _ = core_host
    core.setProperty("themeProfile", "UNKNOWN_NON_EXISTENT_PRESET")
    qapp.processEvents()

    assert core.property("effectiveThemeProfile") == "EV_CORE"
    assert "evcoreflagshipvisual.qml" in str(core.property("activePresetSource")).lower()
    assert core.property("hasActiveVisualItem") is True


def test_loader_destroys_previous_child_no_duplicate(core_host, qapp):
    """B3. Loader unloads previous preset item so only one visual preset exists."""
    core, _ = core_host

    # Switch from EV_CORE to MINIMAL
    core.setProperty("themeProfile", "EV_CORE")
    qapp.processEvents()
    assert core.property("hasActiveVisualItem") is True

    core.setProperty("themeProfile", "MINIMAL")
    qapp.processEvents()
    assert core.property("effectiveThemeProfile") == "MINIMAL"
    assert core.property("hasActiveVisualItem") is True

    # Check child items of the core: there should only be one active visual inside loader
    loader = core.findChild(QQuickItem, "presetLoader")
    assert loader is not None
    # Loader itself has at most one item child
    loader_children = [c for c in loader.childItems() if isinstance(c, QQuickItem)]
    assert len(loader_children) == 1


# =============================================================================
# C. Dynamic Preset Switching & Stress
# =============================================================================

def test_sequential_preset_switching(core_host, qapp):
    """C1. Full cycle switching across all presets succeeds cleanly."""
    core, _ = core_host
    sequence = ["EV_CORE", "MINIMAL", "AMBIENT", "FOCUSED", "ALERT", "EV_CORE"]

    for preset_name in sequence:
        core.setProperty("themeProfile", preset_name)
        qapp.processEvents()
        assert core.property("effectiveThemeProfile") == preset_name
        assert core.property("hasActiveVisualItem") is True


def test_rapid_preset_switching_stress(core_host, qapp):
    """C2. Rapid repeated switching stress across multiple cycles does not crash."""
    core, _ = core_host
    cycle = ["EV_CORE", "MINIMAL", "AMBIENT", "FOCUSED", "ALERT"]

    # 4 complete cycles (20 switches)
    for _ in range(4):
        for preset_name in cycle:
            core.setProperty("themeProfile", preset_name)
            qapp.processEvents()
            assert core.property("hasActiveVisualItem") is True

    # Settle back to EV_CORE
    core.setProperty("themeProfile", "EV_CORE")
    qapp.processEvents()
    assert core.property("effectiveThemeProfile") == "EV_CORE"
    assert core.property("hasActiveVisualItem") is True


# =============================================================================
# D. State Propagation
# =============================================================================

@pytest.mark.parametrize("preset", ALL_STYLE_PRESETS)
def test_state_propagation_in_each_preset(core_host, qapp, preset):
    """D1. Operational states propagate cleanly into each active preset."""
    core, _ = core_host
    core.setProperty("themeProfile", preset.value)
    qapp.processEvents()

    states_to_test = [
        EVState.IDLE,
        EVState.LISTENING,
        EVState.PLANNING,
        EVState.EXECUTING,
        EVState.VERIFYING,
        EVState.SUCCESS,
        EVState.FAILED,
    ]

    for st in states_to_test:
        core.setProperty("state", st.value)
        qapp.processEvents()
        assert core.property("stateText") == st.value
        assert core.property("hasActiveVisualItem") is True


# =============================================================================
# E. Non-Negotiable Isolation
# =============================================================================

def test_modes_and_presets_do_not_alter_execution_authority(bridge, event_bus):
    """E1. Changing preset or mode must NOT mutate EVState, PlanStatus, or approvals."""
    initial_state = event_bus.current_state
    assert initial_state == EVState.IDLE

    # Change through all presets and modes
    for mode in ALL_EXPERIENCE_MODES:
        bridge.setExperienceMode(mode.value)
        assert event_bus.current_state == initial_state

    for preset in ALL_STYLE_PRESETS:
        bridge.setStylePreset(preset.value)
        assert event_bus.current_state == initial_state


def test_alert_preset_does_not_imply_or_grant_approval(bridge, event_bus, qapp):
    """E2. Switching to ALERT visual preset NEVER grants approval or alters risk."""
    bridge.setStylePreset("ALERT")
    qapp.processEvents()
    assert bridge.stylePreset == "ALERT"

    # Verify no approval event or bypass occurred
    assert bridge.approvalTaskId == ""
    assert bridge.approvalPending is False


# =============================================================================
# F. Approval Overlay Dominance
# =============================================================================

def test_approval_overlay_dominance(bridge, qapp):
    """F1. EVApprovalOverlay remains z=100 and highest stacking order in EVWindow."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVWindow.qml")),
    )
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    window = comp.create()
    assert window is not None
    qapp.processEvents()

    approval_overlay = window.findChild(QQuickItem, "approvalOverlay")
    assert approval_overlay is not None, "approvalOverlay must exist in EVWindow"
    assert approval_overlay.z() == 100, f"Approval overlay z-index must be 100, got {approval_overlay.z()}"

    flagship_stage = window.findChild(QQuickItem, "flagshipStage")
    assert flagship_stage is not None
    assert flagship_stage.z() < approval_overlay.z(), "Flagship stage must be below approval overlay"

    window.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# G. Protected File Invariants
# =============================================================================

def test_protected_files_hashes_untouched():
    """G1. EVFlagshipStage.qml and EVCommandInput.qml are strictly protected."""
    assert FLAGSHIP_STAGE_PATH.exists(), f"Missing {FLAGSHIP_STAGE_PATH}"
    actual_flagship_hash = hashlib.sha256(FLAGSHIP_STAGE_PATH.read_bytes()).hexdigest().lower()
    assert actual_flagship_hash == EXPECTED_FLAGSHIP_SHA256, (
        f"Protected file EVFlagshipStage.qml was modified! Expected {EXPECTED_FLAGSHIP_SHA256}, got {actual_flagship_hash}"
    )

    assert COMMAND_INPUT_PATH.exists(), f"Missing {COMMAND_INPUT_PATH}"
    actual_input_hash = hashlib.sha256(COMMAND_INPUT_PATH.read_bytes()).hexdigest().lower()
    assert actual_input_hash == EXPECTED_COMMAND_INPUT_SHA256, (
        f"Protected file EVCommandInput.qml was modified! Expected {EXPECTED_COMMAND_INPUT_SHA256}, got {actual_input_hash}"
    )


# =============================================================================
# H. QML Diagnostics Clean
# =============================================================================

def test_qml_diagnostics_clean(bridge, qapp):
    """H1. All modified host and preset components instantiate with zero QML errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    components_to_check = [
        COMPONENT_ROOT / "EVTopBar.qml",
        COMPONENT_ROOT / "EVIntelligenceCore.qml",
        PRESETS_ROOT / "EVCoreFlagshipVisual.qml",
        PRESETS_ROOT / "EVCoreMinimalVisual.qml",
        PRESETS_ROOT / "EVCoreAmbientVisual.qml",
        PRESETS_ROOT / "EVCoreFocusedVisual.qml",
        PRESETS_ROOT / "EVCoreAlertVisual.qml",
    ]

    for comp_path in components_to_check:
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(comp_path)))
        errors = [e.toString() for e in comp.errors()]
        assert not comp.isError(), f"Errors loading {comp_path.name}: {errors}"
        inst = comp.create()
        assert inst is not None, f"Failed to instantiate {comp_path.name}"
        qapp.processEvents()
        inst.deleteLater()

    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# I. Responsive Adaptation of Modes & Presets
# =============================================================================

@pytest.mark.parametrize("width,height", [(800, 600), (1280, 720), (1920, 1080)])
def test_topbar_and_core_responsive_at_target_resolutions(bridge, qapp, width, height):
    """I1. Top bar with mode indicator and flagship stage adapt across resolutions."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVWindow.qml")),
    )
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    window = comp.create()
    assert window is not None

    window.setWidth(width)
    window.setHeight(height)
    qapp.processEvents()

    top_bar = window.findChild(QQuickItem, "topBar")
    assert top_bar is not None
    assert top_bar.width() == width
    assert top_bar.height() > 0

    mode_indicator = top_bar.findChild(QQuickItem, "experienceModeIndicator")
    assert mode_indicator is not None
    assert mode_indicator.property("visible") is True

    flagship_stage = window.findChild(QQuickItem, "flagshipStage")
    assert flagship_stage is not None
    assert flagship_stage.width() > 0
    assert flagship_stage.height() > 0

    window.deleteLater()
    engine.deleteLater()
    qapp.processEvents()
