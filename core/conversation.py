"""
Multi-Turn Conversational & Clarification Context Store for E.V. (Phase 5 Task 006).

This module provides thread-safe, bounded, in-memory management of multi-turn
dialogue history and pending clarification requests.

Security Invariants:
1. Conversational Context != Authorization.
2. Clarification responses supply missing parameters but never bypass EVRiskEngine
   or user approval.
3. Pending context expires after PENDING_CONTEXT_TTL and is never persisted across
   process restarts.
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .memory import EVConversationMemoryStore

logger = logging.getLogger("ev.conversation")

# Configurable architectural limits
MAX_TURNS: int = 10
PENDING_CONTEXT_TTL: float = 300.0  # 5 minutes
MAX_TEXT_LENGTH: int = 1000
CANCELLATION_KEYWORDS = frozenset({"cancel", "stop", "abort", "nevermind", "exit", "quit"})


@dataclass
class ConversationTurn:
    """Represents a single conversational turn in the multi-turn session."""
    user_message: str
    assistant_message: Optional[str] = None
    turn_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PendingClarificationContext:
    """Represents a pending request awaiting user clarification."""
    original_request: str
    clarification_prompt: str
    context_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    created_at: float = field(default_factory=time.monotonic)
    ttl_seconds: float = PENDING_CONTEXT_TTL
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self, current_time: Optional[float] = None) -> bool:
        """Check if this pending clarification has exceeded its TTL."""
        now = current_time if current_time is not None else time.monotonic()
        return (now - self.created_at) > self.ttl_seconds


class EVConversationContextStore:
    """
    Thread-safe, bounded in-memory store for multi-turn conversational history
    and active pending clarification contexts. Optionally backed by EVConversationMemoryStore.
    """

    def __init__(
        self,
        max_turns: int = MAX_TURNS,
        pending_ttl: float = PENDING_CONTEXT_TTL,
        max_text_length: int = MAX_TEXT_LENGTH,
        memory_store: Optional[EVConversationMemoryStore] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self._max_turns = max(1, max_turns)
        self._pending_ttl = max(1.0, pending_ttl)
        self._max_text_length = max_text_length
        self._lock = threading.RLock()
        self._turns: List[ConversationTurn] = []
        self._pending_clarification: Optional[PendingClarificationContext] = None
        self._memory_store: Optional[EVConversationMemoryStore] = memory_store
        self._session_id: Optional[str] = None

        if self._memory_store is not None:
            try:
                if session_id:
                    self._session_id = session_id
                else:
                    self._session_id = self._memory_store.get_or_create_active_session()
                persisted_turns = self._memory_store.get_recent_turns(
                    self._session_id, limit=self._max_turns
                )
                for pt in persisted_turns:
                    dt = None
                    if "timestamp" in pt and pt["timestamp"]:
                        try:
                            dt = datetime.fromisoformat(pt["timestamp"])
                        except Exception:
                            dt = None
                    turn = ConversationTurn(
                        turn_id=pt.get("turn_id") or str(uuid.uuid4())[:8],
                        user_message=pt.get("user_message", ""),
                        assistant_message=pt.get("assistant_message"),
                        timestamp=dt or datetime.now(),
                        metadata=pt.get("metadata") or {},
                    )
                    self._turns.append(turn)
            except Exception as exc:
                logger.warning("Failed to initialize conversation context with memory store: %s", exc)

    @property
    def session_id(self) -> Optional[str]:
        """Return the active persistent session ID, if any."""
        return self._session_id

    @property
    def memory_store(self) -> Optional[EVConversationMemoryStore]:
        """Return the backing persistent memory store, if any."""
        return self._memory_store

    def start_new_session(self, title: Optional[str] = None) -> Optional[str]:
        """Start a new session in persistent storage and reset active in-memory turns."""
        with self._lock:
            self._turns.clear()
            self._pending_clarification = None
            if self._memory_store is not None:
                try:
                    self._session_id = self._memory_store.create_session(title=title)
                    return self._session_id
                except Exception as exc:
                    logger.warning("Failed to create new session in memory store: %s", exc)
            return None

    def add_turn(
        self,
        user_message: str,
        assistant_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ConversationTurn:
        """
        Record a completed or in-progress conversational turn, maintaining bounded capacity.
        """
        bounded_user = (user_message or "")[:self._max_text_length]
        bounded_assistant = (assistant_message[:self._max_text_length]) if assistant_message else None

        turn = ConversationTurn(
            user_message=bounded_user,
            assistant_message=bounded_assistant,
            metadata=dict(metadata) if metadata else {},
        )

        with self._lock:
            self._turns.append(turn)
            if len(self._turns) > self._max_turns:
                self._turns = self._turns[-self._max_turns:]

            if self._memory_store is not None and self._session_id is not None:
                try:
                    self._memory_store.record_turn(
                        session_id=self._session_id,
                        user_message=turn.user_message,
                        assistant_message=turn.assistant_message,
                        turn_id=turn.turn_id,
                        timestamp=turn.timestamp,
                        metadata=turn.metadata,
                    )
                except Exception as exc:
                    logger.warning("Failed to persist turn to memory store: %s", exc)

            return turn

    def get_recent_turns(self, limit: Optional[int] = None) -> List[ConversationTurn]:
        """Return a copy of recent conversational turns."""
        with self._lock:
            if limit is not None and limit > 0:
                return list(self._turns[-limit:])
            return list(self._turns)

    def set_pending_clarification(
        self,
        original_request: str,
        clarification_prompt: str,
        context_id: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PendingClarificationContext:
        """
        Set or supersede the active pending clarification context.
        """
        bounded_req = (original_request or "")[:self._max_text_length]
        bounded_prompt = (clarification_prompt or "")[:self._max_text_length]
        ttl = ttl_seconds if ttl_seconds is not None and ttl_seconds > 0 else self._pending_ttl

        ctx = PendingClarificationContext(
            original_request=bounded_req,
            clarification_prompt=bounded_prompt,
            context_id=context_id or str(uuid.uuid4())[:8],
            created_at=time.monotonic(),
            ttl_seconds=ttl,
            metadata=dict(metadata) if metadata else {},
        )

        with self._lock:
            if self._pending_clarification is not None:
                logger.debug(
                    "Superseding existing pending clarification %s with new context %s",
                    self._pending_clarification.context_id,
                    ctx.context_id,
                )
            self._pending_clarification = ctx
            return ctx

    def get_pending_clarification(
        self,
        current_time: Optional[float] = None,
    ) -> Optional[PendingClarificationContext]:
        """
        Retrieve the active pending clarification context if not expired.
        Automatically purges expired context.
        """
        with self._lock:
            if self._pending_clarification is None:
                return None

            if self._pending_clarification.is_expired(current_time):
                logger.info(
                    "Pending clarification %s expired (TTL=%.1fs); discarding",
                    self._pending_clarification.context_id,
                    self._pending_clarification.ttl_seconds,
                )
                self._pending_clarification = None
                return None

            return self._pending_clarification

    def clear_pending_clarification(self) -> None:
        """Clear the active pending clarification context."""
        with self._lock:
            self._pending_clarification = None

    def has_pending_clarification(self, current_time: Optional[float] = None) -> bool:
        """Check if an unexpired pending clarification context currently exists."""
        return self.get_pending_clarification(current_time) is not None

    def is_cancellation(self, user_input: str) -> bool:
        """Check if the user input matches standard cancellation keywords."""
        if not user_input or not isinstance(user_input, str):
            return False
        return user_input.strip().lower() in CANCELLATION_KEYWORDS

    def clear_all(self) -> None:
        """Clear all conversation history and pending clarifications."""
        with self._lock:
            self._turns.clear()
            self._pending_clarification = None
