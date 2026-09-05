"""
Structured Failure Diagnostic & Controlled Windows Repair Engine for E.V. (Phase 5 Task 008).

Provides deterministic system failure detection, root-cause classification,
privilege boundary evaluation, and structured repair plan generation.

Guarantees strict separation between diagnosis and execution:
Diagnosis (Read-Only) -> Repair Plan -> Risk Assessment -> User Approval -> Execution -> Verification -> Recovery
"""
from __future__ import annotations

import json
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

from pydantic import BaseModel, ConfigDict, Field

from core.models import (
    ActionCategory,
    AgentAction,
    AgentTask,
    RiskLevel,
    VerificationType,
)
from tools.filesystem import get_file_info, read_text_file
from tools.network import find_tcp_port
from tools.powershell import run_powershell
from tools.processes import SYSTEM_CRITICAL_PROCESSES, find_processes, list_processes
from tools.services import SYSTEM_CRITICAL_SERVICES, find_services

logger = logging.getLogger("ev.diagnostics")


class FailureCategory(str, Enum):
    """Authoritative taxonomy of supported Windows failure classes."""
    PORT_COLLISION_FAILURE = "PORT_COLLISION_FAILURE"
    STALE_LOCKFILE_FAILURE = "STALE_LOCKFILE_FAILURE"
    CONFIG_CORRUPTION_FAILURE = "CONFIG_CORRUPTION_FAILURE"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    DNS_RESOLUTION_FAILURE = "DNS_RESOLUTION_FAILURE"
    NONE = "NONE"


class PrivilegeRequirement(str, Enum):
    """Privilege requirement classification for diagnosis and repair."""
    STANDARD_USER = "STANDARD_USER"
    ADMIN_REQUIRED = "ADMIN_REQUIRED"
    UNKNOWN = "UNKNOWN"


class RollbackCapability(str, Enum):
    """Reversibility classification for repair operations."""
    FULLY_REVERSIBLE = "FULLY_REVERSIBLE"                     # Restores via EVBackupManager SHA-256 backup
    COMPENSATING_STATE_REVERSIBLE = "COMPENSATING_STATE_REVERSIBLE" # Inverse state restore (e.g. stop restarted service)
    NOT_REVERSIBLE = "NOT_REVERSIBLE"                         # Process termination cannot be un-killed
    NOT_APPLICABLE_IDEMPOTENT = "NOT_APPLICABLE_IDEMPOTENT"   # Idempotent cache reset (e.g. flush DNS)


class DiagnosticResult(BaseModel):
    """
    Structured outcome of a deterministic failure diagnosis.
    Contains evidence, root cause classification, and recommended repair proposal.
    """
    model_config = ConfigDict(extra="forbid")

    failure_category: FailureCategory
    status: str
    is_failure: bool
    affected_resource: Optional[str] = None
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    recommended_repair: Optional[str] = None
    repair_parameters: Optional[Dict[str, Any]] = None
    required_risk_level: RiskLevel = RiskLevel.NONE
    approval_required: bool = False
    privilege_requirement: PrivilegeRequirement = PrivilegeRequirement.STANDARD_USER
    verification_type: Optional[VerificationType] = None
    rollback_capability: RollbackCapability = RollbackCapability.NOT_APPLICABLE_IDEMPOTENT
    message: str = ""


class RepairPlan(BaseModel):
    """
    Executable repair plan generated from a DiagnosticResult.
    """
    model_config = ConfigDict(extra="forbid")

    diagnostic_result: DiagnosticResult
    tasks: List[AgentTask] = Field(default_factory=list)
    is_executable: bool = False
    estimated_risk: RiskLevel = RiskLevel.NONE
    requires_approval: bool = False
    privilege_requirement: PrivilegeRequirement = PrivilegeRequirement.STANDARD_USER
    reversibility_summary: str = ""


# -----------------------------------------------------------------------------
# 1. Port Collision Diagnostic
# -----------------------------------------------------------------------------

