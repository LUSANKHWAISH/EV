"""
Brain-to-Task Conversion Engine for E.V. (Phase 4 Task 009).

This module implements deterministic, fail-closed transformation of validated
BrainActionProposal and BrainDecision objects into authoritative AgentTask instances.

Security Invariant:
  BrainDecision -> BrainProposalValidator approval -> BrainTaskConverter -> AgentTask
  The converter requires explicit validation approval and never authorizes execution on its own.
"""
from __future__ import annotations

import copy
import logging
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from .brain_models import (
    MAX_PROPOSED_ACTIONS,
    BrainActionProposal,
    BrainDecision,
    BrainDecisionType,
)
from .brain_validator import BrainValidationResult, BrainValidationStatus
from .models import AgentAction, AgentTask, VerificationType
from .plan import Plan, PlanStatus, PlanStep, StepStatus

logger = logging.getLogger("ev.brain.converter")

# Length bounds for identifiers
MAX_ID_LENGTH = 64
MIN_ID_LENGTH = 1


class BrainConversionError(Exception):
    """Base exception for all Brain-to-task conversion errors."""
    pass


class BrainConversionValidationError(BrainConversionError):
    """Raised when a proposal fails validation, is unapproved, or validation result is mismatched."""
    pass


class BrainConversionInvariantError(BrainConversionError):
    """Raised when structural or identifier invariants are violated during conversion."""
    pass


def _default_id_factory() -> str:
    """Generate a standard 8-character uuid string."""
    return str(uuid.uuid4())[:8]


