import QtQuick
import QtQuick.Controls

Column {
    id:settings
    objectName:'musicReactionSettings'
    required property var music
    required property bool musicActive
    spacing:12
    component Caption:Text { color:'#8b9fa7';font.pixelSize:12;wrapMode:Text.WordWrap }
    component Picker:ComboBox {
        id:pick;implicitHeight:36;font.pixelSize:12
        contentItem:Text { text:pick.displayText;color:'#d3dcd9';font:pick.font;verticalAlignment:Text.AlignVCenter;leftPadding:12;rightPadding:25;elide:Text.ElideRight }
        background:Rectangle { color:'#11212a';border.color:pick.activeFocus?'#d1ac65':'#31434c';radius:3 }
    }
    Rectangle { width:parent.width;height:1;color:'#23323a' }
    Text { text:'MUSIC REACTION';color:'#d9ae67';font.pixelSize:10;font.letterSpacing:2 }
    Picker {
        objectName:'musicReactionMode';width:parent.width
        model:['Music only','All modes','Off']
        currentIndex:['music','all','off'].indexOf(settings.music.reactionMode)
        Accessible.name:'Music reaction mode'
        onActivated:settings.music.setReactionMode(['music','all','off'][currentIndex])
    }
    Caption { text:'Reaction intensity  '+Math.round(settings.music.reactionIntensity*100)+'%';color:'#c7d1d2' }
    Slider {
        id:intensity;objectName:'musicReactionIntensity';width:parent.width
        from:0;to:1;stepSize:.05;value:settings.music.reactionIntensity
        enabled:settings.music.reactionMode!=='off'
        Accessible.name:'Music reaction intensity'
        onMoved:settings.music.setReactionIntensity(value)
        background:Rectangle {
            x:intensity.leftPadding;y:intensity.topPadding+intensity.availableHeight/2-height/2
            width:intensity.availableWidth;height:3;color:'#30434c';radius:2
            Rectangle { width:intensity.visualPosition*parent.width;height:3;color:'#d9ae67';radius:2 }
        }
        handle:Rectangle {
            x:intensity.leftPadding+intensity.visualPosition*(intensity.availableWidth-width)
            y:intensity.topPadding+intensity.availableHeight/2-height/2
            width:16;height:16;radius:8;color:intensity.pressed?'#fff0bc':'#d9ae67'
        }
    }
    Caption { width:parent.width;text:'Assistant uses 25% of this strength while idle. Listening, speaking and active tasks take priority.' }
    Row {
        width:parent.width;spacing:8
        HudButton { objectName:'reactionInputPlayer';width:(parent.width-8)/2;text:'E.V. PLAYER';selected:settings.music.inputSource==='player';onClicked:settings.music.setInput('player') }
        HudButton { objectName:'reactionInputSystem';width:(parent.width-8)/2;text:'WINDOWS AUDIO';selected:settings.music.inputSource==='system';onClicked:settings.music.setInput('system') }
    }
    Column {
        width:parent.width;spacing:10;visible:settings.music.inputSource==='system'
        Picker {
            objectName:'reactionCaptureDevice';width:parent.width
            model:settings.music.captureDevices;textRole:'label';valueRole:'id'
            currentIndex:indexOfValue(settings.music.captureDeviceId)
            onActivated:settings.music.setCaptureDevice(currentValue)
            Accessible.name:'Windows output for core reaction'
        }
        HudButton {
            objectName:'reactionCaptureToggle';width:parent.width
            readonly property bool capturing:settings.music.captureState==='active'||settings.music.captureState==='starting'
            text:capturing?'STOP CAPTURE':'CONNECT WINDOWS AUDIO'
            enabled:capturing||settings.musicActive||settings.music.reactionMode==='all'
            onClicked:{if(capturing)settings.music.stopCapture();else settings.music.startCapture()}
        }
        Caption { width:parent.width;text:settings.music.status;textFormat:Text.PlainText;font.pixelSize:11 }
        Caption { width:parent.width;text:'Follows the selected Windows output, including VLC, YouTube and other sounds. All modes keeps capture active in Assistant.';font.pixelSize:11 }
    }
    Caption { width:parent.width;visible:settings.music.reactionMode==='off';text:'Core reactions are off. Music mode’s spectrum remains available.';font.pixelSize:11 }
    Rectangle { width:parent.width;height:1;color:'#23323a' }
}
