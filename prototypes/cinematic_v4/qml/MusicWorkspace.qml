import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Rectangle {
    id: musicPage
    objectName: 'musicWorkspace'
    required property var music
    property bool reactionAllowed: true
    property bool showEQ: true
    property bool showQueue: false
    color: '#071119'

    readonly property real queueWidth: width < 1200 ? 210 : 250
    readonly property real mainWidth: showQueue ? (width - queueWidth - 18) : (width - 16)
    readonly property color gold: '#e1b463'

    onEnabledChanged: if (!enabled) files.close()
    function clock(ms) {
        let s = Math.floor((ms || 0) / 1000);
        return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2)
    }

    component Caption: Text {
        color: '#78939f'
        font.pixelSize: 10
        font.family: 'Segoe UI'
        font.letterSpacing: 1.2
    }

    component Picker: ComboBox {
        id: pick
        implicitHeight: 28
        font.pixelSize: 11
        font.family: 'Segoe UI'
        contentItem: Text {
            text: pick.displayText
            color: '#d3dcd9'
            font: pick.font
            verticalAlignment: Text.AlignVCenter
            leftPadding: 8
            rightPadding: 20
            elide: Text.ElideRight
        }
        background: Rectangle {
            color: '#11212a'
            border.color: pick.activeFocus ? '#d1ac65' : '#31434c'
            radius: 3
        }
    }

    component MusicSlider: Slider {
        id: slider
        background: Rectangle {
            x: slider.leftPadding
            y: slider.topPadding + slider.availableHeight / 2 - 2
            width: slider.availableWidth
            height: 4
            radius: 2
            color: '#263b46'
            Rectangle {
                width: slider.visualPosition * parent.width
                height: 4
                radius: 2
                color: musicPage.gold
            }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: slider.topPadding + slider.availableHeight / 2 - 6
            width: 12
            height: 12
            radius: 6
            color: slider.pressed ? '#ffecb5' : musicPage.gold
        }
    }

    FileDialog {
        id: files
        objectName: 'musicFileDialog'
        title: 'Add local music'
        fileMode: FileDialog.OpenFiles
        nameFilters: ['Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.aif *.aiff *.wma)']
        onAccepted: if (musicPage.enabled) musicPage.music.addFiles(selectedFiles)
    }

    DropArea {
        anchors.fill: parent
        onDropped: function(drop) {
            if (drop.hasUrls) {
                musicPage.music.addFiles(drop.urls)
                drop.acceptProposedAction()
            }
        }
    }

    // 1. Sleek Compact Header Bar (height: ~44px)
    Rectangle {
        id: headerBar
        x: 8
        y: 6
        width: musicPage.mainWidth
        height: 44
        color: 'transparent'

        Row {
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            spacing: 10

            // Track info block
            Column {
                spacing: 1
                Caption {
                    text: 'MUSIC  /  AUDIO WORKSPACE'
                    color: musicPage.gold
                    font.pixelSize: 8
                }
                Text {
                    text: musicPage.music && musicPage.music.title ? musicPage.music.title : 'No Track Loaded'
                    textFormat: Text.PlainText
                    color: '#f0e8d8'
                    font.family: 'Segoe UI'
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    width: Math.min(220, musicPage.mainWidth * 0.28)
                }
            }

            // Quick source & device controls
            Row {
                spacing: 5
                anchors.verticalCenter: parent.verticalCenter

                HudButton {
                    objectName: 'musicOpen'
                    text: '＋ OPEN'
                    accent: true
                    height: 26
                    implicitWidth: 64
                    font.pixelSize: 10
                    onClicked: files.open()
                }
                HudButton {
                    objectName: 'musicInputPlayer'
                    text: 'PLAYER'
                    selected: musicPage.music.inputSource === 'player'
                    height: 26
                    implicitWidth: 56
                    font.pixelSize: 10
                    onClicked: musicPage.music.setInput('player')
                }
                HudButton {
                    objectName: 'musicInputSystem'
                    text: musicPage.width < 1300 ? 'SYSTEM' : 'WINDOWS AUDIO'
                    selected: musicPage.music.inputSource === 'system'
                    height: 26
                    implicitWidth: musicPage.width < 1300 ? 60 : 108
                    font.pixelSize: 10
                    onClicked: musicPage.music.setInput('system')
                }
                Picker {
                    objectName: 'musicDevice'
                    width: Math.min(150, Math.max(100, musicPage.mainWidth * 0.12))
                    visible: musicPage.music.inputSource === 'system'
                    model: musicPage.music.captureDevices
                    textRole: 'label'
                    valueRole: 'id'
                    onActivated: musicPage.music.setCaptureDevice(currentValue)
                    Accessible.name: 'Windows output to visualize'
                }
                HudButton {
                    objectName: 'musicCaptureToggle'
                    visible: musicPage.music.inputSource === 'system'
                    implicitWidth: 68
                    height: 26
                    font.pixelSize: 10
                    text: musicPage.music.captureState === 'active' || musicPage.music.captureState === 'starting' ? 'STOP' : 'CONNECT'
                    onClicked: {
                        if (musicPage.music.captureState === 'active' || musicPage.music.captureState === 'starting')
                            musicPage.music.stopCapture()
                        else
                            musicPage.music.startCapture()
                    }
                }
                Picker {
                    objectName: 'musicOutput'
                    visible: musicPage.music.inputSource === 'player'
                    width: Math.min(150, Math.max(100, musicPage.mainWidth * 0.12))
                    model: musicPage.music.outputDevices
                    onActivated: musicPage.music.setOutputDevice(currentIndex)
                    Accessible.name: 'E.V. playback output'
                }
            }
        }

        // Right side: Layout Switcher & Panel Toggles
        Row {
            id: layoutControls
            objectName: 'musicLayoutControls'
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4

            HudButton {
                objectName: 'layoutStudioBtn'
                text: 'STUDIO'
                height: 24
                implicitWidth: 54
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.music && musicPage.music.currentLayout === 'studio-span'
                onClicked: if (musicPage.music) musicPage.music.setLayout('studio-span')
            }
            HudButton {
                objectName: 'layoutTrioBtn'
                text: 'TRIO'
                height: 24
                implicitWidth: 44
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: !musicPage.music || !musicPage.music.currentLayout || musicPage.music.currentLayout === 'reference-trio'
                onClicked: if (musicPage.music) musicPage.music.setLayout('reference-trio')
            }
            HudButton {
                objectName: 'layoutTraceBtn'
                text: 'TRACE'
                height: 24
                implicitWidth: 50
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.music && musicPage.music.currentLayout === 'single-trace'
                onClicked: if (musicPage.music) musicPage.music.setLayout('single-trace')
            }
            HudButton {
                objectName: 'layoutNeedlesBtn'
                text: 'NEEDLES'
                height: 24
                implicitWidth: 62
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.music && musicPage.music.currentLayout === 'single-rain'
                onClicked: if (musicPage.music) musicPage.music.setLayout('single-rain')
            }
            HudButton {
                objectName: 'layoutSplitBtn'
                text: 'SPLIT'
                height: 24
                implicitWidth: 46
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.music && musicPage.music.currentLayout === 'split-duo'
                onClicked: if (musicPage.music) musicPage.music.setLayout('split-duo')
            }
            HudButton {
                objectName: 'layoutSegmentsBtn'
                text: 'SEGMENTS'
                height: 24
                implicitWidth: 74
                font.pixelSize: 10
                font.letterSpacing: 0.2
                selected: musicPage.music && musicPage.music.currentLayout === 'single-stack'
                onClicked: if (musicPage.music) musicPage.music.setLayout('single-stack')
            }

            Rectangle { width: 1; height: 16; color: '#253a47'; anchors.verticalCenter: parent.verticalCenter }

            // Collapsible panel toggles
            HudButton {
                id: layoutEQBtn
                objectName: 'layoutEQBtn'
                text: musicPage.showEQ ? 'EQ ACTIVE' : '10-BAND EQ'
                height: 24
                implicitWidth: 74
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.showEQ
                accent: musicPage.showEQ
                onClicked: musicPage.showEQ = !musicPage.showEQ
            }
            HudButton {
                id: musicEQToggle
                objectName: 'musicEQToggle'
                visible: false
                selected: musicPage.showEQ
                onClicked: musicPage.showEQ = !musicPage.showEQ
            }
            HudButton {
                objectName: 'musicQueueToggle'
                text: musicPage.showQueue ? 'QUEUE [ON]' : 'QUEUE'
                height: 24
                implicitWidth: 66
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.showQueue
                onClicked: musicPage.showQueue = !musicPage.showQueue
            }
        }
    }

    // 2. High-prominence Visualizer Area
    Rectangle {
        id: analyzer
        objectName: 'musicAnalyzer'
        x: 8
        y: 54
        width: musicPage.mainWidth
        readonly property real availH: Math.max(160, musicPage.height - 54 - 60 - 12)
        readonly property real eqH: musicPage.showEQ ? Math.min(180, Math.max(135, availH * 0.28)) : 0
        height: musicPage.showEQ ? Math.max(120, availH - eqH - 6) : availH
        color: '#0a1821'
        border.color: '#263b45'
        radius: 5
        clip: true

        VisualizerBoard {
            id: visualizerBoard
            objectName: 'musicVisualizerBoard'
            anchors.fill: parent
            music: musicPage.music
        }
    }

    // 3. Collapsible 10-Band EQ Panel
    EqualizerPanel {
        id: eqPanel
        objectName: 'musicEqualizerPanel'
        visible: musicPage.showEQ
        x: 8
        y: analyzer.y + analyzer.height + 6
        width: musicPage.mainWidth
        height: analyzer.eqH
        music: musicPage.music
    }

    // 4. Collapsible Playlist Queue Sidebar
    Column {
        id: queueSidebar
        visible: musicPage.showQueue
        x: musicPage.mainWidth + 14
        y: 8
        width: musicPage.queueWidth
        spacing: 8

        Row {
            width: parent.width
            Caption {
                text: 'PLAYLIST QUEUE'
                font.family: 'Segoe UI'
                font.pixelSize: 9
                color: musicPage.gold
            }
            Text {
                text: musicPage.music.queue.length + (musicPage.music.queue.length === 1 ? ' track' : ' tracks')
                color: '#91a7b0'
                font.family: 'Consolas'
                font.pixelSize: 10
                anchors.right: parent.right
            }
        }

        ListView {
            id: queueList
            objectName: 'musicQueue'
            width: parent.width
            height: Math.max(120, musicPage.height - 180)
            clip: true
            spacing: 4
            model: musicPage.music.queue
            ScrollBar.vertical: ScrollBar {}
            delegate: HudButton {
                required property var modelData
                width: ListView.view.width
                height: 34
                text: (modelData.index + 1) + '   ' + modelData.title
                selected: modelData.index === musicPage.music.currentIndex
                onClicked: musicPage.music.playIndex(modelData.index)
            }
            Text {
                visible: musicPage.music.queue.length === 0
                anchors.centerIn: parent
                text: 'Drop local audio files\nor click ＋ OPEN'
                color: '#6f8a98'
                font.family: 'Segoe UI'
                font.pixelSize: 12
                horizontalAlignment: Text.AlignHCenter
            }
        }

        // Mini spectrum bands
        Row {
            width: parent.width
            spacing: 6
            Repeater {
                model: [{ label: 'BASS', value: musicPage.music.bass }, { label: 'MID', value: musicPage.music.mid }, { label: 'HIGH', value: musicPage.music.treble }]
                Column {
                    required property var modelData
                    width: (musicPage.queueWidth - 12) / 3
                    spacing: 4
                    Caption { text: modelData.label; font.pixelSize: 8 }
                    Rectangle {
                        width: parent.width
                        height: 3
                        color: '#253a43'
                        Rectangle { width: parent.width * modelData.value; height: 3; color: musicPage.gold }
                    }
                }
            }
        }
    }

    // 5. Sleek Professional DAW-style Transport Bar (height: 54px)
    Rectangle {
        id: transport
        objectName: 'musicTransport'
        x: 8
        y: parent.height - 54
        width: parent.width - 16
        height: 50
        color: '#0e1a22'
        border.color: '#263b46'
        radius: 4

        // Seek Bar at top edge of transport
        MusicSlider {
            objectName: 'musicSeek'
            x: 4
            y: -6
            width: parent.width - 8
            height: 16
            from: 0
            to: Math.max(1, musicPage.music.duration)
            stepSize: 1000
            value: musicPage.music.position
            enabled: musicPage.music.seekable
            onMoved: musicPage.music.seek(value)
            Accessible.name: 'Track position'
        }

        // Transport Controls Row
        Row {
            x: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            spacing: 6

            HudButton {
                objectName: 'musicPrevious'
                text: 'PREV'
                implicitWidth: 50
                height: 26
                font.pixelSize: 10
                enabled: musicPage.music.hasTrack
                onClicked: musicPage.music.previous()
            }
            HudButton {
                objectName: 'musicPlay'
                text: musicPage.music.playing ? 'PAUSE' : 'PLAY'
                implicitWidth: 62
                height: 26
                accent: true
                font.pixelSize: 10
                enabled: musicPage.music.hasTrack
                onClicked: musicPage.music.togglePlayback()
            }
            HudButton {
                objectName: 'musicNext'
                text: 'NEXT'
                implicitWidth: 50
                height: 26
                font.pixelSize: 10
                enabled: musicPage.music.currentIndex + 1 < musicPage.music.queue.length
                onClicked: musicPage.music.next()
            }
            HudButton {
                objectName: 'musicStop'
                text: 'STOP'
                implicitWidth: 50
                height: 26
                font.pixelSize: 10
                enabled: musicPage.music.hasTrack
                onClicked: musicPage.music.stop()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: musicPage.clock(musicPage.music.position) + ' / ' + musicPage.clock(musicPage.music.duration)
                font.family: 'Consolas'
                font.pixelSize: 11
                color: '#c8d3d1'
            }
        }

        // Center Status Text
        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: 4
            text: musicPage.music.status
            textFormat: Text.PlainText
            color: musicPage.music.captureState === 'error' ? '#e5a06c' : '#7e96a2'
            font.family: 'Segoe UI'
            font.pixelSize: 10
            elide: Text.ElideRight
            width: Math.min(400, parent.width * 0.35)
            horizontalAlignment: Text.AlignHCenter
        }

        // Right Volume & Mute Controls
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 8
            spacing: 6

            HudButton {
                objectName: 'musicMute'
                text: musicPage.music.muted ? 'UNMUTE' : 'MUTE'
                implicitWidth: 58
                height: 26
                font.pixelSize: 10
                onClicked: musicPage.music.setMuted(!musicPage.music.muted)
            }
            MusicSlider {
                objectName: 'musicVolume'
                width: 90
                height: 26
                anchors.verticalCenter: parent.verticalCenter
                from: 0
                to: 1
                value: musicPage.music.volume
                onMoved: musicPage.music.setVolume(value)
                Accessible.name: 'Music volume'
            }
        }
    }
}
