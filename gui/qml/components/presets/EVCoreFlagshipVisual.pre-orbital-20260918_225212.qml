import QtQuick 2.15
import QtQuick3D
import QtQuick3D.Helpers
import QtQuick3D.AssetUtils

// E.V. NUCLEUS v3.0 — REACTIVE VOLUMETRIC GOLD INTELLIGENCE SPHERE
// Presentation only. Six deterministic GLB layers provide the real 3D form.
// A plain transparent SceneEnvironment preserves alpha without a viewport box.

Item {
    id: root
    objectName: "flagshipIntelligenceField"
    anchors.fill: parent
    clip: true

    property var host: parent

    readonly property string visualState:
        host && host.visualState !== undefined ? String(host.visualState) : "IDLE"
    readonly property string previousVisualState:
        host && host.previousVisualState !== undefined ? String(host.previousVisualState) : visualState
    readonly property var visualProfile:
        host && host.visualProfile !== undefined ? host.visualProfile : ({})
    readonly property real visualTransitionProgress:
        host && host.visualTransitionProgress !== undefined ? Number(host.visualTransitionProgress) : 1.0
    readonly property bool visualAnimationEnabled:
        host && host.visualAnimationEnabled !== undefined ? Boolean(host.visualAnimationEnabled) : true
    readonly property real phase:
        host && host.phase !== undefined ? Number(host.phase) : 0.0
    readonly property real pulse:
        host && host.pulse !== undefined ? Number(host.pulse) : (Math.sin(phase) + 1.0) * 0.5
    readonly property real slowPulse:
        host && host.slowPulse !== undefined ? Number(host.slowPulse) : (Math.sin(phase * 0.48) + 1.0) * 0.5
    readonly property real coreBreath:
        host && host.coreBreath !== undefined ? Number(host.coreBreath) : 1.0
    readonly property real glowDrive:
        host && host.glowDrive !== undefined ? Number(host.glowDrive) : 0.58
    readonly property real satelliteSpeed:
        host && host.satelliteSpeed !== undefined ? Number(host.satelliteSpeed) : 0.34
    readonly property real effectiveListenLevel:
        host && host.effectiveListenLevel !== undefined ? Number(host.effectiveListenLevel) : 0.0
    readonly property real effectiveSpeechLevel:
        host && host.effectiveSpeechLevel !== undefined ? Number(host.effectiveSpeechLevel) : 0.0
    readonly property real profileMotion:
        visualProfile && visualProfile.motion !== undefined ? Number(visualProfile.motion) : 0.22
    readonly property real profileNucleus:
        visualProfile && visualProfile.nucleus !== undefined ? Number(visualProfile.nucleus) : 0.30
    readonly property real profileCamera:
        visualProfile && visualProfile.camera !== undefined ? Number(visualProfile.camera) : 0.08

    readonly property bool idleState: visualState === "IDLE"
    readonly property bool awareState: visualState === "AWARE" || visualState === "VERIFYING_WAKE"
    readonly property bool listeningState: visualState === "LISTENING"
    readonly property bool thinkingState: visualState === "THINKING" || visualState === "PROCESSING" || visualState === "PLANNING"
    readonly property bool speakingState: visualState === "SPEAKING"
    readonly property bool executingState: visualState === "EXECUTING"
    readonly property bool verifyingState: visualState === "VERIFYING"
    readonly property bool approvalState: visualState === "WAITING_FOR_APPROVAL" || visualState === "AWAITING_APPROVAL"
    readonly property bool successState: visualState === "SUCCESS"
    readonly property bool failedState: visualState === "ERROR" || visualState === "FAILED" || visualState === "RECOVERING"
    readonly property bool stoppedState: visualState === "SLEEP" || visualState === "STOPPED"

    readonly property color primaryTone:
        failedState ? "#ff3b24" :
        successState ? "#8dff91" :
        approvalState ? "#ffb21d" :
        verifyingState ? "#ffe06a" :
        speakingState ? "#ffe7a1" :
        listeningState ? "#ffc344" :
        "#ff9418"
    readonly property color secondaryTone:
        failedState ? "#ff7850" :
        successState ? "#d4ff9c" :
        approvalState ? "#ff6a0b" :
        speakingState ? "#fff0c2" :
        "#ff5b0a"

    readonly property real signalDrive:
        listeningState ? effectiveListenLevel :
        speakingState ? effectiveSpeechLevel :
        thinkingState ? 0.30 + pulse * 0.28 :
        executingState ? 0.58 + pulse * 0.30 :
        verifyingState ? 0.38 + slowPulse * 0.20 :
        approvalState ? 0.44 + slowPulse * 0.12 :
        0.10 + slowPulse * 0.07
    readonly property real transitionEase: {
        var p = clamp01(visualTransitionProgress)
        return 1.0 - Math.pow(1.0 - p, 3.0)
    }
    readonly property real motionDrive:
        0.70 + Math.max(0.0, satelliteSpeed) * 0.68 + profileMotion * 0.55
    readonly property real layerSpread:
        approvalState ? 17.0 :
        executingState ? 12.0 + pulse * 5.0 :
        listeningState ? 5.0 + effectiveListenLevel * 11.0 :
        speakingState ? 6.0 + effectiveSpeechLevel * 10.0 :
        failedState ? 9.0 + pulse * 5.0 : 4.0
    readonly property real assemblyScale:
        (stoppedState ? 0.84 : 0.985 + signalDrive * 0.045 + interactionPulse * 0.035)
        * (0.91 + transitionEase * 0.09) * coreBreath
    readonly property real cameraDepth:
        listeningState ? 800.0 - effectiveListenLevel * 32.0 :
        speakingState ? 800.0 - effectiveSpeechLevel * 28.0 :
        executingState ? 776.0 : 800.0
    readonly property bool localAnimationRunning:
        visible && visualAnimationEnabled && !stoppedState

    property real hoverX: 0.0
    property real hoverY: 0.0
    property real interactionPulse: 0.0

    function clamp01(value) {
        return Math.max(0.0, Math.min(1.0, Number(value)))
    }
    function rgba(colorValue, alphaValue) {
        return "rgba(" + Math.round(colorValue.r * 255) + ","
             + Math.round(colorValue.g * 255) + ","
             + Math.round(colorValue.b * 255) + "," + clamp01(alphaValue) + ")"
    }
    function spinDuration(baseMs) {
        var stateBoost = thinkingState ? 1.42 : executingState ? 1.75 :
                         (listeningState || speakingState) ? 1.24 + signalDrive * 0.65 : 1.0
        return Math.max(1900, Math.round(baseMs / (motionDrive * stateBoost)))
    }
    function repaintHologram() {
        ambientAura.requestPaint()
        holoCanvas.requestPaint()
    }

    onPrimaryToneChanged: repaintHologram()
    onSecondaryToneChanged: repaintHologram()
    onVisualStateChanged: repaintHologram()
    onSignalDriveChanged: repaintHologram()
    onPhaseChanged: repaintHologram()
    Component.onCompleted: repaintHologram()

    Canvas {
        id: ambientAura
        anchors.centerIn: parent
        width: Math.max(1, Math.min(root.width, root.height) * 1.16)
        height: width
        opacity: root.stoppedState ? 0.06 : 0.22 + root.signalDrive * 0.08
        antialiasing: true
        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            var cx = width * 0.5
            var cy = height * 0.5
            var radius = width * 0.49
            var glow = ctx.createRadialGradient(cx, cy, width * 0.05, cx, cy, radius)
            glow.addColorStop(0.0, root.rgba(root.primaryTone, 0.12 + root.signalDrive * 0.08))
            glow.addColorStop(0.22, root.rgba(root.secondaryTone, 0.052))
            glow.addColorStop(0.55, root.rgba(root.primaryTone, 0.012))
            glow.addColorStop(1.0, "rgba(0,0,0,0)")
            ctx.fillStyle = glow
            ctx.fillRect(0, 0, width, height)
        }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    Item {
        id: coreViewport
        objectName: "intelligenceField"
        anchors.centerIn: parent
        width: Math.max(1, Math.min(root.width * 0.94, root.height * 0.985, 900))
        height: width
        opacity: root.stoppedState ? 0.28 : 1.0
        onWidthChanged: root.repaintHologram()
        onHeightChanged: root.repaintHologram()

        View3D {
            id: field
            objectName: "intelligenceView3D"
            anchors.fill: parent
            camera: intelligenceCamera
            environment: SceneEnvironment {
                id: sceneEnvironment
                backgroundMode: SceneEnvironment.Transparent
                clearColor: "transparent"
                antialiasingMode: SceneEnvironment.MSAA
                antialiasingQuality: SceneEnvironment.High
                temporalAAEnabled: false
                specularAAEnabled: true
                tonemapMode: SceneEnvironment.TonemapModeFilmic
            }

            PerspectiveCamera {
                id: intelligenceCamera
                objectName: "intelligenceCamera"
                position: Qt.vector3d(root.hoverX * 12.0, -7.0 - root.hoverY * 9.0, root.cameraDepth)
                eulerRotation: Qt.vector3d(-0.55 + root.hoverY * 0.82, -root.hoverX * 1.10, 0)
                fieldOfView: 37
                clipNear: 1
                clipFar: 1900
            }

            DirectionalLight {
                eulerRotation: Qt.vector3d(-36, -31, 4)
                color: "#ffd08a"
                brightness: 0.62 + root.glowDrive * 0.09
                castsShadow: false
            }
            DirectionalLight {
                eulerRotation: Qt.vector3d(142, 42, 16)
                color: root.secondaryTone
                brightness: 0.22 + root.signalDrive * 0.12
                castsShadow: false
            }
            PointLight {
                position: Qt.vector3d(-65, 20, 235)
                color: root.primaryTone
                brightness: 7.4 + root.glowDrive * 2.6 + root.signalDrive * 3.2
                constantFade: 1.0
                linearFade: 0.007
                quadraticFade: 0.000045
                castsShadow: false
            }
            PointLight {
                position: Qt.vector3d(165, -110, 130)
                color: root.secondaryTone
                brightness: 4.8 + root.signalDrive * 2.0
                constantFade: 1.0
                linearFade: 0.009
                quadraticFade: 0.000065
                castsShadow: false
            }

            Node {
                id: sceneRoot
                objectName: "nucleusAssembly3D"
                position: Qt.vector3d(
                    root.failedState ? Math.sin(root.phase * 6.0) * 2.5 : 0,
                    11 + (root.failedState ? Math.cos(root.phase * 5.0) * 2.0 : 0),
                    0)
                scale: Qt.vector3d(root.assemblyScale, root.assemblyScale, root.assemblyScale)
                eulerRotation: Qt.vector3d(
                    -7.0 + root.hoverY * 8.5 + Math.sin(root.phase * 0.23) * 0.75,
                    11.0 + root.hoverX * 10.5 + Math.cos(root.phase * 0.21) * 0.85,
                    root.executingState ? Math.sin(root.phase) * 2.4 : Math.sin(root.phase * 0.32) * 0.65)
                opacity: root.stoppedState ? 0.24 : 1.0

                Node {
                    id: deepStructureGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, -42 - root.layerSpread * 0.45)
                    eulerRotation: Qt.vector3d(-4 + Math.sin(root.phase * .31) * 2.2,
                                                     7 + Math.cos(root.phase * .27) * 2.0,
                                                     spinZ)
                    RuntimeLoader {
                        id: deepStructureAsset
                        objectName: "evV3DeepStructureAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_deep_structure.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: 360
                        duration: root.spinDuration(48000)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }

                Node {
                    id: outerLatticeGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, -13 - root.layerSpread * 0.20)
                    scale: Qt.vector3d(1 + root.signalDrive*.014, 1 + root.signalDrive*.014, 1 + root.signalDrive*.014)
                    eulerRotation: Qt.vector3d(13 + Math.sin(root.phase*.42)*3.0,
                                                     -17 + Math.cos(root.phase*.38)*3.4,
                                                     spinZ)
                    RuntimeLoader {
                        id: outerLatticeAsset
                        objectName: "evV3OuterLatticeAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_outer_lattice.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: -360
                        duration: root.spinDuration(33500)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }

                Node {
                    id: innerLatticeGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, 18 + root.layerSpread * 0.34)
                    scale: Qt.vector3d(1 + root.signalDrive*.025, 1 + root.signalDrive*.025, 1 + root.signalDrive*.025)
                    eulerRotation: Qt.vector3d(-21 + Math.cos(root.phase*.54)*4.6,
                                                     26 + Math.sin(root.phase*.49)*5.2,
                                                     spinZ)
                    RuntimeLoader {
                        id: innerLatticeAsset
                        objectName: "evV3InnerLatticeAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_inner_lattice.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: 360
                        duration: root.spinDuration(root.thinkingState ? 12800 : 22000)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }

                Node {
                    id: coreVortexGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, 50 + root.layerSpread * 0.72 + root.interactionPulse * 5)
                    scale: Qt.vector3d(0.98 + root.signalDrive*.10 + root.interactionPulse*.07,
                                           0.98 + root.signalDrive*.10 + root.interactionPulse*.07,
                                           0.98 + root.signalDrive*.10 + root.interactionPulse*.07)
                    eulerRotation: Qt.vector3d(Math.sin(root.phase*.73)*7.0,
                                                     Math.cos(root.phase*.69)*8.0,
                                                     spinZ)
                    RuntimeLoader {
                        id: coreVortexAsset
                        objectName: "evV3CoreVortexAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_core_vortex.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: -360
                        duration: root.spinDuration(root.speakingState ? 7600 : 14200)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }

                Node {
                    id: fragmentGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, 27 + root.layerSpread * 0.20)
                    eulerRotation: Qt.vector3d(17 + Math.sin(root.phase*.33)*5,
                                                     -12 + Math.cos(root.phase*.29)*5,
                                                     spinZ)
                    RuntimeLoader {
                        id: fragmentAsset
                        objectName: "evV3FragmentAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_fragments.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: 360
                        duration: root.spinDuration(root.executingState ? 9200 : 27200)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }

                Node {
                    id: nodesGroup
                    property real spinZ: 0
                    position: Qt.vector3d(0, 0, 62 + root.layerSpread * 0.55)
                    scale: Qt.vector3d(1 + root.signalDrive*.045, 1 + root.signalDrive*.045, 1 + root.signalDrive*.045)
                    eulerRotation: Qt.vector3d(-28 + Math.sin(root.phase*.45)*8,
                                                     20 + Math.cos(root.phase*.40)*8,
                                                     spinZ)
                    RuntimeLoader {
                        id: nodesAsset
                        objectName: "evV3NodesAsset"
                        source: Qt.resolvedUrl("../../assets/ev_v3_nodes.glb")
                    }
                    NumberAnimation on spinZ {
                        from: 0; to: -360
                        duration: root.spinDuration((root.listeningState || root.speakingState) ? 9800 : 19000)
                        loops: Animation.Infinite
                        running: root.localAnimationRunning
                    }
                }
            }
        }

        // Thin transparent calibration marks complement, but never replace, the 3D GLBs.
        Canvas {
            id: holoCanvas
            anchors.fill: parent
            opacity: root.stoppedState ? 0.06 : 0.26 + root.signalDrive * 0.09
            antialiasing: true
            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)
                var cx = width * 0.5
                var cy = height * 0.5
                var base = width * 0.405
                for (var i = 0; i < 18; ++i) {
                    var r = base * (0.66 + i * 0.021)
                    var start = (i * 47 + root.phase * (3 + i % 4)) * Math.PI / 180
                    var span = (18 + (i * 19) % 74) * Math.PI / 180
                    ctx.beginPath()
                    ctx.arc(cx, cy, r, start, start + span, false)
                    ctx.strokeStyle = root.rgba(i % 4 === 0 ? root.secondaryTone : root.primaryTone,
                                                0.20 + (i % 3) * 0.055)
                    ctx.lineWidth = i % 5 === 0 ? 1.5 : 0.7
                    ctx.stroke()
                }
                for (var t = 0; t < 72; ++t) {
                    var a = (t * 5 + root.phase * 1.7) * Math.PI / 180
                    var inner = base * (0.89 + (t % 4) * 0.012)
                    var outer = inner + (t % 9 === 0 ? 11 : 4)
                    ctx.beginPath()
                    ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner)
                    ctx.lineTo(cx + Math.cos(a) * outer, cy + Math.sin(a) * outer)
                    ctx.strokeStyle = root.rgba(t % 7 === 0 ? root.secondaryTone : root.primaryTone, 0.28)
                    ctx.lineWidth = t % 9 === 0 ? 1.2 : 0.55
                    ctx.stroke()
                }
            }
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()
        }
    }

    MouseArea {
        id: visualInteraction
        anchors.fill: parent
        hoverEnabled: true
        acceptedButtons: Qt.LeftButton
        cursorShape: Qt.CrossCursor
        onPositionChanged: function(mouse) {
            root.hoverX = root.width > 0 ? (mouse.x / root.width - 0.5) * 2.0 : 0
            root.hoverY = root.height > 0 ? (mouse.y / root.height - 0.5) * 2.0 : 0
        }
        onExited: {
            root.hoverX = 0
            root.hoverY = 0
        }
        onClicked: {
            root.interactionPulse = 1.0
            interactionPulseAnimation.restart()
        }
    }
    Behavior on hoverX { NumberAnimation { duration: 145; easing.type: Easing.OutCubic } }
    Behavior on hoverY { NumberAnimation { duration: 145; easing.type: Easing.OutCubic } }
    NumberAnimation {
        id: interactionPulseAnimation
        target: root
        property: "interactionPulse"
        from: 1.0
        to: 0.0
        duration: 680
        easing.type: Easing.OutCubic
    }
}
