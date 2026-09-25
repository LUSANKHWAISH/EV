import numpy as np
import trimesh
from shapely.geometry import Polygon, Point
from scipy.spatial import Delaunay
from pathlib import Path
import math, json, hashlib, zipfile

OUT = Path('/mnt/data/ev_r10_package')
AS = OUT/'assets'
AS.mkdir(parents=True, exist_ok=True)

# --------------------------- geometry helpers ---------------------------

def pbr(name, rgba, metallic=0.72, roughness=0.30):
    return trimesh.visual.material.PBRMaterial(
        name=name,
        baseColorFactor=np.array(rgba, dtype=np.uint8),
        metallicFactor=float(metallic),
        roughnessFactor=float(roughness),
    )

MATS = {
    'A': pbr('R10_CommandGraphite', [34, 39, 47, 255], .74, .28),
    'B': pbr('R10_ExecutionGraphite', [25, 30, 38, 255], .78, .31),
    'C': pbr('R10_KeelGraphite', [42, 46, 54, 255], .70, .34),
    'D': pbr('R10_RearGraphite', [20, 25, 32, 255], .76, .36),
    'E': pbr('R10_InnerGraphite', [48, 52, 60, 255], .68, .27),
    'F': pbr('R10_AnchorGraphite', [29, 34, 42, 255], .75, .33),
    'shard': pbr('R10_CognitionShard', [55, 60, 68, 255], .82, .22),
    'ridge': pbr('R10_Ridge', [58, 63, 72, 255], .84, .24),
}

def dist_point_segment(px, py, ax, ay, bx, by):
    vx, vy = bx-ax, by-ay
    wx, wy = px-ax, py-ay
    c1 = vx*wx + vy*wy
    if c1 <= 0: return math.hypot(px-ax, py-ay)
    c2 = vx*vx + vy*vy
    if c2 <= c1: return math.hypot(px-bx, py-by)
    t = c1/c2
    qx, qy = ax+t*vx, ay+t*vy
    return math.hypot(px-qx, py-qy)

def make_plate(name, outline, z_base, thickness=7.0, ridge_line=None, ridge_amp=10.0, plane=(0.0,0.0), material=None, interior_grid=18):
    outline = np.asarray(outline, dtype=float)
    poly = Polygon(outline)
    if not poly.is_valid:
        poly = poly.buffer(0)
    minx,miny,maxx,maxy = poly.bounds
    pts = [tuple(p) for p in outline]
    # add deterministic interior points on grid to create faceted surfaces
    nx = max(3, int((maxx-minx)/interior_grid)+1)
    ny = max(3, int((maxy-miny)/interior_grid)+1)
    for x in np.linspace(minx+interior_grid*.55, maxx-interior_grid*.55, nx):
        for y in np.linspace(miny+interior_grid*.55, maxy-interior_grid*.55, ny):
            if poly.contains(Point(float(x), float(y))):
                pts.append((float(x), float(y)))
    pts = np.array(pts, dtype=float)
    tri = Delaunay(pts)
    faces2=[]
    for f in tri.simplices:
        c=pts[f].mean(axis=0)
        if poly.buffer(1e-6).covers(Point(float(c[0]),float(c[1]))):
            faces2.append(tuple(map(int,f)))
    # top z function
    cx,cy = outline.mean(axis=0)
    sx=max(1,maxx-minx); sy=max(1,maxy-miny)
    z=[]
    for x,y in pts:
        zz=z_base + plane[0]*(x-cx)/sx + plane[1]*(y-cy)/sy
        if ridge_line:
            d=dist_point_segment(x,y,*ridge_line[0],*ridge_line[1])
            # faceted fold ridge with finite influence
            influence=max(0.0, 1.0-d/42.0)
            zz += ridge_amp*influence
        # Controlled perimeter bevel: boundary sits slightly lower than the
        # inner field so hard-surface highlights catch the shell edge.
        edge_dist = poly.boundary.distance(Point(float(x), float(y)))
        edge_factor = min(1.0, edge_dist / 7.0)
        zz += -2.8 * (1.0 - edge_factor)

        # Subtle macro fold; this is intentional surface break, not noise.
        zz += 1.4*((x-cx)/sx)*((y-cy)/sy)
        z.append(zz)
    z=np.array(z)
    top=np.column_stack([pts,z])
    bottom=np.column_stack([pts,z-thickness])
    n=len(pts)
    vertices=np.vstack([top,bottom])
    faces=[]
    # top and bottom
    for a,b,c in faces2:
        # ensure top outward +z
        va,vb,vc=top[[a,b,c]]
        if np.dot(np.cross(vb-va,vc-va), [0,0,1]) < 0:
            b,c=c,b
        faces.append((a,b,c))
        faces.append((c+n,b+n,a+n))
    # side walls using original outline indexes 0..len(outline)-1
    m=len(outline)
    for i in range(m):
        j=(i+1)%m
        faces.append((i,j,j+n))
        faces.append((i,j+n,i+n))
    mesh=trimesh.Trimesh(vertices=vertices, faces=np.array(faces), process=True)
    mesh.remove_unreferenced_vertices()
    mesh.fix_normals()
    if not mesh.is_watertight:
        try:
            trimesh.repair.fill_holes(mesh)
            mesh.fix_normals()
        except Exception:
            pass
    # Keep shared top-surface vertices so the authored camber shades smoothly;
    # the explicit ridge meshes below provide the deliberate hard creases.
    mesh.visual.material = material or MATS['A']
    return mesh

