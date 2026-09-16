"""
Anthropic Claude Brain Provider for E.V. (Phase 4).

This module implements AnthropicProvider, a native REST adapter for Anthropic's
Messages API (https://api.anthropic.com/v1/messages) that conforms to the
EVBrainProvider interface and returns structured BrainDecision objects.
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
    BrainContext,
    BrainDecision,
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

logger = logging.getLogger("ev.brain.providers.anthropic")


def _sanitize_error_message(msg: str, key_to_redact: Optional[str] = None) -> str:
    """Sanitize error messages to prevent credential/key leakage."""
    if not msg:
        return "Unknown provider error"
    sanitized = str(msg)
    if key_to_redact and len(key_to_redact) > 4:
        sanitized = sanitized.replace(key_to_redact, "[REDACTED_API_KEY]")
    sanitized = re.sub(r"sk-ant-[0-9A-Za-z-_]{20,}", "[REDACTED_API_KEY]", sanitized)
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"x-api-key:\s*[A-Za-z0-9-_]+", "x-api-key: [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


class AnthropicProvider(EVBrainProvider):
    """
    Native REST adapter for Anthropic Claude Messages API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.anthropic.com/v1",
        model_name: str = "claude-3-5-sonnet-20241022",
        provider_name: str = "anthropic",
        custom_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._provider_name = provider_name
        self._custom_headers = custom_headers or {}
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
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
            "CRITICAL RULES:\n"
            "1. Output MUST be valid JSON conforming strictly to BrainDecision schema.\n"
            "2. Available proposed actions are strictly limited to these enum values: "
            f"{json.dumps(available_actions)}.\n"
            "3. Available verification types are strictly limited to: "
            f"{json.dumps(available_verifications)}.\n"
            "4. NEVER invent tool names, action names, or unauthorized capabilities.\n"
            "5. If an action is not executable safely or supported, choose REFUSAL or EXPLANATION_ONLY.\n"
            "6. If the user's intent is ambiguous, choose REQUEST_CLARIFICATION.\n"
            "7. If the user asks to verify a state, choose REQUEST_VERIFICATION with an appropriate action and verification_type.\n"
            "8. Output ONLY the raw JSON object. Do NOT wrap in markdown fences or include introductory text."
        )

    def _build_user_message(self, prompt: str, context: BrainContext) -> str:
        """Construct user message containing bounded context."""
        context_payload = {
            "user_prompt": prompt,
            "system_state": context.current_state.value,
            "platform": context.platform,
            "recent_tasks": context.recent_task_summaries,
        }
        if context.verification_context:
            context_payload["verification_context"] = context.verification_context

        return (
            "=== UNTRUSTED USER INPUT AND CONTEXT ===\n"
            f"{json.dumps(context_payload, indent=2)}\n"
            "========================================"
        )

    def _get_request_headers(self) -> dict[str, str]:
        """Construct sanitized request headers for Anthropic."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        headers.update(self._custom_headers)
        return headers

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        """Generate a structured BrainDecision via Anthropic Messages API."""
        self._validate_inputs(prompt, context, timeout_seconds)

        if not self._api_key and self._http_client is None:
            raise BrainProviderAuthError(
                f"API key is required for {self.provider_name}",
                provider_name=self.provider_name,
            )

        url = f"{self._base_url}/messages"
        headers = self._get_request_headers()

        payload: dict[str, Any] = {
            "model": self._model_name,
            "system": self._build_system_instruction(),
            "messages": [
                {"role": "user", "content": self._build_user_message(prompt, context)}
            ],
            "max_tokens": 1024,
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

        try:
            data = response.json()
        except Exception as e:
            raise BrainProviderMalformedResponseError(
                f"Failed to decode {self.provider_name} response JSON: {e}",
                provider_name=self.provider_name,
            ) from e

        content_blocks = data.get("content", [])
        if not content_blocks or not isinstance(content_blocks, list):
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} response missing 'content' list",
                provider_name=self.provider_name,
            )

        raw_text = ""
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                raw_text += block.get("text", "")

        if not raw_text.strip():
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} response content is empty",
                provider_name=self.provider_name,
            )

        clean_json = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean_json, re.DOTALL)
        if fence_match:
            clean_json = fence_match.group(1).strip()

        try:
            decision = BrainDecision.model_validate_json(clean_json)
        except (ValidationError, ValueError) as e:
            raise BrainProviderMalformedResponseError(
                f"{self.provider_name} output failed BrainDecision validation: {e}",
                provider_name=self.provider_name,
            ) from e

        updates: dict[str, Any] = {}
        if not decision.provider_name:
            updates["provider_name"] = self.provider_name
        if not decision.model_name:
            updates["model_name"] = self.model_name

        if updates:
            return decision.model_copy(update=updates)
        return decision

    def check_health(self) -> bool:
        return bool(self._api_key or self._http_client is not None)