class BrainTaskConverter:
    """
    Deterministic converter that maps validated Brain proposals into authoritative AgentTask objects.

    Enforces that only proposals explicitly approved by BrainProposalValidator can be converted.
    Completely side-effect free, read-only, and non-authorizing.
    """

    def convert_decision(
        self,
        decision: Any,
        *,
        validation_result: Any,
        id_factory: Optional[Callable[[], str]] = None,
        correlation_id_factory: Optional[Callable[[], str]] = None,
    ) -> List[AgentTask]:
        """
        Convert a validated BrainDecision into a list of authoritative AgentTask objects.

        Args:
            decision: BrainDecision object to convert.
            validation_result: Authoritative BrainValidationResult from BrainProposalValidator.
            id_factory: Optional custom factory for deterministic task IDs in tests.
            correlation_id_factory: Optional custom factory for deterministic correlation IDs in tests.

        Returns:
            List of constructed AgentTask instances (empty for non-executable decision types).

        Raises:
            BrainConversionValidationError: If validation_result is invalid, unapproved, or mismatched.
            BrainConversionInvariantError: If structural or identifier invariants fail.
            BrainConversionError: On other conversion failures.
        """
        # 1. Type validation of inputs
        if decision is None or not isinstance(decision, BrainDecision):
            raise BrainConversionValidationError("Input decision must be a valid BrainDecision instance")

        if validation_result is None or not isinstance(validation_result, BrainValidationResult):
            raise BrainConversionValidationError("Validation result must be a valid BrainValidationResult instance")

        # 2. Check validation approval boundary
        if not validation_result.valid:
            raise BrainConversionValidationError(
                f"Cannot convert unvalidated BrainDecision (status={validation_result.status.value})"
            )

        dtype = decision.decision_type

        # 3. Non-executable decision types must produce ZERO tasks
        if dtype in (
            BrainDecisionType.REFUSAL,
            BrainDecisionType.REQUEST_CLARIFICATION,
            BrainDecisionType.EXPLANATION_ONLY,
        ):
            # Ensure validation result matches non-executable status
            expected_statuses = {
                BrainDecisionType.REFUSAL: BrainValidationStatus.REFUSED,
                BrainDecisionType.REQUEST_CLARIFICATION: BrainValidationStatus.CLARIFICATION_REQUIRED,
                BrainDecisionType.EXPLANATION_ONLY: BrainValidationStatus.EXPLANATION,
            }
            if validation_result.status != expected_statuses[dtype]:
                raise BrainConversionValidationError(
                    f"Validation status mismatch: decision is {dtype.value} but validation status is {validation_result.status.value}"
                )
            return []

        # 4. Executable decision types (EXECUTE_ACTION, REQUEST_VERIFICATION)
        if dtype not in (BrainDecisionType.EXECUTE_ACTION, BrainDecisionType.REQUEST_VERIFICATION):
            raise BrainConversionValidationError(f"Unsupported decision type: {dtype}")

        if validation_result.status != BrainValidationStatus.VALID:
            raise BrainConversionValidationError(
                f"Executable decision requires VALID status, got {validation_result.status.value}"
            )

        accepted_actions = validation_result.accepted_actions
        if not accepted_actions or len(accepted_actions) == 0:
            raise BrainConversionValidationError(f"{dtype.value} validation result contains no accepted actions")

        # 5. Verify validation result correspondence with decision proposals
        if len(accepted_actions) != len(decision.proposed_actions):
            raise BrainConversionValidationError(
                "Validation result accepted actions count does not match decision proposed actions count"
            )

        for idx, (prop, accepted) in enumerate(zip(decision.proposed_actions, accepted_actions)):
            if prop.action != accepted.action:
                raise BrainConversionValidationError(
                    f"Action mismatch at index {idx}: proposed={prop.action}, accepted={accepted.action}"
                )
            if prop.verification_type != accepted.verification_type:
                raise BrainConversionValidationError(
                    f"Verification type mismatch at index {idx}: proposed={prop.verification_type}, accepted={accepted.verification_type}"
                )

        # 6. ID factory setup
        gen_id = id_factory or _default_id_factory

        # 7. Convert each approved proposal to an AgentTask
        tasks: List[AgentTask] = []
        seen_task_ids: Set[str] = set()

        for idx, proposal in enumerate(accepted_actions):
            task = self._convert_single_proposal(
                idx=idx,
                proposal=proposal,
                id_factory=gen_id,
                seen_task_ids=seen_task_ids,
            )
            tasks.append(task)

        return tasks

    def _convert_single_proposal(
        self,
        idx: int,
        proposal: BrainActionProposal,
        id_factory: Callable[[], str],
        seen_task_ids: Set[str],
    ) -> AgentTask:
        """Deterministically convert a single approved BrainActionProposal into an AgentTask."""
        # Validate action enum
        if not isinstance(proposal.action, AgentAction):
            raise BrainConversionInvariantError(f"Proposal [{idx}]: Action is not a valid AgentAction")

        # Validate parameters dictionary
        if not isinstance(proposal.parameters, dict):
            raise BrainConversionInvariantError(f"Proposal [{idx}]: Parameters must be a dictionary")

        # Validate verification type
        if proposal.verification_type is not None and not isinstance(proposal.verification_type, VerificationType):
            raise BrainConversionInvariantError(f"Proposal [{idx}]: Invalid VerificationType")

        # Generate and validate task ID
        try:
            task_id = id_factory()
        except Exception as exc:
            raise BrainConversionInvariantError(f"ID factory failed: {exc}") from exc

        if not isinstance(task_id, str) or not task_id.strip():
            raise BrainConversionInvariantError("Generated task_id must be a non-empty string")

        task_id = task_id.strip()
        if len(task_id) > MAX_ID_LENGTH or len(task_id) < MIN_ID_LENGTH:
            raise BrainConversionInvariantError(
                f"Generated task_id length ({len(task_id)}) exceeds bounds [{MIN_ID_LENGTH}, {MAX_ID_LENGTH}]"
            )

        if task_id in seen_task_ids:
            raise BrainConversionInvariantError(f"Duplicate task_id generated: {task_id}")
        seen_task_ids.add(task_id)

        # Construct AgentTask safely (deep-copy parameters to ensure caller immutability)
        return AgentTask(
            task_id=task_id,
            action=proposal.action,
            parameters=copy.deepcopy(proposal.parameters),
            verification_type=proposal.verification_type,
        )

    def convert_decision_to_plan(
        self,
        decision: Any,
        *,
        validation_result: Any,
        plan_id_factory: Optional[Callable[[], str]] = None,
        goal: Optional[str] = None,
    ) -> Optional[Plan]:
        """
        Convert a validated BrainDecision into an untrusted Plan proposal.
        The Plan must subsequently be validated by PlanValidator before execution.

        Args:
            decision: Validated BrainDecision.
            validation_result: Authoritative BrainValidationResult.
            plan_id_factory: Optional custom factory for plan_id.
            goal: Optional human-readable goal override.

        Returns:
            Constructed Plan instance (or None for non-executable decisions).
        """
        # First convert to tasks to enforce all conversion invariants
        tasks = self.convert_decision(decision, validation_result=validation_result)
        if not tasks:
            return None

        p_id = (plan_id_factory() if plan_id_factory else f"plan-{uuid.uuid4().hex[:10]}")
        plan_goal = goal or decision.decision_summary or decision.user_message

        steps: List[PlanStep] = []
        prev_step_id: Optional[str] = None

        for idx, task in enumerate(tasks):
            step = PlanStep(
                step_id=task.task_id,
                action=task.action,
                parameters=copy.deepcopy(task.parameters),
                dependencies=[prev_step_id] if prev_step_id else [],
                verification_type=task.verification_type,
                description=f"Step {idx + 1}: {task.action.value}",
            )
            steps.append(step)
            prev_step_id = task.task_id

        return Plan(
            plan_id=p_id,
            goal=plan_goal,
            steps=steps,
            status=PlanStatus.CREATED,
            metadata={"decision_id": getattr(decision, "decision_id", None)},
        )

