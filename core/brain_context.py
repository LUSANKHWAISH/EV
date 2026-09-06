"""
Bounded Context & Memory Assembly Engine for E.V. Brain (Phase 4 Task 008).

This module provides deterministic, read-only, privacy-preserving construction of
BrainContext instances from application state, task history, and verification metadata.
"""
from __future__ import annotations

import copy
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol, Set, Union, runtime_checkable

from .brain_models import (
    MAX_CONTEXT_TASKS,
    MAX_SHORT_STRING_LENGTH,
    MAX_STRING_LENGTH,
    BrainContext,
)
from .models import AgentAction, AgentStatus, EVState, TaskHistoryRecord

logger = logging.getLogger("ev.brain.context")

# Explicit safety bounds
MAX_SUMMARY_STRING_LENGTH = 500
MAX_KEY_LENGTH = 100
MAX_RECURSION_DEPTH = 5
MAX_COLLECTION_ITEMS = 20
MAX_AGGREGATE_CONTEXT_CHARS = 10000
REDACTION_MARKER = "[REDACTED]"

# Case-insensitive sensitive keys for recursive redaction
SENSITIVE_KEY_SUBSTRINGS: Set[str] = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "authorization",
    "auth",
    "credential",
    "credentials",
    "private_key",
    "client_secret",
    "session_token",
    "cookie",
    "bearer",
}

# Raw and unrestricted fields to strictly exclude from task summaries
EXCLUDED_RAW_FIELDS: Set[str] = {
    "file_contents",
    "content",
    "text_content",
    "raw_bytes",
    "bytes",
    "data",
    "stdout",
    "stderr",
    "output",
    "dump",
    "traceback",
    "env",
    "environment",
    "memory_dump",
}


