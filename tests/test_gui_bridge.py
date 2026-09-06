# Real unit tests for GuiBridge and EVEventBus integration.
import sys
import threading
from typing import Optional

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy

from core.events import EVEvent, EVEventBus
from core.models import EVEventSeverity, EVEventType, EVState
from gui.bridge import GuiBridge


@pytest.fixture
def app():
    """Ensure a QGuiApplication instance exists for Qt event loop and signals."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv)
    yield instance


@pytest.fixture
def event_bus():
    """Create an EVEventBus instance with IDLE initial state."""
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, app):
    """Create a GuiBridge instance bound to the test event bus."""
    b = GuiBridge(event_bus)
    yield b
    b.shutdown()


def test_bridge_initializes_with_bus_state(event_bus, app):
    """1. Test that the bridge's initial state matches the bus's current state."""
    custom_bus = EVEventBus(initial_state=EVState.PLANNING)
    custom_bridge = GuiBridge(custom_bus)
    assert custom_bridge.currentState == EVState.PLANNING.value
    assert custom_bridge._state == EVState.PLANNING
    custom_bridge.shutdown()


def test_bus_state_changed_reaches_bridge(bridge, event_bus, app):
    """2. Test that a STATE_CHANGED event from the bus updates the bridge's state."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    new_state = EVState.LISTENING
    event_bus.set_state(new_state)
    QCoreApplication.processEvents()

    assert bridge.currentState == new_state.value
    assert bridge._state == new_state
    assert spy.count() == 1
    assert spy.at(0)[0] == new_state.value


def test_same_state_causes_no_false_signal(bridge, event_bus, app):
    """3. Test that setting the same state causes no false signal or duplicate transition."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    current_state = event_bus.current_state

    result = event_bus.set_state(current_state)
    QCoreApplication.processEvents()

    assert result.changed is False
    assert bridge.currentState == current_state.value
    assert spy.count() == 0


def test_status_event_does_not_modify_state(bridge, event_bus, app):
    """4. Test that publishing a STATUS event does not modify the bridge state."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    initial_state = bridge.currentState

    event_bus.publish(
        event_type=EVEventType.STATUS,
        source="system",
        message="Telemetry heartbeat ping",
        severity=EVEventSeverity.INFO,
    )
    QCoreApplication.processEvents()

    assert bridge.currentState == initial_state
    assert spy.count() == 0


def test_error_event_does_not_imply_failed(bridge, event_bus, app):
    """5. Test that an ERROR event by itself does not force the bridge state to FAILED."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    initial_state = bridge.currentState

    event_bus.publish(
        event_type=EVEventType.ERROR,
        source="tool_runner",
        message="Non-fatal command timeout warning",
        severity=EVEventSeverity.ERROR,
    )
    QCoreApplication.processEvents()

    assert bridge.currentState == initial_state
    assert bridge.currentState != EVState.FAILED.value
    assert spy.count() == 0


def test_unusual_transition_remains_observable(bridge, event_bus, app):
    """6. Test that an unusual transition (e.g. IDLE -> VERIFYING) is observable."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    unusual_state = EVState.VERIFYING

    event_bus.set_state(unusual_state)
    QCoreApplication.processEvents()

    assert bridge.currentState == unusual_state.value
    assert spy.count() == 1
    assert spy.at(0)[0] == unusual_state.value


def test_bridge_uses_canonical_enums(bridge, event_bus, app):
    """7. Test that the bridge uses canonical core.models enums."""
    assert isinstance(bridge._state, EVState)
    assert bridge._state == EVState.IDLE

    event_bus.set_state(EVState.AWAITING_APPROVAL)
    QCoreApplication.processEvents()

    assert isinstance(bridge._state, EVState)
    assert bridge._state == EVState.AWAITING_APPROVAL
    assert bridge.currentState == EVState.AWAITING_APPROVAL.value


def test_all_subscriptions_removed_by_shutdown(event_bus, app):
    """8. Test that all subscriptions are removed from the event bus upon shutdown."""
    bridge = GuiBridge(event_bus)
    assert len(bridge._subscription_tokens) > 0
    tokens = list(bridge._subscription_tokens)

    for token in tokens:
        assert token in event_bus._subscriptions

    bridge.shutdown()
    assert len(bridge._subscription_tokens) == 0

    for token in tokens:
        assert token not in event_bus._subscriptions


