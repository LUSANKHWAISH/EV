"""
Audio Capture Abstraction and Ring Buffer foundation for E.V. (Task 014B).

Establishes the hardware-independent audio ingress contract for the voice pipeline.
Provides:
  - Canonical audio contract constants (16 kHz, 16-bit Mono PCM, 30 ms frames).
  - AudioFrame: immutable, validated representation of a discrete PCM audio slice.
  - AudioRingBuffer: thread-safe bounded circular frame buffer with oldest-frame eviction.
  - EVAudioCaptureProvider: abstract base provider establishing the capture interface.
  - MockAudioCaptureProvider: deterministic in-memory provider for automated testing and CI.
  - Domain exceptions (AudioCaptureError, AudioFormatError, BufferClosedError).

Invariants:
  1. Audio ingress only. Zero execution authority. Never calls orchestrator, brain, or risk.
  2. Zero persistence. Audio frames live exclusively in volatile RAM buffers. No disk writes.
  3. Pure Python standard library. Zero mandatory third-party dependencies (no numpy, sounddevice, etc.).
  4. Privacy preserving. Frame reprs never log or dump raw audio byte contents.
"""
from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, List, Optional, Sequence

logger = logging.getLogger("ev.voice_capture")

# ============================================================================
# Canonical Audio Format Specification
# ============================================================================
DEFAULT_SAMPLE_RATE: int = 16000        # 16 kHz standard
DEFAULT_CHANNELS: int = 1               # Mono
DEFAULT_SAMPLE_WIDTH: int = 2           # 16-bit signed PCM (2 bytes/sample)
DEFAULT_FRAME_DURATION_MS: float = 30.0 # 30 ms per discrete processing frame
DEFAULT_FRAME_DURATION_SEC: float = 0.030
DEFAULT_SAMPLES_PER_FRAME: int = 480    # 16000 * 0.030 = 480 samples
DEFAULT_BYTES_PER_FRAME: int = 960      # 480 samples * 1 ch * 2 bytes = 960 bytes
DEFAULT_RING_BUFFER_CAPACITY: int = 100 # ~3.0 seconds rolling audio at 30ms/frame


# ============================================================================
# Domain Exceptions
# ============================================================================
class AudioCaptureError(Exception):
    """Base exception for audio capture and buffering subsystem."""


class AudioFormatError(AudioCaptureError):
    """Raised when audio data or format metadata fails validation."""


class BufferClosedError(AudioCaptureError):
    """Raised when attempting write operations on a closed ring buffer."""


# ============================================================================
# AudioFrame Representation
# ============================================================================
@dataclass(frozen=True)
class AudioFrame:
    """
    Immutable representation of a discrete PCM audio frame.

    Validates on construction:
      - data is non-empty bytes or bytes-like object
      - sample_rate > 0
      - channels > 0
      - sample_width > 0
      - data length aligns exactly with (channels * sample_width)
    """
    data: bytes
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = DEFAULT_CHANNELS
    sample_width: int = DEFAULT_SAMPLE_WIDTH
    timestamp: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        if not isinstance(self.data, (bytes, bytearray, memoryview)):
            raise AudioFormatError(
                f"AudioFrame data must be bytes-like, got {type(self.data).__name__}"
            )
        raw_bytes = bytes(self.data)
        object.__setattr__(self, "data", raw_bytes)

        if len(raw_bytes) == 0:
            raise AudioFormatError("AudioFrame data cannot be empty")
        if self.sample_rate <= 0:
            raise AudioFormatError(f"sample_rate must be > 0, got {self.sample_rate}")
        if self.channels <= 0:
            raise AudioFormatError(f"channels must be > 0, got {self.channels}")
        if self.sample_width <= 0:
            raise AudioFormatError(f"sample_width must be > 0, got {self.sample_width}")

        bytes_per_sample_block = self.channels * self.sample_width
        if len(raw_bytes) % bytes_per_sample_block != 0:
            raise AudioFormatError(
                f"AudioFrame data length ({len(raw_bytes)} bytes) is not an integral multiple "
                f"of channels * sample_width ({bytes_per_sample_block} bytes)"
            )

    @property
    def sample_count(self) -> int:
        """Number of discrete audio samples per channel in this frame."""
        return len(self.data) // (self.channels * self.sample_width)

    @property
    def duration_seconds(self) -> float:
        """Frame duration in seconds."""
        return self.sample_count / self.sample_rate

    @property
    def duration_ms(self) -> float:
        """Frame duration in milliseconds."""
        return (self.sample_count / self.sample_rate) * 1000.0

    def is_canonical(self) -> bool:
        """Return True if frame conforms to standard 16kHz, 1ch, 16-bit, 30ms specs."""
        return (
            self.sample_rate == DEFAULT_SAMPLE_RATE
            and self.channels == DEFAULT_CHANNELS
            and self.sample_width == DEFAULT_SAMPLE_WIDTH
            and len(self.data) == DEFAULT_BYTES_PER_FRAME
        )

    def __repr__(self) -> str:
        # Privacy Invariant: NEVER dump or log raw audio bytes.
        return (
            f"AudioFrame(bytes={len(self.data)}, rate={self.sample_rate}Hz, "
            f"ch={self.channels}, width={self.sample_width}B, "
            f"duration={self.duration_ms:.1f}ms, ts={self.timestamp:.3f})"
        )


