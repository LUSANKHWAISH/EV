import numpy as np, trimesh, math, os, json, hashlib
from pathlib import Path
from trimesh.visual.material import PBRMaterial

OUT=Path(__file__).resolve().parent; AS=OUT/'assets'; AS.mkdir(parents=True, exist_ok=True)

# materials
def mat(name, color, metallic=.7, rough=.35, emissive=None, alpha=255):
    rgba=list(color[:3])+[alpha]
    return PBRMaterial(name=name, baseColorFactor=rgba, metallicFactor=metallic, roughnessFactor=rough, emissiveFactor=(emissive or [0,0,0]))

graphite=mat('Graphite',[24,29,36],.82,.28)
graphite2=mat('GraphiteDeep',[10,14,19],.78,.40)
steel=mat('EdgeTitanium',[85,96,110],.86,.22)
black=mat('CognitionVoid',[1,2,4],.05,.98)
white=mat('IceWhite',[210,235,255],.18,.14,[0.82,0.94,1.0])
cool=mat('CoolEnergy',[95,185,255],.12,.12,[0.30,0.72,1.0])
warm=mat('WarmEnergy',[255,138,62],.12,.14,[1.0,0.42,0.12])

# utility

def polar_xy(r, a, xscale=1.0, yscale=1.0, ox=0, oy=0):
    return np.array([ox + xscale*r*np.cos(a), oy + yscale*r*np.sin(a)])

def make_shell(angle0, angle1, rin_fn, rout_fn, z_fn, thickness=18, nA=64, nR=7, xscale=1.0, yscale=1.0, ox=0, oy=0, camber=10, material=graphite, name='shell'):
    a_vals=np.linspace(np.deg2rad(angle0), np.deg2rad(angle1), nA+1)
    verts=[]
    # front and back grids
    for side in [0,1]:
        for ia,a in enumerate(a_vals):
            t=ia/nA
            rin=rin_fn(t); rout=rout_fn(t)
            basez=z_fn(t)
            for ir in range(nR+1):
                u=ir/nR
                r=rin+(rout-rin)*u
                # engineered camber with two facet ridges
                fac = (0.55*np.sin(np.pi*u) + 0.15*np.sin(3*np.pi*u))
                z=basez + camber*fac
                if side==1: z -= thickness
                xy=polar_xy(r,a,xscale,yscale,ox,oy)
                verts.append([xy[0],xy[1],z])
    verts=np.asarray(verts,float)
    stride=nR+1; layer=(nA+1)*stride
    faces=[]
    # front/back surfaces
    for side in [0,1]:
        base=side*layer
        for ia in range(nA):
            for ir in range(nR):
                i0=base+ia*stride+ir; i1=i0+1; i2=base+(ia+1)*stride+ir; i3=i2+1
                if side==0:
                    faces += [[i0,i2,i1],[i1,i2,i3]]
                else:
                    faces += [[i0,i1,i2],[i1,i3,i2]]
    # radial inner/outer walls
    for ia in range(nA):
        for ir in [0,nR]:
            f0=ia*stride+ir; f1=(ia+1)*stride+ir; b0=layer+f0; b1=layer+f1
            if ir==0: faces += [[f0,b0,f1],[f1,b0,b1]]
            else: faces += [[f0,f1,b0],[f1,b1,b0]]
    # end caps
    for ia in [0,nA]:
        for ir in range(nR):
            f0=ia*stride+ir; f1=f0+1; b0=layer+f0; b1=b0+1
            if ia==0: faces += [[f0,f1,b0],[f1,b1,b0]]
            else: faces += [[f0,b0,f1],[f1,b0,b1]]
    mesh=trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=True)
    mesh.visual.material=material
    metadata={'name':name}
    mesh.metadata.update(metadata)
    return mesh

def make_rib(angle_deg, r0,r1,width=5, depth=8,z=20, xscale=1.0, yscale=1.0, material=steel):
    # box oriented radially
    length=r1-r0
    m=trimesh.creation.box(extents=[length,width,depth])
    m.visual.material=material
    a=np.deg2rad(angle_deg); rm=(r0+r1)/2
    # box local X radial
    T=trimesh.transformations.rotation_matrix(a,[0,0,1])
    m.apply_transform(T)
    m.apply_translation([xscale*rm*np.cos(a), yscale*rm*np.sin(a), z])
    return m

