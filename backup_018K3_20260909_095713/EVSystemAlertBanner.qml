import QtQuick 2.15
import "../theme"

// EVSystemAlertBanner.qml
//
// Proactive Awareness & System Alert Presentation Surface (Task 018-D).
// Binds to GuiBridge awareness and system alert properties.
// Informational only — zero execution authority, zero commands, zero mutations.
Item {
    id: root
    objectName: "systemAlertBanner"

    readonly property bool isBridgeValid: typeof guiBridge !== "undefined" && guiBridge !== null

    readonly property string awarenessTitle: isBridgeValid ? guiBridge.latestAwarenessTitle : ""
    readonly property string awarenessMessage: isBridgeValid ? guiBridge.latestAwarenessMessage : ""
    readonly property string alertMessage: isBridgeValid ? guiBridge.systemAlertMessage : ""
    readonly property string severity: (isBridgeValid && typeof guiBridge.latestAwarenessSeverity !== "undefined" && guiBridge.latestAwarenessSeverity !== "")
                                      ? guiBridge.latestAwarenessSeverity
                                      : "INFO"

    readonly property bool hasContent: awarenessTitle.length > 0 || awarenessMessage.length > 0 || alertMessage.length > 0

    readonly property string displayTitle: awarenessTitle.length > 0 ? awarenessTitle : (alertMessage.length > 0 ? "SYSTEM ALERT" : "")
    readonly property string displayMessage: awarenessMessage.length > 0 ? awarenessMessage : alertMessage

    // Theme color mapping based on awareness severity
    readonly property color toneColor: {
        if (severity === "CRITICAL") return Theme.luminousCritical;
        if (severity === "WARNING") return Theme.luminousWarning;
        if (severity === "NOTICE") return Theme.luminousPrimary;
        return Theme.textSecondary;
    }

    implicitWidth: parent ? parent.width : 400
    implicitHeight: hasContent ? Math.max(28, contentRow.implicitHeight + Theme.spacingXXS * 2) : 0

    clip: true

    Behavior on implicitHeight {
        NumberAnimation {
            duration: Theme.motionDeliberate
            easing.type: Easing.InOutCubic
        }
    }

    // Banner background container (borderless, subtle transparent HUD aesthetic)
    Rectangle {
        anchors.fill: parent
        visible: root.hasContent
        color: Qt.rgba(root.toneColor.r, root.toneColor.g, root.toneColor.b, 0.05)
        radius: Theme.radiusXS
        border.width: 0
        border.color: "transparent"
        opacity: root.hasContent ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.motionStandard
            }
        }
    }

    // Banner content layout
    Row {
        id: contentRow
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingXS
        anchors.rightMargin: Theme.spacingXS
        anchors.topMargin: Theme.spacingXXS
        anchors.bottomMargin: Theme.spacingXXS
        spacing: Theme.spacingXS
        visible: root.hasContent
        opacity: root.hasContent ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.motionStandard
            }
        }

        // Severity indicator dot (pulses on CRITICAL/WARNING)
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 5
            height: 5
            radius: 2.5
            color: root.toneColor

            SequentialAnimation on opacity {
                running: root.hasContent && (root.severity === "CRITICAL" || root.severity === "WARNING")
                loops: Animation.Infinite
                NumberAnimation {
                    from: 1.0; to: 0.35
                    duration: Theme.motionCinematic
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    from: 0.35; to: 1.0
                    duration: Theme.motionCinematic
                    easing.type: Easing.InOutSine
                }
            }
        }

        // Textual content: Title + Severity Tag and Message
        Column {
            width: parent.width
                   - 5 // dot width
                   - dismissBtn.width
                   - (parent.spacing * 2)
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2

            Row {
                spacing: Theme.spacingXXS
                visible: root.displayTitle.length > 0

                Text {
                    text: root.displayTitle
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                    elide: Text.ElideRight
                }

                Text {
                    text: root.severity
                    color: root.toneColor
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightRegular
                    opacity: 0.85
                }
            }

            Text {
                width: parent.width
                text: root.displayMessage
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightRegular
                wrapMode: Text.Wrap
                elide: Text.ElideRight
                maximumLineCount: 2
            }
        }

        // Dismissal control: presentation-only dismiss
        Rectangle {
            id: dismissBtn
            anchors.verticalCenter: parent.verticalCenter
            width: 18
            height: 18
            radius: Theme.radiusXS
            color: dismissMouseArea.containsMouse ? Theme.surfaceRaised : "transparent"

            Text {
                anchors.centerIn: parent
                text: "×"
                color: dismissMouseArea.containsMouse ? Theme.textPrimary : Theme.textTertiary
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeBodySmall
                font.weight: Theme.fontWeightLight
            }

            MouseArea {
                id: dismissMouseArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    if (root.isBridgeValid && typeof guiBridge.clearAwareness === "function") {
                        guiBridge.clearAwareness();
                    }
                }
            }
        }
    }
}
