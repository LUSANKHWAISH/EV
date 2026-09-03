"""
Unit tests for Automated Speech Recognition (ASR) Foundation (Task 014D).

Verifies:
  - ASRResult immutability, validation bounds, and privacy repr.
  - EVASRProvider interface compliance and MockASRProvider behavior.
  - Audio utilities: frames_to_pcm, calculate_utterance_duration.
  - Empty utterance handling (returns empty transcript safely).
  - Privacy invariants: zero disk writes, zero raw audio leaks.
  - Architectural execution isolation: zero coupling to orchestrator, queue, agent, TTS, risk.
"""
import inspect
import os
import time
from typing import List

import pytest

import core.asr as asr_module
from core.asr import (
    ASRResult,
    EVASRProvider,
    MockASRProvider,
    calculate_utterance_duration,
    frames_to_pcm,
)
from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_FRAME_DURATION_SEC,
    DEFAULT_SAMPLES_PER_FRAME,
    AudioFrame,
    create_silence_frame,
)


# ============================================================================
# 1. ASRResult Tests
# ============================================================================
class TestASRResult:
    def test_valid_construction(self):
        res = ASRResult(
            text="open VS Code",
            confidence=0.96,
            language="en",
            duration_seconds=1.5,
            timestamp=123.456,
            provider="mock_asr",
        )
        assert res.text == "open VS Code"
        assert res.confidence == 0.96
        assert res.language == "en"
        assert res.duration_seconds == 1.5
        assert res.timestamp == 123.456
        assert res.provider == "mock_asr"

    def test_frozen_immutability(self):
        res = ASRResult(
            text="status",
            confidence=0.9,
            language="en",
            duration_seconds=1.0,
            timestamp=1.0,
            provider="mock_asr",
        )
        with pytest.raises((AttributeError, TypeError)):
            res.text = "modified"  # type: ignore[misc]

    def test_confidence_boundary_validation(self):
        # Boundaries 0.0 and 1.0 are valid
        ASRResult("cmd", 0.0, "en", 1.0, 1.0, "p")
        ASRResult("cmd", 1.0, "en", 1.0, 1.0, "p")

        with pytest.raises(ValueError, match="confidence must be in range"):
            ASRResult("cmd", -0.01, "en", 1.0, 1.0, "p")

        with pytest.raises(ValueError, match="confidence must be in range"):
            ASRResult("cmd", 1.01, "en", 1.0, 1.0, "p")

    def test_invalid_types_rejected(self):
        with pytest.raises(TypeError, match="text must be str"):
            ASRResult(123, 0.9, "en", 1.0, 1.0, "p")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="confidence must be numeric"):
            ASRResult("cmd", "high", "en", 1.0, 1.0, "p")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="language must be str"):
            ASRResult("cmd", 0.9, 123, 1.0, 1.0, "p")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="duration_seconds must be numeric"):
            ASRResult("cmd", 0.9, "en", "1s", 1.0, "p")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="timestamp must be numeric"):
            ASRResult("cmd", 0.9, "en", 1.0, "now", "p")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="provider must be str"):
            ASRResult("cmd", 0.9, "en", 1.0, 1.0, None)  # type: ignore[arg-type]

    def test_negative_duration_rejected(self):
        with pytest.raises(ValueError, match="duration_seconds must be non-negative"):
            ASRResult("cmd", 0.9, "en", -0.5, 1.0, "p")

    def test_safe_repr(self):
        res = ASRResult("check CPU usage", 0.95, "en", 2.10, 10.0, "mock_asr")
        rep = repr(res)
        assert "text='check CPU usage'" in rep
        assert "conf=0.95" in rep
        assert "dur=2.10s" in rep
        assert "provider='mock_asr'" in rep


