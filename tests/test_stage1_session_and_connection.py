"""
Stage 1 Isolated Verification Suite:
Session Authentication, Fail-Closed Role Validation, Strict BR01 Branch Resolution,
Sanitized Public Company Projections, and Frontend Business Context Validation.

All tests run on isolated temporary databases with dynamic UUIDs.
Zero interaction with production Supabase PostgreSQL.
"""
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
import pytest

from core.security import hash_password
from db.database import DatabaseManager
from services.company_service import CompanyService, RECOGNIZED_SYSTEM_ROLES
from desktop.web_bridge import BackendBridge

BASE_DIR = Path(__file__).resolve().parent.parent
CONTEXT_JS = BASE_DIR / "js" / "business_context.js"


@pytest.fixture
def isolated_env():
    """Sets up an isolated SQLite database and backend bridge."""
    fd, db_path = tempfile.mkstemp(suffix="_stage1_test.db")
    os.close(fd)
    db_url = f"sqlite:///{db_path}"
    test_db = DatabaseManager(db_url)

    # Initialize tables required for Stage 1
    with test_db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE companies (
                id VARCHAR(36) PRIMARY KEY,
                code VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(100) NOT NULL,
                fin_year VARCHAR(20),
                gstin VARCHAR(20),
                state VARCHAR(50),
                address TEXT,
                username VARCHAR(50),
                password_hash VARCHAR(255),
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE branches (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL,
                code VARCHAR(20) NOT NULL,
                name VARCHAR(100) NOT NULL,
                address TEXT,
                phone VARCHAR(20),
                is_default INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE roles (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(50) UNIQUE NOT NULL,
                description TEXT
            );
        """)
        cur.execute("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36) NOT NULL,
                username VARCHAR(50) NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                full_name VARCHAR(100),
                role_id VARCHAR(36),
                role_name VARCHAR(50) NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("""
            CREATE TABLE audit_logs (
                id VARCHAR(36) PRIMARY KEY,
                company_id VARCHAR(36),
                username VARCHAR(50),
                action VARCHAR(50),
                entity_type VARCHAR(50),
                entity_id VARCHAR(36),
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Seed roles
        for r in RECOGNIZED_SYSTEM_ROLES:
            cur.execute("INSERT INTO roles (id, name, description) VALUES (?, ?, ?);",
                        (f"role-{r.lower()[:15]}", r, f"{r} system role"))

        conn.commit()

    # Create isolated services and bridge
    comp_svc = CompanyService(db=test_db)
    bridge = BackendBridge(parent=None)
    # Patch bridge dependencies to use isolated instances
    import desktop.web_bridge as wb_module
    old_svc = wb_module.company_service
    old_db = wb_module.db_manager
    wb_module.company_service = comp_svc
    wb_module.db_manager = test_db

    yield {
        "db": test_db,
        "comp_svc": comp_svc,
        "bridge": bridge,
        "db_path": db_path
    }

    # Teardown
    wb_module.company_service = old_svc
    wb_module.db_manager = old_db
    test_db.dispose()
    try:
        os.remove(db_path)
    except OSError:
        pass


def test_stage1_successful_user_authentication(isolated_env):
    """Verify authoritative user login with genuine UUIDs and strict BR01 branch binding."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    bid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name, username) VALUES (?, ?, ?, ?);",
                    (cid, ccode, "Test Corp Alpha", "admin_co"))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (bid, cid, "BR01", "Main Operating Branch", 1))
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (uid, cid, "alice", hash_password("pass123"), "Administrator", 1))
        conn.commit()

    res_raw = bridge.authenticateUser(ccode, "alice", "pass123")
    res = json.loads(res_raw)

    assert res["success"] is True
    data = res["data"]
    assert data["company"]["id"] == cid
    assert data["company"]["code"] == ccode
    assert data["branch"]["id"] == bid
    assert data["branch"]["code"] == "BR01"
    assert data["user"]["id"] == uid
    assert data["user"]["role"] == "Administrator"

    # Verify backend in-memory session was set
    session = bridge._authenticated_session
    assert session is not None
    assert session["company_id"] == cid
    assert session["branch_id"] == bid
    assert session["user_id"] == uid
    assert session["role"] == "Administrator"


def test_stage1_role_validation_manager_and_cashier(isolated_env):
    """Verify recognition of valid non-Administrator roles (Store Manager, Cashier)."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    bid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid, ccode, "Beta Retail"))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (bid, cid, "BR01", "Branch 01", 1))
        # Manager user
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "bob_mgr", hash_password("mgrpass"), "Store Manager", 1))
        # Cashier user
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "charlie_csh", hash_password("cshpass"), "Cashier", 1))
        conn.commit()

    # Manager auth
    mgr_res = json.loads(bridge.authenticateUser(ccode, "bob_mgr", "mgrpass"))
    assert mgr_res["success"] is True
    assert mgr_res["data"]["user"]["role"] == "Store Manager"

    # Cashier auth
    csh_res = json.loads(bridge.authenticateUser(ccode, "charlie_csh", "cshpass"))
    assert csh_res["success"] is True
    assert csh_res["data"]["user"]["role"] == "Cashier"


