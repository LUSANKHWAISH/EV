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
    readonly property color stateColorListening: "#4fc3f7" // cyan (receptive)
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
    // Additional spacing tokens used in components
    readonly property int spacingLG: baseUnit * 3    // 24px (same as spacingS)
    readonly property int spacingMD: baseUnit * 2    // 16px (same as spacingXS)
    readonly property int spacingSM: baseUnit        // 8px (same as spacingXXS)

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
    function stateColor(state) {
        switch (state) {
        case EVState.IDLE: return stateColorIdle
        case EVState.LISTENING: return stateColorListening
        case EVState.PLANNING: return stateColorPlanning
        case EVState.AWAITING_APPROVAL: return stateColorAwaitingApproval
        case EVState.EXECUTING: return stateColorExecuting
        case EVState.VERIFYING: return stateColorVerifying
        case EVState.RECOVERING: return stateColorRecovering
        case EVState.SPEAKING: return stateColorSpeaking
        case EVState.SUCCESS: return stateColorSuccess
        case EVState.FAILED: return stateColorFailed
        case EVState.STOPPED: return stateColorStopped
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
        switch (state) {
        case EVState.IDLE: return 0.1
        case EVState.LISTENING: return 0.3
        case EVState.PLANNING: return 0.5
        case EVState.AWAITING_APPROVAL: return 0.7
        case EVState.EXECUTING: return 0.9
        case EVState.VERIFYING: return 0.6
        case EVState.RECOVERING: return 0.4
        case EVState.SPEAKING: return 0.8
        case EVState.SUCCESS: return 0.2
        case EVState.FAILED: return 0.5
        case EVState.STOPPED: return 0.0
        default: return 0.0
        }
    }

    function statePulseDuration(state) {
        // Returns a suggested pulse duration for state visualization
        switch (state) {
        case EVState.LISTENING: return motionAmbient
        case EVState.SPEAKING: return motionDeliberate
        case EVState.VERIFYING: return motionStandard
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
}