import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — FLAGSHIP FORGE
// ============================================================================
// Authored-3D implementation.
//
// Visual identity:
// - deep cognition aperture (not a blue disc)
// - three major graphite containment masses with real thickness/camber
// - recessed titanium precision collar
// - segmented ice/amber event-horizon halo
// - one curved accretion/computation stream that skirts the aperture
// - strong front/mid/rear Z separation and restrained state-colour emission
//
// The body is authored in GLB assets. QML owns camera, lighting, state motion,
// and sparse state signals only. No procedural primary shell geometry lives here.
// ============================================================================

Item {
    id: root

    readonly property real cameraDistance: 455.0

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
    // MOTION CLOCK + STATE SCALARS
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1450 :
        root.failed ? 1180 :
        root.verifying ? 1850 :
        root.speaking ? 1700 :
        root.planning ? 2800 :
        root.listening ? 3100 :
        root.recovering ? 3400 :
        root.awaiting ? 6500 :
        root.successful ? 2250 :
        4800

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.53)
    readonly property real counterDrift: Math.cos(root.phase * 0.41)
    readonly property real scanWave: Math.sin(root.phase * 1.6)

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    property real openness:
        root.listening ? 1.0 :
        root.speaking ? 0.42 :
        root.successful ? 0.20 :
        root.failed ? -0.16 :
        root.stopped ? -0.28 : 0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.25 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 650; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 390; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 480; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 280; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 760; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 430; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.94
    readonly property real stateEmission:
        root.stopped ? 0.02 :
        root.successful ? 1.00 :
        root.verifying ? 0.96 :
        root.executing ? 0.92 :
        root.failed ? 0.90 :
        root.listening ? 0.82 :
        root.speaking ? 0.78 :
        root.planning ? 0.68 :
        root.recovering ? 0.72 :
        root.awaiting ? 0.40 : 0.52

    PrincipledMaterial {
        id: stateSignalMaterial
        baseColor: root.stateTone
        metalness: 0.12
        roughness: 0.13
        clearcoatAmount: 0.30
        clearcoatRoughnessAmount: 0.08
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.stateEmission * 2.4,
            root.stateTone.g * root.stateEmission * 2.4,
            root.stateTone.b * root.stateEmission * 2.4
        )
        cullMode: Material.NoCulling
    }

    View3D {
        anchors.fill: parent

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowStrength: 0.42 + root.energy * 0.06
            glowIntensity: 0.64 + root.energy * 0.10
            glowBloom: 0.065
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(-3.5, 0, 0)
            fieldOfView: 42
            clipNear: 1.0
            clipFar: 2000.0
        }

        // Neutral key: reveals graphite camber and titanium ribs.
        DirectionalLight {
            eulerRotation: Qt.vector3d(-31, 36, -10)
            color: "#f7f9fc"
            brightness: 4.10
            ambientColor: "#151d27"
            castsShadow: false
        }

        // Cool opposite fill preserves deep shadow instead of flattening it.
        DirectionalLight {
            eulerRotation: Qt.vector3d(27, -51, 14)
            color: "#7894b4"
            brightness: 1.35
            ambientColor: "#071019"
            castsShadow: false
        }

        // Forward edge light makes shell thickness readable at normal GUI size.
        PointLight {
            position: Qt.vector3d(-118, 112, 165)
            color: "#d8ecff"
            brightness: 2.70
            constantFade: 1.0
            linearFade: 0.0035
            quadraticFade: 0.000017
        }

        // Restrained warm counter-light — never floods the shell.
        PointLight {
            position: Qt.vector3d(148, -104, 120)
            color: "#ff9952"
            brightness: 1.45
            constantFade: 1.0
            linearFade: 0.0039
            quadraticFade: 0.000021
        }

        // State colour remains inside the cognition aperture.
        PointLight {
            position: Qt.vector3d(
                root.executionFlow * 22,
                root.verificationFocus * root.scanWave * 48,
                42 + root.planningDepth * 18
            )
            color: root.stateTone
            brightness: root.stopped ? 0.01 : 0.62 + root.energy * 0.98
            constantFade: 1.0
            linearFade: 0.0030
            quadraticFade: 0.000015
        }

        Node {
            id: artifactRoot
            position: Qt.vector3d(0, -3 + root.successLift * 4, 0)

            // Stronger 3/4 presentation than R10DP. This exposes >150 world
            // units of authored front/rear depth without turning the object
            // side-on.
            eulerRotation: Qt.vector3d(
                -6.0 + root.counterDrift * 0.28 * root.motionGate,
                -17.0 + root.drift * 1.0 * root.motionGate
                    + root.executionFlow * 2.6,
                -3.0 + root.planningDepth * root.drift * 0.50 * root.motionGate
                    + root.disorder * Math.sin(root.phase * 3.5) * 2.8
            )

            scale: Qt.vector3d(0.93, 0.93, 0.93)

            // ----------------------------------------------------------------
            // DEEP REAR ARCHITECTURE
            // ----------------------------------------------------------------
            Node {
                id: rearAssembly
                position: Qt.vector3d(
                    -root.openness * 3,
                    root.planningDepth * 2,
                    -4 - root.planningDepth * 16
                )
                eulerRotation: Qt.vector3d(
                    0,
                    -root.planningDepth * 4.2 + root.counterDrift * 0.35 * root.motionGate,
                    -root.planningDepth * 2.0
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_rear.glb")
                }
            }

            // ----------------------------------------------------------------
            // PRIMARY LEFT CONTAINMENT MASS
            // ----------------------------------------------------------------
            Node {
                id: leftAssembly
                position: Qt.vector3d(
                    -root.openness * 16 - root.disorder * 7,
                    root.disorder * Math.sin(root.phase * 4.1) * 4,
                    root.openness * 5 + root.disorder * 8
                )
                eulerRotation: Qt.vector3d(
                    0,
                    -root.openness * 4.0 - root.disorder * 5,
                    -root.openness * 2.2 + root.disorder * 3.5
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_left.glb")
                }
            }

            // ----------------------------------------------------------------
            // PRIMARY RIGHT CONTAINMENT MASS
            // ----------------------------------------------------------------
            Node {
                id: rightAssembly
                position: Qt.vector3d(
                    root.openness * 18 + root.executionFlow * 5 + root.disorder * 8,
                    root.executionFlow * 3 + root.disorder * Math.cos(root.phase * 3.6) * 4,
                    root.openness * 9 + root.executionFlow * 7 - root.disorder * 5
                )
                eulerRotation: Qt.vector3d(
                    0,
                    root.openness * 4.8 + root.executionFlow * 3.2 + root.disorder * 5.5,
                    root.openness * 2.5 + root.executionFlow * 1.5 - root.disorder * 3.4
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_right.glb")
                }
            }

            // ----------------------------------------------------------------
            // DEEP COGNITION APERTURE
            // ----------------------------------------------------------------
            Node {
                id: voidAssembly
                position: Qt.vector3d(0, 0, root.planningDepth * -8)
                eulerRotation: Qt.vector3d(0, root.drift * 0.35 * root.motionGate, 0)

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_void.glb")
                }
            }

            // Recessed precision collar advances in PLANNING and VERIFYING.
            Node {
                id: collarAssembly
                position: Qt.vector3d(
                    0,
                    0,
                    root.planningDepth * 10 + root.verificationFocus * 6
                )
                eulerRotation: Qt.vector3d(
                    0,
                    root.planningDepth * root.drift * 2.5 * root.motionGate,
                    root.planningDepth * root.counterDrift * 1.8 * root.motionGate
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_collar.glb")
                }
            }

            // ----------------------------------------------------------------
            // EVENT-HORIZON ENERGY — authored, segmented, never a full HUD ring
            // ----------------------------------------------------------------
            Node {
                id: haloAssembly
                position: Qt.vector3d(0, 0, 5 + root.successLift * 3)
                eulerRotation: Qt.vector3d(
                    0,
                    0,
                    root.planningDepth * 3.0
                        + root.executionFlow * root.drift * 1.2 * root.motionGate
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_halo.glb")
                }
            }

            // Curved computation/accretion stream. It passes BELOW and around
            // the aperture rather than drawing a straight line through it.
            Node {
                id: streamAssembly
                position: Qt.vector3d(
                    root.executionFlow * 10,
                    root.executionFlow * 5,
                    root.executionFlow * 12
                )
                eulerRotation: Qt.vector3d(
                    root.executionFlow * -1.2,
                    root.executionFlow * 2.2,
                    root.executionFlow * 1.0
                )

                RuntimeLoader {
                    source: Qt.resolvedUrl("../assets/ev_core_flagship_stream.glb")
                }
            }

            RuntimeLoader {
                source: Qt.resolvedUrl("../assets/ev_core_flagship_nodes.glb")
            }

            // ----------------------------------------------------------------
            // SPARSE DYNAMIC STATE SIGNALS
            // ----------------------------------------------------------------
            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    -34 + root.drift * 3 * root.motionGate,
                    30 + root.counterDrift * 2 * root.motionGate,
                    26
                )
                scale: Qt.vector3d(0.055, 0.055, 0.055)
                materials: [stateSignalMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    38 - root.counterDrift * 2 * root.motionGate,
                    -24 + root.drift * 3 * root.motionGate,
                    18
                )
                scale: Qt.vector3d(0.040, 0.040, 0.040)
                materials: [stateSignalMaterial]
            }

            Model {
                source: "#Sphere"
                position: Qt.vector3d(
                    10,
                    root.verificationFocus * root.scanWave * 44,
                    34 + root.planningDepth * 10
                )
                scale: Qt.vector3d(
                    0.030 + root.verificationFocus * 0.012,
                    0.030 + root.verificationFocus * 0.012,
                    0.030 + root.verificationFocus * 0.012
                )
                materials: [stateSignalMaterial]
            }
        }
    }
}
