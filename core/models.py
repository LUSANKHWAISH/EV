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

# Verifier models
class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"

class VerificationType(str, Enum):
    PROCESS_EXISTS = "PROCESS_EXISTS"
    PROCESS_NOT_EXISTS = "PROCESS_NOT_EXISTS"
    TCP_PORT_EXISTS = "TCP_PORT_EXISTS"
    TCP_PORT_NOT_EXISTS = "TCP_PORT_NOT_EXISTS"
    FILE_EXISTS = "FILE_EXISTS"
    FILE_NOT_EXISTS = "FILE_NOT_EXISTS"
    DIRECTORY_EXISTS = "DIRECTORY_EXISTS"
    TEXT_CONTAINS = "TEXT_CONTAINS"
    TEXT_NOT_CONTAINS = "TEXT_NOT_CONTAINS"
    RESULT_NOT_EMPTY = "RESULT_NOT_EMPTY"
    RESULT_EMPTY = "RESULT_EMPTY"

class VerificationRequest(BaseModel):
    verification_type: VerificationType
    evidence: Any
    expected_text: Optional[str] = None
    # If needed, other parameters can be added here for specific verification types.

class VerificationResult(BaseModel):
    verification_type: VerificationType
    status: VerificationStatus
    success: bool  # True if VERIFIED, False otherwise (NOT_VERIFIED, INDETERMINATE, ERROR)
    message: str
    evidence_summary: Any
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None

# Backup models
class BackupStatus(str, Enum):
    CREATED = "CREATED"
    RESTORED = "RESTORED"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"

class FileBackupRecord(BaseModel):
    """
    Structured record of a file backup operation for restoration purposes.
    """
    original_path: str
    backup_path: str
    original_size_bytes: int
    backup_size_bytes: int
    sha256: str
    created_at: datetime = Field(default_factory=datetime.now)
    original_exists: bool
    success: bool
    message: str

class BackupResult(BaseModel):
    """
    Structured result of a backup operation.
    """
    status: BackupStatus
    success: bool
    executed: bool
    original_path: str
    backup_path: Optional[str] = None
    message: str
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float
    backup_record: Optional[FileBackupRecord] = None

class RestoreResult(BaseModel):
    """
    Structured result of a restore operation.
    """
    status: BackupStatus  # Reuse BackupStatus for consistency
    success: bool
    executed: bool
    original_path: str
    backup_path: str
    message: str
    error: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: float
    safety_backup_path: Optional[str] = None  # Path to safety backup of overwritten file


# Risk / Permission Engine models
class RiskLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PermissionDecision(str, Enum):
    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"
    INDETERMINATE = "INDETERMINATE"


class ActionCategory(str, Enum):
    READ_ONLY_OBSERVATION = "READ_ONLY_OBSERVATION"
    FILE_CREATE = "FILE_CREATE"
    FILE_MODIFY = "FILE_MODIFY"
    FILE_DELETE = "FILE_DELETE"
    FILE_RESTORE = "FILE_RESTORE"
    PROCESS_START = "PROCESS_START"
    PROCESS_STOP = "PROCESS_STOP"
    COMMAND_EXECUTION = "COMMAND_EXECUTION"
    NETWORK_CONFIGURATION = "NETWORK_CONFIGURATION"
    SERVICE_CONFIGURATION = "SERVICE_CONFIGURATION"
    REGISTRY_MODIFICATION = "REGISTRY_MODIFICATION"
    SOFTWARE_INSTALL = "SOFTWARE_INSTALL"
    SOFTWARE_UNINSTALL = "SOFTWARE_UNINSTALL"
    SYSTEM_POWER = "SYSTEM_POWER"
    SECURITY_CONFIGURATION = "SECURITY_CONFIGURATION"
    CREDENTIAL_ACCESS = "CREDENTIAL_ACCESS"
    UNKNOWN = "UNKNOWN"


class RiskAssessmentRequest(BaseModel):
    """
    Structured request for risk assessment of a proposed action.
    """
    action_category: ActionCategory
    target: Optional[str] = None
    description: Optional[str] = None
    has_backup: bool = False
    reversible: bool = False
    requires_elevation: bool = False
    affects_system: bool = False
    affects_security: bool = False
    user_approved: bool = False


class RiskAssessmentResult(BaseModel):
    """
    Structured result of a risk assessment.
    """
    action_category: ActionCategory
    risk_level: RiskLevel
    decision: PermissionDecision
    allowed: bool
    requires_approval: bool
    reason: str
    policy_rule: str
    evaluated_at: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None