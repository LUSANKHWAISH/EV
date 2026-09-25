E.V. R11B — DENSE MACHINE REVISION
=================================

This is a STATIC-ASSET APPROVAL forge only.

It does NOT modify the live E.V. GUI.

R11B fixes the rejected R11 model by changing the sculpture itself:

- no giant flat white center
- no giant smooth HUD rings
- asymmetric octagonal manufactured outer frame
- integrated flux cartridges rather than floating boxes
- visible dark-copper coil packs
- deep rear stator/cage
- multi-layer smoked-glass energy chamber
- dark cognition nucleus
- small segmented energy emitters only
- more breathing room in approval renders

RUN
---

Recommended direct command:

& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" `
    --background `
    --python "D:\EV\handoff\R11B_FORGE\BUILD_R11B_DENSE_MACHINE.py"

Or:

powershell -ExecutionPolicy Bypass -File "D:\EV\handoff\R11B_FORGE\RUN_R11B_FORGE.ps1"

OUTPUT
------

output\
    R11B_VECTOR_REACTOR_SOURCE.blend
    R11B_BUILD_REPORT.txt
    assets\
    renders\
        R11B_FRONT.png
        R11B_PRIMARY_3Q.png
        R11B_OPPOSITE_3Q.png
        R11B_SIDE_DEPTH.png
        R11B_DARK_ENERGY.png

UPLOAD THE FIVE PNGs TO CHATGPT BEFORE ANY E.V. INTEGRATION.
