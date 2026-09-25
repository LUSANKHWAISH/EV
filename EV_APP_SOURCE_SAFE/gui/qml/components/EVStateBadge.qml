import QtQuick 2.15
import "../theme"

// EVStateBadge - A small indicator that shows the current state with a colored shape and label.
// Designed as precision telemetry, not a rounded pill SaaS badge.
Item {
    id: root

    // Properties
    property alias state: badge.state
    property bool showLabel: true
    property real size: Theme.spacingM   // width and height of the badge

    // Internal EVSurface for the badge background
    EVSurface {
        id: badge
        width: root.size
        height: root.size
        radius: Theme.radiusS
        state: root.state
        useStateColor: true
    }

    // Optional label (e.g., "IDLE", "LIST", etc.)
    Text {
        id: label
        text: root.showLabel ? root.state : ""
        font.family: Theme.fontFamily
        font.pointSize: Theme.fontSizeLabelSmall
        font.weight: Theme.fontWeightMedium
        color: Theme.textPrimary
        anchors.centerIn: badge
        visible: root.showLabel
        elide: Text.ElideRight
    }
}