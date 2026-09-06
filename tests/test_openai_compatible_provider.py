"""
Unit tests for OpenAI-Compatible, OpenRouter, and Azure Providers (Phase 4 Task 005).

All tests are 100% offline and deterministic using mocked HTTP clients and responses.
Zero live API requests or external network calls are used in default regression tests.
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
from providers.openai_compatible_provider import (
    AzureOpenAIProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
    _sanitize_error_message,
)


class TestOpenAICompatibleProvider(unittest.TestCase):
    """Verify OpenAICompatibleProvider REST handling and error translations."""

    def setUp(self):
        self.mock_http = MagicMock(spec=httpx.Client)
        self.provider = OpenAICompatibleProvider(
            api_key="test-key-sk-12345678901234567890",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4o-mini",
            http_client=self.mock_http,
        )
        self.context = BrainContext(
            user_input="Is python running?",
            current_state=EVState.IDLE,
            platform="windows",
        )

    def test_missing_api_key_raises_auth_error(self):
        with patch.dict(os.environ, {}, clear=True):
            if "OPENAI_API_KEY" in os.environ:
                del os.environ["OPENAI_API_KEY"]
            provider = OpenAICompatibleProvider(api_key=None, http_client=None)
            with self.assertRaises(BrainProviderAuthError):
                provider.generate_decision("prompt", self.context)

    def test_successful_decision_generation(self):
        json_content = {
            "decision_type": "EXECUTE_ACTION",
            "user_message": "Checking for Python process.",
            "proposed_actions": [
                {
                    "action": "FIND_PROCESS",
                    "parameters": {"name": "python.exe"},
                }
            ],
            "confidence": 0.95,
        }
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": str(BrainDecision.model_validate(json_content).model_dump_json())}}]
        }
        self.mock_http.post.return_value = mock_response

        result = self.provider.generate_decision("Is python running?", self.context)

        self.assertIsInstance(result, BrainDecision)
        self.assertEqual(result.decision_type, BrainDecisionType.EXECUTE_ACTION)
        self.assertEqual(result.proposed_actions[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(result.provider_name, "openai_compatible")
        self.assertEqual(result.model_name, "gpt-4o-mini")

    def test_malformed_json_response_fails_closed(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Not valid json"}}]
        }
        self.mock_http.post.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("prompt", self.context)

    def test_empty_choices_fails_closed(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"choices": []}
        self.mock_http.post.return_value = mock_response

        with self.assertRaises(BrainProviderMalformedResponseError):
            self.provider.generate_decision("prompt", self.context)

    def test_http_401_raises_auth_error(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 401
        mock_response.text = "Incorrect API key provided"
        self.mock_http.post.return_value = mock_response

        with self.assertRaises(BrainProviderAuthError) as ctx:
            self.provider.generate_decision("prompt", self.context)
        self.assertIn("authentication", str(ctx.exception).lower())

    def test_http_429_raises_unavailable_error(self):
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 429
        mock_response.text = "Rate limit reached"
        self.mock_http.post.return_value = mock_response

        with self.assertRaises(BrainProviderUnavailableError) as ctx:
            self.provider.generate_decision("prompt", self.context)
        self.assertIn("rate limited", str(ctx.exception).lower())

    def test_timeout_raises_timeout_error(self):
        self.mock_http.post.side_effect = httpx.TimeoutException("Read timeout")

        with self.assertRaises(BrainProviderTimeoutError) as ctx:
            self.provider.generate_decision("prompt", self.context, timeout_seconds=5.0)
        self.assertIn("timed out", str(ctx.exception).lower())


class TestOpenRouterProvider(unittest.TestCase):
    """Verify OpenRouter-specific adapter defaults and headers."""

    def test_openrouter_defaults_and_headers(self):
        mock_http = MagicMock(spec=httpx.Client)
        provider = OpenRouterProvider(
            api_key="test-openrouter-key",
            model_name="anthropic/claude-3.5-sonnet",
            http_client=mock_http,
        )

        self.assertEqual(provider.provider_name, "openrouter")
        self.assertEqual(provider.model_name, "anthropic/claude-3.5-sonnet")
        self.assertEqual(provider.base_url, "https://openrouter.ai/api/v1")

        headers = provider._get_request_headers()
        self.assertEqual(headers["HTTP-Referer"], "https://github.com/ev-agent/ev")
        self.assertEqual(headers["X-Title"], "E.V. Virtual Intelligence")
        self.assertEqual(headers["Authorization"], "Bearer test-openrouter-key")


class TestAzureOpenAIProvider(unittest.TestCase):
    """Verify Azure OpenAI Service adapter and URL construction."""

    def test_azure_url_and_headers(self):
        mock_http = MagicMock(spec=httpx.Client)
        provider = AzureOpenAIProvider(
            endpoint="https://my-azure-instance.openai.azure.com",
            api_key="test-azure-key",
            deployment_name="gpt-4o",
            api_version="2024-06-01",
            http_client=mock_http,
        )

        self.assertEqual(provider.provider_name, "azure_openai")
        self.assertEqual(provider.model_name, "gpt-4o")

        url = provider._get_completion_url()
        self.assertEqual(
            url,
            "https://my-azure-instance.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2024-06-01",
        )

        headers = provider._get_request_headers()
        self.assertEqual(headers["api-key"], "test-azure-key")


class TestSecurityAndSanitization(unittest.TestCase):
    """Verify credential and token sanitization across error messages."""

    def test_error_message_redaction(self):
        raw_msg = "Error using sk-12345678901234567890 with Bearer secret_tok_12345 and api-key: my_azure_secret_999"
        sanitized = _sanitize_error_message(raw_msg)

        self.assertNotIn("sk-12345678901234567890", sanitized)
        self.assertNotIn("secret_tok_12345", sanitized)
        self.assertNotIn("my_azure_secret_999", sanitized)
        self.assertIn("[REDACTED_API_KEY]", sanitized)
        self.assertIn("Bearer [REDACTED]", sanitized)
        self.assertIn("api-key: [REDACTED]", sanitized)


if __name__ == "__main__":
    unittest.main()
