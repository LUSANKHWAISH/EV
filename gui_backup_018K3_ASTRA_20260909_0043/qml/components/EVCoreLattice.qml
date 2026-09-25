
import QtQuick 2.15
import "../theme"

// EVCoreLattice - Sparse asymmetric cognitive topology.
// Connection weights create primary, secondary and ghost computation paths.
Item {
    id: root

    property real energy: 0.0
    property var state: null

    property var nodes: [
        [0.50, 0.07],
        [0.33, 0.16],
        [0.66, 0.19],
        [0.20, 0.30],
        [0.44, 0.33],
        [0.73, 0.34],
        [0.11, 0.51],
        [0.34, 0.52],
        [0.59, 0.47],
        [0.87, 0.54],
        [0.24, 0.70],
        [0.48, 0.64],
        [0.72, 0.72],
        [0.37, 0.87],
        [0.61, 0.84],
        [0.80, 0.22]
    ]

    // [nodeA, nodeB, weight]
    // 1.0 = primary cognition route
    // 0.65 = secondary
    // 0.35 = ghost structure
    property var connections: [
        [0, 1, 0.65],
        [0, 2, 1.00],

        [1, 3, 0.35],
        [1, 4, 1.00],

        [2, 4, 0.65],
        [2, 15, 0.35],
        [15, 5, 0.65],

        [3, 6, 0.35],
        [3, 7, 0.65],

        [4, 7, 1.00],
        [4, 8, 1.00],

        [5, 8, 0.65],
        [5, 9, 0.35],

        [6, 10, 0.35],

        [7, 10, 0.65],
        [7, 11, 1.00],

        [8, 11, 1.00],
        [8, 12, 0.65],

        [9, 12, 0.35],

        [10, 13, 0.35],

        [11, 13, 0.65],
        [11, 14, 1.00],

        [12, 14, 0.65],

        [4, 11, 1.00]
    ]

    function nodeX(i) {
        return nodes[i][0] * width
    }

    function nodeY(i) {
        return nodes[i][1] * height
    }

    Repeater {
        model: root.connections.length

        Rectangle {
            property var edge: root.connections[index]

            property real x1: root.nodeX(edge[0])
            property real y1: root.nodeY(edge[0])
            property real x2: root.nodeX(edge[1])
            property real y2: root.nodeY(edge[1])

            property real weight: edge[2]

            property real dx: x2 - x1
            property real dy: y2 - y1
            property real distance: Math.sqrt(dx * dx + dy * dy)

            x: x1
            y: y1 - height / 2

            width: distance

            height:
                weight >= 0.9
                ? Math.max(1.5, Math.min(root.width, root.height) * 0.0034)
                : Math.max(1, Math.min(root.width, root.height) * 0.0022)

            color:
                weight >= 0.9
                ? Theme.stateColor(root.state)
                : Theme.luminousPrimary

            opacity:
                (0.07 + root.energy * 0.20)
                + weight * (0.11 + root.energy * 0.18)

            transformOrigin: Item.Left
            rotation: Math.atan2(dy, dx) * 180 / Math.PI

            Behavior on opacity {
                NumberAnimation { duration: Theme.motionStandard }
            }
        }
    }

    Repeater {
        model: root.nodes.length

        Rectangle {
            property bool major:
                index === 0 || index === 4 || index === 7 ||
                index === 8 || index === 11 || index === 14

            property bool energized:
                root.energy > ((index % 5) * 0.15)

            property real nodeSize:
                major
                ? Math.max(4, Math.min(root.width, root.height) * 0.017)
                : Math.max(2.5, Math.min(root.width, root.height) * 0.010)

            width: nodeSize
            height: nodeSize
            radius: width / 2

            x: root.nodeX(index) - width / 2
            y: root.nodeY(index) - height / 2

            color:
                major || energized
                ? Theme.stateColor(root.state)
                : Theme.luminousPrimary

            opacity:
                major
                ? 0.56 + root.energy * 0.27
                : energized
                    ? 0.40 + root.energy * 0.24
                    : 0.15 + root.energy * 0.14

            scale:
                major
                ? 1.08 + root.energy * 0.18
                : energized ? 1.0 : 0.82

            Behavior on scale {
                NumberAnimation { duration: Theme.motionStandard }
            }

            Behavior on opacity {
                NumberAnimation { duration: Theme.motionStandard }
            }
        }
    }
}
