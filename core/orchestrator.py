import logging
import threading
from typing import Optional

from core.agent import EVAgent
from core.events import EVEventBus
from core.history import EVTaskHistoryStore
from core.models import AgentStatus, AgentTask, EVState
from core.resolver import CommandResolver

logger = logging.getLogger(__name__)


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
        self._execution_lock = threading.Lock()

    def submit_command(self, raw_text: str) -> Optional[threading.Thread]:
        """
        Parses a raw text string into a task and submits it for execution.
        """
        resolver = CommandResolver()
        try:
            task = resolver.resolve(raw_text)
        except ValueError as e:
            logger.warning(f"Command resolution failed: {e}")
            return None
            
        try:
            return self.execute_task(task)
        except RuntimeError as e:
            logger.warning(f"Task submission rejected: {e}")
            return None

    def execute_task(self, task: AgentTask) -> threading.Thread:
        """
        Submit a task for background execution.
        Returns the daemon thread handle.
        """
        if not self._execution_lock.acquire(blocking=False):
            raise RuntimeError("Agent already executing a task")

        def _run_wrapper() -> None:
            try:
                try:
                    self.event_bus.set_state(EVState.EXECUTING)
                    result = self.agent.run(task)
                    if result.status == AgentStatus.COMPLETED:
                        self.event_bus.set_state(EVState.SUCCESS)
                    else:
                        self.event_bus.set_state(EVState.FAILED)
                except Exception as e:
                    logger.exception(f"Unexpected error in agent execution for task {task.task_id}: {e}")
                    try:
                        self.event_bus.set_state(EVState.FAILED)
                    except Exception as nested_e:
                        logger.error(f"Failed to set FAILED state during exception handling: {nested_e}")
            finally:
                try:
                    self.event_bus.set_state(EVState.IDLE)
                except Exception as final_e:
                    logger.error(f"Failed to set IDLE state in finally block: {final_e}")
                finally:
                    self._execution_lock.release()

        thread = threading.Thread(
            target=_run_wrapper,
            daemon=True,
            name=f"EVAgentThread-{task.task_id}"
        )
        thread.start()
        return thread
