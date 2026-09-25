# E.V. TASK 012 — PERSISTENT TASK HISTORY ARCHITECTURE

## 012A live-source findings

1. AgentTask already has the correct durable identity anchor:
   - task_id
   - action
   - parameters
   - created_at

2. AgentRunResult already propagates task_id and carries:
   - AgentStatus
   - one AgentStepResult
   - error

3. AgentStepResult already carries:
   - action
   - success
   - started_at
   - finished_at
   - duration_seconds
   - result
   - error

4. VerificationResult, BackupResult/RestoreResult and RiskAssessmentResult do
   not currently contain task_id.

5. EVEvent has correlation_id and arbitrary data, so it can later carry task
   identity without changing the event bus contract.

6. EVEventBus history is memory-only:
   - deque(maxlen=500)
   - disappears when the process exits
   It is NOT persistent task history.

7. There is no existing database, persistence service, or memory module in the
   current core project files.

8. EVAgent, EVVerifier, EVBackupManager, EVRiskEngine and EVEventBus are
   currently separate components. The inspected source does not contain a
   higher-level orchestrator that binds all of them into one task lifecycle.

## Storage decision

Use Python's built-in sqlite3.

Why:
- local/offline
- durable
- transactional
- zero new dependency
- small footprint
- queryable later by GUI/history/memory features
- schema migrations can be versioned using PRAGMA user_version

Do not use JSON files as the primary store: concurrent updates, filtering and
future migrations become unnecessarily fragile.

## Schema

task_history:
- one current summary row per task_id

task_history_events:
- append-only structured lifecycle records linked to task_id

The event table is deliberately extensible for later:
- verification results
- risk assessments
- backup/restore results
- recovery results
- notes

## Privacy / size decision

Do NOT persist full arbitrary tool results by default.

Example: READ_TEXT_FILE can contain entire file contents. Persisting that would
turn task history into an uncontrolled copy of user data.

012B therefore stores a bounded result summary:
- type
- counts
- safe metadata
- status/error information

Full evidence remains outside task history unless a later feature explicitly
opts in.

## Phases

012A  Live architecture inspection                    COMPLETE
012B  SQLite history foundation + models + tests     THIS PACKAGE
012C  EVAgent lifecycle integration                  NEXT AFTER WINDOWS TEST
012D  verification/risk/backup event attachment      LATER
012E  query/final validation + accepted checkpoint   LATER

012B intentionally does not modify the agent yet.
