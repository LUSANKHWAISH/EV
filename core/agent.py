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
    EVEventType,
    VerificationType,
    VerificationRequest,
    VerificationResult,
    VerificationStatus,
)
from .verifier import EVVerifier
from .history import EVTaskHistoryStore
from .events import EVEventBus
from .backup import EVBackupManager
from tools.processes import find_processes
from tools.network import find_tcp_port
from tools.services import find_services
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

        The resolver embeds 'verification_type' into the parameters dict for
        Task 004 compatibility. The observation tools don't accept this kwarg,
        so we strip it before dispatching.
        """
        return {k: v for k, v in parameters.items() if k != "verification_type"}

    def _extract_target_name(self, task: AgentTask) -> str:
        """Extract a human-readable target name from the task parameters."""
        if "name" in task.parameters:
            return task.parameters["name"]
        if "path" in task.parameters:
            return task.parameters["path"]
        if "port" in task.parameters:
            return str(task.parameters["port"])
        return "unknown"

    def run(self, task: AgentTask) -> AgentRunResult:
        """
        Execute a read-only agent task.
        Returns AgentRunResult with status and optional step details.

        If the task carries a verification_type, the observation result is
        passed through EVVerifier to produce a VerificationResult.
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
        self._publish_event(
            event_type=EVEventType.ACTION_STARTED,
            correlation_id=task.task_id,
            message=f"{task.action.value}: started",
            data={"task_id": task.task_id, "action": task.action.value}
        )

        # Validate action is supported via whitelist
        try:
            handler = self._get_handler(task.action)
        except ValueError as ve:
            error_msg = str(ve)
            logger.error("Agent task failed: %s", error_msg)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
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
                }
            )
            self._history("record_run", task, result)
            return result

        # Validate parameters based on action
        validation_error = self._validate_parameters(task.action, task.parameters)
        if validation_error:
            logger.error("Agent task failed: %s", validation_error)
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
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
                }
            )
            self._history("record_run", task, result)
            return result

        # Execute the approved action
        is_mutation = task.action in (AgentAction.WRITE_FILE, AgentAction.DELETE_FILE)
        backup_record_res = None
        target_path_obj = None
        target_existed_before = False

        if is_mutation:
            raw_path = task.parameters.get("path")
            try:
                target_path_obj = validate_sandbox_path(raw_path, allowed_roots=self._allowed_roots)
                target_existed_before = target_path_obj.exists()
            except Exception as exc:
                validation_error = f"Sandbox validation failed: {exc}"
                logger.error("Agent task failed: %s", validation_error)
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
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
                    }
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
                        }
                    )
                    self._history("record_run", task, result)
                    return result

        try:
            tool_params = self._get_tool_params(task.parameters)
            if is_mutation and self._allowed_roots is not None and "allowed_roots" not in tool_params:
                tool_params["allowed_roots"] = self._allowed_roots
            evidence = handler(**tool_params)

            # Check if mutating tool itself reported failure
            if is_mutation and hasattr(evidence, "success") and not evidence.success:
                error_msg = getattr(evidence, "error", "File action failed")
                self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
                finished_at = datetime.now()
                duration = (finished_at - started_at).total_seconds()
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
                    }
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
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
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
            )
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
                }
            )
            self._history("record_run", task, result)
            return result
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent task error: task_id=%s action=%s", task.task_id, task.action.value)
            if is_mutation:
                self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            error_msg = f"{type(exc).__name__}: {exc}"
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
                }
            )
            self._history("record_run", task, result)
            return result

    def _rollback_if_needed(
        self,
        task: AgentTask,
        target_path_obj: Optional[Any],
        target_existed_before: bool,
        backup_record_res: Optional[Any],
    ) -> None:
        """Trigger deterministic rollback and recovery when a mutation fails."""
        self._set_state_safe("RECOVERING")
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

    def _run_verification(
        self,
        task: AgentTask,
        evidence: Any,
        started_at: datetime,
        is_mutation: bool = False,
        target_path_obj: Optional[Any] = None,
        target_existed_before: bool = False,
        backup_record_res: Optional[Any] = None,
    ) -> AgentRunResult:
        # Signal entry into VERIFYING state
        self._set_state_safe("VERIFYING")

        try:
            v_evidence = evidence
            if is_mutation and target_path_obj is not None:
                if task.verification_type in (
                    VerificationType.FILE_EXISTS,
                    VerificationType.FILE_NOT_EXISTS,
                    VerificationType.DIRECTORY_EXISTS,
                ):
                    v_evidence = get_file_info(str(target_path_obj))
                elif task.verification_type in (
                    VerificationType.TEXT_CONTAINS,
                    VerificationType.TEXT_NOT_CONTAINS,
                ):
                    v_evidence = read_text_file(str(target_path_obj))

            expected_text = (
                task.parameters.get("expected_text")
                or task.parameters.get("text")
                or task.parameters.get("content")
            )
            v_request = VerificationRequest(
                verification_type=task.verification_type,
                evidence=v_evidence,
                expected_text=expected_text,
            )
            v_result = self._verifier.verify(v_request)
        except Exception as exc:
            # Verifier itself raised — treat as failed verification
            logger.exception(
                "Verification engine error: task_id=%s verification_type=%s",
                task.task_id,
                task.verification_type.value,
            )
            if is_mutation:
                self._rollback_if_needed(
                    task=task,
                    target_path_obj=target_path_obj,
                    target_existed_before=target_existed_before,
                    backup_record_res=backup_record_res,
                )
            finished_at = datetime.now()
            duration = (finished_at - started_at).total_seconds()
            error_msg = f"Verification error: {type(exc).__name__}: {exc}"

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

        # Verification completed — format and publish
        finished_at = datetime.now()
        duration = (finished_at - started_at).total_seconds()
        target_name = self._extract_target_name(task)
        v_message = self._format_verification_message(
            task.verification_type, v_result, target_name
        )

        is_success = v_result.status == VerificationStatus.VERIFIED
        if not is_success and is_mutation:
            self._rollback_if_needed(
                task=task,
                target_path_obj=target_path_obj,
                target_existed_before=target_existed_before,
                backup_record_res=backup_record_res,
            )

        agent_status = AgentStatus.COMPLETED if is_success else AgentStatus.FAILED

        logger.info(
            "Verification complete: task_id=%s type=%s status=%s duration=%.3fs",
            task.task_id,
            task.verification_type.value,
            v_result.status.value,
            duration,
        )

        result = AgentRunResult(
            task_id=task.task_id,
            status=agent_status,
            step=AgentStepResult(
                action=task.action,
                success=is_success,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration,
                result=v_result,
            ),
        )

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
            },
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
                "success": is_success,
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

    def _publish_event(
        self,
        event_type: EVEventType,
        correlation_id: str,
        message: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                event_type=event_type,
                source="agent",
                correlation_id=correlation_id,
                message=message,
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
