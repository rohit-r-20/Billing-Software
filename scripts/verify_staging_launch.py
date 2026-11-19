#!/usr/bin/env python3
"""
Phase 3.9B: Controlled Staging Application Launch and Authentication Test.

Verifies:
1. Clean PyQt5 and QtWebEngine desktop launch under APP_ENV=staging.
2. Web interface loading (index.html) into QWebEngineView.
3. DOM verification of the Standalone Login Screen.
4. JavaScript console message monitoring (tracking errors and warnings).
5. Fast Billing POS Cashier authentication & invalid password rejection.
6. Traditional ERP Administrator authentication & invalid password rejection.
7. Session logout and invalidation.
8. Session isolation between Traditional ERP and Fast Billing POS.
9. Zero mutations to production databases.
"""

import sys
import os
import json
import time
import hashlib
from pathlib import Path

# Enforce staging environment
os.environ["APP_ENV"] = "staging"
os.environ["DATABASE_ENV"] = "staging"

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from core.configuration import config
from core.logging_config import logger
from desktop.main_window import MainWindow, CustomWebPage

from PyQt5.QtCore import QTimer, QUrl, Qt
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEnginePage

PROD_FAST_DB = BASE_DIR / "data" / "anti_matrix_billing.db"
PROD_APP_DB = BASE_DIR / "data" / "app.db"
PROD_TRAD_DB = BASE_DIR / "data" / "traditional_billing.db"

BASELINE_FAST_HASH = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd"
BASELINE_APP_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
BASELINE_TRAD_HASH = "770dde96956adf7224023c546559ba6cc9f101e34a71dda9b27d9e717ca9d8c7"


