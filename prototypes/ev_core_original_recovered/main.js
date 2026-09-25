const CONFIG = {
    particleCount: 50000,
    galaxyRadius: 8,
    arms: 2,
    spin: 1.8,
    randomness: 0.25,
    randomnessPower: 2.0,
    verticalSpread: 2.5,
    particleSize: 1.8,
    rotationSpeed: 0.08,
    coreRadius: 1.5,
    coreDensity: 1.8,
    armWidth: 0.2,
    depthRandomness: 0.5
};

// State definition
const STATES = {
    IDLE: 'IDLE',
    LISTENING: 'LISTENING',
    THINKING: 'THINKING',
    PLANNING: 'PLANNING',
    APPROVAL: 'APPROVAL',
    EXECUTING: 'EXECUTING',
    VERIFYING: 'VERIFYING',
    SPEAKING: 'SPEAKING',
    SUCCESS: 'SUCCESS',
    FAILED: 'FAILED',
    SLEEP: 'SLEEP'
};

// Target state variables for interpolation
let currentState = STATES.IDLE;
let targetEnergy = 0.35;
let currentEnergy = 0.35;
let targetColorShift = new THREE.Color(0x000000);
let currentColorShift = new THREE.Color(0x000000);
let targetRotationSpeed = CONFIG.rotationSpeed;
let currentRotationSpeed = CONFIG.rotationSpeed;
let pulseIntensity = 0.0;
let timePhase = 0.0;

// Setup Scene, Camera, Renderer
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x000000);

// Default elevated ~50-degree idle camera setup (camera at [0, 10, 8] -> atan2(10, 8) ≈ 51.3°)
const DEFAULT_RADIUS = Math.hypot(10, 8); // ~12.8062
const DEFAULT_PHI = Math.acos(10 / DEFAULT_RADIUS); // ~0.6751 rad (38.7° from zenith, 51.3° elevation)
const DEFAULT_THETA = 0.0;

const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 10, 8);
camera.lookAt(0, 0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x000000, 1);
container.appendChild(renderer.domElement);

// Core Groups
const coreGroup = new THREE.Group();
const galaxyGroup = new THREE.Group();
const orbitalGroup = new THREE.Group();
scene.add(coreGroup);
coreGroup.add(galaxyGroup);
coreGroup.add(orbitalGroup);

// --- Custom Shader for Particles with GPU Cursor Displacement ---
const particleVertexShader = `
    attribute float size;
    attribute vec3 customColor;
    varying vec3 vColor;
    uniform float time;
    uniform float energy;
    
    // Cursor displacement uniforms
    uniform vec3 uMouseWorld;
    uniform float uMouseRadius;
    uniform float uMouseStrength;
    
    void main() {
        vColor = customColor;
        
        // Transform vertex to world coordinates
        vec4 worldPos = modelMatrix * vec4(position, 1.0);
        
        // Cursor displacement effect: gentle magnetic ATTRACTION + subtle swirl
        vec3 toCursor = uMouseWorld - worldPos.xyz;
        float dist = length(toCursor);
        
        if (dist < uMouseRadius && uMouseStrength > 0.001) {
            float normDist = dist / uMouseRadius;
            float falloff = (1.0 - normDist) * (1.0 - normDist); // smooth quadratic falloff
            
            // Inverted radial direction: particles pulled TOWARD cursor position
            vec3 pullDir = normalize(toCursor + vec3(0.0001, 0.0001, 0.0001));
            // Gentle tangent swirl curving toward cursor
            vec3 swirlDir = vec3(-pullDir.z, pullDir.y * 0.2, pullDir.x);
            
            // Tuned pull strength: gentle noticeable pull without snapping
            vec3 displacement = (pullDir * 0.85 + swirlDir * 0.35) * (falloff * uMouseStrength * 1.2);
            worldPos.xyz += displacement;
        }
        
        // Subtle twinkle based on position and time
        float twinkle = sin(time * 2.0 + position.x * 5.0) * 0.5 + 0.5;
        
        vec4 mvPosition = viewMatrix * worldPos;
        gl_PointSize = size * (1.0 + energy * 0.5 + twinkle * 0.2) * (30.0 / -mvPosition.z);
        gl_Position = projectionMatrix * mvPosition;
    }
`;

