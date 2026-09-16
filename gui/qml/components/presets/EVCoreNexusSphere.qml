import QtQuick 2.15
import QtQuick.Controls 2.15
import "../../theme"

// ============================================================================
// E.V. — NEXUS SPHERE CORE (AUTHORITATIVE FIRST CORE VISUAL PRESET)
// ============================================================================
//
// Pure presentation component implementing the original Nexus Sphere Core
// from authoritative prototype 'ev-core.html' as a seamless visual preset
// inside the E.V. Flagship stage.
//
// VISUAL ARCHITECTURE CONTRACT:
// 1. Pure Visual Preset: Renders the central 3D projective sphere core.
// 2. Seamless Integration: Transparent background — zero rectangular cutoff boxes.
// 3. Clean Interface: Zero duplicate chrome, corner brackets, headers, or buttons.
// 4. Single Core Discipline: Managed exclusively by EVIntelligenceCore Loader.
// 5. Zero Authority: Pure presentation — zero execution capability.
// ============================================================================

Item {
    id: root
    anchors.fill: parent

    // Host connection (from EVIntelligenceCore Loader)
    property var host: parent

    // State & Presentation contract
    property string stateText: (host && host.stateText !== undefined) ? host.stateText : "IDLE"
    property string visualMode: (host && host.visualMode !== undefined) ? host.visualMode : "STANDARD"
    property real energy: (host && host.energy !== undefined) ? host.energy : Theme.stateEnergy(stateText)
    property color stateTone: (host && host.stateTone !== undefined) ? host.stateTone : Theme.stateColor(stateText)
    property color displayTone: (host && host.displayTone !== undefined) ? host.displayTone : stateTone

    // Voice & Audio presentation inputs from host / bridge
    property real audioLevel: (host && host.effectiveListenLevel !== undefined)
        ? host.effectiveListenLevel
        : ((typeof guiBridge !== "undefined" && guiBridge && guiBridge.voiceLevel) ? guiBridge.voiceLevel : 0.0)
    property real speechLevel: (host && host.effectiveSpeechLevel !== undefined)
        ? host.effectiveSpeechLevel
        : ((typeof guiBridge !== "undefined" && guiBridge && guiBridge.speechLevel) ? guiBridge.speechLevel : 0.0)

    // State convenience flags
    readonly property bool isListening: stateText === "LISTENING"
    readonly property bool isSpeaking: stateText === "SPEAKING" || (typeof guiBridge !== "undefined" && guiBridge && guiBridge.speakingActivity)
    readonly property bool isExecuting: stateText === "EXECUTING"
    readonly property bool isPlanning: stateText === "PLANNING" || stateText === "THINKING"
    readonly property bool isVerifying: stateText === "VERIFYING"
    readonly property bool isAwaiting: stateText === "APPROVAL" || stateText === "AWAITING_APPROVAL"
    readonly property bool isFailed: stateText === "FAILED"
    readonly property bool isSleep: stateText === "SLEEP" || visualMode === "SLEEP"

    // Authoritative Audio FFT and Speech Synthesis specifications
    readonly property int fftSize: 512
    readonly property real ttsRate: 0.88
    readonly property real ttsPitch: 0.8
    readonly property real ttsVolume: 1.0

    // Interactive & Dynamics state
    property real surgeLevel: 0.0
    property real spkAmp: 0.0
    property real spkPhase: 0.0
    property int spkBolts: 0
    property real micAmplitude: 0.0

    // 3D Orientation & Dynamics (authoritative initial orientation)
    property real rotX: 0.32
    property real rotY: 0.0
    property real velX: 0.0
    property real velY: 0.0
    property bool isDragging: false
    property real prevMouseX: 0.0
    property real prevMouseY: 0.0
    property bool autoSpin: true
    property real animTime: 0.0
    property real breatheTime: 0.0
    property real ot1: 0.0
    property real ot2: 0.0

    // Auto-spin restore timer after drag inertia
    Timer {
        id: autoSpinRestoreTimer
        interval: 2400
        repeat: false
        onTriggered: {
            if (!root.isDragging) {
                root.autoSpin = true;
            }
        }
    }

    // Interactive Surge trigger method
    function triggerSurge() {
        root.surgeLevel = 1.0;
    }

    // ========================================================================
    // 3D PROJECTIVE NEXUS SPHERE CORE CANVAS (THE ENGINE)
    // ========================================================================
    // Renders on a completely transparent background, seamlessly blending
    // into the E.V. Flagship stage without hard borders or rectangular edges.
    Canvas {
        id: coreCanvas
        anchors.fill: parent
        renderTarget: Canvas.FramebufferObject
        renderStrategy: Canvas.Cooperative

        // Authoritative definition of the 9 orbital rings
        readonly property var ringsDefinition: [
            { r: 0.52, tx: 0,     ty: 0,     spd: 0.013,  c: [0, 222, 255], lw: 2.8 },
            { r: 0.52, tx: 1.571, ty: 0,     spd: -0.010, c: [0, 200, 255], lw: 2.4 },
            { r: 0.52, tx: 1.047, ty: 0,     spd: 0.011,  c: [20, 215, 255], lw: 2.2 },
            { r: 0.52, tx: 0.785, ty: 1.047, spd: -0.011, c: [0, 212, 255], lw: 2.0 },
            { r: 0.82, tx: 0.524, ty: 0,     spd: 0.006,  c: [0, 165, 255], lw: 1.6 },
            { r: 0.82, tx: -0.785,ty: 0.785, spd: -0.007, c: [0, 155, 255], lw: 1.5 },
            { r: 0.82, tx: 1.571, ty: 0.524, spd: 0.005,  c: [0, 175, 255], lw: 1.4 },
            { r: 1.10, tx: 0,     ty: 0,     spd: 0.003,  c: [0, 105, 225], lw: 1.0 },
            { r: 1.10, tx: 1.047, ty: 0.262, spd: -0.004, c: [0, 95, 215],  lw: 0.85 }
        ]

        property var ringsState: []
        property var boltsList: []
        property var particlesList: []
        property var starsData: []
        property int boltTimerCount: 0

        readonly property var nodeAngles: [0, Math.PI * 0.5, Math.PI, Math.PI * 1.5]

        Component.onCompleted: {
            // Initialize 9 rings with random phases matching prototype
            var arr = [];
            for (var i = 0; i < ringsDefinition.length; i++) {
                var def = ringsDefinition[i];
                arr.push({
                    r: def.r,
                    tx: def.tx,
                    ty: def.ty,
                    spd: def.spd,
                    c: def.c,
                    lw: def.lw,
                    ph: Math.random() * Math.PI * 2
                });
            }
            ringsState = arr;

            // Precompute stars with normalized coordinates
            var stars = [];
            for (var s = 0; s < 180; s++) {
                stars.push({
                    x: Math.random(),
                    y: Math.random(),
                    r: Math.random() * 1.3 + 0.3,
                    a: Math.random()
                });
            }
            starsData = stars;
        }

        function projectPoint(x, y, z, CX, CY, W, H) {
            var rx = root.rotX;
            var ry = root.rotY;
            var y1 = y * Math.cos(rx) - z * Math.sin(rx);
            var z1 = y * Math.sin(rx) + z * Math.cos(rx);
            var x2 = x * Math.cos(ry) + z1 * Math.sin(ry);
            var z2 = -x * Math.sin(ry) + z1 * Math.cos(ry);
            var SZ = Math.min(W, H) * 0.38 * (1 + Math.sin(root.breatheTime) * 0.028);
            var D = 5.0;
            var sc = D / (D + z2 + 4.0);
            return {
                sx: CX + x2 * sc * SZ,
                sy: CY + y1 * sc * SZ,
                sz: z2
            };
        }

        function getRingPt(ring, angle, CX, CY, W, H) {
            var lt = angle + ring.ph;
            var x = Math.cos(lt) * ring.r;
            var y = 0.0;
            var z = Math.sin(lt) * ring.r;

            var y1 = y * Math.cos(ring.tx) - z * Math.sin(ring.tx);
            var z1 = y * Math.sin(ring.tx) + z * Math.cos(ring.tx);

            var x2 = x * Math.cos(ring.ty) + z1 * Math.sin(ring.ty);
            var z2 = -x * Math.sin(ring.ty) + z1 * Math.cos(ring.ty);

            return projectPoint(x2, y1, z2, CX, CY, W, H);
        }

        function getRingPts(ring, N, CX, CY, W, H) {
            var pts = [];
            for (var i = 0; i <= N; i++) {
                pts.push(getRingPt(ring, (i / N) * Math.PI * 2, CX, CY, W, H));
            }
            return pts;
        }

        function spawnBolt(p1, p2) {
            boltsList.push({
                x1: p1.sx,
                y1: p1.sy,
                x2: p2.sx,
                y2: p2.sy,
                life: 1.0,
                d: 0.04 + Math.random() * 0.06
            });
        }

        function drawFractalBolt(ctx, x1, y1, x2, y2, r, dep) {
            if (dep <= 0) {
                ctx.lineTo(x2, y2);
                return;
            }
            var mx = (x1 + x2) * 0.5 + (Math.random() - 0.5) * r;
            var my = (y1 + y2) * 0.5 + (Math.random() - 0.5) * r;
            drawFractalBolt(ctx, x1, y1, mx, my, r * 0.52, dep - 1);
            if (dep > 2 && Math.random() < 0.3) {
                var bx = mx + (Math.random() - 0.5) * r * 1.4;
                var by = my + (Math.random() - 0.5) * r * 1.4;
                ctx.save();
                ctx.globalAlpha *= 0.4;
                ctx.lineWidth *= 0.55;
                ctx.beginPath();
                ctx.moveTo(mx, my);
                drawFractalBolt(ctx, mx, my, bx, by, r * 0.38, dep - 2);
                ctx.stroke();
                ctx.restore();
                ctx.beginPath();
                ctx.moveTo(mx, my);
            }
            drawFractalBolt(ctx, mx, my, x2, y2, r * 0.52, dep - 1);
        }

        function spawnParticle(x, y, boost) {
            var a = Math.random() * Math.PI * 2;
            var sp = 0.3 + Math.random() * 2.2 + (boost || 0);
            particlesList.push({
                x: x,
                y: y,
                vx: Math.cos(a) * sp,
                vy: Math.sin(a) * sp - 0.22,
                life: 1.0,
                d: 0.013 + Math.random() * 0.02,
                sz: Math.random() * 2.5 + 0.6
            });
        }

        function drawHexGrid(ctx, cx, cy, r) {
            ctx.save();
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.clip();
            ctx.translate(cx, cy);
            ctx.rotate(root.animTime * 0.07);

            var hr = r * 0.125;
            var hh = hr * 1.732;
            ctx.strokeStyle = "rgba(0, 200, 255, 0.10)";
            ctx.lineWidth = 0.55;

            for (var row = -7; row <= 7; row++) {
                for (var col = -7; col <= 7; col++) {
                    var hx = col * hh * 2 + (row % 2) * hh;
                    var hy = row * hr * 1.5;
                    if (Math.hypot(hx, hy) > r * 1.05) continue;
                    ctx.beginPath();
                    for (var i = 0; i < 6; i++) {
                        var a = (i / 6.0) * Math.PI * 2 + Math.PI / 6.0;
                        var px = hx + hr * 0.9 * Math.cos(a);
                        var py = hy + hr * 0.9 * Math.sin(a);
                        if (i === 0) ctx.moveTo(px, py);
                        else ctx.lineTo(px, py);
                    }
                    ctx.closePath();
                    ctx.stroke();
                }
            }
            ctx.restore();
        }

        function drawSphere(ctx, CX, CY, W, H, sg, amp, sAmp) {
            var totalAmp = Math.max(amp, sAmp);
            var SPH = Math.min(W, H) * 0.118 * (1 + Math.sin(root.breatheTime) * 0.03 + sAmp * 0.04);

            // Speak outer corona
            if (sAmp > 0.05) {
                var sc = ctx.createRadialGradient(CX, CY, SPH * 0.8, CX, CY, SPH * (3.5 + sAmp * 3));
                sc.addColorStop(0, "rgba(0,160,255," + (sAmp * 0.55) + ")");
                sc.addColorStop(0.5, "rgba(0,80,220," + (sAmp * 0.22) + ")");
                sc.addColorStop(1, "rgba(0,0,0,0)");
                ctx.beginPath();
                ctx.arc(CX, CY, SPH * (3.5 + sAmp * 3), 0, Math.PI * 2);
                ctx.fillStyle = sc;
                ctx.fill();
            }

            // Normal outer bloom (radial falloff dissolves cleanly into transparent background)
            var og = ctx.createRadialGradient(CX, CY, 0, CX, CY, SPH * 5.5);
            og.addColorStop(0, "rgba(0,110,255," + (0.12 + sg * 0.16 + totalAmp * 0.12) + ")");
            og.addColorStop(0.4, "rgba(0,55,200," + (0.05 + sg * 0.05 + sAmp * 0.06) + ")");
            og.addColorStop(1, "rgba(0,0,0,0)");
            ctx.beginPath();
            ctx.arc(CX, CY, SPH * 5.5, 0, Math.PI * 2);
            ctx.fillStyle = og;
            ctx.fill();

            // Rotating Hex Grid
            drawHexGrid(ctx, CX, CY, SPH * 0.97);

            // Main sphere body with multi-stop radial gradient
            ctx.save();
            var mg = ctx.createRadialGradient(CX - SPH * 0.22, CY - SPH * 0.22, 0, CX, CY, SPH);
            mg.addColorStop(0, "rgba(255,255,255,0.97)");
            mg.addColorStop(0.06, "rgba(230,248,255,0.91)");
            var rVal = 80 + Math.round(sAmp * 60);
            var gVal = 205 - Math.round(sAmp * 20);
            mg.addColorStop(0.22, "rgba(" + rVal + "," + gVal + ",255,0.83)");
            var midG = 135 + Math.round(totalAmp * 80);
            var midA = 0.65 + sg * 0.25 + totalAmp * 0.22;
            mg.addColorStop(0.48, "rgba(0," + midG + ",255," + midA + ")");
            mg.addColorStop(0.78, "rgba(0,42,185,0.30)");
            mg.addColorStop(1, "rgba(0,0,12,0.0)");
            ctx.beginPath();
            ctx.arc(CX, CY, SPH, 0, Math.PI * 2);
            ctx.fillStyle = mg;
            ctx.fill();
            ctx.restore();

            // Specular highlight
            ctx.save();
            var spec = ctx.createRadialGradient(CX - SPH * 0.32, CY - SPH * 0.32, 0, CX - SPH * 0.18, CY - SPH * 0.18, SPH * 0.6);
            spec.addColorStop(0, "rgba(255,255,255,0.48)");
            spec.addColorStop(0.5, "rgba(200,240,255,0.10)");
            spec.addColorStop(1, "rgba(0,0,0,0)");
            ctx.beginPath();
            ctx.arc(CX, CY, SPH, 0, Math.PI * 2);
            ctx.fillStyle = spec;
            ctx.fill();
            ctx.restore();

            // Central spark (white-hot)
            ctx.save();
            ctx.fillStyle = "rgba(255,255,255,0.96)";
            ctx.beginPath();
            ctx.arc(CX, CY, 4.5 + sg * 5 + sAmp * 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();

            // Speak-reactive ripple rings
            if (sAmp > 0.08) {
                for (var ri = 0; ri < 3; ri++) {
                    var rr = SPH * (1.2 + ri * 0.5 + ((root.animTime * 3 + ri * 2.1) % 3) * 0.4) * (0.5 + sAmp * 0.7);
                    ctx.save();
                    var ripAlpha = Math.max(0, sAmp - 0.15 * (ri + 1)) * 0.6;
                    ctx.strokeStyle = "rgba(0,180,255," + ripAlpha + ")";
                    ctx.lineWidth = Math.max(0.5, 1.5 - ri * 0.4);
                    ctx.beginPath();
                    ctx.arc(CX, CY, rr, 0, Math.PI * 2);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        }

        function drawRingHalf(ctx, ring, pts, back, sAmp) {
            var cr = ring.c[0];
            var cg = ring.c[1];
            var cb = ring.c[2];
            var boost = sAmp * 0.4;
            var alpha = back ? 0.20 : (0.90 + boost * 0.08);
            var lw = back ? (ring.lw * 0.38) : (ring.lw * (1.0 + boost * 0.30));

            ctx.save();
            ctx.strokeStyle = "rgba(" + cr + "," + cg + "," + cb + "," + Math.min(1.0, alpha) + ")";
            ctx.lineWidth = lw;
            ctx.lineCap = "round";
            ctx.beginPath();

            for (var i = 0; i < pts.length - 1; i++) {
                var p1 = pts[i];
                var p2 = pts[i + 1];
                if ((p1.sz > 0) === back && (p2.sz > 0) === back) {
                    ctx.moveTo(p1.sx, p1.sy);
                    ctx.lineTo(p2.sx, p2.sy);
                }
            }
            ctx.stroke();
            ctx.restore();
        }

        function drawRingNodes(ctx, ring, sg, sAmp) {
            var cr = ring.c[0];
            var cg = ring.c[1];
            var cb = ring.c[2];

            for (var i = 0; i < nodeAngles.length; i++) {
                var na = nodeAngles[i];
                var p = getRingPt(ring, na, width * 0.5, height * 0.5, width, height);
                if (p.sz > 0.1) continue;

                ctx.save();
                var fillR = Math.min(255, cr + 80);
                var fillG = Math.min(255, cg + 80);
                var fillB = Math.min(255, cb + 60);
                ctx.fillStyle = "rgba(" + fillR + "," + fillG + "," + fillB + ",0.95)";
                ctx.beginPath();
                ctx.arc(p.sx, p.sy, 3.5 + sg * 2 + sAmp * 2, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = "rgba(" + cr + "," + cg + "," + cb + ",0.45)";
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.arc(p.sx, p.sy, 6.0 + sg * 4 + sAmp * 3, 0, Math.PI * 2);
                ctx.stroke();
                ctx.restore();
            }
        }

        function drawOrbits(ctx, CX, CY, W, H) {
            var SZ = Math.min(W, H) * 0.38;

            // Orbit guide 1
            ctx.save();
            ctx.translate(CX, CY);
            ctx.rotate(root.ot1);
            ctx.beginPath();
            ctx.ellipse(0, 0, SZ * 0.54, SZ * 0.54 * 0.32, Math.PI * 0.2, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(0, 100, 255, 0.12)";
            ctx.lineWidth = 0.7;
            ctx.stroke();

            var dx = Math.cos(root.ot1 * 4) * SZ * 0.54;
            var dy = Math.sin(root.ot1 * 4) * SZ * 0.54 * 0.32;
            ctx.fillStyle = "rgba(0, 200, 255, 0.75)";
            ctx.beginPath();
            ctx.arc(dx, dy, 2.5, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();

            // Orbit guide 2
            ctx.save();
            ctx.translate(CX, CY);
            ctx.rotate(root.ot2 + 1.2);
            ctx.beginPath();
            ctx.ellipse(0, 0, SZ * 0.84, SZ * 0.84 * 0.26, Math.PI * 0.5, 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(80, 0, 200, 0.10)";
            ctx.lineWidth = 0.6;
            ctx.stroke();

            var dx2 = Math.cos(root.ot2 * 3) * SZ * 0.84;
            var dy2 = Math.sin(root.ot2 * 3) * SZ * 0.84 * 0.26;
            ctx.fillStyle = "rgba(130, 60, 255, 0.75)";
            ctx.beginPath();
            ctx.arc(dx2, dy2, 2.0, 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
        }

        function drawBeams(ctx, CX, CY, W, H, sg, amp, sAmp) {
            var totalA = Math.max(amp, sAmp);
            for (var rIdx = 0; rIdx < ringsState.length; rIdx++) {
                var ring = ringsState[rIdx];
                var angles = [0, Math.PI];
                for (var aIdx = 0; aIdx < angles.length; aIdx++) {
                    var na = angles[aIdx];
                    var p = getRingPt(ring, na, CX, CY, W, H);
                    if (p.sz > 0) continue;

                    var ba = 0.10 + sg * 0.28 + totalA * 0.12;
                    var gr = ctx.createLinearGradient(CX, CY, p.sx, p.sy);
                    gr.addColorStop(0, "rgba(255,255,255," + (ba * 0.9) + ")");
                    gr.addColorStop(0.4, "rgba(0,180,255," + (ba * 0.5) + ")");
                    gr.addColorStop(1, "rgba(0,80,200,0)");

                    ctx.save();
                    ctx.strokeStyle = gr;
                    ctx.lineWidth = 1.1 + sg + sAmp * 1.2;
                    ctx.beginPath();
                    ctx.moveTo(CX, CY);
                    ctx.lineTo(p.sx, p.sy);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        }

        function drawRadialAudioBars(ctx, CX, CY, W, H, amp, sAmp) {
            var totalAmp = Math.max(amp, sAmp);
            if (totalAmp < 0.01) return;

            var SPH = Math.min(W, H) * 0.118;
            var N = 48;
            var barMaxH = SPH * 0.65;
            var isSpk = sAmp > amp;

            for (var i = 0; i < N; i++) {
                var angle = (i / N) * Math.PI * 2;
                var barH = (Math.sin(i * 3.7 + root.animTime * (isSpk ? 8 : 5)) * totalAmp * 1.5 + totalAmp) * barMaxH;
                var x1 = CX + Math.cos(angle) * (SPH + 4);
                var y1 = CY + Math.sin(angle) * (SPH + 4);
                var x2 = CX + Math.cos(angle) * (SPH + 4 + barH);
                var y2 = CY + Math.sin(angle) * (SPH + 4 + barH);
                var col = isSpk
                    ? ("rgba(0,180,255," + (0.5 + sAmp * 0.5) + ")")
                    : ("rgba(0,255,136," + (0.5 + amp * 0.5) + ")");

                ctx.save();
                ctx.strokeStyle = col;
                ctx.lineWidth = 2.2;
                ctx.beginPath();
                ctx.moveTo(x1, y1);
                ctx.lineTo(x2, y2);
                ctx.stroke();
                ctx.restore();
            }
        }

        function drawAmbientStars(ctx, CX, CY, W, H) {
            var maxR = Math.min(W, H) * 0.48;
            for (var i = 0; i < starsData.length; i++) {
                var star = starsData[i];
                var sx = star.x * W;
                var sy = star.y * H;
                var d = Math.hypot(sx - CX, sy - CY);
                if (d >= maxR) continue;

                var falloff = 1.0 - (d / maxR);
                var alpha = (0.10 + star.a * 0.50) * falloff;
                ctx.beginPath();
                ctx.arc(sx, sy, star.r, 0, Math.PI * 2);
                ctx.fillStyle = "rgba(190,215,255," + alpha + ")";
                ctx.fill();
            }
        }

        onPaint: {
            var ctx = getContext("2d");
            ctx.reset();

            var W = width;
            var H = height;
            var CX = W * 0.5;
            var CY = H * 0.5;

            // 100% transparent clear — zero rectangular boxes or opaque backgrounds
            ctx.clearRect(0, 0, W, H);

            if (W <= 0 || H <= 0 || ringsState.length === 0) return;

            var effectiveAmp = root.micAmplitude;
            var effectiveSAmp = root.spkAmp;
            var currentSurge = root.surgeLevel;

            // 1. SOFT AMBIENT ATMOSPHERIC BLOOM (Fades to 0 at circular radius)
            var maxRadius = Math.min(W, H) * 0.48;
            var ag = ctx.createRadialGradient(CX, CY, 30, CX, CY, maxRadius);
            ag.addColorStop(0.0, "rgba(0,100,255," + (0.12 + currentSurge * 0.16 + effectiveAmp * 0.08 + effectiveSAmp * 0.10) + ")");
            ag.addColorStop(0.5, "rgba(0,45,165," + (0.04 + currentSurge * 0.04) + ")");
            ag.addColorStop(1.0, "rgba(0,0,0,0.0)");
            ctx.beginPath();
            ctx.arc(CX, CY, maxRadius, 0, Math.PI * 2);
            ctx.fillStyle = ag;
            ctx.fill();

            // 2. AMBIENT RADIAL STARS (Soft falloff toward perimeter)
            drawAmbientStars(ctx, CX, CY, W, H);

            // 3. ORBIT GUIDES
            drawOrbits(ctx, CX, CY, W, H);

            // Pre-calculate ring points
            var allPts = [];
            for (var r = 0; r < ringsState.length; r++) {
                allPts.push(getRingPts(ringsState[r], 80, CX, CY, W, H));
            }

            // 4. BACK RINGS HALF (Z > 0: Behind Central Sphere)
            for (var bi = 0; bi < ringsState.length; bi++) {
                drawRingHalf(ctx, ringsState[bi], allPts[bi], true, effectiveSAmp);
            }

            // 5. CENTRAL ENERGY SPHERE
            drawSphere(ctx, CX, CY, W, H, currentSurge, effectiveAmp, effectiveSAmp);

            // 6. FRONT RINGS HALF (Z <= 0: In Front of Central Sphere)
            for (var fi = 0; fi < ringsState.length; fi++) {
                drawRingHalf(ctx, ringsState[fi], allPts[fi], false, effectiveSAmp);
            }

            // 7. RADIAL ENERGY BEAMS
            drawBeams(ctx, CX, CY, W, H, currentSurge, effectiveAmp, effectiveSAmp);

            // 8. RING NODES
            for (var ni = 0; ni < ringsState.length; ni++) {
                drawRingNodes(ctx, ringsState[ni], currentSurge, effectiveSAmp);
            }

            // 9. RADIAL AUDIO BARS AROUND SPHERE
            drawRadialAudioBars(ctx, CX, CY, W, H, effectiveAmp, effectiveSAmp);

            // 10. FRACTAL LIGHTNING BOLTS
            for (var lIdx = boltsList.length - 1; lIdx >= 0; lIdx--) {
                var b = boltsList[lIdx];
                b.life -= b.d;
                if (b.life <= 0) {
                    boltsList.splice(lIdx, 1);
                    continue;
                }
                ctx.save();
                ctx.globalAlpha = b.life * 0.88;
                ctx.strokeStyle = "rgba(200,245,255,0.92)";
                ctx.lineWidth = 0.75 + currentSurge * 0.40 + effectiveSAmp * 0.50;
                ctx.beginPath();
                ctx.moveTo(b.x1, b.y1);
                drawFractalBolt(ctx, b.x1, b.y1, b.x2, b.y2, 38 + Math.random() * 18, 4);
                ctx.stroke();
                ctx.restore();
            }

            // 11. GRAVITY PARTICLES
            for (var pIdx = particlesList.length - 1; pIdx >= 0; pIdx--) {
                var p = particlesList[pIdx];
                p.x += p.vx;
                p.y += p.vy;
                p.vy += 0.022; // gravity
                p.life -= p.d;
                if (p.life <= 0) {
                    particlesList.splice(pIdx, 1);
                    continue;
                }
                ctx.save();
                ctx.globalAlpha = p.life;
                ctx.fillStyle = "rgba(150,215,255," + p.life + ")";
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.sz * p.life, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            }
        }
    }

    // Master Presentation Animation Driver (60 FPS vsync)
    Timer {
        id: masterRenderTimer
        interval: 16
        running: root.visible && !root.isSleep
        repeat: true
        onTriggered: {
            root.animTime += 0.016;
            root.breatheTime += 0.011;
            root.surgeLevel = Math.max(0.0, root.surgeLevel - 0.016);

            // Automatic 3D rotation
            if (root.autoSpin && !root.isDragging) {
                root.rotY += 0.0045;
            }

            // Inertial damping on mouse release
            if (!root.isDragging) {
                root.velX *= 0.91;
                root.velY *= 0.91;
                if (!root.autoSpin) {
                    root.rotX += root.velX;
                    root.rotY += root.velY;
                }
            }
            root.rotX = Math.max(-1.45, Math.min(1.45, root.rotX));

            root.ot1 += 0.004;
            root.ot2 += 0.0028;

            // Advance rings
            for (var i = 0; i < coreCanvas.ringsState.length; i++) {
                coreCanvas.ringsState[i].ph += coreCanvas.ringsState[i].spd;
            }

            // Simulated vocal harmonics when speaking
            if (root.isSpeaking) {
                root.spkPhase += 0.18;
                root.spkAmp = (
                    Math.abs(Math.sin(root.spkPhase * 1.3)) * 0.40 +
                    Math.abs(Math.sin(root.spkPhase * 2.7)) * 0.30 +
                    Math.abs(Math.sin(root.spkPhase * 0.8)) * 0.30
                ) * 0.85;

                root.spkBolts--;
                if (root.spkBolts <= 0 && coreCanvas.ringsState.length > 0) {
                    root.spkBolts = 18 + Math.floor(Math.random() * 22);
                    var randR1 = coreCanvas.ringsState[Math.floor(Math.random() * coreCanvas.ringsState.length)];
                    var randR2 = coreCanvas.ringsState[Math.floor(Math.random() * coreCanvas.ringsState.length)];
                    var pt1 = coreCanvas.getRingPt(randR1, 0, width * 0.5, height * 0.5, width, height);
                    var pt2 = coreCanvas.getRingPt(randR2, Math.PI, width * 0.5, height * 0.5, width, height);
                    coreCanvas.spawnBolt(pt1, pt2);
                }
            } else {
                root.spkAmp = Math.max(0.0, root.spkAmp - 0.04);
            }

            // Microphone amplitude tracking from host audio level
            root.micAmplitude = Math.max(0.0, Math.min(1.0, root.audioLevel));

            // Random particles from active nodes
            if (coreCanvas.ringsState.length > 0 && Math.random() < (0.15 + root.micAmplitude * 1.5 + root.surgeLevel * 0.5 + root.spkAmp * 1.2)) {
                var randomRing = coreCanvas.ringsState[Math.floor(Math.random() * coreCanvas.ringsState.length)];
                var nodeAngle = coreCanvas.nodeAngles[Math.floor(Math.random() * coreCanvas.nodeAngles.length)];
                var pt = coreCanvas.getRingPt(randomRing, nodeAngle, width * 0.5, height * 0.5, width, height);
                coreCanvas.spawnParticle(pt.sx, pt.sy, root.micAmplitude * 2.5 + root.surgeLevel * 2.0 + root.spkAmp * 2.0);
            }

            coreCanvas.requestPaint();
        }
    }

    // ========================================================================
    // MOUSE & TOUCH 3D ROTATION INTERACTION
    // ========================================================================
    MouseArea {
        id: coreDragArea
        anchors.fill: parent
        z: 5
        acceptedButtons: Qt.LeftButton
        hoverEnabled: true

        onPressed: function(mouse) {
            root.isDragging = true;
            root.autoSpin = false;
            root.prevMouseX = mouse.x;
            root.prevMouseY = mouse.y;
            root.velX = 0;
            root.velY = 0;
        }

        onPositionChanged: function(mouse) {
            if (!root.isDragging) return;
            var dx = mouse.x - root.prevMouseX;
            var dy = mouse.y - root.prevMouseY;
            root.velX = dy * 0.005;
            root.velY = dx * 0.005;
            root.rotX += root.velX;
            root.rotY += root.velY;
            root.prevMouseX = mouse.x;
            root.prevMouseY = mouse.y;
        }

        onReleased: {
            root.isDragging = false;
            autoSpinRestoreTimer.restart();
        }

        onDoubleClicked: root.triggerSurge()
    }
}