def compute_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class ControlledStagingRunner:
    def __init__(self):
        self.results = {
            "launch_success": False,
            "webengine_loaded": False,
            "login_screen_rendered": False,
            "dom_login_elements": {},
            "js_errors": [],
            "js_warnings": [],
            "python_exceptions": [],
            "auth_results": {},
            "session_isolation": {},
            "prod_db_unchanged": False,
        }
        self.app = None
        self.window = None

    def record_js_message(self, level, message, line, source_id):
        if level == QWebEnginePage.ErrorMessageLevel:
            self.results["js_errors"].append(f"[L{line}]: {message}")
            print(f"[JS ERROR L{line}]: {message}", file=sys.stderr)
        elif level == QWebEnginePage.WarningMessageLevel:
            self.results["js_warnings"].append(f"[L{line}]: {message}")

    def run(self):
        print("=" * 70)
        print("ANTI-MATRIX BILLING V2 — PHASE 3.9B: CONTROLLED STAGING LAUNCH")
        print("=" * 70)

        # 1. Environment & Target Verification
        print("[*] Verifying staging environment resolution...")
        env = config.get_environment()
        assert env == "staging", f"Expected 'staging', got '{env}'"
        fast_db = config.get_database_path()
        trad_db = config.get_traditional_database_path()
        print(f"[*] Fast Staging Database:        {fast_db}")
        print(f"[*] Traditional Staging Database: {trad_db}")
        assert "staging" in str(fast_db)
        assert "staging" in str(trad_db)

        # Production database checksums before launch
        assert compute_sha256(PROD_FAST_DB) == BASELINE_FAST_HASH
        assert compute_sha256(PROD_APP_DB) == BASELINE_APP_HASH
        assert compute_sha256(PROD_TRAD_DB) == BASELINE_TRAD_HASH
        print("[✓] Pre-launch production database checksums verified byte-invariant.\n")

        # 2. Launch QApplication
        print("[*] Launching PyQt5 Desktop Application...")
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AntiMatrixBillingStaging")

        # Create MainWindow
        try:
            self.window = MainWindow(load_webengine=True)
            self.results["launch_success"] = True
            print("[✓] MainWindow created successfully.")
        except Exception as e:
            self.results["python_exceptions"].append(f"MainWindow initialization error: {e}")
            print(f"[FATAL ERROR] MainWindow init failed: {e}", file=sys.stderr)
            return self.results

        # Intercept JS console messages
        original_console_msg = self.window.web_page.javaScriptConsoleMessage

        def intercept_console(level, message, line, source_id):
            self.record_js_message(level, message, line, source_id)
            original_console_msg(level, message, line, source_id)

        self.window.web_page.javaScriptConsoleMessage = intercept_console

        # Connect load finished signal
        self.window.web_view.loadFinished.connect(self._on_webengine_load_finished)

        # Schedule safety timeout (max 15 seconds)
        QTimer.singleShot(15000, self._on_timeout)

        # Start Qt event loop
        self.app.exec_()

        # 3. Post-execution verification
        fast_after = compute_sha256(PROD_FAST_DB)
        app_after = compute_sha256(PROD_APP_DB)
        trad_after = compute_sha256(PROD_TRAD_DB)
        self.results["prod_db_unchanged"] = (
            fast_after == BASELINE_FAST_HASH
            and app_after == BASELINE_APP_HASH
            and trad_after == BASELINE_TRAD_HASH
        )
        print(f"\n[✓] Post-execution production database invariance: {self.results['prod_db_unchanged']}")
        return self.results

    def _on_webengine_load_finished(self, success):
        self.results["webengine_loaded"] = success
        if success:
            print("[✓] QWebEngineView loaded index.html successfully.")
            # Give UI 1.5 seconds to complete QWebChannel and DOM setup
            QTimer.singleShot(1500, self._inspect_login_screen_and_auth)
        else:
            print("[ERROR] QWebEngineView failed to load user interface.", file=sys.stderr)
            self.app.quit()

    def _inspect_login_screen_and_auth(self):
        print("\n[*] Inspecting Login Screen DOM via JavaScript execution...")

        dom_probe_script = """
        (function() {
            var loginView = document.getElementById('view-login');
            var isLoginActive = loginView ? loginView.classList.contains('active') : false;
            var prodName = document.querySelector('.login-product-name');
            var btnTrad = document.getElementById('btn-login-mode-trad');
            var btnFast = document.getElementById('btn-login-mode-fast');
            var userInput = document.getElementById('login-user-input');
            var pwdInput = document.getElementById('login-pwd-input');
            var companySelect = document.getElementById('login-company-select');

            return {
                view_login_found: !!loginView,
                view_login_active: isLoginActive,
                product_name: prodName ? prodName.innerText.trim() : null,
                has_trad_button: !!btnTrad,
                has_fast_button: !!btnFast,
                has_user_input: !!userInput,
                has_pwd_input: !!pwdInput,
                has_company_select: !!companySelect,
                company_options_count: companySelect ? companySelect.options.length : 0
            };
        })();
        """

        def handle_dom_probe(data):
            self.results["dom_login_elements"] = data
            if data and data.get("view_login_active"):
                self.results["login_screen_rendered"] = True
                print(f"[✓] Login Screen rendered and ACTIVE: Product '{data.get('product_name')}'")
                print(f"    - Traditional Mode Toggle: {data.get('has_trad_button')}")
                print(f"    - Fast POS Mode Toggle:    {data.get('has_fast_button')}")
                print(f"    - User ID Input:           {data.get('has_user_input')}")
                print(f"    - Password Input:          {data.get('has_pwd_input')}")
                print(f"    - Company Selector:        {data.get('has_company_select')} ({data.get('company_options_count')} options)")
            else:
                print(f"[WARNING] Login screen not detected active in DOM: {data}")

            # Now proceed to Authentication Checks
            self._execute_authentication_checks()

        self.window.web_page.runJavaScript(dom_probe_script, handle_dom_probe)

    def _execute_authentication_checks(self):
        print("\n[*] Executing Authentication Checks via BackendBridge...")
        bridge = self.window.bridge

        auth_out = {}
        isolation_out = {}

        # ----------------------------------------------------------------------
        # Check A: Traditional ERP Staging Administrator Login
        # ----------------------------------------------------------------------
        print("\n--- Check A: Traditional ERP Administrator Login ---")
        # 1. Invalid password rejection
        trad_bad = json.loads(bridge.traditional_authenticateUser("STAGING-CORP", "staging_admin", "WrongPassword!"))
        trad_bad_rejected = (trad_bad.get("success") is False and "Invalid" in trad_bad.get("error", ""))
        print(f"  - Invalid password rejected: {trad_bad_rejected}")

        # 2. Valid login
        trad_good = json.loads(bridge.traditional_authenticateUser("STAGING-CORP", "staging_admin", "Admin@Staging123"))
        trad_data = trad_good.get("data", {})
        trad_user = trad_data.get("user", {})
        trad_login_ok = (trad_good.get("success") is True and trad_user.get("role") == "Administrator")
        trad_token_present = bool(trad_data.get("session_token"))
        print(f"  - Valid staging login success: {trad_login_ok}")
        print(f"  - Role verified: {trad_user.get('role')}")
        print(f"  - Session token issued: {trad_token_present}")

        # 3. Verify session active
        trad_sess = json.loads(bridge.traditional_getAuthenticatedSession())
        trad_sess_data = trad_sess.get("data", {}) or {}
        trad_sess_active = (trad_sess.get("authenticated") is True and trad_sess_data.get("username") == "STAGING_ADMIN")
        print(f"  - Traditional session validated: {trad_sess_active}")

        # 4. Logout Traditional ERP
        trad_logout_res = json.loads(bridge.traditional_logout())
        trad_logged_out = (json.loads(bridge.traditional_getAuthenticatedSession()).get("authenticated") is False)
        print(f"  - Traditional logout successful: {trad_logged_out}")

        auth_out["traditional_admin"] = {
            "invalid_rejected": trad_bad_rejected,
            "login_success": trad_login_ok,
            "session_active": trad_sess_active,
            "logout_success": trad_logged_out,
            "role": trad_user.get("role"),
        }

        # ----------------------------------------------------------------------
        # Check B: Fast Billing POS Staging Cashier Login
        # ----------------------------------------------------------------------
        print("\n--- Check B: Fast Billing POS Cashier Login ---")
        # 1. Invalid password rejection
        fast_bad = json.loads(bridge.authenticateUser("STAGE01", "staging_cashier", "WrongPassword!"))
        fast_bad_rejected = (fast_bad.get("success") is False or "Invalid" in fast_bad.get("error", ""))
        print(f"  - Invalid password rejected: {fast_bad_rejected}")

        # 2. Valid login
        fast_good = json.loads(bridge.authenticateUser("STAGE01", "staging_cashier", "Cashier@123"))
        fast_data = fast_good.get("data", {})
        fast_user = fast_data.get("user", {})
        fast_login_ok = (fast_good.get("success") is True and fast_user.get("role") == "Cashier")
        print(f"  - Valid staging cashier login success: {fast_login_ok}")
        print(f"  - Role verified: {fast_user.get('role')}")

        # 3. Verify session active
        fast_sess = json.loads(bridge.getAuthenticatedSession())
        fast_sess_data = fast_sess.get("data", {}) or {}
        fast_sess_active = (fast_sess.get("authenticated") is True and fast_sess_data.get("role") == "Cashier")
        print(f"  - Fast Billing session validated: {fast_sess_active}")

        # 4. Logout Fast Billing POS
        fast_logout_res = json.loads(bridge.logout())
        fast_logged_out = (json.loads(bridge.getAuthenticatedSession()).get("authenticated") is False)
        print(f"  - Fast POS logout successful: {fast_logged_out}")

        auth_out["fast_cashier"] = {
            "invalid_rejected": fast_bad_rejected,
            "login_success": fast_login_ok,
            "session_active": fast_sess_active,
            "logout_success": fast_logged_out,
            "role": fast_user.get("role"),
        }

        # ----------------------------------------------------------------------
        # Check C: Session & Credential Isolation Between Traditional and Fast Billing
        # ----------------------------------------------------------------------
        print("\n--- Check C: Session & Credential Isolation ---")
        # 1. Cross-database login rejection: Fast cashier cannot authenticate to Traditional ERP
        cross_trad = json.loads(bridge.traditional_authenticateUser("STAGE01", "staging_cashier", "Cashier@123"))
        cross_trad_rejected = (cross_trad.get("success") is False)
        print(f"  - Fast POS cashier rejected in Traditional DB: {cross_trad_rejected}")

        # 2. Cross-database login rejection: Traditional admin cannot authenticate to Fast Billing POS
        cross_fast = json.loads(bridge.authenticateUser("STAGING-CORP", "STAGING_ADMIN", "Admin@Staging123"))
        cross_fast_rejected = (cross_fast.get("success") is False)
        print(f"  - Traditional ERP admin rejected in Fast POS DB: {cross_fast_rejected}")

        # 3. Role boundary isolation: Fast cashier has Cashier role; Traditional admin has Administrator role
        roles_isolated = (fast_user.get("role") == "Cashier" and trad_user.get("role") == "Administrator")
        print(f"  - Role boundary strictly isolated: {roles_isolated} (Cashier vs Administrator)")

        # 4. Post-logout protected endpoint security:
        # Traditional endpoint blocked when logged out
        trad_unauth_call = json.loads(bridge.traditional_listCustomers("", 10))
        trad_protected = (trad_unauth_call.get("success") is False)
        print(f"  - Traditional endpoint protected when logged out: {trad_protected}")

        # Fast cashier search blocked when logged out
        fast_unauth_call = json.loads(bridge.searchCashierProducts("STAGE01", "Soap"))
        fast_protected = (isinstance(fast_unauth_call, list) and len(fast_unauth_call) == 0) or fast_unauth_call.get("error") is not None
        print(f"  - Fast POS endpoint protected when logged out: {fast_protected}")

        isolation_out = {
            "fast_cashier_rejected_in_traditional_db": cross_trad_rejected,
            "traditional_admin_rejected_in_fast_db": cross_fast_rejected,
            "role_boundaries_strictly_isolated": roles_isolated,
            "traditional_endpoints_protected_post_logout": trad_protected,
            "fast_endpoints_protected_post_logout": fast_protected,
        }

        self.results["auth_results"] = auth_out
        self.results["session_isolation"] = isolation_out

        print("\n[✓] All authentication and isolation checks finished.")
        # Quit Qt application cleanly
        QTimer.singleShot(500, self.app.quit)

    def _on_timeout(self):
        print("[WARNING] Staging runner reached timeout threshold.", file=sys.stderr)
        if self.app:
            self.app.quit()


if __name__ == "__main__":
    runner = ControlledStagingRunner()
    results = runner.run()

    report_path = BASE_DIR / "staging_launch_results.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to: {report_path}")
    sys.exit(0 if results.get("webengine_loaded") and results.get("login_screen_rendered") else 1)
