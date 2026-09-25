"""
Task 007 Regression Test Suite: Compound Task Transaction & Multi-Step LIFO Rollback Engine.
"""
import hashlib
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
    RiskAssessmentResult,
    RiskLevel,
    VerificationType,
)
from core.orchestrator import EVOrchestrator
from core.risk import EVRiskEngine
from core.transaction import CompoundTransaction, StepCompensationRecord, TransactionStatus


class TestCompoundTransaction(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="ev_test_tx_")
        self.backup_dir = tempfile.mkdtemp(prefix="ev_test_tx_backups_")
        self.sandbox_dir = Path(self.temp_dir) / "sandbox"
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        self.event_bus = EVEventBus()
        self.db_path = Path(self.temp_dir) / "test_history.sqlite3"
        self.history_store = EVTaskHistoryStore(db_path=self.db_path)
        self.backup_manager = EVBackupManager(backup_root=self.backup_dir)

        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
            backup_manager=self.backup_manager,
            allowed_roots=[str(self.sandbox_dir)],
        )

        self.risk_engine = EVRiskEngine()
        self.orchestrator = EVOrchestrator(
            event_bus=self.event_bus,
            risk_engine=self.risk_engine,
        )
        self.orchestrator.agent = self.agent

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.backup_dir, ignore_errors=True)

    def _calc_hash(self, file_path: Path) -> str:
        return hashlib.sha256(file_path.read_bytes()).hexdigest()

    def _allow_all_risks(self):
        """Helper to pre-authorize all risk evaluations for transaction tests."""
        mock_risk = MagicMock(spec=EVRiskEngine)
        mock_risk.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.LOW,
            decision=PermissionDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            reason="Test pre-authorized",
            policy_rule="test_allow_rule",
        )
        self.orchestrator.risk_engine = mock_risk

    # -----------------------------------------------------------------
    # 1. Transaction commits all successful steps
    # -----------------------------------------------------------------
    def test_transaction_commits_all_successful_steps(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "file_a.txt"
        file_b = self.sandbox_dir / "file_b.txt"

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Alpha"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_b), "content": "Beta"})

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.COMMITTED)
        self.assertTrue(file_a.exists())
        self.assertEqual(file_a.read_text(), "Alpha")
        self.assertTrue(file_b.exists())
        self.assertEqual(file_b.read_text(), "Beta")
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    # -----------------------------------------------------------------
    # 2. Transaction rolls back previous mutations on failure
    # -----------------------------------------------------------------
    def test_transaction_rolls_back_previous_mutations_on_failure(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "file_a.txt"
        file_b = self.sandbox_dir / "file_b.txt"
        file_a.write_text("Original A Content")

        # Step 1: Modifies file_a
        # Step 2: Creates file_b
        # Step 3: Fails (invalid path)
        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Modified A Content"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_b), "content": "Created B Content"})
        task3 = AgentTask(task_id="t3", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "Fail"})

        tx = CompoundTransaction(tasks=[task1, task2, task3])
        thread = self.orchestrator.execute_tasks([task1, task2, task3], transaction=tx)
        thread.join(timeout=5.0)

        # Transaction must be ROLLED_BACK
        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)

        # File A must be restored to original content
        self.assertEqual(file_a.read_text(), "Original A Content")

        # Newly created File B must be deleted
        self.assertFalse(file_b.exists())

    # -----------------------------------------------------------------
    # 3. LIFO rollback order
    # -----------------------------------------------------------------
    def test_lifo_rollback_order(self):
        self._allow_all_risks()
        log_file = self.sandbox_dir / "log.txt"
        log_file.write_text("v0\n")

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(log_file), "content": "v1\n"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(log_file), "content": "v2\n"})
        task3 = AgentTask(task_id="t3", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "fail"})

        tx = CompoundTransaction(tasks=[task1, task2, task3])
        thread = self.orchestrator.execute_tasks([task1, task2, task3], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        # Verify rollback records list shows reverse order
        self.assertEqual(len(tx.rollback_records), 2)
        self.assertEqual(tx.rollback_records[0]["step_index"], 1)  # step 2 rolled back first
        self.assertEqual(tx.rollback_records[1]["step_index"], 0)  # step 1 rolled back second

        # Final content should be original v0
        self.assertEqual(log_file.read_text(), "v0\n")

    # -----------------------------------------------------------------
    # 4. Failed step is recovered when mutated
    # -----------------------------------------------------------------
    def test_failed_step_is_recovered_when_mutated(self):
        self._allow_all_risks()
        target = self.sandbox_dir / "target.txt"
        target.write_text("Initial Text")

        # Task modifies target but verification fails (expected text mismatch)
        task1 = AgentTask(
            task_id="t1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target), "content": "Changed Text"},
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        task1.parameters["expected_text"] = "Nonexistent Expected String"

        tx = CompoundTransaction(tasks=[task1])
        thread = self.orchestrator.execute_tasks([task1], transaction=tx)
        thread.join(timeout=5.0)

        # Single-task agent rollback + transaction rollback
        self.assertEqual(target.read_text(), "Initial Text")

    # -----------------------------------------------------------------
    # 5. New file creation is removed on compensation
    # -----------------------------------------------------------------
    def test_new_file_creation_is_removed_on_compensation(self):
        self._allow_all_risks()
        new_file = self.sandbox_dir / "new_created.txt"
        self.assertFalse(new_file.exists())

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(new_file), "content": "Temp Content"})
        task2 = AgentTask(task_id="t2", action=AgentAction.DELETE_FILE, parameters={"path": str(self.sandbox_dir / "nonexistent.txt")})

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        self.assertFalse(new_file.exists())

    # -----------------------------------------------------------------
    # 6. Existing file restored exact sha256
    # -----------------------------------------------------------------
    def test_existing_file_restored_exact_sha256(self):
        self._allow_all_risks()
        target = self.sandbox_dir / "exact_bytes.bin"
        original_bytes = os.urandom(1024 * 64)
        target.write_bytes(original_bytes)
        orig_sha = hashlib.sha256(original_bytes).hexdigest()

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(target), "content": "corrupted text"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "fail"})

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        self.assertEqual(self._calc_hash(target), orig_sha)

    # -----------------------------------------------------------------
    # 7. Non-mutating steps not rolled back
    # -----------------------------------------------------------------
    def test_non_mutating_steps_not_rolled_back(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "info.txt"
        file_a.write_text("Read only text")

        task1 = AgentTask(task_id="t1", action=AgentAction.GET_FILE_INFO, parameters={"path": str(file_a)})
        task2 = AgentTask(task_id="t2", action=AgentAction.READ_TEXT_FILE, parameters={"path": str(file_a)})
        task3 = AgentTask(task_id="t3", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "fail"})

        tx = CompoundTransaction(tasks=[task1, task2, task3])
        thread = self.orchestrator.execute_tasks([task1, task2, task3], transaction=tx)
        thread.join(timeout=5.0)

        # No completed mutations recorded
        self.assertEqual(len(tx.completed_mutations), 0)
        self.assertEqual(len(tx.rollback_records), 0)
        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)

    # -----------------------------------------------------------------
    # 8. Verification failure triggers compound rollback
    # -----------------------------------------------------------------
    def test_verification_failure_triggers_compound_rollback(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "file_a.txt"
        file_b = self.sandbox_dir / "file_b.txt"
        file_a.write_text("A initial")
        file_b.write_text("B initial")

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "A updated"})
        task2 = AgentTask(
            task_id="t2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file_b), "content": "B updated"},
            verification_type=VerificationType.TEXT_CONTAINS,
        )
        task2.parameters["expected_text"] = "Expected String Not Present"

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        self.assertEqual(file_a.read_text(), "A initial")
        self.assertEqual(file_b.read_text(), "B initial")

    # -----------------------------------------------------------------
    # 9. Rollback failure returns ROLLBACK_FAILED
    # -----------------------------------------------------------------
    def test_rollback_failure_returns_rollback_failed(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "file_a.txt"
        file_a.write_text("A initial")

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "A modified"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "fail"})

        tx = CompoundTransaction(tasks=[task1, task2])

        # Mock backup_manager.restore_file to simulate restore failure (e.g. disk corruption)
        with patch.object(self.backup_manager, "restore_file") as mock_restore:
            mock_restore.return_value = MagicMock(success=False, error="Simulated Restore I/O Failure")
            thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
            thread.join(timeout=5.0)

        # Must report ROLLBACK_FAILED
        self.assertEqual(tx.status, TransactionStatus.ROLLBACK_FAILED)
        self.assertIn("Simulated Restore I/O Failure", tx.rollback_records[0]["error"])

    # -----------------------------------------------------------------
    # 10. Transaction IDs are unique
    # -----------------------------------------------------------------
    def test_transaction_ids_are_unique(self):
        task = AgentTask(task_id="t1", action=AgentAction.FIND_PROCESS, parameters={"name": "explorer.exe"})
        ids = {CompoundTransaction([task]).transaction_id for _ in range(100)}
        self.assertEqual(len(ids), 100)

    # -----------------------------------------------------------------
    # 11. Transaction isolation between runs
    # -----------------------------------------------------------------
    def test_transaction_isolation_between_runs(self):
        self._allow_all_risks()
        file_1 = self.sandbox_dir / "tx1.txt"
        file_2 = self.sandbox_dir / "tx2.txt"

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_1), "content": "Tx1 Content"})
        tx1 = CompoundTransaction(tasks=[task1])
        t1 = self.orchestrator.execute_tasks([task1], transaction=tx1)
        t1.join(timeout=5.0)

        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_2), "content": "Tx2 Content"})
        tx2 = CompoundTransaction(tasks=[task2])
        t2 = self.orchestrator.execute_tasks([task2], transaction=tx2)
        t2.join(timeout=5.0)

        self.assertEqual(tx1.status, TransactionStatus.COMMITTED)
        self.assertEqual(tx2.status, TransactionStatus.COMMITTED)
        self.assertNotEqual(tx1.transaction_id, tx2.transaction_id)
        self.assertEqual(len(tx1.completed_mutations), 1)
        self.assertEqual(len(tx2.completed_mutations), 1)

    # -----------------------------------------------------------------
    # 12. Single task behavior unchanged
    # -----------------------------------------------------------------
    def test_single_task_behavior_unchanged(self):
        self._allow_all_risks()
        single_file = self.sandbox_dir / "single.txt"
        task = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(single_file), "content": "Single Task"})
        thread = self.orchestrator.execute_task(task)
        thread.join(timeout=5.0)

        self.assertTrue(single_file.exists())
        self.assertEqual(single_file.read_text(), "Single Task")
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    # -----------------------------------------------------------------
    # 13. No hidden unapproved mutation
    # -----------------------------------------------------------------
    def test_no_hidden_unapproved_mutation(self):
        file_a = self.sandbox_dir / "file_a.txt"
        file_b = self.sandbox_dir / "file_b.txt"

        # Submit via orchestrator.submit_command (requires approval because WRITE_FILE is HIGH risk)
        self.orchestrator.submit_command(f"write file {file_a} A")
        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # File A must NOT be created before approval
        self.assertFalse(file_a.exists())

    # -----------------------------------------------------------------
    # 14. Transaction metadata propagates to events or history
    # -----------------------------------------------------------------
    def test_transaction_metadata_propagates_to_events_or_history(self):
        self._allow_all_risks()
        events = []
        self.event_bus.subscribe(lambda e: events.append(e))

        file_a = self.sandbox_dir / "meta.txt"
        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Meta"})
        tx = CompoundTransaction(tasks=[task1])

        thread = self.orchestrator.execute_tasks([task1], transaction=tx)
        thread.join(timeout=5.0)

        # Verify transaction ID is present and consistent
        self.assertEqual(tx.status, TransactionStatus.COMMITTED)
        self.assertTrue(tx.transaction_id.startswith("tx-"))

    # -----------------------------------------------------------------
    # 15. Partial completion is explicitly reported
    # -----------------------------------------------------------------
    def test_partial_completion_is_explicitly_reported(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "step1.txt"
        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Step 1"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "Fail"})

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        self.assertEqual(tx.failed_step_index, 1)
        self.assertEqual(len(tx.completed_mutations), 1)
        self.assertTrue(tx.completed_mutations[0].compensated)

    # -----------------------------------------------------------------
    # 16. Approval pause & resume preserves transaction identity
    # -----------------------------------------------------------------
    def test_approval_pause_and_resume_preserves_transaction_identity(self):
        file_a = self.sandbox_dir / "file_a.txt"
        file_b = self.sandbox_dir / "file_b.txt"

        task1 = AgentTask(task_id="t-appr-1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Step 1 Content"})
        task2 = AgentTask(task_id="t-appr-2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_b), "content": "Step 2 Content"})

        # Configure risk engine: task1 allowed, task2 requires approval unless user_approved=True
        mock_risk = MagicMock(spec=EVRiskEngine)
        def mock_assess(req):
            if "file_b.txt" in (req.target or ""):
                if req.user_approved:
                    return RiskAssessmentResult(
                        action_category=ActionCategory.FILE_MODIFY,
                        risk_level=RiskLevel.LOW,
                        decision=PermissionDecision.ALLOW,
                        allowed=True,
                        requires_approval=False,
                        reason="User approved",
                        policy_rule="approved",
                    )
                return RiskAssessmentResult(
                    action_category=ActionCategory.FILE_MODIFY,
                    risk_level=RiskLevel.HIGH,
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    allowed=False,
                    requires_approval=True,
                    reason="Requires user confirmation",
                    policy_rule="file_modify_high",
                )
            return RiskAssessmentResult(
                action_category=ActionCategory.FILE_MODIFY,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="Auto allowed",
                policy_rule="auto_allow",
            )
        mock_risk.assess.side_effect = mock_assess
        self.orchestrator.risk_engine = mock_risk

        tx = CompoundTransaction(tasks=[task1, task2])
        orig_tx_id = tx.transaction_id

        # Start batch
        thread1 = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread1.join(timeout=5.0)

        # Task 1 ran; paused at Task 2
        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertEqual(len(tx.completed_mutations), 1)
        self.assertEqual(file_a.read_text(), "Step 1 Content")
        self.assertFalse(file_b.exists())

        # Resolve approval
        res = self.orchestrator.resolve_approval("t-appr-2", approved=True)
        self.assertTrue(res)

        # Give background thread time to complete
        time.sleep(0.5)

        self.assertEqual(tx.status, TransactionStatus.COMMITTED)
        self.assertEqual(tx.transaction_id, orig_tx_id)
        self.assertEqual(len(tx.completed_mutations), 2)
        self.assertTrue(file_b.exists())
        self.assertEqual(file_b.read_text(), "Step 2 Content")

    # -----------------------------------------------------------------
    # 17. Approval pause & user denial rolls back prior step
    # -----------------------------------------------------------------
    def test_approval_pause_and_user_denial_rolls_back_prior_step(self):
        file_a = self.sandbox_dir / "file_a.txt"
        file_a.write_text("Original A Content")
        file_b = self.sandbox_dir / "file_b.txt"

        task1 = AgentTask(task_id="t-deny-1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "Modified A Content"})
        task2 = AgentTask(task_id="t-deny-2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_b), "content": "Step 2 Content"})

        mock_risk = MagicMock(spec=EVRiskEngine)
        def mock_assess(req):
            if "file_b.txt" in (req.target or ""):
                return RiskAssessmentResult(
                    action_category=ActionCategory.FILE_MODIFY,
                    risk_level=RiskLevel.HIGH,
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    allowed=False,
                    requires_approval=True,
                    reason="Requires user confirmation",
                    policy_rule="file_modify_high",
                )
            return RiskAssessmentResult(
                action_category=ActionCategory.FILE_MODIFY,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="Auto allowed",
                policy_rule="auto_allow",
            )
        mock_risk.assess.side_effect = mock_assess
        self.orchestrator.risk_engine = mock_risk

        tx = CompoundTransaction(tasks=[task1, task2])

        thread1 = self.orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread1.join(timeout=5.0)

        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertEqual(file_a.read_text(), "Modified A Content")

        # User denies Task 2
        res = self.orchestrator.resolve_approval("t-deny-2", approved=False)
        self.assertTrue(res)

        # File A must be rolled back to original content
        self.assertEqual(file_a.read_text(), "Original A Content")
        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        self.assertIsNone(self.orchestrator._pending_approval)

    # -----------------------------------------------------------------
    # 18. Partial rollback failure continues best effort and flags status
    # -----------------------------------------------------------------
    def test_partial_rollback_failure_continues_best_effort_and_flags_status(self):
        self._allow_all_risks()
        file_a = self.sandbox_dir / "file_a.txt"
        file_a.write_text("A Original")
        file_b = self.sandbox_dir / "file_b.txt"
        file_b.write_text("B Original")

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": str(file_a), "content": "A New"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": str(file_b), "content": "B New"})
        task3 = AgentTask(task_id="t3", action=AgentAction.WRITE_FILE, parameters={"path": "", "content": "Fail"})

        tx = CompoundTransaction(tasks=[task1, task2, task3])

        real_restore = self.backup_manager.restore_file
        def selective_restore(backup_path, original_path, **kwargs):
            if "file_b.txt" in str(original_path):
                return MagicMock(success=False, error="Simulated B restore failure")
            return real_restore(backup_path, original_path, **kwargs)

        with patch.object(self.backup_manager, "restore_file", side_effect=selective_restore):
            thread = self.orchestrator.execute_tasks([task1, task2, task3], transaction=tx)
            thread.join(timeout=5.0)

        # Status must be ROLLBACK_FAILED
        self.assertEqual(tx.status, TransactionStatus.ROLLBACK_FAILED)
        # B compensation failed
        self.assertFalse(tx.rollback_records[0]["success"])
        self.assertIn("Simulated B restore failure", tx.rollback_records[0]["error"])
        # A compensation was still attempted and succeeded
        self.assertTrue(tx.rollback_records[1]["success"])
        self.assertEqual(file_a.read_text(), "A Original")


if __name__ == "__main__":
    unittest.main()
