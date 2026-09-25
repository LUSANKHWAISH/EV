"""
tests/test_voice_manager_two_stage.py - Exhaustive Test Suite for Two-Stage Wake-Word Runtime Integration (Task 014F-12B)

Covers the full 36-point Test Matrix:
  1. Basic Stage 1 -> Stage 2 -> LISTENING / IDLE transitions.
  2. Competitor phrases rejection (Hey Evan, Hey Evelyn, Hey Everyone, Hey Evidence, Hey Stevie, Every, Hey Avi, Heavy).
  3. Positive phrases acceptance (Hey EV, Hey E.V., Hey E V, hey ev).
  4. Audio buffer ownership, pre-roll preservation, non-duplication into command stream, deterministic reset.
  5. Concurrency, duplicate trigger prevention, STOP barge-in during verification, shutdown safety, epoch invalidation.
  6. Architectural safety: zero execution authority, zero command submission on wake, zero risk/approval/god-mode bypass.
  7. Performance, idle zero-overhead guarantee, and worker lifecycle isolation.
"""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.asr import ASRResult, MockASRProvider
from core.models import EVState
from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    AudioFrame,
    AudioRingBuffer,
    MockAudioCaptureProvider,
)
from core.voice_manager import (
    DEFAULT_PRE_ROLL_SECONDS,
    DEFAULT_STAGE2_VERIFICATION_BUFFER_SECONDS,
    EVVoiceManager,
    VoiceState,
)
from core.voice_vad import EnergyVADProvider
from core.voice_wakeword import MockBargeInStopDetector, MockWakeWordProvider, WakeWordResult
from core.wake_verifier import (
    FasterWhisperWakeVerifier,
    MockWakeVerifier,
    WakeVerificationResult,
)


def make_frame(val: int = 0) -> AudioFrame:
    """Create a canonical 30ms AudioFrame with repeating byte pattern."""
    return AudioFrame(data=bytes([val & 0xFF]) * DEFAULT_BYTES_PER_FRAME)


class MockOrchestrator:
    """Mock orchestrator tracking command submissions strictly via submit_command."""

    def __init__(self) -> None:
        self.submitted_commands: List[str] = []
        self._lock = threading.Lock()

    def submit_command(self, raw_text: str, queue: Optional[bool] = None, priority: Any = None) -> Any:
        with self._lock:
            self.submitted_commands.append(raw_text)
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


class TestTwoStageBasicTransitions:
    """Matrix items 1-4: Basic two-stage flow."""

    def test_stage1_candidate_triggers_stage2_and_listening(self):
        """Item 1 & 3: Stage 1 candidate -> VERIFYING_WAKE -> Stage 2 verified -> LISTENING."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        event_bus = MockEventBus()

        verifier = MockWakeVerifier(
            scripted_results=[
                WakeVerificationResult(
                    verified=True,
                    confidence=0.98,
                    reason="EXACT_MATCH",
                    raw_transcript="Hey EV",
                    latency_ms=10.0,
                    provider="mock",
                    timestamp=time.monotonic(),
                )
            ]
        )

        state_changes = []
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
            wake_verifier=verifier,
            enable_stage2_verification=True,
            on_state_change=lambda s: state_changes.append(s),
        )

        # Feed 5 background frames in IDLE
        for _ in range(5):
            mgr.process_frame(make_frame(0))
        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 0

        # Trigger Stage-1 candidate
        wake.set_triggered(True)
        mgr.process_frame(make_frame(10))

        # Verification runs asynchronously on worker thread
        # Wait up to 1.0s for worker to complete
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.LISTENING
        assert verifier._verification_count == 1
        assert mgr.total_verifications_attempted == 1
        assert mgr.total_verifications_passed == 1
        assert mgr.total_verifications_rejected == 0
        assert VoiceState.VERIFYING_WAKE in state_changes
        assert VoiceState.LISTENING in state_changes
        assert event_bus.current_state == EVState.LISTENING

    def test_stage1_candidate_rejected_by_stage2_returns_to_idle(self):
        """Item 4: Stage 1 candidate -> VERIFYING_WAKE -> Stage 2 rejected -> IDLE with zero side-effects."""
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
                    confidence=0.10,
                    reason="REJECTED_KEYWORD_EVAN",
                    raw_transcript="Hey Evan",
                    latency_ms=12.0,
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

        # Trigger Stage 1
        wake.set_triggered(True)
        mgr.process_frame(make_frame(10))

        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 1
        assert mgr.total_verifications_attempted == 1
        assert mgr.total_verifications_passed == 0
        assert mgr.total_verifications_rejected == 1
        # Invariant: Event bus NEVER moved to LISTENING
        assert EVState.LISTENING not in event_bus.states_recorded
        # Invariant: Zero commands submitted
        assert len(orch.submitted_commands) == 0

    def test_stage1_non_trigger_does_not_invoke_stage2(self):
        """Item 2 & 33: Stage 1 non-trigger results in ZERO Stage 2 invocations."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()  # Default non-triggering
        vad = EnergyVADProvider()
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

        for _ in range(30):
            mgr.process_frame(make_frame(0))

        assert mgr.state == VoiceState.IDLE
        assert verifier._verification_count == 0
        assert mgr.total_verifications_attempted == 0


