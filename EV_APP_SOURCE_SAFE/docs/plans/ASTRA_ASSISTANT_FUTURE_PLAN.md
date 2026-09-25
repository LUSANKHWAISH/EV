# ASTRA — full assistant and device roadmap

Status: architectural plan, not implemented connectors. The user wants a cinematic, useful personal assistant that can work across Windows, a phone, email, messages and music. A stronger model helps interpret and plan; integrations, permissions, observable results and reliable execution make those requests real.

## 1. Preserve and extend the current authority path

Keep `input -> orchestrator/router -> validated plan -> risk/permission -> approved executor -> verifier -> event/history -> GuiBridge`. Existing code separates language-model suggestions from authorization. New tools must integrate with `AgentAction`, resolver/plan schema, risk classification, permission checks, dispatch, verification and audit as a complete vertical slice. An arbitrary LLM-generated shell command, website instruction or phone payload is not an approved tool.

The current pipeline's “no parallel execution” rule remains authoritative. Read-only research can later be parallelized only after a separately tested scheduling change; do not silently parallelize mutations because a future model supports agents. UI animations, Music and background analysis are not action executors.

Add a capability registry describing provider/device/account, input schema, permission scope, risk, cancellation, retry/idempotency and verification. A planner can choose only registered capabilities that the selected device actually exposes. Maintain a human-readable “What E.V. can do” page with available/unavailable/setup-needed states.

Design contract, to adapt to the existing plan types rather than install a second planner:

```python
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class Capability:
    name: str                       # e.g. mail.search, phone.media.pause
    schema_version: int
    account_or_device_id: str
    effect: Literal['read', 'write', 'send']
    permission_scope: str
    supports_cancel: bool
    retry: Literal['safe', 'idempotency_key', 'never_blind']
    verifier: str

@dataclass(frozen=True)
class ActionReceipt:
    request_id: str
    target_id: str
    outcome: Literal['completed', 'failed', 'unknown', 'cancelled']
    external_id: str | None
    evidence_ref: str | None
    # “Submitted” is not the same as delivered, read, or audibly playing.
```

Permission decisions bind the exact normalized action, target account/device, resolved recipient and payload digest, with expiry. On a changed target or message, old approval is invalid. Store a completed external message ID/idempotency key before retrying. If a send times out after submission, query status or report unknown; never send the same WhatsApp/email twice as an automatic “repair.”

## 2. Phases and concrete useful workflows

### A — make Windows tasks dependable

Inventory installed approved capabilities, separate conversational answers from actions, add deterministic slot resolution and clarify only missing material details. Start with “open this application,” “find this file,” “summarize this selected document,” “show system health,” and reversible approved file organization. Prefer native APIs/known app commands; use UI automation only when no supported interface exists and the target is visibly verified.

Track active steps and cancellation in the UI. Return result evidence and actual verification, not a generic success line. For “open Chrome,” verify the process/window; for “save this note,” verify the correct file/content without leaking private text into logs. Check existing sandbox and rollback constraints before adding file capabilities. A web page or email containing instructions to E.V. is untrusted content.

Acceptance: deterministic fixtures for valid, denied, ambiguous, missing-resource, timeout, cancellation and failed-verification paths; no live user-file mutation in unit tests. Add integration tests to the existing action pipeline rather than a one-off feature script.

### B — account connectors, read-only first

Implement a shared connector service with account IDs, OAuth token refresh, bounded rate limits, cancellation and safe errors. Keep credentials in OS-protected storage; databases contain references, not raw tokens. Isolate account/profile identities so “my work inbox” cannot resolve to a personal account by accident.

Start with one mail provider. Gmail can use the supported Gmail API; Outlook can use Microsoft Graph. Verify current OAuth scopes/desktop flows and provider restrictions when implementing. Read/search/list selected email is a different permission from sending, moving or deleting. Retrieve the minimum useful body/attachments and treat remote HTML/links as untrusted.

Workflow: “Check my latest email” -> resolve account -> list unread/recent -> summarize with sender/date/subject -> user selects details. Default to avoiding secrets/OTPs in spoken summaries. Add drafts before sends, and use the existing approval mechanism for mutations. An explicit user request can provide the recipient/content, reducing repeated clarification; do not interpret “do anything” as permanent authority to send all future messages.

