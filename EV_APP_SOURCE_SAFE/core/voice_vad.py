"""
Voice Activity Detection (VAD) Foundation for E.V. (Task 014C).

Establishes:
  - VADResult: immutable representation of speech detection confidence and energy.
  - EVVADProvider: abstract base provider establishing the VAD interface.
  - EnergyVADProvider: pure standard-library RMS/energy detector with attack/release hysteresis.
  - MockVADProvider: deterministic in-memory provider for automated testing and CI.

Invariants:
  1. VAD is NOT an authoritative gate for wake-word detection.
  2. Pure Python standard library only. Zero third-party dependencies (no numpy, webrtcvad, silero).
  3. No disk writes, no network calls, no raw audio byte logging.
  4. Bounded memory and deterministic reset.
"""
from __future__ import annotations

import logging
import math
import struct
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence

from core.voice_capture import AudioFormatError, AudioFrame

logger = logging.getLogger("ev.voice_vad")


# ============================================================================
# VADResult
# ============================================================================
@dataclass(frozen=True)
class VADResult:
    """
    Immutable result representing voice activity classification for an audio frame.

    Fields:
      is_speech: boolean indicating if speech is active.
      confidence: estimated probability of speech presence [0.0, 1.0].
      energy: root-mean-square (RMS) energy level (>= 0.0).
      timestamp: monotonic timestamp corresponding to the evaluated frame.
    """
    is_speech: bool
    confidence: float
    energy: float
    timestamp: float

    def __post_init__(self) -> None:
        if not isinstance(self.is_speech, bool):
            raise TypeError(f"is_speech must be bool, got {type(self.is_speech).__name__}")
        if not isinstance(self.confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(self.confidence).__name__}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.energy, (int, float)):
            raise TypeError(f"energy must be numeric, got {type(self.energy).__name__}")
        if float(self.energy) < 0.0:
            raise ValueError(f"energy must be non-negative, got {self.energy}")
        if not isinstance(self.timestamp, (int, float)):
            raise TypeError(f"timestamp must be numeric, got {type(self.timestamp).__name__}")

    def __repr__(self) -> str:
        # Privacy Invariant: NEVER dump or log raw audio bytes.
        return (
            f"VADResult(speech={self.is_speech}, conf={self.confidence:.2f}, "
            f"energy={self.energy:.1f}, ts={self.timestamp:.3f})"
        )


