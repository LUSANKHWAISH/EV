"""
Unit tests for E.V. persistent task history (Task 012B).
"""

import json
import sqlite3
import tempfile
from contextlib import closing
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.history import EVTaskHistoryStore
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentStepResult,
    AgentTask,
    BackupResult,
    BackupStatus,
    FileBackupRecord,
    PermissionDecision,
    RestoreResult,
    RiskAssessmentResult,
    RiskLevel,
    TaskHistoryEventType,
    TextReadResult,
    VerificationResult,
    VerificationStatus,
    VerificationType,
)


class TestEVTaskHistoryStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "history.sqlite3"
        self.store = EVTaskHistoryStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _task(
        self,
        task_id="task-1",
        *,
        action=AgentAction.FIND_PROCESS,
        parameters=None,
        created_at=None,
    ):
        return AgentTask(
            task_id=task_id,
            action=action,
            parameters=parameters or {"name": "python"},
            created_at=created_at or datetime.now(),
        )

    def _completed_result(self, task, result=None):
        started = datetime.now()
        finished = started + timedelta(milliseconds=25)
        return AgentRunResult(
            task_id=task.task_id,
            status=AgentStatus.COMPLETED,
            step=AgentStepResult(
                action=task.action,
                success=True,
                started_at=started,
                finished_at=finished,
                duration_seconds=(finished - started).total_seconds(),
                result=result,
            ),
        )

    def _failed_result(self, task, message="simulated failure"):
        started = datetime.now()
        finished = started + timedelta(milliseconds=10)
        return AgentRunResult(
            task_id=task.task_id,
            status=AgentStatus.FAILED,
            error=message,
            step=AgentStepResult(
                action=task.action,
                success=False,
                started_at=started,
                finished_at=finished,
                duration_seconds=(finished - started).total_seconds(),
                error=message,
            ),
        )

    def test_database_and_schema_are_created(self):
        self.assertTrue(self.db_path.exists())

        with closing(sqlite3.connect(self.db_path)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }

        self.assertEqual(version, 1)
        self.assertIn("task_history", tables)
        self.assertIn("task_history_events", tables)

    def test_record_task_creates_pending_history(self):
        task = self._task()

        record = self.store.record_task(task)

        self.assertEqual(record.task_id, task.task_id)
        self.assertEqual(record.action, task.action)
        self.assertEqual(record.parameters, task.parameters)
        self.assertEqual(record.status, AgentStatus.PENDING)
        self.assertIsNone(record.success)

        events = self.store.get_events(task.task_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(
            events[0].event_type,
            TaskHistoryEventType.TASK_CREATED,
        )

    def test_record_task_is_idempotent_for_same_definition(self):
        created_at = datetime.now()
        task = self._task(created_at=created_at)

        first = self.store.record_task(task)
        second = self.store.record_task(task)

        self.assertEqual(first.task_id, second.task_id)
        self.assertEqual(len(self.store.get_events(task.task_id)), 1)

    def test_duplicate_task_id_with_different_definition_is_rejected(self):
        created_at = datetime.now()
        self.store.record_task(
            self._task(
                task_id="same-id",
                action=AgentAction.FIND_PROCESS,
                parameters={"name": "python"},
                created_at=created_at,
            )
        )

        with self.assertRaises(ValueError):
            self.store.record_task(
                self._task(
                    task_id="same-id",
                    action=AgentAction.FIND_TCP_PORT,
                    parameters={"port": 4000},
                    created_at=created_at,
                )
            )

    def test_mark_started_sets_running_status(self):
        task = self._task()
        self.store.record_task(task)
        started_at = datetime.now()

        record = self.store.mark_started(
            task.task_id,
            started_at=started_at,
        )

        self.assertEqual(record.status, AgentStatus.RUNNING)
        self.assertEqual(record.started_at, started_at)

        events = self.store.get_events(task.task_id)
        self.assertEqual(
            events[-1].event_type,
            TaskHistoryEventType.TASK_STARTED,
        )

    def test_record_completed_run_persists_summary(self):
        task = self._task()
        result = self._completed_result(task, result=[1, 2, 3])

        record = self.store.record_run(task, result)

        self.assertEqual(record.status, AgentStatus.COMPLETED)
        self.assertTrue(record.success)
        self.assertIsNotNone(record.started_at)
        self.assertIsNotNone(record.finished_at)
        self.assertGreaterEqual(record.duration_seconds or 0, 0)
        self.assertEqual(
            record.result_summary,
            {
                "type": "list",
                "count": 3,
                "item_types": ["int"],
            },
        )

        events = self.store.get_events(task.task_id)
        self.assertEqual(
            events[-1].event_type,
            TaskHistoryEventType.TASK_COMPLETED,
        )

    def test_record_failed_run_persists_error(self):
        task = self._task()
        result = self._failed_result(task, "boom")

        record = self.store.record_run(task, result)

        self.assertEqual(record.status, AgentStatus.FAILED)
        self.assertFalse(record.success)
        self.assertEqual(record.error, "boom")
        self.assertEqual(
            self.store.get_events(task.task_id)[-1].event_type,
            TaskHistoryEventType.TASK_FAILED,
        )

    def test_full_text_file_content_is_not_persisted_in_result_summary(self):
        secret_content = "DO_NOT_PERSIST_THIS_CONTENT_12345"
        task = self._task(
            action=AgentAction.READ_TEXT_FILE,
            parameters={"path": "C:\\temp\\example.txt"},
        )
        tool_result = TextReadResult(
            path="C:\\temp\\example.txt",
            success=True,
            content=secret_content,
            encoding="utf-8",
            truncated=False,
            size_bytes=len(secret_content),
        )

        record = self.store.record_run(
            task,
            self._completed_result(task, result=tool_result),
        )

        self.assertEqual(record.result_summary["type"], "TextReadResult")
        self.assertNotIn("content", record.result_summary)

        raw_db = self.db_path.read_bytes()
        self.assertNotIn(secret_content.encode("utf-8"), raw_db)

    def test_append_event_supports_future_component_results(self):
        task = self._task()
        self.store.record_task(task)

        event = self.store.append_event(
            task.task_id,
            TaskHistoryEventType.VERIFICATION_RESULT,
            {
                "status": "VERIFIED",
                "success": True,
            },
        )

        self.assertEqual(
            event.event_type,
            TaskHistoryEventType.VERIFICATION_RESULT,
        )
        self.assertEqual(event.payload["status"], "VERIFIED")

        events = self.store.get_events(task.task_id)
        self.assertEqual(len(events), 2)

    def test_append_event_requires_existing_task(self):
        with self.assertRaises(KeyError):
            self.store.append_event(
                "missing-task",
                TaskHistoryEventType.NOTE,
                {"message": "no task"},
            )

    def test_history_survives_store_recreation(self):
        task = self._task()
        self.store.record_run(
            task,
            self._completed_result(task, result=[]),
        )

        reopened = EVTaskHistoryStore(self.db_path)
        record = reopened.get_task(task.task_id)

        self.assertIsNotNone(record)
        self.assertEqual(record.status, AgentStatus.COMPLETED)
        self.assertTrue(record.success)

    def test_list_tasks_filters_and_orders_newest_first(self):
        old_time = datetime.now() - timedelta(minutes=2)
        new_time = datetime.now()

        old_task = self._task(
            task_id="old",
            action=AgentAction.FIND_PROCESS,
            created_at=old_time,
        )
        new_task = self._task(
            task_id="new",
            action=AgentAction.FIND_TCP_PORT,
            parameters={"port": 4000},
            created_at=new_time,
        )

        self.store.record_run(
            old_task,
            self._completed_result(old_task, result=[]),
        )
        self.store.record_run(
            new_task,
            self._failed_result(new_task, "port failure"),
        )

        records = self.store.list_tasks(limit=10)
        self.assertEqual([record.task_id for record in records], ["new", "old"])

        failed = self.store.list_tasks(
            limit=10,
            status=AgentStatus.FAILED,
        )
        self.assertEqual([record.task_id for record in failed], ["new"])

        process_tasks = self.store.list_tasks(
            limit=10,
            action=AgentAction.FIND_PROCESS,
        )
        self.assertEqual(
            [record.task_id for record in process_tasks],
            ["old"],
        )

    def test_get_events_limit_returns_latest_events_in_chronological_order(self):
        task = self._task()
        self.store.record_task(task)
        self.store.append_event(
            task.task_id,
            TaskHistoryEventType.NOTE,
            {"index": 1},
        )
        self.store.append_event(
            task.task_id,
            TaskHistoryEventType.NOTE,
            {"index": 2},
        )

        events = self.store.get_events(task.task_id, limit=2)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].payload["index"], 1)
        self.assertEqual(events[1].payload["index"], 2)

    def test_invalid_limits_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.list_tasks(limit=0)

        task = self._task()
        self.store.record_task(task)

        with self.assertRaises(ValueError):
            self.store.get_events(task.task_id, limit=0)

    def test_get_missing_task_returns_none(self):
        self.assertIsNone(self.store.get_task("does-not-exist"))


