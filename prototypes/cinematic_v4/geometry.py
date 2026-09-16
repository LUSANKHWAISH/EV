"""Small shared mesh and immutable instance buffers for the presentation lab."""
from pathlib import Path
import numpy as np
from PySide6.QtCore import Property, Signal, QByteArray
from PySide6.QtGui import QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry, QQuick3DInstancing

ASSETS=Path(__file__).resolve().parent/'assets'

class LabGeometry(QQuick3DGeometry):
    meshChanged=Signal()
    def __init__(self,parent=None):
        super().__init__(parent);self._mesh=''
    @Property(str,notify=meshChanged)
    def mesh(self):return self._mesh
    @mesh.setter
    def mesh(self,value):
        if value==self._mesh:return
        self._mesh=value
        data=np.load(ASSETS/(value+'.npz'))
        vertices=data['vertices'];indices=data['indices']
        self.clear();self.setStride(32)
        self.setVertexData(QByteArray(vertices.tobytes()))
        self.setIndexData(QByteArray(indices.tobytes()))
        A=QQuick3DGeometry.Attribute
        self.addAttribute(A.PositionSemantic,0,A.F32Type)
        self.addAttribute(A.NormalSemantic,12,A.F32Type)
        self.addAttribute(A.TexCoordSemantic,24,A.F32Type)
        self.addAttribute(A.IndexSemantic,0,A.U32Type)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.setBounds(QVector3D(*vertices[:,:3].min(0).tolist()),QVector3D(*vertices[:,:3].max(0).tolist()))
        self.update();self.meshChanged.emit()

class ParticleInstances(QQuick3DInstancing):
    """One upload. Motion is computed in the vertex shader, not Python per particle."""
    def __init__(self,parent=None):
        super().__init__(parent)
        rng=np.random.default_rng(3701)
        count=3072
        # Qt's instance entries: three transform rows, color, custom data (20 float32s).
        data=np.zeros((count,20),np.float32)
        data[:,0]=1;data[:,5]=1;data[:,10]=1
        data[:,12:16]=1
        data[:,16:20]=rng.random((count,4))
        self._buffer=QByteArray(data.tobytes());self._count=count
        self.setHasTransparency(True)
        self.setDepthSortingEnabled(False)
        self.setShadowBoundsMinimum(QVector3D(-130,-130,-130))
        self.setShadowBoundsMaximum(QVector3D(130,130,130))
    def getInstanceBuffer(self):
        return self._buffer, self._count
