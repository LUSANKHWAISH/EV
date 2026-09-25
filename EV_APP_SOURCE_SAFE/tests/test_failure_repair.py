"""
Comprehensive unit and integration tests for Phase 5 Task 008:
Structured Failure Diagnostic & Controlled Windows Repair Engine.
"""
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from core.diagnostics import (
    FailureCategory,
    PrivilegeRequirement,
    RollbackCapability,
    DiagnosticResult,
    RepairPlan,
    diagnose_port_collision,
    diagnose_stale_lockfile,
    diagnose_config_corruption,
    diagnose_service_failure,
    diagnose_dns_failure,
    create_repair_task,
    create_repair_plan,
)
from core.models import (
    ActionCategory,
    AgentAction,
    AgentStatus,
    AgentTask,
    DnsFlushResult,
    PermissionDecision,
    PowerShellResult,
    ProcessInfo,
    ProcessStopResult,
    RiskAssessmentRequest,
    RiskLevel,
    ServiceInfo,
    ServiceRestartResult,
    TcpConnectionInfo,
    VerificationStatus,
    VerificationType,
)
from core.agent import EVAgent
from core.backup import EVBackupManager
from core.events import EVEventBus
from core.orchestrator import EVOrchestrator, get_action_category
from core.resolver import CommandResolver
from core.risk import EVRiskEngine
from core.transaction import CompoundTransaction, TransactionStatus
from tools.processes import stop_process, SYSTEM_CRITICAL_PROCESSES
from tools.services import restart_service, SYSTEM_CRITICAL_SERVICES
from tools.network import flush_dns


# =============================================================================
# 1. Failure Diagnostics Tests
# =============================================================================

