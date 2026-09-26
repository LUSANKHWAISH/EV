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
    property color eqCurveColor: '#00e5ff'

    // Ballistic peak hold state
    property var peakSpectrum: []

    // Interactive mouse / cursor tracking
    property real mouseXPos: -1
    property real mouseYPos: -1
    property bool mouseHovered: false
    property int draggingBand: -1

    // ISO 10-band center frequencies
    readonly property var eqFreqs: [31, 62, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
    readonly property var eqLabels: ['31', '62', '125', '250', '500', '1K', '2K', '4K', '8K', '16K']

    Timer {
        interval: 33
        running: true
        repeat: true
        onTriggered: {
            const raw = root.music ? (root.music.spectrum || []) : []
            if (raw.length === 0) return
            let p = root.peakSpectrum || []
            if (p.length !== raw.length) {
                p = new Array(raw.length).fill(0)
            }
            for (let i = 0; i < raw.length; ++i) {
                const cur = Number(raw[i] || 0)
                if (cur >= p[i]) {
                    p[i] = cur
                } else {
                    p[i] = Math.max(cur, p[i] - 0.007) // smooth ballistic decay
                }
            }
            root.peakSpectrum = p
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
            const isCompactH = h < 240
            const leftMargin = 30
            const rightMargin = 70 // reserved for stereo level meters
            const topMargin = isCompactH ? 18 : 28   // reserved for top readouts
            const bottomMargin = isCompactH ? 38 : 56 // reserved for frequency scale + statistics bar
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
                const norm = (Math.log10(Math.max(20, Math.min(20000, freq))) - logMin) / (logMax - logMin)
                return leftMargin + norm * plotW
            }
            function xToFreq(x) {
                const norm = Math.max(0, Math.min(1, (x - leftMargin) / plotW))
                return Math.pow(10, logMin + norm * (logMax - logMin))
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

            // 4. Decibel Grid Lines (-78 dB to +6 dB)
            const dbTicks = [
                { db: 6, l: '+6' }, { db: 0, l: '0' }, { db: -6, l: '-6' },
                { db: -12, l: '-12' }, { db: -18, l: '-18' }, { db: -24, l: '-24' },
                { db: -30, l: '-30' }, { db: -36, l: '-36' }, { db: -42, l: '-42' },
                { db: -48, l: '-48' }, { db: -54, l: '-54' }, { db: -60, l: '-60' },
                { db: -66, l: '-66' }, { db: -72, l: '-72' }, { db: -78, l: '-78' }
            ]

            function dbToY(db) {
                const norm = (6.0 - db) / 84.0
                return topMargin + norm * plotH
            }
            function yToDb(y) {
                const norm = (y - topMargin) / plotH
                return 6.0 - norm * 84.0
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

            // 5. Genuine 256-Point FFT Spectrum Curves
            const specData = root.music ? (root.music.spectrum || []) : []
            const peakData = root.peakSpectrum || []

            if (specData.length > 10) {
                const count = specData.length
                const realPts = []
                const peakPts = []

                for (let i = 0; i < count; ++i) {
                    const normX = i / (count - 1)
                    const x = leftMargin + normX * plotW

                    const valReal = Number(specData[i] || 0)
                    const valPeak = Number(peakData[i] || valReal)

                    // Normalized 0..1 magnitude maps linearly to plot height
                    const yReal = plotB - Math.max(0, Math.min(plotH, valReal * plotH))
                    const yPeak = plotB - Math.max(0, Math.min(plotH, valPeak * plotH))

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
                areaGrad.addColorStop(0, 'rgba(166, 226, 46, 0.38)')
                areaGrad.addColorStop(0.5, 'rgba(138, 201, 38, 0.18)')
                areaGrad.addColorStop(1, 'rgba(30, 60, 15, 0.02)')
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

            // 6. Active 10-Band EQ Response Curve & Control Nodes
            const eqGains = root.music && root.music.eqGains ? root.music.eqGains : [0,0,0,0,0,0,0,0,0,0]
            const eqPreamp = root.music ? (root.music.eqPreamp || 0.0) : 0.0
            const eqBypass = root.music ? Boolean(root.music.eqBypass) : false

            // Center the EQ reference line (0 dB) at upper-mid area: -24 dBFS on grid
            const eqZeroY = dbToY(-24.0)
            const eqScalePxPerDb = plotH / 50.0 // 12 dB = ~24% of plot height

            function calcEqGainAtFreq(f) {
                if (eqBypass) return 0.0
                let total = eqPreamp
                for (let b = 0; b < root.eqFreqs.length; ++b) {
                    const f0 = root.eqFreqs[b]
                    const g = Number(eqGains[b] || 0.0)
                    if (Math.abs(g) > 0.01) {
                        const distOct = Math.log2(f / f0) / 0.7
                        total += g / (1.0 + distOct * distOct)
                    }
                }
                return total
            }

            // Draw EQ 0 dB reference dashed line
            c.strokeStyle = eqBypass ? '#22303c' : 'rgba(0, 229, 255, 0.22)'
            c.setLineDash([4, 4])
            c.lineWidth = 1
            c.beginPath()
            c.moveTo(leftMargin, eqZeroY)
            c.lineTo(leftMargin + plotW, eqZeroY)
            c.stroke()
            c.setLineDash([])

            c.font = '8px Consolas, monospace'
            c.textAlign = 'left'
            c.fillStyle = eqBypass ? '#4a5b68' : 'rgba(0, 229, 255, 0.45)'
            c.fillText('EQ 0 dB' + (eqBypass ? ' (BYPASS)' : ''), leftMargin + 8, eqZeroY - 4)

            // Plot EQ composite curve across 128 log points
            const eqCurvePts = []
            const eqSteps = 128
            for (let s = 0; s <= eqSteps; ++s) {
                const norm = s / eqSteps
                const f = Math.pow(10, logMin + norm * (logMax - logMin))
                const gainAtF = calcEqGainAtFreq(f)
                const px = leftMargin + norm * plotW
                const py = eqZeroY - gainAtF * eqScalePxPerDb
                eqCurvePts.push({ x: px, y: py })
            }

            // Shaded fill under EQ curve toward 0 dB line
            c.beginPath()
            c.moveTo(leftMargin, eqZeroY)
            for (let s = 0; s <= eqSteps; ++s) {
                c.lineTo(eqCurvePts[s].x, eqCurvePts[s].y)
            }
            c.lineTo(leftMargin + plotW, eqZeroY)
            c.closePath()
            const eqFillGrad = c.createLinearGradient(0, topMargin, 0, plotB)
            eqFillGrad.addColorStop(0, eqBypass ? 'rgba(50, 70, 80, 0.06)' : 'rgba(0, 229, 255, 0.14)')
            eqFillGrad.addColorStop(1, 'rgba(0, 229, 255, 0.01)')
            c.fillStyle = eqFillGrad
            c.fill()

            // EQ Stroke line
            c.beginPath()
            c.moveTo(eqCurvePts[0].x, eqCurvePts[0].y)
            for (let s = 1; s <= eqSteps; ++s) {
                c.lineTo(eqCurvePts[s].x, eqCurvePts[s].y)
            }
            c.strokeStyle = eqBypass ? '#475e6d' : '#00e5ff'
            c.lineWidth = eqBypass ? 1.2 : 2.0
            c.stroke()

            // 10 Interactive EQ Control Nodes
            for (let b = 0; b < root.eqFreqs.length; ++b) {
                const f0 = root.eqFreqs[b]
                const nx = freqToX(f0)
                const rawGain = Number(eqGains[b] || 0.0)
                const nodeGain = eqBypass ? 0.0 : (rawGain + eqPreamp)
                const ny = eqZeroY - nodeGain * eqScalePxPerDb

                const isDragging = (root.draggingBand === b)
                const isHovered = !isDragging && (root.mouseXPos >= nx - 12 && root.mouseXPos <= nx + 12 &&
                                                  root.mouseYPos >= ny - 12 && root.mouseYPos <= ny + 12)

                // Glow ring on hover/drag
                if (isDragging || isHovered) {
                    c.beginPath()
                    c.arc(nx, ny, 10, 0, Math.PI * 2)
                    c.fillStyle = isDragging ? 'rgba(0, 229, 255, 0.4)' : 'rgba(0, 229, 255, 0.25)'
                    c.fill()
                }

                // Node circle
                c.beginPath()
                c.arc(nx, ny, 5.5, 0, Math.PI * 2)
                c.fillStyle = isDragging ? '#ffffff' : (eqBypass ? '#455966' : '#00e5ff')
                c.fill()
                c.strokeStyle = '#0a1017'
                c.lineWidth = 1.5
                c.stroke()

                // Band number / frequency label above/below node
                c.font = '8px Consolas, monospace'
                c.textAlign = 'center'
                c.fillStyle = isDragging ? '#ffffff' : (isHovered ? '#00e5ff' : '#6f8899')
                const lblY = (ny < eqZeroY) ? (ny - 8) : (ny + 14)
                const gainStr = (rawGain >= 0 ? '+' : '') + rawGain.toFixed(1) + 'dB'
                c.fillText(isDragging || isHovered ? gainStr : root.eqLabels[b], nx, lblY)
            }

            // 7. Interactive Crosshair & Cursor / Peak Readouts
            c.font = 'bold 11px Consolas, monospace'
            c.textAlign = 'left'

            const peakHz = root.music ? (root.music.peakHz || 0) : 0
            const peakNote = root.music ? (root.music.peakNote || '--') : '--'
            const peakText = root.music ? (root.music.samplePeakText || '-inf dBFS') : '-inf dBFS'

            if (root.mouseHovered && root.mouseXPos >= leftMargin && root.mouseXPos <= leftMargin + plotW &&
                root.mouseYPos >= topMargin && root.mouseYPos <= plotB) {
                
                // Draw crosshair lines
                c.strokeStyle = 'rgba(212, 255, 77, 0.35)'
                c.lineWidth = 1
                c.setLineDash([2, 3])

                // Vertical hair
                c.beginPath()
                c.moveTo(root.mouseXPos, topMargin)
                c.lineTo(root.mouseXPos, plotB)
                c.stroke()

                // Horizontal hair
                c.beginPath()
                c.moveTo(leftMargin, root.mouseYPos)
                c.lineTo(leftMargin + plotW, root.mouseYPos)
                c.stroke()
                c.setLineDash([])

                // Calculate cursor values
                const curF = xToFreq(root.mouseXPos)
                const curDb = yToDb(root.mouseYPos)

                // Cursor note
                function calcNote(hz) {
                    if (hz < 20 || !isFinite(hz)) return "--"
                    const midi = 69.0 + 12.0 * Math.log2(hz / 440.0)
                    const nearest = Math.round(midi)
                    const cents = Math.round((midi - nearest) * 100)
                    const names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
                    const note = names[((nearest % 12) + 12) % 12]
                    const octave = Math.floor(nearest / 12) - 1
                    const centsStr = cents > 0 ? ("+" + cents) : ("" + cents)
                    return note + octave + " " + centsStr + "ct"
                }

                const curNote = calcNote(curF)
                const peakDbVal = root.music && root.music.samplePeakL ? (20 * Math.log10(Math.max(1e-5, Math.max(root.music.samplePeakL, root.music.samplePeakR)))) : -78.0
                const deltaDb = curDb - peakDbVal

                c.fillStyle = '#d4ff4d'
                c.fillText(`${Math.round(curF)} HZ    ${curNote}    DELTA ${deltaDb >= 0 ? '+' : ''}${deltaDb.toFixed(1)} DB`, leftMargin + 10, topMargin - 10)
                c.textAlign = 'right'
                c.fillText(`${curDb.toFixed(1)} DB`, leftMargin + plotW - 10, topMargin - 10)
            } else {
                // Default Live Peak Readout
                c.fillStyle = '#d4ff4d'
                const hzStr = peakHz > 20 ? `${Math.round(peakHz)} HZ` : '-- HZ'
                c.fillText(`${hzStr}    ${peakNote}    PEAK TRACKING`, leftMargin + 10, topMargin - 10)
                c.textAlign = 'right'
                c.fillText(peakText, leftMargin + plotW - 10, topMargin - 10)
            }

            // 8. Right Vertical Stereo Level Meters (L & R)
            const meterX = leftMargin + plotW + 28
            const meterW = 14
            const meterH = plotH
            const leftRms = root.music ? Math.max(0, Math.min(1, root.music.left * 4.0)) : 0
            const rightRms = root.music ? Math.max(0, Math.min(1, root.music.right * 4.0)) : 0

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

            // 9. Bottom Statistics & Correlation Bar (Matching Reference 2)
            const statY = h - (isCompactH ? 8 : 18)
            c.textAlign = 'left'
            c.font = '10px Consolas, monospace'

            const compact = plotW < 800

            // Statistics badge
            c.fillStyle = '#223444'
            c.fillRect(leftMargin, statY - 12, 64, 18)
            c.fillStyle = '#d6e6ea'
            c.fillText('Statistics', leftMargin + 4, statY)

            // RMS values (Live L & R dBFS)
            c.fillStyle = '#8ea1b0'
            const rmsLStr = root.music ? (root.music.rmsLText || '-inf dBFS') : '-inf dBFS'
            const rmsRStr = root.music ? (root.music.rmsRText || '-inf dBFS') : '-inf dBFS'
            const rmsX = leftMargin + 72
            c.fillText(`RMS ${rmsLStr} ${rmsRStr}`, rmsX, statY)

            // Crest Factor (Live dB)
            const crestVal = root.music ? (Number(root.music.crestFactor) || 0.0) : 0.0
            const crestX = rmsX + (compact ? 135 : 160)
            c.fillText(`Crest: ${crestVal.toFixed(1)} dB`, crestX, statY)

            // Sample Peak Clippings count
            const clipCount = root.music ? (root.music.eqClippingCount || 0) : 0
            const clipX = crestX + (compact ? 95 : 110)
            c.fillStyle = clipCount > 0 ? '#ff3366' : '#8ea1b0'
            c.fillText(`Clip: ${clipCount}`, clipX, statY)

            // Sample Peak L / R
            c.fillStyle = '#8ea1b0'
            const pkLStr = root.music ? (root.music.samplePeakLText || '-inf dBFS') : '-inf dBFS'
            const pkRStr = root.music ? (root.music.samplePeakRText || '-inf dBFS') : '-inf dBFS'
            const peakX = clipX + (compact ? 65 : 85)
            if (!compact || plotW > 640) {
                c.fillText(`Peak: ${pkLStr} ${pkRStr}`, peakX, statY)
            }

            // Correlation Phase Meter (-1.00 to +1.00)
            const corrW = compact ? 70 : 90
            const corrX = leftMargin + plotW - corrW - 75
            c.fillStyle = '#8ea1b0'
            c.fillText('Corr', corrX - 32, statY)

            // Correlation meter background
            c.fillStyle = '#141d26'
            c.fillRect(corrX, statY - 9, corrW, 11)

            // Center line (0.00)
            c.strokeStyle = '#405868'
            c.beginPath()
            c.moveTo(corrX + corrW * 0.5, statY - 11)
            c.lineTo(corrX + corrW * 0.5, statY + 3)
            c.stroke()

            // Active phase bar
            const corrVal = root.music ? (Number(root.music.correlation) || 0.0) : 1.0
            const barLen = Math.max(-corrW * 0.5, Math.min(corrW * 0.5, corrVal * (corrW * 0.5)))
            c.fillStyle = corrVal >= 0 ? '#4cd964' : '#ff3b30'
            if (barLen >= 0) {
                c.fillRect(corrX + corrW * 0.5, statY - 8, barLen, 9)
            } else {
                c.fillRect(corrX + corrW * 0.5 + barLen, statY - 8, -barLen, 9)
            }

            c.font = '8px Consolas, monospace'
            c.fillStyle = '#5c7385'
            c.fillText('-1', corrX - 2, statY + 12)
            c.fillText('+1', corrX + corrW - 10, statY + 12)

            // Balance readout (Live dB)
            c.font = '10px Consolas, monospace'
            c.fillStyle = '#8ea1b0'
            const balVal = root.music ? (Number(root.music.balance) || 0.0) : 0.0
            const balStr = (balVal >= 0 ? '+' : '') + balVal.toFixed(1)
            c.fillText(`BAL ${balStr}`, corrX + corrW + 12, statY)
        }
    }

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true

        onPositionChanged: function(mouse) {
            root.mouseXPos = mouse.x
            root.mouseYPos = mouse.y
            root.mouseHovered = true

            // If dragging an EQ node:
            if (root.draggingBand >= 0 && root.music) {
                const isCompactH = height < 240
                const topMargin = isCompactH ? 18 : 28
                const bottomMargin = isCompactH ? 38 : 56
                const plotH = Math.max(10, height - topMargin - bottomMargin)
                const eqZeroY = topMargin + (6.0 - (-24.0)) / 84.0 * plotH
                const eqScalePxPerDb = plotH / 50.0
                const deltaPx = eqZeroY - mouse.y
                const newGain = Math.max(-12.0, Math.min(12.0, deltaPx / eqScalePxPerDb))
                root.music.setBandGain(root.draggingBand, Math.round(newGain * 10) / 10)
            }

            canvas.requestPaint()
        }

        onExited: {
            root.mouseHovered = false
            root.draggingBand = -1
            canvas.requestPaint()
        }

        onPressed: function(mouse) {
            const isCompactH = height < 240
            const leftMargin = 30
            const rightMargin = 70
            const topMargin = isCompactH ? 18 : 28
            const bottomMargin = isCompactH ? 38 : 56
            const plotW = Math.max(10, width - leftMargin - rightMargin)
            const plotH = Math.max(10, height - topMargin - bottomMargin)
            const logMin = Math.log10(20)
            const logMax = Math.log10(20000)
            const eqZeroY = topMargin + (6.0 - (-24.0)) / 84.0 * plotH
            const eqScalePxPerDb = plotH / 50.0

            const eqGains = root.music && root.music.eqGains ? root.music.eqGains : [0,0,0,0,0,0,0,0,0,0]
            const eqPreamp = root.music ? (root.music.eqPreamp || 0.0) : 0.0
            const eqBypass = root.music ? Boolean(root.music.eqBypass) : false

            // Check if clicking near any EQ node (within 14 px)
            for (let b = 0; b < root.eqFreqs.length; ++b) {
                const f0 = root.eqFreqs[b]
                const norm = (Math.log10(f0) - logMin) / (logMax - logMin)
                const nx = leftMargin + norm * plotW
                const rawGain = Number(eqGains[b] || 0.0)
                const nodeGain = eqBypass ? 0.0 : (rawGain + eqPreamp)
                const ny = eqZeroY - nodeGain * eqScalePxPerDb

                const dist = Math.hypot(mouse.x - nx, mouse.y - ny)
                if (dist <= 16) {
                    root.draggingBand = b
                    canvas.requestPaint()
                    return
                }
            }
        }

        onReleased: {
            root.draggingBand = -1
            canvas.requestPaint()
        }

        onDoubleClicked: function(mouse) {
            const leftMargin = 30
            const rightMargin = 70
            const topMargin = 28
            const bottomMargin = 56
            const plotW = Math.max(10, width - leftMargin - rightMargin)
            const logMin = Math.log10(20)
            const logMax = Math.log10(20000)

            // Double click on or near a band center resets that band to 0 dB
            for (let b = 0; b < root.eqFreqs.length; ++b) {
                const f0 = root.eqFreqs[b]
                const norm = (Math.log10(f0) - logMin) / (logMax - logMin)
                const nx = leftMargin + norm * plotW
                if (Math.abs(mouse.x - nx) <= 18) {
                    if (root.music) root.music.setBandGain(b, 0.0)
                    canvas.requestPaint()
                    return
                }
            }
        }
    }
}
