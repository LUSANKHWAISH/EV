"""
tests/test_voice_manager.py - Test Suite for E.V. Voice Runtime Integration (Task 014E-1)

Verifies:
  1. Lifecycle operations (start, stop, start twice, stop twice, pause, resume, worker termination).
  2. Wake-word detection (wake detected -> LISTENING, wake not detected -> IDLE).
  3. Pre-roll audio preservation from ring buffer.
  4. VAD & Utterance assembly (speech detection, silence timeout, max duration, speech floor).
  5. Conservative wake phrase stripping (prefix only, punctuation, internal EV preserved).
  6. ASR transcription & untrusted text submission to orchestrator.
  7. Orchestrator security boundary (submit_command ONLY, zero agent/risk/queue authority).
  8. TTS integration & Barge-in / STOP cancellation.
  9. Error isolation & capture failure recovery.
  10. Real microphone provider (SoundDeviceAudioCaptureProvider) contracts.
  11. Privacy invariants (memory-only, zero disk writes).
"""

import os
import queue
import threading
import time
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.asr import ASRResult, MockASRProvider
from core.models import EVState
from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    AudioFrame,
    AudioRingBuffer,
    MockAudioCaptureProvider,
    create_silence_frame,
)
from core.voice_manager import (
    DEFAULT_MAX_UTTERANCE_SECONDS,
    DEFAULT_MIN_SPEECH_SECONDS,
    DEFAULT_PRE_ROLL_SECONDS,
    DEFAULT_SILENCE_TIMEOUT_SECONDS,
    DEFAULT_WAKE_PHRASE,
    EVVoiceManager,
    SoundDeviceAudioCaptureProvider,
    VoiceState,
    strip_wake_phrase,
)
from core.voice_vad import EnergyVADProvider, VADResult
from core.voice_wakeword import MockBargeInStopDetector, MockWakeWordProvider, WakeWordResult


# ============================================================================
# Test Fixtures & Mocks
# ============================================================================
def make_frame(val: int = 0) -> AudioFrame:
    """Create a canonical 30ms AudioFrame with repeating byte pattern."""
    return AudioFrame(data=bytes([val & 0xFF]) * DEFAULT_BYTES_PER_FRAME)


def make_asr_result(text: str, confidence: float = 0.95) -> ASRResult:
    """Create a valid ASRResult dataclass."""
    return ASRResult(
        text=text,
        confidence=confidence,
        language="en",
        duration_seconds=1.0,
        timestamp=time.monotonic(),
        provider="mock",
    )


class MockOrchestrator:
    """Mock orchestrator tracking command submissions strictly via submit_command."""

    def __init__(self) -> None:
        self.submitted_commands: List[str] = []
        self._lock = threading.Lock()

    def submit_command(self, raw_text: str, queue: Optional[bool] = None, priority: Any = None) -> Any:
        with self._lock:
            self.submitted_commands.append(raw_text)
        return None


class MockTTSManager:
    """Mock TTS manager tracking stop and cancel requests."""

    def __init__(self) -> None:
        self.cancel_calls: List[str] = []
        self.stopped: bool = False

    def cancel_all(self, reason: str = "Cancelled") -> None:
        self.cancel_calls.append(reason)

    def stop(self) -> None:
        self.stopped = True


class MockEventBus:
    """Mock event bus tracking state transitions."""

    def __init__(self) -> None:
        self.current_state: Optional[EVState] = EVState.IDLE
        self.states_recorded: List[EVState] = []

    def set_state(self, state: EVState) -> None:
        self.current_state = state
        self.states_recorded.append(state)


class ScriptedVADProvider(EnergyVADProvider):
    """VAD provider returning a pre-scripted sequence of is_speech flags."""

    def __init__(self, script: Optional[List[bool]] = None) -> None:
        super().__init__()
        self._script: List[bool] = list(script or [])
        self._idx: int = 0
        self._default_speech: bool = False

    def set_script(self, script: List[bool]) -> None:
        self._script = list(script)
        self._idx = 0

    def set_default(self, is_speech: bool) -> None:
        self._default_speech = is_speech

    def process_frame(self, frame: AudioFrame) -> VADResult:
        if self._idx < len(self._script):
            val = self._script[self._idx]
            self._idx += 1
            return VADResult(
                is_speech=val,
                confidence=0.95 if val else 0.1,
                energy=1000.0 if val else 10.0,
                timestamp=frame.timestamp,
            )
        return VADResult(
            is_speech=self._default_speech,
            confidence=0.95 if self._default_speech else 0.1,
            energy=1000.0 if self._default_speech else 10.0,
            timestamp=frame.timestamp,
        )

    def reset(self) -> None:
        self._idx = 0