class TestDiagnosticsEngine:
    """Test deterministic root-cause diagnosis across all 5 failure categories."""

    def test_diagnose_port_collision_detected(self):
        """Occupied port by unexpected process is classified as PORT_COLLISION_FAILURE."""
        mock_connections = [
            TcpConnectionInfo(
                local_address="127.0.0.1",
                local_port=8080,
                state="Listen",
                owning_pid=4567,
                process_name="rogue_server",
            )
        ]
        with patch("core.diagnostics.find_tcp_port", return_value=mock_connections):
            diag = diagnose_port_collision(port=8080, expected_process_name="my_app")
            assert diag.is_failure is True
            assert diag.failure_category == FailureCategory.PORT_COLLISION_FAILURE
            assert diag.status == "PORT_COLLISION_DETECTED"
            assert diag.affected_resource == "8080"
            assert diag.recommended_repair == "STOP_PROCESS"
            assert diag.repair_parameters == {"pid": 4567, "process_name": "rogue_server", "port": 8080}
            assert diag.required_risk_level == RiskLevel.MEDIUM
            assert diag.approval_required is True
            assert diag.privilege_requirement == PrivilegeRequirement.STANDARD_USER
            assert diag.rollback_capability == RollbackCapability.NOT_REVERSIBLE

    def test_diagnose_port_free_not_failure(self):
        """Unoccupied port produces clean non-failure result."""
        with patch("core.diagnostics.find_tcp_port", return_value=[]):
            diag = diagnose_port_collision(port=9090)
            assert diag.is_failure is False
            assert diag.failure_category == FailureCategory.NONE
            assert diag.status == "PORT_FREE"
            assert diag.recommended_repair is None

    def test_diagnose_port_occupied_by_expected_process(self):
        """Port occupied by the expected process is healthy (not a failure)."""
        mock_connections = [
            TcpConnectionInfo(
                local_address="127.0.0.1",
                local_port=3000,
                state="Listen",
                owning_pid=1234,
                process_name="node.exe",
            )
        ]
        with patch("core.diagnostics.find_tcp_port", return_value=mock_connections):
            diag = diagnose_port_collision(port=3000, expected_process_name="node.exe")
            assert diag.is_failure is False
            assert diag.failure_category == FailureCategory.NONE
            assert diag.status == "PORT_OCCUPIED_EXPECTED"

    def test_diagnose_port_collision_system_critical_blocks_repair(self):
        """System critical process on port requires ADMIN_REQUIRED and blocks automated stop."""
        mock_connections = [
            TcpConnectionInfo(
                local_address="0.0.0.0",
                local_port=80,
                state="Listen",
                owning_pid=4,
                process_name="System",
            )
        ]
        with patch("core.diagnostics.find_tcp_port", return_value=mock_connections):
            diag = diagnose_port_collision(port=80)
            assert diag.is_failure is True
            assert diag.failure_category == FailureCategory.PORT_COLLISION_FAILURE
            assert diag.status == "PORT_COLLISION_SYSTEM_CRITICAL"
            assert diag.privilege_requirement == PrivilegeRequirement.ADMIN_REQUIRED
            assert diag.recommended_repair is None

    def test_diagnose_stale_lockfile_detected(self, tmp_path):
        """Lockfile with no running associated process is classified as STALE_LOCKFILE_FAILURE."""
        lockfile = tmp_path / "app.lock"
        lockfile.write_text("pid:99999", encoding="utf-8")

        with patch("core.diagnostics.list_processes", return_value=[]), \
             patch("core.diagnostics.find_processes", return_value=[]):
            diag = diagnose_stale_lockfile(
                lockfile_path=str(lockfile),
                associated_process_name="crashed_app",
                associated_pid=99999,
            )
            assert diag.is_failure is True
            assert diag.failure_category == FailureCategory.STALE_LOCKFILE_FAILURE
            assert diag.status == "STALE_LOCKFILE_DETECTED"
            assert diag.recommended_repair == "DELETE_FILE"
            assert diag.repair_parameters == {"path": str(lockfile)}
            assert diag.required_risk_level == RiskLevel.HIGH
            assert diag.approval_required is True
            assert diag.rollback_capability == RollbackCapability.FULLY_REVERSIBLE

    def test_diagnose_active_lockfile_not_stale(self, tmp_path):
        """Lockfile with live process is healthy."""
        lockfile = tmp_path / "app.lock"
        lockfile.write_text("pid:1234", encoding="utf-8")

        mock_procs = [ProcessInfo(pid=1234, name="live_app")]
        with patch("core.diagnostics.list_processes", return_value=mock_procs):
            diag = diagnose_stale_lockfile(
                lockfile_path=str(lockfile),
                associated_pid=1234,
            )
            assert diag.is_failure is False
            assert diag.failure_category == FailureCategory.NONE
            assert diag.status == "LOCKFILE_ACTIVE"
            assert diag.recommended_repair is None

    def test_diagnose_missing_lockfile_clean(self, tmp_path):
        """Nonexistent lockfile is not a failure."""
        missing_lock = tmp_path / "nonexistent.lock"
        diag = diagnose_stale_lockfile(str(missing_lock))
        assert diag.is_failure is False
        assert diag.failure_category == FailureCategory.NONE
        assert diag.status == "LOCKFILE_NOT_FOUND"

    def test_diagnose_config_corruption_syntax_error(self, tmp_path):
        """Syntax-corrupted JSON config is diagnosed as CONFIG_CORRUPTION_FAILURE."""
        cfg = tmp_path / "config.json"
        cfg.write_text("{ broken json: [", encoding="utf-8")

        diag = diagnose_config_corruption(
            config_path=str(cfg),
            expected_format="json",
            repair_template='{"port": 8080}',
        )
        assert diag.is_failure is True
        assert diag.failure_category == FailureCategory.CONFIG_CORRUPTION_FAILURE
        assert diag.status == "CONFIG_SYNTAX_CORRUPTED"
        assert diag.recommended_repair == "WRITE_FILE"
        assert diag.repair_parameters == {"path": str(cfg), "content": '{"port": 8080}'}
        assert diag.rollback_capability == RollbackCapability.FULLY_REVERSIBLE

    def test_diagnose_config_corruption_missing_schema_keys(self, tmp_path):
        """Config missing critical keys is diagnosed as schema invalid."""
        cfg = tmp_path / "config.json"
        cfg.write_text('{"host": "localhost"}', encoding="utf-8")

        diag = diagnose_config_corruption(
            config_path=str(cfg),
            expected_format="json",
            expected_keys=["host", "port", "database"],
        )
        assert diag.is_failure is True
        assert diag.status == "CONFIG_SCHEMA_INVALID"

    def test_diagnose_config_valid(self, tmp_path):
        """Valid JSON config produces clean result."""
        cfg = tmp_path / "config.json"
        cfg.write_text('{"host": "localhost", "port": 8080}', encoding="utf-8")

        diag = diagnose_config_corruption(
            config_path=str(cfg),
            expected_format="json",
            expected_keys=["host", "port"],
        )
        assert diag.is_failure is False
        assert diag.failure_category == FailureCategory.NONE
        assert diag.status == "CONFIG_VALID"

    def test_diagnose_service_failure_stopped(self):
        """Stopped service is diagnosed as SERVICE_FAILURE with RESTART_SERVICE recommendation."""
        mock_svc = [
            ServiceInfo(
                name="MyCustomService",
                display_name="My Custom Background Service",
                status="Stopped",
                start_type="Automatic",
            )
        ]
        with patch("core.diagnostics.find_services", return_value=mock_svc):
            diag = diagnose_service_failure("MyCustomService")
            assert diag.is_failure is True
            assert diag.failure_category == FailureCategory.SERVICE_FAILURE
            assert diag.status == "SERVICE_STOPPED"
            assert diag.recommended_repair == "RESTART_SERVICE"
            assert diag.repair_parameters == {"name": "MyCustomService"}
            assert diag.required_risk_level == RiskLevel.HIGH
            assert diag.approval_required is True
            assert diag.rollback_capability == RollbackCapability.COMPENSATING_STATE_REVERSIBLE

    def test_diagnose_service_running_healthy(self):
        """Running service is healthy."""
        mock_svc = [
            ServiceInfo(
                name="MyCustomService",
                status="Running",
            )
        ]
        with patch("core.diagnostics.find_services", return_value=mock_svc):
            diag = diagnose_service_failure("MyCustomService")
            assert diag.is_failure is False
            assert diag.failure_category == FailureCategory.NONE
            assert diag.status == "SERVICE_HEALTHY"

    def test_diagnose_service_system_critical_requires_admin(self):
        """Stopped system-critical service is flagged as ADMIN_REQUIRED."""
        mock_svc = [
            ServiceInfo(
                name="TrustedInstaller",
                status="Stopped",
            )
        ]
        with patch("core.diagnostics.find_services", return_value=mock_svc):
            diag = diagnose_service_failure("TrustedInstaller")
            assert diag.is_failure is True
            assert diag.status == "SERVICE_STOPPED_SYSTEM_CRITICAL"
            assert diag.privilege_requirement == PrivilegeRequirement.ADMIN_REQUIRED
            assert diag.recommended_repair is None

    def test_diagnose_dns_failure_detected(self):
        """DNS resolution failure with network adapter up generates DNS_RESOLUTION_FAILURE."""
        mock_dns_res = PowerShellResult(
            command="[System.Net.Dns]::GetHostAddresses...",
            stdout="",
            stderr="No such host is known",
            exit_code=1,
            success=False,
            executed=True,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.1,
        )
        mock_net_res = PowerShellResult(
            command="Get-NetAdapter",
            stdout='[{"Name": "Ethernet", "Status": "Up"}]',
            stderr="",
            exit_code=0,
            success=True,
            executed=True,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.1,
        )
        with patch("core.diagnostics.run_powershell", side_effect=[mock_dns_res, mock_net_res]):
            diag = diagnose_dns_failure("broken-internal.local")
            assert diag.is_failure is True
            assert diag.failure_category == FailureCategory.DNS_RESOLUTION_FAILURE
            assert diag.status == "DNS_RESOLUTION_FAILED"
            assert diag.recommended_repair == "FLUSH_DNS"
            assert diag.repair_parameters == {"hostname": "broken-internal.local"}
            assert diag.required_risk_level == RiskLevel.HIGH
            assert diag.rollback_capability == RollbackCapability.NOT_APPLICABLE_IDEMPOTENT

    def test_diagnose_dns_healthy(self):
        """Resolving hostname is diagnosed as healthy."""
        mock_dns_res = PowerShellResult(
            command="...",
            stdout="192.168.1.50\n",
            stderr="",
            exit_code=0,
            success=True,
            executed=True,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.1,
        )
        with patch("core.diagnostics.run_powershell", return_value=mock_dns_res):
            diag = diagnose_dns_failure("gateway.local")
            assert diag.is_failure is False
            assert diag.status == "DNS_HEALTHY"

    def test_diagnose_network_unavailable_not_classified_as_dns_failure(self):
        """Disconnected network adapter is classified as NETWORK_UNAVAILABLE, not DNS failure."""
        mock_dns_res = PowerShellResult(
            command="...", stdout="", stderr="Error", exit_code=1, success=False,
            executed=True, timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.1,
        )
        mock_net_res = PowerShellResult(
            command="Get-NetAdapter", stdout="[]", stderr="", exit_code=0, success=True,
            executed=True, timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.1,
        )
        with patch("core.diagnostics.run_powershell", side_effect=[mock_dns_res, mock_net_res]):
            diag = diagnose_dns_failure("api.example.com")
            assert diag.is_failure is True
            assert diag.status == "NETWORK_UNAVAILABLE"
            assert diag.failure_category == FailureCategory.NONE

    def test_create_repair_task_and_plan(self):
        """RepairPlan is constructed cleanly from DiagnosticResult."""
        diag = DiagnosticResult(
            failure_category=FailureCategory.PORT_COLLISION_FAILURE,
            status="PORT_COLLISION_DETECTED",
            is_failure=True,
            affected_resource="5000",
            recommended_repair="STOP_PROCESS",
            repair_parameters={"pid": 7890, "process_name": "flask_app"},
            required_risk_level=RiskLevel.MEDIUM,
            approval_required=True,
            privilege_requirement=PrivilegeRequirement.STANDARD_USER,
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
            rollback_capability=RollbackCapability.NOT_REVERSIBLE,
        )
        plan = create_repair_plan(diag)
        assert plan.is_executable is True
        assert len(plan.tasks) == 1
        assert plan.tasks[0].action == AgentAction.STOP_PROCESS
        assert plan.tasks[0].parameters == {"pid": 7890, "process_name": "flask_app"}
        assert plan.tasks[0].verification_type == VerificationType.PROCESS_NOT_EXISTS
        assert plan.requires_approval is True
        assert "non-reversible" in plan.reversibility_summary.lower()


