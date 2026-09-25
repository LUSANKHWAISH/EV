import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R10 DEPTH / COLOR / PRECISION REVISION
// ============================================================================
// Purpose:
// - keep the engineered-singularity direction
// - remove the rejected straight computation bridge completely
// - make real Z depth obvious at normal GUI size
// - use layered authored shells, a recessed cognition tunnel, front/mid/rear
//   energy layers, curved energy crescents, and precise state motion
// - preserve the public state interface used by EVFlagshipStage
// ============================================================================

Item {
    id: root

    readonly property real cameraDistance: 405.0

    // ------------------------------------------------------------------------
    // PUBLIC INTERFACE
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
    // MOTION CLOCK
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1380 :
        root.failed ? 1120 :
        root.verifying ? 1760 :
        root.speaking ? 1680 :
        root.planning ? 2600 :
        root.listening ? 3000 :
        root.recovering ? 3300 :
        root.awaiting ? 6500 :
        root.successful ? 2200 :
        4550

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.46) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.44)
    readonly property real counterDrift: Math.cos(root.phase * 0.39)
    readonly property real scanWave: Math.sin(root.phase * 1.55)

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
        root.speaking ? 0.52 :
        root.successful ? 0.18 :
        root.failed ? -0.08 :
        root.stopped ? -0.22 : 0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.20 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 390; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 470; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 760; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 430; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.94

    readonly property real stateEmission:
        root.stopped ? 0.02 :
        root.successful ? 1.00 :
        root.verifying ? 0.96 :
        root.executing ? 0.94 :
        root.failed ? 0.90 :
        root.listening ? 0.86 :
        root.speaking ? 0.82 :
        root.planning ? 0.76 :
        root.recovering ? 0.74 :
        root.awaiting ? 0.44 : 0.58

    // ------------------------------------------------------------------------
    // DYNAMIC MATERIALS
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: stateSignalMaterial
        baseColor: root.stateTone
        metalness: 0.10
        roughness: 0.12
        clearcoatAmount: 0.42
        clearcoatRoughnessAmount: 0.06
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.stateEmission * 2.4,
            root.stateTone.g * root.stateEmission * 2.4,
            root.stateTone.b * root.stateEmission * 2.4
        )
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: deepVoidMaterial
        baseColor: "#010205"
        metalness: 0.02
        roughness: 1.0
        emissiveFactor: Qt.vector3d(0.0, 0.0, 0.0)
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
            glowStrength: 0.54 + root.energy * 0.06
            glowIntensity: 0.76 + root.energy * 0.10
            glowBloom: 0.09
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 2, root.cameraDistance)
            eulerRotation: Qt.vector3d(-1.5, 0, 0)
            fieldOfView: 42
            clipNear: 1.0
            clipFar: 2000.0
        }

        // Main key: high enough to show shell steps and top bevel lands.
        DirectionalLight {
            eulerRotation: Qt.vector3d(-32, 38, -12)
            color: "#f7fbff"
            brightness: 4.6
            ambientColor: "#1c2938"
            castsShadow: false
        }

        // Side fill separates front and rear shell planes.
        DirectionalLight {
            eulerRotation: Qt.vector3d(28, -51, 18)
            color: "#7f9fbe"
            brightness: 1.75
            ambientColor: "#0b131d"
            castsShadow: false
        }

        // Cool front-left rim.
        PointLight {
            position: Qt.vector3d(-128, 112, 188)
            color: "#9dd8ff"
            brightness: 3.05
            constantFade: 1.0
            linearFade: 0.0030
            quadraticFade: 0.000015
        }

        // Warm lower-right rim.
        PointLight {
            position: Qt.vector3d(138, -100, 166)
            color: "#ff9248"
            brightness: 2.55
            constantFade: 1.0
            linearFade: 0.0032
            quadraticFade: 0.000016
        }

        // Neutral rear light reveals the recessed tunnel and back shells.
        PointLight {
            position: Qt.vector3d(0, 34, -118)
            color: "#7194b6"
            brightness: 1.30
            constantFade: 1.0
            linearFade: 0.0042
            quadraticFade: 0.000022
        }

        // E.V. state energy stays inside the cognition chamber.
        PointLight {
            id: stateCoreLight
            position: Qt.vector3d(
                root.executionFlow * 16,
                root.verificationFocus * root.scanWave * 44,
                72 + root.planningDepth * 12
            )
            color: root.stateTone
            brightness: root.stopped ? 0.01 : 0.88 + root.energy * 1.10
            constantFade: 1.0
            linearFade: 0.0029
            quadraticFade: 0.000014
        }

        Node {
            id: artifactRoot
            position: Qt.vector3d(0, -1 + root.successLift * 3, 0)

            // Stronger 3/4 presentation is deliberate. R10S looked flat because
            // it was almost front-on. This angle exposes the 70+ world-unit Z stack.
            eulerRotation: Qt.vector3d(
                -6.5 + root.counterDrift * 0.40 * root.motionGate,
                -16.5 + root.drift * 1.25 * root.motionGate
                    + root.executionFlow * 2.2,
                -2.2 + root.planningDepth * root.drift * 0.70 * root.motionGate
                    + root.disorder * Math.sin(root.phase * 3.7) * 2.7
            )

            scale: Qt.vector3d(
                root.stopped ? 0.90 : 1.045 + root.slowPulse * 0.006 + root.successLift * 0.014,
                root.stopped ? 0.90 : 1.045 + root.slowPulse * 0.006 + root.successLift * 0.014,
                root.stopped ? 0.90 : 1.045 + root.slowPulse * 0.006 + root.successLift * 0.014
            )

            // ---------------------------------------------------------------
            // DEEP COGNITION TUNNEL
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: cognitionTunnel
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_void_tunnel.glb")
                position: Qt.vector3d(0, 0, -root.planningDepth * 7)
                scale: Qt.vector3d(
                    1.0 + root.openness * 0.014,
                    1.0 + root.openness * 0.014,
                    1.0
                )
            }

            // ---------------------------------------------------------------
            // OUTER SHELLS — four independent depth planes
            // ---------------------------------------------------------------
            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_outer_nw.glb")
                position: Qt.vector3d(
                    -root.openness * 7,
                    root.openness * 5,
                    root.openness * 4 - root.planningDepth * 8
                        + root.disorder * Math.sin(root.phase * 4.1) * 5
                )
                eulerRotation: Qt.vector3d(
                    -root.openness * 1.4,
                    -root.openness * 3.2,
                    -root.planningDepth * 2.5
                        + root.disorder * Math.sin(root.phase * 4.0) * 4.0
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_outer_ne.glb")
                position: Qt.vector3d(
                    root.openness * 8 + root.executionFlow * 4,
                    root.openness * 5,
                    -root.openness * 5 - root.planningDepth * 3
                        + root.executionFlow * 8
                        + root.disorder * Math.cos(root.phase * 4.2) * 5
                )
                eulerRotation: Qt.vector3d(
                    root.openness * 1.2,
                    root.openness * 3.6 - root.executionFlow * 1.5,
                    root.planningDepth * 3.0
                        + root.executionFlow * 1.5
                        + root.disorder * Math.cos(root.phase * 4.3) * 4.2
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_outer_sw.glb")
                position: Qt.vector3d(
                    -root.openness * 7,
                    -root.openness * 6 - root.successLift * 2,
                    -root.openness * 4 - root.planningDepth * 3
                        - root.executionFlow * 4
                        + root.disorder * Math.sin(root.phase * 4.5) * 5
                )
                eulerRotation: Qt.vector3d(
                    -root.openness * 1.0,
                    -root.openness * 2.8,
                    root.planningDepth * 2.2
                        - root.executionFlow * 1.0
                        + root.disorder * Math.sin(root.phase * 4.5) * 4.3
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_outer_se.glb")
                position: Qt.vector3d(
                    root.openness * 8 + root.executionFlow * 8,
                    -root.openness * 6 - root.successLift * 2,
                    root.openness * 5 + root.executionFlow * 12
                        + root.disorder * Math.cos(root.phase * 4.0) * 5
                )
                eulerRotation: Qt.vector3d(
                    root.openness * -1.2,
                    root.openness * 3.0 - root.executionFlow * 2.2,
                    -root.planningDepth * 2.8
                        + root.executionFlow * 2.0
                        + root.disorder * Math.cos(root.phase * 4.0) * 4.5
                )
            }

            // ---------------------------------------------------------------
            // MID SHELLS — move opposite the outer mass in PLANNING
            // ---------------------------------------------------------------
            Node {
                id: midShellRoot
                position: Qt.vector3d(0, 0, root.planningDepth * 8)
                eulerRotation.z: -root.planningDepth * root.drift * 1.3 * root.motionGate

                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_mid_nw.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_mid_ne.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_mid_sw.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_mid_se.glb") }
            }

            // ---------------------------------------------------------------
            // INNER COLLAR + DEPTH VANES
            // ---------------------------------------------------------------
            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_inner_collar.glb")
                position: Qt.vector3d(0, 0, root.planningDepth * 10 + root.executionFlow * 3)
                eulerRotation: Qt.vector3d(
                    0,
                    root.executionFlow * -1.5,
                    root.planningDepth * 3.2 + root.drift * 0.34 * root.motionGate
                )
                scale: Qt.vector3d(
                    1.0 + root.openness * 0.024,
                    1.0 + root.openness * 0.024,
                    1.0
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_depth_vanes.glb")
                eulerRotation.z: root.planningDepth * root.counterDrift * 0.9 * root.motionGate
                position: Qt.vector3d(0, 0, root.executionFlow * 2)
            }

            // ---------------------------------------------------------------
            // ENERGY FIELD — FRONT / MID / REAR DEPTH LAYERS
            // No straight bridge. All energy geometry is curved or segmented.
            // ---------------------------------------------------------------
            Node {
                id: frontHaloRoot
                position: Qt.vector3d(0, 0, root.planningDepth * 4 + root.successLift * 2)
                eulerRotation.z:
                    root.planningDepth * root.drift * 1.4 * root.motionGate
                    + root.verificationFocus * root.scanWave * 0.9
                scale: Qt.vector3d(
                    1.0 + root.openness * 0.045 + root.successLift * 0.026,
                    1.0 + root.openness * 0.045 + root.successLift * 0.026,
                    1.0
                )

                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_cool_front.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_white_front.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_warm_front.glb") }
            }

            Node {
                id: rearHaloRoot
                position: Qt.vector3d(0, 0, -root.planningDepth * 5)
                eulerRotation.z: -root.planningDepth * root.counterDrift * 1.1 * root.motionGate

                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_cool_mid.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_white_rear.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10dp_halo_amber_rear.glb") }
            }

            // Two curved crescents echo the reference's energy flow without a
            // giant diagonal bar crossing the core.
            RuntimeLoader {
                id: curvedEnergyStreams
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_energy_streams.glb")
                position: Qt.vector3d(root.executionFlow * 5, 0, root.executionFlow * 5)
                eulerRotation: Qt.vector3d(
                    0,
                    root.executionFlow * -1.8,
                    root.executionFlow * 1.2
                        + root.disorder * Math.sin(root.phase * 4.6) * 1.8
                )
                scale: Qt.vector3d(
                    1.0 + root.executionFlow * 0.018,
                    1.0 + root.executionFlow * 0.018,
                    1.0
                )
            }

            // ---------------------------------------------------------------
            // COGNITION POINTS + STATE ENERGY
            // ---------------------------------------------------------------
            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10dp_nodes.glb")
                position: Qt.vector3d(
                    root.executionFlow * 2,
                    root.verificationFocus * root.scanWave * 3,
                    root.planningDepth * 4
                )
                scale: Qt.vector3d(
                    1.0 + root.pulse * 0.035,
                    1.0 + root.pulse * 0.035,
                    1.0 + root.pulse * 0.035
                )
            }

            // Small state-colored points orbit at different Z planes.
            // These replace the old long straight state trace.
            Model {
                geometry: SphereGeometry { radius: 2.0; segments: 10; rings: 8 }
                materials: [stateSignalMaterial]
                position: Qt.vector3d(
                    Math.cos(root.phase) * 34,
                    Math.sin(root.phase) * 22,
                    66 + Math.sin(root.phase * 0.7) * 8
                )
                scale: Qt.vector3d(0.78, 0.78, 0.78)
            }

            Model {
                geometry: SphereGeometry { radius: 1.6; segments: 10; rings: 8 }
                materials: [stateSignalMaterial]
                position: Qt.vector3d(
                    Math.cos(root.phase + 2.1) * 28,
                    Math.sin(root.phase + 2.1) * 31,
                    38 + Math.cos(root.phase * 0.8) * 10
                )
                scale: Qt.vector3d(0.70, 0.70, 0.70)
            }

            Model {
                geometry: SphereGeometry { radius: 1.35; segments: 10; rings: 8 }
                materials: [stateSignalMaterial]
                position: Qt.vector3d(
                    Math.cos(root.phase + 4.2) * 22,
                    Math.sin(root.phase + 4.2) * 26,
                    12 + Math.sin(root.phase * 0.9) * 8
                )
                scale: Qt.vector3d(0.64, 0.64, 0.64)
            }

            // VERIFYING scan beacon traverses depth as well as height.
            Model {
                geometry: SphereGeometry { radius: 2.2; segments: 10; rings: 8 }
                materials: [stateSignalMaterial]
                visible: root.verificationFocus > 0.02
                position: Qt.vector3d(
                    root.scanWave * 8,
                    root.scanWave * 56,
                    50 + root.scanWave * 20
                )
                scale: Qt.vector3d(
                    0.74 + root.pulse * 0.15,
                    0.74 + root.pulse * 0.15,
                    0.74 + root.pulse * 0.15
                )
            }

            // Explicit black aperture face keeps the center visually deep.
            Model {
                source: "#Sphere"
                materials: [deepVoidMaterial]
                position: Qt.vector3d(0, 0, 34)
                scale: Qt.vector3d(0.50, 0.50, 0.15)
                opacity: root.stopped ? 0.82 : 0.38
            }
        }
    }
}
