import os
import sys
from pathlib import Path

ROOT = Path("d:/EV/prototypes/cinematic_v4")
sys.path.insert(0, str(ROOT))

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

def run():
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
    
    # Connect warnings
    def on_warning(warnings):
        for w in warnings:
            print("QML WARNING:", w.toString())
    engine.warnings.connect(on_warning)
    
    engine.load(QUrl.fromLocalFile(str(ROOT / 'qml/LabWindow.qml')))
    
    window = engine.rootObjects()[0]
    stage = window.findChild(QQuickItem, 'cinematicStage')
    print("Stage found:", stage is not None)
    if stage:
        print("Initial visualTheme:", stage.property('visualTheme'))
        stage.setProperty('visualTheme', 'quantum_singularity')
        print("Updated visualTheme:", stage.property('visualTheme'))
        
        rear = window.findChild(QQuickItem, 'quantumSingularityRearLayer')
        front = window.findChild(QQuickItem, 'quantumSingularityFrontLayer')
        print("Rear layer found:", rear is not None, "visible:", rear.property('visible') if rear else None)
        print("Front layer found:", front is not None, "visible:", front.property('visible') if front else None)
        
    QTimer.singleShot(500, app.quit)
    app.exec()

if __name__ == '__main__':
    run()
