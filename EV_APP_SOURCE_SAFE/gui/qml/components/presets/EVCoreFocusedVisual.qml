import QtQuick 2.15
import "../../theme"

// ============================================================================
// E.V. CORE FOCUSED VISUAL PRESET (FOCUSED)
// ============================================================================
//
// High-concentration geometric energy visualization.
// Concentrated hexagonal/reticle architecture with sharp contrast, crisp
// rotation indicators, and high cognitive visual precision.
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
    property real coreBreath: host && host.coreBreath !== undefined ? host.coreBreath : 1.0
    property real glowDrive: host && host.glowDrive !== undefined ? host.glowDrive : 0.58
    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0

    readonly property real baseRadius: Math.max(45.0, Math.min(width, height) * 0.16)

    // Center container
    Item {
        id: focusedCenter
        anchors.centerIn: parent
        width: root.baseRadius * 3.5
        height: width

        scale: root.coreBreath * (0.98 + root.pulse * 0.04)

        // Outer reticle boundary (diamond / square rotated 45 deg)
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 2.2 + root.effectiveListenLevel * 12.0
            height: width
            color: "transparent"
            border.width: 1
            border.color: root.displayTone
            opacity: 0.35 + root.glowDrive * 0.25
            rotation: root.phase * 15.0

            // 4 corner reticle accents
            Repeater {
                model: 4
                Rectangle {
                    width: 6
                    height: 6
                    color: root.displayTone
                    opacity: 0.8
                    x: (index % 2 === 0 ? 0 : parent.width - 6)
                    y: (index < 2 ? 0 : parent.height - 6)
                }
            }
        }

        // Inner counter-rotating geometric frame
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 1.6
            height: width
            color: "transparent"
            border.width: 1.5
            border.color: root.displayTone
            opacity: 0.45 + root.pulse * 0.20
            rotation: -root.phase * 25.0
        }

        // Precision crosshair lines
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 2.6
            height: 1
            color: root.displayTone
            opacity: 0.18 + root.glowDrive * 0.12
            rotation: 0
        }
        Rectangle {
            anchors.centerIn: parent
            width: 1
            height: root.baseRadius * 2.6
            color: root.displayTone
            opacity: 0.18 + root.glowDrive * 0.12
            rotation: 0
        }

        // Concentrated nucleus with sharp highlight
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * (0.50 + root.effectiveSpeechLevel * 0.10)
            height: width
            radius: 4
            color: root.displayTone
            opacity: 0.70 + root.glowDrive * 0.30
            rotation: root.phase * 45.0

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.5
                height: width
                color: "#FFFFFF"
                opacity: 0.95
            }
        }
    }
}
