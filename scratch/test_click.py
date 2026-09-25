import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import configure_cinematic, attach_cinematic_window

app = None
model = None
window = None

try:
    app = QGuiApplication.instance() or QGuiApplication(['test', '-platform', 'offscreen'])
    engine = QQmlApplicationEngine()
    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    engine.rootContext().setContextProperty('guiBridge', bridge)
    qml_path = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    
    if not engine.rootObjects():
        print("ERROR: No root objects loaded", flush=True)
        sys.exit(1)
        
    window = engine.rootObjects()[0]
    attach_cinematic_window(engine, window)
    model = getattr(engine, '_cinematic_model', None)

    stage = window.findChild(QQuickItem, 'cinematicStage')
    print("Stage:", stage, flush=True)
    if stage:
        print("Stage enabled:", stage.isEnabled(), flush=True)
        
    btn = window.findChild(QQuickItem, 'expandButton')
    print("expandButton:", btn, flush=True)
    if btn:
        print("boundingRect:", btn.boundingRect(), flush=True)
        pt = btn.mapToScene(btn.boundingRect().center()).toPoint()
        print("mapped point:", pt, flush=True)
        print("Trying mouseClick on window with stage disabled...", flush=True)
        if stage:
            stage.setEnabled(False)
        QTest.mouseClick(window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pt)
        print("mouseClick done!", flush=True)
        print("Stage enabled after click:", stage.isEnabled() if stage else "N/A", flush=True)
    print("TEST_CLICK_DIAGNOSTIC_COMPLETED_SUCCESSFULLY", flush=True)
finally:
    # Guaranteed cleanup of workers and windows
    if model and hasattr(model, 'music') and model.music:
        try:
            model.music.close()
        except Exception as e:
            print("Error closing music:", e, flush=True)
    if window:
        try:
            window.close()
        except Exception as e:
            print("Error closing window:", e, flush=True)
    # Use os._exit to guarantee no hang on non-daemon native C++ media/render worker threads
    os._exit(0)

