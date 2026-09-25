import QtQuick 2.15
import "../theme"

// EVTelemetryRail - Truthful sparse system identity/context rail.
Item {
    id: root

    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    property bool compact: width < 140

    property string stateText:
        state === null || state === undefined
        ? "IDLE"
        : String(state)

    Column {
        anchors.fill: parent
        anchors.margins: Theme.spacingSM
        spacing: Theme.spacingXS

        Text {
            text: "E.V."
            font.pointSize: Theme.fontSizeSection
            font.weight: Theme.fontWeightSemibold
            color: Theme.textPrimary
        }

        Text {
            visible: !root.compact
            width: parent.width
            text: "ENHANCED VIRTUAL INTELLIGENCE"
            font.pointSize: Theme.fontSizeLabelSmall
            color: Theme.textTertiary
            wrapMode: Text.WordWrap
        }

        Rectangle {
            visible: !root.compact
            width: parent.width
            height: 1
            color: Theme.luminousPrimary
            opacity: 0.20
        }

        Column {
            visible: !root.compact
            width: parent.width
            spacing: Theme.spacingXS

            Text {
                text: "SYSTEM"
                font.pointSize: Theme.fontSizeLabelSmall
                color: Theme.textTertiary
            }

            Text {
                text: "READY"
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                color: Theme.textPrimary
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.luminousPrimary
                opacity: 0.12
            }

            Text {
                text: "CORE STATE"
                font.pointSize: Theme.fontSizeLabelSmall
                color: Theme.textTertiary
            }

            Row {
                spacing: Theme.spacingXS

                Rectangle {
                    width: Math.max(6, Theme.spacingXS)
                    height: width
                    radius: width / 2
                    color: Theme.stateColor(root.state)
                    opacity: 0.80
                }

                Text {
                    text: root.stateText
                    font.pointSize: Theme.fontSizeLabel
                    color: Theme.textPrimary
                }
            }

            Rectangle {
                width: parent.width
                height: 1
                color: Theme.luminousPrimary
                opacity: 0.12
            }

            Text {
                text: "MODE"
                font.pointSize: Theme.fontSizeLabelSmall
                color: Theme.textTertiary
            }

            Text {
                text: root.visualMode
                font.pointSize: Theme.fontSizeLabel
                color: Theme.textSecondary
            }

            Text {
                text: "PROFILE"
                font.pointSize: Theme.fontSizeLabelSmall
                color: Theme.textTertiary
            }

            Text {
                text: root.themeProfile
                font.pointSize: Theme.fontSizeLabel
                color: Theme.textSecondary
            }
        }

        Rectangle {
            visible: root.compact
            width: Math.max(7, Theme.spacingXS)
            height: width
            radius: width / 2
            color: Theme.stateColor(root.state)
            opacity: 0.80
        }
    }
}
