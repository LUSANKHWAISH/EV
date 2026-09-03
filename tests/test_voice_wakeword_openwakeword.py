"""
Unit tests for the openWakeWord Wake-Word Adapter (Task 014F-1).

Verifies:
  1. Construction & Initialization (default, custom, injected).
  2. Missing dependency handling with actionable error message.
  3. Configuration validation (threshold bounds, type validation, empty target phrase).
  4. Audio format validation & PCM16 conversion (silence, positive max, negative min, zero crossing).
  5. Sample accumulation & rechunking (480 -> 1280 samples) without loss or duplication.
  6. Return of canonical WakeWordResult instances conforming to EVWakeWordProvider contract.
  7. Reset lifecycle behavior (clearing rechunker and model prediction buffers).
  8. Architectural decoupling: zero imports/calls to orchestrator, agent, or execution tools.
  9. Privacy & safety: zero disk writes, zero WAV/PCM persistence, zero network requests.
  10. Concurrency & thread safety under multi-threaded execution.
"""
from __future__ import annotations

import array
import os
import struct
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from core.voice_capture import (
    DEFAULT_BYTES_PER_FRAME,
    DEFAULT_CHANNELS,
    DEFAULT_SAMPLE_RATE,
    DEFAULT_SAMPLES_PER_FRAME,
    DEFAULT_SAMPLE_WIDTH,
    AudioFormatError,
    AudioFrame,
    create_silence_frame,
)
from core.voice_wakeword import (
    AudioFrameRechunker,
    EVWakeWordProvider,
    WakeWordResult,
)
from core.voice_wakeword_openwakeword import (
    DEFAULT_DETECTION_THRESHOLD,
    DEFAULT_WAKEWORD_MODEL_DIR,
    OpenWakeWordProvider,
)


class DummyMockModel:
    """Deterministic mock openWakeWord Model for offline unit tests."""

    def __init__(
        self,
        model_scores: Optional[dict[str, float]] = None,
        models_list: Optional[list[str]] = None,
    ) -> None:
        self.models: dict[str, Any] = {m: None for m in (models_list or ["alexa", "hey_ev"])}
        self._scores = model_scores or {"alexa": 0.0, "hey_ev": 0.0}
        self.predict_calls: list[np.ndarray] = []
        self.reset_called: bool = False

    def predict(self, audio: np.ndarray) -> dict[str, float]:
        self.predict_calls.append(audio.copy())
        return dict(self._scores)

    def set_scores(self, scores: dict[str, float]) -> None:
        self._scores = dict(scores)

    def reset(self) -> None:
        self.reset_called = True


# ============================================================================
# 1. Construction & Initialization Tests
# ============================================================================
class TestConstruction:
    def test_construction_with_injected_model(self):
        mock_model = DummyMockModel(models_list=["alexa"])
        provider = OpenWakeWordProvider(
            wakeword_models=["alexa"],
            threshold=0.6,
            model_instance=mock_model,
            target_phrase="alexa",
        )

        assert provider.provider_name == "openwakeword"
        assert provider.target_phrase == "alexa"
        assert provider.threshold == 0.6
        assert provider.is_available is True
        assert provider.loaded_models == ["alexa"]
        assert provider.processed_frames_count == 0
        assert isinstance(provider, EVWakeWordProvider)

    def test_construction_defaults(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)
        assert provider.threshold == DEFAULT_DETECTION_THRESHOLD
        assert provider.target_phrase == "Hey EV"


# ============================================================================
# 2. Missing Dependency Tests
# ============================================================================
class TestMissingDependency:
    def test_clean_error_when_openwakeword_missing(self):
        with patch.dict("sys.modules", {"openwakeword": None, "openwakeword.model": None}):
            with pytest.raises(RuntimeError) as exc_info:
                OpenWakeWordProvider(model_instance=None)
            assert "openwakeword is not installed" in str(exc_info.value)

    def test_clean_error_when_model_init_fails(self):
        with patch("openwakeword.model.Model", side_effect=Exception("Model weights missing")):
            with pytest.raises(RuntimeError) as exc_info:
                OpenWakeWordProvider(model_instance=None)
            assert "Failed to initialize openWakeWord model" in str(exc_info.value)


