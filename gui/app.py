# Main GUI entry point for E.V.
# Bootstrap application and load QML root.
import argparse
import logging
import os
from pathlib import Path
import re
import sys
import threading
from typing import Any, List, Optional, Tuple
import uuid

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from core.action_pipeline import ActionPipelineContext
from core.brain_provider import EVBrainProvider
from core.brain_provider_manager import EVBrainProviderManager
from core.brain_router import BrainRouter
from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.orchestrator import EVOrchestrator
from core.proactive_awareness import EVProactiveAwarenessEngine
from core.system_monitor import EVSystemMonitor
from gui.bridge import GuiBridge
from gui.windows_chrome import install_windows_native_chrome
from providers.gemini_provider import GeminiProvider
from providers.openai_compatible_provider import (
    AzureOpenAIProvider,
    OpenRouterProvider,
)

logger = logging.getLogger(__name__)

_MAX_RESULT_LENGTH: int = 500

_SENSITIVE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"AIzaSy[a-zA-Z0-9_\-]{30,}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}", re.IGNORECASE),
]

# Patterns that indicate a raw provider/API error dict was leaked into the error string.
_PROVIDER_ERROR_PATTERN = re.compile(
    r"\{\s*['\"]error['\"]\s*:\s*\{.*?['\"]code['\"]\s*:\s*(\d{3})",
    re.DOTALL | re.IGNORECASE,
)


def _sanitize_provider_error(text: str) -> str:
    """Replace raw provider JSON error dicts with concise user-facing messages."""
    if not text:
        return text

    # First check for JSON error dict match
    match = _PROVIDER_ERROR_PATTERN.search(text)
    http_code = match.group(1) if match else None

    # If not found via full JSON pattern, check if provider error mentions status codes or keywords
    if not http_code:
        if "503" in text or "UNAVAILABLE" in text:
            http_code = "503"
        elif "429" in text or "RESOURCE_EXHAUSTED" in text or "rate limit" in text.lower():
            http_code = "429"
        elif "401" in text or "403" in text or "unauthenticated" in text.lower() or "permission_denied" in text.lower():
            http_code = "401"

    # If any raw JSON pattern or provider error dictionary is detected, sanitize
    if http_code or "Brain provider error" in text or "{'error'" in text or '{"error"' in text:
        if http_code == "503":
            return "AI service temporarily unavailable (HTTP 503). Please try again shortly."
        elif http_code == "429":
            return "AI service rate limited (HTTP 429). Please wait a moment and try again."
        elif http_code in ("401", "403"):
            return "AI service authentication error. Check your API key configuration."
        elif http_code:
            return f"AI service error (HTTP {http_code}). Please try again shortly."
        elif "Brain provider error" in text or "{'error'" in text or '{"error"' in text:
            return "AI service error. Unable to process command with configured providers."

    return text


def _sanitize_result_text(text: str) -> str:
    """Sanitize and clamp string to prevent secret exposure or GUI overflow."""
    if not text:
        return ""
    sanitized = _sanitize_provider_error(text)
    for pat in _SENSITIVE_PATTERNS:
        sanitized = pat.sub("[REDACTED]", sanitized)
    if len(sanitized) > _MAX_RESULT_LENGTH:
        sanitized = sanitized[:_MAX_RESULT_LENGTH].rstrip() + "..."
    return sanitized


