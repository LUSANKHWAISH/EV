"""
Wake-Word Detection & Audio Frame Rechunker Foundation for E.V. (Task 014C).

Establishes:
  - WakeWordResult: immutable representation of wake phrase detection events.
  - EVWakeWordProvider: abstract base provider establishing the wake-word interface.
  - MockWakeWordProvider: deterministic in-memory provider for automated testing and CI.
  - AudioFrameRechunker: deterministic sliding-window adapter converting canonical 30 ms
    frames into detector-specific sample windows (e.g. 1280 samples / 80 ms) without sample loss.
  - EVBargeInStopDetector & MockBargeInStopDetector: lightweight abstraction for emergency
    STOP keyword detection during playback, with zero orchestrator/TTS coupling.

Invariants:
  1. VAD is NOT an authoritative gate for wake-word evaluation.
  2. Production wake phrase is conceptually "Hey EV".
  3. Zero third-party dependencies (pure Python standard library).
  4. Frame rechunking preserves chronological sample order and retains exact leftovers.
  5. STOP detection is an event abstraction only; zero execution or cancellation side-effects.
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Sequence

from core.voice_capture import AudioFormatError, AudioFrame

logger = logging.getLogger("ev.voice_wakeword")

DEFAULT_TARGET_WAKE_PHRASE: str = "Hey EV"
DEFAULT_RECHUNKER_TARGET_SAMPLES: int = 1280  # 80 ms @ 16 kHz (openWakeWord standard)


# ============================================================================
# WakeWordResult
# ============================================================================
@dataclass(frozen=True)
class WakeWordResult:
    """
    Immutable result representing a wake-word detection event.

    Fields:
      detected: boolean indicating whether the wake phrase was detected.
      keyword: name of the detected keyword/phrase (e.g. "Hey EV").
      confidence: confidence score of the detection [0.0, 1.0].
      timestamp: monotonic timestamp corresponding to detection.
    """
    detected: bool
    keyword: str
    confidence: float
    timestamp: float

    def __post_init__(self) -> None:
        if not isinstance(self.detected, bool):
            raise TypeError(f"detected must be bool, got {type(self.detected).__name__}")
        if not isinstance(self.keyword, str):
            raise TypeError(f"keyword must be str, got {type(self.keyword).__name__}")
        if not isinstance(self.confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(self.confidence).__name__}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"confidence must be in range [0.0, 1.0], got {self.confidence}")
        if not isinstance(self.timestamp, (int, float)):
            raise TypeError(f"timestamp must be numeric, got {type(self.timestamp).__name__}")

    def __repr__(self) -> str:
        # Privacy Invariant: NEVER dump or log raw audio bytes.
        return (
            f"WakeWordResult(detected={self.detected}, keyword='{self.keyword}', "
            f"conf={self.confidence:.2f}, ts={self.timestamp:.3f})"
        )


# ============================================================================
# EVWakeWordProvider Abstraction
# ============================================================================
class EVWakeWordProvider(ABC):
    """
    Abstract interface for Wake-Word detection providers.
    """

    @abstractmethod
    def process_frame(self, frame: AudioFrame) -> Optional[WakeWordResult]:
        """
        Evaluate an AudioFrame and return WakeWordResult if evaluated, or None.
        Must operate independently of VAD state.
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset internal model buffers, states, and detection histories."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @property
    def target_phrase(self) -> str:
        """Configured target wake phrase."""
        return DEFAULT_TARGET_WAKE_PHRASE

    @property
    def is_available(self) -> bool:
        """Return True if this provider can execute on the current host."""
        return True