const particleFragmentShader = `
    varying vec3 vColor;
    uniform vec3 colorShift;
    uniform float energy;
    
    void main() {
        // Create circular soft particle
        vec2 xy = gl_PointCoord.xy - vec2(0.5);
        float ll = length(xy);
        if(ll > 0.5) discard;
        
        // Soft edge gradient
        float alpha = (0.5 - ll) * 2.0;
        alpha = pow(alpha, 1.5);
        
        // Additive blending effect with color shift
        vec3 finalColor = vColor + colorShift * energy;
        gl_FragColor = vec4(finalColor, alpha);
    }
`;

// Uniforms
const particleUniforms = {
    time: { value: 0.0 },
    energy: { value: currentEnergy },
    colorShift: { value: currentColorShift },
    uMouseWorld: { value: new THREE.Vector3(999, 999, 999) },
    uMouseRadius: { value: 3.5 },
    uMouseStrength: { value: 0.0 }
};

const galaxyMaterial = new THREE.ShaderMaterial({
    uniforms: particleUniforms,
    vertexShader: particleVertexShader,
    fragmentShader: particleFragmentShader,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    transparent: true
});

// --- Galaxy Particle Generation ---
let galaxyGeometry = null;
let galaxyPoints = null;

function generateGalaxy() {
    if(galaxyPoints !== null) {
        galaxyGroup.remove(galaxyPoints);
        galaxyGeometry.dispose();
    }
    
    galaxyGeometry = new THREE.BufferGeometry();
    const positions = new Float32Array(CONFIG.particleCount * 3);
    const colors = new Float32Array(CONFIG.particleCount * 3);
    const sizes = new Float32Array(CONFIG.particleCount);
    
    const colorWhite = new THREE.Color(0xffffff);
    const colorCool1 = new THREE.Color(0xcceeff);
    const colorCool2 = new THREE.Color(0x99ccff);
    const colorAmber = new THREE.Color(0xffaa44);
    const colorOrange = new THREE.Color(0xff8822);
    
    for(let i = 0; i < CONFIG.particleCount; i++) {
        const i3 = i * 3;
        
        // Core vs Arms distribution
        let radius = Math.random() * CONFIG.galaxyRadius;
        // Bias towards center (density)
        radius = Math.pow(Math.random(), CONFIG.coreDensity) * CONFIG.galaxyRadius;
        
        const spinAngle = radius * CONFIG.spin;
        const branchAngle = (i % CONFIG.arms) * ((Math.PI * 2) / CONFIG.arms);
        
        // Volumetric randomness envelope to avoid vertical streak at center
        const coreTaper = 1.0 - (radius / CONFIG.galaxyRadius);
        const randomX = Math.pow(Math.random(), CONFIG.randomnessPower) * (Math.random() < 0.5 ? 1 : -1) * CONFIG.randomness * (radius + 2.0 * coreTaper);
        const randomY = Math.pow(Math.random(), CONFIG.randomnessPower) * (Math.random() < 0.5 ? 1 : -1) * CONFIG.verticalSpread * (0.3 + 0.7 * coreTaper);
        const randomZ = Math.pow(Math.random(), CONFIG.randomnessPower) * (Math.random() < 0.5 ? 1 : -1) * CONFIG.randomness * (radius + 2.0 * coreTaper);
        
        positions[i3] = Math.cos(branchAngle + spinAngle) * radius + randomX;
        positions[i3+1] = randomY;
        positions[i3+2] = Math.sin(branchAngle + spinAngle) * radius + randomZ;
        
        // Scattered Palette
        let particleColor = new THREE.Color();
        const randColor = Math.random();
        
        if (randColor < 0.8) {
            // 80% majority: White / cool blue-white
            const subRand = Math.random();
            if (subRand < 0.4) particleColor.copy(colorWhite);
            else if (subRand < 0.7) particleColor.copy(colorCool1);
            else particleColor.copy(colorCool2);
        } else {
            // 20% minority: Warm amber/orange scattered
            if (Math.random() < 0.5) particleColor.copy(colorAmber);
            else particleColor.copy(colorOrange);
        }
        
        colors[i3] = particleColor.r;
        colors[i3+1] = particleColor.g;
        colors[i3+2] = particleColor.b;
        
        const distRatio = radius / CONFIG.galaxyRadius;
        
        // Size variation
        sizes[i] = Math.random() * CONFIG.particleSize + (0.01 * (1.0 - distRatio));
    }
    
    galaxyGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    galaxyGeometry.setAttribute('customColor', new THREE.BufferAttribute(colors, 3));
    galaxyGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    
    galaxyPoints = new THREE.Points(galaxyGeometry, galaxyMaterial);
    galaxyGroup.add(galaxyPoints);
}

