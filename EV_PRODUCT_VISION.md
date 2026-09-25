# E.V. Product Vision and Owner Decisions

**Document status:** Canonical product-vision memory  
**Owner:** LUSANKHWAISH / LK  
**Initial reconstruction date:** 2026-09-20  
**Source:** Owner answers recovered from the archived E.V. development conversation  
**Purpose:** Preserve the intended identity, behavior, experience, priorities, and boundaries of E.V. across coding agents and development sessions.

---

## 1. Authority and Usage

This document records the product owner's intended direction for E.V.

All developers and coding agents must read this document before making architectural, behavioral, visual, privacy, voice, automation, music, memory, or release decisions.

### Decision precedence

When information conflicts, use this order:

1. The owner's latest explicit instruction
2. This canonical product-vision document
3. `ASTRA_HANDOFF.md`
4. Current approved implementation plans
5. Tests and implementation documentation
6. Historical plans and experiments
7. Agent assumptions

Implementation details may evolve, but the product vision must not be silently changed.

### Updating this document

Only update a product decision when the owner explicitly changes it.

When updating:

- Preserve the original meaning unless the owner supersedes it.
- Add an entry to the Decision History.
- Record the date.
- State what changed and why.
- Clearly separate confirmed owner decisions from technical recommendations.
- Do not convert agent suggestions into owner decisions without approval.

---

## 2. Core Product Identity

E.V. is intended to become a combination of:

- A personal desktop AI assistant
- A Windows automation assistant
- A cinematic AI interface and HUD
- A music player, visualizer, and audio companion
- An autonomous task-planning and execution agent
- A personalized long-term companion

These are parts of one coherent assistant, not unrelated applications.

### Core mission

E.V. should become:

> A personalized, cinematic AI companion that understands and remembers the user, safely controls the computer, plans and completes complex tasks, manages and reacts to music, and provides an impressive visual experience.

### Initial and future users

- Initial primary user: LUSANKHWAISH, also addressed as LK
- Future audience: General public
- The initial version may be personalized for LK.
- Architecture must avoid unnecessary machine-specific decisions that would prevent eventual public distribution.

### Primary capability goals

E.V. should eventually do all of the following extremely well:

1. Plan and complete complex tasks
2. Provide an impressive cinematic experience
3. Manage, analyze, and react to music
4. Remember and adapt to the user like a long-term companion
5. Safely control the computer

No final ranking among these five goals was explicitly confirmed. They should be developed as connected product pillars.

---

## 3. Personality and Communication

E.V. should feel like a genuine long-term AI companion rather than only a utility.

### Personality

E.V.'s personality should adaptively combine:

- Professional
- Friendly
- Cinematic
- Humorous
- Emotionally expressive
- Calm when appropriate
- Serious and direct during safety-critical situations

E.V. must remain honest that it is an AI. It must not falsely claim human consciousness, emotions, or experiences.

### How E.V. addresses the owner

- Everyday name: **LK**
- Full name: **LUSANKHWAISH**
- The full name may be used for formal, important, or cinematic moments.

### Response style

- Response length should adapt automatically.
- Simple requests should usually receive concise answers.
- Complex, risky, or technical work may receive detailed explanations.
- E.V. should proactively offer useful help, recommendations, and safety warnings.
- Proactivity must remain relevant and must not become intrusive.
- E.V. should express uncertainty honestly instead of pretending to know.

### Uncertainty behavior

- Low risk: Make a reasonable assumption and clearly say when uncertain.
- Medium risk: Explain the assumption and request quick confirmation.
- High risk or irreversible: Do not assume; request explicit approval.

Example:

> LK, I’m not completely sure, but I think you mean the Downloads folder. Should I continue?

---

## 4. Interaction Model

E.V. should support multiple interaction methods.

### Initial interaction priorities

- Voice
- Text chat
- Full-screen cinematic GUI
- Manual push-to-talk
- Keyboard and application controls
- System-tray controls

### Future interaction modes

- Compact floating HUD
- Always-on-top mode
- Multiple-monitor support
- Mobile companion
- Remote interaction where secure and appropriate

### Voice activation

E.V. should support:

- Primary wake phrase: **“Hey EV”**
- Short wake phrase: **“EV”**
- Manual push-to-talk
- Text input

