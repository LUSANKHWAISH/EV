"""Lab fixture adapter; reuses E.V.'s existing VisualStateController read-only.

No production bootstrap, microphone, TTS, planner, approval or execution API.
"""
from pathlib import Path
import importlib.util
import math
import time
from collections import deque
from PySide6.QtCore import QObject, Property, Signal, Slot, QTimer, Qt

source=Path(__file__).resolve().parents[2]/'gui/visual_state.py'
spec=importlib.util.spec_from_file_location('ev_lab_existing_visual_state',source)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

PARAMS={
    'IDLE':(1.2,.95,3), 'AWARE':(1.5,1.15,6),
    'LISTENING':(1.4,.9,6), 'THINKING':(1.55,1.6,8),
    'PROCESSING':(1.65,1.7,9), 'SPEAKING':(1.5,1.1,6),
    'EXECUTING':(1.7,1.4,10), 'WAITING_FOR_APPROVAL':(1.1,.08,13),
    'VERIFYING':(1.4,.9,6), 'SUCCESS':(1.75,.85,5),
    'WARNING':(.85,.25,4), 'ERROR':(.65,.12,4), 'SLEEP':(.25,0,2)
}

class LabTelemetry(QObject):
    frameChanged=Signal()
    stateChanged=Signal()
    settingsChanged=Signal()
    requestChanged=Signal()
    statsChanged=Signal()
    def __init__(self,parent=None,controller=None):
        super().__init__(parent)
        self.controller=controller if controller is not None else module.VisualStateController()
        self.controller.changed.connect(self.stateChanged)
        if controller is None:self.controller.set_state_for_simulation('IDLE')
        self._quality=False;self._animation=True;self._connected=True
        self._motion=0.;self._audio=0.;self._glow=PARAMS['IDLE'][0];self._spread=3.
        self._launch_elapsed=None
        self._launch_progress=0.
        self._last=time.perf_counter();self._wall=0.;self._request='No interaction requests'
        self._fps=0.;self._frame_times=deque(maxlen=36000);self._frame_count=0;self._fps_start=self._last
        self.requests=[]
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16);self.timer.timeout.connect(self.tick);self.timer.start()
    @Property(str,notify=stateChanged)
    def visualState(self):return self.controller.state if self._connected else 'DISCONNECTED'
    @Property(str,notify=stateChanged)
    def previousVisualState(self):return self.controller.previous_state
    @Property(float,notify=stateChanged)
    def transitionProgress(self):return self.controller.transition_progress
    @Property(float,notify=frameChanged)
    def motionTime(self):return self._motion
    @Property(float,notify=frameChanged)
    def launchProgress(self):return self._launch_progress
    @Slot()
    def finishLaunch(self):
        self._launch_elapsed=3.2;self._launch_progress=1.;self.frameChanged.emit()
    @Slot()
    def replayLaunch(self):
        self._launch_elapsed=0.;self._launch_progress=0.;self.frameChanged.emit()
    @Property(float,notify=frameChanged)
    def audioLevel(self):return self._audio
    @Property(float,notify=frameChanged)
    def glow(self):return self._glow
    @Property(float,notify=frameChanged)
    def ringSpread(self):return self._spread
    @Property(bool,notify=settingsChanged)
    def qualityMode(self):return self._quality
    @Property(bool,notify=settingsChanged)
    def animationEnabled(self):return self._animation
    @Property(str,notify=requestChanged)
    def lastRequest(self):return self._request
    @Property(float,notify=statsChanged)
    def measuredFps(self):return self._fps
    @Slot(str)
    def setState(self,state):
        self._connected=state!='DISCONNECTED'
        aliases={'WAKING':'AWARE','DISCONNECTED':'SLEEP'}
        self.controller.set_state_for_simulation(aliases.get(state,state))
        self.stateChanged.emit()
    @Slot(bool)
    def setQuality(self,value):
        self._quality=bool(value);self.timer.setInterval(33 if value else 16);self.settingsChanged.emit()
    @Slot(bool)
    def setAnimation(self,value):
        self._animation=bool(value);self.settingsChanged.emit()
    @Slot(str)
    def requestPanel(self,name):
        if name not in ('telemetry','lifecycle','command','result','mode'):return
        self._record('openPanelRequested',name)
    @Slot()
    def requestListening(self):self._record('listenRequested','recorded only; microphone unchanged')
    def _record(self,kind,value):
        self._request=kind+': '+value;self.requests.append({'time':self._wall,'kind':kind,'value':value})
        self.requests=self.requests[-256:];self.requestChanged.emit()
    @Slot()
    def tick(self):
        now=time.perf_counter();dt=min(.1,now-self._last);self._last=now;self._wall+=dt
        state=self.controller.state
        g,speed,spread=PARAMS.get(state,PARAMS['IDLE'])
        if not self._animation:
            changed=self._audio!=0 or self._glow!=g or self._spread!=spread
            self._audio=0.;self._glow=g;self._spread=spread
            if changed:self.frameChanged.emit()
            return
        if self._launch_elapsed is not None and self._launch_progress<1.:
            self._launch_elapsed+=dt
            self._launch_progress=min(1.,self._launch_elapsed/3.2)
        target=self.audio_target(state)
        tau=.025 if target>self._audio else .16
        self._audio+=(target-self._audio)*(1-math.exp(-dt/tau))
        blend=1-math.exp(-dt/.3)
        self._glow+=(g+self._audio*.45-self._glow)*blend
        self._spread+=(spread+self._audio*3-self._spread)*blend
        if self._animation:self._motion+=dt*speed
        self.frameChanged.emit()
    def audio_target(self,state):
        target=0.
        if state=='LISTENING':target=max(0,math.sin(self._wall*2.7))**2*(.3+.6*abs(math.sin(self._wall*6.3)))
        if state=='SPEAKING':target=max(0,math.sin(self._wall*3.4))*(.25+.65*abs(math.sin(self._wall*10.8)))
        if int(self._wall)%7==6:target=0.
        return target
    @Slot()
    def renderedFrame(self):
        now=time.perf_counter()
        # Begin after the first presentation, so shader startup cannot consume
        # the projection before the window has shown a single frame.
        if self._launch_elapsed is None:self._launch_elapsed=0.
        self._frame_times.append(now)
        self._frame_count+=1
        elapsed=now-self._fps_start
        if elapsed>=1:
            self._fps=self._frame_count/elapsed;self._fps_start=now;self._frame_count=0;self.statsChanged.emit()
