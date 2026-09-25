import QtQuick
import QtQuick.Controls

Item {
    id:stage
    objectName:'cinematicStage'
    property var model
    property var targetWindow
    readonly property var startupSound:model && !model.previewMode ? model.startupAudio : null
    readonly property bool musicActive:model && !model.previewMode && model.experienceMode==='MUSIC'
    readonly property var musicSession:model && !model.previewMode ? model.music : null
    readonly property bool musicReactionActive:enabled&&musicSession!==null&&model.animationEnabled&&model.musicReactionAllowed&&musicSession.analysisActive&&musicSession.reactionGain>0
    property bool expanded:false
    property bool checkerboard:false
    property bool recordingActive:false
    property bool cosmicDepthEnabled:true
    property int cosmicTheme:0
    property string visualTheme:'cosmic_orbit'
    property string drawer:''
    property bool geometryInitialized:false
    function initializeGeometry(){
        if (geometryInitialized || width <= 0 || height <= 0) return
        Qt.callLater(function(){
            if (width > 0 && height > 0) geometryInitialized=true
        })
    }
    onWidthChanged:initializeGeometry()
    onHeightChanged:initializeGeometry()
    readonly property bool compact:width<1360
    readonly property bool shortView:height<850
    readonly property real rail:compact?60:76
    readonly property real margin:compact?24:44
    readonly property real sideWidth:compact?208:260
    readonly property real contentLeft:rail+margin
    readonly property real centerX:rail+(width-rail)/2
    readonly property color amber:'#d9ae67'
    property alias nucleus:nucleus
    property alias composer:commandField
    signal closeRequested()

    component Label:Text { color:'#738992';font.family:'Segoe UI';font.pixelSize:10;font.letterSpacing:2 }
    component Rule:Rectangle { height:1;color:'#23323a' }
    component Meter:Item {
        property string label:''
        property string valueText:''
        property real value:0
        width:stage.sideWidth;height:63
        Text { text:parent.label;color:'#8e9fa6';font.pixelSize:11 }
        Text { text:parent.valueText;color:'#dfddd3';font.family:'Consolas';font.pixelSize:17;anchors.right:parent.right;y:-3 }
        Row { y:29;spacing:4
            Repeater { model:24
                Rectangle { required property int index;width:(stage.sideWidth-92)/24;height:3;color:index<Math.round(parent.parent.value/100*24)?'#b68b43':'#1a2a33' }
            }
        }
    }
    Rectangle { anchors.fill:parent;color:'#060c12' }
    Canvas {
        id:atmosphere;anchors.fill:parent
        onWidthChanged:requestPaint()
        onHeightChanged:requestPaint()
        onPaint:{
            let c=getContext('2d');c.reset()
            let g=c.createRadialGradient(stage.centerX,height*.40,10,stage.centerX,height*.40,Math.max(width*.45,height*.8))
            g.addColorStop(0,'#132126');g.addColorStop(.5,'#0a151d');g.addColorStop(1,'#050a10')
            c.fillStyle=g;c.fillRect(0,0,width,height)
            c.strokeStyle='rgba(76,106,116,.025)';c.lineWidth=1
            for(let x=stage.rail+18;x<width;x+=64){c.beginPath();c.moveTo(x,90);c.lineTo(x,height-20);c.stroke()}
            for(let y=122;y<height;y+=64){c.beginPath();c.moveTo(stage.rail,y);c.lineTo(width,y);c.stroke()}
            c.strokeStyle='rgba(79,111,126,.05)';c.beginPath();c.moveTo(stage.centerX,100);c.lineTo(stage.centerX,height-170);c.stroke()
        }
    }
    CosmicDepthField {
        id: cosmicDepthFieldLayer
        objectName: "cosmicDepthFieldLayer"
        anchors.fill: parent
        z: 0
        depthPass: 1
        coreCenterX: nucleus ? (nucleus.x + nucleus.width / 2) : (width / 2)
        coreCenterY: nucleus ? (nucleus.y + nucleus.height / 2) : (height / 2)
        visible: (stage.visualTheme === 'cosmic_orbit' || stage.visualTheme === 'stark_reactor' || stage.visualTheme === '') && stage.cosmicDepthEnabled && (stage.model ? stage.model.launchProgress > 0.15 : true)
        timeSeconds: stage.model ? stage.model.motionTime : 0
        deployment: stage.model ? stage.model.launchProgress : 1
        lowCost: stage.model ? stage.model.qualityMode : false
        colorTheme: stage.visualTheme === 'stark_reactor' ? 0 : stage.cosmicTheme
        activity: Math.max(
            0.0,
            Math.min(
                1.0,
                (stage.model ? Math.max(0.0, stage.model.glow - 1.0) : 0.0)
                + (
                    stage.musicReactionActive
                    ? stage.musicSession.beat
                      * stage.musicSession.reactionGain
                      * 0.35
                    : 0.0
                )
            )
        )
    }
    QuantumSingularityField {
        id: quantumSingularityRearLayer
        objectName: "quantumSingularityRearLayer"
        anchors.fill: parent
        z: 0
        depthPass: 1
        coreCenterX: nucleus ? (nucleus.x + nucleus.width / 2) : (width / 2)
        coreCenterY: nucleus ? (nucleus.y + nucleus.height / 2) : (height / 2)
        visible: stage.visualTheme === 'quantum_singularity' && stage.cosmicDepthEnabled && (stage.model ? stage.model.launchProgress > 0.15 : true)
        timeSeconds: stage.model ? stage.model.motionTime : 0
        deployment: stage.model ? stage.model.launchProgress : 1
        lowCost: stage.model ? stage.model.qualityMode : false
        activity: Math.max(
            0.0,
            Math.min(
                1.0,
                (stage.model ? Math.max(0.0, stage.model.glow - 1.0) : 0.0)
                + (
                    stage.musicReactionActive
                    ? stage.musicSession.beat
                      * stage.musicSession.reactionGain
                      * 0.35
                    : 0.0
                )
            )
        )
    }
    OrbitalAura {
        id: globalFireParticleLayer
        objectName: "globalFireParticleLayer"
        anchors.fill: parent

        // Keep the layer at the stage origin. Do not bind these values to
        // nucleus.x, nucleus.y, nucleus.width, nucleus.scale or view rotation.
        z: 0

        timeSeconds:
            stage.model ? stage.model.motionTime : 0

        deployment:
            stage.model ? stage.model.launchProgress : 1

        lowCost:
            stage.model ? stage.model.qualityMode : false

        activity: Math.max(
            0.0,
            Math.min(
                1.0,
                (stage.model ? Math.max(0.0, stage.model.glow - 1.0) : 0.0)
                + (
                    stage.musicReactionActive
                    ? stage.musicSession.beat
                      * stage.musicSession.reactionGain
                      * 0.20
                    : 0.0
                )
            )
        )
    }
    Repeater { model:stage.checkerboard?Math.ceil(stage.width/32)*Math.ceil(stage.height/32):0
        Rectangle { required property int index;readonly property int cols:Math.ceil(stage.width/32);width:32;height:32;x:(index%cols)*32;y:Math.floor(index/cols)*32;color:((index%cols)+Math.floor(index/cols))%2?'#252d32':'#131a20' }
    }
    Rectangle {
        width:stage.rail;height:parent.height;color:'#070d13'
        Rectangle { anchors.right:parent.right;width:1;height:parent.height;color:'#1b2b34' }
        Text { text:'E';anchors.horizontalCenter:parent.horizontalCenter;y:28;color:'#f1d19a';font.family:'Segoe UI';font.pixelSize:25;font.weight:Font.Light }
        Column { y:148;anchors.horizontalCenter:parent.horizontalCenter;spacing:20
            Repeater { model:[{key:'',glyph:'◈',label:'Assistant'},{key:'activity',glyph:'≡',label:'Activity'},{key:'system',glyph:'⌁',label:'System'},{key:'settings',glyph:'\u2699\ufe0e',label:'Settings'}]
                HudButton { required property var modelData;objectName:'nav_'+modelData.key;width:42;height:42;leftPadding:0;rightPadding:0;text:modelData.glyph;font.pixelSize:21;font.letterSpacing:0;quiet:true;selected:stage.drawer===modelData.key;Accessible.name:modelData.label;onClicked:{if(modelData.key===''&&!stage.model.previewMode)stage.model.openAssistant();stage.drawer=stage.drawer===modelData.key?'':modelData.key} ToolTip.visible:hovered;ToolTip.text:modelData.label }
            }
            HudButton { objectName:'nav_music';visible:!stage.model.previewMode;width:42;height:42;text:'♫';font.pixelSize:23;quiet:true;selected:stage.musicActive;Accessible.name:'Music';onClicked:{stage.drawer='';stage.model.openMusic()} }
        }
        Rectangle { anchors.horizontalCenter:parent.horizontalCenter;y:parent.height-83;width:6;height:6;radius:3;color:'#c49a58' }
        Text { anchors.horizontalCenter:parent.horizontalCenter;y:parent.height-58;text:'V4';color:'#536d79';font.pixelSize:9;font.letterSpacing:1 }
    }
    Item {
        id:header;x:stage.rail;width:parent.width-x;height:88
        MouseArea { anchors.fill:parent;onPressed:function(mouse){if(stage.targetWindow)stage.targetWindow.startSystemMove()} }
        Column { x:stage.margin;y:25;spacing:5
            Text { text:'E.V.';color:'#e7e8e1';font.family:'Segoe UI';font.pixelSize:23;font.letterSpacing:4;font.weight:Font.Light }
            Text { text:'ENHANCED VIRTUAL INTELLIGENCE';color:'#68828e';font.pixelSize:8;font.letterSpacing:2 }
        }
        Row { visible:!stage.compact;anchors.horizontalCenter:parent.horizontalCenter;y:28;spacing:8
            HudButton { objectName:'assistantButton';text:'ASSISTANT';quiet:true;selected:!stage.musicActive&&stage.drawer==='';onClicked:{stage.drawer='';if(!stage.model.previewMode)stage.model.openAssistant()} }
            HudButton { text:'ACTIVITY';quiet:true;selected:stage.drawer==='activity';onClicked:stage.drawer=stage.drawer==='activity'?'':'activity' }
            HudButton { text:'SYSTEM';quiet:true;selected:stage.drawer==='system';onClicked:stage.drawer=stage.drawer==='system'?'':'system' }
            HudButton { objectName:'musicButton';text:stage.model.previewMode?'MUSIC · MAIN APP':'MUSIC';quiet:true;enabled:!stage.model.previewMode;selected:stage.musicActive;Accessible.name:'Music mode';onClicked:{stage.drawer='';stage.model.openMusic()} }
        }
        Row { anchors.right:parent.right;anchors.rightMargin:24;y:27;spacing:12
            Text { text:stage.model.clockText;color:'#bdc8c9';font.family:'Consolas';font.pixelSize:15;anchors.verticalCenter:parent.verticalCenter }
            HudButton { text:'—';width:30;quiet:true;onClicked:if(stage.targetWindow)stage.targetWindow.showMinimized();Accessible.name:'Minimize window' }
            HudButton { text:'×';width:30;quiet:true;font.pixelSize:20;onClicked:stage.closeRequested();Accessible.name:'Close window' }
        }
        Rule { anchors.bottom:parent.bottom;x:stage.margin;width:parent.width-stage.margin*2 }
    }
    Row { x:stage.contentLeft;y:110;spacing:12
        Label { text:'WORKSPACE' }
        Text { text:'/';color:'#3d5662';font.pixelSize:10 }
        Label { text:stage.musicActive?'MUSIC':'PERSONAL ASSISTANT';color:'#a4ada8' }
    }
    Label { anchors.right:parent.right;anchors.rightMargin:stage.margin;y:110;text:stage.model.previewMode?'INTERFACE PREVIEW':'CONNECTED';color:'#a18a62' }
    HudButton {
        objectName:'backgroundAudioIndicator';anchors.right:parent.right;anchors.rightMargin:stage.margin;y:130
        width:240;height:25;quiet:true;font.pixelSize:9
        visible:!stage.musicActive&&stage.musicSession!==null&&stage.musicSession.inputSource==='system'&&stage.musicSession.captureState!=='off'
        text:'WINDOWS AUDIO · '+(stage.musicSession ? stage.musicSession.captureState.toUpperCase() : '')
        Accessible.name:'Windows audio capture status and settings'
        ToolTip.visible:hovered;ToolTip.text:stage.musicSession ? stage.musicSession.status : ''
        onClicked:stage.drawer='settings'
    }

    Column {
        id:contextRail;objectName:'contextRail';x:stage.contentLeft;y:stage.shortView?162:196;width:stage.sideWidth;spacing:stage.shortView?15:21
        visible:!stage.musicActive&&(!stage.expanded||!stage.compact)
        Label { text:'01 / CURRENT CONTEXT' }
        Text { text:stage.model.currentTask==='No active task'?'Standing by.':'Session active.';color:'#d8dedc';font.family:'Segoe UI';font.pixelSize:stage.compact?22:28;font.weight:Font.Light }
        Text { width:parent.width;text:stage.model.currentTask==='No active task'?'Your next idea starts here.\nTell E.V. what you have in mind.':stage.model.currentTask;textFormat:Text.PlainText;color:'#7f929b';font.pixelSize:12;lineHeight:1.5;wrapMode:Text.WordWrap;maximumLineCount:4;elide:Text.ElideRight }
        Rule { width:parent.width }
        Row { width:parent.width
            Label { text:'STATE';width:80 }
            Text { text:stage.model.visualState.split('_').join(' ');color:stage.amber;font.pixelSize:10;font.letterSpacing:1;elide:Text.ElideRight;width:parent.width-80 }
        }
        Row { Label { text:'MODE';width:80 } Text { text:stage.model.experienceMode;color:'#b2beba';font.pixelSize:10;font.letterSpacing:1 } }
        Row { Label { text:'VOICE';width:80 } Text { text:stage.model.previewMode?'SIMULATED':'BRIDGE LEVELS';color:'#7e919b';font.pixelSize:10;font.letterSpacing:1 } }
        Rule { width:parent.width }
        Label { text:'SESSION PATH' }
        Flow { width:parent.width;spacing:stage.shortView?10:12
        Repeater { model:stage.model.lifecycleSteps
            Row { required property string modelData;required property int index;spacing:12;width:stage.shortView?(contextRail.width-10)/2:contextRail.width;height:16
                Rectangle { width:5;height:5;radius:2.5;y:4;color:parent.modelData===stage.model.lifecycleStage?'#c99e52':'#32464e' }
                Text { text:modelData;color:modelData===stage.model.lifecycleStage?'#c5b389':'#5e7784';font.pixelSize:10;font.letterSpacing:1.7 }
            }
        }
        }
        HudButton { text:'VIEW ACTIVITY  ↗';width:parent.width;quiet:true;onClicked:stage.drawer='activity' }
    }
    NucleusScene {
        id:nucleus;telemetry:stage.model;expanded:stage.expanded
        visualTheme: stage.visualTheme
        z:stage.musicActive?12:0
        width:stage.musicActive?170:Math.min(stage.expanded?820:540,stage.height-(stage.shortView?340:220));height:width
        x:stage.musicActive?stage.width-stage.margin-(stage.width-stage.contentLeft-stage.margin<1100?220:270)/2-width/2:stage.centerX-width/2
        y:stage.musicActive?stage.height-385:stage.height*(stage.shortView?.40:.415)-height/2
        showNodes:!stage.musicActive
        musicBeat:stage.musicReactionActive?stage.musicSession.beat*stage.musicSession.reactionGain:0
        scale:1+musicBeat*.025
        reactionOverride:stage.musicReactionActive?Math.min(1,stage.musicSession.level*.2*stage.musicSession.reactionGain+musicBeat):!stage.model.animationEnabled?0:-1
        Behavior on x { enabled:stage.geometryInitialized;NumberAnimation { duration:600;easing.type:Easing.InOutCubic } }
        Behavior on y { enabled:stage.geometryInitialized;NumberAnimation { duration:600;easing.type:Easing.InOutCubic } }
        Behavior on width { enabled:stage.geometryInitialized;NumberAnimation { duration:600;easing.type:Easing.InOutCubic } }
    }
    CosmicDepthField {
        id: cosmicDepthFrontLayer
        objectName: "cosmicDepthFrontLayer"
        anchors.fill: parent
        z: stage.musicActive ? 0.2 : 1
        depthPass: 2
        coreCenterX: nucleus ? (nucleus.x + nucleus.width / 2) : (width / 2)
        coreCenterY: nucleus ? (nucleus.y + nucleus.height / 2) : (height / 2)
        visible: (stage.visualTheme === 'cosmic_orbit' || stage.visualTheme === 'stark_reactor' || stage.visualTheme === '') && stage.cosmicDepthEnabled && (stage.model ? stage.model.launchProgress > 0.15 : true)
        timeSeconds: stage.model ? stage.model.motionTime : 0
        deployment: stage.model ? stage.model.launchProgress : 1
        lowCost: stage.model ? stage.model.qualityMode : false
        colorTheme: stage.visualTheme === 'stark_reactor' ? 0 : stage.cosmicTheme
        activity: Math.max(
            0.0,
            Math.min(
                1.0,
                (stage.model ? Math.max(0.0, stage.model.glow - 1.0) : 0.0)
                + (
                    stage.musicReactionActive
                    ? stage.musicSession.beat
                      * stage.musicSession.reactionGain
                      * 0.35
                    : 0.0
                )
            )
        )
    }
    QuantumSingularityField {
        id: quantumSingularityFrontLayer
        objectName: "quantumSingularityFrontLayer"
        anchors.fill: parent
        z: stage.musicActive ? 0.2 : 1
        depthPass: 2
        coreCenterX: nucleus ? (nucleus.x + nucleus.width / 2) : (width / 2)
        coreCenterY: nucleus ? (nucleus.y + nucleus.height / 2) : (height / 2)
        visible: stage.visualTheme === 'quantum_singularity' && stage.cosmicDepthEnabled && (stage.model ? stage.model.launchProgress > 0.15 : true)
        timeSeconds: stage.model ? stage.model.motionTime : 0
        deployment: stage.model ? stage.model.launchProgress : 1
        lowCost: stage.model ? stage.model.qualityMode : false
        activity: Math.max(
            0.0,
            Math.min(
                1.0,
                (stage.model ? Math.max(0.0, stage.model.glow - 1.0) : 0.0)
                + (
                    stage.musicReactionActive
                    ? stage.musicSession.beat
                      * stage.musicSession.reactionGain
                      * 0.35
                    : 0.0
                )
            )
        )
    }
    MouseArea {
        id:interaction;objectName:'coreInteraction'
        enabled:!stage.musicActive
        x:nucleus.x;y:nucleus.y;width:nucleus.width;height:nucleus.height
        hoverEnabled:true;acceptedButtons:Qt.LeftButton;focus:false
        property real sx:0;property real sy:0;property real iy:0;property real ip:0
        property bool dragged:false;property string pending:''
        onPressed:function(mouse){stage.model.finishLaunch();forceActiveFocus();sx=mouse.x;sy=mouse.y;iy=nucleus.viewYaw;ip=nucleus.viewPitch;dragged=false}
        onPositionChanged:function(mouse){
            nucleus.hoverX=(mouse.x/width-.5)*2;nucleus.hoverY=(mouse.y/height-.5)*2
            if(pressed){let dx=mouse.x-sx,dy=mouse.y-sy;if(Math.hypot(dx,dy)>6){dragged=true;clickTimer.stop()};if(dragged){nucleus.viewYaw=iy+dx*.3;nucleus.viewPitch=Math.max(-18,Math.min(18,ip+dy*.15))}}
            else{let p=nucleus.pick(mouse.x,mouse.y);let n=p.objectHit?p.objectHit.objectName:'';nucleus.hoveredModule=n.indexOf('module_')===0?n.substring(7):''}
        }
        onExited:{nucleus.hoverX=0;nucleus.hoverY=0;nucleus.hoveredModule=''}
        onClicked:function(mouse){if(dragged)return;let p=nucleus.pick(mouse.x,mouse.y);pending=p.objectHit?p.objectHit.objectName:'';clickTimer.restart()}
        onDoubleClicked:{clickTimer.stop();pending='';stage.resetView()}
        onWheel:function(wheel){nucleus.zoom=Math.max(.85,Math.min(1.10,nucleus.zoom+wheel.angleDelta.y/120*.035));wheel.accepted=true}
        Keys.onSpacePressed:stage.expanded=!stage.expanded
        Timer { id:clickTimer;interval:Qt.styleHints.mouseDoubleClickInterval;onTriggered:{if(interaction.pending==='coreHit')stage.model.requestListening();else if(interaction.pending.indexOf('module_')===0)stage.model.requestPanel(interaction.pending.substring(7))} }
    }
    Column { visible:!stage.musicActive&&!stage.expanded&&!stage.shortView;anchors.horizontalCenter:nucleus.horizontalCenter;y:nucleus.y+nucleus.height-8;spacing:10
        Label { anchors.horizontalCenter:parent.horizontalCenter;text:'E . V .   N U C L E U S';color:'#b29868' }
        Label { anchors.horizontalCenter:parent.horizontalCenter;text:'DRAG TO EXPLORE  ·  SCROLL TO ZOOM';font.pixelSize:8;font.letterSpacing:1.7 }
    }
    HudButton { objectName:'expandButton';visible:!stage.musicActive;x:nucleus.x+nucleus.width-34;y:Math.max(140,nucleus.y+8);width:34;text:stage.expanded?'−':'+';font.pixelSize:20;quiet:true;Accessible.name:stage.expanded?'Reduce nucleus':'Expand nucleus';onClicked:stage.expanded=!stage.expanded }
    Text { visible:nucleus.hoveredModule!=='';text:nucleus.hoveredModule.toUpperCase();x:stage.centerX-width/2;y:stage.height*.68;color:'#d3b576';font.pixelSize:10;font.letterSpacing:2 }
    Column {
        id:telemetryRail;objectName:'telemetryRail';x:stage.width-stage.margin-stage.sideWidth;y:stage.shortView?162:196;width:stage.sideWidth;spacing:stage.shortView?12:18
        visible:!stage.musicActive&&(!stage.expanded||!stage.compact)
        Item { width:parent.width;height:12;Label { text:'02 / SYSTEM TELEMETRY' } Rectangle { width:4;height:4;radius:2;color:stage.model.telemetryAvailable?'#96bba2':'#596a72';anchors.right:parent.right;y:5 } }
        Text { text:'Local system';color:'#d8dedc';font.family:'Segoe UI';font.pixelSize:20;font.weight:Font.Light }
        Sparkline { width:parent.width;height:stage.shortView?40:67;samples:stage.model.cpuHistory }
        Meter { label:'PROCESSOR';valueText:stage.model.telemetryAvailable?stage.model.cpuPercent.toFixed(0)+'%':'—';value:stage.model.telemetryAvailable?stage.model.cpuPercent:0 }
        Meter { label:'MEMORY';valueText:stage.model.telemetryAvailable?stage.model.memoryPercent.toFixed(0)+'%':'—';value:stage.model.telemetryAvailable?stage.model.memoryPercent:0 }
        Meter { label:stage.model.previewMode?'STORAGE · D:':'STORAGE';valueText:stage.model.telemetryAvailable?stage.model.diskUsedPercent.toFixed(0)+'%':'—';value:stage.model.telemetryAvailable?stage.model.diskUsedPercent:0 }
        Rule { width:parent.width }
        Item { width:parent.width;height:13;Label { text:'MEMORY IN USE';font.pixelSize:8 } Text { anchors.right:parent.right;text:stage.model.telemetryAvailable?stage.model.memoryText:'—';color:'#8f9fa5';font.family:'Consolas';font.pixelSize:10 } }
        Item { width:parent.width;height:13;Label { text:stage.recordingActive?'CAPTURE TIMING':'RENDER TIMING';font.pixelSize:8 } Text { anchors.right:parent.right;text:stage.model.animationEnabled?stage.model.measuredFps.toFixed(0)+' FPS':'PAUSED';color:'#b8b393';font.family:'Consolas';font.pixelSize:10 } }
        HudButton { text:'SYSTEM DETAILS  ↗';quiet:true;width:parent.width;onClicked:stage.drawer='system' }
    }
    Column {
        id:response;objectName:'responseSurface'
        visible:!stage.musicActive
        width:Math.min(stage.width-stage.rail-stage.sideWidth*2-stage.margin*3,860)
        x:stage.centerX-width/2;y:stage.height-250;spacing:12
        Item { width:parent.width;height:14
            Label { text:'E.V.  /  RESPONSE';anchors.horizontalCenter:parent.horizontalCenter;color:'#8e9e9d' }
            HudButton { objectName:'readResponseButton';visible:stage.model.responseDetail.length>0;text:'OPEN RESPONSE ↗';font.pixelSize:8;quiet:true;width:145;height:22;y:-4;anchors.right:parent.right;onClicked:stage.drawer='response' }
        }
        Text { text:stage.model.responseTitle;anchors.horizontalCenter:parent.horizontalCenter;color:'#e4e5db';font.family:'Segoe UI';font.pixelSize:stage.shortView?23:28;font.weight:Font.Light;horizontalAlignment:Text.AlignHCenter;width:parent.width;maximumLineCount:1;elide:Text.ElideRight }
        Text { text:stage.model.responseDetail;textFormat:Text.PlainText;width:parent.width;horizontalAlignment:Text.AlignHCenter;color:'#8196a0';font.pixelSize:12;lineHeight:1.35;wrapMode:Text.WordWrap;maximumLineCount:2;elide:Text.ElideRight }
    }
    Rectangle {
        id:composerBox;objectName:'composerBox';width:Math.min(960,stage.width-stage.rail-stage.margin*2-120)
        visible:!stage.musicActive
        height:68;x:stage.centerX-width/2;y:stage.height-116
        color:'#0c1820';border.color:commandField.activeFocus?'#816d43':'#2c414b';border.width:1;radius:5
        Rectangle { width:34;height:2;anchors.horizontalCenter:parent.horizontalCenter;anchors.top:parent.top;color:'#bb934f';opacity:.65 }
        Text { x:22;anchors.verticalCenter:parent.verticalCenter;text:'›';font.pixelSize:29;color:'#bd9c60' }
        TextField { id:commandField;objectName:'commandInput';x:50;width:parent.width-167;height:parent.height;placeholderText:'Ask E.V. anything, or describe a task…';color:'#e0e7e4';placeholderTextColor:'#657f8c';font.pixelSize:14;selectByMouse:true;Accessible.name:'Command input';onAccepted:stage.sendCommand();background:Item{} }
        HudButton { objectName:'voiceButton';anchors.right:sendButton.left;anchors.rightMargin:8;anchors.verticalCenter:parent.verticalCenter;width:36;height:38;text:'◉';font.pixelSize:18;quiet:true;Accessible.name:'Request listening';onClicked:stage.model.requestListening() }
        HudButton { id:sendButton;objectName:'sendButton';anchors.right:parent.right;anchors.rightMargin:12;anchors.verticalCenter:parent.verticalCenter;width:43;height:38;text:'↗';font.pixelSize:23;accent:true;enabled:commandField.text.trim().length>0;Accessible.name:'Send command';onClicked:stage.sendCommand() }
    }
    Label { visible:!stage.musicActive;x:composerBox.x;y:stage.height-30;text:stage.model.previewMode?'PREVIEW SESSION · ACTIONS DISCONNECTED':'ENTER TO SEND · VOICE DOES NOT AUTHORIZE ACTIONS';font.pixelSize:8;font.letterSpacing:1.2 }
    Loader {
        id: musicLoader
        active: stage.musicActive
        z: 10
        x: stage.contentLeft
        y: 145
        width: stage.width - x - stage.margin
        height: stage.height - 190

        onLoaded: {
            if (item)
                item.color = "transparent"
        }

        sourceComponent: Component {
            MusicWorkspace {
                music: stage.model.music
                reactionAllowed: stage.musicReactionActive
            }
        }
    }
    Label { anchors.right:parent.right;anchors.rightMargin:stage.margin;y:stage.height-30;text:stage.model.dateText;font.pixelSize:8;font.letterSpacing:1.2 }
    Rectangle {
        id:drawerPanel;objectName:'drawerPanel';visible:stage.drawer!==''
        z:50;width:Math.min(480,stage.width-stage.rail-50);height:Math.min(740,stage.height-146)
        x:stage.width-width-stage.margin;y:106;color:'#101c24';border.color:'#40515a';radius:4
        MouseArea { anchors.fill:parent;acceptedButtons:Qt.AllButtons }
        ScrollView {
            id:drawerScroll;x:28;y:27;width:parent.width-56;height:parent.height-54;clip:true
        Column { width:drawerScroll.availableWidth;spacing:22
            Text { text:stage.drawer==='settings'?'Interface settings':stage.drawer==='activity'?'Session activity':stage.drawer==='response'?'E.V. response':'System overview';font.family:'Segoe UI';font.pixelSize:23;font.weight:Font.Light;color:'#e4e8e2' }
            Rule { width:parent.width }
            Column { visible:stage.drawer==='settings';width:parent.width;spacing:16
                Label { text:'RENDER PROFILE' }
                HudButton { objectName:'qualityToggle';width:parent.width;height:44;text:stage.model.qualityMode?'30 FPS · QUALITY / LIGHTER':'60 FPS · STANDARD';selected:true;onClicked:stage.model.setQuality(!stage.model.qualityMode) }
                Text { width:parent.width;text:'Quality mode reduces circuit detail, particle count, resolution and glow work.';color:'#8b9fa7';font.pixelSize:12;wrapMode:Text.WordWrap;lineHeight:1.4 }
                HudButton { objectName:'animationToggle';width:parent.width;text:stage.model.animationEnabled?'PAUSE ANIMATION':'RESUME ANIMATION';onClicked:stage.model.setAnimation(!stage.model.animationEnabled) }
                Loader {
                    width:parent.width;active:stage.musicSession!==null;visible:active
                    sourceComponent:Component { MusicReactionSettings { music:stage.musicSession;musicActive:stage.musicActive } }
                }
                HudButton { objectName:'replayLaunch';width:parent.width;text:'REPLAY CORE PROJECTION';enabled:stage.model.animationEnabled;onClicked:{stage.drawer='';stage.model.replayLaunch()} }
                HudButton { width:parent.width;text:'RESET VIEW';onClicked:stage.resetView() }
                HudButton { width:parent.width;text:stage.checkerboard?'HIDE COMPOSITING CHECK':'CHECK TRANSPARENCY';onClicked:stage.checkerboard=!stage.checkerboard }
                Rule { width:parent.width }
                Label { text:'APPEARANCE THEME' }
                Column {
                    width:parent.width;spacing:8
                    HudButton {
                        width:parent.width
                        text:'STARK ARC REACTOR (IRON MAN TECH)'
                        selected:stage.visualTheme === 'stark_reactor'
                        onClicked:stage.visualTheme = 'stark_reactor'
                    }
                    Row {
                        width:parent.width;spacing:8
                        HudButton {
                            width:(parent.width - 8)/2
                            text:'COSMIC ORBIT'
                            selected:stage.visualTheme === 'cosmic_orbit' || stage.visualTheme === ''
                            onClicked:stage.visualTheme = 'cosmic_orbit'
                        }
                        HudButton {
                            width:(parent.width - 8)/2
                            text:'QUANTUM SINGULARITY'
                            selected:stage.visualTheme === 'quantum_singularity'
                            onClicked:stage.visualTheme = 'quantum_singularity'
                        }
                    }
                }

                Column {
                    width:parent.width;spacing:10
                    visible:stage.visualTheme === 'cosmic_orbit' || stage.visualTheme === ''
                    Label { text:'COSMIC COLORWAYS' }
                    Row {
                        width:parent.width;spacing:8
                        HudButton {
                            width:(parent.width - 16)/3
                            text:'CYAN BLUE'
                            selected:stage.cosmicTheme === 0
                            onClicked:stage.cosmicTheme = 0
                        }
                        HudButton {
                            width:(parent.width - 16)/3
                            text:'SOLAR GOLD'
                            selected:stage.cosmicTheme === 1
                            onClicked:stage.cosmicTheme = 1
                        }
                        HudButton {
                            width:(parent.width - 16)/3
                            text:'HYBRID'
                            selected:stage.cosmicTheme === 2
                            onClicked:stage.cosmicTheme = 2
                        }
                    }
                }
                Rule { width:parent.width }
                Column {
                    visible:stage.startupSound!==null;width:parent.width;spacing:12
                    Label { text:'STARTUP SOUND' }
                    HudButton {
                        objectName:'startupSoundToggle';width:parent.width
                        text:stage.startupSound && stage.startupSound.muted ? 'STARTUP SOUND · MUTED' : 'STARTUP SOUND · ON'
                        selected:stage.startupSound && !stage.startupSound.muted
                        Accessible.name:'Mute startup sound'
                        onClicked:stage.startupSound.setMuted(!stage.startupSound.muted)
                    }
                    Text {
                        text:'Startup volume  '+Math.round((stage.startupSound ? stage.startupSound.volume : 0)*100)+'%'
                        color:'#c7d1d2';font.pixelSize:12
                    }
                    Slider {
                        id:startupVolume;objectName:'startupVolume';width:parent.width;from:0;to:1;stepSize:0.05
                        value:stage.startupSound ? stage.startupSound.volume : 0
                        enabled:stage.startupSound && !stage.startupSound.muted
                        Accessible.name:'Startup volume'
                        onMoved:stage.startupSound.setVolume(value)
                        background:Rectangle {
                            x:startupVolume.leftPadding;y:startupVolume.topPadding+startupVolume.availableHeight/2-height/2
                            width:startupVolume.availableWidth;height:3;radius:2;color:'#30434c'
                            Rectangle { width:startupVolume.visualPosition*parent.width;height:parent.height;color:stage.amber;radius:2 }
                        }
                        handle:Rectangle {
                            x:startupVolume.leftPadding+startupVolume.visualPosition*(startupVolume.availableWidth-width)
                            y:startupVolume.topPadding+startupVolume.availableHeight/2-height/2
                            width:16;height:16;radius:8;color:startupVolume.pressed?'#fff0be':stage.amber
                        }
                    }
                    Text {
                        width:parent.width;text:'Energy rise, arrival tone and “E.V. online.” play once when E.V. opens. Core replay is silent.'
                        color:'#8b9fa7';font.pixelSize:12;wrapMode:Text.WordWrap;lineHeight:1.4
                    }
                    Rule { width:parent.width }
                }
                HudButton { visible:!stage.model.previewMode;text:'AI PROVIDER SETTINGS';width:parent.width;onClicked:stage.model.openProviderSettings() }
                Label { visible:stage.model.previewMode;text:'PREVIEW STATE · AUDIO IS SIMULATED' }
                Flow { visible:stage.model.previewMode;width:parent.width;spacing:7
                    Repeater { model:['IDLE','LISTENING','THINKING','SPEAKING','EXECUTING','WAITING_FOR_APPROVAL','VERIFYING','SUCCESS','ERROR','DISCONNECTED']
                        HudButton { required property string modelData;width:modelData.length>15?parent.width:Math.floor((parent.width-7)/2);text:modelData.split('_').join(' ');font.pixelSize:9;selected:stage.model.visualState===modelData;onClicked:stage.model.setState(modelData) }
                    }
                }
            }
            Column { visible:stage.drawer==='system';width:parent.width;spacing:22
                Label { text:stage.model.telemetryAvailable?'SYSTEM MEASUREMENTS':'WAITING FOR TELEMETRY' }
                Text { text:stage.model.telemetryAvailable?stage.model.memoryText+' memory in use':'Memory measurement unavailable';color:'#c7d1d2';font.pixelSize:15 }
                Text { text:stage.model.telemetryAvailable?stage.model.processCount+' running processes':'Process measurement unavailable';color:'#c7d1d2';font.pixelSize:15 }
                Sparkline { width:parent.width;height:140;samples:stage.model.cpuHistory }
                Text { width:parent.width;text:stage.model.previewMode?'Processor samples are collected once per second. The chart shows observations from this preview session.':'The chart uses telemetry published by the existing E.V. bridge. No additional system monitor is started.';color:'#849ba6';font.pixelSize:12;lineHeight:1.5;wrapMode:Text.WordWrap }
                Rule { width:parent.width }
                Text { width:parent.width;text:stage.model.previewMode?'Voice amplitude is simulated in this preview. GPU memory and live voice contention have not been measured here.':'Voice levels come from the existing bridge. The speaking signal is synthetic, not measured PCM playback.';color:'#a29880';font.pixelSize:12;lineHeight:1.5;wrapMode:Text.WordWrap }
            }
            Column { visible:stage.drawer==='response';width:parent.width;spacing:20
                Label { text:'FULL RESPONSE' }
                TextArea { objectName:'fullResponseText';width:parent.width;text:stage.model.responseDetail;textFormat:TextEdit.PlainText;readOnly:true;selectByMouse:true;wrapMode:TextEdit.Wrap;leftPadding:0;rightPadding:0;font.pixelSize:14;color:'#d4dfdf';selectionColor:'#695335';selectedTextColor:'#fff4db';background:Item{} }
                Text { width:parent.width;text:'Select text to copy · Ctrl+A selects the response';font.pixelSize:10;color:'#8198a1' }
            }
            Column { visible:stage.drawer==='activity';width:parent.width;spacing:18
                Label { text:stage.model.previewMode?'THIS PREVIEW SESSION':'SESSION RESPONSES' }
                Text { visible:stage.model.history.length===0;width:parent.width;text:stage.model.previewMode?'No messages yet.\nYour preview inputs will appear here.':'No responses yet.\nCompleted results will appear here.';color:'#8199a5';font.pixelSize:14;lineHeight:1.7 }
                ScrollView { width:parent.width;height:Math.min(420,drawerPanel.height-245);clip:true
                    Column { width:parent.width;spacing:20
                        Repeater { model:stage.model.history
                            Column { required property var modelData;width:parent.width;spacing:8
                                Label { text:modelData.time+' / '+modelData.status;font.pixelSize:8 }
                                Text { text:modelData.text;textFormat:Text.PlainText;width:parent.width;color:'#d6deda';font.pixelSize:13;wrapMode:Text.Wrap }
                                Rule { width:parent.width }
                            }
                        }
                    }
                }
                HudButton { text:'CLEAR SESSION HISTORY';width:parent.width;onClicked:stage.model.clearHistory() }
            }
        }
        }
        HudButton { x:parent.width-52;y:20;width:30;height:30;text:'×';font.pixelSize:20;quiet:true;Accessible.name:'Close panel';onClicked:stage.drawer='' }
    }
    Shortcut { sequence:'Esc';enabled:stage.enabled&&stage.drawer!=='';onActivated:stage.drawer='' }
    Connections { target:stage.model
        function onNavigationRequested(name){if(name==='telemetry')stage.drawer='system';else if(name==='lifecycle')stage.drawer='activity';else if(name==='result')stage.drawer='response';else if(name==='mode')stage.drawer='settings';else if(name==='command')commandField.forceActiveFocus()}
    }
    function resetView(){nucleus.viewYaw=0;nucleus.viewPitch=0;nucleus.zoom=1}
    function sendCommand(){let text=commandField.text.trim();if(text.length){stage.model.submitCommand(text);commandField.clear()}}
}
