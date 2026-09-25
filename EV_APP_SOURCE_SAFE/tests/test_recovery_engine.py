"""
Task 005 Regression Test Suite: Automatic Failure Rollback & Recovery Engine.
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
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    BackupStatus,
    EVEventType,
    EVState,
    TaskHistoryEventType,
    VerificationStatus,
    VerificationType,
)
from core.orchestrator import EVOrchestrator
from core.risk import EVRiskEngine


class TestRecoveryEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ev_test_recovery_")
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
    # 1. Mutation Failure Triggers Single Recovery
    # -----------------------------------------------------------------
    def test_mutation_failure_triggers_single_recovery(self):
        target = self.sandbox_dir / "mut_fail.txt"
        target.write_text("initial_state", encoding="utf-8")
        orig_hash = hashlib.sha256(b"initial_state").hexdigest()

        events_captured = []
        self.event_bus.subscribe(lambda e: events_captured.append(e))

        # Attempt to overwrite with overwrite=False (will cause FileExistsError in write_file)
        task = AgentTask(
            task_id="task_mut_fail_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "new_state", "overwrite": False},
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.FAILED)
        self.assertIn("FileExistsError", res.error)

        # Confirm target is intact
        self.assertEqual(target.read_text(encoding="utf-8"), "initial_state")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), orig_hash)

        # Verify exactly one recovery event
        recovery_events = [e for e in events_captured if e.event_type == EVEventType.RECOVERY_RESULT]
        self.assertEqual(len(recovery_events), 1)
        self.assertTrue(recovery_events[0].data.get("success"))

        # Verify history has exactly one RESTORE_RESULT
        hist_events = self.history_store.get_events("task_mut_fail_01")
        restore_events = [e for e in hist_events if e.event_type == TaskHistoryEventType.RESTORE_RESULT]
        self.assertEqual(len(restore_events), 1)

    # -----------------------------------------------------------------
    # 2. Verification Failure Triggers Recovery
    # -----------------------------------------------------------------
    def test_verification_failure_triggers_recovery(self):
        target = self.sandbox_dir / "verif_fail.txt"
        target.write_text("original_valid_text", encoding="utf-8")
        orig_hash = hashlib.sha256(b"original_valid_text").hexdigest()

        task = AgentTask(
            task_id="task_verif_fail_01",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "modified_unverified_text",
                "expected_text": "NonExistentExpectedString999",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.FAILED)

        # File MUST be restored to original_valid_text
        self.assertEqual(target.read_text(encoding="utf-8"), "original_valid_text")
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), orig_hash)

    # -----------------------------------------------------------------
    # 3. Recovery Restores Exact SHA-256
    # -----------------------------------------------------------------
    def test_recovery_restores_exact_sha256(self):
        target = self.sandbox_dir / "sha_target.bin"
        binary_content = os.urandom(65536)  # 64 KB random binary
        target.write_bytes(binary_content)
        expected_hash = hashlib.sha256(binary_content).hexdigest()

        task = AgentTask(
            task_id="task_sha_01",
            action=AgentAction.DELETE_FILE,
            parameters={"path": str(target)},
            verification_type=VerificationType.FILE_EXISTS,  # Will fail because file was deleted
        )
        res = self.agent.run(task)
        self.assertEqual(res.status, AgentStatus.FAILED)

        # After rollback, deleted file must exist and have EXACT sha256
        self.assertTrue(target.exists())
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), expected_hash)

    # -----------------------------------------------------------------
    # 4. Double Recovery Prevented (Idempotent)
    # -----------------------------------------------------------------
    def test_double_recovery_prevented_idempotent(self):
        target = self.sandbox_dir / "idempotent.txt"
        target.write_text("idempotent_original", encoding="utf-8")

        task = AgentTask(
            task_id="task_idempotent_01",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "corrupted"},
        )
        target_path_obj = self.sandbox_dir / "idempotent.txt"

        # Record task in history store first
        self.history_store.record_task(task)

        # Pre-backup
        backup_res = self.backup_manager.backup_file(target_path_obj)
        self.assertTrue(backup_res.success)

        # 1st Rollback call
        res1 = self.agent._rollback_if_needed(
            task=task,
            target_path_obj=target_path_obj,
            target_existed_before=True,
            backup_record_res=backup_res,
        )
        self.assertIsNotNone(res1)
        self.assertTrue(res1.success)

        # 2nd Rollback call for the SAME task
        res2 = self.agent._rollback_if_needed(
            task=task,
            target_path_obj=target_path_obj,
            target_existed_before=True,
            backup_record_res=backup_res,
        )
        # Should return cached result without creating duplicate events/records
        self.assertEqual(res1, res2)

        # Verify history has ONLY 1 RESTORE_RESULT record
        hist_events = self.history_store.get_events("task_idempotent_01")
        restore_events = [e for e in hist_events if e.event_type == TaskHistoryEventType.RESTORE_RESULT]
        self.assertEqual(len(restore_events), 1)

    # -----------------------------------------------------------------
    # 5. Recovery Failure Never Reports Success (Double Failure)
    # -----------------------------------------------------------------
    def test_recovery_failure_never_reports_success(self):
        target = self.sandbox_dir / "double_fail.txt"
        target.write_text("double_fail_orig", encoding="utf-8")

        # Create a mock/failing backup manager whose restore_file always fails
        class BrokenBackupManager(EVBackupManager):
            def restore_file(self, *args, **kwargs):
                from core.models import RestoreResult
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=True,
                    original_path=str(target),
                    backup_path="broken_path.bak",
                    message="Simulated I/O disk corruption during restore",
                    error="DiskError: Bad sectors detected",
                    duration_seconds=0.01,
                )

        failing_backup_manager = BrokenBackupManager(backup_root=self.backup_dir)
        agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
            backup_manager=failing_backup_manager,
            allowed_roots=self.allowed_roots,
        )

        task = AgentTask(
            task_id="task_double_fail_01",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "bad_content",
                "expected_text": "NonExistentString123",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        res = agent.run(task)

        # CRITICAL INVARIANT: Final status MUST be FAILED (never COMPLETED or SUCCESS)
        self.assertEqual(res.status, AgentStatus.FAILED)
        self.assertFalse(res.step.success)

        # Error must clearly report both verification and recovery failure
        self.assertIn("Recovery restore failed", res.error)
        self.assertIn("Bad sectors detected", res.error)

    # -----------------------------------------------------------------
    # 6. Corrupt Backup Blocks Restore Safely
    # -----------------------------------------------------------------
    def test_corrupt_backup_fails_recovery_safely(self):
        target = self.sandbox_dir / "corrupt_test.txt"
        target.write_text("pre_corrupt_text", encoding="utf-8")

        # Create an invalid directory in place of a regular backup file
        corrupt_backup_dir = self.backup_dir / "invalid_bak_dir.bak"
        corrupt_backup_dir.mkdir(parents=True, exist_ok=True)

        # Attempt restore
        restore_res = self.backup_manager.restore_file(
            backup_path=corrupt_backup_dir,
            original_path=target,
            overwrite=True,
        )
        self.assertFalse(restore_res.success)
        self.assertEqual(restore_res.status, BackupStatus.FAILED)
        self.assertIn("IsADirectoryError", restore_res.error)

        # Also test security boundary: backup path outside backup_root
        outside_backup = Path(self.test_dir) / "outside.bak"
        outside_backup.write_text("outside", encoding="utf-8")
        restore_res2 = self.backup_manager.restore_file(
            backup_path=outside_backup,
            original_path=target,
            overwrite=True,
        )
        self.assertFalse(restore_res2.success)
        self.assertEqual(restore_res2.status, BackupStatus.FAILED)
        self.assertIn("SecurityError", restore_res2.error)

    # -----------------------------------------------------------------
    # 7. Missing Backup Blocks Restore Safely
    # -----------------------------------------------------------------
    def test_missing_backup_fails_recovery_safely(self):
        target = self.sandbox_dir / "missing_bak_target.txt"
        missing_backup = self.backup_dir / "non_existent.bak"

        restore_res = self.backup_manager.restore_file(
            backup_path=missing_backup,
            original_path=target,
            overwrite=True,
        )
        self.assertFalse(restore_res.success)
        self.assertEqual(restore_res.status, BackupStatus.FAILED)
        self.assertIn("FileNotFoundError", restore_res.error)

    # -----------------------------------------------------------------
    # 8. Failed Recovery Aborts Batch Sequence
    # -----------------------------------------------------------------
    def test_failed_recovery_aborts_batch_sequence(self):
        f1 = self.sandbox_dir / "batch_1.txt"
        f1.write_text("f1_initial", encoding="utf-8")
        f2 = self.sandbox_dir / "batch_2.txt"

        orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        orchestrator.agent._allowed_roots = self.allowed_roots
        orchestrator.agent._backup_manager = self.backup_manager
        orchestrator.history_store = self.history_store
        orchestrator.agent._history_store = self.history_store

        # T1 fails verification -> triggers recovery
        task_1 = AgentTask(
            task_id="batch_abort_01",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(f1),
                "content": "f1_mod",
                "expected_text": "NonExistentString123",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        # T2 should NEVER execute because T1 fails
        task_2 = AgentTask(
            task_id="batch_abort_02",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(f2), "content": "f2_content"},
            verification_type=VerificationType.FILE_EXISTS,
        )

        orchestrator._dispatch_tasks([task_1, task_2])
        self.assertEqual(orchestrator.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Approve T1
        orchestrator.resolve_approval("batch_abort_01", approved=True)

        timeout = 5.0
        start = time.time()
        while time.time() - start < timeout and orchestrator.event_bus.current_state in (EVState.EXECUTING, EVState.VERIFYING, EVState.RECOVERING, EVState.AWAITING_APPROVAL):
            time.sleep(0.05)

        # Final state must be IDLE (after FAILED)
        self.assertEqual(orchestrator.event_bus.current_state, EVState.IDLE)

        # f1 rolled back to initial
        self.assertEqual(f1.read_text(encoding="utf-8"), "f1_initial")

        # f2 must NOT exist (task_2 was aborted)
        self.assertFalse(f2.exists())

    # -----------------------------------------------------------------
    # 9. Restore History and Event Sequence
    # -----------------------------------------------------------------
    def test_restore_history_and_event_sequence(self):
        target = self.sandbox_dir / "event_seq.txt"
        target.write_text("seq_initial", encoding="utf-8")

        events_captured = []
        self.event_bus.subscribe(lambda e: events_captured.append(e))

        task = AgentTask(
            task_id="task_event_seq_01",
            action=AgentAction.WRITE_FILE,
            parameters={
                "path": str(target),
                "content": "seq_corrupted",
                "expected_text": "ImpossibleString",
            },
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        self.agent.run(task)

        # Verify event sequence contains VERIFICATION_RESULT -> RECOVERY_RESULT -> ACTION_COMPLETED
        event_types = [e.event_type for e in events_captured]
        self.assertIn(EVEventType.VERIFICATION_RESULT, event_types)
        self.assertIn(EVEventType.RECOVERY_RESULT, event_types)
        self.assertIn(EVEventType.ACTION_COMPLETED, event_types)

        verif_idx = event_types.index(EVEventType.VERIFICATION_RESULT)
        recov_idx = event_types.index(EVEventType.RECOVERY_RESULT)
        act_idx = event_types.index(EVEventType.ACTION_COMPLETED)

        # Recovery and Verification results are emitted before action completes
        self.assertLess(recov_idx, act_idx)
        self.assertLess(verif_idx, act_idx)

        # Verify history events
        hist_events = self.history_store.get_events("task_event_seq_01")
        hist_types = [e.event_type for e in hist_events]
        self.assertIn(TaskHistoryEventType.BACKUP_RESULT, hist_types)
        self.assertIn(TaskHistoryEventType.VERIFICATION_RESULT, hist_types)
        self.assertIn(TaskHistoryEventType.RESTORE_RESULT, hist_types)
        self.assertIn(TaskHistoryEventType.TASK_FAILED, hist_types)


if __name__ == "__main__":
    unittest.main()
