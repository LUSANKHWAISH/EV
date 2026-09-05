"""
Two-Stage Wake-Word Phrase Verification Engine for E.V. (Task 014F-12A).

Implements Stage-2 local phrase verification to eliminate confusable hard-negative false triggers
(e.g., 'Hey Evan', 'Hey Evelyn', 'Hey Everyone', 'Hey Evidence', 'Hey Stevie', 'Every')
while preserving true human positive 'Hey EV' recall.

Architectural Guarantees:
  1. Zero Execution Authority: Pure decision signal only (verified: bool). Never executes commands,
     invokes orchestrators, grants permissions, or activates GOD MODE.
  2. Zero Cloud Audio: 100% local, offline inference on CPU.
  3. Memory-only audio transformation (zero disk writes, zero temporary WAV files).
  4. Immutable WakeVerificationResult contract.
"""
from __future__ import annotations

import logging
import math
import os
import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from core.voice_capture import AudioFrame
from core.asr import frames_to_pcm, calculate_utterance_duration

logger = logging.getLogger("ev.voice.wake_verifier")


# ============================================================================
# Stage-2 Decision Contract
# ============================================================================
@dataclass(frozen=True)
class WakeVerificationResult:
    """
    Immutable representation of a Stage-2 wake-word verification decision.

    Fields:
      verified: Boolean decision (True = confirmed 'Hey EV', False = rejected).
      confidence: Aggregate verification confidence in range [0.0, 1.0].
      reason: Deterministic diagnostic reason code (e.g. 'EXACT_MATCH', 'REJECTED_KEYWORD_EVAN').
      raw_transcript: The raw normalized text decoded by the verifier (if ASR-based).
      latency_ms: Execution duration of Stage 2 in milliseconds.
      provider: Identifier of the verifier provider.
      timestamp: Monotonic timestamp when verification completed.
    """
    verified: bool
    confidence: float
    reason: str
    raw_transcript: str
    latency_ms: float
    provider: str
    timestamp: float

    def __post_init__(self) -> None:
        if not isinstance(self.verified, bool):
            raise TypeError(f"verified must be bool, got {type(self.verified).__name__}")
        if not isinstance(self.confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(self.confidence).__name__}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.reason, str):
            raise TypeError(f"reason must be str, got {type(self.reason).__name__}")
        if not isinstance(self.raw_transcript, str):
            raise TypeError(f"raw_transcript must be str, got {type(self.raw_transcript).__name__}")
        if not isinstance(self.latency_ms, (int, float)):
            raise TypeError(f"latency_ms must be numeric, got {type(self.latency_ms).__name__}")
        if not isinstance(self.provider, str):
            raise TypeError(f"provider must be str, got {type(self.provider).__name__}")
        if not isinstance(self.timestamp, (int, float)):
            raise TypeError(f"timestamp must be numeric, got {type(self.timestamp).__name__}")

    def __repr__(self) -> str:
        status = "VERIFIED" if self.verified else "REJECTED"
        return (
            f"WakeVerificationResult({status}, conf={self.confidence:.2f}, "
            f"reason='{self.reason}', text='{self.raw_transcript}', lat={self.latency_ms:.1f}ms)"
        )


# ============================================================================
# Abstract Base Verifier Interface
# ============================================================================
class EVWakeVerifier(ABC):
    """
    Abstract interface for Stage-2 local phrase verifiers.
    Zero execution authority.
    """

    @abstractmethod
    def verify_phrase(
        self,
        audio_data: Union[Sequence[AudioFrame], np.ndarray, bytes],
        target_phrase: str = "Hey EV",
    ) -> WakeVerificationResult:
        """
        Verify if the captured audio buffer represents the genuine target wake phrase.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the verifier backend is ready."""

    @abstractmethod
    def reset(self) -> None:
        """Clear any internal cache or session state."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Identifier string for the verifier provider."""


# ============================================================================
# Mock Verifier (Testing & CI Foundation)
# ============================================================================
class MockWakeVerifier(EVWakeVerifier):
    """Deterministic in-memory verifier for automated unit testing."""

    def __init__(
        self,
        default_verified: bool = True,
        default_confidence: float = 0.95,
        default_reason: str = "MOCK_VERIFIED",
        scripted_results: Optional[Sequence[WakeVerificationResult]] = None,
    ) -> None:
        self.default_verified = default_verified
        self.default_confidence = default_confidence
        self.default_reason = default_reason
        self._scripted_results = list(scripted_results) if scripted_results is not None else []
        self._script_index = 0
        self._verification_count = 0
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "mock_verifier"

    def is_available(self) -> bool:
        return True

    def verify_phrase(
        self,
        audio_data: Union[Sequence[AudioFrame], np.ndarray, bytes],
        target_phrase: str = "Hey EV",
    ) -> WakeVerificationResult:
        t0 = time.monotonic()
        with self._lock:
            self._verification_count += 1
            if self._script_index < len(self._scripted_results):
                res = self._scripted_results[self._script_index]
                self._script_index += 1
                return res

            return WakeVerificationResult(
                verified=self.default_verified,
                confidence=self.default_confidence,
                reason=self.default_reason,
                raw_transcript=target_phrase if self.default_verified else "other",
                latency_ms=(time.monotonic() - t0) * 1000,
                provider=self.provider_name,
                timestamp=time.monotonic(),
            )

    def reset(self) -> None:
        with self._lock:
            self._script_index = 0
            self._verification_count = 0