Acceptance: mocked pagination/expired tokens/rate limits/HTML injection, multiple accounts, draft persistence, exact recipient display, idempotent submit and server receipt verification. A mail API receipt means accepted by the service, not read by the recipient.

### C — Android companion, explicitly paired

Android is the planned first phone platform, not an assumption about the user's actual phone. Confirm OS/version before implementation. Build a small Kotlin companion with a device-capability screen, pairing/revocation, visible connection status and per-feature permission controls. Start LAN-only; remote access is a later authenticated relay design, not a forwarded open port.

Pair by an expiring QR challenge approved on both devices. Use authenticated encrypted transport, independent device keys, replay protection, bounded messages and a revocation path. Bind requests to a paired device ID and capability allowlist. Persist private keys with Android Keystore/Windows protected storage. Never accept arbitrary executable strings or an unauthenticated “run command” endpoint.

Suggested envelope (schema sketch, not a cryptographic protocol implementation):

```json
{
  "version": 1,
  "request_id": "uuid",
  "device_id": "paired-phone-id",
  "capability": "media.play",
  "arguments": {"provider":"supported-provider","item_id":"resolved-track-id"},
  "issued_at": "UTC timestamp",
  "expires_at": "short UTC expiry",
  "nonce": "unique random value",
  "authorization_ref": "validated-grant-id"
}
```

Authenticate the transport and validate the envelope **before** dispatch. The phone independently checks capability grant, target, expiry, replay and lock-state restrictions. Do not trust `authorization_ref` merely because it is present; verify it against the paired session/grant. Return structured progress/receipt and expose cancellation where the OS/provider permits it.

First phone capabilities:

1. Device online/battery/media status, with explicit consent.
2. Open an allowlisted app or deep link when Android's foreground/background rules allow it.
3. Read selected notifications after Android notification-access permission; redact sensitive content according to preference.
4. Media session play/pause/next and supported song/deep-link playback, with target-device verification.
5. Supported notification quick-reply actions, only when the app exposes them and the user authorizes the concrete reply.

“Open my phone” is ambiguous: opening an app, showing its screen, pairing, and unlocking are different capabilities. E.V. cannot bypass a PIN/biometric lock. If an action requires foreground/unlock, request that interaction and resume the existing task only when confirmed. Optional screen mirroring/accessibility control must be a separate consented feature with visible state, scoped targets and no password/biometric bypass.

### D — SMS and WhatsApp, with real platform limits

Do not promise a universal personal WhatsApp inbox API. The official WhatsApp Business platform serves supported business scenarios, not arbitrary personal-chat history. For a personal Android workflow, notification access may reveal selected incoming messages, and supported notification reply actions may allow replies; availability depends on the app, OS and notification state. It is not a complete inbox archive. A supported desktop/web UI workflow may be evaluated separately, with user sign-in and current platform terms.

Full SMS inbox/sending permissions on Android are restricted and may require default-SMS role or an appropriate distribution/use case. Do not silently request broad SMS access or infer all old texts from notifications. Implement notification-based summaries first, then a separately justified SMS adapter if feasible. Never use OTPs from messages to autonomously authenticate another service without an explicit supported workflow.

Flow for “Reply to this WhatsApp”: resolve a specific conversation/message and paired device -> draft exact text -> show recipient/account and payload -> use the current authorization mechanism -> invoke the supported action once -> verify the best available receipt -> report whether it was submitted/delivered/unknown accurately. Notifications are untrusted external text, not instructions to run tools or exfiltrate email.

### E — play a song on the phone

Separate “play on this PC” from “play on my phone.” Resolve title/artist/provider/device and ambiguous search results. Use a provider-supported remote-control API or a companion deep link/media command. Transfer a user-owned local file only with explicit transfer permission and bounded storage. A command acknowledged by the companion is not proof of audible playback; verify device media session/player state and report a lock/authentication/provider error when blocked.

