// ============================================================================
// E.V. INTELLIGENCE CORE — GPT ASTRA ARCHITECTURE
// Faithfully recreates the visual design from OpenAI GPT Astra:
// - Grand-design 2-arm logarithmic spiral
// - Heterogeneous star hierarchy:
//     * Hero Stars with 4-point optical diffraction cross glints
//     * Medium bright stellar bodies
//     * Fine volumetric stardust cloud
// - Soft translucent nebular nucleus with sparkling star cluster
// - 70/30 cool white/ice-blue to warm golden peach/amber palette
// - Near face-on ~75° default perspective with full 3D Steadicam orbit
// ============================================================================

// ----------------------------------------------------------------------------
// CONFIGURATION
// ----------------------------------------------------------------------------
const CONFIG = {
    heroStarCount: 190,
    mediumStarCount: 3200,
    dustCount: 42000,
    nucleusCount: 1100,
    bgStarCount: 1500,
    galaxyRadius: 9.8,
    coreRadius: 1.30,
    twist: 5.2,
    armSpread: 0.62,
    vertSpread: 0.42,
    rotationSpeed: 0.016,
    // Perfectly framed ~75° perspective matching OpenAI Astra
    camBaseX: 0.0,
    camBaseY: 17.5,
    camBaseZ: 4.8
};

// ----------------------------------------------------------------------------
// STATES & TONAL HARMONY
// ----------------------------------------------------------------------------
const STATES = {
    IDLE:      { energy: 1.0,  speedMul: 1.0,  tint: 0xffffff, shift: new THREE.Color(0x002244) },
    LISTENING: { energy: 1.45, speedMul: 1.4,  tint: 0xa5e8ff, shift: new THREE.Color(0x004466) },
    THINKING:  { energy: 1.85, speedMul: 2.2,  tint: 0x70d4ff, shift: new THREE.Color(0x005588) },
    PLANNING:  { energy: 1.25, speedMul: 1.2,  tint: 0xbfe8ff, shift: new THREE.Color(0x003366) },
    APPROVAL:  { energy: 1.15, speedMul: 0.6,  tint: 0xffcc66, shift: new THREE.Color(0x443300) },
    EXECUTING: { energy: 2.1,  speedMul: 2.8,  tint: 0xffffff, shift: new THREE.Color(0x0033aa) },
    VERIFYING: { energy: 1.55, speedMul: 1.8,  tint: 0x6ee7b7, shift: new THREE.Color(0x006644) },
    SPEAKING:  { energy: 1.75, speedMul: 1.6,  tint: 0xffffff, shift: new THREE.Color(0x004488) },
    SUCCESS:   { energy: 2.2,  speedMul: 1.2,  tint: 0x86efac, shift: new THREE.Color(0x008855) },
    FAILED:    { energy: 0.85, speedMul: 0.5,  tint: 0xfca5a5, shift: new THREE.Color(0x551100) },
    SLEEP:     { energy: 0.26, speedMul: 0.08, tint: 0x64748b, shift: new THREE.Color(0x000511) }
};

let currentState = 'IDLE';
let currentEnergy = STATES.IDLE.energy;
let targetEnergy = STATES.IDLE.energy;
let currentSpeedMul = STATES.IDLE.speedMul;
let targetSpeedMul = STATES.IDLE.speedMul;
let currentColorShift = new THREE.Color().copy(STATES.IDLE.shift);
let targetColorShift = new THREE.Color().copy(STATES.IDLE.shift);

// ----------------------------------------------------------------------------
// SCENE, CAMERA, RENDERER
// ----------------------------------------------------------------------------
const container = document.getElementById('canvas-container') || document.body;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x020408);

const camera = new THREE.PerspectiveCamera(
    46, window.innerWidth / window.innerHeight, 0.1, 200
);
camera.position.set(CONFIG.camBaseX, CONFIG.camBaseY, CONFIG.camBaseZ);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x020408, 1);
container.appendChild(renderer.domElement);

const galaxyGroup = new THREE.Group();
scene.add(galaxyGroup);