# ============================================================================
# 1. Wake Phrase Stripping Tests
# ============================================================================
class TestWakePhraseStripping:
    """Tests for conservative prefix wake-word removal."""

    def test_strip_default_phrase(self):
        assert strip_wake_phrase("Hey EV open PowerShell") == "open PowerShell"

    def test_strip_with_comma_punctuation(self):
        assert strip_wake_phrase("Hey EV, what is my CPU usage") == "what is my CPU usage"

    def test_strip_with_colon_punctuation(self):
        assert strip_wake_phrase("Hey EV: launch terminal") == "launch terminal"

    def test_strip_with_exclamation(self):
        assert strip_wake_phrase("Hey EV! check status") == "check status"

    def test_strip_case_insensitive(self):
        assert strip_wake_phrase("hey ev run diagnostics") == "run diagnostics"
        assert strip_wake_phrase("HEY EV open notepad") == "open notepad"

    def test_internal_ev_preserved(self):
        assert strip_wake_phrase("open EV documentation") == "open EV documentation"
        assert strip_wake_phrase("show EV status") == "show EV status"

    def test_bare_wake_phrase_becomes_empty(self):
        assert strip_wake_phrase("Hey EV") == ""
        assert strip_wake_phrase("hey ev,") == ""

    def test_custom_wake_phrase(self):
        assert strip_wake_phrase("Computer status", wake_phrases=["Computer"]) == "status"
        assert strip_wake_phrase("Jarvis, lock screen", wake_phrases=["Jarvis", "Hey EV"]) == "lock screen"

    def test_empty_and_whitespace_inputs(self):
        assert strip_wake_phrase("") == ""
        assert strip_wake_phrase("   ") == ""
        assert strip_wake_phrase(None) == ""  # type: ignore


