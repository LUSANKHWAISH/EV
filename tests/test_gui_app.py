# Regression tests for the GUI launcher (gui/app.py) production wiring.
import argparse
import os
import sys
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

from core.events import EVEventBus
from core.models import EVState
from core.orchestrator import EVOrchestrator
from gui.app import _format_pipeline_result, _parse_args, build_production_router, main
from gui.bridge import GuiBridge

# --- Argument parsing ------------------------------------------------------

def test_parse_args_returns_namespace():
    """Verify the CLI parser works and handles basic arguments."""
    args = _parse_args([])
    assert isinstance(args, argparse.Namespace)

def test_parse_args_accepts_help():
    """Verify --help is handled by argparse."""
    with pytest.raises(SystemExit):
        _parse_args(["--help"])

# --- Production Architecture Wiring ----------------------------------------

@pytest.fixture
def mock_gui_env():
    """Mock out the blocking Qt/GUI components for testing main()."""
    with patch("gui.app.QGuiApplication") as mock_app, \
         patch("gui.app.QQmlApplicationEngine") as mock_engine, \
         patch("gui.app.install_windows_native_chrome"), \
         patch("sys.exit") as mock_exit, \
         patch("sys.argv", ["gui.app"]):

        # Make app.exec() return 0 instead of blocking
        mock_app_instance = MagicMock()
        mock_app_instance.exec.return_value = 0
        mock_app.instance.return_value = mock_app_instance
        mock_app.return_value = mock_app_instance

        # Make engine.rootObjects() return a dummy window
        mock_engine_instance = MagicMock()
        mock_engine_instance.rootObjects.return_value = [MagicMock()]
        mock_engine.return_value = mock_engine_instance

        yield mock_app_instance, mock_engine_instance, mock_exit

def test_build_production_router_with_no_env():
    """Verify router builds with provider_manager=None when no API keys are present."""
    with patch.dict(os.environ, {}, clear=True):
        router = build_production_router()
        assert router.provider_manager is None

def test_build_production_router_with_gemini_env():
    """Verify router builds with GeminiProvider when GEMINI_API_KEY is present."""
    from core.brain_provider import EVBrainProvider
    with patch.dict(os.environ, {"GEMINI_API_KEY": "fake-key-test"}, clear=True):
        with patch("gui.app.GeminiProvider") as mock_gemini:
            mock_provider = MagicMock(spec=EVBrainProvider)
            mock_gemini.return_value = mock_provider
            router = build_production_router()
            assert router.provider_manager is not None
            assert len(router.provider_manager.providers) == 1
            mock_gemini.assert_called_once_with(api_key="fake-key-test")


def test_build_production_router_with_openrouter_env():
    """Verify router builds with OpenRouterProvider when OPENROUTER_API_KEY is present."""
    from core.brain_provider import EVBrainProvider
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-openrouter-key"}, clear=True):
        with patch("gui.app.OpenRouterProvider") as mock_openrouter:
            mock_provider = MagicMock(spec=EVBrainProvider)
            mock_openrouter.return_value = mock_provider
            router = build_production_router()
            assert router.provider_manager is not None
            assert len(router.provider_manager.providers) == 1
            mock_openrouter.assert_called_once_with(api_key="fake-openrouter-key")


def test_build_production_router_with_azure_env():
    """Verify router builds with AzureOpenAIProvider and passes endpoint= correctly."""
    from core.brain_provider import EVBrainProvider
    with patch.dict(
        os.environ,
        {
            "AZURE_OPENAI_API_KEY": "fake-azure-key",
            "AZURE_OPENAI_ENDPOINT": "https://my-instance.openai.azure.com",
        },
        clear=True,
    ):
        with patch("gui.app.AzureOpenAIProvider") as mock_azure:
            mock_provider = MagicMock(spec=EVBrainProvider)
            mock_azure.return_value = mock_provider
            router = build_production_router()
            assert router.provider_manager is not None
            assert len(router.provider_manager.providers) == 1
            mock_azure.assert_called_once_with(
                api_key="fake-azure-key",
                endpoint="https://my-instance.openai.azure.com",
            )


def test_build_production_router_with_azure_missing_endpoint():
    """Verify AzureOpenAIProvider is not registered if endpoint is missing."""
    with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "fake-azure-key"}, clear=True):
        router = build_production_router()
        assert router.provider_manager is None


def test_build_production_router_with_azure_missing_key():
    """Verify AzureOpenAIProvider is not registered if API key is missing."""
    with patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://my-instance.openai.azure.com"}, clear=True):
        router = build_production_router()
        assert router.provider_manager is None


