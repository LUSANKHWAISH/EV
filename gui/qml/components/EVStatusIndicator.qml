import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../theme"

Item {
    id: root
    height: Theme.spacingLG * 3

    Rectangle {
        anchors.fill: parent
        color: Theme.surface
        radius: Theme.radiusMD
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingSM
        spacing: Theme.spacingXS

        Text {
            id: stateText
            text: typeof guiBridge !== "undefined" ? guiBridge.currentState : "IDLE"
            color: Theme.accent
            font.pointSize: 16
            font.bold: true
            Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
        }

        Text {
            id: stateDesc
            text: typeof guiBridge !== "undefined" ? guiBridge.getStateDescription(guiBridge.currentState) : ""
            color: Theme.textSecondary
            font.pointSize: 12
            Layout.alignment: Qt.AlignHCenter | Qt.AlignBottom
        }
    }
}