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
)
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
        logger.info(
            "Agent task started: task_id=%s action=%s",
            task.task_id,
            task.action.value,
        )

        # Validate action is supported via whitelist
        try:
            handler = self._get_handler(task.action)
        except ValueError as ve:
            error_msg = str(ve)
            logger.error("Agent task failed: %s", error_msg)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            return AgentRunResult(
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

        # Validate parameters based on action
        validation_error = self._validate_parameters(task.action, task.parameters)
        if validation_error:
            logger.error("Agent task failed: %s", validation_error)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            return AgentRunResult(
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
            return AgentRunResult(
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
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent task error: task_id=%s action=%s", task.task_id, task.action.value)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            error_msg = f"{type(exc).__name__}: {exc}"
            return AgentRunResult(
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