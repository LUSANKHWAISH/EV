import QtQuick

Item {
    id: root
    required property var music
    property int bands: 10
    property int segments: 12
    property color accent: '#dfb05d'

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
            const values = root.music.bands || []
            const count = Math.max(1, root.bands)
            const cells = Math.max(3, root.segments)
            const step = width / count
            const gap = Math.min(5, Math.max(2, step * 0.12))
            const cellGap = 2
            for (let i = 0; i < count; ++i) {
                const index = Math.min(values.length - 1, Math.floor(i * values.length / count))
                const value = Math.max(0, Math.min(1, Number(values[index] || 0)))
                const lit = Math.round(value * cells)
                const cellHeight = Math.max(2, (height - (cells - 1) * cellGap) / cells)
                for (let j = 0; j < cells; ++j) {
                    const y = height - (j + 1) * cellHeight - j * cellGap
                    c.fillStyle = j < lit ? root.accent : '#1b3039'
                    c.fillRect(i * step + gap * 0.5, y, Math.max(1, step - gap), cellHeight)
                }
                if (lit > 0) {
                    c.fillStyle = '#fff0bc'
                    c.fillRect(i * step + gap * 0.5, height - lit * (cellHeight + cellGap), Math.max(1, step - gap), 1)
                }
            }
        }
    }
}
