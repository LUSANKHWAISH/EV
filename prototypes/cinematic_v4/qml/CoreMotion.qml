import QtQuick

QtObject {
    // Rigid layers orbit inside a stable volume. Activity changes bounded tilt,
    // not radius or phase speed; the existing motion clock supplies smooth pace.
    property real clock: 0
    property real response: 0
    function arcRotation(i) {
        return Qt.vector3d(
            [18,54,-32][i]+Math.sin(clock*.28+i*1.7)*[7,9,6][i]+response*[6,-5,4][i],
            [30,-43,18][i]+clock*[4,-3,2][i]+Math.sin(clock*.21+i)*4,
            [-30,20,63][i]+clock*[7.2,-5.4,4][i])
    }
    readonly property vector3d hubRotation: Qt.vector3d(12+9*Math.sin(clock*.41)+response*5,-12+12*Math.sin(clock*.29),-clock*21)
    readonly property vector3d counterRotation: Qt.vector3d(32+8*Math.sin(clock*.63),18+9*Math.cos(clock*.37),clock*38+27)
}
