"""
OpenAI-Compatible, OpenRouter, and Azure Brain Providers for E.V. (Phase 4).

This module implements:
  - OpenAICompatibleProvider: Generic REST adapter for any OpenAI-compatible API.
  - OpenRouterProvider: Specialized adapter for OpenRouter.ai.
  - AzureOpenAIProvider: Specialized adapter for Azure OpenAI deployments.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx
from pydantic import ValidationError

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
    EVBrainProvider,
)
from core.models import AgentAction, VerificationType

logger = logging.getLogger("ev.brain.providers.openai_compatible")


def _sanitize_error_message(msg: str, key_to_redact: Optional[str] = None) -> str:
    """Sanitize error messages to prevent credential/key leakage."""
    if not msg:
        return "Unknown provider error"
    sanitized = str(msg)
    if key_to_redact and len(key_to_redact) > 4:
        sanitized = sanitized.replace(key_to_redact, "[REDACTED_API_KEY]")
    # Redact common key patterns
    sanitized = re.sub(r"sk-[0-9A-Za-z-_]{20,}", "[REDACTED_API_KEY]", sanitized)
    sanitized = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", sanitized)
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"api-key:\s*[A-Za-z0-9-_]+", "api-key: [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


class OpenAICompatibleProvider(EVBrainProvider):
    """
    Provider-neutral adapter for any standard OpenAI-compatible chat completions endpoint.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model_name: str = "gpt-4o-mini",
        provider_name: str = "openai_compatible",
        custom_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._provider_name = provider_name
        self._custom_headers = custom_headers or {}
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._http_client = http_client

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def base_url(self) -> str:
        return self._base_url

    def _build_system_instruction(self) -> str:
        """Construct the strict advisory system prompt with schema rules."""
        available_actions = [a.value for a in AgentAction]
        available_verifications = [v.value for v in VerificationType]

        return (
            "You are the Intelligence / Brain reasoning component for E.V. (Enhanced Virtual Intelligence on Windows).\n"
            "You are an ADVISORY assistant. You cannot directly execute commands or touch the OS.\n"
            "Your role is to understand user natural language intent and output a strictly structured JSON matching the BrainDecision schema.\n\n"
            "REQUIRED JSON SCHEMA:\n"
            "You must output a single JSON object with EXACTLY these top-level keys:\n"
            '  "decision_type": (string) one of ["EXECUTE_ACTION", "REQUEST_VERIFICATION", "REQUEST_CLARIFICATION", "REFUSAL", "EXPLANATION_ONLY"]\n'
            '  "user_message": (string) the response, message, or explanation to display to the user\n'
            '  "decision_summary": (optional string) brief summary of reasoning\n'
            '  "proposed_actions": (array) list of action objects [{"action": "...", "parameters": {...}, "description": "..."}], or []\n\n'
            "CRITICAL RULES:\n"
            '1. Output MUST be valid JSON conforming strictly to the above keys. Do NOT use "action" or "message" as top-level keys.\n'
            "2. Available proposed actions are strictly limited to these enum values: "
            f"{json.dumps(available_actions)}.\n"
            "3. Available verification types are strictly limited to: "
            f"{json.dumps(available_verifications)}.\n"
            "4. NEVER invent tool names, action names, or unauthorized capabilities.\n"
            '5. If the user prompt is a question, conversational request, or asks to reply with specific text, set "decision_type" to "EXPLANATION_ONLY" and set "user_message" to the requested text or answer.\n'
            "6. Output ONLY the JSON object. Do NOT wrap in markdown fences or include introductory text."
        )

    def _build_messages(self, prompt: str, context: BrainContext) -> list[dict[str, str]]:
        """Construct system and user messages containing bounded context."""
        context_payload = {
            "user_prompt": prompt,
            "system_state": context.current_state.value,
            "platform": context.platform,
            "recent_tasks": context.recent_task_summaries,
        }
        if context.verification_context:
            context_payload["verification_context"] = context.verification_context

        user_content = (
            "=== UNTRUSTED USER INPUT AND CONTEXT ===\n"
            f"{json.dumps(context_payload, indent=2)}\n"
            "========================================"
        )

        return [
            {"role": "system", "content": self._build_system_instruction()},
            {"role": "user", "content": user_content},
        ]

    def _get_request_headers(self) -> dict[str, str]:
        """Construct sanitized request headers."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        headers.update(self._custom_headers)
        return headers

    def _get_completion_url(self) -> str:
        """Return endpoint URL for chat completions."""
        return f"{self._base_url}/chat/completions"

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        """
        Generate a structured BrainDecision via the OpenAI-compatible REST endpoint.
        """
        self._validate_inputs(prompt, context, timeout_seconds)

        if not self._api_key and self._http_client is None:
            raise BrainProviderAuthError(
                f"API key is required for {self.provider_name}",
                provider_name=self.provider_name,
            )

        url = self._get_completion_url()
        headers = self._get_request_headers()
        messages = self._build_messages(prompt, context)

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            if self._http_client is not None:
                response = self._http_client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                )
            else:
                with httpx.Client(timeout=timeout_seconds) as client:
                    response = client.post(url, json=payload, headers=headers)

        except (httpx.TimeoutException, TimeoutError) as e:
            raise BrainProviderTimeoutError(
                f"{self.provider_name} request timed out after {timeout_seconds}s",
                provider_name=self.provider_name,
            ) from e
        except (httpx.ConnectError, httpx.NetworkError, ConnectionError) as e:
            sanitized = _sanitize_error_message(str(e), self._api_key)
            raise BrainProviderUnavailableError(
                f"{self.provider_name} endpoint unreachable: {sanitized}",
                provider_name=self.provider_name,
            ) from e
        except Exception as e:
            sanitized = _sanitize_error_message(str(e), self._api_key)
            raise BrainProviderError(
                f"{self.provider_name} error: {sanitized}",
                provider_name=self.provider_name,
            ) from e

        return self._parse_http_response(response)

    def _parse_http_response(self, response: httpx.Response) -> BrainDecision:
        """Parse the HTTP response and validate into BrainDecision."""
        status_code = response.status_code

        if status_code in (401, 403):
            sanitized_body = _sanitize_error_message(response.text[:300], self._api_key)
            raise BrainProviderAuthError(
                f"{self.provider_name} authentication failed ({status_code}): {sanitized_body}",
                provider_name=self.provider_name,
            )

        if status_code in (408, 504):
            raise BrainProviderTimeoutError(
                f"{self.provider_name} gateway timed out ({status_code})",
                provider_name=self.provider_name,
            )

        if status_code in (429, 500, 502, 503):
            sanitized_body = _sanitize_error_message(response.text[:300], self._api_key)
            raise BrainProviderUnavailableError(
                f"{self.provider_name} service unavailable / rate limited ({status_code}): {sanitized_body}",
                provider_name=self.provider_name,
            )

        if status_code != 200:
            sanitized_body = _sanitize_error_message(response.text[:300], self._api_key)
            raise BrainProviderError(
                f"{self.provider_name} returned HTTP {status_code}: {sanitized_body}",
                provider_name=self.provider_name,
            )

        # Parse response body
        try:
            data = response.json()
        except Exception as e:
            raise BrainProviderMalformedResponseError(
                f"Failed to decode {self.provider_name} response JSON: {e}",
                provider_name=self.provider_name,
            ) from e

        choices = data.get("choices")
        if not choices or not isinstance(choices, list) or len(choices) == 0:
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} response missing 'choices' list",
                provider_name=self.provider_name,
            )

        message = choices[0].get("message", {})
        raw_content = message.get("content")
        if not raw_content or not str(raw_content).strip():
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} choice content is empty",
                provider_name=self.provider_name,
            )

        try:
            # Strip markdown fences if present
            raw_clean = raw_content.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_clean = "\n".join(lines).strip()

            parsed_json = json.loads(raw_clean)
            if isinstance(parsed_json, dict):
                # Normalize common LLM key naming variations
                if "decision_type" not in parsed_json:
                    if "action" in parsed_json and parsed_json["action"] in [e.value for e in BrainDecisionType]:
                        parsed_json["decision_type"] = parsed_json.pop("action")
                    elif "decision" in parsed_json and parsed_json["decision"] in [e.value for e in BrainDecisionType]:
                        parsed_json["decision_type"] = parsed_json.pop("decision")
                    elif "decision" in parsed_json and parsed_json["decision"] == "DIRECT_ANSWER":
                        parsed_json["decision_type"] = "EXPLANATION_ONLY"
                        parsed_json.pop("decision", None)
                    else:
                        parsed_json["decision_type"] = "EXPLANATION_ONLY"
                if "user_message" not in parsed_json:
                    if "message" in parsed_json:
                        parsed_json["user_message"] = str(parsed_json.pop("message"))
                    elif "response" in parsed_json:
                        parsed_json["user_message"] = str(parsed_json.pop("response"))
                    elif "text" in parsed_json:
                        parsed_json["user_message"] = str(parsed_json.pop("text"))
                    elif "content" in parsed_json:
                        parsed_json["user_message"] = str(parsed_json.pop("content"))
                    else:
                        parsed_json["user_message"] = "Response completed."
                if "decision_summary" not in parsed_json and "reasoning" in parsed_json:
                    parsed_json["decision_summary"] = str(parsed_json.pop("reasoning"))[:500]
                allowed_keys = {
                    "decision_id", "decision_type", "user_message", "decision_summary",
                    "proposed_actions", "clarification_prompt", "confidence", "provider_name",
                    "model_name", "token_usage", "created_at"
                }
                filtered_json = {k: v for k, v in parsed_json.items() if k in allowed_keys}
                decision = BrainDecision.model_validate(filtered_json)
            else:
                decision = BrainDecision.model_validate_json(raw_clean)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} output failed BrainDecision validation: {e}",
                provider_name=self.provider_name,
            ) from e

        # Ensure metadata is preserved
        updates: dict[str, Any] = {}
        if not decision.provider_name:
            updates["provider_name"] = self.provider_name
        if not decision.model_name:
            updates["model_name"] = self.model_name

        if updates:
            return decision.model_copy(update=updates)
        return decision

    def check_health(self) -> bool:
        """Check provider health via client availability or basic ping."""
        if not self._api_key and self._http_client is None:
            return False
        return True


class OpenRouterProvider(OpenAICompatibleProvider):
    """
    OpenRouter adapter configured with recommended default models and headers.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
        model_name: Optional[str] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        resolved_model = model_name or os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        headers = dict(custom_headers or {})
        headers.setdefault("HTTP-Referer", "https://github.com/ev-agent/ev")
        headers.setdefault("X-Title", "E.V. Virtual Intelligence")

        super().__init__(
            api_key=resolved_key,
            base_url=base_url,
            model_name=resolved_model,
            provider_name="openrouter",
            custom_headers=headers,
            http_client=http_client,
        )


class AzureOpenAIProvider(OpenAICompatibleProvider):
    """
    Azure OpenAI Service provider adapter.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        deployment_name: Optional[str] = None,
        api_version: str = "2024-06-01",
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._endpoint = (endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT", "")).rstrip("/")
        resolved_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY")
        self._deployment_name = deployment_name or os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        self._api_version = api_version

        base_url = f"{self._endpoint}/openai/deployments/{self._deployment_name}" if self._endpoint else ""

        super().__init__(
            api_key=resolved_key,
            base_url=base_url,
            model_name=self._deployment_name,
            provider_name="azure_openai",
            http_client=http_client,
        )

    def _get_completion_url(self) -> str:
        return f"{self._base_url}/chat/completions?api-version={self._api_version}"

    def _get_request_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["api-key"] = self._api_key
        headers.update(self._custom_headers)
        return headers
