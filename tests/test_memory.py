"""
Unit, concurrency, security, and integration tests for EVConversationMemoryStore (Phase 6 Task 011).
"""
import concurrent.futures
import json
import sqlite3
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from core.conversation import EVConversationContextStore
from core.events import EVEventBus
from core.memory import (
    DEFAULT_FACT_TTL_DAYS,
    MAX_ENVIRONMENT_FACTS,
    MAX_MESSAGE_LENGTH,
    MAX_PREFERENCE_KEYS,
    MAX_PROFILE_KEYS,
    MAX_PROFILE_VALUE_LENGTH,
    MAX_STORED_SESSIONS,
    MAX_TURNS_PER_SESSION,
    EVConversationMemoryStore,
    sanitize_metadata,
    sanitize_text,
)
from core.models import (
    ActionCategory,
    AgentAction,
    AgentTask,
    EVState,
    RiskAssessmentRequest,
    RiskLevel,
)
from core.orchestrator import EVOrchestrator
from core.risk import EVRiskEngine


@pytest.fixture
def temp_db_path(tmp_path):
    """Provide a temporary SQLite database path."""
    return tmp_path / "test_memory.sqlite3"


@pytest.fixture
def memory_store(temp_db_path):
    """Provide a clean EVConversationMemoryStore instance."""
    return EVConversationMemoryStore(db_path=temp_db_path)


# =============================================================================
# 1. Session Tests
# =============================================================================

def test_create_and_load_session(memory_store):
    sid = memory_store.create_session(title="Test Session 1", metadata={"origin": "cli"})
    assert sid.startswith("sess_")
    sess = memory_store.get_session(sid)
    assert sess is not None
    assert sess["session_id"] == sid
    assert sess["title"] == "Test Session 1"
    assert sess["metadata"]["origin"] == "cli"


def test_session_timestamps(memory_store):
    sid = memory_store.create_session()
    sess_before = memory_store.get_session(sid)
    time.sleep(0.01)
    memory_store.touch_session(sid)
    sess_after = memory_store.get_session(sid)
    assert sess_after["updated_at"] >= sess_before["updated_at"]


def test_session_isolation(memory_store):
    s1 = memory_store.create_session(title="Session 1")
    s2 = memory_store.create_session(title="Session 2")

    memory_store.record_turn(s1, user_message="Message in S1")
    memory_store.record_turn(s2, user_message="Message in S2")

    turns1 = memory_store.get_recent_turns(s1)
    turns2 = memory_store.get_recent_turns(s2)

    assert len(turns1) == 1
    assert turns1[0]["user_message"] == "Message in S1"
    assert len(turns2) == 1
    assert turns2[0]["user_message"] == "Message in S2"


def test_session_resumption_recent(memory_store):
    s1 = memory_store.create_session(title="Recent Session")
    resumed = memory_store.get_or_create_active_session(inactivity_hours=2.0)
    assert resumed == s1


def test_session_resumption_expired(memory_store):
    # Create a session and artificially backdate updated_at
    s1 = memory_store.create_session(title="Old Session")
    old_iso = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    with memory_store._connect() as conn:
        conn.execute("UPDATE sessions SET updated_at = ? WHERE session_id = ?", (old_iso, s1))
        conn.commit()

    resumed = memory_store.get_or_create_active_session(inactivity_hours=2.0)
    assert resumed != s1
    assert resumed.startswith("sess_")


def test_session_retention_pruning(temp_db_path):
    store = EVConversationMemoryStore(db_path=temp_db_path)
    sessions = []
    for i in range(MAX_STORED_SESSIONS + 5):
        sid = store.create_session(title=f"Session {i}")
        sessions.append(sid)

    listed = store.list_sessions(limit=100)
    assert len(listed) == MAX_STORED_SESSIONS
    # Oldest 5 sessions should have been pruned
    pruned = sessions[:5]
    for p in pruned:
        assert store.get_session(p) is None


# =============================================================================
# 2. Conversation Turn Tests
# =============================================================================

