import QtQuick
import QtQuick.Window
import "../../../gui/qml/components" as Existing

Window {
    id:window
    objectName:'cinematicWindow'
    title:'E.V. — Cinematic interface'
    width:1920;height:1080;minimumWidth:1100;minimumHeight:760
    visible:true;color:'#060c12'
    flags:Qt.Window|Qt.FramelessWindowHint|Qt.WindowSystemMenuHint|Qt.WindowMinMaxButtonsHint|Qt.WindowCloseButtonHint
    CinematicStage { id:stage;anchors.fill:parent;enabled:!approvalSurface.visible&&!providerSurface.visible&&!(typeof guiBridge !== "undefined" && guiBridge && guiBridge.settingsVisible);model:lab;targetWindow:window;onCloseRequested:window.close() }
    // Existing authority and provider surfaces retain their controller and top-level priority.
    Existing.EVSettingsOverlay { id:providerSurface;objectName:'settingsOverlay';anchors.fill:parent;z:80;cinematic:true }
    Existing.EVApprovalOverlay { id:approvalSurface;objectName:'approvalOverlay';anchors.fill:parent;z:100 }
    Shortcut { sequence:'F11';enabled:!guiBridge.approvalPending;onActivated:window.visibility=window.visibility===Window.FullScreen?Window.Windowed:Window.FullScreen }
}
