// ============================================================================
// E.V. CINEMATIC INTELLIGENCE CORE — WebGL Visual Engine
// Combines Claude's proven aesthetic baseline (soft glowing nucleus,
// elegant 2-arm spiral, 3/4 elevated perspective, scattered stardust)
// with cinematic physics: differential Keplerian rotation, outward
// energy wave ripples, ACES filmic tone mapping, and Steadicam physics.
// ============================================================================

const CONFIG = {
    armCount: 2,
    armParticles: 36000,
    coreParticles: 5000,
    haloParticles: 9000,
    galaxyRadius: 9.5,
    coreRadius: 1.4,
    spin: 3.2,
    armSpread: 0.55,
    vertSpread: 0.35,
    rotationSpeed: 0.02,
    camBaseX: 0.0,
    camBaseY: 9.5,
    camBaseZ: 8.5
};

const STATES = {
    IDLE:      { energy: 1.0,  speedMul: 1.0,  tint: 0xffffff, shift: new THREE.Color(0x002244) },
    LISTENING: { energy: 1.4,  speedMul: 1.5,  tint: 0x9fe8ff, shift: new THREE.Color(0x004466) },
    THINKING:  { energy: 1.8,  speedMul: 2.3,  tint: 0x6fd0ff, shift: new THREE.Color(0x005588) },
    PLANNING:  { energy: 1.2,  speedMul: 1.2,  tint: 0xbfe8ff, shift: new THREE.Color(0x003366) },
    APPROVAL:  { energy: 1.1,  speedMul: 0.6,  tint: 0xffcc66, shift: new THREE.Color(0x443300) },
    EXECUTING: { energy: 2.0,  speedMul: 2.8,  tint: 0xffffff, shift: new THREE.Color(0x0033aa) },
    VERIFYING: { energy: 1.5,  speedMul: 1.8,  tint: 0x7fffd4, shift: new THREE.Color(0x006644) },
    SPEAKING:  { energy: 1.7,  speedMul: 1.6,  tint: 0xffffff, shift: new THREE.Color(0x004488) },
    SUCCESS:   { energy: 2.2,  speedMul: 1.2,  tint: 0x9fffb0, shift: new THREE.Color(0x008855) },
    FAILED:    { energy: 0.85, speedMul: 0.5,  tint: 0xff6666, shift: new THREE.Color(0x551100) },
    SLEEP:     { energy: 0.28, speedMul: 0.08, tint: 0x556677, shift: new THREE.Color(0x000511) }
};

let currentState = 'IDLE';
let currentEnergy = STATES.IDLE.energy;
let targetEnergy = STATES.IDLE.energy;
let currentSpeedMul = STATES.IDLE.speedMul;
let targetSpeedMul = STATES.IDLE.speedMul;
let currentColorShift = new THREE.Color().copy(STATES.IDLE.shift);
let targetColorShift = new THREE.Color().copy(STATES.IDLE.shift);

const container = document.getElementById('canvas-container') || document.body;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x010204);

const camera = new THREE.PerspectiveCamera(
    48, window.innerWidth / window.innerHeight, 0.1, 200
);
camera.position.set(CONFIG.camBaseX, CONFIG.camBaseY, CONFIG.camBaseZ);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x010204, 1);
container.appendChild(renderer.domElement);

const galaxyGroup = new THREE.Group();
scene.add(galaxyGroup);

