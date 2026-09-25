from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional, Any, List, Dict
from enum import Enum

SENSITIVE_METADATA_KEYS = {
    "password", "passwd", "pwd", "secret", "token", "access_token",
    "refresh_token", "api_key", "apikey", "credential",
    "credentials", "authorization", "auth", "private_key", "raw_audio",
    "audio_data", "audio_buffer", "bearer_token"
}

def sanitize_metadata(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sanitize metadata to guarantee no secrets, credentials, or raw audio are stored.
    """
    if not meta or not isinstance(meta, dict):
        return {}
    sanitized: Dict[str, Any] = {}
    for k, v in meta.items():
        k_lower = str(k).lower()
        is_sensitive = (
            k_lower in SENSITIVE_METADATA_KEYS
            or any(k_lower.startswith(s + "_") or k_lower.endswith("_" + s) for s in ("password", "secret", "token", "auth", "credential"))
            or any(s in k_lower for s in ("api_key", "apikey", "bearer", "access_token", "refresh_token", "raw_audio", "audio_buffer", "audio_data", "private_key"))
        )
        if is_sensitive:
            if "audio" in k_lower:
                sanitized[k] = "[REDACTED_AUDIO_BUFFER]"
            else:
                sanitized[k] = "[REDACTED]"
        elif isinstance(v, (bytes, bytearray)):
            sanitized[k] = "[REDACTED_AUDIO_BUFFER]" if "audio" in k_lower else f"<{len(v)} bytes binary omitted>"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_metadata(v)
        elif isinstance(v, list):
            sanitized[k] = [
                sanitize_metadata(item) if isinstance(item, dict) else (
                    "[REDACTED_AUDIO_BUFFER]" if "audio" in k_lower else (
                        f"<{len(item)} bytes binary omitted>" if isinstance(item, (bytes, bytearray)) else item
                    )
                )
                for item in v
            ]
        else:
            sanitized[k] = v
    return sanitized


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

class ServiceInfo(BaseModel):
    """
    Structured information about a Windows service.
    """
    name: str
    display_name: Optional[str] = None
    status: Optional[str] = None
    start_type: Optional[str] = None


class FileWriteResult(BaseModel):
    """
    Structured result of writing a file.
    """
    path: str
    success: bool
    bytes_written: int = 0
    created: bool = False
    sha256: Optional[str] = None
    error: Optional[str] = None


class FileDeleteResult(BaseModel):
    """
    Structured result of deleting a file.
    """
    path: str
    success: bool
    deleted: bool = False
    error: Optional[str] = None


class ProcessStopResult(BaseModel):
    """
    Structured result of stopping a process.
    """
    pid: int
    name: Optional[str] = None
    success: bool
    terminated: bool = False
    error: Optional[str] = None


class ServiceRestartResult(BaseModel):
    """
    Structured result of restarting a Windows service.
    """
    name: str
    prior_status: Optional[str] = None
    current_status: Optional[str] = None
    success: bool
    admin_required: bool = False
    error: Optional[str] = None


class DnsFlushResult(BaseModel):
    """
    Structured result of flushing DNS cache.
    """
    success: bool
    flushed: bool = False
    target_hostname: Optional[str] = None
    resolved: Optional[bool] = None
    verification_status: Optional[str] = None
    error: Optional[str] = None


# Execution and Verifier models
class ExecutionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"
    # Backward compatibility aliases
    NOT_VERIFIED = "NOT_VERIFIED"
    INDETERMINATE = "INDETERMINATE"
    ERROR = "ERROR"

    def __eq__(self, other: Any) -> bool:
        if super().__eq__(other):
            return True
        if isinstance(other, (VerificationStatus, str)):
            val = other.value if isinstance(other, VerificationStatus) else str(other)
            if self.value in ("FAILED", "NOT_VERIFIED", "ERROR") and val in ("FAILED", "NOT_VERIFIED", "ERROR"):
                return True
            if self.value in ("UNKNOWN", "INDETERMINATE") and val in ("UNKNOWN", "INDETERMINATE"):
                return True
        return False

    def __hash__(self) -> int:
        return hash(self.value)

class VerificationType(str, Enum):
    PROCESS_EXISTS = "PROCESS_EXISTS"
    PROCESS_NOT_EXISTS = "PROCESS_NOT_EXISTS"
    PROCESS_IDENTITY_VALID = "PROCESS_IDENTITY_VALID"
    TCP_PORT_EXISTS = "TCP_PORT_EXISTS"
    TCP_PORT_NOT_EXISTS = "TCP_PORT_NOT_EXISTS"
    FILE_EXISTS = "FILE_EXISTS"
    FILE_NOT_EXISTS = "FILE_NOT_EXISTS"
    FILE_CONTENT_MATCH = "FILE_CONTENT_MATCH"
    FILE_HASH_MATCH = "FILE_HASH_MATCH"
    DIRECTORY_EXISTS = "DIRECTORY_EXISTS"
    TEXT_CONTAINS = "TEXT_CONTAINS"
    TEXT_NOT_CONTAINS = "TEXT_NOT_CONTAINS"
    READ_CONTENT_VALID = "READ_CONTENT_VALID"
    RESULT_NOT_EMPTY = "RESULT_NOT_EMPTY"
    RESULT_EMPTY = "RESULT_EMPTY"
    SERVICE_RUNNING = "SERVICE_RUNNING"
    SERVICE_STOPPED = "SERVICE_STOPPED"
    NONE = "NONE"

class VerificationRequest(BaseModel):
    verification_type: VerificationType
    evidence: Any
    expected_text: Optional[str] = None
    expected_sha256: Optional[str] = None
    expected_bytes: Optional[int] = None
    expected_content: Optional[str] = None
    expected_service_status: Optional[str] = None
    # If needed, other parameters can be added here for specific verification types.

class VerificationResult(BaseModel):
    verification_type: Optional[VerificationType] = None
    status: VerificationStatus
    success: bool = True  # True if VERIFIED or NOT_APPLICABLE, False otherwise
    message: str = ""
    evidence_summary: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    error: Optional[str] = None
    observed_state: Optional[Dict[str, Any]] = None

    def __init__(self, **data: Any):
        if "reason" in data and "message" not in data:
            data["message"] = data["reason"]
        if "success" not in data and "status" in data:
            st = data["status"]
            data["success"] = st in (VerificationStatus.VERIFIED, VerificationStatus.NOT_APPLICABLE)
        super().__init__(**data)

    @property
    def reason(self) -> str:
        return self.message or (self.error or "")

    @property
    def is_verified(self) -> bool:
        return self.status in (VerificationStatus.VERIFIED, VerificationStatus.NOT_APPLICABLE)

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
    FIND_SERVICE = "FIND_SERVICE"
    WRITE_FILE = "WRITE_FILE"
    DELETE_FILE = "DELETE_FILE"
    STOP_PROCESS = "STOP_PROCESS"
    RESTART_SERVICE = "RESTART_SERVICE"
    FLUSH_DNS = "FLUSH_DNS"

class ExecutionResult(BaseModel):
    """
    Structured execution result tracking the lifecycle of an action.
    """
    action_id: str
    step_id: Optional[str] = None
    action_type: Any
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime = Field(default_factory=datetime.now)
    duration: float = 0.0
    status: ExecutionStatus = ExecutionStatus.EXECUTING
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    retry_allowed: bool = True
    verification_status: Optional[VerificationStatus] = None

    @field_validator("metadata", mode="before")
    @classmethod
    def _sanitize(cls, val: Any) -> Dict[str, Any]:
        return sanitize_metadata(val if isinstance(val, dict) else {})

class AgentTask(BaseModel):
    task_id: str
    action: AgentAction
    parameters: dict
    verification_type: Optional[VerificationType] = None
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
    execution: Optional[ExecutionResult] = None
    verification: Optional[VerificationResult] = None

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


# Event / State Bus models
class EVState(str, Enum):
    IDLE = "IDLE"
    VERIFYING_WAKE = "VERIFYING_WAKE"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    PROCESSING = "PROCESSING"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERING = "RECOVERING"
    SPEAKING = "SPEAKING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class EVEventType(str, Enum):
    STATE_CHANGED = "STATE_CHANGED"
    VOICE_STATE_CHANGED = "VOICE_STATE_CHANGED"
    VOICE_TELEMETRY = "VOICE_TELEMETRY"
    STATUS = "STATUS"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    ACTION_STARTED = "ACTION_STARTED"
    ACTION_COMPLETED = "ACTION_COMPLETED"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    RECOVERY_RESULT = "RECOVERY_RESULT"
    ERROR = "ERROR"
    SYSTEM_OBSERVATION = "SYSTEM_OBSERVATION"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    SYSTEM_ALERT_RECOVERED = "SYSTEM_ALERT_RECOVERED"
    EXPERIENCE_MODE_CHANGED = "EXPERIENCE_MODE_CHANGED"
    STYLE_PRESET_CHANGED = "STYLE_PRESET_CHANGED"
    AWARENESS_EVENT = "AWARENESS_EVENT"
    AWARENESS_RESOLVED = "AWARENESS_RESOLVED"
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_VALIDATED = "PLAN_VALIDATED"
    PLAN_STARTED = "PLAN_STARTED"
    PLAN_COMPLETED = "PLAN_COMPLETED"
    PLAN_FAILED = "PLAN_FAILED"
    PLAN_CANCELLED = "PLAN_CANCELLED"
    PLAN_ROLLED_BACK = "PLAN_ROLLED_BACK"
    ACTION_ACCEPTED = "ACTION_ACCEPTED"
    ACTION_VERIFYING = "ACTION_VERIFYING"
    ACTION_UNKNOWN = "ACTION_UNKNOWN"
    DIAGNOSIS_CREATED = "DIAGNOSIS_CREATED"
    DIAGNOSIS_UPDATED = "DIAGNOSIS_UPDATED"
    RECOVERY_PROPOSED = "RECOVERY_PROPOSED"
    RECOVERY_ACCEPTED = "RECOVERY_ACCEPTED"
    RECOVERY_REJECTED = "RECOVERY_REJECTED"


class EVEventSeverity(str, Enum):
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


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

# Persistent task history models
class TaskHistoryEventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    BACKUP_RESULT = "BACKUP_RESULT"
    RESTORE_RESULT = "RESTORE_RESULT"
    RECOVERY_RESULT = "RECOVERY_RESULT"
    NOTE = "NOTE"
    DIAGNOSIS_RECORD = "DIAGNOSIS_RECORD"
    RECOVERY_PROPOSAL = "RECOVERY_PROPOSAL"


class TaskHistoryRecord(BaseModel):
    task_id: str
    action: AgentAction
    parameters: dict
    created_at: datetime
    status: AgentStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    success: Optional[bool] = None
    result_summary: Optional[dict] = None
    error: Optional[str] = None
    updated_at: datetime


class TaskHistoryEventRecord(BaseModel):
    event_id: int
    task_id: str
    event_type: TaskHistoryEventType
    payload: dict
    created_at: datetime


# Contextual Diagnosis & Recovery Intelligence Models (Task 017)
class ActionReversibility(str, Enum):
    REVERSIBLE = "REVERSIBLE"
    NON_REVERSIBLE = "NON_REVERSIBLE"


class DiagnosisCategory(str, Enum):
    RESOURCE_PRESSURE = "RESOURCE_PRESSURE"
    PROCESS_FAILURE = "PROCESS_FAILURE"
    FILE_FAILURE = "FILE_FAILURE"
    SERVICE_FAILURE = "SERVICE_FAILURE"
    NETWORK_FAILURE = "NETWORK_FAILURE"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"
    TIMEOUT = "TIMEOUT"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class DiagnosisStatus(str, Enum):
    DETECTED = "DETECTED"
    ANALYZING = "ANALYZING"
    CONFIRMED = "CONFIRMED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class EpistemicType(str, Enum):
    FACT = "FACT"
    INFERENCE = "INFERENCE"
    SPECULATION = "SPECULATION"


class EvidenceType(str, Enum):
    METRIC = "METRIC"
    OBSERVATION = "OBSERVATION"
    EXECUTION_RESULT = "EXECUTION_RESULT"
    VERIFICATION_RESULT = "VERIFICATION_RESULT"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    PROCESS_STATE = "PROCESS_STATE"
    SERVICE_STATE = "SERVICE_STATE"
    FILE_STATE = "FILE_STATE"
    NETWORK_STATE = "NETWORK_STATE"


class EvidenceItem(BaseModel):
    """
    Authoritative, structured evidence item supporting a diagnosis.
    Strictly differentiates between measured FACTS, deterministic INFERENCES, and untrusted SPECULATION.
    """
    evidence_id: str
    evidence_type: EvidenceType
    description: str
    source: str
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence: float = 1.0
    epistemic_type: EpistemicType = EpistemicType.FACT
    data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("data", mode="before")
    @classmethod
    def _sanitize_data(cls, val: Any) -> Dict[str, Any]:
        return sanitize_metadata(val if isinstance(val, dict) else {})


class Hypothesis(BaseModel):
    """
    Root-cause hypothesis explaining an observed system or action failure condition.
    Hypotheses are either deterministic INFERENCES or untrusted SPECULATION. They are NEVER facts.
    """
    hypothesis_id: str
    description: str
    confidence: float = 1.0  # 0.0 to 1.0
    epistemic_type: EpistemicType = EpistemicType.INFERENCE
    supporting_evidence_ids: List[str] = Field(default_factory=list)
    is_primary: bool = False

    @field_validator("epistemic_type")
    @classmethod
    def _validate_not_fact(cls, val: EpistemicType) -> EpistemicType:
        if val == EpistemicType.FACT:
            raise ValueError("Hypotheses cannot be classified as FACT; they must be INFERENCE or SPECULATION")
        return val


class Diagnosis(BaseModel):
    """
    Structured, evidence-backed diagnostic finding representing a system or task failure.
    Contains strictly audited evidence, ranked probable causes, affected resources, and severity.
    """
    diagnosis_id: str
    condition_id: str
    category: DiagnosisCategory
    severity: EVEventSeverity = EVEventSeverity.WARNING
    confidence: float = 1.0
    evidence: List[EvidenceItem] = Field(default_factory=list)
    probable_causes: List[Hypothesis] = Field(default_factory=list)
    affected_resources: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(default_factory=datetime.now)
    status: DiagnosisStatus = DiagnosisStatus.DETECTED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def _sanitize_meta(cls, val: Any) -> Dict[str, Any]:
        return sanitize_metadata(val if isinstance(val, dict) else {})


class FailureClassification(str, Enum):
    """Deterministic taxonomy of execution and verification failure modes."""
    EXECUTION_FAILED = "EXECUTION_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    TIMEOUT = "TIMEOUT"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_UNAVAILABLE = "RESOURCE_UNAVAILABLE"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    CANCELLED = "CANCELLED"


class RecoveryStage(str, Enum):
    """Safe-first ranking stages for recovery options (lowest to highest impact)."""
    OBSERVE = "OBSERVE"                             # Safe rank 1: Non-intrusive observation
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"           # Safe rank 2: Query additional system telemetry
    EXPLAIN = "EXPLAIN"                             # Safe rank 3: Inform and explain condition
    NON_MUTATING_ACTION = "NON_MUTATING_ACTION"     # Safe rank 4: Safe read-only action
    REVERSIBLE_MUTATION = "REVERSIBLE_MUTATION"     # Safe rank 5: Action with backup/compensation
    IRREVERSIBLE_MUTATION = "IRREVERSIBLE_MUTATION" # Safe rank 6: Non-reversible action


class RecoveryOption(BaseModel):
    """
    Structured, proposal-only recovery option generated for a Diagnosis.
    Mutating options strictly require human approval and transaction wrapping.
    """
    option_id: str
    diagnosis_id: str
    description: str
    stage: RecoveryStage
    safe_order_rank: int
    action: Optional[AgentAction] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    expected_effect: str = ""
    risk_level: RiskLevel = RiskLevel.NONE
    reversible: bool = True
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    verification_type: Optional[VerificationType] = None
    confidence: float = 1.0
    requires_approval: bool = False
    plan_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", "parameters", mode="before")
    @classmethod
    def _sanitize_dict(cls, val: Any) -> Dict[str, Any]:
        return sanitize_metadata(val if isinstance(val, dict) else {})


