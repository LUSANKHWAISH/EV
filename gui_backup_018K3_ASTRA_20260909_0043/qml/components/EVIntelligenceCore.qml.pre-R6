import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — ADAPTIVE COGNITIVE FIELD R5
// ============================================================================
//
// Visual identity:
// - five asymmetric graphite membranes
// - open cognition field / negative space through the center
// - layered Z depth rather than concentric ring construction
// - restrained state-colour emission from the internal field
// - motion communicates E.V. state without exposing hidden reasoning
//
// The renderer uses a fixed 3D world. Resizing this Item only resizes the
// View3D viewport; geometry, camera coordinates and light coordinates remain
// in world units.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // FIXED 3D WORLD
    // ------------------------------------------------------------------------
    readonly property real worldWidth: 360.0
    readonly property real worldHeight: 230.0
    readonly property real worldDepth: 130.0
    readonly property real cameraDistance: 525.0

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
        root.executing ? 1800 :
        root.speaking ? 2100 :
        root.failed ? 1550 :
        root.verifying ? 2500 :
        root.planning ? 3300 :
        root.listening ? 3600 :
        root.recovering ? 3900 :
        root.awaiting ? 6200 :
        root.successful ? 3000 :
        5200

    readonly property real pulse: (Math.sin(root.phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(root.phase * 0.5) + 1.0) * 0.5
    readonly property real drift: Math.sin(root.phase * 0.5)

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
    // STATE CONTROL — smoothed scalar factors
    // ------------------------------------------------------------------------
    property real openness:
        root.listening ? 1.0 :
        root.speaking ? 0.72 :
        root.successful ? 0.36 :
        root.failed ? -0.18 :
        root.stopped ? -0.75 :
        0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.28 : 0.0
    property real recoveryFlow: root.recovering ? 1.0 : 0.0
    property real successLift: root.successful ? 1.0 : 0.0

    Behavior on openness { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on planningDepth { NumberAnimation { duration: 650; easing.type: Easing.InOutCubic } }
    Behavior on executionFlow { NumberAnimation { duration: 430; easing.type: Easing.OutCubic } }
    Behavior on verificationFocus { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }
    Behavior on approvalLock { NumberAnimation { duration: 620; easing.type: Easing.InOutCubic } }
    Behavior on disorder { NumberAnimation { duration: 360; easing.type: Easing.OutCubic } }
    Behavior on recoveryFlow { NumberAnimation { duration: 760; easing.type: Easing.InOutCubic } }
    Behavior on successLift { NumberAnimation { duration: 480; easing.type: Easing.OutCubic } }

    readonly property real motionGate: 1.0 - root.approvalLock * 0.82

    readonly property real emissionBase:
        root.stopped ? 0.035 :
        root.listening ? 0.52 :
        root.planning ? 0.45 :
        root.executing ? 0.58 :
        root.verifying ? 0.61 :
        root.awaiting ? 0.31 :
        root.speaking ? 0.54 :
        root.successful ? 0.66 :
        root.failed ? 0.59 :
        root.recovering ? 0.47 :
        0.25

    readonly property real emissionIntensity:
        root.emissionBase * (0.88 + root.pulse * 0.12)

    // ------------------------------------------------------------------------
    // PROCEDURAL GEOMETRY DATA — generated once in fixed world units
    // ------------------------------------------------------------------------
    property var membraneAData: ({ positions: [], normals: [], indexes: [] })
    property var membraneBData: ({ positions: [], normals: [], indexes: [] })
    property var membraneCData: ({ positions: [], normals: [], indexes: [] })
    property var membraneDData: ({ positions: [], normals: [], indexes: [] })
    property var membraneEData: ({ positions: [], normals: [], indexes: [] })
    property var filamentAData: ({ positions: [], normals: [], indexes: [] })
    property var filamentBData: ({ positions: [], normals: [], indexes: [] })

    Component.onCompleted: buildGeometry()

    function bezier(a, b, c, d, t) {
        var u = 1.0 - t
        return u * u * u * a
             + 3.0 * u * u * t * b
             + 3.0 * u * t * t * c
             + t * t * t * d
    }

    function bezierDerivative(a, b, c, d, t) {
        var u = 1.0 - t
        return 3.0 * u * u * (b - a)
             + 6.0 * u * t * (c - b)
             + 3.0 * t * t * (d - c)
    }

    function normalize3(x, y, z) {
        var length = Math.sqrt(x * x + y * y + z * z)
        if (length < 0.00001)
            return { x: 0.0, y: 0.0, z: 1.0 }
        return { x: x / length, y: y / length, z: z / length }
    }

    function generateRibbon(p0x, p0y, p0z,
                            p1x, p1y, p1z,
                            p2x, p2y, p2z,
                            p3x, p3y, p3z,
                            widthStart, widthEnd,
                            depthBulge, twist,
                            lengthSegments, widthSegments) {
        var positions = []
        var normals = []
        var indexes = []

        for (var i = 0; i <= lengthSegments; ++i) {
            var t = i / lengthSegments

            var cx = bezier(p0x, p1x, p2x, p3x, t)
            var cy = bezier(p0y, p1y, p2y, p3y, t)
            var cz = bezier(p0z, p1z, p2z, p3z, t)
                   + depthBulge * Math.sin(Math.PI * t)

            var dx = bezierDerivative(p0x, p1x, p2x, p3x, t)
            var dy = bezierDerivative(p0y, p1y, p2y, p3y, t)
            var dz = bezierDerivative(p0z, p1z, p2z, p3z, t)
                   + depthBulge * Math.PI * Math.cos(Math.PI * t)

            var planarLength = Math.sqrt(dx * dx + dy * dy)
            if (planarLength < 0.00001)
                planarLength = 1.0

            var tangentX = dx / planarLength
            var tangentY = dy / planarLength

            var sideX = -tangentY
            var sideY = tangentX

            var width = widthStart + (widthEnd - widthStart) * t
            width *= 0.66 + 0.34 * Math.sin(Math.PI * t)

            var twistSlope = twist * Math.sin(Math.PI * t)

            for (var w = 0; w <= widthSegments; ++w) {
                var s = w / widthSegments - 0.5
                var lateral = width * s
                var localZ = twistSlope * s

                positions.push(Qt.vector3d(
                    cx + sideX * lateral,
                    cy + sideY * lateral,
                    cz + localZ
                ))

                var sideZ = twistSlope / Math.max(width, 1.0)

                // Cross(tangent, side) gives a stable front-facing surface normal.
                var nx = dy * sideZ - dz * sideY
                var ny = dz * sideX - dx * sideZ
                var nz = dx * sideY - dy * sideX
                var n = normalize3(nx, ny, nz)

                if (n.z < 0.0)
                    n = { x: -n.x, y: -n.y, z: -n.z }

                normals.push(Qt.vector3d(n.x, n.y, n.z))
            }
        }

        var row = widthSegments + 1

        for (var li = 0; li < lengthSegments; ++li) {
            for (var wi = 0; wi < widthSegments; ++wi) {
                var a = li * row + wi
                var b = a + 1
                var c = (li + 1) * row + wi
                var d = c + 1

                indexes.push(a, b, c)
                indexes.push(b, d, c)
            }
        }

        return { positions: positions, normals: normals, indexes: indexes }
    }

    function buildGeometry() {
        // Upper primary membrane — long asymmetric canopy.
        root.membraneAData = generateRibbon(
            -166, 28, -12,
            -112, 104, 2,
             24, 108, 8,
             144, 44, -14,
             48, 35,
             28, 20,
             42, 5
        )

        // Lower counter membrane — deliberately not a mirror of A.
        root.membraneBData = generateRibbon(
            -142, -44, -20,
            -58, -116, 4,
             64, -100, 18,
             162, -28, -4,
             38, 46,
            -20, -16,
             40, 5
        )

        // Inner adaptive membrane — smaller, forward and diagonal.
        root.membraneCData = generateRibbon(
            -92, 2, 18,
            -40, 66, 38,
             46, 36, 34,
             102, -18, 17,
             25, 18,
             16, 19,
             34, 4
        )

        // Rear-left support membrane — recedes into depth.
        root.membraneDData = generateRibbon(
            -156, -18, -58,
            -170, 44, -46,
            -114, 94, -34,
            -42, 72, -20,
             31, 19,
             14, -13,
             32, 4
        )

        // Rear-right membrane — taller and narrower than D.
        root.membraneEData = generateRibbon(
             36, -84, -48,
             108, -60, -38,
             154, 8, -28,
             126, 92, -18,
             21, 32,
             17, 16,
             34, 4
        )

        // Internal field filaments live inside the negative space.
        root.filamentAData = generateRibbon(
            -70, 8, 34,
            -24, 38, 45,
             36, 30, 42,
             82, 4, 34,
             3.2, 2.0,
             7, 2,
             24, 1
        )

        root.filamentBData = generateRibbon(
            -44, -26, 27,
             -8, -6, 38,
             34, -14, 41,
             62, -42, 28,
             2.5, 1.8,
             6, -2,
             20, 1
        )
    }

    // ------------------------------------------------------------------------
    // MATERIALS
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: primaryGraphite
        baseColor: "#111720"
        metalness: 0.42
        roughness: 0.36
        clearcoatAmount: 0.16
        clearcoatRoughnessAmount: 0.24
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: secondaryGraphite
        baseColor: "#0a0f16"
        metalness: 0.30
        roughness: 0.48
        clearcoatAmount: 0.10
        clearcoatRoughnessAmount: 0.32
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: innerGraphite
        baseColor: "#18202a"
        metalness: 0.34
        roughness: 0.40
        clearcoatAmount: 0.13
        clearcoatRoughnessAmount: 0.28
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: fieldMaterial
        baseColor: "#020406"
        metalness: 0.0
        roughness: 0.82
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity,
            root.stateTone.g * root.emissionIntensity,
            root.stateTone.b * root.emissionIntensity
        )
        cullMode: Material.NoCulling
    }

    // ------------------------------------------------------------------------
    // 3D SCENE
    // ------------------------------------------------------------------------
    View3D {
        id: view3d
        anchors.fill: parent

        environment: ExtendedSceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
            tonemapMode: SceneEnvironment.TonemapModeFilmic
            glowEnabled: true
            glowStrength: 0.34
            glowIntensity: 0.38
            glowBloom: 0.06
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(-5.5, 0, 0)
            fieldOfView: 46
            clipNear: 1.0
            clipFar: 2200.0
        }

        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-34, 28, 0)
            color: "#d8e2f2"
            brightness: 1.15
            ambientColor: "#070a10"
            castsShadow: false
        }

        DirectionalLight {
            id: fillLight
            eulerRotation: Qt.vector3d(24, -46, 0)
            color: "#66758a"
            brightness: 0.42
            ambientColor: "#05070a"
            castsShadow: false
        }

        PointLight {
            id: rimLight
            position: Qt.vector3d(-126, 62, 116)
            color: "#8ba7cf"
            brightness: 0.82
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000018
        }

        PointLight {
            id: cognitionLight
            position: Qt.vector3d(
                root.verificationFocus * Math.sin(root.phase * 1.7) * 76,
                root.planningDepth * Math.cos(root.phase * 0.7) * 18,
                42 + root.planningDepth * 16
            )
            color: root.stateTone
            brightness: root.stopped
                ? 0.04
                : 0.34 + root.energy * 0.48 + root.verificationFocus * 0.34
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000025
        }

        Node {
            id: sceneRoot

            eulerRotation: Qt.vector3d(
                -1.0 + root.drift * 0.65 * root.motionGate,
                root.drift * 1.8 * root.motionGate,
                root.disorder * Math.sin(root.phase * 3.2) * 1.2
            )

            scale: Qt.vector3d(
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006,
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006,
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006
            )

            // ---------------------------------------------------------------
            // MEMBRANE A — UPPER CANOPY
            // ---------------------------------------------------------------
            Model {
                id: membraneA
                geometry: ProceduralMesh {
                    positions: root.membraneAData.positions
                    normals: root.membraneAData.normals
                    indexes: root.membraneAData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [primaryGraphite]

                position: Qt.vector3d(
                    -root.openness * 6
                    + root.executionFlow * 10
                    + root.disorder * Math.sin(root.phase * 4.1) * 7,
                    root.openness * 12
                    + root.successLift * 7
                    + root.disorder * Math.cos(root.phase * 3.4) * 5,
                    root.planningDepth * 5
                )

                eulerRotation: Qt.vector3d(
                    -2.0 + root.planningDepth * 2.4,
                    root.executionFlow * -2.0,
                    -root.openness * 3.2
                    + root.disorder * Math.sin(root.phase * 4.7) * 5.5
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE B — LOWER COUNTER-SWEEP
            // ---------------------------------------------------------------
            Model {
                id: membraneB
                geometry: ProceduralMesh {
                    positions: root.membraneBData.positions
                    normals: root.membraneBData.normals
                    indexes: root.membraneBData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [primaryGraphite]

                position: Qt.vector3d(
                    root.openness * 4
                    - root.executionFlow * 5,
                    -root.openness * 10
                    - root.successLift * 5
                    + root.disorder * Math.sin(root.phase * 3.8) * 6,
                    -4 - root.planningDepth * 4
                )

                eulerRotation: Qt.vector3d(
                    1.5,
                    root.executionFlow * 2.3,
                    root.openness * 2.1
                    + root.disorder * Math.cos(root.phase * 4.3) * 4.6
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE C — INNER ADAPTIVE SURFACE
            // ---------------------------------------------------------------
            Model {
                id: membraneC
                geometry: ProceduralMesh {
                    positions: root.membraneCData.positions
                    normals: root.membraneCData.normals
                    indexes: root.membraneCData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [innerGraphite]

                position: Qt.vector3d(
                    root.executionFlow * 15
                    + root.planningDepth * Math.sin(root.phase * 0.8) * 7,
                    root.planningDepth * Math.cos(root.phase * 0.7) * 5,
                    root.planningDepth * 16
                    + root.verificationFocus * 9
                )

                eulerRotation: Qt.vector3d(
                    root.planningDepth * Math.sin(root.phase * 0.6) * 2.0,
                    -4.0 + root.planningDepth * Math.cos(root.phase * 0.7) * 4.0,
                    root.disorder * Math.sin(root.phase * 5.1) * 6.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE D — REAR LEFT DEPTH STRUCTURE
            // ---------------------------------------------------------------
            Model {
                id: membraneD
                geometry: ProceduralMesh {
                    positions: root.membraneDData.positions
                    normals: root.membraneDData.normals
                    indexes: root.membraneDData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [secondaryGraphite]

                position: Qt.vector3d(
                    -root.openness * 8,
                    root.listening ? 4 : 0,
                    -12 - root.planningDepth * 6
                )

                eulerRotation: Qt.vector3d(
                    -2.0,
                    -5.5 + root.planningDepth * 2.5,
                    -1.5 + root.disorder * Math.sin(root.phase * 3.5) * 4.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE E — REAR RIGHT ASCENDING STRUCTURE
            // ---------------------------------------------------------------
            Model {
                id: membraneE
                geometry: ProceduralMesh {
                    positions: root.membraneEData.positions
                    normals: root.membraneEData.normals
                    indexes: root.membraneEData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [secondaryGraphite]

                position: Qt.vector3d(
                    root.openness * 9
                    + root.executionFlow * 13,
                    root.openness * 3
                    + root.executionFlow * 2,
                    -8 + root.executionFlow * 8
                )

                eulerRotation: Qt.vector3d(
                    3.0,
                    5.5 + root.executionFlow * -4.0,
                    2.2 + root.disorder * Math.cos(root.phase * 4.0) * 5.0
                )
            }

            // ---------------------------------------------------------------
            // INTERNAL COGNITION FIELD
            // ---------------------------------------------------------------
            Model {
                id: filamentA
                geometry: ProceduralMesh {
                    positions: root.filamentAData.positions
                    normals: root.filamentAData.normals
                    indexes: root.filamentAData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [fieldMaterial]

                position: Qt.vector3d(
                    root.executionFlow * 10,
                    root.listening ? 2 : 0,
                    root.verificationFocus * 5
                )

                scale: Qt.vector3d(
                    1.0 + root.pulse * 0.025,
                    1.0 + root.openness * 0.12,
                    1.0
                )
            }

            Model {
                id: filamentB
                geometry: ProceduralMesh {
                    positions: root.filamentBData.positions
                    normals: root.filamentBData.normals
                    indexes: root.filamentBData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [fieldMaterial]

                position: Qt.vector3d(
                    -root.executionFlow * 4,
                    -root.speaking * 2,
                    root.planningDepth * 7
                )

                scale: Qt.vector3d(
                    1.0,
                    1.0 + root.pulse * 0.08 * root.motionGate,
                    1.0
                )
            }

            Model {
                id: cognitionSeed
                geometry: SphereGeometry {
                    radius: 4.2
                    segments: 12
                    rings: 8
                }
                materials: [fieldMaterial]

                position: Qt.vector3d(
                    12 + root.executionFlow * 13,
                    4 + root.listening * 4,
                    46 + root.planningDepth * 8
                )

                scale: Qt.vector3d(
                    root.stopped ? 0.35 : 0.90 + root.pulse * 0.20,
                    root.stopped ? 0.35 : 0.90 + root.pulse * 0.20,
                    root.stopped ? 0.35 : 0.90 + root.pulse * 0.20
                )
            }

            // Sparse cognition nodes — intentionally irregular, not an orbital ring.
            Model {
                geometry: SphereGeometry { radius: 1.5; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-58, 22, 32)
                scale: Qt.vector3d(0.72 + root.pulse * 0.22, 0.72 + root.pulse * 0.22, 0.72 + root.pulse * 0.22)
            }
            Model {
                geometry: SphereGeometry { radius: 1.15; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-28, -18, 38)
                scale: Qt.vector3d(0.62 + root.slowPulse * 0.25, 0.62 + root.slowPulse * 0.25, 0.62 + root.slowPulse * 0.25)
            }
            Model {
                geometry: SphereGeometry { radius: 1.35; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(38, 18, 43)
                scale: Qt.vector3d(0.70 + root.pulse * 0.20, 0.70 + root.pulse * 0.20, 0.70 + root.pulse * 0.20)
            }
            Model {
                geometry: SphereGeometry { radius: 1.0; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(68, -24, 30)
                scale: Qt.vector3d(0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20)
            }
            Model {
                geometry: SphereGeometry { radius: 0.95; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(4, 46, 28)
                scale: Qt.vector3d(0.55 + root.pulse * 0.18, 0.55 + root.pulse * 0.18, 0.55 + root.pulse * 0.18)
            }
        }
    }
}