# =============================================================================
# 2. STOP_PROCESS Tool & Agent Tests
# =============================================================================

class TestStopProcess:
    """Test process termination safety, execution, and verification."""

    def test_stop_process_valid_target(self):
        """Eligible user process is terminated successfully."""
        mock_procs = [ProcessInfo(pid=5555, name="worker_node")]
        mock_ps_res = PowerShellResult(
            command="Stop-Process -Id 5555 -Force",
            stdout="",
            stderr="",
            exit_code=0,
            success=True,
            executed=True,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.1,
        )
        with patch("tools.processes.list_processes", return_value=mock_procs), \
             patch("tools.processes.run_powershell", return_value=mock_ps_res):
            res = stop_process(pid=5555, process_name="worker_node")
            assert res.success is True
            assert res.terminated is True
            assert res.pid == 5555

    def test_stop_process_invalid_pid_rejected(self):
        """Invalid PID <= 4 is rejected."""
        res = stop_process(pid=0)
        assert res.success is False
        assert "system-protected" in res.error.lower()

        res_neg = stop_process(pid=-10)
        assert res_neg.success is False

    def test_stop_process_system_critical_rejected(self):
        """Protected system processes cannot be terminated."""
        mock_procs = [ProcessInfo(pid=1000, name="svchost.exe")]
        with patch("tools.processes.list_processes", return_value=mock_procs):
            res = stop_process(pid=1000, process_name="svchost.exe")
            assert res.success is False
            assert "protected system-critical process" in res.error

    def test_stop_process_identity_mismatch_rejected(self):
        """Process name mismatch prevents accidental termination."""
        mock_procs = [ProcessInfo(pid=4444, name="notepad.exe")]
        with patch("tools.processes.list_processes", return_value=mock_procs):
            res = stop_process(pid=4444, process_name="malware.exe")
            assert res.success is False
            assert "identity mismatch" in res.error.lower()

    def test_stop_process_admin_required_handling(self):
        """Permission denied produces ADMIN_REQUIRED diagnostic."""
        mock_procs = [ProcessInfo(pid=6666, name="protected_service_worker")]
        mock_ps_res = PowerShellResult(
            command="Stop-Process...",
            stdout="",
            stderr="Stop-Process : Cannot stop process. Access is denied.",
            exit_code=1,
            success=False,
            executed=True,
            timed_out=False,
            started_at=datetime.now(),
            finished_at=datetime.now(),
            duration_seconds=0.1,
        )
        with patch("tools.processes.list_processes", return_value=mock_procs), \
             patch("tools.processes.run_powershell", return_value=mock_ps_res):
            res = stop_process(pid=6666, process_name="protected_service_worker")
            assert res.success is False
            assert "ADMIN_REQUIRED" in res.error

    def test_agent_run_stop_process_with_verification(self):
        """EVAgent executes STOP_PROCESS and verifies PROCESS_NOT_EXISTS."""
        agent = EVAgent()
        task = AgentTask(
            task_id="t-stop-1",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 7777, "process_name": "temp_worker"},
            verification_type=VerificationType.PROCESS_NOT_EXISTS,
        )

        mock_stop_res = ProcessStopResult(pid=7777, name="temp_worker", success=True, terminated=True)
        # On verification check, find_processes returns empty list (process is gone!)
        with patch("core.agent.stop_process", return_value=mock_stop_res), \
             patch("core.agent.find_processes", return_value=[]):
            run_res = agent.run(task)
            assert run_res.status == AgentStatus.COMPLETED
            assert run_res.step.success is True
            # Check non-compensable metadata recorded
            mutation = agent.get_task_mutation("t-stop-1")
            assert mutation is not None
            assert mutation["is_compensable"] is False


