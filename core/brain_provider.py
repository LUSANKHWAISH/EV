"""
Brain Provider Abstraction & Mock Provider for E.V. (Phase 4).

This module defines the provider-neutral interface EVBrainProvider, the provider
exception hierarchy, and MockBrainProvider for offline deterministic testing.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Tuple

from .brain_models import BrainContext, BrainDecision


class BrainProviderError(Exception):
    """Base exception for all Brain provider failures."""
    def __init__(self, message: str, provider_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.provider_name = provider_name


class BrainProviderTimeoutError(BrainProviderError):
    """Raised when a provider request times out."""
    pass


class BrainProviderUnavailableError(BrainProviderError):
    """Raised when a provider service or endpoint is unavailable or unreachable."""
    pass


class BrainProviderMalformedResponseError(BrainProviderError):
    """Raised when a provider returns unparseable or invalid schema output."""
    pass


class BrainProviderAuthError(BrainProviderError):
    """Raised when provider authentication or API configuration fails."""
    pass


class EVBrainProvider(ABC):
    """
    Abstract interface for all Brain LLM providers.

    Decouples E.V. intelligence orchestration from specific provider APIs
    (Gemini, OpenRouter, Azure, Local, etc.).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique provider name (e.g. 'gemini', 'openrouter', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the active model name (e.g. 'gemini-2.0-flash', 'mock-v1')."""
        pass

    @abstractmethod
    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        """
        Generate a structured BrainDecision from the user prompt and context.

        Args:
            prompt: User natural-language input or query.
            context: Bounded BrainContext.
            timeout_seconds: Timeout limit in seconds (must be positive finite float).

        Returns:
            Validated BrainDecision object.

        Raises:
            BrainProviderTimeoutError: If request exceeds timeout.
            BrainProviderUnavailableError: If provider is unreachable.
            BrainProviderMalformedResponseError: If response is invalid.
            BrainProviderAuthError: If authentication fails.
            BrainProviderError: On any other provider-level failure.
        """
        pass

    @abstractmethod
    def check_health(self) -> bool:
        """
        Check connectivity and health of the provider.

        Returns:
            True if healthy and ready, False otherwise.
        """
        pass

    @staticmethod
    def _validate_inputs(prompt: str, context: BrainContext, timeout_seconds: float) -> None:
        """
        Helper to validate inputs common to all providers.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")
        if not isinstance(context, BrainContext):
            raise TypeError("Context must be a valid BrainContext instance")
        if (
            not isinstance(timeout_seconds, (int, float))
            or math.isnan(timeout_seconds)
            or math.isinf(timeout_seconds)
            or timeout_seconds <= 0.0
        ):
            raise ValueError("timeout_seconds must be a positive finite number")


class MockBrainProvider(EVBrainProvider):
    """
    Deterministic offline mock provider for testing without external APIs or network calls.
    """

    def __init__(
        self,
        decision: Optional[BrainDecision] = None,
        decisions: Optional[List[BrainDecision]] = None,
        decision_factory: Optional[Callable[[str, BrainContext], BrainDecision]] = None,
        healthy: bool = True,
        error_to_raise: Optional[Exception] = None,
        simulate_timeout: bool = False,
        provider_name: str = "mock",
        model_name: str = "mock-brain-v1",
    ) -> None:
        self._default_decision = decision
        self._decisions_queue: List[BrainDecision] = list(decisions) if decisions is not None else []
        self._decision_factory = decision_factory
        self._healthy = healthy
        self._error_to_raise = error_to_raise
        self._simulate_timeout = simulate_timeout
        self._provider_name = provider_name
        self._model_name = model_name
        self.call_count: int = 0
        self.history: List[Tuple[str, BrainContext, float]] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name

    def set_healthy(self, healthy: bool) -> None:
        """Configure mock health status."""
        self._healthy = healthy

    def set_error(self, error: Optional[Exception]) -> None:
        """Configure error to raise on generate_decision."""
        self._error_to_raise = error

    def set_simulate_timeout(self, simulate_timeout: bool) -> None:
        """Configure whether to simulate a timeout."""
        self._simulate_timeout = simulate_timeout

    def check_health(self) -> bool:
        return bool(self._healthy)

    def generate_decision(
        self,
        prompt: str,
        context: BrainContext,
        timeout_seconds: float = 15.0,
    ) -> BrainDecision:
        # Validate inputs first
        self._validate_inputs(prompt, context, timeout_seconds)

        self.call_count += 1
        self.history.append((prompt, context, timeout_seconds))

        if self._simulate_timeout:
            raise BrainProviderTimeoutError(
                f"Mock provider simulated timeout after {timeout_seconds}s",
                provider_name=self._provider_name,
            )

        if self._error_to_raise is not None:
            if isinstance(self._error_to_raise, BrainProviderError):
                raise self._error_to_raise
            raise BrainProviderError(
                str(self._error_to_raise),
                provider_name=self._provider_name,
            ) from self._error_to_raise

        # Check queued responses first
        if self._decisions_queue:
            return self._decisions_queue.pop(0)

        # Check decision factory
        if self._decision_factory is not None:
            res = self._decision_factory(prompt, context)
            if not isinstance(res, BrainDecision):
                raise BrainProviderMalformedResponseError(
                    f"Decision factory returned non-BrainDecision type: {type(res)}",
                    provider_name=self._provider_name,
                )
            return res

        # Check single static decision
        if self._default_decision is not None:
            return self._default_decision

        raise BrainProviderMalformedResponseError(
            "MockBrainProvider has no configured decisions, factory, or error",
            provider_name=self._provider_name,
        )
