import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVResultSurface.qml
//
// Borderless HUD result presentation with lifecycle visualization (Phase 018-E).
// Displays canonical execution lifecycle HUD together with task results
// with smooth typewriter animation directly in the HUD space, with no card,
// border, or opaque background.
//
// Presentation-only component:
// - Zero execution capability
// - Zero mutation authority
// - Dismiss only clears local presentation state
Item {
    id: root
    objectName: "resultSurface"

    readonly property string resultText:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResult
        : ""

    readonly property string resultStatus:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultStatus
        : "IDLE"

    readonly property bool resultSuccess:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultSuccess
        : false

    readonly property bool resultAvailable:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? guiBridge.taskResultAvailable
        : false

    readonly property bool isRunning: resultStatus === "RUNNING"
    readonly property bool isLifecycleActive:
        (typeof guiBridge !== "undefined" && guiBridge !== null)
        ? (guiBridge.lifecycleActive || (guiBridge.lifecycleStage !== "IDLE" && guiBridge.lifecycleStage !== ""))
        : false
    readonly property bool isVisible: resultAvailable || isRunning || isLifecycleActive

    // --- Typewriter animation state ---
    property string _fullText: ""
    property string _displayedText: ""
    property int _charIndex: 0
    property bool _animating: false

    // Characters revealed per timer tick for smooth, fast typing
    readonly property int _charsPerTick: 2
    // Timer interval in ms — 12ms ≈ 83 ticks/sec for smooth feel
    readonly property int _tickInterval: 12

    // Responsive presentation properties
    readonly property bool isCompactHeight: (parent && parent.height < Theme.stageCompactHeight)
                                            || (typeof windowRoot !== "undefined" && windowRoot && windowRoot.isCompactHeight)
    readonly property bool isCompactWidth: (parent && parent.width < Theme.stageCompactWidth)
                                           || (typeof windowRoot !== "undefined" && windowRoot && windowRoot.isCompactWidth)

    // Maximum height allocation for the entire result surface:
    // Standard: at most 35% of parent height up to 240px
    // Compact: at most 25% of parent height up to 140px
    readonly property real maxTotalHeight: isCompactHeight
        ? Math.min(parent ? parent.height * 0.25 : 140, 140)
        : Math.min(parent ? parent.height * 0.35 : 240, 240)

    visible: opacity > 0.001
    opacity: isVisible ? 1.0 : 0.0

    implicitWidth: parent ? parent.width : 400
    implicitHeight: isVisible ? Math.min(maxTotalHeight,
                                          contentColumn.implicitHeight + (isCompactHeight ? Theme.spacingXXS * 2 : Theme.spacingXS * 2)) : 0
    height: implicitHeight

    clip: true

    Behavior on implicitHeight {
        NumberAnimation {
            duration: Theme.motionStandard
            easing.type: Easing.InOutCubic
        }
    }

    Behavior on opacity {
        NumberAnimation {
            duration: Theme.motionStandard
        }
    }

    // --- Typewriter Timer ---
    Timer {
        id: typingTimer
        interval: root._tickInterval
        repeat: true
        running: root._animating

        onTriggered: {
            if (root._charIndex >= root._fullText.length) {
                root._animating = false
                root._displayedText = root._fullText
                return
            }
            var nextIndex = Math.min(root._charIndex + root._charsPerTick,
                                      root._fullText.length)
            root._displayedText = root._fullText.substring(0, nextIndex)
            root._charIndex = nextIndex
        }
    }

    // --- React to new result text ---
    onResultTextChanged: {
        if (resultText.length > 0 && resultAvailable) {
            _startTyping(resultText)
        }
    }

    onResultAvailableChanged: {
        if (resultAvailable && resultText.length > 0) {
            _startTyping(resultText)
        } else if (!resultAvailable && !isRunning) {
            _stopTyping()
        }
    }

    onIsRunningChanged: {
        if (isRunning) {
            _stopTyping()
        }
    }

    function _startTyping(text) {
        _fullText = text
        _displayedText = ""
        _charIndex = 0
        _animating = true
    }

    function _stopTyping() {
        _animating = false
        _fullText = ""
        _displayedText = ""
        _charIndex = 0
    }

    // --- Semantic text color ---
    readonly property color _resultColor: {
        if (isRunning) return Theme.textSecondary
        if (!resultAvailable) return Theme.textSecondary
        if (resultSuccess) return Qt.rgba(Theme.luminousPrimary.r,
                                           Theme.luminousPrimary.g,
                                           Theme.luminousPrimary.b,
                                           0.90)
        if (resultStatus === "ROLLED_BACK") return Qt.rgba(Theme.luminousWarning.r,
                                                            Theme.luminousWarning.g,
                                                            Theme.luminousWarning.b,
                                                            0.90)
        if (resultStatus === "CANCELLED") return Qt.rgba(Theme.luminousWarning.r,
                                                          Theme.luminousWarning.g,
                                                          Theme.luminousWarning.b,
                                                          0.85)
        return Qt.rgba(Theme.luminousCritical.r,
                       Theme.luminousCritical.g,
                       Theme.luminousCritical.b,
                       0.90)
    }

    // --- Content ---
    Column {
        id: contentColumn
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: root.isCompactHeight ? Theme.spacingXXS : Theme.spacingXS
        spacing: root.isCompactHeight ? Theme.spacingXXS : Theme.spacingXS

        // Header: Lifecycle HUD on left, subtle dismiss control on right
        Item {
            id: hudHeader
            width: parent.width
            height: Math.max(lifecycleHUD.implicitHeight, dismissText.implicitHeight)
            visible: root.isVisible

            EVLifecycleHUD {
                id: lifecycleHUD
                anchors.left: parent.left
                anchors.right: dismissArea.left
                anchors.rightMargin: root.isCompactWidth ? Theme.spacingXXS : Theme.spacingXS
                anchors.verticalCenter: parent.verticalCenter
            }

            Item {
                id: dismissArea
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                width: dismissText.implicitWidth + 8
                height: parent.height
                visible: root.resultAvailable

                Text {
                    id: dismissText
                    anchors.centerIn: parent
                    text: "✕"
                    color: dismissMouseArea.containsMouse
                           ? Theme.textSecondary
                           : Theme.textTertiary
                    font.family: Theme.fontFamily
                    font.pointSize: Theme.fontSizeLabelSmall
                    opacity: dismissMouseArea.containsMouse ? 1.0 : 0.4
                    visible: root.resultAvailable

                    Behavior on opacity {
                        NumberAnimation { duration: Theme.motionFast }
                    }
                }

                MouseArea {
                    id: dismissMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        root._stopTyping()
                        if (typeof guiBridge !== "undefined" && guiBridge !== null) {
                            guiBridge.clearTaskResult()
                        }
                    }
                }
            }
        }

        // Result text — borderless, direct HUD presentation
        Flickable {
            id: flickableArea
            width: parent.width
            visible: resultMessageText.text.length > 0
            readonly property real maxTextHeight: root.isCompactHeight
                ? Math.min(parent.parent ? parent.parent.height * 0.16 : 80, 80)
                : Math.min(parent.parent ? parent.parent.height * 0.30 : 160, 160)
            implicitHeight: visible
                ? Math.min(maxTextHeight, resultMessageText.implicitHeight)
                : 0
            contentWidth: width
            contentHeight: resultMessageText.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Text {
                id: resultMessageText
                width: parent.width
                text: root.isRunning
                      ? ((typeof guiBridge !== "undefined" && guiBridge && guiBridge.currentTask) ? guiBridge.currentTask : "")
                      : root._displayedText
                color: root._resultColor
                font.family: root.isRunning ? Theme.fontFamilyMono : Theme.fontFamily
                font.pointSize: (root.isCompactHeight || root.width < 850)
                                ? Theme.fontSizeLabelSmall
                                : (root.isRunning ? Theme.fontSizeLabelSmall : Theme.fontSizeBodySmall)
                font.weight: Theme.fontWeightRegular
                wrapMode: Text.Wrap
                lineHeight: 1.3
                textFormat: Text.PlainText

                Behavior on color {
                    ColorAnimation { duration: Theme.motionStandard }
                }
            }
        }
    }
}
