"""
Brain Provider Manager & Fallback Adapter for E.V. (Phase 4).

This module implements EVBrainProviderManager, which manages multiple EVBrainProvider
instances with deterministic ordering, bounded fallback policies, error classification,
and telemetry tracking.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from .brain_models import BrainContext, BrainDecision
from .brain_provider import (
    BrainProviderAuthError,
    BrainProviderError,
    BrainProviderMalformedResponseError,
    BrainProviderTimeoutError,
    BrainProviderUnavailableError,
    EVBrainProvider,
)

logger = logging.getLogger("ev.brain.provider_manager")


class EVBrainProviderManager:
    """
    Deterministic manager and fallback adapter for multiple EVBrainProviders.

    Maintains a strict, prioritized list of providers (e.g. Primary -> Secondary -> Tertiary)
    and handles fallback execution when retryable or configured failures occur.
    """

    def __init__(
        self,
        providers: Sequence[EVBrainProvider],
        fallback_on_auth_error: bool = True,
        fallback_on_malformed_response: bool = True,
    ) -> None:
        """
        Initialize the provider manager.

        Args:
            providers: Non-empty sequence of EVBrainProvider instances in fallback order.
            fallback_on_auth_error: If True, allow fallback when a provider has an auth/config failure.
            fallback_on_malformed_response: If True, allow fallback when a provider returns malformed output.

        Raises:
            ValueError: If providers list is empty or contains non-EVBrainProvider objects.
        """
        if not providers:
            raise ValueError("EVBrainProviderManager requires at least one configured EVBrainProvider")

        for idx, p in enumerate(providers):
            if not isinstance(p, EVBrainProvider):
                raise TypeError(
                    f"Provider at index {idx} ({type(p).__name__}) must implement EVBrainProvider"
                )

        self._providers: List[EVBrainProvider] = list(providers)
        self._fallback_on_auth_error = fallback_on_auth_error
        self._fallback_on_malformed_response = fallback_on_malformed_response
        self._last_telemetry: List[Dict[str, Any]] = []

    @property
    def providers(self) -> List[EVBrainProvider]:
        """Return the immutable view of configured providers in fallback priority order."""
        return list(self._providers)

    @property
    def primary_provider(self) -> EVBrainProvider:
        """Return the primary (highest priority) provider."""
        return self._providers[0]

    def get_last_telemetry(self) -> List[Dict[str, Any]]:
        """Return bounded diagnostic telemetry for the most recent generate_decision call."""
        return list(self._last_telemetry)

    def check_health(self) -> bool:
        """
        Check aggregate health of configured providers.

        Returns:
            True if at least one configured provider reports healthy, False otherwise.
        """
        for provider in self._providers:
            try:
                if provider.check_health():
                    return True
            except Exception as e:
                logger.warning(
                    "Health check failed for provider %s: %s",
                    provider.provider_name,
                    str(e),
                )
        return False

    def is_retryable_error(self, exc: Exception) -> bool:
        """
        Classify whether an exception allows fallback to the next configured provider.
        """
        if isinstance(exc, (BrainProviderTimeoutError, BrainProviderUnavailableError)):
            return True
        if isinstance(exc, BrainProviderAuthError):
            return self._fallback_on_auth_error
        if isinstance(exc, BrainProviderMalformedResponseError):
            return self._fallback_on_malformed_response
        if isinstance(exc, BrainProviderError):
            return True
        return False

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        """
        Generate a BrainDecision with deterministic fallback across configured providers.

        Each provider is attempted at most once per request.

        Args:
            prompt: User input string.
            context: Bounded BrainContext instance.
            timeout_seconds: Per-provider timeout in seconds.

        Returns:
            Validated BrainDecision object.

        Raises:
            BrainProviderError: If all providers fail or if a non-retryable error occurs.
            ValueError / TypeError: On input validation failure.
        """
        # Validate inputs common to all providers
        EVBrainProvider._validate_inputs(prompt, context, timeout_seconds)

        self._last_telemetry = []
        failure_summaries: List[str] = []

        for idx, provider in enumerate(self._providers):
            p_name = provider.provider_name
            m_name = provider.model_name
            logger.info("Attempting Brain provider [%d/%d]: %s (%s)", idx + 1, len(self._providers), p_name, m_name)

            try:
                decision = provider.generate_decision(
                    prompt=prompt,
                    context=context,
                    timeout_seconds=timeout_seconds,
                )

                if not isinstance(decision, BrainDecision):
                    raise BrainProviderMalformedResponseError(
                        f"Provider {p_name} returned non-BrainDecision type: {type(decision)}",
                        provider_name=p_name,
                    )

                # Record success telemetry
                self._last_telemetry.append({
                    "provider": p_name,
                    "model": m_name,
                    "status": "success",
                    "decision_type": decision.decision_type.value,
                })

                return decision

            except Exception as exc:
                exc_type = type(exc).__name__
                exc_msg = getattr(exc, "message", str(exc))
                # Sanitize message to prevent any potential secret leaks
                sanitized_msg = str(exc_msg)[:200]

                self._last_telemetry.append({
                    "provider": p_name,
                    "model": m_name,
                    "status": "failed",
                    "error_type": exc_type,
                    "error": sanitized_msg,
                })

                failure_summaries.append(f"{p_name} ({m_name}): [{exc_type}] {sanitized_msg}")
                logger.warning(
                    "Provider %s (%s) failed with %s: %s",
                    p_name,
                    m_name,
                    exc_type,
                    sanitized_msg,
                )

                # Check if this error allows fallback to the next provider
                if not self.is_retryable_error(exc):
                    # Fail-closed immediately if policy forbids fallback on this error
                    if isinstance(exc, BrainProviderError):
                        raise exc
                    raise BrainProviderError(
                        f"Non-retryable provider failure on {p_name}: {sanitized_msg}",
                        provider_name=p_name,
                    ) from exc

                # If this was the last provider, we break out
                if idx == len(self._providers) - 1:
                    break

        # All providers exhausted and failed
        summary_text = " | ".join(failure_summaries)
        raise BrainProviderError(
            f"All configured Brain providers failed ({len(self._providers)} attempted): {summary_text}",
            provider_name="manager",
        )