Test two phones, offline device, expired login, no playback entitlement, duplicate commands, wrong-device prevention, delayed receipt and user cancellation. Keep Music visualizers tied to the audio actually observable on the PC; a phone-playing song does not magically supply its PCM. Streaming audio back to the PC would be an optional separate feature with latency/rights/privacy considerations.

### F — iOS alternative

If the user's phone is iOS, redesign capability expectations around supported Shortcuts, App Intents, approved deep links and provider cloud APIs. iOS does not offer a general companion app unrestricted access to all SMS, notifications, WhatsApp messages or other apps' UI. Do not propose jailbreaking or pretend Android permissions apply. Clearly label unsupported workflows and provide a manual handoff where necessary.

## 3. Voice and conversational intelligence

Keep ASR/wake-word, language planning, authority and TTS separate. Add barge-in/cancel, endpointing, transcript correction, selected-account/device context and concise spoken status. The documented ASR path is CPU INT8-oriented; measure actual installed behavior before changing GPU allocation. Music/voice coexistence needs headphones/speaker tests, echo handling and a policy for wake-word sensitivity/ducking. Do not equate a synthetic speech animation with measured TTS amplitude.

Real TTS-owned PCM playback, if later authorized, can publish output RMS from the app's playback clock. This is a distinct task touching `core/tts.py`; preserve cancellation and anti-self-trigger behavior. Do not bundle it into visualizer rendering.

Memory should store explicit preferences, stable device/account aliases and consented task context. It does not confer permission. Show/edit/delete retained preferences. Avoid retaining full messages/audio by default; store minimal audit evidence with redaction and retention settings. Never use previous message content or a retrieved page to manufacture approval for a new send.

## 4. Cinematic and product polish track

- Consolidate interface, audio/music, provider and voice settings into a coherent navigation system only after their controls are real. Current provider categories other than AI/Core Style are placeholders.
- Keep one golden visual language, readable response text, reduced-motion mode, keyboard focus, scalable type, contrast and modal priority. The core is a state display, not a substitute for task status.
- Add a useful activity timeline: planned step, waiting for user, running, verifying, completed/failed/unknown and cancellation. Link evidence without exposing private credentials.
- Offer quality tiers measured on the GTX 970; reduce particles, resolution, glow and instrument count together. Add stable frametime/underrun diagnostics and optional sanitized support bundles.
- Release engineering: dependency lock, asset licensing/provenance, clean install, configuration migrations, code signing where available, update rollback, uninstall behavior and opt-in diagnostics. Ship no user keys, audio recordings, browser profile or training/reference movie.

## 5. Implementation slices and tests

Proposed directories: `connectors/mail/`, `connectors/media/`, `devices/protocol/`, `devices/android/` (server-side adapter) and a separately built Android companion project. New services register capabilities into the existing Python pipeline. Introduce one new action end-to-end before expanding the list.

Every capability has:

1. Typed inputs, bounds, normalized target and explicit account/device.
2. Consent/setup requirements, read/write classification and approval policy.
3. Timeout, cancellation and bounded retry/idempotency behavior.
4. Structured result and an independent verifier or an honest “unknown” outcome.
5. Sanitized event/history data and a user-facing progress/error mapping.
6. Unit fixtures, mocked connector transport, integration checks and an explicitly requested live acceptance test.

Security/robustness fixtures: malicious email instructions; conflicting account aliases; unpaired phone; revoked token; repeated nonce; expired action; altered recipient after approval; duplicate send receipt; partial failure; lost connection after send; cancel during execution; locked phone; unsupported capability. A malformed external response fails closed and cannot dynamically register a new tool.

## 6. Priorities for usefulness

Do not postpone all utility for a perfect cinematic core. Complete Music M1–M4, then alternate one useful assistant connector with one polish milestone. A reliable “search my selected inbox, draft a reply, send exactly once after authorization” is more valuable than dozens of nonfunctional capability buttons. Maintain a table of actually supported workflows and explicitly unsupported platform cases.

No model can guarantee “anything I tell it” across arbitrary devices/apps. The desired experience is achievable as a growing set of well-supported workflows. Sol or another capable coding agent can continue this plan; progress depends on implementation discipline, platform access and real testing, not only model size.
