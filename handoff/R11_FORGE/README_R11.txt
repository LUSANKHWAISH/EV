E.V. R11 VECTOR REACTOR — FORGE PACKAGE
=======================================

PURPOSE
-------
This package builds the R11 core in Blender OUTSIDE the live E.V. GUI.

It creates:
- R11_VECTOR_REACTOR_SOURCE.blend
- 8 authored GLB groups
- 5 static approval renders
- R11_BUILD_REPORT.txt

It does NOT modify D:\EV\gui.

WHY
---
R4–R10 repeatedly integrated weak geometry before static visual approval.
R11 reverses that process:

MODEL -> RENDER -> APPROVE -> ONLY THEN INTEGRATE

WINDOWS STEPS
-------------
1. Extract this package to:

   D:\EV\handoff\R11_FORGE\

2. Check whether Blender is installed:

   where.exe blender

3. If Blender is not installed:

   winget install -e --id BlenderFoundation.Blender

4. Run:

   D:\EV\handoff\R11_FORGE\RUN_R11_FORGE.ps1

5. Wait for Blender to finish.

6. Upload these five files to ChatGPT:

   output\renders\R11_FRONT.png
   output\renders\R11_PRIMARY_3Q.png
   output\renders\R11_OPPOSITE_3Q.png
   output\renders\R11_SIDE_DEPTH.png
   output\renders\R11_DARK_ENERGY.png

7. Also upload:

   output\R11_BUILD_REPORT.txt

DO NOT COPY ANY R11 GLB INTO D:\EV\gui YET.

The five renders must be visually approved first.