def diagnose_port_collision(
    port: int,
    expected_process_name: Optional[str] = None,
) -> DiagnosticResult:
    """
    Diagnose whether a TCP port is occupied by an unexpected or hung process.
    """
    if not isinstance(port, int) or port < 1 or port > 65535:
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="INVALID_PORT",
            is_failure=False,
            message=f"Invalid port number: {port}",
        )

    connections = find_tcp_port(port)
    if not connections:
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="PORT_FREE",
            is_failure=False,
            affected_resource=str(port),
            message=f"Port {port} is free (no active TCP listeners)",
        )

    # Inspect the first active listening or established connection
    conn = connections[0]
    owning_pid = conn.owning_pid
    proc_name = conn.process_name or "unknown"

    # If process name is missing, look it up by PID
    if owning_pid and proc_name == "unknown":
        all_procs = list_processes()
        matched_proc = next((p for p in all_procs if p.pid == owning_pid), None)
        if matched_proc and matched_proc.name:
            proc_name = matched_proc.name

    evidence = {
        "port": port,
        "owning_pid": owning_pid,
        "process_name": proc_name,
        "state": conn.state,
        "local_address": conn.local_address,
    }

    # Case: Port occupied by the expected process
    if expected_process_name and proc_name.lower().strip() == expected_process_name.lower().strip():
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="PORT_OCCUPIED_EXPECTED",
            is_failure=False,
            affected_resource=str(port),
            evidence=evidence,
            message=f"Port {port} is occupied by expected process '{proc_name}' (PID {owning_pid})",
        )

    # Case: Owning PID cannot be determined
    if owning_pid is None or owning_pid <= 0:
        return DiagnosticResult(
            failure_category=FailureCategory.PORT_COLLISION_FAILURE,
            status="PORT_COLLISION_UNKNOWN_OWNER",
            is_failure=True,
            affected_resource=str(port),
            evidence=evidence,
            privilege_requirement=PrivilegeRequirement.ADMIN_REQUIRED,
            message=f"Port {port} is occupied, but owning process PID could not be determined",
        )

    # Case: System-critical process collision
    proc_clean = proc_name.lower().strip().replace(".exe", "")
    if owning_pid <= 4 or proc_clean in SYSTEM_CRITICAL_PROCESSES:
        return DiagnosticResult(
            failure_category=FailureCategory.PORT_COLLISION_FAILURE,
            status="PORT_COLLISION_SYSTEM_CRITICAL",
            is_failure=True,
            affected_resource=str(port),
            evidence=evidence,
            privilege_requirement=PrivilegeRequirement.ADMIN_REQUIRED,
            message=f"Port {port} is occupied by system-critical process '{proc_name}' (PID {owning_pid}); automated termination blocked",
        )

    # Case: Eligible user-level process collision
    return DiagnosticResult(
        failure_category=FailureCategory.PORT_COLLISION_FAILURE,
        status="PORT_COLLISION_DETECTED",
        is_failure=True,
        affected_resource=str(port),
        evidence=evidence,
        recommended_repair="STOP_PROCESS",
        repair_parameters={"pid": owning_pid, "process_name": proc_name, "port": port},
        required_risk_level=RiskLevel.MEDIUM,
        approval_required=True,
        privilege_requirement=PrivilegeRequirement.STANDARD_USER,
        verification_type=VerificationType.PROCESS_NOT_EXISTS,
        rollback_capability=RollbackCapability.NOT_REVERSIBLE,
        message=f"Port {port} collision: unexpected process '{proc_name}' (PID {owning_pid}) is occupying the port",
    )


# -----------------------------------------------------------------------------
# 2. Stale Lockfile Diagnostic
# -----------------------------------------------------------------------------

def diagnose_stale_lockfile(
    lockfile_path: str,
    associated_process_name: Optional[str] = None,
    associated_pid: Optional[int] = None,
) -> DiagnosticResult:
    """
    Diagnose whether a lockfile exists without an active associated process holding it.
    """
    if not lockfile_path or not isinstance(lockfile_path, str):
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="INVALID_PATH",
            is_failure=False,
            message="Invalid lockfile path",
        )

    finfo = get_file_info(lockfile_path)
    if not finfo.exists:
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="LOCKFILE_NOT_FOUND",
            is_failure=False,
            affected_resource=lockfile_path,
            message=f"Lockfile does not exist at '{lockfile_path}'",
        )

    evidence = {
        "lockfile_path": lockfile_path,
        "associated_process_name": associated_process_name,
        "associated_pid": associated_pid,
        "size_bytes": finfo.size_bytes,
    }

    # If associated PID is provided, check if that PID is alive
    if associated_pid is not None and associated_pid > 0:
        all_procs = list_processes()
        proc_live = any(p.pid == associated_pid for p in all_procs)
        if proc_live:
            return DiagnosticResult(
                failure_category=FailureCategory.NONE,
                status="LOCKFILE_ACTIVE",
                is_failure=False,
                affected_resource=lockfile_path,
                evidence=evidence,
                message=f"Lockfile at '{lockfile_path}' is active; associated PID {associated_pid} is running",
            )

    # If associated process name is provided, check if any instance is running
    if associated_process_name and associated_process_name.strip():
        live_matches = find_processes(associated_process_name.strip())
        if live_matches:
            return DiagnosticResult(
                failure_category=FailureCategory.NONE,
                status="LOCKFILE_ACTIVE",
                is_failure=False,
                affected_resource=lockfile_path,
                evidence=evidence,
                message=f"Lockfile at '{lockfile_path}' is active; associated process '{associated_process_name}' is running",
            )

    # If we reached here: lockfile exists, but the associated process/PID is not active
    return DiagnosticResult(
        failure_category=FailureCategory.STALE_LOCKFILE_FAILURE,
        status="STALE_LOCKFILE_DETECTED",
        is_failure=True,
        affected_resource=lockfile_path,
        evidence=evidence,
        recommended_repair="DELETE_FILE",
        repair_parameters={"path": lockfile_path},
        required_risk_level=RiskLevel.HIGH,
        approval_required=True,
        privilege_requirement=PrivilegeRequirement.STANDARD_USER,
        verification_type=VerificationType.FILE_NOT_EXISTS,
        rollback_capability=RollbackCapability.FULLY_REVERSIBLE,
        message=f"Stale lockfile detected at '{lockfile_path}'; associated process is inactive",
    )


