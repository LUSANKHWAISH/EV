import uuid
from typing import Optional
from .models import AgentTask, AgentAction

class CommandResolver:
    """
    Parses a raw text command into an AgentTask.
    Currently maps simple string prefixes to supported AgentActions.
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
        if lower_command.startswith("find port "):
            port_str = command[len("find port "):].strip()
            try:
                port = int(port_str)
            except ValueError:
                raise ValueError("find port requires a valid port number")
            return self._build_task(AgentAction.FIND_TCP_PORT, {"port": port})
            
        # LIST_DIRECTORY
        if lower_command.startswith("list dir "):
            path = command[len("list dir "):].strip()
            if not path:
                raise ValueError("list dir requires a path")
            return self._build_task(AgentAction.LIST_DIRECTORY, {"path": path})
            
        # GET_FILE_INFO
        if lower_command.startswith("file info "):
            path = command[len("file info "):].strip()
            if not path:
                raise ValueError("file info requires a path")
            return self._build_task(AgentAction.GET_FILE_INFO, {"path": path})
            
        # READ_TEXT_FILE
        if lower_command.startswith("read file "):
            path = command[len("read file "):].strip()
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
        
        # Unrecognized intent
        raise ValueError(f"Could not resolve command intent: '{command}'. Try prefixes like 'find process', 'list dir', etc.")
        
    def _build_task(self, action: AgentAction, parameters: dict) -> AgentTask:
        return AgentTask(
            task_id=str(uuid.uuid4())[:8],
            action=action,
            parameters=parameters
        )
