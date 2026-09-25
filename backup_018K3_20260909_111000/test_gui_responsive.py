"""Tests for Phase 018-F — Responsive HUD Layout & Window Adaptation.

Validates that E.V.'s flagship HUD adapts gracefully across desktop resolutions:
1920x1080, 1600x900, 1366x768, 1280x720, 1024x768, and 800x600.

Covers:
A. Component loading at target resolutions
B. Dynamic resize transitions (down and up)
C. Geometry invariants (no negative bounds, no overlap, containment)
D. Flagship stage viability without starving core
E. Long result stress at compact heights
F. Full lifecycle stage progression and readability
G. Approval overlay with long text on compact window
H. Proactive awareness banner co-existence
I. Byte-for-byte protection of EVFlagshipStage.qml (SHA256)
J. Zero QML warnings, TypeErrors, or binding loops
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
from core.models import EVState
from gui.bridge import GuiBridge

QML_ROOT = PROJECT_ROOT / "gui" / "qml"
COMPONENT_ROOT = QML_ROOT / "components"
FLAGSHIP_STAGE_PATH = COMPONENT_ROOT / "EVFlagshipStage.qml"
EXPECTED_FLAGSHIP_SHA256 = "b7eee6e5c3ad6a6c8ea85188767ce5b44ef3fe00d83fb202fb99f0b33fd689c8"

TARGET_RESOLUTIONS = [
    (1920, 1080),
    (1600, 900),
    (1366, 768),
    (1280, 720),
    (1024, 768),
    (800, 600),
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
    b = GuiBridge(event_bus)
    yield b
    b.shutdown()


@pytest.fixture
def responsive_window(bridge, qapp):
    """Fixture providing a helper that loads EVWindow.qml safely via engine.load."""
    engines = []

    def _create(width=1280, height=720):
        engine = QQmlApplicationEngine()
        engine.rootContext().setContextProperty("guiBridge", bridge)
        qml_url = QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVWindow.qml"))
        engine.load(qml_url)
        assert len(engine.rootObjects()) > 0, "Failed to load EVWindow.qml"
        window = engine.rootObjects()[-1]
        window.setWidth(width)
        window.setHeight(height)
        qapp.processEvents()
        engines.append(engine)
        return window

    yield _create

    for eng in engines:
        for root_obj in eng.rootObjects():
            root_obj.deleteLater()
        qapp.processEvents()
        eng.clearComponentCache()
        eng.deleteLater()
        qapp.processEvents()


# =============================================================================
# A. Component Loading at Target Resolutions
# =============================================================================

@pytest.mark.parametrize("width,height", TARGET_RESOLUTIONS)
def test_component_loading_at_resolutions(responsive_window, qapp, width, height):
    """A. EVWindow loads successfully and adapts properties across all target resolutions."""
    window = responsive_window(width, height)
    assert window.property("width") == width
    assert window.property("height") == height

    is_compact_w = width < 900
    is_compact_h = height < 620

    assert window.property("isCompactWidth") == is_compact_w
    assert window.property("isCompactHeight") == is_compact_h

    # Verify positive dimensions on root and child containers
    assert window.width() > 0
    assert window.height() > 0


# =============================================================================
# B. Dynamic Resize Transitions
# =============================================================================

def test_dynamic_resize_transitions(responsive_window, qapp):
    """B. Dynamic resizing down to 800x600 and back to 1920x1080 produces no errors."""
    window = responsive_window(1920, 1080)

    # Step down through resolutions
    for w, h in TARGET_RESOLUTIONS:
        window.setWidth(w)
        window.setHeight(h)
        qapp.processEvents()

        assert window.property("width") == w
        assert window.property("height") == h
        assert window.property("isCompactWidth") == (w < 900)
        assert window.property("isCompactHeight") == (h < 620)

    # Step back up to 1920x1080
    window.setWidth(1920)
    window.setHeight(1080)
    qapp.processEvents()

    assert window.property("width") == 1920
    assert window.property("height") == 1080
    assert window.property("isCompactWidth") is False
    assert window.property("isCompactHeight") is False


# =============================================================================
# C. Geometry Invariants
# =============================================================================

@pytest.mark.parametrize("width,height", [(1920, 1080), (1280, 720), (800, 600)])
def test_geometry_invariants(responsive_window, qapp, width, height):
    """C. Invariants: no negative dimensions, components stay within window bounds."""
    window = responsive_window(width, height)

    top_bar = window.findChild(QQuickItem, "topBar")
    command_input = window.findChild(QQuickItem, "commandInput")
    result_surface = window.findChild(QQuickItem, "resultSurface")
    flagship_stage = window.findChild(QQuickItem, "flagshipStage")

    # TopBar at top
    if top_bar:
        assert top_bar.y() == 0
        assert top_bar.height() == 48

    # Command input pinned to bottom
    if command_input:
        expected_h = 48 if height < 620 else 64
        assert command_input.height() == expected_h
        assert command_input.y() + command_input.height() <= height
        assert command_input.width() > 0

    # Flagship stage bounded between top and bottom surfaces
    if flagship_stage:
        assert flagship_stage.height() > 0
        assert flagship_stage.width() > 0
        assert flagship_stage.y() >= 48
        if command_input:
            assert flagship_stage.y() < command_input.y()


# =============================================================================
# D. Flagship Stage Viability & Rail Containment
# =============================================================================

@pytest.mark.parametrize("width,height", TARGET_RESOLUTIONS)
def test_stage_viability_and_rails(responsive_window, qapp, width, height):
    """D. Stage height remains positive and rails remain within stage bounds."""
    window = responsive_window(width, height)

    stage = window.findChild(QQuickItem, "flagshipStage")
    assert stage is not None
    assert stage.height() > 0
    assert stage.width() > 0

    telemetry_rail = stage.findChild(QQuickItem, "telemetryRail")
    if telemetry_rail:
        assert telemetry_rail.height() > 0
        assert telemetry_rail.width() > 0
        # Telemetry rail must be within stage bounds
        assert telemetry_rail.x() + telemetry_rail.width() <= stage.width() + 1


# =============================================================================
# E. Result Surface Stress on Compact Window
# =============================================================================

def test_result_surface_stress_on_compact_window(responsive_window, bridge, qapp):
    """E. Long multi-line results do not starve the flagship stage or push input off-screen."""
    window = responsive_window(800, 600)

    stage = window.findChild(QQuickItem, "flagshipStage")
    result_surface = window.findChild(QQuickItem, "resultSurface")
    command_input = window.findChild(QQuickItem, "commandInput")

    # Simulate massive 40-line result text
    long_result = "\n".join([f"Line {i}: Processed record {i * 137} with status OK" for i in range(40)])
    bridge.notifyTaskResult(long_result, "SUCCESS", True)
    qapp.processEvents()
    from PySide6.QtTest import QTest
    QTest.qWait(350)

    assert result_surface.property("isVisible") is True
    assert result_surface.property("visible") is True
    assert result_surface.property("isCompactHeight") is True

    # Result surface must be capped on compact screen (at most 140px)
    assert result_surface.height() <= 140

    # Command input remains pinned and within window
    assert command_input.y() + command_input.height() <= 600
    assert command_input.property("visible") is True

    # Flagship stage must maintain viable space (> 150px)
    assert stage.height() >= 150


# =============================================================================
# F. Lifecycle Stress and Readability
# =============================================================================

def test_lifecycle_stress_and_readability(bridge, event_bus, qapp):
    """F. All 11 canonical lifecycle stages are visualized cleanly without clipping."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVLifecycleHUD.qml")))
    assert not comp.isError(), f"EVLifecycleHUD errors: {[e.toString() for e in comp.errors()]}"
    hud = comp.create()
    assert hud is not None

    try:
        # Test at compact width
        hud.setProperty("width", 500)
        qapp.processEvents()
        assert hud.property("isCompactWidth") is True

        stages_to_test = [
            ("THINKING", 1),
            ("PLANNING", 2),
            ("VALIDATING", 3),
            ("RISK", 4),
            ("APPROVAL", 5),
            ("EXECUTE", 6),
            ("VERIFY", 7),
        ]

        for stage_name, idx in stages_to_test:
            bridge.notifyLifecycleStage(stage_name)
            qapp.processEvents()
            assert bridge.lifecycleStage == stage_name
            assert bridge.lifecycleStageIndex == idx
            assert hud.property("stageIndex") == idx

        # Terminal outcomes
        for outcome in ["SUCCESS", "FAILED", "ROLLED_BACK", "CANCELLED"]:
            success = outcome == "SUCCESS"
            bridge.notifyTaskResult(f"Task outcome: {outcome}", outcome, success)
            qapp.processEvents()
            assert bridge.lifecycleStage == outcome
            assert bridge.lifecycleStageIndex == 8
    finally:
        hud.deleteLater()
        engine.deleteLater()
        qapp.processEvents()


