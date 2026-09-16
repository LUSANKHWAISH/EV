"""Presentation contracts: startup timing, pausing and one-shot behaviour."""
import pytest
from PySide6.QtCore import QCoreApplication
from prototypes.cinematic_v4.mock_telemetry import LabTelemetry


@pytest.fixture
def model():
    app=QCoreApplication.instance() or QCoreApplication([])
    model=LabTelemetry();model.timer.stop()
    yield model
    model.controller.deleteLater();model.deleteLater()
    app.processEvents()


def advance(model,seconds,step=.05):
    for _ in range(round(seconds/step)):
        model._last-=step
        model.tick()


def test_projection_waits_for_first_presented_frame(model):
    advance(model,4)
    assert model.launchProgress==0
    model.renderedFrame();advance(model,1)
    assert .3<model.launchProgress<.34


@pytest.mark.parametrize('quality',[False,True])
def test_launch_duration_and_no_replay_on_state_or_quality_change(model,quality):
    model.setQuality(quality);model.renderedFrame();advance(model,3.3)
    assert model.launchProgress==1
    model.setState('THINKING');model.setQuality(not quality);advance(model,.5)
    assert model.launchProgress==1


def test_pause_freezes_projection_and_motion_then_resumes(model):
    model.renderedFrame();advance(model,.7)
    before=(model.launchProgress,model.motionTime)
    model.setAnimation(False);advance(model,2)
    assert (model.launchProgress,model.motionTime)==before
    model.setAnimation(True);advance(model,.7)
    assert model.launchProgress>before[0] and model.motionTime>before[1]


def test_skip_and_explicit_replay_do_not_change_visual_state_or_emit_requests(model):
    model.setState('WAITING_FOR_APPROVAL');state=model.visualState
    model.finishLaunch();advance(model,.2)
    assert model.launchProgress==1
    model.replayLaunch();assert model.launchProgress==0
    assert model.visualState==state and model.requests==[]
