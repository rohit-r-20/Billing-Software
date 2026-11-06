import sys
from pathlib import Path
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEventLoop, QTimer

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


@pytest.fixture(scope="session")
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="session")
def session_web_view(qt_app):
    from PyQt5.QtWebChannel import QWebChannel
    from desktop.web_bridge import BackendBridge

    view = QWebEngineView()
    channel = QWebChannel(view)
    bridge = BackendBridge(view)
    channel.registerObject("backend", bridge)
    view.page().setWebChannel(channel)

    view.resize(1280, 800)
    view.show()
    view.load(QUrl.fromLocalFile(str(INDEX_HTML_PATH)))

    loop = QEventLoop()
    view.loadFinished.connect(lambda ok: loop.quit())
    loop.exec_()

    loop = QEventLoop()
    QTimer.singleShot(1000, loop.quit)
    loop.exec_()

    yield view
    view.close()

