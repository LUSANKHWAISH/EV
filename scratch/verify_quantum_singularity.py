import os
import sys
from pathlib import Path

ROOT = Path("d:/EV/prototypes/cinematic_v4")
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterType
from PySide6.QtQuick import QQuickItem

from geometry import (
    LabGeometry,
    ParticleInstances,
    OrbitalParticleInstances,
    CosmicDepthInstances,
)
from presentation import PresentationModel

def run_test():
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    
    qmlRegisterType(LabGeometry, 'EVLab', 1, 0, 'LabGeometry')
    qmlRegisterType(ParticleInstances, 'EVLab', 1, 0, 'ParticleInstances')
    qmlRegisterType(OrbitalParticleInstances, 'EVLab', 1, 0, 'OrbitalParticleInstances')
    qmlRegisterType(CosmicDepthInstances, 'EVLab', 1, 0, 'CosmicDepthInstances')
    
    lab = PresentationModel()
    lab.setState('IDLE')
    lab.finishLaunch()
    
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('lab', lab)
    engine.rootContext().setContextProperty('startExpanded', False)
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml/LabWindow.qml')))
    
    if not engine.rootObjects():
        print("Engine failed to load")
        sys.exit(1)
        
    window = engine.rootObjects()[0]
    window.resize(1920, 1080)
    
    stage = window.findChild(QQuickItem, 'cinematicStage')
    if stage:
        stage.setProperty('visualTheme', 'quantum_singularity')
        stage.setProperty('cosmicDepthEnabled', True)
        
    out_dir = Path("d:/EV/scratch/quantum_singularity_renders")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    def step1_idle():
        img = window.grabWindow()
        path = str(out_dir / "singularity_idle.png")
        img.save(path)
        print(f"Captured IDLE: {path}")
        
        # Switch to SPEAKING state
        lab.setState('SPEAKING')
        QTimer.singleShot(1000, step2_speaking)
        
    def step2_speaking():
        img = window.grabWindow()
        path = str(out_dir / "singularity_speaking.png")
        img.save(path)
        print(f"Captured SPEAKING: {path}")
        
        # Switch to MUSIC mode
        stage.setProperty('musicActive', True)
        QTimer.singleShot(800, step3_music)
        
    def step3_music():
        img = window.grabWindow()
        path = str(out_dir / "singularity_music.png")
        img.save(path)
        print(f"Captured MUSIC: {path}")
        app.quit()
        
    QTimer.singleShot(1500, step1_idle)
    app.exec()
    print("Verification capture finished successfully!")

if __name__ == '__main__':
    run_test()
