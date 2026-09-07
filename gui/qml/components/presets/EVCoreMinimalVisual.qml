import QtQuick 2.15
import "../../theme"

// ============================================================================
// E.V. CORE MINIMAL VISUAL PRESET (MINIMAL)
// ============================================================================
//
// Ultra-lightweight, high-elegance central intelligence visualization.
// Minimal GPU footprint: uses clean procedural vector elements without heavy
// multi-layer Canvas repaints or large 3D scene graphs.
// Pure presentation component — zero execution authority.
// ============================================================================

Item {
    id: root
    anchors.fill: parent

    // Host connection for synchronized state and animation clock
    property var host: parent

    // Common visual inputs
    property string stateText: host && host.stateText !== undefined ? host.stateText : "IDLE"
    property string visualMode: host && host.visualMode !== undefined ? host.visualMode : "STANDARD"
    property real energy: host && host.energy !== undefined ? host.energy : Theme.stateEnergy(stateText)
    property color stateTone: host && host.stateTone !== undefined ? host.stateTone : Theme.stateColor(stateText)
    property color displayTone: host && host.displayTone !== undefined ? host.displayTone : stateTone

    property real phase: host && host.phase !== undefined ? host.phase : 0.0
    property real pulse: host && host.pulse !== undefined ? host.pulse : ((Math.sin(phase) + 1.0) * 0.5)
    property real slowPulse: host && host.slowPulse !== undefined ? host.slowPulse : ((Math.sin(phase * 0.52) + 1.0) * 0.5)
    property real coreBreath: host && host.coreBreath !== undefined ? host.coreBreath : 1.0
    property real glowDrive: host && host.glowDrive !== undefined ? host.glowDrive : 0.58
    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0

    readonly property real baseRadius: Math.max(36.0, Math.min(width, height) * 0.12)

    // Center container
    Item {
        id: centerAnchor
        anchors.centerIn: parent
        width: root.baseRadius * 4
        height: width

        scale: root.coreBreath * (0.96 + root.slowPulse * 0.06)

        // Outer soft ambient halo
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 3.2
            height: width
            radius: width / 2
            color: root.displayTone
            opacity: 0.04 * root.glowDrive

            Behavior on opacity {
                NumberAnimation { duration: Theme.motionStandard }
            }
        }

        // Precision outer thin ring
        Rectangle {
            id: outerPrecisionRing
            anchors.centerIn: parent
            width: root.baseRadius * 2.4 + root.effectiveListenLevel * 16.0
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 1
            border.color: root.displayTone
            opacity: 0.25 + root.glowDrive * 0.20

            rotation: root.phase * 20.0
        }

        // Secondary counter-rotating dashed precision ring
        Rectangle {
            id: innerDashedRing
            anchors.centerIn: parent
            width: root.baseRadius * 1.85
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 1
            border.color: root.displayTone
            opacity: 0.18 + root.pulse * 0.12

            rotation: -root.phase * 35.0
        }

        // Luminous core nucleus
        Rectangle {
            id: nucleus
            anchors.centerIn: parent
            width: root.baseRadius * (0.65 + root.effectiveSpeechLevel * 0.15)
            height: width
            radius: width / 2
            color: root.displayTone
            opacity: 0.40 + root.glowDrive * 0.40

            // Inner glowing center
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.45
                height: width
                radius: width / 2
                color: "#FFFFFF"
                opacity: 0.85
            }
        }

        // Subtle orbiting point
        Rectangle {
            width: 4
            height: 4
            radius: 2
            color: "#FFFFFF"
            opacity: 0.70 + root.pulse * 0.30

            property real orbAngle: root.phase * 1.5
            property real orbRadius: root.baseRadius * 1.4

            x: parent.width / 2 + Math.cos(orbAngle) * orbRadius - 2
            y: parent.height / 2 + Math.sin(orbAngle) * orbRadius - 2
        }
    }
}