def test_shutdown_is_idempotent(bridge):
    """9. Test that calling shutdown() multiple times is safe and maintains empty tokens."""
    bridge.shutdown()
    assert len(bridge._subscription_tokens) == 0
    bridge.shutdown()
    assert len(bridge._subscription_tokens) == 0


def test_events_after_shutdown_do_not_update_bridge(bridge, event_bus, app):
    """10. Test that events published after shutdown do not update the bridge."""
    bridge.shutdown()
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()

    event_bus.set_state(EVState.EXECUTING)
    QCoreApplication.processEvents()

    assert bridge.currentState == EVState.IDLE.value
    assert spy.count() == 0


def test_bridge_callback_does_not_create_subscriber_errors(bridge, event_bus, app):
    """11. Test that bridge event bus callbacks do not produce subscriber errors."""
    result = event_bus.set_state(EVState.SPEAKING)
    assert result.publish_result is not None
    assert result.publish_result.failed_count == 0
    assert len(result.publish_result.subscriber_errors) == 0

    QCoreApplication.processEvents()
    assert bridge.currentState == EVState.SPEAKING.value


def test_no_execution_or_filesystem_behavior_exists(bridge):
    """12. Test that the bridge exposes no execution or filesystem mutation functionality."""
    forbidden_methods = [
        "execute_command",
        "mutate_filesystem",
        "run_powershell",
        "backup_file",
        "restore_file",
        "delete_file",
        "write_file",
    ]
    for method in forbidden_methods:
        assert not hasattr(bridge, method), f"Bridge should not expose {method}"


class StatePublisherWorker(threading.Thread):
    """Worker thread that publishes a state change to the event bus."""

    def __init__(self, bus: EVEventBus, target_state: EVState) -> None:
        super().__init__()
        self.bus = bus
        self.target_state = target_state
        self.exception: Optional[Exception] = None

    def run(self) -> None:
        try:
            self.bus.set_state(self.target_state)
        except Exception as exc:
            self.exception = exc


def test_worker_thread_event_reaches_qt_state_via_queued_handoff(bridge, event_bus, app):
    """13. Test that worker-thread events reach Qt state via queued handoff with deterministic sync."""
    spy = QSignalSpy(bridge.stateChanged)
    assert spy.isValid()
    worker = StatePublisherWorker(event_bus, EVState.PLANNING)
    worker.start()
    worker.join(timeout=3.0)

    assert not worker.is_alive(), "Worker thread timed out"
    assert worker.exception is None, f"Worker thread encountered exception: {worker.exception}"

    if spy.count() == 0:
        assert spy.wait(3000), "Timed out waiting for stateChanged signal from worker thread"

    assert spy.count() == 1
    assert spy.at(0)[0] == EVState.PLANNING.value
    assert bridge.currentState == EVState.PLANNING.value


def test_bridge_initializes_with_empty_task_and_observation(bridge):
    """Test 1: Bridge starts with safe empty/default values."""
    assert bridge.currentTask == ""
    assert bridge.latestObservation == ""


def test_action_started_updates_current_task(bridge, event_bus, app):
    """Test 2: ACTION_STARTED event updates currentTask."""
    spy = QSignalSpy(bridge.currentTaskChanged)
    assert spy.isValid()
    event_bus.publish(
        event_type=EVEventType.ACTION_STARTED,
        source="system",
        message="Scanning system",
    )
    QCoreApplication.processEvents()

    assert bridge.currentTask == "Scanning system"
    assert spy.count() == 1
    assert spy.at(0)[0] == "Scanning system"


def test_status_updates_latest_observation(bridge, event_bus, app):
    """Test 3: STATUS event updates latestObservation."""
    spy = QSignalSpy(bridge.latestObservationChanged)
    assert spy.isValid()
    event_bus.publish(
        event_type=EVEventType.STATUS,
        source="system",
        message="Observation complete",
    )
    QCoreApplication.processEvents()

    assert bridge.latestObservation == "Observation complete"
    assert spy.count() == 1
    assert spy.at(0)[0] == "Observation complete"


def test_action_completed_clears_task_and_updates_observation(bridge, event_bus, app):
    """Test 4: ACTION_COMPLETED event clears currentTask and updates observation if message present."""
    event_bus.publish(
        event_type=EVEventType.ACTION_STARTED,
        source="system",
        message="Scanning system",
    )
    QCoreApplication.processEvents()

    spy_task = QSignalSpy(bridge.currentTaskChanged)
    spy_obs = QSignalSpy(bridge.latestObservationChanged)

    event_bus.publish(
        event_type=EVEventType.ACTION_COMPLETED,
        source="system",
        message="Scan successful",
    )
    QCoreApplication.processEvents()

    assert bridge.currentTask == ""
    assert bridge.latestObservation == "Scan successful"
    assert spy_task.count() == 1
    assert spy_task.at(0)[0] == ""
    assert spy_obs.count() == 1
    assert spy_obs.at(0)[0] == "Scan successful"


