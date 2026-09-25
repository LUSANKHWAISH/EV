"""
Automated Speech Recognition (ASR) Foundation for E.V. (Task 014D).

Establishes:
  - ASRResult: immutable representation of speech-to-text transcription output.
  - EVASRProvider: engine-agnostic abstract base interface for ASR providers.
  - MockASRProvider: deterministic in-memory ASR provider for testing and CI.
  - Audio utilities: frames_to_pcm, calculate_utterance_duration.

Invariants:
  1. Pure Python standard library only. Zero third-party dependencies (no numpy, torch, ctranslate2).
  2. Zero execution authority. Ingress speech-to-text only; never executes commands or calls orchestrator.
  3. No disk writes, no network calls, no raw audio storage in results or log representations.
  4. Operates strictly over the canonical AudioFrame contract from Task 014B.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from core.voice_capture import AudioFrame

logger = logging.getLogger("ev.asr")


# ============================================================================
# ASRResult
# ============================================================================
@dataclass(frozen=True)
class ASRResult:
    """
    Immutable representation of speech-to-text output.

    Fields:
      text: Cleaned transcript text (untrusted input).
      confidence: Aggregate confidence score in range [0.0, 1.0].
      language: Language code used or detected (e.g. "en").
      duration_seconds: Total duration of processed audio in seconds (>= 0.0).
      timestamp: Monotonic timestamp when transcription completed.
      provider: Identifier of the generating provider (e.g. 'mock_asr').
    """
    text: str
    confidence: float
    language: str
    duration_seconds: float
    timestamp: float
    provider: str

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise TypeError(f"text must be str, got {type(self.text).__name__}")
        if not isinstance(self.confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(self.confidence).__name__}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.language, str):
            raise TypeError(f"language must be str, got {type(self.language).__name__}")
        if not isinstance(self.duration_seconds, (int, float)):
            raise TypeError(f"duration_seconds must be numeric, got {type(self.duration_seconds).__name__}")
        if float(self.duration_seconds) < 0.0:
            raise ValueError(f"duration_seconds must be non-negative, got {self.duration_seconds}")
        if not isinstance(self.timestamp, (int, float)):
            raise TypeError(f"timestamp must be numeric, got {type(self.timestamp).__name__}")
        if not isinstance(self.provider, str):
            raise TypeError(f"provider must be str, got {type(self.provider).__name__}")

    def __repr__(self) -> str:
        # Privacy Invariant: NEVER log or expose raw audio bytes.
        return (
            f"ASRResult(text='{self.text}', conf={self.confidence:.2f}, "
            f"dur={self.duration_seconds:.2f}s, provider='{self.provider}')"
        )


# ============================================================================
# Audio Utilities
# ============================================================================
def frames_to_pcm(frames: Sequence[AudioFrame]) -> bytes:
    """
    Concatenate a sequence of canonical AudioFrames into contiguous linear PCM16 bytes.
    Preserves exact chronological sample order and payload data.
    Returns b"" for an empty sequence.

    Raises:
      TypeError: if frames is not a sequence or contains non-AudioFrame objects.
    """
    if isinstance(frames, (str, bytes, bytearray)) or not isinstance(frames, (list, tuple, Sequence)):
        raise TypeError(f"Expected sequence of AudioFrame, got {type(frames).__name__}")
    if not frames:
        return b""
    chunks: List[bytes] = []
    for idx, f in enumerate(frames):
        if not isinstance(f, AudioFrame):
            raise TypeError(f"Element at index {idx} is not an AudioFrame, got {type(f).__name__}")
        chunks.append(f.data)
    return b"".join(chunks)


def calculate_utterance_duration(frames: Sequence[AudioFrame]) -> float:
    """
    Calculate the total duration in seconds of a sequence of AudioFrames.
    Returns 0.0 for an empty sequence.

    Raises:
      TypeError: if frames is not a sequence or contains non-AudioFrame objects.
    """
    if isinstance(frames, (str, bytes, bytearray)) or not isinstance(frames, (list, tuple, Sequence)):
        raise TypeError(f"Expected sequence of AudioFrame, got {type(frames).__name__}")
    if not frames:
        return 0.0
    total_sec = 0.0
    for idx, f in enumerate(frames):
        if not isinstance(f, AudioFrame):
            raise TypeError(f"Element at index {idx} is not an AudioFrame, got {type(f).__name__}")
        total_sec += f.duration_seconds
    return total_sec


# ============================================================================
# EVASRProvider Abstraction
# ============================================================================
class EVASRProvider(ABC):
    """
    Abstract base interface for Automated Speech Recognition providers.
    Zero execution authority. Ingress speech-to-text only.
    """

    @abstractmethod
    def transcribe(
        self,
        frames: Sequence[AudioFrame],
        language: Optional[str] = "en",
    ) -> ASRResult:
        """
        Transcribe a discrete sequence of AudioFrames into text.

        Args:
          frames: Chronological sequence of canonical AudioFrames.
          language: Optional ISO language code (default "en").

        Returns:
          Immutable ASRResult.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying engine/model is ready for transcription."""

    @abstractmethod
    def reset(self) -> None:
        """Clear any internal cache, decoder session, or state."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier (e.g. 'mock_asr', 'faster_whisper')."""


