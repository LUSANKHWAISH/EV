"""
Brain Proposal Validator & Safety Boundary for E.V. (Phase 4 Task 006).

This module implements deterministic validation of untrusted BrainDecision objects,
acting as a strict gate between provider/LLM output and E.V.'s deterministic
execution and verification systems.
"""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

from .brain_models import (
    MAX_PARAMETERS_PER_ACTION,
    MAX_PROPOSED_ACTIONS,
    BrainActionProposal,
    BrainDecision,
    BrainDecisionType,
)
from .models import AgentAction, VerificationType

logger = logging.getLogger("ev.brain.validator")

# Authoritative parameter allowlists per AgentAction
ALLOWED_PARAMETERS_PER_ACTION: Dict[AgentAction, Set[str]] = {
    AgentAction.FIND_PROCESS: {"name", "verification_type"},
    AgentAction.FIND_TCP_PORT: {"port", "verification_type"},
    AgentAction.GET_FILE_INFO: {"path", "verification_type"},
    AgentAction.LIST_DIRECTORY: {"path", "verification_type"},
    AgentAction.READ_TEXT_FILE: {"path", "max_bytes", "verification_type"},
    AgentAction.FIND_FILES: {"root", "pattern", "max_results", "exclude_dirs", "verification_type"},
    AgentAction.SEARCH_TEXT: {"root_or_file", "text", "max_results", "case_insensitive", "exclude_dirs", "verification_type"},
    AgentAction.FIND_SERVICE: {"name", "verification_type"},
}

