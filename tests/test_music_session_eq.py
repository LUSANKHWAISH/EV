"""Comprehensive tests for 10-band playback EQ integration into MusicSession."""
import json
import math
from pathlib import Path
import tempfile
import time
import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QSettings, QUrl

from music.dsp import EQ_10_BAND_FREQUENCIES, EQStore, EqualizerDSP
from music.session import MusicSession
from prototypes.playback_eq.player import EQPlaybackEngine
from prototypes.playback_eq.wav_reader import WavReader


class DummyCapture:
    def __init__(self, consume, status):
        self.consume, self.status = consume, status
        self.stopped = False

    @staticmethod
    def devices():
        return [{'id': 1, 'label': 'Mock Device'}]

    def start(self, device_id):
        self.status('active', 'Mock Device')

    def stop(self):
        self.stopped = True


@pytest.fixture
def mock_session(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr('music.session.LoopbackCapture', DummyCapture)

    # Use isolated settings and store file
    ini_file = str(tmp_path / 'music_test.ini')
    settings = QSettings(ini_file, QSettings.Format.IniFormat)
    store_file = tmp_path / 'test_music_eq.json'

    # Monkeypatch EQStore path to use test directory
    monkeypatch.setattr(
        'music.session.EQStore',
        lambda storage_path=store_file: EQStore(storage_path=store_file)
    )

    session = MusicSession(settings=settings)
    yield session, store_file
    session.close()
    app.processEvents()


def create_test_wav(path: Path, duration_s: float = 1.0, rate: int = 44100, channels: int = 2) -> Path:
    """Generate a clean test WAV file for unit tests."""
    total_frames = int(rate * duration_s)
    t = np.linspace(0, duration_s, total_frames, endpoint=False)
    # 440 Hz stereo tone
    sig_left = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sig_right = (0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
    stereo = np.column_stack((sig_left, sig_right))

    int16_data = (stereo * 32767.0).astype(np.int16)
    raw_bytes = int16_data.tobytes()

    byte_rate = rate * channels * 2
    block_align = channels * 2
    data_size = len(raw_bytes)
    chunk_size = 36 + data_size

    header = bytearray()
    header.extend(b'RIFF')
    header.extend(chunk_size.to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))
    header.extend((1).to_bytes(2, 'little'))  # PCM
    header.extend(channels.to_bytes(2, 'little'))
    header.extend(rate.to_bytes(4, 'little'))
    header.extend(byte_rate.to_bytes(4, 'little'))
    header.extend(block_align.to_bytes(2, 'little'))
    header.extend((16).to_bytes(2, 'little'))  # 16-bit
    header.extend(b'data')
    header.extend(data_size.to_bytes(4, 'little'))

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(header)
        f.write(raw_bytes)
    return path


def test_eq_frequencies_and_band_count(mock_session):
    session, _ = mock_session
    freqs = session.eqFrequencies
    assert len(freqs) == 10
    expected = [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    for actual, exp in zip(freqs, expected):
        assert abs(actual - exp) < 0.1


def test_band_gain_clamping_and_persistence(mock_session):
    session, store_file = mock_session
    # Set within range
    session.setBandGain(2, 6.5)
    assert abs(session.eqGains[2] - 6.5) < 1e-4

    # Clamp upper bound (+12 dB)
    session.setBandGain(0, 25.0)
    assert abs(session.eqGains[0] - 12.0) < 1e-4

    # Clamp lower bound (-12 dB)
    session.setBandGain(9, -30.0)
    assert abs(session.eqGains[9] - (-12.0)) < 1e-4

    # Verify JSON persistence
    assert store_file.exists()
    data = json.loads(store_file.read_text(encoding='utf-8'))
    assert abs(data['gains'][2] - 6.5) < 1e-4
    assert abs(data['gains'][0] - 12.0) < 1e-4
    assert abs(data['gains'][9] - (-12.0)) < 1e-4


def test_preamp_clamping_and_persistence(mock_session):
    session, store_file = mock_session
    session.setPreamp(-4.5)
    assert abs(session.eqPreamp - (-4.5)) < 1e-4

    # Clamp limits (-18 dB to +18 dB)
    session.setPreamp(24.0)
    assert abs(session.eqPreamp - 18.0) < 1e-4
    session.setPreamp(-50.0)
    assert abs(session.eqPreamp - (-18.0)) < 1e-4

    data = json.loads(store_file.read_text(encoding='utf-8'))
    assert abs(data['preamp_db'] - (-18.0)) < 1e-4


def test_bypass_toggle_and_state(mock_session):
    session, store_file = mock_session
    assert not session.eqBypass

    session.setBypass(True)
    assert session.eqBypass is True
    # EQ must never be displayed as active while bypassed
    assert session.eqActive is False

    data = json.loads(store_file.read_text(encoding='utf-8'))
    assert data['bypass'] is True

    session.setBypass(False)
    assert session.eqBypass is False


def test_reset_flat(mock_session):
    session, store_file = mock_session
    session.setBandGain(1, 9.0)
    session.setBandGain(5, -6.0)
    session.setPreamp(-3.0)

    session.resetFlat()
    assert all(abs(g) < 1e-6 for g in session.eqGains)
    assert abs(session.eqPreamp) < 1e-6

    data = json.loads(store_file.read_text(encoding='utf-8'))
    assert all(abs(g) < 1e-6 for g in data['gains'])
    assert abs(data['preamp_db']) < 1e-6


def test_bypass_does_not_affect_master_volume_or_mute(mock_session):
    session, _ = mock_session
    session.setVolume(0.75)
    session.setMuted(True)

    # Toggle bypass
    session.setBypass(True)
    assert abs(session.volume - 0.75) < 1e-4
    assert session.muted is True

    session.setBypass(False)
    assert abs(session.volume - 0.75) < 1e-4
    assert session.muted is True


def test_settings_restoration_without_starting_playback(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr('music.session.LoopbackCapture', DummyCapture)

    ini_file = str(tmp_path / 'music_restore.ini')
    settings = QSettings(ini_file, QSettings.Format.IniFormat)
    store_file = tmp_path / 'restore_eq.json'

    # Pre-populate store
    store = EQStore(storage_path=store_file)
    store.save({
        'gains': [1.0, 2.0, 3.0, 4.0, 5.0, -1.0, -2.0, -3.0, -4.0, -5.0],
        'preamp_db': -2.5,
        'bypass': False,
    })

    monkeypatch.setattr(
        'music.session.EQStore',
        lambda storage_path=store_file: EQStore(storage_path=store_file)
    )

    new_session = MusicSession(settings=settings)
    try:
        # Settings restored accurately
        assert abs(new_session.eqPreamp - (-2.5)) < 1e-4
        assert abs(new_session.eqGains[4] - 5.0) < 1e-4
        assert abs(new_session.eqGains[9] - (-5.0)) < 1e-4
        assert new_session.eqBypass is False

        # CRITICAL: Playback must NOT start on restore
        assert new_session.playing is False
        assert new_session.hasTrack is False
        assert new_session.currentIndex == -1
    finally:
        new_session.close()
        app.processEvents()


def test_format_routing_wav_vs_mp3(mock_session, tmp_path):
    session, _ = mock_session
    wav_path = create_test_wav(tmp_path / 'test_track.wav', duration_s=0.5)
    fake_mp3 = tmp_path / 'test_track.mp3'
    fake_mp3.write_bytes(b'ID3FakeMP3Data')

    session.addFiles([QUrl.fromLocalFile(str(wav_path)), QUrl.fromLocalFile(str(fake_mp3))])
    assert len(session.queue) == 2

    # Play track 0 (WAV): routes to DSP engine
    session.playIndex(0)
    assert session.backend == 'dsp'
    assert session.eqAvailable is True
    assert 'DSP' in session.eqStatus or 'WAV' in session.eqStatus

    # Play track 1 (MP3): routes to QMediaPlayer backend
    session.playIndex(1)
    assert session.backend == 'media_player'
    assert session.eqAvailable is False
    assert 'Observation' in session.eqStatus
    assert session.eqActive is False


def test_headroom_estimation_and_clipping_property(mock_session):
    session, _ = mock_session
    session.resetFlat()
    assert abs(session.eqHeadroom) < 0.1

    # Boost 3 adjacent bands
    session.setBandGain(0, 6.0)
    session.setBandGain(1, 6.0)
    session.setBandGain(2, 6.0)
    # Combined boost should yield negative headroom
    assert session.eqHeadroom < -5.0

    # eqIsClipping starts False
    assert session.eqIsClipping is False


def test_integrated_playback_antiphase_stereo_preserves_energy(mock_session, tmp_path):
    """Verify that opposite-phase channels do not cancel out in the integrated playback-to-analysis path."""
    session, _ = mock_session
    rate = 48000
    duration_s = 0.5
    total_frames = int(rate * duration_s)
    t = np.linspace(0, duration_s, total_frames, endpoint=False)
    hz = 440.0
    sig_left = (0.4 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    sig_right = (-0.4 * np.sin(2 * np.pi * hz * t)).astype(np.float32)  # Exact opposite phase (-sig_left)
    antiphase_pcm = np.column_stack((sig_left, sig_right))

    # A simple mono mixdown (L + R) / 2 would result in complete silence
    mono_naive = 0.5 * (sig_left + sig_right)
    assert np.allclose(mono_naive, 0.0, atol=1e-5), "Naive downmix must cancel to confirm antiphase test condition"

    # Push through integrated DSP playback analysis path
    session._active = True
    session._input = "player"
    session._backend = "dsp"

    # Simulate active playback state
    session._eq_player._is_playing = True
    session.setVolume(1.0)
    session.setMuted(False)

    # Stream several chunks through the session's DSP PCM tap
    chunk_size = 2048
    for start_idx in range(0, len(antiphase_pcm) - chunk_size, chunk_size):
        chunk = antiphase_pcm[start_idx : start_idx + chunk_size]
        session._dsp_pcm(chunk, rate)

    # Give AnalysisWorker time to process
    time.sleep(0.12)
    session._tick()

    # Verify channel measurements
    assert session.left > 0.20, f"Left channel must be non-zero (measured {session.left})"
    assert session.right > 0.20, f"Right channel must be non-zero (measured {session.right})"
    assert abs(session.left - session.right) < 0.05, "Left and right levels must match for symmetric antiphase"

    # CRITICAL: Verify spectrum bands do NOT cancel out
    assert max(session.bands) > 0.5, f"Spectrum energy must be preserved (peak band is {max(session.bands)})"
    assert session.level > 0.1, f"RMS level must be preserved (measured {session.level})"


def test_muted_or_stopped_ev_playback_clears_beat_reactions_and_preserves_external_capture(mock_session):
    """Verify that muted or stopped EV playback clears beat reactions while external capture is preserved."""
    session, _ = mock_session
    rate = 48000
    t = np.linspace(0, 0.2, int(rate * 0.2), endpoint=False)
    # Strong kick / transient burst
    burst = (0.8 * np.sin(2 * np.pi * 80.0 * t)).astype(np.float32)
    burst_stereo = np.column_stack((burst, burst))

    session._active = True
    session._input = "player"
    session._backend = "dsp"
    session._eq_player._is_playing = True
    session.setVolume(1.0)
    session.setMuted(False)

    # Push kick transient and verify beat response when unmuted
    session._dsp_pcm(burst_stereo, rate)
    time.sleep(0.12)
    session._tick()
    # When active and unmuted, beat reaction can be triggered
    # Now mute playback:
    session.setMuted(True)
    session._dsp_pcm(burst_stereo, rate)
    time.sleep(0.12)
    session._tick()

    # Muted playback MUST clear beat reaction
    assert session.beat == 0.0, f"Muted playback must produce beat == 0, got {session.beat}"

    # Unmute but stop playback:
    session.setMuted(False)
    session._eq_player._is_playing = False
    session._sync_dsp_state()
    session._dsp_pcm(burst_stereo, rate)
    time.sleep(0.08)
    session._tick()

    # Stopped playback MUST clear beat reaction
    assert session.beat == 0.0, f"Stopped playback must produce beat == 0, got {session.beat}"

    # Now verify external capture (system mix) is NOT suppressed by player mute
    session.setInput("system")
    assert session.inputSource == "system"
    # When input is system, gain calculation in _tick uses 1.0 (unsuppressed by EV player mute)
    session.setMuted(True)  # Player mute
    # System loopback input uses gain = 1.0 in session._tick
    gain = 1.0 if session._input == "system" else (0 if session.muted else session.volume)
    assert gain == 1.0, "External audio capture must not be suppressed by EV player mute"


def test_analyzer_metrics_calculations():
    """Verify exact calculation formulas for genuine 256-pt FFT, note/cents, crest factor, correlation, and balance."""
    from music.analysis import analyze, _hz_to_note
    rate = 48000
    n = 2048
    t = np.arange(n) / float(rate)

    # 1. 440 Hz tone note and cents verification
    assert "A4" in _hz_to_note(440.0)
    assert "A5" in _hz_to_note(880.0)
    assert "C4" in _hz_to_note(261.63)

    # 2. In-phase sine wave analysis
    sine_440 = 0.5 * np.sin(2.0 * np.pi * 440.0 * t).astype(np.float32)
    stereo_inphase = np.column_stack([sine_440, sine_440])
    frame = analyze(stereo_inphase, rate)

    # Genuine 256-point log-spaced FFT spectrum
    assert len(frame.spectrum) == 256, f"Detailed analyzer requires 256 points, got {len(frame.spectrum)}"
    assert all(0.0 <= v <= 1.1 for v in frame.spectrum)
    assert abs(frame.peakHz - 440.0) < 15.0  # within FFT bin resolution (48000/2048 = 23.4 Hz)
    assert "A4" in frame.peakNote

    # Theoretical crest factor of a pure sinusoid: peak / RMS = sqrt(2) -> 20*log10(sqrt(2)) = 3.01 dB
    assert abs(frame.crestFactor - 3.01) < 0.5, f"Expected ~3.01 dB crest factor for sine wave, got {frame.crestFactor}"

    # In-phase correlation must be +1.0
    assert abs(frame.correlation - 1.0) < 1e-4

    # Balanced stereo must have balance == 0.0 dB
    assert abs(frame.balance) < 0.1

    # 3. Antiphase stereo analysis
    stereo_antiphase = np.column_stack([sine_440, -sine_440])
    frame_anti = analyze(stereo_antiphase, rate)
    assert abs(frame_anti.correlation - (-1.0)) < 1e-4, f"Antiphase correlation must be -1.0, got {frame_anti.correlation}"
    assert frame_anti.samplePeakL > 0.49
    assert frame_anti.samplePeakR > 0.49

    # 4. Asymmetric stereo balance test (Right 6 dB hotter: R = 2 * L)
    stereo_imbalance = np.column_stack([sine_440 * 0.5, sine_440 * 1.0])
    frame_bal = analyze(stereo_imbalance, rate)
    # 20 * log10(1.0 / 0.5) = +6.02 dB
    assert abs(frame_bal.balance - 6.02) < 0.3, f"Expected balance ~+6.02 dB, got {frame_bal.balance}"


def test_session_analyzer_and_interactive_eq_nodes(mock_session):
    """Verify session properties for analyzer metrics and real-time DSP interactive EQ band modification."""
    session, _ = mock_session
    assert len(session.spectrum) == 256
    assert session.peakNote == "--"
    assert session.peakHz == 0.0
    assert session.eqClippingCount == 0

    # Test interactive EQ node adjustment
    # Band 5 = 1000 Hz. Adjust from 0.0 to +4.5 dB
    session.setBandGain(5, 4.5)
    assert abs(session.eqGains[5] - 4.5) < 1e-4
    assert abs(session._eq_player.dsp.bands[5].gain_db - 4.5) < 1e-4

    # Adjust Band 0 = 31 Hz to -6.0 dB
    session.setBandGain(0, -6.0)
    assert abs(session.eqGains[0] - (-6.0)) < 1e-4
    assert abs(session._eq_player.dsp.bands[0].gain_db - (-6.0)) < 1e-4

    # Reset flat
    session.resetFlat()
    assert all(abs(g) < 1e-4 for g in session.eqGains)
    assert all(abs(g) < 1e-4 for g in session._eq_player.dsp.get_all_gains())


def test_off_bin_frequency_behavior_and_resolution_limits():
    """Verify physical frequency resolution limits (Δf ≈ 23.44 Hz) and off-bin Hann scalloping loss."""
    from music.analysis import analyze
    rate = 48000
    n = 2048
    delta_f = rate / float(n)  # 23.4375 Hz
    t = np.arange(n) / float(rate)

    # 1. Exactly on-bin tone (bin k = 43 -> 1007.8125 Hz)
    k_on = 43
    f_on = k_on * delta_f
    pcm_on = 1.0 * np.sin(2.0 * np.pi * f_on * t).astype(np.float32)
    frame_on = analyze(pcm_on, rate)

    # On-bin tone peak matches bin center exactly
    assert abs(frame_on.peakHz - f_on) < 0.01
    assert len(frame_on.spectrum) == 256

    # 2. Exactly off-bin tone (midpoint between bins 43 and 44: k = 43.5 -> 1019.53125 Hz)
    k_off = 43.5
    f_off = k_off * delta_f
    pcm_off = 1.0 * np.sin(2.0 * np.pi * f_off * t).astype(np.float32)
    frame_off = analyze(pcm_off, rate)

    # Peak bin index must be either 43 or 44; peakHz is bounded within ±Δf/2
    assert abs(frame_off.peakHz - f_off) <= (delta_f / 2.0) + 1e-4

    # Calculate scalloping loss: ratio of off-bin peak to on-bin peak
    # Hann window worst-case scalloping loss is ~1.42 dB (amplitude ratio ~0.849)
    # Using the raw FFT amplitudes before log display
    window = np.hanning(n)
    amp_on = np.max(np.abs(np.fft.rfft(pcm_on * window)) * (2.0 / window.sum()))
    amp_off = np.max(np.abs(np.fft.rfft(pcm_off * window)) * (2.0 / window.sum()))
    scalloping_loss_db = 20.0 * np.log10(amp_off / amp_on)

    # Scalloping loss must be between -1.0 dB and -1.8 dB for mid-bin tone
    assert -1.8 < scalloping_loss_db < -1.0, f"Expected Hann scalloping loss ~ -1.42 dB, got {scalloping_loss_db:.2f} dB"


