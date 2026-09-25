import numpy as np
import trimesh
from pathlib import Path
import math, json, hashlib, zipfile

OUT = Path('/mnt/data/ev_r10_depth_precision_package')
AS = OUT / 'assets'
AS.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# MATERIALS
# -----------------------------------------------------------------------------
def pbr(name, rgba, metallic=0.8, roughness=0.25, emissive=None, double=False):
    return trimesh.visual.material.PBRMaterial(
        name=name,
        baseColorFactor=np.array(rgba, dtype=np.uint8),
        metallicFactor=float(metallic),
        roughnessFactor=float(roughness),
        emissiveFactor=None if emissive is None else np.array(emissive, dtype=float),
        doubleSided=double,
    )

GRAPHITE_PRIMARY = pbr('EV_R10DP_PrimaryGraphite', [22, 29, 38, 255], .88, .22)
GRAPHITE_MID     = pbr('EV_R10DP_MidGraphite',     [38, 48, 60, 255], .82, .24)
GRAPHITE_EDGE    = pbr('EV_R10DP_EdgeGraphite',    [62, 76, 91, 255], .76, .18)
GRAPHITE_DARK    = pbr('EV_R10DP_DeepGraphite',    [10, 15, 21, 255], .90, .34)
VOID_MAT         = pbr('EV_R10DP_CognitionVoid',   [1, 2, 5, 255], .03, .98)
COOL_MAT         = pbr('EV_R10DP_CoolEnergy',      [116, 202, 255, 255], .15, .10, emissive=[0.55, .90, 1.0], double=True)
WHITE_MAT        = pbr('EV_R10DP_WhiteEnergy',     [232, 247, 255, 255], .10, .08, emissive=[1.0, 1.0, 1.0], double=True)
WARM_MAT         = pbr('EV_R10DP_WarmEnergy',      [255, 137, 58, 255], .14, .11, emissive=[1.0, .42, .08], double=True)
AMBER_MAT        = pbr('EV_R10DP_AmberEdge',       [255, 183, 93, 255], .18, .12, emissive=[.92, .31, .06], double=True)

# -----------------------------------------------------------------------------
# GEOMETRY HELPERS
# -----------------------------------------------------------------------------
def ring_wedge(r0, r1, a0, a1, ztop=0.0, depth=16.0, n=28, camber=2.0, skew=0.0):
    """Watertight annular wedge with real extrusion, face camber, and Z skew."""
    if abs((a1 - a0) - 360.0) < 1e-6 and abs(camber) < 1e-6 and abs(skew) < 1e-6:
        m = trimesh.creation.annulus(r_min=r0, r_max=r1, height=depth, sections=max(48, n))
        m.apply_translation([0, 0, ztop - depth * 0.5])
        m.fix_normals()
        return m
    ang = np.linspace(math.radians(a0), math.radians(a1), n + 1)
    verts = []
    for i, a in enumerate(ang):
        t = i / n
        arch = math.sin(math.pi * t)
        z0 = ztop + camber * arch + skew * (t - .5)
        # top inner, top outer, bottom inner, bottom outer
        for r, z in ((r0, z0), (r1, z0 + camber * .26), (r0, z0 - depth), (r1, z0 - depth)):
            verts.append([r * math.cos(a), r * math.sin(a), z])
    faces = []
    for i in range(n):
        j = i + 1
        it, ot, ib, ob = 4*i, 4*i+1, 4*i+2, 4*i+3
        jt, jo, jb, job = 4*j, 4*j+1, 4*j+2, 4*j+3
        faces += [(it, ot, jo), (it, jo, jt)]
        faces += [(ib, jb, job), (ib, job, ob)]
        faces += [(it, jt, jb), (it, jb, ib)]
        faces += [(ot, ob, job), (ot, job, jo)]
    faces += [(0,2,3),(0,3,1)]
    k = 4*n
    faces += [(k,k+1,k+3),(k,k+3,k+2)]
    m = trimesh.Trimesh(vertices=np.array(verts,float), faces=np.array(faces,int), process=True)
    m.fix_normals()
    return m