# -----------------------------------------------------------------------------
# 3. Config Corruption Diagnostic
# -----------------------------------------------------------------------------

def diagnose_config_corruption(
    config_path: str,
    expected_format: Optional[str] = "json",
    expected_keys: Optional[List[str]] = None,
    repair_template: Optional[str] = None,
) -> DiagnosticResult:
    """
    Diagnose whether a configuration file is missing, empty, or syntactically corrupted.
    """
    if not config_path or not isinstance(config_path, str):
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="INVALID_PATH",
            is_failure=False,
            message="Invalid config path",
        )

    read_res = read_text_file(config_path)
    if not read_res.success:
        return DiagnosticResult(
            failure_category=FailureCategory.CONFIG_CORRUPTION_FAILURE,
            status="CONFIG_MISSING_OR_UNREADABLE",
            is_failure=True,
            affected_resource=config_path,
            evidence={"path": config_path, "error": read_res.error},
            recommended_repair="WRITE_FILE" if repair_template else None,
            repair_parameters={"path": config_path, "content": repair_template} if repair_template else None,
            required_risk_level=RiskLevel.LOW if not Path(config_path).exists() else RiskLevel.MEDIUM,
            approval_required=True,
            privilege_requirement=PrivilegeRequirement.STANDARD_USER,
            verification_type=VerificationType.FILE_EXISTS,
            rollback_capability=RollbackCapability.FULLY_REVERSIBLE,
            message=f"Configuration file at '{config_path}' is missing or unreadable: {read_res.error}",
        )

    content = read_res.content or ""
    if not content.strip():
        return DiagnosticResult(
            failure_category=FailureCategory.CONFIG_CORRUPTION_FAILURE,
            status="CONFIG_EMPTY",
            is_failure=True,
            affected_resource=config_path,
            evidence={"path": config_path, "size_bytes": 0},
            recommended_repair="WRITE_FILE" if repair_template else None,
            repair_parameters={"path": config_path, "content": repair_template} if repair_template else None,
            required_risk_level=RiskLevel.MEDIUM,
            approval_required=True,
            privilege_requirement=PrivilegeRequirement.STANDARD_USER,
            verification_type=VerificationType.FILE_EXISTS,
            rollback_capability=RollbackCapability.FULLY_REVERSIBLE,
            message=f"Configuration file at '{config_path}' is empty",
        )

    # Format syntax validation
    if expected_format == "json":
        try:
            parsed = json.loads(content)
            if expected_keys and isinstance(parsed, dict):
                missing_keys = [k for k in expected_keys if k not in parsed]
                if missing_keys:
                    return DiagnosticResult(
                        failure_category=FailureCategory.CONFIG_CORRUPTION_FAILURE,
                        status="CONFIG_SCHEMA_INVALID",
                        is_failure=True,
                        affected_resource=config_path,
                        evidence={"path": config_path, "missing_keys": missing_keys},
                        recommended_repair="WRITE_FILE" if repair_template else None,
                        repair_parameters={"path": config_path, "content": repair_template} if repair_template else None,
                        required_risk_level=RiskLevel.MEDIUM,
                        approval_required=True,
                        privilege_requirement=PrivilegeRequirement.STANDARD_USER,
                        verification_type=VerificationType.FILE_EXISTS,
                        rollback_capability=RollbackCapability.FULLY_REVERSIBLE,
                        message=f"Config at '{config_path}' is missing required schema keys: {missing_keys}",
                    )
        except Exception as exc:
            return DiagnosticResult(
                failure_category=FailureCategory.CONFIG_CORRUPTION_FAILURE,
                status="CONFIG_SYNTAX_CORRUPTED",
                is_failure=True,
                affected_resource=config_path,
                evidence={"path": config_path, "parse_error": str(exc)},
                recommended_repair="WRITE_FILE" if repair_template else None,
                repair_parameters={"path": config_path, "content": repair_template} if repair_template else None,
                required_risk_level=RiskLevel.MEDIUM,
                approval_required=True,
                privilege_requirement=PrivilegeRequirement.STANDARD_USER,
                verification_type=VerificationType.FILE_EXISTS,
                rollback_capability=RollbackCapability.FULLY_REVERSIBLE,
                message=f"Config file at '{config_path}' has syntax corruption: {exc}",
            )

    return DiagnosticResult(
        failure_category=FailureCategory.NONE,
        status="CONFIG_VALID",
        is_failure=False,
        affected_resource=config_path,
        message=f"Configuration file at '{config_path}' is valid",
    )