class TestEVTaskHistoryAttachments(unittest.TestCase):
    """012D: typed verification/risk/backup/restore attachment (bounded payloads)."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "history.sqlite3"
        self.store = EVTaskHistoryStore(self.db_path)
        self.task = AgentTask(
            task_id="attach-1",
            action=AgentAction.READ_TEXT_FILE,
            parameters={"path": "C:\\temp\\example.txt"},
            created_at=datetime.now(),
        )
        self.store.record_task(self.task)

    def tearDown(self):
        self.temp_dir.cleanup()

    # --- verification -------------------------------------------------
    def test_attach_verification(self):
        secret = "SECRET_FILE_BODY_DO_NOT_PERSIST_987"
        evidence = TextReadResult(
            path="C:\\temp\\example.txt",
            success=True,
            content=secret,
            encoding="utf-8",
            truncated=False,
            size_bytes=len(secret),
        )
        result = VerificationResult(
            verification_type=VerificationType.TEXT_CONTAINS,
            status=VerificationStatus.VERIFIED,
            success=True,
            message="Text 'foo' found in file",
            evidence_summary=evidence,
        )

        event = self.store.attach_verification(self.task.task_id, result)

        # 1. correct event type
        self.assertEqual(event.event_type, TaskHistoryEventType.VERIFICATION_RESULT)
        # 2. task_id linkage
        self.assertEqual(event.task_id, self.task.task_id)
        # 3. bounded payload (only allow-listed keys)
        self.assertEqual(
            set(event.payload.keys()),
            {"type", "verification_type", "status", "success", "message", "error", "timestamp"},
        )
        self.assertEqual(event.payload["type"], "VerificationResult")
        self.assertEqual(event.payload["status"], "VERIFIED")
        self.assertEqual(event.payload["verification_type"], "TEXT_CONTAINS")
        # 4. sensitive/full-content evidence is NOT persisted (payload or raw DB)
        self.assertNotIn("evidence_summary", event.payload)
        self.assertNotIn(secret, json.dumps(event.payload))
        self.assertNotIn(secret.encode("utf-8"), self.db_path.read_bytes())
        # 6. round-trips via get_events
        stored = self.store.get_events(self.task.task_id)[-1]
        self.assertEqual(stored.event_type, TaskHistoryEventType.VERIFICATION_RESULT)
        self.assertEqual(stored.payload["status"], "VERIFIED")
        self.assertNotIn("evidence_summary", stored.payload)

    def test_attach_verification_unknown_task_raises_keyerror(self):
        result = VerificationResult(
            verification_type=VerificationType.FILE_EXISTS,
            status=VerificationStatus.VERIFIED,
            success=True,
            message="ok",
            evidence_summary=None,
        )
        with self.assertRaises(KeyError):
            self.store.attach_verification("missing-task", result)

    def test_attach_verification_rejects_wrong_type(self):
        with self.assertRaises(TypeError):
            self.store.attach_verification(self.task.task_id, {"status": "VERIFIED"})

    # --- risk ---------------------------------------------------------
    def test_attach_risk_assessment(self):
        result = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.MEDIUM,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="File modification requires user approval",
            policy_rule="file_modify_requires_approval",
        )

        event = self.store.attach_risk_assessment(self.task.task_id, result)

        self.assertEqual(event.event_type, TaskHistoryEventType.RISK_ASSESSMENT)
        self.assertEqual(event.task_id, self.task.task_id)
        self.assertEqual(
            set(event.payload.keys()),
            {
                "type",
                "action_category",
                "risk_level",
                "decision",
                "allowed",
                "requires_approval",
                "reason",
                "policy_rule",
                "evaluated_at",
                "error",
            },
        )
        self.assertEqual(event.payload["risk_level"], "MEDIUM")
        self.assertEqual(event.payload["decision"], "REQUIRE_APPROVAL")

        stored = self.store.get_events(self.task.task_id)[-1]
        self.assertEqual(stored.event_type, TaskHistoryEventType.RISK_ASSESSMENT)
        self.assertEqual(stored.payload["action_category"], "FILE_MODIFY")

    def test_attach_risk_unknown_task_raises_keyerror(self):
        result = RiskAssessmentResult(
            action_category=ActionCategory.READ_ONLY_OBSERVATION,
            risk_level=RiskLevel.NONE,
            decision=PermissionDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            reason="ok",
            policy_rule="read_only_allowed",
        )
        with self.assertRaises(KeyError):
            self.store.attach_risk_assessment("missing-task", result)

    # --- backup -------------------------------------------------------
    def test_attach_backup_with_bounded_record(self):
        record = FileBackupRecord(
            original_path="C:\\temp\\example.txt",
            backup_path="D:\\EV\\backups\\example.txt.bak",
            original_size_bytes=42,
            backup_size_bytes=42,
            sha256="a" * 64,
            original_exists=True,
            success=True,
            message="Backup created successfully",
        )
        result = BackupResult(
            status=BackupStatus.CREATED,
            success=True,
            executed=True,
            original_path="C:\\temp\\example.txt",
            backup_path="D:\\EV\\backups\\example.txt.bak",
            message="Backup created successfully",
            duration_seconds=0.01,
            backup_record=record,
        )

        event = self.store.attach_backup(self.task.task_id, result)

        self.assertEqual(event.event_type, TaskHistoryEventType.BACKUP_RESULT)
        self.assertEqual(event.task_id, self.task.task_id)
        expected_keys = {
            "type",
            "status",
            "success",
            "executed",
            "original_path",
            "backup_path",
            "message",
            "error",
            "started_at",
            "finished_at",
            "duration_seconds",
            "backup_record",
        }
        self.assertEqual(set(event.payload.keys()), expected_keys)
        self.assertEqual(event.payload["status"], "CREATED")
        # bounded nested record: only allow-listed fields, no 'message'/'backup_path'
        self.assertEqual(
            set(event.payload["backup_record"].keys()),
            {"type", "original_size_bytes", "backup_size_bytes", "sha256", "original_exists", "success"},
        )
        self.assertNotIn("message", event.payload["backup_record"])

        stored = self.store.get_events(self.task.task_id)[-1]
        self.assertEqual(stored.payload["backup_record"]["sha256"], "a" * 64)

    def test_attach_backup_without_record_omits_nested(self):
        result = BackupResult(
            status=BackupStatus.FAILED,
            success=False,
            executed=False,
            original_path="C:\\temp\\missing.txt",
            backup_path=None,
            message="Source file does not exist",
            error="FileNotFoundError: Source file does not exist",
            duration_seconds=0.0,
        )
        event = self.store.attach_backup(self.task.task_id, result)
        self.assertNotIn("backup_record", event.payload)
        self.assertEqual(event.payload["status"], "FAILED")
        self.assertEqual(event.payload["error"], "FileNotFoundError: Source file does not exist")

    def test_attach_backup_unknown_task_raises_keyerror(self):
        result = BackupResult(
            status=BackupStatus.CREATED,
            success=True,
            executed=True,
            original_path="C:\\temp\\example.txt",
            backup_path="D:\\EV\\backups\\example.txt.bak",
            message="ok",
            duration_seconds=0.01,
        )
        with self.assertRaises(KeyError):
            self.store.attach_backup("missing-task", result)

    # --- restore ------------------------------------------------------
    def test_attach_restore(self):
        result = RestoreResult(
            status=BackupStatus.RESTORED,
            success=True,
            executed=True,
            original_path="C:\\temp\\example.txt",
            backup_path="D:\\EV\\backups\\example.txt.bak",
            message="File restored successfully",
            duration_seconds=0.02,
            safety_backup_path="D:\\EV\\backups\\example.txt.safety.bak",
        )

        event = self.store.attach_restore(self.task.task_id, result)

        self.assertEqual(event.event_type, TaskHistoryEventType.RESTORE_RESULT)
        self.assertEqual(event.task_id, self.task.task_id)
        self.assertEqual(
            set(event.payload.keys()),
            {
                "type",
                "status",
                "success",
                "executed",
                "original_path",
                "backup_path",
                "message",
                "error",
                "started_at",
                "finished_at",
                "duration_seconds",
                "safety_backup_path",
            },
        )
        self.assertEqual(event.payload["status"], "RESTORED")
        self.assertEqual(
            event.payload["safety_backup_path"],
            "D:\\EV\\backups\\example.txt.safety.bak",
        )

        stored = self.store.get_events(self.task.task_id)[-1]
        self.assertEqual(stored.event_type, TaskHistoryEventType.RESTORE_RESULT)
        self.assertTrue(stored.payload["success"])

    def test_attach_restore_rejects_wrong_type(self):
        with self.assertRaises(TypeError):
            self.store.attach_restore(self.task.task_id, object())


if __name__ == "__main__":
    unittest.main()
