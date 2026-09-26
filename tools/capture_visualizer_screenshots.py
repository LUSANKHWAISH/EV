"""
Capture offscreen screenshots of the redesigned reference-based visualizers in EV Music.
Captures:
1. Studio SPAN Analyzer (Reference 2 & 3): Dual curves, dB grid, correlation meter, level meters.
2. Reference Trio (Reference 1, 4, 5): Ceiling Rain needles + Flow Trace glowing curve + Segment Stack.
3. Single Flow Trace (Reference 1): Luminous organic curve.
4. Single Ceiling Rain (Reference 5): High-density vertical needle spectrum.
At 1920x1080 and 1100x760 resolutions.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time
import shutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import QEventLoop, QTimer, QUrl, QSize
from PySide6.QtGui import QGuiApplication, QImage
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


def capture_visualizers() -> int:
    print("=== CAPTURING REDESIGNED VISUALIZER SCREENSHOTS ===")

    out_dir = PROJECT_ROOT / "test_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path(r"C:\Users\LUSAN\.gemini\antigravity-ide\brain\bf85add0-b13e-4311-8771-1b6f5c458df0")

    temp_dir = tempfile.TemporaryDirectory(prefix="ev-vis-shot-")
    temp_path = Path(temp_dir.name)
    os.environ["EV_USER_DATA_DIR"] = str(temp_path)

    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([sys.argv[0], "-platform", "offscreen"])

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
    attach_cinematic_window(engine, window)

    def wait(ms: int) -> None:
        loop = QEventLoop()
        QTimer.singleShot(ms, loop.quit)
        loop.exec()
        app.processEvents()

    wait(200)

    cinematic_model = getattr(engine, "_cinematic_model", None)
    bridge.setExperienceMode("MUSIC")
    if cinematic_model and hasattr(cinematic_model, "openMusic"):
        cinematic_model.openMusic()
    wait(300)

    music = cinematic_model.music if cinematic_model else None
    if not music:
        print("ERROR: Music session not attached")
        return 1

    # Load audio file (arrival.wav)
    test_audio = get_resource_root() / "prototypes" / "cinematic_v4" / "assets" / "startup" / "arrival.wav"
    if test_audio.exists():
        music.addFiles([QUrl.fromLocalFile(str(test_audio))])
        wait(200)

    # Set attractive EQ profile
    test_curve = [4.5, 3.5, 2.0, 0.0, -1.5, -1.0, 1.5, 3.0, 4.0, 5.0]
    for i, g in enumerate(test_curve):
        music.setBandGain(i, g)
    music.setPreamp(-1.0)
    music.playIndex(0)
    wait(400)

    def ensure_playing_peak():
        if not music.playing or music.position > 2400:
            music.playIndex(0)
            music.seek(700)
            wait(250)
        else:
            wait(200)

    saved_shots = []

    # 1. Capture STUDIO SPAN (Precision Spectrum) at 1920x1080
    music.setLayout("studio-span")
    window.resize(QSize(1920, 1080))
    ensure_playing_peak()
    shot_span_1080 = out_dir / "visualizer_studio_span_1920x1080.png"
    img1 = window.grabWindow()
    img1.save(str(shot_span_1080))
    saved_shots.append(shot_span_1080)
    print(f"[PASS] Saved Studio SPAN (1920x1080) to {shot_span_1080}")

    # 2. Capture STUDIO SPAN at compact 1100x760
    window.resize(QSize(1100, 760))
    ensure_playing_peak()
    shot_span_1100 = out_dir / "visualizer_studio_span_1100x760.png"
    img2 = window.grabWindow()
    img2.save(str(shot_span_1100))
    saved_shots.append(shot_span_1100)
    print(f"[PASS] Saved Studio SPAN (1100x760) to {shot_span_1100}")

    # 3. Capture REFERENCE TRIO at 1920x1080 (Ceiling Rain needles + Flow Trace glowing curve + Segment Stack)
    music.setLayout("reference-trio")
    window.resize(QSize(1920, 1080))
    ensure_playing_peak()
    shot_trio_1080 = out_dir / "visualizer_reference_trio_1920x1080.png"
    img3 = window.grabWindow()
    img3.save(str(shot_trio_1080))
    saved_shots.append(shot_trio_1080)
    print(f"[PASS] Saved Reference Trio (1920x1080) to {shot_trio_1080}")

    # 4. Capture SINGLE TRACE (Luminous Organic Flow Trace) at 1920x1080
    music.setLayout("single-trace")
    window.resize(QSize(1920, 1080))
    ensure_playing_peak()
    shot_trace_1080 = out_dir / "visualizer_single_trace_1920x1080.png"
    img4 = window.grabWindow()
    img4.save(str(shot_trace_1080))
    saved_shots.append(shot_trace_1080)
    print(f"[PASS] Saved Single Trace (1920x1080) to {shot_trace_1080}")

    # 5. Capture SINGLE RAIN (High-Density Needle Spectrum) at 1920x1080
    music.setLayout("single-rain")
    window.resize(QSize(1920, 1080))
    ensure_playing_peak()
    shot_rain_1080 = out_dir / "visualizer_single_needles_1920x1080.png"
    img5 = window.grabWindow()
    img5.save(str(shot_rain_1080))
    saved_shots.append(shot_rain_1080)
    print(f"[PASS] Saved Single Needles (1920x1080) to {shot_rain_1080}")

    # 6. Capture SINGLE STACK (Segment Stack Horizontal LED Ladder) at 1920x1080
    music.setLayout("single-stack")
    window.resize(QSize(1920, 1080))
    ensure_playing_peak()
    shot_stack_1080 = out_dir / "visualizer_single_stack_1920x1080.png"
    img6 = window.grabWindow()
    img6.save(str(shot_stack_1080))
    saved_shots.append(shot_stack_1080)
    print(f"[PASS] Saved Single Stack (1920x1080) to {shot_stack_1080}")

    # Copy all to artifact directory for embedding
    if artifact_dir.exists():
        for s in saved_shots:
            try:
                shutil.copy(s, artifact_dir / s.name)
                print(f"[PASS] Copied {s.name} to artifact directory")
            except Exception as e:
                print(f"[WARN] Failed to copy {s.name}: {e}")

    # Clean shutdown
    music.close()
    bridge.shutdown()
    temp_dir.cleanup()

    print("=== VISUALIZER CAPTURE COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(capture_visualizers())
