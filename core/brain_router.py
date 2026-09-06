"""
Brain Intent Engine & Command Router for E.V. (Phase 4 Task 010).

This module implements deterministic intent routing between:
1. Fast-path CLI command resolution via CommandResolver.
2. Natural-language Brain path via BrainContextAssembler -> EVBrainProviderManager ->
   BrainProposalValidator -> BrainTaskConverter.

Security Invariant:
  LLM output is an untrusted proposal. The router enforces the full validation
  and conversion gates without executing any tasks or bypassing safety boundaries.
"""
from __future__ import annotations

from enum import Enum
import logging
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from pydantic import BaseModel, ConfigDict, Field

from .brain_context import BrainContextAssembler
from .brain_converter import BrainConversionError, BrainTaskConverter
from .brain_models import BrainContext, BrainDecision, BrainDecisionType
from .brain_provider import BrainProviderError
from .brain_provider_manager import EVBrainProviderManager
from .brain_validator import (
    BrainProposalValidator,
    BrainValidationResult,
    BrainValidationStatus,
)
from .models import AgentAction, AgentTask, EVState, TaskHistoryRecord
from .resolver import CommandResolver

logger = logging.getLogger("ev.brain.router")


class RouteType(str, Enum):
    """Enumeration of possible routing outcomes."""
    FAST_PATH = "FAST_PATH"
    BRAIN_PATH = "BRAIN_PATH"
    NO_ACTION = "NO_ACTION"
    FAILURE = "FAILURE"