def bezier(p0,p1,p2,p3,t):
    return (1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3

def tube_curve(points, radii, sides=12, material=white, name='tube'):
    pts=np.asarray(points,float); n=len(pts)
    tang=np.zeros_like(pts)
    tang[1:-1]=pts[2:]-pts[:-2]; tang[0]=pts[1]-pts[0]; tang[-1]=pts[-1]-pts[-2]
    tang/=np.linalg.norm(tang,axis=1)[:,None]
    frames=[]; prev_n=np.array([0.,0.,1.])
    for i,t in enumerate(tang):
        if abs(np.dot(prev_n,t))>.92: prev_n=np.array([0.,1.,0.])
        b=np.cross(t,prev_n); b/=np.linalg.norm(b)
        nvec=np.cross(b,t); nvec/=np.linalg.norm(nvec)
        prev_n=nvec
        frames.append((nvec,b))
    verts=[]
    for i,p in enumerate(pts):
        nvec,b=frames[i]; r=radii[i] if np.ndim(radii)>0 else radii
        for s in range(sides):
            ang=2*np.pi*s/sides
            verts.append(p+r*(np.cos(ang)*nvec+np.sin(ang)*b))
    faces=[]
    for i in range(n-1):
        for s in range(sides):
            ns=(s+1)%sides
            a=i*sides+s; b0=i*sides+ns; c=(i+1)*sides+s; d=(i+1)*sides+ns
            faces += [[a,c,b0],[b0,c,d]]
    # watertight end caps
    start_center=len(verts); verts.append(pts[0].tolist())
    end_center=len(verts); verts.append(pts[-1].tolist())
    for s in range(sides):
        ns=(s+1)%sides
        faces.append([start_center, ns, s])
        a=(n-1)*sides+s; b=(n-1)*sides+ns
        faces.append([end_center, a, b])
    mesh=trimesh.Trimesh(vertices=np.asarray(verts),faces=np.asarray(faces),process=True)
    mesh.visual.material=material; mesh.metadata['name']=name
    return mesh

def arc_tube(a0,a1,r, z_fn, minor=2.4, n=96, xscale=1.0, yscale=1.0, material=white,name='arc'):
    pts=[]
    for i,a in enumerate(np.linspace(np.deg2rad(a0),np.deg2rad(a1),n)):
        t=i/(n-1); xy=polar_xy(r,a,xscale,yscale)
        pts.append([xy[0],xy[1],z_fn(t)])
    return tube_curve(pts, np.linspace(minor,minor*0.88,n), 12, material,name)


def make_frustum(r_front, r_back, depth, sections=96, material=black):
    # Mouth at z=0, back ring at z=-depth. Closed side + back cap; front left open.
    verts=[]
    for z,r in [(0.0,r_front),(-depth,r_back)]:
        for i in range(sections):
            a=2*np.pi*i/sections
            verts.append([r*np.cos(a), r*0.92*np.sin(a), z])
    verts.append([0,0,-depth])
    back_center=2*sections
    faces=[]
    for i in range(sections):
        j=(i+1)%sections
        faces += [[i,j,sections+i],[j,sections+j,sections+i]]
        faces.append([back_center,sections+j,sections+i])
    m=trimesh.Trimesh(vertices=np.asarray(verts),faces=np.asarray(faces),process=True)
    m.visual.material=material
    return m

# Main left containment mass: broad, irregular, front-biased
left=make_shell(118,238,
    lambda t: 98+10*np.sin(np.pi*t)+6*np.sin(3*np.pi*t),
    lambda t: 205-22*t+8*np.sin(2*np.pi*t),
    lambda t: 42+18*np.sin(np.pi*t)-12*t,
    thickness=30,nA=62,nR=8,xscale=1.0,yscale=.86,ox=-14,oy=4,camber=16,material=graphite,name='primary_left')
# cut visual via ribs / inset geometry as separate scene pieces
left_ribs=[make_rib(a,132,194,4.5,7,52,1,.86,steel) for a in [136,168,205,232]]

# Right containment mass, shorter, forward and more angular
right=make_shell(-18,66,
    lambda t: 112+5*np.sin(2*np.pi*t),
    lambda t: 210+14*np.sin(np.pi*t)-12*t,
    lambda t: 58-14*np.sin(np.pi*t)+12*t,
    thickness=26,nA=48,nR=8,xscale=1.02,yscale=.86,ox=18,oy=10,camber=14,material=graphite,name='primary_right')
right_ribs=[make_rib(a,140,192,4.0,6,67,1.02,.86,steel) for a in [0,24,50]]

# Lower rear buttress: creates deep silhouette without closing circle
rear=make_shell(272,344,
    lambda t: 130+6*np.sin(np.pi*t),
    lambda t: 222-8*np.sin(np.pi*t),
    lambda t: -46-18*np.sin(np.pi*t),
    thickness=34,nA=44,nR=7,xscale=1.02,yscale=.86,ox=16,oy=-12,camber=10,material=graphite2,name='rear_buttress')
rear_ribs=[make_rib(a,154,208,3.5,5,-34,1.02,.86,steel) for a in [286,316,340]]

# Inner collar: partial precision structure, not full ring
collar1=make_shell(142,212,
    lambda t: 72+2*np.sin(np.pi*t), lambda t: 92+3*np.sin(2*np.pi*t),
    lambda t: 26+4*np.sin(np.pi*t), thickness=12,nA=44,nR=4,xscale=1,yscale=.92,camber=4,material=steel,name='collar_left')
collar2=make_shell(-18,54,
    lambda t: 74+2*np.sin(np.pi*t), lambda t: 94+4*np.sin(np.pi*t),
    lambda t: 19-5*np.sin(np.pi*t), thickness=11,nA=46,nR=4,xscale=1,yscale=.92,camber=4,material=steel,name='collar_right')

# Deep void funnel: nested truncated cylinders, create real tunnel
# outer dark cylinder/cone via truncated cone
void_outer=make_frustum(67,46,90,96,black)
void_outer.apply_translation([0,0,8])
# inner back disk sphere-ish dark cap
void_cap=trimesh.creation.icosphere(subdivisions=4,radius=42)
void_cap.apply_scale([1.0,.92,.38]); void_cap.apply_translation([0,0,-82]); void_cap.visual.material=black

# segmented halo: thin partial arcs, not full circle
halo_parts=[
    arc_tube(126,190,101,lambda t:34+5*np.sin(np.pi*t),2.8,70,1,.92,cool,'halo_cool'),
    arc_tube(230,284,102,lambda t:22-6*np.sin(np.pi*t),2.5,62,1,.92,white,'halo_white'),
    arc_tube(-36,22,100,lambda t:31+8*t,2.9,66,1,.92,warm,'halo_warm'),
]

# Curved accretion / computation stream. Skirts void, passes rear-left to front-right, not straight.
ts=np.linspace(0,1,96)
p0=np.array([-220.,-70.,-46.]); p1=np.array([-135.,-146.,-64.]); p2=np.array([85.,-126.,24.]); p3=np.array([225.,-34.,76.])
curve=np.array([bezier(p0,p1,p2,p3,t) for t in ts])
# carve avoidance around exact center by y offset wave, enhances S
curve[:,1]-=10*np.sin(np.pi*ts)
stream_warm=tube_curve(curve, 4.8*(.75+.25*np.sin(np.pi*ts)),14,warm,'energy_stream_warm')
# white/cool core slightly offset in z and thinner
curve2=curve.copy(); curve2[:,2]+=4; curve2[:,1]+=3
stream_core=tube_curve(curve2, 1.7*(.85+.15*np.sin(np.pi*ts)),12,white,'energy_stream_core')

# Rear cognition lattice: 3 radial structural blades behind void, subtle
rear_blades=[]
for a in [96, 246, 334]:
    rear_blades.append(make_rib(a,88,164,7,8,-66,1,.9,graphite2))

# Nodes: small metallic spheres near inner field
nodes=[]
for x,y,z,r in [(-48,38,18,3.2),(44,-33,10,2.6),(35,48,-4,2.2),(-28,-50,-12,2.5),(8,57,-22,1.8)]:
    s=trimesh.creation.icosphere(subdivisions=2,radius=r); s.apply_translation([x,y,z]); s.visual.material=steel; nodes.append(s)

# export scenes
def export_scene(filename, geoms):
    sc=trimesh.Scene()
    for i,g in enumerate(geoms): sc.add_geometry(g,node_name=f'{Path(filename).stem}_{i}')
    data=sc.export(file_type='glb')
    (AS/filename).write_bytes(data)

export_scene('ev_core_flagship_left.glb',[left]+left_ribs)
export_scene('ev_core_flagship_right.glb',[right]+right_ribs)
export_scene('ev_core_flagship_rear.glb',[rear]+rear_ribs+rear_blades)
export_scene('ev_core_flagship_collar.glb',[collar1,collar2])
export_scene('ev_core_flagship_void.glb',[void_outer,void_cap])
export_scene('ev_core_flagship_halo.glb',halo_parts)
export_scene('ev_core_flagship_stream.glb',[stream_warm,stream_core])
export_scene('ev_core_flagship_nodes.glb',nodes)

for fp in sorted(AS.glob('*.glb')):
    sc=trimesh.load(fp,force='scene')
    print(fp.name, fp.stat().st_size, sc.bounds)

