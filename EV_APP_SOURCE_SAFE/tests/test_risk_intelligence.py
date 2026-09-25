"""
Comprehensive unit and security tests for Phase 5 Task 009:
Risk Intelligence & Risk Model Hardening (core/risk_intelligence.py).
"""
import unittest
from unittest.mock import MagicMock, patch

from core.models import (
    ActionCategory,
    AgentAction,
    AgentTask,
    PermissionDecision,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
    VerificationType,
)
from core.risk import EVRiskEngine
from core.risk_intelligence import (
    ActionScope,
    CompoundExposureReport,
    EVRiskIntelligenceEngine,
    PrivilegeScope,
    ReversibilityClass,
    RiskFactor,
    RiskImpact,
    RiskIntelligenceResult,
    analyze_task,
    analyze_tasks,
    analyze_transaction,
    calculate_compound_exposure,
)
from core.transaction import CompoundTransaction


class TestRiskIntelligenceEnumsAndModels(unittest.TestCase):
    """Test suite for taxonomy enums, structural contracts, and model immutability."""

    def test_enums_values(self):
        """Verify all taxonomy enum members match expected constants."""
        self.assertEqual(RiskImpact.READ_ONLY.value, "READ_ONLY")
        self.assertEqual(RiskImpact.CRITICAL.value, "CRITICAL")
        self.assertEqual(ReversibilityClass.FULLY_REVERSIBLE.value, "FULLY_REVERSIBLE")
        self.assertEqual(ReversibilityClass.NON_REVERSIBLE.value, "NON_REVERSIBLE")
        self.assertEqual(ActionScope.SINGLE_FILE.value, "SINGLE_FILE")
        self.assertEqual(ActionScope.SYSTEM_WIDE.value, "SYSTEM_WIDE")
        self.assertEqual(PrivilegeScope.STANDARD_USER.value, "STANDARD_USER")
        self.assertEqual(PrivilegeScope.SYSTEM_PROTECTED.value, "SYSTEM_PROTECTED")
        self.assertEqual(RiskFactor.MUTATION.value, "MUTATION")
        self.assertEqual(RiskFactor.SYSTEM_CRITICAL_TARGET.value, "SYSTEM_CRITICAL_TARGET")

    def test_model_immutability(self):
        """Verify RiskIntelligenceResult and CompoundExposureReport are frozen and forbid extra fields."""
        report = CompoundExposureReport(
            total_steps=1,
            mutation_steps=0,
            non_reversible_steps=0,
            admin_required_steps=0,
            max_impact=RiskImpact.READ_ONLY,
            aggregate_exposure_score=0.0,
            summary="Test summary",
        )
        with self.assertRaises(Exception):
            report.total_steps = 2  # Mutating frozen model must raise

        result = RiskIntelligenceResult(
            task_id="t-001",
            action=AgentAction.FIND_PROCESS,
            action_category=ActionCategory.READ_ONLY_OBSERVATION,
            impact=RiskImpact.READ_ONLY,
            reversibility=ReversibilityClass.IDEMPOTENT,
            scope=ActionScope.SINGLE_PROCESS,
            privilege=PrivilegeScope.STANDARD_USER,
            factors=[],
            explanation="Observation only",
        )
        with self.assertRaises(Exception):
            result.impact = RiskImpact.CRITICAL  # Mutating frozen model must raise


