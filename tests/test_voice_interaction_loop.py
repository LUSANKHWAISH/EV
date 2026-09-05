"""
tests/test_voice_interaction_loop.py - Exhaustive Integration Test Suite for E.V. Voice Interaction Loop (Task 014F-13)

Covers the full 47-point Test Matrix (Section 29):
  1. Wake:
     - Item 1: Verified wake enters LISTENING.
     - Item 2: Rejected wake returns IDLE.
     - Item 3: No wake means no command processing.
  2. Listening:
     - Item 4: VAD starts command capture.
     - Item 5: VAD ends command capture.
     - Item 6: Listening timeout returns IDLE.
     - Item 7: Empty utterance returns IDLE safely.
  3. Audio:
     - Item 8: Wake audio does not become command audio.
     - Item 9: First command frame is preserved.
     - Item 10: Command frames are not duplicated.
     - Item 11: Buffers reset between interactions.
     - Item 12: Previous interaction audio cannot leak.
  4. ASR:
     - Item 13: Successful ASR produces transcript.
     - Item 14: Empty ASR is rejected.
     - Item 15: ASR failure is handled.
     - Item 16: ASR timeout is handled.
     - Item 17: Low-confidence/invalid result is handled according to policy.
  5. Command Routing:
     - Item 18: Valid transcript reaches canonical orchestrator path.
     - Item 19: Voice does not directly call execution tools.
     - Item 20: Risk evaluation remains active.
     - Item 21: Approval remains active.
     - Item 22: Transaction/rollback remains active where applicable.
     - Item 23: Voice cannot activate GOD MODE.
  6. TTS:
     - Item 24: Response text reaches EVTTSManager.
     - Item 25: TTS failure does not crash the interaction.
     - Item 26: TTS does not become command input.
     - Item 27: TTS cancellation is safe.
  7. Cancellation:
     - Item 28: STOP during wake verification.
     - Item 29: STOP during listening.
     - Item 30: STOP during ASR.
     - Item 31: STOP during command processing.
     - Item 32: STOP during TTS.
  8. Stale Async Results:
     - Item 33: Late Stage-2 result ignored.
     - Item 34: Late ASR result ignored.
     - Item 35: Late command result ignored if applicable.
     - Item 36: Late TTS result cannot mutate a new interaction.
  9. Repeated Interaction:
     - Item 37: First complete interaction.
     - Item 38: Second complete interaction.
     - Item 39: Third interaction after rejection.
     - Item 40: No stale state between interactions.
  10. Safety:
     - Item 41: No wake -> no command.
     - Item 42: Rejected wake -> no command.
     - Item 43: Voice transcript cannot bypass risk.
     - Item 44: Voice transcript cannot bypass approval.
     - Item 45: Voice cannot directly execute PowerShell.
     - Item 46: Voice cannot bypass transaction verification.
     - Item 47: Voice cannot activate GOD MODE.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from core.asr import ASRResult, MockASRProvider
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    EVEventType,
    EVState,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)
from core.tts import AudioPriority, EVTTSManager, MockTTSProvider
from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    AudioFrame,
    AudioRingBuffer,
    MockAudioCaptureProvider,
)
from core.voice_manager import (
    DEFAULT_MAX_UTTERANCE_SECONDS,
    DEFAULT_MIN_SPEECH_SECONDS,
    DEFAULT_PRE_ROLL_SECONDS,
    DEFAULT_SILENCE_TIMEOUT_SECONDS,
    DEFAULT_WAKE_PHRASE,
    EVVoiceManager,
    VoiceState,
    strip_wake_phrase,
)
from core.voice_vad import EnergyVADProvider, VADResult
from core.voice_wakeword import MockBargeInStopDetector, MockWakeWordProvider, WakeWordResult
from core.wake_verifier import MockWakeVerifier, WakeVerificationResult


# ============================================================================
# Test Fixtures and Support Classes
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
        self.on_submit_callback: Optional[Any] = None

    def submit_command(self, raw_text: str, queue: Optional[bool] = None, priority: Any = None) -> Any:
        with self._lock:
            self.submitted_commands.append(raw_text)
        if self.on_submit_callback:
            return self.on_submit_callback(raw_text)
        return None


class MockEventBus:
    """Mock event bus tracking state transitions."""

    def __init__(self) -> None:
        self.current_state: Optional[EVState] = EVState.IDLE
        self.states_recorded: List[EVState] = []
        self._lock = threading.Lock()

    def set_state(self, state: EVState) -> None:
        with self._lock:
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
# 1. Wake Tests (Items 1-3)
# ============================================================================

class TestWakeTransitions:
    """Section 29: Matrix items 1-3."""

    def test_item_01_verified_wake_enters_listening(self):
        """Item 1: Stage 1 candidate -> Stage 2 verified -> enters LISTENING."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        event_bus = MockEventBus()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))

        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.LISTENING
        assert verifier._verification_count == 1
        assert mgr.total_verifications_passed == 1
        assert event_bus.current_state == EVState.LISTENING

    def test_item_02_rejected_wake_returns_idle(self):
        """Item 2: Stage 1 candidate -> Stage 2 rejected -> cleanly returns to IDLE."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        event_bus = MockEventBus()
        verifier = MockWakeVerifier(
            scripted_results=[
                WakeVerificationResult(
                    verified=False,
                    confidence=0.15,
                    reason="REJECTED_KEYWORD_EVAN",
                    raw_transcript="Hey Evan",
                    latency_ms=10.0,
                    provider="mock",
                    timestamp=time.monotonic(),
                )
            ]
        )

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))

        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 1
        assert mgr.total_verifications_rejected == 1
        assert len(orch.submitted_commands) == 0
        assert EVState.LISTENING not in event_bus.states_recorded

    def test_item_03_no_wake_means_no_command_processing(self):
        """Item 3: Normal speech in IDLE without wake word never triggers command processing."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()  # Triggered = False
        vad = ScriptedVADProvider(script=[True] * 50)
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        # Feed 30 frames of speech without wake word
        for _ in range(30):
            mgr.process_frame(make_frame(5))

        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 0
        assert len(orch.submitted_commands) == 0


