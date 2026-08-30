import QtQuick 2.15
import "../theme"

// Compact intelligence/task display rail for left side of flagship stage.
Item {
    id: root

    // Dimensions
    implicitWidth: Theme.spacingL   // 24px base, can expand
    implicitHeight: parent.height

    // Properties from bridge (placeholder values)
    property var state: null
    property string activeTask: "INITIALIZING"
    property string currentPhase: "BOOT"
    property string currentAction: "SYNC"
    property string riskLevel: "NOMINAL"
    property bool rollbackAvailable: false

    property string stateText:
        state === null ||
        state === undefined ||
        String(state).length === 0
        ? "IDLE"
        : String(state)

    property color stateTone: Theme.stateColor(stateText)

    Column {
        anchors.fill: parent
        anchors.margins: Theme.spacingS
        spacing: Theme.spacingXS

        // Active Task
        Row {
            spacing: Theme.spacingXXS
            Text {
                text: "ACTIVE TASK"
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                color: Theme.textTertiary
            }
            Text {
                text: root.activeTask
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }

        // Current Phase
        Row {
            spacing: Theme.spacingXXS
            Text {
                text: "CURRENT PHASE"
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                color: Theme.textTertiary
            }
            Text {
                text: root.currentPhase
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }

        // Current Action
        Row {
            spacing: Theme.spacingXXS
            Text {
                text: "CURRENT ACTION"
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                color: Theme.textTertiary
            }
            Text {
                text: root.currentAction
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                color: Theme.textPrimary
                elide: Text.ElideRight
            }
        }

        // Risk
        Row {
            spacing: Theme.spacingXXS
            Text {
                text: "RISK"
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                color: Theme.textTertiary
            }
            Text {
                text: root.riskLevel
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                color: root.riskLevel === "NOMINAL" ? Theme.stateColorIdle :
                       root.riskLevel === "LOW" ? Theme.stateColorSuccess :
                       root.riskLevel === "MEDIUM" ? Theme.stateColorAwaitingApproval :
                       root.riskLevel === "HIGH" ? Theme.stateColorFailed :
                                                     Theme.stateColorCritical
                elide: Text.ElideRight
            }
        }

        // Rollback
        Row {
            spacing: Theme.spacingXXS
            Text {
                text: "ROLLBACK"
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                color: Theme.textTertiary
            }
            Rectangle {
                width: Theme.spacingXS
                height: Theme.spacingXS
                radius: Theme.radiusXS
                color: root.rollbackAvailable ? Theme.luminousPrimary : Theme.backgroundBase
                opacity: root.rollbackAvailable ? Theme.opacityEmphasis : Theme.opacityMuted
            }
        }

        // State indicator at bottom
        Rectangle {
            anchors.horizontalCenter: parent.horizontalCenter
            width: Theme.spacingM
            height: Theme.spacingM
            radius: Theme.spacingM / 2
            color: stateTone
            opacity: Theme.opacitySignal
        }
    }
}