def test_build_production_router_multi_provider_order():
    """Verify deterministic provider ordering: Gemini (1) -> OpenRouter (2) -> Azure (3)."""
    from core.brain_provider import EVBrainProvider
    env_vars = {
        "GEMINI_API_KEY": "fake-gemini-key",
        "OPENROUTER_API_KEY": "fake-openrouter-key",
        "AZURE_OPENAI_API_KEY": "fake-azure-key",
        "AZURE_OPENAI_ENDPOINT": "https://my-instance.openai.azure.com",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        with patch("gui.app.GeminiProvider") as mock_gemini, \
             patch("gui.app.OpenRouterProvider") as mock_openrouter, \
             patch("gui.app.AzureOpenAIProvider") as mock_azure:

            p_gemini = MagicMock(spec=EVBrainProvider, provider_name="gemini")
            p_openrouter = MagicMock(spec=EVBrainProvider, provider_name="openrouter")
            p_azure = MagicMock(spec=EVBrainProvider, provider_name="azure_openai")

            mock_gemini.return_value = p_gemini
            mock_openrouter.return_value = p_openrouter
            mock_azure.return_value = p_azure

            router = build_production_router()
            assert router.provider_manager is not None
            providers = router.provider_manager.providers
            assert len(providers) == 3
            assert providers[0] is p_gemini
            assert providers[1] is p_openrouter
            assert providers[2] is p_azure


def test_build_production_router_exception_containment():
    """Verify initialization errors in one provider do not block other providers."""
    from core.brain_provider import EVBrainProvider
    env_vars = {
        "GEMINI_API_KEY": "fake-gemini-key",
        "OPENROUTER_API_KEY": "fake-openrouter-key",
    }
    with patch.dict(os.environ, env_vars, clear=True):
        with patch("gui.app.GeminiProvider", side_effect=RuntimeError("Gemini SDK error")), \
             patch("gui.app.OpenRouterProvider") as mock_openrouter:

            p_openrouter = MagicMock(spec=EVBrainProvider, provider_name="openrouter")
            mock_openrouter.return_value = p_openrouter

            router = build_production_router()
            assert router.provider_manager is not None
            providers = router.provider_manager.providers
            assert len(providers) == 1
            assert providers[0] is p_openrouter


def test_main_creates_shared_event_bus(mock_gui_env):
    """Verify main() creates exactly one EVEventBus and passes it to components."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.EVEventBus") as mock_bus_cls, \
         patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls, \
         patch("gui.app.build_production_router") as mock_router_builder:

        mock_bus_instance = MagicMock()
        mock_bus_cls.return_value = mock_bus_instance
        mock_router_instance = MagicMock()
        mock_router_builder.return_value = mock_router_instance

        main()

        # Bus should be created once
        mock_bus_cls.assert_called_once_with(initial_state=EVState.IDLE)

        # Bridge should receive the exact same bus
        mock_bridge_cls.assert_called_once_with(mock_bus_instance)

        # Orchestrator should receive the bus and router
        mock_orch_cls.assert_called_once_with(event_bus=mock_bus_instance, router=mock_router_instance)

def test_main_registers_bridge_with_qml(mock_gui_env):
    """Verify the GuiBridge is exposed to QML."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls:
        mock_bridge_instance = MagicMock()
        mock_bridge_cls.return_value = mock_bridge_instance

        main()

        root_context = mock_engine.rootContext.return_value
        root_context.setContextProperty.assert_called_once_with("guiBridge", mock_bridge_instance)

def test_main_retains_orchestrator(mock_gui_env):
    """Verify the EVOrchestrator is kept alive by attaching it to the app."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.EVOrchestrator") as mock_orch_cls:
        mock_orch_instance = MagicMock()
        mock_orch_cls.return_value = mock_orch_instance

        main()

        # The app instance must retain the orchestrator to prevent garbage collection
        assert getattr(mock_app, "_ev_orchestrator") is mock_orch_instance

def test_main_executes_and_exits(mock_gui_env):
    """Verify main() calls app.exec() and exits with its return code."""
    mock_app, mock_engine, mock_exit = mock_gui_env
    mock_app.exec.return_value = 42

    main()

    mock_app.exec.assert_called_once()
    mock_exit.assert_called_once_with(42)


def test_main_connects_approval_submission(mock_gui_env):
    """Verify main() connects bridge.approvalSubmitted to orchestrator.resolve_pipeline_approval."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bridge = MagicMock()
        mock_bridge_cls.return_value = mock_bridge
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        main()

        mock_bridge.approvalSubmitted.connect.assert_called_once()


def test_approval_submission_executes_canonical_pipeline_approval(mock_gui_env):
    """Verify handle_approval_submission invokes orchestrator.resolve_pipeline_approval in worker thread."""
    import time
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bridge = MagicMock()
        mock_bridge_cls.return_value = mock_bridge
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        main()

        connect_call = mock_bridge.approvalSubmitted.connect.call_args
        assert connect_call is not None
        callback = connect_call[0][0]

        callback("plan-test-123", True)
        time.sleep(0.1)

        mock_orch.resolve_pipeline_approval.assert_called_once_with(
            plan_id="plan-test-123", approved=True
        )


def test_main_connects_task_submission(mock_gui_env):
    """Verify main() connects bridge.taskSubmitted to handle_task_submission."""
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bridge = MagicMock()
        mock_bridge_cls.return_value = mock_bridge
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        main()

        mock_bridge.taskSubmitted.connect.assert_called_once()


def test_task_submission_executes_canonical_pipeline(mock_gui_env):
    """Verify handle_task_submission invokes orchestrator.execute_pipeline in worker thread."""
    import time
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bridge = MagicMock()
        mock_bridge_cls.return_value = mock_bridge
        mock_orch = MagicMock()
        mock_orch_cls.return_value = mock_orch

        main()

        # Extract the connected callback from taskSubmitted.connect
        connect_call = mock_bridge.taskSubmitted.connect.call_args
        assert connect_call is not None
        callback = connect_call[0][0]

        # Call with command
        callback("find process python")
        # Allow daemon worker thread to execute
        time.sleep(0.1)

        mock_orch.execute_pipeline.assert_called_once()
        call_args = mock_orch.execute_pipeline.call_args
        assert call_args[0][0] == "find process python"
        ctx = call_args[0][1]
        assert ctx.source == "GUI"
        assert ctx.command_text == "find process python"

        # Worker must have notified bridge
        mock_bridge.notifyTaskResult.assert_called_once()


def test_task_submission_worker_handles_unexpected_exception(mock_gui_env):
    """Verify worker catches unhandled exceptions and notifies bridge with safe FAILED status."""
    import time
    mock_app, mock_engine, mock_exit = mock_gui_env

    with patch("gui.app.GuiBridge") as mock_bridge_cls, \
         patch("gui.app.EVOrchestrator") as mock_orch_cls:

        mock_bridge = MagicMock()
        mock_bridge_cls.return_value = mock_bridge
        mock_orch = MagicMock()
        mock_orch.execute_pipeline.side_effect = RuntimeError("Fatal hardware failure")
        mock_orch_cls.return_value = mock_orch

        main()

        connect_call = mock_bridge.taskSubmitted.connect.call_args
        callback = connect_call[0][0]
        callback("check status")
        time.sleep(0.1)

        mock_bridge.notifyTaskResult.assert_called_once()
        args = mock_bridge.notifyTaskResult.call_args[0]
        assert "Execution failed: RuntimeError" in args[0]
        assert args[1] == "FAILED"
        assert args[2] is False


def test_format_pipeline_result_none():
    """Verify None input produces safe FAILED result."""
    summary, status, success = _format_pipeline_result(None)
    assert "Execution completed" in summary
    assert status == "FAILED"
    assert success is False


def test_format_pipeline_result_cancellation():
    """Verify cancelled result produces CANCELLED status."""
    mock_res = MagicMock()
    mock_res.status.value = "CANCELLED"
    mock_res.error = "Cancelled by user"
    mock_res.approved = None
    summary, status, success = _format_pipeline_result(mock_res)
    assert summary == "Cancelled by user"
    assert status == "CANCELLED"
    assert success is False


def test_format_pipeline_result_failure():
    """Verify failed result produces FAILED status with error message."""
    mock_res = MagicMock()
    mock_res.status.value = "FAILED"
    mock_res.overall_success = False
    mock_res.error = "Path does not exist"
    mock_res.approved = True
    summary, status, success = _format_pipeline_result(mock_res)
    assert "Task failed: Path does not exist" in summary
    assert status == "FAILED"
    assert success is False


def test_format_pipeline_result_success_list_directory():
    """Verify list_directory result is summarized cleanly."""
    mock_item1 = MagicMock()
    mock_item1.name = "doc.txt"
    mock_item2 = MagicMock()
    mock_item2.name = "image.png"

    mock_step = MagicMock()
    mock_step.action.value = "list_directory"
    mock_step.parameters = {"path": "C:\\test"}
    mock_step.result = [mock_item1, mock_item2]

    mock_res = MagicMock()
    mock_res.status.value = "COMPLETED"
    mock_res.overall_success = True
    mock_res.error = None
    mock_res.approved = True
    mock_res.plan.steps = [mock_step]
    mock_res.plan.goal = "list C:\\test"

    summary, status, success = _format_pipeline_result(mock_res)
    assert "Found 2 item(s) in 'C:\\test':" in summary
    assert "doc.txt, image.png" in summary
    assert status == "SUCCESS"
    assert success is True


def test_format_pipeline_result_sanitizes_credentials():
    """Verify API keys and sensitive tokens are redacted in result text."""
    mock_res = MagicMock()
    mock_res.status.value = "FAILED"
    mock_res.overall_success = False
    mock_res.error = "Authentication failed for sk-1234567890123456789012345678"
    summary, status, success = _format_pipeline_result(mock_res)
    assert "[REDACTED]" in summary
    assert "sk-1234567890123456789012345678" not in summary
