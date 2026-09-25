import QtQuick 2.15
import "../theme"

// EVSurface - Base surface component with elevation and tone options
// Provides a foundation for building UI elements with controlled depth
Item {
    id: root

    // Properties
    property alias color: rect.color
    property bool elevated: false
    property bool raised: false
    property bool sunken: false
    property var state: null // EVState enum for state-based coloring
    property bool useStateColor: false
    property real radius: Theme.radiusM

    // Background rectangle
    Rectangle {
        id: rect
        anchors.fill: parent
        color: Theme.backgroundBase
        radius: root.radius

        // Compute final color based on properties
        onColorChanged: {
            // Recompute if any property changes
            updateColor()
        }

        Component.onCompleted: updateColor()

        function updateColor() {
            var baseColor = Theme.backgroundBase

            // Apply elevation
            if (root.elevated) {
                baseColor = Theme.surfaceElevated
            } else if (root.raised) {
                baseColor = Theme.surfaceRaised
            } else if (root.sunken) {
                baseColor = Theme.surfaceLowest
            } else {
                baseColor = Theme.surfaceBase
            }

            // Apply state color if requested
            if (root.useStateColor && root.state !== null) {
                baseColor = Theme.stateColor(root.state)
            }

            rect.color = baseColor
        }
    }
}