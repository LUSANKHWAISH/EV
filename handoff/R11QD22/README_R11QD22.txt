E.V. R11Q-D2.2 — ORBITAL TRACERS + SATELLITE NODES

BASELINE
--------
Exact R11Q-D2 Flagship Depth:
28958 bytes
SHA-256:
d1efd95f239dfb5bbb72710238db226923ee452e36b885ec4af92b5be1dc7c2d

PURPOSE
-------
Keep the approved R11Q-D2 core unchanged and add the moving elements requested
by the user around the core.

TERMINOLOGY
-----------
Satellite Nodes:
Larger glowing spheres orbiting the central core.

Orbital Tracers:
Thin elliptical paths / short moving light segments that visually describe
their trajectories.

ADDED
-----
- 6 real Repeater3D satellite spheres
- 3 orbit planes
- true Z movement so nodes cross foreground/background
- 3 faint complete orbit paths behind the core
- 3 moving short tracer arcs in front of the core
- state-aware speed
- state-aware opacity
- LISTENING slightly enlarges the satellite nodes
- AWAITING_APPROVAL nearly freezes the orbital layer

NOT CHANGED
-----------
- R11Q-D2 central orb topology
- R11Q-D2 camera
- R11Q-D2 lighting
- R11Q-D2 depth stack
- existing 24 micro-particle field
- public E.V. contract
- Theme integration
- surrounding UI

DESIGN LIMIT
------------
This is intentionally restrained. It must not become a noisy atom animation.
