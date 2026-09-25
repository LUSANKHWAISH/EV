"""Deterministic instance data and Quick3D component for the expansive 3D cosmic depth particle field."""
from pathlib import Path
import numpy as np
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QVector3D
from PySide6.QtQuick3D import QQuick3DInstancing


def make_cosmic_depth_instance_data(count=3200, seed=4821):
    """Return deterministic Qt Quick 3D instance entries for the 3D depth cosmic particle field."""
    if count <= 0:
        raise ValueError("count must be positive")

    rng = np.random.default_rng(seed)
    data = np.zeros((count, 20), np.float32)

    # Identity transform rows.
    data[:, 0] = 1
    data[:, 5] = 1
    data[:, 10] = 1

    # Neutral instance color. Final color/shading is computed in the shader.
    data[:, 12:16] = 1

    # Deterministic custom particle seeds:
    # x: phase / orbital angle
    # y: radial distance distribution
    # z: inclination / latitude
    # w: twinkle rate / turbulence / size class
    data[:, 16:20] = rng.random((count, 4), dtype=np.float32)
    return data


class CosmicDepthInstances(QQuick3DInstancing):
    """Immutable seeded data for the expansive 3D depth cosmic particle cloud."""

    DEFAULT_COUNT = 3200

    def __init__(self, parent=None):
        super().__init__(parent)
        data = make_cosmic_depth_instance_data(self.DEFAULT_COUNT)
        self._buffer = QByteArray(data.tobytes())
        self._count = len(data)

        self.setHasTransparency(True)
        self.setDepthSortingEnabled(False)

        # Expansive volumetric bounds so particles are never clipped prematurely
        self.setShadowBoundsMinimum(QVector3D(-1200, -900, -600))
        self.setShadowBoundsMaximum(QVector3D(1200, 900, 600))

    def getInstanceBuffer(self):
        return self._buffer, self._count
