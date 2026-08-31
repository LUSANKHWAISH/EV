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

    // Background
    Rectangle {
        anchors.fill: parent
        color: Theme.backgroundDeep
    }

    // Ambient field (existing)
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

    // Subtle ambient data layer (new)
    Canvas {
        id: ambientDataLayer
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
            var cy = height * 0.5
            var radius = Math.min(width, height) * 0.4

            var gradient = ctx.createRadialGradient(
                cx, cy, radius * 0.2,
                cx, cy, radius
            )

            // Slowly shifting hue based on time
            var hue = (Date.now() % 120000) / 120000; // 120 second cycle
            var baseColor = Qt.hsla(hue, 0.3, 0.2, 1.0); // subtle cyan-blue

            gradient.addColorStop(
                0.0,
                rgba(baseColor, 0.02)
            )

            gradient.addColorStop(
                0.5,
                rgba(baseColor, 0.01)
            )

            gradient.addColorStop(
                1.0,
                rgba(baseColor, 0.0)
            )

            ctx.fillStyle = gradient
            ctx.fillRect(0, 0, width, height)
        }

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        // Slow animation
        property real _progress: 0
        NumberAnimation on _progress {
            from: 0; to: 1; duration: 120000; loops: Animation.Infinite;
        }
        on_ProgressChanged: requestPaint()
    }

    // Main container: left rail, core, right rail
    Row {
        id: mainContainer
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: executionTimeline.top
        anchors.margins: Theme.spacingS
        spacing: Theme.spacingL

        // Left rail: intelligence/task display
        EVIntelligenceTaskRail {
            id: leftRail
            width: Theme.spacingL * 3 // 72px
            state: root.state
            activeTask: "INITIALIZING"
            currentPhase: "BOOT"
            currentAction: "SYNC"
            riskLevel: "NOMINAL"
            rollbackAvailable: false
        }

        // Central intelligence core (unchanged)
        EVIntelligenceCore {
            id: intelligenceCore
            width: parent.width
                   - leftRail.width
                   - rightRail.width
                   - 2 * parent.spacing
            height: parent.height
            state: root.state
            visualMode: root.visualMode
            themeProfile: root.themeProfile
        }

        // Right rail: telemetry/system rail
        EVTelemetryRail {
            id: rightRail
            width: Theme.spacingL * 3 // 72px
            state: root.state
            visualMode: root.visualMode
            themeProfile: root.themeProfile
        }
    }

    // Bottom execution timeline
    Item {
        id: executionTimeline
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.margins: Theme.spacingL
        height: Theme.spacingM

        readonly property var timelineStates: [
            "IDLE",
            "LISTENING",
            "PLANNING",
            "AWAITING_APPROVAL",
            "EXECUTING",
            "VERIFYING",
            "SUCCESS",
            "SPEAKING"
        ]

        readonly property var timelineLabels: [
            "OBSERVE",
            "LISTEN",
            "PLAN",
            "APPROVAL",
            "EXECUTE",
            "VERIFY",
            "COMPLETE",
            "RESPOND"
        ]

        Row {
            id: timelineRow
            anchors.fill: parent
            spacing: Theme.spacingXS

            Repeater {
                model: executionTimeline.timelineStates.length

                delegate: Item {
                    width: (timelineRow.width -
                            (executionTimeline.timelineStates.length - 1)
                            * Theme.spacingXS)
                           / executionTimeline.timelineStates.length
                    height: timelineRow.height

                    readonly property bool active:
                        root.stateText === executionTimeline.timelineStates[index]

                    readonly property bool passed:
                        executionTimeline.timelineStates.indexOf(root.stateText) > index

                    Rectangle {
                        id: stepIndicator
                        anchors.top: parent.top
                        anchors.horizontalCenter: parent.horizontalCenter

                        width: Theme.spacingXS
                        height: Theme.spacingXS
                        radius: Theme.radiusXS

                        color: active || passed
                               ? root.stateTone
                               : Theme.backgroundBase

                        opacity: active
                                 ? 1.0
                                 : passed
                                   ? 0.65
                                   : 0.35

                        scale: active ? 1.25 : 1.0

                        Behavior on opacity {
                            NumberAnimation {
                                duration: 180
                            }
                        }

                        Behavior on scale {
                            NumberAnimation {
                                duration: 180
                            }
                        }
                    }

                    Text {
                        anchors.top: stepIndicator.bottom
                        anchors.topMargin: Theme.spacingXS
                        anchors.horizontalCenter: parent.horizontalCenter

                        text: executionTimeline.timelineLabels[index]

                        font.family: Theme.fontFamily
                        font.pointSize: Theme.fontSizeLabelSmall
                        color: active
                               ? root.stateTone
                               : Theme.textTertiary

                        opacity: compact
                                 ? 0.0
                                 : active
                                   ? 0.95
                                   : 0.55

                        visible: !compact
                        horizontalAlignment: Text.AlignHCenter
                    }
                }
            }
        }
    }
}
