import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11Q-D DEPTH REFINEMENT
// ============================================================================
//
// BASELINE:
//   R11Q Living Energy Core — the visual direction the user preferred.
//
// THIS REVISION IS NOT A REDESIGN.
// It keeps the original R11Q:
// - aura language
// - central living orb
// - state colours
// - listening ripples
// - speaking pulses
// - planning/executing constellation
// - elegant minimal silhouette
//
// ONLY DEPTH IS REFINED:
// - recessed rear shadow shell
// - layered sapphire energy volume
// - separate dark cognition nucleus
// - shallow front containment lens
// - six subtle internal depth facets
// - 18 real 3D particles spanning front / center / rear
// - slightly stronger 3/4 object presentation
// - state motion moves INTERNAL layers through Z instead of rebuilding the core
//
// QML-only. No GLB / Blender / RuntimeLoader.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // PUBLIC INTERFACE — preserve EVFlagshipStage contract
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

    // ------------------------------------------------------------------------
    // OPTIONAL REAL VOICE HOOKS
    // ------------------------------------------------------------------------
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ------------------------------------------------------------------------
    // MOTION CLOCK — retained from R11Q
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1500 :
        root.failed ? 1350 :
        root.verifying ? 1900 :
        root.speaking ? 1600 :
        root.planning ? 2200 :
        root.listening ? 1700 :
        root.recovering ? 2700 :
        root.awaiting ? 6200 :
        root.successful ? 2400 :
        5200

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.52) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.41)
    readonly property real counterDrift: Math.cos(root.phase * 0.37)

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
    // R11Q STATE LANGUAGE — retained
    // ------------------------------------------------------------------------
    readonly property color displayTone:
        root.idle ? "#34E6E0" :
        root.listening ? "#8E6BFF" :
        root.planning ? "#FF9D3D" :
        root.speaking ? "#FFCF6B" :
        root.stateTone

    readonly property real syntheticListenLevel:
        root.listening ? 0.18 + root.pulse * 0.28 : 0.0

    readonly property real syntheticSpeechLevel:
        root.speaking
        ? 0.16 + Math.max(0.0, Math.sin(root.phase * 3.0)) * 0.44
        : 0.0

    readonly property real effectiveListenLevel:
        root.listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.audioLevel > 0.01
                    ? root.audioLevel
                    : root.syntheticListenLevel
            )
        )
        : 0.0

    readonly property real effectiveSpeechLevel:
        root.speaking
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.speechLevel > 0.01
                    ? root.speechLevel
                    : root.syntheticSpeechLevel
            )
        )
        : 0.0

    readonly property real thinkingDrive:
        root.planning ? 1.0 :
        root.executing ? 0.84 :
        root.verifying ? 0.66 :
        0.0

    readonly property real disturbance:
        root.failed ? 1.0 : 0.0

    readonly property real recoveryDrive:
        root.recovering ? 1.0 : 0.0

    readonly property real motionGate:
        root.awaiting ? 0.06 : 1.0

    readonly property real coreBreath:
        root.idle ? 0.985 + root.slowPulse * 0.035 :
        root.listening ? 0.98 + root.effectiveListenLevel * 0.13 :
        root.speaking ? 0.99 + root.effectiveSpeechLevel * 0.10 :
        root.successful ? 1.055 :
        root.failed ? 0.96 + root.pulse * 0.025 :
        root.stopped ? 0.86 :
        1.0 + root.pulse * 0.025

    readonly property real glowDrive:
        root.stopped ? 0.05 :
        root.listening ? 0.70 + root.effectiveListenLevel * 0.52 :
        root.speaking ? 0.76 + root.effectiveSpeechLevel * 0.50 :
        root.planning ? 0.82 :
        root.executing ? 0.96 :
        root.verifying ? 0.92 :
        root.successful ? 1.10 :
        root.failed ? 0.68 :
        root.recovering ? 0.78 :
        root.awaiting ? 0.42 :
        0.58

    readonly property real baseRadius:
        Math.max(
            54.0,
            Math.min(root.width, root.height) * 0.165
        )

    // ------------------------------------------------------------------------
    // DEPTH REFINEMENT — deliberately small state offsets
    // ------------------------------------------------------------------------
    readonly property real rearDepthOffset:
        root.listening ? -root.effectiveListenLevel * 5.0 :
        root.failed ? root.counterDrift * 4.0 :
        root.recovering ? -2.0 + root.pulse * 2.0 :
        0.0

    readonly property real chamberDepthOffset:
        root.executing ? 6.0 :
        root.verifying ? root.drift * 6.0 :
        root.planning ? root.drift * 2.5 :
        0.0

    readonly property real lensDepthOffset:
        root.listening ? root.effectiveListenLevel * 7.0 :
        root.speaking ? root.effectiveSpeechLevel * 5.0 :
        root.successful ? 5.0 :
        0.0

    readonly property real nucleusDepthOffset:
        root.executing ? 8.0 :
        root.verifying ? root.drift * 4.0 :
        root.speaking ? root.effectiveSpeechLevel * 5.5 :
        0.0

    // ------------------------------------------------------------------------
    // HELPERS
    // ------------------------------------------------------------------------
    function rgbaString(c, alphaValue) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, alphaValue))
            + ")"
    }

    function particleAngle(indexValue, countValue, speedValue) {
        return (indexValue / countValue) * Math.PI * 2.0
            + root.phase * speedValue
    }

    // ------------------------------------------------------------------------
    // ORIGINAL R11Q BACKGROUND AURA / RIPPLES / 2D CONSTELLATION
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
            var r = root.baseRadius * root.coreBreath
            var tone = root.displayTone

            ctx.clearRect(0, 0, w, h)

            var aura = ctx.createRadialGradient(
                cx,
                cy,
                r * 0.18,
                cx,
                cy,
                r * (2.45 + root.glowDrive * 0.18)
            )

            aura.addColorStop(
                0.0,
                root.rgbaString(
                    tone,
                    0.26 * root.glowDrive
                )
            )

            aura.addColorStop(
                0.36,
                root.rgbaString(
                    tone,
                    0.11 * root.glowDrive
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
                r * (2.55 + root.glowDrive * 0.18),
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            if (root.listening) {
                ctx.lineWidth =
                    Math.max(1.0, r * 0.010)

                for (var i = 0; i < 4; ++i) {
                    var travel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + i * 0.25
                        ) % 1.0

                    var rr =
                        r
                        * (
                            1.12
                            + travel
                            * (
                                0.82
                                + root.effectiveListenLevel * 0.46
                            )
                        )

                    var alpha =
                        (1.0 - travel)
                        * (
                            0.14
                            + root.effectiveListenLevel * 0.28
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            tone,
                            alpha
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
                            1.06
                            + speechTravel
                            * (
                                0.72
                                + root.effectiveSpeechLevel * 0.44
                            )
                        )

                    var sa =
                        (1.0 - speechTravel)
                        * (
                            0.12
                            + root.effectiveSpeechLevel * 0.32
                        )

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            r
                            * (
                                0.008
                                + root.effectiveSpeechLevel * 0.007
                            )
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            tone,
                            sa
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

            var particleCount = 34

            var speed =
                root.planning ? 1.60 :
                root.executing ? 2.35 :
                root.verifying ? 1.20 :
                0.34

            for (var p = 0; p < particleCount; ++p) {
                var a =
                    root.particleAngle(
                        p,
                        particleCount,
                        speed
                    )

                var band = p % 3
                var orbit =
                    r * (1.42 + band * 0.19)

                var ellipse =
                    0.48 + band * 0.075

                if (root.listening)
                    orbit +=
                        root.effectiveListenLevel
                        * r
                        * 0.14

                var px =
                    cx
                    + Math.cos(a)
                    * orbit

                var py =
                    cy
                    + Math.sin(a)
                    * orbit
                    * ellipse

                var depth =
                    (Math.sin(a) + 1.0) * 0.5

                var pa =
                    0.10 + depth * 0.38

                if (
                    root.planning
                    || root.executing
                    || root.verifying
                )
                    pa *= 1.25
                else
                    pa *= 0.52

                var size =
                    Math.max(
                        0.8,
                        r
                        * (
                            0.006
                            + depth * 0.008
                        )
                    )

                ctx.fillStyle =
                    root.rgbaString(
                        tone,
                        pa
                    )

                ctx.beginPath()
                ctx.arc(
                    px,
                    py,
                    size,
                    0,
                    Math.PI * 2.0
                )
                ctx.fill()
            }

            if (root.verifying) {
                var vr =
                    r
                    * (
                        1.18
                        + 0.12
                        * Math.sin(
                            root.phase * 1.6
                        )
                    )

                ctx.lineWidth =
                    Math.max(
                        1.0,
                        r * 0.012
                    )

                ctx.strokeStyle =
                    root.rgbaString(
                        tone,
                        0.32
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

            if (root.failed) {
                ctx.lineWidth =
                    Math.max(
                        1.0,
                        r * 0.014
                    )

                ctx.strokeStyle =
                    root.rgbaString(
                        tone,
                        0.26
                    )

                for (var f = 0; f < 3; ++f) {
                    var offset =
                        f * Math.PI * 0.73
                        + root.phase
                        * (
                            0.4
                            + f * 0.08
                        )

                    ctx.beginPath()
                    ctx.arc(
                        cx
                        + Math.sin(
                            root.phase * 2.7 + f
                          )
                          * r
                          * 0.035,

                        cy
                        + Math.cos(
                            root.phase * 2.2 + f
                          )
                          * r
                          * 0.025,

                        r * (1.28 + f * 0.15),

                        offset,
                        offset + Math.PI * 0.72
                    )
                    ctx.stroke()
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // R11Q-D TRUE 3D FOCAL CORE
    // ------------------------------------------------------------------------
    View3D {
        id: core3D
        anchors.centerIn: parent
        width: Math.min(root.width, root.height) * 0.52
        height: width

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
            position: Qt.vector3d(0, 0, 350)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1200
        }

        // --------------------------------------------------------------------
        // LIGHTING — R11Q style, plus a restrained rear separator
        // --------------------------------------------------------------------
        DirectionalLight {
            eulerRotation:
                Qt.vector3d(-32, 38, -8)

            color: "#F4F8FF"
            brightness: 2.20
            ambientColor: "#111923"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(28, -46, 12)

            color: "#7387A3"
            brightness: 0.72
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position:
                Qt.vector3d(-62, 58, 118)

            color:
                root.displayTone

            brightness:
                1.35
                + root.glowDrive * 1.15

            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        PointLight {
            position:
                Qt.vector3d(44, -28, -86)

            color:
                root.displayTone

            brightness:
                0.18
                + root.glowDrive * 0.20

            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.000035
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: rearShellMaterial

            baseColor:
                Qt.rgba(
                    0.018
                    + root.displayTone.r * 0.045,

                    0.024
                    + root.displayTone.g * 0.045,

                    0.038
                    + root.displayTone.b * 0.045,

                    1.0
                )

            metalness: 0.42
            roughness: 0.26
            clearcoatAmount: 0.34
            clearcoatRoughnessAmount: 0.12

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.glowDrive
                    * 0.10,

                    root.displayTone.g
                    * root.glowDrive
                    * 0.10,

                    root.displayTone.b
                    * root.glowDrive
                    * 0.10
                )
        }

        PrincipledMaterial {
            id: outerOrbMaterial

            baseColor:
                Qt.rgba(
                    0.035
                    + root.displayTone.r * 0.16,

                    0.045
                    + root.displayTone.g * 0.16,

                    0.065
                    + root.displayTone.b * 0.16,

                    1.0
                )

            metalness: 0.18
            roughness: 0.16
            clearcoatAmount: 0.64
            clearcoatRoughnessAmount: 0.08

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.glowDrive
                    * 0.46,

                    root.displayTone.g
                    * root.glowDrive
                    * 0.46,

                    root.displayTone.b
                    * root.glowDrive
                    * 0.46
                )
        }

        PrincipledMaterial {
            id: chamberMaterial

            baseColor:
                Qt.rgba(
                    0.045
                    + root.displayTone.r * 0.20,

                    0.080
                    + root.displayTone.g * 0.25,

                    0.18
                    + root.displayTone.b * 0.30,

                    1.0
                )

            metalness: 0.08
            roughness: 0.13
            clearcoatAmount: 0.68
            clearcoatRoughnessAmount: 0.055

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.glowDrive
                    * 0.78,

                    root.displayTone.g
                    * root.glowDrive
                    * 0.78,

                    root.displayTone.b
                    * root.glowDrive
                    * 0.78
                )
        }

        PrincipledMaterial {
            id: nucleusMaterial

            baseColor: "#07101D"
            metalness: 0.10
            roughness: 0.18
            clearcoatAmount: 0.48
            clearcoatRoughnessAmount: 0.085

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.glowDrive
                    * 1.10,

                    root.displayTone.g
                    * root.glowDrive
                    * 1.10,

                    root.displayTone.b
                    * root.glowDrive
                    * 1.10
                )
        }

        PrincipledMaterial {
            id: lensMaterial

            baseColor:
                Qt.rgba(
                    0.10
                    + root.displayTone.r * 0.12,

                    0.13
                    + root.displayTone.g * 0.12,

                    0.20
                    + root.displayTone.b * 0.14,

                    0.28
                )

            metalness: 0.05
            roughness: 0.07
            clearcoatAmount: 0.90
            clearcoatRoughnessAmount: 0.035
            transmissionFactor: 0.62
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: facetMaterial

            baseColor:
                Qt.rgba(
                    0.16
                    + root.displayTone.r * 0.14,

                    0.18
                    + root.displayTone.g * 0.14,

                    0.23
                    + root.displayTone.b * 0.15,

                    1.0
                )

            metalness: 0.78
            roughness: 0.18
            clearcoatAmount: 0.50
            clearcoatRoughnessAmount: 0.08

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r
                    * root.glowDrive
                    * 0.16,

                    root.displayTone.g
                    * root.glowDrive
                    * 0.16,

                    root.displayTone.b
                    * root.glowDrive
                    * 0.16
                )
        }

        PrincipledMaterial {
            id: particleMaterial

            baseColor:
                root.displayTone

            metalness: 0.04
            roughness: 0.18

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * 1.45,
                    root.displayTone.g * 1.45,
                    root.displayTone.b * 1.45
                )
        }

        // --------------------------------------------------------------------
        // MASTER CORE — same R11Q silhouette, slightly stronger 3/4 angle
        // --------------------------------------------------------------------
        Node {
            id: orbRoot

            scale:
                Qt.vector3d(
                    root.coreBreath,
                    root.coreBreath,
                    root.coreBreath
                )

            eulerRotation:
                Qt.vector3d(
                    -6.5
                    + root.counterDrift
                    * 0.45
                    * root.motionGate,

                    -14.0
                    + root.drift
                    * 1.35
                    * root.motionGate,

                    root.planning
                    * root.drift
                    * 0.8
                    + root.failed
                    * Math.sin(root.phase * 3.8)
                    * 1.8
                )

            // ---------------------------------------------------------------
            // REAR SHADOW VOLUME — visible as a recessed off-axis crescent
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        -7.0,
                        4.0,
                        -27.0 + root.rearDepthOffset
                    )

                scale:
                    Qt.vector3d(
                        1.09,
                        1.04,
                        0.72
                    )

                materials:
                    [rearShellMaterial]
            }

            // ---------------------------------------------------------------
            // ORIGINAL LIVING ORB BODY
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        -3
                    )

                scale:
                    Qt.vector3d(
                        1.18,
                        1.18,
                        1.02
                    )

                materials:
                    [outerOrbMaterial]
            }

            // ---------------------------------------------------------------
            // RECESSED SAPPHIRE ENERGY CHAMBER
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        2.0,
                        -1.0,
                        15.0 + root.chamberDepthOffset
                    )

                scale:
                    Qt.vector3d(
                        0.69
                        + root.effectiveListenLevel * 0.035,

                        0.69
                        + root.effectiveListenLevel * 0.035,

                        0.54
                        + root.effectiveSpeechLevel * 0.025
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.phase * 12.0
                            : root.drift * 1.6,

                        root.planning
                            ? -root.phase * 18.0
                            : root.counterDrift * 2.0,

                        root.executing
                            ? root.phase * 5.0
                            : 0.0
                    )

                materials:
                    [chamberMaterial]
            }

            // ---------------------------------------------------------------
            // DARK COGNITION NUCLEUS — clearly separated forward layer
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        root.executing ? 5.0 : -2.0,

                        root.verifying
                            ? root.drift * 3.5
                            : 2.0,

                        35.0
                        + root.nucleusDepthOffset
                    )

                scale:
                    Qt.vector3d(
                        0.30
                        + root.effectiveListenLevel * 0.020
                        + root.effectiveSpeechLevel * 0.025,

                        0.30
                        + root.effectiveListenLevel * 0.020
                        + root.effectiveSpeechLevel * 0.025,

                        0.27
                    )

                materials:
                    [nucleusMaterial]
            }

            // ---------------------------------------------------------------
            // SHALLOW FRONT CONTAINMENT LENS — depth cue, not a new silhouette
            // ---------------------------------------------------------------
            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        48.0
                        + root.lensDepthOffset
                    )

                scale:
                    Qt.vector3d(
                        0.98,
                        0.98,
                        0.16
                    )

                materials:
                    [lensMaterial]
            }

            // ---------------------------------------------------------------
            // SIX INTERNAL FACETS
            // Kept inside the orb so the outside silhouette stays R11Q-clean.
            // ---------------------------------------------------------------
            Repeater3D {
                model: 6

                delegate: Model {
                    property real facetAngle:
                        (
                            index / 6.0
                        )
                        * Math.PI
                        * 2.0
                        + Math.PI / 6.0

                    property real facetRadius:
                        58.0
                        + (
                            root.listening
                            ? root.effectiveListenLevel * 3.0
                            : 0.0
                          )

                    source: "#Cube"

                    position:
                        Qt.vector3d(
                            Math.cos(facetAngle)
                            * facetRadius,

                            Math.sin(facetAngle)
                            * facetRadius
                            * 0.76,

                            (
                                index === 0 ? 28 :
                                index === 1 ? 10 :
                                index === 2 ? -18 :
                                index === 3 ? -34 :
                                index === 4 ? -10 :
                                20
                            )
                        )

                    eulerRotation:
                        Qt.vector3d(
                            index % 2 === 0
                                ? -9.0
                                : 7.0,

                            index % 3 === 0
                                ? 8.0
                                : -5.0,

                            facetAngle
                            * 180.0
                            / Math.PI
                            + 90.0
                        )

                    scale:
                        Qt.vector3d(
                            0.18,
                            0.035,
                            0.055
                        )

                    materials:
                        [facetMaterial]
                }
            }

            // ---------------------------------------------------------------
            // REAL 3D PARTICLE PARALLAX — increased from 10 to 18
            // ---------------------------------------------------------------
            Repeater3D {
                model: 18

                delegate: Model {
                    property int particleIndex:
                        index

                    property real angle:
                        (
                            particleIndex / 18.0
                        )
                        * Math.PI
                        * 2.0
                        + root.phase
                        * (
                            root.planning ? 1.80 :
                            root.executing ? 2.40 :
                            root.verifying ? 1.25 :
                            root.listening ? 0.62 :
                            root.speaking ? 0.74 :
                            0.28
                        )

                    property real orbitRadius:
                        82.0
                        + (
                            particleIndex % 3
                          )
                          * 13.0
                        + (
                            root.listening
                            ? root.effectiveListenLevel * 5.0
                            : 0.0
                          )

                    property real depthZ:
                        Math.sin(
                            angle * 1.55
                            + particleIndex * 0.72
                        )
                        * (
                            36.0
                            + (
                                particleIndex % 4
                              )
                              * 7.0
                          )

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(angle)
                            * orbitRadius,

                            Math.sin(angle)
                            * (
                                45.0
                                + (
                                    particleIndex % 3
                                  )
                                  * 7.0
                              ),

                            depthZ
                        )

                    scale:
                        Qt.vector3d(
                            0.018
                            + (
                                particleIndex % 3
                              )
                              * 0.006,

                            0.018
                            + (
                                particleIndex % 3
                              )
                              * 0.006,

                            0.018
                            + (
                                particleIndex % 3
                              )
                              * 0.006
                        )

                    materials:
                        [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // ORIGINAL R11Q GLASS LOOK — made slightly more transparent so the new
    // internal Z layers remain visible. Shape and highlight language stay.
    // ------------------------------------------------------------------------
    Canvas {
        id: glassCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = root.baseRadius * root.coreBreath
            var tone = root.displayTone

            ctx.clearRect(
                0,
                0,
                width,
                height
            )

            var core =
                ctx.createRadialGradient(
                    cx - r * 0.30,
                    cy - r * 0.34,
                    r * 0.05,
                    cx,
                    cy,
                    r * 1.18
                )

            // Same R11Q treatment, reduced just enough to reveal true depth.
            core.addColorStop(
                0.00,
                "rgba(255,255,255,0.38)"
            )

            core.addColorStop(
                0.18,
                root.rgbaString(
                    tone,
                    0.27 * root.glowDrive
                )
            )

            core.addColorStop(
                0.62,
                root.rgbaString(
                    tone,
                    0.075 * root.glowDrive
                )
            )

            core.addColorStop(
                1.00,
                "rgba(3,7,14,0.04)"
            )

            ctx.fillStyle = core
            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 0.94,
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.015
                )

            ctx.strokeStyle =
                root.rgbaString(
                    tone,
                    0.30
                    + root.glowDrive * 0.10
                )

            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 1.01,
                0,
                Math.PI * 2.0
            )
            ctx.stroke()

            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.028
                )

            ctx.strokeStyle =
                "rgba(255,255,255,0.25)"

            ctx.beginPath()
            ctx.arc(
                cx - r * 0.015,
                cy - r * 0.010,
                r * 0.81,
                Math.PI * 1.10,
                Math.PI * 1.55
            )
            ctx.stroke()

            var kernelRadius =
                r
                * (
                    0.20
                    + root.effectiveListenLevel * 0.055
                    + root.effectiveSpeechLevel * 0.050
                )

            var kernel =
                ctx.createRadialGradient(
                    cx - kernelRadius * 0.25,
                    cy - kernelRadius * 0.25,
                    1,
                    cx,
                    cy,
                    kernelRadius
                )

            kernel.addColorStop(
                0.0,
                "rgba(255,255,255,0.80)"
            )

            kernel.addColorStop(
                0.28,
                root.rgbaString(
                    tone,
                    0.72
                )
            )

            kernel.addColorStop(
                1.0,
                root.rgbaString(
                    tone,
                    0.03
                )
            )

            ctx.fillStyle = kernel
            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                kernelRadius,
                0,
                Math.PI * 2.0
            )
            ctx.fill()
        }
    }

    // ------------------------------------------------------------------------
    // REPAINT HOOKS
    // ------------------------------------------------------------------------
    onPhaseChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onWidthChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onHeightChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onDisplayToneChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onAudioLevelChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onSpeechLevelChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }
}
