"""
Minimal deterministic backup / rollback layer for E.V.
"""
import hashlib
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from .models import BackupResult, RestoreResult, BackupStatus, FileBackupRecord


class EVBackupManager:
    """
    Deterministic backup manager for file-level backup and restore operations.
    """

    def __init__(self, backup_root: Union[str, Path] = None):
        """
        Initialize the backup manager.

        Args:
            backup_root: Root directory for backups. If None, uses D:\\EV\\backups
        """
        if backup_root is None:
            # Default backup directory under EV project
            self.backup_root = Path(r"D:\EV\backups")
        else:
            self.backup_root = Path(backup_root)
        # Do not create backup root here; create lazily when needed

    def _ensure_backup_root(self) -> None:
        """Create the backup root directory if it does not exist."""
        self.backup_root.mkdir(parents=True, exist_ok=True)

    def _generate_backup_path(self, original_path: Union[str, Path]) -> Path:
        """
        Generate a unique backup path for the given original file.

        Args:
            original_path: Path to the original file

        Returns:
            Unique backup path within the backup root
        """
        original_path = Path(original_path)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        # Use a counter to avoid collisions if multiple backups in same second
        counter = 0
        while True:
            if counter == 0:
                backup_name = f"{original_path.name}.{timestamp}.bak"
            else:
                backup_name = f"{original_path.name}.{timestamp}.{counter:03d}.bak"
            backup_path = self.backup_root / backup_name
            if not backup_path.exists():
                return backup_path
            counter += 1

    def _calculate_file_hash(self, file_path: Union[str, Path]) -> str:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hexadecimal SHA-256 hash string
        """
        hash_sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()

    def backup_file(self, file_path: Union[str, Path]) -> BackupResult:
        """
        Create a backup of a regular file.

        Args:
            file_path: Path to the file to backup

        Returns:
            BackupResult with status and details
        """
        started_at = datetime.now()
        original_path = Path(file_path)

        # Validate source
        if not original_path.exists():
            finished_at = datetime.now()
            return BackupResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=None,
                message="Source file does not exist",
                error="FileNotFoundError: Source file does not exist",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        if not original_path.is_file():
            finished_at = datetime.now()
            return BackupResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=None,
                message="Source is not a regular file",
                error="IsADirectoryError: Source is a directory, not a regular file",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        # Calculate source hash for integrity verification
        try:
            original_hash = self._calculate_file_hash(original_path)
            original_size = original_path.stat().st_size
        except OSError as exc:
            finished_at = datetime.now()
            return BackupResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=None,
                message=f"Cannot read source file: {exc}",
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

        # Ensure backup root exists and generate backup path inside try block
        copy_attempted = False
        try:
            self._ensure_backup_root()
            backup_path = self._generate_backup_path(original_path)

            # Perform backup
            shutil.copy2(original_path, backup_path)
            copy_attempted = True

            # Verify backup integrity
            backup_hash = self._calculate_file_hash(backup_path)
            backup_size = backup_path.stat().st_size

            if original_hash != backup_hash:
                # Hash mismatch - remove the invalid backup
                try:
                    backup_path.unlink()
                except OSError:
                    pass  # Best effort cleanup

                finished_at = datetime.now()
                return BackupResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=True,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message="Backup integrity check failed: hash mismatch",
                    error="IntegrityError: Source and backup file hashes do not match",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                )

            # Success - create backup record
            backup_record = FileBackupRecord(
                original_path=str(original_path),
                backup_path=str(backup_path),
                original_size_bytes=original_size,
                backup_size_bytes=backup_size,
                sha256=backup_hash,
                created_at=datetime.now(),
                original_exists=True,
                success=True,
                message="Backup created successfully",
            )

            finished_at = datetime.now()
            return BackupResult(
                status=BackupStatus.CREATED,
                success=True,
                executed=True,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message="Backup created successfully",
                error=None,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                backup_record=backup_record,
            )

        except OSError as exc:
            finished_at = datetime.now()
            return BackupResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=copy_attempted,
                original_path=str(original_path),
                backup_path=str(backup_path) if 'backup_path' in locals() and backup_path.exists() else None,
                message=f"Backup operation failed: {exc}",
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
            )

    def restore_file(
        self,
        backup_path: Union[str, Path],
        original_path: Union[str, Path],
        overwrite: bool = False,
        create_parents: bool = False,
    ) -> RestoreResult:
        """
        Restore a file from a backup.

        Args:
            backup_path: Path to the backup file
            original_path: Path where the file should be restored
            overwrite: Whether to overwrite existing target file
            create_parents: Whether to create parent directories of target if missing

        Returns:
            RestoreResult with status and details
        """
        started_at = datetime.now()
        backup_path = Path(backup_path)
        original_path = Path(original_path)

        # Validate backup: must exist and be inside backup_root
        if not backup_path.exists():
            finished_at = datetime.now()
            return RestoreResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message="Backup file does not exist",
                error="FileNotFoundError: Backup file does not exist",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=None,
            )

        if not backup_path.is_file():
            finished_at = datetime.now()
            return RestoreResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message="Backup is not a regular file",
                error="IsADirectoryError: Backup is a directory, not a regular file",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=None,
            )

        # Ensure backup is within backup_root (resolve symlinks)
        try:
            backup_resolved = backup_path.resolve()
            backup_root_resolved = self.backup_root.resolve()
            if not backup_resolved.is_relative_to(backup_root_resolved):
                finished_at = datetime.now()
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=False,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message="Backup path is outside the configured backup root",
                    error="SecurityError: Backup path is outside backup_root",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    safety_backup_path=None,
                )
        except Exception as exc:  # pragma: no cover - unlikely
            finished_at = datetime.now()
            return RestoreResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message=f"Unable to validate backup path: {exc}",
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=None,
            )

        # Validate target directory exists or can be created
        original_parent = original_path.parent
        if not original_parent.exists():
            if not create_parents:
                finished_at = datetime.now()
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=False,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message="Target parent directory does not exist and create_parents is False",
                    error=None,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    safety_backup_path=None,
                )
            try:
                original_parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                finished_at = datetime.now()
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=False,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message=f"Cannot create target directory: {exc}",
                    error=f"{type(exc).__name__}: {exc}",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    safety_backup_path=None,
                )

        # Check if target already exists
        target_exists = original_path.exists()
        safety_backup_path = None
        target_original_hash = None  # hash of target before restore, if exists
        restore_attempted = False

        if target_exists and not overwrite:
            finished_at = datetime.now()
            return RestoreResult(
                status=BackupStatus.SKIPPED,
                success=False,
                executed=False,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message="Target file exists and overwrite is False",
                error=None,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=None,
            )

        # Handle overwrite with safety backup
        if target_exists and overwrite:
            try:
                # Calculate hash of existing target for safety verification
                target_original_hash = self._calculate_file_hash(original_path)
                # Create safety backup of existing target
                safety_backup_path = self._generate_backup_path(original_path)
                shutil.copy2(original_path, safety_backup_path)
                # Verify safety backup integrity
                safety_hash = self._calculate_file_hash(safety_backup_path)
                if target_original_hash != safety_hash:
                    # Safety backup failed - clean up and fail
                    try:
                        if safety_backup_path.exists():
                            safety_backup_path.unlink()
                    except OSError:
                        pass
                    finished_at = datetime.now()
                    return RestoreResult(
                        status=BackupStatus.FAILED,
                        success=False,
                        executed=False,
                        original_path=str(original_path),
                        backup_path=str(backup_path),
                        message="Safety backup integrity check failed: hash mismatch",
                        error="IntegrityError: Safety backup and original file hashes do not match",
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=(finished_at - started_at).total_seconds(),
                        safety_backup_path=None,
                    )
            except OSError as exc:
                finished_at = datetime.now()
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=False,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message=f"Failed to create safety backup: {exc}",
                    error=f"{type(exc).__name__}: {exc}",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    safety_backup_path=None,
                )

        # Perform restore using unique temporary file in same directory as target
        temp_path = None
        recovery_temp_path = None
        try:
            # Create a temporary file in the same directory
            fd, temp_path_str = tempfile.mkstemp(
                suffix=original_path.suffix, dir=original_parent, prefix=".tmp"
            )
            os.close(fd)  # we will write via shutil.copy2
            temp_path = Path(temp_path_str)

            restore_attempted = True
            shutil.copy2(backup_path, temp_path)

            # Verify restore integrity (backup vs temp)
            backup_hash = self._calculate_file_hash(backup_path)
            temp_hash = self._calculate_file_hash(temp_path)

            if backup_hash != temp_hash:
                # Hash mismatch - cleanup temp
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                except OSError:
                    pass

                finished_at = datetime.now()
                return RestoreResult(
                    status=BackupStatus.FAILED,
                    success=False,
                    executed=True,
                    original_path=str(original_path),
                    backup_path=str(backup_path),
                    message="Restore integrity check failed: hash mismatch (backup vs temp)",
                    error="IntegrityError: Backup and temporary file hashes do not match",
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=(finished_at - started_at).total_seconds(),
                    safety_backup_path=str(safety_backup_path) if safety_backup_path else None,
                )

            # Atomic replace
            if temp_path.exists():
                temp_path.replace(original_path)

            # Verify final restored target matches backup hash
            try:
                restored_hash = self._calculate_file_hash(original_path)
            except OSError as exc:
                # If we can't read the restored target, treat it as a verification failure
                restored_hash = None

            if backup_hash != restored_hash:
                # Final verification failed: attempt recovery
                finished_at = datetime.now()
                # If target existed before restore, we have safety_backup_path (verified)
                if target_exists and safety_backup_path is not None:
                    # Try to restore from safety backup via temporary file to avoid partial overwrite
                    try:
                        fd2, recovery_temp_path_str = tempfile.mkstemp(
                            suffix=original_path.suffix, dir=original_parent, prefix=".recovery.tmp"
                        )
                        os.close(fd2)
                        recovery_temp_path = Path(recovery_temp_path_str)

                        shutil.copy2(safety_backup_path, recovery_temp_path)
                        recovery_hash = self._calculate_file_hash(recovery_temp_path)
                        if target_original_hash == recovery_hash:
                            # Recovery succeeded, replace target
                            recovery_temp_path.replace(original_path)
                            # Recovery verified
                            return RestoreResult(
                                status=BackupStatus.FAILED,
                                success=False,
                                executed=True,
                                original_path=str(original_path),
                                backup_path=str(backup_path),
                                message="Final verification failed; recovered original from safety backup",
                                error="IntegrityError: Restored file does not match backup; recovered original",
                                started_at=started_at,
                                finished_at=finished_at,
                                duration_seconds=(finished_at - started_at).total_seconds(),
                                safety_backup_path=str(safety_backup_path),
                            )
                        else:
                            # Recovery also failed - cleanup recovery temp
                            try:
                                if recovery_temp_path.exists():
                                    recovery_temp_path.unlink()
                            except OSError:
                                pass
                            return RestoreResult(
                                status=BackupStatus.FAILED,
                                success=False,
                                executed=True,
                                original_path=str(original_path),
                                backup_path=str(backup_path),
                                message="Final verification failed; recovery failed to reproduce the original target",
                                error="IntegrityError: Recovery did not match original target",
                                started_at=started_at,
                                finished_at=finished_at,
                                duration_seconds=(finished_at - started_at).total_seconds(),
                                safety_backup_path=str(safety_backup_path),
                            )
                    except OSError as exc:
                        # Cleanup recovery temp if exists
                        if recovery_temp_path and recovery_temp_path.exists():
                            try:
                                recovery_temp_path.unlink()
                            except OSError:
                                pass
                        return RestoreResult(
                            status=BackupStatus.FAILED,
                            success=False,
                            executed=True,
                            original_path=str(original_path),
                            backup_path=str(backup_path),
                            message=f"Final verification failed; recovery attempt failed: {exc}",
                            error=f"{type(exc).__name__}: {exc}",
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_seconds=(finished_at - started_at).total_seconds(),
                            safety_backup_path=str(safety_backup_path) if safety_backup_path else None,
                        )
                else:
                    # No safety backup (target did not exist before); remove the bad restored target
                    try:
                        if original_path.exists():
                            original_path.unlink()
                    except OSError:
                        pass
                    return RestoreResult(
                        status=BackupStatus.FAILED,
                        success=False,
                        executed=True,
                        original_path=str(original_path),
                        backup_path=str(backup_path),
                        message="Final verification failed; removed corrupt target (no prior target)",
                        error="IntegrityError: Restored file does not match backup and no safety backup available",
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=(finished_at - started_at).total_seconds(),
                        safety_backup_path=None,
                    )

            # Success
            finished_at = datetime.now()
            return RestoreResult(
                status=BackupStatus.RESTORED,
                success=True,
                executed=True,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message="File restored successfully",
                error=None,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=str(safety_backup_path) if safety_backup_path else None,
            )

        except OSError as exc:
            finished_at = datetime.now()
            # Cleanup temp file if it exists
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass
            # Cleanup recovery temp if it exists
            if recovery_temp_path and recovery_temp_path.exists():
                try:
                    recovery_temp_path.unlink()
                except OSError:
                    pass

            return RestoreResult(
                status=BackupStatus.FAILED,
                success=False,
                executed=restore_attempted,
                original_path=str(original_path),
                backup_path=str(backup_path),
                message=f"Restore operation failed: {exc}",
                error=f"{type(exc).__name__}: {exc}",
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=(finished_at - started_at).total_seconds(),
                safety_backup_path=str(safety_backup_path) if safety_backup_path else None,
            )