def create_silence_frame(
    sample_rate: int = DEFAULT_SAMPLE_RATE,
    channels: int = DEFAULT_CHANNELS,
    sample_width: int = DEFAULT_SAMPLE_WIDTH,
    duration_ms: float = DEFAULT_FRAME_DURATION_MS,
    timestamp: Optional[float] = None,
) -> AudioFrame:
    """Generate a canonical AudioFrame containing digital PCM silence (zero-bytes)."""
    samples = int(sample_rate * (duration_ms / 1000.0))
    if samples <= 0:
        samples = 1
    num_bytes = samples * channels * sample_width
    ts = timestamp if timestamp is not None else time.monotonic()
    return AudioFrame(
        data=b"\x00" * num_bytes,
        sample_rate=sample_rate,
        channels=channels,
        sample_width=sample_width,
        timestamp=ts,
    )


# ============================================================================
# AudioRingBuffer
# ============================================================================
class AudioRingBuffer:
    """
    Thread-safe bounded circular frame buffer.

    Retains up to `max_frames` most recent AudioFrame items in FIFO order.
    When capacity is reached, writes evict the oldest frame deterministically.
    Guarantees bounded memory usage without unbounded queue growth.
    All read/write operations are non-blocking.
    """

    def __init__(self, max_frames: int = DEFAULT_RING_BUFFER_CAPACITY) -> None:
        if max_frames <= 0:
            raise ValueError(f"max_frames must be > 0, got {max_frames}")
        self._max_frames: int = max_frames
        self._buffer: Deque[AudioFrame] = deque(maxlen=max_frames)
        self._lock: threading.RLock = threading.RLock()
        self._is_closed: bool = False
        self._dropped_frames_count: int = 0
        self._total_written_count: int = 0

    @property
    def capacity(self) -> int:
        """Maximum number of frames this buffer can hold."""
        return self._max_frames

    @property
    def dropped_frames(self) -> int:
        """Total number of frames evicted due to buffer overflow."""
        with self._lock:
            return self._dropped_frames_count

    @property
    def total_written(self) -> int:
        """Total number of frames successfully accepted."""
        with self._lock:
            return self._total_written_count

    @property
    def is_closed(self) -> bool:
        """Return True if the buffer is closed to new writes."""
        with self._lock:
            return self._is_closed

    def write(self, frame: AudioFrame) -> bool:
        """
        Write an AudioFrame to the ring buffer (non-blocking).

        Returns:
          True if the frame was appended without overflowing.
          False if an older frame was evicted to make room.

        Raises:
          BufferClosedError: if write is attempted on a closed buffer.
          TypeError: if frame is not an instance of AudioFrame.
        """
        if not isinstance(frame, AudioFrame):
            raise TypeError(f"Expected AudioFrame, got {type(frame).__name__}")

        with self._lock:
            if self._is_closed:
                raise BufferClosedError("Cannot write to a closed AudioRingBuffer")

            was_full = len(self._buffer) == self._max_frames
            if was_full:
                self._dropped_frames_count += 1

            self._buffer.append(frame)
            self._total_written_count += 1
            return not was_full

    def read(self) -> Optional[AudioFrame]:
        """
        Pop and return the oldest AudioFrame in FIFO order (non-blocking).
        Returns None if buffer is empty.
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer.popleft()

    def read_many(self, max_frames: Optional[int] = None) -> List[AudioFrame]:
        """
        Pop and return up to `max_frames` in FIFO order (non-blocking).
        If max_frames is None, drains and returns all currently buffered frames.
        """
        with self._lock:
            if not self._buffer:
                return []
            count = len(self._buffer) if max_frames is None else min(max_frames, len(self._buffer))
            if count <= 0:
                return []
            result: List[AudioFrame] = []
            for _ in range(count):
                result.append(self._buffer.popleft())
            return result

    def peek(self) -> Optional[AudioFrame]:
        """
        Return the oldest AudioFrame without removing it (non-blocking).
        Returns None if buffer is empty.
        """
        with self._lock:
            if not self._buffer:
                return None
            return self._buffer[0]

    def peek_recent(self, count: Optional[int] = None) -> List[AudioFrame]:
        """
        Return up to `count` most recent AudioFrames in chronological order
        without removing them (non-blocking).
        If count is None, returns all buffered frames.
        Essential for pre-roll window extraction prior to wake-word triggers.
        """
        with self._lock:
            if not self._buffer:
                return []
            if count is None or count >= len(self._buffer):
                return list(self._buffer)
            if count <= 0:
                return []
            return list(self._buffer)[-count:]

    def clear(self) -> None:
        """Discard all buffered frames (non-blocking)."""
        with self._lock:
            self._buffer.clear()

    def close(self) -> None:
        """
        Close the buffer to new writes.
        Subsequent write() calls will raise BufferClosedError.
        Remaining unread frames may still be read.
        """
        with self._lock:
            self._is_closed = True

    def is_empty(self) -> bool:
        """Return True if the buffer currently contains zero frames."""
        with self._lock:
            return len(self._buffer) == 0

    def is_full(self) -> bool:
        """Return True if the buffer currently contains `capacity` frames."""
        with self._lock:
            return len(self._buffer) == self._max_frames

    def __len__(self) -> int:
        """Current number of frames buffered."""
        with self._lock:
            return len(self._buffer)

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"AudioRingBuffer(frames={len(self._buffer)}/{self._max_frames}, "
                f"dropped={self._dropped_frames_count}, closed={self._is_closed})"
            )


# ============================================================================
# EVAudioCaptureProvider Abstraction
# ============================================================================
class EVAudioCaptureProvider(ABC):
    """
    Abstract interface for microphone audio capture providers.
    Establishes the hardware-independent ingress contract.
    Providers produce canonical AudioFrame streams into target buffers.
    """

    @abstractmethod
    def start(self) -> None:
        """Start audio capture."""

    @abstractmethod
    def stop(self) -> None:
        """Stop audio capture."""

    @abstractmethod
    def is_running(self) -> bool:
        """Return True if capture stream is currently active."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can capture audio on this host."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""


