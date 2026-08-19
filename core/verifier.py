"""
Minimal verifier engine for E.V.
"""
from datetime import datetime
from typing import Any, List, Optional

from .models import VerificationRequest, VerificationResult, VerificationStatus, VerificationType
from .models import ProcessInfo, TcpConnectionInfo, FileInfo, TextReadResult


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