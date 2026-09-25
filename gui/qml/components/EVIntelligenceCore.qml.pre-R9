import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — COGNITIVE FOLD R8
// ============================================================================
//
// R8 abandons the hard strap / eye / orbit language completely.
// The core is one asymmetric cognitive fold: broad cambered membranes flow
// around an intentionally incomplete cognition void, with a faceted inner
// shard and sparse intelligence traces suspended through the depth.
//
// Design rules:
// - one unified flowing structure, not a collection of rings or crossed bars
// - no eye, no lens, no reactor, no complete perimeter
// - broad curved graphite surfaces with real Z-depth and cross-section camber
// - state colour lives inside the void; the shell stays graphite
// - fixed 3D world independent of viewport size
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // FIXED 3D WORLD
    // ------------------------------------------------------------------------
    readonly property real worldWidth: 330.0
    readonly property real worldHeight: 300.0
    readonly property real worldDepth: 190.0
    readonly property real cameraDistance: 425.0

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
        root.executing ? 1750 :
        root.speaking ? 2100 :
        root.failed ? 1450 :
        root.verifying ? 2350 :
        root.planning ? 3200 :
        root.listening ? 3500 :
        root.recovering ? 3900 :
        root.awaiting ? 6100 :
        root.successful ? 2850 :
        5100

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
    // STATE CONTROL — scalar only, all geometry remains vector-safe
    // ------------------------------------------------------------------------
    property real openness:
        root.listening ? 1.0 :
        root.speaking ? 0.72 :
        root.successful ? 0.30 :
        root.failed ? -0.18 :
        root.stopped ? -0.72 :
        0.0

    property real planningDepth: root.planning ? 1.0 : 0.0
    property real executionFlow: root.executing ? 1.0 : 0.0
    property real verificationFocus: root.verifying ? 1.0 : 0.0
    property real approvalLock: root.awaiting ? 1.0 : 0.0
    property real disorder: root.failed ? 1.0 : root.recovering ? 0.24 : 0.0
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

    readonly property real motionGate: 1.0 - root.approvalLock * 0.86

    readonly property real emissionBase:
        root.stopped ? 0.035 :
        root.listening ? 0.60 :
        root.planning ? 0.50 :
        root.executing ? 0.66 :
        root.verifying ? 0.70 :
        root.awaiting ? 0.36 :
        root.speaking ? 0.61 :
        root.successful ? 0.76 :
        root.failed ? 0.68 :
        root.recovering ? 0.54 :
        0.31

    readonly property real emissionIntensity:
        root.emissionBase * (0.88 + root.pulse * 0.12)

    // ------------------------------------------------------------------------
    // PROCEDURAL DATA — generated once in fixed world coordinates
    // ------------------------------------------------------------------------
    property var bladeAData: ({ positions: [], normals: [], indexes: [] })
    property var bladeBData: ({ positions: [], normals: [], indexes: [] })
    property var bladeCData: ({ positions: [], normals: [], indexes: [] })
    property var bladeDData: ({ positions: [], normals: [], indexes: [] })
    property var bladeEData: ({ positions: [], normals: [], indexes: [] })

    property var filamentAData: ({ positions: [], normals: [], indexes: [] })
    property var filamentBData: ({ positions: [], normals: [], indexes: [] })
    property var filamentCData: ({ positions: [], normals: [], indexes: [] })
    property var shardData: ({ positions: [], normals: [], indexes: [] })

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

    // A true cambered blade.  Width tapers toward both ends and the cross
    // section bows in Z, producing a sculpted membrane rather than a flat strap.
    function generateBlade(p0x, p0y, p0z,
                           p1x, p1y, p1z,
                           p2x, p2y, p2z,
                           p3x, p3y, p3z,
                           maxWidth, camber, twist, depthWave,
                           lengthSegments, widthSegments) {
        var positions = []
        var normals = []
        var indexes = []

        for (var i = 0; i <= lengthSegments; ++i) {
            var t = i / lengthSegments
            var sinT = Math.sin(Math.PI * t)

            var cx = bezier(p0x, p1x, p2x, p3x, t)
            var cy = bezier(p0y, p1y, p2y, p3y, t)
            var cz = bezier(p0z, p1z, p2z, p3z, t)
                   + depthWave * sinT

            var dx = bezierDerivative(p0x, p1x, p2x, p3x, t)
            var dy = bezierDerivative(p0y, p1y, p2y, p3y, t)
            var dz = bezierDerivative(p0z, p1z, p2z, p3z, t)
                   + depthWave * Math.PI * Math.cos(Math.PI * t)

            var planarLength = Math.sqrt(dx * dx + dy * dy)
            if (planarLength < 0.00001)
                planarLength = 1.0

            var sideX = -dy / planarLength
            var sideY = dx / planarLength

            // Never collapse completely to zero; this avoids degenerate tips.
            var taper = 0.10 + 0.90 * Math.pow(Math.max(0.0, sinT), 0.72)
            var halfWidth = maxWidth * 0.5 * taper

            for (var w = 0; w <= widthSegments; ++w) {
                var s = (w / widthSegments) * 2.0 - 1.0
                var lateral = halfWidth * s

                // Convex cross-section + controlled twist.
                var camberZ = camber * (1.0 - s * s) * sinT
                var twistZ = twist * s * sinT

                positions.push(Qt.vector3d(
                    cx + sideX * lateral,
                    cy + sideY * lateral,
                    cz + camberZ + twistZ
                ))

                // Approximate derivative across blade width.
                var sx = sideX * halfWidth
                var sy = sideY * halfWidth
                var sz = (-2.0 * camber * s + twist) * sinT

                // Cross(tangent, sideDerivative)
                var nx = dy * sz - dz * sy
                var ny = dz * sx - dx * sz
                var nz = dx * sy - dy * sx
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

    function buildShard(width, height, depth) {
        var hw = width * 0.5
        var hh = height * 0.5
        var hd = depth * 0.5

        var raw = [
            Qt.vector3d(0,  hh, 0),
            Qt.vector3d(0, -hh, 0),
            Qt.vector3d(-hw, 0, 0),
            Qt.vector3d( hw, 0, 0),
            Qt.vector3d(0, 0,  hd),
            Qt.vector3d(0, 0, -hd)
        ]

        var normals = []
        for (var i = 0; i < raw.length; ++i) {
            var p = raw[i]
            var n = normalize3(p.x, p.y, p.z)
            normals.push(Qt.vector3d(n.x, n.y, n.z))
        }

        var indexes = [
            0, 4, 3,
            0, 2, 4,
            0, 5, 2,
            0, 3, 5,
            1, 3, 4,
            1, 4, 2,
            1, 2, 5,
            1, 5, 3
        ]

        return { positions: raw, normals: normals, indexes: indexes }
    }

    function buildGeometry() {
        // R8 composition: an asymmetric, incomplete cognitive fold.
        // Four broad outer fields sweep around the centre from different
        // directions, but none is a mirrored partner and the perimeter never
        // closes.  The fifth blade floats forward inside the structure.

        // A — broad upper-left crown sweeping toward the right.
        root.bladeAData = generateBlade(
            -122,   54, -18,
             -88,  126,   8,
              42,  136,  22,
             118,   64,  -6,
              58,   20, -16,  26,
              44,    7
        )

        // B — left descending fold.  It drops away from the crown instead of
        // mirroring it, creating the large open lower-left break.
        root.bladeBData = generateBlade(
            -118,   48,  18,
            -148,   -8,  34,
            -104,  -82,  20,
             -34, -112, -14,
              48,   17,  18,  20,
              40,    6
        )

        // C — lower sweep rising into the right side.
        root.bladeCData = generateBlade(
             -28, -114, -42,
              42, -142, -16,
             122,  -92,  14,
             116,  -20,  24,
              50,   18, -20,  22,
              42,    7
        )

        // D — shorter right-upper adaptive fold.  It terminates early and
        // leaves a deliberate opening at the upper-right edge.
        root.bladeDData = generateBlade(
             112,  -16, -52,
             148,   38, -30,
             112,   96,  -6,
              56,   92,  18,
              38,   15,  17,  17,
              34,    6
        )

        // E — inner forward fold.  This is the closest surface to the viewer
        // and gives the object its characteristic asymmetric intelligence flow.
        root.bladeEData = generateBlade(
             -60,   28,  48,
             -20,   80,  76,
              54,   58,  84,
              70,   -8,  56,
              34,   17, -12,  12,
              36,    6
        )

        // Internal intelligence traces cross the void at different depths.
        // They are intentionally short and curved rather than perimeter arcs.
        root.filamentAData = generateBlade(
             -56,  -42,  82,
             -24,   -6, 100,
              18,   34, 106,
              54,   12,  90,
               4.4, 1.8,  2.0,  4.0,
              26,   2
        )

        root.filamentBData = generateBlade(
             -32,   56,  88,
              -2,   30, 108,
               8,  -18, 112,
              38,  -52,  90,
               3.6, 1.4, -2.0,  3.5,
              24,   2
        )

        root.filamentCData = generateBlade(
             -52,    8,  92,
             -16,  -28, 110,
              30,  -10, 108,
              54,   34,  88,
               2.8, 1.0,  1.2,  2.5,
              22,   2
        )

        root.shardData = buildShard(14.0, 36.0, 19.0)
    }

    // ------------------------------------------------------------------------
    // MATERIALS
    // ------------------------------------------------------------------------
    PrincipledMaterial {
        id: primaryGraphite
        baseColor: "#35424f"
        metalness: 0.48
        roughness: 0.31
        clearcoatAmount: 0.34
        clearcoatRoughnessAmount: 0.16
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: secondaryGraphite
        baseColor: "#202a34"
        metalness: 0.40
        roughness: 0.42
        clearcoatAmount: 0.22
        clearcoatRoughnessAmount: 0.22
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: innerGraphite
        baseColor: "#536373"
        metalness: 0.34
        roughness: 0.34
        clearcoatAmount: 0.30
        clearcoatRoughnessAmount: 0.17
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * 0.035,
            root.stateTone.g * 0.035,
            root.stateTone.b * 0.035
        )
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: fieldMaterial
        baseColor: "#030609"
        metalness: 0.0
        roughness: 0.72
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity,
            root.stateTone.g * root.emissionIntensity,
            root.stateTone.b * root.emissionIntensity
        )
        cullMode: Material.NoCulling
    }

    PrincipledMaterial {
        id: shardMaterial
        baseColor: "#071018"
        metalness: 0.12
        roughness: 0.26
        clearcoatAmount: 0.42
        clearcoatRoughnessAmount: 0.12
        emissiveFactor: Qt.vector3d(
            root.stateTone.r * root.emissionIntensity * 1.20,
            root.stateTone.g * root.emissionIntensity * 1.20,
            root.stateTone.b * root.emissionIntensity * 1.20
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
            glowIntensity: 0.46
            glowBloom: 0.07
            glowBlendMode: ExtendedSceneEnvironment.GlowBlendMode.Screen
            ditheringEnabled: true
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 4, root.cameraDistance)
            eulerRotation: Qt.vector3d(-1.5, 0, 0)
            fieldOfView: 45
            clipNear: 1.0
            clipFar: 2200.0
        }

        DirectionalLight {
            id: keyLight
            eulerRotation: Qt.vector3d(-30, 34, -10)
            color: "#f5f8fc"
            brightness: 3.45
            ambientColor: "#1b2631"
            castsShadow: false
        }

        DirectionalLight {
            id: fillLight
            eulerRotation: Qt.vector3d(28, -54, 16)
            color: "#a7b7c7"
            brightness: 1.55
            ambientColor: "#101820"
            castsShadow: false
        }

        PointLight {
            id: rimLight
            position: Qt.vector3d(-122, 118, 158)
            color: "#c4ddf8"
            brightness: 2.55
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000018
        }

        PointLight {
            id: lowerRimLight
            position: Qt.vector3d(118, -106, 92)
            color: "#6f87a4"
            brightness: 1.20
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000022
        }

        PointLight {
            id: cognitionLight
            position: Qt.vector3d(
                root.executionFlow * 18,
                root.verificationFocus * Math.sin(root.phase * 1.5) * 92,
                62 + root.planningDepth * 22
            )
            color: root.stateTone
            brightness: root.stopped
                ? 0.04
                : 0.52 + root.energy * 0.62 + root.verificationFocus * 0.42
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000023
        }

        Node {
            id: sceneRoot

            position: Qt.vector3d(0, -1 + root.successLift * 6, 0)

            eulerRotation: Qt.vector3d(
                -8.0 + root.microDrift * 1.1 * root.motionGate,
                -17.0 + root.drift * 2.8 * root.motionGate,
                -10.0 + root.executionFlow * 3.0
                + root.disorder * Math.sin(root.phase * 3.2) * 5.0
            )

            scale: Qt.vector3d(
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.005,
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.005,
                root.stopped ? 0.84 : 1.0 + root.slowPulse * 0.005
            )

            // ---------------------------------------------------------------
            // A — LEFT FRONT PETAL
            // ---------------------------------------------------------------
            Model {
                id: bladeA
                geometry: ProceduralMesh {
                    positions: root.bladeAData.positions
                    normals: root.bladeAData.normals
                    indexes: root.bladeAData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [primaryGraphite]

                position: Qt.vector3d(
                    -4 - root.openness * 7
                    + root.disorder * Math.sin(root.phase * 4.0) * 8,
                     6 + root.openness * 12 + root.successLift * 5,
                     6 + root.planningDepth * 5
                )

                eulerRotation: Qt.vector3d(
                    -3.0 + root.planningDepth * 2.5,
                    -7.0 + root.executionFlow * 3.0,
                    -2.0 - root.openness * 2.2
                    + root.disorder * Math.sin(root.phase * 4.4) * 7.0
                )
            }

            // ---------------------------------------------------------------
            // B — RIGHT REAR PETAL
            // ---------------------------------------------------------------
            Model {
                id: bladeB
                geometry: ProceduralMesh {
                    positions: root.bladeBData.positions
                    normals: root.bladeBData.normals
                    indexes: root.bladeBData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [secondaryGraphite]

                position: Qt.vector3d(
                    -6 - root.openness * 12,
                    -2 - root.openness * 5,
                    -8 - root.planningDepth * 7
                )

                eulerRotation: Qt.vector3d(
                     2.0,
                     7.0 - root.executionFlow * 4.0,
                     2.0 + root.openness * 1.5
                    + root.disorder * Math.cos(root.phase * 4.1) * 7.0
                )
            }

            // ---------------------------------------------------------------
            // C — CENTRAL FORWARD FOLD
            // ---------------------------------------------------------------
            Model {
                id: bladeC
                geometry: ProceduralMesh {
                    positions: root.bladeCData.positions
                    normals: root.bladeCData.normals
                    indexes: root.bladeCData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [innerGraphite]

                position: Qt.vector3d(
                     5 + root.executionFlow * 10,
                    -8 - root.openness * 11
                    + root.planningDepth * Math.sin(root.phase * 0.72) * 4,
                    18 + root.planningDepth * 17 + root.verificationFocus * 9
                )

                eulerRotation: Qt.vector3d(
                    -2.0 + root.planningDepth * Math.sin(root.phase * 0.6) * 2.0,
                     9.0 + root.planningDepth * Math.cos(root.phase * 0.68) * 3.5,
                    -2.0 + root.executionFlow * 3.5
                    + root.disorder * Math.sin(root.phase * 5.0) * 8.0
                )
            }

            // ---------------------------------------------------------------
            // D — UPPER LEFT REAR FOLD
            // ---------------------------------------------------------------
            Model {
                id: bladeD
                geometry: ProceduralMesh {
                    positions: root.bladeDData.positions
                    normals: root.bladeDData.normals
                    indexes: root.bladeDData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [secondaryGraphite]

                position: Qt.vector3d(
                     8 + root.openness * 12,
                     4 + root.openness * 6,
                   -24 - root.planningDepth * 8
                )

                eulerRotation: Qt.vector3d(
                    -7.0,
                   -11.0 + root.planningDepth * 4.0,
                    -4.0 + root.disorder * Math.sin(root.phase * 3.4) * 7.0
                )
            }

            // ---------------------------------------------------------------
            // E — LOWER RIGHT SUPPORT FOLD
            // ---------------------------------------------------------------
            Model {
                id: bladeE
                geometry: ProceduralMesh {
                    positions: root.bladeEData.positions
                    normals: root.bladeEData.normals
                    indexes: root.bladeEData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [primaryGraphite]

                position: Qt.vector3d(
                     3 + root.openness * 4 + root.executionFlow * 13,
                     1 + root.openness * 3 + root.executionFlow * 4,
                    26 + root.planningDepth * 18 + root.executionFlow * 8
                )

                eulerRotation: Qt.vector3d(
                     5.0 + root.planningDepth * 2.0,
                    12.0 - root.executionFlow * 6.0,
                     4.0 + root.openness * 1.4
                    + root.disorder * Math.cos(root.phase * 4.0) * 7.0
                )
            }

            // ---------------------------------------------------------------
            // INTERNAL NEURAL FIELD
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
                    -2 + root.executionFlow * 8,
                     1 + root.openness * 4,
                    18 + root.verificationFocus * 8
                )

                eulerRotation: Qt.vector3d(-1, -3, -2 + root.executionFlow * 2)
                scale: Qt.vector3d(1.0 + root.pulse * 0.025, 1.0, 1.0)
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
                     5 - root.executionFlow * 5,
                    -1 - root.speaking * 3,
                    22 + root.planningDepth * 11
                )

                eulerRotation: Qt.vector3d(1, 4, 3 - root.planningDepth * 2)
                scale: Qt.vector3d(1.0, 1.0 + root.pulse * 0.07 * root.motionGate, 1.0)
            }

            Model {
                id: filamentC
                geometry: ProceduralMesh {
                    positions: root.filamentCData.positions
                    normals: root.filamentCData.normals
                    indexes: root.filamentCData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [fieldMaterial]

                position: Qt.vector3d(
                    root.executionFlow * 9,
                    root.verificationFocus * Math.sin(root.phase * 1.5) * 9,
                    28 + root.planningDepth * 12
                )

                eulerRotation: Qt.vector3d(0, -2, 2)
            }

            // Faceted cognition shard — replaces the generic central sphere.
            Model {
                id: cognitionShard
                geometry: ProceduralMesh {
                    positions: root.shardData.positions
                    normals: root.shardData.normals
                    indexes: root.shardData.indexes
                    primitiveMode: ProceduralMesh.Triangles
                }
                materials: [shardMaterial]

                position: Qt.vector3d(
                     2 + root.executionFlow * 9,
                     2 + root.listening * 4 + root.successLift * 7,
                    88 + root.planningDepth * 10
                )

                eulerRotation: Qt.vector3d(
                    -8 + root.drift * 2.0,
                    18 + root.phase * 5.0,
                     5 + root.executionFlow * 5.0
                )

                scale: Qt.vector3d(
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.10,
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.10,
                    root.stopped ? 0.46 : 0.92 + root.pulse * 0.10
                )
            }

            // Sparse cognition nodes — vertical constellation, never an orbit.
            Model {
                geometry: SphereGeometry { radius: 1.35; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-48, -30, 70)
                scale: Qt.vector3d(0.72 + root.pulse * 0.18, 0.72 + root.pulse * 0.18, 0.72 + root.pulse * 0.18)
            }
            Model {
                geometry: SphereGeometry { radius: 1.05; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-28, 18, 82)
                scale: Qt.vector3d(0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20, 0.60 + root.slowPulse * 0.20)
            }
            Model {
                geometry: SphereGeometry { radius: 1.10; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(18, -38, 90)
                scale: Qt.vector3d(0.62 + root.pulse * 0.18, 0.62 + root.pulse * 0.18, 0.62 + root.pulse * 0.18)
            }
            Model {
                geometry: SphereGeometry { radius: 1.25; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(42, 24, 78)
                scale: Qt.vector3d(0.67 + root.slowPulse * 0.18, 0.67 + root.slowPulse * 0.18, 0.67 + root.slowPulse * 0.18)
            }
            Model {
                geometry: SphereGeometry { radius: 0.95; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-8, 52, 74)
                scale: Qt.vector3d(0.58 + root.pulse * 0.17, 0.58 + root.pulse * 0.17, 0.58 + root.pulse * 0.17)
            }
            Model {
                geometry: SphereGeometry { radius: 1.15; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(56, -8, 64)
                scale: Qt.vector3d(0.64 + root.slowPulse * 0.18, 0.64 + root.slowPulse * 0.18, 0.64 + root.slowPulse * 0.18)
            }
            Model {
                geometry: SphereGeometry { radius: 0.90; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(-50, 52, 52)
                scale: Qt.vector3d(0.56 + root.pulse * 0.16, 0.56 + root.pulse * 0.16, 0.56 + root.pulse * 0.16)
            }
            Model {
                geometry: SphereGeometry { radius: 0.95; segments: 6; rings: 5 }
                materials: [fieldMaterial]
                position: Qt.vector3d(8, -62, 60)
                scale: Qt.vector3d(0.58 + root.slowPulse * 0.16, 0.58 + root.slowPulse * 0.16, 0.58 + root.slowPulse * 0.16)
            }
        }
    }
}
