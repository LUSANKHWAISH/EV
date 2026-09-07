import QtQuick 2.15
import "../theme"

// ============================================================================
// E.V. INTELLIGENCE CORE — VISUAL PRESET HOST & BEHAVIORAL INTERFACE
// ============================================================================
//
// Serves as the stable common behavioral interface and dynamic preset host
// for the E.V. Flagship UI (Phase 018-G).
//
// ARCHITECTURAL CONTRACT:
// 1. Common Interface: Exposes all state, animation clock, and energy metrics.
// 2. Dynamic Loading: Instantiates ONLY the active visual preset via QML Loader.
// 3. Resource Discipline: Inactive preset scene graphs/canvases are destroyed.
// 4. Zero Authority: Pure presentation container — zero execution capability.
// 5. Preserves EVFlagshipStage.qml compatibility without modifying protected files.
// ============================================================================

Item {
    id: root

    // ------------------------------------------------------------------------
    // Public State & Mode Properties
    // ------------------------------------------------------------------------
    property var state: null
    property string visualMode: "STANDARD"
    property string themeProfile: "EV_CORE"

    property string stateText:
        state === null || state === undefined || String(state).length === 0
        ? "IDLE"
        : String(state)

    property real energy: Theme.stateEnergy(root.stateText)
    property color stateTone: Theme.stateColor(root.stateText)

    // State boolean flags for presentation convenience
    property bool idle: stateText === "IDLE"
    property bool listening: stateText === "LISTENING"
    property bool planning: stateText === "PLANNING"
    property bool executing: stateText === "EXECUTING"
    property bool verifying: stateText === "VERIFYING"
    property bool awaiting: stateText === "AWAITING_APPROVAL"
    property bool speaking: stateText === "SPEAKING"
    property bool successful: stateText === "SUCCESS"
    property bool failed: stateText === "FAILED"
    property bool recovering: stateText === "RECOVERING"
    property bool stopped: stateText === "STOPPED"

    // Audio & Speech input levels
    property real audioLevel: 0.0
    property real speechLevel: 0.0

    // Master Animation Phase Clock
    property real phase: 0.0

    readonly property int motionCycle:
        root.executing ? 1500 :
        root.failed ? 1350 :
        root.verifying ? 1900 :
        root.speaking ? 1600 :
        root.planning ? 2200 :
        root.listening ? 1700 :
        root.recovering ? 2700 :
        root.awaiting ? 6200 :
        root.successful ? 2400 :
        5200

    readonly property real pulse:
        (Math.sin(root.phase) + 1.0) * 0.5

    readonly property real slowPulse:
        (Math.sin(root.phase * 0.52) + 1.0) * 0.5

    readonly property real drift:
        Math.sin(root.phase * 0.41)

    readonly property real counterDrift:
        Math.cos(root.phase * 0.37)

    // Master Phase Driver (single clock for all loaded visual presets)
    NumberAnimation {
        target: root
        property: "phase"
        from: 0.0
        to: Math.PI * 2.0
        duration: root.motionCycle
        loops: Animation.Infinite
        running: root.visible && !root.stopped
    }

    readonly property color displayTone:
        root.idle ? "#34E6E0" :
        root.listening ? "#8E6BFF" :
        root.planning ? "#FF9D3D" :
        root.speaking ? "#FFCF6B" :
        root.stateTone

    readonly property real syntheticListenLevel:
        root.listening
        ? 0.18 + root.pulse * 0.28
        : 0.0

    readonly property real syntheticSpeechLevel:
        root.speaking
        ? 0.16 + Math.max(0.0, Math.sin(root.phase * 3.0)) * 0.44
        : 0.0

    readonly property real effectiveListenLevel:
        root.listening
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.audioLevel > 0.01
                ? root.audioLevel
                : root.syntheticListenLevel
            )
        )
        : 0.0

    readonly property real effectiveSpeechLevel:
        root.speaking
        ? Math.max(
            0.0,
            Math.min(
                1.0,
                root.speechLevel > 0.01
                ? root.speechLevel
                : root.syntheticSpeechLevel
            )
        )
        : 0.0

    readonly property real motionGate:
        root.awaiting ? 0.06 : 1.0

    readonly property real coreBreath:
        root.idle ? 0.985 + root.slowPulse * 0.035 :
        root.listening ? 0.98 + root.effectiveListenLevel * 0.10 :
        root.speaking ? 0.99 + root.effectiveSpeechLevel * 0.08 :
        root.successful ? 1.055 :
        root.failed ? 0.96 + root.pulse * 0.025 :
        root.stopped ? 0.86 :
        1.0 + root.pulse * 0.022

    readonly property real glowDrive:
        root.stopped ? 0.05 :
        root.listening ? 0.70 + root.effectiveListenLevel * 0.52 :
        root.speaking ? 0.76 + root.effectiveSpeechLevel * 0.50 :
        root.planning ? 0.82 :
        root.executing ? 0.96 :
        root.verifying ? 0.92 :
        root.successful ? 1.10 :
        root.failed ? 0.68 :
        root.recovering ? 0.78 :
        root.awaiting ? 0.42 :
        0.58

    readonly property real satelliteSpeed:
        root.stopped ? 0.0 :
        root.awaiting ? 0.12 :
        root.executing ? 1.55 :
        root.planning ? 1.18 :
        root.verifying ? 0.92 :
        root.listening ? 0.68 + root.effectiveListenLevel * 0.22 :
        root.speaking ? 0.78 + root.effectiveSpeechLevel * 0.20 :
        root.failed ? 1.10 :
        root.recovering ? 0.48 :
        root.successful ? 0.42 :
        0.34

    readonly property real tracerOpacity:
        root.stopped ? 0.02 :
        root.awaiting ? 0.07 :
        root.executing ? 0.20 :
        root.planning ? 0.17 :
        root.verifying ? 0.16 :
        root.listening ? 0.14 + root.effectiveListenLevel * 0.05 :
        root.speaking ? 0.15 + root.effectiveSpeechLevel * 0.05 :
        root.failed ? 0.13 :
        0.10

    readonly property real auraRadius:
        Math.max(
            62.0,
            Math.min(root.width, root.height) * 0.185
        )

    readonly property real rearDepth:
        root.failed ? -66.0 + root.counterDrift * 5.0 :
        root.recovering ? -68.0 + root.pulse * 3.0 :
        -68.0

    readonly property real rearEnergyDepth:
        root.verifying ? -30.0 + root.drift * 5.0 :
        -34.0

    readonly property real chamberDepth:
        root.executing ? 22.0 :
        root.verifying ? 16.0 + root.drift * 7.0 :
        root.planning ? 17.0 + root.drift * 2.0 :
        16.0

    readonly property real nucleusDepth:
        root.executing ? 46.0 :
        root.verifying ? 40.0 + root.drift * 8.0 :
        root.speaking ? 40.0 + root.effectiveSpeechLevel * 5.0 :
        40.0

    readonly property real lensDepth:
        root.listening ? 66.0 + root.effectiveListenLevel * 7.0 :
        root.speaking ? 66.0 + root.effectiveSpeechLevel * 5.0 :
        root.successful ? 71.0 :
        66.0

    function rgbaString(c, alphaValue) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, alphaValue))
            + ")"
    }

    // ------------------------------------------------------------------------
    // Visual Preset Dynamic Loader
    // ------------------------------------------------------------------------
    // Maps themeProfile to the appropriate visual component.
    // Unloads old component tree immediately when switching presets,
    // avoiding duplicate View3D or Canvas resource consumption.
    readonly property string effectiveThemeProfile: {
        var p = (themeProfile || "").toString().trim().toUpperCase()
        if (p === "MINIMAL" || p === "AMBIENT" || p === "FOCUSED" || p === "ALERT" || p === "EV_CORE") {
            return p
        }
        return "EV_CORE"
    }

    readonly property var activeVisualItem: presetLoader.item
    readonly property bool hasActiveVisualItem: presetLoader.item !== null
    readonly property string activePresetSource: presetLoader.source.toString()

    function getPresetSource(profile) {
        switch (profile) {
        case "MINIMAL": return Qt.resolvedUrl("presets/EVCoreMinimalVisual.qml")
        case "AMBIENT": return Qt.resolvedUrl("presets/EVCoreAmbientVisual.qml")
        case "FOCUSED": return Qt.resolvedUrl("presets/EVCoreFocusedVisual.qml")
        case "ALERT":   return Qt.resolvedUrl("presets/EVCoreAlertVisual.qml")
        case "EV_CORE":
        default:        return Qt.resolvedUrl("presets/EVCoreFlagshipVisual.qml")
        }
    }

    Loader {
        id: presetLoader
        objectName: "presetLoader"
        anchors.fill: parent
        asynchronous: false
        source: root.getPresetSource(root.effectiveThemeProfile)

        onLoaded: {
            if (item && "host" in item) {
                item.host = root
            }
        }
    }
}
