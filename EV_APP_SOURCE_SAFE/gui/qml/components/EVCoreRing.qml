import QtQuick 2.15
import "../theme"

// EVCoreRing - Sparse partial precision instrumentation arc.
// It is deliberately secondary to the main E.V. intelligence nucleus.
Item {
    id: root

    property real thickness: Theme.coreRingThickness
    property real gap: 0.65
    property real baseOpacity: 0.45
    property int segmentCount: 32
    property real startAngle: 0
    property real endAngle: 360 * (1 - gap)

    Repeater {
        model: root.segmentCount

        Rectangle {
            property real angle: index * 360 / root.segmentCount
            property real orbitRadius:
                Math.max(0, Math.min(root.width, root.height) / 2 - height * 2)

            visible: angle >= root.startAngle && angle <= root.endAngle

            width: Math.max(3, root.thickness * 2.4)
            height: Math.max(1, root.thickness * 0.8)
            radius: height / 2

            color: Theme.luminousPrimary
            opacity: root.baseOpacity * (index % 3 === 0 ? 1.0 : 0.68)

            x: root.width / 2 - width / 2
               + orbitRadius * Math.cos(angle * Math.PI / 180)

            y: root.height / 2 - height / 2
               + orbitRadius * Math.sin(angle * Math.PI / 180)

            // Tangential segment orientation.
            rotation: angle + 90
        }
    }
}