def test_stage1_fail_closed_unrecognized_or_empty_role(isolated_env):
    """Verify that empty, NULL, or unrecognized roles fail closed and never default to Administrator."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    bid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid, ccode, "Security Corp"))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (bid, cid, "BR01", "Branch 01", 1))
        # Empty role
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "empty_role_user", hash_password("pass"), "", 1))
        # Unrecognized role
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "rogue_role_user", hash_password("pass"), "SuperAdmin", 1))
        conn.commit()

    # Empty role must be rejected
    res1 = json.loads(bridge.authenticateUser(ccode, "empty_role_user", "pass"))
    assert res1["success"] is False
    assert bridge._authenticated_session is None

    # Unrecognized role must be rejected
    res2 = json.loads(bridge.authenticateUser(ccode, "rogue_role_user", "pass"))
    assert res2["success"] is False
    assert bridge._authenticated_session is None


def test_stage1_disabled_legacy_company_authentication(isolated_env):
    """Verify that legacy company-password authentication is explicitly disabled with zero impersonation."""
    bridge = isolated_env["bridge"]

    res = json.loads(bridge.authenticateCompany("COMP0001", "any_password"))
    assert res["success"] is False
    assert "Legacy company-password authentication is disabled" in res["error"]
    assert bridge._authenticated_session is None


def test_stage1_strict_branch_resolution_missing_br01(isolated_env):
    """Verify authentication fails if company lacks a configured BR01 branch with is_default = 1."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid, ccode, "No Branch Corp"))
        # Non-BR01 branch or is_default=0
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "BR99", "Other Branch", 0))
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "user1", hash_password("pass"), "Administrator", 1))
        conn.commit()

    res = json.loads(bridge.authenticateUser(ccode, "user1", "pass"))
    assert res["success"] is False
    assert "Main Branch (BR01) is not configured" in res["error"]
    assert bridge._authenticated_session is None


def test_stage1_strict_branch_resolution_duplicate_br01(isolated_env):
    """Verify authentication fails if ambiguous multiple default BR01 branches exist."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid, ccode, "Dupe Branch Corp"))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "BR01", "Default 1", 1))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "BR01", "Default 2", 1))
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid, "user1", hash_password("pass"), "Administrator", 1))
        conn.commit()

    res = json.loads(bridge.authenticateUser(ccode, "user1", "pass"))
    assert res["success"] is False
    assert "Multiple default BR01 branches" in res["error"]
    assert bridge._authenticated_session is None


def test_stage1_cross_company_branch_isolation(isolated_env):
    """Verify that a company cannot use or resolve another company's BR01 branch."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid_a = str(uuid.uuid4())
    cid_b = str(uuid.uuid4())
    ccode_a = f"CP{uuid.uuid4().hex[:6].upper()}"
    ccode_b = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid_a, ccode_a, "Company A"))
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid_b, ccode_b, "Company B"))
        # Company A has BR01
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid_a, "BR01", "A BR01", 1))
        # Company B has user but NO branches
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (str(uuid.uuid4()), cid_b, "user_b", hash_password("pass_b"), "Administrator", 1))
        conn.commit()

    # Attempt login for Company B
    res = json.loads(bridge.authenticateUser(ccode_b, "user_b", "pass_b"))
    assert res["success"] is False
    assert "Main Branch (BR01) is not configured" in res["error"]


