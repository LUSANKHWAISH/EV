import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Item {
    id: musicPage
    objectName: 'musicWorkspace'
    required property var music
    property var stage: null
    property bool reactionAllowed: true
    property string viewMode: 'cinematic' // 'cinematic' | 'orange' | 'studio'
    property bool showEQEditor: false
    property bool showQueue: false

    readonly property real queueWidth: width < 1200 ? 210 : 250
    readonly property real mainWidth: showQueue ? (width - queueWidth - 18) : (width - 16)
    readonly property color gold: '#e1b463'
    readonly property color cyan: '#53e6d2'
    readonly property color darkBg: '#0c1822'
    readonly property color borderColor: '#2c414d'
    readonly property bool hasTrack: music !== null && music.currentIndex >= 0 && music.queue && music.queue.length > 0

    onEnabledChanged: if (!enabled) files.close()
    function clock(ms) {
        let s = Math.floor((ms || 0) / 1000);
        return Math.floor(s / 60) + ':' + ('0' + s % 60).slice(-2)
    }

    // Synchronize viewMode with stage.visualTheme
    onViewModeChanged: {
        if (viewMode === 'orange') {
            if (stage) stage.visualTheme = 'stark_reactor'
        } else if (viewMode === 'cinematic') {
            if (stage && stage.visualTheme === 'stark_reactor') stage.visualTheme = 'cosmic_orbit'
        } else if (viewMode === 'studio') {
            if (stage && stage.visualTheme === 'stark_reactor') stage.visualTheme = 'cosmic_orbit'
        }
    }

    Component.onCompleted: {
        if (stage && stage.visualTheme === 'stark_reactor') {
            viewMode = 'orange'
        }
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

    // 1. Sleek Compact Header Bar (height: 42px)
    Item {
        id: headerBar
        x: 8
        y: 6
        width: musicPage.mainWidth
        height: 42

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
                    text: musicPage.hasTrack ? musicPage.music.title : 'No Track Loaded'
                    textFormat: Text.PlainText
                    color: '#f0e8d8'
                    font.family: 'Segoe UI'
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                    width: Math.min(200, musicPage.mainWidth * 0.24)
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
                    implicitWidth: 54
                    font.pixelSize: 10
                    onClicked: musicPage.music.setInputSource('player')
                }
                HudButton {
                    objectName: 'musicInputSystem'
                    text: musicPage.width < 1300 ? 'SYSTEM' : 'WINDOWS AUDIO'
                    selected: musicPage.music.inputSource === 'system'
                    height: 26
                    implicitWidth: musicPage.width < 1300 ? 56 : 94
                    font.pixelSize: 10
                    onClicked: musicPage.music.setInputSource('system')
                }
                Picker {
                    objectName: 'musicOutputPicker'
                    visible: musicPage.music.availableOutputs.length > 1
                    model: musicPage.music.availableOutputs
                    textRole: 'name'
                    implicitWidth: Math.min(130, Math.max(90, musicPage.mainWidth * 0.14))
                    currentIndex: Math.max(0, musicPage.music.availableOutputs.findIndex(function(o){ return o.id === musicPage.music.selectedOutputId }))
                    onActivated: function(index) {
                        let row = model[index];
                        if (row) musicPage.music.selectOutput(row.id)
                    }
                }
            }
        }

        // Right side: View Modes, DSP Status, EQ & Queue
        Row {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: 6

            // Separate Viewing Modes
            Row {
                spacing: 4
                anchors.verticalCenter: parent.verticalCenter

                HudButton {
                    id: viewCinematicBtn
                    objectName: 'viewCinematicBtn'
                    text: 'CINEMATIC'
                    height: 24
                    implicitWidth: 72
                    font.pixelSize: 10
                    font.letterSpacing: 0.3
                    selected: musicPage.viewMode === 'cinematic'
                    onClicked: musicPage.viewMode = 'cinematic'
                }

                HudButton {
                    id: viewOrangeBtn
                    objectName: 'viewOrangeBtn'
                    text: 'ORANGE'
                    height: 24
                    implicitWidth: 64
                    font.pixelSize: 10
                    font.letterSpacing: 0.3
                    selected: musicPage.viewMode === 'orange'
                    onClicked: musicPage.viewMode = 'orange'
                }

                HudButton {
                    id: layoutStudioBtn
                    objectName: 'layoutStudioBtn'
                    text: 'STUDIO'
                    height: 24
                    implicitWidth: 62
                    font.pixelSize: 10
                    font.letterSpacing: 0.3
                    selected: musicPage.viewMode === 'studio'
                    onClicked: {
                        musicPage.viewMode = 'studio'
                        if (musicPage.music) musicPage.music.setLayout('studio-span')
                    }
                }
            }

            // Studio Layout Switches (Visible in Studio mode, but always preserved in hierarchy for test detection)
            Row {
                id: studioSubLayouts
                visible: musicPage.viewMode === 'studio'
                spacing: 4
                anchors.verticalCenter: parent.verticalCenter

                Rectangle { width: 1; height: 16; color: '#253a47'; anchors.verticalCenter: parent.verticalCenter }

                HudButton {
                    id: layoutTrioBtn
                    objectName: 'layoutTrioBtn'
                    text: 'TRIO'
                    height: 24
                    implicitWidth: 46
                    font.pixelSize: 10
                    font.letterSpacing: 0.3
                    selected: musicPage.music && musicPage.music.currentLayout === 'reference-trio'
                    onClicked: if (musicPage.music) musicPage.music.setLayout('reference-trio')
                }
                HudButton {
                    id: layoutTraceBtn
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
                    id: layoutSplitBtn
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
                    id: layoutSegmentsBtn
                    objectName: 'layoutSegmentsBtn'
                    text: 'SEGMENTS'
                    height: 24
                    implicitWidth: 70
                    font.pixelSize: 10
                    font.letterSpacing: 0.2
                    selected: musicPage.music && musicPage.music.currentLayout === 'single-stack'
                    onClicked: if (musicPage.music) musicPage.music.setLayout('single-stack')
                }
            }

            Rectangle { width: 1; height: 16; color: '#253a47'; anchors.verticalCenter: parent.verticalCenter }

            // Dedicated Processing Status Badge (Separate from whether EQ editor is open)
            Rectangle {
                id: dspBadge
                height: 22
                width: dspRow.implicitWidth + 12
                radius: 3
                color: musicPage.music && !musicPage.music.eqBypass ? '#12251f' : '#192025'
                border.color: musicPage.music && !musicPage.music.eqBypass ? '#2d6852' : '#2b3b44'
                anchors.verticalCenter: parent.verticalCenter

                Row {
                    id: dspRow
                    anchors.centerIn: parent
                    spacing: 5
                    Rectangle {
                        width: 6
                        height: 6
                        radius: 3
                        color: musicPage.music && !musicPage.music.eqBypass ? '#2ed573' : '#657e8a'
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: musicPage.music && !musicPage.music.eqBypass ? 'DSP ACTIVE' : 'DSP BYPASS'
                        font.family: 'Segoe UI'
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                        color: musicPage.music && !musicPage.music.eqBypass ? '#6fe6ac' : '#7f95a1'
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
            }

            // On-Demand EQ Editor Toggle Button
            HudButton {
                id: layoutEQBtn
                objectName: 'layoutEQBtn'
                text: musicPage.showEQEditor ? 'EQ [OPEN]' : 'EQ'
                height: 24
                implicitWidth: 62
                font.pixelSize: 10
                font.letterSpacing: 0.3
                selected: musicPage.showEQEditor
                accent: musicPage.showEQEditor
                onClicked: musicPage.showEQEditor = !musicPage.showEQEditor
            }

            HudButton {
                id: musicEQToggle
                objectName: 'musicEQToggle'
                visible: false
                selected: musicPage.showEQEditor
                onClicked: musicPage.showEQEditor = !musicPage.showEQEditor
            }

            // Playlist Queue Toggle Button
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

    // 2. Useful Empty-State Message (When no track loaded in Cinematic/Orange view)
    Rectangle {
        id: emptyStatePill
        visible: musicPage.viewMode !== 'studio' && !musicPage.hasTrack
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: musicPage.showEQEditor ? eqPanel.top : transport.top
        anchors.bottomMargin: 14
        height: 28
        width: emptyRow.implicitWidth + 24
        color: '#b00b1720'
        border.color: '#344c58'
        radius: 14

        Row {
            id: emptyRow
            anchors.centerIn: parent
            spacing: 8
            Text {
                text: '♪'
                color: musicPage.gold
                font.pixelSize: 11
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: 'No audio track loaded · Drop audio file or click ＋ OPEN to begin playback'
                color: '#8da4ad'
                font.family: 'Segoe UI'
                font.pixelSize: 11
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }

    // 3. Technical Studio Visualizer Area (ONLY visible in STUDIO mode)
    Rectangle {
        id: analyzer
        objectName: 'musicAnalyzer'
        visible: musicPage.viewMode === 'studio'
        x: 8
        y: 50
        width: musicPage.mainWidth
        readonly property real availH: Math.max(160, musicPage.height - 50 - 58 - 8)
        readonly property real eqH: musicPage.showEQEditor ? Math.min(180, Math.max(140, availH * 0.32)) : 0
        height: musicPage.showEQEditor ? Math.max(120, availH - eqH - 6) : availH
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

    // 4. Compact On-Demand 10-Band EQ Editor (Anchored outside the core's bounds)
    EqualizerPanel {
        id: eqPanel
        objectName: 'musicEqualizerPanel'
        visible: musicPage.showEQEditor
        width: Math.min(760, musicPage.mainWidth)
        height: musicPage.stage && musicPage.stage.shortView ? 142 : 165
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: transport.top
        anchors.bottomMargin: 6
        music: musicPage.music
        onCloseRequested: musicPage.showEQEditor = false
    }

    // 5. Collapsible Playlist Queue Sidebar
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
                text: musicPage.music ? musicPage.music.queue.length + (musicPage.music.queue.length === 1 ? ' track' : ' tracks') : '0 tracks'
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
            model: musicPage.music ? musicPage.music.queue : []
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
                visible: !musicPage.music || musicPage.music.queue.length === 0
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
                model: [{ label: 'BASS', value: musicPage.music ? musicPage.music.bass : 0 }, { label: 'MID', value: musicPage.music ? musicPage.music.mid : 0 }, { label: 'HIGH', value: musicPage.music ? musicPage.music.treble : 0 }]
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

    // 6. Sleek Compact DAW-style Transport Bar (height: 48px)
    Rectangle {
        id: transport
        objectName: 'musicTransport'
        x: 8
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 4
        width: musicPage.mainWidth
        height: 48
        color: '#e60c1822'
        border.color: '#263b46'
        radius: 5

        // Seek Bar at top edge of transport
        MusicSlider {
            objectName: 'musicSeek'
            x: 4
            y: -6
            width: parent.width - 8
            height: 16
            from: 0
            to: Math.max(1, musicPage.music ? musicPage.music.duration : 1)
            stepSize: 1000
            value: musicPage.music ? musicPage.music.position : 0
            enabled: musicPage.music && musicPage.music.seekable
            onMoved: if (musicPage.music) musicPage.music.seek(value)
            Accessible.name: 'Track position'
        }

        // Transport Controls Row
        Row {
            x: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 7
            spacing: 6

            HudButton {
                objectName: 'musicPrevious'
                text: 'PREV'
                implicitWidth: 48
                height: 24
                font.pixelSize: 10
                enabled: musicPage.music && musicPage.music.hasTrack
                onClicked: musicPage.music.previous()
            }
            HudButton {
                objectName: 'musicPlay'
                text: musicPage.music && musicPage.music.playing ? 'PAUSE' : 'PLAY'
                implicitWidth: 58
                height: 24
                accent: true
                font.pixelSize: 10
                enabled: musicPage.music && musicPage.music.hasTrack
                onClicked: musicPage.music.togglePlayback()
            }
            HudButton {
                objectName: 'musicNext'
                text: 'NEXT'
                implicitWidth: 48
                height: 24
                font.pixelSize: 10
                enabled: musicPage.music && (musicPage.music.currentIndex + 1 < musicPage.music.queue.length)
                onClicked: musicPage.music.next()
            }
            HudButton {
                objectName: 'musicStop'
                text: 'STOP'
                implicitWidth: 48
                height: 24
                font.pixelSize: 10
                enabled: musicPage.music && musicPage.music.hasTrack
                onClicked: musicPage.music.stop()
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: musicPage.clock(musicPage.music ? musicPage.music.position : 0) + ' / ' + musicPage.clock(musicPage.music ? musicPage.music.duration : 0)
                font.family: 'Consolas'
                font.pixelSize: 10
                color: '#c8d3d1'
            }
        }

        // Center Status Text
        Text {
            anchors.centerIn: parent
            anchors.verticalCenterOffset: 3
            text: musicPage.music ? musicPage.music.status : ''
            textFormat: Text.PlainText
            color: musicPage.music && musicPage.music.captureState === 'error' ? '#e5a06c' : '#7e96a2'
            font.family: 'Segoe UI'
            font.pixelSize: 10
            elide: Text.ElideRight
            width: Math.min(360, parent.width * 0.32)
            horizontalAlignment: Text.AlignHCenter
        }

        // Right Volume & Mute Controls
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 10
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 7
            spacing: 6

            HudButton {
                objectName: 'musicMute'
                text: musicPage.music && musicPage.music.muted ? 'UNMUTE' : 'MUTE'
                implicitWidth: 54
                height: 24
                font.pixelSize: 10
                onClicked: if (musicPage.music) musicPage.music.setMuted(!musicPage.music.muted)
            }
            MusicSlider {
                objectName: 'musicVolume'
                width: 84
                height: 24
                anchors.verticalCenter: parent.verticalCenter
                from: 0
                to: 1
                value: musicPage.music ? musicPage.music.volume : 0.55
                onMoved: if (musicPage.music) musicPage.music.setVolume(value)
                Accessible.name: 'Music volume'
            }
        }
    }
}
