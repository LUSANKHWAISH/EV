import QtQuick 2.15
import "../theme"

// EVSystemAlertBanner.qml
//
// Non-intrusive system alert display.
// Binds to guiBridge.systemAlertMessage.
// Informational only — no action buttons, no mutation authority.
Item {
    id: root

    property string alertMessage:
        typeof guiBridge !== "undefined" && guiBridge !== null
        ? guiBridge.systemAlertMessage
        : ""

    property bool hasAlert: alertMessage.length > 0

    implicitWidth: parent ? parent.width : 200
    implicitHeight: hasAlert ? alertContent.implicitHeight + Theme.spacingXXS * 2 : 0

    clip: true

    Behavior on implicitHeight {
        NumberAnimation {
            duration: Theme.motionDeliberate
            easing.type: Easing.InOutCubic
        }
    }

    // Alert background
    Rectangle {
        anchors.fill: parent
        visible: root.hasAlert
        color: Theme.surfaceLowest
        radius: Theme.radiusXS
        border.width: Theme.hairline
        border.color: Theme.luminousWarning
        opacity: root.hasAlert ? 0.92 : 0.0

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.motionStandard
            }
        }
    }

    // Alert content
    Row {
        id: alertContent
        anchors.fill: parent
        anchors.margins: Theme.spacingXXS
        spacing: Theme.spacingXXS
        visible: root.hasAlert
        opacity: root.hasAlert ? 1.0 : 0.0

        Behavior on opacity {
            NumberAnimation {
                duration: Theme.motionStandard
            }
        }

        // Warning indicator dot
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(6, Theme.spacingXXS)
            height: width
            radius: width / 2
            color: Theme.luminousWarning

            // Subtle pulse when alert is active
            SequentialAnimation on opacity {
                running: root.hasAlert
                loops: Animation.Infinite
                NumberAnimation {
                    from: 1.0; to: 0.4
                    duration: Theme.motionCinematic
                    easing.type: Easing.InOutSine
                }
                NumberAnimation {
                    from: 0.4; to: 1.0
                    duration: Theme.motionCinematic
                    easing.type: Easing.InOutSine
                }
            }
        }

        // Alert text
        Text {
            width: parent.width
                   - Theme.spacingXXS      // dot width
                   - parent.spacing
            anchors.verticalCenter: parent.verticalCenter

            text: root.alertMessage
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightRegular
            wrapMode: Text.Wrap
            elide: Text.ElideRight
            maximumLineCount: 2
        }
    }
}