def test_stage1_session_restoration_and_logout(isolated_env):
    """Verify in-memory session restoration, logout, and subsequent protected RPC rejection."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    bid = str(uuid.uuid4())
    uid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO companies (id, code, name) VALUES (?, ?, ?);", (cid, ccode, "Session Corp"))
        cur.execute("INSERT INTO branches (id, company_id, code, name, is_default) VALUES (?, ?, ?, ?, ?);",
                    (bid, cid, "BR01", "Branch 01", 1))
        cur.execute("INSERT INTO users (id, company_id, username, password_hash, role_name, is_active) VALUES (?, ?, ?, ?, ?, ?);",
                    (uid, cid, "sam", hash_password("sampass"), "Administrator", 1))
        conn.commit()

    # 1. Before auth: session is null
    s0 = json.loads(bridge.getAuthenticatedSession())
    assert s0["success"] is False
    assert s0["authenticated"] is False

    # 2. Authenticate
    auth_res = json.loads(bridge.authenticateUser(ccode, "sam", "sampass"))
    assert auth_res["success"] is True

    # 3. Session restored from memory
    s1 = json.loads(bridge.getAuthenticatedSession())
    assert s1["success"] is True
    assert s1["authenticated"] is True
    assert s1["data"]["company"]["id"] == cid
    assert s1["data"]["branch"]["id"] == bid
    assert s1["data"]["user"]["id"] == uid

    # 4. Logout
    out_res = json.loads(bridge.logout())
    assert out_res["success"] is True
    assert bridge._authenticated_session is None

    # 5. Session after logout is null
    s2 = json.loads(bridge.getAuthenticatedSession())
    assert s2["success"] is False
    assert s2["authenticated"] is False

    # 6. Protected RPC after logout fails closed
    rpc_res = json.loads(bridge.getCompanyConfig(ccode))
    assert rpc_res["success"] is False
    assert "Authentication required" in rpc_res["error"]


def test_stage1_sanitized_public_company_listing(isolated_env):
    """Verify listCompanies exposes strictly code and name only."""
    db = isolated_env["db"]
    bridge = isolated_env["bridge"]

    cid = str(uuid.uuid4())
    ccode = f"CP{uuid.uuid4().hex[:6].upper()}"

    with db.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO companies (id, code, name, fin_year, gstin, state, password_hash)
            VALUES (?, ?, ?, '2026-2027', '33GSTIN1234', 'Tamilnadu', 'secret_hash');
        """, (cid, ccode, "Public Listed Corp"))
        conn.commit()

    res = json.loads(bridge.listCompanies())
    assert res["success"] is True
    assert len(res["data"]) >= 1

    entry = next(c for c in res["data"] if c["code"] == ccode)
    assert entry == {"code": ccode, "name": "Public Listed Corp"}
    assert "id" not in entry
    assert "password_hash" not in entry
    assert "gstin" not in entry