class TestRiskIntelligenceClassification(unittest.TestCase):
    """Test suite for single task classifications across impact, reversibility, scope, and privilege."""

    def setUp(self):
        self.engine = EVRiskIntelligenceEngine()

    def test_read_only_observation_classification(self):
        """Read-only actions produce READ_ONLY impact, IDEMPOTENT reversibility, STANDARD_USER privilege."""
        task = AgentTask(
            task_id="t-read-1",
            action=AgentAction.READ_TEXT_FILE,
            parameters={"path": "C:\\sandbox\\data.txt"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.READ_ONLY_OBSERVATION)
        self.assertEqual(result.impact, RiskImpact.READ_ONLY)
        self.assertEqual(result.reversibility, ReversibilityClass.IDEMPOTENT)
        self.assertEqual(result.scope, ActionScope.SINGLE_FILE)
        self.assertEqual(result.privilege, PrivilegeScope.STANDARD_USER)
        self.assertEqual(result.factors, [])

    def test_directory_observation_scope(self):
        """LIST_DIRECTORY and FIND_FILES produce DIRECTORY scope."""
        task_ls = AgentTask(task_id="t-ls", action=AgentAction.LIST_DIRECTORY, parameters={"path": "C:\\sandbox"})
        task_find = AgentTask(task_id="t-find", action=AgentAction.FIND_FILES, parameters={"root": "C:\\sandbox", "pattern": "*.py"})
        self.assertEqual(self.engine.analyze_task(task_ls).scope, ActionScope.DIRECTORY)
        self.assertEqual(self.engine.analyze_task(task_find).scope, ActionScope.DIRECTORY)

    def test_file_modification_classification(self):
        """WRITE_FILE on sandbox path produces MEDIUM impact, FULLY_REVERSIBLE, SINGLE_FILE scope."""
        task = AgentTask(
            task_id="t-write-1",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "C:\\sandbox\\output.txt", "content": "hello"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.FILE_MODIFY)
        self.assertEqual(result.impact, RiskImpact.MEDIUM)
        self.assertEqual(result.reversibility, ReversibilityClass.FULLY_REVERSIBLE)
        self.assertEqual(result.scope, ActionScope.SINGLE_FILE)
        self.assertEqual(result.privilege, PrivilegeScope.STANDARD_USER)
        self.assertIn(RiskFactor.MUTATION, result.factors)

    def test_file_deletion_classification(self):
        """DELETE_FILE produces HIGH impact, FULLY_REVERSIBLE, SINGLE_FILE scope."""
        task = AgentTask(
            task_id="t-del-1",
            action=AgentAction.DELETE_FILE,
            parameters={"path": "C:\\sandbox\\temp.log"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.FILE_DELETE)
        self.assertEqual(result.impact, RiskImpact.HIGH)
        self.assertEqual(result.reversibility, ReversibilityClass.FULLY_REVERSIBLE)
        self.assertIn(RiskFactor.MUTATION, result.factors)
        self.assertIn(RiskFactor.WIDE_BLAST_RADIUS, result.factors)

    def test_system_file_mutation_privilege(self):
        """Writing to C:\\Windows system directory flags ADMIN_REQUIRED privilege and ELEVATED_PRIVILEGE factor."""
        task = AgentTask(
            task_id="t-sys-write",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "C:\\Windows\\System32\\drivers\\etc\\hosts", "content": "127.0.0.1 rogue.local"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.privilege, PrivilegeScope.ADMIN_REQUIRED)
        self.assertIn(RiskFactor.ELEVATED_PRIVILEGE, result.factors)

    def test_high_impact_categories_classification(self):
        """Direct action categories (COMMAND_EXECUTION, SYSTEM_POWER, REGISTRY_MODIFICATION) classify accurately."""
        res_cmd = self.engine.analyze_task({"action_category": ActionCategory.COMMAND_EXECUTION, "parameters": {"command": "dir"}})
        self.assertEqual(res_cmd.impact, RiskImpact.HIGH)
        self.assertEqual(res_cmd.privilege, PrivilegeScope.ADMIN_REQUIRED)
        self.assertEqual(res_cmd.scope, ActionScope.SYSTEM_WIDE)

        res_pwr = self.engine.analyze_task({"action_category": ActionCategory.SYSTEM_POWER, "parameters": {"action": "restart"}})
        self.assertEqual(res_pwr.impact, RiskImpact.HIGH)
        self.assertEqual(res_pwr.scope, ActionScope.SYSTEM_WIDE)

        res_reg = self.engine.analyze_task({"action_category": ActionCategory.REGISTRY_MODIFICATION, "parameters": {"key": "HKLM\\Software"}})
        self.assertEqual(res_reg.impact, RiskImpact.HIGH)
        self.assertEqual(res_reg.privilege, PrivilegeScope.ADMIN_REQUIRED)

    def test_critical_categories_classification(self):
        """SECURITY_CONFIGURATION and CREDENTIAL_ACCESS produce CRITICAL impact, SYSTEM_PROTECTED privilege."""
        res_sec = self.engine.analyze_task({"action_category": ActionCategory.SECURITY_CONFIGURATION})
        self.assertEqual(res_sec.impact, RiskImpact.CRITICAL)
        self.assertEqual(res_sec.privilege, PrivilegeScope.SYSTEM_PROTECTED)
        self.assertIn(RiskFactor.SYSTEM_CRITICAL_TARGET, res_sec.factors)

        res_cred = self.engine.analyze_task({"action_category": ActionCategory.CREDENTIAL_ACCESS})
        self.assertEqual(res_cred.impact, RiskImpact.CRITICAL)
        self.assertEqual(res_cred.privilege, PrivilegeScope.SYSTEM_PROTECTED)
        self.assertIn(RiskFactor.SYSTEM_CRITICAL_TARGET, res_cred.factors)


class TestTask008ActionsAnalysis(unittest.TestCase):
    """Test suite verifying accurate analysis of Task 008 actions (STOP_PROCESS, RESTART_SERVICE, FLUSH_DNS)."""

    def setUp(self):
        self.engine = EVRiskIntelligenceEngine()

    def test_stop_user_process(self):
        """Stopping an eligible user process is MEDIUM impact, NON_REVERSIBLE, STANDARD_USER privilege."""
        task = AgentTask(
            task_id="t-stop-user",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 4567, "name": "rogue_server.exe"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.PROCESS_STOP)
        self.assertEqual(result.impact, RiskImpact.MEDIUM)
        self.assertEqual(result.reversibility, ReversibilityClass.NON_REVERSIBLE)
        self.assertEqual(result.scope, ActionScope.SINGLE_PROCESS)
        self.assertEqual(result.privilege, PrivilegeScope.STANDARD_USER)
        self.assertIn(RiskFactor.MUTATION, result.factors)
        self.assertIn(RiskFactor.NON_REVERSIBLE_CHANGE, result.factors)

    def test_stop_system_critical_process(self):
        """Stopping a system-critical process flags CRITICAL impact, SYSTEM_PROTECTED, SYSTEM_CRITICAL_TARGET."""
        for crit_proc in ["explorer.exe", "lsass.exe", "services.exe", "csrss"]:
            task = AgentTask(
                task_id=f"t-stop-{crit_proc}",
                action=AgentAction.STOP_PROCESS,
                parameters={"pid": 1000, "name": crit_proc},
            )
            result = self.engine.analyze_task(task)
            self.assertEqual(result.impact, RiskImpact.CRITICAL)
            self.assertEqual(result.privilege, PrivilegeScope.SYSTEM_PROTECTED)
            self.assertIn(RiskFactor.SYSTEM_CRITICAL_TARGET, result.factors)
            self.assertIn(RiskFactor.ELEVATED_PRIVILEGE, result.factors)

    def test_restart_normal_service(self):
        """Restarting a normal service is HIGH impact, COMPENSATING_REVERSIBLE, ADMIN_REQUIRED privilege."""
        task = AgentTask(
            task_id="t-svc-restart",
            action=AgentAction.RESTART_SERVICE,
            parameters={"name": "Spooler"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.SERVICE_CONFIGURATION)
        self.assertEqual(result.impact, RiskImpact.HIGH)
        self.assertEqual(result.reversibility, ReversibilityClass.COMPENSATING_REVERSIBLE)
        self.assertEqual(result.scope, ActionScope.SERVICE)
        self.assertEqual(result.privilege, PrivilegeScope.ADMIN_REQUIRED)
        self.assertIn(RiskFactor.MUTATION, result.factors)
        self.assertIn(RiskFactor.ELEVATED_PRIVILEGE, result.factors)

    def test_restart_critical_service(self):
        """Restarting a system-critical service flags CRITICAL impact, SYSTEM_PROTECTED, SYSTEM_CRITICAL_TARGET."""
        task = AgentTask(
            task_id="t-svc-crit",
            action=AgentAction.RESTART_SERVICE,
            parameters={"name": "trustedinstaller"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.impact, RiskImpact.CRITICAL)
        self.assertEqual(result.privilege, PrivilegeScope.SYSTEM_PROTECTED)
        self.assertIn(RiskFactor.SYSTEM_CRITICAL_TARGET, result.factors)

    def test_flush_dns_cache(self):
        """FLUSH_DNS is HIGH impact, IDEMPOTENT reversibility, STANDARD_USER privilege."""
        task = AgentTask(
            task_id="t-dns-flush",
            action=AgentAction.FLUSH_DNS,
            parameters={"hostname": "example.com"},
        )
        result = self.engine.analyze_task(task)
        self.assertEqual(result.action_category, ActionCategory.NETWORK_CONFIGURATION)
        self.assertEqual(result.impact, RiskImpact.HIGH)
        self.assertEqual(result.reversibility, ReversibilityClass.IDEMPOTENT)
        self.assertEqual(result.scope, ActionScope.NETWORK_INTERFACE)
        self.assertEqual(result.privilege, PrivilegeScope.STANDARD_USER)
        self.assertIn(RiskFactor.MUTATION, result.factors)


class TestRiskFactorsAndEdgeCases(unittest.TestCase):
    """Test suite verifying risk factor combination, unbacked mutations, and malformed inputs."""

    def setUp(self):
        self.engine = EVRiskIntelligenceEngine()

    def test_unbacked_mutation_factor(self):
        """Explicitly unbacked or non-reversible file mutation flags UNBACKED_MUTATION and NON_REVERSIBLE_CHANGE."""
        task = AgentTask(
            task_id="t-unbacked",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "C:\\sandbox\\data.bin"},
        )
        result = self.engine.analyze_task(task, has_backup=False, is_reversible=False)
        self.assertEqual(result.reversibility, ReversibilityClass.NON_REVERSIBLE)
        self.assertIn(RiskFactor.UNBACKED_MUTATION, result.factors)
        self.assertIn(RiskFactor.NON_REVERSIBLE_CHANGE, result.factors)

    def test_malformed_input_fails_closed(self):
        """Non-task objects or invalid structures fail closed to CRITICAL impact with safe advisory fallback."""
        result = self.engine.analyze_task(None)
        self.assertEqual(result.action_category, ActionCategory.UNKNOWN)
        self.assertEqual(result.impact, RiskImpact.CRITICAL)
        self.assertEqual(result.reversibility, ReversibilityClass.UNKNOWN)
        self.assertEqual(result.scope, ActionScope.UNKNOWN)
        self.assertEqual(result.privilege, PrivilegeScope.UNKNOWN)
        self.assertIn("Malformed or invalid", result.explanation)

    def test_dictionary_input_support(self):
        """Valid dictionary payloads are parsed and evaluated properly."""
        raw_dict = {
            "task_id": "dict-1",
            "action": AgentAction.FIND_TCP_PORT,
            "parameters": {"port": 8080},
        }
        result = self.engine.analyze_task(raw_dict)
        self.assertEqual(result.task_id, "dict-1")
        self.assertEqual(result.action, AgentAction.FIND_TCP_PORT)
        self.assertEqual(result.impact, RiskImpact.READ_ONLY)


class TestCompoundExposureAnalysis(unittest.TestCase):
    """Test suite for compound exposure aggregation and transparent deterministic formula."""

    def setUp(self):
        self.engine = EVRiskIntelligenceEngine()

    def test_empty_tasks_exposure(self):
        """Empty sequence produces 0 score and clean summary."""
        report = self.engine.calculate_compound_exposure([])
        self.assertEqual(report.total_steps, 0)
        self.assertEqual(report.aggregate_exposure_score, 0.0)
        self.assertEqual(report.max_impact, RiskImpact.READ_ONLY)

    def test_pure_observation_compound_exposure(self):
        """Sequence of observation steps maintains zero mutation count and low base score."""
        tasks = [
            AgentTask(task_id="t1", action=AgentAction.FIND_PROCESS, parameters={"name": "calc.exe"}),
            AgentTask(task_id="t2", action=AgentAction.FIND_TCP_PORT, parameters={"port": 80}),
            AgentTask(task_id="t3", action=AgentAction.GET_FILE_INFO, parameters={"path": "C:\\test.txt"}),
        ]
        report = self.engine.calculate_compound_exposure(tasks)
        self.assertEqual(report.total_steps, 3)
        self.assertEqual(report.mutation_steps, 0)
        self.assertEqual(report.aggregate_exposure_score, 0.0)
        self.assertEqual(report.max_impact, RiskImpact.READ_ONLY)

    def test_mixed_compound_exposure(self):
        """Mixed sequence correctly accumulates mutation, non-reversible, and chain multipliers."""
        tasks = [
            AgentTask(task_id="t1", action=AgentAction.FIND_PROCESS, parameters={"name": "test.exe"}),
            AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\a.txt"}),
            AgentTask(task_id="t3", action=AgentAction.STOP_PROCESS, parameters={"pid": 1234, "name": "test.exe"}),
            AgentTask(task_id="t4", action=AgentAction.RESTART_SERVICE, parameters={"name": "Spooler"}),
        ]
        report = self.engine.calculate_compound_exposure(tasks)
        self.assertEqual(report.total_steps, 4)
        self.assertEqual(report.mutation_steps, 3)
        self.assertEqual(report.non_reversible_steps, 1)
        self.assertEqual(report.admin_required_steps, 1)
        self.assertEqual(report.max_impact, RiskImpact.HIGH)
        self.assertEqual(report.aggregate_exposure_score, 100.0)

    def test_analyze_tasks_and_transaction(self):
        """analyze_tasks and analyze_transaction correctly attach compound exposure reports."""
        task1 = AgentTask(task_id="t1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\1.txt"})
        task2 = AgentTask(task_id="t2", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\2.txt"})
        results = self.engine.analyze_tasks([task1, task2])
        self.assertEqual(len(results), 2)
        self.assertIsNotNone(results[0].compound_exposure)
        self.assertEqual(results[0].compound_exposure.total_steps, 2)
        self.assertEqual(results[0].compound_exposure.mutation_steps, 2)

        # Transaction interface
        tx = CompoundTransaction(tasks=[task1, task2])
        tx_results, tx_report = analyze_transaction(tx)
        self.assertEqual(len(tx_results), 2)
        self.assertEqual(tx_report.mutation_steps, 2)


class TestDeterminismAndExplanations(unittest.TestCase):
    """Test suite verifying 100% deterministic output stability and explanation generation."""

    def test_100_runs_determinism(self):
        """100 evaluations of identical tasks produce 100 identical results."""
        engine = EVRiskIntelligenceEngine()
        task = AgentTask(
            task_id="det-1",
            action=AgentAction.RESTART_SERVICE,
            parameters={"name": "Spooler"},
        )
        first_result = engine.analyze_task(task)
        first_dict = first_result.model_dump()

        for _ in range(100):
            current = engine.analyze_task(task)
            self.assertEqual(current.model_dump(), first_dict)
            self.assertEqual(current.factors, first_result.factors)
            self.assertEqual(current.explanation, first_result.explanation)

    def test_deterministic_explanation_structure(self):
        """Generated explanations contain structured facts without timestamps or random words."""
        engine = EVRiskIntelligenceEngine()
        task = AgentTask(
            task_id="exp-1",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 9999, "name": "rogue.exe"},
        )
        res = engine.analyze_task(task)
        self.assertIn("Action: STOP_PROCESS targeting 'rogue.exe'", res.explanation)
        self.assertIn("Impact: MEDIUM", res.explanation)
        self.assertIn("Scope: SINGLE_PROCESS", res.explanation)
        self.assertIn("Privilege: STANDARD_USER", res.explanation)
        self.assertIn("Reversibility: NON_REVERSIBLE", res.explanation)
        self.assertIn("Identified Risk Factors: MUTATION, NON_REVERSIBLE_CHANGE", res.explanation)


class TestSecurityInvariantsAndAuthorityIsolation(unittest.TestCase):
    """Security tests verifying strict advisory boundary and zero execution authority."""

    def test_no_authorization_fields_or_methods(self):
        """RiskIntelligenceResult and EVRiskIntelligenceEngine expose no authorization APIs."""
        engine = EVRiskIntelligenceEngine()
        task = AgentTask(task_id="sec-1", action=AgentAction.FIND_PROCESS, parameters={"name": "notepad.exe"})
        result = engine.analyze_task(task)

        # Prohibited field checks
        self.assertFalse(hasattr(result, "allowed"))
        self.assertFalse(hasattr(result, "decision"))
        self.assertFalse(hasattr(result, "approval_required"))
        self.assertFalse(hasattr(result, "authorized"))
        self.assertFalse(hasattr(result, "execute"))

        # Prohibited engine method checks
        self.assertFalse(hasattr(engine, "approve"))
        self.assertFalse(hasattr(engine, "authorize"))
        self.assertFalse(hasattr(engine, "execute"))

    @patch("subprocess.run")
    @patch("subprocess.Popen")
    @patch("os.system")
    @patch("socket.socket")
    def test_zero_side_effects(self, mock_socket, mock_os_system, mock_popen, mock_sub_run):
        """Engine execution makes zero system, subprocess, socket, or OS calls."""
        engine = EVRiskIntelligenceEngine()
        task = AgentTask(
            task_id="pure-1",
            action=AgentAction.RESTART_SERVICE,
            parameters={"name": "trustedinstaller"},
        )
        _ = engine.analyze_task(task)
        mock_socket.assert_not_called()
        mock_os_system.assert_not_called()
        mock_popen.assert_not_called()
        mock_sub_run.assert_not_called()

    def test_ev_risk_engine_authority_preservation(self):
        """
        Proof of Architectural Invariant:
        Advisory classification from RiskIntelligence cannot alter or weaken EVRiskEngine decisions.
        """
        intel_engine = EVRiskIntelligenceEngine()
        authoritative_risk_engine = EVRiskEngine()

        # Case 1: Unapproved file modification
        # Intelligence classifies as MEDIUM impact
        intel_res = intel_engine.analyze_task(
            AgentTask(task_id="pol-1", action=AgentAction.WRITE_FILE, parameters={"path": "C:\\sandbox\\file.txt"}),
        )
        self.assertEqual(intel_res.impact, RiskImpact.MEDIUM)

        # EVRiskEngine MUST remain authoritative: returns REQUIRE_APPROVAL
        risk_req = RiskAssessmentRequest(
            action_category=ActionCategory.FILE_MODIFY,
            target="C:\\sandbox\\file.txt",
            user_approved=False,
            has_backup=True,
            reversible=True,
        )
        auth_res = authoritative_risk_engine.assess(risk_req)
        self.assertEqual(auth_res.decision, PermissionDecision.REQUIRE_APPROVAL)
        self.assertFalse(auth_res.allowed)
        self.assertTrue(auth_res.requires_approval)

        # Case 2: Security configuration mutation
        # Intelligence classifies as CRITICAL impact
        sec_intel = intel_engine.analyze_task(
            {"action_category": ActionCategory.SECURITY_CONFIGURATION},
        )
        self.assertEqual(sec_intel.impact, RiskImpact.CRITICAL)

        # EVRiskEngine MUST return DENY even if user_approved=True
        sec_req = RiskAssessmentRequest(
            action_category=ActionCategory.SECURITY_CONFIGURATION,
            user_approved=True,
        )
        sec_auth = authoritative_risk_engine.assess(sec_req)
        self.assertEqual(sec_auth.decision, PermissionDecision.DENY)
        self.assertFalse(sec_auth.allowed)


if __name__ == "__main__":
    unittest.main()
