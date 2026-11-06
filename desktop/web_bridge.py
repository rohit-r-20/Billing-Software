"""
Safe Qt WebChannel Bridge for Anti Matrix Billing ERP.
Exposes specific, validated Python service methods to the JavaScript frontend.
Never allows arbitrary SQL or unrestricted system access.
"""
import json
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QFileDialog
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
from core.configuration import config
from core.logging_config import logger


class BackendBridge(QObject):
    # Signals to send notifications or async events back to UI
    notification_signal = pyqtSignal(str)
    backup_status_signal = pyqtSignal(str)
    mobile_scan_signal = pyqtSignal(str, str)
    mobile_status_signal = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent
        # Register mobile scanner callbacks
        mobile_scanner_service.scan_callback = self._on_mobile_scan
        mobile_scanner_service.status_callback = self._on_mobile_status

    def _on_mobile_scan(self, barcode: str, device: str):
        self.mobile_scan_signal.emit(barcode, device)

    def _on_mobile_status(self, status: str, details: str):
        self.mobile_status_signal.emit(status, details)

    # --- Companies ---
    @pyqtSlot(result=str)
    def listCompanies(self) -> str:
        try:
            comps = company_service.list_companies()
            return json.dumps({"success": True, "data": comps})
        except Exception as e:
            logger.error(f"Error in listCompanies: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def authenticateCompany(self, code: str, password: str) -> str:
        try:
            comp = company_service.authenticate(code, password)
            if comp:
                return json.dumps({"success": True, "data": comp})
            return json.dumps({"success": False, "error": "Invalid username or password."})
        except Exception as e:
            logger.error(f"Error in authenticateCompany: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def authenticateUser(self, company_code: str, username: str, password: str) -> str:
        try:
            comp = company_service.authenticate(company_code or username, password, username)
            if comp:
                return json.dumps({"success": True, "data": comp})
            return json.dumps({"success": False, "error": "Invalid User ID or password. Please try again."})
        except Exception as e:
            logger.error(f"Error in authenticateUser: {e}")
            return json.dumps({"success": False, "error": str(e)})

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
            cfg = company_service.get_config(company_code)
            return json.dumps({"success": True, "data": cfg})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveCompanyConfig(self, company_code: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            company_service.save_config(company_code, data)
            return json.dumps({"success": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Accounts ---
    @pyqtSlot(str, result=str)
    def listAccounts(self, company_id: str) -> str:
        try:
            accs = account_service.list_accounts(company_id)
            return json.dumps({"success": True, "data": accs}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveAccount(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            acc = account_service.save_account(company_id, data)
            return json.dumps({"success": True, "data": acc}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getAccountById(self, company_id: str, account_id: str) -> str:
        try:
            acc = account_service.get_account_by_id(company_id, account_id)
            if acc:
                return json.dumps({"success": True, "data": acc}, default=str)
            return json.dumps({"success": False, "error": f"Account with ID '{account_id}' not found."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def searchCustomers(self, company_id: str, query: str = "") -> str:
        try:
            customers = account_service.search_customers(company_id, query)
            return json.dumps({"success": True, "data": customers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def searchSuppliers(self, company_id: str, query: str = "") -> str:
        try:
            suppliers = account_service.search_suppliers(company_id, query)
            return json.dumps({"success": True, "data": suppliers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def deleteAccount(self, company_id: str, account_id: str) -> str:
        try:
            account_service.delete_account(company_id, account_id)
            return json.dumps({"success": True, "data": True})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, bool, result=str)
    def toggleAccountActive(self, company_id: str, account_id: str, is_active: bool) -> str:
        try:
            with account_service.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE accounts SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE company_id = ? AND id = ?;",
                    (1 if is_active else 0, company_id, account_id)
                )
                cursor.execute(
                    "UPDATE suppliers SET is_active = ?, updated_at = CURRENT_TIMESTAMP WHERE company_id = ? AND id = ?;",
                    (1 if is_active else 0, company_id, account_id)
                )
                conn.commit()
            return json.dumps({"success": True, "data": is_active})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Items & Barcodes ---
    @pyqtSlot(str, str, result=str)
    def searchItems(self, company_id: str, query: str) -> str:
        try:
            items = catalogue_service.search_items(company_id, query)
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
            item = catalogue_service.get_item_by_id(company_id, item_id)
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
            item = catalogue_service.find_by_barcode(company_id, barcode)
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
            items = catalogue_service.search_cashier_items(company_id, query)
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
            item = catalogue_service.get_cashier_item_by_barcode(company_id, barcode)
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
            data = json.loads(json_data)
            it = catalogue_service.save_item(company_id, data)
            return json.dumps({"success": True, "data": it})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Barcode Generator & Label Printing ---
    @pyqtSlot(result=str)
    @pyqtSlot(str, result=str)
    def generateUniqueBarcode(self, company_id: str = "") -> str:
        try:
            res = barcode_service.generate_internal_barcode(company_id or None)
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
                # Called as (company_id, barcode, exclude_item_id)
                comp_id = arg1
                barcode = arg2
                exclude_id = arg3 or None
            else:
                # Called as (barcode)
                comp_id = None
                barcode = arg1
                exclude_id = None
            res = barcode_service.check_barcode_uniqueness(comp_id, barcode, exclude_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    @pyqtSlot(str, str, result=str)
    def getItemBarcodes(self, arg1: str, arg2: str = "") -> str:
        try:
            if arg2:
                res = barcode_service.get_item_barcodes(arg1, arg2)
            else:
                res = barcode_service.get_item_barcodes(arg1)
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
            num = billing_service.get_next_voucher_number(company_id, series or "Main")
            return json.dumps({"success": True, "data": num})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createSaleInvoice(self, company_id: str, json_data: str) -> str:
        try:
            payload = json.loads(json_data)
            items = payload.get("items", [])
            party = payload.get("party_name", "CASH")
            sale_type = payload.get("sale_type", "L/GST-18%")
            pay_method = payload.get("payment_method", "CASH")
            payments = payload.get("payments")
            narration = payload.get("narration", "")

            res = billing_service.create_sale_invoice(
                company_id=company_id,
                items=items,
                party_name=party,
                account_id=payload.get("account_id"),
                sale_type=sale_type,
                payment_method=pay_method,
                payments=payments,
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
            payload = json.loads(json_data)
            items = payload.get("items", [])
            party = payload.get("party_name", "CASH")
            sale_type = payload.get("sale_type", "L/GST-18%")
            pay_method = payload.get("payment_method", "CASH")
            payments = payload.get("payments")
            narration = payload.get("narration", "")
            vch_date = payload.get("vch_date")

            res = billing_service.modify_sale_invoice(
                company_id=company_id,
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
            billing_service.delete_sale_invoice(company_id, vch_id)
            return json.dumps({"success": False, "error": "Sales invoices cannot be deleted."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listVouchers(self, company_id: str) -> str:
        try:
            vouchers = billing_service.list_vouchers(company_id)
            return json.dumps({"success": True, "data": vouchers}, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getVoucherDetails(self, company_id: str, vch_id: str) -> str:
        try:
            vch = billing_service.get_voucher_details(company_id, vch_id)
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
            vouchers = billing_service.get_today_sales_history(
                company_id=company_id,
                branch_id=branch_id if branch_id else None
            )
            return json.dumps({"success": True, "data": vouchers}, default=str)
        except Exception as e:
            logger.error(f"Error fetching today sales history: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getDailyDiscount(self, company_id: str, branch_id: str, business_date: str) -> str:
        try:
            cfg = billing_service.get_daily_discount(
                company_id=company_id,
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
            res = billing_service.set_daily_discount(
                company_id=company_id,
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
            res = billing_service.get_customer_category_discounts(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error getting customer category discounts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def setCustomerCategoryDiscounts(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = billing_service.set_customer_category_discounts(company_id, data)
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
            rate = billing_service.calculate_authoritative_discount(
                company_id=company_id,
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
            res = supplier_service.list_suppliers(company_id, query)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveSupplier(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = supplier_service.save_supplier(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getSupplierLedger(self, company_id: str, supplier_id: str) -> str:
        try:
            res = supplier_service.get_supplier_ledger(company_id, supplier_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Purchase Management ---
    @pyqtSlot(str, str, result=str)
    def getNextPurchaseVoucherNumber(self, company_id: str, series: str) -> str:
        try:
            res = purchase_service.get_next_purchase_voucher_number(company_id, series or "Main")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createPurchaseVoucher(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = purchase_service.create_purchase_voucher(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def modifyPurchaseVoucher(self, company_id: str, voucher_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = purchase_service.modify_purchase_voucher(company_id, voucher_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error modifying purchase voucher: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def deletePurchaseVoucher(self, company_id: str, voucher_id: str) -> str:
        try:
            purchase_service.delete_purchase_voucher(company_id, voucher_id)
            return json.dumps({"success": True, "message": "Purchase voucher deleted."})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listPurchaseVouchers(self, company_id: str) -> str:
        try:
            res = purchase_service.list_purchase_vouchers(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getPurchaseVoucherDetails(self, company_id: str, voucher_id: str) -> str:
        try:
            res = purchase_service.get_purchase_voucher_details(company_id, voucher_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def createPurchaseReturn(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = purchase_service.create_purchase_return(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Sales Returns ---
    @pyqtSlot(str, str, result=str)
    def createSalesReturn(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = billing_service.create_sales_return(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listSalesReturns(self, company_id: str) -> str:
        try:
            res = billing_service.list_sales_returns(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Centralized Inventory ---
    @pyqtSlot(str, str, str, result=str)
    def validateStockAvailability(self, company_id: str, branch_id: str, items_json: str) -> str:
        """Validates stock availability against negative stock policy for shared inventory."""
        try:
            items = json.loads(items_json) if isinstance(items_json, str) else items_json
            is_valid, errors = inventory_service.validate_stock_availability(
                company_id=company_id,
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
            breakdown = inventory_service.calculate_stock_breakdown(
                company_id=company_id,
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
            qty = inventory_service.get_stock(
                company_id=company_id,
                item_id=item_id,
                branch_id=branch_id if branch_id else None
            )
            return json.dumps({"success": True, "data": qty})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getStockSummary(self, company_id: str, branch_id: str, query: str) -> str:
        try:
            res = inventory_service.get_stock_summary(company_id, branch_id if branch_id else None, query or "")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getStockItemLedger(self, company_id: str, item_id: str, branch_id: str) -> str:
        try:
            res = inventory_service.get_stock_item_ledger(company_id, item_id, branch_id if branch_id else None)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getInventoryDashboard(self, company_id: str) -> str:
        try:
            res = inventory_service.get_inventory_dashboard(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getLowStockAlerts(self, company_id: str) -> str:
        try:
            alerts = inventory_service.get_active_low_stock_alerts(company_id)
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error getting low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getLowStockNotificationsFiltered(self, company_id: str, filter_type: str) -> str:
        """Retrieve low stock notifications with filter ('all', 'critical', 'reorder', 'resolved')."""
        try:
            alerts = inventory_service.get_active_low_stock_alerts(
                company_id=company_id,
                filter_type=filter_type or "all",
                include_dismissed=False
            )
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error getting filtered low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getLowStockNotifications(self, company_id: str, filter_type: str, user_role: str) -> str:
        """
        Retrieve low-stock and reorder notifications for authorised roles.
        Cashier counter role is strictly forbidden from accessing stock valuation and notifications.
        """
        try:
            role_clean = str(user_role or "").strip().lower()
            if role_clean in ("cashier", "pos_cashier", "fast_billing_cashier"):
                return json.dumps({
                    "success": False,
                    "error": "Access Denied: Stock management and notifications are restricted for Cashier roles."
                })

            alerts = inventory_service.get_active_low_stock_alerts(
                company_id=company_id,
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
            data = json.loads(config_json)
            res = catalogue_service.set_item_branch_config(company_id, branch_id, item_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error setting item branch stock config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, str, result=str)
    def getItemBranchStockConfig(self, company_id: str, branch_id: str, item_id: str) -> str:
        """Retrieve branch-specific stock threshold configuration."""
        try:
            res = catalogue_service.get_item_branch_config(company_id, branch_id, item_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error getting item branch stock config: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def listItemBranchStockConfigs(self, company_id: str, item_id: str) -> str:
        """List all branch overrides for an item."""
        try:
            res = catalogue_service.list_item_branch_configs(company_id, item_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error listing item branch configs: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def dismissLowStockAlert(self, company_id: str, alert_id: str) -> str:
        try:
            inventory_service.dismiss_low_stock_alert(company_id, alert_id if alert_id else None)
            return json.dumps({"success": True})
        except Exception as e:
            logger.error(f"Error dismissing low stock alert: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def evaluateLowStockAlerts(self, company_id: str) -> str:
        try:
            alerts = inventory_service.evaluate_low_stock_alerts(company_id)
            return json.dumps({"success": True, "data": alerts})
        except Exception as e:
            logger.error(f"Error evaluating low stock alerts: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def recordStockAdjustment(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = inventory_service.record_stock_adjustment(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def recordStockTransfer(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            res = inventory_service.record_stock_transfer(company_id, data)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Accounting & Ledgers ---
    @pyqtSlot(str, result=str)
    def getChartOfAccounts(self, company_id: str) -> str:
        try:
            res = accounting_service.get_chart_of_accounts(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def getDayBook(self, company_id: str, business_date: str) -> str:
        try:
            res = accounting_service.get_day_book(company_id, business_date if business_date else None)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def getTrialBalance(self, company_id: str) -> str:
        try:
            res = accounting_service.get_trial_balance(company_id)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Supplier Invoice Document OCR ---
    @pyqtSlot(str, str, str, result=str)
    def processInvoiceOcr(self, company_id: str, file_path_or_text: str, file_name: str) -> str:
        try:
            res = ocr_service.process_invoice_document(company_id, file_path_or_text, file_name or "bill.pdf")
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Printing ---
    @pyqtSlot(str, str, int, result=str)
    def getThermalReceipt(self, company_id: str, vch_id: str, width_mm: int) -> str:
        try:
            vch = billing_service.get_voucher_details(company_id, vch_id)
            if not vch:
                return json.dumps({"success": False, "error": "Voucher not found."})
            receipt_text = printing_service.format_thermal_receipt(vch, width_mm or 80)
            return json.dumps({"success": True, "data": receipt_text})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def generatePdfInvoice(self, company_id: str, vch_id: str) -> str:
        try:
            vch = billing_service.get_voucher_details(company_id, vch_id)
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
            vch = billing_service.get_voucher_details(company_id, vch_id)
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
            ext_dest = Path(external_path) if external_path.strip() else None
            res = backup_service.perform_backup(external_dest=ext_dest)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def listBackups(self) -> str:
        try:
            backups = backup_service.list_backups()
            return json.dumps({"success": True, "data": backups})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def restoreBackup(self, filepath: str) -> str:
        try:
            res = backup_service.restore_from_file(filepath)
            return json.dumps(res)
        except Exception as e:
            return json.dumps({"success": False, "message": str(e)})

    # --- Reports ---
    @pyqtSlot(str, str, result=str)
    def getReport(self, company_id: str, report_type: str) -> str:
        try:
            if report_type == "daily_sales":
                data = reporting_service.get_daily_sales_report(company_id)
            elif report_type == "payment_summary":
                data = reporting_service.get_payment_summary(company_id)
            elif report_type == "gst_summary":
                data = reporting_service.get_gst_summary(company_id)
            elif report_type == "gross_profit":
                data = reporting_service.get_gross_profit_report(company_id)
            elif report_type == "low_stock":
                data = inventory_service.get_low_stock_report(company_id)
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
            payload = json.loads(payload_json)
            summary = migration_service.import_localstorage_payload(payload)
            return json.dumps({"success": True, "data": summary})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Mobile Wi-Fi Scanner & Demo Products ---
    @pyqtSlot(str, result=str)
    def startMobileScanner(self, company_id: str) -> str:
        try:
            info = mobile_scanner_service.start_server(company_id=company_id)
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            logger.error(f"Error starting mobile scanner: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def stopMobileScanner(self) -> str:
        try:
            res = mobile_scanner_service.stop_server()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def revokeMobileScannerToken(self) -> str:
        try:
            info = mobile_scanner_service.revoke_token()
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def getMobileScannerInfo(self) -> str:
        try:
            info = mobile_scanner_service.get_info()
            return json.dumps({"success": True, "data": info})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def simulateScan(self, company_id: str, barcode: str) -> str:
        try:
            res = mobile_scanner_service.simulate_scan(company_id=company_id, barcode=barcode)
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def seedDemoProducts(self) -> str:
        try:
            res = demo_product_service.seed_demo_products()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def cleanupDemoProducts(self) -> str:
        try:
            res = demo_product_service.cleanup_demo_products()
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(result=str)
    def getDemoProductsStatus(self) -> str:
        try:
            items = demo_product_service.get_status()
            return json.dumps({"success": True, "data": items})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

