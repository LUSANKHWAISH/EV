"""Rendered bridge/overlay contract checks. No orchestrator or external service."""
import os
import sys
import json
from pathlib import Path

os.environ.setdefault('QSG_RHI_BACKEND','d3d11')
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QTimer,QUrl,Qt,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QSignalSpy
from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge
from .integration import configure_cinematic,attach_cinematic_window,BridgeVisualSource
from .validate_preview import LabValidation

ROOT=Path(__file__).resolve().parent

class IntegrationValidation(LabValidation):
    def __init__(self,window,model,app,bridge,messages):
        super().__init__(window,model,app)
        self.bridge=bridge;self.messages=messages
        self.submitted=QSignalSpy(bridge.taskSubmitted)
        self.decisions=QSignalSpy(bridge.approvalSubmitted)
    def start(self):
        self.steps=[(0,self.contracts),(400,self.results),(400,self.result_checks),
                    (400,self.begin_approval),(400,self.modal_checks),(500,self.check_modal_input),
                    (400,self.check_rejection),(500,self.check_provider),(400,self.close_provider),
                    (400,self.finish)]
        self.next()
    def contracts(self):
        self.check('connected_model_uses_bridge_facade',isinstance(self.model.controller,BridgeVisualSource) and self.model.controller.bridge is self.bridge)
        self.check('preview_mode_is_false',not self.model.previewMode)
        self.check('unknown_telemetry_stays_unavailable',not self.model.telemetryAvailable and self.model.cpuHistory==[])
        before=self.bridge.visualState;self.model.setState('ERROR')
        self.check('fixture_cannot_change_production_state',before==self.bridge.visualState)
        self.bridge.setVisualStateForSimulation('LISTENING')
        self.bridge._on_voice_telemetry_internal(.42,.65,True,False)
        self.check('visual_state_consumes_canonical_bridge',self.model.visualState==self.bridge.visualState=='LISTENING')
        self.check('audio_reads_existing_bridge',abs(self.model.audio_target('LISTENING')-.42)<.001 and abs(self.model.audio_target('SPEAKING')-.65)<.001)
        self.model.submitCommand('Read-only integration fixture')
        self.check('command_emits_existing_submission_once',self.submitted.count()==1 and self.submitted.at(0)[0]=='Read-only integration fixture')
        self.check('raw_command_not_duplicated_into_history',self.model.history==[])
        self.bridge._on_telemetry_updated_internal({'cpu_percent':21.,'memory_percent':47.,'memory_used_mb':8192,'memory_total_mb':32768,'disk_free_percent':33.,'process_count':123})
        self.check('system_values_come_from_bridge',self.model.cpuPercent==21 and self.model.memoryPercent==47 and self.model.diskUsedPercent==67 and self.model.processCount==123)
        self.check('no_parallel_telemetry_sampler',self.model.cpuHistory==[21.])
        self.bridge.notifyTaskResult('Integration result <b>must remain plain text</b>.','SUCCESS',True)
    def results(self):
        self.check('response_and_history_follow_result',self.model.responseDetail==self.bridge.taskResult and len(self.model.history)==1)
        self.check('terminal_lifecycle_is_visible',self.model.lifecycleStage=='SUCCESS' and 'SUCCESS' in self.model.lifecycleSteps)
        self.model.submitCommand('Second isolated fixture')
        self.bridge.notifyTaskResult('Integration result <b>must remain plain text</b>.','SUCCESS',True)
    def result_checks(self):
        self.check('identical_results_on_separate_tasks_retained',len(self.model.history)==2)
        self.model.requestListening()
        self.check('voice_request_does_not_submit_or_approve',self.submitted.count()==2 and self.decisions.count()==0 and 'no microphone state was changed' in self.model.responseDetail)
        self.bridge.clearTaskResult()
        self.bridge.clearVisualSimulation()
        self.item('commandInput').setProperty('text','must not execute')
        self.item('commandInput').forceActiveFocus()
        self.stage.setProperty('drawer','settings')
    def begin_approval(self):
        self.bridge._on_approval_requested_internal({'task_id':'cinematic-test-only','action':'ISOLATED_TEST_FIXTURE','description':'No executor is connected. This checks modal input ownership.','risk_level':'LOW','reason':'Integration validation'})
    def modal_checks(self):
        approval=self.item('approvalOverlay');providers=self.item('settingsOverlay')
        self.check('approval_above_other_surfaces',approval.isVisible() and approval.z()>providers.z()>self.stage.z())
        self.check('approval_disables_underlying_stage',not self.stage.isEnabled() and not self.item('commandInput').isEnabled())
        self.window.grabWindow().save(str(ROOT/'evidence/integration_approval.png'))
        self.click('commandInput');self.key(Qt.Key.Key_Return,'\r');self.key(Qt.Key.Key_Space,' ')
    def check_modal_input(self):
        self.check('modal_input_cannot_submit_or_approve',self.submitted.count()==2 and self.decisions.count()==0 and self.bridge.approvalPending)
        self.click('rejectButton')
    def check_rejection(self):
        self.check('existing_reject_button_uses_canonical_bridge',self.decisions.count()==1 and self.decisions.at(0)==['cinematic-test-only',False])
        self.check('stage_reenabled_after_resolution',not self.bridge.approvalPending and self.stage.isEnabled())
        self.model.openProviderSettings()
    def check_provider(self):
        self.check('provider_settings_use_existing_overlay',self.bridge.settingsVisible and self.item('settingsOverlay').isVisible() and not self.stage.isEnabled())
        self.bridge.closeSettings()
    def close_provider(self):
        self.check('provider_close_restores_interface',self.stage.isEnabled())
        self.stage.setProperty('drawer','')
        self.item('commandInput').setProperty('text','')
        self.window.grabWindow().save(str(ROOT/'evidence/integration_connected.png'))
    def finish(self):
        problems=[m for m in self.messages if any(v in m.lower() for v in ('referenceerror','typeerror','binding loop','failed to load','cannot assign','shader compilation failed'))]
        self.check('qml_has_no_runtime_errors',not problems,problems)
        passed=all(c['passed'] for c in self.checks)
        (ROOT/'evidence/integration_validation.json').write_text(json.dumps({'passed':passed,'scope':'Actual rendered QML and real GuiBridge with an isolated EVEventBus. No orchestrator, credentials, live approvals or external calls.','checks':self.checks},indent=2))
        self.app.exit(0 if passed else 1)

def main():
    messages=[]
    def log(kind,context,message):
        messages.append(message)
        print(message,flush=True)
    qInstallMessageHandler(log)
    app=QGuiApplication(sys.argv[:1]);engine=QQmlApplicationEngine()
    bridge=GuiBridge(EVEventBus(initial_state=EVState.IDLE))
    engine.rootContext().setContextProperty('guiBridge',bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine,bridge))))
    if not engine.rootObjects():return 2
    window=engine.rootObjects()[0];attach_cinematic_window(engine,window)
    pump=None
    if '--force-render' in sys.argv:
        pump=QTimer(window);pump.setInterval(16)
        pump.timeout.connect(lambda:window.grabWindow());pump.start()
    checks=IntegrationValidation(window,engine._cinematic_model,app,bridge,messages)
    QTimer.singleShot(1800,checks.start)
    result=app.exec()
    engine._cinematic_model.timer.stop();engine._cinematic_model.systemTimer.stop()
    import shiboken6
    shiboken6.delete(engine)
    bridge.shutdown()
    (ROOT/'evidence/integration_diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
    return result

if __name__=='__main__':raise SystemExit(main())
