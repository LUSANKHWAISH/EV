import QtQuick
import QtQuick3D
import "../../theme"

// ============================================================================
// E.V. CORE FLAGSHIP VISUAL PRESET — PRODUCTION ASTRA INTELLIGENCE CORE
// ============================================================================
//
// Translates the approved and locked WebGL ASTRA Intelligence Core specification
// into a high-performance, GPU-instanced QtQuick3D implementation.
//
// VISUAL SPECIFICATION:
// 1. 3D Celestial Intelligence Globe / spherical computational field.
// 2. Hero Stars (~220 total, 154 cool ice-blue + 66 warm champagne/peach glints)
//    distributed along 3 helical surface ribbons with 4-point optical diffraction.
// 3. Misty Dimensional Nucleus with internal stellar cluster, soft Gaussian
//    nebula core, hot spark nucleus, and dynamic voice aura.
// 4. Volumetric Stardust Mantle establishing 3D interior depth.
// 5. Monotonic forward rotation that freezes rock-solid in LISTENING (zero reverse).
// 6. Natural syllabic cadence modulation (3.5 - 5 Hz) during SPEAKING.
// 7. Pure presentation component — zero execution authority.
// ============================================================================

Item {
    id: root
    anchors.fill: parent

    // Host connection for synchronized state and animation clock
    property var host: parent

    // Core state & visual inputs
    property string stateText: host && host.stateText !== undefined ? host.stateText : "IDLE"
    property string visualMode: host && host.visualMode !== undefined ? host.visualMode : "STANDARD"
    property real energy: host && host.energy !== undefined ? host.energy : Theme.stateEnergy(stateText)
    property color stateTone: host && host.stateTone !== undefined ? host.stateTone : Theme.stateColor(stateText)
    property color displayTone: host && host.displayTone !== undefined ? host.displayTone : stateTone

    // Phase clock & audio levels
    property real phase: host && host.phase !== undefined ? host.phase : 0.0
    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0
    property real pulse: host && host.pulse !== undefined ? host.pulse : ((Math.sin(phase) + 1.0) * 0.5)
    property real slowPulse: host && host.slowPulse !== undefined ? host.slowPulse : ((Math.sin(phase * 0.52) + 1.0) * 0.5)
    property real coreBreath: host && host.coreBreath !== undefined ? host.coreBreath : 1.0
    property real glowDrive: host && host.glowDrive !== undefined ? host.glowDrive : 0.58

    // State boolean convenience flags
    readonly property bool idle: stateText === "IDLE"
    readonly property bool listening: stateText === "LISTENING"
    readonly property bool thinking: stateText === "THINKING"
    readonly property bool planning: stateText === "PLANNING"
    readonly property bool executing: stateText === "EXECUTING"
    readonly property bool verifying: stateText === "VERIFYING"
    readonly property bool awaiting: stateText === "APPROVAL" || stateText === "AWAITING_APPROVAL"
    readonly property bool speaking: stateText === "SPEAKING"
    readonly property bool successful: stateText === "SUCCESS"
    readonly property bool failed: stateText === "FAILED"
    readonly property bool sleep: stateText === "SLEEP" || visualMode === "SLEEP"

    // ------------------------------------------------------------------------
    // ASTRA Behavioral Speed & Energy Mapping
    // ------------------------------------------------------------------------
    readonly property real targetStateSpeed: {
        if (root.listening) return 0.0;
        if (root.thinking) return 2.20;
        if (root.executing) return 2.80;
        if (root.verifying) return 1.80;
        if (root.planning) return 1.20;
        if (root.successful) return 1.20;
        if (root.awaiting) return 0.60;
        if (root.failed) return 0.50;
        if (root.speaking) return 0.25;
        if (root.sleep) return 0.08;
        return 1.00; // IDLE
    }

    property real currentSpeed: 1.00
    Behavior on currentSpeed {
        NumberAnimation {
            duration: root.listening ? 120 : 450
            easing.type: root.listening ? Easing.OutCubic : Easing.InOutQuad
        }
    }

    // Monotonic forward rotation accumulator (Freezes cleanly in LISTENING)
    property real rotY: 0.0

    FrameAnimation {
        running: root.visible && root.visualMode !== "SLEEP"
        onTriggered: {
            if (root.currentSpeed > 0.0001) {
                root.rotY = (root.rotY + frameTime * root.currentSpeed * 20.0) % 360.0;
            }
        }
    }

    // ------------------------------------------------------------------------
    // Voice Reactivity & Syllabic Cadence
    // ------------------------------------------------------------------------
    // Syllabic speech cadence (3.5 - 5 Hz modulation)
    readonly property real speechCadence: Math.max(0.0, Math.sin(root.phase * 4.2)) * 0.40 * (0.6 + root.effectiveSpeechLevel * 0.4)

    readonly property real targetVoiceGlow: {
        if (root.listening) {
            return 0.85 + root.effectiveListenLevel * 0.45;
        }
        if (root.speaking) {
            return 0.70 + root.effectiveSpeechLevel * 0.50 + root.speechCadence;
        }
        if (root.effectiveListenLevel > 0.01) {
            return root.effectiveListenLevel * 0.80;
        }
        return 0.0;
    }

    property real voiceGlow: 0.0
    Behavior on voiceGlow {
        NumberAnimation {
            duration: root.listening ? 180 : 250
            easing.type: Easing.OutQuad
        }
    }

    // Interactive mouse orbit tilt with smooth spring physics & idle decay
    property real targetTiltX: 0.0
    property real targetTiltY: 0.0
    property real mouseTiltX: targetTiltX
    property real mouseTiltY: targetTiltY

    Behavior on mouseTiltX {
        SpringAnimation {
            spring: 3.8
            damping: 0.32
            epsilon: 0.005
        }
    }
    Behavior on mouseTiltY {
        SpringAnimation {
            spring: 3.8
            damping: 0.32
            epsilon: 0.005
        }
    }

    Timer {
        id: mouseDecayTimer
        interval: 1400
        repeat: false
        onTriggered: {
            root.targetTiltX = 0.0
            root.targetTiltY = 0.0
        }
    }

    // ------------------------------------------------------------------------
    // 3D Scene Viewport
    // ------------------------------------------------------------------------
    View3D {
        id: view3D
        anchors.fill: parent

        environment: SceneEnvironment {
            backgroundMode: SceneEnvironment.Transparent
            antialiasingMode: SceneEnvironment.MSAA
            antialiasingQuality: SceneEnvironment.High
        }

        // Camera: elevated near-face-on perspective with subtle living breath
        PerspectiveCamera {
            id: camera
            position: Qt.vector3d(
                0,
                4 + Math.cos(root.phase * 0.35) * 1.5,
                255
            )
            fieldOfView: 42
            clipNear: 1.0
            clipFar: 1000.0
        }

        // Central environmental illumination (coreLight)
        PointLight {
            position: Qt.vector3d(0, 0, 0)
            color: root.displayTone
            brightness: 2.2 + (root.energy * 0.6) + (root.voiceGlow * 7.5)
            constantFade: 1.0
            linearFade: 0.008
            quadraticFade: 0.0001
        }

        // Soft celestial rim lights
        DirectionalLight {
            eulerRotation: Qt.vector3d(-25, 45, 0)
            color: "#def2ff"
            brightness: 0.75
        }
        DirectionalLight {
            eulerRotation: Qt.vector3d(35, -45, 0)
            color: "#ffd2a0"
            brightness: 0.35
        }

        // --------------------------------------------------------------------
        // Materials (70% Diamond Ice-Blue, 30% Warm Champagne Palette)
        // --------------------------------------------------------------------
        // 1. Cool Hero Star Material (Brilliant white / diamond ice-blue)
        PrincipledMaterial {
            id: heroCoolMaterial
            baseColor: "#ffffff"
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_hero_star.png") }
            emissiveFactor: Qt.vector3d(2.4, 2.7, 3.2)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // 2. Warm Hero Star Material (Restrained champagne / golden peach)
        PrincipledMaterial {
            id: heroWarmMaterial
            baseColor: "#ffe8d0"
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_hero_star.png") }
            emissiveFactor: Qt.vector3d(2.8, 2.2, 1.7)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // 3. Stardust Dot Material (Mantle, atmospheric dust, nucleus points)
        PrincipledMaterial {
            id: stardustMaterial
            baseColor: "#def2ff"
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_stardust_dot.png") }
            emissiveFactor: Qt.vector3d(1.8, 2.0, 2.4)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // 4. Soft Translucent Nebular Core Material
        PrincipledMaterial {
            id: nebulaCoreMaterial
            baseColor: root.displayTone
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_nebula_glow.png") }
            emissiveFactor: Qt.vector3d(
                1.5 + root.voiceGlow * 1.5,
                1.8 + root.voiceGlow * 1.8,
                2.2 + root.voiceGlow * 2.2
            )
            opacity: Math.min(1.0, 0.55 + root.voiceGlow * 0.40)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // 5. Hot Inner Spark Nucleus Material
        PrincipledMaterial {
            id: innerSparkMaterial
            baseColor: "#ffffff"
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_nebula_glow.png") }
            emissiveFactor: Qt.vector3d(
                3.2 + root.voiceGlow * 3.0,
                3.4 + root.voiceGlow * 3.0,
                3.8 + root.voiceGlow * 3.0
            )
            opacity: Math.min(1.0, 0.80 + root.voiceGlow * 0.20)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // 6. Wide Voice Aura Material (Expands and glows dynamically with voice)
        PrincipledMaterial {
            id: voiceAuraMaterial
            baseColor: root.displayTone
            baseColorMap: Texture { source: Qt.resolvedUrl("../../assets/astra_nebula_glow.png") }
            emissiveFactor: Qt.vector3d(1.4, 1.7, 2.2)
            opacity: Math.min(0.85, root.voiceGlow * 0.75)
            alphaMode: PrincipledMaterial.Blend
            cullMode: Material.NoCulling
            lighting: PrincipledMaterial.NoLighting
            depthDrawMode: Material.NeverDepthDraw
        }

        // --------------------------------------------------------------------
        // Stationary Optical Nucleus (Faces Camera at All Times)
        // --------------------------------------------------------------------
        Node {
            id: opticalNucleusNode
            position: Qt.vector3d(0, 0, 0)

            // Wide Voice Aura (Blooms dramatically on voice/listening)
            Model {
                source: "#Rectangle"
                materials: [voiceAuraMaterial]
                scale: Qt.vector3d(
                    1.20 + root.voiceGlow * 0.85,
                    1.20 + root.voiceGlow * 0.85,
                    1.0
                )
            }

            // Soft Translucent Gaussian Nebular Core
            Model {
                source: "#Rectangle"
                materials: [nebulaCoreMaterial]
                scale: Qt.vector3d(
                    (0.72 + root.voiceGlow * 0.40) * (1.0 + Math.sin(root.phase) * 0.025),
                    (0.72 + root.voiceGlow * 0.40) * (1.0 + Math.sin(root.phase) * 0.025),
                    1.0
                )
            }

            // Hot Inner Spark Nucleus
            Model {
                source: "#Rectangle"
                materials: [innerSparkMaterial]
                scale: Qt.vector3d(
                    0.28 + root.voiceGlow * 0.22,
                    0.28 + root.voiceGlow * 0.22,
                    1.0
                )
            }
        }

        // --------------------------------------------------------------------
        // Celestial Globe Orb Root (Rotates continuously, freezes in LISTENING)
        // --------------------------------------------------------------------
        Node {
            id: globeNode
            eulerRotation: Qt.vector3d(
                root.mouseTiltX,
                root.rotY + root.mouseTiltY,
                0
            )

            // Dynamic scale driven by audio and breathing
            property real orbBreath: 1.0 + Math.sin(root.phase * 0.8) * 0.015 + (root.voiceGlow * 0.05)
            scale: Qt.vector3d(orbBreath, orbBreath, orbBreath)

            // ----------------------------------------------------------------
            // 1. Hero Stars (220 Total, 154 Ice-Blue + 66 Warm Champagne)
            // Rendered with dual-plane cross jewel quads so star glints remain
            // luminous and perfectly optical from all 3D spherical viewing angles.
            // ----------------------------------------------------------------
            // Cool Hero Stars — Primary Quad (Z-plane)
            Model {
                id: heroCoolStars
                source: "#Rectangle"
                scale: Qt.vector3d(0.044, 0.044, 0.044)
                materials: [heroCoolMaterial]

                instancing: InstanceList {
                    id: coolInstances
                    Component.onCompleted: {
                        function rng(s) {
                            return function() {
                                s = (s * 1664525 + 1013904223) & 0xffffffff;
                                return (s >>> 0) / 4294967296.0;
                            };
                        }
                        var r1 = rng(101);
                        for (var i = 0; i < 154; i++) {
                            var u = i / 154.0;
                            var phi = 0.12 * Math.PI + u * 0.76 * Math.PI + (r1() - 0.5) * 0.06;
                            var ribbon = i % 3;
                            var theta = ribbon * (Math.PI * 2.0 / 3.0) + 3.2 * phi + (r1() - 0.5) * 0.08;
                            var r = 68.0 * (0.97 + r1() * 0.06);
                            var x = r * Math.sin(phi) * Math.cos(theta);
                            var y = r * Math.cos(phi);
                            var z = r * Math.sin(phi) * Math.sin(theta);

                            var s = 0.85 + r1() * 0.35;
                            var entry = Qt.createQmlObject(
                                'import QtQuick3D; InstanceListEntry { position: Qt.vector3d(' + x.toFixed(2) + ',' + y.toFixed(2) + ',' + z.toFixed(2) + '); scale: Qt.vector3d(' + s.toFixed(2) + ',' + s.toFixed(2) + ',' + s.toFixed(2) + ') }',
                                coolInstances
                            );
                            if (entry) instances.push(entry);
                        }
                    }
                }
            }

            // Cool Hero Stars — Orthogonal Cross Quad (X-plane for full 3D glint)
            Model {
                id: heroCoolStarsCross
                source: "#Rectangle"
                eulerRotation: Qt.vector3d(0, 90, 0)
                scale: Qt.vector3d(0.044, 0.044, 0.044)
                materials: [heroCoolMaterial]
                instancing: coolInstances
            }

            // Warm Hero Stars — Primary Quad (Z-plane)
            Model {
                id: heroWarmStars
                source: "#Rectangle"
                scale: Qt.vector3d(0.044, 0.044, 0.044)
                materials: [heroWarmMaterial]

                instancing: InstanceList {
                    id: warmInstances
                    Component.onCompleted: {
                        function rng(s) {
                            return function() {
                                s = (s * 1664525 + 1013904223) & 0xffffffff;
                                return (s >>> 0) / 4294967296.0;
                            };
                        }
                        var r2 = rng(202);
                        for (var i = 0; i < 66; i++) {
                            var u = i / 66.0;
                            var phi = 0.15 * Math.PI + u * 0.70 * Math.PI + (r2() - 0.5) * 0.06;
                            var ribbon = (i + 1) % 3;
                            var theta = ribbon * (Math.PI * 2.0 / 3.0) + 3.2 * phi + 0.35 + (r2() - 0.5) * 0.08;
                            var r = 68.0 * (0.97 + r2() * 0.06);
                            var x = r * Math.sin(phi) * Math.cos(theta);
                            var y = r * Math.cos(phi);
                            var z = r * Math.sin(phi) * Math.sin(theta);

                            var s = 0.85 + r2() * 0.35;
                            var entry = Qt.createQmlObject(
                                'import QtQuick3D; InstanceListEntry { position: Qt.vector3d(' + x.toFixed(2) + ',' + y.toFixed(2) + ',' + z.toFixed(2) + '); scale: Qt.vector3d(' + s.toFixed(2) + ',' + s.toFixed(2) + ',' + s.toFixed(2) + ') }',
                                warmInstances
                            );
                            if (entry) instances.push(entry);
                        }
                    }
                }
            }

            // Warm Hero Stars — Orthogonal Cross Quad (X-plane for full 3D glint)
            Model {
                id: heroWarmStarsCross
                source: "#Rectangle"
                eulerRotation: Qt.vector3d(0, 90, 0)
                scale: Qt.vector3d(0.044, 0.044, 0.044)
                materials: [heroWarmMaterial]
                instancing: warmInstances
            }

            // ----------------------------------------------------------------
            // 2. True 3D Spherical Surface Shell & Mantle Layer (450 Stars)
            // ----------------------------------------------------------------
            Model {
                id: mantleStars
                source: "#Rectangle"
                scale: Qt.vector3d(0.045, 0.045, 0.045)
                materials: [stardustMaterial]

                instancing: InstanceList {
                    id: mantleInstances
                    Component.onCompleted: {
                        function rng(s) {
                            return function() {
                                s = (s * 1664525 + 1013904223) & 0xffffffff;
                                return (s >>> 0) / 4294967296.0;
                            };
                        }
                        var r3 = rng(303);
                        for (var i = 0; i < 450; i++) {
                            var r;
                            if (r3() < 0.70) {
                                r = 68.0 * (0.88 + r3() * 0.16);
                            } else {
                                r = 18.0 + r3() * (68.0 * 0.88 - 18.0);
                            }
                            var phi = Math.acos(2.0 * r3() - 1.0);
                            var theta = r3() * Math.PI * 2.0;

                            var x = r * Math.sin(phi) * Math.cos(theta);
                            var y = r * Math.cos(phi);
                            var z = r * Math.sin(phi) * Math.sin(theta);

                            var s = 0.50 + r3() * 0.35;
                            var entry = Qt.createQmlObject(
                                'import QtQuick3D; InstanceListEntry { position: Qt.vector3d(' + x.toFixed(2) + ',' + y.toFixed(2) + ',' + z.toFixed(2) + '); scale: Qt.vector3d(' + s.toFixed(2) + ',' + s.toFixed(2) + ',' + s.toFixed(2) + ') }',
                                mantleInstances
                            );
                            if (entry) instances.push(entry);
                        }
                    }
                }
            }

            // ----------------------------------------------------------------
            // 3. True 3D Volumetric Nucleus Cluster (250 Tiny Stars, Radius <= 18.0)
            // ----------------------------------------------------------------
            Model {
                id: nucleusCluster
                source: "#Rectangle"
                scale: Qt.vector3d(0.038, 0.038, 0.038)
                materials: [stardustMaterial]

                instancing: InstanceList {
                    id: nucleusInstances
                    Component.onCompleted: {
                        function rng(s) {
                            return function() {
                                s = (s * 1664525 + 1013904223) & 0xffffffff;
                                return (s >>> 0) / 4294967296.0;
                            };
                        }
                        var r4 = rng(404);
                        for (var i = 0; i < 250; i++) {
                            var r = 18.0 * Math.cbrt(r4());
                            var phi = Math.acos(2.0 * r4() - 1.0);
                            var theta = r4() * Math.PI * 2.0;

                            var x = r * Math.sin(phi) * Math.cos(theta);
                            var y = r * Math.cos(phi);
                            var z = r * Math.sin(phi) * Math.sin(theta);

                            var s = 0.40 + r4() * 0.30;
                            var entry = Qt.createQmlObject(
                                'import QtQuick3D; InstanceListEntry { position: Qt.vector3d(' + x.toFixed(2) + ',' + y.toFixed(2) + ',' + z.toFixed(2) + '); scale: Qt.vector3d(' + s.toFixed(2) + ',' + s.toFixed(2) + ',' + s.toFixed(2) + ') }',
                                nucleusInstances
                            );
                            if (entry) instances.push(entry);
                        }
                    }
                }
            }

            // ----------------------------------------------------------------
            // 4. True 3D Volumetric Atmospheric Stardust Crust (350 Stars)
            // ----------------------------------------------------------------
            Model {
                id: atmosphericDust
                source: "#Rectangle"
                scale: Qt.vector3d(0.035, 0.035, 0.035)
                materials: [stardustMaterial]

                instancing: InstanceList {
                    id: atmosphericInstances
                    Component.onCompleted: {
                        function rng(s) {
                            return function() {
                                s = (s * 1664525 + 1013904223) & 0xffffffff;
                                return (s >>> 0) / 4294967296.0;
                            };
                        }
                        var r5 = rng(505);
                        for (var i = 0; i < 350; i++) {
                            var p = r5();
                            var r;
                            if (p < 0.60) {
                                r = 68.0 * (0.86 + r5() * 0.18);
                            } else if (p < 0.85) {
                                r = 18.0 + r5() * (68.0 * 0.86 - 18.0);
                            } else {
                                r = 18.0 * Math.cbrt(r5());
                            }
                            var phi = Math.acos(2.0 * r5() - 1.0);
                            var theta = r5() * Math.PI * 2.0;

                            var x = r * Math.sin(phi) * Math.cos(theta);
                            var y = r * Math.cos(phi);
                            var z = r * Math.sin(phi) * Math.sin(theta);

                            var s = 0.35 + r5() * 0.30;
                            var entry = Qt.createQmlObject(
                                'import QtQuick3D; InstanceListEntry { position: Qt.vector3d(' + x.toFixed(2) + ',' + y.toFixed(2) + ',' + z.toFixed(2) + '); scale: Qt.vector3d(' + s.toFixed(2) + ',' + s.toFixed(2) + ',' + s.toFixed(2) + ') }',
                                atmosphericInstances
                            );
                            if (entry) instances.push(entry);
                        }
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // Interactive Mouse Orbit Tracking & Spring-Back Area
    // ------------------------------------------------------------------------
    MouseArea {
        id: mouseControl
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        preventStealing: false
        propagateComposedEvents: true

        onPositionChanged: function(mouse) {
            var cx = root.width * 0.5;
            var cy = root.height * 0.5;
            if (cx <= 0 || cy <= 0) return;
            var dx = Math.max(-1.0, Math.min(1.0, (mouse.x - cx) / cx));
            var dy = Math.max(-1.0, Math.min(1.0, (mouse.y - cy) / cy));

            // Organic elastic magnetic tilt (+/- 14 degrees)
            root.targetTiltY = dx * 14.0;
            root.targetTiltX = -dy * 14.0;
            mouseDecayTimer.restart();
        }

        onExited: {
            root.targetTiltX = 0.0;
            root.targetTiltY = 0.0;
        }

        onReleased: {
            root.targetTiltX = 0.0;
            root.targetTiltY = 0.0;
        }
    }
}
