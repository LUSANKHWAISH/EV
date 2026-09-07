"""
Comprehensive Test Suite for 018-D: Telemetry + Awareness UI.
Covers Telemetry, Awareness, Lifecycle, QML presentation, and Invariant Security.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import threading
import time
from typing import Dict, Any
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtTest import QSignalSpy

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType, EVState
from core.proactive_awareness import (
    AwarenessCategory,
    AwarenessEvent,
    AwarenessSeverity,
    AwarenessState,
    EVProactiveAwarenessEngine,
    NotificationPolicy,
    ProactiveAwarenessConfig,
)
from core.system_monitor import (
    EVSystemMonitor,
    SystemAlert,
    SystemMetricDomain,
    SystemMonitorConfig,
    SystemObservation,
    SystemObservationSeverity,
)
from gui.bridge import GuiBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QML_COMPONENTS = PROJECT_ROOT / "gui" / "qml" / "components"


@pytest.fixture(scope="session")
def qapp():
    """Ensure a single QGuiApplication exists across the test session."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def event_bus():
    """Create a fresh EVEventBus in IDLE state."""
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, qapp):
    """Create a fresh GuiBridge wired to the test event bus."""
    b = GuiBridge(event_bus)
    yield b
    b.shutdown()


# =============================================================================
# 1. Telemetry Tests (Requirements 1-10)
# =============================================================================

def test_telemetry_default_unavailable_state(bridge):
    """1. Test default initial telemetry state: unavailable with safe zeros and empty timestamp."""
    assert bridge.telemetryAvailable is False
    assert bridge.telemetryTimestamp == ""
    assert bridge.telemetryAgeMs == -1
    assert bridge.telemetryCpuPercent == 0.0
    assert bridge.telemetryMemoryPercent == 0.0
    assert bridge.telemetryMemoryUsedMb == 0
    assert bridge.telemetryMemoryTotalMb == 0
    assert bridge.telemetryDiskFreePercent == 0.0
    assert bridge.telemetryDiskFreeGb == 0.0
    assert bridge.telemetryProcessCount == 0
    assert bridge.telemetryTopProcessName == ""
    assert bridge.telemetryTopProcessCpuPercent == 0.0
    assert bridge.telemetryTopProcessMemoryMb == 0
    assert bridge.telemetryNetworkConnected is False


def test_telemetry_populated_from_system_observation(bridge, event_bus, qapp):
    """2. Test populated telemetry ingestion via SYSTEM_OBSERVATION event."""
    sample_snapshot = {
        "cpu_percent": 35.4,
        "memory_used_percent": 58.2,
        "memory_available_bytes": 8 * 1024**3,
        "memory_total_bytes": 16 * 1024**3,
        "disk_free_percent": 72.0,
        "disk_free_bytes": 200 * 1024**3,
        "process_count": 165,
        "top_cpu_process": "code.exe",
        "top_cpu_percent": 12.5,
        "network_connected": True,
    }

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        message="System telemetry update",
        data={"snapshot": sample_snapshot},
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is True
    assert bridge.telemetryTimestamp != ""
    assert bridge.telemetryAgeMs >= 0


def test_telemetry_cpu_binding(bridge, event_bus, qapp):
    """3. Test CPU utilization percentage property and change notification."""
    spy = QSignalSpy(bridge.telemetryCpuPercentChanged)
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"cpu_percent": 42.7}},
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryCpuPercent == 42.7
    assert spy.count() == 1
    assert abs(spy.at(0)[0] - 42.7) < 0.01


def test_telemetry_memory_binding(bridge, event_bus, qapp):
    """4. Test Memory percentage, used MB, and total MB properties and signals."""
    spy_pct = QSignalSpy(bridge.telemetryMemoryPercentChanged)
    spy_used = QSignalSpy(bridge.telemetryMemoryUsedMbChanged)
    spy_total = QSignalSpy(bridge.telemetryMemoryTotalMbChanged)

    total_bytes = 16 * 1024**3
    avail_bytes = 6 * 1024**3
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "snapshot": {
                "memory_used_percent": 62.5,
                "memory_total_bytes": total_bytes,
                "memory_available_bytes": avail_bytes,
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryMemoryPercent == 62.5
    assert bridge.telemetryMemoryTotalMb == 16384
    assert bridge.telemetryMemoryUsedMb == 10240
    assert spy_pct.count() == 1
    assert spy_used.count() == 1
    assert spy_total.count() == 1


def test_telemetry_disk_binding(bridge, event_bus, qapp):
    """5. Test Disk free percentage and disk free GB properties and signals."""
    spy_pct = QSignalSpy(bridge.telemetryDiskFreePercentChanged)
    spy_gb = QSignalSpy(bridge.telemetryDiskFreeGbChanged)

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "snapshot": {
                "disk_free_percent": 45.0,
                "disk_free_bytes": 100 * (1024**3),
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryDiskFreePercent == 45.0
    assert bridge.telemetryDiskFreeGb == 100.0
    assert spy_pct.count() == 1
    assert spy_gb.count() == 1


def test_telemetry_network_binding(bridge, event_bus, qapp):
    """6. Test Network connectivity boolean property and signal."""
    spy = QSignalSpy(bridge.telemetryNetworkConnectedChanged)

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"network_connected": True}},
    )
    QCoreApplication.processEvents()
    assert bridge.telemetryNetworkConnected is True
    assert spy.count() == 1

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"network_connected": False}},
    )
    QCoreApplication.processEvents()
    assert bridge.telemetryNetworkConnected is False
    assert spy.count() == 2


