from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, List
from enum import Enum

class PowerShellResult(BaseModel):
    """
    Structured result of a PowerShell command execution.
    """
    command: str
    stdout: str
    stderr: str
    exit_code: Optional[int] = None
    success: bool
    executed: bool
    timed_out: bool
    started_at: datetime
    finished_at: datetime
    duration_seconds: float

class ProcessInfo(BaseModel):
    """
    Structured information about a Windows process.
    """
    pid: int
    name: str
    executable_path: Optional[str] = None
    status: Optional[str] = None

class TcpConnectionInfo(BaseModel):
    """
    Structured information about a TCP connection.
    """
    local_address: str
    local_port: int
    remote_address: Optional[str] = None
    remote_port: Optional[int] = None
    state: Optional[str] = None
    owning_pid: Optional[int] = None
    process_name: Optional[str] = None

class FileInfo(BaseModel):
    """
    Structured information about a file or directory.
    """
    path: str
    name: str
    exists: bool
    is_file: bool
    is_directory: bool
    size_bytes: Optional[int] = None
    modified_at: Optional[datetime] = None
    extension: Optional[str] = None

class TextReadResult(BaseModel):
    """
    Structured result of reading a text file.
    """
    path: str
    success: bool
    content: str
    encoding: Optional[str] = None
    truncated: bool
    size_bytes: Optional[int] = None
    error: Optional[str] = None

# Agent orchestration models
class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class AgentAction(str, Enum):
    FIND_PROCESS = "FIND_PROCESS"
    FIND_TCP_PORT = "FIND_TCP_PORT"
    GET_FILE_INFO = "GET_FILE_INFO"
    LIST_DIRECTORY = "LIST_DIRECTORY"
    READ_TEXT_FILE = "READ_TEXT_FILE"
    FIND_FILES = "FIND_FILES"
    SEARCH_TEXT = "SEARCH_TEXT"

class AgentTask(BaseModel):
    task_id: str
    action: AgentAction
    parameters: dict
    created_at: datetime = Field(default_factory=datetime.now)

class AgentStepResult(BaseModel):
    action: AgentAction
    success: bool
    started_at: datetime
    finished_at: datetime
    duration_seconds: float
    result: Optional[Any] = None
    error: Optional[str] = None

class AgentRunResult(BaseModel):
    task_id: str
    status: AgentStatus
    step: Optional[AgentStepResult] = None
    error: Optional[str] = None
