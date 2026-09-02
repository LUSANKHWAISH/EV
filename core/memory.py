"""
Durable local conversation memory and session profile store for E.V. (Phase 6 Task 011).

Provides bounded, thread-safe SQLite persistence for:
1. Multi-turn dialogue sessions and completed turns
2. User profile and preference key-values
3. Environmental and system facts
4. Deterministic secret/credential sanitization

Security Invariants:
1. Memory != Authorization: Stored context never authorizes actions or bypasses EVRiskEngine.
2. Ephemeral Isolation: Active approvals, cancellations, and pending clarifications are NEVER persisted.
3. Secret Redaction: Passwords, tokens, API keys, and private keys are redacted to [REDACTED] before persistence.
4. Bounded Storage: Max 100 turns per session, max 50 sessions, max 1,000 chars per message.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("ev.memory")

DEFAULT_MEMORY_DB_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "ev_memory.sqlite3"
)

_SCHEMA_VERSION = 1

# Explicit safety and capacity bounds
MAX_MESSAGE_LENGTH: int = 1000
MAX_METADATA_LENGTH: int = 5000
MAX_TURNS_PER_SESSION: int = 100
MAX_STORED_SESSIONS: int = 50
MAX_PREFERENCE_KEYS: int = 200
MAX_PROFILE_KEYS: int = 50
MAX_PROFILE_VALUE_LENGTH: int = 500
MAX_ENVIRONMENT_FACTS: int = 200
DEFAULT_FACT_TTL_DAYS: int = 90
SESSION_INACTIVITY_HOURS: float = 2.0

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

# Credential regex patterns for string-level redaction
REDACTION_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE), "[REDACTED]"),
    (re.compile(r"AIzaSy[a-zA-Z0-9_\-]{30,}", re.IGNORECASE), "[REDACTED]"),
    (re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z ]+)?PRIVATE KEY-----"), "[REDACTED]"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[a-zA-Z0-9_\-]{10,}\.eyJ[a-zA-Z0-9_\-]{10,}\.[a-zA-Z0-9_\-]{10,}", re.IGNORECASE), "[REDACTED]"),
]


def sanitize_text(text: Optional[str]) -> str:
    """
    Sanitize text by replacing detected API keys, bearer tokens, and private keys.
    Truncates text to MAX_MESSAGE_LENGTH.
    """
    if not text or not isinstance(text, str):
        return ""
    sanitized = text
    for pattern, replacement in REDACTION_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized[:MAX_MESSAGE_LENGTH]


def sanitize_metadata(data: Any, depth: int = 0) -> Any:
    """
    Recursively sanitize dictionaries, lists, and values.
    Redacts any key containing sensitive substrings and scrubs regex patterns from string values.
    """
    if depth > 5:
        return "[MAX_DEPTH]"
    if data is None or isinstance(data, (int, float, bool)):
        return data
    if isinstance(data, str):
        return sanitize_text(data)
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            key_str = str(k)
            lower_k = key_str.lower()
            if any(sub in lower_k for sub in SENSITIVE_KEY_SUBSTRINGS):
                cleaned[key_str] = "[REDACTED]"
            else:
                cleaned[key_str] = sanitize_metadata(v, depth + 1)
        return cleaned
    if isinstance(data, (list, tuple, set)):
        return [sanitize_metadata(item, depth + 1) for item in data]
    return sanitize_text(str(data))


class EVConversationMemoryStore:
    """
    Thread-safe, durable SQLite conversation memory and session profile store.
    Uses Write-Ahead Logging (WAL) and short-lived connections.
    """

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_MEMORY_DB_PATH
        self.db_path = self.db_path.expanduser().resolve()
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        """Create a fresh SQLite connection with WAL mode and foreign keys enabled."""
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=5.0,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        """Initialize SQLite database tables and indexes idempotently."""
        with self._lock:
            try:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
                with closing(self._connect()) as conn:
                    version_row = conn.execute("PRAGMA user_version").fetchone()
                    version = int(version_row[0]) if version_row else 0

                    if version > _SCHEMA_VERSION:
                        raise RuntimeError(
                            f"Memory database schema version {version} is newer than "
                            f"supported schema {_SCHEMA_VERSION}"
                        )

                    conn.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS sessions (
                            session_id TEXT PRIMARY KEY,
                            title TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            metadata_json TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS conversation_turns (
                            turn_id TEXT PRIMARY KEY,
                            session_id TEXT NOT NULL,
                            timestamp TEXT NOT NULL,
                            user_message TEXT NOT NULL,
                            assistant_message TEXT,
                            metadata_json TEXT NOT NULL,
                            FOREIGN KEY(session_id)
                                REFERENCES sessions(session_id)
                                ON DELETE CASCADE
                        );

                        CREATE TABLE IF NOT EXISTS user_preferences (
                            key TEXT PRIMARY KEY,
                            value_json TEXT NOT NULL,
                            category TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS user_profile (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL,
                            updated_at TEXT NOT NULL
                        );

                        CREATE TABLE IF NOT EXISTS environment_facts (
                            fact_key TEXT PRIMARY KEY,
                            fact_value TEXT NOT NULL,
                            topic TEXT NOT NULL,
                            source TEXT NOT NULL,
                            created_at TEXT NOT NULL,
                            expires_at TEXT,
                            metadata_json TEXT NOT NULL
                        );

                        CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                            ON sessions(updated_at DESC);

                        CREATE INDEX IF NOT EXISTS idx_turns_session_timestamp
                            ON conversation_turns(session_id, timestamp ASC);

                        CREATE INDEX IF NOT EXISTS idx_env_facts_topic
                            ON environment_facts(topic);

                        CREATE INDEX IF NOT EXISTS idx_env_facts_expires_at
                            ON environment_facts(expires_at);
                        """
                    )

                    if version == 0:
                        conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
                    conn.commit()
            except Exception as exc:
                logger.error("Failed to initialize EVConversationMemoryStore at %s: %s", self.db_path, exc)
                raise

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------

    def create_session(
        self,
        session_id: Optional[str] = None,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new persistent dialogue session, enforcing global session bounds.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        sid = session_id or f"sess_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        stitle = sanitize_text(title or f"Session {sid}")[:100]
        meta = json.dumps(sanitize_metadata(metadata or {}))[:MAX_METADATA_LENGTH]

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    # Enforce global session limit: delete oldest session(s)
                    count_row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
                    current_count = count_row[0] if count_row else 0
                    if current_count >= MAX_STORED_SESSIONS:
                        excess = (current_count - MAX_STORED_SESSIONS) + 1
                        conn.execute(
                            f"""
                            DELETE FROM sessions WHERE session_id IN (
                                SELECT session_id FROM sessions
                                ORDER BY updated_at ASC LIMIT {excess}
                            )
                            """
                        )

                    conn.execute(
                        """
                        INSERT INTO sessions (session_id, title, created_at, updated_at, metadata_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (sid, stitle, now_iso, now_iso, meta),
                    )
                    conn.commit()
                    logger.debug("Created session %s", sid)
                    return sid
            except Exception as exc:
                logger.warning("Failed to create session %s in memory store: %s", sid, exc)
                return sid

    def get_or_create_active_session(
        self,
        inactivity_hours: float = SESSION_INACTIVITY_HOURS,
    ) -> str:
        """
        Retrieve the latest session if active within inactivity_hours; otherwise create a new one.
        """
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        "SELECT session_id, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 1"
                    ).fetchone()
                    if row:
                        last_updated_str = row["updated_at"]
                        try:
                            last_updated = datetime.fromisoformat(last_updated_str)
                            # Handle timezone awareness
                            if last_updated.tzinfo is None:
                                last_updated = last_updated.replace(tzinfo=timezone.utc)
                            now = datetime.now(timezone.utc)
                            if (now - last_updated) < timedelta(hours=inactivity_hours):
                                return str(row["session_id"])
                        except Exception:
                            pass
            except Exception as exc:
                logger.warning("Error inspecting active session: %s", exc)

        return self.create_session()

    def touch_session(self, session_id: str) -> None:
        """Update the updated_at timestamp of a session."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    conn.execute(
                        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                        (now_iso, session_id),
                    )
                    conn.commit()
            except Exception as exc:
                logger.debug("Failed to touch session %s: %s", session_id, exc)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session record by session_id."""
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        "SELECT * FROM sessions WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    if not row:
                        return None
                    return {
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "metadata": json.loads(row["metadata_json"]),
                    }
            except Exception as exc:
                logger.warning("Failed to fetch session %s: %s", session_id, exc)
                return None

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """List recent sessions ordered by updated_at descending."""
        bounded_limit = min(max(1, limit), MAX_STORED_SESSIONS)
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    cursor = conn.execute(
                        "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
                        (bounded_limit,),
                    )
                    results = []
                    for row in cursor.fetchall():
                        results.append({
                            "session_id": row["session_id"],
                            "title": row["title"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                            "metadata": json.loads(row["metadata_json"]),
                        })
                    return results
            except Exception as exc:
                logger.warning("Failed to list sessions: %s", exc)
                return []

    # -------------------------------------------------------------------------
    # Conversation Turns
    # -------------------------------------------------------------------------

    def record_turn(
        self,
        session_id: str,
        user_message: str,
        assistant_message: Optional[str] = None,
        turn_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Record a completed conversation turn for a session.
        Enforces MAX_TURNS_PER_SESSION and message bounds, redacting any secrets.
        """
        tid = turn_id or str(uuid.uuid4())[:8]
        ts = (timestamp or datetime.now(timezone.utc)).isoformat()
        sanitized_user = sanitize_text(user_message)
        sanitized_assistant = sanitize_text(assistant_message) if assistant_message else None
        meta_json = json.dumps(sanitize_metadata(metadata or {}))[:MAX_METADATA_LENGTH]

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    # Ensure session exists
                    sess_row = conn.execute(
                        "SELECT session_id FROM sessions WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    if not sess_row:
                        self.create_session(session_id=session_id)

                    # Enforce per-session turn limit: delete oldest turns
                    count_row = conn.execute(
                        "SELECT COUNT(*) FROM conversation_turns WHERE session_id = ?",
                        (session_id,),
                    ).fetchone()
                    current_count = count_row[0] if count_row else 0
                    if current_count >= MAX_TURNS_PER_SESSION:
                        excess = (current_count - MAX_TURNS_PER_SESSION) + 1
                        conn.execute(
                            f"""
                            DELETE FROM conversation_turns WHERE turn_id IN (
                                SELECT turn_id FROM conversation_turns
                                WHERE session_id = ?
                                ORDER BY timestamp ASC LIMIT {excess}
                            )
                            """,
                            (session_id,),
                        )

                    conn.execute(
                        """
                        INSERT INTO conversation_turns
                        (turn_id, session_id, timestamp, user_message, assistant_message, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (tid, session_id, ts, sanitized_user, sanitized_assistant, meta_json),
                    )
                    # Update session updated_at
                    conn.execute(
                        "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                        (ts, session_id),
                    )
                    conn.commit()
                    return tid
            except Exception as exc:
                logger.warning("Failed to record turn %s for session %s: %s", tid, session_id, exc)
                return tid

    def get_recent_turns(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve recent turns for a session in chronological order.
        """
        bounded_limit = min(max(1, limit), MAX_TURNS_PER_SESSION)
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    cursor = conn.execute(
                        """
                        SELECT * FROM (
                            SELECT * FROM conversation_turns
                            WHERE session_id = ?
                            ORDER BY timestamp DESC LIMIT ?
                        ) ORDER BY timestamp ASC
                        """,
                        (session_id, bounded_limit),
                    )
                    turns = []
                    for row in cursor.fetchall():
                        turns.append({
                            "turn_id": row["turn_id"],
                            "session_id": row["session_id"],
                            "timestamp": row["timestamp"],
                            "user_message": row["user_message"],
                            "assistant_message": row["assistant_message"],
                            "metadata": json.loads(row["metadata_json"]),
                        })
                    return turns
            except Exception as exc:
                logger.warning("Failed to get turns for session %s: %s", session_id, exc)
                return []

    # -------------------------------------------------------------------------
    # User Preferences
    # -------------------------------------------------------------------------

    def set_preference(
        self,
        key: str,
        value: Any,
        category: str = "general",
    ) -> bool:
        """
        Persist a user preference key-value pair, bounded to MAX_PREFERENCE_KEYS.
        """
        clean_key = sanitize_text(str(key))[:100]
        if not clean_key:
            return False
        clean_category = sanitize_text(str(category))[:50] or "general"
        sanitized_val = sanitize_metadata(value)
        val_json = json.dumps(sanitized_val)[:MAX_METADATA_LENGTH]
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    count_row = conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()
                    count = count_row[0] if count_row else 0
                    if count >= MAX_PREFERENCE_KEYS:
                        # Check if updating existing key
                        exists = conn.execute(
                            "SELECT 1 FROM user_preferences WHERE key = ?", (clean_key,)
                        ).fetchone()
                        if not exists:
                            logger.warning("Max preference keys reached (%d); cannot add key %s", MAX_PREFERENCE_KEYS, clean_key)
                            return False

                    conn.execute(
                        """
                        INSERT INTO user_preferences (key, value_json, category, updated_at)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            value_json = excluded.value_json,
                            category = excluded.category,
                            updated_at = excluded.updated_at
                        """,
                        (clean_key, val_json, clean_category, now_iso),
                    )
                    conn.commit()
                    return True
            except Exception as exc:
                logger.warning("Failed to set preference %s: %s", clean_key, exc)
                return False

    def get_preference(self, key: str, default: Any = None) -> Any:
        """Retrieve a user preference value by key."""
        clean_key = str(key)[:100]
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        "SELECT value_json FROM user_preferences WHERE key = ?",
                        (clean_key,),
                    ).fetchone()
                    if row:
                        return json.loads(row["value_json"])
                    return default
            except Exception as exc:
                logger.warning("Failed to get preference %s: %s", clean_key, exc)
                return default

    def list_preferences(self, category: Optional[str] = None) -> Dict[str, Any]:
        """List all preferences, optionally filtered by category."""
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    if category:
                        cursor = conn.execute(
                            "SELECT key, value_json FROM user_preferences WHERE category = ?",
                            (str(category)[:50],),
                        )
                    else:
                        cursor = conn.execute("SELECT key, value_json FROM user_preferences")

                    prefs = {}
                    for row in cursor.fetchall():
                        prefs[row["key"]] = json.loads(row["value_json"])
                    return prefs
            except Exception as exc:
                logger.warning("Failed to list preferences: %s", exc)
                return {}

    def delete_preference(self, key: str) -> bool:
        """Delete a user preference by key."""
        clean_key = str(key)[:100]
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    cursor = conn.execute(
                        "DELETE FROM user_preferences WHERE key = ?",
                        (clean_key,),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
            except Exception as exc:
                logger.warning("Failed to delete preference %s: %s", clean_key, exc)
                return False

    # -------------------------------------------------------------------------
    # User Profile
    # -------------------------------------------------------------------------

    def set_profile_item(self, key: str, value: str) -> bool:
        """
        Store a profile attribute bounded to MAX_PROFILE_KEYS and MAX_PROFILE_VALUE_LENGTH.
        """
        clean_key = sanitize_text(str(key))[:100]
        if not clean_key:
            return False
        clean_val = sanitize_text(str(value))[:MAX_PROFILE_VALUE_LENGTH]
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    count_row = conn.execute("SELECT COUNT(*) FROM user_profile").fetchone()
                    count = count_row[0] if count_row else 0
                    if count >= MAX_PROFILE_KEYS:
                        exists = conn.execute(
                            "SELECT 1 FROM user_profile WHERE key = ?", (clean_key,)
                        ).fetchone()
                        if not exists:
                            logger.warning("Max profile keys reached (%d); cannot add key %s", MAX_PROFILE_KEYS, clean_key)
                            return False

                    conn.execute(
                        """
                        INSERT INTO user_profile (key, value, updated_at)
                        VALUES (?, ?, ?)
                        ON CONFLICT(key) DO UPDATE SET
                            value = excluded.value,
                            updated_at = excluded.updated_at
                        """,
                        (clean_key, clean_val, now_iso),
                    )
                    conn.commit()
                    return True
            except Exception as exc:
                logger.warning("Failed to set profile item %s: %s", clean_key, exc)
                return False

    def get_profile_item(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Retrieve a profile value by key."""
        clean_key = str(key)[:100]
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        "SELECT value FROM user_profile WHERE key = ?",
                        (clean_key,),
                    ).fetchone()
                    if row:
                        return str(row["value"])
                    return default
            except Exception as exc:
                logger.warning("Failed to get profile item %s: %s", clean_key, exc)
                return default

    def list_profile(self) -> Dict[str, str]:
        """List all user profile key-values."""
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    cursor = conn.execute("SELECT key, value FROM user_profile")
                    return {row["key"]: row["value"] for row in cursor.fetchall()}
            except Exception as exc:
                logger.warning("Failed to list profile items: %s", exc)
                return {}

    # -------------------------------------------------------------------------
    # Environment Facts
    # -------------------------------------------------------------------------

    def set_environment_fact(
        self,
        fact_key: str,
        fact_value: str,
        topic: str = "system",
        source: str = "observation",
        ttl_days: int = DEFAULT_FACT_TTL_DAYS,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Record a bounded environmental or system fact with a TTL.
        """
        f_key = sanitize_text(str(fact_key))[:100]
        if not f_key:
            return False
        f_val = sanitize_text(str(fact_value))[:1000]
        f_topic = sanitize_text(str(topic))[:50] or "system"
        f_source = sanitize_text(str(source))[:50] or "observation"
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(days=max(1, ttl_days))).isoformat()
        meta_json = json.dumps(sanitize_metadata(metadata or {}))[:MAX_METADATA_LENGTH]

        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    count_row = conn.execute("SELECT COUNT(*) FROM environment_facts").fetchone()
                    count = count_row[0] if count_row else 0
                    if count >= MAX_ENVIRONMENT_FACTS:
                        # Purge expired facts first
                        conn.execute(
                            "DELETE FROM environment_facts WHERE expires_at IS NOT NULL AND expires_at < ?",
                            (now_iso,),
                        )
                        count_after = conn.execute("SELECT COUNT(*) FROM environment_facts").fetchone()[0]
                        if count_after >= MAX_ENVIRONMENT_FACTS:
                            exists = conn.execute(
                                "SELECT 1 FROM environment_facts WHERE fact_key = ?", (f_key,)
                            ).fetchone()
                            if not exists:
                                # Evict oldest fact
                                conn.execute(
                                    """
                                    DELETE FROM environment_facts WHERE fact_key IN (
                                        SELECT fact_key FROM environment_facts
                                        ORDER BY created_at ASC LIMIT 1
                                    )
                                    """
                                )

                    conn.execute(
                        """
                        INSERT INTO environment_facts
                        (fact_key, fact_value, topic, source, created_at, expires_at, metadata_json)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(fact_key) DO UPDATE SET
                            fact_value = excluded.fact_value,
                            topic = excluded.topic,
                            source = excluded.source,
                            created_at = excluded.created_at,
                            expires_at = excluded.expires_at,
                            metadata_json = excluded.metadata_json
                        """,
                        (f_key, f_val, f_topic, f_source, now_iso, expires_iso, meta_json),
                    )
                    conn.commit()
                    return True
            except Exception as exc:
                logger.warning("Failed to set environment fact %s: %s", f_key, exc)
                return False

    def get_environment_fact(self, fact_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve an environment fact if not expired."""
        now_iso = datetime.now(timezone.utc).isoformat()
        f_key = str(fact_key)[:100]
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    row = conn.execute(
                        """
                        SELECT * FROM environment_facts
                        WHERE fact_key = ? AND (expires_at IS NULL OR expires_at > ?)
                        """,
                        (f_key, now_iso),
                    ).fetchone()
                    if not row:
                        return None
                    return {
                        "fact_key": row["fact_key"],
                        "fact_value": row["fact_value"],
                        "topic": row["topic"],
                        "source": row["source"],
                        "created_at": row["created_at"],
                        "expires_at": row["expires_at"],
                        "metadata": json.loads(row["metadata_json"]),
                    }
            except Exception as exc:
                logger.warning("Failed to get environment fact %s: %s", f_key, exc)
                return None

    def list_environment_facts(self, topic: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active environment facts, optionally filtered by topic."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._lock:
            try:
                with closing(self._connect()) as conn:
                    if topic:
                        cursor = conn.execute(
                            """
                            SELECT * FROM environment_facts
                            WHERE topic = ? AND (expires_at IS NULL OR expires_at > ?)
                            ORDER BY created_at DESC
                            """,
                            (str(topic)[:50], now_iso),
                        )
                    else:
                        cursor = conn.execute(
                            """
                            SELECT * FROM environment_facts
                            WHERE expires_at IS NULL OR expires_at > ?
                            ORDER BY created_at DESC
                            """,
                            (now_iso,),
                        )

                    facts = []
                    for row in cursor.fetchall():
                        facts.append({
                            "fact_key": row["fact_key"],
                            "fact_value": row["fact_value"],
                            "topic": row["topic"],
                            "source": row["source"],
                            "created_at": row["created_at"],
                            "expires_at": row["expires_at"],
                            "metadata": json.loads(row["metadata_json"]),
                        })
                    return facts
            except Exception as exc:
                logger.warning("Failed to list environment facts: %s", exc)
                return []
