import QtQuick 2.15
import QtQuick3D
import "../theme"

Item {
    id: root

    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    property string stateText:
        state === null || state === undefined || String(state).length === 0
        ? "IDLE"
        : String(state)

    property real energy: Theme.stateEnergy(root.stateText)
    property color stateTone: Theme.stateColor(root.stateText)

    property real audioLevel: 0.0
    property real speechLevel: 0.0

    View3D {
        id: view3D
        anchors.fill: parent

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 300)
            fieldOfView: 45
            clipNear: 1
            clipFar: 1200
        }

        Node {
            id: rootNode

            Model {
                id: orb
                source: "#Sphere"
                scale: Qt.vector3d(1.0, 1.0, 1.0)

                materials: [
                    PrincipledMaterial {
                        baseColor: "#0A0F1F"
                        roughness: 0.2
                        metalness: 0.8

                        emissiveFactor:
                            Qt.vector3d(
                                0.0,
                                0.749,
                                1.0
                            )
                    }
                ]
            }

            DirectionalLight {
                eulerRotation: Qt.vector3d(-30, 45, 0)
                brightness: 1.2
                color: "#FFFFFF"
                castsShadow: false
            }

            PointLight {
                position: Qt.vector3d(0, 0, 200)
                color: "#00FFFF"
                brightness: 3.0
                constantFade: 1.0
                linearFade: 0.0
                quadraticFade: 0.00002
            }
        }
    }
}
