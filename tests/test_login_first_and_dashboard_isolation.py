"""
Tests for Alpha Billing V2: Login-First Startup, Dashboard Isolation,
Authentication Gate, and Backend Data Integration.
"""
import json
import subprocess
import pytest
from pathlib import Path

from services.company_service import CompanyService
from services.migration_service import MigrationService
from db.database import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_HTML = BASE_DIR / "index.html"
APP_JS = BASE_DIR / "app.js"
CONTEXT_JS = BASE_DIR / "js" / "business_context.js"
HEADER_JS = BASE_DIR / "js" / "header.js"
DASH_JS = BASE_DIR / "js" / "dashboard.js"
NAV_JS = BASE_DIR / "js" / "navigation.js"


# ==============================================================================
# 1. HTML Markup & Initial State Tests
# ==============================================================================

def test_fresh_startup_html_isolation():
    """Verify index.html contains ONLY view-login as active, with header and sidebar hidden."""
    html = INDEX_HTML.read_text(encoding="utf-8")

    # 1. view-login must be active
    assert '<section class="screen-view active" id="view-login">' in html

    # 2. view-dashboard must NOT be active
    assert '<section class="screen-view" id="view-dashboard">' in html
    assert '<section class="screen-view active" id="view-dashboard">' not in html

    # 3. Top header and sidebar must have initial display: none
    assert '<header class="alpha-top-header" id="alpha-top-header" style="display: none;">' in html
    assert '<aside class="alpha-sidebar" id="alpha-sidebar" style="display: none;">' in html

    # 4. No hardcoded admin, company, or branch strings in initial welcome banner
    assert 'Good morning, Admin' not in html
    assert '<strong id="welcome-ctx-company">ANTI MATRIX RETAIL & WHOLESALE</strong>' not in html
    assert '<strong id="welcome-ctx-branch">Main Branch (HQ)</strong>' not in html


def test_startup_app_js_routes_to_login():
    """Verify app.js launches view-login and initializes activeCompany to null."""
    code = APP_JS.read_text(encoding="utf-8")

    # Startup route at the bottom of app.js must be view-login
    assert 'showScreen("view-login");' in code
    assert code.strip().endswith('showScreen("view-login");')

    # activeCompany must be null on startup, not hardcoded COMP0001
    assert 'window.activeCompany = null;' in code
    assert 'activeCompany = null;' in code
    assert 'id: "COMP0001"' not in code[code.find("// Startup"):code.find("// Startup") + 400]


# ==============================================================================
# 2. Authentication State Machine Tests (js/business_context.js)
# ==============================================================================

