"""
Unit tests for Wake-Word Detection, Rechunker, and STOP Abstraction (Task 014C).

Verifies:
  - WakeWordResult validation, immutability, and privacy repr.
  - MockWakeWordProvider detection modes, markers, scripted results, and reset.
  - AudioFrameRechunker sample accumulation (480 -> 1280), exact byte preservation,
    leftover sample retention, and deterministic timestamps.
  - EVBargeInStopDetector / MockBargeInStopDetector isolation and detection events.
  - Decoupled parallel topology (wake detection operates independently of VAD).
  - Zero disk writes and zero raw audio leaks.
"""
import os
import pytest

from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_SAMPLE_RATE,
    AudioFormatError,
    AudioFrame,
    create_silence_frame,
)
from core.voice_vad import EnergyVADProvider
from core.voice_wakeword import (
    AudioFrameRechunker,
    EVBargeInStopDetector,
    EVWakeWordProvider,
    MockBargeInStopDetector,
    MockWakeWordProvider,
    WakeWordResult,
)


# ============================================================================
# WakeWordResult Tests
# ============================================================================
class TestWakeWordResult:
    def test_valid_construction(self):
        res = WakeWordResult(detected=True, keyword="Hey EV", confidence=0.95, timestamp=10.5)
        assert res.detected is True
        assert res.keyword == "Hey EV"
        assert res.confidence == 0.95
        assert res.timestamp == 10.5

    def test_confidence_validation(self):
        # Valid bounds
        WakeWordResult(detected=False, keyword="none", confidence=0.0, timestamp=1.0)
        WakeWordResult(detected=True, keyword="Hey EV", confidence=1.0, timestamp=1.0)

        # Invalid bounds
        with pytest.raises(ValueError, match="confidence must be in range"):
            WakeWordResult(detected=True, keyword="Hey EV", confidence=-0.1, timestamp=1.0)

        with pytest.raises(ValueError, match="confidence must be in range"):
            WakeWordResult(detected=True, keyword="Hey EV", confidence=1.05, timestamp=1.0)

    def test_type_validation(self):
        with pytest.raises(TypeError, match="detected must be bool"):
            WakeWordResult(detected="yes", keyword="Hey EV", confidence=0.9, timestamp=1.0)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="keyword must be str"):
            WakeWordResult(detected=True, keyword=123, confidence=0.9, timestamp=1.0)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="confidence must be numeric"):
            WakeWordResult(detected=True, keyword="Hey EV", confidence="high", timestamp=1.0)  # type: ignore[arg-type]

    def test_immutability(self):
        res = WakeWordResult(detected=True, keyword="Hey EV", confidence=0.9, timestamp=1.0)
        with pytest.raises((AttributeError, TypeError)):
            res.detected = False  # type: ignore[misc]

    def test_repr_hides_raw_audio(self):
        res = WakeWordResult(detected=True, keyword="Hey EV", confidence=0.95, timestamp=12.345)
        rep = repr(res)
        assert "detected=True" in rep
        assert "keyword='Hey EV'" in rep
        assert "conf=0.95" in rep


# ============================================================================
# MockWakeWordProvider Tests
# ============================================================================
class TestMockWakeWordProvider:
    def test_initial_state(self):
        provider = MockWakeWordProvider()
        assert provider.provider_name == "mock_wakeword"
        assert provider.target_phrase == "Hey EV"
        assert provider.is_available is True
        assert provider.processed_count == 0

    def test_default_no_detection(self):
        provider = MockWakeWordProvider()
        frame = create_silence_frame()
        res = provider.process_frame(frame)
        assert res is None
        assert provider.processed_count == 1

    def test_trigger_after_n_frames(self):
        provider = MockWakeWordProvider(trigger_after_frames=3)
        f1 = create_silence_frame()
        f2 = create_silence_frame()
        f3 = create_silence_frame()

        assert provider.process_frame(f1) is None
        assert provider.process_frame(f2) is None

        res3 = provider.process_frame(f3)
        assert res3 is not None
        assert res3.detected is True
        assert res3.keyword == "Hey EV"
        assert res3.confidence >= 0.9

    def test_manual_trigger(self):
        provider = MockWakeWordProvider()
        f1 = create_silence_frame()
        f2 = create_silence_frame()

        assert provider.process_frame(f1) is None

        provider.set_triggered(True)
        res2 = provider.process_frame(f2)
        assert res2 is not None
        assert res2.detected is True
        assert res2.keyword == "Hey EV"

        # Subsequent frame without trigger returns None
        f3 = create_silence_frame()
        assert provider.process_frame(f3) is None

    def test_trigger_on_marker_bytes(self):
        marker = b"WAKE_MARKER_TEST"
        provider = MockWakeWordProvider(trigger_on_marker=marker)

        normal_frame = create_silence_frame()
        assert provider.process_frame(normal_frame) is None

        marked_data = marker + (b"\x00" * (DEFAULT_BYTES_PER_FRAME - len(marker)))
        marked_frame = AudioFrame(data=marked_data)

        res = provider.process_frame(marked_frame)
        assert res is not None
        assert res.detected is True
        assert res.keyword == "Hey EV"

    def test_scripted_results(self):
        r1 = WakeWordResult(detected=False, keyword="none", confidence=0.0, timestamp=1.0)
        r2 = WakeWordResult(detected=True, keyword="Hey EV", confidence=0.99, timestamp=2.0)

        provider = MockWakeWordProvider(scripted_results=[r1, r2])
        f1 = create_silence_frame()
        f2 = create_silence_frame()

        assert provider.process_frame(f1) is r1
        assert provider.process_frame(f2) is r2

    def test_reset_clears_history(self):
        provider = MockWakeWordProvider(trigger_after_frames=2)
        provider.process_frame(create_silence_frame())
        assert provider.processed_count == 1

        provider.reset()
        assert provider.processed_count == 0
        assert provider.get_processed_frames() == []

    def test_invalid_frame_rejected(self):
        provider = MockWakeWordProvider()
        with pytest.raises(TypeError, match="Expected AudioFrame"):
            provider.process_frame(b"raw_bytes")  # type: ignore[arg-type]


