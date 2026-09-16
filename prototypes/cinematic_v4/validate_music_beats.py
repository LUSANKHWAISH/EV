"""Real PCM-to-render beat proof, using synthetic kick hits with known timing."""
import json
import os
from pathlib import Path
import sys
import time
import traceback
import wave

import numpy as np
os.environ['EV_STARTUP_AUDIO']='false'
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QTimer,QUrl,QSettings,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication,QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from core.events import EVEventBus
from core.models import EVState
from core.experience import EVExperienceManager
from gui.bridge import GuiBridge
from .integration import configure_cinematic,attach_cinematic_window

DEST=Path(__file__).resolve().parent/'evidence/music_beats'


def main():
    rate=48000;t=np.arange(rate*7)/rate;x=np.zeros_like(t)
    expected=[.5,1.,1.5,2.,2.5,3.,3.5,4.,4.5,5.]
    for hit in expected:
        age=t-hit;x+=.5*np.sin(2*np.pi*75*age)*np.where(age>=0,np.exp(-np.maximum(age,0)*32),0)
    fixture=DEST/'kicks.wav'
    with wave.open(str(fixture),'wb') as stream:
        stream.setnchannels(2);stream.setsampwidth(2);stream.setframerate(rate)
        stream.writeframes((np.column_stack((x,x))*32767).astype('<i2').tobytes())
    messages=[];checks=[];samples=[];images={}
    qInstallMessageHandler(lambda kind,context,message:messages.append(message))
    sys.excepthook=lambda kind,value,tb:messages.append('CALLBACK ERROR '+''.join(traceback.format_exception(kind,value,tb)))
    app=QGuiApplication(['music-beat-validation']);engine=QQmlApplicationEngine()
    bus=EVEventBus(initial_state=EVState.IDLE);bridge=GuiBridge(bus);bridge.set_experience_manager(EVExperienceManager(bus))
    engine.rootContext().setContextProperty('guiBridge',bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine,bridge))))
    if not engine.rootObjects():print(messages);return 2
    window=engine.rootObjects()[0];attach_cinematic_window(engine,window)
    model=engine._cinematic_model;music=model.music
    music._settings=QSettings(str(DEST/'test_settings.ini'),QSettings.Format.IniFormat)
    music.setReactionMode('music')
    music.setReactionIntensity(1.)
    music.setVolume(.4)
    scene=window.findChild(QQuickItem,'nucleusView')
    pump=QTimer(window);pump.setInterval(33);pump.timeout.connect(lambda:window.grabWindow());pump.start()
    start=time.monotonic()
    def check(name,condition,detail=None):checks.append({'name':name,'passed':bool(condition),'detail':detail})
    def snapshot(name):
        frame=window.grabWindow();frame.save(str(DEST/(name+'.png')))
        p=scene.mapToScene(scene.boundingRect().topLeft())
        crop=frame.copy(int(p.x())-8,int(p.y())-8,int(scene.width())+16,int(scene.height())+16)
        crop.save(str(DEST/(name+'_core.png')))
        rgb=crop.convertToFormat(QImage.Format.Format_RGBA8888)
        data=np.frombuffer(rgb.constBits(),dtype=np.uint8).reshape(rgb.height(),rgb.bytesPerLine())[:,:rgb.width()*4].reshape(rgb.height(),rgb.width(),4)
        energy=float(np.sum(data[:,:,0].astype(float)+data[:,:,1].astype(float)))
        images[name]={'energy':energy,'beat':music.beat,'scale':scene.scale(),'shader_pulse':scene.property('musicBeat')}
    def sample():
        samples.append({'seconds':time.monotonic()-start,'position':music.position,'beat':music.beat,'shader':scene.property('musicBeat'),'scale':scene.scale()})
        if music.beat>.7 and 'beat' not in images and music.position>1200:
            snapshot('beat')
        if music.beat<.015 and 'quiet' not in images and 3200<music.position<4800:
            snapshot('quiet')
    meter=QTimer(window);meter.setInterval(16);meter.timeout.connect(sample)
    def play():
        model.openMusic();model.timer.stop();model._motion=10.;model.frameChanged.emit()
        scene.setProperty('orbitTimeOverride',10.)
        music.addFiles([QUrl.fromLocalFile(str(fixture))]);meter.start()
        QTimer.singleShot(7800,inspect)
    def inspect():
        if 'quiet' not in images:snapshot('quiet')
        rising=[];last=False
        for s in samples:
            high=s['beat']>.55
            if high and not last:rising.append(s)
            last=high
        check('known_audio_hits_produce_distinct_pulses',len(rising)==len(expected),len(rising))
        check('pulse_reaches_actual_core_uniform',any(s['shader']>.7 for s in samples))
        check('pulse_remains_bounded',max(s['scale'] for s in samples)<=1.02501)
        check('silence_clears_beat',music.beat==0,music.beat)
        check('rendered_core_brightens_on_hit','beat' in images and images['beat']['energy']>images['quiet']['energy']*1.08,images)
        music.setInput('system');music.seek(0);music.player.play()
        loop_samples=[]
        def collect():loop_samples.append(music.beat)
        music.analysisChanged.connect(collect)
        def loop_finish():
            music.analysisChanged.disconnect(collect)
            check('loopback_drives_same_beat_signal',music.captureState=='active' and max(loop_samples,default=0)>.4,{'state':music.captureState,'max':max(loop_samples,default=0)})
            music.stopCapture();music.stop();finish()
        QTimer.singleShot(3000,loop_finish)
    def finish():
        check('stopping_clears_beat',music.beat==0)
        model.openAssistant()
        check('assistant_has_no_music_pulse',scene.property('musicBeat')==0 and scene.scale()==1)
        problems=[m for m in messages if any(w in m.lower() for w in ('referenceerror','typeerror','callback error','shader compilation failed','binding loop','cannot assign'))]
        check('no_render_or_callback_errors',not problems,problems)
        music.close()
        result={'passed':all(c['passed'] for c in checks),'checks':checks,'images':images,'scope':'Generated 120 BPM kick fixture through real local PCM then selected-output loopback. Render motion frozen for image comparison only. No executor or microphone.'}
        (DEST/'validation.json').write_text(json.dumps(result,indent=2));(DEST/'samples.json').write_text(json.dumps(samples));(DEST/'diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
        print(json.dumps(result),flush=True);app.exit(0 if result['passed'] else 1)
    QTimer.singleShot(2200,play);QTimer.singleShot(22000,app.quit)
    result=app.exec();music.close();bridge.shutdown();return result


if __name__=='__main__':raise SystemExit(main())
