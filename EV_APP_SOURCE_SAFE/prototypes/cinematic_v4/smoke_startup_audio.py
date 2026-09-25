"""Normal gui.app bootstrap with audible startup, then a clean bounded shutdown."""
import json
import os
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

os.environ['EV_TTS_ENABLED'] = 'false'
os.environ['EV_STARTUP_AUDIO'] = 'true'
from PySide6.QtCore import QTimer, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from .integration import attach_cinematic_window

DEST = Path(__file__).resolve().parent/'evidence/startup_audio'


def main():
    messages, phases = [], []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    sys.excepthook = lambda kind, value, tb: messages.append('Python callback error: '+''.join(traceback.format_exception(kind, value, tb)))
    app = QGuiApplication(['ev-startup-audio-smoke'])
    started = time.perf_counter()
    report = {'scope':'Actual gui.app, normal threaded rendering. No tasks, microphone or conversational TTS. Startup audio uses current user preferences.'}

    def attach(engine, window):
        model = engine._cinematic_model
        audio = model.startupAudio

        def capture():
            report.update({'visible':window.isVisible(),'launch_progress':model.launchProgress,
                           'phase':audio._phase,'muted':audio.muted,'volume':audio.volume,
                           'native_chrome':getattr(app,'_ev_windows_native_chrome',None) is not None,
                           'capture_saved':window.grabWindow().save(str(DEST/'main_app.png'))})
            app.quit()

        def phase_changed(phase):
            phases.append({'phase':phase,'seconds':time.perf_counter()-started,'progress':model.launchProgress})
            if phase in ('complete', 'cancelled'):
                QTimer.singleShot(500 if phase == 'complete' else 4000, capture)

        audio.phaseChanged.connect(phase_changed)
        attach_cinematic_window(engine, window)

    QTimer.singleShot(25000, app.quit)
    sys.argv = ['gui.app']
    from gui.app import main as ev_main
    with patch('prototypes.cinematic_v4.integration.attach_cinematic_window', attach):
        try:
            ev_main()
        except SystemExit as exc:
            report['exit_code'] = exc.code
    report['phases'] = phases
    report['errors'] = [m for m in messages if any(token in m.lower() for token in ('referenceerror','typeerror','binding loop','failed to load','cannot assign','python callback error'))]
    report['passed'] = (report.get('visible') and report.get('native_chrome') and report.get('launch_progress') == 1.
                        and report.get('phase') == 'complete' and report.get('capture_saved') and report.get('exit_code') == 0 and not report['errors'])
    (DEST/'main_app_smoke.json').write_text(json.dumps(report,indent=2))
    (DEST/'main_app_diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
    print(json.dumps(report),flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
