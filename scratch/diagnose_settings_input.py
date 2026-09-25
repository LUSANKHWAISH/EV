"""Diagnostic script for settings input ownership with bounded waits and guaranteed cleanup."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
from unittest.mock import MagicMock

os.environ['EV_STARTUP_AUDIO'] = 'false'
os.environ['QML_DISABLE_DISK_CACHE'] = '1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QEventLoop, QTimer, QUrl, Qt, qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import configure_cinematic, attach_cinematic_window

def main():
    messages = []
    qInstallMessageHandler(lambda kind, context, message: messages.append(message))
    app = QGuiApplication(['diagnostic'])
    
    # 60s hard timeout
    timeout_timer = QTimer()
    timeout_timer.setSingleShot(True)
    timeout_timer.timeout.connect(lambda: (print("ERROR: Diagnostic timed out after 60s", flush=True), os._exit(2)))
    timeout_timer.start(60000)

    temporary = tempfile.TemporaryDirectory(prefix='ev-diag-')
    scratch = Path(temporary.name)
    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    bridge.set_experience_manager(EVExperienceManager(bus))
    store = AIProviderConfigStore(config_path=scratch/'providers.json', credential_store=DPAPICredentialStore(store_path=scratch/'credentials.bin'))
    bridge.set_provider_config_store(store)
    bridge._get_core_style_path = lambda: scratch/'core_style.json'
    
    provider = next(p for p in json.loads(bridge.getProvidersJson()) if p['provider_type'] == 'Gemini')
    bridge.saveProvider(json.dumps(provider), 'visual-test-key-not-a-real-credential')
    bridge.setActiveProvider(provider['id'])
    
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('guiBridge', bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine, bridge))))
    if not engine.rootObjects():
        print("Failed to load QML root objects", flush=True)
        return 1
    
    window = engine.rootObjects()[0]
    attach_cinematic_window(engine, window)
    model = engine._cinematic_model

    def wait(ms):
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()

    def item(name):
        control = window.findChild(QQuickItem, name)
        if control is None:
            pending = [window.contentItem()]
            while pending:
                candidate = pending.pop()
                if candidate.objectName() == name:
                    control = candidate
                    break
                pending.extend(candidate.childItems())
        if control is None:
            raise AssertionError('Missing ' + name)
        return control

    results = {}
    try:
        stage = item('cinematicStage')
        overlay = item('settingsOverlay')
        
        print("Opening provider settings...", flush=True)
        model.openProviderSettings()
        
        # Bounded wait for overlay-open condition
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if bridge.settingsVisible and overlay.property('visible') and not stage.isEnabled():
                break
            wait(50)
            
        results['overlay_opened'] = bool(bridge.settingsVisible and overlay.property('visible'))
        results['stage_disabled_while_open'] = not stage.isEnabled()
        print(f"Overlay opened: {results['overlay_opened']}, Stage disabled: {results['stage_disabled_while_open']}", flush=True)
        
        # Test input isolation:
        # Check that clicking stage or stage controls while Settings is open does not trigger stage actions
        # Check drawer button / music button / expand button
        music_btn = item('musicButton')
        music_active_before = model.experienceMode == 'MUSIC'
        pt = music_btn.mapToScene(music_btn.boundingRect().center()).toPoint()
        print(f"Attempting click on underlying musicButton at {pt}...", flush=True)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
        wait(100)
        music_active_after = model.experienceMode == 'MUSIC'
        results['underlying_blocked_while_open'] = (music_active_before == music_active_after) and (not stage.isEnabled())
        print(f"Underlying control blocked: {results['underlying_blocked_while_open']}", flush=True)
        
        # Now close settings
        print("Closing settings...", flush=True)
        bridge.closeSettings()
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if not bridge.settingsVisible and stage.isEnabled():
                break
            wait(50)
            
        results['stage_enabled_after_close'] = stage.isEnabled()
        print(f"Stage re-enabled after close: {results['stage_enabled_after_close']}", flush=True)
        
        # Test that underlying controls receive input again after close
        print("Clicking musicButton after settings closed...", flush=True)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
        wait(100)
        results['underlying_works_after_close'] = (model.experienceMode == 'MUSIC')
        print(f"Underlying control works after close: {results['underlying_works_after_close']}", flush=True)
        
    except Exception as e:
        results['error'] = traceback.format_exc()
        print(f"Exception during diagnostic: {e}", flush=True)
    finally:
        print("Cleaning up diagnostic...", flush=True)
        try:
            model.music.close()
            bridge.shutdown()
            temporary.cleanup()
        except Exception:
            pass
        print("FINAL RESULTS:", json.dumps(results, indent=2), flush=True)
        app.quit()
        
    return 0

if __name__ == '__main__':
    sys.exit(main())
