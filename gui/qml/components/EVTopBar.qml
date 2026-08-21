import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import "../theme"

Item {
    id: root
    height: Theme.spacingLG * 2

    required property Window targetWindow

    Rectangle {
        anchors.fill: parent
        color: Theme.surfaceRaised
    }

    // Window drag area using native startSystemMove
    MouseArea {
        anchors.fill: parent
        onPressed: function(mouse) {
            if (mouse.button === Qt.LeftButton && targetWindow) {
                if (typeof targetWindow.startSystemMove === "function") {
                    targetWindow.startSystemMove();
                }
            }
        }
        onDoubleClicked: function(mouse) {
            if (mouse.button === Qt.LeftButton && targetWindow) {
                if (targetWindow.visibility === Window.Maximized) {
                    targetWindow.showNormal();
                } else {
                    targetWindow.showMaximized();
                }
            }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: Theme.spacingMD
        anchors.rightMargin: Theme.spacingSM
        spacing: Theme.spacingSM

        Text {
            text: "E.V. - Enhanced Virtual Intelligence"
            color: Theme.textPrimary
            font.pointSize: 12
            font.bold: true
            elide: Text.ElideRight
            Layout.alignment: Qt.AlignLeft | Qt.AlignVCenter
            Layout.fillWidth: true
        }

        RowLayout {
            spacing: Theme.spacingXS
            Layout.alignment: Qt.AlignRight | Qt.AlignVCenter

            // Minimize Button
            Button {
                id: minimizeButton
                implicitWidth: Theme.spacingLG
                implicitHeight: Theme.spacingLG
                contentItem: Text {
                    text: "_"
                    color: Theme.textPrimary
                    font.pointSize: 12
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: minimizeButton.down ? Theme.surfaceOverlay : (minimizeButton.hovered ? Theme.surface : Theme.surfaceRaised)
                    radius: Theme.radiusSM
                }
                onClicked: {
                    if (targetWindow) {
                        targetWindow.showMinimized();
                    }
                }
            }

            // Maximize / Restore Button
            Button {
                id: maximizeButton
                implicitWidth: Theme.spacingLG
                implicitHeight: Theme.spacingLG
                contentItem: Text {
                    text: (targetWindow && targetWindow.visibility === Window.Maximized) ? "[]" : "[ ]"
                    color: Theme.textPrimary
                    font.pointSize: 11
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: maximizeButton.down ? Theme.surfaceOverlay : (maximizeButton.hovered ? Theme.surface : Theme.surfaceRaised)
                    radius: Theme.radiusSM
                }
                onClicked: {
                    if (targetWindow) {
                        if (targetWindow.visibility === Window.Maximized) {
                            targetWindow.showNormal();
                        } else {
                            targetWindow.showMaximized();
                        }
                    }
                }
            }

            // Close Button
            Button {
                id: closeButton
                implicitWidth: Theme.spacingLG
                implicitHeight: Theme.spacingLG
                contentItem: Text {
                    text: "X"
                    color: closeButton.hovered ? Theme.error : Theme.textPrimary
                    font.pointSize: 12
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    color: closeButton.down ? Theme.surfaceOverlay : (closeButton.hovered ? Theme.surface : Theme.surfaceRaised)
                    radius: Theme.radiusSM
                }
                onClicked: {
                    if (targetWindow) {
                        targetWindow.close();
                    }
                }
            }
        }
    }
}