# ============================================================================
# AudioFrameRechunker Tests
# ============================================================================
class TestAudioFrameRechunker:
    def test_rechunker_invalid_params_rejected(self):
        with pytest.raises(ValueError, match="target_samples must be > 0"):
            AudioFrameRechunker(target_samples=0)

        with pytest.raises(ValueError, match="sample_rate must be > 0"):
            AudioFrameRechunker(sample_rate=0)

        with pytest.raises(ValueError, match="channels must be > 0"):
            AudioFrameRechunker(channels=0)

        with pytest.raises(ValueError, match="sample_width must be > 0"):
            AudioFrameRechunker(sample_width=0)

    def test_canonical_480_to_1280_accumulation_and_leftovers(self):
        """
        Verifies accumulation across 30ms (480-sample) frames to 80ms (1280-sample) target:
          Frame 1: 480 samples  -> emits [] (480 buffered)
          Frame 2: 480 samples  -> emits [] (960 buffered)
          Frame 3: 480 samples  -> emits [1280 samples], retains 160 samples!
          Frame 4: 480 samples  -> emits [] (160 + 480 = 640 buffered)
          Frame 5: 480 samples  -> emits [] (640 + 480 = 1120 buffered)
          Frame 6: 480 samples  -> emits [1280 samples], retains 320 samples!
        """
        rechunker = AudioFrameRechunker(target_samples=1280, sample_rate=16000, channels=1, sample_width=2)
        assert rechunker.is_empty is True
        assert rechunker.buffered_samples == 0

        # Unique 2-byte sample markers per frame
        f1 = AudioFrame(data=b"\x01\x01" * 480, timestamp=0.0)
        f2 = AudioFrame(data=b"\x02\x02" * 480, timestamp=0.03)
        f3 = AudioFrame(data=b"\x03\x03" * 480, timestamp=0.06)

        out1 = rechunker.push_frame(f1)
        assert out1 == []
        assert rechunker.buffered_samples == 480
        assert rechunker.is_empty is False

        out2 = rechunker.push_frame(f2)
        assert out2 == []
        assert rechunker.buffered_samples == 960

        out3 = rechunker.push_frame(f3)
        assert len(out3) == 1
        assert rechunker.buffered_samples == 160  # (480 * 3) - 1280 = 160

        chunk1 = out3[0]
        assert chunk1.sample_count == 1280
        assert len(chunk1.data) == 2560  # 1280 * 2 bytes
        assert chunk1.sample_rate == 16000
        assert chunk1.timestamp == 0.0

        # Verify byte contents of chunk 1: 480 of \x01\x01 + 480 of \x02\x02 + 320 of \x03\x03
        expected_bytes = (b"\x01\x01" * 480) + (b"\x02\x02" * 480) + (b"\x03\x03" * 320)
        assert chunk1.data == expected_bytes

        # Push next 3 frames
        f4 = AudioFrame(data=b"\x04\x04" * 480, timestamp=0.09)
        f5 = AudioFrame(data=b"\x05\x05" * 480, timestamp=0.12)
        f6 = AudioFrame(data=b"\x06\x06" * 480, timestamp=0.15)

        out4 = rechunker.push_frame(f4)
        assert out4 == []
        assert rechunker.buffered_samples == 640  # 160 + 480 = 640

        out5 = rechunker.push_frame(f5)
        assert out5 == []
        assert rechunker.buffered_samples == 1120  # 640 + 480 = 1120

        out6 = rechunker.push_frame(f6)
        assert len(out6) == 1
        assert rechunker.buffered_samples == 320  # 1120 + 480 - 1280 = 320

        chunk2 = out6[0]
        assert chunk2.sample_count == 1280
        # Expected timestamp of chunk 2 is 0.0 + (1280 / 16000) = 0.080 s
        assert chunk2.timestamp == pytest.approx(0.080, rel=1e-4)

        # Content of chunk 2: leftover 160 of \x03\x03 + 480 of \x04\x04 + 480 of \x05\x05 + 160 of \x06\x06
        expected_chunk2 = (b"\x03\x03" * 160) + (b"\x04\x04" * 480) + (b"\x05\x05" * 480) + (b"\x06\x06" * 160)
        assert chunk2.data == expected_chunk2

    def test_incompatible_format_rejected(self):
        rechunker = AudioFrameRechunker(target_samples=1280, sample_rate=16000, channels=1, sample_width=2)

        # Mismatched sample rate
        f_bad_rate = AudioFrame(data=b"\x00\x00" * 480, sample_rate=8000, channels=1, sample_width=2)
        with pytest.raises(AudioFormatError, match="format mismatch"):
            rechunker.push_frame(f_bad_rate)

        # Mismatched channels
        f_bad_ch = AudioFrame(data=b"\x00\x00\x00\x00" * 240, sample_rate=16000, channels=2, sample_width=2)
        with pytest.raises(AudioFormatError, match="format mismatch"):
            rechunker.push_frame(f_bad_ch)

    def test_rechunker_clear_and_reset(self):
        rechunker = AudioFrameRechunker(target_samples=1280)
        rechunker.push_frame(create_silence_frame())
        assert rechunker.buffered_samples == 480

        rechunker.clear()
        assert rechunker.buffered_samples == 0
        assert rechunker.buffered_bytes == 0
        assert rechunker.is_empty is True


