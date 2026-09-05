pragma Singleton
import QtQuick 2.15

QtObject {
    id: theme

    // ==================================
    // COLOR SYSTEM
    // ==================================
    // Spatial foundation (near-black with subtle temperature)
    readonly property color backgroundVoid: "#050505"      // deepest space
    readonly property color backgroundDeep: "#0a0a0a"      // primary background
    readonly property color backgroundBase: "#0f0f0f"      // elevated backgrounds

    // Surface system (luminosity layers)
    readonly property color surfaceLowest: "#1a1a1a"       // lowest surface
    readonly property color surfaceLow: "#212121"          // low surface
    readonly property color surfaceBase: "#2a2a2a"         // base surface
    readonly property color surfaceRaised: "#333333"       // raised surface
    readonly property color surfaceElevated: "#3c3c3c"     // elevated surface

    // Edge system (subtle delineation)
    readonly property color edgeSubtle: "#424242"          // subtle hairline
    readonly property color edgeStandard: "#4a4a4a"        // standard edge
    readonly property color edgeActive: "#555555"          // active/interactive edge

    // Text system (opacity hierarchy)
    readonly property color textPrimary: Qt.rgba(1.0, 1.0, 1.0, 0.95)   // primary
    readonly property color textSecondary: Qt.rgba(1.0, 1.0, 1.0, 0.70) // secondary
    readonly property color textTertiary: Qt.rgba(1.0, 1.0, 1.0, 0.40)  // tertiary
    readonly property color textDisabled: Qt.rgba(1.0, 1.0, 1.0, 0.20)  // disabled

    // Luminous system (rare, purposeful emission)
    readonly property color luminousPrimary: "#00ff88"     // primary accent (green-cyan)
    readonly property color luminousSecondary: "#88ff00"   // secondary accent (yellow-green)
    readonly property color luminousWarning: "#ffb300"     // warning (amber)
    readonly property color luminousCritical: "#ff3333"    // critical (red)

    // State-specific colors (for identity beyond just color)
    readonly property color stateColorIdle: "#64b5f6"      // blue (calm)
    readonly property color stateColorVerifyingWake: "#80deea" // teal (receptive evaluation)
    readonly property color stateColorListening: "#4fc3f7" // cyan (receptive)
    readonly property color stateColorTranscribing: "#b39ddb"  // soft violet (speech inference)
    readonly property color stateColorProcessing: "#81c784"    // green (action cognition)
    readonly property color stateColorPlanning: "#9575cd"  // purple (cognition)
    readonly property color stateColorAwaitingApproval: "#ffb74d" // amber (tension)
    readonly property color stateColorExecuting: "#81c784" // green (action)
    readonly property color stateColorVerifying: "#fff176" // yellow (analysis)
    readonly property color stateColorRecovering: "#e57373" // red (reconstruction)
    readonly property color stateColorSpeaking: "#ffffff"  // white (expression)
    readonly property color stateColorSuccess: "#a5d6a7"   // green (resolved)
    readonly property color stateColorFailed: "#ef9a9a"    // red (controlled)
    readonly property color stateColorStopped: "#90a4ae"   // blue-gray (dormant)

    // ==================================
    // TYPOGRAPHY SYSTEM
    // ==================================
    // Font families (using system fonts for reliability)
    readonly property string fontFamily: "Segoe UI, system-ui, sans-serif"
    readonly property string fontFamilyMono: "Consolas, 'Courier New', monospace"

    // Font sizes (in points, scalable via DPI)
    readonly property int fontSizeDisplay: 48
    readonly property int fontSizeTitle: 32
    readonly property int fontSizeSection: 24
    readonly property int fontSizeBody: 16
    readonly property int fontSizeBodySmall: 14
    readonly property int fontSizeLabel: 12
    readonly property int fontSizeLabelSmall: 10
    readonly property int fontSizeNumeric: 18
    readonly property int fontSizeMono: 12

    // Font weights
    readonly property int fontWeightLight: 300
    readonly property int fontWeightRegular: 400
    readonly property int fontWeightMedium: 500
    readonly property int fontWeightSemibold: 600
    readonly property int fontWeightBold: 700

    // Letter spacing (tracking)
    readonly property real letterSpacingTight: -0.5
    readonly property real letterSpacingNormal: 0
    readonly property real letterSpacingWide: 0.5
    readonly property real letterSpacingEmphasis: 0.85

    // Line height
    readonly property real lineHeightTight: 1.2
    readonly property real lineHeightNormal: 1.4
    readonly property real lineHeightLoose: 1.6

    // ==================================
    // GEOMETRY / SPACING SYSTEM
    // ==================================
    // Base unit (8px) - scalable
    readonly property int baseUnit: 8

    // Spacing multiples
    readonly property int spacingXXXS: baseUnit / 2   // 4px
    readonly property int spacingXXS: baseUnit       // 8px
    readonly property int spacingXS: baseUnit * 2    // 16px
    readonly property int spacingS: baseUnit * 3     // 24px
    readonly property int spacingM: baseUnit * 4     // 32px
    readonly property int spacingL: baseUnit * 5     // 40px
    readonly property int spacingXL: baseUnit * 6    // 48px
    readonly property int spacingXXL: baseUnit * 8   // 64px
    readonly property int spacingXXXL: baseUnit * 10 // 80px
    // Compatibility aliases. New/updated components use the canonical scale above.
    readonly property int spacingLG: spacingS
    readonly property int spacingMD: spacingXS
    readonly property int spacingSM: spacingXXS

    // Radii (restrained, engineering)
    readonly property int radiusNone: 0
    readonly property int radiusXS: baseUnit / 2     // 4px
    readonly property int radiusS: baseUnit         // 8px
    readonly property int radiusM: baseUnit * 2     // 16px
    readonly property int radiusL: baseUnit * 3     // 24px
    readonly property int radiusXL: baseUnit * 4    // 32px

    // Border widths
    readonly property real hairline: 0.5   // actual hairline (device-dependent)
    readonly property int borderThin: 1
    readonly property int borderStandard: 2
    readonly property int borderThick: 3

    // Core ring thickness for intelligence components
    readonly property real coreRingThickness: 2

    // Window / chrome geometry
    readonly property int windowDefaultWidth: 1280
    readonly property int windowDefaultHeight: 720
    readonly property int windowMinimumWidth: 800
    readonly property int windowMinimumHeight: 600
    readonly property int stageCompactWidth: 900
    readonly property int stageCompactHeight: 620
    readonly property int topBarHeight: baseUnit * 6
    readonly property int windowControlWidth: baseUnit * 5
    readonly property int windowControlHeight: baseUnit * 4
    readonly property int windowResizeEdgeSize: 6
    readonly property int windowResizeCornerSize: 10

    // Opacity / emphasis hierarchy
    readonly property real opacityEmphasis: 0.88
    readonly property real opacitySignal: 0.86
    readonly property real opacityStandard: 0.72
    readonly property real opacityMuted: 0.62
    readonly property real opacitySubtle: 0.50

    // ==================================
    // MOTION SYSTEM
    // ==================================
    // Duration (milliseconds)
    readonly property int motionInstant: 0
    readonly property int motionMicro: 50
    readonly property int motionFast: 100
    readonly property int motionStandard: 200
    readonly property int motionDeliberate: 350
    readonly property int motionCinematic: 600
    readonly property int motionAmbient: 1200

    // Easing curves (for motion intent)
    readonly property int easingLinear: Easing.Linear
    readonly property int easingStandard: Easing.InOutQuad
    readonly property int easingDeliberate: Easing.InOutCubic
    readonly property int easingCinematic: Easing.InOutQuart
    readonly property int easingAmbient: Easing.InOutQuint

    // ==================================
    // DEPTH / LUMINANCE SYSTEM
    // ==================================
    // Luminance levels (for subtle emission)
    readonly property real luminanceNone: 0.0
    readonly property real luminanceSubtle: 0.05
    readonly property real luminanceFocused: 0.15
    readonly property real luminanceActive: 0.25
    readonly property real luminanceCritical: 0.35

    // ==================================
    // STATE IDENTITY SYSTEM
    // ==================================
    // Functions to map state to identity properties
    // State is expected to be a string from guiBridge.currentState
    function stateColor(state) {
        if (!state) return textPrimary
        switch (state) {
        case "IDLE": return stateColorIdle
        case "VERIFYING_WAKE": return stateColorVerifyingWake
        case "LISTENING": return stateColorListening
        case "TRANSCRIBING": return stateColorTranscribing
        case "PROCESSING": return stateColorProcessing
        case "PLANNING": return stateColorPlanning
        case "AWAITING_APPROVAL": return stateColorAwaitingApproval
        case "EXECUTING": return stateColorExecuting
        case "VERIFYING": return stateColorVerifying
        case "RECOVERING": return stateColorRecovering
        case "SPEAKING": return stateColorSpeaking
        case "SUCCESS": return stateColorSuccess
        case "FAILED": return stateColorFailed
        case "STOPPED": return stateColorStopped
        default: return textPrimary
        }
    }

    function stateSecondaryColor(state) {
        // Returns a complementary or secondary luminance for the state
        var base = stateColor(state)
        // For simplicity, we return a muted version; could be more sophisticated
        return Qt.darker(base, 150)
    }

    function stateEnergy(state) {
        // Returns a value from 0.0 to 1.0 representing the energy/intensity of the state
        if (!state) return 0.0
        switch (state) {
        case "IDLE": return 0.1
        case "VERIFYING_WAKE": return 0.35
        case "LISTENING": return 0.3
        case "TRANSCRIBING": return 0.5
        case "PROCESSING": return 0.7
        case "PLANNING": return 0.5
        case "AWAITING_APPROVAL": return 0.7
        case "EXECUTING": return 0.9
        case "VERIFYING": return 0.6
        case "RECOVERING": return 0.4
        case "SPEAKING": return 0.8
        case "SUCCESS": return 0.2
        case "FAILED": return 0.5
        case "STOPPED": return 0.0
        default: return 0.0
        }
    }

    function statePulseDuration(state) {
        // Returns a suggested pulse duration for state visualization
        if (!state) return motionInstant
        switch (state) {
        case "VERIFYING_WAKE": return motionFast
        case "LISTENING": return motionAmbient
        case "TRANSCRIBING": return motionStandard
        case "PROCESSING": return motionDeliberate
        case "SPEAKING": return motionDeliberate
        case "VERIFYING": return motionStandard
        default: return motionInstant
        }
    }

    // ==================================
    // HELPER FUNCTIONS
    // ==================================
    // Convenience for getting a color with opacity
    function colorWithOpacity(baseColor, opacity) {
        return Qt.rgba(
            red(baseColor),
            green(baseColor),
            blue(baseColor),
            opacity
        )
    }

    // Convenience for getting a lighter/darker color
    function tintColor(baseColor, factor) {
        // factor > 1 for lighter, < 1 for darker (simple approach)
        return Qt.lighter(baseColor, factor * 100)
    }

    // ==================================
    // EXPERIENCE MODE VISUAL MAPPINGS
    // ==================================
    function experienceModeColor(mode) {
        if (!mode) return luminousPrimary
        switch (mode) {
        case "STANDARD":  return stateColorIdle          // calm blue
        case "AI":        return luminousPrimary          // green-cyan (intelligence)
        case "WORK":      return stateColorProcessing     // green (productivity)
        case "MUSIC":     return stateColorTranscribing   // soft violet (creative)
        case "SYSTEM":    return stateColorVerifying       // yellow (diagnostics)
        case "APPROVAL":  return stateColorAwaitingApproval // amber (decision)
        case "SLEEP":     return stateColorStopped        // blue-gray (dormant)
        default:          return luminousPrimary
        }
    }

    function experienceModeGlyph(mode) {
        // Text-only glyphs for experience mode indicators (no icon fonts)
        if (!mode) return "◆"
        switch (mode) {
        case "STANDARD":  return "◆"   // diamond — default
        case "AI":        return "◈"   // diamond with dot — intelligence
        case "WORK":      return "▣"   // filled square — structured
        case "MUSIC":     return "♪"   // eighth note — audio
        case "SYSTEM":    return "⚙"   // gear — diagnostics
        case "APPROVAL":  return "⚑"   // flag — attention
        case "SLEEP":     return "◇"   // empty diamond — minimal
        default:          return "◆"
        }
    }

    // ==================================
    // STYLE PRESET VISUAL MAPPINGS
    // ==================================
    function stylePresetOpacity(preset) {
        // Ambient opacity multiplier per preset
        if (!preset) return 1.0
        switch (preset) {
        case "EV_CORE":  return 1.0    // full flagship detail
        case "MINIMAL":  return 0.6    // reduced density
        case "AMBIENT":  return 0.8    // atmospheric
        case "FOCUSED":  return 1.0    // sharp and bright
        case "ALERT":    return 1.0    // elevated urgency
        default:         return 1.0
        }
    }

    function stylePresetEnergy(preset) {
        // Energy/intensity multiplier per preset
        if (!preset) return 1.0
        switch (preset) {
        case "EV_CORE":  return 1.0    // standard energy
        case "MINIMAL":  return 0.4    // quiet
        case "AMBIENT":  return 0.6    // soft
        case "FOCUSED":  return 1.2    // amplified
        case "ALERT":    return 1.4    // urgent
        default:         return 1.0
        }
    }
}