def test_telemetry_process_binding(bridge, event_bus, qapp):
    """7. Test process count, top process name, and top CPU percentage."""
    spy_cnt = QSignalSpy(bridge.telemetryProcessCountChanged)
    spy_name = QSignalSpy(bridge.telemetryTopProcessNameChanged)

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "snapshot": {
                "process_count": 215,
                "top_cpu_process": "python.exe",
                "top_cpu_percent": 24.8,
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryProcessCount == 215
    assert bridge.telemetryTopProcessName == "python.exe"
    assert bridge.telemetryTopProcessCpuPercent == 24.8
    assert spy_cnt.count() == 1
    assert spy_name.count() == 1


def test_telemetry_stale_state(bridge, event_bus, qapp):
    """8. Test telemetry age calculation for detecting stale telemetry (>10000ms)."""
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"cpu_percent": 20.0}},
    )
    QCoreApplication.processEvents()

    # Fresh observation age should be small (< 2000ms)
    assert 0 <= bridge.telemetryAgeMs < 2000

    # Simulate aged observation by manipulating the private timestamp
    from datetime import timedelta
    bridge._telemetry_timestamp = datetime.now(timezone.utc) - timedelta(seconds=15)

    # Now telemetryAgeMs must reflect > 10000ms (STALE)
    assert bridge.telemetryAgeMs > 10000


def test_telemetry_queued_cross_thread_update(bridge, event_bus, qapp):
    """9. Test thread safety: telemetry published from background thread arrives via Qt QueuedConnection."""
    spy = QSignalSpy(bridge.telemetryUpdated)

    def _worker():
        event_bus.publish(
            event_type=EVEventType.SYSTEM_OBSERVATION,
            source="worker_thread",
            data={"snapshot": {"cpu_percent": 55.5}},
        )

    t = threading.Thread(target=_worker)
    t.start()
    t.join()

    # Allow Qt main thread event loop to process queued slot
    QCoreApplication.processEvents()

    assert spy.count() == 1
    assert bridge.telemetryCpuPercent == 55.5


def test_telemetry_no_direct_backend_execution_path(bridge):
    """10. Invariant: GuiBridge must expose zero execution authority or backend mutation methods."""
    forbidden_methods = [
        "execute", "execute_command", "run_powershell", "execute_pipeline",
        "kill_process", "repair", "mutate", "rollback", "approve_all"
    ]
    for method in forbidden_methods:
        assert not hasattr(bridge, method), f"Security violation: GuiBridge exposes {method}"


# =============================================================================
# 2. Awareness Tests (Requirements 11-16)
# =============================================================================

def test_awareness_title_and_message_propagation(bridge, event_bus, qapp):
    """11. Test propagation of proactive awareness title and message to GuiBridge."""
    spy_title = QSignalSpy(bridge.latestAwarenessTitleChanged)
    spy_msg = QSignalSpy(bridge.latestAwarenessMessageChanged)

    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={
            "awareness_id": "aw-001",
            "title": "Elevated CPU Utilization",
            "message": "Process 'code.exe' consuming 85% CPU",
            "severity": "WARNING",
        },
    )
    QCoreApplication.processEvents()

    assert bridge.latestAwarenessTitle == "Elevated CPU Utilization"
    assert bridge.latestAwarenessMessage == "Process 'code.exe' consuming 85% CPU"
    assert spy_title.count() == 1
    assert spy_msg.count() == 1


