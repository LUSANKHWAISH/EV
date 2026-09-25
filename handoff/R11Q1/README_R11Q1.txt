E.V. R11Q.1 — TRUE DEPTH ENGINE

WHY R11Q LOOKED FLAT
--------------------
The runtime recording showed that the focal core was visually dominated by
2D Canvas:
- radial aura
- circular ripples
- orbital particles
- full glass-face overlay

The actual View3D sphere underneath had too little visible structural depth.
The camera was essentially frontal and the visible pieces had little Z
separation.

WHAT R11Q.1 CHANGES
-------------------
Canvas is now background-only.

Visible structure is true Qt Quick 3D:
- rear stator plane around Z -72
- mid cognition plane around Z -24
- central energy volumes around Z +4 / +22 / +44
- front containment plane around Z +58
- 20 real 3D particles spanning roughly Z -62 .. +62
- permanent shallow 3/4 core rotation
- independent plane counter-rotation
- executing pushes the front plane toward the camera
- verifying moves the mid plane through depth
- failure desynchronises rear depth
- listening expands the front/mid radii
- speaking drives the central energy volume

No GLB files are needed.
