import QtQuick 2.15
import QtQuick.Window 2.15
import QtQuick.Controls 2.15
import "../theme"
import ".." as Main

// EVWindow.qml provides the architectural window shell.
// It is an ApplicationWindow with a frameless style, custom top bar, and window controls.
// It contains Main.qml as its central content.
// Uses the E.V. Design System from Theme.qml and components.

ApplicationWindow {
    id: windowRoot
    visible: true
    width: Theme.windowDefaultWidth
    height: Theme.windowDefaultHeight
    minimumWidth: Theme.windowMinimumWidth
    minimumHeight: Theme.windowMinimumHeight
    title: "E.V. - Enhanced Virtual Intelligence"
    color: Theme.backgroundDeep

    // Window flags for custom chrome (frameless)
    flags: Qt.Window
           | Qt.FramelessWindowHint
           | Qt.WindowSystemMenuHint
           | Qt.WindowMinMaxButtonsHint
           | Qt.WindowCloseButtonHint

    // Configure Qt Quick Controls to use Basic style (avoids native Windows warnings)
    // This is typically done in C++/Python before QML loading, but we can also set it here
    // as a fallback or to ensure consistency. The primary configuration should be in gui/app.py.
    // Note: Actually setting the style should be done before QML engine initialization.
    // We'll rely on gui/app.py to do this properly.

    // Main content layout.
    // The flagship stage receives the full workspace below the custom
    // window chrome. State presentation is handled inside the stage
    // instead of consuming permanent vertical space in a second header.
    Item {
        id: contentContainer
        anchors.fill: parent

        EVTopBar {
            id: topBar
            targetWindow: windowRoot

            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right

            height: Theme.topBarHeight
        }

        EVFlagshipStage {
            id: flagshipStage

            anchors.top: topBar.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: commandInput.top

            anchors.topMargin: Theme.spacingXXXS
            anchors.leftMargin: Theme.spacingXS
            anchors.rightMargin: Theme.spacingXS
            anchors.bottomMargin: Theme.spacingXS

            state: guiBridge.currentState
            visualMode: (typeof guiBridge !== "undefined" && guiBridge !== null && guiBridge.experienceMode !== "")
                        ? guiBridge.experienceMode
                        : "STANDARD"
            themeProfile: (typeof guiBridge !== "undefined" && guiBridge !== null && guiBridge.stylePreset !== "")
                          ? guiBridge.stylePreset
                          : "EV_CORE"
        }

        EVCommandInput {
            id: commandInput
            anchors.bottom: parent.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: Theme.spacingXS
            anchors.rightMargin: Theme.spacingXS
            anchors.bottomMargin: Theme.spacingXS
        }

    }
    // Frameless edge and corner resize handlers using startSystemResize
    MouseArea {
        id: topResize
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: Theme.windowResizeEdgeSize
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
        height: Theme.windowResizeEdgeSize
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
        width: Theme.windowResizeEdgeSize
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
        width: Theme.windowResizeEdgeSize
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
        width: Theme.windowResizeCornerSize
        height: Theme.windowResizeCornerSize
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
        width: Theme.windowResizeCornerSize
        height: Theme.windowResizeCornerSize
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
        width: Theme.windowResizeCornerSize
        height: Theme.windowResizeCornerSize
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
        width: Theme.windowResizeCornerSize
        height: Theme.windowResizeCornerSize
        cursorShape: Qt.SizeFDiagCursor
        onPressed: function() {
            if (typeof windowRoot.startSystemResize === "function") {
                windowRoot.startSystemResize(Qt.BottomEdge | Qt.RightEdge);
            }
        }
    }
}
