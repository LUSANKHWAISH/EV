import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11C3 ARMORED CUBE CORE
// ============================================================================
//
// Visual target:
// - armored black-metal cube housing
// - deep octagonal front aperture
// - electric-blue transparent cube chamber
// - floating central cognition cube
// - sparse gold circuit traces
// - internal blue particle field
//
// Native Qt Quick 3D only.
// No Blender / GLB / RuntimeLoader.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // E.V. PUBLIC CONTRACT
    // ------------------------------------------------------------------------
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

    property real phase: 0.0

    readonly property bool idle: stateText === "IDLE"
    readonly property bool listening: stateText === "LISTENING"
    readonly property bool planning: stateText === "PLANNING"
    readonly property bool executing: stateText === "EXECUTING"
    readonly property bool verifying: stateText === "VERIFYING"
    readonly property bool speaking: stateText === "SPEAKING"
    readonly property bool awaiting: stateText === "AWAITING_APPROVAL"
    readonly property bool successful: stateText === "SUCCESS"
    readonly property bool failed: stateText === "FAILED"
    readonly property bool recovering: stateText === "RECOVERING"
    readonly property bool stopped: stateText === "STOPPED"

    readonly property color coreBlue:
        root.failed ? "#FF5D66" :
        root.awaiting ? "#A678FF" :
        root.successful ? "#66FFF0" :
        root.speaking ? "#7EE7FF" :
        root.planning ? "#3E9CFF" :
        "#3AA8FF"

    readonly property color glowBlue:
        root.failed ? "#FF8088" :
        root.awaiting ? "#C39CFF" :
        root.successful ? "#84FFF5" :
        "#65C9FF"

    readonly property real listenDrive:
        root.listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.audioLevel > 0.01
                ? root.audioLevel
                : 0.20
                  + 0.30
                  * (
                        (
                            Math.sin(root.phase * 2.0)
                            + 1.0
                          ) * 0.5
                    )
            )
        )
        : 0.0

    readonly property real speechDrive:
        root.speaking
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.speechLevel > 0.01
                ? root.speechLevel
                : 0.18
                  + 0.42
                  * Math.max(
                        0.0,
                        Math.sin(root.phase * 3.2)
                    )
            )
        )
        : 0.0

    readonly property real drive:
        root.executing ? 1.0 :
        root.planning ? 0.82 :
        root.verifying ? 0.72 :
        root.speaking ? 0.70 + root.speechDrive * 0.22 :
        root.listening ? 0.62 + root.listenDrive * 0.24 :
        root.successful ? 0.80 :
        root.failed ? 0.55 :
        root.recovering ? 0.50 :
        root.awaiting ? 0.20 :
        root.stopped ? 0.02 :
        0.35

    readonly property real motionGate:
        root.awaiting ? 0.07 : 1.0

    NumberAnimation {
        target: root
        property: "phase"
        from: 0
        to: Math.PI * 2
        duration:
            root.executing ? 2200 :
            root.planning ? 3200 :
            root.listening ? 2400 :
            root.speaking ? 2200 :
            root.awaiting ? 6200 :
            5200
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    // ------------------------------------------------------------------------
    // SOFT BACKGROUND GLOW
    // ------------------------------------------------------------------------
    Rectangle {
        anchors.fill: parent
        color: "transparent"

        Rectangle {
            width:
                Math.min(
                    root.width,
                    root.height
                ) * 0.56

            height: width
            radius: width / 2
            anchors.centerIn: parent
            color: root.coreBlue
            opacity: 0.050 + root.drive * 0.040

            scale:
                1.0
                + 0.035
                * Math.sin(root.phase * 1.2)
        }

        Rectangle {
            width:
                Math.min(
                    root.width,
                    root.height
                ) * 0.78

            height: width
            radius: width / 2
            anchors.centerIn: parent
            color: root.glowBlue
            opacity: 0.018 + root.drive * 0.018

            scale:
                1.0
                + 0.026
                * Math.cos(root.phase * 0.8)
        }
    }

    View3D {
        id: view3d
        anchors.centerIn: parent

        width:
            Math.min(
                root.width,
                root.height
            ) * 0.80

        height: width

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 520)
            fieldOfView: 32
            clipNear: 1
            clipFar: 2000
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    -32,
                    35,
                    0
                )

            brightness: 1.7
            color: "#EDF4FF"
            ambientColor: "#0A0D12"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    28,
                    -42,
                    0
                )

            brightness: 0.55
            color: "#7AAEFF"
            ambientColor: "#05070A"
            castsShadow: false
        }

        PointLight {
            position:
                Qt.vector3d(
                    0,
                    0,
                    140
                )

            brightness:
                1.8
                + root.drive * 1.8

            color: root.glowBlue

            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.00002
        }

        PointLight {
            position:
                Qt.vector3d(
                    0,
                    0,
                    -120
                )

            brightness: 0.45
            color: "#183764"

            constantFade: 1.0
            linearFade: 0.01
            quadraticFade: 0.00005
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: outerMetal
            baseColor: "#1A2028"
            metalness: 0.92
            roughness: 0.20
            clearcoatAmount: 0.45
            clearcoatRoughnessAmount: 0.05
        }

        PrincipledMaterial {
            id: darkMetal
            baseColor: "#11161D"
            metalness: 0.88
            roughness: 0.24
            clearcoatAmount: 0.30
            clearcoatRoughnessAmount: 0.06
        }

        PrincipledMaterial {
            id: innerMetal
            baseColor: "#202A35"
            metalness: 0.80
            roughness: 0.16
            clearcoatAmount: 0.42
            clearcoatRoughnessAmount: 0.05
        }

        PrincipledMaterial {
            id: energyGlass

            baseColor:
                Qt.rgba(
                    root.glowBlue.r,
                    root.glowBlue.g,
                    root.glowBlue.b,
                    0.16
                )

            metalness: 0.0
            roughness: 0.04
            clearcoatAmount: 0.70
            clearcoatRoughnessAmount: 0.025
            transmissionFactor: 0.78
            alphaMode: PrincipledMaterial.Blend

            emissiveFactor:
                Qt.vector3d(
                    root.glowBlue.r
                    * (
                        0.70
                        + root.drive * 0.48
                      ),

                    root.glowBlue.g
                    * (
                        0.70
                        + root.drive * 0.48
                      ),

                    root.glowBlue.b
                    * (
                        0.70
                        + root.drive * 0.48
                      )
                )
        }

        PrincipledMaterial {
            id: brightEnergy
            baseColor: "#DFF8FF"
            metalness: 0.0
            roughness: 0.08
            clearcoatAmount: 0.64
            clearcoatRoughnessAmount: 0.025
            emissiveFactor: Qt.vector3d(1.6, 2.2, 2.8)
        }

        PrincipledMaterial {
            id: blueStrip
            baseColor: root.coreBlue
            metalness: 0.08
            roughness: 0.10
            clearcoatAmount: 0.34
            clearcoatRoughnessAmount: 0.04

            emissiveFactor:
                Qt.vector3d(
                    root.coreBlue.r
                    * (
                        0.90
                        + root.drive * 0.72
                      ),

                    root.coreBlue.g
                    * (
                        0.90
                        + root.drive * 0.72
                      ),

                    root.coreBlue.b
                    * (
                        0.90
                        + root.drive * 0.72
                      )
                )
        }

        PrincipledMaterial {
            id: goldTrace
            baseColor: "#8F6A33"
            metalness: 0.78
            roughness: 0.22
            clearcoatAmount: 0.24
            clearcoatRoughnessAmount: 0.08
            emissiveFactor: Qt.vector3d(0.08, 0.05, 0.0)
        }

        // ====================================================================
        // MAIN ASSEMBLY
        // ====================================================================
        Node {
            id: rig

            eulerRotation:
                Qt.vector3d(
                    -8
                    + Math.sin(root.phase * 0.23)
                      * 0.55
                      * root.motionGate,

                    -16
                    + Math.sin(root.phase * 0.35)
                      * 1.20
                      * root.motionGate,

                    0.6
                )

            scale:
                Qt.vector3d(
                    1.0
                    + 0.010
                    * Math.sin(root.phase * 0.8),

                    1.0
                    + 0.010
                    * Math.sin(root.phase * 0.8),

                    1.0
                    + 0.010
                    * Math.sin(root.phase * 0.8)
                )

            // ---------------------------------------------------------------
            // REAR BODY MASS
            // ---------------------------------------------------------------
            Model {
                source: "#Cube"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        -36
                    )

                scale:
                    Qt.vector3d(
                        2.00,
                        2.00,
                        1.45
                    )

                materials: [darkMetal]
            }

            // ---------------------------------------------------------------
            // OUTER ARMORED FRAME — four corner masses
            // ---------------------------------------------------------------
            Repeater3D {
                model: 4

                delegate: Node {
                    readonly property real sx:
                        index % 2 === 0 ? -1 : 1

                    readonly property real sy:
                        index < 2 ? -1 : 1

                    Model {
                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                122 * sx,
                                122 * sy,
                                50
                            )

                        scale:
                            Qt.vector3d(
                                0.54,
                                0.54,
                                0.52
                            )

                        materials: [outerMetal]
                    }

                    Model {
                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                126 * sx,
                                72 * sy,
                                58
                            )

                        scale:
                            Qt.vector3d(
                                0.36,
                                0.31,
                                0.46
                            )

                        materials: [outerMetal]
                    }

                    Model {
                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                72 * sx,
                                128 * sy,
                                58
                            )

                        scale:
                            Qt.vector3d(
                                0.31,
                                0.36,
                                0.46
                            )

                        materials: [outerMetal]
                    }
                }
            }

            // ---------------------------------------------------------------
            // TOP / BOTTOM ARMOR PLATES
            // ---------------------------------------------------------------
            Repeater3D {
                model: 3

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            (index - 1) * 76,
                            -152,
                            48
                        )

                    scale:
                        Qt.vector3d(
                            0.50,
                            0.20,
                            0.30
                        )

                    materials: [outerMetal]
                }
            }

            Repeater3D {
                model: 3

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            (index - 1) * 76,
                            152,
                            48
                        )

                    scale:
                        Qt.vector3d(
                            0.50,
                            0.20,
                            0.30
                        )

                    materials: [outerMetal]
                }
            }

            // ---------------------------------------------------------------
            // LEFT / RIGHT ARMOR PLATES
            // ---------------------------------------------------------------
            Repeater3D {
                model: 3

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            -152,
                            (index - 1) * 76,
                            48
                        )

                    scale:
                        Qt.vector3d(
                            0.20,
                            0.50,
                            0.30
                        )

                    materials: [outerMetal]
                }
            }

            Repeater3D {
                model: 3

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            152,
                            (index - 1) * 76,
                            48
                        )

                    scale:
                        Qt.vector3d(
                            0.20,
                            0.50,
                            0.30
                        )

                    materials: [outerMetal]
                }
            }

            // ---------------------------------------------------------------
            // DEEP FRONT CAVITY
            // ---------------------------------------------------------------
            Model {
                source: "#Cube"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        54
                    )

                scale:
                    Qt.vector3d(
                        1.44,
                        1.44,
                        0.62
                    )

                materials: [darkMetal]
            }

            // ---------------------------------------------------------------
            // OCTAGONAL FRONT APERTURE
            // ---------------------------------------------------------------
            Repeater3D {
                model: 8

                delegate: Model {
                    property real a:
                        (
                            index / 8.0
                        )
                        * Math.PI
                        * 2.0
                        + Math.PI / 8.0

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 104,
                            Math.sin(a) * 104,
                            104
                        )

                    eulerRotation:
                        Qt.vector3d(
                            0,
                            0,
                            a * 180 / Math.PI
                        )

                    scale:
                        Qt.vector3d(
                            0.55,
                            0.17,
                            0.20
                        )

                    materials: [innerMetal]
                }
            }

            Repeater3D {
                model: 8

                delegate: Model {
                    property real a:
                        (
                            index / 8.0
                        )
                        * Math.PI
                        * 2.0
                        + Math.PI / 8.0

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 82,
                            Math.sin(a) * 82,
                            118
                        )

                    eulerRotation:
                        Qt.vector3d(
                            0,
                            0,
                            a * 180 / Math.PI
                        )

                    scale:
                        Qt.vector3d(
                            0.38,
                            0.10,
                            0.10
                        )

                    materials: [blueStrip]
                }
            }

            // ---------------------------------------------------------------
            // GLOWING INNER CHAMBER
            // ---------------------------------------------------------------
            Node {
                id: chamber

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                        ? root.phase * 2.5
                        : 0,

                        root.executing
                        ? root.phase * 4.0
                        : root.phase * 0.80,

                        0
                    )

                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            0,
                            0,
                            60
                        )

                    scale:
                        Qt.vector3d(
                            0.94,
                            0.94,
                            0.94
                        )

                    materials: [energyGlass]
                }

                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            0,
                            0,
                            60
                        )

                    scale:
                        Qt.vector3d(
                            0.80,
                            0.80,
                            0.80
                        )

                    materials: [energyGlass]
                }

                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            0,
                            0,
                            60
                        )

                    scale:
                        Qt.vector3d(
                            0.67,
                            0.67,
                            0.67
                        )

                    materials: [energyGlass]
                }

                // -----------------------------------------------------------
                // CHAMBER EDGE-LIGHT APPROXIMATION
                // -----------------------------------------------------------
                Repeater3D {
                    model: 4

                    delegate: Node {
                        readonly property real sx:
                            index % 2 === 0 ? -1 : 1

                        readonly property real sy:
                            index < 2 ? -1 : 1

                        Model {
                            source: "#Cube"

                            position:
                                Qt.vector3d(
                                    48 * sx,
                                    48 * sy,
                                    60
                                )

                            scale:
                                Qt.vector3d(
                                    0.035,
                                    0.035,
                                    0.96
                                )

                            materials: [brightEnergy]
                        }

                        Model {
                            source: "#Cube"

                            position:
                                Qt.vector3d(
                                    48 * sx,
                                    0,
                                    108
                                )

                            scale:
                                Qt.vector3d(
                                    0.035,
                                    0.96,
                                    0.035
                                )

                            materials: [brightEnergy]
                        }

                        Model {
                            source: "#Cube"

                            position:
                                Qt.vector3d(
                                    0,
                                    48 * sy,
                                    108
                                )

                            scale:
                                Qt.vector3d(
                                    0.96,
                                    0.035,
                                    0.035
                                )

                            materials: [brightEnergy]
                        }
                    }
                }
            }

            // ---------------------------------------------------------------
            // CENTRAL FLOATING COGNITION CUBE
            // ---------------------------------------------------------------
            Node {
                id: centralCore

                position:
                    Qt.vector3d(
                        root.executing
                        ? 5.0
                        : 0,

                        root.verifying
                        ? Math.sin(root.phase * 1.3) * 4.0
                        : 0,

                        102
                        + Math.sin(root.phase * 1.6) * 4.0
                        + root.listenDrive * 4.0
                        + root.speechDrive * 5.0
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.phase * 7.0,
                        root.phase * 14.0,
                        root.phase * 4.0
                    )

                Model {
                    source: "#Cube"

                    scale:
                        Qt.vector3d(
                            0.36,
                            0.36,
                            0.36
                        )

                    materials: [outerMetal]
                }

                Model {
                    source: "#Cube"

                    scale:
                        Qt.vector3d(
                            0.10,
                            0.10,
                            0.37
                        )

                    materials: [goldTrace]
                }

                Model {
                    source: "#Cube"

                    scale:
                        Qt.vector3d(
                            0.37,
                            0.10,
                            0.10
                        )

                    materials: [goldTrace]
                }

                Model {
                    source: "#Cube"

                    scale:
                        Qt.vector3d(
                            0.10,
                            0.37,
                            0.10
                        )

                    materials: [goldTrace]
                }

                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            0,
                            0,
                            24
                        )

                    scale:
                        Qt.vector3d(
                            0.055,
                            0.055,
                            0.012
                        )

                    materials: [brightEnergy]
                }
            }

            // ---------------------------------------------------------------
            // INTERNAL PARTICLE FIELD
            // ---------------------------------------------------------------
            Repeater3D {
                model: 40

                delegate: Model {
                    property real a:
                        (
                            index / 40.0
                        )
                        * Math.PI
                        * 2.0

                    property real orbit:
                        18
                        + (
                            index % 5
                          ) * 10

                    property real z:
                        28
                        + (
                            index % 6
                          ) * 15
                        + Math.sin(
                            root.phase * 1.5
                            + index
                          ) * 3.0

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(
                                a
                                + root.phase
                                * (
                                    root.executing
                                    ? 1.15
                                    : root.planning
                                      ? 0.82
                                      : 0.40
                                  )
                            )
                            * orbit,

                            Math.sin(
                                a * 1.3
                                + root.phase * 0.55
                            )
                            * orbit,

                            z
                        )

                    scale:
                        Qt.vector3d(
                            0.016
                            + (
                                index % 3
                              ) * 0.005,

                            0.016
                            + (
                                index % 3
                              ) * 0.005,

                            0.016
                            + (
                                index % 3
                              ) * 0.005
                        )

                    materials: [brightEnergy]
                }
            }

            // ---------------------------------------------------------------
            // SPARSE GOLD CIRCUIT TRACE FEEL
            // ---------------------------------------------------------------
            Repeater3D {
                model: 8

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            (index - 3.5) * 22,
                            -108,
                            116
                        )

                    scale:
                        Qt.vector3d(
                            0.075,
                            0.010,
                            0.018
                        )

                    materials: [goldTrace]
                }
            }

            Repeater3D {
                model: 8

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            (index - 3.5) * 22,
                            108,
                            116
                        )

                    scale:
                        Qt.vector3d(
                            0.075,
                            0.010,
                            0.018
                        )

                    materials: [goldTrace]
                }
            }

            Repeater3D {
                model: 6

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            -108,
                            (index - 2.5) * 27,
                            116
                        )

                    scale:
                        Qt.vector3d(
                            0.010,
                            0.075,
                            0.018
                        )

                    materials: [goldTrace]
                }
            }

            Repeater3D {
                model: 6

                delegate: Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            108,
                            (index - 2.5) * 27,
                            116
                        )

                    scale:
                        Qt.vector3d(
                            0.010,
                            0.075,
                            0.018
                        )

                    materials: [goldTrace]
                }
            }
        }
    }
}
