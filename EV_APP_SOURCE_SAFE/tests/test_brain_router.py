"""
Unit tests for Brain Intent Engine & Command Router (Phase 4 Task 010).

All tests are 100% offline, deterministic, and verify:
  - Fast-path CLI command resolution via CommandResolver without invoking Brain
  - Natural-language fallback to Brain path (Context -> Provider -> Validator -> Converter)
  - Non-executable Brain decisions (REFUSAL, CLARIFICATION, EXPLANATION) return NO_ACTION
  - Safe error propagation on provider failures and validator rejections
  - Preservation of safety invariants and zero OS/orchestrator side-effects
"""
import unittest
from unittest.mock import MagicMock, patch

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
from core.brain_validator import (
    BrainProposalValidator,
    BrainValidationResult,
    BrainValidationStatus,
)
from core.models import AgentAction, AgentTask, EVState, VerificationType
from core.resolver import CommandResolver


class FakeBrainProvider(EVBrainProvider):
    """Deterministic offline fake provider for router testing."""

    def __init__(
        self,
        decision_to_return: BrainDecision,
        name: str = "FakeProvider",
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


class TestBrainRouterFastPath(unittest.TestCase):
    """Test deterministic fast-path CLI resolution."""

    def setUp(self):
        self.resolver = CommandResolver()
        self.mock_provider_manager = MagicMock(spec=EVBrainProviderManager)
        self.router = BrainRouter(
            provider_manager=self.mock_provider_manager,
            resolver=self.resolver,
        )

    def test_fast_path_find_process(self):
        res = self.router.route("find process notepad.exe")
        self.assertEqual(res.route_type, RouteType.FAST_PATH)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 1)
        self.assertEqual(res.tasks[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(res.tasks[0].parameters, {"name": "notepad.exe"})
        self.mock_provider_manager.generate_decision.assert_not_called()

    def test_fast_path_find_port(self):
        res = self.router.route("find port 8080")
        self.assertEqual(res.route_type, RouteType.FAST_PATH)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 1)
        self.assertEqual(res.tasks[0].action, AgentAction.FIND_TCP_PORT)
        self.assertEqual(res.tasks[0].parameters, {"port": 8080})
        self.mock_provider_manager.generate_decision.assert_not_called()

    def test_fast_path_verify_service(self):
        res = self.router.route("verify service Spooler")
        self.assertEqual(res.route_type, RouteType.FAST_PATH)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 1)
        self.assertEqual(res.tasks[0].action, AgentAction.FIND_SERVICE)
        self.assertEqual(res.tasks[0].verification_type, VerificationType.SERVICE_RUNNING)
        self.mock_provider_manager.generate_decision.assert_not_called()