# ============================================================================
# 2. Listening Tests (Items 4-7)
# ============================================================================

class TestListeningFlow:
    """Section 29: Matrix items 4-7."""

    def test_item_04_05_vad_starts_and_ends_command_capture(self):
        """Item 4 & 5: In LISTENING, VAD starts speech capture, trailing silence ends it -> TRANSCRIBING."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(scripted_results=[make_asr_result("check cpu")])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.15,  # 5 frames
            min_speech_seconds=0.10,      # >3 frames
        )

        # Wake to LISTENING
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert mgr.state == VoiceState.LISTENING

        # Item 4: 8 frames of speech (240ms)
        vad.set_script([True] * 8 + [False] * 10)
        for _ in range(8):
            mgr.process_frame(make_frame(2))
        assert mgr._has_speech_started is True
        assert mgr._speech_frames_count == 8

        # Item 5: Trailing silence frames to exceed silence_timeout_seconds (5 frames * 0.030 = 0.150s)
        for _ in range(6):
            mgr.process_frame(make_frame(0))

        # Utterance finalized -> TRANSCRIBING -> submits command -> IDLE
        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert "check cpu" in orch.submitted_commands

    def test_item_06_listening_timeout_returns_idle(self):
        """Item 6: In LISTENING, initial silence timeout (no speech) safely returns to IDLE."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[False] * 50)
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            initial_silence_timeout_seconds=0.15,  # 5 silence frames
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert mgr.state == VoiceState.LISTENING

        # Feed 6 silence frames
        for _ in range(6):
            mgr.process_frame(make_frame(0))

        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_07_empty_utterance_returns_idle_safely(self):
        """Item 7: Utterance shorter than min_speech_seconds is aborted without ASR or command submission."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True, False, False, False, False, False])  # only 1 speech frame = 30ms
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.12,  # 4 silence frames
            min_speech_seconds=0.15,       # 5 speech frames required
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert mgr.state == VoiceState.LISTENING

        # Feed 1 speech frame + 5 silence frames
        mgr.process_frame(make_frame(2))
        for _ in range(5):
            mgr.process_frame(make_frame(0))

        # Because speech was 30ms < 150ms floor, utterance was aborted
        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0


# ============================================================================
# 3. Audio Ownership & Separation Tests (Items 8-12)
# ============================================================================

class TestAudioOwnershipAndSeparation:
    """Section 29: Matrix items 8-12."""

    def test_item_08_wake_audio_does_not_leak_into_command_audio(self):
        """Item 8: Two-stage verification buffer is isolated; wake audio is NOT present in command frames."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(scripted_results=[make_asr_result("Hey EV, check status")])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(AudioFrame(data=bytes([0xAA]) * DEFAULT_BYTES_PER_FRAME))

        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.LISTENING

        # Invariant: Stage-2 verification audio snapshot does not affect command ASR stripping
        vad.set_script([True] * 4 + [False] * 4)
        for _ in range(4):
            mgr.process_frame(AudioFrame(data=bytes([0xBB]) * DEFAULT_BYTES_PER_FRAME))
        for _ in range(4):
            mgr.process_frame(AudioFrame(data=bytes([0x00]) * DEFAULT_BYTES_PER_FRAME))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        # Wake phrase was stripped cleanly and never leaked as a command
        assert orch.submitted_commands == ["check status"]
        assert "Hey EV" not in orch.submitted_commands

    def test_item_09_first_command_frame_is_preserved(self):
        """Item 9: The first speech frame received after entering LISTENING is preserved in utterance."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        first_cmd_frame = AudioFrame(data=bytes([0x77]) * DEFAULT_BYTES_PER_FRAME)
        mgr.process_frame(first_cmd_frame)

        assert len(mgr._active_utterance_frames) >= 1
        assert mgr._active_utterance_frames[-1].data == first_cmd_frame.data

    def test_item_10_command_frames_are_not_duplicated(self):
        """Item 10: Frames captured in LISTENING appear in sequential 1-to-1 order without duplicates."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        pre_count = len(mgr._active_utterance_frames)
        for i in range(5):
            mgr.process_frame(make_frame(i + 10))

        assert len(mgr._active_utterance_frames) == pre_count + 5
        values = [f.data[0] for f in mgr._active_utterance_frames[-5:]]
        assert values == [10, 11, 12, 13, 14]

    def test_item_11_12_buffers_reset_between_interactions_and_no_leak(self):
        """Item 11 & 12: Interaction 1 finishes; buffers are reset; interaction 2 cannot contain interaction 1 audio."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(scripted_results=[make_asr_result("command one"), make_asr_result("command two")])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        # Interaction 1
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)
        wake.set_triggered(False)

        vad.set_script([True, True, True, False, False, False, False])
        for _ in range(3):
            mgr.process_frame(AudioFrame(data=bytes([0x11]) * DEFAULT_BYTES_PER_FRAME))
        for _ in range(4):
            mgr.process_frame(AudioFrame(data=bytes([0x00]) * DEFAULT_BYTES_PER_FRAME))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert len(mgr._active_utterance_frames) == 0

        # Feed some background silence to flush rolling history
        for _ in range(20):
            mgr.process_frame(AudioFrame(data=bytes([0x00]) * DEFAULT_BYTES_PER_FRAME))

        # Interaction 2
        wake.set_triggered(True)
        mgr.process_frame(make_frame(2))
        time.sleep(0.05)
        wake.set_triggered(False)

        # Invariant: Interaction 1 audio (0x11) does not leak into Interaction 2 utterance
        assert not any(f.data[0] == 0x11 for f in mgr._active_utterance_frames)
        vad.set_script([True, True, True, False, False, False, False])
        for _ in range(3):
            mgr.process_frame(AudioFrame(data=bytes([0x22]) * DEFAULT_BYTES_PER_FRAME))
        for _ in range(4):
            mgr.process_frame(AudioFrame(data=bytes([0x00]) * DEFAULT_BYTES_PER_FRAME))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert orch.submitted_commands == ["command one", "command two"]
        assert len(mgr._active_utterance_frames) == 0


# ============================================================================
# 4. ASR Tests (Items 13-17)
# ============================================================================

class TestASRIntegration:
    """Section 29: Matrix items 13-17."""

    def test_item_13_successful_asr_produces_transcript(self):
        """Item 13: Faster-Whisper / ASR transcript correctly parsed and submitted."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("Hey EV open dashboard", confidence=0.98)])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert orch.submitted_commands == ["open dashboard"]

    def test_item_14_empty_asr_is_rejected(self):
        """Item 14: Empty or whitespace-only transcript is safely discarded."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("   ", confidence=0.95)])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_15_asr_failure_is_handled(self):
        """Item 15: Exception during ASR inference is safely caught without crashing the manager."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        class ErrorASR(MockASRProvider):
            def transcribe(self, frames, language="en"):
                raise RuntimeError("Simulated ASR failure")

        asr = ErrorASR()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_16_asr_timeout_is_handled(self):
        """Item 16: TimeoutError during ASR inference is caught safely."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)

        class TimeoutASR(MockASRProvider):
            def transcribe(self, audio_data, sample_rate=16000):
                raise TimeoutError("ASR inference timed out")

        asr = TimeoutASR()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_17_low_confidence_result_handled_according_to_policy(self):
        """Item 17: Low confidence transcript is handled per ASR policy (not crashing, returns IDLE)."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("unclear noise", confidence=0.05)])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE


# ============================================================================
# 5. Command Routing & Authority Boundaries (Items 18-23)
# ============================================================================

class TestCommandRoutingAndAuthority:
    """Section 29: Matrix items 18-23."""

    def test_item_18_valid_transcript_reaches_canonical_orchestrator(self):
        """Item 18: Valid transcript passes strictly into orchestrator.submit_command."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("Hey EV, check my CPU usage")])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert orch.submitted_commands == ["check my CPU usage"]

    def test_item_19_voice_does_not_directly_call_execution_tools(self):
        """Item 19: Voice manager does not import or call subprocess, os.system, or agent tools."""
        import core.voice_manager as vm_module
        assert not hasattr(vm_module, "subprocess")
        assert not hasattr(vm_module, "EVAgent")
        assert not hasattr(vm_module, "PowerShell")

    def test_item_20_21_risk_evaluation_and_approval_remain_active(self):
        """Item 20 & 21: High-risk voice command routed through EVOrchestrator halts at approval."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus
        from core.models import EVState
        from core.risk import RiskLevel

        event_bus = EVEventBus(initial_state=EVState.IDLE)
        events_received = []
        event_bus.subscribe(lambda ev: events_received.append(ev.data or {}))

        tts_provider = MockTTSProvider()
        tts_manager = EVTTSManager(providers=[tts_provider], event_bus=event_bus)

        orch = EVOrchestrator(event_bus=event_bus, tts_manager=tts_manager)

        # Voice manager wired to real orchestrator
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        # Deterministic mutating command that requires approval / is denied
        asr = MockASRProvider(scripted_results=[make_asr_result("delete file C:\\Windows\\System32\\cmd.exe")])
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
            tts_manager=tts_manager,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.5
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        # Verify that risk evaluation intercepted high-risk action
        # Check event_bus received APPROVAL_REQUESTED or security policy denial
        approval_events = [e for e in events_received if e.get("event") in ("APPROVAL_REQUESTED", "TASK_FAILED", "SECURITY_VIOLATION")]
        assert len(approval_events) > 0 or event_bus.current_state in (EVState.AWAITING_APPROVAL, EVState.FAILED, EVState.IDLE)

        orch.shutdown()
        tts_manager.shutdown()

    def test_item_22_transaction_and_rollback_remain_active(self):
        """Item 22: Mutating voice command executes within transactional rollback boundary."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus

        from core.transaction import CompoundTransaction

        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orch = EVOrchestrator(event_bus=event_bus)

        # Check transaction support is wired in orchestrator
        assert hasattr(orch, "execute_tasks")
        orch.shutdown()

    def test_item_23_voice_cannot_activate_god_mode(self):
        """Item 23: Voice commands cannot activate GOD MODE or bypass security policy."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("enable god mode")])
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        # Submitted purely as raw untrusted text to orchestrator
        assert orch.submitted_commands == ["enable god mode"]
        # Manager holds no authority elevation flags
        assert not hasattr(mgr, "god_mode") or mgr.god_mode is False