# ============================================================================
# 2. MockASRProvider Tests
# ============================================================================
class TestMockASRProvider:
    def test_provider_contract(self):
        provider = MockASRProvider()
        assert isinstance(provider, EVASRProvider)
        assert provider.provider_name == "mock_asr"
        assert provider.is_available() is True
        assert provider.transcription_count == 0

    def test_default_transcription(self):
        provider = MockASRProvider(default_text="open terminal")
        frames = [create_silence_frame() for _ in range(3)]
        res = provider.transcribe(frames)

        assert res.text == "open terminal"
        assert res.confidence == 0.95
        assert res.language == "en"
        assert res.duration_seconds == pytest.approx(0.090, rel=1e-3)
        assert res.provider == "mock_asr"
        assert res.timestamp > 0.0
        assert provider.transcription_count == 1
        assert len(provider.get_last_frames()) == 3

    def test_custom_language(self):
        provider = MockASRProvider(default_text="hola")
        frames = [create_silence_frame()]
        res = provider.transcribe(frames, language="es")
        assert res.language == "es"

    def test_empty_frame_sequence(self):
        provider = MockASRProvider(default_text="ignored")
        res = provider.transcribe([])
        assert res.text == ""
        assert res.confidence == 0.0
        assert res.duration_seconds == 0.0
        assert res.provider == "mock_asr"

    def test_scripted_results(self):
        r1 = ASRResult("command 1", 0.9, "en", 1.0, 1.0, "mock_asr")
        provider = MockASRProvider(scripted_results=[r1, "command 2"])

        frames = [create_silence_frame()]

        res1 = provider.transcribe(frames)
        assert res1 is r1
        assert res1.text == "command 1"

        res2 = provider.transcribe(frames)
        assert res2.text == "command 2"

        # After script exhaustion, falls back to default
        res3 = provider.transcribe(frames)
        assert res3.text == provider.default_text

    def test_reset(self):
        provider = MockASRProvider(scripted_results=["cmd1", "cmd2"])
        frames = [create_silence_frame()]
        provider.transcribe(frames)
        assert provider.transcription_count == 1

        provider.reset()
        assert provider.transcription_count == 0
        assert provider.get_last_frames() == []

        # Script starts over
        res = provider.transcribe(frames)
        assert res.text == "cmd1"

    def test_invalid_input_rejected(self):
        provider = MockASRProvider()
        with pytest.raises(TypeError, match="Expected sequence of AudioFrame"):
            provider.transcribe("not_a_sequence")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="is not an AudioFrame"):
            provider.transcribe([create_silence_frame(), "invalid_frame"])  # type: ignore[list-item]


# ============================================================================
# 3. Audio Utility Tests
# ============================================================================
class TestAudioUtilities:
    def test_frames_to_pcm_single_frame(self):
        frame = AudioFrame(data=b"\x01\x02" * 480)
        pcm = frames_to_pcm([frame])
        assert pcm == frame.data
        assert len(pcm) == DEFAULT_BYTES_PER_FRAME

    def test_frames_to_pcm_multiple_frames_preserves_order(self):
        f1 = AudioFrame(data=b"\x01\x01" * 480)
        f2 = AudioFrame(data=b"\x02\x02" * 480)
        f3 = AudioFrame(data=b"\x03\x03" * 480)

        pcm = frames_to_pcm([f1, f2, f3])
        assert len(pcm) == DEFAULT_BYTES_PER_FRAME * 3
        assert pcm == (b"\x01\x01" * 480) + (b"\x02\x02" * 480) + (b"\x03\x03" * 480)

    def test_frames_to_pcm_empty_sequence(self):
        assert frames_to_pcm([]) == b""

    def test_frames_to_pcm_invalid_elements_rejected(self):
        with pytest.raises(TypeError, match="Expected sequence of AudioFrame"):
            frames_to_pcm(None)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="is not an AudioFrame"):
            frames_to_pcm([b"raw_bytes"])  # type: ignore[list-item]

    def test_calculate_utterance_duration(self):
        f1 = AudioFrame(data=b"\x00\x00" * 480)  # 30 ms
        f2 = AudioFrame(data=b"\x00\x00" * 480)  # 30 ms
        dur = calculate_utterance_duration([f1, f2])
        assert dur == pytest.approx(0.060, rel=1e-3)

    def test_calculate_utterance_duration_empty(self):
        assert calculate_utterance_duration([]) == 0.0

    def test_calculate_utterance_duration_invalid_elements_rejected(self):
        with pytest.raises(TypeError, match="Expected sequence of AudioFrame"):
            calculate_utterance_duration(123)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="is not an AudioFrame"):
            calculate_utterance_duration(["invalid"])  # type: ignore[list-item]