// ----------------------------------------------------------------------------
// PROCEDURAL TEXTURES (Hero Glint + Soft Dot + Nebular Glow)
// ----------------------------------------------------------------------------
// 1. Hero Star Texture: Brilliant core + soft halo + 4-point diffraction cross spikes
function makeHeroStarTexture() {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const c = size / 2;

    // Soft outer glow
    const g = ctx.createRadialGradient(c, c, 0, c, c, size / 2);
    g.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)');
    g.addColorStop(0.12, 'rgba(230, 245, 255, 0.85)');
    g.addColorStop(0.35, 'rgba(140, 210, 255, 0.35)');
    g.addColorStop(0.70, 'rgba(20, 80, 180, 0.08)');
    g.addColorStop(1.0, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);

    // 4-point diffraction cross spikes
    ctx.save();
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.95)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(6, c); ctx.lineTo(size - 6, c);
    ctx.moveTo(c, 6); ctx.lineTo(c, size - 6);
    ctx.stroke();

    // Subtle wider flare base
    ctx.strokeStyle = 'rgba(200, 235, 255, 0.45)';
    ctx.lineWidth = 2.8;
    ctx.beginPath();
    ctx.moveTo(24, c); ctx.lineTo(size - 24, c);
    ctx.moveTo(c, 24); ctx.lineTo(c, size - 24);
    ctx.stroke();
    ctx.restore();

    // Hot incandescent pinpoint core
    const coreG = ctx.createRadialGradient(c, c, 0, c, c, 8);
    coreG.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)');
    coreG.addColorStop(0.6, 'rgba(255, 255, 255, 0.9)');
    coreG.addColorStop(1.0, 'rgba(255, 255, 255, 0)');
    ctx.fillStyle = coreG;
    ctx.beginPath();
    ctx.arc(c, c, 8, 0, Math.PI * 2);
    ctx.fill();

    return new THREE.CanvasTexture(canvas);
}
const heroStarTex = makeHeroStarTexture();

