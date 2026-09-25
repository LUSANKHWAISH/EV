import QtQuick
import QtQuick.Controls

Button {
    id:control
    property bool selected:false
    property bool quiet:false
    property bool accent:false
    implicitWidth:126;implicitHeight:36
    hoverEnabled:true;focusPolicy:Qt.StrongFocus
    font.family:'Segoe UI';font.pixelSize:11;font.letterSpacing:1.2;padding:10
    contentItem:Text {
        text:control.text
        color:!control.enabled?'#4f6066':control.selected||control.accent?'#ecc681':control.hovered||control.activeFocus?'#eef2ee':'#8b9ca2'
        font:control.font;horizontalAlignment:Text.AlignHCenter;verticalAlignment:Text.AlignVCenter;elide:Text.ElideRight
    }
    background:Rectangle {
        radius:3
        color:control.down?'#27302c':control.selected?'#24231d':control.hovered?'#111d23':control.quiet?'transparent':'#0b1319'
        border.width:control.quiet&&!control.activeFocus&&!control.selected?0:1
        border.color:control.activeFocus?'#d8b66b':control.selected?'#635338':'#26343b'
        Rectangle { visible:control.selected;width:22;height:1;color:'#e8b861';anchors.horizontalCenter:parent.horizontalCenter;anchors.bottom:parent.bottom }
    }
}
