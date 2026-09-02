"""
Comprehensive unit, concurrency, and lifecycle tests for Task 012:
Command Queue & Priority Runtime.
"""
from __future__ import annotations

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from core.cancellation import CancellationSource, CancellationToken
from core.events import EVEventBus, EVEventType
from core.models import (
    ActionCategory,
    AgentAction,
    AgentStatus,
    AgentTask,
    EVState,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
)
from core.orchestrator import EVOrchestrator
from core.task_queue import (
    EVTaskQueue,
    QueuedCommand,
    QueueFullError,
    QueueItemStatus,
    TaskExecutionThread,
    TaskPriority,
)
from core.transaction import CompoundTransaction, TransactionStatus


def make_test_task(task_id: str = "t1", action: AgentAction = AgentAction.FIND_PROCESS) -> AgentTask:
    """Helper to construct valid AgentTask instances."""
    return AgentTask(
        task_id=task_id,
        action=action,
        parameters={"name": "test.exe"},
    )


def make_risk_result(
    decision: PermissionDecision = PermissionDecision.ALLOW,
    risk_level: RiskLevel = RiskLevel.LOW,
    action_category: ActionCategory = ActionCategory.READ_ONLY_OBSERVATION,
    reason: str = "Test risk assessment",
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


# ==============================================================================
# 1. QUEUE CORE TESTS (Items 1-8)
# ==============================================================================

class TestQueueCore(unittest.TestCase):
    """Verify basic priority queue mechanics, FIFO tie-breaking, and capacity bounds."""

    def test_01_enqueue_basic(self) -> None:
        """1. Basic enqueue operation."""
        queue = EVTaskQueue(max_capacity=10)
        task = make_test_task("t1")
        item = queue.enqueue("find test", [task], priority=TaskPriority.USER_INTERACTIVE)
        self.assertEqual(queue.size(), 1)
        self.assertEqual(item.command_text, "find test")
        self.assertEqual(item.status, QueueItemStatus.QUEUED)
        self.assertFalse(queue.is_empty())

    def test_02_dequeue_basic(self) -> None:
        """2. Basic dequeue/pop operation."""
        queue = EVTaskQueue(max_capacity=10)
        task = make_test_task("t1")
        queue.enqueue("find test", [task], priority=TaskPriority.USER_INTERACTIVE)
        item = queue.pop()
        self.assertIsNotNone(item)
        self.assertEqual(item.status, QueueItemStatus.DISPATCHING)
        self.assertEqual(queue.size(), 0)
        self.assertTrue(queue.is_empty())

    def test_03_fifo_same_priority(self) -> None:
        """3. Strict FIFO preservation within identical priority."""
        queue = EVTaskQueue(max_capacity=10)
        t1 = make_test_task("t1")
        t2 = make_test_task("t2")
        t3 = make_test_task("t3")

        i1 = queue.enqueue("cmd 1", [t1], priority=TaskPriority.USER_INTERACTIVE)
        i2 = queue.enqueue("cmd 2", [t2], priority=TaskPriority.USER_INTERACTIVE)
        i3 = queue.enqueue("cmd 3", [t3], priority=TaskPriority.USER_INTERACTIVE)

        self.assertEqual(queue.pop().command_id, i1.command_id)
        self.assertEqual(queue.pop().command_id, i2.command_id)
        self.assertEqual(queue.pop().command_id, i3.command_id)

    def test_04_priority_ordering(self) -> None:
        """4. Strict priority ordering: CONTROL > APPROVAL_RESUME > USER_INTERACTIVE > SYSTEM_REPAIR > BACKGROUND."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")

        bg = queue.enqueue("bg", [t], priority=TaskPriority.BACKGROUND)
        ui = queue.enqueue("ui", [t], priority=TaskPriority.USER_INTERACTIVE)
        ctrl = queue.enqueue("ctrl", [t], priority=TaskPriority.CONTROL)
        appr = queue.enqueue("appr", [t], priority=TaskPriority.APPROVAL_RESUME)
        repair = queue.enqueue("repair", [t], priority=TaskPriority.SYSTEM_REPAIR)

        self.assertEqual(queue.pop().command_id, ctrl.command_id)
        self.assertEqual(queue.pop().command_id, appr.command_id)
        self.assertEqual(queue.pop().command_id, ui.command_id)
        self.assertEqual(queue.pop().command_id, repair.command_id)
        self.assertEqual(queue.pop().command_id, bg.command_id)

    def test_05_capacity_limit(self) -> None:
        """5. Capacity bound enforcement."""
        queue = EVTaskQueue(max_capacity=3)
        t = make_test_task("t")

        queue.enqueue("1", [t])
        queue.enqueue("2", [t])
        queue.enqueue("3", [t])
        self.assertTrue(queue.is_full())

        with self.assertRaises(QueueFullError):
            queue.enqueue("4", [t])

    def test_06_queue_full_fail_closed(self) -> None:
        """6. Queue full fails closed and preserves existing items."""
        queue = EVTaskQueue(max_capacity=2)
        t = make_test_task("t")

        i1 = queue.enqueue("1", [t])
        i2 = queue.enqueue("2", [t])

        with self.assertRaises(QueueFullError):
            queue.enqueue("overflow", [t])

        self.assertEqual(queue.size(), 2)
        self.assertEqual(queue.pop().command_id, i1.command_id)
        self.assertEqual(queue.pop().command_id, i2.command_id)

    def test_07_unique_sequence_ordering(self) -> None:
        """7. Monotonic sequence counter increments sequentially."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")

        i1 = queue.enqueue("1", [t])
        i2 = queue.enqueue("2", [t])
        self.assertLess(i1.sequence, i2.sequence)

    def test_08_thread_safe_concurrent_enqueue(self) -> None:
        """8. Thread-safe concurrent enqueuing by multiple producers."""
        queue = EVTaskQueue(max_capacity=50)
        errors: list[Exception] = []

        def producer(p_id: int) -> None:
            try:
                for j in range(5):
                    t = make_test_task(f"t_{p_id}_{j}")
                    queue.enqueue(f"cmd_{p_id}_{j}", [t], priority=TaskPriority.USER_INTERACTIVE)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=producer, args=(i,)) for i in range(10)]
        for th in threads:
            th.start()
        for th in threads:
            th.join(timeout=5.0)

        self.assertEqual(len(errors), 0)
        self.assertEqual(queue.size(), 50)


