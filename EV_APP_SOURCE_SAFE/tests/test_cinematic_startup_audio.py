"""Startup audio contracts with fake output: never touches speakers or user settings."""
import json
from pathlib import Path
import wave

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QObject, QSettings, Signal
from PySide6.QtMultimedia import QSoundEffect
from PySide6.QtGui import QWindow

from prototypes.cinematic_v4.startup_audio import ASSETS, StartupAudio


class Model(QObject):
    frameChanged = Signal()
    settingsChanged = Signal()
    listeningRequested = Signal()
    launchProgress = 0.
    animationEnabled = True


class Bridge(QObject):
    taskSubmitted = Signal(str)
    visualStateChanged = Signal()
    approvalPendingChanged = Signal(bool)
    lifecycleActiveChanged = Signal(bool)
    voiceActivityChanged = Signal(bool)
    speakingActivityChanged = Signal(bool)
    approvalPending = False
    lifecycleActive = False
    voiceActivity = False
    speakingActivity = False
    visualState = 'IDLE'


class Effect(QObject):
    statusChanged = Signal()
    playingChanged = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.ready = QSoundEffect.Status.Ready
        self.plays = 0
        self.playing = False
        self.gain = None

    def setLoopCount(self, value):
        assert value == 1

    def setVolume(self, value):
        self.gain = value

    def setSource(self, value):
        self.source = value

    def status(self):
        return self.ready

    def play(self):
        self.plays += 1
        self.playing = True
        self.playingChanged.emit()

    def stop(self):
        self.playing = False
        self.playingChanged.emit()

    def isPlaying(self):
        return self.playing


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.delenv('EV_STARTUP_AUDIO', raising=False)
    app = QCoreApplication.instance() or QCoreApplication([])
    model, bridge = Model(), Bridge()
    settings = QSettings(str(tmp_path/'audio.ini'), QSettings.Format.IniFormat)
    audio = StartupAudio(model, bridge, settings=settings, effect_factory=Effect)
    yield audio, model, bridge, settings
    audio.cancel()
    model.deleteLater()
    bridge.deleteLater()
    app.processEvents()


def test_waits_for_first_presentation_then_tracks_projection_once(rig):
    audio, model, _, _ = rig
    rise, arrival = audio._effects.values()
    model.frameChanged.emit()
    assert rise.plays == arrival.plays == 0
    audio._first_frame()
    assert rise.plays == 1 and arrival.plays == 0
    model.launchProgress = .99
    model.frameChanged.emit()
    assert arrival.plays == 0
    model.launchProgress = 1.
    model.frameChanged.emit()
    assert not rise.playing and arrival.plays == 1
    arrival.stop()
    assert audio._phase == 'complete'
    model.launchProgress = 0.
    model.frameChanged.emit()
    audio._first_frame()
    model.launchProgress = 1.
    model.frameChanged.emit()
    assert rise.plays == arrival.plays == 1


@pytest.mark.parametrize('event', ['task', 'listen_request', 'approval', 'voice', 'speech', 'lifecycle', 'thinking', 'pause', 'quit'])
def test_activity_cancels_without_restarting(rig, event):
    audio, model, bridge, _ = rig
    audio._first_frame()
    if event == 'task':
        bridge.taskSubmitted.emit('test only')
    elif event == 'listen_request':
        model.listeningRequested.emit()
    elif event == 'approval':
        bridge.approvalPending = True
        bridge.approvalPendingChanged.emit(True)
    elif event == 'voice':
        bridge.voiceActivity = True
        bridge.voiceActivityChanged.emit(True)
    elif event == 'speech':
        bridge.speakingActivity = True
        bridge.speakingActivityChanged.emit(True)
    elif event == 'lifecycle':
        bridge.lifecycleActive = True
        bridge.lifecycleActiveChanged.emit(True)
    elif event == 'thinking':
        bridge.visualState = 'THINKING'
        bridge.visualStateChanged.emit()
    elif event == 'pause':
        model.animationEnabled = False
        model.settingsChanged.emit()
    else:
        QCoreApplication.instance().aboutToQuit.emit()
    model.launchProgress = 1.
    model.frameChanged.emit()
    assert audio._phase == 'cancelled'
    assert not any(effect.playing for effect in audio._effects.values())
    assert audio._effects['arrival'].plays == 0