# =============================================================================
# 3. RESTART_SERVICE Tool & Agent Tests
# =============================================================================

class TestRestartService:
    """Test service restart safety, execution, prior state recording, and verification."""

    def test_restart_service_success(self):
        """Service restart successfully transitions service to Running state."""
        svc_before = [ServiceInfo(name="PrintSpooler", status="Stopped")]
        svc_after = [ServiceInfo(name="PrintSpooler", status="Running")]
        mock_ps_res = PowerShellResult(
            command="Restart-Service -Name 'PrintSpooler' -Force",
            stdout="", stderr="", exit_code=0, success=True, executed=True,
            timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.5,
        )

        with patch("tools.services.find_services", side_effect=[svc_before, svc_after]), \
             patch("tools.services.run_powershell", return_value=mock_ps_res):
            res = restart_service("PrintSpooler")
            assert res.success is True
            assert res.prior_status == "Stopped"
            assert res.current_status == "Running"
            assert res.admin_required is False

    def test_restart_service_system_critical_requires_admin(self):
        """System critical service restart is blocked and requires admin."""
        svc_mock = [ServiceInfo(name="TrustedInstaller", status="Stopped")]
        with patch("tools.services.find_services", return_value=svc_mock):
            res = restart_service("TrustedInstaller")
            assert res.success is False
            assert res.admin_required is True
            assert "ADMIN_REQUIRED" in res.error

    def test_restart_service_access_denied_produces_admin_required(self):
        """Access denied from Windows SCM produces clear ADMIN_REQUIRED status."""
        svc_mock = [ServiceInfo(name="ProtectedService", status="Stopped")]
        mock_ps_res = PowerShellResult(
            command="Restart-Service...",
            stdout="", stderr="Cannot open Service Control Manager: Access is denied.",
            exit_code=1, success=False, executed=True, timed_out=False,
            started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.2,
        )
        with patch("tools.services.find_services", return_value=svc_mock), \
             patch("tools.services.run_powershell", return_value=mock_ps_res):
            res = restart_service("ProtectedService")
            assert res.success is False
            assert res.admin_required is True
            assert "ADMIN_REQUIRED" in res.error

    def test_agent_run_restart_service(self):
        """EVAgent executes RESTART_SERVICE cleanly."""
        agent = EVAgent()
        task = AgentTask(
            task_id="t-svc-1",
            action=AgentAction.RESTART_SERVICE,
            parameters={"name": "MyWorkerService"},
            verification_type=VerificationType.RESULT_NOT_EMPTY,
        )
        mock_res = ServiceRestartResult(
            name="MyWorkerService",
            prior_status="Stopped",
            current_status="Running",
            success=True,
        )
        with patch("core.agent.restart_service", return_value=mock_res):
            run_res = agent.run(task)
            assert run_res.status == AgentStatus.COMPLETED
            assert run_res.step.success is True