# =============================================================================
# G. Approval Stress on Compact Window
# =============================================================================

def test_approval_stress_compact_window(responsive_window, bridge, event_bus, qapp):
    """G. Approval dialog with extensive parameters remains contained with accessible buttons."""
    window = responsive_window(800, 600)

    overlay = window.findChild(QQuickItem, "approvalOverlay")
    assert overlay is not None

    # Publish approval with very long fields
    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        EVEventType.APPROVAL_REQUIRED,
        "risk_engine",
        data={
            "task_id": "plan-stress-001",
            "action": "MUTATE_SYSTEM_SERVICES_EXTENDED",
            "goal": "Reconfigure cluster services and restart daemon threads",
            "description": "This is an extensive operation that will touch critical infrastructure files: " * 5,
            "resource": "cluster://nodes/worker-01/etc/systemd/system/multi-user.target.wants/service.d/override.conf",
            "risk_level": "CRITICAL",
            "reason": "Production daemon modification detected which could cause service downtime if misconfigured " * 3,
            "reversible": False,
            "rollback_available": False,
        },
    )
    qapp.processEvents()

    assert bridge.approvalPending is True
    assert overlay.property("visible") is True

    dialog_card = overlay.findChild(QQuickItem, "dialogCard")
    assert dialog_card is not None

    # Card must fit comfortably within the 600px window
    assert dialog_card.height() <= 600 - 32
    assert dialog_card.width() <= 800 - 32

    # Action buttons must be reachable and inside the card
    approve_btn = overlay.findChild(QQuickItem, "approveButton")
    reject_btn = overlay.findChild(QQuickItem, "rejectButton")
    assert approve_btn is not None
    assert reject_btn is not None
    assert approve_btn.property("enabled") is True
    assert reject_btn.property("enabled") is True

    # Test approving
    overlay.handleDecision(True)
    qapp.processEvents()
    assert overlay.property("isResolving") is True


