# Copy this into the next coding agent

```text
You are continuing E.V. on Windows at D:\EV. Read ASTRA_HANDOFF.md and ASTRA_PLAN.md
first, then docs/plans/ASTRA_MUSIC_STUDIO_PLAN.md. Do not reconstruct the project
from scratch or assume older “Music soon” documents describe the current state.

Current accepted behavior: cinematic golden core and main interface; startup
“E.V. online”; local Music player and Windows loopback; real onset-driven core
reaction in Music and subtly in Assistant; saved All modes/Music only/Off controls;
restyled dark blue/gold provider settings. Preserve these.

The previous task produced PLANS, not the new EQ/preset implementation. Ask the
user which milestone to execute if they have not authorized implementation yet.
When authorized, start M1: Reference Trio and multiple arranged visualizers.
The reference clip is F:\OneDrive\Videos\NVIDIA\Desktop\Desktop 2026.09.16 - 20.32.34.02.mp4.
It shows downward fine bars, a small segmented upward meter, and a smooth
white/cyan bottom trace simultaneously. The plan records observation limits.

First inspect Git status and the checkpoint record. Preserve unrelated work.
Make a verified source backup. Reproduce the narrow tests and one isolated
rendered check. Implement one milestone at a time and keep the current player
backend until a real owned-PCM DSP path passes. QAudioBufferOutput is an
observation tap, not an audible EQ insertion point. Windows output capture
visualizes the mix but must never be fed back to speakers.

Use one capture/analysis service and shared snapshots for all panels. Keep queues,
FFT requests, geometry and spectrogram history bounded. Preserve source/seek
generation resets, audio/GUI thread boundaries, manual capture stop, silence,
all-modes reaction scaling, voice/task priority and approval overlays.

Do not alter core/tts.py, authority/approval rules, provider secrets or phone
permissions as part of a visualizer milestone. Do not make live network/message
tests using the user's real accounts. Use generated audio and temporary config.

Acceptance for M1: all three reference presets run together, respond to actual
audio, fit at 1100x760 and 1920x1080, persist a validated layout, and use no extra
capture instance per widget. Give actual screenshots, test results and measured
limitations. Do not claim 60 FPS from forced readback tests or hide a failed test.

At completion, update the handoff and milestone table. Report changed files,
tests, backup/hash, risks and launch instructions. Commit/push only when the user
has authorized that task's publication. Never overwrite the only known-good core.
```

For later work, use the same structure with one explicit milestone from `ASTRA_ASSISTANT_FUTURE_PLAN.md`. Read platform restrictions before promising phone/SMS/WhatsApp behavior. Prefer supported APIs and capability contracts over unbounded GUI automation.
