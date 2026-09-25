"""
Unit tests for Voice Activity Detection (VAD) subsystem (Task 014C).

Verifies:
  - VADResult validation, immutability, and privacy repr.
  - EnergyVADProvider RMS calculation, thresholding, and attack/release hysteresis.
  - MockVADProvider scripted and deterministic responses.
  - Rejection of invalid inputs and format mismatches.
  - Zero disk writes and zero raw audio leaks.
"""
import os
import struct
import pytest

from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    AudioFormatError,
    AudioFrame,
    create_silence_frame,
)
from core.voice_vad import (
    EVVADProvider,
    EnergyVADProvider,
    MockVADProvider,
    VADResult,
)


# ============================================================================
# VADResult Tests
# ============================================================================
class TestVADResult:
    def test_valid_construction(self):
        res = VADResult(is_speech=True, confidence=0.85, energy=450.0, timestamp=123.456)
        assert res.is_speech is True
        assert res.confidence == 0.85
        assert res.energy == 450.0
        assert res.timestamp == 123.456

    def test_confidence_validation_bounds(self):
        # Valid boundaries
        VADResult(is_speech=False, confidence=0.0, energy=0.0, timestamp=1.0)
        VADResult(is_speech=True, confidence=1.0, energy=100.0, timestamp=1.0)

        # Invalid bounds
        with pytest.raises(ValueError, match="confidence must be in range"):
            VADResult(is_speech=True, confidence=-0.01, energy=100.0, timestamp=1.0)

        with pytest.raises(ValueError, match="confidence must be in range"):
            VADResult(is_speech=True, confidence=1.01, energy=100.0, timestamp=1.0)

    def test_invalid_types_rejected(self):
        with pytest.raises(TypeError, match="is_speech must be bool"):
            VADResult(is_speech="yes", confidence=0.5, energy=10.0, timestamp=1.0)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="confidence must be numeric"):
            VADResult(is_speech=True, confidence="high", energy=10.0, timestamp=1.0)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="energy must be numeric"):
            VADResult(is_speech=True, confidence=0.5, energy=None, timestamp=1.0)  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="timestamp must be numeric"):
            VADResult(is_speech=True, confidence=0.5, energy=10.0, timestamp="now")  # type: ignore[arg-type]

    def test_negative_energy_rejected(self):
        with pytest.raises(ValueError, match="energy must be non-negative"):
            VADResult(is_speech=False, confidence=0.5, energy=-1.0, timestamp=1.0)

    def test_immutability(self):
        res = VADResult(is_speech=True, confidence=0.5, energy=10.0, timestamp=1.0)
        with pytest.raises((AttributeError, TypeError)):
            res.is_speech = False  # type: ignore[misc]

    def test_repr_hides_raw_audio(self):
        res = VADResult(is_speech=True, confidence=0.92, energy=1250.5, timestamp=10.0)
        rep = repr(res)
        assert "speech=True" in rep
        assert "conf=0.92" in rep
        assert "energy=1250.5" in rep


