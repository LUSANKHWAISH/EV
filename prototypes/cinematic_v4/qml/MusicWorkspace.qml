import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs

Rectangle {
    id:musicPage
    objectName:'musicWorkspace'
    required property var music
    property bool reactionAllowed:true
    color:'#071119'
    readonly property real queueWidth:width<1100?220:270
    readonly property real mainWidth:width-queueWidth-26
    readonly property color gold:'#e1b463'
    onEnabledChanged:if(!enabled)files.close()
    function clock(ms){let s=Math.floor(ms/1000);return Math.floor(s/60)+':'+('0'+s%60).slice(-2)}
    component Caption:Text { color:'#78939f';font.pixelSize:10;font.letterSpacing:1.6 }
    component Picker:ComboBox {
        id:pick;implicitHeight:36;font.pixelSize:11
        contentItem:Text { text:pick.displayText;color:'#d3dcd9';font:pick.font;verticalAlignment:Text.AlignVCenter;leftPadding:12;rightPadding:25;elide:Text.ElideRight }
        background:Rectangle { color:'#11212a';border.color:pick.activeFocus?'#d1ac65':'#31434c';radius:3 }
    }
    component MusicSlider:Slider {
        id:slider
        background:Rectangle { x:slider.leftPadding;y:slider.topPadding+slider.availableHeight/2-2;width:slider.availableWidth;height:4;radius:2;color:'#263b46'
            Rectangle { width:slider.visualPosition*parent.width;height:4;radius:2;color:musicPage.gold }
        }
        handle:Rectangle { x:slider.leftPadding+slider.visualPosition*(slider.availableWidth-width);y:slider.topPadding+slider.availableHeight/2-6;width:12;height:12;radius:6;color:slider.pressed?'#ffecb5':musicPage.gold }
    }
    FileDialog {
        id:files;objectName:'musicFileDialog';title:'Add local music';fileMode:FileDialog.OpenFiles
        nameFilters:['Audio files (*.mp3 *.wav *.flac *.m4a *.aac *.ogg *.opus *.aif *.aiff *.wma)']
        onAccepted:if(musicPage.enabled)musicPage.music.addFiles(selectedFiles)
    }
    DropArea { anchors.fill:parent;onDropped:function(drop){if(drop.hasUrls){musicPage.music.addFiles(drop.urls);drop.acceptProposedAction()}} }
    Column {
        width:musicPage.mainWidth;spacing:12
        Caption { text:'MUSIC  /  AUDIO WORKSPACE';color:musicPage.gold }
        Text { width:parent.width;text:musicPage.music.title;textFormat:Text.PlainText;color:'#f0e8d8';font.family:'Segoe UI';font.pixelSize:musicPage.width<1100?25:33;font.weight:Font.Light;elide:Text.ElideRight }
        Text { width:parent.width;text:'Open or drop local tracks. Choose Windows audio to follow VLC, a browser or another player.';wrapMode:Text.WordWrap;font.pixelSize:12;color:'#91a7b0' }
        Row { spacing:8
            HudButton { objectName:'musicOpen';text:'＋  OPEN TRACKS';accent:true;width:150;onClicked:files.open() }
            HudButton { objectName:'musicInputPlayer';text:'E.V. PLAYER';selected:musicPage.music.inputSource==='player';onClicked:musicPage.music.setInput('player') }
            HudButton { objectName:'musicInputSystem';text:'WINDOWS AUDIO';width:150;selected:musicPage.music.inputSource==='system';onClicked:musicPage.music.setInput('system') }
        }
        Row { spacing:10
            Picker {
                objectName:'musicDevice';width:Math.min(300,musicPage.mainWidth-160)
                visible:musicPage.music.inputSource==='system'
                model:musicPage.music.captureDevices;textRole:'label';valueRole:'id'
                onActivated:musicPage.music.setCaptureDevice(currentValue)
                Accessible.name:'Windows output to visualize'
            }
            HudButton {
                objectName:'musicCaptureToggle';visible:musicPage.music.inputSource==='system';width:130
                text:musicPage.music.captureState==='active'||musicPage.music.captureState==='starting'?'STOP CAPTURE':'CONNECT'
                onClicked:{if(musicPage.music.captureState==='active'||musicPage.music.captureState==='starting')musicPage.music.stopCapture();else musicPage.music.startCapture()}
            }
            Picker { objectName:'musicOutput';visible:musicPage.music.inputSource==='player';width:Math.min(300,musicPage.mainWidth-160);model:musicPage.music.outputDevices;onActivated:musicPage.music.setOutputDevice(currentIndex);Accessible.name:'E.V. playback output' }
        }
    }
    Rectangle {
        id:analyzer;objectName:'musicAnalyzer';y:205;width:musicPage.mainWidth;height:Math.max(160,musicPage.height-355)
        color:'#0a1821';border.color:'#263b45';radius:5;clip:true
        Caption { x:20;y:17;text:'LIVE SPECTRUM';color:musicPage.gold }
        Text { anchors.right:parent.right;anchors.rightMargin:20;y:17;text:musicPage.music.rmsText+' RMS    '+musicPage.music.peakText+' PEAK';color:'#9cb0b8';font.family:'Consolas';font.pixelSize:11 }
        Canvas {
            id:spectrum;objectName:'musicSpectrum';x:42;y:48;width:parent.width-64;height:parent.height-88
            onWidthChanged:requestPaint();onHeightChanged:requestPaint()
            Connections { target:musicPage.music;function onAnalysisChanged(){spectrum.requestPaint()} }
            onPaint:{
                let c=getContext('2d');c.reset()
                c.lineWidth=1;c.strokeStyle='#1e323c'
                for(let j=0;j<5;j++){let y=j*(height-38)/4;c.beginPath();c.moveTo(0,y);c.lineTo(width,y);c.stroke()}
                let bars=musicPage.music.bands;let step=width/bars.length
                let g=c.createLinearGradient(0,0,0,height);g.addColorStop(0,'#ffe6a2');g.addColorStop(.5,'#db982d');g.addColorStop(1,'#62421f');c.fillStyle=g
                for(let i=0;i<bars.length;i++){let h=bars[i]*(height-40);if(h>.4)c.fillRect(i*step,height-38-h,Math.max(1,step-2),h)}
                let wave=musicPage.music.waveform;c.beginPath();c.strokeStyle='#99b5b5';c.lineWidth=1
                for(let k=0;k<wave.length;k++){let x=k*width/(wave.length-1),y=height-15-wave[k]*18;if(k===0)c.moveTo(x,y);else c.lineTo(x,y)}c.stroke()
            }
        }
        Column { x:8;y:45;spacing:Math.max(1,(analyzer.height-125)/4-10)
            Repeater { model:['0','−20','−40','−60','−80'];Text { required property string modelData;text:modelData;color:'#617f8e';font.family:'Consolas';font.pixelSize:9 } }
        }
        Item { x:42;y:parent.height-25;width:parent.width-64
            Repeater { model:['25 Hz','95','360','1.4k','5.3k','20k'];Text { required property string modelData;required property int index;x:index*(parent.width-width)/5;text:modelData;color:'#617f8e';font.family:'Consolas';font.pixelSize:10 } }
        }
    }
    Column {
        x:musicPage.mainWidth+26;width:musicPage.queueWidth;spacing:12
        Caption { text:'UP NEXT' }
        Text { text:musicPage.music.queue.length+(musicPage.music.queue.length===1?' local track':' local tracks');color:'#c5d0d0';font.pixelSize:18;font.weight:Font.Light }
        ListView {
            objectName:'musicQueue';width:parent.width;height:Math.max(120,musicPage.height-460);clip:true;spacing:6
            model:musicPage.music.queue;ScrollBar.vertical:ScrollBar{}
            delegate:HudButton {
                required property var modelData
                width:ListView.view.width;height:44;text:(modelData.index+1)+'   '+modelData.title
                selected:modelData.index===musicPage.music.currentIndex;onClicked:musicPage.music.playIndex(modelData.index)
            }
            Text { visible:musicPage.music.queue.length===0;anchors.fill:parent;text:'Add a few tracks,\nor visualize music\nalready playing.';color:'#6f8a98';font.pixelSize:13;lineHeight:1.6 }
        }
        Row { width:parent.width;spacing:8
            Repeater { model:[{label:'BASS',value:musicPage.music.bass},{label:'MID',value:musicPage.music.mid},{label:'HIGH',value:musicPage.music.treble}]
                Column { required property var modelData;width:(musicPage.queueWidth-16)/3;spacing:8
                    Caption { text:modelData.label;font.pixelSize:8 }
                    Rectangle { width:parent.width;height:3;color:'#253a43';Rectangle { width:parent.width*modelData.value;height:3;color:musicPage.gold } }
                }
            }
        }
    }
    Row { x:musicPage.mainWidth+26;y:musicPage.height-162;width:musicPage.queueWidth;spacing:8
        Rectangle { width:6;height:6;radius:3;y:2;color:musicPage.gold;opacity:.15+(musicPage.reactionAllowed?musicPage.music.beat*musicPage.music.reactionGain*.85:0) }
        Text { text:musicPage.music.reactionMode==='off'?'E.V.  /  REACTION OFF':musicPage.reactionAllowed?'E.V.  /  BEAT RESPONSE':'E.V.  /  REACTION PAUSED';color:'#b39762';font.pixelSize:9;font.letterSpacing:1.2 }
    }
    Rectangle {
        id:transport;objectName:'musicTransport';y:parent.height-128;width:parent.width;height:128;color:'#101e27';border.color:'#30454e';radius:5
        Row { x:18;y:12;spacing:8
            HudButton { objectName:'musicPrevious';text:'PREV';width:65;enabled:musicPage.music.hasTrack;onClicked:musicPage.music.previous() }
            HudButton { objectName:'musicPlay';text:musicPage.music.playing?'PAUSE':'PLAY';width:85;accent:true;enabled:musicPage.music.hasTrack;onClicked:musicPage.music.togglePlayback() }
            HudButton { objectName:'musicNext';text:'NEXT';width:65;enabled:musicPage.music.currentIndex+1<musicPage.music.queue.length;onClicked:musicPage.music.next() }
            HudButton { objectName:'musicStop';text:'STOP';width:65;enabled:musicPage.music.hasTrack;onClicked:musicPage.music.stop() }
            Text { y:11;text:musicPage.clock(musicPage.music.position)+' / '+musicPage.clock(musicPage.music.duration);font.family:'Consolas';font.pixelSize:12;color:'#c8d3d1' }
        }
        Row { anchors.right:parent.right;anchors.rightMargin:18;y:12;spacing:8
            HudButton { objectName:'musicMute';text:musicPage.music.muted?'UNMUTE':'MUTE';width:75;onClicked:musicPage.music.setMuted(!musicPage.music.muted) }
            MusicSlider { objectName:'musicVolume';width:120;from:0;to:1;value:musicPage.music.volume;onMoved:musicPage.music.setVolume(value);Accessible.name:'Music volume' }
        }
        MusicSlider { objectName:'musicSeek';x:18;y:53;width:parent.width-36;from:0;to:Math.max(1,musicPage.music.duration);stepSize:1000;value:musicPage.music.position;enabled:musicPage.music.seekable;onMoved:musicPage.music.seek(value);Accessible.name:'Track position' }
        Text { x:20;y:96;width:parent.width-40;text:musicPage.music.status;textFormat:Text.PlainText;color:musicPage.music.captureState==='error'?'#e5a06c':'#839ea9';font.pixelSize:11;elide:Text.ElideRight }
    }
}
