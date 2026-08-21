import QtQuick 2.15
import "../theme"

// EVSignalIndicator - A small indicator for showing state or health via animated pulses or fills.
// Not for fake activity; only for meaningful state visualization.
Item {
    id: root

    // Properties
    property bool active: false
    property real size: Theme.spacingM
    property var state: null
    property bool useStateColor: true
    property int pulseDuration: Theme.motionAmbient
    property real pulseOpacity: Theme.luminanceActive

    // Background circle
    Rectangle {
        id: background
        width: root.size
        height: root.size
        radius: Math.min(width, height) / 2
        color: Theme.surfaceLowest
    }

    // Foreground fill (indicates level or activity)
    Rectangle {
        id: foreground
        width: root.active ? root.size : 0
        height: root.active ? root.size : 0
        radius: Math.min(width, height) / 2
        color: root.useStateColor && root.state !== null ?
               Theme.stateColor(root.state) :
               Theme.textPrimary
        // Center the foreground within the background
        anchors.centerIn: background
    }

    // Optional pulse effect for active state
    Rectangle {
        id: pulse
        width: root.size * 1.5
        height: root.size * 1.5
        radius: Math.min(width, height) / 2
        color: root.useStateColor && root.state !== null ?
               Theme.stateColor(root.state) :
               Theme.textPrimary
        opacity: 0
        anchors.centerIn: background
        visible: root.active
        SequentialAnimation on opacity {
            running: root.active
            loops: Animation.Infinite
            PauseAnimation { duration: root.pulseDuration / 2 }
            NumberAnimation { to: root.pulseOpacity; duration: root.pulseDuration / 2 }
            NumberAnimation { to: 0; duration: root.pulseDuration / 2 }
        }
    }
}
