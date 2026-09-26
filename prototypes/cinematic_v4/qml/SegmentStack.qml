import QtQuick

Item {
    id: root
    required property var music
    property int bands: 18
    property int segments: 20
    property color accentLit: '#ffffff'
    property color accentPeak: '#00f0ff'
    property color cellUnlit: '#101a24'
    property color cellBorder: '#182734'

    // Ballistic peak hold per column
    property var peakCells: []

    Timer {
        interval: 35
        running: true
        repeat: true
        onTriggered: {
            const raw = root.music ? (root.music.bands || []) : []
            if (raw.length === 0) return
            const count = root.bands
            let p = root.peakCells || []
            if (p.length !== count) {
                p = new Array(count).fill(0)
            }
            for (let i = 0; i < count; ++i) {
                const idx = Math.min(raw.length - 1, Math.floor(i * raw.length / count))
                const val = Math.max(0, Math.min(1, Number(raw[idx] || 0)))
                const lit = Math.round(Math.pow(val, 0.8) * root.segments)
                if (lit >= p[i]) {
                    p[i] = lit
                } else {
                    p[i] = Math.max(0, p[i] - 0.28)
                }
            }
            root.peakCells = p
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

            // Dark rich studio background
            const bgGrad = c.createLinearGradient(0, 0, 0, height)
            bgGrad.addColorStop(0, '#091219')
            bgGrad.addColorStop(1, '#05090e')
            c.fillStyle = bgGrad
            c.fillRect(0, 0, width, height)

            const values = root.music ? (root.music.bands || []) : []
            const count = Math.max(1, root.bands)
            const cells = Math.max(4, root.segments)

            // Padding and geometry (Reference 4 aesthetic)
            const padX = 14
            const padBottom = 16
            const padTop = 14
            const availW = width - padX * 2
            const availH = height - padBottom - padTop
            const colWidth = availW / count
            const colGap = Math.max(3, colWidth * 0.20)
            const barW = Math.max(4, colWidth - colGap)
            const cellGap = 2.0
            const cellH = Math.max(2, (availH - (cells - 1) * cellGap) / cells)

            // Render each ladder column
            for (let i = 0; i < count; ++i) {
                const index = Math.min(values.length - 1, Math.floor(i * values.length / count))
                const val = Math.max(0, Math.min(1, Number(values[index] || 0)))
                const litCount = Math.round(Math.pow(val, 0.8) * cells)
                const peakCell = root.peakCells ? Math.round(root.peakCells[i] || 0) : 0
                const colX = padX + i * colWidth + colGap * 0.5

                for (let j = 0; j < cells; ++j) {
                    const cellY = height - padBottom - (j + 1) * cellH - j * cellGap

                    if (j < litCount) {
                        // Lit segment (pure crisp white with subtle cyan highlight near ceiling)
                        const normJ = j / cells
                        if (normJ > 0.85) {
                            c.fillStyle = '#00f0ff'
                        } else if (normJ > 0.65) {
                            c.fillStyle = '#eaf8ff'
                        } else {
                            c.fillStyle = '#ffffff'
                        }
                        c.fillRect(colX, cellY, barW, cellH)
                    } else {
                        // Unlit segment structure
                        c.fillStyle = root.cellUnlit
                        c.fillRect(colX, cellY, barW, cellH)
                        c.strokeStyle = root.cellBorder
                        c.lineWidth = 0.8
                        c.strokeRect(colX, cellY, barW, cellH)
                    }
                }

                // Floating peak indicator segment
                if (peakCell > 0 && peakCell <= cells) {
                    const peakY = height - padBottom - peakCell * cellH - (peakCell - 1) * cellGap
                    c.fillStyle = '#00f0ff'
                    c.fillRect(colX, peakY, barW, Math.max(1.8, cellH * 0.7))
                }
            }

            // Baseline horizontal accent line (Reference 4)
            c.strokeStyle = '#223846'
            c.lineWidth = 1
            c.beginPath()
            c.moveTo(padX, height - padBottom + 4)
            c.lineTo(width - padX, height - padBottom + 4)
            c.stroke()
        }
    }
}
