"""
Deterministic Risk Intelligence & Risk Model Hardening Engine for E.V. (Phase 5 Task 009).

This module provides pure deterministic advisory risk intelligence, multi-dimensional
impact classification, reversibility evaluation, privilege scoping, risk factor detection,
compound exposure calculation, and deterministic human-readable explanations.

SAFETY AND ARCHITECTURAL INVARIANTS:
1. STRICTLY ADVISORY: This engine never authorizes, approves, denies, or executes any action.
   EVRiskEngine remains the sole, final authoritative gatekeeper for execution authorization.
2. ZERO SIDE EFFECTS: This module is 100% pure computation. It performs no disk I/O, process
   inspection/control, service manipulation, network operations, PowerShell calls, subprocess
   invocations, or environment modifications.
3. 100% DETERMINISTIC: Identical inputs produce identical outputs with stable factor ordering.
   No timestamps, random seeds, heuristics, or external data are used in classification.
4. FAIL-CLOSED CLASSIFICATION: Malformed or unrecognized tasks default to CRITICAL impact,
   UNKNOWN reversibility, and conservative advisory risk factors.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field

from core.models import (
    ActionCategory,
    AgentAction,
    AgentTask,
    RiskLevel,
)


# =============================================================================
# 1. Deterministic Known System Constants (Static Knowledge)
# =============================================================================

KNOWN_CRITICAL_PROCESSES: Set[str] = {
    "system",
    "idle",
    "smss",
    "smss.exe",
    "csrss",
    "csrss.exe",
    "wininit",
    "wininit.exe",
    "services",
    "services.exe",
    "lsass",
    "lsass.exe",
    "svchost",
    "svchost.exe",
    "explorer",
    "explorer.exe",
    "winlogon",
    "winlogon.exe",
    "dwm",
    "dwm.exe",
    "fontdrvhost",
    "fontdrvhost.exe",
}

KNOWN_CRITICAL_SERVICES: Set[str] = {
    "trustedinstaller",
    "lsass",
    "samss",
    "rpcss",
    "dcomlaunch",
    "cryptsvc",
    "windefend",
    "mpssvc",
    "eventlog",
    "securityhealthservice",
    "gpsvc",
}


# =============================================================================
# 2. Risk Intelligence Taxonomy (Advisory Dimensions)
# =============================================================================

class RiskImpact(str, Enum):
    """Advisory severity of the potential operational impact of an action."""
    READ_ONLY = "READ_ONLY"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReversibilityClass(str, Enum):
    """Advisory classification of an action's reversibility / rollback capacity."""
    FULLY_REVERSIBLE = "FULLY_REVERSIBLE"                     # Automatic pre-execution backup or reverse action
    COMPENSATING_REVERSIBLE = "COMPENSATING_REVERSIBLE"       # Compensating state restore (e.g. stop restarted service)
    IDEMPOTENT = "IDEMPOTENT"                                 # Repeatable without persistent damage (e.g. DNS flush)
    NON_REVERSIBLE = "NON_REVERSIBLE"                         # Cannot be undone (e.g. process kill)
    UNKNOWN = "UNKNOWN"                                       # Reversibility cannot be proven deterministically


class ActionScope(str, Enum):
    """Advisory blast radius / target boundary of an action."""
    SINGLE_FILE = "SINGLE_FILE"
    DIRECTORY = "DIRECTORY"
    SINGLE_PROCESS = "SINGLE_PROCESS"
    SERVICE = "SERVICE"
    NETWORK_INTERFACE = "NETWORK_INTERFACE"
    SYSTEM_WIDE = "SYSTEM_WIDE"
    UNKNOWN = "UNKNOWN"


class PrivilegeScope(str, Enum):
    """Advisory privilege boundary required for safe execution."""
    STANDARD_USER = "STANDARD_USER"
    ADMIN_REQUIRED = "ADMIN_REQUIRED"
    SYSTEM_PROTECTED = "SYSTEM_PROTECTED"
    UNKNOWN = "UNKNOWN"


