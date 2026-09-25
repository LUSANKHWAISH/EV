"""Streaming musical attack detection, not a synthetic BPM clock."""
from collections import deque
import math

import numpy as np


class OnsetDetector:
    size = 1024
    hop = 512

    def __init__(self, rate):
        self.rate = rate
        self.window = np.hanning(self.size)
        freq = np.fft.rfftfreq(self.size, 1/rate)
        edges = [25,80,160,320,640,1280,2560,5120,10000,20000]
        self.indices = [np.flatnonzero((freq>=a)&(freq<b)) for a,b in zip(edges[:-1],edges[1:])]
        self.pending = None
        self.previous = np.zeros(len(self.indices))
        self.history = deque(maxlen=round(1.5*rate/self.hop))
        self.samples_seen = 0
        self.last_hit = -rate
        self.rms_average = 0.

    def process(self, block):
        """Return (sample offset within this block, strength, RMS) for new attacks.

        Every hop is examined, including the beginning of large decoder buffers.
        Offsets let the caller schedule decoded audio or timestamp captured audio.
        """
        block = np.nan_to_num(np.asarray(block,dtype=np.float32),nan=0.,posinf=0.,neginf=0.)
        if block.ndim==1: block=block[:,None]
        before = self.samples_seen
        self.samples_seen += len(block)
        self.pending = block.copy() if self.pending is None else np.concatenate((self.pending,block))
        hits = []
        while len(self.pending)>=self.size:
            frame = self.pending[:self.size]
            end_sample = self.samples_seen-len(self.pending)+self.size
            rms = float(np.sqrt(np.mean(frame**2)))
            mag = np.sqrt(np.mean(np.abs(np.fft.rfft(frame*self.window[:,None],axis=0))**2,axis=1))*2/self.window.sum()
            bands = np.array([float(np.max(mag[idx])) if len(idx) else 0. for idx in self.indices])
            spectrum = np.log1p(bands*30)
            flux = float(np.mean(np.maximum(0,spectrum-self.previous)))
            median = float(np.median(self.history)) if self.history else 0.
            deviation = float(np.median(np.abs(np.asarray(self.history)-median))) if self.history else 0.
            threshold = max(.012,median*1.8+deviation*2.5)
            refractory = (end_sample-self.last_hit)/self.rate >= .145
            if rms>.0015 and flux>threshold and refractory:
                strength = min(1.,.4+.25*flux/threshold)
                hits.append((end_sample-before,strength,rms))
                self.last_hit=end_sample
            self.previous=spectrum
            self.history.append(flux)
            self.rms_average += (rms-self.rms_average)*(1-math.exp(-self.hop/self.rate/.2))
            self.pending=self.pending[self.hop:]
        return hits


class BeatEnvelope:
    """Attack immediately, release quickly. No repeating or predicted pulses."""
    def __init__(self): self.value=0.

    def update(self, dt, hits, gain, active):
        if not active or gain<=0:
            self.value=0.
            return self.value
        self.value *= math.exp(-max(0,dt)/.115)
        for hit in hits:
            audible = min(1., math.sqrt(max(0.,hit['rms']*gain)/.02))
            self.value=max(self.value,hit['strength']*audible)
        if self.value<.002:self.value=0.
        return self.value
