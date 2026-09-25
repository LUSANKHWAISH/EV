VARYING vec2 vUv;
VARYING float vDepth01;
VARYING float vTwinkle;
VARYING vec4 vSeed;
VARYING float vVisibility;
VARYING float vIsCore;

void MAIN()
{
    vec2 point = vUv * 2.0 - 1.0;
    float radiusSquared = dot(point, point);
    float radius = sqrt(radiusSquared);

    if (radius > 1.0) {
        discard;
    }

    // Depth-Dependent Volumetric Point Spread Function:
    // Background (depth01 -> 0): Tight pinpoint star with minimal halo (sharp, tiny)
    // Foreground (depth01 -> 1): Luminous bokeh orb with soft silky exponential halo (big, radiant)
    float coreExponent = mix(32.0, 16.0, vDepth01);
    float core = exp(-radiusSquared * coreExponent);

    float haloExponent = mix(6.0, 3.0, vDepth01);
    float haloWeight = mix(0.12, 0.42, vDepth01);
    float halo = exp(-radiusSquared * haloExponent) * haloWeight;

    float edgeCut = 1.0 - smoothstep(0.70, 0.98, radius);
    float particleProfile = (core * 0.90 + halo) * edgeCut;

    // Color Palette Selection
    // Theme 0: Celestial Cyan / Supernova Blue (exact aesthetic from Video-20807.mp4)
    // Theme 1: Solar Gold / Amber (native E.V. signature aesthetic)
    // Theme 2: Hybrid Nebula (deep sapphire backdrop with gold inner stellar swirl)
    vec3 color;

    // Theme 0: Celestial Cyan / Blue
    vec3 celestialDeep    = vec3(0.06, 0.24, 0.52); // Deep sapphire
    vec3 celestialMid     = vec3(0.14, 0.70, 1.00); // Electric cyan
    vec3 celestialHigh    = vec3(0.78, 0.94, 1.00); // Diamond cyan-white

    // Theme 1: Solar Gold / Amber
    vec3 solarDeep        = vec3(0.55, 0.22, 0.04); // Deep ember
    vec3 solarMid         = vec3(0.96, 0.62, 0.12); // Molten amber
    vec3 solarHigh        = vec3(1.00, 0.88, 0.58); // Radiant gold-white

    float toneSeed = fract(vSeed.w * 31.17 + vSeed.x * 19.43);

    if (colorTheme == 0) {
        // Celestial Cyan / Blue (Video-20807 style)
        vec3 tone = mix(celestialDeep, celestialMid, smoothstep(0.15, 0.75, toneSeed));
        color = mix(tone, celestialHigh, smoothstep(0.50, 0.95, vDepth01) * 0.75);
    } else if (colorTheme == 1) {
        // Solar Gold / Amber
        vec3 tone = mix(solarDeep, solarMid, smoothstep(0.15, 0.75, toneSeed));
        color = mix(tone, solarHigh, smoothstep(0.50, 0.95, vDepth01) * 0.75);
    } else {
        // Hybrid Nebula: Outer/rear stars are cosmic blue, inner/front stars are warm gold
        vec3 outerColor = mix(celestialDeep, celestialMid, toneSeed);
        vec3 innerColor = mix(solarMid, solarHigh, toneSeed);
        float hybridMix = smoothstep(0.25, 0.75, vDepth01);
        color = mix(outerColor, innerColor, hybridMix);
    }

    // Boost core plasma luminescence for particles inside the core volume
    if (vIsCore > 0.0) {
        vec3 coreHot = colorTheme == 0 ? vec3(0.85, 0.95, 1.0) : vec3(1.0, 0.94, 0.82);
        color = mix(color, coreHot, vIsCore * 0.40);
    }

    // Depth-weighted luminous intensity (distant faint, foreground bright)
    float depthGlow = mix(0.60, 1.30, vDepth01);
    vec3 finalColor = color * depthGlow * gain;

    float alpha = clamp(
        particleProfile * vVisibility * coverage,
        0.0,
        1.0
    );

    FRAGCOLOR = vec4(finalColor, alpha);
}
