import QtQuick 2.15
import "../theme"

// EVSectionLabel - A label for section headings, using typography system
// Similar to a title but for sections within a panel
Item {
    id: root

    // Properties
    property string text: ""
    property bool muted: false   // use tertiary color instead of primary
    property bool small: false   // use smaller font size
    property real letterSpacing: Theme.letterSpacingNormal
    property real lineHeight: Theme.lineHeightNormal
    property int alignment: Qt.AlignLeft | Qt.AlignVCenter   // default alignment

    // Text element
    Text {
        id: label
        text: root.text
        font.family: Theme.fontFamily
        font.pointSize: root.small ? Theme.fontSizeLabelSmall : Theme.fontSizeLabel
        font.weight: Theme.fontWeightMedium
        font.letterSpacing: root.letterSpacing
        lineHeight: root.lineHeight
        color: root.muted ? Theme.textTertiary : Theme.textPrimary
        horizontalAlignment: root.alignment & Qt.AlignHorizontal_Mask
        verticalAlignment: root.alignment & Qt.AlignVertical_Mask
        elide: Text.ElideRight
    }

    // Expose the text's implicit size for layout purposes
    implicitWidth: label.implicitWidth
    implicitHeight: label.implicitHeight
}