def test_auth_state_machine_transitions():
    """Verify AuthState machine: UNAUTHENTICATED -> AUTHENTICATING -> AUTHENTICATED -> SESSION_EXPIRED / LOGOUT."""
    node_script = """
    const fs = require('fs');
    const crypto = require('crypto');
    global.window = {};
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.console = { log: () => {}, warn: () => {}, error: () => {} };

    let code = fs.readFileSync('js/business_context.js', 'utf8');
    eval(code);

    const ctx = window.BusinessContext;
    const history = [];
    ctx.on('auth-state-changed', (d) => history.push(d.state));

    // Dynamic UUIDs
    const compId = crypto.randomUUID();
    const branchId = crypto.randomUUID();
    const user1Id = crypto.randomUUID();
    const user2Id = crypto.randomUUID();

    // 1. Initial State
    const initValid = (ctx.getAuthState() === 'UNAUTHENTICATED' && !ctx.isAuthenticatedSession());

    // 2. Transition to AUTHENTICATING
    ctx.setAuthenticating();
    const authenticatingValid = (ctx.getAuthState() === 'AUTHENTICATING' && !ctx.isAuthenticatedSession());

    // 3. Transition to AUTHENTICATED
    ctx.setAuthenticatedSession({
      user: { id: user1Id, username: 'john_manager', displayName: 'John Doe', role: 'Store Manager' },
      company: { id: compId, code: 'C01', name: 'Acme Supermarket', finYear: '2026-2027' },
      branch: { id: branchId, code: 'BR01', name: 'Main Branch' }
    });
    const authValid = (ctx.getAuthState() === 'AUTHENTICATED' && ctx.isAuthenticatedSession());
    const userRole = ctx.getCurrentUser().role;
    const userInitials = ctx.getCurrentUser().avatarInitials;

    // 4. Invalidate Session via Logout
    ctx.clearAuthenticatedSession('logout');
    const logoutValid = (ctx.getAuthState() === 'UNAUTHENTICATED' && !ctx.isAuthenticatedSession() && ctx.getCurrentUser() === null);

    // 5. Invalidate Session via Expiration
    ctx.setAuthenticatedSession({
      user: { id: user2Id, username: 'cashier_1', displayName: 'Jane Cashier', role: 'Cashier' },
      company: { id: compId, code: 'C01', name: 'Acme Supermarket' },
      branch: { id: branchId, code: 'BR01', name: 'Main Branch' }
    });
    ctx.expireSession();
    const expireValid = (ctx.getAuthState() === 'SESSION_EXPIRED' && !ctx.isAuthenticatedSession());

    process.stdout.write(JSON.stringify({
      initValid,
      authenticatingValid,
      authValid,
      userRole,
      userInitials,
      logoutValid,
      expireValid,
      history
    }));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    json_lines = [l for l in res.stdout.strip().splitlines() if l.startswith('{')]
    data = json.loads(json_lines[-1])

    assert data["initValid"] is True
    assert data["authenticatingValid"] is True
    assert data["authValid"] is True
    assert data["userRole"] == "Store Manager"
    assert data["userInitials"] == "JD"
    assert data["logoutValid"] is True
    assert data["expireValid"] is True
    assert "AUTHENTICATING" in data["history"]
    assert "AUTHENTICATED" in data["history"]
    assert "SESSION_EXPIRED" in data["history"]


# ==============================================================================
# 3. Dashboard Isolation Tests (js/dashboard.js)
# ==============================================================================

def test_dashboard_isolation_before_login():
    """Verify DashboardManager does not render data or query backend when unauthenticated."""
    node_script = """
    const fs = require('fs');
    global.window = {};
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.console = { log: () => {}, warn: () => {}, error: () => {} };

    // Mock DOM elements
    const dom = {};
    global.document = {
      getElementById: (id) => {
        if (!dom[id]) dom[id] = { textContent: '', innerHTML: '', style: {} };
        return dom[id];
      }
    };

    // Load business context in unauthenticated state
    eval(fs.readFileSync('js/business_context.js', 'utf8'));
    eval(fs.readFileSync('js/dashboard.js', 'utf8'));

    const dash = window.DashboardManager;
    dash.init();

    // Check DOM state
    const welcomeHeading = dom['welcome-greeting-heading'] ? dom['welcome-greeting-heading'].textContent : null;
    const companyText = dom['welcome-ctx-company'] ? dom['welcome-ctx-company'].textContent : null;
    const isLive = dash.isLiveMode;
    const hasInterval = Boolean(dash.clockInterval);

    process.stdout.write(JSON.stringify({
      welcomeHeading,
      companyText,
      isLive,
      hasInterval
    }));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    json_lines = [l for l in res.stdout.strip().splitlines() if l.startswith('{')]
    data = json.loads(json_lines[-1])

    # Must be completely blank/placeholder before login
    assert data["welcomeHeading"] == ""
    assert data["companyText"] == "--"
    assert data["isLive"] is False
    assert data["hasInterval"] is False


