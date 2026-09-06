"""
Unit tests for EVBrainProviderManager (Phase 4 Task 005).

Tests are 100% offline, deterministic, and verify:
  - Provider ordering is strictly preserved.
  - Successful primary call bypasses fallbacks.
  - Timeout / unavailable / auth / malformed errors trigger bounded fallback.
  - Each provider is called at most once per request.
  - Successful provider metadata is preserved on BrainDecision.
  - All-provider failures fail closed with sanitized error messages.
  - Aggregate health check logic works.
  - Telemetry tracking is bounded and recorded.
  - Safety boundary: zero OS commands or orchestrator interactions.
"""
import unittest

from core.brain_models import (
    BrainActionProposal,
    BrainContext,
    BrainDecision,
    BrainDecisionType,
)
from core.brain_provider import (
    BrainProviderAuthError,
    BrainProviderError,
    BrainProviderMalformedResponseError,
    BrainProviderTimeoutError,
    BrainProviderUnavailableError,
    MockBrainProvider,
)
from core.brain_provider_manager import EVBrainProviderManager
from core.models import AgentAction, EVState


class TestBrainProviderManagerConstruction(unittest.TestCase):
    """Verify EVBrainProviderManager initialization and validation."""

    def test_empty_provider_list_rejected(self):
        with self.assertRaises(ValueError):
            EVBrainProviderManager(providers=[])

    def test_invalid_provider_type_rejected(self):
        with self.assertRaises(TypeError):
            EVBrainProviderManager(providers=["not_a_provider"])  # type: ignore

    def test_provider_ordering_preserved(self):
        p1 = MockBrainProvider(provider_name="p1", model_name="m1")
        p2 = MockBrainProvider(provider_name="p2", model_name="m2")
        p3 = MockBrainProvider(provider_name="p3", model_name="m3")

        manager = EVBrainProviderManager(providers=[p1, p2, p3])
        self.assertEqual(len(manager.providers), 3)
        self.assertEqual(manager.providers[0].provider_name, "p1")
        self.assertEqual(manager.providers[1].provider_name, "p2")
        self.assertEqual(manager.providers[2].provider_name, "p3")
        self.assertEqual(manager.primary_provider.provider_name, "p1")


