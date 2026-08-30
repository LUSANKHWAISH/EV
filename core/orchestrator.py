import threading
from typing import Optional

from core.agent import EVAgent
from core.events import EVEventBus
from core.history import EVTaskHistoryStore
from core.models import AgentTask


class EVOrchestrator:
    """
    Long-lived production execution owner for the E.V. agent.
    Manages the lifecycle of a single agent and executes tasks in the background.
    """
    def __init__(self, event_bus: EVEventBus):
        self.event_bus = event_bus
        self.history_store = EVTaskHistoryStore()
        self.agent = EVAgent(
            history_store=self.history_store,
            event_bus=self.event_bus,
        )

    def execute_task(self, task: AgentTask) -> threading.Thread:
        """
        Submit a task for background execution.
        Returns the daemon thread handle.
        """
        thread = threading.Thread(
            target=self.agent.run,
            args=(task,),
            daemon=True,
            name=f"EVAgentThread-{task.task_id}"
        )
        thread.start()
        return thread
