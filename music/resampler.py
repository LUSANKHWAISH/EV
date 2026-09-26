"""Stateful, continuous streaming resampler for real-time chunked audio playback.

Guarantees:
1. C^1 continuity across chunk boundaries via Catmull-Rom cubic Hermite interpolation.
2. Exact output duration/length matching the sample rate ratio.
3. Anti-aliasing filtering when downsampling.
4. Clean resampler tail draining at end-of-file.
"""
from __future__ import annotations

import numpy as np
import scipy.signal as signal


class StreamingResampler:
    """Continuous, stateful audio resampler for chunked real-time streaming."""

    def __init__(self, in_rate: int, out_rate: int, channels: int = 2):
        self.in_rate = int(in_rate)
        self.out_rate = int(out_rate)
        self.channels = int(channels)
        self.ratio = float(self.in_rate) / float(self.out_rate)
        self.phase: float = 0.0
        self.history = np.zeros((3, self.channels), dtype=np.float32)

        # Anti-aliasing filter when downsampling
        if self.out_rate < self.in_rate:
            cutoff = min(20000.0, 0.45 * float(self.out_rate))
            self.sos = signal.butter(4, cutoff, fs=float(self.in_rate), output="sos")
            self.zi = signal.sosfilt_zi(self.sos)[:, :, None] * np.zeros((1, 1, self.channels), dtype=np.float32)
        else:
            self.sos = None
            self.zi = None

    def reset(self) -> None:
        """Reset internal phase, history, and filter states."""
        self.phase = 0.0
        self.history = np.zeros((3, self.channels), dtype=np.float32)
        if self.sos is not None:
            self.zi = signal.sosfilt_zi(self.sos)[:, :, None] * np.zeros((1, 1, self.channels), dtype=np.float32)

    def process(self, chunk: np.ndarray) -> np.ndarray:
        """Resample a chunk of frames preserving boundary continuity."""
        if len(chunk) == 0:
            return np.zeros((0, self.channels), dtype=np.float32)
        if chunk.ndim == 1:
            chunk = chunk[:, None]

        # Apply anti-aliasing if downsampling
        if self.sos is not None:
            chunk, self.zi = signal.sosfilt(self.sos, chunk, axis=0, zi=self.zi)

        buf = np.vstack([self.history, chunk])
        n_buf = len(buf)
        n_chunk = len(chunk)

        start_pos = 3.0 + self.phase
        max_pos = float(n_buf - 2)

        if start_pos >= max_pos:
            self.history = buf[-3:]
            self.phase -= n_chunk
            return np.zeros((0, self.channels), dtype=np.float32)

        k = np.arange(0, int((max_pos - start_pos) / self.ratio) + 1)
        positions = start_pos + k * self.ratio
        positions = positions[positions < max_pos]
        if len(positions) == 0:
            self.history = buf[-3:]
            self.phase -= n_chunk
            return np.zeros((0, self.channels), dtype=np.float32)

        i0 = np.floor(positions).astype(int)
        u = (positions - i0)[:, None]

        p0 = buf[i0 - 1]
        p1 = buf[i0]
        p2 = buf[i0 + 1]
        p3 = buf[i0 + 2]

        c0 = p1
        c1 = 0.5 * (p2 - p0)
        c2 = p0 - 2.5 * p1 + 2.0 * p2 - 0.5 * p3
        c3 = 0.5 * (p3 - p0) + 1.5 * (p1 - p2)

        out = ((c3 * u + c2) * u + c1) * u + c0

        last_pos = positions[-1]
        next_pos = last_pos + self.ratio
        self.phase = next_pos - (3.0 + n_chunk)
        self.history = buf[-3:]

        return out.astype(np.float32)

    def drain(self) -> np.ndarray:
        """Drain the final fractional tail of the resampler up to end-of-stream."""
        if self.phase >= -1e-5:
            return np.zeros((0, self.channels), dtype=np.float32)

        # Output positions relative to the end of the input stream (strictly < 0.0)
        k = np.arange(0, int(np.ceil(-self.phase / self.ratio)) + 1)
        positions_rel = self.phase + k * self.ratio
        positions_rel = positions_rel[positions_rel < -1e-5]
        if len(positions_rel) == 0:
            return np.zeros((0, self.channels), dtype=np.float32)

        # Pad history (3 samples) with 2 samples replicating the final sample
        # so Catmull-Rom has p2 and p3 available for interpolating up to the boundary.
        pad = np.repeat(self.history[-1:], 2, axis=0)
        buf = np.vstack([self.history, pad])

        # Relative to start of buf (length 5), the end of input stream is at index 3.0
        positions = 3.0 + positions_rel

        i0 = np.floor(positions).astype(int)
        u = (positions - i0)[:, None]

        p0 = buf[i0 - 1]
        p1 = buf[i0]
        p2 = buf[i0 + 1]
        p3 = buf[i0 + 2]

        c0 = p1
        c1 = 0.5 * (p2 - p0)
        c2 = p0 - 2.5 * p1 + 2.0 * p2 - 0.5 * p3
        c3 = 0.5 * (p3 - p0) + 1.5 * (p1 - p2)

        out = ((c3 * u + c2) * u + c1) * u + c0

        # Mark resampler as fully drained
        self.phase = 0.0
        return out.astype(np.float32)