# =============================================================================
# 4. FLUSH_DNS Tool & Agent Tests
# =============================================================================

class TestFlushDns:
    """Test DNS cache flush bounded execution and verification."""

    def test_flush_dns_bounded_execution_with_hostname_verification(self):
        """FLUSH_DNS executes Clear-DnsClientCache and verifies target hostname."""
        ps_flush = PowerShellResult(
            command="Clear-DnsClientCache", stdout="", stderr="", exit_code=0, success=True,
            executed=True, timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.1,
        )
        ps_resolve = PowerShellResult(
            command="[System.Net.Dns]::GetHostAddresses...", stdout="93.184.216.34\n", stderr="", exit_code=0, success=True,
            executed=True, timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.1,
        )
        with patch("tools.network.run_powershell", side_effect=[ps_flush, ps_resolve]):
            res = flush_dns(hostname="example.com")
            assert res.success is True
            assert res.flushed is True
            assert res.resolved is True
            assert res.verification_status == "RESOLVED"

    def test_flush_dns_without_hostname_reports_verification_limitation(self):
        """FLUSH_DNS without hostname reports verification limitation without claiming false test."""
        ps_flush = PowerShellResult(
            command="Clear-DnsClientCache", stdout="", stderr="", exit_code=0, success=True,
            executed=True, timed_out=False, started_at=datetime.now(), finished_at=datetime.now(), duration_seconds=0.1,
        )
        with patch("tools.network.run_powershell", return_value=ps_flush):
            res = flush_dns()
            assert res.success is True
            assert res.flushed is True
            assert "VERIFICATION_UNAVAILABLE" in res.verification_status

    def test_agent_run_flush_dns(self):
        """EVAgent dispatches FLUSH_DNS."""
        agent = EVAgent()
        task = AgentTask(
            task_id="t-dns-1",
            action=AgentAction.FLUSH_DNS,
            parameters={"hostname": "internal.corp"},
            verification_type=VerificationType.RESULT_NOT_EMPTY,
        )
        mock_res = DnsFlushResult(
            success=True,
            flushed=True,
            target_hostname="internal.corp",
            resolved=True,
            verification_status="RESOLVED",
        )
        with patch("core.agent.flush_dns", return_value=mock_res):
            run_res = agent.run(task)
            assert run_res.status == AgentStatus.COMPLETED


