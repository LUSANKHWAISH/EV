import QtQuick 2.15
import "../theme"

// EVTelemetryRail.qml
//
// Precision telemetry rail for E.V. flagship workspace (Task 018-D).
// Designed to fit within the 72px right-column boundary of EVFlagshipStage.
// Pure presentation surface: read-only bindings to GuiBridge telemetry properties.
// Zero execution authority, zero commands, zero subprocess calls, zero polling timers.
Item {
    id: root
    objectName: "telemetryRail"

    // Preserved stage interface properties for seamless compatibility
    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    // Read-only bridge bindings
    readonly property bool isBridgeValid: typeof guiBridge !== "undefined" && guiBridge !== null
    readonly property bool telemetryAvailable: isBridgeValid ? guiBridge.telemetryAvailable : false
    readonly property int telemetryAgeMs: isBridgeValid ? guiBridge.telemetryAgeMs : -1
    readonly property real cpuPercent: isBridgeValid ? guiBridge.telemetryCpuPercent : 0.0
    readonly property real memPercent: isBridgeValid ? guiBridge.telemetryMemoryPercent : 0.0
    readonly property real diskPercent: isBridgeValid ? guiBridge.telemetryDiskFreePercent : 0.0
    readonly property bool netConnected: isBridgeValid ? guiBridge.telemetryNetworkConnected : false
    readonly property int processCount: isBridgeValid ? guiBridge.telemetryProcessCount : 0
    readonly property string topProcessName: isBridgeValid ? guiBridge.telemetryTopProcessName : ""

    // Three lifecycle presentation states (Task 018-D Section 6)
    readonly property bool isLive: telemetryAvailable && telemetryAgeMs >= 0 && telemetryAgeMs <= 10000
    readonly property bool isStale: telemetryAvailable && telemetryAgeMs > 10000
    readonly property bool isStandby: !telemetryAvailable

    implicitWidth: 72
    implicitHeight: contentColumn.implicitHeight + Theme.spacingS

    clip: true

    Column {
        id: contentColumn
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingXXS
        anchors.rightMargin: Theme.spacingXXS
        anchors.topMargin: Theme.spacingXXS
        spacing: Theme.spacingXS

        // -------------------------------------------------------------
        // Header: System Telemetry Identity & Status Badge
        // -------------------------------------------------------------
        Column {
            width: parent.width
            spacing: 2

            Text {
                text: "TELEMETRY"
                color: Theme.textTertiary
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeLabelSmall
                font.weight: Theme.fontWeightMedium
                font.letterSpacing: Theme.letterSpacingWide
            }

            Row {
                spacing: Theme.spacingXXXS

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 5
                    height: 5
                    radius: 2.5
                    color: root.isStandby
                           ? Theme.textTertiary
                           : (root.isStale ? Theme.luminousWarning : Theme.luminousPrimary)
                }

                Text {
                    text: root.isStandby ? "STANDBY" : (root.isStale ? "STALE" : "LIVE")
                    color: root.isStandby
                           ? Theme.textTertiary
                           : (root.isStale ? Theme.luminousWarning : Theme.luminousPrimary)
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }
            }

            Rectangle {
                width: parent.width
                height: Theme.hairline
                color: Theme.edgeSubtle
            }
        }

        // -------------------------------------------------------------
        // Metrics Stack (Muted when Stale or Standby)
        // -------------------------------------------------------------
        Column {
            id: metricsGroup
            width: parent.width
            spacing: Theme.spacingXS
            opacity: root.isLive ? 1.0 : Theme.opacityMuted

            Behavior on opacity {
                NumberAnimation {
                    duration: Theme.motionStandard
                }
            }

            // CPU Block
            Column {
                width: parent.width
                spacing: 1

                Text {
                    text: "CPU"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    text: root.isStandby ? "--" : root.cpuPercent.toFixed(0) + "%"
                    color: (root.isLive && root.cpuPercent >= 90)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                }
            }

            // RAM Block
            Column {
                width: parent.width
                spacing: 1

                Text {
                    text: "RAM"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    text: root.isStandby ? "--" : root.memPercent.toFixed(0) + "%"
                    color: (root.isLive && root.memPercent >= 90)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                }
            }

            // DISK Block
            Column {
                width: parent.width
                spacing: 1

                Text {
                    text: "DISK"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    text: root.isStandby ? "--" : root.diskPercent.toFixed(0) + "%"
                    color: (root.isLive && root.diskPercent <= 10)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                }
            }

            // NET Block
            Column {
                width: parent.width
                spacing: 1

                Text {
                    text: "NET"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    text: root.isStandby ? "--" : (root.netConnected ? "ON" : "OFF")
                    color: root.isStandby
                           ? Theme.textTertiary
                           : (root.netConnected ? Theme.luminousPrimary : Theme.luminousWarning)
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                }
            }

            // PROC Block
            Column {
                width: parent.width
                spacing: 1

                Text {
                    text: "PROC"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    text: root.isStandby ? "--" : String(root.processCount)
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                }
            }

            // Contextual Top Process (if available)
            Column {
                width: parent.width
                spacing: 1
                visible: root.isLive && root.topProcessName.length > 0

                Text {
                    text: "TOP"
                    color: Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightMedium
                }

                Text {
                    width: parent.width
                    text: root.topProcessName
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightRegular
                    elide: Text.ElideRight
                }
            }
        }
    }
}
