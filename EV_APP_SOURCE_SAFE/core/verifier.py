"""
Minimal verifier engine for E.V.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import VerificationRequest, VerificationResult, VerificationStatus, VerificationType
from .models import (
    ProcessInfo,
    TcpConnectionInfo,
    FileInfo,
    TextReadResult,
    ServiceInfo,
    ServiceRestartResult,
    FileWriteResult,
    FileDeleteResult,
    ProcessStopResult,
)


class EVVerifier:
    """Deterministic verifier that operates on structured evidence."""

    def verify(self, request: VerificationRequest) -> VerificationResult:
        """
        Verify a condition based on the provided evidence.
        Returns a VerificationResult.
        """
        try:
            if request.verification_type == VerificationType.PROCESS_EXISTS:
                return self._verify_process_exists(request)
            elif request.verification_type == VerificationType.PROCESS_NOT_EXISTS:
                return self._verify_process_not_exists(request)
            elif request.verification_type == VerificationType.TCP_PORT_EXISTS:
                return self._verify_tcp_port_exists(request)
            elif request.verification_type == VerificationType.TCP_PORT_NOT_EXISTS:
                return self._verify_tcp_port_not_exists(request)
            elif request.verification_type == VerificationType.FILE_EXISTS:
                return self._verify_file_exists(request)
            elif request.verification_type == VerificationType.FILE_NOT_EXISTS:
                return self._verify_file_not_exists(request)
            elif request.verification_type == VerificationType.DIRECTORY_EXISTS:
                return self._verify_directory_exists(request)
            elif request.verification_type == VerificationType.TEXT_CONTAINS:
                return self._verify_text_contains(request)
            elif request.verification_type == VerificationType.TEXT_NOT_CONTAINS:
                return self._verify_text_not_contains(request)
            elif request.verification_type == VerificationType.RESULT_NOT_EMPTY:
                return self._verify_result_not_empty(request)
            elif request.verification_type == VerificationType.RESULT_EMPTY:
                return self._verify_result_empty(request)
            elif request.verification_type == VerificationType.PROCESS_IDENTITY_VALID:
                return self._verify_process_identity_valid(request)
            elif request.verification_type == VerificationType.FILE_CONTENT_MATCH:
                return self._verify_file_content_match(request)
            elif request.verification_type == VerificationType.FILE_HASH_MATCH:
                return self._verify_file_hash_match(request)
            elif request.verification_type == VerificationType.READ_CONTENT_VALID:
                return self._verify_read_content_valid(request)
            elif request.verification_type == VerificationType.SERVICE_RUNNING:
                return self._verify_service_running(request)
            elif request.verification_type == VerificationType.SERVICE_STOPPED:
                return self._verify_service_stopped(request)
            elif request.verification_type == VerificationType.NONE:
                return self._verify_none(request)
            else:
                # Should not happen due to enum, but keep for safety.
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.INDETERMINATE,
                    success=False,
                    message=f"Unsupported verification type: {request.verification_type}",
                    evidence_summary=request.evidence,
                    timestamp=datetime.now(),
                )
        except Exception as exc:  # pragma: no cover - defensive
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.ERROR,
                success=False,
                message=f"Unexpected internal verifier error: {exc}",
                evidence_summary=request.evidence,
                timestamp=datetime.now(),
                error=str(exc),
            )

    # -----------------------------------------------------------------
    # Helper methods for each verification type
    # -----------------------------------------------------------------
    def _verify_process_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, list):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a list of ProcessInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # All elements must be ProcessInfo
        if not all(isinstance(item, ProcessInfo) for item in evidence):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence list contains non-ProcessInfo items",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if len(evidence) > 0:
            status = VerificationStatus.VERIFIED
            success = True
            message = f"Found {len(evidence)} process(es)"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message="No processes found"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_process_not_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, list):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a list of ProcessInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # All elements must be ProcessInfo
        if not all(isinstance(item, ProcessInfo) for item in evidence):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence list contains non-ProcessInfo items",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if len(evidence) == 0:
            status = VerificationStatus.VERIFIED
            success = True
            message="No processes found (as expected)"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"Found {len(evidence)} process(es), but expected none"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_tcp_port_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, list):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a list of TcpConnectionInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # All elements must be TcpConnectionInfo
        if not all(isinstance(item, TcpConnectionInfo) for item in evidence):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence list contains non-TcpConnectionInfo items",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if len(evidence) > 0:
            status = VerificationStatus.VERIFIED
            success = True
            message = f"Found {len(evidence)} TCP connection(s)"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message="No TCP connections found"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_tcp_port_not_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, list):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a list of TcpConnectionInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # All elements must be TcpConnectionInfo
        if not all(isinstance(item, TcpConnectionInfo) for item in evidence):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence list contains non-TcpConnectionInfo items",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if len(evidence) == 0:
            status = VerificationStatus.VERIFIED
            success = True
            message="No TCP connections found (as expected)"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"Found {len(evidence)} TCP connection(s), but expected none"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_file_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, FileInfo):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a FileInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if evidence.exists and evidence.is_file:
            status = VerificationStatus.VERIFIED
            success = True
            message=f"File exists: {evidence.path}"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"File does not exist or is not a file: {evidence.path}"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_file_not_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, FileInfo):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a FileInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not evidence.exists:
            status = VerificationStatus.VERIFIED
            success = True
            message=f"File does not exist: {evidence.path}"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"File exists: {evidence.path}"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_directory_exists(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, FileInfo):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a FileInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if evidence.exists and evidence.is_directory:
            status = VerificationStatus.VERIFIED
            success = True
            message=f"Directory exists: {evidence.path}"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"Directory does not exist or is not a directory: {evidence.path}"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_text_contains(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        expected = request.expected_text
        if expected is None or not isinstance(expected, str):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Missing or invalid expected_text parameter",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not isinstance(evidence, TextReadResult):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a TextReadResult",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not evidence.success:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Failed to read text file",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if expected in evidence.content:
            status = VerificationStatus.VERIFIED
            success = True
            message=f"Text '{expected}' found in file"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"Text '{expected}' not found in file"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_text_not_contains(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        expected = request.expected_text
        if expected is None or not isinstance(expected, str):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Missing or invalid expected_text parameter",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not isinstance(evidence, TextReadResult):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Evidence is not a TextReadResult",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not evidence.success:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="Failed to read text file",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if expected not in evidence.content:
            status = VerificationStatus.VERIFIED
            success = True
            message=f"Text '{expected}' not found in file (as expected)"
        else:
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message=f"Text '{expected}' found in file, but expected absence"
        return VerificationResult(
            verification_type=request.verification_type,
            status=status,
            success=success,
            message=message,
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_result_not_empty(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        # Determine if evidence is meaningfully empty or non-empty.
        # None is indeterminate (no usable evidence).
        if evidence is None:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="No usable evidence provided",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # For strings, lists, dicts, sets, tuples we can check length.
        if isinstance(evidence, (str, list, dict, set, tuple)):
            if len(evidence) > 0:
                status = VerificationStatus.VERIFIED
                success = True
                message="Evidence is not empty"
            else:
                status = VerificationStatus.NOT_VERIFIED
                success = False
                message="Evidence is empty"
            return VerificationResult(
                verification_type=request.verification_type,
                status=status,
                success=success,
                message=message,
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # For known structured evidence types (ProcessInfo, TcpConnectionInfo, FileInfo, TextReadResult)
        # we consider them non-empty if they are not None (they are single objects).
        # However, a single ProcessInfo object is meaningful non-empty evidence for RESULT_NOT_EMPTY?
        # The spec: RESULT_NOT_EMPTY expects meaningful valid non-empty evidence.
        # A single structured object is non-empty.
        if isinstance(evidence, (ProcessInfo, TcpConnectionInfo, FileInfo, TextReadResult)):
            status = VerificationStatus.VERIFIED
            success = True
            message="Evidence is not empty (single structured object)"
            return VerificationResult(
                verification_type=request.verification_type,
                status=status,
                success=success,
                message=message,
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # Any other type is considered indeterminate because we cannot safely determine emptiness.
        return VerificationResult(
            verification_type=request.verification_type,
            status=VerificationStatus.INDETERMINATE,
            success=False,
            message="Unsupported evidence type for emptiness check",
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_result_empty(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        # Determine if evidence is meaningfully empty or non-empty.
        # None is indeterminate (no usable evidence).
        if evidence is None:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.INDETERMINATE,
                success=False,
                message="No usable evidence provided",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # For strings, lists, dicts, sets, tuples we can check length.
        if isinstance(evidence, (str, list, dict, set, tuple)):
            if len(evidence) == 0:
                status = VerificationStatus.VERIFIED
                success = True
                message="Evidence is empty"
            else:
                status = VerificationStatus.NOT_VERIFIED
                success = False
                message="Evidence is not empty"
            return VerificationResult(
                verification_type=request.verification_type,
                status=status,
                success=success,
                message=message,
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # For known structured evidence types (ProcessInfo, TcpConnectionInfo, FileInfo, TextReadResult)
        # we consider them non-empty if they are not None (they are single objects).
        # A single structured object is meaningful non-empty evidence, thus not empty.
        if isinstance(evidence, (ProcessInfo, TcpConnectionInfo, FileInfo, TextReadResult)):
            status = VerificationStatus.NOT_VERIFIED
            success = False
            message="Evidence is not empty (single structured object)"
            return VerificationResult(
                verification_type=request.verification_type,
                status=status,
                success=success,
                message=message,
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        # Any other type is considered indeterminate because we cannot safely determine emptiness.
        return VerificationResult(
            verification_type=request.verification_type,
            status=VerificationStatus.INDETERMINATE,
            success=False,
            message="Unsupported evidence type for emptiness check",
            evidence_summary=evidence,
            timestamp=datetime.now(),
        )

    def _verify_none(self, request: VerificationRequest) -> VerificationResult:
        return VerificationResult(
            verification_type=VerificationType.NONE,
            status=VerificationStatus.NOT_APPLICABLE,
            success=True,
            message="Verification not applicable for this action",
            evidence_summary=request.evidence,
            timestamp=datetime.now(),
        )

    def _verify_service_running(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        status_val = None
        service_name = "unknown"
        if isinstance(evidence, ServiceInfo):
            status_val = evidence.status
            service_name = evidence.name
        elif isinstance(evidence, ServiceRestartResult):
            status_val = evidence.current_status
            service_name = evidence.name
        elif isinstance(evidence, list) and len(evidence) > 0 and isinstance(evidence[0], ServiceInfo):
            status_val = evidence[0].status
            service_name = evidence[0].name
        elif isinstance(evidence, dict):
            status_val = evidence.get("status") or evidence.get("current_status")
            service_name = evidence.get("name", "unknown")

        if status_val is None:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message=f"Unable to determine service status for '{service_name}' from evidence",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        if str(status_val).strip().lower() == "running":
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.VERIFIED,
                success=True,
                message=f"Service '{service_name}' is Running",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"service": service_name, "status": "Running"},
            )
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message=f"Service '{service_name}' is not Running (current: {status_val})",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"service": service_name, "status": str(status_val)},
            )

    def _verify_service_stopped(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        status_val = None
        service_name = "unknown"
        if isinstance(evidence, ServiceInfo):
            status_val = evidence.status
            service_name = evidence.name
        elif isinstance(evidence, ServiceRestartResult):
            status_val = evidence.current_status
            service_name = evidence.name
        elif isinstance(evidence, list) and len(evidence) > 0 and isinstance(evidence[0], ServiceInfo):
            status_val = evidence[0].status
            service_name = evidence[0].name
        elif isinstance(evidence, dict):
            status_val = evidence.get("status") or evidence.get("current_status")
            service_name = evidence.get("name", "unknown")

        if status_val is None:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message=f"Unable to determine service status for '{service_name}' from evidence",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        if str(status_val).strip().lower() == "stopped":
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.VERIFIED,
                success=True,
                message=f"Service '{service_name}' is Stopped",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"service": service_name, "status": "Stopped"},
            )
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message=f"Service '{service_name}' is not Stopped (current: {status_val})",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"service": service_name, "status": str(status_val)},
            )

    def _verify_process_identity_valid(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        target_list: List[ProcessInfo] = []
        if isinstance(evidence, ProcessInfo):
            target_list = [evidence]
        elif isinstance(evidence, list) and all(isinstance(p, ProcessInfo) for p in evidence):
            target_list = evidence
        elif isinstance(evidence, ProcessStopResult):
            if evidence.pid > 0:
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.VERIFIED,
                    success=True,
                    message=f"Valid process identity: PID {evidence.pid} ({evidence.name})",
                    evidence_summary=evidence,
                    timestamp=datetime.now(),
                    observed_state={"pid": evidence.pid, "name": evidence.name},
                )
            else:
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.FAILED,
                    success=False,
                    message=f"Invalid PID in ProcessStopResult: {evidence.pid}",
                    evidence_summary=evidence,
                    timestamp=datetime.now(),
                )
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Evidence is not a valid ProcessInfo or list of ProcessInfo",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        if not target_list:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message="No matching process identity found",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        expected_name = (request.expected_text or "").strip().lower()
        for p in target_list:
            if p.pid <= 0:
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.FAILED,
                    success=False,
                    message=f"Invalid process PID: {p.pid}",
                    evidence_summary=evidence,
                    timestamp=datetime.now(),
                )
            if expected_name and p.name.lower() != expected_name and p.name.lower().replace(".exe", "") != expected_name:
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.FAILED,
                    success=False,
                    message=f"Process identity mismatch: found '{p.name}', expected '{request.expected_text}'",
                    evidence_summary=evidence,
                    timestamp=datetime.now(),
                )

        return VerificationResult(
            verification_type=request.verification_type,
            status=VerificationStatus.VERIFIED,
            success=True,
            message=f"Verified valid process identity ({len(target_list)} process(es))",
            evidence_summary=evidence,
            timestamp=datetime.now(),
            observed_state={"count": len(target_list), "processes": [p.name for p in target_list]},
        )

    def _verify_file_content_match(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        expected = request.expected_content if request.expected_content is not None else request.expected_text
        if expected is None:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Missing expected_content or expected_text for FILE_CONTENT_MATCH",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        content = None
        if isinstance(evidence, TextReadResult):
            if not evidence.success:
                return VerificationResult(
                    verification_type=request.verification_type,
                    status=VerificationStatus.FAILED,
                    success=False,
                    message=f"Failed to read file content: {evidence.error or 'read unsuccessful'}",
                    evidence_summary=evidence,
                    timestamp=datetime.now(),
                )
            content = evidence.content
        elif isinstance(evidence, str):
            content = evidence
        elif isinstance(evidence, dict) and "content" in evidence:
            content = evidence["content"]
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Evidence is not a TextReadResult or string content",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        if content == expected:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.VERIFIED,
                success=True,
                message=f"File content matches expected ({len(content)} chars)",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message=f"File content mismatch: expected {len(expected)} chars, got {len(content)} chars",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

    def _verify_file_hash_match(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        expected_sha = request.expected_sha256
        if not expected_sha:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Missing expected_sha256 parameter",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        actual_sha = None
        if isinstance(evidence, FileWriteResult):
            actual_sha = evidence.sha256
        elif isinstance(evidence, dict) and "sha256" in evidence:
            actual_sha = evidence["sha256"]
        elif hasattr(evidence, "sha256"):
            actual_sha = getattr(evidence, "sha256")

        if not actual_sha:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Evidence does not contain sha256 hash",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )

        if actual_sha.lower() == expected_sha.lower():
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.VERIFIED,
                success=True,
                message="File SHA256 matches expected",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"sha256": actual_sha},
            )
        else:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message=f"File SHA256 mismatch: expected {expected_sha}, got {actual_sha}",
                evidence_summary=evidence,
                timestamp=datetime.now(),
                observed_state={"sha256": actual_sha},
            )

    def _verify_read_content_valid(self, request: VerificationRequest) -> VerificationResult:
        evidence = request.evidence
        if not isinstance(evidence, TextReadResult):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.UNKNOWN,
                success=False,
                message="Evidence is not a TextReadResult",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if not evidence.success:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message=f"Text read unsuccessful: {evidence.error or 'unknown read error'}",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if evidence.content is None or not isinstance(evidence.content, str):
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message="Text read content is null or not a valid string",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        if "\x00" in evidence.content:
            return VerificationResult(
                verification_type=request.verification_type,
                status=VerificationStatus.FAILED,
                success=False,
                message="Text content contains corrupt null bytes (possible binary payload)",
                evidence_summary=evidence,
                timestamp=datetime.now(),
            )
        return VerificationResult(
            verification_type=request.verification_type,
            status=VerificationStatus.VERIFIED,
            success=True,
            message=f"Read content structurally valid ({len(evidence.content)} chars)",
            evidence_summary=evidence,
            timestamp=datetime.now(),
            observed_state={"length": len(evidence.content), "encoding": evidence.encoding},
        )