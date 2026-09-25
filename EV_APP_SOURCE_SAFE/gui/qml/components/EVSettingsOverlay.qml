import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15

Item {
    id: root
    objectName: "settingsOverlay"

    // Local presentation tokens: the classic app and approval surfaces keep
    // their own theme; provider storage and routing still belong to GuiBridge.
    property bool cinematic: false
    QtObject {
        id: skin
        readonly property color backgroundDeep: "#0b151d"
        readonly property color surfaceLowest: "#0e1d26"
        readonly property color surfaceBase: "#14252e"
        readonly property color surfaceRaised: "#29291f"
        readonly property color surfaceElevated: "#263832"
        readonly property color edgeSubtle: "#2b404a"
        readonly property color edgeStandard: "#354b55"
        readonly property color brandPrimary: "#d9ae67"
        readonly property color luminousWarning: "#efbd73"
        readonly property color luminousCritical: "#ef9b82"
        readonly property color textPrimary: "#e0e5df"
        readonly property color textSecondary: "#a7bac1"
        readonly property color textTertiary: "#829ca9"
        readonly property string fontFamily: "Segoe UI"
        readonly property string fontFamilyMono: "Consolas"
        readonly property int fontSizeSection: 30
        readonly property int fontSizeBody: 16
        readonly property int fontSizeBodySmall: 13
        readonly property int fontSizeLabel: 13
        readonly property int fontSizeLabelSmall: 11
        readonly property int fontWeightRegular: Font.Normal
        readonly property int fontWeightMedium: Font.Medium
        readonly property int fontWeightSemibold: Font.Medium
        readonly property int fontWeightBold: Font.DemiBold
        readonly property real letterSpacingWide: 1
        readonly property real letterSpacingEmphasis: 1.2
        readonly property int spacingXXXS: 6
        readonly property int spacingXXS: 8
        readonly property int spacingXS: 16
        readonly property int spacingS: 28
        readonly property int spacingM: 28
        readonly property int radiusXS: 3
        readonly property int radiusS: 4
        readonly property int radiusM: 6
        readonly property int borderThin: 1
        readonly property int hairline: 1
        readonly property int motionStandard: 180
    }

    component ProviderPicker: ComboBox {
        id: picker
        implicitHeight: 42
        font.family: "Segoe UI"
        font.pixelSize: 13
        leftPadding: 12; rightPadding: 34
        contentItem: Text {
            text: picker.displayText; font: picker.font; color: "#d9e1de"
            verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        background: Rectangle {
            color: picker.hovered ? "#142630" : "#0e1d26"; radius: 4
            border.color: picker.activeFocus || picker.popup.visible ? "#d9ae67" : "#2b404a"
        }
        indicator: Text {
            text: "⌄"; color: "#d9ae67"; font.pixelSize: 18
            x: picker.width - 27; y: (picker.height-height)/2-3
        }
        delegate: ItemDelegate {
            width: picker.width; height: 38
            contentItem: Text {
                text: modelData; color: highlighted ? "#efcc8f" : "#c5d4d7"
                font: picker.font; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
            }
            highlighted: picker.highlightedIndex === index
            background: Rectangle { color: parent.highlighted ? "#29291f" : "#101e27" }
        }
        popup: Popup {
            y: picker.height+5; width: picker.width; padding: 5
            implicitHeight: Math.min(contentItem.implicitHeight+10,300)
            contentItem: ListView {
                clip: true; implicitHeight: contentHeight
                model: picker.popup.visible ? picker.delegateModel : null
                currentIndex: picker.highlightedIndex; ScrollIndicator.vertical: ScrollIndicator {}
            }
            background: Rectangle { color: "#101e27"; border.color: "#6a593e"; radius: 4 }
        }
    }

    anchors.fill: parent
    visible: opacity > 0.001
    opacity: (typeof guiBridge !== "undefined" && guiBridge && guiBridge.settingsVisible) ? 1.0 : 0.0

    Behavior on opacity {
        NumberAnimation { duration: skin.motionStandard; easing.type: Easing.OutCubic }
    }

    // State properties
    property string activeCategory: "AI PROVIDERS"
    property var providerList: []
    property var currentProvider: null
    property string testStatusText: ""
    property color testStatusColor: skin.textSecondary
    property bool isTesting: false

    // Sync provider list from bridge whenever overlay becomes visible or list changes
    function refreshProviders() {
        if (typeof guiBridge === "undefined" || !guiBridge) return;
        try {
            var raw = guiBridge.getProvidersJson();
            var list = JSON.parse(raw);
            providerList = list;

            // Maintain current selection or select active provider
            var found = false;
            if (currentProvider && currentProvider.id) {
                for (var i = 0; i < list.length; i++) {
                    if (list[i].id === currentProvider.id) {
                        selectProvider(list[i]);
                        found = true;
                        break;
                    }
                }
            }
            if (!found && list.length > 0) {
                // Find active provider
                var activeIdx = 0;
                for (var j = 0; j < list.length; j++) {
                    if (list[j].is_active) {
                        activeIdx = j;
                        break;
                    }
                }
                selectProvider(list[activeIdx]);
            }
        } catch (e) {
            console.log("Error refreshing providers:", e);
        }
    }

    function selectProvider(p) {
        currentProvider = p;
        if (!p) return;

        nameInput.text = p.name || "";
        typeCombo.currentIndex = Math.max(0, typeCombo.model.indexOf(p.provider_type));
        protocolCombo.currentIndex = Math.max(0, protocolCombo.model.indexOf(p.protocol));
        modelInput.text = p.model || "";
        baseUrlInput.text = p.base_url || "";
        endpointInput.text = p.endpoint || "";
        apiVersionInput.text = p.api_version || "";
        keyInput.text = p.has_credential ? "••••••••••••" : "";
        testStatusText = "";
    }

    function createNewProvider() {
        var newP = {
            "id": "custom-" + Date.now(),
            "name": "Custom AI",
            "provider_type": "Custom / OpenAI Compatible",
            "protocol": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": true,
            "is_active": false,
            "has_credential": false
        };
        selectProvider(newP);
    }

    onVisibleChanged: {
        if (visible) {
            refreshProviders();
        }
    }

    Connections {
        target: typeof guiBridge !== "undefined" && guiBridge ? guiBridge : null
        function onProviderListChanged() {
            root.refreshProviders();
        }
        function onActiveProviderChanged() {
            root.refreshProviders();
        }
    }

    // Modal dark backdrop
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0.015, 0.03, 0.045, 0.82)

        MouseArea {
            anchors.fill: parent
            onClicked: {
                if (typeof guiBridge !== "undefined" && guiBridge) {
                    guiBridge.closeSettings();
                }
            }
        }
    }

    // Main Settings Panel
    Rectangle {
        id: panel
        objectName: "settingsPanel"
        anchors.centerIn: parent
        width: Math.min(parent.width - 64, 1080)
        height: Math.min(parent.height - 64, 800)
        radius: skin.radiusM
        color: skin.backgroundDeep
        border.width: skin.borderThin
        border.color: skin.edgeStandard
        Rectangle { width: 74; height: 2; color: skin.brandPrimary; anchors.top: parent.top; x: 28 }

        // Consume clicks so backdrop doesn't close on inner click
        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: skin.spacingS
            spacing: skin.spacingS

            // -------------------------------------------------------------
            // Header: Subsystem Title + Close Button
            // -------------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter

                ColumnLayout {
                    spacing: 6
                    Text { text: "E.V.  /  PERSONAL PREFERENCES";color: skin.brandPrimary;font.family: skin.fontFamily;font.pixelSize: 10;font.letterSpacing: 2 }
                    Text { text: "Settings";color: skin.textPrimary;font.family: skin.fontFamily;font.pixelSize: 32;font.weight: Font.Light }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 28; height: 28
                    radius: skin.radiusS
                    color: closeArea.pressed
                           ? skin.surfaceElevated
                           : closeArea.containsMouse
                               ? skin.surfaceBase
                               : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        color: closeArea.containsMouse ? skin.textPrimary : skin.textSecondary
                        font.family: skin.fontFamily
                        font.pixelSize: skin.fontSizeLabel
                    }

                    MouseArea {
                        id: closeArea
                        objectName: "settingsClose"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (typeof guiBridge !== "undefined" && guiBridge) {
                                guiBridge.closeSettings();
                            }
                        }
                    }
                }
            }

            // Hairline separator
            Rectangle {
                Layout.fillWidth: true
                height: skin.hairline
                color: skin.edgeStandard
            }

            // -------------------------------------------------------------
            // Body Layout: Sidebar Tabs (left) + Category View (right)
            // -------------------------------------------------------------
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: skin.spacingS

                // Category Sidebar
                ColumnLayout {
                    Layout.fillWidth: false
                    Layout.preferredWidth: panel.width < 900 ? 152 : 196
                    Layout.minimumWidth: panel.width < 900 ? 152 : 196
                    Layout.maximumWidth: panel.width < 900 ? 152 : 196
                    Layout.fillHeight: true
                    spacing: skin.spacingXXXS
                    Text { text: "CONFIGURATION";color: skin.textTertiary;font.family: skin.fontFamily;font.pixelSize: 9;font.letterSpacing: 2;Layout.bottomMargin: 12 }

                    Repeater {
                        model: [
                            "AI PROVIDERS",
                            "VOICE",
                            "APPEARANCE",
                            "CORE STYLE",
                            "AUDIO",
                            "GENERAL"
                        ]

                        delegate: Rectangle {
                            Layout.fillWidth: true
                            height: 46
                            radius: skin.radiusS
                            color: root.activeCategory === modelData
                                   ? skin.surfaceRaised
                                   : tabArea.containsMouse
                                       ? skin.surfaceBase
                                       : "transparent"

                            Rectangle {
                                width: 3
                                height: parent.height - 8
                                anchors.left: parent.left
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.leftMargin: 4
                                radius: 1.5
                                color: skin.brandPrimary
                                visible: root.activeCategory === modelData
                            }

                            Text {
                                anchors.left: parent.left
                                anchors.leftMargin: 16
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData
                                color: root.activeCategory === modelData
                                       ? skin.textPrimary
                                       : tabArea.containsMouse
                                           ? skin.textSecondary
                                           : skin.textTertiary
                                font.family: skin.fontFamily
                                font.pixelSize: skin.fontSizeLabel
                                font.weight: root.activeCategory === modelData
                                             ? skin.fontWeightSemibold
                                             : skin.fontWeightRegular
                                font.letterSpacing: skin.letterSpacingWide
                            }

                            MouseArea {
                                id: tabArea
                                objectName: "settingsTab_" + modelData
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    root.activeCategory = modelData;
                                }
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }
                }

                // Vertical Divider
                Rectangle {
                    Layout.fillWidth: false
                    Layout.preferredWidth: skin.hairline
                    Layout.minimumWidth: skin.hairline
                    Layout.maximumWidth: skin.hairline
                    Layout.fillHeight: true
                    width: skin.hairline
                    color: skin.edgeStandard
                }

                // ---------------------------------------------------------
                // Right Content Area
                // ---------------------------------------------------------
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumWidth: 300
                    Layout.preferredWidth: 640

                    // === AI PROVIDERS VIEW ===
                    ColumnLayout {
                        anchors.fill: parent
                        visible: root.activeCategory === "AI PROVIDERS"
                        spacing: skin.spacingXS

                        // Active Provider Callout Card
                        Rectangle {
                            Layout.fillWidth: true
                            height: 48
                            radius: skin.radiusS
                            color: skin.surfaceLowest
                            border.width: skin.borderThin
                            border.color: skin.edgeSubtle

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: skin.spacingS
                                anchors.rightMargin: skin.spacingS
                                spacing: skin.spacingS

                                Text {
                                    text: "PRIMARY PROVIDER"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightMedium
                                    font.letterSpacing: skin.letterSpacingWide
                                }

                                Text {
                                    text: typeof guiBridge !== "undefined" && guiBridge ? guiBridge.activeProviderName : "Gemini"
                                    color: skin.textPrimary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabel
                                    font.weight: skin.fontWeightSemibold
                                }

                                Row {
                                    spacing: 4
                                    Layout.alignment: Qt.AlignVCenter

                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 6; height: 6; radius: 3
                                        color: (typeof guiBridge !== "undefined" && guiBridge && guiBridge.activeProviderStatus === "Connected")
                                               ? skin.brandPrimary
                                               : skin.luminousWarning
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: typeof guiBridge !== "undefined" && guiBridge ? guiBridge.activeProviderStatus : "Connected"
                                        color: (typeof guiBridge !== "undefined" && guiBridge && guiBridge.activeProviderStatus === "Connected")
                                               ? skin.brandPrimary
                                               : skin.luminousWarning
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabelSmall
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }
                        }

                        // Provider Selector & Add Button
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: skin.spacingXS

                            Text {
                                text: "PROFILE"
                                color: skin.textSecondary
                                font.family: skin.fontFamily
                                font.pixelSize: skin.fontSizeLabel
                            }

                            ProviderPicker {
                                id: providerSelectCombo
                                objectName: "providerSelector"
                                Layout.fillWidth: true
                                model: {
                                    var names = [];
                                    for (var i = 0; i < root.providerList.length; i++) {
                                        var p = root.providerList[i];
                                        names.push(p.name + (p.is_active ? " (Active)" : ""));
                                    }
                                    return names;
                                }
                                currentIndex: {
                                    if (!root.currentProvider) return 0;
                                    for (var i = 0; i < root.providerList.length; i++) {
                                        if (root.providerList[i].id === root.currentProvider.id) return i;
                                    }
                                    return 0;
                                }
                                onActivated: function(index) {
                                    if (index >= 0 && index < root.providerList.length) {
                                        root.selectProvider(root.providerList[index]);
                                    }
                                }
                            }

                            Rectangle {
                                Layout.preferredWidth: panel.width < 900 ? 96 : 110
                                Layout.preferredHeight: 40
                                width: 110; height: 40
                                radius: skin.radiusS
                                color: addArea.pressed ? skin.surfaceElevated : (addArea.containsMouse ? skin.surfaceRaised : skin.surfaceBase)
                                border.width: skin.borderThin
                                border.color: skin.edgeStandard

                                Text {
                                    anchors.centerIn: parent
                                    text: "+ Add Provider"
                                    color: skin.textPrimary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightMedium
                                }

                                MouseArea {
                                    id: addArea
                                    objectName: "providerAdd"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.createNewProvider()
                                }
                            }
                        }

                        // Configuration Form (ScrollView)
                        ScrollView {
                            id: formScroll
                            objectName: "providerForm"
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            implicitWidth: 0
                            clip: true
                            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                            ScrollBar.vertical.policy: ScrollBar.AsNeeded

                            ColumnLayout {
                                width: formScroll.availableWidth > 0 ? formScroll.availableWidth - 8 : parent.width - 8
                                spacing: skin.spacingXXS

                                // Field: Provider Name
                                Text {
                                    text: "Provider Name"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 42
                                    radius: skin.radiusS
                                    color: skin.surfaceLowest
                                    border.width: skin.borderThin
                                    border.color: nameInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                    TextInput {
                                        id: nameInput
                                        objectName: "nameInput"
                                        clip: true
                                        anchors.fill: parent
                                        anchors.leftMargin: 12; anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: skin.textPrimary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabel
                                        selectByMouse: true
                                    }
                                }

                                // Field: Provider Type
                                Text {
                                    text: "Provider Type"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }
                                ProviderPicker {
                                    id: typeCombo
                                    objectName: "providerType"
                                    Layout.fillWidth: true
                                    model: [
                                        "Gemini",
                                        "OpenAI",
                                        "Azure OpenAI",
                                        "Anthropic",
                                        "OpenRouter",
                                        "Groq",
                                        "Ollama",
                                        "Custom / OpenAI Compatible"
                                    ]
                                    onActivated: function(index) {
                                        var val = model[index];
                                        if (val === "Gemini") {
                                            protocolCombo.currentIndex = protocolCombo.model.indexOf("gemini");
                                            if (!modelInput.text || modelInput.text.indexOf("gpt") !== -1) modelInput.text = "gemini-2.5-flash";
                                        } else if (val === "Anthropic") {
                                            protocolCombo.currentIndex = protocolCombo.model.indexOf("anthropic");
                                            if (!modelInput.text || modelInput.text.indexOf("gemini") !== -1) modelInput.text = "claude-3-5-sonnet-20241022";
                                            if (!baseUrlInput.text) baseUrlInput.text = "https://api.anthropic.com/v1";
                                        } else if (val === "Azure OpenAI") {
                                            protocolCombo.currentIndex = protocolCombo.model.indexOf("azure_openai");
                                            if (!apiVersionInput.text) apiVersionInput.text = "2024-06-01";
                                        } else {
                                            protocolCombo.currentIndex = protocolCombo.model.indexOf("openai_compatible");
                                            if (val === "OpenAI" && !baseUrlInput.text) baseUrlInput.text = "https://api.openai.com/v1";
                                            if (val === "OpenRouter" && !baseUrlInput.text) baseUrlInput.text = "https://openrouter.ai/api/v1";
                                            if (val === "Groq" && !baseUrlInput.text) baseUrlInput.text = "https://api.groq.com/openai/v1";
                                            if (val === "Ollama" && !baseUrlInput.text) baseUrlInput.text = "http://localhost:11434/v1";
                                        }
                                    }
                                }

                                // Field: Model
                                Text {
                                    text: "Model Identifier"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 42
                                    radius: skin.radiusS
                                    color: skin.surfaceLowest
                                    border.width: skin.borderThin
                                    border.color: modelInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                    TextInput {
                                        id: modelInput
                                        objectName: "modelInput"
                                        clip: true
                                        anchors.fill: parent
                                        anchors.leftMargin: 12; anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: skin.textPrimary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabel
                                        selectByMouse: true
                                    }
                                }

                                // Field: API Key (Masked)
                                Text {
                                    text: "API key · Encrypted on this device"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }
                                Rectangle {
                                    Layout.fillWidth: true
                                    height: 42
                                    radius: skin.radiusS
                                    color: skin.surfaceLowest
                                    border.width: skin.borderThin
                                    border.color: keyInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                    TextInput {
                                        id: keyInput
                                        objectName: "keyInput"
                                        clip: true
                                        anchors.fill: parent
                                        anchors.leftMargin: 12; anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        color: skin.textPrimary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabel
                                        echoMode: TextInput.Password
                                        selectByMouse: true
                                    }
                                }

                                // Field: Base URL (Visible for OpenAI-compatible and Anthropic)
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    width: parent.width
                                    visible: typeCombo.currentText !== "Gemini" && typeCombo.currentText !== "Azure OpenAI"
                                    spacing: 2

                                    Text {
                                        text: "Base URL"
                                        color: skin.textTertiary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabelSmall
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 42
                                        radius: skin.radiusS
                                        color: skin.surfaceLowest
                                        border.width: skin.borderThin
                                        border.color: baseUrlInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                        TextInput {
                                            id: baseUrlInput
                                        objectName: "baseUrlInput"
                                        clip: true
                                            anchors.fill: parent
                                            anchors.leftMargin: 12; anchors.rightMargin: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            color: skin.textPrimary
                                            font.family: skin.fontFamily
                                            font.pixelSize: skin.fontSizeLabel
                                            selectByMouse: true
                                        }
                                    }
                                }

                                // Fields: Azure Specific
                                ColumnLayout {
                                    Layout.fillWidth: true
                                    width: parent.width
                                    visible: typeCombo.currentText === "Azure OpenAI"
                                    spacing: 2

                                    Text {
                                        text: "Azure Endpoint (e.g. https://my-resource.openai.azure.com)"
                                        color: skin.textTertiary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabelSmall
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 42
                                        radius: skin.radiusS
                                        color: skin.surfaceLowest
                                        border.width: skin.borderThin
                                        border.color: endpointInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                        TextInput {
                                            id: endpointInput
                                        objectName: "endpointInput"
                                        clip: true
                                            anchors.fill: parent
                                            anchors.leftMargin: 12; anchors.rightMargin: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            color: skin.textPrimary
                                            font.family: skin.fontFamily
                                            font.pixelSize: skin.fontSizeLabel
                                            selectByMouse: true
                                        }
                                    }

                                    Text {
                                        text: "API Version"
                                        color: skin.textTertiary
                                        font.family: skin.fontFamily
                                        font.pixelSize: skin.fontSizeLabelSmall
                                    }
                                    Rectangle {
                                        Layout.fillWidth: true
                                        height: 42
                                        radius: skin.radiusS
                                        color: skin.surfaceLowest
                                        border.width: skin.borderThin
                                        border.color: apiVersionInput.activeFocus ? skin.brandPrimary : skin.edgeSubtle

                                        TextInput {
                                            id: apiVersionInput
                                        objectName: "apiVersionInput"
                                        clip: true
                                            anchors.fill: parent
                                            anchors.leftMargin: 12; anchors.rightMargin: 12
                                            verticalAlignment: TextInput.AlignVCenter
                                            color: skin.textPrimary
                                            font.family: skin.fontFamily
                                            font.pixelSize: skin.fontSizeLabel
                                            selectByMouse: true
                                        }
                                    }
                                }

                                // Field: Protocol Selector
                                Text {
                                    text: "Protocol"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }
                                ProviderPicker {
                                    id: protocolCombo
                                    objectName: "providerProtocol"
                                    Layout.fillWidth: true
                                    model: [
                                        "auto_detect",
                                        "openai_compatible",
                                        "anthropic",
                                        "gemini",
                                        "azure_openai",
                                        "custom"
                                    ]
                                }
                            }
                        }

                        // Real-time Test Connection feedback label
                        Text {
                            id: statusLabel
                            objectName: "providerStatus"
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                            text: root.testStatusText
                            color: root.testStatusColor
                            font.family: skin.fontFamily
                            font.pixelSize: skin.fontSizeLabel
                            font.weight: skin.fontWeightMedium
                            visible: root.testStatusText !== ""
                        }

                        // Action Buttons Bar
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10

                            // Test Connection Button
                            Rectangle {
                                Layout.preferredWidth: panel.width < 900 ? 120 : 140
                                Layout.preferredHeight: 40
                                height: 40
                                radius: skin.radiusS
                                color: testArea.pressed ? skin.surfaceElevated : (testArea.containsMouse ? skin.surfaceRaised : skin.surfaceBase)
                                border.width: skin.borderThin
                                border.color: skin.edgeStandard
                                opacity: root.isTesting ? 0.6 : 1.0

                                Text {
                                    anchors.centerIn: parent
                                    text: root.isTesting ? "Testing..." : "Test Connection"
                                    color: skin.textPrimary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightMedium
                                }

                                MouseArea {
                                    id: testArea
                                    objectName: "providerTest"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    enabled: !root.isTesting
                                    onClicked: {
                                        root.isTesting = true;
                                        root.testStatusText = "Testing...";
                                        root.testStatusColor = skin.textSecondary;

                                        var payload = {
                                            "id": root.currentProvider ? root.currentProvider.id : "",
                                            "name": nameInput.text,
                                            "provider_type": typeCombo.currentText,
                                            "protocol": protocolCombo.currentText,
                                            "model": modelInput.text,
                                            "base_url": baseUrlInput.text,
                                            "endpoint": endpointInput.text,
                                            "api_version": apiVersionInput.text,
                                            "enabled": true
                                        };

                                        var resStr = guiBridge.testConnection(JSON.stringify(payload), keyInput.text);
                                        root.isTesting = false;
                                        try {
                                            var res = JSON.parse(resStr);
                                            root.testStatusText = res.message;
                                            if (res.success) {
                                                root.testStatusColor = skin.brandPrimary;
                                            } else if (res.message.indexOf("Quota") !== -1) {
                                                root.testStatusColor = skin.luminousWarning;
                                            } else {
                                                root.testStatusColor = skin.luminousCritical;
                                            }
                                            if (res.detected_protocol && res.detected_protocol !== "unknown") {
                                                var pIdx = protocolCombo.model.indexOf(res.detected_protocol);
                                                if (pIdx >= 0) {
                                                    protocolCombo.currentIndex = pIdx;
                                                }
                                            }
                                            if (res.discovered_models && res.discovered_models.length > 0 && (!modelInput.text || modelInput.text === "")) {
                                                modelInput.text = res.discovered_models[0];
                                            }
                                        } catch (e) {
                                            root.testStatusText = "✕ Test failed";
                                            root.testStatusColor = skin.luminousCritical;
                                        }
                                    }
                                }
                            }

                            // Set Active Button
                            Rectangle {
                                Layout.preferredWidth: panel.width < 900 ? 96 : 110
                                Layout.preferredHeight: 40
                                height: 40
                                radius: skin.radiusS
                                color: setActiveArea.pressed ? skin.surfaceElevated : (setActiveArea.containsMouse ? skin.surfaceRaised : skin.surfaceBase)
                                border.width: skin.borderThin
                                border.color: (root.currentProvider && root.currentProvider.is_active) ? skin.brandPrimary : skin.edgeStandard

                                Text {
                                    anchors.centerIn: parent
                                    text: (root.currentProvider && root.currentProvider.is_active) ? "✓ Active" : "Set Active"
                                    color: (root.currentProvider && root.currentProvider.is_active) ? skin.brandPrimary : skin.textPrimary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightMedium
                                }

                                MouseArea {
                                    id: setActiveArea
                                    objectName: "providerActivate"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.currentProvider && root.currentProvider.id) {
                                            // First save changes
                                            saveArea.clicked(null);
                                            guiBridge.setActiveProvider(root.currentProvider.id);
                                        }
                                    }
                                }
                            }

                            // Save Button
                            Rectangle {
                                Layout.preferredWidth: panel.width < 900 ? 120 : 140
                                Layout.preferredHeight: 40
                                height: 40
                                radius: skin.radiusS
                                color: saveArea.pressed ? Qt.darker(skin.brandPrimary, 1.2) : (saveArea.containsMouse ? Qt.lighter(skin.brandPrimary, 1.1) : skin.brandPrimary)

                                Text {
                                    anchors.centerIn: parent
                                    text: "SAVE CHANGES"
                                    color: skin.backgroundDeep
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightBold
                                }

                                MouseArea {
                                    id: saveArea
                                    objectName: "providerSave"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        var pId = root.currentProvider ? root.currentProvider.id : ("custom-" + Date.now());
                                        var payload = {
                                            "id": pId,
                                            "name": nameInput.text,
                                            "provider_type": typeCombo.currentText,
                                            "protocol": protocolCombo.currentText,
                                            "model": modelInput.text,
                                            "base_url": baseUrlInput.text,
                                            "endpoint": endpointInput.text,
                                            "api_version": apiVersionInput.text,
                                            "enabled": true,
                                            "is_active": root.currentProvider ? root.currentProvider.is_active : false
                                        };
                                        var savedId = guiBridge.saveProvider(JSON.stringify(payload), keyInput.text);
                                        if (savedId) {
                                            root.testStatusText = "✓ Configuration saved";
                                            root.testStatusColor = skin.brandPrimary;
                                        }
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }

                            // Delete Button
                            Rectangle {
                                Layout.preferredWidth: panel.width < 900 ? 68 : 80
                                Layout.preferredHeight: 40
                                height: 40
                                radius: skin.radiusS
                                color: deleteArea.pressed ? skin.surfaceElevated : (deleteArea.containsMouse ? skin.surfaceRaised : skin.surfaceLowest)
                                border.width: skin.borderThin
                                border.color: skin.edgeSubtle
                                visible: root.currentProvider && root.currentProvider.id && !root.currentProvider.is_active

                                Text {
                                    anchors.centerIn: parent
                                    text: "Delete"
                                    color: deleteArea.containsMouse ? skin.luminousCritical : skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                }

                                MouseArea {
                                    id: deleteArea
                                    objectName: "providerDelete"
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        if (root.currentProvider && root.currentProvider.id) {
                                            guiBridge.deleteProvider(root.currentProvider.id);
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // === CORE STYLE VIEW ===
                    ColumnLayout {
                        anchors.fill: parent
                        visible: root.activeCategory === "CORE STYLE"
                        spacing: skin.spacingS

                        Text {
                            visible: root.cinematic
                            Layout.fillWidth: true
                            text: "These presets apply to the classic interface. Cinematic core controls are in Interface settings."
                            color: skin.textSecondary;font.family: skin.fontFamily;font.pixelSize: 13;wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "CORE STYLE"
                            color: skin.textPrimary
                            font.family: skin.fontFamily
                            font.pixelSize: skin.fontSizeSection
                            font.weight: skin.fontWeightSemibold
                            font.letterSpacing: skin.letterSpacingEmphasis
                        }

                        // Hairline separator
                        Rectangle {
                            Layout.fillWidth: true
                            height: skin.hairline
                            color: skin.edgeStandard
                        }

                        // Active Core Style Callout Card
                        Rectangle {
                            Layout.fillWidth: true
                            height: 48
                            radius: skin.radiusS
                            color: skin.surfaceLowest
                            border.width: skin.borderThin
                            border.color: skin.edgeSubtle

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: skin.spacingS
                                anchors.rightMargin: skin.spacingS
                                spacing: skin.spacingS

                                Text {
                                    text: "ACTIVE"
                                    color: skin.textTertiary
                                    font.family: skin.fontFamily
                                    font.pixelSize: skin.fontSizeLabelSmall
                                    font.weight: skin.fontWeightMedium
                                    font.letterSpacing: skin.letterSpacingWide
                                }

                                Rectangle {
                                    radius: skin.radiusXS
                                    color: skin.surfaceRaised
                                    border.width: skin.borderThin
                                    border.color: skin.brandPrimary
                                    Layout.preferredHeight: 26
                                    Layout.preferredWidth: activePresetText.implicitWidth + 24

                                    Text {
                                        id: activePresetText
                                        anchors.centerIn: parent
                                        text: "[ " + ((typeof guiBridge !== "undefined" && guiBridge && guiBridge.stylePreset) ? guiBridge.stylePreset : "ASTRA") + " ]"
                                        color: skin.brandPrimary
                                        font.family: skin.fontFamilyMono
                                        font.pixelSize: skin.fontSizeLabelSmall
                                        font.weight: skin.fontWeightBold
                                        font.letterSpacing: skin.letterSpacingEmphasis
                                    }
                                }

                                Item { Layout.fillWidth: true }
                            }
                        }

                        Text {
                            text: "AVAILABLE STYLES"
                            color: skin.textSecondary
                            font.family: skin.fontFamily
                            font.pixelSize: skin.fontSizeLabelSmall
                            font.weight: skin.fontWeightMedium
                            font.letterSpacing: skin.letterSpacingWide
                            Layout.topMargin: skin.spacingXS
                        }

                        // Styles List
                        ScrollView {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true

                            ColumnLayout {
                                width: parent.width
                                spacing: skin.spacingXS

                                Repeater {
                                    model: (typeof guiBridge !== "undefined" && guiBridge && guiBridge.availableStylePresets) ? guiBridge.availableStylePresets : [
                                        {"id": "ASTRA", "name": "ASTRA", "description": "Celestial intelligence globe"},
                                        {"id": "ORIGINAL", "name": "ORIGINAL", "description": "Original E.V. intelligence field"},
                                        {"id": "MINIMAL", "name": "MINIMAL", "description": "Reduced visual Core"},
                                        {"id": "AMBIENT", "name": "AMBIENT", "description": "Atmospheric Core"},
                                        {"id": "FOCUSED", "name": "FOCUSED", "description": "High-energy intelligence Core"}
                                    ]

                                    delegate: Rectangle {
                                        Layout.fillWidth: true
                                        height: 56
                                        radius: skin.radiusS
                                        readonly property bool isSelected: (typeof guiBridge !== "undefined" && guiBridge && guiBridge.stylePreset === modelData.id)
                                        color: isSelected ? skin.surfaceRaised : (styleCardArea.containsMouse ? skin.surfaceBase : skin.surfaceLowest)
                                        border.width: skin.borderThin
                                        border.color: isSelected ? skin.brandPrimary : (styleCardArea.containsMouse ? skin.edgeStandard : skin.edgeSubtle)

                                        RowLayout {
                                            anchors.fill: parent
                                            anchors.leftMargin: skin.spacingM
                                            anchors.rightMargin: skin.spacingM
                                            spacing: skin.spacingS

                                            Text {
                                                text: isSelected ? "●" : "○"
                                                color: isSelected ? skin.brandPrimary : skin.textTertiary
                                                font.family: skin.fontFamily
                                                font.pixelSize: skin.fontSizeBody
                                                font.weight: skin.fontWeightBold
                                            }

                                            ColumnLayout {
                                                Layout.fillWidth: true
                                                spacing: 2

                                                Text {
                                                    text: modelData.name
                                                    color: isSelected ? skin.textPrimary : skin.textSecondary
                                                    font.family: skin.fontFamily
                                                    font.pixelSize: skin.fontSizeLabel
                                                    font.weight: isSelected ? skin.fontWeightSemibold : skin.fontWeightMedium
                                                    font.letterSpacing: skin.letterSpacingWide
                                                }

                                                Text {
                                                    text: modelData.description
                                                    Layout.fillWidth: true
                                                    wrapMode: Text.WordWrap
                                                    color: skin.textTertiary
                                                    font.family: skin.fontFamily
                                                    font.pixelSize: skin.fontSizeLabelSmall
                                                }
                                            }
                                        }

                                        MouseArea {
                                            id: styleCardArea
                                            objectName: "settingsStyle_" + modelData.id
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (typeof guiBridge !== "undefined" && guiBridge) {
                                                    guiBridge.setStylePreset(modelData.id);
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // === PLACEHOLDER VIEWS (VOICE, APPEARANCE, AUDIO, GENERAL) ===
                    ColumnLayout {
                        anchors.fill: parent
                        visible: root.activeCategory !== "AI PROVIDERS" && root.activeCategory !== "CORE STYLE"
                        spacing: skin.spacingS

                        Text {
                            text: root.activeCategory
                            color: skin.textPrimary
                            font.family: skin.fontFamily
                            font.pixelSize: skin.fontSizeSection
                            font.weight: skin.fontWeightSemibold
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            height: skin.hairline
                            color: skin.edgeStandard
                        }

                        Item { Layout.fillHeight: true }

                        ColumnLayout {
                            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
                            spacing: skin.spacingXS

                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: "No preferences here yet"
                                color: skin.brandPrimary
                                font.family: skin.fontFamily
                                font.pixelSize: skin.fontSizeLabel
                                font.weight: skin.fontWeightSemibold
                                font.letterSpacing: skin.letterSpacingWide
                            }

                            Text {
                                Layout.alignment: Qt.AlignHCenter
                                text: "Additional preferences will appear here as they become available."
                                Layout.maximumWidth: panel.width < 900 ? 330 : 460
                                wrapMode: Text.WordWrap
                                horizontalAlignment: Text.AlignHCenter
                                color: skin.textTertiary
                                font.family: skin.fontFamily
                                font.pixelSize: skin.fontSizeBodySmall
                            }
                        }

                        Item { Layout.fillHeight: true }
                    }
                }
            }
        }
    }
}