# ============================================================================
# 4. Privacy & Safety Tests
# ============================================================================
class TestASRPrivacyAndSafety:
    def test_zero_disk_writes(self):
        before = set(os.listdir("."))
        provider = MockASRProvider(default_text="test transcript")
        frames = [create_silence_frame() for _ in range(10)]
        pcm = frames_to_pcm(frames)
        assert len(pcm) == DEFAULT_BYTES_PER_FRAME * 10
        res = provider.transcribe(frames)
        assert res.text == "test transcript"

        after = set(os.listdir("."))
        assert after == before, "ASR operations created unwanted files on disk"

    def test_no_raw_audio_in_result(self):
        res = ASRResult("cmd", 0.9, "en", 1.0, 1.0, "mock")
        # Ensure no byte buffer attribute exists
        for val in vars(res).values():
            assert not isinstance(val, (bytes, bytearray, memoryview))


# ============================================================================
# 5. Execution Isolation Verification
# ============================================================================
class TestExecutionIsolation:
    def test_core_asr_has_no_execution_coupling(self):
        """
        Verify that core/asr.py contains zero imports, calls, or bindings to
        execution authority, task queue, agent, or TTS subsystems.
        """
        source = inspect.getsource(asr_module)
        forbidden_symbols = [
            "EVOrchestrator",
            "EVTaskQueue",
            "EVTTSManager",
            "EVAgent",
            "EVRiskEngine",
            "CancellationToken",
            "CommandResolver",
        ]
        for symbol in forbidden_symbols:
            assert symbol not in source, f"Forbidden execution coupling '{symbol}' found in core/asr.py"

    def test_confidence_integer_coercion(self):
        # 1 and 0 as integers are accepted and converted to float
        r1 = ASRResult("cmd", 1, "en", 1.0, 1.0, "p")
        assert r1.confidence == 1.0
        r0 = ASRResult("cmd", 0, "en", 1.0, 1.0, "p")
        assert r0.confidence == 0.0

    def test_frames_to_pcm_length_consistency(self):
        # 5 canonical frames -> exactly 4800 bytes
        frames = [create_silence_frame() for _ in range(5)]
        pcm = frames_to_pcm(frames)
        assert len(pcm) == 5 * DEFAULT_BYTES_PER_FRAME
        assert len(pcm) // 2 == 5 * DEFAULT_SAMPLES_PER_FRAME

    def test_calculate_utterance_duration_multiple_canonical(self):
        # 10 frames -> 0.300 seconds
        frames = [create_silence_frame() for _ in range(10)]
        dur = calculate_utterance_duration(frames)
        assert dur == pytest.approx(0.300, rel=1e-3)

    def test_mock_provider_retains_frames_copy(self):
        provider = MockASRProvider()
        frames = [create_silence_frame()]
        provider.transcribe(frames)
        last = provider.get_last_frames()
        assert len(last) == 1
        last.clear()
        assert len(provider.get_last_frames()) == 1

    def test_timestamp_is_recent_monotonic(self):
        provider = MockASRProvider(default_text="ts_test")
        t_before = time.monotonic()
        res = provider.transcribe([create_silence_frame()])
        t_after = time.monotonic()
        assert t_before <= res.timestamp <= t_after