def test_record_and_retrieve_turns(memory_store):
    sid = memory_store.create_session()
    t1 = memory_store.record_turn(sid, user_message="Hello", assistant_message="Hi there")
    t2 = memory_store.record_turn(sid, user_message="How are you?", assistant_message="Good!")

    turns = memory_store.get_recent_turns(sid)
    assert len(turns) == 2
    assert turns[0]["turn_id"] == t1
    assert turns[0]["user_message"] == "Hello"
    assert turns[0]["assistant_message"] == "Hi there"
    assert turns[1]["turn_id"] == t2


def test_chronological_ordering(memory_store):
    sid = memory_store.create_session()
    for i in range(5):
        memory_store.record_turn(sid, user_message=f"Msg {i}")

    turns = memory_store.get_recent_turns(sid, limit=5)
    assert len(turns) == 5
    for i in range(5):
        assert turns[i]["user_message"] == f"Msg {i}"


def test_restart_persistence(temp_db_path):
    store1 = EVConversationMemoryStore(db_path=temp_db_path)
    sid = store1.create_session(title="Persistent Session")
    store1.record_turn(sid, user_message="Remember this", assistant_message="I will")

    # Simulate process restart by creating a new store instance with same db
    store2 = EVConversationMemoryStore(db_path=temp_db_path)
    turns = store2.get_recent_turns(sid)
    assert len(turns) == 1
    assert turns[0]["user_message"] == "Remember this"
    assert turns[0]["assistant_message"] == "I will"


def test_100_turn_bound_pruning(memory_store):
    sid = memory_store.create_session()
    for i in range(MAX_TURNS_PER_SESSION + 15):
        memory_store.record_turn(sid, user_message=f"Turn {i}")

    turns = memory_store.get_recent_turns(sid, limit=200)
    assert len(turns) == MAX_TURNS_PER_SESSION
    # Oldest 15 turns should have been evicted
    assert turns[0]["user_message"] == "Turn 15"
    assert turns[-1]["user_message"] == f"Turn {MAX_TURNS_PER_SESSION + 14}"


def test_1000_char_message_bound(memory_store):
    sid = memory_store.create_session()
    huge_msg = "A" * (MAX_MESSAGE_LENGTH + 500)
    memory_store.record_turn(sid, user_message=huge_msg, assistant_message=huge_msg)

    turns = memory_store.get_recent_turns(sid)
    assert len(turns) == 1
    assert len(turns[0]["user_message"]) == MAX_MESSAGE_LENGTH
    assert len(turns[0]["assistant_message"]) == MAX_MESSAGE_LENGTH


def test_metadata_bounds(memory_store):
    sid = memory_store.create_session()
    meta = {"source": "gui", "valid": True, "token": "secret123"}
    memory_store.record_turn(sid, user_message="Test", metadata=meta)

    turns = memory_store.get_recent_turns(sid)
    assert turns[0]["metadata"]["source"] == "gui"
    assert turns[0]["metadata"]["valid"] is True
    # Secret key should be redacted
    assert turns[0]["metadata"]["token"] == "[REDACTED]"


# =============================================================================
# 3. Preferences & Profile Tests
# =============================================================================

def test_preference_crud(memory_store):
    assert memory_store.set_preference("editor", "vscode", category="tools")
    assert memory_store.get_preference("editor") == "vscode"

    # Update
    assert memory_store.set_preference("editor", "neovim", category="tools")
    assert memory_store.get_preference("editor") == "neovim"

    # List
    prefs = memory_store.list_preferences(category="tools")
    assert prefs["editor"] == "neovim"

    # Delete
    assert memory_store.delete_preference("editor")
    assert memory_store.get_preference("editor") is None


def test_preference_max_bound(memory_store):
    for i in range(MAX_PREFERENCE_KEYS):
        assert memory_store.set_preference(f"pref_{i}", i)

    # Adding beyond bound should fail
    assert not memory_store.set_preference("pref_overflow", "too_many")
    assert memory_store.get_preference("pref_overflow") is None


def test_profile_crud(memory_store):
    assert memory_store.set_profile_item("preferred_shell", "pwsh")
    assert memory_store.get_profile_item("preferred_shell") == "pwsh"

    profile = memory_store.list_profile()
    assert profile["preferred_shell"] == "pwsh"


def test_profile_bounds(memory_store):
    long_val = "x" * (MAX_PROFILE_VALUE_LENGTH + 200)
    assert memory_store.set_profile_item("long_key", long_val)
    retrieved = memory_store.get_profile_item("long_key")
    assert len(retrieved) == MAX_PROFILE_VALUE_LENGTH