// 2. Medium & Stardust Texture: Soft Gaussian Dot
function makeDotTexture() {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const c = size / 2;

    const g = ctx.createRadialGradient(c, c, 0, c, c, size / 2);
    g.addColorStop(0.0, 'rgba(255, 255, 255, 1.0)');
    g.addColorStop(0.25, 'rgba(255, 255, 255, 0.9)');
    g.addColorStop(0.65, 'rgba(220, 242, 255, 0.3)');
    g.addColorStop(1.0, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}
const dotTex = makeDotTexture();

// 3. Central Nebular Core Texture: Soft Translucent Milky Cloud
function makeNebulaGlowTexture() {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const c = size / 2;

    const g = ctx.createRadialGradient(c, c, 0, c, c, size / 2);
    g.addColorStop(0.0, 'rgba(255, 255, 255, 0.85)');
    g.addColorStop(0.15, 'rgba(235, 245, 255, 0.60)');
    g.addColorStop(0.35, 'rgba(160, 215, 255, 0.22)');
    g.addColorStop(0.65, 'rgba(40, 110, 200, 0.05)');
    g.addColorStop(1.0, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}
const nebulaGlowTex = makeNebulaGlowTexture();

// ----------------------------------------------------------------------------
// ASTRA COLOR PALETTE (70% Cool White/Ice Blue, 30% Warm Golden Peach/Amber)
// ----------------------------------------------------------------------------
const astraCoolColors = [
    new THREE.Color(0xffffff), // Pure white
    new THREE.Color(0xeef7ff), // Diamond white
    new THREE.Color(0xd0e8ff), // Soft ice blue
    new THREE.Color(0x9fc8f5), // Platinum blue
    new THREE.Color(0x70abed), // Electric blue
];
const astraWarmColors = [
    new THREE.Color(0xf6ad55), // Warm peach gold
    new THREE.Color(0xed8936), // Amber copper
    new THREE.Color(0xdd6b20), // Deep warm amber
    new THREE.Color(0xfbd38d), // Pale golden champagne
];

function pickAstraColor(isHero) {
    if (isHero) {
        return Math.random() < 0.75 
            ? astraCoolColors[Math.floor(Math.random() * 3)] 
            : astraWarmColors[Math.floor(Math.random() * 2)];
    }
    return Math.random() < 0.70 
        ? astraCoolColors[Math.floor(Math.random() * astraCoolColors.length)]
        : astraWarmColors[Math.floor(Math.random() * astraWarmColors.length)];
}

// ----------------------------------------------------------------------------
// GLSL SHADER (Differential Keplerian Flow + ACES Filmic Tone Mapping)
// ----------------------------------------------------------------------------
const particleVertexShader = `
    attribute float size;
    attribute vec3 customColor;
    attribute float radius;
    attribute float initialAngle;
    attribute float randomSeed;
    attribute float layerType; // 0: Nucleus, 1: Hero, 2: Medium, 3: Dust, 4: Background

    varying vec3 vColor;
    varying float vAlpha;

    uniform float time;
    uniform float energy;
    uniform float pulse;
    uniform float speedMul;
    uniform vec3 uMouseWorld;
    uniform float uMouseRadius;
    uniform float uMouseStrength;

    void main() {
        vColor = customColor;

        // Differential Keplerian rotation: inner core circulates faster than outer arms
        float angVel = 0.0;
        if (layerType == 4.0) {
            angVel = 0.005; // background stars barely drift
        } else if (layerType == 0.0) {
            angVel = 0.28;  // core rotates briskly
        } else {
            angVel = 0.24 / sqrt(max(0.7, radius * 0.45));
        }

        float curAngle = initialAngle - angVel * time * (0.85 + energy * 0.3) * speedMul;

        // Radial breathing ripple
        float wave = sin(radius * 1.5 - time * 1.8) * 0.025 * energy;
        float curR = radius * (1.0 + wave);

        vec3 pos;
        if (layerType == 4.0 || layerType == 0.0) {
            float c = cos(curAngle);
            float s = sin(curAngle);
            pos.x = position.x * c - position.z * s;
            pos.z = position.x * s + position.z * c;
            pos.y = position.y;
        } else {
            pos.x = cos(curAngle) * curR + position.x;
            pos.z = sin(curAngle) * curR + position.z;
            pos.y = position.y + sin(curAngle * 2.0 + time * 1.2) * 0.05;
        }

        // Sub-bass respiration pulse
        float rScale = 1.0 + (pulse - 1.0) * (layerType == 0.0 ? 1.15 : 0.6);
        pos *= rScale;

        vec4 worldPos = modelMatrix * vec4(pos, 1.0);

        // Smooth cursor attraction
        vec3 toCursor = uMouseWorld - worldPos.xyz;
        float dist = length(toCursor);
        if (dist < uMouseRadius && uMouseStrength > 0.001) {
            float normDist = dist / uMouseRadius;
            float falloff = (1.0 - normDist) * (1.0 - normDist);
            vec3 pullDir = normalize(toCursor + vec3(0.0001));
            vec3 swirlDir = vec3(-pullDir.z, pullDir.y * 0.25, pullDir.x);
            worldPos.xyz += (pullDir * 0.7 + swirlDir * 0.3) * (falloff * uMouseStrength * 1.1);
        }

        // Individual optical twinkling
        float twinkle = sin(time * 6.0 + randomSeed * 45.0) * 0.15 + 0.85;

        vec4 mvPosition = viewMatrix * worldPos;

        // Size with perspective attenuation
        float scaleMul = (layerType == 1.0) ? 3.4 : ((layerType == 2.0) ? 1.35 : 0.85);
        gl_PointSize = size * scaleMul * (28.0 / -mvPosition.z) * twinkle * (1.0 + energy * 0.2);
        gl_PointSize = clamp(gl_PointSize, 1.0, 72.0);

        gl_Position = projectionMatrix * mvPosition;

        if (layerType == 1.0) vAlpha = 0.98;
        else if (layerType == 0.0) vAlpha = 0.92;
        else if (layerType == 2.0) vAlpha = 0.88;
        else if (layerType == 3.0) vAlpha = 0.75;
        else vAlpha = 0.40;
    }
`;

const particleFragmentShader = `
    varying vec3 vColor;
    varying float vAlpha;

    uniform vec3 colorShift;
    uniform float energy;
    uniform sampler2D uTexture;

    // ACES Filmic Tone Mapping Curve
    vec3 ACESFilm(vec3 x) {
        float a = 2.51;
        float b = 0.03;
        float c = 2.43;
        float d = 0.59;
        float e = 0.14;
        return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
    }

    void main() {
        vec4 texColor = texture2D(uTexture, gl_PointCoord);
        if (texColor.a < 0.02) discard;

        vec3 baseCol = vColor + colorShift * energy * 0.65;
        vec3 hdrCol = baseCol * texColor.a * (1.3 + energy * 0.4);

        vec3 toneMapped = ACESFilm(hdrCol);
        gl_FragColor = vec4(toneMapped, vAlpha * texColor.a);
    }
`;

// ----------------------------------------------------------------------------
// MULTI-TIER GEOMETRY GENERATION
// ----------------------------------------------------------------------------
const uniformsTemplate = {
    time: { value: 0.0 },
    energy: { value: currentEnergy },
    pulse: { value: 1.0 },
    speedMul: { value: currentSpeedMul },
    colorShift: { value: currentColorShift },
    uMouseWorld: { value: new THREE.Vector3(999, 999, 999) },
    uMouseRadius: { value: 4.2 },
    uMouseStrength: { value: 0.0 }
};

// Material 1: Hero Stars (Uses 4-point cross diffraction texture)
const heroMaterial = new THREE.ShaderMaterial({
    uniforms: Object.assign({}, uniformsTemplate, { uTexture: { value: heroStarTex } }),
    vertexShader: particleVertexShader,
    fragmentShader: particleFragmentShader,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true
});

// Material 2: Standard Stars (Medium stars, dust motes, core cluster, background)
const standardMaterial = new THREE.ShaderMaterial({
    uniforms: Object.assign({}, uniformsTemplate, { uTexture: { value: dotTex } }),
    vertexShader: particleVertexShader,
    fragmentShader: particleFragmentShader,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true
});

let combinedGeometry = null;
let heroPoints = null;
let standardPoints = null;

function buildAstraGalaxy() {
    // ------------------------------------------------------------------------
    // 1. HERO STARS (160 prominent glinting jewels along the arm spines)
    // ------------------------------------------------------------------------
    const heroPos = new Float32Array(CONFIG.heroStarCount * 3);
    const heroCol = new Float32Array(CONFIG.heroStarCount * 3);
    const heroSizes = new Float32Array(CONFIG.heroStarCount);
    const heroRadii = new Float32Array(CONFIG.heroStarCount);
    const heroAngles = new Float32Array(CONFIG.heroStarCount);
    const heroSeeds = new Float32Array(CONFIG.heroStarCount);
    const heroLayers = new Float32Array(CONFIG.heroStarCount);

    // Logarithmic spiral parameters: r(theta) = r_min * exp(k * theta)
    const rMin = CONFIG.coreRadius * 0.70;
    const rMax = CONFIG.galaxyRadius;
    const maxAngle = 3.05 * Math.PI; // ~1.52 full turns
    const kGrowth = Math.log(rMax / rMin) / maxAngle;
    const astraGlobalOffset = 1.40; // Aligns arm orientation perfectly with Astra reference

    for (let i = 0; i < CONFIG.heroStarCount; i++) {
        const arm = i % 2;
        const s = 0.04 + ((i / CONFIG.heroStarCount) * 0.93) + (Math.random() - 0.5) * 0.02;
        const thetaArm = s * maxAngle;
        const radius = rMin * Math.exp(kGrowth * thetaArm);

        let angle = astraGlobalOffset + arm * Math.PI - thetaArm;

        // Occasional spur branch (15% chance)
        if (s > 0.3 && s < 0.7 && Math.random() < 0.15) {
            angle += (arm === 0 ? 0.35 : -0.35);
        }

        // Tight spine scatter (Hero stars stay near the spine)
        const jitter = (Math.random() - 0.5) * CONFIG.armSpread * 0.35;
        const jitterY = (Math.random() - 0.5) * CONFIG.vertSpread * 0.25;

        heroPos[i * 3 + 0] = jitter;
        heroPos[i * 3 + 1] = jitterY;
        heroPos[i * 3 + 2] = jitter;

        const c = pickAstraColor(true);
        heroCol[i * 3 + 0] = c.r;
        heroCol[i * 3 + 1] = c.g;
        heroCol[i * 3 + 2] = c.b;

        heroSizes[i] = 2.4 + Math.random() * 2.2;
        heroRadii[i] = radius;
        heroAngles[i] = angle;
        heroSeeds[i] = Math.random();
        heroLayers[i] = 1.0; // Hero
    }

    const heroGeo = new THREE.BufferGeometry();
    heroGeo.setAttribute('position', new THREE.BufferAttribute(heroPos, 3));
    heroGeo.setAttribute('customColor', new THREE.BufferAttribute(heroCol, 3));
    heroGeo.setAttribute('size', new THREE.BufferAttribute(heroSizes, 1));
    heroGeo.setAttribute('radius', new THREE.BufferAttribute(heroRadii, 1));
    heroGeo.setAttribute('initialAngle', new THREE.BufferAttribute(heroAngles, 1));
    heroGeo.setAttribute('randomSeed', new THREE.BufferAttribute(heroSeeds, 1));
    heroGeo.setAttribute('layerType', new THREE.BufferAttribute(heroLayers, 1));

    heroPoints = new THREE.Points(heroGeo, heroMaterial);
    galaxyGroup.add(heroPoints);

    // ------------------------------------------------------------------------
    // 2. STANDARD PARTICLES (Medium stars + Stardust + Nucleus + Background)
    // ------------------------------------------------------------------------
    const stdTotal = CONFIG.mediumStarCount + CONFIG.dustCount + 
                     CONFIG.nucleusCount + CONFIG.bgStarCount;

    const stdPos = new Float32Array(stdTotal * 3);
    const stdCol = new Float32Array(stdTotal * 3);
    const stdSizes = new Float32Array(stdTotal);
    const stdRadii = new Float32Array(stdTotal);
    const stdAngles = new Float32Array(stdTotal);
    const stdSeeds = new Float32Array(stdTotal);
    const stdLayers = new Float32Array(stdTotal);

    let idx = 0;

    // A. NUCLEUS CLUSTER (950 sparkling pinpoint core stars, slightly barred)
    for (let i = 0; i < CONFIG.nucleusCount; i++) {
        const u = Math.random();
        const r = CONFIG.coreRadius * Math.cbrt(u);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        stdPos[idx * 3 + 0] = r * Math.sin(phi) * Math.cos(theta) * 1.15;
        stdPos[idx * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.50;
        stdPos[idx * 3 + 2] = r * Math.cos(phi) * 0.85;

        const c = Math.random() < 0.85 
            ? new THREE.Color(0xffffff).lerp(new THREE.Color(0xdef2ff), Math.random() * 0.5)
            : astraWarmColors[0];

        stdCol[idx * 3 + 0] = c.r;
        stdCol[idx * 3 + 1] = c.g;
        stdCol[idx * 3 + 2] = c.b;

        stdSizes[idx] = 0.95 + Math.random() * 0.75;
        stdRadii[idx] = r;
        stdAngles[idx] = theta;
        stdSeeds[idx] = Math.random();
        stdLayers[idx] = 0.0; // Nucleus
        idx++;
    }

    // B. MEDIUM BRIGHT STARS (2,600 distinct glowing orbs defining the arms)
    for (let i = 0; i < CONFIG.mediumStarCount; i++) {
        const arm = i % 2;
        const s = Math.pow(Math.random(), 1.22);
        const thetaArm = s * maxAngle;
        let radius = rMin * Math.exp(kGrowth * thetaArm);

        let angle = astraGlobalOffset + arm * Math.PI - thetaArm;

        // Arm spurs (18% probability for natural galactic feathering)
        if (s > 0.25 && s < 0.75 && Math.random() < 0.18) {
            angle += (Math.random() - 0.5) * 0.60;
            radius *= (0.90 + Math.random() * 0.20);
        }

        // Box-Muller normal scatter
        const u1 = Math.max(1e-6, Math.random());
        const u2 = Math.random();
        const rNorm = Math.sqrt(-2.0 * Math.log(u1)) * CONFIG.armSpread * (0.30 + 0.70 * (1.0 - s * 0.25));
        const phi = u2 * Math.PI * 2;

        stdPos[idx * 3 + 0] = rNorm * Math.cos(phi);
        stdPos[idx * 3 + 1] = (Math.random() - 0.5) * CONFIG.vertSpread * (0.35 + 0.65 * (1.0 - s * 0.25));
        stdPos[idx * 3 + 2] = rNorm * Math.sin(phi);

        const c = pickAstraColor(false);
        stdCol[idx * 3 + 0] = c.r;
        stdCol[idx * 3 + 1] = c.g;
        stdCol[idx * 3 + 2] = c.b;

        stdSizes[idx] = 0.95 + Math.random() * 0.85;
        stdRadii[idx] = radius;
        stdAngles[idx] = angle;
        stdSeeds[idx] = Math.random();
        stdLayers[idx] = 2.0; // Medium
        idx++;
    }

    // C. FINE STARDUST (32,000 microscopic volumetric cloud motes)
    for (let i = 0; i < CONFIG.dustCount; i++) {
        const arm = i % 2;
        const s = Math.pow(Math.random(), 1.30);
        const thetaArm = s * maxAngle;
        let radius = rMin * Math.exp(kGrowth * thetaArm);

        let angle = astraGlobalOffset + arm * Math.PI - thetaArm;

        if (s > 0.20 && s < 0.80 && Math.random() < 0.22) {
            angle += (Math.random() - 0.5) * 0.70;
            radius *= (0.88 + Math.random() * 0.24);
        }

        const u1 = Math.max(1e-6, Math.random());
        const u2 = Math.random();
        const rNorm = Math.sqrt(-2.0 * Math.log(u1)) * CONFIG.armSpread * (0.38 + 0.62 * (1.0 - s * 0.22));
        const phi = u2 * Math.PI * 2;

        stdPos[idx * 3 + 0] = rNorm * Math.cos(phi);
        stdPos[idx * 3 + 1] = (Math.random() - 0.5) * CONFIG.vertSpread * (0.30 + 0.70 * (1.0 - s * 0.22));
        stdPos[idx * 3 + 2] = rNorm * Math.sin(phi);

        const c = pickAstraColor(false);
        stdCol[idx * 3 + 0] = c.r;
        stdCol[idx * 3 + 1] = c.g;
        stdCol[idx * 3 + 2] = c.b;

        stdSizes[idx] = 0.42 + Math.random() * 0.42;
        stdRadii[idx] = radius;
        stdAngles[idx] = angle;
        stdSeeds[idx] = Math.random();
        stdLayers[idx] = 3.0; // Dust
        idx++;
    }

    // D. BACKGROUND DEEP COSMIC STARS (1,200 distant twinkling stars)
    for (let i = 0; i < CONFIG.bgStarCount; i++) {
        const r = CONFIG.galaxyRadius * (0.6 + Math.random() * 1.1);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        stdPos[idx * 3 + 0] = r * Math.sin(phi) * Math.cos(theta);
        stdPos[idx * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.4;
        stdPos[idx * 3 + 2] = r * Math.cos(phi);

        const c = Math.random() < 0.8 ? astraCoolColors[2] : astraWarmColors[1];
        stdCol[idx * 3 + 0] = c.r;
        stdCol[idx * 3 + 1] = c.g;
        stdCol[idx * 3 + 2] = c.b;

        stdSizes[idx] = 0.35 + Math.random() * 0.45;
        stdRadii[idx] = r;
        stdAngles[idx] = theta;
        stdSeeds[idx] = Math.random();
        stdLayers[idx] = 4.0; // Background
        idx++;
    }

    const stdGeo = new THREE.BufferGeometry();
    stdGeo.setAttribute('position', new THREE.BufferAttribute(stdPos, 3));
    stdGeo.setAttribute('customColor', new THREE.BufferAttribute(stdCol, 3));
    stdGeo.setAttribute('size', new THREE.BufferAttribute(stdSizes, 1));
    stdGeo.setAttribute('radius', new THREE.BufferAttribute(stdRadii, 1));
    stdGeo.setAttribute('initialAngle', new THREE.BufferAttribute(stdAngles, 1));
    stdGeo.setAttribute('randomSeed', new THREE.BufferAttribute(stdSeeds, 1));
    stdGeo.setAttribute('layerType', new THREE.BufferAttribute(stdLayers, 1));

    standardPoints = new THREE.Points(stdGeo, standardMaterial);
    galaxyGroup.add(standardPoints);

    combinedGeometry = stdGeo;
}

buildAstraGalaxy();

// ----------------------------------------------------------------------------
// TRANSLUCENT NEBULAR CORE GLOW (Soft Optical Atmosphere, No Hard Borders)
// ----------------------------------------------------------------------------
const nebulaMat = new THREE.SpriteMaterial({
    map: nebulaGlowTex,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
    opacity: 0.55
});
const nebulaCore = new THREE.Sprite(nebulaMat);
nebulaCore.scale.set(4.8, 4.8, 1);
galaxyGroup.add(nebulaCore);

// Faint hot inner core spark
const innerGlowMat = new THREE.SpriteMaterial({
    map: nebulaGlowTex,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false,
    opacity: 0.75
});
const innerGlow = new THREE.Sprite(innerGlowMat);
innerGlow.scale.set(2.0, 2.0, 1);
galaxyGroup.add(innerGlow);

// Soft environmental point light
const coreLight = new THREE.PointLight(0xd8f2ff, 1.8, 16);
galaxyGroup.add(coreLight);

// ----------------------------------------------------------------------------
// STEADICAM CAMERA PHYSICS & INTERACTION
// ----------------------------------------------------------------------------
let mouseX = 0, mouseY = 0;
let isDragging = false;
let prevPointerX = 0, prevPointerY = 0;

let orbitRadius = Math.hypot(CONFIG.camBaseX, CONFIG.camBaseY, CONFIG.camBaseZ);
let orbitPhi = Math.acos(CONFIG.camBaseY / orbitRadius);
let orbitTheta = Math.atan2(CONFIG.camBaseX, CONFIG.camBaseZ);

let targetOrbitTheta = orbitTheta;
let targetOrbitPhi = orbitPhi;
let targetOrbitRadius = orbitRadius;

window.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
    mouseY = (e.clientY / window.innerHeight - 0.5) * 2;

    const vector = new THREE.Vector3(mouseX, -mouseY, 0.5);
    vector.unproject(camera);
    const dir = vector.sub(camera.position).normalize();
    const distance = -camera.position.z / dir.z;
    const worldPos = camera.position.clone().add(dir.multiplyScalar(distance));

    heroMaterial.uniforms.uMouseWorld.value.copy(worldPos);
    heroMaterial.uniforms.uMouseStrength.value = 1.0;
    standardMaterial.uniforms.uMouseWorld.value.copy(worldPos);
    standardMaterial.uniforms.uMouseStrength.value = 1.0;
});

window.addEventListener('mouseleave', () => {
    heroMaterial.uniforms.uMouseStrength.value = 0.0;
    standardMaterial.uniforms.uMouseStrength.value = 0.0;
});

container.addEventListener('pointerdown', (e) => {
    if (e.target.closest('#mic-panel') || e.target.closest('#debug-overlay')) return;
    isDragging = true;
    prevPointerX = e.clientX;
    prevPointerY = e.clientY;
    try { container.setPointerCapture(e.pointerId); } catch (_) {}
});

container.addEventListener('pointermove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - prevPointerX;
    const dy = e.clientY - prevPointerY;
    prevPointerX = e.clientX;
    prevPointerY = e.clientY;

    targetOrbitTheta -= dx * 0.005;
    targetOrbitPhi = Math.max(0.12, Math.min(Math.PI - 0.12, targetOrbitPhi - dy * 0.005));
});

function endDrag(e) {
    if (isDragging) {
        isDragging = false;
        try { container.releasePointerCapture(e.pointerId); } catch (_) {}
    }
}
container.addEventListener('pointerup', endDrag);
container.addEventListener('pointercancel', endDrag);

container.addEventListener('wheel', (e) => {
    e.preventDefault();
    targetOrbitRadius = Math.max(6.0, Math.min(28.0, targetOrbitRadius + Math.sign(e.deltaY) * 1.4));
}, { passive: false });

container.addEventListener('dblclick', () => {
    targetOrbitRadius = Math.hypot(CONFIG.camBaseX, CONFIG.camBaseY, CONFIG.camBaseZ);
    targetOrbitPhi = Math.acos(CONFIG.camBaseY / targetOrbitRadius);
    targetOrbitTheta = Math.atan2(CONFIG.camBaseX, CONFIG.camBaseZ);
});

// ----------------------------------------------------------------------------
// STATE MANAGEMENT & HUD
// ----------------------------------------------------------------------------
function updateHUD(name) {
    const label = document.getElementById('current-state-label') || document.getElementById('stateLabel');
    if (label) label.textContent = `STATE: ${name}`;
}

const keyMap = {
    '1':'IDLE', '2':'LISTENING', '3':'THINKING', '4':'PLANNING', '5':'APPROVAL',
    '6':'EXECUTING', '7':'VERIFYING', '8':'SPEAKING', '9':'SUCCESS', '0':'FAILED',
    's':'SLEEP', 'S':'SLEEP'
};

window.addEventListener('keydown', (e) => {
    const s = keyMap[e.key];
    if (s) EVCore.setState({ state: s });
});

const EVCore = {
    setState: function(config) {
        let name = 'IDLE';
        if (typeof config === 'string') {
            name = config;
        } else if (config && config.state) {
            name = typeof config.state === 'string' ? config.state : (config.state.name || 'IDLE');
        }
        name = name.toUpperCase();
        if (STATES[name]) {
            currentState = name;
            targetEnergy = STATES[name].energy;
            targetSpeedMul = STATES[name].speedMul;
            targetColorShift.copy(STATES[name].shift);
            nebulaCore.material.color.set(STATES[name].tint);
            coreLight.color.set(STATES[name].tint);
            updateHUD(name);
        }
    }
};

// ----------------------------------------------------------------------------
// MICROPHONE INFRASTRUCTURE (Web Audio API)
// ----------------------------------------------------------------------------
let audioContext = null;
let analyser = null;
let audioDataArray = null;
let micStream = null;
let isMicActive = false;
let currentMicLevel = 0.0;
let targetMicLevel = 0.0;

const micToggleBtn = document.getElementById('mic-toggle-btn');
const micBtnLabel = document.getElementById('mic-btn-label');
const micVuBar = document.getElementById('mic-vu-bar');
const micStatusNote = document.getElementById('mic-status-note');

function showMicStatus(text, statusClass) {
    if (!micStatusNote) return;
    micStatusNote.innerText = text;
    micStatusNote.className = 'mic-note ' + (statusClass || '');
}

async function initMicrophone() {
    if (isMicActive) {
        disableMicrophone();
        return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showMicStatus("Microphone API not supported in this browser", "denied");
        return;
    }
    try {
        micStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        audioContext = new AudioContextClass();
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }
        const source = audioContext.createMediaStreamSource(micStream);
        analyser = audioContext.createAnalyser();
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.75;
        source.connect(analyser);
        audioDataArray = new Uint8Array(analyser.frequencyBinCount);
        isMicActive = true;
        if (micToggleBtn) micToggleBtn.classList.add('active');
        if (micBtnLabel) micBtnLabel.innerText = "MIC ACTIVE";
        showMicStatus("Live microphone input active", "active");
    } catch (err) {
        isMicActive = false;
        if (micToggleBtn) micToggleBtn.classList.add('denied');
        showMicStatus("Mic access denied — voice reactivity disabled", "denied");
    }
}

