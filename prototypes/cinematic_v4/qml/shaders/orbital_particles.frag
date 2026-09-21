VARYING vec2 vUv;
VARYING float vTone;
VARYING float vDepth01;
VARYING float vParticleClass;
VARYING float vRegionClass;
VARYING float vBaseVisibility;
VARYING float vUiReadability;
VARYING float vRearOcclusion;

void MAIN()
{
    vec2 point = vUv * 2.0 - 1.0;
    float radiusSquared = dot(point, point);
    float radius = sqrt(radiusSquared);

    // Defined luminous center rather than a large fuzzy Gaussian.
    float pinPoint =
        1.0 - smoothstep(0.025, 0.21, radius);

    float compactCoreExponent = mix(
        12.0,
        20.0,
        vDepth01
    );
    float compactCore =
        exp(-radiusSquared * compactCoreExponent);

    // Rear particles retain slight atmospheric softness. Front particles use
    // a tighter halo. Halo contribution remains within 0.04–0.06.
    float haloExponent = mix(3.2, 5.2, vDepth01);
    float haloWeight = mix(0.06, 0.04, vDepth01);
    float restrainedHalo =
        exp(-radiusSquared * haloExponent) * haloWeight;

    float edgeCut =
        1.0 - smoothstep(0.72, 0.98, radius);

    float particleShape =
        (pinPoint * 0.72 + compactCore * 0.88 + restrainedHalo)
        * edgeCut;

    // Approved fire palette only—no white, grey or green.
    vec3 deepEmber       = vec3(0.5608, 0.2314, 0.0392); // #8F3B0A
    vec3 burntOrange     = vec3(0.7843, 0.3529, 0.0706); // #C85A12
    vec3 fireOrange      = vec3(0.9412, 0.4706, 0.0941); // #F07818
    vec3 moltenAmber     = vec3(0.9608, 0.6510, 0.1373); // #F5A623
    vec3 goldenHighlight = vec3(1.0000, 0.7686, 0.3529); // #FFC45A

    // Tone distribution:
    // 30% burnt orange
    // 35% fire orange
    // 28% molten amber
    // 7% golden highlight
    vec3 toneColor;
    if (vTone < 0.30) {
        toneColor = burntOrange;
    } else if (vTone < 0.65) {
        toneColor = fireOrange;
    } else if (vTone < 0.93) {
        toneColor = moltenAmber;
    } else {
        toneColor = goldenHighlight;
    }

    // Rear particles transition toward deep ember. Middle particles are clear
    // orange/amber; front particles remain sharp molten fire-gold.
    float rearBlend =
        1.0 - smoothstep(0.20, 0.54, vDepth01);
    vec3 colour = mix(
        toneColor,
        deepEmber,
        rearBlend * 0.56
    );

    float middleDepth =
        smoothstep(0.30, 0.60, vDepth01);
    float frontDepth =
        smoothstep(0.64, 0.88, vDepth01);

    float depthIntensity =
        mix(0.66, 0.92, middleDepth);
    depthIntensity =
        mix(depthIntensity, 1.08, frontDepth);

    vec3 finalColor =
        colour * depthIntensity * gain;

    float alpha = clamp(
        particleShape
        * vBaseVisibility
        * coverage,
        0.0,
        0.95
    );

    FRAGCOLOR = vec4(finalColor, alpha);
}
