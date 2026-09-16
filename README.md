# E.V. — Enhanced Virtual Intelligence

## Current development handoff - 16 September 2026

Start with [Astra plan](ASTRA_PLAN.md), [current application handoff](ASTRA_HANDOFF.md)
and [next-agent instructions](docs/handoff/ASTRA_NEXT_AGENT_PROMPT.md).
The cinematic interface is now the default (`Launch EV.cmd` or
`.venv\Scripts\python.exe -B -m gui.app`); `--classic` selects the earlier interface.
Music playback, output capture and core beat reactions exist. The new equalizer,
multi-visualizer studio and mobile assistant features are **planned, not implemented**.
See [checkpoint and validation](docs/handoff/ASTRA_CHECKPOINT.md) and
[local backup instructions](astrabackup/README.md).

The original V1 section below records the initial project scope. The user has since
authorized the cinematic interface, voice and Music work; the current Astra roadmap
governs that expanded scope while retaining execution, approval and verification.

Engineering principle:

Execution & Verification

## V1 Goal

Build a safe autonomous Windows troubleshooting engine.

Initial focus:

- PowerShell execution
- Structured command results
- System observation
- Verification
- Backups
- Rollback
- Permissions
- Logging

Do not add browser automation, GUI automation, voice, HUD, YouTube automation,
or unrelated modules until the V1 troubleshooting core is reliable.
