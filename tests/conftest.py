import sys
import os
from pathlib import Path
import pytest
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QEventLoop, QTimer

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"

# Default PostgreSQL test URL (can be overridden via env var)
DEFAULT_PG_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")


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


@pytest.fixture(autouse=True)
def ensure_postgresql_used():
    """
    Ensures all tests use PostgreSQL when DATABASE_URL is configured.
    This prevents tests from accidentally writing to SQLite and corrupting the guardian database.
    """
    # Ensure DATABASE_URL is set to PostgreSQL
    if "DATABASE_URL" in os.environ:
        original_url = os.environ["DATABASE_URL"]
    else:
        original_url = None

    # Force PostgreSQL URL for tests when it's configured
    if original_url and original_url.startswith("sqlite"):
        # Test explicitly needs SQLite - allow it but with isolation
        yield
        return

    # Ensure we're using PostgreSQL (not SQLite)
    os.environ["DATABASE_URL"] = DEFAULT_PG_URL

    # Force reinitialization of db_manager singleton for PostgreSQL
    try:
        import db.database as db_module
        # Create new DatabaseManager with PostgreSQL URL
        new_manager = db_module.DatabaseManager(DEFAULT_PG_URL)
        # Replace the singleton instance
        db_module.db_manager = new_manager
    except ImportError:
        pass

    yield

    # Restore original environment
    if original_url is not None:
        os.environ["DATABASE_URL"] = original_url
    else:
        os.environ.pop("DATABASE_URL", None)