# ============================================================================
# MockASRProvider (Testing / CI Foundation)
# ============================================================================
class MockASRProvider(EVASRProvider):
    """
    Deterministic in-memory ASR provider for automated unit testing and CI.
    Zero network, zero external model dependencies, zero hardware requirements.
    """

    def __init__(
        self,
        default_text: str = "",
        default_confidence: float = 0.95,
        default_language: str = "en",
        scripted_results: Optional[Sequence[Union[ASRResult, str]]] = None,
    ) -> None:
        self.default_text: str = default_text
        self.default_confidence: float = default_confidence
        self.default_language: str = default_language
        self._scripted_results: List[Union[ASRResult, str]] = (
            list(scripted_results) if scripted_results is not None else []
        )
        self._script_index: int = 0
        self._transcription_count: int = 0
        self._last_frames: List[AudioFrame] = []
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "mock_asr"

    def is_available(self) -> bool:
        return True

    def transcribe(
        self,
        frames: Sequence[AudioFrame],
        language: Optional[str] = "en",
    ) -> ASRResult:
        if isinstance(frames, (str, bytes, bytearray)) or not isinstance(frames, (list, tuple, Sequence)):
            raise TypeError(f"Expected sequence of AudioFrame, got {type(frames).__name__}")
        for idx, f in enumerate(frames):
            if not isinstance(f, AudioFrame):
                raise TypeError(f"Element at index {idx} is not an AudioFrame, got {type(f).__name__}")

        lang = language if language is not None else self.default_language
        duration = calculate_utterance_duration(frames)

        # Empty audio frames sequence returns empty result
        if not frames:
            return ASRResult(
                text="",
                confidence=0.0,
                language=lang,
                duration_seconds=0.0,
                timestamp=time.monotonic(),
                provider=self.provider_name,
            )

        with self._lock:
            self._transcription_count += 1
            self._last_frames = list(frames)

            # 1. Scripted result sequence if available
            if self._script_index < len(self._scripted_results):
                res = self._scripted_results[self._script_index]
                self._script_index += 1
                if isinstance(res, ASRResult):
                    return res
                return ASRResult(
                    text=res,
                    confidence=self.default_confidence,
                    language=lang,
                    duration_seconds=duration,
                    timestamp=time.monotonic(),
                    provider=self.provider_name,
                )

            # 2. Default transcript
            return ASRResult(
                text=self.default_text,
                confidence=self.default_confidence,
                language=lang,
                duration_seconds=duration,
                timestamp=time.monotonic(),
                provider=self.provider_name,
            )

    def reset(self) -> None:
        with self._lock:
            self._script_index = 0
            self._transcription_count = 0
            self._last_frames.clear()

    @property
    def transcription_count(self) -> int:
        with self._lock:
            return self._transcription_count

    def get_last_frames(self) -> List[AudioFrame]:
        with self._lock:
            return list(self._last_frames)
