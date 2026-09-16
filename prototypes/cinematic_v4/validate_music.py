"""Real player, loopback and rendered input checks with a generated local fixture."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

os.environ['EV_STARTUP_AUDIO']='false'
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QTimer,QUrl,Qt,QSettings,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from core.events import EVEventBus
from core.models import EVState
from core.experience import EVExperienceManager
from gui.bridge import GuiBridge
from .integration import configure_cinematic,attach_cinematic_window

DEST=Path(__file__).resolve().parent/'evidence/music_foundation'


def main():
    messages=[];checks=[];samples=[]
    qInstallMessageHandler(lambda kind,context,text:messages.append(text))
    sys.excepthook=lambda kind,value,tb:messages.append('CALLBACK ERROR '+''.join(traceback.format_exception(kind,value,tb)))
    app=QGuiApplication(['music-validation'])
    event_bus=EVEventBus(initial_state=EVState.IDLE)
    bridge=GuiBridge(event_bus);bridge.set_experience_manager(EVExperienceManager(event_bus))
    engine=QQmlApplicationEngine();engine.rootContext().setContextProperty('guiBridge',bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine,bridge))))
    if not engine.rootObjects(): print(messages);return 2
    window=engine.rootObjects()[0];attach_cinematic_window(engine,window)
    model=engine._cinematic_model;music=model.music
    music._settings=QSettings(str(DEST/'test-settings.ini'),QSettings.Format.IniFormat)
    music.setReactionMode('music')
    music.setReactionIntensity(1.)
    music.setVolume(.55)
    stage=window.findChild(QQuickItem,'cinematicStage')
    def check(name,condition,detail=None): checks.append({'name':name,'passed':bool(condition),'detail':detail})
    def click(name):
        item=window.findChild(QQuickItem,name)
        if item is None: raise AssertionError('Missing '+name)
        point=item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
    pump=QTimer(window);pump.setInterval(33);pump.timeout.connect(lambda:window.grabWindow());pump.start()
    meter=QTimer(window);meter.setInterval(100)
    meter.timeout.connect(lambda:samples.append({'time':time.monotonic(),'source':music.inputSource,'level':music.level,'peak':max(music.bands),'position':music.position}))
    meter.start()
    phases=[]
    def step(delay,func): phases.append((delay,func))
    def next_step():
        if phases:
            delay,func=phases.pop(0)
            def run():
                try: func()
                except Exception:
                    messages.append('CALLBACK ERROR '+traceback.format_exc());check(func.__name__,False,messages[-1])
                next_step()
            QTimer.singleShot(delay,run)

    def open_music():
        click('musicButton')
    def load():
        check('canonical_music_mode',bridge.experienceMode=='MUSIC')
        check('music_surface_loaded',window.findChild(QQuickItem,'musicWorkspace') is not None)
        music.addFiles([QUrl.fromLocalFile(str(DEST/'fixture.wav'))])
    def playing():
        # Codec/device initialization varies on physical vs remote audio. Wait
        # for the observed playback position, rather than a process-start guess.
        deadline=time.monotonic()+3
        while music.position<=1000 and time.monotonic()<deadline:QTest.qWait(50)
        check('local_playback_running',music.playing and music.position>1000 and music.duration>=11900,{'position':music.position,'duration':music.duration})
        check('real_pcm_reaches_analyzer',music.worker.processed>0 and music.level>.01 and max(music.bands)>.2,{'processed':music.worker.processed,'level':music.level})
        slider=window.findChild(QQuickItem,'musicVolume');slider.forceActiveFocus();before=music.volume
        QTest.keyClick(window,Qt.Key.Key_Left)
        check('volume_slider_controls_output',music.volume<before,{'before':before,'after':music.volume})
        music.setVolume(before)
        window.grabWindow().save(str(DEST/'music_playing.png'))
        click('musicPlay')
    def paused():
        check('pause_control_and_silence',not music.playing and music.level<.01,music.level)
        slider=window.findChild(QQuickItem,'musicSeek');slider.forceActiveFocus();before=music.position
        QTest.keyClick(window,Qt.Key.Key_Right)
        QTest.qWait(150)
        check('seek_slider_controls_position',music.position>before,{'before':before,'after':music.position})
        music.seek(7500);music.togglePlayback()
    def seeked():
        check('seek_works',music.position>7500 and music.playing,music.position)
        click('musicMute')
    def muted():
        check('mute_control_and_meter',music.muted and music.level<.01,music.level)
        click('musicMute')
        music.seek(0)
        click('musicInputSystem')
    def loopback():
        check('loopback_started',music.captureState=='active',music.status)
        check('windows_mix_has_real_audio',music.level>.01,music.level)
        click('musicCaptureToggle')
    def stopped_capture():
        check('stop_capture_releases_device',music.capture is None and music.captureState=='off' and music.level<.01)
        click('musicCaptureToggle')
    def reconnected():
        check('capture_reconnect',music.captureState=='active' and music.level>.01)
        music.setCaptureDevice(-1)
    def device_reconnect():
        check('device_reconnect_with_default',music.captureState=='active')
        click('musicInputPlayer')
        check('source_switch_releases_loopback',music.capture is None and music.inputSource=='player')
        music.seek(5200)
    def silent_segment():
        check('recorded_silence_settles',music.level<.01,music.level)
        window.resize(1100,760)
        music.seek(0)
    def narrow():
        window.grabWindow().save(str(DEST/'music_1100.png'))
        check('compact_music_navigation',window.findChild(QQuickItem,'nav_music').isVisible())
        bridge._on_approval_requested_internal({'task_id':'music-ui-fixture','action':'TEST_ONLY','description':'No executor attached','risk_level':'LOW','reason':'Modal test'})
    def approval():
        check('approval_disables_music_controls',not stage.isEnabled() and not window.findChild(QQuickItem,'musicPlay').isEnabled())
        window.grabWindow().save(str(DEST/'music_approval.png'))
        click('rejectButton')
        model.openAssistant()
    def restored():
        check('assistant_restored',bridge.experienceMode=='STANDARD' and window.findChild(QQuickItem,'commandInput').isVisible())
        check('capture_and_analysis_sleep_outside_music',music.capture is None and not music.timer.isActive())
        model.openMusic()
        music.stop()
    def finish():
        check('stop_control_stops_player',not music.playing)
        problems=[m for m in messages if any(token in m.lower() for token in ('typeerror','referenceerror','binding loop','cannot assign','callback error'))]
        check('no_qml_or_python_callbacks_failed',not problems,problems)
        music.close()
        check('analysis_worker_stops',not music.worker.thread.is_alive())
        report={'passed':all(c['passed'] for c in checks),'scope':'Real QMediaPlayer + Qt PCM tap + WASAPI selected output. Generated signal fixture; isolated bridge, no executor. Forced readbacks, not FPS benchmark.','checks':checks,'sample_count':len(samples)}
        (DEST/'validation.json').write_text(json.dumps(report,indent=2));(DEST/'samples.json').write_text(json.dumps(samples))
        (DEST/'diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
        print(json.dumps(report),flush=True)
        app.exit(0 if report['passed'] else 1)
    for delay,func in [(2000,open_music),(800,load),(2200,playing),(1000,paused),(800,seeked),(1000,muted),(1600,loopback),(500,stopped_capture),(1000,reconnected),(600,device_reconnect),(700,silent_segment),(1000,narrow),(500,approval),(800,restored),(500,finish)]:step(delay,func)
    next_step();QTimer.singleShot(35000,app.quit)
    code=app.exec();music.close();bridge.shutdown();return code


if __name__=='__main__':raise SystemExit(main())
