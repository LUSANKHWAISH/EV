import QtQuick

Item {
    id: root
    required property var music
    property real panelGap: 8

    CeilingRain {
        id: rain
        objectName: 'ceilingRain'
        music: root.music
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: Math.max(48, parent.height * 0.34)
    }

    FlowTrace {
        id: trace
        objectName: 'flowTrace'
        music: root.music
        anchors.left: parent.left
        anchors.right: stack.left
        anchors.leftMargin: 0
        anchors.rightMargin: root.panelGap
        anchors.top: rain.bottom
        anchors.topMargin: root.panelGap
        anchors.bottom: parent.bottom
    }

    SegmentStack {
        id: stack
        objectName: 'segmentStack'
        music: root.music
        anchors.right: parent.right
        anchors.top: rain.bottom
        anchors.topMargin: root.panelGap
        anchors.bottom: parent.bottom
        width: Math.max(110, parent.width * 0.27)
    }
}
