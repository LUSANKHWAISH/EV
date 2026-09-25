import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — COGNITIVE BRAID R7
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
    readonly property real worldHeight: 260.0
    readonly property real worldDepth: 180.0
    readonly property real cameraDistance: 430.0

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
        // R7 deliberately abandons the "upper shell / lower shell" composition.
        // The five surfaces form an offset diagonal braid.  No membrane pair
        // encloses the center, so the silhouette cannot resolve into an eye,
        // lens, ring or horizontal logo.

        // A — dominant rising sheath: lower-left -> upper-right.
        root.membraneAData = generateRibbon(
            -142, -92,   0,
            -126,  -6,  28,
             -54,  94,  46,
              74, 106,  12,
              38,  20,
              34,  28,
              38,   5
        )

        // B — forward crossing flow: upper-left -> lower-right.
        // It crosses the cognition field at a different depth instead of
        // mirroring membrane A.
        root.membraneBData = generateRibbon(
            -118,  48,  42,
             -72,  22,  66,
               8, -18,  78,
             126, -66,  34,
              25,  13,
              24, -30,
              38,   4
        )

        // C — narrow right-side lift.  This surface is tall and open-ended;
        // it supplies vertical tension without completing a perimeter.
        root.membraneCData = generateRibbon(
              52, -112, -34,
             118,  -78, -18,
             142,   18,   6,
              92,  116, -16,
              17,  31,
              22,  22,
              36,   4
        )

        // D — short upper-left rear fold.
        root.membraneDData = generateRibbon(
            -154,  48, -62,
            -138,  92, -48,
             -88, 124, -34,
             -22, 106, -24,
              22,  11,
              16, -18,
              30,   4
        )

        // E — lower-center rear tongue.  It terminates before reaching the
        // right edge and therefore never becomes a lower "eyelid".
        root.membraneEData = generateRibbon(
             -72, -124, -58,
             -34, -106, -44,
              18,  -82, -34,
              64,  -34, -22,
              24,  12,
              15,  14,
              30,   4
        )

        // Internal cognition traces follow the diagonal braid rather than
        // tracing the perimeter.  They remain thin and deliberately offset.
        root.filamentAData = generateRibbon(
             -58, -36,  70,
             -26,  -4,  84,
              18,  30,  86,
              70,  66,  68,
               2.8, 1.4,
               7,   5,
              24,   1
        )

        root.filamentBData = generateRibbon(
             -16,  66,  62,
               8,  42,  76,
              18,   2,  82,
              58, -46,  64,
               2.1, 1.2,
               6,  -5,
              22,   1
        )
    }

    // ------------------------------------------------------------------------
    // MATERIALS
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: primaryGraphite
        baseColor: "#465565"
        metalness: 0.34
        roughness: 0.34
        clearcoatAmount: 0.28
        clearcoatRoughnessAmount: 0.18
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: secondaryGraphite
        baseColor: "#26323d"
        metalness: 0.28
        roughness: 0.46
        clearcoatAmount: 0.16
        clearcoatRoughnessAmount: 0.26
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: innerGraphite
        baseColor: "#5b6977"
        metalness: 0.30
        roughness: 0.36
        clearcoatAmount: 0.22
        clearcoatRoughnessAmount: 0.20
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
            glowStrength: 0.42
            glowIntensity: 0.48
            glowBloom: 0.08
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, root.cameraDistance)
            eulerRotation: Qt.vector3d(-2.0, 0, 0)
            fieldOfView: 45
            clipNear: 1.0
            clipFar: 2200.0
        }

        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-28, 28, -12)
            color: "#f2f6ff"
            brightness: 2.85
            ambientColor: "#17212b"
            castsShadow: false
        }

        DirectionalLight {
            id: fillLight
            eulerRotation: Qt.vector3d(22, -48, 18)
            color: "#9fb1c5"
            brightness: 1.16
            ambientColor: "#0d141b"
            castsShadow: false
        }

        PointLight {
            id: rimLight
            position: Qt.vector3d(-126, 92, 146)
            color: "#b6d1f2"
            brightness: 1.95
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
                -7.0 + root.drift * 1.2 * root.motionGate,
                -18.0 + root.drift * 3.4 * root.motionGate,
                -11.0 + root.executionFlow * 4.5
                + root.disorder * Math.sin(root.phase * 3.2) * 5.5
            )

            scale: Qt.vector3d(
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006,
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006,
                root.stopped ? 0.82 : 1.0 + root.slowPulse * 0.006
            )

            // ---------------------------------------------------------------
            // MEMBRANE A — DOMINANT RISING SHEATH
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
                    -8 - root.openness * 13
                    + root.disorder * Math.sin(root.phase * 4.1) * 11,
                    1 + root.openness * 8 + root.successLift * 10,
                    8 - root.executionFlow * 10 + root.planningDepth * 7
                )

                eulerRotation: Qt.vector3d(
                    -7.0 + root.planningDepth * 4.0,
                    -10.0 + root.executionFlow * 4.5,
                    -8.0 - root.openness * 4.0
                    + root.disorder * Math.sin(root.phase * 4.7) * 10.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE B — FORWARD CROSSING FLOW
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
                    7 + root.openness * 15 + root.executionFlow * 13,
                    -2 - root.openness * 7 - root.successLift * 7
                    + root.disorder * Math.sin(root.phase * 3.8) * 10,
                    4 + root.executionFlow * 12 - root.planningDepth * 5
                )

                eulerRotation: Qt.vector3d(
                    3.0 + root.planningDepth * 2.0,
                    7.0 - root.executionFlow * 6.0,
                    5.0 + root.openness * 3.0
                    + root.disorder * Math.cos(root.phase * 4.3) * 9.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE C — RIGHT-SIDE LIFT
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
                    4 + root.executionFlow * 24
                    + root.planningDepth * Math.sin(root.phase * 0.8) * 10,
                    -2 + root.planningDepth * Math.cos(root.phase * 0.7) * 10,
                    22 + root.planningDepth * 24
                    + root.verificationFocus * 16
                )

                eulerRotation: Qt.vector3d(
                    -4.0 + root.planningDepth * Math.sin(root.phase * 0.6) * 4.0,
                    -14.0 + root.planningDepth * Math.cos(root.phase * 0.7) * 8.0,
                    5.0 + root.executionFlow * 7.0
                    + root.disorder * Math.sin(root.phase * 5.1) * 11.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE D — UPPER-LEFT REAR FOLD
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
                    -10 - root.openness * 8,
                    3 + root.openness * 5,
                    -24 - root.planningDepth * 12
                )

                eulerRotation: Qt.vector3d(
                    -9.0,
                    -18.0 + root.planningDepth * 5.0,
                    -16.0 + root.disorder * Math.sin(root.phase * 3.5) * 9.0
                )
            }

            // ---------------------------------------------------------------
            // MEMBRANE E — LOWER-CENTER REAR TONGUE
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
                    5 + root.openness * 9 + root.executionFlow * 22,
                    0 + root.openness * 4 + root.executionFlow * 8,
                    -14 + root.executionFlow * 16
                )

                eulerRotation: Qt.vector3d(
                    9.0,
                    18.0 - root.executionFlow * 9.0,
                    16.0 + root.openness * 2.0
                    + root.disorder * Math.cos(root.phase * 4.0) * 10.0
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
                    -2 + root.executionFlow * 16,
                    2 + root.openness * 5,
                    12 + root.verificationFocus * 10
                )

                eulerRotation: Qt.vector3d(-2, -6, -12 + root.executionFlow * 5)

                scale: Qt.vector3d(
                    1.0 + root.pulse * 0.035,
                    1.0 + root.openness * 0.10,
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
                    8 - root.executionFlow * 7,
                    -1 - root.speaking * 4,
                    14 + root.planningDepth * 13
                )

                eulerRotation: Qt.vector3d(2, 6, 16 - root.planningDepth * 5)

                scale: Qt.vector3d(
                    1.0,
                    1.0 + root.pulse * 0.10 * root.motionGate,
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
                    10 + root.executionFlow * 18,
                    8 + root.listening * 7,
                    72 + root.planningDepth * 12
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
                position: Qt.vector3d(-62, -20, 42)
                scale: Qt.vector3d(0.72 + root.pulse * 0.22, 0.72 + root.pulse * 0.22, 0.72 + root.pulse * 0.22)
            }
            Model {
                geometry: SphereGeometry { radius: 1.15; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-34, 10, 50)
                scale: Qt.vector3d(0.62 + root.slowPulse * 0.25, 0.62 + root.slowPulse * 0.25, 0.62 + root.slowPulse * 0.25)
            }
            Model {
                geometry: SphereGeometry { radius: 1.35; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(34, 34, 54)
                scale: Qt.vector3d(0.70 + root.pulse * 0.20, 0.70 + root.pulse * 0.20, 0.70 + root.pulse * 0.20)
            }
            Model {
                geometry: SphereGeometry { radius: 1.0; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(72, 8, 40)
                scale: Qt.vector3d(0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20)
            }
            Model {
                geometry: SphereGeometry { radius: 0.95; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(2, 68, 34)
                scale: Qt.vector3d(0.55 + root.pulse * 0.18, 0.55 + root.pulse * 0.18, 0.55 + root.pulse * 0.18)
            }
        }
    }
}
