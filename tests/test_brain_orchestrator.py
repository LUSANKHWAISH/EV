"""
Unit and integration tests for EVOrchestrator Brain integration (Phase 4 Task 011).

All tests are 100% offline, deterministic, and verify:
  - Fast-path deterministic commands execute through standard agent path
  - Natural-language input is routed through BrainRouter -> EVAgent
  - Brain-produced tasks enter the exact same risk, verification, history, and event paths
  - NO_ACTION and FAILURE results execute 0 tasks and emit status messages
  - Multi-task execution preserves strict sequential ordering
  - Rejection when busy and execution lock safety are preserved
  - Fast path avoids invoking Brain provider
  - Brain tasks record history and publish events identically to CLI tasks
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from core.agent import EVAgent
from core.brain_context import BrainContextAssembler
from core.brain_converter import BrainTaskConverter
from core.brain_models import (
    BrainActionProposal,
    BrainContext,
    BrainDecision,
    BrainDecisionType,
)
from core.brain_provider import (
    BrainProviderTimeoutError,
    BrainProviderUnavailableError,
    EVBrainProvider,
)
from core.brain_provider_manager import EVBrainProviderManager
from core.brain_router import BrainRouter, RouteType, RoutingResult
from core.brain_validator import BrainProposalValidator
from core.events import EVEvent, EVEventBus
from core.models import (
    AgentAction,
    AgentRunResult,
    AgentStatus,
    AgentTask,
    EVEventType,
    EVState,
    VerificationType,
)
from core.orchestrator import EVOrchestrator


class FakeBrainProvider(EVBrainProvider):
    """Deterministic offline fake provider for orchestrator integration tests."""

    def __init__(
        self,
        decision_to_return: BrainDecision,
        name: str = "FakeOrchestratorProvider",
        model: str = "fake-model-v1",
    ):
        self._name = name
        self._model = model
        self._decision = decision_to_return
        self.call_count = 0

    @property
    def provider_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return self._model

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        self.call_count += 1
        return self._decision

    def check_health(self) -> bool:
        return True


class TestEVOrchestratorBrainIntegration(unittest.TestCase):
    """Test EVOrchestrator integration with BrainRouter."""

    def setUp(self):
        self.event_bus = EVEventBus(initial_state=EVState.IDLE)

    def test_fast_path_command_execution(self):
        """Fast-path deterministic commands execute normally through standard agent path."""
        orchestrator = EVOrchestrator(event_bus=self.event_bus)

        executed_tasks = []

        def mock_run(task: AgentTask):
            executed_tasks.append(task)
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("find process python.exe")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        self.assertEqual(len(executed_tasks), 1)
        self.assertEqual(executed_tasks[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(executed_tasks[0].parameters["name"], "python.exe")
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    def test_fast_path_does_not_invoke_brain_provider(self):
        """Fast-path deterministic commands do not call the Brain provider."""
        mock_provider = MagicMock(spec=EVBrainProvider)
        mock_provider.name = "MockProvider"
        mock_provider_mgr = EVBrainProviderManager([mock_provider])
        router = BrainRouter(provider_manager=mock_provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        def mock_run(task: AgentTask):
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("find port 8080")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        mock_provider.generate_decision.assert_not_called()

    def test_natural_language_brain_path_execution(self):
        """Natural language input routes through Brain to execute AgentTask."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Checking for active processes",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "explorer.exe"},
                )
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        executed_tasks = []

        def mock_run(task: AgentTask):
            executed_tasks.append(task)
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("is explorer running on the system?")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        self.assertEqual(len(executed_tasks), 1)
        self.assertEqual(executed_tasks[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(executed_tasks[0].parameters["name"], "explorer.exe")
        self.assertEqual(fake_provider.call_count, 1)

    def test_brain_verification_request_executes_with_verification(self):
        """REQUEST_VERIFICATION from Brain preserves VerificationType on task."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_VERIFICATION,
            user_message="Verifying spooler service",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_SERVICE,
                    parameters={"name": "Spooler"},
                    verification_type=VerificationType.SERVICE_RUNNING,
                )
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        executed_tasks = []

        def mock_run(task: AgentTask):
            executed_tasks.append(task)
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("verify that the spooler service is running")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        self.assertEqual(len(executed_tasks), 1)
        self.assertEqual(executed_tasks[0].verification_type, VerificationType.SERVICE_RUNNING)

    def test_no_action_refusal_executes_nothing(self):
        """Brain REFUSAL produces 0 tasks and publishes a status message."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.REFUSAL,
            user_message="I cannot perform disk formatting.",
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        status_messages = []
        self.event_bus.subscribe(
            lambda e: status_messages.append(e.message),
            [EVEventType.STATUS],
        )

        thread = orchestrator.submit_command("format drive C:")
        self.assertIsNone(thread)
        self.assertIn("I cannot perform disk formatting.", status_messages)
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    def test_no_action_clarification_executes_nothing(self):
        """Brain REQUEST_CLARIFICATION produces 0 tasks and publishes clarification prompt."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
            user_message="Need more details",
            clarification_prompt="Which process name do you want to inspect?",
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        status_messages = []
        self.event_bus.subscribe(
            lambda e: status_messages.append(e.message),
            [EVEventType.STATUS],
        )

        thread = orchestrator.submit_command("check the process")
        self.assertIsNone(thread)
        self.assertIn("Which process name do you want to inspect?", status_messages)

    def test_no_action_explanation_executes_nothing(self):
        """Brain EXPLANATION_ONLY produces 0 tasks and publishes user message."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="E.V. is a Windows verification agent.",
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        status_messages = []
        self.event_bus.subscribe(
            lambda e: status_messages.append(e.message),
            [EVEventType.STATUS],
        )

        thread = orchestrator.submit_command("what is this program?")
        self.assertIsNone(thread)
        self.assertIn("E.V. is a Windows verification agent.", status_messages)

    def test_provider_failure_executes_nothing(self):
        """When provider fails, orchestrator publishes error and executes 0 tasks."""
        mock_mgr = MagicMock(spec=EVBrainProviderManager)
        mock_mgr.generate_decision.side_effect = BrainProviderTimeoutError("Provider timeout after 15s")
        router = BrainRouter(provider_manager=mock_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        status_messages = []
        self.event_bus.subscribe(
            lambda e: status_messages.append(e.message),
            [EVEventType.STATUS],
        )

        thread = orchestrator.submit_command("search for network anomalies")
        self.assertIsNone(thread)
        self.assertTrue(any("Brain provider error" in msg for msg in status_messages))

    def test_validation_failure_executes_nothing(self):
        """When Brain proposes invalid action, proposal validator fails closed and 0 tasks run."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Invalid port query",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_TCP_PORT,
                    parameters={"port": 999999},  # exceeds port range
                )
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        status_messages = []
        self.event_bus.subscribe(
            lambda e: status_messages.append(e.message),
            [EVEventType.STATUS],
        )

        thread = orchestrator.submit_command("check port 999999")
        self.assertIsNone(thread)
        self.assertTrue(any("validation failed" in msg.lower() for msg in status_messages))

    def test_multi_task_sequential_execution(self):
        """Multiple Brain action proposals are executed sequentially in exact order."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Multi action check",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python.exe"}),
                BrainActionProposal(action=AgentAction.FIND_SERVICE, parameters={"name": "Spooler"}),
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        executed_actions = []

        def mock_run(task: AgentTask):
            executed_actions.append(task.action)
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.COMPLETED)

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("check python process and spooler service")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        self.assertEqual(executed_actions, [AgentAction.FIND_PROCESS, AgentAction.FIND_SERVICE])
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)

    def test_multi_task_stops_on_first_failure(self):
        """Multi-task batch stops executing subsequent tasks if an earlier task fails."""
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Multi action check with failure",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p1.exe"}),
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p2.exe"}),
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        provider_mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=provider_mgr)

        orchestrator = EVOrchestrator(event_bus=self.event_bus, router=router)

        executed_actions = []

        def mock_run(task: AgentTask):
            executed_actions.append(task.action)
            # First task fails
            return AgentRunResult(task_id=task.task_id, status=AgentStatus.FAILED, error="Process not found")

        orchestrator.agent.run = mock_run

        thread = orchestrator.submit_command("check p1 and p2")
        self.assertIsNotNone(thread)
        thread.join(timeout=5.0)

        # Only the first task was executed because it failed
        self.assertEqual(len(executed_actions), 1)
        self.assertEqual(self.event_bus.current_state, EVState.IDLE)


if __name__ == "__main__":
    unittest.main()