function disableMicrophone() {
    if (micStream) {
        micStream.getTracks().forEach(t => t.stop());
        micStream = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
        audioContext = null;
    }
    isMicActive = false;
    analyser = null;
    targetMicLevel = 0.0;
    currentMicLevel = 0.0;
    if (micToggleBtn) {
        micToggleBtn.classList.remove('active');
        micToggleBtn.classList.remove('denied');
    }
    if (micBtnLabel) micBtnLabel.innerText = "ENABLE MIC";
    if (micVuBar) micVuBar.style.width = '0%';
    showMicStatus("Voice reactivity: Standby", "");
}

if (micToggleBtn) {
    micToggleBtn.addEventListener('click', () => {
        if (!isMicActive) initMicrophone();
        else disableMicrophone();
    });
}

function updateMicrophone() {
    if (!isMicActive || !analyser || !audioDataArray) {
        targetMicLevel = 0.0;
    } else {
        analyser.getByteFrequencyData(audioDataArray);
        let sum = 0;
        const count = audioDataArray.length;
        for (let i = 0; i < count; i++) {
            sum += audioDataArray[i];
        }
        const avg = sum / count;
        targetMicLevel = Math.min(1.0, (avg / 128.0) * 1.5);
    }
    currentMicLevel += (targetMicLevel - currentMicLevel) * 0.2;
    if (micVuBar) {
        micVuBar.style.width = `${Math.round(currentMicLevel * 100)}%`;
    }
}

