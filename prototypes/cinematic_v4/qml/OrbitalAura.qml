import QtQuick
import QtQuick3D
import EVLab 1.0

View3D {
    id: aura
    objectName: "globalFireParticleLayer"

    property real timeSeconds: 0
    property real deployment: 1
    property real activity: 0
    property bool lowCost: false
    property int depthLayerMode: 0

    readonly property int activeCount: lowCost ? 520 : 1400
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

    // Number of world units represented by one screen pixel at Z=0.
    readonly property real pixelToWorld:
        2.0
        * cameraDistance
        * Math.tan(compensatedFieldOfView * Math.PI / 360.0)
        / Math.max(1.0, height)

    visible: deployment > 0.35
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
        position: Qt.vector3d(0, 0, aura.cameraDistance)
        fieldOfView: aura.compensatedFieldOfView
        clipNear: 10
        clipFar: 1400
    }

    Node {
        id: globalFireParticleFrame
        objectName: "globalFireParticleFrame"

        // This node deliberately has no core position, scale or rotation
        // bindings. Its transform remains in the persistent stage coordinate
        // system while the nucleus moves independently.

        Model {
            id: particleModel
            objectName: "orbitalAuraParticles"
            source: "#Rectangle"
            castsShadows: false

            instancing: OrbitalParticleInstances {
                id: orbitalInstances
                instanceCountOverride: aura.activeCount
            }

            materials: CustomMaterial {
                shadingMode: CustomMaterial.Unshaded
                depthDrawMode: Material.NeverDepthDraw
                cullMode: Material.NoCulling

                sourceBlend: CustomMaterial.SrcAlpha
                destinationBlend: CustomMaterial.OneMinusSrcAlpha
                sourceAlphaBlend: CustomMaterial.One
                destinationAlphaBlend:
                    CustomMaterial.OneMinusSrcAlpha

                property real timeSeconds: aura.timeSeconds
                property real deployment: aura.deployment
                property real activity: Math.max(
                    0.0,
                    Math.min(1.0, aura.activity)
                )
                property real pixelToWorld: aura.pixelToWorld

                property real gain: aura.lowCost ? 1.12 : 1.30
                property real coverage: aura.lowCost ? 0.90 : 1.00

                property real leftPanelBoundary: 0.22
                property real rightPanelBoundary: 0.82
                property real topNavigationBoundary: 0.12
                property real bottomResponseBoundary: 0.26

                property int depthLayerMode: aura.depthLayerMode

                vertexShader: "shaders/orbital_particles.vert"
                fragmentShader: "shaders/orbital_particles.frag"
            }
        }
    }
}