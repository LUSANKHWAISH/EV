"""Bounded audible Qt startup and settings check, isolated from execution services."""
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

os.environ['QML_DISABLE_DISK_CACHE'] = '1'
os.environ['EV_STARTUP_AUDIO'] = 'true'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
from PySide6.QtCore import QObject, QPoint, QSettings, QTimer, QUrl, Qt, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge
from .integration import configure_cinematic, attach_cinematic_window

DEST = Path(__file__).resolve().parent/'evidence/startup_audio'


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    messages, phases, playback, checks, commands = [], [], [], [], []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QGuiApplication(['startup-audio-validation'])
    settings = QSettings(str(DEST/'validation-settings.ini'), QSettings.Format.IniFormat)
    settings.setValue('muted', False)
    settings.setValue('volume', .55)
    engine = QQmlApplicationEngine()
    bridge = GuiBridge(EVEventBus(initial_state=EVState.IDLE))
    bridge.taskSubmitted.connect(lambda text:commands.append(text))
    engine.rootContext().setContextProperty('guiBridge', bridge)
    with patch('prototypes.cinematic_v4.startup_audio.QSettings', return_value=settings):
        path = configure_cinematic(engine, bridge)
    model = engine._cinematic_model
    audio = model.startupAudio
    started = time.perf_counter()
    audio.phaseChanged.connect(lambda phase:phases.append({'phase':phase,'seconds':time.perf_counter()-started,'progress':model.launchProgress}))
    for name, effect in audio._effects.items():
        effect.playingChanged.connect(lambda n=name,e=effect:playback.append({'asset':n,'playing':e.isPlaying(),'seconds':time.perf_counter()-started}))
    engine.load(QUrl.fromLocalFile(str(path)))
    if not engine.rootObjects():
        print(messages)
        return 2
    window = engine.rootObjects()[0]
    attach_cinematic_window(engine, window)
    # Full-window readback is reliable in this remote display; not an FPS test.
    pump = QTimer(window)
    pump.setInterval(33)
    pump.timeout.connect(lambda:window.grabWindow())
    pump.start()
    stage = window.findChild(QQuickItem, 'cinematicStage')

    def check(name, condition, detail=None):
        checks.append({'name':name,'passed':bool(condition),'detail':detail})

    def click(name):
        item = window.findChild(QQuickItem, name)
        position = item.mapToScene(item.boundingRect().center()).toPoint()
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, position)

    def inspect_sequence():
        check('once_in_correct_order', [p['phase'] for p in phases] == ['rise', 'arrival', 'complete'], phases)
        arrival = next((p for p in phases if p['phase']=='arrival'), {})
        check('arrival_follows_completed_core', arrival.get('progress') == 1.)
        check('both_assets_reached_playing', all(any(p['asset']==name and p['playing'] for p in playback) for name in ('rise','arrival')), playback)
        check('completed_without_active_output', not any(e.isPlaying() for e in audio._effects.values()))
        window.grabWindow().save(str(DEST/'connected.png'))
        model.replayLaunch()
        stage.setProperty('drawer', 'settings')
        QTimer.singleShot(500, inspect_settings)

    def inspect_settings():
        window.grabWindow().save(str(DEST/'settings.png'))
        toggle = window.findChild(QQuickItem, 'startupSoundToggle')
        slider = window.findChild(QQuickItem, 'startupVolume')
        check('startup_controls_exist', toggle is not None and slider is not None)
        click('startupSoundToggle')
        check('mute_button_works', audio.muted and not slider.isEnabled())
        click('startupSoundToggle')
        check('unmute_button_works', not audio.muted and slider.isEnabled())
        # Keyboard operates the actual Qt slider, including onMoved wiring.
        slider.forceActiveFocus()
        QTest.keyClick(window, Qt.Key.Key_Left)
        check('volume_slider_works', abs(audio.volume-.50)<.001, audio.volume)
        reloaded = QSettings(settings.fileName(), QSettings.Format.IniFormat)
        check('settings_saved', reloaded.value('muted', type=bool) is False and abs(reloaded.value('volume', type=float)-.50)<.001)
        window.resize(1100, 760)
        QTimer.singleShot(500, finish)

    def finish():
        window.grabWindow().save(str(DEST/'settings_1100.png'))
        check('visual_replay_remains_silent', len(phases) == 3 and audio._phase == 'complete')
        check('no_commands_emitted', commands == [])
        errors = [m for m in messages if any(token in m.lower() for token in ('referenceerror','typeerror','binding loop','failed to load','cannot assign','traceback'))]
        check('no_qml_errors', not errors, errors)
        result = {'passed':all(c['passed'] for c in checks),'audio_outputs':[d.description() for d in QMediaDevices.audioOutputs()],
                  'scope':'Real QSoundEffect playback and QML controls; isolated GuiBridge, no executor or microphone. Forced readback, not a performance benchmark.',
                  'checks':checks,'phases':phases,'playback':playback}
        (DEST/'rendered_validation.json').write_text(json.dumps(result,indent=2))
        (DEST/'rendered_diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
        print(json.dumps(result),flush=True)
        app.exit(0 if result['passed'] else 1)

    QTimer.singleShot(10500, inspect_sequence)
    QTimer.singleShot(20000, app.quit)
    result = app.exec()
    audio.cancel()
    bridge.shutdown()
    return result


if __name__ == '__main__':
    raise SystemExit(main())