def make_ridge_strip(name, pts, width=5.0, z=0.0, thickness=1.8, material=None):
    # R10 ridges are deliberate hard-surface ribs. Each current design uses
    # a single straight segment, so build a watertight oriented box instead
    # of a thin open strip.
    pts=np.asarray(pts,float)
    p0,p1=pts[0],pts[-1]
    d=p1-p0
    length=float(np.linalg.norm(d))
    angle=math.atan2(d[1],d[0])
    mesh=trimesh.creation.box(extents=[length,width,thickness])
    # box local X follows the segment
    T=trimesh.transformations.rotation_matrix(angle,[0,0,1])
    T[:3,3]=[(p0[0]+p1[0])/2,(p0[1]+p1[1])/2,z-thickness/2]
    mesh.apply_transform(T)
    mesh.visual.material=material or MATS['ridge']
    return mesh

# ----------------------------- R10 design ------------------------------
# Intentionally angular, interrupted, and asymmetric. Central cognition void
# roughly occupies x=-28..38, y=-35..42.
plates = {
'A': dict(outline=[(-160,34),(-154,82),(-118,117),(-68,121),(-35,98),(-31,66),(-55,42),(-91,31),(-126,22)], z=-5, t=11, ridge=((-145,78),(-49,84)), amp=14, plane=(8,-2)),
'B': dict(outline=[(37,95),(76,121),(123,112),(158,76),(154,34),(130,14),(98,22),(72,44),(52,69)], z=6, t=11, ridge=((52,91),(140,57)), amp=14, plane=(-7,4)),
'C': dict(outline=[(-151,32),(-120,25),(-89,14),(-62,-10),(-50,-42),(-31,-68),(-43,-102),(-82,-116),(-122,-99),(-148,-62),(-143,-18)], z=2, t=11, ridge=((-127,14),(-54,-81)), amp=13, plane=(5,7)),
'D': dict(outline=[(51,26),(83,33),(121,20),(151,-10),(160,-48),(140,-86),(106,-113),(64,-109),(42,-82),(48,-51),(70,-26),(57,-2)], z=12, t=11, ridge=((68,18),(135,-77)), amp=13, plane=(-4,7)),
'E': dict(outline=[(-129,76),(-105,100),(-69,102),(-48,84),(-55,65),(-86,57),(-113,61)], z=20, t=6, ridge=((-117,82),(-59,82)), amp=6, plane=(3,-1)),
'F': dict(outline=[(78,-24),(111,-18),(136,-39),(132,-68),(104,-89),(76,-82),(65,-59)], z=31, t=6, ridge=((82,-32),(124,-68)), amp=6, plane=(-2,3)),
}


for key,kw in plates.items():
    mesh=make_plate('R10_'+key, kw['outline'], kw['z'], kw['t'], kw['ridge'], kw['amp'], kw['plane'], MATS[key])
    # add an integrated hard-surface ridge only to A/B/C/E, not decorative everywhere
    scene=trimesh.Scene()
    scene.add_geometry(mesh, geom_name=f'R10_{key}_Main', node_name=f'R10_{key}_Main')
    if key in ['A','B','C','E']:
        (p0,p1)=kw['ridge']
        # shorten ridge to stay within shell and float slightly over face
        x0,y0=p0; x1,y1=p1
        q0=(x0*.88+x1*.12,y0*.88+y1*.12); q1=(x0*.12+x1*.88,y0*.12+y1*.88)
        # estimate z above base + ridge amp
        rz=kw['z']+kw['amp']+1.0
        ridge=make_ridge_strip('ridge',[q0,q1],width=4.2 if key!='E' else 3.4,z=rz,thickness=1.7,material=MATS['ridge'])
        scene.add_geometry(ridge, geom_name=f'R10_{key}_Ridge', node_name=f'R10_{key}_Ridge')
    scene.export(AS/f'ev_core_r10_{key.lower()}.glb')

# Faceted cognition shard: stretched octahedron with hard asymmetry
verts=np.array([
    [0, 18, 9], [11, 2, 7], [4,-17,5], [-9,-10,6], [-12,7,8],
    [1,3,24], [2,1,-6]
],float)
faces=np.array([
    [0,1,5],[1,2,5],[2,3,5],[3,4,5],[4,0,5],
    [1,0,6],[2,1,6],[3,2,6],[4,3,6],[0,4,6]
])
sh=trimesh.Trimesh(vertices=verts,faces=faces,process=True)
sh.fix_normals()
sh.visual.material=MATS['shard']
sc=trimesh.Scene(); sc.add_geometry(sh, geom_name='R10_CognitionShard', node_name='R10_CognitionShard'); sc.export(AS/'ev_core_r10_shard.glb')

print('generated', len(list(AS.glob('*.glb'))), 'assets')
for p in sorted(AS.glob('*.glb')):
    s=trimesh.load(p,force='scene')
    b=s.bounds
    print(p.name,p.stat().st_size,'bounds',np.round(b,1).tolist())