def test_dashboard_initializes_after_authentication():
    """Verify DashboardManager populates user identity and starts updates when authenticated."""
    node_script = """
    const fs = require('fs');
    const crypto = require('crypto');
    global.window = {};
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.console = { log: () => {}, warn: () => {}, error: () => {} };

    // Mock DOM elements
    const dom = {};
    global.document = {
      getElementById: (id) => {
        if (!dom[id]) dom[id] = { textContent: '', innerHTML: '', style: {}, addEventListener: () => {}, hasChildNodes: () => false };
        return dom[id];
      },
      querySelectorAll: () => []
    };
    window.getLucideIcon = global.getLucideIcon = () => '<svg></svg>';

    // Load business context & dashboard
    eval(fs.readFileSync('js/business_context.js', 'utf8'));
    eval(fs.readFileSync('js/dashboard.js', 'utf8'));

    const ctx = window.BusinessContext;
    const dash = window.DashboardManager;
    dash.init();

    // Authenticate with dynamic UUIDs
    const compId = crypto.randomUUID();
    const branchId = crypto.randomUUID();
    const userId = crypto.randomUUID();

    ctx.setAuthenticatedSession({
      user: { id: userId, username: 'priya_cashier', displayName: 'Priya Sharma', role: 'Cashier' },
      company: { id: compId, code: 'C01', name: 'Priya Supermarket', finYear: '2026-2027' },
      branch: { id: branchId, code: 'BR01', name: 'Main Branch' }
    });

    const greeting = dom['welcome-greeting-heading'].textContent;
    const company = dom['welcome-ctx-company'].textContent;
    const hasClock = Boolean(dash.clockInterval);

    // Logout
    ctx.clearAuthenticatedSession('logout');
    const greetingAfterLogout = dom['welcome-greeting-heading'].textContent;
    const companyAfterLogout = dom['welcome-ctx-company'].textContent;
    const hasClockAfterLogout = Boolean(dash.clockInterval);

    process.stdout.write(JSON.stringify({
      greeting,
      company,
      hasClock,
      greetingAfterLogout,
      companyAfterLogout,
      hasClockAfterLogout
    }));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    json_lines = [l for l in res.stdout.strip().splitlines() if l.startswith('{')]
    data = json.loads(json_lines[-1])

    assert "Priya Sharma" in data["greeting"]
    assert data["company"] == "Priya Supermarket"
    assert data["hasClock"] is True
    # After logout, all dashboard data is wiped
    assert data["greetingAfterLogout"] == ""
    assert data["companyAfterLogout"] == "--"
    assert data["hasClockAfterLogout"] is False


# ==============================================================================
# 4. Backend Authentication Service Tests (SQLAlchemy / Database)
# ==============================================================================

@pytest.fixture
def test_company_service(tmp_path):
    import uuid
    from core.security import hash_password
    db_file = tmp_path / "test_auth_gate.db"
    db_mgr = DatabaseManager(str(db_file))
    db_mgr.run_migrations()

    comp_svc = CompanyService(db=db_mgr)
    comp_svc._ensure_sqlite_user_tables()

    cid = str(uuid.uuid4())
    bid = str(uuid.uuid4())
    ccode = "COMP0001"

    with db_mgr.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state, username, password_hash)
            VALUES (?, ?, ?, '2026-2027', '33AAAPL1234F1Z1', 'Tamilnadu', 'admin_user', ?);
        """, (cid, ccode, "Test Corp Alpha", hash_password("secretpassword")))
        cur.execute("""
            INSERT INTO branches (id, company_id, code, name, is_default)
            VALUES (?, ?, 'BR01', 'Main Branch', 1);
        """, (bid, cid))
        cur.execute("INSERT OR IGNORE INTO roles (id, name, description) VALUES (?, ?, ?);",
                    (str(uuid.uuid4()), "Administrator", "Administrator role"))
        conn.commit()

    comp_svc.create_user(
        company_id=cid,
        username="admin_user",
        password="secretpassword",
        full_name="Admin User",
        role_name="Administrator"
    )

    yield comp_svc
    db_mgr.dispose()


