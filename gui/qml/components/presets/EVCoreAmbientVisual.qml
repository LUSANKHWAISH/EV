import QtQuick 2.15
import "../../theme"

// ============================================================================
// E.V. CORE AMBIENT VISUAL PRESET (AMBIENT)
// ============================================================================
//
// Soft, atmospheric intelligence visualization.
// Features deep diffused gradients, calm harmonic breathing rhythms, and
// subtle glowing waves. Low contrast, low visual aggression.
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

    readonly property real auraRadius: Math.max(50.0, Math.min(width, height) * 0.22)

    function rgbaString(c, alphaValue) {
        return "rgba("
            + Math.round(c.r * 255) + ","
            + Math.round(c.g * 255) + ","
            + Math.round(c.b * 255) + ","
            + Math.max(0.0, Math.min(1.0, alphaValue))
            + ")"
    }

    // Single dedicated ambient Canvas for soft harmonic gradient rendering
    Canvas {
        id: ambientCanvas
        anchors.fill: parent
        antialiasing: true

        onPaint: {
            var ctx = getContext("2d")
            var cx = width * 0.5
            var cy = height * 0.5
            var baseR = root.auraRadius * root.coreBreath * (0.92 + root.slowPulse * 0.10)
            var tone = root.displayTone

            ctx.clearRect(0, 0, width, height)

            // 1. Broad atmospheric nebula glow
            var grad = ctx.createRadialGradient(cx, cy, baseR * 0.1, cx, cy, baseR * 2.1)
            grad.addColorStop(0.0, root.rgbaString(tone, 0.18 * root.glowDrive))
            grad.addColorStop(0.35, root.rgbaString(tone, 0.08 * root.glowDrive))
            grad.addColorStop(0.70, root.rgbaString(tone, 0.02 * root.glowDrive))
            grad.addColorStop(1.0, root.rgbaString(tone, 0.0))

            ctx.fillStyle = grad
            ctx.beginPath()
            ctx.arc(cx, cy, baseR * 2.1, 0, Math.PI * 2.0)
            ctx.fill()

            // 2. Concentric gentle harmonic wave circles
            for (var w = 1; w <= 3; ++w) {
                var waveProgress = ((root.phase * 0.25 + w * 0.33) % 1.0)
                var wr = baseR * (0.7 + waveProgress * 1.0 + root.effectiveListenLevel * 0.3)
                var wa = (1.0 - waveProgress) * (0.12 * root.glowDrive)

                ctx.lineWidth = Math.max(1.0, baseR * 0.010)
                ctx.strokeStyle = root.rgbaString(tone, wa)
                ctx.beginPath()
                ctx.arc(cx, cy, wr, 0, Math.PI * 2.0)
                ctx.stroke()
            }

            // 3. Central warm core
            var coreGrad = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 0.35)
            coreGrad.addColorStop(0.0, "rgba(255,255,255,0.70)")
            coreGrad.addColorStop(0.40, root.rgbaString(tone, 0.45 * root.glowDrive))
            coreGrad.addColorStop(1.0, root.rgbaString(tone, 0.0))

            ctx.fillStyle = coreGrad
            ctx.beginPath()
            ctx.arc(cx, cy, baseR * 0.35, 0, Math.PI * 2.0)
            ctx.fill()
        }
    }

    onPhaseChanged: ambientCanvas.requestPaint()
    onWidthChanged: ambientCanvas.requestPaint()
    onHeightChanged: ambientCanvas.requestPaint()
    onDisplayToneChanged: ambientCanvas.requestPaint()
    onStateTextChanged: ambientCanvas.requestPaint()
    onVisualModeChanged: ambientCanvas.requestPaint()

    Component.onCompleted: ambientCanvas.requestPaint()
}