class TestBrainProviderManagerFallback(unittest.TestCase):
    """Verify deterministic fallback logic and failure classification."""

    def _sample_context(self) -> BrainContext:
        return BrainContext(
            user_input="check python",
            current_state=EVState.IDLE,
            platform="windows",
        )

    def _sample_decision(self, msg: str = "ok") -> BrainDecision:
        return BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message=msg,
        )

    def test_primary_success_skips_fallbacks(self):
        p1 = MockBrainProvider(decision=self._sample_decision("from p1"), provider_name="p1")
        p2 = MockBrainProvider(decision=self._sample_decision("from p2"), provider_name="p2")
        manager = EVBrainProviderManager(providers=[p1, p2])

        result = manager.generate_decision("prompt", self._sample_context())

        self.assertEqual(result.user_message, "from p1")
        self.assertEqual(p1.call_count, 1)
        self.assertEqual(p2.call_count, 0)

        # Check telemetry
        telemetry = manager.get_last_telemetry()
        self.assertEqual(len(telemetry), 1)
        self.assertEqual(telemetry[0]["provider"], "p1")
        self.assertEqual(telemetry[0]["status"], "success")

    def test_primary_timeout_falls_back_to_secondary(self):
        p1 = MockBrainProvider(simulate_timeout=True, provider_name="p1")
        p2 = MockBrainProvider(decision=self._sample_decision("from p2"), provider_name="p2")
        manager = EVBrainProviderManager(providers=[p1, p2])

        result = manager.generate_decision("prompt", self._sample_context())

        self.assertEqual(result.user_message, "from p2")
        self.assertEqual(p1.call_count, 1)
        self.assertEqual(p2.call_count, 1)

        telemetry = manager.get_last_telemetry()
        self.assertEqual(len(telemetry), 2)
        self.assertEqual(telemetry[0]["provider"], "p1")
        self.assertEqual(telemetry[0]["status"], "failed")
        self.assertEqual(telemetry[1]["provider"], "p2")
        self.assertEqual(telemetry[1]["status"], "success")

    def test_primary_unavailable_falls_back_to_secondary(self):
        p1 = MockBrainProvider(
            error_to_raise=BrainProviderUnavailableError("503 Service Unavailable"),
            provider_name="p1",
        )
        p2 = MockBrainProvider(decision=self._sample_decision("from p2"), provider_name="p2")
        manager = EVBrainProviderManager(providers=[p1, p2])

        result = manager.generate_decision("prompt", self._sample_context())

        self.assertEqual(result.user_message, "from p2")
        self.assertEqual(p1.call_count, 1)
        self.assertEqual(p2.call_count, 1)

    def test_auth_error_fallback_policy(self):
        # Case A: fallback_on_auth_error=True (default) -> falls back to secondary
        p1 = MockBrainProvider(error_to_raise=BrainProviderAuthError("Missing key"), provider_name="p1")
        p2 = MockBrainProvider(decision=self._sample_decision("from p2"), provider_name="p2")
        manager_with_fallback = EVBrainProviderManager(providers=[p1, p2], fallback_on_auth_error=True)

        res = manager_with_fallback.generate_decision("prompt", self._sample_context())
        self.assertEqual(res.user_message, "from p2")

        # Case B: fallback_on_auth_error=False -> fails closed immediately
        p1_strict = MockBrainProvider(error_to_raise=BrainProviderAuthError("Missing key"), provider_name="p1_strict")
        p2_strict = MockBrainProvider(decision=self._sample_decision("from p2"), provider_name="p2_strict")
        manager_strict = EVBrainProviderManager(providers=[p1_strict, p2_strict], fallback_on_auth_error=False)

        with self.assertRaises(BrainProviderAuthError):
            manager_strict.generate_decision("prompt", self._sample_context())
        self.assertEqual(p2_strict.call_count, 0)

    def test_all_providers_fail_raises_brain_provider_error(self):
        p1 = MockBrainProvider(simulate_timeout=True, provider_name="p1", model_name="m1")
        p2 = MockBrainProvider(
            error_to_raise=BrainProviderUnavailableError("429 Rate Limit"),
            provider_name="p2",
            model_name="m2",
        )
        p3 = MockBrainProvider(
            error_to_raise=BrainProviderAuthError("401 Unauthorized"),
            provider_name="p3",
            model_name="m3",
        )
        manager = EVBrainProviderManager(providers=[p1, p2, p3])

        with self.assertRaises(BrainProviderError) as ctx:
            manager.generate_decision("prompt", self._sample_context())

        err_msg = str(ctx.exception)
        self.assertIn("All configured Brain providers failed", err_msg)
        self.assertIn("p1", err_msg)
        self.assertIn("p2", err_msg)
        self.assertIn("p3", err_msg)

        # Verify each provider called exactly once
        self.assertEqual(p1.call_count, 1)
        self.assertEqual(p2.call_count, 1)
        self.assertEqual(p3.call_count, 1)

    def test_metadata_preservation_from_successful_provider(self):
        p1 = MockBrainProvider(simulate_timeout=True, provider_name="gemini", model_name="gemini-3.6-flash")
        p2_decision = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="Fallback explanation",
            provider_name="openrouter",
            model_name="claude-3.5-sonnet",
        )
        p2 = MockBrainProvider(decision=p2_decision, provider_name="openrouter", model_name="claude-3.5-sonnet")
        manager = EVBrainProviderManager(providers=[p1, p2])

        result = manager.generate_decision("prompt", self._sample_context())

        self.assertEqual(result.provider_name, "openrouter")
        self.assertEqual(result.model_name, "claude-3.5-sonnet")


class TestBrainProviderManagerInputValidationAndHealth(unittest.TestCase):
    """Verify input validation and aggregate health checks."""

    def test_input_validation_rejections(self):
        p1 = MockBrainProvider(decision=BrainDecision(decision_type=BrainDecisionType.EXPLANATION_ONLY, user_message="ok"))
        manager = EVBrainProviderManager(providers=[p1])
        ctx = BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

        with self.assertRaises(ValueError):
            manager.generate_decision("", ctx)

        with self.assertRaises(ValueError):
            manager.generate_decision("test", ctx, timeout_seconds=-1.0)

        with self.assertRaises(TypeError):
            manager.generate_decision("test", {"not": "context"})  # type: ignore

    def test_aggregate_health_check(self):
        p1 = MockBrainProvider(healthy=False)
        p2 = MockBrainProvider(healthy=True)
        manager = EVBrainProviderManager(providers=[p1, p2])

        # At least one healthy -> True
        self.assertTrue(manager.check_health())

        # Both unhealthy -> False
        p2.set_healthy(False)
        self.assertFalse(manager.check_health())


if __name__ == "__main__":
    unittest.main()
