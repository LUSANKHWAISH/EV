import uuid
from typing import Optional
from .models import AgentTask, AgentAction, VerificationType

class CommandResolver:
    """
    Parses a raw text command into an AgentTask.
    Maps string prefixes to supported AgentActions and VerificationTypes.
    """
    def resolve(self, command: str) -> AgentTask:
        command = command.strip()
        if not command:
            raise ValueError("Command cannot be empty")
            
        lower_command = command.lower()
        
        # FIND_PROCESS
        if lower_command.startswith("find process ") or lower_command == "find process":
            name = command[len("find process"):].strip()
            if not name:
                raise ValueError("find process requires a process name")
            return self._build_task(AgentAction.FIND_PROCESS, {"name": name})
            
        # FIND_TCP_PORT
        if lower_command.startswith("find port ") or lower_command == "find port":
            port_str = command[len("find port"):].strip()
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError("find port requires a valid port number")
            if port < 1 or port > 65535:
                raise ValueError("find port requires a port between 1 and 65535")
            return self._build_task(AgentAction.FIND_TCP_PORT, {"port": port})
            
        # FIND_SERVICE
        if lower_command.startswith("find service ") or lower_command == "find service":
            name = command[len("find service"):].strip()
            if not name:
                raise ValueError("find service requires a service name")
            return self._build_task(AgentAction.FIND_SERVICE, {"name": name})

        # VERIFY_PROCESS (PROCESS_EXISTS)
        if lower_command.startswith("verify process ") or lower_command == "verify process":
            name = command[len("verify process"):].strip()
            if not name:
                raise ValueError("verify process requires a process name")
            return self._build_task(
                AgentAction.FIND_PROCESS,
                {
                    "name": name,
                    "verification_type": VerificationType.PROCESS_EXISTS.value,
                },
                verification_type=VerificationType.PROCESS_EXISTS,
            )

        # VERIFY_TCP_PORT (TCP_PORT_EXISTS)
        if lower_command.startswith("verify port ") or lower_command == "verify port":
            port_str = command[len("verify port"):].strip()
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError("verify port requires a valid port number")
            if port < 1 or port > 65535:
                raise ValueError("verify port requires a port between 1 and 65535")
            return self._build_task(
                AgentAction.FIND_TCP_PORT,
                {
                    "port": port,
                    "verification_type": VerificationType.TCP_PORT_EXISTS.value,
                },
                verification_type=VerificationType.TCP_PORT_EXISTS,
            )

        # VERIFY_FILE (FILE_EXISTS)
        if lower_command.startswith("verify file ") or lower_command == "verify file":
            path = command[len("verify file"):].strip()
            if not path:
                raise ValueError("verify file requires a path")
            return self._build_task(
                AgentAction.GET_FILE_INFO,
                {
                    "path": path,
                    "verification_type": VerificationType.FILE_EXISTS.value,
                },
                verification_type=VerificationType.FILE_EXISTS,
            )

        # VERIFY_DIRECTORY (DIRECTORY_EXISTS)
        if lower_command.startswith("verify dir ") or lower_command == "verify dir":
            path = command[len("verify dir"):].strip()
            if not path:
                raise ValueError("verify dir requires a path")
            return self._build_task(
                AgentAction.GET_FILE_INFO,
                {
                    "path": path,
                    "verification_type": VerificationType.DIRECTORY_EXISTS.value,
                },
                verification_type=VerificationType.DIRECTORY_EXISTS,
            )

        # VERIFY_SERVICE (SERVICE_RUNNING)
        if lower_command.startswith("verify service ") or lower_command == "verify service":
            name = command[len("verify service"):].strip()
            if not name:
                raise ValueError("verify service requires a service name")
            return self._build_task(
                AgentAction.FIND_SERVICE,
                {
                    "name": name,
                    "verification_type": VerificationType.SERVICE_RUNNING.value,
                },
                verification_type=VerificationType.SERVICE_RUNNING,
            )

        # LIST_DIRECTORY
        if lower_command.startswith("list dir ") or lower_command == "list dir":
            path = command[len("list dir"):].strip()
            if not path:
                raise ValueError("list dir requires a path")
            return self._build_task(AgentAction.LIST_DIRECTORY, {"path": path})
            
        # GET_FILE_INFO
        if lower_command.startswith("file info ") or lower_command == "file info":
            path = command[len("file info"):].strip()
            if not path:
                raise ValueError("file info requires a path")
            return self._build_task(AgentAction.GET_FILE_INFO, {"path": path})
            
        # READ_TEXT_FILE
        if lower_command.startswith("read file ") or lower_command == "read file":
            path = command[len("read file"):].strip()
            if not path:
                raise ValueError("read file requires a path")
            return self._build_task(AgentAction.READ_TEXT_FILE, {"path": path})

        # SEARCH_TEXT
        if lower_command.startswith("search text "):
            # Format: "search text 'query' in path" or just simple parsing
            # For simplicity, we split on " in "
            parts = command[len("search text "):].split(" in ", 1)
            if len(parts) == 2:
                text = parts[0].strip(" '\"")
                root = parts[1].strip()
                return self._build_task(AgentAction.SEARCH_TEXT, {"text": text, "root_or_file": root})
            else:
                raise ValueError("search text requires format: search text 'query' in path")
                
        # FIND_FILES
        if lower_command.startswith("find files "):
            # Format: "find files 'pattern' in path"
            parts = command[len("find files "):].split(" in ", 1)
            if len(parts) == 2:
                pattern = parts[0].strip(" '\"")
                root = parts[1].strip()
                return self._build_task(AgentAction.FIND_FILES, {"pattern": pattern, "root": root})
            else:
                raise ValueError("find files requires format: find files 'pattern' in path")

        # WRITE_FILE
        if lower_command.startswith("write file ") or lower_command == "write file":
            rest = command[len("write file"):].strip()
            if not rest:
                raise ValueError("write file requires a path and content")

            if rest.startswith('"'):
                end_quote = rest.find('"', 1)
                if end_quote == -1:
                    raise ValueError("write file has unmatched double quotes in path")
                path = rest[1:end_quote].strip()
                content = rest[end_quote + 1:].lstrip()
            elif rest.startswith("'"):
                end_quote = rest.find("'", 1)
                if end_quote == -1:
                    raise ValueError("write file has unmatched single quotes in path")
                path = rest[1:end_quote].strip()
                content = rest[end_quote + 1:].lstrip()
            else:
                parts = rest.split(None, 1)
                if len(parts) < 2:
                    raise ValueError("write file requires both path and content")
                path = parts[0].strip()
                content = parts[1]

            if not path:
                raise ValueError("write file requires a non-empty path")
            if not content:
                raise ValueError("write file requires non-empty content")

            return self._build_task(AgentAction.WRITE_FILE, {"path": path, "content": content})

        # DELETE_FILE
        if lower_command.startswith("delete file ") or lower_command == "delete file":
            path = command[len("delete file"):].strip().strip('"').strip("'")
            if not path:
                raise ValueError("delete file requires a path")
            return self._build_task(AgentAction.DELETE_FILE, {"path": path})

        # STOP_PROCESS
        if lower_command.startswith("stop process ") or lower_command == "stop process":
            raw_pid = command[len("stop process"):].strip()
            if not raw_pid:
                raise ValueError("stop process requires a PID")
            try:
                pid = int(raw_pid)
            except ValueError:
                raise ValueError(f"stop process requires an integer PID, got '{raw_pid}'")
            if pid <= 0:
                raise ValueError("stop process requires a positive integer PID")
            return self._build_task(
                AgentAction.STOP_PROCESS,
                {"pid": pid},
                verification_type=VerificationType.PROCESS_NOT_EXISTS,
            )

        # RESTART_SERVICE
        if lower_command.startswith("restart service ") or lower_command == "restart service":
            name = command[len("restart service"):].strip().strip('"').strip("'")
            if not name:
                raise ValueError("restart service requires a service name")
            return self._build_task(
                AgentAction.RESTART_SERVICE,
                {"name": name},
                verification_type=VerificationType.RESULT_NOT_EMPTY,
            )

        # FLUSH_DNS
        if lower_command.startswith("flush dns") or lower_command == "flush-dns":
            hostname = command[len("flush dns"):].strip().strip('"').strip("'")
            params = {}
            if hostname:
                params["hostname"] = hostname
            return self._build_task(
                AgentAction.FLUSH_DNS,
                params,
                verification_type=VerificationType.RESULT_NOT_EMPTY,
            )

        # Unrecognized intent
        raise ValueError(f"Could not resolve command intent: '{command}'. Try prefixes like 'find process', 'stop process', 'restart service', 'flush dns', 'list dir', etc.")
        
    def _build_task(
        self,
        action: AgentAction,
        parameters: dict,
        verification_type: Optional[VerificationType] = None,
    ) -> AgentTask:
        return AgentTask(
            task_id=str(uuid.uuid4())[:8],
            action=action,
            parameters=parameters,
            verification_type=verification_type,
        )