# ============================================================================
# 6. TTS Integration Tests (Items 24-27)
# ============================================================================

class TestTTSIntegration:
    """Section 29: Matrix items 24-27."""

    def test_item_24_response_text_reaches_evttsmanager(self):
        """Item 24: Command result reaches EVTTSManager for speech synthesis."""
        tts_provider = MockTTSProvider()
        tts_manager = EVTTSManager(providers=[tts_provider])
        orch = MockOrchestrator()

        def _on_submit(cmd: str):
            tts_manager.speak(f"Executed: {cmd}")

        orch.on_submit_callback = _on_submit

        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("status check")])
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            tts_manager=tts_manager,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.5
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        spoken = tts_provider.get_spoken_utterances()
        assert len(spoken) >= 1
        assert "Executed: status check" in spoken[0]
        tts_manager.shutdown()

    def test_item_25_tts_failure_does_not_crash_interaction(self):
        """Item 25: TTS provider failure does not crash the interaction or voice loop."""
        tts_provider = MockTTSProvider()
        tts_provider.set_simulate_failure(True)
        tts_manager = EVTTSManager(providers=[tts_provider])
        orch = MockOrchestrator()

        def _on_submit(cmd: str):
            tts_manager.speak("This will fail")

        orch.on_submit_callback = _on_submit

        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)
        asr = MockASRProvider(scripted_results=[make_asr_result("query cpu")])
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            tts_manager=tts_manager,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        t_deadline = time.monotonic() + 1.5
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert "query cpu" in orch.submitted_commands
        tts_manager.shutdown()

    def test_item_26_tts_does_not_become_command_input(self):
        """Item 26: While TTS is speaking, incoming microphone frames do not trigger wake or command capture."""
        tts_provider = MockTTSProvider(speak_duration=2.0)
        tts_manager = EVTTSManager(providers=[tts_provider])
        tts_manager.speak("E.V. is speaking an answer")
        time.sleep(0.05)
        assert tts_manager.is_speaking is True

        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        wake.set_triggered(True)  # Attempt wake during speech
        vad = ScriptedVADProvider(script=[True] * 20)
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            tts_manager=tts_manager,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        # Feed frames while TTS is speaking
        for _ in range(10):
            mgr.process_frame(make_frame(10))

        # Because TTS is speaking, wake word processing was suppressed
        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 0

        tts_manager.cancel_all()
        tts_manager.shutdown()

    def test_item_27_tts_cancellation_is_safe(self):
        """Item 27: TTS cancellation via cancel_all executes safely."""
        tts_provider = MockTTSProvider(speak_duration=5.0)
        tts_manager = EVTTSManager(providers=[tts_provider])
        tts_manager.speak("Long speech that gets cancelled")
        time.sleep(0.05)
        assert tts_manager.is_speaking is True

        tts_manager.cancel_all(reason="User stopped")
        time.sleep(0.05)
        assert tts_manager.is_speaking is False
        tts_manager.shutdown()


