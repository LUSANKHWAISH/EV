E.V. R11Q-D2.3 — ORBITAL PRESENCE POLISH

BASE
----
Exact R11Q-D2.2:
39073 bytes
SHA-256:
f01f304468df9df18918fa3910004d0b395c54ff563cc813addb6bc1e13e9b04

GOAL
----
Make the six satellite nodes visually identifiable from the existing 24
micro-particles without changing the accepted orbital concept.

SURGICAL CHANGES
----------------
1. Satellite node base size:
   0.028 -> 0.039 (about +39%)

2. Satellite node variation:
   0.005 -> 0.007

3. Satellite LISTENING size response:
   0.003 -> 0.004

4. Satellite emission:
   0.30 + tone*1.22
   ->
   0.36 + tone*1.46

5. Existing 24 micro-particle emission:
   tone*1.38
   ->
   tone*1.13
   (about -18%)

6. Rear orbit path width:
   max(0.7, r*0.0045)
   ->
   max(0.9, r*0.0058)

7. Rear path opacity multipliers:
   0.45 -> 0.72
   0.34 -> 0.54
   0.28 -> 0.45

8. Front tracer width:
   max(1.0, r*0.007)
   ->
   max(1.1, r*0.008)

9. Front tracer arc lengths:
   0.58 -> 0.72
   0.46 -> 0.58
   0.38 -> 0.48

10. Front tracer opacity multipliers:
    0.92 -> 1.20
    0.72 -> 0.94
    0.58 -> 0.75

NO TOPOLOGY / CAMERA / SPEED / ORBIT-RADIUS CHANGES.
