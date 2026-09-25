"""Biquad Second-Order Section (SOS) filter generation and processing."""
from __future__ import annotations

import math
from typing import Tuple
import numpy as np

try:
    import scipy.signal as signal
    _HAS_SCIPY = True
except ImportError:
    signal = None
    _HAS_SCIPY = False


def peaking_sos(rate: float, hz: float, gain_db: float, q: float) -> np.ndarray:
    """Generate Second-Order Section (SOS) coefficients for an RBJ peaking EQ filter.

    Returns a 1D numpy array of 6 floats: [b0, b1, b2, 1.0, a1, a2] normalized by a0.
    """
    if not all(math.isfinite(v) for v in (rate, hz, gain_db, q)) or rate <= 0:
        raise ValueError("Finite parameters and positive sample rate required")

    # Clamp parameters to physically sound audio boundaries
    hz = float(np.clip(hz, 20.0, rate * 0.45))
    q = float(np.clip(q, 0.1, 18.0))
    gain_db = float(np.clip(gain_db, -24.0, 24.0))

    if abs(gain_db) < 1e-6:
        # Unity gain bypass section
        return np.array([1.0, 0.0, 0.0, 1.0, 0.0, 0.0], dtype=np.float64)

    a_lin = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * hz / rate
    cos_w0 = math.cos(w0)
    sin_w0 = math.sin(w0)
    alpha = sin_w0 / (2.0 * q)

    b0 = 1.0 + alpha * a_lin
    b1 = -2.0 * cos_w0
    b2 = 1.0 - alpha * a_lin
    a0 = 1.0 + alpha / a_lin
    a1 = -2.0 * cos_w0
    a2 = 1.0 - alpha / a_lin

    return np.array(
        [b0 / a0, b1 / a0, b2 / a0, 1.0, a1 / a0, a2 / a0],
        dtype=np.float64,
    )


def sos_freq_response(
    sos: np.ndarray,
    freqs: np.ndarray | list[float],
    rate: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate frequency response (frequencies Hz, magnitude dB) of an SOS filter."""
    freqs_arr = np.asarray(freqs, dtype=np.float64)
    if _HAS_SCIPY:
        w = 2.0 * np.pi * freqs_arr / rate
        _, h = signal.sosfreqz(sos.reshape(-1, 6), worN=w)
        db = 20.0 * np.log10(np.maximum(np.abs(h), 1e-12))
        return freqs_arr, db

    # Analytical fallback without SciPy
    z = np.exp(-1j * 2.0 * math.pi * freqs_arr / rate)
    z2 = z * z
    h_total = np.ones(len(freqs_arr), dtype=np.complex128)
    sos_2d = sos.reshape(-1, 6)
    for section in sos_2d:
        b0, b1, b2, a0, a1, a2 = section
        num = b0 + b1 * z + b2 * z2
        den = a0 + a1 * z + a2 * z2
        h_total *= num / den
    db = 20.0 * np.log10(np.maximum(np.abs(h_total), 1e-12))
    return freqs_arr, db


def apply_sos_filter(
    sos: np.ndarray,
    x: np.ndarray,
    zi: np.ndarray | None = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Filter input audio x using Second-Order Sections (SOS).

    x: np.ndarray with shape (frames, channels) or (frames,).
    zi: initial filter delay state with shape (num_sections, 2, channels).

    Returns:
        (y, zf) where y is the filtered audio, and zf is the final delay state.
    """
    sos_2d = sos.reshape(-1, 6)
    num_sections = sos_2d.shape[0]

    is_1d = (x.ndim == 1)
    if is_1d:
        x_2d = x[:, np.newaxis]
    else:
        x_2d = x

    frames, channels = x_2d.shape
    if zi is None:
        zi = np.zeros((num_sections, 2, channels), dtype=np.float64)

    if _HAS_SCIPY:
        y_out, zf = signal.sosfilt(sos_2d, x_2d, axis=0, zi=zi)
        y_out = np.nan_to_num(y_out, nan=0.0, posinf=0.0, neginf=0.0)
        return (y_out.ravel() if is_1d else y_out), zf

    # High-efficiency fallback Direct Form II Transposed implementation
    y_out = np.zeros_like(x_2d, dtype=np.float64)
    zf = np.copy(zi)

    for ch in range(channels):
        x_ch = x_2d[:, ch].tolist()
        y_ch = list(x_ch)
        for s in range(num_sections):
            b0, b1, b2, _, a1, a2 = sos_2d[s]
            s1 = float(zf[s, 0, ch])
            s2 = float(zf[s, 1, ch])
            for n in range(frames):
                xn = y_ch[n]
                yn = b0 * xn + s1
                s1 = b1 * xn - a1 * yn + s2
                s2 = b2 * xn - a2 * yn
                y_ch[n] = yn
            zf[s, 0, ch] = s1
            zf[s, 1, ch] = s2
        y_out[:, ch] = y_ch

    y_out = np.nan_to_num(y_out, nan=0.0, posinf=0.0, neginf=0.0)
    return (y_out.ravel() if is_1d else y_out), zf
