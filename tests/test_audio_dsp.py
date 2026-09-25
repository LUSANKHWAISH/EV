"""Unit tests for Biquad filter calculations, EqualizerDSP chain, and acceptance checks."""
from __future__ import annotations

import math
import numpy as np
import pytest

from music.dsp.biquad import apply_sos_filter, peaking_sos, sos_freq_response
from music.dsp.chain import EQBand, EqualizerDSP


class TestBiquadSOS:
    """Verifies RBJ peaking filter coefficients, constraints, and frequency response."""

    def test_invalid_parameters_raise_value_error(self):
        with pytest.raises(ValueError, match="positive sample rate"):
            peaking_sos(rate=0, hz=1000, gain_db=6.0, q=1.0)
        with pytest.raises(ValueError, match="Finite parameters"):
            peaking_sos(rate=48000, hz=float("nan"), gain_db=6.0, q=1.0)
        with pytest.raises(ValueError, match="Finite parameters"):
            peaking_sos(rate=48000, hz=1000, gain_db=float("inf"), q=1.0)

    def test_parameter_clamping_bounds(self):
        # hz clamped to [20, 0.45*rate]
        sos_low = peaking_sos(rate=48000, hz=5.0, gain_db=6.0, q=1.0)
        sos_high = peaking_sos(rate=48000, hz=30000.0, gain_db=6.0, q=1.0)
        assert np.all(np.isfinite(sos_low))
        assert np.all(np.isfinite(sos_high))

    def test_zero_gain_is_exact_unity(self):
        sos_zero = peaking_sos(rate=48000, hz=1000.0, gain_db=0.0, q=1.0)
        # Should return [1, 0, 0, 1, 0, 0]
        np.testing.assert_allclose(sos_zero, [1.0, 0.0, 0.0, 1.0, 0.0, 0.0], atol=1e-12)

    def test_boost_and_cut_frequency_response(self):
        fs = 48000.0
        f0 = 1000.0

        # +6 dB Boost
        sos_boost = peaking_sos(rate=fs, hz=f0, gain_db=6.0, q=1.0)
        _, db_boost = sos_freq_response(sos_boost, [100.0, 1000.0, 10000.0], rate=fs)
        assert db_boost[1] == pytest.approx(6.0, abs=0.05)
        assert db_boost[0] < 0.2  # Far from center should be near 0 dB
        assert db_boost[2] < 0.2

        # -6 dB Cut
        sos_cut = peaking_sos(rate=fs, hz=f0, gain_db=-6.0, q=1.0)
        _, db_cut = sos_freq_response(sos_cut, [100.0, 1000.0, 10000.0], rate=fs)
        assert db_cut[1] == pytest.approx(-6.0, abs=0.05)
        assert abs(db_cut[0]) < 0.2
        assert abs(db_cut[2]) < 0.2


