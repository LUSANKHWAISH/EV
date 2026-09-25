"""Rendered settings review using isolated providers and mocked connection tests."""
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
from unittest.mock import MagicMock,patch

os.environ['EV_STARTUP_AUDIO']='false'
os.environ['QML_DISABLE_DISK_CACHE']='1'
os.environ.setdefault('QT_QUICK_CONTROLS_STYLE','Basic')
from PySide6.QtCore import QEventLoop,QTimer,QUrl,Qt,qInstallMessageHandler
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest
from core.events import EVEventBus
from core.experience import EVExperienceManager
from core.models import EVState
from core.provider_config import AIProviderConfigStore,DPAPICredentialStore
from gui.bridge import GuiBridge
from .integration import configure_cinematic,attach_cinematic_window

DEST=Path(__file__).resolve().parent/'evidence/settings_redesign'


def wait(ms):
    loop=QEventLoop();QTimer.singleShot(ms,loop.quit);loop.exec()


def main():
    messages=[];checks=[]
    qInstallMessageHandler(lambda kind,context,message:messages.append(message))
    sys.excepthook=lambda kind,value,tb:messages.append('CALLBACK ERROR '+''.join(traceback.format_exception(kind,value,tb)))
    app=QGuiApplication(['settings-design-review']);engine=QQmlApplicationEngine()
    temporary=tempfile.TemporaryDirectory(prefix='ev-settings-review-');scratch=Path(temporary.name)
    bus=EVEventBus(initial_state=EVState.IDLE);bridge=GuiBridge(bus)
    bridge.set_experience_manager(EVExperienceManager(bus))
    store=AIProviderConfigStore(config_path=scratch/'providers.json',credential_store=DPAPICredentialStore(store_path=scratch/'credentials.bin'))
    bridge.set_provider_config_store(store)
    bridge._get_core_style_path=lambda:scratch/'core_style.json'
    provider=next(p for p in json.loads(bridge.getProvidersJson()) if p['provider_type']=='Gemini')
    bridge.saveProvider(json.dumps(provider),'visual-test-key-not-a-real-credential');bridge.setActiveProvider(provider['id'])
    engine.rootContext().setContextProperty('guiBridge',bridge)
    engine.load(QUrl.fromLocalFile(str(configure_cinematic(engine,bridge))))
    if not engine.rootObjects(): print(messages);return 2
    window=engine.rootObjects()[0];attach_cinematic_window(engine,window)
    model=engine._cinematic_model
    pump=QTimer(window);pump.setInterval(33);pump.timeout.connect(lambda:window.grabWindow());pump.start()
    def check(name,condition,detail=None):checks.append({'name':name,'passed':bool(condition),'detail':detail})
    def item(name):
        control=window.findChild(QQuickItem,name)
        if control is None:
            pending=[window.contentItem()]
            while pending:
                candidate=pending.pop()
                if candidate.objectName()==name:
                    control=candidate;break
                pending.extend(candidate.childItems())
        if control is None:raise AssertionError('Missing '+name)
        return control
    def click(name):
        control=item(name)
        QTest.mouseClick(window,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,control.mapToScene(control.boundingRect().center()).toPoint());wait(100)
    def capture(name):window.grabWindow().save(str(DEST/(name+'.png')))
    def run():
        try:
            model.openProviderSettings();wait(300)
            overlay=item('settingsOverlay');panel=item('settingsPanel');stage=item('cinematicStage')
            check('modal_uses_cinematic_style',overlay.property('cinematic') and panel.property('color').name()=='#0b151d')
            check('settings_owns_input',not stage.isEnabled())
            check('credential_remains_password_masked',QQmlExpression(engine.rootContext(),item('keyInput'),'echoMode === 2').evaluate()[0])
            capture('providers_1920')
            click('providerType');capture('provider_dropdown');QTest.keyClick(window,Qt.Key.Key_Escape);wait(100)
            response=MagicMock();response.status_code=200
            with patch('httpx.Client.get',return_value=response) as network:
                click('providerTest')
                check('connection_button_keeps_existing_route',network.called and 'Connection successful' in item('providerStatus').property('text'))
            # Enter a name using the actual field and persist only to the fixture store.
            click('nameInput');QTest.keyClick(window,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
            item('nameInput').setProperty('text','Gemini studio');click('providerSave')
            check('save_button_updates_isolated_provider',any(p['name']=='Gemini studio' for p in json.loads(bridge.getProvidersJson())))
            saved=next(p for p in json.loads(bridge.getProvidersJson()) if p['id']==provider['id'])
            check('saving_retains_masked_credential',saved['has_credential'] and 'api_key' not in saved)
            click('providerAdd');click('nameInput');QTest.keyClick(window,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier)
            item('nameInput').setProperty('text','Design fixture');click('providerSave')
            custom=next(p for p in json.loads(bridge.getProvidersJson()) if p['name']=='Design fixture')
            check('add_provider_works',bool(custom['id']))
            window.setMinimumWidth(800);window.setMinimumHeight(600);window.resize(800,600);wait(500)
            capture('inactive_800')
            delete=item('providerDelete');corner=delete.mapToScene(delete.boundingRect().bottomRight())
            panel_corner=panel.mapToScene(panel.boundingRect().bottomRight())
            check('inactive_actions_fit_inside_panel',corner.x()<panel_corner.x()-20 and corner.y()<panel_corner.y()-20)
            window.resize(1920,1080);wait(200)
            click('providerActivate')
            check('activate_provider_works',bridge.activeProviderName=='Design fixture')
            bridge.setActiveProvider(provider['id']);wait(100)
            # Select the saved custom profile, then delete it through its real control.
            QQmlExpression(engine.rootContext(),overlay,'selectProvider('+json.dumps(custom)+')').evaluate();wait(100);click('providerDelete')
            check('delete_provider_works',all(p['id']!=custom['id'] for p in json.loads(bridge.getProvidersJson())))
            # Exercise the actual custom dropdown and conditional Azure fields.
            combo=item('providerType');combo.forceActiveFocus()
            QTest.keyClick(window,Qt.Key.Key_Home);QTest.keyClick(window,Qt.Key.Key_Down);QTest.keyClick(window,Qt.Key.Key_Down);QTest.keyClick(window,Qt.Key.Key_Return);wait(100)
            check('azure_fields_visible',combo.property('currentText')=='Azure OpenAI' and item('endpointInput').isVisible())
            capture('azure_1920')
            bridge.providerListChanged.emit();wait(100)
            for category in ('VOICE','APPEARANCE','CORE STYLE','AUDIO','GENERAL'):
                click('settingsTab_'+category)
                check('category_'+category,overlay.property('activeCategory')==category)
                if category=='CORE STYLE':
                    click('settingsStyle_ORIGINAL');check('classic_style_control_still_works',bridge.stylePreset=='ORIGINAL');capture('core_styles')
            click('settingsTab_AI PROVIDERS')
            for width,height in ((1100,760),(800,600)):
                window.setMinimumWidth(800);window.setMinimumHeight(600);window.resize(width,height);wait(500)
                capture('providers_'+str(width))
                bounds=[]
                for name in ('providerTest','providerActivate','providerSave','settingsClose'):
                    control=item(name);point=control.mapToScene(control.boundingRect().bottomRight())
                    bounds.append((name,point.x(),point.y()))
                check('actions_fit_'+str(width),all(0<x<width and 0<y<height for _,x,y in bounds),bounds)
            window.resize(1920,1080);wait(300)
            bridge._on_approval_requested_internal({'task_id':'settings-ui-fixture','action':'TEST_ONLY','description':'No executor attached','risk_level':'LOW','reason':'Modal layering'})
            wait(200)
            check('approval_remains_above_settings',item('approvalOverlay').isVisible() and item('approvalOverlay').z()>overlay.z())
            click('rejectButton');click('settingsClose');wait(250)
            check('close_restores_main_interface',not bridge.settingsVisible and stage.isEnabled())
        except Exception:
            check('validation_exception',False,traceback.format_exc())
        finally:
            problems=[m for m in messages if any(w in m.lower() for w in ('referenceerror','typeerror','callback error','binding loop','cannot assign','failed to load'))]
            check('no_qml_or_callback_errors',not problems,problems)
            model.music.close();bridge.shutdown()
            report={'passed':all(c['passed'] for c in checks),'checks':checks,'scope':'Real rendered QML and GuiBridge; temporary provider/credential store, fake credential, mocked HTTP. No live provider changes or network calls.'}
            (DEST/'validation.json').write_text(json.dumps(report,indent=2));(DEST/'diagnostics.txt').write_text('\n'.join(messages),encoding='utf-8')
            print(json.dumps(report),flush=True);app.exit(0 if report['passed'] else 1)
    QTimer.singleShot(1600,run)
    code=app.exec();model.music.close();bridge.shutdown();temporary.cleanup();return code


if __name__=='__main__':raise SystemExit(main())
