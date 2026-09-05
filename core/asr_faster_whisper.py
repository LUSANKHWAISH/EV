"""
Production faster-whisper Automated Speech Recognition (ASR) Provider for E.V. (Task 014D-B).

Implements the EVASRProvider contract using faster-whisper (CTranslate2 backend).
Optimized for local, offline, CPU-based INT8 quantized inference on the development host.

Invariants:
  1. Thread-safe lazy model initialization (zero model loading on module import).
  2. Memory-only audio transformation (zero disk writes, zero temporary WAV files).
  3. Strict conformance to the canonical AudioFrame contract from core.voice_capture.
  4. Returns immutable ASRResult from core.asr.
  5. Zero execution authority (never executes commands, calls orchestrator, or invokes tasks).
"""
from __future__ import annotations

import logging
import math
import os
import threading
import time
from typing import Any, List, Optional, Sequence

from core.asr import (
    ASRResult,
    EVASRProvider,
    calculate_utterance_duration,
    frames_to_pcm,
)
from core.voice_capture import AudioFrame

logger = logging.getLogger("ev.asr.faster_whisper")

DEFAULT_MODEL_DIR = r"D:\EV\models\asr"


class FasterWhisperASRProvider(EVASRProvider):
    """
    Production ASR provider utilizing faster-whisper with CTranslate2.
    Supports local CPU inference with INT8 quantization.
    """

    def __init__(
        self,
        model_size_or_path: str = "base.en",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: Optional[int] = 4,
        num_workers: int = 1,
        download_root: Optional[str] = None,
        beam_size: int = 1,
        temperature: float = 0.0,
        without_timestamps: bool = True,
        condition_on_previous_text: bool = False,
        initial_prompt: Optional[str] = "E.V. PowerShell CPU RAM",
        vad_filter: bool = False,
    ) -> None:
        self.model_size_or_path: str = model_size_or_path
        self.device: str = device
        self.compute_type: str = compute_type
        self.cpu_threads: Optional[int] = cpu_threads
        self.num_workers: int = num_workers
        self.download_root: str = (
            download_root
            or os.getenv("EV_ASR_MODEL_DIR")
            or DEFAULT_MODEL_DIR
        )
        self.beam_size: int = beam_size
        self.temperature: float = temperature
        self.without_timestamps: bool = without_timestamps
        self.condition_on_previous_text: bool = condition_on_previous_text
        self.initial_prompt: Optional[str] = initial_prompt
        self.vad_filter: bool = vad_filter

        self._model: Optional[Any] = None
        self._model_lock = threading.Lock()
        self._transcription_count: int = 0
        self._last_duration: float = 0.0

    @property
    def provider_name(self) -> str:
        return "faster_whisper"

    def is_available(self) -> bool:
        """Return True if faster_whisper and numpy are installed and importable."""
        try:
            import faster_whisper  # noqa: F401
            import numpy  # noqa: F401
            return True
        except ImportError:
            return False

    def load_model(self) -> Any:
        """
        Thread-safe lazy initialization of the WhisperModel.
        Loads the model on demand; reuses the existing instance once loaded.
        """
        if self._model is not None:
            return self._model

        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as err:
                raise RuntimeError(
                    "faster-whisper is not installed. Install it via `pip install faster-whisper`."
                ) from err

            logger.info(
                "Loading faster-whisper model '%s' (device=%s, compute_type=%s, threads=%s, dir=%s)",
                self.model_size_or_path,
                self.device,
                self.compute_type,
                self.cpu_threads,
                self.download_root,
            )

            # Ensure model download directory exists if specified
            if self.download_root:
                os.makedirs(self.download_root, exist_ok=True)

            model = WhisperModel(
                model_size_or_path=self.model_size_or_path,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads or 4,
                num_workers=self.num_workers,
                download_root=self.download_root,
            )
            self._model = model
            return self._model

    def transcribe(
        self,
        frames: Sequence[AudioFrame],
        language: Optional[str] = "en",
    ) -> ASRResult:
        """
        Transcribe a discrete sequence of canonical AudioFrames using faster-whisper.

        Args:
          frames: Chronological sequence of canonical AudioFrames.
          language: Language code (default 'en').

        Returns:
          Immutable ASRResult. Returns empty result if frames is empty or no speech detected.
        """
        if isinstance(frames, (str, bytes, bytearray)) or not isinstance(frames, (list, tuple, Sequence)):
            raise TypeError(f"Expected sequence of AudioFrame, got {type(frames).__name__}")
        for idx, f in enumerate(frames):
            if not isinstance(f, AudioFrame):
                raise TypeError(f"Element at index {idx} is not an AudioFrame, got {type(f).__name__}")

        lang = language or "en"
        duration = calculate_utterance_duration(frames)

        # Empty audio sequence returns safe empty result
        if not frames:
            return ASRResult(
                text="",
                confidence=0.0,
                language=lang,
                duration_seconds=0.0,
                timestamp=time.monotonic(),
                provider=self.provider_name,
            )

        try:
            import numpy as np
        except ImportError as err:
            raise RuntimeError("numpy is required for faster-whisper audio decoding.") from err

        model = self.load_model()

        # Concatenate PCM16 bytes and convert to in-memory normalized float32 numpy array
        pcm_bytes = frames_to_pcm(frames)
        audio_array = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        try:
            transcribe_kwargs: dict[str, Any] = {
                "language": lang,
                "beam_size": self.beam_size,
                "temperature": self.temperature,
                "without_timestamps": self.without_timestamps,
                "condition_on_previous_text": self.condition_on_previous_text,
                "vad_filter": self.vad_filter,
            }
            if self.initial_prompt:
                transcribe_kwargs["initial_prompt"] = self.initial_prompt

            segments, info = model.transcribe(audio_array, **transcribe_kwargs)
            segments_list = list(segments)
        except Exception as exc:
            logger.warning("faster-whisper transcription error: %s", exc)
            return ASRResult(
                text="",
                confidence=0.0,
                language=lang,
                duration_seconds=duration,
                timestamp=time.monotonic(),
                provider=self.provider_name,
            )

        with self._model_lock:
            self._transcription_count += 1
            self._last_duration = duration

        if not segments_list:
            return ASRResult(
                text="",
                confidence=0.0,
                language=getattr(info, "language", lang) or lang,
                duration_seconds=duration,
                timestamp=time.monotonic(),
                provider=self.provider_name,
            )

        # Reconstruct full transcript text from segments
        text = " ".join(s.text.strip() for s in segments_list if s.text and s.text.strip()).strip()

        # Compute aggregate confidence score from avg_logprob of segments
        conf_scores = [
            max(0.0, min(1.0, math.exp(s.avg_logprob)))
            for s in segments_list
            if hasattr(s, "avg_logprob") and not math.isnan(s.avg_logprob)
        ]
        confidence = sum(conf_scores) / len(conf_scores) if conf_scores else 0.90

        resolved_lang = getattr(info, "language", lang) or lang

        return ASRResult(
            text=text,
            confidence=confidence,
            language=resolved_lang,
            duration_seconds=duration,
            timestamp=time.monotonic(),
            provider=self.provider_name,
        )

    def reset(self) -> None:
        """Clear transcription counts and temporary session metrics."""
        with self._model_lock:
            self._transcription_count = 0
            self._last_duration = 0.0

    @property
    def transcription_count(self) -> int:
        with self._model_lock:
            return self._transcription_count