def layered_wedge(name, r0, r1, a0, a1, z, depth, camber=3.0, skew=0.0, n=30):
    """Three-level hard-surface wedge: body + inset top + edge land."""
    body = ring_wedge(r0, r1, a0, a1, z, depth, n=n, camber=camber, skew=skew)
    inset = ring_wedge(r0+3.2, r1-3.4, a0+1.0, a1-1.2, z+3.0, max(4.0, depth*.22), n=max(16,n-6), camber=camber*.55, skew=skew*.45)
    edge = ring_wedge(r1-4.2, r1-1.0, a0+2.0, a1-2.0, z+5.0, max(3.2, depth*.15), n=max(14,n-8), camber=camber*.35, skew=skew*.25)
    return [
        (name+'_body', body, GRAPHITE_PRIMARY),
        (name+'_inset', inset, GRAPHITE_MID),
        (name+'_edge', edge, GRAPHITE_EDGE),
    ]

def tube_arc(radius, tube, a0, a1, z=0.0, n_arc=54, n_ring=12, flatten=.82):
    angles = np.linspace(math.radians(a0), math.radians(a1), n_arc+1)
    phis = np.linspace(0, 2*math.pi, n_ring, endpoint=False)
    v=[]
    for a in angles:
        ca, sa = math.cos(a), math.sin(a)
        for p in phis:
            rr = radius + tube * math.cos(p)
            zz = z + tube * math.sin(p) * flatten
            v.append([rr*ca, rr*sa, zz])
    f=[]
    for i in range(n_arc):
        for j in range(n_ring):
            j2=(j+1)%n_ring
            a=i*n_ring+j; b=i*n_ring+j2; c=(i+1)*n_ring+j2; d=(i+1)*n_ring+j
            f += [(a,b,c),(a,c,d)]
    # close tube ends for clean authored solids
    start_center=len(v); v.append([radius*math.cos(angles[0]), radius*math.sin(angles[0]), z])
    end_center=len(v); v.append([radius*math.cos(angles[-1]), radius*math.sin(angles[-1]), z])
    for j in range(n_ring):
        j2=(j+1)%n_ring
        f.append((start_center, j2, j))
        a=n_arc*n_ring+j; b=n_arc*n_ring+j2
        f.append((end_center, a, b))
    m=trimesh.Trimesh(vertices=np.array(v,float),faces=np.array(f,int),process=True)
    m.fix_normals()
    return m

def radial_vane(angle_deg, r0, r1, width, depth, z):
    a=math.radians(angle_deg)
    p0=np.array([r0*math.cos(a),r0*math.sin(a),z],float)
    p1=np.array([r1*math.cos(a),r1*math.sin(a),z],float)
    d=p1-p0
    length=float(np.linalg.norm(d[:2]))
    m=trimesh.creation.box(extents=[length,width,depth])
    T=trimesh.transformations.rotation_matrix(math.atan2(d[1],d[0]),[0,0,1])
    T[:3,3]=(p0+p1)/2
    m.apply_transform(T)
    return m