# -----------------------------------------------------------------------------
# 4. Service Failure Diagnostic
# -----------------------------------------------------------------------------

def diagnose_service_failure(
    service_name: str,
    allowed_services: Optional[Set[str]] = None,
) -> DiagnosticResult:
    """
    Diagnose whether a Windows service is in a failed or stopped state.
    """
    if not service_name or not isinstance(service_name, str) or not service_name.strip():
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="INVALID_SERVICE_NAME",
            is_failure=False,
            message="Invalid service name",
        )

    clean_name = service_name.strip()
    services = find_services(clean_name)
    if not services:
        return DiagnosticResult(
            failure_category=FailureCategory.SERVICE_FAILURE,
            status="SERVICE_NOT_FOUND",
            is_failure=True,
            affected_resource=clean_name,
            message=f"Service '{clean_name}' was not found on this system",
        )

    svc = services[0]
    canonical_name = svc.name
    status = svc.status or "Unknown"

    evidence = {
        "service_name": canonical_name,
        "display_name": svc.display_name,
        "status": status,
        "start_type": svc.start_type,
    }

    if status.lower() == "running":
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="SERVICE_HEALTHY",
            is_failure=False,
            affected_resource=canonical_name,
            evidence=evidence,
            message=f"Service '{canonical_name}' is running normally",
        )

    # Check privilege requirement: system-critical service check
    canonical_lower = canonical_name.lower()
    is_sys_critical = canonical_lower in SYSTEM_CRITICAL_SERVICES
    if is_sys_critical:
        if not allowed_services or canonical_lower not in {s.lower() for s in allowed_services}:
            return DiagnosticResult(
                failure_category=FailureCategory.SERVICE_FAILURE,
                status="SERVICE_STOPPED_SYSTEM_CRITICAL",
                is_failure=True,
                affected_resource=canonical_name,
                evidence=evidence,
                privilege_requirement=PrivilegeRequirement.ADMIN_REQUIRED,
                message=f"Service '{canonical_name}' is stopped ({status}), but is a protected system-critical service",
            )

    return DiagnosticResult(
        failure_category=FailureCategory.SERVICE_FAILURE,
        status="SERVICE_STOPPED",
        is_failure=True,
        affected_resource=canonical_name,
        evidence=evidence,
        recommended_repair="RESTART_SERVICE",
        repair_parameters={"name": canonical_name},
        required_risk_level=RiskLevel.HIGH,
        approval_required=True,
        privilege_requirement=PrivilegeRequirement.STANDARD_USER,
        verification_type=VerificationType.RESULT_NOT_EMPTY,
        rollback_capability=RollbackCapability.COMPENSATING_STATE_REVERSIBLE,
        message=f"Service '{canonical_name}' is stopped ({status}); restart recommended",
    )


# -----------------------------------------------------------------------------
# 5. DNS Resolution Failure Diagnostic
# -----------------------------------------------------------------------------

