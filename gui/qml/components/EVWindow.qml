import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15
import "../theme"

ApplicationWindow {
    id: windowRoot
    visible: true
    width: 1280
    height: 720
    minimumWidth: 800
    minimumHeight: 600
    title: "E.V. - Enhanced Virtual Intelligence"
    color: Theme.background
    flags: Qt.FramelessWindowHint | Qt.Window

    // Main content layout
    Item {
        id: contentContainer
        anchors.fill: parent

        EVTopBar {
            id: topBar
            targetWindow: windowRoot
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            height: Theme.spacingLG * 2
        }

        EVStatusIndicator {
            id: statusIndicator
            anchors.top: topBar.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Theme.spacingMD
            height: Theme.spacingLG * 3
        }

        EVCorePlaceholder {
            id: corePlaceholder
            anchors.top: statusIndicator.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Theme.spacingMD
        }
    }

    // Frameless edge and corner resize handlers using startSystemResize
    MouseArea {
        id: topResize
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 6
        cursorShape: Qt.SizeVerCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.TopEdge);
            }
        }
    }

    MouseArea {
        id: bottomResize
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        height: 6
        cursorShape: Qt.SizeVerCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.BottomEdge);
            }
        }
    }

    MouseArea {
        id: leftResize
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: 6
        cursorShape: Qt.SizeHorCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.LeftEdge);
            }
        }
    }

    MouseArea {
        id: rightResize
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 6
        cursorShape: Qt.SizeHorCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.RightEdge);
            }
        }
    }

    MouseArea {
        id: topLeftResize
        anchors.top: parent.top
        anchors.left: parent.left
        width: 10
        height: 10
        cursorShape: Qt.SizeFDiagCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.TopEdge | Qt.LeftEdge);
            }
        }
    }

    MouseArea {
        id: topRightResize
        anchors.top: parent.top
        anchors.right: parent.right
        width: 10
        height: 10
        cursorShape: Qt.SizeBDiagCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.TopEdge | Qt.RightEdge);
            }
        }
    }

    MouseArea {
        id: bottomLeftResize
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        width: 10
        height: 10
        cursorShape: Qt.SizeBDiagCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.BottomEdge | Qt.LeftEdge);
            }
        }
    }

    MouseArea {
        id: bottomRightResize
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 10
        height: 10
        cursorShape: Qt.SizeFDiagCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.BottomEdge | Qt.RightEdge);
            }
        }
    }
}