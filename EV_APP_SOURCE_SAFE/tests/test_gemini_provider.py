"""
Unit tests for Google Gemini Brain Provider (Phase 4 Task 004).

All tests are 100% offline and deterministic, using mocked clients and responses.
Zero live API requests or secrets are used in the default regression test suite.
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import httpx

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
)
from core.models import AgentAction, EVState, VerificationType
from providers.gemini_provider import (
    GeminiProvider,
    _sanitize_error_message,
)


class TestGeminiProviderConstruction(unittest.TestCase):
    """Verify GeminiProvider instantiation, API key handling, and metadata."""

    def test_missing_api_key_raises_auth_error(self):
        with patch.dict(os.environ, {}, clear=True):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            with self.assertRaises(BrainProviderAuthError) as ctx:
                GeminiProvider(api_key=None, client=None)
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))
            self.assertEqual(ctx.exception.provider_name, "gemini")

    def test_constructor_with_injected_client(self):
        mock_client = MagicMock()
        provider = GeminiProvider(client=mock_client, model_name="gemini-2.0-flash")

        self.assertEqual(provider.provider_name, "gemini")
        self.assertEqual(provider.model_name, "gemini-2.0-flash")

    def test_custom_model_name(self):
        mock_client = MagicMock()
        provider = GeminiProvider(client=mock_client, model_name="gemini-1.5-pro-latest")

        self.assertEqual(provider.model_name, "gemini-1.5-pro-latest")


class TestGeminiProviderSuccessfulGeneration(unittest.TestCase):
    """Verify structured response generation and Pydantic BrainDecision mapping."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.provider = GeminiProvider(client=self.mock_client, model_name="gemini-2.0-flash")
        self.context = BrainContext(
            user_input="Is python running?",
            current_state=EVState.IDLE,
            platform="windows",
        )

    def test_successful_decision_with_parsed_model(self):
        # Mock structured response with response.parsed as BrainDecision
        expected_decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Checking for Python process.",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "python.exe"},
                )
            ],
            confidence=0.97,
        )
        mock_response = MagicMock()
        mock_response.parsed = expected_decision
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.provider.generate_decision("Is python running?", self.context)

        self.assertIsInstance(result, BrainDecision)
        self.assertEqual(result.decision_type, BrainDecisionType.EXECUTE_ACTION)
        self.assertEqual(result.proposed_actions[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(result.provider_name, "gemini")
        self.assertEqual(result.model_name, "gemini-2.0-flash")

    def test_successful_decision_with_json_text_fallback(self):
        # Mock structured response where response.text contains JSON string
        json_payload = {
            "decision_type": "EXPLANATION_ONLY",
            "user_message": "Python is an interpreted programming language.",
            "decision_summary": "Informational answer",
            "confidence": 1.0,
        }
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"decision_type": "EXPLANATION_ONLY", "user_message": "Python is an interpreted programming language.", "decision_summary": "Informational answer", "confidence": 1.0}'
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.provider.generate_decision("What is python?", self.context)

        self.assertIsInstance(result, BrainDecision)
        self.assertEqual(result.decision_type, BrainDecisionType.EXPLANATION_ONLY)
        self.assertEqual(result.user_message, "Python is an interpreted programming language.")
        self.assertEqual(result.provider_name, "gemini")

    def test_successful_verification_decision(self):
        expected_decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_VERIFICATION,
            user_message="Verifying that port 8080 is listening.",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_TCP_PORT,
                    parameters={"port": 8080},
                    verification_type=VerificationType.TCP_PORT_EXISTS,
                )
            ],
            confidence=0.99,
        )
        mock_response = MagicMock()
        mock_response.parsed = expected_decision
        self.mock_client.models.generate_content.return_value = mock_response

        result = self.provider.generate_decision("Verify port 8080", self.context)

        self.assertEqual(result.decision_type, BrainDecisionType.REQUEST_VERIFICATION)
        self.assertEqual(result.proposed_actions[0].verification_type, VerificationType.TCP_PORT_EXISTS)