# ==============================================================================
# 2. CANCELLATION TESTS (Items 9-16)
# ==============================================================================

class TestQueueCancellation(unittest.TestCase):
    """Verify cancellation semantics for queued commands, active commands, and approval."""

    def test_09_queued_cancellation(self) -> None:
        """9. Cancel a queued task before execution begins."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")
        item = queue.enqueue("cmd", [t])

        success = queue.cancel(item.command_id, reason="User cancelled")
        self.assertTrue(success)
        self.assertEqual(item.status, QueueItemStatus.CANCELLED)
        self.assertTrue(item.cancellation_token.is_cancelled())
        self.assertTrue(item.completion_event.is_set())
        self.assertEqual(queue.size(), 0)

    def test_10_queued_cancellation_does_not_rollback(self) -> None:
        """10. Cancelling a queued command does not invoke transaction rollback."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")
        tx = CompoundTransaction(tasks=[t])
        item = queue.enqueue("cmd", [t], transaction=tx)

        queue.cancel(item.command_id)
        # Transaction was never begun or mutated; rollback should remain untouched
        self.assertEqual(tx.status, TransactionStatus.PENDING)
        self.assertEqual(len(tx.rollback_records), 0)

    def test_11_targeted_cancellation(self) -> None:
        """11. Cancelling one specific queued command leaves other queued items intact."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")

        i1 = queue.enqueue("cmd 1", [t])
        i2 = queue.enqueue("cmd 2", [t])
        i3 = queue.enqueue("cmd 3", [t])

        # Cancel i2 specifically
        self.assertTrue(queue.cancel(i2.command_id))
        self.assertEqual(queue.size(), 2)
        self.assertEqual(queue.pop().command_id, i1.command_id)
        self.assertEqual(queue.pop().command_id, i3.command_id)

    def test_12_cancellation_idempotency(self) -> None:
        """12. Repeated cancellation of the same item returns False safely."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")
        item = queue.enqueue("cmd", [t])

        self.assertTrue(queue.cancel(item.command_id))
        self.assertFalse(queue.cancel(item.command_id))

    def test_13_cancel_race_with_dequeue(self) -> None:
        """13. Race between worker dequeue and cancellation handles cancelled token cleanly."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")
        item = queue.enqueue("cmd", [t])

        # Dequeue item
        popped = queue.pop()
        self.assertIsNotNone(popped)
        # Cancel after pop
        popped.cancellation_token.cancel("Cancelled right after pop")
        self.assertTrue(popped.cancellation_token.is_cancelled())

    def test_14_cancel_all_purges_queue(self) -> None:
        """14. cancel_all purges all waiting queued items."""
        queue = EVTaskQueue(max_capacity=10)
        t = make_test_task("t")

        i1 = queue.enqueue("cmd 1", [t])
        i2 = queue.enqueue("cmd 2", [t])

        cancelled_count = queue.cancel_all(reason="Mass cancel")
        self.assertEqual(cancelled_count, 2)
        self.assertEqual(queue.size(), 0)
        self.assertTrue(i1.completion_event.is_set())
        self.assertTrue(i2.completion_event.is_set())
        self.assertEqual(i1.status, QueueItemStatus.CANCELLED)
        self.assertEqual(i2.status, QueueItemStatus.CANCELLED)

    def test_15_active_cancellation_uses_task010_token(self) -> None:
        """15. Active execution cancellation triggers Task 010 token and rolls back."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus)

        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test.txt", "content": "hello"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test2.txt", "content": "world"})
        tx = CompoundTransaction(tasks=[task1, task2])

        token = CancellationToken()
        token.cancel("Immediate cancel test")

        # execute_tasks with already-cancelled token
        thread = orchestrator.execute_tasks([task1, task2], transaction=tx, cancellation_token=token)
        thread.join(timeout=5.0)

        self.assertEqual(tx.status, TransactionStatus.ROLLED_BACK)

    def test_16_approval_cancellation(self) -> None:
        """16. Cancelling pending approval unblocks queue worker cleanly."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)
        orchestrator._assess_task_risk = lambda task, user_approved=False: make_risk_result(
            PermissionDecision.REQUIRE_APPROVAL
        )

        task = AgentTask(task_id="mut1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test.txt", "content": "data"})
        cmd = orchestrator.task_queue.enqueue("write file", [task])

        for _ in range(30):
            if cmd.status == QueueItemStatus.AWAITING_APPROVAL:
                break
            time.sleep(0.05)

        self.assertEqual(cmd.status, QueueItemStatus.AWAITING_APPROVAL)
        orchestrator.cancel_pending_approval("User refused approval")
        self.assertEqual(cmd.status, QueueItemStatus.CANCELLED)
        self.assertTrue(cmd.completion_event.is_set())
        orchestrator.stop_queue_worker()


# ==============================================================================
# 3. APPROVAL & SEQUENCING TESTS (Items 17-22)
# ==============================================================================

class TestApprovalAndSequencing(unittest.TestCase):
    """Verify that approval gating properly pauses and resumes the queue worker."""

    def test_17_approval_required_pauses_queue(self) -> None:
        """17. A task requiring approval pauses the queue worker."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        # Mock risk engine to require approval for t1 and allow t2
        t1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\file.txt"})
        t2 = AgentTask(task_id="t2", action=AgentAction.FIND_PROCESS, parameters={"name": "proc.exe"})

        def mock_assess(task, user_approved=False):
            if task.task_id == "t1" and not user_approved:
                return make_risk_result(PermissionDecision.REQUIRE_APPROVAL, risk_level=RiskLevel.HIGH)
            return make_risk_result(PermissionDecision.ALLOW, risk_level=RiskLevel.LOW)

        orchestrator._assess_task_risk = mock_assess

        cmd1 = orchestrator.task_queue.enqueue("cmd 1", [t1])
        cmd2 = orchestrator.task_queue.enqueue("cmd 2", [t2])

        # Wait for worker to pop cmd1 and pause at AWAITING_APPROVAL
        for _ in range(30):
            if event_bus.current_state == EVState.AWAITING_APPROVAL:
                break
            time.sleep(0.05)
        self.assertEqual(event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertEqual(cmd1.status, QueueItemStatus.AWAITING_APPROVAL)
        # cmd2 must remain QUEUED and NOT executed
        self.assertEqual(cmd2.status, QueueItemStatus.QUEUED)
        self.assertEqual(orchestrator.task_queue.size(), 1)

        orchestrator.cancel_all()
        orchestrator.stop_queue_worker()

    def test_18_read_only_task_cannot_execute_around_pending_approval(self) -> None:
        """18. Read-only commands cannot bypass a paused pending approval."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        t_mut = AgentTask(task_id="mut", action=AgentAction.DELETE_FILE, parameters={"path": "C:\\del.txt"})
        t_ro = AgentTask(task_id="ro", action=AgentAction.FIND_PROCESS, parameters={"name": "p.exe"})

        orchestrator._assess_task_risk = lambda task, user_approved=False: (
            make_risk_result(PermissionDecision.REQUIRE_APPROVAL)
            if task.task_id == "mut" and not user_approved
            else make_risk_result(PermissionDecision.ALLOW)
        )

        orchestrator.task_queue.enqueue("delete", [t_mut])
        for _ in range(30):
            if event_bus.current_state == EVState.AWAITING_APPROVAL:
                break
            time.sleep(0.05)
        self.assertEqual(event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Enqueue read-only command while awaiting approval
        ro_cmd = orchestrator.task_queue.enqueue("read only", [t_ro])
        time.sleep(0.2)

        # ro_cmd must not execute!
        self.assertEqual(ro_cmd.status, QueueItemStatus.QUEUED)

        orchestrator.cancel_all()
        orchestrator.stop_queue_worker()

    def test_19_approval_resumes_correct_task_only(self) -> None:
        """19. Approving the pending task executes it and then resumes subsequent queue items."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        t1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test.txt"})
        t2 = AgentTask(task_id="t2", action=AgentAction.FIND_PROCESS, parameters={"name": "proc.exe"})

        orchestrator._assess_task_risk = lambda task, user_approved=False: (
            make_risk_result(PermissionDecision.REQUIRE_APPROVAL)
            if task.task_id == "t1" and not user_approved
            else make_risk_result(PermissionDecision.ALLOW)
        )
        orchestrator.agent.run = lambda task: MagicMock(status=AgentStatus.COMPLETED)

        cmd1 = orchestrator.task_queue.enqueue("cmd 1", [t1])
        cmd2 = orchestrator.task_queue.enqueue("cmd 2", [t2])

        time.sleep(0.2)
        self.assertEqual(event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Resolve approval
        orchestrator.resolve_approval("t1", approved=True)

        # Wait for both to complete
        cmd1.completion_event.wait(timeout=3.0)
        cmd2.completion_event.wait(timeout=3.0)

        self.assertEqual(cmd1.status, QueueItemStatus.COMPLETED)
        self.assertEqual(cmd2.status, QueueItemStatus.COMPLETED)
        orchestrator.stop_queue_worker()

    def test_20_stale_approval_rejected(self) -> None:
        """20. Approval attempt for nonexistent or mismatch task ID is rejected."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus)

        self.assertFalse(orchestrator.resolve_approval("nonexistent_id", approved=True))

    def test_21_denial_resumes_queue(self) -> None:
        """21. Denying pending task fails it and resumes the next queued command."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        t1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\test.txt"})
        t2 = AgentTask(task_id="t2", action=AgentAction.FIND_PROCESS, parameters={"name": "proc.exe"})

        orchestrator._assess_task_risk = lambda task, user_approved=False: (
            make_risk_result(PermissionDecision.REQUIRE_APPROVAL)
            if task.task_id == "t1" and not user_approved
            else make_risk_result(PermissionDecision.ALLOW)
        )
        orchestrator.agent.run = lambda task: MagicMock(status=AgentStatus.COMPLETED)

        cmd1 = orchestrator.task_queue.enqueue("cmd 1", [t1])
        cmd2 = orchestrator.task_queue.enqueue("cmd 2", [t2])

        time.sleep(0.2)
        self.assertEqual(event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Deny t1
        orchestrator.resolve_approval("t1", approved=False)

        cmd1.completion_event.wait(timeout=3.0)
        cmd2.completion_event.wait(timeout=3.0)

        self.assertEqual(cmd1.status, QueueItemStatus.FAILED)
        self.assertEqual(cmd2.status, QueueItemStatus.COMPLETED)
        orchestrator.stop_queue_worker()

    def test_22_later_tasks_execute_only_after_approval_flow_resolves(self) -> None:
        """22. Execution order is strictly preserved through approval pausing."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        execution_log: list[str] = []

        t1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\1.txt"})
        t2 = AgentTask(task_id="t2", action=AgentAction.FIND_PROCESS, parameters={"name": "2.exe"})

        orchestrator._assess_task_risk = lambda task, user_approved=False: (
            make_risk_result(PermissionDecision.REQUIRE_APPROVAL)
            if task.task_id == "t1" and not user_approved
            else make_risk_result(PermissionDecision.ALLOW)
        )

        def mock_run(task):
            execution_log.append(task.task_id)
            return MagicMock(status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        cmd1 = orchestrator.task_queue.enqueue("cmd 1", [t1])
        cmd2 = orchestrator.task_queue.enqueue("cmd 2", [t2])

        time.sleep(0.2)
        self.assertEqual(len(execution_log), 0)

        orchestrator.resolve_approval("t1", approved=True)
        cmd1.completion_event.wait(timeout=3.0)
        cmd2.completion_event.wait(timeout=3.0)

        self.assertEqual(execution_log, ["t1", "t2"])
        orchestrator.stop_queue_worker()


# ==============================================================================
# 4. LIFECYCLE & INTEGRATION TESTS (Items 23-30)
# ==============================================================================

class TestLifecycleAndIntegration(unittest.TestCase):
    """Verify worker startup, shutdown, sequential processing, and compatibility."""

    def test_23_worker_starts_and_stops(self) -> None:
        """23. Queue worker thread lifecycle management."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=False)

        self.assertIsNone(orchestrator._worker_thread)
        orchestrator.start_queue_worker()
        self.assertIsNotNone(orchestrator._worker_thread)
        self.assertTrue(orchestrator._worker_thread.is_alive())

        orchestrator.stop_queue_worker(timeout=2.0)
        self.assertFalse(orchestrator._worker_thread.is_alive())

    def test_24_sequential_execution(self) -> None:
        """24. Tasks execute one at a time sequentially."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        concurrent_count = 0
        max_concurrent = 0
        lock = threading.Lock()

        def monitored_run(task):
            nonlocal concurrent_count, max_concurrent
            with lock:
                concurrent_count += 1
                if concurrent_count > max_concurrent:
                    max_concurrent = concurrent_count
            time.sleep(0.05)
            with lock:
                concurrent_count -= 1
            return MagicMock(status=AgentStatus.COMPLETED)

        orchestrator.agent.run = monitored_run
        orchestrator._assess_task_risk = lambda task, user_approved=False: make_risk_result(PermissionDecision.ALLOW)

        t1 = make_test_task("t1")
        t2 = make_test_task("t2")
        t3 = make_test_task("t3")

        c1 = orchestrator.task_queue.enqueue("1", [t1])
        c2 = orchestrator.task_queue.enqueue("2", [t2])
        c3 = orchestrator.task_queue.enqueue("3", [t3])

        c1.completion_event.wait(timeout=3.0)
        c2.completion_event.wait(timeout=3.0)
        c3.completion_event.wait(timeout=3.0)

        self.assertEqual(max_concurrent, 1)
        orchestrator.stop_queue_worker()

    def test_25_completion_signalling_and_thread_handle(self) -> None:
        """25. TaskExecutionThread.join() unblocks when queued command completes."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)
        orchestrator.agent.run = lambda task: MagicMock(status=AgentStatus.COMPLETED)
        orchestrator._assess_task_risk = lambda task, user_approved=False: make_risk_result(PermissionDecision.ALLOW)

        t = make_test_task("t")
        queued_cmd = orchestrator.task_queue.enqueue("cmd", [t])
        thread = TaskExecutionThread(queued_cmd)

        self.assertTrue(thread.is_alive())
        thread.join(timeout=3.0)
        self.assertFalse(thread.is_alive())
        orchestrator.stop_queue_worker()

    def test_26_shutdown_cancels_queue(self) -> None:
        """26. Shutdown cancels all pending queued items."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)

        t = make_test_task("t")
        c1 = orchestrator.task_queue.enqueue("1", [t])
        c2 = orchestrator.task_queue.enqueue("2", [t])

        orchestrator.shutdown(timeout=2.0)
        self.assertEqual(orchestrator.task_queue.size(), 0)
        self.assertTrue(c1.completion_event.is_set())
        self.assertTrue(c2.completion_event.is_set())
        self.assertEqual(event_bus.current_state, EVState.STOPPED)

    def test_27_shutdown_worker_exit(self) -> None:
        """27. Queue worker exits cleanly on shutdown."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=True)
        self.assertTrue(orchestrator._worker_thread.is_alive())

        orchestrator.shutdown(timeout=2.0)
        self.assertFalse(orchestrator._worker_thread.is_alive())

    def test_28_restart_starts_empty(self) -> None:
        """28. New orchestrator instance starts with an empty queue (RAM-only)."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus)
        self.assertEqual(orchestrator.task_queue.size(), 0)
        self.assertTrue(orchestrator.task_queue.is_empty())

    def test_29_queued_command_never_resurrects(self) -> None:
        """29. Unexecuted queued commands from past instances do not resurrect."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        o1 = EVOrchestrator(event_bus)
        t = make_test_task("t")
        o1.task_queue.enqueue("cmd", [t])
        self.assertEqual(o1.task_queue.size(), 1)

        # Simulate restart
        o2 = EVOrchestrator(event_bus)
        self.assertEqual(o2.task_queue.size(), 0)

    def test_30_queue_command_interface_backward_compatibility(self) -> None:
        """30. queue_command provides thread-like handle and completes successfully."""
        event_bus = EVEventBus(initial_state=EVState.IDLE)
        orchestrator = EVOrchestrator(event_bus, enable_queue=False)

        task = make_test_task("t")
        with patch.object(orchestrator.router, "route") as mock_route:
            mock_route.return_value = MagicMock(
                success=True,
                route_type=MagicMock(),
                tasks=[task],
                message="Dispatched",
            )
            orchestrator.agent.run = lambda t: MagicMock(status=AgentStatus.COMPLETED)
            orchestrator._assess_task_risk = lambda t, user_approved=False: make_risk_result(PermissionDecision.ALLOW)

            thread = orchestrator.queue_command("find test process")
            self.assertIsNotNone(thread)
            self.assertTrue(isinstance(thread, threading.Thread))
            thread.join(timeout=3.0)
            self.assertFalse(thread.is_alive())

        orchestrator.stop_queue_worker()


if __name__ == "__main__":
    unittest.main()
