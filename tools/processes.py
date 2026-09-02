import subprocess
import json
import logging
from typing import List, Optional
from core.models import ProcessInfo
from tools.powershell import run_powershell

logger = logging.getLogger("ev.processes")

def list_processes() -> List[ProcessInfo]:
    """
    List all processes using PowerShell and return structured ProcessInfo.
    """
    # PowerShell command to get process info as JSON
    ps_command = """
    Get-Process | Select-Object Id, ProcessName, Path, Status | ConvertTo-Json -Depth 1
    """
    result = run_powershell(ps_command)
    processes = []
    if not result.success:
        logger.error("Failed to list processes: %s", result.stderr)
        return processes
    try:
        data = json.loads(result.stdout)
        # Ensure data is a list
        if isinstance(data, dict):
            data = [data]
        for item in data:
            pid = item.get('Id')
            name = item.get('ProcessName')
            path = item.get('Path')
            status = item.get('Status')
            if pid is not None and name is not None:
                processes.append(ProcessInfo(
                    pid=int(pid),
                    name=name,
                    executable_path=path,
                    status=status
                ))
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error("Error parsing process list: %s", e)
    logger.info("Listed %d processes", len(processes))
    return processes

def find_processes(name: str) -> List[ProcessInfo]:
    """
    Find processes by name (case-insensitive).
    """
    all_processes = list_processes()
    name_lower = name.lower()
    matches = [p for p in all_processes if p.name.lower() == name_lower]
    logger.info("Found %d processes matching name '%s'", len(matches), name)
    return matches


SYSTEM_CRITICAL_PROCESSES = {
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


def stop_process(pid: int, process_name: Optional[str] = None) -> "ProcessStopResult":
    """
    Safely terminate a known user-level process by PID.
    Validates process existence and prevents termination of system-critical targets.
    """
    from core.models import ProcessStopResult

    if not isinstance(pid, int) or pid <= 4:
        return ProcessStopResult(
            pid=pid if isinstance(pid, int) else -1,
            name=process_name,
            success=False,
            terminated=False,
            error=f"Invalid or system-protected PID: {pid}",
        )

    # Inspect current processes to verify target exists and check its name
    all_procs = list_processes()
    target = next((p for p in all_procs if p.pid == pid), None)
    if target is None:
        return ProcessStopResult(
            pid=pid,
            name=process_name,
            success=False,
            terminated=False,
            error=f"Process with PID {pid} does not exist",
        )

    proc_name = target.name or process_name or "unknown"
    proc_name_lower = proc_name.lower().strip()

    # Block system-critical processes
    if proc_name_lower in SYSTEM_CRITICAL_PROCESSES or proc_name_lower.replace(".exe", "") in SYSTEM_CRITICAL_PROCESSES:
        return ProcessStopResult(
            pid=pid,
            name=proc_name,
            success=False,
            terminated=False,
            error=f"Termination blocked: '{proc_name}' (PID {pid}) is a protected system-critical process",
        )

    # Validate name mismatch if process_name was provided
    if process_name and process_name.strip():
        expected_lower = process_name.strip().lower()
        if expected_lower != proc_name_lower and expected_lower.replace(".exe", "") != proc_name_lower.replace(".exe", ""):
            return ProcessStopResult(
                pid=pid,
                name=proc_name,
                success=False,
                terminated=False,
                error=f"Process identity mismatch: PID {pid} is '{proc_name}', expected '{process_name}'",
            )

    # Execute termination via bounded PowerShell Stop-Process
    ps_cmd = f"Stop-Process -Id {pid} -Force"
    result = run_powershell(ps_cmd)
    if not result.success:
        err_msg = result.stderr or f"Failed to stop process {pid}"
        if "Access is denied" in err_msg or "UnauthorizedAccessException" in err_msg or "PermissionDenied" in err_msg:
            err_msg = f"ADMIN_REQUIRED: Access denied terminating PID {pid} ({proc_name})"
        return ProcessStopResult(
            pid=pid,
            name=proc_name,
            success=False,
            terminated=False,
            error=err_msg,
        )

    logger.info("Successfully stopped process %s (PID %d)", proc_name, pid)
    return ProcessStopResult(
        pid=pid,
        name=proc_name,
        success=True,
        terminated=True,
    )
