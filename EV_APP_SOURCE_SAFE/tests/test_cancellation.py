"""
Comprehensive unit, concurrency, and integration tests for Phase 5 Task 010:
Cooperative Cancellation & Deterministic STOP Runtime.
"""
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from core.agent import EVAgent
from core.backup import EVBackupManager
from core.cancellation import (
    CancellationSource,
    CancellationState,
    CancellationToken,
    OperationCancelledError,
)
from core.events import EVEventBus
from core.models import (
    ActionCategory,
    AgentAction,
    AgentStatus,
    AgentTask,
    EVEventType,
    EVState,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)
from core.orchestrator import EVOrchestrator
from core.risk import EVRiskEngine
from core.transaction import CompoundTransaction, TransactionStatus


def make_risk_result(
    decision: PermissionDecision = PermissionDecision.ALLOW,
    risk_level: RiskLevel = RiskLevel.LOW,
    action_category: ActionCategory = ActionCategory.READ_ONLY_OBSERVATION,
    reason: str = "Test assessment",
    requires_approval: bool = False,
    allowed: bool = True,
    policy_rule: str = "RULE_DEFAULT",
) -> RiskAssessmentResult:
    """Helper to construct valid RiskAssessmentResult instances."""
    return RiskAssessmentResult(
        action_category=action_category,
        risk_level=risk_level,
        decision=decision,
        allowed=allowed,
        requires_approval=requires_approval,
        reason=reason,
        policy_rule=policy_rule,
    )


class TestCancellationTokenBasics(unittest.TestCase):
    """Test suite for CancellationToken behavior, state snapshots, and error raising."""

    def test_token_initial_state(self):
        """Token initializes uncancelled with clean state."""
        token = CancellationToken()
        self.assertFalse(token.is_cancelled())
        state = token.state
        self.assertFalse(state.cancellation_requested)
        self.assertIsNone(state.timestamp)
        self.assertIsNone(state.reason)
        self.assertIsNone(state.source)

    def test_token_cancellation_transition(self):
        """Cancelling token updates state snapshot and returns True."""
        token = CancellationToken()
        result = token.cancel(reason="User abort", source=CancellationSource.GUI_BUTTON)
        self.assertTrue(result)
        self.assertTrue(token.is_cancelled())
        state = token.state
        self.assertTrue(state.cancellation_requested)
        self.assertEqual(state.reason, "User abort")
        self.assertEqual(state.source, CancellationSource.GUI_BUTTON)
        self.assertIsNotNone(state.timestamp)

    def test_token_idempotency(self):
        """Repeated cancel calls return False and preserve first cancellation reason."""
        token = CancellationToken()
        first = token.cancel(reason="First cancel", source=CancellationSource.USER_COMMAND)
        second = token.cancel(reason="Second cancel", source=CancellationSource.TIMEOUT)
        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(token.state.reason, "First cancel")
        self.assertEqual(token.state.source, CancellationSource.USER_COMMAND)

    def test_throw_if_cancelled(self):
        """throw_if_cancelled raises OperationCancelledError only when cancelled."""
        token = CancellationToken()
        token.throw_if_cancelled()  # Must not raise

        token.cancel(reason="Operation aborted", source=CancellationSource.USER_COMMAND)
        with self.assertRaises(OperationCancelledError) as ctx:
            token.throw_if_cancelled()
        self.assertIn("Operation aborted", str(ctx.exception))
        self.assertEqual(ctx.exception.source, CancellationSource.USER_COMMAND)

    def test_register_callback_before_cancellation(self):
        """Callbacks registered before cancellation are executed upon cancel()."""
        token = CancellationToken()
        called = []
        token.register_callback(lambda: called.append("cb1"))
        token.register_callback(lambda: called.append("cb2"))
        self.assertEqual(called, [])

        token.cancel(reason="Triggered", source=CancellationSource.USER_COMMAND)
        self.assertEqual(called, ["cb1", "cb2"])

    def test_register_callback_after_cancellation(self):
        """Callbacks registered after token is already cancelled execute immediately."""
        token = CancellationToken()
        token.cancel(reason="Already cancelled", source=CancellationSource.USER_COMMAND)

        called = []
        registered = token.register_callback(lambda: called.append("late_cb"))
        self.assertFalse(registered)
        self.assertEqual(called, ["late_cb"])

    def test_callback_exception_safety(self):
        """Exceptions in callbacks do not crash token.cancel() or prevent other callbacks."""
        token = CancellationToken()
        called = []

        def faulty_callback():
            raise RuntimeError("Callback crash")

        token.register_callback(faulty_callback)
        token.register_callback(lambda: called.append("survivor"))

        token.cancel()
        self.assertTrue(token.is_cancelled())
        self.assertEqual(called, ["survivor"])


