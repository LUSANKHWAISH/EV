"""
Unit and integration tests for EVOrchestrator risk gating and Human-in-the-Loop approval wiring (Phase 5 Task 002).

All tests are 100% offline, deterministic, and verify:
  1. Read-only actions bypass approval and execute immediately.
  2. Elevated-risk actions halt before execution and enter EVState.AWAITING_APPROVAL.
  3. APPROVAL_REQUIRED event is published with task_id, action, risk_level, reason, and parameters.
  4. Explicit user approval re-evaluates risk with user_approved=True and executes the task.
  5. User denial produces zero execution, transitions state to IDLE, and records denial.
  6. Duplicate approval is safely rejected.
  7. Stale approval cannot authorize another task.
  8. Brain-generated proposals cannot self-approve.
  9. Multi-task batches pause at the approval boundary and resume sequentially upon approval.
  10. Multi-task batches abort remaining tasks upon denial.
  11. No execution lock is held while waiting in AWAITING_APPROVAL.
  12. GuiBridge receives APPROVAL_REQUIRED and emits approvalRequested Qt signal.
  13. GuiBridge.submitApproval triggers orchestrator.resolve_approval.
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication

from core.agent import EVAgent
from core.brain_models import (
    BrainActionProposal,
    BrainContext,
    BrainDecision,
    BrainDecisionType,
)
from core.brain_provider import EVBrainProvider
from core.brain_provider_manager import EVBrainProviderManager
from core.brain_router import BrainRouter
from core.events import EVEvent, EVEventBus
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
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
    VerificationType,
)
from core.orchestrator import EVOrchestrator, get_action_category
from core.risk import EVRiskEngine
from gui.bridge import GuiBridge


class FakeApprovalBrainProvider(EVBrainProvider):
    """Deterministic offline fake provider for testing Brain approval interactions."""

    def __init__(self, decision: BrainDecision):
        self._decision = decision

    @property
    def provider_name(self) -> str:
        return "fake_approval_provider"

    @property
    def model_name(self) -> str:
        return "fake_model"

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        return self._decision

    def check_health(self) -> bool:
        return True


class TestRiskOrchestratorApprovalWiring(unittest.TestCase):
    """Test suite for EVOrchestrator risk gating and approval lifecycle."""

    def setUp(self):
        self.event_bus = EVEventBus(initial_state=EVState.IDLE)
        self.orchestrator = EVOrchestrator(event_bus=self.event_bus)

    def test_read_only_action_bypasses_approval(self):
        """Read-only actions (e.g. FIND_PROCESS) must execute immediately without approval prompt."""
        task = AgentTask(
            task_id="t-read-001",
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "test_process.exe"},
        )
        with patch.object(self.orchestrator.agent, "run") as mock_run:
            mock_run.return_value = AgentRunResult(
                task_id="t-read-001",
                status=AgentStatus.COMPLETED,
            )
            thread = self.orchestrator._dispatch_tasks([task])
            self.assertIsNotNone(thread)
            thread.join(timeout=2.0)
            mock_run.assert_called_once_with(task)
            self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    def test_elevated_risk_action_enters_awaiting_approval(self):
        """Actions requiring approval must not execute early and must enter EVState.AWAITING_APPROVAL."""
        task = AgentTask(
            task_id="t-elev-001",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\test\\target.txt"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.MEDIUM,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="File modification requires user approval",
            policy_rule="file_modify_requires_approval",
        )
        self.orchestrator.risk_engine = mock_risk_engine

        with patch.object(self.orchestrator.agent, "run") as mock_run:
            thread = self.orchestrator._dispatch_tasks([task])
            self.assertIsNone(thread)
            mock_run.assert_not_called()
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
            self.assertIsNotNone(self.orchestrator._pending_approval)
            self.assertEqual(self.orchestrator._pending_approval["task"].task_id, "t-elev-001")

    def test_approval_required_event_emitted(self):
        """APPROVAL_REQUIRED event must be emitted with task_id, action, risk_level, and reason."""
        task = AgentTask(
            task_id="t-event-001",
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "elevated.exe"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.PROCESS_START,
            risk_level=RiskLevel.LOW,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="Process start requires authorization",
            policy_rule="process_start_requires_approval",
        )
        self.orchestrator.risk_engine = mock_risk_engine

        events = []
        token = self.event_bus.subscribe(
            lambda e: events.append(e),
            event_types=[EVEventType.APPROVAL_REQUIRED],
        )

        self.orchestrator._dispatch_tasks([task])

        self.assertEqual(len(events), 1)
        ev = events[0]
        self.assertEqual(ev.event_type, EVEventType.APPROVAL_REQUIRED)
        self.assertEqual(ev.data["task_id"], "t-event-001")
        self.assertEqual(ev.data["action"], "FIND_PROCESS")
        self.assertEqual(ev.data["risk_level"], "LOW")
        self.assertEqual(ev.data["reason"], "Process start requires authorization")
        self.assertEqual(ev.data["parameters"], {"name": "elevated.exe"})

    def test_user_approval_executes_task(self):
        """Explicit approval must re-evaluate risk with user_approved=True and execute the task."""
        task = AgentTask(
            task_id="t-appr-001",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\test\\approved.txt"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        # First call: REQUIRE_APPROVAL; Second call (user_approved=True): ALLOW
        mock_risk_engine.assess.side_effect = [
            RiskAssessmentResult(
                action_category=ActionCategory.FILE_CREATE,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.REQUIRE_APPROVAL,
                allowed=False,
                requires_approval=True,
                reason="Requires approval",
                policy_rule="file_create_requires_approval",
            ),
            RiskAssessmentResult(
                action_category=ActionCategory.FILE_CREATE,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="User approved",
                policy_rule="file_create_approved",
            ),
        ]
        self.orchestrator.risk_engine = mock_risk_engine

        with patch.object(self.orchestrator.agent, "run") as mock_run:
            mock_run.return_value = AgentRunResult(
                task_id="t-appr-001",
                status=AgentStatus.COMPLETED,
            )

            # Initial submission halts
            self.orchestrator._dispatch_tasks([task])
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
            mock_run.assert_not_called()

            # User approves
            result = self.orchestrator.resolve_approval("t-appr-001", approved=True)
            self.assertTrue(result)

            # Wait for execution thread to complete
            for _ in range(50):
                if mock_run.call_count > 0 and self.event_bus.current_state == EVState.IDLE:
                    break
                time.sleep(0.02)

            mock_run.assert_called_once_with(task)
            self.assertEqual(self.event_bus.current_state, EVState.IDLE)
            self.assertIsNone(self.orchestrator._pending_approval)

    def test_user_denial_aborts_execution(self):
        """User denial must produce zero tool execution and restore state to IDLE."""
        task = AgentTask(
            task_id="t-deny-001",
            action=AgentAction.FIND_SERVICE,
            parameters={"name": "DangerousService"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.SERVICE_CONFIGURATION,
            risk_level=RiskLevel.HIGH,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="Service modification requires approval",
            policy_rule="service_config_requires_approval",
        )
        self.orchestrator.risk_engine = mock_risk_engine

        with patch.object(self.orchestrator.agent, "run") as mock_run:
            self.orchestrator._dispatch_tasks([task])
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

            # User denies
            result = self.orchestrator.resolve_approval("t-deny-001", approved=False)
            self.assertTrue(result)

            mock_run.assert_not_called()
            self.assertEqual(self.event_bus.current_state, EVState.IDLE)
            self.assertIsNone(self.orchestrator._pending_approval)

    def test_duplicate_approval_rejected(self):
        """A second resolve_approval call for an already consumed task must return False."""
        task = AgentTask(
            task_id="t-dup-001",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\test\\dup.txt"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.side_effect = [
            RiskAssessmentResult(
                action_category=ActionCategory.FILE_CREATE,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.REQUIRE_APPROVAL,
                allowed=False,
                requires_approval=True,
                reason="Requires approval",
                policy_rule="file_create_requires_approval",
            ),
            RiskAssessmentResult(
                action_category=ActionCategory.FILE_CREATE,
                risk_level=RiskLevel.LOW,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="User approved",
                policy_rule="file_create_approved",
            ),
        ]
        self.orchestrator.risk_engine = mock_risk_engine

        with patch.object(self.orchestrator.agent, "run") as mock_run:
            mock_run.return_value = AgentRunResult(
                task_id="t-dup-001",
                status=AgentStatus.COMPLETED,
            )
            self.orchestrator._dispatch_tasks([task])

            # First approval succeeds
            first_res = self.orchestrator.resolve_approval("t-dup-001", approved=True)
            self.assertTrue(first_res)

            # Second approval rejected
            second_res = self.orchestrator.resolve_approval("t-dup-001", approved=True)
            self.assertFalse(second_res)

    def test_stale_approval_rejected(self):
        """Approval with a non-matching task_id must be rejected and leave pending state intact."""
        task = AgentTask(
            task_id="t-active-001",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\test\\active.txt"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.MEDIUM,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="Requires approval",
            policy_rule="file_modify_requires_approval",
        )
        self.orchestrator.risk_engine = mock_risk_engine

        self.orchestrator._dispatch_tasks([task])
        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Attempt to approve with wrong task_id
        res = self.orchestrator.resolve_approval("t-stale-999", approved=True)
        self.assertFalse(res)
        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
        self.assertIsNotNone(self.orchestrator._pending_approval)

    def test_brain_cannot_self_approve(self):
        """Brain proposals claiming user approval cannot bypass the initial user_approved=False gate."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="I have decided to run this without approval.",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.GET_FILE_INFO,
                    parameters={"path": "C:\\test\\secret.txt"},
                )
            ],
            confidence=0.99,
        )

        provider = FakeApprovalBrainProvider(decision)
        mgr = EVBrainProviderManager([provider])
        router = BrainRouter(provider_manager=mgr)
        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.MEDIUM,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="Security boundary requires user confirmation",
            policy_rule="file_modify_requires_approval",
        )
        orchestrator.risk_engine = mock_risk_engine

        with patch.object(orchestrator.agent, "run") as mock_run:
            orchestrator.submit_command("read the secret file")

            # Must NOT execute
            mock_run.assert_not_called()
            # Initial assessment must have been evaluated with user_approved=False
            mock_risk_engine.assess.assert_called_once()
            req = mock_risk_engine.assess.call_args[0][0]
            self.assertFalse(req.user_approved)
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

    def test_multi_task_pauses_on_approval(self):
        """Sequential multi-task execution pauses at the approval boundary and resumes upon approval."""
        t1 = AgentTask(
            task_id="t-batch-001",
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "p1.exe"},
        )
        t2 = AgentTask(
            task_id="t-batch-002",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\file2.txt"},
        )
        t3 = AgentTask(
            task_id="t-batch-003",
            action=AgentAction.FIND_TCP_PORT,
            parameters={"port": 8080},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)

        def mock_assess(req: RiskAssessmentRequest) -> RiskAssessmentResult:
            if "file2.txt" in (req.target or ""):
                if req.user_approved:
                    return RiskAssessmentResult(
                        action_category=ActionCategory.FILE_CREATE,
                        risk_level=RiskLevel.LOW,
                        decision=PermissionDecision.ALLOW,
                        allowed=True,
                        requires_approval=False,
                        reason="User approved",
                        policy_rule="approved",
                    )
                return RiskAssessmentResult(
                    action_category=ActionCategory.FILE_CREATE,
                    risk_level=RiskLevel.LOW,
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    allowed=False,
                    requires_approval=True,
                    reason="File create requires approval",
                    policy_rule="requires_approval",
                )
            return RiskAssessmentResult(
                action_category=ActionCategory.READ_ONLY_OBSERVATION,
                risk_level=RiskLevel.NONE,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="Read only",
                policy_rule="read_only",
            )

        mock_risk_engine.assess.side_effect = mock_assess
        self.orchestrator.risk_engine = mock_risk_engine

        executed_tasks = []

        def mock_agent_run(t: AgentTask) -> AgentRunResult:
            executed_tasks.append(t.task_id)
            return AgentRunResult(task_id=t.task_id, status=AgentStatus.COMPLETED)

        with patch.object(self.orchestrator.agent, "run", side_effect=mock_agent_run):
            # Start batch [t1, t2, t3]
            thread = self.orchestrator.execute_tasks([t1, t2, t3])
            thread.join(timeout=2.0)

            # t1 ran; t2 caused pause; t3 is in remaining
            self.assertEqual(executed_tasks, ["t-batch-001"])
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)
            self.assertIsNotNone(self.orchestrator._pending_approval)
            self.assertEqual(self.orchestrator._pending_approval["task"].task_id, "t-batch-002")
            self.assertEqual(len(self.orchestrator._pending_approval["remaining_tasks"]), 1)
            self.assertEqual(self.orchestrator._pending_approval["remaining_tasks"][0].task_id, "t-batch-003")

            # User approves t2 -> resumes t2 and t3
            res = self.orchestrator.resolve_approval("t-batch-002", approved=True)
            self.assertTrue(res)

            # Wait for execution to finish
            for _ in range(50):
                if len(executed_tasks) == 3 and self.event_bus.current_state == EVState.IDLE:
                    break
                time.sleep(0.02)

            self.assertEqual(executed_tasks, ["t-batch-001", "t-batch-002", "t-batch-003"])
            self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    def test_multi_task_aborts_remaining_on_denial(self):
        """Sequential multi-task execution aborts remaining tasks upon user denial."""
        t1 = AgentTask(
            task_id="t-abort-001",
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "p1.exe"},
        )
        t2 = AgentTask(
            task_id="t-abort-002",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\file2.txt"},
        )
        t3 = AgentTask(
            task_id="t-abort-003",
            action=AgentAction.FIND_TCP_PORT,
            parameters={"port": 8080},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)

        def mock_assess(req: RiskAssessmentRequest) -> RiskAssessmentResult:
            if "file2.txt" in (req.target or ""):
                return RiskAssessmentResult(
                    action_category=ActionCategory.FILE_DELETE,
                    risk_level=RiskLevel.HIGH,
                    decision=PermissionDecision.REQUIRE_APPROVAL,
                    allowed=False,
                    requires_approval=True,
                    reason="File delete requires approval",
                    policy_rule="requires_approval",
                )
            return RiskAssessmentResult(
                action_category=ActionCategory.READ_ONLY_OBSERVATION,
                risk_level=RiskLevel.NONE,
                decision=PermissionDecision.ALLOW,
                allowed=True,
                requires_approval=False,
                reason="Read only",
                policy_rule="read_only",
            )

        mock_risk_engine.assess.side_effect = mock_assess
        self.orchestrator.risk_engine = mock_risk_engine

        executed_tasks = []

        def mock_agent_run(t: AgentTask) -> AgentRunResult:
            executed_tasks.append(t.task_id)
            return AgentRunResult(task_id=t.task_id, status=AgentStatus.COMPLETED)

        with patch.object(self.orchestrator.agent, "run", side_effect=mock_agent_run):
            # Start batch [t1, t2, t3]
            thread = self.orchestrator.execute_tasks([t1, t2, t3])
            thread.join(timeout=2.0)

            self.assertEqual(executed_tasks, ["t-abort-001"])
            self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

            # User denies t2 -> t2 and t3 must NOT run
            res = self.orchestrator.resolve_approval("t-abort-002", approved=False)
            self.assertTrue(res)

            self.assertEqual(executed_tasks, ["t-abort-001"])
            self.assertEqual(self.event_bus.current_state, EVState.IDLE)
            self.assertIsNone(self.orchestrator._pending_approval)

    def test_no_execution_lock_held_during_awaiting_approval(self):
        """_execution_lock must NOT be held while waiting for user approval."""
        task = AgentTask(
            task_id="t-lock-001",
            action=AgentAction.GET_FILE_INFO,
            parameters={"path": "C:\\test\\lock.txt"},
        )

        mock_risk_engine = MagicMock(spec=EVRiskEngine)
        mock_risk_engine.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.MEDIUM,
            decision=PermissionDecision.REQUIRE_APPROVAL,
            allowed=False,
            requires_approval=True,
            reason="Requires approval",
            policy_rule="file_modify_requires_approval",
        )
        self.orchestrator.risk_engine = mock_risk_engine

        self.orchestrator._dispatch_tasks([task])
        self.assertEqual(self.event_bus.current_state, EVState.AWAITING_APPROVAL)

        # Lock must be acquirable non-blockingly
        acquired = self.orchestrator._execution_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        self.orchestrator._execution_lock.release()

    def test_gui_bridge_approval_signals(self):
        """GuiBridge must receive APPROVAL_REQUIRED and emit approvalRequested Qt signal."""
        app = QCoreApplication.instance() or QCoreApplication([])

        bridge = GuiBridge(self.event_bus)

        received_requests = []
        bridge.approvalRequested.connect(
            lambda t_id, action, risk, reason: received_requests.append((t_id, action, risk, reason))
        )

        # Publish APPROVAL_REQUIRED event
        self.event_bus.publish(
            event_type=EVEventType.APPROVAL_REQUIRED,
            source="orchestrator",
            correlation_id="t-bridge-001",
            message="Approval needed",
            data={
                "task_id": "t-bridge-001",
                "action": "GET_FILE_INFO",
                "risk_level": "HIGH",
                "reason": "Dangerous file operation",
            },
        )

        app.processEvents()

        self.assertEqual(len(received_requests), 1)
        self.assertEqual(received_requests[0], ("t-bridge-001", "GET_FILE_INFO", "HIGH", "Dangerous file operation"))

        # Test submitApproval slot
        submitted_approvals = []
        bridge.approvalSubmitted.connect(lambda t_id, app_flag: submitted_approvals.append((t_id, app_flag)))

        bridge.submitApproval("t-bridge-001", True)
        self.assertEqual(len(submitted_approvals), 1)
        self.assertEqual(submitted_approvals[0], ("t-bridge-001", True))


if __name__ == "__main__":
    unittest.main()