def test_action_started_fallback_message(bridge, event_bus, app):
    """Test 6: Safe handling if message is empty/missing."""
    event_bus.publish(
        event_type=EVEventType.ACTION_STARTED,
        source="system",
        message=None,
    )
    QCoreApplication.processEvents()
    assert bridge.currentTask == "Active"


def test_status_empty_message_ignored(bridge, event_bus, app):
    """Test 6b: Empty status message doesn't overwrite observation."""
    event_bus.publish(
        event_type=EVEventType.STATUS,
        source="system",
        message="Old message",
    )
    QCoreApplication.processEvents()
    event_bus.publish(
        event_type=EVEventType.STATUS,
        source="system",
        message=None,
    )
    QCoreApplication.processEvents()
    assert bridge.latestObservation == "Old message"


def test_orchestrator_end_to_end(app):
    """
    Verify the complete production wiring:
    EVAgent -> EVEventBus -> GuiBridge -> QML property updates
    """
    from core.events import EVEventBus
    from core.models import EVState, AgentTask, AgentAction
    from core.orchestrator import EVOrchestrator
    from gui.bridge import GuiBridge
    from PySide6.QtCore import QCoreApplication
    from unittest.mock import patch

    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)
    orchestrator = EVOrchestrator(event_bus=event_bus)

    assert orchestrator.event_bus is bridge._event_bus, "Must share exact EventBus instance"

    task = AgentTask(
        task_id="t1",
        action=AgentAction.FIND_PROCESS,
        parameters={"name": "test_process"}
    )

    # Track signal emissions manually
    task_emissions = []
    obs_emissions = []

    bridge.currentTaskChanged.connect(lambda: task_emissions.append(bridge.currentTask))
    bridge.latestObservationChanged.connect(lambda: obs_emissions.append(bridge.latestObservation))

    with patch('core.agent.find_processes', return_value=[]):
        thread = orchestrator.execute_task(task)
        thread.join(timeout=3.0)
        assert not thread.is_alive(), "Orchestrator thread timed out"
        QCoreApplication.processEvents()

    assert len(task_emissions) >= 2
    assert len(obs_emissions) >= 2
    assert any(t.startswith("FIND_PROCESS") for t in task_emissions)
    assert any(obs != "" for obs in obs_emissions)


def test_bridge_approval_contract_defaults(bridge):
    """Verify default initial values for approval presentation properties."""
    assert bridge.approvalPending is False
    assert bridge.approvalTaskId == ""
    assert bridge.approvalPlanId == ""
    assert bridge.approvalAction == ""
    assert bridge.approvalDescription == ""
    assert bridge.approvalResource == ""
    assert bridge.approvalRiskLevel == ""
    assert bridge.approvalReason == ""
    assert bridge.approvalReversible is True
    assert bridge.approvalRollbackAvailable is True