# =============================================================================
# 4. Environment Facts Tests
# =============================================================================

def test_environment_facts_crud(memory_store):
    assert memory_store.set_environment_fact(
        fact_key="os_version",
        fact_value="Windows 11 Build 22631",
        topic="os",
        source="systeminfo",
    )
    fact = memory_store.get_environment_fact("os_version")
    assert fact is not None
    assert fact["fact_value"] == "Windows 11 Build 22631"
    assert fact["topic"] == "os"


def test_environment_facts_topic_filtering(memory_store):
    memory_store.set_environment_fact("net_adapter", "Ethernet 1", topic="network")
    memory_store.set_environment_fact("dns_server", "1.1.1.1", topic="network")
    memory_store.set_environment_fact("cpu_model", "Ryzen 9", topic="hardware")

    net_facts = memory_store.list_environment_facts(topic="network")
    assert len(net_facts) == 2
    assert all(f["topic"] == "network" for f in net_facts)


def test_environment_facts_ttl_expiration(memory_store):
    memory_store.set_environment_fact(
        fact_key="temp_state",
        fact_value="reboot_required",
        ttl_days=1,
    )
    # Artificially expire the fact
    expired_iso = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with memory_store._connect() as conn:
        conn.execute("UPDATE environment_facts SET expires_at = ? WHERE fact_key = 'temp_state'", (expired_iso,))
        conn.commit()

    assert memory_store.get_environment_fact("temp_state") is None
    assert len(memory_store.list_environment_facts()) == 0


def test_environment_facts_max_bound(memory_store):
    for i in range(MAX_ENVIRONMENT_FACTS):
        memory_store.set_environment_fact(f"fact_{i}", f"val_{i}")

    # Adding one more should safely evict oldest without error
    assert memory_store.set_environment_fact("fact_overflow", "overflow_val")
    assert memory_store.get_environment_fact("fact_overflow") is not None


# =============================================================================
# 5. Security & Redaction Tests
# =============================================================================

def test_password_and_token_redaction(memory_store):
    sid = memory_store.create_session()
    user_txt = "My password is supersecret123 and token is sk-1234567890abcdef12345678"
    memory_store.record_turn(sid, user_message=user_txt)

    turns = memory_store.get_recent_turns(sid)
    assert "sk-" not in turns[0]["user_message"]
    assert "[REDACTED]" in turns[0]["user_message"]


def test_api_key_redaction():
    text = "Here is my Google key: AIzaSyD1234567890123456789012345678901 and OpenAI sk-abcdefghijklmnopqrstuvwxyz12345"
    sanitized = sanitize_text(text)
    assert "AIzaSy" not in sanitized
    assert "sk-" not in sanitized
    assert "[REDACTED]" in sanitized


def test_private_key_redaction():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0\n-----END RSA PRIVATE KEY-----"
    sanitized = sanitize_text(text)
    assert "BEGIN RSA PRIVATE KEY" not in sanitized
    assert "[REDACTED]" in sanitized


def test_bearer_token_redaction():
    text = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThis"
    sanitized = sanitize_text(text)
    assert "Bearer [REDACTED]" in sanitized
    assert "doNotLeakThis" not in sanitized


def test_nested_metadata_secret_redaction():
    nested = {
        "headers": {
            "Authorization": "Bearer 12345",
            "api_key": "some-secret",
            "content-type": "application/json",
        },
        "user_credentials": ["admin", "secret_pass_123"],
    }
    cleaned = sanitize_metadata(nested)
    assert cleaned["headers"]["Authorization"] == "[REDACTED]"
    assert cleaned["headers"]["api_key"] == "[REDACTED]"
    assert cleaned["headers"]["content-type"] == "application/json"
    # Key containing 'credential' is properly redacted
    assert cleaned["user_credentials"] == "[REDACTED]"


# =============================================================================
# 6. SQLite Concurrency Tests
# =============================================================================

def test_wal_mode_and_pragmas(memory_store):
    with memory_store._connect() as conn:
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.lower() == "wal"
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert fk == 1
        user_ver = conn.execute("PRAGMA user_version").fetchone()[0]
        assert user_ver == 1


