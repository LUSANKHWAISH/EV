"""Equalizer DSP processing chain with 10-band cascade, smooth transitions, clipping detection, and bypass."""
from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import List, Optional, Sequence, Tuple
import numpy as np

from .biquad import apply_sos_filter, peaking_sos, sos_freq_response

# Standard 10-band ISO octave center frequencies
EQ_10_BAND_FREQUENCIES: Tuple[float, ...] = (
    31.0,
    62.0,
    125.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    4000.0,
    8000.0,
    16000.0,
)

# Standard 1-octave Q factor: Q = 1 / (2 * sinh(ln(2)/2 * BW)) ≈ 1.4142 for BW = 1.0 octave.
# This ensures neighboring bands intersect at approximately the -3dB point without excessive ripple.
EQ_DEFAULT_Q: float = 1.4142


@dataclass
class EQBand:
    hz: float = 1000.0
    gain_db: float = 0.0
    q: float = EQ_DEFAULT_Q
    enabled: bool = True


class EqualizerDSP:
    """Manages audio preamp, 10-band graphic/parametric EQ, smooth transitions, and clipping detection."""

    def __init__(self, sample_rate: int = 48000, channels: int = 2):
        self.sample_rate = int(sample_rate)
        self.channels = int(channels)

        self._preamp_db: float = 0.0
        self._target_preamp_linear: float = 1.0
        self._current_preamp_linear: float = 1.0

        # Initialize 10 standard ISO bands
        self.bands: List[EQBand] = [
            EQBand(hz=f, gain_db=0.0, q=EQ_DEFAULT_Q, enabled=True)
            for f in EQ_10_BAND_FREQUENCIES
        ]
        self.bypass: bool = False

        # Active filter coefficients (shape: [num_bands, 6]) & state (shape: [num_bands, 2, channels])
        self._current_sos: np.ndarray = self._build_cascade_sos(self.bands)
        self._zi: np.ndarray = np.zeros((len(self.bands), 2, self.channels), dtype=np.float64)

        # Transition management for click-free parameter smoothing
        self._pending_sos: Optional[np.ndarray] = None
        self._transition_active: bool = False
        self._old_zi: Optional[np.ndarray] = None
        self._old_sos: Optional[np.ndarray] = None

        # Diagnostics & Metrics
        self.last_processing_time_ms: float = 0.0
        self.total_blocks_processed: int = 0
        self.clipped_samples: int = 0
        self.is_clipping: bool = False
        self._clip_hold_counter: int = 0
        self.peak_dbfs: float = -120.0
        self.dynamic_headroom_db: float = 120.0

    @property
    def estimated_headroom_db(self) -> float:
        """Estimated filter headroom in dB based on maximum combined boost + preamp.
        0.0 dB when response is flat. Negative when combined filter boost exceeds 0 dBFS.
        """
        peak_gain = self.estimate_peak_gain_db() + self.preamp_db
        return float(-peak_gain)

    @property
    def headroom_db(self) -> float:
        return self.estimated_headroom_db

    @property
    def band(self) -> EQBand:
        """Backward-compatibility accessor returning the 1000 Hz mid-band."""
        return self.bands[5]

    @property
    def band_frequencies(self) -> Tuple[float, ...]:
        return EQ_10_BAND_FREQUENCIES

    @property
    def band_gains(self) -> List[float]:
        return [b.gain_db for b in self.bands]

    def get_all_gains(self) -> List[float]:
        return [b.gain_db for b in self.bands]

    def _build_cascade_sos(self, bands: Sequence[EQBand]) -> np.ndarray:
        """Construct the concatenated SOS matrix for all enabled bands."""
        sections = []
        for b in bands:
            if not b.enabled or abs(b.gain_db) < 1e-6:
                # Unity passthrough section: [1, 0, 0, 1, 0, 0]
                sec = np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
            else:
                sec = peaking_sos(self.sample_rate, b.hz, b.gain_db, b.q)
            sections.append(sec)
        return np.vstack(sections)

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
        """Reset internal filter delay lines (zi) to zero while preserving filter coefficients."""
        if self._pending_sos is not None:
            self._current_sos = self._pending_sos
            self._pending_sos = None
        self._zi = np.zeros((len(self.bands), 2, self.channels), dtype=np.float64)
        self._old_zi = None
        self._old_sos = None
        self._transition_active = False

    def set_preamp_db(self, db: float) -> None:
        """Set pre-filter gain in decibels [-18.0, +18.0]."""
        self._preamp_db = float(np.clip(db, -18.0, 18.0))
        self._target_preamp_linear = 10.0 ** (self._preamp_db / 20.0)

    @property
    def preamp_db(self) -> float:
        return self._preamp_db

    def set_band_gain(self, band_idx: int, gain_db: float, force_immediate: bool = False) -> None:
        """Adjust a specific band's gain (-12 dB to +12 dB)."""
        if 0 <= band_idx < len(self.bands):
            self.bands[band_idx].gain_db = float(np.clip(gain_db, -12.0, 12.0))
            self._update_coefficients(force_immediate=force_immediate)

    def get_band_gain(self, band_idx: int) -> float:
        if 0 <= band_idx < len(self.bands):
            return self.bands[band_idx].gain_db
        return 0.0

    def set_all_gains(self, gains: Sequence[float], force_immediate: bool = False) -> None:
        """Set gains for all 10 bands simultaneously."""
        for idx, g in enumerate(gains[: len(self.bands)]):
            self.bands[idx].gain_db = float(np.clip(g, -12.0, 12.0))
        self._update_coefficients(force_immediate=force_immediate)

    def reset_flat(self, force_immediate: bool = False) -> None:
        """Reset all 10 bands and preamp to 0 dB flat response."""
        for b in self.bands:
            b.gain_db = 0.0
        self.set_preamp_db(0.0)
        self._update_coefficients(force_immediate=force_immediate)

    def set_eq_band(
        self,
        hz: float,
        gain_db: float,
        q: float = EQ_DEFAULT_Q,
        enabled: bool = True,
        force_immediate: bool = False,
    ) -> None:
        """Backward-compatible setter: finds the closest band to hz and updates it."""
        # Find closest frequency in self.bands
        diffs = [abs(b.hz - hz) for b in self.bands]
        idx = int(np.argmin(diffs))
        self.bands[idx].hz = float(hz)
        self.bands[idx].gain_db = float(np.clip(gain_db, -12.0, 12.0))
        self.bands[idx].q = float(q)
        self.bands[idx].enabled = bool(enabled)
        self._update_coefficients(force_immediate=force_immediate)

    def set_bypass(self, bypass: bool, force_immediate: bool = False) -> None:
        """Toggle EQ bypass with click-free transition. Does not affect master volume or mute."""
        if self.bypass != bool(bypass) or force_immediate:
            self.bypass = bool(bypass)
            self._update_coefficients(force_immediate=force_immediate)

    def estimate_peak_gain_db(self) -> float:
        """Estimate the maximum combined electrical filter gain across the spectrum."""
        if self.bypass:
            return 0.0
        sos_to_test = self._pending_sos if self._pending_sos is not None else self._current_sos
        test_freqs = np.logspace(np.log10(20.0), np.log10(min(20000.0, self.sample_rate * 0.45)), 80)
        _, db_resp = sos_freq_response(sos_to_test, test_freqs, rate=self.sample_rate)
        return float(np.max(db_resp))

    def _update_coefficients(self, force_immediate: bool = False) -> None:
        if self.bypass:
            new_sos = np.vstack([
                np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)
                for _ in self.bands
            ])
        else:
            new_sos = self._build_cascade_sos(self.bands)

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

        Applies smooth preamp interpolation, 10-band cascaded SOS filtering with
        crossfade smoothing, headroom calculation, and clipping detection.
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
            self.dynamic_headroom_db = 120.0
            self.is_clipping = False
            return np.zeros_like(x)

        # 3. Filtering or direct passthrough if bypassed
        if self.bypass and not self._transition_active:
            y = x_scaled
            self._zi.fill(0.0)
        elif self._transition_active and self._pending_sos is not None and self._old_sos is not None:
            # Crossfade transition between old and new filter states
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
            # Regular cascaded 10-band filtering
            y, self._zi = apply_sos_filter(self._current_sos, x_scaled, zi=self._zi)

        # 4. Clipping and headroom detection
        peak_val = float(np.max(np.abs(y)))
        if peak_val > 1e-6:
            self.peak_dbfs = float(20.0 * math.log10(peak_val))
            self.dynamic_headroom_db = float(-self.peak_dbfs)
        else:
            self.peak_dbfs = -120.0
            self.dynamic_headroom_db = 120.0

        if peak_val > 1.0:
            over_samples = int(np.sum(np.abs(y) > 1.0))
            self.clipped_samples += over_samples
            self.is_clipping = True
            self._clip_hold_counter = 10  # Hold clipping indicator for 10 blocks (~200ms)
            # Safety clamp to prevent wrap-around driver clicks (note: hard clipping introduces harmonic distortion)
            y = np.clip(y, -1.0, 1.0)
        else:
            if self._clip_hold_counter > 0:
                self._clip_hold_counter -= 1
            else:
                self.is_clipping = False

        y_out = np.nan_to_num(y, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        self.last_processing_time_ms = (time.perf_counter() - t0) * 1000.0
        self.total_blocks_processed += 1

        return y_out.ravel() if is_1d else y_out
