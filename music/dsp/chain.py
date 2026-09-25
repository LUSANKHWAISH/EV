"""Equalizer DSP processing chain with smooth transitions, clipping detection, and bypass."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Optional
import numpy as np

from .biquad import apply_sos_filter, peaking_sos


@dataclass
class EQBand:
    hz: float = 1000.0
    gain_db: float = 0.0
    q: float = 1.0
    enabled: bool = True


class EqualizerDSP:
    """Manages audio preamp, parametric peaking EQ, smooth transitions, and clipping detection."""

    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

        self._preamp_db: float = 0.0
        self._target_preamp_linear: float = 1.0
        self._current_preamp_linear: float = 1.0

        self.band = EQBand(hz=1000.0, gain_db=0.0, q=1.0, enabled=True)
        self.bypass: bool = False

        # Active filter coefficients & state
        self._current_sos: np.ndarray = peaking_sos(self.sample_rate, self.band.hz, self.band.gain_db, self.band.q)
        self._zi: np.ndarray = np.zeros((1, 2, self.channels), dtype=np.float64)

        # Transition management for click-free parameter smoothing
        self._pending_sos: Optional[np.ndarray] = None
        self._transition_active: bool = False
        self._old_zi: Optional[np.ndarray] = None
        self._old_sos: Optional[np.ndarray] = None

        # Diagnostics & Metrics
        self.last_processing_time_ms: float = 0.0
        self.total_blocks_processed: int = 0
        self.clipped_samples: int = 0
        self.peak_dbfs: float = -120.0
        self.headroom_db: float = 120.0

    def set_sample_rate(self, rate: int) -> None:
        if rate != self.sample_rate and rate > 0:
            self.sample_rate = int(rate)
            self._update_coefficients(force_immediate=True)
            self.reset_state()

    def set_channels(self, channels: int) -> None:
        if channels != self.channels and channels > 0:
            self.channels = int(channels)
            self.reset_state()

    def reset_state(self) -> None:
        """Reset internal filter delay lines."""
        if self._pending_sos is not None:
            self._current_sos = self._pending_sos
            self._pending_sos = None
        self._zi = np.zeros((1, 2, self.channels), dtype=np.float64)
        self._old_zi = None
        self._old_sos = None
        self._transition_active = False

    def set_preamp_db(self, db: float) -> None:
        """Set pre-filter gain in decibels [-24.0, +24.0]."""
        self._preamp_db = float(np.clip(db, -24.0, 24.0))
        self._target_preamp_linear = 10.0 ** (self._preamp_db / 20.0)

    @property
    def preamp_db(self) -> float:
        return self._preamp_db

    def set_eq_band(self, hz: float, gain_db: float, q: float, enabled: bool = True, force_immediate: bool = False) -> None:
        """Update peaking EQ parameters with smooth click-free crossfade transition."""
        self.band.hz = float(hz)
        self.band.gain_db = float(gain_db)
        self.band.q = float(q)
        self.band.enabled = bool(enabled)
        self._update_coefficients(force_immediate=force_immediate)

    def set_bypass(self, bypass: bool, force_immediate: bool = False) -> None:
        """Toggle EQ bypass with click-free transition."""
        if self.bypass != bool(bypass) or force_immediate:
            self.bypass = bool(bypass)
            self._update_coefficients(force_immediate=force_immediate)

    def _update_coefficients(self, force_immediate: bool = False) -> None:
        if self.bypass or not self.band.enabled:
            new_sos = np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
        else:
            new_sos = peaking_sos(self.sample_rate, self.band.hz, self.band.gain_db, self.band.q)

        if force_immediate:
            self._current_sos = new_sos
            self._pending_sos = None
            self._transition_active = False
            self._old_zi = None
            self._old_sos = None
        else:
            # Trigger smooth crossfade transition across next audio block
            self._old_sos = np.copy(self._current_sos)
            self._old_zi = np.copy(self._zi)
            self._pending_sos = new_sos
            self._transition_active = True

    def process(self, x: np.ndarray) -> np.ndarray:
        """Process an input block of PCM audio (shape [N, C] or [N]).

        Applies smooth preamp interpolation, EQ filtering with crossfade smoothing,
        headroom calculation, and clipping detection.
        """
        t0 = time.perf_counter()
        is_1d = (x.ndim == 1)
        if is_1d:
            x_2d = x[:, np.newaxis]
        else:
            x_2d = x

        frames, channels = x_2d.shape
        if channels != self.channels:
            self.set_channels(channels)

        # 1. Preamp smoothing across the block
        if abs(self._current_preamp_linear - self._target_preamp_linear) > 1e-5:
            preamp_ramp = np.linspace(
                self._current_preamp_linear,
                self._target_preamp_linear,
                frames,
                dtype=np.float64,
            )[:, np.newaxis]
            self._current_preamp_linear = self._target_preamp_linear
            x_scaled = x_2d.astype(np.float64) * preamp_ramp
        else:
            x_scaled = x_2d.astype(np.float64) * self._current_preamp_linear

        # 2. Check for exact silence
        is_silent = np.all(np.abs(x_scaled) < 1e-8)
        if is_silent and np.all(np.abs(self._zi) < 1e-8) and not self._transition_active:
            self._zi.fill(0.0)
            self.last_processing_time_ms = (time.perf_counter() - t0) * 1000.0
            self.total_blocks_processed += 1
            self.peak_dbfs = -120.0
            self.headroom_db = 120.0
            return np.zeros_like(x)

        # 3. Filtering or direct passthrough if bypassed
        if self.bypass and not self._transition_active:
            y = x_scaled
            self._zi.fill(0.0)
        elif self._transition_active and self._pending_sos is not None and self._old_sos is not None:
            # Crossfade transition between old and new state
            if self._old_sos is None:
                y_old = x_scaled
            else:
                y_old, self._old_zi = apply_sos_filter(self._old_sos, x_scaled, zi=self._old_zi)

            if self.bypass:
                y_new = x_scaled
                self._zi.fill(0.0)
            else:
                y_new, self._zi = apply_sos_filter(self._pending_sos, x_scaled, zi=self._zi)

            ramp = np.linspace(0.0, 1.0, frames, dtype=np.float64)[:, np.newaxis]
            y = (1.0 - ramp) * y_old + ramp * y_new

            self._current_sos = self._pending_sos
            self._pending_sos = None
            self._transition_active = False
            self._old_zi = None
            self._old_sos = None
        else:
            # Regular filtering
            y, self._zi = apply_sos_filter(self._current_sos, x_scaled, zi=self._zi)

        # 4. Clipping and headroom detection
        peak_val = float(np.max(np.abs(y)))
        if peak_val > 1e-6:
            self.peak_dbfs = float(20.0 * math.log10(peak_val))
            self.headroom_db = float(-self.peak_dbfs)
        else:
            self.peak_dbfs = -120.0
            self.headroom_db = 120.0

        if peak_val > 1.0:
            over_samples = int(np.sum(np.abs(y) > 1.0))
            self.clipped_samples += over_samples
            # Safety clamp to prevent hardware driver corruption
            y = np.clip(y, -1.0, 1.0)

        y_out = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        self.last_processing_time_ms = (time.perf_counter() - t0) * 1000.0
        self.total_blocks_processed += 1

        return y_out.ravel() if is_1d else y_out
