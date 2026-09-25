import QtQuick
import QtQuick.Shapes

Item {
    id: starkCore
    objectName: "starkArcReactorCore"

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

    readonly property real t: telemetry ? telemetry.motionTime : 0
    readonly property real orbitTime: orbitTimeOverride >= 0 ? orbitTimeOverride : t
    readonly property real energy: telemetry ? telemetry.glow : 1.0
    readonly property real level: telemetry ? telemetry.audioLevel : 0.0
    readonly property real deployment: telemetry ? telemetry.launchProgress : 1.0
    readonly property bool lowCost: telemetry ? telemetry.qualityMode : false
    readonly property real reaction: reactionOverride >= 0
        ? Math.min(1.0, reactionOverride)
        : Math.max(0.0, Math.min(1.0, (energy - 1.0) * 1.5 + level * 0.4 + musicBeat * 0.5))

    // Interactive 3D Perspective Gimbal with Spring-Back Parallax
    readonly property real gimbalPitch: Math.max(-28.0, Math.min(28.0, viewPitch + hoverY * 2.0))
    readonly property real gimbalYaw: Math.max(-32.0, Math.min(32.0, viewYaw + hoverX * 2.4))

    // Multi-speed Counter-Rotating Kinetics
    readonly property real coreAngle: (orbitTime * 6.0) % 360
    readonly property real statorAngle: (-orbitTime * 10.0) % 360
    readonly property real shardAngle: (orbitTime * 4.0) % 360
    readonly property real sparkAngle: (-orbitTime * 14.0) % 360

    // Dynamic Energy Pulse & Audio Modulation
    readonly property real corePulse: 1.0 + Math.sin(orbitTime * 3.5) * 0.02 + reaction * 0.12 + musicBeat * 0.16
    readonly property real unibeamGlow: Math.min(1.0, 0.75 + reaction * 0.35 + musicBeat * 0.45 + Math.sin(orbitTime * 6.0) * 0.10)

    opacity: deployment
    visible: deployment > 0.05

    // -------------------------------------------------------------
    // Main Perspective 3D Transformation Rig
    // -------------------------------------------------------------
    Item {
        id: reactorRig
        anchors.centerIn: parent
        width: Math.min(parent.width, parent.height) * 0.90
        height: width

        transform: [
            Rotation {
                origin.x: reactorRig.width / 2
                origin.y: reactorRig.height / 2
                axis { x: 1; y: 0; z: 0 }
                angle: starkCore.gimbalPitch
            },
            Rotation {
                origin.x: reactorRig.width / 2
                origin.y: reactorRig.height / 2
                axis { x: 0; y: 1; z: 0 }
                angle: starkCore.gimbalYaw
            },
            Scale {
                origin.x: reactorRig.width / 2
                origin.y: reactorRig.height / 2
                xScale: starkCore.zoom * starkCore.corePulse
                yScale: starkCore.zoom * starkCore.corePulse
            }
        ]

        // -------------------------------------------------------------
        // LAYER 1: Full-Resolution Master Photorealistic Chassis
        // -------------------------------------------------------------
        Image {
            id: masterChassis
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            source: "../assets/stark_mk85/stark_master_clean.png"
            mipmap: true
            smooth: true
            opacity: 0.96
        }

        // -------------------------------------------------------------
        // LAYER 2: Kinetic Intermediate Stator Turbine (Counter-Rotating)
        // -------------------------------------------------------------
        Image {
            id: statorTurbine
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            source: "../assets/stark_mk85/stark_stator_ring.png"
            mipmap: true
            smooth: true
            rotation: starkCore.statorAngle
            opacity: 0.82 + starkCore.reaction * 0.18

            // Parallax shift relative to gimbal
            x: -starkCore.gimbalYaw * 0.18
            y: -starkCore.gimbalPitch * 0.18
        }

        // -------------------------------------------------------------
        // LAYER 3: Orbiting Nanotech Armor Shards (Foreground Parallax)
        // -------------------------------------------------------------
        Image {
            id: outerShards
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            source: "../assets/stark_mk85/stark_outer_shards.png"
            mipmap: true
            smooth: true
            rotation: starkCore.shardAngle

            // Outward beat shockwave expansion + foreground parallax
            scale: 1.0 + starkCore.musicBeat * 0.05 + starkCore.reaction * 0.02
            x: -starkCore.gimbalYaw * 0.50
            y: -starkCore.gimbalPitch * 0.50
            opacity: 0.88 + starkCore.unibeamGlow * 0.12
        }

        // -------------------------------------------------------------
        // LAYER 4: Radiant Flying Embers & Micro-Sparks into the Void
        // -------------------------------------------------------------
        Item {
            id: sparkField
            anchors.centerIn: parent
            width: parent.width
            height: parent.height
            rotation: starkCore.sparkAngle

            Repeater {
                model: 48
                Item {
                    id: sparkAnchor
                    required property int index
                    anchors.centerIn: parent
                    width: parent.width
                    height: parent.height
                    rotation: index * (360 / 48)

                    readonly property real sparkDist: parent.width * (0.45 + (index % 5) * 0.035) + (starkCore.reaction * 24.0)
                    readonly property real sparkSize: 2.0 + (index % 4) * 2.0

                    Rectangle {
                        anchors.top: parent.top
                        anchors.topMargin: -sparkAnchor.sparkDist
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: sparkAnchor.sparkSize
                        height: sparkAnchor.sparkSize
                        radius: width / 2
                        color: sparkAnchor.index % 3 === 0 ? "#ffffff" : (sparkAnchor.index % 2 === 0 ? "#fff176" : "#ff9800")
                        opacity: (0.35 + Math.sin(starkCore.orbitTime * 9.0 + sparkAnchor.index) * 0.45) * (1.0 - (sparkAnchor.index % 5) * 0.12)
                    }
                }
            }
        }

        // -------------------------------------------------------------
        // LAYER 5: Central Unibeam Tri-Core (Independent Pulse & Flare)
        // -------------------------------------------------------------
        Item {
            id: triCoreContainer
            anchors.centerIn: parent
            width: parent.width
            height: parent.height

            // Recessed background parallax
            x: starkCore.gimbalYaw * 0.12
            y: starkCore.gimbalPitch * 0.12

            Image {
                anchors.centerIn: parent
                width: parent.width
                height: parent.height
                source: "../assets/stark_mk85/stark_tri_core.png"
                mipmap: true
                smooth: true

                // Scale and pulse with speech level and music beats
                scale: 1.0 + starkCore.reaction * 0.10 + starkCore.musicBeat * 0.15
                opacity: 0.90 + starkCore.unibeamGlow * 0.10
            }

            // White-Hot Singularity Point (Incandescent Core)
            Rectangle {
                anchors.centerIn: parent
                width: 22 + starkCore.reaction * 12.0 + starkCore.musicBeat * 16.0
                height: width
                radius: width / 2
                color: "#ffffff"
                border.color: "#fff9c4"
                border.width: 2.5

                // Center incandescent burst
                scale: 1.0 + Math.sin(starkCore.orbitTime * 8.0) * 0.12 + starkCore.reaction * 0.20
                opacity: starkCore.unibeamGlow * 0.90
            }
        }

        // -------------------------------------------------------------
        // LAYER 6: Blazing Anamorphic Laser Flare Beams
        // -------------------------------------------------------------
        Item {
            id: flareAssembly
            anchors.centerIn: parent
            width: parent.width * 1.55
            height: parent.height * 1.55

            // Horizontal Optical Anamorphic Streak (Soft Outer Bloom)
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 16 + starkCore.reaction * 14.0 + starkCore.musicBeat * 18.0
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.00; color: "transparent" }
                    GradientStop { position: 0.22; color: Qt.rgba(1.0, 0.45, 0.05, 0.12 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.42; color: Qt.rgba(1.0, 0.70, 0.15, 0.35 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.50; color: Qt.rgba(1.0, 0.90, 0.40, 0.60 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.58; color: Qt.rgba(1.0, 0.70, 0.15, 0.35 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.78; color: Qt.rgba(1.0, 0.45, 0.05, 0.12 * starkCore.unibeamGlow) }
                    GradientStop { position: 1.00; color: "transparent" }
                }
            }

            // Piercing Intense Horizontal Anamorphic Core Beam
            Rectangle {
                anchors.centerIn: parent
                width: parent.width
                height: 4.5 + starkCore.reaction * 5.0 + starkCore.musicBeat * 7.0
                radius: height / 2
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0.00; color: "transparent" }
                    GradientStop { position: 0.25; color: Qt.rgba(1.0, 0.55, 0.05, 0.35 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.46; color: Qt.rgba(1.0, 0.94, 0.50, 0.90 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.50; color: Qt.rgba(1.0, 1.00, 0.95, 1.00 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.54; color: Qt.rgba(1.0, 0.94, 0.50, 0.90 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.75; color: Qt.rgba(1.0, 0.55, 0.05, 0.35 * starkCore.unibeamGlow) }
                    GradientStop { position: 1.00; color: "transparent" }
                }
            }

            // Vertical Cross Ray
            Rectangle {
                anchors.centerIn: parent
                height: parent.height * 0.90
                width: 3.5 + starkCore.reaction * 3.5 + starkCore.musicBeat * 5.0
                radius: width / 2
                gradient: Gradient {
                    orientation: Gradient.Vertical
                    GradientStop { position: 0.00; color: "transparent" }
                    GradientStop { position: 0.30; color: Qt.rgba(1.0, 0.50, 0.05, 0.25 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.47; color: Qt.rgba(1.0, 0.90, 0.40, 0.85 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.50; color: Qt.rgba(1.0, 1.00, 0.95, 0.95 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.53; color: Qt.rgba(1.0, 0.90, 0.40, 0.85 * starkCore.unibeamGlow) }
                    GradientStop { position: 0.70; color: Qt.rgba(1.0, 0.50, 0.05, 0.25 * starkCore.unibeamGlow) }
                    GradientStop { position: 1.00; color: "transparent" }
                }
            }
        }

        // -------------------------------------------------------------
        // LAYER 7: J.A.R.V.I.S. / Mark 85 Futuristic HUD Telemetry
        // -------------------------------------------------------------
        Item {
            anchors.fill: parent

            // Top-Left Tech Bracket
            Item {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.leftMargin: 8
                anchors.topMargin: 8
                width: 170
                height: 50

                Rectangle { width: 18; height: 1.5; color: "#ffca28" }
                Rectangle { width: 1.5; height: 18; color: "#ffca28" }

                Column {
                    anchors.left: parent.left
                    anchors.leftMargin: 6
                    anchors.top: parent.top
                    anchors.topMargin: 4
                    spacing: 2
                    Text {
                        text: "SYS.CORE // MARK_85_TRI_CORE"
                        font.family: "Consolas"
                        font.pixelSize: 8
                        font.bold: true
                        color: "#ffca28"
                    }
                    Text {
                        text: "CONTAINMENT FLUX: 99.99%"
                        font.family: "Consolas"
                        font.pixelSize: 7
                        color: Qt.rgba(1.0, 0.75, 0.25, 0.75)
                    }
                    Text {
                        text: "OUTPUT: " + (12.4 + starkCore.reaction * 6.2).toFixed(1) + " GW [OPTIMAL]"
                        font.family: "Consolas"
                        font.pixelSize: 7
                        color: Qt.rgba(1.0, 0.75, 0.25, 0.75)
                    }
                }
            }

            // Bottom-Right Tech Readout
            Item {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 8
                anchors.bottomMargin: 8
                width: 170
                height: 50

                Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 18; height: 1.5; color: "#ff9100" }
                Rectangle { anchors.right: parent.right; anchors.bottom: parent.bottom; width: 1.5; height: 18; color: "#ff9100" }

                Column {
                    anchors.right: parent.right
                    anchors.rightMargin: 6
                    anchors.bottom: parent.bottom
                    anchors.bottomMargin: 4
                    spacing: 2
                    Text {
                        anchors.right: parent.right
                        text: "NANOTECH ARMOR: ENGAGED"
                        font.family: "Consolas"
                        font.pixelSize: 8
                        font.bold: true
                        color: "#ff9100"
                    }
                    Text {
                        anchors.right: parent.right
                        text: "HARMONIC FREQ: " + Math.round(432 + starkCore.level * 96) + " HZ"
                        font.family: "Consolas"
                        font.pixelSize: 7
                        color: Qt.rgba(1.0, 0.75, 0.25, 0.75)
                    }
                    Text {
                        anchors.right: parent.right
                        text: "GIMBAL VECTORS: " + Math.round(starkCore.gimbalYaw) + "° / " + Math.round(starkCore.gimbalPitch) + "°"
                        font.family: "Consolas"
                        font.pixelSize: 7
                        color: Qt.rgba(1.0, 0.75, 0.25, 0.65)
                    }
                }
            }
        }
    }

    // Pass-through pick function for core click detection
    function pick(x, y) {
        let cx = width / 2
        let cy = height / 2
        let dist = Math.hypot(x - cx, y - cy)
        let coreR = Math.min(width, height) * 0.28
        if (dist <= coreR) {
            return { objectHit: { objectName: "coreHit" } }
        }
        return { objectHit: null }
    }
}
