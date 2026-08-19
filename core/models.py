from pydantic import BaseModel
from datetime import datetime
from typing import Optional

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
