import QtQuick

Item {
    id: root
    required property var music
    property int bands: 110
    property real silenceFloor: 0.008
    property color needleColor: '#ffffff'
    property color needleBase: '#a6c8d4'
    property color peakColor: '#00f0ff'

    // Ballistic peak hold per needle
    property var peakHeights: []

    Timer {
        interval: 33
        running: true
        repeat: true
        onTriggered: {
            const raw = root.music ? (root.music.bands || []) : []
            if (raw.length === 0) return
            const count = root.bands
            let p = root.peakHeights || []
            if (p.length !== count) {
                p = new Array(count).fill(0)
            }
            for (let i = 0; i < count; ++i) {
                const idx = Math.min(raw.length - 1, Math.floor(i * raw.length / count))
                const val = Math.max(0, Math.min(1, Number(raw[idx] || 0)))
                if (val >= p[i]) {
                    p[i] = val
                } else {
                    p[i] = Math.max(0, p[i] - 0.012)
                }
            }
            root.peakHeights = p
            canvas.requestPaint()
        }
    }

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

            // Dark night-sky studio backdrop
            const bgGrad = c.createLinearGradient(0, 0, 0, height)
            bgGrad.addColorStop(0, '#0a1017')
            bgGrad.addColorStop(1, '#06090e')
            c.fillStyle = bgGrad
            c.fillRect(0, 0, width, height)

            const values = root.music ? (root.music.bands || []) : []
            const count = Math.max(16, root.bands)
            const padX = 14
            const padBottom = 16
            const availW = width - padX * 2
            const availH = height - padBottom - 12
            const baseY = height - padBottom
            const step = availW / count
            const needleW = Math.max(1.2, step * 0.55)

            // Draw baseline dots / tick line
            c.fillStyle = '#223847'
            for (let i = 0; i < count; ++i) {
                const bx = padX + i * step + step * 0.5
                c.fillRect(bx - 0.8, baseY + 3, 1.6, 1.6)
            }

            // Draw vertical needles (Image 5 aesthetic)
            for (let i = 0; i < count; ++i) {
                const index = Math.min(values.length - 1, Math.floor(i * values.length / count))
                const val = Math.max(0, Math.min(1, Number(values[index] || 0)))
                const peak = root.peakHeights ? Number(root.peakHeights[i] || 0) : val

                if (val < root.silenceFloor && peak < root.silenceFloor) {
                    continue
                }

                // Exponential height scaling for crisp dynamic needle reach
                const h = Math.min(availH, Math.pow(val, 0.9) * availH)
                const needleX = padX + i * step + (step - needleW) * 0.5

                if (h > 1.0) {
                    // Needle body gradient (pure white tip, gentle silver-cyan base)
                    const nGrad = c.createLinearGradient(0, baseY - h, 0, baseY)
                    nGrad.addColorStop(0, '#ffffff')
                    nGrad.addColorStop(0.35, '#f0faff')
                    nGrad.addColorStop(1, 'rgba(166, 200, 212, 0.45)')

                    c.fillStyle = nGrad
                    c.fillRect(needleX, baseY - h, needleW, h)

                    // Sharp bright tip pixel
                    c.fillStyle = '#ffffff'
                    c.fillRect(needleX, baseY - h, needleW, Math.min(2.5, h))
                }

                // Peak hold marker point
                const peakH = Math.min(availH, Math.pow(peak, 0.9) * availH)
                if (peakH > h + 2.0) {
                    c.fillStyle = root.peakColor
                    c.fillRect(needleX, baseY - peakH, needleW, 1.8)
                }
            }

            // Subtle baseline separator line
            c.strokeStyle = '#1b2d39'
            c.lineWidth = 1
            c.beginPath()
            c.moveTo(padX, baseY)
            c.lineTo(width - padX, baseY)
            c.stroke()
        }
    }
}
