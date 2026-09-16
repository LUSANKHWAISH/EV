import QtQuick
import QtQuick3D
import EVLab 1.0

View3D {
    id: scene
    objectName: "renderView"
    property var telemetry
    property real viewYaw: 0
    property real viewPitch: 0
    property real hoverX: 0
    property real hoverY: 0
    property real zoom: 1
    property bool expanded: false
    property bool showNodes: true
    property string hoveredModule: ""
    readonly property real t: telemetry ? telemetry.motionTime : 0
    // Diagnostics isolate internal orientation and local emission from camera/time.
    property real orbitTimeOverride: -1
    property real reactionOverride: -1
    property real musicBeat: 0
    readonly property real orbitTime: orbitTimeOverride>=0 ? orbitTimeOverride : t
    readonly property real reaction: reactionOverride>=0 ? Math.min(1,reactionOverride) : Math.max(0,Math.min(1,(energy-1.2)*1.7+level*.3))
    CoreMotion { id: motion; clock: scene.orbitTime; response: scene.reaction }
    component CoreMaterial: HoloMaterial {
        reaction:scene.reaction
        beatPulse:Math.max(0,Math.min(1,scene.musicBeat))
    }
    readonly property real deployment: telemetry ? telemetry.launchProgress : 1
    function phase(a,b) { let v=Math.max(0,Math.min(1,(deployment-a)/(b-a)));return v*v*(3-2*v) }
    readonly property real travel: phase(.03,.38)
    readonly property vector3d projectionPosition: Qt.vector3d(-64*(1-travel)+10*Math.sin(Math.PI*travel),-72*(1-travel)+28*Math.sin(Math.PI*travel),12)
    readonly property real energy: telemetry ? telemetry.glow : 1
    readonly property real level: telemetry ? telemetry.audioLevel : 0
    readonly property bool lowCost: telemetry ? telemetry.qualityMode : false
    readonly property int particleCount: fieldInstances.instanceCountOverride
    renderStats.extendedDataCollectionEnabled: true
    renderMode: View3D.Offscreen
    explicitTextureWidth: Math.round(width*(lowCost ? .78 : 1))
    explicitTextureHeight: Math.round(height*(lowCost ? .78 : 1))
    environment: SceneEnvironment {
        backgroundMode: SceneEnvironment.Transparent
        clearColor: "transparent"
        depthTestEnabled: true
        depthPrePassEnabled: false
        antialiasingMode: SceneEnvironment.MSAA
        antialiasingQuality: SceneEnvironment.High
        tonemapMode: SceneEnvironment.TonemapModeFilmic
    }
    camera: PerspectiveCamera {
        position: Qt.vector3d(0,0,382/Math.min(scene.zoom,1.10))
        fieldOfView: 38
        clipNear: 10; clipFar: 1200
    }
    Node {
        visible: scene.deployment<.7
        Model {
            geometry: LabGeometry { mesh: 'launch_trail' }
            materials: HoloMaterial { kind:7;deployment:scene.deployment;gain:2.4 }
        }
        Model {
            source:'#Rectangle'
            position:scene.projectionPosition
            scale:Qt.vector3d(.26,.26,1)
            materials:HoloMaterial { kind:6;deployment:scene.deployment;gain:2.2 }
        }
    }
    Node {
        id: assembly
        objectName: "coreAssembly"
        position:Qt.vector3d(scene.projectionPosition.x,scene.projectionPosition.y,0)
        eulerRotation: Qt.vector3d(Math.max(-20,Math.min(20,scene.viewPitch+scene.hoverY*1.5+Math.sin(scene.t*.21)*1.1)),
                                  scene.viewYaw+scene.hoverX*2.3+scene.t*.65-75*(1-scene.phase(.12,.8)),-35*(1-scene.phase(.16,.82)))
        readonly property real growth:.035+.965*scene.phase(.16,.86)+.035*Math.sin(scene.phase(.65,1)*Math.PI)
        scale: Qt.vector3d(growth,growth,growth)
        Repeater3D {
            model: 3
            delegate: Model {
                id: shellPatch
                required property int index
                geometry: LabGeometry { mesh: "shell_"+shellPatch.index }
                readonly property real s: [1,.86,.65][index]
                scale: Qt.vector3d(s,s,s)
                eulerRotation: Qt.vector3d([6,-31,48][index],[9,47,-23][index]+scene.orbitTime*[1.2,-1.8,.7][index],[-6,19,31][index])
                materials: CoreMaterial {
                    deployment: scene.deployment
                    kind: 0; timeSeconds: scene.t; seed: shellPatch.index*.31
                    gain: scene.energy*1.4
                    coverage: [2.15,1.05,.85][shellPatch.index]
                    lowCost: scene.lowCost ? 1 : 0
                    textureSource: scene.lowCost ? "../assets/circuit_low.png" : "../assets/circuit.png"
                }
            }
        }
        Model {
            geometry: LabGeometry { mesh: scene.lowCost ? "circuit_routes_low" : "circuit_routes" }
            eulerRotation: Qt.vector3d(-3,scene.orbitTime*.85,9)
            materials: CoreMaterial { deployment: scene.deployment; kind: 3; timeSeconds: scene.t; gain: scene.energy*2.0; coverage: .95 }
        }
        Model {
            objectName:'energyPaths'
            geometry: LabGeometry { mesh: scene.lowCost ? 'neural_paths_low' : 'neural_paths' }
            eulerRotation:Qt.vector3d(8,scene.orbitTime*.65,-8)
            materials:CoreMaterial { kind:5;timeSeconds:scene.t;gain:scene.energy*2.0;coverage:1.1;deployment:scene.deployment }
        }
        Model {
            objectName: "goldDischarges"
            geometry: LabGeometry { mesh: scene.lowCost ? "gold_discharges_low" : "gold_discharges" }
            eulerRotation: Qt.vector3d(0,scene.orbitTime*.65,0)
            materials: CoreMaterial { kind:8;timeSeconds:scene.t;gain:scene.energy*2.4;coverage:1.45;deployment:scene.deployment }
        }
        Model {
            geometry: LabGeometry { mesh: "peripheral_schematics" }
            scale: Qt.vector3d(.92,.92,.92)
            eulerRotation: Qt.vector3d(3,8+scene.orbitTime*.45,-7)
            materials: CoreMaterial { deployment: scene.deployment; kind: 3; timeSeconds: scene.t; gain: scene.energy*2.1; coverage: 1.6 }
        }
        Model {
            geometry: LabGeometry { mesh: "plates" }
            eulerRotation: Qt.vector3d(-8,scene.orbitTime*.6,8)
            materials: CoreMaterial { deployment: scene.deployment; timeSeconds: scene.t; gain: scene.energy*1.3; coverage: 1.4; lowCost: scene.lowCost ? 1 : 0; textureSource: scene.lowCost ? "../assets/circuit_low.png" : "../assets/circuit.png" }
        }
        Repeater3D {
            model: 3
            delegate: Node {
                id: bandNode
                required property int index
                objectName: "orbitalArc"+index
                eulerRotation: motion.arcRotation(index)
                position: Qt.vector3d([0,-4,7,-2,0,5][index],[0,3,-3,0,-4,0][index],index%2 ? -3 : 4)
                Model {
                    geometry: LabGeometry { mesh: ['flow_band_outer','flow_band_outer','flow_band_mid'][bandNode.index] }
                    materials: CoreMaterial { deployment: scene.deployment; kind: 1; timeSeconds: scene.t; seed: bandNode.index*.2; gain: scene.energy*2.3; coverage: [2.4,2.15,2.1][bandNode.index]; textureSource: "../assets/bands.png" }
                }
                Model {
                    visible: bandNode.index < 1
                    geometry: LabGeometry { mesh: "rails" }
                    materials: CoreMaterial { deployment: scene.deployment; kind: 3; timeSeconds: scene.t; gain: scene.energy*1.3; coverage: .58 }
                }
            }
        }
        Node {
            objectName: "innerHub"
            position: Qt.vector3d(0,0,16)
            eulerRotation: motion.hubRotation
            scale: Qt.vector3d(1.18,1.18,1.18)
            Model {
                objectName: "coreFilaments"
                pickable: false
                geometry: LabGeometry { mesh: "core_filaments" }
                materials: CoreMaterial { deployment: scene.deployment; kind: 2; timeSeconds: scene.t; gain: scene.energy*1.8; coverage: 1.65 }
            }
            Model {
                objectName: "innerCounterLoop"
                geometry: LabGeometry { mesh: "core_filaments" }
                eulerRotation: motion.counterRotation
                scale: Qt.vector3d(.8,.8,.8)
                materials: CoreMaterial { deployment: scene.deployment; kind: 2; timeSeconds: scene.t+2; gain: scene.energy*1.8; coverage: .75 }
            }
            Model {
                objectName: "coreHit"
                pickable: true
                source: "#Sphere"
                scale: Qt.vector3d(.44,.44,.44)
                materials: PrincipledMaterial { lighting: PrincipledMaterial.NoLighting; alphaMode: PrincipledMaterial.Blend; baseColor: Qt.rgba(0,0,0,.001); depthDrawMode: Material.NeverDepthDraw }
            }
        }
        Model {
            geometry: LabGeometry { mesh: "streams" }
            eulerRotation: Qt.vector3d(18+Math.sin(scene.orbitTime*.3)*8,13,scene.orbitTime*8-19)
            z: 12
            materials: CoreMaterial { deployment: scene.deployment; kind: 2; timeSeconds: scene.t; gain: scene.energy*1.6; coverage: .64 }
        }
        Model {
            objectName: "innerEnergyFilaments"
            geometry: LabGeometry { mesh: scene.lowCost ? "energy_ribbons_low" : "energy_ribbons" }
            eulerRotation: Qt.vector3d(5,-10+Math.sin(scene.orbitTime*.27)*10,-scene.orbitTime*5)
            z: 14
            materials: CoreMaterial { deployment: scene.deployment; kind: 4; timeSeconds: scene.t; gain: scene.energy*2.3; coverage: 1.8 }
        }
        Model {
            source: "#Rectangle"
            castsShadows: false
            instancing: ParticleInstances { id: fieldInstances; instanceCountOverride: scene.lowCost ? 1024 : 3072 }
            materials: CustomMaterial {
                shadingMode: CustomMaterial.Unshaded
                depthDrawMode: Material.NeverDepthDraw; cullMode: Material.NoCulling
                sourceBlend: CustomMaterial.SrcAlpha; destinationBlend: CustomMaterial.One
                sourceAlphaBlend: CustomMaterial.One; destinationAlphaBlend: CustomMaterial.OneMinusSrcAlpha
                property real timeSeconds: scene.t
                property real activity: scene.reaction
                property real gain: scene.energy*1.5
                property real coverage: .75
                property real deployment: scene.deployment
                vertexShader: "shaders/particles.vert"; fragmentShader: "shaders/particles.frag"
            }
        }
        Repeater3D {
            model: scene.showNodes && scene.deployment===1 ? ['telemetry','lifecycle','command','result','mode'] : []
            delegate: Node {
                id: satellite
                required property string modelData
                required property int index
                readonly property real a: index*Math.PI*2/5+.3+scene.t*.009
                position: Qt.vector3d(Math.cos(a)*108,Math.sin(a)*104,Math.sin(a)*14)
                Model {
                    source: "#Cube"
                    scale: Qt.vector3d(.014,.014,.014)
                    eulerRotation: Qt.vector3d(0,0,45)
                    materials: PrincipledMaterial { lighting: PrincipledMaterial.NoLighting; baseColor: scene.hoveredModule===satellite.modelData ? '#fff1c9' : '#be8b32' }
                }
                Model {
                    objectName: "module_"+satellite.modelData
                    pickable: true; source: "#Sphere"
                    scale: Qt.vector3d(.10,.10,.10)
                    materials: PrincipledMaterial { lighting: PrincipledMaterial.NoLighting; alphaMode: PrincipledMaterial.Blend; baseColor: Qt.rgba(1,.5,.1,.001); depthDrawMode: Material.NeverDepthDraw }
                }
            }
        }
    }
}
