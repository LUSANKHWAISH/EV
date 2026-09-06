import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVApprovalOverlay.qml
//
// Modal approval surface for E.V. flagship GUI.
// Presentation only: Intercepts attention, displays action risk and parameters,
// and submits authorization decisions strictly through GuiBridge.
Item {
    id: root

    // Local resolution state machine
    property bool isResolving: false
    property string resolutionError: ""

    // Presentation properties bound to GuiBridge
    property bool approvalPending: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalPending : false
    property string taskId: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalTaskId : ""
    property string planId: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalPlanId : ""
    property string actionName: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalAction : ""
    property string descriptionText: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalDescription : ""
    property string resourcePath: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalResource : ""
    property string riskLevel: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalRiskLevel : ""
    property string reasonText: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalReason : ""
    property bool reversible: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalReversible : true
    property bool rollbackAvailable: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.approvalRollbackAvailable : true
    property string currentState: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.currentState : ""

    // Overlay is visible when approval is pending OR while resolving OR when resolution failed
    property bool overlayVisible: (typeof guiBridge !== "undefined" && guiBridge !== null)
             && (guiBridge.approvalPending || ((isResolving || resolutionError.length > 0) && guiBridge.currentState === "AWAITING_APPROVAL"))
    visible: overlayVisible

    // Focus handling when visible to absorb keys
    focus: visible

    Keys.onEscapePressed: {
        if (!isResolving && approvalPending) {
            handleDecision(false);
        }
    }

    Connections {
        target: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge : null
        ignoreUnknownSignals: true

        function onApprovalPendingChanged(pending) {
            root.approvalPending = pending;
            if (pending) {
                root.isResolving = false;
                root.resolutionError = "";
            } else if (!root.isResolving) {
                root.resolutionError = "";
            }
        }

        function onApprovalTaskIdChanged(id) {
            root.taskId = id;
            root.planId = id;
        }

        function onApprovalActionChanged(action) {
            root.actionName = action;
        }

        function onApprovalDescriptionChanged(desc) {
            root.descriptionText = desc;
        }

        function onApprovalResourceChanged(res) {
            root.resourcePath = res;
        }

        function onApprovalRiskLevelChanged(risk) {
            root.riskLevel = risk;
        }

        function onApprovalReasonChanged(reason) {
            root.reasonText = reason;
        }

        function onApprovalReversibleChanged(rev) {
            root.reversible = rev;
        }

        function onApprovalRollbackAvailableChanged(avail) {
            root.rollbackAvailable = avail;
        }

        function onStateChanged(state) {
            root.currentState = state;
            // When backend transitions out of AWAITING_APPROVAL, resolution is complete
            if (state !== "AWAITING_APPROVAL") {
                root.isResolving = false;
                root.resolutionError = "";
            }
        }

        function onApprovalFailed(failedTaskId, errorMsg) {
            if (root.isResolving || failedTaskId === root.taskId || root.taskId === "" || failedTaskId === "") {
                root.isResolving = false;
                root.resolutionError = errorMsg ? errorMsg : "Authorization resolution failed in backend.";
            }
        }
    }

    function handleDecision(approved) {
        if (isResolving) {
            return; // Guard against duplicate submissions
        }
        var targetId = root.taskId || root.planId;
        if (!targetId && !root.approvalPending) {
            return;
        }

        isResolving = true;
        resolutionError = "";

        if (typeof guiBridge !== "undefined" && guiBridge !== null) {
            guiBridge.submitApproval(targetId, approved);
        }
    }

    // Semi-transparent backdrop blocking input to underlying layers
    Rectangle {
        id: backdrop
        anchors.fill: parent
        color: Theme.backgroundVoid
        opacity: root.visible ? 0.88 : 0.0

        Behavior on opacity {
            NumberAnimation { duration: 180; easing.type: Easing.OutQuad }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            preventStealing: true
            onClicked: {
                // Do not dismiss automatically on backdrop click to prevent accidental actions
            }
        }
    }

    // Modal Card
    Rectangle {
        id: dialogCard
        width: Math.min(parent.width - Theme.spacingXL * 2, 580)
        height: Math.min(parent.height - Theme.spacingXL * 2, cardLayout.implicitHeight + Theme.spacingL * 2)
        anchors.centerIn: parent

        color: Theme.surfaceBase
        radius: Theme.radiusM
        border.width: Theme.borderThin
        border.color: {
            if (root.riskLevel === "CRITICAL" || root.riskLevel === "HIGH") {
                return Theme.luminousCritical;
            }
            if (root.riskLevel === "MEDIUM") {
                return Theme.luminousWarning;
            }
            return Theme.stateColorAwaitingApproval;
        }

        // Top accent glow line
        Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: 3
            radius: Theme.radiusM
            color: dialogCard.border.color
        }

        Column {
            id: cardLayout
            anchors.fill: parent
            anchors.margins: Theme.spacingL
            spacing: Theme.spacingM

            // Header Row: Category Badge & Risk Level
            Item {
                width: parent.width
                height: 24

                // Attention badge
                Rectangle {
                    anchors.left: parent.left
                    height: 24
                    width: headerLabel.implicitWidth + Theme.spacingS * 2
                    radius: Theme.radiusS
                    color: Qt.rgba(Theme.stateColorAwaitingApproval.r, Theme.stateColorAwaitingApproval.g, Theme.stateColorAwaitingApproval.b, 0.15)
                    border.width: Theme.borderThin
                    border.color: Theme.stateColorAwaitingApproval

                    Text {
                        id: headerLabel
                        anchors.centerIn: parent
                        text: "HUMAN AUTHORIZATION REQUIRED"
                        color: Theme.stateColorAwaitingApproval
                        font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeLabelSmall
                        font.weight: Theme.fontWeightBold
                    }
                }

                // Risk Badge
                Rectangle {
                    anchors.right: parent.right
                    height: 24
                    width: riskLabel.implicitWidth + Theme.spacingS * 2
                    radius: Theme.radiusS
                    color: {
                        var c = dialogCard.border.color;
                        return Qt.rgba(c.r, c.g, c.b, 0.18);
                    }
                    border.width: Theme.borderThin
                    border.color: dialogCard.border.color

                    Text {
                        id: riskLabel
                        anchors.centerIn: parent
                        text: "RISK: " + (root.riskLevel ? root.riskLevel : "UNKNOWN")
                        color: dialogCard.border.color
                        font.family: Theme.fontFamilyMono
                        font.pointSize: Theme.fontSizeLabelSmall
                        font.weight: Theme.fontWeightBold
                    }
                }
            }

            // Action & Goal Title
            Column {
                width: parent.width
                spacing: Theme.spacingXXXS

                Text {
                    id: actionText
                    text: root.actionName ? root.actionName : "MUTATING_OPERATION"
                    color: Theme.textPrimary
                    font.family: Theme.fontFamilyMono
                    font.pointSize: Theme.fontSizeSection
                    font.weight: Theme.fontWeightBold
                    elide: Text.ElideRight
                    width: parent.width
                }

                Text {
                    id: descText
                    text: root.descriptionText ? root.descriptionText : "Execution will modify system resources."
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeBodySmall
                    wrapMode: Text.Wrap
                    width: parent.width
                }
            }

            // Divider
            Rectangle {
                width: parent.width
                height: 1
                color: Theme.edgeSubtle
            }

            // Structured Details Grid
            Column {
                width: parent.width
                spacing: Theme.spacingS

                // Resource Field
                Row {
                    width: parent.width
                    spacing: Theme.spacingS

                    Text {
                        width: 90
                        text: "RESOURCE"
                        color: Theme.textTertiary
                        font.family: Theme.fontFamilyMono
                        font.pointSize: Theme.fontSizeLabelSmall
                        font.weight: Theme.fontWeightMedium
                    }

                    Text {
                        id: resourceText
                        width: parent.width - 100
                        text: root.resourcePath ? root.resourcePath : "(system environment)"
                        color: Theme.textPrimary
                        font.family: Theme.fontFamilyMono
                        font.pointSize: Theme.fontSizeLabelSmall
                        wrapMode: Text.WrapAnywhere
                    }
                }

                // Reason Field
                Row {
                    width: parent.width
                    spacing: Theme.spacingS

                    Text {
                        width: 90
                        text: "REASON"
                        color: Theme.textTertiary
                        font.family: Theme.fontFamilyMono
                        font.pointSize: Theme.fontSizeLabelSmall
                        font.weight: Theme.fontWeightMedium
                    }

                    Text {
                        id: reasonText
                        width: parent.width - 100
                        text: root.reasonText ? root.reasonText : "Mutating action requires human consent"
                        color: Theme.textSecondary
                        font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeLabelSmall
                        wrapMode: Text.Wrap
                    }
                }

                // Safety attributes: Reversible & Rollback
                Row {
                    width: parent.width
                    spacing: Theme.spacingM

                    Row {
                        spacing: Theme.spacingXS

                        Text {
                            text: "REVERSIBLE:"
                            color: Theme.textTertiary
                            font.family: Theme.fontFamilyMono
                            font.pointSize: Theme.fontSizeLabelSmall
                        }

                        Text {
                            id: reversibleText
                            text: root.reversible ? "YES" : "NO (IRREVERSIBLE)"
                            color: root.reversible ? Theme.luminousPrimary : Theme.luminousCritical
                            font.family: Theme.fontFamilyMono
                            font.pointSize: Theme.fontSizeLabelSmall
                            font.weight: Theme.fontWeightBold
                        }
                    }

                    Row {
                        spacing: Theme.spacingXS

                        Text {
                            text: "ROLLBACK:"
                            color: Theme.textTertiary
                            font.family: Theme.fontFamilyMono
                            font.pointSize: Theme.fontSizeLabelSmall
                        }

                        Text {
                            id: rollbackText
                            text: root.rollbackAvailable ? "AVAILABLE" : "UNAVAILABLE"
                            color: root.rollbackAvailable ? Theme.luminousPrimary : Theme.luminousWarning
                            font.family: Theme.fontFamilyMono
                            font.pointSize: Theme.fontSizeLabelSmall
                            font.weight: Theme.fontWeightBold
                        }
                    }
                }
            }

            // Error Message (if resolution failed)
            Rectangle {
                width: parent.width
                height: errorText.implicitHeight + Theme.spacingS
                color: Qt.rgba(Theme.luminousCritical.r, Theme.luminousCritical.g, Theme.luminousCritical.b, 0.15)
                radius: Theme.radiusS
                border.width: Theme.borderThin
                border.color: Theme.luminousCritical
                visible: root.resolutionError.length > 0

                Text {
                    id: errorText
                    anchors.centerIn: parent
                    width: parent.width - Theme.spacingS * 2
                    text: root.resolutionError
                    color: Theme.luminousCritical
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    wrapMode: Text.Wrap
                }
            }

            // Status message during resolution
            Text {
                id: resolvingStatusText
                width: parent.width
                text: "Submitting authorization to backend..."
                color: Theme.stateColorAwaitingApproval
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                horizontalAlignment: Text.AlignHCenter
                visible: root.isResolving
            }

            // Action Buttons Row
            Row {
                width: parent.width
                spacing: Theme.spacingM
                layoutDirection: Qt.RightToLeft

                // Approve Button
                EVButton {
                    id: approveButton
                    text: root.isResolving ? "AUTHORIZING..." : "APPROVE"
                    enabled: !root.isResolving && (root.approvalPending || root.taskId !== "")
                    highlighted: true
                    horizontalPadding: Theme.spacingL
                    verticalPadding: Theme.spacingM

                    onClicked: {
                        root.handleDecision(true);
                    }
                }

                // Reject Button
                EVButton {
                    id: rejectButton
                    text: "REJECT"
                    enabled: !root.isResolving && (root.approvalPending || root.taskId !== "")
                    horizontalPadding: Theme.spacingL
                    verticalPadding: Theme.spacingM

                    onClicked: {
                        root.handleDecision(false);
                    }
                }
            }
        }
    }
}
