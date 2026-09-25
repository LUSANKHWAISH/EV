"""
Deterministic Plan Representation & State Machine for E.V. (Task 015).

This module defines the structured data models, step specifications, and lifecycle
state machine for multi-step execution plans.

Architectural Invariants:
1. Pure data representation: defines the plan structure, steps, and lifecycle.
2. Independent State Machine: PlanStatus is strictly separate from EVState, VoiceState,
   ExperienceMode, and AutonomyLevel.
3. Untrusted Proposal by Default: Plans may be constructed from Brain, user commands,
   or system suggestions, but are NOT executable until validated by PlanValidator.
4. Zero Execution Authority: This module contains NO direct execution, subprocess,
   or mutation mechanisms.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from core.models import AgentAction, AgentTask, RiskLevel, VerificationType
from core.transaction import ActionReversibility


class PlanStatus(str, Enum):
    """Deterministic lifecycle states for multi-step execution plans."""
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    READY = "READY"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    ROLLING_BACK = "ROLLING_BACK"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class StepStatus(str, Enum):
    """Execution status for individual plan steps."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


@dataclass
class PlanStep:
    """
    Structured specification of a single step within a Plan.
    """
    step_id: str
    action: AgentAction
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    verification_type: Optional[VerificationType] = None
    is_compensable: bool = True
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    risk_level: Optional[RiskLevel] = None
    description: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_agent_task(self) -> AgentTask:
        """Convert this PlanStep into an authoritative AgentTask for execution."""
        return AgentTask(
            task_id=self.step_id,
            action=self.action,
            parameters=copy.deepcopy(self.parameters),
            verification_type=self.verification_type,
        )

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation of the step."""
        return {
            "step_id": self.step_id,
            "action": self.action.value if hasattr(self.action, "value") else str(self.action),
            "parameters": copy.deepcopy(self.parameters),
            "dependencies": list(self.dependencies),
            "verification_type": self.verification_type.value if self.verification_type else None,
            "is_compensable": self.is_compensable,
            "reversibility": self.reversibility.value if hasattr(self.reversibility, "value") else str(self.reversibility),
            "risk_level": self.risk_level.value if self.risk_level else None,
            "description": self.description,
            "status": self.status.value,
            "result": copy.deepcopy(self.result) if self.result is not None else None,
            "error": self.error,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
            "metadata": copy.deepcopy(self.metadata),
        }


@dataclass
class Plan:
    """
    Deterministic representation of a multi-step execution plan.
    """
    plan_id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: PlanStatus = PlanStatus.CREATED
    risk_level: RiskLevel = RiskLevel.NONE
    approval_required: bool = False
    transaction_required: bool = True
    verification_required: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        goal: str,
        steps: Optional[List[PlanStep]] = None,
        plan_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        transaction_required: bool = True,
    ) -> Plan:
        """Factory constructor generating unique plan_id if omitted."""
        return cls(
            plan_id=plan_id or f"plan-{uuid.uuid4().hex[:10]}",
            goal=goal,
            steps=list(steps) if steps else [],
            metadata=dict(metadata) if metadata else {},
            transaction_required=transaction_required,
        )

    def get_step(self, step_id: str) -> Optional[PlanStep]:
        """Retrieve a step by its unique step_id."""
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def to_agent_tasks(self) -> List[AgentTask]:
        """Convert all plan steps to AgentTask instances."""
        return [step.to_agent_task() for step in self.steps]

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation of the complete plan."""
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "risk_level": self.risk_level.value,
            "approval_required": self.approval_required,
            "transaction_required": self.transaction_required,
            "verification_required": self.verification_required,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "metadata": copy.deepcopy(self.metadata),
            "error": self.error,
        }

    def summary(self) -> str:
        """Produce a concise deterministic summary of the plan."""
        step_count = len(self.steps)
        mutations = sum(1 for s in self.steps if s.action not in (
            AgentAction.FIND_PROCESS,
            AgentAction.FIND_TCP_PORT,
            AgentAction.GET_FILE_INFO,
            AgentAction.LIST_DIRECTORY,
            AgentAction.READ_TEXT_FILE,
            AgentAction.FIND_FILES,
            AgentAction.SEARCH_TEXT,
            AgentAction.FIND_SERVICE,
        ))
        return (
            f"Plan '{self.plan_id}' [{self.status.value}]: {self.goal} "
            f"({step_count} step(s), {mutations} mutation(s), risk={self.risk_level.value}, "
            f"approval={self.approval_required})"
        )
