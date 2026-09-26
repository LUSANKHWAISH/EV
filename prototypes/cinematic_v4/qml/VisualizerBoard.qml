import QtQuick

Item {
    id: root
    required property var music
    property real panelGap: 6

    readonly property string currentLayout: root.music && root.music.currentLayout ? root.music.currentLayout : 'reference-trio'
    readonly property bool spanVisible: currentLayout === 'studio-span'
    readonly property bool rainVisible: !spanVisible && (currentLayout === 'reference-trio' || currentLayout === 'single-rain')
    readonly property bool traceVisible: !spanVisible && (currentLayout === 'reference-trio' || currentLayout === 'single-trace' || currentLayout === 'split-duo')
    readonly property bool stackVisible: !spanVisible && (currentLayout === 'reference-trio' || currentLayout === 'split-duo' || currentLayout === 'single-stack')

    PrecisionSpectrum {
        id: span
        objectName: 'precisionSpectrum'
        music: root.music
        visible: root.spanVisible
        anchors.fill: parent
    }

    CeilingRain {
        id: rain
        objectName: 'ceilingRain'
        music: root.music
        visible: root.rainVisible
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: root.currentLayout === 'single-rain' ? parent.height : Math.max(60, Math.round(parent.height * 0.48))
    }

    FlowTrace {
        id: trace
        objectName: 'flowTrace'
        music: root.music
        visible: root.traceVisible
        anchors.left: parent.left
        anchors.right: root.stackVisible ? stack.left : parent.right
        anchors.rightMargin: root.stackVisible ? root.panelGap : 0
        anchors.top: root.rainVisible ? rain.bottom : parent.top
        anchors.topMargin: root.rainVisible ? root.panelGap : 0
        anchors.bottom: parent.bottom
    }

    SegmentStack {
        id: stack
        objectName: 'segmentStack'
        music: root.music
        visible: root.stackVisible
        anchors.left: root.currentLayout === 'single-stack' ? parent.left : undefined
        anchors.right: parent.right
        anchors.top: root.rainVisible ? rain.bottom : parent.top
        anchors.topMargin: root.rainVisible ? root.panelGap : 0
        anchors.bottom: parent.bottom
        width: root.currentLayout === 'single-stack' ? parent.width : (root.currentLayout === 'split-duo' ? Math.max(140, Math.round(parent.width * 0.35)) : Math.max(130, Math.round(parent.width * 0.30)))
    }
}