# ============================================================================
# Production Faster-Whisper Constrained Phrase Verifier
# ============================================================================
class FasterWhisperWakeVerifier(EVWakeVerifier):
    """
    Stage-2 Wake-Word Verifier utilizing local INT8 quantized faster-whisper.
    Applies strict phonetic and vocabulary constraints to distinguish 'Hey EV' from
    confusable prefix words ('Hey Evan', 'Hey Evelyn', 'Hey Everyone', 'Every', etc.).
    """

    DEFAULT_REJECTED_KEYWORDS: Sequence[str] = (
        "evan", "evelyn", "everyone", "everybody", "evidence", "event", "events",
        "everest", "everett", "everywhere", "eventually", "everyday", "every",
        "stevie", "steve", "steven", "eddie", "heavy", "duty", "rain", "browser",
        "lights", "diagnostics", "status", "cancel", "open", "turn", "search",
        "close", "what", "time", "show", "active", "tasks", "window", "speakers"
    )

    def __init__(
        self,
        model_size_or_path: str = "tiny.en",
        device: str = "cpu",
        compute_type: str = "int8",
        cpu_threads: int = 4,
        download_root: str = r"D:\EV\models\asr",
        confidence_threshold: float = 0.50,
        rejected_keywords: Optional[Sequence[str]] = None,
    ) -> None:
        self.model_size_or_path = model_size_or_path
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.download_root = download_root
        self.confidence_threshold = confidence_threshold
        self.rejected_keywords = tuple(
            k.lower().strip() for k in (rejected_keywords or self.DEFAULT_REJECTED_KEYWORDS)
        )

        self._model: Optional[Any] = None
        self._lock = threading.Lock()
        self._verification_count = 0

    @property
    def provider_name(self) -> str:
        return f"faster_whisper_{self.model_size_or_path}"

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401
            import numpy  # noqa: F401
            return True
        except ImportError:
            return False

    def load_model(self) -> Any:
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as err:
                raise RuntimeError("faster-whisper is not installed.") from err

            logger.info(
                "Initializing FasterWhisperWakeVerifier '%s' (device=%s, compute_type=%s, threads=%d)",
                self.model_size_or_path, self.device, self.compute_type, self.cpu_threads
            )
            os.makedirs(self.download_root, exist_ok=True)
            self._model = WhisperModel(
                model_size_or_path=self.model_size_or_path,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
                download_root=self.download_root,
            )
            return self._model

    def _normalize(self, text: str) -> str:
        t = text.lower().strip()
        t = re.sub(r"[^\w\s]", " ", t)
        return " ".join(t.split())

    def _evaluate_transcript(self, raw_text: str) -> Tuple[bool, float, str]:
        """
        Evaluate if raw transcript matches 'Hey EV' and does not contain confusable competitors.
        """
        norm = self._normalize(raw_text)
        if not norm:
            return False, 0.0, "EMPTY_TRANSCRIPT"

        words = norm.split()

        # 1. Hard Rejection of Explicit Competitor Keywords
        for rk in self.rejected_keywords:
            for w in words:
                if w == rk or w.startswith(rk):
                    return False, 0.10, f"REJECTED_KEYWORD_{rk.upper()}"

        # 2. Rejection of Incomplete Wake Utterances
        if norm in ("hey", "a", "the", "he", "hi", "ay", "oh"):
            return False, 0.20, "INCOMPLETE_WAKE_PREFIX"

        # 3. Exact Matching Patterns
        if norm in ("hey ev", "hey e v", "hey v", "hey ee vee"):
            return True, 0.98, "EXACT_PHRASE_MATCH"

        # 4. Normalized Word Combinations
        # 2 words: [hey/ay/a] + [ev/v/e]
        if len(words) == 2:
            if words[0] in ("hey", "ay", "a", "hi") and words[1] in ("ev", "v", "ee"):
                return True, 0.95, "NORMALIZED_2WORD_MATCH"
            if words[0] in ("hey", "ay", "a") and words[1] in ("e", "easy"):
                return True, 0.80, "ACOUSTIC_ACCENT_MATCH"

        # 3 words: [hey/ay/a] + [e] + [v/vee]
        if len(words) == 3:
            if words[0] in ("hey", "ay", "a") and words[1] == "e" and words[2] in ("v", "vee", "b"):
                return True, 0.92, "NORMALIZED_3WORD_SPACED_MATCH"

        # Reject everything else
        return False, 0.30, f"UNMATCHED_TRANSCRIPT_{norm}"

    def verify_phrase(
        self,
        audio_data: Union[Sequence[AudioFrame], np.ndarray, bytes],
        target_phrase: str = "Hey EV",
    ) -> WakeVerificationResult:
        """
        Execute Stage-2 transcription and strict phrase validation.
        """
        t_start = time.monotonic()
        model = self.load_model()

        # Convert input to 1D float32 array normalized [-1.0, 1.0] @ 16kHz
        if isinstance(audio_data, (list, tuple)) and audio_data and isinstance(audio_data[0], AudioFrame):
            pcm_bytes = frames_to_pcm(audio_data)
            audio_arr = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        elif isinstance(audio_data, bytes):
            audio_arr = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        elif isinstance(audio_data, np.ndarray):
            if audio_data.dtype == np.int16:
                audio_arr = audio_data.astype(np.float32) / 32768.0
            else:
                audio_arr = audio_data.astype(np.float32)
        else:
            return WakeVerificationResult(
                verified=False,
                confidence=0.0,
                reason="INVALID_AUDIO_INPUT_FORMAT",
                raw_transcript="",
                latency_ms=0.0,
                provider=self.provider_name,
                timestamp=time.monotonic(),
            )

        if len(audio_arr) < 1600:  # < 100ms
            return WakeVerificationResult(
                verified=False,
                confidence=0.0,
                reason="AUDIO_TOO_SHORT",
                raw_transcript="",
                latency_ms=(time.monotonic() - t_start) * 1000,
                provider=self.provider_name,
                timestamp=time.monotonic(),
            )

        try:
            # Deterministic, anti-hallucination inference configuration
            segments, info = model.transcribe(
                audio_arr,
                language="en",
                beam_size=1,
                temperature=0.0,
                condition_on_previous_text=False,
                without_timestamps=True,
                initial_prompt="Hey EV. Hey E.V.",
            )
            raw_transcript = " ".join(s.text.strip() for s in segments if s.text).strip()
        except Exception as exc:
            logger.warning("FasterWhisperWakeVerifier transcription failed: %s", exc)
            return WakeVerificationResult(
                verified=False,
                confidence=0.0,
                reason=f"TRANSCRIPTION_ERROR_{type(exc).__name__}",
                raw_transcript="",
                latency_ms=(time.monotonic() - t_start) * 1000,
                provider=self.provider_name,
                timestamp=time.monotonic(),
            )

        with self._lock:
            self._verification_count += 1

        verified, confidence, reason = self._evaluate_transcript(raw_transcript)
        latency = (time.monotonic() - t_start) * 1000

        return WakeVerificationResult(
            verified=verified,
            confidence=confidence,
            reason=reason,
            raw_transcript=raw_transcript,
            latency_ms=latency,
            provider=self.provider_name,
            timestamp=time.monotonic(),
        )

    def reset(self) -> None:
        with self._lock:
            self._verification_count = 0


