import QtQuick 2.15
import "../theme"

// EVIconButton - A button that shows only an icon, useful for toolbars and controls.
// Follows the same interaction language as EVButton but optimized for icons.
Item {
    id: root

    // Properties
    property string iconSource: ""        // required: path or URL to icon
    property real iconSize: Theme.spacingL // size of the icon
    property bool highlighted: false   // for hover or focus
    property bool pressed: false
    property int alignment: Qt.AlignCenter   // default alignment

    // Internal state for mouse interaction
    property bool hovered: false
    property bool pressedInternal: false

    // Visual dimensions
    implicitWidth: iconSize + horizontalPadding * 2
    implicitHeight: iconSize + verticalPadding * 2
    property real horizontalPadding: Theme.spacingS
    property real verticalPadding: Theme.spacingXS

    // Background
    Rectangle {
        id: background
        anchors.fill: parent
        radius: Theme.radiusM
        color: root.enabled ? (
            pressedInternal ? Theme.surfaceElevated :
            highlighted ? Theme.surfaceRaised :
            Theme.surfaceBase
        ) : Theme.surfaceLowest
        border.color: root.enabled ? Theme.edgeStandard : Theme.edgeSubtle
        border.width: Theme.borderThin
    }

    // Icon
    Image {
        id: icon
        anchors.fill: parent
        anchors.margins: Theme.spacingXS
        source: root.iconSource
        fillMode: Image.PreserveAspectFit
        opacity: root.enabled ? 1.0 : 0.5
        smooth: true
    }

    // Mouse area for interaction
    MouseArea {
        id: mouseArea
        anchors.fill: parent
        enabled: root.enabled
        hoverEnabled: true
        pressAndHoldInterval: 500
        onEntered: { root.hovered = true; root.highlighted = true; }
        onExited: { root.hovered = false; root.highlighted = false; }
        onPressed: {
            root.pressedInternal = true;
            root.pressed = true;
        }
        onReleased: {
            root.pressedInternal = false;
            root.pressed = false;
        }
        onClicked: {
            if (root.enabled) {
                root.clicked()
            }
        }
    }

    // Signals
    signal clicked()
}