class RiskFactor(str, Enum):
    """Deterministic risk factors identified from action metadata and parameters."""
    MUTATION = "MUTATION"
    UNBACKED_MUTATION = "UNBACKED_MUTATION"
    NON_REVERSIBLE_CHANGE = "NON_REVERSIBLE_CHANGE"
    ELEVATED_PRIVILEGE = "ELEVATED_PRIVILEGE"
    SYSTEM_CRITICAL_TARGET = "SYSTEM_CRITICAL_TARGET"
    WIDE_BLAST_RADIUS = "WIDE_BLAST_RADIUS"
    COMPOUND_MUTATION_CHAIN = "COMPOUND_MUTATION_CHAIN"


# =============================================================================
# 3. Structured Output Models (Immutable Data Contracts)
# =============================================================================

class CompoundExposureReport(BaseModel):
    """
    Structured aggregate risk exposure analysis across a sequence of tasks or transaction.
    Purely advisory; does not authorize execution.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    total_steps: int = Field(ge=0, description="Total number of tasks in the compound chain")
    mutation_steps: int = Field(ge=0, description="Count of mutating actions")
    non_reversible_steps: int = Field(ge=0, description="Count of non-reversible actions")
    admin_required_steps: int = Field(ge=0, description="Count of actions requiring elevated/admin privileges")
    max_impact: RiskImpact = Field(description="Highest single-step impact observed")
    aggregate_exposure_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Deterministic exposure index bounded between 0.0 and 100.0",
    )
    summary: str = Field(description="Deterministic summary of compound exposure")


class RiskIntelligenceResult(BaseModel):
    """
    Structured, multi-dimensional risk intelligence analysis for an individual AgentTask.
    Strictly advisory. Contains no authorization fields (no `allowed`, `decision`, or execution hooks).
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: Optional[str] = Field(default=None, description="Identifier of the assessed task")
    action: Optional[AgentAction] = Field(default=None, description="Evaluated AgentAction enum")
    action_category: ActionCategory = Field(description="Authoritative ActionCategory mapped from task")
    impact: RiskImpact = Field(description="Advisory impact severity")
    reversibility: ReversibilityClass = Field(description="Advisory reversibility classification")
    scope: ActionScope = Field(description="Advisory target scope / blast radius")
    privilege: PrivilegeScope = Field(description="Advisory privilege requirement")
    factors: List[RiskFactor] = Field(default_factory=list, description="Sorted list of identified risk factors")
    explanation: str = Field(description="Deterministic human-readable risk explanation")
    compound_exposure: Optional[CompoundExposureReport] = Field(
        default=None,
        description="Optional compound exposure report if evaluated in a transaction context",
    )


# =============================================================================
# 4. Pure Deterministic Helper Functions
# =============================================================================

def map_action_to_category(action: Optional[AgentAction], parameters: Optional[Dict[str, Any]] = None) -> ActionCategory:
    """
    Deterministically map an AgentAction and optional parameters to an ActionCategory.
    Pure functional mapping without filesystem or live system access.
    """
    if action is None:
        return ActionCategory.UNKNOWN

    if action in (
        AgentAction.FIND_PROCESS,
        AgentAction.FIND_TCP_PORT,
        AgentAction.GET_FILE_INFO,
        AgentAction.LIST_DIRECTORY,
        AgentAction.READ_TEXT_FILE,
        AgentAction.FIND_FILES,
        AgentAction.SEARCH_TEXT,
        AgentAction.FIND_SERVICE,
    ):
        return ActionCategory.READ_ONLY_OBSERVATION

    if action == AgentAction.WRITE_FILE:
        return ActionCategory.FILE_MODIFY

    if action == AgentAction.DELETE_FILE:
        return ActionCategory.FILE_DELETE

    if action == AgentAction.STOP_PROCESS:
        return ActionCategory.PROCESS_STOP

    if action == AgentAction.RESTART_SERVICE:
        return ActionCategory.SERVICE_CONFIGURATION

    if action == AgentAction.FLUSH_DNS:
        return ActionCategory.NETWORK_CONFIGURATION

    return ActionCategory.UNKNOWN


def is_mutation_category(category: ActionCategory) -> bool:
    """Check if an ActionCategory represents a state-mutating operation."""
    return category not in (ActionCategory.READ_ONLY_OBSERVATION, ActionCategory.UNKNOWN)


# =============================================================================
# 5. Core Deterministic Risk Intelligence Engine
# =============================================================================

