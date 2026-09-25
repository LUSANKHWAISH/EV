import os
import sys
from pathlib import Path

# Ensure prototype root is in path
ROOT = Path("d:/EV/prototypes/cinematic_v4")
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickItem

from geometry import (
    LabGeometry,
    ParticleInstances,
    OrbitalParticleInstances,
    CosmicDepthInstances,
)
from presentation import PresentationModel

def capture_scenario(theme, state, out_path, wait_ms=2500):
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    
    qmlRegisterType(LabGeometry, 'EVLab', 1, 0, 'LabGeometry')
    qmlRegisterType(ParticleInstances, 'EVLab', 1, 0, 'ParticleInstances')
    qmlRegisterType(OrbitalParticleInstances, 'EVLab', 1, 0, 'OrbitalParticleInstances')
    qmlRegisterType(CosmicDepthInstances, 'EVLab', 1, 0, 'CosmicDepthInstances')
    
    lab = PresentationModel()
    lab.setState(state)
    lab.finishLaunch()
    
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('lab', lab)
    engine.rootContext().setContextProperty('startExpanded', False)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml/LabWindow.qml')))
    
    if not engine.rootObjects():
        print(f"Failed to load engine for {out_path}")
        return False
        
    window = engine.rootObjects()[0]
    window.resize(1920, 1080)
    
    stage = window.findChild(QQuickItem, 'cinematicStage')
    if stage:
        stage.setProperty('cosmicTheme', theme)
        stage.setProperty('cosmicDepthEnabled', True)
        
    captured = False
    
    def do_capture():
        nonlocal captured
        img = window.grabWindow()
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path)
        print(f"Saved: {out_path}")
        captured = True
        app.quit()
        
    QTimer.singleShot(wait_ms, do_capture)
    app.exec()
    return captured

if __name__ == '__main__':
    evidence_dir = Path("d:/EV/scratch/cosmic_evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    
    print("Capturing Cyan Idle...")
    capture_scenario(0, 'IDLE', str(evidence_dir / 'cyan_idle.png'), 2500)
    
    print("Capturing Cyan Speaking...")
    capture_scenario(0, 'SPEAKING', str(evidence_dir / 'cyan_speaking.png'), 2500)
    
    print("Capturing Gold Idle...")
    capture_scenario(1, 'IDLE', str(evidence_dir / 'gold_idle.png'), 2500)
    
    print("Capturing Gold Speaking...")
    capture_scenario(1, 'SPEAKING', str(evidence_dir / 'gold_speaking.png'), 2500)
    
    print("Capturing Hybrid...")
    capture_scenario(2, 'SPEAKING', str(evidence_dir / 'hybrid_speaking.png'), 2500)
    
    print("All captures completed successfully!")
