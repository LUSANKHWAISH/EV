import os
import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add the EV directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_powershell_successful_execution():
    from tools.powershell import run_powershell
    from core.models import PowerShellResult
    # Mock subprocess.run to return a successful result
    mock_completed = MagicMock()
    mock_completed.stdout = "EV_PS_OK\n"
    mock_completed.stderr = ""
    mock_completed.returncode = 0
    with patch('subprocess.run', return_value=mock_completed) as mock_run:
        result = run_powershell('Write-Output "EV_PS_OK"')
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        # Check that the command was called with the expected arguments
        assert args[0] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", 'Write-Output "EV_PS_OK"']
        assert kwargs['capture_output'] is True
        assert kwargs['text'] is True
        assert 'timeout' in kwargs
    assert isinstance(result, PowerShellResult)
    assert result.executed is True
    assert result.success is True
    assert result.timed_out is False
    assert result.exit_code == 0
    assert "EV_PS_OK" in result.stdout
    assert result.stderr == ""
    # Check that timestamps are set and duration is non-negative
    assert result.started_at is not None
    assert result.finished_at is not None
    assert result.duration_seconds >= 0

def test_powershell_non_zero_exit():
    from tools.powershell import run_powershell
    # Mock subprocess.run to return a non-zero exit code
    mock_completed = MagicMock()
    mock_completed.stdout = ""
    mock_completed.stderr = ""
    mock_completed.returncode = 7
    with patch('subprocess.run', return_value=mock_completed):
        result = run_powershell('exit 7')
    assert result.executed is True
    assert result.success is False
    assert result.exit_code == 7
    assert result.timed_out is False
    # stdout and stderr may be empty

def test_powershell_error_stderr_capture():
    from tools.powershell import run_powershell
    # Mock subprocess.run to return zero exit code but with stderr output
    mock_completed = MagicMock()
    mock_completed.stdout = ""
    mock_completed.stderr = "test error\n"
    mock_completed.returncode = 0
    with patch('subprocess.run', return_value=mock_completed):
        result = run_powershell('Write-Error "test error"; exit 0')
    assert result.executed is True
    assert result.success is True  # because exit code is 0
    assert result.exit_code == 0
    assert "test error" in result.stderr

def test_powershell_timeout():
    from tools.powershell import run_powershell
    # Mock subprocess.run to raise TimeoutExpired
    from subprocess import TimeoutExpired
    with patch('subprocess.run', side_effect=TimeoutExpired(cmd="powershell.exe", timeout=1, output="", stderr="")):
        result = run_powershell('Start-Sleep -Seconds 2', timeout=1)
    assert result.executed is True
    assert result.success is False
    assert result.timed_out is True
    # We don't have stdout/stderr because the process was killed, but we can check that they are empty strings.
    assert result.stdout == ""
    assert result.stderr == ""
    # Check that duration is around 1 second (maybe a little more or less)
    # Note: the mocked TimeoutExpired doesn't actually take time, so duration will be very small.
    # We'll just check that the result is structured correctly.
    assert result.duration_seconds >= 0

def test_powershell_default_timeout():
    from tools.powershell import run_powershell
    from config.settings import settings
    # We'll test that when timeout is not provided, it uses the setting.
    # We'll mock subprocess.run and check that the timeout argument passed is the setting.
    mock_completed = MagicMock()
    mock_completed.stdout = "default timeout test\n"
    mock_completed.stderr = ""
    mock_completed.returncode = 0
    with patch('subprocess.run', return_value=mock_completed) as mock_run:
        result = run_powershell('Write-Output "default timeout test"')
        args, kwargs = mock_run.call_args
        assert kwargs['timeout'] == settings.EV_MAX_COMMAND_TIMEOUT
    assert result.executed is True
    assert result.success is True

def test_powershell_dry_run():
    from tools.powershell import run_powershell
    from config.settings import settings
    # We need to temporarily set EV_DRY_RUN to True for this test.
    original_dry_run = settings.EV_DRY_RUN
    try:
        settings.EV_DRY_RUN = True
        result = run_powershell('Write-Output "should not execute"')
        # In dry run, executed should be False
        assert result.executed is False
        assert result.success is False
        assert result.timed_out is False
        # The command string should be preserved
        assert result.command == 'Write-Output "should not execute"'
    finally:
        # Restore the original setting
        settings.EV_DRY_RUN = original_dry_run

def test_powershell_structured_result_model():
    from tools.powershell import run_powershell
    from core.models import PowerShellResult
    mock_completed = MagicMock()
    mock_completed.stdout = "model test\n"
    mock_completed.stderr = ""
    mock_completed.returncode = 0
    with patch('subprocess.run', return_value=mock_completed):
        result = run_powershell('Write-Output "model test"')
    assert isinstance(result, PowerShellResult)
    # Check that all required fields are present and of correct type
    assert isinstance(result.command, str)
    assert isinstance(result.stdout, str)
    assert isinstance(result.stderr, str)
    assert isinstance(result.exit_code, int)
    assert isinstance(result.success, bool)
    assert isinstance(result.executed, bool)
    assert isinstance(result.timed_out, bool)
    assert result.started_at is not None
    assert result.finished_at is not None
    assert isinstance(result.duration_seconds, float)
    # Check that duration is non-negative
    assert result.duration_seconds >= 0
    # Check that finished_at is after started_at (or equal if very fast)
    assert result.finished_at >= result.started_at

if __name__ == "__main__":
    # Simple test runner
    import traceback
    tests = [
        test_powershell_successful_execution,
        test_powershell_non_zero_exit,
        test_powershell_error_stderr_capture,
        test_powershell_timeout,
        test_powershell_default_timeout,
        test_powershell_dry_run,
        test_powershell_structured_result_model,
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