def test_mute_immediately_stops_arrival_and_persists(rig):
    audio, model, _, settings = rig
    audio._first_frame()
    model.launchProgress = 1.
    model.frameChanged.emit()
    audio.setMuted(True)
    assert audio.muted and audio._phase == 'cancelled'
    assert not audio._effects['arrival'].playing
    reloaded = QSettings(settings.fileName(), QSettings.Format.IniFormat)
    assert reloaded.value('muted', type=bool)
    audio.setMuted(False)
    assert audio._phase == 'cancelled'


def test_volume_updates_output_and_persists(rig):
    audio, _, _, settings = rig
    audio.setVolume(.3)
    assert audio.volume == .3
    assert all(effect.gain == .3 for effect in audio._effects.values())
    reloaded = QSettings(settings.fileName(), QSettings.Format.IniFormat)
    assert reloaded.value('volume', type=float) == .3
    audio.setVolume(0)
    assert audio._phase == 'cancelled'


@pytest.mark.parametrize('value,expected', [('broken', .55), ('nan', .55), ('inf', .55), (-1, 0), (3, 1)])
def test_corrupt_volume_is_bounded(value, expected):
    assert StartupAudio._bounded_volume(value) == expected


@pytest.mark.parametrize('status', [QSoundEffect.Status.Loading, QSoundEffect.Status.Error])
def test_unavailable_or_late_audio_never_delays_animation(rig, status):
    audio, model, _, _ = rig
    audio._effects['rise'].ready = status
    audio._first_frame()
    model.launchProgress = .13
    model.frameChanged.emit()
    audio._effects['rise'].ready = QSoundEffect.Status.Ready
    audio._effects['rise'].statusChanged.emit()
    assert model.launchProgress == .13 and audio._phase == 'cancelled'
    assert not any(effect.plays for effect in audio._effects.values())


def test_loading_can_complete_early_in_projection(rig):
    audio, model, _, _ = rig
    audio._effects['rise'].ready = QSoundEffect.Status.Loading
    audio._first_frame()
    model.launchProgress = .02
    audio._effects['rise'].ready = QSoundEffect.Status.Ready
    audio._effects['rise'].statusChanged.emit()
    assert audio._effects['rise'].plays == 1


def test_environment_can_silence_smoke_runs(rig, monkeypatch):
    _, model, bridge, settings = rig
    monkeypatch.setenv('EV_STARTUP_AUDIO', 'false')
    audio = StartupAudio(model, bridge, settings=settings, effect_factory=Effect)
    audio._first_frame()
    assert audio._phase == 'cancelled'
    assert not any(effect.plays for effect in audio._effects.values())


@pytest.mark.parametrize('reason', ['hide', 'minimize', 'close'])
def test_window_interrupts_arrival(rig, reason):
    class Window(QObject):
        frameSwapped = Signal()
        visibleChanged = Signal(bool)
        visibilityChanged = Signal(QWindow.Visibility)
        closing = Signal()
        visible = True
        mode = QWindow.Visibility.Windowed

        def isVisible(self):
            return self.visible

        def visibility(self):
            return self.mode

    audio, model, _, _ = rig
    window = Window()
    audio.attach_window(window)
    window.frameSwapped.emit()
    model.launchProgress = 1.
    model.frameChanged.emit()
    assert audio._effects['arrival'].playing
    if reason == 'hide':
        window.visible = False
        window.visibleChanged.emit(False)
    elif reason == 'minimize':
        window.mode = QWindow.Visibility.Minimized
        window.visibilityChanged.emit(window.mode)
    else:
        window.closing.emit()
    assert audio._phase == 'cancelled'
    assert not any(effect.playing for effect in audio._effects.values())


def test_bundled_pcm_is_nonempty_unclipped_and_has_clean_edges():
    manifest = json.loads((ASSETS/'manifest.json').read_text())
    for name in ('rise.wav', 'arrival.wav'):
        with wave.open(str(ASSETS/name), 'rb') as stream:
            assert (stream.getnchannels(), stream.getframerate(), stream.getsampwidth()) == (2, 48000, 2)
            assert stream.getnframes()/48000 == manifest['files'][name]['seconds']
            pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').reshape(-1, 2)/32768
        assert .1 < np.max(np.abs(pcm)) < .9
        assert np.sqrt(np.mean(pcm**2)) > .02
        assert np.max(np.abs(pcm[0])) < .001
        assert np.max(np.abs(pcm[-1])) < .001