# ============================================================================
# MockWakeWordProvider (Testing / CI Foundation)
# ============================================================================
class MockWakeWordProvider(EVWakeWordProvider):
    """
    Deterministic in-memory wake-word provider for testing and CI.
    Supports scripted detection events, trigger-after-N-frames, or marker matching.
    """

    def __init__(
        self,
        trigger_after_frames: Optional[int] = None,
        trigger_on_marker: Optional[bytes] = None,
        scripted_results: Optional[Sequence[Optional[WakeWordResult]]] = None,
        target_phrase: str = DEFAULT_TARGET_WAKE_PHRASE,
        default_confidence: float = 0.95,
    ) -> None:
        self.trigger_after_frames: Optional[int] = trigger_after_frames
        self.trigger_on_marker: Optional[bytes] = trigger_on_marker
        self._target_phrase: str = target_phrase
        self.default_confidence: float = default_confidence

        self._scripted_results: List[Optional[WakeWordResult]] = (
            list(scripted_results) if scripted_results is not None else []
        )
        self._script_index: int = 0
        self._processed_frames: List[AudioFrame] = []
        self._manual_trigger: bool = False
        self._lock = threading.Lock()

    @property
    def provider_name(self) -> str:
        return "mock_wakeword"

    @property
    def target_phrase(self) -> str:
        return self._target_phrase

    def set_triggered(self, triggered: bool = True) -> None:
        """Programmatically arm or disarm manual detection for the next frame."""
        with self._lock:
            self._manual_trigger = triggered

    def process_frame(self, frame: AudioFrame) -> Optional[WakeWordResult]:
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        with self._lock:
            self._processed_frames.append(frame)
            idx = len(self._processed_frames)

            # 1. Scripted result sequence takes highest priority
            if self._script_index < len(self._scripted_results):
                res = self._scripted_results[self._script_index]
                self._script_index += 1
                return res

            # 2. Manual trigger
            if self._manual_trigger:
                self._manual_trigger = False
                return WakeWordResult(
                    detected=True,
                    keyword=self._target_phrase,
                    confidence=self.default_confidence,
                    timestamp=frame.timestamp,
                )

            # 3. Trigger on marker bytes in frame payload
            if self.trigger_on_marker is not None and self.trigger_on_marker in frame.data:
                return WakeWordResult(
                    detected=True,
                    keyword=self._target_phrase,
                    confidence=self.default_confidence,
                    timestamp=frame.timestamp,
                )

            # 4. Trigger after N frames
            if self.trigger_after_frames is not None and idx >= self.trigger_after_frames:
                return WakeWordResult(
                    detected=True,
                    keyword=self._target_phrase,
                    confidence=self.default_confidence,
                    timestamp=frame.timestamp,
                )

            return None

    def reset(self) -> None:
        with self._lock:
            self._processed_frames.clear()
            self._script_index = 0
            self._manual_trigger = False

    @property
    def processed_count(self) -> int:
        with self._lock:
            return len(self._processed_frames)

    def get_processed_frames(self) -> List[AudioFrame]:
        with self._lock:
            return list(self._processed_frames)


