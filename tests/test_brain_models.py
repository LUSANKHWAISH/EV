"""
Unit tests for Brain Decision Models & Action Schemas (Phase 4 Task 002).

Tests are completely offline, deterministic, and verify:
  - Strong typing & structural invariants for all BrainDecisionTypes
  - Fail-closed behavior on malformed or hallucinated actions/fields
  - Bounded constraints on strings, actions, parameters, confidence, and context
  - JSON serialization / deserialization round-tripping
  - Compatibility with existing AgentAction and VerificationType enums
"""
import math
import json
import unittest
from datetime import datetime
from pydantic import ValidationError

from core.models import AgentAction, EVState, VerificationType
from core.brain_models import (
    BrainDecisionType,
    BrainActionProposal,
    BrainDecision,
    BrainContext,
    MAX_PROPOSED_ACTIONS,
    MAX_STRING_LENGTH,
    MAX_PARAMETERS_PER_ACTION,
)


class TestBrainModels(unittest.TestCase):
    """Test suite for BrainDecision, BrainActionProposal, and BrainContext."""

    # 1. valid EXECUTE_ACTION decision
    def test_valid_execute_action_decision(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "python.exe"},
            description="Find running Python process",
        )
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXECUTE_ACTION,
            user_message="Checking if Python is running.",
            decision_summary="User asked for Python process status.",
            proposed_actions=[proposal],
            confidence=0.95,
            provider_name="gemini",
            model_name="gemini-2.0-flash",
        )
        self.assertEqual(decision.decision_type, BrainDecisionType.EXECUTE_ACTION)
        self.assertEqual(len(decision.proposed_actions), 1)
        self.assertEqual(decision.proposed_actions[0].action, AgentAction.FIND_PROCESS)
        self.assertEqual(decision.confidence, 0.95)

    # 2. valid REQUEST_VERIFICATION decision
    def test_valid_request_verification_decision(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "notepad.exe"},
            verification_type=VerificationType.PROCESS_EXISTS,
        )
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_VERIFICATION,
            user_message="Verifying that notepad is active.",
            proposed_actions=[proposal],
            confidence=0.99,
        )
        self.assertEqual(decision.decision_type, BrainDecisionType.REQUEST_VERIFICATION)
        self.assertEqual(decision.proposed_actions[0].verification_type, VerificationType.PROCESS_EXISTS)

    # 3. valid REQUEST_CLARIFICATION decision
    def test_valid_request_clarification_decision(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
            user_message="Could you clarify which port or process you want to check?",
            clarification_prompt="Please specify a valid port number or process name.",
        )
        self.assertEqual(decision.decision_type, BrainDecisionType.REQUEST_CLARIFICATION)
        self.assertEqual(decision.proposed_actions, [])
        self.assertIsNotNone(decision.clarification_prompt)

    # 4. valid REFUSAL decision
    def test_valid_refusal_decision(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.REFUSAL,
            user_message="I cannot execute arbitrary PowerShell scripts or delete system files.",
            decision_summary="Refused destructive command.",
        )
        self.assertEqual(decision.decision_type, BrainDecisionType.REFUSAL)
        self.assertEqual(decision.proposed_actions, [])

    # 5. valid EXPLANATION_ONLY decision
    def test_valid_explanation_only_decision(self):
        decision = BrainDecision(
            decision_type=BrainDecisionType.EXPLANATION_ONLY,
            user_message="E.V. is an enhanced virtual intelligence system for Windows observation.",
        )
        self.assertEqual(decision.decision_type, BrainDecisionType.EXPLANATION_ONLY)
        self.assertEqual(decision.proposed_actions, [])

    # 6. invalid action enum rejected
    def test_invalid_action_enum_rejected(self):
        with self.assertRaises(ValidationError):
            BrainActionProposal(
                action="DELETE_ENTIRE_DISK",  # type: ignore
                parameters={},
            )

    # 7. invalid verification enum rejected
    def test_invalid_verification_enum_rejected(self):
        with self.assertRaises(ValidationError):
            BrainActionProposal(
                action=AgentAction.FIND_PROCESS,
                parameters={"name": "python"},
                verification_type="NON_EXISTENT_VERIFICATION",  # type: ignore
            )

    # 8. missing action for executable decision rejected
    def test_missing_action_for_execute_decision_rejected(self):
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="I will execute this action.",
                proposed_actions=[],  # Empty actions rejected for EXECUTE_ACTION
            )

    def test_missing_action_for_request_verification_rejected(self):
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.REQUEST_VERIFICATION,
                user_message="Verifying.",
                proposed_actions=[],
            )

    def test_request_verification_without_verification_type_rejected(self):
        proposal_without_vtype = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "python"},
            verification_type=None,
        )
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.REQUEST_VERIFICATION,
                user_message="Verifying.",
                proposed_actions=[proposal_without_vtype],
            )

    # 9. missing clarification prompt for clarification decision rejected
    def test_missing_clarification_prompt_rejected(self):
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
                user_message="Please clarify.",
                clarification_prompt=None,
            )

    # 10. clarification with executable actions rejected
    def test_clarification_with_executable_actions_rejected(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "python"},
        )
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.REQUEST_CLARIFICATION,
                user_message="Clarify.",
                clarification_prompt="What process?",
                proposed_actions=[proposal],
            )

    # 11. refusal with executable actions rejected
    def test_refusal_with_executable_actions_rejected(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "python"},
        )
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.REFUSAL,
                user_message="Refused.",
                proposed_actions=[proposal],
            )

    # 12. explanation-only with executable actions rejected
    def test_explanation_only_with_executable_actions_rejected(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_PROCESS,
            parameters={"name": "python"},
        )
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXPLANATION_ONLY,
                user_message="Here is an explanation.",
                proposed_actions=[proposal],
            )

    # 13. invalid confidence < 0 rejected
    def test_invalid_confidence_negative_rejected(self):
        proposal = BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python"})
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="Action.",
                proposed_actions=[proposal],
                confidence=-0.1,
            )

    # 14. invalid confidence > 1 rejected
    def test_invalid_confidence_too_high_rejected(self):
        proposal = BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python"})
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="Action.",
                proposed_actions=[proposal],
                confidence=1.05,
            )

    # 15. NaN / infinite confidence rejected
    def test_nan_or_infinite_confidence_rejected(self):
        proposal = BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": "python"})
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="Action.",
                proposed_actions=[proposal],
                confidence=float("nan"),
            )
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="Action.",
                proposed_actions=[proposal],
                confidence=float("inf"),
            )

    # 16. oversized action list rejected
    def test_oversized_action_list_rejected(self):
        proposals = [
            BrainActionProposal(action=AgentAction.FIND_PROCESS, parameters={"name": f"proc_{i}"})
            for i in range(MAX_PROPOSED_ACTIONS + 1)
        ]
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXECUTE_ACTION,
                user_message="Many actions.",
                proposed_actions=proposals,
            )

    # 17. oversized fields rejected
    def test_oversized_user_message_rejected(self):
        oversized = "a" * (MAX_STRING_LENGTH + 1)
        with self.assertRaises(ValidationError):
            BrainDecision(
                decision_type=BrainDecisionType.EXPLANATION_ONLY,
                user_message=oversized,
            )

    # 18. serialization round-trip
    def test_json_serialization_round_trip(self):
        proposal = BrainActionProposal(
            action=AgentAction.FIND_SERVICE,
            parameters={"name": "Spooler"},
            verification_type=VerificationType.SERVICE_RUNNING,
            description="Verify Print Spooler service",
        )
        decision = BrainDecision(
            decision_id="dec-123",
            decision_type=BrainDecisionType.REQUEST_VERIFICATION,
            user_message="Checking spooler service status.",
            decision_summary="Service check.",
            proposed_actions=[proposal],
            confidence=0.9,
            provider_name="gemini",
            model_name="gemini-2.0-flash",
            token_usage={"prompt": 150, "completion": 45},
        )

        json_str = decision.model_dump_json()
        loaded_dict = json.loads(json_str)
        reconstituted = BrainDecision.model_validate(loaded_dict)

        self.assertEqual(reconstituted.decision_id, "dec-123")
        self.assertEqual(reconstituted.decision_type, BrainDecisionType.REQUEST_VERIFICATION)
        self.assertEqual(reconstituted.proposed_actions[0].action, AgentAction.FIND_SERVICE)
        self.assertEqual(reconstituted.proposed_actions[0].verification_type, VerificationType.SERVICE_RUNNING)
        self.assertEqual(reconstituted.confidence, 0.9)

    # 19. deserialization rejection of invalid json/fields
    def test_deserialization_rejection_of_invalid_data(self):
        invalid_payload = {
            "decision_type": "EXECUTE_ACTION",
            "user_message": "test",
            "proposed_actions": [
                {"action": "INVALID_ACTION_NAME", "parameters": {}}
            ]
        }
        with self.assertRaises(ValidationError):
            BrainDecision.model_validate(invalid_payload)

    # 20. unexpected executable extra fields rejected (extra="forbid")
    def test_unexpected_fields_rejected_fail_closed(self):
        with self.assertRaises(ValidationError):
            BrainActionProposal.model_validate({
                "action": "FIND_PROCESS",
                "parameters": {"name": "python"},
                "execute_arbitrary_code": True,  # Unexpected extra field
            })

        with self.assertRaises(ValidationError):
            BrainDecision.model_validate({
                "decision_type": "EXPLANATION_ONLY",
                "user_message": "Info.",
                "untrusted_admin_override": True,  # Unexpected extra field
            })

    # 21. existing AgentAction compatibility
    def test_agent_action_compatibility(self):
        for action in AgentAction:
            proposal = BrainActionProposal(action=action, parameters={})
            self.assertEqual(proposal.action, action)

    # 22. existing VerificationType compatibility
    def test_verification_type_compatibility(self):
        for vtype in VerificationType:
            proposal = BrainActionProposal(
                action=AgentAction.FIND_PROCESS,
                parameters={"name": "test"},
                verification_type=vtype,
            )
            self.assertEqual(proposal.verification_type, vtype)

    # 23. BrainContext bounded validation
    def test_brain_context_validation(self):
        ctx = BrainContext(
            user_input="Is port 80 open?",
            current_state=EVState.IDLE,
            platform="windows",
            recent_task_summaries=[{"task_id": "1", "action": "FIND_TCP_PORT", "success": True}],
        )
        self.assertEqual(ctx.user_input, "Is port 80 open?")
        self.assertEqual(ctx.current_state, EVState.IDLE)
        self.assertEqual(len(ctx.available_actions), len(AgentAction))

    def test_brain_context_forbids_extra_fields(self):
        with self.assertRaises(ValidationError):
            BrainContext.model_validate({
                "user_input": "test",
                "secret_api_key": "12345",  # Unexpected extra field
            })

    # 24. Action proposal parameter bounds
    def test_action_proposal_parameters_bound(self):
        too_many_params = {f"k_{i}": f"v_{i}" for i in range(MAX_PARAMETERS_PER_ACTION + 1)}
        with self.assertRaises(ValidationError):
            BrainActionProposal(
                action=AgentAction.FIND_PROCESS,
                parameters=too_many_params,
            )


if __name__ == "__main__":
    unittest.main()