# =============================================================================
# 5. Risk, Approval & Orchestrator Integration Tests
# =============================================================================

class TestRiskAndOrchestrationIntegration:
    """Test risk category mapping, approval gating, and resolver intents for repair actions."""

    def test_action_category_mappings(self):
        """Verify new repair actions map cleanly into existing ActionCategory enums."""
        assert get_action_category(AgentAction.STOP_PROCESS) == ActionCategory.PROCESS_STOP
        assert get_action_category(AgentAction.RESTART_SERVICE) == ActionCategory.SERVICE_CONFIGURATION
        assert get_action_category(AgentAction.FLUSH_DNS) == ActionCategory.NETWORK_CONFIGURATION

    def test_risk_engine_requires_approval_for_repairs(self):
        """EVRiskEngine requires approval for unapproved repair actions."""
        risk_engine = EVRiskEngine()

        # STOP_PROCESS
        req_stop = RiskAssessmentRequest(
            action_category=ActionCategory.PROCESS_STOP,
            target="1234",
            user_approved=False,
        )
        res_stop = risk_engine.assess(req_stop)
        assert res_stop.decision == PermissionDecision.REQUIRE_APPROVAL
        assert res_stop.risk_level == RiskLevel.MEDIUM

        # RESTART_SERVICE
        req_svc = RiskAssessmentRequest(
            action_category=ActionCategory.SERVICE_CONFIGURATION,
            target="MyService",
            user_approved=False,
        )
        res_svc = risk_engine.assess(req_svc)
        assert res_svc.decision == PermissionDecision.REQUIRE_APPROVAL
        assert res_svc.risk_level == RiskLevel.HIGH

        # FLUSH_DNS
        req_dns = RiskAssessmentRequest(
            action_category=ActionCategory.NETWORK_CONFIGURATION,
            target="example.com",
            user_approved=False,
        )
        res_dns = risk_engine.assess(req_dns)
        assert res_dns.decision == PermissionDecision.REQUIRE_APPROVAL
        assert res_dns.risk_level == RiskLevel.HIGH

    def test_resolver_repair_command_intents(self):
        """CommandResolver maps deterministic repair commands."""
        resolver = CommandResolver()

        # stop process
        t1 = resolver.resolve("stop process 4567")
        assert t1.action == AgentAction.STOP_PROCESS
        assert t1.parameters == {"pid": 4567}
        assert t1.verification_type == VerificationType.PROCESS_NOT_EXISTS

        # restart service
        t2 = resolver.resolve("restart service 'Spooler'")
        assert t2.action == AgentAction.RESTART_SERVICE
        assert t2.parameters == {"name": "Spooler"}

        # flush dns
        t3 = resolver.resolve("flush dns internal.local")
        assert t3.action == AgentAction.FLUSH_DNS
        assert t3.parameters == {"hostname": "internal.local"}


