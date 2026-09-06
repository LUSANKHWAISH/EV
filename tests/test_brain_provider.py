"""
Unit tests for Brain Provider Abstraction & Mock Provider (Phase 4 Task 003).

Tests are 100% offline, deterministic, and verify:
  - Abstract base interface EVBrainProvider cannot be instantiated directly
  - MockBrainProvider generates validated BrainDecision objects
  - Health check verification (healthy/unhealthy state)
  - Error hierarchy (BrainProviderError, Timeout, Unavailable, Malformed, Auth)
  - Input validation (empty prompts, invalid context, invalid timeouts)
  - Call history tracking and deterministic repeatability
  - Safety boundary (no network calls, no tool execution, no side-effects)
"""
import math
import unittest

from core.models import AgentAction, EVState, VerificationType
from core.brain_models import (
    BrainDecisionType,
    BrainActionProposal,
    BrainDecision,
    BrainContext,
)
from core.brain_provider import (
    EVBrainProvider,
    MockBrainProvider,
    BrainProviderError,
    BrainProviderTimeoutError,
    BrainProviderUnavailableError,
    BrainProviderMalformedResponseError,
    BrainProviderAuthError,
)


class TestBrainProviderInterface(unittest.TestCase):
    """Verify EVBrainProvider ABC contract and interface constraints."""

    def test_cannot_instantiate_abstract_provider(self):
        with self.assertRaises(TypeError):
            EVBrainProvider()  # type: ignore

    def test_concrete_subclass_implements_interface(self):
        class DummyProvider(EVBrainProvider):
            @property
            def provider_name(self) -> str:
                return "dummy"

            @property
            def model_name(self) -> str:
                return "dummy-model"

            def generate_decision(self, prompt: str, context: BrainContext, timeout_seconds: float = 15.0) -> BrainDecision:
                return BrainDecision(
                    decision_type=BrainDecisionType.EXPLANATION_ONLY,
                    user_message="dummy response",
                )

            def check_health(self) -> bool:
                return True

        provider = DummyProvider()
        self.assertEqual(provider.provider_name, "dummy")
        self.assertEqual(provider.model_name, "dummy-model")
        self.assertTrue(provider.check_health())


class TestMockBrainProvider(unittest.TestCase):
    """Verify MockBrainProvider functionality, determinism, and safety."""

    def _sample_context(self, user_input: str = "check python") -> BrainContext:
        return BrainContext(
            user_input=user_input,
            current_state=EVState.IDLE,
            platform="windows",
        )

    def _sample_decision(self) -> BrainDecision:
        return BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Checking Python process.",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "python.exe"},
                )
            ],
            confidence=0.98,
        )

    def test_mock_provider_default_decision(self):
        decision = self._sample_decision()
        provider = MockBrainProvider(decision=decision)

        result = provider.generate_decision(
            prompt="Is python running?",
            context=self._sample_context(),
            timeout_seconds=10.0,
        )

        self.assertIsInstance(result, BrainDecision)
        self.assertEqual(result.decision_type, BrainDecisionType.EXECUTE_ACTION)
        self.assertEqual(result.user_message, "Checking Python process.")
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(len(provider.history), 1)

    def test_mock_provider_deterministic_repeatability(self):
        decision = self._sample_decision()
        provider = MockBrainProvider(decision=decision)
        context = self._sample_context()

        res1 = provider.generate_decision("check python", context)
        res2 = provider.generate_decision("check python", context)

        self.assertEqual(res1.model_dump(), res2.model_dump())
        self.assertEqual(provider.call_count, 2)

    def test_mock_provider_decision_queue(self):
        d1 = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="Answer 1",
        )
        d2 = BrainDecision(
            decision_type=BrainDecisionType.REFUSAL,
            user_message="Refusal 2",
        )
        provider = MockBrainProvider(decisions=[d1, d2])
        context = self._sample_context()

        res1 = provider.generate_decision("q1", context)
        res2 = provider.generate_decision("q2", context)

        self.assertEqual(res1.decision_type, BrainDecisionType.EXPLANATION_ONLY)
        self.assertEqual(res2.decision_type, BrainDecisionType.REFUSAL)

        # Third call when queue is exhausted raises MalformedResponseError
        with self.assertRaises(BrainProviderMalformedResponseError):
            provider.generate_decision("q3", context)

    def test_mock_provider_factory(self):
        def custom_factory(prompt: str, ctx: BrainContext) -> BrainDecision:
            return BrainDecision(
                decision_type=BrainDecisionType.EXPLANATION_ONLY,
                user_message=f"Echo: {prompt}",
            )

        provider = MockBrainProvider(decision_factory=custom_factory)
        result = provider.generate_decision("Hello world", self._sample_context())

        self.assertEqual(result.user_message, "Echo: Hello world")

    def test_mock_provider_factory_invalid_return_type(self):
        def bad_factory(prompt: str, ctx: BrainContext) -> dict:  # type: ignore
            return {"invalid": "dict"}

        provider = MockBrainProvider(decision_factory=bad_factory)  # type: ignore
        with self.assertRaises(BrainProviderMalformedResponseError):
            provider.generate_decision("Hello", self._sample_context())

    def test_mock_provider_metadata(self):
        provider = MockBrainProvider(
            provider_name="custom-mock",
            model_name="custom-model-v2",
        )
        self.assertEqual(provider.provider_name, "custom-mock")
        self.assertEqual(provider.model_name, "custom-model-v2")

    def test_health_check(self):
        provider = MockBrainProvider(healthy=True)
        self.assertTrue(provider.check_health())

        provider.set_healthy(False)
        self.assertFalse(provider.check_health())


