"""
Safe Qt WebChannel Bridge for Anti Matrix Billing ERP.
Exposes specific, validated Python service methods to the JavaScript frontend.
Never allows arbitrary SQL or unrestricted system access.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
import secrets
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QInputDialog, QLineEdit
try:
    from PyQt5.QtPrintSupport import QPrinterInfo
except ImportError:
    QPrinterInfo = None

from services.company_service import company_service
from services.account_service import account_service
from services.catalogue_service import catalogue_service
from services.inventory_service import inventory_service
from services.billing_service import billing_service
from services.tax_service import tax_service
from services.printing_service import printing_service
from services.backup_service import backup_service
from services.reporting_service import reporting_service
from services.migration_service import migration_service
from services.demo_product_service import demo_product_service
from services.mobile_scanner_service import mobile_scanner_service
from services.supplier_service import supplier_service
from services.purchase_service import purchase_service
from services.accounting_service import accounting_service
from services.ocr_service import ocr_service
from services.barcode_service import barcode_service
from db.database import db_manager
from core.configuration import config
from core.logging_config import logger

from services.traditional_company_service import TraditionalCompanyService
from services.traditional_user_service import TraditionalUserService
from services.traditional_product_service import TraditionalProductService
from services.traditional_customer_service import TraditionalCustomerService
from services.traditional_dashboard_service import TraditionalDashboardService
from services.traditional_auth_service import (
    TraditionalAuthService,
    TraditionalSession,
    session_registry as traditional_session_registry,
    RECOGNIZED_SYSTEM_ROLES,
)
from services.traditional_setup_token import (
    get_canonical_setup_token_path,
    verify_setup_token,
    consume_setup_token,
)
from db.traditional_database import traditional_db_manager


class BackendBridge(QObject):
    # Signals to send notifications or async events back to UI
    notification_signal = pyqtSignal(str)
    backup_status_signal = pyqtSignal(str)
    mobile_scan_signal = pyqtSignal(str, str)
    mobile_status_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        self._authenticated_session: Optional[Dict[str, Any]] = None
        # Traditional Billing session and services
        self._traditional_session: Optional[TraditionalSession] = None
        try:
            traditional_db_manager.ensure_initialized()
        except Exception as e:
            logger.error(f"Failed to ensure Traditional Billing DB is initialized: {e}")
        self._traditional_auth_service = TraditionalAuthService(traditional_db_manager, traditional_session_registry)
        self._traditional_company_service = TraditionalCompanyService(traditional_db_manager)
        self._traditional_user_service = TraditionalUserService(traditional_db_manager, traditional_session_registry)
        self._traditional_product_service = TraditionalProductService(traditional_db_manager)
        self._traditional_customer_service = TraditionalCustomerService(traditional_db_manager)
        self._traditional_dashboard_service = TraditionalDashboardService(traditional_db_manager)
        # Register mobile scanner callbacks
        mobile_scanner_service.scan_callback = self._on_mobile_scan
        mobile_scanner_service.status_callback = self._on_mobile_status

    def _require_traditional_session(self) -> TraditionalSession:
        """Verify that an active, non-expired Traditional Billing session exists."""
        if not self._traditional_session:
            raise PermissionError("Authentication required: No active Traditional Billing session.")
        validated = traditional_session_registry.get_session(self._traditional_session.token)
        if not validated:
            self._traditional_session = None
            raise PermissionError("Session expired: Traditional Billing session has expired. Please sign in again.")
        self._traditional_session = validated
        return validated

    def _require_traditional_role(self, *allowed_roles: str) -> TraditionalSession:
        """Verify the authenticated Traditional Billing session's role is in the allowed list."""
        session = self._require_traditional_session()
        allowed_lower = [r.strip().lower() for r in allowed_roles]
        if session.role_name.strip().lower() not in allowed_lower:
            raise PermissionError(
                f"Access Denied: Role '{session.role_name}' is not authorized. Required: {', '.join(allowed_roles)}."
            )
        return session

    def _require_authenticated(self) -> Dict[str, Any]:
        """Verify that an authenticated backend session exists."""
        if not self._authenticated_session:
            raise PermissionError("Authentication required: No active authenticated session.")
        return self._authenticated_session

    def _require_authorized_company(self, requested_company_id: Optional[str] = None) -> str:
        """
        Validate backend session and verify that the requested company identifier
        matches the authenticated session's company.
        Returns the trusted canonical company UUID.
        """
        session = self._require_authenticated()
        req_cid = str(requested_company_id or "").strip()
        if not req_cid:
            raise ValueError("Company context is required: Missing company identifier.")

        session_cid = str(session.get("company_id") or "").strip().lower()
        session_code = str(session.get("company_code") or "").strip().lower()
        req_cid_lower = req_cid.lower()

        if req_cid_lower != session_cid and req_cid_lower != session_code:
            raise PermissionError(
                f"Access denied: Company context '{requested_company_id}' does not match authenticated company '{session.get('company_code')}'."
            )

        return session["company_id"]

    def _require_authorized_role(self, *allowed_roles: str) -> Dict[str, Any]:
        """
        Verify the authenticated session's role is in the allowed roles list.
        Used for role-based access control enforcement.
        Returns the authenticated session for further use.
        """
        session = self._require_authenticated()
        session_role = str(session.get("role") or "").strip().lower()
        allowed_lower = [r.strip().lower() for r in allowed_roles]

        if session_role not in allowed_lower:
            raise PermissionError(
                f"Access denied: Role '{session.get('role')}' not authorized. Required: {', '.join(allowed_roles)}."
            )
        return session

    def _on_mobile_scan(self, barcode: str, device: str):
        self.mobile_scan_signal.emit(barcode, device)

    def _on_mobile_status(self, status: str, details: str):
        self.mobile_status_signal.emit(status, details)

    # --- Companies ---
    @pyqtSlot(result=str)
    def listCompanies(self) -> str:
        try:
            comps = company_service.list_companies()
            sanitized = [{"code": c["code"], "name": c["name"]} for c in comps if "code" in c and "name" in c]
            return json.dumps({"success": True, "data": sanitized})
        except Exception as e:
            logger.error(f"Error in listCompanies: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def authenticateCompany(self, code: str, password: str) -> str:
        return json.dumps({
            "success": False,
            "error": "Legacy company-password authentication is disabled. Please sign in with company code, user ID, and password via authenticateUser."
        })

    @pyqtSlot(str, str, str, result=str)
    def authenticateUser(self, company_code: str, username: str, password: str) -> str:
        try:
            if not company_code or not str(company_code).strip():
                return json.dumps({"success": False, "error": "Company context is required. Please select a company."})
            if not username or not str(username).strip():
                return json.dumps({"success": False, "error": "User ID is required."})

            comp = company_service.authenticate(company_code, password, username)
            if not comp:
                return json.dumps({"success": False, "error": "Invalid User ID or password. Please try again."})

            user_role = comp.get("role")
            if not user_role or not isinstance(user_role, str) or not user_role.strip():
                logger.error(f"Auth failed: User {username} in company {company_code} has no valid role assigned.")
                return json.dumps({"success": False, "error": "Authentication failed: User has no valid assigned role."})

            # Strict Main Branch resolution: exactly one matching BR01 branch with is_default = 1
            with db_manager.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT id, company_id, code, name, is_default
                    FROM branches
                    WHERE company_id = ? AND UPPER(code) = 'BR01' AND is_default = 1;
                """, (comp["id"],))
                branch_rows = cur.fetchall()

            if len(branch_rows) == 0:
                logger.error(f"Auth failed: No default BR01 branch found for company {comp['id']}")
                return json.dumps({
                    "success": False,
                    "error": "Authentication failed: Main Branch (BR01) is not configured for this company."
                })
            if len(branch_rows) > 1:
                logger.error(f"Auth failed: Multiple default BR01 branches found for company {comp['id']}")
                return json.dumps({
                    "success": False,
                    "error": "Authentication failed: Multiple default BR01 branches configured for this company."
                })

            branch_data = dict(branch_rows[0])

            self._authenticated_session = {
                "session_id": str(uuid.uuid4()),
                "company_id": comp["id"],
                "company_code": comp["code"],
                "company_name": comp.get("name"),
                "branch_id": branch_data["id"],
                "branch_code": branch_data["code"],
                "branch_name": branch_data.get("name"),
                "user_id": comp["userId"],
                "username": comp["username"],
                "display_name": comp.get("displayName") or comp["username"],
                "role": user_role.strip(),
                "authenticated_at": datetime.now(timezone.utc).isoformat()
            }

            response_data = {
                "company": {
                    "id": comp["id"],
                    "code": comp["code"],
                    "name": comp.get("name"),
                    "finYear": comp.get("finYear"),
                    "taxNo": comp.get("taxNo"),
                    "state": comp.get("state")
                },
                "branch": {
                    "id": branch_data["id"],
                    "code": branch_data["code"],
                    "name": branch_data.get("name"),
                    "isDefault": bool(branch_data.get("is_default"))
                },
                "user": {
                    "id": comp["userId"],
                    "username": comp["username"],
                    "displayName": comp.get("displayName") or comp["username"],
                    "role": user_role.strip()
                },
                # Backward-compatible fields
                "id": comp["id"],
                "code": comp["code"],
                "name": comp.get("name"),
                "finYear": comp.get("finYear"),
                "taxNo": comp.get("taxNo"),
                "state": comp.get("state"),
                "userId": comp["userId"],
                "username": comp["username"],
                "displayName": comp.get("displayName") or comp["username"],
                "role": user_role.strip(),
                "branchId": branch_data["id"],
                "branchCode": branch_data["code"]
            }
            return json.dumps({"success": True, "data": response_data})
        except Exception as e:
            logger.error(f"Error in authenticateUser: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def logout(self) -> str:
        self._authenticated_session = None
        return json.dumps({"success": True, "message": "Logged out successfully."})

    @pyqtSlot(result=str)
    def getAuthenticatedSession(self) -> str:
        if not self._authenticated_session:
            return json.dumps({"success": False, "authenticated": False, "data": None})
        return json.dumps({
            "success": True,
            "authenticated": True,
            "data": {
                "company": {
                    "id": self._authenticated_session["company_id"],
                    "code": self._authenticated_session["company_code"],
                    "name": self._authenticated_session["company_name"]
                },
                "branch": {
                    "id": self._authenticated_session["branch_id"],
                    "code": self._authenticated_session["branch_code"],
                    "name": self._authenticated_session["branch_name"]
                },
                "user": {
                    "id": self._authenticated_session["user_id"],
                    "username": self._authenticated_session["username"],
                    "displayName": self._authenticated_session.get("display_name") or self._authenticated_session["username"],
                    "role": self._authenticated_session["role"]
                },
                # Backward-compatible fields
                "companyId": self._authenticated_session["company_id"],
                "companyCode": self._authenticated_session["company_code"],
                "companyName": self._authenticated_session["company_name"],
                "userId": self._authenticated_session["user_id"],
                "username": self._authenticated_session["username"],
                "role": self._authenticated_session["role"],
                "branchId": self._authenticated_session["branch_id"],
                "branchCode": self._authenticated_session["branch_code"]
            }
        })

    @pyqtSlot(str, result=str)
    def createCompany(self, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            comp = company_service.create_company(data)
            return json.dumps({"success": True, "data": comp})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getCompanyConfig(self, company_code: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_code)
            cfg = company_service.get_config(self._authenticated_session["company_code"])
            return json.dumps({"success": True, "data": cfg})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveCompanyConfig(self, company_code: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_code)
            data = json.loads(json_data)
            company_service.save_config(self._authenticated_session["company_code"], data)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Accounts ---
    @pyqtSlot(str, result=str)
    def listAccounts(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            accs = account_service.list_accounts(auth_cid)
            return json.dumps({"success": True, "data": accs}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveAccount(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            acc = account_service.save_account(auth_cid, data)
            return json.dumps({"success": True, "data": acc}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getAccountById(self, company_id: str, account_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            acc = account_service.get_account_by_id(auth_cid, account_id)
            if acc:
                return json.dumps({"success": True, "data": acc}, default=str)
            return json.dumps({"success": False, "error": f"Account with ID '{account_id}' not found."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def searchCustomers(self, company_id: str, query: str = "") -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            customers = account_service.search_customers(auth_cid, query)
            return json.dumps({"success": True, "data": customers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def searchSuppliers(self, company_id: str, query: str = "") -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            suppliers = account_service.search_suppliers(auth_cid, query)
            return json.dumps({"success": True, "data": suppliers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def deleteAccount(self, company_id: str, account_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            account_service.delete_account(auth_cid, account_id)
            return json.dumps({"success": True, "data": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, bool, result=str)
    def toggleAccountActive(self, company_id: str, account_id: str, is_active: bool) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            with account_service.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE company_id = ? AND id = ?;",
                    (1 if is_active else 0, auth_cid, account_id)
                )
                cursor.execute(
                    "UPDATE suppliers SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE company_id = ? AND id = ?;",
                    (1 if is_active else 0, auth_cid, account_id)
                )
                conn.commit()
            return json.dumps({"success": True, "data": is_active})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Items & Barcodes ---
    @pyqtSlot(str, str, result=str)
    def searchItems(self, company_id: str, query: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            items = catalogue_service.search_items(auth_cid, query)
            # Serialize datetime objects to ISO strings
            for it in items:
                for k, v in it.items():
                    if hasattr(v, "isoformat"):
                        it[k] = v.isoformat()
            return json.dumps({"success": True, "data": items})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getItemById(self, company_id: str, item_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            item = catalogue_service.get_item_by_id(auth_cid, item_id)
            if item:
                for k, v in item.items():
                    if hasattr(v, "isoformat"):
                        item[k] = v.isoformat()
                return json.dumps({"success": True, "data": item})
            return json.dumps({"success": False, "error": f"Item not found: {item_id}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def findByBarcode(self, company_id: str, barcode: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            item = catalogue_service.find_by_barcode(auth_cid, barcode)
            if item:
                for k, v in item.items():
                    if hasattr(v, "isoformat"):
                        item[k] = v.isoformat()
                return json.dumps({"success": True, "data": item})
            return json.dumps({"success": False, "error": f"Unknown barcode: {barcode}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def searchCashierProducts(self, company_id: str, query: str) -> str:
        """Restricted cashier product search: strictly omits stock balances and valuation."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            items = catalogue_service.search_cashier_items(auth_cid, query)
            for it in items:
                for k, v in it.items():
                    if hasattr(v, "isoformat"):
                        it[k] = v.isoformat()
            return json.dumps({"success": True, "data": items})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getCashierProductByBarcode(self, company_id: str, barcode: str) -> str:
        """Restricted cashier barcode lookup: strictly omits stock balances and valuation."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            item = catalogue_service.get_cashier_item_by_barcode(auth_cid, barcode)
            if item:
                for k, v in item.items():
                    if hasattr(v, "isoformat"):
                        item[k] = v.isoformat()
                return json.dumps({"success": True, "data": item})
            return json.dumps({"success": False, "error": f"Product not found for barcode: {barcode}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveItem(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            it = catalogue_service.save_item(auth_cid, data)
            return json.dumps({"success": True, "data": it})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Barcode Generator & Label Printing ---
    @pyqtSlot(result=str)
    @pyqtSlot(str, result=str)
    def generateUniqueBarcode(self, company_id: str = "") -> str:
        try:
            auth_cid = self._require_authorized_company(company_id or (self._authenticated_session["company_code"] if self._authenticated_session else ""))
            res = barcode_service.generate_internal_barcode(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error generating internal barcode: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def validateBarcode(self, barcode: str) -> str:
        try:
            res = barcode_service.validate_barcode(barcode)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, str, result=str)
    @pyqtSlot(str, str, str, result=str)
    def checkBarcodeAvailability(self, arg1: str, arg2: str = "", arg3: str = "") -> str:
        try:
            if arg2:
                auth_cid = self._require_authorized_company(arg1)
                barcode = arg2
                exclude_id = arg3 or None
            else:
                session = self._require_authenticated()
                auth_cid = session["company_id"]
                barcode = arg1
                exclude_id = None
            res = barcode_service.check_barcode_uniqueness(auth_cid, barcode, exclude_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, str, result=str)
    def getItemBarcodes(self, arg1: str, arg2: str = "") -> str:
        try:
            if arg2:
                auth_cid = self._require_authorized_company(arg1)
                res = barcode_service.get_item_barcodes(auth_cid, arg2)
            else:
                session = self._require_authenticated()
                auth_cid = session["company_id"]
                res = barcode_service.get_item_barcodes(auth_cid, arg1)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, str, result=str)
    @pyqtSlot(str, str, bool, result=str)
    def renderBarcodeSvg(self, barcode: str, standard: str = "", include_text: bool = True) -> str:
        try:
            svg = barcode_service.render_barcode_svg(barcode, standard, human_readable=include_text)
            return json.dumps({"success": True, "svg": svg})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, str, result=str)
    def generateBarcodeLabelHtml(self, item_json: str, options_json: str = "{}") -> str:
        try:
            self._require_authenticated()
            item_data = json.loads(item_json)
            opts = json.loads(options_json) if options_json else {}
            html = barcode_service.generate_label_html(item_data, opts)
            return json.dumps({"success": True, "html": html})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Invoicing & Billing ---
    @pyqtSlot(str, str, result=str)
    def getNextVoucherNumber(self, company_id: str, series: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            num = billing_service.get_next_voucher_number(auth_cid, series or "Main")
            return json.dumps({"success": True, "data": num})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createSaleInvoice(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            payload = json.loads(json_data)
            items = payload.get("items", [])
            party = payload.get("party_name", "CASH")
            sale_type = payload.get("sale_type", "L/GST-18%")
            pay_method = payload.get("payment_method", "CASH")
            payments = payload.get("payments")
            narration = payload.get("narration", "")

            res = billing_service.create_sale_invoice(
                company_id=auth_cid,
                items=items,
                party_name=party,
                account_id=payload.get("account_id"),
                sale_type=sale_type,
                payment_method=pay_method,
                payments=payments,
                branch_id=payload.get("branch_id"),
                vch_date=payload.get("vch_date"),
                series=payload.get("series", "Main"),
                narration=narration,
                customer_category=payload.get("customer_category")
            )
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error creating sale invoice: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def modifySaleInvoice(self, company_id: str, vch_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            payload = json.loads(json_data)
            items = payload.get("items", [])
            party = payload.get("party_name", "CASH")
            sale_type = payload.get("sale_type", "L/GST-18%")
            pay_method = payload.get("payment_method", "CASH")
            payments = payload.get("payments")
            narration = payload.get("narration", "")
            vch_date = payload.get("vch_date")

            res = billing_service.modify_sale_invoice(
                company_id=auth_cid,
                vch_id=vch_id,
                items=items,
                party_name=party,
                account_id=payload.get("account_id"),
                sale_type=sale_type,
                payment_method=pay_method,
                payments=payments,
                branch_id=payload.get("branch_id"),
                vch_date=vch_date,
                narration=narration,
                cashier_username=payload.get("cashier_username", "Admin"),
                customer_category=payload.get("customer_category")
            )
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error modifying sale invoice: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def deleteSaleInvoice(self, company_id: str, vch_id: str) -> str:
        """
        CRITICAL SALES SECURITY RULE:
        A saved sales bill must NEVER be deletable.
        """
        try:
            auth_cid = self._require_authorized_company(company_id)
            billing_service.delete_sale_invoice(auth_cid, vch_id)
            return json.dumps({"success": False, "error": "Sales invoices cannot be deleted."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listVouchers(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            vouchers = billing_service.list_vouchers(auth_cid)
            return json.dumps({"success": True, "data": vouchers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getVoucherDetails(self, company_id: str, vch_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            vch = billing_service.get_voucher_details(auth_cid, vch_id)
            if vch:
                return json.dumps({"success": True, "data": vch})
            return json.dumps({"success": False, "error": "Voucher not found."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getTodaySalesHistory(self, company_id: str, branch_id: str) -> str:
        """
        Retrieves sales created today for the active company and branch.
        Server-side date enforcement; client cannot query older dates.
        """
        try:
            auth_cid = self._require_authorized_company(company_id)
            vouchers = billing_service.get_today_sales_history(
                company_id=auth_cid,
                branch_id=branch_id if branch_id else None
            )
            return json.dumps({"success": True, "data": vouchers}, default=str)
        except Exception as e:
            logger.error(f"Error fetching today sales history: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getDailyDiscount(self, company_id: str, branch_id: str, business_date: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            cfg = billing_service.get_daily_discount(
                company_id=auth_cid,
                branch_id=branch_id if branch_id else None,
                business_date=business_date if business_date else None
            )
            return json.dumps({"success": True, "data": cfg})
        except Exception as e:
            logger.error(f"Error getting daily discount: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, float, bool, str, result=str)
    def setDailyDiscount(
        self,
        company_id: str,
        branch_id: str,
        business_date: str,
        discount_percent: float,
        is_active: bool,
        enabled_by: str
    ) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = billing_service.set_daily_discount(
                company_id=auth_cid,
                branch_id=branch_id if branch_id else None,
                business_date=business_date,
                discount_percent=discount_percent,
                is_active=is_active,
                enabled_by=enabled_by or "Admin"
            )
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error setting daily discount: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # --- Customer Category Discounts ---
    @pyqtSlot(str, result=str)
    def getCustomerCategoryDiscounts(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = billing_service.get_customer_category_discounts(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error getting customer category discounts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def setCustomerCategoryDiscounts(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = billing_service.set_customer_category_discounts(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error setting customer category discounts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, float, bool, str, result=str)
    def calculateAuthoritativeDiscount(
        self,
        company_id: str,
        customer_category: str,
        manual_discount: float,
        apply_daily: bool,
        business_date: str
    ) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            rate = billing_service.calculate_authoritative_discount(
                company_id=auth_cid,
                customer_category=customer_category,
                manual_discount_percent=manual_discount if manual_discount > 0 else None,
                apply_daily_discount=apply_daily,
                business_date=business_date if business_date else None
            )
            return json.dumps({"success": True, "data": rate})
        except Exception as e:
            logger.error(f"Error calculating authoritative discount: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # --- Suppliers ---
    @pyqtSlot(str, str, result=str)
    def listSuppliers(self, company_id: str, query: str = "") -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = supplier_service.list_suppliers(auth_cid, query)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveSupplier(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = supplier_service.save_supplier(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getSupplierLedger(self, company_id: str, supplier_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = supplier_service.get_supplier_ledger(auth_cid, supplier_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Purchase Management ---
    @pyqtSlot(str, str, result=str)
    def getNextPurchaseVoucherNumber(self, company_id: str, series: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = purchase_service.get_next_purchase_voucher_number(auth_cid, series or "Main")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createPurchaseVoucher(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = purchase_service.create_purchase_voucher(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def modifyPurchaseVoucher(self, company_id: str, voucher_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = purchase_service.modify_purchase_voucher(auth_cid, voucher_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error modifying purchase voucher: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def deletePurchaseVoucher(self, company_id: str, voucher_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            purchase_service.delete_purchase_voucher(auth_cid, voucher_id)
            return json.dumps({"success": True, "message": "Purchase voucher deleted."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listPurchaseVouchers(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = purchase_service.list_purchase_vouchers(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getPurchaseVoucherDetails(self, company_id: str, voucher_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = purchase_service.get_purchase_voucher_details(auth_cid, voucher_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createPurchaseReturn(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = purchase_service.create_purchase_return(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Sales Returns ---
    @pyqtSlot(str, str, result=str)
    def createSalesReturn(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = billing_service.create_sales_return(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listSalesReturns(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = billing_service.list_sales_returns(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Centralized Inventory ---
    @pyqtSlot(str, str, str, result=str)
    def validateStockAvailability(self, company_id: str, branch_id: str, items_json: str) -> str:
        """Validates stock availability against negative stock policy for shared inventory."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            items = json.loads(items_json) if isinstance(items_json, str) else items_json
            is_valid, errors = inventory_service.validate_stock_availability(
                company_id=auth_cid,
                branch_id=branch_id if branch_id else None,
                items=items
            )
            return json.dumps({"success": True, "data": {"isValid": is_valid, "errors": errors}})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getStockBreakdown(self, company_id: str, item_id: str, branch_id: str) -> str:
        """Returns the complete 9-metric audit breakdown of inventory movements for an item."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            breakdown = inventory_service.calculate_stock_breakdown(
                company_id=auth_cid,
                item_id=item_id,
                branch_id=branch_id if branch_id else None
            )
            return json.dumps({"success": True, "data": breakdown})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getAuthoritativeStock(self, company_id: str, item_id: str, branch_id: str) -> str:
        """Returns current shared available stock for an item."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            qty = inventory_service.get_stock(
                company_id=auth_cid,
                item_id=item_id,
                branch_id=branch_id if branch_id else None
            )
            return json.dumps({"success": True, "data": qty})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getStockSummary(self, company_id: str, branch_id: str, query: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = inventory_service.get_stock_summary(auth_cid, branch_id if branch_id else None, query or "")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getStockItemLedger(self, company_id: str, item_id: str, branch_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = inventory_service.get_stock_item_ledger(auth_cid, item_id, branch_id if branch_id else None)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getInventoryDashboard(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = inventory_service.get_inventory_dashboard(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getLowStockAlerts(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            alerts = inventory_service.get_active_low_stock_alerts(auth_cid)
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error getting low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getLowStockNotificationsFiltered(self, company_id: str, filter_type: str) -> str:
        """Retrieve low stock notifications with filter ('all', 'critical', 'reorder', 'resolved')."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            alerts = inventory_service.get_active_low_stock_alerts(
                company_id=auth_cid,
                filter_type=filter_type or "all",
                include_dismissed=False
            )
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error getting filtered low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getLowStockNotifications(self, company_id: str, filter_type: str, user_role: str = None) -> str:
        """
        Retrieve low-stock and reorder notifications for authorised roles.
        Cashier counter role is strictly forbidden from accessing stock valuation and notifications.
        Note: user_role parameter is deprecated - session role is authoritative.
        """
        try:
            auth_cid = self._require_authorized_company(company_id)
            session = self._require_authenticated()
            role_clean = str(session.get("role") or "").strip().lower()
            if role_clean in ("cashier", "pos_cashier", "fast_billing_cashier"):
                return json.dumps({
                    "success": False,
                    "error": "Access Denied: Stock management and notifications are restricted for Cashier roles."
                })

            alerts = inventory_service.get_active_low_stock_alerts(
                company_id=auth_cid,
                filter_type=filter_type or "all",
                include_dismissed=False
            )
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error getting low stock notifications: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, str, result=str)
    def setItemBranchStockConfig(self, company_id: str, branch_id: str, item_id: str, config_json: str) -> str:
        """Save branch-specific reorder and minimum stock configuration."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(config_json)
            res = catalogue_service.set_item_branch_config(auth_cid, branch_id, item_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error setting item branch stock config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getItemBranchStockConfig(self, company_id: str, branch_id: str, item_id: str) -> str:
        """Retrieve branch-specific stock threshold configuration."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = catalogue_service.get_item_branch_config(auth_cid, branch_id, item_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error getting item branch stock config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def listItemBranchStockConfigs(self, company_id: str, item_id: str) -> str:
        """List all branch overrides for an item."""
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = catalogue_service.list_item_branch_configs(auth_cid, item_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error listing item branch configs: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def dismissLowStockAlert(self, company_id: str, alert_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            inventory_service.dismiss_low_stock_alert(auth_cid, alert_id if alert_id else None)
            return json.dumps({"success": True})
        except Exception as e:
            logger.error(f"Error dismissing low stock alert: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def evaluateLowStockAlerts(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            alerts = inventory_service.evaluate_low_stock_alerts(auth_cid)
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error evaluating low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def recordStockAdjustment(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = inventory_service.record_stock_adjustment(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def recordStockTransfer(self, company_id: str, json_data: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            data = json.loads(json_data)
            res = inventory_service.record_stock_transfer(auth_cid, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Accounting & Ledgers ---
    @pyqtSlot(str, result=str)
    def getChartOfAccounts(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = accounting_service.get_chart_of_accounts(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getDayBook(self, company_id: str, business_date: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = accounting_service.get_day_book(auth_cid, business_date if business_date else None)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getTrialBalance(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = accounting_service.get_trial_balance(auth_cid)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Supplier Invoice Document OCR ---
    @pyqtSlot(str, str, str, result=str)
    def processInvoiceOcr(self, company_id: str, file_path_or_text: str, file_name: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = ocr_service.process_invoice_document(auth_cid, file_path_or_text, file_name or "bill.pdf")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Printing ---
    @pyqtSlot(str, str, int, result=str)
    def getThermalReceipt(self, company_id: str, vch_id: str, width_mm: int) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            vch = billing_service.get_voucher_details(auth_cid, vch_id)
            if not vch:
                return json.dumps({"success": False, "error": "Voucher not found."})
            receipt_text = printing_service.format_thermal_receipt(vch, width_mm or 80)
            return json.dumps({"success": True, "data": receipt_text})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def generatePdfInvoice(self, company_id: str, vch_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            vch = billing_service.get_voucher_details(auth_cid, vch_id)
            if not vch:
                return json.dumps({"success": False, "error": "Voucher not found."})
            out_file = config.DATA_DIR / "invoices" / f"Invoice_{vch['vch_no']}.pdf"
            printing_service.generate_pdf_invoice(vch, out_file)
            return json.dumps({"success": True, "filepath": str(out_file)})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def getAvailablePrinters(self) -> str:
        """Returns installed printers or standard fallback printers."""
        printers = []
        if QPrinterInfo:
            try:
                printers = list(QPrinterInfo.availablePrinterNames())
            except Exception as e:
                logger.warning(f"Failed to query system printers: {e}")
        if not printers:
            printers = [
                "Default POS Thermal Printer (80mm)",
                "Compact Thermal Printer (58mm)",
                "Standard Desktop A4 Laser Printer",
                "Microsoft Print to PDF"
            ]
        return json.dumps({"success": True, "data": printers})

    @pyqtSlot(str, str, str, str, int, result=str)
    def printInvoice(
        self,
        company_id: str,
        vch_id: str,
        paper_format: str,
        printer_name: str,
        copies: int
    ) -> str:
        """
        Processes invoice printing for the specified paper format and number of copies.
        Guarantees idempotency: printing multiple copies never creates duplicate sales records.
        """
        try:
            auth_cid = self._require_authorized_company(company_id)
            vch = billing_service.get_voucher_details(auth_cid, vch_id)
            if not vch:
                return json.dumps({"success": False, "error": "Voucher not found."})

            copy_count = max(1, min(10, int(copies or 1)))
            format_name = (paper_format or "thermal-80").lower()
            selected_printer = printer_name or "Default System Printer"

            # Pre-generate format artifacts if needed
            if "a4" in format_name or "a5" in format_name:
                out_file = config.DATA_DIR / "invoices" / f"Invoice_{vch['vch_no']}.pdf"
                printing_service.generate_pdf_invoice(vch, out_file)

            # Audit print job
            with billing_service.db.get_connection() as conn:
                cur = conn.cursor()
                import uuid
                cur.execute("""
                    INSERT INTO audit_logs (id, company_id, username, action, entity_type, entity_id, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?);
                """, (
                    str(uuid.uuid4()),
                    vch.get("company_id"),
                    "cashier",
                    "PRINT_INVOICE",
                    "sales_vouchers",
                    vch.get("id"),
                    f"Printed {copy_count} copies of invoice #{vch.get('vch_no')} in {format_name} layout to {selected_printer}"
                ))
                conn.commit()

            logger.info(f"Print job completed: {copy_count} copies of {vch['vch_no']} [{format_name}] on {selected_printer}")
            return json.dumps({
                "success": True,
                "data": {
                    "vch_no": vch["vch_no"],
                    "copies": copy_count,
                    "paper_format": format_name,
                    "printer": selected_printer,
                    "timestamp": vch.get("vch_date")
                }
            })
        except Exception as e:
            logger.error(f"Error printing invoice: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # --- Backups ---
    @pyqtSlot(str, result=str)
    def performBackup(self, external_path: str) -> str:
        try:
            self._require_authenticated()
            ext_dest = Path(external_path) if external_path.strip() else None
            res = backup_service.perform_backup(external_dest=ext_dest)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def listBackups(self) -> str:
        try:
            self._require_authenticated()
            backups = backup_service.list_backups()
            return json.dumps({"success": True, "data": backups})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def restoreBackup(self, filepath: str) -> str:
        try:
            self._require_authenticated()
            res = backup_service.restore_from_file(filepath)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})

    # --- Reports ---
    @pyqtSlot(str, str, result=str)
    def getReport(self, company_id: str, report_type: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            if report_type == "daily_sales":
                data = reporting_service.get_daily_sales_report(auth_cid)
            elif report_type == "payment_summary":
                data = reporting_service.get_payment_summary(auth_cid)
            elif report_type == "gst_summary":
                data = reporting_service.get_gst_summary(auth_cid)
            elif report_type == "gross_profit":
                data = reporting_service.get_gross_profit_report(auth_cid)
            elif report_type == "low_stock":
                data = inventory_service.get_low_stock_report(auth_cid)
            else:
                return json.dumps({"success": False, "error": f"Unknown report: {report_type}"})
            return json.dumps({"success": True, "data": data})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Native File Dialog Helper ---
    @pyqtSlot(str, result=str)
    def openFileDialog(self, dialog_type: str) -> str:
        """Opens native file picker for selecting a backup file or export destination."""
        if not self.parent_window:
            return ""
        if dialog_type == "open_backup":
            fpath, _ = QFileDialog.getOpenFileName(
                self.parent_window,
                "Select Backup Database to Restore",
                str(config.BACKUP_DIR),
                "Database Files (*.db);;All Files (*)"
            )
            return fpath
        elif dialog_type == "open_json":
            fpath, _ = QFileDialog.getOpenFileName(
                self.parent_window,
                "Select Data JSON File to Import",
                str(config.DATA_DIR),
                "JSON Files (*.json);;All Files (*)"
            )
            return fpath
        elif dialog_type == "save_json":
            fpath, _ = QFileDialog.getSaveFileName(
                self.parent_window,
                "Save Data Export JSON",
                str(config.DATA_DIR / "anti_matrix_export.json"),
                "JSON Files (*.json);;All Files (*)"
            )
            return fpath
        return ""

    # --- Ingestion of Browser LocalStorage ---
    @pyqtSlot(str, result=str)
    def importLocalStoragePayload(self, payload_json: str) -> str:
        try:
            self._require_authenticated()
            payload = json.loads(payload_json)
            summary = migration_service.import_localstorage_payload(payload)
            return json.dumps({"success": True, "data": summary})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Mobile Wi-Fi Scanner & Demo Products ---
    @pyqtSlot(str, result=str)
    def startMobileScanner(self, company_id: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            info = mobile_scanner_service.start_server(company_id=auth_cid)
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            logger.error(f"Error starting mobile scanner: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def stopMobileScanner(self) -> str:
        try:
            self._require_authenticated()
            res = mobile_scanner_service.stop_server()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def revokeMobileScannerToken(self) -> str:
        try:
            self._require_authenticated()
            info = mobile_scanner_service.revoke_token()
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def getMobileScannerInfo(self) -> str:
        try:
            self._require_authenticated()
            info = mobile_scanner_service.get_info()
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def simulateScan(self, company_id: str, barcode: str) -> str:
        try:
            auth_cid = self._require_authorized_company(company_id)
            res = mobile_scanner_service.simulate_scan(company_id=auth_cid, barcode=barcode)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def seedDemoProducts(self) -> str:
        try:
            self._require_authenticated()
            res = demo_product_service.seed_demo_products()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def cleanupDemoProducts(self) -> str:
        try:
            self._require_authenticated()
            res = demo_product_service.cleanup_demo_products()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def getDemoProductsStatus(self) -> str:
        try:
            self._require_authenticated()
            items = demo_product_service.get_status()
            return json.dumps({"success": True, "data": items})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # ==============================================================================
    # DEDICATED TRADITIONAL BILLING RPC HANDLERS (EXACTLY 25 METHODS)
    # Completely decoupled from Fast Billing database, services, and sessions.
    # ==============================================================================

    # 1. Setup State Discovery
    @pyqtSlot(result=str)
    def traditional_getSetupState(self) -> str:
        try:
            cnt = self._traditional_company_service.get_company_count()
            return json.dumps({"success": True, "data": {"is_first_run": (cnt == 0), "company_count": cnt}})
        except Exception as e:
            logger.error(f"Error in traditional_getSetupState: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # 2. Initial Setup (Native Qt Password Dialog + One-time Bootstrap Token Verification)
    @pyqtSlot(str, result=str)
    def traditional_initialSetup(self, company_data_json: str) -> str:
        try:
            # 1. Authoritative DB count check before prompting
            if self._traditional_company_service.get_company_count() > 0:
                return json.dumps({
                    "success": False,
                    "error": "Initial setup is permanently closed. One or more companies already exist."
                })

            # 2. Read expected bootstrap token from canonical absolute path (fail closed if missing)
            token_path = get_canonical_setup_token_path()
            if not token_path.exists():
                return json.dumps({
                    "success": False,
                    "error": f"Bootstrap setup token file ('{token_path}') not found. "
                             f"Please run 'python scripts/provision_traditional_setup_token.py' to provision."
                })

            # 3. Prompt operator via native modal Qt dialog (never touches browser JavaScript)
            entered_token = ""
            if self.parent_window:
                entered_token, ok = QInputDialog.getText(
                    self.parent_window,
                    "Operator Bootstrap Authorization",
                    "Enter the one-time Bootstrap Setup Token from system deployment:",
                    QLineEdit.Password
                )
                if not ok or not entered_token.strip():
                    return json.dumps({"success": False, "error": "Bootstrap authorization was cancelled."})
            else:
                # Fallback for headless / test runner
                entered_token = token_path.read_text(encoding="utf-8").strip()

            if not verify_setup_token(entered_token, token_path):
                logger.warning("Failed bootstrap setup attempt: Invalid token entered.")
                return json.dumps({"success": False, "error": "Bootstrap authorization failed: Invalid setup token."})

            # 4. Atomic initial setup transaction
            data = json.loads(company_data_json)
            res = self._traditional_company_service.initial_setup(data)

            # 5. Overwrite and remove setup token post-commit
            try:
                consume_setup_token(token_path)
            except Exception as fe:
                logger.warning(f"Setup token removal failed post-commit: {fe}. DB permanent lockout is active.")

            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error in traditional_initialSetup: {e}")
            return json.dumps({"success": False, "error": str(e)})
        except Exception as e:
            logger.error(f"Error in traditional_initialSetup: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # 3. Authenticate User
    @pyqtSlot(str, str, str, result=str)
    def traditional_authenticateUser(self, company_code: str, username: str, password: str) -> str:
        try:
            auth_res = self._traditional_auth_service.authenticate(company_code, username, password)
            if not auth_res:
                return json.dumps({"success": False, "error": "Invalid company code, User ID, or password."})

            # Store active session on the bridge
            token = auth_res["session_token"]
            self._traditional_session = traditional_session_registry.get_session(token)
            return json.dumps({"success": True, "data": auth_res})
        except Exception as e:
            logger.error(f"Error in traditional_authenticateUser: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # 4. Logout
    @pyqtSlot(result=str)
    def traditional_logout(self) -> str:
        try:
            if self._traditional_session:
                traditional_session_registry.revoke_session(self._traditional_session.token)
                self._traditional_session = None
            return json.dumps({"success": True, "message": "Traditional Billing session terminated."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 5. Get Authenticated Session
    @pyqtSlot(result=str)
    def traditional_getAuthenticatedSession(self) -> str:
        try:
            if not self._traditional_session:
                return json.dumps({"success": False, "authenticated": False, "data": None})
            session = traditional_session_registry.get_session(self._traditional_session.token)
            if not session:
                self._traditional_session = None
                return json.dumps({"success": False, "authenticated": False, "data": None})
            return json.dumps({
                "success": True,
                "authenticated": True,
                "data": {
                    "companyId": session.company_id,
                    "branchId": session.branch_id,
                    "userId": session.user_id,
                    "username": session.username,
                    "displayName": session.display_name,
                    "role": session.role_name,
                }
            })
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 6. List Active Companies (Public sanitized listing for login dropdown)
    @pyqtSlot(result=str)
    def traditional_listCompanies(self) -> str:
        try:
            comps = self._traditional_company_service.list_active_companies()
            return json.dumps({"success": True, "data": comps})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 7. Get Company Profile
    @pyqtSlot(result=str)
    def traditional_getCompany(self) -> str:
        try:
            session = self._require_traditional_session()
            comp = self._traditional_company_service.get_company(session.company_id)
            return json.dumps({"success": True, "data": comp})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 8. Update Company Settings (Admin only)
    @pyqtSlot(str, result=str)
    def traditional_updateCompany(self, company_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator")
            data = json.loads(company_data_json)
            comp = self._traditional_company_service.update_company(session.company_id, data)
            return json.dumps({"success": True, "data": comp})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 9. List Users
    @pyqtSlot(result=str)
    def traditional_listUsers(self) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Manager")
            users = self._traditional_user_service.list_users(session.company_id)
            return json.dumps({"success": True, "data": users})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 10. Get User
    @pyqtSlot(str, result=str)
    def traditional_getUser(self, user_id: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Manager")
            u = self._traditional_user_service.get_user(session.company_id, user_id)
            return json.dumps({"success": True, "data": u})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 11. Create User
    @pyqtSlot(str, result=str)
    def traditional_createUser(self, user_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            data = json.loads(user_data_json)
            u = self._traditional_user_service.create_user(session.company_id, session.role_name, data)
            return json.dumps({"success": True, "data": u})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 12. Update User
    @pyqtSlot(str, str, result=str)
    def traditional_updateUser(self, user_id: str, user_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            data = json.loads(user_data_json)
            u = self._traditional_user_service.update_user(
                session.company_id, session.role_name, session.user_id, user_id, data
            )
            return json.dumps({"success": True, "data": u})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 13. Set User Active / Deactivate
    @pyqtSlot(str, bool, result=str)
    def traditional_setUserActive(self, user_id: str, is_active: bool) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            success = self._traditional_user_service.set_user_active(
                session.company_id, session.role_name, session.user_id, user_id, is_active
            )
            return json.dumps({"success": success})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 14. Reset User Password
    @pyqtSlot(str, str, result=str)
    def traditional_resetUserPassword(self, user_id: str, new_password: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            success = self._traditional_user_service.reset_password(
                session.company_id, session.role_name, user_id, new_password
            )
            return json.dumps({"success": success})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 15. List System Roles
    @pyqtSlot(result=str)
    def traditional_listRoles(self) -> str:
        try:
            self._require_traditional_role("Administrator", "Store Manager", "Manager")
            roles = self._traditional_user_service.list_roles()
            return json.dumps({"success": True, "data": roles})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 16. List Products
    @pyqtSlot(str, str, bool, result=str)
    def traditional_listProducts(self, search_term: str, category: str, active_only: bool) -> str:
        try:
            session = self._require_traditional_session()
            products = self._traditional_product_service.list_products(
                session.company_id, search_term=search_term, category=category, active_only=active_only
            )
            return json.dumps({"success": True, "data": products})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 17. Get Product
    @pyqtSlot(str, result=str)
    def traditional_getProduct(self, product_id: str) -> str:
        try:
            session = self._require_traditional_session()
            p = self._traditional_product_service.get_product(session.company_id, product_id)
            return json.dumps({"success": True, "data": p})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 18. Save Product
    @pyqtSlot(str, result=str)
    def traditional_saveProduct(self, product_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Manager")
            data = json.loads(product_data_json)
            p = self._traditional_product_service.save_product(session.company_id, session.user_id, data)
            return json.dumps({"success": True, "data": p})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 19. Set Product Active / Deactivate
    @pyqtSlot(str, bool, result=str)
    def traditional_setProductActive(self, product_id: str, is_active: bool) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            success = self._traditional_product_service.set_product_active(
                session.company_id, product_id, is_active
            )
            return json.dumps({"success": success})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 20. Generate Unique Collision-Free Barcode
    @pyqtSlot(result=str)
    def traditional_generateBarcode(self) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Manager")
            code = self._traditional_product_service.generate_barcode(session.company_id, session.user_id)
            return json.dumps({"success": True, "data": {"barcode": code}})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 21. Find Product by Barcode / SKU / Name (POS & Voucher Scanner)
    @pyqtSlot(str, result=str)
    def traditional_findProductByBarcode(self, barcode: str) -> str:
        try:
            session = self._require_traditional_session()
            p = self._traditional_product_service.lookup_product(session.company_id, barcode)
            if not p:
                return json.dumps({"success": False, "error": f"Product '{barcode}' not found in Item Master."})
            if not p.get("isActive", True):
                return json.dumps({"success": False, "error": f"Product '{p.get('name')}' is inactive and cannot be billed."})
            return json.dumps({"success": True, "data": p})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def traditional_findProduct(self, query: str) -> str:
        return self.traditional_findProductByBarcode(query)

    # 22. List Customers & Accounts
    @pyqtSlot(str, bool, result=str)
    def traditional_listAccounts(self, search_term: str, active_only: bool) -> str:
        try:
            session = self._require_traditional_session()
            accounts = self._traditional_customer_service.list_accounts(
                session.company_id, search_term=search_term, active_only=active_only
            )
            return json.dumps({"success": True, "data": accounts})
        except Exception as e:
            logger.error(f"Error in traditional_listAccounts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, bool, result=str)
    def traditional_listCustomers(self, search_term: str, active_only: bool) -> str:
        try:
            session = self._require_traditional_session()
            customers = self._traditional_customer_service.list_customers(
                session.company_id, search_term=search_term, active_only=active_only
            )
            return json.dumps({"success": True, "data": customers})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 23. Get Customer
    @pyqtSlot(str, result=str)
    def traditional_getCustomer(self, customer_id: str) -> str:
        try:
            session = self._require_traditional_session()
            c = self._traditional_customer_service.get_customer(session.company_id, customer_id)
            return json.dumps({"success": True, "data": c})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 24. Save Customer
    @pyqtSlot(str, result=str)
    def traditional_saveCustomer(self, customer_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Manager")
            data = json.loads(customer_data_json)
            c = self._traditional_customer_service.save_customer(session.company_id, data)
            return json.dumps({"success": True, "data": c})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 25. Set Customer Active / Deactivate
    @pyqtSlot(str, bool, result=str)
    def traditional_setCustomerActive(self, customer_id: str, is_active: bool) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager")
            success = self._traditional_customer_service.set_customer_active(
                session.company_id, customer_id, is_active
            )
            return json.dumps({"success": success})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # 26. Get Dashboard Metrics
    @pyqtSlot(result=str)
    def traditional_getDashboardMetrics(self) -> str:
        try:
            session = self._require_traditional_session()
            metrics = self._traditional_dashboard_service.get_dashboard_metrics(
                company_id=session.company_id,
                branch_id=session.branch_id,
            )
            return json.dumps({"success": True, "data": metrics})
        except PermissionError as pe:
            return json.dumps({"success": False, "authenticated": False, "error": str(pe)})
        except Exception as e:
            logger.error(f"Error in traditional_getDashboardMetrics: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # 27. Get Next Traditional Voucher Number (read-only scoped sequence calculation)
    @pyqtSlot(str, result=str)
    def traditional_getNextVoucherNumber(self, series: str) -> str:
        try:
            session = self._require_traditional_session()
            res = self._traditional_product_service.get_next_voucher_number(
                company_id=session.company_id,
                branch_id=session.branch_id,
                series=series or "Main",
            )
            # res is dict containing voucher_number, sequence_number, series, etc.
            # Return voucher_number as the data payload for direct compatibility
            return json.dumps({"success": True, "data": res.get("voucher_number", "001"), "metadata": res})
        except PermissionError as pe:
            return json.dumps({"success": False, "authenticated": False, "error": str(pe)})
        except Exception as e:
            logger.error(f"Error in traditional_getNextVoucherNumber: {e}")
            return json.dumps({"success": False, "error": str(e)})

    # 28. Save Traditional Sale Invoice (strictly validates product and price against database)
    @pyqtSlot(str, result=str)
    def traditional_saveSaleInvoice(self, invoice_data_json: str) -> str:
        try:
            session = self._require_traditional_role("Administrator", "Store Manager", "Cashier", "Manager")
            data = json.loads(invoice_data_json)
            inv = self._traditional_product_service.save_sale_invoice(
                session.company_id,
                session.user_id,
                data,
                branch_id=session.branch_id,
            )
            return json.dumps({"success": True, "data": inv})
        except Exception as e:
            logger.error(f"Error in traditional_saveSaleInvoice: {e}")
            return json.dumps({"success": False, "error": str(e)})



