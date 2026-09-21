VARYING vec2 vUv;
VARYING float vTone;
VARYING float vDepth01;
VARYING float vParticleClass;
VARYING float vRegionClass;
VARYING float vBaseVisibility;
VARYING float vUiReadability;
VARYING float vRearOcclusion;

const float TAU = 6.28318530718;

void MAIN()
{
    vec4 seed = INSTANCE_DATA;

    float phaseSeed = seed.x;
    float regionSeed = seed.y;
    float latitudeSeed = seed.z;
    float speedSeed = seed.w;

    // Exact population distribution:
    // 44% inner/core atmosphere
    // 42% workspace atmosphere
    // 14% outer/full-display atmosphere
    float isWorkspace = step(0.44, regionSeed);
    float isOuter = step(0.86, regionSeed);
    float isInner = 1.0 - isWorkspace;
    float workspaceOnly = isWorkspace * (1.0 - isOuter);

    float innerT = clamp(regionSeed / 0.44, 0.0, 1.0);
    float workspaceT = clamp(
        (regionSeed - 0.44) / 0.42,
        0.0,
        1.0
    );
    float outerT = clamp(
        (regionSeed - 0.86) / 0.14,
        0.0,
        1.0
    );

    // One coherent 104-second volumetric orbit.
    // Negative angular direction produces front left-to-right movement and
    // rear right-to-left movement for the camera located on positive Z.
    float globalPeriod = 104.0;
    float regionalSpeed = mix(1.0, 0.92, isOuter);
    float speedMultiplier =
        regionalSpeed * mix(0.96, 1.04, speedSeed);

    float longitudeJitter =
        (fract(speedSeed * 29.17 + phaseSeed * 13.81) - 0.5)
        * radians(8.0);

    float longitude =
        phaseSeed * TAU
        + longitudeJitter
        - (timeSeconds / globalPeriod) * TAU * speedMultiplier;

    float yDirection = clamp(
        latitudeSeed * 2.0 - 1.0,
        -0.98,
        0.98
    );
    float horizontalDirection = sqrt(
        max(0.0, 1.0 - yDirection * yDirection)
    );

    vec3 direction = vec3(
        cos(longitude) * horizontalDirection,
        yDirection,
        sin(longitude) * horizontalDirection
    );

    // Densified envelopes. Most particles remain near the nucleus/workspace,
    // while the final 14% preserve sparse full-display coverage.
    vec3 innerExtent = vec3(
        mix(105.0, 225.0, innerT),
        mix(70.0, 158.0, innerT),
        mix(105.0, 192.0, innerT)
    );

    vec3 workspaceExtent = vec3(
        mix(220.0, 420.0, workspaceT),
        mix(145.0, 285.0, workspaceT),
        mix(165.0, 260.0, workspaceT)
    );

    vec3 outerExtent = vec3(
        mix(420.0, 760.0, outerT),
        mix(270.0, 500.0, outerT),
        mix(205.0, 305.0, outerT)
    );

    vec3 extent =
        innerExtent * isInner
        + workspaceExtent * workspaceOnly
        + outerExtent * isOuter;

    vec3 center = direction * extent;

    // Restrained deterministic irregularity prevents artificial rings.
    center.x +=
        (fract(seed.x * 37.19 + seed.y * 19.83) - 0.5) * 24.0;
    center.y +=
        (fract(seed.y * 43.11 + seed.z * 27.53) - 0.5) * 20.0;
    center.z +=
        (fract(seed.z * 51.77 + seed.w * 33.19) - 0.5) * 22.0;

    // Slow independent organic drift, approximately 280 seconds.
    float driftAngle = timeSeconds * TAU / 280.0;
    center.y += sin(driftAngle + speedSeed * TAU) * 3.8;
    center.x += cos(driftAngle * 0.73 + phaseSeed * TAU) * 2.4;

    float densityBreakup =
        0.90
        + 0.10 * sin(
            phaseSeed * TAU * 3.0
            + (latitudeSeed * 2.0 - 1.0) * 4.0
        );

    float outerFeather = mix(
        1.0,
        mix(0.96, 0.68, outerT),
        isOuter
    );

    // Real 3D layering with restrained size variation.
    float depth01 = clamp(
        (center.z + 320.0) / 640.0,
        0.0,
        1.0
    );

    // Required depth-size range: rear 0.72, front 1.12.
    float depthSize = mix(0.72, 1.12, depth01);
    float depthBrightness = mix(0.70, 1.0, depth01);

    float middleDepth = smoothstep(0.30, 0.60, depth01);
    float frontDepth = smoothstep(0.64, 0.88, depth01);

    // Rear particles behind the nucleus are attenuated, not removed.
    float projectedRadius = length(center.xy);
    float rearMask = center.z < 0.0
        ? 1.0 - smoothstep(78.0, 124.0, projectedRadius)
        : 0.0;
    float rearOcclusion = mix(1.0, 0.14, rearMask);

    // Screen-diameter classes before depth scaling:
    // Fine:   4.0–5.0 px
    // Medium: 5.0–6.2 px
    // Accent: 6.2–7.1 px
    // Absolute result remains below 8 px after 1.12 front scaling.
    float classSeed =
        fract(seed.w * 37.19 + seed.x * 17.83);

    float particleSize;
    float classAlpha;
    float particleClass;

    if (classSeed < 0.72) {
        float classT = classSeed / 0.72;
        particleSize = mix(5.4, 6.2, classT);
        classAlpha = mix(
            mix(0.70, 0.82, classT),
            mix(0.88, 1.0, classT),
            frontDepth
        );
        particleClass = 0.0;
    } else if (classSeed < 0.95) {
        float classT = (classSeed - 0.72) / 0.23;
        particleSize = mix(6.2, 6.8, classT);
        classAlpha = mix(
            mix(0.74, 0.86, classT),
            mix(0.92, 1.0, classT),
            frontDepth
        );
        particleClass = 1.0;
    } else {
        float classT = (classSeed - 0.95) / 0.05;
        particleSize = mix(6.8, 7.14, classT);
        classAlpha = mix(
            mix(0.78, 0.90, classT),
            1.0,
            frontDepth
        );
        particleClass = 2.0;
    }

    particleSize *= depthSize;

    vec4 worldCenter = MODEL_MATRIX * vec4(center, 1.0);
    vec4 viewCenter = VIEW_MATRIX * worldCenter;

    // #Rectangle is approximately 100 world units across. The 0.01 factor
    // converts it to one unit before applying the desired pixel diameter.
    viewCenter.xy +=
        VERTEX.xy
        * particleSize
        * pixelToWorld
        * 0.01;

    POSITION = PROJECTION_MATRIX * viewCenter;

    vec2 ndc = POSITION.xy / max(POSITION.w, 0.0001);
    float edgeDistance = max(abs(ndc.x), abs(ndc.y));
    float screenEdgeFeather =
        1.0 - smoothstep(0.90, 1.02, edgeDistance);

    vec2 screenPos = ndc * 0.5 + 0.5;

    float transitionX = 0.055;
    float leftFactor = smoothstep(
        leftPanelBoundary - transitionX,
        leftPanelBoundary + transitionX,
        screenPos.x
    );
    float leftAttenuation = mix(0.30, 1.0, leftFactor);

    float rightFactor = smoothstep(
        rightPanelBoundary + transitionX,
        rightPanelBoundary - transitionX,
        screenPos.x
    );
    float rightAttenuation = mix(0.30, 1.0, rightFactor);

    float transitionY = 0.05;
    float topThreshold = 1.0 - topNavigationBoundary;
    float topFactor = smoothstep(
        topThreshold + transitionY,
        topThreshold - transitionY,
        screenPos.y
    );
    float topAttenuation = mix(0.28, 1.0, topFactor);

    float bottomFactor = smoothstep(
        bottomResponseBoundary - transitionY,
        bottomResponseBoundary + transitionY,
        screenPos.y
    );
    float bottomAttenuation = mix(0.24, 1.0, bottomFactor);

    float uiReadability = min(
        min(leftAttenuation, rightAttenuation),
        min(topAttenuation, bottomAttenuation)
    );

    float slowTwinkle =
        0.94
        + 0.06 * sin(
            timeSeconds * (0.16 + seed.y * 0.11)
            + seed.x * 31.0
        );

    float deployFade = smoothstep(0.45, 0.85, deployment);
    float activityGain = 0.96 + activity * 0.04;

    float layerVisibility = 1.0;
    if (depthLayerMode == 1) {
        layerVisibility =
            1.0 - smoothstep(0.36, 0.43, depth01);
    } else if (depthLayerMode == 2) {
        layerVisibility =
            smoothstep(0.29, 0.36, depth01)
            * (1.0 - smoothstep(0.68, 0.75, depth01));
    } else if (depthLayerMode == 3) {
        layerVisibility =
            smoothstep(0.62, 0.69, depth01);
    }

    vBaseVisibility =
        outerFeather
        * classAlpha
        * densityBreakup
        * depthBrightness
        * rearOcclusion
        * slowTwinkle
        * deployFade
        * activityGain
        * screenEdgeFeather
        * uiReadability
        * layerVisibility;

    vUv = UV0;
    vTone = classSeed;
    vDepth01 = depth01;
    vParticleClass = particleClass;
    vRegionClass = regionSeed;
    vUiReadability = uiReadability;
    vRearOcclusion = rearOcclusion;
}
