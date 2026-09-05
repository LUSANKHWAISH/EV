"""
Minimal read-only agent/orchestration layer for E.V.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from .models import (
    AgentTask,
    AgentAction,
    AgentStatus,
    AgentStepResult,
    AgentRunResult,
    ExecutionStatus,
    ExecutionResult,
    EVEventType,
    EVEventSeverity,
    VerificationType,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
    sanitize_metadata,
)
from .cancellation import CancellationToken
from .verifier import EVVerifier
from .history import EVTaskHistoryStore
from .events import EVEventBus
from .backup import EVBackupManager
from tools.processes import find_processes, stop_process, list_processes
from tools.network import find_tcp_port, flush_dns
from tools.services import find_services, restart_service
from tools.filesystem import (
    get_file_info,
    list_directory,
    read_text_file,
    find_files,
    search_text,
    write_file,
    delete_file,
    validate_sandbox_path,
)

logger = logging.getLogger(__name__)

# Deterministic idempotency classification matrix (Task 016 Part F)
IS_ACTION_IDEMPOTENT: Dict[AgentAction, bool] = {
    AgentAction.FIND_PROCESS: True,
    AgentAction.FIND_TCP_PORT: True,
    AgentAction.GET_FILE_INFO: True,
    AgentAction.LIST_DIRECTORY: True,
    AgentAction.READ_TEXT_FILE: True,
    AgentAction.FIND_FILES: True,
    AgentAction.SEARCH_TEXT: True,
    AgentAction.FIND_SERVICE: True,
    AgentAction.WRITE_FILE: True,
    AgentAction.DELETE_FILE: True,
    AgentAction.FLUSH_DNS: True,
    AgentAction.STOP_PROCESS: False,   # Terminating a process by PID is non-idempotent
    AgentAction.RESTART_SERVICE: False, # Service bouncing can disrupt dependencies
}


class EVAgent:
    """Agent that dispatches to approved observation and reversible mutating capabilities."""

    def _get_handler(self, action: AgentAction):
        """Return the current approved function for the action."""
        if action == AgentAction.FIND_PROCESS:
            return find_processes
        if action == AgentAction.FIND_TCP_PORT:
            return find_tcp_port
        if action == AgentAction.FIND_SERVICE:
            return find_services
        if action == AgentAction.GET_FILE_INFO:
            return get_file_info
        if action == AgentAction.LIST_DIRECTORY:
            return list_directory
        if action == AgentAction.READ_TEXT_FILE:
            return read_text_file
        if action == AgentAction.FIND_FILES:
            return find_files
        if action == AgentAction.SEARCH_TEXT:
            return search_text
        if action == AgentAction.WRITE_FILE:
            return write_file
        if action == AgentAction.DELETE_FILE:
            return delete_file
        if action == AgentAction.STOP_PROCESS:
            return stop_process
        if action == AgentAction.RESTART_SERVICE:
            return restart_service
        if action == AgentAction.FLUSH_DNS:
            return flush_dns
        raise ValueError(f"Unsupported action: {action}")

    def _format_result_summary(self, action: AgentAction, result: Any) -> str:
        """Create a concise, human-readable string representation of the raw task result."""
        if result is None:
            return f"{action.value}: finished"

        if isinstance(result, list):
            if not result:
                return f"{action.value}: 0 results found."

            # Take up to 3 items for a concise summary
            summary = f"{action.value}: {len(result)} items found.\n"
            for item in result[:3]:
                if hasattr(item, 'name'):
                    summary += f"- {item.name}"
                    if hasattr(item, 'pid'):
                        summary += f" (PID: {item.pid})"
                    elif hasattr(item, 'size_bytes') and item.size_bytes is not None:
                        summary += f" ({item.size_bytes} bytes)"
                    summary += "\n"
                else:
                    summary += f"- {str(item)[:50]}\n"
            if len(result) > 3:
                summary += f"... and {len(result) - 3} more."
            return summary.strip()

        # Fallback for non-list results
        return f"{action.value}: {str(result)[:150]}"

    def _format_verification_message(
        self,
        verification_type: VerificationType,
        v_result: VerificationResult,
        target_name: str,
    ) -> str:
        """Create a concise human-readable verification message for HUD display."""
        status = v_result.status
        vtype = verification_type.value

        if status == VerificationStatus.VERIFIED:
            return f"VERIFIED: {vtype} — {target_name}"
        elif status == VerificationStatus.NOT_VERIFIED:
            return f"VERIFICATION FAILED: {vtype} — {target_name} — {v_result.message}"
        elif status == VerificationStatus.INDETERMINATE:
            return f"VERIFICATION INDETERMINATE: {vtype} — {target_name} — {v_result.message}"
        else:
            return f"VERIFICATION ERROR: {vtype} — {target_name} — {v_result.message}"

    def _get_tool_params(self, parameters: dict) -> dict:
        """Return a copy of parameters with resolver metadata stripped out.

        The resolver embeds 'verification_type' and verification expectations into
        the parameters dict. The tools don't accept these kwargs, so we strip them
        before dispatching.
        """
        ignored_keys = {"verification_type", "expected_text"}
        return {k: v for k, v in parameters.items() if k not in ignored_keys}

    def _extract_target_name(self, task: AgentTask) -> str:
        """Extract a human-readable target name from the task parameters."""
        if "name" in task.parameters:
            return task.parameters["name"]
        if "path" in task.parameters:
            return task.parameters["path"]
        if "port" in task.parameters:
            return str(task.parameters["port"])
        return "unknown"

    def run(
        self,
        task: AgentTask,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AgentRunResult:
        """
        Execute an approved agent task with structured execution and verification tracking.
        Returns AgentRunResult with execution status, verification results, and optional step details.

        Enforces:
        - Cancellation checks before dispatch and before verification.
        - Idempotency & retry_allowed semantics.
        - Timeout detection mapping to ExecutionStatus.UNKNOWN on mutating operations.
        - Observation-only safe state resolution.
        - Execution succeeded + Verification failed = OVERALL FAILURE.
        """
        started_at = datetime.now()
        self._history("record_task", task)
        self._history("mark_started", task.task_id, started_at=started_at)
        logger.info(
            "Agent task started: task_id=%s action=%s verification=%s",
            task.task_id,
            task.action.value,
            task.verification_type.value if task.verification_type else "none",
        )

        # 1. Pre-dispatch cooperative cancellation check
        if cancellation_token and cancellation_token.is_cancelled():
            cancel_reason = cancellation_token.state.reason or "Cancelled before dispatch"
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            logger.info("Task %s cancelled before dispatch: %s", task.task_id, cancel_reason)
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.CANCELLED,
                error=cancel_reason,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=cancel_reason,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=cancel_reason,
                ),
                execution=exec_res,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: cancelled before dispatch",
                data={"task_id": task.task_id, "action": task.action.value, "status": "CANCELLED"},
            )
            self._history("record_run", task, result)
            return result

        # 2. Publish ACTION_ACCEPTED
        self._publish_event(
            event_type=EVEventType.ACTION_ACCEPTED,
            correlation_id=task.task_id,
            message=f"{task.action.value}: accepted",
            data={"task_id": task.task_id, "action": task.action.value},
        )

        # 3. Publish ACTION_STARTED
        self._publish_event(
            event_type=EVEventType.ACTION_STARTED,
            correlation_id=task.task_id,
            message=f"{task.action.value}: started",
            data={"task_id": task.task_id, "action": task.action.value},
        )

        # Validate action is supported via whitelist
        try:
            handler = self._get_handler(task.action)
        except ValueError as ve:
            error_msg = str(ve)
            logger.error("Agent task failed: %s", error_msg)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.FAILED,
                error=error_msg,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=error_msg,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=error_msg,
                ),
                execution=exec_res,
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=error_msg,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (unsupported)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                },
            )
            self._history("record_run", task, result)
            return result

        # Validate parameters based on action
        validation_error = self._validate_parameters(task.action, task.parameters)
        if validation_error:
            logger.error("Agent task failed: %s", validation_error)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.FAILED,
                error=validation_error,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=validation_error,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=validation_error,
                ),
                execution=exec_res,
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=validation_error,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (validation)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                },
            )
            self._history("record_run", task, result)
            return result

        # Execute the approved action
        is_file_mutation = task.action in (AgentAction.WRITE_FILE, AgentAction.DELETE_FILE)
        is_mutation = task.action in (
            AgentAction.WRITE_FILE,
            AgentAction.DELETE_FILE,
            AgentAction.STOP_PROCESS,
            AgentAction.RESTART_SERVICE,
            AgentAction.FLUSH_DNS,
        )
        backup_record_res = None
        target_path_obj = None
        target_existed_before = False

        if is_file_mutation:
            raw_path = task.parameters.get("path")
            try:
                target_path_obj = validate_sandbox_path(raw_path, allowed_roots=self._allowed_roots)
                target_existed_before = target_path_obj.exists()
            except Exception as exc:
                validation_error = f"Sandbox validation failed: {exc}"
                logger.error("Agent task failed: %s", validation_error)
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
                exec_res = ExecutionResult(
                    action_id=task.task_id,
                    step_id=task.parameters.get("step_id"),
                    action_type=task.action,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration=duration,
                    status=ExecutionStatus.FAILED,
                    error=validation_error,
                    metadata=sanitize_metadata(task.parameters),
                    retry_allowed=False,
                )
                result = AgentRunResult(
                    task_id=task.task_id,
                    status=AgentStatus.FAILED,
                    error=validation_error,
                    step=AgentStepResult(
                        action=task.action,
                        success=False,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=duration,
                        error=validation_error,
                    ),
                    execution=exec_res,
                )
                self._publish_event(
                    event_type=EVEventType.STATUS,
                    correlation_id=task.task_id,
                    message=validation_error,
                )
                self._publish_event(
                    event_type=EVEventType.ACTION_COMPLETED,
                    correlation_id=task.task_id,
                    message=f"{task.action.value}: failed (sandbox validation)",
                    data={
                        "task_id": task.task_id,
                        "action": task.action.value,
                        "success": False,
                        "duration_seconds": duration,
                    },
                )
                self._history("record_run", task, result)
                return result

            # Pre-execution backup if target file exists
            if target_existed_before:
                backup_record_res = self._backup_manager.backup_file(target_path_obj)
                self._history("attach_backup", task.task_id, backup_record_res)
                if not backup_record_res.success:
                    backup_err = f"Pre-execution backup failed: {backup_record_res.error or backup_record_res.message}"
                    logger.error("Agent task failed: %s", backup_err)
                    finished_at = datetime.now()
                    duration = (finished_at - started_at).total_seconds()
                    exec_res = ExecutionResult(
                        action_id=task.task_id,
                        step_id=task.parameters.get("step_id"),
                        action_type=task.action,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration=duration,
                        status=ExecutionStatus.FAILED,
                        error=backup_err,
                        metadata=sanitize_metadata(task.parameters),
                        retry_allowed=False,
                    )
                    result = AgentRunResult(
                        task_id=task.task_id,
                        status=AgentStatus.FAILED,
                        error=backup_err,
                        step=AgentStepResult(
                            action=task.action,
                            success=False,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_seconds=duration,
                            error=backup_err,
                        ),
                        execution=exec_res,
                    )
                    self._publish_event(
                        event_type=EVEventType.STATUS,
                        correlation_id=task.task_id,
                        message=backup_err,
                    )
                    self._publish_event(
                        event_type=EVEventType.ACTION_COMPLETED,
                        correlation_id=task.task_id,
                        message=f"{task.action.value}: failed (backup error)",
                        data={
                            "task_id": task.task_id,
                            "action": task.action.value,
                            "success": False,
                            "duration_seconds": duration,
                        },
                    )
                    self._history("record_run", task, result)
                    return result

        try:
            tool_params = self._get_tool_params(task.parameters)
            if is_file_mutation and self._allowed_roots is not None and "allowed_roots" not in tool_params:
                tool_params["allowed_roots"] = self._allowed_roots
            evidence = handler(**tool_params)

            # Check if execution timed out or produced an ambiguous outcome (Task 016 Part E & I)
            is_timed_out = getattr(evidence, "timed_out", False) or (
                hasattr(evidence, "error") and evidence.error and "timed out" in str(evidence.error).lower()
            )

            if is_timed_out and is_mutation:
                logger.warning(
                    "Mutating action %s timed out; entering UNKNOWN state for safe observation",
                    task.action.value,
                )
                obs_resolution = self._observe_unknown_mutation(task, target_path_obj)
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()

                if obs_resolution == "RESOLVED_SUCCESS":
                    logger.info("Mutating action %s timeout resolved to SUCCESS via safe observation", task.action.value)
                    if hasattr(evidence, "success"):
                        evidence.success = True
                else:
                    # Unresolved or still failed -> status UNKNOWN, retry_allowed = False
                    error_msg = f"{task.action.value} execution timed out; Windows state is UNKNOWN ({obs_resolution})"
                    exec_res = ExecutionResult(
                        action_id=task.task_id,
                        step_id=task.parameters.get("step_id"),
                        action_type=task.action,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration=duration,
                        status=ExecutionStatus.UNKNOWN,
                        result=evidence,
                        error=error_msg,
                        metadata=sanitize_metadata(task.parameters),
                        retry_allowed=False,  # Never blindly retry unknown mutating action
                        verification_status=VerificationStatus.UNKNOWN,
                    )
                    v_res = VerificationResult(
                        verification_type=task.verification_type or VerificationType.NONE,
                        status=VerificationStatus.UNKNOWN,
                        success=False,
                        message=error_msg,
                        timestamp=datetime.now(),
                    )
                    result = AgentRunResult(
                        task_id=task.task_id,
                        status=AgentStatus.FAILED,
                        error=error_msg,
                        step=AgentStepResult(
                            action=task.action,
                            success=False,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_seconds=duration,
                            error=error_msg,
                            result=evidence,
                        ),
                        execution=exec_res,
                        verification=v_res,
                    )
                    self._publish_event(
                        event_type=EVEventType.ACTION_UNKNOWN,
                        correlation_id=task.task_id,
                        message=error_msg,
                        data={"task_id": task.task_id, "action": task.action.value, "retry_allowed": False},
                    )
                    self._publish_event(
                        event_type=EVEventType.ACTION_COMPLETED,
                        correlation_id=task.task_id,
                        message=error_msg,
                        data={
                            "task_id": task.task_id,
                            "action": task.action.value,
                            "success": False,
                            "execution_status": "UNKNOWN",
                            "retry_allowed": False,
                            "duration_seconds": duration,
                        },
                    )
                    self._history("record_run", task, result)
                    return result

            # Check if mutating tool itself reported failure
            if is_mutation and hasattr(evidence, "success") and not evidence.success:
                error_msg = getattr(evidence, "error", "Action failed")
                restore_res = self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
                if restore_res is not None and not restore_res.success:
                    restore_err_detail = restore_res.error or restore_res.message or "restore failed"
                    error_msg = f"{error_msg} | Recovery restore failed: {restore_err_detail}"

                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
                exec_res = ExecutionResult(
                    action_id=task.task_id,
                    step_id=task.parameters.get("step_id"),
                    action_type=task.action,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration=duration,
                    status=ExecutionStatus.FAILED,
                    result=evidence,
                    error=error_msg,
                    metadata=sanitize_metadata(task.parameters),
                    retry_allowed=IS_ACTION_IDEMPOTENT.get(task.action, False),
                )
                result = AgentRunResult(
                    task_id=task.task_id,
                    status=AgentStatus.FAILED,
                    error=error_msg,
                    step=AgentStepResult(
                        action=task.action,
                        success=False,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=duration,
                        error=error_msg,
                        result=evidence,
                    ),
                    execution=exec_res,
                )
                self._publish_event(
                    event_type=EVEventType.STATUS,
                    correlation_id=task.task_id,
                    message=error_msg,
                )
                self._publish_event(
                    event_type=EVEventType.ACTION_COMPLETED,
                    correlation_id=task.task_id,
                    message=f"{task.action.value}: failed ({error_msg})",
                    data={
                        "task_id": task.task_id,
                        "action": task.action.value,
                        "success": False,
                        "duration_seconds": duration,
                    },
                )
                self._history("record_run", task, result)
                return result

            # Pre-verification cooperative cancellation check (Task 016 Part H)
            if cancellation_token and cancellation_token.is_cancelled():
                cancel_err = cancellation_token.state.reason or "Cancelled before verification"
                if is_mutation:
                    self._rollback_if_needed(
                        task=task,
                        target_path_obj=target_path_obj,
                        target_existed_before=target_existed_before,
                        backup_record_res=backup_record_res,
                    )
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
                exec_res = ExecutionResult(
                    action_id=task.task_id,
                    step_id=task.parameters.get("step_id"),
                    action_type=task.action,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration=duration,
                    status=ExecutionStatus.CANCELLED,
                    error=cancel_err,
                    metadata=sanitize_metadata(task.parameters),
                    retry_allowed=False,
                )
                result = AgentRunResult(
                    task_id=task.task_id,
                    status=AgentStatus.FAILED,
                    error=cancel_err,
                    step=AgentStepResult(
                        action=task.action,
                        success=False,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration_seconds=duration,
                        error=cancel_err,
                    ),
                    execution=exec_res,
                )
                self._publish_event(
                    event_type=EVEventType.ACTION_COMPLETED,
                    correlation_id=task.task_id,
                    message=f"{task.action.value}: cancelled before verification",
                    data={"task_id": task.task_id, "action": task.action.value, "status": "CANCELLED"},
                )
                self._history("record_run", task, result)
                return result

            # -----------------------------------------------------------
            # Verification branch: if task carries a verification_type,
            # pass the observation/action evidence through EVVerifier.
            # -----------------------------------------------------------
            if task.verification_type is not None:
                return self._run_verification(
                    task=task,
                    evidence=evidence,
                    started_at=started_at,
                    is_mutation=is_mutation,
                    is_file_mutation=is_file_mutation,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                    cancellation_token=cancellation_token,
                )

            # -----------------------------------------------------------
            # Non-verification (standard observation / execution) branch:
            # -----------------------------------------------------------
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            logger.info(
                "Agent task completed: task_id=%s action=%s duration=%.3fs",
                task.task_id,
                task.action.value,
                duration,
            )
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.SUCCEEDED,
                result=evidence,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=IS_ACTION_IDEMPOTENT.get(task.action, True),
                verification_status=VerificationStatus.NOT_APPLICABLE,
            )
            v_res = VerificationResult(
                verification_type=VerificationType.NONE,
                status=VerificationStatus.NOT_APPLICABLE,
                success=True,
                message="Verification not applicable for this action",
                timestamp=datetime.now(),
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.COMPLETED,
                step=AgentStepResult(
                    action=task.action,
                    success=True,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    result=evidence,
                ),
                execution=exec_res,
                verification=v_res,
            )
            if is_mutation:
                if is_file_mutation:
                    b_path = backup_record_res.backup_path if backup_record_res else None
                    b_sha = (
                        backup_record_res.backup_record.sha256
                        if (backup_record_res and backup_record_res.backup_record)
                        else None
                    )
                    self._task_mutations[task.task_id] = {
                        "target_path": str(target_path_obj) if target_path_obj else task.parameters.get("path"),
                        "target_existed_before": target_existed_before,
                        "backup_path": b_path,
                        "original_sha256": b_sha,
                        "action": task.action,
                        "is_compensable": True,
                    }
                else:
                    self._task_mutations[task.task_id] = {
                        "target_path": None,
                        "target_existed_before": False,
                        "backup_path": None,
                        "original_sha256": None,
                        "action": task.action,
                        "is_compensable": False,
                    }
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=f"{task.action.value}: completed successfully",
            )
            obs_message = self._format_result_summary(task.action, result.step.result)

            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=obs_message,
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": True,
                    "duration_seconds": duration,
                },
            )
            self._history("record_run", task, result)
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent task error: task_id=%s action=%s", task.task_id, task.action.value)
            error_msg = f"{type(exc).__name__}: {exc}"
            is_timeout_exc = isinstance(exc, TimeoutError) or "timed out" in str(exc).lower()

            if is_mutation and is_timeout_exc:
                logger.warning("Mutating action %s timed out with exception; checking safe observation", task.action.value)
                obs_resolution = self._observe_unknown_mutation(task, target_path_obj)
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
                if obs_resolution == "RESOLVED_SUCCESS":
                    logger.info("Mutating action %s timeout resolved to SUCCESS via safe observation", task.action.value)
                    exec_res = ExecutionResult(
                        action_id=task.task_id,
                        step_id=task.parameters.get("step_id"),
                        action_type=task.action,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration=duration,
                        status=ExecutionStatus.SUCCEEDED,
                        metadata=sanitize_metadata(task.parameters),
                        retry_allowed=IS_ACTION_IDEMPOTENT.get(task.action, False),
                        verification_status=VerificationStatus.VERIFIED,
                    )
                    v_res = VerificationResult(
                        verification_type=task.verification_type or VerificationType.NONE,
                        status=VerificationStatus.VERIFIED,
                        success=True,
                        message=f"Mutating action {task.action.value} timeout resolved to success via observation",
                        timestamp=datetime.now(),
                    )
                    result = AgentRunResult(
                        task_id=task.task_id,
                        status=AgentStatus.COMPLETED,
                        step=AgentStepResult(
                            action=task.action,
                            success=True,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_seconds=duration,
                            result={"resolved_via_observation": True},
                        ),
                        execution=exec_res,
                        verification=v_res,
                    )
                    self._publish_event(
                        event_type=EVEventType.ACTION_COMPLETED,
                        correlation_id=task.task_id,
                        message=f"{task.action.value}: completed (resolved via observation)",
                        data={"task_id": task.task_id, "action": task.action.value, "success": True},
                    )
                    self._history("record_run", task, result)
                    return result
                else:
                    # Ambiguous/unknown outcome: do not rollback blindly if state cannot be confirmed, stop further mutation
                    error_msg = f"{task.action.value} timed out: {exc}; state is UNKNOWN ({obs_resolution})"
                    exec_res = ExecutionResult(
                        action_id=task.task_id,
                        step_id=task.parameters.get("step_id"),
                        action_type=task.action,
                        started_at=started_at,
                        finished_at=finished_at,
                        duration=duration,
                        status=ExecutionStatus.UNKNOWN,
                        error=error_msg,
                        metadata=sanitize_metadata(task.parameters),
                        retry_allowed=False,
                        verification_status=VerificationStatus.UNKNOWN,
                    )
                    v_res = VerificationResult(
                        verification_type=task.verification_type or VerificationType.NONE,
                        status=VerificationStatus.UNKNOWN,
                        success=False,
                        message=error_msg,
                        timestamp=datetime.now(),
                    )
                    result = AgentRunResult(
                        task_id=task.task_id,
                        status=AgentStatus.FAILED,
                        error=error_msg,
                        step=AgentStepResult(
                            action=task.action,
                            success=False,
                            started_at=started_at,
                            finished_at=finished_at,
                            duration_seconds=duration,
                            error=error_msg,
                        ),
                        execution=exec_res,
                        verification=v_res,
                    )
                    self._publish_event(
                        event_type=EVEventType.ACTION_UNKNOWN,
                        correlation_id=task.task_id,
                        message=error_msg,
                        severity=EVEventSeverity.WARNING,
                        data={"task_id": task.task_id, "action": task.action.value, "error": error_msg},
                    )
                    self._history("record_run", task, result)
                    return result

            if is_mutation:
                restore_res = self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
                if restore_res is not None and not restore_res.success:
                    restore_err_detail = restore_res.error or restore_res.message or "restore failed"
                    error_msg = f"{error_msg} | Recovery restore failed: {restore_err_detail}"

            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.FAILED,
                error=error_msg,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=error_msg,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=error_msg,
                ),
                execution=exec_res,
            )
            self._publish_event(
                event_type=EVEventType.STATUS,
                correlation_id=task.task_id,
                message=error_msg,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: failed (exception)",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                },
            )
            self._history("record_run", task, result)
            return result


    def _rollback_if_needed(
        self,
        task: AgentTask,
        target_path_obj: Optional[Any],
        target_existed_before: bool,
        backup_record_res: Optional[Any],
    ) -> Optional[Any]:
        """Trigger deterministic rollback and recovery when a mutation fails.

        Guarantees idempotency: executes recovery at most once per task execution.
        """
        task_id = task.task_id
        if task_id in self._recovered_tasks:
            logger.debug("Rollback already attempted for task %s; skipping duplicate", task_id)
            return self._recovered_tasks[task_id]

        self._set_state_safe("RECOVERING")
        restore_res = None

        if backup_record_res and backup_record_res.success and backup_record_res.backup_path:
            restore_res = self._backup_manager.restore_file(
                backup_path=backup_record_res.backup_path,
                original_path=target_path_obj,
                overwrite=True,
            )
            self._history("attach_restore", task.task_id, restore_res)
            self._publish_event(
                event_type=EVEventType.RECOVERY_RESULT,
                correlation_id=task.task_id,
                message=f"Rollback recovery: {restore_res.message}",
                data={
                    "task_id": task.task_id,
                    "success": restore_res.success,
                    "backup_path": restore_res.backup_path,
                    "original_path": restore_res.original_path,
                },
            )
        elif not target_existed_before and target_path_obj and target_path_obj.exists():
            try:
                target_path_obj.unlink()
            except OSError:
                pass

        self._recovered_tasks[task_id] = restore_res
        return restore_res

    def _observe_unknown_mutation(self, task: AgentTask, target_path_obj: Optional[Any] = None) -> str:
        """
        Observation-only inspection to safely resolve ambiguous/timeout mutation outcomes.
        Never executes mutations. Never retries mutating calls.
        """
        try:
            if task.action == AgentAction.STOP_PROCESS:
                pid = task.parameters.get("pid")
                proc_name = task.parameters.get("process_name") or task.parameters.get("name")
                if pid:
                    all_procs = list_processes()
                    matching = [p for p in all_procs if p.pid == pid]
                    if not matching:
                        return "RESOLVED_SUCCESS"
                    return f"PROCESS_STILL_RUNNING (PID {pid})"
                elif proc_name:
                    matches = find_processes(proc_name)
                    if not matches:
                        return "RESOLVED_SUCCESS"
                    return f"PROCESS_STILL_RUNNING ({proc_name})"
            elif task.action == AgentAction.RESTART_SERVICE:
                name = task.parameters.get("name")
                if name:
                    matches = find_services(name)
                    if matches and matches[0].status and matches[0].status.lower() == "running":
                        return "RESOLVED_SUCCESS"
                    current = matches[0].status if matches else "NOT_FOUND"
                    return f"SERVICE_NOT_RUNNING (current: {current})"
            elif task.action == AgentAction.WRITE_FILE:
                raw_path = task.parameters.get("path")
                from pathlib import Path
                p = target_path_obj or Path(raw_path)
                if p.exists() and p.is_file():
                    expected_content = task.parameters.get("content")
                    if expected_content is not None:
                        try:
                            actual = p.read_text(encoding=task.parameters.get("encoding", "utf-8"))
                            if actual == expected_content:
                                return "RESOLVED_SUCCESS"
                        except Exception:
                            pass
                    else:
                        return "RESOLVED_SUCCESS"
                return "FILE_NOT_VERIFIED"
            elif task.action == AgentAction.DELETE_FILE:
                raw_path = task.parameters.get("path")
                from pathlib import Path
                p = target_path_obj or Path(raw_path)
                if not p.exists():
                    return "RESOLVED_SUCCESS"
                return "FILE_STILL_EXISTS"
            elif task.action == AgentAction.FLUSH_DNS:
                return "RESOLVED_SUCCESS"
        except Exception as exc:
            logger.debug("Error during safe observation of unknown mutation: %s", exc)
        return "OBSERVATION_UNRESOLVED"

    def _run_verification(
        self,
        task: AgentTask,
        evidence: Any,
        started_at: datetime,
        is_mutation: bool = False,
        is_file_mutation: bool = False,
        target_path_obj: Optional[Any] = None,
        target_existed_before: bool = False,
        backup_record_res: Optional[Any] = None,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AgentRunResult:
        # Pre-verification cancellation check
        if cancellation_token and cancellation_token.is_cancelled():
            cancel_err = cancellation_token.state.reason or "Cancelled before verification"
            if is_mutation:
                self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.CANCELLED,
                error=cancel_err,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=cancel_err,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=cancel_err,
                ),
                execution=exec_res,
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: cancelled before verification",
                data={"task_id": task.task_id, "action": task.action.value, "status": "CANCELLED"},
            )
            self._history("record_run", task, result)
            return result

        # Signal entry into VERIFYING state
        self._set_state_safe("VERIFYING")
        self._publish_event(
            event_type=EVEventType.ACTION_VERIFYING,
            correlation_id=task.task_id,
            message=f"{task.action.value}: verifying {task.verification_type.value if task.verification_type else ''}",
            data={"task_id": task.task_id, "action": task.action.value},
        )

        try:
            v_evidence = evidence
            if hasattr(evidence, "model_dump"):
                v_evidence = evidence.model_dump()
            elif hasattr(evidence, "dict"):
                v_evidence = evidence.dict()

            target_path_str = str(target_path_obj) if target_path_obj else task.parameters.get("path")

            # Gather deterministic observation evidence
            if task.verification_type in (
                VerificationType.FILE_EXISTS,
                VerificationType.FILE_NOT_EXISTS,
                VerificationType.DIRECTORY_EXISTS,
            ) and target_path_str:
                v_evidence = get_file_info(target_path_str)
            elif task.verification_type in (
                VerificationType.TEXT_CONTAINS,
                VerificationType.TEXT_NOT_CONTAINS,
                VerificationType.FILE_CONTENT_MATCH,
            ) and target_path_str:
                v_evidence = read_text_file(target_path_str)
            elif task.verification_type == VerificationType.READ_CONTENT_VALID:
                v_evidence = evidence
            elif task.verification_type == VerificationType.FILE_HASH_MATCH:
                v_evidence = evidence
            elif task.action == AgentAction.STOP_PROCESS:
                if task.verification_type == VerificationType.PROCESS_NOT_EXISTS:
                    proc_name = task.parameters.get("process_name") or task.parameters.get("name")
                    if proc_name:
                        v_evidence = find_processes(proc_name)
                    else:
                        all_procs = list_processes()
                        pid_val = task.parameters.get("pid")
                        v_evidence = [p for p in all_procs if p.pid == pid_val]
                elif task.verification_type == VerificationType.TCP_PORT_NOT_EXISTS and "port" in task.parameters:
                    v_evidence = find_tcp_port(int(task.parameters["port"]))
            elif task.verification_type == VerificationType.PROCESS_IDENTITY_VALID:
                if isinstance(evidence, list):
                    v_evidence = evidence
                else:
                    name_param = task.parameters.get("name") or task.parameters.get("process_name")
                    v_evidence = find_processes(name_param) if name_param else evidence
            elif task.verification_type in (VerificationType.SERVICE_RUNNING, VerificationType.SERVICE_STOPPED):
                service_name = task.parameters.get("name")
                if service_name:
                    v_evidence = find_services(service_name)
                else:
                    v_evidence = evidence

            expected_text = (
                task.parameters.get("expected_text")
                or task.parameters.get("text")
                or task.parameters.get("content")
            )
            expected_content = task.parameters.get("content") or task.parameters.get("expected_content")
            expected_sha256 = task.parameters.get("sha256") or task.parameters.get("expected_sha256")
            expected_bytes = task.parameters.get("expected_bytes")

            v_request = VerificationRequest(
                verification_type=task.verification_type,
                evidence=v_evidence,
                expected_text=expected_text,
                expected_content=expected_content,
                expected_sha256=expected_sha256,
                expected_bytes=expected_bytes,
            )
            v_result = self._verifier.verify(v_request)
        except Exception as exc:
            logger.exception(
                "Verification engine error: task_id=%s verification_type=%s",
                task.task_id,
                task.verification_type.value,
            )
            error_msg = f"Verification error: {type(exc).__name__}: {exc}"
            if is_mutation:
                restore_res = self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
                if restore_res is not None and not restore_res.success:
                    restore_err_detail = restore_res.error or restore_res.message or "restore failed"
                    error_msg = f"{error_msg} | Recovery restore failed: {restore_err_detail}"

            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            exec_res = ExecutionResult(
                action_id=task.task_id,
                step_id=task.parameters.get("step_id"),
                action_type=task.action,
                started_at=started_at,
                finished_at=finished_at,
                duration=duration,
                status=ExecutionStatus.FAILED,
                error=error_msg,
                metadata=sanitize_metadata(task.parameters),
                retry_allowed=False,
                verification_status=VerificationStatus.ERROR,
            )
            v_res = VerificationResult(
                verification_type=task.verification_type,
                status=VerificationStatus.ERROR,
                success=False,
                message=error_msg,
                timestamp=datetime.now(),
            )
            result = AgentRunResult(
                task_id=task.task_id,
                status=AgentStatus.FAILED,
                error=error_msg,
                step=AgentStepResult(
                    action=task.action,
                    success=False,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration,
                    error=error_msg,
                ),
                execution=exec_res,
                verification=v_res,
            )
            self._publish_event(
                event_type=EVEventType.VERIFICATION_RESULT,
                correlation_id=task.task_id,
                message=f"VERIFICATION ERROR: {task.verification_type.value} — {error_msg}",
                data={
                    "task_id": task.task_id,
                    "verification_type": task.verification_type.value,
                    "status": "ERROR",
                    "success": False,
                },
            )
            self._publish_event(
                event_type=EVEventType.ACTION_COMPLETED,
                correlation_id=task.task_id,
                message=f"{task.action.value}: verification error",
                data={
                    "task_id": task.task_id,
                    "action": task.action.value,
                    "success": False,
                    "duration_seconds": duration,
                },
            )
            self._history("record_run", task, result)
            return result

        # Verification completed — format and evaluate
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        target_name = self._extract_target_name(task)
        v_message = self._format_verification_message(
            task.verification_type, v_result, target_name
        )

        is_verified = (v_result.status == VerificationStatus.VERIFIED or v_result.status == VerificationStatus.NOT_APPLICABLE)
        restore_res = None

        if not is_verified:
            # Critical Task 016 rule: Execution succeeded + Verification failed = OVERALL FAILURE
            logger.warning(
                "Execution verification FAILED for task %s (status=%s): %s",
                task.task_id,
                v_result.status.value,
                v_result.message,
            )
            if is_mutation:
                restore_res = self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )

        agent_status = AgentStatus.COMPLETED if is_verified else AgentStatus.FAILED
        error_val = None
        if not is_verified:
            error_val = v_message
            if restore_res is not None and not restore_res.success:
                restore_err_detail = restore_res.error or restore_res.message or "restore failed"
                error_val = f"{v_message} | Recovery restore failed: {restore_err_detail}"

        # Determine execution status and retry eligibility
        if is_verified:
            exec_status = ExecutionStatus.SUCCEEDED
            retry_allowed = IS_ACTION_IDEMPOTENT.get(task.action, True)
        elif v_result.status in (VerificationStatus.UNKNOWN, VerificationStatus.INDETERMINATE):
            exec_status = ExecutionStatus.UNKNOWN
            retry_allowed = False  # Crucial rule: Never blindly retry unknown mutating action
        else:
            exec_status = ExecutionStatus.FAILED
            retry_allowed = IS_ACTION_IDEMPOTENT.get(task.action, False)

        logger.info(
            "Verification complete: task_id=%s type=%s status=%s duration=%.3fs",
            task.task_id,
            task.verification_type.value,
            v_result.status.value,
            duration,
        )

        exec_res = ExecutionResult(
            action_id=task.task_id,
            step_id=task.parameters.get("step_id"),
            action_type=task.action,
            started_at=started_at,
            finished_at=finished_at,
            duration=duration,
            status=exec_status,
            result=evidence,
            error=error_val,
            metadata=sanitize_metadata(task.parameters),
            retry_allowed=retry_allowed,
            verification_status=v_result.status,
        )

        result = AgentRunResult(
            task_id=task.task_id,
            status=agent_status,
            error=error_val,
            step=AgentStepResult(
                action=task.action,
                success=is_verified,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                result=v_result,
                error=error_val,
            ),
            execution=exec_res,
            verification=v_result,
        )

        if is_verified and is_mutation:
            if is_file_mutation:
                b_path = backup_record_res.backup_path if backup_record_res else None
                b_sha = (
                    backup_record_res.backup_record.sha256
                    if (backup_record_res and backup_record_res.backup_record)
                    else None
                )
                self._task_mutations[task.task_id] = {
                    "target_path": str(target_path_obj) if target_path_obj else task.parameters.get("path"),
                    "target_existed_before": target_existed_before,
                    "backup_path": b_path,
                    "original_sha256": b_sha,
                    "action": task.action,
                    "is_compensable": True,
                }
            else:
                self._task_mutations[task.task_id] = {
                    "target_path": None,
                    "target_existed_before": False,
                    "backup_path": None,
                    "original_sha256": None,
                    "action": task.action,
                    "is_compensable": False,
                }

        # Publish VERIFICATION_RESULT event
        self._publish_event(
            event_type=EVEventType.VERIFICATION_RESULT,
            correlation_id=task.task_id,
            message=v_message,
            data={
                "task_id": task.task_id,
                "verification_type": task.verification_type.value,
                "status": v_result.status.value,
                "success": v_result.success,
                "retry_allowed": retry_allowed,
            },
        )

        # Publish ACTION_UNKNOWN if outcome is unknown
        if exec_status == ExecutionStatus.UNKNOWN:
            self._publish_event(
                event_type=EVEventType.ACTION_UNKNOWN,
                correlation_id=task.task_id,
                message=f"{task.action.value}: outcome is UNKNOWN ({v_message})",
                data={"task_id": task.task_id, "action": task.action.value, "retry_allowed": False},
            )

        # Publish ACTION_COMPLETED
        self._publish_event(
            event_type=EVEventType.ACTION_COMPLETED,
            correlation_id=task.task_id,
            message=v_message,
            data={
                "task_id": task.task_id,
                "action": task.action.value,
                "verification_type": task.verification_type.value,
                "verification_status": v_result.status.value,
                "execution_status": exec_status.value,
                "success": is_verified,
                "retry_allowed": retry_allowed,
                "duration_seconds": duration,
            },
        )

        # Persist to history
        self._history("record_run", task, result)
        self._history("attach_verification", task.task_id, v_result)

        return result


    def _set_state_safe(self, state_name: str) -> None:
        """Attempt to set EVState via the event bus; swallow failures."""
        if self._event_bus is None:
            return
        try:
            from .models import EVState
            self._event_bus.set_state(EVState(state_name))
        except Exception:
            logger.exception("Failed to set state to %s", state_name)

    def _validate_parameters(self, action: AgentAction, params: Dict[str, Any]) -> Optional[str]:
        """Validate required parameters for each action."""
        if action == AgentAction.FIND_PROCESS:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "FIND_PROCESS requires non-empty string 'name'"
        elif action == AgentAction.FIND_SERVICE:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "FIND_SERVICE requires non-empty string 'name'"
        elif action == AgentAction.FIND_TCP_PORT:
            port = params.get("port")
            if not isinstance(port, int):
                return "FIND_TCP_PORT requires integer 'port'"
            if port < 1 or port > 65535:
                return "FIND_TCP_PORT port must be between 1 and 65535"
        elif action in (AgentAction.GET_FILE_INFO, AgentAction.LIST_DIRECTORY, AgentAction.READ_TEXT_FILE):
            path = params.get("path")
            if not path or not isinstance(path, str):
                return f"{action.value} requires string 'path'"
        elif action == AgentAction.READ_TEXT_FILE:
            max_bytes = params.get("max_bytes")
            if max_bytes is not None:
                if not isinstance(max_bytes, int) or max_bytes <= 0:
                    return "READ_TEXT_FILE max_bytes must be positive integer if provided"
        elif action == AgentAction.FIND_FILES:
            root = params.get("root")
            pattern = params.get("pattern")
            if not root or not isinstance(root, str):
                return "FIND_FILES requires string 'root'"
            if not pattern or not isinstance(pattern, str):
                return "FIND_FILES requires string 'pattern'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or max_results <= 0:
                    return "FIND_FILES max_results must be positive integer if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "FIND_FILES exclude_dirs must be list of strings if provided"
        elif action == AgentAction.SEARCH_TEXT:
            root_or_file = params.get("root_or_file")
            text = params.get("text")
            if not root_or_file or not isinstance(root_or_file, str):
                return "SEARCH_TEXT requires string 'root_or_file'"
            if not text or not isinstance(text, str) or not text.strip():
                return "SEARCH_TEXT requires non-empty string 'text'"
            max_results = params.get("max_results")
            if max_results is not None:
                if not isinstance(max_results, int) or max_results <= 0:
                    return "SEARCH_TEXT max_results must be positive integer if provided"
            case_insensitive = params.get("case_insensitive")
            if case_insensitive is not None and not isinstance(case_insensitive, bool):
                return "SEARCH_TEXT case_insensitive must be boolean if provided"
            exclude_dirs = params.get("exclude_dirs")
            if exclude_dirs is not None:
                if not isinstance(exclude_dirs, list) or not all(isinstance(d, str) for d in exclude_dirs):
                    return "SEARCH_TEXT exclude_dirs must be list of strings if provided"
        elif action == AgentAction.WRITE_FILE:
            path = params.get("path")
            content = params.get("content")
            if not path or not isinstance(path, str) or not path.strip():
                return "WRITE_FILE requires non-empty string 'path'"
            if len(path) > 1000:
                return "WRITE_FILE 'path' exceeds maximum length of 1000 characters"
            if content is None or not isinstance(content, str):
                return "WRITE_FILE requires string 'content'"
            if len(content) > 1024 * 1024:
                return "WRITE_FILE 'content' exceeds maximum allowed size of 1MB"
            encoding = params.get("encoding")
            if encoding is not None and not isinstance(encoding, str):
                return "WRITE_FILE 'encoding' must be string if provided"
            overwrite = params.get("overwrite")
            if overwrite is not None and not isinstance(overwrite, bool):
                return "WRITE_FILE 'overwrite' must be boolean if provided"
        elif action == AgentAction.DELETE_FILE:
            path = params.get("path")
            if not path or not isinstance(path, str) or not path.strip():
                return "DELETE_FILE requires non-empty string 'path'"
            if len(path) > 1000:
                return "DELETE_FILE 'path' exceeds maximum length of 1000 characters"
            missing_ok = params.get("missing_ok")
            if missing_ok is not None and not isinstance(missing_ok, bool):
                return "DELETE_FILE 'missing_ok' must be boolean if provided"
        elif action == AgentAction.STOP_PROCESS:
            pid = params.get("pid")
            if pid is None or not isinstance(pid, int) or pid <= 0:
                return "STOP_PROCESS requires positive integer 'pid'"
            process_name = params.get("process_name") or params.get("name")
            if process_name is not None and not isinstance(process_name, str):
                return "STOP_PROCESS 'process_name' must be string if provided"
        elif action == AgentAction.RESTART_SERVICE:
            name = params.get("name")
            if not name or not isinstance(name, str) or not name.strip():
                return "RESTART_SERVICE requires non-empty string 'name'"
        elif action == AgentAction.FLUSH_DNS:
            hostname = params.get("hostname")
            if hostname is not None and (not isinstance(hostname, str) or not hostname.strip()):
                return "FLUSH_DNS 'hostname' must be non-empty string if provided"
        return None

    def __init__(
        self,
        history_store: Optional[EVTaskHistoryStore] = None,
        event_bus: Optional[EVEventBus] = None,
        backup_manager: Optional[EVBackupManager] = None,
        allowed_roots: Optional[list] = None,
    ):
        self._history_store = history_store
        self._event_bus = event_bus
        self._verifier = EVVerifier()
        self._backup_manager = backup_manager or EVBackupManager()
        self._allowed_roots = allowed_roots
        self._recovered_tasks: Dict[str, Any] = {}
        self._task_mutations: Dict[str, Dict[str, Any]] = {}

    @property
    def backup_manager(self) -> EVBackupManager:
        """Return the configured EVBackupManager instance."""
        return self._backup_manager

    def get_task_mutation(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return the recorded mutation metadata for a completed task."""
        return self._task_mutations.get(task_id)

    @property
    def verifier(self) -> EVVerifier:
        """Return the configured EVVerifier instance."""
        return self._verifier

    def _publish_event(
        self,
        event_type: EVEventType,
        correlation_id: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        severity: EVEventSeverity = EVEventSeverity.INFO,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                event_type=event_type,
                source="agent",
                correlation_id=correlation_id,
                message=message,
                severity=severity,
                data=data,
            )
        except Exception:
            logger.exception("Agent telemetry publication failed")

    def _history(self, method, *args, **kwargs):
        if self._history_store is None:
            return
        try:
            getattr(self._history_store, method)(*args, **kwargs)
        except Exception:
            logger.exception("Agent task history persistence failed")
