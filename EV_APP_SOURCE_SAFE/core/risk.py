"""
Risk / Permission Engine for E.V.
"""
from datetime import datetime
from typing import Optional

from .models import (
    ActionCategory,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskLevel,
    PermissionDecision,
)


class EVRiskEngine:
    """
    Deterministic risk and permission engine for proposed actions.
    """

    def assess(self, request: RiskAssessmentRequest) -> RiskAssessmentResult:
        """
        Assess the risk and permission for a proposed action.

        Args:
            request: Structured request containing action category and context.

        Returns:
            RiskAssessmentResult with the computed risk level, decision, etc.
        """
        try:
            # Handle malformed or unsupported action categories early
            if not isinstance(request.action_category, ActionCategory):
                return RiskAssessmentResult(
                    action_category=ActionCategory.UNKNOWN,  # type: ignore
                    risk_level=RiskLevel.CRITICAL,
                    decision=PermissionDecision.DENY,
                    allowed=False,
                    requires_approval=False,
                    reason="Invalid or unsupported action category",
                    policy_rule="unsupported_category",
                    evaluated_at=datetime.now(),
                )

            # Calculate base risk and decision first (before overrides)
            risk_level, decision, reason, policy_rule = self._calculate_base_assessment(request)

            # Preserve READ_ONLY_OBSERVATION: it must remain NONE/ALLOW regardless of overrides
            if request.action_category == ActionCategory.READ_ONLY_OBSERVATION:
                # Already set correctly by base assessment; just return to skip overrides
                pass
            else:
                # Apply centralized overrides for security/elevation/system flags
                # These overrides happen after base calculation but before final decision
                # Define mutation categories (all except READ_ONLY_OBSERVATION)
                MUTATION_CATEGORIES = {
                    ActionCategory.FILE_CREATE,
                    ActionCategory.FILE_MODIFY,
                    ActionCategory.FILE_DELETE,
                    ActionCategory.FILE_RESTORE,
                    ActionCategory.PROCESS_START,
                    ActionCategory.PROCESS_STOP,
                    ActionCategory.COMMAND_EXECUTION,
                    ActionCategory.NETWORK_CONFIGURATION,
                    ActionCategory.SERVICE_CONFIGURATION,
                    ActionCategory.REGISTRY_MODIFICATION,
                    ActionCategory.SOFTWARE_INSTALL,
                    ActionCategory.SOFTWARE_UNINSTALL,
                    ActionCategory.SYSTEM_POWER,
                    ActionCategory.SECURITY_CONFIGURATION,
                    ActionCategory.CREDENTIAL_ACCESS,
                }

                # First, handle hard denies for security-impacting mutations
                if request.affects_security and request.action_category in MUTATION_CATEGORIES:
                    # Any security-impacting mutation is denied regardless of other factors
                    risk_level = RiskLevel.CRITICAL
                    decision = PermissionDecision.DENY
                    reason = f"{request.action_category.value} affecting security is denied by minimal policy"
                    policy_rule = f"{policy_rule}_security_impact_denied"
                else:
                    # Apply security/elevation overrides for non-security-impacting cases
                    if request.affects_security or request.requires_elevation:
                        # Security configuration and credential access are always denied (hard denies)
                        if request.action_category in (ActionCategory.SECURITY_CONFIGURATION, ActionCategory.CREDENTIAL_ACCESS):
                            risk_level = RiskLevel.CRITICAL
                            decision = PermissionDecision.DENY
                            reason = f"{request.action_category.value} is always denied due to security impact"
                            policy_rule = "hard_deny_security"
                        # For other actions with security/elevation impact, apply risk elevation
                        elif risk_level != RiskLevel.CRITICAL:  # Don't downgrade from CRITICAL
                            # Elevate risk level for security/elevation impact
                            if request.affects_security or request.requires_elevation:
                                if risk_level == RiskLevel.NONE:
                                    risk_level = RiskLevel.LOW
                                elif risk_level == RiskLevel.LOW:
                                    risk_level = RiskLevel.MEDIUM
                                elif risk_level == RiskLevel.MEDIUM:
                                    risk_level = RiskLevel.HIGH
                                elif risk_level == RiskLevel.HIGH:
                                    risk_level = RiskLevel.CRITICAL

                                # Update reason to reflect security/elevation concern
                                if request.affects_security:
                                    reason = f"{reason} (affects security)"
                                if request.requires_elevation:
                                    reason = f"{reason} (requires elevation)"

                                policy_rule = f"{policy_rule}_with_security_elevation"

                # Apply system impact override (separate from security)
                # Skip if already denied by security impact
                if not (request.affects_security and request.action_category in MUTATION_CATEGORIES):
                    if request.affects_system and request.action_category not in (ActionCategory.SECURITY_CONFIGURATION, ActionCategory.CREDENTIAL_ACCESS):
                        if risk_level != RiskLevel.CRITICAL:  # Don't downgrade from CRITICAL
                            # Elevate risk level for system impact
                            if risk_level == RiskLevel.NONE:
                                risk_level = RiskLevel.LOW
                            elif risk_level == RiskLevel.LOW:
                                risk_level = RiskLevel.MEDIUM
                            elif risk_level == RiskLevel.MEDIUM:
                                risk_level = RiskLevel.HIGH
                            elif risk_level == RiskLevel.HIGH:
                                risk_level = RiskLevel.CRITICAL

                            reason = f"{reason} (affects system)"
                            policy_rule = f"{policy_rule}_with_system_impact"

            # Build result
            allowed = decision == PermissionDecision.ALLOW
            requires_approval = decision == PermissionDecision.REQUIRE_APPROVAL

            return RiskAssessmentResult(
                action_category=request.action_category,
                risk_level=risk_level,
                decision=decision,
                allowed=allowed,
                requires_approval=requires_approval,
                reason=reason,
                policy_rule=policy_rule,
                evaluated_at=datetime.now(),
            )
        except Exception as exc:
            # Fail closed: any internal error results in INDETERMINATE
            return RiskAssessmentResult(
                action_category=request.action_category if isinstance(request.action_category, ActionCategory) else ActionCategory.UNKNOWN,
                risk_level=RiskLevel.CRITICAL,
                decision=PermissionDecision.INDETERMINATE,
                allowed=False,
                requires_approval=False,
                reason=f"Internal risk engine error: {exc}",
                policy_rule="internal_error",
                evaluated_at=datetime.now(),
                error=str(exc),
            )

    def _calculate_base_assessment(self, request: RiskAssessmentRequest) -> tuple[RiskLevel, PermissionDecision, str, str]:
        """
        Calculate the base risk assessment without security/elevation/system overrides.

        Returns:
            Tuple of (risk_level, decision, reason, policy_rule)
        """
        # Read-only observation: always allowed, no risk
        if request.action_category == ActionCategory.READ_ONLY_OBSERVATION:
            return RiskLevel.NONE, PermissionDecision.ALLOW, "Read-only observation poses no risk", "read_only_allowed"

        # File creation
        elif request.action_category == ActionCategory.FILE_CREATE:
            if request.user_approved:
                return RiskLevel.LOW, PermissionDecision.ALLOW, "File creation with explicit user approval", "file_create_approved"
            else:
                return RiskLevel.LOW, PermissionDecision.REQUIRE_APPROVAL, "File creation requires user approval", "file_create_requires_approval"

        # File modification
        elif request.action_category == ActionCategory.FILE_MODIFY:
            if request.user_approved:
                # With approval, we still consider backup and reversibility for risk level
                if request.has_backup and request.reversible:
                    # Safe modification with approval -> MEDIUM risk (per spec: approval changes unsafe to ALLOW, but safe stays MEDIUM?)
                    # Wait, spec says: "safe (has_backup+reversible) => MEDIUM risk (approval changes to ALLOW, unsafe => HIGH/DENY even with approval)"
                    # This seems contradictory. Let me re-read:
                    # "Update FILE_MODIFY policy: safe (has_backup+reversible) => MEDIUM risk (approval changes to ALLOW, unsafe => HIGH/DENY even with approval)"
                    # I think this means:
                    # - Safe (has_backup+reversible): BASE risk is MEDIUM
                    # - With approval: decision becomes ALLOW (but risk level stays MEDIUM?)
                    # - Unsafe: even with approval => HIGH risk and DENY decision

                    # Actually, re-reading more carefully:
                    # "safe (has_backup+reversible) => MEDIUM risk (approval changes to ALLOW, unsafe => HIGH/DENY even with approval)"
                    # This means:
                    # - For safe modifications: base risk is MEDIUM
                    # - Approval changes the decision from REQUIRE_APPROVAL to ALLOW
                    # - For unsafe modifications: even with approval => HIGH risk and DENY decision

                    return RiskLevel.MEDIUM, PermissionDecision.ALLOW, "File modification with explicit user approval (safe)", "file_modify_approved_safe"
                else:
                    # Unsafe modification: even with approval => HIGH risk and DENY decision
                    return RiskLevel.HIGH, PermissionDecision.DENY, "File modification is unsafe (no backup or not reversible) and cannot be approved", "file_modify_unsafe_denied"
            else:
                # Without approval
                if request.has_backup and request.reversible:
                    return RiskLevel.MEDIUM, PermissionDecision.REQUIRE_APPROVAL, "File modification has backup and reversible but requires user approval", "file_modify_requires_approval"
                else:
                    return RiskLevel.MEDIUM, PermissionDecision.REQUIRE_APPROVAL, "File modification lacks safety nets and requires user approval", "file_modify_requires_approval"

        # File deletion
        elif request.action_category == ActionCategory.FILE_DELETE:
            if request.user_approved:
                # Explicit user approval may produce ALLOW only for a narrowly-scoped file deletion that is represented as reversible / safely backed up
                if request.reversible and request.has_backup:
                    return RiskLevel.LOW, PermissionDecision.ALLOW, "File deletion with user approval, reversible, and backed up", "file_delete_approved_safe"
                else:
                    # Otherwise: DENY or REQUIRE_APPROVAL
                    # Since we have user_approved but it doesn't meet narrow scope, we DENY
                    return RiskLevel.HIGH, PermissionDecision.DENY, "File deletion lacks safety nets (reversible and backed up) despite user approval", "file_delete_unsafely_approved_denied"
            else:
                # No user approval
                return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "File deletion requires user approval", "file_delete_requires_approval"

        # File restore
        elif request.action_category == ActionCategory.FILE_RESTORE:
            if request.user_approved:
                # Approval requires BOTH has_backup=True AND reversible=True for ALLOW, else DENY
                if request.has_backup and request.reversible:
                    return RiskLevel.MEDIUM, PermissionDecision.ALLOW, "File restore with explicit user approval (reversible and backed up)", "file_restore_approved_safe"
                else:
                    return RiskLevel.HIGH, PermissionDecision.DENY, "File restore requires both reversible and a backup to be approved", "file_restore_requires_safe_denied"
            else:
                return RiskLevel.MEDIUM, PermissionDecision.REQUIRE_APPROVAL, "File restore requires user approval", "file_restore_requires_approval"

        # Process start
        elif request.action_category == ActionCategory.PROCESS_START:
            if request.user_approved:
                return RiskLevel.LOW, PermissionDecision.ALLOW, "Process start with explicit user approval", "process_start_approved"
            else:
                return RiskLevel.LOW, PermissionDecision.REQUIRE_APPROVAL, "Process start requires user approval", "process_start_requires_approval"

        # Process stop
        elif request.action_category == ActionCategory.PROCESS_STOP:
            if request.user_approved:
                # Still consider elevation and system impact for risk level (but these will be handled by overrides)
                return RiskLevel.MEDIUM, PermissionDecision.ALLOW, "Process stop with explicit user approval", "process_stop_approved"
            else:
                return RiskLevel.MEDIUM, PermissionDecision.REQUIRE_APPROVAL, "Process stop requires user approval", "process_stop_requires_approval"

        # Command execution
        elif request.action_category == ActionCategory.COMMAND_EXECUTION:
            # Base risk is HIGH (changed from MEDIUM)
            if request.requires_elevation or request.affects_system or request.affects_security:
                # These will be handled by overrides, but we start with HIGH
                return RiskLevel.HIGH, PermissionDecision.DENY, "Command execution with elevation/system/security impact is denied", "command_exec_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Command execution with user approval (no elevation/system/security)", "command_exec_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Command execution requires user approval", "command_exec_requires_approval"

        # Network configuration
        elif request.action_category == ActionCategory.NETWORK_CONFIGURATION:
            if request.affects_security or request.requires_elevation:
                return RiskLevel.HIGH, PermissionDecision.DENY, "Network configuration affecting security or requiring elevation is denied", "network_config_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Network configuration with user approval", "network_config_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Network configuration requires user approval", "network_config_requires_approval"

        # Service configuration
        elif request.action_category == ActionCategory.SERVICE_CONFIGURATION:
            if request.affects_security or request.requires_elevation:
                return RiskLevel.HIGH, PermissionDecision.DENY, "Service configuration affecting security or requiring elevation is denied", "service_config_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Service configuration with user approval", "service_config_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Service configuration requires user approval", "service_config_requires_approval"

        # Registry modification
        elif request.action_category == ActionCategory.REGISTRY_MODIFICATION:
            if request.affects_security or request.requires_elevation:
                return RiskLevel.HIGH, PermissionDecision.DENY, "Registry modification affecting security or requiring elevation is denied", "registry_config_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Registry modification with user approval", "registry_config_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Registry modification requires user approval", "registry_config_requires_approval"

        # Software install
        elif request.action_category == ActionCategory.SOFTWARE_INSTALL:
            if request.affects_security or request.requires_elevation:
                return RiskLevel.HIGH, PermissionDecision.DENY, "Software installation affecting security or requiring elevation is denied", "software_install_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Software installation with user approval", "software_install_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Software installation requires user approval", "software_install_requires_approval"

        # Software uninstall
        elif request.action_category == ActionCategory.SOFTWARE_UNINSTALL:
            if request.affects_security or request.requires_elevation:
                return RiskLevel.HIGH, PermissionDecision.DENY, "Software uninstallation affecting security or requiring elevation is denied", "software_uninstall_critical_denied"
            else:
                if request.user_approved:
                    return RiskLevel.HIGH, PermissionDecision.ALLOW, "Software uninstallation with user approval", "software_uninstall_approved"
                else:
                    return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "Software uninstallation requires user approval", "software_uninstall_requires_approval"

        # System power
        elif request.action_category == ActionCategory.SYSTEM_POWER:
            if request.user_approved:
                return RiskLevel.HIGH, PermissionDecision.ALLOW, "System power operation with user approval", "system_power_approved"
            else:
                return RiskLevel.HIGH, PermissionDecision.REQUIRE_APPROVAL, "System power operation requires user approval", "system_power_requires_approval"

        # Security configuration
        elif request.action_category == ActionCategory.SECURITY_CONFIGURATION:
            # Minimal engine: always deny, regardless of approval
            return RiskLevel.CRITICAL, PermissionDecision.DENY, "Security configuration is denied by minimal policy", "security_config_denied"

        # Credential access
        elif request.action_category == ActionCategory.CREDENTIAL_ACCESS:
            # Minimal engine: always deny
            return RiskLevel.CRITICAL, PermissionDecision.DENY, "Credential access is denied by minimal policy", "credential_access_denied"

        # Unknown category (should have been caught earlier, but just in case)
        else:
            return RiskLevel.CRITICAL, PermissionDecision.DENY, "Unknown action category", "unknown_category"