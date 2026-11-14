"""
Pytest configuration for Alpha Billing V2.
Enforces strict test database isolation:
- Tests default to isolated SQLite (in-memory or tmp file).
- Neutralizes remote database URLs from .env to prevent accidental hits to production.
- Allows local PostgreSQL only when TEST_DATABASE_URL is explicitly set to localhost/127.0.0.1.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
import pytest

# 1. Environment configuration established at the very top of conftest.py BEFORE any application imports
_test_db_url = os.environ.get("TEST_DATABASE_URL", "").strip()
if not _test_db_url:
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["TESTING"] = "1"
    # Neutralize secondary database URLs that core.configuration checks if DATABASE_URL was absent
    os.environ.pop("SUPABASE_DATABASE_URL", None)
    os.environ.pop("ANTI_MATRIX_DATABASE_URL", None)
else:
    _parsed = urlparse(_test_db_url)
    _scheme = _parsed.scheme.lower()
    _hostname = (_parsed.hostname or "").lower()
    _is_sqlite = _scheme.startswith("sqlite")
    _is_localhost = _hostname in ("localhost", "127.0.0.1", "::1")
    if not (_is_sqlite or _is_localhost):
        raise RuntimeError(
            f"SAFETY VIOLATION: TEST_DATABASE_URL ({_test_db_url}) points to unauthorized host '{_hostname}'. "
            f"Automated tests are prohibited from targeting remote databases!"
        )
    os.environ["DATABASE_URL"] = _test_db_url
    os.environ["TESTING"] = "1"
    os.environ.pop("SUPABASE_DATABASE_URL", None)
    os.environ.pop("ANTI_MATRIX_DATABASE_URL", None)

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent / "index.html"


@pytest.fixture(scope="session", autouse=True)
def assert_safe_test_environment():
    """Verify that tests are executing strictly against local/sqlite databases."""
    active_url = os.environ.get("DATABASE_URL", "")
    assert not any(remote in active_url.lower() for remote in ["supabase.co", "pooler.supabase.com", "aws", "azure"]), \
        f"SAFETY VIOLATION: Test running against remote database URL: {active_url}"
    yield


@pytest.fixture(scope="session")
def qt_app():
    from PyQt5.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="session")
def session_web_view(qt_app):
    from PyQt5.QtWebChannel import QWebChannel
    from PyQt5.QtWebEngineWidgets import QWebEngineView
    from PyQt5.QtCore import QUrl, QEventLoop, QTimer
    from desktop.web_bridge import BackendBridge

    view = QWebEngineView()
    channel = QWebChannel(view)
    bridge = BackendBridge(parent=view)
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
