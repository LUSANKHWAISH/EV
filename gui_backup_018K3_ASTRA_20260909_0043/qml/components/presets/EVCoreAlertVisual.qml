import QtQuick 2.15
import "../../theme"

// ============================================================================
// E.V. CORE ALERT VISUAL PRESET (ALERT)
// ============================================================================
//
// Elevated vigilance and urgency visualization.
// Features segmented orbital warning arcs, heightened breathing rate, and
// amber/warning color accents.
//
// NON-NEGOTIABLE SAFETY INVARIANT:
// This visual preset is purely presentational. It NEVER acts as an authorization
// signal. Authoritative human approval is solely governed by EVApprovalOverlay (z=100).
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

    // Infuse alert preset with warm warning/alert luminance when in standard or idle states
    property color alertAccentColor: (stateText === "AWAITING_APPROVAL" || stateText === "FAILED")
        ? Theme.stateColor(stateText)
        : Theme.luminousWarning

    property color displayTone: (host && host.displayTone !== undefined && stateText !== "IDLE")
        ? host.displayTone
        : alertAccentColor

    property real phase: host && host.phase !== undefined ? host.phase : 0.0
    property real pulse: host && host.pulse !== undefined ? host.pulse : ((Math.sin(phase) + 1.0) * 0.5)
    property real coreBreath: host && host.coreBreath !== undefined ? host.coreBreath : 1.0
    property real glowDrive: host && host.glowDrive !== undefined ? host.glowDrive : 0.75
    property real effectiveListenLevel: host && host.effectiveListenLevel !== undefined ? host.effectiveListenLevel : 0.0
    property real effectiveSpeechLevel: host && host.effectiveSpeechLevel !== undefined ? host.effectiveSpeechLevel : 0.0

    readonly property real baseRadius: Math.max(48.0, Math.min(width, height) * 0.17)

    Item {
        id: alertCenter
        anchors.centerIn: parent
        width: root.baseRadius * 3.8
        height: width

        scale: root.coreBreath * (0.95 + root.pulse * 0.08)

        // Outer warning pulse perimeter
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 2.8 + root.effectiveListenLevel * 14.0
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 1.5
            border.color: root.displayTone
            opacity: 0.35 + root.pulse * 0.30
        }

        // Dual segmented warning brackets (rotating)
        Item {
            anchors.fill: parent
            rotation: root.phase * 40.0

            // Bracket top-left
            Rectangle {
                width: 18
                height: 3
                color: root.displayTone
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: parent.width * 0.15
            }
            Rectangle {
                width: 3
                height: 18
                color: root.displayTone
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: parent.width * 0.15
            }

            // Bracket bottom-right
            Rectangle {
                width: 18
                height: 3
                color: root.displayTone
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: parent.width * 0.15
            }
            Rectangle {
                width: 3
                height: 18
                color: root.displayTone
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: parent.width * 0.15
            }
        }

        // Counter-rotating segmented inner ring
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * 1.9
            height: width
            radius: width / 2
            color: "transparent"
            border.width: 2
            border.color: root.displayTone
            opacity: 0.50 + root.glowDrive * 0.30
            rotation: -root.phase * 55.0
        }

        // High-energy central warning core
        Rectangle {
            anchors.centerIn: parent
            width: root.baseRadius * (0.60 + root.effectiveSpeechLevel * 0.15)
            height: width
            radius: width / 2
            color: root.displayTone
            opacity: 0.65 + root.pulse * 0.35

            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.45
                height: width
                radius: width / 2
                color: "#FFFFFF"
                opacity: 0.90
            }
        }
    }
}
