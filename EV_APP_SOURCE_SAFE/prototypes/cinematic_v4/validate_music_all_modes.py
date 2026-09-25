"""Actual PCM and QML checks for ambient core reactions and user controls."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

os.environ['EV_STARTUP_AUDIO']='false'
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QEventLoop,QSettings,QTimer,QUrl,Qt,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from gui.bridge import GuiBridge
from .integration import configure_cinematic,attach_cinematic_window

DEST=Path(__file__).resolve().parent/'evidence/music_all_modes'


def wait(ms):
    # exec releases the GIL so the real PCM worker can run during each wait.
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    messages=[];checks=[];samples=[]
    qInstallMessageHandler(lambda kind,context,message:messages.append(message))
    sys.excepthook=lambda kind,value,tb:messages.append('CALLBACK ERROR '+''.join(traceback.format_exception(kind,value,tb)))
    app=QGuiApplication(['music-all-modes-validation']);engine=QQmlApplicationEngine()
    bus=EVEventBus(initial_state=EVState.IDLE);bridge=GuiBridge(bus)
    bridge.set_experience_manager(EVExperienceManager(bus))
    engine.rootContext().setContextProperty('guiBridge',bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine,bridge))))
    if not engine.rootObjects(): print(messages);return 2
    window=engine.rootObjects()[0];attach_cinematic_window(engine,window)
    model=engine._cinematic_model;music=model.music
    music._settings=QSettings(str(DEST/'test-settings.ini'),QSettings.Format.IniFormat)
    music.setReactionMode('all');music.setReactionIntensity(1.);music.setVolume(.4)
    stage=window.findChild(QQuickItem,'cinematicStage')
    scene=window.findChild(QQuickItem,'nucleusView')
    pump=QTimer(window);pump.setInterval(33);pump.timeout.connect(lambda:window.grabWindow());pump.start()
    def check(name,condition,detail=None):checks.append({'name':name,'passed':bool(condition),'detail':detail})
    def item(name):
        found=window.findChild(QQuickItem,name)
        if found is None:raise AssertionError('Missing '+name)
        return found
    def click(name):
        control=item(name)
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,control.mapToScene(control.boundingRect().center()).toPoint())
        wait(80)
    def take(duration,label):
        until=time.monotonic()+duration;out=[];saved=False
        while time.monotonic()<until:
            wait(20)
            row={'phase':label,'beat':music.beat,'shader':scene.property('musicBeat'),'scale':scene.scale(),'position':music.position,'processed':music.worker.processed,'active':music.analysisActive,'allowed':model.musicReactionAllowed}
            out.append(row)
            if row['shader']>.08 and not saved:
                window.grabWindow().save(str(DEST/(label+'.png')));saved=True
        samples.extend(out);return out
    def run():
        try:
            check('startup_has_no_capture_or_analysis',music.capture is None and not music.analysisActive)
            model.openMusic()
            music.addFiles([QUrl.fromLocalFile(str(DEST.parent/'music_beats/kicks.wav'))])
            wait(1600)
            model.openAssistant();wait(700)
            rows=take(2.3,'assistant_player')
            check('real_player_beats_reach_assistant',max(r['shader'] for r in rows)>.1, max(r['shader'] for r in rows))
            check('assistant_strength_is_quarter',all(abs(r['shader']-r['beat']*.25)<.00001 for r in rows))
            check('assistant_scale_is_bounded',max(r['scale'] for r in rows)<=1.006251)
            check('player_analysis_survives_navigation',music.analysisActive and music.playing)

            # Freeze the measured envelope only for deterministic priority checks.
            music.timer.stop();music._beat.value=1.;music.analysisChanged.emit()
            for state in ('LISTENING','THINKING','SPEAKING','EXECUTING','VERIFYING'):
                bridge._visual_controller.set_state_for_simulation(state);wait(50)
                check('priority_'+state,scene.property('musicBeat')==0 and scene.scale()==1.)
            bridge._visual_controller.set_state_for_simulation('IDLE');wait(50)
            check('idle_restores_reaction',scene.property('musicBeat')==.25)
            model.setAnimation(False);wait(50)
            check('animation_pause_suppresses_reaction',scene.property('musicBeat')==0 and scene.scale()==1.)
            model.setAnimation(True)
            bridge._lifecycle_active=True;bridge.lifecycleActiveChanged.emit(True);wait(50)
            check('lifecycle_flag_suppresses_reaction',scene.property('musicBeat')==0)
            bridge._lifecycle_active=False;bridge.lifecycleActiveChanged.emit(False)
            bridge._on_approval_requested_internal({'task_id':'ambient-ui-fixture','action':'TEST_ONLY','description':'No executor attached','risk_level':'LOW','reason':'Modal test'})
            wait(100)
            check('approval_suppresses_reaction_and_controls',scene.property('musicBeat')==0 and not stage.isEnabled())
            click('rejectButton')
            music.timer.start()

            stage.setProperty('drawer','settings');wait(100)
            mode=item('musicReactionMode');mode.forceActiveFocus()
            QTest.keyClick(window,Qt.Key.Key_Home);QTest.keyClick(window,Qt.Key.Key_Return);wait(100)
            check('mode_control_selects_music_only',music.reactionMode=='music',music.reactionMode)
            check('music_only_sleeps_in_assistant',not music.analysisActive and scene.property('musicBeat')==0)
            # Select All modes through the actual ComboBox keyboard interaction.
            mode.forceActiveFocus();QTest.keyClick(window,Qt.Key.Key_Down);QTest.keyClick(window,Qt.Key.Key_Return);wait(100)
            check('mode_control_selects_all',music.reactionMode=='all',music.reactionMode)
            slider=item('musicReactionIntensity');slider.forceActiveFocus()
            QTest.keyClick(window,Qt.Key.Key_Left);wait(50)
            check('intensity_slider_updates_settings',abs(music.reactionIntensity-.95)<.00001,music.reactionIntensity)
            window.grabWindow().save(str(DEST/'settings_1920.png'))
            window.resize(1100,760);wait(300)
            window.grabWindow().save(str(DEST/'settings_1100.png'))
            check('settings_controls_fit_narrow_drawer',slider.width()>200 and slider.mapToScene(slider.boundingRect().topRight()).x()<1100)
            window.resize(1920,1080);wait(100)
            music.setReactionIntensity(1.)
            # Source control in Assistant starts an explicit Windows capture.
            click('reactionInputSystem');wait(1000)
            check('assistant_source_control_starts_capture',music.inputSource=='system' and music.captureState=='active',music.status)
            indicator=item('backgroundAudioIndicator')
            check('capture_indicator_visible',indicator.isVisible())
            stage.setProperty('drawer','');music.seek(0);music.player.play();wait(300)
            capture=music.capture
            rows=take(2.2,'assistant_windows')
            check('windows_mix_drives_assistant',max(r['shader'] for r in rows)>.08,max(r['shader'] for r in rows))
            model.openMusic();wait(700)
            check('navigation_preserves_capture_instance',music.capture is capture)
            rows=take(1.6,'music_windows')
            check('music_full_strength_preserved',max(r['shader'] for r in rows)>.4,max(r['shader'] for r in rows))
            music.setReactionMode('off');wait(100)
            check('off_disables_core_but_not_spectrum',scene.property('musicBeat')==0 and music.analysisActive and music.captureState=='active')
            model.openAssistant();wait(200)
            check('off_releases_background_capture',music.capture is None and not music.analysisActive)
            music.setReactionMode('all');wait(700)
            check('all_restores_requested_capture',music.captureState=='active')
            stage.setProperty('drawer','settings');wait(100)
            # Capture control is below the fold; scroll it into the actual viewport.
            toggle=item('reactionCaptureToggle')
            scroll=toggle.parentItem()
            while scroll and scroll.property('contentY') is None:scroll=scroll.parentItem()
            if scroll:scroll.setProperty('contentY',220)
            wait(100);click('reactionCaptureToggle')
            check('stop_capture_control_releases_background',music.capture is None and not music.analysisActive)
            check('indicator_hides_after_stop',not indicator.isVisible())
            model.openMusic();model.openAssistant();wait(100)
            check('manual_stop_survives_navigation',music.capture is None)
        except Exception:
            check('validation_exception',False,traceback.format_exc())
        finally:
            problems=[m for m in messages if any(w in m.lower() for w in ('referenceerror','typeerror','callback error','shader compilation failed','binding loop','cannot assign'))]
            check('no_render_or_callback_errors',not problems,problems)
            music.close();check('worker_closed',not music.worker.thread.is_alive())
            report={'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Real generated PCM and Windows loopback; fixed envelope only for priority checks. Isolated bridge, no executor. Forced frame readbacks, not FPS benchmark.'}
            (DEST/'validation.json').write_text(json.dumps(report,indent=2));(DEST/'samples.json').write_text(json.dumps(samples))
            (DEST/'diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
            print(json.dumps(report),flush=True);app.exit(0 if report['passed'] else 1)
    QTimer.singleShot(1600,run)
    code=app.exec();music.close();bridge.shutdown();return code


if __name__=='__main__':raise SystemExit(main())