# Authoritative verification type compatibility mapping
ACTION_VERIFICATION_COMPATIBILITY: Dict[AgentAction, Set[VerificationType]] = {
    AgentAction.FIND_PROCESS: {
        VerificationType.PROCESS_EXISTS,
        VerificationType.PROCESS_NOT_EXISTS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.FIND_TCP_PORT: {
        VerificationType.TCP_PORT_EXISTS,
        VerificationType.TCP_PORT_NOT_EXISTS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.GET_FILE_INFO: {
        VerificationType.FILE_EXISTS,
        VerificationType.FILE_NOT_EXISTS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.LIST_DIRECTORY: {
        VerificationType.DIRECTORY_EXISTS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.READ_TEXT_FILE: {
        VerificationType.TEXT_CONTAINS,
        VerificationType.TEXT_NOT_CONTAINS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.FIND_FILES: {
        VerificationType.FILE_EXISTS,
        VerificationType.FILE_NOT_EXISTS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.SEARCH_TEXT: {
        VerificationType.TEXT_CONTAINS,
        VerificationType.TEXT_NOT_CONTAINS,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
    AgentAction.FIND_SERVICE: {
        VerificationType.SERVICE_RUNNING,
        VerificationType.SERVICE_STOPPED,
        VerificationType.RESULT_NOT_EMPTY,
        VerificationType.RESULT_EMPTY,
    },
}


class BrainValidationStatus(str, Enum):
    """Status outcomes of deterministic Brain proposal validation."""
    VALID = "VALID"
    INVALID = "INVALID"
    REFUSED = "REFUSED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    EXPLANATION = "EXPLANATION"


class BrainValidationResult(BaseModel):
    """
    Strongly typed result of Brain proposal validation.
    Communicates admissibility, errors, and accepted proposals safely.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    valid: bool
    status: BrainValidationStatus
    errors: List[str] = Field(default_factory=list, max_length=50)
    warnings: List[str] = Field(default_factory=list, max_length=50)
    accepted_actions: List[BrainActionProposal] = Field(default_factory=list, max_length=MAX_PROPOSED_ACTIONS)
    decision_type: Optional[BrainDecisionType] = None
    requires_risk_evaluation: bool = False


class BrainProposalValidator:
    """
    Deterministic gate that evaluates untrusted BrainDecision objects.

    Enforces action whitelisting, parameter allowlists, parameter constraints,
    verification compatibility, and fail-closed multi-action safety.
    """

    def validate(self, decision: Any) -> BrainValidationResult:
        """
        Deterministically validate an untrusted BrainDecision proposal.

        Args:
            decision: BrainDecision object to validate.

        Returns:
            BrainValidationResult indicating admissibility and diagnostics.
        """
        try:
            return self._validate_internal(decision)
        except Exception as exc:
            # Defensive fail-closed catch
            logger.exception("Unexpected exception inside BrainProposalValidator: %s", exc)
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=[f"Validator internal error: {type(exc).__name__}: {str(exc)[:200]}"],
            )

    def _validate_internal(self, decision: Any) -> BrainValidationResult:
        if decision is None or not isinstance(decision, BrainDecision):
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=["Input must be a valid BrainDecision instance"],
            )

        dtype = decision.decision_type

        # 1. Non-executable decision types
        if dtype == BrainDecisionType.REFUSAL:
            if decision.proposed_actions:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["REFUSAL decision must not contain proposed actions"],
                    decision_type=dtype,
                )
            if decision.clarification_prompt:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["REFUSAL decision must not contain clarification prompt"],
                    decision_type=dtype,
                )
            return BrainValidationResult(
                valid=True,
                status=BrainValidationStatus.REFUSED,
                decision_type=dtype,
                accepted_actions=[],
            )

        if dtype == BrainDecisionType.REQUEST_CLARIFICATION:
            if decision.proposed_actions:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["REQUEST_CLARIFICATION must not contain proposed actions"],
                    decision_type=dtype,
                )
            if not decision.clarification_prompt or not decision.clarification_prompt.strip():
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["REQUEST_CLARIFICATION requires non-empty clarification prompt"],
                    decision_type=dtype,
                )
            return BrainValidationResult(
                valid=True,
                status=BrainValidationStatus.CLARIFICATION_REQUIRED,
                decision_type=dtype,
                accepted_actions=[],
            )

        if dtype == BrainDecisionType.EXPLANATION_ONLY:
            if decision.proposed_actions:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["EXPLANATION_ONLY must not contain proposed actions"],
                    decision_type=dtype,
                )
            if decision.clarification_prompt:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["EXPLANATION_ONLY must not contain clarification prompt"],
                    decision_type=dtype,
                )
            return BrainValidationResult(
                valid=True,
                status=BrainValidationStatus.EXPLANATION,
                decision_type=dtype,
                accepted_actions=[],
            )

        # 2. Executable decision types (EXECUTE_ACTION, REQUEST_VERIFICATION)
        if dtype not in (BrainDecisionType.EXECUTE_ACTION, BrainDecisionType.REQUEST_VERIFICATION):
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=[f"Unsupported decision type: {dtype}"],
                decision_type=dtype,
            )

        if decision.clarification_prompt:
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=[f"{dtype.value} must not contain clarification prompt"],
                decision_type=dtype,
            )

        if not decision.proposed_actions or len(decision.proposed_actions) == 0:
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=[f"{dtype.value} requires at least one proposed action"],
                decision_type=dtype,
            )

        if len(decision.proposed_actions) > MAX_PROPOSED_ACTIONS:
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=[f"Proposed actions exceed maximum limit of {MAX_PROPOSED_ACTIONS}"],
                decision_type=dtype,
            )

        # Invariant for REQUEST_VERIFICATION: At least one action must have verification_type
        if dtype == BrainDecisionType.REQUEST_VERIFICATION:
            has_verification = any(p.verification_type is not None for p in decision.proposed_actions)
            if not has_verification:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=["REQUEST_VERIFICATION requires at least one action with a verification_type"],
                    decision_type=dtype,
                )

        # Check for duplicate action proposals to prevent amplification
        seen_proposals = set()
        for idx, prop in enumerate(decision.proposed_actions):
            # Create a hashable representation
            prop_key = (
                prop.action.value,
                tuple(sorted(prop.parameters.items(), key=lambda x: str(x[0]))),
                prop.verification_type.value if prop.verification_type else None,
            )
            if prop_key in seen_proposals:
                return BrainValidationResult(
                    valid=False,
                    status=BrainValidationStatus.INVALID,
                    errors=[f"Duplicate identical action proposal detected at index {idx}"],
                    decision_type=dtype,
                )
            seen_proposals.add(prop_key)

        # Validate each action proposal deterministically
        errors: List[str] = []
        for idx, proposal in enumerate(decision.proposed_actions):
            prop_errors = self._validate_proposal(idx, proposal)
            errors.extend(prop_errors)

        if errors:
            # Fail closed: entire decision is rejected if ANY action is invalid
            return BrainValidationResult(
                valid=False,
                status=BrainValidationStatus.INVALID,
                errors=errors,
                decision_type=dtype,
                accepted_actions=[],
            )

        return BrainValidationResult(
            valid=True,
            status=BrainValidationStatus.VALID,
            errors=[],
            accepted_actions=decision.proposed_actions,
            decision_type=dtype,
            requires_risk_evaluation=True,
        )

    def _validate_proposal(self, idx: int, proposal: BrainActionProposal) -> List[str]:
        """Validate a single BrainActionProposal against whitelists and constraints."""
        errors: List[str] = []

        if not isinstance(proposal.action, AgentAction):
            errors.append(f"Action [{idx}]: Unknown action '{proposal.action}' is not whitelisted")
            return errors

        action = proposal.action
        params = proposal.parameters

        # Check parameter count bound
        if len(params) > MAX_PARAMETERS_PER_ACTION:
            errors.append(f"Action [{idx}] ({action.value}): Parameter count exceeds limit of {MAX_PARAMETERS_PER_ACTION}")

        # Check parameter key allowlist
        allowed_keys = ALLOWED_PARAMETERS_PER_ACTION.get(action, set())
        for param_key in params.keys():
            if param_key not in allowed_keys:
                errors.append(
                    f"Action [{idx}] ({action.value}): Disallowed parameter '{param_key}' is not permitted"
                )

        # Check parameter semantic constraints
        param_error = self._validate_action_parameters(action, params)
        if param_error:
            errors.append(f"Action [{idx}] ({action.value}): {param_error}")

        # Check verification type compatibility if present
        if proposal.verification_type is not None:
            vtype = proposal.verification_type
            if not isinstance(vtype, VerificationType):
                errors.append(f"Action [{idx}] ({action.value}): Unknown verification type '{vtype}'")
            else:
                compatible_vtypes = ACTION_VERIFICATION_COMPATIBILITY.get(action, set())
                if vtype not in compatible_vtypes:
                    errors.append(
                        f"Action [{idx}] ({action.value}): Incompatible verification type '{vtype.value}' for action"
                    )

        return errors

    def _validate_action_parameters(self, action: AgentAction, params: Dict[str, Any]) -> Optional[str]:
        """Validate semantic parameter constraints matching EVAgent requirements."""
        if action == AgentAction.FIND_PROCESS:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "FIND_PROCESS requires non-empty string 'name'"
            if len(name) > 500:
                return "FIND_PROCESS 'name' exceeds maximum length of 500 characters"

        elif action == AgentAction.FIND_SERVICE:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "FIND_SERVICE requires non-empty string 'name'"
            if len(name) > 500:
                return "FIND_SERVICE 'name' exceeds maximum length of 500 characters"

        elif action == AgentAction.FIND_TCP_PORT:
            port = params.get("port")
            if not isinstance(port, int) or isinstance(port, bool):
                return "FIND_TCP_PORT requires integer 'port'"
            if port < 1 or port > 65535:
                return f"FIND_TCP_PORT 'port' must be between 1 and 65535 (got {port})"

        elif action in (AgentAction.GET_FILE_INFO, AgentAction.LIST_DIRECTORY):
            path = params.get("path")
            if not path or not isinstance(path, str) or not path.strip():
                return f"{action.value} requires non-empty string 'path'"
            if len(path) > 1000:
                return f"{action.value} 'path' exceeds maximum length of 1000 characters"

        elif action == AgentAction.READ_TEXT_FILE:
            path = params.get("path")
            if not path or not isinstance(path, str) or not path.strip():
                return "READ_TEXT_FILE requires non-empty string 'path'"
            if len(path) > 1000:
                return "READ_TEXT_FILE 'path' exceeds maximum length of 1000 characters"
            max_bytes = params.get("max_bytes")
            if max_bytes is not None:
                if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes <= 0:
                    return "READ_TEXT_FILE 'max_bytes' must be a positive integer if provided"

        elif action == AgentAction.FIND_FILES:
            root = params.get("root")
            pattern = params.get("pattern")
            if not root or not isinstance(root, str) or not root.strip():
                return "FIND_FILES requires non-empty string 'root'"
            if not pattern or not isinstance(pattern, str) or not pattern.strip():
                return "FIND_FILES requires non-empty string 'pattern'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results <= 0:
                    return "FIND_FILES 'max_results' must be a positive integer if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "FIND_FILES 'exclude_dirs' must be a list of strings if provided"

        elif action == AgentAction.SEARCH_TEXT:
            root_or_file = params.get("root_or_file")
            text = params.get("text")
            if not root_or_file or not isinstance(root_or_file, str) or not root_or_file.strip():
                return "SEARCH_TEXT requires non-empty string 'root_or_file'"
            if not text or not isinstance(text, str) or not text.strip():
                return "SEARCH_TEXT requires non-empty string 'text'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or isinstance(max_results, bool) or max_results <= 0:
                    return "SEARCH_TEXT 'max_results' must be a positive integer if provided"
            case_insensitive = params.get("case_insensitive")
            if case_insensitive is not None and not isinstance(case_insensitive, bool):
                return "SEARCH_TEXT 'case_insensitive' must be boolean if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "SEARCH_TEXT 'exclude_dirs' must be a list of strings if provided"

        return None