def test_awareness_severity_propagation(bridge, event_bus, qapp):
    """12. Test propagation and sanitization of awareness severity (INFO, NOTICE, WARNING, CRITICAL)."""
    spy_sev = QSignalSpy(bridge.latestAwarenessSeverityChanged)

    # Valid severity: CRITICAL
    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={"title": "Critical Storage", "message": "Drive C: critically low", "severity": "CRITICAL"},
    )
    QCoreApplication.processEvents()
    assert bridge.latestAwarenessSeverity == "CRITICAL"
    assert spy_sev.count() == 1

    # Invalid severity coerced safely to INFO
    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={"title": "Test", "message": "Notice", "severity": "UNKNOWN_SEV"},
    )
    QCoreApplication.processEvents()
    assert bridge.latestAwarenessSeverity == "INFO"
    assert spy_sev.count() == 2


def test_awareness_event_presentation(bridge, event_bus, qapp):
    """13. Test awarenessEventChanged signal emits awareness_id, title, message."""
    spy_event = QSignalSpy(bridge.awarenessEventChanged)

    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={
            "awareness_id": "aw-42",
            "title": "Network Lost",
            "message": "No active network adapters detected",
            "severity": "WARNING",
        },
    )
    QCoreApplication.processEvents()

    assert spy_event.count() == 1
    args = spy_event.at(0)
    assert args[0] == "aw-42"
    assert args[1] == "Network Lost"
    assert args[2] == "No active network adapters detected"


def test_awareness_recovery_and_clear(bridge, event_bus, qapp):
    """14. Test AWARENESS_RESOLVED clears awareness state and clearAwareness slot works presentation-only."""
    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={"title": "High Memory", "message": "RAM usage high", "severity": "WARNING"},
    )
    QCoreApplication.processEvents()
    assert bridge.latestAwarenessTitle == "High Memory"

    # Backend recovery event resolves awareness
    event_bus.publish(
        event_type=EVEventType.AWARENESS_RESOLVED,
        source="proactive_awareness",
        data={"title": "High Memory Recovered", "message": "RAM normal"},
    )
    QCoreApplication.processEvents()

    assert bridge.latestAwarenessTitle == ""
    assert bridge.latestAwarenessMessage == ""
    assert bridge.latestAwarenessSeverity == "INFO"

    # Test clearAwareness slot
    bridge._latest_awareness_title = "Manual Alert"
    bridge._latest_awareness_message = "Manual Message"
    bridge.clearAwareness()
    assert bridge.latestAwarenessTitle == ""
    assert bridge.latestAwarenessMessage == ""


def test_awareness_bounded_and_sanitized_presentation(bridge, event_bus, qapp):
    """15. Test awareness title is bounded to 100 chars and message to 500 chars."""
    huge_title = "A" * 300
    huge_msg = "B" * 1500

    event_bus.publish(
        event_type=EVEventType.AWARENESS_EVENT,
        source="proactive_awareness",
        data={"title": huge_title, "message": huge_msg, "severity": "INFO"},
    )
    QCoreApplication.processEvents()

    assert len(bridge.latestAwarenessTitle) == 100
    assert len(bridge.latestAwarenessMessage) == 500


def test_awareness_no_execution_authority_from_presentation(bridge):
    """16. Invariant: Awareness ≠ Authority. Zero execution methods exposed."""
    forbidden = ["execute_suggestion", "apply_fix", "dismiss_backend", "override_risk"]
    for attr in forbidden:
        assert not hasattr(bridge, attr)


# =============================================================================
# 3. Lifecycle Tests (Requirements 17-22)
# =============================================================================

def test_system_monitor_startup_and_shutdown(event_bus):
    """17-18. Test EVSystemMonitor starts thread and stops cleanly on shutdown."""
    config = SystemMonitorConfig(polling_interval_seconds=10.0)
    monitor = EVSystemMonitor(config=config, event_bus=event_bus)

    assert not monitor.is_running
    monitor.start()
    assert monitor.is_running

    monitor.stop(timeout=2.0)
    assert not monitor.is_running


def test_awareness_engine_startup_and_shutdown(event_bus):
    """19-20. Test EVProactiveAwarenessEngine starts and unregisters subscriptions cleanly."""
    engine = EVProactiveAwarenessEngine(event_bus=event_bus)

    assert not engine.is_running
    engine.start()
    assert engine.is_running
    assert len(engine._subscription_tokens) > 0

    engine.stop()
    assert not engine.is_running
    assert len(engine._subscription_tokens) == 0


