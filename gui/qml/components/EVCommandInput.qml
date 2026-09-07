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
            color: Qt.rgba(1, 1, 1, 0.03)
            radius: Theme.radiusS
            border.color: commandField.activeFocus
                          ? Qt.rgba(Theme.brandPrimary.r,
                                    Theme.brandPrimary.g,
                                    Theme.brandPrimary.b,
                                    0.35)
                          : Qt.rgba(1, 1, 1, 0.06)
            border.width: commandField.activeFocus ? 1 : 0.5
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
