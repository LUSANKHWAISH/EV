"""Actual rendered projection and local-flow checks; no backend or OS input."""
import json
from pathlib import Path
import numpy as np
from PySide6.QtGui import QImage
from PySide6.QtCore import QPointF,QTimer
from validate_preview import LabValidation

OUT=Path(__file__).resolve().parent/'evidence/flow_launch'


class ProjectionValidation(LabValidation):
    def start(self):
        self.window.setProperty('expanded',True)
        self.original_state=self.model.visualState
        self.model.replayLaunch()
        self.steps=[(220,lambda:self.snapshot('launch_seed')),
                    (620,lambda:self.snapshot('launch_arcs')),
                    (750,lambda:self.snapshot('launch_weave')),
                    (1900,self.settled),(420,self.flow_second),
                    (50,self.pause_start),(450,self.pause_ready),(650,self.pause_compare),
                    (50,self.resume),(3700,self.after_resume),
                    (400,self.interrupt),(150,self.after_interrupt),(100,self.finish)]
        self.next()
    def snapshot(self,name):
        image=self.window.grabWindow()
        image.save(str(OUT/(name+'.png')))
        p=self.scene.mapToScene(QPointF(0,0))
        crop=image.copy(round(p.x()),round(p.y()),round(self.scene.width()),round(self.scene.height())).convertToFormat(QImage.Format.Format_RGBA8888)
        a=np.frombuffer(bytes(crop.constBits()),np.uint8).reshape(crop.height(),crop.bytesPerLine()//4,4)[:,:crop.width()]
        row={'progress':self.model.launchProgress}
        setattr(self,name,row)
        # Bounds use only the transparent scene, excluding overlaid navigation
        # and response labels that also have gold pixels in the window capture.
        def alpha_extent(pixels):
            mask=pixels[:,:,3]>16
            ys,xs=np.nonzero(mask)
            row.update(extent=[int(xs.max()-xs.min()),int(ys.max()-ys.min())] if len(xs) else [0,0],bright_pixels=int(mask.sum()))
        self.capture('flow_launch/'+name+'_alpha.png',alpha_extent)
        if name=='launch_settled':self.flow_before=a.copy()
        if name=='flow_after':self.flow_after_pixels=a.copy()
        return a
    def settled(self):
        self.snapshot('launch_settled')
        self.check('launch_seed_is_visible',self.launch_seed['bright_pixels']>5,self.launch_seed)
        self.check('launch_progresses_and_settles',self.launch_seed['progress']<self.launch_arcs['progress']<self.launch_weave['progress']<1 and self.model.launchProgress==1)
        self.check('startup_does_not_change_task_state',self.model.visualState==self.original_state and self.model.requests==[])
        self.model.setQuality(True);self.model.setQuality(False)
        self.check('quality_changes_do_not_replay',self.model.launchProgress==1)
    def flow_second(self):
        self.check('projection_grows_from_compact_source',self.launch_settled['extent'][0]>self.launch_arcs['extent'][0]*1.4,{'arcs':self.launch_arcs,'settled':self.launch_settled})
        self.snapshot('flow_after')
        delta=np.abs(self.flow_after_pixels[:,:,:3].astype(float)-self.flow_before[:,:,:3])
        self.check('idle_emission_changes_between_frames',float(delta.mean())>.2,float(delta.mean()))
    def pause_start(self):
        self.model.replayLaunch()
    def pause_ready(self):
        self.model.setAnimation(False)
        self.paused_progress=self.model.launchProgress
        self.capture('flow_launch/projection_paused_a.png',lambda a:setattr(self,'paused_pixels',a.copy()))
    def pause_compare(self):
        self.check('pause_holds_partial_projection',0<self.paused_progress<1 and self.model.launchProgress==self.paused_progress)
        def compare(a):
            self.check('paused_projection_pixels_identical',np.array_equal(a,self.paused_pixels))
        self.capture('flow_launch/projection_paused_b.png',compare)
    def resume(self):self.model.setAnimation(True)
    def after_resume(self):
        self.check('resuming_finishes_projection',self.model.launchProgress==1)
        self.window.setProperty('drawer','settings')
        QTimer.singleShot(120,lambda:self.click('replayLaunch'))
    def interrupt(self):
        self.check('settings_replay_starts_projection',self.model.launchProgress<.3 and self.window.property('drawer')=='',{'progress':self.model.launchProgress,'drawer':self.window.property('drawer')})
        self.click('coreInteraction')
    def after_interrupt(self):
        self.check('core_interaction_skips_projection',self.model.launchProgress==1)
        self.check('command_input_remains_enabled',self.item('commandInput').isEnabled())
    def finish(self):
        passed=all(c['passed'] for c in self.checks)
        (OUT/'projection_validation.json').write_text(json.dumps({'passed':passed,'checks':self.checks},indent=2))
        self.app.exit(0 if passed else 1)
