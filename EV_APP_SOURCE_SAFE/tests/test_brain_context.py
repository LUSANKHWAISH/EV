"""
Unit tests for Bounded Context & Memory Assembly Engine (Phase 4 Task 008).

All tests are 100% offline, deterministic, and verify:
  - Strict BrainContext construction adhering to authoritative data contracts
  - Deterministic action and task ordering
  - Upper bounds on recent tasks (max 10) and context sizes
  - Case-insensitive recursive secret redaction
  - Strict exclusion of raw file contents, command outputs, and environment dumps
  - No mutation of caller-owned data
  - Complete error handling and fail-closed validation
"""
import copy
from datetime import datetime
import json
import unittest

from core.brain_context import (
    MAX_AGGREGATE_CONTEXT_CHARS,
    MAX_CONTEXT_TASKS,
    MAX_RECURSION_DEPTH,
    REDACTION_MARKER,
    BrainContextAssembler,
    is_sensitive_key,
    sanitize_data,
)
from core.brain_models import BrainContext
from core.models import AgentAction, AgentStatus, EVState, TaskHistoryRecord


class DummyHistorySource:
    """In-memory mock implementing HistorySourceProtocol for testing."""
    def __init__(self, tasks=None):
        self.tasks = tasks or []

    def list_tasks(self, *, limit=50, status=None, action=None):
        return self.tasks[:limit]


class TestBrainContextAssemblerBasics(unittest.TestCase):
    """Verify standard BrainContext assembly and field propagation."""

    def setUp(self):
        self.assembler = BrainContextAssembler()

    def test_basic_construction(self):
        ctx = self.assembler.assemble_context(
            user_input="Check python processes",
            current_state=EVState.IDLE,
            platform="windows",
        )
        self.assertIsInstance(ctx, BrainContext)
        self.assertEqual(ctx.user_input, "Check python processes")
        self.assertEqual(ctx.current_state, EVState.IDLE)
        self.assertEqual(ctx.platform, "windows")
        self.assertEqual(len(ctx.available_actions), len(AgentAction))
        self.assertEqual(ctx.recent_task_summaries, [])
        self.assertIsNone(ctx.verification_context)

    def test_user_input_bounds_and_whitespace(self):
        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input="")

        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input="   \t\n  ")

        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input=None)  # type: ignore

        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input="a" * 4001)

    def test_invalid_state_and_platform(self):
        with self.assertRaises(TypeError):
            self.assembler.assemble_context(user_input="valid", current_state="IDLE")  # type: ignore

        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input="valid", platform="")

        with self.assertRaises(ValueError):
            self.assembler.assemble_context(user_input="valid", platform="p" * 51)

    def test_available_actions_whitelist_and_sorting(self):
        subset = [AgentAction.FIND_TCP_PORT, AgentAction.FIND_PROCESS]
        ctx = self.assembler.assemble_context(
            user_input="check network and processes",
            available_actions=subset,
        )
        # Verify deduplicated and sorted deterministically
        self.assertEqual(ctx.available_actions, [AgentAction.FIND_PROCESS, AgentAction.FIND_TCP_PORT])

        with self.assertRaises(TypeError):
            self.assembler.assemble_context(user_input="valid", available_actions=["NOT_AN_ACTION"])  # type: ignore

    def test_repeatable_determinism(self):
        ctx1 = self.assembler.assemble_context("Repeat test", EVState.IDLE, "windows")
        ctx2 = self.assembler.assemble_context("Repeat test", EVState.IDLE, "windows")
        self.assertEqual(ctx1.model_dump_json(), ctx2.model_dump_json())


