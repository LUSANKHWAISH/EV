"""
Unit tests for FasterWhisperASRProvider (Task 014D-B).

Verifies:
  - FasterWhisperASRProvider inherits from EVASRProvider.
  - Configuration, path resolution, and environment overrides.
  - Thread-safe lazy model initialization without loading on import or construction.
  - PCM to float32 in-memory conversion without disk persistence.
  - Mocked segment transcription, confidence scoring, and empty audio safety.
  - Execution isolation: zero coupling to orchestrator, task queue, agent, TTS, or risk.
  - CI safety: 100% mocked; zero real Whisper model downloads during test execution.
"""
from __future__ import annotations

import inspect
import os
import threading
from unittest.mock import MagicMock, patch

import pytest

import core.asr_faster_whisper as fwhisper_module
from core.asr import ASRResult, EVASRProvider
from core.asr_faster_whisper import DEFAULT_MODEL_DIR, FasterWhisperASRProvider
from core.voice_capture import AudioFrame, create_silence_frame


class DummySegment:
    """Mock segment mirroring faster_whisper.transcribe.Segment."""
    def __init__(self, text: str, avg_logprob: float = -0.1) -> None:
        self.text = text
        self.avg_logprob = avg_logprob


class DummyInfo:
    """Mock info mirroring faster_whisper.transcribe.TranscriptionInfo."""
    def __init__(self, language: str = "en") -> None:
        self.language = language


# ============================================================================
# 1. Provider Configuration & Contract Tests
# ============================================================================
class TestFasterWhisperProviderContract:
    def test_inherits_ev_asr_provider(self):
        provider = FasterWhisperASRProvider()
        assert isinstance(provider, EVASRProvider)
        assert provider.provider_name == "faster_whisper"

    def test_default_configuration(self):
        provider = FasterWhisperASRProvider()
        assert provider.model_size_or_path == "base.en"
        assert provider.device == "cpu"
        assert provider.compute_type == "int8"
        assert provider.cpu_threads == 4
        assert provider.download_root == DEFAULT_MODEL_DIR
        assert provider._model is None  # Lazy loading verified

    def test_custom_configuration(self):
        provider = FasterWhisperASRProvider(
            model_size_or_path="tiny.en",
            device="cpu",
            compute_type="int8",
            cpu_threads=8,
            download_root=r"D:\custom\models",
            beam_size=1,
            temperature=0.2,
        )
        assert provider.model_size_or_path == "tiny.en"
        assert provider.device == "cpu"
        assert provider.cpu_threads == 8
        assert provider.download_root == r"D:\custom\models"
        assert provider.beam_size == 1
        assert provider.temperature == 0.2

    def test_environment_override_model_dir(self, monkeypatch):
        monkeypatch.setenv("EV_ASR_MODEL_DIR", r"D:\env_models\asr")
        provider = FasterWhisperASRProvider()
        assert provider.download_root == r"D:\env_models\asr"

    def test_is_available_returns_bool(self):
        provider = FasterWhisperASRProvider()
        # In this environment faster-whisper is installed, so is_available should be True
        assert isinstance(provider.is_available(), bool)


