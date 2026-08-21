import QtQuick 2.15
import "../theme"

// EVHairline - A thin line (1px or device-independent hairline) for subtle separation
// Can be horizontal or vertical
Item {
    id: root

    // Properties
    property bool vertical: false
    property color color: Theme.edgeSubtle
    property real thickness: Theme.hairline

    implicitWidth: root.vertical ? root.thickness : 0
    implicitHeight: root.vertical ? 0 : root.thickness

    // If vertical, swap width and height
    Rectangle {
        id: line
        anchors.fill: parent
        color: root.color
    }
}