def _format_pipeline_result(result: Any) -> Tuple[str, str, bool]:
    """
    Deterministically format an ActionPipelineResult into a concise, safe,
    human-readable summary for the GUI presentation surface.
    Returns: (summary_text, status_str, success_bool)
    """
    if result is None:
        return ("Execution completed, but no result reference was returned.", "FAILED", False)

    try:
        # Check cancellation or user denial
        status_val = getattr(result.status, "value", str(getattr(result, "status", "") or ""))
        if status_val == "CANCELLED" or getattr(result, "approved", None) is False:
            err = getattr(result, "error", None) or "Task cancelled."
            return (_sanitize_result_text(err), "CANCELLED", False)

        # Check awaiting approval
        if status_val == "AWAITING_APPROVAL":
            goal = getattr(result.plan, "goal", "") if getattr(result, "plan", None) else getattr(result, "command_text", "")
            msg = f"Awaiting approval for: {goal}" if goal else "Awaiting human approval."
            return (_sanitize_result_text(msg), "AWAITING_APPROVAL", False)

        # Check rollback
        if getattr(result, "rolled_back", None) is True:
            raw_err = getattr(result, "error", None)
            if not raw_err and getattr(result, "plan", None):
                raw_err = getattr(result.plan, "error", None)
            err_text = raw_err or "Operation failed and was rolled back."
            return (_sanitize_result_text(f"Task rolled back: {err_text}"), "ROLLED_BACK", False)

        # Check failure
        overall_success = bool(getattr(result, "overall_success", False))
        if not overall_success or status_val in ("FAILED", "REJECTED"):
            raw_err = getattr(result, "error", None)
            if not raw_err and getattr(result, "plan", None):
                raw_err = getattr(result.plan, "error", None)
            err_text = raw_err or "Task execution failed."
            return (_sanitize_result_text(f"Task failed: {err_text}"), "FAILED", False)

        # Overall success
        plan = getattr(result, "plan", None)
        if plan is None:
            cmd = getattr(result, "command_text", "")
            return (_sanitize_result_text(f"Task completed successfully: {cmd}" if cmd else "Task completed successfully."), "SUCCESS", True)

        steps = getattr(plan, "steps", None) or []
        if not steps:
            goal = getattr(plan, "goal", "") or getattr(result, "command_text", "")
            return (_sanitize_result_text(f"Task completed: {goal}" if goal else "Task completed successfully."), "SUCCESS", True)

        # If single step, produce specific concise summary
        if len(steps) == 1:
            step = steps[0]
            action_name = getattr(step.action, "value", str(getattr(step, "action", "")))
            params = getattr(step, "parameters", {}) or {}
            step_result = getattr(step, "result", None)

            if action_name == "LIST_DIRECTORY":
                path = params.get("path", "directory")
                if isinstance(step_result, list):
                    count = len(step_result)
                    if count == 0:
                        return (_sanitize_result_text(f"Directory '{path}' is empty (0 items)."), "SUCCESS", True)
                    names = [getattr(item, "name", str(item)) for item in step_result[:5]]
                    items_str = ", ".join(names)
                    more = f" (+{count - 5} more)" if count > 5 else ""
                    return (_sanitize_result_text(f"Found {count} item(s) in '{path}':\n{items_str}{more}"), "SUCCESS", True)

            elif action_name == "FIND_PROCESS":
                proc_name = params.get("name") or params.get("process_name") or ""
                if isinstance(step_result, list):
                    count = len(step_result)
                    if count == 0:
                        msg = f"No processes found matching '{proc_name}'." if proc_name else "No matching processes found."
                        return (_sanitize_result_text(msg), "SUCCESS", True)
                    procs = [f"{getattr(p, 'name', str(p))} (PID {getattr(p, 'pid', '?')})" for p in step_result[:3]]
                    procs_str = ", ".join(procs)
                    more = f" (+{count - 3} more)" if count > 3 else ""
                    return (_sanitize_result_text(f"Found {count} process(es):\n{procs_str}{more}"), "SUCCESS", True)

            elif action_name == "READ_TEXT_FILE":
                path = params.get("path", "file")
                content = getattr(step_result, "content", "") if step_result else ""
                size = getattr(step_result, "size_bytes", len(content)) if step_result else 0
                if content:
                    snippet = content.strip()[:200] + ("..." if len(content.strip()) > 200 else "")
                    return (_sanitize_result_text(f"Read '{path}' ({size} bytes):\n{snippet}"), "SUCCESS", True)
                return (_sanitize_result_text(f"File '{path}' is empty."), "SUCCESS", True)

            elif action_name == "GET_FILE_INFO":
                name = getattr(step_result, "name", params.get("path", "file")) if step_result else params.get("path", "file")
                size = getattr(step_result, "size_bytes", 0) if step_result else 0
                is_dir = getattr(step_result, "is_directory", False) if step_result else False
                type_str = "Directory" if is_dir else "File"
                return (_sanitize_result_text(f"{type_str} '{name}' ({size} bytes)."), "SUCCESS", True)

            elif action_name == "POWERSHELL_COMMAND":
                stdout = getattr(step_result, "stdout", "") if step_result else ""
                if stdout and stdout.strip():
                    snippet = stdout.strip()[:250] + ("..." if len(stdout.strip()) > 250 else "")
                    return (_sanitize_result_text(f"Command output:\n{snippet}"), "SUCCESS", True)
                return (_sanitize_result_text("PowerShell command executed successfully."), "SUCCESS", True)

        # Multi-step or general fallback
        goal = getattr(plan, "goal", "") or getattr(result, "command_text", "Task")
        return (_sanitize_result_text(f"Task completed successfully: {goal}\n({len(steps)} step(s) completed and verified)"), "SUCCESS", True)

    except Exception as exc:
        logger.warning("Error formatting pipeline result: %s", exc)
        fallback_success = bool(getattr(result, "overall_success", False))
        return (
            "Execution completed, but the result could not be displayed.",
            "SUCCESS" if fallback_success else "FAILED",
            fallback_success,
        )


