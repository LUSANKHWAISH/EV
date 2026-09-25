"""
Brain Decision Models & Action Schemas for E.V. (Phase 4).

This module defines typed data contracts for Brain decisions, action proposals,
and bounded context. It provides model-level structural validation to ensure that
untrusted LLM output fails closed before reaching any deterministic validation
or execution layers.
"""
from __future__ import annotations

import math
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import AgentAction, EVState, VerificationType

# Bounded constraints for safety against untrusted LLM outputs
MAX_PROPOSED_ACTIONS = 5
MAX_STRING_LENGTH = 4000
MAX_SHORT_STRING_LENGTH = 500
MAX_PARAMETERS_PER_ACTION = 20
MAX_CONTEXT_TASKS = 10


class BrainDecisionType(str, Enum):
    """
    Strongly-typed enum of all possible Brain decision outcomes.
    Prevents free-form strings and ambiguous fallback decisions.
    """
    EXECUTE_ACTION = "EXECUTE_ACTION"
    REQUEST_VERIFICATION = "REQUEST_VERIFICATION"
    REQUEST_CLARIFICATION = "REQUEST_CLARIFICATION"
    REFUSAL = "REFUSAL"
    EXPLANATION_ONLY = "EXPLANATION_ONLY"


class BrainActionProposal(BaseModel):
    """
    A single proposed action from the Brain.

    The action MUST be a member of the existing AgentAction enum.
    The verification_type (if present) MUST be a member of VerificationType.
    Extra fields are strictly forbidden to prevent hallucinated keys.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: AgentAction
    parameters: Dict[str, Any] = Field(default_factory=dict)
    verification_type: Optional[VerificationType] = None
    description: Optional[str] = Field(default=None, max_length=MAX_SHORT_STRING_LENGTH)

    @field_validator("parameters")
    @classmethod
    def validate_parameters_bounds(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if len(v) > MAX_PARAMETERS_PER_ACTION:
            raise ValueError(f"Parameters dictionary exceeds maximum allowed size of {MAX_PARAMETERS_PER_ACTION}")
        return v


class BrainDecision(BaseModel):
    """
    Structured outcome of the Brain's reasoning over user input and context.

    This is an untrusted proposal. A valid BrainDecision does NOT grant execution
    permission and must undergo downstream deterministic validation.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], max_length=64)
    decision_type: BrainDecisionType
    user_message: str = Field(..., min_length=1, max_length=MAX_STRING_LENGTH)
    decision_summary: Optional[str] = Field(default=None, max_length=MAX_STRING_LENGTH)
    proposed_actions: List[BrainActionProposal] = Field(default_factory=list, max_length=MAX_PROPOSED_ACTIONS)
    clarification_prompt: Optional[str] = Field(default=None, max_length=MAX_STRING_LENGTH)
    confidence: Optional[float] = Field(default=None)
    provider_name: Optional[str] = Field(default=None, max_length=100)
    model_name: Optional[str] = Field(default=None, max_length=100)
    token_usage: Optional[Dict[str, int]] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: Optional[float]) -> Optional[float]:
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("Confidence cannot be NaN or Infinite")
            if v < 0.0 or v > 1.0:
                raise ValueError("Confidence must be between 0.0 and 1.0 inclusive")
        return v

    @model_validator(mode="after")
    def validate_decision_invariants(self) -> BrainDecision:
        """
        Enforce strict structural invariants per decision type.
        """
        dtype = self.decision_type

        if dtype == BrainDecisionType.EXECUTE_ACTION:
            if not self.proposed_actions:
                raise ValueError("EXECUTE_ACTION decision must contain at least one proposed action")
            if self.clarification_prompt:
                raise ValueError("EXECUTE_ACTION decision cannot contain a clarification_prompt")

        elif dtype == BrainDecisionType.REQUEST_VERIFICATION:
            if not self.proposed_actions:
                raise ValueError("REQUEST_VERIFICATION decision must contain at least one proposed action")
            has_verification = any(a.verification_type is not None for a in self.proposed_actions)
            if not has_verification:
                raise ValueError("REQUEST_VERIFICATION decision must have verification_type set on at least one proposed action")
            if self.clarification_prompt:
                raise ValueError("REQUEST_VERIFICATION decision cannot contain a clarification_prompt")

        elif dtype == BrainDecisionType.REQUEST_CLARIFICATION:
            if not self.clarification_prompt or not self.clarification_prompt.strip():
                raise ValueError("REQUEST_CLARIFICATION decision requires a non-empty clarification_prompt")
            if self.proposed_actions:
                raise ValueError("REQUEST_CLARIFICATION decision must not contain executable actions")

        elif dtype == BrainDecisionType.REFUSAL:
            if not self.user_message or not self.user_message.strip():
                raise ValueError("REFUSAL decision requires a non-empty user_message")
            if self.proposed_actions:
                raise ValueError("REFUSAL decision must not contain executable actions")
            if self.clarification_prompt:
                raise ValueError("REFUSAL decision cannot contain a clarification_prompt")

        elif dtype == BrainDecisionType.EXPLANATION_ONLY:
            if not self.user_message or not self.user_message.strip():
                raise ValueError("EXPLANATION_ONLY decision requires a non-empty user_message")
            if self.proposed_actions:
                raise ValueError("EXPLANATION_ONLY decision must not contain executable actions")
            if self.clarification_prompt:
                raise ValueError("EXPLANATION_ONLY decision cannot contain a clarification_prompt")

        return self


class BrainContext(BaseModel):
    """
    Bounded, privacy-safe context payload provided to the Brain.

    Contains only necessary task/environment metadata without raw secrets,
    file dumps, memory dumps, or unbounded historical records.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    user_input: str = Field(..., min_length=1, max_length=MAX_STRING_LENGTH)
    current_state: EVState = Field(default=EVState.IDLE)
    platform: str = Field(default="windows", max_length=50)
    available_actions: List[AgentAction] = Field(default_factory=lambda: list(AgentAction))
    recent_task_summaries: List[Dict[str, Any]] = Field(default_factory=list, max_length=MAX_CONTEXT_TASKS)
    verification_context: Optional[Dict[str, Any]] = None
    active_awareness: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=25)