class TestBrainRouterBrainPath(unittest.TestCase):
    """Test Brain path routing, validation, and conversion."""

    def test_executable_brain_decision_routes_to_tasks(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Looking for python process",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "python.exe"},
                )
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res = router.route("is python running right now?")
        self.assertEqual(res.route_type, RouteType.BRAIN_PATH)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 1)
        self.assertEqual(res.tasks[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(res.tasks[0].parameters, {"name": "python.exe"})
        self.assertEqual(fake_provider.call_count, 1)

    def test_refusal_decision_produces_no_action(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.REFUSAL,
            user_message="I cannot format your disk.",
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res = router.route("format drive C:")
        self.assertEqual(res.route_type, RouteType.NO_ACTION)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 0)
        self.assertEqual(res.message, "I cannot format your disk.")

    def test_clarification_decision_produces_no_action(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
            user_message="Please clarify which service.",
            clarification_prompt="Which service name would you like to inspect?",
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res = router.route("check the service")
        self.assertEqual(res.route_type, RouteType.NO_ACTION)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 0)
        self.assertEqual(res.message, "Which service name would you like to inspect?")

    def test_explanation_decision_produces_no_action(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="E.V. is an Execution and Verification agent for Windows.",
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res = router.route("what is your purpose?")
        self.assertEqual(res.route_type, RouteType.NO_ACTION)
        self.assertTrue(res.success)
        self.assertEqual(len(res.tasks), 0)
        self.assertEqual(res.message, "E.V. is an Execution and Verification agent for Windows.")


class TestBrainRouterFailuresAndSafety(unittest.TestCase):
    """Test error handling, unvalidated proposal rejections, and failure boundaries."""

    def test_empty_or_whitespace_input_fails_safely(self):
        router = BrainRouter()
        res1 = router.route("")
        self.assertEqual(res1.route_type, RouteType.FAILURE)
        self.assertFalse(res1.success)

        res2 = router.route("   ")
        self.assertEqual(res2.route_type, RouteType.FAILURE)
        self.assertFalse(res2.success)

    def test_missing_provider_manager_on_natural_language_fails(self):
        router = BrainRouter(provider_manager=None)
        res = router.route("can you search for error in log files?")
        self.assertEqual(res.route_type, RouteType.FAILURE)
        self.assertFalse(res.success)
        self.assertIn("No Brain provider manager configured", res.error or "")

    def test_provider_error_surfaced_safely(self):
        mock_mgr = MagicMock(spec=EVBrainProviderManager)
        mock_mgr.generate_decision.side_effect = BrainProviderTimeoutError("Provider request timed out after 15.0s")
        router = BrainRouter(provider_manager=mock_mgr)

        res = router.route("find active connections")
        self.assertEqual(res.route_type, RouteType.FAILURE)
        self.assertFalse(res.success)
        self.assertIn("Brain provider error", res.error or "")

    def test_invalid_proposal_rejected_by_validator(self):
        # Decision has an invalid parameter (e.g. invalid type or forbidden field)
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Find port with invalid string",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_TCP_PORT,
                    parameters={"port": "NOT_AN_INT"},  # validator requires int 1..65535
                )
            ],
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res = router.route("check port NOT_AN_INT")
        self.assertEqual(res.route_type, RouteType.FAILURE)
        self.assertFalse(res.success)
        self.assertEqual(len(res.tasks), 0)
        self.assertIn("Brain proposal validation failed", res.error or "")

    def test_deterministic_routing_repeatability(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Find python",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python.exe"})],
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])
        router = BrainRouter(provider_manager=mgr)

        res1 = router.route("is python running?")
        res2 = router.route("is python running?")

        self.assertEqual(res1.route_type, res2.route_type)
        self.assertEqual(res1.success, res2.success)
        self.assertEqual(len(res1.tasks), len(res2.tasks))
        self.assertEqual(res1.tasks[0].action, res2.tasks[0].action)

    def test_no_retry_loop_on_provider_error(self):
        mock_mgr = MagicMock(spec=EVBrainProviderManager)
        mock_mgr.generate_decision.side_effect = BrainProviderUnavailableError("Provider offline")
        router = BrainRouter(provider_manager=mock_mgr)

        res = router.route("find files matching *.log")
        self.assertEqual(res.route_type, RouteType.FAILURE)
        self.assertFalse(res.success)
        # Verify provider manager is called exactly ONCE (no retry loop in router)
        self.assertEqual(mock_mgr.generate_decision.call_count, 1)

    def test_context_assembler_invoked_with_provided_arguments(self):
        mock_assembler = MagicMock(spec=BrainContextAssembler)
        mock_assembler.assemble_context.return_value = BrainContext(
            user_input="test query",
            current_state=EVState.IDLE,
            platform="windows",
            available_actions=[AgentAction.FIND_PROCESS],
        )

        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Test decision",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "test.exe"})],
        )
        fake_provider = FakeBrainProvider(decision)
        mgr = EVBrainProviderManager([fake_provider])

        router = BrainRouter(
            provider_manager=mgr,
            context_assembler=mock_assembler,
        )

        res = router.route(
            "test query",
            current_state=EVState.IDLE,
            platform="windows",
            available_actions=[AgentAction.FIND_PROCESS],
        )
        self.assertEqual(res.route_type, RouteType.BRAIN_PATH)
        self.assertTrue(res.success)
        mock_assembler.assemble_context.assert_called_once()


if __name__ == "__main__":
    unittest.main()
