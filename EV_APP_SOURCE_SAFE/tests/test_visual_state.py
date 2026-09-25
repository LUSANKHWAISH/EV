"""Focused tests for the presentation-only Super Core visual state contract."""

import sys

import pytest
from PySide6.QtCore import QCoreApplication, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent

from core.events import EVEventBus
from core.models import EVEventType, EVState
from gui.bridge import GuiBridge
from gui.visual_state import EVVisualState, VisualStateController


@pytest.fixture(scope="session")
def qapp():
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def event_bus():
    return EVEventBus(initial_state=EVState.IDLE)


@pytest.fixture
def bridge(event_bus, qapp):
    instance = GuiBridge(event_bus)
    yield instance
    instance.shutdown()


@pytest.mark.parametrize("state", list(EVVisualState))
def test_every_visual_state_has_a_deterministic_profile(state):
    controller = VisualStateController()
    controller.set_state_for_simulation(state.value)

    assert controller.state == state.value
    assert controller.profile["energy"] >= 0.0
    assert controller.profile["transitionInMs"] > 0
    assert controller.profile["transitionOutMs"] > 0


def test_invalid_visual_state_is_rejected():
    controller = VisualStateController()
    with pytest.raises(ValueError, match="Unsupported visual state"):
        controller.set_state_for_simulation("NOT_A_VISUAL_STATE")


def test_transition_records_previous_state_and_progress():
    controller = VisualStateController()
    controller.set_state_for_simulation("THINKING")

    assert controller.previous_state == "IDLE"
    assert controller.transition_progress == 0.0

    controller.advance_transition(0.5)
    assert controller.transition_progress == 0.5

    controller.advance_transition(3.0)
    assert controller.transition_progress == 1.0


def test_sleep_profile_disables_animation():
    controller = VisualStateController()
    controller.set_state_for_simulation("SLEEP")

    assert controller.animation_enabled is False
    assert controller.profile["animationEnabled"] is False


@pytest.mark.parametrize(
    ("event_type", "state", "expected"),
    [
        (EVEventType.PLAN_CREATED, None, "THINKING"),
        (EVEventType.PLAN_VALIDATED, None, "PROCESSING"),
        (EVEventType.APPROVAL_REQUIRED, None, "WAITING_FOR_APPROVAL"),
        (EVEventType.ACTION_STARTED, None, "EXECUTING"),
        (EVEventType.ACTION_VERIFYING, None, "VERIFYING"),
        (EVEventType.PLAN_COMPLETED, None, "SUCCESS"),
        (EVEventType.PLAN_FAILED, None, "ERROR"),
        (EVEventType.PLAN_CANCELLED, None, "WARNING"),
        (EVEventType.STATE_CHANGED, EVState.STOPPED, "SLEEP"),
    ],
)
def test_backend_events_map_to_visual_states(bridge, event_bus, qapp, event_type, state, expected):
    if event_type == EVEventType.STATE_CHANGED:
        event_bus.set_state(state)
    else:
        event_bus.publish(event_type, "test")
    QCoreApplication.processEvents()

    assert bridge.visualState == expected


def test_voice_event_maps_to_listening_without_mutating_authoritative_state(bridge, event_bus, qapp):
    event_bus.publish(
        EVEventType.VOICE_STATE_CHANGED,
        "voice",
        data={"voice_state": "LISTENING"},
    )
    QCoreApplication.processEvents()

    assert bridge.visualState == "LISTENING"
    assert event_bus.current_state == EVState.IDLE


def test_simulation_isolated_from_authoritative_event_bus_and_approval(bridge, event_bus, qapp):
    submitted = []
    bridge.approvalSubmitted.connect(lambda task_id, approved: submitted.append((task_id, approved)))

    bridge.setVisualStateForSimulation("WAITING_FOR_APPROVAL")
    bridge.injectVisualApprovalEvent(True)
    bridge.injectVisualExecutionEvent("ACTION_STARTED")
    QCoreApplication.processEvents()

    assert bridge.visualSimulationActive is True
    assert bridge.visualState == "EXECUTING"
    assert event_bus.current_state == EVState.IDLE
    assert bridge.approvalPending is False
    assert submitted == []


def test_simulation_does_not_submit_tasks_or_publish_events(bridge, event_bus, qapp):
    observed = []
    event_bus.subscribe(lambda event: observed.append(event))
    submitted = []
    bridge.taskSubmitted.connect(submitted.append)

    bridge.injectVisualActionEvent("PLAN_STARTED")
    bridge.injectVisualVoiceSignal(activity=True)
    QCoreApplication.processEvents()

    assert bridge.visualState == "LISTENING"
    assert observed == []
    assert submitted == []


def test_real_events_are_ignored_until_simulation_is_cleared(bridge, event_bus, qapp):
    bridge.setVisualStateForSimulation("SLEEP")
    event_bus.publish(EVEventType.ACTION_STARTED, "executor")
    QCoreApplication.processEvents()
    assert bridge.visualState == "SLEEP"

    bridge.clearVisualSimulation()
    event_bus.publish(EVEventType.ACTION_STARTED, "executor")
    QCoreApplication.processEvents()
    assert bridge.visualState == "EXECUTING"


def test_core_exposes_read_only_visual_contract(bridge, qapp):
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", bridge)
    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile("D:/EV/gui/qml/components/EVIntelligenceCore.qml"),
    )
    assert not component.isError(), [error.toString() for error in component.errors()]
    core = component.create()
    assert core is not None

    bridge.setVisualStateForSimulation("SLEEP")
    qapp.processEvents()

    assert core.property("visualState") == "SLEEP"
    assert core.property("visualAnimationEnabled") is False
    assert core.property("visualProfile")["animationEnabled"] is False

    core.deleteLater()
    engine.deleteLater()
    qapp.processEvents()
