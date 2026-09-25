import QtQuick
import QtQuick3D
import EVLab 1.0

View3D {
    id: singularityField
    objectName: "quantumSingularityFieldLayer"

    property real timeSeconds: 0
    property real deployment: 1
    property real activity: 0
    property bool lowCost: false
    property int depthPass: 0  // 0 = all, 1 = rear only (Z <= 0), 2 = front only (Z > 0)
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
        position: Qt.vector3d(0, 0, singularityField.cameraDistance)
        fieldOfView: singularityField.compensatedFieldOfView
        clipNear: 10
        clipFar: 1800
    }

    Node {
        id: singularityFieldFrame
        objectName: "singularityFieldFrame"
        position: Qt.vector3d(
            (singularityField.coreCenterX - singularityField.width / 2) * singularityField.pixelToWorld,
            -(singularityField.coreCenterY - singularityField.height / 2) * singularityField.pixelToWorld,
            0
        )

        Model {
            id: singularityModel
            objectName: "singularityParticles"
            source: "#Rectangle"
            castsShadows: false

            instancing: CosmicDepthInstances {
                id: singularityInstances
            }

            materials: CustomMaterial {
                shadingMode: CustomMaterial.Unshaded
                depthDrawMode: Material.NeverDepthDraw
                cullMode: Material.NoCulling

                // Additive blending for relativistic luminous glow
                sourceBlend: CustomMaterial.SrcAlpha
                destinationBlend: CustomMaterial.One
                sourceAlphaBlend: CustomMaterial.One
                destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha

                property real timeSeconds: singularityField.timeSeconds
                property real deployment: singularityField.deployment
                property real activity: Math.max(0.0, Math.min(1.0, singularityField.activity))
                property real pixelToWorld: singularityField.pixelToWorld
                property real gain: singularityField.gain
                property real coverage: singularityField.coverage
                property int depthPass: singularityField.depthPass
                property real orbitSpeed: singularityField.orbitSpeed

                vertexShader: "shaders/quantum_singularity.vert"
                fragmentShader: "shaders/quantum_singularity.frag"
            }
        }
    }
}
