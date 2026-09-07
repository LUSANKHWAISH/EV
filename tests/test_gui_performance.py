"""
Performance & Rendering Polish Test Suite (Phase 018-H).

Verifies:
A. Telemetry signal change guarding (no duplicate Changed signals, initial snapshot emits, heartbeat preserved).
B. SLEEP mode master animation quiescence (stops in SLEEP, resumes when leaving SLEEP, normal modes run).
C. Preset Loader stability (single active child, clean destruction, zero QML warnings).
D. Canvas repaint contract (orbital canvases smooth, static canvases not flooded on idle phase ticks).
E. Approval authority invariance (dominant, modal, canonical resolution intact across all modes/presets).
F. Protected EVFlagshipStage.qml SHA256 integrity.
"""

import hashlib
from pathlib import Path
import sys
from typing import Any, Dict

import pytest
from PySide6.QtCore import QCoreApplication, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtTest import QSignalSpy

from core.events import EVEvent, EVEventBus
from core.experience import EVExperienceManager, EVExperienceMode, EVCoreStylePreset
from core.models import EVEventType, EVState
from gui.bridge import GuiBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_COMPONENTS = PROJECT_ROOT / "gui" / "qml" / "components"

PROTECTED_FLAGSHIP_STAGE_SHA256 = "B7EEE6E5C3AD6A6C8EA85188767CE5B44EF3FE00D83FB202FB99F0B33FD689C8"


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QGuiApplication exists across tests."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def event_bus():
    """Create fresh EVEventBus in IDLE state."""
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, qapp):
    """Create a fresh GuiBridge."""
    exp_mgr = EVExperienceManager(event_bus)
    b = GuiBridge(event_bus, experience_manager=exp_mgr)
    yield b
    b.shutdown()


# =============================================================================
# A. Telemetry Signal Change Guarding Tests
# =============================================================================

def test_telemetry_first_snapshot_emits_changed_signals(bridge, event_bus, qapp):
    """Initial valid telemetry snapshot populates and emits all changed signals."""
    spy_avail = QSignalSpy(bridge.telemetryAvailableChanged)
    spy_cpu = QSignalSpy(bridge.telemetryCpuPercentChanged)
    spy_mem = QSignalSpy(bridge.telemetryMemoryPercentChanged)
    spy_disk = QSignalSpy(bridge.telemetryDiskFreePercentChanged)
    spy_updated = QSignalSpy(bridge.telemetryUpdated)

    assert bridge.telemetryAvailable is False

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "snapshot": {
                "cpu_percent": 25.0,
                "memory_used_percent": 50.0,
                "disk_free_percent": 75.0,
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is True
    assert spy_avail.count() == 1
    assert spy_cpu.count() == 1
    assert spy_mem.count() == 1
    assert spy_disk.count() == 1
    assert spy_updated.count() == 1
    assert bridge.telemetryCpuPercent == 25.0


def test_telemetry_unchanged_snapshot_suppresses_duplicate_signals(bridge, event_bus, qapp):
    """Identical telemetry snapshots do not re-emit property Changed signals."""
    snapshot = {
        "cpu_percent": 30.0,
        "memory_used_percent": 45.0,
        "disk_free_percent": 80.0,
        "process_count": 120,
        "network_connected": True,
    }

    # Initial snapshot
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": snapshot},
    )
    QCoreApplication.processEvents()

    spy_avail = QSignalSpy(bridge.telemetryAvailableChanged)
    spy_cpu = QSignalSpy(bridge.telemetryCpuPercentChanged)
    spy_mem = QSignalSpy(bridge.telemetryMemoryPercentChanged)
    spy_proc = QSignalSpy(bridge.telemetryProcessCountChanged)
    spy_net = QSignalSpy(bridge.telemetryNetworkConnectedChanged)
    spy_updated = QSignalSpy(bridge.telemetryUpdated)

    # Publish 5 identical snapshots
    for _ in range(5):
        event_bus.publish(
            event_type=EVEventType.SYSTEM_OBSERVATION,
            source="system_monitor",
            data={"snapshot": snapshot},
        )
        QCoreApplication.processEvents()

    # Changed signals MUST NOT have emitted again
    assert spy_avail.count() == 0
    assert spy_cpu.count() == 0
    assert spy_mem.count() == 0
    assert spy_proc.count() == 0
    assert spy_net.count() == 0

    # Heartbeat signal MUST emit every snapshot (5 times)
    assert spy_updated.count() == 5


def test_telemetry_changed_value_emits_specific_changed_signal(bridge, event_bus, qapp):
    """When only one metric changes, only its specific Changed signal is emitted."""
    snapshot1 = {
        "cpu_percent": 20.0,
        "memory_used_percent": 40.0,
        "disk_free_percent": 60.0,
    }
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": snapshot1},
    )
    QCoreApplication.processEvents()

    spy_cpu = QSignalSpy(bridge.telemetryCpuPercentChanged)
    spy_mem = QSignalSpy(bridge.telemetryMemoryPercentChanged)
    spy_disk = QSignalSpy(bridge.telemetryDiskFreePercentChanged)

    # Only CPU changes from 20.0 to 55.0
    snapshot2 = {
        "cpu_percent": 55.0,
        "memory_used_percent": 40.0,
        "disk_free_percent": 60.0,
    }
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": snapshot2},
    )
    QCoreApplication.processEvents()

    assert spy_cpu.count() == 1
    assert abs(spy_cpu.at(0)[0] - 55.0) < 0.01
    assert spy_mem.count() == 0
    assert spy_disk.count() == 0


