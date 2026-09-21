import QtQuick

Item {
    id: root
    required property var music
    property color accent: '#e6f0e8'
    property color secondary: '#83c3c2'

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
            c.fillStyle = '#0b1820'
            c.fillRect(0, 0, width, height)
            c.strokeStyle = '#1a3039'
            c.lineWidth = 1
            c.beginPath(); c.moveTo(0, height - 1); c.lineTo(width, height - 1); c.stroke()
            const values = root.music.bands || []
            if (values.length < 2) return
            function drawTrace(color, offset) {
                c.strokeStyle = color
                c.lineWidth = 1.4
                c.beginPath()
                for (let i = 0; i < values.length; ++i) {
                    const prev = Number(values[Math.max(0, i - 1)] || 0)
                    const next = Number(values[Math.min(values.length - 1, i + 1)] || 0)
                    const value = Math.max(0, Math.min(1, (prev + Number(values[i] || 0) + next) / 3))
                    const x = i * width / (values.length - 1)
                    const y = height - 4 - Math.min(height - 8, value * (height - 8)) + offset
                    if (i === 0) c.moveTo(x, y); else c.lineTo(x, y)
                }
                c.stroke()
            }
            drawTrace(root.accent, 0)
            if (Number(root.music.right || 0) > 0.001)
                drawTrace(root.secondary, 2)
        }
    }
}
