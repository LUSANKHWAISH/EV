"""
Deterministic Plan Validator & Dependency Graph Engine for E.V. (Task 015).

This module implements fail-closed validation, topological dependency ordering,
DFS cycle detection, parameter schema enforcement, and security anti-bypass rules.

Security & Architectural Invariants:
1. FAIL-CLOSED: Malformed, cyclical, unresolvable, or policy-violating plans are REJECTED.
2. Canonical Authority: Untrusted metadata (from Brain, Voice, or user prompts) cannot
   override EVRiskEngine, downgrade risk levels, or bypass approval/transaction boundaries.
3. Deterministic Ordering: Topological sort produces a stable, 100% deterministic
   sequential execution sequence.
4. ZERO Execution Authority: This validator only inspects and normalizes plans. It never
   invokes execution, PowerShell, subprocesses, or OS mutations.
"""
from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from core.models import (
    ActionCategory,
    AgentAction,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskLevel,
    VerificationType,
)
from core.plan import Plan, PlanStatus, PlanStep, StepStatus
from core.risk import EVRiskEngine
from core.risk_intelligence import map_action_to_category
from core.transaction import ActionReversibility

logger = logging.getLogger("ev.plan_validator")

# Configurable bounds to prevent resource exhaustion from untrusted inputs
MAX_PLAN_STEPS = 25
MAX_DEPENDENCIES_PER_STEP = 10

# Read-only observation actions
READ_ONLY_ACTIONS: Set[AgentAction] = {
    AgentAction.FIND_PROCESS,
    AgentAction.FIND_TCP_PORT,
    AgentAction.GET_FILE_INFO,
    AgentAction.LIST_DIRECTORY,
    AgentAction.READ_TEXT_FILE,
    AgentAction.FIND_FILES,
    AgentAction.SEARCH_TEXT,
    AgentAction.FIND_SERVICE,
}

# Intrinsically non-compensable actions
NON_COMPENSABLE_ACTIONS: Set[AgentAction] = {
    AgentAction.STOP_PROCESS,
    AgentAction.RESTART_SERVICE,
    AgentAction.FLUSH_DNS,
}


@dataclass
class PlanValidationResult:
    """
    Structured outcome of deterministic plan validation.
    """
    is_valid: bool
    status: PlanStatus
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    topological_order: List[str] = field(default_factory=list)
    aggregate_risk: RiskLevel = RiskLevel.NONE
    approval_required: bool = False
    transaction_required: bool = True
    validated_plan: Optional[Plan] = None

    def summary(self) -> str:
        """Produce a human-readable summary of validation outcome."""
        if self.is_valid:
            return (
                f"VALIDATED: {len(self.topological_order)} steps, order={self.topological_order}, "
                f"risk={self.aggregate_risk.value}, approval_required={self.approval_required}"
            )
        return f"REJECTED ({len(self.errors)} error(s)): {'; '.join(self.errors)}"