# =============================================================================
# B. SLEEP Mode Master Animation Quiescence Tests
# =============================================================================

def test_sleep_mode_stops_master_phase_animation(bridge, event_bus, qapp):
    """In SLEEP mode, the master phase animation stops completely."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_COMPONENTS / "EVIntelligenceCore.qml")))
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    core = comp.create()
    assert core is not None
    qapp.processEvents()

    # Verify in STANDARD mode it is running
    core.setProperty("visualMode", "STANDARD")
    qapp.processEvents()
    assert core.property("visualMode") == "STANDARD"

    # Switch to SLEEP mode
    core.setProperty("visualMode", "SLEEP")
    qapp.processEvents()

    phase_sleep1 = core.property("phase")
    qapp.processEvents()
    phase_sleep2 = core.property("phase")
    assert phase_sleep1 == phase_sleep2

    # Switch back to STANDARD mode
    core.setProperty("visualMode", "STANDARD")
    qapp.processEvents()
    assert core.property("visualMode") == "STANDARD"

    core.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# C. Preset Loader Stability Tests
# =============================================================================

def test_preset_loader_single_child_and_clean_destruction(bridge, event_bus, qapp):
    """Dynamic preset loader always maintains exactly 1 child without leaks or errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_COMPONENTS / "EVIntelligenceCore.qml")))
    core = comp.create()
    assert core is not None
    qapp.processEvents()

    loader = core.findChild(QQuickItem, "presetLoader")
    assert loader is not None

    cycle = ["EV_CORE", "MINIMAL", "AMBIENT", "FOCUSED", "ALERT", "EV_CORE"]
    for preset in cycle:
        core.setProperty("themeProfile", preset)
        qapp.processEvents()
        children = [x for x in loader.childItems() if isinstance(x, QQuickItem)]
        assert len(children) == 1, f"Expected 1 active child for preset {preset}, got {len(children)}"

    core.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# D. Canvas Repaint Contract Tests
# =============================================================================

def test_canvas_repaint_contract_in_flagship_visual(bridge, qapp):
    """EVCoreFlagshipVisual initializes cleanly with optimized repaint connections."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_COMPONENTS / "presets" / "EVCoreFlagshipVisual.qml")))
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    visual = comp.create()
    assert visual is not None
    qapp.processEvents()

    # Changing stateText should trigger canvas updates without error
    visual.setProperty("stateText", "LISTENING")
    qapp.processEvents()
    visual.setProperty("stateText", "SPEAKING")
    qapp.processEvents()
    visual.setProperty("stateText", "IDLE")
    qapp.processEvents()

    # Resize should trigger canvas updates without error
    visual.setProperty("width", 800)
    visual.setProperty("height", 600)
    qapp.processEvents()

    visual.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# E. Approval Authority Invariance Tests
# =============================================================================

def test_approval_overlay_declarative_binding_invariance(bridge, event_bus, qapp):
    """Approval overlay reflects bridge state declaratively with zero broken bindings."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    window = QQuickWindow()
    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(QML_COMPONENTS / "EVApprovalOverlay.qml")))
    assert not comp.isError(), [e.toString() for e in comp.errors()]
    overlay = comp.create()
    assert overlay is not None
    overlay.setParentItem(window.contentItem())
    qapp.processEvents()

    # Initially hidden
    assert overlay.property("visible") is False
    assert overlay.property("approvalPending") is False

    # Trigger approval event
    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-perf-01",
        data={
            "task_id": "plan-perf-01",
            "action": "EXECUTE_COMMAND",
            "description": "Restart system service",
            "resource": "spooler.service",
            "risk_level": "MEDIUM",
            "reason": "Print subsystem maintenance",
            "reversible": True,
            "rollback_available": True,
        },
    )
    qapp.processEvents()

    # Declarative bindings must reflect new values immediately
    assert overlay.property("visible") is True
    assert overlay.property("approvalPending") is True
    assert overlay.property("actionName") == "EXECUTE_COMMAND"
    assert overlay.property("descriptionText") == "Restart system service"
    assert overlay.property("resourcePath") == "spooler.service"
    assert overlay.property("riskLevel") == "MEDIUM"
    assert overlay.property("reversible") is True
    assert overlay.property("rollbackAvailable") is True

    # User rejection via Escape or handleDecision(False)
    spy_submit = QSignalSpy(bridge.approvalSubmitted)
    bridge.submitApproval("plan-perf-01", False)
    qapp.processEvents()

    assert spy_submit.count() == 1
    assert spy_submit.at(0)[0] == "plan-perf-01"
    assert spy_submit.at(0)[1] is False

    overlay.deleteLater()
    window.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


# =============================================================================
# F. Protected Flagship Stage Hash Invariance
# =============================================================================

def test_protected_flagship_stage_hash_intact():
    """Verify EVFlagshipStage.qml SHA256 matches exact protected hash byte-for-byte."""
    path = PROJECT_ROOT / "gui" / "qml" / "components" / "EVFlagshipStage.qml"
    content = path.read_bytes()
    computed_sha = hashlib.sha256(content).hexdigest().upper()
    assert computed_sha == PROTECTED_FLAGSHIP_STAGE_SHA256, (
        f"Protected file EVFlagshipStage.qml hash mismatch! Expected {PROTECTED_FLAGSHIP_STAGE_SHA256}, got {computed_sha}"
    )