def test_bridge_approval_required_populates_presentation_properties(bridge, event_bus, app):
    """Verify APPROVAL_REQUIRED event populates all presentation properties and emits signals."""
    spy_pending = QSignalSpy(bridge.approvalPendingChanged)
    spy_task = QSignalSpy(bridge.approvalTaskIdChanged)
    spy_action = QSignalSpy(bridge.approvalActionChanged)
    spy_desc = QSignalSpy(bridge.approvalDescriptionChanged)
    spy_resource = QSignalSpy(bridge.approvalResourceChanged)
    spy_risk = QSignalSpy(bridge.approvalRiskLevelChanged)
    spy_reason = QSignalSpy(bridge.approvalReasonChanged)
    spy_req = QSignalSpy(bridge.approvalRequested)

    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-test-001",
        message="Approval required for write file",
        data={
            "plan_id": "plan-test-001",
            "task_id": "plan-test-001",
            "action": "WRITE_FILE",
            "goal": "Write configuration file",
            "description": "Write configuration file to disk",
            "resource": "C:\\config\\settings.json",
            "risk_level": "HIGH",
            "reason": "Dangerous file write operation",
            "reversible": True,
            "rollback_available": True,
        },
    )
    QCoreApplication.processEvents()

    assert bridge.approvalPending is True
    assert bridge.approvalTaskId == "plan-test-001"
    assert bridge.approvalPlanId == "plan-test-001"
    assert bridge.approvalAction == "WRITE_FILE"
    assert bridge.approvalDescription == "Write configuration file to disk"
    assert bridge.approvalResource == "C:\\config\\settings.json"
    assert bridge.approvalRiskLevel == "HIGH"
    assert bridge.approvalReason == "Dangerous file write operation"
    assert bridge.approvalReversible is True
    assert bridge.approvalRollbackAvailable is True

    assert spy_pending.count() == 1
    assert spy_pending.at(0)[0] is True
    assert spy_task.count() == 1
    assert spy_task.at(0)[0] == "plan-test-001"
    assert spy_action.count() == 1
    assert spy_action.at(0)[0] == "WRITE_FILE"
    assert spy_desc.count() == 1
    assert spy_desc.at(0)[0] == "Write configuration file to disk"
    assert spy_resource.count() == 1
    assert spy_resource.at(0)[0] == "C:\\config\\settings.json"
    assert spy_risk.count() == 1
    assert spy_risk.at(0)[0] == "HIGH"
    assert spy_reason.count() == 1
    assert spy_reason.at(0)[0] == "Dangerous file write operation"
    assert spy_req.count() == 1
    assert spy_req.at(0) == ["plan-test-001", "WRITE_FILE", "HIGH", "Dangerous file write operation"]


def test_bridge_submit_approval_clears_presentation_properties(bridge, event_bus, app):
    """Verify submitApproval with matching ID clears state and emits approvalSubmitted."""
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-test-002",
        data={
            "task_id": "plan-test-002",
            "action": "DELETE_FILE",
            "reason": "File deletion",
            "risk_level": "CRITICAL",
        },
    )
    QCoreApplication.processEvents()
    assert bridge.approvalPending is True

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)
    spy_resolved = QSignalSpy(bridge.approvalResolved)
    spy_pending = QSignalSpy(bridge.approvalPendingChanged)

    bridge.submitApproval("plan-test-002", True)
    QCoreApplication.processEvents()

    assert bridge.approvalPending is False
    assert bridge.approvalTaskId == ""
    assert bridge.approvalAction == ""
    assert spy_submitted.count() == 1
    assert spy_submitted.at(0) == ["plan-test-002", True]
    assert spy_resolved.count() == 1
    assert spy_resolved.at(0) == ["plan-test-002", True]
    assert spy_pending.count() == 1
    assert spy_pending.at(0)[0] is False


def test_bridge_submit_approval_mismatched_id_rejected(bridge, event_bus, app):
    """Verify submitApproval with mismatched task_id is rejected when pending."""
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-active",
        data={
            "task_id": "plan-active",
            "action": "WRITE_FILE",
            "risk_level": "HIGH",
        },
    )
    QCoreApplication.processEvents()
    assert bridge.approvalPending is True
    assert bridge.approvalTaskId == "plan-active"

    spy_submitted = QSignalSpy(bridge.approvalSubmitted)

    # Stale/mismatched ID submitted
    bridge.submitApproval("plan-stale-wrong", True)
    QCoreApplication.processEvents()

    assert spy_submitted.count() == 0, "Mismatched approval submission must be rejected"
    assert bridge.approvalPending is True
    assert bridge.approvalTaskId == "plan-active"


def test_bridge_state_change_out_of_approval_clears_properties(bridge, event_bus, app):
    """Verify that transitioning state away from AWAITING_APPROVAL clears approval."""
    event_bus.set_state(EVState.AWAITING_APPROVAL)
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-active",
        data={
            "task_id": "plan-active",
            "action": "WRITE_FILE",
            "risk_level": "HIGH",
        },
    )
    QCoreApplication.processEvents()
    assert bridge.approvalPending is True

    event_bus.set_state(EVState.IDLE)
    QCoreApplication.processEvents()

    assert bridge.approvalPending is False
    assert bridge.approvalTaskId == ""


# -----------------------------------------------------------------------------
# Telemetry Contract Tests (Task 018-B)
# -----------------------------------------------------------------------------

def test_bridge_telemetry_default_state(bridge):
    """Verify default initial state: telemetry is explicitly unavailable with safe zeros."""
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


