import numpy as np
import trimesh
from pathlib import Path
import math, json, hashlib

OUT = Path('/mnt/data/ev_r10_singularity_package')
AS = OUT/'assets'
AS.mkdir(parents=True, exist_ok=True)

# ---------------- materials ----------------
def mat(name, rgba, metallic=0.75, roughness=0.28, emissive=None, double=False):
    return trimesh.visual.material.PBRMaterial(
        name=name,
        baseColorFactor=np.array(rgba, dtype=np.uint8),
        metallicFactor=float(metallic),
        roughnessFactor=float(roughness),
        emissiveFactor=None if emissive is None else np.array(emissive, dtype=float),
        doubleSided=double,
    )

GRAPHITE_A = mat('EV_R10S_CommandGraphite', [28,34,42,255], .84, .24)
GRAPHITE_B = mat('EV_R10S_DeepGraphite', [15,20,27,255], .88, .30)
GRAPHITE_C = mat('EV_R10S_EdgeGraphite', [42,48,57,255], .78, .22)
GRAPHITE_D = mat('EV_R10S_MatteVoidFrame', [10,13,18,255], .72, .42)
VOID_MAT = mat('EV_R10S_CognitionVoid', [1,2,4,255], .05, .96)
COOL_MAT = mat('EV_R10S_CoolHalo', [145,205,255,255], .20, .12, emissive=[0.55,0.82,1.0], double=True)
WHITE_MAT = mat('EV_R10S_WhiteHalo', [228,244,255,255], .12, .10, emissive=[0.95,1.0,1.0], double=True)
WARM_MAT = mat('EV_R10S_WarmHalo', [255,145,66,255], .18, .14, emissive=[1.0,0.38,0.08], double=True)
HOT_MAT = mat('EV_R10S_HotRail', [255,194,120,255], .12, .10, emissive=[1.0,0.46,0.12], double=True)
COOL_RAIL = mat('EV_R10S_CoolRail', [165,218,255,255], .10, .10, emissive=[0.45,0.78,1.0], double=True)

# ---------------- geometry helpers ----------------
def ring_wedge(r0, r1, a0, a1, z0=0.0, thickness=7.0, n=20, camber=2.0, skew=0.0):
    """Watertight annular wedge with slight camber and z skew."""
    ang = np.linspace(math.radians(a0), math.radians(a1), n+1)
    verts=[]
    # top inner, top outer, bottom inner, bottom outer per sample
    for i,a in enumerate(ang):
        t=i/n
        arch = math.sin(math.pi*t)
        ztop = z0 + camber*arch + skew*(t-0.5)
        for r,z in [(r0,ztop),(r1,ztop+camber*0.30),(r0,ztop-thickness),(r1,ztop-thickness)]:
            verts.append([r*math.cos(a), r*math.sin(a), z])
    verts=np.array(verts,float)
    faces=[]
    # indices sample i: inner top=4i, outer top=4i+1, inner bot=4i+2, outer bot=4i+3
    for i in range(n):
        j=i+1
        it,ot,ib,ob=4*i,4*i+1,4*i+2,4*i+3
        jt,jot,jb,job=4*j,4*j+1,4*j+2,4*j+3
        # top
        faces += [(it,ot,jot),(it,jot,jt)]
        # bottom
        faces += [(ib,jb,job),(ib,job,ob)]
        # inner wall
        faces += [(it,jt,jb),(it,jb,ib)]
        # outer wall
        faces += [(ot,ob,job),(ot,job,jot)]
    # end caps
    faces += [(0,2,3),(0,3,1)]
    k=4*n
    faces += [(k,k+1,k+3),(k,k+3,k+2)]
    m=trimesh.Trimesh(vertices=verts, faces=np.array(faces), process=True)
    m.fix_normals()
    return m

