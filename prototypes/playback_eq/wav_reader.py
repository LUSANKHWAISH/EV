"""Streaming WAV file reader with multi-format PCM decoding to float32."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
import wave
import numpy as np


class WavReader:
    """Reads uncompressed WAV files and yields standardized float32 PCM blocks."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        if not self.path.exists():
            raise FileNotFoundError(f"WAV file not found: {self.path}")

        self._wave: Optional[wave.Wave_read] = None
        self._open()

    def _open(self) -> None:
        self._wave = wave.open(str(self.path), "rb")
        self.channels = self._wave.getnchannels()
        self.sample_rate = self._wave.getframerate()
        self.sample_width = self._wave.getsampwidth()
        self.total_frames = self._wave.getnframes()
        self.duration_seconds = (
            self.total_frames / self.sample_rate if self.sample_rate > 0 else 0.0
        )

    def close(self) -> None:
        if self._wave is not None:
            self._wave.close()
            self._wave = None

    def __enter__(self) -> WavReader:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def tell(self) -> int:
        if self._wave is None:
            return 0
        return self._wave.tell()

    def seek(self, frame_idx: int) -> None:
        if self._wave is not None:
            frame_idx = max(0, min(int(frame_idx), self.total_frames))
            self._wave.setpos(frame_idx)

    def read_frames(self, count: int, upmix_mono: bool = True) -> np.ndarray:
        """Read up to `count` frames from the WAV file and decode to float32 [-1.0, 1.0].

        Returns array with shape (frames, channels).
        """
        if self._wave is None:
            return np.empty((0, 2 if upmix_mono and self.channels == 1 else self.channels), dtype=np.float32)

        raw_bytes = self._wave.readframes(count)
        if not raw_bytes:
            return np.empty((0, 2 if upmix_mono and self.channels == 1 else self.channels), dtype=np.float32)

        # Decode based on sample width
        if self.sample_width == 1:
            # 8-bit unsigned PCM
            raw = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32)
            pcm = (raw - 128.0) / 128.0
        elif self.sample_width == 2:
            # 16-bit signed PCM
            raw = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
            pcm = raw / 32768.0
        elif self.sample_width == 3:
            # 24-bit signed PCM (packed 3 bytes per sample)
            byte_arr = np.frombuffer(raw_bytes, dtype=np.uint8)
            num_samples = len(byte_arr) // 3
            # Reshape to (N, 3), pad with 0 for most-significant 32-bit alignment
            padded = np.zeros((num_samples, 4), dtype=np.uint8)
            padded[:, 1:] = byte_arr.reshape((num_samples, 3))
            # Interpret as int32
            raw32 = padded.view(dtype=np.int32).squeeze(-1).astype(np.float32)
            pcm = raw32 / 2147483648.0
        elif self.sample_width == 4:
            # 32-bit PCM (float or int)
            try:
                # Attempt float32 first
                pcm = np.frombuffer(raw_bytes, dtype=np.float32).copy()
                if np.max(np.abs(pcm)) > 10.0:
                    # Likely 32-bit int
                    raw_int = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32)
                    pcm = raw_int / 2147483648.0
            except Exception:
                raw_int = np.frombuffer(raw_bytes, dtype=np.int32).astype(np.float32)
                pcm = raw_int / 2147483648.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {self.sample_width} bytes")

        # Reshape into [frames, channels]
        frames_read = len(pcm) // self.channels
        pcm_2d = pcm[: frames_read * self.channels].reshape((frames_read, self.channels))

        # Upmix mono to stereo if requested
        if upmix_mono and self.channels == 1:
            pcm_2d = np.repeat(pcm_2d, 2, axis=1)

        return np.ascontiguousarray(pcm_2d, dtype=np.float32)
