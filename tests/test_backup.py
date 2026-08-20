"""
Unit tests for the EVBackupManager.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.backup import EVBackupManager
from core.models import BackupStatus


class TestEVBackupManager(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory for backup root to avoid interfering with real backups
        self.temp_dir = tempfile.TemporaryDirectory()
        self.backup_root = Path(self.temp_dir.name) / "test_backups"
        self.manager = EVBackupManager(backup_root=self.backup_root)

        # Create a temporary file for testing
        self.source_file = tempfile.NamedTemporaryFile(
            mode="w", delete=False, dir=self.temp_dir.name, suffix=".txt"
        )
        self.source_file.write("Hello, World! This is a test file.\nSecond line.")
        self.source_file.flush()
        self.source_file.close()
        self.source_path = Path(self.source_file.name)

    def tearDown(self):
        # Clean up temporary files and directory
        self.temp_dir.cleanup()

    def test_backup_existing_file_success(self):
        """Test backing up an existing file succeeds."""
        result = self.manager.backup_file(self.source_path)

        self.assertEqual(result.status, BackupStatus.CREATED)
        self.assertTrue(result.success)
        self.assertTrue(result.executed)
        self.assertEqual(result.original_path, str(self.source_path))
        self.assertIsNotNone(result.backup_path)
        self.assertTrue(Path(result.backup_path).exists())
        self.assertIsNotNone(result.backup_record)
        self.assertTrue(result.backup_record.success)
        self.assertEqual(result.backup_record.original_path, str(self.source_path))
        self.assertEqual(result.backup_record.original_size_bytes, self.source_path.stat().st_size)
        self.assertGreater(result.duration_seconds, 0)

    def test_backup_preserves_exact_content(self):
        """Test that backup preserves exact content of source file."""
        result = self.manager.backup_file(self.source_path)
        self.assertTrue(result.success)

        # Read original and backup content
        with open(self.source_path, "r") as f:
            original_content = f.read()
        with open(result.backup_path, "r") as f:
            backup_content = f.read()

        self.assertEqual(original_content, backup_content)

    def test_backup_hash_matches_source_hash(self):
        """Test that backup file hash matches source file hash."""
        import hashlib

        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()

        result = self.manager.backup_file(self.source_path)
        self.assertTrue(result.success)

        original_hash = file_hash(self.source_path)
        backup_hash = file_hash(result.backup_path)

        self.assertEqual(original_hash, backup_hash)
        # Also check that the backup record contains the SHA-256
        self.assertIsNotNone(result.backup_record)
        self.assertEqual(result.backup_record.sha256, backup_hash)

    def test_backup_does_not_modify_source(self):
        """Test that backup operation does not modify the source file."""
        import hashlib

        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()

        original_hash = file_hash(self.source_path)
        original_mtime = self.source_path.stat().st_mtime

        result = self.manager.backup_file(self.source_path)
        self.assertTrue(result.success)

        # Hash should be unchanged
        new_hash = file_hash(self.source_path)
        self.assertEqual(original_hash, new_hash)

        # Modification time should be unchanged (or very close, allowing for filesystem precision)
        new_mtime = self.source_path.stat().st_mtime
        self.assertAlmostEqual(original_mtime, new_mtime, places=0)

    def test_backup_preserves_original_path_metadata_in_record(self):
        """Test that backup record contains correct original path metadata."""
        result = self.manager.backup_file(self.source_path)
        self.assertTrue(result.success)

        record = result.backup_record
        self.assertIsNotNone(record)
        self.assertEqual(record.original_path, str(self.source_path))
        self.assertEqual(record.backup_path, result.backup_path)
        self.assertEqual(record.original_size_bytes, self.source_path.stat().st_size)
        self.assertTrue(record.original_exists)
        self.assertTrue(record.success)

    def test_backup_missing_file_structured_failure(self):
        """Test that backing up a missing file returns structured failure."""
        missing_path = Path(self.temp_dir.name) / "nonexistent.txt"
        result = self.manager.backup_file(missing_path)

        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertFalse(result.executed)
        self.assertEqual(result.original_path, str(missing_path))
        self.assertIsNone(result.backup_path)
        self.assertIn("does not exist", result.message)
        self.assertIsNotNone(result.error)
        self.assertIn("FileNotFoundError", result.error)

    def test_backup_directory_instead_of_file_structured_failure(self):
        """Test that backing up a directory returns structured failure."""
        dir_path = Path(self.temp_dir.name) / "testdir"
        dir_path.mkdir()

        result = self.manager.backup_file(dir_path)

        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertFalse(result.executed)
        self.assertEqual(result.original_path, str(dir_path))
        self.assertIsNone(result.backup_path)
        self.assertIn("not a regular file", result.message)
        self.assertIsNotNone(result.error)
        self.assertIn("IsADirectoryError", result.error)

    def test_unique_backup_names_for_repeated_backup(self):
        """Test that repeated backups of the same source create unique backup names."""
        result1 = self.manager.backup_file(self.source_path)
        result2 = self.manager.backup_file(self.source_path)

        self.assertTrue(result1.success)
        self.assertTrue(result2.success)
        self.assertNotEqual(result1.backup_path, result2.backup_path)
        self.assertTrue(Path(result1.backup_path).exists())
        self.assertTrue(Path(result2.backup_path).exists())

        # Both should contain the same content
        with open(result1.backup_path, "r") as f1, open(result2.backup_path, "r") as f2:
            self.assertEqual(f1.read(), f2.read())

    def test_restore_to_missing_target_success(self):
        """Test restoring to a missing target succeeds."""
        # First create a backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Define a target path that doesn't exist
        target_path = Path(self.temp_dir.name) / "restored.txt"

        # Restore
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )

        self.assertEqual(restore_result.status, BackupStatus.RESTORED)
        self.assertTrue(restore_result.success)
        self.assertTrue(restore_result.executed)
        self.assertEqual(restore_result.original_path, str(target_path))
        self.assertEqual(restore_result.backup_path, backup_result.backup_path)
        self.assertTrue(Path(restore_result.original_path).exists())
        self.assertIsNone(restore_result.safety_backup_path)
        self.assertGreater(restore_result.duration_seconds, 0)

    def test_restore_exact_content(self):
        """Test that restored file has exact content from backup."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Restore to new location
        target_path = Path(self.temp_dir.name) / "restored.txt"
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )
        self.assertTrue(restore_result.success)

        # Compare content
        with open(self.source_path, "r") as f_source, open(
            target_path, "r"
        ) as f_target:
            self.assertEqual(f_source.read(), f_target.read())

    def test_restore_hash_matches_backup_hash(self):
        """Test that restored file hash matches backup file hash."""
        import hashlib

        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()

        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        backup_hash = file_hash(backup_result.backup_path)

        # Restore
        target_path = Path(self.temp_dir.name) / "restored.txt"
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )
        self.assertTrue(restore_result.success)

        # Check hash
        restored_hash = file_hash(target_path)
        self.assertEqual(backup_hash, restored_hash)

    def test_restore_missing_backup_structured_failure(self):
        """Test that restoring from missing backup returns structured failure."""
        missing_backup = Path(self.temp_dir.name) / "missing.bak"
        target_path = Path(self.temp_dir.name) / "target.txt"

        result = self.manager.restore_file(missing_backup, target_path, overwrite=False)

        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertFalse(result.executed)
        self.assertEqual(result.backup_path, str(missing_backup))
        self.assertEqual(result.original_path, str(target_path))
        self.assertIn("does not exist", result.message)
        self.assertIsNotNone(result.error)
        self.assertIn("FileNotFoundError", result.error)

    def test_restore_directory_as_backup_structured_failure(self):
        """Test that restoring when backup is a directory returns structured failure."""
        # Create a directory and try to use it as backup
        backup_dir = Path(self.temp_dir.name) / "backup_dir"
        backup_dir.mkdir()
        target_path = Path(self.temp_dir.name) / "target.txt"

        result = self.manager.restore_file(backup_dir, target_path, overwrite=False)

        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertFalse(result.executed)
        self.assertEqual(result.backup_path, str(backup_dir))
        self.assertIn("not a regular file", result.message)
        self.assertIsNotNone(result.error)
        self.assertIn("IsADirectoryError", result.error)

    def test_restore_existing_target_without_overwrite_no_modification(self):
        """Test that restoring to existing target without overwrite does not modify target."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Create an existing target with different content
        target_path = Path(self.temp_dir.name) / "target.txt"
        with open(target_path, "w") as f:
            f.write("Different content that should not be overwritten")

        original_target_content = "Different content that should not be overwritten"
        original_target_mtime = target_path.stat().st_mtime

        # Try to restore without overwrite
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )

        self.assertEqual(restore_result.status, BackupStatus.SKIPPED)
        self.assertFalse(restore_result.success)
        self.assertFalse(restore_result.executed)
        self.assertIsNone(restore_result.safety_backup_path)

        # Target should be unchanged
        with open(target_path, "r") as f:
            self.assertEqual(f.read(), original_target_content)
        # Modification time should be unchanged
        self.assertEqual(target_path.stat().st_mtime, original_target_mtime)

    def test_restore_existing_target_with_overwrite_success(self):
        """Test that restoring to existing target with overwrite succeeds."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Create an existing target with different content
        target_path = Path(self.temp_dir.name) / "target.txt"
        with open(target_path, "w") as f:
            f.write("Different content that will be overwritten")

        # Restore with overwrite
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=True
        )

        self.assertEqual(restore_result.status, BackupStatus.RESTORED)
        self.assertTrue(restore_result.success)
        self.assertTrue(restore_result.executed)
        self.assertIsNotNone(restore_result.safety_backup_path)
        self.assertTrue(Path(restore_result.safety_backup_path).exists())

        # Target should now have backup content
        with open(target_path, "r") as f:
            self.assertEqual(f.read(), "Hello, World! This is a test file.\nSecond line.")

        # Safety backup should contain original target content
        with open(restore_result.safety_backup_path, "r") as f:
            self.assertEqual(f.read(), "Different content that will be overwritten")

    def test_overwrite_preserves_previous_target_as_safety_backup(self):
        """Test that overwrite=True preserves previous target as safety backup."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Create an existing target
        target_path = Path(self.temp_dir.name) / "target.txt"
        original_content = "Original target content that should be preserved"
        with open(target_path, "w") as f:
            f.write(original_content)

        # Restore with overwrite
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=True
        )

        self.assertTrue(restore_result.success)
        self.assertIsNotNone(restore_result.safety_backup_path)
        safety_path = Path(restore_result.safety_backup_path)

        # Safety backup should contain original target content
        with open(safety_path, "r") as f:
            self.assertEqual(f.read(), original_content)

        # Safety backup should be in the backup root
        self.assertTrue(safety_path.is_relative_to(self.manager.backup_root))

    def test_safety_backup_contains_previous_target_content(self):
        """Test that safety backup contains the exact previous target content."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Create an existing target with known content
        target_path = Path(self.temp_dir.name) / "target.txt"
        original_content = "Exact original content for safety backup verification\nLine 2\nLine 3"
        with open(target_path, "w") as f:
            f.write(original_content)

        # Restore with overwrite
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=True
        )

        self.assertTrue(restore_result.success)
        self.assertIsNotNone(restore_result.safety_backup_path)

        # Verify safety backup content matches original target
        with open(restore_result.safety_backup_path, "r") as f:
            safety_content = f.read()
        self.assertEqual(safety_content, original_content)

    def test_restored_content_equals_requested_backup(self):
        """Test that restored content equals the requested backup content."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Read backup content
        with open(backup_result.backup_path, "r") as f:
            backup_content = f.read()

        # Restore to new location
        target_path = Path(self.temp_dir.name) / "target.txt"
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )

        self.assertTrue(restore_result.success)

        # Verify restored content equals backup content
        with open(target_path, "r") as f:
            restored_content = f.read()
        self.assertEqual(restored_content, backup_content)

    def test_timestamps_duration_populated(self):
        """Test that timestamps and duration are populated in results."""
        # Backup test
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        self.assertIsInstance(backup_result.started_at, type(backup_result.finished_at))
        self.assertGreaterEqual(backup_result.duration_seconds, 0)
        if backup_result.backup_record:
            self.assertIsInstance(backup_result.backup_record.created_at, type(backup_result.finished_at))

        # Restore test
        target_path = Path(self.temp_dir.name) / "target.txt"
        restore_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )
        self.assertTrue(restore_result.success)
        self.assertIsInstance(restore_result.started_at, type(restore_result.finished_at))
        self.assertGreaterEqual(restore_result.duration_seconds, 0)

    def test_expected_filesystem_exception_returned_structurally(self):
        """Test that expected filesystem exceptions are returned structurally."""
        # Test permission error by trying to backup to a read-only location (simulated)
        # Instead, we'll test that the error handling works by checking the structure
        missing_path = Path(self.temp_dir.name) / "nonexistent.txt"
        result = self.manager.backup_file(missing_path)

        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertIsInstance(result.error, str)
        self.assertGreater(len(result.error), 0)
        self.assertIn("FileNotFoundError", result.error)

    def test_backup_result_executed_semantics_sensible(self):
        """Test that backup result executed semantics are sensible."""
        # Successful backup
        success_result = self.manager.backup_file(self.source_path)
        self.assertTrue(success_result.executed)
        self.assertTrue(success_result.success)

        # Failed backup due to missing file
        missing_path = Path(self.temp_dir.name) / "missing.txt"
        fail_result = self.manager.backup_file(missing_path)
        self.assertFalse(fail_result.executed)  # Not executed because validation failed early
        self.assertFalse(fail_result.success)

        # Failed backup due to integrity issue (simulated by mocking hash calculation)
        with patch.object(
            self.manager, "_calculate_file_hash", side_effect=[ "hash1", "hash2" ]
        ):  # Different hashes
            integrity_fail_result = self.manager.backup_file(self.source_path)
            self.assertTrue(integrity_fail_result.executed)  # Copy was attempted
            self.assertFalse(integrity_fail_result.success)  # But failed integrity check

    def test_restore_result_executed_semantics_sensible(self):
        """Test that restore result executed semantics are sensible."""
        # Create backup first
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)

        # Successful restore
        target_path = Path(self.temp_dir.name) / "target.txt"
        success_result = self.manager.restore_file(
            backup_result.backup_path, target_path, overwrite=False
        )
        self.assertTrue(success_result.executed)
        self.assertTrue(success_result.success)

        # Failed restore due to missing backup
        missing_backup = Path(self.temp_dir.name) / "missing.bak"
        fail_result = self.manager.restore_file(
            missing_backup, target_path, overwrite=False
        )
        self.assertFalse(fail_result.executed)  # Not executed because validation failed early
        self.assertFalse(fail_result.success)

        # Failed restore due to integrity issue (simulated by mocking hash calculation)
        # Use a fresh target path that does not exist to ensure we reach the copy attempt
        integrity_target = Path(self.temp_dir.name) / "integrity_fail_target.txt"
        with patch.object(
            self.manager, "_calculate_file_hash", side_effect=[ "hash1", "hash2" ]
        ):  # Different hashes: backup hash != temp hash
            integrity_fail_result = self.manager.restore_file(
                backup_result.backup_path, integrity_target, overwrite=False
            )
            self.assertTrue(integrity_fail_result.executed)  # Copy was attempted
            self.assertFalse(integrity_fail_result.success)  # But failed integrity check
            self.assertEqual(integrity_fail_result.status, BackupStatus.FAILED)
            # The target should not have been created because the integrity check failed
            self.assertFalse(integrity_target.exists())


# ---- Failure Path Hardening Tests ----
    def test_backup_root_creation_failure(self):
        """Test that backup-root creation failure returns structured failure."""
        # Mock _ensure_backup_root to raise OSError
        with patch.object(self.manager, '_ensure_backup_root', side_effect=OSError("permission denied")):
            result = self.manager.backup_file(self.source_path)
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertFalse(result.executed)  # No copy attempted
            self.assertIn("Backup operation failed", result.message)
            self.assertIsNotNone(result.error)
            self.assertIn("permission denied", result.error)

    def test_backup_copy_then_oserror(self):
        """Test that an OSError after copy attempt (during hash calculation) results in executed=True."""
        # Mock _calculate_file_hash to return a valid hash for the source, then raise OSError for the backup hash
        with patch.object(self.manager, '_calculate_file_hash') as mock_hash:
            mock_hash.side_effect = ["validhash", OSError("hash read failed")]
            result = self.manager.backup_file(self.source_path)
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)  # copy was attempted
            self.assertIn("Backup operation failed", result.message)
            self.assertIsNotNone(result.error)

    def test_restore_validation_failure_executed_false(self):
        """Test that restore validation failure (missing backup) returns executed=False."""
        missing_backup = Path(self.temp_dir.name) / "missing.bak"
        target_path = Path(self.temp_dir.name) / "target.txt"
        result = self.manager.restore_file(missing_backup, target_path, overwrite=False)
        self.assertEqual(result.status, BackupStatus.FAILED)
        self.assertFalse(result.success)
        self.assertFalse(result.executed)
        self.assertIn("Backup file does not exist", result.message)

    def test_restore_temp_copy_then_oserror(self):
        """Test that an OSError during temp copy results in executed=True."""
        # Create a backup first
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        target_path = Path(self.temp_dir.name) / "target.txt"
        # Mock tempfile.mkstemp to raise OSError after we set restore_attempted? Actually we want to simulate
        # an error during shutil.copy2 (backup to temp). We'll mock shutil.copy2 to raise OSError.
        with patch('shutil.copy2', side_effect=OSError("copy failed")):
            result = self.manager.restore_file(backup_result.backup_path, target_path, overwrite=False)
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)  # copy attempted
            self.assertIn("Restore operation failed", result.message)
            self.assertIsNotNone(result.error)

    def test_final_hash_read_error_with_prior_target(self):
        """Test final hash read error with prior target triggers recovery."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        target_path = Path(self.temp_dir.name) / "target.txt"
        # Create an existing target with known content
        original_content = "original target content"
        with open(target_path, "w") as f:
            f.write(original_content)
        # Compute expected hashes
        import hashlib
        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        original_target_hash = file_hash(target_path)  # hash of original target (content)
        backup_hash = file_hash(Path(backup_result.backup_path))  # hash of backup (source file content)
        # Note: safety backup will be a copy of original target, so its hash == original_target_hash
        # Sequence of hash calls in restore_file with overwrite=True:
        # 1. target_original_hash = hash(target_path) -> original_target_hash
        # 2. safety_hash = hash(safety_backup_path) -> original_target_hash
        # 3. backup_hash = hash(backup_path) -> backup_hash
        # 4. temp_hash = hash(temp_path) -> backup_hash
        # 5. restored_hash = hash(target_path) after replace -> we want this to raise OSError
        # 6. recovery safety hash = hash(safety_backup_path) -> original_target_hash
        # 7. recovery temp hash = hash(recovery_temp_path) -> original_target_hash (if recovery succeeds)
        real_hash = self.manager._calculate_file_hash
        target_hash_calls = 0
        def hash_side_effect(path):
            nonlocal target_hash_calls
            p = Path(path)
            if p == target_path:
                target_hash_calls += 1
                # first call: hash of original target before overwrite (target_original_hash)
                # second call: hash of restored target after replace (final verification)
                if target_hash_calls == 2:
                    raise OSError("read fail")
            return real_hash(path)
        with patch.object(self.manager, '_calculate_file_hash', side_effect=hash_side_effect):
            result = self.manager.restore_file(backup_result.backup_path, target_path, overwrite=True)
            # Should fail, executed=True, and recovery succeeded
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)
            self.assertIn("recovered original from safety backup", result.message)
            # Safety backup should still exist
            self.assertIsNotNone(result.safety_backup_path)
            self.assertTrue(Path(result.safety_backup_path).exists())
            # Target should now have original content (recovered)
            with open(target_path, "r") as f:
                self.assertEqual(f.read(), original_content)

    def test_final_hash_read_error_no_prior_target_removes_target(self):
        """Test final hash read error with no prior target removes the unverified target."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        target_path = Path(self.temp_dir.name) / "target.txt"
        # Ensure target does not exist
        # We'll mock _calculate_file_hash to return:
        #   1. hash of backup -> returns a valid hash (hash1)
        #   2. hash of temp -> returns the same valid hash (hash1)
        #   3. hash of restored target -> raises OSError
        with patch.object(self.manager, '_calculate_file_hash') as mock_hash:
            mock_hash.side_effect = ["hash1", "hash1", OSError("read fail")]
            result = self.manager.restore_file(backup_result.backup_path, target_path, overwrite=False)
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)
            self.assertIn("removed corrupt target", result.message)
            # Target should not exist
            self.assertFalse(target_path.exists())

    def test_recovery_success_restores_original_target(self):
        """Test that recovery successfully restores original target when final verification fails."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        target_path = Path(self.temp_dir.name) / "target.txt"
        # Create an existing target with known content
        original_content = "original content to be restored"
        with open(target_path, "w") as f:
            f.write(original_content)
        # Compute expected hashes
        import hashlib
        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        original_target_hash = file_hash(target_path)  # hash of original target (content)
        backup_hash = file_hash(Path(backup_result.backup_path))  # hash of backup (source file content)
        # Note: safety backup will be a copy of original target, so its hash == original_target_hash
        # Sequence of hash calls in restore_file with overwrite=True:
        # 1. target_original_hash = hash(target_path) -> original_target_hash
        # 2. safety_hash = hash(safety_backup_path) -> original_target_hash
        # 3. backup_hash = hash(backup_path) -> backup_hash
        # 4. temp_hash = hash(temp_path) -> backup_hash
        # 5. restored_hash = hash(target_path) after replace -> we want this to be different (to trigger recovery)
        # 6. recovery safety hash = hash(safety_backup_path) -> original_target_hash
        # 7. recovery temp hash = hash(recovery_temp_path) -> original_target_hash (if recovery succeeds)
        with patch.object(self.manager, '_calculate_file_hash') as mock_hash:
            mock_hash.side_effect = [
                original_target_hash,  # call 1: target_original_hash
                original_target_hash,  # call 2: safety_hash
                backup_hash,           # call 3: backup_hash
                backup_hash,           # call 4: temp_hash
                backup_hash + "x",     # call 5: restored_hash (mismatch)
                original_target_hash,  # call 6: safety_hash during recovery
                original_target_hash   # call 7: recovery temp hash
            ]
            result = self.manager.restore_file(backup_result.backup_path, target_path, overwrite=True)
            # Since we mocked to make restored_hash differ, we expect failure but recovery attempted and succeeded.
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)
            self.assertIn("recovered original from safety backup", result.message)
            # Target should now have original content (recovered)
            with open(target_path, "r") as f:
                self.assertEqual(f.read(), original_content)
            # Safety backup should still exist
            self.assertIsNotNone(result.safety_backup_path)
            self.assertTrue(Path(result.safety_backup_path).exists())

    def test_failed_recovery_does_not_claim_safety_backup_corrupt(self):
        """Test that when recovery fails, message does not claim safety backup is corrupt."""
        # Create backup
        backup_result = self.manager.backup_file(self.source_path)
        self.assertTrue(backup_result.success)
        target_path = Path(self.temp_dir.name) / "target.txt"
        # Create an existing target with known content
        original_content = "original"
        with open(target_path, "w") as f:
            f.write(original_content)
        # Compute expected hashes
        import hashlib
        def file_hash(path):
            hash_sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        original_target_hash = file_hash(target_path)  # hash of original target
        backup_hash = file_hash(Path(backup_result.backup_path))  # hash of backup (source file content)
        # Safety backup will be a copy of original target, so its hash == original_target_hash
        # Sequence of hash calls in restore_file with overwrite=True:
        # 1. target_original_hash = hash(target_path) -> original_target_hash
        # 2. safety_hash = hash(safety_backup_path) -> original_target_hash
        # 3. backup_hash = hash(backup_path) -> backup_hash
        # 4. temp_hash = hash(temp_path) -> backup_hash
        # 5. restored_hash = hash(target_path) after replace -> we want this to raise OSError
        # 6. recovery_hash = hash(recovery_temp_path) -> we want this to raise OSError (recovery fails)
        with patch.object(self.manager, '_calculate_file_hash') as mock_hash:
            mock_hash.side_effect = [
                original_target_hash,  # call 1
                original_target_hash,  # call 2
                backup_hash,           # call 3
                backup_hash,           # call 4
                OSError("read fail"),  # call 5: final verification read fails
                OSError("read fail")   # call 6: recovery temp hash read fails
            ]
            result = self.manager.restore_file(backup_result.backup_path, target_path, overwrite=True)
            self.assertEqual(result.status, BackupStatus.FAILED)
            self.assertFalse(result.success)
            self.assertTrue(result.executed)
            # Message should not say "safety backup also corrupt"
            self.assertNotIn("safety backup also corrupt", result.message)
            # Should mention recovery attempt failed
            self.assertIn("recovery attempt failed", result.message)
            # Safety backup should still exist
            self.assertIsNotNone(result.safety_backup_path)
            self.assertTrue(Path(result.safety_backup_path).exists())
            # Safety backup should contain the original target content
            with open(result.safety_backup_path, "r") as f:
                self.assertEqual(f.read(), original_content)

if __name__ == '__main__':
    unittest.main()