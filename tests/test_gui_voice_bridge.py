"""
Unit and integration tests for E.V. GuiBridge voice state binding (Task 014F-14).

Verifies:
  1. VoiceState lifecycle propagation (IDLE -> VERIFYING_WAKE -> LISTENING ->
     TRANSCRIBING -> PROCESSING -> SPEAKING -> IDLE) via EVEventBus to GuiBridge.
  2. Sequential ordering preservation across Qt thread boundary.
  3. Proper synchronization of bridge.currentState and bridge.voiceState.
  4. Accuracy of human-readable descriptions via getStateDescription().
  5. Thread-safe queued signal emission and property change notifications.
  6. Cancellation and STOP barge-in returning bridge state to IDLE.
  7. Authority invariant: bridge/QML is strictly display-only with zero execution
     authority or approval bypass.
"""

import sys
import threading
import time
from typing import List
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy

from core.events import EVEvent, EVEventBus
from core.models import EVEventType, EVState
from core.voice_manager import EVVoiceManager, VoiceState
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


# ============================================================================
# 1. State Propagation Tests
# ============================================================================

def test_bridge_initial_voice_state(bridge):
    """Verify bridge initializes with voiceState='IDLE' and isVoiceActive=False."""
    assert bridge.voiceState == "IDLE"
    assert bridge.isVoiceActive is False


@pytest.mark.parametrize(
    "voice_state,expected_active,expected_desc",
    [
        ("IDLE", False, "Ready and waiting for input"),
        ("VERIFYING_WAKE", True, "Verifying wake phrase..."),
        ("LISTENING", True, "Listening for voice commands"),
        ("TRANSCRIBING", True, "Transcribing speech..."),
        ("PROCESSING", True, "Processing command..."),
        ("SPEAKING", True, "Speaking response"),
        ("PAUSED", False, "Voice processing paused"),
    ],
)
def test_voice_state_propagation_reaches_bridge(
    bridge, event_bus, app, voice_state, expected_active, expected_desc
):
    """Verify each canonical VoiceState reaches the bridge via VOICE_STATE_CHANGED."""
    spy_voice = QSignalSpy(bridge.voiceStateChanged)
    spy_state = QSignalSpy(bridge.stateChanged)
    assert spy_voice.isValid()
    assert spy_state.isValid()

    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice_manager",
        data={"voice_state": voice_state, "old_state": "IDLE"},
    )
    QCoreApplication.processEvents()

    assert bridge.voiceState == voice_state
    assert bridge.isVoiceActive is expected_active
    assert spy_voice.count() == (1 if voice_state != "IDLE" else 0)
    assert bridge.getStateDescription(voice_state) == expected_desc

    # Also verify currentState synchronized for HUD components
    if voice_state in ("IDLE", "VERIFYING_WAKE", "LISTENING", "TRANSCRIBING", "PROCESSING", "SPEAKING"):
        assert bridge.currentState == voice_state


def test_voice_state_same_value_no_duplicate_signal(bridge, event_bus, app):
    """Verify publishing the same voice state does not emit duplicate signals."""
    spy_voice = QSignalSpy(bridge.voiceStateChanged)

    # Set to LISTENING
    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice_manager",
        data={"voice_state": "LISTENING", "old_state": "IDLE"},
    )
    QCoreApplication.processEvents()
    assert spy_voice.count() == 1

    # Publish LISTENING again
    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice_manager",
        data={"voice_state": "LISTENING", "old_state": "LISTENING"},
    )
    QCoreApplication.processEvents()
    assert spy_voice.count() == 1


# ============================================================================
# 2. Sequential Ordering Preservation
# ============================================================================

def test_voice_lifecycle_sequence_preserved(bridge, event_bus, app):
    """Verify the canonical lifecycle preserves exact ordering into the bridge."""
    observed_states: List[str] = []
    bridge.voiceStateChanged.connect(lambda s: observed_states.append(s))

    lifecycle = [
        "VERIFYING_WAKE",
        "LISTENING",
        "TRANSCRIBING",
        "PROCESSING",
        "SPEAKING",
        "IDLE",
    ]

    for st in lifecycle:
        event_bus.publish(
            event_type=EVEventType.VOICE_STATE_CHANGED,
            source="voice_manager",
            data={"voice_state": st},
        )
        QCoreApplication.processEvents()

    assert observed_states == lifecycle
    assert bridge.voiceState == "IDLE"
    assert bridge.currentState == "IDLE"
    assert bridge.isVoiceActive is False


# ============================================================================
# 3. Cross-Thread Handoff
# ============================================================================

def test_cross_thread_voice_state_propagation(bridge, event_bus, app):
    """Verify voice state events emitted from background worker threads safely reach Qt state."""
    spy = QSignalSpy(bridge.voiceStateChanged)

    def worker():
        time.sleep(0.02)
        event_bus.publish(
            event_type=EVEventType.VOICE_STATE_CHANGED,
            source="voice_manager",
            data={"voice_state": "VERIFYING_WAKE"},
        )
        time.sleep(0.02)
        event_bus.publish(
            event_type=EVEventType.VOICE_STATE_CHANGED,
            source="voice_manager",
            data={"voice_state": "LISTENING"},
        )

    t = threading.Thread(target=worker)
    t.start()
    t.join(timeout=2.0)

    # Process events on Qt main thread
    QCoreApplication.processEvents()

    assert bridge.voiceState == "LISTENING"
    assert bridge.isVoiceActive is True
    assert spy.count() == 2


# ============================================================================
# 4. EVVoiceManager Real State Publishing Integration
# ============================================================================