def bezier_tube(points, radius=2.5, n_path=50, n_ring=10):
    """Tube following cubic Bezier. Used only for curved energy crescents, never straight bars."""
    p0,p1,p2,p3=[np.array(p,float) for p in points]
    ts=np.linspace(0,1,n_path+1)
    curve=[]; tang=[]
    for t in ts:
        p=(1-t)**3*p0+3*(1-t)**2*t*p1+3*(1-t)*t*t*p2+t**3*p3
        d=3*(1-t)**2*(p1-p0)+6*(1-t)*t*(p2-p1)+3*t*t*(p3-p2)
        curve.append(p); tang.append(d/np.linalg.norm(d))
    verts=[]
    up=np.array([0,0,1.0])
    for p,t in zip(curve,tang):
        n=np.cross(t,up)
        if np.linalg.norm(n)<1e-4:
            up=np.array([0,1.0,0]); n=np.cross(t,up)
        n=n/np.linalg.norm(n)
        b=np.cross(t,n); b=b/np.linalg.norm(b)
        for phi in np.linspace(0,2*math.pi,n_ring,endpoint=False):
            verts.append(p + radius*(math.cos(phi)*n + math.sin(phi)*b))
    faces=[]
    for i in range(n_path):
        for j in range(n_ring):
            j2=(j+1)%n_ring
            a=i*n_ring+j; b=i*n_ring+j2; c=(i+1)*n_ring+j2; d=(i+1)*n_ring+j
            faces += [(a,b,c),(a,c,d)]
    start_center=len(verts); verts.append(curve[0])
    end_center=len(verts); verts.append(curve[-1])
    for j in range(n_ring):
        j2=(j+1)%n_ring
        faces.append((start_center,j2,j))
        a=n_path*n_ring+j; b=n_path*n_ring+j2
        faces.append((end_center,a,b))
    m=trimesh.Trimesh(vertices=np.array(verts,float),faces=np.array(faces,int),process=True)
    m.fix_normals()
    return m

def export_scene(filename, geos):
    sc=trimesh.Scene()
    for name,mesh,material in geos:
        mesh.visual.material=material
        sc.add_geometry(mesh, geom_name=name, node_name=name)
    sc.export(AS/filename)

# -----------------------------------------------------------------------------
# AUTHORED CORE — DEEP LAYERED CONTAINMENT
# -----------------------------------------------------------------------------
# Deliberately different Z planes. Viewed at a 3/4 angle these form a deep machine,
# not a flat HUD ring.
outer_specs = {
    'nw': (126,169,108,166,  34, 26, 5.5, 12),
    'ne': (127,171, 18, 74,  -2, 30, 4.8,-14),
    'sw': (124,167,197,250, -30, 24, 4.2,-10),
    'se': (126,172,287,339,  26, 32, 5.8, 14),
}
for key,s in outer_specs.items():
    export_scene(f'ev_core_r10dp_outer_{key}.glb', layered_wedge('outer_'+key,*s,n=32))

# Secondary split shells at different depths for visible parallax.
mid_specs = {
    'nw': (101,119,119,158,  12, 18, 3.4,  5),
    'ne': (101,119, 30, 67, -22, 19, 3.0, -6),
    'sw': (100,118,207,241, -12, 18, 2.8, -5),
    'se': (101,120,298,331,  15, 20, 3.3,  6),
}
for key,s in mid_specs.items():
    geos=layered_wedge('mid_'+key,*s,n=24)
    # darker body to keep hierarchy
    geos[0]=(geos[0][0],geos[0][1],GRAPHITE_DARK)
    export_scene(f'ev_core_r10dp_mid_{key}.glb', geos)

# Inner collar: front and rear segments alternate in Z.
inner_geos=[]
inner_segments=[
    (72,89,112,171, 40,13,2.2, 5,GRAPHITE_EDGE),
    (72,89, 18, 69,  4,13,2.2,-5,GRAPHITE_MID),
    (72,89,204,255,-18,14,2.0,-4,GRAPHITE_MID),
    (72,89,287,337, 32,14,2.4, 6,GRAPHITE_EDGE),
]
for i,(r0,r1,a0,a1,z,d,c,s,mat_) in enumerate(inner_segments):
    inner_geos.append((f'inner_{i}',ring_wedge(r0,r1,a0,a1,z,d,n=28,camber=c,skew=s),mat_))
export_scene('ev_core_r10dp_inner_collar.glb',inner_geos)

