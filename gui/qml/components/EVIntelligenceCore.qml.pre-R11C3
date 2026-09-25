import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11C2 COPILOT MECHANICAL ORB
// ============================================================================
//
// Visual target: user-supplied image
// - segmented black-metal spherical shell
// - front intelligence aperture
// - bright cyan central energy core
// - radial inner detail
// - restrained cyan shell light strips
// - orbital particle field / energy paths
//
// Native Qt Quick 3D only.
// No GLB / Blender / RuntimeLoader.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // PUBLIC E.V. CONTRACT
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

    // ------------------------------------------------------------------------
    // STATE / MOTION
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property color cyanTone:
        root.failed ? "#FF5D68" :
        root.recovering ? "#52D6FF" :
        root.awaiting ? "#A47CFF" :
        root.planning ? "#42A8FF" :
        root.speaking ? "#7EE7FF" :
        root.successful ? "#66FFF1" :
        "#19C9FF"

    readonly property real listenDrive:
        root.listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.audioLevel > 0.01
                ? root.audioLevel
                : 0.22 + 0.28 * ((Math.sin(root.phase * 2.0) + 1.0) * 0.5)
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
                : 0.18 + 0.40 * Math.max(0.0, Math.sin(root.phase * 3.2))
            )
        )
        : 0.0

    readonly property real activity:
        root.executing ? 1.0 :
        root.planning ? 0.82 :
        root.verifying ? 0.70 :
        root.listening ? 0.60 + root.listenDrive * 0.35 :
        root.speaking ? 0.62 + root.speechDrive * 0.35 :
        root.successful ? 0.76 :
        root.failed ? 0.50 :
        root.recovering ? 0.58 :
        root.awaiting ? 0.18 :
        root.stopped ? 0.03 :
        0.34

    readonly property real motionSpeed:
        root.executing ? 2.20 :
        root.planning ? 1.60 :
        root.verifying ? 1.10 :
        root.listening ? 0.85 :
        root.speaking ? 0.95 :
        root.failed ? 1.35 :
        root.recovering ? 0.70 :
        root.awaiting ? 0.10 :
        root.stopped ? 0.01 :
        0.34

    readonly property real shellBreath:
        root.stopped ? 0.92 :
        0.99
        + 0.018 * ((Math.sin(root.phase * 0.55) + 1.0) * 0.5)
        + root.listenDrive * 0.018
        + root.speechDrive * 0.015

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration:
            root.executing ? 1600 :
            root.planning ? 2200 :
            root.listening ? 1800 :
            root.speaking ? 1650 :
            root.awaiting ? 6000 :
            5000
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    // ------------------------------------------------------------------------
    // BACKGROUND ENERGY HAZE
    // ------------------------------------------------------------------------
    Canvas {
        id: aura
        anchors.fill: parent
        antialiasing: true

        function rgba(c, a) {
            return "rgba("
                + Math.round(c.r * 255) + ","
                + Math.round(c.g * 255) + ","
                + Math.round(c.b * 255) + ","
                + a + ")"
        }

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.23

            ctx.clearRect(0, 0, width, height)

            var g = ctx.createRadialGradient(
                cx, cy, r * 0.25,
                cx, cy, r * 1.65
            )

            g.addColorStop(
                0.0,
                rgba(root.cyanTone, 0.18 * root.activity)
            )
            g.addColorStop(
                0.45,
                rgba(root.cyanTone, 0.07 * root.activity)
            )
            g.addColorStop(
                1.0,
                rgba(root.cyanTone, 0.0)
            )

            ctx.fillStyle = g
            ctx.beginPath()
            ctx.arc(cx, cy, r * 1.65, 0, Math.PI * 2.0)
            ctx.fill()
        }
    }

    // ------------------------------------------------------------------------
    // TRUE 3D CORE
    // ------------------------------------------------------------------------
    View3D {
        id: view3D
        anchors.centerIn: parent

        width: Math.min(root.width, root.height) * 0.74
        height: width

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 340)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1400
        }

        // --------------------------------------------------------------------
        // LIGHTING
        // --------------------------------------------------------------------
        DirectionalLight {
            eulerRotation: Qt.vector3d(-34, 40, -8)
            color: "#EAF4FF"
            brightness: 2.05
            ambientColor: "#0A101A"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(24, -52, 16)
            color: "#4A72A8"
            brightness: 0.64
            ambientColor: "#03060A"
            castsShadow: false
        }

        PointLight {
            position: Qt.vector3d(0, 0, 125)
            color: root.cyanTone
            brightness: 1.4 + root.activity * 1.9
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000022
        }

        PointLight {
            position: Qt.vector3d(-70, 55, -65)
            color: "#2B7DCB"
            brightness: 0.35
            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.00004
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: shellMaterial
            baseColor: "#0A0F18"
            metalness: 0.84
            roughness: 0.19
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.06
        }

        PrincipledMaterial {
            id: shellInsetMaterial
            baseColor: "#111A28"
            metalness: 0.72
            roughness: 0.24
            clearcoatAmount: 0.42
            clearcoatRoughnessAmount: 0.08
        }

        PrincipledMaterial {
            id: ringMaterial
            baseColor: "#101A28"
            metalness: 0.80
            roughness: 0.16
            clearcoatAmount: 0.52
            clearcoatRoughnessAmount: 0.05

            emissiveFactor:
                Qt.vector3d(
                    root.cyanTone.r * root.activity * 0.16,
                    root.cyanTone.g * root.activity * 0.16,
                    root.cyanTone.b * root.activity * 0.16
                )
        }

        PrincipledMaterial {
            id: cyanMaterial
            baseColor: root.cyanTone
            metalness: 0.12
            roughness: 0.12
            clearcoatAmount: 0.54
            clearcoatRoughnessAmount: 0.04

            emissiveFactor:
                Qt.vector3d(
                    root.cyanTone.r * (1.0 + root.activity * 0.8),
                    root.cyanTone.g * (1.0 + root.activity * 0.8),
                    root.cyanTone.b * (1.0 + root.activity * 0.8)
                )
        }

        PrincipledMaterial {
            id: coreMaterial
            baseColor: "#B9F6FF"
            metalness: 0.02
            roughness: 0.08
            clearcoatAmount: 0.74
            clearcoatRoughnessAmount: 0.025

            emissiveFactor:
                Qt.vector3d(
                    1.8,
                    2.4,
                    2.8
                )
        }

        PrincipledMaterial {
            id: particleMaterial
            baseColor: root.cyanTone
            metalness: 0.0
            roughness: 0.2

            emissiveFactor:
                Qt.vector3d(
                    root.cyanTone.r * 1.55,
                    root.cyanTone.g * 1.55,
                    root.cyanTone.b * 1.55
                )
        }

        // ====================================================================
        // MASTER SPHERE
        // ====================================================================
        Node {
            id: orbRoot

            scale:
                Qt.vector3d(
                    root.shellBreath,
                    root.shellBreath,
                    root.shellBreath
                )

            eulerRotation:
                Qt.vector3d(
                    -7.5,
                    -13.5 + Math.sin(root.phase * 0.34) * 1.2,
                    1.0
                )

            // ----------------------------------------------------------------
            // MAIN BLACK METAL SHELL BODY
            // ----------------------------------------------------------------
            Model {
                source: "#Sphere"
                scale: Qt.vector3d(1.16, 1.16, 1.08)
                materials: [shellMaterial]
            }

            // ----------------------------------------------------------------
            // SEGMENTED SHELL PANELS
            // Built as shallow cubes following the spherical silhouette.
            // ----------------------------------------------------------------
            Repeater3D {
                model: 8

                delegate: Model {
                    property real a:
                        (index / 8.0) * Math.PI * 2.0

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 61.0,
                            Math.sin(a) * 61.0,
                            52.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            -6.0,
                            0.0,
                            a * 180.0 / Math.PI + 90.0
                        )

                    scale:
                        Qt.vector3d(
                            0.30,
                            0.10,
                            0.09
                        )

                    materials: [shellInsetMaterial]
                }
            }

            // ----------------------------------------------------------------
            // FOUR CYAN SHELL LIGHT WINDOWS
            // ----------------------------------------------------------------
            Repeater3D {
                model: 4

                delegate: Model {
                    property real a:
                        (index / 4.0) * Math.PI * 2.0
                        + Math.PI / 4.0

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 67.0,
                            Math.sin(a) * 67.0,
                            62.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            0,
                            0,
                            a * 180.0 / Math.PI + 90.0
                        )

                    scale:
                        Qt.vector3d(
                            0.12,
                            0.035,
                            0.018
                        )

                    materials: [cyanMaterial]
                }
            }

            // ----------------------------------------------------------------
            // FRONT APERTURE STACK
            // ----------------------------------------------------------------

            // Deep front recess.
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(0, 0, 70)
                eulerRotation: Qt.vector3d(90, 0, 0)
                scale: Qt.vector3d(0.74, 0.18, 0.74)
                materials: [shellInsetMaterial]
            }

            // Outer aperture bezel.
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(0, 0, 82)
                eulerRotation: Qt.vector3d(90, 0, 0)
                scale: Qt.vector3d(0.66, 0.11, 0.66)
                materials: [ringMaterial]
            }

            // Inner ring.
            Model {
                source: "#Cylinder"
                position: Qt.vector3d(0, 0, 94)
                eulerRotation: Qt.vector3d(90, 0, 0)
                scale: Qt.vector3d(0.49, 0.08, 0.49)
                materials: [shellInsetMaterial]
            }

            // ----------------------------------------------------------------
            // RADIAL INNER DETAIL
            // ----------------------------------------------------------------
            Repeater3D {
                model: 24

                delegate: Model {
                    property real a:
                        (index / 24.0) * Math.PI * 2.0
                        + root.phase * (
                            root.planning ? 0.18 :
                            root.executing ? 0.30 :
                            0.04
                        )

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 34.0,
                            Math.sin(a) * 34.0,
                            105.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            0,
                            0,
                            a * 180.0 / Math.PI
                        )

                    scale:
                        Qt.vector3d(
                            0.10,
                            0.020,
                            0.018
                        )

                    materials:
                        index % 3 === 0
                        ? [cyanMaterial]
                        : [ringMaterial]
                }
            }

            // ----------------------------------------------------------------
            // CENTRAL ENERGY CORE
            // ----------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        116.0
                        + root.speechDrive * 4.0
                    )

                scale:
                    Qt.vector3d(
                        0.30 + root.listenDrive * 0.025 + root.speechDrive * 0.035,
                        0.30 + root.listenDrive * 0.025 + root.speechDrive * 0.035,
                        0.22
                    )

                materials: [coreMaterial]
            }

            // Cyan halo around central energy.
            Repeater3D {
                model: 16

                delegate: Model {
                    property real a:
                        (index / 16.0) * Math.PI * 2.0
                        - root.phase * (
                            root.executing ? 0.22 :
                            root.planning ? 0.15 :
                            0.03
                        )

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * 26.0,
                            Math.sin(a) * 26.0,
                            115.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            0,
                            0,
                            a * 180.0 / Math.PI
                        )

                    scale:
                        Qt.vector3d(
                            0.055,
                            0.016,
                            0.014
                        )

                    materials: [cyanMaterial]
                }
            }

            // ----------------------------------------------------------------
            // TRUE 3D ORBITAL PARTICLES
            // Creates the energetic orbital feel from the reference image.
            // ----------------------------------------------------------------
            Repeater3D {
                model: 42

                delegate: Model {
                    property real baseAngle:
                        (index / 42.0) * Math.PI * 2.0

                    property real orbitAngle:
                        baseAngle
                        + root.phase
                        * root.motionSpeed
                        * (
                            index % 2 === 0 ? 1.0 : -0.72
                        )

                    property real orbitRadius:
                        112.0
                        + (
                            index % 4
                          ) * 13.0

                    property real yTilt:
                        index % 3 === 0 ? 0.44 :
                        index % 3 === 1 ? 0.26 :
                        0.62

                    property real zDepth:
                        Math.sin(
                            orbitAngle * 1.22
                            + index * 0.47
                        ) * 72.0

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(orbitAngle) * orbitRadius,
                            Math.sin(orbitAngle) * orbitRadius * yTilt,
                            zDepth
                        )

                    scale:
                        Qt.vector3d(
                            0.012 + (index % 3) * 0.004,
                            0.012 + (index % 3) * 0.004,
                            0.012 + (index % 3) * 0.004
                        )

                    materials: [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // 2D ORBITAL TRAILS
    // Thin Canvas trails reinforce the image reference but do not cover core.
    // ------------------------------------------------------------------------
    Canvas {
        id: orbitCanvas
        anchors.fill: parent
        antialiasing: true

        function rgba(c, a) {
            return "rgba("
                + Math.round(c.r * 255) + ","
                + Math.round(c.g * 255) + ","
                + Math.round(c.b * 255) + ","
                + a + ")"
        }

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.21

            ctx.clearRect(0, 0, width, height)

            for (var i = 0; i < 3; ++i) {
                ctx.save()
                ctx.translate(cx, cy)
                ctx.rotate(
                    -0.34
                    + i * 0.34
                    + root.phase * 0.015 * (i % 2 === 0 ? 1 : -1)
                )

                ctx.scale(
                    1.55 + i * 0.12,
                    0.38 + i * 0.055
                )

                ctx.lineWidth = Math.max(0.8, r * 0.006)

                ctx.strokeStyle =
                    rgba(
                        root.cyanTone,
                        0.11 + root.activity * 0.12
                    )

                ctx.beginPath()
                ctx.arc(
                    0,
                    0,
                    r * (0.92 + i * 0.15),
                    0,
                    Math.PI * 2.0
                )
                ctx.stroke()
                ctx.restore()
            }
        }
    }

    onPhaseChanged: {
        aura.requestPaint()
        orbitCanvas.requestPaint()
    }

    onWidthChanged: {
        aura.requestPaint()
        orbitCanvas.requestPaint()
    }

    onHeightChanged: {
        aura.requestPaint()
        orbitCanvas.requestPaint()
    }

    onCyanToneChanged: {
        aura.requestPaint()
        orbitCanvas.requestPaint()
    }
}