class TestCancellationTokenConcurrency(unittest.TestCase):
    """Test suite for concurrent CancellationToken operations."""

    def test_concurrent_cancel_calls(self):
        """Multiple threads racing to cancel token results in exactly one True return."""
        token = CancellationToken()
        results = []

        def racer(idx):
            res = token.cancel(reason=f"Racer {idx}", source=CancellationSource.USER_COMMAND)
            results.append(res)

        threads = [threading.Thread(target=racer, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(results.count(True), 1)
        self.assertEqual(results.count(False), 19)
        self.assertTrue(token.is_cancelled())


class TestOrchestratorControlCommands(unittest.TestCase):
    """Test suite for deterministic STOP / CANCEL / ABORT control command interception."""

    def setUp(self):
        self.event_bus = EVEventBus()
        self.orchestrator = EVOrchestrator(event_bus=self.event_bus)

    def test_stop_command_no_active_work(self):
        """STOP command when idle returns harmless status and does not invoke Brain."""
        result = self.orchestrator.submit_command("stop")
        self.assertIsNone(result)
        events = self.event_bus.get_history()
        self.assertTrue(any("No active execution" in (e.message or "") for e in events))

    def test_cancel_command_case_and_whitespace(self):
        """Control commands are case-insensitive and whitespace-tolerant."""
        for cmd in ["  CANCEL  ", "Abort", "sToP"]:
            res = self.orchestrator.submit_command(cmd)
            self.assertIsNone(res)

    def test_control_commands_do_not_invoke_brain(self):
        """STOP/CANCEL commands never query the router or LLM."""
        with patch.object(self.orchestrator.router, "route") as mock_route:
            self.orchestrator.submit_command("stop")
            self.orchestrator.submit_command("cancel")
            self.orchestrator.submit_command("abort")
            mock_route.assert_not_called()


class TestPendingApprovalCancellation(unittest.TestCase):
    """Test suite for cancelling pending approvals and preventing stale approval acceptance."""

    def setUp(self):
        self.event_bus = EVEventBus()
        self.orchestrator = EVOrchestrator(event_bus=self.event_bus)

    def test_cancel_pending_approval_via_method(self):
        """cancel_pending_approval clears pending state and resets orchestrator to IDLE."""
        task = AgentTask(task_id="t-pend-1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\a.txt"})
        with self.orchestrator._pending_lock:
            self.orchestrator._pending_approval = {
                "task": task,
                "remaining_tasks": [],
                "risk_assessment": make_risk_result(
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    risk_level=RiskLevel.MEDIUM,
                    action_category=ActionCategory.FILE_MODIFY,
                    reason="Needs approval",
                    requires_approval=True,
                    allowed=False,
                ),
                "transaction": CompoundTransaction(tasks=[task]),
            }
        self.event_bus.set_state(EVState.AWAITING_APPROVAL)

        cancelled = self.orchestrator.cancel_pending_approval(reason="User rejected in UI")
        self.assertTrue(cancelled)
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)
        with self.orchestrator._pending_lock:
            self.assertIsNone(self.orchestrator._pending_approval)

    def test_cancel_pending_approval_via_stop_command(self):
        """Submitting 'stop' while in AWAITING_APPROVAL cancels the pending task."""
        task = AgentTask(task_id="t-pend-2", action=AgentAction.DELETE_FILE, parameters={"path": "C:\\sandbox\\b.txt"})
        with self.orchestrator._pending_lock:
            self.orchestrator._pending_approval = {
                "task": task,
                "remaining_tasks": [],
                "risk_assessment": make_risk_result(
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    risk_level=RiskLevel.HIGH,
                    action_category=ActionCategory.FILE_DELETE,
                    reason="Needs approval",
                    requires_approval=True,
                    allowed=False,
                ),
                "transaction": CompoundTransaction(tasks=[task]),
            }
        self.event_bus.set_state(EVState.AWAITING_APPROVAL)

        self.orchestrator.submit_command("stop")
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)
        with self.orchestrator._pending_lock:
            self.assertIsNone(self.orchestrator._pending_approval)

    def test_stale_approval_resolution_rejected_after_cancellation(self):
        """Resolving an approval after cancellation returns False and does not execute."""
        task = AgentTask(task_id="t-pend-3", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\c.txt"})
        with self.orchestrator._pending_lock:
            self.orchestrator._pending_approval = {
                "task": task,
                "remaining_tasks": [],
                "risk_assessment": make_risk_result(
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    risk_level=RiskLevel.MEDIUM,
                    action_category=ActionCategory.FILE_MODIFY,
                    reason="Needs approval",
                    requires_approval=True,
                    allowed=False,
                ),
                "transaction": CompoundTransaction(tasks=[task]),
            }
        self.event_bus.set_state(EVState.AWAITING_APPROVAL)

        # Cancel pending approval
        self.orchestrator.cancel_pending_approval(reason="Cancelled by user")

        # Attempt to resolve stale approval
        resolved = self.orchestrator.resolve_approval(task_id="t-pend-3", approved=True)
        self.assertFalse(resolved)
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)