def tube_arc(radius, tube, a0, a1, z=0.0, n_arc=72, n_ring=10, flatten=1.0):
    """Curved emissive tube, ring cross-section slightly flattened in Z."""
    angles=np.linspace(math.radians(a0),math.radians(a1),n_arc+1)
    phis=np.linspace(0,2*math.pi,n_ring,endpoint=False)
    v=[]
    for a in angles:
        ca,sa=math.cos(a),math.sin(a)
        # local radial direction in xy, binormal z
        for p in phis:
            rr=radius + tube*math.cos(p)
            zz=z + tube*math.sin(p)*flatten
            v.append([rr*ca, rr*sa, zz])
    f=[]
    for i in range(n_arc):
        for j in range(n_ring):
            j2=(j+1)%n_ring
            a=i*n_ring+j; b=i*n_ring+j2; c=(i+1)*n_ring+j2; d=(i+1)*n_ring+j
            f += [(a,b,c),(a,c,d)]
    # caps fan approximation
    m=trimesh.Trimesh(vertices=np.array(v,float),faces=np.array(f),process=True)
    m.fix_normals()
    return m

def box_between(p0,p1,width,depth,material):
    p0=np.array(p0,float); p1=np.array(p1,float)
    d=p1-p0; length=float(np.linalg.norm(d[:2]))
    angle=math.atan2(d[1],d[0])
    mesh=trimesh.creation.box(extents=[length,width,depth])
    T=trimesh.transformations.rotation_matrix(angle,[0,0,1])
    T[:3,3]=[(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,(p0[2]+p1[2])/2]
    mesh.apply_transform(T); mesh.visual.material=material
    return mesh

def export_scene(filename, geometries):
    sc=trimesh.Scene()
    for name,mesh,material in geometries:
        mesh.visual.material=material
        sc.add_geometry(mesh, geom_name=name, node_name=name)
    sc.export(AS/filename)

# ---------------- authored structural groups ----------------
# Four groups with intentionally uneven spans and layered radii. Breaks prevent a perfect sci-fi HUD ring.
groups={
 'nw': [
    (126,156,108,166,-10,10,5.2,6),
    (110,122,118,156,  8, 7,3.0,-4),
    (160,173,132,159,-22, 8,2.0,8),
 ],
 'ne': [
    (128,158, 18, 76,  4,11,5.8,-7),
    (111,123, 31, 69, 18, 7,2.8,5),
    (163,176, 35, 65,-18, 8,2.4,-5),
 ],
 'sw': [
    (125,157,196,249,  0,11,5.0,-6),
    (109,122,205,239, 16, 7,2.6,4),
    (161,174,205,235,-21, 8,2.0,7),
 ],
 'se': [
    (126,159,286,340,-4,10,5.4,6),
    (110,123,295,330,17, 7,2.7,-4),
    (163,176,300,330,-19, 8,2.1,-6),
 ],
}
for key, defs in groups.items():
    geos=[]
    for idx,(r0,r1,a0,a1,z,t,c,s) in enumerate(defs):
        m=ring_wedge(r0,r1,a0,a1,z,t,n=18 if idx==0 else 12,camber=c,skew=s)
        geos.append((f'R10S_{key}_{idx}',m,[GRAPHITE_A,GRAPHITE_C,GRAPHITE_B][idx]))
    export_scene(f'ev_core_r10s_{key}.glb',geos)

# Inner segmented frame clusters: engineered collar, not complete circle.
inner_defs={
 'inner_l':[(93,106,132,184,10,6,2.6,3),(82,90,145,176,27,5,1.8,-2)],
 'inner_r':[(93,106,-3,49,12,6,2.6,-3),(82,90,8,40,29,5,1.8,2)],
 'inner_b':[(93,106,222,269,6,6,2.4,4),(82,90,232,262,25,5,1.6,-2)],
}
for key,defs in inner_defs.items():
    geos=[]
    for i,d in enumerate(defs):
        m=ring_wedge(*d,n=14,camber=d[6],skew=d[7]) if False else None
    # manual because star args with keywords mismatch
    for i,(r0,r1,a0,a1,z,t,c,s) in enumerate(defs):
        m=ring_wedge(r0,r1,a0,a1,z,t,n=14,camber=c,skew=s)
        geos.append((f'R10S_{key}_{i}',m,GRAPHITE_C if i==0 else GRAPHITE_B))
    export_scene(f'ev_core_r10s_{key}.glb',geos)

# Halo: four emissive arcs with purposeful gaps, cool dominant / warm lower-right.
halo_specs=[
 ('halo_cool_a',68,4.6,100,208,24,COOL_MAT),
 ('halo_white',68,4.0,211,282,25,WHITE_MAT),
 ('halo_warm',68,4.8,285,407,24,WARM_MAT),
 ('halo_cool_b',68,3.5,50,94,23,COOL_MAT),
]
for name,r,t,a0,a1,z,ma in halo_specs:
    m=tube_arc(r,t,a0,a1,z,n_arc=max(24,int(abs(a1-a0)/2.2)),n_ring=10,flatten=.82)
    export_scene(f'ev_core_r10s_{name}.glb',[(name,m,ma)])

# Dark aperture: flattened sphere plus rear collar disk.
void=trimesh.creation.icosphere(subdivisions=3,radius=57)
void.apply_scale([1.0,1.0,0.42]); void.apply_translation([0,0,9]); void.visual.material=VOID_MAT
rear=trimesh.creation.cylinder(radius=78,height=5,sections=72)
rear.apply_translation([0,0,-31]); rear.visual.material=GRAPHITE_D
export_scene('ev_core_r10s_void.glb',[('CognitionVoid',void,VOID_MAT),('RearCollar',rear,GRAPHITE_D)])

# Diagonal accretion / computation bridge.
angle=13.5
length=430
ca,sa=math.cos(math.radians(angle)),math.sin(math.radians(angle))
p0=(-length/2*ca,-length/2*sa,34); p1=(length/2*ca,length/2*sa,34)
rail_base=box_between(p0,p1,17,7,GRAPHITE_B)
rail_top=box_between((-205*ca,-205*sa,43),(218*ca,218*sa,43),5.2,2.6,HOT_MAT)
rail_cool=box_between((-202*ca,-202*sa-5,39),(205*ca,205*sa-5,39),2.0,1.8,COOL_RAIL)
# Secondary micro-rails staggered for an engineered accretion plane.
rail_s1=box_between((-180*ca,-180*sa+12,28),(160*ca,160*sa+12,28),3.0,2.4,GRAPHITE_C)
rail_s2=box_between((-130*ca,-130*sa-15,52),(190*ca,190*sa-15,52),2.2,1.8,GRAPHITE_A)
export_scene('ev_core_r10s_bridge.glb',[
    ('BridgeBase',rail_base,GRAPHITE_B),('BridgeHot',rail_top,HOT_MAT),('BridgeCool',rail_cool,COOL_RAIL),
    ('BridgeSubA',rail_s1,GRAPHITE_C),('BridgeSubB',rail_s2,GRAPHITE_A)
])

# Radial containment vanes around gaps, hard-edged boxes tangent-ish.
vanes=[]
for idx,(ang,r,l,w,z,tilt) in enumerate([
    (91,139,45,8,12,0),(178,139,35,8,-3,0),(270,145,38,8,9,0),(350,142,34,7,4,0),
    (76,120,28,6,28,0),(235,120,26,6,24,0)
]):
    a=math.radians(ang)
    # radial box from r-l/2 to r+l/2
    q0=((r-l/2)*math.cos(a),(r-l/2)*math.sin(a),z)
    q1=((r+l/2)*math.cos(a),(r+l/2)*math.sin(a),z)
    m=box_between(q0,q1,w,5,GRAPHITE_C)
    vanes.append((f'Vane{idx}',m,GRAPHITE_C if idx%2==0 else GRAPHITE_A))
export_scene('ev_core_r10s_vanes.glb',vanes)

# cognition nodes as authored faceted shards around the fissure, sparse.
points=[(-35,35,45),(30,26,41),(-28,-34,38),(38,-30,44),(5,49,32)]
sc=trimesh.Scene()
for i,p in enumerate(points):
    m=trimesh.creation.icosphere(subdivisions=1,radius=2.6 if i==0 else 1.7)
    m.apply_scale([1,1,1.4]); m.apply_translation(p)
    m.visual.material=WHITE_MAT if i==0 else COOL_MAT
    sc.add_geometry(m,geom_name=f'Node{i}',node_name=f'Node{i}')
sc.export(AS/'ev_core_r10s_nodes.glb')

# Validate and manifest
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
(OUT/'MANIFEST_R10S.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
