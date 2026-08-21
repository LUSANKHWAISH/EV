pragma Singleton
import QtQuick 2.15

QtObject {
    id: theme

    // Colors
    readonly property color background: "#0a0a0a"          // near-black
    readonly property color surface: "#1a1a1a"             // slightly lighter than background
    readonly property color surfaceRaised: "#2a2a2a"       // for elevated surfaces
    readonly property color surfaceOverlay: Qt.rgba(0, 0, 0, 0.3) // for overlays
    readonly property color textPrimary: "#ffffff"         // primary text
    readonly property color textSecondary: "#b0b0b0"       // secondary text
    readonly property color textMuted: "#707070"           // muted text
    readonly property color accent: "#00ff88"              // accent color (green)
    readonly property color success: "#00ff88"             // success
    readonly property color warning: "#ffb300"             // warning (amber)
    readonly property color error: "#ff3333"               // error (red)

    // Spacing (8dp base)
    readonly property int spacingXS: 4   // 4dp
    readonly property int spacingSM: 8   // 8dp
    readonly property int spacingMD: 16  // 16dp
    readonly property int spacingLG: 24  // 24dp
    readonly property int spacingXL: 32  // 32dp

    // Radius
    readonly property int radiusSM: 4
    readonly property int radiusMD: 8
    readonly property int radiusLG: 16

    // Motion durations (in milliseconds)
    readonly property int motionFast: 100
    readonly property int motionNormal: 200
    readonly property int motionSlow: 300
}