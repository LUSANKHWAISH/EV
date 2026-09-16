"""Batched branching energy paths and projection geometry; no frame textures."""
import json
import math
import random
import numpy as np
from . import generate_assets as base


def paths():
    rng=random.Random(160926)
    full,low=base.Mesh(),base.Mesh()
    for family in range(72):
        phi=rng.uniform(0,math.tau);lat=rng.uniform(-1.1,1.1)
        curl=rng.choice([-1,1])*rng.uniform(.75,1.9)
        radius=rng.uniform(83,104);width=rng.uniform(.12,.24)
        def center(u,bend=0.,fork=.44):
            branch=max(0.,(u-fork)/(1-fork))
            angle=phi+curl*u+bend*branch**1.3+.08*math.sin(u*12+phi)
            latitude=lat*(.3+.7*u)+.14*math.sin(u*math.pi+phi)+bend*.2*branch
            return np.asarray(base.sphere(angle,latitude,13+(radius-13)*u))
        for branch in range(2 if family%3 else 1):
            start=.44 if branch else 0.
            bend=rng.choice([-1,1])*.65 if branch else 0.
            def point(u,v,start=start,bend=bend):
                s=start+(1-start)*u;c=center(s,bend)
                tangent=center(s+.001,bend)-center(s-.001,bend)
                side=np.cross(tangent,c);side/=max(np.linalg.norm(side),1e-8)
                return c+side*(v-.5)*width*(.75+.25*math.sin(s*math.pi))
            uv=lambda u,v,start=start,family=family:(family+(start+(1-start)*u)*.98,v)
            full.patch(64,1,point,uv)
            if family%3==1:low.patch(40,1,point,uv)
    full.save('neural_paths');low.save('neural_paths_low')


def orbits():
    for name,radius in [('flow_band_outer',100),('flow_band_mid',76)]:
        mesh=base.Mesh();rng=random.Random(361+int(radius))
        angle=.08
        while angle<math.tau-.12:
            span=min(rng.uniform(.24,.78),math.tau-.12-angle)
            def point(u,v,a=angle,span=span):
                theta=a+u*span
                r=radius*(.985+.018*math.sin(theta*3+.4))
                w=1.2+4.6*math.sin(theta*1.5+.7)**2
                r+=(v-.5)*w
                return r*math.cos(theta),r*math.sin(theta),radius*.055*math.sin(theta*2+.2)
            mesh.patch(max(8,int(span*42)),3,point,
                       lambda u,v,a=angle,span=span:((a+u*span)/math.tau,v))
            angle+=span+rng.uniform(.025,.09)
        mesh.save(name)
    trail=base.Mesh()
    trail.patch(96,1,lambda u,v:(-64*(1-u)+10*math.sin(math.pi*u)+(v-.5)*.65,
                                -72*(1-u)+28*math.sin(math.pi*u),12),lambda u,v:(u,v))
    trail.save('launch_trail')


def main():
    paths();orbits()
    destination=base.OUT/'manifest.json'
    manifest=json.loads(destination.read_text())
    manifest['meshes'].update(base.manifest['meshes'])
    manifest['flow_seed']=160926
    destination.write_text(json.dumps(manifest,indent=2))
    print(json.dumps(base.manifest['meshes'],indent=2))


if __name__=='__main__':main()
