import subprocess
import json
import logging
from typing import List, Optional, Dict
from core.models import TcpConnectionInfo
from tools.powershell import run_powershell
from tools.processes import list_processes

logger = logging.getLogger("ev.network")

def list_tcp_connections() -> List[TcpConnectionInfo]:
    """
    List all TCP connections using PowerShell and return structured TcpConnectionInfo.
    """
    # PowerShell command to get TCP connections as JSON, with State explicitly converted to string
    ps_command = """
    Get-NetTCPConnection | Select-Object LocalAddress, LocalPort, RemoteAddress, RemotePort, 
        @{Name='State';Expression={$_.State.ToString()}}, OwningProcess | ConvertTo-Json -Depth 1
    """
    result = run_powershell(ps_command)
    connections = []
    if not result.success:
        logger.error("Failed to list TCP connections: %s", result.stderr)
        return connections
    try:
        data = json.loads(result.stdout)
        # Ensure data is a list
        if isinstance(data, dict):
            data = [data]
        # Build a map of PID to process name for enrichment
        process_map: Dict[int, str] = {}
        try:
            processes = list_processes()
            for p in processes:
                if p.pid is not None:
                    process_map[p.pid] = p.name
        except Exception as e:
            logger.warning("Could not enrich TCP connections with process names: %s", e)
        # Process each connection
        for item in data:
            try:
                local_addr = item.get('LocalAddress')
                local_port = item.get('LocalPort')
                remote_addr = item.get('RemoteAddress')
                remote_port = item.get('RemotePort')
                state = item.get('State')
                owning_pid = item.get('OwningProcess')
                # Get process name from map
                process_name = None
                if owning_pid is not None:
                    process_name = process_map.get(int(owning_pid))
                connections.append(TcpConnectionInfo(
                    local_address=str(local_addr) if local_addr is not None else '',
                    local_port=int(local_port) if local_port is not None else 0,
                    remote_address=str(remote_addr) if remote_addr is not None else None,
                    remote_port=int(remote_port) if remote_port is not None else None,
                    state=str(state) if state is not None else None,
                    owning_pid=int(owning_pid) if owning_pid is not None else None,
                    process_name=process_name
                ))
            except (ValueError, TypeError) as e:
                logger.warning("Skipping malformed TCP connection record: %s. Data: %s", e, item)
                continue
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("Error parsing TCP connections: %s", e)
    logger.info("Listed %d TCP connections", len(connections))
    return connections

def find_tcp_port(port: int) -> List[TcpConnectionInfo]:
    """
    Find TCP connections by local port.
    """
    if not (1 <= port <= 65535):
        raise ValueError("Port must be in the range 1..65535")
    all_connections = list_tcp_connections()
    matches = [c for c in all_connections if c.local_port == port]
    logger.info("Found %d TCP connections on local port %d", len(matches), port)
    return matches
