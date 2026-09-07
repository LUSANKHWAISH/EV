import QtQuick 2.15
import QtQuick3D
import "../../theme"

// ============================================================================
// E.V. CORE FLAGSHIP VISUAL PRESET (EV_CORE)
// ============================================================================
//
// Extracted byte-for-byte visual logic from R11Q-D2.3 EVIntelligenceCore.
// Procedural QtQuick3D View3D + Canvas orbital/aura layers.
// Pure presentation component — zero execution authority.
// ============================================================================

Item {
    id: root
    anchors.fill: parent

    // Host connection for synchronized state and animation clock
    property var host: parent

    // Visual inputs (falling back to host properties or safe defaults)
    property string stateText: host && host.stateText !== undefined ? host.stateText : "IDLE"
    property string visualMode: host && host.visualMode !== undefined ? host.visualMode : "STANDARD"
    property real energy: host && host.energy !== undefined ? host.energy : Theme.stateEnergy(stateText)
    property color stateTone: host && host.stateTone !== undefined ? host.stateTone : Theme.stateColor(stateText)
    property color displayTone: host && host.displayTone !== undefined ? host.displayTone : stateTone

    property real phase: host && host.phase !== undefined ? host.phase : 0.0
    property real pulse: host && host.pulse !== undefined ? host.pulse : ((Math.sin(phase) + 1.0) * 0.5)
    property real slowPulse: host && host.slowPulse !== undefined ? host.slowPulse : ((Math.sin(phase * 0.52) + 1.0) * 0.5)
    property real drift: host && host.drift !== undefined ? host.drift : Math.sin(phase * 0.41)
    property real counterDrift: host && host.counterDrift !== undefined ? host.counterDrift : Math.cos(phase * 0.37)

    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0

    property real motionGate: host && host.motionGate !== undefined ? host.motionGate : (awaiting ? 0.06 : 1.0)
    property real coreBreath: host && host.coreBreath !== undefined ? host.coreBreath : 1.0
    property real glowDrive: host && host.glowDrive !== undefined ? host.glowDrive : 0.58
    property real satelliteSpeed: host && host.satelliteSpeed !== undefined ? host.satelliteSpeed : 0.34
    property real tracerOpacity: host && host.tracerOpacity !== undefined ? host.tracerOpacity : 0.10

    property real auraRadius: host && host.auraRadius !== undefined ? host.auraRadius : Math.max(62.0, Math.min(width, height) * 0.185)
    property real rearDepth: host && host.rearDepth !== undefined ? host.rearDepth : -68.0
    property real rearEnergyDepth: host && host.rearEnergyDepth !== undefined ? host.rearEnergyDepth : -34.0
    property real chamberDepth: host && host.chamberDepth !== undefined ? host.chamberDepth : 16.0
    property real nucleusDepth: host && host.nucleusDepth !== undefined ? host.nucleusDepth : 40.0
    property real lensDepth: host && host.lensDepth !== undefined ? host.lensDepth : 66.0

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

    function rgbaString(c, alphaValue) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, alphaValue))
            + ")"
    }

    // ------------------------------------------------------------------------
    // 1. AURA CANVAS LAYER
    // ------------------------------------------------------------------------
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
    // 2. REAR ORBITAL TRACERS
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

                ctx.lineWidth = Math.max(1.0, r * 0.006)
                ctx.strokeStyle = root.rgbaString(tone, alphaValue)
                ctx.stroke()
            }

            ellipsePath(
                r * 1.34,
                r * 0.48,
                -0.34,
                root.tracerOpacity * 0.65
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

    // ------------------------------------------------------------------------
    // 3. 3D CORE (View3D)
    // ------------------------------------------------------------------------
    View3D {
        id: core3D
        anchors.centerIn: parent
        camera: camera

        width:
            Math.min(
                root.width,
                root.height
            ) * 0.64

        height: width

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 305)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1200
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(-32, 38, -8)
            color: "#F4F8FF"
            brightness: 2.10
            ambientColor: "#111923"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(28, -46, 12)
            color: "#7387A3"
            brightness: 0.68
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            position: Qt.vector3d(-62, 58, 118)
            color: root.displayTone
            brightness: 1.20 + root.glowDrive * 1.00
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        PointLight {
            position: Qt.vector3d(46, -28, -96)
            color: root.displayTone
            brightness: 0.14 + root.glowDrive * 0.18
            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.000035
        }

        PrincipledMaterial {
            id: rearShellMaterial
            baseColor: Qt.rgba(
                0.014 + root.displayTone.r * 0.040,
                0.020 + root.displayTone.g * 0.040,
                0.032 + root.displayTone.b * 0.040,
                1.0
            )
            metalness: 0.46
            roughness: 0.28
            clearcoatAmount: 0.32
            clearcoatRoughnessAmount: 0.12
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.075,
                root.displayTone.g * root.glowDrive * 0.075,
                root.displayTone.b * root.glowDrive * 0.075
            )
        }

        PrincipledMaterial {
            id: rearEnergyMaterial
            baseColor: Qt.rgba(
                0.028 + root.displayTone.r * 0.12,
                0.055 + root.displayTone.g * 0.16,
                0.13 + root.displayTone.b * 0.22,
                0.88
            )
            metalness: 0.08
            roughness: 0.19
            clearcoatAmount: 0.52
            clearcoatRoughnessAmount: 0.075
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.30,
                root.displayTone.g * root.glowDrive * 0.30,
                root.displayTone.b * root.glowDrive * 0.30
            )
        }

        PrincipledMaterial {
            id: outerOrbMaterial
            baseColor: Qt.rgba(
                0.028 + root.displayTone.r * 0.12,
                0.040 + root.displayTone.g * 0.13,
                0.060 + root.displayTone.b * 0.14,
                1.0
            )
            metalness: 0.16
            roughness: 0.17
            clearcoatAmount: 0.66
            clearcoatRoughnessAmount: 0.07
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 0.36,
                root.displayTone.g * root.glowDrive * 0.36,
                root.displayTone.b * root.glowDrive * 0.36
            )
        }

        PrincipledMaterial {
            id: chamberMaterial
            baseColor: Qt.rgba(
                0.040 + root.displayTone.r * 0.19,
                0.074 + root.displayTone.g * 0.24,
                0.17 + root.displayTone.b * 0.29,
                1.0
            )
            metalness: 0.06
            roughness: 0.12
            clearcoatAmount: 0.70
            clearcoatRoughnessAmount: 0.050
            emissiveFactor: Qt.vector3d(
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
            emissiveFactor: Qt.vector3d(
                root.displayTone.r * root.glowDrive * 1.06,
                root.displayTone.g * root.glowDrive * 1.06,
                root.displayTone.b * root.glowDrive * 1.06
            )
        }

        PrincipledMaterial {
            id: lensMaterial
            baseColor: Qt.rgba(
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
            baseColor: root.displayTone
            metalness: 0.04
            roughness: 0.18
            emissiveFactor: Qt.vector3d(
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
            emissiveFactor: Qt.vector3d(
                0.36 + root.displayTone.r * 1.46,
                0.36 + root.displayTone.g * 1.46,
                0.36 + root.displayTone.b * 1.46
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
                -7.5 + root.counterDrift * 0.35 * root.motionGate,
                -15.0 + root.drift * 1.05 * root.motionGate,
                root.failed
                ? Math.sin(root.phase * 3.8) * 1.5
                : root.planning
                  ? root.drift * 0.55
                  : 0.6
            )

            Model {
                source: "#Sphere"
                position: Qt.vector3d(-10.0, 5.0, root.rearDepth)
                scale: Qt.vector3d(1.11, 1.05, 0.62)
                materials: [rearShellMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(-4.0, 2.0, root.rearEnergyDepth)
                scale: Qt.vector3d(0.91, 0.89, 0.54)
                materials: [rearEnergyMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(0, 0, -4.0)
                scale: Qt.vector3d(1.15, 1.15, 0.94)
                materials: [outerOrbMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(2.0, -1.0, root.chamberDepth)
                scale: Qt.vector3d(
                    0.67 + root.effectiveListenLevel * 0.030,
                    0.67 + root.effectiveListenLevel * 0.030,
                    0.50 + root.effectiveSpeechLevel * 0.022
                )
                eulerRotation: Qt.vector3d(
                    root.planning ? root.phase * 8.0 : root.drift * 1.2,
                    root.planning ? -root.phase * 12.0 : root.counterDrift * 1.6,
                    root.executing ? root.phase * 3.0 : 0.0
                )
                materials: [chamberMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    root.executing ? 4.0 : -2.0,
                    root.verifying ? root.drift * 3.0 : 2.0,
                    root.nucleusDepth
                )
                scale: Qt.vector3d(
                    0.29 + root.effectiveListenLevel * 0.016 + root.effectiveSpeechLevel * 0.020,
                    0.29 + root.effectiveListenLevel * 0.016 + root.effectiveSpeechLevel * 0.020,
                    0.25
                )
                materials: [nucleusMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(0, 0, root.lensDepth)
                scale: Qt.vector3d(0.93, 0.93, 0.105)
                materials: [lensMaterial]
            }

            Repeater3D {
                model: 24

                delegate: Model {
                    property int particleIndex: index
                    property real angle:
                        (particleIndex / 24.0) * Math.PI * 2.0
                        + root.phase * (
                            root.planning ? 1.70 :
                            root.executing ? 2.30 :
                            root.verifying ? 1.18 :
                            root.listening ? 0.62 :
                            root.speaking ? 0.72 :
                            0.27
                        )

                    property real orbitRadius:
                        78.0
                        + (particleIndex % 4) * 11.0
                        - (root.listening ? root.effectiveListenLevel * 8.0 : 0.0)

                    property real depthZ:
                        Math.sin(angle * 1.37 + particleIndex * 0.63)
                        * (52.0 + (particleIndex % 4) * 7.0)

                    source: "#Sphere"
                    position: Qt.vector3d(
                        Math.cos(angle) * orbitRadius,
                        Math.sin(angle) * orbitRadius * (0.50 + (particleIndex % 3) * 0.045),
                        depthZ
                    )
                    scale: Qt.vector3d(
                        0.016 + (particleIndex % 3) * 0.005,
                        0.016 + (particleIndex % 3) * 0.005,
                        0.016 + (particleIndex % 3) * 0.005
                    )
                    materials: [particleMaterial]
                }
            }
        }

        // SATELLITE NODES
        Node {
            id: satelliteSystem

            Repeater3D {
                model: 6

                delegate: Model {
                    property int satelliteIndex: index
                    property real direction: satelliteIndex % 2 === 0 ? 1.0 : -0.82
                    property real angle:
                        root.phase * root.satelliteSpeed * direction
                        + satelliteIndex * 1.37

                    property int orbitPlane: satelliteIndex % 3
                    property real radiusX: 112.0 + (satelliteIndex % 3) * 18.0
                    property real radiusY: 42.0 + (satelliteIndex % 2) * 17.0
                    property real xPos: Math.cos(angle) * radiusX
                    property real yPos:
                        orbitPlane === 0
                        ? Math.sin(angle) * radiusY
                        : orbitPlane === 1
                          ? Math.sin(angle) * radiusY + Math.cos(angle) * 13.0
                          : Math.sin(angle) * (radiusY * 0.82) - Math.cos(angle) * 16.0

                    property real zPos:
                        orbitPlane === 0
                        ? Math.sin(angle) * 72.0
                        : orbitPlane === 1
                          ? -Math.sin(angle) * 58.0 + Math.cos(angle) * 24.0
                          : Math.sin(angle) * 82.0 + Math.cos(angle) * 14.0

                    source: "#Sphere"
                    position: Qt.vector3d(xPos, yPos, zPos)
                    scale: Qt.vector3d(
                        0.039 + (satelliteIndex % 3) * 0.007 + root.effectiveListenLevel * 0.004,
                        0.039 + (satelliteIndex % 3) * 0.007 + root.effectiveListenLevel * 0.004,
                        0.039 + (satelliteIndex % 3) * 0.007 + root.effectiveListenLevel * 0.004
                    )
                    materials: [satelliteMaterial]
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // 4. FRONT GLASS REFLECTION CANVAS
    // ------------------------------------------------------------------------
    Canvas {
        id: glassCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r = root.auraRadius * root.coreBreath * 0.83
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            ctx.lineWidth = Math.max(1.0, r * 0.010)
            ctx.strokeStyle = root.rgbaString(tone, 0.15 + root.glowDrive * 0.05)
            ctx.beginPath()
            ctx.arc(cx, cy, r, Math.PI * 0.06, Math.PI * 1.86)
            ctx.stroke()

            ctx.lineWidth = Math.max(1.0, r * 0.018)
            ctx.strokeStyle = "rgba(255,255,255,0.17)"
            ctx.beginPath()
            ctx.arc(cx - r * 0.020, cy - r * 0.018, r * 0.76, Math.PI * 1.11, Math.PI * 1.48)
            ctx.stroke()

            var kernelRadius = r * (0.13 + root.effectiveListenLevel * 0.030 + root.effectiveSpeechLevel * 0.028)
            var kernel = ctx.createRadialGradient(
                cx - kernelRadius * 0.18,
                cy - kernelRadius * 0.18,
                1,
                cx,
                cy,
                kernelRadius
            )
            kernel.addColorStop(0.0, "rgba(255,255,255,0.46)")
            kernel.addColorStop(0.42, root.rgbaString(tone, 0.28))
            kernel.addColorStop(1.0, root.rgbaString(tone, 0.0))

            ctx.fillStyle = kernel
            ctx.beginPath()
            ctx.arc(cx, cy, kernelRadius, 0, Math.PI * 2.0)
            ctx.fill()
        }
    }

    // ------------------------------------------------------------------------
    // 5. FRONT ORBITAL TRACERS
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

            function movingArc(rx, ry, rotation, startAngle, arcLength, alphaValue) {
                var steps = 30
                var cr = Math.cos(rotation)
                var sr = Math.sin(rotation)

                ctx.beginPath()
                for (var i = 0; i <= steps; ++i) {
                    var t = startAngle + (i / steps) * arcLength
                    var ex = Math.cos(t) * rx
                    var ey = Math.sin(t) * ry
                    var x = cx + ex * cr - ey * sr
                    var y = cy + ex * sr + ey * cr

                    if (i === 0)
                        ctx.moveTo(x, y)
                    else
                        ctx.lineTo(x, y)
                }
                ctx.lineWidth = Math.max(1.1, r * 0.008)
                ctx.strokeStyle = root.rgbaString(tone, alphaValue)
                ctx.stroke()
            }

            var p = root.phase * root.satelliteSpeed

            movingArc(r * 1.34, r * 0.48, -0.34, p + 0.10, 0.72, root.tracerOpacity * 1.20)
            movingArc(r * 1.18, r * 0.62, 0.18, -p * 0.82 + 2.10, 0.58, root.tracerOpacity * 0.94)
            movingArc(r * 1.44, r * 0.38, 0.58, p * 0.66 + 4.10, 0.48, root.tracerOpacity * 0.75)
        }
    }

    // Synchronize canvas repaints on property triggers
    onPhaseChanged: {
        rearOrbitCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
        if (root.listening || root.speaking || root.verifying) {
            auraCanvas.requestPaint()
        }
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

    onStateTextChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onVisualModeChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }

    onGlowDriveChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onAuraRadiusChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onEffectiveListenLevelChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    onEffectiveSpeechLevelChanged: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
    }

    Component.onCompleted: {
        auraCanvas.requestPaint()
        glassCanvas.requestPaint()
        rearOrbitCanvas.requestPaint()
        frontOrbitCanvas.requestPaint()
    }
}