generateGalaxy();

// --- Central Nucleus ---
const nucleusGroup = new THREE.Group();
coreGroup.add(nucleusGroup);

// 1. Luminous Point (Core bright center)
const coreLight = new THREE.PointLight(0xffffff, 2.5, 12);
nucleusGroup.add(coreLight);

// 2. Translucent Shell
const shellGeometry = new THREE.SphereGeometry(CONFIG.coreRadius * 0.5, 64, 64);
const shellMaterial = new THREE.MeshBasicMaterial({
    color: 0xffccaa,
    transparent: true,
    opacity: 0.12,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
    wireframe: false
});
const shell = new THREE.Mesh(shellGeometry, shellMaterial);
nucleusGroup.add(shell);

// 3. Inner dense cloud (using points)
const innerCloudGeo = new THREE.BufferGeometry();
const icCount = 3000;
const icPos = new Float32Array(icCount * 3);
const icCol = new Float32Array(icCount * 3);
const icSizes = new Float32Array(icCount);
for(let i=0; i<icCount; i++) {
    const r = Math.pow(Math.random(), 2.0) * (CONFIG.coreRadius * 0.45);
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos((Math.random() * 2) - 1);
    icPos[i*3] = r * Math.sin(phi) * Math.cos(theta);
    icPos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
    icPos[i*3+2] = r * Math.cos(phi);
    icCol[i*3] = 1.0; icCol[i*3+1] = 0.9; icCol[i*3+2] = 0.8;
    icSizes[i] = Math.random() * 2.0 + 1.0;
}
innerCloudGeo.setAttribute('position', new THREE.BufferAttribute(icPos, 3));
innerCloudGeo.setAttribute('customColor', new THREE.BufferAttribute(icCol, 3));
innerCloudGeo.setAttribute('size', new THREE.BufferAttribute(icSizes, 1));
const innerCloud = new THREE.Points(innerCloudGeo, galaxyMaterial);
nucleusGroup.add(innerCloud);


// ============================================================================
// FEATURE 1: Cursor-Reactive Particle Displacement
// ============================================================================
const raycaster = new THREE.Raycaster();
const mouseNDC = new THREE.Vector2(-10, -10);
let mouseX = 0;
let mouseY = 0;
let isMouseOnScreen = false;
let hasInitialMouseHit = false;
const galaxyCenter = new THREE.Vector3(0, 0, 0);
const depthPlane = new THREE.Plane();
const planeNormal = new THREE.Vector3();
const hitPoint = new THREE.Vector3();

const targetMouseWorld = new THREE.Vector3(0, 0, 0);
const currentMouseWorld = new THREE.Vector3(0, 0, 0);
let targetMouseStrength = 0.0;
let currentMouseStrength = 0.0;

