import QtQuick 2.15
import QtQuick.Layouts 1.15
import "../theme"

Item {
    id: root
    height: Theme.spacingLG * 3

    Rectangle {
        anchors.fill: parent
        color: Theme.surfaceBase
        radius: Theme.radiusM
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingSM
        spacing: Theme.spacingXS

        Text {
            id: stateText
            text: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.currentState : "IDLE"
            color: Theme.textPrimary
            font.pointSize: Theme.fontSizeBody
            font.weight: Theme.fontWeightMedium
            Layout.alignment: Qt.AlignHCenter | Qt.AlignTop
        }

        Text {
            id: stateDesc
            text: (typeof guiBridge !== "undefined" && guiBridge !== null) ? guiBridge.getStateDescription(guiBridge.currentState) : ""
            color: Theme.textSecondary
            font.pointSize: Theme.fontSizeLabel
            Layout.alignment: Qt.AlignHCenter | Qt.AlignBottom
        }
    }
}