def test_stage1_frontend_business_context_validation():
    """Verify js/business_context.js fail-closed validation and clean startup via Node.js."""
    node_script = f"""
    const fs = require('fs');
    const vm = require('vm');
    const crypto = require('crypto');
    global.window = {{}};
    const contextCode = fs.readFileSync('{CONTEXT_JS}', 'utf8');
    vm.runInThisContext(contextCode);

    const mgr = new BusinessContextManager();
    mgr.init();

    // 1. Clean startup: unauthenticated
    if (mgr.getAuthState() !== "UNAUTHENTICATED") throw new Error("Initial state not UNAUTHENTICATED");
    if (mgr.isAuthenticated !== false) throw new Error("Initial isAuthenticated not false");
    if (mgr.currentUser !== null) throw new Error("Initial currentUser not null");

    // Dynamic valid UUIDs
    const validCompId = crypto.randomUUID();
    const validUserId = crypto.randomUUID();
    const validBranchId = crypto.randomUUID();

    // 2. Reject null/empty session
    if (mgr.setAuthenticatedSession(null) !== false) throw new Error("Allowed null session");
    if (mgr.setAuthenticatedSession({{}}) !== false) throw new Error("Allowed empty session");

    // 3. Reject non-canonical company UUIDs (malformed, whitespace-padded, short)
    const malformedCompIds = ["c-uuid-1", "not-a-uuid", validCompId.slice(0, 35), " " + validCompId, validCompId + " "];
    for (const badId of malformedCompIds) {{
      const badCompSession = {{
        company: {{ id: badId, code: "C1", name: "Corp" }},
        user: {{ id: validUserId, username: "u", role: "Administrator" }},
        branch: {{ id: validBranchId, code: "BR01" }}
      }};
      if (mgr.setAuthenticatedSession(badCompSession) !== false) throw new Error("Allowed company with bad UUID: " + badId);
      if (mgr.isAuthenticatedSession()) throw new Error("State authenticated after bad company UUID");
    }}

    // 4. Reject non-canonical user UUIDs
    const malformedUserIds = ["u-uuid-1", "12345", " " + validUserId];
    for (const badId of malformedUserIds) {{
      const badUserSession = {{
        company: {{ id: validCompId, code: "C1", name: "Corp" }},
        user: {{ id: badId, username: "u", role: "Administrator" }},
        branch: {{ id: validBranchId, code: "BR01" }}
      }};
      if (mgr.setAuthenticatedSession(badUserSession) !== false) throw new Error("Allowed user with bad UUID: " + badId);
      if (mgr.isAuthenticatedSession()) throw new Error("State authenticated after bad user UUID");
    }}

    // 5. Reject missing/empty user role
    const noRole = {{
      company: {{ id: validCompId, code: "C1", name: "Corp" }},
      user: {{ id: validUserId, username: "u", role: "" }},
      branch: {{ id: validBranchId, code: "BR01" }}
    }};
    if (mgr.setAuthenticatedSession(noRole) !== false) throw new Error("Allowed user with empty role");

    // 6. Reject non-canonical branch UUIDs
    const badBranchSession = {{
      company: {{ id: validCompId, code: "C1", name: "Corp" }},
      user: {{ id: validUserId, username: "u", role: "Administrator" }},
      branch: {{ id: "b-uuid-1", code: "BR01" }}
    }};
    if (mgr.setAuthenticatedSession(badBranchSession) !== false) throw new Error("Allowed branch with bad UUID");

    // 7. Reject missing branch entirely
    const noBranch = {{
      company: {{ id: validCompId, code: "C1", name: "Corp" }},
      user: {{ id: validUserId, username: "u", role: "Administrator" }}
    }};
    if (mgr.setAuthenticatedSession(noBranch) !== false) throw new Error("Allowed session with no branch");

    // 8. Accept complete valid session with dynamic canonical UUIDs
    const validSession = {{
      company: {{ id: validCompId, code: "C1", name: "Corp 1", finYear: "2026-2027" }},
      user: {{ id: validUserId, username: "alice", displayName: "Alice Admin", role: "Administrator" }},
      branch: {{ id: validBranchId, code: "BR01", name: "Main Branch" }}
    }};
    if (mgr.setAuthenticatedSession(validSession) !== true) throw new Error("Rejected valid session");
    if (mgr.getAuthState() !== "AUTHENTICATED") throw new Error("State did not become AUTHENTICATED");
    if (mgr.currentUser.id !== validUserId) throw new Error("User ID mismatch");
    if (mgr.currentUser.role !== "Administrator") throw new Error("Role mismatch");
    if (mgr.activeCompanyId !== validCompId) throw new Error("Company ID mismatch");
    if (mgr.activeBranchId !== validBranchId) throw new Error("Branch ID mismatch");

    // 9. Logout/clear
    mgr.clearAuthenticatedSession("logout");
    if (mgr.getAuthState() !== "UNAUTHENTICATED") throw new Error("State did not become UNAUTHENTICATED after clear");
    if (mgr.currentUser !== null) throw new Error("currentUser not cleared");
    if (mgr.activeCompanyId !== null) throw new Error("activeCompanyId not cleared");

    console.log("ALL_FRONTEND_CONTEXT_TESTS_PASSED");
    """
    res = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, check=True)
    assert "ALL_FRONTEND_CONTEXT_TESTS_PASSED" in res.stdout