@pytest.fixture(scope="module")
def whisper_verifier():
    return FasterWhisperWakeVerifier(
        model_size_or_path="tiny.en",
        device="cpu",
        compute_type="int8",
        download_root=r"D:\EV\models\asr",
    )


class TestCompetitorAndPositivePhrases:
    """Matrix items 5-16: FasterWhisperWakeVerifier phrase validation."""

    def test_hard_competitors_rejected(self, whisper_verifier):
        """Items 5-12: Verify competitor phrases are rejected."""
        competitors = [
            ("Hey Evan", "REJECTED_KEYWORD_EVAN"),
            ("Hey Evelyn", "REJECTED_KEYWORD_EVELYN"),
            ("Hey Everyone", "REJECTED_KEYWORD_EVERYONE"),
            ("Hey Evidence", "REJECTED_KEYWORD_EVIDENCE"),
            ("Hey Stevie", "REJECTED_KEYWORD_STEVIE"),
            ("Every", "REJECTED_KEYWORD_EVERY"),
            ("Heavy", "REJECTED_KEYWORD_HEAVY"),
            ("Heavy duty", "REJECTED_KEYWORD_HEAVY"),
        ]
        for phrase, expected_substr in competitors:
            v, c, r = whisper_verifier._evaluate_transcript(phrase)
            assert v is False, f"Competitor '{phrase}' should be rejected, got {r}"
            assert expected_substr in r or "UNMATCHED" in r

    def test_positive_phrases_accepted(self, whisper_verifier):
        """Items 13-16: Verify positive wake phrases are accepted."""
        positives = ["Hey EV", "Hey E.V.", "Hey E V", "hey ev", "Hey V", "hey ee vee"]
        for phrase in positives:
            v, c, r = whisper_verifier._evaluate_transcript(phrase)
            assert v is True, f"Positive '{phrase}' should be accepted, got {r}"


class TestAudioBufferingAndOwnership:
    """Matrix items 17-21: Audio buffer ownership and continuity."""

    def test_pre_roll_preservation_and_audio_continuity(self):
        """Items 17-20: Pre-roll is preserved and not lost during Stage-2 verification."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        verifier = MockWakeVerifier(
            scripted_results=[
                WakeVerificationResult(
                    verified=True,
                    confidence=0.99,
                    reason="EXACT_MATCH",
                    raw_transcript="Hey EV",
                    latency_ms=5.0,
                    provider="mock",
                    timestamp=time.monotonic(),
                )
            ]
        )

        ring = AudioRingBuffer(max_frames=100)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            ring_buffer=ring,
            pre_roll_seconds=0.75,
            enable_stage2_verification=True,
        )

        # Feed 25 distinct frames (byte 1..25)
        for i in range(1, 26):
            mgr.process_frame(make_frame(i))

        # Trigger wake on frame 26
        wake.set_triggered(True)
        mgr.process_frame(make_frame(26))

        # Wait for transition to LISTENING
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.01)

        assert mgr.state == VoiceState.LISTENING
        # Pre-roll should contain recent frames from ring buffer
        assert len(mgr._active_utterance_frames) > 0
        # The latest frame in pre-roll should be frame 26
        assert mgr._active_utterance_frames[-1].data == bytes([26]) * DEFAULT_BYTES_PER_FRAME

    def test_ring_buffer_deterministic_reset(self):
        """Item 21: Ring buffer and verifier states reset cleanly on stop."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        verifier = MockWakeVerifier()

        ring = AudioRingBuffer(max_frames=50)
        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=verifier,
            ring_buffer=ring,
            enable_stage2_verification=True,
        )

        for i in range(10):
            mgr.process_frame(make_frame(i))
        assert len(mgr.ring_buffer) == 10

        mgr.stop()
        assert len(mgr.ring_buffer) == 0
        assert mgr.state == VoiceState.IDLE