def test_bridge_telemetry_population_from_system_observation(bridge, event_bus, app):
    """Verify SYSTEM_OBSERVATION event populates all telemetry properties and emits signals."""
    spy_avail = QSignalSpy(bridge.telemetryAvailableChanged)
    spy_cpu = QSignalSpy(bridge.telemetryCpuPercentChanged)
    spy_mem = QSignalSpy(bridge.telemetryMemoryPercentChanged)
    spy_mem_used = QSignalSpy(bridge.telemetryMemoryUsedMbChanged)
    spy_mem_total = QSignalSpy(bridge.telemetryMemoryTotalMbChanged)
    spy_disk_pct = QSignalSpy(bridge.telemetryDiskFreePercentChanged)
    spy_disk_gb = QSignalSpy(bridge.telemetryDiskFreeGbChanged)
    spy_procs = QSignalSpy(bridge.telemetryProcessCountChanged)
    spy_top_name = QSignalSpy(bridge.telemetryTopProcessNameChanged)
    spy_top_cpu = QSignalSpy(bridge.telemetryTopProcessCpuPercentChanged)
    spy_top_mem = QSignalSpy(bridge.telemetryTopProcessMemoryMbChanged)
    spy_net = QSignalSpy(bridge.telemetryNetworkConnectedChanged)
    spy_updated = QSignalSpy(bridge.telemetryUpdated)

    sample_snapshot = {
        "cpu_percent": 18.5,
        "memory_used_percent": 62.4,
        "memory_available_bytes": 6 * 1024**3,
        "memory_total_bytes": 16 * 1024**3,
        "disk_free_percent": 42.1,
        "disk_free_bytes": 128 * 1024**3,
        "disk_total_bytes": 512 * 1024**3,
        "process_count": 210,
        "top_cpu_process": "code.exe",
        "top_cpu_percent": 14.2,
        "top_cpu_list": [
            {"pid": 1234, "name": "code.exe", "cpu_percent": 14.2, "memory_percent": 4.5}
        ],
        "top_mem_list": [
            {"pid": 1234, "name": "code.exe", "cpu_percent": 14.2, "memory_percent": 4.5}
        ],
        "network_connected": True,
        "uptime_seconds": 3600.0,
    }

    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        message="Captured 6 system observations",
        data={"snapshot": sample_snapshot},
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is True
    assert bridge.telemetryTimestamp != ""
    assert bridge.telemetryAgeMs >= 0
    assert bridge.telemetryCpuPercent == 18.5
    assert bridge.telemetryMemoryPercent == 62.4
    assert bridge.telemetryMemoryTotalMb == 16384
    assert bridge.telemetryMemoryUsedMb == 10240  # 16GB - 6GB available = 10GB = 10240MB
    assert bridge.telemetryDiskFreePercent == 42.1
    assert bridge.telemetryDiskFreeGb == 128.0
    assert bridge.telemetryProcessCount == 210
    assert bridge.telemetryTopProcessName == "code.exe"
    assert bridge.telemetryTopProcessCpuPercent == 14.2
    assert bridge.telemetryTopProcessMemoryMb > 0
    assert bridge.telemetryNetworkConnected is True

    # Check signal emissions
    assert spy_avail.count() == 1
    assert spy_avail.at(0)[0] is True
    assert spy_cpu.count() == 1
    assert spy_cpu.at(0)[0] == 18.5
    assert spy_mem.count() == 1
    assert spy_mem.at(0)[0] == 62.4
    assert spy_mem_used.count() == 1
    assert spy_mem_used.at(0)[0] == 10240
    assert spy_mem_total.count() == 1
    assert spy_mem_total.at(0)[0] == 16384
    assert spy_disk_pct.count() == 1
    assert spy_disk_pct.at(0)[0] == 42.1
    assert spy_disk_gb.count() == 1
    assert spy_disk_gb.at(0)[0] == 128.0
    assert spy_procs.count() == 1
    assert spy_procs.at(0)[0] == 210
    assert spy_top_name.count() == 1
    assert spy_top_name.at(0)[0] == "code.exe"
    assert spy_top_cpu.count() == 1
    assert spy_top_cpu.at(0)[0] == 14.2
    assert spy_net.count() == 1
    assert spy_net.at(0)[0] is True
    assert spy_updated.count() == 1


