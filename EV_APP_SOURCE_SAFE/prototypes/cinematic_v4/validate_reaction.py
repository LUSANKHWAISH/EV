"""Rendered checks for independent internal motion inside a stable volume."""
import hashlib
import json
import time
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject,QTimer
from PySide6.QtQuick3D import QQuick3DGeometry
from validate_preview import LabValidation

OUT=Path(__file__).resolve().parent/'evidence/reaction_motion'


class ReactionValidation(LabValidation):
    def next(self):
        if self.pending:
            if time.monotonic()-self.started>90:
                self.check('readbacks_complete',False,'Timed out');self.finish();return
            self.window.grabWindow();QTimer.singleShot(50,self.next)
        else:super().next()
    def capture(self,name,callback=None):
        self.pending+=1
        def ready(a):
            try:
                if callback:callback(a)
            except Exception as exc:self.check(name,False,str(exc))
            finally:self.pending-=1
        super().capture('reaction_motion/'+name,ready)
    def sample(self,name):
        self.pending+=1
        def grab():
            self.capture(name+'.png',lambda a:self.samples.__setitem__(name,a.copy()))
            self.pending-=1
        QTimer.singleShot(220,grab)
    def node(self,name):
        obj=self.window.findChild(QObject,name)
        if obj is None:raise RuntimeError('Missing 3D node '+name)
        return obj
    def transforms(self):
        result={}
        for name in ['coreAssembly','orbitalArc0','orbitalArc1','orbitalArc2','innerHub','innerCounterLoop']:
            obj=self.node(name);row={}
            for prop in ['scale','position','eulerRotation']:
                v=obj.property(prop);row[prop]=[v.x(),v.y(),v.z()]
            result[name]=row
        return result
    def mesh_hash(self):
        h=hashlib.sha256()
        for g in self.window.findChildren(QQuick3DGeometry):
            h.update(bytes(g.vertexData()));h.update(bytes(g.indexData()))
        return h.hexdigest()
    def start(self):
        self.started=time.monotonic();self.pending=0;self.samples={};self.poses={}
        self.model.finishLaunch();self.model.setAnimation(False)
        self.fixed_time=self.model.motionTime
        self.window.setProperty('expanded',True)
        self.scene.setProperty('showNodes',False)
        self.scene.setProperty('hoverX',0.);self.scene.setProperty('hoverY',0.)
        self.scene.setProperty('reactionOverride',0.)
        self.steps=[(500,lambda:self.pose(0)),(500,lambda:self.pose(6)),(500,lambda:self.pose(12)),(400,self.motion_checks),
                    (200,self.react),(500,self.reaction_checks),(200,self.lighter),(500,self.lighter_checks),
                    (200,self.resume),(800,self.pause),(350,lambda:self.sample('paused_a')),
                    (650,lambda:self.sample('paused_b')),(300,self.pause_check)]
        for t,yaw,pitch in [(0,0,18),(6,90,-18),(12,180,18),(18,270,-18)]:
            self.steps.append((300,lambda t=t,yaw=yaw,pitch=pitch:self.extreme(t,yaw,pitch)))
        self.steps += [(400,self.bounds),(100,self.finish)]
        self.next()
    def pose(self,t):
        self.scene.setProperty('orbitTimeOverride',float(t))
        self.poses[t]=self.transforms()
        if t==0:self.original_mesh_hash=self.mesh_hash()
        self.sample('orbit_'+str(t))
    def motion_checks(self):
        original=self.poses[0]
        self.check('assembly_does_not_swell_or_tilt_with_internal_orbits',all(p['coreAssembly']==original['coreAssembly'] for p in self.poses.values()))
        self.check('all_orbit_radii_and_layer_scales_stay_fixed',all(row['scale']==original[n]['scale'] and row['position']==original[n]['position'] for p in self.poses.values() for n,row in p.items()))
        self.check('mesh_vertex_and_index_buffers_unchanged',self.mesh_hash()==self.original_mesh_hash)
        deltas=[np.array(self.poses[6]['orbitalArc'+str(i)]['eulerRotation'])-original['orbitalArc'+str(i)]['eulerRotation'] for i in range(3)]
        self.check('three_arcs_move_independently',all(np.linalg.norm(d)>10 for d in deltas) and all(np.linalg.norm(deltas[i]-deltas[j])>20 for i,j in [(0,1),(1,2),(0,2)]),[d.tolist() for d in deltas])
        self.check('inner_loops_rotate_in_opposite_local_directions',self.poses[6]['innerHub']['eulerRotation'][2]<original['innerHub']['eulerRotation'][2] and self.poses[6]['innerCounterLoop']['eulerRotation'][2]>original['innerCounterLoop']['eulerRotation'][2])
        a=self.samples['orbit_0'].astype(float)
        changes={t:float(np.abs(self.samples['orbit_'+str(t)]-a).mean()) for t in [6,12]}
        self.check('internal_motion_visible_with_camera_and_emission_frozen',min(changes.values())>.5 and self.model.motionTime==self.fixed_time,changes)
        self.before_reaction=self.transforms()
    def react(self):
        self.scene.setProperty('reactionOverride',1.)
        self.sample('reaction_active')
    def reaction_checks(self):
        before=self.before_reaction;after=self.transforms()
        self.check('reaction_keeps_assembly_and_layer_sizes_fixed',all(after[n]['scale']==row['scale'] and after[n]['position']==row['position'] for n,row in before.items()) and after['coreAssembly']==before['coreAssembly'])
        self.check('reaction_adjusts_internal_arc_alignment',after['orbitalArc0']['eulerRotation']!=before['orbitalArc0']['eulerRotation'])
        delta=float(np.abs(self.samples['reaction_active'].astype(float)-self.samples['orbit_12']).mean())
        self.check('reaction_is_visible_at_fixed_motion_time',delta>.2 and self.model.motionTime==self.fixed_time,delta)
        self.full_indices=sum(g.indexData().size()//4 for g in self.window.findChildren(QQuick3DGeometry))
    def lighter(self):
        self.model.setQuality(True);self.sample('lighter_active')
    def lighter_checks(self):
        count=sum(g.indexData().size()//4 for g in self.window.findChildren(QQuick3DGeometry))
        self.check('lighter_profile_reduces_buffers_and_particles',count<self.full_indices and self.scene.property('particleCount')==1024,{'full_indices':self.full_indices,'lighter_indices':count})
        self.check('lighter_profile_keeps_rendered_core',np.count_nonzero(self.samples['lighter_active'][:,:,3]>20)>10000)
    def resume(self):
        self.scene.setProperty('orbitTimeOverride',-1.);self.scene.setProperty('reactionOverride',-1.)
        self.model.setState('THINKING');self.model.setAnimation(True)
    def pause(self):
        self.model.setAnimation(False);self.paused_time=self.model.motionTime
    def pause_check(self):
        self.check('pause_freezes_internal_motion_and_emission',np.array_equal(self.samples['paused_a'],self.samples['paused_b']) and self.model.motionTime==self.paused_time)
        self.check('visual_reactions_emit_no_command_or_authority_requests',self.model.requests==[])
        self.model.setQuality(False)
    def extreme(self,t,yaw,pitch):
        self.scene.setProperty('zoom',1.10)
        self.scene.setProperty('orbitTimeOverride',float(t))
        self.scene.setProperty('viewYaw',float(yaw));self.scene.setProperty('viewPitch',float(pitch))
        self.sample('bound_'+str(yaw))
    def bounds(self):
        for name,a in self.samples.items():
            if not name.startswith('bound_'):continue
            border=np.concatenate((a[:3].reshape(-1,4),a[-3:].reshape(-1,4),a[:,:3].reshape(-1,4),a[:,-3:].reshape(-1,4)))
            self.check(name+'_unclipped_at_max_zoom',int(border[:,3].max())==0,int(border[:,3].max()))
    def finish(self):
        passed=all(c['passed'] for c in self.checks)
        (OUT/'reaction_validation.json').write_text(json.dumps({'passed':passed,'checks':self.checks,'scope':'Actual Qt renders and live 3D transforms; geometry motion isolated from camera/emission, stable scales/radii, reaction, lighter profile, pause and bounds. Visual acceptance remains separate.'},indent=2))
        self.app.exit(0 if passed else 1)
