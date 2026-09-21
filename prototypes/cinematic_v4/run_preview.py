"""Launch the independent E.V. presentation lab using the existing Qt installation."""
import os
import sys
sys.dont_write_bytecode=True
os.environ.setdefault('QSG_RHI_BACKEND','d3d11')
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ['QT_DISABLE_SHADER_DISK_CACHE']='1'
os.environ['QSG_RHI_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QSG_INFO','1')
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
import argparse
import json
import time
from pathlib import Path
from PySide6.QtCore import QUrl, QTimer, qInstallMessageHandler, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickWindow
from geometry import LabGeometry, ParticleInstances, OrbitalParticleInstances
from presentation import PresentationModel

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--expanded',action='store_true')
    parser.add_argument('--quality',action='store_true')
    parser.add_argument('--state',default='IDLE')
    parser.add_argument('--capture',default='')
    parser.add_argument('--capture-after',type=float,default=3)
    parser.add_argument('--duration',type=float,default=0)
    parser.add_argument('--checkerboard',action='store_true')
    parser.add_argument('--record',default='')
    parser.add_argument('--record-seconds',type=float,default=25)
    parser.add_argument('--scenario',action='store_true')
    parser.add_argument('--validate',action='store_true')
    parser.add_argument('--validate-launch',action='store_true')
    parser.add_argument('--validate-reaction',action='store_true')
    parser.add_argument('--force-render',action='store_true',help='Diagnostic readback pump for an occluded/remote desktop. Not a live FPS benchmark.')
    parser.add_argument('--reference-dpi',action='store_true',help='Use one physical pixel per logical pixel in this process for reproducible 1080p evidence.')
    parser.add_argument('--report',default='last_run.json')
    parser.add_argument('--drawer',choices=['','settings','activity','system'],default='')
    parser.add_argument('--size',default='1920x1080')
    parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--orbit-time',type=float,default=-1)
    parser.add_argument('--skip-launch',action='store_true')
    parser.add_argument('--record-launch',action='store_true',help='Replay projection as the recording begins.')
    parser.add_argument('--view-yaw',type=float,default=0)
    parser.add_argument('--hide-aura',action='store_true')
    parser.add_argument('--depth-layer',type=int,default=0,choices=[0,1,2,3],help='Diagnostic depth layer: 0=all, 1=rear, 2=middle, 3=front')
    args=parser.parse_args()
    if args.reference_dpi:
        os.environ['QT_ENABLE_HIGHDPI_SCALING']='0'
    (ROOT/'evidence').mkdir(exist_ok=True)
    log=(ROOT/'evidence/render_diagnostics.txt').open('w',encoding='utf-8')
    messages=[]
    def message_handler(kind,context,message):
        messages.append(str(message));log.write(str(message)+'\n');log.flush()
        print(message,flush=True)
    qInstallMessageHandler(message_handler)
    app=QGuiApplication(sys.argv[:1]);app.setApplicationName('EV-Cinematic-Preview')
    screen=app.primaryScreen()
    display={'name':screen.name(),'logical_width':screen.size().width(),'logical_height':screen.size().height(),
             'refresh_hz':screen.refreshRate(),'device_pixel_ratio':screen.devicePixelRatio(),
             'reference_dpi_requested':args.reference_dpi}
    qmlRegisterType(LabGeometry,'EVLab',1,0,'LabGeometry')
    qmlRegisterType(ParticleInstances,'EVLab',1,0,'ParticleInstances')
    qmlRegisterType(
        OrbitalParticleInstances,
        'EVLab',
        1,
        0,
        'OrbitalParticleInstances',
    )
    lab=PresentationModel();lab.setQuality(args.quality);lab.setState(args.state)
    engine=QQmlApplicationEngine()
    engine.rootContext().setContextProperty('lab',lab)
    engine.rootContext().setContextProperty('startExpanded',args.expanded)
    engine.load(QUrl.fromLocalFile(str(ROOT/'qml/LabWindow.qml')))
    if not engine.rootObjects():return 2
    window=engine.rootObjects()[0]
    width,height=map(int,args.size.lower().split('x'))
    window.resize(width,height)
    window.setProperty('drawer',args.drawer)
    if args.freeze or args.skip_launch:lab.finishLaunch()
    if args.freeze:lab.setAnimation(False)
    from PySide6.QtQuick import QQuickItem
    scene=window.findChild(QQuickItem,'nucleusView')
    scene.setProperty('viewYaw',args.view_yaw)
    scene.setProperty('orbitTimeOverride',args.orbit_time)
    if args.hide_aura:
        aura_item = window.findChild(
            QQuickItem,
            'globalFireParticleLayer',
        )
        if aura_item:
            aura_item.setVisible(False)
    if args.depth_layer:
        aura_item = window.findChild(
            QQuickItem,
            'globalFireParticleLayer',
        )
        if aura_item:
            aura_item.setProperty(
                'depthLayerMode',
                args.depth_layer,
            )
    from frame_pacing import FramePacer
    pacer=FramePacer(window.screen().refreshRate())
    pacer.quality=args.quality
    if not args.force_render:
        window.beforeFrameBegin.connect(pacer.before_frame,Qt.ConnectionType.DirectConnection)
    def apply_frame_pacing():
        pacer.quality=lab.qualityMode
    lab.settingsChanged.connect(apply_frame_pacing)
    window.frameSwapped.connect(lab.renderedFrame)
    window.setProperty('checkerboard',args.checkerboard)
    exposure_samples=[]
    exposure_timer=QTimer(window);exposure_timer.setInterval(250)
    exposure_timer.timeout.connect(lambda:exposure_samples.append({'exposed':window.isExposed(),'active':window.isActive()}))
    exposure_timer.start()
    render_pump=None
    if args.force_render:
        render_pump=QTimer(window)
        render_pump.setInterval(16)
        render_pump.timeout.connect(lambda:window.grabWindow())
        render_pump.start()
    captures=[]
    def capture():
        image=window.grabWindow()
        target=ROOT/'evidence'/args.capture
        ok=image.save(str(target))
        captures.append({'path':str(target),'saved':ok,'width':image.width(),'height':image.height()})
        print('CAPTURE '+json.dumps(captures[-1]),flush=True)
    if args.capture:QTimer.singleShot(int(args.capture_after*1000),capture)
    recorder=None
    if args.record:
        from recording import RenderRecorder
        recorder=RenderRecorder(window,ROOT/'evidence'/args.record,seconds=args.record_seconds)
        def begin_record():
            window.setProperty('recordingActive',True)
            if render_pump:render_pump.stop()  # The recorder supplies its own readbacks.
            if args.record_launch:lab.replayLaunch()
            recorder.start()
            if args.scenario:
                for delay,state in [(0,'IDLE'),(3000,'LISTENING'),(6000,'THINKING'),(9000,'SPEAKING'),(12000,'IDLE')]:
                    QTimer.singleShot(delay,lambda state=state:lab.setState(state))
                scene=window.findChild(__import__('PySide6.QtQuick',fromlist=['QQuickItem']).QQuickItem,'nucleusView')
                for delay,x,y in [(12500,-1,.4),(13500,1,-.4),(14500,0,0)]:
                    QTimer.singleShot(delay,lambda x=x,y=y:(scene.setProperty('hoverX',x),scene.setProperty('hoverY',y)))
        QTimer.singleShot(2500,begin_record)
    validation=None
    if args.validate:
        from validate_preview import LabValidation
        validation=LabValidation(window,lab,app)
        validation.forced_render=args.force_render
        QTimer.singleShot(4000,validation.start)
    if args.validate_launch:
        from validate_projection import ProjectionValidation
        validation=ProjectionValidation(window,lab,app)
        QTimer.singleShot(1400,validation.start)
    if args.validate_reaction:
        from validate_reaction import ReactionValidation
        validation=ReactionValidation(window,lab,app)
        QTimer.singleShot(1400,validation.start)
    if args.duration:QTimer.singleShot(int(args.duration*1000),app.quit)
    started=time.perf_counter()
    result=app.exec()
    import numpy as np
    times=np.asarray(lab._frame_times)
    delta=np.diff(times)*1000
    warm=times[1:]-started>2 if len(times)>1 else np.array([],dtype=bool)
    clean=delta[warm] if len(delta) else delta
    report={'duration_seconds':time.perf_counter()-started,'frame_count':len(times),'quality_mode':args.quality,'state':args.state,'captures':captures,'requests':lab.requests,
            'display':display,
            'forced_readback_pump':args.force_render,
            'window_exposed':window.isExposed(),
            'window_active':window.isActive(),
            'window_observations_during_run':{'samples':len(exposure_samples),'exposed_samples':sum(s['exposed'] for s in exposure_samples),'active_samples':sum(s['active'] for s in exposure_samples)},
            'median_frame_ms':float(np.median(clean)) if len(clean) else None,
            'p95_frame_ms':float(np.percentile(clean,95)) if len(clean) else None,
            'p99_frame_ms':float(np.percentile(clean,99)) if len(clean) else None,
            'one_percent_low_fps':1000/float(np.percentile(clean,99)) if len(clean) and np.percentile(clean,99)>0 else None,
            'mean_presented_fps_after_warmup':1000/float(np.mean(clean)) if len(clean) else None,
            'messages':messages}
    from PySide6.QtQuick import QQuickItem
    scene=window.findChild(QQuickItem,'nucleusView')
    aura_item = window.findChild(
        QQuickItem,
        'globalFireParticleLayer',
    )

    report['quick3d_stats'] = {
        key: scene.property(key)
        for key in (
            'rendererFps',
            'drawCalls',
            'drawnVertices',
            'imageBytes',
            'particleCount',
        )
    }

    report['quick3d_stats']['orbitalParticleCount'] = (
        aura_item.property('activeCount')
        if aura_item is not None
        else None
    )
    report['qml_errors']=[m for m in messages if any(s in m.lower() for s in ('failed to compile','failed to find include','shader compilation failed','referenceerror','typeerror','binding loop','cannot assign'))]
    csv_path=ROOT/'evidence'/(Path(args.report).stem+'_frames.csv')
    csv_path.write_text('seconds,frame_interval_ms\n'+'\n'.join(f'{stamp-started:.6f},{interval:.6f}' for stamp,interval in zip(times[1:],delta)))
    if recorder:
        recorder.timer.stop()
        if hasattr(recorder,'thread'):recorder.thread.join(timeout=10)
        report['recording_error']=recorder.error
    (ROOT/'evidence'/args.report).write_text(json.dumps(report,indent=2))
    # Destroy the engine while the context objects and diagnostic sink still exist.
    import shiboken6
    shiboken6.delete(engine)
    qInstallMessageHandler(None)
    log.close()
    return result or (3 if report['qml_errors'] else 0)

if __name__=='__main__':raise SystemExit(main())
