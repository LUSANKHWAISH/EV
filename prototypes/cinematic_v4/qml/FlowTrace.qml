import QtQuick

Item {
    id: root
    required property var music
    property color accent: '#00f0ff'
    property color peakColor: '#2de2d0'
    property color baseColor: '#d6e6ea'
    property color glowColor: '#00c8e6'

    Canvas {
        id: canvas
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        Connections {
            target: root.music
            function onAnalysisChanged() { canvas.requestPaint() }
        }
        onPaint: {
            const c = getContext('2d')
            c.reset()

            // Dark rich studio background
            const bgGradient = c.createLinearGradient(0, 0, 0, height)
            bgGradient.addColorStop(0, '#0a1017')
            bgGradient.addColorStop(1, '#060a0f')
            c.fillStyle = bgGradient
            c.fillRect(0, 0, width, height)

            // Subtle horizontal baseline with fade-out at edges
            const baseGrad = c.createLinearGradient(0, 0, width, 0)
            baseGrad.addColorStop(0, 'rgba(30, 48, 60, 0)')
            baseGrad.addColorStop(0.1, 'rgba(30, 48, 60, 0.7)')
            baseGrad.addColorStop(0.9, 'rgba(30, 48, 60, 0.7)')
            baseGrad.addColorStop(1, 'rgba(30, 48, 60, 0)')
            c.strokeStyle = baseGrad
            c.lineWidth = 1
            const baseY = height - 12
            c.beginPath()
            c.moveTo(0, baseY)
            c.lineTo(width, baseY)
            c.stroke()

            const rawValues = root.music ? (root.music.bands || []) : []
            if (rawValues.length < 2) return

            // Smooth values with 5-point Gaussian-weighted window for organic fluid curve
            const n = rawValues.length
            const pts = []
            const padX = width * 0.04
            const plotW = width - padX * 2
            const maxH = height - 28

            for (let i = 0; i < n; ++i) {
                let sum = 0
                let wSum = 0
                for (let k = -2; k <= 2; ++k) {
                    const idx = Math.max(0, Math.min(n - 1, i + k))
                    const weight = k === 0 ? 0.38 : (Math.abs(k) === 1 ? 0.24 : 0.07)
                    sum += Number(rawValues[idx] || 0) * weight
                    wSum += weight
                }
                const val = Math.max(0, Math.min(1, sum / wSum))
                const x = padX + (i / (n - 1)) * plotW
                const y = baseY - Math.min(maxH, Math.pow(val, 0.85) * maxH)
                pts.push({ x: x, y: y, val: val })
            }

            // Build smooth Bezier path
            function buildCurvePath() {
                c.beginPath()
                c.moveTo(0, baseY)
                c.lineTo(pts[0].x, pts[0].y)
                for (let i = 0; i < pts.length - 1; ++i) {
                    const curr = pts[i]
                    const next = pts[i + 1]
                    const midX = (curr.x + next.x) * 0.5
                    const midY = (curr.y + next.y) * 0.5
                    c.quadraticCurveTo(curr.x, curr.y, midX, midY)
                }
                const last = pts[pts.length - 1]
                c.lineTo(last.x, last.y)
                c.lineTo(width, baseY)
            }

            // Pass 1: Translucent underfill (gradient down to baseline)
            buildCurvePath()
            c.lineTo(width, baseY)
            c.lineTo(0, baseY)
            c.closePath()
            const fillGrad = c.createLinearGradient(0, height * 0.15, 0, baseY)
            fillGrad.addColorStop(0, 'rgba(0, 240, 255, 0.22)')
            fillGrad.addColorStop(0.45, 'rgba(45, 226, 208, 0.09)')
            fillGrad.addColorStop(1, 'rgba(10, 24, 33, 0.0)')
            c.fillStyle = fillGrad
            c.fill()

            // Pass 2: Diffused outer glow stroke
            buildCurvePath()
            c.strokeStyle = 'rgba(0, 220, 255, 0.28)'
            c.lineWidth = 7.5
            c.stroke()

            // Pass 3: Intermediate glow stroke
            buildCurvePath()
            c.strokeStyle = 'rgba(45, 226, 208, 0.55)'
            c.lineWidth = 3.6
            c.stroke()

            // Pass 4: Sharp luminous foreground curve with multi-stop horizontal gradient
            const strokeGrad = c.createLinearGradient(0, 0, width, 0)
            strokeGrad.addColorStop(0, 'rgba(214, 230, 234, 0.7)')
            strokeGrad.addColorStop(0.18, '#ffffff')
            strokeGrad.addColorStop(0.35, '#2de2d0')
            strokeGrad.addColorStop(0.60, '#00f0ff')
            strokeGrad.addColorStop(0.82, '#ffffff')
            strokeGrad.addColorStop(1, 'rgba(214, 230, 234, 0.7)')

            buildCurvePath()
            c.strokeStyle = strokeGrad
            c.lineWidth = 2.0
            c.stroke()
        }
    }
}
