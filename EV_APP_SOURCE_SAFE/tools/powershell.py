import subprocess
import time
from datetime import datetime
from typing import Optional
from config.settings import settings
from core.logging_config import setup_logging
from core.models import PowerShellResult

logger = setup_logging("ev.powershell")

def run_powershell(command: str, timeout: Optional[int] = None) -> PowerShellResult:
    """
    Execute a PowerShell command and return a structured result.
    """
    # Determine timeout
    if timeout is None:
        timeout = settings.EV_MAX_COMMAND_TIMEOUT

    # Dry-run check
    if settings.EV_DRY_RUN:
        logger.info("PowerShell execution skipped (dry-run mode). Command: %s", command)
        return PowerShellResult(
            command=command,
            stdout="",
            stderr="",
            exit_code=0,
            success=False,
            executed=False,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.0,
        )

    # Prepare the command
    # Using powershell.exe with -NoProfile -NonInteractive -Command
    ps_command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]

    started_at = datetime.now()
    try:
        logger.info("PowerShell execution started. Command: %s", command)
        # We use subprocess.run with timeout and capture output
        completed = subprocess.run(
            ps_command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()

        # Determine success based on exit code
        success = (completed.returncode == 0)

        logger.info(
            "PowerShell execution completed. Exit code: %d, Duration: %.2f seconds",
            completed.returncode,
            duration,
        )

        return PowerShellResult(
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            exit_code=completed.returncode,
            success=success,
            executed=True,
            timed_out=False,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
    except subprocess.TimeoutExpired:
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        logger.warning(
            "PowerShell execution timed out after %d seconds. Command: %s",
            timeout,
            command,
        )
        # Note: On timeout, the process is still running? subprocess.run with timeout will kill it.
        # We return a result indicating timeout.
        return PowerShellResult(
            command=command,
            stdout="",  # We might have partial output, but subprocess.TimeoutExpired doesn't give it.
            stderr="",  # Similarly, we don't capture partial output on timeout.
            exit_code=-1,  # Indicate timeout with a non-zero exit code
            success=False,
            executed=True,
            timed_out=True,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
    except Exception as e:
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        logger.error(
            "PowerShell execution failed with exception: %s. Command: %s",
            e,
            command,
        )
        return PowerShellResult(
            command=command,
            stdout="",
            stderr=str(e),
            exit_code=-2,
            success=False,
            executed=True,
            timed_out=False,
            started_at=started_at,
            finished_at=finished_at,
            duration_seconds=duration,
        )
