import QtQuick
import QtQuick3D
import EVLab 1.0

View3D {
    id: cosmicField
    objectName: "cosmicDepthFieldLayer"

    property real timeSeconds: 0
    property real deployment: 1
    property real activity: 0
    property bool lowCost: false
    property int colorTheme: 0 // 0 = Celestial Blue (Video style), 1 = Solar Gold, 2 = Hybrid
    property int depthPass: 0  // 0 = all, 1 = rear only (Z <= 5), 2 = front only (Z > 5)
    property real orbitSpeed: 1.0
    property real gain: 1.30
    property real coverage: 1.0

    property real coreCenterX: width / 2
    property real coreCenterY: height / 2

    readonly property real cameraDistance: 382.0
    readonly property real baseFieldOfView: 38.0
    readonly property real referenceProjectionHeight: 760.0
    readonly property real projectionRatio:
        height / Math.max(1.0, referenceProjectionHeight)

    readonly property real compensatedFieldOfView: Math.min(
        120.0,
        Math.max(
            10.0,
            2.0 * Math.atan(
                projectionRatio
                * Math.tan(baseFieldOfView * Math.PI / 360.0)
            ) * 180.0 / Math.PI
        )
    )

    // World units per screen pixel at Z=0
    readonly property real pixelToWorld:
        2.0
        * cameraDistance
        * Math.tan(compensatedFieldOfView * Math.PI / 360.0)
        / Math.max(1.0, height)

    visible: deployment > 0.15
    renderMode: View3D.Inline

    environment: SceneEnvironment {
        backgroundMode: SceneEnvironment.Transparent
        clearColor: "transparent"
        depthTestEnabled: true
        depthPrePassEnabled: false
        antialiasingMode: SceneEnvironment.NoAA
        tonemapMode: SceneEnvironment.TonemapModeNone
    }

    camera: PerspectiveCamera {
        position: Qt.vector3d(0, 0, cosmicField.cameraDistance)
        fieldOfView: cosmicField.compensatedFieldOfView
        clipNear: 10
        clipFar: 1800
    }

    Node {
        id: cosmicFieldFrame
        objectName: "cosmicFieldFrame"
        position: Qt.vector3d(
            (cosmicField.coreCenterX - cosmicField.width / 2) * cosmicField.pixelToWorld,
            -(cosmicField.coreCenterY - cosmicField.height / 2) * cosmicField.pixelToWorld,
            0
        )

        Model {
            id: cosmicModel
            objectName: "cosmicParticles"
            source: "#Rectangle"
            castsShadows: false

            instancing: CosmicDepthInstances {
                id: cosmicInstances
            }

            materials: CustomMaterial {
                shadingMode: CustomMaterial.Unshaded
                depthDrawMode: Material.NeverDepthDraw
                cullMode: Material.NoCulling

                // Additive blending for ethereal luminous cosmic depth
                sourceBlend: CustomMaterial.SrcAlpha
                destinationBlend: CustomMaterial.One
                sourceAlphaBlend: CustomMaterial.One
                destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha

                property real timeSeconds: cosmicField.timeSeconds
                property real deployment: cosmicField.deployment
                property real activity: Math.max(0.0, Math.min(1.0, cosmicField.activity))
                property real pixelToWorld: cosmicField.pixelToWorld
                property real gain: cosmicField.gain
                property real coverage: cosmicField.coverage
                property int colorTheme: cosmicField.colorTheme
                property int depthPass: cosmicField.depthPass
                property real orbitSpeed: cosmicField.orbitSpeed

                vertexShader: "shaders/cosmic_depth.vert"
                fragmentShader: "shaders/cosmic_depth.frag"
            }
        }
    }
}
