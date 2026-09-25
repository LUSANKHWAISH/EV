import QtQuick 2.15
import QtQuick3D 1.15
import "../../theme"

Item {
    id: root
    anchors.fill: parent

    property var host: parent

    // Visual inputs
    property string stateText: host && host.stateText !== undefined ? host.stateText : "IDLE"
    property string visualMode: host && host.visualMode !== undefined ? host.visualMode : "STANDARD"
    property real energy: host && host.energy !== undefined ? host.energy : Theme.stateEnergy(stateText)
    property color stateTone: host && host.stateTone !== undefined ? host.stateTone : Theme.stateColor(stateText)
    property color displayTone: host && host.displayTone !== undefined ? host.displayTone : stateTone

    property real phase: host && host.phase !== undefined ? host.phase : 0.0
    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0

    property bool idle: stateText === "IDLE"
    property bool listening: stateText === "LISTENING"
    property bool planning: stateText === "PLANNING"
    property bool executing: stateText === "EXECUTING"
    property bool verifying: stateText === "VERIFYING"
    property bool awaiting: stateText === "AWAITING_APPROVAL"
    property bool speaking: stateText === "SPEAKING"
    property bool successful: stateText === "SUCCESS"
    property bool failed: stateText === "FAILED"
    property bool recovering: stateText === "RECOVERING"
    property bool stopped: stateText === "STOPPED"

    // Dynamic scale driven by audio
    property real dynamicScale: 1.0 + (effectiveListenLevel * 0.25) + (effectiveSpeechLevel * 0.20)
    Behavior on dynamicScale {
        SpringAnimation { spring: 3.5; damping: 0.3 }
    }

    // Dynamic rotation speeds
    property real rotationSpeedMultiplier: 
        executing ? 3.5 :
        planning ? 2.5 :
        verifying ? 2.0 :
        listening ? 1.5 + effectiveListenLevel :
        speaking ? 1.5 + effectiveSpeechLevel :
        failed ? 4.0 :
        1.0
        
    Behavior on rotationSpeedMultiplier {
        NumberAnimation { duration: 800; easing.type: Easing.InOutQuad }
    }

    // Dynamic Z Depth
    property real sceneZDepth:
        executing ? 30.0 :
        verifying ? 15.0 :
        awaiting ? 40.0 :
        failed ? -30.0 :
        0.0

    Behavior on sceneZDepth {
        SpringAnimation { spring: 2.0; damping: 0.25 }
    }

    View3D {
        id: core3D
        anchors.fill: parent
        camera: camera

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 300 - sceneZDepth)
            fieldOfView: 45
            clipNear: 1
            clipFar: 1000
            
            Behavior on position {
                SpringAnimation { spring: 2.5; damping: 0.3 }
            }
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-30, 45, -10)
            color: "#FFFFFF"
            brightness: 1.8
            ambientColor: Qt.rgba(0.05, 0.08, 0.12, 1.0)
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(30, -45, 10)
            color: root.displayTone
            brightness: 0.8
        }

        PointLight {
            position: Qt.vector3d(0, 0, 0)
            color: root.displayTone
            brightness: 2.5 + (effectiveListenLevel * 2.0) + (effectiveSpeechLevel * 2.0)
            constantFade: 1.0
            linearFade: 0.01
            quadraticFade: 0.0001
        }

        // --- Materials ---

        PrincipledMaterial {
            id: nucleusMaterial
            baseColor: root.displayTone
            metalness: 0.1
            roughness: 0.2
            clearcoatAmount: 0.8
            clearcoatRoughnessAmount: 0.1
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * (1.5 + effectiveListenLevel * 2.0 + effectiveSpeechLevel * 2.0),
                root.displayTone.g * (1.5 + effectiveListenLevel * 2.0 + effectiveSpeechLevel * 2.0),
                root.displayTone.b * (1.5 + effectiveListenLevel * 2.0 + effectiveSpeechLevel * 2.0)
            )
        }

        PrincipledMaterial {
            id: innerShellMaterial
            baseColor: Qt.rgba(root.displayTone.r, root.displayTone.g, root.displayTone.b, 0.4)
            metalness: 0.3
            roughness: 0.1
            transmissionFactor: 0.8
            clearcoatAmount: 1.0
            alphaMode: PrincipledMaterial.Blend
        }
        
        PrincipledMaterial {
            id: outerShellMaterial
            baseColor: Qt.rgba(root.displayTone.r * 0.5, root.displayTone.g * 0.5, root.displayTone.b * 0.5, 0.2)
            metalness: 0.5
            roughness: 0.3
            transmissionFactor: 0.6
            clearcoatAmount: 0.5
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: orbitRingMaterial
            baseColor: root.displayTone
            metalness: 0.8
            roughness: 0.2
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * 0.8,
                root.displayTone.g * 0.8,
                root.displayTone.b * 0.8
            )
        }
        
        PrincipledMaterial {
            id: particleMaterial
            baseColor: "#FFFFFF"
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * 2.0,
                root.displayTone.g * 2.0,
                root.displayTone.b * 2.0
            )
        }

        // --- Geometry Nodes ---

        Node {
            id: sceneRoot
            scale: Qt.vector3d(dynamicScale, dynamicScale, dynamicScale)

            // Central Nucleus
            Model {
                id: nucleus
                source: "#Sphere"
                scale: Qt.vector3d(0.35, 0.35, 0.35)
                materials: [nucleusMaterial]
                
                // Audio reactive bounce and subtle pulse
                property real bounce: Math.sin(root.phase * 2.0) * 0.05
                scale: Qt.vector3d(
                    0.35 + bounce + (effectiveListenLevel * 0.15) + (effectiveSpeechLevel * 0.15),
                    0.35 + bounce + (effectiveListenLevel * 0.15) + (effectiveSpeechLevel * 0.15),
                    0.35 + bounce + (effectiveListenLevel * 0.15) + (effectiveSpeechLevel * 0.15)
                )
            }

            // Inner Transmissive Shell
            Model {
                id: innerShell
                source: "#Sphere"
                materials: [innerShellMaterial]
                
                property real shellScale: 
                    root.planning ? 0.6 :
                    root.executing ? 0.7 :
                    0.55
                    
                Behavior on shellScale {
                    SpringAnimation { spring: 2.0; damping: 0.3 }
                }
                
                scale: Qt.vector3d(shellScale, shellScale, shellScale)
                eulerRotation: Qt.vector3d(root.phase * 15 * rotationSpeedMultiplier, root.phase * 20 * rotationSpeedMultiplier, 0)
            }

            // Outer Transmissive Shell
            Model {
                id: outerShell
                source: "#Sphere"
                materials: [outerShellMaterial]
                
                property real shellScale:
                    root.verifying ? 0.95 :
                    root.awaiting ? 0.85 :
                    0.8
                    
                Behavior on shellScale {
                    SpringAnimation { spring: 1.5; damping: 0.3 }
                }
                
                scale: Qt.vector3d(shellScale, shellScale, shellScale)
                eulerRotation: Qt.vector3d(root.phase * -10 * rotationSpeedMultiplier, root.phase * 12 * rotationSpeedMultiplier, 0)
            }
            
            // Structured Orbits (Torus)
            Node {
                eulerRotation: Qt.vector3d(
                    root.planning ? 45 : 30,
                    root.phase * 25 * rotationSpeedMultiplier,
                    root.planning ? 45 : 15
                )
                
                Behavior on eulerRotation {
                    SpringAnimation { spring: 1.0; damping: 0.2 }
                }
                
                Model {
                    source: "#Torus"
                    scale: Qt.vector3d(1.2, 1.2, 0.02)
                    materials: [orbitRingMaterial]
                }
                
                // Orbiting satellite
                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(60, 0, 0)
                    scale: Qt.vector3d(0.08, 0.08, 0.08)
                    materials: [particleMaterial]
                }
            }

            Node {
                eulerRotation: Qt.vector3d(
                    root.planning ? -45 : -20,
                    root.phase * -35 * rotationSpeedMultiplier,
                    root.planning ? -45 : -10
                )
                
                Behavior on eulerRotation {
                    SpringAnimation { spring: 1.0; damping: 0.2 }
                }
                
                Model {
                    source: "#Torus"
                    scale: Qt.vector3d(1.4, 1.4, 0.015)
                    materials: [orbitRingMaterial]
                }
                
                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(70, 0, 0)
                    scale: Qt.vector3d(0.06, 0.06, 0.06)
                    materials: [particleMaterial]
                }
            }

            // Particle System Cloud
            Node {
                eulerRotation: Qt.vector3d(0, root.phase * 10 * rotationSpeedMultiplier, 0)
                
                Repeater3D {
                    model: 36
                    
                    delegate: Model {
                        property real idx: index
                        property real theta: (idx / 36) * Math.PI * 2.0
                        property real phi: Math.acos(1.0 - (2.0 * idx + 1.0) / 36.0)
                        
                        property real radius: 1.1 + Math.sin(root.phase * 3.0 + idx) * 0.1
                        
                        source: "#Sphere"
                        position: Qt.vector3d(
                            radius * Math.sin(phi) * Math.cos(theta) * 50,
                            radius * Math.sin(phi) * Math.sin(theta) * 50,
                            radius * Math.cos(phi) * 50
                        )
                        scale: Qt.vector3d(0.02, 0.02, 0.02)
                        materials: [particleMaterial]
                    }
                }
            }
        }
    }
}