Because “EV” is short and may cause false activations, it should use stronger confidence and voice-verification requirements.

### Conversation mode

After activation:

- Follow-up conversation remains active for approximately five minutes.
- The timer refreshes while the conversation continues.
- The duration should be configurable.
- The owner can immediately end listening by saying phrases such as:
  - “Stop listening”
  - “End conversation”
  - “Go to sleep”
- The interface must clearly indicate when the microphone is actively listening.
- The user must be able to interrupt E.V. while E.V. is speaking.

### Voice identity

- Initially, E.V. should respond primarily to LK’s verified voice.
- A setting should allow E.V. to respond to anyone.
- Future versions should support multiple users with separate:
  - Voice profiles
  - Memories
  - Preferences
  - Permissions
  - Conversation histories

### Voice options

- Multiple selectable voices are required.
- Exact pronouns, default voice, and final voice character remain unresolved.
- Voice should run locally where practical.
- Higher-quality online voices may be optional.
- Voice customization should eventually include pitch, speed, emotional intensity, verbosity, and humor where technically appropriate.

---

## 5. Intelligence and Provider Strategy

E.V. should use a hybrid local/cloud intelligence architecture.

### Provider support

E.V. should support practical providers such as:

- Gemini
- OpenAI
- Anthropic Claude
- Local models
- OpenAI-compatible providers
- Other legitimate compatible providers

### Provider routing

E.V. may automatically select the best available provider based on:

- Task quality
- Privacy
- Availability
- Context limits
- Cost
- Latency
- Local hardware capability

When asked, E.V. should explain which provider was used.

A constant cloud-use indicator is not required, but cloud processing and privacy behavior must remain inspectable.

### Offline behavior

Basic functionality must continue without internet access, including where practical:

- Wake-word detection
- Basic voice interaction
- Local application controls
- Routine safe commands
- Local memory access
- Local music features
- Core GUI operation

### Cost policy

- No recurring API budget is allocated at present.
- Prefer local processing and legitimate free or included provider quotas.
- Existing subscriptions or provider access may be used only according to their actual terms.
- Consumer subscriptions and developer API access must not be assumed to be equivalent.
- E.V. must never bypass quotas, restrictions, payment systems, or provider terms.

---

## 6. Privacy and Data Boundaries

Personal information should remain local unless the owner explicitly approves sharing it.

### Local-first private data

The following should remain local by default:

- Personal memories
- Conversation history
- Project information
- Personal documents
- Voice profiles
- Contact and relationship information
- Health information
- Financial information
- Identity information
- User activity history

### Encryption

- Memories and conversation history should be encrypted locally.
- Sensitive memory categories require stronger access controls.
- Credentials must not be stored in conversational memory.
- Passwords, tokens, and authentication secrets belong in a secure credential vault.
- Use of stored credentials requires appropriate approval.

### Private Session

E.V. must provide a Private Session mode in which it retains no:

- Conversation history
- Raw microphone audio
- Screen content
- Activity history
- New long-term memories

Raw microphone audio should normally be deleted after processing unless the owner explicitly chooses to save it.

---

## 7. Computer Control and Autonomy

E.V. should be highly capable and should eventually perform most legitimate computer work the owner could perform personally.

### Intended capabilities

Subject to permissions and safety rules, E.V. may eventually:

- Open and close applications
- Search and organize files
- Rename and move files
- Delete files with approval
- Run validated terminal or system operations
- Control processes and services
- Change Windows settings
- Install or uninstall software
- Browse websites
- Download files
- Prepare emails and messages
- Control music
- Use the microphone when permitted
- Restart or shut down the computer with approval
- Automate multi-step workflows
- Plan and complete complex tasks
- Work in the background
- Notify the owner when work finishes

### Autonomy model

E.V. should support configurable modes:

1. **Observation Mode**  
   Explains what it would do without executing changes.

2. **Safe Mode**  
   Requests approval before changes.

3. **Standard Mode**  
   Performs routine safe actions and requests approval for risky operations.

4. **Trusted Task Mode**  
   Completes a specifically authorized plan autonomously while still respecting critical boundaries.

### Complex tasks

For complex work, E.V. should:

- Create a plan
- Show the plan before or while executing
- Execute authorized steps
- Maintain a visible activity log
- Explain failures
- Retry safely when appropriate
- Create backups or restore points before significant changes
- Attempt rollback when a task fails
- Notify the user when background work finishes

### Emergency stop

E.V. must provide:

- An emergency **“Stop EV”** voice command
- A visible emergency stop control

Emergency stop should:

- Cancel queued work
- Stop active operations where safely possible
- Prevent new execution from starting
- Preserve enough state for diagnosis and safe recovery

---

## 8. Non-Negotiable Safety Boundaries

E.V. must not:

- Create accounts autonomously
- Bypass CAPTCHAs
- Bypass multi-factor authentication
- Bypass security warnings
- Bypass provider restrictions
- Violate application or service terms
- Permanently delete important files without confirmation
- Send emails, messages, or public posts without showing the final content and receiving approval
- Purchase items autonomously
- Transfer money autonomously
- Manage banking autonomously
- Enter stored passwords without approval
- Weaken or disable firewall, antivirus, privacy, or security protections without explicit confirmation
- Hide consequential actions from the user
- Claim an action succeeded without verification
- Expose secrets in source code, logs, reports, prompts, archives, or Git
- Deploy, publish, release, commit, or push when the current development task prohibits it

### Security-setting policy

E.V. may manage security settings, but:

- Weakening or disabling protection always requires explicit confirmation.
- Strengthening protection or restoring a known-safe setting may be performed within an approved task.
- All security changes require logging.
- Significant changes require backup and rollback planning.

### Software installation

Software installation or uninstallation may occur autonomously only as part of an explicitly approved task and only through legitimate, verified sources.

---

## 9. Memory Vision

E.V. should remember broadly and naturally, similar to a trusted long-term human companion, while remaining inspectable and controllable.

### Memory categories

- Working memory
- Conversation memory
- Episodic memory
- Personal preferences
- Relationships and important people
- Daily routines
- Important dates
- Project memory
- Procedural preferences
- Music preferences and listening patterns
- Long-term goals
- Commitments and reminders
- Corrections and learned lessons

### Memory behavior

E.V. should:

- Summarize meaningful information instead of permanently saving every word
- Connect related memories
- Record the source of important information
- Track uncertainty
- Never treat assumptions as confirmed facts
- Reduce the prominence of obsolete information
- Ask before storing sensitive or ambiguous personal information when appropriate
- Retrieve relevant memories naturally
- Keep different users’ memories isolated

### User controls

The user should be able to say:

- “Remember this.”
- “Forget this.”
- “What do you remember about me?”
- “Correct that memory.”
- “Forget everything from today.”
- “Don’t save this conversation.”
- “Start a private session.”

A future memory dashboard should allow the user to:

- Inspect memories
- Correct memories
- Delete memories
- Export memories
- Review sources and confidence
- Control retention

---

## 10. Cinematic Interface Vision

### Primary form

Initial primary interface:

- Full-screen cinematic interface

Also required:

- System-tray controls

Future forms:

- Compact floating HUD
- Always-on-top mode
- Ambient display
- Multi-monitor layouts
- Mobile companion interface

### Visual identity

E.V. should look and feel:

- Futuristic
- Holographic
- Science-fiction-inspired
- Luxurious
- Polished
- Dark and mysterious where appropriate
- Original rather than copied from an existing fictional assistant

### Visual representations

E.V. should support multiple interchangeable or composable representations:

- Abstract energy core
- Orb or circular interface
- Avatar
- Circular spectrum
- Waveform
- Frequency bars
- Particles
- Pulsing orb
- 3D tunnel
- Album-art effects
- Additional selectable visualizers

### Reactive states

The appearance should respond to:

- Sleeping
- Listening
- Thinking
- Planning
- Executing
- Warning
- Error
- Music mode
- Private Session
- Microphone input
- E.V.’s voice
- Music
- System audio
- Computer activity
- Conversational tone

### Presentation modes

E.V. should eventually support:

- **Cinematic Mode:** Maximum visual impact
- **Workspace Mode:** Practical information and controls
- **Ambient Mode:** Minimal persistent visual presence
- **Performance Mode:** Reduced graphical cost
- **Music Mode:** Full audio-reactive experience