def diagnose_dns_failure(
    hostname: str,
) -> DiagnosticResult:
    """
    Diagnose whether a DNS resolution failure exists for a target hostname.
    Distinguishes DNS resolution failure from general network unavailability.
    """
    if not hostname or not isinstance(hostname, str) or not hostname.strip():
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="INVALID_HOSTNAME",
            is_failure=False,
            message="Invalid hostname",
        )

    clean_host = hostname.strip()

    # Test DNS resolution
    dns_cmd = f"[System.Net.Dns]::GetHostAddresses('{clean_host}') | Select-Object -ExpandProperty IPAddressToString"
    dns_res = run_powershell(dns_cmd)

    if dns_res.success and dns_res.stdout and dns_res.stdout.strip():
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="DNS_HEALTHY",
            is_failure=False,
            affected_resource=clean_host,
            evidence={"hostname": clean_host, "resolved_addresses": dns_res.stdout.strip().splitlines()},
            message=f"Hostname '{clean_host}' resolves successfully",
        )

    # Check if network interfaces are active
    net_cmd = "Get-NetAdapter | Where-Object { $_.Status -eq 'Up' } | Select-Object Name, Status | ConvertTo-Json -Depth 1"
    net_res = run_powershell(net_cmd)
    if not net_res.success or not net_res.stdout or not net_res.stdout.strip() or net_res.stdout.strip() == "[]":
        return DiagnosticResult(
            failure_category=FailureCategory.NONE,
            status="NETWORK_UNAVAILABLE",
            is_failure=True,
            affected_resource=clean_host,
            evidence={"hostname": clean_host, "error": "No active network adapter found"},
            message="Network adapter is disconnected or unavailable; not a DNS cache failure",
        )

    evidence = {
        "hostname": clean_host,
        "dns_error": dns_res.stderr or "Host not found",
    }

    return DiagnosticResult(
        failure_category=FailureCategory.DNS_RESOLUTION_FAILURE,
        status="DNS_RESOLUTION_FAILED",
        is_failure=True,
        affected_resource=clean_host,
        evidence=evidence,
        recommended_repair="FLUSH_DNS",
        repair_parameters={"hostname": clean_host},
        required_risk_level=RiskLevel.HIGH,
        approval_required=True,
        privilege_requirement=PrivilegeRequirement.STANDARD_USER,
        verification_type=VerificationType.RESULT_NOT_EMPTY,
        rollback_capability=RollbackCapability.NOT_APPLICABLE_IDEMPOTENT,
        message=f"DNS resolution failed for '{clean_host}'; local DNS client cache flush recommended",
    )


# -----------------------------------------------------------------------------
# 6. Repair Plan Construction
# -----------------------------------------------------------------------------

def create_repair_task(diagnostic: DiagnosticResult) -> Optional[AgentTask]:
    """
    Deterministically transform a DiagnosticResult with a recommended repair into a validated AgentTask.
    """
    import uuid

    if not diagnostic.is_failure or not diagnostic.recommended_repair or not diagnostic.repair_parameters:
        return None

    repair_action_str = diagnostic.recommended_repair.upper()
    try:
        action = AgentAction(repair_action_str)
    except ValueError:
        logger.error("Unsupported repair action in diagnostic: %s", repair_action_str)
        return None

    return AgentTask(
        task_id=f"rep-{str(uuid.uuid4())[:6]}",
        action=action,
        parameters=diagnostic.repair_parameters,
        verification_type=diagnostic.verification_type,
    )


def create_repair_plan(diagnostic: DiagnosticResult) -> RepairPlan:
    """
    Construct a structured, auditable RepairPlan from a DiagnosticResult.
    """
    task = create_repair_task(diagnostic)
    tasks = [task] if task is not None else []
    is_executable = (len(tasks) > 0) and (diagnostic.privilege_requirement != PrivilegeRequirement.ADMIN_REQUIRED)

    reversibility_map = {
        RollbackCapability.FULLY_REVERSIBLE: "Reversible via pre-execution SHA-256 backup restoration",
        RollbackCapability.COMPENSATING_STATE_REVERSIBLE: "Compensating state restoration available",
        RollbackCapability.NOT_REVERSIBLE: "Process termination cannot be undone (non-reversible side effect)",
        RollbackCapability.NOT_APPLICABLE_IDEMPOTENT: "Idempotent cache reset (no rollback required)",
    }

    return RepairPlan(
        diagnostic_result=diagnostic,
        tasks=tasks,
        is_executable=is_executable,
        estimated_risk=diagnostic.required_risk_level,
        requires_approval=diagnostic.approval_required,
        privilege_requirement=diagnostic.privilege_requirement,
        reversibility_summary=reversibility_map.get(diagnostic.rollback_capability, "Unknown"),
    )


# Task 017 Contextual Diagnosis & Recovery re-exports
from core.recovery import EVDiagnosticEngine, EVRecoveryPlanner