def test_voice_manager_publishes_to_bridge_on_state_change(bridge, event_bus, app):
    """Verify that EVVoiceManager._set_state automatically triggers bridge state updates."""
    mock_capture = MagicMock()
    mock_wake = MagicMock()
    mock_vad = MagicMock()
    mock_asr = MagicMock()
    mock_orch = MagicMock()

    mgr = EVVoiceManager(
        capture_provider=mock_capture,
        wake_word_provider=mock_wake,
        vad_provider=mock_vad,
        asr_provider=mock_asr,
        orchestrator=mock_orch,
        event_bus=event_bus,
    )

    spy_voice = QSignalSpy(bridge.voiceStateChanged)

    # Transition manager to VERIFYING_WAKE
    mgr._set_state(VoiceState.VERIFYING_WAKE)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "VERIFYING_WAKE"
    assert bridge.currentState == "VERIFYING_WAKE"

    # Transition manager to LISTENING
    mgr._set_state(VoiceState.LISTENING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "LISTENING"
    assert bridge.currentState == "LISTENING"

    # Transition manager to TRANSCRIBING
    mgr._set_state(VoiceState.TRANSCRIBING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "TRANSCRIBING"
    assert bridge.currentState == "TRANSCRIBING"

    # Transition manager to PROCESSING
    mgr._set_state(VoiceState.PROCESSING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "PROCESSING"
    assert bridge.currentState == "PROCESSING"

    # Transition manager to SPEAKING
    mgr._set_state(VoiceState.SPEAKING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "SPEAKING"
    assert bridge.currentState == "SPEAKING"

    # Transition manager to IDLE
    mgr._set_state(VoiceState.IDLE)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "IDLE"
    assert bridge.currentState == "IDLE"
    assert bridge.isVoiceActive is False

    assert spy_voice.count() == 6


# ============================================================================
# 5. Cancellation & STOP / Barge-In
# ============================================================================

def test_voice_abort_returns_bridge_to_idle(bridge, event_bus, app):
    """Verify that aborting an active utterance resets bridge state cleanly to IDLE."""
    mock_capture = MagicMock()
    mock_wake = MagicMock()
    mock_vad = MagicMock()
    mock_asr = MagicMock()
    mock_orch = MagicMock()

    mgr = EVVoiceManager(
        capture_provider=mock_capture,
        wake_word_provider=mock_wake,
        vad_provider=mock_vad,
        asr_provider=mock_asr,
        orchestrator=mock_orch,
        event_bus=event_bus,
    )

    # Put into LISTENING
    mgr._set_state(VoiceState.LISTENING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "LISTENING"

    # Call _abort_utterance (e.g. silence timeout or cancellation)
    mgr._abort_utterance()
    QCoreApplication.processEvents()

    assert bridge.voiceState == "IDLE"
    assert bridge.currentState == "IDLE"
    assert bridge.isVoiceActive is False


def test_barge_in_stop_returns_bridge_to_idle(bridge, event_bus, app):
    """Verify that STOP barge-in resets bridge state cleanly to IDLE."""
    mock_capture = MagicMock()
    mock_wake = MagicMock()
    mock_vad = MagicMock()
    mock_asr = MagicMock()
    mock_orch = MagicMock()
    mock_tts = MagicMock()

    mgr = EVVoiceManager(
        capture_provider=mock_capture,
        wake_word_provider=mock_wake,
        vad_provider=mock_vad,
        asr_provider=mock_asr,
        orchestrator=mock_orch,
        tts_manager=mock_tts,
        event_bus=event_bus,
    )

    # Put into SPEAKING
    mgr._set_state(VoiceState.SPEAKING)
    QCoreApplication.processEvents()
    assert bridge.voiceState == "SPEAKING"

    # Trigger STOP barge-in
    mgr._handle_stop_barge_in()
    QCoreApplication.processEvents()

    assert bridge.voiceState == "IDLE"
    assert bridge.currentState == "IDLE"
    assert bridge.isVoiceActive is False
    mock_orch.submit_command.assert_called_with("stop")


# ============================================================================
# 6. Approval State Immunity
# ============================================================================

def test_awaiting_approval_not_overwritten_by_idle_voice_state(bridge, event_bus, app):
    """Verify that if the system is AWAITING_APPROVAL, an IDLE voice state does not overwrite currentState."""
    event_bus.set_state(EVState.AWAITING_APPROVAL)
    QCoreApplication.processEvents()
    assert bridge.currentState == "AWAITING_APPROVAL"

    # Voice manager transitions to IDLE
    event_bus.publish(
        event_type=EVEventType.VOICE_STATE_CHANGED,
        source="voice_manager",
        data={"voice_state": "IDLE"},
    )
    QCoreApplication.processEvents()

    assert bridge.voiceState == "IDLE"
    # System state preserved!
    assert bridge.currentState == "AWAITING_APPROVAL"


# ============================================================================
# 7. Authority Invariant
# ============================================================================

def test_bridge_has_no_voice_state_mutator():
    """Verify QML cannot mutate voiceState directly (no setter exposed)."""
    assert not hasattr(GuiBridge, "setVoiceState")
    prop = GuiBridge.voiceState
    # Check that write/setter is None
    assert prop.fset is None, "voiceState must be read-only"


def test_bridge_has_no_execution_authority():
    """Verify GuiBridge has no execution, subprocess, or GOD MODE methods."""
    for forbidden in [
        "execute",
        "run_command",
        "eval",
        "system",
        "subprocess",
        "powershell",
        "elevate",
        "god_mode",
        "bypass_risk",
        "bypass_approval",
    ]:
        assert not hasattr(GuiBridge, forbidden), f"Forbidden method found: {forbidden}"
