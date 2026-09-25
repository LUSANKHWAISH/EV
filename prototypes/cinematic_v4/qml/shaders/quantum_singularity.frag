VARYING vec2 vUv;
VARYING float vDoppler;
VARYING float vType;
VARYING float vDepth01;
VARYING float vTwinkle;
VARYING float vVisibility;

void MAIN()
{
    // Centered coordinates in [-1, 1]
    vec2 p = vUv * 2.0 - 1.0;
    float r = length(p);

    if (r > 1.0) {
        discard;
    }

    // 1. Dual-lobe Radial Profile:
    // Core: tight diamond/Gaussian center
    float core = exp(-r * r * 22.0);
    // Halo: smooth exponential falloff with soft zero-edge boundary
    float halo = exp(-r * 3.8) * (1.0 - smoothstep(0.70, 1.0, r));

    // 2. Relativistic Doppler Color Palette:
    // Inspiration: Interstellar (Gargantua) & Relativistic Astrophysics
    // Palette: Obsidian void, blinding white photon ring, electric violet & fiery amber.
    vec3 col = vec3(1.0);

    if (vType < 0.5) {
        // --- ACCRETION DISK (Doppler Beaming) ---
        // Fiery amber base plasma:
        vec3 amberDeep = vec3(0.70, 0.18, 0.04);  // deep fiery ember
        vec3 amberMid  = vec3(1.00, 0.55, 0.08);  // molten solar amber
        vec3 amberGlow = vec3(1.00, 0.82, 0.40);  // radiant amber-gold

        // Doppler blueshifted approaching plasma:
        vec3 cyanDeep  = vec3(0.08, 0.42, 0.85);  // electric sapphire
        vec3 cyanMid   = vec3(0.12, 0.75, 1.00);  // electric cyan
        vec3 cyanHot   = vec3(0.88, 0.96, 1.00);  // relativistic blue-white

        // Doppler redshifted receding plasma:
        vec3 redDeep   = vec3(0.52, 0.06, 0.38);  // deep infrared violet
        vec3 redMid    = vec3(0.95, 0.28, 0.05);  // fiery redshifted ember

        if (vDoppler > 0.52) {
            // Blueshift (approaching viewer): shifts from amber-gold to electric cyan / white-hot
            float t = (vDoppler - 0.52) / 0.48;
            col = mix(amberGlow, mix(cyanMid, cyanHot, t), pow(t, 0.8));
        } else {
            // Redshift (receding into background): shifts from amber to deep fiery red / infrared violet
            float t = (0.52 - vDoppler) / 0.52;
            col = mix(amberMid, mix(redMid, redDeep, t), pow(t, 0.85));
        }

        // Diamond white-hot core at the particle center with saturated plasma halo
        col = mix(col, vec3(1.0, 1.0, 1.0), core * 0.65);

    } else if (vType < 1.5) {
        // --- BIPOLAR RELATIVISTIC JETS (+/- Y POLES) ---
        // High-energy electric violet plasma beam with neon-cyan core
        vec3 jetViolet = vec3(0.72, 0.18, 1.00); // deep electric violet
        vec3 jetCyan   = vec3(0.25, 0.85, 1.00); // plasma cyan
        vec3 jetCore   = vec3(0.92, 0.96, 1.00); // white-hot diamond center
        vec3 jetCol    = mix(jetViolet, jetCyan, halo * 0.5);
        col = mix(jetCol, jetCore, core * 0.85);

    } else {
        // --- PHOTON RING ---
        // Blinding white-gold relativistic flare framing the event horizon
        vec3 ringAmber = vec3(1.00, 0.65, 0.15); // golden-amber corona
        vec3 ringWhite = vec3(1.00, 0.98, 0.92); // blinding white photon ring
        col = mix(ringAmber, ringWhite, core * 0.90);
    }

    // Combine core brilliance and luminous atmospheric halo
    float intensity = (core * 1.50 + halo * 0.85) * vVisibility;
    intensity = clamp(intensity, 0.0, 1.0);

    if (intensity < 0.005) {
        discard;
    }

    // Additive output with relativistic luminescence
    vec3 finalRgb = col * intensity * 1.40;
    FRAGCOLOR = vec4(finalRgb, intensity);
}