class TestTaskHistorySanitizationAndBounds(unittest.TestCase):
    """Verify task history integration, bounding, and exclusion of raw output."""

    def setUp(self):
        self.assembler = BrainContextAssembler()

    def test_maximum_task_count_bound(self):
        # Generate 20 tasks
        tasks = []
        for i in range(20):
            tasks.append({
                "task_id": f"task-{i:02d}",
                "action": AgentAction.FIND_PROCESS,
                "status": AgentStatus.COMPLETED,
                "created_at": datetime.now(),
                "parameters": {"name": f"proc_{i}.exe"},
            })

        ctx = self.assembler.assemble_context(
            user_input="History check",
            recent_tasks=tasks,
            max_tasks=15,  # Requested 15, but must be capped at MAX_CONTEXT_TASKS (10)
        )
        self.assertEqual(len(ctx.recent_task_summaries), MAX_CONTEXT_TASKS)
        self.assertEqual(ctx.recent_task_summaries[0]["task_id"], "task-00")
        self.assertEqual(ctx.recent_task_summaries[9]["task_id"], "task-09")

    def test_history_source_dependency_injection(self):
        mock_tasks = [
            TaskHistoryRecord(
                task_id="task-rec-1",
                action=AgentAction.FIND_SERVICE,
                parameters={"name": "Spooler"},
                created_at=datetime(2026, 9, 1, 12, 0, 0),
                status=AgentStatus.COMPLETED,
                success=True,
                updated_at=datetime(2026, 9, 1, 12, 0, 1),
            )
        ]
        history_source = DummyHistorySource(mock_tasks)
        assembler = BrainContextAssembler(history_source=history_source)

        ctx = assembler.assemble_context(user_input="Check spooler")
        self.assertEqual(len(ctx.recent_task_summaries), 1)
        self.assertEqual(ctx.recent_task_summaries[0]["task_id"], "task-rec-1")
        self.assertEqual(ctx.recent_task_summaries[0]["action"], "FIND_SERVICE")
        self.assertEqual(ctx.recent_task_summaries[0]["parameters"], {"name": "Spooler"})
        self.assertTrue(ctx.recent_task_summaries[0]["success"])

    def test_raw_content_and_unrestricted_fields_excluded(self):
        dirty_task = {
            "task_id": "task-dirty",
            "action": "READ_TEXT_FILE",
            "status": "COMPLETED",
            "created_at": datetime.now().isoformat(),
            "parameters": {
                "path": "C:\\config.txt",
                "file_contents": "SUPER SECRET FILE DUMP THAT SHOULD NOT BE HERE",
                "raw_bytes": "0x1234567890",
                "stdout": "Dump of terminal stdout",
                "env": {"PATH": "...", "API_KEY": "secret"},
            },
            "unwanted_internal_db_column": 12345,
        }

        ctx = self.assembler.assemble_context(
            user_input="Check config",
            recent_tasks=[dirty_task],
        )
        summary = ctx.recent_task_summaries[0]
        params = summary["parameters"]

        # Allowed parameter preserved
        self.assertEqual(params.get("path"), "C:\\config.txt")

        # Raw/unrestricted fields strictly excluded
        self.assertNotIn("file_contents", params)
        self.assertNotIn("raw_bytes", params)
        self.assertNotIn("stdout", params)
        self.assertNotIn("env", params)
        self.assertNotIn("unwanted_internal_db_column", summary)


