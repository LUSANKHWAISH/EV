// EVIntelligenceCore.qml
// E.V. TASK 011C — R11G1 GROK FLAGSHIP CANDIDATE
//
// Source direction: Grok's proposed pure-QML flagship core.
// Integration/correctness pass: ChatGPT.
//
// IMPORTANT:
// - Preserves E.V. state contract.
// - Fixed-world Qt Quick 3D: no pixel-to-world geometry scaling.
// - No external 3D asset loading or Blender dependency.
// - Grok's structural shell, deep chamber, sparse gold filaments and
//   true-3D particle field are preserved as the visual experiment.
// - R11G1 is a candidate only. Judge runtime before accepting.
//
// Compatible target:
//   import QtQuick 2.15
//   import QtQuick3D
//   import "../theme"

import QtQuick 2.15
import QtQuick3D
import "../theme"

Item {
    id: root

    // ========================================================================
    // PUBLIC E.V. INTERFACE — DO NOT BREAK
    // ========================================================================
    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    property string stateText:
        state === null || state === undefined || String(state).length === 0
        ? "IDLE"
        : String(state)

    property real energy: Theme.stateEnergy(root.stateText)
    property color stateTone: Theme.stateColor(root.stateText)

    // Optional future voice inputs.
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // ========================================================================
    // NORMALISED STATE
    // ========================================================================
    readonly property string activeState: {
        var s = root.stateText === undefined || root.stateText === null
                ? "IDLE"
                : String(root.stateText).toUpperCase()

        s = s.replace(/[\s-]+/g, "_")

        // Be tolerant of enum-like stringification such as "EVState.IDLE".
        var dot = s.lastIndexOf(".")
        if (dot >= 0)
            s = s.substring(dot + 1)

        return s.length > 0 ? s : "IDLE"
    }

    readonly property real energyClamped:
        Math.max(0.05, Math.min(1.0, root.energy))

    readonly property real rawAudio:
        Math.max(0.0, Math.min(1.0, root.audioLevel))

    readonly property real rawSpeech:
        Math.max(0.0, Math.min(1.0, root.speechLevel))

    // Demo-state fallbacks. Real voice levels override them automatically.
    readonly property real syntheticAudio:
        root.activeState === "LISTENING"
        ? 0.18 + ((Math.sin(root.globalPhase * 5.2) + 1.0) * 0.5) * 0.42
        : 0.0

    readonly property real syntheticSpeech:
        root.activeState === "SPEAKING"
        ? 0.16
          + Math.max(0.0, Math.sin(root.globalPhase * 7.6)) * 0.55
        : 0.0

    readonly property real audio:
        root.activeState === "LISTENING"
        ? (root.rawAudio > 0.01 ? root.rawAudio : root.syntheticAudio)
        : 0.0

    readonly property real speech:
        root.activeState === "SPEAKING"
        ? (root.rawSpeech > 0.01 ? root.rawSpeech : root.syntheticSpeech)
        : 0.0

    // ========================================================================
    // STATE TARGETS
    // ========================================================================
    property real shellOpenBase: 0.0
    property real filamentActivityBase: 0.05
    property real particleSpeedBase: 0.18
    property real energyIntensityBase: 0.32
    property real desync: 0.0
    property real lockAmount: 0.0
    property real successBloom: 0.0
    property real recoverProgress: 1.0

    readonly property real shellOpen:
        Math.max(
            0.0,
            Math.min(
                1.0,
                root.shellOpenBase
                + (root.activeState === "LISTENING" ? root.audio * 0.45 : 0.0)
            )
        )

    readonly property real filamentActivity:
        Math.max(
            0.0,
            Math.min(
                1.0,
                root.filamentActivityBase
                + (root.activeState === "SPEAKING" ? root.speech * 0.38 : 0.0)
            )
        )

    readonly property real particleSpeed:
        root.particleSpeedBase
        + (root.activeState === "LISTENING" ? root.audio * 0.50 : 0.0)

    readonly property real energyIntensity:
        Math.max(
            0.03,
            Math.min(
                1.30,
                root.energyIntensityBase
                + (root.activeState === "LISTENING" ? root.audio * 0.30 : 0.0)
                + (root.activeState === "SPEAKING" ? root.speech * 0.34 : 0.0)
                + root.successBloom * 0.10
            )
        )

    // Continuous phase drivers.
    property real globalPhase: 0.0
    property real filamentPhase: 0.0
    property real particlePhase: 0.0

    // Separate breath signal avoids fighting voice/state writes.
    property real breathPulse: 0.0

    readonly property real nucleusPulse:
        Math.max(
            root.breathPulse,
            root.activeState === "SPEAKING" ? root.speech * 0.92 : 0.0
        )

    // ========================================================================
    // BACKGROUND AURA ONLY
    // ========================================================================
    Canvas {
        id: auraCanvas
        anchors.fill: parent
        z: -1
        opacity: 0.22 + root.energyIntensity * 0.18
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            ctx.clearRect(0, 0, width, height)

            var cx = width * 0.5
            var cy = height * 0.5
            var r = Math.min(width, height) * 0.42

            var g = ctx.createRadialGradient(
                cx, cy, r * 0.15,
                cx, cy, r
            )

            g.addColorStop(
                0.0,
                Qt.rgba(
                    0.07,
                    0.18,
                    0.45,
                    0.35 * root.energyIntensity
                )
            )

            g.addColorStop(
                0.55,
                Qt.rgba(0.04, 0.09, 0.22, 0.12)
            )

            g.addColorStop(
                1.0,
                Qt.rgba(0.0, 0.0, 0.0, 0.0)
            )

            ctx.fillStyle = g
            ctx.fillRect(0, 0, width, height)
        }
    }

    // ========================================================================
    // TRUE 3D CORE
    // ========================================================================
    View3D {
        id: view
        anchors.fill: parent

        environment: SceneEnvironment {
            id: sceneEnv
            backgroundMode: SceneEnvironment.Transparent
            clearColor: "transparent"
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        // Fixed world. The viewport changes size; the geometry does not.
        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 12, 500)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1400
        }

        // --------------------------------------------------------------------
        // LIGHTING
        // --------------------------------------------------------------------
        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-42, -35, 0)
            brightness: 1.25
            color: "#E8F0FF"
            ambientColor: "#0B1019"
            castsShadow: false
        }

        DirectionalLight {
            id: rimLight
            eulerRotation: Qt.vector3d(25, 140, 0)
            brightness: 0.62
            color: "#A8C4FF"
            ambientColor: "#05080D"
            castsShadow: false
        }

        PointLight {
            id: coreLight
            position: Qt.vector3d(0, 0, 70)
            brightness:
                0.90
                + root.energyIntensity * 1.40
                + root.speech * 0.80
            color: "#4F8CFF"
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000030
        }

        PointLight {
            id: goldAccentLight
            position: Qt.vector3d(48, -28, 72)
            brightness:
                0.22
                + root.filamentActivity * 0.72
            color: "#FFD08A"
            constantFade: 1.0
            linearFade: 0.005
            quadraticFade: 0.000035
        }

        // ====================================================================
        // MATERIALS
        // ====================================================================
        PrincipledMaterial {
            id: shellMatDark
            baseColor: "#0A0E16"
            metalness: 0.92
            roughness: 0.38
            clearcoatAmount: 0.35
            clearcoatRoughnessAmount: 0.25
            emissiveFactor: Qt.vector3d(
                0.008 * root.energyIntensity,
                0.018 * root.energyIntensity,
                0.050 * root.energyIntensity
            )
        }

        PrincipledMaterial {
            id: shellMatMid
            baseColor: "#101822"
            metalness: 0.88
            roughness: 0.42
            clearcoatAmount: 0.28
            clearcoatRoughnessAmount: 0.22
        }

        PrincipledMaterial {
            id: shellMatEdge
            baseColor: "#1A2430"
            metalness: 0.95
            roughness: 0.28
            clearcoatAmount: 0.50
            clearcoatRoughnessAmount: 0.15
        }

        PrincipledMaterial {
            id: edgeAccentMat
            baseColor: "#8A9BB0"
            metalness: 0.97
            roughness: 0.18
            clearcoatAmount: 0.60
            clearcoatRoughnessAmount: 0.10
            emissiveFactor: Qt.vector3d(0.05, 0.07, 0.10)
        }

        PrincipledMaterial {
            id: frontGlassMat
            baseColor: Qt.rgba(0.15, 0.35, 0.70, 0.22)
            metalness: 0.10
            roughness: 0.08
            clearcoatAmount: 0.85
            clearcoatRoughnessAmount: 0.05
            transmissionFactor: 0.65
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: energyVolumeMat
            baseColor: Qt.rgba(0.08, 0.22, 0.65, 0.58)
            metalness: 0.05
            roughness: 0.15
            emissiveFactor: Qt.vector3d(
                0.07 + root.energyIntensity * 0.12,
                0.22 + root.energyIntensity * 0.35,
                0.70 + root.energyIntensity * 0.80 + root.speech * 0.32
            )
            clearcoatAmount: 0.40
            clearcoatRoughnessAmount: 0.08
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: nucleusMat
            baseColor: "#05070C"
            metalness: 0.60
            roughness: 0.48
            clearcoatAmount: 0.32
            clearcoatRoughnessAmount: 0.12
            emissiveFactor: Qt.vector3d(
                0.02,
                0.04,
                0.12 + root.energyIntensity * 0.15
            )
        }

        PrincipledMaterial {
            id: rearCavityMat
            baseColor: Qt.rgba(0.06, 0.10, 0.20, 0.46)
            metalness: 0.30
            roughness: 0.40
            emissiveFactor: Qt.vector3d(0.02, 0.05, 0.15)
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: internalRingMat
            baseColor: Qt.rgba(0.20, 0.45, 0.90, 0.20)
            metalness: 0.20
            roughness: 0.20
            emissiveFactor: Qt.vector3d(
                0.10,
                0.25,
                0.62 + root.energyIntensity * 0.18
            )
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: goldFilamentMat
            baseColor: "#C9A86C"
            metalness: 0.98
            roughness: 0.22
            emissiveFactor: Qt.vector3d(
                0.28 + root.filamentActivity * 0.40,
                0.19 + root.filamentActivity * 0.28,
                0.07 + root.filamentActivity * 0.09
            )
            clearcoatAmount: 0.40
            clearcoatRoughnessAmount: 0.12
        }

        PrincipledMaterial {
            id: goldNodeMat
            baseColor: "#D7AD69"
            metalness: 0.95
            roughness: 0.18
            emissiveFactor: Qt.vector3d(
                0.34 + root.filamentActivity * 0.42,
                0.22 + root.filamentActivity * 0.20,
                0.07
            )
        }

        PrincipledMaterial {
            id: particleMat
            baseColor: "#58B8FF"
            metalness: 0.10
            roughness: 0.30
            emissiveFactor: Qt.vector3d(
                0.25,
                0.55,
                1.05 + root.energyIntensity * 0.20
            )
        }

        // ====================================================================
        // MASTER INTELLIGENCE ASSEMBLY
        // ====================================================================
        Node {
            id: coreRoot

            // Permanent 3/4 presentation angle lives on the object rather than
            // pointing the camera away from the origin.
            eulerRotation: Qt.vector3d(
                -8.2
                + Math.sin(root.globalPhase * 0.37) * 1.1
                + root.desync * 3.0,

                -14.5
                + Math.cos(root.globalPhase * 0.29) * 1.5
                - root.desync * 2.4,

                1.8
                + Math.sin(root.globalPhase * 0.19) * 0.55
            )

            position: Qt.vector3d(
                Math.sin(root.globalPhase * 0.21) * 2.2,
                Math.cos(root.globalPhase * 0.17) * 1.6,
                0
            )

            scale: Qt.vector3d(
                0.96 + root.nucleusPulse * 0.018 + root.successBloom * 0.025,
                0.96 + root.nucleusPulse * 0.018 + root.successBloom * 0.025,
                0.96 + root.nucleusPulse * 0.018 + root.successBloom * 0.025
            )

            // ================================================================
            // A. GROK OUTER INTELLIGENCE SHELL
            // ================================================================
            Node {
                id: outerShell

                // Front-left structural plate.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.85, 0.22, 0.55)
                    position: Qt.vector3d(
                        -48 - root.shellOpen * 14,
                        32 + root.shellOpen * 6,
                        68 + root.shellOpen * 12
                    )
                    eulerRotation: Qt.vector3d(12, -28, 18)
                    materials: [shellMatDark]
                }

                // Front-right structural plate.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.65, 0.20, 0.48)
                    position: Qt.vector3d(
                        52 + root.shellOpen * 12,
                        18,
                        72 + root.shellOpen * 10
                    )
                    eulerRotation: Qt.vector3d(-8, 22, -14)
                    materials: [shellMatDark]
                }

                // Upper rear plate.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.95, 0.18, 0.62)
                    position: Qt.vector3d(
                        -12,
                        48 - root.shellOpen * 4,
                        -62
                    )
                    eulerRotation: Qt.vector3d(8, 5, -6)
                    materials: [shellMatMid]
                }

                // Lower rear stator plate.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.70, 0.24, 0.70)
                    position: Qt.vector3d(18, -42, -78)
                    eulerRotation: Qt.vector3d(-14, -18, 9)
                    materials: [shellMatDark]
                }

                // Mid-left rail.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(0.28, 1.90, 0.35)
                    position: Qt.vector3d(
                        -62 - root.shellOpen * 8,
                        5,
                        18
                    )
                    eulerRotation: Qt.vector3d(4, 12, -8)
                    materials: [shellMatEdge]
                }

                // Mid-right rail.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(0.26, 1.75, 0.32)
                    position: Qt.vector3d(
                        58 + root.shellOpen * 9,
                        -8,
                        8
                    )
                    eulerRotation: Qt.vector3d(-6, -15, 11)
                    materials: [shellMatEdge]
                }

                // Lower front lip.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.40, 0.18, 0.40)
                    position: Qt.vector3d(
                        -8,
                        -48 - root.shellOpen * 5,
                        55 + root.shellOpen * 8
                    )
                    eulerRotation: Qt.vector3d(18, 4, -3)
                    materials: [shellMatMid]
                }

                // Upper front partial canopy.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.55, 0.16, 0.45)
                    position: Qt.vector3d(
                        22,
                        55 + root.shellOpen * 7,
                        48
                    )
                    eulerRotation: Qt.vector3d(-22, -12, 7)
                    materials: [shellMatDark]
                }

                // Deep rear architecture.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(1.30, 0.90, 0.28)
                    position: Qt.vector3d(-28, -5, -88)
                    eulerRotation: Qt.vector3d(3, 28, -4)
                    materials: [shellMatDark]
                }

                // Precision titanium accents.
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(0.12, 1.10, 0.12)
                    position: Qt.vector3d(-55, 25, 42)
                    eulerRotation: Qt.vector3d(5, -8, 0)
                    materials: [edgeAccentMat]
                }

                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(0.11, 0.95, 0.11)
                    position: Qt.vector3d(51, -22, 38)
                    eulerRotation: Qt.vector3d(-4, 11, 0)
                    materials: [edgeAccentMat]
                }
            }

            // ================================================================
            // B. GROK DEEP INTERNAL ENERGY CHAMBER
            // ================================================================
            Node {
                id: energyChamber

                eulerRotation: Qt.vector3d(
                    Math.sin(root.globalPhase * 0.60)
                    * (2.0 + root.filamentActivity * 3.5),

                    root.filamentPhase
                    * 22.0
                    * (1.0 - root.lockAmount),

                    Math.cos(root.globalPhase * 0.45) * 1.8
                )

                // Front containment glass.
                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.92, 0.92, 0.55)
                    position: Qt.vector3d(0, 0, 38)
                    materials: [frontGlassMat]
                }

                // Main sapphire energy volume.
                Model {
                    id: energyVolume
                    source: "#Sphere"
                    scale: Qt.vector3d(
                        0.78 + root.nucleusPulse * 0.06 + root.speech * 0.05,
                        0.78 + root.nucleusPulse * 0.06 + root.speech * 0.05,
                        0.72 + root.nucleusPulse * 0.05
                    )
                    position: Qt.vector3d(0, 0, 12)
                    materials: [energyVolumeMat]
                }

                // Dark cognition nucleus.
                Model {
                    id: nucleus
                    source: "#Sphere"
                    scale: Qt.vector3d(
                        0.32 + root.nucleusPulse * 0.04,
                        0.32 + root.nucleusPulse * 0.04,
                        0.32 + root.nucleusPulse * 0.04
                    )
                    position: Qt.vector3d(
                        root.activeState === "EXECUTING" ? 4 : 0,
                        root.activeState === "VERIFYING"
                            ? Math.sin(root.globalPhase * 2.0) * 3.5
                            : 0,
                        2
                    )
                    materials: [nucleusMat]
                }

                // Rear cavity.
                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.68, 0.68, 0.45)
                    position: Qt.vector3d(0, 0, -32)
                    materials: [rearCavityMat]
                }

                // Internal depth marker at Z +22.
                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.95, 0.04, 0.95)
                    position: Qt.vector3d(0, 0, 22)
                    eulerRotation: Qt.vector3d(90, 0, 0)
                    materials: [internalRingMat]
                }

                // Internal depth marker at Z -8.
                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.72, 0.035, 0.72)
                    position: Qt.vector3d(0, 0, -8)
                    eulerRotation: Qt.vector3d(90, 0, 0)
                    materials: [internalRingMat]
                }
            }

            // ================================================================
            // C. GROK SPARSE GOLD INTELLIGENCE FILAMENTS
            // ================================================================
            Node {
                id: filamentSystem
                opacity: 0.24 + root.filamentActivity * 0.66

                // The whole neural network subtly rotates/re-registers.
                eulerRotation: Qt.vector3d(
                    Math.sin(root.filamentPhase * 0.7) * 2.0,
                    root.filamentPhase * 7.0,
                    Math.cos(root.filamentPhase * 0.6) * 1.5
                )

                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.035, 0.85, 0.035)
                    position: Qt.vector3d(28, 12, 25)
                    eulerRotation: Qt.vector3d(55, -35, 10)
                    materials: [goldFilamentMat]
                }

                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.028, 0.70, 0.028)
                    position: Qt.vector3d(-24, -18, 15)
                    eulerRotation: Qt.vector3d(-40, 50, -8)
                    materials: [goldFilamentMat]
                }

                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.030, 0.60, 0.030)
                    position: Qt.vector3d(8, 22, -28)
                    eulerRotation: Qt.vector3d(25, 15, 70)
                    materials: [goldFilamentMat]
                }

                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.060, 0.060, 0.060)
                    position: Qt.vector3d(22, 8, 32)
                    materials: [goldNodeMat]
                }

                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.050, 0.050, 0.050)
                    position: Qt.vector3d(-18, -12, 18)
                    materials: [goldNodeMat]
                }

                Model {
                    source: "#Sphere"
                    scale: Qt.vector3d(0.055, 0.055, 0.055)
                    position: Qt.vector3d(5, 15, -22)
                    materials: [goldNodeMat]
                }

                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(
                        0.022,
                        0.55 + root.filamentActivity * 0.15,
                        0.022
                    )
                    position: Qt.vector3d(-12, 28, 8)
                    eulerRotation: Qt.vector3d(70, 20, -30)
                    materials: [goldFilamentMat]
                    opacity: 0.35 + root.filamentActivity * 0.60
                }

                Model {
                    source: "#Cylinder"
                    scale: Qt.vector3d(0.020, 0.48, 0.020)
                    position: Qt.vector3d(30, -15, -5)
                    eulerRotation: Qt.vector3d(-25, -40, 55)
                    materials: [goldFilamentMat]
                    opacity: 0.30 + root.filamentActivity * 0.65
                }
            }

            // ================================================================
            // D. GROK TRUE-3D PARTICLE FIELD
            // ================================================================
            Node {
                id: particleField

                Repeater3D {
                    id: particleRepeater
                    model: 36

                    delegate: Node {
                        id: pNode

                        property real seed:
                            index * 1.6180339887

                        property real orbitRadius:
                            28 + (index % 7) * 9.5

                        property real speed:
                            0.40 + (index % 5) * 0.18

                        property real elevation:
                            ((index * 37) % 160) - 80

                        property real phaseOffset:
                            seed * 2.3

                        property real listenPull:
                            root.activeState === "LISTENING"
                            ? root.audio * 11.0
                            : 0.0

                        position: Qt.vector3d(
                            Math.cos(
                                root.particlePhase * speed + phaseOffset
                            )
                            * Math.max(14.0, orbitRadius - listenPull)
                            * 0.95,

                            Math.sin(
                                root.particlePhase * speed * 0.7
                                + phaseOffset * 0.6
                            )
                            * Math.max(14.0, orbitRadius - listenPull)
                            * 0.55
                            + elevation * 0.15,

                            Math.sin(
                                root.particlePhase * speed * 0.85
                                + phaseOffset
                            )
                            * orbitRadius
                            * 0.75
                            + (
                                index % 3 === 0
                                ? -45
                                : (
                                    index % 3 === 1
                                    ? 15
                                    : 40
                                )
                              )
                        )

                        Model {
                            source: "#Sphere"
                            scale: Qt.vector3d(
                                0.040 + (index % 4) * 0.010,
                                0.040 + (index % 4) * 0.010,
                                0.040 + (index % 4) * 0.010
                            )
                            materials: [particleMat]
                            opacity:
                                0.34
                                + root.energyIntensity * 0.36
                                + (index % 3) * 0.06
                        }
                    }
                }
            }
        }
    }

    // ========================================================================
    // MOTION
    // ========================================================================
    Timer {
        id: phaseTimer
        interval: 16
        running: root.visible
        repeat: true

        onTriggered: {
            var dt = 0.016

            root.globalPhase +=
                dt
                * (0.22 + root.energyIntensity * 0.15)
                * (1.0 - root.lockAmount * 0.85)

            root.filamentPhase +=
                dt
                * (0.40 + root.filamentActivity * 1.80)
                * (1.0 - root.lockAmount * 0.85)

            root.particlePhase +=
                dt
                * root.particleSpeed
                * (1.0 - root.lockAmount * 0.90)

            // Failed state adds a controlled phase disagreement.
            if (root.activeState === "FAILED")
                root.particlePhase += dt * 0.06

            auraCanvas.requestPaint()
        }
    }

    SequentialAnimation {
        id: breathAnim
        running: root.visible && root.activeState !== "STOPPED"
        loops: Animation.Infinite

        NumberAnimation {
            target: root
            property: "breathPulse"
            from: 0.0
            to: 0.85
            duration: 3100
            easing.type: Easing.InOutSine
        }

        NumberAnimation {
            target: root
            property: "breathPulse"
            from: 0.85
            to: 0.0
            duration: 3500
            easing.type: Easing.InOutSine
        }
    }

    // ========================================================================
    // STATE MACHINE
    // ========================================================================
    function applyState(s) {
        successSettle.stop()
        recoverAnim.stop()

        root.shellOpenBase = 0.0
        root.filamentActivityBase = 0.05
        root.particleSpeedBase = 0.18
        root.energyIntensityBase = 0.32
        root.desync = 0.0
        root.lockAmount = 0.0
        root.successBloom = 0.0
        root.recoverProgress = 1.0

        switch (s) {
        case "IDLE":
            root.shellOpenBase = 0.05
            root.energyIntensityBase =
                0.28 + root.energyClamped * 0.15
            root.particleSpeedBase = 0.16
            root.filamentActivityBase = 0.03
            break

        case "LISTENING":
            root.shellOpenBase = 0.18
            root.energyIntensityBase = 0.46
            root.particleSpeedBase = 0.42
            root.filamentActivityBase = 0.15
            break

        case "PLANNING":
            root.shellOpenBase = 0.18
            root.energyIntensityBase = 0.62
            root.particleSpeedBase = 0.45
            root.filamentActivityBase = 0.85
            break

        case "EXECUTING":
            root.shellOpenBase = 0.28
            root.energyIntensityBase = 0.75
            root.particleSpeedBase = 0.70
            root.filamentActivityBase = 0.55
            break

        case "VERIFYING":
            root.shellOpenBase = 0.12
            root.energyIntensityBase = 0.58
            root.particleSpeedBase = 0.35
            root.filamentActivityBase = 0.40
            break

        case "AWAITING_APPROVAL":
            root.shellOpenBase = 0.02
            root.energyIntensityBase = 0.38
            root.particleSpeedBase = 0.06
            root.filamentActivityBase = 0.08
            root.lockAmount = 0.92
            break

        case "SPEAKING":
            root.shellOpenBase = 0.15
            root.energyIntensityBase = 0.56
            root.particleSpeedBase = 0.40
            root.filamentActivityBase = 0.36
            break

        case "SUCCESS":
            root.shellOpenBase = 0.45
            root.energyIntensityBase = 0.95
            root.particleSpeedBase = 0.50
            root.filamentActivityBase = 0.30
            root.successBloom = 1.0
            successSettle.start()
            break

        case "FAILED":
            root.shellOpenBase = 0.08
            root.energyIntensityBase = 0.18
            root.particleSpeedBase = 0.12
            root.filamentActivityBase = 0.05
            root.desync = 0.85
            break

        case "RECOVERING":
            root.shellOpenBase = 0.20
            root.energyIntensityBase = 0.40
            root.particleSpeedBase = 0.30
            root.filamentActivityBase = 0.35
            root.desync = 0.40
            root.recoverProgress = 0.0
            recoverAnim.start()
            break

        case "STOPPED":
            root.shellOpenBase = 0.0
            root.energyIntensityBase = 0.06
            root.particleSpeedBase = 0.02
            root.filamentActivityBase = 0.0
            root.lockAmount = 0.97
            break

        default:
            root.shellOpenBase = 0.05
            root.energyIntensityBase = 0.30
            root.particleSpeedBase = 0.16
            root.filamentActivityBase = 0.03
            break
        }

        auraCanvas.requestPaint()
    }

    SequentialAnimation {
        id: successSettle

        PauseAnimation {
            duration: 900
        }

        ParallelAnimation {
            NumberAnimation {
                target: root
                property: "shellOpenBase"
                to: 0.08
                duration: 1400
                easing.type: Easing.OutCubic
            }

            NumberAnimation {
                target: root
                property: "energyIntensityBase"
                to: 0.40
                duration: 1200
                easing.type: Easing.OutCubic
            }

            NumberAnimation {
                target: root
                property: "successBloom"
                to: 0.0
                duration: 1200
                easing.type: Easing.OutCubic
            }
        }
    }

    SequentialAnimation {
        id: recoverAnim

        NumberAnimation {
            target: root
            property: "desync"
            to: 0.0
            duration: 1600
            easing.type: Easing.OutQuad
        }

        ParallelAnimation {
            NumberAnimation {
                target: root
                property: "recoverProgress"
                to: 1.0
                duration: 1200
                easing.type: Easing.OutCubic
            }

            NumberAnimation {
                target: root
                property: "energyIntensityBase"
                to: 0.45
                duration: 800
                easing.type: Easing.OutQuad
            }
        }
    }

    Behavior on shellOpenBase {
        NumberAnimation {
            duration: 700
            easing.type: Easing.OutCubic
        }
    }

    Behavior on energyIntensityBase {
        NumberAnimation {
            duration: 500
            easing.type: Easing.OutQuad
        }
    }

    Behavior on filamentActivityBase {
        NumberAnimation {
            duration: 600
            easing.type: Easing.OutCubic
        }
    }

    Behavior on particleSpeedBase {
        NumberAnimation {
            duration: 800
            easing.type: Easing.OutQuad
        }
    }

    Behavior on desync {
        NumberAnimation {
            duration: 900
            easing.type: Easing.OutQuad
        }
    }

    Behavior on lockAmount {
        NumberAnimation {
            duration: 500
            easing.type: Easing.OutCubic
        }
    }

    onActiveStateChanged:
        root.applyState(root.activeState)

    onEnergyIntensityChanged:
        auraCanvas.requestPaint()

    onWidthChanged:
        auraCanvas.requestPaint()

    onHeightChanged:
        auraCanvas.requestPaint()

    Component.onCompleted: {
        root.applyState(root.activeState)
        auraCanvas.requestPaint()
    }
}