@runtime_checkable
class HistorySourceProtocol(Protocol):
    """Minimal protocol for dependency-injected history reading."""
    def list_tasks(
        self,
        *,
        limit: int = 50,
        status: Optional[AgentStatus] = None,
        action: Optional[AgentAction] = None,
    ) -> List[Any]:
        ...


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary key name indicates sensitive credentials/secrets."""
    if not isinstance(key, str):
        return False
    norm_key = key.lower().replace("-", "_").replace(" ", "_")
    return any(sub in norm_key for sub in SENSITIVE_KEY_SUBSTRINGS)


def sanitize_data(data: Any, depth: int = 0) -> Any:
    """
    Recursively sanitize data structures, redacting sensitive keys and truncating strings.
    Guarantees no mutation of the original caller objects.
    """
    if depth > MAX_RECURSION_DEPTH:
        return "[TRUNCATED_DEPTH]"

    if isinstance(data, dict):
        sanitized_dict: Dict[str, Any] = {}
        # Bound dictionary item count and sort keys for determinism
        items = list(data.items())[:MAX_COLLECTION_ITEMS]
        for k, v in items:
            key_str = str(k)[:MAX_KEY_LENGTH]
            lower_k = key_str.lower()
            if lower_k in EXCLUDED_RAW_FIELDS:
                continue
            if is_sensitive_key(key_str):
                sanitized_dict[key_str] = REDACTION_MARKER
            else:
                sanitized_dict[key_str] = sanitize_data(v, depth + 1)
        return sanitized_dict

    elif isinstance(data, list):
        sanitized_list: List[Any] = []
        for item in data[:MAX_COLLECTION_ITEMS]:
            sanitized_list.append(sanitize_data(item, depth + 1))
        return sanitized_list

    elif isinstance(data, str):
        # Bound length
        s = data[:MAX_SUMMARY_STRING_LENGTH]
        # Redact bearer token patterns if embedded in string
        lower_s = s.lower()
        if lower_s.startswith("bearer ") or lower_s.startswith("basic "):
            return REDACTION_MARKER
        return s

    elif isinstance(data, (int, float, bool)):
        return data

    elif isinstance(data, datetime):
        return data.isoformat()

    elif data is None:
        return None

    else:
        return str(data)[:MAX_SUMMARY_STRING_LENGTH]


class BrainContextAssembler:
    """
    Deterministic, read-only assembler for BrainContext instances.
    Safely packages bounded runtime metadata, history summaries, and verification state.
    """

    def __init__(self, history_source: Optional[HistorySourceProtocol] = None):
        """
        Initialize the assembler with an optional dependency-injected history source.
        """
        self._history_source = history_source

    def assemble_context(
        self,
        user_input: str,
        current_state: EVState = EVState.IDLE,
        platform: str = "windows",
        available_actions: Optional[List[AgentAction]] = None,
        recent_tasks: Optional[List[Union[TaskHistoryRecord, Dict[str, Any]]]] = None,
        verification_context: Optional[Dict[str, Any]] = None,
        active_awareness: Optional[List[Dict[str, Any]]] = None,
        max_tasks: int = MAX_CONTEXT_TASKS,
    ) -> BrainContext:
        """
        Assemble a validated, bounded, and privacy-safe BrainContext.

        Args:
            user_input: Raw user prompt string.
            current_state: Current EVState of the application.
            platform: Platform name string (e.g. 'windows').
            available_actions: Optional subset of whitelisted AgentAction enums.
            recent_tasks: Optional list of recent tasks (or queries history_source if None).
            verification_context: Optional active verification metadata.
            max_tasks: Maximum task summaries to include (bounded at MAX_CONTEXT_TASKS).

        Returns:
            A strictly bounded BrainContext instance.

        Raises:
            ValueError: On invalid input text, oversized context, or malformed data.
            TypeError: On invalid state or action types.
        """
        # 1. Validate user input
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string")
        if len(user_input) > MAX_STRING_LENGTH:
            raise ValueError(f"user_input exceeds maximum length of {MAX_STRING_LENGTH}")

        # 2. Validate current state
        if not isinstance(current_state, EVState):
            raise TypeError(f"current_state must be an instance of EVState, got {type(current_state)}")

        # 3. Validate platform
        if not isinstance(platform, str) or not platform.strip() or len(platform) > 50:
            raise ValueError("platform must be a non-empty string up to 50 characters")

        # 4. Validate and sort available actions deterministically
        if available_actions is None:
            actions_list = sorted(list(AgentAction), key=lambda a: a.value)
        else:
            if not isinstance(available_actions, list) or not all(isinstance(a, AgentAction) for a in available_actions):
                raise TypeError("available_actions must be a list of AgentAction enum values")
            # Deduplicate and sort deterministically
            actions_list = sorted(list(set(available_actions)), key=lambda a: a.value)

        # 5. Gather and bound recent task summaries
        bounded_max_tasks = min(max(1, max_tasks), MAX_CONTEXT_TASKS)
        raw_tasks = recent_tasks

        if raw_tasks is None and self._history_source is not None:
            try:
                raw_tasks = self._history_source.list_tasks(limit=bounded_max_tasks)
            except Exception as exc:
                logger.warning("Failed to query history source: %s", exc)
                raw_tasks = []

        task_summaries: List[Dict[str, Any]] = []
        if raw_tasks:
            for item in raw_tasks[:bounded_max_tasks]:
                summary = self._extract_task_summary(item)
                if summary:
                    task_summaries.append(summary)

        # 6. Sanitize verification context
        sanitized_verification: Optional[Dict[str, Any]] = None
        if verification_context is not None:
            if not isinstance(verification_context, dict):
                raise TypeError("verification_context must be a dictionary if provided")
            sanitized_verification = sanitize_data(verification_context)

        # 7. Sanitize active awareness context
        sanitized_awareness: Optional[List[Dict[str, Any]]] = None
        if active_awareness is not None:
            if not isinstance(active_awareness, list):
                raise TypeError("active_awareness must be a list of dictionaries if provided")
            sanitized_awareness = [sanitize_data(item) for item in active_awareness[:25]]

        # 8. Construct and validate aggregate size
        context = BrainContext(
            user_input=user_input.strip(),
            current_state=current_state,
            platform=platform.strip(),
            available_actions=actions_list,
            recent_task_summaries=task_summaries,
            verification_context=sanitized_verification,
            active_awareness=sanitized_awareness,
        )

        serialized_length = len(context.model_dump_json())
        if serialized_length > MAX_AGGREGATE_CONTEXT_CHARS:
            raise ValueError(
                f"Serialized context length ({serialized_length}) exceeds maximum limit of {MAX_AGGREGATE_CONTEXT_CHARS}"
            )

        return context

    def _extract_task_summary(self, record: Union[TaskHistoryRecord, Dict[str, Any], Any]) -> Optional[Dict[str, Any]]:
        """
        Extract a bounded, sanitized summary dictionary from a task history record.
        """
        if record is None:
            return None

        # Extract scalar fields based on type
        if isinstance(record, TaskHistoryRecord):
            task_id = record.task_id
            action = record.action.value if hasattr(record.action, "value") else str(record.action)
            status = record.status.value if hasattr(record.status, "value") else str(record.status)
            created_at = record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at)
            parameters = record.parameters or {}
            success = record.success
            error = record.error
        elif isinstance(record, dict):
            task_id = str(record.get("task_id", ""))
            action_raw = record.get("action", "")
            action = action_raw.value if hasattr(action_raw, "value") else str(action_raw)
            status_raw = record.get("status", "")
            status = status_raw.value if hasattr(status_raw, "value") else str(status_raw)
            created_at_raw = record.get("created_at", "")
            created_at = created_at_raw.isoformat() if hasattr(created_at_raw, "isoformat") else str(created_at_raw)
            parameters = record.get("parameters", {})
            success = record.get("success")
            error = record.get("error")
        else:
            task_id = str(getattr(record, "task_id", ""))
            action_raw = getattr(record, "action", "")
            action = action_raw.value if hasattr(action_raw, "value") else str(action_raw)
            status_raw = getattr(record, "status", "")
            status = status_raw.value if hasattr(status_raw, "value") else str(status_raw)
            created_at_raw = getattr(record, "created_at", "")
            created_at = created_at_raw.isoformat() if hasattr(created_at_raw, "isoformat") else str(created_at_raw)
            parameters = getattr(record, "parameters", {})
            success = getattr(record, "success", None)
            error = getattr(record, "error", None)

        if not task_id:
            return None

        # Sanitize parameters (deep-clean secrets and bound sizes)
        sanitized_params = sanitize_data(parameters) if isinstance(parameters, dict) else {}

        summary: Dict[str, Any] = {
            "task_id": task_id[:64],
            "action": action[:50],
            "status": status[:50],
            "created_at": created_at[:50],
            "parameters": sanitized_params,
        }

        if success is not None:
            summary["success"] = bool(success)
        if error:
            summary["error"] = str(error)[:MAX_SHORT_STRING_LENGTH]

        return summary