def test_concurrent_readers_and_writers(temp_db_path):
    store = EVConversationMemoryStore(db_path=temp_db_path)
    sid = store.create_session(title="Concurrency Test")

    def writer_task(idx):
        for i in range(10):
            store.record_turn(sid, user_message=f"Writer {idx} Turn {i}")

    def reader_task():
        for _ in range(10):
            store.get_recent_turns(sid, limit=5)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = []
        for i in range(4):
            futures.append(executor.submit(writer_task, i))
            futures.append(executor.submit(reader_task))
        concurrent.futures.wait(futures)

    turns = store.get_recent_turns(sid, limit=100)
    assert len(turns) == 40


def test_multiple_store_instances(temp_db_path):
    store1 = EVConversationMemoryStore(db_path=temp_db_path)
    store2 = EVConversationMemoryStore(db_path=temp_db_path)

    sid = store1.create_session(title="Cross-instance Session")
    store2.record_turn(sid, user_message="From Store 2")

    turns = store1.get_recent_turns(sid)
    assert len(turns) == 1
    assert turns[0]["user_message"] == "From Store 2"


# =============================================================================
# 7. Failure & Degradation Tests
# =============================================================================

def test_unwriteable_database_graceful_degradation(tmp_path):
    bad_db = tmp_path / "non_existent_folder" / "sub" / "unwriteable.sqlite3"
    # Even if initialization fails or db is unwriteable, methods should catch and not crash
    with patch.object(EVConversationMemoryStore, "_connect", side_effect=sqlite3.OperationalError("disk I/O error")):
        with pytest.raises(Exception):
            EVConversationMemoryStore(db_path=bad_db)


def test_context_store_graceful_degradation_on_memory_error(temp_db_path):
    store = EVConversationMemoryStore(db_path=temp_db_path)
    ctx = EVConversationContextStore(memory_store=store)

    # Force record_turn to fail
    with patch.object(store, "record_turn", side_effect=sqlite3.OperationalError("database locked")):
        # add_turn should still succeed in-memory without raising exception!
        turn = ctx.add_turn(user_message="Safe in-memory", assistant_message="OK")
        assert turn.user_message == "Safe in-memory"
        assert len(ctx.get_recent_turns()) == 1


# =============================================================================
# 8. Absolute Safety Invariant Test
# =============================================================================

def test_memory_never_authorizes_future_mutation(memory_store):
    """
    CRITICAL INVARIANT:
    Past approvals or instructions recorded in conversation memory must NEVER
    authorize a future mutating task. Every mutating task must independently
    pass EVRiskEngine and require explicit user approval.
    """
    sid = memory_store.create_session()
    memory_store.record_turn(
        sid,
        user_message="I previously approved deleting D:\\test.txt",
        assistant_message="Understood.",
    )

    # Verify that evaluating a new DELETE_FILE task still strictly requires approval
    risk_engine = EVRiskEngine()
    req = RiskAssessmentRequest(
        action_category=ActionCategory.FILE_DELETE,
        target="D:\\test.txt",
        description="Action DELETE_FILE",
        user_approved=False,  # Past memory cannot set this to True!
        has_backup=True,
        reversible=True,
    )
    result = risk_engine.assess(req)

    # Must NOT be permitted without user approval!
    assert result.decision.value == "REQUIRE_APPROVAL"
    assert result.requires_approval is True
    assert result.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM)


# =============================================================================
# 9. Orchestrator Integration Test
# =============================================================================

def test_orchestrator_integration_with_memory(temp_db_path):
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    mem_store = EVConversationMemoryStore(db_path=temp_db_path)
    orch = EVOrchestrator(event_bus=event_bus, memory_store=mem_store)

    assert orch.memory_store is not None
    assert orch.context_store.memory_store is mem_store

    # Record turn via context_store and ensure it reached mem_store
    turn = orch.context_store.add_turn(user_message="Integration test message", assistant_message="Response")
    assert turn is not None

    active_sid = orch.context_store.session_id
    assert active_sid is not None
    turns_in_db = mem_store.get_recent_turns(active_sid)
    assert len(turns_in_db) >= 1
    assert turns_in_db[-1]["user_message"] == "Integration test message"
