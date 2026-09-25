import QtQuick 2.15
import "../theme"

// EVPanel - A panel component that builds on EVSurface with optional border and padding
// Suitable for containers that need visible separation
Item {
    id: root

    // Properties
    property bool bordered: false
    property real padding: Theme.spacingM
    property var state: null
    property bool useStateColor: false
    property bool elevated: false
    property bool raised: false
    property bool sunken: false

    // Internal surface
    EVSurface {
        id: surface
        anchors.fill: parent
        elevated: root.elevated
        raised: root.raised
        sunken: root.sunken
        state: root.state
        useStateColor: root.useStateColor
    }

    // Optional border
    Rectangle {
        id: borderRect
        anchors.fill: parent
        color: "transparent"
        border.color: Theme.edgeStandard
        border.width: root.bordered ? Theme.borderThin : 0
        radius: surface.radius
        visible: root.bordered
    }

    // Padding container for children
    Item {
        id: contentItem
        anchors.fill: parent
        anchors.margins: root.padding
    }
}