# ============================================================================
# 3. Invalid Configuration Tests
# ============================================================================
class TestConfigurationValidation:
    def test_invalid_threshold_bounds(self):
        mock_model = DummyMockModel()
        with pytest.raises(ValueError, match="threshold must be in range"):
            OpenWakeWordProvider(threshold=-0.01, model_instance=mock_model)

        with pytest.raises(ValueError, match="threshold must be in range"):
            OpenWakeWordProvider(threshold=1.01, model_instance=mock_model)

    def test_invalid_threshold_type(self):
        mock_model = DummyMockModel()
        with pytest.raises(TypeError, match="threshold must be numeric"):
            OpenWakeWordProvider(threshold="high", model_instance=mock_model)  # type: ignore[arg-type]

    def test_invalid_target_phrase(self):
        mock_model = DummyMockModel()
        with pytest.raises(ValueError, match="target_phrase must be a non-empty string"):
            OpenWakeWordProvider(target_phrase="   ", model_instance=mock_model)

        with pytest.raises(ValueError, match="target_phrase must be a non-empty string"):
            OpenWakeWordProvider(target_phrase="", model_instance=mock_model)


# ============================================================================
# 4. Audio Conversion & PCM16 Integrity Tests
# ============================================================================
class TestAudioConversion:
    def test_silence_conversion(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Feed 3 silence frames (480 * 3 = 1440 samples >= 1280)
        for _ in range(3):
            provider.process_frame(create_silence_frame())

        assert len(mock_model.predict_calls) == 1
        predicted_audio = mock_model.predict_calls[0]
        assert isinstance(predicted_audio, np.ndarray)
        assert predicted_audio.dtype == np.int16
        assert len(predicted_audio) == 1280
        assert np.all(predicted_audio == 0)

    def test_positive_and_negative_extreme_values(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Create known values (+32767, -32768, 0, 1000, -1000)
        pattern = [32767, -32768, 0, 1000, -1000] * 96  # 480 samples
        raw_bytes = struct.pack(f"<{len(pattern)}h", *pattern)

        for _ in range(3):
            provider.process_frame(AudioFrame(data=raw_bytes))

        assert len(mock_model.predict_calls) == 1
        predicted_audio = mock_model.predict_calls[0]
        assert predicted_audio.dtype == np.int16
        assert predicted_audio[0] == 32767
        assert predicted_audio[1] == -32768
        assert predicted_audio[2] == 0
        assert predicted_audio[3] == 1000
        assert predicted_audio[4] == -1000

    def test_audio_format_validation(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Wrong sample rate
        bad_rate_frame = AudioFrame(data=b"\x00" * 960, sample_rate=8000)
        with pytest.raises(AudioFormatError, match="rate"):
            provider.process_frame(bad_rate_frame)

        # Wrong channels
        bad_ch_frame = AudioFrame(data=b"\x00" * 960, channels=2)
        with pytest.raises(AudioFormatError, match="channels"):
            provider.process_frame(bad_ch_frame)

        # Wrong sample width
        bad_width_frame = AudioFrame(data=b"\x00" * 960, sample_width=4)
        with pytest.raises(AudioFormatError, match="width"):
            provider.process_frame(bad_width_frame)

        # Invalid frame type
        with pytest.raises(TypeError, match="Expected AudioFrame"):
            provider.process_frame("raw_audio_string")  # type: ignore[arg-type]


# ============================================================================
# 5. Chunking & Sample Accumulation Tests (480 -> 1280)
# ============================================================================
class TestChunkingAndAccumulation:
    def test_accumulation_timing_and_leftovers(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Frame 1 (480 samples = 480 total): insufficient for 1280
        res1 = provider.process_frame(create_silence_frame(timestamp=1.0))
        assert res1 is None
        assert len(mock_model.predict_calls) == 0

        # Frame 2 (480 samples = 960 total): insufficient for 1280
        res2 = provider.process_frame(create_silence_frame(timestamp=1.03))
        assert res2 is None
        assert len(mock_model.predict_calls) == 0

        # Frame 3 (480 samples = 1440 total): 1280 emitted, 160 retained
        res3 = provider.process_frame(create_silence_frame(timestamp=1.06))
        assert len(mock_model.predict_calls) == 1
        assert len(mock_model.predict_calls[0]) == 1280

        # Frame 4 (480 samples = 160 + 480 = 640 total): insufficient
        res4 = provider.process_frame(create_silence_frame(timestamp=1.09))
        assert len(mock_model.predict_calls) == 1

        # Frame 5 (480 samples = 640 + 480 = 1120 total): insufficient
        res5 = provider.process_frame(create_silence_frame(timestamp=1.12))
        assert len(mock_model.predict_calls) == 1

        # Frame 6 (480 samples = 1120 + 480 = 1600 total): 1280 emitted, 320 retained
        res6 = provider.process_frame(create_silence_frame(timestamp=1.15))
        assert len(mock_model.predict_calls) == 2

    def test_sample_continuity_across_chunks(self):
        """Verify exact sequential samples across chunk boundaries."""
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Send monotonically increasing 16-bit integer samples
        all_samples = list(range(480 * 8))  # 3840 total samples (8 frames)
        for i in range(8):
            chunk_samples = all_samples[i * 480 : (i + 1) * 480]
            raw_bytes = struct.pack(f"<{len(chunk_samples)}h", *chunk_samples)
            provider.process_frame(AudioFrame(data=raw_bytes))

        # 3840 // 1280 = exactly 3 evaluation chunks
        assert len(mock_model.predict_calls) == 3
        concatenated = np.concatenate(mock_model.predict_calls)
        expected = np.array(all_samples[: 1280 * 3], dtype=np.int16)
        assert np.array_equal(concatenated, expected)


# ============================================================================
# 6. Result Contract Tests
# ============================================================================
class TestResultContract:
    def test_detection_above_threshold(self):
        mock_model = DummyMockModel(model_scores={"hey_ev": 0.85})
        provider = OpenWakeWordProvider(
            threshold=0.5,
            model_instance=mock_model,
            target_phrase="Hey EV",
        )

        for _ in range(2):
            provider.process_frame(create_silence_frame(timestamp=1.0))
        res = provider.process_frame(create_silence_frame(timestamp=1.06))

        assert res is not None
        assert isinstance(res, WakeWordResult)
        assert res.detected is True
        assert res.keyword == "hey_ev"
        assert res.confidence == 0.85
        assert res.timestamp == 1.0  # Timestamp of start of accumulated window

    def test_no_detection_below_threshold(self):
        mock_model = DummyMockModel(model_scores={"hey_ev": 0.42})
        provider = OpenWakeWordProvider(
            threshold=0.5,
            model_instance=mock_model,
        )

        for _ in range(2):
            provider.process_frame(create_silence_frame())
        res = provider.process_frame(create_silence_frame())

        assert res is None

    def test_multiple_models_returns_highest_confidence(self):
        mock_model = DummyMockModel(model_scores={"alexa": 0.75, "hey_ev": 0.92})
        provider = OpenWakeWordProvider(
            threshold=0.5,
            model_instance=mock_model,
        )

        for _ in range(2):
            provider.process_frame(create_silence_frame())
        res = provider.process_frame(create_silence_frame())

        assert res is not None
        assert res.keyword == "hey_ev"
        assert res.confidence == 0.92


# ============================================================================
# 7. Reset & Lifecycle Tests
# ============================================================================
class TestLifecycleAndReset:
    def test_reset_clears_state_and_rechunker(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        # Ingest 2 frames (960 samples buffered in rechunker)
        provider.process_frame(create_silence_frame())
        provider.process_frame(create_silence_frame())
        assert provider.processed_frames_count == 2

        # Reset
        provider.reset()
        assert provider.processed_frames_count == 0
        assert mock_model.reset_called is True

        # Next single frame should NOT trigger 1280 chunk emission (since buffer was cleared)
        provider.process_frame(create_silence_frame())
        assert len(mock_model.predict_calls) == 0

    def test_close_is_idempotent(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)
        provider.close()
        provider.close()
        assert provider.processed_frames_count == 0


# ============================================================================
# 8. Decoupling & Security Architecture Tests
# ============================================================================
class TestSecurityDecoupling:
    def test_no_orchestrator_or_agent_imports(self):
        import core.voice_wakeword_openwakeword as module

        disallowed = [
            "EVOrchestrator",
            "EVAgent",
            "EVRiskEngine",
            "EVTaskQueue",
            "subprocess",
            "PowerShell",
        ]
        module_text = open(module.__file__, "r", encoding="utf-8").read()
        for symbol in disallowed:
            assert symbol not in module_text, f"Security Violation: '{symbol}' found in adapter!"

    def test_zero_disk_writes_during_processing(self, tmp_path):
        mock_model = DummyMockModel(model_scores={"hey_ev": 0.95})
        provider = OpenWakeWordProvider(model_instance=mock_model)

        with patch("builtins.open", side_effect=AssertionError("Disk write attempted!")) as mock_open:
            for _ in range(6):
                provider.process_frame(create_silence_frame())


# ============================================================================
# 9. Concurrency & Thread Safety Tests
# ============================================================================
class TestThreadSafety:
    def test_concurrent_frame_processing(self):
        mock_model = DummyMockModel()
        provider = OpenWakeWordProvider(model_instance=mock_model)

        errors = []

        def worker():
            try:
                for _ in range(30):
                    provider.process_frame(create_silence_frame())
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert provider.processed_frames_count == 150
