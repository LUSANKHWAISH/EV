"""
Hardening and edge-case test suite for Phase 5 Task 004: Mutating Actions & Allowlisting.
"""
import hashlib
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from core.agent import EVAgent
from core.backup import EVBackupManager
from core.events import EVEventBus
from core.history import EVTaskHistoryStore
from core.models import (
    ActionCategory,
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    EVEventType,
    EVState,
    PermissionDecision,
    RiskLevel,
    VerificationStatus,
    VerificationType,
)
from core.orchestrator import EVOrchestrator
from core.resolver import CommandResolver
from core.risk import EVRiskEngine
from tools.filesystem import read_text_file, write_file


class TestMutatingActionsHardening(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ev_test_hardening_")
        self.sandbox_dir = Path(self.test_dir) / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir = Path(self.test_dir) / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self.allowed_roots = [self.sandbox_dir, self.backup_dir]
        self.backup_manager = EVBackupManager(backup_root=self.backup_dir)
        self.event_bus = EVEventBus()
        self.db_path = Path(self.test_dir) / "history.sqlite3"
        self.history_store = EVTaskHistoryStore(db_path=self.db_path)
        self.risk_engine = EVRiskEngine()
        self.resolver = CommandResolver()

        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
            backup_manager=self.backup_manager,
            allowed_roots=self.allowed_roots,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------
    # 1. Resolver Tests
    # -----------------------------------------------------------------
    def test_resolver_mutating_actions(self):
        # 1a. Unquoted write
        cmd_write = "write file sandbox/test.txt hello world"
        task_write = self.resolver.resolve(cmd_write)
        self.assertEqual(task_write.action, AgentAction.WRITE_FILE)
        self.assertEqual(task_write.parameters["path"], "sandbox/test.txt")
        self.assertEqual(task_write.parameters["content"], "hello world")
        self.assertIsNone(task_write.verification_type)

        # 1b. Quoted write (double quotes)
        cmd_quoted = 'write file "sandbox/my path/file.txt" {"key": "value"}'
        task_quoted = self.resolver.resolve(cmd_quoted)
        self.assertEqual(task_quoted.action, AgentAction.WRITE_FILE)
        self.assertEqual(task_quoted.parameters["path"], "sandbox/my path/file.txt")
        self.assertEqual(task_quoted.parameters["content"], '{"key": "value"}')

        # 1c. Quoted write (single quotes)
        cmd_single = "write file 'sandbox/single.txt' multi-line\ncontent"
        task_single = self.resolver.resolve(cmd_single)
        self.assertEqual(task_single.action, AgentAction.WRITE_FILE)
        self.assertEqual(task_single.parameters["path"], "sandbox/single.txt")
        self.assertEqual(task_single.parameters["content"], "multi-line\ncontent")

        # 1d. Delete file
        cmd_del = "delete file sandbox/to_remove.txt"
        task_del = self.resolver.resolve(cmd_del)
        self.assertEqual(task_del.action, AgentAction.DELETE_FILE)
        self.assertEqual(task_del.parameters["path"], "sandbox/to_remove.txt")

        # 1e. Malformed write / delete commands
        with self.assertRaises(ValueError):
            self.resolver.resolve("write file")
        with self.assertRaises(ValueError):
            self.resolver.resolve("write file only_path")
        with self.assertRaises(ValueError):
            self.resolver.resolve('write file "unmatched quote text')
        with self.assertRaises(ValueError):
            self.resolver.resolve("delete file")

    # -----------------------------------------------------------------
    # 2. Batch Execution with Mixed Read/Write Tasks
    # -----------------------------------------------------------------
    def test_batch_execution_with_mutations(self):
        existing_file = self.sandbox_dir / "read_target.txt"
        existing_file.write_text("initial data", encoding="utf-8")
        write_target = self.sandbox_dir / "batch_out.txt"

        orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        orchestrator.agent._allowed_roots = self.allowed_roots
        orchestrator.agent._backup_manager = self.backup_manager
        orchestrator.history_store = self.history_store
        orchestrator.agent._history_store = self.history_store

        # Batch: 1. Read (observation) -> 2. Write (mutation)
        task_read = AgentTask(
            task_id="batch_01_read",
            action=AgentAction.READ_TEXT_FILE,
            parameters={"path": str(existing_file)},
        )
        task_write = AgentTask(
            task_id="batch_02_write",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(write_target), "content": "batch generated content"},
            verification_type=VerificationType.FILE_EXISTS,
        )

        # Dispatch batch: task_read is evaluated first (READ_ONLY_OBSERVATION -> ALLOW)
        thread = orchestrator._dispatch_tasks([task_read, task_write])
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        # After task_read finishes, task_write must halt at AWAITING_APPROVAL!
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertIsNotNone(orchestrator._pending_approval)
        self.assertEqual(orchestrator._pending_approval["task"].task_id, "batch_02_write")
        self.assertFalse(write_target.exists())  # Must NOT write before approval!

        # Resolve approval
        resolved = orchestrator.resolve_approval("batch_02_write", approved=True)
        self.assertTrue(resolved)

        timeout = 5.0
        start = time.time()
        while time.time() - start < timeout and orchestrator.event_bus.current_state in (EVState.EXECUTING, EVState.VERIFYING, EVState.AWAITING_APPROVAL):
            time.sleep(0.05)

        self.assertTrue(write_target.exists())
        self.assertEqual(write_target.read_text(encoding="utf-8"), "batch generated content")
        self.assertEqual(orchestrator.event_bus.current_state, EVState.IDLE)

    # -----------------------------------------------------------------
    # 3. Stale & Duplicate Approval Rejection
    # -----------------------------------------------------------------
    def test_stale_approval_rejected(self):
        orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        target = self.sandbox_dir / "stale_test.txt"

        task = AgentTask(
            task_id="stale_task_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "data"},
        )

        # 3a. Calling resolve_approval when nothing is pending
        self.assertFalse(orchestrator.resolve_approval("random_task_id", approved=True))

        # 3b. Dispatch task to enter AWAITING_APPROVAL
        orchestrator._dispatch_tasks([task])
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # 3c. Calling resolve_approval with wrong task ID fails
        self.assertFalse(orchestrator.resolve_approval("wrong_task_id", approved=True))
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # 3d. Resolving approval with correct task ID succeeds
        self.assertTrue(orchestrator.resolve_approval("stale_task_01", approved=True))

        # 3e. Duplicate resolution of the SAME task ID immediately fails
        self.assertFalse(orchestrator.resolve_approval("stale_task_01", approved=True))

    # -----------------------------------------------------------------
    # 4. Direct Agent Bypass Safety
    # -----------------------------------------------------------------
    def test_direct_agent_bypass_safety(self):
        # 4a. Outside sandbox path fails inside agent
        outside_target = "C:/Windows/System32/evil_payload.txt"
        task_outside = AgentTask(
            task_id="bypass_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": outside_target, "content": "hacked"},
        )
        res_outside = self.agent.run(task_outside)
        self.assertEqual(res_outside.status, AgentStatus.FAILED)
        self.assertIn("Sandbox validation failed", res_outside.error)

        # 4b. Parent traversal fails inside agent
        traversal_target = str(self.sandbox_dir / ".." / ".." / "traversal_payload.txt")
        task_traversal = AgentTask(
            task_id="bypass_02",
            action=AgentAction.WRITE_FILE,
            parameters={"path": traversal_target, "content": "traversal"},
        )
        res_traversal = self.agent.run(task_traversal)
        self.assertEqual(res_traversal.status, AgentStatus.FAILED)
        self.assertIn("Sandbox validation failed", res_traversal.error)

        # 4c. Valid sandbox path with verification failure triggers automatic backup & recovery inside agent
        target = self.sandbox_dir / "direct_safety.txt"
        target.write_text("original direct data", encoding="utf-8")
        orig_hash = hashlib.sha256(b"original direct data").hexdigest()

        task_verif_fail = AgentTask(
            task_id="bypass_03",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "corrupted text",
                "expected_text": "ImpossibleString",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        res_verif = self.agent.run(task_verif_fail)
        self.assertEqual(res_verif.status, AgentStatus.FAILED)
        # Verify target is reverted to original
        self.assertEqual(target.read_text(encoding="utf-8"), "original direct data")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), orig_hash)

    # -----------------------------------------------------------------
    # 5. Unicode and Boundary Content Tests
    # -----------------------------------------------------------------
    def test_unicode_and_boundary_content(self):
        target = self.sandbox_dir / "unicode_test.txt"
        unicode_content = "🚀 E.V. System नमस्ते दुनिया こんにちは 你好 Special Characters: äöüß—€£¥"

        task = AgentTask(
            task_id="unicode_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": unicode_content},
            verification_type=VerificationType.FILE_EXISTS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertEqual(target.read_text(encoding="utf-8"), unicode_content)

        # 5b. Valid boundary size: 1 MB (1024 * 1024 characters)
        large_target = self.sandbox_dir / "large_valid.txt"
        content_1mb = "A" * (1024 * 1024)
        task_1mb = AgentTask(
            task_id="size_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(large_target), "content": content_1mb},
            verification_type=VerificationType.FILE_EXISTS,
        )
        res_1mb = self.agent.run(task_1mb)
        self.assertEqual(res_1mb.status, AgentStatus.COMPLETED)
        self.assertEqual(large_target.stat().st_size, 1024 * 1024)

        # 5c. Exceeded boundary size: 1 MB + 1 byte
        oversized_target = self.sandbox_dir / "oversized.txt"
        content_oversized = "A" * (1024 * 1024 + 1)
        task_oversized = AgentTask(
            task_id="size_02",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(oversized_target), "content": content_oversized},
            verification_type=VerificationType.FILE_EXISTS,
        )
        res_oversized = self.agent.run(task_oversized)
        self.assertEqual(res_oversized.status, AgentStatus.FAILED)
        self.assertFalse(oversized_target.exists())

    # -----------------------------------------------------------------
    # 6. Rapid Mutation and Recovery Integrity
    # -----------------------------------------------------------------
    def test_rapid_mutation_and_recovery_integrity(self):
        target = self.sandbox_dir / "rapid_target.txt"
        target.write_text("v0_initial", encoding="utf-8")

        # Perform 4 sequential valid modifications
        for i in range(1, 5):
            new_content = f"v{i}_content_update"
            task = AgentTask(
                task_id=f"rapid_mod_{i}",
                action=AgentAction.WRITE_FILE,
                parameters={"path": str(target), "content": new_content},
                verification_type=VerificationType.FILE_EXISTS,
            )
            res = self.agent.run(task)
            self.assertEqual(res.status, AgentStatus.COMPLETED)
            self.assertEqual(target.read_text(encoding="utf-8"), new_content)

        # State before 5th failed write
        v4_content = "v4_content_update"
        v4_hash = hashlib.sha256(v4_content.encode("utf-8")).hexdigest()
        self.assertEqual(target.read_text(encoding="utf-8"), v4_content)

        # 5th write: fails verification
        task_fail = AgentTask(
            task_id="rapid_mod_5_fail",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "v5_corrupted_payload",
                "expected_text": "NonExistentString12345",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        res_fail = self.agent.run(task_fail)
        self.assertEqual(res_fail.status, AgentStatus.FAILED)

        # File must be rolled back precisely to v4 state
        self.assertEqual(target.read_text(encoding="utf-8"), v4_content)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), v4_hash)


if __name__ == "__main__":
    unittest.main()
