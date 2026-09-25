"""Bounded real application startup check; never submits a task or starts TTS."""
import os
import sys
import json
import argparse
from pathlib import Path
os.environ['EV_TTS_ENABLED']='false'
os.environ.setdefault('QSG_RHI_BACKEND','d3d11')
os.environ['QML_DISABLE_DISK_CACHE']='1'
from PySide6.QtCore import QTimer,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickWindow,QQuickItem

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--classic',action='store_true')
    parser.add_argument('--force-render',action='store_true')
    parser.add_argument('--report',default='connected_startup.json')
    args=parser.parse_args()
    destination=ROOT/'evidence'/args.report
    destination.parent.mkdir(parents=True,exist_ok=True)
    messages=[];report={'interface':'classic' if args.classic else 'cinematic_default','scope':'Actual gui.app bootstrap, native chrome, provider configuration and normal observational subsystems. No task submission, approval, network model request or TTS startup.'}
    def log(kind,context,message):messages.append(message)
    qInstallMessageHandler(log)
    app=QGuiApplication(['ev-cinematic-startup-check'])
    def capture():
        windows=[w for w in app.allWindows() if isinstance(w,QQuickWindow) and w.isVisible() and (args.classic or w.objectName()=='cinematicWindow')]
        report['window_count']=len(windows)
        if windows:
            window=windows[0];stage=window.findChild(QQuickItem,'cinematicStage');scene=window.findChild(QQuickItem,'nucleusView')
            report.update({'visible':window.isVisible(),'stage_enabled':stage.isEnabled() if stage else args.classic,'renderer_fps':scene.property('rendererFps') if scene else None,
                           'launch_progress':scene.property('launchProgress') if scene else None,
                           'cinematic_stage_present':stage is not None,
                           'native_chrome_attached':getattr(app,'_ev_windows_native_chrome',None) is not None})
            report['capture_saved']=window.grabWindow().save(str(destination.with_suffix('.png')))
    # Production bootstrap can take several seconds before the first frame.
    # Measure the one-shot projection after presentation, not process startup.
    armed=False
    pump=QTimer(app)
    report['forced_readback_pump']=args.force_render
    def first_frame():
        nonlocal armed
        if armed:return
        armed=True
        QTimer.singleShot(4600,capture)
        QTimer.singleShot(5700,app.quit)
    def watch_window():
        windows=[w for w in app.allWindows() if isinstance(w,QQuickWindow) and w.isVisible()]
        if not windows:
            QTimer.singleShot(100,watch_window)
            return
        windows[0].frameSwapped.connect(first_frame)
        windows[0].update()
        if args.force_render:
            window=windows[0]
            if not window.grabWindow().isNull():first_frame()
            pump.setInterval(33);pump.timeout.connect(lambda:window.grabWindow());pump.start()
    QTimer.singleShot(100,watch_window)
    QTimer.singleShot(25000,app.quit)
    sys.argv=['gui.app']+(['--classic'] if args.classic else [])
    from gui.app import main as ev_main
    try:ev_main()
    except SystemExit as exc:report['exit_code']=exc.code
    report['qml_errors']=[m for m in messages if any(s in m.lower() for s in ('referenceerror','typeerror','binding loop','failed to load','cannot assign','shader compilation failed'))]
    report['passed']=report.get('window_count')==1 and report.get('visible') and report.get('stage_enabled') and report.get('cinematic_stage_present') is (not args.classic) and (args.classic or report.get('launch_progress')==1) and report.get('capture_saved') and report.get('exit_code')==0 and not report['qml_errors']
    destination.write_text(json.dumps(report,indent=2))
    destination.with_name(destination.stem+'_diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