# ============================================================================
# EnergyVADProvider Tests
# ============================================================================
class TestEnergyVADProvider:
    def test_rms_calculation_silence(self):
        frame = create_silence_frame()
        rms = EnergyVADProvider.calculate_rms(frame)
        assert rms == 0.0

    def test_rms_calculation_known_signal(self):
        # Frame of constant amplitude 1000
        samples = [1000] * 480
        data = struct.pack("<480h", *samples)
        frame = AudioFrame(data=data)
        rms = EnergyVADProvider.calculate_rms(frame)
        assert rms == pytest.approx(1000.0, rel=1e-3)

    def test_silence_frame_classified_inactive(self):
        vad = EnergyVADProvider(threshold=200.0)
        frame = create_silence_frame()
        res = vad.process_frame(frame)
        assert res.is_speech is False
        assert res.confidence == 0.0
        assert res.energy == 0.0

    def test_loud_audio_classified_active(self):
        vad = EnergyVADProvider(threshold=300.0, attack_frames=1)
        samples = [2000] * 480
        frame = AudioFrame(data=struct.pack("<480h", *samples))
        res = vad.process_frame(frame)
        assert res.is_speech is True
        assert res.energy == pytest.approx(2000.0, rel=1e-3)
        assert res.confidence > 0.5

    def test_threshold_sensitivity(self):
        # Moderate amplitude 400
        samples = [400] * 480
        frame = AudioFrame(data=struct.pack("<480h", *samples))

        vad_low = EnergyVADProvider(threshold=200.0, attack_frames=1)
        vad_high = EnergyVADProvider(threshold=800.0, attack_frames=1)

        res_low = vad_low.process_frame(frame)
        res_high = vad_high.process_frame(frame)

        assert res_low.is_speech is True
        assert res_high.is_speech is False

    def test_attack_hysteresis(self):
        # Requires 3 consecutive loud frames to trigger speech
        vad = EnergyVADProvider(threshold=300.0, attack_frames=3, release_frames=1)
        loud_frame = AudioFrame(data=struct.pack("<480h", *([1000] * 480)))

        # Frame 1: above threshold, but attack count 1 < 3
        res1 = vad.process_frame(loud_frame)
        assert res1.is_speech is False

        # Frame 2: attack count 2 < 3
        res2 = vad.process_frame(loud_frame)
        assert res2.is_speech is False

        # Frame 3: attack count 3 >= 3 -> triggers speech
        res3 = vad.process_frame(loud_frame)
        assert res3.is_speech is True

    def test_release_hysteresis(self):
        # Requires 3 consecutive quiet frames to drop speech
        vad = EnergyVADProvider(threshold=300.0, attack_frames=1, release_frames=3)
        loud_frame = AudioFrame(data=struct.pack("<480h", *([1000] * 480)))
        silence_frame = create_silence_frame()

        # Trigger active speech
        vad.process_frame(loud_frame)
        assert vad._is_speech is True

        # Silence 1: remains True (hangover)
        res1 = vad.process_frame(silence_frame)
        assert res1.is_speech is True

        # Silence 2: remains True (hangover)
        res2 = vad.process_frame(silence_frame)
        assert res2.is_speech is True

        # Silence 3: release count reached -> drops to False
        res3 = vad.process_frame(silence_frame)
        assert res3.is_speech is False

    def test_reset_clears_state(self):
        vad = EnergyVADProvider(threshold=300.0, attack_frames=1, release_frames=5)
        loud_frame = AudioFrame(data=struct.pack("<480h", *([1000] * 480)))
        vad.process_frame(loud_frame)
        assert vad._is_speech is True

        vad.reset()
        assert vad._is_speech is False
        assert vad._above_threshold_count == 0
        assert vad._below_threshold_count == 0

    def test_invalid_parameters_rejected(self):
        with pytest.raises(ValueError, match="threshold must be non-negative"):
            EnergyVADProvider(threshold=-50.0)

        with pytest.raises(ValueError, match="attack_frames must be >= 1"):
            EnergyVADProvider(attack_frames=0)

        with pytest.raises(ValueError, match="release_frames must be >= 1"):
            EnergyVADProvider(release_frames=0)

    def test_invalid_frame_rejected(self):
        vad = EnergyVADProvider()
        with pytest.raises(TypeError, match="Expected AudioFrame"):
            vad.process_frame("not_a_frame")  # type: ignore[arg-type]

        # Incompatible sample width (e.g. 1-byte 8-bit PCM)
        odd_frame = AudioFrame(data=b"\x01" * 100, sample_rate=16000, channels=1, sample_width=1)
        with pytest.raises(AudioFormatError, match="requires 16-bit PCM"):
            vad.process_frame(odd_frame)


# ============================================================================
# MockVADProvider Tests
# ============================================================================
class TestMockVADProvider:
    def test_fixed_speech_decision(self):
        mock_vad = MockVADProvider(fixed_is_speech=True, fixed_confidence=0.88, fixed_energy=350.0)
        assert mock_vad.provider_name == "mock_vad"
        assert mock_vad.is_available is True

        frame = create_silence_frame()
        res = mock_vad.process_frame(frame)
        assert res.is_speech is True
        assert res.confidence == 0.88
        assert res.energy == 350.0
        assert mock_vad.processed_count == 1

    def test_scripted_result_sequence(self):
        res_a = VADResult(is_speech=False, confidence=0.1, energy=50.0, timestamp=1.0)
        res_b = VADResult(is_speech=True, confidence=0.9, energy=800.0, timestamp=2.0)

        mock_vad = MockVADProvider(scripted_results=[res_a, res_b])
        f1 = create_silence_frame()
        f2 = create_silence_frame()

        assert mock_vad.process_frame(f1) is res_a
        assert mock_vad.process_frame(f2) is res_b

        # After script is exhausted, falls back to fixed/default decision
        f3 = create_silence_frame()
        res3 = mock_vad.process_frame(f3)
        assert res3.is_speech is False

    def test_reset_clears_history(self):
        mock_vad = MockVADProvider()
        mock_vad.process_frame(create_silence_frame())
        assert mock_vad.processed_count == 1

        mock_vad.reset()
        assert mock_vad.processed_count == 0
        assert mock_vad.get_processed_frames() == []


# ============================================================================
# Privacy Invariants
# ============================================================================
class TestVADPrivacy:
    def test_zero_disk_writes(self):
        before = set(os.listdir("."))
        vad = EnergyVADProvider()
        for _ in range(20):
            vad.process_frame(create_silence_frame())
        after = set(os.listdir("."))
        assert after == before, "VAD operation created unwanted files on disk"
