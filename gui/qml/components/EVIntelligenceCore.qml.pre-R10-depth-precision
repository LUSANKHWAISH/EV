import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R10 ENGINEERED SINGULARITY
// ============================================================================
// Authored-3D revision of R10 inspired by the user's black-hole reference.
// The astrophysical idea is translated into an engineered cognition aperture:
// broken graphite containment arcs + a dark central void + split cool/warm
// energy halo + a diagonal computation/accretion bridge.
//
// Explicitly NOT a literal space scene:
// - no stars / planets / nebula background
// - no perfect HUD ring
// - no decorative telemetry geometry
// - state motion is physical, sparse, and tied to cognition behavior
// ============================================================================

Item {
    id: root

    readonly property real cameraDistance: 430.0

    // ------------------------------------------------------------------------
    // PUBLIC INTERFACE — preserved for EVFlagshipStage
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
        root.executing ? 1420 :
        root.failed ? 1160 :
        root.verifying ? 1880 :
        root.speaking ? 1780 :
        root.planning ? 2800 :
        root.listening ? 3150 :
        root.recovering ? 3500 :
        root.awaiting ? 6400 :
        root.successful ? 2300 :
        4700

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.47) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.46)
    readonly property real counterDrift: Math.cos(root.phase * 0.42)
    readonly property real scanWave: Math.sin(root.phase * 1.45)

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
        root.speaking ? 0.48 :
        root.successful ? 0.20 :
        root.failed ? -0.10 :
        root.stopped ? -0.30 : 0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.24 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 390; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 470; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 270; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 760; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 430; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.93

    readonly property real stateEmission:
        root.stopped ? 0.02 :
        root.successful ? 1.00 :
        root.verifying ? 0.94 :
        root.executing ? 0.91 :
        root.failed ? 0.88 :
        root.listening ? 0.82 :
        root.speaking ? 0.78 :
        root.planning ? 0.68 :
        root.recovering ? 0.72 :
        root.awaiting ? 0.42 : 0.52

    // Dynamic state accents. The authored halo keeps the cool/warm singularity
    // identity while this material makes E.V.'s actual state readable.
    PrincipledMaterial {
        id: stateSignalMaterial
        baseColor: root.stateTone
        metalness: 0.15
        roughness: 0.14
        clearcoatAmount: 0.36
        clearcoatRoughnessAmount: 0.08
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.stateEmission * 2.2,
            root.stateTone.g * root.stateEmission * 2.2,
            root.stateTone.b * root.stateEmission * 2.2
        )
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: deepVoidMaterial
        baseColor: "#010204"
        metalness: 0.05
        roughness: 0.98
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
            glowStrength: 0.46 + root.energy * 0.05
            glowIntensity: 0.68 + root.energy * 0.08
            glowBloom: 0.075
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(-1.8, 0, 0)
            fieldOfView: 40
            clipNear: 1.0
            clipFar: 2000.0
        }

        // Hard neutral key for graphite plate readability.
        DirectionalLight {
            eulerRotation: Qt.vector3d(-28, 32, -9)
            color: "#f5f8fc"
            brightness: 3.75
            ambientColor: "#17222e"
            castsShadow: false
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(30, -46, 12)
            color: "#93a9c2"
            brightness: 1.55
            ambientColor: "#0a1119"
            castsShadow: false
        }

        // Cool upper-left / warm lower-right lights reinforce the authored
        // singularity split without turning the shell itself neon.
        PointLight {
            position: Qt.vector3d(-95, 102, 142)
            color: "#b8dcff"
            brightness: 2.40
            constantFade: 1.0
            linearFade: 0.0035
            quadraticFade: 0.000018
        }

        PointLight {
            position: Qt.vector3d(108, -82, 126)
            color: "#ff9a52"
            brightness: 1.85
            constantFade: 1.0
            linearFade: 0.0038
            quadraticFade: 0.000020
        }

        // E.V. state color remains concentrated in the cognition aperture.
        PointLight {
            id: stateCoreLight
            position: Qt.vector3d(
                root.executionFlow * 18,
                root.verificationFocus * root.scanWave * 46,
                62 + root.planningDepth * 12
            )
            color: root.stateTone
            brightness: root.stopped ? 0.01 : 0.62 + root.energy * 0.95
            constantFade: 1.0
            linearFade: 0.0032
            quadraticFade: 0.000016
        }

        PointLight {
            id: bridgeStateLight
            position: Qt.vector3d(
                root.executionFlow * 42,
                root.executionFlow * 10,
                78
            )
            color: root.stateTone
            brightness: root.stopped ? 0.01 : 0.30 + root.energy * 0.50
            constantFade: 1.0
            linearFade: 0.0040
            quadraticFade: 0.000021
        }

        Node {
            id: artifactRoot
            position: Qt.vector3d(0, -1 + root.successLift * 3, 0)

            // Almost-front presentation like the reference, but slight 3/4
            // yaw exposes real plate thickness and layered containment depth.
            eulerRotation: Qt.vector3d(
                -3.2 + root.counterDrift * 0.35 * root.motionGate,
                -7.0 + root.drift * 1.15 * root.motionGate
                    + root.executionFlow * 2.0,
                -0.8 + root.planningDepth * root.drift * 0.55 * root.motionGate
                    + root.disorder * Math.sin(root.phase * 3.6) * 2.6
            )

            scale: Qt.vector3d(
                root.stopped ? 0.88 : 1.02 + root.slowPulse * 0.004 + root.successLift * 0.012,
                root.stopped ? 0.88 : 1.02 + root.slowPulse * 0.004 + root.successLift * 0.012,
                root.stopped ? 0.88 : 1.02 + root.slowPulse * 0.004 + root.successLift * 0.012
            )

            // ---------------------------------------------------------------
            // COGNITION VOID / REAR COLLAR
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: cognitionVoid
                source: Qt.resolvedUrl("../assets/ev_core_r10s_void.glb")
                position: Qt.vector3d(0, 0, -root.planningDepth * 5)
                scale: Qt.vector3d(
                    1.0 + root.openness * 0.018,
                    1.0 + root.openness * 0.018,
                    1.0
                )
            }

            // ---------------------------------------------------------------
            // OUTER CONTAINMENT QUADRANTS
            // LISTENING opens the aperture physically. PLANNING produces a
            // controlled counter-rotation. FAILURE breaks alignment.
            // ---------------------------------------------------------------
            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_nw.glb")
                position: Qt.vector3d(-root.openness * 6, root.openness * 5, -root.planningDepth * 5)
                eulerRotation: Qt.vector3d(
                    -root.openness * 1.5,
                    -root.openness * 2.4,
                    -root.planningDepth * 2.2
                        + root.disorder * Math.sin(root.phase * 4.1) * 4.0
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_ne.glb")
                position: Qt.vector3d(root.openness * 7 + root.executionFlow * 4,
                                      root.openness * 5,
                                      root.executionFlow * 5 - root.planningDepth * 3)
                eulerRotation: Qt.vector3d(
                    root.openness * 1.3,
                    root.openness * 2.8,
                    root.planningDepth * 2.8
                        + root.executionFlow * 1.4
                        + root.disorder * Math.cos(root.phase * 4.3) * 4.2
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_sw.glb")
                position: Qt.vector3d(-root.openness * 6,
                                      -root.openness * 5 - root.successLift * 2,
                                      root.executionFlow * -3 - root.planningDepth * 2)
                eulerRotation: Qt.vector3d(
                    root.openness * -1.2,
                    root.openness * -2.1,
                    root.planningDepth * 2.0
                        - root.executionFlow * 1.2
                        + root.disorder * Math.sin(root.phase * 4.5) * 4.4
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_se.glb")
                position: Qt.vector3d(root.openness * 7 + root.executionFlow * 7,
                                      -root.openness * 5 - root.successLift * 2,
                                      root.executionFlow * 8)
                eulerRotation: Qt.vector3d(
                    root.openness * -1.3,
                    root.openness * 2.3 - root.executionFlow * 1.5,
                    -root.planningDepth * 2.5
                        + root.executionFlow * 1.8
                        + root.disorder * Math.cos(root.phase * 4.0) * 4.5
                )
            }

            // ---------------------------------------------------------------
            // INNER CONTAINMENT COLLAR
            // Independent motion gives the aperture layered mechanical depth.
            // ---------------------------------------------------------------
            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_inner_l.glb")
                position: Qt.vector3d(-root.openness * 3, 0, root.planningDepth * 5)
                eulerRotation.z: root.planningDepth * 3.0 + root.drift * 0.25 * root.motionGate
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_inner_r.glb")
                position: Qt.vector3d(root.openness * 3 + root.executionFlow * 2, 0,
                                      root.planningDepth * 7 + root.executionFlow * 3)
                eulerRotation.z: -root.planningDepth * 3.4 - root.drift * 0.22 * root.motionGate
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_inner_b.glb")
                position: Qt.vector3d(0, -root.openness * 2, root.planningDepth * 4)
                eulerRotation.z: root.planningDepth * 2.1
            }

            RuntimeLoader {
                id: containmentVanes
                source: Qt.resolvedUrl("../assets/ev_core_r10s_vanes.glb")
                eulerRotation.z: root.planningDepth * root.counterDrift * 0.7 * root.motionGate
                scale: Qt.vector3d(
                    1.0 + root.openness * 0.018,
                    1.0 + root.openness * 0.018,
                    1.0
                )
            }

            // ---------------------------------------------------------------
            // SPLIT SINGULARITY HALO
            // Static cool/warm identity, physically breathing with the aperture.
            // ---------------------------------------------------------------
            Node {
                id: haloRoot
                position: Qt.vector3d(0, 0, 2 + root.planningDepth * 5)
                eulerRotation.z:
                    root.planningDepth * root.drift * 1.2 * root.motionGate
                    + root.verificationFocus * root.scanWave * 0.7

                scale: Qt.vector3d(
                    1.0 + root.openness * 0.042 + root.successLift * 0.026,
                    1.0 + root.openness * 0.042 + root.successLift * 0.026,
                    1.0
                )

                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10s_halo_cool_a.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10s_halo_cool_b.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10s_halo_white.glb") }
                RuntimeLoader { source: Qt.resolvedUrl("../assets/ev_core_r10s_halo_warm.glb") }
            }

            // ---------------------------------------------------------------
            // DIAGONAL COMPUTATION / ACCRETION BRIDGE
            // EXECUTING gives it directional tension rather than random spin.
            // ---------------------------------------------------------------
            RuntimeLoader {
                id: computationBridge
                source: Qt.resolvedUrl("../assets/ev_core_r10s_bridge.glb")
                position: Qt.vector3d(root.executionFlow * 8,
                                      root.executionFlow * 2,
                                      root.executionFlow * 7 + root.planningDepth * 3)
                eulerRotation: Qt.vector3d(
                    0,
                    root.executionFlow * -1.2,
                    root.executionFlow * 1.7
                        + root.disorder * Math.sin(root.phase * 4.6) * 2.4
                )
                scale: Qt.vector3d(
                    1.0 + root.executionFlow * 0.018,
                    1.0,
                    1.0
                )
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_r10s_nodes.glb")
                position: Qt.vector3d(root.executionFlow * 2,
                                      root.verificationFocus * root.scanWave * 3,
                                      root.planningDepth * 6)
                scale: Qt.vector3d(
                    1.0 + root.pulse * 0.035,
                    1.0 + root.pulse * 0.035,
                    1.0 + root.pulse * 0.035
                )
            }

            // ---------------------------------------------------------------
            // DYNAMIC E.V. STATE TRACE
            // One restrained state-colored cognition seam. It is intentionally
            // separate from the permanent blue/amber singularity identity.
            // ---------------------------------------------------------------
            Model {
                id: stateTrace
                source: "#Cube"
                materials: [stateSignalMaterial]
                position: Qt.vector3d(
                    root.executionFlow * 10,
                    root.verificationFocus * root.scanWave * 42,
                    61 + root.planningDepth * 8
                )
                eulerRotation: Qt.vector3d(0, 0, 13.5)
                scale: Qt.vector3d(
                    0.29 + root.executionFlow * 0.035,
                    0.010 + root.pulse * 0.002,
                    0.010
                )
            }

            // VERIFYING: a small scan beacon traverses the aperture vertically.
            Model {
                geometry: SphereGeometry { radius: 2.1; segments: 10; rings: 8 }
                materials: [stateSignalMaterial]
                visible: root.verificationFocus > 0.02
                position: Qt.vector3d(
                    0,
                    root.scanWave * 60,
                    72
                )
                scale: Qt.vector3d(
                    0.72 + root.pulse * 0.15,
                    0.72 + root.pulse * 0.15,
                    0.72 + root.pulse * 0.15
                )
            }

            // STOPPED state receives an explicit dark center rather than relying
            // on the halo to disappear completely.
            Model {
                source: "#Sphere"
                materials: [deepVoidMaterial]
                position: Qt.vector3d(0, 0, 38)
                scale: Qt.vector3d(0.54, 0.54, 0.18)
                opacity: root.stopped ? 0.72 : 0.20
            }
        }
    }
}
