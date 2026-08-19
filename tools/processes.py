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
