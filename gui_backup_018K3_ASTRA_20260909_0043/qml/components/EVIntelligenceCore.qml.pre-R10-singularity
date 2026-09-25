import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — SPLIT NEURAL MONOLITH R10
// ============================================================================
//
// Authored-3D flagship candidate.
//
// R10 deliberately abandons the petal/cocoon silhouette from R9. The core is
// now composed as two engineered graphite cognition masses separated by a
// vertical intelligence fissure. Four primary hard-surface shell plates define
// the silhouette; two inset plates add controlled layer depth. State energy is
// concentrated inside the fissure instead of painting the shell.
//
// Design constraints:
// - no eye / lens / ring / flower / orbital topology
// - no full enclosure around the center
// - broad, asymmetric engineered shell masses
// - central negative-space cognition fissure
// - authored GLB shell geometry with real thickness + camber
// - sparse emissive logic elements only inside the fissure
// - fixed 3D world; viewport resize never changes world coordinates
// ============================================================================

Item {
    id: root

    readonly property real cameraDistance: 385.0

    // ------------------------------------------------------------------------
    // PUBLIC INTERFACE — preserved for EVFlagshipStage
    // ------------------------------------------------------------------------
    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    property string stateText:
        state === null ||
        state === undefined ||
        String(state).length === 0
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
    // MOTION CLOCK
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1500 :
        root.speaking ? 1850 :
        root.failed ? 1180 :
        root.verifying ? 2050 :
        root.planning ? 2900 :
        root.listening ? 3200 :
        root.recovering ? 3600 :
        root.awaiting ? 6200 :
        root.successful ? 2400 :
        4700

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.52) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.48)
    readonly property real microDrift: Math.sin(root.phase * 0.83)
    readonly property real scanWave: Math.sin(root.phase * 1.35)

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
    // STATE SCALARS
    // ------------------------------------------------------------------------
    property real openness:
        root.listening ? 1.0 :
        root.speaking ? 0.58 :
        root.successful ? 0.22 :
        root.failed ? -0.08 :
        root.stopped ? -0.36 :
        0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.22 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 540; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 420; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 500; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 640; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 780; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 460; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.90

    readonly property real emissionBase:
        root.stopped ? 0.025 :
        root.listening ? 0.84 :
        root.planning ? 0.68 :
        root.executing ? 0.92 :
        root.verifying ? 0.98 :
        root.awaiting ? 0.46 :
        root.speaking ? 0.82 :
        root.successful ? 1.00 :
        root.failed ? 0.88 :
        root.recovering ? 0.72 :
        0.48

    readonly property real emissionIntensity:
        root.emissionBase * (0.86 + root.pulse * 0.14)

    // ------------------------------------------------------------------------
    // INTERNAL COGNITION MATERIALS
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: signalMaterial
        baseColor: root.stateTone
        metalness: 0.18
        roughness: 0.16
        clearcoatAmount: 0.42
        clearcoatRoughnessAmount: 0.10
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity * 1.95,
            root.stateTone.g * root.emissionIntensity * 1.95,
            root.stateTone.b * root.emissionIntensity * 1.95
        )
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: secondarySignalMaterial
        baseColor: root.stateTone
        metalness: 0.10
        roughness: 0.24
        clearcoatAmount: 0.20
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity * 0.95,
            root.stateTone.g * root.emissionIntensity * 0.95,
            root.stateTone.b * root.emissionIntensity * 0.95
        )
        cullMode: Material.NoCulling
    }

    // ------------------------------------------------------------------------
    // 3D SCENE
    // ------------------------------------------------------------------------
    View3D {
        anchors.fill: parent

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowStrength: 0.34
            glowIntensity: 0.50
            glowBloom: 0.065
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(0, 0, 0)
            fieldOfView: 38
            clipNear: 1.0
            clipFar: 2000.0
        }

        // Neutral graphite key: establishes broad shell planes.
        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-30, 34, -8)
            color: "#f4f7fb"
            brightness: 3.55
            ambientColor: "#19232d"
            castsShadow: false
        }

        // Cooler opposite fill prevents the deep shell from collapsing to black.
        DirectionalLight {
            id: fillLight
            eulerRotation: Qt.vector3d(26, -50, 13)
            color: "#a5b6c8"
            brightness: 1.48
            ambientColor: "#0d151e"
            castsShadow: false
        }

        PointLight {
            id: leftRim
            position: Qt.vector3d(-152, 88, 138)
            color: "#d5e6f7"
            brightness: 2.65
            constantFade: 1.0
            linearFade: 0.0038
            quadraticFade: 0.000018
        }

        PointLight {
            id: rightRim
            position: Qt.vector3d(148, -86, 112)
            color: "#8ea3b8"
            brightness: 1.55
            constantFade: 1.0
            linearFade: 0.0040
            quadraticFade: 0.000020
        }

        // State energy lives in the fissure, not on the shell exterior.
        PointLight {
            id: cognitionLight
            position: Qt.vector3d(
                root.executionFlow * 12,
                root.verificationFocus * root.scanWave * 72,
                52 + root.planningDepth * 17
            )
            color: root.stateTone
            brightness: root.stopped
                ? 0.02
                : 1.00 + root.energy * 1.08 + root.verificationFocus * 0.42
            constantFade: 1.0
            linearFade: 0.0034
            quadraticFade: 0.000018
        }

        PointLight {
            id: rearCognitionLight
            position: Qt.vector3d(
                -8 - root.openness * 7,
                -16 + root.successLift * 11,
                -50 - root.planningDepth * 12
            )
            color: root.stateTone
            brightness: root.stopped ? 0.01 : 0.46 + root.energy * 0.62
            constantFade: 1.0
            linearFade: 0.0039
            quadraticFade: 0.000023
        }

        Node {
            id: artifactRoot

            position: Qt.vector3d(0, -2 + root.successLift * 4, 0)

            // A restrained 3/4 presentation keeps real thickness visible while
            // preserving the split-monolith silhouette from the front.
            eulerRotation: Qt.vector3d(
                -4.5 + root.microDrift * 0.55 * root.motionGate,
                -11.5 + root.drift * 1.45 * root.motionGate
                + root.executionFlow * 2.8,
                -2.6 + root.executionFlow * 1.5
                + root.disorder * Math.sin(root.phase * 3.2) * 3.6
            )

            scale: Qt.vector3d(
                root.stopped ? 0.86 : 1.01 + root.slowPulse * 0.004,
                root.stopped ? 0.86 : 1.01 + root.slowPulse * 0.004,
                root.stopped ? 0.86 : 1.01 + root.slowPulse * 0.004
            )

            // ---------------------------------------------------------------
            // LEFT COGNITION MASS
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: shellA
                source: Qt.resolvedUrl("../assets/ev_core_r10_a.glb")
                position: Qt.vector3d(
                    -root.openness * 11
                    - root.executionFlow * 3
                    + root.disorder * Math.sin(root.phase * 4.0) * 5,
                    root.openness * 3 + root.successLift * 2,
                    -root.planningDepth * 7
                )
                eulerRotation: Qt.vector3d(
                    root.planningDepth * 1.2,
                    -root.openness * 4.2,
                    -root.openness * 1.2
                    + root.disorder * Math.sin(root.phase * 4.6) * 4.2
                )
            }

            RuntimeLoader {
                id: shellC
                source: Qt.resolvedUrl("../assets/ev_core_r10_c.glb")
                position: Qt.vector3d(
                    -root.openness * 10
                    - root.executionFlow * 5,
                    -root.openness * 3 - root.successLift * 2,
                    -root.planningDepth * 4
                    + root.disorder * Math.cos(root.phase * 3.9) * 4
                )
                eulerRotation: Qt.vector3d(
                    -root.planningDepth * 1.1,
                    -root.openness * 3.5,
                    root.executionFlow * -1.6
                    + root.disorder * Math.sin(root.phase * 4.2) * 4.4
                )
            }

            // ---------------------------------------------------------------
            // RIGHT COGNITION MASS
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: shellB
                source: Qt.resolvedUrl("../assets/ev_core_r10_b.glb")
                position: Qt.vector3d(
                    root.openness * 12
                    + root.executionFlow * 8,
                    root.openness * 4 + root.successLift * 2,
                    root.executionFlow * 7 - root.planningDepth * 6
                )
                eulerRotation: Qt.vector3d(
                    root.planningDepth * -1.0,
                    root.openness * 4.5 - root.executionFlow * 2.5,
                    root.executionFlow * 1.4
                    + root.disorder * Math.cos(root.phase * 4.1) * 4.0
                )
            }

            RuntimeLoader {
                id: shellD
                source: Qt.resolvedUrl("../assets/ev_core_r10_d.glb")
                position: Qt.vector3d(
                    root.openness * 11
                    + root.executionFlow * 7,
                    -root.openness * 4 - root.successLift * 2,
                    root.executionFlow * 11
                    + root.disorder * Math.sin(root.phase * 3.7) * 4
                )
                eulerRotation: Qt.vector3d(
                    root.planningDepth * 1.0,
                    root.openness * 3.8 - root.executionFlow * 3.2,
                    root.executionFlow * 2.0
                    + root.disorder * Math.sin(root.phase * 4.4) * 4.6
                )
            }

            // ---------------------------------------------------------------
            // INSET INTELLIGENCE PLATES
            // These sit on the main masses and move at a different rate,
            // giving planning/execution real layered parallax.
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: insetE
                source: Qt.resolvedUrl("../assets/ev_core_r10_e.glb")
                position: Qt.vector3d(
                    -root.openness * 12,
                    root.planningDepth * 3,
                    root.planningDepth * 9 + root.verificationFocus * 4
                )
                eulerRotation: Qt.vector3d(
                    0,
                    -root.openness * 5.5,
                    root.planningDepth * 1.8
                )
            }

            RuntimeLoader {
                id: insetF
                source: Qt.resolvedUrl("../assets/ev_core_r10_f.glb")
                position: Qt.vector3d(
                    root.openness * 12 + root.executionFlow * 5,
                    -root.planningDepth * 2,
                    root.planningDepth * 11 + root.executionFlow * 6
                )
                eulerRotation: Qt.vector3d(
                    0,
                    root.openness * 5.2 - root.executionFlow * 2.0,
                    -root.executionFlow * 2.2
                )
            }

            // ---------------------------------------------------------------
            // COGNITION SHARD — authored dark carrier inside the fissure.
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: cognitionShard
                source: Qt.resolvedUrl("../assets/ev_core_r10_shard.glb")
                position: Qt.vector3d(
                    root.executionFlow * 6,
                    root.successLift * 6,
                    38 + root.planningDepth * 10
                )
                eulerRotation: Qt.vector3d(
                    -7 + root.drift * 1.2,
                    16 + root.phase * 5.2,
                    4 + root.executionFlow * 3.0
                )
                scale: Qt.vector3d(
                    root.stopped ? 0.52 : 0.96 + root.pulse * 0.06,
                    root.stopped ? 0.52 : 0.96 + root.pulse * 0.06,
                    root.stopped ? 0.52 : 0.96 + root.pulse * 0.06
                )
            }

            // ---------------------------------------------------------------
            // INTERNAL LOGIC FISSURE
            // Three sparse emissive elements. No rings, orbits, or decorative
            // HUD geometry. Their relative motion makes the intelligence feel
            // active inside the shell rather than painted on top of it.
            // ---------------------------------------------------------------
            Model {
                id: cognitionPrism
                source: "#Cube"
                materials: [signalMaterial]
                position: Qt.vector3d(
                    root.executionFlow * 5,
                    2 + root.successLift * 6,
                    56 + root.planningDepth * 8
                )
                eulerRotation: Qt.vector3d(
                    36 + root.drift * 2.0,
                    45 + root.phase * 8.0,
                    28 + root.executionFlow * 6.0
                )
                scale: Qt.vector3d(
                    0.050 + root.pulse * 0.004,
                    0.095 + root.pulse * 0.006,
                    0.028 + root.pulse * 0.003
                )
            }

            Model {
                id: logicRailUpper
                source: "#Cube"
                materials: [secondarySignalMaterial]
                position: Qt.vector3d(
                    -8 - root.openness * 2,
                    38 + root.verificationFocus * root.scanWave * 16,
                    45 + root.planningDepth * 5
                )
                eulerRotation: Qt.vector3d(5, -12, -16)
                scale: Qt.vector3d(
                    0.015,
                    0.245 + (root.listening ? 0.035 : 0.0),
                    0.012
                )
            }

            Model {
                id: logicRailLower
                source: "#Cube"
                materials: [secondarySignalMaterial]
                position: Qt.vector3d(
                    10 + root.executionFlow * 4,
                    -34 + root.verificationFocus * root.scanWave * 18,
                    47 + root.executionFlow * 5
                )
                eulerRotation: Qt.vector3d(-4, 10, 13)
                scale: Qt.vector3d(
                    0.014,
                    0.220 + (root.executing ? 0.045 : 0.0),
                    0.011
                )
            }

            // Sparse cognition nodes establish scale without becoming telemetry.
            Model {
                geometry: SphereGeometry { radius: 1.30; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(-18, 64, 38)
                scale: Qt.vector3d(0.62 + root.pulse * 0.12,
                                   0.62 + root.pulse * 0.12,
                                   0.62 + root.pulse * 0.12)
            }

            Model {
                geometry: SphereGeometry { radius: 1.05; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(20, 53, 34)
                scale: Qt.vector3d(0.54 + root.slowPulse * 0.11,
                                   0.54 + root.slowPulse * 0.11,
                                   0.54 + root.slowPulse * 0.11)
            }

            Model {
                geometry: SphereGeometry { radius: 1.18; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(17, -59, 37)
                scale: Qt.vector3d(0.58 + root.pulse * 0.12,
                                   0.58 + root.pulse * 0.12,
                                   0.58 + root.pulse * 0.12)
            }

            Model {
                geometry: SphereGeometry { radius: 0.90; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(-16, -72, 29)
                scale: Qt.vector3d(0.50 + root.slowPulse * 0.10,
                                   0.50 + root.slowPulse * 0.10,
                                   0.50 + root.slowPulse * 0.10)
            }
        }
    }
}
