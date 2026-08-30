# 012C5 DIAGNOSIS REPORT

Status: **COMPLETE (two root causes found & fixed; visually verified via frame grab)**
Date: 2026-08-30 (IST)
Investigator: F (Genspark Claw), direct diagnosis after 4 interrupted Claude Code runs

## Problem
Central 3D Intelligence Core (View3D scene in `EVIntelligenceCore.qml`, hosted by
`EVFlagshipStage.qml` inside `EVWindow.qml`) rendered INVISIBLE/BLACK in the real app,
while pytest passed.

## Root cause #2 (found after user re-test still showed no core)
**Layout bug in `EVFlagshipStage.qml`: the main container Row anchored
`anchors.top: ambientField.bottom`.** `ambientField` is a Canvas with
`anchors.fill: parent`, so its BOTTOM equals the stage's bottom — pushing the Row
(and the EVIntelligenceCore inside it) entirely BELOW the visible stage. The core
was rendering fine, just off-screen. Evidence: runtime scene mutation (red clear
color, 5x lights, red emissive on all 8 materials) changed NOTHING in center-screen
pixel samples; object tree showed core 720x720 visible — i.e. rendered but not
composited in view. Fix: `anchors.top: parent.top`. After the fix, frame grab shows
the 3D orb with shading, orbital rings and satellites (confirmed by image analysis;
center max pixel went 30 → 765/765 brightness scale).

## Root cause #1 (fixed first)
**QML syntax error: unbalanced braces in `gui/qml/components/EVIntelligenceCore.qml`.**

A previous (interrupted) agent run appended a debugging `Component.onCompleted { ... }`
block but the file ended without closing the root `Item` — 54 `{` vs 53 `}`.

Because of this, the QML engine failed to load the ENTIRE component chain:

```
Main.qml:6            Type Components.EVWindow unavailable
EVWindow.qml:54       Type EVFlagshipStage unavailable
EVFlagshipStage.qml:205  Type EVIntelligenceCore unavailable
EVIntelligenceCore.qml:1427  Expected token `}`
```

In the real app `engine.rootObjects()` came back empty → nothing (or a black window)
rendered. Tests passed because they exercised components/logic that did not require a
successful load of this file in the same way (and/or predated the broken edit).

The appended debug block itself was also invalid: it referenced ids `core3D` and
`camera` plus `core3D.children[0].materials`, producing a TypeError once braces were
balanced. It was pure leftover instrumentation, not a fix.

## Evidence
- Offscreen run (`QT_QPA_PLATFORM=offscreen`) with `engine.warnings` captured produced
  the four warnings above and `FATAL: no root objects loaded`.
- After the fix, the app loads: object tree shows `EVFlagshipStage` (1248x660, visible)
  → `EVIntelligenceCore` (720x720, visible) → SceneEnvironment, PerspectiveCamera,
  2 DirectionalLights, 2 PointLights, and dozens of QQuick3DModel instances all
  visible with sane transforms.

## Fix (minimal)
Files changed:
1. `gui/qml/components/EVIntelligenceCore.qml` — removed broken leftover
   `Component.onCompleted` debug block; balanced braces (root cause #1).
2. `gui/qml/components/EVFlagshipStage.qml` — mainContainer Row:
   `anchors.top: ambientField.bottom` → `anchors.top: parent.top` (root cause #2).

No other project files were modified. No `.bak` / `.pre-*` backups touched.

## Follow-up: horizontal centering (user-reported, resolved)
After fix #2 the core appeared LEFT of center with excess space on the right.
Analysis of `EVFlagshipStage.qml` composition: mainContainer is a Row of
[leftRail 72px][core][rightRail 72px]. The core's width was hard-coded
`parent.width * 0.6`, which does NOT consume the remaining Row space —
leaving the leftover width dangling after the right rail, i.e. dead space on
the right. This was an unintended layout consequence, NOT a reserved HUD area:
the design already dedicates symmetric left/right rails (task rail + telemetry
rail) as the flanking UI; no other component anchors into that leftover gap.

Minimal correction (no eye-balled offsets):
`EVIntelligenceCore` width = `parent.width - leftRail.width - rightRail.width -
2*parent.spacing`, height = `parent.height` — the core now exactly fills the
space between the rails, making the composition symmetric by construction.
(EVIntelligenceCore's internal View3D self-sizes via min(width,height)*0.64 and
anchors.centerIn, so non-square bounds are safe.)

Verification: frame grab + image analysis — "orb is almost perfectly
horizontally centered ... offset 0-10 px (negligible)". Tests unchanged:
250 passed, 1 unrelated env failure.

## Test results
`D:\EV\.venv\Scripts\python.exe -m pytest tests -q`

**250 passed, 6 subtests passed, 1 failed** — the single failure is
`tests/test_processes_network.py::test_process_list`, which failed with
`[WinError 2]` spawning `powershell.exe`: an artifact of the sandboxed shell
environment (PowerShell not on PATH for the child process), NOT related to this fix.
Re-run in a normal shell to confirm it passes there.

Note: scratch files `test_msaa.py`, `test_qml2.py`, `test_view3d.py` in the repo ROOT
(from earlier agent runs) and duplicated tests under `handoff/012A_INSPECTION/` break
bare `pytest` collection — run `pytest tests` or clean these up in a later task.

## Remaining follow-ups
- Visual confirmation on-screen (run `python -m gui.app --demo-states` on the desktop).
- Optional cleanup task: remove root-level scratch tests + prune `.bak`/`.pre-*` jungle
  after committing a checkpoint.
- Known separate issue: Qt teardown exception 0x8001010d in tests (pre-existing,
  cosmetic, not addressed here).
