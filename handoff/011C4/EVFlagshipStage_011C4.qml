import QtQuick 2.15
import "../theme"

// E.V. flagship workspace.
//
// 011C.3 information ownership:
// - EVTopBar owns product identity / window chrome.
// - This stage owns active state + state description.
// - Mode/profile remain low-priority configuration context.
// - No unconditional system-health claim is shown.
// - EVTelemetryRail and EVStatusIndicator remain registered for contextual use.
Item {
    id: root

    width: Theme.windowDefaultWidth
    height: Theme.windowDefaultHeight

    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"
    property var state: null

    property string stateText:
        state === null ||
        state === undefined ||
        String(state).length === 0
        ? "IDLE"
        : String(state)

    property string stateDescription:
        typeof guiBridge !== "undefined" &&
        guiBridge !== null
        ? guiBridge.getStateDescription(root.stateText)
        : ""

    property color stateTone: Theme.stateColor(root.stateText)
    property real stateEnergy: Theme.stateEnergy(root.stateText)

    property bool compact:
        width < Theme.stageCompactWidth ||
        height < Theme.stageCompactHeight

    Rectangle {
        anchors.fill: parent
        color: Theme.backgroundDeep
    }

    Canvas {
        id: ambientField
        anchors.fill: parent

        function rgba(colorValue, alphaValue) {
            return "rgba("
                + Math.round(colorValue.r * 255) + ","
                + Math.round(colorValue.g * 255) + ","
                + Math.round(colorValue.b * 255) + ","
                + alphaValue + ")"
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)

            var cx = width * 0.5
            var cy = height * 0.47
            var radius = Math.min(width, height) * 0.56

            var gradient = ctx.createRadialGradient(
                cx, cy, 0,
                cx, cy, radius
            )

            gradient.addColorStop(
                0.0,
                rgba(
                    root.stateTone,
                    0.075 + root.stateEnergy * 0.035
                )
            )

            gradient.addColorStop(
                0.32,
                rgba(
                    root.stateTone,
                    0.030 + root.stateEnergy * 0.016
                )
            )

            gradient.addColorStop(
                0.68,
                rgba(root.stateTone, 0.006)
            )

            gradient.addColorStop(
                1.0,
                rgba(root.stateTone, 0.0)
            )

            ctx.fillStyle = gradient
            ctx.fillRect(0, 0, width, height)
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        Connections {
            target: root

            function onStateToneChanged() {
                ambientField.requestPaint()
            }

            function onStateEnergyChanged() {
                ambientField.requestPaint()
            }
        }
    }

    // Primary intelligence presence.
    EVIntelligenceCore {
        id: intelligenceCore

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.verticalCenter: parent.verticalCenter

        anchors.verticalCenterOffset:
            root.compact
            ? -Theme.spacingXXS
            : -Theme.spacingXS

        width:
            root.compact
            ? parent.width * 0.90
            : parent.width * 0.86

        height:
            root.compact
            ? parent.height * 0.74
            : parent.height * 0.80

        scale: 1.0

        visualMode: root.visualMode
        themeProfile: root.themeProfile
        state: root.state

        Behavior on scale {
            NumberAnimation {
                duration: Theme.motionDeliberate
                easing.type: Theme.easingDeliberate
            }
        }
    }

    // Primary dynamic information: one authoritative state presentation.
    Column {
        id: stateContext

        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom

        anchors.bottomMargin:
            root.compact
            ? Theme.spacingXS
            : Theme.spacingL

        width: Math.min(parent.width * 0.72, 620)
        spacing: Theme.spacingXXXS

        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            spacing: Theme.spacingXXS

            Rectangle {
                anchors.verticalCenter: parent.verticalCenter

                width:
                    root.compact
                    ? Math.max(4, Theme.spacingXXXS)
                    : Math.max(5, Theme.spacingXXXS + 1)

                height: width
                radius: width / 2

                color: root.stateTone
                opacity: Theme.opacityEmphasis

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.motionStandard
                    }
                }
            }

            Text {
                text: root.stateText
                color: root.stateTone

                font.family: Theme.fontFamily
                font.pointSize:
                    root.compact
                    ? Theme.fontSizeLabel
                    : Theme.fontSizeBody

                font.weight: Theme.fontWeightSemibold
                font.letterSpacing:
                    root.compact
                    ? Theme.letterSpacingWide
                    : Theme.letterSpacingEmphasis

                Behavior on color {
                    ColorAnimation {
                        duration: Theme.motionStandard
                    }
                }
            }
        }

        Text {
            visible:
                !root.compact &&
                root.stateDescription.length > 0

            width: parent.width
            text: root.stateDescription
            color: Theme.textSecondary

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightRegular

            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
        }
    }

    // Secondary configuration context only.
    // Product identity already lives in EVTopBar.
    Text {
        id: configurationContext

        visible: !root.compact

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.rightMargin: Theme.spacingXXS
        anchors.bottomMargin: Theme.spacingXXS

        text:
            root.visualMode
            + "  ·  "
            + root.themeProfile.replace("_", " ")

        color: Theme.textTertiary
        opacity: Theme.opacitySubtle

        font.family: Theme.fontFamily
        font.pointSize: Theme.fontSizeLabelSmall
        font.weight: Theme.fontWeightMedium
        font.letterSpacing: Theme.letterSpacingWide
    }
}
