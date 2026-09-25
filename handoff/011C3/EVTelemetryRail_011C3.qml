import QtQuick 2.15
import "../theme"

// Contextual E.V. information rail.
//
// This is not a permanent flagship-stage element. It stays registered for
// future diagnostics/settings/inspection surfaces without inventing telemetry
// that the current bridge does not expose.
Item {
    id: root

    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    // Explicit caller-controlled disclosure.
    property bool expanded: false

    property bool compact:
        width > 0 &&
        width < 160

    property string stateText:
        state === null ||
        state === undefined ||
        String(state).length === 0
        ? "IDLE"
        : String(state)

    implicitWidth:
        root.expanded
        ? 220
        : Theme.spacingLG

    implicitHeight:
        root.expanded
        ? 210
        : Theme.spacingLG

    opacity:
        root.expanded
        ? 1.0
        : 0.62

    // Collapsed form: one truthful state signal only.
    Rectangle {
        visible: !root.expanded
        anchors.centerIn: parent

        width: Math.max(7, Theme.spacingXS)
        height: width
        radius: width / 2

        color: Theme.stateColor(root.stateText)
        opacity: 0.86

        Behavior on color {
            ColorAnimation {
                duration: Theme.motionStandard
            }
        }
    }

    // Expanded form: explicit contextual inspection.
    Column {
        visible:
            root.expanded &&
            !root.compact

        anchors.fill: parent
        anchors.margins: Theme.spacingSM
        spacing: Theme.spacingXS

        Text {
            text: "CONTEXT"
            color: Theme.textTertiary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightMedium
            font.letterSpacing: Theme.letterSpacingWide
        }

        Rectangle {
            width: parent.width
            height: Theme.hairline
            color: Theme.edgeSubtle
        }

        Text {
            text: "STATE"
            color: Theme.textTertiary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightMedium
        }

        Row {
            spacing: Theme.spacingXXS

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.max(6, Theme.spacingXXS)
                height: width
                radius: width / 2
                color: Theme.stateColor(root.stateText)
                opacity: 0.86
            }

            Text {
                text: root.stateText
                color: Theme.textPrimary

                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
            }
        }

        Rectangle {
            width: parent.width
            height: Theme.hairline
            color: Theme.edgeSubtle
        }

        Text {
            text: "MODE"
            color: Theme.textTertiary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightMedium
        }

        Text {
            text: root.visualMode
            color: Theme.textSecondary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightRegular
        }

        Text {
            text: "PROFILE"
            color: Theme.textTertiary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightMedium
        }

        Text {
            text: root.themeProfile.replace("_", " ")
            color: Theme.textSecondary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightRegular
        }
    }

    // Expanded but narrow: collapse visually instead of stacking unreadably.
    Rectangle {
        visible:
            root.expanded &&
            root.compact

        anchors.centerIn: parent

        width: Math.max(7, Theme.spacingXS)
        height: width
        radius: width / 2

        color: Theme.stateColor(root.stateText)
        opacity: 0.86
    }
}