# Deep aperture tunnel: rear dark chamber + thick collar walls + inner lip.
void_geos=[]
rear=trimesh.creation.cylinder(radius=55,height=12,sections=72); rear.apply_translation([0,0,-58]); void_geos.append(('rear_void',rear,VOID_MAT))
# deep dark throat (cap toward camera remains black, thickness gives subtle parallax)
throat=trimesh.creation.cylinder(radius=54,height=64,sections=72); throat.apply_translation([0,0,-23]); void_geos.append(('void_throat',throat,VOID_MAT))
# rear collar and front lip
void_geos.append(('rear_collar',ring_wedge(56,71,0,360,-27,28,n=72,camber=0,skew=0),GRAPHITE_DARK))
void_geos.append(('front_lip',ring_wedge(57,66,0,360,46,10,n=72,camber=0,skew=0),GRAPHITE_EDGE))
export_scene('ev_core_r10dp_void_tunnel.glb',void_geos)

# Depth vanes: different Z and lengths, visually connect shell layers without clutter.
vanes=[]
for i,(a,r0,r1,w,d,z,mat_) in enumerate([
    (92, 91,158,7,16, 18,GRAPHITE_EDGE),
    (177,92,148,7,18,-18,GRAPHITE_MID),
    (270,90,153,7,16,  8,GRAPHITE_EDGE),
    (348,91,148,6,18,-10,GRAPHITE_MID),
    (61, 92,133,5,12, 42,GRAPHITE_EDGE),
    (232,91,132,5,13,-34,GRAPHITE_DARK),
]):
    vanes.append((f'vane_{i}',radial_vane(a,r0,r1,w,d,z),mat_))
export_scene('ev_core_r10dp_depth_vanes.glb',vanes)

# Energy halo layers at three depth planes.
halo_defs=[
    ('cool_front', 66.5,4.2,100,196, 50,COOL_MAT),
    ('white_front',66.5,3.5,202,263, 51,WHITE_MAT),
    ('warm_front', 66.5,4.4,286,381, 49,WARM_MAT),
    ('cool_mid',   61.5,2.8, 32, 88, 18,COOL_MAT),
    ('white_rear', 59.0,2.5,108,228,-20,WHITE_MAT),
    ('amber_rear', 60.0,2.8,268,340,-18,AMBER_MAT),
]
for name,r,t,a0,a1,z,mat_ in halo_defs:
    export_scene(f'ev_core_r10dp_halo_{name}.glb',[(name,tube_arc(r,t,a0,a1,z,n_arc=max(28,int(abs(a1-a0)/2)),n_ring=12,flatten=.78),mat_)])

# Curved energy crescents: replace the rejected straight accretion bridge.
# They stay outside the central void and arc around it in different Z planes.
stream_cool=bezier_tube([(-150,26,-8),(-118,75,8),(-42,95,42),(34,72,58)],radius=2.2,n_path=58,n_ring=10)
stream_warm=bezier_tube([(152,-24,-20),(116,-72,-2),(52,-96,34),(-18,-76,54)],radius=2.5,n_path=58,n_ring=10)
export_scene('ev_core_r10dp_energy_streams.glb',[
    ('cool_stream',stream_cool,COOL_MAT),('warm_stream',stream_warm,WARM_MAT)
])

# Sparse authored cognition nodes, positioned at distinct depths.
node_points=[(-28,28,62),(27,19,48),(-20,-31,30),(31,-26,10),(5,39,-5),(-7,-8,70)]
node_geos=[]
for i,p in enumerate(node_points):
    m=trimesh.creation.icosphere(subdivisions=1,radius=2.4 if i in (0,5) else 1.5)
    m.apply_scale([1.0,1.0,1.35]); m.apply_translation(p)
    node_geos.append((f'node_{i}',m,WHITE_MAT if i in (0,5) else COOL_MAT))
export_scene('ev_core_r10dp_nodes.glb',node_geos)

# -----------------------------------------------------------------------------
# MANIFEST
# -----------------------------------------------------------------------------
manifest={}
for p in sorted(AS.glob('*.glb')):
    data=p.read_bytes()
    scene=trimesh.load(p,force='scene')
    manifest[p.name]={
        'bytes':len(data),
        'sha256':hashlib.sha256(data).hexdigest(),
        'bounds':np.round(scene.bounds,2).tolist() if scene.bounds is not None else None,
        'geometry_count':len(scene.geometry),
    }
(OUT/'MANIFEST_R10DP.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
