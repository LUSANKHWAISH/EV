"""Opt-in presentation integration; the existing GuiBridge retains all authority."""
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import QObject,Property,Signal,Slot,Qt
from PySide6.QtQml import qmlRegisterType
from .geometry import LabGeometry,ParticleInstances
from .presentation import PresentationModel
from .frame_pacing import FramePacer
from .startup_audio import StartupAudio
from music.session import MusicSession

ROOT=Path(__file__).resolve().parent

class BridgeVisualSource(QObject):
    """Read-only facade, not a second state machine."""
    changed=Signal()
    def __init__(self,bridge):
        super().__init__(bridge);self.bridge=bridge
        bridge.visualStateChanged.connect(self.changed)
    @property
    def state(self):return self.bridge.visualState
    @property
    def previous_state(self):return self.bridge.previousVisualState
    @property
    def transition_progress(self):return self.bridge.visualTransitionProgress

class BridgePresentationModel(PresentationModel):
    listeningRequested=Signal()
    bridgeContentChanged=Signal()
    bridgeSystemChanged=Signal()
    musicPriorityChanged=Signal()
    def __init__(self,bridge):
        self.bridge=bridge
        self._local_notice=''
        self._last_result=''
        super().__init__(controller=BridgeVisualSource(bridge),sample_local=False)
        self._startup_audio=StartupAudio(self,bridge)
        self._music=MusicSession(self)
        self._music.userAction.connect(self._startup_audio.cancel)
        bridge.experienceModeChanged.connect(self._music_mode_changed)
        bridge.visualStateChanged.connect(self.musicPriorityChanged)
        bridge.lifecycleActiveChanged.connect(self.musicPriorityChanged)
        bridge.approvalPendingChanged.connect(self.musicPriorityChanged)
        bridge.voiceActivityChanged.connect(self.musicPriorityChanged)
        bridge.speakingActivityChanged.connect(self.musicPriorityChanged)
        self._music.set_active(bridge.experienceMode=='MUSIC')
        self.contentChanged.connect(self.bridgeContentChanged)
        self.systemChanged.connect(self.bridgeSystemChanged)
        bridge.telemetryUpdated.connect(self.sampleSystem)
        bridge.taskResultChanged.connect(self.refreshContent)
        bridge.currentTaskChanged.connect(self.refreshContent)
        bridge.lifecycleStageChanged.connect(self.refreshContent)
        bridge.experienceModeChanged.connect(self.refreshContent)
        self.sampleSystem()
    @Property(bool,constant=True)
    def previewMode(self):return False
    @Property(QObject,constant=True)
    def startupAudio(self):return self._startup_audio
    @Property(QObject,constant=True)
    def music(self):return self._music
    @Property(bool,notify=musicPriorityChanged)
    def musicReactionAllowed(self):
        return (not self.bridge.approvalPending and not self.bridge.lifecycleActive
                and not self.bridge.voiceActivity and not self.bridge.speakingActivity
                and self.bridge.visualState in ('IDLE','AWARE','WARNING'))
    @Slot()
    def openMusic(self):
        self._startup_audio.cancel()
        self.finishLaunch()
        self.bridge.setExperienceMode('MUSIC')
    @Slot()
    def openAssistant(self):self.bridge.setExperienceMode('STANDARD')
    @Slot(str)
    def _music_mode_changed(self,mode):self._music.set_active(mode=='MUSIC')
    @Property(bool,notify=bridgeSystemChanged)
    def telemetryAvailable(self):return self.bridge.telemetryAvailable
    @Property(str,notify=bridgeContentChanged)
    def experienceMode(self):return self.bridge.experienceMode
    @Property(str,notify=bridgeContentChanged)
    def currentTask(self):return self.bridge.currentTask or 'No active task'
    @Property(str,notify=bridgeContentChanged)
    def lifecycleStage(self):
        return {'IDLE':'OBSERVE','THINKING':'REASON','LISTENING':'LISTEN','SPEAKING':'RESPOND'}.get(self.bridge.lifecycleStage,self.bridge.lifecycleStage)
    @Property(str,notify=bridgeContentChanged)
    def responseTitle(self):
        if self._local_notice:return 'Voice control'
        if self.bridge.taskResultAvailable:return 'E.V. response' if self.bridge.taskResultSuccess else 'Attention required'
        if self.bridge.lifecycleActive:return 'Working on your request.'
        return 'Ready when you are.'
    @Property(str,notify=bridgeContentChanged)
    def responseDetail(self):
        return self._local_notice or self.bridge.taskResult or 'A clear space to think, create and get things done.'
    @Slot()
    def refreshContent(self,*args):
        self._local_notice=''
        result=self.bridge.taskResult
        if self.bridge.taskResultAvailable and result and result!=self._last_result:
            self._last_result=result
            self._history=([{'text':result,'time':datetime.now().strftime('%H:%M'),'status':self.bridge.taskResultStatus}]+self._history)[:30]
        self.contentChanged.emit()
    @Slot()
    def sampleSystem(self):
        if self.bridge.telemetryAvailable:
            self._cpu=self.bridge.telemetryCpuPercent;self._memory=self.bridge.telemetryMemoryPercent
            self._disk=100-self.bridge.telemetryDiskFreePercent;self._processes=self.bridge.telemetryProcessCount
            self._memory_text=f'{self.bridge.telemetryMemoryUsedMb/1024:.1f} / {self.bridge.telemetryMemoryTotalMb/1024:.1f} GB'
            self._samples=(self._samples+[self._cpu])[-48:]
        self.systemChanged.emit()
    def audio_target(self,state):
        # Speaking uses the existing bridge signal, not a claim of measured PCM.
        value=self.bridge.voiceLevel if state=='LISTENING' else self.bridge.speechLevel if state=='SPEAKING' else 0.
        return max(0.,min(1.,float(value)))
    @Slot(str)
    def setState(self,state):
        # Fixture controls cannot alter the production controller.
        return
    @Slot(str)
    def submitCommand(self,text):
        text=text.strip()
        if text:
            self._local_notice=''
            self._last_result=''
            # Do not duplicate raw input into preview history; it may contain credentials.
            self.bridge.submitTask(text)
    @Slot()
    def requestListening(self):
        self._local_notice='A microphone-start action is not exposed by the current GUI bridge. Use your existing voice controls; no microphone state was changed.'
        self.listeningRequested.emit();self.contentChanged.emit()
    @Slot()
    def openProviderSettings(self):self.bridge.openSettings()

def configure_cinematic(engine,bridge):
    qmlRegisterType(LabGeometry,'EVLab',1,0,'LabGeometry')
    qmlRegisterType(ParticleInstances,'EVLab',1,0,'ParticleInstances')
    model=BridgePresentationModel(bridge)
    engine._cinematic_model=model
    engine.rootContext().setContextProperty('lab',model)
    engine.rootContext().setContextProperty('startExpanded',False)
    return ROOT/'qml/ConnectedWindow.qml'

def attach_cinematic_window(engine,window):
    model=engine._cinematic_model
    pacer=FramePacer(window.screen().refreshRate())
    engine._cinematic_pacer=pacer
    def settings_changed():pacer.quality=model.qualityMode
    model.settingsChanged.connect(settings_changed)
    window.beforeFrameBegin.connect(pacer.before_frame,Qt.ConnectionType.DirectConnection)
    window.frameSwapped.connect(model.renderedFrame)
    model.startupAudio.attach_window(window)
