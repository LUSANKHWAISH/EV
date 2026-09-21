import QtQuick

Item {
    id: composite
    objectName: "nucleusView"
    property alias telemetry: view.telemetry
    property alias viewYaw: view.viewYaw
    property alias viewPitch: view.viewPitch
    property alias hoverX: view.hoverX
    property alias hoverY: view.hoverY
    property alias zoom: view.zoom
    property alias expanded: view.expanded
    property alias showNodes: view.showNodes
    property alias hoveredModule: view.hoveredModule
    property alias orbitTimeOverride: view.orbitTimeOverride
    property alias reactionOverride: view.reactionOverride
    property alias musicBeat: view.musicBeat
    property alias explicitTextureWidth: view.explicitTextureWidth
    property alias explicitTextureHeight: view.explicitTextureHeight
    readonly property bool lowCost: view.lowCost
    readonly property real launchProgress: view.deployment
    readonly property int particleCount: view.particleCount
    readonly property int orbitalParticleCount: view.orbitalParticleCount
    readonly property int rendererFps: view.renderStats.fps
    readonly property real drawCalls: view.renderStats.drawCallCount
    readonly property real drawnVertices: view.renderStats.drawVertexCount
    readonly property real imageBytes: view.renderStats.imageDataSize
    function pick(x,y) { return view.pick(x,y) }

    ShaderEffectSource {
        id: glowSource
        sourceItem: view
        hideSource: false
        live: true
        visible: false
        smooth: true
        textureSize: Qt.size(Math.max(1,Math.round(composite.width*(composite.lowCost ? .28 : .5))),
                             Math.max(1,Math.round(composite.height*(composite.lowCost ? .28 : .5))))
    }
    ShaderEffect {
        anchors.fill: parent
        property variant source: glowSource
        property vector2d texelStep: Qt.vector2d(1/glowSource.textureSize.width,1/glowSource.textureSize.height)
        property real glowGain: composite.lowCost ? .68 : .95
        property int tapCount: composite.lowCost ? 5 : 13
        fragmentShader: "shaders/glow.frag.qsb"
    }
    NucleusView { id: view; anchors.fill: parent }
}
