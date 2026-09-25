"""Meaningful in-process Qt rendering, focus, input and layout checks."""
import json
import time
from pathlib import Path
import numpy as np
from PySide6.QtCore import QObject,QTimer,QPoint,QPointF,QEvent,Qt
from PySide6.QtGui import QGuiApplication,QImage,QWheelEvent,QKeyEvent,QMouseEvent
from PySide6.QtQuick import QQuickItem
from PySide6.QtQml import QQmlExpression,QQmlEngine

ROOT=Path(__file__).resolve().parent

class LabValidation(QObject):
    def __init__(self,window,model,app):
        super().__init__(window)
        self.window=window;self.model=model;self.app=app
        self.stage=window.findChild(QQuickItem,'cinematicStage')
        self.scene=window.findChild(QQuickItem,'nucleusView')
        self.context=QQmlEngine.contextForObject(self.stage)
        self.checks=[];self.steps=[];self.grabs=[]
    def check(self,name,passed,detail=None):
        row={'check':name,'passed':bool(passed),'detail':detail};self.checks.append(row)
        print('CHECK '+json.dumps(row),flush=True)
    def item(self,name):
        item=self.window.findChild(QQuickItem,name)
        # Repeater delegates can have a visual parent without belonging to
        # that parent's QObject tree. Search the rendered item tree too.
        if item is None:
            pending=[self.window.contentItem()]
            while pending:
                candidate=pending.pop()
                if candidate.objectName()==name:
                    item=candidate;break
                pending.extend(candidate.childItems())
        if item is None:raise RuntimeError('Missing item: '+name)
        return item
    def point(self,item):
        p=item.mapToScene(QPointF(item.width()/2,item.height()/2))
        return QPoint(round(p.x()),round(p.y()))
    def mouse(self,kind,point):
        move=kind==QEvent.Type.MouseMove
        button=Qt.MouseButton.NoButton if move else Qt.MouseButton.LeftButton
        buttons=Qt.MouseButton.NoButton if kind==QEvent.Type.MouseButtonRelease else Qt.MouseButton.LeftButton
        event=QMouseEvent(kind,QPointF(point),QPointF(self.window.mapToGlobal(point)),button,buttons,Qt.KeyboardModifier.NoModifier)
        QGuiApplication.postEvent(self.window,event)
    def click_point(self,point):
        self.mouse(QEvent.Type.MouseButtonPress,point);self.mouse(QEvent.Type.MouseButtonRelease,point)
    def click(self,name):self.click_point(self.point(self.item(name)))
    def key(self,key,text=''):
        for kind in (QEvent.Type.KeyPress,QEvent.Type.KeyRelease):
            QGuiApplication.postEvent(self.window,QKeyEvent(kind,key,Qt.KeyboardModifier.NoModifier,text))
    def js(self,expression):
        obj=QQmlExpression(self.context,self.stage,expression);value=obj.evaluate()
        if obj.hasError():raise RuntimeError(obj.error().toString())
        return value[0] if isinstance(value,tuple) else value
    def capture(self,name,callback=None):
        grab=self.scene.grabToImage();self.grabs.append(grab)
        def ready():
            image=grab.image().convertToFormat(QImage.Format.Format_RGBA8888)
            image.save(str(ROOT/'evidence'/name))
            a=np.frombuffer(bytes(image.constBits()),np.uint8).reshape(image.height(),image.bytesPerLine()//4,4)[:,:image.width()]
            if callback:callback(a)
        grab.ready.connect(ready)
    def start(self):
        self.steps=[(0,self.initial),(400,self.keyboard),(400,self.keyboard_result),(300,self.after_submit),(400,self.drag),
                    (400,self.after_drag),(650,self.after_reset),(650,self.after_core),(650,self.after_module),
                    (350,self.expansion),(500,self.settings),(1400,self.quality),
                    (250,self.pause),(700,self.freeze_first),(900,self.freeze_second),
                    (350,self.small),(600,self.after_small),(350,self.long_response),(350,self.after_response),
                    (300,self.states),(350,self.orbit_start),(500,lambda:self.orbit_pose(90)),
                    (500,lambda:self.orbit_pose(180)),(500,lambda:self.orbit_pose(270)),(700,self.finish)]
        self.next()
    def next(self):
        if not self.steps:return
        delay,fn=self.steps.pop(0)
        def run():
            try:fn()
            except Exception as exc:self.check(fn.__name__,False,str(exc))
            self.next()
        QTimer.singleShot(delay,run)
    def initial(self):
        self.window.setProperty('expanded',False);self.window.setProperty('drawer','')
        self.check('existing_visual_controller',type(self.model.controller).__name__=='VisualStateController')
        self.check('music_is_planned_and_disabled',not self.item('musicButton').isEnabled())
        before=len(self.model.requests);self.model.requestPanel('approve');self.model.requestPanel('execute')
        self.check('authority_ids_rejected',len(self.model.requests)==before)
        self.full_vertices=self.scene.property('drawnVertices')
        if getattr(self,'forced_render',False):self.full_mesh_indices=self.mesh_indices()
        def alpha(a):
            border=np.concatenate((a[:8].reshape(-1,4),a[-8:].reshape(-1,4),a[:,:8].reshape(-1,4),a[:,-8:].reshape(-1,4)))
            self.check('transparent_composite_border',int(border[:,3].max())==0,int(border[:,3].max()))
            self.check('rendered_geometry_is_nonempty',int(np.count_nonzero(a[:,:,3]))>5000)
        self.capture('core_rgba.png',alpha)
    def keyboard(self):
        # Posting events lets Qt process them outside a Python callback. The
        # synchronous QTest mouse helper holds the GIL while focusing TextInput
        # and can deadlock a Python render-thread callback on this runtime.
        self.click('commandInput')
        self.before_expanded=self.window.property('expanded')
        def type_text():
            self.key(Qt.Key.Key_A,'Inspect the reference');self.key(Qt.Key.Key_Space,' ')
        QTimer.singleShot(120,type_text)
    def keyboard_result(self):
        self.check('typing_space_does_not_expand',self.window.property('expanded')==self.before_expanded)
        self.check('typing_reaches_composer','Inspect the reference' in self.item('commandInput').property('text'))
        self.key(Qt.Key.Key_Return,'\r')
    def after_submit(self):
        self.check('command_records_preview_only',len(self.model.history)==1 and self.model.history[0]['status']=='PREVIEW INPUT')
        self.check('composer_clears_after_submit',self.item('commandInput').property('text')=='')
        self.check('response_discloses_disconnected_execution','not connected' in self.model.responseDetail)
        self.before_requests=len(self.model.requests)
    def drag(self):
        p=self.point(self.scene)
        self.mouse(QEvent.Type.MouseButtonPress,p)
        for i in range(1,11):QTimer.singleShot(i*18,lambda i=i:self.mouse(QEvent.Type.MouseMove,p+QPoint(i*14,i*17)))
        QTimer.singleShot(220,lambda:self.mouse(QEvent.Type.MouseButtonRelease,p+QPoint(140,170)))
    def after_drag(self):
        self.check('drag_rotates',abs(self.scene.property('viewYaw'))>20)
        self.check('pitch_is_bounded',abs(self.scene.property('viewPitch'))<=18.001)
        self.check('drag_does_not_request_listening',len(self.model.requests)==self.before_requests)
        p=self.point(self.scene)
        self.click_point(p)
        def second_click():
            self.mouse(QEvent.Type.MouseButtonPress,p)
            self.mouse(QEvent.Type.MouseButtonDblClick,p)
            self.mouse(QEvent.Type.MouseButtonRelease,p)
        QTimer.singleShot(90,second_click)
    def hit(self,prefix):
        # Aim inside the hit region; choosing its first boundary pixel is
        # unstable when the next rendered frame moves a thin filament.
        value=self.js('JSON.stringify((function(){let hits={};for(let y=8;y<nucleus.height-8;y+=6){for(let x=8;x<nucleus.width-8;x+=6){let p=nucleus.pick(x,y);let name=p.objectHit?p.objectHit.objectName:"";if(name.indexOf('+json.dumps(prefix)+')===0){if(!hits[name])hits[name]=[];hits[name].push([x,y]);}}}for(let name in hits){let a=hits[name],cx=0,cy=0;for(let p of a){cx+=p[0];cy+=p[1]}cx/=a.length;cy/=a.length;a.sort((p,q)=>(p[0]-cx)**2+(p[1]-cy)**2-(q[0]-cx)**2-(q[1]-cy)**2);return [a[0][0]+nucleus.x,a[0][1]+nucleus.y];}return null;})())')
        p=json.loads(value)
        if not p:raise RuntimeError('No pick hit for '+prefix)
        return QPoint(round(p[0]),round(p[1]))
    def after_reset(self):
        self.check('double_click_resets_without_single_click',abs(self.scene.property('viewYaw'))<.01 and len(self.model.requests)==self.before_requests)
        self.click_point(self.hit('coreHit'))
    def after_core(self):
        self.check('core_emits_listening_request_only',self.model.requests[-1]['kind']=='listenRequested' and self.model.visualState=='IDLE')
        self.click_point(self.hit('module_'))
    def after_module(self):
        self.check('module_routes_allowed_panel',self.model.requests[-1]['kind']=='openPanelRequested')
        self.window.setProperty('drawer','')
        self.item('coreInteraction').forceActiveFocus()
        self.key(Qt.Key.Key_Space,' ')
    def expansion(self):
        self.check('core_space_expands',self.window.property('expanded'))
        p=QPointF(self.point(self.scene))
        event=QWheelEvent(p,p,QPoint(),QPoint(0,2400),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.ScrollUpdate,False)
        QGuiApplication.postEvent(self.window,event)
        def after_wheel():
            self.check('zoom_is_bounded',1<self.scene.property('zoom')<=1.1001)
            self.window.setProperty('expanded',False);self.scene.setProperty('zoom',1.)
            self.click('nav_settings')
        QTimer.singleShot(120,after_wheel)
    def settings(self):
        self.check('settings_button_opens_panel',self.window.property('drawer')=='settings')
        self.quality_click_time=time.perf_counter()
        self.click('qualityToggle')
    def quality(self):
        self.check('quality_toggle_works',self.model.qualityMode)
        self.check('quality_reduces_particles',self.scene.property('particleCount')==1024)
        self.check('quality_reduces_resolution',self.scene.property('explicitTextureWidth')<self.scene.width())
        if getattr(self,'forced_render',False):
            count=self.mesh_indices()
            self.check('quality_selects_fewer_mesh_indices',count<self.full_mesh_indices,{'full':self.full_mesh_indices,'light':count,'method':'Bound QQuick3DGeometry index buffers; RenderStats is stale without presentation.'})
        else:
            self.check('quality_reduces_geometry',self.scene.property('drawnVertices')<self.full_vertices,{'full':self.full_vertices,'light':self.scene.property('drawnVertices')})
        times=np.asarray(self.model._frame_times)
        recent=times[times>self.quality_click_time+.35]
        fps=1/np.diff(recent).mean() if len(recent)>8 else 0
        if getattr(self,'forced_render',False):
            self.checks.append({'check':'quality_paces_frames','passed':None,'skipped':True,'detail':'Explicit readback pump on remote/occluded desktop; presentation FPS is not measurable in this run.'})
        else:
            self.check('quality_paces_frames',20<=fps<=32,{'measured_fps':float(fps),'cached_renderer_fps':self.scene.property('rendererFps')})
    def mesh_indices(self):
        from PySide6.QtQuick3D import QQuick3DGeometry
        return sum(g.indexData().size()//4 for g in self.window.findChildren(QQuick3DGeometry))
    def pause(self):
        self.click('animationToggle')
        QTimer.singleShot(120,lambda:self.key(Qt.Key.Key_Escape))
        self.scene.setProperty('hoverX',0.);self.scene.setProperty('hoverY',0.)
    def freeze_first(self):
        self.check('pause_toggle_works',not self.model.animationEnabled)
        self.check('escape_closes_drawer',self.window.property('drawer')=='')
        self.frozen_clock=self.model.motionTime
        self.capture('frozen_a.png',lambda a:setattr(self,'frozen',a.copy()))
    def freeze_second(self):
        def compare(a):
            diff=np.abs(a.astype(np.int16)-self.frozen.astype(np.int16))
            self.check('pause_freezes_core_pixels',self.model.motionTime==self.frozen_clock and diff.mean()<.001 and diff.max()<=8,{'mean':float(diff.mean()),'max':int(diff.max())})
        self.capture('frozen_b.png',compare)
    def small(self):
        self.window.resize(1280,800);self.model.clearHistory()
    def after_small(self):
        response=self.item('responseSurface');composer=self.item('composerBox')
        expand=self.item('expandButton');telemetry=self.item('telemetryRail')
        self.check('small_expand_button_clear_of_telemetry',expand.x()+expand.width()<telemetry.x())
        self.check('small_composer_within_window',composer.y()+composer.height()<=self.window.height())
        self.check('response_does_not_overlap_composer',response.y()+response.height()<composer.y())
        def bounds(a):
            ys,xs=np.nonzero(a[:,:,3]>10)
            bottom=self.scene.y()+int(ys.max()) if len(ys) else 9999
            self.check('small_core_clear_of_response',bottom<response.y(),{'core_bottom':bottom,'response_top':response.y()})
        self.capture('small_core_rgba.png',bounds)
        self.window.grabWindow().save(str(ROOT/'evidence/layout_1280x800.png'))
    def long_response(self):
        self.model._response_detail='Detailed response. '*40;self.model.contentChanged.emit()
        self.click('readResponseButton')
    def after_response(self):
        self.check('long_response_has_full_view',self.window.property('drawer')=='response')
        response_text=self.item('fullResponseText')
        self.check('full_response_is_read_only_and_selectable',response_text.property('readOnly') and response_text.property('selectByMouse') and response_text.property('text')==self.model.responseDetail)
        self.window.setProperty('drawer','');self.window.resize(1920,1080)
    def states(self):
        values={}
        for state in ['IDLE','WAKING','LISTENING','THINKING','SPEAKING','EXECUTING','WAITING_FOR_APPROVAL','VERIFYING','SUCCESS','ERROR','DISCONNECTED']:
            self.model.setState(state);values[state]=self.model.visualState
        self.check('all_state_fixtures_map',all(v=={'WAKING':'AWARE'}.get(k,k) for k,v in values.items()),values)
        self.check('bounded_frame_history',self.model._frame_times.maxlen==36000)
    def orbit_start(self):
        self.model.setState('IDLE');self.model.setQuality(False);self.model.setAnimation(False)
        self.window.setProperty('expanded',True)
        self.scene.setProperty('viewPitch',0.);self.scene.setProperty('viewYaw',0.)
        self.scene.setProperty('hoverX',0.);self.scene.setProperty('hoverY',0.)
        QTimer.singleShot(250,lambda:self.orbit_capture(0))
    def orbit_pose(self,yaw):
        self.scene.setProperty('viewYaw',float(yaw))
        QTimer.singleShot(250,lambda:self.orbit_capture(yaw))
    def orbit_capture(self,yaw):
        def inspect(a):
            ys,xs=np.nonzero(a[:,:,3]>10)
            border=np.concatenate((a[:3].reshape(-1,4),a[-3:].reshape(-1,4),a[:,:3].reshape(-1,4),a[:,-3:].reshape(-1,4)))
            extent=[int(xs.max()-xs.min()),int(ys.max()-ys.min())] if len(xs) else [0,0]
            self.check('yaw_'+str(yaw)+'_keeps_volume_inside_view',border[:,3].max()==0 and min(extent)>.6*min(a.shape[:2]),extent)
        self.capture('orbit_'+str(yaw)+'.png',inspect)
    def finish(self):
        passed=all(c['passed'] is not False for c in self.checks)
        (ROOT/'evidence/validation.json').write_text(json.dumps({'passed':passed,'checks':self.checks,'scope':'In-process Qt input/render checks. No OS input injection or live backend execution.'},indent=2))
        self.app.exit(0 if passed else 1)