# ============================================================================
# MockAudioCaptureProvider (Testing / CI Foundation)
# ============================================================================
class MockAudioCaptureProvider(EVAudioCaptureProvider):
    """
    Deterministic in-memory audio capture provider for testing and CI.
    Feeds simulated or pre-recorded AudioFrames into an optional target AudioRingBuffer.
    Requires zero audio hardware, OS drivers, or third-party packages.
    """

    def __init__(
        self,
        ring_buffer: Optional[AudioRingBuffer] = None,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        channels: int = DEFAULT_CHANNELS,
        sample_width: int = DEFAULT_SAMPLE_WIDTH,
        frame_duration_ms: float = DEFAULT_FRAME_DURATION_MS,
    ) -> None:
        self.ring_buffer: Optional[AudioRingBuffer] = ring_buffer
        self.sample_rate: int = sample_rate
        self.channels: int = channels
        self.sample_width: int = sample_width
        self.frame_duration_ms: float = frame_duration_ms

        self._is_running: bool = False
        self._lock: threading.Lock = threading.Lock()
        self._pushed_frames: List[AudioFrame] = []
        self._push_count: int = 0

    @property
    def provider_name(self) -> str:
        return "mock"

    def is_available(self) -> bool:
        return True

    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def start(self) -> None:
        """Start provider. Idempotent."""
        with self._lock:
            self._is_running = True

    def stop(self) -> None:
        """Stop provider. Idempotent."""
        with self._lock:
            self._is_running = False

    def push_frame(self, frame: AudioFrame) -> AudioFrame:
        """
        Push a validated AudioFrame through the capture provider.
        If ring_buffer is configured, writes the frame to it.
        Also records frame locally for test verification.

        Raises:
          RuntimeError: if provider is not running.
        """
        with self._lock:
            if not self._is_running:
                raise RuntimeError("MockAudioCaptureProvider must be started before pushing frames")
            self._pushed_frames.append(frame)
            self._push_count += 1

        if self.ring_buffer is not None:
            self.ring_buffer.write(frame)
        return frame

    def push_pcm(self, data: bytes, timestamp: Optional[float] = None) -> AudioFrame:
        """Wrap raw PCM bytes into an AudioFrame and push it."""
        ts = timestamp if timestamp is not None else time.monotonic()
        frame = AudioFrame(
            data=data,
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
            timestamp=ts,
        )
        return self.push_frame(frame)

    def push_silence(self, duration_ms: Optional[float] = None) -> AudioFrame:
        """Generate and push a canonical frame of digital PCM silence (zeros)."""
        ms = duration_ms if duration_ms is not None else self.frame_duration_ms
        frame = create_silence_frame(
            sample_rate=self.sample_rate,
            channels=self.channels,
            sample_width=self.sample_width,
            duration_ms=ms,
        )
        return self.push_frame(frame)

    @property
    def pushed_count(self) -> int:
        """Total number of frames pushed through this provider."""
        with self._lock:
            return self._push_count

    def get_pushed_frames(self) -> List[AudioFrame]:
        """Return a snapshot list of all pushed frames."""
        with self._lock:
            return list(self._pushed_frames)

    def clear(self) -> None:
        """Clear recorded pushed frames."""
        with self._lock:
            self._pushed_frames.clear()
            self._push_count = 0