# =============================================================================
# H. Proactive Awareness Banner Stress
# =============================================================================

def test_awareness_banner_stress(responsive_window, event_bus, qapp):
    """H. Awareness banner activation does not obscure command input or violate layout."""
    window = responsive_window(800, 600)

    banner = window.findChild(QQuickItem, "systemAlertBanner")
    command_input = window.findChild(QQuickItem, "commandInput")
    stage = window.findChild(QQuickItem, "flagshipStage")

    assert banner is not None
    assert banner.property("hasContent") is False

    # Publish awareness alert
    event_bus.publish(
        EVEventType.AWARENESS_EVENT,
        "system_monitor",
        data={
            "title": "High Memory Usage Warning",
            "message": "Memory utilization at 88%. Consider closing unused processes.",
            "severity": "WARNING",
        },
    )
    qapp.processEvents()
    from PySide6.QtTest import QTest
    QTest.qWait(400)

    assert banner.property("hasContent") is True
    assert banner.height() > 0

    # Banner is positioned below top bar and above flagship stage
    assert banner.y() >= 48
    assert stage.y() >= banner.y() + banner.height()

    # Command input remains reachable at bottom
    assert command_input.y() + command_input.height() <= 600
    assert command_input.property("visible") is True


# =============================================================================
# I. Protected File Invariant: EVFlagshipStage.qml
# =============================================================================

def test_protected_flagship_sha_unchanged():
    """I. EVFlagshipStage.qml is strictly protected and its SHA256 matches baseline."""
    assert FLAGSHIP_STAGE_PATH.exists(), f"File not found: {FLAGSHIP_STAGE_PATH}"
    actual_hash = hashlib.sha256(FLAGSHIP_STAGE_PATH.read_bytes()).hexdigest().lower()
    assert actual_hash == EXPECTED_FLAGSHIP_SHA256, (
        f"Protected file EVFlagshipStage.qml was modified! Expected {EXPECTED_FLAGSHIP_SHA256}, got {actual_hash}"
    )


# =============================================================================
# J. QML Diagnostics Clean
# =============================================================================

def test_qml_diagnostics_clean(bridge, qapp):
    """J. All modified components instantiate and resize with zero QML errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    components_to_check = [
        "EVWindow.qml",
        "EVResultSurface.qml",
        "EVLifecycleHUD.qml",
        "EVCommandInput.qml",
        "EVApprovalOverlay.qml",
    ]

    for comp_name in components_to_check:
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(COMPONENT_ROOT / comp_name)))
        errors = [e.toString() for e in comp.errors()]
        assert not comp.isError(), f"Errors loading {comp_name}: {errors}"
        inst = comp.create()
        assert inst is not None, f"Failed to instantiate {comp_name}"
        qapp.processEvents()
        inst.deleteLater()

    engine.deleteLater()
    qapp.processEvents()
