import QtQuick 2.15
import "../theme"

// Reusable contextual state summary.
//
// 011C.3 removes this component from any permanent-header role.
// It remains registered/importable for future contextual surfaces.
Item {
    id: root

    property var state: null

    property string stateText:
        state === null ||
        state === undefined ||
        String(state).length === 0
        ? (
            typeof guiBridge !== "undefined" &&
            guiBridge !== null
            ? guiBridge.currentState
            : "IDLE"
          )
        : String(state)

    property string description:
        typeof guiBridge !== "undefined" &&
        guiBridge !== null
        ? guiBridge.getStateDescription(root.stateText)
        : ""

    property bool compact: false
    property bool showDescription: !compact

    implicitWidth: compact ? 120 : 360
    implicitHeight:
        compact
        ? Theme.spacingS
        : Theme.spacingS * 2

    Row {
        anchors.fill: parent
        spacing: Theme.spacingXXS

        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(5, Theme.spacingXXXS + 1)
            height: width
            radius: width / 2
            color: Theme.stateColor(root.stateText)
            opacity: Theme.opacityEmphasis

            Behavior on color {
                ColorAnimation {
                    duration: Theme.motionStandard
                }
            }
        }

        Column {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(0, parent.width - Theme.spacingXS)
            spacing: Theme.spacingXXXS

            Text {
                text: root.stateText
                color: Theme.stateColor(root.stateText)

                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabel
                font.weight: Theme.fontWeightSemibold
                font.letterSpacing: Theme.letterSpacingWide
            }

            Text {
                visible:
                    root.showDescription &&
                    root.description.length > 0

                width: parent.width
                text: root.description
                color: Theme.textSecondary

                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightRegular

                elide: Text.ElideRight
            }
        }
    }
}