def build_production_router() -> BrainRouter:
    """
    Discover configured provider credentials in environment variables and build a BrainRouter.
    Credentials are never logged, printed, or exposed.
    """
    providers: List[EVBrainProvider] = []

    # 1. Gemini Provider (Primary if GEMINI_API_KEY / GOOGLE_API_KEY is present)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        try:
            providers.append(GeminiProvider(api_key=gemini_key))
            logger.info("Configured GeminiProvider from environment credentials")
        except Exception as exc:
            logger.warning("Failed to initialize GeminiProvider: %s", exc)

    # 2. OpenRouter Provider (Fallback or Primary if OPENROUTER_API_KEY is present)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            providers.append(OpenRouterProvider(api_key=openrouter_key))
            logger.info("Configured OpenRouterProvider from environment credentials")
        except Exception as exc:
            logger.warning("Failed to initialize OpenRouterProvider: %s", exc)

    # 3. Azure OpenAI Provider
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    if azure_key and azure_endpoint:
        try:
            providers.append(AzureOpenAIProvider(api_key=azure_key, endpoint=azure_endpoint))
            logger.info("Configured AzureOpenAIProvider from environment credentials")
        except Exception as exc:
            logger.warning("Failed to initialize AzureOpenAIProvider: %s", exc)

    provider_mgr = EVBrainProviderManager(providers) if providers else None
    return BrainRouter(provider_manager=provider_mgr)


def _parse_args(argv: list) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="gui.app",
        description="E.V. - Enhanced Virtual Intelligence GUI",
    )
    return parser.parse_args(argv)


