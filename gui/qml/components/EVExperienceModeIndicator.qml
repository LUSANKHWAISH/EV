import QtQuick 2.15
import "../theme"

// EVExperienceModeIndicator.qml
//
// Compact visual indicator showing the current experience mode.
// Binds to guiBridge.experienceMode.  Purely presentational —
// no execution authority, no mutation capability.
Item {
    id: root

    property string mode:
        typeof guiBridge !== "undefined" && guiBridge !== null
        ? guiBridge.experienceMode
        : "STANDARD"

    property color modeColor: Theme.experienceModeColor(root.mode)
    property string modeGlyph: Theme.experienceModeGlyph(root.mode)

    implicitWidth: modeRow.implicitWidth + Theme.spacingXS * 2
    implicitHeight: Theme.spacingS

    Row {
        id: modeRow
        anchors.centerIn: parent
        spacing: Theme.spacingXXS

        // Colored dot
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.max(6, Theme.spacingXXS)
            height: width
            radius: width / 2
            color: root.modeColor
            opacity: Theme.opacitySignal

            Behavior on color {
                ColorAnimation {
                    duration: Theme.motionStandard
                }
            }
        }

        // Glyph
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.modeGlyph
            color: root.modeColor
            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            opacity: Theme.opacityMuted

            Behavior on color {
                ColorAnimation {
                    duration: Theme.motionStandard
                }
            }
        }

        // Label
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.mode
            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabelSmall
            font.weight: Theme.fontWeightMedium
            font.letterSpacing: Theme.letterSpacingWide

            Behavior on color {
                ColorAnimation {
                    duration: Theme.motionStandard
                }
            }
        }
    }
}
