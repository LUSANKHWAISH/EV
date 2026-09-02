import json
import logging
from typing import List, Optional
from core.models import ServiceInfo
from tools.powershell import run_powershell

logger = logging.getLogger("ev.services")


def list_services() -> List[ServiceInfo]:
    """
    List Windows services using PowerShell and return structured ServiceInfo models.
    """
    ps_command = """
    Get-Service | Select-Object Name, DisplayName, @{Name='Status';Expression={$_.Status.ToString()}}, @{Name='StartType';Expression={$_.StartType.ToString()}} | ConvertTo-Json -Depth 1
    """
    result = run_powershell(ps_command)
    services: List[ServiceInfo] = []

    if not result.success:
        logger.error("Failed to list services: %s", result.stderr)
        return services

    if not result.stdout or not result.stdout.strip():
        logger.info("PowerShell returned empty output for services")
        return services

    try:
        data = json.loads(result.stdout)
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list):
            logger.warning(
                "Unexpected JSON format from Get-Service: expected list or dict, got %s",
                type(data),
            )
            return services

        for item in data:
            if not isinstance(item, dict):
                continue
            name = item.get("Name")
            display_name = item.get("DisplayName")
            status = item.get("Status")
            start_type = item.get("StartType")

            if name is not None and str(name).strip():
                services.append(
                    ServiceInfo(
                        name=str(name),
                        display_name=str(display_name) if display_name is not None else None,
                        status=str(status) if status is not None else None,
                        start_type=str(start_type) if start_type is not None else None,
                    )
                )
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.error("Error parsing service list: %s", e)

    logger.info("Listed %d services", len(services))
    return services


def find_services(name: str) -> List[ServiceInfo]:
    """
    Find services by service name or display name (case-insensitive).
    """
    if not name or not isinstance(name, str) or not name.strip():
        return []

    all_services = list_services()
    name_lower = name.strip().lower()
    matches = [
        s
        for s in all_services
        if s.name.lower() == name_lower
        or (s.display_name and s.display_name.lower() == name_lower)
    ]
    logger.info("Found %d services matching '%s'", len(matches), name)
    return matches


SYSTEM_CRITICAL_SERVICES = {
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


def restart_service(name: str, allowed_services: Optional[set] = None) -> "ServiceRestartResult":
    """
    Safely restart or start an eligible Windows service.
    Inspects prior state, checks privilege boundaries, and verifies post-restart state.
    """
    from core.models import ServiceRestartResult

    if not name or not isinstance(name, str) or not name.strip():
        return ServiceRestartResult(
            name=name if isinstance(name, str) else "unknown",
            success=False,
            error="Service name must be a non-empty string",
        )

    clean_name = name.strip()
    name_lower = clean_name.lower()

    # Find service and record prior status
    matches = find_services(clean_name)
    if not matches:
        return ServiceRestartResult(
            name=clean_name,
            success=False,
            error=f"Service '{clean_name}' not found",
        )

    target_service = matches[0]
    canonical_name = target_service.name
    prior_status = target_service.status or "Unknown"

    # Block system-critical services unless explicitly in allowed_services
    if canonical_name.lower() in SYSTEM_CRITICAL_SERVICES:
        if not allowed_services or canonical_name.lower() not in {s.lower() for s in allowed_services}:
            return ServiceRestartResult(
                name=canonical_name,
                prior_status=prior_status,
                current_status=prior_status,
                success=False,
                admin_required=True,
                error=f"ADMIN_REQUIRED: Service '{canonical_name}' is a protected system-critical service",
            )

    # Execute service restart via bounded PowerShell
    ps_cmd = f"Restart-Service -Name '{canonical_name}' -Force"
    result = run_powershell(ps_cmd)

    if not result.success:
        err_msg = result.stderr or f"Failed to restart service '{canonical_name}'"
        admin_req = False
        if any(w in err_msg for w in ("Access is denied", "UnauthorizedAccessException", "PermissionDenied", "Cannot open Service Control Manager")):
            admin_req = True
            err_msg = f"ADMIN_REQUIRED: Administrative privileges required to restart service '{canonical_name}'"
        return ServiceRestartResult(
            name=canonical_name,
            prior_status=prior_status,
            current_status=prior_status,
            success=False,
            admin_required=admin_req,
            error=err_msg,
        )

    # Inspect post-restart status to verify service reached Running state
    post_matches = find_services(canonical_name)
    current_status = post_matches[0].status if post_matches else "Unknown"

    if current_status.lower() != "running":
        return ServiceRestartResult(
            name=canonical_name,
            prior_status=prior_status,
            current_status=current_status,
            success=False,
            error=f"Service '{canonical_name}' restarted but current status is '{current_status}' (expected 'Running')",
        )

    logger.info("Successfully restarted service '%s' (prior status: %s, current status: %s)", canonical_name, prior_status, current_status)
    return ServiceRestartResult(
        name=canonical_name,
        prior_status=prior_status,
        current_status=current_status,
        success=True,
    )