class RoutingResult(BaseModel):
    """
    Structured outcome of the routing process.
    Provides deterministic task lists or non-executable messages without authorizing execution.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    route_type: RouteType
    tasks: List[AgentTask] = Field(default_factory=list)
    decision: Optional[BrainDecision] = None
    validation_result: Optional[BrainValidationResult] = None
    message: Optional[str] = None
    error: Optional[str] = None
    success: bool = True


class BrainRouter:
    """
    Deterministic intent router coordinating fast-path command resolution and Brain planning.

    Completely side-effect free, read-only, and decoupled from runtime execution.
    """

    def __init__(
        self,
        provider_manager: Optional[EVBrainProviderManager] = None,
        context_assembler: Optional[BrainContextAssembler] = None,
        validator: Optional[BrainProposalValidator] = None,
        converter: Optional[BrainTaskConverter] = None,
        resolver: Optional[CommandResolver] = None,
    ) -> None:
        """
        Initialize the router with injected components or safe defaults.
        """
        self._provider_manager = provider_manager
        self._context_assembler = context_assembler or BrainContextAssembler()
        self._validator = validator or BrainProposalValidator()
        self._converter = converter or BrainTaskConverter()
        self._resolver = resolver or CommandResolver()

    @property
    def provider_manager(self) -> Optional[EVBrainProviderManager]:
        """Return the configured EVBrainProviderManager, if any."""
        return self._provider_manager

    def route(
        self,
        user_input: str,
        current_state: EVState = EVState.IDLE,
        platform: str = "windows",
        available_actions: Optional[List[AgentAction]] = None,
        recent_tasks: Optional[List[Union[TaskHistoryRecord, Dict[str, Any]]]] = None,
        verification_context: Optional[Dict[str, Any]] = None,
        timeout_seconds: float = 15.0,
    ) -> RoutingResult:
        """
        Deterministically route user input to either fast-path CLI resolution or Brain planning.

        Args:
            user_input: Raw input string from the user.
            current_state: Current EVState of the system.
            platform: Platform name string (e.g. 'windows').
            available_actions: Optional subset of AgentAction enums.
            recent_tasks: Optional list of recent task history records.
            verification_context: Optional active verification metadata.
            timeout_seconds: Timeout for provider generation in seconds.

        Returns:
            RoutingResult indicating route type, generated tasks, messages, and diagnostics.
        """
        # 1. Input validation
        if not isinstance(user_input, str) or not user_input.strip():
            return RoutingResult(
                route_type=RouteType.FAILURE,
                error="User input must be a non-empty string",
                success=False,
            )

        cleaned_input = user_input.strip()

        # 2. Fast-path resolution attempt
        try:
            fast_task = self._resolver.resolve(cleaned_input)
            return RoutingResult(
                route_type=RouteType.FAST_PATH,
                tasks=[fast_task],
                message=f"Resolved via fast path: {fast_task.action.value}",
                success=True,
            )
        except ValueError:
            # Unrecognized by fast-path grammar -> fallback to Brain path
            logger.debug("Fast-path resolution missed for input: '%s'; routing to Brain", cleaned_input)

        # 3. Brain-path execution
        if self._provider_manager is None:
            return RoutingResult(
                route_type=RouteType.FAILURE,
                error="No Brain provider manager configured to handle natural language request",
                success=False,
            )

        # 3a. Bounded context assembly
        try:
            context = self._context_assembler.assemble_context(
                user_input=cleaned_input,
                current_state=current_state,
                platform=platform,
                available_actions=available_actions,
                recent_tasks=recent_tasks,
                verification_context=verification_context,
            )
        except Exception as exc:
            logger.warning("Context assembly failed during routing: %s", exc)
            return RoutingResult(
                route_type=RouteType.FAILURE,
                error=f"Context assembly failed: {str(exc)[:200]}",
                success=False,
            )

        # 3b. Provider decision generation (provider manager handles ordered fallback)
        try:
            decision = self._provider_manager.generate_decision(
                prompt=cleaned_input,
                context=context,
                timeout_seconds=timeout_seconds,
            )
        except BrainProviderError as exc:
            logger.warning("Brain provider error during routing: %s", exc)
            return RoutingResult(
                route_type=RouteType.FAILURE,
                error=f"Brain provider error: {str(exc)[:200]}",
                success=False,
            )
        except Exception as exc:
            logger.exception("Unexpected provider failure during routing: %s", exc)
            return RoutingResult(
                route_type=RouteType.FAILURE,
                error=f"Unexpected provider error: {type(exc).__name__}: {str(exc)[:200]}",
                success=False,
            )

        # 3c. Brain proposal validation gate
        validation_result = self._validator.validate(decision)
        if not validation_result.valid:
            error_details = "; ".join(validation_result.errors) if validation_result.errors else "Proposal validation failed"
            return RoutingResult(
                route_type=RouteType.FAILURE,
                decision=decision,
                validation_result=validation_result,
                error=f"Brain proposal validation failed: {error_details}",
                success=False,
            )

        # 3d. Non-executable decision types handling
        if decision.decision_type in (
            BrainDecisionType.REFUSAL,
            BrainDecisionType.REQUEST_CLARIFICATION,
            BrainDecisionType.EXPLANATION_ONLY,
        ):
            if decision.decision_type == BrainDecisionType.REQUEST_CLARIFICATION:
                msg = decision.clarification_prompt or decision.user_message
            else:
                msg = decision.user_message

            return RoutingResult(
                route_type=RouteType.NO_ACTION,
                tasks=[],
                decision=decision,
                validation_result=validation_result,
                message=msg,
                success=True,
            )

        # 3e. Task conversion gate for executable decisions
        try:
            tasks = self._converter.convert_decision(
                decision=decision,
                validation_result=validation_result,
            )
            return RoutingResult(
                route_type=RouteType.BRAIN_PATH,
                tasks=tasks,
                decision=decision,
                validation_result=validation_result,
                message=decision.user_message,
                success=True,
            )
        except BrainConversionError as exc:
            logger.warning("Brain task conversion failed during routing: %s", exc)
            return RoutingResult(
                route_type=RouteType.FAILURE,
                decision=decision,
                validation_result=validation_result,
                error=f"Brain task conversion failed: {str(exc)[:200]}",
                success=False,
            )
        except Exception as exc:
            logger.exception("Unexpected conversion error during routing: %s", exc)
            return RoutingResult(
                route_type=RouteType.FAILURE,
                decision=decision,
                validation_result=validation_result,
                error=f"Unexpected conversion error: {type(exc).__name__}: {str(exc)[:200]}",
                success=False,
            )
