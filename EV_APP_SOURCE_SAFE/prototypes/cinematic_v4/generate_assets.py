"""Procedural segmented data surfaces and fine gold circuitry for the V4 study.

Reference film frames are never used as render textures. Geometry is batched
triangle surfaces, not thousands of separately drawn tubes or QML objects.
"""
from pathlib import Path
import math
import json
import random
import numpy as np
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QImage, QPainter, QPen, QColor, QPainterPath

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'assets'
OUT.mkdir(exist_ok=True)
TAU=math.tau
manifest={'seed':9416,'meshes':{},'textures':{}}

class Mesh:
    def __init__(self):self.vertices=[];self.indices=[]
    def patch(self,nu,nv,point,uv=lambda u,v:(u,v)):
        base=len(self.vertices)
        for j in range(nv+1):
            v=j/nv
            for i in range(nu+1):
                u=i/nu;p=np.array(point(u,v))
                du=np.array(point(u+.0001,v))-np.array(point(u-.0001,v))
                dv=np.array(point(u,v+.0001))-np.array(point(u,v-.0001))
                n=np.cross(du,dv);n/=max(np.linalg.norm(n),1e-8)
                if np.dot(n,p)<0:n=-n
                self.vertices.append([*p,*n,*uv(u,v)])
        for j in range(nv):
            for i in range(nu):
                a=base+j*(nu+1)+i;b=a+nu+1
                self.indices.extend([a,a+1,b,a+1,b+1,b])
    def save(self,name):
        v=np.asarray(self.vertices,np.float32);i=np.asarray(self.indices,np.uint32)
        np.savez(OUT/(name+'.npz'),vertices=v,indices=i)
        manifest['meshes'][name]={'vertices':len(v),'triangles':len(i)//3}

def sphere(phi,lat,r=100):
    return r*math.cos(lat)*math.cos(phi),r*math.sin(lat),r*math.cos(lat)*math.sin(phi)

def shells():
    rng=random.Random(9416)
    for layer in range(3):
        mesh=Mesh()
        # Irregular zones, not a continuous opaque spherical surface.
        for k in range(24 if layer==0 else 33):
            p0=rng.uniform(0,TAU);ps=rng.uniform(.25,1.4)
            lat=rng.uniform(-1.2,1.05);ls=rng.uniform(.07,.28)
            r=97+rng.uniform(-6,3) if layer==0 else 97+rng.uniform(-9,3)
            def point(u,v,p0=p0,ps=ps,lat=lat,ls=ls,r=r):
                return sphere(p0+u*ps,lat+v*ls,r)
            mesh.patch(max(8,round(ps*22)),4,point,
                       lambda u,v,p0=p0,ps=ps,lat=lat,ls=ls:((p0+u*ps)/TAU,(lat+v*ls)/math.pi+.5))
        mesh.save('shell_'+str(layer))

def bands():
    rng=random.Random(772)
    for group,radius,width in [('outer',101,5.0),('mid',78,7.0),('inner',48,4.2)]:
        mesh=Mesh()
        # Broken annular ribbons with gaps and varying widths.
        a=.15
        while a<TAU-.18:
            span=min(rng.uniform(.2,.85),TAU-.18-a)
            def point(u,v,a=a,span=span):
                angle=a+u*span
                w=width*(.35+.9*math.sin(angle*2+.8)**2)
                r=radius*(.93+.065*math.sin(angle*2+.3))+(v-.5)*w
                return r*math.cos(angle),r*math.sin(angle),radius*.12*math.sin(angle*2+.7)
            mesh.patch(max(6,int(span*35)),3,point,
                       lambda u,v,a=a,span=span:((a+u*span)/TAU,v))
            a+=span+rng.uniform(.03,.18)
        mesh.save('band_'+group)

    # Fine rails and radial tick marks: one mesh, one draw.
    rails=Mesh()
    for radial in [96,98.5,101.2]:
        for k in range(17):
            if k%7==0:continue
            a=k*TAU/17;span=TAU/17*.91
            rails.patch(9,1,lambda u,v,a=a,span=span,radial=radial:
                        ((radial+(v-.5)*.12)*math.cos(a+u*span),
                         (radial+(v-.5)*.12)*math.sin(a+u*span),0),
                        lambda u,v,a=a,span=span:((a+u*span)/TAU,v))
    for k in range(160):
        if k%11 in [0,1,2]:continue
        a=k*TAU/160;length=2.4 if k%5 else 5.8
        rails.patch(1,1,lambda u,v,a=a,length=length:
                    ((96+length*u)*math.cos(a)+(v-.5)*.14*math.sin(a),
                     (96+length*u)*math.sin(a)-(v-.5)*.14*math.cos(a),0))
    rails.save('rails')

def center_and_streams():
    core=Mesh()
    for k in range(7):
        phase=k*TAU/7
        def point(u,v,phase=phase,k=k):
            a=u*TAU*(.67+k*.06)+phase
            radius=9.0+2.6*math.sin(a*1.7+phase)+k*.43+.5*math.sin(a*9+phase)
            ribbon=(v-.5)*(.22+.72*math.sin(math.pi*u)**2)
            return ((radius+ribbon)*math.cos(a),
                    (radius+ribbon)*math.sin(a)*.88,
                    4*math.sin(a*1.2+phase)+k*.35)
        core.patch(160,2,point,lambda u,v,k=k:(u+k*.123,v))
    core.save('core_filaments')
    streams=Mesh()
    for k in range(4):
        phase=k*TAU/4
        def point(u,v,phase=phase,k=k):
            a=phase+u*3.3+.15*math.sin(u*9+phase)
            r=12+69*u
            w=(.15+2.1*math.sin(math.pi*u)**2)*(v-.5)
            return ((r+w)*math.cos(a),(r+w)*math.sin(a)*(.36+.2*math.sin(phase)**2),3+24*math.sin(a+.5)*u)
        streams.patch(150,2,point,lambda u,v,k=k:(u+k*.17,v))
    streams.save('streams')
    inner_filaments()


def inner_filaments():
    """Separate tapered strands, with shared packet coordinates at each fork."""
    full,low=Mesh(),Mesh()
    rng=random.Random(16092624)
    for family,phase in enumerate([2.55,.32,4.55]):
        curl=[.88,-.72,.95][family]
        def center(u):
            a=phase+curl*(u*.65+.35*u*u*(3-2*u))
            r=18+70*u
            return np.array([r*math.cos(a),r*math.sin(a)*[.94,.90,.97][family],
                [-9,13,-14][family]+14*math.sin(u*math.pi+phase)+(u-.5)*[14,-12,8][family]])
        for strand in range(7):
            lane=family*16+strand
            offset=0 if strand==0 else rng.uniform(-1.8,1.8)
            depth=0 if strand==0 else rng.uniform(-4,4)
            phase_offset=rng.uniform(0,TAU)
            width=.40 if strand==0 else rng.uniform(.16,.28)
            def path(u,branch=0.):
                c=center(u)
                tangent=center(u+.001)-center(u-.001)
                side=np.cross(tangent,np.array([0.,0.,1.]));side/=max(np.linalg.norm(side),1e-8)
                taper=max(0,math.sin(math.pi*u))**.8
                c+=side*(offset+.35*math.sin(u*8+phase_offset))*taper
                c[2]+=depth*taper+.45*math.sin(u*7+phase_offset)*taper
                split=max(0,(u-.48)/.44)
                return c+branch*(side*4.8+np.array([0.,0.,8.]))*split**1.5
            for branch in ([0.,1.] if strand==0 else [0.]):
                start,end=(.48,.92) if branch else (0.,1.)
                def point(u,v,start=start,end=end,branch=branch):
                    s=start+(end-start)*u;c=path(s,branch)
                    tangent=path(s+.001,branch)-path(s-.001,branch)
                    side=np.cross(tangent,np.array([0.,0.,1.]));side/=max(np.linalg.norm(side),1e-8)
                    taper=.10+.90*max(0,math.sin(math.pi*u))**.7
                    return c+side*(v-.5)*width*taper*(.7 if branch else 1.)
                uv=lambda u,v,lane=lane,start=start,end=end:(lane+(start+(end-start)*u)*.98,v)
                full.patch(40 if branch else 96,1,point,uv)
                if strand in (0,2,5):low.patch(24 if branch else 56,1,point,uv)
    full.save('energy_ribbons');low.save('energy_ribbons_low')

def plates():
    mesh=Mesh();rng=random.Random(2501)
    for k in range(60):
        a=rng.uniform(0,TAU);lat=rng.uniform(-1.08,1.08)
        radius=rng.uniform(91,110)
        center=np.asarray(sphere(a,lat,radius))
        right=np.asarray((-math.sin(a),0,math.cos(a)))
        up=np.asarray((-math.sin(lat)*math.cos(a),math.cos(lat),-math.sin(lat)*math.sin(a)))
        width=rng.uniform(2,11);height=rng.uniform(3,14)
        # Outlying tangent data panels preserve the angular, irregular silhouette.
        mesh.patch(1,1,lambda u,v,c=center,r=right,t=up,w=width,h=height:tuple(c+(u-.5)*w*r+(v-.5)*h*t),
                   lambda u,v,k=k:(u*.10+(k%7)*.127,v*.14+(k%5)*.18))
    mesh.save('plates')

def circuit_routes():
    rng=random.Random(9471)
    full,low=Mesh(),Mesh()
    def line(mesh,p0,p1,width,seed):
        p0=np.array(p0);p1=np.array(p1)
        tangent=p1-p0
        side=np.cross(tangent,(p0+p1)*.5)
        side/=max(np.linalg.norm(side),1e-8)
        mesh.patch(1,1,lambda u,v:tuple(p0+u*tangent+(v-.5)*width*side),
                   lambda u,v:(u*.02+seed,v))
    clusters=[(rng.uniform(0,TAU),rng.uniform(-1.18,1.18),rng.uniform(66,101),rng.uniform(.10,.32)) for _ in range(45)]
    for k in range(2100):
        center_phi,center_lat,center_r,spread=clusters[k%len(clusters)]
        phi=center_phi+rng.gauss(0,spread);lat=center_lat+rng.gauss(0,spread*.65)
        r=center_r+rng.uniform(-1.6,1.6)
        width=rng.uniform(.11,.23)
        for step in range(rng.randrange(2,7)):
            p0=sphere(phi,lat,r)
            if step%2:phi+=rng.choice([-1,1])*rng.uniform(.007,.085)
            else:lat+=rng.choice([-1,1])*rng.uniform(.008,.07)
            p1=sphere(phi,lat,r)
            line(full,p0,p1,width,k*.002)
            if k%3==0:line(low,p0,p1,width*1.15,k*.002)
    full.save('circuit_routes');low.save('circuit_routes_low')

def peripheral_schematics():
    """Partial radial data boards, with open combs and outlying angular traces."""
    mesh=Mesh();rng=random.Random(1904)
    def point(a,r,z):return np.array((r*math.cos(a),r*math.sin(a),z+4*math.sin(a*3)))
    def stroke(a0,r0,a1,r1,z,width,seed):
        p0,p1=point(a0,r0,z),point(a1,r1,z)
        side=np.cross(p1-p0,np.array((0,0,1.)))
        side/=max(np.linalg.norm(side),1e-8)
        mesh.patch(1,1,lambda u,v:tuple(p0+u*(p1-p0)+(v-.5)*width*side),lambda u,v:(seed+u*.03,v))
    for sector in range(17):
        a0=sector*TAU/17+rng.uniform(-.10,.08)
        span=rng.uniform(.12,.32);z=rng.uniform(-23,24)
        inner=rng.uniform(79,96);outer=rng.uniform(104,116)
        for line in range(rng.randrange(14,24)):
            a=a0+rng.random()*span;r=inner+rng.random()*(outer-inner)*.6
            for step in range(rng.randrange(2,6)):
                aa=a+rng.uniform(.009,.035) if step%2 else a
                rr=r+rng.uniform(1,5) if not step%2 else r
                rr=min(rr,outer)
                stroke(a,r,aa,rr,z,rng.uniform(.22,.38),sector*.07+line*.001)
                if step==2:
                    stroke(aa-.004,rr,aa+.004,rr,z,.95,sector*.07)
                a,r=aa,rr
        # Discontinuous outer rails keep the silhouette visibly unfinished.
        for j in range(4):
            a=a0+j*span/4
            stroke(a,outer,a+span*.18,outer,z,.12,sector*.1)
    mesh.save('peripheral_schematics')

def gray(w,h):
    im=QImage(w,h,QImage.Format.Format_Grayscale8);im.fill(0);return im

def array(im):
    return np.frombuffer(im.constBits(),np.uint8).reshape(im.height(),im.bytesPerLine())[:,:im.width()].copy().astype(np.float32)/255

def blur(a):
    return (a*4+np.roll(a,1,0)+np.roll(a,-1,0)+np.roll(a,1,1)+np.roll(a,-1,1))/8

def save(name,channels):
    a=np.clip(np.stack(channels,-1)*255,0,255).astype(np.uint8);h,w=a.shape[:2]
    im=QImage(a.data,w,h,a.strides[0],QImage.Format.Format_RGBA8888).copy()
    assert im.save(str(OUT/name))
    manifest['textures'][name]={'width':w,'height':h,'format':'RGBA8'}

def textures():
    rng=random.Random(932);w,h=2048,1024
    traces,pads,major=gray(w,h),gray(w,h),gray(w,h)
    pt,pp,pm=QPainter(traces),QPainter(pads),QPainter(major)
    for painter in [pt,pp,pm]:painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for k in range(5600):
        x=rng.randrange(w);y=rng.randrange(h)
        b=rng.randrange(90,240)
        pt.setPen(QPen(QColor(b,b,b),rng.choice([.7,.8,1.])))
        p=QPainterPath(QPointF(x,y))
        for step in range(rng.randrange(2,7)):
            length=rng.randrange(2,20)
            if step%2:x+=length*rng.choice([-1,1])
            else:y+=length*rng.choice([-1,1])
            p.lineTo(x,y)
        pt.drawPath(p)
        if k%3==0:
            pp.setPen(Qt.PenStyle.NoPen);pp.setBrush(QColor(255,255,255))
            pp.drawRect(x,y,rng.choice([1,1,2,3]),rng.choice([1,1,2]))
    for k in range(380):
        x=rng.randrange(w-80);y=rng.randrange(h-60)
        ww=rng.randrange(10,75);hh=rng.randrange(6,50)
        pm.setPen(QPen(QColor(160,160,160),.85));pm.setBrush(Qt.BrushStyle.NoBrush)
        # Asymmetric open schematics, pads and short parallel bus routes.
        pm.drawLine(x,y,x+ww,y);pm.drawLine(x,y,x,y+hh)
        pm.drawLine(x,y+hh,x+ww*.62,y+hh)
        for row in range(1,rng.randrange(2,8)):
            yy=y+row*3
            pt.setPen(QPen(QColor(120,120,120),.7));pt.drawLine(x+4,yy,x+ww-3,yy)
    for painter in [pt,pp,pm]:painter.end()
    t,p,m=array(traces),array(pads),array(major)
    y,x=np.mgrid[0:h,0:w].astype(np.float32);u=x/w;v=y/h
    activation=.35+.65*(.5+.5*np.sin(TAU*(u*7+v*4)+np.sin(TAU*v*9)))
    lines=np.maximum(t,m)
    save('circuit.png',[lines,blur(lines)*.55,p,activation])
    low=QImage(str(OUT/'circuit.png')).scaled(1024,512,Qt.AspectRatioMode.IgnoreAspectRatio,Qt.TransformationMode.SmoothTransformation)
    low.save(str(OUT/'circuit_low.png'))
    manifest['textures']['circuit_low.png']={'width':1024,'height':512,'format':'RGBA8'}
    # Dense fine-track ribbon texture, with data gaps and no solid stripe fill.
    w,h=2048,256;y,x=np.mgrid[0:h,0:w].astype(np.float32);u=x/w;v=y/h
    tracks=np.maximum(0,np.cos(TAU*(v*8+.13*np.sin(TAU*u*8))))**20
    gates=.45+.55*(np.sin(TAU*(u*43+v*2))>-.1)
    fine=tracks*gates
    tick=(np.maximum(0,np.cos(TAU*u*140))**40)*(np.maximum(0,np.cos(TAU*v*3))**12)
    save('bands.png',[fine,blur(fine)*.25,tick,np.ones_like(fine)])
    # Flow data is periodic so UV animation has no wrap jump.
    w,h=512,256;y,x=np.mgrid[0:h,0:w].astype(np.float32);u=x/w;v=y/h
    r=.5+.24*np.sin(TAU*(u*3+v*2))+.08*np.sin(TAU*(u*13-v*5))
    g=.5+.24*np.cos(TAU*(u*2-v*3))+.08*np.cos(TAU*(u*7+v*9))
    b=.5+.3*np.sin(TAU*(u*5+v*3))*.6+.2*np.sin(TAU*(u*17-v*11))
    save('flow.png',[r,g,b,np.ones_like(r)])

def main():
    shells();bands();center_and_streams();plates();circuit_routes();peripheral_schematics();textures()
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
