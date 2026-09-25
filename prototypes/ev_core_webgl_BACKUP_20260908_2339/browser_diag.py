import sys
import time
from PySide6.QtCore import QUrl, QTimer, Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtGui import QImage

class DiagnosticPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        levels = {
            QWebEnginePage.InfoMessageLevel: "INFO",
            QWebEnginePage.WarningMessageLevel: "WARN",
            QWebEnginePage.ErrorMessageLevel: "ERROR"
        }
        level_str = levels.get(level, "LOG")
        print(f"[{level_str}] {sourceID}:{lineNumber}: {message}")

app = QApplication(sys.argv)
view = QWebEngineView()
page = DiagnosticPage()
view.setPage(page)

def on_load_finished(ok):
    print(f"Page loaded: {ok}")
    # Wait a bit for Three.js to render
    QTimer.singleShot(2000, take_screenshot)

def take_screenshot():
    view.grab().save('d:/EV/prototypes/ev_core_webgl/diagnostic_screenshot.png')
    print("Screenshot saved to diagnostic_screenshot.png")
    app.quit()

view.loadFinished.connect(on_load_finished)
view.resize(1024, 576)
view.load(QUrl.fromLocalFile('d:/EV/prototypes/ev_core_webgl/index.html'))
view.show()

# Failsafe timer
QTimer.singleShot(10000, lambda: (print("Timeout!"), app.quit()))
sys.exit(app.exec())
