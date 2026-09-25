"""Unit tests for GuiBridge Task Result Contract (Task 018-C.7)."""

import sys
import threading
import time

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QSignalSpy

from core.events import EVEventBus
from core.models import EVState
from gui.bridge import GuiBridge


@pytest.fixture(scope="module")
def app():
    """Ensure a QGuiApplication exists for Qt event processing."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    return instance


@pytest.fixture
def bridge(app):
    """Create a GuiBridge instance with clean lifecycle."""
    bus = EVEventBus(initial_state=EVState.IDLE)
    b = GuiBridge(bus)
    yield b
    b.shutdown()


def test_initial_result_state(bridge):
    """1. Verify initial default state of result properties."""
    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "IDLE"
    assert bridge.taskResultSuccess is False
    assert bridge.taskResultAvailable is False


def test_submit_task_clears_previous_result_and_sets_running(bridge):
    """2. Verify submitTask() clears any previous result and sets status to RUNNING."""
    # Seed previous completed state
    bridge.notifyTaskResult("Previous execution output", "SUCCESS", True)
    QCoreApplication.processEvents()
    assert bridge.taskResult == "Previous execution output"
    assert bridge.taskResultStatus == "SUCCESS"
    assert bridge.taskResultAvailable is True

    spy = QSignalSpy(bridge.taskResultChanged)
    assert spy.isValid()

    # Submit new task
    bridge.submitTask("find process ev")
    QCoreApplication.processEvents()

    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "RUNNING"
    assert bridge.taskResultSuccess is False
    assert bridge.taskResultAvailable is False
    assert spy.count() >= 1


def test_notify_task_result_success(bridge):
    """3. Verify notifyTaskResult propagates SUCCESS correctly."""
    spy = QSignalSpy(bridge.taskResultChanged)
    assert spy.isValid()

    bridge.notifyTaskResult("Found 3 processes.", status="SUCCESS", success=True)
    QCoreApplication.processEvents()

    assert bridge.taskResult == "Found 3 processes."
    assert bridge.taskResultStatus == "SUCCESS"
    assert bridge.taskResultSuccess is True
    assert bridge.taskResultAvailable is True
    assert spy.count() == 1


def test_notify_task_result_failed(bridge):
    """4. Verify notifyTaskResult propagates FAILED correctly."""
    spy = QSignalSpy(bridge.taskResultChanged)
    assert spy.isValid()

    bridge.notifyTaskResult("Task failed: Directory not found", status="FAILED", success=False)
    QCoreApplication.processEvents()

    assert bridge.taskResult == "Task failed: Directory not found"
    assert bridge.taskResultStatus == "FAILED"
    assert bridge.taskResultSuccess is False
    assert bridge.taskResultAvailable is True
    assert spy.count() == 1


def test_notify_task_result_cancelled(bridge):
    """5. Verify notifyTaskResult propagates CANCELLED correctly."""
    spy = QSignalSpy(bridge.taskResultChanged)
    assert spy.isValid()

    bridge.notifyTaskResult("Task was cancelled by user.", status="CANCELLED", success=False)
    QCoreApplication.processEvents()

    assert bridge.taskResult == "Task was cancelled by user."
    assert bridge.taskResultStatus == "CANCELLED"
    assert bridge.taskResultSuccess is False
    assert bridge.taskResultAvailable is True
    assert spy.count() == 1


def test_clear_task_result_restores_defaults(bridge):
    """6. Verify clearTaskResult() restores all defaults."""
    bridge.notifyTaskResult("Some output", status="SUCCESS", success=True)
    QCoreApplication.processEvents()
    assert bridge.taskResultAvailable is True

    spy = QSignalSpy(bridge.taskResultChanged)
    bridge.clearTaskResult()
    QCoreApplication.processEvents()

    assert bridge.taskResult == ""
    assert bridge.taskResultStatus == "IDLE"
    assert bridge.taskResultSuccess is False
    assert bridge.taskResultAvailable is False
    assert spy.count() == 1


def test_cross_thread_queued_handoff(bridge):
    """7. Verify worker thread can safely invoke notifyTaskResult via queued connection."""
    spy = QSignalSpy(bridge.taskResultChanged)

    def _worker():
        time.sleep(0.02)
        bridge.notifyTaskResult("Worker result output", status="SUCCESS", success=True)

    thread = threading.Thread(target=_worker, name="TestWorkerThread")
    thread.start()
    thread.join(timeout=2.0)

    # Process events in main Qt thread
    QCoreApplication.processEvents()

    assert bridge.taskResult == "Worker result output"
    assert bridge.taskResultStatus == "SUCCESS"
    assert bridge.taskResultSuccess is True
    assert bridge.taskResultAvailable is True
    assert spy.count() == 1
