import QtQuick 2.15
import QtQuick.Shapes 1.15
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
        anchors.leftMargin: 6
        anchors.rightMargin: 6
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

            // CPU Metric (Icon + Value)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS

                Shape {
                    id: cpuIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: (root.isLive && root.cpuPercent >= 90)
                                     ? Theme.luminousWarning
                                     : Theme.textTertiary
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.MiterJoin

                        // Center chip body
                        startX: 4
                        startY: 4
                        PathLine { x: 16; y: 4 }
                        PathLine { x: 16; y: 16 }
                        PathLine { x: 4; y: 16 }
                        PathLine { x: 4; y: 4 }

                        // Top pins
                        PathMove { x: 7; y: 4 }
                        PathLine { x: 7; y: 1 }
                        PathMove { x: 10; y: 4 }
                        PathLine { x: 10; y: 1 }
                        PathMove { x: 13; y: 4 }
                        PathLine { x: 13; y: 1 }

                        // Bottom pins
                        PathMove { x: 7; y: 16 }
                        PathLine { x: 7; y: 19 }
                        PathMove { x: 10; y: 16 }
                        PathLine { x: 10; y: 19 }
                        PathMove { x: 13; y: 16 }
                        PathLine { x: 13; y: 19 }

                        // Left pins
                        PathMove { x: 4; y: 7 }
                        PathLine { x: 1; y: 7 }
                        PathMove { x: 4; y: 10 }
                        PathLine { x: 1; y: 10 }
                        PathMove { x: 4; y: 13 }
                        PathLine { x: 1; y: 13 }

                        // Right pins
                        PathMove { x: 16; y: 7 }
                        PathLine { x: 19; y: 7 }
                        PathMove { x: 16; y: 10 }
                        PathLine { x: 19; y: 10 }
                        PathMove { x: 16; y: 13 }
                        PathLine { x: 19; y: 13 }
                    }

                    // Inner core square
                    ShapePath {
                        strokeWidth: 1.0
                        strokeColor: (root.isLive && root.cpuPercent >= 90)
                                     ? Theme.luminousWarning
                                     : Theme.textTertiary
                        fillColor: "transparent"
                        startX: 8
                        startY: 8
                        PathLine { x: 12; y: 8 }
                        PathLine { x: 12; y: 12 }
                        PathLine { x: 8; y: 12 }
                        PathLine { x: 8; y: 8 }
                    }
                }

                Text {
                    text: root.isStandby ? "--" : root.cpuPercent.toFixed(0) + "%"
                    color: (root.isLive && root.cpuPercent >= 90)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // RAM Metric (Icon + Value)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS

                Shape {
                    id: ramIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: (root.isLive && root.memPercent >= 90)
                                     ? Theme.luminousWarning
                                     : Theme.textTertiary
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.MiterJoin

                        // Main horizontal module board with bottom key notch
                        startX: 2
                        startY: 6
                        PathLine { x: 18; y: 6 }
                        PathLine { x: 18; y: 15 }
                        PathLine { x: 12; y: 15 }
                        PathLine { x: 12; y: 13.5 }
                        PathLine { x: 10; y: 13.5 }
                        PathLine { x: 10; y: 15 }
                        PathLine { x: 2; y: 15 }
                        PathLine { x: 2; y: 6 }

                        // Chip 1
                        PathMove { x: 4.5; y: 8.5 }
                        PathLine { x: 8.5; y: 8.5 }
                        PathLine { x: 8.5; y: 12.5 }
                        PathLine { x: 4.5; y: 12.5 }
                        PathLine { x: 4.5; y: 8.5 }

                        // Chip 2
                        PathMove { x: 11.5; y: 8.5 }
                        PathLine { x: 15.5; y: 8.5 }
                        PathLine { x: 15.5; y: 12.5 }
                        PathLine { x: 11.5; y: 12.5 }
                        PathLine { x: 11.5; y: 8.5 }
                    }
                }

                Text {
                    text: root.isStandby ? "--" : root.memPercent.toFixed(0) + "%"
                    color: (root.isLive && root.memPercent >= 90)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // DISK Metric (Icon + Value)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS

                Shape {
                    id: diskIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: (root.isLive && root.diskPercent <= 10)
                                     ? Theme.luminousWarning
                                     : Theme.textTertiary
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap

                        // Top ellipse
                        startX: 2
                        startY: 6
                        PathArc { x: 18; y: 6; radiusX: 8; radiusY: 3.2; useLargeArc: false }
                        PathArc { x: 2; y: 6; radiusX: 8; radiusY: 3.2; useLargeArc: false }

                        // Middle cylinder rim
                        PathMove { x: 2; y: 6 }
                        PathLine { x: 2; y: 11 }
                        PathArc { x: 18; y: 11; radiusX: 8; radiusY: 3.2; useLargeArc: false }
                        PathLine { x: 18; y: 6 }

                        // Bottom cylinder rim
                        PathMove { x: 2; y: 11 }
                        PathLine { x: 2; y: 16 }
                        PathArc { x: 18; y: 16; radiusX: 8; radiusY: 3.2; useLargeArc: false }
                        PathLine { x: 18; y: 11 }
                    }
                }

                Text {
                    text: root.isStandby ? "--" : root.diskPercent.toFixed(0) + "%"
                    color: (root.isLive && root.diskPercent <= 10)
                           ? Theme.luminousWarning
                           : Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // NET Metric (Icon + Value)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS

                Shape {
                    id: netIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: root.isStandby
                                     ? Theme.textTertiary
                                     : (root.netConnected ? Theme.luminousPrimary : Theme.luminousWarning)
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.MiterJoin

                        // Top Node Box
                        startX: 7
                        startY: 2
                        PathLine { x: 13; y: 2 }
                        PathLine { x: 13; y: 7 }
                        PathLine { x: 7; y: 7 }
                        PathLine { x: 7; y: 2 }

                        // Vertical bus down
                        PathMove { x: 10; y: 7 }
                        PathLine { x: 10; y: 12 }

                        // Horizontal distribution bus
                        PathMove { x: 4; y: 12 }
                        PathLine { x: 16; y: 12 }

                        // Left vertical drop and node box
                        PathMove { x: 4; y: 12 }
                        PathLine { x: 4; y: 14 }
                        PathMove { x: 2; y: 14 }
                        PathLine { x: 6; y: 14 }
                        PathLine { x: 6; y: 18 }
                        PathLine { x: 2; y: 18 }
                        PathLine { x: 2; y: 14 }

                        // Right vertical drop and node box
                        PathMove { x: 16; y: 12 }
                        PathLine { x: 16; y: 14 }
                        PathMove { x: 14; y: 14 }
                        PathLine { x: 18; y: 14 }
                        PathLine { x: 18; y: 18 }
                        PathLine { x: 14; y: 18 }
                        PathLine { x: 14; y: 14 }
                    }
                }

                Text {
                    text: root.isStandby ? "--" : (root.netConnected ? "ON" : "OFF")
                    color: root.isStandby
                           ? Theme.textTertiary
                           : (root.netConnected ? Theme.luminousPrimary : Theme.luminousWarning)
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // PROC Metric (Icon + Value)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS

                Shape {
                    id: procIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: Theme.textTertiary
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.MiterJoin

                        // Outer toothed gear outline
                        startX: 8.5
                        startY: 1.5
                        PathLine { x: 11.5; y: 1.5 }
                        PathLine { x: 11.5; y: 4.5 }
                        PathLine { x: 14.5; y: 6.2 }
                        PathLine { x: 17.1; y: 4.7 }
                        PathLine { x: 18.6; y: 7.3 }
                        PathLine { x: 16.0; y: 8.8 }
                        PathLine { x: 16.0; y: 11.2 }
                        PathLine { x: 18.6; y: 12.7 }
                        PathLine { x: 17.1; y: 15.3 }
                        PathLine { x: 14.5; y: 13.8 }
                        PathLine { x: 11.5; y: 15.5 }
                        PathLine { x: 11.5; y: 18.5 }
                        PathLine { x: 8.5; y: 18.5 }
                        PathLine { x: 8.5; y: 15.5 }
                        PathLine { x: 5.5; y: 13.8 }
                        PathLine { x: 2.9; y: 15.3 }
                        PathLine { x: 1.4; y: 12.7 }
                        PathLine { x: 4.0; y: 11.2 }
                        PathLine { x: 4.0; y: 8.8 }
                        PathLine { x: 1.4; y: 7.3 }
                        PathLine { x: 2.9; y: 4.7 }
                        PathLine { x: 5.5; y: 6.2 }
                        PathLine { x: 8.5; y: 4.5 }
                        PathLine { x: 8.5; y: 1.5 }

                        // Center axle hole
                        PathMove { x: 7.5; y: 10 }
                        PathArc { x: 12.5; y: 10; radiusX: 2.5; radiusY: 2.5; useLargeArc: false }
                        PathArc { x: 7.5; y: 10; radiusX: 2.5; radiusY: 2.5; useLargeArc: false }
                    }
                }

                Text {
                    text: root.isStandby ? "--" : String(root.processCount)
                    color: Theme.textPrimary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabel
                    font.weight: Theme.fontWeightSemibold
                    anchors.verticalCenter: parent.verticalCenter
                }
            }

            // Contextual Top Process (Icon + Value, if available)
            Row {
                width: parent.width
                spacing: Theme.spacingXXXS
                visible: root.isLive && root.topProcessName.length > 0

                Shape {
                    id: topIconShape
                    width: 20
                    height: 20
                    layer.enabled: true
                    layer.samples: 4
                    anchors.verticalCenter: parent.verticalCenter

                    ShapePath {
                        strokeWidth: 1.2
                        strokeColor: Theme.textTertiary
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.MiterJoin

                        // Upper chevron
                        startX: 4
                        startY: 9
                        PathLine { x: 10; y: 3 }
                        PathLine { x: 16; y: 9 }

                        // Lower chevron
                        PathMove { x: 4; y: 15 }
                        PathLine { x: 10; y: 9 }
                        PathLine { x: 16; y: 15 }
                    }
                }

                Text {
                    width: parent.width - Theme.spacingXXXS - 20
                    text: root.topProcessName
                    color: Theme.textSecondary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    font.weight: Theme.fontWeightRegular
                    elide: Text.ElideRight
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
        }
    }
}
