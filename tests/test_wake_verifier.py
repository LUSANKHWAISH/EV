"""
Unit tests for Stage-2 Local Phrase Verifier and Two-Stage Wake-Word Pipeline (Task 014F-12A).

Verifies:
  1. WakeVerificationResult immutable contract, field validation, and repr.
  2. MockWakeVerifier deterministic operation, scripted responses, and reset.
  3. FasterWhisperWakeVerifier:
     - Availability and initialization.
     - Text normalization and strict keyword/prefix rejection rules.
     - Rejection of confusable hard negatives: 'Hey Evan', 'Hey Evelyn', 'Hey Everyone', 'Hey Stevie', etc.
     - Acceptance of valid phrase variations: 'Hey EV', 'Hey E V', 'Hey ee vee'.
     - Audio format conversions: AudioFrame sequence, raw PCM16 bytes, int16 array, float32 array.
     - Rejection of empty or too-short audio frames.
  4. TwoStageWakeWordPipeline:
     - Buffering of incoming AudioFrames up to buffer duration.
     - Stage 2 invocation ONLY when Stage 1 triggers detection.
     - End-to-end integration with mock and real providers.
  5. Architectural Safety: Zero execution coupling, zero orchestrator imports, zero task authorization.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.voice_capture import AudioFrame
from core.wake_verifier import (
    EVWakeVerifier,
    FasterWhisperWakeVerifier,
    MockWakeVerifier,
    TwoStageWakeWordPipeline,
    WakeVerificationResult,
)


class TestWakeVerificationResultContract:
    """Test suite for WakeVerificationResult dataclass contract and validation."""

    def test_valid_result_construction(self):
        res = WakeVerificationResult(
            verified=True,
            confidence=0.95,
            reason="EXACT_MATCH",
            raw_transcript="Hey EV",
            latency_ms=12.5,
            provider="test_provider",
            timestamp=100.0,
        )
        assert res.verified is True
        assert res.confidence == 0.95
        assert res.reason == "EXACT_MATCH"
        assert res.raw_transcript == "Hey EV"
        assert res.latency_ms == 12.5
        assert res.provider == "test_provider"
        assert res.timestamp == 100.0
        assert "VERIFIED" in repr(res)
        assert "12.5ms" in repr(res)

    def test_rejected_result_repr(self):
        res = WakeVerificationResult(
            verified=False,
            confidence=0.10,
            reason="REJECTED_KEYWORD_EVAN",
            raw_transcript="Hey Evan",
            latency_ms=8.0,
            provider="test_provider",
            timestamp=101.0,
        )
        assert res.verified is False
        assert "REJECTED" in repr(res)
        assert "REJECTED_KEYWORD_EVAN" in repr(res)

    def test_immutability(self):
        res = WakeVerificationResult(
            verified=True,
            confidence=0.90,
            reason="EXACT_MATCH",
            raw_transcript="Hey EV",
            latency_ms=10.0,
            provider="test",
            timestamp=1.0,
        )
        with pytest.raises(Exception):
            res.verified = False  # Frozen dataclass should reject mutations

    def test_type_and_bounds_validation(self):
        # Invalid confidence bounds (> 1.0)
        with pytest.raises(ValueError):
            WakeVerificationResult(
                verified=True,
                confidence=1.5,
                reason="EXACT",
                raw_transcript="Hey EV",
                latency_ms=10.0,
                provider="test",
                timestamp=1.0,
            )

        # Invalid confidence bounds (< 0.0)
        with pytest.raises(ValueError):
            WakeVerificationResult(
                verified=True,
                confidence=-0.1,
                reason="EXACT",
                raw_transcript="Hey EV",
                latency_ms=10.0,
                provider="test",
                timestamp=1.0,
            )

        # Invalid verified type
        with pytest.raises(TypeError):
            WakeVerificationResult(
                verified="yes",  # type: ignore
                confidence=0.5,
                reason="EXACT",
                raw_transcript="Hey EV",
                latency_ms=10.0,
                provider="test",
                timestamp=1.0,
            )


class TestMockWakeVerifier:
    """Test suite for MockWakeVerifier operations and scripting."""

    def test_mock_default_behavior(self):
        mock = MockWakeVerifier(default_verified=True, default_confidence=0.99, default_reason="MOCK_OK")
        dummy_audio = np.zeros(16000, dtype=np.int16)
        res = mock.verify_phrase(dummy_audio)
        assert res.verified is True
        assert res.confidence == 0.99
        assert res.reason == "MOCK_OK"
        assert mock.is_available() is True
        assert mock.provider_name == "mock_verifier"

    def test_mock_scripted_sequence(self):
        r1 = WakeVerificationResult(True, 0.9, "OK1", "Hey EV", 1.0, "mock", 1.0)
        r2 = WakeVerificationResult(False, 0.1, "REJECT1", "Hey Evan", 1.0, "mock", 2.0)
        mock = MockWakeVerifier(scripted_results=[r1, r2])

        dummy = np.zeros(1600, dtype=np.int16)
        assert mock.verify_phrase(dummy).reason == "OK1"
        assert mock.verify_phrase(dummy).reason == "REJECT1"
        # Falls back to default
        assert mock.verify_phrase(dummy).reason == "MOCK_VERIFIED"

        mock.reset()
        assert mock.verify_phrase(dummy).reason == "OK1"


class TestFasterWhisperWakeVerifier:
    """Test suite for FasterWhisperWakeVerifier decision rules and transcript evaluation."""

    @pytest.fixture(scope="class")
    def verifier(self):
        v = FasterWhisperWakeVerifier(
            model_size_or_path="tiny.en",
            device="cpu",
            compute_type="int8",
            cpu_threads=2,
            download_root=r"D:\EV\models\asr",
        )
        return v

    def test_normalize_text(self, verifier):
        assert verifier._normalize("Hey, E.V.!") == "hey e v"
        assert verifier._normalize("  Hey   EV  ") == "hey ev"
        assert verifier._normalize("Hey... EV???") == "hey ev"

    def test_evaluate_transcript_positive_matches(self, verifier):
        # Exact phrases
        v, c, r = verifier._evaluate_transcript("Hey EV")
        assert v is True
        assert "EXACT" in r or "NORMALIZED" in r

        v, c, r = verifier._evaluate_transcript("Hey E.V.")
        assert v is True

        v, c, r = verifier._evaluate_transcript("hey e v")
        assert v is True

        v, c, r = verifier._evaluate_transcript("Hey V")
        assert v is True

        v, c, r = verifier._evaluate_transcript("hey ee vee")
        assert v is True

    def test_evaluate_transcript_hard_negatives_rejection(self, verifier):
        hard_negs = [
            "Hey Evan",
            "Hey Evelyn",
            "Hey Everyone",
            "Hey Everybody",
            "Hey Evidence",
            "Hey Event",
            "Hey Events",
            "Hey Everest",
            "Hey Everett",
            "Hey Everywhere",
            "Hey Eventually",
            "Hey Everyday",
            "Hey Stevie",
            "Hey Steve",
            "Every",
            "Heavy duty",
            "Heavy rain",
        ]
        for phrase in hard_negs:
            v, c, r = verifier._evaluate_transcript(phrase)
            assert v is False, f"Phrase '{phrase}' must be REJECTED, but was accepted (reason: {r})"
            assert "REJECTED_KEYWORD" in r or "UNMATCHED" in r

    def test_evaluate_transcript_incomplete_rejection(self, verifier):
        incompletes = ["Hey", "Hi", "A", "The", "He", "Oh"]
        for phrase in incompletes:
            v, c, r = verifier._evaluate_transcript(phrase)
            assert v is False, f"Incomplete prefix '{phrase}' must be REJECTED"
            assert "INCOMPLETE" in r or "UNMATCHED" in r

    def test_evaluate_empty_audio_and_short_audio(self, verifier):
        # Empty array
        res_empty = verifier.verify_phrase(np.array([], dtype=np.int16))
        assert res_empty.verified is False
        assert res_empty.reason == "AUDIO_TOO_SHORT"

        # Too short (< 100ms / 1600 samples)
        short_audio = np.zeros(800, dtype=np.int16)
        res_short = verifier.verify_phrase(short_audio)
        assert res_short.verified is False
        assert res_short.reason == "AUDIO_TOO_SHORT"

    def test_audio_format_compatibility(self, verifier):
        # Test 1 second of silence with different input formats
        samples = 16000
        raw_pcm16 = np.zeros(samples, dtype=np.int16).tobytes()
        arr_int16 = np.zeros(samples, dtype=np.int16)
        arr_float32 = np.zeros(samples, dtype=np.float32)
        frames = [
            AudioFrame(raw_pcm16[i : i + 960], 16000, 1, 2, i / 32000.0)
            for i in range(0, len(raw_pcm16), 960)
        ]

        # Verify all formats execute without error
        res_pcm = verifier.verify_phrase(raw_pcm16)
        res_int16 = verifier.verify_phrase(arr_int16)
        res_float = verifier.verify_phrase(arr_float32)
        res_frames = verifier.verify_phrase(frames)

        assert isinstance(res_pcm, WakeVerificationResult)
        assert isinstance(res_int16, WakeVerificationResult)
        assert isinstance(res_float, WakeVerificationResult)
        assert isinstance(res_frames, WakeVerificationResult)


class DummyStage1Provider:
    """Mock Stage 1 Provider simulating openWakeWord output."""

    def __init__(self, scores: List[float]) -> None:
        self.scores = scores
        self.index = 0

    def process_frame(self, frame: AudioFrame):
        class DummyResult:
            def __init__(self, score, detected):
                self.score = score
                self.detected = detected

        if self.index < len(self.scores):
            s = self.scores[self.index]
            self.index += 1
            return DummyResult(score=s, detected=(s >= 0.50))
        return DummyResult(score=0.0, detected=False)

    def reset(self):
        self.index = 0


class TestTwoStageWakeWordPipeline:
    """Test suite for TwoStageWakeWordPipeline coordination and isolation."""

    def test_stage2_only_invoked_on_stage1_trigger(self):
        # 3 frames with low score, 1 frame with high score (0.85)
        scores = [0.1, 0.2, 0.15, 0.85, 0.2]
        s1 = DummyStage1Provider(scores)
        mock_v = MockWakeVerifier(default_verified=True, default_reason="MOCK_CONFIRMED")
        pipeline = TwoStageWakeWordPipeline(stage1_provider=s1, stage2_verifier=mock_v, buffer_seconds=2.0)

        # Send frames 1 to 3 -> Stage 2 should not run
        frame_bytes = b"\x00" * 960
        for i in range(3):
            f = AudioFrame(frame_bytes, 16000, 1, 2, i * 0.03)
            r1, r2 = pipeline.process_frame(f)
            assert r1.detected is False
            assert r2 is None
            assert mock_v._verification_count == 0

        # Frame 4 (score 0.85) -> Stage 2 should run
        f4 = AudioFrame(frame_bytes, 16000, 1, 2, 3 * 0.03)
        r1, r2 = pipeline.process_frame(f4)
        assert r1.detected is True
        assert r2 is not None
        assert r2.verified is True
        assert r2.reason == "MOCK_CONFIRMED"
        assert mock_v._verification_count == 1

        # Frame 5 (score 0.2) -> Stage 2 should not run again
        f5 = AudioFrame(frame_bytes, 16000, 1, 2, 4 * 0.03)
        r1, r2 = pipeline.process_frame(f5)
        assert r1.detected is False
        assert r2 is None
        assert mock_v._verification_count == 1

    def test_pipeline_reset_clears_buffer_and_state(self):
        s1 = DummyStage1Provider([0.9])
        mock_v = MockWakeVerifier()
        pipeline = TwoStageWakeWordPipeline(stage1_provider=s1, stage2_verifier=mock_v)

        f = AudioFrame(b"\x00" * 960, 16000, 1, 2, 0.0)
        pipeline.process_frame(f)
        assert len(pipeline._audio_buffer) == 1
        assert pipeline._stage1_triggers == 1

        pipeline.reset()
        assert len(pipeline._audio_buffer) == 0
        assert pipeline._stage1_triggers == 0
        assert pipeline._stage2_verifications == 0


class TestSafetyIsolationGuarantees:
    """Verify architectural boundaries: zero execution authority, no external command coupling."""

    def test_verifier_module_has_no_execution_imports(self):
        import core.wake_verifier as wv

        module_attrs = dir(wv)
        # Ensure no execution orchestrators or subprocesses leaked into wake_verifier
        assert "subprocess" not in module_attrs
        assert "EVOrchestrator" not in module_attrs
        assert "RiskEngine" not in module_attrs
        assert "execute" not in module_attrs

    def test_result_contains_no_execution_fields(self):
        res = WakeVerificationResult(
            verified=True,
            confidence=0.99,
            reason="EXACT_MATCH",
            raw_transcript="Hey EV",
            latency_ms=5.0,
            provider="test",
            timestamp=0.0,
        )
        fields = set(res.__dataclass_fields__.keys())
        forbidden_fields = {"execute", "command", "task_id", "bypass", "approved", "role", "god_mode"}
        assert fields.isdisjoint(forbidden_fields), f"Forbidden authorization fields found: {fields & forbidden_fields}"
