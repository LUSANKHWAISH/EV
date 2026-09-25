R11C1 — COPILOT ORB CANDIDATE

This intentionally implements only the user-supplied Copilot idea:
- one dark metallic sphere
- cyan emission
- one directional light
- one cyan point light
- perspective camera

Only Qt Quick 3D compatibility was corrected:
- QtQuick3D 1.15 -> QtQuick3D
- emissiveColor/emissiveIntensity -> emissiveFactor
- light intensity -> brightness
- Environment -> SceneEnvironment
- camera lookAt omitted because the centered +Z camera already faces the origin
- sample world coordinates 3/2 converted to practical 300/200 units

No extra visual system was added.