def main() -> None:
    """Main entry point for the GUI application."""
    args = _parse_args(sys.argv[1:])

    app = QGuiApplication.instance()
    if app is None:
        # Pass only the program name; CLI flags are handled by argparse above.
        app = QGuiApplication(sys.argv[:1])

    # Set Qt Quick Controls style to Basic before loading QML
    QQuickStyle.setStyle('Basic')

    engine = QQmlApplicationEngine()

    # Create event bus
    event_bus = EVEventBus(initial_state=EVState.IDLE)

    # Create bridge and register context property for QML
    bridge = GuiBridge(event_bus)

    # Create experience manager and attach to bridge
    experience_manager = EVExperienceManager(event_bus)
    bridge.set_experience_manager(experience_manager)

    engine.rootContext().setContextProperty("guiBridge", bridge)

    # Discover providers and instantiate production backend orchestrator
    router = build_production_router()

    # Task 013: Optional TTS subsystem — opt-in via EV_TTS_ENABLED=true
    # Default is disabled; E.V. starts normally in text-only mode if TTS is
    # not enabled or if initialization fails for any reason.
    tts_manager = None
    if os.getenv("EV_TTS_ENABLED", "false").strip().lower() == "true":
        try:
            from core.tts import EVTTSManager, WindowsSAPIProvider
            _sapi = WindowsSAPIProvider()
            if _sapi.is_available():
                tts_manager = EVTTSManager(providers=[_sapi], event_bus=event_bus)
                logger.info("TTS subsystem initialized with WindowsSAPIProvider")
            else:
                logger.info("TTS: WindowsSAPIProvider not available; running in text-only mode")
        except Exception as _tts_exc:
            logger.warning(
                "TTS initialization failed; E.V. will run in text-only mode: %s",
                _tts_exc,
            )

    if tts_manager is not None:
        orchestrator = EVOrchestrator(event_bus=event_bus, router=router, tts_manager=tts_manager)
    else:
        orchestrator = EVOrchestrator(event_bus=event_bus, router=router)

    # Task 018-D: Observational subsystems (System Monitor & Proactive Awareness)
    # Zero execution authority: monitoring and awareness are presentation-only.
    system_monitor = EVSystemMonitor(event_bus=event_bus)
    system_monitor.start()

    awareness_engine = EVProactiveAwarenessEngine(
        event_bus=event_bus,
        system_monitor=system_monitor,
        experience_manager=experience_manager,
        tts_manager=tts_manager,
    )
    awareness_engine.start()

    def handle_task_submission(command: str) -> None:
        cleaned = command.strip()
        if not cleaned:
            return
        ctx = ActionPipelineContext(
            pipeline_id=f"gui-{uuid.uuid4().hex[:8]}",
            source="GUI",
            command_text=cleaned,
        )

        def _pipeline_worker() -> None:
            try:
                result = orchestrator.execute_pipeline(cleaned, ctx)
                summary, status, success = _format_pipeline_result(result)
                bridge.notifyTaskResult(summary, status, success)
            except Exception as exc:
                logger.exception("Pipeline execution failed unexpectedly: %s", exc)
                safe_err = f"Execution failed: {type(exc).__name__}"
                bridge.notifyTaskResult(safe_err, "FAILED", False)

        worker = threading.Thread(
            target=_pipeline_worker,
            name=f"EV-GuiPipelineWorker-{ctx.pipeline_id}",
            daemon=True,
        )
        worker.start()

    bridge.taskSubmitted.connect(handle_task_submission)

    def handle_approval_submission(task_id: str, approved: bool) -> None:
        def _resolve_worker() -> None:
            err_msg = "Backend authorization failed or task ID mismatched."
            success = False
            try:
                result = orchestrator.resolve_pipeline_approval(
                    plan_id=task_id, approved=approved
                )
                if result is not None:
                    if approved:
                        success = bool(result.overall_success)
                        if not success:
                            err_msg = result.error or "Pipeline execution or verification failed."
                    else:
                        if result.approved is False and result.plan is not None:
                            success = True
                        else:
                            err_msg = result.error or "Plan ID mismatch or no plan awaiting approval."
            except Exception as exc:
                logger.exception(
                    "Exception during approval resolution for plan %s: %s", task_id, exc
                )
                success = False
                err_msg = str(exc)

            if not success:
                logger.warning(
                    "Approval resolution failed or was rejected by backend for plan %s: %s",
                    task_id,
                    err_msg,
                )
                if hasattr(bridge, "notifyApprovalFailed"):
                    bridge.notifyApprovalFailed(task_id, err_msg)

        worker = threading.Thread(
            target=_resolve_worker,
            name=f"EV-GuiApprovalWorker-{task_id}",
            daemon=True,
        )
        worker.start()

    bridge.approvalSubmitted.connect(handle_approval_submission)

    # Load root QML
    qml_file = Path(__file__).parent / "qml" / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_file)))

    if not engine.rootObjects():
        sys.exit(-1)

    # Windows-only native chrome integration.
    #
    # The QML window remains visually frameless, while Windows receives
    # the native frame capabilities required for Aero Snap and normal
    # desktop window management.
    root_window = engine.rootObjects()[0]
    native_chrome = install_windows_native_chrome(app, root_window)

    # Keep the native event filter alive for the complete application
    # lifetime. QAbstractNativeEventFilter must not be garbage-collected.
    setattr(app, "_ev_windows_native_chrome", native_chrome)

    # Store subsystems on app to prevent premature garbage collection
    setattr(app, "_ev_orchestrator", orchestrator)
    setattr(app, "_ev_experience_manager", experience_manager)
    setattr(app, "_ev_system_monitor", system_monitor)
    setattr(app, "_ev_awareness_engine", awareness_engine)

    def _clean_shutdown() -> None:
        try:
            awareness_engine.stop()
        except Exception as _e:
            logger.debug("Error stopping awareness engine: %s", _e)
        try:
            system_monitor.stop()
        except Exception as _e:
            logger.debug("Error stopping system monitor: %s", _e)
        try:
            bridge.shutdown()
        except Exception as _e:
            logger.debug("Error shutting down bridge: %s", _e)

    app.aboutToQuit.connect(_clean_shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
