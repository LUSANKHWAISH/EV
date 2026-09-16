# ASTRA PLAN — E.V. continuation map

Version: 16 September 2026, evening checkpoint. Owner: Lusan. Scope of this delivery: **planning, handoff, backup and Git checkpoint only**. The next equalizer, visualizer gallery, phone companion and service connectors are not implemented by this task.

## Read in this order

1. [ASTRA_HANDOFF.md](ASTRA_HANDOFF.md): current implementation, launch, source map, guardrails and verification.
2. [Music studio implementation plan](docs/plans/ASTRA_MUSIC_STUDIO_PLAN.md): the immediate next build; includes audio architecture, multi-panel layouts, DSP examples, preset specifications and acceptance gates.
3. [Full assistant roadmap](docs/plans/ASTRA_ASSISTANT_FUTURE_PLAN.md): the path from the current Windows assistant to useful desktop, account and phone workflows.
4. [Next-agent prompt](docs/handoff/ASTRA_NEXT_AGENT_PROMPT.md): copy this into the next coding agent.
5. [Checkpoint record](docs/handoff/ASTRA_CHECKPOINT.md): what was packaged, verified and pushed. Local restore material is under `astrabackup/`.

The older September 16 plans/reports remain historical evidence. Their statements such as “Music not started” or “Music soon” describe an earlier point in the day. This plan and the handoff supersede those status statements. The original README's V1-only scope predates the user's explicitly approved cinematic interface, Music and assistant expansion.

## Product destination

E.V. is a practical personal assistant with a cinematic interface, not just an animated core. It should understand a request, identify the correct device/account/app, propose or execute supported steps within granted authority, show progress, verify the result and explain failures. Its golden nucleus communicates state, speech and music without obscuring controls or misleading the user about completion.

The user wants a full music environment: local and supported cloud music, real playback EQ, multiple arranged visualizers, SPAN-style analysis, Fruity Parametric EQ-inspired interaction, Wave Candy-style instruments and the three visual behaviors in the supplied desktop video. “Inspired by” means original E.V. implementations, not bundled FL Studio/Voxengo plugins, copied artwork or a claim of plugin compatibility.

## Delivery sequence

| Order | Milestone | Definition of done |
|---|---|---|
| 0 | Reproduce checkpoint | Fresh checkout launches; narrow unit set and isolated UI tests pass; source/asset hashes are recorded. |
| 1 | Reference Trio + multi-panel workspace | Three requested visualizers run together from one real analysis stream; layouts persist and fit 1100×760; accepted core and existing playback remain intact. |
| 2 | Studio instruments | Log-spectrum/peak hold, oscilloscope, spectrogram, stereo scope and meters are calibrated against fixtures; choose up to four visible instruments on this PC. |
| 3 | Real player EQ | Processing-capable playback backend proven; 10-band EQ and preamp audibly alter owned PCM; bypass, seek, device loss and silent input behave correctly. |
| 4 | Parametric EQ | Seven editable bands, useful frequency/Q/gain controls, summed response graph and pre/post analysis; no audible clicks when parameters change. |
| 5 | Complete local player | Persistent library, tags/artwork, queue editing, playlists, shuffle/repeat, media keys, gapless/crossfade only after audio tests. |
| 6 | Supported cloud sources | Direct streams + one personal-library provider first; commercial services are capability/policy-specific adapters. |
| 7 | Assistant usefulness | Capability registry, reliable read-only desktop/account tasks, structured plans and verified actions. |
| 8 | Android companion | Paired device identity, selected notification access, media commands and tightly scoped actions; offline/locked-device handling. |
| 9 | Mail and messaging | Account-specific read/search/draft/send and supported notification replies; preview/authorization/idempotency/verification. |
| 10 | Cinematic polish and release | Settings consolidation, accessibility, voice coexistence, performance tiers, installer, diagnostics, recovery and update path. |

Milestones can be split into small pull requests. Do not implement all of them in one uncontrolled rewrite. First next-agent task: **M1, Reference Trio and a deterministic multi-panel layout**, keeping the existing playback backend. M3's audio proof can be planned independently but must pass before a working EQ is advertised.

## Model recommendation and spending strategy

**Primary coding model: GPT-5.6 Sol (`gpt-5.6-sol`). It is a suitable continuation model for the difficult Qt, audio and integration work. Use GPT-5.6 Terra for bounded routine changes; reserve Astra for particularly difficult architectural reviews if budget permits.** A capable model with filesystem, terminal, Git and rendered-UI access is more useful here than a text-only chat that cannot run E.V.

Official model guidance read on September 16: [OpenAI model guidance](https://learn.chatgpt.com/docs/models). It describes Sol for complex work, Terra as the pragmatic everyday option and Astra for the hardest end-to-end workflows. This is a recommendation, not a guarantee of defect-free code or an assertion that these names are available through the user's Azure deployment. Check the next provider/account's actual catalog and cost before choosing. No cross-vendor ranking or exact price claim was established in this handoff.

Budget practice: give the agent one milestone and this handoff; require a small diff, meaningful tests, screenshots and a checkpoint. Use moderate effort for ordinary changes and higher effort for DSP/threading/security. Do not pay repeatedly for reconstructing the whole conversation. Keep an up-to-date completion table in the handoff, rather than resending large videos and every historic report on each turn.

## Non-negotiable continuity

- Preserve the accepted sharp fire-gold core. No elastic globe, blurred orange ball, uncontrolled tumbling or random scribble replacement.
- Keep one canonical GuiBridge/state/approval/execution path. New panels consume state; they do not create a second assistant authority system.
- Music is real audio-driven. No synthetic sine-wave “beats” in production. Synthetic fixtures are labelled test data.
- Analysis of Windows output does not itself provide system-wide EQ or the identity of the playing song.
- A strong model alone cannot unlock an arbitrary phone, bypass an app's access rules or control every service. Build explicit supported connectors, with useful alternatives when a capability is unavailable.
- No live emails/messages, real account mutation, real provider switching or desktop audio rerouting during development tests. Use isolated fixtures and mocked service transport unless the user requests a concrete live test.
- `core/tts.py` PCM playback changes remain a separate explicitly approved task; prior visual/music authorization did not authorize that rewrite.

## Questions for later implementation, not blockers for this handoff

Phone OS/version and whether a companion app can be installed; Gmail versus Outlook accounts; personal versus business WhatsApp; first cloud music provider; preferred default three-panel arrangement; exact subscription/tool budget for the next coding agent. The roadmap assumes Windows 10 desktop and Android-first companion work, with iOS limitations documented separately.

## Estimates

Use acceptance gates, not an overnight completion promise. Reference Trio/layout: approximately 2–4 focused engineering days; calibrated studio instruments: 3–6; real audio backend/EQ: 5–10; complete local library/queue polish: 4–8. Provider adapters and phone integration each require additional weeks of testing, permissions and device-specific work. These are planning ranges, not measured delivery commitments; a model may generate code quickly while listening, device and regression testing still take time.
