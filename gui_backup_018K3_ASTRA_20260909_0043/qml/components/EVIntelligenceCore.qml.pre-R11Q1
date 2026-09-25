import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11Q LIVING ENERGY CORE
// ============================================================================
//
// QML-only experimental flagship core.
//
// This revision deliberately stops trying to make the visual identity out of
// authored mechanical GLBs. It translates the strongest ideas from the
// voice-reactive orb prototype into the existing E.V. QML/state architecture:
//
// - calm breathing idle
// - microphone-amplitude-reactive listening
// - faster particle constellation while planning
// - directional energy while executing
// - depth-focus pulse while verifying
// - warm speech pulse while speaking
// - restrained success / failed / recovering behaviour
//
// The public interface used by EVFlagshipStage is preserved.
// audioLevel / speechLevel are optional hooks for the future real voice layer.
// Until those hooks are connected, LISTENING and SPEAKING use tasteful
// synthetic fallback animation so --demo-states remains visually useful.
//
// No external GLB assets are required by this file.
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
    // 0.0 .. 1.0. Later the Python voice bridge can bind live microphone /
    // playback amplitude here without changing the renderer architecture.
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ------------------------------------------------------------------------
    // MOTION CLOCK
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
    // STATE LANGUAGE
    // ------------------------------------------------------------------------
    // These four colours intentionally preserve the strongest visual language
    // from the provided voice-reactive prototype while all other E.V. states
    // continue to use Theme.stateColor().
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
        ? Math.max(0.0, Math.min(1.0,
            root.audioLevel > 0.01 ? root.audioLevel : root.syntheticListenLevel))
        : 0.0

    readonly property real effectiveSpeechLevel:
        root.speaking
        ? Math.max(0.0, Math.min(1.0,
            root.speechLevel > 0.01 ? root.speechLevel : root.syntheticSpeechLevel))
        : 0.0

    readonly property real thinkingDrive:
        root.planning ? 1.0 :
        root.executing ? 0.84 :
        root.verifying ? 0.66 : 0.0

    readonly property real disturbance: root.failed ? 1.0 : 0.0
    readonly property real recoveryDrive: root.recovering ? 1.0 : 0.0
    readonly property real motionGate: root.awaiting ? 0.06 : 1.0

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

    readonly property real baseRadius: Math.max(
        54.0,
        Math.min(root.width, root.height) * 0.165
    )

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
    // BACKGROUND AURA / VOICE RIPPLES / PARTICLE CONSTELLATION
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

            // ------------------------------------------------------------
            // Deep aura — wide, soft, restrained.
            // ------------------------------------------------------------
            var aura = ctx.createRadialGradient(
                cx, cy, r * 0.18,
                cx, cy, r * (2.45 + root.glowDrive * 0.18)
            )
            aura.addColorStop(0.0, root.rgbaString(tone, 0.26 * root.glowDrive))
            aura.addColorStop(0.36, root.rgbaString(tone, 0.11 * root.glowDrive))
            aura.addColorStop(1.0, root.rgbaString(tone, 0.0))

            ctx.fillStyle = aura
            ctx.beginPath()
            ctx.arc(cx, cy, r * (2.55 + root.glowDrive * 0.18), 0, Math.PI * 2)
            ctx.fill()

            // ------------------------------------------------------------
            // LISTENING: live amplitude ripple field.
            // ------------------------------------------------------------
            if (root.listening) {
                ctx.lineWidth = Math.max(1.0, r * 0.010)

                for (var i = 0; i < 4; ++i) {
                    var travel = ((root.phase / (Math.PI * 2.0)) + i * 0.25) % 1.0
                    var rr = r * (1.12 + travel * (0.82 + root.effectiveListenLevel * 0.46))
                    var alpha = (1.0 - travel) * (0.14 + root.effectiveListenLevel * 0.28)

                    ctx.strokeStyle = root.rgbaString(tone, alpha)
                    ctx.beginPath()
                    ctx.arc(cx, cy, rr, 0, Math.PI * 2)
                    ctx.stroke()
                }
            }

            // ------------------------------------------------------------
            // SPEAKING: warm outward speech pulses.
            // ------------------------------------------------------------
            if (root.speaking) {
                for (var s = 0; s < 3; ++s) {
                    var speechTravel = ((root.phase / (Math.PI * 2.0)) + s / 3.0) % 1.0
                    var sr = r * (1.06 + speechTravel * (0.72 + root.effectiveSpeechLevel * 0.44))
                    var sa = (1.0 - speechTravel) * (0.12 + root.effectiveSpeechLevel * 0.32)

                    ctx.lineWidth = Math.max(1.0, r * (0.008 + root.effectiveSpeechLevel * 0.007))
                    ctx.strokeStyle = root.rgbaString(tone, sa)
                    ctx.beginPath()
                    ctx.arc(cx, cy, sr, 0, Math.PI * 2)
                    ctx.stroke()
                }
            }

            // ------------------------------------------------------------
            // PLANNING / EXECUTING / VERIFYING:
            // sparse orbital constellation with elliptical depth.
            // ------------------------------------------------------------
            var particleCount = 34
            var speed = root.planning ? 1.60 :
                        root.executing ? 2.35 :
                        root.verifying ? 1.20 :
                        0.34

            for (var p = 0; p < particleCount; ++p) {
                var a = root.particleAngle(p, particleCount, speed)
                var band = p % 3
                var orbit = r * (1.42 + band * 0.19)
                var ellipse = 0.48 + band * 0.075

                if (root.listening)
                    orbit += root.effectiveListenLevel * r * 0.14

                var px = cx + Math.cos(a) * orbit
                var py = cy + Math.sin(a) * orbit * ellipse

                // Fake parallax: rear particles dim, front particles brighten.
                var depth = (Math.sin(a) + 1.0) * 0.5
                var pa = 0.10 + depth * 0.38

                if (root.planning || root.executing || root.verifying)
                    pa *= 1.25
                else
                    pa *= 0.52

                var size = Math.max(0.8, r * (0.006 + depth * 0.008))
                ctx.fillStyle = root.rgbaString(tone, pa)
                ctx.beginPath()
                ctx.arc(px, py, size, 0, Math.PI * 2)
                ctx.fill()
            }

            // ------------------------------------------------------------
            // VERIFYING: depth-focus halo, not a straight scan line.
            // ------------------------------------------------------------
            if (root.verifying) {
                var vr = r * (1.18 + 0.12 * Math.sin(root.phase * 1.6))
                ctx.lineWidth = Math.max(1.0, r * 0.012)
                ctx.strokeStyle = root.rgbaString(tone, 0.32)
                ctx.beginPath()
                ctx.arc(cx, cy, vr, 0, Math.PI * 2)
                ctx.stroke()
            }

            // ------------------------------------------------------------
            // FAILED: restrained desynchronised arcs.
            // ------------------------------------------------------------
            if (root.failed) {
                ctx.lineWidth = Math.max(1.0, r * 0.014)
                ctx.strokeStyle = root.rgbaString(tone, 0.26)

                for (var f = 0; f < 3; ++f) {
                    var offset = f * Math.PI * 0.73 + root.phase * (0.4 + f * 0.08)
                    ctx.beginPath()
                    ctx.arc(
                        cx + Math.sin(root.phase * 2.7 + f) * r * 0.035,
                        cy + Math.cos(root.phase * 2.2 + f) * r * 0.025,
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
    // REAL 3D FOCAL ORB
    // ------------------------------------------------------------------------
    View3D {
        id: core3D
        anchors.centerIn: parent
        width: Math.min(root.width, root.height) * 0.50
        height: width

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 330)
            fieldOfView: 39
            clipNear: 1
            clipFar: 1200
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-32, 38, -8)
            color: "#F4F8FF"
            brightness: 2.2
            ambientColor: "#111923"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(28, -46, 12)
            color: "#7387A3"
            brightness: 0.72
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position: Qt.vector3d(-62, 58, 118)
            color: root.displayTone
            brightness: 1.35 + root.glowDrive * 1.15
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        PrincipledMaterial {
            id: outerOrbMaterial
            baseColor: Qt.rgba(
                0.035 + root.displayTone.r * 0.16,
                0.045 + root.displayTone.g * 0.16,
                0.065 + root.displayTone.b * 0.16,
                1.0
            )
            metalness: 0.18
            roughness: 0.16
            clearcoatAmount: 0.64
            clearcoatRoughnessAmount: 0.08
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.48,
                root.displayTone.g * root.glowDrive * 0.48,
                root.displayTone.b * root.glowDrive * 0.48
            )
        }

        PrincipledMaterial {
            id: nucleusMaterial
            baseColor: "#08111D"
            metalness: 0.08
            roughness: 0.20
            clearcoatAmount: 0.42
            clearcoatRoughnessAmount: 0.10
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 1.10,
                root.displayTone.g * root.glowDrive * 1.10,
                root.displayTone.b * root.glowDrive * 1.10
            )
        }

        PrincipledMaterial {
            id: particleMaterial
            baseColor: root.displayTone
            metalness: 0.04
            roughness: 0.18
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * 1.45,
                root.displayTone.g * 1.45,
                root.displayTone.b * 1.45
            )
        }

        Node {
            id: orbRoot

            scale: Qt.vector3d(
                root.coreBreath,
                root.coreBreath,
                root.coreBreath
            )

            eulerRotation: Qt.vector3d(
                -5.5 + root.counterDrift * 0.35 * root.motionGate,
                -12.0 + root.drift * 1.25 * root.motionGate,
                root.planning * root.drift * 0.8
                    + root.failed * Math.sin(root.phase * 3.8) * 1.8
            )

            Model {
                source: "#Sphere"
                scale: Qt.vector3d(1.18, 1.18, 1.18)
                materials: [outerOrbMaterial]
            }

            // Bright cognition nucleus slightly forward in Z to create depth.
            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    root.executing ? 5.0 : 0.0,
                    root.verifying ? root.drift * 4.0 : 0.0,
                    22
                )
                scale: Qt.vector3d(
                    0.54 + root.effectiveListenLevel * 0.04,
                    0.54 + root.effectiveListenLevel * 0.04,
                    0.54 + root.effectiveListenLevel * 0.04
                )
                materials: [nucleusMaterial]
            }

            // Sparse true-3D cognition points. They provide actual parallax
            // while the larger constellation remains cheap 2D Canvas.
            Repeater3D {
                model: 10

                delegate: Model {
                    property int particleIndex: index
                    property real angle:
                        (particleIndex / 10.0) * Math.PI * 2.0
                        + root.phase * (
                            root.planning ? 1.8 :
                            root.executing ? 2.4 :
                            root.verifying ? 1.25 :
                            0.28
                        )

                    source: "#Sphere"

                    position: Qt.vector3d(
                        Math.cos(angle) * (84 + (particleIndex % 2) * 14),
                        Math.sin(angle) * (47 + (particleIndex % 3) * 7),
                        Math.sin(angle * 1.7 + particleIndex) * 34
                    )

                    scale: Qt.vector3d(
                        0.022 + (particleIndex % 3) * 0.007,
                        0.022 + (particleIndex % 3) * 0.007,
                        0.022 + (particleIndex % 3) * 0.007
                    )

                    materials: [particleMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // FOREGROUND GLASS HIGHLIGHT
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

            ctx.clearRect(0, 0, width, height)

            // Main orb body. This overlays the 3D sphere with a controlled
            // luxury-glass gradient rather than relying only on bloom.
            var core = ctx.createRadialGradient(
                cx - r * 0.30,
                cy - r * 0.34,
                r * 0.05,
                cx,
                cy,
                r * 1.18
            )

            core.addColorStop(0.00, "rgba(255,255,255,0.56)")
            core.addColorStop(0.18, root.rgbaString(tone, 0.38 * root.glowDrive))
            core.addColorStop(0.62, root.rgbaString(tone, 0.12 * root.glowDrive))
            core.addColorStop(1.00, "rgba(3,7,14,0.10)")

            ctx.fillStyle = core
            ctx.beginPath()
            ctx.arc(cx, cy, r * 0.94, 0, Math.PI * 2)
            ctx.fill()

            // Thin precision rim.
            ctx.lineWidth = Math.max(1.0, r * 0.015)
            ctx.strokeStyle = root.rgbaString(tone, 0.34 + root.glowDrive * 0.12)
            ctx.beginPath()
            ctx.arc(cx, cy, r * 1.01, 0, Math.PI * 2)
            ctx.stroke()

            // Controlled specular crescent.
            ctx.lineWidth = Math.max(1.0, r * 0.028)
            ctx.strokeStyle = "rgba(255,255,255,0.30)"
            ctx.beginPath()
            ctx.arc(
                cx - r * 0.015,
                cy - r * 0.010,
                r * 0.81,
                Math.PI * 1.10,
                Math.PI * 1.55
            )
            ctx.stroke()

            // Tiny inner energy kernel.
            var kernelRadius = r * (
                0.20
                + root.effectiveListenLevel * 0.055
                + root.effectiveSpeechLevel * 0.050
            )
            var kernel = ctx.createRadialGradient(
                cx - kernelRadius * 0.25,
                cy - kernelRadius * 0.25,
                1,
                cx,
                cy,
                kernelRadius
            )
            kernel.addColorStop(0.0, "rgba(255,255,255,0.96)")
            kernel.addColorStop(0.28, root.rgbaString(tone, 0.94))
            kernel.addColorStop(1.0, root.rgbaString(tone, 0.06))

            ctx.fillStyle = kernel
            ctx.beginPath()
            ctx.arc(cx, cy, kernelRadius, 0, Math.PI * 2)
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

    onAudioLevelChanged: auraCanvas.requestPaint()
    onSpeechLevelChanged: auraCanvas.requestPaint()
}