# ============================================================================
# Two-Stage Wake-Word Orchestrator
# ============================================================================
class TwoStageWakeWordPipeline:
    """
    Two-Stage Wake-Word Pipeline:
      Stage 1: Lightweight, always-on openWakeWord streaming detector.
      Stage 2: On-demand local phrase verifier (runs ONLY on Stage 1 candidate triggers).
    """

    def __init__(
        self,
        stage1_provider: Any,
        stage2_verifier: EVWakeVerifier,
        buffer_seconds: float = 2.0,
    ) -> None:
        self.stage1_provider = stage1_provider
        self.stage2_verifier = stage2_verifier
        self.buffer_seconds = buffer_seconds
        self.buffer_samples = int(16000 * buffer_seconds)

        self._audio_buffer: List[AudioFrame] = []
        self._lock = threading.Lock()
        self._stage1_triggers = 0
        self._stage2_verifications = 0
        self._stage2_accepts = 0
        self._stage2_rejects = 0

    def process_frame(self, frame: AudioFrame) -> Tuple[Optional[Any], Optional[WakeVerificationResult]]:
        """
        Ingest streaming frame:
          1. Buffer frame in rolling audio history.
          2. Process frame with Stage-1 detector.
          3. If Stage-1 triggers candidate detection, invoke Stage-2 phrase verifier on buffer.
        """
        with self._lock:
            self._audio_buffer.append(frame)
            # Trim buffer to max window
            total_dur = sum(f.duration_seconds for f in self._audio_buffer)
            while total_dur > self.buffer_seconds and len(self._audio_buffer) > 1:
                removed = self._audio_buffer.pop(0)
                total_dur -= removed.duration_seconds

        # Stage 1 Detection
        stage1_res = self.stage1_provider.process_frame(frame)

        if stage1_res is None or not getattr(stage1_res, "detected", False):
            return stage1_res, None

        # Stage 1 Triggered! Run Stage 2 Verifier
        with self._lock:
            self._stage1_triggers += 1
            current_buffer = list(self._audio_buffer)

        stage2_res = self.stage2_verifier.verify_phrase(current_buffer)

        with self._lock:
            self._stage2_verifications += 1
            if stage2_res.verified:
                self._stage2_accepts += 1
            else:
                self._stage2_rejects += 1

        return stage1_res, stage2_res

    def reset(self) -> None:
        with self._lock:
            self._audio_buffer.clear()
            self._stage1_triggers = 0
            self._stage2_verifications = 0
            self._stage2_accepts = 0
            self._stage2_rejects = 0
        self.stage1_provider.reset()
        self.stage2_verifier.reset()