class EVRiskIntelligenceEngine:
    """
    Pure deterministic risk intelligence and risk model hardening engine for E.V.
    Analyzes tasks, actions, parameters, and transactions to produce structured advisory reports.
    """

    def analyze_task(
        self,
        task: Union[AgentTask, Dict[str, Any], ActionCategory, Any],
        has_backup: Optional[bool] = None,
        is_reversible: Optional[bool] = None,
        compound_report: Optional[CompoundExposureReport] = None,
    ) -> RiskIntelligenceResult:
        """
        Analyze a single AgentTask or ActionCategory deterministically and return a RiskIntelligenceResult.
        """
        task_id: Optional[str] = None
        action: Optional[AgentAction] = None
        parameters: Dict[str, Any] = {}
        category: ActionCategory = ActionCategory.UNKNOWN

        # 1. Structural extraction & fail-closed validation
        if isinstance(task, AgentTask):
            task_id = task.task_id
            action = task.action
            parameters = task.parameters or {}
            category = map_action_to_category(action, parameters)
        elif isinstance(task, ActionCategory):
            category = task
        elif isinstance(task, dict):
            task_id = str(task.get("task_id", "")) or None
            raw_action = task.get("action")
            if isinstance(raw_action, AgentAction):
                action = raw_action
            elif isinstance(raw_action, str):
                try:
                    action = AgentAction(raw_action)
                except ValueError:
                    action = None

            raw_params = task.get("parameters")
            if isinstance(raw_params, dict):
                parameters = raw_params

            raw_category = task.get("action_category")
            if isinstance(raw_category, ActionCategory):
                category = raw_category
            elif isinstance(raw_category, str):
                try:
                    category = ActionCategory(raw_category)
                except ValueError:
                    category = map_action_to_category(action, parameters)
            else:
                category = map_action_to_category(action, parameters)
        else:
            # Unrecognized/malformed input -> fail closed
            return RiskIntelligenceResult(
                task_id=None,
                action=None,
                action_category=ActionCategory.UNKNOWN,
                impact=RiskImpact.CRITICAL,
                reversibility=ReversibilityClass.UNKNOWN,
                scope=ActionScope.UNKNOWN,
                privilege=PrivilegeScope.UNKNOWN,
                factors=[RiskFactor.SYSTEM_CRITICAL_TARGET],
                explanation="Malformed or invalid task structure; failed closed with critical advisory rating.",
                compound_exposure=compound_report,
            )

        # 2. Classify Target Scope
        scope = self._classify_scope(action, category, parameters)

        # 3. Classify Privilege Scope
        privilege = self._classify_privilege(action, category, parameters)

        # 4. Classify Impact
        impact = self._classify_impact(action, category, parameters, privilege, scope)

        # 5. Classify Reversibility
        reversibility = self._classify_reversibility(action, category, parameters, has_backup, is_reversible)

        # 6. Identify Deterministic Risk Factors
        factors = self._identify_factors(
            category=category,
            impact=impact,
            reversibility=reversibility,
            privilege=privilege,
            scope=scope,
            has_backup=has_backup,
            is_reversible=is_reversible,
        )

        # 7. Generate Deterministic Explanation
        explanation = self._generate_explanation(
            action=action,
            category=category,
            impact=impact,
            reversibility=reversibility,
            scope=scope,
            privilege=privilege,
            factors=factors,
            parameters=parameters,
        )

        return RiskIntelligenceResult(
            task_id=task_id,
            action=action,
            action_category=category,
            impact=impact,
            reversibility=reversibility,
            scope=scope,
            privilege=privilege,
            factors=factors,
            explanation=explanation,
            compound_exposure=compound_report,
        )

    def analyze_tasks(self, tasks: Sequence[AgentTask]) -> List[RiskIntelligenceResult]:
        """
        Analyze an ordered sequence of tasks, attaching compound exposure analysis to each.
        """
        if not tasks:
            return []

        compound_report = self.calculate_compound_exposure(tasks)
        results: List[RiskIntelligenceResult] = []

        for task in tasks:
            res = self.analyze_task(task, compound_report=compound_report)
            results.append(res)

        return results

    def analyze_transaction(self, transaction: Any) -> Tuple[List[RiskIntelligenceResult], CompoundExposureReport]:
        """
        Analyze a CompoundTransaction deterministically.
        Extracts tasks from the transaction and computes individual and aggregate exposure.
        """
        tasks: List[AgentTask] = []
        if hasattr(transaction, "tasks") and isinstance(transaction.tasks, list):
            tasks = transaction.tasks

        compound_report = self.calculate_compound_exposure(tasks)
        task_results = [self.analyze_task(t, compound_report=compound_report) for t in tasks]
        return task_results, compound_report

    def calculate_compound_exposure(self, tasks: Sequence[AgentTask]) -> CompoundExposureReport:
        """
        Deterministically calculate compound risk exposure across a batch of tasks.

        Transparent Scoring Formula:
        - Base impact score: Max impact across all steps (READ_ONLY=0, LOW=10, MEDIUM=25, HIGH=50, CRITICAL=90)
        - Mutation step adder: +5.0 per mutating action
        - Non-reversible adder: +15.0 per non-reversible action
        - Admin-required adder: +20.0 per admin/system action
        - Compound chain adder: +5.0 * (mutation_steps - 1) if mutation_steps >= 2
        - Total is clamped strictly between 0.0 and 100.0.
        """
        if not tasks:
            return CompoundExposureReport(
                total_steps=0,
                mutation_steps=0,
                non_reversible_steps=0,
                admin_required_steps=0,
                max_impact=RiskImpact.READ_ONLY,
                aggregate_exposure_score=0.0,
                summary="Empty task sequence; zero exposure.",
            )

        total_steps = len(tasks)
        mutation_steps = 0
        non_reversible_steps = 0
        admin_required_steps = 0
        max_impact = RiskImpact.READ_ONLY

        impact_weights = {
            RiskImpact.READ_ONLY: 0.0,
            RiskImpact.LOW: 10.0,
            RiskImpact.MEDIUM: 25.0,
            RiskImpact.HIGH: 50.0,
            RiskImpact.CRITICAL: 90.0,
        }

        for t in tasks:
            cat = map_action_to_category(t.action, t.parameters)
            params = t.parameters or {}

            # Scope, privilege, impact, reversibility for step
            scope = self._classify_scope(t.action, cat, params)
            priv = self._classify_privilege(t.action, cat, params)
            imp = self._classify_impact(t.action, cat, params, priv, scope)
            rev = self._classify_reversibility(t.action, cat, params)

            if impact_weights[imp] > impact_weights[max_impact]:
                max_impact = imp

            if is_mutation_category(cat):
                mutation_steps += 1

            if rev == ReversibilityClass.NON_REVERSIBLE:
                non_reversible_steps += 1

            if priv in (PrivilegeScope.ADMIN_REQUIRED, PrivilegeScope.SYSTEM_PROTECTED):
                admin_required_steps += 1

        # Calculate score
        base_score = impact_weights[max_impact]
        mutation_contrib = mutation_steps * 5.0
        non_rev_contrib = non_reversible_steps * 15.0
        admin_contrib = admin_required_steps * 20.0
        chain_contrib = (mutation_steps - 1) * 5.0 if mutation_steps >= 2 else 0.0

        raw_score = base_score + mutation_contrib + non_rev_contrib + admin_contrib + chain_contrib
        aggregate_score = round(max(0.0, min(100.0, raw_score)), 2)

        summary = (
            f"Compound exposure: {total_steps} step(s), {mutation_steps} mutation(s), "
            f"{non_reversible_steps} non-reversible step(s), {admin_required_steps} elevated step(s). "
            f"Peak impact: {max_impact.value}. Aggregate score: {aggregate_score:.1f}/100."
        )

        return CompoundExposureReport(
            total_steps=total_steps,
            mutation_steps=mutation_steps,
            non_reversible_steps=non_reversible_steps,
            admin_required_steps=admin_required_steps,
            max_impact=max_impact,
            aggregate_exposure_score=aggregate_score,
            summary=summary,
        )

    # -------------------------------------------------------------------------
    # Internal Deterministic Classifiers
    # -------------------------------------------------------------------------

    def _classify_scope(
        self,
        action: Optional[AgentAction],
        category: ActionCategory,
        parameters: Dict[str, Any],
    ) -> ActionScope:
        """Deterministically determine the target boundary / blast radius."""
        if category == ActionCategory.UNKNOWN:
            return ActionScope.UNKNOWN

        if category == ActionCategory.READ_ONLY_OBSERVATION:
            if action in (AgentAction.LIST_DIRECTORY, AgentAction.FIND_FILES):
                return ActionScope.DIRECTORY
            if action == AgentAction.FIND_PROCESS:
                return ActionScope.SINGLE_PROCESS
            if action == AgentAction.FIND_SERVICE:
                return ActionScope.SERVICE
            if action == AgentAction.FIND_TCP_PORT:
                return ActionScope.NETWORK_INTERFACE
            if action in (AgentAction.GET_FILE_INFO, AgentAction.READ_TEXT_FILE, AgentAction.SEARCH_TEXT):
                return ActionScope.SINGLE_FILE
            return ActionScope.SINGLE_FILE

        if category in (ActionCategory.FILE_CREATE, ActionCategory.FILE_MODIFY, ActionCategory.FILE_DELETE, ActionCategory.FILE_RESTORE):
            return ActionScope.SINGLE_FILE

        if category in (ActionCategory.PROCESS_START, ActionCategory.PROCESS_STOP):
            return ActionScope.SINGLE_PROCESS

        if category == ActionCategory.SERVICE_CONFIGURATION:
            return ActionScope.SERVICE

        if category == ActionCategory.NETWORK_CONFIGURATION:
            return ActionScope.NETWORK_INTERFACE

        if category in (
            ActionCategory.SYSTEM_POWER,
            ActionCategory.SECURITY_CONFIGURATION,
            ActionCategory.CREDENTIAL_ACCESS,
            ActionCategory.REGISTRY_MODIFICATION,
            ActionCategory.SOFTWARE_INSTALL,
            ActionCategory.SOFTWARE_UNINSTALL,
            ActionCategory.COMMAND_EXECUTION,
        ):
            return ActionScope.SYSTEM_WIDE

        return ActionScope.UNKNOWN

    def _classify_privilege(
        self,
        action: Optional[AgentAction],
        category: ActionCategory,
        parameters: Dict[str, Any],
    ) -> PrivilegeScope:
        """Deterministically determine the required privilege boundary."""
        if category == ActionCategory.UNKNOWN:
            return PrivilegeScope.UNKNOWN

        if category == ActionCategory.READ_ONLY_OBSERVATION:
            return PrivilegeScope.STANDARD_USER

        if category in (ActionCategory.FILE_CREATE, ActionCategory.FILE_MODIFY, ActionCategory.FILE_DELETE, ActionCategory.FILE_RESTORE):
            path_str = str(parameters.get("path", "")).lower()
            # Windows system directories require elevation
            if any(path_str.startswith(p) for p in ("c:\\windows", "c:\\program files", "\\windows\\system32")):
                return PrivilegeScope.ADMIN_REQUIRED
            return PrivilegeScope.STANDARD_USER

        if category == ActionCategory.PROCESS_STOP:
            proc_name = str(parameters.get("process_name") or parameters.get("name") or "").lower().strip()
            pid = parameters.get("pid")
            clean_name = proc_name.replace(".exe", "")
            if (isinstance(pid, int) and pid <= 4) or (clean_name in KNOWN_CRITICAL_PROCESSES):
                return PrivilegeScope.SYSTEM_PROTECTED
            return PrivilegeScope.STANDARD_USER

        if category == ActionCategory.SERVICE_CONFIGURATION:
            svc_name = str(parameters.get("name") or parameters.get("service_name") or "").lower().strip()
            if svc_name in KNOWN_CRITICAL_SERVICES:
                return PrivilegeScope.SYSTEM_PROTECTED
            return PrivilegeScope.ADMIN_REQUIRED

        if category == ActionCategory.NETWORK_CONFIGURATION:
            if action == AgentAction.FLUSH_DNS:
                return PrivilegeScope.STANDARD_USER
            return PrivilegeScope.ADMIN_REQUIRED

        if category in (ActionCategory.SECURITY_CONFIGURATION, ActionCategory.CREDENTIAL_ACCESS):
            return PrivilegeScope.SYSTEM_PROTECTED

        if category in (
            ActionCategory.REGISTRY_MODIFICATION,
            ActionCategory.SOFTWARE_INSTALL,
            ActionCategory.SOFTWARE_UNINSTALL,
            ActionCategory.SYSTEM_POWER,
            ActionCategory.COMMAND_EXECUTION,
            ActionCategory.PROCESS_START,
        ):
            return PrivilegeScope.ADMIN_REQUIRED

        return PrivilegeScope.UNKNOWN

    def _classify_impact(
        self,
        action: Optional[AgentAction],
        category: ActionCategory,
        parameters: Dict[str, Any],
        privilege: PrivilegeScope,
        scope: ActionScope,
    ) -> RiskImpact:
        """Deterministically determine advisory impact severity."""
        if category == ActionCategory.UNKNOWN:
            return RiskImpact.CRITICAL

        if category == ActionCategory.READ_ONLY_OBSERVATION:
            return RiskImpact.READ_ONLY

        if category == ActionCategory.FILE_CREATE:
            return RiskImpact.LOW

        if category in (ActionCategory.FILE_MODIFY, ActionCategory.FILE_RESTORE, ActionCategory.PROCESS_START):
            return RiskImpact.MEDIUM

        if category == ActionCategory.FILE_DELETE:
            return RiskImpact.HIGH

        if category == ActionCategory.PROCESS_STOP:
            if privilege in (PrivilegeScope.ADMIN_REQUIRED, PrivilegeScope.SYSTEM_PROTECTED):
                return RiskImpact.CRITICAL
            return RiskImpact.MEDIUM

        if category in (ActionCategory.SERVICE_CONFIGURATION, ActionCategory.NETWORK_CONFIGURATION):
            if privilege == PrivilegeScope.SYSTEM_PROTECTED:
                return RiskImpact.CRITICAL
            return RiskImpact.HIGH

        if category in (
            ActionCategory.SECURITY_CONFIGURATION,
            ActionCategory.CREDENTIAL_ACCESS,
        ):
            return RiskImpact.CRITICAL

        if category in (
            ActionCategory.SYSTEM_POWER,
            ActionCategory.REGISTRY_MODIFICATION,
            ActionCategory.SOFTWARE_INSTALL,
            ActionCategory.SOFTWARE_UNINSTALL,
            ActionCategory.COMMAND_EXECUTION,
        ):
            return RiskImpact.HIGH

        return RiskImpact.CRITICAL

    def _classify_reversibility(
        self,
        action: Optional[AgentAction],
        category: ActionCategory,
        parameters: Dict[str, Any],
        has_backup: Optional[bool] = None,
        is_reversible: Optional[bool] = None,
    ) -> ReversibilityClass:
        """Deterministically determine advisory reversibility class."""
        if category == ActionCategory.UNKNOWN:
            return ReversibilityClass.UNKNOWN

        if category == ActionCategory.READ_ONLY_OBSERVATION:
            return ReversibilityClass.IDEMPOTENT

        # File actions in EV runtime
        if category in (ActionCategory.FILE_CREATE, ActionCategory.FILE_MODIFY, ActionCategory.FILE_DELETE, ActionCategory.FILE_RESTORE):
            if is_reversible is False or has_backup is False:
                return ReversibilityClass.NON_REVERSIBLE
            return ReversibilityClass.FULLY_REVERSIBLE

        if category in (ActionCategory.PROCESS_STOP, ActionCategory.PROCESS_START):
            return ReversibilityClass.NON_REVERSIBLE

        if category == ActionCategory.SERVICE_CONFIGURATION:
            return ReversibilityClass.COMPENSATING_REVERSIBLE

        if category == ActionCategory.NETWORK_CONFIGURATION:
            if action == AgentAction.FLUSH_DNS:
                return ReversibilityClass.IDEMPOTENT
            return ReversibilityClass.COMPENSATING_REVERSIBLE

        if category in (ActionCategory.SECURITY_CONFIGURATION, ActionCategory.CREDENTIAL_ACCESS):
            return ReversibilityClass.NON_REVERSIBLE

        return ReversibilityClass.UNKNOWN

    def _identify_factors(
        self,
        category: ActionCategory,
        impact: RiskImpact,
        reversibility: ReversibilityClass,
        privilege: PrivilegeScope,
        scope: ActionScope,
        has_backup: Optional[bool] = None,
        is_reversible: Optional[bool] = None,
    ) -> List[RiskFactor]:
        """Identify and sort applicable risk factors in stable deterministic order."""
        factors: List[RiskFactor] = []

        if is_mutation_category(category):
            factors.append(RiskFactor.MUTATION)

        if is_mutation_category(category) and (has_backup is False or is_reversible is False):
            factors.append(RiskFactor.UNBACKED_MUTATION)

        if reversibility == ReversibilityClass.NON_REVERSIBLE:
            factors.append(RiskFactor.NON_REVERSIBLE_CHANGE)

        if privilege in (PrivilegeScope.ADMIN_REQUIRED, PrivilegeScope.SYSTEM_PROTECTED):
            factors.append(RiskFactor.ELEVATED_PRIVILEGE)

        if privilege == PrivilegeScope.SYSTEM_PROTECTED or category in (
            ActionCategory.SECURITY_CONFIGURATION,
            ActionCategory.CREDENTIAL_ACCESS,
        ):
            factors.append(RiskFactor.SYSTEM_CRITICAL_TARGET)

        if scope in (ActionScope.SYSTEM_WIDE, ActionScope.DIRECTORY) or impact in (RiskImpact.HIGH, RiskImpact.CRITICAL):
            factors.append(RiskFactor.WIDE_BLAST_RADIUS)

        # Ensure stable, deterministic enum ordering
        factor_order = [
            RiskFactor.MUTATION,
            RiskFactor.UNBACKED_MUTATION,
            RiskFactor.NON_REVERSIBLE_CHANGE,
            RiskFactor.ELEVATED_PRIVILEGE,
            RiskFactor.SYSTEM_CRITICAL_TARGET,
            RiskFactor.WIDE_BLAST_RADIUS,
            RiskFactor.COMPOUND_MUTATION_CHAIN,
        ]
        return [f for f in factor_order if f in factors]

    def _generate_explanation(
        self,
        action: Optional[AgentAction],
        category: ActionCategory,
        impact: RiskImpact,
        reversibility: ReversibilityClass,
        scope: ActionScope,
        privilege: PrivilegeScope,
        factors: List[RiskFactor],
        parameters: Dict[str, Any],
    ) -> str:
        """Deterministically generate a clear, human-readable risk explanation."""
        action_name = action.value if action else category.value
        target = parameters.get("path") or parameters.get("name") or parameters.get("port") or parameters.get("pid") or ""
        target_str = f" targeting '{target}'" if target else ""

        lines = [
            f"Action: {action_name}{target_str} (Category: {category.value}).",
            f"Impact: {impact.value} | Scope: {scope.value} | Privilege: {privilege.value} | Reversibility: {reversibility.value}.",
        ]

        if factors:
            factor_names = ", ".join(f.value for f in factors)
            lines.append(f"Identified Risk Factors: {factor_names}.")
        else:
            lines.append("No elevated risk factors detected.")

        return " ".join(lines)