// ----------------------------------------------------------------------------
// RESIZE
// ----------------------------------------------------------------------------
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// ----------------------------------------------------------------------------
// ANIMATION LOOP — Astra Cosmic Motion & Fluid Respiration
// ----------------------------------------------------------------------------
const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);
    const dt = clock.getDelta();
    const t = clock.getElapsedTime();

    updateMicrophone();

    // Smooth state interpolation
    currentEnergy += (targetEnergy - currentEnergy) * 0.08;
    currentSpeedMul += (targetSpeedMul - currentSpeedMul) * 0.08;
    currentColorShift.lerp(targetColorShift, 0.08);

    // Subtle poly-rhythmic breathing
    const subBass = 1.0 + Math.sin(t * 1.5) * 0.04 * currentEnergy;
    const micPulse = 1.0 + currentMicLevel * 0.75;
    const totalPulse = subBass * micPulse;

    // Pass uniforms to both shaders
    const effectiveSpeed = currentSpeedMul * (1.0 + currentMicLevel * 1.4);
    
    [heroMaterial, standardMaterial].forEach(mat => {
        mat.uniforms.time.value = t;
        mat.uniforms.energy.value = currentEnergy;
        mat.uniforms.pulse.value = totalPulse;
        mat.uniforms.speedMul.value = effectiveSpeed;
        mat.uniforms.colorShift.value.copy(currentColorShift);
    });

    // Nucleus optical breathing
    nebulaCore.scale.set(3.8 * totalPulse * currentEnergy, 3.8 * totalPulse * currentEnergy, 1);
    innerGlow.scale.set(1.4 * totalPulse, 1.4 * totalPulse, 1);
    coreLight.intensity = (2.2 + currentEnergy * 0.8) * micPulse;

    // Steadicam camera physics & subtle autonomous zero-g micro-drift
    orbitTheta += (targetOrbitTheta - orbitTheta) * 0.05;
    orbitPhi += (targetOrbitPhi - orbitPhi) * 0.05;
    orbitRadius += (targetOrbitRadius - orbitRadius) * 0.05;

    const driftX = Math.sin(t * 0.35) * 0.18;
    const driftY = Math.cos(t * 0.28) * 0.10;

    const orbitX = orbitRadius * Math.sin(orbitPhi) * Math.sin(orbitTheta);
    const orbitY = orbitRadius * Math.cos(orbitPhi);
    const orbitZ = orbitRadius * Math.sin(orbitPhi) * Math.cos(orbitTheta);

    const targetCamX = orbitX + mouseX * 2.0 + driftX;
    const targetCamY = orbitY - mouseY * 1.2 + driftY;

    camera.position.x += (targetCamX - camera.position.x) * 0.04;
    camera.position.y += (targetCamY - camera.position.y) * 0.04;
    camera.position.z += (orbitZ - camera.position.z) * 0.04;
    camera.lookAt(0, 0, 0);

    renderer.render(scene, camera);
}
animate();

// ----------------------------------------------------------------------------
// RUNTIME EXPORTS
// ----------------------------------------------------------------------------
window.EVCore = EVCore;
window.STATES = STATES;
Object.defineProperty(window, 'currentState', { get: () => currentState });
window.renderer = renderer;
window.camera = camera;
window.fieldGeometry = combinedGeometry;
window.galaxyGeometry = combinedGeometry;
window.initMicrophone = initMicrophone;
window.disableMicrophone = disableMicrophone;
