"""
Durable local task history for E.V.

Task 012B provides the persistence foundation only. The store has no import-time
side effects and is not automatically attached to EVAgent yet.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel

from .models import (
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    TaskHistoryEventRecord,
    TaskHistoryEventType,
    TaskHistoryRecord,
)


DEFAULT_HISTORY_DB_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "ev_history.sqlite3"
)

_SCHEMA_VERSION = 1


class EVTaskHistoryStore:
    """Thread-safe SQLite-backed persistent task history."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_HISTORY_DB_PATH
        self.db_path = self.db_path.expanduser().resolve()
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _initialize(self) -> None:
        with self._lock:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as connection:
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])

                if version > _SCHEMA_VERSION:
                    raise RuntimeError(
                        f"Task history database schema {version} is newer than "
                        f"supported schema {_SCHEMA_VERSION}"
                    )

                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS task_history (
                        task_id TEXT PRIMARY KEY,
                        action TEXT NOT NULL,
                        parameters_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        started_at TEXT,
                        finished_at TEXT,
                        duration_seconds REAL,
                        success INTEGER,
                        result_summary_json TEXT,
                        error TEXT,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS task_history_events (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        task_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(task_id)
                            REFERENCES task_history(task_id)
                            ON DELETE CASCADE
                    );

                    CREATE INDEX IF NOT EXISTS idx_task_history_created_at
                        ON task_history(created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_task_history_status
                        ON task_history(status);

                    CREATE INDEX IF NOT EXISTS idx_task_history_action
                        ON task_history(action);

                    CREATE INDEX IF NOT EXISTS idx_task_history_events_task
                        ON task_history_events(task_id, event_id);
                    """
                )

                if version == 0:
                    connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                connection.commit()

    @staticmethod
    def _to_jsonable(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, BaseModel):
            if hasattr(value, "model_dump"):
                return EVTaskHistoryStore._to_jsonable(value.model_dump())
            return EVTaskHistoryStore._to_jsonable(value.dict())
        if isinstance(value, dict):
            return {
                str(key): EVTaskHistoryStore._to_jsonable(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [EVTaskHistoryStore._to_jsonable(item) for item in value]
        return repr(value)

    @classmethod
    def _json_dumps(cls, value: Any) -> str:
        return json.dumps(
            cls._to_jsonable(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @staticmethod
    def _json_loads(value: Optional[str]) -> Any:
        if value is None:
            return None
        return json.loads(value)

    @classmethod
    def summarize_result(cls, result: Any) -> Optional[dict]:
        """
        Create a deliberately bounded result summary.

        Full arbitrary tool results are not persisted. This avoids turning the
        history database into a copy of file contents, search snippets, or other
        potentially large/sensitive evidence.
        """
        if result is None:
            return None

        if isinstance(result, BaseModel):
            if hasattr(result, "model_dump"):
                data = result.model_dump()
            else:
                data = result.dict()

            summary = {"type": type(result).__name__}
            allowed_fields = (
                "path",
                "name",
                "success",
                "exists",
                "is_file",
                "is_directory",
                "size_bytes",
                "truncated",
                "encoding",
                "pid",
                "local_port",
                "remote_port",
                "state",
                "status",
                "error",
            )
            for field in allowed_fields:
                if field in data:
                    summary[field] = cls._to_jsonable(data[field])
            return summary

        if isinstance(result, (list, tuple, set)):
            item_types = sorted({type(item).__name__ for item in result})
            return {
                "type": type(result).__name__,
                "count": len(result),
                "item_types": item_types[:10],
            }

        if isinstance(result, dict):
            keys = sorted(str(key) for key in result.keys())
            return {
                "type": "dict",
                "key_count": len(keys),
                "keys": keys[:20],
            }

        if isinstance(result, str):
            return {
                "type": "str",
                "length": len(result),
            }

        if isinstance(result, bytes):
            return {
                "type": "bytes",
                "length": len(result),
            }

        if isinstance(result, (int, float, bool)):
            return {
                "type": type(result).__name__,
                "value": result,
            }

        return {"type": type(result).__name__}

    def record_task(self, task: AgentTask) -> TaskHistoryRecord:
        """Create a PENDING task record, idempotently for the same task definition."""
        parameters_json = self._json_dumps(task.parameters)
        now = datetime.now()

        with self._lock:
            with closing(self._connect()) as connection:
                existing = connection.execute(
                    """
                    SELECT action, parameters_json, created_at
                    FROM task_history
                    WHERE task_id = ?
                    """,
                    (task.task_id,),
                ).fetchone()

                if existing is not None:
                    if (
                        existing["action"] != task.action.value
                        or existing["parameters_json"] != parameters_json
                        or existing["created_at"] != task.created_at.isoformat()
                    ):
                        raise ValueError(
                            f"task_id '{task.task_id}' already exists with a "
                            "different task definition"
                        )
                else:
                    connection.execute(
                        """
                        INSERT INTO task_history (
                            task_id,
                            action,
                            parameters_json,
                            created_at,
                            status,
                            updated_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            task.task_id,
                            task.action.value,
                            parameters_json,
                            task.created_at.isoformat(),
                            AgentStatus.PENDING.value,
                            now.isoformat(),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO task_history_events (
                            task_id,
                            event_type,
                            payload_json,
                            created_at
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            task.task_id,
                            TaskHistoryEventType.TASK_CREATED.value,
                            self._json_dumps(
                                {
                                    "action": task.action.value,
                                    "created_at": task.created_at,
                                }
                            ),
                            now.isoformat(),
                        ),
                    )
                    connection.commit()

        record = self.get_task(task.task_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to persist task '{task.task_id}'")
        return record

    def mark_started(
        self,
        task_id: str,
        *,
        started_at: Optional[datetime] = None,
    ) -> TaskHistoryRecord:
        """Mark an existing task RUNNING and append a TASK_STARTED event."""
        started_at = started_at or datetime.now()
        now = datetime.now()

        with self._lock:
            with closing(self._connect()) as connection:
                self._require_task(connection, task_id)
                connection.execute(
                    """
                    UPDATE task_history
                    SET
                        status = ?,
                        started_at = COALESCE(started_at, ?),
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (
                        AgentStatus.RUNNING.value,
                        started_at.isoformat(),
                        now.isoformat(),
                        task_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO task_history_events (
                        task_id,
                        event_type,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        TaskHistoryEventType.TASK_STARTED.value,
                        self._json_dumps({"started_at": started_at}),
                        now.isoformat(),
                    ),
                )
                connection.commit()

        record = self.get_task(task_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to update task '{task_id}'")
        return record

    def record_run(
        self,
        task: AgentTask,
        run_result: AgentRunResult,
    ) -> TaskHistoryRecord:
        """Persist the final AgentRunResult for a task."""
        if task.task_id != run_result.task_id:
            raise ValueError("AgentTask.task_id must match AgentRunResult.task_id")

        self.record_task(task)

        step = run_result.step
        started_at = step.started_at if step is not None else None
        finished_at = step.finished_at if step is not None else datetime.now()
        duration_seconds = step.duration_seconds if step is not None else None
        result_summary = (
            self.summarize_result(step.result)
            if step is not None
            else None
        )
        success = (
            run_result.status == AgentStatus.COMPLETED
            and (step is None or step.success)
        )
        error = run_result.error or (step.error if step is not None else None)
        event_type = (
            TaskHistoryEventType.TASK_COMPLETED
            if run_result.status == AgentStatus.COMPLETED
            else TaskHistoryEventType.TASK_FAILED
        )
        now = datetime.now()

        with self._lock:
            with closing(self._connect()) as connection:
                self._require_task(connection, task.task_id)
                connection.execute(
                    """
                    UPDATE task_history
                    SET
                        status = ?,
                        started_at = COALESCE(started_at, ?),
                        finished_at = ?,
                        duration_seconds = ?,
                        success = ?,
                        result_summary_json = ?,
                        error = ?,
                        updated_at = ?
                    WHERE task_id = ?
                    """,
                    (
                        run_result.status.value,
                        started_at.isoformat() if started_at is not None else None,
                        finished_at.isoformat(),
                        duration_seconds,
                        1 if success else 0,
                        self._json_dumps(result_summary)
                        if result_summary is not None
                        else None,
                        error,
                        now.isoformat(),
                        task.task_id,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO task_history_events (
                        task_id,
                        event_type,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        task.task_id,
                        event_type.value,
                        self._json_dumps(
                            {
                                "status": run_result.status.value,
                                "success": success,
                                "duration_seconds": duration_seconds,
                                "error": error,
                            }
                        ),
                        now.isoformat(),
                    ),
                )
                connection.commit()

        record = self.get_task(task.task_id)
        if record is None:  # pragma: no cover - defensive
            raise RuntimeError(f"Failed to persist run for task '{task.task_id}'")
        return record

    def append_event(
        self,
        task_id: str,
        event_type: TaskHistoryEventType,
        payload: Optional[dict] = None,
        *,
        created_at: Optional[datetime] = None,
    ) -> TaskHistoryEventRecord:
        """
        Append an explicit structured event to an existing task.

        This is the extension point for later verification/risk/backup/recovery
        integration without changing the base task table schema.
        """
        if not isinstance(event_type, TaskHistoryEventType):
            raise TypeError("event_type must be TaskHistoryEventType")

        created_at = created_at or datetime.now()
        payload = payload or {}

        with self._lock:
            with closing(self._connect()) as connection:
                self._require_task(connection, task_id)
                cursor = connection.execute(
                    """
                    INSERT INTO task_history_events (
                        task_id,
                        event_type,
                        payload_json,
                        created_at
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        event_type.value,
                        self._json_dumps(payload),
                        created_at.isoformat(),
                    ),
                )
                event_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE task_history
                    SET updated_at = ?
                    WHERE task_id = ?
                    """,
                    (datetime.now().isoformat(), task_id),
                )
                connection.commit()

        return TaskHistoryEventRecord(
            event_id=event_id,
            task_id=task_id,
            event_type=event_type,
            payload=self._to_jsonable(payload),
            created_at=created_at,
        )

    def get_task(self, task_id: str) -> Optional[TaskHistoryRecord]:
        with self._lock:
            with closing(self._connect()) as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM task_history
                    WHERE task_id = ?
                    """,
                    (task_id,),
                ).fetchone()

        return self._row_to_record(row) if row is not None else None

    def list_tasks(
        self,
        *,
        limit: int = 50,
        status: Optional[AgentStatus] = None,
        action: Optional[AgentAction] = None,
    ) -> List[TaskHistoryRecord]:
        if limit < 1:
            raise ValueError("limit must be >= 1")

        clauses = []
        values: List[Any] = []

        if status is not None:
            if not isinstance(status, AgentStatus):
                raise TypeError("status must be AgentStatus or None")
            clauses.append("status = ?")
            values.append(status.value)

        if action is not None:
            if not isinstance(action, AgentAction):
                raise TypeError("action must be AgentAction or None")
            clauses.append("action = ?")
            values.append(action.value)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        values.append(limit)

        with self._lock:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM task_history
                    {where_sql}
                    ORDER BY created_at DESC, task_id DESC
                    LIMIT ?
                    """,
                    values,
                ).fetchall()

        return [self._row_to_record(row) for row in rows]

    def get_events(
        self,
        task_id: str,
        *,
        limit: Optional[int] = None,
    ) -> List[TaskHistoryEventRecord]:
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1 or None")

        with self._lock:
            with closing(self._connect()) as connection:
                self._require_task(connection, task_id)

                if limit is None:
                    rows = connection.execute(
                        """
                        SELECT *
                        FROM task_history_events
                        WHERE task_id = ?
                        ORDER BY event_id ASC
                        """,
                        (task_id,),
                    ).fetchall()
                else:
                    rows = connection.execute(
                        """
                        SELECT *
                        FROM (
                            SELECT *
                            FROM task_history_events
                            WHERE task_id = ?
                            ORDER BY event_id DESC
                            LIMIT ?
                        )
                        ORDER BY event_id ASC
                        """,
                        (task_id, limit),
                    ).fetchall()

        return [
            TaskHistoryEventRecord(
                event_id=int(row["event_id"]),
                task_id=row["task_id"],
                event_type=TaskHistoryEventType(row["event_type"]),
                payload=self._json_loads(row["payload_json"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _require_task(
        connection: sqlite3.Connection,
        task_id: str,
    ) -> None:
        row = connection.execute(
            "SELECT 1 FROM task_history WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown task_id: {task_id}")

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row) -> TaskHistoryRecord:
        return TaskHistoryRecord(
            task_id=row["task_id"],
            action=AgentAction(row["action"]),
            parameters=cls._json_loads(row["parameters_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            status=AgentStatus(row["status"]),
            started_at=(
                datetime.fromisoformat(row["started_at"])
                if row["started_at"] is not None
                else None
            ),
            finished_at=(
                datetime.fromisoformat(row["finished_at"])
                if row["finished_at"] is not None
                else None
            ),
            duration_seconds=row["duration_seconds"],
            success=(
                bool(row["success"])
                if row["success"] is not None
                else None
            ),
            result_summary=cls._json_loads(row["result_summary_json"]),
            error=row["error"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
