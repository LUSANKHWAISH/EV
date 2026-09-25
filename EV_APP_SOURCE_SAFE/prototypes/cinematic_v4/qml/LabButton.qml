import QtQuick

Rectangle {
    id: button
    property string text: ""
    property bool selected: false
    signal clicked()
    implicitWidth: 126
    implicitHeight: 34
    radius: 5
    color: selected ? "#292317" : hover.hovered ? "#171918" : "#101312"
    border.color: selected ? "#8a6b32" : "#252a27"
    Text { anchors.centerIn: parent; text: button.text; color: button.selected ? "#f4d58b" : "#89958d"; font.pixelSize: 12; font.family: "Segoe UI" }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: button.clicked() }
    Accessible.role: Accessible.Button
    Accessible.name: text
    Accessible.onPressAction: clicked()
}