# =============================================================================
# 6. Module-Level Convenience Functions
# =============================================================================

_DEFAULT_ENGINE = EVRiskIntelligenceEngine()


def analyze_task(
    task: Union[AgentTask, Dict[str, Any], ActionCategory, Any],
    has_backup: Optional[bool] = None,
    is_reversible: Optional[bool] = None,
    compound_report: Optional[CompoundExposureReport] = None,
) -> RiskIntelligenceResult:
    """Convenience functional interface for analyzing a single task."""
    return _DEFAULT_ENGINE.analyze_task(
        task=task,
        has_backup=has_backup,
        is_reversible=is_reversible,
        compound_report=compound_report,
    )


def analyze_tasks(tasks: Sequence[AgentTask]) -> List[RiskIntelligenceResult]:
    """Convenience functional interface for analyzing a sequence of tasks."""
    return _DEFAULT_ENGINE.analyze_tasks(tasks)


def analyze_transaction(transaction: Any) -> Tuple[List[RiskIntelligenceResult], CompoundExposureReport]:
    """Convenience functional interface for analyzing a CompoundTransaction."""
    return _DEFAULT_ENGINE.analyze_transaction(transaction)


def calculate_compound_exposure(tasks: Sequence[AgentTask]) -> CompoundExposureReport:
    """Convenience functional interface for calculating compound exposure."""
    return _DEFAULT_ENGINE.calculate_compound_exposure(tasks)
