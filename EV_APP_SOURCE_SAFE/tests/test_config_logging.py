import os
import sys
import tempfile
import logging
from pathlib import Path

# Ensure the EV directory is in the path so we can import config and core
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_default_configuration():
    from config.settings import Settings
    # Unset environment variables to test defaults
    for var in ["EV_LOG_LEVEL", "EV_DRY_RUN", "EV_MAX_COMMAND_TIMEOUT"]:
        os.environ.pop(var, None)
    # Reload the module to get fresh Settings instance? Since Settings is instantiated at import,
    # we need to create a new instance. We'll test by creating a new Settings class instance.
    # But the singleton settings is already created at import time with whatever env was present.
    # To avoid side effects, we'll test by creating a new Settings instance directly.
    # However, the Settings class reads from environment at instantiation.
    # So we can test by temporarily clearing env and creating a new instance.
    # We'll do that in each test.
    pass  # We'll implement in each test.

def test_settings_defaults():
    from config.settings import Settings
    # Clear relevant env vars
    for var in ["EV_LOG_LEVEL", "EV_DRY_RUN", "EV_MAX_COMMAND_TIMEOUT"]:
        os.environ.pop(var, None)
    settings = Settings()  # new instance
    assert settings.EV_LOG_LEVEL == "INFO"
    assert settings.EV_DRY_RUN is False
    assert settings.EV_MAX_COMMAND_TIMEOUT == 120

def test_settings_env_override():
    from config.settings import Settings
    os.environ["EV_LOG_LEVEL"] = "DEBUG"
    os.environ["EV_DRY_RUN"] = "true"
    os.environ["EV_MAX_COMMAND_TIMEOUT"] = "30"
    try:
        settings = Settings()
        assert settings.EV_LOG_LEVEL == "DEBUG"
        assert settings.EV_DRY_RUN is True
        assert settings.EV_MAX_COMMAND_TIMEOUT == 30
    finally:
        for var in ["EV_LOG_LEVEL", "EV_DRY_RUN", "EV_MAX_COMMAND_TIMEOUT"]:
            os.environ.pop(var, None)

def test_settings_boolean_parsing():
    from config.settings import Settings
    for true_val in ["true", "True", "1", "yes", "on"]:
        os.environ["EV_DRY_RUN"] = true_val
        try:
            settings = Settings()
            assert settings.EV_DRY_RUN is True, f"Failed for {true_val}"
        finally:
            os.environ.pop("EV_DRY_RUN", None)
    for false_val in ["false", "False", "0", "no", "off", ""]:
        os.environ["EV_DRY_RUN"] = false_val
        try:
            settings = Settings()
            assert settings.EV_DRY_RUN is False, f"Failed for {false_val}"
        finally:
            os.environ.pop("EV_DRY_RUN", None)

def test_settings_timeout_validation():
    from config.settings import Settings
    # Valid positive
    os.environ["EV_MAX_COMMAND_TIMEOUT"] = "5"
    try:
        settings = Settings()
        assert settings.EV_MAX_COMMAND_TIMEOUT == 5
    finally:
        os.environ.pop("EV_MAX_COMMAND_TIMEOUT", None)
    # Reject zero
    os.environ["EV_MAX_COMMAND_TIMEOUT"] = "0"
    try:
        try:
            Settings()
            assert False, "Expected validation error for zero timeout"
        except Exception as e:
            # Should be a validation error
            assert "EV_MAX_COMMAND_TIMEOUT must be a positive integer" in str(e)
    finally:
        os.environ.pop("EV_MAX_COMMAND_TIMEOUT", None)
    # Reject negative
    os.environ["EV_MAX_COMMAND_TIMEOUT"] = "-1"
    try:
        try:
            Settings()
            assert False, "Expected validation error for negative timeout"
        except Exception as e:
            assert "EV_MAX_COMMAND_TIMEOUT must be a positive integer" in str(e)
    finally:
        os.environ.pop("EV_MAX_COMMAND_TIMEOUT", None)

def test_logging_initialization():
    from core.logging_config import setup_logging
    logger = setup_logging("test_logger")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_logger"
    # Check that it has at least a console and file handler
    assert len(logger.handlers) >= 2
    # Check that the level is set from settings (default INFO)
    from config.settings import settings
    expected_level = getattr(logging, settings.EV_LOG_LEVEL.upper())
    assert logger.level == expected_level

def test_logging_writes_message():
    from core.logging_config import setup_logging
    import io
    import logging
    logger = setup_logging("test_logger2")
    # Capture log output by adding a stream handler temporarily? Instead we can check the log file.
    # We'll use a temporary log file for isolation.
    # But we can also rely on the logger's file handler writing to the actual logs directory.
    # Since we are in a test environment, we can check the file.
    # We'll log a message and then read the log file.
    test_msg = "TEST LOG MESSAGE"
    logger.info(test_msg)
    # Force flush
    for handler in logger.handlers:
        handler.flush()
    # Locate the log file
    log_file = Path(__file__).parent.parent / "logs" / "ev.log"
    assert log_file.exists()
    # Read the file and check that our message appears
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert test_msg in content

def test_logging_no_duplicate_handlers():
    from core.logging_config import setup_logging
    logger1 = setup_logging("test_logger3")
    initial_handlers = len(logger1.handlers)
    logger2 = setup_logging("test_logger3")  # same name
    # Should be the same logger instance (since getLogger returns same)
    assert logger1 is logger2
    # Handlers count should not have increased
    assert len(logger2.handlers) == initial_handlers

if __name__ == "__main__":
    # Simple test runner
    import traceback
    tests = [
        test_settings_defaults,
        test_settings_env_override,
        test_settings_boolean_parsing,
        test_settings_timeout_validation,
        test_logging_initialization,
        test_logging_writes_message,
        test_logging_no_duplicate_handlers,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"PASS: {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL: {test.__name__}")
            traceback.print_exc()
    print(f"\nTotal: {passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
