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
