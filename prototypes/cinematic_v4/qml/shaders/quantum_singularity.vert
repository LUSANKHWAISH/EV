VARYING vec2 vUv;
VARYING float vDoppler;
VARYING float vType; // 0 = Accretion Disk, 1 = Bipolar Jet, 2 = Photon Ring
VARYING float vDepth01;
VARYING float vTwinkle;
VARYING float vVisibility;

const float TAU = 6.28318530718;

void MAIN()
{
    vec4 seed = INSTANCE_DATA;

    float phaseSeed    = seed.x;
    float typeSeed     = seed.y;
    float paramSeed    = seed.z;
    float speedSeed    = seed.w;

    float speedFactor = orbitSpeed > 0.0 ? orbitSpeed : 1.0;

    // Component Classification:
    // 0.00 - 0.60 (60%): Relativistic Accretion Disk with Gravitational Lensing
    // 0.60 - 0.82 (22%): Bipolar Relativistic Magnetic Jets (+/- Y axis)
    // 0.82 - 1.00 (18%): Intense Gravitational Photon Ring
    float pType = 0.0;
    vec3 center = vec3(0.0);
    float doppler = 0.5; // 0 = max redshift, 1 = max blueshift
    float baseSize = 6.0;

    if (typeSeed < 0.60) {
        // --- 1. ACCRETION DISK WITH GRAVITATIONAL LENSING ---
        pType = 0.0;
        float uR = typeSeed / 0.60;
        float r = mix(68.0, 360.0, pow(uR, 1.15));

        // Relativistic Keplerian velocity with frame dragging
        float omega = (0.16 / (1.0 + r / 90.0) + 0.024) * speedFactor;
        float speedMult = mix(0.92, 1.08, speedSeed);
        float theta = phaseSeed * TAU + timeSeconds * (omega * speedMult);

        // Breathing & voice pulsation
        float breathing = sin(r * 0.05 - timeSeconds * 2.5) * (activity * mix(6.0, 16.0, smoothstep(70.0, 220.0, r)));
        float activeR = r + breathing;

        // Disk inclination: tilted ~32 degrees toward viewer
        float diskInc = radians(32.0);
        float zThickness = (paramSeed * 2.0 - 1.0) * mix(8.0, 26.0, smoothstep(70.0, 300.0, r));

        // Un-lensed flat disk coordinates:
        float xD = activeR * sin(theta);
        float zD = activeR * cos(theta);
        float yD = zThickness;

        // Apply disk pitch tilt (32 degrees):
        float cosI = cos(diskInc);
        float sinI = sin(diskInc);
        float yT = yD * cosI - zD * sinI;
        float zT = yD * sinI + zD * cosI;

        // Gravitational Lensing (Einstein light bending over & under the event horizon):
        // In general relativity (Interstellar / Gargantua), light from behind the black hole
        // is bent over the top and under the bottom, creating circular luminous arcs framing the event horizon.
        if (zD < -20.0) {
            float rearIntensity = smoothstep(-20.0, -180.0, zD);
            float lensSign = (paramSeed >= 0.5) ? 1.0 : -1.0;
            
            // Arch radius matched to particle orbital radius
            float rArch = mix(95.0, 185.0, pow(uR, 0.75));
            float xDistSquared = xD * xD;
            if (xDistSquared < rArch * rArch) {
                float archY = sqrt(rArch * rArch - xDistSquared) * lensSign;
                float lensBlend = rearIntensity * 0.92;
                yT = mix(yT, archY + yD * 0.3, lensBlend);
                zT = mix(zT, -35.0, lensBlend * 0.75);
            }
        }

        center = vec3(xD, yT, clamp(zT, -280.0, 210.0));

        // Doppler Beaming:
        // Particles moving toward viewer (+Z / +X depending on orbital quadrant)
        // have relativistic velocity boosting and spectral blueshift.
        // Receding particles have spectral redshift.
        float orbitalVelocity = -sin(theta); // directional tangent
        float viewComponent = orbitalVelocity * cosI;
        doppler = clamp(0.5 + 0.5 * viewComponent, 0.0, 1.0);

        baseSize = mix(5.5, 9.5, fract(phaseSeed * 31.17 + speedSeed * 19.43));

    } else if (typeSeed < 0.82) {
        // --- 2. BIPOLAR RELATIVISTIC JETS (+/- Y POLES) ---
        pType = 1.0;
        float uJet = (typeSeed - 0.60) / 0.22;
        float jetSign = (paramSeed < 0.5) ? 1.0 : -1.0;

        // Jet distance along pole: 50 px to 440 px
        float jetDist = mix(50.0, 440.0, pow(uJet, 1.10));

        // Helical magnetic collimation
        float jetRadius = mix(4.0, 36.0, sqrt(uJet)) * (1.0 + activity * 0.40);
        float helixSpeed = 3.2 * speedFactor;
        float helixAngle = jetDist * 0.08 - timeSeconds * helixSpeed + phaseSeed * TAU;

        // High velocity ejection
        float jetX = jetRadius * cos(helixAngle);
        float jetZ = jetRadius * sin(helixAngle);
        float jetY = jetDist * jetSign;

        // Slight magnetic flare pulsation
        float pulse = sin(jetDist * 0.12 - timeSeconds * 6.0) * (activity * 8.0);
        jetY += pulse * jetSign;

        center = vec3(jetX, jetY, jetZ);

        // Jets are ultra-relativistic: high energy blueshifted plasma
        doppler = 0.85 + 0.15 * sin(jetDist * 0.06 - timeSeconds * 4.0);
        baseSize = mix(6.0, 11.0, fract(speedSeed * 47.11));

    } else {
        // --- 3. INTENSE GRAVITATIONAL PHOTON RING ---
        pType = 2.0;
        float uRing = (typeSeed - 0.82) / 0.18;
        float rRing = mix(82.0, 116.0, uRing);

        // Near-lightspeed orbital rotation
        float omegaRing = (0.24 + 0.06 * speedSeed) * speedFactor;
        float thetaRing = phaseSeed * TAU + timeSeconds * omegaRing;

        // Photon ring forms an intense, thin spherical shell framing the event horizon
        float ringLat = (paramSeed * 2.0 - 1.0) * radians(78.0);
        center.x = rRing * cos(ringLat) * sin(thetaRing);
        center.y = rRing * sin(ringLat);
        center.z = rRing * cos(ringLat) * cos(thetaRing);

        // Photon ring has extreme relativistic brightness
        doppler = 0.70 + 0.30 * cos(thetaRing);
        baseSize = mix(4.0, 7.5, fract(phaseSeed * 53.29));
    }

    // Depth pass filtering:
    // depthPass: 0 = all particles
    // depthPass: 1 = rear particles only (z <= 0.0)
    // depthPass: 2 = front particles only (z > 0.0)
    if (depthPass == 1 && center.z > 0.0) {
        POSITION = vec4(0.0, 0.0, 2.0, 1.0);
        return;
    }
    if (depthPass == 2 && center.z <= 0.0) {
        POSITION = vec4(0.0, 0.0, 2.0, 1.0);
        return;
    }

    // Normalized depth [0, 1]
    float depth01 = clamp((center.z + 280.0) / 490.0, 0.0, 1.0);

    // 3D Perspective Depth Scaling:
    // Far away: small crisp stardust (0.65x)
    // Close in front: large radiant bokeh discs (1.40x)
    float depthSizeFactor = mix(0.65, 1.40, pow(depth01, 1.15));
    float particleSize = baseSize * depthSizeFactor;

    // Camera billboarding
    vec4 worldCenter = MODEL_MATRIX * vec4(center, 1.0);
    vec4 viewCenter  = VIEW_MATRIX * worldCenter;

    viewCenter.xy += VERTEX.xy * particleSize * pixelToWorld * 0.01;
    POSITION = PROJECTION_MATRIX * viewCenter;

    // Screen coordinates for UI margin attenuation
    vec2 ndc = POSITION.xy / max(POSITION.w, 0.0001);
    vec2 screenPos = ndc * 0.5 + 0.5;

    // UI Readability: softly attenuate particles over dense text panels
    float leftFactor = smoothstep(0.16, 0.24, screenPos.x);
    float rightFactor = smoothstep(0.86, 0.78, screenPos.x);
    float topFactor = smoothstep(0.92, 0.84, screenPos.y);
    float bottomFactor = smoothstep(0.18, 0.26, screenPos.y);
    float uiReadability = mix(0.45, 1.0, min(min(leftFactor, rightFactor), min(topFactor, bottomFactor)));

    // Twinkle & relativistic shimmering
    float twinkle = 0.85 + 0.15 * sin(timeSeconds * mix(2.0, 5.0, speedSeed) + phaseSeed * 50.0);

    // Doppler intensity boost: blueshifted approaching particles are significantly brighter
    float dopplerBrightness = mix(0.55, 1.45, doppler);

    // Visibility:
    float deployFade = smoothstep(0.15, 0.75, deployment);
    float depthBrightness = mix(0.65, 1.20, depth01);
    float activityBoost = 1.0 + activity * 0.45;

    // Screen edge feathering
    float edgeDist = max(abs(ndc.x), abs(ndc.y));
    float edgeFeather = 1.0 - smoothstep(0.90, 1.02, edgeDist);

    vVisibility = deployFade * depthBrightness * dopplerBrightness * twinkle * activityBoost * edgeFeather * uiReadability;
    vDoppler = doppler;
    vType = pType;
    vDepth01 = depth01;
    vTwinkle = twinkle;
    vUv = UV0;
}