def test_backend_auth_valid_and_invalid(test_company_service):
    # Valid credentials with username
    comp = test_company_service.authenticate("COMP0001", "secretpassword", username="admin_user")
    assert comp is not None
    assert comp["code"] == "COMP0001"
    assert comp["name"] == "Test Corp Alpha"
    assert comp["role"] == "Administrator"

    # Missing username returns None (fail-closed legacy gating)
    assert test_company_service.authenticate("COMP0001", "secretpassword") is None

    # Invalid password
    assert test_company_service.authenticate("COMP0001", "wrong_pass", username="admin_user") is None

    # Invalid company
    assert test_company_service.authenticate("NON_EXISTENT", "secretpassword", username="admin_user") is None


def test_backend_auth_multi_user_roles(test_company_service):
    """Verify users table lookup supports dynamic roles (Manager, Cashier)."""
    # 1. Create a Manager
    manager = test_company_service.create_user(
        company_id="COMP0001",
        username="m_manager",
        password="mgrpassword",
        full_name="Mukesh Manager",
        role_name="Store Manager"
    )
    assert manager["username"] == "m_manager"

    # 2. Create a Cashier
    cashier = test_company_service.create_user(
        company_id="COMP0001",
        username="c_cashier",
        password="cashpassword",
        full_name="Chitra Cashier",
        role_name="Cashier"
    )
    assert cashier["username"] == "c_cashier"

    # 3. Authenticate Manager
    auth_mgr = test_company_service.authenticate("COMP0001", "mgrpassword", username="m_manager")
    assert auth_mgr is not None
    assert auth_mgr["displayName"] == "Mukesh Manager"
    assert auth_mgr["role"] == "Store Manager"

    # 4. Authenticate Cashier
    auth_csh = test_company_service.authenticate("COMP0001", "cashpassword", username="c_cashier")
    assert auth_csh is not None
    assert auth_csh["displayName"] == "Chitra Cashier"
    assert auth_csh["role"] == "Cashier"

    # 5. Wrong password for Cashier
    assert test_company_service.authenticate("COMP0001", "wrongpass", username="c_cashier") is None


# ==============================================================================
# 5. Header & Navigation Dynamic Identity & Route Guard Tests
# ==============================================================================

