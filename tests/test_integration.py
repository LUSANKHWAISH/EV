import pytest
import threading
import time
from core.models import EVState, AgentAction, EVEventType
from core.events import EVEventBus
from core.orchestrator import EVOrchestrator
from core.resolver import CommandResolver
from gui.bridge import GuiBridge

def test_resolver_success():
    # 1. resolver success
    resolver = CommandResolver()
    task = resolver.resolve("find process explorer.exe")
    assert task.action == AgentAction.FIND_PROCESS
    assert task.parameters["name"] == "explorer.exe"

def test_resolver_unknown_command():
    # 2. resolver unknown command
    resolver = CommandResolver()
    with pytest.raises(ValueError):
        resolver.resolve("open Chrome")

def test_empty_command():
    # 3. empty command
    resolver = CommandResolver()
    with pytest.raises(ValueError):
        resolver.resolve("   ")

def test_gui_bridge_to_orchestrator_submission():
    # 4. GUI bridge -> orchestrator submission
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    bridge = GuiBridge(event_bus)
    
    # We will track if execute_task gets called by intercepting it
    tasks_received = []
    original_execute = orchestrator.execute_task
    def mock_execute(task):
        tasks_received.append(task)
        return None
    orchestrator.execute_task = mock_execute
    
    def on_task_submitted(cmd):
        orchestrator.submit_command(cmd)
        
    bridge.taskSubmitted.connect(on_task_submitted)
    bridge.submitTask("find process system")
    
    assert len(tasks_received) == 1
    assert tasks_received[0].action == AgentAction.FIND_PROCESS
    assert tasks_received[0].parameters["name"] == "system"

def test_orchestrator_to_agent_task():
    # 5. orchestrator -> AgentTask
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    tasks_received = []
    original_execute = orchestrator.execute_task
    def mock_execute(task):
        tasks_received.append(task)
        return None
    orchestrator.execute_task = mock_execute
    
    orchestrator.submit_command("list dir C:\\")
    assert len(tasks_received) == 1
    assert tasks_received[0].action == AgentAction.LIST_DIRECTORY

def test_real_agent_task_execution_and_lifecycle():
    # 6. real AgentTask execution
    # 7. EXECUTING -> SUCCESS -> IDLE
    # 11. shared EventBus identity remains intact
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    states_observed = []
    def on_state(state_str):
        states_observed.append(state_str)
    
    event_bus.subscribe(
        lambda e: on_state(e.state.name if e.state else ""), 
        [EVEventType.STATE_CHANGED]
    )
    
    # Use list dir which is fast and reliable
    thread = orchestrator.submit_command("list dir C:\\")
    assert thread is not None
    thread.join(timeout=10.0)
    
    assert "EXECUTING" in states_observed
    assert "SUCCESS" in states_observed
    assert states_observed[-1] == "IDLE"

def test_executing_failed_idle_lifecycle():
    # 8. EXECUTING -> FAILED -> IDLE
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    states_observed = []
    def on_state(state_str):
        states_observed.append(state_str)
        
    event_bus.subscribe(
        lambda e: on_state(e.state.name if e.state else ""), 
        [EVEventType.STATE_CHANGED]
    )
    
    # Mock agent.run to raise an exception, testing the error handling path
    def mock_run(*args, **kwargs):
        raise RuntimeError("Simulated agent crash")
    orchestrator.agent.run = mock_run
    
    thread = orchestrator.submit_command("list dir C:\\")
    assert thread is not None
    thread.join(timeout=10.0)
    
    assert "EXECUTING" in states_observed
    assert "FAILED" in states_observed
    assert states_observed[-1] == "IDLE"

def test_rejected_concurrent_task():
    # 9. rejected concurrent task
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    # We lock the orchestrator manually to simulate a running task
    acquired = orchestrator._execution_lock.acquire(blocking=False)
    assert acquired is True
    
    try:
        thread = orchestrator.submit_command("list dir C:\\")
        assert thread is None # Should return None on rejection
    finally:
        orchestrator._execution_lock.release()

def test_lock_released_after_task():
    # Verify: Task A running -> Task B rejected -> Task A completes -> Task C successfully executes
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    # Task B (submitted while A is running or just finished)
    # To reliably make B reject, we acquire the lock manually or inject a delay in A.
    # Since A is "list dir", it might finish extremely fast. We can mock it to block.
    
    lock_held_during_a = threading.Event()
    
    original_run = orchestrator.agent.run
    def blocking_run(*args, **kwargs):
        # We are inside Task A now. 
        # Inform the main thread that we are holding the lock.
        lock_held_during_a.set()
        # Block for a moment to ensure Task B is rejected
        time.sleep(0.1)
        return original_run(*args, **kwargs)
        
    orchestrator.agent.run = blocking_run
    
    thread_a = orchestrator.submit_command("list dir C:\\")
    assert thread_a is not None
    
    # Wait until Task A is definitely inside its execution
    lock_held_during_a.wait(timeout=5.0)
    
    # Submit Task B - should be rejected because Task A holds the lock
    thread_b = orchestrator.submit_command("list dir C:\\")
    assert thread_b is None
    
    # Wait for Task A to finish
    thread_a.join(timeout=10.0)
    
    # Unmock agent.run
    orchestrator.agent.run = original_run
    
    # Task C - should succeed because Task A finished and released the lock
    thread_c = orchestrator.submit_command("list dir C:\\")
    assert thread_c is not None
    thread_c.join(timeout=10.0)
    
    # Verify state is IDLE
    assert event_bus.current_state == EVState.IDLE

def test_rejected_command_does_not_execute_agent():
    # 10. rejected command does not execute an agent
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    orchestrator = EVOrchestrator(event_bus)
    
    tasks_received = []
    original_execute = orchestrator.execute_task
    def mock_execute(task):
        tasks_received.append(task)
        return None
    orchestrator.execute_task = mock_execute
    
    thread = orchestrator.submit_command("unknown command")
    assert thread is None
    assert len(tasks_received) == 0 # Agent was never invoked
    assert event_bus.current_state == EVState.IDLE
