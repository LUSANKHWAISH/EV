import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — AUTHORED SHELL R9
// ============================================================================
//
// R9 stops trying to sculpt the flagship core from QML-generated ribbons.
// The graphite shell is now a set of authored GLB membrane assets with real
// closed thickness, camber, overlap, and 3D volume.
//
// Design rules:
// - tall asymmetric intelligence artifact, not a circular emblem
// - no eye/lens/ring/orbit topology
// - broad shell plates form one split cocoon around open cognition space
// - state colour comes from internal lighting, not painted shell colour
// - individual membrane assets can move independently by state
// - fixed world coordinates; viewport resize never regenerates geometry
// ============================================================================

Item {
    id: root

    readonly property real cameraDistance: 410.0

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
        root.executing ? 1650 :
        root.speaking ? 1900 :
        root.failed ? 1300 :
        root.verifying ? 2200 :
        root.planning ? 3000 :
        root.listening ? 3300 :
        root.recovering ? 3700 :
        root.awaiting ? 6000 :
        root.successful ? 2600 :
        5000

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.52) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.48)
    readonly property real microDrift: Math.sin(root.phase * 0.83)

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
        root.speaking ? 0.64 :
        root.successful ? 0.24 :
        root.failed ? -0.12 :
        root.stopped ? -0.42 :
        0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.20 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 430; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 330; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 760; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 460; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.88

    readonly property real emissionBase:
        root.stopped ? 0.03 :
        root.listening ? 0.72 :
        root.planning ? 0.58 :
        root.executing ? 0.80 :
        root.verifying ? 0.84 :
        root.awaiting ? 0.42 :
        root.speaking ? 0.72 :
        root.successful ? 0.90 :
        root.failed ? 0.76 :
        root.recovering ? 0.62 :
        0.40

    readonly property real emissionIntensity:
        root.emissionBase * (0.88 + root.pulse * 0.12)

    // ------------------------------------------------------------------------
    // INTERNAL COGNITION MATERIAL
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: signalMaterial
        baseColor: root.stateTone
        metalness: 0.12
        roughness: 0.20
        clearcoatAmount: 0.35
        clearcoatRoughnessAmount: 0.12
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity * 1.55,
            root.stateTone.g * root.emissionIntensity * 1.55,
            root.stateTone.b * root.emissionIntensity * 1.55
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
            glowStrength: 0.30
            glowIntensity: 0.42
            glowBloom: 0.055
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(0, 0, 0)
            fieldOfView: 39
            clipNear: 1.0
            clipFar: 2000.0
        }

        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-32, 38, -10)
            color: "#f5f7fa"
            brightness: 3.10
            ambientColor: "#17212b"
            castsShadow: false
        }

        DirectionalLight {
            id: fillLight
            eulerRotation: Qt.vector3d(24, -52, 14)
            color: "#9fb0c2"
            brightness: 1.35
            ambientColor: "#0d141c"
            castsShadow: false
        }

        PointLight {
            id: rimLight
            position: Qt.vector3d(-135, 105, 145)
            color: "#c8dcf2"
            brightness: 2.35
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000019
        }

        PointLight {
            id: lowerRim
            position: Qt.vector3d(112, -122, 90)
            color: "#768aa0"
            brightness: 1.05
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000022
        }

        PointLight {
            id: cognitionLight
            position: Qt.vector3d(
                8 + root.executionFlow * 18,
                root.verificationFocus * Math.sin(root.phase * 1.5) * 74,
                48 + root.planningDepth * 24
            )
            color: root.stateTone
            brightness: root.stopped
                ? 0.03
                : 0.80 + root.energy * 0.92 + root.verificationFocus * 0.46
            constantFade: 1.0
            linearFade: 0.0036
            quadraticFade: 0.000020
        }

        PointLight {
            id: rearCognitionLight
            position: Qt.vector3d(
                -26 - root.openness * 10,
                -18 + root.successLift * 12,
                -54 - root.planningDepth * 14
            )
            color: root.stateTone
            brightness: root.stopped ? 0.02 : 0.42 + root.energy * 0.55
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000024
        }

        Node {
            id: artifactRoot

            position: Qt.vector3d(0, -2 + root.successLift * 5, 0)

            eulerRotation: Qt.vector3d(
                -4.0 + root.microDrift * 0.8 * root.motionGate,
                -14.0 + root.drift * 2.0 * root.motionGate
                + root.executionFlow * 3.0,
                -4.5 + root.executionFlow * 2.2
                + root.disorder * Math.sin(root.phase * 3.2) * 4.5
            )

            scale: Qt.vector3d(
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.004,
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.004,
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.004
            )

            // ---------------------------------------------------------------
            // AUTHORED GRAPHITE MEMBRANES
            // Each GLB is independently transformable for real state motion.
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: membraneA
                source: Qt.resolvedUrl("../assets/ev_core_r9_a.glb")
                position: Qt.vector3d(
                    -root.openness * 7
                    + root.disorder * Math.sin(root.phase * 4.0) * 6,
                    root.openness * 5 + root.successLift * 3,
                    root.openness * 4
                )
                eulerRotation: Qt.vector3d(
                    0,
                    -root.openness * 2.8,
                    -root.openness * 1.6
                    + root.disorder * Math.sin(root.phase * 4.6) * 5
                )
            }

            RuntimeLoader {
                id: membraneB
                source: Qt.resolvedUrl("../assets/ev_core_r9_b.glb")
                position: Qt.vector3d(
                    root.openness * 8,
                    root.openness * 2,
                    -root.planningDepth * 8
                )
                eulerRotation: Qt.vector3d(
                    root.planningDepth * 1.8,
                    root.openness * 3.0 - root.executionFlow * 3.5,
                    root.disorder * Math.cos(root.phase * 4.1) * 5
                )
            }

            RuntimeLoader {
                id: membraneC
                source: Qt.resolvedUrl("../assets/ev_core_r9_c.glb")
                position: Qt.vector3d(
                    -root.openness * 6,
                    root.openness * 3 + root.planningDepth * 4,
                    -root.planningDepth * 10
                )
                eulerRotation: Qt.vector3d(
                    -root.planningDepth * 2.0,
                    root.planningDepth * 3.0,
                    -root.disorder * Math.sin(root.phase * 3.8) * 4.5
                )
            }

            RuntimeLoader {
                id: membraneD
                source: Qt.resolvedUrl("../assets/ev_core_r9_d.glb")
                position: Qt.vector3d(
                    root.openness * 5,
                    -root.openness * 5,
                    -root.openness * 3
                )
                eulerRotation: Qt.vector3d(
                    0,
                    root.openness * 2.4,
                    root.executionFlow * 2.8
                    + root.disorder * Math.sin(root.phase * 4.3) * 4.0
                )
            }

            RuntimeLoader {
                id: membraneE
                source: Qt.resolvedUrl("../assets/ev_core_r9_e.glb")
                position: Qt.vector3d(
                    root.executionFlow * 8,
                    -root.openness * 4,
                    8 + root.planningDepth * 16 + root.verificationFocus * 7
                )
                eulerRotation: Qt.vector3d(
                    root.planningDepth * 2.0,
                    -root.executionFlow * 4.0,
                    root.openness * 2.2
                )
            }

            RuntimeLoader {
                id: cognitionShard
                source: Qt.resolvedUrl("../assets/ev_core_r9_shard.glb")
                position: Qt.vector3d(
                    root.executionFlow * 8,
                    root.listening ? 3 : root.successLift * 7,
                    18 + root.planningDepth * 8
                )
                eulerRotation: Qt.vector3d(
                    -8 + root.drift * 1.8,
                    18 + root.phase * 7.0,
                    5 + root.executionFlow * 4.0
                )
                scale: Qt.vector3d(
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.08,
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.08,
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.08
                )
            }

            // ---------------------------------------------------------------
            // SPARSE COGNITION FIELD — no arcs, rings, or orbital geometry.
            // ---------------------------------------------------------------
            Model {
                geometry: SphereGeometry { radius: 1.55; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(-28, 36, 36)
                scale: Qt.vector3d(0.72 + root.pulse * 0.16,
                                   0.72 + root.pulse * 0.16,
                                   0.72 + root.pulse * 0.16)
            }

            Model {
                geometry: SphereGeometry { radius: 1.10; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(32, 52, 24)
                scale: Qt.vector3d(0.58 + root.slowPulse * 0.14,
                                   0.58 + root.slowPulse * 0.14,
                                   0.58 + root.slowPulse * 0.14)
            }

            Model {
                geometry: SphereGeometry { radius: 1.25; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(22, -42, 34)
                scale: Qt.vector3d(0.62 + root.pulse * 0.14,
                                   0.62 + root.pulse * 0.14,
                                   0.62 + root.pulse * 0.14)
            }

            Model {
                geometry: SphereGeometry { radius: 0.95; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(-34, -55, 20)
                scale: Qt.vector3d(0.55 + root.slowPulse * 0.14,
                                   0.55 + root.slowPulse * 0.14,
                                   0.55 + root.slowPulse * 0.14)
            }

            Model {
                geometry: SphereGeometry { radius: 0.85; segments: 8; rings: 6 }
                materials: [signalMaterial]
                position: Qt.vector3d(7, 78, 12)
                scale: Qt.vector3d(0.52 + root.pulse * 0.12,
                                   0.52 + root.pulse * 0.12,
                                   0.52 + root.pulse * 0.12)
            }
        }
    }
}
