import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11Q.1 TRUE DEPTH ENGINE
// ============================================================================
//
// QML-only. No GLB / Blender assets.
//
// R11Q worked functionally but read visually flat because most visible structure
// was drawn in 2D Canvas. R11Q.1 keeps Canvas ONLY for the distant aura and
// state ripples. The visible machine/energy structure is now real Qt Quick 3D:
//
//   FRONT PLANE   +48 .. +72
//   CORE PLANE    +08 .. +34
//   MID PLANE     -18 .. -34
//   REAR PLANE    -62 .. -82
//
// The entire assembly is viewed at a permanent shallow 3/4 angle so these
// planes produce real perspective, occlusion and parallax.
//
// Public EVFlagshipStage contract is preserved.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // PUBLIC CONTRACT
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

    // Future real voice hooks.
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ------------------------------------------------------------------------
    // CLOCK / STATE PHYSICS
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1450 :
        root.failed ? 1300 :
        root.verifying ? 1850 :
        root.speaking ? 1550 :
        root.planning ? 2100 :
        root.listening ? 1650 :
        root.recovering ? 2600 :
        root.awaiting ? 6000 :
        root.successful ? 2300 :
        5000

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.52) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.41)
    readonly property real drift2: Math.cos(root.phase * 0.33)

    readonly property color displayTone:
        root.idle ? "#34E6E0" :
        root.listening ? "#8E6BFF" :
        root.planning ? "#FF9D3D" :
        root.speaking ? "#FFCF6B" :
        root.stateTone

    readonly property real syntheticListen:
        root.listening ? 0.16 + root.pulse * 0.30 : 0.0

    readonly property real syntheticSpeech:
        root.speaking
        ? 0.14 + Math.max(0.0, Math.sin(root.phase * 3.0)) * 0.48
        : 0.0

    readonly property real listenDrive:
        root.listening
        ? Math.max(0.0, Math.min(1.0,
            root.audioLevel > 0.01 ? root.audioLevel : root.syntheticListen))
        : 0.0

    readonly property real speechDrive:
        root.speaking
        ? Math.max(0.0, Math.min(1.0,
            root.speechLevel > 0.01 ? root.speechLevel : root.syntheticSpeech))
        : 0.0

    readonly property real coreScale:
        root.stopped ? 0.82 :
        root.idle ? 0.985 + root.slowPulse * 0.030 :
        root.listening ? 0.98 + root.listenDrive * 0.085 :
        root.speaking ? 0.99 + root.speechDrive * 0.070 :
        root.successful ? 1.045 :
        root.failed ? 0.965 + root.pulse * 0.020 :
        1.0 + root.pulse * 0.018

    readonly property real glowDrive:
        root.stopped ? 0.05 :
        root.listening ? 0.70 + root.listenDrive * 0.45 :
        root.speaking ? 0.74 + root.speechDrive * 0.46 :
        root.planning ? 0.82 :
        root.executing ? 0.98 :
        root.verifying ? 0.90 :
        root.successful ? 1.08 :
        root.failed ? 0.66 :
        root.recovering ? 0.76 :
        root.awaiting ? 0.38 :
        0.58

    readonly property real motionGate: root.awaiting ? 0.07 : 1.0

    // Actual front/mid/rear separation changes with state.
    readonly property real frontAdvance:
        root.executing ? 16.0 :
        root.listening ? root.listenDrive * 10.0 :
        root.speaking ? root.speechDrive * 7.0 :
        root.successful ? 8.0 :
        root.failed ? Math.sin(root.phase * 4.0) * 4.0 :
        0.0

    readonly property real midShift:
        root.planning ? Math.sin(root.phase * 1.4) * 6.0 :
        root.verifying ? Math.sin(root.phase * 1.7) * 10.0 :
        root.recovering ? (1.0 - root.pulse) * -5.0 :
        0.0

    readonly property real rearShift:
        root.failed ? Math.cos(root.phase * 3.2) * 8.0 :
        root.recovering ? Math.sin(root.phase) * 3.5 :
        0.0

    readonly property real logicalSize: Math.max(
        180.0,
        Math.min(root.width, root.height) * 0.58
    )

    function rgbaString(c, a) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, a))
            + ")"
    }

    // ------------------------------------------------------------------------
    // BACKGROUND ONLY — no fake glass face over the 3D object.
    // ------------------------------------------------------------------------
    Canvas {
        id: auraCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var w = width
            var h = height
            var cx = w * 0.5
            var cy = h * 0.5
            var r = Math.min(w, h) * 0.105
            var tone = root.displayTone

            ctx.clearRect(0, 0, w, h)

            var aura = ctx.createRadialGradient(
                cx, cy, r * 0.20,
                cx, cy, r * 3.4
            )
            aura.addColorStop(0.0, root.rgbaString(tone, 0.17 * root.glowDrive))
            aura.addColorStop(0.40, root.rgbaString(tone, 0.065 * root.glowDrive))
            aura.addColorStop(1.0, root.rgbaString(tone, 0.0))
            ctx.fillStyle = aura
            ctx.beginPath()
            ctx.arc(cx, cy, r * 3.4, 0, Math.PI * 2)
            ctx.fill()

            // State ripples remain behind the 3D assembly.
            if (root.listening || root.speaking) {
                var drive = root.listening ? root.listenDrive : root.speechDrive
                for (var i = 0; i < 3; ++i) {
                    var travel = ((root.phase / (Math.PI * 2.0)) + i / 3.0) % 1.0
                    var rr = r * (1.75 + travel * (1.0 + drive * 0.50))
                    ctx.lineWidth = Math.max(1.0, r * 0.010)
                    ctx.strokeStyle = root.rgbaString(
                        tone,
                        (1.0 - travel) * (0.07 + drive * 0.15)
                    )
                    ctx.beginPath()
                    ctx.arc(cx, cy, rr, 0, Math.PI * 2)
                    ctx.stroke()
                }
            }

            if (root.verifying) {
                var vr = r * (1.55 + root.pulse * 0.18)
                ctx.lineWidth = Math.max(1.0, r * 0.010)
                ctx.strokeStyle = root.rgbaString(tone, 0.16)
                ctx.beginPath()
                ctx.arc(cx, cy, vr, 0, Math.PI * 2)
                ctx.stroke()
            }
        }
    }

    // ------------------------------------------------------------------------
    // TRUE 3D ASSEMBLY
    // ------------------------------------------------------------------------
    View3D {
        id: coreView
        anchors.centerIn: parent
        width: root.logicalSize
        height: root.logicalSize

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        // Longer lens + closer camera gives stronger depth compression/parallax
        // while keeping the object elegant rather than distorted.
        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 500)
            fieldOfView: 37
            clipNear: 1
            clipFar: 1500
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-28, 38, -8)
            color: "#F7FAFF"
            brightness: 2.55
            ambientColor: "#111720"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(32, -48, 16)
            color: "#647D9D"
            brightness: 0.82
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position: Qt.vector3d(-74, 66, 150)
            color: root.displayTone
            brightness: 1.2 + root.glowDrive * 1.35
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        PointLight {
            position: Qt.vector3d(72, -46, -90)
            color: root.displayTone
            brightness: 0.36 + root.glowDrive * 0.34
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000030
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: rearMaterial
            baseColor: Qt.rgba(
                0.025 + root.displayTone.r * 0.055,
                0.032 + root.displayTone.g * 0.055,
                0.045 + root.displayTone.b * 0.055,
                1.0
            )
            metalness: 0.82
            roughness: 0.31
            clearcoatAmount: 0.22
            clearcoatRoughnessAmount: 0.17
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.10,
                root.displayTone.g * root.glowDrive * 0.10,
                root.displayTone.b * root.glowDrive * 0.10
            )
        }

        PrincipledMaterial {
            id: midMaterial
            baseColor: Qt.rgba(
                0.050 + root.displayTone.r * 0.090,
                0.060 + root.displayTone.g * 0.090,
                0.080 + root.displayTone.b * 0.090,
                1.0
            )
            metalness: 0.72
            roughness: 0.24
            clearcoatAmount: 0.40
            clearcoatRoughnessAmount: 0.11
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.22,
                root.displayTone.g * root.glowDrive * 0.22,
                root.displayTone.b * root.glowDrive * 0.22
            )
        }

        PrincipledMaterial {
            id: frontMaterial
            baseColor: "#AEB9C8"
            metalness: 0.88
            roughness: 0.17
            clearcoatAmount: 0.48
            clearcoatRoughnessAmount: 0.08
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.16,
                root.displayTone.g * root.glowDrive * 0.16,
                root.displayTone.b * root.glowDrive * 0.16
            )
        }

        PrincipledMaterial {
            id: energyMaterial
            baseColor: Qt.rgba(
                0.18 + root.displayTone.r * 0.70,
                0.22 + root.displayTone.g * 0.70,
                0.30 + root.displayTone.b * 0.70,
                1.0
            )
            metalness: 0.04
            roughness: 0.13
            clearcoatAmount: 0.68
            clearcoatRoughnessAmount: 0.06
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 1.35,
                root.displayTone.g * root.glowDrive * 1.35,
                root.displayTone.b * root.glowDrive * 1.35
            )
        }

        PrincipledMaterial {
            id: nucleusMaterial
            baseColor: "#040812"
            metalness: 0.20
            roughness: 0.16
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.08
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.52,
                root.displayTone.g * root.glowDrive * 0.52,
                root.displayTone.b * root.glowDrive * 0.52
            )
        }

        PrincipledMaterial {
            id: particleMaterial
            baseColor: root.displayTone
            metalness: 0.04
            roughness: 0.16
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * 1.55,
                root.displayTone.g * 1.55,
                root.displayTone.b * 1.55
            )
        }

        // --------------------------------------------------------------------
        // MASTER ASSEMBLY — permanent shallow 3/4 angle.
        // --------------------------------------------------------------------
        Node {
            id: assembly

            scale: Qt.vector3d(
                root.coreScale,
                root.coreScale,
                root.coreScale
            )

            eulerRotation: Qt.vector3d(
                -8.5 + root.drift2 * 0.45 * root.motionGate,
                -16.5 + root.drift * 1.35 * root.motionGate,
                root.failed
                    ? Math.sin(root.phase * 3.6) * 1.8
                    : root.drift2 * 0.30 * root.motionGate
            )

            // ---------------------------------------------------------------
            // REAR DEPTH PLANE — dark stator, ~Z -72
            // ---------------------------------------------------------------
            Node {
                id: rearPlane
                z: -72 + root.rearShift
                eulerRotation.z:
                    root.planning ? -root.phase * 8.0 :
                    root.failed ? root.drift * 5.0 :
                    root.recovering ? -root.phase * 2.0 :
                    root.drift * 0.5 * root.motionGate

                Repeater3D {
                    model: 14

                    delegate: Model {
                        property real angle: (index / 14.0) * Math.PI * 2.0
                        property real rr: 118.0

                        source: "#Cube"

                        position: Qt.vector3d(
                            Math.cos(angle) * rr,
                            Math.sin(angle) * rr,
                            (index % 2 === 0 ? -4.0 : 5.0)
                        )

                        eulerRotation: Qt.vector3d(
                            index % 3 === 0 ? 7.0 : -3.0,
                            index % 2 === 0 ? -4.0 : 4.0,
                            angle * 180.0 / Math.PI + 90.0
                        )

                        scale: Qt.vector3d(
                            0.42 + (index % 3) * 0.035,
                            0.082,
                            0.075 + (index % 2) * 0.018
                        )

                        materials: [rearMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // MID DEPTH PLANE — counter rotating cognition carrier, ~Z -24
            // ---------------------------------------------------------------
            Node {
                id: midPlane
                z: -24 + root.midShift
                eulerRotation.z:
                    root.planning ? root.phase * 13.0 :
                    root.executing ? root.phase * 17.0 :
                    root.verifying ? root.phase * 4.5 :
                    root.drift * 0.75 * root.motionGate

                Repeater3D {
                    model: 12

                    delegate: Model {
                        property real angle: (index / 12.0) * Math.PI * 2.0
                        property real rr:
                            94.0
                            + (root.listening ? root.listenDrive * 6.0 : 0.0)

                        source: "#Cube"

                        position: Qt.vector3d(
                            Math.cos(angle) * rr,
                            Math.sin(angle) * rr,
                            index % 3 === 0 ? 7.0 :
                            index % 3 === 1 ? -5.0 : 1.0
                        )

                        eulerRotation: Qt.vector3d(
                            -4.0 + (index % 3) * 4.0,
                            index % 2 === 0 ? 5.0 : -5.0,
                            angle * 180.0 / Math.PI + 90.0
                        )

                        scale: Qt.vector3d(
                            0.33 + (index % 2) * 0.045,
                            0.070,
                            0.052
                        )

                        materials: [midMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // CENTRAL ENERGY BODY — actual solid volumes at different Z.
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"
                z: 4
                scale: Qt.vector3d(0.86, 0.86, 0.62)
                materials: [rearMaterial]
            }

            Model {
                source: "#Sphere"
                z: 22
                scale: Qt.vector3d(
                    0.57 + root.listenDrive * 0.035,
                    0.57 + root.listenDrive * 0.035,
                    0.46 + root.speechDrive * 0.030
                )
                materials: [energyMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    root.executing ? 5.0 : 0.0,
                    root.verifying ? root.drift * 3.5 : 0.0,
                    44 + root.frontAdvance * 0.22
                )
                scale: Qt.vector3d(
                    0.255 + root.speechDrive * 0.018,
                    0.255 + root.speechDrive * 0.018,
                    0.235
                )
                materials: [nucleusMaterial]
            }

            // ---------------------------------------------------------------
            // FRONT DEPTH PLANE — silver containment cassettes, ~Z +58
            // ---------------------------------------------------------------
            Node {
                id: frontPlane
                z: 58 + root.frontAdvance
                eulerRotation.z:
                    root.planning ? -root.phase * 4.0 :
                    root.executing ? root.phase * 3.0 :
                    root.drift2 * 0.55 * root.motionGate

                Repeater3D {
                    model: 8

                    delegate: Model {
                        property real angle:
                            (index / 8.0) * Math.PI * 2.0 + Math.PI / 8.0
                        property real rr:
                            76.0
                            + (root.listening ? root.listenDrive * 8.0 : 0.0)
                            + (root.successful ? 4.0 : 0.0)

                        source: "#Cube"

                        position: Qt.vector3d(
                            Math.cos(angle) * rr,
                            Math.sin(angle) * rr,
                            index % 2 === 0 ? 5.0 : -3.0
                        )

                        eulerRotation: Qt.vector3d(
                            index % 2 === 0 ? -8.0 : 6.0,
                            index % 3 === 0 ? 8.0 : -4.0,
                            angle * 180.0 / Math.PI + 90.0
                        )

                        scale: Qt.vector3d(
                            index % 2 === 0 ? 0.265 : 0.225,
                            0.058,
                            index % 2 === 0 ? 0.050 : 0.042
                        )

                        materials: [frontMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // TRUE 3D PARTICLE FIELD — Z spread is intentional and large.
            // ---------------------------------------------------------------
            Repeater3D {
                model: 20

                delegate: Model {
                    property real baseAngle:
                        (index / 20.0) * Math.PI * 2.0

                    property real speed:
                        root.planning ? 1.55 :
                        root.executing ? 2.15 :
                        root.verifying ? 0.90 :
                        0.28

                    property real angle:
                        baseAngle + root.phase * speed

                    property real rr:
                        132.0 + (index % 4) * 11.0

                    property real zz:
                        Math.sin(angle * 1.65 + index * 0.73) * 62.0
                        + (index % 3 - 1) * 7.0

                    source: "#Sphere"

                    position: Qt.vector3d(
                        Math.cos(angle) * rr,
                        Math.sin(angle) * rr * 0.72,
                        zz
                    )

                    scale: Qt.vector3d(
                        0.018 + (index % 3) * 0.006,
                        0.018 + (index % 3) * 0.006,
                        0.018 + (index % 3) * 0.006
                    )

                    materials: [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // VERY LIGHT FRONT SPECULAR — no full 2D sphere covering the 3D renderer.
    // ------------------------------------------------------------------------
    Canvas {
        id: accentCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.105
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            // Small upper-left highlight only.
            ctx.lineWidth = Math.max(1.0, r * 0.018)
            ctx.strokeStyle = "rgba(255,255,255,0.23)"
            ctx.beginPath()
            ctx.arc(
                cx - r * 0.02,
                cy - r * 0.01,
                r * 0.54,
                Math.PI * 1.10,
                Math.PI * 1.49
            )
            ctx.stroke()

            // Tiny precision energy edge.
            ctx.lineWidth = Math.max(1.0, r * 0.009)
            ctx.strokeStyle = root.rgbaString(tone, 0.30 * root.glowDrive)
            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 0.71,
                Math.PI * 0.08,
                Math.PI * 0.54
            )
            ctx.stroke()
        }
    }

    // ------------------------------------------------------------------------
    // REPAINT
    // ------------------------------------------------------------------------
    onPhaseChanged: {
        auraCanvas.requestPaint()
        accentCanvas.requestPaint()
    }

    onWidthChanged: {
        auraCanvas.requestPaint()
        accentCanvas.requestPaint()
    }

    onHeightChanged: {
        auraCanvas.requestPaint()
        accentCanvas.requestPaint()
    }

    onDisplayToneChanged: {
        auraCanvas.requestPaint()
        accentCanvas.requestPaint()
    }

    onAudioLevelChanged: auraCanvas.requestPaint()
    onSpeechLevelChanged: auraCanvas.requestPaint()
}
