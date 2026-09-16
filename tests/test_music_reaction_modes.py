"""Source continuity, user preferences and Assistant activity priority."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from music.session import MusicSession
from prototypes.cinematic_v4.integration import BridgePresentationModel


class Capture:
    def __init__(self, consume, status):
        self.consume, self.status = consume, status
        self.stopped = False

    @staticmethod
    def devices(): return [{'id':7,'label':'Test output'}]

    def start(self, device_id):
        self.device_id = device_id
        self.status('active','Test output')

    def stop(self): self.stopped = True


@pytest.fixture
def session(tmp_path, monkeypatch):
    app = QCoreApplication.instance() or QCoreApplication([])
    monkeypatch.setattr('music.session.LoopbackCapture', Capture)
    settings = QSettings(str(tmp_path/'music.ini'),QSettings.Format.IniFormat)
    music = MusicSession(settings=settings)
    yield music, settings
    music.close()
    app.processEvents()


def test_startup_does_not_capture_or_analyze_without_a_source(session):
    music, _ = session
    music.set_active(False)
    assert music.reactionMode == 'all'
    assert music.inputSource == 'player'
    assert music.capture is None and not music.analysisActive
    assert not music.timer.isActive()


def test_all_modes_preserves_same_output_capture_on_navigation(session):
    music, _ = session
    music.set_active(True)
    music.setInput('system')
    capture = music.capture
    music.set_active(False)
    assert music.capture is capture and not capture.stopped
    assert music.captureState == 'active' and music.analysisActive
    assert music.reactionGain == .25
    music.set_active(True)
    assert music.capture is capture and music.reactionGain == 1.


def test_music_only_releases_capture_and_resumes_when_opened(session):
    music, _ = session
    music.setReactionMode('music')
    music.set_active(True)
    music.setInput('system')
    capture = music.capture
    music._beat.value = 1.
    music.set_active(False)
    assert capture.stopped and music.capture is None
    assert music.reactionGain == music.beat == 0 and not music.timer.isActive()
    music.set_active(True)
    assert music.captureState == 'active' and music.capture is not capture


def test_manual_stop_stays_stopped_across_navigation_and_device_changes(session):
    music, _ = session
    music.setInput('system')
    assert music.captureState == 'active'
    music.stopCapture()
    music.set_active(True)
    music.set_active(False)
    music._devices_changed()
    music.setCaptureDevice(-1)
    assert music.capture is None and not music.analysisActive
    music.startCapture()
    assert music.captureState == 'active'


def test_off_stops_background_but_keeps_music_spectrum(session):
    music, _ = session
    music.setInput('system')
    music.setReactionMode('off')
    assert music.capture is None and music.reactionGain == 0
    music.set_active(True)
    assert music.analysisActive and music.captureState == 'active'
    assert music.reactionGain == 0


def test_switch_to_player_releases_background_capture_when_nothing_playing(session):
    music, _ = session
    music.setInput('system')
    old = music.capture
    music.setInput('player')
    assert old.stopped and music.capture is None and not music.analysisActive


def test_preferences_survive_new_session_without_restarting_capture(session):
    music, settings = session
    music.setReactionMode('music')
    music.setReactionIntensity(.6)
    music.close()
    other = MusicSession(settings=QSettings(settings.fileName(),QSettings.Format.IniFormat))
    try:
        assert other.reactionMode == 'music' and other.reactionIntensity == .6
        assert not other.analysisActive and other.capture is None
        other.set_active(True)
        assert other.reactionGain == .6
    finally: other.close()


def test_intensity_and_invalid_preferences_remain_bounded(session):
    music, _ = session
    music.setReactionMode('bogus')
    assert music.reactionMode == 'all'
    music.setReactionIntensity(100)
    assert music.reactionGain == .25
    music.setReactionIntensity(float('nan'))
    assert music.reactionIntensity == 1
    music.setReactionIntensity(-3)
    assert music.reactionGain == 0


@pytest.mark.parametrize('state',['LISTENING','THINKING','SPEAKING','EXECUTING','VERIFYING','WAITING_FOR_APPROVAL','ERROR'])
def test_busy_visual_states_take_priority(state):
    bridge=SimpleNamespace(approvalPending=False,lifecycleActive=False,voiceActivity=False,speakingActivity=False,visualState=state)
    model=SimpleNamespace(bridge=bridge)
    assert not BridgePresentationModel.musicReactionAllowed.fget(model)


@pytest.mark.parametrize('flag',['approvalPending','lifecycleActive','voiceActivity','speakingActivity'])
def test_actual_activity_wins_even_before_visual_state_catches_up(flag):
    bridge=SimpleNamespace(approvalPending=False,lifecycleActive=False,voiceActivity=False,speakingActivity=False,visualState='IDLE')
    model=SimpleNamespace(bridge=bridge)
    assert BridgePresentationModel.musicReactionAllowed.fget(model)
    setattr(bridge,flag,True)
    assert not BridgePresentationModel.musicReactionAllowed.fget(model)