# ============================================================================
# EVVADProvider Abstraction
# ============================================================================
class EVVADProvider(ABC):
    """
    Abstract interface for Voice Activity Detection providers.
    Establishes the contract for speech activity and boundary detection.
    """

    @abstractmethod
    def process_frame(self, frame: AudioFrame) -> VADResult:
        """Evaluate a single AudioFrame and return VAD classification."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal smoothing buffers, states, and hysteresis counters."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @property
    def is_available(self) -> bool:
        """Return True if this provider can execute on the current host."""
        return True


# ============================================================================
# EnergyVADProvider (Pure Standard Library RMS/Energy Detector)
# ============================================================================
class EnergyVADProvider(EVVADProvider):
    """
    Pure standard-library energy/RMS Voice Activity Detector.
    Serves as the foundation and fallback VAD without external ML packages.

    Calculates root-mean-square amplitude for signed 16-bit PCM frames.
    Applies configurable thresholding with attack/release hysteresis to prevent
    choppy speech boundary oscillations.
    """

    def __init__(
        self,
        threshold: float = 300.0,
        attack_frames: int = 1,
        release_frames: int = 3,
    ) -> None:
        if threshold < 0.0:
            raise ValueError(f"threshold must be non-negative, got {threshold}")
        if attack_frames < 1:
            raise ValueError(f"attack_frames must be >= 1, got {attack_frames}")
        if release_frames < 1:
            raise ValueError(f"release_frames must be >= 1, got {release_frames}")

        self.threshold: float = threshold
        self.attack_frames: int = attack_frames
        self.release_frames: int = release_frames

        self._is_speech: bool = False
        self._above_threshold_count: int = 0
        self._below_threshold_count: int = 0
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "energy_rms"

    @staticmethod
    def calculate_rms(frame: AudioFrame) -> float:
        """
        Compute root-mean-square (RMS) energy for 16-bit signed PCM audio.
        Returns energy in range [0.0, 32767.0].
        """
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")
        if frame.sample_width != 2:
            raise AudioFormatError(
                f"EnergyVADProvider requires 16-bit PCM (sample_width=2), got {frame.sample_width}"
            )

        data = frame.data
        num_samples = len(data) // 2
        if num_samples == 0:
            return 0.0

        # Unpack signed 16-bit little-endian samples
        samples = struct.unpack(f"<{num_samples}h", data)
        sum_sq = sum(s * s for s in samples)
        return math.sqrt(sum_sq / num_samples)

    def process_frame(self, frame: AudioFrame) -> VADResult:
        """
        Evaluate frame energy against threshold and hysteresis counters.
        Returns immutable VADResult.
        """
        rms = self.calculate_rms(frame)

        with self._lock:
            if rms >= self.threshold:
                self._above_threshold_count += 1
                self._below_threshold_count = 0
                if self._above_threshold_count >= self.attack_frames:
                    self._is_speech = True
            else:
                self._below_threshold_count += 1
                self._above_threshold_count = 0
                if self._below_threshold_count >= self.release_frames:
                    self._is_speech = False

            # Estimate continuous confidence based on ratio to threshold
            if self.threshold <= 0.0:
                confidence = 1.0 if rms > 0.0 else 0.0
            elif rms >= self.threshold:
                # Range 0.5 to 1.0 as energy increases past threshold
                ratio = (rms - self.threshold) / max(1.0, self.threshold)
                confidence = min(1.0, 0.5 + 0.5 * ratio)
            else:
                # Range 0.0 to 0.5 as energy approaches threshold
                ratio = rms / self.threshold
                confidence = max(0.0, 0.5 * ratio)

            return VADResult(
                is_speech=self._is_speech,
                confidence=confidence,
                energy=rms,
                timestamp=frame.timestamp,
            )

    def reset(self) -> None:
        """Reset hysteresis state counters."""
        with self._lock:
            self._is_speech = False
            self._above_threshold_count = 0
            self._below_threshold_count = 0


# ============================================================================
# MockVADProvider (Testing / CI Foundation)
# ============================================================================
class MockVADProvider(EVVADProvider):
    """
    Deterministic in-memory VAD provider for automated unit testing and CI.
    Supports scripted result sequences, fixed responses, or programmatic triggers.
    """

    def __init__(
        self,
        fixed_is_speech: Optional[bool] = None,
        fixed_confidence: float = 0.9,
        fixed_energy: float = 500.0,
        scripted_results: Optional[Sequence[VADResult]] = None,
    ) -> None:
        self.fixed_is_speech: Optional[bool] = fixed_is_speech
        self.fixed_confidence: float = fixed_confidence
        self.fixed_energy: float = fixed_energy
        self._scripted_results: List[VADResult] = list(scripted_results) if scripted_results else []
        self._script_index: int = 0
        self._processed_frames: List[AudioFrame] = []
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "mock_vad"

    def process_frame(self, frame: AudioFrame) -> VADResult:
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        with self._lock:
            self._processed_frames.append(frame)

            # Return scripted result if available
            if self._script_index < len(self._scripted_results):
                res = self._scripted_results[self._script_index]
                self._script_index += 1
                return res

            # Return fixed decision if configured
            is_speech = self.fixed_is_speech if self.fixed_is_speech is not None else False
            return VADResult(
                is_speech=is_speech,
                confidence=self.fixed_confidence,
                energy=self.fixed_energy,
                timestamp=frame.timestamp,
            )

    def reset(self) -> None:
        with self._lock:
            self._script_index = 0
            self._processed_frames.clear()

    @property
    def processed_count(self) -> int:
        with self._lock:
            return len(self._processed_frames)

    def get_processed_frames(self) -> List[AudioFrame]:
        with self._lock:
            return list(self._processed_frames)
