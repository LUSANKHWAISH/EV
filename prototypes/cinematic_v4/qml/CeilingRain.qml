import QtQuick

Item {
    id: root
    required property var music
    property int bands: 96
    property real silenceFloor: 0.012
    property color accent: '#f4d99b'
    property color shadow: '#81551e'

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
            const count = Math.max(1, root.bands)
            const step = width / count
            const gap = Math.min(2, Math.max(1, step * 0.18))
            const available = Math.max(0, height - 4)
            const gradient = c.createLinearGradient(0, 0, 0, available)
            gradient.addColorStop(0, root.accent)
            gradient.addColorStop(0.55, '#d99b36')
            gradient.addColorStop(1, root.shadow)
            c.fillStyle = gradient
            for (let i = 0; i < count; ++i) {
                const index = Math.min(values.length - 1, Math.floor(i * values.length / count))
                const value = Math.max(0, Math.min(1, Number(values[index] || 0)))
                const h = value > root.silenceFloor ? value * available : 0
                if (h > 0.5)
                    c.fillRect(i * step + gap * 0.5, 2, Math.max(1, step - gap), h)
            }
        }
    }
}
