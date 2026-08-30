# Regression tests for the GUI launcher (gui/app.py) state-progression wiring.
#
# Root cause guarded here: the launcher previously gated the lifecycle state
# driver behind a --demo-states flag that defaulted to False, so a normal
# `python gui/app.py` launch never published any STATE_CHANGED event and the
# HUD stayed pinned at the initial state (displayed as "OBSERVE"). These tests
# lock in that the driver is wired on the default launch path and that the
# sequence it publishes is fully observable end-to-end through the bridge.
import sys

import pytest
from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtGui import QGuiApplication

from core.events import EVEventBus
from core.models import EVState
from gui.app import (
    DEMO_INTERVAL_MS,
    DEMO_STATE_SEQUENCE,
    _parse_args,
    _start_state_demo,
)
from gui.bridge import GuiBridge


# --- Argument parsing: the actual root-cause guard -------------------------

def test_demo_states_enabled_by_default():
    """A plain launch (no flags) must drive the lifecycle progression."""
    args = _parse_args([])
    assert args.demo_states is True


def test_no_demo_states_flag_disables_progression():
    """--no-demo-states must pin the window to the initial state."""
    args = _parse_args(["--no-demo-states"])
    assert args.demo_states is False


def test_demo_states_flag_still_accepted():
    """--demo-states remains valid (backward compatible)."""
    args = _parse_args(["--demo-states"])
    assert args.demo_states is True


# --- The sequence covers the documented lifecycle --------------------------

def test_sequence_covers_acceptance_lifecycle_in_order():
    """DEMO_STATE_SEQUENCE must contain the OBSERVE->...->COMPLETE lifecycle
    (IDLE->LISTENING->PLANNING->AWAITING_APPROVAL->EXECUTING->VERIFYING->
    SUCCESS) in order."""
    lifecycle = [
        EVState.IDLE,
        EVState.LISTENING,
        EVState.PLANNING,
        EVState.AWAITING_APPROVAL,
        EVState.EXECUTING,
        EVState.VERIFYING,
        EVState.SUCCESS,
    ]
    indices = [DEMO_STATE_SEQUENCE.index(s) for s in lifecycle]
    assert indices == sorted(indices), "lifecycle states must appear in order"


def test_sequence_starts_at_initial_state():
    """The sequence must begin at IDLE (the HUD's initial/OBSERVE state)."""
    assert DEMO_STATE_SEQUENCE[0] == EVState.IDLE


# --- Qt-level structural + integration guards ------------------------------

@pytest.fixture
def app():
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    yield instance


def test_start_state_demo_creates_running_timer(app):
    """_start_state_demo must create an active, correctly-configured QTimer
    parented to the application (so a driver actually runs)."""
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    timer = _start_state_demo(app, event_bus)
    try:
        assert isinstance(timer, QTimer)
        assert timer.isActive()
        assert timer.interval() == DEMO_INTERVAL_MS
        assert timer.parent() is app
    finally:
        timer.stop()


def test_default_sequence_is_observable_through_bridge(app):
    """Publishing the launcher's sequence through the real event bus must move
    the real bridge through each state (i.e. it does not get stuck at OBSERVE).
    This exercises the bus->bridge path the default launch now relies on,
    without depending on the slow QTimer cadence."""
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)
    try:
        seen = []
        for state in DEMO_STATE_SEQUENCE:
            event_bus.set_state(state)
            QCoreApplication.processEvents()
            seen.append(bridge.currentState)

        # The bridge must have left the initial IDLE/OBSERVE state and visited
        # every distinct state in the sequence.
        assert bridge.currentState == DEMO_STATE_SEQUENCE[-1].value
        for state in DEMO_STATE_SEQUENCE:
            assert state.value in seen
        assert any(s != EVState.IDLE.value for s in seen)
    finally:
        bridge.shutdown()
