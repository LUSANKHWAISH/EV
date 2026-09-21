import QtQuick
import QtQuick3D

CustomMaterial {
    id: material
    property int kind: 0
    property real timeSeconds: 0
    property real gain: 1
    property real coverage: 1
    property real lowCost: 0
    property real seed: 0
    property real deployment: 1
    property real reaction: 0
    property real beatPulse: 0


    property url textureSource: kind===0 ? "../assets/circuit.png" : "../assets/flow.png"
    property TextureInput detailMap: TextureInput {
        texture: Texture {
            source: material.textureSource
            tilingModeHorizontal: Texture.Repeat
            tilingModeVertical: Texture.Repeat
            generateMipmaps: true
            minFilter: Texture.Linear
            magFilter: Texture.Linear
            mipFilter: Texture.Linear
        }
    }
    property TextureInput flowMap: TextureInput {
        texture: Texture {
            source: "../assets/flow.png"
            tilingModeHorizontal: Texture.Repeat
            tilingModeVertical: Texture.Repeat
            minFilter: Texture.Linear
            magFilter: Texture.Linear
        }
    }
    shadingMode: CustomMaterial.Unshaded
    sourceBlend: CustomMaterial.SrcAlpha
    destinationBlend: CustomMaterial.One
    sourceAlphaBlend: CustomMaterial.One
    destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha
    depthDrawMode: Material.NeverDepthDraw
    cullMode: Material.NoCulling
    vertexShader: "shaders/surface.vert"
    fragmentShader: "shaders/surface.frag"
}
