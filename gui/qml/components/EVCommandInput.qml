import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVCommandInput.qml
// Standalone component for user task submission.
// Placed at the window level to cleanly separate input from the visual stage.

Item {
    id: root
    
    // Adaptive presentation properties
    readonly property bool isCompact: (parent && parent.height < Theme.stageCompactHeight)
                                      || (typeof windowRoot !== "undefined" && windowRoot && windowRoot.isCompactHeight)

    // Allow the parent to anchor it; adapts between standard (64px) and compact (48px)
    height: isCompact ? Theme.spacingXL : Theme.spacingXXL

    TextField {
        id: commandField
        anchors.fill: parent
        horizontalAlignment: TextInput.AlignHCenter
        verticalAlignment: TextInput.AlignVCenter
        
        placeholderText: "Enter a task..."
        color: Theme.textPrimary
        placeholderTextColor: Theme.textSecondary
        
        background: Rectangle {
            color: commandField.activeFocus
                   ? Qt.rgba(1.0, 1.0, 1.0, 0.08)
                   : Qt.rgba(1.0, 1.0, 1.0, 0.05)
            radius: Theme.radiusS
            border.width: 0
            border.color: "transparent"

            Behavior on color {
                ColorAnimation {
                    duration: Theme.motionStandard
                }
            }
        }
        
        font.family: Theme.fontFamily
        font.pointSize: root.isCompact ? Theme.fontSizeBodySmall : Theme.fontSizeBody
        
        leftPadding: root.isCompact ? Theme.spacingS : Theme.spacingM
        rightPadding: root.isCompact ? Theme.spacingS : Theme.spacingM
        
        onAccepted: {
            var rawText = text.trim()
            if (rawText.length > 0) {
                if (typeof guiBridge !== "undefined" && guiBridge !== null) {
                    guiBridge.submitTask(rawText)
                }
                text = ""
            }
        }
    }
}