### Customization

The interface should eventually support:

- Multiple themes
- Custom colors
- Light and dark modes
- Adjustable transparency
- Full-screen and compact modes
- Always-on-top behavior
- High-performance and battery-saving modes
- Hardware-aware quality scaling

### Beauty and utility

Both cinematic beauty and practical utility are important. The interface should adapt rather than permanently sacrificing one for the other.

---

## 11. Current Approved Core and Particle Direction

This section records the owner’s latest visual requirements and may be refined through visual review.

### Core behavior

- On the Assistant page, the core remains centered at its approved normal size.
- On the Music page, only the core becomes smaller and moves into its intended corner.
- The Music-page core must remain completely visible and must not be clipped.
- Core drag, zoom, expansion, and page transitions must remain responsive.

### Global particle atmosphere

The particle atmosphere must be a separate visual layer from the core.

It must not inherit the core’s:

- Position
- Scale
- Rotation
- Dragging
- Zooming
- Expansion
- Startup spin
- Music-page movement

When the core moves to the Music-page corner, the particles must remain spread across the display.

### Particle appearance

Particles should:

- Match the core’s fire and energy colors
- Use ember, orange, amber, and golden-orange tones
- Include crisp foreground particles
- Include readable middle-depth particles
- Include faded rear particles
- Preserve convincing 3D depth
- Remain subordinate to the core
- Avoid large empty gaps
- Retain restrained full-display coverage

Particles must not appear as:

- White blobs
- Grey particles
- Green particles
- Oversized soft circles
- Uniformly faded dust
- Flat rings
- A square or rectangular field
- A layer attached to the core

The atmosphere should remain behind workspace controls where required, with enough attenuation to preserve text and panel readability.

---

## 12. Music-System Vision

E.V. should become a complete music companion rather than only a visualizer.

### Music sources

Support should eventually include:

- Local audio files
- YouTube and YouTube Music where legitimate integration is available
- Internet radio
- Other practical web music services
- Windows system audio
- External applications such as Spotify where technically and legally permitted
- Microphone or external audio input

All web integrations must respect service terms, account requirements, and platform restrictions.

### Music library

E.V. should maintain a local music library with:

- Folder scanning
- Artists
- Albums
- Genres
- Playlists
- Search
- Sorting
- Filters
- Favorites
- Listening history
- Duplicate detection
- Metadata
- Album artwork
- Smart playlists
- Recommendations

### Real-time analysis

E.V. should eventually analyze:

- Beats
- Tempo
- Spectrum
- Mood
- Energy
- Genre
- Vocals versus instrumental sections
- Drops and transitions
- Lyrics timing where available

### Visualizer inputs

Visualizers should react to:

- E.V.’s internal player
- Other applications
- Windows system audio
- Microphone and external music
- E.V.’s voice where appropriate

The existing Windows audio-reaction capability should be preserved and improved rather than unnecessarily replaced.

### Audio features

Planned features include:

- Equalizer
- Bass boost
- Presets
- Custom audio effects
- Volume normalization
- Crossfade
- Gapless playback
- Spatial or surround effects
- Beat-synchronized lighting
- Compatible smart-device control

An equalizer must not be claimed as functional until E.V. owns a verified audio decode, DSP, limiter/headroom, and output path.

### Music intelligence

E.V. should learn the user’s music taste and:

- Recommend songs
- Build playlists
- Select music for mood, activity, and time
- Learn from skipped songs
- Remember songs connected to memories
- Accept natural-language music commands

### Speaking over music

Default behavior:

- Smoothly lower or “duck” music while E.V. speaks.
- Restore the previous level afterward.
- Pause playback for important or lengthy conversations when appropriate.
- Make this behavior configurable.

---

## 13. Hardware and Platform Direction

### Current development computer

- Operating system: Windows 10
- CPU: Intel Core i7-4770K, 4 cores / 8 threads
- GPU: NVIDIA GeForce GTX 970, 4GB VRAM
- RAM: 32GB DDR3
- Storage: Approximately 5–6TB total
- Display: One 1920×1080 monitor
- Refresh rate: 60Hz
- Headphones: JBL Tune 520BT
- Speakers: Sony SA-D40

### Performance direction

