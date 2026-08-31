import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVCommandInput.qml
// Standalone component for user task submission.
// Placed at the window level to cleanly separate input from the visual stage.

Item {
    id: root
    
    // Allow the parent to anchor it
    height: Theme.spacingXXL

    TextField {
        id: commandField
        anchors.fill: parent
        
        placeholderText: "Enter a task..."
        color: Theme.textPrimary
        placeholderTextColor: Theme.textSecondary
        
        background: Rectangle {
            color: Theme.backgroundBase
            radius: Theme.radiusS
            border.color: commandField.activeFocus ? Theme.brandPrimary : Theme.edgeStandard
            border.width: commandField.activeFocus ? 2 : 1
        }
        
        font.family: Theme.fontFamily
        font.pointSize: Theme.fontSizeBody
        
        leftPadding: Theme.spacingM
        rightPadding: Theme.spacingM
        
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
