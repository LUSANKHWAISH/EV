import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R11Q-D2.3 ORBITAL PRESENCE POLISH
// ============================================================================
//
// SAFE BASE:
//   R11Q-D — the strongest current visual direction.
//
// THIS IS A SURGICAL REFINEMENT, NOT A REDESIGN.
//
// CHANGES ONLY:
// - larger visual presence
// - closer camera
// - stronger rear / centre / front Z separation
// - deeper particle parallax
// - thinner / less flattening front glass treatment
// - reduced 2D ripple density
// - no slabs, cage, giant beams, outer mechanical shell
// - adds 6 satellite nodes + restrained orbital tracer paths
//
// QML only. No GLB / Blender / RuntimeLoader.
// ============================================================================

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

    property real audioLevel: 0.0
    property real speechLevel: 0.0

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

    readonly property real pulse:
        (Math.sin(root.phase) + 1.0) * 0.5

    readonly property real slowPulse:
        (Math.sin(root.phase * 0.52) + 1.0) * 0.5

    readonly property real drift:
        Math.sin(root.phase * 0.41)

    readonly property real counterDrift:
        Math.cos(root.phase * 0.37)

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    readonly property color displayTone:
        root.idle ? "#34E6E0" :
        root.listening ? "#8E6BFF" :
        root.planning ? "#FF9D3D" :
        root.speaking ? "#FFCF6B" :
        root.stateTone

    readonly property real syntheticListenLevel:
        root.listening
        ? 0.18 + root.pulse * 0.28
        : 0.0

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

    readonly property real motionGate:
        root.awaiting ? 0.06 : 1.0

    readonly property real coreBreath:
        root.idle ? 0.985 + root.slowPulse * 0.035 :
        root.listening ? 0.98 + root.effectiveListenLevel * 0.10 :
        root.speaking ? 0.99 + root.effectiveSpeechLevel * 0.08 :
        root.successful ? 1.055 :
        root.failed ? 0.96 + root.pulse * 0.025 :
        root.stopped ? 0.86 :
        1.0 + root.pulse * 0.022

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


    // ------------------------------------------------------------------------
    // R11Q-D2.2 — ORBITAL TRACERS + SATELLITE NODES
    // ------------------------------------------------------------------------
    readonly property real satelliteSpeed:
        root.stopped ? 0.0 :
        root.awaiting ? 0.12 :
        root.executing ? 1.55 :
        root.planning ? 1.18 :
        root.verifying ? 0.92 :
        root.listening ? 0.68 + root.effectiveListenLevel * 0.22 :
        root.speaking ? 0.78 + root.effectiveSpeechLevel * 0.20 :
        root.failed ? 1.10 :
        root.recovering ? 0.48 :
        root.successful ? 0.42 :
        0.34

    readonly property real tracerOpacity:
        root.stopped ? 0.02 :
        root.awaiting ? 0.07 :
        root.executing ? 0.20 :
        root.planning ? 0.17 :
        root.verifying ? 0.16 :
        root.listening ? 0.14 + root.effectiveListenLevel * 0.05 :
        root.speaking ? 0.15 + root.effectiveSpeechLevel * 0.05 :
        root.failed ? 0.13 :
        0.10

    readonly property real auraRadius:
        Math.max(
            62.0,
            Math.min(root.width, root.height) * 0.185
        )

    readonly property real rearDepth:
        root.failed ? -66.0 + root.counterDrift * 5.0 :
        root.recovering ? -68.0 + root.pulse * 3.0 :
        -68.0

    readonly property real rearEnergyDepth:
        root.verifying ? -30.0 + root.drift * 5.0 :
        -34.0

    readonly property real chamberDepth:
        root.executing ? 22.0 :
        root.verifying ? 16.0 + root.drift * 7.0 :
        root.planning ? 17.0 + root.drift * 2.0 :
        16.0

    readonly property real nucleusDepth:
        root.executing ? 46.0 :
        root.verifying ? 40.0 + root.drift * 8.0 :
        root.speaking ? 40.0 + root.effectiveSpeechLevel * 5.0 :
        40.0

    readonly property real lensDepth:
        root.listening ? 66.0 + root.effectiveListenLevel * 7.0 :
        root.speaking ? 66.0 + root.effectiveSpeechLevel * 5.0 :
        root.successful ? 71.0 :
        66.0

    function rgbaString(c, alphaValue) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, alphaValue))
            + ")"
    }

    Canvas {
        id: auraCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = root.auraRadius * root.coreBreath
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            var aura = ctx.createRadialGradient(
                cx,
                cy,
                r * 0.18,
                cx,
                cy,
                r * (2.30 + root.glowDrive * 0.14)
            )

            aura.addColorStop(
                0.0,
                root.rgbaString(
                    tone,
                    0.22 * root.glowDrive
                )
            )

            aura.addColorStop(
                0.38,
                root.rgbaString(
                    tone,
                    0.075 * root.glowDrive
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
                r * (2.34 + root.glowDrive * 0.14),
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            if (root.listening) {
                ctx.lineWidth = Math.max(1.0, r * 0.008)

                for (var i = 0; i < 2; ++i) {
                    var travel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + i * 0.5
                        ) % 1.0

                    var rr =
                        r
                        * (
                            1.04
                            + travel
                            * (
                                0.72
                                + root.effectiveListenLevel
                                * 0.34
                            )
                        )

                    var alpha =
                        (1.0 - travel)
                        * (
                            0.07
                            + root.effectiveListenLevel
                            * 0.14
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
                for (var s = 0; s < 2; ++s) {
                    var speechTravel =
                        (
                            root.phase / (Math.PI * 2.0)
                            + s * 0.5
                        ) % 1.0

                    var sr =
                        r
                        * (
                            1.02
                            + speechTravel
                            * (
                                0.66
                                + root.effectiveSpeechLevel
                                * 0.34
                            )
                        )

                    var sa =
                        (1.0 - speechTravel)
                        * (
                            0.06
                            + root.effectiveSpeechLevel
                            * 0.15
                        )

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            r
                            * (
                                0.007
                                + root.effectiveSpeechLevel
                                * 0.004
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

            if (root.verifying) {
                var vr =
                    r
                    * (
                        1.06
                        + 0.05
                        * Math.sin(root.phase * 1.6)
                    )

                ctx.lineWidth =
                    Math.max(
                        1.0,
                        r * 0.008
                    )

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
                    Math.PI * 1.14,
                    Math.PI * 1.78
                )
                ctx.stroke()
            }
        }
    }


    // ------------------------------------------------------------------------
    // REAR ORBITAL TRACERS
    // Faint complete paths are drawn behind the real 3D core.
    // ------------------------------------------------------------------------
    Canvas {
        id: rearOrbitCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = root.auraRadius
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            function ellipsePath(rx, ry, rotation, alphaValue) {
                var steps = 96
                var cr = Math.cos(rotation)
                var sr = Math.sin(rotation)

                ctx.beginPath()

                for (var i = 0; i <= steps; ++i) {
                    var t = (i / steps) * Math.PI * 2.0
                    var ex = Math.cos(t) * rx
                    var ey = Math.sin(t) * ry
                    var x = cx + ex * cr - ey * sr
                    var y = cy + ex * sr + ey * cr

                    if (i === 0)
                        ctx.moveTo(x, y)
                    else
                        ctx.lineTo(x, y)
                }

                ctx.lineWidth = Math.max(0.9, r * 0.0058)
                ctx.strokeStyle = root.rgbaString(tone, alphaValue)
                ctx.stroke()
            }

            ellipsePath(
                r * 1.34,
                r * 0.48,
                -0.34,
                root.tracerOpacity * 0.72
            )

            ellipsePath(
                r * 1.18,
                r * 0.62,
                0.18,
                root.tracerOpacity * 0.54
            )

            ellipsePath(
                r * 1.44,
                r * 0.38,
                0.58,
                root.tracerOpacity * 0.45
            )
        }
    }

    View3D {
        id: core3D
        anchors.centerIn: parent

        width:
            Math.min(
                root.width,
                root.height
            ) * 0.64

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
            position:
                Qt.vector3d(
                    0,
                    0,
                    305
                )

            fieldOfView: 38
            clipNear: 1
            clipFar: 1200
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    -32,
                    38,
                    -8
                )

            color: "#F4F8FF"
            brightness: 2.10
            ambientColor: "#111923"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation:
                Qt.vector3d(
                    28,
                    -46,
                    12
                )

            color: "#7387A3"
            brightness: 0.68
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position:
                Qt.vector3d(
                    -62,
                    58,
                    118
                )

            color:
                root.displayTone

            brightness:
                1.20
                + root.glowDrive * 1.00

            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        PointLight {
            position:
                Qt.vector3d(
                    46,
                    -28,
                    -96
                )

            color:
                root.displayTone

            brightness:
                0.14
                + root.glowDrive * 0.18

            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.000035
        }

        PrincipledMaterial {
            id: rearShellMaterial

            baseColor:
                Qt.rgba(
                    0.014 + root.displayTone.r * 0.040,
                    0.020 + root.displayTone.g * 0.040,
                    0.032 + root.displayTone.b * 0.040,
                    1.0
                )

            metalness: 0.46
            roughness: 0.28
            clearcoatAmount: 0.32
            clearcoatRoughnessAmount: 0.12

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.075,
                    root.displayTone.g * root.glowDrive * 0.075,
                    root.displayTone.b * root.glowDrive * 0.075
                )
        }

        PrincipledMaterial {
            id: rearEnergyMaterial

            baseColor:
                Qt.rgba(
                    0.028 + root.displayTone.r * 0.12,
                    0.055 + root.displayTone.g * 0.16,
                    0.13 + root.displayTone.b * 0.22,
                    0.88
                )

            metalness: 0.08
            roughness: 0.19
            clearcoatAmount: 0.52
            clearcoatRoughnessAmount: 0.075

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.30,
                    root.displayTone.g * root.glowDrive * 0.30,
                    root.displayTone.b * root.glowDrive * 0.30
                )
        }

        PrincipledMaterial {
            id: outerOrbMaterial

            baseColor:
                Qt.rgba(
                    0.028 + root.displayTone.r * 0.12,
                    0.040 + root.displayTone.g * 0.13,
                    0.060 + root.displayTone.b * 0.14,
                    1.0
                )

            metalness: 0.16
            roughness: 0.17
            clearcoatAmount: 0.66
            clearcoatRoughnessAmount: 0.07

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.36,
                    root.displayTone.g * root.glowDrive * 0.36,
                    root.displayTone.b * root.glowDrive * 0.36
                )
        }

        PrincipledMaterial {
            id: chamberMaterial

            baseColor:
                Qt.rgba(
                    0.040 + root.displayTone.r * 0.19,
                    0.074 + root.displayTone.g * 0.24,
                    0.17 + root.displayTone.b * 0.29,
                    1.0
                )

            metalness: 0.06
            roughness: 0.12
            clearcoatAmount: 0.70
            clearcoatRoughnessAmount: 0.050

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 0.76,
                    root.displayTone.g * root.glowDrive * 0.76,
                    root.displayTone.b * root.glowDrive * 0.76
                )
        }

        PrincipledMaterial {
            id: nucleusMaterial

            baseColor: "#06101C"
            metalness: 0.10
            roughness: 0.16
            clearcoatAmount: 0.54
            clearcoatRoughnessAmount: 0.07

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * root.glowDrive * 1.06,
                    root.displayTone.g * root.glowDrive * 1.06,
                    root.displayTone.b * root.glowDrive * 1.06
                )
        }

        PrincipledMaterial {
            id: lensMaterial

            baseColor:
                Qt.rgba(
                    0.10 + root.displayTone.r * 0.08,
                    0.13 + root.displayTone.g * 0.08,
                    0.20 + root.displayTone.b * 0.10,
                    0.17
                )

            metalness: 0.03
            roughness: 0.055
            clearcoatAmount: 0.92
            clearcoatRoughnessAmount: 0.025
            transmissionFactor: 0.48
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: particleMaterial

            baseColor:
                root.displayTone

            metalness: 0.04
            roughness: 0.18

            emissiveFactor:
                Qt.vector3d(
                    root.displayTone.r * 1.13,
                    root.displayTone.g * 1.13,
                    root.displayTone.b * 1.13
                )
        }


        PrincipledMaterial {
            id: satelliteMaterial

            baseColor: "#ECFCFF"
            metalness: 0.02
            roughness: 0.12
            clearcoatAmount: 0.52
            clearcoatRoughnessAmount: 0.035

            emissiveFactor:
                Qt.vector3d(
                    0.36 + root.displayTone.r * 1.46,
                    0.36 + root.displayTone.g * 1.46,
                    0.36 + root.displayTone.b * 1.46
                )
        }

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
                    -7.5
                    + root.counterDrift
                    * 0.35
                    * root.motionGate,

                    -15.0
                    + root.drift
                    * 1.05
                    * root.motionGate,

                    root.failed
                    ? Math.sin(root.phase * 3.8) * 1.5
                    : root.planning
                      ? root.drift * 0.55
                      : 0.6
                )

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        -10.0,
                        5.0,
                        root.rearDepth
                    )

                scale:
                    Qt.vector3d(
                        1.11,
                        1.05,
                        0.62
                    )

                materials:
                    [rearShellMaterial]
            }

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        -4.0,
                        2.0,
                        root.rearEnergyDepth
                    )

                scale:
                    Qt.vector3d(
                        0.91,
                        0.89,
                        0.54
                    )

                materials:
                    [rearEnergyMaterial]
            }

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        -4.0
                    )

                scale:
                    Qt.vector3d(
                        1.15,
                        1.15,
                        0.94
                    )

                materials:
                    [outerOrbMaterial]
            }

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        2.0,
                        -1.0,
                        root.chamberDepth
                    )

                scale:
                    Qt.vector3d(
                        0.67
                        + root.effectiveListenLevel
                        * 0.030,

                        0.67
                        + root.effectiveListenLevel
                        * 0.030,

                        0.50
                        + root.effectiveSpeechLevel
                        * 0.022
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                        ? root.phase * 8.0
                        : root.drift * 1.2,

                        root.planning
                        ? -root.phase * 12.0
                        : root.counterDrift * 1.6,

                        root.executing
                        ? root.phase * 3.0
                        : 0.0
                    )

                materials:
                    [chamberMaterial]
            }

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        root.executing
                        ? 4.0
                        : -2.0,

                        root.verifying
                        ? root.drift * 3.0
                        : 2.0,

                        root.nucleusDepth
                    )

                scale:
                    Qt.vector3d(
                        0.29
                        + root.effectiveListenLevel
                        * 0.016
                        + root.effectiveSpeechLevel
                        * 0.020,

                        0.29
                        + root.effectiveListenLevel
                        * 0.016
                        + root.effectiveSpeechLevel
                        * 0.020,

                        0.25
                    )

                materials:
                    [nucleusMaterial]
            }

            Model {
                source: "#Sphere"

                position:
                    Qt.vector3d(
                        0,
                        0,
                        root.lensDepth
                    )

                scale:
                    Qt.vector3d(
                        0.93,
                        0.93,
                        0.105
                    )

                materials:
                    [lensMaterial]
            }

            Repeater3D {
                model: 24

                delegate: Model {
                    property int particleIndex:
                        index

                    property real angle:
                        (
                            particleIndex
                            / 24.0
                        )
                        * Math.PI
                        * 2.0
                        + root.phase
                        * (
                            root.planning ? 1.70 :
                            root.executing ? 2.30 :
                            root.verifying ? 1.18 :
                            root.listening ? 0.62 :
                            root.speaking ? 0.72 :
                            0.27
                        )

                    property real orbitRadius:
                        78.0
                        + (
                            particleIndex % 4
                          ) * 11.0
                        - (
                            root.listening
                            ? root.effectiveListenLevel * 8.0
                            : 0.0
                          )

                    property real depthZ:
                        Math.sin(
                            angle * 1.37
                            + particleIndex * 0.63
                        )
                        * (
                            52.0
                            + (
                                particleIndex % 4
                              ) * 7.0
                          )

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(angle)
                            * orbitRadius,

                            Math.sin(angle)
                            * orbitRadius
                            * (
                                0.50
                                + (
                                    particleIndex % 3
                                  ) * 0.045
                              ),

                            depthZ
                        )

                    scale:
                        Qt.vector3d(
                            0.016
                            + (
                                particleIndex % 3
                              ) * 0.005,

                            0.016
                            + (
                                particleIndex % 3
                              ) * 0.005,

                            0.016
                            + (
                                particleIndex % 3
                              ) * 0.005
                        )

                    materials:
                        [particleMaterial]
                }
            }
        }

        // --------------------------------------------------------------------
        // SATELLITE NODES
        // Six larger true-3D spheres orbit on three differently tilted planes.
        // Some move in front of the core and some behind it.
        // --------------------------------------------------------------------
        Node {
            id: satelliteSystem

            Repeater3D {
                model: 6

                delegate: Model {
                    property int satelliteIndex: index

                    property real direction:
                        satelliteIndex % 2 === 0
                        ? 1.0
                        : -0.82

                    property real angle:
                        root.phase
                        * root.satelliteSpeed
                        * direction
                        + satelliteIndex * 1.37

                    property int orbitPlane:
                        satelliteIndex % 3

                    property real radiusX:
                        112.0
                        + (
                            satelliteIndex % 3
                          ) * 18.0

                    property real radiusY:
                        42.0
                        + (
                            satelliteIndex % 2
                          ) * 17.0

                    property real xPos:
                        Math.cos(angle)
                        * radiusX

                    property real yPos:
                        orbitPlane === 0
                        ? Math.sin(angle) * radiusY
                        : orbitPlane === 1
                          ? Math.sin(angle) * radiusY
                            + Math.cos(angle) * 13.0
                          : Math.sin(angle)
                            * (
                                radiusY * 0.82
                              )
                            - Math.cos(angle) * 16.0

                    property real zPos:
                        orbitPlane === 0
                        ? Math.sin(angle) * 72.0
                        : orbitPlane === 1
                          ? -Math.sin(angle) * 58.0
                            + Math.cos(angle) * 24.0
                          : Math.sin(angle) * 82.0
                            + Math.cos(angle) * 14.0

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            xPos,
                            yPos,
                            zPos
                        )

                    scale:
                        Qt.vector3d(
                            0.039
                            + (
                                satelliteIndex % 3
                              ) * 0.007
                            + root.effectiveListenLevel * 0.004,

                            0.039
                            + (
                                satelliteIndex % 3
                              ) * 0.007
                            + root.effectiveListenLevel * 0.004,

                            0.039
                            + (
                                satelliteIndex % 3
                              ) * 0.007
                            + root.effectiveListenLevel * 0.004
                        )

                    materials:
                        [satelliteMaterial]
                }
            }
        }

    }

    Canvas {
        id: glassCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r =
                root.auraRadius
                * root.coreBreath
                * 0.83
            var tone = root.displayTone

            ctx.clearRect(
                0,
                0,
                width,
                height
            )

            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.010
                )

            ctx.strokeStyle =
                root.rgbaString(
                    tone,
                    0.15
                    + root.glowDrive * 0.05
                )

            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r,
                Math.PI * 0.06,
                Math.PI * 1.86
            )
            ctx.stroke()

            ctx.lineWidth =
                Math.max(
                    1.0,
                    r * 0.018
                )

            ctx.strokeStyle =
                "rgba(255,255,255,0.17)"

            ctx.beginPath()
            ctx.arc(
                cx - r * 0.020,
                cy - r * 0.018,
                r * 0.76,
                Math.PI * 1.11,
                Math.PI * 1.48
            )
            ctx.stroke()

            var kernelRadius =
                r
                * (
                    0.13
                    + root.effectiveListenLevel
                    * 0.030
                    + root.effectiveSpeechLevel
                    * 0.028
                )

            var kernel =
                ctx.createRadialGradient(
                    cx - kernelRadius * 0.18,
                    cy - kernelRadius * 0.18,
                    1,
                    cx,
                    cy,
                    kernelRadius
                )

            kernel.addColorStop(
                0.0,
                "rgba(255,255,255,0.46)"
            )

            kernel.addColorStop(
                0.42,
                root.rgbaString(
                    tone,
                    0.28
                )
            )

            kernel.addColorStop(
                1.0,
                root.rgbaString(
                    tone,
                    0.0
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
    // FRONT ORBITAL TRACERS
    // Short luminous tracer arcs move over the foreground. Combined with the
    // faint rear paths, this creates a front/back orbital crossing effect.
    // ------------------------------------------------------------------------
    Canvas {
        id: frontOrbitCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = root.auraRadius
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            function movingArc(
                rx,
                ry,
                rotation,
                startAngle,
                arcLength,
                alphaValue
            ) {
                var steps = 30
                var cr = Math.cos(rotation)
                var sr = Math.sin(rotation)

                ctx.beginPath()

                for (var i = 0; i <= steps; ++i) {
                    var t =
                        startAngle
                        + (
                            i / steps
                          ) * arcLength

                    var ex = Math.cos(t) * rx
                    var ey = Math.sin(t) * ry
                    var x = cx + ex * cr - ey * sr
                    var y = cy + ex * sr + ey * cr

                    if (i === 0)
                        ctx.moveTo(x, y)
                    else
                        ctx.lineTo(x, y)
                }

                ctx.lineWidth =
                    Math.max(
                        1.1,
                        r * 0.008
                    )

                ctx.strokeStyle =
                    root.rgbaString(
                        tone,
                        alphaValue
                    )

                ctx.stroke()
            }

            var p =
                root.phase
                * root.satelliteSpeed

            movingArc(
                r * 1.34,
                r * 0.48,
                -0.34,
                p + 0.10,
                0.72,
                root.tracerOpacity * 1.20
            )

            movingArc(
                r * 1.18,
                r * 0.62,
                0.18,
                -p * 0.82 + 2.10,
                0.58,
                root.tracerOpacity * 0.94
            )

            movingArc(
                r * 1.44,
                r * 0.38,
                0.58,
                p * 0.66 + 4.10,
                0.48,
                root.tracerOpacity * 0.75
            )
        }
    }

    onPhaseChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onWidthChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onHeightChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onDisplayToneChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onAudioLevelChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onSpeechLevelChanged: {
        auraCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        glassCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }
}