class PlanValidator:
    """
    Deterministic fail-closed plan validator and dependency graph analyzer.
    """

    def __init__(self, risk_engine: Optional[EVRiskEngine] = None) -> None:
        self.risk_engine: EVRiskEngine = risk_engine or EVRiskEngine()

    def validate(self, plan: Any) -> PlanValidationResult:
        """
        Validate a proposed Plan against structural, dependency, parameter,
        and security invariants.

        Args:
            plan: Proposed Plan instance to validate.

        Returns:
            PlanValidationResult with validation status, errors, topological order,
            and normalized risk/approval requirements.
        """
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Type and basic structural checks
        if plan is None or not isinstance(plan, Plan):
            return PlanValidationResult(
                is_valid=False,
                status=PlanStatus.REJECTED,
                errors=["Invalid plan object: must be an instance of Plan"],
            )

        if not plan.plan_id or not isinstance(plan.plan_id, str) or not plan.plan_id.strip():
            errors.append("Plan plan_id must be a non-empty string")

        if not plan.goal or not isinstance(plan.goal, str) or not plan.goal.strip():
            errors.append("Plan goal must be a non-empty string")

        if not plan.steps or not isinstance(plan.steps, list):
            errors.append("Plan steps must be a non-empty list of PlanStep objects")
            return PlanValidationResult(is_valid=False, status=PlanStatus.REJECTED, errors=errors)

        if len(plan.steps) > MAX_PLAN_STEPS:
            errors.append(f"Plan exceeds maximum allowed steps limit ({len(plan.steps)} > {MAX_PLAN_STEPS})")
            return PlanValidationResult(is_valid=False, status=PlanStatus.REJECTED, errors=errors)

        # 2. Security Anti-Bypass Inspection of Plan Metadata
        meta = plan.metadata or {}
        if meta.get("bypass_approval") or meta.get("is_approved") or meta.get("pre_approved"):
            errors.append("Security violation: plan metadata contains unauthorized approval bypass declaration")

        if meta.get("bypass_risk") or meta.get("god_mode") or meta.get("elevate_authority"):
            errors.append("Security violation: plan metadata contains unauthorized authority escalation declaration")

        if meta.get("bypass_transaction") or meta.get("disable_transaction"):
            errors.append("Security violation: plan metadata contains unauthorized transaction bypass declaration")

        # 3. Step ID Uniqueness & Step Integrity Checks
        step_ids: Set[str] = set()
        step_map: Dict[str, PlanStep] = {}

        for idx, step in enumerate(plan.steps):
            if not isinstance(step, PlanStep):
                errors.append(f"Step at index {idx} is not a valid PlanStep instance")
                continue

            sid = step.step_id
            if not sid or not isinstance(sid, str) or not sid.strip():
                errors.append(f"Step at index {idx} has missing or empty step_id")
                continue

            sid = sid.strip()
            if sid in step_ids:
                errors.append(f"Duplicate step_id '{sid}' detected at index {idx}")
            step_ids.add(sid)
            step_map[sid] = step

            # Step Action Validity
            if not isinstance(step.action, AgentAction):
                errors.append(f"Step '{sid}' has invalid action: '{step.action}'")

            # Step Parameter Checks
            param_errs = self._validate_step_parameters(step)
            errors.extend(param_errs)

            # Verification Compatibility
            if step.verification_type is not None:
                v_errs = self._validate_verification_compatibility(step)
                errors.extend(v_errs)

            # Compensation Invariant Checks
            if step.action in NON_COMPENSABLE_ACTIONS:
                if step.is_compensable:
                    warnings.append(
                        f"Step '{sid}' action '{step.action.value}' is intrinsically non-compensable; "
                        f"forcing is_compensable=False"
                    )
                    step.is_compensable = False
                    step.reversibility = ActionReversibility.NON_REVERSIBLE

            # Anti-Bypass in step metadata
            s_meta = step.metadata or {}
            if s_meta.get("bypass_approval") or s_meta.get("pre_approved") or s_meta.get("god_mode"):
                errors.append(f"Security violation: step '{sid}' metadata contains unauthorized bypass declaration")

        # If step integrity errors exist, fail early
        if errors:
            return PlanValidationResult(is_valid=False, status=PlanStatus.REJECTED, errors=errors, warnings=warnings)

        # 4. Dependency Graph & Cycle Detection
        dep_errors, topo_order = self._resolve_dependency_graph(plan.steps, step_ids)
        errors.extend(dep_errors)

        if errors:
            return PlanValidationResult(is_valid=False, status=PlanStatus.REJECTED, errors=errors, warnings=warnings)

        # 5. Authoritative Risk Assessment & Risk Propagation
        aggregate_risk = RiskLevel.NONE
        approval_required = False
        has_mutating_step = False

        risk_rank = {
            RiskLevel.NONE: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }

        for sid in topo_order:
            step = step_map[sid]
            is_mutation = step.action not in READ_ONLY_ACTIONS
            if is_mutation:
                has_mutating_step = True

            cat = map_action_to_category(step.action, step.parameters)
            req = RiskAssessmentRequest(
                action_category=cat,
                target=str(step.parameters.get("path") or step.parameters.get("name") or step.parameters.get("service_name") or ""),
                description=step.description or f"Step {sid}: {step.action.value}",
                has_backup=False,
                reversible=step.is_compensable,
                requires_elevation=False,
                affects_system=False,
                affects_security=False,
                user_approved=False,
            )
            res = self.risk_engine.assess(req)

            # Store computed risk on step
            step.risk_level = res.risk_level

            # Propagate aggregate risk: MAX(step risks)
            if risk_rank.get(res.risk_level, 0) > risk_rank.get(aggregate_risk, 0):
                aggregate_risk = res.risk_level

            # If any step requires approval, plan requires approval
            if res.decision == PermissionDecision.REQUIRE_APPROVAL:
                approval_required = True

            # If any step is denied by policy, the entire plan is rejected fail-closed
            if res.decision == PermissionDecision.DENY:
                errors.append(
                    f"Security policy denial on step '{sid}' ({step.action.value}): {res.reason}"
                )

        # Mutating multi-step plans must not disable transaction boundary
        if has_mutating_step and plan.transaction_required is False:
            errors.append("Security violation: mutating plan cannot disable transaction handling (transaction_required cannot be False)")
        transaction_required = True
        if not has_mutating_step and not plan.transaction_required:
            transaction_required = False

        if errors:
            return PlanValidationResult(
                is_valid=False,
                status=PlanStatus.REJECTED,
                errors=errors,
                warnings=warnings,
                aggregate_risk=aggregate_risk,
                approval_required=approval_required,
            )

        # 6. Normalize and Finalize Validated Plan
        plan.status = PlanStatus.VALIDATED
        plan.risk_level = aggregate_risk
        plan.approval_required = approval_required
        plan.transaction_required = transaction_required
        plan.verification_required = any(s.verification_type is not None for s in plan.steps)

        logger.info(
            "Plan '%s' validated successfully: %d steps, risk=%s, approval=%s",
            plan.plan_id,
            len(topo_order),
            aggregate_risk.value,
            approval_required,
        )

        return PlanValidationResult(
            is_valid=True,
            status=PlanStatus.VALIDATED,
            errors=[],
            warnings=warnings,
            topological_order=topo_order,
            aggregate_risk=aggregate_risk,
            approval_required=approval_required,
            transaction_required=transaction_required,
            validated_plan=plan,
        )

    # -------------------------------------------------------------------------
    # Dependency Graph & Topological Sort
    # -------------------------------------------------------------------------

    def _resolve_dependency_graph(
        self, steps: List[PlanStep], valid_step_ids: Set[str]
    ) -> Tuple[List[str], List[str]]:
        """
        Validate dependencies and compute deterministic topological execution ordering.
        Detects missing dependencies, self-dependencies, and circular dependency cycles.
        """
        errors: List[str] = []
        adj: Dict[str, List[str]] = {s.step_id: [] for s in steps}
        in_degree: Dict[str, int] = {s.step_id: 0 for s in steps}

        # Build adjacency graph
        for step in steps:
            sid = step.step_id
            for dep in step.dependencies:
                dep_clean = str(dep).strip()
                if dep_clean == sid:
                    errors.append(f"Self-dependency detected: step '{sid}' depends on itself")
                    continue
                if dep_clean not in valid_step_ids:
                    errors.append(f"Missing dependency: step '{sid}' depends on nonexistent step '{dep_clean}'")
                    continue

                # dep -> sid (dep must execute before sid)
                adj[dep_clean].append(sid)
                in_degree[sid] += 1

        if errors:
            return errors, []

        # Kahn's Algorithm for Topological Sort with deterministic tie-breaking
        # Stable queue sorted by original step index for 100% determinism
        step_original_index = {s.step_id: idx for idx, s in enumerate(steps)}
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        queue.sort(key=lambda s: step_original_index[s])

        topo_order: List[str] = []
        while queue:
            curr = queue.pop(0)
            topo_order.append(curr)

            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort(key=lambda s: step_original_index[s])

        # If not all steps are in topological order, a cycle exists
        if len(topo_order) != len(steps):
            cycle_path = self._find_cycle_path(steps, adj)
            errors.append(f"Dependency cycle detected in plan: {cycle_path}")
            return errors, []

        return [], topo_order

    def _find_cycle_path(self, steps: List[PlanStep], adj: Dict[str, List[str]]) -> str:
        """Find and format a readable cycle path using DFS for clear diagnostic error reporting."""
        visited: Dict[str, int] = {s.step_id: 0 for s in steps}  # 0=unvisited, 1=visiting, 2=visited
        parent: Dict[str, Optional[str]] = {s.step_id: None for s in steps}

        cycle: List[str] = []

        def dfs(node: str) -> bool:
            visited[node] = 1
            for neighbor in adj.get(node, []):
                if visited[neighbor] == 1:
                    # Cycle found!
                    cycle.append(neighbor)
                    curr = node
                    while curr and curr != neighbor:
                        cycle.append(curr)
                        curr = parent.get(curr)
                    cycle.append(neighbor)
                    cycle.reverse()
                    return True
                elif visited[neighbor] == 0:
                    parent[neighbor] = node
                    if dfs(neighbor):
                        return True
            visited[node] = 2
            return False

        for step in steps:
            if visited[step.step_id] == 0:
                if dfs(step.step_id):
                    break

        if cycle:
            return " -> ".join(cycle)
        return "Cycle detected among dependent steps"

    # -------------------------------------------------------------------------
    # Parameter & Verification Validation
    # -------------------------------------------------------------------------

    def _validate_step_parameters(self, step: PlanStep) -> List[str]:
        """Verify that step parameters conform to required schema per action."""
        errs: List[str] = []
        params = step.parameters
        sid = step.step_id
        action = step.action

        if not isinstance(params, dict):
            return [f"Step '{sid}' parameters must be a dictionary, got {type(params).__name__}"]

        # Schema rules by action
        if action in (AgentAction.WRITE_FILE, AgentAction.READ_TEXT_FILE, AgentAction.DELETE_FILE, AgentAction.GET_FILE_INFO):
            path = params.get("path")
            if not path or not isinstance(path, str) or not path.strip():
                errs.append(f"Step '{sid}' ({action.value}) requires non-empty string parameter 'path'")

        if action == AgentAction.WRITE_FILE:
            if "content" not in params:
                errs.append(f"Step '{sid}' (WRITE_FILE) requires parameter 'content'")

        if action == AgentAction.STOP_PROCESS:
            pid = params.get("pid")
            pname = params.get("process_name") or params.get("name")
            if pid is None and not pname:
                errs.append(f"Step '{sid}' (STOP_PROCESS) requires either 'pid' or 'process_name'")
            if pid is not None and (not isinstance(pid, int) or pid <= 0):
                errs.append(f"Step '{sid}' (STOP_PROCESS) 'pid' must be a positive integer, got '{pid}'")

        if action in (AgentAction.FIND_SERVICE, AgentAction.RESTART_SERVICE):
            sname = params.get("service_name") or params.get("name")
            if not sname or not isinstance(sname, str) or not sname.strip():
                errs.append(f"Step '{sid}' ({action.value}) requires non-empty string parameter 'service_name'")

        if action == AgentAction.FIND_TCP_PORT:
            port = params.get("port")
            if port is None or not isinstance(port, int) or not (1 <= port <= 65535):
                errs.append(f"Step '{sid}' (FIND_TCP_PORT) requires integer parameter 'port' between 1 and 65535")

        return errs

    def _validate_verification_compatibility(self, step: PlanStep) -> List[str]:
        """Verify that verification_type is logically compatible with the action."""
        errs: List[str] = []
        v_type = step.verification_type
        action = step.action
        sid = step.step_id

        if not isinstance(v_type, VerificationType):
            return [f"Step '{sid}' has invalid verification_type: '{v_type}'"]

        # Compatibility matrix
        file_verifications = {
            VerificationType.FILE_EXISTS,
            VerificationType.FILE_NOT_EXISTS,
            VerificationType.DIRECTORY_EXISTS,
            VerificationType.TEXT_CONTAINS,
            VerificationType.TEXT_NOT_CONTAINS,
        }
        process_verifications = {
            VerificationType.PROCESS_EXISTS,
            VerificationType.PROCESS_NOT_EXISTS,
        }
        port_verifications = {
            VerificationType.TCP_PORT_EXISTS,
            VerificationType.TCP_PORT_NOT_EXISTS,
        }
        service_verifications = {
            VerificationType.SERVICE_RUNNING,
            VerificationType.SERVICE_STOPPED,
        }

        if action in (AgentAction.WRITE_FILE, AgentAction.DELETE_FILE, AgentAction.GET_FILE_INFO, AgentAction.READ_TEXT_FILE):
            if v_type not in file_verifications and v_type not in (VerificationType.RESULT_NOT_EMPTY, VerificationType.RESULT_EMPTY):
                errs.append(f"Step '{sid}': verification '{v_type.value}' is incompatible with file action '{action.value}'")

        elif action == AgentAction.STOP_PROCESS:
            if v_type not in process_verifications and v_type not in (VerificationType.RESULT_NOT_EMPTY, VerificationType.RESULT_EMPTY):
                errs.append(f"Step '{sid}': verification '{v_type.value}' is incompatible with process action '{action.value}'")

        elif action in (AgentAction.FIND_SERVICE, AgentAction.RESTART_SERVICE):
            if v_type not in service_verifications and v_type not in (VerificationType.RESULT_NOT_EMPTY, VerificationType.RESULT_EMPTY):
                errs.append(f"Step '{sid}': verification '{v_type.value}' is incompatible with service action '{action.value}'")

        elif action == AgentAction.FIND_TCP_PORT:
            if v_type not in port_verifications and v_type not in (VerificationType.RESULT_NOT_EMPTY, VerificationType.RESULT_EMPTY):
                errs.append(f"Step '{sid}': verification '{v_type.value}' is incompatible with port action '{action.value}'")

        return errs
