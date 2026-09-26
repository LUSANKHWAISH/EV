"""
Capture offscreen screenshots for the Layout Correction and Orange Reference task:
1. Cinematic Music with EQ closed (1920x1080 and 1100x760)
2. Cinematic Music with EQ open (1920x1080 and 1100x760)
3. Orange reference view (1920x1080 and 1100x760)
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QEventLoop, QTimer, QUrl, QSize
from PySide6.QtGui import QFont, QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickItem, QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

os.environ["EV_STARTUP_AUDIO"] = "false"
os.environ["QSG_RENDER_LOOP"] = "basic"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"

from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.paths import get_resource_root
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import attach_cinematic_window, configure_cinematic


def capture_all() -> int:
    print("=== CAPTURING CINEMATIC MUSIC & ORANGE REFERENCE SCREENSHOTS ===")

    out_dir = PROJECT_ROOT / "test_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    review_dir = out_dir / "visual_review_ec23443"
    review_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path(r"C:\Users\LUSAN\.gemini\antigravity-ide\brain\bf85add0-b13e-4311-8771-1b6f5c458df0")

    temp_dir = tempfile.TemporaryDirectory(prefix="ev-cin-music-")
    temp_path = Path(temp_dir.name)
    os.environ["EV_USER_DATA_DIR"] = str(temp_path)

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv[:1])
    app.setFont(QFont("Segoe UI", 10))

    QQuickStyle.setStyle("Basic")
    engine = QQmlApplicationEngine()
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)

    experience_manager = EVExperienceManager(event_bus)
    bridge.set_experience_manager(experience_manager)
    engine.rootContext().setContextProperty("guiBridge", bridge)

    provider_store = AIProviderConfigStore(
        config_path=temp_path / "providers.json",
        credential_store=DPAPICredentialStore(store_path=temp_path / "credentials.bin"),
    )
    bridge.set_provider_config_store(provider_store)

    qml_file = configure_cinematic(engine, bridge)
    engine.load(QUrl.fromLocalFile(str(qml_file)))
    root_objects = engine.rootObjects()
    if not root_objects:
        print("ERROR: Failed to load root QML window")
        return 1

    window: QQuickWindow = root_objects[0]
    window.resize(QSize(1920, 1080))
    window.show()
    attach_cinematic_window(engine, window)

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        app.processEvents()

    wait(300)

    cinematic_model = getattr(engine, "_cinematic_model", None)
    bridge.setExperienceMode("MUSIC")
    if cinematic_model and hasattr(cinematic_model, "openMusic"):
        cinematic_model.openMusic()
    wait(400)

    music = cinematic_model.music if cinematic_model else None
    if not music:
        print("ERROR: Music session not attached")
        return 1

    # Load audio file (arrival.wav)
    test_audio = get_resource_root() / "prototypes" / "cinematic_v4" / "assets" / "startup" / "arrival.wav"
    if test_audio.exists():
        music.addFiles([QUrl.fromLocalFile(str(test_audio))])
        wait(300)

    # Set attractive EQ profile
    test_curve = [4.5, 3.5, 2.0, 0.0, -1.5, -1.0, 1.5, 3.0, 4.0, 5.0]
    for i, g in enumerate(test_curve):
        music.setBandGain(i, g)
    music.setPreamp(-1.0)
    music.playIndex(0)
    wait(400)

    stage = window.findChild(QQuickItem, "cinematicStage")
    music_workspace = window.findChild(QQuickItem, "musicWorkspace")

    def ensure_playing_peak():
        if not music.playing or music.position > 2400:
            music.playIndex(0)
            music.seek(700)
            wait(300)
        else:
            wait(250)

    saved_shots = []

    # ----------------------------------------------------
    # 1. CINEMATIC MUSIC WITH EQ CLOSED
    # ----------------------------------------------------
    print("Capturing Cinematic Music (EQ closed)...")
    if music_workspace:
        music_workspace.setProperty("viewMode", "cinematic")
        music_workspace.setProperty("showEQEditor", False)
    if stage:
        stage.setProperty("visualTheme", "cosmic_orbit")
    wait(300)

    # 1a. 1920x1080
    window.resize(QSize(1920, 1080))
    wait(600)
    ensure_playing_peak()
    shot1_1080 = out_dir / "cinematic_music_eq_closed_1920x1080.png"
    window.grabWindow().save(str(shot1_1080))
    saved_shots.append(shot1_1080)
    print(f"  [PASS] Saved {shot1_1080.name}")

    # 1b. 1100x760
    window.resize(QSize(1100, 760))
    wait(600)
    ensure_playing_peak()
    shot1_1100 = out_dir / "cinematic_music_eq_closed_1100x760.png"
    window.grabWindow().save(str(shot1_1100))
    saved_shots.append(shot1_1100)
    print(f"  [PASS] Saved {shot1_1100.name}")

    # ----------------------------------------------------
    # 2. CINEMATIC MUSIC WITH EQ OPEN
    # ----------------------------------------------------
    print("Capturing Cinematic Music (EQ open)...")
    if music_workspace:
        music_workspace.setProperty("viewMode", "cinematic")
        music_workspace.setProperty("showEQEditor", True)
    if stage:
        stage.setProperty("visualTheme", "cosmic_orbit")
    wait(400)

    # 2a. 1920x1080
    window.resize(QSize(1920, 1080))
    wait(600)
    ensure_playing_peak()
    shot2_1080 = out_dir / "cinematic_music_eq_open_1920x1080.png"
    window.grabWindow().save(str(shot2_1080))
    saved_shots.append(shot2_1080)
    print(f"  [PASS] Saved {shot2_1080.name}")

    # 2b. 1100x760
    window.resize(QSize(1100, 760))
    wait(600)
    ensure_playing_peak()
    shot2_1100 = out_dir / "cinematic_music_eq_open_1100x760.png"
    window.grabWindow().save(str(shot2_1100))
    saved_shots.append(shot2_1100)
    print(f"  [PASS] Saved {shot2_1100.name}")

    # ----------------------------------------------------
    # 3. ORANGE REFERENCE VIEW
    # ----------------------------------------------------
    print("Capturing Orange Reference View...")
    if music_workspace:
        music_workspace.setProperty("viewMode", "orange")
        music_workspace.setProperty("showEQEditor", False)
    if stage:
        stage.setProperty("visualTheme", "stark_reactor")
    wait(500)

    # 3a. 1920x1080
    window.resize(QSize(1920, 1080))
    wait(600)
    ensure_playing_peak()
    shot3_1080 = out_dir / "orange_reference_view_1920x1080.png"
    window.grabWindow().save(str(shot3_1080))
    saved_shots.append(shot3_1080)
    print(f"  [PASS] Saved {shot3_1080.name}")

    # 3b. 1100x760
    window.resize(QSize(1100, 760))
    wait(600)
    ensure_playing_peak()
    shot3_1100 = out_dir / "orange_reference_view_1100x760.png"
    window.grabWindow().save(str(shot3_1100))
    saved_shots.append(shot3_1100)
    print(f"  [PASS] Saved {shot3_1100.name}")

    # Copy all shots to review_dir and artifact_dir
    for s in saved_shots:
        try:
            shutil.copy(s, review_dir / s.name)
            print(f"  [PASS] Copied {s.name} to {review_dir.name}")
        except Exception as e:
            print(f"  [WARN] Failed to copy {s.name} to review_dir: {e}")

        if artifact_dir.exists():
            try:
                shutil.copy(s, artifact_dir / s.name)
                print(f"  [PASS] Copied {s.name} to artifact_dir")
            except Exception as e:
                print(f"  [WARN] Failed to copy {s.name} to artifact_dir: {e}")

    # Clean shutdown
    try:
        music.close()
        bridge.shutdown()
        temp_dir.cleanup()
    except Exception:
        pass

    print("=== CAPTURE COMPLETE ===")
    os._exit(0)


if __name__ == "__main__":
    capture_all()
