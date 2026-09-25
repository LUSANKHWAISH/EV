import QtQuick 2.15
import "../theme"

Item {
    id: root

    property string text: ""
    property var iconSource: ""
    property real iconWidth: 0
    property real iconHeight: 0
    property bool highlighted: false

    readonly property bool hovered: mouseArea.containsMouse
    readonly property bool pressedInternal: mouseArea.pressed

    property real horizontalPadding: Theme.spacingM
    property real verticalPadding: Theme.spacingS

    signal clicked()

    implicitWidth: Math.max(
        Theme.baseUnit * 5,
        contentRow.implicitWidth + horizontalPadding * 2
    )

    implicitHeight: Math.max(
        Theme.baseUnit * 4,
        contentRow.implicitHeight + verticalPadding * 2
    )

    Rectangle {
        id: background
        anchors.fill: parent
        radius: Theme.radiusS

        color: !root.enabled
            ? Theme.surfaceLowest
            : root.pressedInternal
                ? Theme.surfaceElevated
                : (root.hovered || root.highlighted)
                    ? Theme.surfaceRaised
                    : Theme.surfaceBase

        border.width: Theme.borderThin
        border.color: root.hovered
            ? Theme.edgeStandard
            : Theme.edgeSubtle
    }

    Row {
        id: contentRow
        anchors.centerIn: parent
        spacing: Theme.spacingS

        Image {
            id: icon

            source: root.iconSource
            visible: root.iconSource !== ""

            width: root.iconWidth > 0
                ? root.iconWidth
                : Theme.baseUnit * 2

            height: root.iconHeight > 0
                ? root.iconHeight
                : Theme.baseUnit * 2

            fillMode: Image.PreserveAspectFit
            smooth: true

            opacity: root.enabled ? 1.0 : 0.42
        }

        Text {
            text: root.text
            visible: root.text !== ""

            color: root.enabled
                ? Theme.textPrimary
                : Theme.textDisabled

            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightMedium

            verticalAlignment: Text.AlignVCenter
        }
    }

    MouseArea {
        id: mouseArea

        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.PointingHandCursor

        onClicked: root.clicked()
    }
}