// ----------------------------------------------------------------------------
// SOFT PROCEDURAL TEXTURES
// ----------------------------------------------------------------------------
function makeGlowTexture() {
    const size = 256;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const g = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
    g.addColorStop(0.0, 'rgba(255,255,255,1.0)');
    g.addColorStop(0.18, 'rgba(255,242,225,0.92)');
    g.addColorStop(0.45, 'rgba(255,200,150,0.30)');
    g.addColorStop(0.75, 'rgba(100,180,255,0.08)');
    g.addColorStop(1.0, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}
const glowTex = makeGlowTexture();

function makeDotTexture() {
    const size = 64;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d');
    const g = ctx.createRadialGradient(size/2, size/2, 0, size/2, size/2, size/2);
    g.addColorStop(0.0, 'rgba(255,255,255,1.0)');
    g.addColorStop(0.35, 'rgba(255,255,255,0.9)');
    g.addColorStop(0.75, 'rgba(255,255,255,0.2)');
    g.addColorStop(1.0, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
}
const dotTex = makeDotTexture();

// ----------------------------------------------------------------------------
// COLOR PALETTE (80% Cool White/Cyan, 20% Warm Amber)
// ----------------------------------------------------------------------------
const coolColors = [
    new THREE.Color(0xffffff),
    new THREE.Color(0xd2edff),
    new THREE.Color(0x9fd0ff),
    new THREE.Color(0x6ec0ff)
];
const warmColors = [
    new THREE.Color(0xffb060),
    new THREE.Color(0xff8a3d)
];
function pickColor() {
    if (Math.random() < 0.8) {
        return coolColors[Math.floor(Math.random() * coolColors.length)];
    } else {
        return warmColors[Math.floor(Math.random() * warmColors.length)];
    }
}

// ----------------------------------------------------------------------------
// CINEMATIC SHADER (Differential Keplerian Flow + ACES Tone Mapping)
// ----------------------------------------------------------------------------
const particleVertexShader = `
    attribute float size;
    attribute vec3 customColor;
    attribute float layerType; // 0: Core, 1: Arms, 2: Halo
    attribute float radius;
    attribute float initialAngle;

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
        float angularVelocity = (layerType == 1.0) 
            ? (0.28 / sqrt(max(0.8, radius * 0.45)))
            : ((layerType == 0.0) ? 0.35 : 0.08);

        float currentAngle = initialAngle + angularVelocity * time * (0.8 + energy * 0.3) * speedMul;

        // Radial outward energy ripple
        float wave = sin(radius * 1.8 - time * 2.2) * 0.04 * energy;
        float currentR = radius * (1.0 + wave);

        vec3 pos;
        if (layerType == 1.0) {
            pos.x = cos(currentAngle) * currentR + position.x;
            pos.z = sin(currentAngle) * currentR + position.z;
            pos.y = position.y + sin(currentAngle * 2.0 + time * 1.5) * 0.06;
        } else {
            // Core and halo rotate smoothly
            float c = cos(currentAngle);
            float s = sin(currentAngle);
            pos.x = position.x * c - position.z * s;
            pos.z = position.x * s + position.z * c;
            pos.y = position.y;
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

        // Quantum twinkle shimmer
        float twinkle = sin(time * 8.0 + radius * 5.0) * 0.12 + 0.88;

        vec4 mvPosition = viewMatrix * worldPos;

        // Attenuated point size with depth
        gl_PointSize = size * (24.0 / -mvPosition.z) * twinkle * (1.0 + energy * 0.25);
        gl_PointSize = clamp(gl_PointSize, 1.0, 32.0);

        gl_Position = projectionMatrix * mvPosition;

        if (layerType == 0.0) vAlpha = 0.95;
        else if (layerType == 1.0) vAlpha = 0.88;
        else vAlpha = 0.45;
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

        vec3 baseCol = vColor + colorShift * energy * 0.6;
        vec3 hdrCol = baseCol * texColor.a * (1.25 + energy * 0.4);

        vec3 toneMapped = ACESFilm(hdrCol);
        gl_FragColor = vec4(toneMapped, vAlpha * texColor.a);
    }
`;

const particleUniforms = {
    time: { value: 0.0 },
    energy: { value: currentEnergy },
    pulse: { value: 1.0 },
    speedMul: { value: currentSpeedMul },
    colorShift: { value: currentColorShift },
    uTexture: { value: dotTex },
    uMouseWorld: { value: new THREE.Vector3(999, 999, 999) },
    uMouseRadius: { value: 4.0 },
    uMouseStrength: { value: 0.0 }
};

const particleMaterial = new THREE.ShaderMaterial({
    uniforms: particleUniforms,
    vertexShader: particleVertexShader,
    fragmentShader: particleFragmentShader,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true
});

let fieldGeometry = null;
let fieldPoints = null;

function buildField() {
    const total = CONFIG.coreParticles + CONFIG.armParticles + CONFIG.haloParticles;

    const positions = new Float32Array(total * 3);
    const colors = new Float32Array(total * 3);
    const sizes = new Float32Array(total);
    const layerTypes = new Float32Array(total);
    const radii = new Float32Array(total);
    const initialAngles = new Float32Array(total);

    let idx = 0;

    // 1. CORE BULGE: True spherical volume distribution
    for (let i = 0; i < CONFIG.coreParticles; i++) {
        const u = Math.random();
        const r = CONFIG.coreRadius * Math.cbrt(u);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        const x = r * Math.sin(phi) * Math.cos(theta);
        const y = r * Math.sin(phi) * Math.sin(theta) * 0.65;
        const z = r * Math.cos(phi);

        positions[idx * 3 + 0] = x;
        positions[idx * 3 + 1] = y;
        positions[idx * 3 + 2] = z;

        const c = Math.random() < 0.9
            ? new THREE.Color(0xffffff).lerp(new THREE.Color(0xffecd0), Math.random() * 0.5)
            : pickColor();

        colors[idx * 3 + 0] = c.r;
        colors[idx * 3 + 1] = c.g;
        colors[idx * 3 + 2] = c.b;

        sizes[idx] = 1.3 + Math.random() * 1.0;
        layerTypes[idx] = 0.0;
        radii[idx] = r;
        initialAngles[idx] = theta;
        idx++;
    }

    // 2. PRIMARY 2-ARM SPIRAL
    for (let i = 0; i < CONFIG.armParticles; i++) {
        const armIndex = i % CONFIG.armCount;
        const t = Math.pow(Math.random(), 1.4);
        const radius = CONFIG.coreRadius * 0.6 + t * (CONFIG.galaxyRadius - CONFIG.coreRadius * 0.6);

        const armAngle = (armIndex / CONFIG.armCount) * Math.PI * 2;
        const spinAngle = radius * CONFIG.spin * 0.35;
        const scatterAngle = (Math.random() - 0.5) * 0.5 * (1.0 - t * 0.4);
        const baseAngle = armAngle + spinAngle + scatterAngle;

        const spreadMag = CONFIG.armSpread * (0.3 + (1.0 - t) * 0.7);
        const jitterX = (Math.random() - 0.5) * spreadMag;
        const jitterZ = (Math.random() - 0.5) * spreadMag;
        const jitterY = (Math.random() - 0.5) * CONFIG.vertSpread * (0.4 + (1.0 - t));

        // Store jitter in position buffer, radial motion in shader
        positions[idx * 3 + 0] = jitterX;
        positions[idx * 3 + 1] = jitterY;
        positions[idx * 3 + 2] = jitterZ;

        const c = pickColor();
        colors[idx * 3 + 0] = c.r;
        colors[idx * 3 + 1] = c.g;
        colors[idx * 3 + 2] = c.b;

        sizes[idx] = (0.7 + Math.random() * 0.9) * (1.0 - t * 0.3);
        layerTypes[idx] = 1.0;
        radii[idx] = radius;
        initialAngles[idx] = baseAngle;
        idx++;
    }

    // 3. HALO: Background cosmic dust
    for (let i = 0; i < CONFIG.haloParticles; i++) {
        const r = CONFIG.galaxyRadius * (0.55 + Math.random() * 0.95);
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);

        const x = r * Math.sin(phi) * Math.cos(theta);
        const y = r * Math.sin(phi) * Math.sin(theta) * 0.28;
        const z = r * Math.cos(phi);

        positions[idx * 3 + 0] = x;
        positions[idx * 3 + 1] = y;
        positions[idx * 3 + 2] = z;

        const c = pickColor();
        colors[idx * 3 + 0] = c.r;
        colors[idx * 3 + 1] = c.g;
        colors[idx * 3 + 2] = c.b;

        sizes[idx] = 0.4 + Math.random() * 0.5;
        layerTypes[idx] = 2.0;
        radii[idx] = r;
        initialAngles[idx] = theta;
        idx++;
    }

    fieldGeometry = new THREE.BufferGeometry();
    fieldGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    fieldGeometry.setAttribute('customColor', new THREE.BufferAttribute(colors, 3));
    fieldGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    fieldGeometry.setAttribute('layerType', new THREE.BufferAttribute(layerTypes, 1));
    fieldGeometry.setAttribute('radius', new THREE.BufferAttribute(radii, 1));
    fieldGeometry.setAttribute('initialAngle', new THREE.BufferAttribute(initialAngles, 1));

    fieldPoints = new THREE.Points(fieldGeometry, particleMaterial);
    galaxyGroup.add(fieldPoints);
    return fieldPoints;
}

buildField();

// ----------------------------------------------------------------------------
// NUCLEUS GLOW SPRITES (Soft Optical Glow, No Hard Edges)
// ----------------------------------------------------------------------------
const nucleusMat = new THREE.SpriteMaterial({
    map: glowTex,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false
});
const nucleus = new THREE.Sprite(nucleusMat);
nucleus.scale.set(4.5, 4.5, 1);
galaxyGroup.add(nucleus);

const hotMat = new THREE.SpriteMaterial({
    map: glowTex,
    blending: THREE.AdditiveBlending,
    transparent: true,
    depthWrite: false
});
const hotCenter = new THREE.Sprite(hotMat);
hotCenter.scale.set(1.6, 1.6, 1);
galaxyGroup.add(hotCenter);

// Point light for environment reflections
const coreLight = new THREE.PointLight(0xffffff, 2.0, 15);
galaxyGroup.add(coreLight);

// ----------------------------------------------------------------------------
// STEADICAM CAMERA PHYSICS & INTERACTION
// ----------------------------------------------------------------------------
let mouseX = 0, mouseY = 0;
let isDragging = false;
let prevPointerX = 0, prevPointerY = 0;

let orbitRadius = Math.hypot(CONFIG.camBaseY, CONFIG.camBaseZ);
let orbitPhi = Math.atan2(CONFIG.camBaseY, CONFIG.camBaseZ);
let orbitTheta = 0.0;

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
    particleUniforms.uMouseWorld.value.copy(worldPos);
    particleUniforms.uMouseStrength.value = 1.0;
});