def test_bridge_telemetry_metrics_fallback(bridge, event_bus, app):
    """Verify fallback parsing when event payload contains only metrics map."""
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "metrics": {
                "cpu:utilization": 22.0,
                "memory:used_percent": 55.5,
                "disk:free_percent": 18.0,
                "process:aggregate_processes": 195,
                "network:link_status": False,
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is True
    assert bridge.telemetryCpuPercent == 22.0
    assert bridge.telemetryMemoryPercent == 55.5
    assert bridge.telemetryDiskFreePercent == 18.0
    assert bridge.telemetryProcessCount == 195
    assert bridge.telemetryNetworkConnected is False


def test_bridge_telemetry_malformed_and_bounded(bridge, event_bus, app):
    """Verify that corrupt or out-of-range values are bounded and never crash."""
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={
            "snapshot": {
                "cpu_percent": 999.0,         # Should clamp to 100.0
                "memory_used_percent": -50.0,  # Should clamp to 0.0
                "disk_free_percent": "invalid",# Should fallback to 0.0
                "process_count": "not_an_int", # Should fallback to 0
                "top_cpu_process": "None",     # Sanitized to ""
                "network_connected": "yes",    # Cast to bool
            }
        },
    )
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is True
    assert bridge.telemetryCpuPercent == 100.0
    assert bridge.telemetryMemoryPercent == 0.0
    assert bridge.telemetryDiskFreePercent == 0.0
    assert bridge.telemetryProcessCount == 0
    assert bridge.telemetryTopProcessName == ""
    assert bridge.telemetryNetworkConnected is True


def test_bridge_clear_telemetry(bridge, event_bus, app):
    """Verify clearTelemetry resets available flag and restores safe defaults."""
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"cpu_percent": 50.0, "memory_used_percent": 70.0}},
    )
    QCoreApplication.processEvents()
    assert bridge.telemetryAvailable is True

    spy_avail = QSignalSpy(bridge.telemetryAvailableChanged)
    bridge.clearTelemetry()
    QCoreApplication.processEvents()

    assert bridge.telemetryAvailable is False
    assert bridge.telemetryTimestamp == ""
    assert bridge.telemetryAgeMs == -1
    assert bridge.telemetryCpuPercent == 0.0
    assert bridge.telemetryMemoryPercent == 0.0
    assert spy_avail.count() == 1
    assert spy_avail.at(0)[0] is False


def test_bridge_telemetry_worker_thread_queued_handoff(bridge, event_bus, app):
    """Verify background worker thread event reaches Qt state via queued handoff."""
    spy = QSignalSpy(bridge.telemetryCpuPercentChanged)
    assert spy.isValid()

    class TelemetryPublisherWorker(threading.Thread):
        def run(self):
            event_bus.publish(
                event_type=EVEventType.SYSTEM_OBSERVATION,
                source="system_monitor_worker",
                data={"snapshot": {"cpu_percent": 33.3}},
            )

    worker = TelemetryPublisherWorker()
    worker.start()
    worker.join(timeout=3.0)
    assert not worker.is_alive()

    QCoreApplication.processEvents()
    if spy.count() == 0:
        assert spy.wait(3000)

    assert spy.count() == 1
    assert spy.at(0)[0] == 33.3
    assert bridge.telemetryCpuPercent == 33.3


def test_bridge_telemetry_has_no_execution_authority(bridge):
    """Verify telemetry contract has zero execution or mutation authority."""
    forbidden = [
        "execute_command", "run_subprocess", "kill_process",
        "write_file", "delete_file", "setTelemetryCpuPercent",
        "setTelemetryMemoryPercent", "god_mode", "bypass_risk"
    ]
    for method in forbidden:
        assert not hasattr(bridge, method), f"Bridge must not expose {method}"


def test_bridge_telemetry_preserves_approval_and_voice_contracts(bridge, event_bus, app):
    """Verify telemetry updates do NOT alter or overwrite approval or voice state."""
    # Set approval pending
    event_bus.publish(
        event_type=EVEventType.APPROVAL_REQUIRED,
        source="action_pipeline",
        correlation_id="plan-keep",
        data={"task_id": "plan-keep", "action": "WRITE_FILE", "risk_level": "HIGH"},
    )
    QCoreApplication.processEvents()
    assert bridge.approvalPending is True
    assert bridge.approvalTaskId == "plan-keep"

    # Now receive routine telemetry observation
    event_bus.publish(
        event_type=EVEventType.SYSTEM_OBSERVATION,
        source="system_monitor",
        data={"snapshot": {"cpu_percent": 25.0}},
    )
    QCoreApplication.processEvents()

    # Telemetry updated, approval pending UNCHANGED
    assert bridge.telemetryAvailable is True
    assert bridge.telemetryCpuPercent == 25.0
    assert bridge.approvalPending is True
    assert bridge.approvalTaskId == "plan-keep"