def test_header_dynamic_identity_and_visibility():
    """Verify HeaderManager hides header before login, and shows dynamic user/company after login."""
    node_script = """
    const fs = require('fs');
    const crypto = require('crypto');
    global.window = {};
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.console = { log: () => {}, warn: () => {}, error: () => {} };

    const dom = {};
    global.document = {
      getElementById: (id) => {
        if (!dom[id]) dom[id] = { textContent: '', innerHTML: '', title: '', style: {}, dataset: {}, querySelector: () => ({ innerHTML: '' }), addEventListener: () => {} };
        return dom[id];
      },
      querySelectorAll: () => [],
      addEventListener: () => {}
    };
    window.getLucideIcon = global.getLucideIcon = () => '<svg></svg>';

    eval(fs.readFileSync('js/business_context.js', 'utf8'));
    eval(fs.readFileSync('js/header.js', 'utf8'));

    const ctx = window.BusinessContext;
    const header = window.HeaderManager;
    header.init();

    // 1. Before login: Header must be hidden
    const headerDisplayBefore = dom['alpha-top-header'].style.display;
    const companyBefore = dom['header-company-val'].textContent;

    // 2. Authenticate as Cashier with dynamic UUIDs
    const compId = crypto.randomUUID();
    const branchId = crypto.randomUUID();
    const userId = crypto.randomUUID();

    ctx.setAuthenticatedSession({
      user: { id: userId, username: 'kavitha_cashier', displayName: 'Kavitha R', role: 'Cashier' },
      company: { id: compId, code: 'C01', name: 'Kavitha Retail Mart', finYear: '2026-2027' },
      branch: { id: branchId, code: 'BR01', name: 'South Branch Counter' }
    });

    const headerDisplayAfter = dom['alpha-top-header'].style.display;
    const companyAfter = dom['header-company-val'].textContent;
    const branchAfter = dom['header-branch-val'].textContent;
    const userNameAfter = dom['header-user-name'].textContent;
    const userAvatarAfter = dom['header-user-avatar'].textContent;

    // 3. Logout
    ctx.clearAuthenticatedSession('logout');
    const headerDisplayLogout = dom['alpha-top-header'].style.display;
    const companyLogout = dom['header-company-val'].textContent;

    process.stdout.write(JSON.stringify({
      headerDisplayBefore,
      companyBefore,
      headerDisplayAfter,
      companyAfter,
      branchAfter,
      userNameAfter,
      userAvatarAfter,
      headerDisplayLogout,
      companyLogout
    }));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    json_lines = [l for l in res.stdout.strip().splitlines() if l.startswith('{')]
    data = json.loads(json_lines[-1])

    # Before login: Hidden & empty
    assert data["headerDisplayBefore"] == "none"
    assert data["companyBefore"] == ""

    # After login: Visible with real Cashier details
    assert data["headerDisplayAfter"] == "flex"
    assert "Kavitha Retail Mart" in data["companyAfter"]
    assert data["branchAfter"] == "South Branch Counter"
    assert data["userNameAfter"] == "Kavitha R"
    assert data["userAvatarAfter"] == "KR"

    # After logout: Hidden & cleared
    assert data["headerDisplayLogout"] == "none"
    assert data["companyLogout"] == ""


def test_sidebar_navigation_route_guard():
    """Verify SidebarNavigation blocks unauthenticated action execution and redirects to view-login."""
    node_script = """
    const fs = require('fs');
    const crypto = require('crypto');
    global.window = {};
    global.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
    global.console = { log: () => {}, warn: () => {}, error: () => {} };

    let routedScreen = null;
    let toastMessage = null;
    window.showScreen = (screen) => { routedScreen = screen; };
    window.showToast = (msg) => { toastMessage = msg; };
    window.getLucideIcon = global.getLucideIcon = () => '<svg></svg>';

    const dom = {};
    global.document = {
      getElementById: (id) => {
        if (!dom[id]) dom[id] = { textContent: '', innerHTML: '', style: {}, appendChild: () => {}, addEventListener: () => {}, dataset: {}, querySelector: () => ({ textContent: '' }) };
        return dom[id];
      },
      createElement: () => ({
        appendChild: () => {},
        setAttribute: () => {},
        classList: { add: () => {}, toggle: () => {} },
        dataset: {},
        addEventListener: () => {}
      }),
      querySelector: () => ({ textContent: '' }),
      querySelectorAll: () => [],
      addEventListener: () => {},
      body: { appendChild: () => {} }
    };

    eval(fs.readFileSync('js/business_context.js', 'utf8'));
    eval(fs.readFileSync('js/navigation.js', 'utf8'));

    const ctx = window.BusinessContext;
    const nav = window.SidebarNavigation;
    nav.init();

    // 1. Sidebar must be hidden before login
    const sidebarDisplayBefore = dom['alpha-sidebar'].style.display;

    // 2. Attempt protected action when unauthenticated
    nav.executeAction({ action: 'open-view', targetView: 'view-dashboard', label: 'Operational Dashboard' });
    const blockedRoute = routedScreen;
    const blockedToast = toastMessage;

    // 3. Authenticate with dynamic UUIDs
    const compId = crypto.randomUUID();
    const branchId = crypto.randomUUID();
    const userId = crypto.randomUUID();

    ctx.setAuthenticatedSession({
      user: { id: userId, username: 'ramesh_admin', displayName: 'Ramesh Admin', role: 'Administrator' },
      company: { id: compId, code: 'C01', name: 'Ramesh Stores', finYear: '2026-2027' },
      branch: { id: branchId, code: 'BR01', name: 'Main Branch' }
    });
    const sidebarDisplayAfter = dom['alpha-sidebar'].style.display;

    // 4. Allowed action when authenticated
    nav.executeAction({ action: 'open-view', targetView: 'view-dashboard', label: 'Operational Dashboard' });
    const allowedRoute = routedScreen;

    process.stdout.write(JSON.stringify({
      sidebarDisplayBefore,
      blockedRoute,
      blockedToast,
      sidebarDisplayAfter,
      allowedRoute
    }));
    """
    res = subprocess.run(["node", "-e", node_script], cwd=str(BASE_DIR), capture_output=True, text=True, check=True)
    json_lines = [l for l in res.stdout.strip().splitlines() if l.startswith('{')]
    data = json.loads(json_lines[-1])

    assert data["sidebarDisplayBefore"] == "none"
    assert data["blockedRoute"] == "view-login"
    assert "Authentication required" in data["blockedToast"]
    assert data["sidebarDisplayAfter"] == ""
    assert data["allowedRoute"] == "view-dashboard"


# ==============================================================================
# 5. Qt WebChannel Signal Wire Protocol & Live Desktop Startup Tests
# ==============================================================================

def test_qwebchannel_wire_protocol_passes_integer_signal_id():
    """Verify that qwebchannel.js passes integer signalId to connectToSignal and disconnectFromSignal.
    
    Passing string signalName causes Qt C++ to fail integer conversion (toInt(-1))
    and log 'Cannot find signal with index -1 of object BackendBridge'.
    """
    for file_path in [BASE_DIR / "qwebchannel.js", BASE_DIR / "desktop" / "qwebchannel.js"]:
        content = file_path.read_text(encoding="utf-8")
        assert "signal: signalId" in content
        assert "connect: (function(signalName, signalId)" in content
        assert "disconnect: (function(signalName, signalId)" in content
        # Ensure we do not pass signal: signalName to exec
        assert "signal: signalName" not in content


def test_live_desktop_startup_zero_javascript_errors_and_zero_invalid_signals():
    """Verify live PyQt5 startup of index.html produces zero uncaught JS errors and zero invalid signals."""
    import sys
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QEventLoop, QTimer
    from PyQt5.QtWebEngineWidgets import QWebEnginePage
    from desktop.main_window import MainWindow, CustomWebPage

    app = QApplication.instance() or QApplication(sys.argv)

    errors = []
    messages = []

    win = MainWindow()
    orig_console = win.web_page.javaScriptConsoleMessage

    def console_hook(level, message, line, source_id):
        orig_console(level, message, line, source_id)
        messages.append((level, line, message))
        if level == QWebEnginePage.ErrorMessageLevel:
            errors.append((line, message))

    win.web_page.javaScriptConsoleMessage = console_hook

    loop = QEventLoop()
    win.web_view.loadFinished.connect(lambda ok: loop.quit())
    loop.exec_()

    # Allow startup script execution to settle
    settle_loop = QEventLoop()
    QTimer.singleShot(1000, settle_loop.quit)
    settle_loop.exec_()

    def eval_js(script):
        res = {}
        l = QEventLoop()
        win.web_view.page().runJavaScript(script, lambda val: (res.setdefault("val", val), l.quit()))
        l.exec_()
        return res["val"]

    # 1. Zero uncaught JavaScript errors
    assert len(errors) == 0, f"Uncaught JS errors encountered: {errors}"

    # 2. Specifically verify no 'displayName' error occurred
    display_name_errors = [m for _, _, m in messages if "displayName" in m]
    assert len(display_name_errors) == 0

    # 3. Verify screen and auth states
    assert eval_js('document.getElementById("view-login").classList.contains("active")') is True
    assert eval_js('document.getElementById("view-dashboard").classList.contains("active")') is False
    assert eval_js('window.getComputedStyle(document.getElementById("alpha-top-header")).display') == "none"
    assert eval_js('window.getComputedStyle(document.getElementById("alpha-sidebar")).display') == "none"
    assert eval_js('window.BusinessContext ? window.BusinessContext.isAuthenticatedSession() : null') is False
    assert eval_js('window.BusinessContext ? window.BusinessContext.getCurrentUser() : undefined') is None
    assert eval_js('window.activeCompany') is None

    win.close()


