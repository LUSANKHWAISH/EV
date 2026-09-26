"""Bounded, source-tagged PCM analysis off the GUI/capture threads."""
from collections import deque
from dataclasses import dataclass
import math
import threading
import time

import numpy as np
from .onsets import OnsetDetector


@dataclass(frozen=True)
class AnalysisFrame:
    source_id: str
    generation: int
    sequence: int
    presentation_time: float
    bands: tuple
    waveform: tuple
    rms: float
    peak: float
    left: float
    right: float
    bass: float
    mid: float
    treble: float
    peakHz: float
    timestamp: float
    spectrum: tuple = ()
    peakNote: str = "--"
    crestFactor: float = 0.0
    correlation: float = 1.0
    balance: float = 0.0
    samplePeakL: float = 0.0
    samplePeakR: float = 0.0

    def __getitem__(self, key):
        return getattr(self, key)


def _hz_to_note(hz: float) -> str:
    """Calculate musical note name and cents deviation from frequency."""
    if hz < 20.0 or not np.isfinite(hz):
        return "--"
    midi = 69.0 + 12.0 * math.log2(hz / 440.0)
    nearest = int(round(midi))
    cents = int(round((midi - nearest) * 100))
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    note = names[nearest % 12]
    octave = (nearest // 12) - 1
    cents_str = f"+{cents}" if cents > 0 else (f"{cents}" if cents < 0 else "0")
    return f"{note}{octave} {cents_str}ct"


def analyze(pcm, rate, count=64, *, source_id='audio', generation=0, sequence=0, presentation_time=None):
    """Sample peak and Hann-window spectrum, taking channel energy before mixing.
    
    FFT size: len(pcm) (typically 2048 samples).
    Window: Hann window with coherent gain normalization (2 / sum(window)).
    """
    pcm = np.nan_to_num(np.asarray(pcm, dtype=np.float32), nan=0., posinf=0., neginf=0.)
    if pcm.ndim == 1:
        pcm = pcm[:, None]
    n = len(pcm)
    window = np.hanning(n)
    amplitudes = np.abs(np.fft.rfft(pcm * window[:, None], axis=0)) * (2.0 / window.sum())
    amplitude = np.sqrt(np.mean(amplitudes ** 2, axis=1))
    freq = np.fft.rfftfreq(n, 1.0 / rate)
    db = 20.0 * np.log10(np.maximum(amplitude, 1e-6))

    # Standard 64-band visualizer display
    edges = np.geomspace(25, min(20000, rate / 2), count + 1)
    bands = []
    for low, high in zip(edges[:-1], edges[1:]):
        indices = (freq >= low) & (freq < high)
        value = float(np.max(db[indices])) if indices.any() else float(np.interp((low*high)**.5, freq, db))
        bands.append(float(np.clip((value + 80.0) / 80.0, 0.0, 1.0)))

    # Genuine high-resolution spectrum (256 log-spaced points from 20 Hz to 20 kHz)
    eval_freqs = np.geomspace(20, min(20000, rate / 2), 256)
    spectrum_db = np.interp(eval_freqs, freq, db)
    spectrum_norm = tuple(float(np.clip((v + 80.0) / 80.0, 0.0, 1.1)) for v in spectrum_db)

    rms_per_channel = np.sqrt(np.mean(pcm ** 2, axis=0))
    rms_total = float(np.sqrt(np.mean(rms_per_channel ** 2)))

    sample_peak_l = float(np.max(np.abs(pcm[:, 0]))) if pcm.shape[1] > 0 else 0.0
    sample_peak_r = float(np.max(np.abs(pcm[:, -1]))) if pcm.shape[1] > 0 else 0.0
    sample_peak_total = max(sample_peak_l, sample_peak_r)

    # Crest factor in decibels
    crest_factor = float(20.0 * math.log10(max(sample_peak_total, 1e-5) / max(rms_total, 1e-5)))

    # Stereo phase correlation (-1.0 antiphase to +1.0 in-phase mono)
    if pcm.shape[1] >= 2:
        l = pcm[:, 0]
        r = pcm[:, 1]
        denom = float(np.sqrt(np.sum(l**2) * np.sum(r**2)))
        correlation = float(np.clip(np.sum(l * r) / denom, -1.0, 1.0)) if denom > 1e-6 else 0.0
    else:
        correlation = 1.0

    # Stereo balance in decibels
    bal_r = rms_per_channel[-1] if len(rms_per_channel) > 1 else rms_per_channel[0]
    bal_l = rms_per_channel[0]
    balance_db = float(np.clip(20.0 * math.log10(max(bal_r, 1e-5) / max(bal_l, 1e-5)), -12.0, 12.0))

    def energy(low, high):
        mask = (freq >= low) & (freq < high)
        return float(np.sqrt(np.sum(amplitude[mask]**2) / 3))

    peak_bin_hz = float(freq[1 + np.argmax(amplitude[1:])])
    peak_note_str = _hz_to_note(peak_bin_hz)

    return AnalysisFrame(
        source_id=str(source_id), generation=int(generation), sequence=int(sequence),
        presentation_time=time.monotonic() if presentation_time is None else float(presentation_time),
        bands=tuple(bands),
        waveform=tuple(float(value) for value in pcm[np.linspace(0, n-1, 160).astype(int), 0]),
        rms=rms_total, peak=sample_peak_total,
        left=float(rms_per_channel[0]), right=float(rms_per_channel[-1]),
        bass=energy(25, 250), mid=energy(250, 4000), treble=energy(4000, 20000),
        peakHz=peak_bin_hz, timestamp=time.monotonic(),
        spectrum=spectrum_norm,
        peakNote=peak_note_str,
        crestFactor=crest_factor,
        correlation=correlation,
        balance=balance_db,
        samplePeakL=sample_peak_l,
        samplePeakR=sample_peak_r,
    )


class AnalysisWorker:
    def __init__(self):
        self._condition = threading.Condition()
        self._queue = deque(maxlen=8)
        self._generation = 0
        self._sequence = 0
        self._latest = None
        self._onsets = deque(maxlen=64)
        self._running = True
        self.dropped = 0
        self.processed = 0
        self.thread = threading.Thread(target=self._run, name='EV-MusicAnalysis', daemon=True)
        self.thread.start()

    def reset(self):
        with self._condition:
            self._generation += 1
            self._queue.clear()
            self._latest = None
            self._onsets.clear()

    def push(self, pcm, rate, start_time=None, *, source_id='audio'):
        if not len(pcm):
            return
        with self._condition:
            if not self._running:
                return
            if len(self._queue) == self._queue.maxlen:
                self.dropped += 1
            # Capture timestamps refer to audio already rendered; decoder taps
            # provide a start timestamp for the buffer they are about to play.
            end = time.monotonic()
            block=np.asarray(pcm,dtype=np.float32)[-8192:].copy()
            start=end-len(block)/rate if start_time is None else start_time
            self._queue.append((self._generation,block,int(rate),start,str(source_id)))
            self._condition.notify()

    def latest(self):
        with self._condition:
            return self._latest

    def take_onsets(self, now):
        with self._condition:
            due=[hit for hit in self._onsets if 0<=now-hit['time']<.25]
            self._onsets=deque((hit for hit in self._onsets if hit['time']>now),maxlen=64)
            return due

    def _run(self):
        previous = None
        samples = None
        detector = None
        source_id = 'audio'
        while True:
            with self._condition:
                self._condition.wait_for(lambda:not self._running or self._queue)
                if not self._running:
                    return
                generation, block, rate, start, source_id = self._queue.popleft()
            if block.ndim == 1:
                block = block[:, None]
            identity = (generation, rate, block.shape[1])
            if identity != previous:
                samples = block
                previous = identity
                detector = OnsetDetector(rate)
            else:
                samples = np.concatenate((samples, block))[-8192:]
            hits=detector.process(block)
            frame = analyze(samples[-2048:], rate, source_id=source_id, generation=generation) if len(samples)>=2048 else None
            with self._condition:
                if generation == self._generation:
                    for offset,strength,rms in hits:
                        self._onsets.append({'time':start+offset/rate,'strength':strength,'rms':rms})
                    if frame is not None:
                        self._sequence += 1
                        self._latest = AnalysisFrame(
                            source_id=frame.source_id,
                            generation=frame.generation,
                            sequence=self._sequence,
                            presentation_time=frame.presentation_time,
                            bands=frame.bands,
                            waveform=frame.waveform,
                            rms=frame.rms,
                            peak=frame.peak,
                            left=frame.left,
                            right=frame.right,
                            bass=frame.bass,
                            mid=frame.mid,
                            treble=frame.treble,
                            peakHz=frame.peakHz,
                            timestamp=frame.timestamp,
                            spectrum=frame.spectrum,
                            peakNote=frame.peakNote,
                            crestFactor=frame.crestFactor,
                            correlation=frame.correlation,
                            balance=frame.balance,
                            samplePeakL=frame.samplePeakL,
                            samplePeakR=frame.samplePeakR,
                        )
                        self.processed += 1

    def close(self):
        with self._condition:
            self._running = False
            self._queue.clear()
            self._condition.notify()
        self.thread.join(timeout=2)