# ============================================================================
# AudioFrameRechunker (Adapter for Frame Size Transformation)
# ============================================================================
class AudioFrameRechunker:
    """
    Deterministic adapter converting canonical capture frames (e.g. 480 samples / 30 ms)
    into detector-specific sample windows (e.g. 1280 samples / 80 ms) without sample loss.

    Preserves:
      - Chronological sample ordering
      - Exact sample bytes
      - Leftover sample retention across accumulation boundaries
      - Deterministic timestamp tracking
    """

    def __init__(
        self,
        target_samples: int = DEFAULT_RECHUNKER_TARGET_SAMPLES,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        if target_samples <= 0:
            raise ValueError(f"target_samples must be > 0, got {target_samples}")
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be > 0, got {sample_rate}")
        if channels <= 0:
            raise ValueError(f"channels must be > 0, got {channels}")
        if sample_width <= 0:
            raise ValueError(f"sample_width must be > 0, got {sample_width}")

        self.target_samples: int = target_samples
        self.sample_rate: int = sample_rate
        self.channels: int = channels
        self.sample_width: int = sample_width

        self.bytes_per_sample_block: int = channels * sample_width
        self.target_bytes: int = target_samples * self.bytes_per_sample_block

        self._buffer: bytearray = bytearray()
        self._current_timestamp: Optional[float] = None
        self._lock = threading.Lock()

    @property
    def buffered_samples(self) -> int:
        """Current number of un-emitted samples remaining in the rechunker."""
        with self._lock:
            return len(self._buffer) // self.bytes_per_sample_block

    @property
    def buffered_bytes(self) -> int:
        """Current number of un-emitted bytes remaining in the rechunker."""
        with self._lock:
            return len(self._buffer)

    @property
    def is_empty(self) -> bool:
        """Return True if no leftover bytes are currently buffered."""
        with self._lock:
            return len(self._buffer) == 0

    def push_frame(self, frame: AudioFrame) -> List[AudioFrame]:
        """
        Ingest an AudioFrame, accumulate samples, and emit all complete target windows.

        Example with 480-sample frames and 1280-sample target:
          Frame 1 (480 samples): buffer=480  -> emits []
          Frame 2 (480 samples): buffer=960  -> emits []
          Frame 3 (480 samples): buffer=1440 -> emits [1280 samples], buffer retains 160 samples.

        Raises:
          TypeError: if frame is not an AudioFrame.
          AudioFormatError: if frame metadata does not match rechunker format.
        """
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        if (
            frame.sample_rate != self.sample_rate
            or frame.channels != self.channels
            or frame.sample_width != self.sample_width
        ):
            raise AudioFormatError(
                f"AudioFrame format mismatch: expected rate={self.sample_rate}, "
                f"ch={self.channels}, width={self.sample_width}B; got rate={frame.sample_rate}, "
                f"ch={frame.channels}, width={frame.sample_width}B"
            )

        emitted: List[AudioFrame] = []

        with self._lock:
            if len(self._buffer) == 0:
                self._current_timestamp = frame.timestamp

            self._buffer.extend(frame.data)

            # Emit all fully accumulated target windows
            while len(self._buffer) >= self.target_bytes:
                chunk_bytes = bytes(self._buffer[: self.target_bytes])
                del self._buffer[: self.target_bytes]

                ts = self._current_timestamp if self._current_timestamp is not None else frame.timestamp
                emitted_frame = AudioFrame(
                    data=chunk_bytes,
                    sample_rate=self.sample_rate,
                    channels=self.channels,
                    sample_width=self.sample_width,
                    timestamp=ts,
                )
                emitted.append(emitted_frame)

                # Deterministically advance timestamp for the remaining leftover samples
                seconds_consumed = self.target_samples / self.sample_rate
                if self._current_timestamp is not None:
                    self._current_timestamp += seconds_consumed

        return emitted

    def clear(self) -> None:
        """Discard all accumulated leftover samples and reset timestamp."""
        with self._lock:
            self._buffer.clear()
            self._current_timestamp = None

    def reset(self) -> None:
        """Alias for clear()."""
        self.clear()


# ============================================================================
# STOP / Barge-In Abstraction (Foundation Only)
# ============================================================================
class EVBargeInStopDetector(ABC):
    """
    Abstract interface for emergency barge-in STOP detection during speech playback.

    Invariant:
      This is a pure detection abstraction. It does NOT invoke cancellation,
      does NOT clear ring buffers, and does NOT call orchestrator or TTS directly.
      Convergence into E.V.'s cancellation runtime occurs at the integration layer.
    """

    @abstractmethod
    def process_frame(self, frame: AudioFrame) -> bool:
        """Evaluate an AudioFrame and return True if a STOP event is detected."""

    @abstractmethod
    def reset(self) -> None:
        """Reset internal detector state."""

    @property
    @abstractmethod
    def detector_name(self) -> str:
        """Human-readable detector identifier."""


class MockBargeInStopDetector(EVBargeInStopDetector):
    """
    Deterministic mock STOP detector for unit testing.
    Zero external dependencies, zero hardware, zero side-effects.
    """

    def __init__(
        self,
        trigger_after_frames: Optional[int] = None,
        trigger_on_marker: Optional[bytes] = None,
    ) -> None:
        self.trigger_after_frames: Optional[int] = trigger_after_frames
        self.trigger_on_marker: Optional[bytes] = trigger_on_marker
        self._processed_frames: List[AudioFrame] = []
        self._manual_trigger: bool = False
        self._lock = threading.Lock()

    @property
    def detector_name(self) -> str:
        return "mock_barge_in_stop"

    def set_triggered(self, triggered: bool = True) -> None:
        """Programmatically arm or disarm manual STOP trigger for the next frame."""
        with self._lock:
            self._manual_trigger = triggered

    def process_frame(self, frame: AudioFrame) -> bool:
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        with self._lock:
            self._processed_frames.append(frame)
            idx = len(self._processed_frames)

            if self._manual_trigger:
                self._manual_trigger = False
                return True

            if self.trigger_on_marker is not None and self.trigger_on_marker in frame.data:
                return True

            if self.trigger_after_frames is not None and idx >= self.trigger_after_frames:
                return True

            return False

    def reset(self) -> None:
        with self._lock:
            self._processed_frames.clear()
            self._manual_trigger = False

    @property
    def processed_count(self) -> int:
        with self._lock:
            return len(self._processed_frames)