class TestEqualizerDSPChain:
    """Verifies EqualizerDSP processing, bypass tolerance, silence, and channel isolation."""

    def test_bypass_matches_unprocessed_pcm_within_tolerance(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.set_eq_band(hz=1000.0, gain_db=12.0, q=1.0)
        dsp.set_bypass(True)

        np.random.seed(42)
        x = np.random.randn(2048, 2).astype(np.float32) * 0.2

        # Allow transition to settle if any
        _ = dsp.process(x)
        y = dsp.process(x)

        # Bypass must pass unprocessed audio exactly within float32 tolerance
        np.testing.assert_allclose(y, x, atol=1e-5)

    def test_silence_remains_strictly_silent(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.set_eq_band(hz=1000.0, gain_db=6.0, q=1.0)

        silence = np.zeros((1024, 2), dtype=np.float32)
        y = dsp.process(silence)

        assert np.all(y == 0.0)
        assert dsp.peak_dbfs == -120.0
        assert dsp.dynamic_headroom_db == 120.0
        assert dsp.headroom_db == pytest.approx(-6.0, abs=0.1)

    def test_output_contains_no_nan_or_inf(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.set_eq_band(hz=2000.0, gain_db=18.0, q=5.0)

        # Impulse signal
        impulse = np.zeros((1024, 2), dtype=np.float32)
        impulse[0, :] = 1.0

        y = dsp.process(impulse)
        assert np.all(np.isfinite(y))
        assert not np.any(np.isnan(y))
        assert not np.any(np.isinf(y))

    def test_channel_separation_and_stereo_independence(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.set_eq_band(hz=1000.0, gain_db=6.0, q=1.0)

        fs = 48000
        t = np.arange(1024) / fs
        tone = (0.2 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)

        # 1. Left-only signal
        x_left = np.column_stack([tone, np.zeros_like(tone)])
        y_left = dsp.process(x_left)

        assert np.max(np.abs(y_left[:, 0])) > 0.1  # Left channel has signal
        assert np.all(y_left[:, 1] == 0.0)         # Right channel is strictly silent

        # 2. Right-only signal
        dsp.reset_state()
        x_right = np.column_stack([np.zeros_like(tone), tone])
        y_right = dsp.process(x_right)

        assert np.all(y_right[:, 0] == 0.0)        # Left channel is strictly silent
        assert np.max(np.abs(y_right[:, 1])) > 0.1 # Right channel has signal

    def test_smooth_transition_prevents_discontinuous_clicks(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=1)
        fs = 48000
        t = np.arange(2048) / fs
        sine = (0.3 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)

        # Block 1: Flat
        _ = dsp.process(sine[:1024])

        # Drastic parameter jump: +12 dB to -12 dB
        dsp.set_eq_band(hz=1000.0, gain_db=-12.0, q=2.0)
        # Block 2: Transition block
        y_trans = dsp.process(sine[1024:])

        # Verify no abrupt step / discontinuity between adjacent samples
        diffs = np.abs(np.diff(y_trans))
        assert np.all(diffs < 0.1), "Sample differences must remain bounded without pops/clicks"

    def test_clipping_detection_and_headroom_handling(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.set_preamp_db(6.0)  # +6 dB doubles amplitude

        # Input with peak 0.8 -> preamp scales to 1.6 (> 1.0 full scale)
        hot_signal = np.full((512, 2), 0.8, dtype=np.float32)
        y = dsp.process(hot_signal)

        # Clipping must be detected and counted
        assert dsp.clipped_samples > 0
        assert dsp.peak_dbfs >= 0.0
        # Output must be clamped within [-1.0, 1.0] for hardware safety
        assert np.all(np.abs(y) <= 1.0)

    def test_all_10_band_center_frequencies_and_responses(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        assert len(dsp.bands) == 10
        expected_centers = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]

        for i, center in enumerate(expected_centers):
            assert abs(dsp.bands[i].hz - center) < 0.1
            # Test individual +6 dB boost
            dsp.reset_flat(force_immediate=True)
            dsp.set_band_gain(i, 6.0, force_immediate=True)
            w, resp = sos_freq_response(dsp._current_sos, [center], rate=48000)
            assert resp[0] == pytest.approx(6.0, abs=0.15), f"Band {center} Hz should boost +6 dB"

    def test_bandwidth_and_q_factor_definition(self):
        # Q = 1.4142 corresponds to standard 1-octave bandwidth
        # At f0/sqrt(2) and f0*sqrt(2) for +6 dB peak, gain should be ~+3 dB (+3 dB point)
        sos = peaking_sos(rate=48000, hz=1000.0, gain_db=6.0, q=1.4142)
        f_low = 1000.0 / (2.0 ** 0.5)
        f_high = 1000.0 * (2.0 ** 0.5)
        _, resp = sos_freq_response(sos, [f_low, 1000.0, f_high], rate=48000)
        assert resp[1] == pytest.approx(6.0, abs=0.05)
        # At half-power (3 dB below peak in linear gain, ~3 dB boost)
        assert resp[0] == pytest.approx(3.0, abs=0.3)
        assert resp[2] == pytest.approx(3.0, abs=0.3)

    def test_combined_boost_headroom_estimation(self):
        dsp = EqualizerDSP(sample_rate=48000, channels=2)
        dsp.reset_flat(force_immediate=True)
        assert abs(dsp.headroom_db) < 0.1

        # Boost 3 consecutive bands by +6 dB
        dsp.set_band_gain(4, 6.0, force_immediate=True)  # 500 Hz
        dsp.set_band_gain(5, 6.0, force_immediate=True)  # 1 kHz
        dsp.set_band_gain(6, 6.0, force_immediate=True)  # 2 kHz

        peak_boost = dsp.estimate_peak_gain_db()
        # Due to 1-octave overlap, combined peak is > 6 dB (typically ~8.16 dB)
        assert peak_boost > 7.5
        assert dsp.headroom_db < -7.5

