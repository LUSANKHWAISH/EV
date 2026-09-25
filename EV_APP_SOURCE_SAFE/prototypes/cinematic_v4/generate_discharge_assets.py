"""Short branching golden arcs, batched into one draw per quality mode."""
import json
import math
import random
import numpy as np
from . import generate_assets as base


def main():
    rng = random.Random(16092648)
    full, low = base.Mesh(), base.Mesh()
    for lane in range(48):
        phi = rng.uniform(0, math.tau)
        lat = rng.uniform(-1.1, 1.1)
        radius = rng.uniform(38, 78)
        end_radius = min(108, radius + rng.uniform(20, 38))
        curl = rng.choice([-1, 1]) * rng.uniform(.15, .52)
        knots = np.linspace(0, 1, 13)
        noise = np.array([0] + [rng.uniform(-1, 1) for _ in range(11)] + [0])
        def center(u, fork=0.):
            jag = float(np.interp(u, knots, noise))
            branch = max(0., (u-.5)*2)
            return np.asarray(base.sphere(phi+curl*u+jag*.022+fork*branch*.18,
                lat+jag*.028-fork*branch*.13, radius+(end_radius-radius)*u))
        for fork in (0., rng.choice([-1., 1.])):
            start = .5 if fork else 0.
            width = 1.7 if fork else 3.2
            def point(u, v, start=start, fork=fork, width=width):
                s = start+(1-start)*u
                c = center(s, fork)
                tangent = center(min(1,s+.001),fork)-center(max(0,s-.001),fork)
                side = np.cross(tangent,c)
                side /= max(np.linalg.norm(side),1e-8)
                return c+side*(v-.5)*width
            uv = lambda u,v,start=start,lane=lane: (lane+(start+(1-start)*u)*.98,v)
            segments = 6 if fork else 12
            full.patch(segments, 1, point, uv)
            if lane%3 == 0:
                low.patch(segments, 1, point, uv)
    full.save('gold_discharges'); low.save('gold_discharges_low')
    destination = base.OUT/'manifest.json'
    manifest = json.loads(destination.read_text())
    manifest['meshes'].update(base.manifest['meshes'])
    manifest['discharge_seed'] = 16092648
    destination.write_text(json.dumps(manifest,indent=2))
    print(json.dumps(base.manifest['meshes'],indent=2))


if __name__ == '__main__': main()
