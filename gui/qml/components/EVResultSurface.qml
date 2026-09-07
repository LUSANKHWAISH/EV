import QtQuick 2.15
import QtQuick.Controls 2.15
import "../theme"

// EVResultSurface.qml
//
// Borderless HUD result presentation — 018-D.2.
// Displays task results with smooth typewriter animation directly
// in the HUD space, with no card, border, or opaque background.
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
    readonly property bool isVisible: resultAvailable || isRunning

    // --- Typewriter animation state ---
    property string _fullText: ""
    property string _displayedText: ""
    property int _charIndex: 0
    property bool _animating: false

    // Characters revealed per timer tick for smooth, fast typing
    readonly property int _charsPerTick: 2
    // Timer interval in ms — 12ms ≈ 83 ticks/sec for smooth feel
    readonly property int _tickInterval: 12

    visible: opacity > 0.001
    opacity: isVisible ? 1.0 : 0.0

    implicitWidth: parent ? parent.width : 400
    implicitHeight: isVisible ? Math.min(parent ? parent.height * 0.45 : 240,
                                          contentColumn.implicitHeight + Theme.spacingXS * 2) : 0
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
            _fullText = "Executing through canonical pipeline..."
            _displayedText = _fullText
            _charIndex = _fullText.length
            _animating = false
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
        anchors.margins: Theme.spacingXS
        spacing: 0

        // Subtle dismiss control — top-right aligned
        Item {
            width: parent.width
            height: dismissText.visible ? Theme.spacingXS : 0
            visible: root.resultAvailable

            Text {
                id: dismissText
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
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

                MouseArea {
                    id: dismissMouseArea
                    anchors.fill: parent
                    anchors.margins: -4
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
            implicitHeight: Math.min(parent.parent ? parent.parent.height * 0.4 : 160,
                                      resultMessageText.implicitHeight)
            contentWidth: width
            contentHeight: resultMessageText.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Text {
                id: resultMessageText
                width: parent.width
                text: root.isRunning
                      ? "Executing through canonical pipeline..."
                      : root._displayedText
                color: root._resultColor
                font.family: Theme.fontFamily
                font.pointSize: Theme.fontSizeBodySmall
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
