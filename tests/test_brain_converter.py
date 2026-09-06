"""
Unit tests for Brain-to-Task Conversion Engine (Phase 4 Task 009).

All tests are 100% offline, deterministic, and verify:
  - Conversion of validated BrainDecision proposals into authoritative AgentTask instances
  - Strict enforcement of BrainProposalValidator approval boundary
  - Non-executable decision types return zero tasks
  - VerificationType preservation
  - Deterministic ID factories and duplicate rejection
  - Caller data immutability and zero side-effects
  - Exception sanitization and fail-closed safety
"""
import copy
import unittest

from core.brain_converter import (
    BrainConversionError,
    BrainConversionInvariantError,
    BrainConversionValidationError,
    BrainTaskConverter,
)
from core.brain_models import (
    BrainActionProposal,
    BrainDecision,
    BrainDecisionType,
)
from core.brain_validator import (
    BrainProposalValidator,
    BrainValidationResult,
    BrainValidationStatus,
)
from core.models import AgentAction, AgentTask, VerificationType


class TestBrainTaskConverterBasics(unittest.TestCase):
    """Verify basic conversion and non-executable decision handling."""

    def setUp(self):
        self.converter = BrainTaskConverter()
        self.validator = BrainProposalValidator()

    def test_single_execute_action_conversion(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Find python process",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_PROCESS,
                    parameters={"name": "python.exe"},
                )
            ],
        )
        val_res = self.validator.validate(decision)
        self.assertTrue(val_res.valid)

        tasks = self.converter.convert_decision(
            decision,
            validation_result=val_res,
            id_factory=lambda: "test-task-1",
        )

        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertIsInstance(task, AgentTask)
        self.assertEqual(task.task_id, "test-task-1")
        self.assertEqual(task.action, AgentAction.FIND_PROCESS)
        self.assertEqual(task.parameters, {"name": "python.exe"})
        self.assertIsNone(task.verification_type)

    def test_multi_action_conversion_preserves_order(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Multi action inspection",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python.exe"}),
                BrainActionProposal(action=AgentAction.FIND_TCP_PORT, parameters={"port": 8080}),
                BrainActionProposal(action=AgentAction.FIND_SERVICE, parameters={"name": "Spooler"}),
            ],
        )
        val_res = self.validator.validate(decision)
        self.assertTrue(val_res.valid)

        id_counter = 0

        def sequential_ids():
            nonlocal id_counter
            id_counter += 1
            return f"task-{id_counter:03d}"

        tasks = self.converter.convert_decision(
            decision,
            validation_result=val_res,
            id_factory=sequential_ids,
        )

        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0].task_id, "task-001")
        self.assertEqual(tasks[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(tasks[1].task_id, "task-002")
        self.assertEqual(tasks[1].action, AgentAction.FIND_TCP_PORT)
        self.assertEqual(tasks[2].task_id, "task-003")
        self.assertEqual(tasks[2].action, AgentAction.FIND_SERVICE)

    def test_request_verification_preserves_verification_type(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_VERIFICATION,
            user_message="Verify spooler is running",
            proposed_actions=[
                BrainActionProposal(
                    action=AgentAction.FIND_SERVICE,
                    parameters={"name": "Spooler"},
                    verification_type=VerificationType.SERVICE_RUNNING,
                )
            ],
        )
        val_res = self.validator.validate(decision)
        self.assertTrue(val_res.valid)

        tasks = self.converter.convert_decision(
            decision,
            validation_result=val_res,
            id_factory=lambda: "verify-task-1",
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].verification_type, VerificationType.SERVICE_RUNNING)

    def test_non_executable_decisions_produce_zero_tasks(self):
        # 1. REFUSAL
        d_refusal = BrainDecision(
            decision_type=BrainDecisionType.REFUSAL,
            user_message="I cannot do that.",
        )
        val_refusal = self.validator.validate(d_refusal)
        self.assertEqual(self.converter.convert_decision(d_refusal, validation_result=val_refusal), [])

        # 2. REQUEST_CLARIFICATION
        d_clarify = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
            user_message="Clarify please.",
            clarification_prompt="Which process?",
        )
        val_clarify = self.validator.validate(d_clarify)
        self.assertEqual(self.converter.convert_decision(d_clarify, validation_result=val_clarify), [])

        # 3. EXPLANATION_ONLY
        d_explain = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="Here is some information.",
        )
        val_explain = self.validator.validate(d_explain)
        self.assertEqual(self.converter.convert_decision(d_explain, validation_result=val_explain), [])


