"""
Tests for Phase 5 Task 003: Pre-Execution Backup & Reversible File Action Framework.
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
    BackupStatus,
    EVEventType,
    EVState,
    FileDeleteResult,
    FileWriteResult,
    PermissionDecision,
    RiskLevel,
    TaskHistoryEventType,
    VerificationStatus,
    VerificationType,
)
from core.orchestrator import EVOrchestrator, get_action_category
from core.risk import EVRiskEngine
from tools.filesystem import delete_file, validate_sandbox_path, write_file


class TestBackupReversibleFramework(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ev_test_backup_")
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

        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
            backup_manager=self.backup_manager,
            allowed_roots=self.allowed_roots,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -----------------------------------------------------------------
    # 1. Backup Engine Tests
    # -----------------------------------------------------------------
    def test_backup_existing_file(self):
        target_file = self.sandbox_dir / "test.txt"
        target_file.write_text("Hello World", encoding="utf-8")
        expected_hash = hashlib.sha256(b"Hello World").hexdigest()

        backup_res = self.backup_manager.backup_file(target_file)
        self.assertTrue(backup_res.success)
        self.assertEqual(backup_res.status, BackupStatus.CREATED)
        self.assertIsNotNone(backup_res.backup_path)
        self.assertTrue(Path(backup_res.backup_path).exists())
        self.assertEqual(backup_res.backup_record.sha256, expected_hash)

    def test_backup_sha256_matches_original(self):
        target_file = self.sandbox_dir / "data.bin"
        content = b"\x01\x02\x03\x04\x05" * 100
        target_file.write_bytes(content)
        expected_hash = hashlib.sha256(content).hexdigest()

        backup_res = self.backup_manager.backup_file(target_file)
        self.assertTrue(backup_res.success)
        self.assertEqual(backup_res.backup_record.sha256, expected_hash)
        backup_content = Path(backup_res.backup_path).read_bytes()
        self.assertEqual(hashlib.sha256(backup_content).hexdigest(), expected_hash)

    def test_backup_missing_file_fails(self):
        missing_file = self.sandbox_dir / "non_existent.txt"
        backup_res = self.backup_manager.backup_file(missing_file)
        self.assertFalse(backup_res.success)
        self.assertEqual(backup_res.status, BackupStatus.FAILED)

    # -----------------------------------------------------------------
    # 2. Sandbox & Path Security Tests
    # -----------------------------------------------------------------
    def test_allowed_path(self):
        valid_path = self.sandbox_dir / "sub" / "file.txt"
        resolved = validate_sandbox_path(valid_path, allowed_roots=self.allowed_roots)
        self.assertEqual(resolved, valid_path.resolve())

    def test_disallowed_path_rejected(self):
        outside_path = Path("C:/Windows/System32/drivers/etc/hosts")
        with self.assertRaises(PermissionError):
            validate_sandbox_path(outside_path, allowed_roots=self.allowed_roots)

    def test_parent_traversal_rejected(self):
        traversal_path = str(self.sandbox_dir / ".." / ".." / "outside.txt")
        with self.assertRaises(PermissionError):
            validate_sandbox_path(traversal_path, allowed_roots=self.allowed_roots)

    def test_unc_path_rejected(self):
        unc_path = r"\\192.168.1.1\share\file.txt"
        with self.assertRaises(PermissionError):
            validate_sandbox_path(unc_path, allowed_roots=self.allowed_roots)

    def test_dos_device_name_rejected(self):
        device_path = self.sandbox_dir / "NUL"
        with self.assertRaises(PermissionError):
            validate_sandbox_path(device_path, allowed_roots=self.allowed_roots)

    def test_null_byte_path_rejected(self):
        null_byte_path = str(self.sandbox_dir / "file.txt\x00.evil")
        with self.assertRaises(ValueError):
            validate_sandbox_path(null_byte_path, allowed_roots=self.allowed_roots)

    # -----------------------------------------------------------------
    # 3. Direct Filesystem Tools (write_file / delete_file)
    # -----------------------------------------------------------------
    def test_write_file_creation(self):
        target = self.sandbox_dir / "created.txt"
        res = write_file(str(target), content="Initial content", allowed_roots=self.allowed_roots)
        self.assertTrue(res.success)
        self.assertTrue(res.created)
        self.assertEqual(target.read_text(encoding="utf-8"), "Initial content")

    def test_write_file_overwrite_disallowed(self):
        target = self.sandbox_dir / "exists.txt"
        target.write_text("Old content", encoding="utf-8")
        res = write_file(str(target), content="New content", overwrite=False, allowed_roots=self.allowed_roots)
        self.assertFalse(res.success)
        self.assertIn("FileExistsError", res.error)
        self.assertEqual(target.read_text(encoding="utf-8"), "Old content")

    def test_delete_file_success(self):
        target = self.sandbox_dir / "to_delete.txt"
        target.write_text("Delete me", encoding="utf-8")
        res = delete_file(str(target), allowed_roots=self.allowed_roots)
        self.assertTrue(res.success)
        self.assertTrue(res.deleted)
        self.assertFalse(target.exists())

    def test_delete_missing_file_error(self):
        target = self.sandbox_dir / "missing.txt"
        res = delete_file(str(target), missing_ok=False, allowed_roots=self.allowed_roots)
        self.assertFalse(res.success)
        self.assertIn("FileNotFoundError", res.error)

    # -----------------------------------------------------------------
    # 4. Agent Execution with Pre-Execution Backup
    # -----------------------------------------------------------------
    def test_agent_write_file_new(self):
        target = self.sandbox_dir / "agent_new.txt"
        task = AgentTask(
            task_id="task_write_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "Created via agent"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "Created via agent")

    def test_agent_write_file_existing_creates_backup(self):
        target = self.sandbox_dir / "agent_modify.txt"
        target.write_text("Original content v1", encoding="utf-8")
        original_hash = hashlib.sha256(b"Original content v1").hexdigest()

        task = AgentTask(
            task_id="task_write_02",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "Modified content v2"},
            verification_type=VerificationType.FILE_EXISTS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertEqual(target.read_text(encoding="utf-8"), "Modified content v2")

        # Verify backup record in history
        events = self.history_store.get_events("task_write_02")
        backup_events = [e for e in events if e.event_type == TaskHistoryEventType.BACKUP_RESULT]
        self.assertEqual(len(backup_events), 1)
        self.assertEqual(backup_events[0].payload["status"], "CREATED")
        self.assertEqual(backup_events[0].payload["backup_record"]["sha256"], original_hash)

    def test_agent_delete_file_creates_backup(self):
        target = self.sandbox_dir / "agent_delete.txt"
        target.write_text("To be deleted", encoding="utf-8")
        original_hash = hashlib.sha256(b"To be deleted").hexdigest()

        task = AgentTask(
            task_id="task_del_01",
            action=AgentAction.DELETE_FILE,
            parameters={"path": str(target)},
            verification_type=VerificationType.FILE_NOT_EXISTS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.COMPLETED)
        self.assertFalse(target.exists())

        # Verify backup in history
        events = self.history_store.get_events("task_del_01")
        backup_events = [e for e in events if e.event_type == TaskHistoryEventType.BACKUP_RESULT]
        self.assertEqual(len(backup_events), 1)
        self.assertEqual(backup_events[0].payload["backup_record"]["sha256"], original_hash)

    # -----------------------------------------------------------------
    # 5. Recovery & Rollback Tests
    # -----------------------------------------------------------------
    def test_rollback_on_verification_failure(self):
        target = self.sandbox_dir / "rollback_target.txt"
        target.write_text("Safe Original Text", encoding="utf-8")
        original_hash = hashlib.sha256(b"Safe Original Text").hexdigest()

        events_captured = []
        self.event_bus.subscribe(lambda e: events_captured.append(e))

        # We request TEXT_CONTAINS with an expected_text that is not present in the written file
        task = AgentTask(
            task_id="task_rollback_01",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "Corrupted Text",
                "expected_text": "NonExistentExpectedString",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.FAILED)

        # File MUST be restored to original content!
        self.assertEqual(target.read_text(encoding="utf-8"), "Safe Original Text")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), original_hash)

        # Verify RECOVERY_RESULT event was emitted
        recovery_events = [e for e in events_captured if e.event_type == EVEventType.RECOVERY_RESULT]
        self.assertEqual(len(recovery_events), 1)
        self.assertTrue(recovery_events[0].data.get("success"))

        # Verify history has RESTORE_RESULT event
        events = self.history_store.get_events("task_rollback_01")
        restore_events = [e for e in events if e.event_type == TaskHistoryEventType.RESTORE_RESULT]
        self.assertEqual(len(restore_events), 1)
        self.assertEqual(restore_events[0].payload["status"], "RESTORED")

    def test_rollback_on_new_file_verification_failure_deletes_file(self):
        target = self.sandbox_dir / "unverified_new.txt"

        task = AgentTask(
            task_id="task_rollback_02",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "New File Content"},
            verification_type=VerificationType.FILE_NOT_EXISTS,  # Deliberately incompatible verification
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.FAILED)
        # Newly created unverified file should be cleaned up!
        self.assertFalse(target.exists())

    # -----------------------------------------------------------------
    # 6. Orchestrator Approval & Gating Integration Tests
    # -----------------------------------------------------------------
    def test_orchestrator_action_category_mapping(self):
        target = self.sandbox_dir / "mapped.txt"
        cat_create = get_action_category(AgentAction.WRITE_FILE, {"path": str(target)})
        self.assertEqual(cat_create, ActionCategory.FILE_CREATE)

        target.write_text("exists", encoding="utf-8")
        cat_modify = get_action_category(AgentAction.WRITE_FILE, {"path": str(target)})
        self.assertEqual(cat_modify, ActionCategory.FILE_MODIFY)

        cat_delete = get_action_category(AgentAction.DELETE_FILE, {"path": str(target)})
        self.assertEqual(cat_delete, ActionCategory.FILE_DELETE)

    def test_orchestrator_approval_pipeline_for_file_write(self):
        target = self.sandbox_dir / "orch_write.txt"
        orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        # Inject sandbox allowed roots and backup manager into orchestrator agent
        orchestrator.agent._allowed_roots = self.allowed_roots
        orchestrator.agent._backup_manager = self.backup_manager
        orchestrator.history_store = self.history_store
        orchestrator.agent._history_store = self.history_store

        task = AgentTask(
            task_id="orch_task_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "Approved Write Content"},
            verification_type=VerificationType.FILE_EXISTS,
        )

        # 1. Dispatch without approval -> Must require approval!
        thread = orchestrator._dispatch_tasks([task])
        self.assertIsNone(thread)
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertIsNotNone(orchestrator._pending_approval)
        self.assertFalse(target.exists())  # Must NOT write yet!

        # 2. Resolve with approval -> Must perform secondary risk assessment (ALLOW) and execute!
        resolved = orchestrator.resolve_approval("orch_task_01", approved=True)
        self.assertTrue(resolved)

        # Wait for execution thread to finish
        timeout = 5.0
        start = time.time()
        while time.time() - start < timeout and orchestrator.event_bus.current_state in (EVState.EXECUTING, EVState.VERIFYING, EVState.AWAITING_APPROVAL):
            time.sleep(0.05)

        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "Approved Write Content")
        self.assertEqual(orchestrator.event_bus.current_state, EVState.IDLE)

    def test_orchestrator_denied_file_write_creates_no_backup_or_file(self):
        target = self.sandbox_dir / "orch_denied.txt"
        orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        orchestrator.agent._allowed_roots = self.allowed_roots
        orchestrator.agent._backup_manager = self.backup_manager
        orchestrator.history_store = self.history_store
        orchestrator.agent._history_store = self.history_store

        task = AgentTask(
            task_id="orch_task_denied",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "Denied Content"},
            verification_type=VerificationType.FILE_EXISTS,
        )

        orchestrator._dispatch_tasks([task])
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Deny approval
        resolved = orchestrator.resolve_approval("orch_task_denied", approved=False)
        self.assertTrue(resolved)
        self.assertEqual(orchestrator.event_bus.current_state, EVState.IDLE)
        self.assertFalse(target.exists())

        # No backup should exist
        backups = list(self.backup_dir.glob("*.bak"))
        self.assertEqual(len(backups), 0)


if __name__ == "__main__":
    unittest.main()