The first cinematic interface should target:

- 1920×1080
- Smooth operation appropriate for a 60Hz display
- Automatic quality scaling
- Dedicated-GPU support
- Integrated-GPU support
- CPU fallback
- Performance profiles for weaker hardware

The current GTX 970 must remain an important validation target.

Do not assume that every modern CUDA build supports the GTX 970. Dependencies and acceleration paths must be verified.

### Initial platform

- Windows is the initial primary platform.
- Windows 10 is the owner’s current development environment.
- Security-sensitive public releases must account for operating-system support status.

### Future platforms

Planned future platform direction includes:

- Newer Windows versions
- macOS
- Android companion application

Linux and iPhone support were not explicitly confirmed and remain open decisions.

### Distribution

E.V. should eventually provide:

- A graphical installer
- Start-with-Windows support
- Automatic updates
- Manual update control
- Installed edition
- Portable edition
- Hardware detection
- Automatic performance configuration
- Future synchronization of encrypted settings and memories between devices

Portable and installed editions may have different limitations involving auto-start, updating, credential storage, and system integration.

---

## 14. Development Priorities

The owner explicitly requested that cinematic GUI and music development happen earlier than originally proposed.

### Approved high-level order

#### M0 — Secure and stable foundation

- Prevent private data from entering bundles
- Replace unsafe arbitrary command execution
- Centralize paths and configuration
- Establish reproducible dependencies
- Organize tests by safety category
- Preserve credentials securely
- Maintain cancellation, backup, and recovery

#### M1 — Cinematic music experience

- Full-screen 1080p cinematic interface
- Reactive energy core
- Independent volumetric particle atmosphere
- Waveforms, spectrum, frequency bars, and pulsing elements
- Music playback and library foundations
- Windows system-audio reaction
- Real-time frequency and onset analysis
- Multiple visualizers
- Themes and quality profiles
- System-tray controls
- Initial audio controls
- Responsive Music workspace

#### M2 — Voice companion

- “Hey EV” and “EV” wake phrases
- Manual activation
- LK voice verification
- Five-minute conversation mode
- Interruption while E.V. speaks
- Offline basic functionality
- Local/cloud provider routing
- Natural speech recognition and synthesis

#### M3 — Autonomous computer control

- Planning and execution
- Background tasks
- Risk-based permissions
- Approval system
- Undo, recovery, and backups
- Emergency Stop EV
- Complete activity history

#### M4 — Human-like memory and personalization

- Encrypted long-term memory
- Project, preference, music, relationship, and routine memory
- Memory dashboard
- Private Session
- Separate user profiles

#### M5 — Unified experience

- Integrate GUI, music, voice, automation, and memory
- Proactive assistance
- Adaptive behavior
- Compact floating HUD
- Multi-monitor foundations

#### M6 — Public product preparation

- Installer and updater
- Portable edition
- Hardware scaling
- Onboarding
- Privacy controls
- Documentation
- Public testing

### Development principle

The cinematic and music systems must not become disconnected demonstrations.

They should use stable interfaces that allow voice, automation, and memory to integrate later without rewriting the GUI.

---

## 15. Engineering and Safety Principles

### Preserve before changing

Before significant work:

- Create a timestamped backup.
- Record Git status and diff.
- Preserve untracked work.
- Never use destructive Git cleanup without owner approval.
- Do not overwrite unrelated work.
- Do not commit or push unless explicitly authorized.

### Evidence over claims

Do not claim that something:

- Works
- Passed
- Is secure
- Is performant
- Is production-ready
- Is fully integrated

unless it was actually verified.

Reports should distinguish:

- Confirmed facts
- Measured results
- Estimates
- Assumptions
- Recommendations
- Unresolved questions

### Secrets and private data

Never expose:

- API keys
- Passwords
- Tokens
- Private keys
- Certificates
- Production credentials
- User databases
- Personal audio
- Private memory exports
- Customer data

### Existing architecture

Continue from the accepted E.V. architecture instead of rewriting the application unnecessarily.

Current implementation technologies include:

- Python
- PySide6
- QML
- Qt Quick
- Qt Quick 3D
- GLSL shaders

Web or experimental prototypes may exist, but they must not silently replace the active product path.

---