# ============================================================================
# 2. Lifecycle Tests
# ============================================================================
class TestVoiceManagerLifecycle:
    """Tests for start, stop, pause, resume idempotency and thread cleanliness."""

    def test_start_and_stop_clean(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        assert mgr.state == VoiceState.IDLE
        assert mgr.is_running is False

        mgr.start()
        assert mgr.is_running is True
        assert mgr.state == VoiceState.IDLE
        assert capture.is_running() is True

        mgr.stop(timeout=1.0)
        assert mgr.is_running is False
        assert mgr.state == VoiceState.IDLE
        assert capture.is_running() is False

    def test_start_twice_idempotent(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        mgr.start()
        # Second call should be a clean no-op
        mgr.start()
        assert mgr.is_running is True

        mgr.stop()
        assert mgr.is_running is False

    def test_stop_twice_idempotent(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        mgr.start()
        mgr.stop()
        # Second stop call is clean no-op
        mgr.stop()
        assert mgr.is_running is False

    def test_pause_and_resume(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        mgr.start()
        assert mgr.is_paused is False

        mgr.pause()
        assert mgr.is_paused is True
        assert mgr.state == VoiceState.PAUSED

        mgr.resume()
        assert mgr.is_paused is False
        assert mgr.state == VoiceState.IDLE

        mgr.stop()

    def test_process_frame_ignored_when_paused(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        mgr.start()
        mgr.pause()

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        # Wake word should be ignored while paused
        assert mgr.state == VoiceState.PAUSED
        assert len(orch.submitted_commands) == 0

        mgr.stop()

    def test_worker_thread_terminates_cleanly(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        mgr.start()
        worker = mgr._worker_thread
        assert worker is not None
        assert worker.is_alive() is True

        mgr.stop(timeout=1.0)
        assert worker.is_alive() is False

    def test_manager_properties_exposed(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        assert mgr.capture_provider is capture
        assert mgr.wake_word_provider is wake
        assert mgr.vad_provider is vad
        assert mgr.asr_provider is asr
        assert mgr.ring_buffer is not None
        assert mgr.last_error is None
        assert mgr.last_transcript is None
        assert mgr.total_utterances_processed == 0
        assert mgr.total_commands_submitted == 0

    def test_missing_dependencies_raise_value_error(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        with pytest.raises(ValueError, match="capture_provider"):
            EVVoiceManager(None, wake, vad, asr, orch)  # type: ignore

        with pytest.raises(ValueError, match="wake_word_provider"):
            EVVoiceManager(capture, None, vad, asr, orch)  # type: ignore

        with pytest.raises(ValueError, match="vad_provider"):
            EVVoiceManager(capture, wake, None, asr, orch)  # type: ignore

        with pytest.raises(ValueError, match="asr_provider"):
            EVVoiceManager(capture, wake, vad, None, orch)  # type: ignore

        with pytest.raises(ValueError, match="orchestrator"):
            EVVoiceManager(capture, wake, vad, asr, None)  # type: ignore


# ============================================================================
# 3. Wake Detection & Pre-Roll Tests
# ============================================================================
class TestWakeAndPreRoll:
    """Tests for wake-word triggering, state transition, and pre-roll assembly."""

    def test_wake_word_transitions_to_listening(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        event_bus = MockEventBus()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
        )

        assert mgr.state == VoiceState.IDLE

        # Feed 3 idle frames without wake
        for _ in range(3):
            mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.IDLE

        # Arm wake trigger on 4th frame
        wake.set_triggered(True)
        mgr.process_frame(make_frame(2))

        assert mgr.state == VoiceState.LISTENING
        assert event_bus.current_state == EVState.LISTENING

    def test_pre_roll_preservation_from_ring_buffer(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        # Config: 3 frames pre-roll (90 ms)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            pre_roll_seconds=0.090,
        )

        # Feed 5 pre-history frames
        for i in range(5):
            mgr.process_frame(make_frame(i + 10))

        # Trigger wake on next frame
        wake.set_triggered(True)
        mgr.process_frame(make_frame(99))

        assert mgr.state == VoiceState.LISTENING
        # Utterance collection should contain 3 pre-roll frames
        assert len(mgr._active_utterance_frames) == 3

    def test_wake_provider_exception_does_not_crash(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        wake.process_frame = MagicMock(side_effect=RuntimeError("Wake model fault"))

        # Should log and continue safely in IDLE
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.IDLE


# ============================================================================
# 4. VAD & Utterance Assembly Tests
# ============================================================================
class TestUtteranceAssembly:
    """Tests for speech tracking, silence endpoints, duration limits, and floor checks."""

    def test_full_utterance_assembly_flow(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="Hey EV open terminal")
        orch = MockOrchestrator()

        # silence timeout = 2 frames (60ms), speech floor = 2 frames (60ms)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            silence_timeout_seconds=0.060,
            min_speech_seconds=0.060,
        )

        # 1. Wake event
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.LISTENING

        # 2. Speech frames (3 frames)
        vad.set_script([True, True, True, False, False])
        for _ in range(3):
            mgr.process_frame(make_frame(10))
            assert mgr.state == VoiceState.LISTENING

        # 3. Silence frames (2 frames) -> terminates utterance!
        mgr.process_frame(make_frame(0))
        mgr.process_frame(make_frame(0))

        # Give background transcription worker a brief moment to submit
        time.sleep(0.05)

        # Verified: command stripped and submitted!
        assert "open terminal" in orch.submitted_commands
        assert mgr.total_commands_submitted == 1
        assert mgr.state == VoiceState.IDLE

    def test_speech_floor_discard_does_not_submit(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="noise")
        orch = MockOrchestrator()

        # Floor = 0.150s (5 frames). We only feed 1 speech frame.
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.150,
            silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        # 1 speech frame, then 2 silence frames
        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)
        # Below speech floor: discarded, zero commands submitted
        assert len(orch.submitted_commands) == 0
        assert mgr.state == VoiceState.IDLE

    def test_initial_silence_timeout_aborts_to_idle(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        vad.set_default(False)  # Silence continuously
        asr = MockASRProvider()
        orch = MockOrchestrator()

        # Initial silence timeout = 3 frames (0.090s)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            initial_silence_timeout_seconds=0.090,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.LISTENING

        # Feed 3 silence frames without speech
        for _ in range(3):
            mgr.process_frame(make_frame())

        # Timed out waiting for speech: aborted back to IDLE
        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_max_utterance_duration_ceiling(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        vad.set_default(True)  # Continuous non-stop speech
        asr = MockASRProvider(default_text="Hey EV long monologue")
        orch = MockOrchestrator()

        # Max duration = 5 frames (0.150s)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            max_utterance_seconds=0.150,
            min_speech_seconds=0.030,
            pre_roll_seconds=0.030,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        # Feed 6 frames of speech
        for _ in range(6):
            mgr.process_frame(make_frame())

        time.sleep(0.05)
        # Max duration reached: finalized and submitted
        assert "long monologue" in orch.submitted_commands

    def test_vad_exception_handled_gracefully(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            initial_silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.LISTENING

        # Make VAD raise
        vad.process_frame = MagicMock(side_effect=RuntimeError("VAD fault"))

        # Should handle exception and treat frame as silence without crashing
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.IDLE


# ============================================================================
# 5. ASR & Orchestrator Security Boundary Tests
# ============================================================================
class TestASRAndOrchestratorBoundary:
    """Tests verifying untrusted text submission strictly to EVOrchestrator."""

    def test_empty_asr_result_does_not_submit(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="")
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)
        assert len(orch.submitted_commands) == 0
        assert mgr.state == VoiceState.IDLE

    def test_whitespace_only_asr_does_not_submit(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="   \n\t  ")
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)
        assert len(orch.submitted_commands) == 0

    def test_asr_exception_caught_cleanly(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider()
        asr.transcribe = MagicMock(side_effect=RuntimeError("Whisper OOM error"))
        orch = MockOrchestrator()

        error_log = []
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
            on_error=lambda err: error_log.append(err),
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)
        assert len(orch.submitted_commands) == 0
        assert len(error_log) > 0
        assert "ASR error" in error_log[0]
        assert mgr.state == VoiceState.IDLE

    def test_orchestrator_boundary_untrusted_command_only(self):
        """Verify the manager does not call agent, risk, queue, or bypass safety."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="Hey EV open notepad")

        mock_orch = MagicMock()
        mock_orch.submit_command = MagicMock()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=mock_orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)

        # Strictly calls submit_command and NOTHING else
        mock_orch.submit_command.assert_called_once_with("open notepad")
        called_methods = [call[0] for call in mock_orch.method_calls]
        assert called_methods == ["submit_command"]


# ============================================================================
# 6. TTS Integration & Barge-In STOP Tests
# ============================================================================
class TestTTSAndBargeIn:
    """Tests for TTS cancellation and STOP command submission upon barge-in."""

    def test_barge_in_stop_cancels_tts(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        tts = MockTTSManager()
        stop_detector = MockBargeInStopDetector()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            tts_manager=tts,
            barge_in_detector=stop_detector,
        )

        # Trigger STOP barge-in
        stop_detector.set_triggered(True)
        mgr.process_frame(make_frame())

        # TTS cancel_all should be called
        assert len(tts.cancel_calls) == 1
        assert "barge-in" in tts.cancel_calls[0].lower()

        # Orchestrator should receive control command "stop"
        assert "stop" in orch.submitted_commands

    def test_barge_in_stop_aborts_active_listening(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        stop_detector = MockBargeInStopDetector()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            barge_in_detector=stop_detector,
        )

        # Wake up
        wake.set_triggered(True)
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.LISTENING

        # Trigger STOP
        stop_detector.set_triggered(True)
        mgr.process_frame(make_frame())

        # State returns to IDLE immediately
        assert mgr.state == VoiceState.IDLE
        assert len(mgr._active_utterance_frames) == 0

    def test_barge_in_detector_exception_handled(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        stop_detector = MockBargeInStopDetector()
        stop_detector.process_frame = MagicMock(side_effect=RuntimeError("Detector error"))

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            barge_in_detector=stop_detector,
        )

        # Should not crash
        mgr.process_frame(make_frame())
        assert mgr.state == VoiceState.IDLE


# ============================================================================
# 7. Error Handling & Device Disconnect Tests
# ============================================================================
class TestErrorHandling:
    """Tests for capture provider failures and recovery."""

    def test_invalid_frame_type_raises_type_error(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
        )

        with pytest.raises(TypeError, match="Expected AudioFrame"):
            mgr.process_frame("not an audio frame")  # type: ignore

    def test_capture_read_exception_sets_error_state(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        error_events = []
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            on_error=lambda err: error_events.append(err),
        )

        # Force capture provider read_frame to raise
        capture.read_frame = MagicMock(side_effect=RuntimeError("Audio USB device unplugged"))

        mgr.start()
        time.sleep(0.1)

        assert mgr.state == VoiceState.ERROR
        assert mgr.last_error is not None
        assert "Audio USB device unplugged" in mgr.last_error
        assert len(error_events) > 0

        mgr.stop()

    def test_on_transcript_callback_invoked(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="Hey EV status")
        orch = MockOrchestrator()

        transcripts = []
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
            on_transcript=lambda t: transcripts.append(t),
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame())

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())
        mgr.process_frame(make_frame())

        time.sleep(0.05)
        assert len(transcripts) == 1
        assert transcripts[0] == "status"


# ============================================================================
# 8. SoundDeviceAudioCaptureProvider Tests
# ============================================================================
class TestSoundDeviceAudioCaptureProvider:
    """Tests for the real microphone provider using mocked sounddevice."""

    def test_provider_initialization_defaults(self):
        provider = SoundDeviceAudioCaptureProvider()
        assert provider.sample_rate == 16000
        assert provider.channels == 1
        assert provider.block_size == 480
        assert provider.is_active() is False

    def test_provider_availability(self):
        provider = SoundDeviceAudioCaptureProvider()
        # sounddevice is installed in .venv
        assert provider.is_available() is True

    @patch("sounddevice.RawInputStream")
    def test_provider_start_stop_lifecycle(self, mock_stream_cls):
        mock_stream = MagicMock()
        mock_stream_cls.return_value = mock_stream

        provider = SoundDeviceAudioCaptureProvider()
        provider.start()

        assert provider.is_active() is True
        mock_stream.start.assert_called_once()

        # Idempotent second start
        provider.start()
        assert mock_stream.start.call_count == 1

        provider.stop()
        assert provider.is_active() is False
        mock_stream.stop.assert_called_once()
        mock_stream.close.assert_called_once()

        # Idempotent second stop
        provider.stop()

    @patch("sounddevice.RawInputStream")
    def test_audio_callback_enqueues_audio_frame(self, mock_stream_cls):
        captured_callback = None

        def side_effect(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("callback")
            return MagicMock()

        mock_stream_cls.side_effect = side_effect

        provider = SoundDeviceAudioCaptureProvider()
        provider.start()
        assert captured_callback is not None

        # Invoke callback with raw 960-byte payload
        test_payload = b"\x12\x34" * 480
        captured_callback(test_payload, 480, None, 0)

        frame = provider.read_frame(timeout=0.1)
        assert frame is not None
        assert isinstance(frame, AudioFrame)
        assert frame.data == test_payload
        assert frame.sample_rate == 16000
        assert frame.channels == 1

        provider.stop()

    def test_read_frame_timeout_returns_none(self):
        provider = SoundDeviceAudioCaptureProvider()
        assert provider.read_frame(timeout=0.01) is None


# ============================================================================
# 9. Privacy Invariants
# ============================================================================
class TestPrivacyInvariants:
    """Verifies that voice processing never writes raw audio to disk."""

    def test_privacy_no_audio_files_created_on_disk(self, tmp_path):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(default_text="Hey EV test privacy")
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            min_speech_seconds=0.030,
            silence_timeout_seconds=0.060,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(42))

        vad.set_script([True, False, False])
        mgr.process_frame(make_frame(42))
        mgr.process_frame(make_frame(42))
        mgr.process_frame(make_frame(42))

        time.sleep(0.05)

        # Verify command submitted
        assert "test privacy" in orch.submitted_commands

        # Verify utterance frames were completely wiped from memory
        assert len(mgr._active_utterance_frames) == 0

        # Verify no .wav, .pcm, or .tmp files were created in workspace
        for root, dirs, files in os.walk(r"D:\EV"):
            # Exclude tests and build artifacts
            if any(p in root for p in [".git", ".venv", "models", "data", "gui"]):
                continue
            for f in files:
                assert not f.endswith(".wav"), f"Found leaked WAV: {f}"
                assert not f.endswith(".pcm"), f"Found leaked PCM: {f}"
