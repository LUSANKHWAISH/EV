VARYING vec2 vUv;
VARYING float vDepth01;
VARYING float vTwinkle;
VARYING vec4 vSeed;
VARYING float vVisibility;
VARYING float vIsCore;

const float TAU = 6.28318530718;

void MAIN()
{
    vec4 seed = INSTANCE_DATA;

    float phaseSeed    = seed.x;
    float radiusSeed   = seed.y;
    float latitudeSeed = seed.z;
    float speedSeed    = seed.w;

    // 1. Population Distribution centered around Core (0, 0, 0):
    // All orbits are bounded within r in [50.0, 350.0] so the entire orbit
    // visibly loops around the core without escaping off-screen or approaching the camera lens.
    float r;
    float isCore = 0.0;
    if (radiusSeed < 0.20) {
        float u = radiusSeed / 0.20;
        r = mix(50.0, 120.0, sqrt(u));
        isCore = 1.0 - smoothstep(65.0, 110.0, r);
    } else if (radiusSeed < 0.75) {
        float u = (radiusSeed - 0.20) / 0.55;
        r = mix(120.0, 240.0, pow(u, 1.10));
    } else {
        float u = (radiusSeed - 0.75) / 0.25;
        r = mix(240.0, 350.0, pow(u, 1.15));
    }

    // 2. Calm, Majestic Keplerian Orbital Velocity (Calibrated from WARNING mode)
    float speedFactor = orbitSpeed > 0.0 ? orbitSpeed : 1.0;
    float omega = (0.11 / (1.0 + r / 120.0) + 0.025) * speedFactor;
    float speedMult = mix(0.92, 1.08, speedSeed);

    // Orbital phase:
    float theta = phaseSeed * TAU + timeSeconds * (omega * speedMult);

    // Dynamic voice & energy pulsation
    float breathing = sin(r * 0.045 - timeSeconds * 2.0) * (activity * mix(5.0, 12.0, smoothstep(60.0, 200.0, r)));
    float activeR = r + breathing;

    // 3. True 3D Multi-Inclination Orbital Planes (Matching Video-20807)
    // Particles orbit along inclined 3D ellipses encircling the core:
    // Population distribution of orbital inclinations:
    // - 45% equatorial / accretion belt (inc in [-20 deg, +20 deg])
    // - 40% mid-inclination shells (inc in [-52 deg, +52 deg])
    // - 15% high-inclination / polar halos (inc in [-75 deg, +75 deg])
    float inc;
    float yaw;
    float latSeedNorm = latitudeSeed;
    if (latSeedNorm < 0.45) {
        float u = (latSeedNorm / 0.45) * 2.0 - 1.0;
        inc = u * radians(20.0);
        yaw = u * radians(25.0);
    } else if (latSeedNorm < 0.85) {
        float u = ((latSeedNorm - 0.45) / 0.40) * 2.0 - 1.0;
        inc = u * radians(52.0);
        yaw = ((speedSeed * 2.0 - 1.0) * 0.7 + u * 0.3) * radians(45.0);
    } else {
        float u = ((latSeedNorm - 0.85) / 0.15) * 2.0 - 1.0;
        inc = u * radians(75.0);
        yaw = (speedSeed * 2.0 - 1.0) * radians(65.0);
    }

    // In-plane orbit coordinates:
    // As theta advances, particle moves along a 3D circle in its orbital plane
    float x_p = activeR * sin(theta);
    float z_p = activeR * cos(theta);

    // Rotate by inclination around X-axis:
    float cosInc = cos(inc);
    float sinInc = sin(inc);
    float x_i = x_p;
    float y_i = -z_p * sinInc;
    float z_i =  z_p * cosInc;

    // Rotate by yaw around Y-axis:
    float cosYaw = cos(yaw);
    float sinYaw = sin(yaw);
    vec3 center;
    center.x =  x_i * cosYaw + z_i * sinYaw;
    center.y =  y_i;
    center.z = -x_i * sinYaw + z_i * cosYaw;

    // Perspective pitch tilt (pitch down 16 degrees towards viewer):
    float tiltAngle = radians(16.0);
    float cosT = cos(tiltAngle);
    float sinT = sin(tiltAngle);
    float yTilted = center.y * cosT - center.z * sinT;
    float zTilted = center.y * sinT + center.z * cosT;
    center.y = yTilted;
    // Bound z so particles never come too close to camera at Z=382
    center.z = clamp(zTilted, -280.0, 210.0);

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

    // Normalized depth [0, 1] from deep background (-280) to close foreground (+210)
    float depth01 = clamp((center.z + 280.0) / 490.0, 0.0, 1.0);

    // 4. Dramatic 3D Perspective Depth Scaling (Small Far Away, Big in Front!)
    // Base size distribution:
    float sizeSeed = fract(speedSeed * 43.19 + phaseSeed * 17.83);
    float baseSize;
    if (radiusSeed < 0.20) {
        baseSize = mix(4.0, 6.5, sizeSeed);
    } else if (sizeSeed < 0.65) {
        baseSize = mix(4.5, 7.0, sizeSeed / 0.65);
    } else if (sizeSeed < 0.90) {
        baseSize = mix(7.0, 9.5, (sizeSeed - 0.65) / 0.25);
    } else {
        baseSize = mix(9.5, 12.5, (sizeSeed - 0.90) / 0.10);
    }

    // Depth scaling curve:
    // When combined with camera perspective division (1 / (382 - z)),
    // the total apparent size ratio between far away and front is ~6.5x!
    float depthSizeFactor = mix(0.70, 1.35, pow(depth01, 1.15));
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

    // Twinkle & shimmer
    float twinkle = 0.84 + 0.16 * sin(timeSeconds * mix(1.2, 3.2, speedSeed) + phaseSeed * 47.0);

    // Visibility: distant particles are soft and faint; foreground particles are bright and radiant
    float deployFade = smoothstep(0.15, 0.75, deployment);
    float depthBrightness = mix(0.60, 1.25, depth01);
    float activityBoost = 1.0 + activity * 0.30;

    // Screen edge feathering
    float edgeDist = max(abs(ndc.x), abs(ndc.y));
    float edgeFeather = 1.0 - smoothstep(0.90, 1.02, edgeDist);

    vVisibility = deployFade * depthBrightness * twinkle * activityBoost * edgeFeather * uiReadability;
    vDepth01 = depth01;
    vTwinkle = twinkle;
    vSeed = seed;
    vIsCore = isCore;
    vUv = UV0;
}