def test_subsystems_idempotent_startup(event_bus):
    """21. Test calling start() repeatedly does not create duplicate workers."""
    config = SystemMonitorConfig(polling_interval_seconds=10.0)
    monitor = EVSystemMonitor(config=config, event_bus=event_bus)
    awareness = EVProactiveAwarenessEngine(event_bus=event_bus, system_monitor=monitor)

    monitor.start()
    thread_1 = monitor._worker_thread
    monitor.start()
    assert monitor._worker_thread is thread_1

    awareness.start()
    tokens_1 = list(awareness._subscription_tokens)
    awareness.start()
    assert awareness._subscription_tokens == tokens_1

    awareness.stop()
    monitor.stop(timeout=2.0)


def test_no_worker_thread_leak(event_bus):
    """22. Test 5 consecutive start/stop cycles clean up threads without leakage."""
    initial_threads = threading.active_count()

    for _ in range(5):
        config = SystemMonitorConfig(polling_interval_seconds=10.0)
        m = EVSystemMonitor(config=config, event_bus=event_bus)
        a = EVProactiveAwarenessEngine(event_bus=event_bus, system_monitor=m)
        m.start()
        a.start()
        a.stop()
        m.stop(timeout=2.0)

    # After joining, active threads should return to baseline
    assert threading.active_count() <= initial_threads + 1


# =============================================================================
# 4. QML Presentation & Boundary Tests (Requirements 23-27)
# =============================================================================

def test_telemetry_rail_component_loads(bridge, qapp):
    """23. Test EVTelemetryRail.qml instantiates without QML errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    qml_file = QML_COMPONENTS / "EVTelemetryRail.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_file)))

    assert not component.isError(), f"EVTelemetryRail errors: {[e.toString() for e in component.errors()]}"
    item = component.create()
    assert item is not None
    assert item.property("implicitWidth") == 72
    item.deleteLater()


def test_awareness_banner_component_loads(bridge, qapp):
    """24. Test EVSystemAlertBanner.qml instantiates and has zero height when empty."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    qml_file = QML_COMPONENTS / "EVSystemAlertBanner.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_file)))

    assert not component.isError(), f"EVSystemAlertBanner errors: {[e.toString() for e in component.errors()]}"
    banner = component.create()
    assert banner is not None
    assert banner.property("hasContent") is False
    assert banner.property("implicitHeight") == 0
    banner.deleteLater()


def test_qml_uses_guibridge_properties_only(bridge, event_bus, qapp):
    """25. Test EVTelemetryRail values reflect GuiBridge properties declaratively."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    qml_file = QML_COMPONENTS / "EVTelemetryRail.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_file)))
    rail = component.create()
    assert rail is not None

    # Standby initially
    assert rail.property("isStandby") is True
    assert rail.property("isLive") is False

    # Publish observation
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"cpu_percent": 75.0, "memory_used_percent": 82.0}},
    )
    QCoreApplication.processEvents()

    assert rail.property("isStandby") is False
    assert rail.property("isLive") is True
    assert rail.property("cpuPercent") == 75.0
    assert rail.property("memPercent") == 82.0
    rail.deleteLater()


def test_approval_overlay_remains_dominant(bridge, qapp):
    """26. Test in EVWindow, EVApprovalOverlay has highest z-index (z: 100)."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)

    qml_file = QML_COMPONENTS / "EVWindow.qml"
    component = QQmlComponent(engine, QUrl.fromLocalFile(str(qml_file)))
    assert not component.isError(), f"EVWindow errors: {[e.toString() for e in component.errors()]}"
    window = component.create()
    assert window is not None

    overlay = window.findChild(object, "approvalOverlay")
    banner = window.findChild(object, "systemAlertBanner")

    assert overlay is not None
    assert banner is not None
    assert overlay.property("z") == 100
    assert banner.property("z") == 10
    assert overlay.property("z") > banner.property("z")
    window.deleteLater()


def test_protected_flagship_and_input_hashes_untouched():
    """27. Test protected files EVCommandInput.qml and EVFlagshipStage.qml have identical hashes."""
    expected_input = "6B6C231D7BF04F9FFBD3E0BD860B16A9CE6EBE4AC5BFD943EB83E70D3602AF13"
    expected_stage = "B7EEE6E5C3AD6A6C8EA85188767CE5B44EF3FE00D83FB202FB99F0B33FD689C8"

    input_file = QML_COMPONENTS / "EVCommandInput.qml"
    stage_file = QML_COMPONENTS / "EVFlagshipStage.qml"

    actual_input = hashlib.sha256(input_file.read_bytes()).hexdigest().upper()
    actual_stage = hashlib.sha256(stage_file.read_bytes()).hexdigest().upper()

    assert actual_input == expected_input, f"EVCommandInput.qml hash changed! {actual_input}"
    assert actual_stage == expected_stage, f"EVFlagshipStage.qml hash changed! {actual_stage}"