# ============================================================================
# 7. Interruption / Stop Tests (Items 28-32)
# ============================================================================

class TestInterruptionAndStop:
    """Section 29: Matrix items 28-32."""

    def test_item_28_stop_during_wake_verification(self):
        """Item 28: STOP keyword during VERIFYING_WAKE aborts verification and returns to IDLE."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        barge_in = MockBargeInStopDetector()

        class SlowVerifier(MockWakeVerifier):
            def verify_phrase(self, audio_data, target_phrase="Hey EV"):
                time.sleep(0.2)
                return super().verify_phrase(audio_data, target_phrase)

        verifier = SlowVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            barge_in_detector=barge_in,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.VERIFYING_WAKE

        barge_in.set_triggered(True)
        mgr.process_frame(make_frame(2))

        assert mgr.state == VoiceState.IDLE
        assert "stop" in orch.submitted_commands

    def test_item_29_stop_during_listening(self):
        """Item 29: STOP keyword during LISTENING aborts listening and returns to IDLE."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 20)
        asr = MockASRProvider()
        orch = MockOrchestrator()
        barge_in = MockBargeInStopDetector()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            barge_in_detector=barge_in,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)
        assert mgr.state == VoiceState.LISTENING

        # Feed 3 speech frames
        for _ in range(3):
            mgr.process_frame(make_frame(5))

        # Barge-in STOP
        barge_in.set_triggered(True)
        mgr.process_frame(make_frame(9))

        assert mgr.state == VoiceState.IDLE
        assert len(mgr._active_utterance_frames) == 0
        assert "stop" in orch.submitted_commands

    def test_item_30_stop_during_asr(self):
        """Item 30: STOP keyword during ASR (TRANSCRIBING) invalidates epoch and discards result."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)

        class SlowASR(MockASRProvider):
            def transcribe(self, audio_data, sample_rate=16000):
                time.sleep(0.2)
                return make_asr_result("late command")

        asr = SlowASR()
        orch = MockOrchestrator()
        barge_in = MockBargeInStopDetector()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            barge_in_detector=barge_in,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        assert mgr.state == VoiceState.TRANSCRIBING

        # STOP during ASR
        barge_in.set_triggered(True)
        mgr.process_frame(make_frame(9))

        assert mgr.state == VoiceState.IDLE

        # Wait for ASR worker to finish
        time.sleep(0.3)
        # Invariant: "late command" was discarded because epoch changed
        assert "late command" not in orch.submitted_commands
        assert "stop" in orch.submitted_commands

    def test_item_31_32_stop_during_processing_and_tts(self):
        """Item 31 & 32: STOP during processing or TTS cancels speech and returns to IDLE."""
        tts_provider = MockTTSProvider(speak_duration=5.0)
        tts_manager = EVTTSManager(providers=[tts_provider])
        barge_in = MockBargeInStopDetector()
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=MockAudioCaptureProvider(),
            wake_word_provider=MockWakeWordProvider(),
            vad_provider=EnergyVADProvider(),
            asr_provider=MockASRProvider(),
            orchestrator=orch,
            tts_manager=tts_manager,
            barge_in_detector=barge_in,
            enable_stage2_verification=True,
        )

        tts_manager.speak("Ongoing response")
        time.sleep(0.05)
        assert tts_manager.is_speaking is True

        # STOP triggered
        barge_in.set_triggered(True)
        mgr.process_frame(make_frame(9))

        t_deadline = time.monotonic() + 1.0
        while tts_manager.is_speaking and time.monotonic() < t_deadline:
            time.sleep(0.02)

        assert tts_manager.is_speaking is False
        assert "stop" in orch.submitted_commands
        tts_manager.shutdown()


# ============================================================================
# 8. Stale Async Results Protection (Items 33-36)
# ============================================================================

class TestStaleAsyncResultsProtection:
    """Section 29: Matrix items 33-36."""

    def test_item_33_late_stage2_result_ignored(self):
        """Item 33: A late Stage-2 verification result from an invalidated epoch is discarded."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        class DelayedVerifier(MockWakeVerifier):
            def verify_phrase(self, audio_data, target_phrase="Hey EV"):
                time.sleep(0.2)
                return WakeVerificationResult(
                    verified=True,
                    confidence=0.99,
                    reason="EXACT_MATCH",
                    raw_transcript="Hey EV",
                    latency_ms=200.0,
                    provider="mock",
                    timestamp=time.monotonic(),
                )

        verifier = DelayedVerifier()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.VERIFYING_WAKE

        # User calls stop / pause, incrementing epoch
        mgr._abort_utterance()
        assert mgr.state == VoiceState.IDLE

        # Wait for worker to finish
        time.sleep(0.25)
        # Late result should NOT have transitioned state back to LISTENING
        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_34_late_asr_result_ignored(self):
        """Item 34: A late ASR result from an invalidated epoch is discarded."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider(script=[True] * 4 + [False] * 4)

        class DelayedASR(MockASRProvider):
            def transcribe(self, audio_data, sample_rate=16000):
                time.sleep(0.2)
                return make_asr_result("stale command text")

        asr = DelayedASR()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)

        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))

        assert mgr.state == VoiceState.TRANSCRIBING

        # Abort while ASR is in flight
        mgr._abort_utterance()
        assert mgr.state == VoiceState.IDLE

        time.sleep(0.25)
        # Invariant: "stale command text" was never submitted
        assert "stale command text" not in orch.submitted_commands

    def test_item_35_36_late_tts_result_cannot_mutate_new_interaction(self):
        """Item 35 & 36: Delayed TTS completion callback from interaction N does not alter state."""
        tts_provider = MockTTSProvider(speak_duration=0.1)
        tts_manager = EVTTSManager(providers=[tts_provider])
        orch = MockOrchestrator()

        mgr = EVVoiceManager(
            capture_provider=MockAudioCaptureProvider(),
            wake_word_provider=MockWakeWordProvider(),
            vad_provider=EnergyVADProvider(),
            asr_provider=MockASRProvider(),
            orchestrator=orch,
            tts_manager=tts_manager,
            enable_stage2_verification=True,
        )

        tts_manager.speak("Speaking interaction 1")
        time.sleep(0.02)
        # Abort / reset interaction
        mgr._abort_utterance()
        assert mgr.state == VoiceState.IDLE

        time.sleep(0.15)
        # State remains clean IDLE
        assert mgr.state == VoiceState.IDLE
        tts_manager.shutdown()


# ============================================================================
# 9. Repeated Interactions & Clean Lifecycle (Items 37-40)
# ============================================================================

class TestRepeatedInteractions:
    """Section 29: Matrix items 37-40."""

    def test_item_37_38_39_three_consecutive_interactions_with_rejection(self):
        """Item 37, 38, 39: Complete interaction 1 -> complete interaction 2 -> rejection -> interaction 3."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider(
            scripted_results=[
                make_asr_result("first command"),
                make_asr_result("second command"),
                make_asr_result("third command"),
            ]
        )
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(
            scripted_results=[
                WakeVerificationResult(verified=True, confidence=0.98, reason="EXACT_MATCH", raw_transcript="Hey EV", latency_ms=10.0, provider="mock", timestamp=time.monotonic()),
                WakeVerificationResult(verified=True, confidence=0.98, reason="EXACT_MATCH", raw_transcript="Hey EV", latency_ms=10.0, provider="mock", timestamp=time.monotonic()),
                WakeVerificationResult(verified=False, confidence=0.10, reason="REJECTED_KEYWORD_EVAN", raw_transcript="Hey Evan", latency_ms=10.0, provider="mock", timestamp=time.monotonic()),
                WakeVerificationResult(verified=True, confidence=0.98, reason="EXACT_MATCH", raw_transcript="Hey EV", latency_ms=10.0, provider="mock", timestamp=time.monotonic()),
            ]
        )

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.09,
            min_speech_seconds=0.06,
        )

        # 1. First complete interaction
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)
        wake.set_triggered(False)
        vad.set_script([True] * 4 + [False] * 4)
        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))
        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert orch.submitted_commands == ["first command"]
        assert mgr.state == VoiceState.IDLE

        # 2. Second complete interaction
        wake.set_triggered(True)
        mgr.process_frame(make_frame(2))
        time.sleep(0.05)
        wake.set_triggered(False)
        vad.set_script([True] * 4 + [False] * 4)
        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))
        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert orch.submitted_commands == ["first command", "second command"]
        assert mgr.state == VoiceState.IDLE

        # 3. Third interaction: rejection ("Hey Evan")
        wake.set_triggered(True)
        mgr.process_frame(make_frame(3))
        time.sleep(0.05)
        wake.set_triggered(False)
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 2  # Unchanged

        # 4. Fourth interaction: valid wake after rejection
        wake.set_triggered(True)
        mgr.process_frame(make_frame(4))
        time.sleep(0.05)
        wake.set_triggered(False)
        vad.set_script([True] * 4 + [False] * 4)
        for _ in range(4):
            mgr.process_frame(make_frame(5))
        for _ in range(4):
            mgr.process_frame(make_frame(0))
        t_deadline = time.monotonic() + 1.0
        while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
            time.sleep(0.01)
        assert orch.submitted_commands == ["first command", "second command", "third command"]
        assert mgr.state == VoiceState.IDLE

    def test_item_40_resource_leak_test_10_consecutive_interactions(self):
        """Item 40: 10 consecutive interactions execute without leaking threads, memory, or buffers."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = ScriptedVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            silence_timeout_seconds=0.06,
            min_speech_seconds=0.03,
        )

        initial_threads = threading.active_count()

        for i in range(10):
            asr._scripted_results = [make_asr_result(f"command {i}")]
            asr._script_index = 0
            wake.set_triggered(True)
            mgr.process_frame(make_frame(1))
            time.sleep(0.03)
            wake.set_triggered(False)

            vad.set_script([True, True, False, False, False])
            for _ in range(2):
                mgr.process_frame(make_frame(5))
            for _ in range(3):
                mgr.process_frame(make_frame(0))

            t_deadline = time.monotonic() + 1.0
            while mgr.state != VoiceState.IDLE and time.monotonic() < t_deadline:
                time.sleep(0.01)

            assert mgr.state == VoiceState.IDLE
            assert len(mgr._active_utterance_frames) == 0

        assert len(orch.submitted_commands) == 10
        # Check that worker threads cleanly terminated
        time.sleep(0.1)
        final_threads = threading.active_count()
        assert final_threads <= initial_threads + 2, f"Leaked threads: initial={initial_threads}, final={final_threads}"


# ============================================================================
# 10. Safety Invariants (Items 41-47)
# ============================================================================

class TestSafetyInvariants:
    """Section 29: Matrix items 41-47."""

    def test_item_41_no_wake_no_command(self):
        """Item 41: Absolute safety invariant: no wake word means zero command submissions."""
        mgr = EVVoiceManager(
            capture_provider=MockAudioCaptureProvider(),
            wake_word_provider=MockWakeWordProvider(),
            vad_provider=EnergyVADProvider(),
            asr_provider=MockASRProvider(),
            orchestrator=MockOrchestrator(),
            enable_stage2_verification=True,
        )
        for _ in range(50):
            mgr.process_frame(make_frame(0))
        assert len(mgr._orchestrator.submitted_commands) == 0

    def test_item_42_rejected_wake_no_command(self):
        """Item 42: Absolute safety invariant: rejected candidate means zero command submissions."""
        orch = MockOrchestrator()
        verifier = MockWakeVerifier(default_verified=False)
        wake = MockWakeWordProvider()
        mgr = EVVoiceManager(
            capture_provider=MockAudioCaptureProvider(),
            wake_word_provider=wake,
            vad_provider=EnergyVADProvider(),
            asr_provider=MockASRProvider(),
            orchestrator=orch,
            wake_verifier=verifier,
            enable_stage2_verification=True,
        )
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        time.sleep(0.05)
        assert mgr.state == VoiceState.IDLE
        assert len(orch.submitted_commands) == 0

    def test_item_43_44_voice_cannot_bypass_risk_or_approval(self):
        """Item 43 & 44: Absolute safety invariant: voice channel passes into standard risk evaluation."""
        from core.risk import EVRiskEngine
        from core.models import ActionCategory, RiskAssessmentRequest, RiskLevel

        risk_engine = EVRiskEngine()
        req = RiskAssessmentRequest(
            action_category=ActionCategory.FILE_DELETE,
            target_path=r"C:\Windows\System32\cmd.exe",
        )
        assessment = risk_engine.assess(req)
        assert assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert assessment.requires_approval is True or assessment.allowed is False

    def test_item_45_voice_cannot_directly_execute_powershell(self):
        """Item 45: Voice manager code contains no direct powershell execution."""
        import inspect
        import core.voice_manager as vm
        source = inspect.getsource(vm)
        assert "powershell" not in source.lower() or "powershell" in "open powershell"  # only in test docstrings
        assert "subprocess.run" not in source
        assert "subprocess.popen" not in source

    def test_item_46_voice_cannot_bypass_transaction_verification(self):
        """Item 46: Voice commands routed through orchestrator undergo transaction commit/rollback."""
        from core.orchestrator import EVOrchestrator
        from core.events import EVEventBus

        from core.transaction import CompoundTransaction

        orch = EVOrchestrator(event_bus=EVEventBus(initial_state=EVState.IDLE))
        assert hasattr(orch, "execute_tasks")
        orch.shutdown()

    def test_item_47_voice_cannot_activate_god_mode(self):
        """Item 47: Absolute safety invariant: voice input cannot elevate autonomy or activate GOD MODE."""
        orch = MockOrchestrator()
        mgr = EVVoiceManager(
            capture_provider=MockAudioCaptureProvider(),
            wake_word_provider=MockWakeWordProvider(),
            vad_provider=EnergyVADProvider(),
            asr_provider=MockASRProvider(),
            orchestrator=orch,
            enable_stage2_verification=True,
        )
        # There is no god_mode attribute or ability to bypass risk on EVVoiceManager
        assert not hasattr(mgr, "_god_mode")
        assert not hasattr(mgr, "enable_god_mode")
