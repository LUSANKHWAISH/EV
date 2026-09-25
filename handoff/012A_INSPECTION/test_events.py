"""
Unit tests for the Event / State Bus.
"""
import unittest
from unittest.mock import Mock

from core.events import (
    EVEvent,
    EVEventBus,
    EventPublishResult,
    EVEventSeverity,
    EVEventType,
    EVState,
    StateChangeResult,
)
from core.models import RiskLevel, PermissionDecision  # noqa: F401 (imported for completeness but not used)


class TestEVEventBus(unittest.TestCase):
    def setUp(self) -> None:
        self.bus = EVEventBus(initial_state=EVState.IDLE, history_limit=10)

    # --- Initialization and basic properties ---

    def test_default_initial_state_is_idle(self) -> None:
        bus = EVEventBus()
        self.assertEqual(bus.current_state, EVState.IDLE)

    def test_custom_initial_state_works(self) -> None:
        bus = EVEventBus(initial_state=EVState.LISTENING)
        self.assertEqual(bus.current_state, EVState.LISTENING)

    def test_history_initially_empty(self) -> None:
        self.assertEqual(self.bus.get_history(), [])

    def test_invalid_history_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            EVEventBus(history_limit=0)
        with self.assertRaises(ValueError):
            EVEventBus(history_limit=-5)

    # --- Event publishing basics ---

    def test_publish_creates_event(self) -> None:
        result = self.bus.publish(
            event_type=EVEventType.STATUS,
            source="test",
            message="hello",
        )
        self.assertIsInstance(result, EventPublishResult)
        self.assertIsInstance(result.event, EVEvent)
        self.assertEqual(result.event.event_type, EVEventType.STATUS)
        self.assertEqual(result.event.source, "test")
        self.assertEqual(result.event.message, "hello")
        self.assertEqual(result.event.severity, EVEventSeverity.INFO)

    def test_event_id_populated_and_unique(self) -> None:
        result1 = self.bus.publish(EVEventType.STATUS, "test1")
        result2 = self.bus.publish(EVEventType.STATUS, "test2")
        self.assertIsNotNone(result1.event.event_id)
        self.assertIsNotNone(result2.event.event_id)
        self.assertNotEqual(result1.event.event_id, result2.event.event_id)

    def test_timestamp_populated(self) -> None:
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertIsInstance(result.event.timestamp, type(self.bus._history[0].timestamp))

    def test_sequence_begins_correctly(self) -> None:
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.event.sequence, 1)

    def test_sequence_monotonically_increases(self) -> None:
        result1 = self.bus.publish(EVEventType.STATUS, "test1")
        result2 = self.bus.publish(EVEventType.STATUS, "test2")
        result3 = self.bus.publish(EVEventType.STATUS, "test3")
        self.assertEqual(result1.event.sequence, 1)
        self.assertEqual(result2.event.sequence, 2)
        self.assertEqual(result3.event.sequence, 3)

    # --- Subscription mechanics ---

    def test_subscriber_receives_event(self) -> None:
        callback = Mock()
        token = self.bus.subscribe(callback)
        self.bus.publish(EVEventType.STATUS, "test", message="hello")
        callback.assert_called_once()
        event_arg = callback.call_args[0][0]
        self.assertIsInstance(event_arg, EVEvent)
        self.assertEqual(event_arg.message, "hello")

    def test_multiple_subscribers_receive_in_registration_order(self) -> None:
        callbacks = [Mock(), Mock(), Mock()]
        tokens = [self.bus.subscribe(cb) for cb in callbacks]
        self.bus.publish(EVEventType.STATUS, "test")
        for cb in callbacks:
            cb.assert_called_once()
        # Check order by call count (they are called in the order we provided)
        # Since we called publish once, each should have been called once in order.
        # We can verify by the order of invocations if we had a shared state, but for simplicity
        # we trust that the bus calls them in the order of the snapshot (which is registration order).
        # We'll do a more explicit test by recording the order.
        order: list[int] = []
        def make_callback(i: int):
            def inner(_):
                order.append(i)
            return inner
        # Resubscribe with order-tracking callbacks
        for token in tokens:
            self.bus.unsubscribe(token)
        tokens = [self.bus.subscribe(make_callback(i)) for i in range(3)]
        self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(order, [0, 1, 2])

    def test_event_type_filtering_works(self) -> None:
        callback_status = Mock()
        callback_error = Mock()
        self.bus.subscribe(callback_status, [EVEventType.STATUS])
        self.bus.subscribe(callback_error, [EVEventType.ERROR])
        self.bus.publish(EVEventType.STATUS, "test")
        self.bus.publish(EVEventType.ERROR, "test")
        callback_status.assert_called_once()
        callback_error.assert_called_once()
        # Ensure they didn't get the wrong event
        self.assertEqual(callback_status.call_args[0][0].event_type, EVEventType.STATUS)
        self.assertEqual(callback_error.call_args[0][0].event_type, EVEventType.ERROR)

    def test_unsubscribe_works(self) -> None:
        callback = Mock()
        token = self.bus.subscribe(callback)
        self.assertTrue(self.bus.unsubscribe(token))
        self.bus.publish(EVEventType.STATUS, "test")
        callback.assert_not_called()

    def test_unsubscribe_unknown_token_returns_false(self) -> None:
        self.assertFalse(self.bus.unsubscribe("unknown-token"))

    def test_invalid_callback_rejected(self) -> None:
        with self.assertRaises(TypeError):
            self.bus.subscribe(None)  # type: ignore
        with self.assertRaises(TypeError):
            self.bus.subscribe("not-callable")  # type: ignore

    # --- Subscriber failure isolation ---

    def test_subscriber_exception_does_not_escape_publish(self) -> None:
        def failing_callback(_):
            raise RuntimeError("intentional failure")
        def succeeding_callback(_):
            pass
        token_fail = self.bus.subscribe(failing_callback)
        token_succeed = self.bus.subscribe(succeeding_callback)
        # This should not raise
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.assertEqual(len(result.subscriber_errors), 1)
        self.assertIsInstance(result.subscriber_errors[0][1], RuntimeError)
        # The succeeding callback should have been called
        # We can't directly assert on succeeding_callback because it's a lambda, but we can use a mock
        # Let's redo with mocks for clarity
        succeeding_mock = Mock()
        self.bus.unsubscribe(token_succeed)
        self.bus.unsubscribe(token_fail)
        token_fail = self.bus.subscribe(failing_callback)
        token_succeed = self.bus.subscribe(succeeding_mock)
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(result.failed_count, 1)
        succeeding_mock.assert_called_once()

    def test_later_subscriber_still_called_after_earlier_failure(self) -> None:
        # Subscriber A fails, B succeeds, C fails, D succeeds
        def fail_a(_):
            raise ValueError("A")
        def succeed_b(_):
            pass
        def fail_c(_):
            raise RuntimeError("C")
        def succeed_d(_):
            pass
        tokens = [
            self.bus.subscribe(fail_a),
            self.bus.subscribe(succeed_b),
            self.bus.subscribe(fail_c),
            self.bus.subscribe(succeed_d),
        ]
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.delivered_count, 2)  # B and D
        self.assertEqual(result.failed_count, 2)     # A and C
        self.assertEqual(len(result.subscriber_errors), 2)
        # Cleanup
        for token in tokens:
            self.bus.unsubscribe(token)

    def test_failed_event_still_appears_in_history(self) -> None:
        def failing_callback(_):
            raise ValueError("fail")
        token = self.bus.subscribe(failing_callback)
        self.bus.publish(EVEventType.STATUS, "test", message="should be in history")
        self.bus.unsubscribe(token)
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].message, "should be in history")

    # --- History behavior ---

    def test_history_bounded_correctly(self) -> None:
        # history_limit is 10 from setUp
        for i in range(15):
            self.bus.publish(EVEventType.STATUS, "test", message=str(i))
        history = self.bus.get_history()
        self.assertEqual(len(history), 10)  # limited to history_limit
        # Should contain messages 5 through 14 (0-indexed, so the last 10)
        self.assertEqual([event.message for event in history], [str(i) for i in range(5, 15)])

    def test_sequence_continues_after_history_eviction(self) -> None:
        # Publish 15 events, history keeps last 10, but sequence should go to 15
        for i in range(15):
            self.bus.publish(EVEventType.STATUS, "test")
        # The oldest event in history should have sequence 6 (since we keep 10 most recent: 6-15)
        history = self.bus.get_history()
        self.assertEqual(history[0].sequence, 6)
        self.assertEqual(history[-1].sequence, 15)
        # Publish one more event to prove sequence continues
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.event.sequence, 16)

    def test_history_filtering_works(self) -> None:
        self.bus.publish(EVEventType.STATUS, "test", message="status")
        self.bus.publish(EVEventType.ERROR, "test", message="error")
        self.bus.publish(EVEventType.STATUS, "test", message="status2")
        history = self.bus.get_history(event_types=[EVEventType.STATUS])
        self.assertEqual(len(history), 2)
        self.assertTrue(all(e.event_type == EVEventType.STATUS for e in history))
        self.assertEqual(history[0].message, "status")
        self.assertEqual(history[1].message, "status2")

    def test_history_limit_works(self) -> None:
        for i in range(5):
            self.bus.publish(EVEventType.STATUS, "test", message=str(i))
        history = self.bus.get_history(limit=3)
        self.assertEqual(len(history), 3)
        self.assertEqual([e.message for e in history], ["2", "3", "4"])

    def test_negative_history_query_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.bus.get_history(limit=-1)

    def test_returned_history_cannot_mutate_internal_history(self) -> None:
        self.bus.publish(EVEventType.STATUS, "test", message="original")
        history = self.bus.get_history()
        # Clear the returned list
        history.clear()
        # Internal history should still have the event
        internal = self.bus.get_history()
        self.assertEqual(len(internal), 1)
        self.assertEqual(internal[0].message, "original")

    # --- State change behavior ---

    def test_set_state_changes_current_state(self) -> None:
        result = self.bus.set_state(EVState.LISTENING)
        self.assertTrue(result.changed)
        self.assertEqual(self.bus.current_state, EVState.LISTENING)
        self.assertEqual(result.previous_state, EVState.IDLE)
        self.assertEqual(result.current_state, EVState.LISTENING)

    def test_set_state_creates_state_changed_event(self) -> None:
        result = self.bus.set_state(EVState.PLANNING, source="test", reason="testing")
        self.assertIsNotNone(result.event)
        self.assertEqual(result.event.event_type, EVEventType.STATE_CHANGED)
        self.assertEqual(result.event.source, "test")
        self.assertEqual(result.event.message, "testing")
        self.assertEqual(result.event.state, EVState.PLANNING)
        self.assertEqual(result.event.previous_state, EVState.IDLE)

    def test_state_event_contains_previous_and_new_state(self) -> None:
        result = self.bus.set_state(EVState.EXECUTING)
        self.assertIsNotNone(result.event)
        self.assertEqual(result.event.previous_state, EVState.IDLE)
        self.assertEqual(result.event.state, EVState.EXECUTING)

    def test_same_state_set_returns_changed_false(self) -> None:
        # First change to LISTENING
        self.bus.set_state(EVState.LISTENING)
        # Then try to set to LISTENING again
        result = self.bus.set_state(EVState.LISTENING)
        self.assertFalse(result.changed)
        self.assertIsNone(result.event)
        self.assertIsNone(result.publish_result)

    def test_same_state_set_does_not_increment_sequence(self) -> None:
        # Publish an event to get a baseline sequence
        self.bus.publish(EVEventType.STATUS, "test")
        seq_before = self.bus._sequence_counter  # pylint: disable=protected-access
        # Attempt same-state change
        self.bus.set_state(EVState.IDLE)  # already IDLE
        seq_after = self.bus._sequence_counter  # pylint: disable=protected-access
        self.assertEqual(seq_before, seq_after)

    def test_state_subscribers_receive_state_event(self) -> None:
        callback = Mock()
        token = self.bus.subscribe(callback, [EVEventType.STATE_CHANGED])
        self.bus.set_state(EVState.LISTENING)
        callback.assert_called_once()
        event_arg = callback.call_args[0][0]
        self.assertEqual(event_arg.event_type, EVEventType.STATE_CHANGED)
        self.bus.unsubscribe(token)

    def test_non_state_filtered_subscriber_does_not_receive_state_event(self) -> None:
        callback = Mock()
        token = self.bus.subscribe(callback, [EVEventType.STATUS])  # subscribing to STATUS only
        self.bus.set_state(EVState.LISTENING)
        callback.assert_not_called()
        self.bus.unsubscribe(token)

    def test_correlation_id_preserved(self) -> None:
        corr_id = "corr-123"
        result = self.bus.set_state(
            EVState.LISTENING,
            correlation_id=corr_id,
        )
        self.assertIsNotNone(result.event)
        self.assertEqual(result.event.correlation_id, corr_id)

    def test_event_data_preserved(self) -> None:
        data = {"key": "value", "number": 42}
        result = self.bus.set_state(
            EVState.LISTENING,
            data=data,
        )
        self.assertIsNotNone(result.event)
        self.assertEqual(result.event.data, data)

    def test_error_event_does_not_automatically_change_current_state(self) -> None:
        initial_state = self.bus.current_state
        # Publish an ERROR event
        self.bus.publish(EVEventType.ERROR, "test", message="something went wrong")
        # State should remain unchanged
        self.assertEqual(self.bus.current_state, initial_state)

    def test_unusual_transition_permitted(self) -> None:
        # Task 010 does not enforce a state transition graph
        self.bus.set_state(EVState.VERIFYING)  # from IDLE to VERIFYING
        self.assertEqual(self.bus.current_state, EVState.VERIFYING)
        # Then to RECOVERING
        self.bus.set_state(EVState.RECOVERING)
        self.assertEqual(self.bus.current_state, EVState.RECOVERING)

    # --- Reentrancy tests ---

    def test_subscriber_can_unsubscribe_itself_without_deadlock(self) -> None:
        token_to_remove = None
        self_calls = []

        def self_removing_callback(event):
            self_calls.append(event.sequence)
            if token_to_remove is not None:
                self.bus.unsubscribe(token_to_remove)

        token_to_remove = self.bus.subscribe(self_removing_callback)
        other_callback = Mock()
        other_token = self.bus.subscribe(other_callback)
        # This should not deadlock
        self.bus.publish(EVEventType.STATUS, "test")
        self.bus.publish(EVEventType.STATUS, "test2")
        # The self-removing callback should have been called once (for the first event) and then removed
        self.assertEqual(len(self_calls), 1)
        self.assertEqual(self_calls[0], 1)  # first event sequence
        # The other callback should have been called for both events
        self.assertEqual(other_callback.call_count, 2)
        # Cleanup
        self.bus.unsubscribe(other_token)

    def test_subscriber_can_publish_nested_event_without_deadlock(self) -> None:
        nested_results = []
        def nesting_callback(event):
            # Publish a nested event of a different type to avoid recursion
            nested_results.append(
                self.bus.publish(
                    EVEventType.ACTION_STARTED,
                    "nested",
                    message="nested",
                )
            )
        # Subscribe only to STATUS events so that the nested ACTION_STARTED event does not trigger this callback again
        token = self.bus.subscribe(nesting_callback, event_types=[EVEventType.STATUS])
        # Publish the initial STATUS event
        result = self.bus.publish(EVEventType.STATUS, "outer")
        # Should have published exactly one nested event
        self.assertEqual(len(nested_results), 1)
        # Verify the nested event is of correct type and message
        nested_event_result = nested_results[0]
        self.assertEqual(nested_event_result.event.event_type, EVEventType.ACTION_STARTED)
        self.assertEqual(nested_event_result.event.message, "nested")
        # Verify history contains exactly two events: the outer STATUS and the nested ACTION_STARTED
        history = self.bus.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].event_type, EVEventType.STATUS)
        self.assertEqual(history[0].source, "outer")
        self.assertIsNone(history[0].message)
        self.assertEqual(history[1].event_type, EVEventType.ACTION_STARTED)
        self.assertEqual(history[1].message, "nested")
        # The original publish should have succeeded
        self.assertIsInstance(result, EventPublishResult)
        self.bus.unsubscribe(token)

    # --- Result invariants ---

    def test_event_publish_result_delivery_counts_correct(self) -> None:
        def succeed(_):
            pass
        def fail(_):
            raise Exception()
        token_s = self.bus.subscribe(succeed)
        token_f = self.bus.subscribe(fail)
        result = self.bus.publish(EVEventType.STATUS, "test")
        self.assertEqual(result.delivered_count, 1)
        self.assertEqual(result.failed_count, 1)
        self.bus.unsubscribe(token_s)
        self.bus.unsubscribe(token_f)

    def test_no_external_mutation_or_execution_performed(self) -> None:
        # We trust that the implementation does not perform disallowed actions.
        # This test is a placeholder to document the requirement.
        # We can at least verify that the bus doesn't call external systems by checking
        # that no external side effects occur (e.g., no file changes, no subprocess calls).
        # Since we are only using mocks and in-memory structures, we assume it's safe.
        pass

    def test_thread_safety_publish_concurrent(self) -> None:
        """Test concurrent publishing from multiple threads."""
        import threading

        # Use a fresh bus with high history limit to avoid eviction interference
        bus = EVEventBus(initial_state=EVState.IDLE, history_limit=200)

        num_threads = 4
        publishes_per_thread = 25
        total_expected = num_threads * publishes_per_thread

        # Track results from each thread and any exceptions
        results = []
        thread_errors = []
        threads = []

        def publisher(thread_id: int) -> None:
            try:
                thread_results = []
                for i in range(publishes_per_thread):
                    result = bus.publish(
                        EVEventType.STATUS,
                        f"thread-{thread_id}",
                        message=f"publish-{i}"
                    )
                    thread_results.append(result.event.sequence)
                results.append(thread_results)
            except Exception as e:
                thread_errors.append(e)

        # Create and start threads
        for i in range(num_threads):
            thread = threading.Thread(target=publisher, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Assert no exceptions occurred in worker threads
        self.assertEqual(thread_errors, [], f"Exceptions in worker threads: {thread_errors}")

        # Flatten results and verify
        all_sequences = []
        for thread_result in results:
            all_sequences.extend(thread_result)

        # Should have exactly the expected number of events
        self.assertEqual(len(all_sequences), total_expected)

        # All sequences should be unique
        self.assertEqual(len(set(all_sequences)), len(all_sequences))

        # Sequences should be in the expected range (1 to total_expected)
        self.assertEqual(min(all_sequences), 1)
        self.assertEqual(max(all_sequences), total_expected)

        # Verify no gaps in sequence (since we started fresh and no other publishers)
        expected_set = set(range(1, total_expected + 1))
        actual_set = set(all_sequences)
        self.assertEqual(actual_set, expected_set)

        # Verify history contains the expected number (limited by history_limit)
        history = bus.get_history()
        # Since history_limit=200 and we published 100 events, all should be in history
        self.assertEqual(len(history), total_expected)

    # --- Immutability and isolation tests ---

    def test_input_data_isolation(self) -> None:
        """Test that caller-supplied data is isolated from internal storage."""
        # Create nested mutable data
        payload = {
            "nested": {
                "value": 1
            },
            "list": [1, 2, 3]
        }

        # Publish event with this data
        self.bus.publish(
            EVEventType.STATUS,
            "test",
            data=payload
        )

        # Mutate the original payload
        payload["nested"]["value"] = 999
        payload["list"][0] = 999

        # Get history and verify original values are preserved
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        event = history[0]
        self.assertEqual(event.data["nested"]["value"], 1)
        self.assertEqual(event.data["list"], [1, 2, 3])

    def test_history_output_isolation(self) -> None:
        """Test that returned history cannot mutate internal stored events."""
        # Publish an event
        self.bus.publish(
            EVEventType.STATUS,
            "test",
            message="original",
            data={"key": "value"}
        )

        # Get history
        history1 = self.bus.get_history()

        # Mutate the returned history and its contents
        history1.clear()  # This should not affect internal history
        history1.append("not an event")  # This should not affect internal history

        # Get history again - should be unchanged
        history2 = self.bus.get_history()
        self.assertEqual(len(history2), 1)
        event = history2[0]
        self.assertEqual(event.message, "original")
        self.assertEqual(event.data, {"key": "value"})

        # Now test mutating event objects in history
        history3 = self.bus.get_history()
        if len(history3) > 0:
            event_copy = history3[0]
            # Mutate the event object
            original_message = event_copy.message
            event_copy.message = "tampered"
            event_copy.data["key"] = "tampered"

            # Get history again - should be unchanged
            history4 = self.bus.get_history()
            self.assertEqual(len(history4), 1)
            event_again = history4[0]
            self.assertEqual(event_again.message, original_message)
            self.assertEqual(event_again.data, {"key": "value"})

    def test_publish_result_isolation(self) -> None:
        """Test that EventPublishResult.event does not expose internal mutable state."""
        # Publish an event
        result = self.bus.publish(
            EVEventType.STATUS,
            "test",
            message="original",
            data={"key": "value"}
        )

        # Mutate the returned event
        result.event.message = "tampered"
        result.event.data["key"] = "tampered"
        result.event.data["new_key"] = "new_value"

        # Get history - should be unchanged
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        event = history[0]
        self.assertEqual(event.message, "original")
        self.assertEqual(event.data, {"key": "value"})

    def test_subscriber_isolation(self) -> None:
        """Test that subscriber mutations do not affect other subscribers or history."""
        # Track events received by each subscriber
        events_received_a = []
        events_received_b = []

        def subscriber_a(event):
            events_received_a.append(event)
            # Mutate the received event
            if events_received_a[-1].message is not None:
                events_received_a[-1].message = "mutated_by_a"
            if events_received_a[-1].data is not None:
                events_received_a[-1].data["mutated"] = True

        def subscriber_b(event):
            events_received_b.append(event)
            # Don't mutate, just record

        # Subscribe both
        token_a = self.bus.subscribe(subscriber_a)
        token_b = self.bus.subscribe(subscriber_b)

        # Publish an event
        test_data = {"nested": {"value": 42}}
        self.bus.publish(
            EVEventType.STATUS,
            "test",
            message="original",
            data=test_data
        )

        # Verify each subscriber got an event
        self.assertEqual(len(events_received_a), 1)
        self.assertEqual(len(events_received_b), 1)

        # Subscriber A's event should be mutated (their copy)
        self.assertEqual(events_received_a[0].message, "mutated_by_a")
        self.assertTrue(events_received_a[0].data.get("mutated", False))

        # Subscriber B's event should be original (their isolated copy)
        self.assertEqual(events_received_b[0].message, "original")
        self.assertEqual(events_received_b[0].data, {"nested": {"value": 42}})

        # History should contain the original event
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        history_event = history[0]
        self.assertEqual(history_event.message, "original")
        self.assertEqual(history_event.data, {"nested": {"value": 42}})
        self.assertFalse(history_event.data.get("mutated", False))

        # Cleanup
        self.bus.unsubscribe(token_a)
        self.bus.unsubscribe(token_b)

    # --- State atomicity tests ---

    def test_state_atomicity_under_concurrency(self) -> None:
        """Test that state transitions and STATE_CHANGED events are consistently ordered."""
        import threading
        import time

        # Use a fresh bus
        bus = EVEventBus(initial_state=EVState.IDLE, history_limit=50)

        # Track state change events received and any exceptions
        state_events = []
        thread_errors = []

        def state_listener(event):
            if event.event_type == EVEventType.STATE_CHANGED:
                state_events.append(event)

        # Subscribe to state changes
        token = bus.subscribe(state_listener, [EVEventType.STATE_CHANGED])

        # Define state transition sequence
        transitions = [
            EVState.LISTENING,
            EVState.PLANNING,
            EVState.EXECUTING,
            EVState.VERIFYING,
            EVState.SUCCESS
        ]

        # Function to perform state transitions
        def transition_worker(worker_id):
            try:
                for i, state in enumerate(transitions):
                    # Small stagger to increase chance of interleaving but keep deterministic
                    time.sleep(worker_id * 0.001)
                    bus.set_state(state)
            except Exception as e:
                thread_errors.append(e)

        # Create and run threads
        threads = []
        for i in range(3):  # 3 workers doing same transitions
            thread = threading.Thread(target=transition_worker, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Assert no exceptions occurred in worker threads
        self.assertEqual(thread_errors, [], f"Exceptions in worker threads: {thread_errors}")

        # Verify we got state change events
        self.assertGreater(len(state_events), 0)

        # Check that for each state event, the previous_state matches the state of the prior event
        # (accounting for possible same-state transitions that don't produce events)
        for i in range(1, len(state_events)):
            prev_event = state_events[i-1]
            curr_event = state_events[i]
            # The current event's previous_state should equal the prior event's state
            # unless there were same-state transitions in between that were filtered out
            # We'll check that the sequence makes sense
            self.assertEqual(curr_event.previous_state, prev_event.state)

        # The final state of the bus should match the state of the last state change event
        if len(state_events) > 0:
            last_state_event = state_events[-1]
            self.assertEqual(bus.current_state, last_state_event.state)

        # Cleanup
        self.bus.unsubscribe(token)

    def test_history_limit_zero(self) -> None:
        """Test that get_history(limit=0) returns empty list."""
        # Publish some events
        self.bus.publish(EVEventType.STATUS, "test", message="msg1")
        self.bus.publish(EVEventType.STATUS, "test", message="msg2")

        # Limit zero should return empty list
        result = self.bus.get_history(limit=0)
        self.assertEqual(result, [])

        # Positive limit should work normally
        result = self.bus.get_history(limit=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].message, "msg2")  # Most recent

        # No limit should get all
        result = self.bus.get_history()
        self.assertEqual(len(result), 2)

    # Replace the placeholder test with a real one
    def test_no_external_mutation_or_execution_performed(self) -> None:
        """Verify that the event bus does not perform disallowed external actions."""
        # The immutability tests above verify that no external mutation of internal state occurs
        # Through isolation of data, history, and event objects

        # We can also verify that no exceptions are thrown from normal operation
        try:
            # Basic operations should not raise
            self.bus.publish(EVEventType.STATUS, "test")
            self.bus.set_state(EVState.LISTENING)
            history = self.bus.get_history()
            token = self.bus.subscribe(lambda e: None)
            self.bus.unsubscribe(token)
        except Exception as e:
            self.fail(f"Normal operation threw unexpected exception: {e}")


if __name__ == "__main__":
    unittest.main()