class TestGeminiProviderMalformedOutputFailClosed(unittest.TestCase):
    """Verify malformed, invalid, or hallucinated responses fail closed."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.provider = GeminiProvider(client=self.mock_client)
        self.context = BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

    def test_empty_response_fails_closed(self):
        self.mock_client.models.generate_content.return_value = None

        with self.assertRaises(BrainProviderMalformedResponseError) as ctx:
            self.provider.generate_decision("test", self.context)
        self.assertIn("empty", str(ctx.exception).lower())

    def test_malformed_json_text_fails_closed(self):
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = "This is not valid JSON"
        self.mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("test", self.context)

    def test_invalid_action_enum_fails_closed(self):
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"decision_type": "EXECUTE_ACTION", "user_message": "ok", "proposed_actions": [{"action": "FORMAT_HARD_DRIVE", "parameters": {}}]}'
        self.mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("test", self.context)

    def test_extra_forbidden_field_fails_closed(self):
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"decision_type": "EXPLANATION_ONLY", "user_message": "ok", "unauthorized_admin_mode": true}'
        self.mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("test", self.context)

    def test_invalid_confidence_fails_closed(self):
        mock_response = MagicMock()
        mock_response.parsed = None
        mock_response.text = '{"decision_type": "EXPLANATION_ONLY", "user_message": "ok", "confidence": 1.5}'
        self.mock_client.models.generate_content.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("test", self.context)


class TestGeminiProviderErrorTranslation(unittest.TestCase):
    """Verify underlying API/network exceptions are translated to BrainProviderError hierarchy."""

    def setUp(self):
        self.mock_client = MagicMock()
        self.provider = GeminiProvider(client=self.mock_client)
        self.context = BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

    def test_timeout_translation(self):
        self.mock_client.models.generate_content.side_effect = httpx.TimeoutException("Read timed out")

        with self.assertRaises(BrainProviderTimeoutError) as ctx:
            self.provider.generate_decision("test", self.context, timeout_seconds=5.0)

        self.assertIn("timed out", str(ctx.exception).lower())

    def test_auth_error_translation(self):
        self.mock_client.models.generate_content.side_effect = RuntimeError("API_KEY_INVALID: 401 Unauthorized")

        with self.assertRaises(BrainProviderAuthError) as ctx:
            self.provider.generate_decision("test", self.context)

        self.assertIn("authentication", str(ctx.exception).lower())

    def test_rate_limit_unavailable_translation(self):
        self.mock_client.models.generate_content.side_effect = RuntimeError("ResourceExhausted: 429 Quota exceeded")

        with self.assertRaises(BrainProviderUnavailableError) as ctx:
            self.provider.generate_decision("test", self.context)

        self.assertIn("unavailable", str(ctx.exception).lower())

    def test_generic_error_translation(self):
        self.mock_client.models.generate_content.side_effect = RuntimeError("Internal server error 500")

        with self.assertRaises(BrainProviderError) as ctx:
            self.provider.generate_decision("test", self.context)

        self.assertIn("gemini provider error", str(ctx.exception).lower())


class TestGeminiProviderSecurityAndSanitization(unittest.TestCase):
    """Verify that credentials and secrets are not leaked in exceptions or messages."""

    def test_sanitize_error_message_redacts_api_key(self):
        raw_key = "AIzaSyD-1234567890abcdefghijklmnopqrst"
        raw_error = f"Request failed with key {raw_key} at endpoint"
        sanitized = _sanitize_error_message(raw_error, key_to_redact=raw_key)

        self.assertNotIn(raw_key, sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)

    def test_sanitize_error_message_redacts_bearer_token(self):
        raw_error = "Authorization header Bearer ya29.a0AfH6SM... rejected"
        sanitized = _sanitize_error_message(raw_error)

        self.assertNotIn("ya29.a0AfH6SM", sanitized)
        self.assertIn("Bearer [REDACTED]", sanitized)

    def test_input_validation_prevents_empty_prompts(self):
        mock_client = MagicMock()
        provider = GeminiProvider(client=mock_client)
        ctx = BrainContext(user_input="test", current_state=EVState.IDLE, platform="windows")

        with self.assertRaises(ValueError):
            provider.generate_decision("", ctx)

        with self.assertRaises(ValueError):
            provider.generate_decision("   ", ctx)


class TestGeminiProviderHealthCheck(unittest.TestCase):
    """Verify health check logic."""

    def test_health_check_healthy(self):
        mock_client = MagicMock()
        provider = GeminiProvider(client=mock_client, api_key="valid-test-key")

        self.assertTrue(provider.check_health())

    def test_health_check_failure_returns_false(self):
        mock_client = MagicMock()
        mock_client.models.get.side_effect = RuntimeError("Connection refused")
        provider = GeminiProvider(client=mock_client, api_key="valid-test-key")

        self.assertFalse(provider.check_health())


if __name__ == "__main__":
    unittest.main()
