import QtQuick
import QtQuick.Controls

Rectangle {
    id: eqRoot
    objectName: 'musicEqualizerPanel'
    required property var music
    property bool compact: height < 200
    signal closeRequested()
    readonly property color gold: '#e1b463'
    readonly property color cyan: '#53e6d2'
    readonly property color muted: '#78939f'
    readonly property color trackBg: '#11222b'
    readonly property color panelBg: '#09151d'
    readonly property color panelBorder: '#233742'

    color: panelBg
    border.color: panelBorder
    radius: 5
    clip: true

    component HeaderLabel: Text {
        color: eqRoot.muted
        font.pixelSize: 10
        font.letterSpacing: 1.2
        font.family: 'Segoe UI'
        font.weight: Font.DemiBold
    }

    component BandColumn: Column {
        id: col
        required property int bandIndex
        required property string freqText
        width: Math.max(26, (slidersRow.width - preampCol.width - sepItem.width) / 10)
        height: slidersRow.height
        spacing: 2

        readonly property real bandGain: eqRoot.music && eqRoot.music.eqGains && eqRoot.music.eqGains.length > col.bandIndex ? eqRoot.music.eqGains[col.bandIndex] : 0.0

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: (col.bandGain >= 0 ? '+' : '') + col.bandGain.toFixed(1)
            font.family: 'Consolas'
            font.pixelSize: 9
            color: Math.abs(col.bandGain) > 0.05 ? (col.bandGain > 0 ? eqRoot.gold : eqRoot.cyan) : '#637e8c'
        }

        Slider {
            id: bandSlider
            objectName: 'eqBandSlider_' + col.bandIndex
            orientation: Qt.Vertical
            anchors.horizontalCenter: parent.horizontalCenter
            width: Math.min(26, col.width - 2)
            height: parent.height - 34
            from: -12.0
            to: 12.0
            stepSize: 0.5
            value: col.bandGain
            enabled: eqRoot.music && !eqRoot.music.eqBypass
            opacity: enabled ? 1.0 : 0.4
            onMoved: if (eqRoot.music) eqRoot.music.setBandGain(col.bandIndex, value)

            background: Rectangle {
                x: bandSlider.leftPadding + bandSlider.availableWidth / 2 - 2
                y: bandSlider.topPadding
                width: 4
                height: bandSlider.availableHeight
                radius: 2
                color: eqRoot.trackBg
                // Center 0 dB marker
                Rectangle {
                    y: parent.height / 2 - 1
                    width: 10
                    x: -3
                    height: 2
                    color: '#2a4454'
                }
                // Fill from 0 dB to current value (visualPosition is 0 at top=+12, 1 at bottom=-12)
                Rectangle {
                    property real zeroY: parent.height / 2
                    property real handleY: bandSlider.visualPosition * parent.height
                    y: Math.min(zeroY, handleY)
                    width: 4
                    height: Math.abs(zeroY - handleY)
                    radius: 2
                    color: col.bandGain > 0 ? eqRoot.gold : eqRoot.cyan
                }
            }

            handle: Rectangle {
                x: bandSlider.leftPadding + bandSlider.availableWidth / 2 - width / 2
                y: bandSlider.topPadding + bandSlider.visualPosition * (bandSlider.availableHeight - height)
                width: 14
                height: 8
                radius: 2
                color: bandSlider.pressed ? '#fff3d1' : (col.bandGain > 0 ? eqRoot.gold : (col.bandGain < 0 ? eqRoot.cyan : '#9ab2bd'))
                border.color: '#1a2933'
            }
        }

        HeaderLabel {
            anchors.horizontalCenter: parent.horizontalCenter
            text: col.freqText
            font.pixelSize: 9
            color: Math.abs(col.bandGain) > 0.05 ? '#d2dfdf' : '#637e8c'
        }
    }

    // Top Header & Status Bar
    Rectangle {
        id: headerBar
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 32
        color: '#0d1d27'
        border.color: '#1a2e3a'

        Row {
            anchors.left: parent.left
            anchors.leftMargin: 12
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            HeaderLabel {
                text: '10-BAND REAL-TIME DSP EQUALIZER'
                color: eqRoot.gold
                anchors.verticalCenter: parent.verticalCenter
            }

            // Status Badge
            Rectangle {
                height: 18
                width: statusText.implicitWidth + 14
                radius: 9
                anchors.verticalCenter: parent.verticalCenter
                color: eqRoot.music && eqRoot.music.eqActive ? '#103837' : (eqRoot.music && eqRoot.music.eqBypass ? '#352912' : '#142028')
                border.color: eqRoot.music && eqRoot.music.eqActive ? eqRoot.cyan : (eqRoot.music && eqRoot.music.eqBypass ? eqRoot.gold : '#2d434f')

                Text {
                    id: statusText
                    anchors.centerIn: parent
                    text: eqRoot.music ? eqRoot.music.eqStatus : 'Off'
                    font.family: 'Segoe UI'
                    font.pixelSize: 10
                    font.bold: true
                    color: eqRoot.music && eqRoot.music.eqActive ? eqRoot.cyan : (eqRoot.music && eqRoot.music.eqBypass ? eqRoot.gold : '#839ba8')
                }
            }

            // Headroom display
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4
                visible: eqRoot.width > 600
                HeaderLabel {
                    text: 'HEADROOM:'
                    anchors.verticalCenter: parent.verticalCenter
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: eqRoot.music ? (eqRoot.music.eqHeadroom >= 0 ? '+' : '') + eqRoot.music.eqHeadroom.toFixed(1) + ' dB' : '+0.0 dB'
                    font.family: 'Consolas'
                    font.pixelSize: 10
                    font.bold: true
                    color: eqRoot.music && eqRoot.music.eqHeadroom < 0 ? '#ff9f43' : '#8fa8b4'
                }
            }

            // Clipping & Overload LED Indicator
            Row {
                anchors.verticalCenter: parent.verticalCenter
                spacing: 5
                visible: eqRoot.width > 700
                Rectangle {
                    width: 7
                    height: 7
                    radius: 3.5
                    anchors.verticalCenter: parent.verticalCenter
                    color: eqRoot.music && eqRoot.music.eqIsClipping ? '#ff4757' : '#2ed573'
                    opacity: eqRoot.music && eqRoot.music.eqIsClipping ? 1.0 : 0.5
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: eqRoot.music && eqRoot.music.eqIsClipping ? 'DIGITAL OVERLOAD' : 'CLIP OK'
                    font.family: 'Segoe UI'
                    font.pixelSize: 10
                    color: eqRoot.music && eqRoot.music.eqIsClipping ? '#ff4757' : '#577382'
                }
            }
        }

        // Action Buttons
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            HudButton {
                objectName: 'eqResetFlatBtn'
                text: 'RESET FLAT'
                implicitWidth: 84
                height: 22
                font.pixelSize: 10
                onClicked: if (eqRoot.music) eqRoot.music.resetFlat()
            }

            HudButton {
                objectName: 'eqBypassToggleBtn'
                text: eqRoot.music && eqRoot.music.eqBypass ? 'BYPASSED' : 'BYPASS'
                selected: eqRoot.music && eqRoot.music.eqBypass
                accent: eqRoot.music && eqRoot.music.eqBypass
                implicitWidth: 72
                height: 22
                font.pixelSize: 10
                onClicked: if (eqRoot.music) eqRoot.music.setBypass(!eqRoot.music.eqBypass)
            }

            HudButton {
                text: '✕'
                implicitWidth: 24
                height: 22
                font.pixelSize: 11
                quiet: true
                onClicked: eqRoot.closeRequested()
            }
        }
    }

    // Sliders Container
    Row {
        id: slidersRow
        anchors.top: headerBar.bottom
        anchors.topMargin: 4
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        anchors.left: parent.left
        anchors.leftMargin: 10
        anchors.right: parent.right
        anchors.rightMargin: 10
        spacing: 0

        // Preamp Slider Column
        Column {
            id: preampCol
            width: Math.min(48, Math.max(34, slidersRow.width * 0.08))
            height: parent.height
            spacing: 2

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                text: eqRoot.music ? (eqRoot.music.eqPreamp >= 0 ? '+' : '') + eqRoot.music.eqPreamp.toFixed(1) : '+0.0'
                font.family: 'Consolas'
                font.pixelSize: 9
                color: eqRoot.music && Math.abs(eqRoot.music.eqPreamp) > 0.05 ? eqRoot.gold : '#78939f'
            }

            Slider {
                id: preampSlider
                objectName: 'preampSlider'
                orientation: Qt.Vertical
                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(26, preampCol.width - 2)
                height: parent.height - 34
                from: -18.0
                to: 18.0
                stepSize: 0.5
                value: eqRoot.music ? eqRoot.music.eqPreamp : 0.0
                enabled: eqRoot.music && !eqRoot.music.eqBypass
                opacity: enabled ? 1.0 : 0.4
                onMoved: if (eqRoot.music) eqRoot.music.setPreamp(value)

                background: Rectangle {
                    x: preampSlider.leftPadding + preampSlider.availableWidth / 2 - 2
                    y: preampSlider.topPadding
                    width: 4
                    height: preampSlider.availableHeight
                    radius: 2
                    color: eqRoot.trackBg
                    // Center 0 dB marker
                    Rectangle {
                        y: parent.height / 2 - 1
                        width: 10
                        x: -3
                        height: 2
                        color: '#2a4454'
                    }
                    // Fill from 0 dB to current value (visualPosition is 0 at top=+18, 1 at bottom=-18)
                    Rectangle {
                        property real zeroY: parent.height / 2
                        property real handleY: preampSlider.visualPosition * parent.height
                        y: Math.min(zeroY, handleY)
                        width: 4
                        height: Math.abs(zeroY - handleY)
                        radius: 2
                        color: eqRoot.gold
                    }
                }

                handle: Rectangle {
                    x: preampSlider.leftPadding + preampSlider.availableWidth / 2 - width / 2
                    y: preampSlider.topPadding + preampSlider.visualPosition * (preampSlider.availableHeight - height)
                    width: 14
                    height: 8
                    radius: 2
                    color: preampSlider.pressed ? '#fff3d1' : eqRoot.gold
                    border.color: '#1a2933'
                }
            }

            HeaderLabel {
                anchors.horizontalCenter: parent.horizontalCenter
                text: 'PRE'
                font.pixelSize: 9
                color: eqRoot.gold
            }
        }

        // Vertical Separator
        Item {
            id: sepItem
            width: 14
            height: parent.height
            Rectangle {
                width: 1
                height: parent.height - 10
                anchors.centerIn: parent
                color: '#1c2f3b'
            }
        }

        // 10 Standard ISO Frequency Bands
        BandColumn { bandIndex: 0; freqText: '31' }
        BandColumn { bandIndex: 1; freqText: '62' }
        BandColumn { bandIndex: 2; freqText: '125' }
        BandColumn { bandIndex: 3; freqText: '250' }
        BandColumn { bandIndex: 4; freqText: '500' }
        BandColumn { bandIndex: 5; freqText: '1k' }
        BandColumn { bandIndex: 6; freqText: '2k' }
        BandColumn { bandIndex: 7; freqText: '4k' }
        BandColumn { bandIndex: 8; freqText: '8k' }
        BandColumn { bandIndex: 9; freqText: '16k' }
    }
}
