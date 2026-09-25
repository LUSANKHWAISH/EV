import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11M1 MISTRAL FLAGSHIP CANDIDATE
// ============================================================================
//
// Based on the Mistral design specification supplied by the user.
// Mistral's response described the intended structure but did not include the
// promised QML body, so this file implements that specification natively.
//
// DESIGN INTENT:
// - preserve the clean R11Q-D living-core identity
// - increase visual presence
// - stronger front / centre / rear depth
// - fewer, thicker internal structural masses
// - layered translucent sapphire energy chamber
// - sparse neural gold pathways
// - 40 real Qt Quick 3D particles spanning large Z depth
// - deliberate state-driven motion
//
// QML only. No Blender, no GLB, no external runtime loader.
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

    // Optional future real voice amplitude hooks.
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ------------------------------------------------------------------------
    // MOTION CLOCK
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1450 :
        root.failed ? 1325 :
        root.verifying ? 1850 :
        root.speaking ? 1550 :
        root.planning ? 2050 :
        root.listening ? 1650 :
        root.recovering ? 2650 :
        root.awaiting ? 6200 :
        root.successful ? 2250 :
        5000

    readonly property real pulse:
        (Math.sin(root.phase) + 1.0) * 0.5

    readonly property real slowPulse:
        (Math.sin(root.phase * 0.48) + 1.0) * 0.5

    readonly property real drift:
        Math.sin(root.phase * 0.39)

    readonly property real drift2:
        Math.cos(root.phase * 0.31)

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    // ------------------------------------------------------------------------
    // STATE COLOUR LANGUAGE
    // ------------------------------------------------------------------------
    readonly property color sapphire: "#246CFF"
    readonly property color electricSapphire: "#58B8FF"
    readonly property color deepSapphire: "#123A9C"
    readonly property color coolWhite: "#EAF2FF"
    readonly property color restrainedGold: "#C9A86C"

    readonly property color displayTone:
        root.idle ? root.deepSapphire :
        root.listening ? root.electricSapphire :
        root.planning ? root.restrainedGold :
        root.speaking ? "#FFD08A" :
        root.stateTone

    readonly property real syntheticListen:
        root.listening
        ? 0.18 + root.pulse * 0.34
        : 0.0

    readonly property real syntheticSpeech:
        root.speaking
        ? 0.16 + Math.max(0.0, Math.sin(root.phase * 3.0)) * 0.50
        : 0.0

    readonly property real listenDrive:
        root.listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.audioLevel > 0.01
                ? root.audioLevel
                : root.syntheticListen
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
                : root.syntheticSpeech
            )
        )
        : 0.0

    readonly property real motionGate:
        root.awaiting ? 0.055 : 1.0

    readonly property real glowDrive:
        root.stopped ? 0.04 :
        root.listening ? 0.72 + root.listenDrive * 0.48 :
        root.speaking ? 0.76 + root.speechDrive * 0.50 :
        root.planning ? 0.82 :
        root.executing ? 0.98 :
        root.verifying ? 0.92 :
        root.successful ? 1.12 :
        root.failed ? 0.58 :
        root.recovering ? 0.76 :
        root.awaiting ? 0.34 :
        0.56

    readonly property real shellOpen:
        root.listening ? 0.18 + root.listenDrive * 0.52 :
        root.executing ? 0.26 :
        root.successful ? 0.30 :
        root.failed ? 0.10 :
        root.awaiting ? 0.015 :
        0.05

    readonly property real filamentActivity:
        root.planning ? 0.92 :
        root.speaking ? 0.38 + root.speechDrive * 0.50 :
        root.executing ? 0.62 :
        root.verifying ? 0.44 :
        root.listening ? 0.18 + root.listenDrive * 0.18 :
        root.successful ? 0.52 :
        root.failed ? 0.08 :
        root.recovering ? 0.34 :
        root.awaiting ? 0.06 :
        0.04

    readonly property real particleSpeed:
        root.executing ? 2.15 :
        root.planning ? 1.62 :
        root.verifying ? 0.96 :
        root.listening ? 0.72 + root.listenDrive * 0.68 :
        root.speaking ? 0.78 + root.speechDrive * 0.40 :
        root.failed ? 1.28 :
        root.recovering ? 0.68 :
        root.awaiting ? 0.08 :
        root.stopped ? 0.015 :
        0.28

    readonly property real coreBreath:
        root.stopped ? 0.84 :
        root.idle ? 0.985 + root.slowPulse * 0.030 :
        root.listening ? 0.99 + root.listenDrive * 0.055 :
        root.speaking ? 0.99 + root.speechDrive * 0.060 :
        root.successful ? 1.050 :
        root.failed ? 0.965 + root.pulse * 0.016 :
        1.0 + root.pulse * 0.014

    // Internal Z behaviour. The shell stays coherent; only selected layers move.
    readonly property real rearDepth:
        root.failed ? -64.0 + root.drift2 * 7.0 :
        root.recovering ? -68.0 + root.pulse * 4.0 :
        -70.0

    readonly property real sapphireDepth:
        root.executing ? 22.0 :
        root.verifying ? 14.0 + root.drift * 8.0 :
        16.0

    readonly property real nucleusDepth:
        root.executing ? 46.0 :
        root.verifying ? 34.0 + root.drift * 10.0 :
        root.speaking ? 37.0 + root.speechDrive * 6.0 :
        36.0

    readonly property real frontLensDepth:
        root.listening ? 58.0 + root.listenDrive * 9.0 :
        root.speaking ? 58.0 + root.speechDrive * 6.0 :
        root.successful ? 64.0 :
        58.0

    function rgbaString(c, a) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, a))
            + ")"
    }

    // ------------------------------------------------------------------------
    // BACKGROUND AURA — simple R11Q family
    // ------------------------------------------------------------------------
    Canvas {
        id: auraCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var base = Math.min(width, height) * 0.128
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            var aura = ctx.createRadialGradient(
                cx, cy, base * 0.25,
                cx, cy, base * (2.9 + root.glowDrive * 0.16)
            )

            aura.addColorStop(
                0.0,
                root.rgbaString(tone, 0.19 * root.glowDrive)
            )

            aura.addColorStop(
                0.40,
                root.rgbaString(tone, 0.065 * root.glowDrive)
            )

            aura.addColorStop(
                1.0,
                root.rgbaString(tone, 0.0)
            )

            ctx.fillStyle = aura
            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                base * (3.0 + root.glowDrive * 0.16),
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            if (root.listening) {
                for (var i = 0; i < 3; ++i) {
                    var travel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + i / 3.0
                        ) % 1.0

                    var rr =
                        base
                        * (
                            1.55
                            + travel * (1.15 + root.listenDrive * 0.50)
                        )

                    ctx.lineWidth = Math.max(1.0, base * 0.010)

                    ctx.strokeStyle =
                        root.rgbaString(
                            tone,
                            (1.0 - travel)
                            * (0.075 + root.listenDrive * 0.16)
                        )

                    ctx.beginPath()
                    ctx.arc(cx, cy, rr, 0, Math.PI * 2.0)
                    ctx.stroke()
                }
            }

            if (root.speaking) {
                for (var s = 0; s < 3; ++s) {
                    var speechTravel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + s / 3.0
                        ) % 1.0

                    var sr =
                        base
                        * (
                            1.48
                            + speechTravel * (1.00 + root.speechDrive * 0.44)
                        )

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            base * (0.009 + root.speechDrive * 0.005)
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            "#FFD08A",
                            (1.0 - speechTravel)
                            * (0.07 + root.speechDrive * 0.16)
                        )

                    ctx.beginPath()
                    ctx.arc(cx, cy, sr, 0, Math.PI * 2.0)
                    ctx.stroke()
                }
            }
        }
    }

    // ========================================================================
    // TRUE 3D CORE — MISTRAL CANDIDATE
    // ========================================================================
    View3D {
        id: view3D
        anchors.centerIn: parent

        // Approx 25–30% stronger presence than old R11Q-D.
        width: Math.min(root.width, root.height) * 0.66
        height: width

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 420)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1400
        }

        // --------------------------------------------------------------------
        // CINEMATIC LIGHTING
        // --------------------------------------------------------------------
        DirectionalLight {
            eulerRotation: Qt.vector3d(-35, 36, -7)
            color: "#EAF2FF"
            brightness: 2.20
            ambientColor: "#0E1420"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(29, -48, 14)
            color: "#7896C8"
            brightness: 0.72
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position: Qt.vector3d(-64, 54, 130)
            color: root.displayTone
            brightness: 1.10 + root.glowDrive * 1.10
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000028
        }

        PointLight {
            position: Qt.vector3d(46, -32, -92)
            color: "#547FCB"
            brightness: 0.14 + root.glowDrive * 0.18
            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.000038
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: rearMaterial

            baseColor: "#070A10"
            metalness: 0.50
            roughness: 0.28
            clearcoatAmount: 0.32
            clearcoatRoughnessAmount: 0.11

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.08,
                    root.displayTone.g * root.glowDrive * 0.08,
                    root.displayTone.b * root.glowDrive * 0.08
                )
        }

        PrincipledMaterial {
            id: shellMaterial

            baseColor: "#0D121A"
            metalness: 0.78
            roughness: 0.24
            clearcoatAmount: 0.48
            clearcoatRoughnessAmount: 0.08

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.11,
                    root.displayTone.g * root.glowDrive * 0.11,
                    root.displayTone.b * root.glowDrive * 0.11
                )
        }

        PrincipledMaterial {
            id: shellEdgeMaterial

            baseColor: "#B8C4D3"
            metalness: 0.88
            roughness: 0.16
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.06

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.12,
                    root.displayTone.g * root.glowDrive * 0.12,
                    root.displayTone.b * root.glowDrive * 0.12
                )
        }

        PrincipledMaterial {
            id: sapphireRearMaterial

            baseColor: Qt.rgba(0.035, 0.09, 0.28, 0.68)
            metalness: 0.04
            roughness: 0.18
            clearcoatAmount: 0.50
            clearcoatRoughnessAmount: 0.07
            alphaMode: PrincipledMaterial.Blend

            emissiveFactor:
                Qt.vector3d(
                    0.02 + root.displayTone.r * root.glowDrive * 0.24,
                    0.06 + root.displayTone.g * root.glowDrive * 0.40,
                    0.20 + root.displayTone.b * root.glowDrive * 0.72
                )
        }

        PrincipledMaterial {
            id: sapphireMainMaterial

            baseColor: Qt.rgba(0.06, 0.18, 0.62, 0.82)
            metalness: 0.03
            roughness: 0.11
            clearcoatAmount: 0.72
            clearcoatRoughnessAmount: 0.045
            alphaMode: PrincipledMaterial.Blend

            emissiveFactor:
                Qt.vector3d(
                    0.04 + root.displayTone.r * root.glowDrive * 0.45,
                    0.14 + root.displayTone.g * root.glowDrive * 0.68,
                    0.48 + root.displayTone.b * root.glowDrive * 1.00
                )
        }

        PrincipledMaterial {
            id: nucleusMaterial

            baseColor: "#04070D"
            metalness: 0.20
            roughness: 0.16
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.06

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.72,
                    root.displayTone.g * root.glowDrive * 0.72,
                    root.displayTone.b * root.glowDrive * 0.72
                )
        }

        PrincipledMaterial {
            id: lensMaterial

            baseColor:
                Qt.rgba(
                    0.12 + root.displayTone.r * 0.08,
                    0.15 + root.displayTone.g * 0.08,
                    0.22 + root.displayTone.b * 0.10,
                    0.22
                )

            metalness: 0.02
            roughness: 0.055
            clearcoatAmount: 0.92
            clearcoatRoughnessAmount: 0.03
            transmissionFactor: 0.72
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: goldMaterial

            baseColor: root.restrainedGold
            metalness: 0.86
            roughness: 0.18
            clearcoatAmount: 0.38
            clearcoatRoughnessAmount: 0.08

            emissiveFactor:
                Qt.vector3d(
                    root.restrainedGold.r * root.filamentActivity * 0.74,
                    root.restrainedGold.g * root.filamentActivity * 0.74,
                    root.restrainedGold.b * root.filamentActivity * 0.74
                )
        }

        PrincipledMaterial {
            id: particleMaterial

            baseColor: root.displayTone
            metalness: 0.03
            roughness: 0.16

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * 1.45,
                    root.displayTone.g * 1.45,
                    root.displayTone.b * 1.45
                )
        }

        // ====================================================================
        // MASTER CORE — SUBTLE PERMANENT 3/4 PRESENTATION
        // ====================================================================
        Node {
            id: coreAssembly

            scale:
                Qt.vector3d(
                    root.coreBreath,
                    root.coreBreath,
                    root.coreBreath
                )

            eulerRotation:
                Qt.vector3d(
                    -8.0 + root.drift2 * 0.40 * root.motionGate,

                    -15.0
                    + root.drift * 0.75 * root.motionGate
                    + (root.failed ? root.drift2 * 1.6 : 0.0),

                    1.4
                    + root.drift2 * 0.22 * root.motionGate
                )

            // ----------------------------------------------------------------
            // 1. REAR SHADOW / CAVITY
            // ----------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        -8.0,
                        4.0,
                        root.rearDepth
                    )

                scale:
                    Qt.vector3d(
                        1.10,
                        1.04,
                        0.68
                    )

                materials: [rearMaterial]
            }

            // ----------------------------------------------------------------
            // 2. FEWER / THICKER INTERNAL SHELL MASSES
            // Mostly inside the overall spherical silhouette.
            // ----------------------------------------------------------------
            Node {
                id: shellMasses

                // Front upper-left.
                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            -34.0 - root.shellOpen * 6.0,
                            34.0 + root.shellOpen * 3.0,
                            70.0 + root.shellOpen * 7.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            15,
                            -24,
                            28
                        )

                    scale:
                        Qt.vector3d(
                            0.54,
                            0.13,
                            0.18
                        )

                    materials: [shellMaterial]
                }

                // Front lower-right.
                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            38.0 + root.shellOpen * 6.0,
                            -24.0 - root.shellOpen * 2.0,
                            64.0 + root.shellOpen * 6.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            -12,
                            22,
                            -24
                        )

                    scale:
                        Qt.vector3d(
                            0.50,
                            0.14,
                            0.17
                        )

                    materials: [shellMaterial]
                }

                // Mid-left structural bridge.
                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            -50.0 - root.shellOpen * 4.0,
                            -2.0,
                            6.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            4,
                            18,
                            -8
                        )

                    scale:
                        Qt.vector3d(
                            0.18,
                            0.64,
                            0.16
                        )

                    materials: [shellEdgeMaterial]
                }

                // Rear upper architecture.
                Model {
                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            14.0,
                            38.0,
                            -58.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            8,
                            -10,
                            -8
                        )

                    scale:
                        Qt.vector3d(
                            0.58,
                            0.14,
                            0.20
                        )

                    materials: [shellMaterial]
                }
            }

            // ----------------------------------------------------------------
            // 3. LAYERED SAPPHIRE ENERGY CHAMBER
            // ----------------------------------------------------------------
            Node {
                id: energyChamber

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.phase * 5.0
                            : root.drift * 1.2,

                        root.planning
                            ? -root.phase * 8.5
                            : root.drift2 * 1.5,

                        root.executing
                            ? root.phase * 2.0
                            : 0.0
                    )

                // Rear sapphire layer.
                Model {
                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            -2.0,
                            1.0,
                            -14.0
                        )

                    scale:
                        Qt.vector3d(
                            0.82,
                            0.82,
                            0.56
                        )

                    materials: [sapphireRearMaterial]
                }

                // Main sapphire body.
                Model {
                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            1.5,
                            -1.0,
                            root.sapphireDepth
                        )

                    scale:
                        Qt.vector3d(
                            0.68
                            + root.listenDrive * 0.035,

                            0.68
                            + root.listenDrive * 0.035,

                            0.52
                            + root.speechDrive * 0.030
                        )

                    materials: [sapphireMainMaterial]
                }

                // Cognition nucleus.
                Model {
                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            root.executing ? 5.0 : -2.0,

                            root.verifying
                                ? root.drift * 3.0
                                : 2.0,

                            root.nucleusDepth
                        )

                    scale:
                        Qt.vector3d(
                            0.275
                            + root.speechDrive * 0.022,

                            0.275
                            + root.speechDrive * 0.022,

                            0.25
                        )

                    materials: [nucleusMaterial]
                }

                // Front containment lens.
                Model {
                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            0,
                            0,
                            root.frontLensDepth
                        )

                    scale:
                        Qt.vector3d(
                            0.92,
                            0.92,
                            0.135
                        )

                    materials: [lensMaterial]
                }
            }

            // ----------------------------------------------------------------
            // 4. SPARSE GOLD NEURAL PATHS
            // ----------------------------------------------------------------
            Node {
                id: goldFilaments

                opacity:
                    0.12
                    + root.filamentActivity * 0.70

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.drift * 2.2
                            : 0.0,

                        root.planning
                            ? root.phase * 5.2
                            : root.phase * 0.55,

                        root.speaking
                            ? root.speechDrive * 2.2
                            : 0.0
                    )

                // Path A: three short segments imply a bend.
                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(22, 11, 30)
                    eulerRotation: Qt.vector3d(54, -30, 8)
                    scale: Qt.vector3d(0.022, 0.36, 0.022)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(10, 5, 16)
                    eulerRotation: Qt.vector3d(68, -18, 18)
                    scale: Qt.vector3d(0.019, 0.30, 0.019)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(2, 2, 8)
                    eulerRotation: Qt.vector3d(80, -8, 26)
                    scale: Qt.vector3d(0.017, 0.25, 0.017)
                    materials: [goldMaterial]
                }

                // Path B.
                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(-22, -14, 16)
                    eulerRotation: Qt.vector3d(-46, 48, -10)
                    scale: Qt.vector3d(0.021, 0.38, 0.021)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(-10, -7, 7)
                    eulerRotation: Qt.vector3d(-62, 28, -18)
                    scale: Qt.vector3d(0.018, 0.28, 0.018)
                    materials: [goldMaterial]
                }

                // Deep path.
                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(8, 18, -22)
                    eulerRotation: Qt.vector3d(26, 18, 68)
                    scale: Qt.vector3d(0.020, 0.34, 0.020)
                    materials: [goldMaterial]
                }

                // Two junction nodes.
                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(14, 7, 22)
                    scale: Qt.vector3d(0.040, 0.040, 0.040)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(-14, -9, 10)
                    scale: Qt.vector3d(0.036, 0.036, 0.036)
                    materials: [goldMaterial]
                }
            }

            // ----------------------------------------------------------------
            // 5. TRUE 3D PARTICLES — 40, large Z distribution
            // ----------------------------------------------------------------
            Repeater3D {
                model: 40

                delegate: Model {
                    property real baseAngle:
                        (index / 40.0)
                        * Math.PI
                        * 2.0

                    property real angle:
                        baseAngle
                        + root.phase
                        * root.particleSpeed

                    property real band:
                        index % 5

                    property real baseRadius:
                        70.0 + band * 10.0

                    property real listeningPull:
                        root.listening
                        ? root.listenDrive * 10.0
                        : 0.0

                    property real actualRadius:
                        Math.max(
                            40.0,
                            baseRadius - listeningPull
                        )

                    property real depthZ:
                        Math.sin(
                            angle * 1.50
                            + index * 0.71
                        )
                        * (
                            45.0
                            + band * 7.0
                        )
                        + (
                            index % 4 === 0 ? -18.0 :
                            index % 4 === 1 ? 10.0 :
                            index % 4 === 2 ? 24.0 :
                            -4.0
                        )

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(angle)
                            * actualRadius,

                            Math.sin(angle)
                            * actualRadius
                            * (
                                0.58
                                + band * 0.035
                            ),

                            depthZ
                        )

                    scale:
                        Qt.vector3d(
                            0.014
                            + (
                                index % 4
                              )
                              * 0.004,

                            0.014
                            + (
                                index % 4
                              )
                              * 0.004,

                            0.014
                            + (
                                index % 4
                              )
                              * 0.004
                        )

                    materials: [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // VERY SMALL FRONT SPECULAR ONLY
    // No full 2D orb overlay.
    // ------------------------------------------------------------------------
    Canvas {
        id: accentCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.11

            ctx.clearRect(0, 0, width, height)

            ctx.lineWidth = Math.max(1.0, r * 0.018)
            ctx.strokeStyle = "rgba(255,255,255,0.18)"
            ctx.beginPath()
            ctx.arc(
                cx - r * 0.02,
                cy - r * 0.02,
                r * 0.67,
                Math.PI * 1.10,
                Math.PI * 1.47
            )
            ctx.stroke()

            ctx.lineWidth = Math.max(1.0, r * 0.009)
            ctx.strokeStyle =
                root.rgbaString(
                    root.displayTone,
                    0.18 * root.glowDrive
                )

            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 0.82,
                Math.PI * 0.07,
                Math.PI * 0.40
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

    onAudioLevelChanged:
        auraCanvas.requestPaint()

    onSpeechLevelChanged:
        auraCanvas.requestPaint()
}