window.addEventListener('mouseleave', () => {
    particleUniforms.uMouseStrength.value = 0.0;
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
    targetOrbitRadius = Math.hypot(CONFIG.camBaseY, CONFIG.camBaseZ);
    targetOrbitPhi = Math.atan2(CONFIG.camBaseY, CONFIG.camBaseZ);
    targetOrbitTheta = 0.0;
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
            nucleus.material.color.set(STATES[name].tint);
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
// ANIMATION LOOP — Differential Rotation & Poly-Rhythmic Breathing
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

    // Poly-rhythmic breathing (sub-bass respiration + convective pulse)
    const subBass = 1.0 + Math.sin(t * 1.6) * 0.06 * currentEnergy;
    const convective = 1.0 + Math.sin(t * 3.2) * 0.03;
    const micPulse = 1.0 + currentMicLevel * 0.75;
    const totalPulse = subBass * convective * micPulse;

    // Pass uniforms to GPU
    particleUniforms.time.value = t;
    particleUniforms.energy.value = currentEnergy;
    particleUniforms.pulse.value = totalPulse;
    particleUniforms.speedMul.value = currentSpeedMul * (1.0 + currentMicLevel * 1.5);
    particleUniforms.colorShift.value.copy(currentColorShift);

    // Nucleus optical breathing
    nucleus.scale.set(4.5 * totalPulse * currentEnergy, 4.5 * totalPulse * currentEnergy, 1);
    hotCenter.scale.set(1.6 * totalPulse, 1.6 * totalPulse, 1);
    coreLight.intensity = (2.0 + currentEnergy * 1.0) * micPulse;

    // Steadicam camera physics & subtle autonomous micro-drift
    orbitTheta += (targetOrbitTheta - orbitTheta) * 0.05;
    orbitPhi += (targetOrbitPhi - orbitPhi) * 0.05;
    orbitRadius += (targetOrbitRadius - orbitRadius) * 0.05;

    const driftX = Math.sin(t * 0.4) * 0.2;
    const driftY = Math.cos(t * 0.3) * 0.12;

    const orbitX = orbitRadius * Math.sin(orbitPhi) * Math.sin(orbitTheta);
    const orbitY = orbitRadius * Math.cos(orbitPhi);
    const orbitZ = orbitRadius * Math.sin(orbitPhi) * Math.cos(orbitTheta);

    const targetCamX = orbitX + mouseX * 2.2 + driftX;
    const targetCamY = orbitY - mouseY * 1.3 + driftY;

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
window.fieldGeometry = fieldGeometry;
window.galaxyGeometry = fieldGeometry;
window.initMicrophone = initMicrophone;
window.disableMicrophone = disableMicrophone;
