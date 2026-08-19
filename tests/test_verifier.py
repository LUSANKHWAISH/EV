"""
Unit tests for the EVVerifier.
"""
import unittest
from datetime import datetime

from core.models import (
    ProcessInfo,
    TcpConnectionInfo,
    FileInfo,
    TextReadResult,
    VerificationRequest,
    VerificationType,
)
from core.verifier import EVVerifier, VerificationStatus


class TestEVVerifier(unittest.TestCase):
    def setUp(self):
        self.verifier = EVVerifier()

    # Helper to create dummy evidence
    def dummy_process_info(self, pid=123, name="test.exe"):
        return ProcessInfo(pid=pid, name=name, executable_path=None, status=None)

    def dummy_tcp_info(self, local_port=4003, remote_port=80, state="ESTABLISHED"):
        return TcpConnectionInfo(
            local_address="127.0.0.1",
            local_port=local_port,
            remote_address="127.0.0.1",
            remote_port=remote_port,
            state=state,
            owning_pid=None,
            process_name=None,
        )

    def dummy_file_info(self, path=r"D:\EV\test.txt", exists=True, is_file=True):
        return FileInfo(
            path=path,
            name="test.txt",
            exists=exists,
            is_file=is_file,
            is_directory=not is_file,
            size_bytes=100,
            modified_at=datetime.now(),
            extension=".txt",
        )

    def dummy_text_read_result(self, content="hello world", success=True, path=r"D:\EV\test.txt"):
        return TextReadResult(
            path=path,
            success=success,
            content=content,
            encoding="utf-8",
            truncated=False,
            size_bytes=len(content),
            error=None if success else "read failed",
        )

    # PROCESS_EXISTS
    def test_process_exists_non_empty(self):
        evidence = [self.dummy_process_info()]
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_process_exists_empty(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # PROCESS_NOT_EXISTS
    def test_process_not_exists_empty(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_process_not_exists_non_empty(self):
        evidence = [self.dummy_process_info()]
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # TCP_PORT_EXISTS
    def test_tcp_port_exists_non_empty(self):
        evidence = [self.dummy_tcp_info()]
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_tcp_port_exists_empty(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # TCP_PORT_NOT_EXISTS
    def test_tcp_port_not_exists_empty(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_tcp_port_not_exists_non_empty(self):
        evidence = [self.dummy_tcp_info()]
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # FILE_EXISTS
    def test_file_exists_true(self):
        evidence = self.dummy_file_info(exists=True, is_file=True)
        req = VerificationRequest(
            verification_type=VerificationType.FILE_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_file_exists_false(self):
        evidence = self.dummy_file_info(exists=False, is_file=False)  # is_file irrelevant when exists False
        req = VerificationRequest(
            verification_type=VerificationType.FILE_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    def test_file_exists_is_directory(self):
        evidence = self.dummy_file_info(exists=True, is_file=False)  # is_directory True
        req = VerificationRequest(
            verification_type=VerificationType.FILE_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # FILE_NOT_EXISTS
    def test_file_not_exists_true(self):
        evidence = self.dummy_file_info(exists=False, is_file=False)
        req = VerificationRequest(
            verification_type=VerificationType.FILE_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_file_not_exists_false(self):
        evidence = self.dummy_file_info(exists=True, is_file=True)
        req = VerificationRequest(
            verification_type=VerificationType.FILE_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # DIRECTORY_EXISTS
    def test_directory_exists_true(self):
        evidence = self.dummy_file_info(exists=True, is_file=False)  # is_directory True
        req = VerificationRequest(
            verification_type=VerificationType.DIRECTORY_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_directory_exists_false(self):
        evidence = self.dummy_file_info(exists=True, is_file=True)  # is_directory False
        req = VerificationRequest(
            verification_type=VerificationType.DIRECTORY_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # TEXT_CONTAINS
    def test_text_contains_true(self):
        evidence = self.dummy_text_read_result(content="hello world")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_CONTAINS,
            evidence=evidence,
            expected_text="world",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_text_contains_false(self):
        evidence = self.dummy_text_read_result(content="hello world")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_CONTAINS,
            evidence=evidence,
            expected_text="xyz",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    def test_text_contains_failed_read(self):
        evidence = self.dummy_text_read_result(success=False, content="")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_CONTAINS,
            evidence=evidence,
            expected_text="hello",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_text_not_contains_failed_read(self):
        evidence = self.dummy_text_read_result(success=False, content="")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_NOT_CONTAINS,
            evidence=evidence,
            expected_text="hello",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    # TEXT_NOT_CONTAINS
    def test_text_not_contains_true(self):
        evidence = self.dummy_text_read_result(content="hello world")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_NOT_CONTAINS,
            evidence=evidence,
            expected_text="xyz",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_text_not_contains_false(self):
        evidence = self.dummy_text_read_result(content="hello world")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_NOT_CONTAINS,
            evidence=evidence,
            expected_text="world",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # RESULT_NOT_EMPTY
    def test_result_not_empty_non_empty(self):
        evidence = [1, 2, 3]
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_NOT_EMPTY,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_result_not_empty_empty(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_NOT_EMPTY,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # RESULT_EMPTY
    def test_result_empty_true(self):
        evidence = []
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_EMPTY,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertTrue(res.success)

    def test_result_empty_non_empty(self):
        evidence = [1]
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_EMPTY,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.NOT_VERIFIED)
        self.assertFalse(res.success)

    # INCOMPATIBLE EVIDENCE
    def test_incompatible_evidence(self):
        # Give a list for FILE_EXISTS
        evidence = [1, 2, 3]
        req = VerificationRequest(
            verification_type=VerificationType.FILE_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_none_evidence(self):
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=None,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    # MISSING EXPECTED TEXT
    def test_missing_expected_text(self):
        evidence = self.dummy_text_read_result(content="hello")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_CONTAINS,
            evidence=evidence,
            expected_text=None,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    # TIMING POPULATED
    def test_timestamp_populated(self):
        evidence = [self.dummy_process_info()]
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertIsInstance(res.timestamp, datetime)
        # timestamp should be close to now, but we just check it's not zero
        self.assertGreater(res.timestamp.timestamp(), 0)

    # INTERNAL ERROR ISOLATION (simulate by patching something internal to raise)
    # We'll test that an unexpected exception in the verifier leads to ERROR status.
    # We'll patch an internal verification method to raise an unexpected exception.
    def test_internal_error_isolation(self):
        from unittest.mock import patch

        # Create valid ProcessInfo evidence
        evidence = [self.dummy_process_info()]
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=evidence,
        )

        # Patch the internal verification method to raise an unexpected exception
        with patch.object(
            self.verifier,
            "_verify_process_exists",
            side_effect=RuntimeError("forced internal verifier failure"),
        ):
            res = self.verifier.verify(req)

        # The outer verifier should catch the exception and return ERROR status
        self.assertEqual(res.status, VerificationStatus.ERROR)
        self.assertFalse(res.success)
        self.assertIsNotNone(res.error)
        self.assertIn("forced internal verifier failure", res.error)

    # Additional regression tests per acceptance repair
    def test_process_exists_with_non_processinfo(self):
        evidence = [1, 2, 3]  # list of ints
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_process_not_exists_with_tcp_connection(self):
        evidence = [self.dummy_tcp_info()]  # TcpConnectionInfo in list
        req = VerificationRequest(
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_tcp_port_exists_with_non_tcpinfo(self):
        evidence = [1, 2, 3]
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_tcp_port_not_exists_with_processinfo(self):
        evidence = [self.dummy_process_info()]
        req = VerificationRequest(
            verification_type=VerificationType.TCP_PORT_NOT_EXISTS,
            evidence=evidence,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_result_empty_with_none(self):
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_EMPTY,
            evidence=None,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_result_not_empty_with_none(self):
        req = VerificationRequest(
            verification_type=VerificationType.RESULT_NOT_EMPTY,
            evidence=None,
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_result_not_empty_with_unsupported_scalar(self):
        for evidence in [123, 3.14, object()]:
            with self.subTest(evidence=evidence):
                req = VerificationRequest(
                    verification_type=VerificationType.RESULT_NOT_EMPTY,
                    evidence=evidence,
                )
                res = self.verifier.verify(req)
                self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
                self.assertFalse(res.success)

    def test_result_empty_with_unsupported_scalar(self):
        for evidence in [123, 3.14, object()]:
            with self.subTest(evidence=evidence):
                req = VerificationRequest(
                    verification_type=VerificationType.RESULT_EMPTY,
                    evidence=evidence,
                )
                res = self.verifier.verify(req)
                self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
                self.assertFalse(res.success)

    def test_failed_textread_with_text_contains(self):
        evidence = self.dummy_text_read_result(success=False, content="")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_CONTAINS,
            evidence=evidence,
            expected_text="hello",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)

    def test_failed_textread_with_text_not_contains(self):
        evidence = self.dummy_text_read_result(success=False, content="")
        req = VerificationRequest(
            verification_type=VerificationType.TEXT_NOT_CONTAINS,
            evidence=evidence,
            expected_text="hello",
        )
        res = self.verifier.verify(req)
        self.assertEqual(res.status, VerificationStatus.INDETERMINATE)
        self.assertFalse(res.success)


if __name__ == '__main__':
    unittest.main()