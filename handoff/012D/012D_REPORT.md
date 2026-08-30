# 012D — Verification / Risk / Backup Event Attachment

Status: **IN PROGRESS**
Date: 2026-08-30 (IST)
Rollback boundary: git `9c34e12` (012C.5 checkpoint)

## Scope (approved, narrower)
Attach verifier/risk/backup/restore results to persistent task history as
structured `task_history_events` records, using a bounded allow-list serializer.

Decisions approved by user:
- **task_id**: explicit `task_id` argument on each typed attach method. Do NOT add
  task_id/correlation_id fields to the result models.
- **EVAgent**: unchanged. No `attach_*` pass-throughs on the agent. Attachment
  capability lives only in `EVTaskHistoryStore`, consumed later by an orchestrator.

Modify ONLY: `core/history.py`, `tests/test_history.py`.
Do NOT modify: result models, verifier/risk/backup engines, EVAgent, QML/UI, or any
unrelated file. No `git add .`, no cleanup, no touching `.bak`/`.pre-*` backups.

## Pre-existing foundation (verified in current code)
- `EVTaskHistoryStore.append_event(task_id, event_type, payload, *, created_at)`
  (`core/history.py:455`) — the documented extension point. Validates task exists
  (`_require_task` → `KeyError`), inserts into `task_history_events`, bumps updated_at.
- `TaskHistoryEventType` (`core/models.py:292`) already has VERIFICATION_RESULT,
  RISK_ASSESSMENT, BACKUP_RESULT, RESTORE_RESULT, RECOVERY_RESULT, NOTE.
- Schema `task_history_events` already supports this. **No schema change needed.**
- Engines return pydantic models: VerificationResult, RiskAssessmentResult,
  BackupResult, RestoreResult (none carry task_id — finding #4 in ARCHITECTURE_012).

## Gap 012D closes
`append_event` takes a raw dict only. `summarize_result()`'s allow-list is tuned to
read-only tool evidence, not these result models. `VerificationResult.evidence_summary`
can embed a full TextReadResult (entire file contents). Need typed attach methods with
an explicit bounded serializer that never persists evidence/file contents.

## API added (core/history.py)
- `attach_verification(task_id: str, result: VerificationResult, *, created_at=None) -> TaskHistoryEventRecord`
- `attach_risk_assessment(task_id: str, result: RiskAssessmentResult, *, created_at=None) -> TaskHistoryEventRecord`
- `attach_backup(task_id: str, result: BackupResult, *, created_at=None) -> TaskHistoryEventRecord`
- `attach_restore(task_id: str, result: RestoreResult, *, created_at=None) -> TaskHistoryEventRecord`
- private `_bounded_payload(result, allowed_fields) -> dict` (explicit field allow-list,
  attribute-based, never `model_dump()` of the whole object).

Each method: type-checks its argument (TypeError on mismatch), builds a bounded payload,
delegates to `append_event` (which enforces task existence → KeyError).

## Payload contract (explicit allow-lists)
- VERIFICATION_RESULT: type, verification_type, status, success, message, error, timestamp.
  **EXCLUDES `evidence_summary`** (this is where full file content / TextReadResult lives).
- RISK_ASSESSMENT: type, action_category, risk_level, decision, allowed, requires_approval,
  reason, policy_rule, evaluated_at, error.
- BACKUP_RESULT: type, status, success, executed, original_path, backup_path, message,
  error, started_at, finished_at, duration_seconds, and a bounded `backup_record`
  (original_size_bytes, backup_size_bytes, sha256, original_exists, success) when present.
- RESTORE_RESULT: type, status, success, executed, original_path, backup_path, message,
  error, started_at, finished_at, duration_seconds, safety_backup_path.

No file contents, no raw evidence, no unrestricted model serialization ever enter the payload.

## Tests added (tests/test_history.py) — per attach type
1. correct TaskHistoryEventType
2. correct task_id linkage
3. bounded payload (only allow-listed keys)
4. sensitive/full-content evidence NOT persisted
5. unknown task_id raises KeyError
6. round-trips via get_events()
7. existing history tests still pass

## Baseline to compare (from 012C5_DIAGNOSIS_REPORT.md)
`D:\EV\.venv\Scripts\python.exe -m pytest tests -q` → 250 passed, 6 subtests passed,
1 failed (`tests/test_processes_network.py::test_process_list`, WinError 2 spawning
powershell.exe — sandbox PATH artifact, unrelated).

## Progress log
- [x] Findings + design captured (this file)
- [x] core/history.py implemented (additive: 4 attach methods + `_bounded_payload` + 5 allow-list constants + 4 model imports)
- [x] tests/test_history.py: added `TestEVTaskHistoryAttachments` (13 tests) + `import json`
- [x] `python3 -m py_compile core/history.py tests/test_history.py core/models.py` → clean
- [ ] BLOCKED: `pytest tests -q` could not be executed in this session (see below)

## Verification status — BLOCKED in this environment
This session runs in a Linux sandbox. The project venv (`D:\EV\.venv`) is Windows-only
(`Scripts\python.exe`) and its `pydantic_core` is a compiled `cp312-win_amd64.pyd`, which
cannot load under the sandbox's Linux CPython 3.10. `pip install` is blocked (no network /
proxy 403), so pydantic+pytest cannot be provisioned here either.

What WAS verified here:
- `py_compile` passes for `core/history.py`, `tests/test_history.py`, `core/models.py`.
- Static trace: each attach method delegates to `append_event` (→ `_require_task` → KeyError
  for unknown task); `_bounded_payload` uses only `hasattr`/`getattr` over an explicit
  allow-list (never `model_dump()`), so `evidence_summary`/file contents cannot leak.
- Payload key-sets asserted in tests match `{"type"} ∪ allow-list` produced by the code.

ACTION REQUIRED (user, on Windows):
`D:\EV\.venv\Scripts\python.exe -m pytest tests -q`
Compare to 012C.5 baseline (250 passed / 1 unrelated powershell WinError-2 failure).

## Repo-state note (pre-existing, not introduced by 012D)
At checkpoint `9c34e12`, `core/history.py` and `tests/test_history.py` are **untracked**
(the 012B/012C history work lives only in the working tree; the commit itself was the GUI
core-render fix). `core/agent.py` IS tracked and imports `from .history import ...`, so a
clean checkout of `9c34e12` would not import `core.agent`. When checkpointing 012D, both
`core/history.py` and `tests/test_history.py` must be committed for a coherent tree.

