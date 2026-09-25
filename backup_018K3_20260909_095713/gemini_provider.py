"""
Google Gemini Brain Provider for E.V. (Phase 4).

This module implements GeminiProvider, adapting Google's official Gemini API
(via the google-genai SDK) to the EVBrainProvider interface.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx
from pydantic import ValidationError

try:
    from google import genai
    from google.genai import errors as genai_errors
    from google.genai import types as genai_types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    genai_errors = None
    genai_types = None
    GENAI_AVAILABLE = False

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

logger = logging.getLogger("ev.brain.providers.gemini")

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


def _sanitize_error_message(msg: str, key_to_redact: Optional[str] = None) -> str:
    """Sanitize error messages to prevent credential/key leakage."""
    if not msg:
        return "Unknown Gemini provider error"
    sanitized = str(msg)
    if key_to_redact and len(key_to_redact) > 4:
        sanitized = sanitized.replace(key_to_redact, "[REDACTED_API_KEY]")
    # Redact common key patterns (e.g. AIzaSy...)
    sanitized = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", sanitized)
    # Redact Bearer tokens
    sanitized = re.sub(r"Bearer\s+[A-Za-z0-9\-\._~\+\/]+=*", "Bearer [REDACTED]", sanitized, flags=re.IGNORECASE)
    return sanitized


def _clean_schema_for_gemini(schema: Any) -> Any:
    """
    Remove 'additionalProperties' from JSON schema dictionary because
    Gemini Developer API mode does not support this property.
    Also provides property hints on the parameters dictionary schema so Gemini
    reliably populates action parameters.
    """
    if isinstance(schema, dict):
        cleaned = {}
        for k, v in schema.items():
            if k == "additionalProperties":
                continue
            cleaned[k] = _clean_schema_for_gemini(v)
        if cleaned.get("title") == "Parameters" and cleaned.get("type") == "object":
            cleaned["properties"] = {
                "name": {"type": "string", "description": "Process name (e.g. 'explorer.exe') or service name (e.g. 'Spooler')"},
                "port": {"type": "integer", "description": "TCP port number (1-65535)"},
                "path": {"type": "string", "description": "Filesystem path for file/directory inspection"},
                "pattern": {"type": "string", "description": "File search pattern (e.g. '*.log')"},
                "root": {"type": "string", "description": "Root directory path for file searches"},
                "text": {"type": "string", "description": "Search text substring"},
                "root_or_file": {"type": "string", "description": "Root directory or file path for text searches"},
            }
        return cleaned
    elif isinstance(schema, list):
        return [_clean_schema_for_gemini(item) for item in schema]
    return schema


class GeminiProvider(EVBrainProvider):
    """
    Concrete EVBrainProvider adapter for Google Gemini via the google-genai SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_GEMINI_MODEL,
        client: Optional[Any] = None,
    ) -> None:
        """
        Initialize the GeminiProvider.

        Args:
            api_key: Gemini API key. If None, reads from GEMINI_API_KEY environment variable.
            model_name: Gemini model name (default: 'gemini-3.6-flash').
            client: Optional pre-configured genai.Client instance (useful for testing/mocking).
        """
        self._model_name = model_name or DEFAULT_GEMINI_MODEL
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._client = client

        if self._client is None:
            if not self._api_key:
                raise BrainProviderAuthError(
                    "GEMINI_API_KEY environment variable or api_key parameter is required",
                    provider_name="gemini",
                )
            if not GENAI_AVAILABLE:
                raise BrainProviderError(
                    "google-genai SDK is not installed in the environment",
                    provider_name="gemini",
                )
            try:
                self._client = genai.Client(api_key=self._api_key)
            except Exception as e:
                sanitized_err = _sanitize_error_message(str(e), self._api_key)
                raise BrainProviderAuthError(
                    f"Failed to initialize Gemini client: {sanitized_err}",
                    provider_name="gemini",
                ) from e

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def _build_system_instruction(self) -> str:
        """
        Construct a strict, bounded system instruction for the Gemini model.
        """
        available_actions = [a.value for a in AgentAction]
        available_verifications = [v.value for v in VerificationType]

        return (
            "You are the Intelligence / Brain reasoning component for E.V. (Enhanced Virtual Intelligence on Windows).\n"
            "You are an ADVISORY assistant. You cannot directly execute commands or touch the OS.\n"
            "Your role is to understand user natural language intent and output a strictly structured BrainDecision JSON.\n\n"
            "CRITICAL RULES:\n"
            "1. Output MUST strictly match the BrainDecision schema.\n"
            "2. Available proposed actions are strictly limited to these enum values: "
            f"{json.dumps(available_actions)}.\n"
            "3. Available verification types are strictly limited to: "
            f"{json.dumps(available_verifications)}.\n"
            "4. NEVER invent tool names, action names, or unauthorized capabilities.\n"
            "5. If an action is not executable safely or supported, choose REFUSAL or EXPLANATION_ONLY.\n"
            "6. If the user's intent is ambiguous, choose REQUEST_CLARIFICATION.\n"
            "7. If the user asks to verify a state, choose REQUEST_VERIFICATION with an appropriate action and verification_type.\n"
            "8. Keep user_message and decision_summary concise, professional, and suitable for a HUD display."
        )

    def _build_user_content(self, prompt: str, context: BrainContext) -> str:
        """
        Build the structured user prompt payload containing bounded context.
        """
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

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        """
        Generate a structured BrainDecision using Google Gemini.
        """
        self._validate_inputs(prompt, context, timeout_seconds)

        if self._client is None:
            raise BrainProviderAuthError(
                "Gemini client is not initialized",
                provider_name=self.provider_name,
            )

        system_instruction = self._build_system_instruction()
        user_content = self._build_user_content(prompt, context)

        # Prepare cleaned JSON schema for Gemini Developer API
        raw_schema = BrainDecision.model_json_schema()
        cleaned_schema = _clean_schema_for_gemini(raw_schema)

        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": cleaned_schema,
            "system_instruction": system_instruction,
        }

        # Build config object if genai_types is available
        if genai_types is not None:
            config = genai_types.GenerateContentConfig(**config_kwargs)
        else:
            config = config_kwargs

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=user_content,
                config=config,
            )
        except httpx.TimeoutException as e:
            raise BrainProviderTimeoutError(
                f"Gemini API request timed out after {timeout_seconds}s",
                provider_name=self.provider_name,
            ) from e
        except Exception as e:
            self._handle_api_exception(e)

        # Parse and validate response
        return self._parse_gemini_response(response)

    def _parse_gemini_response(self, response: Any) -> BrainDecision:
        """
        Parse and validate the raw Gemini SDK response into a BrainDecision.
        """
        if response is None:
            raise BrainProviderMalformedResponseError(
                "Gemini API returned an empty response",
                provider_name=self.provider_name,
            )

        # 1. If response.parsed is already a validated BrainDecision instance
        if hasattr(response, "parsed") and isinstance(response.parsed, BrainDecision):
            decision = response.parsed
            return self._ensure_metadata(decision)

        # 2. If response.parsed is a dict or model-like object
        if hasattr(response, "parsed") and response.parsed is not None:
            try:
                if isinstance(response.parsed, dict):
                    decision = BrainDecision.model_validate(response.parsed)
                elif hasattr(response.parsed, "model_dump"):
                    decision = BrainDecision.model_validate(response.parsed.model_dump())
                else:
                    decision = BrainDecision.model_validate(response.parsed)
                return self._ensure_metadata(decision)
            except ValidationError as e:
                raise BrainProviderMalformedResponseError(
                    f"Gemini parsed response failed BrainDecision validation: {e}",
                    provider_name=self.provider_name,
                ) from e

        # 3. Fallback to response.text JSON parsing
        raw_text = getattr(response, "text", None)
        if not raw_text or not str(raw_text).strip():
            raise BrainProviderMalformedResponseError(
                "Gemini API response contained no text or structured output",
                provider_name=self.provider_name,
            )

        try:
            decision = BrainDecision.model_validate_json(raw_text)
            return self._ensure_metadata(decision)
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            raise BrainProviderMalformedResponseError(
                f"Failed to validate Gemini response text as BrainDecision: {e}",
                provider_name=self.provider_name,
            ) from e

    def _ensure_metadata(self, decision: BrainDecision) -> BrainDecision:
        """Ensure provider metadata is populated on the decision."""
        updates: dict[str, Any] = {}
        if not decision.provider_name:
            updates["provider_name"] = self.provider_name
        if not decision.model_name:
            updates["model_name"] = self.model_name

        if updates:
            return decision.model_copy(update=updates)
        return decision

    def _handle_api_exception(self, exc: Exception) -> None:
        """
        Translate underlying SDK/network exceptions to provider-neutral BrainProviderError hierarchy.
        """
        err_msg = _sanitize_error_message(str(exc), self._api_key)

        # Check for timeout
        if "timeout" in err_msg.lower() or "timed out" in err_msg.lower() or "deadline" in err_msg.lower():
            raise BrainProviderTimeoutError(
                f"Gemini API timed out: {err_msg}",
                provider_name=self.provider_name,
            ) from exc

        # Check for authentication / authorization errors
        if any(w in err_msg.lower() for w in ["api_key", "invalid api key", "unauthenticated", "permission_denied", "forbidden", "401", "403"]):
            raise BrainProviderAuthError(
                f"Gemini authentication failed: {err_msg}",
                provider_name=self.provider_name,
            ) from exc

        # Check for rate limits / quota / service unavailable
        if any(w in err_msg.lower() for w in ["rate limit", "resource_exhausted", "quota", "429", "503", "unavailable", "service unavailable"]):
            raise BrainProviderUnavailableError(
                f"Gemini service unavailable or rate limited: {err_msg}",
                provider_name=self.provider_name,
            ) from exc

        # Generic provider error
        raise BrainProviderError(
            f"Gemini provider error: {err_msg}",
            provider_name=self.provider_name,
        ) from exc

    def check_health(self) -> bool:
        """
        Check connectivity and health of the Gemini provider.
        """
        if not self._api_key or self._client is None:
            return False

        try:
            if hasattr(self._client, "models") and hasattr(self._client.models, "get"):
                self._client.models.get(model=self._model_name)
                return True
            return True
        except Exception as e:
            logger.warning("Gemini health check failed: %s", _sanitize_error_message(str(e), self._api_key))
            return False
