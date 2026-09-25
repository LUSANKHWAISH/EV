import QtQuick
import QtQuick.Window

Window {
    id:window
    objectName:'cinematicWindow'
    title:'E.V. — Cinematic interface preview'
    width:1920;height:1080
    minimumWidth:1100;minimumHeight:760
    visible:true;color:'#060c12'
    flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowSystemMenuHint|Qt.WindowMinMaxButtonsHint
    property alias expanded:stage.expanded
    property alias checkerboard:stage.checkerboard
    property alias recordingActive:stage.recordingActive
    property alias drawer:stage.drawer
    CinematicStage { id:stage;anchors.fill:parent;model:lab;targetWindow:window;expanded:startExpanded;onCloseRequested:window.close() }
    Shortcut { sequence:'F11';onActivated:window.visibility=window.visibility===Window.FullScreen?Window.Windowed:Window.FullScreen }
}
