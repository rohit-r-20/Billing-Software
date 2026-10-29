"""
Safe Qt WebChannel Bridge for Anti Matrix Billing ERP.
Exposes specific, validated Python service methods to the JavaScript frontend.
Never allows arbitrary SQL or unrestricted system access.
"""
import json
from pathlib import Path
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import QFileDialog

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
from core.configuration import config
from core.logging_config import logger


class BackendBridge(QObject):
    # Signals to send notifications or async events back to UI
    notification_signal = pyqtSignal(str)
    backup_status_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent_window = parent

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
            return json.dumps({"success": True, "data": accs})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def saveAccount(self, company_id: str, json_data: str) -> str:
        try:
            data = json.loads(json_data)
            acc = account_service.save_account(company_id, data)
            return json.dumps({"success": True, "data": acc})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    # --- Items & Barcodes ---
    @pyqtSlot(str, str, result=str)
    def searchItems(self, company_id: str, query: str) -> str:
        try:
            items = catalogue_service.search_items(company_id, query)
            return json.dumps({"success": True, "data": items})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, str, result=str)
    def findByBarcode(self, company_id: str, barcode: str) -> str:
        try:
            item = catalogue_service.find_by_barcode(company_id, barcode)
            if item:
                return json.dumps({"success": True, "data": item})
            return json.dumps({"success": False, "error": f"Unknown barcode: {barcode}"})
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
                sale_type=sale_type,
                payment_method=pay_method,
                payments=payments,
                narration=narration
            )
            return json.dumps({"success": True, "data": res})
        except Exception as e:
            logger.error(f"Error creating sale invoice: {e}")
            return json.dumps({"success": False, "error": str(e)})

    @pyqtSlot(str, result=str)
    def listVouchers(self, company_id: str) -> str:
        try:
            vouchers = billing_service.list_vouchers(company_id)
            return json.dumps({"success": True, "data": vouchers})
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

