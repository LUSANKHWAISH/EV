"""UI-only adapter for the cinematic preview; no execution or audio service."""
from datetime import datetime
import psutil
from PySide6.QtCore import Property,Signal,Slot,QTimer
try:
    from .mock_telemetry import LabTelemetry
except ImportError:
    from mock_telemetry import LabTelemetry

class PresentationModel(LabTelemetry):
    systemChanged=Signal()
    contentChanged=Signal()
    navigationRequested=Signal(str)
    def __init__(self,parent=None,controller=None,sample_local=True):
        super().__init__(parent,controller=controller)
        self.stateChanged.connect(self.contentChanged)
        self._cpu=0.;self._memory=0.;self._disk=0.;self._memory_text=''
        self._samples=[];self._clock='';self._date='';self._processes=0
        self._history=[];self._response='Ready when you are.'
        self._response_detail='A clear space to think, create and get things done.'
        self._task='No active task'
        self.systemTimer=QTimer(self);self.systemTimer.setInterval(1000)
        self.systemTimer.timeout.connect(self.sampleSystem if sample_local else self.updateClock)
        if sample_local:psutil.cpu_percent(None);self.sampleSystem()
        else:self.updateClock()
        self.systemTimer.start()
    @Property(bool,constant=True)
    def previewMode(self):return True
    @Property(bool,notify=systemChanged)
    def telemetryAvailable(self):return True
    @Property(str,notify=contentChanged)
    def experienceMode(self):return 'STANDARD'
    @Property(str,notify=contentChanged)
    def lifecycleStage(self):
        return {'IDLE':'OBSERVE','AWARE':'OBSERVE','LISTENING':'LISTEN','THINKING':'REASON','SPEAKING':'RESPOND',
                'EXECUTING':'EXECUTE','WAITING_FOR_APPROVAL':'APPROVAL','VERIFYING':'VERIFY','SUCCESS':'SUCCESS'}.get(self.visualState,self.visualState)
    @Property('QVariantList',notify=contentChanged)
    def lifecycleSteps(self):
        terminal=self.lifecycleStage if self.lifecycleStage in ('SUCCESS','FAILED','ERROR','ROLLED_BACK','CANCELLED') else 'COMPLETE'
        reasoning=self.lifecycleStage if self.lifecycleStage in ('PLANNING','VALIDATING','RISK') else 'REASON'
        return ['OBSERVE','LISTEN',reasoning,'APPROVAL','EXECUTE','VERIFY',terminal,'RESPOND']
    @Property(float,notify=systemChanged)
    def cpuPercent(self):return self._cpu
    @Property(float,notify=systemChanged)
    def memoryPercent(self):return self._memory
    @Property(float,notify=systemChanged)
    def diskUsedPercent(self):return self._disk
    @Property(str,notify=systemChanged)
    def memoryText(self):return self._memory_text
    @Property(int,notify=systemChanged)
    def processCount(self):return self._processes
    @Property('QVariantList',notify=systemChanged)
    def cpuHistory(self):return self._samples
    @Property(str,notify=systemChanged)
    def clockText(self):return self._clock
    @Property(str,notify=systemChanged)
    def dateText(self):return self._date
    @Property(str,notify=contentChanged)
    def responseTitle(self):return self._response
    @Property(str,notify=contentChanged)
    def responseDetail(self):return self._response_detail
    @Property(str,notify=contentChanged)
    def currentTask(self):return self._task
    @Property('QVariantList',notify=contentChanged)
    def history(self):return self._history
    @Slot()
    def sampleSystem(self):
        self._cpu=psutil.cpu_percent(None)
        memory=psutil.virtual_memory();self._memory=memory.percent
        self._memory_text=f'{memory.used/1024**3:.1f} / {memory.total/1024**3:.1f} GB'
        self._disk=psutil.disk_usage('D:\\').percent;self._processes=len(psutil.pids())
        self._samples=(self._samples+[self._cpu])[-48:]
        self.updateClock()
    @Slot()
    def updateClock(self):
        now=datetime.now();self._clock=now.strftime('%H:%M');self._date=now.strftime('%d %b %Y').upper()
        self.systemChanged.emit()
    @Slot(str)
    def submitCommand(self,text):
        text=text.strip()
        if not text:return
        self._history=([{'text':text,'time':datetime.now().strftime('%H:%M'),'status':'PREVIEW INPUT'}]+self._history)[:30]
        self._response='Input received in preview.'
        self._response_detail='This interface is not connected to the execution service. Your command has been kept in this preview session only.'
        self._task='Preview input received';self._record('commandPreview',text);self.contentChanged.emit()
    @Slot(str)
    def requestPanel(self,name):
        if name not in ('telemetry','lifecycle','command','result','mode'):return
        super().requestPanel(name);self.navigationRequested.emit(name)
    @Slot()
    def requestListening(self):
        super().requestListening()
        self._response='Microphone request previewed.'
        self._response_detail='Live microphone input is not connected here. Use the state controls to inspect a labelled listening simulation.'
        self.contentChanged.emit()
    @Slot()
    def clearHistory(self):
        self._history=[];self._task='No active task';self._response='Ready when you are.'
        self._response_detail='A clear space to think, create and get things done.';self.contentChanged.emit()
