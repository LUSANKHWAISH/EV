import QtQuick 2.15
import "../theme"

Item {
    id: root

    Rectangle {
        anchors.fill: parent
        color: Theme.surfaceRaised
        radius: Theme.radiusL
    }

    Text {
        text: "E.V. Core"
        color: Theme.textSecondary
        font.pointSize: Theme.fontSizeSection
        anchors.centerIn: parent
    }
}