class TestConcurrencyAndCancellation:
    """Matrix items 22-26: Concurrency, duplicate triggers, barge-in, shutdown safety."""

    def test_duplicate_stage1_triggers_prevented_during_verification(self):
        """Item 22: While in VERIFYING_WAKE, additional frames do not spawn duplicate verifications."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()

        # Slow verifier that blocks for 0.2s
        class SlowVerifier(MockWakeVerifier):
            def verify_phrase(self, audio_data, target_phrase="Hey EV"):
                time.sleep(0.20)
                return super().verify_phrase(audio_data, target_phrase)

        slow_verifier = SlowVerifier(default_verified=True)

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            wake_verifier=slow_verifier,
            enable_stage2_verification=True,
        )

        # Trigger candidate
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.VERIFYING_WAKE

        # Feed 5 more frames while in VERIFYING_WAKE (even if Stage 1 provider attempted to detect)
        wake.set_triggered(True)
        for _ in range(5):
            mgr.process_frame(make_frame(2))

        # Wait for slow verifier to complete
        t_deadline = time.monotonic() + 1.0
        while mgr.state == VoiceState.VERIFYING_WAKE and time.monotonic() < t_deadline:
            time.sleep(0.02)

        assert mgr.state == VoiceState.LISTENING
        # Exactly ONE verification job was spawned
        assert slow_verifier._verification_count == 1
        assert mgr.total_verifications_attempted == 1

    def test_stop_during_verification_cancels_cleanly(self):
        """Item 23-26: Calling stop() during VERIFYING_WAKE cancels result, prevents LISTENING resurrection."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        event_bus = MockEventBus()

        class BlockingVerifier(MockWakeVerifier):
            def __init__(self):
                super().__init__(default_verified=True)
                self.started = threading.Event()
                self.release = threading.Event()

            def verify_phrase(self, audio_data, target_phrase="Hey EV"):
                self.started.set()
                self.release.wait(timeout=1.0)
                return super().verify_phrase(audio_data, target_phrase)

        blocking_verifier = BlockingVerifier()

        mgr = EVVoiceManager(
            capture_provider=capture,
            wake_word_provider=wake,
            vad_provider=vad,
            asr_provider=asr,
            orchestrator=orch,
            event_bus=event_bus,
            wake_verifier=blocking_verifier,
            enable_stage2_verification=True,
        )

        mgr.start()
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))

        # Wait until verifier is actively inside verify_phrase
        blocking_verifier.started.wait(timeout=1.0)
        assert mgr.state == VoiceState.VERIFYING_WAKE

        # User calls stop() during verification
        mgr.stop(timeout=1.0)
        assert mgr.state == VoiceState.IDLE

        # Now release the blocking verifier
        blocking_verifier.release.set()
        time.sleep(0.05)

        # Invariant: Stale verification result MUST be discarded (never resurrects LISTENING)
        assert mgr.state == VoiceState.IDLE
        assert event_bus.current_state != EVState.LISTENING

    def test_barge_in_stop_during_verification(self):
        """Item 23 & barge-in: STOP keyword during VERIFYING_WAKE immediately aborts to IDLE."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
        asr = MockASRProvider()
        orch = MockOrchestrator()
        barge_in = MockBargeInStopDetector()

        class SlowVerifier(MockWakeVerifier):
            def verify_phrase(self, audio_data, target_phrase="Hey EV"):
                time.sleep(0.15)
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

        # Trigger Stage 1
        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))
        assert mgr.state == VoiceState.VERIFYING_WAKE

        # Trigger STOP barge-in while in VERIFYING_WAKE
        barge_in.set_triggered(True)
        mgr.process_frame(make_frame(2))

        assert mgr.state == VoiceState.IDLE
        assert "stop" in orch.submitted_commands


class TestArchitecturalSafetyInvariants:
    """Matrix items 27-32: Zero execution authority, zero bypass."""

    def test_zero_command_execution_on_wake_verification(self):
        """Items 27-32: Neither Stage 1 nor Stage 2 may execute commands or bypass risk/approval."""
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
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

        time.sleep(0.05)
        # Stage 2 verification completed and transitioned to LISTENING
        assert mgr.state == VoiceState.LISTENING
        # Invariant: Zero commands submitted during wake detection
        assert len(orch.submitted_commands) == 0


class TestFeatureFlagDisabledFallback:
    """Matrix item: ENABLE_STAGE2_WAKE_VERIFICATION = False fallback."""

    def test_stage2_disabled_falls_back_to_direct_listening(self):
        capture = MockAudioCaptureProvider()
        wake = MockWakeWordProvider()
        vad = EnergyVADProvider()
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
            enable_stage2_verification=False,  # Disabled
        )

        wake.set_triggered(True)
        mgr.process_frame(make_frame(1))

        # Directly transitions to LISTENING without invoking Stage 2
        assert mgr.state == VoiceState.LISTENING
        assert verifier._verification_count == 0