class TestSensitiveDataRedaction(unittest.TestCase):
    """Verify recursive case-insensitive redaction of credentials and secrets."""

    def test_sensitive_key_detection(self):
        self.assertTrue(is_sensitive_key("password"))
        self.assertTrue(is_sensitive_key("PASSWORD"))
        self.assertTrue(is_sensitive_key("api_key"))
        self.assertTrue(is_sensitive_key("apiKey"))
        self.assertTrue(is_sensitive_key("Authorization"))
        self.assertTrue(is_sensitive_key("client_secret"))
        self.assertTrue(is_sensitive_key("Bearer_Token"))
        self.assertTrue(is_sensitive_key("refresh-token"))

        self.assertFalse(is_sensitive_key("username"))
        self.assertFalse(is_sensitive_key("path"))
        self.assertFalse(is_sensitive_key("port"))
        self.assertFalse(is_sensitive_key("name"))

    def test_recursive_redaction(self):
        input_data = {
            "username": "admin",
            "password": "SuperSecretPassword123!",
            "nested": {
                "apiKey": "xyz-api-token-456",
                "safe_field": 42,
                "deeper": {
                    "AUTHORIZATION": "Bearer eyJhbGciOi...",
                    "client_secret": "shhh",
                }
            },
            "user_records": [
                {"token": "token-1"},
                {"safe_item": "ok"},
            ],
            "api_tokens_list": ["tokenA", "tokenB"],
        }

        sanitized = sanitize_data(input_data)

        self.assertEqual(sanitized["username"], "admin")
        self.assertEqual(sanitized["password"], REDACTION_MARKER)
        self.assertEqual(sanitized["nested"]["apiKey"], REDACTION_MARKER)
        self.assertEqual(sanitized["nested"]["safe_field"], 42)
        self.assertEqual(sanitized["nested"]["deeper"]["AUTHORIZATION"], REDACTION_MARKER)
        self.assertEqual(sanitized["nested"]["deeper"]["client_secret"], REDACTION_MARKER)
        self.assertEqual(sanitized["user_records"][0]["token"], REDACTION_MARKER)
        self.assertEqual(sanitized["user_records"][1]["safe_item"], "ok")
        self.assertEqual(sanitized["api_tokens_list"], REDACTION_MARKER)

        # Ensure no secret string leaked into sanitized dict
        dumped = json.dumps(sanitized)
        self.assertNotIn("SuperSecretPassword123!", dumped)
        self.assertNotIn("xyz-api-token-456", dumped)
        self.assertNotIn("eyJhbGciOi", dumped)
        self.assertNotIn("shhh", dumped)
        self.assertNotIn("tokenA", dumped)

    def test_no_mutation_of_caller_input(self):
        original = {
            "password": "secret_password",
            "metadata": {"api_key": "secret_key"}
        }
        original_copy = copy.deepcopy(original)

        _ = sanitize_data(original)

        # Original dictionary must remain completely unchanged
        self.assertEqual(original, original_copy)
        self.assertEqual(original["password"], "secret_password")
        self.assertEqual(original["metadata"]["api_key"], "secret_key")

    def test_recursion_depth_limit(self):
        # Create deeply nested dictionary
        curr = {}
        root = curr
        for _ in range(MAX_RECURSION_DEPTH + 3):
            curr["nested"] = {}
            curr = curr["nested"]
        curr["val"] = "deep"

        sanitized = sanitize_data(root)
        # Must not crash with RecursionError, should truncate depth
        dumped = json.dumps(sanitized)
        self.assertIn("[TRUNCATED_DEPTH]", dumped)


class TestVerificationContextAndOversizedContext(unittest.TestCase):
    """Verify verification context handling and oversized context safety limits."""

    def setUp(self):
        self.assembler = BrainContextAssembler()

    def test_verification_context_sanitization(self):
        v_ctx = {
            "target": "python.exe",
            "expected_status": "RUNNING",
            "auth_token": "secret-12345",
        }
        ctx = self.assembler.assemble_context(
            user_input="Verify python",
            verification_context=v_ctx,
        )
        self.assertIsNotNone(ctx.verification_context)
        self.assertEqual(ctx.verification_context["target"], "python.exe")
        self.assertEqual(ctx.verification_context["auth_token"], REDACTION_MARKER)

    def test_oversized_context_fails_closed(self):
        # Construct large task payloads that exceed MAX_AGGREGATE_CONTEXT_CHARS
        huge_tasks = []
        for i in range(10):
            huge_tasks.append({
                "task_id": f"task-huge-{i}",
                "action": "SEARCH_TEXT",
                "status": "COMPLETED",
                "created_at": datetime.now().isoformat(),
                "parameters": {f"param_{j}": "x" * 300 for j in range(10)},
            })

        with self.assertRaises(ValueError) as cm:
            self.assembler.assemble_context(
                user_input="Huge payload",
                recent_tasks=huge_tasks,
            )
        self.assertIn("exceeds maximum limit", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
