import QtQuick 2.15
import "../theme"

// EVLifecycleHUD.qml
//
// Lightweight transparent HUD visualization of the canonical execution lifecycle (Phase 018-E).
// Presentation projection of authoritative backend pipeline states:
// THINK › PLAN › VALIDATE › RISK › [APPROVAL ›] EXECUTE › VERIFY › [OUTCOME]
//
// Pure presentation surface:
// - Zero execution authority
// - Zero command dispatch
// - Zero approval mutations
// - Zero polling loops
Item {
    id: root
    objectName: "lifecycleHUD"

    // Safe bridge property bindings
    readonly property bool isBridgeValid: typeof guiBridge !== "undefined" && guiBridge !== null
    readonly property string stage: isBridgeValid ? guiBridge.lifecycleStage : "IDLE"
    readonly property int stageIndex: isBridgeValid ? guiBridge.lifecycleStageIndex : 0
    readonly property bool isActive: isBridgeValid ? guiBridge.lifecycleActive : false
    readonly property bool isRollback: isBridgeValid ? guiBridge.lifecycleRollback : false
    readonly property bool approvalRequired: isBridgeValid
        ? (guiBridge.approvalPending || guiBridge.lifecycleApprovalRequired || stage === "APPROVAL")
        : false
    readonly property bool resultAvailable: isBridgeValid ? guiBridge.taskResultAvailable : false

    readonly property bool isVisible: stage !== "IDLE" && (isActive || resultAvailable)

    implicitWidth: parent ? parent.width : 400
    implicitHeight: isVisible ? 20 : 0
    height: implicitHeight

    visible: opacity > 0.001
    opacity: isVisible ? 1.0 : 0.0

    clip: true

    Behavior on implicitHeight {
        NumberAnimation {
            duration: Theme.motionStandard
            easing.type: Easing.InOutCubic
        }
    }

    Behavior on opacity {
        NumberAnimation {
            duration: Theme.motionStandard
        }
    }

    // Pulse animation for active stage
    property real _pulseOpacity: 1.0
    SequentialAnimation on _pulseOpacity {
        running: root.isActive && root.stageIndex < 8
        loops: Animation.Infinite
        NumberAnimation { from: 1.0; to: 0.60; duration: 600; easing.type: Easing.InOutSine }
        NumberAnimation { from: 0.60; to: 1.0; duration: 600; easing.type: Easing.InOutSine }
    }

    // Helper functions for stage state
    function isStageActive(idx) {
        return root.stageIndex === idx;
    }

    function isStageCompleted(idx) {
        if (root.stageIndex < 8) {
            return root.stageIndex > idx;
        }
        // Terminal stage (stageIndex === 8)
        if (root.stage === "SUCCESS") {
            return true;
        }
        var maxIdx = (isBridgeValid && typeof guiBridge.lifecycleMaxStageIndex !== "undefined")
            ? guiBridge.lifecycleMaxStageIndex
            : 1;
        return idx <= maxIdx;
    }

    function getStageColor(idx, isApproval) {
        if (isStageActive(idx)) {
            return isApproval ? Theme.stateColorAwaitingApproval : Theme.luminousPrimary;
        }
        if (isStageCompleted(idx)) {
            return Qt.rgba(Theme.luminousPrimary.r, Theme.luminousPrimary.g, Theme.luminousPrimary.b, 0.50);
        }
        return Theme.textTertiary;
    }

    function getStageOpacity(idx) {
        if (isStageActive(idx)) {
            return root._pulseOpacity;
        }
        if (isStageCompleted(idx)) {
            return 0.75;
        }
        return 0.22;
    }

    // Responsive presentation properties
    readonly property bool isCompactWidth: width < 720 || (typeof windowRoot !== "undefined" && windowRoot && windowRoot.isCompactWidth)
    readonly property bool isVeryCompactWidth: width < 580 || (typeof windowRoot !== "undefined" && windowRoot && windowRoot.isVeryCompactWidth)
    readonly property int rowSpacing: isVeryCompactWidth ? Theme.spacingXXXS : (isCompactWidth ? Theme.spacingXXS : Theme.spacingXS)

    onStageIndexChanged: _ensureCurrentStageVisible()
    onStageChanged: _ensureCurrentStageVisible()

    function _ensureCurrentStageVisible() {
        if (stageFlickable.contentWidth <= stageFlickable.width) {
            stageFlickable.contentX = 0;
            return;
        }
        var targetItem = null;
        if (stageIndex === 8) {
            targetItem = stageOutcome;
        } else {
            switch (stageIndex) {
            case 1: targetItem = stageThink; break;
            case 2: targetItem = stagePlan; break;
            case 3: targetItem = stageValidate; break;
            case 4: targetItem = stageRisk; break;
            case 5: targetItem = stageApproval; break;
            case 6: targetItem = stageExecute; break;
            case 7: targetItem = stageVerify; break;
            }
        }
        if (targetItem && targetItem.visible) {
            var itemX = targetItem.x;
            var itemRight = itemX + targetItem.width;
            if (itemRight > stageFlickable.contentX + stageFlickable.width) {
                stageFlickable.contentX = Math.max(0, itemRight - stageFlickable.width + 12);
            } else if (itemX < stageFlickable.contentX) {
                stageFlickable.contentX = Math.max(0, itemX - 12);
            }
        }
    }

    Flickable {
        id: stageFlickable
        anchors.fill: parent
        contentWidth: stageRow.width
        contentHeight: height
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Row {
            id: stageRow
            y: Math.max(0, Math.round((parent.height - height) / 2))
            spacing: root.rowSpacing

        // 1. THINK
        Text {
            id: stageThink
            text: "THINK"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(1) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(1, false)
            opacity: root.getStageOpacity(1)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
        }

        // 2. PLAN
        Text {
            id: stagePlan
            text: "PLAN"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(2) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(2, false)
            opacity: root.getStageOpacity(2)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
        }

        // 3. VALIDATE
        Text {
            id: stageValidate
            text: "VALIDATE"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(3) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(3, false)
            opacity: root.getStageOpacity(3)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
        }

        // 4. RISK
        Text {
            id: stageRisk
            text: "RISK"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(4) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(4, false)
            opacity: root.getStageOpacity(4)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        // 5. APPROVAL (conditional, only shown when required)
        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
            visible: root.approvalRequired
        }

        Text {
            id: stageApproval
            text: "APPROVAL"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(5) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(5, true)
            opacity: root.getStageOpacity(5)
            visible: root.approvalRequired
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
        }

        // 6. EXECUTE
        Text {
            id: stageExecute
            text: "EXECUTE"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(6) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(6, false)
            opacity: root.getStageOpacity(6)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
        }

        // 7. VERIFY
        Text {
            id: stageVerify
            text: "VERIFY"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: root.isStageActive(7) ? Theme.fontWeightBold : Theme.fontWeightMedium
            color: root.getStageColor(7, false)
            opacity: root.getStageOpacity(7)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }

        // 8. TERMINAL OUTCOME BADGE
        Text {
            text: "›"
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            opacity: 0.35
            visible: root.stageIndex === 8
        }

        Text {
            id: stageOutcome
            visible: root.stageIndex === 8
            text: {
                if (root.stage === "SUCCESS") return "SUCCESS";
                if (root.stage === "ROLLED_BACK") return "ROLLED BACK";
                if (root.stage === "CANCELLED") return "CANCELLED";
                if (root.stage === "FAILED") return "FAILED";
                return root.stage;
            }
            font.family: Theme.fontFamilyMono
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightBold
            color: {
                if (root.stage === "SUCCESS") return Theme.luminousPrimary;
                if (root.stage === "ROLLED_BACK") return Theme.luminousWarning;
                if (root.stage === "CANCELLED") return Theme.luminousWarning;
                if (root.stage === "FAILED") return Theme.luminousCritical;
                return Theme.textSecondary;
            }
            opacity: 1.0

            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }
    }
}
}
