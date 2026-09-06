# Main GUI entry point for E.V.
# Bootstrap application and load QML root.
import argparse
import logging
import os
from pathlib import Path
import sys
import threading
from typing import List, Optional
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
from gui.bridge import GuiBridge
from gui.windows_chrome import install_windows_native_chrome
from providers.gemini_provider import GeminiProvider
from providers.openai_compatible_provider import (
    AzureOpenAIProvider,
    OpenRouterProvider,
)

logger = logging.getLogger(__name__)


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

    def handle_task_submission(command: str) -> None:
        cleaned = command.strip()
        if not cleaned:
            return
        ctx = ActionPipelineContext(
            pipeline_id=f"gui-{uuid.uuid4().hex[:8]}",
            source="GUI",
            command_text=cleaned,
        )
        worker = threading.Thread(
            target=orchestrator.execute_pipeline,
            args=(cleaned, ctx),
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

    # Store orchestrator and experience manager on app to prevent garbage collection
    setattr(app, "_ev_orchestrator", orchestrator)
    setattr(app, "_ev_experience_manager", experience_manager)

    app.aboutToQuit.connect(bridge.shutdown)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
