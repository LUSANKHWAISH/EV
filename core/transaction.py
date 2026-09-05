"""
Compound Task Transaction & Multi-Step LIFO Rollback Engine for E.V. (Phase 5 Task 007).

This module coordinates multi-step task execution transactions with deterministic
reverse-order (LIFO) compensating rollbacks upon failure.

Security Invariants:
1. Risk & Human Approval remain authoritative: every task in a transaction must pass
   EVRiskEngine and explicit user approval where required.
2. Brain remains advisory: transaction coordination is strictly deterministic.
3. Strict LIFO compensation: on step failure, all previously completed mutating steps
   are restored in reverse execution order.
4. Distinguishes COMMITTED, ROLLED_BACK, and ROLLBACK_FAILED. Rollback failures are
   never reported as success.
5. Non-mutating observation steps do not generate fake rollback records.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .backup import EVBackupManager
from .models import AgentAction, AgentTask

logger = logging.getLogger("ev.transaction")


class TransactionStatus(str, Enum):
    """Lifecycle states of a compound task execution transaction."""
    PENDING = "PENDING"
    EXECUTING = "EXECUTING"
    COMMITTED = "COMMITTED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    FAILED = "FAILED"


class CompensationStatus(str, Enum):
    """Deterministic compensation outcome states for a mutation step."""
    COMPENSATION_SUCCEEDED = "COMPENSATION_SUCCEEDED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"
    COMPENSATION_NOT_AVAILABLE = "COMPENSATION_NOT_AVAILABLE"


class ActionReversibility(str, Enum):
    """Action reversibility classification for transaction rollback capability."""
    REVERSIBLE = "REVERSIBLE"
    NON_REVERSIBLE = "NON_REVERSIBLE"


@dataclass
class StepCompensationRecord:
    """Record of a single mutation step within a transaction eligible for compensation."""
    step_index: int
    task_id: str
    action: AgentAction
    target_path: Optional[str] = None
    target_existed_before: bool = False
    backup_path: Optional[str] = None
    original_sha256: Optional[str] = None
    completed_at: datetime = field(default_factory=datetime.now)
    is_compensable: bool = True
    reversibility: ActionReversibility = ActionReversibility.REVERSIBLE
    compensated: bool = False
    compensation_status: Optional[CompensationStatus] = None
    compensation_error: Optional[str] = None


class CompoundTransaction:
    """
    Coordinates an ordered sequence of tasks as a single logical transaction
    with deterministic LIFO compensating rollback on execution or verification failure.
    """

    def __init__(
        self,
        tasks: List[AgentTask],
        transaction_id: Optional[str] = None,
    ) -> None:
        if not tasks:
            raise ValueError("CompoundTransaction requires a non-empty list of AgentTasks")
        self.transaction_id: str = transaction_id or f"tx-{uuid.uuid4().hex[:10]}"
        self.tasks: List[AgentTask] = list(tasks)
        self.status: TransactionStatus = TransactionStatus.PENDING
        self.completed_mutations: List[StepCompensationRecord] = []
        self.current_step_index: int = 0
        self.failed_step_index: Optional[int] = None
        self.failure_reason: Optional[str] = None
        self.rollback_records: List[Dict[str, Any]] = []
        self._lock = threading.RLock()
        self.created_at: datetime = datetime.now()
        self.finished_at: Optional[datetime] = None

    def begin(self) -> None:
        """Mark transaction as actively executing."""
        with self._lock:
            if self.status != TransactionStatus.PENDING:
                raise RuntimeError(f"Cannot begin transaction in status {self.status.value}")
            self.status = TransactionStatus.EXECUTING
            logger.info("Transaction %s started with %d task(s)", self.transaction_id, len(self.tasks))

    def record_mutation_step(
        self,
        step_index: int,
        task: AgentTask,
        target_path: Optional[str],
        target_existed_before: bool,
        backup_path: Optional[str] = None,
        original_sha256: Optional[str] = None,
        is_compensable: bool = True,
        reversibility: Optional[ActionReversibility] = None,
    ) -> StepCompensationRecord:
        """
        Record a successfully completed mutation step for future LIFO compensation.
        """
        with self._lock:
            # Deterministic sanitization: never treat None, "None", or empty string as valid path
            cleaned_target_path: Optional[str] = None
            if target_path is not None:
                s_path = str(target_path).strip()
                if s_path and s_path.lower() != "none":
                    cleaned_target_path = s_path

            # If no valid target path exists or explicitly marked non-compensable
            effective_is_compensable = bool(is_compensable)
            if cleaned_target_path is None:
                effective_is_compensable = False

            if reversibility is not None:
                effective_reversibility = reversibility
            elif effective_is_compensable:
                effective_reversibility = ActionReversibility.REVERSIBLE
            else:
                effective_reversibility = ActionReversibility.NON_REVERSIBLE

            record = StepCompensationRecord(
                step_index=step_index,
                task_id=task.task_id,
                action=task.action,
                target_path=cleaned_target_path,
                target_existed_before=target_existed_before,
                backup_path=str(backup_path) if backup_path else None,
                original_sha256=original_sha256,
                is_compensable=effective_is_compensable,
                reversibility=effective_reversibility,
            )
            self.completed_mutations.append(record)
            logger.debug(
                "Transaction %s recorded mutation step %d (task=%s, action=%s, existed=%s, compensable=%s, reversibility=%s)",
                self.transaction_id,
                step_index,
                task.task_id,
                task.action.value,
                target_existed_before,
                effective_is_compensable,
                effective_reversibility.value,
            )
            return record

    def commit(self) -> None:
        """Commit the transaction after all steps have succeeded and verified."""
        with self._lock:
            if self.status != TransactionStatus.EXECUTING:
                raise RuntimeError(f"Cannot commit transaction in status {self.status.value}")
            self.status = TransactionStatus.COMMITTED
            self.finished_at = datetime.now()
            logger.info(
                "Transaction %s COMMITTED successfully (%d mutation steps)",
                self.transaction_id,
                len(self.completed_mutations),
            )

    def rollback(
        self,
        backup_manager: EVBackupManager,
        failed_step_index: Optional[int] = None,
        failure_reason: Optional[str] = None,
    ) -> bool:
        """
        Execute deterministic LIFO compensating rollback of all completed mutation steps.

        Args:
            backup_manager: Authoritative EVBackupManager for restoring backups.
            failed_step_index: Index of the step that triggered the failure.
            failure_reason: Error description of the failure.

        Returns:
            True if all completed mutation steps were cleanly compensated (ROLLED_BACK).
            False if any compensation step failed or was non-compensable (ROLLBACK_FAILED).
        """
        with self._lock:
            self.status = TransactionStatus.ROLLING_BACK
            self.failed_step_index = failed_step_index
            self.failure_reason = failure_reason
            self.rollback_records.clear()

            all_clean = True
            logger.warning(
                "Transaction %s initiating LIFO rollback of %d completed mutation(s) (failure: %s)",
                self.transaction_id,
                len(self.completed_mutations),
                failure_reason,
            )

            # Iterate through completed mutations in strict reverse execution order (LIFO)
            for record in reversed(self.completed_mutations):
                step_success = False
                err_msg = None

                # 1. Non-compensable or missing path check: fail closed!
                if not record.is_compensable or not record.target_path:
                    step_success = False
                    err_msg = f"Step {record.step_index} ({record.action.value}) is non-reversible (is_compensable=False)"
                    logger.warning(
                        "Transaction %s cannot compensate step %d (%s): non-reversible action",
                        self.transaction_id,
                        record.step_index,
                        record.action.value,
                    )
                    record.compensated = False
                    record.compensation_status = CompensationStatus.COMPENSATION_NOT_AVAILABLE
                    record.compensation_error = err_msg
                    self.rollback_records.append({
                        "step_index": record.step_index,
                        "task_id": record.task_id,
                        "target_path": record.target_path,
                        "action": record.action.value,
                        "success": False,
                        "error": err_msg,
                        "compensation_status": CompensationStatus.COMPENSATION_NOT_AVAILABLE.value,
                        "is_compensable": False,
                    })
                    continue

                target_p = Path(record.target_path)

                try:
                    if record.target_existed_before and record.backup_path:
                        # Existing file modified/deleted -> restore from backup
                        restore_res = backup_manager.restore_file(
                            backup_path=record.backup_path,
                            original_path=target_p,
                            overwrite=True,
                            create_parents=True,
                        )
                        if restore_res.success:
                            step_success = True
                            record.compensation_status = CompensationStatus.COMPENSATION_SUCCEEDED
                            logger.info(
                                "Transaction %s compensated step %d (restored %s from %s)",
                                self.transaction_id,
                                record.step_index,
                                record.target_path,
                                record.backup_path,
                            )
                        else:
                            step_success = False
                            record.compensation_status = CompensationStatus.COMPENSATION_FAILED
                            err_msg = restore_res.error or restore_res.message or "Restore failed"
                            logger.error(
                                "Transaction %s failed to restore step %d (%s): %s",
                                self.transaction_id,
                                record.step_index,
                                record.target_path,
                                err_msg,
                            )
                    elif not record.target_existed_before:
                        # Newly created file -> remove/unlink it
                        if target_p.exists():
                            target_p.unlink()
                            step_success = True
                            record.compensation_status = CompensationStatus.COMPENSATION_SUCCEEDED
                            logger.info(
                                "Transaction %s compensated step %d (unlinked newly created file %s)",
                                self.transaction_id,
                                record.step_index,
                                record.target_path,
                            )
                        else:
                            # Already deleted or not present -> cleanly compensated
                            step_success = True
                            record.compensation_status = CompensationStatus.COMPENSATION_SUCCEEDED
                    else:
                        # Missing backup information for an existing file
                        step_success = False
                        record.compensation_status = CompensationStatus.COMPENSATION_FAILED
                        err_msg = f"Missing backup path for existing file {record.target_path}"
                        logger.error(
                            "Transaction %s compensation error on step %d: %s",
                            self.transaction_id,
                            record.step_index,
                            err_msg,
                        )

                except Exception as exc:
                    step_success = False
                    record.compensation_status = CompensationStatus.COMPENSATION_FAILED
                    err_msg = f"{type(exc).__name__}: {exc}"
                    logger.exception(
                        "Transaction %s unexpected exception compensating step %d: %s",
                        self.transaction_id,
                        record.step_index,
                        exc,
                    )

                record.compensated = step_success
                record.compensation_error = err_msg

                self.rollback_records.append({
                    "step_index": record.step_index,
                    "task_id": record.task_id,
                    "target_path": record.target_path,
                    "action": record.action.value,
                    "success": step_success,
                    "error": err_msg,
                    "compensation_status": record.compensation_status.value if record.compensation_status else CompensationStatus.COMPENSATION_FAILED.value,
                    "is_compensable": True,
                })

                if not step_success:
                    all_clean = False

            self.finished_at = datetime.now()
            if all_clean:
                self.status = TransactionStatus.ROLLED_BACK
                logger.info(
                    "Transaction %s LIFO rollback completed successfully (status=ROLLED_BACK)",
                    self.transaction_id,
                )
                return True
            else:
                self.status = TransactionStatus.ROLLBACK_FAILED
                logger.critical(
                    "Transaction %s LIFO rollback encountered failure(s) (status=ROLLBACK_FAILED)",
                    self.transaction_id,
                )
                return False
