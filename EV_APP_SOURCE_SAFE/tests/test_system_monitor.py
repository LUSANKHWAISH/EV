"""
Unit, integration, and lifecycle tests for EVSystemMonitor (Task 014F-16).

Verifies:
- Lifecycle: start, stop, restart, idempotent double start/stop, thread termination.
- Hysteresis & debouncing: transient spikes vs. sustained conditions, recovery, flapping prevention.
- Domain observers: CPU, Memory, Disk, Process, Network, System.
- Failure isolation: single observer exception does not crash the subsystem.
- Event bus integration: SYSTEM_OBSERVATION, SYSTEM_ALERT, SYSTEM_ALERT_RECOVERED.
- Bounded history & context summary.
- Memory store integration: routine samples omitted, only alert facts persisted.
- 20-cycle lifecycle leak test: zero thread growth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import threading
import time
from typing import List

import pytest

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType
from core.system_monitor import (
    EVSystemMonitor,
    SystemAlert,
    SystemMetricDomain,
    SystemMonitorConfig,
    SystemObservation,
    SystemObservationSeverity,
)


@pytest.fixture
def event_bus() -> EVEventBus:
    return EVEventBus()


@pytest.fixture
def fast_config() -> SystemMonitorConfig:
    """Config with short sustained durations for fast deterministic testing."""
    return SystemMonitorConfig(
        polling_interval_seconds=0.05,
        cpu_warning_threshold=90.0,
        cpu_sustained_seconds=0.2,
        cpu_recovery_threshold=75.0,
        cpu_recovery_seconds=0.1,
        memory_warning_threshold=90.0,
        memory_sustained_seconds=0.2,
        memory_recovery_threshold=80.0,
        memory_recovery_seconds=0.1,
        disk_warning_percent=10.0,
        disk_critical_percent=5.0,
        disk_sustained_seconds=0.2,
        disk_recovery_percent=12.0,
        disk_recovery_seconds=0.1,
        process_high_cpu_threshold=80.0,
        process_high_cpu_sustained_seconds=0.2,
        process_high_cpu_recovery_threshold=50.0,
        process_high_cpu_recovery_seconds=0.1,
        process_sample_interval_seconds=100.0,
        max_retained_observations=10,
        max_retained_alerts=5,
    )


@pytest.fixture(autouse=True)
def mock_benign_background():
    """Isolate tests from real Windows host CPU spikes / background processes."""
    mock_p = MagicMock()
    mock_p.info = {"pid": 9999, "name": "idle_test.exe", "cpu_percent": 0.5, "memory_percent": 1.0}
    with patch("psutil.process_iter", return_value=[mock_p]):
        yield


# -----------------------------------------------------------------------------
# 1. Lifecycle Tests
# -----------------------------------------------------------------------------

def test_monitor_initialization(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    assert not monitor.is_running
    assert len(monitor.get_recent_observations()) == 0
    assert len(monitor.get_active_alerts()) == 0


def test_monitor_start_stop(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    monitor.start()
    assert monitor.is_running

    time.sleep(0.1)

    monitor.stop(timeout=2.0)
    assert not monitor.is_running


def test_monitor_idempotent_start_stop(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    monitor.start()
    worker_1 = monitor._worker_thread
    monitor.start()  # Duplicate start
    assert monitor._worker_thread is worker_1

    monitor.stop(timeout=2.0)
    assert not monitor.is_running
    monitor.stop(timeout=2.0)  # Duplicate stop
    assert not monitor.is_running


def test_monitor_restart(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    monitor.start()
    assert monitor.is_running
    monitor.stop(timeout=2.0)
    assert not monitor.is_running

    monitor.start()
    assert monitor.is_running
    monitor.stop(timeout=2.0)
    assert not monitor.is_running


# -----------------------------------------------------------------------------
# 2. Synchronous Poll & Domain Observers
# -----------------------------------------------------------------------------

def test_poll_once_collects_all_domains(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    observations = monitor.poll_once()

    assert len(observations) >= 6
    domains = {obs.domain for obs in observations}
    assert SystemMetricDomain.CPU in domains
    assert SystemMetricDomain.MEMORY in domains
    assert SystemMetricDomain.DISK in domains
    assert SystemMetricDomain.PROCESS in domains
    assert SystemMetricDomain.NETWORK in domains
    assert SystemMetricDomain.SYSTEM in domains


def test_context_summary(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)
    monitor.poll_once()
    summary = monitor.get_context_summary()

    assert "cpu_percent" in summary
    assert "memory_used_percent" in summary
    assert "disk_free_percent" in summary
    assert "process_count" in summary
    assert "uptime_seconds" in summary
    assert "active_alerts_count" in summary
    assert isinstance(summary["active_alerts"], list)


# -----------------------------------------------------------------------------
# 3. Hysteresis & Debouncing: CPU Spikes vs. Sustained Condition
# -----------------------------------------------------------------------------

def test_cpu_transient_spike_does_not_alert(fast_config, event_bus):
    """
    A brief spike in CPU does NOT trigger an alert if it recovers
    before the sustained duration (0.2s) elapses.
    """
    events_received: List[EVEvent] = []
    event_bus.subscribe(
        lambda e: events_received.append(e),
        event_types=[EVEventType.SYSTEM_ALERT, EVEventType.SYSTEM_ALERT_RECOVERED],
    )

    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    # Spike: 95% CPU at t=0
    with patch("psutil.cpu_percent", return_value=95.0):
        monitor.poll_once()

    # Recovery: 50% CPU immediately at t=0.05 (less than 0.2s sustained)
    time.sleep(0.05)
    with patch("psutil.cpu_percent", return_value=50.0):
        monitor.poll_once()

    cpu_alerts = [e for e in events_received if e.data.get("domain") == "cpu"]
    assert len(cpu_alerts) == 0
    active_cpu_alerts = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.CPU]
    assert len(active_cpu_alerts) == 0


def test_cpu_sustained_condition_triggers_alert_and_recovers(fast_config, event_bus):
    """
    CPU >= 90% sustained for >= 0.2s triggers SYSTEM_ALERT.
    Then dropping <= 75% sustained for >= 0.1s triggers SYSTEM_ALERT_RECOVERED.
    """
    alerts_received: List[EVEvent] = []
    recovers_received: List[EVEvent] = []

    event_bus.subscribe(
        lambda e: alerts_received.append(e),
        event_types=[EVEventType.SYSTEM_ALERT],
    )
    event_bus.subscribe(
        lambda e: recovers_received.append(e),
        event_types=[EVEventType.SYSTEM_ALERT_RECOVERED],
    )

    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    # 1. Condition breached at t=0
    with patch("psutil.cpu_percent", return_value=95.0):
        monitor.poll_once()
        cpu_alerts = [e for e in alerts_received if e.data.get("domain") == "cpu"]
        assert len(cpu_alerts) == 0

        # Wait past sustained threshold (0.2s)
        time.sleep(0.25)
        monitor.poll_once()

    cpu_alerts = [e for e in alerts_received if e.data.get("domain") == "cpu"]
    assert len(cpu_alerts) == 1
    alert_event = cpu_alerts[0]
    assert alert_event.severity == EVEventSeverity.WARNING
    assert alert_event.data["domain"] == "cpu"
    assert alert_event.data["value"] == 95.0

    active_cpu = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.CPU]
    assert len(active_cpu) == 1

    # 2. Deadband value (80% CPU): alert must remain active, no flapping
    with patch("psutil.cpu_percent", return_value=80.0):
        time.sleep(0.05)
        monitor.poll_once()
        cpu_alerts = [e for e in alerts_received if e.data.get("domain") == "cpu"]
        cpu_recovers = [e for e in recovers_received if e.data.get("domain") == "cpu"]
        assert len(cpu_alerts) == 1
        assert len(cpu_recovers) == 0
        active_cpu = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.CPU]
        assert len(active_cpu) == 1

    # 3. Recovery zone (70% CPU): must sustain for >= 0.1s
    with patch("psutil.cpu_percent", return_value=70.0):
        monitor.poll_once()
        cpu_recovers = [e for e in recovers_received if e.data.get("domain") == "cpu"]
        assert len(cpu_recovers) == 0  # Not yet sustained

        time.sleep(0.15)
        monitor.poll_once()

    cpu_recovers = [e for e in recovers_received if e.data.get("domain") == "cpu"]
    assert len(cpu_recovers) == 1
    assert cpu_recovers[0].severity == EVEventSeverity.INFO
    active_cpu = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.CPU]
    assert len(active_cpu) == 0


# -----------------------------------------------------------------------------
# 4. Memory & Disk Observers
# -----------------------------------------------------------------------------

def test_memory_sustained_alert_and_recovery(fast_config, event_bus):
    alerts_received: List[EVEvent] = []
    recovers_received: List[EVEvent] = []

    event_bus.subscribe(lambda e: alerts_received.append(e), event_types=[EVEventType.SYSTEM_ALERT])
    event_bus.subscribe(lambda e: recovers_received.append(e), event_types=[EVEventType.SYSTEM_ALERT_RECOVERED])

    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    mock_vmem_high = MagicMock(percent=96.0, available=1024**3, total=32 * 1024**3)
    mock_vmem_normal = MagicMock(percent=60.0, available=12 * 1024**3, total=32 * 1024**3)

    with patch("psutil.cpu_percent", return_value=10.0), patch("psutil.virtual_memory", return_value=mock_vmem_high):
        monitor.poll_once()
        time.sleep(0.25)
        monitor.poll_once()

    mem_alerts = [e for e in alerts_received if e.data.get("domain") == "memory"]
    assert len(mem_alerts) == 1
    assert mem_alerts[0].data["domain"] == "memory"
    active_mem = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.MEMORY]
    assert len(active_mem) == 1

    with patch("psutil.cpu_percent", return_value=10.0), patch("psutil.virtual_memory", return_value=mock_vmem_normal):
        monitor.poll_once()
        time.sleep(0.15)
        monitor.poll_once()

    mem_recovers = [e for e in recovers_received if e.data.get("domain") == "memory"]
    assert len(mem_recovers) == 1
    active_mem = [a for a in monitor.get_active_alerts() if a.domain == SystemMetricDomain.MEMORY]
    assert len(active_mem) == 0


def test_disk_low_space_and_critical_alert(fast_config, event_bus):
    alerts_received: List[EVEvent] = []
    event_bus.subscribe(lambda e: alerts_received.append(e), event_types=[EVEventType.SYSTEM_ALERT])

    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    # 4% free space -> Critical threshold
    mock_disk_crit = MagicMock(total=100 * 1024**3, free=4 * 1024**3, used=96 * 1024**3)
    with patch("psutil.cpu_percent", return_value=10.0), patch("psutil.disk_usage", return_value=mock_disk_crit):
        monitor.poll_once()
        time.sleep(0.25)
        monitor.poll_once()

    disk_alerts = [e for e in alerts_received if e.data.get("domain") == "disk"]
    assert len(disk_alerts) == 1
    assert disk_alerts[0].severity == EVEventSeverity.CRITICAL
    assert disk_alerts[0].data["domain"] == "disk"


# -----------------------------------------------------------------------------
# 5. Process Observer & Mock Isolation
# -----------------------------------------------------------------------------

def test_process_observer_top_consumers(fast_config, event_bus):
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    mock_p1 = MagicMock()
    mock_p1.info = {"pid": 1001, "name": "heavy_proc.exe", "cpu_percent": 85.0, "memory_percent": 12.0}
    mock_p2 = MagicMock()
    mock_p2.info = {"pid": 1002, "name": "idle_proc.exe", "cpu_percent": 1.0, "memory_percent": 2.0}

    with patch("psutil.process_iter", return_value=[mock_p1, mock_p2]):
        observations = monitor._observe_processes(datetime.now(timezone.utc), time.monotonic())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.domain == SystemMetricDomain.PROCESS
    assert obs.metadata["top_cpu"][0]["name"] == "heavy_proc.exe"
    assert obs.metadata["top_cpu"][0]["cpu_percent"] == 85.0


# -----------------------------------------------------------------------------
# 6. Failure Isolation
# -----------------------------------------------------------------------------

def test_observer_failure_isolation(fast_config, event_bus):
    """
    If one observer crashes (e.g. disk failure), the remaining observers
    run and a diagnostic warning observation is captured.
    """
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    with patch.object(monitor, "_observe_disk", side_effect=PermissionError("Disk access denied")):
        observations = monitor.poll_once()

    domains = {obs.domain for obs in observations}
    assert SystemMetricDomain.CPU in domains
    assert SystemMetricDomain.MEMORY in domains
    assert SystemMetricDomain.PROCESS in domains

    # Verify diagnostic error captured
    diag_errors = [o for o in observations if o.metric == "disk_observer_error"]
    assert len(diag_errors) == 1
    assert diag_errors[0].severity == SystemObservationSeverity.WARNING


# -----------------------------------------------------------------------------
# 7. Bounded History & Memory Store Integration
# -----------------------------------------------------------------------------

def test_bounded_observation_history(fast_config, event_bus):
    # max_retained_observations is 10 in fast_config
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    # 3 poll passes will generate >= 18 observations, exceeding 10
    for _ in range(3):
        monitor.poll_once()

    assert len(monitor._observations) == 10
    assert len(monitor.get_recent_observations(limit=50)) == 10


def test_memory_store_only_records_meaningful_alerts(fast_config, event_bus):
    mock_memory_store = MagicMock()
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus, memory_store=mock_memory_store)

    # Normal polling must NEVER call set_environment_fact
    with patch("psutil.cpu_percent", return_value=10.0):
        monitor.poll_once()
        assert mock_memory_store.set_environment_fact.call_count == 0

    # Sustained alert MUST call set_environment_fact
    with patch("psutil.cpu_percent", return_value=95.0):
        monitor.poll_once()
        time.sleep(0.25)
        monitor.poll_once()

    assert mock_memory_store.set_environment_fact.call_count == 1
    args, kwargs = mock_memory_store.set_environment_fact.call_args
    assert "cpu:utilization" in kwargs["fact_key"]


# -----------------------------------------------------------------------------
# 8. 20-Cycle Lifecycle Leak Test
# -----------------------------------------------------------------------------

def test_20_cycle_lifecycle_leak(fast_config, event_bus):
    initial_threads = threading.active_count()
    monitor = EVSystemMonitor(config=fast_config, event_bus=event_bus)

    for _ in range(20):
        monitor.start()
        monitor.start()  # Idempotent
        monitor.stop(timeout=2.0)
        monitor.stop(timeout=2.0)  # Idempotent

    final_threads = threading.active_count()
    assert final_threads == initial_threads
