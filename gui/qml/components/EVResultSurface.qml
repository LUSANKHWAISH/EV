import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVResultSurface.qml
//
// Presentation-only component displaying authoritative task execution results.
// Strictly decoupled from execution authority:
// - Zero execution capability
// - Zero mutation authority
// - Dismiss only clears local presentation state
Item {
    id: root
    objectName: "resultSurface"

    readonly property string resultText:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResult
        : ""

    readonly property string resultStatus:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultStatus
        : "IDLE"

    readonly property bool resultSuccess:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultSuccess
        : false

    readonly property bool resultAvailable:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultAvailable
        : false

    readonly property bool isRunning: resultStatus === "RUNNING"
    readonly property bool isVisible: resultAvailable || isRunning

    visible: opacity > 0.001
    opacity: isVisible ? 1.0 : 0.0

    implicitWidth: parent ? parent.width : 400
    implicitHeight: isVisible ? Math.min(240, cardContainer.implicitHeight) : 0
    height: implicitHeight

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

    // Main Card Background
    Rectangle {
        id: backgroundRect
        anchors.fill: parent
        color: Theme.surfaceLowest
        radius: Theme.radiusS
        border.width: Theme.borderThin
        border.color: {
            if (root.isRunning) {
                return Theme.luminousWarning
            }
            if (!root.resultAvailable) {
                return Theme.edgeStandard
            }
            if (root.resultSuccess) {
                return Theme.luminousPrimary
            }
            if (root.resultStatus === "CANCELLED") {
                return Theme.luminousWarning
            }
            return Theme.luminousCritical
        }

        Behavior on border.color {
            ColorAnimation {
                duration: Theme.motionStandard
            }
        }
    }

    // Content Layout
    Column {
        id: cardContainer
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: Theme.spacingXS
        spacing: Theme.spacingXXS

        // Header Item: Status Indicator & Label on left, Dismiss Control on right
        Item {
            width: parent.width
            height: Theme.spacingM

            Row {
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.spacingXXS

                // Status Indicator Dot
                Rectangle {
                    id: statusDot
                    anchors.verticalCenter: parent.verticalCenter
                    width: 8
                    height: 8
                    radius: 4
                    color: {
                        if (root.isRunning) {
                            return Theme.luminousWarning
                        }
                        if (root.resultSuccess) {
                            return Theme.luminousPrimary
                        }
                        if (root.resultStatus === "CANCELLED") {
                            return Theme.luminousWarning
                        }
                        return Theme.luminousCritical
                    }

                    // Pulse animation while executing in pipeline
                    SequentialAnimation on opacity {
                        running: root.isRunning
                        loops: Animation.Infinite
                        NumberAnimation { from: 1.0; to: 0.3; duration: Theme.motionCinematic; easing.type: Easing.InOutSine }
                        NumberAnimation { from: 0.3; to: 1.0; duration: Theme.motionCinematic; easing.type: Easing.InOutSine }
                    }
                }

                // Status Title Text
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: {
                        if (root.isRunning) {
                            return "PIPELINE EXECUTING..."
                        }
                        if (root.resultSuccess) {
                            return "TASK COMPLETED"
                        }
                        if (root.resultStatus === "CANCELLED") {
                            return "TASK CANCELLED"
                        }
                        return "TASK FAILED"
                    }
                    color: Theme.textSecondary
                    font.family: Theme.fontFamilyMono
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightBold
                }
            }

            // Dismiss Button (Presentation-only: clears displayed result)
            Rectangle {
                id: dismissButton
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: 20
                height: 20
                radius: 10
                color: dismissArea.containsMouse ? Theme.surfaceRaised : "transparent"

                Text {
                    anchors.centerIn: parent
                    text: "✕"
                    color: dismissArea.containsMouse ? Theme.textPrimary : Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightBold
                }

                MouseArea {
                    id: dismissArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (typeof guiBridge !== "undefined" && guiBridge !== null) {
                            guiBridge.clearTaskResult()
                        }
                    }
                }
            }
        }

        // Hairline Divider
        Rectangle {
            width: parent.width
            height: Theme.hairline
            color: Theme.edgeSubtle
        }

        // Body Text / Result Readout
        Flickable {
            id: flickableArea
            width: parent.width
            implicitHeight: Math.min(160, resultMessageText.implicitHeight)
            contentWidth: width
            contentHeight: resultMessageText.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Text {
                id: resultMessageText
                width: parent.width
                text: root.isRunning ? "Command is being executed through canonical pipeline..." : root.resultText
                color: root.isRunning ? Theme.textSecondary : Theme.textPrimary
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeBodySmall
                font.weight: Theme.fontWeightRegular
                wrapMode: Text.Wrap
                lineHeight: 1.3
            }
        }
    }
}
