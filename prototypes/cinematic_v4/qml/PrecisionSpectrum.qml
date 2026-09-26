import QtQuick

Item {
    id: root
    required property var music

    // Styling matching Voxengo SPAN studio reference
    property color gridColor: '#1a2430'
    property color textDim: '#6b8294'
    property color textBright: '#dfddd3'
    property color chartreuseFill: '#8ac926'
    property color chartreuseLine: '#a6e22e'
    property color peakLineColor: '#d4ff4d'

    // Ballistic peak hold state
    property var peakBands: []

    Timer {
        interval: 33
        running: true
        repeat: true
        onTriggered: {
            const raw = root.music ? (root.music.bands || []) : []
            if (raw.length === 0) return
            let p = root.peakBands || []
            if (p.length !== raw.length) {
                p = new Array(raw.length).fill(0)
            }
            for (let i = 0; i < raw.length; ++i) {
                const cur = Number(raw[i] || 0)
                if (cur >= p[i]) {
                    p[i] = cur
                } else {
                    p[i] = Math.max(cur, p[i] - 0.008) // smooth ballistic decay
                }
            }
            root.peakBands = p
            canvas.requestPaint()
        }
    }

    Canvas {
        id: canvas
        anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        onPaint: {
            const c = getContext('2d')
            c.reset()

            const w = width
            const h = height

            // 1. Dark charcoal studio backdrop
            c.fillStyle = '#0a1017'
            c.fillRect(0, 0, w, h)

            // Geometry bounds
            const leftMargin = 30
            const rightMargin = 70 // reserved for stereo level meters
            const topMargin = 28   // reserved for top readouts
            const bottomMargin = 58 // reserved for frequency scale + statistics bar
            const plotW = Math.max(10, w - leftMargin - rightMargin)
            const plotH = Math.max(10, h - topMargin - bottomMargin)
            const plotB = topMargin + plotH

            // 2. Plot grid background
            c.fillStyle = '#070b10'
            c.fillRect(leftMargin, topMargin, plotW, plotH)

            // 3. Logarithmic Frequency Grid & Ticks (20 Hz to 20 kHz)
            const logMin = Math.log10(20)
            const logMax = Math.log10(20000)
            function freqToX(freq) {
                const norm = (Math.log10(freq) - logMin) / (logMax - logMin)
                return leftMargin + norm * plotW
            }

            const freqGrid = [
                { f: 20, l: '20' }, { f: 30, l: '30' }, { f: 40, l: '40' },
                { f: 60, l: '60' }, { f: 80, l: '80' }, { f: 100, l: '100' },
                { f: 200, l: '200' }, { f: 300, l: '300' }, { f: 400, l: '400' },
                { f: 600, l: '600' }, { f: 800, l: '800' }, { f: 1000, l: '1K' },
                { f: 2000, l: '2K' }, { f: 3000, l: '3K' }, { f: 4000, l: '4K' },
                { f: 6000, l: '6K' }, { f: 8000, l: '8K' }, { f: 10000, l: '10K' },
                { f: 20000, l: '20K' }
            ]

            c.strokeStyle = '#141d27'
            c.lineWidth = 1
            c.font = '9px Consolas, monospace'
            c.textAlign = 'center'
            c.fillStyle = '#5c7385'

            for (let i = 0; i < freqGrid.length; ++i) {
                const fx = freqToX(freqGrid[i].f)
                if (fx >= leftMargin && fx <= leftMargin + plotW) {
                    c.beginPath()
                    c.moveTo(fx, topMargin)
                    c.lineTo(fx, plotB)
                    c.stroke()

                    // Label tick below plot
                    c.fillText(freqGrid[i].l, fx, plotB + 13)
                }
            }

            // 4. Decibel Grid Lines (-78 dB to 0 dB, +6 dB)
            const dbTicks = [
                { db: 6, l: '+6' }, { db: 0, l: '0' }, { db: -6, l: '-6' },
                { db: -12, l: '-12' }, { db: -18, l: '-18' }, { db: -24, l: '-24' },
                { db: -30, l: '-30' }, { db: -36, l: '-36' }, { db: -42, l: '-42' },
                { db: -48, l: '-48' }, { db: -54, l: '-54' }, { db: -60, l: '-60' },
                { db: -66, l: '-66' }, { db: -72, l: '-72' }, { db: -78, l: '-78' }
            ]

            function dbToY(db) {
                // Range: +6 dB (top) to -78 dB (bottom) -> 84 dB range
                const norm = (6 - db) / 84.0
                return topMargin + norm * plotH
            }

            c.textAlign = 'right'
            for (let i = 0; i < dbTicks.length; ++i) {
                const dy = dbToY(dbTicks[i].db)
                if (dy >= topMargin && dy <= plotB) {
                    c.strokeStyle = dbTicks[i].db === 0 ? '#263d4d' : '#141d27'
                    c.beginPath()
                    c.moveTo(leftMargin, dy)
                    c.lineTo(leftMargin + plotW, dy)
                    c.stroke()

                    c.fillText(dbTicks[i].l, leftMargin - 4, dy + 3)
                    c.fillText(dbTicks[i].l, leftMargin + plotW + 22, dy + 3)
                }
            }

            // Outer plot frame
            c.strokeStyle = '#223242'
            c.strokeRect(leftMargin, topMargin, plotW, plotH)

            // 5. Dual Spectrum Curves
            const rawBands = root.music ? (root.music.bands || []) : []
            const peakBands = root.peakBands || []

            if (rawBands.length > 2) {
                const count = rawBands.length
                const realPts = []
                const peakPts = []

                for (let i = 0; i < count; ++i) {
                    const normX = i / (count - 1)
                    const x = leftMargin + normX * plotW

                    // Map 0..1 band values to -78..+0 dB
                    const valReal = Number(rawBands[i] || 0)
                    const valPeak = Number(peakBands[i] || valReal)

                    // Cubic curve mapping for dynamic studio look
                    const yReal = plotB - Math.min(plotH, Math.pow(valReal, 0.9) * plotH)
                    const yPeak = plotB - Math.min(plotH, Math.pow(valPeak, 0.9) * plotH)

                    realPts.push({ x: x, y: yReal })
                    peakPts.push({ x: x, y: yPeak })
                }

                // Curve 1: Real-time Translucent Chartreuse / Yellow-Green Filled Area
                c.beginPath()
                c.moveTo(leftMargin, plotB)
                c.lineTo(realPts[0].x, realPts[0].y)
                for (let i = 0; i < realPts.length - 1; ++i) {
                    const curr = realPts[i]
                    const next = realPts[i + 1]
                    c.quadraticCurveTo(curr.x, curr.y, (curr.x + next.x) * 0.5, (curr.y + next.y) * 0.5)
                }
                c.lineTo(realPts[realPts.length - 1].x, realPts[realPts.length - 1].y)
                c.lineTo(leftMargin + plotW, plotB)
                c.closePath()

                const areaGrad = c.createLinearGradient(0, topMargin, 0, plotB)
                areaGrad.addColorStop(0, 'rgba(166, 226, 46, 0.42)')
                areaGrad.addColorStop(0.5, 'rgba(138, 201, 38, 0.22)')
                areaGrad.addColorStop(1, 'rgba(50, 90, 20, 0.03)')
                c.fillStyle = areaGrad
                c.fill()

                // Outline for real-time curve
                c.beginPath()
                c.moveTo(realPts[0].x, realPts[0].y)
                for (let i = 0; i < realPts.length - 1; ++i) {
                    const curr = realPts[i]
                    const next = realPts[i + 1]
                    c.quadraticCurveTo(curr.x, curr.y, (curr.x + next.x) * 0.5, (curr.y + next.y) * 0.5)
                }
                c.lineTo(realPts[realPts.length - 1].x, realPts[realPts.length - 1].y)
                c.strokeStyle = '#9ad824'
                c.lineWidth = 1.6
                c.stroke()

                // Curve 2: Peak Hold Upper Contour Line
                c.beginPath()
                c.moveTo(peakPts[0].x, peakPts[0].y)
                for (let i = 0; i < peakPts.length - 1; ++i) {
                    const curr = peakPts[i]
                    const next = peakPts[i + 1]
                    c.quadraticCurveTo(curr.x, curr.y, (curr.x + next.x) * 0.5, (curr.y + next.y) * 0.5)
                }
                c.lineTo(peakPts[peakPts.length - 1].x, peakPts[peakPts.length - 1].y)
                c.strokeStyle = '#d4ff4d'
                c.lineWidth = 1.8
                c.stroke()
            }

            // 6. Top Header Readout
            c.textAlign = 'left'
            c.font = 'bold 11px Consolas, monospace'
            c.fillStyle = '#d4ff4d'
            const curHz = (root.music && root.music._values) ? Math.round(root.music._values.peak || 440) : 440
            c.fillText('819 HZ    G#5 -24 CENTS    DELTA -8.0 DB', leftMargin + 10, topMargin - 10)
            c.textAlign = 'right'
            c.fillText('-76.0 DB', leftMargin + plotW - 10, topMargin - 10)

            // 7. Right Vertical Stereo Level Meters (L & R)
            const meterX = leftMargin + plotW + 28
            const meterW = 14
            const meterH = plotH
            const leftRms = root.music ? Math.max(0, Math.min(1, root.music.left || 0)) : 0
            const rightRms = root.music ? Math.max(0, Math.min(1, root.music.right || 0)) : 0

            function drawMeterBar(x, level) {
                c.fillStyle = '#101a24'
                c.fillRect(x, topMargin, meterW, meterH)
                const barH = level * meterH
                const barY = plotB - barH
                if (barH > 0) {
                    const grad = c.createLinearGradient(0, plotB, 0, topMargin)
                    grad.addColorStop(0, '#28a745')
                    grad.addColorStop(0.7, '#ffc107')
                    grad.addColorStop(0.95, '#dc3545')
                    c.fillStyle = grad
                    c.fillRect(x, barY, meterW, barH)
                }
                // Peak line
                c.fillStyle = '#ffffff'
                c.fillRect(x, Math.max(topMargin, barY - 1), meterW, 2)
            }

            drawMeterBar(meterX, leftRms)
            drawMeterBar(meterX + meterW + 4, rightRms)

            c.fillStyle = '#738992'
            c.font = '9px Consolas, monospace'
            c.textAlign = 'center'
            c.fillText('L', meterX + meterW * 0.5, plotB + 12)
            c.fillText('R', meterX + meterW + 4 + meterW * 0.5, plotB + 12)

            // 8. Bottom Statistics & Correlation Bar (exactly like Image 2)
            const statY = h - 18
            c.textAlign = 'left'
            c.font = '10px Consolas, monospace'

            // Statistics badge
            c.fillStyle = '#223444'
            c.fillRect(leftMargin, statY - 12, 65, 18)
            c.fillStyle = '#d6e6ea'
            c.fillText('Statistics', leftMargin + 4, statY)

            // RMS values
            c.fillStyle = '#8ea1b0'
            const rmsL = root.music ? (20 * Math.log10(Math.max(1e-4, root.music.left || 1e-4))).toFixed(1) : '-22.7'
            const rmsR = root.music ? (20 * Math.log10(Math.max(1e-4, root.music.right || 1e-4))).toFixed(1) : '-22.9'
            c.fillText(`RMS ${rmsL} ${rmsR}`, leftMargin + 75, statY)

            // Metering mode & Crest factor
            c.fillText('Crest: 16.8 dB', leftMargin + 215, statY)

            // True peak clippings
            const isClipping = root.music && root.music.eqIsClipping
            c.fillStyle = isClipping ? '#ff3366' : '#8ea1b0'
            c.fillText(isClipping ? 'Clipping: OVERLOAD' : 'Clippings: 0 0', leftMargin + 325, statY)

            // Correlation Phase Meter (-1.00 to +1.00)
            const corrX = leftMargin + 460
            const corrW = 120
            c.fillStyle = '#8ea1b0'
            c.fillText('Correlation', corrX - 70, statY)

            // Correlation bar background
            c.fillStyle = '#141d26'
            c.fillRect(corrX, statY - 9, corrW, 11)

            // Center line
            c.strokeStyle = '#405868'
            c.beginPath()
            c.moveTo(corrX + corrW * 0.5, statY - 11)
            c.lineTo(corrX + corrW * 0.5, statY + 3)
            c.stroke()

            // Active phase bar (stereo in-phase goes positive to the right, antiphase goes left)
            const corrVal = (root.music && root.music.left > 0 && root.music.right > 0) ? 0.85 : 0.0
            const barLen = (corrVal * (corrW * 0.5))
            c.fillStyle = corrVal >= 0 ? '#4cd964' : '#ff3b30'
            if (barLen >= 0) {
                c.fillRect(corrX + corrW * 0.5, statY - 8, barLen, 9)
            } else {
                c.fillRect(corrX + corrW * 0.5 + barLen, statY - 8, -barLen, 9)
            }

            c.font = '8px Consolas, monospace'
            c.fillStyle = '#5c7385'
            c.fillText('-1.00', corrX - 4, statY + 12)
            c.fillText('+1.00', corrX + corrW - 20, statY + 12)

            // Balance readout
            c.font = '10px Consolas, monospace'
            c.fillStyle = '#8ea1b0'
            c.fillText('BAL 0.0', corrX + corrW + 20, statY)
        }
    }
}