class TestActiveExecutionCancellationAndRollback(unittest.TestCase):
    """Test suite for active background execution interruption and compound LIFO rollback."""

    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.sandbox_path = Path(self.temp_dir.name) / "sandbox"
        self.sandbox_path.mkdir(parents=True, exist_ok=True)
        self.backup_path = Path(self.temp_dir.name) / "backups"
        self.backup_path.mkdir(parents=True, exist_ok=True)
        self.event_bus = EVEventBus()
        self.orchestrator = EVOrchestrator(event_bus=self.event_bus)
        self.backup_manager = EVBackupManager(backup_root=str(self.backup_path))
        self.orchestrator.agent = EVAgent(
            history_store=self.orchestrator.history_store,
            event_bus=self.event_bus,
            backup_manager=self.backup_manager,
            allowed_roots=[str(self.sandbox_path)],
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cancel_active_task_stops_next_step(self):
        """Active cancellation token prevents subsequent batch tasks from executing."""
        file1 = self.sandbox_path / "step1.txt"
        file2 = self.sandbox_path / "step2.txt"

        task1 = AgentTask(
            task_id="t-step-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file1), "content": "data 1"},
        )
        task2 = AgentTask(
            task_id="t-step-2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file2), "content": "data 2"},
        )

        token = CancellationToken()
        original_run = self.orchestrator.agent.run

        def intercepting_run(task):
            res = original_run(task)
            if task.task_id == "t-step-1":
                token.cancel(reason="User hit STOP after step 1", source=CancellationSource.USER_COMMAND)
            return res

        self.orchestrator.agent.run = intercepting_run

        with patch.object(self.orchestrator, "_assess_task_risk") as mock_risk:
            mock_risk.return_value = make_risk_result(
                decision=PermissionDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                action_category=ActionCategory.FILE_CREATE,
                reason="Safe sandbox",
                requires_approval=False,
                allowed=True,
            )
            tx = CompoundTransaction(tasks=[task1, task2])
            thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx, cancellation_token=token)
            thread.join(timeout=5.0)

        # Step 2 must never have created file2
        self.assertFalse(file2.exists())
        # Transaction must be rolled back, restoring step 1 (unlinking newly created file1)
        self.assertFalse(file1.exists())
        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)

    def test_cancel_active_task_via_submit_command_stop(self):
        """Submitting 'stop' while a long task runs triggers cooperative cancellation."""
        file1 = self.sandbox_path / "long1.txt"
        file2 = self.sandbox_path / "long2.txt"

        task1 = AgentTask(
            task_id="t-long-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file1), "content": "long 1"},
        )
        task2 = AgentTask(
            task_id="t-long-2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file2), "content": "long 2"},
        )

        original_run = self.orchestrator.agent.run

        def slow_run(task):
            if task.task_id == "t-long-1":
                time.sleep(0.1)
            return original_run(task)

        self.orchestrator.agent.run = slow_run

        with patch.object(self.orchestrator, "_assess_task_risk") as mock_risk:
            mock_risk.return_value = make_risk_result(
                decision=PermissionDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                action_category=ActionCategory.FILE_CREATE,
                reason="Safe sandbox",
                requires_approval=False,
                allowed=True,
            )
            tx = CompoundTransaction(tasks=[task1, task2])
            thread = self.orchestrator.execute_tasks([task1, task2], transaction=tx)

            # Issue stop command while thread is executing
            time.sleep(0.02)
            self.orchestrator.submit_command("stop")
            thread.join(timeout=5.0)

        self.assertFalse(file2.exists())
        self.assertIn(tx.status, (TransactionStatus.ROLLED_BACK, TransactionStatus.ROLLING_BACK))

    def test_compound_transaction_lifo_rollback_order_on_cancellation(self):
        """Cancellation triggers rollback of completed steps in reverse LIFO order."""
        file1 = self.sandbox_path / "orig1.txt"
        file2 = self.sandbox_path / "orig2.txt"
        file1.write_text("initial 1")
        file2.write_text("initial 2")

        task1 = AgentTask(
            task_id="t-lifo-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file1), "content": "modified 1"},
        )
        task2 = AgentTask(
            task_id="t-lifo-2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(file2), "content": "modified 2"},
        )
        task3 = AgentTask(
            task_id="t-lifo-3",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(self.sandbox_path / "never.txt"), "content": "never"},
        )

        token = CancellationToken()
        original_run = self.orchestrator.agent.run

        def intercept_after_step2(task):
            res = original_run(task)
            if task.task_id == "t-lifo-2":
                token.cancel(reason="Aborted after step 2", source=CancellationSource.USER_COMMAND)
            return res

        self.orchestrator.agent.run = intercept_after_step2

        with patch.object(self.orchestrator, "_assess_task_risk") as mock_risk:
            mock_risk.return_value = make_risk_result(
                decision=PermissionDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                action_category=ActionCategory.FILE_MODIFY,
                reason="Safe sandbox",
                requires_approval=False,
                allowed=True,
            )
            tx = CompoundTransaction(tasks=[task1, task2, task3])
            thread = self.orchestrator.execute_tasks([task1, task2, task3], transaction=tx, cancellation_token=token)
            thread.join(timeout=5.0)

        # Step 3 never created
        self.assertFalse((self.sandbox_path / "never.txt").exists())
        # Step 2 and Step 1 restored to original text via LIFO rollback
        self.assertEqual(file1.read_text(), "initial 1")
        self.assertEqual(file2.read_text(), "initial 2")
        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)
        # Rollback records must be in reverse order (step 2, then step 1)
        self.assertEqual(tx.rollback_records[0]["task_id"], "t-lifo-2")
        self.assertEqual(tx.rollback_records[1]["task_id"], "t-lifo-1")

    def test_non_reversible_action_on_cancellation_honesty(self):
        """Interruption does not fabricate rollback for non-reversible operations."""
        task_stop = AgentTask(
            task_id="t-proc-stop",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 9999, "name": "dummy.exe"},
        )
        task_write = AgentTask(
            task_id="t-write-next",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(self.sandbox_path / "next.txt"), "content": "data"},
        )

        token = CancellationToken()
        token.cancel(reason="Immediate cancel before start", source=CancellationSource.USER_COMMAND)

        with patch.object(self.orchestrator, "_assess_task_risk") as mock_risk:
            mock_risk.return_value = make_risk_result(
                decision=PermissionDecision.ALLOW,
                risk_level=RiskLevel.LOW,
                action_category=ActionCategory.PROCESS_STOP,
                reason="Safe sandbox",
                requires_approval=False,
                allowed=True,
            )
            tx = CompoundTransaction(tasks=[task_stop, task_write])
            thread = self.orchestrator.execute_tasks([task_stop, task_write], transaction=tx, cancellation_token=token)
            thread.join(timeout=5.0)

        self.assertFalse((self.sandbox_path / "next.txt").exists())
        self.assertNotEqual(tx.status, TransactionStatus.COMMITTED)


