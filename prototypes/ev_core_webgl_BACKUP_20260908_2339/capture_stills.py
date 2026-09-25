import sys
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

class DiagnosticPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        print(f"[JS LOG] {sourceID}:{lineNumber}: {message}", flush=True)

app = QApplication(sys.argv)
view = QWebEngineView()
page = DiagnosticPage()
view.setPage(page)

step = 0

def on_load_finished(ok):
    print(f"Page loaded: {ok}", flush=True)
    QTimer.singleShot(3000, next_step)

def next_step():
    global step
    if step == 0:
        # Step 0: Idle frame
        view.grab().save('d:/EV/prototypes/ev_core_webgl/reference_stills/v3/idle.png')
        print("Saved idle.png", flush=True)
        # Setup for mid-rotation: fast forward time or just let it spin
        page.runJavaScript("EVCore.setState({state: STATES.THINKING});")
        QTimer.singleShot(2500, next_step)
    elif step == 1:
        # Step 1: Mid-rotation (Thinking state has high rotation)
        view.grab().save('d:/EV/prototypes/ev_core_webgl/reference_stills/v3/mid_rotation.png')
        print("Saved mid_rotation.png", flush=True)
        # Setup for close-up: zoom camera in via JS
        page.runJavaScript("EVCore.setState({state: STATES.IDLE}); camera.position.set(2, 5, 5);")
        QTimer.singleShot(2500, next_step)
    elif step == 2:
        # Step 2: Close-up arm detail
        view.grab().save('d:/EV/prototypes/ev_core_webgl/reference_stills/v3/arm_detail_close_up.png')
        print("Saved arm_detail_close_up.png", flush=True)
        app.quit()
    
    step += 1

view.loadFinished.connect(on_load_finished)
view.resize(1920, 1080)
view.load(QUrl.fromLocalFile('d:/EV/prototypes/ev_core_webgl/index.html'))
view.show()

# Failsafe
QTimer.singleShot(20000, lambda: (print("Timeout!", flush=True), app.quit()))
sys.exit(app.exec())

