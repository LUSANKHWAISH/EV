"""Measured signal correctness and bounded lifecycle contracts."""
import time

import numpy as np

from music.analysis import AnalysisWorker, analyze


def tone(hz, rate=48000, count=2048, gain=.5):
    return gain*np.sin(2*np.pi*hz*np.arange(count)/rate)


def test_known_tone_frequency_and_level():
    pcm=tone(750)
    result=analyze(pcm,48000)
    assert abs(result['peakHz']-750)<24
    assert abs(result['rms']-.5/2**.5)<.001
    assert abs(result['peak']-.5)<.001
    assert result['mid']>result['bass']*100


def test_antiphase_stereo_does_not_disappear():
    pcm=tone(750)
    result=analyze(np.column_stack((pcm,-pcm)),48000)
    assert result['rms']>.35
    assert max(result['bands'])>.8


def test_left_only_stereo_is_measured_separately():
    pcm=tone(750)
    result=analyze(np.column_stack((pcm,np.zeros_like(pcm))),48000)
    assert result['left']>.35
    assert result['right']==0


def test_silence_has_no_manufactured_activity():
    result=analyze(np.zeros((2048,2)),44100)
    assert max(result['bands'])==0
    assert result['rms']==result['peak']==result['bass']==result['treble']==0


def test_low_and_high_energy_stay_in_their_bands():
    low=analyze(tone(93.75),48000)
    high=analyze(tone(6000),48000)
    assert low['bass']>low['treble']*100
    assert high['treble']>high['bass']*100


def test_nonfinite_pcm_cannot_poison_visual_state():
    pcm=np.zeros(2048);pcm[10]=np.nan;pcm[20]=np.inf
    result=analyze(pcm,48000)
    assert np.isfinite(result['bands']).all()
    assert result['rms']==0


def test_worker_reset_discards_old_source_and_closes():
    worker=AnalysisWorker()
    try:
        worker.push(tone(750),48000)
        until=time.monotonic()+2
        while worker.latest() is None and time.monotonic()<until: time.sleep(.01)
        assert worker.latest()['peakHz']==750
        worker.reset()
        assert worker.latest() is None
        worker.push(np.zeros(2048),48000)
        until=time.monotonic()+2
        while worker.latest() is None and time.monotonic()<until: time.sleep(.01)
        assert worker.latest()['rms']==0
    finally:
        worker.close()
    assert not worker.thread.is_alive()


def test_capture_queue_has_a_hard_bound():
    worker=AnalysisWorker()
    try:
        with worker._condition:
            for _ in range(20): worker.push(np.zeros((2048,2)),48000)
            assert len(worker._queue)==8
            assert worker.dropped==12
    finally:
        worker.close()
