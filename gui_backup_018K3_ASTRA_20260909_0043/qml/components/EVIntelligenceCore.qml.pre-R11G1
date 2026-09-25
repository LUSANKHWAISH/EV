import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11Q.2 "EV CRYSTAL CORE"
// ============================================================================
//
// QML translation of the supplied luxury crystalline energy-core concept.
//
// IMPORTANT:
// - The visual identity and product name are EV CORE.
// - No Blender.
// - No GLB assets.
// - No browser / Three.js runtime.
// - No Web Speech API inside QML.
// - Existing E.V. state architecture is preserved.
//
// Visual language translated from the supplied concept:
// - obsidian / black-glass crystalline shell
// - deep sapphire intelligence chamber
// - warm gold filament lattice
// - internal particle energy flow
// - breathing IDLE
// - shell opening while LISTENING
// - faster inner rotation while PLANNING
// - stronger forward drive while EXECUTING
// - depth-focus while VERIFYING
// - gold speech pulse while SPEAKING
// - controlled SUCCESS / FAILED / RECOVERING behaviour
//
// R11Q.2 intentionally keeps the elegant aura / ripple language of R11Q,
// while the focal object is now a layered true-3D crystalline energy heart.
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

    // Future live voice hooks.
    // These are optional. Demo states synthesize tasteful fallback motion.
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ------------------------------------------------------------------------
    // MOTION CLOCK
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1450 :
        root.failed ? 1350 :
        root.verifying ? 1900 :
        root.speaking ? 1550 :
        root.planning ? 2050 :
        root.listening ? 1700 :
        root.recovering ? 2700 :
        root.awaiting ? 6200 :
        root.successful ? 2300 :
        5200

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    readonly property real pulse:
        (Math.sin(root.phase) + 1.0) * 0.5

    readonly property real slowPulse:
        (Math.sin(root.phase * 0.52) + 1.0) * 0.5

    readonly property real drift:
        Math.sin(root.phase * 0.39)

    readonly property real drift2:
        Math.cos(root.phase * 0.31)

    // ------------------------------------------------------------------------
    // EV CORE COLOUR LANGUAGE
    // ------------------------------------------------------------------------
    readonly property color sapphire: "#246CFF"
    readonly property color deepSapphire: "#123A9C"
    readonly property color electricSapphire: "#58B8FF"
    readonly property color luxuryGold: "#D7AD69"
    readonly property color warmGold: "#FFD08A"
    readonly property color obsidian: "#070A10"

    readonly property color displayTone:
        root.idle ? root.deepSapphire :
        root.listening ? root.electricSapphire :
        root.planning ? root.luxuryGold :
        root.speaking ? root.warmGold :
        root.stateTone

    readonly property color particleTone:
        root.speaking ? root.warmGold :
        root.planning ? root.luxuryGold :
        root.listening ? root.electricSapphire :
        root.executing ? root.stateTone :
        root.sapphire

    // ------------------------------------------------------------------------
    // VOICE / STATE DRIVES
    // ------------------------------------------------------------------------
    readonly property real syntheticListen:
        root.listening ? 0.18 + root.pulse * 0.34 : 0.0

    readonly property real syntheticSpeech:
        root.speaking
        ? 0.16 + Math.max(0.0, Math.sin(root.phase * 3.1)) * 0.52
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

    readonly property real intensity:
        root.stopped ? 0.03 :
        root.listening ? 0.72 + root.listenDrive * 0.58 :
        root.speaking ? 0.78 + root.speechDrive * 0.62 :
        root.planning ? 1.02 :
        root.executing ? 1.18 :
        root.verifying ? 0.92 :
        root.successful ? 1.16 :
        root.failed ? 0.74 :
        root.recovering ? 0.82 :
        root.awaiting ? 0.34 :
        0.58

    readonly property real shellOpen:
        root.listening ? root.listenDrive :
        root.executing ? 0.28 :
        root.successful ? 0.22 :
        root.failed ? 0.15 :
        0.0

    readonly property real filamentDrive:
        root.speaking ? 0.72 + root.speechDrive * 0.50 :
        root.planning ? 0.88 :
        root.executing ? 0.72 :
        root.listening ? 0.42 + root.listenDrive * 0.30 :
        root.successful ? 0.86 :
        root.failed ? 0.28 :
        root.stopped ? 0.03 :
        0.34

    readonly property real particleSpeed:
        root.planning ? 1.72 :
        root.executing ? 2.28 :
        root.verifying ? 1.02 :
        root.speaking ? 1.16 :
        root.listening ? 1.28 :
        root.failed ? 1.66 :
        root.recovering ? 0.78 :
        0.34

    readonly property real coreBreath:
        root.stopped ? 0.84 :
        root.idle ? 0.985 + root.slowPulse * 0.030 :
        root.listening ? 0.985 + root.listenDrive * 0.080 :
        root.speaking ? 0.992 + root.speechDrive * 0.070 :
        root.successful ? 1.045 :
        root.failed ? 0.965 + root.pulse * 0.020 :
        1.0 + root.pulse * 0.016

    readonly property real motionGate:
        root.awaiting ? 0.06 : 1.0

    readonly property real viewSize:
        Math.max(
            220.0,
            Math.min(root.width, root.height) * 0.62
        )

    // ------------------------------------------------------------------------
    // HELPER
    // ------------------------------------------------------------------------
    function rgbaString(c, a) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, a))
            + ")"
    }

    // ------------------------------------------------------------------------
    // R11Q BACKGROUND AURA — KEEP THE PART THAT ALREADY LOOKED GOOD
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

            // Wide premium aura.
            var aura = ctx.createRadialGradient(
                cx,
                cy,
                r * 0.18,
                cx,
                cy,
                r * (3.0 + root.intensity * 0.28)
            )

            aura.addColorStop(
                0.0,
                root.rgbaString(
                    tone,
                    0.20 * root.intensity
                )
            )

            aura.addColorStop(
                0.34,
                root.rgbaString(
                    tone,
                    0.075 * root.intensity
                )
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
                r * (3.1 + root.intensity * 0.28),
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            // LISTENING — quiet expanding sapphire waves.
            if (root.listening) {
                for (var i = 0; i < 3; ++i) {
                    var travel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + i / 3.0
                        ) % 1.0

                    var rr =
                        r
                        * (
                            1.55
                            + travel
                            * (
                                1.15
                                + root.listenDrive * 0.55
                            )
                        )

                    ctx.lineWidth =
                        Math.max(1.0, r * 0.010)

                    ctx.strokeStyle =
                        root.rgbaString(
                            tone,
                            (1.0 - travel)
                            * (
                                0.08
                                + root.listenDrive * 0.16
                            )
                        )

                    ctx.beginPath()
                    ctx.arc(
                        cx,
                        cy,
                        rr,
                        0,
                        Math.PI * 2.0
                    )
                    ctx.stroke()
                }
            }

            // SPEAKING — warmer rhythmic pulse.
            if (root.speaking) {
                for (var s = 0; s < 3; ++s) {
                    var speechTravel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + s / 3.0
                        ) % 1.0

                    var sr =
                        r
                        * (
                            1.48
                            + speechTravel
                            * (
                                1.05
                                + root.speechDrive * 0.50
                            )
                        )

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            r
                            * (
                                0.009
                                + root.speechDrive * 0.005
                            )
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            root.warmGold,
                            (1.0 - speechTravel)
                            * (
                                0.08
                                + root.speechDrive * 0.18
                            )
                        )

                    ctx.beginPath()
                    ctx.arc(
                        cx,
                        cy,
                        sr,
                        0,
                        Math.PI * 2.0
                    )
                    ctx.stroke()
                }
            }

            // VERIFYING — restrained precision halo.
            if (root.verifying) {
                var vr =
                    r
                    * (
                        1.56
                        + root.pulse * 0.18
                    )

                ctx.lineWidth =
                    Math.max(1.0, r * 0.009)

                ctx.strokeStyle =
                    root.rgbaString(
                        tone,
                        0.16
                    )

                ctx.beginPath()
                ctx.arc(
                    cx,
                    cy,
                    vr,
                    0,
                    Math.PI * 2.0
                )
                ctx.stroke()
            }

            // FAILED — mild fracture echo only.
            if (root.failed) {
                ctx.lineWidth =
                    Math.max(1.0, r * 0.010)

                ctx.strokeStyle =
                    root.rgbaString(
                        tone,
                        0.13
                    )

                for (var f = 0; f < 2; ++f) {
                    var offset =
                        f * Math.PI
                        + root.phase * 0.45

                    ctx.beginPath()
                    ctx.arc(
                        cx,
                        cy,
                        r * (1.62 + f * 0.22),
                        offset,
                        offset + Math.PI * 0.62
                    )
                    ctx.stroke()
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // TRUE 3D EV CRYSTAL CORE
    // ------------------------------------------------------------------------
    View3D {
        id: crystalView
        anchors.centerIn: parent
        width: root.viewSize
        height: root.viewSize

        environment: SceneEnvironment {
            backgroundMode:
                SceneEnvironment.Transparent

            antialiasingMode:
                SceneEnvironment.MSAA

            antialiasingQuality:
                SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera

            position:
                Qt.vector3d(
                    0,
                    0,
                    385
                )

            fieldOfView: 39
            clipNear: 1
            clipFar: 1200
        }

        // --------------------------------------------------------------------
        // CINEMATIC LIGHTING
        // --------------------------------------------------------------------
        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    -28,
                    36,
                    -6
                )

            color: "#FFF5E6"
            brightness: 2.5
            ambientColor: "#111522"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    30,
                    -44,
                    14
                )

            color: "#789EFF"
            brightness: 0.78
            ambientColor: "#05080F"
            castsShadow: false
        }

        PointLight {
            position:
                Qt.vector3d(
                    -70,
                    62,
                    126
                )

            color:
                root.displayTone

            brightness:
                0.95
                + root.intensity * 1.20

            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000028
        }

        PointLight {
            position:
                Qt.vector3d(
                    60,
                    -44,
                    82
                )

            color:
                root.luxuryGold

            brightness:
                0.26
                + root.filamentDrive * 0.40

            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000030
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: obsidianMaterial

            baseColor:
                Qt.rgba(
                    0.018
                    + root.displayTone.r * 0.045,
                    0.022
                    + root.displayTone.g * 0.045,
                    0.032
                    + root.displayTone.b * 0.045,
                    1.0
                )

            metalness: 0.76
            roughness: 0.12
            clearcoatAmount: 0.74
            clearcoatRoughnessAmount: 0.055

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.intensity
                    * 0.12,

                    root.displayTone.g
                    * root.intensity
                    * 0.12,

                    root.displayTone.b
                    * root.intensity
                    * 0.12
                )
        }

        PrincipledMaterial {
            id: shardEdgeMaterial

            baseColor:
                Qt.rgba(
                    0.13
                    + root.displayTone.r * 0.16,
                    0.15
                    + root.displayTone.g * 0.16,
                    0.20
                    + root.displayTone.b * 0.16,
                    1.0
                )

            metalness: 0.90
            roughness: 0.10
            clearcoatAmount: 0.64
            clearcoatRoughnessAmount: 0.045

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.intensity
                    * 0.20,

                    root.displayTone.g
                    * root.intensity
                    * 0.20,

                    root.displayTone.b
                    * root.intensity
                    * 0.20
                )
        }

        PrincipledMaterial {
            id: sapphireMaterial

            baseColor:
                Qt.rgba(
                    0.08,
                    0.20
                    + root.displayTone.g * 0.26,
                    0.48
                    + root.displayTone.b * 0.36,
                    1.0
                )

            metalness: 0.10
            roughness: 0.10
            clearcoatAmount: 0.72
            clearcoatRoughnessAmount: 0.045

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.intensity
                    * 1.10,

                    root.displayTone.g
                    * root.intensity
                    * 1.10,

                    root.displayTone.b
                    * root.intensity
                    * 1.10
                )
        }

        PrincipledMaterial {
            id: nucleusMaterial

            baseColor: "#04060C"
            metalness: 0.22
            roughness: 0.13
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.055

            emissiveFactor:
                Qt.vector3d(
                    root.particleTone.r
                    * root.intensity
                    * 0.64,

                    root.particleTone.g
                    * root.intensity
                    * 0.64,

                    root.particleTone.b
                    * root.intensity
                    * 0.64
                )
        }

        PrincipledMaterial {
            id: goldMaterial

            baseColor:
                root.luxuryGold

            metalness: 0.72
            roughness: 0.16
            clearcoatAmount: 0.42
            clearcoatRoughnessAmount: 0.07

            emissiveFactor:
                Qt.vector3d(
                    root.luxuryGold.r
                    * root.filamentDrive
                    * 1.05,

                    root.luxuryGold.g
                    * root.filamentDrive
                    * 1.05,

                    root.luxuryGold.b
                    * root.filamentDrive
                    * 1.05
                )
        }

        PrincipledMaterial {
            id: particleMaterial

            baseColor:
                root.particleTone

            metalness: 0.04
            roughness: 0.12

            emissiveFactor:
                Qt.vector3d(
                    root.particleTone.r * 1.55,
                    root.particleTone.g * 1.55,
                    root.particleTone.b * 1.55
                )
        }

        // --------------------------------------------------------------------
        // MASTER EV CORE GROUP
        // --------------------------------------------------------------------
        Node {
            id: coreGroup

            scale:
                Qt.vector3d(
                    root.coreBreath,
                    root.coreBreath,
                    root.coreBreath
                )

            eulerRotation:
                Qt.vector3d(
                    -7.0
                    + root.drift2
                    * 1.0
                    * root.motionGate,

                    -13.0
                    + root.phase
                    * (
                        root.planning
                            ? 4.0
                            : root.executing
                                ? 5.5
                                : 0.42
                    )
                    * root.motionGate,

                    root.failed
                        ? Math.sin(root.phase * 3.7) * 1.6
                        : root.drift * 0.50 * root.motionGate
                )

            // ---------------------------------------------------------------
            // DEEP OBSIDIAN BODY
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                scale:
                    Qt.vector3d(
                        1.04,
                        1.04,
                        1.04
                    )

                materials:
                    [obsidianMaterial]
            }

            // ---------------------------------------------------------------
            // INNER SAPPHIRE ENERGY HEART
            // ---------------------------------------------------------------
            Model {
                id: innerEnergy

                source: "#Sphere"

                position:
                    Qt.vector3d(
                        root.executing ? 4.5 : 0.0,
                        root.verifying ? root.drift * 3.0 : 0.0,
                        15
                    )

                scale:
                    Qt.vector3d(
                        0.50
                        + root.listenDrive * 0.060
                        + root.speechDrive * 0.050,

                        0.50
                        + root.listenDrive * 0.060
                        + root.speechDrive * 0.050,

                        0.48
                        + root.speechDrive * 0.035
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.phase
                        * (
                            root.planning ? 18.0 : 4.0
                        ),

                        -root.phase
                        * (
                            root.planning ? 26.0 : 6.0
                        ),

                        root.phase * 3.0
                    )

                materials:
                    [sapphireMaterial]
            }

            // ---------------------------------------------------------------
            // DARK COGNITION NUCLEUS
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        -3.0,
                        2.0,
                        39
                    )

                scale:
                    Qt.vector3d(
                        0.205
                        + root.speechDrive * 0.020,

                        0.205
                        + root.speechDrive * 0.020,

                        0.190
                    )

                materials:
                    [nucleusMaterial]
            }

            // ---------------------------------------------------------------
            // CRYSTALLINE OUTER SHELL
            //
            // These overlapping angled plates create a faceted obsidian
            // crystal around the solid body. Listening physically opens them.
            // ---------------------------------------------------------------
            Repeater3D {
                model: 18

                delegate: Model {
                    property real shardAngle:
                        (index / 18.0) * Math.PI * 2.0

                    property real layer:
                        index % 3

                    property real shardRadius:
                        50.0
                        + layer * 4.5
                        + root.shellOpen
                        * (
                            8.0
                            + layer * 2.0
                        )

                    property real shardWave:
                        root.speaking
                            ? Math.sin(
                                root.phase * 3.0
                                + index * 0.72
                              )
                              * root.speechDrive
                              * 4.0
                            : 0.0

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(shardAngle)
                            * (
                                shardRadius
                                + shardWave
                            ),

                            Math.sin(shardAngle)
                            * (
                                shardRadius
                                + shardWave
                            )
                            * 0.90,

                            (
                                layer - 1
                            )
                            * 17.0
                            + Math.sin(
                                shardAngle * 2.0
                                + index
                              )
                              * 6.0
                        )

                    eulerRotation:
                        Qt.vector3d(
                            -16.0
                            + layer * 15.0
                            + Math.sin(shardAngle) * 14.0,

                            18.0
                            + Math.cos(shardAngle) * 18.0,

                            shardAngle
                            * 180.0
                            / Math.PI
                            + 90.0
                            + (
                                index % 2 === 0
                                    ? 7.0
                                    : -6.0
                              )
                        )

                    scale:
                        Qt.vector3d(
                            0.34
                            + (
                                index % 4
                              )
                              * 0.030,

                            0.17
                            + layer * 0.020,

                            0.055
                            + (
                                index % 2
                              )
                              * 0.012
                        )

                    materials:
                        index % 4 === 0
                            ? [shardEdgeMaterial]
                            : [obsidianMaterial]
                }
            }

            // ---------------------------------------------------------------
            // GOLD FILAMENT RING A
            // ---------------------------------------------------------------
            Node {
                id: filamentA

                eulerRotation:
                    Qt.vector3d(
                        18,
                        0,
                        root.phase
                        * (
                            root.planning ? 18.0 : 3.0
                        )
                        * root.motionGate
                    )

                Repeater3D {
                    model: 20

                    delegate: Model {
                        property real filamentAngle:
                            (index / 20.0)
                            * Math.PI
                            * 2.0

                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                Math.cos(filamentAngle) * 37.0,
                                Math.sin(filamentAngle) * 37.0,
                                2.0
                            )

                        eulerRotation.z:
                            filamentAngle
                            * 180.0
                            / Math.PI
                            + 90.0

                        scale:
                            Qt.vector3d(
                                0.095,
                                0.012
                                + root.filamentDrive * 0.004,
                                0.012
                            )

                        materials:
                            [goldMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // GOLD FILAMENT RING B
            // ---------------------------------------------------------------
            Node {
                id: filamentB

                eulerRotation:
                    Qt.vector3d(
                        67,
                        13,
                        -root.phase
                        * (
                            root.planning ? 15.0 : 2.3
                        )
                        * root.motionGate
                    )

                Repeater3D {
                    model: 18

                    delegate: Model {
                        property real filamentAngle:
                            (index / 18.0)
                            * Math.PI
                            * 2.0

                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                Math.cos(filamentAngle) * 40.0,
                                Math.sin(filamentAngle) * 40.0,
                                -3.0
                            )

                        eulerRotation.z:
                            filamentAngle
                            * 180.0
                            / Math.PI
                            + 90.0

                        scale:
                            Qt.vector3d(
                                0.105,
                                0.010
                                + root.filamentDrive * 0.004,
                                0.010
                            )

                        materials:
                            [goldMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // GOLD FILAMENT RING C
            // ---------------------------------------------------------------
            Node {
                id: filamentC

                eulerRotation:
                    Qt.vector3d(
                        -23,
                        71,
                        root.phase
                        * (
                            root.planning ? 12.0 : 1.8
                        )
                        * root.motionGate
                    )

                Repeater3D {
                    model: 16

                    delegate: Model {
                        property real filamentAngle:
                            (index / 16.0)
                            * Math.PI
                            * 2.0

                        source: "#Cube"

                        position:
                            Qt.vector3d(
                                Math.cos(filamentAngle) * 34.0,
                                Math.sin(filamentAngle) * 34.0,
                                0.0
                            )

                        eulerRotation.z:
                            filamentAngle
                            * 180.0
                            / Math.PI
                            + 90.0

                        scale:
                            Qt.vector3d(
                                0.090,
                                0.010
                                + root.filamentDrive * 0.004,
                                0.010
                            )

                        materials:
                            [goldMaterial]
                    }
                }
            }

            // ---------------------------------------------------------------
            // INTERNAL ENERGY PARTICLES
            //
            // True 3D particles with spherical depth distribution.
            // ---------------------------------------------------------------
            Repeater3D {
                model: 36

                delegate: Model {
                    property real particleBase:
                        (index / 36.0)
                        * Math.PI
                        * 2.0

                    property real particleAngle:
                        particleBase
                        + root.phase
                        * root.particleSpeed

                    property real particleBand:
                        index % 4

                    property real particleRadius:
                        25.0
                        + particleBand * 12.0

                    property real inwardDrive:
                        root.listening
                            ? root.listenDrive * 8.0
                            : 0.0

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(particleAngle)
                            * (
                                particleRadius
                                - inwardDrive
                            ),

                            Math.sin(particleAngle)
                            * (
                                particleRadius
                                - inwardDrive
                            )
                            * (
                                0.72
                                + particleBand * 0.045
                            ),

                            Math.sin(
                                particleAngle * 1.7
                                + index * 0.67
                            )
                            * (
                                22.0
                                + particleBand * 5.0
                            )
                        )

                    scale:
                        Qt.vector3d(
                            0.014
                            + (
                                index % 3
                              )
                              * 0.005
                            + root.intensity * 0.002,

                            0.014
                            + (
                                index % 3
                              )
                              * 0.005
                            + root.intensity * 0.002,

                            0.014
                            + (
                                index % 3
                              )
                              * 0.005
                            + root.intensity * 0.002
                        )

                    materials:
                        [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // MINIMAL FRONT SPECULAR DETAIL
    // ------------------------------------------------------------------------
    Canvas {
        id: accentCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.082

            ctx.clearRect(
                0,
                0,
                width,
                height
            )

            // Luxury glass glint.
            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.022
                )

            ctx.strokeStyle =
                "rgba(255,255,255,0.20)"

            ctx.beginPath()
            ctx.arc(
                cx - r * 0.025,
                cy - r * 0.020,
                r * 0.76,
                Math.PI * 1.12,
                Math.PI * 1.49
            )
            ctx.stroke()

            // Very thin state-colour micro-edge.
            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.010
                )

            ctx.strokeStyle =
                root.rgbaString(
                    root.displayTone,
                    0.22 * root.intensity
                )

            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 0.92,
                Math.PI * 0.08,
                Math.PI * 0.45
            )
            ctx.stroke()
        }
    }

    // ------------------------------------------------------------------------
    // REPAINT HOOKS
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