class TestValidationApprovalBoundary(unittest.TestCase):
    """Verify that unvalidated, rejected, or mismatched proposals fail closed."""

    def setUp(self):
        self.converter = BrainTaskConverter()
        self.validator = BrainProposalValidator()

    def test_missing_or_invalid_validation_result_rejected(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Find process",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "test"})],
        )

        with self.assertRaises(BrainConversionValidationError):
            self.converter.convert_decision(decision, validation_result=None)  # type: ignore

        with self.assertRaises(BrainConversionValidationError):
            self.converter.convert_decision(decision, validation_result={"not": "valid"})  # type: ignore

    def test_unapproved_validation_result_rejected(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Find process with invalid port param",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "test"})],
        )
        # Create an artificial rejected validation result
        rejected_result = BrainValidationResult(
            valid=False,
            status=BrainValidationStatus.INVALID,
            errors=["Action rejected by security rule"],
        )

        with self.assertRaises(BrainConversionValidationError) as cm:
            self.converter.convert_decision(decision, validation_result=rejected_result)
        self.assertIn("Cannot convert unvalidated", str(cm.exception))

    def test_mismatched_validation_result_rejected(self):
        # Decision has 2 actions, but validation result has only 1 accepted action
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Two actions",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p1"}),
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p2"}),
            ],
        )
        mismatched_result = BrainValidationResult(
            valid=True,
            status=BrainValidationStatus.VALID,
            accepted_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p1"})],
        )

        with self.assertRaises(BrainConversionValidationError) as cm:
            self.converter.convert_decision(decision, validation_result=mismatched_result)
        self.assertIn("count does not match", str(cm.exception))


class TestIDGenerationAndInvariants(unittest.TestCase):
    """Verify task ID factory bounds, duplicate detection, and immutability."""

    def setUp(self):
        self.converter = BrainTaskConverter()
        self.validator = BrainProposalValidator()

    def test_duplicate_task_id_rejected(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Two actions",
            proposed_actions=[
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p1"}),
                BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p2"}),
            ],
        )
        val_res = self.validator.validate(decision)
        self.assertTrue(val_res.valid)

        # ID factory always returns the same ID
        with self.assertRaises(BrainConversionInvariantError) as cm:
            self.converter.convert_decision(
                decision,
                validation_result=val_res,
                id_factory=lambda: "duplicate-id",
            )
        self.assertIn("Duplicate task_id generated", str(cm.exception))

    def test_invalid_task_id_length_rejected(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="One action",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "p1"})],
        )
        val_res = self.validator.validate(decision)

        # Empty ID
        with self.assertRaises(BrainConversionInvariantError):
            self.converter.convert_decision(
                decision,
                validation_result=val_res,
                id_factory=lambda: "",
            )

        # Oversized ID (>64 chars)
        with self.assertRaises(BrainConversionInvariantError):
            self.converter.convert_decision(
                decision,
                validation_result=val_res,
                id_factory=lambda: "x" * 65,
            )

    def test_caller_data_not_mutated(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Immutability check",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "proc.exe"})],
        )
        decision_copy = copy.deepcopy(decision)
        val_res = self.validator.validate(decision)
        val_res_copy = copy.deepcopy(val_res)

        tasks = self.converter.convert_decision(decision, validation_result=val_res)

        # Mutate the produced task's parameters
        tasks[0].parameters["name"] = "MUTATED_VALUE"

        # Verify original decision and validation result were not mutated
        self.assertEqual(decision.proposed_actions[0].parameters["name"], "proc.exe")
        self.assertEqual(decision, decision_copy)
        self.assertEqual(val_res, val_res_copy)

    def test_deterministic_repeatability(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Repeat check",
            proposed_actions=[BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "repeat.exe"})],
        )
        val_res = self.validator.validate(decision)

        tasks1 = self.converter.convert_decision(decision, validation_result=val_res, id_factory=lambda: "fixed-id")
        tasks2 = self.converter.convert_decision(decision, validation_result=val_res, id_factory=lambda: "fixed-id")

        self.assertEqual(tasks1[0].task_id, tasks2[0].task_id)
        self.assertEqual(tasks1[0].action, tasks2[0].action)
        self.assertEqual(tasks1[0].parameters, tasks2[0].parameters)


if __name__ == "__main__":
    unittest.main()
