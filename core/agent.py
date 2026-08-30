"""
Minimal read-only agent/orchestration layer for E.V.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .models import (
    AgentTask,
    AgentAction,
    AgentStatus,
    AgentStepResult,
    AgentRunResult,
    EVEventType,
)
from .history import EVTaskHistoryStore
from .events import EVEventBus
from tools.processes import find_processes
from tools.network import find_tcp_port
from tools.filesystem import (
    get_file_info,
    list_directory,
    read_text_file,
    find_files,
    search_text,
)

logger = logging.getLogger(__name__)


class EVAgent:
    """Read-only agent that dispatches to approved observation capabilities."""

    def _get_handler(self, action: AgentAction):
        """Return the current approved function for the action."""
        if action == AgentAction.FIND_PROCESS:
            return find_processes
        if action == AgentAction.FIND_TCP_PORT:
            return find_tcp_port
        if action == AgentAction.GET_FILE_INFO:
            return get_file_info
        if action == AgentAction.LIST_DIRECTORY:
            return list_directory
        if action == AgentAction.READ_TEXT_FILE:
            return read_text_file
        if action == AgentAction.FIND_FILES:
            return find_files
        if action == AgentAction.SEARCH_TEXT:
            return search_text
        raise ValueError(f"Unsupported action: {action}")

    def run(self, task: AgentTask) -> AgentRunResult:
        """
        Execute a read-only agent task.
        Returns AgentRunResult with status and optional step details.
        """
        started_at = datetime.now()
        self._history("record_task", task)
        self._history("mark_started", task.task_id, started_at=started_at)
        logger.info(
            "Agent task started: task_id=%s action=%s",
            task.task_id,
            task.action.value,
        )
        self._publish_event(
            event_type=EVEventType.ACTION_STARTED,
            correlation_id=task.task_id,
            message=f"{task.action.value}: started",
            data={"task_id": task.task_id, "action": task.action.value}
        )

        # Validate action is supported via whitelist
        try:
            handler = self._get_handler(task.action)
        except ValueError as ve:
            error_msg = str(ve)
            logger.error("Agent task failed: %s", error_msg)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=error_msg,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=error_msg,
                ),
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=error_msg,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (unsupported)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                }
            )
            self._history("record_run", task, result)
            return result

        # Validate parameters based on action
        validation_error = self._validate_parameters(task.action, task.parameters)
        if validation_error:
            logger.error("Agent task failed: %s", validation_error)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=validation_error,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=validation_error,
                ),
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=validation_error,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (validation)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                }
            )
            self._history("record_run", task, result)
            return result

        # Execute the approved action
        try:
            result = handler(**task.parameters)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            logger.info(
                "Agent task completed: task_id=%s action=%s duration=%.3fs",
                task.task_id,
                task.action.value,
                duration,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.COMPLETED,
                step=AgentStepResult(
                    action=task.action,
                    success=True,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    result=result,
                ),
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=f"{task.action.value}: completed successfully",
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: finished",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": True,
                    "duration_seconds": duration,
                }
            )
            self._history("record_run", task, result)
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent task error: task_id=%s action=%s", task.task_id, task.action.value)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            error_msg = f"{type(exc).__name__}: {exc}"
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=error_msg,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=error_msg,
                ),
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=error_msg,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (exception)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                }
            )
            self._history("record_run", task, result)
            return result

    def _validate_parameters(self, action: AgentAction, params: Dict[str, Any]) -> Optional[str]:
        """Validate required parameters for each action."""
        if action == AgentAction.FIND_PROCESS:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "FIND_PROCESS requires non-empty string 'name'"
        elif action == AgentAction.FIND_TCP_PORT:
            port = params.get("port")
            if not isinstance(port, int):
                return "FIND_TCP_PORT requires integer 'port'"
            if port < 1 or port > 65535:
                return "FIND_TCP_PORT port must be between 1 and 65535"
        elif action in (AgentAction.GET_FILE_INFO, AgentAction.LIST_DIRECTORY, AgentAction.READ_TEXT_FILE):
            path = params.get("path")
            if not path or not isinstance(path, str):
                return f"{action.value} requires string 'path'"
        elif action == AgentAction.READ_TEXT_FILE:
            max_bytes = params.get("max_bytes")
            if max_bytes is not None:
                if not isinstance(max_bytes, int) or max_bytes <= 0:
                    return "READ_TEXT_FILE max_bytes must be positive integer if provided"
        elif action == AgentAction.FIND_FILES:
            root = params.get("root")
            pattern = params.get("pattern")
            if not root or not isinstance(root, str):
                return "FIND_FILES requires string 'root'"
            if not pattern or not isinstance(pattern, str):
                return "FIND_FILES requires string 'pattern'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or max_results <= 0:
                    return "FIND_FILES max_results must be positive integer if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "FIND_FILES exclude_dirs must be list of strings if provided"
        elif action == AgentAction.SEARCH_TEXT:
            root_or_file = params.get("root_or_file")
            text = params.get("text")
            if not root_or_file or not isinstance(root_or_file, str):
                return "SEARCH_TEXT requires string 'root_or_file'"
            if not text or not isinstance(text, str) or not text.strip():
                return "SEARCH_TEXT requires non-empty string 'text'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or max_results <= 0:
                    return "SEARCH_TEXT max_results must be positive integer if provided"
            case_insensitive = params.get("case_insensitive")
            if case_insensitive is not None and not isinstance(case_insensitive, bool):
                return "SEARCH_TEXT case_insensitive must be boolean if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "SEARCH_TEXT exclude_dirs must be list of strings if provided"
        return None

    def __init__(
        self,
        history_store: Optional[EVTaskHistoryStore] = None,
        event_bus: Optional[EVEventBus] = None,
    ):
        self._history_store = history_store
        self._event_bus = event_bus

    def _publish_event(
        self,
        event_type: EVEventType,
        correlation_id: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                event_type=event_type,
                source="agent",
                correlation_id=correlation_id,
                message=message,
                data=data,
            )
        except Exception:
            logger.exception("Agent telemetry publication failed")

    def _history(self, method, *args, **kwargs):
        if self._history_store is None:
            return
        try:
            getattr(self._history_store, method)(*args, **kwargs)
        except Exception:
            logger.exception("Agent task history persistence failed")
