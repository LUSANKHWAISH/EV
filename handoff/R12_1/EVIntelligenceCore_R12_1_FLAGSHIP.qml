import QtQuick 2.15
import QtQuick3D
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — R12.1 FLAGSHIP CUSTOM-MESH PROTOTYPE
// ============================================================================
//
// MAIN CHANGE:
// The visual identity is no longer assembled from cubes/spheres.
// The outer shell, living membrane, front lens and cognition nucleus are
// custom ProceduralMesh geometry generated ONCE at startup.
//
// No GLB. No Blender. No RuntimeLoader. No browser stack.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // PUBLIC E.V. CONTRACT
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

    property real audioLevel: 0.0
    property real speechLevel: 0.0

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
    // MOTION
    // ------------------------------------------------------------------------
    property real phase: 0.0

    readonly property int cycle:
        executing ? 1500 :
        failed ? 1350 :
        verifying ? 1900 :
        speaking ? 1550 :
        planning ? 2100 :
        listening ? 1700 :
        recovering ? 2800 :
        awaiting ? 6800 :
        successful ? 2500 :
        5200

    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.cycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    readonly property real pulse: (Math.sin(phase) + 1.0) * 0.5
    readonly property real slowPulse: (Math.sin(phase * 0.46) + 1.0) * 0.5
    readonly property real drift: Math.sin(phase * 0.37)
    readonly property real drift2: Math.cos(phase * 0.29)

    readonly property real demoListen:
        listening ? 0.18 + pulse * 0.34 : 0.0

    readonly property real demoSpeech:
        speaking
        ? 0.16 + Math.max(0.0, Math.sin(phase * 3.0)) * 0.50
        : 0.0

    readonly property real listenDrive:
        listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                audioLevel > 0.01 ? audioLevel : demoListen
            )
        )
        : 0.0

    readonly property real speechDrive:
        speaking
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                speechLevel > 0.01 ? speechLevel : demoSpeech
            )
        )
        : 0.0

    readonly property real motionGate:
        awaiting ? 0.055 :
        stopped ? 0.0 :
        1.0

    readonly property color sapphire: "#246CFF"
    readonly property color brightSapphire: "#58B8FF"
    readonly property color deepSapphire: "#123A9C"
    readonly property color restrainedGold: "#C9A86C"
    readonly property color coldWhite: "#EAF2FF"

    readonly property color coreTone:
        idle ? deepSapphire :
        listening ? brightSapphire :
        planning ? "#6F8FFF" :
        speaking ? "#FFD08A" :
        stateTone

    readonly property real glow:
        stopped ? 0.03 :
        listening ? 0.72 + listenDrive * 0.46 :
        speaking ? 0.75 + speechDrive * 0.48 :
        planning ? 0.84 :
        executing ? 1.00 :
        verifying ? 0.92 :
        successful ? 1.10 :
        failed ? 0.48 :
        recovering ? 0.72 :
        awaiting ? 0.32 :
        0.56

    readonly property real membraneScale:
        stopped ? 0.90 :
        listening ? 1.00 + listenDrive * 0.065 :
        speaking ? 1.00 + speechDrive * 0.052 :
        successful ? 1.045 :
        failed ? 0.975 :
        0.992 + slowPulse * 0.018

    readonly property real membraneZ:
        executing ? 18.0 :
        verifying ? 6.0 + drift * 12.0 :
        listening ? 4.0 + listenDrive * 7.0 :
        speaking ? 7.0 + speechDrive * 6.0 :
        2.0

    readonly property real nucleusZ:
        executing ? 54.0 :
        verifying ? 36.0 + drift * 14.0 :
        speaking ? 42.0 + speechDrive * 8.0 :
        listening ? 40.0 + listenDrive * 5.0 :
        39.0

    readonly property real lensZ:
        listening ? 6.0 + listenDrive * 8.0 :
        speaking ? 6.0 + speechDrive * 6.0 :
        successful ? 8.0 :
        0.0

    readonly property real particleSpeed:
        executing ? 2.20 :
        planning ? 1.62 :
        verifying ? 0.98 :
        listening ? 0.60 + listenDrive * 0.74 :
        speaking ? 0.76 + speechDrive * 0.44 :
        failed ? 1.28 :
        recovering ? 0.68 :
        awaiting ? 0.08 :
        stopped ? 0.01 :
        0.28

    function rgbaString(c, a) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, a))
            + ")"
    }

    // ------------------------------------------------------------------------
    // CUSTOM MESH BUILDERS — called once
    // ------------------------------------------------------------------------
    function normalize3(x, y, z) {
        var l = Math.sqrt(x*x + y*y + z*z)
        if (l < 0.000001)
            l = 1.0
        return Qt.vector3d(x/l, y/l, z/l)
    }

    function wrapPi(a) {
        while (a > Math.PI)
            a -= Math.PI * 2.0
        while (a < -Math.PI)
            a += Math.PI * 2.0
        return a
    }

    function shellPoint(theta, lat) {
        var c = Math.cos(lat)
        var s = Math.sin(lat)

        var m =
            1.0
            + 0.060 * Math.sin(2.0*theta + 0.45) * c*c
            + 0.032 * Math.sin(3.0*lat + theta*0.75)
            + 0.018 * Math.cos(4.0*theta - lat)

        var x = 98.0 * c * Math.cos(theta) * m
        var y = 110.0 * s * (1.0 + 0.035*Math.cos(theta - 0.55))
        var z =
            76.0 * c * Math.sin(theta)
            * (m + 0.035*Math.sin(lat*2.0))

        // continuous sculptural asymmetry
        x += 7.0 * s * Math.sin(theta)
        y += 3.5 * Math.sin(2.0*theta) * c
        z += 3.0 * Math.sin(theta + lat) * c

        return Qt.vector3d(x, y, z)
    }

    function shellNormal(p) {
        return normalize3(
            p.x / (98.0*98.0),
            p.y / (110.0*110.0),
            p.z / (76.0*76.0)
        )
    }

    function isAperture(theta, lat) {
        // Main asymmetric front intelligence aperture.
        var d = wrapPi(
            theta - (
                Math.PI/2.0
                + 0.16*lat
                - 0.06
            )
        )

        var half =
            0.63
            * Math.max(
                0.34,
                1.0
                - 0.56
                * Math.abs(lat / 0.78)
            )

        var main =
            lat > -0.72
            && lat < 0.74
            && Math.abs(d) < half

        // Secondary precision incision.
        var d2 =
            wrapPi(
                theta
                - (Math.PI/2.0 - 0.72)
            )

        var incision =
            lat > 0.22
            && lat < 0.72
            && d2 > 0.19
            && d2 < 0.38

        return main || incision
    }

    function buildShell() {
        var nt = 30
        var nl = 18

        var pos = []
        var nrm = []
        var idx = []

        var i
        var j

        for (j = 0; j <= nl; ++j) {
            var lat =
                -Math.PI/2.0
                + j * Math.PI / nl

            for (i = 0; i <= nt; ++i) {
                var theta =
                    i * Math.PI * 2.0 / nt

                var p =
                    shellPoint(theta, lat)

                pos.push(p)
                nrm.push(shellNormal(p))
            }
        }

        function vid(ii, jj) {
            return jj * (nt + 1) + ii
        }

        for (j = 0; j < nl; ++j) {
            var latc =
                -Math.PI/2.0
                + (j + 0.5) * Math.PI / nl

            for (i = 0; i < nt; ++i) {
                var thetac =
                    (i + 0.5)
                    * Math.PI
                    * 2.0
                    / nt

                if (isAperture(thetac, latc))
                    continue

                var a = vid(i, j)
                var b = vid(i + 1, j)
                var c = vid(i + 1, j + 1)
                var d = vid(i, j + 1)

                idx.push(a, b, c)
                idx.push(a, c, d)
            }
        }

        shellGeometry.positions = pos
        shellGeometry.normals = nrm
        shellGeometry.indexes = idx
    }

    function membranePoint(theta, lat) {
        var c = Math.cos(lat)
        var s = Math.sin(lat)

        var m =
            1.0
            + 0.045
            * Math.sin(3.0*theta + 0.5)
            * c*c
            + 0.030
            * Math.cos(2.0*lat - theta)

        return Qt.vector3d(
            78.0*c*Math.cos(theta)*m
                + 4.0*s*Math.sin(theta),

            88.0*s
                * (
                    1.0
                    + 0.025*Math.cos(theta + 0.4)
                ),

            62.0*c*Math.sin(theta)
                * (
                    m
                    + 0.025*Math.sin(2.0*lat)
                )
        )
    }

    function buildMembrane() {
        var nt = 26
        var nl = 16

        var pos = []
        var nrm = []
        var idx = []

        var i
        var j

        for (j = 0; j <= nl; ++j) {
            var lat =
                -Math.PI/2.0
                + j * Math.PI / nl

            for (i = 0; i <= nt; ++i) {
                var theta =
                    i * Math.PI * 2.0 / nt

                var p =
                    membranePoint(theta, lat)

                pos.push(p)

                nrm.push(
                    normalize3(
                        p.x/(78.0*78.0),
                        p.y/(88.0*88.0),
                        p.z/(62.0*62.0)
                    )
                )
            }
        }

        function vid(ii, jj) {
            return jj * (nt + 1) + ii
        }

        for (j = 0; j < nl; ++j) {
            for (i = 0; i < nt; ++i) {
                var a = vid(i, j)
                var b = vid(i + 1, j)
                var c = vid(i + 1, j + 1)
                var d = vid(i, j + 1)

                idx.push(a, b, c)
                idx.push(a, c, d)
            }
        }

        membraneGeometry.positions = pos
        membraneGeometry.normals = nrm
        membraneGeometry.indexes = idx
    }

    function buildLens() {
        var nseg = 36
        var nr = 5

        var pos = [Qt.vector3d(0, 0, 75)]
        var nrm = [Qt.vector3d(0, 0, 1)]
        var idx = []

        var rj
        var i

        for (rj = 1; rj <= nr; ++rj) {
            var rr = rj / nr

            for (i = 0; i < nseg; ++i) {
                var a =
                    Math.PI * 2.0
                    * i
                    / nseg

                var x =
                    54.0
                    * rr
                    * Math.cos(a)

                var y =
                    64.0
                    * rr
                    * Math.sin(a)

                var z =
                    68.0
                    + 7.0*(1.0 - rr*rr)
                    + 2.2*Math.sin(a)*rr

                pos.push(Qt.vector3d(x, y, z))

                nrm.push(
                    normalize3(
                        x/(54.0*54.0),
                        y/(64.0*64.0),
                        1.0/22.0
                    )
                )
            }
        }

        for (i = 0; i < nseg; ++i) {
            idx.push(
                0,
                1 + i,
                1 + ((i + 1) % nseg)
            )
        }

        for (rj = 1; rj < nr; ++rj) {
            var start1 =
                1 + (rj - 1) * nseg

            var start2 =
                1 + rj * nseg

            for (i = 0; i < nseg; ++i) {
                var a1 = start1 + i
                var b1 =
                    start1
                    + ((i + 1) % nseg)

                var c1 =
                    start2
                    + ((i + 1) % nseg)

                var d1 =
                    start2 + i

                idx.push(a1, d1, c1)
                idx.push(a1, c1, b1)
            }
        }

        lensGeometry.positions = pos
        lensGeometry.normals = nrm
        lensGeometry.indexes = idx
    }

    function buildNucleus() {
        var phi =
            (1.0 + Math.sqrt(5.0)) / 2.0

        var raw = [
            [-1, phi, 0],
            [1, phi, 0],
            [-1, -phi, 0],
            [1, -phi, 0],
            [0, -1, phi],
            [0, 1, phi],
            [0, -1, -phi],
            [0, 1, -phi],
            [phi, 0, -1],
            [phi, 0, 1],
            [-phi, 0, -1],
            [-phi, 0, 1]
        ]

        var faces = [
            [0,11,5],[0,5,1],[0,1,7],[0,7,10],[0,10,11],
            [1,5,9],[5,11,4],[11,10,2],[10,7,6],[7,1,8],
            [3,9,4],[3,4,2],[3,2,6],[3,6,8],[3,8,9],
            [4,9,5],[2,4,11],[6,2,10],[8,6,7],[9,8,1]
        ]

        var points = []

        var scale =
            24.0
            / Math.sqrt(
                1.0 + phi*phi
            )

        var i

        for (i = 0; i < raw.length; ++i) {
            points.push(
                Qt.vector3d(
                    raw[i][0] * scale,
                    raw[i][1] * scale,
                    raw[i][2] * scale
                )
            )
        }

        var pos = []
        var nrm = []
        var idx = []

        for (i = 0; i < faces.length; ++i) {
            var p0 = points[faces[i][0]]
            var p1 = points[faces[i][1]]
            var p2 = points[faces[i][2]]

            var ux = p1.x - p0.x
            var uy = p1.y - p0.y
            var uz = p1.z - p0.z

            var vx = p2.x - p0.x
            var vy = p2.y - p0.y
            var vz = p2.z - p0.z

            var nn =
                normalize3(
                    uy*vz - uz*vy,
                    uz*vx - ux*vz,
                    ux*vy - uy*vx
                )

            var base = pos.length

            pos.push(p0, p1, p2)
            nrm.push(nn, nn, nn)
            idx.push(base, base + 1, base + 2)
        }

        nucleusGeometry.positions = pos
        nucleusGeometry.normals = nrm
        nucleusGeometry.indexes = idx
    }

    function buildCustomGeometry() {
        buildShell()
        buildMembrane()
        buildLens()
        buildNucleus()
    }

    Component.onCompleted:
        buildCustomGeometry()

    // ------------------------------------------------------------------------
    // ATMOSPHERE ONLY — DOES NOT PAINT OVER THE 3D OBJECT
    // ------------------------------------------------------------------------
    Canvas {
        id: atmosphere
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var r =
                Math.min(width, height) * 0.135

            ctx.clearRect(0, 0, width, height)

            var g =
                ctx.createRadialGradient(
                    cx,
                    cy,
                    r * 0.35,
                    cx,
                    cy,
                    r * 2.75
                )

            g.addColorStop(
                0.0,
                root.rgbaString(
                    root.coreTone,
                    0.15 * root.glow
                )
            )

            g.addColorStop(
                0.46,
                root.rgbaString(
                    root.coreTone,
                    0.045 * root.glow
                )
            )

            g.addColorStop(
                1.0,
                root.rgbaString(
                    root.coreTone,
                    0.0
                )
            )

            ctx.fillStyle = g
            ctx.beginPath()
            ctx.arc(
                cx,
                cy,
                r * 2.8,
                0,
                Math.PI * 2.0
            )
            ctx.fill()

            if (root.listening) {
                for (var i = 0; i < 2; ++i) {
                    var t =
                        (
                            root.phase
                            / (Math.PI * 2.0)
                            + i * 0.5
                        ) % 1.0

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            r * 0.009
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            root.coreTone,
                            (1.0 - t)
                            * (
                                0.06
                                + root.listenDrive * 0.15
                            )
                        )

                    ctx.beginPath()
                    ctx.arc(
                        cx,
                        cy,
                        r
                        * (
                            1.45
                            + t
                            * (
                                1.00
                                + root.listenDrive * 0.42
                            )
                        ),
                        0,
                        Math.PI * 2.0
                    )
                    ctx.stroke()
                }
            }

            if (root.speaking) {
                for (var s = 0; s < 2; ++s) {
                    var st =
                        (
                            root.phase
                            / (Math.PI * 2.0)
                            + s * 0.5
                        ) % 1.0

                    ctx.lineWidth =
                        Math.max(
                            1.0,
                            r * 0.008
                        )

                    ctx.strokeStyle =
                        root.rgbaString(
                            "#FFD08A",
                            (1.0 - st)
                            * (
                                0.05
                                + root.speechDrive * 0.14
                            )
                        )

                    ctx.beginPath()
                    ctx.arc(
                        cx,
                        cy,
                        r
                        * (
                            1.40
                            + st
                            * (
                                0.95
                                + root.speechDrive * 0.38
                            )
                        ),
                        0,
                        Math.PI * 2.0
                    )
                    ctx.stroke()
                }
            }
        }
    }

    // ========================================================================
    // TRUE 3D FLAGSHIP OBJECT
    // ========================================================================
    View3D {
        id: view3D
        anchors.centerIn: parent
        width: Math.min(root.width, root.height) * 0.72
        height: width

        environment: SceneEnvironment {
            backgroundMode:
                SceneEnvironment.Transparent

            antialiasingMode:
                SceneEnvironment.MSAA

            antialiasingQuality:
                SceneEnvironment.High
        }

        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(0, 0, 335)
            fieldOfView: 38
            clipNear: 1
            clipFar: 1400
        }

        ProceduralMesh {
            id: shellGeometry
            primitiveMode: ProceduralMesh.Triangles
        }

        ProceduralMesh {
            id: membraneGeometry
            primitiveMode: ProceduralMesh.Triangles
        }

        ProceduralMesh {
            id: lensGeometry
            primitiveMode: ProceduralMesh.Triangles
        }

        ProceduralMesh {
            id: nucleusGeometry
            primitiveMode: ProceduralMesh.Triangles
        }

        // --------------------------------------------------------------------
        // MATERIALS
        // --------------------------------------------------------------------
        PrincipledMaterial {
            id: shellMaterial
            baseColor: "#080C12"
            metalness: 0.82
            roughness: 0.23
            clearcoatAmount: 0.58
            clearcoatRoughnessAmount: 0.07

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 0.055,
                    root.coreTone.g * root.glow * 0.055,
                    root.coreTone.b * root.glow * 0.055
                )
        }

        PrincipledMaterial {
            id: shellInnerMaterial
            baseColor: "#030509"
            metalness: 0.46
            roughness: 0.34
            clearcoatAmount: 0.24
            clearcoatRoughnessAmount: 0.12

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 0.025,
                    root.coreTone.g * root.glow * 0.025,
                    root.coreTone.b * root.glow * 0.025
                )
        }

        PrincipledMaterial {
            id: membraneMaterial

            baseColor:
                Qt.rgba(
                    0.04 + root.coreTone.r * 0.20,
                    0.08 + root.coreTone.g * 0.24,
                    0.22 + root.coreTone.b * 0.36,
                    0.82
                )

            metalness: 0.04
            roughness: 0.12
            clearcoatAmount: 0.72
            clearcoatRoughnessAmount: 0.045
            alphaMode: PrincipledMaterial.Blend

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 0.82,
                    root.coreTone.g * root.glow * 0.82,
                    root.coreTone.b * root.glow * 0.82
                )
        }

        PrincipledMaterial {
            id: membraneInnerMaterial
            baseColor: Qt.rgba(0.02, 0.06, 0.22, 0.50)
            metalness: 0.02
            roughness: 0.18
            clearcoatAmount: 0.40
            clearcoatRoughnessAmount: 0.08
            alphaMode: PrincipledMaterial.Blend

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 0.36,
                    root.coreTone.g * root.glow * 0.36,
                    root.coreTone.b * root.glow * 0.36
                )
        }

        PrincipledMaterial {
            id: nucleusMaterial
            baseColor: "#02050A"
            metalness: 0.32
            roughness: 0.14
            clearcoatAmount: 0.66
            clearcoatRoughnessAmount: 0.045

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 1.18,
                    root.coreTone.g * root.glow * 1.18,
                    root.coreTone.b * root.glow * 1.18
                )
        }

        PrincipledMaterial {
            id: nucleusCoreMaterial
            baseColor: root.coldWhite
            metalness: 0.06
            roughness: 0.10
            clearcoatAmount: 0.62
            clearcoatRoughnessAmount: 0.04

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * root.glow * 1.65,
                    root.coreTone.g * root.glow * 1.65,
                    root.coreTone.b * root.glow * 1.65
                )
        }

        PrincipledMaterial {
            id: lensMaterial

            baseColor:
                Qt.rgba(
                    0.12 + root.coreTone.r * 0.06,
                    0.15 + root.coreTone.g * 0.06,
                    0.20 + root.coreTone.b * 0.08,
                    0.18
                )

            metalness: 0.02
            roughness: 0.045
            clearcoatAmount: 0.94
            clearcoatRoughnessAmount: 0.025
            transmissionFactor: 0.76
            alphaMode: PrincipledMaterial.Blend
        }

        PrincipledMaterial {
            id: goldMaterial
            baseColor: root.restrainedGold
            metalness: 0.84
            roughness: 0.18
            clearcoatAmount: 0.40
            clearcoatRoughnessAmount: 0.07

            emissiveFactor:
                Qt.vector3d(
                    root.restrainedGold.r
                    * (
                        root.planning ? 0.48 :
                        root.speaking
                            ? 0.26 + root.speechDrive * 0.22 :
                        root.executing ? 0.26 :
                        0.06
                    ),

                    root.restrainedGold.g
                    * (
                        root.planning ? 0.48 :
                        root.speaking
                            ? 0.26 + root.speechDrive * 0.22 :
                        root.executing ? 0.26 :
                        0.06
                    ),

                    root.restrainedGold.b
                    * (
                        root.planning ? 0.48 :
                        root.speaking
                            ? 0.26 + root.speechDrive * 0.22 :
                        root.executing ? 0.26 :
                        0.06
                    )
                )
        }

        PrincipledMaterial {
            id: particleMaterial
            baseColor: root.coreTone
            metalness: 0.04
            roughness: 0.16

            emissiveFactor:
                Qt.vector3d(
                    root.coreTone.r * 1.48,
                    root.coreTone.g * 1.48,
                    root.coreTone.b * 1.48
                )
        }

        // --------------------------------------------------------------------
        // CINEMATIC LIGHTING
        // --------------------------------------------------------------------
        DirectionalLight {
            eulerRotation: Qt.vector3d(-34, 40, -9)
            color: "#EAF2FF"
            brightness: 2.15
            ambientColor: "#0B111B"
        }

        DirectionalLight {
            eulerRotation: Qt.vector3d(31, -48, 14)
            color: "#718BB2"
            brightness: 0.68
            ambientColor: "#03060B"
        }

        PointLight {
            position: Qt.vector3d(-58, 48, 120)
            color: root.coreTone
            brightness: 1.00 + root.glow * 1.15
            constantFade: 1.0
            linearFade: 0.004
            quadraticFade: 0.000030
        }

        PointLight {
            position: Qt.vector3d(34, -26, -96)
            color: root.deepSapphire
            brightness: 0.14 + root.glow * 0.18
            constantFade: 1.0
            linearFade: 0.006
            quadraticFade: 0.000040
        }

        // ====================================================================
        // ONE COHERENT E.V. OBJECT
        // ====================================================================
        Node {
            id: coreAssembly

            eulerRotation:
                Qt.vector3d(
                    -7.5
                    + root.drift2
                    * 0.35
                    * root.motionGate,

                    -14.0
                    + root.drift
                    * 0.75
                    * root.motionGate,

                    1.5
                    + root.drift2
                    * 0.18
                    * root.motionGate
                )

            // Rear shadow/thickness.
            Model {
                geometry: shellGeometry
                position: Qt.vector3d(0, 0, -7)
                scale: Qt.vector3d(0.955, 0.955, 0.955)
                materials: [shellInnerMaterial]
            }

            // Main custom E.V. shell.
            Model {
                geometry: shellGeometry
                scale: Qt.vector3d(1.0, 1.0, 1.0)
                materials: [shellMaterial]
            }

            // Deep energy membrane.
            Model {
                geometry: membraneGeometry

                position:
                    Qt.vector3d(
                        0,
                        0,
                        -13.0
                        + root.membraneZ * 0.30
                    )

                scale:
                    Qt.vector3d(
                        root.membraneScale * 0.91,
                        root.membraneScale * 0.91,
                        root.membraneScale * 0.91
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.phase * 3.2
                            : root.drift * 0.7,

                        root.planning
                            ? -root.phase * 4.6
                            : root.drift2 * 0.8,

                        0
                    )

                materials: [membraneInnerMaterial]
            }

            // Main living membrane.
            Model {
                geometry: membraneGeometry
                position: Qt.vector3d(0, 0, root.membraneZ)

                scale:
                    Qt.vector3d(
                        root.membraneScale,
                        root.membraneScale,
                        root.membraneScale
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.phase * 5.6
                            : root.drift * 1.1,

                        root.planning
                            ? -root.phase * 7.2
                            : root.drift2 * 1.0,

                        root.failed
                            ? root.drift * 1.8
                            : 0.0
                    )

                materials: [membraneMaterial]
            }

            // Faceted cognition nucleus.
            Node {
                id: nucleusNode

                position:
                    Qt.vector3d(
                        root.executing ? 4.5 : -1.5,

                        root.verifying
                            ? root.drift * 3.2
                            : 1.8,

                        root.nucleusZ
                    )

                eulerRotation:
                    Qt.vector3d(
                        root.phase
                        * (
                            root.planning ? 17.0 :
                            root.executing ? 12.0 :
                            root.verifying ? 8.0 :
                            root.idle ? 1.8 :
                            4.0
                        ),

                        -root.phase
                        * (
                            root.planning ? 23.0 :
                            root.executing ? 16.0 :
                            root.verifying ? 10.0 :
                            root.idle ? 2.2 :
                            5.0
                        ),

                        root.failed
                            ? root.drift2 * 5.0
                            : root.phase * 1.2
                    )

                Model {
                    geometry: nucleusGeometry

                    scale:
                        Qt.vector3d(
                            1.0
                            + root.speechDrive * 0.08,

                            1.0
                            + root.speechDrive * 0.08,

                            1.0
                            + root.speechDrive * 0.08
                        )

                    materials: [nucleusMaterial]
                }

                Model {
                    geometry: nucleusGeometry
                    scale: Qt.vector3d(0.52, 0.52, 0.52)
                    eulerRotation: Qt.vector3d(18, -24, 11)
                    materials: [nucleusCoreMaterial]
                }
            }

            // Sparse internal neural traces only.
            Node {
                id: neuralTraces

                opacity:
                    root.stopped ? 0.0 :
                    root.planning ? 0.78 :
                    root.executing ? 0.52 :
                    root.speaking
                        ? 0.28 + root.speechDrive * 0.30 :
                    root.verifying ? 0.34 :
                    0.10

                eulerRotation:
                    Qt.vector3d(
                        root.planning
                            ? root.drift * 3.0
                            : 0.0,

                        root.planning
                            ? root.phase * 4.2
                            : root.phase * 0.45,

                        0.0
                    )

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(27, 15, 24)
                    eulerRotation: Qt.vector3d(58, -34, 12)
                    scale: Qt.vector3d(0.018, 0.32, 0.018)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(13, 7, 18)
                    eulerRotation: Qt.vector3d(68, -19, 21)
                    scale: Qt.vector3d(0.015, 0.25, 0.015)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(-24, -16, 14)
                    eulerRotation: Qt.vector3d(-48, 44, -12)
                    scale: Qt.vector3d(0.017, 0.33, 0.017)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Cylinder"
                    position: Qt.vector3d(-11, -8, 9)
                    eulerRotation: Qt.vector3d(-64, 26, -19)
                    scale: Qt.vector3d(0.014, 0.23, 0.014)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(18, 10, 21)
                    scale: Qt.vector3d(0.030, 0.030, 0.030)
                    materials: [goldMaterial]
                }

                Model {
                    source: "#Sphere"
                    position: Qt.vector3d(-15, -10, 11)
                    scale: Qt.vector3d(0.027, 0.027, 0.027)
                    materials: [goldMaterial]
                }
            }

            // True XYZ cognition field.
            Repeater3D {
                model: 32

                delegate: Model {
                    property real a:
                        (
                            index / 32.0
                        )
                        * Math.PI
                        * 2.0
                        + root.phase
                        * root.particleSpeed

                    property real band:
                        index % 4

                    property real radius:
                        68.0
                        + band * 11.0
                        - (
                            root.listening
                            ? root.listenDrive * 14.0
                            : 0.0
                        )

                    property real zBase:
                        Math.sin(
                            a * 1.46
                            + index * 0.67
                        )
                        * (
                            44.0
                            + band * 8.0
                        )

                    property real zState:
                        root.executing ? 12.0 :

                        root.verifying
                            ? Math.sin(
                                root.phase * 2.0
                                + index * 0.34
                              )
                              * 18.0 :

                        root.speaking
                            ? Math.sin(
                                a + index * 0.15
                              )
                              * root.speechDrive
                              * 12.0 :

                        root.failed
                            ? Math.sin(
                                index * 1.7
                                + root.phase * 3.0
                              )
                              * 9.0 :

                        0.0

                    source: "#Sphere"

                    position:
                        Qt.vector3d(
                            Math.cos(a) * radius,

                            Math.sin(a)
                            * radius
                            * (
                                0.58
                                + band * 0.035
                            ),

                            zBase + zState
                        )

                    scale:
                        Qt.vector3d(
                            0.013
                            + (index % 4) * 0.004,

                            0.013
                            + (index % 4) * 0.004,

                            0.013
                            + (index % 4) * 0.004
                        )

                    materials: [particleMaterial]
                }
            }

            // Real front lens — shallow and smaller than shell aperture.
            Model {
                geometry: lensGeometry
                position: Qt.vector3d(0, 0, root.lensZ)

                scale:
                    Qt.vector3d(
                        1.0 + root.listenDrive * 0.025,
                        1.0 + root.listenDrive * 0.025,
                        1.0
                    )

                materials: [lensMaterial]
            }
        }
    }

    onPhaseChanged: atmosphere.requestPaint()
    onWidthChanged: atmosphere.requestPaint()
    onHeightChanged: atmosphere.requestPaint()
    onCoreToneChanged: atmosphere.requestPaint()
    onAudioLevelChanged: atmosphere.requestPaint()
    onSpeechLevelChanged: atmosphere.requestPaint()
}