document.addEventListener('mousemove', (e) => {
    mouseX = (e.clientX / window.innerWidth) * 2 - 1;
    mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
    mouseNDC.x = mouseX;
    mouseNDC.y = mouseY;
    isMouseOnScreen = true;
});

document.addEventListener('mouseleave', () => {
    isMouseOnScreen = false;
    hasInitialMouseHit = false;
});


// ============================================================================
// FEATURE 2: Free Drag-to-Rotate (Full 3D Orbit Control with Damping)
// ============================================================================
let currentRadius = DEFAULT_RADIUS;
let targetRadius = DEFAULT_RADIUS;
let currentPhi = DEFAULT_PHI;
let targetPhi = DEFAULT_PHI;
let currentTheta = DEFAULT_THETA;
let targetTheta = DEFAULT_THETA;

let isDragging = false;
let prevPointerX = 0;
let prevPointerY = 0;
let velocityTheta = 0;
let velocityPhi = 0;

let currentParallaxX = 0;
let currentParallaxY = 0;

container.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return; // Primary left button only
    isDragging = true;
    prevPointerX = e.clientX;
    prevPointerY = e.clientY;
    velocityTheta = 0;
    velocityPhi = 0;
    try {
        container.setPointerCapture(e.pointerId);
    } catch (_) {}
});

container.addEventListener('pointermove', (e) => {
    if (!isDragging) return;
    const deltaX = e.clientX - prevPointerX;
    const deltaY = e.clientY - prevPointerY;
    prevPointerX = e.clientX;
    prevPointerY = e.clientY;
    
    const rotateSpeed = 0.0055;
    velocityTheta = -deltaX * rotateSpeed;
    velocityPhi = -deltaY * rotateSpeed;
    
    targetTheta += velocityTheta;
    targetPhi += velocityPhi;
    // Clamp polar angle to avoid flipping over poles and gimbal lock
    targetPhi = Math.max(0.06, Math.min(Math.PI - 0.06, targetPhi));
});

function endDrag(e) {
    if (isDragging) {
        isDragging = false;
        try {
            container.releasePointerCapture(e.pointerId);
        } catch (_) {}
    }
}

container.addEventListener('pointerup', endDrag);
container.addEventListener('pointercancel', endDrag);

// Mouse wheel zoom with clamp to prevent geometry clipping
container.addEventListener('wheel', (e) => {
    e.preventDefault();
    targetRadius = Math.max(6.0, Math.min(24.0, targetRadius + Math.sign(e.deltaY) * 1.2));
}, { passive: false });

// Double click to smoothly reset back to default elevated view (~50 degrees)
container.addEventListener('dblclick', () => {
    targetTheta = DEFAULT_THETA;
    targetPhi = DEFAULT_PHI;
    targetRadius = DEFAULT_RADIUS;
    velocityTheta = 0;
    velocityPhi = 0;
});


// ============================================================================
// FEATURE 3: Real Microphone Reactivity (Web Audio API)
// ============================================================================
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
        // AnalyserNode is purely analytical: not connected to audioContext.destination
        
        audioDataArray = new Uint8Array(analyser.frequencyBinCount);
        isMicActive = true;
        
        if (micToggleBtn) {
            micToggleBtn.classList.add('active');
            micToggleBtn.classList.remove('denied');
        }
        if (micBtnLabel) micBtnLabel.innerText = "MIC ACTIVE";
        showMicStatus("Voice Reactivity: Live", "active");
    } catch (err) {
        console.warn("Microphone access failed/denied:", err);
        isMicActive = false;
        if (micToggleBtn) {
            micToggleBtn.classList.remove('active');
            micToggleBtn.classList.add('denied');
        }
        if (micBtnLabel) micBtnLabel.innerText = "MIC DENIED";
        // Required fallback note
        showMicStatus("Mic access denied — voice reactivity disabled", "denied");
    }
}

