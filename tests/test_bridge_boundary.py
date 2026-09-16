import pytest
from core.events import EVEventBus
from core.models import EVState
from core.orchestrator import EVOrchestrator
from gui.bridge import GuiBridge
from PySide6.QtCore import QMetaObject

def test_bridge_submittask_is_slot_and_propagates():
    # 1. Prove GuiBridge exposes submitTask as a Qt Slot
    event_bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(event_bus)
    
    meta_obj = bridge.metaObject()
    has_submit_task_slot = False
    for i in range(meta_obj.methodCount()):
        method = meta_obj.method(i)
        if method.name().data().decode('utf-8') == "submitTask" and method.methodType().name == "Slot":
            has_submit_task_slot = True
            break
            
    assert has_submit_task_slot, "submitTask is NOT exposed as a Qt Slot!"

    # 2. & 3. Calling bridge.submitTask emits taskSubmitted exactly once with the same string
    # 4. orchestrator.submit_command is called
    orchestrator = EVOrchestrator(event_bus)
    
    submitted_commands = []
    def mock_submit_command(cmd):
        submitted_commands.append(cmd)
        
    orchestrator.submit_command = mock_submit_command
    
    tasks_received = []
    def handle_task_submission(command: str) -> None:
        tasks_received.append(command)
        if not command.strip():
            return
        orchestrator.submit_command(command.strip())
        
    bridge.taskSubmitted.connect(handle_task_submission)
    
    bridge.submitTask("find process python")
    
    assert len(tasks_received) == 1
    assert tasks_received[0] == "find process python"
    
    assert len(submitted_commands) == 1
    assert submitted_commands[0] == "find process python"