# =============================================================================
# 6. Filesystem Repair & Transaction Rollback Integration Tests
# =============================================================================

class TestFilesystemRepairAndRollback:
    """Test stale lockfile deletion, config repair, and rollback under CompoundTransaction."""

    def test_stale_lockfile_deletion_and_rollback(self, tmp_path):
        """Stale lockfile deletion in a transaction is restored if a subsequent step fails."""
        from core.models import RiskAssessmentResult

        lockfile = tmp_path / "app.lock"
        original_content = "pid:8888"
        lockfile.write_text(original_content, encoding="utf-8")

        event_bus = EVEventBus()
        orchestrator = EVOrchestrator(event_bus=event_bus)
        orchestrator.agent._allowed_roots = [tmp_path]

        mock_risk = MagicMock(spec=EVRiskEngine)
        mock_risk.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_DELETE,
            risk_level=RiskLevel.LOW,
            decision=PermissionDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            reason="Test pre-authorized",
            policy_rule="test_allow_rule",
        )
        orchestrator.risk_engine = mock_risk

        task1 = AgentTask(
            task_id="t-del-lock",
            action=AgentAction.DELETE_FILE,
            parameters={"path": str(lockfile)},
        )
        task2 = AgentTask(
            task_id="t-fail-step",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "", "content": "fails_parameter_validation"},
        )

        # Execute batch with transaction
        tx = CompoundTransaction(tasks=[task1, task2])
        thread = orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        # Transaction rolled back
        assert tx.status == TransactionStatus.ROLLED_BACK
        # Stale lockfile was restored to original content via pre-execution backup!
        assert lockfile.exists()
        assert lockfile.read_text(encoding="utf-8") == original_content

    def test_config_repair_backup_and_rollback(self, tmp_path):
        """Corrupted config overwritten during repair is restored on subsequent step failure."""
        from core.models import RiskAssessmentResult

        config_file = tmp_path / "settings.json"
        corrupted_content = "{ broken: json "
        config_file.write_text(corrupted_content, encoding="utf-8")

        event_bus = EVEventBus()
        orchestrator = EVOrchestrator(event_bus=event_bus)
        orchestrator.agent._allowed_roots = [tmp_path]

        mock_risk = MagicMock(spec=EVRiskEngine)
        mock_risk.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.LOW,
            decision=PermissionDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            reason="Test pre-authorized",
            policy_rule="test_allow_rule",
        )
        orchestrator.risk_engine = mock_risk

        task1 = AgentTask(
            task_id="t-fix-cfg",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(config_file), "content": '{"port": 8080}', "overwrite": True},
        )
        task2 = AgentTask(
            task_id="t-fail-step2",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "", "content": "fails_validation"},
        )

        tx = CompoundTransaction(tasks=[task1, task2])
        thread = orchestrator.execute_tasks([task1, task2], transaction=tx)
        thread.join(timeout=5.0)

        assert tx.status == TransactionStatus.ROLLED_BACK
        assert config_file.exists()
        assert config_file.read_text(encoding="utf-8") == corrupted_content

    def test_compound_transaction_with_non_compensable_stop_process(self, tmp_path):
        """Compound transaction with STOP_PROCESS (non-compensable) + file mutation handles failure safely."""
        from core.models import RiskAssessmentResult

        target_file = tmp_path / "app_state.txt"
        target_file.write_text("initial_state", encoding="utf-8")

        event_bus = EVEventBus()
        orchestrator = EVOrchestrator(event_bus=event_bus)
        orchestrator.agent._allowed_roots = [tmp_path]

        mock_risk = MagicMock(spec=EVRiskEngine)
        mock_risk.assess.return_value = RiskAssessmentResult(
            action_category=ActionCategory.FILE_MODIFY,
            risk_level=RiskLevel.LOW,
            decision=PermissionDecision.ALLOW,
            allowed=True,
            requires_approval=False,
            reason="Test pre-authorized",
            policy_rule="test_allow_rule",
        )
        orchestrator.risk_engine = mock_risk

        mock_stop_res = ProcessStopResult(pid=8888, name="rogue_app", success=True, terminated=True)

        task1 = AgentTask(
            task_id="t-stop-proc",
            action=AgentAction.STOP_PROCESS,
            parameters={"pid": 8888, "process_name": "rogue_app"},
        )
        task2 = AgentTask(
            task_id="t-write-state",
            action=AgentAction.WRITE_FILE,
            parameters={"path": str(target_file), "content": "mutated_state", "overwrite": True},
        )
        task3 = AgentTask(
            task_id="t-fail-step3",
            action=AgentAction.WRITE_FILE,
            parameters={"path": "", "content": "fail"},
        )

        with patch("core.agent.stop_process", return_value=mock_stop_res):
            tx = CompoundTransaction(tasks=[task1, task2, task3])
            thread = orchestrator.execute_tasks([task1, task2, task3], transaction=tx)
            thread.join(timeout=5.0)

            # Transaction rolled back compensable steps (file mutation restored!)
            assert tx.status == TransactionStatus.ROLLED_BACK
            assert target_file.read_text(encoding="utf-8") == "initial_state"



# =============================================================================
# 7. Protected Files Byte-for-Byte Verification
# =============================================================================

class TestProtectedFilesIntegrity:
    """Ensure all 8 protected files remain completely untouched."""

    @pytest.mark.parametrize(
        "filepath",
        [
            "core/risk.py",
            "core/backup.py",
            "core/verifier.py",
            "core/events.py",
            "core/brain_models.py",
            "core/brain_validator.py",
            "core/brain_converter.py",
            "core/brain_router.py",
        ],
    )
    def test_protected_files_untouched(self, filepath):
        """Protected files must have zero uncommitted diffs against HEAD."""
        import subprocess
        res = subprocess.run(
            ["git", "diff", "HEAD", "--", filepath],
            capture_output=True,
            text=True,
            cwd=str(Path("D:/EV")),
        )
        assert res.returncode == 0
        assert res.stdout.strip() == "", f"Protected file {filepath} was modified!"
