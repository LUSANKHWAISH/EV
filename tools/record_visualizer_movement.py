"""
Record a short video demonstration of EV Music visualizer movement with real music.
Demonstrates:
1. Real music playback with dynamic visualizer movement (Reference Trio: Needles + Flow Trace + Segment Stack).
2. Pause toggle (decay of meters and clearance of beat response).
3. Resuming playback and dynamic layout switch to STUDIO SPAN Analyzer (genuine 256-pt spectrum + EQ curve).
Encodes video to MP4 using ffmpeg.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ["EV_STARTUP_AUDIO"] = "false"
os.environ["QSG_RENDER_LOOP"] = "basic"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"

from PySide6.QtCore import QEventLoop, QTimer, QUrl, QSize
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtQuickControls2 import QQuickStyle

from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.paths import get_resource_root
from core.provider_config import AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge
from prototypes.cinematic_v4.integration import attach_cinematic_window, configure_cinematic


def record_movement_demo() -> int:
    print("=== RECORDING VISUALIZER MOVEMENT DEMONSTRATION ===")

    out_dir = PROJECT_ROOT / "test_runtime"
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = Path(r"C:\Users\LUSAN\.gemini\antigravity-ide\brain\bf85add0-b13e-4311-8771-1b6f5c458df0")

    temp_app_dir = tempfile.TemporaryDirectory(prefix="ev-rec-app-")
    temp_frames_dir = tempfile.TemporaryDirectory(prefix="ev-rec-frames-")
    temp_app_path = Path(temp_app_dir.name)
    frames_path = Path(temp_frames_dir.name)
    os.environ["EV_USER_DATA_DIR"] = str(temp_app_path)

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
        config_path=temp_app_path / "providers.json",
        credential_store=DPAPICredentialStore(store_path=temp_app_path / "credentials.bin"),
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

    test_audio = get_resource_root() / "prototypes" / "cinematic_v4" / "assets" / "startup" / "arrival.wav"
    if test_audio.exists():
        music.addFiles([QUrl.fromLocalFile(str(test_audio))])
        wait(200)

    # Set attractive EQ profile
    test_curve = [4.5, 3.5, 2.0, 0.0, -1.5, -1.0, 1.5, 3.0, 4.0, 5.0]
    for i, g in enumerate(test_curve):
        music.setBandGain(i, g)
    music.setPreamp(-1.0)

    # Use 1280x720 video resolution
    window.resize(QSize(1280, 720))
    music.setLayout("reference-trio")
    music.playIndex(0)
    wait(300)

    total_frames = 100
    fps = 25
    frame_interval_ms = int(1000 / fps)

    print(f"Recording {total_frames} frames ({total_frames / fps:.1f}s) of real playback, pause & layout switch...")

    for frame_idx in range(total_frames):
        # Action schedule:
        # Frames 0-35 (0.0s - 1.4s): Active playback in reference-trio layout
        # Frame 36: Toggle pause
        if frame_idx == 36:
            print(f"  Frame {frame_idx}: Toggling PAUSE")
            music.togglePlayback()

        # Frame 56: Toggle resume and switch layout to studio-span
        if frame_idx == 56:
            print(f"  Frame {frame_idx}: Resuming PLAYBACK & switching layout to STUDIO SPAN")
            music.togglePlayback()
            music.setLayout("studio-span")

        wait(frame_interval_ms)

        img = window.grabWindow()
        frame_file = frames_path / f"frame_{frame_idx:04d}.png"
        img.save(str(frame_file))

    print("All frames captured. Encoding MP4 video via ffmpeg...")
    out_mp4 = out_dir / "visualizer_movement_recording.mp4"

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate", str(fps),
        "-i", str(frames_path / "frame_%04d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-preset", "fast",
        str(out_mp4),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"FFmpeg error: {res.stderr}")
        return 1

    print(f"[PASS] Successfully encoded recording to {out_mp4} ({out_mp4.stat().st_size} bytes)")

    # Copy to artifact directory
    if artifact_dir.exists():
        target = artifact_dir / out_mp4.name
        shutil.copy(out_mp4, target)
        print(f"[PASS] Copied recording to {target}")

    music.close()
    bridge.shutdown()
    temp_app_dir.cleanup()
    temp_frames_dir.cleanup()

    print("=== RECORDING COMPLETE ===")
    return 0


if __name__ == "__main__":
    sys.exit(record_movement_demo())