## 16. Unresolved Owner Decisions

The following remain unresolved or require later confirmation:

- Commercial, open-source, free closed-source, or other release model
- Exact product deadline
- Final default voice
- E.V.’s preferred pronoun or whether it should simply be called E.V.
- Initial supported spoken languages
- Mixed-language conversation requirements
- Exact cloud-provider priority
- Final cross-device synchronization architecture
- Linux support
- iPhone companion support
- Final visual reference or mood board
- Final public privacy policy
- Public account and licensing model
- Exact onboarding experience
- Exact crash-reporting policy
- Final telemetry policy

These must not be silently decided by a coding agent.

---

## 17. Current Definition of Success

E.V. is successful when it feels like one coherent companion rather than a collection of disconnected tools.

The intended experience is:

- Visually impressive
- Personally adaptive
- Musically intelligent
- Capable of complex work
- Safe around consequential actions
- Honest about uncertainty
- Useful without internet for basic tasks
- Private by default
- Inspectable and reversible
- Smooth on the owner’s current hardware
- Expandable into a public product without discarding the original architecture

The ultimate experience should combine cinematic presence, practical utility, music awareness, long-term memory, natural voice interaction, and controlled autonomy.

---

## 18. Instructions for Future Agents

Before working on E.V.:

1. Read this complete document.
2. Read `ASTRA_HANDOFF.md`.
3. Read `ASTRA_PLAN.md`.
4. Inspect current Git status without changing it.
5. Identify the active implementation path.
6. Preserve uncommitted work.
7. Confirm the specific task and editable files.
8. Create a timestamped backup.
9. Make the smallest task-scoped change.
10. Run focused verification.
11. Report measured results honestly.
12. Wait for owner approval before committing or pushing.

A future agent must never reinterpret E.V. as only:

- A visualizer
- A chatbot
- A music player
- A command runner
- A static HUD

E.V. is intended to become the integrated product described in this document.

---

## 19. Decision History

### 2026-09-20 — Initial canonical reconstruction

Recovered and consolidated the owner’s explicit product decisions from the archived E.V. development conversation.

Confirmed:

- Combined assistant identity
- LK-first and public-later direction
- Adaptive companion personality
- Voice, text, and cinematic interaction
- Five-minute follow-up conversation
- Hybrid local/cloud intelligence
- Local-first privacy and encrypted memory
- High autonomy with explicit critical boundaries
- Human-like memory
- Full-screen cinematic direction
- Complete music-system ambition
- Windows-first hardware and distribution requirements
- Cinematic GUI and music moved earlier in the roadmap
- Independent full-display fire particle atmosphere as the latest visual direction

Unresolved items remain listed in Section 16.

### 2026-09-21 — Core Frustum Clipping Fix, Fire Particles Finalization & Workspace Cleanup

- **Core Spherical Silhouette & Frustum Restored**: Resolved the issue where the 3D nucleus core appeared square/flat-edged. The camera's `boundedCoreFieldOfView` was restored from `27.5°` to `38°` in `prototypes/cinematic_v4/qml/NucleusView.qml`. At `27.5°`, the camera frustum at $z=382$ only provided a view half-width of $93.5$ scene units, physically clipping the outer $109.2$-unit rings, plates, and schematics into a flat-edged box. At `38°`, the frustum provides $131.5$ units of view space, allowing the entire core to remain fully visible, round, and unclipped across all normal orientations and zoom levels.
- **Independent Full-Screen Fire Particle Atmosphere**: Finalized and validated `OrbitalAura.qml` with 1,400 independent GPU particles across three depth layers with size $\le 8.0\text{ px}$ (P95 $\approx 4.0\text{ px}$), single draw call, and independent screen-space coordinate system.
- **Contract & Validation Suite**: Added and verified all 12 contract assertions in `tests/test_cinematic_orbital_aura.py` and `validate_independent_fire.py`.
- **Checkpoint Commit & Remote Push**: Created commit `a97c09c` (`feat(cinematic): fix core spherical frustum clipping and finalize independent fire particles`) and pushed to `origin/master`.
- **Workspace Hygiene**: Cleaned up 81 obsolete review folders, loose screenshots, scratch test scripts, and root logs, freeing ~220 MB.

