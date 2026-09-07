import QtQuick 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "../theme"

Item {
    id: root

    property Window targetWindow: null

    height: Theme.topBarHeight

    Rectangle {
        anchors.fill: parent
        color: "transparent"
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom

        height: Theme.hairline
        color: Theme.edgeSubtle
    }

    // Native Windows system move area.
    // Window control MouseAreas below sit above this layer and consume
    // their own mouse events.
    MouseArea {
        id: dragArea

        anchors.fill: parent
        acceptedButtons: Qt.LeftButton

        onPressed: {
            if (root.targetWindow) {
                root.targetWindow.startSystemMove()
            }
        }

        onDoubleClicked: {
            if (!root.targetWindow) {
                return
            }

            if (root.targetWindow.visibility === Window.Maximized) {
                root.targetWindow.showNormal()
            } else {
                root.targetWindow.showMaximized()
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingXS
        anchors.rightMargin: Theme.spacingXXS

        spacing: Theme.spacingXXS

        Text {
            text: "E.V."

            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightMedium

            Layout.alignment: Qt.AlignVCenter
        }

        Rectangle {
            width: Theme.hairline
            height: Theme.spacingXS

            color: Theme.edgeStandard
            Layout.alignment: Qt.AlignVCenter
        }

        Text {
            text: "ENHANCED VIRTUAL INTELLIGENCE"

            color: Theme.textSecondary
            font.family: Theme.fontFamily
            font.pointSize: Theme.fontSizeLabel
            font.weight: Theme.fontWeightMedium

            opacity: Theme.opacityStandard

            Layout.alignment: Qt.AlignVCenter
        }

        Item {
            Layout.fillWidth: true
        }

        EVExperienceModeIndicator {
            id: experienceModeIndicator
            objectName: "experienceModeIndicator"

            Layout.alignment: Qt.AlignVCenter
            Layout.rightMargin: Theme.spacingXS
        }

        // ====================================================
        // MINIMIZE
        // ====================================================

        Rectangle {
            id: minimizeButton

            width: Theme.windowControlWidth
            height: Theme.windowControlHeight

            radius: Theme.radiusS

            color: minimizeArea.pressed
                ? Theme.surfaceElevated
                : minimizeArea.containsMouse
                    ? Theme.surfaceBase
                    : "transparent"

            border.width: minimizeArea.containsMouse
                ? Theme.borderThin
                : 0

            border.color: Theme.edgeSubtle

            Layout.alignment: Qt.AlignVCenter
            z: 10

            Rectangle {
                width: Theme.baseUnit * 1.5
                height: Math.max(1, Theme.hairline)

                anchors.centerIn: parent

                color: Theme.textSecondary
            }

            MouseArea {
                id: minimizeArea

                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor

                onClicked: {
                    if (root.targetWindow) {
                        root.targetWindow.showMinimized()
                    }
                }
            }
        }

        // ====================================================
        // MAXIMIZE / RESTORE
        // ====================================================

        Rectangle {
            id: maximizeButton

            width: Theme.windowControlWidth
            height: Theme.windowControlHeight

            radius: Theme.radiusS

            color: maximizeArea.pressed
                ? Theme.surfaceElevated
                : maximizeArea.containsMouse
                    ? Theme.surfaceBase
                    : "transparent"

            border.width: maximizeArea.containsMouse
                ? Theme.borderThin
                : 0

            border.color: Theme.edgeSubtle

            Layout.alignment: Qt.AlignVCenter
            z: 10

            // Normal maximize glyph
            Rectangle {
                visible: !root.targetWindow ||
                         root.targetWindow.visibility !== Window.Maximized

                width: Theme.baseUnit * 1.45
                height: Theme.baseUnit * 1.25

                anchors.centerIn: parent

                color: "transparent"
                border.width: Math.max(1, Theme.hairline)
                border.color: Theme.textSecondary
            }

            // Restore glyph - rear frame
            Rectangle {
                visible: root.targetWindow &&
                         root.targetWindow.visibility === Window.Maximized

                width: Theme.baseUnit * 1.25
                height: Theme.baseUnit

                x: parent.width / 2 - width / 2 + 2
                y: parent.height / 2 - height / 2 - 2

                color: "transparent"
                border.width: Math.max(1, Theme.hairline)
                border.color: Theme.textSecondary
            }

            // Restore glyph - front frame
            Rectangle {
                visible: root.targetWindow &&
                         root.targetWindow.visibility === Window.Maximized

                width: Theme.baseUnit * 1.25
                height: Theme.baseUnit

                x: parent.width / 2 - width / 2 - 2
                y: parent.height / 2 - height / 2 + 2

                color: Theme.surfaceRaised
                border.width: Math.max(1, Theme.hairline)
                border.color: Theme.textSecondary
            }

            MouseArea {
                id: maximizeArea

                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor

                onClicked: {
                    if (!root.targetWindow) {
                        return
                    }

                    if (root.targetWindow.visibility === Window.Maximized) {
                        root.targetWindow.showNormal()
                    } else {
                        root.targetWindow.showMaximized()
                    }
                }
            }
        }

        // ====================================================
        // CLOSE
        // ====================================================

        Rectangle {
            id: closeButton

            width: Theme.windowControlWidth
            height: Theme.windowControlHeight

            radius: Theme.radiusS

            color: closeArea.pressed
                ? Theme.surfaceElevated
                : closeArea.containsMouse
                    ? Theme.surfaceBase
                    : "transparent"

            border.width: closeArea.containsMouse
                ? Theme.borderThin
                : 0

            border.color: closeArea.containsMouse
                ? Theme.edgeStandard
                : Theme.edgeSubtle

            Layout.alignment: Qt.AlignVCenter
            z: 10

            Item {
                width: Theme.baseUnit * 1.5
                height: Theme.baseUnit * 1.5

                anchors.centerIn: parent

                Rectangle {
                    width: parent.width
                    height: Math.max(1, Theme.hairline)

                    anchors.centerIn: parent

                    rotation: 45
                    color: Theme.textSecondary
                }

                Rectangle {
                    width: parent.width
                    height: Math.max(1, Theme.hairline)

                    anchors.centerIn: parent

                    rotation: -45
                    color: Theme.textSecondary
                }
            }

            MouseArea {
                id: closeArea

                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton
                cursorShape: Qt.PointingHandCursor

                onClicked: {
                    if (root.targetWindow) {
                        root.targetWindow.close()
                    }
                }
            }
        }
    }
}