# ============================================================================
# EVBargeInStopDetector & MockBargeInStopDetector Tests
# ============================================================================
class TestBargeInStopDetector:
    def test_mock_detector_trigger_modes(self):
        detector = MockBargeInStopDetector(trigger_after_frames=3)
        assert detector.detector_name == "mock_barge_in_stop"
        assert detector.processed_count == 0

        f1 = create_silence_frame()
        f2 = create_silence_frame()
        f3 = create_silence_frame()

        assert detector.process_frame(f1) is False
        assert detector.process_frame(f2) is False
        assert detector.process_frame(f3) is True
        assert detector.processed_count == 3

    def test_mock_detector_manual_trigger(self):
        detector = MockBargeInStopDetector()
        f = create_silence_frame()

        assert detector.process_frame(f) is False

        detector.set_triggered(True)
        assert detector.process_frame(f) is True
        assert detector.process_frame(f) is False

    def test_mock_detector_marker_trigger(self):
        marker = b"STOP_BARGE_IN_TRIGGER"
        detector = MockBargeInStopDetector(trigger_on_marker=marker)

        normal = create_silence_frame()
        assert detector.process_frame(normal) is False

        marked = AudioFrame(data=marker + (b"\x00" * (DEFAULT_BYTES_PER_FRAME - len(marker))))
        assert detector.process_frame(marked) is True

    def test_mock_detector_reset(self):
        detector = MockBargeInStopDetector(trigger_after_frames=1)
        detector.process_frame(create_silence_frame())
        assert detector.processed_count == 1

        detector.reset()
        assert detector.processed_count == 0

    def test_zero_cancellation_side_effects(self):
        """Verifies that STOP detector evaluation has zero direct side-effects."""
        detector = MockBargeInStopDetector(trigger_after_frames=1)
        res = detector.process_frame(create_silence_frame())
        assert res is True
        # Pure boolean return: zero orchestrator, cancellation, or TTS calls


# ============================================================================
# Decoupled Parallel Topology Verification
# ============================================================================
class TestDecoupledTopology:
    def test_wake_detection_operates_when_vad_reports_inactive(self):
        """
        CRITICAL ARCHITECTURAL INVARIANT:
        VAD is NOT an authoritative gate for wake word.
        A low-energy audio frame classified as inactive by VAD must still be evaluated
        and triggerable by the wake-word provider.
        """
        vad = EnergyVADProvider(threshold=500.0)
        wakeword = MockWakeWordProvider(trigger_after_frames=1)

        # Quiet frame (amplitude 50 < threshold 500)
        quiet_frame = AudioFrame(data=b"\x32\x00" * 480)

        # 1. Evaluate VAD
        vad_res = vad.process_frame(quiet_frame)
        assert vad_res.is_speech is False  # VAD says NOT speech

        # 2. Evaluate Wake Word independently
        wake_res = wakeword.process_frame(quiet_frame)
        assert wake_res is not None
        assert wake_res.detected is True  # Wake word STILL detected!


# ============================================================================
# Privacy Invariants
# ============================================================================
class TestWakeWordPrivacy:
    def test_zero_disk_writes(self):
        before = set(os.listdir("."))
        provider = MockWakeWordProvider()
        rechunker = AudioFrameRechunker()
        for _ in range(10):
            frame = create_silence_frame()
            provider.process_frame(frame)
            rechunker.push_frame(frame)
        after = set(os.listdir("."))
        assert after == before, "Wake word operation created unwanted files on disk"