# ============================================================================
# 2. Lazy Model Initialization & Thread-Safety
# ============================================================================
class TestModelLoading:
    def test_lazy_initialization_not_loaded_on_init(self):
        provider = FasterWhisperASRProvider()
        assert provider._model is None

    @patch("faster_whisper.WhisperModel")
    def test_load_model_creates_instance_with_exact_config(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        provider = FasterWhisperASRProvider(
            model_size_or_path="base.en",
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            download_root=r"D:\EV\models\asr",
        )

        model = provider.load_model()
        assert model is mock_instance
        assert provider._model is mock_instance

        mock_whisper_cls.assert_called_once_with(
            model_size_or_path="base.en",
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            num_workers=1,
            download_root=r"D:\EV\models\asr",
        )

        # Subsequent call reuses cached instance
        model2 = provider.load_model()
        assert model2 is mock_instance
        assert mock_whisper_cls.call_count == 1

    @patch("faster_whisper.WhisperModel")
    def test_thread_safe_concurrent_loading(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        provider = FasterWhisperASRProvider()
        results = []

        def worker():
            m = provider.load_model()
            results.append(m)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5
        assert all(m is mock_instance for m in results)
        assert mock_whisper_cls.call_count == 1


# ============================================================================
# 3. Audio Transcription Tests (Mocked Faster-Whisper Model)
# ============================================================================
class TestTranscription:
    def test_empty_frame_sequence_returns_safe_empty_result(self):
        provider = FasterWhisperASRProvider()
        res = provider.transcribe([])

        assert isinstance(res, ASRResult)
        assert res.text == ""
        assert res.confidence == 0.0
        assert res.duration_seconds == 0.0
        assert res.provider == "faster_whisper"
        assert provider._model is None  # Never loaded model for empty audio

    def test_invalid_input_rejected(self):
        provider = FasterWhisperASRProvider()
        with pytest.raises(TypeError, match="Expected sequence of AudioFrame"):
            provider.transcribe("invalid_string")  # type: ignore[arg-type]

        with pytest.raises(TypeError, match="is not an AudioFrame"):
            provider.transcribe([create_silence_frame(), "invalid_item"])  # type: ignore[list-item]

    @patch("faster_whisper.WhisperModel")
    def test_successful_transcription(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        segments = [
            DummySegment("open", avg_logprob=-0.05),
            DummySegment("VS Code", avg_logprob=-0.08),
        ]
        info = DummyInfo(language="en")
        mock_instance.transcribe.return_value = (iter(segments), info)

        provider = FasterWhisperASRProvider()
        frames = [create_silence_frame() for _ in range(10)]  # 300 ms

        res = provider.transcribe(frames)

        assert res.text == "open VS Code"
        assert res.language == "en"
        assert 0.90 <= res.confidence <= 1.0
        assert res.duration_seconds == pytest.approx(0.300, rel=1e-3)
        assert res.provider == "faster_whisper"
        assert provider.transcription_count == 1

    @patch("faster_whisper.WhisperModel")
    def test_no_speech_detected_in_audio(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance

        # Model returns empty segments generator
        mock_instance.transcribe.return_value = (iter([]), DummyInfo(language="en"))

        provider = FasterWhisperASRProvider()
        frames = [create_silence_frame() for _ in range(5)]

        res = provider.transcribe(frames)

        assert res.text == ""
        assert res.confidence == 0.0
        assert res.duration_seconds == pytest.approx(0.150, rel=1e-3)

    @patch("faster_whisper.WhisperModel")
    def test_transcription_exception_fails_safely(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance
        mock_instance.transcribe.side_effect = RuntimeError("Inference kernel crashed")

        provider = FasterWhisperASRProvider()
        frames = [create_silence_frame()]

        res = provider.transcribe(frames)
        assert res.text == ""
        assert res.confidence == 0.0
        assert res.provider == "faster_whisper"

    @patch("faster_whisper.WhisperModel")
    def test_reset(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance
        mock_instance.transcribe.return_value = (iter([DummySegment("test")]), DummyInfo())

        provider = FasterWhisperASRProvider()
        provider.transcribe([create_silence_frame()])
        assert provider.transcription_count == 1

        provider.reset()
        assert provider.transcription_count == 0


# ============================================================================
# 4. Privacy & Safety Tests
# ============================================================================
class TestPrivacyAndSafety:
    @patch("faster_whisper.WhisperModel")
    def test_zero_disk_writes_during_transcription(self, mock_whisper_cls):
        mock_instance = MagicMock()
        mock_whisper_cls.return_value = mock_instance
        mock_instance.transcribe.return_value = (iter([DummySegment("clean")]), DummyInfo())

        provider = FasterWhisperASRProvider()
        before_files = set(os.listdir("."))

        frames = [create_silence_frame() for _ in range(5)]
        provider.transcribe(frames)

        after_files = set(os.listdir("."))
        assert after_files == before_files, "Temporary files were leaked during transcription"


# ============================================================================
# 5. Execution Isolation Tests
# ============================================================================
class TestExecutionIsolation:
    def test_core_asr_faster_whisper_has_no_execution_coupling(self):
        source = inspect.getsource(fwhisper_module)
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
            assert symbol not in source, (
                f"Forbidden execution coupling '{symbol}' found in core/asr_faster_whisper.py"
            )
