# E.V. Intelligence Core - WebGL Prototype

## Purpose
This is a standalone WebGL prototype for the new visual engine of the E.V. Intelligence Core. The goal is to validate the design, animation, state responses, and performance of a 3D spiral galaxy concept before porting it to the production QtQuick3D PySide6 application.

**IMPORTANT:** This prototype is completely isolated and is NOT connected to the production E.V. runtime, voice pipelines, or core backend.

## How to Run
1. Open `index.html` in any modern web browser (e.g., Chrome, Edge, Firefox).
2. Note: Because it relies on a CDN for Three.js, you need an active internet connection to load the library.

## Architecture
- **HTML/CSS:** Fullscreen, black background canvas container with no scrollbars.
- **JavaScript (Vanilla):** Implements the Three.js scene, camera, renderer, geometry, materials, and animation loop.
- **Three.js:** Utilized for WebGL abstraction. The main galaxy uses `THREE.BufferGeometry` and `THREE.Points` combined with a custom `THREE.ShaderMaterial` for optimal rendering of large particle counts.

## Particle Generation Mathematics
The `generateGalaxy()` function creates 50,000 particles (by default) arranged in spiral arms around a denser central core.
- **Radial Distribution:** Particles are placed at a `radius` with a density bias (`coreDensity`) towards the center.
- **Spiral Arms:** A `spinAngle` (proportional to radius) and a `branchAngle` (dividing the circle into `N` arms) dictate the core spiral shape.
- **Scatter:** Randomness tapering is applied based on the radius (outer particles spread less vertically but more horizontally) using `Math.pow(Math.random(), randomnessPower)`.
- **Distance-based Coloring:** Colors interpolate from white at the center, to cyan, electric blue, violet, and finally deep blue at the edges using `THREE.Color.lerpColors()`.

## Configuration Parameters
The `CONFIG` object at the top of `main.js` controls the visual generation:
- `particleCount`: Total number of galaxy points (Default: 50,000).
- `galaxyRadius`: Outer extent of the spiral.
- `arms`: Number of main spiral arms.
- `spin`: Tightness of the spiral curve.
- `randomness` / `verticalSpread`: Scatter and height variation.
- `coreRadius` / `coreDensity`: Control the size and density of the central nucleus.

## State API
The `EVCore.setState({ state: '...', energy: 0.x })` function provides the interface for state transitions.
It interpolates global uniforms (`targetEnergy`, `targetColorShift`, `targetRotationSpeed`) to smoothly animate the visual state without abrupt jumps.

## State Keyboard Controls
Press the following keys in the browser to preview states:
- `1` : IDLE
- `2` : LISTENING
- `3` : THINKING
- `4` : PLANNING
- `5` : APPROVAL
- `6` : EXECUTING
- `7` : VERIFYING
- `8` : SPEAKING
- `9` : SUCCESS
- `0` : FAILED
- `S` : SLEEP

## Performance Notes
- Uses a single `THREE.BufferGeometry` and custom `ShaderMaterial` for all 50,000 main particles.
- Points are rendered as soft circles natively in the fragment shader by calculating the fragment's distance to the point coordinate (`gl_PointCoord`). This is vastly more performant than generating 50,000 individual textured sprite meshes.
- Avoids per-frame allocations; all position and color data is sent to the GPU once during initialization.
- Uses `window.devicePixelRatio` capped at `2.0` to avoid overdrawing on ultra-high-density displays.

## Production Translation (QtQuick3D)
To map this to production:
- The `BufferGeometry` particle system maps directly to QtQuick3D's `CustomGeometry` or `ParticleSystem3D`.
- The `ShaderMaterial` translates cleanly to a QtQuick3D `CustomMaterial`.
- The state interpolation (`targetEnergy` lerping) can be implemented via QML `Behavior on` animations or a dedicated `FrameAnimation` component in QML.

