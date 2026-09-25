import QtQuick

Item {
    id: composite
    objectName: "nucleusView"

    property string visualTheme: "cosmic_orbit"
    readonly property bool isStarkTheme: visualTheme === "stark_reactor"

    property var telemetry
    property real viewYaw: 0
    property real viewPitch: 0
    property real hoverX: 0
    property real hoverY: 0
    property real zoom: 1
    property bool expanded: false
    property bool showNodes: true
    property string hoveredModule: ""
    property real orbitTimeOverride: -1
    property real reactionOverride: -1
    property real musicBeat: 0
    property real explicitTextureWidth: classicView.explicitTextureWidth
    property real explicitTextureHeight: classicView.explicitTextureHeight

    readonly property bool lowCost: classicView.lowCost
    readonly property real launchProgress: classicView.deployment
    readonly property int particleCount: classicView.particleCount
    readonly property int orbitalParticleCount: classicView.orbitalParticleCount
    readonly property int rendererFps: classicView.renderStats ? classicView.renderStats.fps : 60
    readonly property real drawCalls: classicView.renderStats ? classicView.renderStats.drawCallCount : 0
    readonly property real drawnVertices: classicView.renderStats ? classicView.renderStats.drawVertexCount : 0
    readonly property real imageBytes: classicView.renderStats ? classicView.renderStats.imageDataSize : 0

    function pick(x, y) {
        if (isStarkTheme) {
            return starkView.pick(x, y)
        }
        return classicView.pick(x, y)
    }

    ShaderEffectSource {
        id: glowSource
        sourceItem: composite.isStarkTheme ? starkView : classicView
        hideSource: false
        live: true
        visible: false
        smooth: true
        textureSize: Qt.size(
            Math.max(1, Math.round(composite.width * (composite.lowCost ? 0.28 : 0.5))),
            Math.max(1, Math.round(composite.height * (composite.lowCost ? 0.28 : 0.5)))
        )
    }

    ShaderEffect {
        anchors.fill: parent
        property variant source: glowSource
        property vector2d texelStep: Qt.vector2d(1 / glowSource.textureSize.width, 1 / glowSource.textureSize.height)
        property real glowGain: composite.lowCost ? 0.68 : 0.95
        property int tapCount: composite.lowCost ? 5 : 13
        fragmentShader: "shaders/glow.frag.qsb"
    }

    // Classic Amber Core (Preserved for COSMIC ORBIT & default)
    NucleusView {
        id: classicView
        anchors.fill: parent
        visible: !composite.isStarkTheme
        telemetry: composite.telemetry
        viewYaw: composite.viewYaw
        viewPitch: composite.viewPitch
        hoverX: composite.hoverX
        hoverY: composite.hoverY
        zoom: composite.zoom
        expanded: composite.expanded
        showNodes: composite.showNodes
        hoveredModule: composite.hoveredModule
        orbitTimeOverride: composite.orbitTimeOverride
        reactionOverride: composite.reactionOverride
        musicBeat: composite.musicBeat
    }

    // Tony Stark Iron Man Cinematic Arc Reactor Core (Full Tech)
    StarkArcReactorCore {
        id: starkView
        anchors.fill: parent
        visible: composite.isStarkTheme
        telemetry: composite.telemetry
        viewYaw: composite.viewYaw
        viewPitch: composite.viewPitch
        hoverX: composite.hoverX
        hoverY: composite.hoverY
        zoom: composite.zoom
        expanded: composite.expanded
        showNodes: composite.showNodes
        hoveredModule: composite.hoveredModule
        orbitTimeOverride: composite.orbitTimeOverride
        reactionOverride: composite.reactionOverride
        musicBeat: composite.musicBeat
    }
}
