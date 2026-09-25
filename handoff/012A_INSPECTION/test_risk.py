"""
Unit tests for the EVRiskEngine.
"""
import unittest
from unittest.mock import patch
from datetime import datetime

from core.risk import EVRiskEngine
from core.models import (
    ActionCategory,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
    PermissionDecision,
)


class TestEVRiskEngine(unittest.TestCase):
    def setUp(self):
        self.engine = EVRiskEngine()

    def _make_request(
        self,
        action_category,
        target=None,
        description=None,
        has_backup=False,
        reversible=False,
        requires_elevation=False,
        affects_system=False,
        affects_security=False,
        user_approved=False,
    ):
        return RiskAssessmentRequest(
            action_category=action_category,
            target=target,
            description=description,
            has_backup=has_backup,
            reversible=reversible,
            requires_elevation=requires_elevation,
            affects_system=affects_system,
            affects_security=affects_security,
            user_approved=user_approved,
        )

    def test_read_only_observation_allowed(self):
        req = self._make_request(ActionCategory.READ_ONLY_OBSERVATION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.NONE)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("Read-only observation", res.reason)

    def test_file_create_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.FILE_CREATE)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_file_create_with_approval_allowed(self):
        req = self._make_request(ActionCategory.FILE_CREATE, user_approved=True)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_file_modify_with_backup_and_reversible_no_approval_requires_approval(self):
        req = self._make_request(
            ActionCategory.FILE_MODIFY, has_backup=True, reversible=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_file_modify_with_backup_and_reversible_with_approval_allowed(self):
        req = self._make_request(
            ActionCategory.FILE_MODIFY,
            has_backup=True,
            reversible=True,
            user_approved=True,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)  # safe => MEDIUM risk (approval changes to ALLOW)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_file_modify_without_backup_higher_risk(self):
        req = self._make_request(ActionCategory.FILE_MODIFY)
        res = self.engine.assess(req)
        # Without backup, not reversible, no approval -> medium risk, requires approval
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_file_restore_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.FILE_RESTORE)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_file_restore_with_approval_allowed(self):
        req = self._make_request(
            ActionCategory.FILE_RESTORE,
            user_approved=True,
            has_backup=True,
            reversible=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_file_delete_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.FILE_DELETE)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_file_delete_with_approval_but_not_safe_still_denied(self):
        # Approved but not reversible or no backup -> deny
        req = self._make_request(
            ActionCategory.FILE_DELETE,
            user_approved=True,
            has_backup=False,
            reversible=False,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_file_delete_with_approval_and_safe_allowed(self):
        req = self._make_request(
            ActionCategory.FILE_DELETE,
            user_approved=True,
            has_backup=True,
            reversible=True,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_process_start_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.PROCESS_START)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_process_start_with_approval_allowed(self):
        req = self._make_request(ActionCategory.PROCESS_START, user_approved=True)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_process_stop_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.PROCESS_STOP)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_process_stop_with_elevation_without_approval_high_risk(self):
        req = self._make_request(
            ActionCategory.PROCESS_STOP, requires_elevation=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_command_execution_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.COMMAND_EXECUTION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)  # Updated: base risk is HIGH
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_command_execution_with_elevation_denied(self):
        req = self._make_request(
            ActionCategory.COMMAND_EXECUTION, requires_elevation=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_command_execution_with_approval_no_elevation_allowed(self):
        req = self._make_request(
            ActionCategory.COMMAND_EXECUTION, user_approved=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)  # base risk HIGH, no elevation/security/system
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_network_configuration_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.NETWORK_CONFIGURATION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_network_configuration_affects_security_denied(self):
        req = self._make_request(
            ActionCategory.NETWORK_CONFIGURATION, affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_service_configuration_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.SERVICE_CONFIGURATION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_service_configuration_affects_security_denied(self):
        req = self._make_request(
            ActionCategory.SERVICE_CONFIGURATION, affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_registry_modification_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.REGISTRY_MODIFICATION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_registry_modification_affects_security_denied(self):
        req = self._make_request(
            ActionCategory.REGISTRY_MODIFICATION, affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_software_install_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.SOFTWARE_INSTALL)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_software_install_affects_security_denied(self):
        req = self._make_request(
            ActionCategory.SOFTWARE_INSTALL, affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_software_uninstall_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.SOFTWARE_UNINSTALL)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_system_power_without_approval_requires_approval(self):
        req = self._make_request(ActionCategory.SYSTEM_POWER)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_security_configuration_always_denied(self):
        req = self._make_request(ActionCategory.SECURITY_CONFIGURATION)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_security_configuration_with_approval_still_denied(self):
        req = self._make_request(
            ActionCategory.SECURITY_CONFIGURATION, user_approved=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_credential_access_always_denied(self):
        req = self._make_request(ActionCategory.CREDENTIAL_ACCESS)
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_unknown_category_denied(self):
        # Test that unknown action category (via enum) results in DENY
        req = RiskAssessmentRequest(
            action_category=ActionCategory.UNKNOWN
        )
        res = self.engine.assess(req)
        self.assertEqual(res.action_category, ActionCategory.UNKNOWN)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertEqual(res.policy_rule, "unknown_category")

    def test_result_invariants_allow(self):
        req = self._make_request(ActionCategory.READ_ONLY_OBSERVATION)
        res = self.engine.assess(req)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_result_invariants_require_approval(self):
        req = self._make_request(ActionCategory.FILE_CREATE)
        res = self.engine.assess(req)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_result_invariants_deny(self):
        req = self._make_request(
            ActionCategory.SECURITY_CONFIGURATION
        )
        res = self.engine.assess(req)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)

    def test_evaluated_at_populated(self):
        req = self._make_request(ActionCategory.READ_ONLY_OBSERVATION)
        res = self.engine.assess(req)
        self.assertIsInstance(res.evaluated_at, datetime)
        # Just ensure it's set

    def test_file_modify_safe_with_approval_allowed_medium_risk(self):
        # safe (has_backup+reversible) => MEDIUM risk (approval changes to ALLOW)
        req = self._make_request(
            ActionCategory.FILE_MODIFY,
            has_backup=True,
            reversible=True,
            user_approved=True,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.MEDIUM)  # safe => MEDIUM risk
        self.assertEqual(res.decision, PermissionDecision.ALLOW)  # approval changes to ALLOW
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("safe", res.reason.lower())

    def test_file_modify_unsafe_even_with_approval_denied(self):
        # unsafe => HIGH/DENY even with approval
        req = self._make_request(
            ActionCategory.FILE_MODIFY,
            has_backup=False,  # unsafe: no backup
            reversible=False,  # unsafe: not reversible
            user_approved=True,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)  # unsafe => HIGH risk
        self.assertEqual(res.decision, PermissionDecision.DENY)  # unsafe => DENY even with approval
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("unsafe", res.reason.lower())

    def test_file_restore_approval_requires_reversible_and_backup_for_allow(self):
        # approval requires BOTH reversible=True AND has_backup=True for ALLOW, else DENY
        # Test case: approved but not reversible -> DENY
        req = self._make_request(
            ActionCategory.FILE_RESTORE,
            user_approved=True,
            reversible=False,  # not reversible
            has_backup=True,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)  # should be HIGH when not reversible
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("reversible", res.reason.lower())

        # Test case: approved but no backup -> DENY (reversible is true but no backup)
        req2 = self._make_request(
            ActionCategory.FILE_RESTORE,
            user_approved=True,
            reversible=True,
            has_backup=False,  # no backup
        )
        res2 = self.engine.assess(req2)
        self.assertEqual(res2.risk_level, RiskLevel.HIGH)  # should be HIGH when no backup
        self.assertEqual(res2.decision, PermissionDecision.DENY)
        self.assertFalse(res2.allowed)
        self.assertFalse(res2.requires_approval)
        self.assertIn("backup", res2.reason.lower())

        # Test case: approved with both reversible and backup -> ALLOW
        req3 = self._make_request(
            ActionCategory.FILE_RESTORE,
            user_approved=True,
            reversible=True,
            has_backup=True,
        )
        res3 = self.engine.assess(req3)
        self.assertEqual(res3.risk_level, RiskLevel.MEDIUM)  # base MEDIUM for restore
        self.assertEqual(res3.decision, PermissionDecision.ALLOW)
        self.assertTrue(res3.allowed)
        self.assertFalse(res3.requires_approval)

    def test_command_execution_base_risk_high(self):
        # COMMAND_EXECUTION base risk changed to HIGH
        req = self._make_request(
            ActionCategory.COMMAND_EXECUTION,
            user_approved=False,
            requires_elevation=False,
            affects_system=False,
            affects_security=False,
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.HIGH)  # base risk is now HIGH
        self.assertEqual(res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_approval)

    def test_exception_isolation_fail_closed(self):
        # Test that internal exceptions result in INDETERMINATE (fail closed)
        # We'll patch the _calculate_base_assessment method to raise an exception
        with patch.object(self.engine, '_calculate_base_assessment', side_effect=RuntimeError("forced risk engine failure")):
            req = self._make_request(ActionCategory.FILE_CREATE)
            res = self.engine.assess(req)
            self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
            self.assertEqual(res.decision, PermissionDecision.INDETERMINATE)
            self.assertFalse(res.allowed)
            self.assertFalse(res.requires_approval)
            self.assertIn("Internal risk engine error", res.reason)
            self.assertIsNotNone(res.error)
            self.assertEqual(res.policy_rule, "internal_error")


    def test_security_override_file_create_approved_denied(self):
        # FILE_CREATE with affects_security=True must be DENY even with approval
        req = self._make_request(
            ActionCategory.FILE_CREATE,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_file_modify_approved_denied(self):
        # FILE_MODIFY with backup/reversible/approved but affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.FILE_MODIFY,
            has_backup=True,
            reversible=True,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_file_delete_approved_denied(self):
        # FILE_DELETE with backup/reversible/approved but affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.FILE_DELETE,
            has_backup=True,
            reversible=True,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_file_restore_approved_denied(self):
        # FILE_RESTORE with backup/reversible/approved but affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.FILE_RESTORE,
            has_backup=True,
            reversible=True,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_process_start_approved_denied(self):
        # PROCESS_START with affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.PROCESS_START,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_process_stop_approved_denied(self):
        # PROCESS_STOP with affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.PROCESS_STOP,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_command_execution_approved_denied(self):
        # COMMAND_EXECUTION with affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.COMMAND_EXECUTION,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_security_override_system_power_approved_denied(self):
        # SYSTEM_POWER with affects_security=True -> DENY
        req = self._make_request(
            ActionCategory.SYSTEM_POWER,
            user_approved=True,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.CRITICAL)
        self.assertEqual(res.decision, PermissionDecision.DENY)
        self.assertFalse(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("security is denied", res.reason)

    def test_read_only_observation_unaffected_by_security(self):
        # READ_ONLY_OBSERVATION should remain NONE/ALLOW even with affects_security=True
        req = self._make_request(
            ActionCategory.READ_ONLY_OBSERVATION,
            affects_security=True
        )
        res = self.engine.assess(req)
        self.assertEqual(res.risk_level, RiskLevel.NONE)
        self.assertEqual(res.decision, PermissionDecision.ALLOW)
        self.assertTrue(res.allowed)
        self.assertFalse(res.requires_approval)
        self.assertIn("Read-only observation", res.reason)

if __name__ == '__main__':
    unittest.main()