"""
Unit tests for the EVAgent orchestration layer.
"""
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

from core.models import AgentTask, AgentAction, AgentStatus, AgentStepResult
from core.agent import EVAgent
from core.history import EVTaskHistoryStore
from tempfile import TemporaryDirectory
from pathlib import Path
from pydantic import ValidationError


class TestEVAgent(unittest.TestCase):
    def setUp(self):
        self.agent = EVAgent()

    def _task(self, task_id='history-test', **kwargs):
        return AgentTask(task_id=task_id, action=kwargs.pop('action', AgentAction.FIND_PROCESS),
                         parameters=kwargs.pop('parameters', {'name': 'python'}), created_at=datetime.now())

    def test_history_lifecycle_and_exactly_once(self):
        with TemporaryDirectory() as directory:
            store = EVTaskHistoryStore(Path(directory) / 'history.sqlite3')
            task = self._task()
            with patch('core.agent.find_processes', return_value=[]) as handler:
                result = EVAgent(store).run(task)
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertEqual(handler.call_count, 1)
            self.assertEqual([event.event_type.value for event in store.get_events(task.task_id)],
                             ['TASK_CREATED', 'TASK_STARTED', 'TASK_COMPLETED'])

    def test_history_failure_does_not_retry_or_change_result(self):
        store = MagicMock()
        store.record_task.side_effect = RuntimeError('history unavailable')
        store.mark_started.side_effect = RuntimeError('history unavailable')
        store.record_run.side_effect = RuntimeError('history unavailable')
        task = self._task()
        with patch('core.agent.find_processes', return_value=[]) as handler:
            result = EVAgent(store).run(task)
        self.assertEqual(result.status, AgentStatus.COMPLETED)
        self.assertEqual(handler.call_count, 1)

    def test_failed_paths_are_recorded(self):
        with TemporaryDirectory() as directory:
            store = EVTaskHistoryStore(Path(directory) / 'history.sqlite3')
            task = self._task(parameters={})
            result = EVAgent(store).run(task)
            self.assertEqual(result.status, AgentStatus.FAILED)
            self.assertEqual(store.get_task(task.task_id).status, AgentStatus.FAILED)

    def test_find_process_dispatch(self):
        mock_result = [MagicMock()]
        with patch('core.agent.find_processes', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test1',
                action=AgentAction.FIND_PROCESS,
                parameters={'name': 'python'},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(name='python')
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertIsNotNone(result.step)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_find_tcp_port_dispatch(self):
        mock_result = [MagicMock()]
        with patch('core.agent.find_tcp_port', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test2',
                action=AgentAction.FIND_TCP_PORT,
                parameters={'port': 4003},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(port=4003)
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_get_file_info_dispatch(self):
        mock_result = MagicMock()
        with patch('core.agent.get_file_info', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test3',
                action=AgentAction.GET_FILE_INFO,
                parameters={'path': 'C:\\temp\\test.txt'},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(path='C:\\temp\\test.txt')
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_list_directory_dispatch(self):
        mock_result = [MagicMock()]
        with patch('core.agent.list_directory', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test4',
                action=AgentAction.LIST_DIRECTORY,
                parameters={'path': 'C:\\temp'},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(path='C:\\temp')
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_read_text_file_dispatch(self):
        mock_result = MagicMock()
        with patch('core.agent.read_text_file', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test5',
                action=AgentAction.READ_TEXT_FILE,
                parameters={'path': 'C:\\temp\\test.txt', 'max_bytes': 1024},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(path='C:\\temp\\test.txt', max_bytes=1024)
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_find_files_dispatch(self):
        mock_result = [MagicMock()]
        with patch('core.agent.find_files', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test6',
                action=AgentAction.FIND_FILES,
                parameters={
                    'root': 'C:\\temp',
                    'pattern': '*.txt',
                    'recursive': True,
                    'max_results': 100,
                    'exclude_dirs': ['.git']
                },
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(
                root='C:\\temp',
                pattern='*.txt',
                recursive=True,
                max_results=100,
                exclude_dirs=['.git']
            )
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_search_text_dispatch(self):
        mock_result = [{}]
        with patch('core.agent.search_text', return_value=mock_result) as mock_func:
            task = AgentTask(
                task_id='test7',
                action=AgentAction.SEARCH_TEXT,
                parameters={
                    'root_or_file': 'C:\\temp\\test.txt',
                    'text': 'hello',
                    'recursive': True,
                    'max_results': 50,
                    'case_insensitive': True,
                    'exclude_dirs': ['__pycache__']
                },
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            mock_func.assert_called_once_with(
                root_or_file='C:\\temp\\test.txt',
                text='hello',
                recursive=True,
                max_results=50,
                case_insensitive=True,
                exclude_dirs=['__pycache__']
            )
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertTrue(result.step.success)
            self.assertEqual(result.step.result, mock_result)

    def test_invalid_tcp_port_zero(self):
        task = AgentTask(
            task_id='test8',
            action=AgentAction.FIND_TCP_PORT,
            parameters={'port': 0},
            created_at=datetime.now()
        )
        result = self.agent.run(task)
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIn('port must be between 1 and 65535', result.error)
        self.assertFalse(result.step.success if result.step else True)

    def test_invalid_tcp_port_too_large(self):
        task = AgentTask(
            task_id='test9',
            action=AgentAction.FIND_TCP_PORT,
            parameters={'port': 70000},
            created_at=datetime.now()
        )
        result = self.agent.run(task)
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIn('port must be between 1 and 65535', result.error)

    def test_invalid_tcp_port_non_int(self):
        task = AgentTask(
            task_id='test10',
            action=AgentAction.FIND_TCP_PORT,
            parameters={'port': 'abc'},
            created_at=datetime.now()
        )
        result = self.agent.run(task)
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIn('requires integer', result.error)

    def test_missing_required_parameter(self):
        task = AgentTask(
            task_id='test11',
            action=AgentAction.FIND_PROCESS,
            parameters={},  # missing 'name'
            created_at=datetime.now()
        )
        result = self.agent.run(task)
        self.assertEqual(result.status, AgentStatus.FAILED)
        self.assertIn('requires non-empty string', result.error)

    def test_tool_exception_isolation(self):
        with patch('core.agent.find_processes', side_effect=RuntimeError('simulated failure')):
            task = AgentTask(
                task_id='test12',
                action=AgentAction.FIND_PROCESS,
                parameters={'name': 'python'},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            self.assertEqual(result.status, AgentStatus.FAILED)
            self.assertIsNotNone(result.step)
            self.assertFalse(result.step.success)
            self.assertIn('simulated failure', result.step.error or result.error or '')

    def test_timing_fields(self):
        with patch('core.agent.find_processes', return_value=[]) as mock_func:
            task = AgentTask(
                task_id='test13',
                action=AgentAction.FIND_PROCESS,
                parameters={'name': 'python'},
                created_at=datetime.now()
            )
            result = self.agent.run(task)
            self.assertEqual(result.status, AgentStatus.COMPLETED)
            self.assertIsInstance(result.step.started_at, datetime)
            self.assertIsInstance(result.step.finished_at, datetime)
            self.assertGreaterEqual(result.step.duration_seconds, 0)

    def test_safety_whitelist_unsupported_action(self):
        # AgentTask.action is typed as AgentAction; unsupported strings are rejected by Pydantic.
        with self.assertRaises(ValidationError):
            AgentTask(
                task_id='unsafe',
                action='RUN_POWERSHELL',  # type: ignore
                parameters={'command': 'whoami'}
            )
        # Additionally, verify all defined actions are handled by _get_handler (no exception).
        for action in AgentAction:
            try:
                self.agent._get_handler(action)
            except ValueError:
                self.fail(f"_get_handler does not handle action {action}")


    def test_event_lifecycle_successful(self):
        from core.events import EVEventBus, EVEventType
        event_bus = MagicMock(spec=EVEventBus)
        agent = EVAgent(event_bus=event_bus)

        mock_result = [MagicMock()]
        with patch('core.agent.find_processes', return_value=mock_result):
            task = self._task()
            result = agent.run(task)

        self.assertEqual(result.status, AgentStatus.COMPLETED)

        # Check calls to event_bus.publish
        calls = event_bus.publish.call_args_list
        self.assertEqual(len(calls), 3)

        self.assertEqual(calls[0].kwargs['event_type'], EVEventType.ACTION_STARTED)
        self.assertEqual(calls[0].kwargs['correlation_id'], task.task_id)

        self.assertEqual(calls[1].kwargs['event_type'], EVEventType.STATUS)
        self.assertEqual(calls[1].kwargs['correlation_id'], task.task_id)

        self.assertEqual(calls[2].kwargs['event_type'], EVEventType.ACTION_COMPLETED)
        self.assertEqual(calls[2].kwargs['correlation_id'], task.task_id)
        self.assertTrue(calls[2].kwargs['data']['success'])
        self.assertIn('duration_seconds', calls[2].kwargs['data'])

    def test_event_lifecycle_validation_failure(self):
        from core.events import EVEventBus, EVEventType
        event_bus = MagicMock(spec=EVEventBus)
        agent = EVAgent(event_bus=event_bus)

        task = AgentTask(
            task_id='test-fail-valid',
            action=AgentAction.FIND_PROCESS,
            parameters={},  # missing 'name'
            created_at=datetime.now()
        )
        result = agent.run(task)

        self.assertEqual(result.status, AgentStatus.FAILED)

        calls = event_bus.publish.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs['event_type'], EVEventType.ACTION_STARTED)
        self.assertEqual(calls[1].kwargs['event_type'], EVEventType.STATUS)
        self.assertEqual(calls[2].kwargs['event_type'], EVEventType.ACTION_COMPLETED)
        self.assertFalse(calls[2].kwargs['data']['success'])

    def test_event_lifecycle_tool_exception(self):
        from core.events import EVEventBus, EVEventType
        event_bus = MagicMock(spec=EVEventBus)
        agent = EVAgent(event_bus=event_bus)

        with patch('core.agent.find_processes', side_effect=RuntimeError('simulated error')):
            task = self._task()
            result = agent.run(task)

        self.assertEqual(result.status, AgentStatus.FAILED)

        calls = event_bus.publish.call_args_list
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0].kwargs['event_type'], EVEventType.ACTION_STARTED)
        self.assertEqual(calls[1].kwargs['event_type'], EVEventType.STATUS)
        self.assertEqual(calls[2].kwargs['event_type'], EVEventType.ACTION_COMPLETED)
        self.assertFalse(calls[2].kwargs['data']['success'])

    def test_no_event_bus(self):
        # Already tested by other tests implicitly, but explicit test here
        agent = EVAgent()
        with patch('core.agent.find_processes', return_value=[]):
            task = self._task()
            result = agent.run(task)
        self.assertEqual(result.status, AgentStatus.COMPLETED)

    def test_event_bus_failure_isolation(self):
        from core.events import EVEventBus
        event_bus = MagicMock(spec=EVEventBus)
        event_bus.publish.side_effect = RuntimeError("event bus broken")

        agent = EVAgent(event_bus=event_bus)

        with patch('core.agent.find_processes', return_value=[]):
            task = self._task()
            result = agent.run(task)

        # Agent task succeeds despite telemetry failures
        self.assertEqual(result.status, AgentStatus.COMPLETED)
        self.assertEqual(event_bus.publish.call_count, 3)

if __name__ == '__main__':
    unittest.main()
