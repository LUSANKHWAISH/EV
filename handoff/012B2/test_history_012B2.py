"""
Unit tests for E.V. persistent task history (Task 012B).
"""

import sqlite3
import tempfile
from contextlib import closing
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from core.history import EVTaskHistoryStore
from core.models import (
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentStepResult,
    AgentTask,
    TaskHistoryEventType,
    TextReadResult,
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


if __name__ == "__main__":
    unittest.main()