function disableMicrophone() {
    if (micStream) {
        micStream.getTracks().forEach(track => track.stop());
        micStream = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().catch(() => {});
        audioContext = null;
    }
    isMicActive = false;
    targetMicLevel = 0.0;
    if (micToggleBtn) {
        micToggleBtn.classList.remove('active');
        micToggleBtn.classList.remove('denied');
    }
    if (micBtnLabel) micBtnLabel.innerText = "ENABLE MIC";
    showMicStatus("Voice reactivity: Standby", "");
}

function showMicStatus(text, statusClass) {
    if (micStatusNote) {
        micStatusNote.innerText = text;
        micStatusNote.className = 'mic-note ' + (statusClass || '');
    }
}

if (micToggleBtn) {
    micToggleBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        initMicrophone();
    });
}

// Check permission status on load
if (navigator.permissions && navigator.permissions.query) {
    navigator.permissions.query({ name: 'microphone' }).then(permissionStatus => {
        if (permissionStatus.state === 'granted') {
            initMicrophone();
        }
        permissionStatus.onchange = () => {
            if (permissionStatus.state === 'denied') {
                disableMicrophone();
                showMicStatus("Mic access denied — voice reactivity disabled", "denied");
            }
        };
    }).catch(() => {});
}


// --- Window Resize ---
window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
});

// --- State API ---
const EVCore = {
    setState: function(stateObj) {
        if (stateObj.state && STATES[stateObj.state]) {
            currentState = stateObj.state;
            document.getElementById('current-state-label').innerText = 'STATE: ' + currentState;
            this.applyStateVisuals();
        }
        if (stateObj.energy !== undefined) {
            targetEnergy = stateObj.energy;
        }
    },
    
    applyStateVisuals: function() {
        switch(currentState) {
            case STATES.IDLE:
                targetEnergy = 0.35;
                targetRotationSpeed = CONFIG.rotationSpeed;
                targetColorShift.setHex(0x000000);
                break;
            case STATES.LISTENING:
                targetEnergy = 0.6;
                targetRotationSpeed = CONFIG.rotationSpeed * 1.5;
                targetColorShift.setHex(0x0044aa);
                break;
            case STATES.THINKING:
                targetEnergy = 0.8;
                targetRotationSpeed = CONFIG.rotationSpeed * 3.0;
                targetColorShift.setHex(0x0044aa);
                break;
            case STATES.PLANNING:
                targetEnergy = 0.5;
                targetRotationSpeed = CONFIG.rotationSpeed * 2.0;
                targetColorShift.setHex(0x002244);
                break;
            case STATES.APPROVAL:
                targetEnergy = 0.5;
                targetRotationSpeed = CONFIG.rotationSpeed * 0.5;
                targetColorShift.setHex(0xaa6600); // Amber hint
                break;
            case STATES.EXECUTING:
                targetEnergy = 1.0;
                targetRotationSpeed = CONFIG.rotationSpeed * 4.0;
                targetColorShift.setHex(0x00aaff);
                break;
            case STATES.VERIFYING:
                targetEnergy = 0.7;
                targetRotationSpeed = CONFIG.rotationSpeed * 2.5;
                targetColorShift.setHex(0x00ff88);
                break;
            case STATES.SPEAKING:
                targetEnergy = 0.8;
                targetRotationSpeed = CONFIG.rotationSpeed * 1.2;
                targetColorShift.setHex(0x0066cc);
                break;
            case STATES.SUCCESS:
                targetEnergy = 1.2;
                targetRotationSpeed = CONFIG.rotationSpeed * 1.5;
                targetColorShift.setHex(0x00ffaa);
                setTimeout(() => EVCore.setState({ state: STATES.IDLE }), 1500);
                break;
            case STATES.FAILED:
                targetEnergy = 0.9;
                targetRotationSpeed = CONFIG.rotationSpeed * 0.2;
                targetColorShift.setHex(0xff2200);
                break;
            case STATES.SLEEP:
                targetEnergy = 0.1;
                targetRotationSpeed = CONFIG.rotationSpeed * 0.1;
                targetColorShift.setHex(0x000000);
                break;
        }
    }
};

