import time

import numpy as np
import pytest

from music.analysis import AnalysisFrame, AnalysisWorker, analyze


def test_analysis_frame_is_immutable_and_backward_readable():
    frame = analyze(np.zeros(2048), 48000, source_id="player", generation=4, sequence=9)
    assert isinstance(frame, AnalysisFrame)
    assert frame.source_id == "player"
    assert frame.generation == 4
    assert frame.sequence == 9
    assert frame["rms"] == frame.rms == 0
    assert isinstance(frame.bands, tuple)
    assert isinstance(frame.waveform, tuple)
    with pytest.raises((AttributeError, TypeError)):
        frame.rms = 1


def test_worker_publishes_generation_and_monotonic_sequences():
    worker = AnalysisWorker()
    try:
        worker.push(np.sin(2 * np.pi * 750 * np.arange(2048) / 48000), 48000, source_id='player:2')
        until = time.monotonic() + 2
        while worker.latest() is None and time.monotonic() < until:
            time.sleep(.01)
        first = worker.latest()
        assert first is not None
        assert first.source_id == 'player:2'
        worker.push(np.zeros((2048, 2)), 48000, source_id='player:2')
        until = time.monotonic() + 2
        while worker.latest() is first and time.monotonic() < until:
            time.sleep(.01)
        second = worker.latest()
        assert second is not None
        assert second.sequence > first.sequence
        assert second.generation == first.generation
        old_generation = second.generation
        worker.reset()
        assert worker.latest() is None
        worker.push(np.zeros((2048, 2)), 48000, source_id='output:4')
        until = time.monotonic() + 2
        while worker.latest() is None and time.monotonic() < until:
            time.sleep(.01)
        third = worker.latest()
        assert third is not None
        assert third.generation > old_generation
        assert third.source_id == 'output:4'
    finally:
        worker.close()