class TestCancellationEdgeCasesAndRaces(unittest.TestCase):
    """Test suite for race conditions, repeated cancellations, and rapid re-submission."""

    def setUp(self):
        self.event_bus = EVEventBus()
        self.orchestrator = EVOrchestrator(event_bus=self.event_bus)

    def test_double_cancel_active_task_returns_false(self):
        """Second call to cancel_active_task is a clean no-op."""
        token = CancellationToken()
        with self.orchestrator._token_lock:
            self.orchestrator._active_cancellation_token = token

        first = self.orchestrator.cancel_active_task(reason="Stop 1")
        second = self.orchestrator.cancel_active_task(reason="Stop 2")
        self.assertTrue(first)
        self.assertFalse(second)

    def test_simultaneous_cancellation_and_resolve_approval(self):
        """Resolving approval concurrently with cancellation results in deterministic state without deadlock."""
        task = AgentTask(task_id="t-race-1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\race.txt"})
        with self.orchestrator._pending_lock:
            self.orchestrator._pending_approval = {
                "task": task,
                "remaining_tasks": [],
                "risk_assessment": make_risk_result(
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    risk_level=RiskLevel.MEDIUM,
                    action_category=ActionCategory.FILE_MODIFY,
                    reason="Needs approval",
                    requires_approval=True,
                    allowed=False,
                ),
                "transaction": CompoundTransaction(tasks=[task]),
            }
        self.event_bus.set_state(EVState.AWAITING_APPROVAL)

        res_cancel = []
        res_approve = []

        t1 = threading.Thread(target=lambda: res_cancel.append(self.orchestrator.cancel_pending_approval()))
        t2 = threading.Thread(target=lambda: res_approve.append(self.orchestrator.resolve_approval("t-race-1", approved=True)))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one should have consumed the pending approval state
        self.assertTrue(any(res_cancel) or any(res_approve))
        with self.orchestrator._pending_lock:
            self.assertIsNone(self.orchestrator._pending_approval)


if __name__ == "__main__":
    unittest.main()