// --- Keyboard Debug Controls ---
document.addEventListener('keydown', (e) => {
    switch(e.key.toLowerCase()) {
        case '1': EVCore.setState({ state: STATES.IDLE }); break;
        case '2': EVCore.setState({ state: STATES.LISTENING }); break;
        case '3': EVCore.setState({ state: STATES.THINKING }); break;
        case '4': EVCore.setState({ state: STATES.PLANNING }); break;
        case '5': EVCore.setState({ state: STATES.APPROVAL }); break;
        case '6': EVCore.setState({ state: STATES.EXECUTING }); break;
        case '7': EVCore.setState({ state: STATES.VERIFYING }); break;
        case '8': EVCore.setState({ state: STATES.SPEAKING }); break;
        case '9': EVCore.setState({ state: STATES.SUCCESS }); break;
        case '0': EVCore.setState({ state: STATES.FAILED }); break;
        case 's': EVCore.setState({ state: STATES.SLEEP }); break;
    }
});


// ============================================================================
// Animation Loop
// ============================================================================
const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);
    
    const delta = clock.getDelta();
    timePhase += delta;
    
    // Smooth interpolations of state variables
    currentEnergy += (targetEnergy - currentEnergy) * delta * 2.0;
    currentRotationSpeed += (targetRotationSpeed - currentRotationSpeed) * delta * 1.5;
    currentColorShift.lerp(targetColorShift, delta * 2.0);
    
    // --- Live Audio Analysis ---
    if (isMicActive && analyser && audioDataArray) {
        analyser.getByteFrequencyData(audioDataArray);
        let sum = 0;
        const binStart = 2;
        const binEnd = Math.min(64, audioDataArray.length);
        for (let i = binStart; i < binEnd; i++) {
            sum += audioDataArray[i];
        }
        const avg = sum / (binEnd - binStart);
        // Noise gate threshold: values below ~15 are treated as ambient noise
        const normalized = Math.max(0, (avg - 15) / 115.0);
        targetMicLevel = Math.min(1.0, Math.pow(normalized, 1.2));
    } else {
        targetMicLevel = 0.0;
    }
    
    // Audio envelope: swift attack, gentle decay
    const audioLerp = targetMicLevel > currentMicLevel ? 18.0 : 6.0;
    currentMicLevel += (targetMicLevel - currentMicLevel) * delta * audioLerp;
    
    if (micVuBar) {
        micVuBar.style.width = Math.round(currentMicLevel * 100) + '%';
    }
    
    // Mic modulation values
    const micEnergyBoost = currentMicLevel * 1.0;
    const effectiveEnergy = currentEnergy + micEnergyBoost;
    
    // Breathing logic
    let breathing = 0;
    if (currentState === STATES.IDLE || currentState === STATES.LISTENING || currentState === STATES.SLEEP) {
        breathing = Math.sin(timePhase * 1.5) * 0.05 * currentEnergy;
    } else if (currentState === STATES.SPEAKING) {
        breathing = Math.sin(timePhase * 10.0) * 0.15 * currentEnergy;
    } else {
        breathing = Math.sin(timePhase * 3.0) * 0.08 * currentEnergy;
    }
    
    // Nucleus scaling & brightness with mic audio modulation
    const micPulse = currentMicLevel * 0.35;
    const nScale = (1.0 + breathing) * (1.0 + micPulse);
    nucleusGroup.scale.set(nScale, nScale, nScale);
    coreLight.intensity = (2.0 * effectiveEnergy + currentMicLevel * 4.0) * nScale;
    shellMaterial.opacity = 0.12 + currentMicLevel * 0.22;
    
    // Rotations: mic accelerates rotation speed proportionally to loudness
    const effectiveRotationSpeed = currentRotationSpeed * (1.0 + currentMicLevel * 2.5);
    galaxyGroup.rotation.y -= effectiveRotationSpeed * delta;
    
    orbitalGroup.children.forEach(ring => {
        ring.rotation.y += ring.userData.speed * currentRotationSpeed * delta;
    });
    
    // --- Cursor Particle Displacement (GPU Vertex Shader) ---
    targetMouseStrength = isMouseOnScreen ? 1.0 : 0.0;
    currentMouseStrength += (targetMouseStrength - currentMouseStrength) * delta * 6.0;
    
    if (isMouseOnScreen) {
        raycaster.setFromCamera(mouseNDC, camera);
        camera.getWorldDirection(planeNormal);
        planeNormal.negate();
        depthPlane.setFromNormalAndCoplanarPoint(planeNormal, galaxyCenter);
        if (raycaster.ray.intersectPlane(depthPlane, hitPoint)) {
            targetMouseWorld.copy(hitPoint);
            if (!hasInitialMouseHit) {
                currentMouseWorld.copy(hitPoint);
                hasInitialMouseHit = true;
            }
        }
    }
    currentMouseWorld.lerp(targetMouseWorld, delta * 10.0);
    
    // Update Uniforms
    particleUniforms.time.value = timePhase;
    particleUniforms.energy.value = effectiveEnergy;
    particleUniforms.colorShift.value = currentColorShift;
    particleUniforms.uMouseWorld.value.copy(currentMouseWorld);
    particleUniforms.uMouseStrength.value = currentMouseStrength;
    
    // --- Drag-to-Rotate Orbit Control & Hover Parallax ---
    if (!isDragging) {
        velocityTheta *= 0.90;
        velocityPhi *= 0.90;
        targetTheta += velocityTheta;
        targetPhi += velocityPhi;
        targetPhi = Math.max(0.06, Math.min(Math.PI - 0.06, targetPhi));
    }
    
    currentTheta += (targetTheta - currentTheta) * delta * 12.0;
    currentPhi += (targetPhi - currentPhi) * delta * 12.0;
    currentRadius += (targetRadius - currentRadius) * delta * 8.0;
    
    // Spherical to Cartesian base position
    const sinPhi = Math.sin(currentPhi);
    const cosPhi = Math.cos(currentPhi);
    const sinTheta = Math.sin(currentTheta);
    const cosTheta = Math.cos(currentTheta);
    
    const baseCameraPos = new THREE.Vector3(
        currentRadius * sinPhi * sinTheta,
        currentRadius * cosPhi,
        currentRadius * sinPhi * cosTheta
    );
    
    // Parallax sway: active during hover when not dragging
    const targetParallaxX = isDragging ? 0.0 : mouseX * 1.5;
    const targetParallaxY = isDragging ? 0.0 : mouseY * 1.5;
    currentParallaxX += (targetParallaxX - currentParallaxX) * delta * 4.0;
    currentParallaxY += (targetParallaxY - currentParallaxY) * delta * 4.0;
    
    const depthBreathing = Math.sin(timePhase * 0.5) * 0.2;
    
    // Local camera coordinate frame
    const viewDir = baseCameraPos.clone().negate().normalize();
    const upRef = Math.abs(viewDir.y) > 0.98 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0);
    const camRight = new THREE.Vector3().crossVectors(viewDir, upRef).normalize();
    const camUp = new THREE.Vector3().crossVectors(camRight, viewDir).normalize();
    
    camera.position.copy(baseCameraPos)
        .addScaledVector(camRight, currentParallaxX)
        .addScaledVector(camUp, currentParallaxY + depthBreathing);
    camera.lookAt(0, 0, 0);
    
    renderer.render(scene, camera);
}

// Start
EVCore.setState({ state: STATES.IDLE });
animate();