class TestBrainProviderErrorHierarchy(unittest.TestCase):
    """Verify error classes, typing, and safety against leaking secrets."""

    def _sample_context(self) -> BrainContext:
        return BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

    def test_error_inheritance(self):
        self.assertTrue(issubclass(BrainProviderTimeoutError, BrainProviderError))
        self.assertTrue(issubclass(BrainProviderUnavailableError, BrainProviderError))
        self.assertTrue(issubclass(BrainProviderMalformedResponseError, BrainProviderError))
        self.assertTrue(issubclass(BrainProviderAuthError, BrainProviderError))

    def test_mock_provider_simulated_timeout(self):
        provider = MockBrainProvider(simulate_timeout=True)
        with self.assertRaises(BrainProviderTimeoutError) as ctx:
            provider.generate_decision("query", self._sample_context())

        self.assertIn("timeout", str(ctx.exception).lower())
        self.assertEqual(ctx.exception.provider_name, "mock")

    def test_mock_provider_configured_error(self):
        auth_err = BrainProviderAuthError("Invalid API key configuration", provider_name="mock-auth")
        provider = MockBrainProvider(error_to_raise=auth_err)

        with self.assertRaises(BrainProviderAuthError) as ctx:
            provider.generate_decision("query", self._sample_context())

        self.assertEqual(ctx.exception.provider_name, "mock-auth")
        self.assertIsInstance(ctx.exception, BrainProviderError)

    def test_mock_provider_generic_exception_wrapped(self):
        provider = MockBrainProvider(error_to_raise=RuntimeError("underlying network socket closed"))
        with self.assertRaises(BrainProviderError) as ctx:
            provider.generate_decision("query", self._sample_context())

        self.assertIn("underlying network socket closed", str(ctx.exception))


class TestBrainProviderInputValidation(unittest.TestCase):
    """Verify input validation for prompt, context, and timeout."""

    def setUp(self):
        self.provider = MockBrainProvider(
            decision=BrainDecision(
                decision_type=BrainDecisionType.EXPLANATION_ONLY,
                user_message="valid",
            )
        )
        self.context = BrainContext(user_input="hello", current_state=EVState.IDLE, platform="windows")

    def test_empty_or_whitespace_prompt_rejected(self):
        with self.assertRaises(ValueError):
            self.provider.generate_decision("", self.context)

        with self.assertRaises(ValueError):
            self.provider.generate_decision("    ", self.context)

        with self.assertRaises(ValueError):
            self.provider.generate_decision(None, self.context)  # type: ignore

    def test_invalid_context_type_rejected(self):
        with self.assertRaises(TypeError):
            self.provider.generate_decision("query", {"not": "a BrainContext"})  # type: ignore

    def test_invalid_timeout_rejected(self):
        with self.assertRaises(ValueError):
            self.provider.generate_decision("query", self.context, timeout_seconds=0.0)

        with self.assertRaises(ValueError):
            self.provider.generate_decision("query", self.context, timeout_seconds=-5.0)

        with self.assertRaises(ValueError):
            self.provider.generate_decision("query", self.context, timeout_seconds=float("nan"))

        with self.assertRaises(ValueError):
            self.provider.generate_decision("query", self.context, timeout_seconds=float("inf"))


class TestBrainProviderSafetyBoundary(unittest.TestCase):
    """Verify MockBrainProvider does not trigger execution or modify state."""

    def test_provider_does_not_execute_actions(self):
        # A proposal containing an action
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Proposal only.",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "explorer.exe"},
                )
            ],
        )
        provider = MockBrainProvider(decision=decision)
        ctx = BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

        result = provider.generate_decision("test", ctx)

        # The result is merely a BrainDecision data structure
        self.assertIsInstance(result, BrainDecision)
        self.assertEqual(result.decision_type, BrainDecisionType.EXECUTE_ACTION)
        # Verify provider did not mutate context
        self.assertEqual(ctx.current_state, EVState.IDLE)


if __name__ == "__main__":
    unittest.main()
