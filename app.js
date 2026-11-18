// =============================================================
// ALPHA BILLING SOFTWARE - COMPLETE APPLICATION ENGINE
// =============================================================

// Default seed company: none in V2. Companies are loaded exclusively from backend.
const DEFAULT_COMPANIES = [];

// App State
let companies = [];
let filteredCompanies = [];
let selectedIndex = 0;
let activeCompany = null;
let currentPendingCompany = null;
let currentScreen = "view-login"; // view-login is the default startup screen
let uiZoom = parseFloat(localStorage.getItem("alpha_ui_zoom") || "1.0");

// Dual Billing Mode & Tabs State
let activeBillingMode = "traditional"; // "traditional" | "fast_billing"
let openTabs = new Set(["traditional"]);
let lastTraditionalScreen = "view-dashboard";
let lastFastBillingScreen = "view-fast-billing";
let isSavingPosSale = false;
let currentPrintVchId = null;
let currentPrintVchData = null;
let currentPrintVoucherType = "sales_invoice";
let currentPrintIsReprint = false;
let printSourceScreen = "view-fast-billing";
let currentPrintPaperFormat = "thermal-80";
let currentPrintOrientation = "portrait";
let todaySalesHistoryData = [];

// DOM Elements - App Root & Zoom
const appRoot = document.getElementById("app-root");
const quickZoomLabel = document.getElementById("quick-zoom-label");
const quickZoomIn = document.getElementById("quick-zoom-in");
const quickZoomOut = document.getElementById("quick-zoom-out");
const menuZoomIn = document.getElementById("menu-zoom-in");
const menuZoomOut = document.getElementById("menu-zoom-out");
const menuZoomReset = document.getElementById("menu-zoom-reset");

// DOM Elements - Views
const viewLogin = document.getElementById("view-login");
const viewCompanies = document.getElementById("view-companies");
const viewModeSelection = document.getElementById("view-mode-selection");
const viewDashboard = document.getElementById("view-dashboard");
const viewAddAccountMaster = document.getElementById("view-add-account-master");
const viewAccountList = document.getElementById("view-account-list");
const viewAddItemMaster = document.getElementById("view-add-item-master");
const viewSalesVoucher = document.getElementById("view-sales-voucher");
const viewSalesList = document.getElementById("view-sales-list");
const viewItemsList = document.getElementById("view-items-list");
const viewFastBilling = document.getElementById("view-fast-billing");
const viewPurchaseEntry = document.getElementById("view-purchase-entry");
const viewPurchaseList = document.getElementById("view-purchase-list");
const viewSupplierMaster = document.getElementById("view-supplier-master");
const viewStockSummary = document.getElementById("view-stock-summary");
const viewStockAdjustments = document.getElementById("view-stock-adjustments");
const viewDayBook = document.getElementById("view-day-book");
const viewFastBillingHistory = document.getElementById("view-fast-billing-history");
const viewFastBillingPrint = document.getElementById("view-fast-billing-print");
const viewCustomerReceipt = document.getElementById("view-customer-receipt");
const viewReceiptList = document.getElementById("view-receipt-list");
const viewSupplierPayment = document.getElementById("view-supplier-payment");
const viewPaymentList = document.getElementById("view-payment-list");
const viewCustomerOutstanding = document.getElementById("view-customer-outstanding");
const viewSupplierOutstanding = document.getElementById("view-supplier-outstanding");
const viewReconciliationDashboard = document.getElementById("view-reconciliation-dashboard");
const viewConfiguration = document.getElementById("view-configuration");

// Dual Billing Mode & Tabs DOM Elements
const appTabsBar = document.getElementById("app-tabs-bar");
const tabBtnTraditional = document.getElementById("tab-btn-traditional");
const tabBtnFastBilling = document.getElementById("tab-btn-fast-billing");
const tabTradBadge = document.getElementById("tab-trad-badge");
const tabFastBadge = document.getElementById("tab-fast-badge");
const btnCloseTradTab = document.getElementById("btn-close-trad-tab");
const btnCloseFastTab = document.getElementById("btn-close-fast-tab");
const btnTabSwitchMode = document.getElementById("btn-tab-switch-mode");
const tabModeIndicator = document.getElementById("tab-mode-indicator");

// Fast Billing Navigation Buttons
const btnPosTabNewSale = document.getElementById("btn-pos-tab-new-sale");
const btnPosTabTodaySales = document.getElementById("btn-pos-tab-today-sales");
const btnPosTabReprint = document.getElementById("btn-pos-tab-reprint");
const btnPosBarTodayHistory = document.getElementById("btn-pos-bar-today-history");

// Fast Billing History Elements
const posHistoryCompany = document.getElementById("pos-history-company");
const posHistoryBranch = document.getElementById("pos-history-branch");
const posHistoryCashier = document.getElementById("pos-history-cashier");
const posHistoryCount = document.getElementById("pos-history-count");
const posHistoryTotalAmt = document.getElementById("pos-history-total-amt");
const posHistoryCashAmt = document.getElementById("pos-history-cash-amt");
const posHistoryDigitalAmt = document.getElementById("pos-history-digital-amt");
const posHistorySearch = document.getElementById("pos-history-search");
const posHistoryTbody = document.getElementById("pos-history-tbody");
const btnPosHistoryBack = document.getElementById("btn-pos-history-back");
const btnPosHistoryRefresh = document.getElementById("btn-pos-history-refresh");
const btnPosHistoryClose = document.getElementById("btn-pos-history-close");

// Fast Billing Print Elements
const posPrintCompany = document.getElementById("pos-print-company");
const posPrintVchNo = document.getElementById("pos-print-vch-no");
const posPrinterSelect = document.getElementById("pos-printer-select");
const posPrintCopies = document.getElementById("pos-print-copies");
const btnCopyDec = document.getElementById("btn-copy-dec");
const btnCopyInc = document.getElementById("btn-copy-inc");
const btnTriggerPrint = document.getElementById("btn-trigger-print");
const btnRefreshPreview = document.getElementById("btn-refresh-preview");
const btnDownloadPdfPrint = document.getElementById("btn-download-pdf-print");
const btnPrintScreenNewBill = document.getElementById("btn-print-screen-new-bill");
const btnPrintNextBill = document.getElementById("btn-print-next-bill");
const btnPosPrintBack = document.getElementById("btn-pos-print-back");
const btnPosPrintClose = document.getElementById("btn-pos-print-close");
const printStatusMsg = document.getElementById("print-status-msg");
const posInvoicePreviewSheet = document.getElementById("pos-invoice-preview-sheet");

// DOM Elements - Screen 1: Standalone Login
const loginCompanySelect = document.getElementById("login-company-select");
const loginUserInput = document.getElementById("login-user-input");
const loginPwdInput = document.getElementById("login-pwd-input");
const btnTogglePwd = document.getElementById("btn-toggle-pwd");
const pwdToggleIcon = document.getElementById("pwd-toggle-icon");
const btnLoginSubmit = document.getElementById("btn-login-submit");
const loginBtnSpinner = document.getElementById("login-btn-spinner");
const loginBtnText = document.getElementById("login-btn-text");
const loginAlert = document.getElementById("login-alert");
const loginAlertText = document.getElementById("login-alert-text");
const btnGotoCompanies = document.getElementById("btn-goto-companies");
const btnCompaniesBack = document.getElementById("btn-companies-back");

// DOM Elements - Companies List
const searchInput = document.getElementById("company-search");
const companyRowsEl = document.getElementById("company-rows");
const recordStatusEl = document.getElementById("record-status");
const chkFinYear = document.getElementById("chk-fin-year");
const chkTaxNo = document.getElementById("chk-tax-no");
const btnSelect = document.getElementById("btn-select");
const btnQuit = document.getElementById("btn-quit");
const btnCreateCompanyModal = document.getElementById("btn-create-company-modal");

// DOM Elements - Modals
const modalLogin = document.getElementById("modal-login");
const loginUsername = document.getElementById("login-username");
const loginPassword = document.getElementById("login-password");
const loginErrorMsg = document.getElementById("login-error-msg");
const btnLoginOk = document.getElementById("btn-login-ok");
const btnLoginBack = document.getElementById("btn-login-back");
const formLogin = document.getElementById("form-login");

const modalCreateCompany = document.getElementById("modal-create-company");
const formCreateCompany = document.getElementById("form-create-company");
const btnCloseCreateModal = document.getElementById("btn-close-create-modal");
const btnCancelNewCompany = document.getElementById("btn-cancel-new-company");
const newCompName = document.getElementById("new-comp-name");
const newCompCode = document.getElementById("new-comp-code");
const newCompFinyear = document.getElementById("new-comp-finyear");
const newCompGstin = document.getElementById("new-comp-gstin");
const newCompState = document.getElementById("new-comp-state");
const newCompUser = document.getElementById("new-comp-user");
const newCompPass = document.getElementById("new-comp-pass");

const modalConfiguration = document.getElementById("modal-configuration");
const formConfiguration = document.getElementById("form-configuration");
const btnCloseConfigModal = document.getElementById("btn-close-config-modal");
const btnCancelConfig = document.getElementById("btn-cancel-config");
const cfgVchStart = document.getElementById("cfg-vch-start");
const cfgVchDigits = document.getElementById("cfg-vch-digits");
const cfgVchPrefix = document.getElementById("cfg-vch-prefix");
const cfgDefaultTax = document.getElementById("cfg-default-tax");
const cfgAutoRound = document.getElementById("cfg-auto-round");

// DOM Elements - Dashboard Elements
const dashboardWatermark = document.getElementById("dashboard-center-watermark");
const statusCompName = document.getElementById("status-comp-name");
const statusFy = document.getElementById("status-fy");
const statusGstin = document.getElementById("status-gstin");
const statusUser = document.getElementById("status-user");
const statusState = document.getElementById("status-state");
const dashboardDatetime = document.getElementById("dashboard-datetime");
const dashboardBreadcrumb = document.getElementById("dashboard-breadcrumb");

// Menus
const menuCloseCompany = document.getElementById("menu-close-company");
const menuEditCompany = document.getElementById("menu-edit-company");
const menuNewCompany = document.getElementById("menu-new-company");
const menuAddAccountMaster = document.getElementById("menu-add-account-master");
const menuAddItemMaster = document.getElementById("menu-add-item-master");
const menuListItemMaster = document.getElementById("menu-list-item-master");
const menuModifyItemMaster = document.getElementById("menu-modify-item-master");
const menuConfigFeatures = document.getElementById("menu-config-features");
const menuConfigVoucherSeries = document.getElementById("menu-config-voucher-series");
const menuChangePassword = document.getElementById("menu-change-password");
const menuSalesAdd = document.getElementById("menu-sales-add");
const menuSalesList = document.getElementById("menu-sales-list");
const menuDisplayBills = document.getElementById("menu-display-bills");

// DOM Elements - Masters
const formAccountMaster = document.getElementById("form-account-master");
const btnAccSave = document.getElementById("btn-acc-save");
const btnAccQuit = document.getElementById("btn-acc-quit");
const btnAccCloseTop = document.getElementById("btn-acc-close-top");
const btnValidateGstin = document.getElementById("btn-validate-gstin");
const accGstin = document.getElementById("acc-gstin");
const accName = document.getElementById("acc-name");
const accPrintName = document.getElementById("acc-print-name");
const accAlias = document.getElementById("acc-alias");

const formItemMaster = document.getElementById("form-item-master");
const itemIdInput = document.getElementById("item-id");
const itemMasterTitle = document.getElementById("item-master-screen-title");
const btnItemSave = document.getElementById("btn-item-save");
const btnItemQuit = document.getElementById("btn-item-quit");
const btnItemCloseTop = document.getElementById("btn-item-close-top");
const btnItemNewClear = document.getElementById("btn-item-new-clear");
const btnItemOpenList = document.getElementById("btn-item-open-list");
const btnItemViewListBottom = document.getElementById("btn-item-view-list-bottom");
const btnItemBackList = document.getElementById("btn-item-back-list");
const itemName = document.getElementById("item-name");
const itemPrintName = document.getElementById("item-print-name");

// DOM Elements - Products & Inventory Catalogue (View 7)
const itemsListSearch = document.getElementById("items-list-search");
const itemsListGroupFilter = document.getElementById("items-list-group-filter");
const itemsMasterTbody = document.getElementById("items-master-tbody");
const itemsListCount = document.getElementById("items-list-count");
const btnItemsListEditSelected = document.getElementById("btn-items-list-edit-selected");
const btnItemsListAdd = document.getElementById("btn-items-list-add");
const btnItemsListAddBottom = document.getElementById("btn-items-list-add-bottom");
const btnItemsListRefresh = document.getElementById("btn-items-list-refresh");
const btnItemsListClose = document.getElementById("btn-items-list-close");
const btnItemsListCloseBottom = document.getElementById("btn-items-list-close-bottom");
const btnItemsListBack = document.getElementById("btn-items-list-back");
const btnClearItemSearch = document.getElementById("btn-clear-item-search");

// DOM Elements - Autocomplete & Product Search Modal (F1)
const posBarcodeSuggestions = document.getElementById("pos-barcode-suggestions");
const modalPosItemSearch = document.getElementById("modal-pos-item-search");
const posModalSearchInput = document.getElementById("pos-modal-search-input");
const posSearchModalTbody = document.getElementById("pos-search-modal-tbody");
const btnClosePosItemSearch = document.getElementById("btn-close-pos-item-search");
const btnCancelPosItemSearch = document.getElementById("btn-cancel-pos-item-search");
const btnModalSearchClear = document.getElementById("btn-modal-search-clear");
const posModalSearchCount = document.getElementById("pos-modal-search-count");
const vchItemAutocompletePopup = document.getElementById("vch-item-autocomplete-popup");
const btnVchSearchProducts = document.getElementById("btn-vch-search-products");

// DOM Elements - Sales Voucher (Billing)
const vchSeries = document.getElementById("vch-series");
const vchDate = document.getElementById("vch-date");
const vchDayLabel = document.getElementById("vch-day-label");
const vchNumber = document.getElementById("vch-number");
const vchSaleType = document.getElementById("vch-sale-type");
const vchPartyInput = document.getElementById("vch-party-input");
const partyDatalist = document.getElementById("party-datalist");
const vchMatCentre = document.getElementById("vch-mat-centre");
const vchNarration = document.getElementById("vch-narration");
const vchItemsTbody = document.getElementById("vch-items-tbody");
const vchSubtotalVal = document.getElementById("vch-subtotal-val");
const btnApplyTax = document.getElementById("btn-apply-tax");
const taxRateDisplay = document.getElementById("tax-rate-display");
const taxableAmtDisplay = document.getElementById("taxable-amt-display");
const cgstDisplay = document.getElementById("cgst-display");
const sgstDisplay = document.getElementById("sgst-display");
const sundry1Name = document.getElementById("sundry-1-name");
const sundry1Rate = document.getElementById("sundry-1-rate");
const sundry1Amt = document.getElementById("sundry-1-amt");
const sundry2Name = document.getElementById("sundry-2-name");
const sundry2Rate = document.getElementById("sundry-2-rate");
const sundry2Amt = document.getElementById("sundry-2-amt");
const sundryRoundAmt = document.getElementById("sundry-round-amt");
const vchGrandTotal = document.getElementById("vch-grand-total");
const saleTypeDesc = document.getElementById("sale-type-desc");
const vchItemInfo = document.getElementById("vch-item-info");
const infoVchNo = document.getElementById("info-vch-no");
const btnSaveSalesVoucher = document.getElementById("btn-save-sales-voucher");
const btnQuitSalesVoucher = document.getElementById("btn-quit-sales-voucher");
const btnSalesCloseTop = document.getElementById("btn-sales-close-top");

// Sales Bills List
const salesRegisterTbody = document.getElementById("sales-register-tbody");
const salesRegisterCount = document.getElementById("sales-register-count");
const btnNewBillFromList = document.getElementById("btn-new-bill-from-list");
const btnCloseSalesList = document.getElementById("btn-close-sales-list");
const btnSalesListClose = document.getElementById("btn-sales-list-close");

// Fast Billing (POS) Elements
const posBarcodeInput = document.getElementById("pos-barcode-input");
const posCartTbody = document.getElementById("pos-cart-tbody");
const posEmptyCartMsg = document.getElementById("pos-empty-cart-msg");
const posItemCount = document.getElementById("pos-item-count");
const posGrossSubtotal = document.getElementById("pos-gross-subtotal");
const posDiscountTotal = document.getElementById("pos-discount-total");
const posSubtotal = document.getElementById("pos-subtotal");
const posTaxTotal = document.getElementById("pos-tax-total");
const posRoundOff = document.getElementById("pos-round-off");
const posPayableAmount = document.getElementById("pos-payable-amount");
const posVchNo = document.getElementById("pos-vch-no");
const btnPosClose = document.getElementById("btn-pos-close");
const btnPosSearchItem = document.getElementById("btn-pos-search-item");
const btnPosHold = document.getElementById("btn-pos-hold");
const btnPosResume = document.getElementById("btn-pos-resume");
const btnPosClear = document.getElementById("btn-pos-clear");
const heldCountEl = document.getElementById("held-count");
const btnPosPayCash = document.getElementById("btn-pos-pay-cash");
const btnPosPayUpi = document.getElementById("btn-pos-pay-upi");
const btnPosPayCard = document.getElementById("btn-pos-pay-card");
const btnPosPaySplit = document.getElementById("btn-pos-pay-split");
const btnPosCheckoutPrint = document.getElementById("btn-pos-checkout-print");

// Cash Modal Elements
const modalPosCash = document.getElementById("modal-pos-cash");
const btnClosePosCash = document.getElementById("btn-close-pos-cash");
const modalCashDueVal = document.getElementById("modal-cash-due-val");
const posCashTendered = document.getElementById("pos-cash-tendered");
const modalCashChangeVal = document.getElementById("modal-cash-change-val");
const btnConfirmPosCash = document.getElementById("btn-confirm-pos-cash");

// Thermal Receipt Modal Elements
const modalReceiptPreview = document.getElementById("modal-receipt-preview");
const receiptPreviewText = document.getElementById("receipt-preview-text");
const btnCloseReceiptModal = document.getElementById("btn-close-receipt-modal");
const btnDownloadPdfInvoice = document.getElementById("btn-download-pdf-invoice");
const btnPrintReceiptAction = document.getElementById("btn-print-receipt-action");

// Backup Modal Elements
const modalBackup = document.getElementById("modal-backup");
const btnCloseBackupModal = document.getElementById("btn-close-backup-modal");
const btnTriggerBackup = document.getElementById("btn-trigger-backup");
const backupExternalDrive = document.getElementById("backup-external-drive");
const backupListTbody = document.getElementById("backup-list-tbody");

// Reports Modal Elements
const modalReports = document.getElementById("modal-reports");
const btnCloseReportsModal = document.getElementById("btn-close-reports-modal");
const reportContentView = document.getElementById("report-content-view");

// Data Migration Modal Elements
const modalDataMigration = document.getElementById("modal-data-migration");
const btnCloseMigrationModal = document.getElementById("btn-close-migration-modal");
const btnExportJsonAction = document.getElementById("btn-export-json-action");
const btnImportJsonAction = document.getElementById("btn-import-json-action");
const migrationStatusMsg = document.getElementById("migration-status-msg");

// Menus
const menuFastBilling = document.getElementById("menu-fast-billing");
const menuDataExportImport = document.getElementById("menu-data-export-import");
const menuGstReports = document.getElementById("menu-gst-reports");
const menuPrinterSettings = document.getElementById("menu-printer-settings");
const menuBackupRestore = document.getElementById("menu-backup-restore");

// Mode Selection Elements
const modeCompanyName = document.getElementById("mode-company-name");
const modeBranchName = document.getElementById("mode-branch-name");
const modeUserName = document.getElementById("mode-user-name");
const modeFyName = document.getElementById("mode-fy-name");
const btnModeSettings = document.getElementById("btn-mode-settings");
const btnModeLogout = document.getElementById("btn-mode-logout");
const btnSelectBilling = document.getElementById("btn-select-billing");
const btnSelectFastBilling = document.getElementById("btn-select-fast-billing");
const cardModeBilling = document.getElementById("card-mode-billing");
const cardModeFastBilling = document.getElementById("card-mode-fast-billing");
const menuSwitchMode = document.getElementById("menu-switch-mode");
const barSwitchMode = document.getElementById("bar-switch-mode");

// Fast Billing Header Elements
const btnPosBackMode = document.getElementById("btn-pos-back-mode");
const btnPosLogout = document.getElementById("btn-pos-logout");
const posHeaderCompany = document.getElementById("pos-header-company");
const posHeaderBranch = document.getElementById("pos-header-branch");
const posHeaderCashier = document.getElementById("pos-header-cashier");

// Fast Billing Bottom Action Bar Buttons
const btnPosBarNewSale = document.getElementById("btn-pos-bar-new-sale");
const btnPosBarSearch = document.getElementById("btn-pos-bar-search");
const btnPosBarHold = document.getElementById("btn-pos-bar-hold");
const btnPosBarResume = document.getElementById("btn-pos-bar-resume");
const btnPosBarRemove = document.getElementById("btn-pos-bar-remove");
const btnPosBarCancel = document.getElementById("btn-pos-bar-cancel");
const btnPosBarCheckout = document.getElementById("btn-pos-bar-checkout");
const btnPosBarReprint = document.getElementById("btn-pos-bar-reprint");

// POS State & Usability Elements
let posCart = [];
let heldBills = [];
let lastCompletedVoucher = null;
const posScanFeedback = document.getElementById("pos-scan-feedback");
const posTenderReceived = document.getElementById("pos-tender-received");
const posChangeDueVal = document.getElementById("pos-change-due-val");
const posBalanceDueVal = document.getElementById("pos-balance-due-val");
const chipTenderExact = document.getElementById("chip-tender-exact");
const posDailyDiscountToggle = document.getElementById("pos-daily-discount-toggle");
const posDailyDiscountBadge = document.getElementById("pos-daily-discount-badge");

// Controlled Enhancement: Low-Stock Alerts & Customer Category State
let cachedCategoryDiscounts = {
  "Commercial": 5.0,
  "Sub-Commercial": 2.5,
  "Direct Customer": 0.0
};
let cachedAccountsList = [];
let activeVoucherCustomerCategory = "Direct Customer";
let activePosCustomerCategory = "Direct Customer";
let activePosCustomerName = "CASH";
let activePosCustomerId = null;
let sessionLowStockDismissed = false;

// =============================================================
// STORAGE & MIGRATION UTILITIES
// =============================================================
function loadCompanies() {
  // Backend-only company catalog in V2. No hardcoded or localStorage demo companies.
  return [];
}

function saveCompanies() {
  // No-op in V2: company catalog is mastered in backend database.
}

function generateNextCompanyCode() {
  let maxId = 0;
  companies.forEach((c) => {
    const match = c.code.match(/COMP(\d+)/i);
    if (match) {
      const num = parseInt(match[1], 10);
      if (num > maxId) maxId = num;
    }
  });
  return "COMP" + String(maxId + 1).padStart(4, "0");
}

// Company Configuration Storage
function getCompanyConfig(companyCode) {
  const key = `alpha_config_${companyCode || (activeCompany ? activeCompany.code : "COMP0001")}`;
  try {
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved);
  } catch (e) {}
  return {
    vchStart: 1,
    vchDigits: 3,
    vchPrefix: "",
    defaultTax: "18",
    autoRound: "Y"
  };
}

function saveCompanyConfig(companyCode, config) {
  const key = `alpha_config_${companyCode || (activeCompany ? activeCompany.code : "COMP0001")}`;
  localStorage.setItem(key, JSON.stringify(config));
}

// =============================================================
// GLOBAL APPLICATION ZOOM CONTROLLER
// One central application-wide zoom mechanism across every screen
// =============================================================
const ZoomController = {
  MIN_ZOOM: 0.70, // 70%
  MAX_ZOOM: 1.50, // 150%
  STEP: 0.10,     // 10% increments
  STORAGE_KEY: "alpha_ui_zoom",

  getZoom() {
    if (typeof uiZoom !== "undefined" && !isNaN(uiZoom) && uiZoom > 0) {
      return uiZoom;
    }
    const saved = parseFloat(localStorage.getItem(this.STORAGE_KEY) || "1.0");
    return isNaN(saved) ? 1.0 : saved;
  },

  clamp(scale) {
    let target = Math.round(scale * 10) / 10;
    return Math.min(this.MAX_ZOOM, Math.max(this.MIN_ZOOM, target));
  },

  applyZoom(newScale, showToast = true) {
    const clamped = this.clamp(newScale);
    uiZoom = Math.round(clamped * 100) / 100;
    window.uiZoom = uiZoom;

    if (appRoot) {
      appRoot.style.zoom = uiZoom;
      appRoot.style.width = `calc(100vw / ${uiZoom})`;
      appRoot.style.height = `calc(100vh / ${uiZoom})`;
      appRoot.style.maxWidth = `calc(100vw / ${uiZoom})`;
      appRoot.style.maxHeight = `calc(100vh / ${uiZoom})`;
    }
    document.documentElement.style.setProperty("--ui-scale", uiZoom.toString());

    const percentage = Math.round(uiZoom * 100) + "%";
    
    // Update visible header display and compatibility elements immediately
    const headerLabel = document.getElementById("header-zoom-label");
    if (headerLabel) {
      headerLabel.textContent = percentage;
    }
    if (quickZoomLabel) {
      quickZoomLabel.textContent = percentage;
    }

    // Boundary button states (disable - at 70%, + at 150%)
    const btnIn = document.getElementById("btn-zoom-in");
    const btnOut = document.getElementById("btn-zoom-out");
    if (btnIn) {
      btnIn.disabled = (uiZoom >= this.MAX_ZOOM);
    }
    if (btnOut) {
      btnOut.disabled = (uiZoom <= this.MIN_ZOOM);
    }

    const qIn = document.getElementById("quick-zoom-in");
    const qOut = document.getElementById("quick-zoom-out");
    if (qIn) qIn.disabled = (uiZoom >= this.MAX_ZOOM);
    if (qOut) qOut.disabled = (uiZoom <= this.MIN_ZOOM);

    try {
      localStorage.setItem(this.STORAGE_KEY, uiZoom.toString());
    } catch (e) {}

    if (showToast && typeof showNotification === "function") {
      showNotification(`Interface Scale: ${percentage}`);
    }

    return uiZoom;
  },

  zoomIn() {
    return this.applyZoom(this.getZoom() + this.STEP);
  },

  zoomOut() {
    return this.applyZoom(this.getZoom() - this.STEP);
  },

  resetZoom() {
    return this.applyZoom(1.0);
  },

  bindControls() {
    const btnIn = document.getElementById("btn-zoom-in");
    const btnOut = document.getElementById("btn-zoom-out");

    if (btnIn && !btnIn.dataset.zoomBound) {
      btnIn.dataset.zoomBound = "true";
      btnIn.addEventListener("click", () => this.zoomIn());
    }
    if (btnOut && !btnOut.dataset.zoomBound) {
      btnOut.dataset.zoomBound = "true";
      btnOut.addEventListener("click", () => this.zoomOut());
    }

    const qIn = document.getElementById("quick-zoom-in");
    const qOut = document.getElementById("quick-zoom-out");
    if (qIn && !qIn.dataset.zoomBound) {
      qIn.dataset.zoomBound = "true";
      qIn.addEventListener("click", () => this.zoomIn());
    }
    if (qOut && !qOut.dataset.zoomBound) {
      qOut.dataset.zoomBound = "true";
      qOut.addEventListener("click", () => this.zoomOut());
    }

    const menuIn = document.getElementById("menu-zoom-in");
    const menuOut = document.getElementById("menu-zoom-out");
    const menuReset = document.getElementById("menu-zoom-reset");
    if (menuIn && !menuIn.dataset.zoomBound) {
      menuIn.dataset.zoomBound = "true";
      menuIn.addEventListener("click", () => this.zoomIn());
    }
    if (menuOut && !menuOut.dataset.zoomBound) {
      menuOut.dataset.zoomBound = "true";
      menuOut.addEventListener("click", () => this.zoomOut());
    }
    if (menuReset && !menuReset.dataset.zoomBound) {
      menuReset.dataset.zoomBound = "true";
      menuReset.addEventListener("click", () => this.resetZoom());
    }
  },

  init() {
    this.bindControls();
    const initial = this.getZoom();
    this.applyZoom(initial, false);
  }
};
window.ZoomController = ZoomController;

function applyZoom(newScale) {
  return ZoomController.applyZoom(newScale);
}
window.applyZoom = applyZoom;

window.addEventListener("resize", () => {
  if (appRoot && uiZoom) {
    appRoot.style.width = `calc(100vw / ${uiZoom})`;
    appRoot.style.height = `calc(100vh / ${uiZoom})`;
    appRoot.style.maxWidth = `calc(100vw / ${uiZoom})`;
    appRoot.style.maxHeight = `calc(100vh / ${uiZoom})`;
  }
});

ZoomController.bindControls();

// =============================================================
// SCREEN VIEW ROUTER
// =============================================================
function showScreen(screenId) {
  // Authentication Route Guard
  const isAuth = window.BusinessContext ? window.BusinessContext.isAuthenticatedSession() : false;
  if (!isAuth && screenId !== "view-login") {
    console.warn(`[RouteGuard] Blocked access to ${screenId} for unauthenticated session.`);
    if (typeof showNotification === "function") {
      showNotification("Authentication required. Please sign in.", "warning");
    }
    screenId = "view-login";
  }

  currentScreen = screenId;
  const allViews = [
    viewLogin,
    viewCompanies,
    viewModeSelection,
    viewDashboard,
    viewAddAccountMaster,
    viewAccountList,
    viewAddItemMaster,
    viewSalesVoucher,
    viewSalesList,
    viewItemsList,
    viewFastBilling,
    viewFastBillingHistory,
    viewFastBillingPrint,
    viewPurchaseEntry,
    viewPurchaseList,
    viewSupplierMaster,
    viewStockSummary,
    viewStockAdjustments,
    viewDayBook,
    viewCustomerReceipt,
    viewReceiptList,
    viewSupplierPayment,
    viewPaymentList,
    viewCustomerOutstanding,
    viewSupplierOutstanding,
    viewReconciliationDashboard,
    viewConfiguration
  ];

  allViews.forEach((view) => {
    if (view) {
      view.classList.toggle("active", view.id === screenId);
    }
  });

  const fastBillingScreens = ["view-fast-billing", "view-fast-billing-history", "view-fast-billing-print"];
  const isFastBilling = fastBillingScreens.includes(screenId);
  const isStandalone = ["view-login", "view-companies", "view-mode-selection"].includes(screenId);

  // Manage internal application tab bar visibility & mode state
  if (appTabsBar) {
    if (isStandalone || !isAuth) {
      appTabsBar.style.display = "none";
    } else {
      appTabsBar.style.display = "flex";
      updateAppTabsDisplay(isFastBilling ? "fast_billing" : "traditional");
    }
  }

  // Manage Top Header visibility: Only visible for authenticated non-standalone screens
  const alphaTopHeader = document.getElementById("alpha-top-header");
  if (alphaTopHeader) {
    alphaTopHeader.style.display = isAuth && !isStandalone ? "flex" : "none";
  }

  // Manage Sidebar: Fast Billing cashier workspace hides sidebar; unauthenticated hides sidebar
  const alphaSidebar = document.getElementById("alpha-sidebar");
  if (alphaSidebar) {
    if (!isAuth || isStandalone || isFastBilling) {
      alphaSidebar.style.display = "none";
    } else {
      alphaSidebar.style.display = "";
    }
  }

  // Track separate navigation contexts
  if (!isStandalone) {
    if (isFastBilling) {
      activeBillingMode = "fast_billing";
      lastFastBillingScreen = screenId;
      openTabs.add("fast_billing");
    } else {
      activeBillingMode = "traditional";
      lastTraditionalScreen = screenId;
      openTabs.add("traditional");
    }
  }

  // Update Header Title & Breadcrumbs
  const titleEl = document.getElementById("header-page-title");
  const breadcrumbEl = document.getElementById("dashboard-breadcrumb");
  const viewMeta = {
    "view-dashboard": { title: "Business Dashboard", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Dashboard</strong>" },
    "view-fast-billing": { title: "Fast Billing (Retail POS)", bc: "Alpha Billing &rsaquo; Fast Billing &rsaquo; <strong>New Bill (POS)</strong>" },
    "view-fast-billing-history": { title: "Today's Sales History", bc: "Alpha Billing &rsaquo; Fast Billing &rsaquo; <strong>Today's Sales History</strong>" },
    "view-fast-billing-print": { title: "Invoice Print & Preview", bc: "Alpha Billing &rsaquo; Fast Billing &rsaquo; <strong>Print & Preview</strong>" },
    "view-sales-voucher": { title: "Sales Tax Invoice", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Sales Tax Invoice</strong>" },
    "view-sales-list": { title: "Sales Invoices Register", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Sales Register</strong>" },
    "view-purchase-entry": { title: "Purchase Entry (Inward)", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Purchase Entry</strong>" },
    "view-purchase-list": { title: "Purchase Register", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Purchase Register</strong>" },
    "view-add-item-master": { title: "Item & Product Master", bc: "Alpha Billing &rsaquo; Administration &rsaquo; <strong>Add Product</strong>" },
    "view-items-list": { title: "Products Catalogue", bc: "Alpha Billing &rsaquo; Administration &rsaquo; <strong>Products List</strong>" },
    "view-supplier-master": { title: "Supplier Master", bc: "Alpha Billing &rsaquo; Administration &rsaquo; <strong>Supplier Master</strong>" },
    "view-add-account-master": { title: "Account Master", bc: "Alpha Billing &rsaquo; Administration &rsaquo; <strong>Account Master</strong>" },
    "view-account-list": { title: "List of Accounts", bc: "Alpha Billing &rsaquo; Administration &rsaquo; <strong>Account Master List</strong>" },
    "view-stock-summary": { title: "Stock Valuation & WAC Summary", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Stock Valuation</strong>" },
    "view-stock-adjustments": { title: "Stock Adjustments & Transfers", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Stock Operations</strong>" },
    "view-day-book": { title: "Financial Day Book & Trial Balance", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Day Book & Trial Balance</strong>" },
    "view-customer-receipt": { title: "Customer Receipt (Collection)", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Customer Receipt</strong>" },
    "view-receipt-list": { title: "Customer Receipts Register", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Receipts Register</strong>" },
    "view-supplier-payment": { title: "Supplier Payment (Disbursement)", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Supplier Payment</strong>" },
    "view-payment-list": { title: "Supplier Payments Register", bc: "Alpha Billing &rsaquo; Transaction &rsaquo; <strong>Payments Register</strong>" },
    "view-customer-outstanding": { title: "Accounts Receivable (Customer Outstandings)", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Accounts Receivable</strong>" },
    "view-supplier-outstanding": { title: "Accounts Payable (Supplier Outstandings)", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Accounts Payable</strong>" },
    "view-reconciliation-dashboard": { title: "Financial Reconciliation & Audit", bc: "Alpha Billing &rsaquo; Display &rsaquo; <strong>Financial Reconciliation</strong>" },
    "view-companies": { title: "List of Companies", bc: "Alpha Billing &rsaquo; Company &rsaquo; <strong>Switch Company</strong>" },
    "view-configuration": { title: "Paper & Hardware Configuration", bc: "Anti Matrix &rsaquo; Administration &rsaquo; <strong>Paper Configuration</strong>" },
    "view-login": { title: "Sign In", bc: "Alpha Billing &rsaquo; <strong>Authentication</strong>" }
  };
  if (viewMeta[screenId]) {
    if (titleEl) titleEl.textContent = viewMeta[screenId].title;
    if (breadcrumbEl) breadcrumbEl.innerHTML = viewMeta[screenId].bc;
  }

  // Update Sidebar active navigation item
  const screenNavMap = {
    "view-dashboard": "btn-nav-overview",
    "view-fast-billing": "btn-nav-pos",
    "view-sales-voucher": "btn-nav-sales-add",
    "view-sales-list": "btn-nav-sales-list",
    "view-purchase-entry": "btn-nav-purchase-add",
    "view-purchase-list": "btn-nav-purchase-list",
    "view-supplier-master": "btn-nav-suppliers",
    "view-stock-summary": "btn-nav-stock",
    "view-stock-adjustments": "btn-nav-adjustments",
    "view-items-list": "btn-nav-products",
    "view-add-item-master": "btn-nav-add-product",
    "view-add-account-master": "btn-nav-customers",
    "view-account-list": "btn-nav-customers",
    "view-day-book": "btn-nav-daybook",
    "view-configuration": "sub-admin-configuration"
  };
  const activeNavId = screenNavMap[screenId];
  document.querySelectorAll(".dash-nav-item, .nav-sub-btn").forEach(item => {
    item.classList.toggle("active", item.id === activeNavId);
  });

  if (screenId === "view-login") {
    populateLoginCompanies();
    hideLoginAlert();
    if (loginPwdInput) loginPwdInput.value = "";
    setTimeout(() => {
      if (loginUserInput && !loginUserInput.value) {
        loginUserInput.focus();
      } else if (loginPwdInput) {
        loginPwdInput.focus();
      }
    }, 50);
  } else if (screenId === "view-companies") {
    searchInput.focus();
    renderCompanyTable();
  } else if (screenId === "view-dashboard") {
    renderOperationalDashboard();
  } else if (screenId === "view-mode-selection") {
    renderModeSelection();
  } else if (screenId === "view-add-account-master") {
    accName.focus();
  } else if (screenId === "view-account-list") {
    renderAccountMasterList();
    setTimeout(() => {
      const searchIn = document.getElementById("acc-list-search");
      if (searchIn) searchIn.focus();
    }, 50);
  } else if (screenId === "view-add-item-master") {
    itemName.focus();
  } else if (screenId === "view-sales-voucher") {
    if (!isSalesModifyMode) {
      initSalesVoucherScreen();
    }
  } else if (screenId === "view-sales-list") {
    renderSalesRegister();
  } else if (screenId === "view-items-list") {
    renderProductsList();
    setTimeout(() => {
      if (itemsListSearch) itemsListSearch.focus();
    }, 50);
  } else if (screenId === "view-fast-billing") {
    initFastBillingScreen();
  } else if (screenId === "view-fast-billing-history") {
    renderFastBillingHistory();
  } else if (screenId === "view-fast-billing-print") {
    renderInvoicePrintPreview();
  } else if (screenId === "view-purchase-entry") {
    initPurchaseEntryScreen();
  } else if (screenId === "view-purchase-list") {
    renderPurchaseRegister();
  } else if (screenId === "view-supplier-master") {
    renderSupplierMaster();
  } else if (screenId === "view-stock-summary") {
    renderStockSummary();
  } else if (screenId === "view-stock-adjustments") {
    initStockAdjustmentsScreen();
  } else if (screenId === "view-day-book") {
    renderDayBookScreen();
  } else if (screenId === "view-customer-receipt") {
    initCustomerReceiptScreen();
  } else if (screenId === "view-receipt-list") {
    renderCustomerReceiptsRegister();
  } else if (screenId === "view-supplier-payment") {
    initSupplierPaymentScreen();
  } else if (screenId === "view-payment-list") {
    renderSupplierPaymentsRegister();
  } else if (screenId === "view-customer-outstanding") {
    renderCustomerOutstandingView();
  } else if (screenId === "view-supplier-outstanding") {
    renderSupplierOutstandingView();
  } else if (screenId === "view-reconciliation-dashboard") {
    renderReconciliationDashboard();
  } else if (screenId === "view-configuration") {
    if (typeof initPaperConfigScreen === "function") {
      initPaperConfigScreen();
    }
  }
}

// =============================================================
// COMPANIES LIST & SELECTION
// =============================================================
function renderCompanyTable() {
  companyRowsEl.innerHTML = "";

  const showFin = chkFinYear.checked;
  const showTax = chkTaxNo.checked;

  document.querySelectorAll(".col-finyear").forEach((el) => {
    el.classList.toggle("hidden", !showFin);
  });
  document.querySelectorAll(".col-taxno").forEach((el) => {
    el.classList.toggle("hidden", !showTax);
  });

  if (filteredCompanies.length === 0) {
    const emptyRow = document.createElement("tr");
    emptyRow.innerHTML = `
      <td colspan="4" style="text-align: center; color: #64748b; padding: 24px; font-weight: normal;">
        No companies found. Click "+ Create Company" to add one.
      </td>
    `;
    companyRowsEl.appendChild(emptyRow);
    recordStatusEl.textContent = `Record - 0 # 0`;
    return;
  }

  if (selectedIndex >= filteredCompanies.length) selectedIndex = filteredCompanies.length - 1;
  if (selectedIndex < 0) selectedIndex = 0;

  filteredCompanies.forEach((comp, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.index = idx;
    if (idx === selectedIndex) {
      tr.classList.add("selected");
    }

    tr.innerHTML = `
      <td class="col-name">${escapeHtml(comp.name)}</td>
      <td class="col-code">${escapeHtml(comp.code)}</td>
      <td class="col-finyear ${showFin ? "" : "hidden"}">${escapeHtml(comp.finYear)}</td>
      <td class="col-taxno ${showTax ? "" : "hidden"}">${escapeHtml(comp.taxNo || "")}</td>
    `;

    tr.addEventListener("click", () => setSelectedIndex(idx));
    tr.addEventListener("dblclick", () => {
      setSelectedIndex(idx);
      openLoginModalForSelected();
    });

    companyRowsEl.appendChild(tr);
  });

  updateRecordStatus();
}

function updateRecordStatus() {
  const current = filteredCompanies.length > 0 ? selectedIndex + 1 : 0;
  const total = filteredCompanies.length;
  recordStatusEl.textContent = `Record - ${current} # ${total}`;
}

function setSelectedIndex(newIndex) {
  if (newIndex < 0 || newIndex >= filteredCompanies.length) return;
  selectedIndex = newIndex;

  const rows = companyRowsEl.querySelectorAll("tr");
  rows.forEach((row, idx) => {
    row.classList.toggle("selected", idx === selectedIndex);
    if (idx === selectedIndex) {
      row.scrollIntoView({ block: "nearest" });
    }
  });

  updateRecordStatus();
}

function filterCompanies() {
  const query = searchInput.value.trim().toUpperCase();
  if (!query) {
    filteredCompanies = [...companies];
  } else {
    filteredCompanies = companies.filter((c) => {
      return (
        c.name.toUpperCase().includes(query) ||
        c.code.toUpperCase().includes(query) ||
        (c.taxNo && c.taxNo.toUpperCase().includes(query))
      );
    });
  }
  selectedIndex = 0;
  renderCompanyTable();
}

// =============================================================
// SCREEN 1: STANDALONE LOGIN ENGINE
// =============================================================
let activeLoginMode = "traditional";
let companyFetchSeq = 0;

function fetchAndPopulateCompanies() {
  const currentSeq = ++companyFetchSeq;
  const currentMode = activeLoginMode;

  // Immediately clear companies so previous mode's data never lingers
  companies = [];
  filteredCompanies = [];

  if (!window.backend) {
    populateLoginCompanies();
    return;
  }

  // Show loading state while fetching from backend
  populateLoginCompanies(true);

  if (currentMode === "traditional") {
    if (typeof window.backend.traditional_listCompanies === "function") {
      window.backend.traditional_listCompanies((resp) => {
        // Discard stale responses from previous requests or mode switches
        if (currentSeq !== companyFetchSeq || activeLoginMode !== "traditional") {
          return;
        }
        try {
          const r = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (r && r.success && Array.isArray(r.data)) {
            companies = r.data;
            filteredCompanies = [...companies];
          } else {
            companies = [];
            filteredCompanies = [];
          }
        } catch (e) {
          console.error("Error loading traditional companies:", e);
          companies = [];
          filteredCompanies = [];
        }
        populateLoginCompanies();
      });
    } else {
      populateLoginCompanies();
    }
  } else if (currentMode === "fast_billing") {
    if (typeof window.backend.listCompanies === "function") {
      window.backend.listCompanies((resp) => {
        // Discard stale responses from previous requests or mode switches
        if (currentSeq !== companyFetchSeq || activeLoginMode !== "fast_billing") {
          return;
        }
        try {
          const r = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (r && r.success && Array.isArray(r.data)) {
            companies = r.data;
            filteredCompanies = [...companies];
          } else {
            companies = [];
            filteredCompanies = [];
          }
        } catch (e) {
          console.error("Error loading fast billing companies:", e);
          companies = [];
          filteredCompanies = [];
        }
        populateLoginCompanies();
      });
    } else {
      populateLoginCompanies();
    }
  }
}

function initLoginModeToggle() {
  const btnTrad = document.getElementById("btn-login-mode-trad");
  const btnFast = document.getElementById("btn-login-mode-fast");
  if (!btnTrad || !btnFast) return;

  btnTrad.onclick = () => {
    if (activeLoginMode === "traditional") return;
    activeLoginMode = "traditional";
    btnTrad.style.background = "#2563eb";
    btnTrad.style.color = "#ffffff";
    btnTrad.style.borderColor = "#2563eb";
    btnFast.style.background = "#f8fafc";
    btnFast.style.color = "#475569";
    btnFast.style.borderColor = "#cbd5e1";
    const btnOpenRecovery = document.getElementById("btn-open-traditional-recovery");
    if (btnOpenRecovery) btnOpenRecovery.style.display = (companies && companies.length > 0) ? "inline-flex" : "none";
    fetchAndPopulateCompanies();
  };

  btnFast.onclick = () => {
    if (activeLoginMode === "fast_billing") return;
    activeLoginMode = "fast_billing";
    btnFast.style.background = "#059669";
    btnFast.style.color = "#ffffff";
    btnFast.style.borderColor = "#059669";
    btnTrad.style.background = "#f8fafc";
    btnTrad.style.color = "#475569";
    btnTrad.style.borderColor = "#cbd5e1";
    // Never show Traditional setup or recovery in Fast Billing mode
    const tradSetupContainer = document.getElementById("traditional-setup-container");
    if (tradSetupContainer) tradSetupContainer.style.display = "none";
    const btnOpenRecovery = document.getElementById("btn-open-traditional-recovery");
    if (btnOpenRecovery) btnOpenRecovery.style.display = "none";
    closeTraditionalSetupModal();
    if (typeof closeTraditionalRecoveryModal === "function") {
      closeTraditionalRecoveryModal();
    }
    fetchAndPopulateCompanies();
  };
}

function populateLoginCompanies(isLoading = false) {
  if (!loginCompanySelect) return;
  const currentVal = loginCompanySelect.value;
  loginCompanySelect.innerHTML = "";
  const tradSetupContainer = document.getElementById("traditional-setup-container");
  const btnOpenRecovery = document.getElementById("btn-open-traditional-recovery");

  if (isLoading) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Loading companies...";
    opt.disabled = true;
    opt.selected = true;
    loginCompanySelect.appendChild(opt);
    loginCompanySelect.disabled = true;
    if (btnLoginSubmit) btnLoginSubmit.disabled = true;
    if (loginUserInput) loginUserInput.disabled = true;
    if (loginPwdInput) loginPwdInput.disabled = true;
    if (tradSetupContainer) tradSetupContainer.style.display = "none";
    if (btnOpenRecovery) btnOpenRecovery.style.display = "none";
    return;
  }

  if (!companies || companies.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    if (!window.backend) {
      opt.textContent = "Connecting to backend...";
      if (tradSetupContainer) tradSetupContainer.style.display = "none";
    } else if (activeLoginMode === "traditional") {
      opt.textContent = "-- No Traditional Companies (Setup Required) --";
      if (tradSetupContainer) tradSetupContainer.style.display = "block";
    } else {
      opt.textContent = "-- No Fast Billing Companies Found --";
      if (tradSetupContainer) tradSetupContainer.style.display = "none";
    }
    opt.disabled = true;
    opt.selected = true;
    loginCompanySelect.appendChild(opt);
    loginCompanySelect.disabled = true;
    if (btnLoginSubmit) btnLoginSubmit.disabled = true;
    if (loginUserInput) loginUserInput.disabled = true;
    if (loginPwdInput) loginPwdInput.disabled = true;
    if (btnOpenRecovery) btnOpenRecovery.style.display = "none";
    return;
  }

  // Companies loaded from backend - enable controls
  if (tradSetupContainer) tradSetupContainer.style.display = "none";
  if (btnOpenRecovery) {
    btnOpenRecovery.style.display = activeLoginMode === "traditional" ? "inline-flex" : "none";
  }
  loginCompanySelect.disabled = false;
  if (btnLoginSubmit) btnLoginSubmit.disabled = false;
  if (loginUserInput) loginUserInput.disabled = false;
  if (loginPwdInput) loginPwdInput.disabled = false;

  companies.forEach((comp) => {
    const opt = document.createElement("option");
    opt.value = comp.code;
    opt.textContent = `${comp.name} (${comp.code})`;
    loginCompanySelect.appendChild(opt);
  });

  if (currentVal && Array.from(loginCompanySelect.options).some((o) => o.value === currentVal)) {
    loginCompanySelect.value = currentVal;
  } else if (loginCompanySelect.options.length > 0) {
    loginCompanySelect.selectedIndex = 0;
  }
}

// =============================================================
// TRADITIONAL BILLING FIRST-TIME SETUP MODAL ENGINE
// =============================================================
let isSubmittingTraditionalSetup = false;

function openTraditionalSetupModal() {
  const modal = document.getElementById("modal-traditional-setup");
  if (!modal) return;
  hideTraditionalSetupAlert();
  setTraditionalSetupLoading(false);

  // Set default values if empty
  const nameInput = document.getElementById("trad-setup-name");
  const codeInput = document.getElementById("trad-setup-code");
  const finyearInput = document.getElementById("trad-setup-finyear");
  const stateInput = document.getElementById("trad-setup-state");
  const userInput = document.getElementById("trad-setup-admin-user");
  const pwdInput = document.getElementById("trad-setup-admin-pwd");
  const confirmPwdInput = document.getElementById("trad-setup-confirm-pwd");

  if (nameInput) nameInput.value = "";
  if (codeInput && !codeInput.value) codeInput.value = "CORP01";
  if (finyearInput && !finyearInput.value) finyearInput.value = "2026-2027";
  if (stateInput && !stateInput.value) stateInput.value = "Tamilnadu";
  if (userInput && !userInput.value) userInput.value = "ADMIN";
  if (pwdInput) pwdInput.value = "";
  if (confirmPwdInput) confirmPwdInput.value = "";

  modal.style.display = "flex";
  if (nameInput) nameInput.focus();
}

function closeTraditionalSetupModal() {
  const modal = document.getElementById("modal-traditional-setup");
  if (modal) modal.style.display = "none";
  hideTraditionalSetupAlert();
  setTraditionalSetupLoading(false);
}

function showTraditionalSetupAlert(msg) {
  const alertBox = document.getElementById("trad-setup-alert");
  const alertText = document.getElementById("trad-setup-alert-text");
  if (alertBox && alertText) {
    alertText.textContent = msg;
    alertBox.style.display = "flex";
  }
}

function hideTraditionalSetupAlert() {
  const alertBox = document.getElementById("trad-setup-alert");
  if (alertBox) alertBox.style.display = "none";
}

function setTraditionalSetupLoading(isLoading) {
  isSubmittingTraditionalSetup = isLoading;
  const btnSubmit = document.getElementById("btn-submit-traditional-setup");
  const btnCancel = document.getElementById("btn-cancel-traditional-setup");
  const spinner = document.getElementById("trad-setup-spinner");
  const submitText = document.getElementById("trad-setup-submit-text");

  if (btnSubmit) btnSubmit.disabled = isLoading;
  if (btnCancel) btnCancel.disabled = isLoading;
  if (spinner) spinner.style.display = isLoading ? "inline-block" : "none";
  if (submitText) {
    submitText.textContent = isLoading ? "Authorizing with backend..." : "Authorize & Complete Setup \u2192";
  }
}

function handleTraditionalSetupSubmit() {
  if (isSubmittingTraditionalSetup) return; // Prevent duplicate submission

  const nameInput = document.getElementById("trad-setup-name");
  const codeInput = document.getElementById("trad-setup-code");
  const finyearInput = document.getElementById("trad-setup-finyear");
  const taxnoInput = document.getElementById("trad-setup-taxno");
  const stateInput = document.getElementById("trad-setup-state");
  const userInput = document.getElementById("trad-setup-admin-user");
  const pwdInput = document.getElementById("trad-setup-admin-pwd");
  const confirmPwdInput = document.getElementById("trad-setup-confirm-pwd");

  const name = (nameInput ? nameInput.value : "").trim();
  const code = (codeInput ? codeInput.value : "").trim().toUpperCase() || "CORP01";
  const finYear = (finyearInput ? finyearInput.value : "").trim() || "2026-2027";
  const taxNo = (taxnoInput ? taxnoInput.value : "").trim().toUpperCase() || null;
  const state = (stateInput ? stateInput.value : "").trim() || "Tamilnadu";
  const adminUsername = (userInput ? userInput.value : "").trim().toUpperCase() || "ADMIN";
  const adminPassword = pwdInput ? pwdInput.value : "";
  const confirmPassword = confirmPwdInput ? confirmPwdInput.value : "";

  // Validation
  if (!name) {
    showTraditionalSetupAlert("Company / Business Name is required.");
    if (nameInput) nameInput.focus();
    return;
  }
  if (!code) {
    showTraditionalSetupAlert("Company Code is required.");
    if (codeInput) codeInput.focus();
    return;
  }
  if (!adminUsername) {
    showTraditionalSetupAlert("Administrator Username is required.");
    if (userInput) userInput.focus();
    return;
  }
  if (!adminPassword) {
    showTraditionalSetupAlert("Administrator Password is required.");
    if (pwdInput) pwdInput.focus();
    return;
  }
  if (adminPassword.length < 4) {
    showTraditionalSetupAlert("Administrator Password must be at least 4 characters.");
    if (pwdInput) pwdInput.focus();
    return;
  }
  if (adminPassword !== confirmPassword) {
    showTraditionalSetupAlert("Passwords do not match. Please re-enter.");
    if (confirmPwdInput) confirmPwdInput.focus();
    return;
  }

  if (!window.backend || typeof window.backend.traditional_initialSetup !== "function") {
    showTraditionalSetupAlert("Backend service connection is unavailable. Cannot perform initial setup.");
    return;
  }

  setTraditionalSetupLoading(true);
  hideTraditionalSetupAlert();

  const payload = {
    name,
    code,
    finYear,
    taxNo,
    state,
    adminUsername,
    adminPassword,
  };

  window.backend.traditional_initialSetup(JSON.stringify(payload), (resp) => {
    setTraditionalSetupLoading(false);
    try {
      const res = typeof resp === "string" ? JSON.parse(resp) : resp;
      if (res && res.success) {
        showNotification("Traditional Billing company initialized successfully!");
        closeTraditionalSetupModal();
        // Refresh companies immediately
        fetchAndPopulateCompanies();
        // Pre-fill login user input with the newly created admin username
        if (loginUserInput) loginUserInput.value = adminUsername;
        if (loginPwdInput) {
          loginPwdInput.value = "";
          loginPwdInput.focus();
        }
      } else {
        const errMsg = (res && res.error) ? res.error : "Setup authorization failed. Please check setup token.";
        showTraditionalSetupAlert(errMsg);
      }
    } catch (e) {
      showTraditionalSetupAlert("Unexpected response from backend: " + e.message);
    }
  });
}

function initTraditionalSetupListeners() {
  const btnShowSetup = document.getElementById("btn-show-traditional-setup");
  const btnCloseModal = document.getElementById("btn-close-traditional-setup-modal");
  const btnCancel = document.getElementById("btn-cancel-traditional-setup");
  const formSetup = document.getElementById("form-traditional-setup");

  if (btnShowSetup) btnShowSetup.onclick = openTraditionalSetupModal;
  if (btnCloseModal) btnCloseModal.onclick = closeTraditionalSetupModal;
  if (btnCancel) btnCancel.onclick = closeTraditionalSetupModal;
  if (formSetup) {
    formSetup.onsubmit = (e) => {
      e.preventDefault();
      handleTraditionalSetupSubmit();
    };
  }
}

// =============================================================
// TRADITIONAL BILLING COMPANY & ADMINISTRATOR RECOVERY ENGINE
// =============================================================
let isSubmittingTraditionalRecovery = false;

function openTraditionalRecoveryModal() {
  const modal = document.getElementById("modal-traditional-recovery");
  if (!modal) return;
  hideTraditionalRecoveryAlert();
  setTraditionalRecoveryLoading(false);

  const compIdInput = document.getElementById("trad-recovery-company-id");
  const compNameInput = document.getElementById("trad-recovery-company-name");
  const compCodeInput = document.getElementById("trad-recovery-company-code");
  const finYearInput = document.getElementById("trad-recovery-finyear");
  const gstinInput = document.getElementById("trad-recovery-gstin");
  const stateInput = document.getElementById("trad-recovery-state");
  const adminIdInput = document.getElementById("trad-recovery-admin-id");
  const adminUserInput = document.getElementById("trad-recovery-admin-username");
  const newPwdInput = document.getElementById("trad-recovery-new-pwd");
  const confirmPwdInput = document.getElementById("trad-recovery-confirm-pwd");

  if (compIdInput) compIdInput.value = "";
  if (compNameInput) compNameInput.value = "Loading...";
  if (compCodeInput) compCodeInput.value = "Loading...";
  if (finYearInput) finYearInput.value = "";
  if (gstinInput) gstinInput.value = "";
  if (stateInput) stateInput.value = "";
  if (adminIdInput) adminIdInput.value = "";
  if (adminUserInput) adminUserInput.value = "";
  if (newPwdInput) newPwdInput.value = "";
  if (confirmPwdInput) confirmPwdInput.value = "";

  modal.style.display = "flex";

  let selectedCompId = "";
  if (loginCompanySelect && loginCompanySelect.value && Array.isArray(companies)) {
    const matched = companies.find((c) => c.code === loginCompanySelect.value);
    if (matched && matched.id) selectedCompId = matched.id;
  }

  if (window.backend && typeof window.backend.traditional_getCompanyRecoveryProfile === "function") {
    window.backend.traditional_getCompanyRecoveryProfile(selectedCompId, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.data) {
          const d = r.data;
          if (compIdInput) compIdInput.value = d.company_id || "";
          if (compNameInput) compNameInput.value = d.company_name || "";
          if (compCodeInput) compCodeInput.value = d.company_code || "";
          if (finYearInput) finYearInput.value = d.fin_year || "";
          if (gstinInput) gstinInput.value = d.gstin || "N/A";
          if (stateInput) stateInput.value = d.state || "N/A";
          if (adminIdInput) adminIdInput.value = d.admin_user_id || "";
          if (adminUserInput) adminUserInput.value = d.admin_username || "";
          if (compNameInput) compNameInput.focus();
        } else {
          showTraditionalRecoveryAlert(r && r.error ? r.error : "Failed to load recovery information.");
        }
      } catch (e) {
        showTraditionalRecoveryAlert("Error loading recovery profile: " + e.message);
      }
    });
  } else {
    // Fallback if backend not ready
    if (compNameInput) compNameInput.value = "";
    if (compCodeInput) compCodeInput.value = "";
  }
}

function closeTraditionalRecoveryModal() {
  const modal = document.getElementById("modal-traditional-recovery");
  if (modal) modal.style.display = "none";
  hideTraditionalRecoveryAlert();
  setTraditionalRecoveryLoading(false);
}

function showTraditionalRecoveryAlert(msg) {
  const alertBox = document.getElementById("trad-recovery-alert");
  const alertText = document.getElementById("trad-recovery-alert-text");
  if (alertBox && alertText) {
    alertText.textContent = msg;
    alertBox.style.display = "flex";
  }
}

function hideTraditionalRecoveryAlert() {
  const alertBox = document.getElementById("trad-recovery-alert");
  if (alertBox) alertBox.style.display = "none";
}

function setTraditionalRecoveryLoading(isLoading) {
  isSubmittingTraditionalRecovery = isLoading;
  const btnSubmit = document.getElementById("btn-submit-traditional-recovery");
  const btnCancel = document.getElementById("btn-cancel-traditional-recovery");
  const spinner = document.getElementById("trad-recovery-spinner");
  const submitText = document.getElementById("trad-recovery-submit-text");

  if (btnSubmit) btnSubmit.disabled = isLoading;
  if (btnCancel) btnCancel.disabled = isLoading;
  if (spinner) spinner.style.display = isLoading ? "inline-block" : "none";
  if (submitText) {
    submitText.textContent = isLoading ? "Authorizing Recovery..." : "Authorize & Apply Recovery →";
  }
}

function handleTraditionalRecoverySubmit() {
  if (isSubmittingTraditionalRecovery) return;

  const compIdInput = document.getElementById("trad-recovery-company-id");
  const compNameInput = document.getElementById("trad-recovery-company-name");
  const compCodeInput = document.getElementById("trad-recovery-company-code");
  const adminIdInput = document.getElementById("trad-recovery-admin-id");
  const adminUserInput = document.getElementById("trad-recovery-admin-username");
  const newPwdInput = document.getElementById("trad-recovery-new-pwd");
  const confirmPwdInput = document.getElementById("trad-recovery-confirm-pwd");

  const companyId = compIdInput ? compIdInput.value.trim() : "";
  const companyName = compNameInput ? compNameInput.value.trim() : "";
  const companyCode = compCodeInput ? compCodeInput.value.trim().toUpperCase() : "";
  const adminUserId = adminIdInput ? adminIdInput.value.trim() : "";
  const adminUsername = adminUserInput ? adminUserInput.value.trim().toUpperCase() : "";
  const newPwd = newPwdInput ? newPwdInput.value : "";
  const confirmPwd = confirmPwdInput ? confirmPwdInput.value : "";

  hideTraditionalRecoveryAlert();

  if (!companyId) {
    showTraditionalRecoveryAlert("Target company ID is missing.");
    return;
  }
  if (!companyName) {
    showTraditionalRecoveryAlert("Please enter a valid company name.");
    if (compNameInput) compNameInput.focus();
    return;
  }
  if (!companyCode) {
    showTraditionalRecoveryAlert("Please enter a valid company code.");
    if (compCodeInput) compCodeInput.focus();
    return;
  }
  if (!adminUsername) {
    showTraditionalRecoveryAlert("Please enter an Administrator username.");
    if (adminUserInput) adminUserInput.focus();
    return;
  }

  if (newPwd || confirmPwd) {
    if (newPwd.length < 4) {
      showTraditionalRecoveryAlert("Password must be at least 4 characters.");
      if (newPwdInput) newPwdInput.focus();
      return;
    }
    if (newPwd !== confirmPwd) {
      showTraditionalRecoveryAlert("New password and confirmation do not match.");
      if (confirmPwdInput) confirmPwdInput.focus();
      return;
    }
  }

  const payload = {
    company_id: companyId,
    company_name: companyName,
    company_code: companyCode,
    admin_user_id: adminUserId || undefined,
    admin_username: adminUsername,
    new_password: newPwd || undefined,
  };

  setTraditionalRecoveryLoading(true);

  if (window.backend && typeof window.backend.traditional_recoverCompanyAndAdmin === "function") {
    window.backend.traditional_recoverCompanyAndAdmin(JSON.stringify(payload), (resp) => {
      setTraditionalRecoveryLoading(false);
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res && res.success) {
          if (res.data && res.data.warning) {
            showNotification(res.data.warning);
          } else {
            showNotification(`Company and Administrator credentials recovered successfully!`);
          }
          closeTraditionalRecoveryModal();
          fetchAndPopulateCompanies();
          if (loginUserInput) loginUserInput.value = adminUsername;
          if (loginPwdInput) {
            loginPwdInput.value = "";
            loginPwdInput.focus();
          }
        } else {
          const errMsg = (res && res.error) ? res.error : "Recovery operation failed.";
          showTraditionalRecoveryAlert(errMsg);
        }
      } catch (e) {
        showTraditionalRecoveryAlert("Unexpected response from backend: " + e.message);
      }
    });
  } else {
    setTraditionalRecoveryLoading(false);
    showTraditionalRecoveryAlert("Backend recovery service not connected.");
  }
}

function initTraditionalRecoveryListeners() {
  const btnOpen = document.getElementById("btn-open-traditional-recovery");
  const btnClose = document.getElementById("btn-close-traditional-recovery-modal");
  const btnCancel = document.getElementById("btn-cancel-traditional-recovery");
  const formRecovery = document.getElementById("form-traditional-recovery");

  if (btnOpen) btnOpen.onclick = openTraditionalRecoveryModal;
  if (btnClose) btnClose.onclick = closeTraditionalRecoveryModal;
  if (btnCancel) btnCancel.onclick = closeTraditionalRecoveryModal;
  if (formRecovery) {
    formRecovery.onsubmit = (e) => {
      e.preventDefault();
      handleTraditionalRecoverySubmit();
    };
  }
}

window.openTraditionalRecoveryModal = openTraditionalRecoveryModal;
window.closeTraditionalRecoveryModal = closeTraditionalRecoveryModal;
window.handleTraditionalRecoverySubmit = handleTraditionalRecoverySubmit;
window.initTraditionalRecoveryListeners = initTraditionalRecoveryListeners;

function showLoginAlert(msg) {
  if (loginAlert && loginAlertText) {
    loginAlertText.textContent = msg;
    loginAlert.style.display = "flex";
  }
}

function hideLoginAlert() {
  if (loginAlert) {
    loginAlert.style.display = "none";
  }
}

function setLoginLoading(isLoading) {
  if (btnLoginSubmit) {
    btnLoginSubmit.disabled = isLoading;
  }
  if (loginBtnSpinner) {
    loginBtnSpinner.style.display = isLoading ? "inline-block" : "none";
  }
  if (loginBtnText) {
    loginBtnText.textContent = isLoading ? "Verifying..." : "Sign In →";
  }
}

function togglePasswordVisibility() {
  if (!loginPwdInput) return;
  const isPwd = loginPwdInput.type === "password";
  loginPwdInput.type = isPwd ? "text" : "password";
  if (pwdToggleIcon) {
    pwdToggleIcon.textContent = isPwd ? "Hide" : "Show";
  }
}

function handleMainLoginSubmit() {
  const companyCode = loginCompanySelect ? loginCompanySelect.value : "";
  const username = (loginUserInput ? loginUserInput.value : "").trim();
  const password = loginPwdInput ? loginPwdInput.value : "";

  if (!companyCode) {
    showLoginAlert("Please select a company.");
    if (loginCompanySelect) loginCompanySelect.focus();
    return;
  }
  if (!username) {
    showLoginAlert("Please enter your User ID / Username.");
    if (loginUserInput) loginUserInput.focus();
    return;
  }
  if (!password) {
    showLoginAlert("Please enter your password.");
    if (loginPwdInput) loginPwdInput.focus();
    return;
  }

  setLoginLoading(true);
  hideLoginAlert();
  if (window.BusinessContext) {
    window.BusinessContext.setAuthenticating();
  }

  const applyAuthSuccess = (authData) => {
    const sessionData = (authData && authData.company && authData.user && authData.branch)
      ? authData
      : {
          user: {
            id: authData.userId || authData.id,
            username: authData.username || username,
            displayName: authData.displayName || authData.username || username,
            role: authData.role
          },
          company: {
            id: authData.id || authData.companyId,
            code: authData.code || companyCode,
            name: authData.name,
            finYear: authData.finYear || "2026-2027",
            taxNo: authData.taxNo || authData.gstin,
            state: authData.state
          },
          branch: authData.branch || null
        };

    let sessionOk = false;
    if (window.BusinessContext) {
      sessionOk = window.BusinessContext.setAuthenticatedSession(sessionData);
    }
    if (!sessionOk) {
      applyAuthFailure("Authentication session initialization failed: Invalid session context.");
      return;
    }

    if (window.DashboardManager) {
      window.DashboardManager.initForSession();
    }
    activeCompany = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    if (loginPwdInput) loginPwdInput.value = "";
    if (activeLoginMode === "traditional") {
      enterCompanyDashboard(activeCompany);
    } else {
      openFastBillingPos();
    }
  };

  const applyAuthFailure = (errMsg) => {
    if (window.BusinessContext) {
      window.BusinessContext.clearAuthenticatedSession("invalid_credentials");
    }
    showLoginAlert(errMsg || "Invalid User ID or Password. Please try again.");
    if (loginPwdInput) {
      loginPwdInput.select();
      loginPwdInput.focus();
    }
  };

  if (activeLoginMode === "traditional" && window.backend && window.backend.traditional_authenticateUser) {
    window.backend.traditional_authenticateUser(companyCode, username, password, (resp) => {
      setLoginLoading(false);
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res.success && res.data) {
          applyAuthSuccess(res.data);
        } else {
          applyAuthFailure(res.error);
        }
      } catch (e) {
        applyAuthFailure("Authentication error: " + e.message);
      }
    });
  } else if (window.backend && window.backend.authenticateUser) {
    window.backend.authenticateUser(companyCode, username, password, (resp) => {
      setLoginLoading(false);
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res.success && res.data) {
          applyAuthSuccess(res.data);
        } else {
          applyAuthFailure(res.error);
        }
      } catch (e) {
        applyAuthFailure("Authentication error: " + e.message);
      }
    });
  } else {
    setLoginLoading(false);
    applyAuthFailure("Backend bridge connection is unavailable. Cannot authenticate without backend.");
  }
}

function selectCompanyFromList() {
  if (filteredCompanies.length === 0) return;
  const comp = filteredCompanies[selectedIndex];
  if (!comp) return;

  if (loginCompanySelect) {
    populateLoginCompanies();
    loginCompanySelect.value = comp.code;
  }
  if (loginUserInput) {
    loginUserInput.value = comp.username || "";
  }
  showScreen("view-login");
  if (loginPwdInput) {
    loginPwdInput.value = "";
    loginPwdInput.focus();
  }
}

function logoutUser() {
  if (currentScreen === "view-fast-billing" && posCart.length > 0) {
    const choice = confirm(
      `You have ${posCart.length} item(s) in your active POS cart.\n\n` +
      `Click OK to HOLD this sale before logging out, or CANCEL to stay in cart.`
    );
    if (choice) {
      if (btnPosHold) btnPosHold.click();
      posCart = [];
    } else {
      return;
    }
  }

  // Clear authenticated session and state
  if (window.BusinessContext) {
    window.BusinessContext.clearAuthenticatedSession("logout");
  }

  // Clear backend authenticated session
  if (window.backend && typeof window.backend.logout === "function") {
    try {
      window.backend.logout();
    } catch (e) {
      console.warn("Backend logout notification note:", e);
    }
  }

  // Clear dashboard components and stop live updates
  if (window.DashboardManager) {
    window.DashboardManager.clearDashboard();
  }

  activeCompany = null;
  if (loginPwdInput) loginPwdInput.value = "";
  hideLoginAlert();

  // Hide top header and sidebar
  const alphaTopHeader = document.getElementById("alpha-top-header");
  if (alphaTopHeader) alphaTopHeader.style.display = "none";
  const alphaSidebar = document.getElementById("alpha-sidebar");
  if (alphaSidebar) alphaSidebar.style.display = "none";

  showScreen("view-login");
  showNotification("Logged out successfully.");
}

// Legacy Modal Login Handlers
function openLoginModalForSelected() {
  selectCompanyFromList();
}

function closeLoginModal() {
  if (modalLogin) modalLogin.classList.remove("show");
  currentPendingCompany = null;
}

function handleLoginSubmit() {
  handleMainLoginSubmit();
}

// =============================================================
// DUAL BILLING MODE & INTERNAL TABS WORKFLOW
// =============================================================
function openBillingModeSelection(comp) {
  if (comp) activeCompany = comp;
  showScreen("view-mode-selection");
}

function renderModeSelection() {
  if (!activeCompany) return;
  const curUser = window.BusinessContext ? window.BusinessContext.getCurrentUser() : null;
  const curBranch = window.BusinessContext ? window.BusinessContext.getActiveBranch() : null;
  if (modeCompanyName) modeCompanyName.textContent = activeCompany.name;
  if (modeBranchName) modeBranchName.textContent = curBranch ? `${curBranch.name} (${curBranch.code || 'BR01'})` : (activeCompany.branch || "BR01");
  if (modeUserName) modeUserName.textContent = curUser ? `${curUser.displayName || curUser.username} (${curUser.role || 'User'})` : (activeCompany.username || "--");
  if (modeFyName) modeFyName.textContent = (activeCompany.finYear || activeCompany.fin_year || "2026-27").split(" ")[0];
  showNotification(`Logged in to ${activeCompany.name}`);
}

function activateBillingTab(tabKey) {
  activeBillingMode = tabKey;
  openTabs.add(tabKey);

  if (tabKey === "traditional") {
    if (tabModeIndicator) tabModeIndicator.textContent = "Mode: Traditional Billing";
    if (activeCompany) {
      if (dashboardWatermark) dashboardWatermark.textContent = `${activeCompany.name} (F.Y. ${activeCompany.finYear})`;
      if (statusCompName) statusCompName.textContent = `${activeCompany.name} (${activeCompany.code})`;
      if (statusFy) statusFy.textContent = (activeCompany.finYear || "2026-27").split(" ")[0];
      if (statusGstin) statusGstin.textContent = activeCompany.taxNo || "N/A";
      if (statusUser) statusUser.textContent = activeCompany.username || "A";
      if (statusState) statusState.textContent = activeCompany.state || "Tamilnadu";
    }
    showScreen(lastTraditionalScreen || "view-dashboard");
  } else if (tabKey === "fast_billing") {
    if (tabModeIndicator) tabModeIndicator.textContent = "Mode: Fast Billing (Cashier)";
    if (activeCompany) {
      if (posHeaderCompany) posHeaderCompany.textContent = activeCompany.name;
      if (posHeaderBranch) posHeaderBranch.textContent = "Branch: Main Branch | Reg: 01";
      if (posHeaderCashier) posHeaderCashier.textContent = `${activeCompany.username || "A"}`;
    }
    showScreen(lastFastBillingScreen || "view-fast-billing");
  }
  updateAppTabsDisplay(tabKey);
}

function updateAppTabsDisplay(activeKey) {
  if (tabBtnTraditional) {
    tabBtnTraditional.classList.toggle("active", activeKey === "traditional");
    tabBtnTraditional.style.display = openTabs.has("traditional") ? "inline-flex" : "none";
  }
  if (tabBtnFastBilling) {
    tabBtnFastBilling.classList.toggle("active", activeKey === "fast_billing");
    tabBtnFastBilling.style.display = openTabs.has("fast_billing") ? "inline-flex" : "none";
  }
  if (tabModeIndicator) {
    tabModeIndicator.textContent = activeKey === "traditional" ? "Mode: Traditional Billing" : "Mode: Fast Billing (Cashier)";
  }
}

function closeBillingTab(tabKey) {
  openTabs.delete(tabKey);
  if (openTabs.size === 0) {
    showScreen("view-mode-selection");
  } else {
    const remaining = [...openTabs][0];
    activateBillingTab(remaining);
  }
}

function enterCompanyDashboard(comp) {
  if (comp) activeCompany = comp;
  openTabs.add("traditional");
  lastTraditionalScreen = "view-dashboard";
  activateBillingTab("traditional");
  if (activeLoginMode !== "traditional") {
    fetchCustomerCategoryDiscounts();
    checkLowStockAlerts(true);
  }
  showNotification(`Traditional Billing: ${activeCompany ? activeCompany.name : ''}`);
}

function openFastBillingPos() {
  if (!activeCompany) return;
  openTabs.add("fast_billing");
  lastFastBillingScreen = "view-fast-billing";
  activateBillingTab("fast_billing");
  showNotification(`Fast Billing (POS): ${activeCompany.name}`);
}

function openFastBillingNewBill() {
  lastFastBillingScreen = "view-fast-billing";
  posCart = [];
  if (posTenderReceived) posTenderReceived.value = "";
  renderPosCart();
  initFastBillingScreen();
  showScreen("view-fast-billing");
  if (posBarcodeInput) {
    setTimeout(() => posBarcodeInput.focus(), 60);
  }
}

function openFastBillingHistory() {
  lastFastBillingScreen = "view-fast-billing-history";
  showScreen("view-fast-billing-history");
}

function openFastBillingReprint() {
  if (lastCompletedVoucherData) {
    openFastBillingPrint(lastCompletedVoucherData.voucher_id || lastCompletedVoucherData.id, lastCompletedVoucherData);
  } else if (todaySalesHistoryData && todaySalesHistoryData.length > 0) {
    const first = todaySalesHistoryData[0];
    openFastBillingPrint(first.id, first);
  } else {
    showNotification("No recent invoice found to reprint. Please select an invoice from Today's Sales History.");
    openFastBillingHistory();
  }
}

function openFastBillingPrint(vchId, vchData = null, sourceScreen = "view-fast-billing", voucherType = "sales_invoice", isReprint = false) {
  currentPrintVchId = vchId;
  currentPrintVchData = vchData;
  currentPrintVoucherType = voucherType || "sales_invoice";
  currentPrintIsReprint = !!isReprint;
  printSourceScreen = sourceScreen;
  lastFastBillingScreen = "view-fast-billing-print";

  if (posPrintCompany && activeCompany) {
    posPrintCompany.textContent = activeCompany.name;
  }

  // Populate installed system printers via bridge
  if (posPrinterSelect) {
    if (window.backend && window.backend.getAvailablePrinters) {
      window.backend.getAvailablePrinters((resp) => {
        try {
          const res = JSON.parse(resp);
          if (res.success && Array.isArray(res.data) && res.data.length > 0) {
            posPrinterSelect.innerHTML = res.data.map(p => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`).join("");
          }
        } catch (e) {}
      });
    }
  }

  // If full details not passed, fetch from backend via authoritative Phase 3 bridge
  if (!currentPrintVchData || !currentPrintVchData.items) {
    const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "";
    const mode = activeBillingMode || "traditional";
    if (window.backend && window.backend.getVoucherPrintDetails && vchId) {
      window.backend.getVoucherPrintDetails(compId, currentPrintVoucherType, vchId, mode, (resp) => {
        try {
          const res = JSON.parse(resp);
          if (res.success && res.data) {
            currentPrintVchData = res.data;
            if (posPrintVchNo) posPrintVchNo.textContent = res.data.vch_no || res.data.voucher_number || "VCH-001";
            renderInvoicePrintPreview();
          }
        } catch (e) {
          console.error("Error fetching voucher print details:", e);
        }
      });
    } else if (window.backend && window.backend.getVoucherDetails && vchId) {
      window.backend.getVoucherDetails(compId, vchId, (resp) => {
        try {
          const res = JSON.parse(resp);
          if (res.success && res.data) {
            currentPrintVchData = res.data;
            if (posPrintVchNo) posPrintVchNo.textContent = res.data.vch_no || "POS-001";
            renderInvoicePrintPreview();
          }
        } catch (e) {}
      });
    }
  } else {
    if (posPrintVchNo) posPrintVchNo.textContent = currentPrintVchData.vch_no || currentPrintVchData.voucher_number || "POS-001";
    renderInvoicePrintPreview();
  }

  showScreen("view-fast-billing-print");
}

function renderInvoicePrintPreview() {
  if (!posInvoicePreviewSheet) return;
  const vch = currentPrintVchData || {
    vch_no: "POS-001",
    vch_date: new Date().toLocaleDateString("en-IN"),
    created_at: new Date().toISOString(),
    party_name: "CASH",
    payment_method: "CASH",
    items: [],
    subtotal: 0,
    cgst_amount: 0,
    sgst_amount: 0,
    igst_amount: 0,
    round_off: 0,
    grand_total: 0
  };

  const comp = activeCompany || {
    name: "ANTI MATRIX",
    taxNo: "33AAAPL1234F1Z1",
    state: "Tamilnadu",
    username: "Admin"
  };

  const format = currentPrintPaperFormat || "thermal-80";
  const orient = currentPrintOrientation || "portrait";
  posInvoicePreviewSheet.className = `pos-invoice-sheet sheet-${format} orientation-${orient}`;
  posInvoicePreviewSheet.style.width = "";
  posInvoicePreviewSheet.style.minHeight = "";
  posInvoicePreviewSheet.style.maxWidth = "";

  if (format === "thermal-80" || format === "thermal-58") {
    renderThermalReceiptPreview(posInvoicePreviewSheet, comp, vch, format);
  } else if (format === "a4" || format === "a5") {
    renderTaxInvoiceSheetPreview(posInvoicePreviewSheet, comp, vch, format, null, null, orient);
  } else {
    // Custom dimensions
    const w = parseFloat(document.getElementById("custom-paper-width") ? document.getElementById("custom-paper-width").value : "80") || 80;
    const h = parseFloat(document.getElementById("custom-paper-height") ? document.getElementById("custom-paper-height").value : "150") || 150;
    let sheetW = w;
    let sheetH = h;
    if (orient === "landscape") {
      sheetW = h;
      sheetH = w;
    }
    posInvoicePreviewSheet.style.width = `${sheetW * 3.78}px`;
    posInvoicePreviewSheet.style.maxWidth = `${sheetW * 3.78}px`;
    posInvoicePreviewSheet.style.minHeight = `${sheetH * 3.78}px`;
    if (sheetW <= 85) {
      renderThermalReceiptPreview(posInvoicePreviewSheet, comp, vch, "thermal-80");
    } else {
      renderTaxInvoiceSheetPreview(posInvoicePreviewSheet, comp, vch, "custom", sheetW, sheetH, orient);
    }
  }
}

function renderThermalReceiptPreview(container, comp, vch, format) {
  const is58 = format === "thermal-58";
  const items = vch.items || [];
  const vchNo = vch.vch_no || vch.voucher_number || "POS-001";
  const dateStr = vch.vch_date || new Date().toLocaleDateString("en-IN");
  const timeStr = vch.created_at ? vch.created_at.substring(11, 16) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const party = vch.party_name || vch.customer_name || "CASH";
  const subtotal = parseFloat(vch.subtotal || 0).toFixed(2);
  const cgst = parseFloat(vch.cgst_amount || 0).toFixed(2);
  const sgst = parseFloat(vch.sgst_amount || 0).toFixed(2);
  const igst = parseFloat(vch.igst_amount || 0).toFixed(2);
  const roundOff = parseFloat(vch.round_off || 0).toFixed(2);
  const grandTotal = parseFloat(vch.grand_total || 0).toFixed(2);
  const payMethod = vch.payment_method || "CASH";
  const discTotal = parseFloat(vch.discount_total || 0);

  let itemsHtml = items.map((it) => {
    const name = it.item_name || it.name || "Item";
    const qty = parseFloat(it.qty || 0);
    const unit = it.unit || "Pcs.";
    const price = parseFloat(it.price || it.rate || 0).toFixed(2);
    const total = parseFloat(it.line_total || it.total || it.amount || (qty * price)).toFixed(2);
    if (is58) {
      return `
        <tr>
          <td colspan="2" style="padding-top: 3px; font-weight: 700; overflow-wrap: break-word; word-break: break-word;">${escapeHtml(name)}</td>
        </tr>
        <tr style="border-bottom: 1px dotted #e2e8f0;">
          <td style="padding-left: 6px; font-size: 8.5px; color: #475569;">${qty} ${unit} @ ₹${price}</td>
          <td style="text-align: right; font-weight: 700; font-size: 9.5px;">₹${total}</td>
        </tr>
      `;
    }
    return `
      <tr>
        <td style="overflow-wrap: break-word; word-break: break-word; padding-right: 4px;">${escapeHtml(name)}</td>
        <td style="text-align: center;">${qty} ${unit}</td>
        <td style="text-align: right;">${price}</td>
        <td style="text-align: right; font-weight: 700;">${total}</td>
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div class="thermal-receipt-view">
      <div class="t-center t-title">${escapeHtml(comp.name.toUpperCase())}</div>
      <div class="t-center t-sub">RETAIL CASH RECEIPT / TAX INVOICE</div>
      ${comp.taxNo ? `<div class="t-center t-sub">GSTIN: ${escapeHtml(comp.taxNo)}</div>` : ""}
      <div class="t-divider"></div>
      <div class="t-row"><span>Bill No: <strong>${escapeHtml(vchNo)}</strong></span><span>Date: ${escapeHtml(dateStr)} ${escapeHtml(timeStr)}</span></div>
      <div class="t-row"><span>Customer: ${escapeHtml(party)}</span><span>Cashier: ${escapeHtml(comp.username || "Admin")}</span></div>
      <div class="t-divider"></div>
      <table class="t-table">
        <thead>
          ${is58 ? `<tr><th style="width: 55%;">Item</th><th style="width: 45%; text-align: right;">Total</th></tr>` :
                   `<tr><th style="width: 44%;">Item</th><th style="width: 16%; text-align: center;">Qty</th><th style="width: 20%; text-align: right;">Price</th><th style="width: 20%; text-align: right;">Total</th></tr>`}
        </thead>
        <tbody>
          ${itemsHtml || '<tr><td colspan="4" style="text-align: center; padding: 10px;">No items</td></tr>'}
        </tbody>
      </table>
      <div class="t-divider"></div>
      <div class="t-row"><span>Subtotal:</span><span>₹ ${subtotal}</span></div>
      ${discTotal > 0 ? `<div class="t-row" style="color: #047857;"><span>Discount:</span><span>- ₹ ${discTotal.toFixed(2)}</span></div>` : ""}
      ${parseFloat(cgst) > 0 ? `<div class="t-row"><span>CGST:</span><span>₹ ${cgst}</span></div>` : ""}
      ${parseFloat(sgst) > 0 ? `<div class="t-row"><span>SGST:</span><span>₹ ${sgst}</span></div>` : ""}
      ${parseFloat(igst) > 0 ? `<div class="t-row"><span>IGST:</span><span>₹ ${igst}</span></div>` : ""}
      ${parseFloat(roundOff) !== 0 ? `<div class="t-row"><span>Round Off:</span><span>₹ ${roundOff}</span></div>` : ""}
      <div class="t-double-divider"></div>
      <div class="t-grand-total"><span>PAYABLE:</span><span>₹ ${grandTotal}</span></div>
      <div class="t-double-divider"></div>
      <div class="t-row"><span>Paid By: <strong>${escapeHtml(payMethod)}</strong></span><span>Status: PAID</span></div>
      ${vch.amount_in_words ? `<div class="t-sub" style="font-size: 8.5px; font-style: italic; margin-top: 4px; overflow-wrap: break-word; word-break: break-word;">Words: ${escapeHtml(vch.amount_in_words)}</div>` : ""}
      <div class="t-divider"></div>
      <div class="t-center t-sub" style="margin-top: 4px;">*** THANK YOU FOR SHOPPING! ***</div>
      <div class="t-center t-sub">Goods once sold cannot be returned.</div>
      <div class="t-center t-sub" style="font-size: 8.5px; color: #666; margin-top: 3px;">Powered by Alpha Billing ERP</div>
    </div>
  `;
}

function renderTaxInvoiceSheetPreview(container, comp, vch, format, customW = null, customH = null, orient = "portrait") {
  const isA5 = format === "a5";
  const items = vch.items || [];
  const vchNo = vch.vch_no || vch.voucher_number || "POS-001";
  const dateStr = vch.vch_date || new Date().toLocaleDateString("en-IN");
  const party = vch.party_name || vch.customer_name || "CASH";
  const subtotal = parseFloat(vch.subtotal || 0).toFixed(2);
  const cgst = parseFloat(vch.cgst_amount || 0).toFixed(2);
  const sgst = parseFloat(vch.sgst_amount || 0).toFixed(2);
  const igst = parseFloat(vch.igst_amount || 0).toFixed(2);
  const roundOff = parseFloat(vch.round_off || 0).toFixed(2);
  const grandTotal = parseFloat(vch.grand_total || 0).toFixed(2);
  const payMethod = vch.payment_method || "CASH";
  const discTotal = parseFloat(vch.discount_total || 0);
  const words = vch.amount_in_words || "";

  let itemsHtml = items.map((it, idx) => {
    const name = it.item_name || it.name || "Item";
    const qty = parseFloat(it.qty || 0);
    const unit = it.unit || "Pcs.";
    const price = parseFloat(it.price || it.rate || 0).toFixed(2);
    const taxRate = parseFloat(it.tax_rate || it.gst_rate || 18);
    const discPct = parseFloat(it.discount_percent || 0);
    const total = parseFloat(it.line_total || it.total || it.amount || (qty * price)).toFixed(2);

    return `
      <tr>
        <td style="text-align: center; padding: ${isA5 ? '3px 2px' : '5px 4px'}; border-bottom: 1px solid #e2e8f0;">${idx + 1}</td>
        <td style="padding: ${isA5 ? '3px 4px' : '5px 6px'}; border-bottom: 1px solid #e2e8f0; overflow-wrap: break-word; word-break: break-word;">
          <strong>${escapeHtml(name)}</strong>
          ${it.hsn ? `<span style="font-size: ${isA5 ? '7px' : '8.5px'}; color: #64748b; margin-left: 4px;">[HSN: ${escapeHtml(it.hsn)}]</span>` : ''}
        </td>
        <td style="text-align: center; padding: ${isA5 ? '3px 2px' : '5px 4px'}; border-bottom: 1px solid #e2e8f0;">${qty} ${unit}</td>
        <td style="text-align: right; padding: ${isA5 ? '3px 4px' : '5px 6px'}; border-bottom: 1px solid #e2e8f0; font-variant-numeric: tabular-nums;">₹ ${price}</td>
        <td style="text-align: center; padding: ${isA5 ? '3px 2px' : '5px 4px'}; border-bottom: 1px solid #e2e8f0;">${discPct > 0 ? `${discPct}%` : '-'}</td>
        <td style="text-align: center; padding: ${isA5 ? '3px 2px' : '5px 4px'}; border-bottom: 1px solid #e2e8f0;">${taxRate}%</td>
        <td style="text-align: right; font-weight: 700; padding: ${isA5 ? '3px 4px' : '5px 6px'}; border-bottom: 1px solid #e2e8f0; font-variant-numeric: tabular-nums;">₹ ${total}</td>
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: ${isA5 ? '10px' : '14px'}; font-size: ${isA5 ? '9.5px' : '11px'}; width: 100%; box-sizing: border-box; overflow: hidden;">
      <!-- Invoice Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1e3a8a; padding-bottom: 8px; width: 100%; box-sizing: border-box;">
        <div style="min-width: 0; flex: 1 1 auto;">
          <h1 style="margin: 0; font-size: ${isA5 ? '15px' : '19px'}; color: #1e3a8a; font-weight: 900; line-height: 1.2;">${escapeHtml(comp.name)}</h1>
          <div style="color: #475569; margin-top: 3px; font-size: ${isA5 ? '8.5px' : '10px'};">State: ${escapeHtml(comp.state || "Tamilnadu")} | Reg. Business Entity</div>
          <div style="color: #1e293b; font-weight: 700; margin-top: 2px; font-size: ${isA5 ? '8.5px' : '10px'};">GSTIN: ${escapeHtml(comp.taxNo || "N/A")}</div>
        </div>
        <div style="text-align: right; flex: 0 0 auto; margin-left: 12px;">
          <span style="display: inline-block; background: #1e3a8a; color: #fff; padding: 3px 10px; font-weight: 800; font-size: ${isA5 ? '10px' : '12px'}; border-radius: 3px; letter-spacing: 0.5px;">TAX INVOICE</span>
          <div style="margin-top: 4px; font-weight: 700;">Invoice No: <span style="color: #047857;">${escapeHtml(vchNo)}</span></div>
          <div style="color: #64748b; font-size: ${isA5 ? '8.5px' : '9.5px'};">Date: ${escapeHtml(dateStr)}</div>
        </div>
      </div>

      <!-- Bill To & Details Grid -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; background: #f8fafc; padding: 8px 10px; border-radius: 4px; border: 1px solid #e2e8f0; width: 100%; box-sizing: border-box;">
        <div style="min-width: 0; overflow-wrap: break-word;">
          <div style="font-weight: 700; color: #64748b; font-size: ${isA5 ? '8px' : '9px'}; text-transform: uppercase;">Billed To Customer:</div>
          <div style="font-size: ${isA5 ? '11px' : '12.5px'}; font-weight: 800; color: #0f172a; margin-top: 2px; overflow-wrap: break-word;">${escapeHtml(party)}</div>
          <div style="color: #475569; font-size: ${isA5 ? '8.5px' : '9.5px'};">Payment Method: <strong>${escapeHtml(payMethod)}</strong></div>
        </div>
        <div style="text-align: right; min-width: 0;">
          <div style="font-weight: 700; color: #64748b; font-size: ${isA5 ? '8px' : '9px'}; text-transform: uppercase;">Counter Details:</div>
          <div style="color: #0f172a; font-weight: 600; font-size: ${isA5 ? '9px' : '10.5px'};">Cashier: ${escapeHtml(comp.username || "Admin")}</div>
          <div style="color: #64748b; font-size: ${isA5 ? '8.5px' : '9.5px'};">Place of Supply: ${escapeHtml(comp.state || "Tamilnadu")}</div>
        </div>
      </div>

      <!-- Table of items (Strictly Proportional and Contained) -->
      <table style="width: 100%; border-collapse: collapse; margin-top: 4px; table-layout: fixed; box-sizing: border-box;">
        <thead>
          <tr style="background: #1e40af; color: #ffffff; font-size: ${isA5 ? '8.5px' : '10px'};">
            <th style="padding: ${isA5 ? '4px 2px' : '6px 4px'}; width: 5%; text-align: center; box-sizing: border-box;">#</th>
            <th style="padding: ${isA5 ? '4px 4px' : '6px 6px'}; width: 37%; text-align: left; box-sizing: border-box; overflow-wrap: break-word;">Item Description</th>
            <th style="padding: ${isA5 ? '4px 2px' : '6px 4px'}; width: 11%; text-align: center; box-sizing: border-box;">Qty</th>
            <th style="padding: ${isA5 ? '4px 4px' : '6px 6px'}; width: 13%; text-align: right; box-sizing: border-box;">Price</th>
            <th style="padding: ${isA5 ? '4px 2px' : '6px 4px'}; width: 8%; text-align: center; box-sizing: border-box;">Disc</th>
            <th style="padding: ${isA5 ? '4px 2px' : '6px 4px'}; width: 9%; text-align: center; box-sizing: border-box;">Tax %</th>
            <th style="padding: ${isA5 ? '4px 4px' : '6px 6px'}; width: 17%; text-align: right; box-sizing: border-box;">Amount</th>
          </tr>
        </thead>
        <tbody style="border-bottom: 1px solid #cbd5e1; font-size: ${isA5 ? '8.5px' : '10px'};">
          ${itemsHtml || '<tr><td colspan="7" style="text-align: center; padding: 12px;">No items</td></tr>'}
        </tbody>
      </table>

      <!-- Totals & Terms Section (Perfect Right Alignment) -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; margin-top: 6px; width: 100%; box-sizing: border-box; min-width: 0;">
        <div style="flex: 1 1 50%; max-width: 55%; font-size: ${isA5 ? '8px' : '9px'}; color: #64748b; min-width: 0; overflow-wrap: break-word; line-height: 1.35;">
          <strong>Terms &amp; Conditions:</strong><br />
          1. Goods once sold will not be taken back or exchanged.<br />
          2. All disputes are subject to local jurisdiction.<br />
          3. This is a computer-generated tax invoice.
        </div>
        <div style="flex: 0 0 ${isA5 ? '180px' : '230px'}; display: flex; flex-direction: column; gap: 3px; min-width: 0; box-sizing: border-box; font-size: ${isA5 ? '9px' : '10.5px'};">
          <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;"><span>Taxable Subtotal:</span><span style="font-variant-numeric: tabular-nums;">₹ ${subtotal}</span></div>
          ${discTotal > 0 ? `<div style="display: flex; justify-content: space-between; align-items: center; color: #047857; width: 100%;"><span>Discount:</span><span style="font-variant-numeric: tabular-nums;">- ₹ ${discTotal.toFixed(2)}</span></div>` : ""}
          ${parseFloat(cgst) > 0 ? `<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;"><span>CGST:</span><span style="font-variant-numeric: tabular-nums;">₹ ${cgst}</span></div>` : ""}
          ${parseFloat(sgst) > 0 ? `<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;"><span>SGST:</span><span style="font-variant-numeric: tabular-nums;">₹ ${sgst}</span></div>` : ""}
          ${parseFloat(igst) > 0 ? `<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;"><span>IGST:</span><span style="font-variant-numeric: tabular-nums;">₹ ${igst}</span></div>` : ""}
          ${parseFloat(roundOff) !== 0 ? `<div style="display: flex; justify-content: space-between; align-items: center; width: 100%;"><span>Round Off:</span><span style="font-variant-numeric: tabular-nums;">₹ ${roundOff}</span></div>` : ""}
          <div style="display: flex; justify-content: space-between; align-items: center; font-size: ${isA5 ? '11.5px' : '13px'}; font-weight: 900; color: #047857; border-top: 2px solid #047857; border-bottom: 2px solid #047857; padding: 4px 0; margin-top: 3px; width: 100%;">
            <span>GRAND TOTAL:</span><span style="font-variant-numeric: tabular-nums;">₹ ${grandTotal}</span>
          </div>
        </div>
      </div>

      <!-- Amount in Words -->
      ${words ? `
        <div style="font-size: ${isA5 ? '8px' : '9px'}; font-style: italic; color: #475569; width: 100%; border-top: 1px dotted #cbd5e1; padding-top: 3px; box-sizing: border-box; overflow-wrap: break-word;">
          <b>Amount in Words:</b> ${escapeHtml(words)}
        </div>
      ` : ''}

      <!-- Signature Box -->
      <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: ${isA5 ? '12px' : '24px'}; width: 100%; box-sizing: border-box;">
        <div style="font-size: ${isA5 ? '8px' : '9px'}; color: #94a3b8;">E. &amp; O.E.</div>
        <div style="text-align: center; border-top: 1px dashed #64748b; width: ${isA5 ? '140px' : '180px'}; padding-top: 4px; font-size: ${isA5 ? '9px' : '10.5px'}; font-weight: 700;">
          Authorized Signatory<br />
          <span style="font-size: ${isA5 ? '7.5px' : '8.5px'}; color: #64748b; font-weight: normal;">For ${escapeHtml(comp.name)}</span>
        </div>
      </div>
    </div>
  `;
}

function triggerInvoicePrint() {
  if (!currentPrintVchId && (!currentPrintVchData || (!currentPrintVchData.vch_no && !currentPrintVchData.voucher_number))) {
    showNotification("No invoice loaded to print.");
    return;
  }
  const copiesInput = document.getElementById("pos-print-copies");
  const copies = parseInt(copiesInput ? copiesInput.value : 1) || 1;
  const printerSelect = document.getElementById("pos-printer-select");
  const printerName = printerSelect ? printerSelect.value : "Default Printer";
  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  const vchId = currentPrintVchId || (currentPrintVchData ? (currentPrintVchData.id || currentPrintVchData.voucher_id || currentPrintVchData.vch_no) : "");
  const vchType = currentPrintVoucherType || "sales_invoice";
  const mode = activeBillingMode || "traditional";
  const isReprint = !!currentPrintIsReprint;

  if (printStatusMsg) {
    printStatusMsg.style.display = "block";
    printStatusMsg.className = "print-status-box info";
    printStatusMsg.textContent = `${isReprint ? 'Reprinting' : 'Printing'} ${copies} cop${copies === 1 ? 'y' : 'ies'} of ${vchType} to ${printerName}...`;
  }

  // Phase 3 Authoritative Print Bridge
  if (window.backend && (window.backend.printVoucherRecord || window.backend.reprintVoucher)) {
    const slotMethod = isReprint && window.backend.reprintVoucher
      ? window.backend.reprintVoucher
      : window.backend.printVoucherRecord;

    slotMethod(compId, vchType, vchId, currentPrintPaperFormat, printerName, copies, mode, (resp) => {
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res.success) {
          const vNum = (res.data && (res.data.voucher_number || res.data.vch_no)) ? (res.data.voucher_number || res.data.vch_no) : vchId;
          if (printStatusMsg) {
            printStatusMsg.className = "print-status-box success";
            printStatusMsg.textContent = `✅ Successfully ${isReprint ? 'reprinted' : 'printed'} ${copies} cop${copies === 1 ? 'y' : 'ies'} of ${vchType} #${vNum} on ${printerName}.`;
          }
          showNotification(`${isReprint ? 'Reprinted' : 'Printed'} ${copies} copy of #${vNum}`);
        } else {
          if (printStatusMsg) {
            printStatusMsg.className = "print-status-box error";
            printStatusMsg.textContent = `Printer Notice: ${res.error}. Transaction is safely preserved. You can retry printing anytime.`;
          }
        }
      } catch (e) {
        if (printStatusMsg) {
          printStatusMsg.className = "print-status-box success";
          printStatusMsg.textContent = `✅ Printed ${copies} copy to ${printerName}. (Simulated)`;
        }
      }
    });
    return;
  }

  if (window.backend && window.backend.printInvoice) {
    window.backend.printInvoice(compId, vchId, currentPrintPaperFormat, printerName, copies, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success) {
          if (printStatusMsg) {
            printStatusMsg.className = "print-status-box success";
            printStatusMsg.textContent = `✅ Successfully printed ${copies} cop${copies === 1 ? 'y' : 'ies'} of Bill #${res.data.vch_no} to ${printerName}.`;
          }
          showNotification(`Printed ${copies} copy of Bill #${res.data.vch_no}`);
        } else {
          if (printStatusMsg) {
            printStatusMsg.className = "print-status-box error";
            printStatusMsg.textContent = `Printer Notice: ${res.error}. Transaction is safely preserved. You can retry printing anytime.`;
          }
        }
      } catch (e) {
        if (printStatusMsg) {
          printStatusMsg.className = "print-status-box success";
          printStatusMsg.textContent = `✅ Printed ${copies} copy to ${printerName}. (Simulated)`;
        }
      }
    });
  } else {
    // Local fallback
    if (printStatusMsg) {
      printStatusMsg.className = "print-status-box success";
      printStatusMsg.textContent = `✅ Successfully printed ${copies} cop${copies === 1 ? 'y' : 'ies'} of Bill #${currentPrintVchData ? (currentPrintVchData.vch_no || currentPrintVchData.voucher_number) : 'POS-001'} to ${printerName}.`;
    }
    showNotification(`Printed ${copies} copy to ${printerName}`);
  }
}

function renderFastBillingHistory() {
  const tbody = document.getElementById("pos-history-tbody");
  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 24px; color: #64748b;">Loading today's sales invoices...</td></tr>`;

  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  const branchId = (activeCompany ? activeCompany.branchId : "") || "";

  if (posHistoryCompany && activeCompany) posHistoryCompany.textContent = activeCompany.name;
  if (posHistoryBranch && activeCompany) posHistoryBranch.textContent = `Branch: ${activeCompany.branch || "Main"}`;
  if (posHistoryCashier && activeCompany) posHistoryCashier.textContent = activeCompany.username || "Admin";

  const onDataLoaded = (vouchers) => {
    todaySalesHistoryData = vouchers || [];
    renderTodaySalesTable(todaySalesHistoryData);
  };

  if (window.backend && window.backend.getTodaySalesHistory) {
    window.backend.getTodaySalesHistory(compId, branchId, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success) {
          onDataLoaded(res.data);
        } else {
          tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: #ef4444;">Failed to load today's sales: ${res.error}</td></tr>`;
        }
      } catch (e) {
        tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 20px; color: #ef4444;">Error: ${e}</td></tr>`;
      }
    });
  } else {
    // Local storage fallback for dev/offline
    const saved = JSON.parse(localStorage.getItem(`alpha_sales_${activeCompany ? activeCompany.code : 'COMP0001'}`) || "[]");
    onDataLoaded(saved);
  }
}

function renderTodaySalesTable(vouchers) {
  const tbody = document.getElementById("pos-history-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  // Update summary KPIs
  let totalAmt = 0;
  let cashAmt = 0;
  let digitalAmt = 0;

  vouchers.forEach((vch) => {
    const amt = parseFloat(vch.grand_total || 0);
    totalAmt += amt;
    const method = (vch.payment_method || "CASH").toUpperCase();
    if (method === "CASH") cashAmt += amt;
    else digitalAmt += amt;
  });

  if (posHistoryCount) posHistoryCount.textContent = `${vouchers.length} Bill${vouchers.length === 1 ? '' : 's'}`;
  if (posHistoryTotalAmt) posHistoryTotalAmt.textContent = `₹ ${totalAmt.toFixed(2)}`;
  if (posHistoryCashAmt) posHistoryCashAmt.textContent = `₹ ${cashAmt.toFixed(2)}`;
  if (posHistoryDigitalAmt) posHistoryDigitalAmt.textContent = `₹ ${digitalAmt.toFixed(2)}`;

  if (vouchers.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: #64748b; font-size: 13px;">No sales invoices created today yet. Click <strong>New Bill (F4)</strong> to start your first checkout.</td></tr>`;
    return;
  }

  vouchers.forEach((vch) => {
    const tr = document.createElement("tr");
    const dateFormatted = vch.created_at ? vch.created_at.substring(0, 16) : (vch.vch_date || "Today");
    const method = vch.payment_method || "CASH";
    const status = vch.payment_status || "PAID";

    tr.innerHTML = `
      <td><strong style="color: #1e40af;">#${escapeHtml(vch.vch_no || "-")}</strong></td>
      <td style="color: #475569;">${escapeHtml(dateFormatted)}</td>
      <td><strong>${escapeHtml(vch.party_name || "CASH")}</strong></td>
      <td style="text-align: center;"><span class="badge-payment-method ${method.toLowerCase()}">${escapeHtml(method)}</span></td>
      <td style="text-align: right; font-weight: 800; color: #047857;">₹ ${parseFloat(vch.grand_total || 0).toFixed(2)}</td>
      <td style="text-align: center;"><span class="badge-status success">${escapeHtml(status)}</span></td>
      <td style="text-align: center;">
        <button type="button" class="btn-table-action reprint-btn btn-history-reprint" data-id="${escapeHtml(vch.id)}" data-vchno="${escapeHtml(vch.vch_no || '')}">
          🖨️ View &amp; Reprint
        </button>
      </td>
    `;

    const btnReprint = tr.querySelector(".btn-history-reprint");
    if (btnReprint) {
      btnReprint.addEventListener("click", () => {
        openFastBillingPrint(vch.id, vch);
      });
    }

    tbody.appendChild(tr);
  });
}

function navigateAwayFromPos(targetScreen = "view-mode-selection") {
  if (posCart.length > 0) {
    const choice = confirm(
      `You have ${posCart.length} item(s) in your active POS cart.\n\n` +
      `Click OK to HOLD this sale before leaving, or CANCEL to return to cart.`
    );
    if (choice) {
      if (btnPosHold) btnPosHold.click();
      showScreen(targetScreen);
    }
    return;
  }
  showScreen(targetScreen);
}

function closeCompany() {
  logoutUser();
}

// =============================================================
// CREATE COMPANY
// =============================================================
function openCreateCompanyModal() {
  newCompName.value = "";
  newCompCode.value = generateNextCompanyCode();
  newCompFinyear.value = "2026-2027 (1 Yr)";
  newCompGstin.value = "";
  newCompState.value = "Tamilnadu";
  newCompUser.value = "A";
  newCompPass.value = "";

  modalCreateCompany.classList.add("show");
  setTimeout(() => newCompName.focus(), 50);
}

function closeCreateCompanyModal() {
  modalCreateCompany.classList.remove("show");
  if (currentScreen === "view-companies") {
    searchInput.focus();
  }
}

function handleCreateCompanySubmit() {
  const name = newCompName.value.trim().toUpperCase();
  if (!name) {
    alert("Please enter a valid Company Name.");
    newCompName.focus();
    return;
  }

  const newComp = {
    id: newCompCode.value,
    name: name,
    code: newCompCode.value,
    finYear: newCompFinyear.value.trim() || "2026-2027 (1 Yr)",
    taxNo: newCompGstin.value.trim().toUpperCase(),
    state: newCompState.value.trim() || "Tamilnadu",
    username: newCompUser.value.trim() || "A",
    password: newCompPass.value
  };

  if (window.backend) {
    window.backend.createCompany(JSON.stringify(newComp), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          syncFromBackend();
        }
      } catch (e) {}
    });
  }

  companies.push(newComp);
  saveCompanies();

  closeCreateCompanyModal();
  filteredCompanies = [...companies];
  selectedIndex = companies.length - 1;
  renderCompanyTable();
  showNotification(`Company "${newComp.name}" created successfully!`);
}

// =============================================================
// CONFIGURATION MODAL (FEATURES / OPTIONS)
// =============================================================
function openConfigurationModal() {
  if (!activeCompany) return;
  const cfg = getCompanyConfig(activeCompany.code);
  cfgVchStart.value = cfg.vchStart || 1;
  cfgVchDigits.value = cfg.vchDigits || 3;
  cfgVchPrefix.value = cfg.vchPrefix || "";
  cfgDefaultTax.value = cfg.defaultTax || "18";
  cfgAutoRound.value = cfg.autoRound || "Y";

  const commEl = document.getElementById("cfg-disc-commercial");
  const subEl = document.getElementById("cfg-disc-sub-commercial");
  const dirEl = document.getElementById("cfg-disc-direct");

  if (commEl) commEl.value = cachedCategoryDiscounts["Commercial"] ?? 5.0;
  if (subEl) subEl.value = cachedCategoryDiscounts["Sub-Commercial"] ?? 2.5;
  if (dirEl) dirEl.value = cachedCategoryDiscounts["Direct Customer"] ?? 0.0;

  if (window.backend && window.backend.getCustomerCategoryDiscounts) {
    window.backend.getCustomerCategoryDiscounts(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          cachedCategoryDiscounts = r.data;
          if (commEl) commEl.value = r.data["Commercial"] ?? 5.0;
          if (subEl) subEl.value = r.data["Sub-Commercial"] ?? 2.5;
          if (dirEl) dirEl.value = r.data["Direct Customer"] ?? 0.0;
        }
      } catch (e) {}
    });
  }

  modalConfiguration.classList.add("show");
}

function closeConfigurationModal() {
  modalConfiguration.classList.remove("show");
}

function handleSaveConfiguration() {
  if (!activeCompany) return;
  const config = {
    vchStart: parseInt(cfgVchStart.value, 10) || 1,
    vchDigits: parseInt(cfgVchDigits.value, 10) || 3,
    vchPrefix: cfgVchPrefix.value.trim(),
    defaultTax: cfgDefaultTax.value,
    autoRound: cfgAutoRound.value
  };

  const commEl = document.getElementById("cfg-disc-commercial");
  const subEl = document.getElementById("cfg-disc-sub-commercial");
  const dirEl = document.getElementById("cfg-disc-direct");

  const commVal = parseFloat(commEl ? commEl.value : "5.0");
  const subVal = parseFloat(subEl ? subEl.value : "2.5");
  const dirVal = parseFloat(dirEl ? dirEl.value : "0.0");

  if (isNaN(commVal) || commVal < 0 || commVal > 100 ||
      isNaN(subVal) || subVal < 0 || subVal > 100 ||
      isNaN(dirVal) || dirVal < 0 || dirVal > 100) {
    alert("Discount percentages must be between 0.00% and 100.00%.");
    return;
  }

  const newDiscounts = {
    "Commercial": commVal,
    "Sub-Commercial": subVal,
    "Direct Customer": dirVal
  };

  if (window.backend && window.backend.setCustomerCategoryDiscounts) {
    window.backend.setCustomerCategoryDiscounts(activeCompany.id, JSON.stringify(newDiscounts), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          cachedCategoryDiscounts = r.data;
          updatePosCustomerCategoryBadge();
          updateVoucherPartyCategory();
        }
      } catch (e) {}
    });
  } else {
    cachedCategoryDiscounts = newDiscounts;
  }

  saveCompanyConfig(activeCompany.code, config);
  closeConfigurationModal();
  showNotification("Configuration and Customer Category Discounts saved!");
}

// =============================================================
// ACCOUNT MASTER & THREE-OPTION WORKFLOW STATE
// =============================================================
let currentModifySaleVchId = null;
let isSalesModifyMode = false;
let currentModifyPurchaseVchId = null;
let isPurchaseModifyMode = false;
let isSavingAccount = false;

function syncAccountPrintName() {
  if (accPrintName && accName) {
    accPrintName.value = accName.value;
  }
}

function resetAccountMasterAddForm() {
  if (formAccountMaster) formAccountMaster.reset();
  const idEl = document.getElementById("acc-id");
  if (idEl) idEl.value = "";
  const codeEl = document.getElementById("acc-code");
  if (codeEl) codeEl.value = "";
  if (accName) accName.value = "";
  if (accAlias) accAlias.value = "";
  if (accPrintName) accPrintName.value = "";

  const groupEl = document.getElementById("acc-group");
  if (groupEl) groupEl.value = "Sundry Debtors";
  const opBalEl = document.getElementById("acc-op-bal");
  if (opBalEl) opBalEl.value = "0.00";
  const opTypeEl = document.getElementById("acc-op-type");
  if (opTypeEl) opTypeEl.value = "D";
  const prevBalEl = document.getElementById("acc-prev-bal");
  if (prevBalEl) prevBalEl.value = "0.00";
  const prevTypeEl = document.getElementById("acc-prev-type");
  if (prevTypeEl) prevTypeEl.value = "D";
  const addr1El = document.getElementById("acc-addr1");
  if (addr1El) addr1El.value = "";
  const addr2El = document.getElementById("acc-addr2");
  if (addr2El) addr2El.value = "";
  const countryEl = document.getElementById("acc-country");
  if (countryEl) countryEl.value = "India";
  const stateEl = document.getElementById("acc-state");
  if (stateEl) stateEl.value = "Tamilnadu";
  const dealerEl = document.getElementById("acc-dealer-type");
  if (dealerEl) dealerEl.value = "Unregistered";
  const catEl = document.getElementById("acc-customer-category");
  if (catEl) catEl.value = "Direct Customer";
  const gstinEl = document.getElementById("acc-gstin");
  if (gstinEl) gstinEl.value = "";
  const mobEl = document.getElementById("acc-mobile");
  if (mobEl) mobEl.value = "";
  const waEl = document.getElementById("acc-whatsapp");
  if (waEl) waEl.value = "";
  const bankNameEl = document.getElementById("acc-bank-name");
  if (bankNameEl) bankNameEl.value = "";
  const bankAccEl = document.getElementById("acc-bank-acc");
  if (bankAccEl) bankAccEl.value = "";
  const ifscEl = document.getElementById("acc-bank-ifsc");
  if (ifscEl) ifscEl.value = "";
  const pinEl = document.getElementById("acc-pincode");
  if (pinEl) pinEl.value = "";
  const extraEl = document.getElementById("acc-extra-info");
  if (extraEl) extraEl.value = "";

  const titleEl = document.getElementById("account-master-screen-title");
  if (titleEl) titleEl.textContent = "Add Account Master";
}

function openAddAccountMaster() {
  resetAccountMasterAddForm();
  showScreen("view-add-account-master");
  setTimeout(() => { if (accName) accName.focus(); }, 50);
}

function openModifyAccountMaster(accId) {
  if (!accId) {
    const modal = document.getElementById("modal-select-account-modify");
    if (modal) {
      modal.classList.add("show");
      modal.style.display = "flex";
      renderSelectAccountModifyModal();
    }
    return;
  }
  if (!activeCompany) return;

  const loadIntoForm = (acc) => {
    if (!acc) {
      alert("Account details not found.");
      return;
    }
    const idEl = document.getElementById("acc-id");
    if (idEl) idEl.value = acc.id || "";
    const codeEl = document.getElementById("acc-code");
    if (codeEl) codeEl.value = acc.code || acc.customer_code || acc.customerCode || "";
    if (accName) accName.value = acc.name || "";
    const aliasEl = document.getElementById("acc-alias");
    if (aliasEl) aliasEl.value = acc.alias || "";
    const printEl = document.getElementById("acc-print-name");
    if (printEl) printEl.value = acc.print_name || acc.printName || acc.name || "";
    const groupEl = document.getElementById("acc-group");
    if (groupEl) groupEl.value = acc.account_group || acc.group || "Sundry Debtors";
    const opBalEl = document.getElementById("acc-op-bal");
    if (opBalEl) opBalEl.value = acc.op_bal ?? acc.opBal ?? 0;
    const opTypeEl = document.getElementById("acc-op-type");
    if (opTypeEl) opTypeEl.value = acc.op_type || acc.opType || "D";
    const addr1El = document.getElementById("acc-addr1");
    if (addr1El) addr1El.value = acc.address || "";
    const countryEl = document.getElementById("acc-country");
    if (countryEl) countryEl.value = acc.country || "India";
    const stateEl = document.getElementById("acc-state");
    if (stateEl) stateEl.value = acc.state || "Tamilnadu";
    const dealerEl = document.getElementById("acc-dealer-type");
    if (dealerEl) dealerEl.value = acc.dealer_type || acc.dealerType || "Unregistered";
    const catEl = document.getElementById("acc-customer-category");
    if (catEl) catEl.value = acc.customer_category || acc.customerCategory || "Direct Customer";
    if (accGstin) accGstin.value = acc.gstin || "";
    const mobEl = document.getElementById("acc-mobile");
    if (mobEl) mobEl.value = acc.mobile || "";
    const waEl = document.getElementById("acc-whatsapp");
    if (waEl) waEl.value = acc.whatsapp || "";
    const bankNameEl = document.getElementById("acc-bank-name");
    if (bankNameEl) bankNameEl.value = acc.bank_name || acc.bankName || "";
    const bankAccEl = document.getElementById("acc-bank-acc");
    if (bankAccEl) bankAccEl.value = acc.bank_acc || acc.bankAcc || "";
    const ifscEl = document.getElementById("acc-bank-ifsc");
    if (ifscEl) ifscEl.value = acc.ifsc || "";
    const pinEl = document.getElementById("acc-pincode");
    if (pinEl) pinEl.value = acc.pincode || "";
    const notesEl = document.getElementById("acc-extra-info");
    if (notesEl) notesEl.value = acc.notes || "";
    const titleEl = document.getElementById("account-master-screen-title");
    if (titleEl) titleEl.textContent = `Modify Account Master: ${acc.name}`;
    showScreen("view-add-account-master");
  };

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
  if (isTrad && window.backend && typeof window.backend.traditional_getCustomer === "function") {
    window.backend.traditional_getCustomer(accId, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.data) {
          loadIntoForm(r.data);
          return;
        }
      } catch (e) {}
      if (window.backend.traditional_listAccounts) {
        window.backend.traditional_listAccounts("", false, (lResp) => {
          try {
            const lr = typeof lResp === "string" ? JSON.parse(lResp) : lResp;
            const found = (lr.data || []).find(a => a.id === accId || a.name === accId);
            if (found) loadIntoForm(found);
          } catch(e) {}
        });
      }
    });
    return;
  }

  if (window.backend && window.backend.getAccountById) {
    window.backend.getAccountById(activeCompany.id, accId, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          loadIntoForm(r.data);
          return;
        }
      } catch (e) {}
      if (window.backend.listAccounts) {
        window.backend.listAccounts(activeCompany.id, (lResp) => {
          try {
            const lr = JSON.parse(lResp);
            const found = (lr.data || []).find(a => a.id === accId || a.name === accId);
            loadIntoForm(found);
          } catch(e) {}
        });
      }
    });
  } else if (window.backend && window.backend.listAccounts) {
    window.backend.listAccounts(activeCompany.id, (lResp) => {
      try {
        const lr = JSON.parse(lResp);
        const found = (lr.data || []).find(a => a.id === accId || a.name === accId);
        loadIntoForm(found);
      } catch(e) {}
    });
  }
}

function renderAccountMasterList(searchQuery, groupFilter) {
  if (!activeCompany) return;
  const tbody = document.getElementById("acc-master-tbody");
  const emptyEl = document.getElementById("acc-master-empty");
  const countEl = document.getElementById("acc-list-count");
  if (!tbody) return;

  const q = (searchQuery !== undefined ? searchQuery : (document.getElementById("acc-list-search")?.value || "")).toLowerCase().trim();
  const g = (groupFilter !== undefined ? groupFilter : (document.getElementById("acc-list-group-filter")?.value || "")).trim();

  const handleAccountsData = (accounts) => {
    let filtered = accounts.filter(acc => {
      const matchQ = !q || (acc.name && acc.name.toLowerCase().includes(q)) || 
                           (acc.mobile && acc.mobile.includes(q)) || 
                           (acc.gstin && acc.gstin.toLowerCase().includes(q)) ||
                           (acc.account_group && acc.account_group.toLowerCase().includes(q));
      let matchG = true;
      if (g) {
        const ag = acc.account_group || acc.group || "";
        if (g === "Sundry Debtors") {
          matchG = ag === "Sundry Debtors" || ag.includes("Both");
        } else if (g === "Sundry Creditors") {
          matchG = ag === "Sundry Creditors" || ag.includes("Both");
        } else {
          matchG = ag === g;
        }
      }
      return matchQ && matchG;
    });

    if (countEl) countEl.textContent = `Total Accounts: ${filtered.length}`;
    if (filtered.length === 0) {
      tbody.innerHTML = "";
      if (emptyEl) emptyEl.style.display = "block";
      return;
    }
    if (emptyEl) emptyEl.style.display = "none";
    tbody.innerHTML = "";
    filtered.forEach((acc, idx) => {
      const tr = document.createElement("tr");
      const bal = parseFloat(acc.current_balance ?? acc.op_bal ?? acc.opBal ?? 0) || 0;
      const rawGrp = acc.account_group || acc.group || "Sundry Debtors";
      let badgeStyle = "background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe;";
      let badgeLabel = rawGrp;
      if (rawGrp === "Sundry Debtors") {
        badgeStyle = "background: #dbeafe; color: #1e40af; border: 1px solid #93c5fd;";
        badgeLabel = "Customer";
      } else if (rawGrp === "Sundry Creditors") {
        badgeStyle = "background: #fef3c7; color: #92400e; border: 1px solid #fde68a;";
        badgeLabel = "Supplier";
      } else if (rawGrp.includes("Both")) {
        badgeStyle = "background: #ede9fe; color: #6b21a8; border: 1px solid #ddd6fe;";
        badgeLabel = "Customer & Supplier";
      }
      const inactiveTag = acc.is_active === 0 ? '<span style="display: inline-block; margin-left: 6px; font-size: 10px; padding: 1px 5px; background: #fee2e2; color: #991b1b; border-radius: 3px; font-weight: 700;">INACTIVE</span>' : '';

      tr.innerHTML = `
        <td style="text-align: center; color: #64748b;">${idx + 1}</td>
        <td><strong>${escapeHtml(acc.name)}</strong>${inactiveTag}</td>
        <td><span class="badge-category" style="${badgeStyle}">${escapeHtml(badgeLabel)}</span></td>
        <td>${escapeHtml(acc.customer_category || acc.customerCategory || "Direct Customer")}</td>
        <td>${escapeHtml(acc.gstin || acc.state || "-")}</td>
        <td>${escapeHtml(acc.mobile || "-")}</td>
        <td style="text-align: right; font-weight: 700; color: ${bal < 0 ? '#b91c1c' : '#1e3a8a'};">₹ ${bal.toFixed(2)}</td>
        <td style="text-align: center;">
          <button type="button" class="btn-table-action primary btn-modify-acc" data-id="${acc.id}">Modify</button>
        </td>
      `;
      tr.querySelector(".btn-modify-acc").addEventListener("click", (e) => {
        e.stopPropagation();
        openModifyAccountMaster(acc.id);
      });
      tr.addEventListener("dblclick", () => {
        openModifyAccountMaster(acc.id);
      });
      tbody.appendChild(tr);
    });
  };

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
  if (isTrad && window.backend && typeof window.backend.traditional_listAccounts === "function") {
    window.backend.traditional_listAccounts(q || "", false, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && Array.isArray(r.data)) {
          handleAccountsData(r.data);
          return;
        }
      } catch (e) {}
      const key = `alpha_accounts_${activeCompany.code}`;
      let list = [];
      try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
      handleAccountsData(list);
    });
    return;
  } else if (isTrad && window.backend && typeof window.backend.traditional_listCustomers === "function") {
    window.backend.traditional_listCustomers(q || "", false, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && Array.isArray(r.data)) {
          handleAccountsData(r.data);
          return;
        }
      } catch (e) {}
      const key = `alpha_accounts_${activeCompany.code}`;
      let list = [];
      try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
      handleAccountsData(list);
    });
    return;
  }

  if (window.backend && window.backend.listAccounts) {
    window.backend.listAccounts(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          handleAccountsData(r.data);
          return;
        }
      } catch (e) {}
      handleAccountsData([]);
    });
  } else {
    const key = `alpha_accounts_${activeCompany.code}`;
    let list = [];
    try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
    handleAccountsData(list);
  }
}

function handleSaveAccountMaster() {
  if (isSavingAccount) return;

  const name = accName ? accName.value.trim() : "";
  if (!name) {
    alert("Please enter Account Name.");
    if (accName) accName.focus();
    return;
  }

  const groupEl = document.getElementById("acc-group");
  const group = groupEl ? groupEl.value.trim() : "Sundry Debtors";
  if (!group) {
    alert("Please select an Account Group.");
    if (groupEl) groupEl.focus();
    return;
  }

  // Prevent duplicate saves caused by repeated button clicks
  isSavingAccount = true;
  if (btnAccSave) {
    btnAccSave.disabled = true;
    btnAccSave.style.opacity = "0.6";
  }

  // Print Name is automatically populated and synchronised with Name
  const printName = name;
  if (accPrintName) accPrintName.value = name;

  const alias = accAlias ? accAlias.value.trim() : (document.getElementById("acc-alias") ? document.getElementById("acc-alias").value.trim() : "");
  const existingAccId = document.getElementById("acc-id") ? document.getElementById("acc-id").value : "";
  const existingAccCode = document.getElementById("acc-code") ? document.getElementById("acc-code").value.trim() : "";
  const custCategory = document.getElementById("acc-customer-category") ? document.getElementById("acc-customer-category").value : "Direct Customer";
  const opBal = document.getElementById("acc-op-bal") ? parseFloat(document.getElementById("acc-op-bal").value) || 0.0 : 0.0;
  const opType = document.getElementById("acc-op-type") ? document.getElementById("acc-op-type").value : "D";

  const accountData = {
    name: name,
    alias: alias,
    printName: printName,
    print_name: printName,
    group: group,
    account_group: group,
    customerCategory: custCategory,
    customer_category: custCategory,
    opBal: opBal,
    op_bal: opBal,
    opType: opType,
    op_type: opType,
    address: [
      document.getElementById("acc-addr1") ? document.getElementById("acc-addr1").value.trim() : "",
      document.getElementById("acc-addr2") ? document.getElementById("acc-addr2").value.trim() : ""
    ].filter(Boolean).join(", "),
    country: document.getElementById("acc-country") ? document.getElementById("acc-country").value.trim() : "India",
    state: document.getElementById("acc-state") ? document.getElementById("acc-state").value.trim() : "Tamilnadu",
    dealerType: document.getElementById("acc-dealer-type") ? document.getElementById("acc-dealer-type").value : "Unregistered",
    gstin: accGstin ? accGstin.value.trim().toUpperCase() : "",
    mobile: document.getElementById("acc-mobile") ? document.getElementById("acc-mobile").value.trim() : "",
    whatsapp: document.getElementById("acc-whatsapp") ? document.getElementById("acc-whatsapp").value.trim() : "",
    bankName: document.getElementById("acc-bank-name") ? document.getElementById("acc-bank-name").value.trim() : "",
    bankAcc: document.getElementById("acc-bank-acc") ? document.getElementById("acc-bank-acc").value.trim() : "",
    ifsc: document.getElementById("acc-bank-ifsc") ? document.getElementById("acc-bank-ifsc").value.trim().toUpperCase() : "",
    pincode: document.getElementById("acc-pincode") ? document.getElementById("acc-pincode").value.trim() : "",
    notes: document.getElementById("acc-extra-info") ? document.getElementById("acc-extra-info").value.trim() : "",
    createdAt: new Date().toISOString()
  };
  if (existingAccId) {
    accountData.id = existingAccId;
  }
  if (existingAccCode) {
    accountData.code = existingAccCode;
    accountData.customer_code = existingAccCode;
  }

  const completeSave = (savedData) => {
    // Sync localStorage cache
    if (activeCompany) {
      const key = `alpha_accounts_${activeCompany.code}`;
      let list = [];
      try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) {}
      const targetId = (savedData && savedData.id) || existingAccId;
      const existingIdx = list.findIndex(a => (targetId && a.id === targetId) || (a.name && a.name.toUpperCase() === name.toUpperCase()));
      const recordToCache = { ...accountData, id: targetId || (savedData && savedData.id) || accountData.id || ("acc-" + Date.now()) };
      if (existingIdx !== -1) {
        list[existingIdx] = recordToCache;
      } else {
        list.push(recordToCache);
      }
      localStorage.setItem(key, JSON.stringify(list));
    }

    if (existingAccId) {
      // Modify mode: notification, reset form, and return to account list
      showNotification(`Account Master "${name}" updated successfully!`);
      resetAccountMasterAddForm();
      showScreen("view-account-list");
      renderAccountMasterList();
    } else {
      // Continuous Add Workflow for NEW records:
      // 1. Clear success confirmation
      showNotification(`Account Master "${name}" saved successfully!`);
      // 2. Reset form fields for next entry while preserving defaults
      resetAccountMasterAddForm();
      // 3. Keep user on the same Add Master screen (no redirect to Dashboard, List, Modify, etc.)
      showScreen("view-add-account-master");
      // 4. Automatically focus Name field
      setTimeout(() => {
        if (accName) accName.focus();
      }, 50);
    }

    isSavingAccount = false;
    if (btnAccSave) {
      btnAccSave.disabled = false;
      btnAccSave.style.opacity = "";
    }
  };

  const failSave = (errMsg) => {
    isSavingAccount = false;
    if (btnAccSave) {
      btnAccSave.disabled = false;
      btnAccSave.style.opacity = "";
    }
    // Retain entered form data - do NOT clear form
    alert(`Failed to save Account Master: ${errMsg || "Unknown database error"}`);
    if (accName) accName.focus();
  };

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
  if (isTrad && window.backend && typeof window.backend.traditional_saveCustomer === "function") {
    window.backend.traditional_saveCustomer(JSON.stringify(accountData), (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success) {
          completeSave(r.data);
        } else {
          failSave(r ? r.error : "Failed to save Customer Account.");
        }
      } catch (e) {
        failSave(e.message);
      }
    });
  } else if (activeCompany && window.backend && typeof window.backend.saveAccount === "function") {
    window.backend.saveAccount(activeCompany.id, JSON.stringify(accountData), (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success) {
          completeSave(r.data);
        } else {
          failSave(r ? r.error : "Failed to save Account Master.");
        }
      } catch (e) {
        failSave(e.message);
      }
    });
  } else {
    // Standalone / preview mode
    completeSave({ id: "acc-" + Date.now(), name: name });
  }
}

function validateGstinOnline() {
  const val = accGstin.value.trim().toUpperCase();
  if (!val) {
    alert("Please enter GSTIN to validate.");
    accGstin.focus();
    return;
  }
  const gstinRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
  if (gstinRegex.test(val)) {
    showNotification(`GSTIN ${val} validated successfully.`);
  } else {
    alert(`Invalid GSTIN format: ${val}\nExpected 15-character format, e.g. 33AAAAA0000A1Z5`);
  }
}

// =============================================================
// AUTOMATIC UNIQUE BARCODE GENERATOR & LABEL PRINTING
// =============================================================
let currentAlternateBarcodes = [];

function initBarcodeModule() {
  const btnGen = document.getElementById("btn-generate-barcode");
  const aliasInput = document.getElementById("item-alias");
  const btnPrint = document.getElementById("btn-print-barcode-label");
  const btnAddAlt = document.getElementById("btn-add-alternate-barcode");
  const altInput = document.getElementById("item-alternate-barcodes-input");

  // 1. Generate Barcode Button
  if (btnGen && !btnGen.dataset.bound) {
    btnGen.dataset.bound = "true";
    btnGen.addEventListener("click", () => {
      handleGenerateBarcodeClick();
    });
  }

  // 2. Barcode Input Live Validation & Preview
  if (aliasInput && !aliasInput.dataset.bound) {
    aliasInput.dataset.bound = "true";
    let debounceTimer = null;
    aliasInput.addEventListener("input", () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const val = aliasInput.value.trim().toUpperCase();
        aliasInput.value = val;
        if (val) {
          updateBarcodePreview(val);
        } else {
          const prev = document.getElementById("item-barcode-preview-container");
          if (prev) prev.style.display = "none";
        }
      }, 250);
    });
  }

  // 3. Add Alternate Barcode
  if (btnAddAlt && !btnAddAlt.dataset.bound) {
    btnAddAlt.dataset.bound = "true";
    btnAddAlt.addEventListener("click", () => {
      handleAddAlternateBarcode();
    });
  }
  if (altInput && !altInput.dataset.bound) {
    altInput.dataset.bound = "true";
    altInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddAlternateBarcode();
      }
    });
  }

  // 4. Print Barcode Label
  if (btnPrint && !btnPrint.dataset.bound) {
    btnPrint.dataset.bound = "true";
    btnPrint.addEventListener("click", () => {
      openBarcodeLabelModal();
    });
  }

  // Modal event bindings
  initBarcodeModalEvents();
}

function handleGenerateBarcodeClick() {
  const aliasInput = document.getElementById("item-alias");
  const currentVal = aliasInput ? aliasInput.value.trim() : "";

  // Requirement 1: Do not overwrite an existing manually entered barcode without confirmation
  if (currentVal) {
    const ok = confirm(`The Barcode / SKU field already contains "${currentVal}".\n\nDo you want to generate a new unique barcode and replace it?`);
    if (!ok) return;
  }

  const compId = activeCompany ? activeCompany.id : "COMP0001";
  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
  if (isTrad && window.backend && typeof window.backend.traditional_generateBarcode === "function") {
    window.backend.traditional_generateBarcode((resp) => {
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res.success && res.data) {
          const genCode = res.data.barcode;
          if (aliasInput) aliasInput.value = genCode;
          showNotification(`Allocated unique barcode: ${genCode}`);
          updateBarcodePreview(genCode, "", "Code 128");
        } else {
          alert(`Error generating barcode: ${res.error || "Unknown error"}`);
        }
      } catch (e) {
        console.error("Barcode generator response parse error:", e);
      }
    });
    return;
  }
  if (window.backend && window.backend.generateUniqueBarcode) {
    window.backend.generateUniqueBarcode(compId, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          const genCode = res.data.barcode;
          if (aliasInput) aliasInput.value = genCode;
          showNotification(`Generated unique Code 128 barcode: ${genCode}`);
          updateBarcodePreview(genCode, res.data.svg, res.data.standard);
        } else {
          alert(`Error generating barcode: ${res.error || "Unknown error"}`);
        }
      } catch (e) {
        console.error("Barcode generator response parse error:", e);
      }
    });
  } else {
    // Standalone fallback: simulate atomic AB sequence
    const fallbackCode = "AB" + String(Date.now()).slice(-12);
    if (aliasInput) aliasInput.value = fallbackCode;
    updateBarcodePreview(fallbackCode);
  }
}

function updateBarcodePreview(barcode, preRenderedSvg, standardName) {
  const container = document.getElementById("item-barcode-preview-container");
  const svgWrapper = document.getElementById("item-barcode-svg-wrapper");
  const humanText = document.getElementById("item-barcode-human-text");
  const badge = document.getElementById("item-barcode-standard-badge");
  const statusText = document.getElementById("item-barcode-status-text");

  if (!container || !barcode) {
    if (container) container.style.display = "none";
    return;
  }

  container.style.display = "flex";
  if (humanText) humanText.textContent = barcode;

  const currentItemId = document.getElementById("item-id")?.value.trim() || "";
  const compId = activeCompany ? activeCompany.id : "";

  // Render SVG graphic
  if (preRenderedSvg && svgWrapper) {
    svgWrapper.innerHTML = preRenderedSvg;
    if (badge && standardName) badge.textContent = standardName;
  } else if (window.backend && window.backend.renderBarcodeSvg) {
    window.backend.renderBarcodeSvg(barcode, "", (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.svg && svgWrapper) {
          svgWrapper.innerHTML = r.svg;
        }
      } catch (e) {}
    });
  }

  // Validate format & checksum
  if (window.backend && window.backend.validateBarcode) {
    window.backend.validateBarcode(barcode, (resp) => {
      try {
        const valRes = JSON.parse(resp);
        if (valRes.success && valRes.data) {
          const d = valRes.data;
          if (badge) badge.textContent = d.standard || "Code 128";
          if (!d.is_valid) {
            if (statusText) {
              statusText.style.color = "#dc2626";
              statusText.textContent = `⚠️ ${d.message || "Invalid Check Digit"}`;
            }
            return;
          }
        }
      } catch (e) {}

      // Check database uniqueness across all products
      if (compId && window.backend.checkBarcodeAvailability) {
        window.backend.checkBarcodeAvailability(compId, barcode, currentItemId, (availResp) => {
          try {
            const aRes = JSON.parse(availResp);
            if (aRes.success && aRes.data) {
              if (aRes.data.is_unique) {
                if (statusText) {
                  statusText.style.color = "#166534";
                  statusText.textContent = "✓ Unique & Available in Database";
                }
              } else {
                const dupItem = aRes.data.existing_product ? aRes.data.existing_product.name : "another item";
                if (statusText) {
                  statusText.style.color = "#dc2626";
                  statusText.textContent = `❌ Conflicting: Already assigned to "${dupItem}"`;
                }
              }
            }
          } catch (e) {}
        });
      }
    });
  }
}

function handleAddAlternateBarcode() {
  const altInput = document.getElementById("item-alternate-barcodes-input");
  const val = altInput ? altInput.value.trim().toUpperCase() : "";
  if (!val) return;

  const primary = document.getElementById("item-alias")?.value.trim().toUpperCase();
  if (val === primary) {
    alert(`"${val}" is already entered as the primary barcode.`);
    return;
  }
  if (currentAlternateBarcodes.includes(val)) {
    alert(`"${val}" is already added to alternate barcodes.`);
    return;
  }

  const currentItemId = document.getElementById("item-id")?.value.trim() || "";
  const compId = activeCompany ? activeCompany.id : "";

  // Check backend availability
  if (compId && window.backend && window.backend.checkBarcodeAvailability) {
    window.backend.checkBarcodeAvailability(compId, val, currentItemId, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data && !r.data.is_unique) {
          const item = r.data.existing_product ? r.data.existing_product.name : "another product";
          alert(`Cannot add barcode "${val}": Already assigned to "${item}".`);
          return;
        }
      } catch (e) {}
      currentAlternateBarcodes.push(val);
      if (altInput) altInput.value = "";
      renderAlternateBarcodesList();
    });
  } else {
    currentAlternateBarcodes.push(val);
    if (altInput) altInput.value = "";
    renderAlternateBarcodesList();
  }
}

function removeAlternateBarcode(bcode) {
  currentAlternateBarcodes = currentAlternateBarcodes.filter(x => x !== bcode);
  renderAlternateBarcodesList();
}

function renderAlternateBarcodesList() {
  const listEl = document.getElementById("item-alternate-barcodes-list");
  if (!listEl) return;
  listEl.innerHTML = "";
  currentAlternateBarcodes.forEach((b) => {
    const badge = document.createElement("span");
    badge.className = "alternate-barcode-badge";
    badge.innerHTML = `<span>${b}</span><button type="button" class="remove-barcode-btn" title="Remove barcode" onclick="removeAlternateBarcode('${b}')">&times;</button>`;
    listEl.appendChild(badge);
  });
}

function openBarcodeLabelModal() {
  const modal = document.getElementById("modal-barcode-label-print");
  const barcode = document.getElementById("item-alias")?.value.trim();
  if (!barcode) {
    alert("Please enter or generate a Barcode / SKU first before printing labels.");
    return;
  }
  if (modal) {
    modal.style.display = "flex";
    modal.classList.add("show");
    updateBarcodeLabelLivePreview();
  }
}

function closeBarcodeLabelModal() {
  const modal = document.getElementById("modal-barcode-label-print");
  if (modal) {
    modal.style.display = "none";
    modal.classList.remove("show");
  }
}

function updateBarcodeLabelLivePreview() {
  const previewBox = document.getElementById("barcode-label-live-preview");
  if (!previewBox) return;

  const barcode = document.getElementById("item-alias")?.value.trim() || "AB000000000001";
  const name = document.getElementById("item-name")?.value.trim() || "Product Name";
  const salesPrice = parseFloat(document.getElementById("item-sales-price")?.value || "0");
  const mrp = parseFloat(document.getElementById("item-mrp")?.value || "0");
  const sku = document.getElementById("item-alias")?.value.trim() || "";

  const sizeKey = document.getElementById("barcode-label-size-select")?.value || "50x25";
  const incName = document.getElementById("chk-label-include-name")?.checked ?? true;
  const incPrice = document.getElementById("chk-label-include-price")?.checked ?? true;
  const incMrp = document.getElementById("chk-label-include-mrp")?.checked ?? true;
  const incSku = document.getElementById("chk-label-include-sku")?.checked ?? true;

  const itemData = {
    name: name,
    barcode: barcode,
    alias: sku,
    sales_price: salesPrice,
    mrp: mrp
  };
  const opts = {
    size: sizeKey,
    include_name: incName,
    include_price: incPrice,
    include_mrp: incMrp,
    include_sku: incSku,
    copies: 1
  };

  if (window.backend && window.backend.generateBarcodeLabelHtml) {
    window.backend.generateBarcodeLabelHtml(JSON.stringify(itemData), JSON.stringify(opts), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.html) {
          const parser = new DOMParser();
          const doc = parser.parseFromString(r.html, "text/html");
          const labelEl = doc.querySelector(".physical-barcode-label");
          if (labelEl) {
            previewBox.innerHTML = labelEl.outerHTML;
          }
        }
      } catch (e) {}
    });
  }
}

function initBarcodeModalEvents() {
  const btnClose = document.getElementById("btn-close-barcode-modal");
  const btnCancel = document.getElementById("btn-cancel-barcode-modal");
  const btnPrintNow = document.getElementById("btn-execute-print-barcode");

  if (btnClose && !btnClose.dataset.bound) {
    btnClose.dataset.bound = "true";
    btnClose.addEventListener("click", closeBarcodeLabelModal);
  }
  if (btnCancel && !btnCancel.dataset.bound) {
    btnCancel.dataset.bound = "true";
    btnCancel.addEventListener("click", closeBarcodeLabelModal);
  }

  ["barcode-label-size-select", "chk-label-include-name", "chk-label-include-price", "chk-label-include-mrp", "chk-label-include-sku"].forEach((id) => {
    const el = document.getElementById(id);
    if (el && !el.dataset.bound) {
      el.dataset.bound = "true";
      el.addEventListener("change", updateBarcodeLabelLivePreview);
    }
  });

  if (btnPrintNow && !btnPrintNow.dataset.bound) {
    btnPrintNow.dataset.bound = "true";
    btnPrintNow.addEventListener("click", executeBarcodeLabelPrint);
  }
}

function executeBarcodeLabelPrint() {
  const barcode = document.getElementById("item-alias")?.value.trim() || "";
  const name = document.getElementById("item-name")?.value.trim() || "Product";
  const salesPrice = parseFloat(document.getElementById("item-sales-price")?.value || "0");
  const mrp = parseFloat(document.getElementById("item-mrp")?.value || "0");
  const sku = document.getElementById("item-alias")?.value.trim() || "";

  const sizeKey = document.getElementById("barcode-label-size-select")?.value || "50x25";
  const incName = document.getElementById("chk-label-include-name")?.checked ?? true;
  const incPrice = document.getElementById("chk-label-include-price")?.checked ?? true;
  const incMrp = document.getElementById("chk-label-include-mrp")?.checked ?? true;
  const incSku = document.getElementById("chk-label-include-sku")?.checked ?? true;
  const copies = parseInt(document.getElementById("barcode-label-copies")?.value || "1", 10);

  const itemData = { name, barcode, alias: sku, sales_price: salesPrice, mrp };
  const opts = { size: sizeKey, include_name: incName, include_price: incPrice, include_mrp: incMrp, include_sku: incSku, copies };

  if (window.backend && window.backend.generateBarcodeLabelHtml) {
    window.backend.generateBarcodeLabelHtml(JSON.stringify(itemData), JSON.stringify(opts), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.html) {
          // Open decoupled print iframe
          let printIframe = document.getElementById("barcode-print-iframe");
          if (!printIframe) {
            printIframe = document.createElement("iframe");
            printIframe.id = "barcode-print-iframe";
            printIframe.style.position = "fixed";
            printIframe.style.right = "0";
            printIframe.style.bottom = "0";
            printIframe.style.width = "0";
            printIframe.style.height = "0";
            printIframe.style.border = "0";
            document.body.appendChild(printIframe);
          }
          const doc = printIframe.contentWindow.document;
          doc.open();
          doc.write(r.html);
          doc.close();
          setTimeout(() => {
            printIframe.contentWindow.focus();
            printIframe.contentWindow.print();
            closeBarcodeLabelModal();
            showNotification(`Sent ${copies} barcode label(s) to printer.`);
          }, 300);
        }
      } catch (e) {
        alert("Print error: " + e.message);
      }
    });
  } else {
    window.print();
    closeBarcodeLabelModal();
  }
}

// =============================================================
// ITEM MASTER & PRODUCTS CATALOGUE MANAGEMENT
// =============================================================
let isSavingItem = false;

function syncItemPrintName() {
  const nameEl = document.getElementById("item-name");
  const printEl = document.getElementById("item-print-name");
  if (nameEl && printEl) {
    printEl.value = nameEl.value;
  }
}

function resetProductMasterForm() {
  if (formItemMaster && typeof formItemMaster.reset === "function") {
    formItemMaster.reset();
  }
  const idEl = document.getElementById("item-id");
  if (idEl) idEl.value = "";
  if (itemName) itemName.value = "";
  const aliasEl = document.getElementById("item-alias");
  if (aliasEl) aliasEl.value = "";
  if (itemPrintName) itemPrintName.value = "";
  syncItemPrintName();

  // Reset category and unit defaults
  const groupEl = document.getElementById("item-group");
  if (groupEl) groupEl.value = "General";
  const unitEl = document.getElementById("item-unit");
  if (unitEl) unitEl.value = "Pcs.";

  // Reset stock quantities and levels
  const opQtyEl = document.getElementById("item-op-qty");
  if (opQtyEl) opQtyEl.value = "0.00";
  const opValEl = document.getElementById("item-op-val");
  if (opValEl) opValEl.value = "0.00";
  const minStockEl = document.getElementById("item-min-stock-level");
  if (minStockEl) minStockEl.value = "";
  const reorderLvlEl = document.getElementById("item-reorder-level");
  if (reorderLvlEl) reorderLvlEl.value = "";
  const reorderQtyEl = document.getElementById("item-reorder-qty");
  if (reorderQtyEl) reorderQtyEl.value = "";
  const maxStockEl = document.getElementById("item-max-stock-level");
  if (maxStockEl) maxStockEl.value = "";
  const alertEnabledEl = document.getElementById("item-alert-enabled");
  if (alertEnabledEl) alertEnabledEl.checked = true;

  // Reset tax and HSN
  const taxCatEl = document.getElementById("item-tax-cat");
  if (taxCatEl) taxCatEl.value = "GST 18%";
  const hsnEl = document.getElementById("item-hsn");
  if (hsnEl) hsnEl.value = "";

  // Reset pricing
  const salesPriceEl = document.getElementById("item-sales-price");
  if (salesPriceEl) salesPriceEl.value = "0.00";
  const purcPriceEl = document.getElementById("item-purc-price");
  if (purcPriceEl) purcPriceEl.value = "0.00";
  const mrpEl = document.getElementById("item-mrp");
  if (mrpEl) mrpEl.value = "0.00";
  const minPriceEl = document.getElementById("item-min-sales-price");
  if (minPriceEl) minPriceEl.value = "0.00";

  // Reset discounts
  const saleDiscEl = document.getElementById("item-sale-disc");
  if (saleDiscEl) saleDiscEl.value = "0.00";
  const purcDiscEl = document.getElementById("item-purc-disc");
  if (purcDiscEl) purcDiscEl.value = "0.00";

  // Reset descriptions
  const descEl = document.getElementById("item-desc");
  if (descEl) descEl.value = "";
  const extraInfoEl = document.getElementById("item-extra-info");
  if (extraInfoEl) extraInfoEl.value = "";

  // Reset Barcode Preview & Alternates
  const altInput = document.getElementById("item-alternate-barcodes-input");
  if (altInput) altInput.value = "";
  const prev = document.getElementById("item-barcode-preview-container");
  if (prev) prev.style.display = "none";
  const svgWrap = document.getElementById("item-barcode-svg-wrapper");
  if (svgWrap) svgWrap.innerHTML = "";
  currentAlternateBarcodes = [];
  if (typeof renderAlternateBarcodesList === "function") {
    renderAlternateBarcodesList();
  }

  const titleEl = document.getElementById("item-master-screen-title");
  if (titleEl) titleEl.textContent = "Add Product";
}

function openAddProductMaster() {
  resetProductMasterForm();
  showScreen("view-add-item-master");
  setTimeout(() => {
    if (itemName) itemName.focus();
  }, 50);
}

function loadProductForEditing(itemOrId) {
  function applyItem(item) {
    if (!item) {
      alert("Product not found.");
      return;
    }
    const idEl = document.getElementById("item-id");
    if (idEl) idEl.value = item.id || "";
    
    if (itemName) itemName.value = item.name || "";
    const aliasEl = document.getElementById("item-alias");
    const primaryBar = (Array.isArray(item.barcodes) && item.barcodes.length > 0)
      ? item.barcodes[0]
      : (item.sku || item.primary_barcode || item.alias || (typeof item.barcodes === "string" ? item.barcodes.split(",")[0].trim() : ""));
    if (aliasEl) aliasEl.value = primaryBar;

    currentAlternateBarcodes = [];
    if (Array.isArray(item.barcodes)) {
      currentAlternateBarcodes = item.barcodes.filter(b => b && b !== primaryBar);
    } else if (item.alternate_barcodes && Array.isArray(item.alternate_barcodes)) {
      currentAlternateBarcodes = item.alternate_barcodes.filter(b => b && b !== primaryBar);
    } else if (typeof item.barcodes === "string" && item.barcodes.trim()) {
      const parts = item.barcodes.split(",").map(s => s.trim()).filter(Boolean);
      currentAlternateBarcodes = parts.filter(b => b !== primaryBar);
    }
    renderAlternateBarcodesList();

    if (primaryBar) {
      updateBarcodePreview(primaryBar);
    } else {
      const prev = document.getElementById("item-barcode-preview-container");
      if (prev) prev.style.display = "none";
    }
    const printEl = document.getElementById("item-print-name");
    if (printEl) printEl.value = item.name || item.print_name || item.printName || "";
    syncItemPrintName();
    const groupEl = document.getElementById("item-group");
    if (groupEl) groupEl.value = item.item_group || item.group || "General";
    const unitEl = document.getElementById("item-unit");
    if (unitEl) unitEl.value = item.unit || "Pcs.";
    const opQtyEl = document.getElementById("item-op-qty");
    if (opQtyEl) opQtyEl.value = item.op_stock_qty ?? item.opStockQty ?? 0;
    const opValEl = document.getElementById("item-op-val");
    if (opValEl) opValEl.value = item.op_stock_val ?? item.opStockVal ?? 0;
    const taxCatEl = document.getElementById("item-tax-cat");
    if (taxCatEl) taxCatEl.value = item.tax_category || item.taxCategory || "GST 18%";
    const hsnEl = document.getElementById("item-hsn");
    if (hsnEl) hsnEl.value = item.hsn || "";
    const salesPriceEl = document.getElementById("item-sales-price");
    if (salesPriceEl) salesPriceEl.value = item.selling_price ?? item.sellingPrice ?? item.sales_price ?? item.salesPrice ?? 0;
    const purcPriceEl = document.getElementById("item-purc-price");
    if (purcPriceEl) purcPriceEl.value = item.cogs_amount ?? item.cogsAmount ?? item.purc_price ?? item.purcPrice ?? 0;
    const mrpEl = document.getElementById("item-mrp");
    if (mrpEl) mrpEl.value = item.mrp ?? 0;
    const minPriceEl = document.getElementById("item-min-sales-price");
    if (minPriceEl) minPriceEl.value = item.min_sales_price ?? item.minSalesPrice ?? 0;
    const descEl = document.getElementById("item-desc");
    if (descEl) descEl.value = item.description || "";

    const minStockEl = document.getElementById("item-min-stock-level");
    if (minStockEl) {
      minStockEl.value = (item.min_stock_alert_level !== null && item.min_stock_alert_level !== undefined) ? item.min_stock_alert_level : "";
    }
    const reorderLvlEl = document.getElementById("item-reorder-level");
    if (reorderLvlEl) {
      reorderLvlEl.value = (item.reorder_level !== null && item.reorder_level !== undefined) ? item.reorder_level : "";
    }
    const reorderQtyEl = document.getElementById("item-reorder-qty");
    if (reorderQtyEl) {
      reorderQtyEl.value = (item.reorder_qty !== null && item.reorder_qty !== undefined) ? item.reorder_qty : "";
    }
    const maxStockEl = document.getElementById("item-max-stock-level");
    if (maxStockEl) {
      maxStockEl.value = (item.max_stock_level !== null && item.max_stock_level !== undefined) ? item.max_stock_level : "";
    }
    const alertEnabledEl = document.getElementById("item-alert-enabled");
    if (alertEnabledEl) {
      alertEnabledEl.checked = (item.alert_enabled !== 0);
    }

    const titleEl = document.getElementById("item-master-screen-title");
    if (titleEl) titleEl.textContent = `Modify Product: ${item.name}`;

    showScreen("view-add-item-master");
    if (itemName) itemName.focus();
  }

  if (typeof itemOrId === "object" && itemOrId !== null) {
    applyItem(itemOrId);
    return;
  }

  fetchItemById(itemOrId, applyItem);
}

function handleSaveItemMaster() {
  if (isSavingItem) return;

  const name = itemName ? itemName.value.trim() : "";
  if (!name) {
    alert("Please enter Product Name.");
    if (itemName) itemName.focus();
    return;
  }

  // Ensure Receipt Print Name is synchronized and matches Product Name
  syncItemPrintName();

  // Prevent duplicate saves caused by repeated button clicks or F2 presses
  isSavingItem = true;
  const btnSave = document.getElementById("btn-item-save");
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.style.opacity = "0.6";
  }

  const unlockSave = () => {
    isSavingItem = false;
    if (btnSave) {
      btnSave.disabled = false;
      btnSave.style.opacity = "";
    }
  };

  const existingId = document.getElementById("item-id")?.value.trim() || undefined;

  const rawMinStock = document.getElementById("item-min-stock-level") ? document.getElementById("item-min-stock-level").value.trim() : "";
  const rawReorder = document.getElementById("item-reorder-level") ? document.getElementById("item-reorder-level").value.trim() : "";
  const rawReorderQty = document.getElementById("item-reorder-qty") ? document.getElementById("item-reorder-qty").value.trim() : "";
  const rawMaxStock = document.getElementById("item-max-stock-level") ? document.getElementById("item-max-stock-level").value.trim() : "";
  const alertEnabled = document.getElementById("item-alert-enabled") ? (document.getElementById("item-alert-enabled").checked ? 1 : 0) : 1;

  let parsedMinStock = null;
  if (rawMinStock !== "" && !isNaN(parseFloat(rawMinStock))) {
    parsedMinStock = Math.max(0, parseFloat(rawMinStock));
  }
  let parsedReorder = null;
  if (rawReorder !== "" && !isNaN(parseFloat(rawReorder))) {
    parsedReorder = Math.max(0, parseFloat(rawReorder));
  }
  let parsedReorderQty = null;
  if (rawReorderQty !== "" && !isNaN(parseFloat(rawReorderQty))) {
    parsedReorderQty = Math.max(0, parseFloat(rawReorderQty));
  }
  let parsedMaxStock = null;
  if (rawMaxStock !== "" && !isNaN(parseFloat(rawMaxStock))) {
    parsedMaxStock = Math.max(0, parseFloat(rawMaxStock));
  }

  const primaryBarcode = document.getElementById("item-alias") ? document.getElementById("item-alias").value.trim() : "";
  const allBarcodes = [primaryBarcode, ...currentAlternateBarcodes].filter(Boolean);

  const itemData = {
    id: existingId,
    name: name,
    sku: primaryBarcode,
    barcode: primaryBarcode,
    alias: primaryBarcode,
    barcodes: allBarcodes,
    alternate_barcodes: currentAlternateBarcodes,
    printName: name,
    print_name: name,
    group: document.getElementById("item-group") ? document.getElementById("item-group").value : "General",
    item_group: document.getElementById("item-group") ? document.getElementById("item-group").value : "General",
    category: document.getElementById("item-group") ? document.getElementById("item-group").value : "General",
    unit: document.getElementById("item-unit") ? document.getElementById("item-unit").value : "Pcs.",
    opStockQty: document.getElementById("item-op-qty") ? document.getElementById("item-op-qty").value : "0.00",
    op_stock_qty: document.getElementById("item-op-qty") ? document.getElementById("item-op-qty").value : "0.00",
    opStockVal: document.getElementById("item-op-val") ? document.getElementById("item-op-val").value : "0.00",
    op_stock_val: document.getElementById("item-op-val") ? document.getElementById("item-op-val").value : "0.00",
    taxCategory: document.getElementById("item-tax-cat") ? document.getElementById("item-tax-cat").value : "GST 18%",
    tax_category: document.getElementById("item-tax-cat") ? document.getElementById("item-tax-cat").value : "GST 18%",
    hsn: document.getElementById("item-hsn") ? document.getElementById("item-hsn").value.trim() : "",
    salesPrice: document.getElementById("item-sales-price") ? document.getElementById("item-sales-price").value : "0.00",
    sales_price: document.getElementById("item-sales-price") ? document.getElementById("item-sales-price").value : "0.00",
    sellingPrice: document.getElementById("item-sales-price") ? document.getElementById("item-sales-price").value : "0.00",
    selling_price: document.getElementById("item-sales-price") ? document.getElementById("item-sales-price").value : "0.00",
    purcPrice: document.getElementById("item-purc-price") ? document.getElementById("item-purc-price").value : "0.00",
    purc_price: document.getElementById("item-purc-price") ? document.getElementById("item-purc-price").value : "0.00",
    cogsAmount: document.getElementById("item-purc-price") ? document.getElementById("item-purc-price").value : "0.00",
    cogs_amount: document.getElementById("item-purc-price") ? document.getElementById("item-purc-price").value : "0.00",
    mrp: document.getElementById("item-mrp") ? document.getElementById("item-mrp").value : "0.00",
    minSalesPrice: document.getElementById("item-min-sales-price") ? document.getElementById("item-min-sales-price").value : "0.00",
    min_sales_price: document.getElementById("item-min-sales-price") ? document.getElementById("item-min-sales-price").value : "0.00",
    sale_disc: document.getElementById("item-sale-disc") ? document.getElementById("item-sale-disc").value : "0.00",
    purc_disc: document.getElementById("item-purc-disc") ? document.getElementById("item-purc-disc").value : "0.00",
    description: document.getElementById("item-desc") ? document.getElementById("item-desc").value.trim() : "",
    extra_info: document.getElementById("item-extra-info") ? document.getElementById("item-extra-info").value.trim() : "",
    min_stock_alert_level: parsedMinStock,
    min_stock_level: parsedMinStock,
    reorder_level: parsedReorder,
    reorder_qty: parsedReorderQty,
    max_stock_level: parsedMaxStock,
    alert_enabled: alertEnabled,
    updatedAt: new Date().toISOString()
  };

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");
  if (isTrad && window.backend && typeof window.backend.traditional_saveProduct === "function") {
    window.backend.traditional_saveProduct(JSON.stringify(itemData), (resp) => {
      unlockSave();
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success) {
          if (activeCompany) {
            const key = `alpha_items_${activeCompany.code}`;
            let list = [];
            try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch (e) {}
            const targetId = (r.data && r.data.id) || existingId;
            const existingIdx = list.findIndex(x => (targetId && x.id === targetId) || (x.name && x.name.toUpperCase() === name.toUpperCase()));
            const recordToCache = { ...itemData, id: targetId || itemData.id };
            if (existingIdx !== -1) {
              list[existingIdx] = recordToCache;
            } else {
              list.push(recordToCache);
            }
            localStorage.setItem(key, JSON.stringify(list));
          }

          if (existingId) {
            // Modify Mode: updating existing product
            // 1. Success notification toast with updated product name
            showNotification(`Product "${name}" updated successfully!`);
            // 2. Clear previous product form state
            resetProductMasterForm();
            // 3. Automatically navigate back to Product List
            showScreen("view-items-list");
            // 4. Refresh Product List from database
            renderProductsList();
          } else {
            // Continuous Add Mode for new product:
            // 1. Success notification toast with saved product name
            showNotification(`Product "${name}" saved to database!`);
            // 2. Refresh background product catalogue
            renderProductsList();
            // 3. Reset form to fresh Add Product state
            resetProductMasterForm();
            // 4. Ensure view remains on view-add-item-master
            showScreen("view-add-item-master");
            // 5. Automatically focus cursor on Product Name
            setTimeout(() => {
              if (itemName) itemName.focus();
            }, 50);
          }
        } else {
          // Failed save: do NOT reset form; retain all entered values
          const errMsg = (r && r.error) ? r.error : "Unknown database error";
          alert(`Failed to save Product: ${errMsg}`);
          if (errMsg && (errMsg.toLowerCase().includes("sku") || errMsg.toLowerCase().includes("barcode"))) {
            const aliasEl = document.getElementById("item-alias");
            if (aliasEl) aliasEl.focus();
          } else if (errMsg && errMsg.toLowerCase().includes("name")) {
            if (itemName) itemName.focus();
          } else if (errMsg && errMsg.toLowerCase().includes("price")) {
            const priceEl = document.getElementById("item-sales-price");
            if (priceEl) priceEl.focus();
          } else {
            if (itemName) itemName.focus();
          }
        }
      } catch (e) {
        console.error("Error saving traditional product:", e);
        alert(`Failed to save Product: ${e.message || "Unknown error"}`);
        if (itemName) itemName.focus();
      }
    });
    return;
  }

  if (activeCompany) {
    if (window.backend && typeof window.backend.saveItem === "function") {
      window.backend.saveItem(activeCompany.id, JSON.stringify(itemData), (resp) => {
        unlockSave();
        try {
          const r = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (r && r.success) {
            const actionText = existingId ? "updated" : "saved to database";
            showNotification(`Product "${name}" ${actionText}!`);
            checkLowStockAlerts(false);
            renderProductsList();
          }
        } catch (e) {
          console.error("Error saving item to backend:", e);
        }
      });
    }

    const key = `alpha_items_${activeCompany.code}`;
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(key) || "[]");
    } catch (e) {}
    
    if (existingId) {
      const idx = list.findIndex((x) => x.id === existingId || x.name === name);
      if (idx !== -1) {
        list[idx] = { ...list[idx], ...itemData };
      } else {
        list.push(itemData);
      }
    } else {
      list.push(itemData);
    }
    localStorage.setItem(key, JSON.stringify(list));
  }

  unlockSave();
  showNotification(`Product "${name}" ${existingId ? 'updated' : 'saved'}!`);
  resetProductMasterForm();
  showScreen("view-items-list");
}

function fetchAllItems(query, callback) {
  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");
  if (isTrad && window.backend && typeof window.backend.traditional_listProducts === "function") {
    window.backend.traditional_listProducts(query || "", "", true, (resp) => {
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res && res.success && Array.isArray(res.data)) {
          callback(res.data);
          return;
        }
      } catch (e) {
        console.error("Backend traditional_listProducts error:", e);
      }
      fallbackLocalItems(query, callback);
    });
    return;
  }

  if (window.backend && activeCompany) {
    window.backend.searchItems(activeCompany.id, query || "", (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && Array.isArray(res.data)) {
          callback(res.data);
          return;
        }
      } catch (e) {
        console.error("Backend searchItems error:", e);
      }
      fallbackLocalItems(query, callback);
    });
  } else {
    fallbackLocalItems(query, callback);
  }
}

function fallbackLocalItems(query, callback) {
  let list = [];
  if (activeCompany) {
    try {
      list = JSON.parse(localStorage.getItem(`alpha_items_${activeCompany.code}`) || "[]");
    } catch (e) {}
  }
  if (!query) {
    callback(list);
    return;
  }
  const q = query.toUpperCase();
  const filtered = list.filter((it) =>
    (it.name && it.name.toUpperCase().includes(q)) ||
    (it.sku && it.sku.toUpperCase().includes(q)) ||
    (it.alias && it.alias.toUpperCase().includes(q)) ||
    (it.group && it.group.toUpperCase().includes(q)) ||
    (it.category && it.category.toUpperCase().includes(q))
  );
  callback(filtered);
}

function fetchItemById(itemId, callback) {
  const comp = activeCompany || window.activeCompany;
  if (!activeCompany && comp) activeCompany = comp;
  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");
  if (isTrad && window.backend && typeof window.backend.traditional_getProduct === "function") {
    window.backend.traditional_getProduct(itemId, (resp) => {
      try {
        const res = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (res && res.success && res.data) {
          callback(res.data);
          return;
        }
      } catch (e) {
        console.error("Backend traditional_getProduct error:", e);
      }
      fallbackLocalItemById(itemId, callback);
    });
    return;
  }

  if (window.backend && comp) {
    window.backend.getItemById(comp.id, itemId, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          callback(res.data);
          return;
        }
      } catch (e) {
        console.error("Backend getItemById error:", e);
      }
      fallbackLocalItemById(itemId, callback);
    });
  } else {
    fallbackLocalItemById(itemId, callback);
  }
}

function fallbackLocalItemById(itemId, callback) {
  let list = [];
  if (activeCompany) {
    try {
      list = JSON.parse(localStorage.getItem(`alpha_items_${activeCompany.code}`) || "[]");
    } catch (e) {}
  }
  const found = list.find((it) => it.id === itemId || it.name === itemId);
  callback(found || null);
}

let selectedProductRowId = null;

function renderProductsList(query = "", groupFilter = "") {
  const tbody = document.getElementById("items-master-tbody");
  const countEl = document.getElementById("items-list-count");
  const emptyMsg = document.getElementById("items-list-empty-msg");
  const editBtn = document.getElementById("btn-items-list-edit-selected");
  const groupSelect = document.getElementById("items-list-group-filter");

  if (!tbody) return;
  tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; padding: 24px; color: #64748b;">Loading products...</td></tr>`;
  selectedProductRowId = null;
  if (editBtn) editBtn.disabled = true;

  fetchAllItems(query, (items) => {
    tbody.innerHTML = "";

    if (groupSelect && (!groupSelect.options || groupSelect.options.length <= 1)) {
      const groups = new Set();
      items.forEach((it) => {
        const g = it.item_group || it.group;
        if (g) groups.add(g);
      });
      groupSelect.innerHTML = `<option value="">All Categories (${items.length})</option>`;
      groups.forEach((g) => {
        const opt = document.createElement("option");
        opt.value = g;
        opt.textContent = g;
        groupSelect.appendChild(opt);
      });
      if (groupFilter) groupSelect.value = groupFilter;
    }

    let filtered = items || [];
    if (groupFilter) {
      filtered = filtered.filter((it) => (it.item_group || it.group) === groupFilter);
    }

    if (countEl) countEl.textContent = `Total Products: ${filtered.length}`;

    if (!filtered || filtered.length === 0) {
      if (emptyMsg) emptyMsg.style.display = "block";
      return;
    }
    if (emptyMsg) emptyMsg.style.display = "none";

    filtered.forEach((it, idx) => {
      const tr = document.createElement("tr");
      tr.dataset.id = it.id || "";
      tr.dataset.name = it.name || "";

      const price = parseFloat(it.selling_price ?? it.sellingPrice ?? it.sales_price ?? it.salesPrice ?? 0).toFixed(2);
      const stock = parseFloat(it.current_stock ?? it.op_stock_qty ?? it.opStockQty ?? 0);
      const barcode = (Array.isArray(it.barcodes) && it.barcodes.length > 0)
        ? it.barcodes.join(", ")
        : (it.sku || it.barcodes || it.alias || "-");
      const group = it.category || it.item_group || it.group || "General";
      const unit = it.unit || "Pcs.";
      const tax = it.tax_category || it.taxCategory || "GST 18%";

      let stockBadgeClass = "in-stock";
      if (stock <= 0) stockBadgeClass = "out-of-stock";
      else if (stock < 10) stockBadgeClass = "low-stock";

      tr.innerHTML = `
        <td style="text-align: center; color: #64748b;">${idx + 1}</td>
        <td><strong>${escapeHtml(it.name)}</strong></td>
        <td><span class="badge-barcode">${escapeHtml(barcode)}</span></td>
        <td><span class="badge-category">${escapeHtml(group)}</span></td>
        <td style="text-align: right; font-weight: 700; color: #166534;">₹ ${price}</td>
        <td style="text-align: center;">${escapeHtml(unit)}</td>
        <td style="text-align: right;"><span class="badge-stock ${stockBadgeClass}">${stock} ${escapeHtml(unit)}</span></td>
        <td style="text-align: center; color: #475569;">${escapeHtml(tax)}</td>
        <td style="text-align: center;">
          <button type="button" class="btn-table-action primary btn-edit-row" data-id="${it.id}">Edit</button>
        </td>
      `;

      tr.addEventListener("click", () => {
        tbody.querySelectorAll("tr").forEach((r) => r.classList.remove("selected-row"));
        tr.classList.add("selected-row");
        selectedProductRowId = it.id;
        if (editBtn) editBtn.disabled = false;
      });

      tr.addEventListener("dblclick", () => {
        loadProductForEditing(it.id);
      });

      const editBtnRow = tr.querySelector(".btn-edit-row");
      if (editBtnRow) {
        editBtnRow.addEventListener("click", (e) => {
          e.stopPropagation();
          loadProductForEditing(it.id);
        });
      }

      tbody.appendChild(tr);
    });
  });
}

function openProductsListView() {
  showScreen("view-items-list");
  renderProductsList();
}

// =============================================================
// SALES VOUCHER / BILLING ENGINE (Screenshot 5)
// =============================================================

// Get existing sales vouchers for active company
function getSalesVouchers() {
  if (!activeCompany) return [];
  const key = `alpha_vouchers_${activeCompany.code}`;
  try {
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved);
  } catch (e) {}
  return [];
}

function saveSalesVoucherRecord(voucher) {
  if (!activeCompany) return;
  const key = `alpha_vouchers_${activeCompany.code}`;
  const list = getSalesVouchers();
  list.push(voucher);
  localStorage.setItem(key, JSON.stringify(list));
}

// Generate the next strictly sequential & unique voucher number (starting 001)
function getNextVoucherNumber() {
  if (!activeCompany) return "001";
  const vouchers = getSalesVouchers();
  const cfg = getCompanyConfig(activeCompany.code);
  const padding = cfg.vchDigits || 3;
  const prefix = cfg.vchPrefix || "";

  let maxNum = 0;
  vouchers.forEach((v) => {
    // Extract integer sequence
    const numPart = v.vchNo.replace(/^\D+/g, "");
    const parsed = parseInt(numPart, 10);
    if (!isNaN(parsed) && parsed > maxNum) {
      maxNum = parsed;
    }
  });

  const nextSeq = Math.max(maxNum + 1, cfg.vchStart || 1);
  return prefix + String(nextSeq).padStart(padding, "0");
}

// Check if a voucher number is already used in active company
function isVoucherNumberUsed(vchNum) {
  const vouchers = getSalesVouchers();
  return vouchers.some((v) => v.vchNo.trim() === vchNum.trim());
}

// =============================================================
// REBUILT SALES INVOICE WORKFLOW & MASTER INTEGRATION
// =============================================================

// Party Autocomplete & Customer Masters State
let currentPartySuggestions = [];
let activePartySuggestionIndex = -1;
let partyDebounceTimer = null;

function setupPartyAutocomplete() {
  if (!vchPartyInput) return;
  const popup = document.getElementById("vch-party-autocomplete-popup");
  if (!popup) return;

  function positionPartyPopup() {
    if (!vchPartyInput || !popup) return;
    const inputRect = vchPartyInput.getBoundingClientRect();
    const formEl = document.querySelector(".sales-voucher-body") || document.getElementById("view-sales-voucher") || document.body;
    const formRect = formEl.getBoundingClientRect();

    const left = Math.max(10, inputRect.left);
    const rightBoundary = formRect.right - 12;
    let calculatedWidth = rightBoundary - left;
    const maxAvailable = window.innerWidth - left - 16;
    calculatedWidth = Math.min(Math.max(calculatedWidth, 650), maxAvailable);
    if (calculatedWidth < 450) calculatedWidth = maxAvailable;

    const top = inputRect.bottom + 2;
    const spaceBelow = window.innerHeight - top;
    if (spaceBelow < 220 && inputRect.top > 250) {
      popup.style.top = "auto";
      popup.style.bottom = `${window.innerHeight - inputRect.top + 2}px`;
    } else {
      popup.style.top = `${top}px`;
      popup.style.bottom = "auto";
    }

    popup.style.left = `${left}px`;
    popup.style.width = `${calculatedWidth}px`;
  }

  function renderSuggestions(list, query) {
    popup.innerHTML = "";
    currentPartySuggestions = list;
    activePartySuggestionIndex = -1;

    positionPartyPopup();

    if (!list || list.length === 0) {
      const noMatch = document.createElement("div");
      noMatch.className = "vch-party-no-match";
      noMatch.textContent = "No customer master found. Please create this customer in Administration → Masters → Add.";
      popup.appendChild(noMatch);
      popup.style.display = "flex";
      return;
    }

    // Wide horizontal table header for party suggestions
    const header = document.createElement("div");
    header.className = "vch-autocomplete-header";
    header.innerHTML = `
      <div class="vch-party-col-name">Party Name</div>
      <div class="vch-party-col-alias">Alias</div>
      <div class="vch-party-col-type">Type</div>
      <div class="vch-party-col-code">Customer Code</div>
      <div class="vch-party-col-gstin">GSTIN / Status</div>
    `;
    popup.appendChild(header);

    const listContainer = document.createElement("div");
    listContainer.className = "vch-autocomplete-list";

    list.forEach((acc, idx) => {
      const itemEl = document.createElement("div");
      itemEl.className = "vch-party-sugg-item vch-suggestion-row";
      itemEl.dataset.index = idx;

      const isCash = (acc.id === "CASH" || (acc.name && acc.name.toUpperCase() === "CASH"));
      const name = isCash ? "CASH" : (acc.name || "");
      const alias = acc.alias || (isCash ? "Cash Sale" : "-");
      const code = isCash ? "CASH" : (acc.code || acc.customer_code || acc.account_code || "-");
      const type = isCash ? "Direct Customer" : (acc.customer_category || acc.classification || acc.account_group || "Customer");
      const gstin = acc.gstin ? acc.gstin : (isCash ? "Unregistered" : "Unregistered");

      itemEl.innerHTML = `
        <div class="vch-party-col-name" title="${escapeHtml(name)}">${escapeHtml(name)}</div>
        <div class="vch-party-col-alias" title="${escapeHtml(alias)}">${escapeHtml(alias)}</div>
        <div class="vch-party-col-type" title="${escapeHtml(type)}"><span class="vch-party-badge ${isCash ? 'cash' : 'customer'}">${escapeHtml(type)}</span></div>
        <div class="vch-party-col-code" title="${escapeHtml(code)}">${escapeHtml(code)}</div>
        <div class="vch-party-col-gstin" title="${escapeHtml(gstin)}">${escapeHtml(gstin)}</div>
      `;

      itemEl.addEventListener("mousedown", (e) => {
        e.preventDefault();
        selectPartyItem(acc);
      });

      listContainer.appendChild(itemEl);
    });

    popup.appendChild(listContainer);
    popup.style.display = "flex";
  }

  function selectPartyItem(acc) {
    const isCash = (acc.id === "CASH" || (acc.name && acc.name.toUpperCase() === "CASH"));
    if (isCash) {
      vchPartyInput.value = "CASH";
      delete vchPartyInput.dataset.accountId;
    } else {
      vchPartyInput.value = acc.name || "";
      vchPartyInput.dataset.accountId = acc.id || "";
    }
    updateVoucherPartyCategory();
    hidePartyPopup();

    // Focus row 1 Item field immediately after selecting customer
    const firstRowItem = vchItemsTbody ? vchItemsTbody.querySelector('.vch-item-input[data-row="1"]') : null;
    if (firstRowItem) {
      firstRowItem.focus();
    }
  }

  function hidePartyPopup() {
    popup.style.display = "none";
    currentPartySuggestions = [];
    activePartySuggestionIndex = -1;
  }

  function highlightPartySuggestion(idx) {
    const items = popup.querySelectorAll(".vch-party-sugg-item");
    items.forEach((el, i) => {
      el.classList.toggle("active", i === idx);
      if (i === idx) el.scrollIntoView({ block: "nearest" });
    });
  }

  function filterEligibleCustomers(query) {
    const q = (query || "").trim().toUpperCase();
    const cashOption = {
      id: "CASH",
      name: "CASH",
      account_group: "Sundry Debtors",
      classification: "Customer",
      customer_category: "Direct Customer"
    };

    const eligible = (cachedAccountsList || []).filter((acc) => {
      const grp = acc.account_group || acc.group || "";
      const isCust = grp === "Sundry Debtors" || grp.includes("Both") || grp === "Customer" ||
                     acc.classification === "Customer" || acc.classification === "Both (Customer & Supplier)";
      return isCust || !grp;
    });

    let results = [];
    if (!q) {
      results = [cashOption, ...eligible.slice(0, 10)];
    } else {
      if ("CASH".includes(q) || "DIRECT".includes(q)) {
        results.push(cashOption);
      }
      const matched = eligible.filter((acc) => {
        const name = (acc.name || "").toUpperCase();
        const printName = (acc.print_name || acc.printName || "").toUpperCase();
        const alias = (acc.alias || "").toUpperCase();
        const gstin = (acc.gstin || "").toUpperCase();
        const mobile = (acc.mobile || acc.mobile_no || "").toUpperCase();
        return name.includes(q) || printName.includes(q) || alias.includes(q) || gstin.includes(q) || mobile.includes(q);
      });
      results.push(...matched);
    }
    return results;
  }

  vchPartyInput.addEventListener("input", () => {
    const q = vchPartyInput.value.trim();
    clearTimeout(partyDebounceTimer);
    partyDebounceTimer = setTimeout(() => {
      if (window.backend && window.backend.searchCustomers && activeCompany && q) {
        window.backend.searchCustomers(activeCompany.id, q, (resp) => {
          try {
            const r = JSON.parse(resp);
            if (r.success && Array.isArray(r.data)) {
              let list = r.data;
              if ("CASH".includes(q.toUpperCase())) {
                list = [{ id: "CASH", name: "CASH", customer_category: "Direct Customer" }, ...list];
              }
              renderSuggestions(list, q);
              return;
            }
          } catch (e) {}
          renderSuggestions(filterEligibleCustomers(q), q);
        });
      } else {
        renderSuggestions(filterEligibleCustomers(q), q);
      }
    }, 120);
  });

  vchPartyInput.addEventListener("focus", () => {
    const q = vchPartyInput.value.trim();
    renderSuggestions(filterEligibleCustomers(q), q);
  });

  vchPartyInput.addEventListener("keydown", (e) => {
    if (popup.style.display !== "none") {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        if (currentPartySuggestions.length > 0) {
          activePartySuggestionIndex = (activePartySuggestionIndex + 1) % currentPartySuggestions.length;
          highlightPartySuggestion(activePartySuggestionIndex);
        }
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        if (currentPartySuggestions.length > 0) {
          activePartySuggestionIndex = (activePartySuggestionIndex - 1 + currentPartySuggestions.length) % currentPartySuggestions.length;
          highlightPartySuggestion(activePartySuggestionIndex);
        }
        return;
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        if (activePartySuggestionIndex >= 0 && currentPartySuggestions[activePartySuggestionIndex]) {
          selectPartyItem(currentPartySuggestions[activePartySuggestionIndex]);
          return;
        } else if (currentPartySuggestions.length === 1) {
          selectPartyItem(currentPartySuggestions[0]);
          return;
        } else {
          const text = vchPartyInput.value.trim().toUpperCase();
          if (text === "CASH" || text === "CASH SALE") {
            selectPartyItem({ id: "CASH", name: "CASH" });
            return;
          }
          const exactMatch = (cachedAccountsList || []).find(a => 
            (a.name || "").toUpperCase() === text || 
            (a.alias || "").toUpperCase() === text
          );
          if (exactMatch) {
            selectPartyItem(exactMatch);
            return;
          }
          alert("No customer master found. Please create this customer in Administration → Masters → Add.");
          vchPartyInput.focus();
          return;
        }
      } else if (e.key === "Escape") {
        hidePartyPopup();
        return;
      }
    } else {
      if (e.key === "Enter") {
        e.preventDefault();
        const text = vchPartyInput.value.trim().toUpperCase();
        if (text === "CASH" || text === "CASH SALE" || text === "") {
          selectPartyItem({ id: "CASH", name: "CASH" });
          return;
        }
        const exactMatch = (cachedAccountsList || []).find(a => 
          (a.name || "").toUpperCase() === text || 
          (a.alias || "").toUpperCase() === text
        );
        if (exactMatch) {
          selectPartyItem(exactMatch);
          return;
        }
        alert("No customer master found. Please create this customer in Administration → Masters → Add.");
        vchPartyInput.focus();
      }
    }
  });

  document.addEventListener("click", (e) => {
    if (!popup.contains(e.target) && e.target !== vchPartyInput) {
      hidePartyPopup();
    }
  });
}

function refreshSalesVoucherNumber() {
  const isTrad = (typeof activeBillingMode !== "undefined" && activeBillingMode === "traditional") || (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");
  const series = vchSeries ? (vchSeries.value || "Main") : "Main";

  if (isTrad && window.backend && typeof window.backend.traditional_getNextVoucherNumber === "function") {
    window.backend.traditional_getNextVoucherNumber(series, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.data) {
          const vchNumStr = typeof r.data === "object" ? (r.data.voucher_number || r.data.vch_no || r.data) : r.data;
          if (vchNumber) vchNumber.value = vchNumStr;
          if (infoVchNo) infoVchNo.textContent = vchNumStr;
          return;
        }
      } catch (e) {
        console.error("traditional_getNextVoucherNumber error:", e);
      }
    });
  } else if (window.backend && window.backend.getNextVoucherNumber && activeCompany) {
    window.backend.getNextVoucherNumber(activeCompany.id, series, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          if (vchNumber) vchNumber.value = r.data;
          if (infoVchNo) infoVchNo.textContent = r.data;
          return;
        }
      } catch (e) {}
      const fallbackNo = getNextVoucherNumber();
      if (vchNumber) vchNumber.value = fallbackNo;
      if (infoVchNo) infoVchNo.textContent = fallbackNo;
    });
  } else {
    const nextNo = getNextVoucherNumber();
    if (vchNumber) vchNumber.value = nextNo;
    if (infoVchNo) infoVchNo.textContent = nextNo;
  }
}

if (typeof vchSeries !== "undefined" && vchSeries) {
  vchSeries.addEventListener("change", () => {
    if (typeof isSalesModifyMode !== "undefined" && isSalesModifyMode) return;
    refreshSalesVoucherNumber();
  });
}

// Initialize Sales Billing Screen
function initSalesVoucherScreen() {
  isSalesModifyMode = false;
  currentModifySaleVchId = null;
  const modIn = document.getElementById("sales-modify-vch-id");
  if (modIn) modIn.value = "";
  const titleEl = document.getElementById("sales-voucher-screen-title");
  if (titleEl) titleEl.textContent = "Add Sales Voucher";

  // Request next available sequential voucher number from database atomically
  refreshSalesVoucherNumber();

  // Preserve header defaults: Series, Date, Mat Centre, Sale Type
  const now = new Date();
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const yyyy = now.getFullYear();
  if (vchDate && !vchDate.value) {
    vchDate.value = `${dd}-${mm}-${yyyy}`;
  }
  const days = ["(Sun)", "(Mon)", "(Tue)", "(Wed)", "(Thu)", "(Fri)", "(Sat)"];
  if (vchDayLabel) vchDayLabel.textContent = days[now.getDay()];

  if (vchSeries && !vchSeries.value) vchSeries.value = "Main";
  if (vchMatCentre && !vchMatCentre.value) vchMatCentre.value = "Main Store";
  if (vchSaleType && !vchSaleType.value) vchSaleType.value = "L/GST-18%";

  // Reset inputs and party
  if (vchPartyInput) {
    vchPartyInput.value = "CASH";
    delete vchPartyInput.dataset.accountId;
  }
  if (vchNarration) vchNarration.value = "";
  updateVoucherPartyCategory();

  // Load customer accounts from permanent database
  if (activeCompany) {
    if (window.backend && window.backend.searchCustomers) {
      window.backend.searchCustomers(activeCompany.id, "", (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success && Array.isArray(r.data)) {
            cachedAccountsList = r.data;
            return;
          }
        } catch (e) {}
        const key = `alpha_accounts_${activeCompany.code}`;
        cachedAccountsList = JSON.parse(localStorage.getItem(key) || "[]");
      });
    } else {
      const key = `alpha_accounts_${activeCompany.code}`;
      cachedAccountsList = JSON.parse(localStorage.getItem(key) || "[]");
    }
  }

  // Render 11 item rows and recalculate totals
  renderVoucherItemRows();
  recalculateVoucherTotals();

  // Focus party input automatically
  setTimeout(() => {
    if (vchPartyInput) {
      vchPartyInput.focus();
      vchPartyInput.select();
    }
  }, 60);
}

// Product Lookup by Barcode or Name
function resolveItemByBarcodeOrName(val, callback) {
  if (!val) {
    callback(null);
    return;
  }
  const clean = val.trim();
  const upper = clean.toUpperCase();

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");
  if (isTrad && window.backend && typeof window.backend.traditional_findProductByBarcode === "function") {
    window.backend.traditional_findProductByBarcode(clean, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.data) {
          callback(r.data);
          return;
        } else if (r && !r.success && r.error && r.error.includes("inactive")) {
          alert(r.error);
          callback(null);
          return;
        }
      } catch (e) {
        console.error("traditional_findProductByBarcode error:", e);
      }
      searchCatalogFallback();
    });
    return;
  }

  // 1. Try barcode bridge first if available (Fast Billing / Legacy)
  if (window.backend && window.backend.findByBarcode && activeCompany) {
    window.backend.findByBarcode(activeCompany.id, clean, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          callback(r.data);
          return;
        }
      } catch (e) {}
      searchCatalogFallback();
    });
  } else {
    searchCatalogFallback();
  }

  function searchCatalogFallback() {
    fetchAllItems(clean, (items) => {
      if (!items || items.length === 0) {
        callback(null);
        return;
      }
      // Exact barcode match (supports arrays and strings)
      let found = items.find(it => {
        if (Array.isArray(it.barcodes)) {
          return it.barcodes.some(b => b && b.toUpperCase() === upper);
        }
        if (typeof it.barcodes === "string") {
          return it.barcodes.toUpperCase() === upper;
        }
        if (it.barcode && typeof it.barcode === "string") {
          return it.barcode.toUpperCase() === upper;
        }
        return false;
      });
      // Exact SKU / alias match
      if (!found) {
        found = items.find(it => (it.sku && it.sku.toUpperCase() === upper) || (it.alias && it.alias.toUpperCase() === upper));
      }
      // Exact name match
      if (!found) {
        found = items.find(it => it.name && it.name.toUpperCase() === upper);
      }
      // Prefix name match
      if (!found) {
        found = items.find(it => it.name && it.name.toUpperCase().startsWith(upper));
      }
      // First matching item
      if (!found && items.length > 0) {
        found = items[0];
      }
      callback(found || null);
    });
  }
}

// Populate line item row with product data from Item Master
function populateVoucherRowWithItem(rowNum, item) {
  if (!item) return;

  // Inactive product rejection
  if (item.isActive === false || item.is_active === false) {
    alert(`Product "${item.name}" is inactive and cannot be billed.`);
    return;
  }

  const rowInput = vchItemsTbody.querySelector(`.vch-item-input[data-row="${rowNum}"]`);
  const unitEl = vchItemsTbody.querySelector(`.vch-unit-input[data-row="${rowNum}"]`);
  const priceEl = vchItemsTbody.querySelector(`.vch-price-input[data-row="${rowNum}"]`);
  const qtyEl = vchItemsTbody.querySelector(`.vch-qty-input[data-row="${rowNum}"]`);

  // Extract actual saved selling price (never fallback to COGS or purchase cost)
  const rawPrice = item.selling_price ?? item.sellingPrice ?? item.sales_price ?? item.salesPrice ?? 0;
  const price = parseFloat(rawPrice) || 0;

  if (rowInput) {
    rowInput.value = item.name || "";
    rowInput.dataset.itemId = item.id || "";
    rowInput.dataset.productBarcode = Array.isArray(item.barcodes) ? (item.barcodes[0] || "") : (item.barcodes || item.barcode || item.alias || "");
    rowInput.dataset.sku = item.sku || item.alias || "";
    rowInput.dataset.unit = item.unit || "Pcs.";
    rowInput.dataset.sellingPrice = price.toFixed(2);
    rowInput.dataset.taxCategory = item.tax_category || item.taxCategory || "GST 18%";
    rowInput.dataset.taxRate = item.tax_rate_percent || item.taxRatePercent || item.tax_rate || "18";
    rowInput.dataset.hsn = item.hsn || "";
  }
  // Standard Unit loaded automatically from Item Master (read-only)
  if (unitEl) {
    unitEl.value = item.unit || "Pcs.";
  }

  // Populate selling price from Item Master's saved selling_price
  if (priceEl) {
    priceEl.value = price.toFixed(2);
  }

  // Default quantity to 1 if empty or <= 0
  if (qtyEl && (!qtyEl.value || parseFloat(qtyEl.value) <= 0)) {
    qtyEl.value = "1";
  }

  calcRowAmount(rowNum);
  recalculateVoucherTotals();

  if (vchItemInfo) {
    const skuText = item.sku ? ` | SKU: ${escapeHtml(item.sku)}` : "";
    const hsnText = item.hsn ? ` | HSN: ${escapeHtml(item.hsn)}` : "";
    const taxCat = item.tax_category || item.taxCategory || "GST 18%";
    const taxRate = item.tax_rate_percent || item.taxRatePercent || item.tax_rate || "18";
    vchItemInfo.innerHTML = `
      Product: <strong>${escapeHtml(item.name)}</strong>${skuText}<br/>
      Category: ${escapeHtml(item.item_group || item.category || item.group || "General")} | Unit: ${escapeHtml(item.unit || "Pcs.")}${hsnText}<br/>
      Selling Price: ₹${price.toFixed(2)} | Tax Cat: ${escapeHtml(taxCat)} (${taxRate}%)
    `;
  }

  showNotification(`Selected ${item.name} (₹${price.toFixed(2)})`);
  // Enter key from Item moves focus directly to Quantity field, skipping read-only Unit field!
  if (qtyEl) {
    qtyEl.focus();
    qtyEl.select();
  }
}

// Reset an invoice row to clean state and recalculate totals
function clearVoucherRow(rowNum) {
  const rowInput = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-item-input[data-row="${rowNum}"]`) : null;
  const unitEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-unit-input[data-row="${rowNum}"]`) : null;
  const priceEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-price-input[data-row="${rowNum}"]`) : null;
  const qtyEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-qty-input[data-row="${rowNum}"]`) : null;
  const amtEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-amount-input[data-row="${rowNum}"]`) : null;

  if (rowInput) {
    delete rowInput.dataset.itemId;
    delete rowInput.dataset.productBarcode;
    delete rowInput.dataset.sku;
    delete rowInput.dataset.unit;
    delete rowInput.dataset.sellingPrice;
    delete rowInput.dataset.taxCategory;
    delete rowInput.dataset.taxRate;
    delete rowInput.dataset.hsn;
  }
  if (unitEl) unitEl.value = "Pcs.";
  if (priceEl) priceEl.value = "0.00";
  if (qtyEl) qtyEl.value = "1";
  if (amtEl) {
    amtEl.value = "0.00";
    amtEl.dataset.gross = "0.00";
    amtEl.dataset.discountPercent = "0.00";
    amtEl.dataset.discountAmount = "0.00";
  }
  if (vchItemInfo && rowInput && (!rowInput.value || rowInput.value.trim() === "")) {
    vchItemInfo.innerHTML = "No item selected";
  }
  recalculateVoucherTotals();
}

let activeVchRowForPopup = null;
let currentVchSuggestions = [];
let activeVchSuggestionIndex = -1;

function setupVoucherAutocomplete(input, row) {
  let timer = null;

  input.addEventListener("input", () => {
    const q = input.value.trim();
    clearTimeout(timer);

    if (!q) {
      hideVchAutocompletePopup();
      clearVoucherRow(row);
      return;
    }

    timer = setTimeout(() => {
      fetchAllItems(q, (items) => {
        if (!items || items.length === 0) {
          hideVchAutocompletePopup();
          return;
        }
        currentVchSuggestions = items.slice(0, 8);
        activeVchSuggestionIndex = -1;
        activeVchRowForPopup = row;
        renderVchAutocompletePopup(input, currentVchSuggestions, row);
      });
    }, 150);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "F1") {
      e.preventDefault();
      openProductSearchModal("VOUCHER", row);
      return;
    }

    const popupVisible = vchItemAutocompletePopup && vchItemAutocompletePopup.style.display !== "none";

    if (popupVisible) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        activeVchSuggestionIndex = (activeVchSuggestionIndex + 1) % currentVchSuggestions.length;
        highlightVchSuggestion(activeVchSuggestionIndex);
        return;
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        activeVchSuggestionIndex = (activeVchSuggestionIndex - 1 + currentVchSuggestions.length) % currentVchSuggestions.length;
        highlightVchSuggestion(activeVchSuggestionIndex);
        return;
      } else if (e.key === "Escape") {
        e.preventDefault();
        hideVchAutocompletePopup();
        return;
      }
    }

    if (e.key === "Enter") {
      e.preventDefault();
      e.stopPropagation();

      // Case 1: Active suggestion highlighted in popup
      if (popupVisible && activeVchSuggestionIndex >= 0 && currentVchSuggestions[activeVchSuggestionIndex]) {
        const chosen = currentVchSuggestions[activeVchSuggestionIndex];
        hideVchAutocompletePopup();
        populateVoucherRowWithItem(row, chosen);
        return;
      }

      // Case 2: User scanned a barcode or entered a product name / SKU
      const val = input.value.trim();
      if (!val) {
        const nextRow = parseInt(row, 10) + 1;
        const nextItem = vchItemsTbody.querySelector(`.vch-item-input[data-row="${nextRow}"]`);
        if (nextItem) nextItem.focus();
        else if (btnSaveSalesVoucher) btnSaveSalesVoucher.focus();
        return;
      }

      hideVchAutocompletePopup();

      resolveItemByBarcodeOrName(val, (matchedItem) => {
        if (matchedItem) {
          populateVoucherRowWithItem(row, matchedItem);
        } else {
          // Prevent adding unregistered products
          alert(`Product "${val}" not found in Item Master. Only registered products can be added to the invoice.`);
          input.focus();
          input.select();
        }
      });
    }
  });
}

function renderVchAutocompletePopup(input, items, row) {
  if (!vchItemAutocompletePopup) return;
  vchItemAutocompletePopup.innerHTML = "";

  if (!items || items.length === 0) {
    hideVchAutocompletePopup();
    return;
  }

  const inputRect = input.getBoundingClientRect();
  const formEl = document.querySelector(".sales-voucher-body") || document.getElementById("view-sales-voucher") || document.body;
  const formRect = formEl.getBoundingClientRect();

  const left = Math.max(10, inputRect.left);
  const rightBoundary = formRect.right - 12;
  let calculatedWidth = rightBoundary - left;
  const maxAvailable = window.innerWidth - left - 16;
  calculatedWidth = Math.min(Math.max(calculatedWidth, 650), maxAvailable);
  if (calculatedWidth < 450) calculatedWidth = maxAvailable;

  const top = inputRect.bottom + 2;
  const spaceBelow = window.innerHeight - top;
  if (spaceBelow < 220 && inputRect.top > 250) {
    vchItemAutocompletePopup.style.top = "auto";
    vchItemAutocompletePopup.style.bottom = `${window.innerHeight - inputRect.top + 2}px`;
  } else {
    vchItemAutocompletePopup.style.top = `${top}px`;
    vchItemAutocompletePopup.style.bottom = "auto";
  }

  vchItemAutocompletePopup.style.left = `${left}px`;
  vchItemAutocompletePopup.style.width = `${calculatedWidth}px`;

  // Wide horizontal table header for product suggestions
  const header = document.createElement("div");
  header.className = "vch-autocomplete-header";
  header.innerHTML = `
    <div class="vch-item-col-name">Product Name</div>
    <div class="vch-item-col-sku">SKU</div>
    <div class="vch-item-col-barcode">Barcode</div>
    <div class="vch-item-col-unit">Unit</div>
    <div class="vch-item-col-price">Price (₹)</div>
    <div class="vch-item-col-tax">GST Rate</div>
  `;
  vchItemAutocompletePopup.appendChild(header);

  const listContainer = document.createElement("div");
  listContainer.className = "vch-autocomplete-list";

  items.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "vch-suggestion-item vch-suggestion-row";
    div.dataset.index = index;

    const rawPrice = item.selling_price ?? item.sellingPrice ?? item.sales_price ?? item.salesPrice ?? 0;
    const price = (parseFloat(rawPrice) || 0).toFixed(2);
    const sku = item.sku || item.alias || "-";
    const barcode = Array.isArray(item.barcodes) ? (item.barcodes[0] || "-") : (item.barcodes || item.barcode || "-");
    const unit = item.unit || "Pcs.";
    const taxCat = item.tax_category || item.taxCategory || "GST 18%";
    const taxRate = item.tax_rate_percent || item.taxRatePercent || "18";
    const taxDisplay = `${taxRate}%`;

    div.innerHTML = `
      <div class="vch-item-col-name" title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</div>
      <div class="vch-item-col-sku" title="${escapeHtml(sku)}">${escapeHtml(sku)}</div>
      <div class="vch-item-col-barcode" title="${escapeHtml(barcode)}">${escapeHtml(barcode)}</div>
      <div class="vch-item-col-unit" title="${escapeHtml(unit)}">${escapeHtml(unit)}</div>
      <div class="vch-item-col-price" title="₹ ${price}">₹ ${price}</div>
      <div class="vch-item-col-tax" title="${escapeHtml(taxCat)} (${taxDisplay})">${escapeHtml(taxDisplay)}</div>
    `;

    div.addEventListener("mousedown", (e) => {
      e.preventDefault();
      populateVoucherRowWithItem(row, item);
      hideVchAutocompletePopup();
    });

    listContainer.appendChild(div);
  });

  vchItemAutocompletePopup.appendChild(listContainer);
  vchItemAutocompletePopup.style.display = "flex";
}

function hideVchAutocompletePopup() {
  if (vchItemAutocompletePopup) {
    vchItemAutocompletePopup.style.display = "none";
  }
  currentVchSuggestions = [];
  activeVchSuggestionIndex = -1;
  activeVchRowForPopup = null;
}

function highlightVchSuggestion(index) {
  if (!vchItemAutocompletePopup) return;
  const items = vchItemAutocompletePopup.querySelectorAll(".vch-suggestion-item");
  items.forEach((el, i) => {
    el.classList.toggle("active", i === index);
    if (i === index) el.scrollIntoView({ block: "nearest" });
  });
}

// Hide voucher autocomplete popup on outside click
document.addEventListener("click", (e) => {
  if (vchItemAutocompletePopup && !vchItemAutocompletePopup.contains(e.target) && !e.target.classList.contains("vch-item-input")) {
    hideVchAutocompletePopup();
  }
});

// Dismiss autocomplete popups on table scroll or window resize
const vchTableWrapperEl = document.querySelector(".vch-table-wrapper");
if (vchTableWrapperEl) {
  vchTableWrapperEl.addEventListener("scroll", () => {
    hideVchAutocompletePopup();
  });
}

window.addEventListener("resize", () => {
  hideVchAutocompletePopup();
  const partyPopup = document.getElementById("vch-party-autocomplete-popup");
  if (partyPopup) partyPopup.style.display = "none";
});

// Render 11 item rows into billing table
function renderVoucherItemRows() {
  if (!vchItemsTbody) return;
  vchItemsTbody.innerHTML = "";

  for (let i = 1; i <= 11; i++) {
    const tr = document.createElement("tr");
    tr.dataset.row = i;

    // Ordered columns: S.N. | Item | Unit | Qty. | Price (Rs.) | Amount (Rs.)
    // Note: Unit is visibly read-only, populated from Item Master, with tabindex="-1" so keyboard flow skips directly to Qty!
    tr.innerHTML = `
      <td class="col-vch-sn">${i}</td>
      <td class="col-vch-item">
        <input type="text" class="vch-item-input" data-row="${i}" placeholder="${i === 1 ? 'Scan barcode or type product name (F1 to search)...' : ''}" autocomplete="off" />
      </td>
      <td class="col-vch-unit">
        <input type="text" class="vch-unit-input input-readonly" data-row="${i}" value="Pcs." readonly tabindex="-1" title="Unit from Item Master (Automatic &amp; Read-Only)" />
      </td>
      <td class="col-vch-qty">
        <input type="number" step="1" min="0" class="vch-qty-input" data-row="${i}" placeholder="0" />
      </td>
      <td class="col-vch-price">
        <input type="number" step="0.01" min="0" class="vch-price-input" data-row="${i}" placeholder="0.00" />
      </td>
      <td class="col-vch-amount">
        <input type="text" class="vch-amount-input" data-row="${i}" value="0.00" readonly tabindex="-1" style="font-weight: 700; color: #1e40af;" />
      </td>
    `;

    vchItemsTbody.appendChild(tr);
  }

  // Attach input calculation listeners
  vchItemsTbody.querySelectorAll(".vch-qty-input, .vch-price-input").forEach((input) => {
    input.addEventListener("input", (e) => {
      const row = e.target.dataset.row;
      calcRowAmount(row);
      recalculateVoucherTotals();
    });
  });

  // Attach Enter navigation on Quantity inputs:
  // Enter confirms line item, recalculates line amount and totals, and moves focus directly to next row's Item field!
  vchItemsTbody.querySelectorAll(".vch-qty-input").forEach((qtyInput) => {
    qtyInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        const row = parseInt(qtyInput.dataset.row, 10);
        const val = parseFloat(qtyInput.value);
        if (isNaN(val) || val <= 0) {
          qtyInput.value = "1";
        }
        calcRowAmount(row);
        recalculateVoucherTotals();

        // Move directly to next row's Item field
        const nextRow = row + 1;
        const nextItemInput = vchItemsTbody.querySelector(`.vch-item-input[data-row="${nextRow}"]`);
        if (nextItemInput) {
          nextItemInput.focus();
        } else {
          // If on the last row, focus Save button
          if (btnSaveSalesVoucher) btnSaveSalesVoucher.focus();
        }
      }
    });
  });

  // Attach autocomplete & selection listeners
  vchItemsTbody.querySelectorAll(".vch-item-input").forEach((input) => {
    const row = input.dataset.row;
    setupVoucherAutocomplete(input, row);

    input.addEventListener("focus", (e) => {
      const val = e.target.value.trim();
      if (val && vchItemInfo) {
        vchItemInfo.textContent = `Selected Product: ${val}`;
      }
    });
  });
}

function updateVoucherPartyCategory() {
  if (!vchPartyInput) return;
  const partyName = vchPartyInput.value.trim().toUpperCase();
  const badgeEl = document.getElementById("vch-party-category-badge");
  if (!badgeEl) return;

  if (!partyName || partyName === "CASH" || partyName === "CASH SALE") {
    delete vchPartyInput.dataset.accountId;
    activeVoucherCustomerCategory = "Direct Customer";
    const discPct = cachedCategoryDiscounts["Direct Customer"] || 0.0;
    badgeEl.textContent = `Direct (${discPct}%)`;
    badgeEl.className = "vch-party-category-badge direct";
    badgeEl.style.display = "inline-flex";
    return;
  }

  const foundAcc = (cachedAccountsList || []).find(a => 
    (a.name || "").toUpperCase() === partyName ||
    (a.print_name || a.printName || "").toUpperCase() === partyName ||
    (a.alias || "").toUpperCase() === partyName
  );
  if (foundAcc && foundAcc.id) {
    vchPartyInput.dataset.accountId = foundAcc.id;
  } else {
    delete vchPartyInput.dataset.accountId;
  }

  const cat = (foundAcc && foundAcc.customer_category) ? foundAcc.customer_category : (foundAcc && foundAcc.customerCategory ? foundAcc.customerCategory : "Direct Customer");
  activeVoucherCustomerCategory = cat;
  const discPct = cachedCategoryDiscounts[cat] !== undefined ? cachedCategoryDiscounts[cat] : (cat === "Commercial" ? 5.0 : (cat === "Sub-Commercial" ? 2.5 : 0.0));

  const cls = cat === "Commercial" ? "commercial" : (cat === "Sub-Commercial" ? "sub-commercial" : "direct");
  badgeEl.textContent = `${cat} (${discPct}% Disc)`;
  badgeEl.className = `vch-party-category-badge ${cls}`;
  badgeEl.style.display = "inline-flex";
}

function calcRowAmount(row) {
  const qtyEl = vchItemsTbody.querySelector(`.vch-qty-input[data-row="${row}"]`);
  const priceEl = vchItemsTbody.querySelector(`.vch-price-input[data-row="${row}"]`);
  const amtEl = vchItemsTbody.querySelector(`.vch-amount-input[data-row="${row}"]`);
  if (!qtyEl || !priceEl || !amtEl) return;

  const qty = parseFloat(qtyEl.value) || 0;
  const price = parseFloat(priceEl.value) || 0;
  const gross = Math.round(qty * price * 100) / 100;

  const catRate = cachedCategoryDiscounts[activeVoucherCustomerCategory] || 0.0;
  const discAmt = Math.round(gross * (catRate / 100) * 100) / 100;
  const netAmt = Math.max(0, Math.round((gross - discAmt) * 100) / 100);

  amtEl.value = netAmt.toFixed(2);
  amtEl.dataset.gross = gross.toFixed(2);
  amtEl.dataset.discountPercent = catRate.toFixed(2);
  amtEl.dataset.discountAmount = discAmt.toFixed(2);
}

// Calculate Voucher Grand Total, Tax & Bill Sundries
function recalculateVoucherTotals() {
  let subtotal = 0;
  vchItemsTbody.querySelectorAll(".vch-amount-input").forEach((input) => {
    subtotal += parseFloat(input.value) || 0;
  });

  vchSubtotalVal.textContent = subtotal.toFixed(2);
  taxableAmtDisplay.textContent = subtotal.toFixed(2);

  const saleType = vchSaleType.value;
  let taxRate = 18;
  let isInterState = false;

  if (saleType === "L/GST-18%") {
    taxRate = 18;
    isInterState = false;
    saleTypeDesc.textContent = "Local Sales, Tax at Voucher Level (Rate : 18% all Items)";
  } else if (saleType === "L/GST-12%") {
    taxRate = 12;
    isInterState = false;
    saleTypeDesc.textContent = "Local Sales, Tax at Voucher Level (Rate : 12% all Items)";
  } else if (saleType === "L/GST-5%") {
    taxRate = 5;
    isInterState = false;
    saleTypeDesc.textContent = "Local Sales, Tax at Voucher Level (Rate : 5% all Items)";
  } else if (saleType === "L/GST-28%") {
    taxRate = 28;
    isInterState = false;
    saleTypeDesc.textContent = "Local Sales, Tax at Voucher Level (Rate : 28% all Items)";
  } else if (saleType === "I/GST-18%") {
    taxRate = 18;
    isInterState = true;
    saleTypeDesc.textContent = "Inter-State Sales (IGST 18% all Items)";
  } else {
    taxRate = 0;
    isInterState = false;
    saleTypeDesc.textContent = "Exempt / Non-GST Sales";
  }

  taxRateDisplay.textContent = `${taxRate}%`;

  let cgst = 0;
  let sgst = 0;
  let igst = 0;

  if (taxRate > 0) {
    if (isInterState) {
      igst = Math.round(((subtotal * taxRate) / 100) * 100) / 100;
      sundry1Name.textContent = `IGST ${taxRate}%`;
      sundry1Rate.textContent = `${taxRate}.00`;
      sundry1Amt.textContent = igst.toFixed(2);

      sundry2Name.textContent = "-";
      sundry2Rate.textContent = "-";
      sundry2Amt.textContent = "0.00";

      cgstDisplay.textContent = "-";
      sgstDisplay.textContent = igst.toFixed(2);
    } else {
      const halfRate = taxRate / 2;
      cgst = Math.round(((subtotal * halfRate) / 100) * 100) / 100;
      sgst = Math.round(((subtotal * halfRate) / 100) * 100) / 100;

      sundry1Name.textContent = `CGST ${halfRate}%`;
      sundry1Rate.textContent = `${halfRate}.00`;
      sundry1Amt.textContent = cgst.toFixed(2);

      sundry2Name.textContent = `SGST ${halfRate}%`;
      sundry2Rate.textContent = `${halfRate}.00`;
      sundry2Amt.textContent = sgst.toFixed(2);

      cgstDisplay.textContent = cgst.toFixed(2);
      sgstDisplay.textContent = sgst.toFixed(2);
    }
  } else {
    sundry1Name.textContent = "CGST 0%";
    sundry1Rate.textContent = "0.00";
    sundry1Amt.textContent = "0.00";
    sundry2Name.textContent = "SGST 0%";
    sundry2Rate.textContent = "0.00";
    sundry2Amt.textContent = "0.00";
    cgstDisplay.textContent = "0.00";
    sgstDisplay.textContent = "0.00";
  }

  const rawTotal = Math.round((subtotal + cgst + sgst + igst) * 100) / 100;
  const roundedTotal = Math.round(rawTotal);
  const roundDiff = Math.round((roundedTotal - rawTotal) * 100) / 100;
  sundryRoundAmt.textContent = (roundDiff >= 0 ? "+" : "") + roundDiff.toFixed(2);

  vchGrandTotal.textContent = `₹ ${roundedTotal.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

vchSaleType.addEventListener("change", recalculateVoucherTotals);
btnApplyTax.addEventListener("click", () => {
  recalculateVoucherTotals();
  showNotification("Tax & Bill Sundry recalculated.");
});

// Save Sales Voucher with atomic voucher sequence and post-save print transition
function handleSaveSalesVoucher() {
  const party = vchPartyInput.value.trim();
  if (!party) {
    alert("Please enter or select a Party / Customer Name.");
    vchPartyInput.focus();
    return;
  }

  // 1. Party Selection - Masters Database Only Validation
  const isDirectCash = (party.toUpperCase() === "CASH" || party.toUpperCase() === "CASH SALE" || party.toUpperCase() === "DIRECT CUSTOMER");
  let customerAccountId = vchPartyInput.dataset.accountId;

  if (isDirectCash) {
    // Direct cash sale party is allowed for local retail billing,
    // but MUST NOT be allowed for inter-state (IGST) transactions where a registered customer master is required.
    const saleType = vchSaleType.value;
    if (saleType && saleType.startsWith("I/GST")) {
      alert("Direct Cash Sale (CASH) is not permitted for Inter-State (IGST) sales. Please select a registered Customer Master from Masters with a valid State and GSTIN.");
      vchPartyInput.focus();
      return;
    }
  } else {
    // If not direct cash, party MUST exist in Customer Masters database
    if (!customerAccountId) {
      const match = (cachedAccountsList || []).find(a => 
        (a.name || "").toUpperCase() === party.toUpperCase() ||
        (a.print_name || a.printName || "").toUpperCase() === party.toUpperCase() ||
        (a.alias || "").toUpperCase() === party.toUpperCase()
      );
      if (match && match.id) {
        customerAccountId = match.id;
        vchPartyInput.dataset.accountId = match.id;
      }
    }

    if (!customerAccountId) {
      alert("No customer master found. Please create this customer in Administration → Masters → Add.");
      vchPartyInput.focus();
      return;
    }
  }

  // 2. Validate products / line items
  const items = [];
  let hasUnregisteredProduct = false;
  let unregisteredProductName = "";

  vchItemsTbody.querySelectorAll("tr").forEach((tr) => {
    const row = tr.dataset.row;
    const nameEl = tr.querySelector(`.vch-item-input[data-row="${row}"]`);
    const qtyEl = tr.querySelector(`.vch-qty-input[data-row="${row}"]`);
    const unitEl = tr.querySelector(`.vch-unit-input[data-row="${row}"]`);
    const priceEl = tr.querySelector(`.vch-price-input[data-row="${row}"]`);
    const amtEl = tr.querySelector(`.vch-amount-input[data-row="${row}"]`);

    const name = nameEl.value.trim();
    const qty = parseFloat(qtyEl.value) || 0;
    const price = parseFloat(priceEl.value) || 0;
    const amount = parseFloat(amtEl.value) || 0;

    if (name) {
      const itemId = nameEl.dataset.itemId;
      if (!itemId && !nameEl.dataset.productBarcode) {
        hasUnregisteredProduct = true;
        unregisteredProductName = name;
      }
      if (qty > 0 || price > 0) {
        items.push({ 
          sn: row, 
          name, 
          qty: qty > 0 ? qty : 1, 
          unit: unitEl ? unitEl.value : "Pcs.", 
          price, 
          amount: amount > 0 ? amount : (qty * price),
          item_id: itemId || undefined
        });
      }
    }
  });

  if (hasUnregisteredProduct) {
    alert(`Product "${unregisteredProductName}" is not registered in Item Master. Only registered products can be added to the invoice.`);
    return;
  }

  if (items.length === 0) {
    alert("Please add at least one registered item with quantity and price.");
    const firstItem = vchItemsTbody.querySelector('.vch-item-input[data-row="1"]');
    if (firstItem) firstItem.focus();
    return;
  }

  const subtotal = parseFloat(vchSubtotalVal.textContent) || 0;
  const grandTotal = vchGrandTotal.textContent.replace("₹", "").trim();

  // If modifying existing invoice
  if (isSalesModifyMode && currentModifySaleVchId) {
    const payload = {
      party_name: isDirectCash ? "CASH" : party,
      account_id: customerAccountId || undefined,
      customer_category: activeVoucherCustomerCategory || "Direct Customer",
      sale_type: vchSaleType.value,
      payment_method: "CASH",
      series: vchSeries.value || "Main",
      vch_date: vchDate.value,
      narration: vchNarration.value.trim(),
      items: items.map((it) => ({
        item_id: it.item_id || undefined,
        name: it.name,
        qty: it.qty,
        unit: it.unit,
        price: it.price,
        discount_percent: it.discount_percent || (cachedCategoryDiscounts[activeVoucherCustomerCategory] || 0.0),
        discount_amount: it.discount_amount || 0.0,
        line_total: it.amount
      }))
    };

    if (window.backend && activeCompany) {
      window.backend.modifySaleInvoice(activeCompany.id, currentModifySaleVchId, JSON.stringify(payload), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
            showNotification(`Sales Bill #${vchNumber.value} modified successfully! Inventory and accounts reconciled.`);
            checkLowStockAlerts(false);
            isSalesModifyMode = false;
            currentModifySaleVchId = null;
            const titleEl = document.getElementById("sales-voucher-screen-title");
            if (titleEl) titleEl.textContent = "Add Sales Voucher";
            showScreen("view-sales-list");
          } else {
            alert(`Failed to modify sale invoice: ${r.error}`);
          }
        } catch (e) {
          alert(`Error: ${e.message}`);
        }
      });
    }
    return;
  }

  // New Invoice: Backend generates sequential voucher number atomically inside database transaction
  const payload = {
    party_name: isDirectCash ? "CASH" : party,
    account_id: customerAccountId || undefined,
    customer_category: activeVoucherCustomerCategory || "Direct Customer",
    sale_type: vchSaleType.value,
    payment_method: "CASH",
    series: vchSeries.value || "Main",
    vch_date: vchDate.value,
    narration: vchNarration.value.trim(),
    items: items.map((it) => ({
      item_id: it.item_id || undefined,
      name: it.name,
      qty: it.qty,
      unit: it.unit,
      price: it.price,
      discount_percent: it.discount_percent || (cachedCategoryDiscounts[activeVoucherCustomerCategory] || 0.0),
      discount_amount: it.discount_amount || 0.0,
      line_total: it.amount
    }))
  };

  const onCommitSuccess = (savedData) => {
    lastCompletedVoucher = savedData.vch_no;
    lastCompletedVoucherData = savedData;
    saveSalesVoucherRecord({
      vchNo: savedData.vch_no,
      series: vchSeries.value || "Main",
      date: vchDate.value,
      saleType: vchSaleType.value,
      party: party,
      matCentre: vchMatCentre.value,
      narration: vchNarration.value.trim(),
      items: items,
      subtotal: subtotal,
      grandTotal: grandTotal,
      createdAt: new Date().toISOString()
    });

    checkLowStockAlerts(false);
    showNotification(`Sales Bill #${savedData.vch_no} saved and committed!`);

    // Automatic post-save transition to dedicated Print screen
    printSourceScreen = "view-sales-voucher";
    openFastBillingPrint(savedData.voucher_id || savedData.id, savedData, "view-sales-voucher");
  };

  const isTrad = (typeof activeBillingMode !== "undefined" && activeBillingMode === "traditional") || (typeof openTabs !== "undefined" && openTabs.has("traditional")) || (typeof activeLoginMode !== "undefined" && activeLoginMode === "traditional");

  if (window.backend && isTrad && typeof window.backend.traditional_saveSaleInvoice === "function") {
    window.backend.traditional_saveSaleInvoice(JSON.stringify(payload), (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r.success) {
          onCommitSuccess(r.data);
        } else {
          alert(`Failed to save sales invoice: ${r.error}`);
        }
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
    return;
  }

  if (window.backend && activeCompany) {
    window.backend.createSaleInvoice(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          onCommitSuccess(r.data);
        } else {
          alert(`Failed to save sales invoice: ${r.error}`);
        }
      } catch (e) {
        alert(`Error: ${e.message}`);
      }
    });
  } else {
    // Offline / mock fallback
    const mockVchNo = getNextVoucherNumber();
    const mockData = {
      id: "vch_" + Date.now(),
      voucher_id: "vch_" + Date.now(),
      vch_no: mockVchNo,
      party_name: party,
      account_id: customerAccountId,
      vch_date: vchDate.value,
      subtotal: subtotal,
      grand_total: parseFloat(grandTotal.replace(/,/g, "")),
      items: items
    };
    onCommitSuccess(mockData);
  }
}

function openModifySaleInvoice(vchId) {
  if (!activeCompany) return;
  const loadInvoice = (vch) => {
    if (!vch) {
      alert("Sales invoice not found.");
      return;
    }
    isSalesModifyMode = true;
    currentModifySaleVchId = vch.id || vchId;
    const modIn = document.getElementById("sales-modify-vch-id");
    if (modIn) modIn.value = currentModifySaleVchId;

    if (vchNumber) vchNumber.value = vch.vch_no || "";
    if (infoVchNo) infoVchNo.textContent = vch.vch_no || "";
    if (vchDate && vch.vch_date) vchDate.value = vch.vch_date;
    if (vchPartyInput) {
      vchPartyInput.value = vch.party_name || "CASH";
      if (vch.account_id) {
        vchPartyInput.dataset.accountId = vch.account_id;
      } else {
        delete vchPartyInput.dataset.accountId;
      }
    }
    if (vchSaleType && vch.sale_type) vchSaleType.value = vch.sale_type;
    if (vchNarration) vchNarration.value = vch.narration || "";

    const titleEl = document.getElementById("sales-voucher-screen-title");
    if (titleEl) titleEl.textContent = `Modify Sales Voucher: ${vch.vch_no}`;

    renderVoucherItemRows();
    const items = vch.items || [];
    for (let r = 1; r <= 11; r++) {
      const it = items[r - 1];
      const nameEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-item-input[data-row="${r}"]`) : null;
      const qtyEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-qty-input[data-row="${r}"]`) : null;
      const unitEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-unit-input[data-row="${r}"]`) : null;
      const priceEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-price-input[data-row="${r}"]`) : null;
      const amtEl = vchItemsTbody ? vchItemsTbody.querySelector(`.vch-amount-input[data-row="${r}"]`) : null;
      if (nameEl) {
        nameEl.value = it ? (it.item_name || it.name || "") : "";
        nameEl.dataset.itemId = it ? (it.item_id || it.id || "") : "";
      }
      if (qtyEl) qtyEl.value = it ? (it.qty || "") : "";
      if (unitEl) unitEl.value = it ? (it.unit || "Pcs.") : "Pcs.";
      if (priceEl) priceEl.value = it ? (it.price || "") : "";
      if (amtEl) amtEl.value = it ? (it.line_total || it.amount || "") : "";
    }
    updateVoucherPartyCategory();
    recalculateVoucherTotals();
    showScreen("view-sales-voucher");
  };

  if (window.backend && window.backend.getVoucherDetails) {
    window.backend.getVoucherDetails(activeCompany.id, vchId, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          loadInvoice(r.data);
          return;
        }
      } catch (e) {}
      if (window.backend.listVouchers) {
        window.backend.listVouchers(activeCompany.id, (resp2) => {
          try {
            const r2 = JSON.parse(resp2);
            if (r2.success && Array.isArray(r2.data)) {
              const found = r2.data.find(v => v.id === vchId || v.vch_no === vchId);
              loadInvoice(found);
            }
          } catch (e) {}
        });
      }
    });
  } else if (window.backend && window.backend.listVouchers) {
    window.backend.listVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const found = r.data.find(v => v.id === vchId || v.vch_no === vchId);
          loadInvoice(found);
        }
      } catch (e) {}
    });
  }
}

// =============================================================
// SALES BILLS REGISTER / LIST
// =============================================================
function renderSalesRegister() {
  salesRegisterTbody.innerHTML = "";
  
  if (window.backend && activeCompany) {
    window.backend.listVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data) && r.data.length > 0) {
          salesRegisterCount.textContent = `Total Bills: ${r.data.length}`;
          salesRegisterTbody.innerHTML = "";
          r.data.forEach((bill) => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            tr.title = "Double-click to modify invoice | Click Print for voucher output";
            tr.innerHTML = `
              <td style="font-weight: 800; color: #1e40af;">${escapeHtml(bill.vch_no)}</td>
              <td>${escapeHtml(bill.vch_date)}</td>
              <td style="font-weight: 700;">${escapeHtml(bill.party_name)}</td>
              <td>${escapeHtml(bill.sale_type)}</td>
              <td>${((bill.grand_total || 0) - (bill.subtotal || 0)).toFixed(2)}</td>
              <td style="font-weight: 800; color: #047857;">₹ ${(bill.grand_total || 0).toFixed(2)}</td>
              <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn-classic btn-sales-print-row" data-id="${bill.id || bill.vch_no}" style="padding: 2px 8px; font-size: 11px;" title="Print / Preview Invoice">🖨️ Print</button>
              </td>
            `;
            const printBtn = tr.querySelector(".btn-sales-print-row");
            if (printBtn) {
              printBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openFastBillingPrint(bill.id || bill.vch_no, bill, "view-sales-list", "sales_invoice");
              });
            }
            tr.addEventListener("dblclick", () => {
              openModifySaleInvoice(bill.id || bill.vch_no);
            });
            salesRegisterTbody.appendChild(tr);
          });
          return;
        }
      } catch (e) {}
      renderLocalSalesRegister();
    });
  } else {
    renderLocalSalesRegister();
  }
}

function renderLocalSalesRegister() {
  salesRegisterTbody.innerHTML = "";
  const bills = getSalesVouchers();

  if (bills.length === 0) {
    salesRegisterTbody.innerHTML = `
      <tr>
        <td colspan="7" style="text-align: center; color: #64748b; padding: 24px;">
          No sales bills recorded yet. Click "+ New Sales Bill" to create Bill #001.
        </td>
      </tr>
    `;
    salesRegisterCount.textContent = "Total Bills: 0";
    return;
  }

  salesRegisterCount.textContent = `Total Bills: ${bills.length}`;

  bills.forEach((bill) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 800; color: #1e40af;">${escapeHtml(bill.vchNo)}</td>
      <td>${escapeHtml(bill.date)}</td>
      <td style="font-weight: 700;">${escapeHtml(bill.party)}</td>
      <td>${escapeHtml(bill.saleType)}</td>
      <td>${(parseFloat(bill.grandTotal.replace(/,/g, '')) - bill.subtotal).toFixed(2)}</td>
      <td style="font-weight: 800; color: #047857;">₹ ${escapeHtml(bill.grandTotal)}</td>
      <td style="text-align: center; white-space: nowrap;">
        <button type="button" class="btn-classic btn-sales-print-row" style="padding: 2px 8px; font-size: 11px;" title="Print / Preview Invoice">🖨️ Print</button>
      </td>
    `;
    const printBtn = tr.querySelector(".btn-sales-print-row");
    if (printBtn) {
      printBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        openFastBillingPrint(bill.vchNo, bill, "view-sales-list", "sales_invoice");
      });
    }
    salesRegisterTbody.appendChild(tr);
  });
}

if (btnNewBillFromList) btnNewBillFromList.addEventListener("click", () => showScreen("view-sales-voucher"));
if (btnCloseSalesList) btnCloseSalesList.addEventListener("click", () => showScreen("view-dashboard"));
if (btnSalesListClose) btnSalesListClose.addEventListener("click", () => showScreen("view-dashboard"));

// =============================================================
// CONTROLLED ENHANCEMENT: LOW-STOCK ALERTS & CUSTOMER CATEGORIES
// =============================================================
function fetchCustomerCategoryDiscounts() {
  if (activeLoginMode === "traditional" || activeBillingMode === "traditional") return;
  if (!activeCompany || !window.backend || !window.backend.getCustomerCategoryDiscounts) return;
  window.backend.getCustomerCategoryDiscounts(activeCompany.id, (resp) => {
    try {
      const res = JSON.parse(resp);
      if (res.success && res.data) {
        cachedCategoryDiscounts = res.data;
        updatePosCustomerCategoryBadge();
        updateVoucherPartyCategory();
      }
    } catch (e) {
      console.warn("Error fetching customer category discounts:", e);
    }
  });
}

let currentNotifFilter = "all";
let currentNotifAlerts = [];

function updateHeaderNotificationsBadge(count) {
  const badge = document.getElementById("header-notif-badge");
  const btn = document.getElementById("btn-header-notifications");
  const modalBadge = document.getElementById("low-stock-modal-badge");

  // In Fast Billing cashier mode, cashier cannot view stock management or alerts
  const isCashier = (activeBillingMode === "FAST" && window.currentUserRole === "cashier");
  if (isCashier) {
    if (badge) badge.style.display = "none";
    if (btn) btn.style.display = "none";
    return;
  }

  if (btn) btn.style.display = "flex";
  if (modalBadge) modalBadge.textContent = count;

  if (badge) {
    badge.textContent = count;
    if (count > 0) {
      badge.style.display = "flex";
      badge.style.backgroundColor = "#dc2626";
    } else {
      badge.style.display = "none";
    }
  }
}

function checkLowStockAlerts(allowAutoPopup = true) {
  if (!activeCompany || !window.backend) return;
  if (activeLoginMode === "traditional" || activeBillingMode === "traditional") {
    updateHeaderNotificationsBadge(0);
    return;
  }
  if (activeBillingMode === "FAST" && window.currentUserRole === "cashier") {
    updateHeaderNotificationsBadge(0);
    return;
  }

  const fetchAlerts = (cb) => {
    if (window.backend.getLowStockNotificationsFiltered) {
      window.backend.getLowStockNotificationsFiltered(activeCompany.id, "all", cb);
    } else if (window.backend.getLowStockAlerts) {
      window.backend.getLowStockAlerts(activeCompany.id, cb);
    }
  };

  fetchAlerts((resp) => {
    try {
      const res = JSON.parse(resp);
      if (!res.success) return;
      const alerts = res.data || [];
      const count = alerts.length;

      updateHeaderNotificationsBadge(count);

      // Update Legacy / POS Badges if present
      const barBtn = document.getElementById("bar-low-stock-alert");
      const barCount = document.getElementById("bar-low-stock-count");
      if (barBtn && barCount) {
        barCount.textContent = count;
        barBtn.style.display = count > 0 ? "inline-flex" : "none";
      }

      if (count > 0 && allowAutoPopup && !sessionLowStockDismissed) {
        showLowStockAlertModal(alerts, "all");
      }
    } catch (e) {
      console.warn("Error checking low stock alerts:", e);
    }
  });
}

function renderNotificationRows(alertsList, filterQuery = "") {
  const tbody = document.getElementById("low-stock-modal-tbody");
  const summaryText = document.getElementById("notif-modal-summary-text");
  const modal = document.getElementById("modal-low-stock-alert");
  if (!tbody) return;

  tbody.innerHTML = "";
  const query = (filterQuery || "").trim().toUpperCase();

  const filtered = (alertsList || []).filter((a) => {
    if (!query) return true;
    const name = (a.product_name || a.name || "").toUpperCase();
    const code = (a.item_code || a.alias || "").toUpperCase();
    const barcode = (a.barcode || "").toUpperCase();
    const branch = (a.branch_name || "").toUpperCase();
    return name.includes(query) || code.includes(query) || barcode.includes(query) || branch.includes(query);
  });

  if (summaryText) {
    summaryText.textContent = `Showing ${filtered.length} of ${(alertsList || []).length} items (${currentNotifFilter.toUpperCase()})`;
  }

  if (filtered.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="10" style="text-align: center; padding: 24px; color: #64748b; font-size: 13px;">No notifications found for this criteria.</td>`;
    tbody.appendChild(tr);
    if (modal) modal.dataset.selectedItemId = "";
    return;
  }

  filtered.forEach((a, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.itemId = a.item_id;
    tr.className = "low-stock-table-row";
    if (idx === 0) {
      tr.classList.add("selected-row");
      if (modal) modal.dataset.selectedItemId = a.item_id;
    }

    const isCritical = (a.severity === "CRITICAL" || a.current_stock <= 0);
    const isResolved = (a.status === "RESOLVED");

    let badgeHtml = "";
    if (isResolved) {
      badgeHtml = `<span class="stock-badge-resolved">RESOLVED</span>`;
    } else if (isCritical) {
      badgeHtml = `<span class="stock-badge-critical">CRITICAL</span>`;
    } else {
      badgeHtml = `<span class="stock-badge-reorder">REORDER</span>`;
    }

    const stockColor = isResolved ? "#166534" : (isCritical ? "#dc2626" : "#b45309");
    const stockVal = Number(a.current_stock !== undefined ? a.current_stock : a.available_qty || 0).toFixed(2);
    const minVal = a.min_stock_level !== null && a.min_stock_level !== undefined ? Number(a.min_stock_level).toFixed(2) : "-";
    const reorderVal = a.reorder_level !== null && a.reorder_level !== undefined ? Number(a.reorder_level).toFixed(2) : (a.threshold ? Number(a.threshold).toFixed(2) : "-");
    const suggestedQty = a.suggested_reorder_qty !== null && a.suggested_reorder_qty !== undefined ? Number(a.suggested_reorder_qty).toFixed(2) : "0.00";
    const timeVal = a.created_at || a.last_evaluated_at || a.resolved_at || "-";

    tr.innerHTML = `
      <td style="padding: 8px 10px; font-weight: 700; color: #0f172a;">${escapeHtml(a.product_name || a.name || "")}</td>
      <td style="padding: 8px 10px; font-family: monospace; color: #475569;">${escapeHtml(a.item_code || a.alias || "-")}</td>
      <td style="padding: 8px 10px; font-family: monospace; color: #64748b;">${escapeHtml(a.barcode || "-")}</td>
      <td style="padding: 8px 10px; color: #334155;">${escapeHtml(a.branch_name || "Main Store")}</td>
      <td style="padding: 8px 10px; text-align: right; font-weight: 800; color: ${stockColor};">${stockVal} ${escapeHtml(a.unit || '')}</td>
      <td style="padding: 8px 10px; text-align: right; color: #475569;">${minVal}</td>
      <td style="padding: 8px 10px; text-align: right; font-weight: 600; color: #1e293b;">${reorderVal}</td>
      <td style="padding: 8px 10px; text-align: right; font-weight: 800; color: #1e40af;">+${suggestedQty}</td>
      <td style="padding: 8px 10px; text-align: center;">${badgeHtml}</td>
      <td style="padding: 8px 10px; text-align: right; font-size: 11px; color: #64748b;">${escapeHtml(timeVal)}</td>
    `;

    tr.addEventListener("click", () => {
      tbody.querySelectorAll("tr").forEach(r => r.classList.remove("selected-row"));
      tr.classList.add("selected-row");
      if (modal) modal.dataset.selectedItemId = a.item_id;
    });

    tbody.appendChild(tr);
  });
}

function showLowStockAlertModal(alertsList = null, filterType = "all") {
  const modal = document.getElementById("modal-low-stock-alert");
  if (!modal) return;

  currentNotifFilter = filterType;

  // Highlight active filter tab
  document.querySelectorAll(".notif-filter-btn").forEach((btn) => {
    btn.classList.toggle("notif-filter-active", btn.dataset.filter === filterType);
  });

  const searchInput = document.getElementById("notif-modal-search");
  if (searchInput) searchInput.value = "";

  const renderData = (data) => {
    currentNotifAlerts = data || [];
    renderNotificationRows(currentNotifAlerts, "");
    modal.classList.add("show");
    modal.style.display = "flex";
  };

  if (alertsList && filterType === "all") {
    renderData(alertsList);
  } else if (activeCompany && window.backend) {
    if (window.backend.getLowStockNotificationsFiltered) {
      window.backend.getLowStockNotificationsFiltered(activeCompany.id, filterType, (resp) => {
        try {
          const res = JSON.parse(resp);
          renderData(res.success ? res.data : []);
        } catch (e) {
          console.error("Error loading low stock notifications:", e);
        }
      });
    } else if (window.backend.getLowStockAlerts) {
      window.backend.getLowStockAlerts(activeCompany.id, (resp) => {
        try {
          const res = JSON.parse(resp);
          renderData(res.success ? res.data : []);
        } catch (e) {
          console.error(e);
        }
      });
    }
  } else {
    modal.classList.add("show");
    modal.style.display = "flex";
  }
}

function closeLowStockAlertModal(dismissForSession = false) {
  const modal = document.getElementById("modal-low-stock-alert");
  if (!modal) return;
  modal.classList.remove("show");
  modal.style.display = "none";
  if (dismissForSession) {
    sessionLowStockDismissed = true;
    if (activeCompany && window.backend && window.backend.dismissLowStockAlert) {
      window.backend.dismissLowStockAlert(activeCompany.id, "", () => {});
    }
  }
}

function initPosCustomerSelector() {
  const select = document.getElementById("pos-customer-select");
  if (!select) return;
  select.innerHTML = '<option value="" data-category="Direct Customer">Cash / Walk-In Customer</option>';

  const populateOptions = (accList) => {
    select.innerHTML = '<option value="" data-category="Direct Customer">Cash / Walk-In Customer</option>';
    accList.forEach((acc) => {
      const opt = document.createElement("option");
      opt.value = acc.id || acc.name;
      opt.dataset.category = acc.customer_category || acc.customerCategory || "Direct Customer";
      opt.dataset.name = acc.name;
      opt.textContent = `${acc.name} (${opt.dataset.category})`;
      select.appendChild(opt);
    });
  };

  if (activeCompany) {
    const key = `alpha_accounts_${activeCompany.code}`;
    let localAccounts = [];
    try {
      localAccounts = JSON.parse(localStorage.getItem(key) || "[]");
    } catch (e) {}

    const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
    if (isTrad && window.backend && typeof window.backend.traditional_listCustomers === "function") {
      window.backend.traditional_listCustomers("", true, (resp) => {
        try {
          const r = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (r && r.success && Array.isArray(r.data)) {
            populateOptions(r.data);
            return;
          }
        } catch (e) {}
        populateOptions(localAccounts);
      });
      return;
    }

    if (window.backend && window.backend.listAccounts) {
      window.backend.listAccounts(activeCompany.id, (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success && Array.isArray(r.data)) {
            cachedAccountsList = r.data;
            populateOptions(r.data.filter(a => {
              const grp = a.account_group || a.group || "";
              return !grp || grp === "Sundry Debtors" || grp.includes("Both") || a.classification === "Customer" || a.classification === "Both (Customer & Supplier)";
            }));
          } else {
            populateOptions(localAccounts);
          }
        } catch (e) {
          populateOptions(localAccounts);
        }
      });
    } else {
      populateOptions(localAccounts);
    }
  }

  select.onchange = handlePosCustomerChange;
  updatePosCustomerCategoryBadge();
}

function handlePosCustomerChange() {
  const select = document.getElementById("pos-customer-select");
  if (!select) return;
  const selOpt = select.options[select.selectedIndex];
  if (!selOpt || !selOpt.value) {
    activePosCustomerId = null;
    activePosCustomerName = "CASH";
    activePosCustomerCategory = "Direct Customer";
  } else {
    activePosCustomerId = selOpt.value;
    activePosCustomerName = selOpt.dataset.name || selOpt.textContent;
    activePosCustomerCategory = selOpt.dataset.category || "Direct Customer";
  }

  updatePosCustomerCategoryBadge();

  const catRate = cachedCategoryDiscounts[activePosCustomerCategory] !== undefined ? cachedCategoryDiscounts[activePosCustomerCategory] : (activePosCustomerCategory === "Commercial" ? 5.0 : (activePosCustomerCategory === "Sub-Commercial" ? 2.5 : 0.0));
  const dailyRate = (activeDailyDiscount && activeDailyDiscount.active && activeDailyDiscount.percent > 0) ? activeDailyDiscount.percent : 0.0;
  const effectiveRate = Math.max(catRate, dailyRate);

  posCart.forEach((item) => {
    if (!item.isManualDiscount) {
      item.discountPercent = effectiveRate;
    }
  });

  renderPosCart();
}

function updatePosCustomerCategoryBadge() {
  const badge = document.getElementById("pos-customer-category-badge");
  if (!badge) return;
  const cat = activePosCustomerCategory || "Direct Customer";
  const rate = cachedCategoryDiscounts[cat] !== undefined ? cachedCategoryDiscounts[cat] : (cat === "Commercial" ? 5.0 : (cat === "Sub-Commercial" ? 2.5 : 0.0));
  const cls = cat === "Commercial" ? "commercial" : (cat === "Sub-Commercial" ? "sub-commercial" : "direct");
  badge.textContent = `${cat === "Commercial" ? "Commercial" : (cat === "Sub-Commercial" ? "Sub-Comm" : "Direct")} (${rate}%)`;
  badge.className = `pos-category-badge ${cls}`;
}

// =============================================================
// FAST BILLING (POS) ENGINE
// =============================================================
function initFastBillingScreen() {
  if (posVchNo) {
    if (window.backend && activeCompany) {
      window.backend.getNextVoucherNumber(activeCompany.id, "POS", (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) posVchNo.textContent = r.data;
        } catch (e) {}
      });
    } else {
      posVchNo.textContent = getNextVoucherNumber();
    }
  }
  fetchCustomerCategoryDiscounts();
  initPosCustomerSelector();
  checkLowStockAlerts(false);
  initPosTextSizeControls();
  initDailyDiscountControls();
  initPosTenderListeners();
  renderPosCart();
  setTimeout(() => {
    if (posBarcodeInput) {
      posBarcodeInput.focus();
    }
  }, 100);
}

function renderPosCart() {
  if (!posCartTbody) return;
  posCartTbody.innerHTML = "";

  // Update item count badge in the toolbar below the table
  const tableCountEl = document.getElementById("pos-cart-table-count");
  if (tableCountEl) {
    const n = posCart.length;
    tableCountEl.textContent = `${n} item${n === 1 ? '' : 's'} in list`;
  }

  if (posCart.length === 0) {
    if (posEmptyCartMsg) posEmptyCartMsg.style.display = "block";
    updatePosTotals();
    return;
  }

  if (posEmptyCartMsg) posEmptyCartMsg.style.display = "none";

  posCart.forEach((item, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.index = idx;
    const isUnverified = (item.is_verified === 0 || item.price <= 0 || item.barcode === "8909263004690" || (item.name && item.name.includes("Unverified")));
    
    const qty = parseFloat(item.qty) || 0;
    const price = parseFloat(item.price) || 0;
    const discPct = item.discountPercent !== undefined ? parseFloat(item.discountPercent) : 0;
    const grossLine = Math.round(qty * price * 100) / 100;
    const discAmt = Math.round(grossLine * (discPct / 100) * 100) / 100;
    const taxableLine = Math.max(0, grossLine - discAmt);
    const taxAmt = Math.round(taxableLine * ((item.taxRate || 0) / 100) * 100) / 100;
    const lineTotal = taxableLine + taxAmt;

    tr.innerHTML = `
      <td class="col-pos-num">${idx + 1}</td>
      <td class="col-pos-barcode">
        <span class="pos-barcode-badge">${escapeHtml(item.barcode || "-")}</span>
      </td>
      <td class="col-pos-desc">
        <span class="pos-item-name">${escapeHtml(item.name)}</span>
        ${isUnverified ? '<br/><span class="cart-unverified-tag">[UNVERIFIED: ₹0 PRICE - CANNOT CHECKOUT]</span>' : ''}
      </td>
      <td class="col-pos-qty">
        <div class="pos-qty-control">
          <button type="button" class="pos-qty-btn btn-pos-qty-dec" data-index="${idx}" title="Decrease quantity">−</button>
          <input type="number" step="0.001" min="0.001" class="pos-cart-qty-input" data-index="${idx}" value="${item.qty}" />
          <button type="button" class="pos-qty-btn btn-pos-qty-inc" data-index="${idx}" title="Increase quantity">+</button>
        </div>
      </td>
      <td class="col-pos-unit">${escapeHtml(item.unit || "Pcs.")}</td>
      <td class="col-pos-price" style="${isUnverified ? 'color: #dc2626;' : ''}">₹ ${price.toFixed(2)}</td>
      <td class="col-pos-discount">
        <input type="number" step="0.1" min="0" max="100" class="pos-cart-disc-input" data-index="${idx}" value="${discPct}" title="Discount % (0 - 100)" />
      </td>
      <td class="col-pos-tax">${item.taxRate || 0}%</td>
      <td class="col-pos-total" style="color: ${isUnverified ? '#dc2626' : '#047857'};">₹ ${lineTotal.toFixed(2)}</td>
      <td class="col-pos-action">
        <button type="button" class="pos-cart-btn-del" data-index="${idx}" title="Remove Item">&times;</button>
      </td>
    `;

    // Row selection on click (preserves crisp column dividers)
    tr.addEventListener("click", (e) => {
      if (e.target.closest(".pos-qty-control") || e.target.closest(".pos-cart-btn-del") || e.target.closest(".pos-cart-disc-input")) {
        return;
      }
      posCartTbody.querySelectorAll("tr").forEach((r) => r.classList.remove("active-row", "pos-row-selected"));
      tr.classList.add("active-row", "pos-row-selected");
    });

    posCartTbody.appendChild(tr);
  });

  // Attach Quantity increment/decrement buttons
  posCartTbody.querySelectorAll(".btn-pos-qty-inc").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      posCart[idx].qty = Math.round((posCart[idx].qty + 1) * 1000) / 1000;
      renderPosCart();
      if (posBarcodeInput) posBarcodeInput.focus();
    });
  });

  posCartTbody.querySelectorAll(".btn-pos-qty-dec").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      if (posCart[idx].qty > 1) {
        posCart[idx].qty = Math.round((posCart[idx].qty - 1) * 1000) / 1000;
        renderPosCart();
      } else {
        if (confirm(`Remove "${posCart[idx].name}" from cart?`)) {
          posCart.splice(idx, 1);
          renderPosCart();
        }
      }
      if (posBarcodeInput) posBarcodeInput.focus();
    });
  });

  // Attach Quantity input change handlers
  posCartTbody.querySelectorAll(".pos-cart-qty-input").forEach((input) => {
    input.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      const val = parseFloat(e.target.value);
      if (!isNaN(val) && val > 0) {
        posCart[idx].qty = val;
        renderPosCart();
      } else {
        e.target.value = posCart[idx].qty;
      }
    });
  });

  // Attach Discount input change and live input handlers
  posCartTbody.querySelectorAll(".pos-cart-disc-input").forEach((input) => {
    input.addEventListener("change", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      let val = parseFloat(e.target.value);
      if (isNaN(val) || val < 0) val = 0;
      if (val > 100) val = 100;
      posCart[idx].discountPercent = val;
      renderPosCart();
    });
    input.addEventListener("input", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      let val = parseFloat(e.target.value);
      if (!isNaN(val) && val >= 0 && val <= 100) {
        posCart[idx].discountPercent = val;
        updatePosTotals();
      }
    });
  });

  // Attach Delete item handlers
  posCartTbody.querySelectorAll(".pos-cart-btn-del").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      const idx = parseInt(e.target.dataset.index, 10);
      posCart.splice(idx, 1);
      renderPosCart();
      if (posBarcodeInput) posBarcodeInput.focus();
    });
  });

  updatePosTotals();
}

// =============================================================
// POS CART TABLE TEXT SIZING CONTROLS (INCREMENTAL)
// =============================================================
const POS_MIN_FONT_SIZE = 11;
const POS_MAX_FONT_SIZE = 18;
const POS_DEFAULT_FONT_SIZE = 13;
const POS_FONT_SIZE_STORAGE_KEY = "alpha_pos_table_text_size";

function applyPosCartTextSize(size) {
  let numSize = parseInt(size, 10);
  if (isNaN(numSize)) {
    if (size === "small") numSize = 11;
    else if (size === "large") numSize = 16;
    else numSize = POS_DEFAULT_FONT_SIZE;
  }

  if (numSize < POS_MIN_FONT_SIZE) numSize = POS_MIN_FONT_SIZE;
  if (numSize > POS_MAX_FONT_SIZE) numSize = POS_MAX_FONT_SIZE;

  const container = document.getElementById("pos-cart-container");
  if (container) {
    container.style.setProperty("--pos-table-font-size", `${numSize}px`);
    // Backward compatibility classes
    container.classList.remove("pos-text-size-small", "pos-text-size-normal", "pos-text-size-large");
    if (numSize <= 11) container.classList.add("pos-text-size-small");
    else if (numSize >= 15) container.classList.add("pos-text-size-large");
    else container.classList.add("pos-text-size-normal");
  }

  const displayEl = document.getElementById("pos-font-size-val");
  if (displayEl) {
    displayEl.textContent = `${numSize} px`;
  }

  const decBtn = document.getElementById("btn-pos-font-dec");
  if (decBtn) {
    decBtn.disabled = (numSize <= POS_MIN_FONT_SIZE);
  }

  const incBtn = document.getElementById("btn-pos-font-inc");
  if (incBtn) {
    incBtn.disabled = (numSize >= POS_MAX_FONT_SIZE);
  }

  try {
    localStorage.setItem(POS_FONT_SIZE_STORAGE_KEY, numSize.toString());
  } catch (e) {
    console.warn("Could not persist POS table text size:", e);
  }
}

function getPosCartTextSize() {
  try {
    const saved = localStorage.getItem(POS_FONT_SIZE_STORAGE_KEY);
    if (saved) {
      if (saved === "small") return 11;
      if (saved === "large") return 16;
      if (saved === "normal") return 13;
      const parsed = parseInt(saved, 10);
      if (!isNaN(parsed) && parsed >= POS_MIN_FONT_SIZE && parsed <= POS_MAX_FONT_SIZE) {
        return parsed;
      }
    }
  } catch (e) {}
  return POS_DEFAULT_FONT_SIZE;
}

function stepPosCartTextSize(delta) {
  const current = getPosCartTextSize();
  const next = Math.max(POS_MIN_FONT_SIZE, Math.min(POS_MAX_FONT_SIZE, current + delta));
  applyPosCartTextSize(next);
}

function initPosTextSizeControls() {
  const decBtn = document.getElementById("btn-pos-font-dec");
  const incBtn = document.getElementById("btn-pos-font-inc");

  if (decBtn && !decBtn.dataset.bound) {
    decBtn.dataset.bound = "true";
    decBtn.addEventListener("click", () => stepPosCartTextSize(-1));
  }

  if (incBtn && !incBtn.dataset.bound) {
    incBtn.dataset.bound = "true";
    incBtn.addEventListener("click", () => stepPosCartTextSize(1));
  }

  // Apply persisted or default size
  applyPosCartTextSize(getPosCartTextSize());
}

let posFeedbackTimer = null;
function showPosFeedback(message, type = "info") {
  if (!posScanFeedback) return;
  posScanFeedback.textContent = message;
  posScanFeedback.className = `pos-scan-feedback ${type}`;
  posScanFeedback.style.display = "block";
  if (posFeedbackTimer) clearTimeout(posFeedbackTimer);
  posFeedbackTimer = setTimeout(() => {
    if (posScanFeedback) posScanFeedback.style.display = "none";
  }, 3500);
}

// =============================================================
// DAILY DISCOUNT ARCHITECTURE & CONFIGURATION
// =============================================================
let activeDailyDiscount = {
  active: false,
  percent: 0.0,
  date: null
};

function getTodayDateStr() {
  const now = new Date();
  const yyyy = now.getFullYear();
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const dd = String(now.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function loadDailyDiscountConfig(callback) {
  const todayStr = getTodayDateStr();
  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  const branchId = (activeCompany ? activeCompany.branchId : null) || "";

  if (window.backend && window.backend.getDailyDiscount) {
    window.backend.getDailyDiscount(compId, branchId, todayStr, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data && res.data.is_active && res.data.business_date === todayStr) {
          activeDailyDiscount = {
            active: true,
            percent: parseFloat(res.data.discount_percent) || 0.0,
            date: todayStr
          };
        } else {
          activeDailyDiscount = {
            active: false,
            percent: 0.0,
            date: todayStr
          };
        }
      } catch (e) {
        activeDailyDiscount = { active: false, percent: 0.0, date: todayStr };
      }
      updateDailyDiscountUI();
      if (callback) callback(activeDailyDiscount);
    });
  } else {
    // Local fallback with automatic expiration on date mismatch
    try {
      const saved = JSON.parse(localStorage.getItem(`alpha_daily_discount_${compId}`) || "null");
      if (saved && saved.is_active && saved.business_date === todayStr) {
        activeDailyDiscount = {
          active: true,
          percent: parseFloat(saved.discount_percent) || 0.0,
          date: todayStr
        };
      } else {
        activeDailyDiscount = { active: false, percent: 0.0, date: todayStr };
      }
    } catch (e) {
      activeDailyDiscount = { active: false, percent: 0.0, date: todayStr };
    }
    updateDailyDiscountUI();
    if (callback) callback(activeDailyDiscount);
  }
}

function updateDailyDiscountUI() {
  const toggleEl = document.getElementById("pos-daily-discount-toggle");
  const badgeEl = document.getElementById("pos-daily-discount-badge");

  if (toggleEl) {
    toggleEl.checked = activeDailyDiscount.active;
  }

  if (badgeEl) {
    if (activeDailyDiscount.active && activeDailyDiscount.percent > 0) {
      badgeEl.textContent = `ON (${activeDailyDiscount.percent.toFixed(2)}%)`;
      badgeEl.className = "pos-discount-badge on";
      badgeEl.title = `Active: ${activeDailyDiscount.percent.toFixed(2)}% applied to new bills today. Click to edit percentage or disable.`;
    } else {
      badgeEl.textContent = "OFF";
      badgeEl.className = "pos-discount-badge off";
      badgeEl.title = "Click toggle to enable daily discount for today's bills.";
    }
  }
}

function saveDailyDiscountConfig(percent, isActive, callback) {
  const todayStr = getTodayDateStr();
  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  const branchId = (activeCompany ? activeCompany.branchId : null) || "";

  if (window.backend && window.backend.setDailyDiscount) {
    window.backend.setDailyDiscount(compId, branchId, todayStr, percent, isActive, "Admin", (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success) {
          activeDailyDiscount = {
            active: isActive,
            percent: percent,
            date: todayStr
          };
          updateDailyDiscountUI();
          if (callback) callback(true);
        } else {
          alert(`Failed to save daily discount: ${res.error}`);
          if (callback) callback(false);
        }
      } catch (e) {
        if (callback) callback(false);
      }
    });
  } else {
    // Local fallback
    const record = {
      company_id: compId,
      branch_id: branchId,
      business_date: todayStr,
      discount_percent: percent,
      is_active: isActive ? 1 : 0,
      enabled_by: "Admin"
    };
    localStorage.setItem(`alpha_daily_discount_${compId}`, JSON.stringify(record));
    activeDailyDiscount = {
      active: isActive,
      percent: percent,
      date: todayStr
    };
    updateDailyDiscountUI();
    if (callback) callback(true);
  }
}

function handleDailyDiscountToggleChange(e) {
  const isChecked = e.target.checked;
  const todayStr = getTodayDateStr();

  if (isChecked) {
    // Prompt operator to enter discount percentage
    const currentVal = activeDailyDiscount.percent > 0 ? activeDailyDiscount.percent : 5;
    const input = prompt(`Enter default discount percentage to apply to all bills today (${todayStr}):`, currentVal);
    if (input === null) {
      e.target.checked = false;
      return;
    }

    const pct = parseFloat(input);
    if (isNaN(pct) || pct <= 0 || pct > 100) {
      alert("Invalid discount percentage. Please enter a percentage between 0.01% and 100%.");
      e.target.checked = false;
      return;
    }

    if (confirm(`Confirm activating ${pct}% discount on all subsequent bills for today (${todayStr})?`)) {
      saveDailyDiscountConfig(pct, true, (ok) => {
        if (ok) {
          showNotification(`Daily discount of ${pct.toFixed(2)}% enabled for today.`);
          if (posCart.length > 0) {
            const hasZeroDisc = posCart.some(it => (it.discountPercent || 0) === 0);
            if (hasZeroDisc && confirm(`Apply this ${pct}% daily discount to the current active cart as well?`)) {
              posCart.forEach(it => {
                if ((it.discountPercent || 0) === 0) {
                  it.discountPercent = pct;
                }
              });
              renderPosCart();
            }
          }
        } else {
          e.target.checked = false;
        }
      });
    } else {
      e.target.checked = false;
    }
  } else {
    // Disabling
    if (confirm("Are you sure you want to disable the daily discount?\n\nSubsequent new bills will not receive automatic discounts. (Existing bills and current cart items will preserve their discounts).")) {
      saveDailyDiscountConfig(0.0, false, (ok) => {
        if (ok) {
          showNotification("Daily discount disabled for subsequent new bills.");
        } else {
          e.target.checked = true;
        }
      });
    } else {
      e.target.checked = true;
    }
  }
}

function initDailyDiscountControls() {
  const toggleEl = document.getElementById("pos-daily-discount-toggle");
  const badgeEl = document.getElementById("pos-daily-discount-badge");

  if (toggleEl && !toggleEl.dataset.discBound) {
    toggleEl.dataset.discBound = "true";
    toggleEl.addEventListener("change", handleDailyDiscountToggleChange);
  }

  if (badgeEl && !badgeEl.dataset.discBound) {
    badgeEl.dataset.discBound = "true";
    badgeEl.addEventListener("click", () => {
      if (activeDailyDiscount.active) {
        const action = prompt(`Active Daily Discount: ${activeDailyDiscount.percent}%\n\nEnter new discount percentage, or type 0 to turn off:`, activeDailyDiscount.percent);
        if (action === null) return;
        const val = parseFloat(action);
        if (isNaN(val) || val < 0 || val > 100) {
          alert("Invalid percentage entered.");
          return;
        }
        if (val === 0) {
          saveDailyDiscountConfig(0, false, () => {
            showNotification("Daily discount deactivated.");
          });
        } else {
          saveDailyDiscountConfig(val, true, () => {
            showNotification(`Updated daily discount to ${val.toFixed(2)}%.`);
          });
        }
      } else {
        if (toggleEl) {
          toggleEl.click();
        }
      }
    });
  }

  loadDailyDiscountConfig();
}

function initPosTenderListeners() {
  if (posTenderReceived && !posTenderReceived.dataset.tenderBound) {
    posTenderReceived.dataset.tenderBound = "true";
    const events = ["input", "keyup", "change", "blur"];
    events.forEach((ev) => {
      posTenderReceived.addEventListener(ev, () => {
        if (parseFloat(posTenderReceived.value) < 0) {
          posTenderReceived.value = "0";
        }
        updatePosTenderCalc();
      });
    });
    posTenderReceived.addEventListener("paste", () => {
      setTimeout(() => {
        if (parseFloat(posTenderReceived.value) < 0) {
          posTenderReceived.value = "0";
        }
        updatePosTenderCalc();
      }, 10);
    });
  }

  if (chipTenderExact && !chipTenderExact.dataset.chipBound) {
    chipTenderExact.dataset.chipBound = "true";
    chipTenderExact.addEventListener("click", () => {
      if (posPayableAmount && posTenderReceived) {
        const payable = parseFloat(posPayableAmount.textContent.replace(/[^\d.]/g, "")) || 0;
        posTenderReceived.value = payable.toFixed(2);
        updatePosTenderCalc();
      }
    });
  }

  document.querySelectorAll(".btn-tender-chip[data-amt]").forEach((chip) => {
    if (!chip.dataset.chipBound) {
      chip.dataset.chipBound = "true";
      chip.addEventListener("click", () => {
        const val = parseFloat(chip.dataset.amt);
        if (!isNaN(val) && posTenderReceived) {
          posTenderReceived.value = val.toFixed(2);
          updatePosTenderCalc();
        }
      });
    }
  });
}

function updatePosTenderCalc() {
  if (!posPayableAmount || !posTenderReceived) return { payable: 0, tendered: 0, change: 0, balance: 0 };

  const rawPayableText = posPayableAmount.textContent.replace(/[^\d.]/g, "");
  const payable = parseFloat(rawPayableText) || 0;

  let rawVal = posTenderReceived.value;
  if (rawVal === undefined || rawVal === null || rawVal.trim() === "") {
    rawVal = "0";
  }
  let tendered = parseFloat(rawVal);
  if (isNaN(tendered) || tendered < 0) {
    tendered = 0;
  }

  // Decimal-safe calculations in paise (cents)
  const dPayable = Math.round(payable * 100);
  const dTendered = Math.round(tendered * 100);

  let change = 0;
  let balance = 0;

  if (dTendered > dPayable) {
    change = (dTendered - dPayable) / 100;
    balance = 0;
  } else if (dTendered === dPayable) {
    change = 0;
    balance = 0;
  } else {
    change = 0;
    balance = (dPayable - dTendered) / 100;
  }

  if (posChangeDueVal) {
    posChangeDueVal.textContent = `₹ ${change.toFixed(2)}`;
    posChangeDueVal.style.color = change > 0 ? "#047857" : "#334155";
  }

  const balanceDueEl = document.getElementById("pos-balance-due-val");
  if (balanceDueEl) {
    balanceDueEl.textContent = `₹ ${balance.toFixed(2)}`;
    if (balance > 0) {
      balanceDueEl.style.color = "#dc2626";
      balanceDueEl.classList.add("unpaid");
      balanceDueEl.classList.remove("paid");
    } else {
      balanceDueEl.style.color = "#047857";
      balanceDueEl.classList.add("paid");
      balanceDueEl.classList.remove("unpaid");
    }
  }

  return { payable, tendered, change, balance };
}

function updatePosTotals() {
  let grossSubtotal = 0;
  let totalDiscount = 0;
  let taxableSubtotal = 0;
  let taxTotal = 0;
  let totalQty = 0;

  posCart.forEach((it) => {
    const p = parseFloat(it.price) || 0;
    const q = parseFloat(it.qty) || 0;
    const rate = parseFloat(it.taxRate) || 0;
    const discPct = it.discountPercent !== undefined ? parseFloat(it.discountPercent) : 0;

    const grossLine = Math.round(p * q * 100) / 100;
    const discAmt = Math.round(grossLine * (discPct / 100) * 100) / 100;
    const taxableLine = Math.max(0, grossLine - discAmt);
    const taxAmt = Math.round(taxableLine * (rate / 100) * 100) / 100;
    const lineTotal = taxableLine + taxAmt;

    it.gross_amount = grossLine;
    it.discount_amount = discAmt;
    it.taxable_amount = taxableLine;
    it.tax_amount = taxAmt;
    it.line_total = lineTotal;

    grossSubtotal += grossLine;
    totalDiscount += discAmt;
    taxableSubtotal += taxableLine;
    taxTotal += taxAmt;
    totalQty += q;
  });

  const rawTotal = taxableSubtotal + taxTotal;
  const rounded = Math.round(rawTotal);
  const roundDiff = rounded - rawTotal;

  if (posItemCount) posItemCount.textContent = `${posCart.length} items (${totalQty.toFixed(2)} qty)`;
  if (posGrossSubtotal) posGrossSubtotal.textContent = `₹ ${grossSubtotal.toFixed(2)}`;
  if (posDiscountTotal) posDiscountTotal.textContent = `- ₹ ${totalDiscount.toFixed(2)}`;
  if (posSubtotal) posSubtotal.textContent = `₹ ${taxableSubtotal.toFixed(2)}`;
  if (posTaxTotal) posTaxTotal.textContent = `₹ ${taxTotal.toFixed(2)}`;
  if (posRoundOff) posRoundOff.textContent = (roundDiff >= 0 ? "+" : "") + roundDiff.toFixed(2);
  if (posPayableAmount) posPayableAmount.textContent = `₹ ${rounded.toFixed(2)}`;

  updatePosTenderCalc();
}

// POS Barcode Scanner Handler
function handleBarcodeScan(barcodeStr, isSimulated = false) {
  const code = (barcodeStr || "").trim();
  if (!code) return;

  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";

  const lookupFn = (window.backend && window.backend.getCashierProductByBarcode) 
    ? window.backend.getCashierProductByBarcode 
    : (window.backend && window.backend.findByBarcode ? window.backend.findByBarcode : null);

  if (lookupFn) {
    lookupFn(compId, code, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          addItemToPosCart(res.data);
          const scanType = isSimulated ? "Simulated scan" : "Scan received";
          const priceStr = parseFloat(res.data.sales_price || 0).toFixed(2);
          showPosFeedback(`${isSimulated ? 'Simulated: ' : 'Scanned: '}${res.data.name}`, "success");
          appendMobileScannerLog(`${scanType}: ${code} -> Added ${res.data.name} (₹${priceStr})`);
          if (res.data.is_verified === 0 || code === "8909263004690" || parseFloat(res.data.sales_price || 0) <= 0) {
            showMedicalVerificationModal(res.data);
          }
        } else {
          showPosFeedback(`Barcode "${code}" not found. Press F1 to search product.`, "error");
          showNotification(`Barcode "${code}" not registered.`);
          appendMobileScannerLog(`Unknown barcode: ${code}`);
        }
      } catch (e) {
        searchLocalItemsForBarcode(code, isSimulated);
      }
    });
  } else {
    searchLocalItemsForBarcode(code, isSimulated);
  }
}

function searchLocalItemsForBarcode(code, isSimulated = false) {
  const codeUpper = code.toUpperCase();
  let savedItems = [];
  if (activeCompany) {
    savedItems = JSON.parse(localStorage.getItem(`alpha_items_${activeCompany.code}`) || "[]");
  }
  const matched = savedItems.find(
    (it) => (it.alias && it.alias.toUpperCase() === codeUpper) || (it.name && it.name.toUpperCase() === codeUpper)
  );

  if (matched) {
    const isUnverified = (matched.is_verified === 0 || code === "8909263004690" || parseFloat(matched.salesPrice || 0) <= 0);
    const itemData = {
      id: matched.name,
      name: matched.name,
      alias: matched.alias || code,
      sales_price: parseFloat(matched.salesPrice) || 0.0,
      unit: matched.unit || "Pcs.",
      tax_category: matched.taxCategory || "GST 18%",
      is_verified: isUnverified ? 0 : 1,
      matched_barcode: code
    };
    addItemToPosCart(itemData);
    appendMobileScannerLog(`${isSimulated ? 'Simulated scan' : 'Scan received'}: ${code} -> Added ${itemData.name} (₹${itemData.sales_price.toFixed(2)})`);
    if (isUnverified) {
      showMedicalVerificationModal(itemData);
    }
  } else {
    showNotification(`Item "${code}" not registered. Press F1 to search.`);
    appendMobileScannerLog(`Unknown barcode: ${code}`);
  }
}

function addItemToPosCart(itemData) {
  const isUnverified = (itemData.is_verified === 0 || parseFloat(itemData.sales_price || itemData.salesPrice || 0) <= 0 || (itemData.matched_barcode === "8909263004690") || (itemData.barcode === "8909263004690") || (itemData.name && itemData.name.includes("Unverified")));
  const existingIdx = posCart.findIndex(
    (it) => (it.id && it.id === itemData.id) || (it.name.toUpperCase() === itemData.name.toUpperCase())
  );

  let taxRate = 18.0;
  const taxCat = itemData.tax_category || itemData.taxCategory || "";
  if (isUnverified) {
    taxRate = 0.0;
  } else if (taxCat.includes("28%")) {
    taxRate = 28.0;
  } else if (taxCat.includes("12%")) {
    taxRate = 12.0;
  } else if (taxCat.includes("5%")) {
    taxRate = 5.0;
  } else if (taxCat.includes("0%") || taxCat.includes("Exempt")) {
    taxRate = 0.0;
  }

  if (existingIdx !== -1) {
    posCart[existingIdx].qty += 1;
    showNotification(`Added +1 to ${itemData.name} (Qty: ${posCart[existingIdx].qty})`);
  } else {
    const catRate = cachedCategoryDiscounts[activePosCustomerCategory] !== undefined ? cachedCategoryDiscounts[activePosCustomerCategory] : (activePosCustomerCategory === "Commercial" ? 5.0 : (activePosCustomerCategory === "Sub-Commercial" ? 2.5 : 0.0));
    const dailyRate = (activeDailyDiscount && activeDailyDiscount.active && activeDailyDiscount.percent > 0)
      ? activeDailyDiscount.percent
      : 0.0;
    const defaultDisc = Math.max(catRate, dailyRate);
    posCart.push({
      id: itemData.id || itemData.name,
      name: itemData.name,
      barcode: itemData.matched_barcode || itemData.barcode || itemData.alias || "",
      qty: 1.0,
      unit: itemData.unit || "Pcs.",
      price: parseFloat(itemData.sales_price || itemData.salesPrice) || 0.0,
      taxRate: taxRate,
      discountPercent: defaultDisc,
      is_verified: isUnverified ? 0 : 1
    });
    showNotification(`Added ${itemData.name} to cart.`);
  }

  renderPosCart();
  if (posBarcodeInput) {
    posBarcodeInput.value = "";
    posBarcodeInput.focus();
  }
}

// Quick Payment & Checkout
function triggerPosCheckout(method) {
  if (posCart.length === 0) {
    alert("Cannot checkout: Cart is empty. Please scan or add items first.");
    if (posBarcodeInput) posBarcodeInput.focus();
    return;
  }

  // Safety protection: block accidental checkout of unconfigured / demo medical items
  const unverifiedItems = posCart.filter((it) => it.price <= 0 || it.is_verified === 0 || it.barcode === "8909263004690" || (it.name && it.name.includes("Unverified")));
  if (unverifiedItems.length > 0) {
    const names = unverifiedItems.map((it) => it.name).join(", ");
    alert(`CHECKOUT BLOCKED\n\nCannot proceed to payment. The cart contains items with unconfigured pricing or pending verification:\n• ${names}\n\nCommercial sale is strictly prohibited until product packaging is verified and valid price/tax is configured in Item Master.`);
    showPosFeedback("Checkout blocked: Unverified item with ₹0.00 price in cart", "error");
    return;
  }

  const tenderCalc = updatePosTenderCalc();
  const payable = tenderCalc ? tenderCalc.payable : parseFloat(posPayableAmount.textContent.replace(/[^\d.]/g, "")) || 0;
  let tendered = tenderCalc ? tenderCalc.tendered : 0;

  if (method === "CASH") {
    // If cashier already entered Amount Received in posTenderReceived
    if (posTenderReceived && posTenderReceived.value.trim() !== "") {
      if (tendered < payable) {
        const bal = payable - tendered;
        alert(`PAYMENT VALIDATION FAILED\n\nAmount Received (₹ ${tendered.toFixed(2)}) is less than Payable Amount (₹ ${payable.toFixed(2)}).\n\nOutstanding Balance Due: ₹ ${bal.toFixed(2)}.\n\nPlease collect the remaining balance before completing cash sale.`);
        posTenderReceived.focus();
        posTenderReceived.select();
        return;
      }
      // Valid cash payment
      const change = Math.max(0, tendered - payable);
      finalizePosSale("CASH", tendered, change);
      return;
    }

    // Otherwise open Cash modal
    modalCashDueVal.textContent = `₹ ${payable.toFixed(2)}`;
    posCashTendered.value = payable.toFixed(2);
    modalCashChangeVal.textContent = "₹ 0.00";
    modalPosCash.classList.add("show");
    setTimeout(() => {
      posCashTendered.focus();
      posCashTendered.select();
    }, 50);
  } else if (method === "UPI") {
    if (confirm(`Confirm UPI payment received of ₹ ${payable.toFixed(2)}?`)) {
      finalizePosSale("UPI", payable, 0);
    }
  } else if (method === "CARD") {
    if (confirm(`Confirm Card transaction of ₹ ${payable.toFixed(2)} on POS terminal?`)) {
      finalizePosSale("CARD", payable, 0);
    }
  } else {
    finalizePosSale("SPLIT", payable, 0);
  }
}

function finalizePosSale(method, amountPaid, changeDue) {
  if (posCart.length === 0) return;
  if (isSavingPosSale) {
    showNotification("Sale is already being processed. Please wait...");
    return;
  }
  isSavingPosSale = true;
  if (btnPosCheckoutPrint) btnPosCheckoutPrint.disabled = true;
  if (btnPosBarCheckout) btnPosBarCheckout.disabled = true;

  const vchNum = posVchNo.textContent.trim() || getNextVoucherNumber();
  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}-${now.getFullYear()}`;

  const itemsPayload = posCart.map((it, idx) => {
    const q = parseFloat(it.qty) || 0;
    const p = parseFloat(it.price) || 0;
    const discPct = it.discountPercent !== undefined ? parseFloat(it.discountPercent) : 0;
    const rate = parseFloat(it.taxRate) || 0;

    const gross = Math.round(q * p * 100) / 100;
    const discAmt = Math.round(gross * (discPct / 100) * 100) / 100;
    const taxable = Math.max(0, gross - discAmt);
    const taxAmt = Math.round(taxable * (rate / 100) * 100) / 100;
    const lineTotal = taxable + taxAmt;

    return {
      id: it.id,
      sn: idx + 1,
      name: it.name,
      qty: q,
      unit: it.unit,
      price: p,
      discount_percent: discPct,
      discount_amount: discAmt,
      taxable_amount: taxable,
      tax_rate: rate,
      tax_amount: taxAmt,
      line_total: lineTotal
    };
  });

  const payload = {
    party_name: activePosCustomerName || "CASH",
    account_id: activePosCustomerId || undefined,
    customer_category: activePosCustomerCategory || "Direct Customer",
    sale_type: "L/GST-18%",
    payment_method: method,
    items: itemsPayload,
    vch_date: dateStr,
    narration: `POS Checkout (${method}) - ${activePosCustomerCategory || "Direct Customer"}`
  };

  const calculatedTotals = {
    items: itemsPayload,
    vch_no: vchNum,
    vch_date: dateStr,
    party_name: activePosCustomerName || "CASH",
    payment_method: method,
    gross_subtotal: parseFloat(posGrossSubtotal ? posGrossSubtotal.textContent.replace(/[^\d.]/g, "") : 0) || 0,
    discount_total: parseFloat(posDiscountTotal ? posDiscountTotal.textContent.replace(/[^\d.]/g, "") : 0) || 0,
    subtotal: parseFloat(posSubtotal ? posSubtotal.textContent.replace(/[^\d.]/g, "") : 0) || 0,
    cgst_amount: parseFloat(posTaxTotal ? posTaxTotal.textContent.replace(/[^\d.]/g, "") : 0) / 2 || 0,
    sgst_amount: parseFloat(posTaxTotal ? posTaxTotal.textContent.replace(/[^\d.]/g, "") : 0) / 2 || 0,
    round_off: parseFloat(posRoundOff ? posRoundOff.textContent.replace(/[^\d.-]/g, "") : 0) || 0,
    grand_total: parseFloat(posPayableAmount ? posPayableAmount.textContent.replace(/[^\d.]/g, "") : 0) || 0,
    amount_paid: amountPaid,
    change_due: changeDue
  };

  if (window.backend && activeCompany) {
    window.backend.createSaleInvoice(activeCompany.id, JSON.stringify(payload), (resp) => {
      isSavingPosSale = false;
      if (btnPosCheckoutPrint) btnPosCheckoutPrint.disabled = false;
      if (btnPosBarCheckout) btnPosBarCheckout.disabled = false;

      try {
        const res = JSON.parse(resp);
        if (res.success) {
          lastCompletedVoucher = res.data.vch_no;
          lastCompletedVoucherData = { ...calculatedTotals, ...res.data };
          showNotification(`Sale #${res.data.vch_no} completed successfully!`);
          checkLowStockAlerts(false);

          posCart = [];
          if (posTenderReceived) posTenderReceived.value = "";
          renderPosCart();

          // AUTOMATIC POST-SAVE PRINT SCREEN NAVIGATION:
          // Immediately navigate to dedicated Print screen (do not return to blank billing screen)
          openFastBillingPrint(res.data.voucher_id || res.data.id, lastCompletedVoucherData);
        } else {
          alert(`Checkout failed: ${res.error}`);
        }
      } catch (e) {
        alert(`Checkout error: ${e}`);
      }
    });
  } else {
    // Local fallback
    isSavingPosSale = false;
    if (btnPosCheckoutPrint) btnPosCheckoutPrint.disabled = false;
    if (btnPosBarCheckout) btnPosBarCheckout.disabled = false;

    const voucherRecord = {
      ...calculatedTotals,
      id: vchNum,
      vchNo: vchNum,
      series: "POS",
      createdAt: new Date().toISOString()
    };
    saveSalesVoucherRecord(voucherRecord);
    lastCompletedVoucherData = voucherRecord;
    lastCompletedVoucher = vchNum;
    showNotification(`Sale #${vchNum} completed successfully!`);
    posCart = [];
    if (posTenderReceived) posTenderReceived.value = "";
    renderPosCart();
    openFastBillingPrint(vchNum, voucherRecord);
  }
}

// Receipt Modal Handler
function showReceiptModal(vchId) {
  if (window.backend && activeCompany) {
    window.backend.getThermalReceipt(activeCompany.id, vchId, 80, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          receiptPreviewText.textContent = r.data;
          modalReceiptPreview.classList.add("show");
        }
      } catch (e) {}
    });
  }
}

// Backup & Restore Dialog
function openBackupModal() {
  modalBackup.classList.add("show");
  refreshBackupList();
}

function refreshBackupList() {
  if (!backupListTbody) return;
  backupListTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: #94a3b8;">Loading backups...</td></tr>`;

  if (window.backend) {
    window.backend.listBackups((resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          if (r.data.length === 0) {
            backupListTbody.innerHTML = `<tr><td colspan="4" style="text-align: center; color: #94a3b8;">No backups found yet.</td></tr>`;
            return;
          }
          backupListTbody.innerHTML = "";
          r.data.forEach((b) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="font-weight: 700;">${escapeHtml(b.filename)}</td>
              <td>${b.size_kb} KB</td>
              <td>${escapeHtml(b.created_at)}</td>
              <td>
                <button type="button" class="btn-action restore-backup-btn" data-path="${escapeHtml(b.filepath)}">Restore</button>
              </td>
            `;
            backupListTbody.appendChild(tr);
          });

          backupListTbody.querySelectorAll(".restore-backup-btn").forEach((btn) => {
            btn.addEventListener("click", (e) => {
              const path = e.target.dataset.path;
              if (confirm(`Are you sure you want to restore database from:\n${path}?\nA safety snapshot will be created before restoring.`)) {
                window.backend.restoreBackup(path, (resJson) => {
                  const res = JSON.parse(resJson);
                  if (res.success) {
                    alert(res.message);
                    location.reload();
                  } else {
                    alert(`Restore failed: ${res.message}`);
                  }
                });
              }
            });
          });
        }
      } catch (e) {}
    });
  }
}

// Reports Dialog
function openReportsModal() {
  modalReports.classList.add("show");
  loadReportData("daily");
}

function loadReportData(tabType) {
  if (!reportContentView || !activeCompany) return;
  reportContentView.innerHTML = `<div style="padding: 20px; text-align: center; color: #64748b;">Loading report data...</div>`;

  if (window.backend) {
    const reportKey = tabType === "daily" ? "daily_sales" : tabType === "gst" ? "gst_summary" : tabType === "profit" ? "gross_profit" : "payment_summary";
    window.backend.getReport(activeCompany.id, reportKey, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          renderReportContent(tabType, r.data);
        }
      } catch (e) {}
    });
  }
}

function renderReportContent(tabType, data) {
  if (tabType === "daily") {
    if (!data || data.length === 0) {
      reportContentView.innerHTML = `<div style="padding: 20px; text-align: center; color: #64748b;">No sales records found.</div>`;
      return;
    }
    let html = `<table class="report-table"><thead><tr><th>Date</th><th>Bills</th><th>Taxable (₹)</th><th>Tax (₹)</th><th>Total Revenue (₹)</th></tr></thead><tbody>`;
    data.forEach((row) => {
      html += `<tr><td>${escapeHtml(row.date)}</td><td>${row.total_bills}</td><td>₹ ${row.total_taxable.toFixed(2)}</td><td>₹ ${row.total_tax.toFixed(2)}</td><td style="font-weight: 800; color: #047857;">₹ ${row.total_revenue.toFixed(2)}</td></tr>`;
    });
    html += `</tbody></table>`;
    reportContentView.innerHTML = html;
  } else if (tabType === "gst") {
    reportContentView.innerHTML = `
      <div style="padding: 16px; font-size: 13px; display: flex; flex-direction: column; gap: 8px;">
        <div>Total Taxable Sales: <strong>₹ ${(data.total_taxable || 0).toFixed(2)}</strong></div>
        <div>CGST (Central Tax): <strong>₹ ${(data.total_cgst || 0).toFixed(2)}</strong></div>
        <div>SGST (State Tax): <strong>₹ ${(data.total_sgst || 0).toFixed(2)}</strong></div>
        <div>IGST (Integrated Tax): <strong>₹ ${(data.total_igst || 0).toFixed(2)}</strong></div>
        <div style="font-size: 15px; font-weight: 800; color: #1e40af; border-top: 1px dashed #cbd5e1; padding-top: 8px;">
          Total GST Collected: ₹ ${(data.total_gst || 0).toFixed(2)}
        </div>
      </div>
    `;
  } else if (tabType === "profit") {
    reportContentView.innerHTML = `
      <div style="padding: 16px; font-size: 13px; display: flex; flex-direction: column; gap: 8px;">
        <div>Total Sales Revenue: <strong>₹ ${(data.total_sales_revenue || 0).toFixed(2)}</strong></div>
        <div>Total Estimated Cost (Purchases): <strong>₹ ${(data.total_estimated_cost || 0).toFixed(2)}</strong></div>
        <div style="font-size: 16px; font-weight: 900; color: #047857; border-top: 1px dashed #cbd5e1; padding-top: 8px;">
          Estimated Gross Profit: ₹ ${(data.estimated_gross_profit || 0).toFixed(2)} (${data.margin_percentage}% Margin)
        </div>
      </div>
    `;
  } else if (tabType === "payments") {
    let html = `<table class="report-table"><thead><tr><th>Payment Method</th><th>Transactions</th><th>Total Collected (₹)</th></tr></thead><tbody>`;
    (data || []).forEach((row) => {
      html += `<tr><td style="font-weight: 700;">${escapeHtml(row.method)}</td><td>${row.count}</td><td style="font-weight: 800; color: #047857;">₹ ${row.total_collected.toFixed(2)}</td></tr>`;
    });
    html += `</tbody></table>`;
    reportContentView.innerHTML = html;
  }
}

// Synchronize companies and session from Python backend
function syncFromBackend() {
  if (!window.backend) return;

  // Mode-aware company fetch based on currently selected billing mode
  fetchAndPopulateCompanies();

  // Mode-aware session restoration check
  if (activeLoginMode === "traditional" && typeof window.backend.traditional_getAuthenticatedSession === "function") {
    window.backend.traditional_getAuthenticatedSession((resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.authenticated && r.data) {
          console.log("[BackendBridge] Active Traditional Billing session restored from backend memory.");
          if (window.BusinessContext) {
            const ok = window.BusinessContext.setAuthenticatedSession(r.data);
            if (ok) {
              if (window.DashboardManager) window.DashboardManager.initForSession();
              activeCompany = window.BusinessContext.getActiveCompany();
              openBillingModeSelection(activeCompany);
            }
          }
        }
      } catch (err) {
        console.error("Traditional session restoration error:", err);
      }
    });
  } else if (activeLoginMode === "fast_billing" && typeof window.backend.getAuthenticatedSession === "function") {
    window.backend.getAuthenticatedSession((resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && r.authenticated && r.data) {
          console.log("[BackendBridge] Active Fast Billing session restored from backend memory.");
          if (window.BusinessContext) {
            const ok = window.BusinessContext.setAuthenticatedSession(r.data);
            if (ok) {
              if (window.DashboardManager) window.DashboardManager.initForSession();
              activeCompany = window.BusinessContext.getActiveCompany();
              openBillingModeSelection(activeCompany);
            }
          }
        }
      } catch (err) {
        console.error("Fast Billing session restoration error:", err);
      }
    });
  }
}

// Initialize QWebChannel if running inside PyQt5 WebEngine
if (typeof QWebChannel !== "undefined" && window.qt && window.qt.webChannelTransport) {
  new QWebChannel(qt.webChannelTransport, function(channel) {
    window.backend = channel.objects.backend;
    console.log("Connected to Qt WebChannel Backend!");

    // Wire up Mobile Scanner signals
    if (window.backend.mobile_scan_signal) {
      window.backend.mobile_scan_signal.connect(function(barcode, deviceName) {
        console.log("Mobile scan signal received:", barcode, deviceName);
        showPosFeedback(`Mobile Scan: ${barcode}`, "success");
        handleBarcodeScan(barcode, false);
      });
    }

    if (window.backend.mobile_status_signal) {
      window.backend.mobile_status_signal.connect(function(status, details) {
        console.log("Mobile scanner status update:", status, details);
        if (status === "CONNECTED") {
          updateMobileScannerStatusUI("CONNECTED", details, true, details, "Active");
          appendMobileScannerLog(`Phone connected: ${details}`);
          showNotification(`Mobile scanner connected: ${details}`);
        } else if (status === "DISCONNECTED" || status === "HEARTBEAT_TIMEOUT") {
          updateMobileScannerStatusUI("DISCONNECTED", details, false, "", "");
          appendMobileScannerLog(`Phone disconnected: ${details}`);
          showNotification(`Mobile scanner disconnected`);
        } else if (status === "ERROR") {
          updateMobileScannerStatusUI("ERROR", details, false, "", "");
          appendMobileScannerLog(`Scanner error: ${details}`);
        } else if (status === "PAIRING") {
          appendMobileScannerLog(`Pairing in progress: ${details}`);
        } else {
          // SERVER_WAITING
          updateMobileScannerStatusUI("WAITING", details, false, "", "");
          appendMobileScannerLog(`Service active: ${details}`);
        }
      });
    }

    syncFromBackend();
  });
}

// =============================================================
// GLOBAL NOTIFICATION TOAST
// =============================================================
function showNotification(message) {
  let toast = document.getElementById("app-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "app-toast";
    toast.style.position = "fixed";
    toast.style.bottom = "36px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.background = "#0f172a";
    toast.style.color = "#ffffff";
    toast.style.padding = "6px 16px";
    toast.style.borderRadius = "3px";
    toast.style.fontSize = "12px";
    toast.style.fontWeight = "600";
    toast.style.boxShadow = "0 4px 10px rgba(0,0,0,0.25)";
    toast.style.zIndex = "9999";
    toast.style.transition = "opacity 0.2s";
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.display = "block";
  toast.style.opacity = "1";
  setTimeout(() => {
    if (toast) {
      toast.style.opacity = "0";
      setTimeout(() => (toast.style.display = "none"), 200);
    }
  }, 2200);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// =============================================================
// EVENT LISTENERS BINDING
// =============================================================
// Standalone Login Listeners
const loginMainForm = document.getElementById("login-main-form");
if (loginMainForm) {
  loginMainForm.addEventListener("submit", (e) => {
    e.preventDefault();
    handleMainLoginSubmit();
  });
}
if (btnLoginSubmit) {
  btnLoginSubmit.addEventListener("click", (e) => {
    e.preventDefault();
    handleMainLoginSubmit();
  });
}
if (btnTogglePwd) {
  btnTogglePwd.addEventListener("click", togglePasswordVisibility);
}
if (btnGotoCompanies) {
  btnGotoCompanies.addEventListener("click", () => showScreen("view-companies"));
}
if (btnCompaniesBack) {
  btnCompaniesBack.addEventListener("click", () => showScreen("view-login"));
}

searchInput.addEventListener("input", filterCompanies);
chkFinYear.addEventListener("change", renderCompanyTable);
chkTaxNo.addEventListener("change", renderCompanyTable);

btnSelect.addEventListener("click", selectCompanyFromList);
btnQuit.addEventListener("click", () => {
  if (confirm("Are you sure you want to quit Alpha Billing Software?")) {
    window.close();
  }
});
btnCreateCompanyModal.addEventListener("click", openCreateCompanyModal);

// Tender Box Listeners
initPosTenderListeners();

// Login Modal
formLogin.addEventListener("submit", (e) => {
  e.preventDefault();
  handleLoginSubmit();
});
btnLoginOk.addEventListener("click", handleLoginSubmit);
btnLoginBack.addEventListener("click", closeLoginModal);

// Create Company Modal
formCreateCompany.addEventListener("submit", (e) => {
  e.preventDefault();
  handleCreateCompanySubmit();
});
btnCloseCreateModal.addEventListener("click", closeCreateCompanyModal);
btnCancelNewCompany.addEventListener("click", closeCreateCompanyModal);

// Configuration Modal
formConfiguration.addEventListener("submit", (e) => {
  e.preventDefault();
  handleSaveConfiguration();
});
btnCloseConfigModal.addEventListener("click", closeConfigurationModal);
btnCancelConfig.addEventListener("click", closeConfigurationModal);

// Dashboard Menu Events (Legacy compatibility)
if (menuCloseCompany) menuCloseCompany.addEventListener("click", closeCompany);
if (menuEditCompany) menuEditCompany.addEventListener("click", () => {
  if (activeCompany) alert(`Editing details for ${activeCompany.name}`);
});
if (menuNewCompany) menuNewCompany.addEventListener("click", openCreateCompanyModal);
if (menuAddAccountMaster) menuAddAccountMaster.addEventListener("click", () => showScreen("view-add-account-master"));
if (menuAddItemMaster) menuAddItemMaster.addEventListener("click", () => openAddProductMaster());
if (menuListItemMaster) menuListItemMaster.addEventListener("click", openProductsListView);
if (menuModifyItemMaster) menuModifyItemMaster.addEventListener("click", openProductsListView);
if (menuConfigFeatures) menuConfigFeatures.addEventListener("click", openConfigurationModal);
if (menuConfigVoucherSeries) menuConfigVoucherSeries.addEventListener("click", openConfigurationModal);
if (menuSalesAdd) menuSalesAdd.addEventListener("click", () => showScreen("view-sales-voucher"));
if (menuSalesList) menuSalesList.addEventListener("click", () => showScreen("view-sales-list"));
if (menuDisplayBills) menuDisplayBills.addEventListener("click", () => showScreen("view-sales-list"));

if (menuChangePassword) menuChangePassword.addEventListener("click", () => {
  if (!activeCompany) return;
  const newPass = prompt(`Enter new password for ${activeCompany.name}:`, activeCompany.password || "");
  if (newPass !== null) {
    activeCompany.password = newPass;
    const idx = companies.findIndex((c) => c.code === activeCompany.code);
    if (idx !== -1) {
      companies[idx].password = newPass;
      saveCompanies();
    }
    showNotification("Password updated.");
  }
});

// Account Master
btnAccSave.addEventListener("click", handleSaveAccountMaster);
btnAccQuit.addEventListener("click", () => showScreen("view-dashboard"));
btnAccCloseTop.addEventListener("click", () => showScreen("view-dashboard"));
btnValidateGstin.addEventListener("click", validateGstinOnline);

if (accName) {
  accName.addEventListener("input", syncAccountPrintName);
  accName.addEventListener("change", syncAccountPrintName);
  accName.addEventListener("keyup", syncAccountPrintName);
  accName.addEventListener("paste", () => setTimeout(syncAccountPrintName, 0));
}

if (accPrintName) {
  accPrintName.readOnly = true;
  accPrintName.setAttribute("readonly", "readonly");
  accPrintName.addEventListener("keydown", (e) => {
    e.preventDefault();
  });
  accPrintName.addEventListener("paste", (e) => {
    e.preventDefault();
  });
}

// Item Master (Add / Edit Product)
if (itemName) {
  itemName.addEventListener("input", syncItemPrintName);
  itemName.addEventListener("change", syncItemPrintName);
  itemName.addEventListener("keyup", syncItemPrintName);
  itemName.addEventListener("paste", () => setTimeout(syncItemPrintName, 0));
}

if (itemPrintName) {
  itemPrintName.readOnly = true;
  itemPrintName.setAttribute("readonly", "readonly");
  itemPrintName.addEventListener("keydown", (e) => {
    e.preventDefault();
  });
  itemPrintName.addEventListener("paste", (e) => {
    e.preventDefault();
  });
}

btnItemSave.addEventListener("click", handleSaveItemMaster);
btnItemQuit.addEventListener("click", () => showScreen("view-items-list"));
btnItemCloseTop.addEventListener("click", () => showScreen("view-dashboard"));
if (btnItemNewClear) btnItemNewClear.addEventListener("click", () => openAddProductMaster());
if (btnItemOpenList) btnItemOpenList.addEventListener("click", openProductsListView);
if (btnItemViewListBottom) btnItemViewListBottom.addEventListener("click", openProductsListView);
if (btnItemBackList) btnItemBackList.addEventListener("click", openProductsListView);

// Products List (Catalogue View)
if (btnItemsListAdd) btnItemsListAdd.addEventListener("click", () => openAddProductMaster());
if (btnItemsListAddBottom) btnItemsListAddBottom.addEventListener("click", () => openAddProductMaster());
if (btnItemsListEditSelected) btnItemsListEditSelected.addEventListener("click", () => {
  if (selectedProductRowId) {
    loadProductForEditing(selectedProductRowId);
  }
});
if (btnItemsListRefresh) btnItemsListRefresh.addEventListener("click", () => {
  renderProductsList(itemsListSearch ? itemsListSearch.value.trim() : "", itemsListGroupFilter ? itemsListGroupFilter.value : "");
});
if (btnItemsListClose) btnItemsListClose.addEventListener("click", () => showScreen("view-dashboard"));
if (btnItemsListCloseBottom) btnItemsListCloseBottom.addEventListener("click", () => showScreen("view-dashboard"));
if (btnItemsListBack) btnItemsListBack.addEventListener("click", () => showScreen("view-dashboard"));

if (itemsListSearch) {
  let searchTimer = null;
  itemsListSearch.addEventListener("input", () => {
    clearTimeout(searchTimer);
    const q = itemsListSearch.value.trim();
    if (btnClearItemSearch) btnClearItemSearch.style.display = q ? "block" : "none";
    searchTimer = setTimeout(() => {
      renderProductsList(q, itemsListGroupFilter ? itemsListGroupFilter.value : "");
    }, 150);
  });
}

if (btnClearItemSearch && itemsListSearch) {
  btnClearItemSearch.addEventListener("click", () => {
    itemsListSearch.value = "";
    btnClearItemSearch.style.display = "none";
    itemsListSearch.focus();
    renderProductsList("", itemsListGroupFilter ? itemsListGroupFilter.value : "");
  });
}

if (itemsListGroupFilter) {
  itemsListGroupFilter.addEventListener("change", () => {
    renderProductsList(itemsListSearch ? itemsListSearch.value.trim() : "", itemsListGroupFilter.value);
  });
}

// Sales Voucher
btnSaveSalesVoucher.addEventListener("click", handleSaveSalesVoucher);
btnQuitSalesVoucher.addEventListener("click", () => showScreen("view-dashboard"));
btnSalesCloseTop.addEventListener("click", () => showScreen("view-dashboard"));

// =============================================================
// DUAL BILLING MODE & FAST BILLING EVENT BINDINGS
// =============================================================
// Mode Selection Actions
if (btnSelectBilling) {
  btnSelectBilling.addEventListener("click", () => enterCompanyDashboard(activeCompany));
}
if (cardModeBilling) {
  cardModeBilling.addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") enterCompanyDashboard(activeCompany);
  });
  cardModeBilling.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      enterCompanyDashboard(activeCompany);
    }
  });
}
if (btnSelectFastBilling) {
  btnSelectFastBilling.addEventListener("click", () => openFastBillingPos());
}
if (cardModeFastBilling) {
  cardModeFastBilling.addEventListener("click", (e) => {
    if (e.target.tagName !== "BUTTON") openFastBillingPos();
  });
  cardModeFastBilling.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openFastBillingPos();
    }
  });
}
if (btnModeSettings) {
  btnModeSettings.addEventListener("click", () => openConfigurationModal());
}
if (btnModeLogout) {
  btnModeLogout.addEventListener("click", () => logoutUser());
}
if (menuSwitchMode) {
  menuSwitchMode.addEventListener("click", () => showScreen("view-mode-selection"));
}
if (barSwitchMode) {
  barSwitchMode.addEventListener("click", () => showScreen("view-mode-selection"));
}

// =============================================================
// INTERNAL TABS & FAST BILLING NAVIGATION EVENT BINDINGS
// =============================================================
if (tabBtnTraditional) {
  tabBtnTraditional.addEventListener("click", () => activateBillingTab("traditional"));
}
if (tabBtnFastBilling) {
  tabBtnFastBilling.addEventListener("click", () => activateBillingTab("fast_billing"));
}
if (btnCloseTradTab) {
  btnCloseTradTab.addEventListener("click", (e) => {
    e.stopPropagation();
    closeBillingTab("traditional");
  });
}
if (btnCloseFastTab) {
  btnCloseFastTab.addEventListener("click", (e) => {
    e.stopPropagation();
    closeBillingTab("fast_billing");
  });
}
if (btnTabSwitchMode) {
  btnTabSwitchMode.addEventListener("click", () => showScreen("view-mode-selection"));
}

// Fast Billing Ribbon Navigation Tabs
if (btnPosTabNewSale) {
  btnPosTabNewSale.addEventListener("click", () => openFastBillingNewBill());
}
if (btnPosTabTodaySales) {
  btnPosTabTodaySales.addEventListener("click", () => openFastBillingHistory());
}
if (btnPosTabReprint) {
  btnPosTabReprint.addEventListener("click", () => openFastBillingReprint());
}
if (btnPosBarTodayHistory) {
  btnPosBarTodayHistory.addEventListener("click", () => openFastBillingHistory());
}

// Today's Sales History Event Listeners
if (btnPosHistoryBack) {
  btnPosHistoryBack.addEventListener("click", () => openFastBillingNewBill());
}
if (btnPosHistoryRefresh) {
  btnPosHistoryRefresh.addEventListener("click", () => renderFastBillingHistory());
}
if (btnPosHistoryClose) {
  btnPosHistoryClose.addEventListener("click", () => openFastBillingNewBill());
}
if (posHistorySearch) {
  posHistorySearch.addEventListener("input", () => {
    const q = posHistorySearch.value.trim().toUpperCase();
    if (!q) {
      renderTodaySalesTable(todaySalesHistoryData);
    } else {
      const filtered = todaySalesHistoryData.filter((v) => {
        const no = String(v.vch_no || "").toUpperCase();
        const party = String(v.party_name || "").toUpperCase();
        const method = String(v.payment_method || "").toUpperCase();
        return no.includes(q) || party.includes(q) || method.includes(q);
      });
      renderTodaySalesTable(filtered);
    }
  });
}

// Dedicated Print Screen Event Listeners
document.querySelectorAll(".btn-paper-format").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".btn-paper-format").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentPrintPaperFormat = btn.dataset.format || "thermal-80";

    const customRow = document.getElementById("custom-paper-dimensions");
    if (customRow) {
      customRow.style.display = currentPrintPaperFormat === "custom" ? "flex" : "none";
    }
    renderInvoicePrintPreview();
  });
});

document.querySelectorAll(".btn-orientation").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".btn-orientation").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentPrintOrientation = btn.dataset.orientation || "portrait";
    renderInvoicePrintPreview();
  });
});

if (btnCopyDec) {
  btnCopyDec.addEventListener("click", () => {
    if (posPrintCopies) {
      const val = Math.max(1, (parseInt(posPrintCopies.value) || 1) - 1);
      posPrintCopies.value = val;
    }
  });
}
if (btnCopyInc) {
  btnCopyInc.addEventListener("click", () => {
    if (posPrintCopies) {
      const val = Math.min(10, (parseInt(posPrintCopies.value) || 1) + 1);
      posPrintCopies.value = val;
    }
  });
}

if (btnTriggerPrint) {
  btnTriggerPrint.addEventListener("click", () => triggerInvoicePrint());
}
if (btnRefreshPreview) {
  btnRefreshPreview.addEventListener("click", () => renderInvoicePrintPreview());
}
if (btnDownloadPdfPrint) {
  btnDownloadPdfPrint.addEventListener("click", () => {
    const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "";
    const vchId = currentPrintVchId || (currentPrintVchData ? (currentPrintVchData.id || currentPrintVchData.voucher_id || currentPrintVchData.vch_no) : "");
    const vchType = currentPrintVoucherType || "sales_invoice";
    const mode = activeBillingMode || "traditional";

    if (window.backend && window.backend.exportVoucherPdf && vchId) {
      window.backend.exportVoucherPdf(compId, vchType, vchId, currentPrintPaperFormat, "", mode, (resp) => {
        try {
          const res = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (res.success) {
            showNotification(`PDF Document generated: ${res.file_path || res.filepath}`);
          } else {
            alert(`PDF generation failed: ${res.error}`);
          }
        } catch (e) {
          alert(`PDF error: ${e}`);
        }
      });
      return;
    }

    if (window.backend && window.backend.generatePdfInvoice && vchId) {
      window.backend.generatePdfInvoice(compId, vchId, (resp) => {
        try {
          const res = JSON.parse(resp);
          if (res.success) {
            showNotification(`PDF Invoice generated: ${res.filepath}`);
          } else {
            alert(`PDF generation failed: ${res.error}`);
          }
        } catch (e) {
          alert(`PDF error: ${e}`);
        }
      });
    } else {
      showNotification("PDF download simulated (voucher saved).");
    }
  });
}
function returnFromPrintScreen() {
  if (printSourceScreen === "view-sales-voucher") {
    printSourceScreen = "view-fast-billing";
    initSalesVoucherScreen();
    showScreen("view-sales-voucher");
  } else {
    openFastBillingNewBill();
  }
}

if (btnPrintScreenNewBill) {
  btnPrintScreenNewBill.addEventListener("click", () => returnFromPrintScreen());
}
if (btnPrintNextBill) {
  btnPrintNextBill.addEventListener("click", () => returnFromPrintScreen());
}
if (btnPosPrintBack) {
  btnPosPrintBack.addEventListener("click", () => returnFromPrintScreen());
}
if (btnPosPrintClose) {
  btnPosPrintClose.addEventListener("click", () => returnFromPrintScreen());
}

const customWidthInput = document.getElementById("custom-paper-width");
const customHeightInput = document.getElementById("custom-paper-height");
if (customWidthInput) customWidthInput.addEventListener("input", () => renderInvoicePrintPreview());
if (customHeightInput) customHeightInput.addEventListener("input", () => renderInvoicePrintPreview());

// Fast Billing Header Navigation
if (menuFastBilling) menuFastBilling.addEventListener("click", () => openFastBillingPos());
if (btnPosBackMode) {
  btnPosBackMode.addEventListener("click", () => navigateAwayFromPos("view-mode-selection"));
}
if (btnPosClose) {
  btnPosClose.addEventListener("click", () => navigateAwayFromPos("view-mode-selection"));
}
if (btnPosLogout) {
  btnPosLogout.addEventListener("click", () => logoutUser());
}

// Fast Billing Bottom Cashier Action Bar
if (btnPosBarNewSale) {
  btnPosBarNewSale.addEventListener("click", () => {
    if (posCart.length > 0) {
      if (confirm("Cart contains items. Click OK to PARK this sale before starting a new one.")) {
        if (btnPosHold) btnPosHold.click();
      } else if (!confirm("Discard current cart for a new sale?")) {
        return;
      } else {
        posCart = [];
        renderPosCart();
      }
    }
    initFastBillingScreen();
    showNotification("Ready for New POS Sale.");
  });
}
if (btnPosBarSearch) {
  btnPosBarSearch.addEventListener("click", () => {
    openProductSearchModal("POS");
  });
}
if (btnPosBarHold) {
  btnPosBarHold.addEventListener("click", () => {
    if (btnPosHold) btnPosHold.click();
  });
}
if (btnPosBarResume) {
  btnPosBarResume.addEventListener("click", () => {
    if (btnPosResume) btnPosResume.click();
  });
}
if (btnPosBarRemove) {
  btnPosBarRemove.addEventListener("click", () => {
    if (posCart.length === 0) {
      alert("Cart is empty.");
      return;
    }
    const removed = posCart.pop();
    renderPosCart();
    showNotification(`Removed ${removed.name} from cart.`);
    if (posBarcodeInput) posBarcodeInput.focus();
  });
}
if (btnPosBarCancel) {
  btnPosBarCancel.addEventListener("click", () => {
    if (posCart.length > 0 && confirm("Cancel current sale and clear cart?")) {
      posCart = [];
      renderPosCart();
      showNotification("Sale cancelled.");
      if (posBarcodeInput) posBarcodeInput.focus();
    }
  });
}
if (btnPosBarCheckout) {
  btnPosBarCheckout.addEventListener("click", () => triggerPosCheckout("CASH"));
}
if (btnPosBarReprint) {
  btnPosBarReprint.addEventListener("click", () => {
    if (lastCompletedVoucher) {
      showReceiptModal(lastCompletedVoucher);
    } else {
      alert("No recent sale receipt available to reprint in this session.");
    }
  });
}



if (btnPosClear) {
  btnPosClear.addEventListener("click", () => {
    if (posCart.length > 0 && confirm("Clear current cart?")) {
      posCart = [];
      renderPosCart();
      if (posBarcodeInput) posBarcodeInput.focus();
    }
  });
}

if (btnPosHold) {
  btnPosHold.addEventListener("click", () => {
    if (posCart.length === 0) {
      alert("Cart is empty; nothing to hold.");
      return;
    }
    const billTime = new Date().toLocaleTimeString();
    heldBills.push({
      id: Date.now(),
      time: billTime,
      items: [...posCart]
    });
    posCart = [];
    if (heldCountEl) heldCountEl.textContent = heldBills.length;
    renderPosCart();
    showNotification(`Bill parked at ${billTime}. Total parked: ${heldBills.length}`);
    if (posBarcodeInput) posBarcodeInput.focus();
  });
}

if (btnPosResume) {
  btnPosResume.addEventListener("click", () => {
    if (heldBills.length === 0) {
      alert("No held bills to resume.");
      return;
    }
    const parked = heldBills.pop();
    if (heldCountEl) heldCountEl.textContent = heldBills.length;
    posCart = parked.items;
    renderPosCart();
    showNotification(`Resumed parked bill from ${parked.time}.`);
    if (posBarcodeInput) posBarcodeInput.focus();
  });
}

let modalSearchTarget = "POS";
let modalTargetVoucherRow = null;
let modalProductItems = [];
let modalActiveIndex = -1;

function openProductSearchModal(target = "POS", voucherRow = null) {
  modalSearchTarget = target;
  modalTargetVoucherRow = voucherRow;
  modalActiveIndex = -1;

  if (modalPosItemSearch) {
    modalPosItemSearch.classList.add("show");
    modalPosItemSearch.style.display = "flex";
  }

  if (posModalSearchInput) {
    posModalSearchInput.value = "";
    setTimeout(() => posModalSearchInput.focus(), 50);
  }

  renderModalProductSearch("");
}

function closeProductSearchModal() {
  if (modalPosItemSearch) {
    modalPosItemSearch.classList.remove("show");
    modalPosItemSearch.style.display = "none";
  }
  if (modalSearchTarget === "POS" && posBarcodeInput) {
    posBarcodeInput.focus();
  } else if (modalSearchTarget === "VOUCHER" && modalTargetVoucherRow) {
    const qtyInput = vchItemsTbody.querySelector(`.vch-qty-input[data-row="${modalTargetVoucherRow}"]`);
    if (qtyInput) qtyInput.focus();
  } else if (modalSearchTarget === "PURCHASE") {
    const purBarcodeInput = document.getElementById("pur-barcode-input");
    if (purBarcodeInput) purBarcodeInput.focus();
  }
}

function renderModalProductSearch(query = "") {
  if (!posSearchModalTbody) return;
  posSearchModalTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #64748b;">Searching products...</td></tr>`;

  const onItemsLoaded = (items) => {
    modalProductItems = items || [];
    posSearchModalTbody.innerHTML = "";
    modalActiveIndex = -1;

    const countEl = document.getElementById("pos-modal-search-count");
    const emptyMsg = document.getElementById("pos-search-modal-empty");

    if (countEl) countEl.textContent = `Showing ${modalProductItems.length} products`;

    if (modalProductItems.length === 0) {
      if (emptyMsg) emptyMsg.style.display = "block";
      return;
    }
    if (emptyMsg) emptyMsg.style.display = "none";

    modalProductItems.forEach((it, idx) => {
      const tr = document.createElement("tr");
      tr.dataset.index = idx;

      const price = parseFloat(it.selling_price ?? it.sellingPrice ?? it.sales_price ?? it.salesPrice ?? 0).toFixed(2);
      const barcode = it.barcodes || it.alias || it.matched_barcode || it.barcode || "-";
      const group = it.item_group || it.group || "General";

      tr.innerHTML = `
        <td><strong>${escapeHtml(it.name)}</strong></td>
        <td><span class="badge-barcode">${escapeHtml(barcode)}</span></td>
        <td><span class="badge-category">${escapeHtml(group)}</span></td>
        <td style="text-align: right; font-weight: 700; color: #166534;">₹ ${price}</td>
        <td style="text-align: center;">
          <button type="button" class="btn-table-action primary btn-modal-select-item" data-index="${idx}">
            ${modalSearchTarget === "POS" ? "+ Add to Cart" : "Select Product"}
          </button>
        </td>
      `;

      tr.addEventListener("click", () => {
        selectProductFromModal(it);
      });

      const btn = tr.querySelector(".btn-modal-select-item");
      if (btn) {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          selectProductFromModal(it);
        });
      }

      posSearchModalTbody.appendChild(tr);
    });
  };

  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  if (modalSearchTarget === "POS" && window.backend && window.backend.searchCashierProducts) {
    window.backend.searchCashierProducts(compId, query, (resp) => {
      try {
        const r = JSON.parse(resp);
        onItemsLoaded(r.success ? r.data : []);
      } catch (e) {
        onItemsLoaded([]);
      }
    });
  } else {
    fetchAllItems(query, onItemsLoaded);
  }
}

function selectProductFromModal(item) {
  closeProductSearchModal();
  if (modalSearchTarget === "POS") {
    addItemToPosCart(item);
    showPosFeedback(`Added: ${item.name}`, "success");
    showNotification(`Added ${item.name} to cart.`);
    if (item.is_verified === 0 || item.matched_barcode === "8909263004690" || parseFloat(item.sales_price || 0) <= 0) {
      showMedicalVerificationModal(item);
    }
    if (posBarcodeInput) posBarcodeInput.focus();
  } else if (modalSearchTarget === "VOUCHER") {
    if (modalTargetVoucherRow) {
      populateVoucherRowWithItem(modalTargetVoucherRow, item);
    }
  } else if (modalSearchTarget === "PURCHASE") {
    const costRate = parseFloat(item.purc_price ?? item.purchase_price ?? item.sales_price ?? 0);
    const taxRate = parseFloat(item.tax_rate ?? 18);
    const lineTotal = costRate * (1 + (taxRate / 100));
    purchaseItemsData.push({
      item_id: item.id,
      barcode: item.barcode || item.alias || "",
      name: item.name,
      batch_no: "",
      expiry_date: "",
      qty: 1,
      free_qty: 0,
      unit: item.unit || "Pcs.",
      cost_rate: costRate,
      discount_pct: 0,
      taxable_amount: costRate,
      tax_rate: taxRate,
      cgst_amount: 0,
      sgst_amount: 0,
      igst_amount: 0,
      line_total: lineTotal
    });
    renderPurchaseGridRows();
    calcPurchaseTotals();
    showNotification(`Added ${item.name} to purchase voucher.`);
    const purBarcodeInput = document.getElementById("pur-barcode-input");
    if (purBarcodeInput) purBarcodeInput.focus();
  }
}

// Fast Billing Barcode & Product Live Autocomplete
let activePosSuggestionIndex = -1;
let currentPosSuggestions = [];

function setupPosBarcodeAutocomplete() {
  if (!posBarcodeInput || !posBarcodeSuggestions) return;

  let debounceTimer = null;

  posBarcodeInput.addEventListener("input", () => {
    const text = posBarcodeInput.value.trim();
    clearTimeout(debounceTimer);

    if (!text || text.length < 1) {
      posBarcodeSuggestions.style.display = "none";
      currentPosSuggestions = [];
      activePosSuggestionIndex = -1;
      return;
    }

    debounceTimer = setTimeout(() => {
      const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "";
      if (window.backend && window.backend.searchCashierProducts) {
        window.backend.searchCashierProducts(compId, text, (resp) => {
          try {
            const r = JSON.parse(resp);
            if (!r.success || !r.data || r.data.length === 0) {
              posBarcodeSuggestions.style.display = "none";
              currentPosSuggestions = [];
              activePosSuggestionIndex = -1;
              return;
            }
            currentPosSuggestions = r.data.slice(0, 10);
            activePosSuggestionIndex = -1;
            renderPosBarcodeSuggestions(currentPosSuggestions);
          } catch (e) {
            posBarcodeSuggestions.style.display = "none";
          }
        });
      } else {
        fetchAllItems(text, (items) => {
          if (!items || items.length === 0) {
            posBarcodeSuggestions.style.display = "none";
            currentPosSuggestions = [];
            activePosSuggestionIndex = -1;
            return;
          }
          currentPosSuggestions = items.slice(0, 10);
          activePosSuggestionIndex = -1;
          renderPosBarcodeSuggestions(currentPosSuggestions);
        });
      }
    }, 150);
  });

  posBarcodeInput.addEventListener("keydown", (e) => {
    const isSuggestionsVisible = posBarcodeSuggestions.style.display !== "none" && currentPosSuggestions.length > 0;

    if (e.key === "ArrowDown") {
      if (isSuggestionsVisible) {
        e.preventDefault();
        activePosSuggestionIndex = (activePosSuggestionIndex + 1) % currentPosSuggestions.length;
        highlightPosSuggestion(activePosSuggestionIndex);
      }
    } else if (e.key === "ArrowUp") {
      if (isSuggestionsVisible) {
        e.preventDefault();
        activePosSuggestionIndex = (activePosSuggestionIndex - 1 + currentPosSuggestions.length) % currentPosSuggestions.length;
        highlightPosSuggestion(activePosSuggestionIndex);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (isSuggestionsVisible && activePosSuggestionIndex >= 0) {
        const selected = currentPosSuggestions[activePosSuggestionIndex];
        selectPosSuggestionItem(selected);
      } else {
        const val = posBarcodeInput.value.trim();
        posBarcodeSuggestions.style.display = "none";
        currentPosSuggestions = [];
        activePosSuggestionIndex = -1;
        if (val) {
          handleBarcodeScan(val, false);
          posBarcodeInput.value = "";
        }
      }
    } else if (e.key === "Escape") {
      posBarcodeSuggestions.style.display = "none";
      currentPosSuggestions = [];
      activePosSuggestionIndex = -1;
    }
  });

  document.addEventListener("click", (e) => {
    if (!posBarcodeInput.contains(e.target) && !posBarcodeSuggestions.contains(e.target)) {
      posBarcodeSuggestions.style.display = "none";
    }
  });
}

function renderPosBarcodeSuggestions(items) {
  posBarcodeSuggestions.innerHTML = "";
  items.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "pos-suggestion-item";
    div.dataset.index = index;

    const price = parseFloat(item.selling_price ?? item.sellingPrice ?? item.sales_price ?? item.salesPrice ?? 0).toFixed(2);
    const barcode = item.barcodes || item.alias || item.matched_barcode || item.barcode || "";
    const group = item.item_group || item.group || "General";

    div.innerHTML = `
      <div class="pos-suggestion-left">
        <span class="pos-suggestion-name">${escapeHtml(item.name)}</span>
        <div class="pos-suggestion-meta">
          <span>${escapeHtml(group)}</span>
          ${barcode ? `<span>• Barcode: <strong>${escapeHtml(barcode)}</strong></span>` : ""}
          <span>• Unit: ${escapeHtml(item.unit || "Pcs.")}</span>
        </div>
      </div>
      <div class="pos-suggestion-right">
        <span class="pos-suggestion-price">₹ ${price}</span>
        <span class="pos-suggestion-add-tag">+ Add Enter</span>
      </div>
    `;

    div.addEventListener("mousedown", (e) => {
      e.preventDefault();
      selectPosSuggestionItem(item);
    });

    posBarcodeSuggestions.appendChild(div);
  });

  posBarcodeSuggestions.style.display = "block";
}

function highlightPosSuggestion(index) {
  const items = posBarcodeSuggestions.querySelectorAll(".pos-suggestion-item");
  items.forEach((el, i) => {
    el.classList.toggle("active", i === index);
    if (i === index) el.scrollIntoView({ block: "nearest" });
  });
}

function selectPosSuggestionItem(item) {
  posBarcodeSuggestions.style.display = "none";
  posBarcodeInput.value = "";
  currentPosSuggestions = [];
  activePosSuggestionIndex = -1;
  addItemToPosCart(item);
  showPosFeedback(`Added: ${item.name}`, "success");
  if (item.is_verified === 0 || item.matched_barcode === "8909263004690" || parseFloat(item.sales_price || 0) <= 0) {
    showMedicalVerificationModal(item);
  }
  posBarcodeInput.focus();
}

if (btnPosSearchItem) {
  btnPosSearchItem.addEventListener("click", () => {
    openProductSearchModal("POS");
  });
}

if (btnVchSearchProducts) {
  btnVchSearchProducts.addEventListener("click", () => {
    openProductSearchModal("VOUCHER", 1);
  });
}

if (btnClosePosItemSearch) {
  btnClosePosItemSearch.addEventListener("click", closeProductSearchModal);
}

if (btnCancelPosItemSearch) {
  btnCancelPosItemSearch.addEventListener("click", closeProductSearchModal);
}

if (btnModalSearchClear && posModalSearchInput) {
  btnModalSearchClear.addEventListener("click", () => {
    posModalSearchInput.value = "";
    posModalSearchInput.focus();
    renderModalProductSearch("");
  });
}

if (posModalSearchInput) {
  let modalDebounce = null;
  posModalSearchInput.addEventListener("input", () => {
    clearTimeout(modalDebounce);
    modalDebounce = setTimeout(() => {
      renderModalProductSearch(posModalSearchInput.value.trim());
    }, 150);
  });

  posModalSearchInput.addEventListener("keydown", (e) => {
    const rows = posSearchModalTbody ? posSearchModalTbody.querySelectorAll("tr") : [];
    if (rows.length === 0) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      modalActiveIndex = (modalActiveIndex + 1) % rows.length;
      rows.forEach((r, i) => {
        r.classList.toggle("selected-row", i === modalActiveIndex);
        if (i === modalActiveIndex) r.scrollIntoView({ block: "nearest" });
      });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      modalActiveIndex = (modalActiveIndex - 1 + rows.length) % rows.length;
      rows.forEach((r, i) => {
        r.classList.toggle("selected-row", i === modalActiveIndex);
        if (i === modalActiveIndex) r.scrollIntoView({ block: "nearest" });
      });
    } else if (e.key === "Enter" && modalActiveIndex >= 0 && modalProductItems[modalActiveIndex]) {
      e.preventDefault();
      selectProductFromModal(modalProductItems[modalActiveIndex]);
    } else if (e.key === "Escape") {
      closeProductSearchModal();
    }
  });
}

// Payment triggers
if (btnPosPayCash) btnPosPayCash.addEventListener("click", () => triggerPosCheckout("CASH"));
if (btnPosPayUpi) btnPosPayUpi.addEventListener("click", () => triggerPosCheckout("UPI"));
if (btnPosPayCard) btnPosPayCard.addEventListener("click", () => triggerPosCheckout("CARD"));
if (btnPosPaySplit) btnPosPaySplit.addEventListener("click", () => triggerPosCheckout("SPLIT"));
if (btnPosCheckoutPrint) btnPosCheckoutPrint.addEventListener("click", () => triggerPosCheckout("CASH"));

// Cash Modal Event Listeners
if (posCashTendered) {
  posCashTendered.addEventListener("input", () => {
    const tendered = parseFloat(posCashTendered.value) || 0;
    const due = parseFloat(modalCashDueVal.textContent.replace("₹", "").trim()) || 0;
    const change = Math.max(tendered - due, 0);
    modalCashChangeVal.textContent = `₹ ${change.toFixed(2)}`;
  });
  posCashTendered.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      btnConfirmPosCash.click();
    }
  });
}

if (btnConfirmPosCash) {
  btnConfirmPosCash.addEventListener("click", () => {
    const tendered = parseFloat(posCashTendered.value) || 0;
    const due = parseFloat(modalCashDueVal.textContent.replace("₹", "").trim()) || 0;
    if (tendered < due) {
      alert(`PAYMENT VALIDATION FAILED\n\nTendered amount (₹ ${tendered.toFixed(2)}) is less than Due amount (₹ ${due.toFixed(2)}).\n\nOutstanding Balance Due: ₹ ${(due - tendered).toFixed(2)}.\n\nPlease collect the full cash payment.`);
      posCashTendered.focus();
      posCashTendered.select();
      return;
    }
    modalPosCash.classList.remove("show");
    finalizePosSale("CASH", tendered, Math.max(tendered - due, 0));
  });
}

if (btnClosePosCash) {
  btnClosePosCash.addEventListener("click", () => modalPosCash.classList.remove("show"));
}

// Thermal Receipt Modal
if (btnCloseReceiptModal) {
  btnCloseReceiptModal.addEventListener("click", () => modalReceiptPreview.classList.remove("show"));
}
if (btnPrintReceiptAction) {
  btnPrintReceiptAction.addEventListener("click", () => {
    window.print();
    showNotification("Print sent to system printer spooler.");
  });
}
if (btnDownloadPdfInvoice) {
  btnDownloadPdfInvoice.addEventListener("click", () => {
    if (window.backend && activeCompany && lastCompletedVoucher) {
      window.backend.generatePdfInvoice(activeCompany.id, lastCompletedVoucher, (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
            alert(`A4 Tax Invoice PDF generated successfully at:\n${r.filepath}`);
          }
        } catch (e) {}
      });
    } else {
      window.print();
    }
  });
}

// Backup & Restore Dialog
if (menuBackupRestore) menuBackupRestore.addEventListener("click", openBackupModal);
if (btnCloseBackupModal) btnCloseBackupModal.addEventListener("click", () => modalBackup.classList.remove("show"));

if (btnTriggerBackup) {
  btnTriggerBackup.addEventListener("click", () => {
    if (!window.backend) {
      alert("Backup feature requires the desktop application runtime.");
      return;
    }
    const ext = backupExternalDrive ? backupExternalDrive.value.trim() : "";
    btnTriggerBackup.disabled = true;
    btnTriggerBackup.textContent = "Backing up...";
    window.backend.performBackup(ext, (resp) => {
      btnTriggerBackup.disabled = false;
      btnTriggerBackup.textContent = "Create Local Backup";
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          showNotification(r.data.message || "Backup created successfully!");
          refreshBackupList();
        } else {
          alert(`Backup failed: ${r.error}`);
        }
      } catch (e) {
        alert(`Backup error: ${e}`);
      }
    });
  });
}

// Reports Dialog
if (menuGstReports) menuGstReports.addEventListener("click", openReportsModal);
if (btnCloseReportsModal) btnCloseReportsModal.addEventListener("click", () => modalReports.classList.remove("show"));

document.querySelectorAll(".report-tab-btn").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    document.querySelectorAll(".report-tab-btn").forEach((b) => b.classList.remove("primary-btn"));
    e.target.classList.add("primary-btn");
    loadReportData(e.target.dataset.tab);
  });
});

// Data Migration Dialog
if (menuDataExportImport) {
  menuDataExportImport.addEventListener("click", () => {
    if (migrationStatusMsg) migrationStatusMsg.textContent = "";
    modalDataMigration.classList.add("show");
  });
}
if (btnCloseMigrationModal) {
  btnCloseMigrationModal.addEventListener("click", () => modalDataMigration.classList.remove("show"));
}

if (btnExportJsonAction) {
  btnExportJsonAction.addEventListener("click", () => {
    if (!activeCompany) {
      alert("Please select a company first.");
      return;
    }
    const code = activeCompany.code;
    const exportData = {
      alpha_companies: companies,
      [`alpha_config_${code}`]: getCompanyConfig(code),
      [`alpha_accounts_${code}`]: JSON.parse(localStorage.getItem(`alpha_accounts_${code}`) || "[]"),
      [`alpha_items_${code}`]: JSON.parse(localStorage.getItem(`alpha_items_${code}`) || "[]"),
      [`alpha_vouchers_${code}`]: getSalesVouchers()
    };
    const jsonStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
    const dlAnchor = document.createElement("a");
    dlAnchor.setAttribute("href", jsonStr);
    dlAnchor.setAttribute("download", `AntiMatrix_${code}_Export.json`);
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();
    if (migrationStatusMsg) migrationStatusMsg.textContent = `Exported data for ${activeCompany.name} to JSON file.`;
  });
}

if (btnImportJsonAction) {
  btnImportJsonAction.addEventListener("click", () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".json";
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (event) => {
        try {
          const payload = JSON.parse(event.target.result);
          if (window.backend) {
            window.backend.importLocalStoragePayload(JSON.stringify(payload), (resp) => {
              const r = JSON.parse(resp);
              if (r.success) {
                alert(`Data imported into SQLite database successfully!\nCompanies: ${r.data.companies_imported}, Items: ${r.data.items_imported}, Accounts: ${r.data.accounts_imported}, Bills: ${r.data.vouchers_imported}`);
                location.reload();
              } else {
                alert(`Import failed: ${r.error}`);
              }
            });
          } else {
            // Local fallback import
            if (payload.alpha_companies) localStorage.setItem("alpha_companies", JSON.stringify(payload.alpha_companies));
            Object.keys(payload).forEach((k) => {
              if (k.startsWith("alpha_")) localStorage.setItem(k, typeof payload[k] === "string" ? payload[k] : JSON.stringify(payload[k]));
            });
            alert("Data imported into browser storage successfully!");
            location.reload();
          }
        } catch (err) {
          alert(`Invalid JSON file: ${err.message}`);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  });
}

// =============================================================
// MOBILE SCANNER & SIMULATION CONTROLS
// =============================================================
const btnPosMobileScanner = document.getElementById("btn-pos-mobile-scanner");
const modalMobileScanner = document.getElementById("modal-mobile-scanner");
const btnCloseMobileScanner = document.getElementById("btn-close-mobile-scanner");
const btnDismissMobileScanner = document.getElementById("btn-dismiss-mobile-scanner");
const btnRevokeScannerToken = document.getElementById("btn-revoke-scanner-token");
const btnCopyScannerUrl = document.getElementById("btn-copy-scanner-url");
const btnOpenScannerBrowser = document.getElementById("btn-open-scanner-browser");
const btnClearScannerLog = document.getElementById("btn-clear-scanner-log");

const btnPosSimulateScan = document.getElementById("btn-pos-simulate-scan");
const modalSimulateScan = document.getElementById("modal-simulate-scan");
const btnCloseSimulateScan = document.getElementById("btn-close-simulate-scan");
const btnCloseSimDialog = document.getElementById("btn-close-sim-dialog");
const formSimulateScan = document.getElementById("form-simulate-scan");
const simBarcodeInput = document.getElementById("sim-barcode-input");

const modalMedVerification = document.getElementById("modal-medical-verification");
const btnCloseMedVerification = document.getElementById("btn-close-medical-verification");
const btnAckMedVerification = document.getElementById("btn-ack-medical-verification");

function openMobileScannerModal() {
  if (!modalMobileScanner) return;
  modalMobileScanner.style.display = "flex";
  
  const compId = activeCompany ? (activeCompany.id || activeCompany.code) : "COMP0001";
  if (window.backend && window.backend.startMobileScanner) {
    window.backend.startMobileScanner(compId, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          renderMobileScannerInfo(res.data);
        } else {
          showNotification(`Scanner error: ${res.error || "Failed to start"}`);
        }
      } catch (e) {
        console.error("Error starting mobile scanner:", e);
      }
    });
  } else {
    renderMobileScannerInfo({
      url: "http://127.0.0.1:8990/scanner?token=standalone_test",
      is_running: true,
      lan_ip: "127.0.0.1",
      port: 8990,
      token: "standalone_test",
      status: "Desktop Standalone (Browser Mode)"
    });
  }
}

function closeMobileScannerModal() {
  if (modalMobileScanner) modalMobileScanner.style.display = "none";
}

function updateMobileScannerStatusUI(status, details, isConnected, deviceName, lastHeartbeat) {
  const statusText = document.getElementById("mobile-scanner-status-text");
  const statusPill = document.getElementById("mobile-scanner-pill");
  const toolbarBadge = document.getElementById("pos-scanner-status-indicator");
  const heartbeatEl = document.getElementById("mobile-scanner-heartbeat-text");

  if (isConnected) {
    if (statusPill) {
      statusPill.textContent = "PHONE CONNECTED";
      statusPill.className = "mobile-status-pill connected";
    }
    if (statusText) {
      statusText.textContent = `● Connected: ${deviceName || "Mobile device"}`;
      statusText.style.color = "#15803d";
    }
    if (toolbarBadge) {
      toolbarBadge.textContent = "Connected";
      toolbarBadge.className = "pos-scanner-badge connected";
      toolbarBadge.title = `Phone Connected: ${deviceName || "Mobile device"}`;
    }
    if (heartbeatEl) {
      heartbeatEl.textContent = `Last Heartbeat: ${lastHeartbeat || "Active"}`;
      heartbeatEl.style.display = "block";
    }
  } else if (status === "ERROR") {
    if (statusPill) {
      statusPill.textContent = "ERROR";
      statusPill.className = "mobile-status-pill error";
    }
    if (statusText) {
      statusText.textContent = `● ${details || "Connection Error"}`;
      statusText.style.color = "#dc2626";
    }
    if (toolbarBadge) {
      toolbarBadge.textContent = "Error";
      toolbarBadge.className = "pos-scanner-badge error";
      toolbarBadge.title = details || "Connection Error";
    }
    if (heartbeatEl) heartbeatEl.style.display = "none";
  } else if (status === "DISCONNECTED") {
    if (statusPill) {
      statusPill.textContent = "DISCONNECTED";
      statusPill.className = "mobile-status-pill disconnected";
    }
    if (statusText) {
      statusText.textContent = "● Phone disconnected. Scan QR code to reconnect.";
      statusText.style.color = "#b45309";
    }
    if (toolbarBadge) {
      toolbarBadge.textContent = "Disconnected";
      toolbarBadge.className = "pos-scanner-badge waiting";
      toolbarBadge.title = "Phone disconnected";
    }
    if (heartbeatEl) heartbeatEl.style.display = "none";
  } else {
    // Waiting for Phone
    if (statusPill) {
      statusPill.textContent = "WAITING FOR PHONE";
      statusPill.className = "mobile-status-pill waiting";
    }
    if (statusText) {
      statusText.textContent = `● ${details || "Service Running — Waiting for Phone"}`;
      statusText.style.color = "#475569";
    }
    if (toolbarBadge) {
      toolbarBadge.textContent = "Ready";
      toolbarBadge.className = "pos-scanner-badge waiting";
      toolbarBadge.title = "Scanner Ready — Waiting for Phone";
    }
    if (heartbeatEl) heartbeatEl.style.display = "none";
  }
}

function renderMobileScannerInfo(info) {
  const urlInput = document.getElementById("mobile-scanner-url-input");
  const qrBox = document.getElementById("mobile-scanner-qr-svg");
  const linkCa = document.getElementById("link-download-ca");
  const linkSetup = document.getElementById("link-open-setup-guide");

  if (urlInput) urlInput.value = info.url || "";
  if (linkCa && info.ca_url) linkCa.href = info.ca_url;
  if (linkSetup && info.setup_url) linkSetup.href = info.setup_url;

  const isConn = info.client_connected === true;
  const dev = info.connected_device || "";
  const st = isConn ? "CONNECTED" : (info.status === "Connection Error" ? "ERROR" : (info.status === "Disconnected" ? "DISCONNECTED" : "WAITING"));
  const detailStr = isConn ? `Connected: ${dev}` : `Service running on https://${info.lan_ip || "LAN"}:${info.port || 8990} — Scan QR code`;
  updateMobileScannerStatusUI(st, detailStr, isConn, dev, info.last_heartbeat);

  const logEl = document.getElementById("mobile-scanner-log");
  if (logEl && logEl.children.length === 0) {
    appendMobileScannerLog(`Service started on https://${info.lan_ip || "LAN"}:${info.port || 8990}`);
    if (isConn) {
      appendMobileScannerLog(`Phone connected: ${dev}`);
    } else {
      appendMobileScannerLog("Waiting for phone connection...");
    }
  }

  if (qrBox && info.url && typeof qrcode !== "undefined") {
    try {
      const qr = qrcode(0, "M");
      qr.addData(info.url);
      qr.make();
      qrBox.innerHTML = qr.createSvgTag({ cellSize: 4, margin: 4 });
      const svg = qrBox.querySelector("svg");
      if (svg) {
        svg.style.width = "100%";
        svg.style.height = "100%";
        svg.style.display = "block";
      }
    } catch (e) {
      qrBox.innerHTML = `<span style="font-size:10px; color:#ef4444;">QR Error: ${e.message}</span>`;
    }
  }
}

function appendMobileScannerLog(msg) {
  const logEl = document.getElementById("mobile-scanner-log");
  if (!logEl) return;
  const now = new Date();
  const time = now.toTimeString().split(" ")[0]; // HH:MM:SS format
  const line = document.createElement("div");
  line.textContent = `[${time}] ${msg}`;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

function showMedicalVerificationModal(itemData) {
  if (!modalMedVerification) return;
  const nameEl = document.getElementById("med-verify-product-name");
  const codeEl = document.getElementById("med-verify-barcode");
  const priceEl = document.getElementById("med-verify-price");
  const taxEl = document.getElementById("med-verify-tax");
  const titleEl = document.getElementById("med-verify-banner-title");
  const textEl = document.getElementById("med-verify-banner-text");

  const bcode = (itemData && (itemData.matched_barcode || itemData.barcode || itemData.alias)) || "Unknown";
  const name = (itemData && itemData.name) || "Unknown Product";

  if (nameEl) nameEl.textContent = name;
  if (codeEl) codeEl.textContent = bcode;
  if (priceEl) priceEl.textContent = `Not Configured (₹ ${parseFloat((itemData && (itemData.sales_price || itemData.price)) || 0).toFixed(2)})`;
  if (taxEl) taxEl.textContent = (itemData && (itemData.tax_category || itemData.taxCategory)) || "Unconfigured (Verification Required)";

  if (bcode === "8909263004690") {
    if (titleEl) titleEl.textContent = "DEMO / UNVERIFIED MEDICAL RECORD DETECTED";
    if (textEl) textEl.innerHTML = `Barcode <strong>${bcode}</strong> is registered as a demo placeholder for <em>${escapeHtml(name)}</em>. Commercial sale is strictly blocked until packaging is verified.`;
  } else {
    if (titleEl) titleEl.textContent = "UNCONFIGURED PRICING & TAX DETECTED";
    if (textEl) textEl.innerHTML = `Product <strong>${escapeHtml(name)}</strong> (Barcode: <strong>${bcode}</strong>) has unconfigured price, MRP, or tax. Added to cart for inspection, but checkout is blocked until configured in Item Master.`;
  }

  modalMedVerification.style.display = "flex";
}
function closeMedicalVerificationModal() {
  if (modalMedVerification) {
    modalMedVerification.style.display = "none";
  }
}

function openSimulateScanModal() {
  if (!modalSimulateScan) return;
  modalSimulateScan.style.display = "flex";
  if (simBarcodeInput) {
    simBarcodeInput.value = "";
    setTimeout(() => simBarcodeInput.focus(), 50);
  }
}
function closeSimulateScanModal() {
  if (modalSimulateScan) modalSimulateScan.style.display = "none";
}

if (btnPosMobileScanner) {
  btnPosMobileScanner.addEventListener("click", openMobileScannerModal);
}
if (btnCloseMobileScanner) {
  btnCloseMobileScanner.addEventListener("click", closeMobileScannerModal);
}
if (btnDismissMobileScanner) {
  btnDismissMobileScanner.addEventListener("click", closeMobileScannerModal);
}
if (btnRevokeScannerToken) {
  btnRevokeScannerToken.addEventListener("click", () => {
    if (window.backend && window.backend.revokeMobileScannerToken) {
      window.backend.revokeMobileScannerToken((resp) => {
        try {
          const res = JSON.parse(resp);
          if (res.success && res.data) {
            renderMobileScannerInfo(res.data);
            appendMobileScannerLog("Pairing token revoked and regenerated.");
            showNotification("Pairing token regenerated. Please scan new QR code.");
          }
        } catch (e) {
          console.error("Token revoke error:", e);
        }
      });
    }
  });
}
if (btnCopyScannerUrl) {
  btnCopyScannerUrl.addEventListener("click", () => {
    const urlInput = document.getElementById("mobile-scanner-url-input");
    if (urlInput && urlInput.value) {
      navigator.clipboard.writeText(urlInput.value).then(() => {
        showNotification("Pairing URL copied to clipboard!");
      }).catch(() => {
        urlInput.select();
        document.execCommand("copy");
        showNotification("Pairing URL copied!");
      });
    }
  });
}
if (btnOpenScannerBrowser) {
  btnOpenScannerBrowser.addEventListener("click", () => {
    const urlInput = document.getElementById("mobile-scanner-url-input");
    if (urlInput && urlInput.value) {
      window.open(urlInput.value, "_blank");
    }
  });
}
if (btnClearScannerLog) {
  btnClearScannerLog.addEventListener("click", () => {
    const logEl = document.getElementById("mobile-scanner-log");
    if (logEl) logEl.innerHTML = "";
  });
}

// Demo Product Buttons in Mobile Scanner Modal
document.querySelectorAll(".btn-demo-test").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    const code = e.currentTarget.getAttribute("data-barcode");
    if (code) {
      handleBarcodeScan(code, true);
    }
  });
});

const btnScannerModalTestScan = document.getElementById("btn-scanner-modal-test-scan");
const inputScannerModalManualBarcode = document.getElementById("scanner-modal-manual-barcode");
if (btnScannerModalTestScan && inputScannerModalManualBarcode) {
  btnScannerModalTestScan.addEventListener("click", () => {
    const code = inputScannerModalManualBarcode.value.trim();
    if (code) {
      handleBarcodeScan(code, true);
      inputScannerModalManualBarcode.value = "";
    }
  });
  inputScannerModalManualBarcode.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const code = inputScannerModalManualBarcode.value.trim();
      if (code) {
        handleBarcodeScan(code, true);
        inputScannerModalManualBarcode.value = "";
      }
    }
  });
}

if (btnPosSimulateScan) {
  btnPosSimulateScan.addEventListener("click", openSimulateScanModal);
}
if (btnCloseSimulateScan) {
  btnCloseSimulateScan.addEventListener("click", closeSimulateScanModal);
}
if (btnCloseSimDialog) {
  btnCloseSimDialog.addEventListener("click", closeSimulateScanModal);
}
if (formSimulateScan) {
  formSimulateScan.addEventListener("submit", (e) => {
    e.preventDefault();
    const code = simBarcodeInput.value.trim();
    if (code) {
      handleBarcodeScan(code, true);
      closeSimulateScanModal();
    }
  });
}
document.querySelectorAll(".btn-sim-quick").forEach((btn) => {
  btn.addEventListener("click", (e) => {
    const code = e.currentTarget.getAttribute("data-code");
    if (code) {
      handleBarcodeScan(code, true);
      closeSimulateScanModal();
    }
  });
});

if (btnCloseMedVerification) {
  btnCloseMedVerification.addEventListener("click", closeMedicalVerificationModal);
}
if (btnAckMedVerification) {
  btnAckMedVerification.addEventListener("click", closeMedicalVerificationModal);
}

// Global Keyboard Navigation
window.addEventListener("keydown", (e) => {
  // Zoom hotkeys: Ctrl/Cmd + Plus/Minus/0
  if ((e.ctrlKey || e.metaKey) && (e.key === "+" || e.key === "=")) {
    e.preventDefault();
    ZoomController.zoomIn();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "-" || e.key === "_")) {
    e.preventDefault();
    ZoomController.zoomOut();
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "0") {
    e.preventDefault();
    ZoomController.resetZoom();
    return;
  }

  // Modals handle Esc
  if (modalLogin.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); closeLoginModal(); }
    return;
  }
  if (modalCreateCompany.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); closeCreateCompanyModal(); }
    return;
  }
  if (modalConfiguration.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); closeConfigurationModal(); }
    return;
  }
  if (modalPosCash && modalPosCash.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); modalPosCash.classList.remove("show"); }
    return;
  }
  if (modalReceiptPreview && modalReceiptPreview.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); modalReceiptPreview.classList.remove("show"); }
    return;
  }
  if (modalBackup && modalBackup.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); modalBackup.classList.remove("show"); }
    return;
  }
  if (modalReports && modalReports.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); modalReports.classList.remove("show"); }
    return;
  }
  if (modalDataMigration && modalDataMigration.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); modalDataMigration.classList.remove("show"); }
    return;
  }
  if (modalMobileScanner && modalMobileScanner.style.display === "flex") {
    if (e.key === "Escape") { e.preventDefault(); closeMobileScannerModal(); }
    return;
  }
  if (modalSimulateScan && modalSimulateScan.style.display === "flex") {
    if (e.key === "Escape") { e.preventDefault(); closeSimulateScanModal(); }
    return;
  }
  if (modalMedVerification && modalMedVerification.style.display === "flex") {
    if (e.key === "Escape") { e.preventDefault(); closeMedicalVerificationModal(); }
    return;
  }

  // View-specific hotkeys
  if (currentScreen === "view-login") {
    if (e.key === "Enter") {
      e.preventDefault();
      handleMainLoginSubmit();
    }
  } else if (currentScreen === "view-companies") {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(selectedIndex + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(selectedIndex - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      selectCompanyFromList();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-login");
    }
  } else if (currentScreen === "view-mode-selection") {
    if (e.key === "1" || e.key === "b" || e.key === "B") {
      e.preventDefault();
      enterCompanyDashboard(activeCompany);
    } else if (e.key === "2" || e.key === "f" || e.key === "F") {
      e.preventDefault();
      openFastBillingPos();
    } else if (e.key === "s" || e.key === "S") {
      e.preventDefault();
      openConfigurationModal();
    } else if (e.key === "Escape") {
      e.preventDefault();
      logoutUser();
    }
  } else if (currentScreen === "view-sales-voucher") {
    if (e.key === "F1") {
      e.preventDefault();
      openProductSearchModal("VOUCHER", 1);
    } else if (e.key === "F2") {
      e.preventDefault();
      handleSaveSalesVoucher();
    } else if (e.key === "F4") {
      e.preventDefault();
      recalculateVoucherTotals();
      showNotification("Tax recalculated.");
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-fast-billing") {
    if (e.key === "F1") {
      e.preventDefault();
      if (btnPosSearchItem) btnPosSearchItem.click();
    } else if (e.key === "F2") {
      e.preventDefault();
      if (btnPosHold) btnPosHold.click();
    } else if (e.key === "F3") {
      e.preventDefault();
      if (btnPosResume) btnPosResume.click();
    } else if (e.key === "F4") {
      e.preventDefault();
      openFastBillingNewBill();
    } else if (e.key === "F5") {
      e.preventDefault();
      openFastBillingHistory();
    } else if (e.key === "F7") {
      e.preventDefault();
      openFastBillingReprint();
    } else if (e.key === "F8") {
      e.preventDefault();
      if (btnPosPaySplit) btnPosPaySplit.click();
    } else if (e.key === "F9") {
      e.preventDefault();
      if (btnPosPayCash) btnPosPayCash.click();
    } else if (e.key === "F10") {
      e.preventDefault();
      if (btnPosPayUpi) btnPosPayUpi.click();
    } else if (e.key === "F12") {
      e.preventDefault();
      if (btnPosCheckoutPrint) btnPosCheckoutPrint.click();
    } else if (e.key === "Escape") {
      e.preventDefault();
      navigateAwayFromPos("view-mode-selection");
    }
  } else if (currentScreen === "view-fast-billing-history") {
    if (e.key === "F4") {
      e.preventDefault();
      openFastBillingNewBill();
    } else if (e.key === "F5") {
      e.preventDefault();
      renderFastBillingHistory();
    } else if (e.key === "Escape") {
      e.preventDefault();
      openFastBillingNewBill();
    }
  } else if (currentScreen === "view-fast-billing-print") {
    if (e.key === "F4" || e.key === "Escape") {
      e.preventDefault();
      returnFromPrintScreen();
    } else if (e.key === "Enter" || (e.ctrlKey && (e.key === "p" || e.key === "P"))) {
      e.preventDefault();
      triggerInvoicePrint();
    }
  } else if (currentScreen === "view-add-account-master") {
    if (e.key === "F2") {
      e.preventDefault();
      handleSaveAccountMaster();
    } else if (e.key === "F5") {
      e.preventDefault();
      showScreen("view-account-list");
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-account-list");
    }
  } else if (currentScreen === "view-account-list") {
    if (e.key === "F2") {
      e.preventDefault();
      openAddAccountMaster();
    } else if (e.key === "F5") {
      e.preventDefault();
      renderAccountMasterList();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-add-item-master") {
    if (e.key === "F2") {
      e.preventDefault();
      handleSaveItemMaster();
    } else if (e.key === "F5") {
      e.preventDefault();
      openProductsListView();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-items-list");
    }
  } else if (currentScreen === "view-items-list") {
    if (e.key === "F1") {
      e.preventDefault();
      if (itemsListSearch) itemsListSearch.focus();
    } else if (e.key === "F5") {
      e.preventDefault();
      renderProductsList();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-sales-list") {
    if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-purchase-entry") {
    if (e.key === "F1") {
      e.preventDefault();
      openProductSearchModal("PURCHASE");
    } else if (e.key === "F5") {
      e.preventDefault();
      showScreen("view-purchase-list");
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-purchase-list") {
    if (e.key === "F5") {
      e.preventDefault();
      renderPurchaseRegister();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-supplier-master") {
    if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-stock-summary") {
    if (e.key === "F5") {
      e.preventDefault();
      renderStockSummary();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-stock-adjustments") {
    if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-day-book") {
    if (e.key === "F5") {
      e.preventDefault();
      renderDayBookScreen();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-dashboard") {
    if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-mode-selection");
    }
  }
});

// =============================================================
// ENTERPRISE ERP: INVENTORY, PURCHASE, SUPPLIERS & ACCOUNTING
// =============================================================

let purchaseItemsData = [];
let cachedSuppliersList = [];
let cachedCatalogueItems = [];
let lastOcrExtractedData = null;

const SAMPLE_GST_INVOICE_TEXT = `TAX INVOICE
MADRAS CHEMICALS & CONSUMER GOODS DISTRIBUTORS
GSTIN: 33AABCM8942K1Z8
Address: 45 Mount Road, Guindy, Chennai - 600032
Invoice No: MCC/2026/8942
Date: 28-10-2026

Billed To:
ANTI MATRIX
GSTIN: 33AAAPL1234F1Z1

Line Items:
1. Levosalbutamol Inhaler 50mcg | HSN: 300490 | Qty: 20 Pcs | Rate: 120.00 | GST: 12% | Total: 2688.00
2. Hide & Seek Chocolate Biscuits 120g | HSN: 190531 | Qty: 50 Pcs | Rate: 28.00 | GST: 18% | Total: 1652.00
3. Milk Bikis Classic 100g | HSN: 190531 | Qty: 40 Pcs | Rate: 18.00 | GST: 18% | Total: 849.60

Subtotal: 4460.00
CGST: 364.80
SGST: 364.80
Grand Total: 5189.60`;

// --- Purchase Entry Screen ---
function initPurchaseEntryScreen() {
  if (!activeCompany) {
    alert("Please select and log in to a company first.");
    showScreen("view-companies");
    return;
  }

  isPurchaseModifyMode = false;
  currentModifyPurchaseVchId = null;
  const modIn = document.getElementById("pur-modify-vch-id");
  if (modIn) modIn.value = "";
  const titleEl = document.getElementById("purchase-entry-screen-title");
  if (titleEl) titleEl.textContent = "Add Purchase Voucher (Inward Goods)";
  
  const purDateInput = document.getElementById("pur-date");
  const purSupDateInput = document.getElementById("pur-supplier-inv-date");
  const todayStr = new Date().toISOString().slice(0, 10);
  if (purDateInput) purDateInput.value = todayStr;
  if (purSupDateInput) purSupDateInput.value = todayStr;

  const purSupInvNo = document.getElementById("pur-supplier-inv-no");
  if (purSupInvNo) purSupInvNo.value = "";
  const purNarration = document.getElementById("pur-narration");
  if (purNarration) purNarration.value = "";
  const purFreight = document.getElementById("pur-freight-exp");
  if (purFreight) purFreight.value = "0.00";
  const purHandling = document.getElementById("pur-handling-exp");
  if (purHandling) purHandling.value = "0.00";

  // Fetch Next Purchase Voucher Number
  if (window.backend && window.backend.getNextPurchaseVoucherNumber) {
    window.backend.getNextPurchaseVoucherNumber(activeCompany.id, "Main", (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && r.data) {
          const vchEl = document.getElementById("pur-vch-no");
          if (vchEl) vchEl.value = r.data;
        }
      } catch (e) {
        console.error("Error getting next purchase voucher no:", e);
      }
    });
  }

  // Load Suppliers & Catalogue
  loadSuppliersDropdown();
  loadCatalogueItemsForPurchase();

  // Reset Purchase items grid
  if (purchaseItemsData.length === 0) {
    purchaseItemsData = [ createEmptyPurchaseItem() ];
  }
  renderPurchaseGridRows();
  calcPurchaseTotals();

  setTimeout(() => {
    if (purSupInvNo) purSupInvNo.focus();
  }, 50);
}

function loadSuppliersDropdown(selectIdToSet) {
  if (!activeCompany || !window.backend || !window.backend.listSuppliers) return;
  window.backend.listSuppliers(activeCompany.id, "", (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        cachedSuppliersList = r.data;
        const selects = [
          document.getElementById("pur-supplier-select"),
          document.getElementById("pr-supplier-select")
        ];
        selects.forEach(sel => {
          if (!sel) return;
          const currentVal = selectIdToSet || sel.value;
          sel.innerHTML = '<option value="">-- Select Supplier (or Add New) --</option>';
          r.data.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s.id;
            opt.textContent = `${s.name} (${s.code || "SUP"}${s.gstin ? " - " + s.gstin : ""})`;
            sel.appendChild(opt);
          });
          if (currentVal) sel.value = currentVal;
        });
      }
    } catch (e) {
      console.error("Error loading suppliers:", e);
    }
  });
}

function loadCatalogueItemsForPurchase() {
  if (!activeCompany || !window.backend || !window.backend.searchItems) return;
  window.backend.searchItems(activeCompany.id, "", (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        cachedCatalogueItems = r.data;
        const selects = [
          document.getElementById("adj-item-select"),
          document.getElementById("trn-item-select"),
          document.getElementById("sr-item-select"),
          document.getElementById("pr-item-select")
        ];
        selects.forEach(sel => {
          if (!sel) return;
          const cur = sel.value;
          sel.innerHTML = '<option value="">-- Choose Catalogue Product --</option>';
          r.data.forEach(it => {
            const opt = document.createElement("option");
            opt.value = it.id;
            opt.textContent = `${it.name} [Barcode: ${it.barcode || "N/A"}] - ₹${parseFloat(it.sales_price || it.mrp || 0).toFixed(2)}`;
            sel.appendChild(opt);
          });
          if (cur) sel.value = cur;
        });
      }
    } catch (e) {
      console.error("Error loading catalogue items:", e);
    }
  });
}

function createEmptyPurchaseItem() {
  return {
    item_id: "",
    barcode: "",
    name: "",
    batch_no: "",
    expiry_date: "",
    qty: 1,
    free_qty: 0,
    unit: "Pcs",
    cost_rate: 0,
    discount_pct: 0,
    taxable_amount: 0,
    tax_rate: 18,
    cgst_amount: 0,
    sgst_amount: 0,
    igst_amount: 0,
    line_total: 0
  };
}

function calcPurchaseTotals() {
  let subtotal = 0;
  let totalCgst = 0;
  let totalSgst = 0;
  let totalIgst = 0;
  let totalQty = 0;

  purchaseItemsData.forEach(it => {
    const qty = parseFloat(it.qty) || 0;
    const freeQty = parseFloat(it.free_qty) || 0;
    const rate = parseFloat(it.cost_rate) || 0;
    const discPct = parseFloat(it.discount_pct) || 0;
    const taxRate = parseFloat(it.tax_rate) || 0;

    const gross = qty * rate;
    const discAmt = gross * (discPct / 100);
    const taxable = Math.max(0, gross - discAmt);
    const taxAmt = taxable * (taxRate / 100);
    const cgst = taxAmt / 2;
    const sgst = taxAmt / 2;
    const lineTotal = taxable + taxAmt;

    it.taxable_amount = taxable;
    it.cgst_amount = cgst;
    it.sgst_amount = sgst;
    it.line_total = lineTotal;

    subtotal += taxable;
    totalCgst += cgst;
    totalSgst += sgst;
    totalQty += (qty + freeQty);
  });

  const freight = parseFloat(document.getElementById("pur-freight-exp")?.value) || 0;
  const handling = parseFloat(document.getElementById("pur-handling-exp")?.value) || 0;
  const rawGrandTotal = subtotal + totalCgst + totalSgst + totalIgst + freight + handling;
  const roundedGrandTotal = Math.round(rawGrandTotal);
  const roundOff = roundedGrandTotal - rawGrandTotal;

  const subEl = document.getElementById("pur-subtotal-val");
  if (subEl) subEl.textContent = `₹ ${subtotal.toFixed(2)}`;
  const cgstEl = document.getElementById("pur-cgst-val");
  if (cgstEl) cgstEl.textContent = `₹ ${totalCgst.toFixed(2)}`;
  const sgstEl = document.getElementById("pur-sgst-val");
  if (sgstEl) sgstEl.textContent = `₹ ${totalSgst.toFixed(2)}`;
  const igstEl = document.getElementById("pur-igst-val");
  if (igstEl) igstEl.textContent = `₹ ${totalIgst.toFixed(2)}`;
  const roundEl = document.getElementById("pur-round-val");
  if (roundEl) roundEl.textContent = `${roundOff >= 0 ? "+" : ""}${roundOff.toFixed(2)}`;
  const grandEl = document.getElementById("pur-grand-total");
  if (grandEl) grandEl.textContent = `₹ ${roundedGrandTotal.toFixed(2)}`;
  const countEl = document.getElementById("pur-items-count-label");
  if (countEl) countEl.textContent = `Items: ${purchaseItemsData.length} | Total Qty: ${totalQty}`;
}

function renderPurchaseGridRows() {
  const tbody = document.getElementById("pur-items-tbody");
  if (!tbody) return;
  tbody.innerHTML = "";

  purchaseItemsData.forEach((it, idx) => {
    const tr = document.createElement("tr");
    tr.dataset.index = idx;
    tr.innerHTML = `
      <td style="text-align: center; font-weight: 700; color: #64748b;">${idx + 1}</td>
      <td><input type="text" class="pur-row-barcode" value="${escapeHtml(it.barcode || "")}" placeholder="Barcode" /></td>
      <td><input type="text" class="pur-row-name" value="${escapeHtml(it.name || "")}" placeholder="Type product name or scan..." /></td>
      <td><input type="text" class="pur-row-batch" value="${escapeHtml(it.batch_no || "")}" placeholder="Batch" /></td>
      <td><input type="number" class="pur-row-qty" value="${it.qty}" min="0.001" step="any" style="text-align: right; font-weight: 700;" /></td>
      <td><input type="number" class="pur-row-free-qty" value="${it.free_qty || 0}" min="0" step="any" style="text-align: right;" /></td>
      <td><input type="text" class="pur-row-unit" value="${escapeHtml(it.unit || "Pcs")}" style="text-align: center;" /></td>
      <td><input type="number" class="pur-row-rate" value="${(parseFloat(it.cost_rate) || 0).toFixed(2)}" min="0" step="0.01" style="text-align: right;" /></td>
      <td><input type="number" class="pur-row-disc" value="${parseFloat(it.discount_pct) || 0}" min="0" max="100" step="0.5" style="text-align: right;" /></td>
      <td style="text-align: right; font-weight: 600;" class="pur-row-taxable">₹ ${(parseFloat(it.taxable_amount) || 0).toFixed(2)}</td>
      <td>
        <select class="pur-row-tax-rate" style="width: 100%; border: 1px solid #cbd5e1; padding: 2px;">
          <option value="18" ${it.tax_rate == 18 ? "selected" : ""}>18%</option>
          <option value="12" ${it.tax_rate == 12 ? "selected" : ""}>12%</option>
          <option value="5" ${it.tax_rate == 5 ? "selected" : ""}>5%</option>
          <option value="28" ${it.tax_rate == 28 ? "selected" : ""}>28%</option>
          <option value="0" ${it.tax_rate == 0 ? "selected" : ""}>0%</option>
        </select>
      </td>
      <td style="text-align: right; font-weight: 700; color: #1e3a8a;" class="pur-row-total">₹ ${(parseFloat(it.line_total) || 0).toFixed(2)}</td>
      <td style="text-align: center;"><button type="button" class="btn-row-del" title="Delete Row">&times;</button></td>
    `;

    const barcodeInput = tr.querySelector(".pur-row-barcode");
    const nameInput = tr.querySelector(".pur-row-name");
    const qtyInput = tr.querySelector(".pur-row-qty");
    const freeQtyInput = tr.querySelector(".pur-row-free-qty");
    const rateInput = tr.querySelector(".pur-row-rate");
    const discInput = tr.querySelector(".pur-row-disc");
    const taxSelect = tr.querySelector(".pur-row-tax-rate");
    const unitInput = tr.querySelector(".pur-row-unit");
    const batchInput = tr.querySelector(".pur-row-batch");
    const btnDel = tr.querySelector(".btn-row-del");

    barcodeInput.addEventListener("change", (e) => {
      const val = e.target.value.trim();
      it.barcode = val;
      if (val && cachedCatalogueItems.length > 0) {
        const found = cachedCatalogueItems.find(p => (p.barcode || "").toLowerCase() === val.toLowerCase());
        if (found) {
          it.item_id = found.id;
          it.name = found.name;
          it.unit = found.unit || it.unit;
          if (found.purchase_price) it.cost_rate = parseFloat(found.purchase_price);
          nameInput.value = it.name;
          unitInput.value = it.unit;
          rateInput.value = it.cost_rate.toFixed(2);
        }
      }
      calcPurchaseTotals();
    });

    nameInput.addEventListener("change", (e) => {
      it.name = e.target.value.trim();
      if (!it.item_id && cachedCatalogueItems.length > 0) {
        const found = cachedCatalogueItems.find(p => p.name.toLowerCase() === it.name.toLowerCase());
        if (found) {
          it.item_id = found.id;
          it.barcode = found.barcode || it.barcode;
          it.unit = found.unit || it.unit;
          if (found.purchase_price) it.cost_rate = parseFloat(found.purchase_price);
          barcodeInput.value = it.barcode;
          unitInput.value = it.unit;
          rateInput.value = it.cost_rate.toFixed(2);
        }
      }
      calcPurchaseTotals();
    });

    qtyInput.addEventListener("input", (e) => {
      it.qty = parseFloat(e.target.value) || 0;
      calcPurchaseTotals();
      tr.querySelector(".pur-row-taxable").textContent = `₹ ${it.taxable_amount.toFixed(2)}`;
      tr.querySelector(".pur-row-total").textContent = `₹ ${it.line_total.toFixed(2)}`;
    });

    freeQtyInput.addEventListener("input", (e) => {
      it.free_qty = parseFloat(e.target.value) || 0;
      calcPurchaseTotals();
    });

    rateInput.addEventListener("input", (e) => {
      it.cost_rate = parseFloat(e.target.value) || 0;
      calcPurchaseTotals();
      tr.querySelector(".pur-row-taxable").textContent = `₹ ${it.taxable_amount.toFixed(2)}`;
      tr.querySelector(".pur-row-total").textContent = `₹ ${it.line_total.toFixed(2)}`;
    });

    discInput.addEventListener("input", (e) => {
      it.discount_pct = parseFloat(e.target.value) || 0;
      calcPurchaseTotals();
      tr.querySelector(".pur-row-taxable").textContent = `₹ ${it.taxable_amount.toFixed(2)}`;
      tr.querySelector(".pur-row-total").textContent = `₹ ${it.line_total.toFixed(2)}`;
    });

    taxSelect.addEventListener("change", (e) => {
      it.tax_rate = parseFloat(e.target.value) || 0;
      calcPurchaseTotals();
      tr.querySelector(".pur-row-taxable").textContent = `₹ ${it.taxable_amount.toFixed(2)}`;
      tr.querySelector(".pur-row-total").textContent = `₹ ${it.line_total.toFixed(2)}`;
    });

    unitInput.addEventListener("change", (e) => { it.unit = e.target.value; });
    batchInput.addEventListener("change", (e) => { it.batch_no = e.target.value; });

    btnDel.addEventListener("click", () => {
      purchaseItemsData.splice(idx, 1);
      if (purchaseItemsData.length === 0) {
        purchaseItemsData.push(createEmptyPurchaseItem());
      }
      renderPurchaseGridRows();
      calcPurchaseTotals();
    });

    tbody.appendChild(tr);
  });
}

function postPurchaseVoucher() {
  if (!activeCompany) return;
  const supplierSelect = document.getElementById("pur-supplier-select");
  const supplierId = supplierSelect ? supplierSelect.value : "";
  const supplierName = supplierSelect && supplierSelect.selectedOptions[0] ? supplierSelect.selectedOptions[0].textContent.split(" (")[0] : "";
  const supInvNo = document.getElementById("pur-supplier-inv-no")?.value.trim();
  const supInvDate = document.getElementById("pur-supplier-inv-date")?.value;
  const purDate = document.getElementById("pur-date")?.value;
  const series = document.getElementById("pur-series")?.value || "Main";
  const godownId = document.getElementById("pur-godown-select")?.value || "GODOWN-MAIN";
  const paymentMode = document.getElementById("pur-payment-mode")?.value || "CREDIT";
  const freight = parseFloat(document.getElementById("pur-freight-exp")?.value) || 0;
  const handling = parseFloat(document.getElementById("pur-handling-exp")?.value) || 0;
  const narration = document.getElementById("pur-narration")?.value.trim() || "";

  if (!supplierId) {
    alert("Please select a Supplier for this purchase voucher.");
    if (supplierSelect) supplierSelect.focus();
    return;
  }
  if (!supInvNo) {
    alert("Please enter the Supplier Bill / Invoice Number.");
    document.getElementById("pur-supplier-inv-no")?.focus();
    return;
  }

  const validItems = purchaseItemsData.filter(it => it.name && (parseFloat(it.qty) > 0 || parseFloat(it.cost_rate) > 0));
  if (validItems.length === 0) {
    alert("Please add at least one product with name, quantity, and cost rate.");
    return;
  }

  const payload = {
    supplier_id: supplierId,
    supplier_name: supplierName,
    supplier_invoice_no: supInvNo,
    supplier_invoice_date: supInvDate,
    voucher_date: purDate,
    series: series,
    godown_id: godownId,
    payment_mode: paymentMode,
    freight_charges: freight,
    handling_charges: handling,
    narration: narration,
    items: validItems.map(it => ({
      item_id: it.item_id || undefined,
      name: it.name,
      barcode: it.barcode || undefined,
      batch_no: it.batch_no || undefined,
      expiry_date: it.expiry_date || undefined,
      qty: parseFloat(it.qty) || 1,
      free_qty: parseFloat(it.free_qty) || 0,
      unit: it.unit || "Pcs",
      cost_rate: parseFloat(it.cost_rate) || 0,
      discount_pct: parseFloat(it.discount_pct) || 0,
      tax_rate: parseFloat(it.tax_rate) || 0,
      line_total: parseFloat(it.line_total) || 0
    }))
  };

  if (isPurchaseModifyMode && currentModifyPurchaseVchId) {
    if (window.backend && window.backend.modifyPurchaseVoucher) {
      window.backend.modifyPurchaseVoucher(activeCompany.id, currentModifyPurchaseVchId, JSON.stringify(payload), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
            showNotification(`Purchase Voucher ${r.data.vch_no} modified successfully! Inward inventory reconciled.`);
            isPurchaseModifyMode = false;
            currentModifyPurchaseVchId = null;
            const titleEl = document.getElementById("purchase-entry-screen-title");
            if (titleEl) titleEl.textContent = "Add Purchase Voucher (Inward Goods)";
            showScreen("view-purchase-list");
          } else {
            alert(`Failed to modify purchase voucher: ${r.error}`);
          }
        } catch (e) {
          alert(`Error: ${e.message}`);
        }
      });
    }
    return;
  }

  if (window.backend && window.backend.createPurchaseVoucher) {
    window.backend.createPurchaseVoucher(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          showNotification(`Purchase Voucher ${r.data.vch_no} posted successfully! Inward inventory updated.`);
          if (confirm(`Purchase ${r.data.vch_no} saved successfully!\nInventory and Accounts updated.\n\nOpen Purchase Register?`)) {
            showScreen("view-purchase-list");
          } else {
            purchaseItemsData = [ createEmptyPurchaseItem() ];
            initPurchaseEntryScreen();
          }
        } else {
          alert(`Failed to post purchase voucher: ${r.error}`);
        }
      } catch (e) {
        console.error("Error creating purchase voucher:", e);
        alert(`Error: ${e.message}`);
      }
    });
  }
}

function openModifyPurchaseVoucher(vchId) {
  if (!activeCompany) return;
  const loadVoucher = (vch) => {
    if (!vch) {
      alert("Purchase voucher not found.");
      return;
    }
    isPurchaseModifyMode = true;
    currentModifyPurchaseVchId = vch.id || vchId;
    const modIn = document.getElementById("pur-modify-vch-id");
    if (modIn) modIn.value = currentModifyPurchaseVchId;

    const supplierSelect = document.getElementById("pur-supplier-select");
    if (supplierSelect && vch.supplier_id) supplierSelect.value = vch.supplier_id;
    const supInvNo = document.getElementById("pur-supplier-inv-no");
    if (supInvNo) supInvNo.value = vch.supplier_invoice_no || "";
    const supInvDate = document.getElementById("pur-supplier-inv-date");
    if (supInvDate && vch.supplier_invoice_date) supInvDate.value = vch.supplier_invoice_date;
    const purDate = document.getElementById("pur-date");
    if (purDate && vch.voucher_date) purDate.value = vch.voucher_date;
    const series = document.getElementById("pur-series");
    if (series && vch.series) series.value = vch.series;
    const paymentMode = document.getElementById("pur-payment-mode");
    if (paymentMode && vch.payment_mode) paymentMode.value = vch.payment_mode;
    const freight = document.getElementById("pur-freight-exp");
    if (freight) freight.value = vch.freight_charges || "0";
    const handling = document.getElementById("pur-handling-exp");
    if (handling) handling.value = vch.handling_charges || "0";
    const narration = document.getElementById("pur-narration");
    if (narration) narration.value = vch.narration || "";

    const titleEl = document.getElementById("purchase-entry-screen-title");
    if (titleEl) titleEl.textContent = `Modify Purchase Voucher: ${vch.vch_no}`;

    if (Array.isArray(vch.items) && vch.items.length > 0) {
      purchaseItemsData = vch.items.map(it => ({
        item_id: it.item_id || "",
        barcode: it.barcode || "",
        name: it.name || "",
        batch_no: it.batch_no || "",
        expiry_date: it.expiry_date || "",
        qty: parseFloat(it.qty) || 1,
        free_qty: parseFloat(it.free_qty) || 0,
        unit: it.unit || "Pcs",
        cost_rate: parseFloat(it.cost_rate) || 0,
        discount_pct: parseFloat(it.discount_pct) || 0,
        tax_rate: parseFloat(it.tax_rate) || 0,
        taxable_amount: parseFloat(it.taxable_amount) || 0,
        tax_amount: parseFloat(it.tax_amount) || 0,
        line_total: parseFloat(it.line_total) || 0
      }));
    } else {
      purchaseItemsData = [ createEmptyPurchaseItem() ];
    }
    renderPurchaseGridRows();
    calcPurchaseTotals();
    showScreen("view-purchase-entry");
  };

  if (window.backend && window.backend.listPurchaseVouchers) {
    window.backend.listPurchaseVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const found = r.data.find(v => v.id === vchId || v.vch_no === vchId);
          loadVoucher(found);
          return;
        }
      } catch (e) {}
    });
  }
}

// --- Purchase Register ---
function renderPurchaseRegister() {
  if (!activeCompany || !window.backend || !window.backend.listPurchaseVouchers) return;
  const tbody = document.getElementById("pur-register-tbody");
  const emptyMsg = document.getElementById("pur-register-empty");
  const countLabel = document.getElementById("pur-register-count-label");
  const totalValEl = document.getElementById("pur-register-total-val");

  window.backend.listPurchaseVouchers(activeCompany.id, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        if (r.data.length === 0) {
          if (tbody) tbody.innerHTML = "";
          if (emptyMsg) emptyMsg.style.display = "block";
          if (countLabel) countLabel.textContent = "Total Vouchers: 0";
          if (totalValEl) totalValEl.textContent = "₹ 0.00";
          return;
        }

        if (emptyMsg) emptyMsg.style.display = "none";
        if (countLabel) countLabel.textContent = `Total Vouchers: ${r.data.length}`;
        let totalVal = 0;

        if (tbody) {
          tbody.innerHTML = "";
          r.data.forEach((vch, idx) => {
            const netAmt = parseFloat(vch.grand_total) || 0;
            totalVal += netAmt;
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center;">${idx + 1}</td>
              <td>${vch.voucher_date || vch.created_at?.slice(0, 10)}</td>
              <td style="font-weight: 700; color: #1e3a8a;">${vch.vch_no}</td>
              <td style="font-weight: 600;">${vch.supplier_invoice_no}</td>
              <td>${escapeHtml(vch.supplier_name || "Supplier")}</td>
              <td style="text-align: center;">${vch.item_count || "-"}</td>
              <td style="text-align: right;">₹ ${(parseFloat(vch.tax_amount) || 0).toFixed(2)}</td>
              <td style="text-align: right; font-weight: 800; color: #0f172a;">₹ ${netAmt.toFixed(2)}</td>
              <td style="text-align: center;"><span class="stock-badge-optimal">POSTED</span></td>
              <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn-classic pur-modify-btn" data-id="${vch.id}" style="padding: 2px 8px; font-size: 11px; margin-right: 4px;">Modify</button>
                <button type="button" class="btn-classic pur-view-btn" data-id="${vch.id}" style="padding: 2px 8px; font-size: 11px; margin-right: 4px;">View</button>
                <button type="button" class="btn-classic pur-print-btn" data-id="${vch.id}" style="padding: 2px 8px; font-size: 11px;" title="Print Purchase Inward Voucher">🖨️ Print</button>
              </td>
            `;

            tr.querySelector(".pur-modify-btn").addEventListener("click", (e) => {
              e.stopPropagation();
              openModifyPurchaseVoucher(vch.id);
            });

            tr.querySelector(".pur-view-btn").addEventListener("click", (e) => {
              e.stopPropagation();
              viewPurchaseVoucherDetails(vch.id);
            });

            const purPrintBtn = tr.querySelector(".pur-print-btn");
            if (purPrintBtn) {
              purPrintBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                openFastBillingPrint(vch.id, vch, "view-purchase-list", "purchase_invoice");
              });
            }

            tr.addEventListener("dblclick", () => {
              openModifyPurchaseVoucher(vch.id);
            });

            tbody.appendChild(tr);
          });
        }
        if (totalValEl) totalValEl.textContent = `₹ ${totalVal.toFixed(2)}`;
      }
    } catch (e) {
      console.error("Error listing purchase vouchers:", e);
    }
  });
}

function viewPurchaseVoucherDetails(voucherId) {
  if (!activeCompany || !window.backend || !window.backend.getPurchaseVoucherDetails) return;
  window.backend.getPurchaseVoucherDetails(activeCompany.id, voucherId, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && r.data) {
        openFastBillingPrint(voucherId, r.data, "view-purchase-list", "purchase_invoice");
      }
    } catch (e) {
      console.error("Error viewing voucher details:", e);
    }
  });
}

// --- Supplier Master ---
function renderSupplierMaster(searchQuery = "") {
  if (!activeCompany || !window.backend || !window.backend.listSuppliers) return;
  const tbody = document.getElementById("supplier-master-tbody");
  const emptyMsg = document.getElementById("supplier-master-empty");
  const countLabel = document.getElementById("supplier-master-count-label");
  const totalOutEl = document.getElementById("supplier-master-total-outstanding");

  window.backend.listSuppliers(activeCompany.id, searchQuery, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        cachedSuppliersList = r.data;
        if (r.data.length === 0) {
          if (tbody) tbody.innerHTML = "";
          if (emptyMsg) emptyMsg.style.display = "block";
          if (countLabel) countLabel.textContent = "Total Suppliers: 0";
          if (totalOutEl) totalOutEl.textContent = "₹ 0.00";
          return;
        }

        if (emptyMsg) emptyMsg.style.display = "none";
        if (countLabel) countLabel.textContent = `Total Suppliers: ${r.data.length}`;
        let totalOut = 0;

        if (tbody) {
          tbody.innerHTML = "";
          r.data.forEach((sup, idx) => {
            const bal = parseFloat(sup.current_balance) || 0;
            totalOut += bal;
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center;">${idx + 1}</td>
              <td style="font-weight: 700; color: #0f766e;">${escapeHtml(sup.code || "")}</td>
              <td style="font-weight: 700;">${escapeHtml(sup.name)}</td>
              <td>${escapeHtml(sup.gstin || "-")}</td>
              <td>${escapeHtml(sup.phone || "-")}</td>
              <td>${escapeHtml(sup.city ? (sup.city + ", " + (sup.state || "")) : (sup.state || "-"))}</td>
              <td style="text-align: right;">₹ ${(parseFloat(sup.credit_limit) || 0).toFixed(2)}</td>
              <td style="text-align: right; font-weight: 800; color: ${bal > 0 ? '#b91c1c' : '#15803d'};">₹ ${bal.toFixed(2)} Cr</td>
              <td style="text-align: center; white-space: nowrap;">
                <button type="button" class="btn-classic sup-btn-edit" data-id="${sup.id}" style="padding: 2px 8px; font-size: 11px;">Edit</button>
                <button type="button" class="btn-classic sup-btn-ledger" data-id="${sup.id}" style="padding: 2px 8px; font-size: 11px; font-weight: 700; color: #0f766e;">Statement</button>
              </td>
            `;

            tr.querySelector(".sup-btn-edit").addEventListener("click", () => {
              openSupplierFormModal(sup);
            });
            tr.querySelector(".sup-btn-ledger").addEventListener("click", () => {
              openSupplierLedgerModal(sup);
            });

            tbody.appendChild(tr);
          });
        }
        if (totalOutEl) totalOutEl.textContent = `₹ ${totalOut.toFixed(2)}`;
      }
    } catch (e) {
      console.error("Error rendering supplier master:", e);
    }
  });
}

function openSupplierFormModal(sup = null) {
  const modal = document.getElementById("modal-supplier-form");
  if (!modal) return;
  modal.style.display = "flex";

  const title = document.getElementById("modal-supplier-title");
  const idInput = document.getElementById("sup-form-id");
  const codeInput = document.getElementById("sup-form-code");
  const nameInput = document.getElementById("sup-form-name");
  const gstinInput = document.getElementById("sup-form-gstin");
  const panInput = document.getElementById("sup-form-pan");
  const phoneInput = document.getElementById("sup-form-phone");
  const emailInput = document.getElementById("sup-form-email");
  const addressInput = document.getElementById("sup-form-address");
  const cityInput = document.getElementById("sup-form-city");
  const stateInput = document.getElementById("sup-form-state");
  const creditLimitInput = document.getElementById("sup-form-credit-limit");
  const opBalInput = document.getElementById("sup-form-opening-balance");

  if (sup) {
    if (title) title.textContent = "Modify Supplier Master";
    if (idInput) idInput.value = sup.id || "";
    if (codeInput) codeInput.value = sup.code || "";
    if (nameInput) nameInput.value = sup.name || "";
    if (gstinInput) gstinInput.value = sup.gstin || "";
    if (panInput) panInput.value = sup.pan || "";
    if (phoneInput) phoneInput.value = sup.phone || "";
    if (emailInput) emailInput.value = sup.email || "";
    if (addressInput) addressInput.value = sup.address || "";
    if (cityInput) cityInput.value = sup.city || "";
    if (stateInput) stateInput.value = sup.state || "Tamilnadu";
    if (creditLimitInput) creditLimitInput.value = sup.credit_limit || 0;
    if (opBalInput) opBalInput.value = sup.opening_balance || 0;
  } else {
    if (title) title.textContent = "Add New Supplier Master";
    if (idInput) idInput.value = "";
    if (codeInput) codeInput.value = "";
    if (nameInput) nameInput.value = "";
    if (gstinInput) gstinInput.value = "";
    if (panInput) panInput.value = "";
    if (phoneInput) phoneInput.value = "";
    if (emailInput) emailInput.value = "";
    if (addressInput) addressInput.value = "";
    if (cityInput) cityInput.value = "";
    if (stateInput) stateInput.value = "Tamilnadu";
    if (creditLimitInput) creditLimitInput.value = "0.00";
    if (opBalInput) opBalInput.value = "0.00";
  }

  setTimeout(() => {
    if (nameInput) nameInput.focus();
  }, 50);
}

function saveSupplierMaster() {
  if (!activeCompany) return;
  const name = document.getElementById("sup-form-name")?.value.trim();
  if (!name) {
    alert("Please enter the Supplier / Business Name.");
    document.getElementById("sup-form-name")?.focus();
    return;
  }

  const payload = {
    id: document.getElementById("sup-form-id")?.value || undefined,
    code: document.getElementById("sup-form-code")?.value.trim() || undefined,
    name: name,
    gstin: document.getElementById("sup-form-gstin")?.value.trim().toUpperCase() || undefined,
    pan: document.getElementById("sup-form-pan")?.value.trim().toUpperCase() || undefined,
    phone: document.getElementById("sup-form-phone")?.value.trim() || undefined,
    email: document.getElementById("sup-form-email")?.value.trim() || undefined,
    address: document.getElementById("sup-form-address")?.value.trim() || undefined,
    city: document.getElementById("sup-form-city")?.value.trim() || undefined,
    state: document.getElementById("sup-form-state")?.value.trim() || "Tamilnadu",
    credit_limit: parseFloat(document.getElementById("sup-form-credit-limit")?.value) || 0,
    opening_balance: parseFloat(document.getElementById("sup-form-opening-balance")?.value) || 0
  };

  if (window.backend && window.backend.saveSupplier) {
    window.backend.saveSupplier(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          showNotification(`Supplier ${r.data.name} saved successfully!`);
          const modal = document.getElementById("modal-supplier-form");
          if (modal) modal.style.display = "none";
          loadSuppliersDropdown(r.data.id);
          renderSupplierMaster();
        } else {
          alert(`Error saving supplier: ${r.error}`);
        }
      } catch (e) {
        console.error("Error saving supplier:", e);
      }
    });
  }
}

function openSupplierLedgerModal(sup) {
  if (!activeCompany || !window.backend || !window.backend.getSupplierLedger) return;
  const modal = document.getElementById("modal-supplier-ledger");
  if (!modal) return;
  modal.style.display = "flex";

  document.getElementById("sup-ledger-name").textContent = sup.name;
  document.getElementById("sup-ledger-meta").textContent = `Code: ${sup.code || 'SUP'} | GSTIN: ${sup.gstin || 'Unregistered'} | Phone: ${sup.phone || '-'}`;

  const tbody = document.getElementById("sup-ledger-tbody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 16px;">Loading supplier ledger...</td></tr>';

  window.backend.getSupplierLedger(activeCompany.id, sup.id, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && r.data) {
        const data = r.data;
        document.getElementById("sup-ledger-balance").textContent = `₹ ${parseFloat(data.current_balance || 0).toFixed(2)} Cr`;
        if (tbody) {
          tbody.innerHTML = "";
          (data.transactions || []).forEach((trItem, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center;">${idx + 1}</td>
              <td>${trItem.date}</td>
              <td style="font-weight: 700; color: #0f766e;">${escapeHtml(trItem.voucher_no || "-")}</td>
              <td>${escapeHtml(trItem.ref_no || "-")}</td>
              <td>${escapeHtml(trItem.particulars)}</td>
              <td style="text-align: right; color: #15803d;">${trItem.debit > 0 ? "₹ " + trItem.debit.toFixed(2) : "-"}</td>
              <td style="text-align: right; color: #b91c1c; font-weight: 600;">${trItem.credit > 0 ? "₹ " + trItem.credit.toFixed(2) : "-"}</td>
              <td style="text-align: right; font-weight: 800;">₹ ${parseFloat(trItem.balance).toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      }
    } catch (e) {
      console.error("Error loading supplier ledger:", e);
    }
  });
}

// --- Centralized Stock Summary & Valuation ---
function renderStockSummary() {
  if (!activeCompany || !window.backend || !window.backend.getStockSummary) return;
  const tbody = document.getElementById("stock-summary-tbody");
  const emptyMsg = document.getElementById("stock-summary-empty");
  const searchInput = document.getElementById("stock-summary-search");
  const statusFilter = document.getElementById("stock-summary-filter-status");
  const query = searchInput ? searchInput.value.trim() : "";
  const filterVal = statusFilter ? statusFilter.value : "";

  window.backend.getStockSummary(activeCompany.id, "", query, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        let items = r.data;
        if (filterVal) {
          if (filterVal === "LOW_STOCK") {
            items = items.filter(it => it.status === "LOW_STOCK" || it.is_low_stock);
          } else {
            items = items.filter(it => it.status === filterVal);
          }
        }

        const totalSkusEl = document.getElementById("stock-summary-total-skus");
        const totalQtyEl = document.getElementById("stock-summary-total-qty");
        const lowCountEl = document.getElementById("stock-summary-low-count");
        const totalValEl = document.getElementById("stock-summary-total-valuation");

        let totalQty = 0;
        let totalValuation = 0;
        let lowCount = 0;

        if (items.length === 0) {
          if (tbody) tbody.innerHTML = "";
          if (emptyMsg) emptyMsg.style.display = "block";
          if (totalSkusEl) totalSkusEl.textContent = "Total SKUs: 0";
          if (totalQtyEl) totalQtyEl.textContent = "Total Stock Qty: 0";
          if (lowCountEl) lowCountEl.textContent = "Low Stock Alert: 0";
          if (totalValEl) totalValEl.textContent = "₹ 0.00";
          return;
        }

        if (emptyMsg) emptyMsg.style.display = "none";

        if (tbody) {
          tbody.innerHTML = "";
          items.forEach((it, idx) => {
            const closing = parseFloat(it.closing_stock) || 0;
            const wacRate = parseFloat(it.valuation_rate || it.wac_rate) || 0;
            const stockVal = parseFloat(it.stock_value) || 0;
            totalQty += closing;
            totalValuation += stockVal;

            let badgeHtml = '<span class="stock-badge-optimal">OPTIMAL</span>';
            if (it.status === "LOW_STOCK" || it.is_low_stock) {
              lowCount++;
              const thresholdStr = it.min_stock_alert_level ? ` (< ${it.min_stock_alert_level})` : '';
              badgeHtml = `<span class="stock-badge-low">LOW STOCK${thresholdStr}</span>`;
            } else if (it.status === "OUT_OF_STOCK") {
              lowCount++;
              badgeHtml = '<span class="stock-badge-out">OUT OF STOCK</span>';
            } else if (it.status === "NEGATIVE" || it.status === "NEGATIVE_STOCK") {
              lowCount++;
              badgeHtml = '<span class="stock-badge-negative">NEGATIVE</span>';
            }

            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td style="font-weight: 600;">${escapeHtml(it.barcode || it.sku || "-")}</td>
              <td style="font-weight: 700; color: #1e3a8a;">${escapeHtml(it.product_name || it.name)}</td>
              <td>${escapeHtml(it.category || "General")}</td>
              <td style="text-align: center;">${escapeHtml(it.unit || "Pcs")}</td>
              <td style="text-align: right; color: #64748b;">${it.opening_stock}</td>
              <td style="text-align: right; font-weight: 600; color: #166534;">+${it.purchase_inward ?? it.inward_qty ?? 0}</td>
              <td style="text-align: right; font-weight: 600; color: #b91c1c;">-${it.sales_outward ?? it.outward_qty ?? 0}</td>
              <td style="text-align: right; font-weight: 800; font-size: 13px; color: ${closing <= 0 ? '#b91c1c' : '#0f172a'};">${closing}</td>
              <td style="text-align: right;">₹ ${wacRate.toFixed(2)}</td>
              <td style="text-align: right; font-weight: 700; color: #15803d;">₹ ${stockVal.toFixed(2)}</td>
              <td style="text-align: center;">${badgeHtml}</td>
              <td style="text-align: center;">
                <button type="button" class="btn-classic stock-btn-ledger" data-id="${it.item_id || it.id}" style="padding: 2px 8px; font-size: 11px; font-weight: 700; color: #15803d;">Ledger</button>
              </td>
            `;

            tr.querySelector(".stock-btn-ledger").addEventListener("click", () => {
              openStockItemLedgerModal(it);
            });
            tr.addEventListener("dblclick", () => {
              openStockItemLedgerModal(it);
            });

            tbody.appendChild(tr);
          });
        }

        if (totalSkusEl) totalSkusEl.textContent = `Total SKUs: ${items.length}`;
        if (totalQtyEl) totalQtyEl.textContent = `Total Stock Qty: ${totalQty}`;
        if (lowCountEl) lowCountEl.textContent = `Low Stock Alert: ${lowCount}`;
        if (totalValEl) totalValEl.textContent = `₹ ${totalValuation.toFixed(2)}`;
      }
    } catch (e) {
      console.error("Error loading stock summary:", e);
    }
  });
}

function openStockItemLedgerModal(it) {
  if (!activeCompany || !window.backend || !window.backend.getStockItemLedger) return;
  const modal = document.getElementById("modal-stock-item-ledger");
  if (!modal) return;
  modal.style.display = "flex";

  document.getElementById("stock-ledger-item-name").textContent = it.name;
  document.getElementById("stock-ledger-item-meta").textContent = `Barcode: ${it.barcode || 'N/A'} | Unit: ${it.unit || 'Pcs'} | Category: ${it.category || 'General'}`;

  const tbody = document.getElementById("stock-item-ledger-tbody");
  if (tbody) tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 16px;">Loading item ledger movements...</td></tr>';

  window.backend.getStockItemLedger(activeCompany.id, it.id, "", (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && r.data) {
        const ledger = r.data;
        document.getElementById("stock-ledger-closing-bal").textContent = `${ledger.closing_stock || 0} ${it.unit || 'Pcs'}`;
        if (tbody) {
          tbody.innerHTML = "";
          (ledger.entries || []).forEach((row, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center;">${idx + 1}</td>
              <td>${row.date}</td>
              <td><span class="stock-badge-optimal" style="background: #f1f5f9; color: #1e3a8a;">${escapeHtml(row.voucher_type)}</span></td>
              <td style="font-weight: 700;">${escapeHtml(row.voucher_no || "-")}</td>
              <td style="text-align: right; color: #166534; font-weight: 700;">${row.inward_qty > 0 ? "+" + row.inward_qty : "-"}</td>
              <td style="text-align: right; color: #b91c1c; font-weight: 700;">${row.outward_qty > 0 ? "-" + row.outward_qty : "-"}</td>
              <td style="text-align: right; font-weight: 800; font-size: 13px;">${row.balance}</td>
              <td style="font-size: 11px; color: #64748b;">${escapeHtml(row.remarks || "-")}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      }
    } catch (e) {
      console.error("Error loading stock item ledger:", e);
    }
  });
}

// --- Stock Adjustments & Godown Transfers ---
function initStockAdjustmentsScreen() {
  if (!activeCompany) return;
  const today = new Date().toISOString().slice(0, 10);
  const adjDate = document.getElementById("adj-date");
  if (adjDate) adjDate.value = today;
  const trnDate = document.getElementById("trn-date");
  if (trnDate) trnDate.value = today;

  loadCatalogueItemsForPurchase();

  const adjItemSelect = document.getElementById("adj-item-select");
  const adjQty = document.getElementById("adj-qty");
  const adjType = document.getElementById("adj-type");

  function refreshAdjStockPreview() {
    if (!adjItemSelect || !adjItemSelect.value) {
      document.getElementById("adj-current-stock-disp").textContent = "0";
      document.getElementById("adj-new-stock-disp").textContent = "0";
      return;
    }
    const it = cachedCatalogueItems.find(p => p.id === adjItemSelect.value);
    const curStock = it ? parseFloat(it.stock_quantity ?? it.stockQty ?? 0) : 0;
    document.getElementById("adj-current-stock-disp").textContent = String(curStock);

    const qty = parseFloat(adjQty?.value) || 0;
    const type = adjType?.value;
    let newBal = curStock;
    if (type === "INCREASE") newBal = curStock + qty;
    else if (type === "PHYSICAL_COUNT") newBal = qty;
    else newBal = curStock - qty;

    document.getElementById("adj-new-stock-disp").textContent = String(newBal);
  }

  if (adjItemSelect) adjItemSelect.addEventListener("change", refreshAdjStockPreview);
  if (adjQty) adjQty.addEventListener("input", refreshAdjStockPreview);
  if (adjType) adjType.addEventListener("change", refreshAdjStockPreview);
}

function switchStockAdjTab(tab) {
  const tabBtnAdj = document.getElementById("tab-btn-stock-adj");
  const tabBtnTrn = document.getElementById("tab-btn-stock-transfer");
  const paneAdj = document.getElementById("tab-pane-stock-adj");
  const paneTrn = document.getElementById("tab-pane-stock-transfer");

  if (tab === "transfer") {
    if (tabBtnTrn) tabBtnTrn.classList.add("active");
    if (tabBtnAdj) tabBtnAdj.classList.remove("active");
    if (paneTrn) paneTrn.style.display = "block";
    if (paneAdj) paneAdj.style.display = "none";
  } else {
    if (tabBtnAdj) tabBtnAdj.classList.add("active");
    if (tabBtnTrn) tabBtnTrn.classList.remove("active");
    if (paneAdj) paneAdj.style.display = "block";
    if (paneTrn) paneTrn.style.display = "none";
  }
}

function postStockAdjustment() {
  if (!activeCompany || !window.backend || !window.backend.recordStockAdjustment) return;
  const itemId = document.getElementById("adj-item-select")?.value;
  const qty = parseFloat(document.getElementById("adj-qty")?.value) || 0;
  const type = document.getElementById("adj-type")?.value || "DAMAGE";
  const godownId = document.getElementById("adj-godown")?.value || "GODOWN-MAIN";
  const reason = document.getElementById("adj-reason")?.value.trim() || "Stock Adjustment";
  const dateStr = document.getElementById("adj-date")?.value || new Date().toISOString().slice(0, 10);

  if (!itemId) {
    alert("Please select a product for stock adjustment.");
    return;
  }
  if (qty <= 0) {
    alert("Please enter a valid adjustment quantity greater than 0.");
    return;
  }

  const payload = {
    adjustment_type: type,
    godown_id: godownId,
    item_id: itemId,
    quantity: qty,
    reason: reason,
    adjustment_date: dateStr
  };

  window.backend.recordStockAdjustment(activeCompany.id, JSON.stringify(payload), (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success) {
        showNotification("Stock adjustment recorded successfully!");
        if (confirm("Stock adjustment posted!\n\nView updated Stock Summary?")) {
          showScreen("view-stock-summary");
        } else {
          showScreen("view-dashboard");
        }
      } else {
        alert(`Error recording stock adjustment: ${r.error}`);
      }
    } catch (e) {
      console.error("Error posting stock adjustment:", e);
    }
  });
}

function postStockTransfer() {
  if (!activeCompany || !window.backend || !window.backend.recordStockTransfer) return;
  const fromGodown = document.getElementById("trn-from-godown")?.value;
  const toGodown = document.getElementById("trn-to-godown")?.value;
  const itemId = document.getElementById("trn-item-select")?.value;
  const qty = parseFloat(document.getElementById("trn-qty")?.value) || 0;
  const notes = document.getElementById("trn-notes")?.value.trim() || "Inter-Godown Transfer";
  const dateStr = document.getElementById("trn-date")?.value || new Date().toISOString().slice(0, 10);

  if (!itemId) {
    alert("Please select a product to transfer.");
    return;
  }
  if (qty <= 0) {
    alert("Please enter a transfer quantity greater than 0.");
    return;
  }
  if (fromGodown === toGodown) {
    alert("Source and destination godowns cannot be identical.");
    return;
  }

  const payload = {
    from_godown_id: fromGodown,
    to_godown_id: toGodown,
    item_id: itemId,
    quantity: qty,
    transfer_notes: notes,
    transfer_date: dateStr
  };

  window.backend.recordStockTransfer(activeCompany.id, JSON.stringify(payload), (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success) {
        showNotification("Stock transfer executed successfully!");
        if (confirm("Stock transfer posted!\n\nView updated Stock Summary?")) {
          showScreen("view-stock-summary");
        } else {
          showScreen("view-dashboard");
        }
      } else {
        alert(`Error executing stock transfer: ${r.error}`);
      }
    } catch (e) {
      console.error("Error posting stock transfer:", e);
    }
  });
}

// --- Day Book & Trial Balance ---
function renderDayBookScreen() {
  if (!activeCompany || !window.backend || !window.backend.getDayBook) return;
  const dateInput = document.getElementById("daybook-date-input");
  const bDate = dateInput?.value || new Date().toISOString().slice(0, 10);
  if (dateInput && !dateInput.value) dateInput.value = bDate;

  const tbody = document.getElementById("daybook-tbody");
  const emptyMsg = document.getElementById("daybook-empty");
  const countLabel = document.getElementById("daybook-count-label");
  const totalDebitEl = document.getElementById("daybook-total-debit");
  const totalCreditEl = document.getElementById("daybook-total-credit");

  window.backend.getDayBook(activeCompany.id, bDate, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data)) {
        if (r.data.length === 0) {
          if (tbody) tbody.innerHTML = "";
          if (emptyMsg) emptyMsg.style.display = "block";
          if (countLabel) countLabel.textContent = "Entries: 0";
          if (totalDebitEl) totalDebitEl.textContent = "₹ 0.00";
          if (totalCreditEl) totalCreditEl.textContent = "₹ 0.00";
          return;
        }

        if (emptyMsg) emptyMsg.style.display = "none";
        if (countLabel) countLabel.textContent = `Entries: ${r.data.length}`;
        let totalDebit = 0;
        let totalCredit = 0;

        if (tbody) {
          tbody.innerHTML = "";
          let lineIdx = 1;
          r.data.forEach(entry => {
            (entry.lines || []).forEach(l => {
              const dr = parseFloat(l.debit_amount) || 0;
              const cr = parseFloat(l.credit_amount) || 0;
              totalDebit += dr;
              totalCredit += cr;

              const tr = document.createElement("tr");
              tr.innerHTML = `
                <td style="text-align: center; color: #64748b;">${lineIdx++}</td>
                <td>${entry.entry_date}</td>
                <td style="font-weight: 700; color: #1e3a8a;">${escapeHtml(entry.voucher_number || "-")}</td>
                <td><span class="stock-badge-optimal" style="background: #e2e8f0; color: #334155;">${escapeHtml(entry.voucher_type)}</span></td>
                <td>
                  <strong style="color: ${dr > 0 ? '#1e3a8a' : '#15803d'};">${escapeHtml(l.account_name)}</strong>
                  ${entry.narration ? `<div style="font-size: 11px; color: #64748b;">${escapeHtml(entry.narration)}</div>` : ''}
                </td>
                <td style="text-align: right; font-weight: 700; color: #1e3a8a;">${dr > 0 ? "₹ " + dr.toFixed(2) : "-"}</td>
                <td style="text-align: right; font-weight: 700; color: #15803d;">${cr > 0 ? "₹ " + cr.toFixed(2) : "-"}</td>
              `;
              tbody.appendChild(tr);
            });
          });
        }

        if (totalDebitEl) totalDebitEl.textContent = `₹ ${totalDebit.toFixed(2)}`;
        if (totalCreditEl) totalCreditEl.textContent = `₹ ${totalCredit.toFixed(2)}`;
      }
    } catch (e) {
      console.error("Error rendering day book:", e);
    }
  });
}

function renderTrialBalanceScreen() {
  if (!activeCompany || !window.backend || !window.backend.getTrialBalance) return;
  const tbody = document.getElementById("trial-balance-tbody");
  const totalDebitEl = document.getElementById("tb-total-debit");
  const totalCreditEl = document.getElementById("tb-total-credit");
  const diffEl = document.getElementById("tb-difference");
  const badgeEl = document.getElementById("trial-balance-status-badge");

  window.backend.getTrialBalance(activeCompany.id, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && r.data) {
        const tb = r.data;
        if (tbody) {
          tbody.innerHTML = "";
          (tb.accounts || []).forEach((acc, idx) => {
            const deb = parseFloat(acc.debit) || 0;
            const cred = parseFloat(acc.credit) || 0;
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td style="font-weight: 700; color: #1e293b;">${escapeHtml(acc.account_name)}</td>
              <td><span style="font-size: 11px; color: #64748b; text-transform: uppercase;">${escapeHtml(acc.account_type || "Ledger")}</span></td>
              <td style="text-align: right; font-weight: 700; color: #1e3a8a;">${deb > 0 ? "₹ " + deb.toFixed(2) : "-"}</td>
              <td style="text-align: right; font-weight: 700; color: #15803d;">${cred > 0 ? "₹ " + cred.toFixed(2) : "-"}</td>
            `;
            tbody.appendChild(tr);
          });
        }

        const totalDebit = parseFloat(tb.total_debit) || 0;
        const totalCredit = parseFloat(tb.total_credit) || 0;
        const difference = parseFloat(tb.difference ?? Math.abs(totalDebit - totalCredit)) || 0;

        if (totalDebitEl) totalDebitEl.textContent = `₹ ${totalDebit.toFixed(2)}`;
        if (totalCreditEl) totalCreditEl.textContent = `₹ ${totalCredit.toFixed(2)}`;
        if (diffEl) diffEl.textContent = `₹ ${difference.toFixed(2)}`;

        if (badgeEl) {
          if (tb.is_balanced || difference < 0.01) {
            badgeEl.style.color = "#15803d";
            badgeEl.innerHTML = `<span>[BALANCED]</span> <span>Trial Balance is Balanced (Diff: ₹0.00)</span>`;
          } else {
            badgeEl.style.color = "#b91c1c";
            badgeEl.innerHTML = `<span>[OUT OF BALANCE]</span> <span>Trial Balance Out of Balance by ₹${difference.toFixed(2)}</span>`;
          }
        }
      }
    } catch (e) {
      console.error("Error rendering trial balance:", e);
    }
  });
}

function switchDayBookTab(tab) {
  const tabBtnDb = document.getElementById("tab-btn-daybook");
  const tabBtnTb = document.getElementById("tab-btn-trial-balance");
  const paneDb = document.getElementById("tab-pane-daybook");
  const paneTb = document.getElementById("tab-pane-trial-balance");

  if (tab === "trial-balance") {
    if (tabBtnTb) tabBtnTb.classList.add("active");
    if (tabBtnDb) tabBtnDb.classList.remove("active");
    if (paneTb) paneTb.style.display = "flex";
    if (paneDb) paneDb.style.display = "none";
    renderTrialBalanceScreen();
  } else {
    if (tabBtnDb) tabBtnDb.classList.add("active");
    if (tabBtnTb) tabBtnTb.classList.remove("active");
    if (paneDb) paneDb.style.display = "flex";
    if (paneTb) paneTb.style.display = "none";
    renderDayBookScreen();
  }
}

// --- Invoice Document Scanning & OCR ---
function openOcrModal() {
  const modal = document.getElementById("modal-invoice-ocr");
  if (modal) {
    modal.style.display = "flex";
    const rawText = document.getElementById("ocr-raw-text-input");
    if (rawText) rawText.value = "";
    const resPanel = document.getElementById("ocr-results-panel");
    if (resPanel) resPanel.style.display = "none";
  }
}

function runOcrExtraction() {
  if (!activeCompany || !window.backend || !window.backend.processInvoiceOcr) return;
  const rawTextEl = document.getElementById("ocr-raw-text-input");
  const fileInput = document.getElementById("ocr-file-input");
  let fileOrText = rawTextEl?.value.trim() || "";
  let fileName = "bill.pdf";

  if (fileInput && fileInput.files && fileInput.files[0]) {
    fileName = fileInput.files[0].name;
  }

  if (!fileOrText) {
    alert("Please upload a file, paste text, or click 'Load Sample GST Tax Invoice'.");
    return;
  }

  window.backend.processInvoiceOcr(activeCompany.id, fileOrText, fileName, (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && r.data) {
        lastOcrExtractedData = r.data;
        const resPanel = document.getElementById("ocr-results-panel");
        if (resPanel) resPanel.style.display = "block";

        document.getElementById("ocr-res-supplier").textContent = r.data.extracted_supplier_name || "Detected Supplier";
        document.getElementById("ocr-res-gstin").textContent = r.data.extracted_supplier_gstin || "N/A";
        document.getElementById("ocr-res-inv-no").textContent = r.data.extracted_invoice_no || "INV-001";
        document.getElementById("ocr-res-date").textContent = r.data.extracted_invoice_date || new Date().toISOString().slice(0, 10);
        document.getElementById("ocr-res-total").textContent = `₹ ${(parseFloat(r.data.extracted_total_amount) || 0).toFixed(2)}`;

        const tbody = document.getElementById("ocr-items-tbody");
        if (tbody) {
          tbody.innerHTML = "";
          (r.data.extracted_items || []).forEach((it, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center;">${idx + 1}</td>
              <td style="font-weight: 600;">${escapeHtml(it.description)}</td>
              <td style="color: #1e3a8a; font-weight: 700;">${it.matched_item_name ? escapeHtml(it.matched_item_name) : "(New Product / Custom)"}</td>
              <td style="text-align: right;">${it.qty}</td>
              <td style="text-align: center;">${escapeHtml(it.unit || "Pcs")}</td>
              <td style="text-align: right;">₹ ${(parseFloat(it.rate) || 0).toFixed(2)}</td>
              <td style="text-align: center;">${it.tax_rate}%</td>
              <td style="text-align: right; font-weight: 700;">₹ ${(parseFloat(it.line_total) || 0).toFixed(2)}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      } else {
        alert(`OCR extraction notice: ${r.error || "Unable to extract items"}`);
      }
    } catch (e) {
      console.error("Error processing OCR:", e);
    }
  });
}

function populatePurchaseVoucherFromOcr() {
  if (!lastOcrExtractedData) return;
  const modal = document.getElementById("modal-invoice-ocr");
  if (modal) modal.style.display = "none";

  showScreen("view-purchase-entry");

  const invNoEl = document.getElementById("pur-supplier-inv-no");
  if (invNoEl && lastOcrExtractedData.extracted_invoice_no) {
    invNoEl.value = lastOcrExtractedData.extracted_invoice_no;
  }
  const invDateEl = document.getElementById("pur-supplier-inv-date");
  if (invDateEl && lastOcrExtractedData.extracted_invoice_date) {
    invDateEl.value = lastOcrExtractedData.extracted_invoice_date;
  }

  if (Array.isArray(lastOcrExtractedData.extracted_items) && lastOcrExtractedData.extracted_items.length > 0) {
    purchaseItemsData = lastOcrExtractedData.extracted_items.map(it => ({
      item_id: it.matched_item_id || "",
      barcode: it.barcode || "",
      name: it.matched_item_name || it.description || "",
      batch_no: "",
      expiry_date: "",
      qty: parseFloat(it.qty) || 1,
      free_qty: 0,
      unit: it.unit || "Pcs",
      cost_rate: parseFloat(it.rate) || 0,
      discount_pct: 0,
      taxable_amount: (parseFloat(it.qty) || 1) * (parseFloat(it.rate) || 0),
      tax_rate: parseFloat(it.tax_rate) || 18,
      cgst_amount: 0,
      sgst_amount: 0,
      igst_amount: 0,
      line_total: parseFloat(it.line_total) || 0
    }));
  }

  renderPurchaseGridRows();
  calcPurchaseTotals();
  showNotification("Purchase voucher populated from scanned invoice! Ready for review.");
}

// --- Sales Returns & Purchase Returns ---
function openSalesReturnModal() {
  const modal = document.getElementById("modal-sales-return");
  if (!modal) return;
  loadCatalogueItemsForPurchase();
  modal.style.display = "flex";

  const itemSel = document.getElementById("sr-item-select");
  const qtyInput = document.getElementById("sr-qty");
  const rateInput = document.getElementById("sr-rate");
  const taxInput = document.getElementById("sr-tax-rate");
  const totalDisp = document.getElementById("sr-total-display");

  function calcSrTotal() {
    const q = parseFloat(qtyInput?.value) || 0;
    const r = parseFloat(rateInput?.value) || 0;
    const t = parseFloat(taxInput?.value) || 0;
    const gross = q * r;
    const tax = gross * (t / 100);
    const tot = gross + tax;
    if (totalDisp) totalDisp.textContent = `₹ ${tot.toFixed(2)}`;
  }

  if (itemSel) {
    itemSel.addEventListener("change", () => {
      const it = cachedCatalogueItems.find(p => p.id === itemSel.value);
      if (it && rateInput) {
        rateInput.value = (parseFloat(it.sales_price || it.mrp || 0)).toFixed(2);
      }
      calcSrTotal();
    });
  }
  if (qtyInput) qtyInput.addEventListener("input", calcSrTotal);
  if (rateInput) rateInput.addEventListener("input", calcSrTotal);
  if (taxInput) taxInput.addEventListener("input", calcSrTotal);
}

function postSalesReturn() {
  if (!activeCompany || !window.backend || !window.backend.createSalesReturn) return;
  const itemId = document.getElementById("sr-item-select")?.value;
  const custName = document.getElementById("sr-customer-name")?.value.trim() || "Walk-in Customer";
  const origInv = document.getElementById("sr-original-inv")?.value.trim() || "";
  const qty = parseFloat(document.getElementById("sr-qty")?.value) || 1;
  const rate = parseFloat(document.getElementById("sr-rate")?.value) || 0;
  const taxRate = parseFloat(document.getElementById("sr-tax-rate")?.value) || 18;
  const cond = document.getElementById("sr-stock-condition")?.value || "SALEABLE";
  const reason = document.getElementById("sr-reason")?.value.trim() || "Customer return";

  if (!itemId) {
    alert("Please select the product to return.");
    return;
  }

  const payload = {
    customer_name: custName,
    original_invoice_no: origInv,
    reason: reason,
    items: [{
      item_id: itemId,
      quantity: qty,
      rate: rate,
      tax_rate: taxRate,
      stock_condition: cond
    }]
  };

  window.backend.createSalesReturn(activeCompany.id, JSON.stringify(payload), (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success) {
        showNotification("Sales Return (Credit Note) posted! Stock restored.");
        const modal = document.getElementById("modal-sales-return");
        if (modal) modal.style.display = "none";
        renderStockSummary();
      } else {
        alert(`Error posting sales return: ${r.error}`);
      }
    } catch (e) {
      console.error("Error creating sales return:", e);
    }
  });
}

function openPurchaseReturnModal() {
  const modal = document.getElementById("modal-purchase-return");
  if (!modal) return;
  loadSuppliersDropdown();
  loadCatalogueItemsForPurchase();
  modal.style.display = "flex";

  const itemSel = document.getElementById("pr-item-select");
  const qtyInput = document.getElementById("pr-qty");
  const rateInput = document.getElementById("pr-rate");
  const taxInput = document.getElementById("pr-tax-rate");
  const totalDisp = document.getElementById("pr-total-display");

  function calcPrTotal() {
    const q = parseFloat(qtyInput?.value) || 0;
    const r = parseFloat(rateInput?.value) || 0;
    const t = parseFloat(taxInput?.value) || 0;
    const gross = q * r;
    const tax = gross * (t / 100);
    const tot = gross + tax;
    if (totalDisp) totalDisp.textContent = `₹ ${tot.toFixed(2)}`;
  }

  if (itemSel) {
    itemSel.addEventListener("change", () => {
      const it = cachedCatalogueItems.find(p => p.id === itemSel.value);
      if (it && rateInput) {
        rateInput.value = (parseFloat(it.purchase_price || 0)).toFixed(2);
      }
      calcPrTotal();
    });
  }
  if (qtyInput) qtyInput.addEventListener("input", calcPrTotal);
  if (rateInput) rateInput.addEventListener("input", calcPrTotal);
  if (taxInput) taxInput.addEventListener("input", calcPrTotal);
}

function postPurchaseReturn() {
  if (!activeCompany || !window.backend || !window.backend.createPurchaseReturn) return;
  const supplierId = document.getElementById("pr-supplier-select")?.value;
  const origBill = document.getElementById("pr-original-bill")?.value.trim() || "";
  const itemId = document.getElementById("pr-item-select")?.value;
  const qty = parseFloat(document.getElementById("pr-qty")?.value) || 1;
  const rate = parseFloat(document.getElementById("pr-rate")?.value) || 0;
  const taxRate = parseFloat(document.getElementById("pr-tax-rate")?.value) || 18;
  const reason = document.getElementById("pr-reason")?.value.trim() || "Goods returned to supplier";

  if (!supplierId) {
    alert("Please select the supplier for this purchase return.");
    return;
  }
  if (!itemId) {
    alert("Please select the product to return.");
    return;
  }

  const payload = {
    supplier_id: supplierId,
    supplier_invoice_no: origBill,
    reason: reason,
    items: [{
      item_id: itemId,
      quantity: qty,
      rate: rate,
      tax_rate: taxRate
    }]
  };

  window.backend.createPurchaseReturn(activeCompany.id, JSON.stringify(payload), (resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success) {
        showNotification("Purchase Return (Debit Note) posted! Stock and supplier balance adjusted.");
        const modal = document.getElementById("modal-purchase-return");
        if (modal) modal.style.display = "none";
        renderSupplierMaster();
        renderStockSummary();
      } else {
        alert(`Error posting purchase return: ${r.error}`);
      }
    } catch (e) {
      console.error("Error creating purchase return:", e);
    }
  });
}

function setupEnterpriseErpEventListeners() {
  // Navigation & Menubar Hooks
  const menuPurAdd = document.getElementById("menu-purchase-add");
  if (menuPurAdd) menuPurAdd.addEventListener("click", () => showScreen("view-purchase-entry"));

  const menuPurList = document.getElementById("menu-purchase-list");
  if (menuPurList) menuPurList.addEventListener("click", () => showScreen("view-purchase-list"));

  const menuDispPurReg = document.getElementById("menu-display-purchase-register");
  if (menuDispPurReg) menuDispPurReg.addEventListener("click", () => showScreen("view-purchase-list"));

  const menuAddSup = document.getElementById("menu-add-supplier-master");
  if (menuAddSup) menuAddSup.addEventListener("click", () => openSupplierFormModal());

  const menuListSup = document.getElementById("menu-list-supplier-master");
  if (menuListSup) menuListSup.addEventListener("click", () => showScreen("view-supplier-master"));

  const menuDispStock = document.getElementById("menu-display-stock");
  if (menuDispStock) menuDispStock.addEventListener("click", () => showScreen("view-stock-summary"));

  const menuDispDaybook = document.getElementById("menu-display-daybook");
  if (menuDispDaybook) menuDispDaybook.addEventListener("click", () => {
    showScreen("view-day-book");
    switchDayBookTab("daybook");
  });

  const menuDispTb = document.getElementById("menu-display-trial-balance");
  if (menuDispTb) menuDispTb.addEventListener("click", () => {
    showScreen("view-day-book");
    switchDayBookTab("trial-balance");
  });

  const menuSalesRet = document.getElementById("menu-sales-return");
  if (menuSalesRet) menuSalesRet.addEventListener("click", openSalesReturnModal);

  const menuPurRet = document.getElementById("menu-purchase-return");
  if (menuPurRet) menuPurRet.addEventListener("click", openPurchaseReturnModal);

  const menuStockTrn = document.getElementById("menu-stock-transfer");
  if (menuStockTrn) menuStockTrn.addEventListener("click", () => {
    showScreen("view-stock-adjustments");
    switchStockAdjTab("transfer");
  });

  const menuStockAdj = document.getElementById("menu-stock-adjustment");
  if (menuStockAdj) menuStockAdj.addEventListener("click", () => {
    showScreen("view-stock-adjustments");
    switchStockAdjTab("adj");
  });

  // Fast Billing POS ERP Ribbon Pills
  const btnPosQuickStock = document.getElementById("btn-pos-quick-stock");
  if (btnPosQuickStock) btnPosQuickStock.addEventListener("click", () => showScreen("view-stock-summary"));

  const btnPosQuickPur = document.getElementById("btn-pos-quick-purchase");
  if (btnPosQuickPur) btnPosQuickPur.addEventListener("click", () => showScreen("view-purchase-entry"));

  // Purchase Entry View Buttons
  const btnPurBack = document.getElementById("btn-pur-back-dash");
  if (btnPurBack) btnPurBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnPurClose = document.getElementById("btn-pur-close-top");
  if (btnPurClose) btnPurClose.addEventListener("click", () => showScreen("view-dashboard"));
  const btnPurQuickSup = document.getElementById("btn-pur-quick-add-supplier");
  if (btnPurQuickSup) btnPurQuickSup.addEventListener("click", () => openSupplierFormModal());
  const btnPurAddRow = document.getElementById("btn-pur-add-row");
  if (btnPurAddRow) btnPurAddRow.addEventListener("click", () => {
    purchaseItemsData.push(createEmptyPurchaseItem());
    renderPurchaseGridRows();
    calcPurchaseTotals();
  });
  const btnPurOpenOcr = document.getElementById("btn-pur-open-ocr");
  if (btnPurOpenOcr) btnPurOpenOcr.addEventListener("click", openOcrModal);
  const btnPurReset = document.getElementById("btn-pur-reset");
  if (btnPurReset) btnPurReset.addEventListener("click", () => {
    purchaseItemsData = [ createEmptyPurchaseItem() ];
    initPurchaseEntryScreen();
  });
  const btnPurRegNav = document.getElementById("btn-pur-register-nav");
  if (btnPurRegNav) btnPurRegNav.addEventListener("click", () => showScreen("view-purchase-list"));
  const btnPurSave = document.getElementById("btn-pur-save-post");
  if (btnPurSave) btnPurSave.addEventListener("click", postPurchaseVoucher);
  const btnPurSearchItem = document.getElementById("btn-pur-search-item");
  if (btnPurSearchItem) btnPurSearchItem.addEventListener("click", () => openProductSearchModal("PURCHASE"));

  // Barcode scanner input in Purchase Entry
  const purBarcodeInput = document.getElementById("pur-barcode-input");
  if (purBarcodeInput) {
    purBarcodeInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const code = purBarcodeInput.value.trim();
        if (!code) return;
        const found = cachedCatalogueItems.find(p => (p.barcode || "").toLowerCase() === code.toLowerCase() || p.name.toLowerCase().includes(code.toLowerCase()));
        if (found) {
          purchaseItemsData.push({
            item_id: found.id,
            barcode: found.barcode || code,
            name: found.name,
            batch_no: "",
            expiry_date: "",
            qty: 1,
            free_qty: 0,
            unit: found.unit || "Pcs",
            cost_rate: parseFloat(found.purchase_price || 0),
            discount_pct: 0,
            taxable_amount: parseFloat(found.purchase_price || 0),
            tax_rate: 18,
            cgst_amount: 0,
            sgst_amount: 0,
            igst_amount: 0,
            line_total: parseFloat(found.purchase_price || 0) * 1.18
          });
          showNotification(`Added ${found.name} to purchase voucher.`);
        } else {
          purchaseItemsData.push({
            ...createEmptyPurchaseItem(),
            barcode: code,
            name: `Item (${code})`
          });
          showNotification(`Added barcode ${code}. Enter details.`);
        }
        purBarcodeInput.value = "";
        renderPurchaseGridRows();
        calcPurchaseTotals();
      }
    });
  }

  const purFreight = document.getElementById("pur-freight-exp");
  if (purFreight) purFreight.addEventListener("input", calcPurchaseTotals);
  const purHandling = document.getElementById("pur-handling-exp");
  if (purHandling) purHandling.addEventListener("input", calcPurchaseTotals);

  // Purchase Register Buttons
  const btnPurListBack = document.getElementById("btn-pur-list-back");
  if (btnPurListBack) btnPurListBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnPurListClose = document.getElementById("btn-pur-list-close");
  if (btnPurListClose) btnPurListClose.addEventListener("click", () => showScreen("view-dashboard"));
  const btnPurListAddNew = document.getElementById("btn-pur-list-add-new");
  if (btnPurListAddNew) btnPurListAddNew.addEventListener("click", () => showScreen("view-purchase-entry"));
  const btnPurListRefresh = document.getElementById("btn-pur-list-refresh");
  if (btnPurListRefresh) btnPurListRefresh.addEventListener("click", renderPurchaseRegister);

  // Supplier Master Buttons
  const btnSupBack = document.getElementById("btn-supplier-master-back");
  if (btnSupBack) btnSupBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnSupClose = document.getElementById("btn-supplier-master-close");
  if (btnSupClose) btnSupClose.addEventListener("click", () => showScreen("view-dashboard"));
  const btnSupAddNew = document.getElementById("btn-supplier-add-new");
  if (btnSupAddNew) btnSupAddNew.addEventListener("click", () => openSupplierFormModal());
  const btnSupRefresh = document.getElementById("btn-supplier-master-refresh");
  if (btnSupRefresh) btnSupRefresh.addEventListener("click", () => renderSupplierMaster());
  const supSearchInput = document.getElementById("supplier-master-search");
  if (supSearchInput) {
    supSearchInput.addEventListener("input", (e) => {
      renderSupplierMaster(e.target.value.trim());
    });
  }

  // Supplier Form Modal
  const btnCloseSupModal = document.getElementById("btn-close-supplier-modal");
  if (btnCloseSupModal) btnCloseSupModal.addEventListener("click", () => {
    document.getElementById("modal-supplier-form").style.display = "none";
  });
  const btnCancelSupModal = document.getElementById("btn-cancel-supplier-modal");
  if (btnCancelSupModal) btnCancelSupModal.addEventListener("click", () => {
    document.getElementById("modal-supplier-form").style.display = "none";
  });
  const btnSaveSupModal = document.getElementById("btn-save-supplier-modal");
  if (btnSaveSupModal) btnSaveSupModal.addEventListener("click", saveSupplierMaster);

  // Supplier Ledger Modal
  const btnCloseSupLedger = document.getElementById("btn-close-supplier-ledger");
  if (btnCloseSupLedger) btnCloseSupLedger.addEventListener("click", () => {
    document.getElementById("modal-supplier-ledger").style.display = "none";
  });
  const btnCloseSupLedgerBottom = document.getElementById("btn-close-sup-ledger-bottom");
  if (btnCloseSupLedgerBottom) btnCloseSupLedgerBottom.addEventListener("click", () => {
    document.getElementById("modal-supplier-ledger").style.display = "none";
  });

  // Stock Summary Buttons
  const btnStockBack = document.getElementById("btn-stock-summary-back");
  if (btnStockBack) btnStockBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnStockClose = document.getElementById("btn-stock-summary-close");
  if (btnStockClose) btnStockClose.addEventListener("click", () => showScreen("view-dashboard"));
  const btnStockRefresh = document.getElementById("btn-stock-summary-refresh");
  if (btnStockRefresh) btnStockRefresh.addEventListener("click", renderStockSummary);
  const btnStockAdjNav = document.getElementById("btn-stock-summary-adjust");
  if (btnStockAdjNav) btnStockAdjNav.addEventListener("click", () => showScreen("view-stock-adjustments"));
  const stockSearchInput = document.getElementById("stock-summary-search");
  if (stockSearchInput) stockSearchInput.addEventListener("input", renderStockSummary);
  const stockFilterStatus = document.getElementById("stock-summary-filter-status");
  if (stockFilterStatus) stockFilterStatus.addEventListener("change", renderStockSummary);

  // Stock Item Ledger Modal
  const btnCloseItemLedger = document.getElementById("btn-close-stock-item-ledger");
  if (btnCloseItemLedger) btnCloseItemLedger.addEventListener("click", () => {
    document.getElementById("modal-stock-item-ledger").style.display = "none";
  });
  const btnCloseItemLedgerBottom = document.getElementById("btn-close-stock-ledger-bottom");
  if (btnCloseItemLedgerBottom) btnCloseItemLedgerBottom.addEventListener("click", () => {
    document.getElementById("modal-stock-item-ledger").style.display = "none";
  });

  // Stock Adjustments Screen
  const btnStockAdjBack = document.getElementById("btn-stock-adj-back");
  if (btnStockAdjBack) btnStockAdjBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnStockAdjClose = document.getElementById("btn-stock-adj-close");
  if (btnStockAdjClose) btnStockAdjClose.addEventListener("click", () => showScreen("view-dashboard"));
  const tabBtnAdj = document.getElementById("tab-btn-stock-adj");
  if (tabBtnAdj) tabBtnAdj.addEventListener("click", () => switchStockAdjTab("adj"));
  const tabBtnTrn = document.getElementById("tab-btn-stock-transfer");
  if (tabBtnTrn) tabBtnTrn.addEventListener("click", () => switchStockAdjTab("transfer"));
  const btnAdjSubmit = document.getElementById("btn-adj-submit");
  if (btnAdjSubmit) btnAdjSubmit.addEventListener("click", postStockAdjustment);
  const btnAdjReset = document.getElementById("btn-adj-reset");
  if (btnAdjReset) {
    btnAdjReset.addEventListener("click", () => {
      const itemSel = document.getElementById("adj-item-select");
      if (itemSel) itemSel.value = "";
      const qtyInput = document.getElementById("adj-qty");
      if (qtyInput) qtyInput.value = "";
      const reasonInput = document.getElementById("adj-reason");
      if (reasonInput) reasonInput.value = "";
      const curStockDisp = document.getElementById("adj-current-stock-disp");
      if (curStockDisp) curStockDisp.textContent = "0";
      const newStockDisp = document.getElementById("adj-new-stock-disp");
      if (newStockDisp) newStockDisp.textContent = "0";
      showNotification("Stock adjustment inputs reset.");
    });
  }

  const btnTrnSubmit = document.getElementById("btn-trn-submit");
  if (btnTrnSubmit) btnTrnSubmit.addEventListener("click", postStockTransfer);
  const btnTrnReset = document.getElementById("btn-trn-reset");
  if (btnTrnReset) {
    btnTrnReset.addEventListener("click", () => {
      const trnItemSel = document.getElementById("trn-item-select");
      if (trnItemSel) trnItemSel.value = "";
      const trnQtyInput = document.getElementById("trn-qty");
      if (trnQtyInput) trnQtyInput.value = "";
      const trnNotes = document.getElementById("trn-notes");
      if (trnNotes) trnNotes.value = "";
      showNotification("Stock transfer inputs reset.");
    });
  }

  // Day Book & Trial Balance Screen
  const btnDayBookBack = document.getElementById("btn-daybook-back");
  if (btnDayBookBack) btnDayBookBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnDayBookClose = document.getElementById("btn-daybook-close");
  if (btnDayBookClose) btnDayBookClose.addEventListener("click", () => showScreen("view-dashboard"));
  const tabBtnDb = document.getElementById("tab-btn-daybook");
  if (tabBtnDb) tabBtnDb.addEventListener("click", () => switchDayBookTab("daybook"));
  const tabBtnTb = document.getElementById("tab-btn-trial-balance");
  if (tabBtnTb) tabBtnTb.addEventListener("click", () => switchDayBookTab("trial-balance"));
  const btnDbRefresh = document.getElementById("btn-daybook-refresh");
  if (btnDbRefresh) btnDbRefresh.addEventListener("click", renderDayBookScreen);
  const btnTbRefresh = document.getElementById("btn-trial-balance-refresh");
  if (btnTbRefresh) btnTbRefresh.addEventListener("click", renderTrialBalanceScreen);
  const dbDateInput = document.getElementById("daybook-date-input");
  if (dbDateInput) dbDateInput.addEventListener("change", renderDayBookScreen);

  // OCR Modal Buttons
  const btnCloseOcr = document.getElementById("btn-close-ocr-modal");
  if (btnCloseOcr) btnCloseOcr.addEventListener("click", () => {
    document.getElementById("modal-invoice-ocr").style.display = "none";
  });
  const btnCloseOcrBottom = document.getElementById("btn-close-ocr-bottom");
  if (btnCloseOcrBottom) btnCloseOcrBottom.addEventListener("click", () => {
    document.getElementById("modal-invoice-ocr").style.display = "none";
  });
  const btnOcrSample = document.getElementById("btn-ocr-load-sample");
  if (btnOcrSample) {
    btnOcrSample.addEventListener("click", () => {
      const rawText = document.getElementById("ocr-raw-text-input");
      if (rawText) rawText.value = SAMPLE_GST_INVOICE_TEXT;
      showNotification("Sample GST tax invoice text loaded.");
    });
  }
  const btnOcrExtract = document.getElementById("btn-ocr-run-extract");
  if (btnOcrExtract) btnOcrExtract.addEventListener("click", runOcrExtraction);
  const btnOcrPopulate = document.getElementById("btn-ocr-populate-purchase");
  if (btnOcrPopulate) btnOcrPopulate.addEventListener("click", populatePurchaseVoucherFromOcr);

  // Sales Return Modal
  const btnCloseSr = document.getElementById("btn-close-sales-return");
  if (btnCloseSr) btnCloseSr.addEventListener("click", () => {
    document.getElementById("modal-sales-return").style.display = "none";
  });
  const btnCancelSr = document.getElementById("btn-cancel-sales-return");
  if (btnCancelSr) btnCancelSr.addEventListener("click", () => {
    document.getElementById("modal-sales-return").style.display = "none";
  });
  const btnSubmitSr = document.getElementById("btn-submit-sales-return");
  if (btnSubmitSr) btnSubmitSr.addEventListener("click", postSalesReturn);

  // Purchase Return Modal
  const btnClosePr = document.getElementById("btn-close-purchase-return");
  if (btnClosePr) btnClosePr.addEventListener("click", () => {
    document.getElementById("modal-purchase-return").style.display = "none";
  });
  const btnCancelPr = document.getElementById("btn-cancel-purchase-return");
  if (btnCancelPr) btnCancelPr.addEventListener("click", () => {
    document.getElementById("modal-purchase-return").style.display = "none";
  });
  const btnSubmitPr = document.getElementById("btn-submit-purchase-return");
  if (btnSubmitPr) btnSubmitPr.addEventListener("click", postPurchaseReturn);

  // Low Stock Alert Modal & Ribbon Pills
  const barLowStockAlert = document.getElementById("bar-low-stock-alert");
  if (barLowStockAlert) {
    barLowStockAlert.addEventListener("click", () => {
      if (activeCompany && window.backend && window.backend.getLowStockAlerts) {
        window.backend.getLowStockAlerts(activeCompany.id, (resp) => {
          try {
            const r = JSON.parse(resp);
            if (r.success && r.data) {
              showLowStockAlertModal(r.data);
            }
          } catch (e) {
            console.error(e);
          }
        });
      }
    });
  }

  const btnPosLowStockPill = document.getElementById("btn-pos-low-stock-pill");
  if (btnPosLowStockPill) {
    btnPosLowStockPill.addEventListener("click", () => {
      if (activeCompany && window.backend && window.backend.getLowStockAlerts) {
        window.backend.getLowStockAlerts(activeCompany.id, (resp) => {
          try {
            const r = JSON.parse(resp);
            if (r.success && r.data) {
              showLowStockAlertModal(r.data);
            }
          } catch (e) {
            console.error(e);
          }
        });
      }
    });
  }

  // Header Notifications Bell Trigger
  const btnHeaderNotifications = document.getElementById("btn-header-notifications");
  if (btnHeaderNotifications) {
    btnHeaderNotifications.addEventListener("click", () => {
      showLowStockAlertModal(null, "all");
    });
  }

  // Low Stock Notification Filter Tabs
  document.querySelectorAll(".notif-filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const fType = btn.dataset.filter || "all";
      showLowStockAlertModal(null, fType);
    });
  });

  // Low Stock Notification In-Modal Search
  const notifModalSearch = document.getElementById("notif-modal-search");
  if (notifModalSearch) {
    notifModalSearch.addEventListener("input", (e) => {
      renderNotificationRows(currentNotifAlerts, e.target.value);
    });
  }

  const btnCloseLowStockModal = document.getElementById("btn-close-low-stock-modal");
  if (btnCloseLowStockModal) {
    btnCloseLowStockModal.addEventListener("click", () => closeLowStockAlertModal(false));
  }

  const btnCloseLowStockBottom = document.getElementById("btn-close-low-stock-bottom");
  if (btnCloseLowStockBottom) {
    btnCloseLowStockBottom.addEventListener("click", () => closeLowStockAlertModal(false));
  }

  const btnLowStockDismiss = document.getElementById("btn-low-stock-dismiss");
  if (btnLowStockDismiss) {
    btnLowStockDismiss.addEventListener("click", () => closeLowStockAlertModal(true));
  }

  const btnLowStockViewInventory = document.getElementById("btn-low-stock-view-inventory");
  if (btnLowStockViewInventory) {
    btnLowStockViewInventory.addEventListener("click", () => {
      closeLowStockAlertModal(false);
      showScreen("view-stock-summary");
      const statusFilter = document.getElementById("stock-summary-filter-status");
      if (statusFilter) {
        statusFilter.value = "LOW_STOCK";
      }
      renderStockSummary();
    });
  }

  const btnLowStockEditItem = document.getElementById("btn-low-stock-edit-item") || document.getElementById("btn-low-stock-view-product");
  if (btnLowStockEditItem) {
    btnLowStockEditItem.addEventListener("click", () => {
      const modal = document.getElementById("modal-low-stock-alert");
      const selectedId = modal ? modal.dataset.selectedItemId : null;
      closeLowStockAlertModal(false);
      if (selectedId) {
        loadProductForEditing(selectedId);
      } else {
        showScreen("view-items-list");
      }
    });
  }

  const btnLowStockViewProduct = document.getElementById("btn-low-stock-view-product");
  if (btnLowStockViewProduct && btnLowStockViewProduct !== btnLowStockEditItem) {
    btnLowStockViewProduct.addEventListener("click", () => {
      const modal = document.getElementById("modal-low-stock-alert");
      const selectedId = modal ? modal.dataset.selectedItemId : null;
      closeLowStockAlertModal(false);
      if (selectedId) {
        loadProductForEditing(selectedId);
      } else {
        showScreen("view-items-list");
      }
    });
  }

  // Traditional Billing Party Category changes
  if (vchPartyInput) {
    vchPartyInput.addEventListener("input", () => {
      updateVoucherPartyCategory();
      for (let r = 1; r <= 10; r++) {
        calcRowAmount(r);
      }
      recalculateVoucherTotals();
    });
    vchPartyInput.addEventListener("change", () => {
      updateVoucherPartyCategory();
      for (let r = 1; r <= 10; r++) {
        calcRowAmount(r);
      }
      recalculateVoucherTotals();
    });
  }
}

// Update System Clock
function updateSystemClock() {
  const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const now = new Date();
  const dayName = days[now.getDay()];
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const yyyy = now.getFullYear();
  const hh = String(now.getHours()).padStart(2, "0");
  const min = String(now.getMinutes()).padStart(2, "0");

  const formatted = `${dayName} ${dd}-${mm}-${yyyy} ${hh}:${min}`;
  if (dashboardDatetime) {
    dashboardDatetime.textContent = formatted;
  }
}

// Cascading Submenu Positioning & Viewport Boundary Flip
function initCascadingSubmenuPositioning() {
  const branches = document.querySelectorAll(".tree-branch");
  branches.forEach((branch) => {
    branch.addEventListener("mouseenter", () => {
      const submenu = branch.querySelector(":scope > .tree-submenu");
      if (!submenu) return;

      submenu.classList.remove("submenu-flip-left", "submenu-shift-up");

      const rect = submenu.getBoundingClientRect();
      const scale = typeof uiZoom !== "undefined" ? uiZoom : 1.0;
      const winW = window.innerWidth;
      const winH = window.innerHeight;

      // If opening on the right would exceed viewport boundary
      if (rect.right * scale > winW - 5) {
        submenu.classList.add("submenu-flip-left");
      }

      // If opening downwards would exceed viewport boundary
      if (rect.bottom * scale > winH - 28) {
        submenu.classList.add("submenu-shift-up");
      }
    });
  });
}

// =============================================================
// OPERATIONAL DASHBOARD & SIDEBAR NAVIGATION
// =============================================================
function renderOperationalDashboard() {
  if (!activeCompany) return;

  const todayStr = new Date().toISOString().slice(0, 10);
  const activeFyEl = document.getElementById("dash-active-fy");
  if (activeFyEl && activeCompany) {
    activeFyEl.textContent = `F.Y. ${activeCompany.fin_year || "2026-27"}`;
  }

  // 1. Sales metrics & recent table
  const salesValEl = document.getElementById("dash-today-sales");
  const salesCountEl = document.getElementById("dash-sales-count");
  const salesTbody = document.getElementById("dash-recent-sales-tbody");

  function processSales(bills) {
    let todaySales = 0;
    let todayCount = 0;
    (bills || []).forEach(b => {
      const bDate = (b.vch_date || b.created_at || "").slice(0, 10);
      if (bDate === todayStr || !bDate) {
        todaySales += (parseFloat(b.grand_total) || 0);
        todayCount++;
      }
    });

    if (salesValEl) salesValEl.innerHTML = `&#8377;${todaySales.toFixed(2)}`;
    if (salesCountEl) salesCountEl.textContent = `${todayCount} invoice${todayCount === 1 ? "" : "s"} generated today (${(bills || []).length} total)`;

    if (salesTbody) {
      if (!bills || bills.length === 0) {
        salesTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 14px;">No sales invoices recorded yet.</td></tr>`;
      } else {
        const recent = bills.slice(-5).reverse();
        salesTbody.innerHTML = recent.map(b => `
          <tr>
            <td style="font-weight: 700; color: #1e40af;">${escapeHtml(b.vch_no || "VCH-001")}</td>
            <td>${escapeHtml((b.vch_date || b.created_at || todayStr).slice(0, 10))}</td>
            <td style="font-weight: 600;">${escapeHtml(b.party_name || "Retail Customer")}</td>
            <td style="text-align: right; font-weight: 800; color: #047857;">&#8377;${(parseFloat(b.grand_total) || 0).toFixed(2)}</td>
            <td><span class="status-badge success">Paid</span></td>
          </tr>
        `).join("");
      }
    }
  }

  if (window.backend && window.backend.listVouchers) {
    window.backend.listVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          processSales(r.data);
          return;
        }
      } catch (e) {}
      processSales(getSalesVouchers());
    });
  } else {
    processSales(getSalesVouchers());
  }

  // 2. Purchases metrics & recent table
  const purValEl = document.getElementById("dash-today-purchases");
  const purCountEl = document.getElementById("dash-purchases-count");
  const purTbody = document.getElementById("dash-recent-purchases-tbody");

  function processPurchases(purs) {
    let todayPurchases = 0;
    let todayPurCount = 0;
    (purs || []).forEach(p => {
      const pDate = (p.voucher_date || p.created_at || "").slice(0, 10);
      if (pDate === todayStr || !pDate) {
        todayPurchases += (parseFloat(p.grand_total) || 0);
        todayPurCount++;
      }
    });

    if (purValEl) purValEl.innerHTML = `&#8377;${todayPurchases.toFixed(2)}`;
    if (purCountEl) purCountEl.textContent = `${todayPurCount} purchase bill${todayPurCount === 1 ? "" : "s"} posted today (${(purs || []).length} total)`;

    if (purTbody) {
      if (!purs || purs.length === 0) {
        purTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 14px;">No inward purchases recorded yet.</td></tr>`;
      } else {
        const recent = purs.slice(-5).reverse();
        purTbody.innerHTML = recent.map(p => `
          <tr>
            <td style="font-weight: 700; color: #1e3a8a;">${escapeHtml(p.vch_no || p.supplier_invoice_no || "PUR-001")}</td>
            <td>${escapeHtml((p.voucher_date || p.created_at || todayStr).slice(0, 10))}</td>
            <td style="font-weight: 600;">${escapeHtml(p.supplier_name || "Standard Supplier")}</td>
            <td style="text-align: right; font-weight: 800; color: #0f172a;">&#8377;${(parseFloat(p.grand_total) || 0).toFixed(2)}</td>
            <td><span class="status-badge success">Posted</span></td>
          </tr>
        `).join("");
      }
    }
  }

  if (window.backend && window.backend.listPurchaseVouchers) {
    window.backend.listPurchaseVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          processPurchases(r.data);
          return;
        }
      } catch (e) {}
      processPurchases([]);
    });
  } else {
    processPurchases([]);
  }

  // 3. Low stock alerts
  const lowStockValEl = document.getElementById("dash-low-stock");
  const lowStockBadgeEl = document.getElementById("dash-low-stock-badge");
  const lowStockSubEl = document.getElementById("dash-low-stock-sub");

  if (window.backend && window.backend.getLowStockAlerts) {
    window.backend.getLowStockAlerts(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const count = r.data.length;
          if (lowStockValEl) lowStockValEl.textContent = `${count} item${count === 1 ? "" : "s"}`;
          if (lowStockBadgeEl) {
            lowStockBadgeEl.className = count > 0 ? "status-badge warning" : "status-badge success";
            lowStockBadgeEl.textContent = count > 0 ? "Attention" : "Optimal";
          }
          if (lowStockSubEl) {
            lowStockSubEl.textContent = count > 0
              ? `${count} product(s) below reorder threshold`
              : "All products above minimum threshold";
          }
        }
      } catch (e) {}
    });
  }

  // 4. Held bills / POS Cart
  const heldBillsValEl = document.getElementById("dash-held-bills");
  if (heldBillsValEl) {
    const activeBillsCount = (typeof heldBills !== "undefined" && heldBills ? heldBills.length : 0) +
                             (typeof posCart !== "undefined" && posCart && posCart.length > 0 ? 1 : 0);
    heldBillsValEl.textContent = `${activeBillsCount} bill${activeBillsCount === 1 ? "" : "s"}`;
  }
}

function setupSidebarAndDashboardNav() {
  const navMappings = [
    { id: "btn-nav-overview", action: () => showScreen("view-dashboard") },
    { id: "btn-nav-pos", action: () => openFastBillingPos() },
    { id: "btn-nav-sales-add", action: () => showScreen("view-sales-voucher") },
    { id: "btn-nav-sales-list", action: () => showScreen("view-sales-list") },
    { id: "btn-nav-sales-return", action: () => {
        const m = document.getElementById("modal-sales-return");
        if (m) m.classList.add("active");
      }
    },
    { id: "btn-nav-purchase-add", action: () => showScreen("view-purchase-entry") },
    { id: "btn-nav-purchase-list", action: () => showScreen("view-purchase-list") },
    { id: "btn-nav-purchase-return", action: () => {
        const m = document.getElementById("modal-purchase-return");
        if (m) m.classList.add("active");
      }
    },
    { id: "btn-nav-suppliers", action: () => showScreen("view-supplier-master") },
    { id: "btn-nav-stock", action: () => showScreen("view-stock-summary") },
    { id: "btn-nav-transfer", action: () => {
        showScreen("view-stock-adjustments");
        const tabBtn = document.getElementById("tab-btn-stock-transfer");
        if (tabBtn) tabBtn.click();
      }
    },
    { id: "btn-nav-adjustments", action: () => {
        showScreen("view-stock-adjustments");
        const tabBtn = document.getElementById("tab-btn-stock-adj");
        if (tabBtn) tabBtn.click();
      }
    },
    { id: "btn-nav-low-stock", action: () => {
        if (typeof checkLowStockAlerts === "function") checkLowStockAlerts(true);
      }
    },
    { id: "btn-nav-customers", action: () => showScreen("view-add-account-master") },
    { id: "btn-nav-customer-categories", action: () => {
        const m = document.getElementById("modal-configuration");
        if (m) m.classList.add("active");
      }
    },
    { id: "btn-nav-add-product", action: () => openAddProductMaster() },
    { id: "btn-nav-products", action: () => showScreen("view-items-list") },
    { id: "btn-nav-daybook", action: () => showScreen("view-day-book") },
    { id: "btn-nav-trial-balance", action: () => {
        showScreen("view-day-book");
        const tbBtn = document.getElementById("tab-btn-trial-balance");
        if (tbBtn) tbBtn.click();
      }
    },
    { id: "btn-nav-gst", action: () => {
        const m = document.getElementById("modal-reports");
        if (m) m.classList.add("active");
        else showScreen("view-day-book");
      }
    },
    { id: "btn-nav-config", action: () => {
        const m = document.getElementById("modal-configuration");
        if (m) m.classList.add("active");
      }
    },
    { id: "btn-nav-switch-mode", action: () => {
        const btn = document.getElementById("bar-switch-mode");
        if (btn) btn.click();
      }
    },
    { id: "btn-nav-backup", action: () => {
        const m = document.getElementById("modal-backup");
        if (m) m.classList.add("active");
      }
    },
    { id: "btn-nav-printer", action: () => {
        const m = document.getElementById("modal-receipt-preview");
        if (m) m.classList.add("active");
      }
    },
    // Quick Actions on Dashboard
    { id: "dash-btn-refresh-overview", action: () => renderOperationalDashboard() },
    { id: "dash-btn-pos", action: () => openFastBillingPos() },
    { id: "dash-btn-sales-add", action: () => showScreen("view-sales-voucher") },
    { id: "dash-btn-purchase-add", action: () => showScreen("view-purchase-entry") },
    { id: "dash-btn-product-add", action: () => openAddProductMaster() },
    { id: "dash-btn-stock-view", action: () => showScreen("view-stock-summary") },
    { id: "dash-btn-daybook", action: () => showScreen("view-day-book") },
    { id: "dash-btn-view-all-sales", action: () => showScreen("view-sales-list") },
    { id: "dash-btn-view-all-purchases", action: () => showScreen("view-purchase-list") },
  ];

  navMappings.forEach(({ id, action }) => {
    const el = document.getElementById(id);
    if (el) {
      el.addEventListener("click", action);
    }
  });
}

// Startup
window.showToast = window.showNotification = showNotification;
if (window.BusinessContext) window.BusinessContext.init();
if (window.SidebarNavigation) window.SidebarNavigation.init();
if (window.HeaderManager) window.HeaderManager.init();
if (window.DashboardManager) window.DashboardManager.init();
if (window.GlobalSearchManager) window.GlobalSearchManager.init();

window.activeCompany = null;
activeCompany = null;

renderCompanyTable();
initLoginModeToggle();
initTraditionalSetupListeners();
initTraditionalRecoveryListeners();
fetchAndPopulateCompanies();
updateSystemClock();
setInterval(updateSystemClock, 10000);
setupPosBarcodeAutocomplete();
setupPartyAutocomplete();
initPosTextSizeControls();
initDailyDiscountControls();
initPosTenderListeners();

function setupCompanyAndPlaceholderModalListeners() {
  // 1. Edit Company Modal
  const modalEditComp = document.getElementById("modal-edit-company");
  const btnCloseEditComp = document.getElementById("btn-close-edit-company-modal");
  const btnCancelEditComp = document.getElementById("btn-cancel-edit-company");
  const formEditComp = document.getElementById("form-edit-company");

  function closeEditCompanyModal() {
    if (modalEditComp) {
      modalEditComp.classList.remove("show");
      modalEditComp.style.display = "none";
    }
  }

  if (btnCloseEditComp) btnCloseEditComp.addEventListener("click", closeEditCompanyModal);
  if (btnCancelEditComp) btnCancelEditComp.addEventListener("click", closeEditCompanyModal);

  if (formEditComp) {
    formEditComp.addEventListener("submit", (e) => {
      e.preventDefault();
      const name = document.getElementById("edit-comp-name").value.trim();
      const code = document.getElementById("edit-comp-code").value.trim();
      const finYear = document.getElementById("edit-comp-finyear").value.trim();
      const gstin = document.getElementById("edit-comp-gstin").value.trim();
      const state = document.getElementById("edit-comp-state").value.trim();
      const address = document.getElementById("edit-comp-address").value.trim();

      if (!name) {
        if (typeof showNotification === "function") showNotification("Please enter a valid Company Name.", "warning");
        return;
      }

      if (window.BusinessContext) {
        window.BusinessContext.updateCompanyDetails(code, {
          name,
          finYear,
          taxNo: gstin,
          state,
          address
        });
      }

      closeEditCompanyModal();
      if (typeof showNotification === "function") showNotification(`Company "${name}" updated successfully.`, "success");
    });
  }

  // 2. Close Company Confirmation Modal
  const modalCloseComp = document.getElementById("modal-close-company-confirm");
  const btnCloseCompX = document.getElementById("btn-close-company-confirm-x");
  const btnCancelCloseComp = document.getElementById("btn-cancel-close-company");
  const btnConfirmCloseComp = document.getElementById("btn-confirm-close-company");

  function closeCloseCompanyModal() {
    if (modalCloseComp) {
      modalCloseComp.classList.remove("show");
      modalCloseComp.style.display = "none";
    }
  }

  if (btnCloseCompX) btnCloseCompX.addEventListener("click", closeCloseCompanyModal);
  if (btnCancelCloseComp) btnCancelCloseComp.addEventListener("click", closeCloseCompanyModal);

  if (btnConfirmCloseComp) {
    btnConfirmCloseComp.addEventListener("click", () => {
      closeCloseCompanyModal();
      if (window.BusinessContext) {
        window.BusinessContext.closeActiveCompanySession();
      }
      if (typeof showScreen === "function") showScreen("view-companies");
      if (typeof showNotification === "function") showNotification("Company workspace closed. Select a company to continue.", "info");
    });
  }

  // 3. Feature Placeholder Modal
  const modalPlaceholder = document.getElementById("modal-feature-placeholder");
  const btnClosePlaceholder = document.getElementById("btn-close-placeholder-modal");
  const btnOkPlaceholder = document.getElementById("btn-ok-placeholder-modal");

  function closePlaceholderModal() {
    if (modalPlaceholder) {
      modalPlaceholder.classList.remove("show");
      modalPlaceholder.style.display = "none";
    }
  }

  if (btnClosePlaceholder) btnClosePlaceholder.addEventListener("click", closePlaceholderModal);
  if (btnOkPlaceholder) {
    btnOkPlaceholder.addEventListener("click", () => {
      closePlaceholderModal();
      if (typeof showScreen === "function") showScreen("view-dashboard");
    });
  }

  // Escape key handler for these modals
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      if (modalEditComp && modalEditComp.classList.contains("show")) closeEditCompanyModal();
      if (modalCloseComp && modalCloseComp.classList.contains("show")) closeCloseCompanyModal();
      if (modalPlaceholder && modalPlaceholder.classList.contains("show")) closePlaceholderModal();
      const mAcc = document.getElementById("modal-select-account-modify");
      if (mAcc && (mAcc.classList.contains("show") || mAcc.style.display !== "none")) closeModal("modal-select-account-modify");
      const mItem = document.getElementById("modal-select-item-modify");
      if (mItem && (mItem.classList.contains("show") || mItem.style.display !== "none")) closeModal("modal-select-item-modify");
      const mSales = document.getElementById("modal-select-sales-modify");
      if (mSales && (mSales.classList.contains("show") || mSales.style.display !== "none")) closeModal("modal-select-sales-modify");
      const mPur = document.getElementById("modal-select-purchase-modify");
      if (mPur && (mPur.classList.contains("show") || mPur.style.display !== "none")) closeModal("modal-select-purchase-modify");
    }
  });
}

// =============================================================
// THREE-OPTION WORKFLOW SELECTION MODALS & EVENT HANDLERS
// =============================================================
function openModal(modalId) {
  if (modalId === "modal-config" || modalId === "modal-configuration-page") {
    if (typeof showScreen === "function") {
      showScreen("view-configuration");
      return;
    }
  }
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add("show");
    modal.style.display = "flex";
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove("show");
    modal.style.display = "none";
  }
}

window.openModal = openModal;
window.closeModal = closeModal;

function renderSelectAccountModifyModal() {
  if (!activeCompany) return;
  const tbody = document.getElementById("acc-modify-modal-tbody");
  const searchIn = document.getElementById("acc-modify-modal-search");
  if (!tbody) return;
  const q = (searchIn?.value || "").toLowerCase().trim();

  const populate = (accounts) => {
    const list = accounts.filter(a => !q || (a.name && a.name.toLowerCase().includes(q)) || (a.mobile && a.mobile.includes(q)) || (a.gstin && a.gstin.toLowerCase().includes(q)));
    tbody.innerHTML = "";
    if (list.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color:#64748b;">No matching accounts found</td></tr>`;
      return;
    }
    list.forEach(a => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      const bal = parseFloat(a.current_balance ?? a.op_bal ?? 0) || 0;
      tr.innerHTML = `
        <td><strong>${escapeHtml(a.name)}</strong></td>
        <td>${escapeHtml(a.account_group || a.group || "Sundry Debtors")}</td>
        <td>${escapeHtml(a.customer_category || "Direct Customer")}</td>
        <td>${escapeHtml(a.mobile || a.gstin || "-")}</td>
        <td style="text-align: right; font-weight: 700;">₹ ${bal.toFixed(2)}</td>
        <td style="text-align: center;"><button type="button" class="btn-classic primary-action-btn" style="padding: 2px 8px; font-size: 11px;">Modify</button></td>
      `;
      const onSelect = () => {
        closeModal("modal-select-account-modify");
        openModifyAccountMaster(a.id);
      };
      tr.addEventListener("click", onSelect);
      tbody.appendChild(tr);
    });
  };

  const isTrad = (typeof openTabs !== "undefined" && openTabs.has("traditional"));
  if (isTrad && window.backend && typeof window.backend.traditional_listAccounts === "function") {
    window.backend.traditional_listAccounts(q || "", false, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && Array.isArray(r.data)) {
          populate(r.data);
          return;
        }
      } catch (e) {}
      const key = `alpha_accounts_${activeCompany.code}`;
      let list = [];
      try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
      populate(list);
    });
    return;
  } else if (isTrad && window.backend && typeof window.backend.traditional_listCustomers === "function") {
    window.backend.traditional_listCustomers(q || "", false, (resp) => {
      try {
        const r = typeof resp === "string" ? JSON.parse(resp) : resp;
        if (r && r.success && Array.isArray(r.data)) {
          populate(r.data);
          return;
        }
      } catch (e) {}
      const key = `alpha_accounts_${activeCompany.code}`;
      let list = [];
      try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
      populate(list);
    });
    return;
  }

  if (window.backend && window.backend.listAccounts) {
    window.backend.listAccounts(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          populate(r.data);
          return;
        }
      } catch (e) {}
      populate([]);
    });
  } else {
    const key = `alpha_accounts_${activeCompany.code}`;
    let list = [];
    try { list = JSON.parse(localStorage.getItem(key) || "[]"); } catch(e){}
    populate(list);
  }
}

function renderSelectItemModifyModal() {
  if (!activeCompany) return;
  const tbody = document.getElementById("item-modify-modal-tbody");
  const searchIn = document.getElementById("item-modify-modal-search");
  if (!tbody) return;
  const q = (searchIn?.value || "").toLowerCase().trim();

  fetchAllItems(q, (items) => {
    tbody.innerHTML = "";
    if (!items || items.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding: 20px; color:#64748b;">No matching products found</td></tr>`;
      return;
    }
    items.forEach(it => {
      const tr = document.createElement("tr");
      tr.style.cursor = "pointer";
      const price = parseFloat(it.sales_price || it.salesPrice || it.price || 0).toFixed(2);
      tr.innerHTML = `
        <td><strong>${escapeHtml(it.name)}</strong></td>
        <td><span class="badge-barcode">${escapeHtml(it.barcodes || it.barcode || it.alias || "-")}</span></td>
        <td>${escapeHtml(it.item_group || it.group || "General")}</td>
        <td style="text-align: right; font-weight: 700; color: #166534;">₹ ${price}</td>
        <td style="text-align: center;"><button type="button" class="btn-classic primary-action-btn" style="padding: 2px 8px; font-size: 11px;">Modify</button></td>
      `;
      const onSelect = () => {
        closeModal("modal-select-item-modify");
        loadProductForEditing(it.id);
      };
      tr.addEventListener("click", onSelect);
      tbody.appendChild(tr);
    });
  });
}

function renderSelectSalesModifyModal() {
  if (!activeCompany) return;
  const tbody = document.getElementById("sales-modify-modal-tbody");
  const searchIn = document.getElementById("sales-modify-modal-search");
  if (!tbody) return;
  const q = (searchIn?.value || "").toLowerCase().trim();

  if (window.backend && window.backend.listVouchers) {
    window.backend.listVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const list = r.data.filter(v => !q || (v.vch_no && v.vch_no.toLowerCase().includes(q)) || (v.party_name && v.party_name.toLowerCase().includes(q)));
          tbody.innerHTML = "";
          if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color:#64748b;">No matching sales invoices found</td></tr>`;
            return;
          }
          list.forEach(v => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            const total = parseFloat(v.grand_total || 0).toFixed(2);
            tr.innerHTML = `
              <td style="font-weight: 800; color: #1e40af;">${escapeHtml(v.vch_no)}</td>
              <td>${escapeHtml(v.vch_date || "")}</td>
              <td style="font-weight: 700;">${escapeHtml(v.party_name || "CASH")}</td>
              <td style="text-align: right; font-weight: 800; color: #047857;">₹ ${total}</td>
              <td style="text-align: center;"><span class="stock-badge-optimal">POSTED</span></td>
              <td style="text-align: center;"><button type="button" class="btn-classic primary-action-btn" style="padding: 2px 8px; font-size: 11px;">Modify</button></td>
            `;
            const onSelect = () => {
              closeModal("modal-select-sales-modify");
              openModifySaleInvoice(v.id || v.voucher_id || v.vch_no);
            };
            tr.addEventListener("click", onSelect);
            tbody.appendChild(tr);
          });
        }
      } catch (e) {}
    });
  }
}

function renderSelectPurchaseModifyModal() {
  if (!activeCompany) return;
  const tbody = document.getElementById("purchase-modify-modal-tbody");
  const searchIn = document.getElementById("purchase-modify-modal-search");
  if (!tbody) return;
  const q = (searchIn?.value || "").toLowerCase().trim();

  if (window.backend && window.backend.listPurchaseVouchers) {
    window.backend.listPurchaseVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const list = r.data.filter(v => !q || (v.vch_no && v.vch_no.toLowerCase().includes(q)) || (v.supplier_name && v.supplier_name.toLowerCase().includes(q)) || (v.supplier_invoice_no && v.supplier_invoice_no.toLowerCase().includes(q)));
          tbody.innerHTML = "";
          if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 20px; color:#64748b;">No matching purchase vouchers found</td></tr>`;
            return;
          }
          list.forEach(v => {
            const tr = document.createElement("tr");
            tr.style.cursor = "pointer";
            const total = parseFloat(v.grand_total || 0).toFixed(2);
            tr.innerHTML = `
              <td style="font-weight: 800; color: #1e40af;">${escapeHtml(v.vch_no)}</td>
              <td>${escapeHtml(v.voucher_date || "")}</td>
              <td style="font-weight: 600;">${escapeHtml(v.supplier_invoice_no || "-")}</td>
              <td>${escapeHtml(v.supplier_name || "")}</td>
              <td style="text-align: right; font-weight: 800; color: #0f172a;">₹ ${total}</td>
              <td style="text-align: center;"><button type="button" class="btn-classic primary-action-btn" style="padding: 2px 8px; font-size: 11px;">Modify</button></td>
            `;
            const onSelect = () => {
              closeModal("modal-select-purchase-modify");
              openModifyPurchaseVoucher(v.id);
            };
            tr.addEventListener("click", onSelect);
            tbody.appendChild(tr);
          });
        }
      } catch (e) {}
    });
  }
}

function setupThreeOptionWorkflowListeners() {
  // Account List controls
  const btnAccBackList = document.getElementById("btn-acc-back-list");
  if (btnAccBackList) btnAccBackList.addEventListener("click", () => showScreen("view-account-list"));
  const btnAccListBack = document.getElementById("btn-acc-list-back");
  if (btnAccListBack) btnAccListBack.addEventListener("click", () => showScreen("view-dashboard"));
  const btnAccListClose = document.getElementById("btn-acc-list-close");
  if (btnAccListClose) btnAccListClose.addEventListener("click", () => showScreen("view-dashboard"));
  const btnAccListCloseBottom = document.getElementById("btn-acc-list-close-bottom");
  if (btnAccListCloseBottom) btnAccListCloseBottom.addEventListener("click", () => showScreen("view-dashboard"));
  const btnAccListAdd = document.getElementById("btn-acc-list-add-new");
  if (btnAccListAdd) btnAccListAdd.addEventListener("click", () => openAddAccountMaster());
  const btnAccListRefresh = document.getElementById("btn-acc-list-refresh");
  if (btnAccListRefresh) btnAccListRefresh.addEventListener("click", () => renderAccountMasterList());
  const accListSearch = document.getElementById("acc-list-search");
  if (accListSearch) {
    accListSearch.addEventListener("input", (e) => renderAccountMasterList(e.target.value));
  }
  const accListGroupFilter = document.getElementById("acc-list-group-filter");
  if (accListGroupFilter) {
    accListGroupFilter.addEventListener("change", (e) => renderAccountMasterList(undefined, e.target.value));
  }

  // Account Modify Modal
  const btnCloseAccMod = document.getElementById("btn-close-acc-modify-modal");
  if (btnCloseAccMod) btnCloseAccMod.addEventListener("click", () => closeModal("modal-select-account-modify"));
  const accModSearch = document.getElementById("acc-modify-modal-search");
  if (accModSearch) accModSearch.addEventListener("input", () => renderSelectAccountModifyModal());
  const btnAccModClear = document.getElementById("btn-acc-modify-modal-clear");
  if (btnAccModClear && accModSearch) {
    btnAccModClear.addEventListener("click", () => {
      accModSearch.value = "";
      accModSearch.focus();
      renderSelectAccountModifyModal();
    });
  }

  // Item Modify Modal
  const btnCloseItemMod = document.getElementById("btn-close-item-modify-modal");
  if (btnCloseItemMod) btnCloseItemMod.addEventListener("click", () => closeModal("modal-select-item-modify"));
  const itemModSearch = document.getElementById("item-modify-modal-search");
  if (itemModSearch) itemModSearch.addEventListener("input", () => renderSelectItemModifyModal());
  const btnItemModClear = document.getElementById("btn-item-modify-modal-clear");
  if (btnItemModClear && itemModSearch) {
    btnItemModClear.addEventListener("click", () => {
      itemModSearch.value = "";
      itemModSearch.focus();
      renderSelectItemModifyModal();
    });
  }

  // Sales Modify Modal
  const btnCloseSalesMod = document.getElementById("btn-close-sales-modify-modal");
  if (btnCloseSalesMod) btnCloseSalesMod.addEventListener("click", () => closeModal("modal-select-sales-modify"));
  const salesModSearch = document.getElementById("sales-modify-modal-search");
  if (salesModSearch) salesModSearch.addEventListener("input", () => renderSelectSalesModifyModal());
  const btnSalesModClear = document.getElementById("btn-sales-modify-modal-clear");
  if (btnSalesModClear && salesModSearch) {
    btnSalesModClear.addEventListener("click", () => {
      salesModSearch.value = "";
      salesModSearch.focus();
      renderSelectSalesModifyModal();
    });
  }

  // Purchase Modify Modal
  const btnClosePurMod = document.getElementById("btn-close-purchase-modify-modal");
  if (btnClosePurMod) btnClosePurMod.addEventListener("click", () => closeModal("modal-select-purchase-modify"));
  const purModSearch = document.getElementById("purchase-modify-modal-search");
  if (purModSearch) purModSearch.addEventListener("input", () => renderSelectPurchaseModifyModal());
  const btnPurModClear = document.getElementById("btn-purchase-modify-modal-clear");
  if (btnPurModClear && purModSearch) {
    btnPurModClear.addEventListener("click", () => {
      purModSearch.value = "";
      purModSearch.focus();
      renderSelectPurchaseModifyModal();
    });
  }
}

// =============================================================================
// PHASE 3.6: TRADITIONAL PAYMENT, RECEIPT & RECONCILIATION CONTROLLER MODULE
// =============================================================================

let currentReceiptInvoices = [];
let cashAndBankAccounts = [];
let activeReversalContext = { type: null, id: null, number: null, party: null, amount: null };
let activePrintContext = null;

function formatMoney(amount) {
  const num = parseFloat(amount || 0);
  return "₹ " + num.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function convertNumberToWords(amount) {
  const num = Math.floor(Math.abs(parseFloat(amount || 0)));
  if (num === 0) return "Zero Rupees Only";
  const units = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"];
  const tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"];
  function numToWords(n) {
    if (n < 20) return units[n];
    if (n < 100) return tens[Math.floor(n / 10)] + (n % 10 ? " " + units[n % 10] : "");
    if (n < 1000) return units[Math.floor(n / 100)] + " Hundred" + (n % 100 ? " " + numToWords(n % 100) : "");
    if (n < 100000) return numToWords(Math.floor(n / 1000)) + " Thousand" + (n % 1000 ? " " + numToWords(n % 1000) : "");
    if (n < 10000000) return numToWords(Math.floor(n / 100000)) + " Lakh" + (n % 100000 ? " " + numToWords(n % 100000) : "");
    return numToWords(Math.floor(n / 10000000)) + " Crore" + (n % 10000000 ? " " + numToWords(n % 10000000) : "");
  }
  return "Rupees " + numToWords(num) + " Only";
}

function loadCashAndBankAccounts(callback) {
  if (window.backend && window.backend.traditional_listCashAndBankAccounts) {
    window.backend.traditional_listCashAndBankAccounts((resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && Array.isArray(res.data)) {
          cashAndBankAccounts = res.data;
        } else {
          cashAndBankAccounts = [];
        }
      } catch (e) {
        console.error("Error parsing cash and bank accounts:", e);
        cashAndBankAccounts = [];
      }
      if (typeof callback === "function") callback(cashAndBankAccounts);
    });
  } else {
    if (typeof callback === "function") callback([]);
  }
}

function populateAccountsDropdown(selectId, paymentMethod) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  sel.innerHTML = "";
  const pm = (paymentMethod || "CASH").toUpperCase();
  const isCash = pm === "CASH";
  const filtered = cashAndBankAccounts.filter(acc => {
    const accType = (acc.account_type || "").toLowerCase();
    const grpCode = (acc.group_code || "").toUpperCase();
    if (isCash) {
      return accType === "cash" || grpCode === "GRP_CASH" || acc.code === "CASH";
    } else {
      return accType === "bank" || grpCode === "GRP_BANK" || grpCode === "GRP_BANK_OD" || (acc.code || "").startsWith("BANK");
    }
  });

  const listToUse = filtered.length > 0 ? filtered : cashAndBankAccounts;
  listToUse.forEach(acc => {
    const opt = document.createElement("option");
    opt.value = acc.id;
    opt.textContent = `${acc.name} (${acc.code || acc.account_type})`;
    sel.appendChild(opt);
  });
}

// -----------------------------------------------------------------------------
// 1. Customer Receipt Form Controller
// -----------------------------------------------------------------------------
function initCustomerReceiptScreen(preselectedCustomerId = null) {
  const dateInp = document.getElementById("rct-date");
  if (dateInp && !dateInp.value) {
    const today = new Date().toISOString().split("T")[0];
    dateInp.value = today;
  }

  // Peek voucher number
  if (window.backend && window.backend.traditional_getNextReceiptNumber) {
    window.backend.traditional_getNextReceiptNumber("RCT", (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const numEl = document.getElementById("rct-number");
          if (numEl) numEl.value = res.data.voucher_number || "RCT-001";
        }
      } catch (e) {
        console.error("Error peeking receipt number:", e);
      }
    });
  }

  // Load accounts and populate
  loadCashAndBankAccounts(() => {
    const pm = document.getElementById("rct-payment-method") ? document.getElementById("rct-payment-method").value : "CASH";
    populateAccountsDropdown("rct-deposit-account", pm);
  });

  // Populate customers
  if (window.backend && window.backend.traditional_listCustomers) {
    window.backend.traditional_listCustomers("", true, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && Array.isArray(res.data)) {
          const sel = document.getElementById("rct-customer-select");
          if (sel) {
            sel.innerHTML = '<option value="">-- Select Customer --</option>';
            res.data.forEach(c => {
              const opt = document.createElement("option");
              opt.value = c.id;
              opt.textContent = `${c.name} (${c.code || "CUST"})`;
              sel.appendChild(opt);
            });
            if (preselectedCustomerId) {
              sel.value = preselectedCustomerId;
              onCustomerReceiptCustomerChanged();
            }
          }
        }
      } catch (e) {
        console.error("Error listing customers for receipt:", e);
      }
    });
  }
}

function onCustomerReceiptCustomerChanged() {
  const sel = document.getElementById("rct-customer-select");
  const custId = sel ? sel.value : "";
  const nameEl = document.getElementById("rct-disp-cust-name");
  const codeEl = document.getElementById("rct-disp-cust-code");
  const arEl = document.getElementById("rct-disp-ledger-ar");
  const advEl = document.getElementById("rct-disp-advances");
  const countEl = document.getElementById("rct-disp-unpaid-count");
  const tbody = document.getElementById("rct-invoices-tbody");
  const emptyMsg = document.getElementById("rct-invoices-empty");

  if (!custId) {
    if (nameEl) nameEl.textContent = "None Selected";
    if (codeEl) codeEl.textContent = "";
    if (arEl) arEl.textContent = "₹ 0.00";
    if (advEl) advEl.textContent = "₹ 0.00";
    if (countEl) countEl.textContent = "0";
    if (tbody) tbody.innerHTML = "";
    if (emptyMsg) emptyMsg.style.display = "block";
    currentReceiptInvoices = [];
    recalculateReceiptSummary();
    return;
  }

  // Load customer position
  if (window.backend && window.backend.traditional_getCustomerOutstanding) {
    window.backend.traditional_getCustomerOutstanding(custId, "", (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const d = res.data;
          if (nameEl) nameEl.textContent = d.customer_name || "Customer";
          if (codeEl) codeEl.textContent = d.customer_code ? `(${d.customer_code})` : "";
          if (arEl) {
            const arVal = parseFloat(d.net_ledger_outstanding || 0);
            arEl.textContent = formatMoney(arVal);
            arEl.style.color = arVal > 0 ? "#b91c1c" : "#15803d";
          }
          if (advEl) advEl.textContent = formatMoney(d.total_unallocated_advances || 0);
          if (countEl) countEl.textContent = d.unpaid_invoices_count || 0;
        }
      } catch (e) {
        console.error("Error fetching customer outstanding:", e);
      }
    });
  }

  // Load unsettled invoices
  if (window.backend && window.backend.traditional_getCustomerInvoices) {
    window.backend.traditional_getCustomerInvoices(custId, "", (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && Array.isArray(res.data)) {
          currentReceiptInvoices = res.data;
          renderInvoiceAllocationsGrid();
        } else {
          currentReceiptInvoices = [];
          renderInvoiceAllocationsGrid();
        }
      } catch (e) {
        console.error("Error fetching customer invoices:", e);
        currentReceiptInvoices = [];
        renderInvoiceAllocationsGrid();
      }
    });
  }
}

function renderInvoiceAllocationsGrid() {
  const tbody = document.getElementById("rct-invoices-tbody");
  const emptyMsg = document.getElementById("rct-invoices-empty");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!currentReceiptInvoices || currentReceiptInvoices.length === 0) {
    if (emptyMsg) {
      emptyMsg.textContent = "No unpaid invoices found for this customer. Any amount entered will be recorded as unallocated Customer Advance.";
      emptyMsg.style.display = "block";
    }
    recalculateReceiptSummary();
    return;
  }

  if (emptyMsg) emptyMsg.style.display = "none";

  currentReceiptInvoices.forEach((inv, idx) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="text-align: center; color: #64748b;">${idx + 1}</td>
      <td style="font-weight: 700; color: #1e3a8a;">${inv.voucher_number || "INV"}</td>
      <td>${inv.vch_date || ""}</td>
      <td style="text-align: right;">${formatMoney(inv.grand_total)}</td>
      <td style="text-align: right; font-weight: 700; color: #b91c1c;">${formatMoney(inv.outstanding_amount)}</td>
      <td style="text-align: right;">
        <input type="number" step="0.01" min="0" max="${inv.outstanding_amount}" value="0.00" class="input-meta-compact rct-alloc-input" data-inv-id="${inv.invoice_id}" data-due="${inv.outstanding_amount}" style="text-align: right; width: 110px; font-weight: 700;" />
      </td>
      <td style="text-align: right;">
        <input type="number" step="0.01" min="0" value="0.00" class="input-meta-compact rct-disc-input" data-inv-id="${inv.invoice_id}" style="text-align: right; width: 90px;" />
      </td>
      <td style="text-align: right; font-weight: 700;" id="rct-bal-after-${inv.invoice_id}">${formatMoney(inv.outstanding_amount)}</td>
    `;
    tbody.appendChild(tr);
  });

  // Attach input event listeners for dynamic recalculation
  tbody.querySelectorAll(".rct-alloc-input, .rct-disc-input").forEach(inp => {
    inp.addEventListener("input", recalculateReceiptSummary);
  });

  recalculateReceiptSummary();
}

function recalculateReceiptSummary() {
  const totalReceived = parseFloat(document.getElementById("rct-total-amount")?.value || 0);
  let totalAllocated = 0;
  let totalDiscount = 0;

  document.querySelectorAll(".rct-alloc-input").forEach(inp => {
    const alloc = parseFloat(inp.value || 0);
    const due = parseFloat(inp.dataset.due || 0);
    const invId = inp.dataset.invId;
    const discInp = document.querySelector(`.rct-disc-input[data-inv-id="${invId}"]`);
    const disc = parseFloat(discInp?.value || 0);

    totalAllocated += alloc;
    totalDiscount += disc;

    const balAfter = Math.max(0, due - alloc - disc);
    const balEl = document.getElementById(`rct-bal-after-${invId}`);
    if (balEl) {
      balEl.textContent = formatMoney(balAfter);
      balEl.style.color = balAfter === 0 ? "#15803d" : "#334155";
    }
  });

  const unallocatedAdvance = Math.max(0, totalReceived - totalAllocated);

  const sumTotalEl = document.getElementById("rct-sum-total");
  const sumAllocEl = document.getElementById("rct-sum-allocated");
  const sumDiscEl = document.getElementById("rct-sum-discount");
  const sumAdvEl = document.getElementById("rct-sum-advance");

  if (sumTotalEl) sumTotalEl.textContent = formatMoney(totalReceived);
  if (sumAllocEl) sumAllocEl.textContent = formatMoney(totalAllocated);
  if (sumDiscEl) sumDiscEl.textContent = formatMoney(totalDiscount);
  if (sumAdvEl) sumAdvEl.textContent = formatMoney(unallocatedAdvance);
}

function autoAllocateCustomerReceipt() {
  const totalAmount = parseFloat(document.getElementById("rct-total-amount")?.value || 0);
  if (totalAmount <= 0) {
    if (typeof showNotification === "function") {
      showNotification("Please enter a Total Amount Received (₹) first.", "warning");
    }
    const totInp = document.getElementById("rct-total-amount");
    if (totInp) totInp.focus();
    return;
  }

  let remaining = totalAmount;
  document.querySelectorAll(".rct-alloc-input").forEach(inp => {
    const due = parseFloat(inp.dataset.due || 0);
    if (remaining > 0) {
      const alloc = Math.min(remaining, due);
      inp.value = alloc.toFixed(2);
      remaining -= alloc;
    } else {
      inp.value = "0.00";
    }
  });

  recalculateReceiptSummary();
}

function clearReceiptAllocations() {
  document.querySelectorAll(".rct-alloc-input").forEach(inp => inp.value = "0.00");
  document.querySelectorAll(".rct-disc-input").forEach(inp => inp.value = "0.00");
  recalculateReceiptSummary();
}

function saveCustomerReceipt() {
  const custSelect = document.getElementById("rct-customer-select");
  const custId = custSelect ? custSelect.value : "";
  const dateInp = document.getElementById("rct-date");
  const rctDate = dateInp ? dateInp.value : "";
  const totalInp = document.getElementById("rct-total-amount");
  const totalAmount = parseFloat(totalInp?.value || 0);
  const methodSelect = document.getElementById("rct-payment-method");
  const method = methodSelect ? methodSelect.value : "CASH";
  const depositSelect = document.getElementById("rct-deposit-account");
  const depositAccId = depositSelect ? depositSelect.value : "";
  const refNo = document.getElementById("rct-ref-number")?.value.trim() || null;
  const refDate = document.getElementById("rct-ref-date")?.value || null;
  const narration = document.getElementById("rct-narration")?.value.trim() || null;

  if (!custId) {
    showNotification("Please select a customer.", "warning");
    if (custSelect) custSelect.focus();
    return;
  }
  if (!rctDate) {
    showNotification("Please enter a valid receipt date.", "warning");
    if (dateInp) dateInp.focus();
    return;
  }
  if (totalAmount <= 0) {
    showNotification("Receipt total amount must be greater than zero.", "warning");
    if (totalInp) totalInp.focus();
    return;
  }
  if (!depositAccId) {
    showNotification("Please select a deposit ledger account.", "warning");
    if (depositSelect) depositSelect.focus();
    return;
  }

  // Collect allocations
  const allocations = [];
  let sumAlloc = 0;
  let validationError = null;

  document.querySelectorAll(".rct-alloc-input").forEach(inp => {
    const val = parseFloat(inp.value || 0);
    const due = parseFloat(inp.dataset.due || 0);
    const invId = inp.dataset.invId;
    const discInp = document.querySelector(`.rct-disc-input[data-inv-id="${invId}"]`);
    const discVal = parseFloat(discInp?.value || 0);

    if (val > due) {
      validationError = `Allocation for invoice exceeds current due amount (${val} > ${due}).`;
    }
    if (val > 0 || discVal > 0) {
      sumAlloc += val;
      allocations.push({
        invoice_id: invId,
        allocated_amount: val,
        discount_amount: discVal
      });
    }
  });

  if (validationError) {
    showNotification(validationError, "error");
    return;
  }
  if (sumAlloc > totalAmount) {
    showNotification(`Total allocated amount (${formatMoney(sumAlloc)}) exceeds total received (${formatMoney(totalAmount)}).`, "error");
    return;
  }

  const payload = {
    customer_id: custId,
    receipt_date: rctDate,
    total_amount: totalAmount,
    payment_method: method,
    deposit_account_id: depositAccId,
    reference_number: refNo,
    reference_date: refDate,
    notes: narration,
    allocations: allocations
  };

  const btnSave = document.getElementById("btn-rct-save");
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.textContent = "Posting Receipt...";
  }

  if (window.backend && window.backend.traditional_createCustomerReceipt) {
    window.backend.traditional_createCustomerReceipt(JSON.stringify(payload), (resStr) => {
      if (btnSave) {
        btnSave.disabled = false;
        btnSave.textContent = "Post Receipt (F2)";
      }
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          showNotification(`Customer Receipt ${res.data.voucher_number} posted successfully!`, "success");
          openVoucherPrintModal(res.data, "RECEIPT");
          resetCustomerReceiptForm();
        } else {
          showNotification(`Receipt failed: ${res.error || "Unknown error"}`, "error");
        }
      } catch (e) {
        console.error("Error creating receipt:", e);
        showNotification("An error occurred while posting the customer receipt.", "error");
      }
    });
  }
}

function resetCustomerReceiptForm() {
  const totInp = document.getElementById("rct-total-amount");
  if (totInp) totInp.value = "";
  const refInp = document.getElementById("rct-ref-number");
  if (refInp) refInp.value = "";
  const refDateInp = document.getElementById("rct-ref-date");
  if (refDateInp) refDateInp.value = "";
  const narrInp = document.getElementById("rct-narration");
  if (narrInp) narrInp.value = "";
  const custSel = document.getElementById("rct-customer-select");
  if (custSel) custSel.value = "";
  onCustomerReceiptCustomerChanged();
  initCustomerReceiptScreen();
}

// -----------------------------------------------------------------------------
// 2. Customer Receipts Register Controller
// -----------------------------------------------------------------------------
function renderCustomerReceiptsRegister() {
  const search = document.getElementById("rct-list-search")?.value.trim() || "";
  const fromDate = document.getElementById("rct-list-from-date")?.value || "";
  const toDate = document.getElementById("rct-list-to-date")?.value || "";
  const status = document.getElementById("rct-list-status")?.value || "";
  const tbody = document.getElementById("receipts-register-tbody");
  const emptyMsg = document.getElementById("receipts-register-empty");

  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 20px; color: #64748b;">Loading receipts register...</td></tr>';

  if (window.backend && window.backend.traditional_listCustomerReceipts) {
    window.backend.traditional_listCustomerReceipts("", fromDate, toDate, status, search, 100, 0, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const receipts = res.data.receipts || [];
          tbody.innerHTML = "";

          if (receipts.length === 0) {
            if (emptyMsg) emptyMsg.style.display = "block";
            updateReceiptsRegisterSummary(0, 0, 0);
            return;
          }

          if (emptyMsg) emptyMsg.style.display = "none";
          let totalReceivedSum = 0;
          let totalAdvanceSum = 0;

          receipts.forEach((r, idx) => {
            const tr = document.createElement("tr");
            const isReversed = r.status === "REVERSED";
            const tot = parseFloat(r.total_amount || 0);
            const adv = parseFloat(r.unallocated_amount || 0);
            if (!isReversed) {
              totalReceivedSum += tot;
              totalAdvanceSum += adv;
            }

            const statusBadge = isReversed
              ? '<span style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px;">REVERSED</span>'
              : '<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px;">POSTED</span>';

            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td>${r.receipt_date || ""}</td>
              <td style="font-weight: 800; color: #1e3a8a;">${r.voucher_number || ""}</td>
              <td><strong>${r.customer_name || "Customer"}</strong> <span style="color: #64748b; font-size: 11px;">(${r.customer_code || ""})</span></td>
              <td>${r.payment_method || ""}</td>
              <td style="text-align: right; font-weight: 700;">${formatMoney(r.total_amount)}</td>
              <td style="text-align: right; color: #15803d;">${formatMoney(r.allocated_amount)}</td>
              <td style="text-align: right; color: #7c3aed; font-weight: 700;">${formatMoney(r.unallocated_amount)}</td>
              <td style="text-align: center;">${statusBadge}</td>
              <td style="text-align: center;">
                <div style="display: flex; gap: 4px; justify-content: center;">
                  <button type="button" class="btn-classic btn-sm btn-view-rct" data-id="${r.id}" style="padding: 2px 8px; font-size: 11px;">View</button>
                  ${!isReversed ? `<button type="button" class="btn-classic btn-sm btn-reverse-rct" data-id="${r.id}" data-num="${r.voucher_number}" data-party="${r.customer_name || ""}" data-amount="${formatMoney(r.total_amount)}" style="padding: 2px 8px; font-size: 11px; color: #dc2626;">Reverse</button>` : ''}
                  <button type="button" class="btn-classic btn-sm btn-print-rct" data-id="${r.id}" style="padding: 2px 8px; font-size: 11px;">Print</button>
                </div>
              </td>
            `;
            tbody.appendChild(tr);
          });

          // Bind row action buttons
          tbody.querySelectorAll(".btn-view-rct").forEach(b => {
            b.addEventListener("click", () => openVoucherDetailsModal("RECEIPT", b.dataset.id));
          });
          tbody.querySelectorAll(".btn-reverse-rct").forEach(b => {
            b.addEventListener("click", () => openReversalModal("RECEIPT", b.dataset.id, b.dataset.num, b.dataset.party, b.dataset.amount));
          });
          tbody.querySelectorAll(".btn-print-rct").forEach(b => {
            b.addEventListener("click", () => {
              if (window.backend && window.backend.traditional_getCustomerReceipt) {
                window.backend.traditional_getCustomerReceipt(b.dataset.id, (vStr) => {
                  try {
                    const vr = JSON.parse(vStr);
                    if (vr.success && vr.data) openVoucherPrintModal(vr.data, "RECEIPT");
                  } catch (e) {
                    console.error("Error loading receipt for print:", e);
                  }
                });
              }
            });
          });

          updateReceiptsRegisterSummary(receipts.length, totalReceivedSum, totalAdvanceSum);
        }
      } catch (e) {
        console.error("Error rendering receipts register:", e);
      }
    });
  }
}

function updateReceiptsRegisterSummary(count, totalReceived, totalAdvance) {
  const countEl = document.getElementById("rct-list-count");
  const totEl = document.getElementById("rct-list-total-sum");
  const advEl = document.getElementById("rct-list-advance-sum");
  if (countEl) countEl.textContent = `Receipts: ${count}`;
  if (totEl) totEl.textContent = formatMoney(totalReceived);
  if (advEl) advEl.textContent = formatMoney(totalAdvance);
}

// -----------------------------------------------------------------------------
// 3. Supplier Payment Form Controller
// -----------------------------------------------------------------------------
function initSupplierPaymentScreen(preselectedSupplierId = null) {
  const dateInp = document.getElementById("pmt-date");
  if (dateInp && !dateInp.value) {
    const today = new Date().toISOString().split("T")[0];
    dateInp.value = today;
  }

  // Peek payment voucher number
  if (window.backend && window.backend.traditional_getNextPaymentNumber) {
    window.backend.traditional_getNextPaymentNumber("PMT", (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const numEl = document.getElementById("pmt-number");
          if (numEl) numEl.value = res.data.voucher_number || "PMT-001";
        }
      } catch (e) {
        console.error("Error peeking payment number:", e);
      }
    });
  }

  // Load accounts and populate
  loadCashAndBankAccounts(() => {
    const pm = document.getElementById("pmt-payment-method") ? document.getElementById("pmt-payment-method").value : "CASH";
    populateAccountsDropdown("pmt-source-account", pm);
  });

  // Populate suppliers
  if (window.backend && window.backend.traditional_listSuppliers) {
    window.backend.traditional_listSuppliers("", true, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && Array.isArray(res.data)) {
          const sel = document.getElementById("pmt-supplier-select");
          if (sel) {
            sel.innerHTML = '<option value="">-- Select Supplier --</option>';
            res.data.forEach(s => {
              const opt = document.createElement("option");
              opt.value = s.id;
              opt.textContent = `${s.name} (${s.code || "SUPP"})`;
              sel.appendChild(opt);
            });
            if (preselectedSupplierId) {
              sel.value = preselectedSupplierId;
              onSupplierPaymentSupplierChanged();
            }
          }
        }
      } catch (e) {
        console.error("Error listing suppliers:", e);
      }
    });
  }
}

function onSupplierPaymentSupplierChanged() {
  const sel = document.getElementById("pmt-supplier-select");
  const suppId = sel ? sel.value : "";
  const nameEl = document.getElementById("pmt-disp-supp-name");
  const codeEl = document.getElementById("pmt-disp-supp-code");
  const apEl = document.getElementById("pmt-disp-ledger-ap");
  const advEl = document.getElementById("pmt-disp-advances");

  if (!suppId) {
    if (nameEl) nameEl.textContent = "None Selected";
    if (codeEl) codeEl.textContent = "";
    if (apEl) apEl.textContent = "₹ 0.00";
    if (advEl) advEl.textContent = "₹ 0.00";
    recalculatePaymentSummary();
    return;
  }

  // Load supplier position
  if (window.backend && window.backend.traditional_getSupplierOutstanding) {
    window.backend.traditional_getSupplierOutstanding(suppId, "", (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const d = res.data;
          if (nameEl) nameEl.textContent = d.supplier_name || "Supplier";
          if (codeEl) codeEl.textContent = d.supplier_code ? `(${d.supplier_code})` : "";
          if (apEl) {
            const apVal = parseFloat(d.net_ledger_payable || 0);
            apEl.textContent = formatMoney(apVal);
            apEl.style.color = apVal > 0 ? "#b91c1c" : "#15803d";
          }
          if (advEl) advEl.textContent = formatMoney(d.total_unallocated_advances || 0);
        }
      } catch (e) {
        console.error("Error fetching supplier outstanding:", e);
      }
    });
  }

  recalculatePaymentSummary();
}

function recalculatePaymentSummary() {
  const total = parseFloat(document.getElementById("pmt-total-amount")?.value || 0);
  const sumTotalEl = document.getElementById("pmt-sum-total");
  const sumAdvEl = document.getElementById("pmt-sum-advance");
  if (sumTotalEl) sumTotalEl.textContent = formatMoney(total);
  if (sumAdvEl) sumAdvEl.textContent = formatMoney(total);
}

function saveSupplierPayment() {
  const suppSelect = document.getElementById("pmt-supplier-select");
  const suppId = suppSelect ? suppSelect.value : "";
  const dateInp = document.getElementById("pmt-date");
  const pmtDate = dateInp ? dateInp.value : "";
  const totalInp = document.getElementById("pmt-total-amount");
  const totalAmount = parseFloat(totalInp?.value || 0);
  const methodSelect = document.getElementById("pmt-payment-method");
  const method = methodSelect ? methodSelect.value : "CASH";
  const sourceSelect = document.getElementById("pmt-source-account");
  const sourceAccId = sourceSelect ? sourceSelect.value : "";
  const refNo = document.getElementById("pmt-ref-number")?.value.trim() || null;
  const refDate = document.getElementById("pmt-ref-date")?.value || null;
  const narration = document.getElementById("pmt-narration")?.value.trim() || null;

  if (!suppId) {
    showNotification("Please select a supplier.", "warning");
    if (suppSelect) suppSelect.focus();
    return;
  }
  if (!pmtDate) {
    showNotification("Please enter a valid payment date.", "warning");
    if (dateInp) dateInp.focus();
    return;
  }
  if (totalAmount <= 0) {
    showNotification("Payment total amount must be greater than zero.", "warning");
    if (totalInp) totalInp.focus();
    return;
  }
  if (!sourceAccId) {
    showNotification("Please select a source payment account.", "warning");
    if (sourceSelect) sourceSelect.focus();
    return;
  }

  const payload = {
    supplier_id: suppId,
    payment_date: pmtDate,
    total_amount: totalAmount,
    payment_method: method,
    payment_account_id: sourceAccId,
    reference_number: refNo,
    reference_date: refDate,
    notes: narration,
    allocations: []
  };

  const btnSave = document.getElementById("btn-pmt-save");
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.textContent = "Disbursing Payment...";
  }

  if (window.backend && window.backend.traditional_createSupplierPayment) {
    window.backend.traditional_createSupplierPayment(JSON.stringify(payload), (resStr) => {
      if (btnSave) {
        btnSave.disabled = false;
        btnSave.textContent = "Disburse Payment (F2)";
      }
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          showNotification(`Supplier Payment ${res.data.voucher_number} posted successfully!`, "success");
          openVoucherPrintModal(res.data, "PAYMENT");
          resetSupplierPaymentForm();
        } else {
          showNotification(`Payment failed: ${res.error || "Unknown error"}`, "error");
        }
      } catch (e) {
        console.error("Error creating payment:", e);
        showNotification("An error occurred while disbursing the supplier payment.", "error");
      }
    });
  }
}

function resetSupplierPaymentForm() {
  const totInp = document.getElementById("pmt-total-amount");
  if (totInp) totInp.value = "";
  const refInp = document.getElementById("pmt-ref-number");
  if (refInp) refInp.value = "";
  const refDateInp = document.getElementById("pmt-ref-date");
  if (refDateInp) refDateInp.value = "";
  const narrInp = document.getElementById("pmt-narration");
  if (narrInp) narrInp.value = "";
  const suppSel = document.getElementById("pmt-supplier-select");
  if (suppSel) suppSel.value = "";
  onSupplierPaymentSupplierChanged();
  initSupplierPaymentScreen();
}

// -----------------------------------------------------------------------------
// 4. Supplier Payments Register Controller
// -----------------------------------------------------------------------------
function renderSupplierPaymentsRegister() {
  const search = document.getElementById("pmt-list-search")?.value.trim() || "";
  const fromDate = document.getElementById("pmt-list-from-date")?.value || "";
  const toDate = document.getElementById("pmt-list-to-date")?.value || "";
  const status = document.getElementById("pmt-list-status")?.value || "";
  const tbody = document.getElementById("payments-register-tbody");
  const emptyMsg = document.getElementById("payments-register-empty");

  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 20px; color: #64748b;">Loading payments register...</td></tr>';

  if (window.backend && window.backend.traditional_listSupplierPayments) {
    window.backend.traditional_listSupplierPayments("", fromDate, toDate, status, search, 100, 0, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const payments = res.data.payments || [];
          tbody.innerHTML = "";

          if (payments.length === 0) {
            if (emptyMsg) emptyMsg.style.display = "block";
            updatePaymentsRegisterSummary(0, 0, 0);
            return;
          }

          if (emptyMsg) emptyMsg.style.display = "none";
          let totalDisbursedSum = 0;
          let totalAdvanceSum = 0;

          payments.forEach((p, idx) => {
            const tr = document.createElement("tr");
            const isReversed = p.status === "REVERSED";
            const tot = parseFloat(p.total_amount || 0);
            const adv = parseFloat(p.unallocated_amount || 0);
            if (!isReversed) {
              totalDisbursedSum += tot;
              totalAdvanceSum += adv;
            }

            const statusBadge = isReversed
              ? '<span style="background: #fee2e2; color: #991b1b; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px;">REVERSED</span>'
              : '<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-weight: 800; font-size: 11px;">POSTED</span>';

            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td>${p.payment_date || ""}</td>
              <td style="font-weight: 800; color: #1e3a8a;">${p.voucher_number || ""}</td>
              <td><strong>${p.supplier_name || "Supplier"}</strong> <span style="color: #64748b; font-size: 11px;">(${p.supplier_code || ""})</span></td>
              <td>${p.payment_method || ""}</td>
              <td style="text-align: right; font-weight: 700; color: #b91c1c;">${formatMoney(p.total_amount)}</td>
              <td style="text-align: right;">${formatMoney(p.allocated_amount)}</td>
              <td style="text-align: right; color: #7c3aed; font-weight: 700;">${formatMoney(p.unallocated_amount)}</td>
              <td style="text-align: center;">${statusBadge}</td>
              <td style="text-align: center;">
                <div style="display: flex; gap: 4px; justify-content: center;">
                  <button type="button" class="btn-classic btn-sm btn-view-pmt" data-id="${p.id}" style="padding: 2px 8px; font-size: 11px;">View</button>
                  ${!isReversed ? `<button type="button" class="btn-classic btn-sm btn-reverse-pmt" data-id="${p.id}" data-num="${p.voucher_number}" data-party="${p.supplier_name || ""}" data-amount="${formatMoney(p.total_amount)}" style="padding: 2px 8px; font-size: 11px; color: #dc2626;">Reverse</button>` : ''}
                  <button type="button" class="btn-classic btn-sm btn-print-pmt" data-id="${p.id}" style="padding: 2px 8px; font-size: 11px;">Print</button>
                </div>
              </td>
            `;
            tbody.appendChild(tr);
          });

          tbody.querySelectorAll(".btn-view-pmt").forEach(b => {
            b.addEventListener("click", () => openVoucherDetailsModal("PAYMENT", b.dataset.id));
          });
          tbody.querySelectorAll(".btn-reverse-pmt").forEach(b => {
            b.addEventListener("click", () => openReversalModal("PAYMENT", b.dataset.id, b.dataset.num, b.dataset.party, b.dataset.amount));
          });
          tbody.querySelectorAll(".btn-print-pmt").forEach(b => {
            b.addEventListener("click", () => {
              if (window.backend && window.backend.traditional_getSupplierPayment) {
                window.backend.traditional_getSupplierPayment(b.dataset.id, (vStr) => {
                  try {
                    const vr = JSON.parse(vStr);
                    if (vr.success && vr.data) openVoucherPrintModal(vr.data, "PAYMENT");
                  } catch (e) {
                    console.error("Error loading payment for print:", e);
                  }
                });
              }
            });
          });

          updatePaymentsRegisterSummary(payments.length, totalDisbursedSum, totalAdvanceSum);
        }
      } catch (e) {
        console.error("Error rendering payments register:", e);
      }
    });
  }
}

function updatePaymentsRegisterSummary(count, totalDisbursed, totalAdvance) {
  const countEl = document.getElementById("pmt-list-count");
  const totEl = document.getElementById("pmt-list-total-sum");
  const advEl = document.getElementById("pmt-list-advance-sum");
  if (countEl) countEl.textContent = `Payments: ${count}`;
  if (totEl) totEl.textContent = formatMoney(totalDisbursed);
  if (advEl) advEl.textContent = formatMoney(totalAdvance);
}

// -----------------------------------------------------------------------------
// 5. Customer Outstanding View (Accounts Receivable)
// -----------------------------------------------------------------------------
function renderCustomerOutstandingView() {
  const asOfDate = document.getElementById("cust-out-as-of-date")?.value || "";
  const search = (document.getElementById("cust-out-search")?.value || "").toLowerCase().trim();
  const tbody = document.getElementById("cust-out-tbody");
  const emptyMsg = document.getElementById("cust-out-empty");

  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 20px; color: #64748b;">Calculating accounts receivable...</td></tr>';

  if (window.backend && window.backend.traditional_listCustomersOutstanding) {
    window.backend.traditional_listCustomersOutstanding(asOfDate, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          let customers = res.data.customers || [];
          if (search) {
            customers = customers.filter(c =>
              (c.customer_name || "").toLowerCase().includes(search) ||
              (c.customer_code || "").toLowerCase().includes(search) ||
              (c.phone || "").toLowerCase().includes(search) ||
              (c.gstin || "").toLowerCase().includes(search)
            );
          }

          tbody.innerHTML = "";
          if (customers.length === 0) {
            if (emptyMsg) emptyMsg.style.display = "block";
            const cntEl = document.getElementById("cust-out-count");
            const totEl = document.getElementById("cust-out-total-sum");
            if (cntEl) cntEl.textContent = "Total Customers: 0";
            if (totEl) totEl.textContent = "₹ 0.00";
            return;
          }

          if (emptyMsg) emptyMsg.style.display = "none";
          let totalAR = 0;

          customers.forEach((c, idx) => {
            const tr = document.createElement("tr");
            const outAmt = parseFloat(c.outstanding_amount || 0);
            totalAR += outAmt;

            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td style="font-weight: 700; color: #1e3a8a;">${c.customer_code || ""}</td>
              <td><strong>${c.customer_name || "Customer"}</strong></td>
              <td>${c.phone || "-"}</td>
              <td>${c.gstin || "-"}</td>
              <td style="text-align: right;">${formatMoney(c.total_billed)}</td>
              <td style="text-align: right; color: #15803d;">${formatMoney(c.total_paid)}</td>
              <td style="text-align: right; font-weight: 800; color: ${outAmt > 0 ? '#b91c1c' : '#15803d'};">${formatMoney(outAmt)}</td>
              <td style="text-align: center; font-weight: 700;">${c.balance_type || "Dr"}</td>
              <td style="text-align: center;">
                <button type="button" class="btn-classic btn-sm btn-cust-out-rct" data-id="${c.customer_id}" style="padding: 2px 8px; font-size: 11px; background: #15803d; color: #fff; font-weight: 700;">Receive</button>
              </td>
            `;
            tbody.appendChild(tr);
          });

          tbody.querySelectorAll(".btn-cust-out-rct").forEach(b => {
            b.addEventListener("click", () => {
              showScreen("view-customer-receipt");
              initCustomerReceiptScreen(b.dataset.id);
            });
          });

          const cntEl = document.getElementById("cust-out-count");
          const totEl = document.getElementById("cust-out-total-sum");
          if (cntEl) cntEl.textContent = `Total Customers: ${customers.length}`;
          if (totEl) totEl.textContent = formatMoney(totalAR);
        }
      } catch (e) {
        console.error("Error rendering customer outstandings:", e);
      }
    });
  }
}

// -----------------------------------------------------------------------------
// 6. Supplier Outstanding View (Accounts Payable)
// -----------------------------------------------------------------------------
function renderSupplierOutstandingView() {
  const asOfDate = document.getElementById("supp-out-as-of-date")?.value || "";
  const search = (document.getElementById("supp-out-search")?.value || "").toLowerCase().trim();
  const tbody = document.getElementById("supp-out-tbody");
  const emptyMsg = document.getElementById("supp-out-empty");

  if (!tbody) return;
  tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 20px; color: #64748b;">Calculating accounts payable...</td></tr>';

  if (window.backend && window.backend.traditional_listSuppliersOutstanding) {
    window.backend.traditional_listSuppliersOutstanding(asOfDate, (resStr) => {
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          let suppliers = res.data.suppliers || [];
          if (search) {
            suppliers = suppliers.filter(s =>
              (s.supplier_name || "").toLowerCase().includes(search) ||
              (s.supplier_code || "").toLowerCase().includes(search) ||
              (s.phone || "").toLowerCase().includes(search) ||
              (s.gstin || "").toLowerCase().includes(search)
            );
          }

          tbody.innerHTML = "";
          if (suppliers.length === 0) {
            if (emptyMsg) emptyMsg.style.display = "block";
            const cntEl = document.getElementById("supp-out-count");
            const totEl = document.getElementById("supp-out-total-sum");
            if (cntEl) cntEl.textContent = "Total Suppliers: 0";
            if (totEl) totEl.textContent = "₹ 0.00";
            return;
          }

          if (emptyMsg) emptyMsg.style.display = "none";
          let totalAP = 0;

          suppliers.forEach((s, idx) => {
            const tr = document.createElement("tr");
            const outAmt = parseFloat(s.outstanding_amount || 0);
            totalAP += outAmt;

            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td style="font-weight: 700; color: #78350f;">${s.supplier_code || ""}</td>
              <td><strong>${s.supplier_name || "Supplier"}</strong></td>
              <td>${s.phone || "-"}</td>
              <td>${s.gstin || "-"}</td>
              <td style="text-align: right;">${formatMoney(s.total_purchases)}</td>
              <td style="text-align: right; color: #15803d;">${formatMoney(s.total_paid)}</td>
              <td style="text-align: right; font-weight: 800; color: ${outAmt > 0 ? '#b91c1c' : '#15803d'};">${formatMoney(outAmt)}</td>
              <td style="text-align: center; font-weight: 700;">${s.balance_type || "Cr"}</td>
              <td style="text-align: center;">
                <button type="button" class="btn-classic btn-sm btn-supp-out-pmt" data-id="${s.supplier_id}" style="padding: 2px 8px; font-size: 11px; background: #b91c1c; color: #fff; font-weight: 700;">Pay</button>
              </td>
            `;
            tbody.appendChild(tr);
          });

          tbody.querySelectorAll(".btn-supp-out-pmt").forEach(b => {
            b.addEventListener("click", () => {
              showScreen("view-supplier-payment");
              initSupplierPaymentScreen(b.dataset.id);
            });
          });

          const cntEl = document.getElementById("supp-out-count");
          const totEl = document.getElementById("supp-out-total-sum");
          if (cntEl) cntEl.textContent = `Total Suppliers: ${suppliers.length}`;
          if (totEl) totEl.textContent = formatMoney(totalAP);
        }
      } catch (e) {
        console.error("Error rendering supplier outstandings:", e);
      }
    });
  }
}

// -----------------------------------------------------------------------------
// 7. Financial Reconciliation Dashboard Controller
// -----------------------------------------------------------------------------
function renderReconciliationDashboard() {
  const asOfDate = document.getElementById("recon-as-of-date")?.value || "";
  const runBtn = document.getElementById("btn-recon-run-audit");
  if (runBtn) {
    runBtn.disabled = true;
    runBtn.textContent = "Auditing Subledgers...";
  }

  if (window.backend && window.backend.traditional_getFinancialReconciliationSummary) {
    window.backend.traditional_getFinancialReconciliationSummary(asOfDate, (resStr) => {
      if (runBtn) {
        runBtn.disabled = false;
        runBtn.textContent = "Run Full Financial Audit";
      }
      try {
        const res = JSON.parse(resStr);
        if (res.success && res.data) {
          const d = res.data;
          const timeEl = document.getElementById("recon-last-audit-time");
          if (timeEl) timeEl.textContent = `Last audited: ${new Date().toLocaleTimeString()} (${d.as_of_date || "Today"})`;

          // Executive Banner
          const isBalanced = d.overall_status === "BALANCED";
          const bannerEl = document.getElementById("recon-executive-banner");
          const badgeEl = document.getElementById("recon-executive-badge");
          const titleEl = document.getElementById("recon-executive-title");
          const descEl = document.getElementById("recon-executive-desc");
          const scoreEl = document.getElementById("recon-executive-score");

          if (badgeEl) {
            badgeEl.textContent = d.overall_status || "BALANCED";
            badgeEl.style.background = isBalanced ? "#15803d" : "#dc2626";
          }
          if (bannerEl) {
            bannerEl.style.background = isBalanced ? "#f0fdf4" : "#fef2f2";
            bannerEl.style.borderColor = isBalanced ? "#86efac" : "#fecaca";
          }
          if (titleEl) {
            titleEl.textContent = isBalanced ? "Books & Subledgers Perfectly Balanced" : "Subledger Discrepancies Detected";
          }
          if (descEl) {
            descEl.textContent = isBalanced
              ? "All customer AR, supplier AP, cash/bank liquid movements and double-entry journals are 100% reconciled."
              : "Audit diagnostic has identified variance between General Ledger balances and transactional subledgers.";
          }
          if (scoreEl) {
            scoreEl.textContent = d.health_score || (isBalanced ? "100%" : "85%");
            scoreEl.style.color = isBalanced ? "#15803d" : "#dc2626";
          }

          // Card 1: AR
          const ar = d.customer_ar || {};
          setReconCardStatus("recon-ar-status", ar.status);
          setElText("recon-ar-gl", formatMoney(ar.gl_ar_balance));
          setElText("recon-ar-sub", formatMoney(ar.subledger_net_receivable));
          setElText("recon-ar-diff", formatMoney(ar.discrepancy));

          // Card 2: AP
          const ap = d.supplier_ap || {};
          setReconCardStatus("recon-ap-status", ap.status);
          setElText("recon-ap-gl", formatMoney(ap.gl_ap_balance));
          setElText("recon-ap-sub", formatMoney(ap.subledger_net_payable));
          setElText("recon-ap-diff", formatMoney(ap.discrepancy));

          // Card 3: Cash & Bank
          const cb = d.cash_and_bank || {};
          setReconCardStatus("recon-cb-status", cb.status);
          setElText("recon-cb-gl", formatMoney(cb.total_liquid_gl_balance));
          setElText("recon-cb-sub", formatMoney(cb.total_net_voucher_movement));
          setElText("recon-cb-diff", formatMoney(cb.discrepancy));

          // Card 4: Customer Advances
          const ca = d.customer_advances || {};
          setReconCardStatus("recon-adv-cust-status", ca.status);
          setElText("recon-adv-cust-vch", formatMoney(ca.unallocated_receipts_advances));
          setElText("recon-adv-cust-gl", formatMoney(ca.gl_advance_liability_balance));
          setElText("recon-adv-cust-diff", formatMoney(ca.discrepancy));

          // Card 5: Supplier Advances
          const sa = d.supplier_advances || {};
          setReconCardStatus("recon-adv-supp-status", sa.status);
          setElText("recon-adv-supp-vch", formatMoney(sa.unallocated_payments_advances));
          setElText("recon-adv-supp-gl", formatMoney(sa.gl_advance_asset_balance));
          setElText("recon-adv-supp-diff", formatMoney(sa.discrepancy));

          // Card 6: Journal Integrity
          const aud = d.journal_audit || {};
          setReconCardStatus("recon-audit-status", aud.status === "CLEAN" ? "CLEAN" : "ANOMALIES");
          setElText("recon-audit-orphan", aud.orphan_journals_count || "0");
          setElText("recon-audit-unbalanced", aud.unbalanced_lines_count || "0");
          setElText("recon-audit-total", aud.total_anomalies_count || "0");
        }
      } catch (e) {
        console.error("Error rendering reconciliation summary:", e);
      }
    });
  }
}

function setReconCardStatus(elementId, status) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const isOk = status === "BALANCED" || status === "CLEAN";
  el.textContent = status || "UNKNOWN";
  el.style.background = isOk ? "#dcfce7" : "#fee2e2";
  el.style.color = isOk ? "#15803d" : "#dc2626";
}

function setElText(id, txt) {
  const el = document.getElementById(id);
  if (el) el.textContent = txt;
}

// -----------------------------------------------------------------------------
// 8. Modals Controller (Details, Reversals, Print)
// -----------------------------------------------------------------------------
function openVoucherDetailsModal(type, voucherId) {
  const modal = document.getElementById("modal-voucher-details");
  if (!modal) return;

  const titleBadge = document.getElementById("vch-detail-type-badge");
  const titleEl = document.getElementById("vch-detail-title");
  if (titleBadge) {
    titleBadge.textContent = type;
    titleBadge.style.background = type === "RECEIPT" ? "#1e3a8a" : "#b91c1c";
  }

  const numEl = document.getElementById("vch-det-num");
  const dateEl = document.getElementById("vch-det-date");
  const partyEl = document.getElementById("vch-det-party");
  const methEl = document.getElementById("vch-det-method");
  const accEl = document.getElementById("vch-det-account");
  const refEl = document.getElementById("vch-det-ref");
  const statEl = document.getElementById("vch-det-status");
  const userEl = document.getElementById("vch-det-user");
  const totEl = document.getElementById("vch-det-total");
  const allocEl = document.getElementById("vch-det-allocated");
  const advEl = document.getElementById("vch-det-advance");
  const discEl = document.getElementById("vch-det-discount");
  const revAlert = document.getElementById("vch-det-reversal-alert");
  const revReason = document.getElementById("vch-det-reversal-reason");
  const tbody = document.getElementById("vch-det-alloc-tbody");
  const emptyAlloc = document.getElementById("vch-det-alloc-empty");

  const cb = (resStr) => {
    try {
      const res = JSON.parse(resStr);
      if (res.success && res.data) {
        const d = res.data;
        activePrintContext = { data: d, type: type };
        if (titleEl) titleEl.textContent = `Voucher Details: ${d.voucher_number || ""}`;
        if (numEl) numEl.textContent = d.voucher_number || "";
        if (dateEl) dateEl.textContent = d.receipt_date || d.payment_date || "";
        if (partyEl) partyEl.textContent = d.customer_name || d.supplier_name || "Party";
        if (methEl) methEl.textContent = d.payment_method || "";
        if (accEl) accEl.textContent = d.deposit_account_name || d.source_account_name || d.deposit_account_id || d.source_account_id || "";
        if (refEl) refEl.textContent = d.reference_number || "-";
        if (statEl) {
          const isRev = d.status === "REVERSED";
          statEl.textContent = d.status || "POSTED";
          statEl.style.background = isRev ? "#fee2e2" : "#dcfce7";
          statEl.style.color = isRev ? "#991b1b" : "#15803d";
        }
        if (userEl) userEl.textContent = d.created_by || "Administrator";
        if (totEl) totEl.textContent = formatMoney(d.total_amount);
        if (allocEl) allocEl.textContent = formatMoney(d.allocated_amount);
        if (advEl) advEl.textContent = formatMoney(d.unallocated_amount);
        if (discEl) discEl.textContent = formatMoney(d.discount_amount);

        if (d.status === "REVERSED") {
          if (revAlert) revAlert.style.display = "block";
          if (revReason) revReason.textContent = d.reversal_reason || "Reversed by authorized user.";
        } else {
          if (revAlert) revAlert.style.display = "none";
        }

        if (tbody) tbody.innerHTML = "";
        const allocs = d.allocations || [];
        if (allocs.length === 0) {
          if (emptyAlloc) emptyAlloc.style.display = "block";
        } else {
          if (emptyAlloc) emptyAlloc.style.display = "none";
          allocs.forEach((a, idx) => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
              <td style="text-align: center; color: #64748b;">${idx + 1}</td>
              <td style="font-weight: 700; color: #1e3a8a;">${a.invoice_number || a.bill_number || a.invoice_id || a.purchase_voucher_id || "Bill"}</td>
              <td style="text-align: right; font-weight: 700;">${formatMoney(a.allocated_amount)}</td>
              <td style="text-align: right; color: #b45309;">${formatMoney(a.discount_amount)}</td>
            `;
            tbody.appendChild(tr);
          });
        }

        openModal("modal-voucher-details");
      }
    } catch (e) {
      console.error("Error loading voucher details:", e);
    }
  };

  if (type === "RECEIPT" && window.backend && window.backend.traditional_getCustomerReceipt) {
    window.backend.traditional_getCustomerReceipt(voucherId, cb);
  } else if (type === "PAYMENT" && window.backend && window.backend.traditional_getSupplierPayment) {
    window.backend.traditional_getSupplierPayment(voucherId, cb);
  }
}

function openReversalModal(type, voucherId, voucherNumber, partyName, amount) {
  activeReversalContext = { type, id: voucherId, number: voucherNumber, party: partyName, amount };
  const numEl = document.getElementById("reversal-vch-num");
  const partyEl = document.getElementById("reversal-party-name");
  const amtEl = document.getElementById("reversal-amount");
  const reasonInp = document.getElementById("reversal-reason-input");

  if (numEl) numEl.textContent = voucherNumber;
  if (partyEl) partyEl.textContent = partyName;
  if (amtEl) amtEl.textContent = amount;
  if (reasonInp) {
    reasonInp.value = "";
    setTimeout(() => reasonInp.focus(), 50);
  }

  openModal("modal-reversal-confirm");
}

function executeVoucherReversal() {
  const reasonInp = document.getElementById("reversal-reason-input");
  const reason = reasonInp ? reasonInp.value.trim() : "";
  if (!reason) {
    showNotification("Reversal reason is mandatory for double-entry audit compliance.", "warning");
    if (reasonInp) reasonInp.focus();
    return;
  }

  const { type, id, number } = activeReversalContext;
  const btn = document.getElementById("btn-reversal-confirm");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Posting Reversal...";
  }

  const handleResponse = (resStr) => {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Confirm & Post Reversal";
    }
    try {
      const res = JSON.parse(resStr);
      if (res.success) {
        showNotification(`Voucher ${number} reversed successfully. Compensating journal entry posted.`, "success");
        closeModal("modal-reversal-confirm");
        if (type === "RECEIPT") renderCustomerReceiptsRegister();
        else if (type === "PAYMENT") renderSupplierPaymentsRegister();
      } else {
        showNotification(`Reversal failed: ${res.error || "Permission denied or invalid state"}`, "error");
      }
    } catch (e) {
      console.error("Error executing reversal:", e);
      showNotification("An error occurred during voucher reversal.", "error");
    }
  };

  if (type === "RECEIPT" && window.backend && window.backend.traditional_reverseCustomerReceipt) {
    window.backend.traditional_reverseCustomerReceipt(id, reason, handleResponse);
  } else if (type === "PAYMENT" && window.backend && window.backend.traditional_reverseSupplierPayment) {
    window.backend.traditional_reverseSupplierPayment(id, reason, handleResponse);
  }
}

function openVoucherPrintModal(vchData, type) {
  if (!vchData) return;
  activePrintContext = { data: vchData, type: type };

  const compName = window.activeCompany ? window.activeCompany.name : "ALPHA BILLING ENTERPRISE";
  const compAddr = window.activeCompany ? (window.activeCompany.address || "") : "Main Commercial Complex, City";
  const compGstin = window.activeCompany ? (window.activeCompany.gstin || "") : "27AABCA1234A1Z5";

  setElText("print-company-name", compName);
  setElText("print-company-address", compAddr);
  setElText("print-company-gstin", compGstin ? `GSTIN: ${compGstin}` : "");

  setElText("print-voucher-title", type === "RECEIPT" ? "CUSTOMER RECEIPT VOUCHER" : "SUPPLIER PAYMENT VOUCHER");
  setElText("print-vch-no", vchData.voucher_number || "");
  setElText("print-vch-date", vchData.receipt_date || vchData.payment_date || "");
  setElText("print-vch-mode", vchData.payment_method || "");
  setElText("print-vch-ref", vchData.reference_number || "-");
  setElText("print-vch-account", vchData.deposit_account_name || vchData.source_account_name || vchData.deposit_account_id || vchData.source_account_id || "");
  setElText("print-vch-status", vchData.status || "POSTED");

  setElText("print-party-name", vchData.customer_name || vchData.supplier_name || "Party");
  setElText("print-party-code", vchData.customer_code || vchData.supplier_code || "");
  setElText("print-party-phone", vchData.customer_phone || vchData.supplier_phone || "-");
  setElText("print-party-gstin", vchData.customer_gstin || vchData.supplier_gstin || "-");

  const allocTbody = document.getElementById("print-alloc-tbody");
  if (allocTbody) {
    allocTbody.innerHTML = "";
    const allocs = vchData.allocations || [];
    if (allocs.length === 0) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="padding: 4px 0;">On-Account / Advance Payment</td>
        <td style="text-align: right; padding: 4px 0;">${formatMoney(vchData.total_amount)}</td>
      `;
      allocTbody.appendChild(tr);
    } else {
      allocs.forEach(a => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="padding: 4px 0;">Settlement for Invoice: ${a.invoice_number || a.bill_number || a.invoice_id || a.purchase_voucher_id || "Bill"}</td>
          <td style="text-align: right; padding: 4px 0;">${formatMoney(a.allocated_amount)}</td>
        `;
        allocTbody.appendChild(tr);
      });
      if (parseFloat(vchData.unallocated_amount || 0) > 0) {
        const trAdv = document.createElement("tr");
        trAdv.innerHTML = `
          <td style="padding: 4px 0; font-style: italic;">Unallocated Customer Advance</td>
          <td style="text-align: right; padding: 4px 0;">${formatMoney(vchData.unallocated_amount)}</td>
        `;
        allocTbody.appendChild(trAdv);
      }
    }
  }

  setElText("print-total-amount", formatMoney(vchData.total_amount));
  setElText("print-amount-words", convertNumberToWords(vchData.total_amount));
  setElText("print-narration", vchData.notes || "None");

  openModal("modal-voucher-print");
}

function initPaymentAndReceiptModule() {
  // Navigation & Ribbon buttons
  const rctBack = document.getElementById("btn-rct-back");
  const rctClose = document.getElementById("btn-rct-close");
  if (rctBack) rctBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (rctClose) rctClose.addEventListener("click", () => showScreen("view-dashboard"));

  const rctListBack = document.getElementById("btn-rct-list-back");
  const rctListClose = document.getElementById("btn-rct-list-close");
  if (rctListBack) rctListBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (rctListClose) rctListClose.addEventListener("click", () => showScreen("view-dashboard"));

  const pmtBack = document.getElementById("btn-pmt-back");
  const pmtClose = document.getElementById("btn-pmt-close");
  if (pmtBack) pmtBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (pmtClose) pmtClose.addEventListener("click", () => showScreen("view-dashboard"));

  const pmtListBack = document.getElementById("btn-pmt-list-back");
  const pmtListClose = document.getElementById("btn-pmt-list-close");
  if (pmtListBack) pmtListBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (pmtListClose) pmtListClose.addEventListener("click", () => showScreen("view-dashboard"));

  const custOutBack = document.getElementById("btn-cust-out-back");
  const custOutClose = document.getElementById("btn-cust-out-close");
  if (custOutBack) custOutBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (custOutClose) custOutClose.addEventListener("click", () => showScreen("view-dashboard"));

  const suppOutBack = document.getElementById("btn-supp-out-back");
  const suppOutClose = document.getElementById("btn-supp-out-close");
  if (suppOutBack) suppOutBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (suppOutClose) suppOutClose.addEventListener("click", () => showScreen("view-dashboard"));

  const reconBack = document.getElementById("btn-recon-back");
  const reconClose = document.getElementById("btn-recon-close");
  if (reconBack) reconBack.addEventListener("click", () => showScreen("view-dashboard"));
  if (reconClose) reconClose.addEventListener("click", () => showScreen("view-dashboard"));

  // Customer Receipt Action buttons
  const btnRctAuto = document.getElementById("btn-rct-auto-allocate");
  if (btnRctAuto) btnRctAuto.addEventListener("click", autoAllocateCustomerReceipt);

  const btnRctClear = document.getElementById("btn-rct-clear-allocate");
  if (btnRctClear) btnRctClear.addEventListener("click", clearReceiptAllocations);

  const btnRctReset = document.getElementById("btn-rct-reset");
  if (btnRctReset) btnRctReset.addEventListener("click", resetCustomerReceiptForm);

  const btnRctSave = document.getElementById("btn-rct-save");
  if (btnRctSave) btnRctSave.addEventListener("click", saveCustomerReceipt);

  const rctCustSelect = document.getElementById("rct-customer-select");
  if (rctCustSelect) rctCustSelect.addEventListener("change", onCustomerReceiptCustomerChanged);

  const rctMethodSelect = document.getElementById("rct-payment-method");
  if (rctMethodSelect) {
    rctMethodSelect.addEventListener("change", (e) => {
      populateAccountsDropdown("rct-deposit-account", e.target.value);
    });
  }

  const rctTotalInp = document.getElementById("rct-total-amount");
  if (rctTotalInp) rctTotalInp.addEventListener("input", recalculateReceiptSummary);

  // Receipts Register Buttons
  const btnRctListRef = document.getElementById("btn-rct-list-refresh");
  if (btnRctListRef) btnRctListRef.addEventListener("click", renderCustomerReceiptsRegister);

  const btnRctListNew = document.getElementById("btn-rct-list-new");
  if (btnRctListNew) btnRctListNew.addEventListener("click", () => showScreen("view-customer-receipt"));

  const rctSearch = document.getElementById("rct-list-search");
  if (rctSearch) rctSearch.addEventListener("input", renderCustomerReceiptsRegister);

  const rctStatus = document.getElementById("rct-list-status");
  if (rctStatus) rctStatus.addEventListener("change", renderCustomerReceiptsRegister);

  // Supplier Payment Action buttons
  const btnPmtReset = document.getElementById("btn-pmt-reset");
  if (btnPmtReset) btnPmtReset.addEventListener("click", resetSupplierPaymentForm);

  const btnPmtSave = document.getElementById("btn-pmt-save");
  if (btnPmtSave) btnPmtSave.addEventListener("click", saveSupplierPayment);

  const pmtSuppSelect = document.getElementById("pmt-supplier-select");
  if (pmtSuppSelect) pmtSuppSelect.addEventListener("change", onSupplierPaymentSupplierChanged);

  const pmtMethodSelect = document.getElementById("pmt-payment-method");
  if (pmtMethodSelect) {
    pmtMethodSelect.addEventListener("change", (e) => {
      populateAccountsDropdown("pmt-source-account", e.target.value);
    });
  }

  const pmtTotalInp = document.getElementById("pmt-total-amount");
  if (pmtTotalInp) pmtTotalInp.addEventListener("input", recalculatePaymentSummary);

  // Payments Register Buttons
  const btnPmtListRef = document.getElementById("btn-pmt-list-refresh");
  if (btnPmtListRef) btnPmtListRef.addEventListener("click", renderSupplierPaymentsRegister);

  const btnPmtListNew = document.getElementById("btn-pmt-list-new");
  if (btnPmtListNew) btnPmtListNew.addEventListener("click", () => showScreen("view-supplier-payment"));

  const pmtSearch = document.getElementById("pmt-list-search");
  if (pmtSearch) pmtSearch.addEventListener("input", renderSupplierPaymentsRegister);

  const pmtStatus = document.getElementById("pmt-list-status");
  if (pmtStatus) pmtStatus.addEventListener("change", renderSupplierPaymentsRegister);

  // Outstandings & Recon Buttons
  const btnCustOutRef = document.getElementById("btn-cust-out-refresh");
  if (btnCustOutRef) btnCustOutRef.addEventListener("click", renderCustomerOutstandingView);

  const custOutSearch = document.getElementById("cust-out-search");
  if (custOutSearch) custOutSearch.addEventListener("input", renderCustomerOutstandingView);

  const btnSuppOutRef = document.getElementById("btn-supp-out-refresh");
  if (btnSuppOutRef) btnSuppOutRef.addEventListener("click", renderSupplierOutstandingView);

  const suppOutSearch = document.getElementById("supp-out-search");
  if (suppOutSearch) suppOutSearch.addEventListener("input", renderSupplierOutstandingView);

  const btnReconRun = document.getElementById("btn-recon-run-audit");
  if (btnReconRun) btnReconRun.addEventListener("click", renderReconciliationDashboard);

  // Modals buttons
  const btnCloseVchDet = document.getElementById("btn-close-voucher-details");
  const btnVchDetClose = document.getElementById("btn-vch-det-close");
  if (btnCloseVchDet) btnCloseVchDet.addEventListener("click", () => closeModal("modal-voucher-details"));
  if (btnVchDetClose) btnVchDetClose.addEventListener("click", () => closeModal("modal-voucher-details"));

  const btnVchDetPrint = document.getElementById("btn-vch-det-print");
  if (btnVchDetPrint) {
    btnVchDetPrint.addEventListener("click", () => {
      if (activePrintContext) {
        closeModal("modal-voucher-details");
        openVoucherPrintModal(activePrintContext.data, activePrintContext.type);
      }
    });
  }

  const btnCloseRev = document.getElementById("btn-close-reversal-modal");
  const btnRevCancel = document.getElementById("btn-reversal-cancel");
  if (btnCloseRev) btnCloseRev.addEventListener("click", () => closeModal("modal-reversal-confirm"));
  if (btnRevCancel) btnRevCancel.addEventListener("click", () => closeModal("modal-reversal-confirm"));

  const btnRevConfirm = document.getElementById("btn-reversal-confirm");
  if (btnRevConfirm) btnRevConfirm.addEventListener("click", executeVoucherReversal);

  const btnClosePrint = document.getElementById("btn-close-voucher-print");
  const btnPrintClose = document.getElementById("btn-print-slip-close");
  if (btnClosePrint) btnClosePrint.addEventListener("click", () => closeModal("modal-voucher-print"));
  if (btnPrintClose) btnPrintClose.addEventListener("click", () => closeModal("modal-voucher-print"));

  const btnPrintAction = document.getElementById("btn-print-slip-action");
  if (btnPrintAction) {
    btnPrintAction.addEventListener("click", () => {
      window.print();
    });
  }

  // Keyboard shortcuts (F2, F5, Esc)
  document.addEventListener("keydown", (e) => {
    if (e.key === "F2") {
      if (currentScreen === "view-customer-receipt") {
        e.preventDefault();
        saveCustomerReceipt();
      } else if (currentScreen === "view-supplier-payment") {
        e.preventDefault();
        saveSupplierPayment();
      } else if (currentScreen === "view-receipt-list") {
        e.preventDefault();
        showScreen("view-customer-receipt");
      } else if (currentScreen === "view-payment-list") {
        e.preventDefault();
        showScreen("view-supplier-payment");
      }
    } else if (e.key === "F5") {
      if (currentScreen === "view-customer-receipt") {
        e.preventDefault();
        showScreen("view-receipt-list");
      } else if (currentScreen === "view-supplier-payment") {
        e.preventDefault();
        showScreen("view-payment-list");
      } else if (currentScreen === "view-receipt-list") {
        e.preventDefault();
        renderCustomerReceiptsRegister();
      } else if (currentScreen === "view-payment-list") {
        e.preventDefault();
        renderSupplierPaymentsRegister();
      } else if (currentScreen === "view-customer-outstanding") {
        e.preventDefault();
        renderCustomerOutstandingView();
      } else if (currentScreen === "view-supplier-outstanding") {
        e.preventDefault();
        renderSupplierOutstandingView();
      } else if (currentScreen === "view-reconciliation-dashboard") {
        e.preventDefault();
        renderReconciliationDashboard();
      }
    } else if (e.key === "Escape") {
      const modalDet = document.getElementById("modal-voucher-details");
      const modalRev = document.getElementById("modal-reversal-confirm");
      const modalPrt = document.getElementById("modal-voucher-print");
      if (modalDet && modalDet.classList.contains("show")) {
        closeModal("modal-voucher-details");
        return;
      }
      if (modalRev && modalRev.classList.contains("show")) {
        closeModal("modal-reversal-confirm");
        return;
      }
      if (modalPrt && modalPrt.classList.contains("show")) {
        closeModal("modal-voucher-print");
        return;
      }
      const paymentScreens = [
        "view-customer-receipt", "view-receipt-list",
        "view-supplier-payment", "view-payment-list",
        "view-customer-outstanding", "view-supplier-outstanding",
        "view-reconciliation-dashboard"
      ];
      if (paymentScreens.includes(currentScreen)) {
        showScreen("view-dashboard");
      }
    }
  });
}


// Global Exports
window.syncItemPrintName = syncItemPrintName;
window.resetProductMasterForm = resetProductMasterForm;
window.handleSaveItemMaster = handleSaveItemMaster;
window.openAddProductMaster = openAddProductMaster;
window.loadProductForEditing = loadProductForEditing;
window.renderSelectAccountModifyModal = renderSelectAccountModifyModal;
window.renderSelectItemModifyModal = renderSelectItemModifyModal;
window.renderSelectSalesModifyModal = renderSelectSalesModifyModal;
window.renderSelectPurchaseModifyModal = renderSelectPurchaseModifyModal;
window.openAddAccountMaster = openAddAccountMaster;
window.openModifyAccountMaster = openModifyAccountMaster;
window.openModifySaleInvoice = openModifySaleInvoice;
window.openModifyPurchaseVoucher = openModifyPurchaseVoucher;
window.renderAccountMasterList = renderAccountMasterList;
window.removeAlternateBarcode = removeAlternateBarcode;
window.openBarcodeLabelModal = openBarcodeLabelModal;
window.initBarcodeModule = initBarcodeModule;
window.populateVoucherRowWithItem = populateVoucherRowWithItem;
window.clearVoucherRow = clearVoucherRow;
window.calcRowAmount = calcRowAmount;
window.recalculateVoucherTotals = recalculateVoucherTotals;
window.setupPartyAutocomplete = setupPartyAutocomplete;
window.renderVchAutocompletePopup = renderVchAutocompletePopup;
window.initCustomerReceiptScreen = initCustomerReceiptScreen;
window.renderCustomerReceiptsRegister = renderCustomerReceiptsRegister;
window.initSupplierPaymentScreen = initSupplierPaymentScreen;
window.renderSupplierPaymentsRegister = renderSupplierPaymentsRegister;
window.renderCustomerOutstandingView = renderCustomerOutstandingView;
window.renderSupplierOutstandingView = renderSupplierOutstandingView;
window.renderReconciliationDashboard = renderReconciliationDashboard;
window.openVoucherDetailsModal = openVoucherDetailsModal;
window.openReversalModal = openReversalModal;
window.openVoucherPrintModal = openVoucherPrintModal;

setupEnterpriseErpEventListeners();
setupCompanyAndPlaceholderModalListeners();
setupThreeOptionWorkflowListeners();
setupSidebarAndDashboardNav();
initCascadingSubmenuPositioning();
initBarcodeModule();
initPaymentAndReceiptModule();
ZoomController.init();

// =============================================================
// PHASE 1: PAPER CONFIGURATION MODULE
// =============================================================
const PaperConfigModule = {
  currentFormat: "a4",
  isDirty: false,
  printers: [],
  configs: {
    a4: null,
    a5: null,
    thermal: null
  },

  init() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    // Top Ribbon Actions
    const btnSave = document.getElementById("btn-config-save");
    if (btnSave) btnSave.addEventListener("click", () => this.saveConfiguration());

    const btnReset = document.getElementById("btn-config-reset-default");
    if (btnReset) btnReset.addEventListener("click", () => this.resetToDefault());

    const btnTestPrint = document.getElementById("btn-config-test-print");
    if (btnTestPrint) btnTestPrint.addEventListener("click", () => this.testPrint());

    const btnRefreshPrinters = document.getElementById("btn-config-refresh-printers");
    if (btnRefreshPrinters) btnRefreshPrinters.addEventListener("click", () => this.refreshPrinters(true));

    const btnBack = document.getElementById("btn-config-back");
    if (btnBack) btnBack.addEventListener("click", () => this.handleNavigateAway("view-dashboard"));

    const btnClose = document.getElementById("btn-config-close");
    if (btnClose) btnClose.addEventListener("click", () => this.handleNavigateAway("view-dashboard"));

    // Category Sidebar Navigation
    const catItems = document.querySelectorAll(".config-category-item");
    catItems.forEach(item => {
      item.addEventListener("click", () => {
        if (item.classList.contains("disabled")) {
          showNotification("This module is scheduled for subsequent phases.", "info");
          return;
        }
        const cat = item.dataset.category;
        catItems.forEach(c => c.classList.toggle("active", c === item));
        const panePaper = document.getElementById("pane-paper-config");
        const paneBillLayout = document.getElementById("pane-bill-layout-config");
        const paneVchNum = document.getElementById("pane-voucher-numbering-config");
        const paneGstTax = document.getElementById("pane-gst-tax-config");
        const paneInventory = document.getElementById("pane-inventory-config");

        if (cat === "inventory") {
          if (panePaper) panePaper.style.display = "none";
          if (paneBillLayout) paneBillLayout.style.display = "none";
          if (paneVchNum) paneVchNum.style.display = "none";
          if (paneGstTax) paneGstTax.style.display = "none";
          if (paneInventory) paneInventory.style.display = "flex";
          if (window.InventoryConfigModule) {
            window.InventoryConfigModule.initScreen();
          }
        } else if (cat === "gst-tax") {
          if (panePaper) panePaper.style.display = "none";
          if (paneBillLayout) paneBillLayout.style.display = "none";
          if (paneVchNum) paneVchNum.style.display = "none";
          if (paneInventory) paneInventory.style.display = "none";
          if (paneGstTax) paneGstTax.style.display = "flex";
          if (window.GstTaxConfigModule) {
            window.GstTaxConfigModule.initScreen();
          }
        } else if (cat === "voucher-numbering") {
          if (panePaper) panePaper.style.display = "none";
          if (paneBillLayout) paneBillLayout.style.display = "none";
          if (paneGstTax) paneGstTax.style.display = "none";
          if (paneInventory) paneInventory.style.display = "none";
          if (paneVchNum) paneVchNum.style.display = "flex";
          if (window.VoucherNumberingConfigModule) {
            window.VoucherNumberingConfigModule.initScreen();
          }
        } else if (cat === "bill-layout") {
          if (panePaper) panePaper.style.display = "none";
          if (paneVchNum) paneVchNum.style.display = "none";
          if (paneGstTax) paneGstTax.style.display = "none";
          if (paneInventory) paneInventory.style.display = "none";
          if (paneBillLayout) paneBillLayout.style.display = "flex";
          if (window.BillLayoutConfigModule) {
            window.BillLayoutConfigModule.initScreen();
          }
        } else if (cat === "paper") {
          if (paneBillLayout) paneBillLayout.style.display = "none";
          if (paneVchNum) paneVchNum.style.display = "none";
          if (paneGstTax) paneGstTax.style.display = "none";
          if (paneInventory) paneInventory.style.display = "none";
          if (panePaper) panePaper.style.display = "flex";
          PaperConfigModule.initScreen();
        }
      });
    });

    // Format Tab Switchers
    const formatTabs = document.querySelectorAll(".btn-format-tab");
    formatTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const fmt = tab.dataset.format;
        if (fmt && fmt !== this.currentFormat) {
          this.switchFormat(fmt);
        }
      });
    });

    // A4 Orientation
    const btnA4Portrait = document.getElementById("btn-a4-orient-portrait");
    const btnA4Landscape = document.getElementById("btn-a4-orient-landscape");
    if (btnA4Portrait && btnA4Landscape) {
      btnA4Portrait.addEventListener("click", () => {
        btnA4Portrait.classList.add("active");
        btnA4Landscape.classList.remove("active");
        const h = document.getElementById("cfg-a4-orientation");
        if (h) h.value = "portrait";
        this.markDirty();
        this.updateLivePreview();
      });
      btnA4Landscape.addEventListener("click", () => {
        btnA4Landscape.classList.add("active");
        btnA4Portrait.classList.remove("active");
        const h = document.getElementById("cfg-a4-orientation");
        if (h) h.value = "landscape";
        this.markDirty();
        this.updateLivePreview();
      });
    }

    // A5 Orientation
    const btnA5Portrait = document.getElementById("btn-a5-orient-portrait");
    const btnA5Landscape = document.getElementById("btn-a5-orient-landscape");
    if (btnA5Portrait && btnA5Landscape) {
      btnA5Portrait.addEventListener("click", () => {
        btnA5Portrait.classList.add("active");
        btnA5Landscape.classList.remove("active");
        const h = document.getElementById("cfg-a5-orientation");
        if (h) h.value = "portrait";
        this.markDirty();
        this.updateLivePreview();
      });
      btnA5Landscape.addEventListener("click", () => {
        btnA5Landscape.classList.add("active");
        btnA5Portrait.classList.remove("active");
        const h = document.getElementById("cfg-a5-orientation");
        if (h) h.value = "landscape";
        this.markDirty();
        this.updateLivePreview();
      });
    }

    // Thermal Width Selectors (80mm, 58mm, Custom)
    const btnTh80 = document.getElementById("btn-thermal-80");
    const btnTh58 = document.getElementById("btn-thermal-58");
    const btnThCustom = document.getElementById("btn-thermal-custom");
    const customWrap = document.getElementById("cfg-thermal-custom-width-wrap");
    const thWidthTypeInput = document.getElementById("cfg-thermal-width-type");
    const thPrintableInput = document.getElementById("cfg-thermal-printable-width");
    const thFontInput = document.getElementById("cfg-thermal-font-size");

    if (btnTh80 && btnTh58 && btnThCustom) {
      btnTh80.addEventListener("click", () => {
        btnTh80.classList.add("active");
        btnTh58.classList.remove("active");
        btnThCustom.classList.remove("active");
        if (customWrap) customWrap.style.display = "none";
        if (thWidthTypeInput) thWidthTypeInput.value = "80mm";
        if (thPrintableInput) thPrintableInput.value = "72";
        if (thFontInput) thFontInput.value = "10";
        this.markDirty();
        this.updateLivePreview();
      });

      btnTh58.addEventListener("click", () => {
        btnTh58.classList.add("active");
        btnTh80.classList.remove("active");
        btnThCustom.classList.remove("active");
        if (customWrap) customWrap.style.display = "none";
        if (thWidthTypeInput) thWidthTypeInput.value = "58mm";
        if (thPrintableInput) thPrintableInput.value = "48";
        if (thFontInput) thFontInput.value = "9";
        this.markDirty();
        this.updateLivePreview();
      });

      btnThCustom.addEventListener("click", () => {
        btnThCustom.classList.add("active");
        btnTh80.classList.remove("active");
        btnTh58.classList.remove("active");
        if (customWrap) customWrap.style.display = "flex";
        if (thWidthTypeInput) thWidthTypeInput.value = "custom";
        const customW = parseFloat(document.getElementById("cfg-thermal-width")?.value || "80");
        if (thPrintableInput) thPrintableInput.value = Math.max(10, customW - 8);
        this.markDirty();
        this.updateLivePreview();
      });
    }

    // Thermal Alignment Buttons
    const alignBtns = document.querySelectorAll(".btn-align");
    const thAlignInput = document.getElementById("cfg-thermal-alignment");
    alignBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        alignBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        if (thAlignInput) thAlignInput.value = btn.dataset.align || "left";
        this.markDirty();
        this.updateLivePreview();
      });
    });

    // Attach real-time input change listeners to all form controls in #form-paper-config
    const form = document.getElementById("form-paper-config");
    if (form) {
      form.addEventListener("input", () => {
        this.markDirty();
        this.updateLivePreview();
      });
      form.addEventListener("change", () => {
        this.markDirty();
        this.updateLivePreview();
      });
    }
  },

  handleNavigateAway(targetScreen) {
    if (this.isDirty) {
      if (!confirm("You have unsaved changes in Paper Configuration. Do you want to discard them?")) {
        return;
      }
    }
    this.isDirty = false;
    showScreen(targetScreen);
  },

  markDirty() {
    this.isDirty = true;
    const badge = document.getElementById("config-unsaved-badge");
    if (badge) badge.style.display = "inline-flex";
    const statusPill = document.getElementById("config-persistence-indicator");
    if (statusPill) {
      statusPill.textContent = "○ Unsaved Changes";
      statusPill.style.color = "#d97706";
      statusPill.style.background = "#fef3c7";
    }
  },

  clearDirty() {
    this.isDirty = false;
    const badge = document.getElementById("config-unsaved-badge");
    if (badge) badge.style.display = "none";
    const statusPill = document.getElementById("config-persistence-indicator");
    if (statusPill) {
      statusPill.textContent = "● Database Synced";
      statusPill.style.color = "#15803d";
      statusPill.style.background = "#dcfce7";
    }
  },

  showStatus(msg, type = "success") {
    const el = document.getElementById("config-status-msg");
    if (!el) return;
    el.textContent = msg;
    el.style.display = "inline-block";
    el.style.color = type === "error" ? "#dc2626" : (type === "info" ? "#0284c7" : "#16a34a");
    setTimeout(() => {
      el.style.display = "none";
    }, 4500);
    if (typeof showToast === "function") showToast(msg);
  },

  initScreen() {
    const compBadge = document.getElementById("config-company-badge");
    if (compBadge) {
      compBadge.textContent = activeCompany ? activeCompany.name : "ANTI MATRIX";
    }

    const modeBadge = document.getElementById("config-mode-badge");
    if (modeBadge) {
      modeBadge.textContent = activeBillingMode === "fast_billing" ? "Fast Billing (Cashier)" : "Traditional Billing";
    }

    this.refreshPrinters(false, () => {
      this.loadConfiguration(this.currentFormat);
    });
  },

  refreshPrinters(showNotification = false, callback = null) {
    if (window.backend && window.backend.getAvailablePrintersWithCapabilities) {
      window.backend.getAvailablePrintersWithCapabilities((respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            this.printers = resp.data || [];
            this.populatePrinterDropdowns(this.printers, resp.default_printer);
            if (showNotification) this.showStatus("Printers refreshed from system.");
          }
        } catch (e) {
          console.error("Error parsing printers:", e);
        }
        if (callback) callback();
      });
    } else if (window.backend && window.backend.getAvailablePrinters) {
      window.backend.getAvailablePrinters((respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            const list = (resp.data || []).map(p => typeof p === "string" ? { name: p, is_default: false } : p);
            this.printers = list;
            this.populatePrinterDropdowns(list, "");
            if (showNotification) this.showStatus("Printers refreshed.");
          }
        } catch (e) {
          console.error("Error parsing fallback printers:", e);
        }
        if (callback) callback();
      });
    } else {
      if (callback) callback();
    }
  },

  populatePrinterDropdowns(printers, defaultPrinterName) {
    const selects = [
      document.getElementById("cfg-a4-printer"),
      document.getElementById("cfg-a5-printer"),
      document.getElementById("cfg-thermal-printer")
    ];

    selects.forEach(sel => {
      if (!sel) return;
      const currentVal = sel.value;
      sel.innerHTML = `<option value="">System Default Printer (${defaultPrinterName || "None"})</option>`;
      printers.forEach(p => {
        const opt = document.createElement("option");
        opt.value = p.name;
        opt.textContent = p.name + (p.is_default ? " [Default]" : "") + (p.is_thermal ? " (Thermal)" : "");
        sel.appendChild(opt);
      });
      if (currentVal) sel.value = currentVal;
    });
  },

  switchFormat(newFormat) {
    if (this.isDirty) {
      if (!confirm(`You have unsaved changes in ${this.currentFormat.toUpperCase()} Paper Configuration. Discard changes and switch?`)) {
        return;
      }
    }

    this.currentFormat = newFormat;

    // Switch tab buttons
    document.querySelectorAll(".btn-format-tab").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.format === newFormat);
      tab.setAttribute("aria-selected", tab.dataset.format === newFormat ? "true" : "false");
    });

    // Switch form panels
    document.querySelectorAll(".paper-panel").forEach(panel => {
      const match = panel.dataset.panelFormat === newFormat;
      panel.style.display = match ? "flex" : "none";
      panel.classList.toggle("active", match);
    });

    const formatBadge = document.getElementById("config-format-badge");
    if (formatBadge) {
      const names = { a4: "Active: A4 Paper", a5: "Active: A5 Paper", thermal: "Active: Thermal Paper" };
      formatBadge.textContent = names[newFormat] || "Active: Paper";
    }

    this.loadConfiguration(newFormat);
  },

  loadConfiguration(format) {
    const mode = activeBillingMode === "fast_billing" ? "fast_billing" : "traditional";
    if (window.backend && window.backend.getPaperConfig) {
      window.backend.getPaperConfig(format, mode, (respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            this.configs[format] = resp.data;
            this.populateForm(format, resp.data);
            this.updateLivePreview();
            this.clearDirty();
          } else {
            this.showStatus("Error loading configuration: " + (resp ? resp.error : "Unknown"), "error");
          }
        } catch (e) {
          console.error("Error parsing paper config:", e);
        }
      });
    }
  },

  populateForm(format, cfg) {
    if (!cfg) return;

    if (format === "a4") {
      const elWidth = document.getElementById("cfg-a4-width");
      const elHeight = document.getElementById("cfg-a4-height");
      const elOrient = document.getElementById("cfg-a4-orientation");
      const btnPort = document.getElementById("btn-a4-orient-portrait");
      const btnLand = document.getElementById("btn-a4-orient-landscape");
      const elScale = document.getElementById("cfg-a4-scaling");
      const elTop = document.getElementById("cfg-a4-margin-top");
      const elBottom = document.getElementById("cfg-a4-margin-bottom");
      const elLeft = document.getElementById("cfg-a4-margin-left");
      const elRight = document.getElementById("cfg-a4-margin-right");
      const elHSpace = document.getElementById("cfg-a4-header-spacing");
      const elFSpace = document.getElementById("cfg-a4-footer-spacing");
      const elPrinter = document.getElementById("cfg-a4-printer");
      const elPageNo = document.getElementById("cfg-a4-page-numbering");

      if (elWidth) elWidth.value = cfg.width_mm ?? 210;
      if (elHeight) elHeight.value = cfg.height_mm ?? 297;
      const orient = (cfg.orientation || "portrait").toLowerCase();
      if (elOrient) elOrient.value = orient;
      if (btnPort) btnPort.classList.toggle("active", orient === "portrait");
      if (btnLand) btnLand.classList.toggle("active", orient === "landscape");
      if (elScale) elScale.value = cfg.print_scaling ?? 100;
      if (elTop) elTop.value = cfg.margin_top_mm ?? 10;
      if (elBottom) elBottom.value = cfg.margin_bottom_mm ?? 10;
      if (elLeft) elLeft.value = cfg.margin_left_mm ?? 10;
      if (elRight) elRight.value = cfg.margin_right_mm ?? 10;
      if (elHSpace) elHSpace.value = cfg.header_spacing_mm ?? 5;
      if (elFSpace) elFSpace.value = cfg.footer_spacing_mm ?? 5;
      if (elPrinter && cfg.default_printer) elPrinter.value = cfg.default_printer;
      if (elPageNo) elPageNo.checked = cfg.page_numbering !== false;

    } else if (format === "a5") {
      const elWidth = document.getElementById("cfg-a5-width");
      const elHeight = document.getElementById("cfg-a5-height");
      const elOrient = document.getElementById("cfg-a5-orientation");
      const btnPort = document.getElementById("btn-a5-orient-portrait");
      const btnLand = document.getElementById("btn-a5-orient-landscape");
      const elScale = document.getElementById("cfg-a5-scaling");
      const elTop = document.getElementById("cfg-a5-margin-top");
      const elBottom = document.getElementById("cfg-a5-margin-bottom");
      const elLeft = document.getElementById("cfg-a5-margin-left");
      const elRight = document.getElementById("cfg-a5-margin-right");
      const elHSpace = document.getElementById("cfg-a5-header-spacing");
      const elFSpace = document.getElementById("cfg-a5-footer-spacing");
      const elPrinter = document.getElementById("cfg-a5-printer");
      const elPageNo = document.getElementById("cfg-a5-page-numbering");

      if (elWidth) elWidth.value = cfg.width_mm ?? 148;
      if (elHeight) elHeight.value = cfg.height_mm ?? 210;
      const orient = (cfg.orientation || "portrait").toLowerCase();
      if (elOrient) elOrient.value = orient;
      if (btnPort) btnPort.classList.toggle("active", orient === "portrait");
      if (btnLand) btnLand.classList.toggle("active", orient === "landscape");
      if (elScale) elScale.value = cfg.print_scaling ?? 100;
      if (elTop) elTop.value = cfg.margin_top_mm ?? 8;
      if (elBottom) elBottom.value = cfg.margin_bottom_mm ?? 8;
      if (elLeft) elLeft.value = cfg.margin_left_mm ?? 8;
      if (elRight) elRight.value = cfg.margin_right_mm ?? 8;
      if (elHSpace) elHSpace.value = cfg.header_spacing_mm ?? 4;
      if (elFSpace) elFSpace.value = cfg.footer_spacing_mm ?? 4;
      if (elPrinter && cfg.default_printer) elPrinter.value = cfg.default_printer;
      if (elPageNo) elPageNo.checked = cfg.page_numbering !== false;

    } else if (format === "thermal") {
      const wType = (cfg.thermal_paper_width_type || "80mm").toLowerCase();
      const elWidthType = document.getElementById("cfg-thermal-width-type");
      if (elWidthType) elWidthType.value = wType;

      const btn80 = document.getElementById("btn-thermal-80");
      const btn58 = document.getElementById("btn-thermal-58");
      const btnCustom = document.getElementById("btn-thermal-custom");
      const wrapCustom = document.getElementById("cfg-thermal-custom-width-wrap");

      if (btn80) btn80.classList.toggle("active", wType === "80mm");
      if (btn58) btn58.classList.toggle("active", wType === "58mm");
      if (btnCustom) btnCustom.classList.toggle("active", wType === "custom");
      if (wrapCustom) wrapCustom.style.display = wType === "custom" ? "flex" : "none";

      const elWidth = document.getElementById("cfg-thermal-width");
      const elPrintable = document.getElementById("cfg-thermal-printable-width");
      const elLeft = document.getElementById("cfg-thermal-margin-left");
      const elRight = document.getElementById("cfg-thermal-margin-right");
      const elTop = document.getElementById("cfg-thermal-margin-top");
      const elBottom = document.getElementById("cfg-thermal-margin-bottom");
      const elPrinter = document.getElementById("cfg-thermal-printer");
      const elFontSize = document.getElementById("cfg-thermal-font-size");
      const elLineSpacing = document.getElementById("cfg-thermal-line-spacing");
      const elAlign = document.getElementById("cfg-thermal-alignment");
      const elDensity = document.getElementById("cfg-thermal-density");
      const elAutoCut = document.getElementById("cfg-thermal-auto-cut");

      if (elWidth) elWidth.value = cfg.width_mm ?? 80;
      if (elPrintable) elPrintable.value = cfg.printable_width_mm ?? (wType === "58mm" ? 48 : 72);
      if (elLeft) elLeft.value = cfg.margin_left_mm ?? 2;
      if (elRight) elRight.value = cfg.margin_right_mm ?? 2;
      if (elTop) elTop.value = cfg.margin_top_mm ?? 4;
      if (elBottom) elBottom.value = cfg.margin_bottom_mm ?? 4;
      if (elPrinter && cfg.default_printer) elPrinter.value = cfg.default_printer;
      if (elFontSize) elFontSize.value = cfg.font_size ?? (wType === "58mm" ? 9 : 10);
      if (elLineSpacing) elLineSpacing.value = String(cfg.line_spacing ?? 1.2);
      if (elDensity) elDensity.value = cfg.print_density ?? "Normal";
      if (elAutoCut) elAutoCut.checked = cfg.auto_cut !== false;

      const align = (cfg.char_alignment || "left").toLowerCase();
      if (elAlign) elAlign.value = align;
      document.querySelectorAll(".btn-align").forEach(b => {
        b.classList.toggle("active", b.dataset.align === align);
      });
    }
  },

  readCurrentFormValues() {
    const fmt = this.currentFormat;
    if (fmt === "a4") {
      return {
        paper_format: "a4",
        width_mm: parseFloat(document.getElementById("cfg-a4-width")?.value || 210),
        height_mm: parseFloat(document.getElementById("cfg-a4-height")?.value || 297),
        orientation: document.getElementById("cfg-a4-orientation")?.value || "portrait",
        print_scaling: parseInt(document.getElementById("cfg-a4-scaling")?.value || 100, 10),
        margin_top_mm: parseFloat(document.getElementById("cfg-a4-margin-top")?.value || 10),
        margin_bottom_mm: parseFloat(document.getElementById("cfg-a4-margin-bottom")?.value || 10),
        margin_left_mm: parseFloat(document.getElementById("cfg-a4-margin-left")?.value || 10),
        margin_right_mm: parseFloat(document.getElementById("cfg-a4-margin-right")?.value || 10),
        header_spacing_mm: parseFloat(document.getElementById("cfg-a4-header-spacing")?.value || 5),
        footer_spacing_mm: parseFloat(document.getElementById("cfg-a4-footer-spacing")?.value || 5),
        default_printer: document.getElementById("cfg-a4-printer")?.value || "",
        page_numbering: document.getElementById("cfg-a4-page-numbering")?.checked !== false
      };
    } else if (fmt === "a5") {
      return {
        paper_format: "a5",
        width_mm: parseFloat(document.getElementById("cfg-a5-width")?.value || 148),
        height_mm: parseFloat(document.getElementById("cfg-a5-height")?.value || 210),
        orientation: document.getElementById("cfg-a5-orientation")?.value || "portrait",
        print_scaling: parseInt(document.getElementById("cfg-a5-scaling")?.value || 100, 10),
        margin_top_mm: parseFloat(document.getElementById("cfg-a5-margin-top")?.value || 8),
        margin_bottom_mm: parseFloat(document.getElementById("cfg-a5-margin-bottom")?.value || 8),
        margin_left_mm: parseFloat(document.getElementById("cfg-a5-margin-left")?.value || 8),
        margin_right_mm: parseFloat(document.getElementById("cfg-a5-margin-right")?.value || 8),
        header_spacing_mm: parseFloat(document.getElementById("cfg-a5-header-spacing")?.value || 4),
        footer_spacing_mm: parseFloat(document.getElementById("cfg-a5-footer-spacing")?.value || 4),
        default_printer: document.getElementById("cfg-a5-printer")?.value || "",
        page_numbering: document.getElementById("cfg-a5-page-numbering")?.checked !== false
      };
    } else {
      const wType = document.getElementById("cfg-thermal-width-type")?.value || "80mm";
      let w = 80;
      if (wType === "58mm") w = 58;
      else if (wType === "custom") {
        w = parseFloat(document.getElementById("cfg-thermal-width")?.value || 80);
      }
      return {
        paper_format: "thermal",
        thermal_paper_width_type: wType,
        width_mm: w,
        height_mm: null,
        printable_width_mm: parseFloat(document.getElementById("cfg-thermal-printable-width")?.value || (w - 8)),
        margin_top_mm: parseFloat(document.getElementById("cfg-thermal-margin-top")?.value || 4),
        margin_bottom_mm: parseFloat(document.getElementById("cfg-thermal-margin-bottom")?.value || 4),
        margin_left_mm: parseFloat(document.getElementById("cfg-thermal-margin-left")?.value || 2),
        margin_right_mm: parseFloat(document.getElementById("cfg-thermal-margin-right")?.value || 2),
        default_printer: document.getElementById("cfg-thermal-printer")?.value || "",
        font_size: parseInt(document.getElementById("cfg-thermal-font-size")?.value || 10, 10),
        line_spacing: parseFloat(document.getElementById("cfg-thermal-line-spacing")?.value || 1.2),
        char_alignment: document.getElementById("cfg-thermal-alignment")?.value || "left",
        print_density: document.getElementById("cfg-thermal-density")?.value || "Normal",
        auto_cut: document.getElementById("cfg-thermal-auto-cut")?.checked !== false
      };
    }
  },

  validateCurrentForm(data) {
    if (this.currentFormat === "a4") {
      if (isNaN(data.width_mm) || data.width_mm < 100 || data.width_mm > 350) {
        return { valid: false, error: "A4 width must be between 100 mm and 350 mm." };
      }
      if (isNaN(data.height_mm) || data.height_mm < 100 || data.height_mm > 500) {
        return { valid: false, error: "A4 height must be between 100 mm and 500 mm." };
      }
      if (data.margin_left_mm + data.margin_right_mm >= data.width_mm) {
        return { valid: false, error: "Total horizontal margins must be less than paper width." };
      }
      if (data.margin_top_mm + data.margin_bottom_mm >= data.height_mm) {
        return { valid: false, error: "Total vertical margins must be less than paper height." };
      }
    } else if (this.currentFormat === "a5") {
      if (isNaN(data.width_mm) || data.width_mm < 80 || data.width_mm > 250) {
        return { valid: false, error: "A5 width must be between 80 mm and 250 mm." };
      }
      if (isNaN(data.height_mm) || data.height_mm < 100 || data.height_mm > 350) {
        return { valid: false, error: "A5 height must be between 100 mm and 350 mm." };
      }
      if (data.margin_left_mm + data.margin_right_mm >= data.width_mm) {
        return { valid: false, error: "Total horizontal margins must be less than paper width." };
      }
      if (data.margin_top_mm + data.margin_bottom_mm >= data.height_mm) {
        return { valid: false, error: "Total vertical margins must be less than paper height." };
      }
    } else if (this.currentFormat === "thermal") {
      if (data.thermal_paper_width_type === "custom") {
        if (isNaN(data.width_mm) || data.width_mm < 30 || data.width_mm > 120) {
          return { valid: false, error: "Custom thermal width must be between 30 mm and 120 mm." };
        }
      }
      const maxPrintable = data.width_mm - data.margin_left_mm - data.margin_right_mm;
      if (data.margin_left_mm + data.margin_right_mm >= data.width_mm) {
        return { valid: false, error: "Thermal margins must be less than total paper width." };
      }
      if (data.printable_width_mm <= 0 || data.printable_width_mm > maxPrintable) {
        return { valid: false, error: `Printable width (${data.printable_width_mm}mm) cannot exceed available area (${maxPrintable}mm).` };
      }
    }
    return { valid: true };
  },

  saveConfiguration() {
    const data = this.readCurrentFormValues();
    const validation = this.validateCurrentForm(data);
    if (!validation.valid) {
      this.showStatus("Validation Error: " + validation.error, "error");
      return;
    }

    const mode = activeBillingMode === "fast_billing" ? "fast_billing" : "traditional";
    if (window.backend && window.backend.savePaperConfig) {
      window.backend.savePaperConfig(this.currentFormat, JSON.stringify(data), mode, (respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            this.configs[this.currentFormat] = resp.data;
            this.clearDirty();
            this.showStatus(`${this.currentFormat.toUpperCase()} Paper Configuration saved successfully to database!`, "success");
          } else {
            this.showStatus("Failed to save: " + (resp ? resp.error : "Unknown error"), "error");
          }
        } catch (e) {
          console.error("Error saving paper config:", e);
          this.showStatus("Save error: " + e.message, "error");
        }
      });
    }
  },

  resetToDefault() {
    if (!confirm(`Restore factory default specifications for ${this.currentFormat.toUpperCase()} paper format?`)) {
      return;
    }

    const mode = activeBillingMode === "fast_billing" ? "fast_billing" : "traditional";
    if (window.backend && window.backend.resetPaperConfig) {
      window.backend.resetPaperConfig(this.currentFormat, mode, (respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            this.configs[this.currentFormat] = resp.data;
            this.populateForm(this.currentFormat, resp.data);
            this.updateLivePreview();
            this.clearDirty();
            this.showStatus(`${this.currentFormat.toUpperCase()} restored to factory defaults.`, "info");
          } else {
            this.showStatus("Reset failed: " + (resp ? resp.error : "Unknown error"), "error");
          }
        } catch (e) {
          console.error("Error resetting paper config:", e);
        }
      });
    }
  },

  testPrint() {
    const data = this.readCurrentFormValues();
    const validation = this.validateCurrentForm(data);
    if (!validation.valid) {
      this.showStatus("Validation Error: " + validation.error, "error");
      return;
    }

    const printer = data.default_printer || "";
    this.showStatus(`Sending test print to ${printer || 'System Default'}...`, "info");

    if (window.backend && window.backend.testPrintPaper) {
      window.backend.testPrintPaper(printer, this.currentFormat, JSON.stringify(data), (respStr) => {
        try {
          const resp = JSON.parse(respStr);
          if (resp && resp.success) {
            if (resp.format === "thermal") {
              alert(`=== TEST RECEIPT PRINT PREVIEW ===\n\n${resp.receipt_text}\n\n[Status: SUCCESS]`);
              this.showStatus("Thermal test receipt formatted and validated successfully!");
            } else {
              this.showStatus(`${resp.format.toUpperCase()} test print PDF generated: ${resp.file_path}`, "success");
            }
          } else {
            this.showStatus("Test print failed: " + (resp ? resp.error : "Unknown error"), "error");
          }
        } catch (e) {
          console.error("Error running test print:", e);
        }
      });
    }
  },

  updateLivePreview() {
    const data = this.readCurrentFormValues();
    const fmt = this.currentFormat;

    const sheetWrapper = document.getElementById("sheet-preview-wrapper");
    const thermalWrapper = document.getElementById("thermal-receipt-wrapper");
    const previewTitle = document.getElementById("preview-header-title");
    const previewDims = document.getElementById("preview-meta-dimensions");
    const previewMargins = document.getElementById("preview-meta-margins");

    if (fmt === "a4" || fmt === "a5") {
      if (sheetWrapper) sheetWrapper.style.display = "flex";
      if (thermalWrapper) thermalWrapper.style.display = "none";

      const isA4 = fmt === "a4";
      const orient = data.orientation || "portrait";
      const isLandscape = orient === "landscape";

      if (previewTitle) previewTitle.textContent = `Live Preview • ${fmt.toUpperCase()} ${orient.toUpperCase()}`;
      if (previewDims) previewDims.textContent = `${data.width_mm} × ${data.height_mm} mm`;
      if (previewMargins) previewMargins.textContent = `M: T${data.margin_top_mm}, B${data.margin_bottom_mm}, L${data.margin_left_mm}, R${data.margin_right_mm} mm`;

      const paperEl = document.getElementById("sheet-paper-element");
      const marginBox = document.getElementById("sheet-margin-box");

      let baseW = isA4 ? 280 : 220;
      let baseH = isA4 ? 396 : 312;
      if (isLandscape) {
        const temp = baseW;
        baseW = baseH;
        baseH = temp;
      }

      if (paperEl) {
        paperEl.style.width = `${baseW}px`;
        paperEl.style.height = `${baseH}px`;
      }

      if (marginBox) {
        const pTop = Math.max(2, Math.round((data.margin_top_mm / data.height_mm) * baseH));
        const pBottom = Math.max(2, Math.round((data.margin_bottom_mm / data.height_mm) * baseH));
        const pLeft = Math.max(2, Math.round((data.margin_left_mm / data.width_mm) * baseW));
        const pRight = Math.max(2, Math.round((data.margin_right_mm / data.width_mm) * baseW));
        marginBox.style.padding = `${pTop}px ${pRight}px ${pBottom}px ${pLeft}px`;
      }

      const docTypeLbl = document.getElementById("sheet-doc-type");
      if (docTypeLbl) docTypeLbl.textContent = `NEUTRAL TEST LAYOUT • ${fmt.toUpperCase()}`;

      const fmtLbl = document.getElementById("sheet-preview-fmt-lbl");
      if (fmtLbl) fmtLbl.textContent = `${fmt.toUpperCase()} (${data.width_mm}×${data.height_mm} mm)`;

      const orientLbl = document.getElementById("sheet-preview-orient-lbl");
      if (orientLbl) orientLbl.textContent = orient.toUpperCase();

      const scaleLbl = document.getElementById("sheet-scale-lbl");
      if (scaleLbl) scaleLbl.textContent = `${data.print_scaling}%`;

      const printWLbl = document.getElementById("sheet-print-w-lbl");
      if (printWLbl) printWLbl.textContent = `${Math.max(0, data.width_mm - data.margin_left_mm - data.margin_right_mm).toFixed(1)} mm`;

      const printHLbl = document.getElementById("sheet-print-h-lbl");
      if (printHLbl) printHLbl.textContent = `${Math.max(0, data.height_mm - data.margin_top_mm - data.margin_bottom_mm).toFixed(1)} mm`;

      const pageNoLbl = document.getElementById("sheet-preview-page-no");
      const sampleItems = document.getElementById("thermal-sample-items");
      if (sampleItems) {
        sampleItems.style.textAlign = data.char_alignment || "left";
      }

      const headline = document.getElementById("thermal-width-headline");
      if (headline) headline.textContent = `THERMAL RECEIPT PREVIEW (${w}mm)`;

      const wLbl = document.getElementById("thermal-w-lbl");
      if (wLbl) wLbl.textContent = `${w} mm (${data.thermal_paper_width_type || "80mm"})`;

      const pwLbl = document.getElementById("thermal-pw-lbl");
      if (pwLbl) pwLbl.textContent = `${data.printable_width_mm} mm`;

      const densityLbl = document.getElementById("thermal-density-lbl");
      if (densityLbl) {
        densityLbl.textContent = `Density: ${data.print_density || 'Normal'} • Font: ${data.font_size || 10}pt • Align: ${(data.char_alignment || 'left').toUpperCase()}`;
      }

      const cutIndicator = document.getElementById("thermal-cut-indicator");
      if (cutIndicator) {
        cutIndicator.style.display = data.auto_cut !== false ? "block" : "none";
      }
    }
  }
};

// =============================================================
// PHASE 2: BILL LAYOUT CONFIGURATION MODULE
// =============================================================
const BillLayoutConfigModule = {
  currentVoucherType: "sales_invoice",
  currentPreviewFmt: "a4",
  currentPreviewZoom: 80,
  currentPreviewOrientation: "portrait",
  isDirty: false,
  companyDetails: null,
  paperConfig: null,
  configs: {
    sales_invoice: null,
    sales_return: null,
    purchase_invoice: null,
    purchase_return: null
  },

  init() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    // Voucher Type Tabs
    const vchTabs = document.querySelectorAll(".btn-vch-tab");
    vchTabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const vt = tab.dataset.voucher;
        if (vt && vt !== this.currentVoucherType) {
          this.switchVoucherType(vt);
        }
      });
    });

    // Accordions Toggle
    const accHeaders = document.querySelectorAll(".layout-acc-header");
    accHeaders.forEach(hdr => {
      hdr.addEventListener("click", () => {
        const card = hdr.closest(".layout-acc-card");
        if (card) {
          card.classList.toggle("collapsed");
        }
      });
    });

    // Action Buttons
    const btnSave = document.getElementById("btn-layout-save");
    if (btnSave) btnSave.addEventListener("click", () => this.saveLayout());

    const btnResetAction = document.getElementById("btn-layout-reset-action");
    if (btnResetAction) {
      btnResetAction.addEventListener("click", () => {
        const selSec = document.getElementById("sel-layout-reset-section");
        const sec = selSec ? selSec.value : "";
        this.resetLayout(sec);
      });
    }

    // Duplicate Layout Modal
    const btnDuplicate = document.getElementById("btn-layout-duplicate");
    const modalDup = document.getElementById("modal-duplicate-layout");
    const btnCloseDup = document.getElementById("btn-close-dup-modal");
    const btnCancelDup = document.getElementById("btn-cancel-dup-layout");
    const btnConfirmDup = document.getElementById("btn-confirm-dup-layout");
    const dispTargetVch = document.getElementById("disp-dup-target-vch");

    if (btnDuplicate) {
      btnDuplicate.addEventListener("click", () => {
        if (dispTargetVch) {
          const titles = {
            sales_invoice: "Sales Invoice",
            sales_return: "Sales Return",
            purchase_invoice: "Purchase Invoice",
            purchase_return: "Purchase Return"
          };
          dispTargetVch.value = titles[this.currentVoucherType] || this.currentVoucherType;
        }
        if (modalDup) modalDup.style.display = "flex";
      });
    }
    const closeDupModal = () => { if (modalDup) modalDup.style.display = "none"; };
    if (btnCloseDup) btnCloseDup.addEventListener("click", closeDupModal);
    if (btnCancelDup) btnCancelDup.addEventListener("click", closeDupModal);
    if (btnConfirmDup) {
      btnConfirmDup.addEventListener("click", () => {
        const selSource = document.getElementById("sel-dup-source-vch");
        const sourceVch = selSource ? selSource.value : "sales_invoice";
        this.duplicateFrom(sourceVch);
        closeDupModal();
      });
    }

    // Logo Upload & Remove
    const fileLogo = document.getElementById("file-hdr-logo");
    const btnUploadLogo = document.getElementById("btn-hdr-upload-logo");
    const btnRemoveLogo = document.getElementById("btn-hdr-remove-logo");
    const imgLogoThumb = document.getElementById("img-hdr-logo-thumb");
    const chkLogo = document.getElementById("chk-hdr-logo");
    const wrapLogoProps = document.getElementById("wrap-hdr-logo-props");

    if (btnUploadLogo && fileLogo) {
      btnUploadLogo.addEventListener("click", () => fileLogo.click());
      fileLogo.addEventListener("change", (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
          const reader = new FileReader();
          reader.onload = (loadEvt) => {
            const dataUrl = loadEvt.target.result;
            if (imgLogoThumb) imgLogoThumb.src = dataUrl;
            if (wrapLogoProps) wrapLogoProps.style.display = "flex";
            if (btnRemoveLogo) btnRemoveLogo.style.display = "inline-block";
            if (chkLogo) chkLogo.checked = true;
            this.handleInputChange();
          };
          reader.readAsDataURL(file);
        }
      });
    }

    if (btnRemoveLogo) {
      btnRemoveLogo.addEventListener("click", () => {
        if (imgLogoThumb) imgLogoThumb.src = "";
        if (wrapLogoProps) wrapLogoProps.style.display = "none";
        btnRemoveLogo.style.display = "none";
        if (chkLogo) chkLogo.checked = false;
        if (fileLogo) fileLogo.value = "";
        this.handleInputChange();
      });
    }

    if (chkLogo) {
      chkLogo.addEventListener("change", () => {
        if (wrapLogoProps) {
          wrapLogoProps.style.display = chkLogo.checked ? "flex" : "none";
        }
        this.handleInputChange();
      });
    }

    // Preview Format Switcher
    const prevFmtBtns = [
      document.getElementById("btn-prev-fmt-a4"),
      document.getElementById("btn-prev-fmt-a5"),
      document.getElementById("btn-prev-fmt-thermal")
    ];
    prevFmtBtns.forEach(btn => {
      if (btn) {
        btn.addEventListener("click", () => {
          const fmt = btn.dataset.fmt;
          if (fmt && fmt !== this.currentPreviewFmt) {
            this.currentPreviewFmt = fmt;
            prevFmtBtns.forEach(b => { if (b) b.classList.toggle("active", b === btn); });
            this.loadPaperConfig(fmt);
          }
        });
      }
    });

    // Preview Orientation
    const selOrient = document.getElementById("sel-prev-orientation");
    if (selOrient) {
      selOrient.addEventListener("change", () => {
        this.currentPreviewOrientation = selOrient.value;
        this.updateLivePreview();
      });
    }

    // Preview Zoom
    const btnZoomIn = document.getElementById("btn-prev-zoom-in");
    const btnZoomOut = document.getElementById("btn-prev-zoom-out");
    const lblZoom = document.getElementById("prev-zoom-lvl");
    if (btnZoomIn) {
      btnZoomIn.addEventListener("click", () => {
        this.currentPreviewZoom = Math.min(150, this.currentPreviewZoom + 10);
        if (lblZoom) lblZoom.textContent = `${this.currentPreviewZoom}%`;
        this.updateLivePreview();
      });
    }
    if (btnZoomOut) {
      btnZoomOut.addEventListener("click", () => {
        this.currentPreviewZoom = Math.max(40, this.currentPreviewZoom - 10);
        if (lblZoom) lblZoom.textContent = `${this.currentPreviewZoom}%`;
        this.updateLivePreview();
      });
    }

    // Test Print Sample
    const btnPrintSample = document.getElementById("btn-layout-print-sample");
    if (btnPrintSample) {
      btnPrintSample.addEventListener("click", () => this.testPrintInvoice());
    }

    // Realtime Change Listeners on Controls
    const formInputs = document.querySelectorAll(
      "#pane-bill-layout-config input, #pane-bill-layout-config select, #pane-bill-layout-config textarea"
    );
    formInputs.forEach(input => {
      if (input.id !== "file-hdr-logo" && !input.id.startsWith("sel-prev-") && !input.id.startsWith("btn-prev-")) {
        input.addEventListener("input", () => this.handleInputChange());
        input.addEventListener("change", () => this.handleInputChange());
      }
    });
  },

  handleInputChange() {
    this.isDirty = true;
    const persistInd = document.getElementById("layout-persistence-indicator");
    if (persistInd) {
      persistInd.textContent = "● Unsaved Changes";
      persistInd.style.color = "#f59e0b";
      persistInd.style.borderColor = "#f59e0b";
    }
    this.updateLivePreview();
  },

  initScreen() {
    this.loadCompanyDetails();
    this.loadPaperConfig(this.currentPreviewFmt);
    this.loadLayoutConfig(this.currentVoucherType);
  },

  loadCompanyDetails() {
    try {
      const mode = activeBillingMode || "traditional";
      if (window.backendBridge && typeof window.backendBridge.getCompanyDetailsForBillLayout === "function") {
        const raw = window.backendBridge.getCompanyDetailsForBillLayout(mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.companyDetails = res.data;
        }
      }
    } catch (e) {
      console.warn("Could not load company details for bill layout:", e);
    }
    if (!this.companyDetails) {
      this.companyDetails = {
        company_name: "ANTI MATRIX COMMERCIAL BILLING",
        gstin: "33AAAPL1234F1Z1",
        state: "Tamil Nadu (33)",
        address: "Main Business Complex, Market Road",
        phone: "+91 98765 43210",
        email: "billing@antimatrix.local",
        website: "www.antimatrix.local"
      };
    }
  },

  loadPaperConfig(fmt) {
    try {
      const mode = activeBillingMode || "traditional";
      if (window.backendBridge && typeof window.backendBridge.getPaperConfig === "function") {
        const raw = window.backendBridge.getPaperConfig(fmt, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.paperConfig = res.data;
          if (this.paperConfig.orientation) {
            this.currentPreviewOrientation = this.paperConfig.orientation;
            const selOrient = document.getElementById("sel-prev-orientation");
            if (selOrient) selOrient.value = this.paperConfig.orientation;
          }
        }
      }
    } catch (e) {
      console.warn("Could not load paper config for bill layout preview:", e);
    }
    if (!this.paperConfig) {
      this.paperConfig = {
        paper_format: fmt,
        width_mm: fmt === "a5" ? 148.0 : (fmt === "thermal" ? 80.0 : 210.0),
        height_mm: fmt === "a5" ? 210.0 : (fmt === "thermal" ? null : 297.0),
        orientation: "portrait",
        margin_top_mm: 10.0,
        margin_bottom_mm: 10.0,
        margin_left_mm: 10.0,
        margin_right_mm: 10.0
      };
    }
    this.updateLivePreview();
  },

  loadLayoutConfig(voucherType) {
    const mode = activeBillingMode || "traditional";
    try {
      if (window.backendBridge && typeof window.backendBridge.getBillLayoutConfig === "function") {
        const raw = window.backendBridge.getBillLayoutConfig(voucherType, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.configs[voucherType] = res.data;
          this.populateForm(res.data);
          this.renderColumnsConfigTable(res.data.columns_config || []);
          this.isDirty = false;
          const persistInd = document.getElementById("layout-persistence-indicator");
          if (persistInd) {
            persistInd.textContent = "● Database Synced";
            persistInd.style.color = "#10b981";
            persistInd.style.borderColor = "#10b981";
          }
          this.updateLivePreview();
          return;
        }
      }
    } catch (e) {
      console.warn("Could not load layout config via bridge:", e);
    }
  },

  switchVoucherType(voucherType) {
    if (this.isDirty) {
      const confirmLeave = confirm("You have unsaved changes in this voucher layout. Discard changes and switch?");
      if (!confirmLeave) return;
    }
    this.currentVoucherType = voucherType;
    document.querySelectorAll(".btn-vch-tab").forEach(tab => {
      tab.classList.toggle("active", tab.dataset.voucher === voucherType);
    });
    this.loadLayoutConfig(voucherType);
  },

  populateForm(cfg) {
    if (!cfg) return;
    const nameEl = document.getElementById("input-layout-name");
    if (nameEl) nameEl.value = cfg.layout_name || "";

    // 1. Header
    const h = cfg.header_config || {};
    const setChk = (id, val) => { const el = document.getElementById(id); if (el) el.checked = !!val; };
    const setVal = (id, val) => { const el = document.getElementById(id); if (el && val !== undefined) el.value = val; };

    setChk("chk-hdr-comp-name", h.show_company_name !== false);
    setChk("chk-hdr-logo", !!h.show_logo);
    setChk("chk-hdr-address", h.show_address !== false);
    setChk("chk-hdr-phone", h.show_phone !== false);
    setChk("chk-hdr-email", h.show_email !== false);
    setChk("chk-hdr-website", h.show_website !== false);
    setChk("chk-hdr-gstin", h.show_gstin !== false);
    setChk("chk-hdr-state", h.show_state !== false);
    setChk("chk-hdr-reg", h.show_reg_details !== false);
    setVal("input-hdr-tagline", h.custom_header_text || "");
    setVal("sel-hdr-logo-pos", h.logo_position || "left");
    setVal("input-hdr-logo-w", h.logo_width_mm || 30);
    setVal("input-hdr-logo-h", h.logo_height_mm || 20);

    const imgThumb = document.getElementById("img-hdr-logo-thumb");
    const wrapLogo = document.getElementById("wrap-hdr-logo-props");
    const btnRemLogo = document.getElementById("btn-hdr-remove-logo");
    if (h.logo_data) {
      if (imgThumb) imgThumb.src = h.logo_data;
      if (wrapLogo) wrapLogo.style.display = h.show_logo ? "flex" : "none";
      if (btnRemLogo) btnRemLogo.style.display = "inline-block";
    } else {
      if (imgThumb) imgThumb.src = "";
      if (wrapLogo) wrapLogo.style.display = "none";
      if (btnRemLogo) btnRemLogo.style.display = "none";
    }

    // 2. Invoice Info
    const info = cfg.invoice_info_config || {};
    setChk("chk-inv-show-title", info.show_title !== false);
    setVal("input-inv-title", info.title || "TAX INVOICE");
    setChk("chk-inv-vch-no", info.show_voucher_no !== false);
    setVal("input-inv-vch-no-lbl", info.voucher_no_label || "Invoice No");
    setChk("chk-inv-date", info.show_date !== false);
    setVal("input-inv-date-lbl", info.date_label || "Date");
    setChk("chk-inv-due-date", info.show_due_date !== false);
    setVal("input-inv-due-date-lbl", info.due_date_label || "Due Date");
    setChk("chk-inv-ref-no", info.show_reference_no !== false);
    setVal("input-inv-ref-no-lbl", info.reference_no_label || "Ref No");
    setChk("chk-inv-party-name", info.show_party_name !== false);
    setVal("input-inv-party-lbl", info.party_name_label || "Customer (Billed To)");
    setChk("chk-inv-party-address", info.show_party_address !== false);
    setChk("chk-inv-party-gstin", info.show_party_gstin !== false);
    setChk("chk-inv-party-state", info.show_party_state !== false);
    setChk("chk-inv-party-contact", info.show_party_contact !== false);

    // 3. Styling
    const st = cfg.style_config || {};
    setVal("input-tbl-header-bg", st.header_bg_color || "#1e40af");
    setVal("input-tbl-header-color", st.header_text_color || "#ffffff");

    // 4. Totals
    const tot = cfg.totals_config || {};
    setChk("chk-tot-subtotal", tot.show_subtotal !== false);
    setChk("chk-tot-discount", tot.show_discount_total !== false);
    setChk("chk-tot-taxable", tot.show_taxable_amount !== false);
    setChk("chk-tot-cgst", tot.show_cgst_total !== false);
    setChk("chk-tot-sgst", tot.show_sgst_total !== false);
    setChk("chk-tot-igst", tot.show_igst_total !== false);
    setChk("chk-tot-roundoff", tot.show_round_off !== false);
    setChk("chk-tot-grandtotal", tot.show_grand_total !== false);
    setChk("chk-tot-words", tot.show_amount_in_words !== false);
    setChk("chk-tot-payment-method", tot.show_payment_method !== false);
    setChk("chk-tot-amount-paid", tot.show_amount_paid !== false);
    setChk("chk-tot-balance-due", tot.show_balance_due !== false);

    // 5. Footer
    const ftr = cfg.footer_config || {};
    setChk("chk-ftr-terms", ftr.show_terms !== false);
    setVal("txt-ftr-terms", ftr.terms_and_conditions || "");
    setChk("chk-ftr-bank", ftr.show_bank_details !== false);
    setVal("input-ftr-bank-name", ftr.bank_name || "");
    setVal("input-ftr-acc-no", ftr.account_number || "");
    setVal("input-ftr-ifsc", ftr.ifsc_code || "");
    setVal("input-ftr-upi", ftr.upi_id || "");
    setChk("chk-ftr-notes", ftr.show_customer_notes !== false);
    setVal("input-ftr-notes", ftr.customer_notes || "");
    setChk("chk-ftr-signatory", ftr.show_authorized_signatory !== false);
    setVal("input-ftr-signatory-title", ftr.signatory_title || "Authorized Signatory");
    setChk("chk-ftr-seal", ftr.show_company_seal !== false);
  },

  renderColumnsConfigTable(columns) {
    const container = document.getElementById("columns-config-container");
    if (!container) return;
    container.innerHTML = "";

    const cols = Array.isArray(columns) && columns.length ? columns : [];
    cols.sort((a, b) => (a.order || 0) - (b.order || 0));

    cols.forEach((col, idx) => {
      const row = document.createElement("div");
      row.className = `col-cfg-row ${col.visible ? '' : 'col-hidden'}`;
      row.dataset.key = col.key;

      row.innerHTML = `
        <span class="col-cfg-order">${idx + 1}</span>
        <input type="checkbox" class="col-vis-chk" ${col.visible ? 'checked' : ''} title="Toggle Visibility">
        <span class="col-cfg-key-pill" title="${col.key}">${col.key}</span>
        <input type="text" class="col-cfg-label-input" value="${col.label || col.key}" title="Header Label">
        <input type="text" class="col-cfg-width-input" value="${col.width || '8%'}" title="Width (e.g. 10%)">
        <select class="col-cfg-align-select" title="Column Alignment">
          <option value="left" ${col.align === 'left' ? 'selected' : ''}>Left</option>
          <option value="center" ${col.align === 'center' ? 'selected' : ''}>Center</option>
          <option value="right" ${col.align === 'right' ? 'selected' : ''}>Right</option>
        </select>
        <div style="display: flex; gap: 2px;">
          <button type="button" class="col-cfg-btn-order btn-move-up" title="Move Up" ${idx === 0 ? 'disabled' : ''}>▲</button>
          <button type="button" class="col-cfg-btn-order btn-move-down" title="Move Down" ${idx === cols.length - 1 ? 'disabled' : ''}>▼</button>
        </div>
      `;

      // Event handlers for row
      const chk = row.querySelector(".col-vis-chk");
      chk.addEventListener("change", () => {
        row.classList.toggle("col-hidden", !chk.checked);
        this.handleInputChange();
      });

      const lblInp = row.querySelector(".col-cfg-label-input");
      lblInp.addEventListener("input", () => this.handleInputChange());

      const wInp = row.querySelector(".col-cfg-width-input");
      wInp.addEventListener("input", () => this.handleInputChange());

      const alignSel = row.querySelector(".col-cfg-align-select");
      alignSel.addEventListener("change", () => this.handleInputChange());

      const btnUp = row.querySelector(".btn-move-up");
      btnUp.addEventListener("click", () => {
        if (idx > 0) {
          const temp = cols[idx - 1];
          cols[idx - 1] = cols[idx];
          cols[idx] = temp;
          cols.forEach((c, i) => { c.order = i + 1; });
          this.renderColumnsConfigTable(cols);
          this.handleInputChange();
        }
      });

      const btnDown = row.querySelector(".btn-move-down");
      btnDown.addEventListener("click", () => {
        if (idx < cols.length - 1) {
          const temp = cols[idx + 1];
          cols[idx + 1] = cols[idx];
          cols[idx] = temp;
          cols.forEach((c, i) => { c.order = i + 1; });
          this.renderColumnsConfigTable(cols);
          this.handleInputChange();
        }
      });

      container.appendChild(row);
    });
  },

  gatherForm() {
    const getChk = (id) => { const el = document.getElementById(id); return el ? el.checked : false; };
    const getVal = (id, def = "") => { const el = document.getElementById(id); return el ? el.value : def; };

    const imgThumb = document.getElementById("img-hdr-logo-thumb");
    const logoData = (imgThumb && imgThumb.src && imgThumb.src.startsWith("data:")) ? imgThumb.src : "";

    // Gather columns from table
    const colRows = document.querySelectorAll(".col-cfg-row");
    const gatheredCols = [];
    colRows.forEach((row, idx) => {
      gatheredCols.push({
        key: row.dataset.key,
        order: idx + 1,
        visible: row.querySelector(".col-vis-chk").checked,
        label: row.querySelector(".col-cfg-label-input").value.trim(),
        width: row.querySelector(".col-cfg-width-input").value.trim(),
        align: row.querySelector(".col-cfg-align-select").value
      });
    });

    return {
      voucher_type: this.currentVoucherType,
      layout_name: getVal("input-layout-name", "Standard Layout"),
      header_config: {
        show_company_name: getChk("chk-hdr-comp-name"),
        show_logo: getChk("chk-hdr-logo"),
        logo_data: logoData,
        logo_position: getVal("sel-hdr-logo-pos", "left"),
        logo_width_mm: parseFloat(getVal("input-hdr-logo-w", 30)) || 30,
        logo_height_mm: parseFloat(getVal("input-hdr-logo-h", 20)) || 20,
        show_address: getChk("chk-hdr-address"),
        show_phone: getChk("chk-hdr-phone"),
        show_email: getChk("chk-hdr-email"),
        show_website: getChk("chk-hdr-website"),
        show_gstin: getChk("chk-hdr-gstin"),
        show_state: getChk("chk-hdr-state"),
        show_reg_details: getChk("chk-hdr-reg"),
        custom_header_text: getVal("input-hdr-tagline")
      },
      invoice_info_config: {
        title: getVal("input-inv-title", "TAX INVOICE"),
        show_title: getChk("chk-inv-show-title"),
        show_voucher_no: getChk("chk-inv-vch-no"),
        voucher_no_label: getVal("input-inv-vch-no-lbl", "Invoice No"),
        show_date: getChk("chk-inv-date"),
        date_label: getVal("input-inv-date-lbl", "Date"),
        show_due_date: getChk("chk-inv-due-date"),
        due_date_label: getVal("input-inv-due-date-lbl", "Due Date"),
        show_party_name: getChk("chk-inv-party-name"),
        party_name_label: getVal("input-inv-party-lbl", "Customer (Billed To)"),
        show_party_address: getChk("chk-inv-party-address"),
        show_party_gstin: getChk("chk-inv-party-gstin"),
        show_party_state: getChk("chk-inv-party-state"),
        show_party_contact: getChk("chk-inv-party-contact"),
        show_place_of_supply: true,
        show_reference_no: getChk("chk-inv-ref-no"),
        reference_no_label: getVal("input-inv-ref-no-lbl", "Ref No")
      },
      columns_config: gatheredCols,
      totals_config: {
        show_subtotal: getChk("chk-tot-subtotal"),
        show_discount_total: getChk("chk-tot-discount"),
        show_taxable_amount: getChk("chk-tot-taxable"),
        show_cgst_total: getChk("chk-tot-cgst"),
        show_sgst_total: getChk("chk-tot-sgst"),
        show_igst_total: getChk("chk-tot-igst"),
        show_round_off: getChk("chk-tot-roundoff"),
        show_grand_total: getChk("chk-tot-grandtotal"),
        show_amount_in_words: getChk("chk-tot-words"),
        show_payment_method: getChk("chk-tot-payment-method"),
        show_amount_paid: getChk("chk-tot-amount-paid"),
        show_balance_due: getChk("chk-tot-balance-due")
      },
      footer_config: {
        show_terms: getChk("chk-ftr-terms"),
        terms_and_conditions: getVal("txt-ftr-terms"),
        show_bank_details: getChk("chk-ftr-bank"),
        bank_name: getVal("input-ftr-bank-name"),
        account_number: getVal("input-ftr-acc-no"),
        ifsc_code: getVal("input-ftr-ifsc"),
        upi_id: getVal("input-ftr-upi"),
        show_customer_notes: getChk("chk-ftr-notes"),
        customer_notes: getVal("input-ftr-notes"),
        show_authorized_signatory: getChk("chk-ftr-signatory"),
        signatory_title: getVal("input-ftr-signatory-title", "Authorized Signatory"),
        show_company_seal: getChk("chk-ftr-seal")
      },
      style_config: {
        header_bg_color: getVal("input-tbl-header-bg", "#1e40af"),
        header_text_color: getVal("input-tbl-header-color", "#ffffff")
      }
    };
  },

  saveLayout() {
    const data = this.gatherForm();
    const mode = activeBillingMode || "traditional";
    try {
      if (window.backendBridge && typeof window.backendBridge.saveBillLayoutConfig === "function") {
        const raw = window.backendBridge.saveBillLayoutConfig(this.currentVoucherType, JSON.stringify(data), mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.isDirty = false;
          const persistInd = document.getElementById("layout-persistence-indicator");
          if (persistInd) {
            persistInd.textContent = "● Database Synced";
            persistInd.style.color = "#10b981";
            persistInd.style.borderColor = "#10b981";
          }
          showNotification(`${data.layout_name} saved successfully!`, "success");
          return;
        } else {
          showNotification(`Save failed: ${res ? res.error : "Unknown error"}`, "error");
        }
      }
    } catch (e) {
      showNotification(`Save error: ${e}`, "error");
    }
  },

  resetLayout(section) {
    const mode = activeBillingMode || "traditional";
    try {
      if (window.backendBridge && typeof window.backendBridge.resetBillLayoutConfig === "function") {
        const sec = (section === "all" || !section) ? "" : section;
        const raw = window.backendBridge.resetBillLayoutConfig(this.currentVoucherType, sec, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.loadLayoutConfig(this.currentVoucherType);
          showNotification(sec ? `Section '${sec}' reset to default.` : "Layout restored to defaults.", "info");
        }
      }
    } catch (e) {
      showNotification(`Reset error: ${e}`, "error");
    }
  },

  duplicateFrom(sourceVoucherType) {
    const mode = activeBillingMode || "traditional";
    try {
      if (window.backendBridge && typeof window.backendBridge.duplicateBillLayoutConfig === "function") {
        const raw = window.backendBridge.duplicateBillLayoutConfig(sourceVoucherType, this.currentVoucherType, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.loadLayoutConfig(this.currentVoucherType);
          showNotification(`Layout duplicated from '${sourceVoucherType}' successfully!`, "success");
        } else {
          showNotification(`Duplicate failed: ${res ? res.error : "Unknown error"}`, "error");
        }
      }
    } catch (e) {
      showNotification(`Duplicate error: ${e}`, "error");
    }
  },

  updateLivePreview() {
    const canvas = document.getElementById("bill-invoice-preview-canvas");
    if (!canvas) return;

    const data = this.gatherForm();
    const comp = this.companyDetails || {};
    const fmt = this.currentPreviewFmt;
    const isThermal = fmt === "thermal";
    const orient = this.currentPreviewOrientation || "portrait";
    const zoom = this.currentPreviewZoom / 100;

    const pCfg = this.paperConfig || {
      width_mm: fmt === "a5" ? 148 : 210,
      height_mm: fmt === "a5" ? 210 : 297,
      margin_top_mm: 10,
      margin_bottom_mm: 10,
      margin_left_mm: 10,
      margin_right_mm: 10
    };

    if (isThermal) {
      const widthMm = pCfg.width_mm || 80;
      const is58 = widthMm <= 60;
      canvas.innerHTML = `
        <div class="invoice-preview-thermal" style="width: ${widthMm * 3.78}px; max-width: ${widthMm * 3.78}px; transform: scale(${zoom}); padding: 12px 10px; box-sizing: border-box; overflow: hidden;">
          <div style="text-align: center; border-bottom: 1px dashed #475569; padding-bottom: 6px; margin-bottom: 6px;">
            <div style="font-weight: 800; font-size: 13px;">${comp.company_name || 'ANTI MATRIX'}</div>
            <div style="font-size: 10px; font-weight: 700;">${data.invoice_info_config.title || 'RECEIPT'}</div>
            ${data.header_config.show_gstin && comp.gstin ? `<div style="font-size: 9px;">GSTIN: ${comp.gstin}</div>` : ''}
            ${data.header_config.show_phone && comp.phone ? `<div style="font-size: 9px;">Ph: ${comp.phone}</div>` : ''}
          </div>

          <div style="font-size: 9px; line-height: 1.4; border-bottom: 1px dashed #475569; padding-bottom: 4px; margin-bottom: 6px;">
            <div><b>Vch No:</b> INV-2026-001 &nbsp; <b>Date:</b> 16-11-2026</div>
            <div><b>Party:</b> Cash Retail Customer</div>
          </div>

          <table style="width: 100%; font-size: 9px; border-collapse: collapse; margin-bottom: 6px; table-layout: fixed; box-sizing: border-box;">
            <tr style="border-bottom: 1px dashed #475569;">
              <th style="width: ${is58 ? '44%' : '42%'}; text-align: left; padding: 2px 0;">Item</th>
              <th style="width: ${is58 ? '16%' : '16%'}; text-align: center; padding: 2px 0;">Qty</th>
              <th style="width: ${is58 ? '20%' : '20%'}; text-align: right; padding: 2px 0;">Rate</th>
              <th style="width: ${is58 ? '20%' : '22%'}; text-align: right; padding: 2px 0;">Total</th>
            </tr>
            <tr>
              <td style="overflow-wrap: break-word; word-break: break-word; padding: 2px 0;">Standard Product Item</td>
              <td style="text-align: center; padding: 2px 0;">2</td>
              <td style="text-align: right; padding: 2px 0;">500.00</td>
              <td style="text-align: right; padding: 2px 0; font-weight: 700;">1000.00</td>
            </tr>
            <tr>
              <td style="overflow-wrap: break-word; word-break: break-word; padding: 2px 0;">Commercial Supply Box</td>
              <td style="text-align: center; padding: 2px 0;">1</td>
              <td style="text-align: right; padding: 2px 0;">1200.00</td>
              <td style="text-align: right; padding: 2px 0; font-weight: 700;">1200.00</td>
            </tr>
          </table>

          <div style="border-top: 1px dashed #475569; padding-top: 4px; font-size: 9px; line-height: 1.5; width: 100%; box-sizing: border-box;">
            ${data.totals_config.show_subtotal ? `<div style="display: flex; justify-content: space-between;"><span>Subtotal:</span><span style="font-variant-numeric: tabular-nums;">₹ 2200.00</span></div>` : ''}
            ${data.totals_config.show_cgst_total ? `<div style="display: flex; justify-content: space-between;"><span>CGST (9%):</span><span style="font-variant-numeric: tabular-nums;">₹ 198.00</span></div>` : ''}
            ${data.totals_config.show_sgst_total ? `<div style="display: flex; justify-content: space-between;"><span>SGST (9%):</span><span style="font-variant-numeric: tabular-nums;">₹ 198.00</span></div>` : ''}
            <div style="display: flex; justify-content: space-between; font-weight: 800; font-size: 11px; border-top: 1px solid #000; border-bottom: 1px solid #000; padding: 2px 0; margin-top: 2px;">
              <span>GRAND TOTAL:</span><span style="font-variant-numeric: tabular-nums;">₹ 2596.00</span>
            </div>
          </div>

          ${data.footer_config.show_customer_notes && data.footer_config.customer_notes ? `
            <div style="text-align: center; font-size: 9px; margin-top: 8px;">${data.footer_config.customer_notes}</div>
          ` : ''}

          <div class="thermal-cut-line" style="margin-top: 12px;">✂ --- AUTOMATIC PAPER CUT --- ✂</div>
          <div class="thermal-receipt-cut-bottom"></div>
        </div>
      `;
      return;
    }

    // Sheet Preview (A4 & A5)
    let wMm = pCfg.width_mm || (fmt === "a5" ? 148 : 210);
    let hMm = pCfg.height_mm || (fmt === "a5" ? 210 : 297);
    if (orient === "landscape") {
      const t = wMm; wMm = hMm; hMm = t;
    }

    // Scale mm to px (1 mm ≈ 3.78 px)
    const sheetW = wMm * 3.78;
    const sheetH = hMm * 3.78;
    const mTop = (pCfg.margin_top_mm || 10) * 3.78;
    const mBottom = (pCfg.margin_bottom_mm || 10) * 3.78;
    const mLeft = (pCfg.margin_left_mm || 10) * 3.78;
    const mRight = (pCfg.margin_right_mm || 10) * 3.78;

    const h = data.header_config;
    const info = data.invoice_info_config;
    const cols = data.columns_config.filter(c => c.visible);
    const tot = data.totals_config;
    const ftr = data.footer_config;
    const st = data.style_config;

    // Header layout with Logo
    let logoHtml = "";
    if (h.show_logo && h.logo_data) {
      const logoW = (h.logo_width_mm || 30) * 3.78;
      const logoH = (h.logo_height_mm || 20) * 3.78;
      logoHtml = `<img src="${h.logo_data}" style="max-width: ${logoW}px; max-height: ${logoH}px; object-fit: contain;">`;
    }

    let headerCompanyHtml = `
      <div style="display: flex; flex-direction: column; gap: 2px;">
        ${h.show_company_name ? `<div style="font-size: 16px; font-weight: 800; color: ${st.header_bg_color || '#1e40af'};">${comp.company_name || 'ANTI MATRIX COMMERCIAL BILLING'}</div>` : ''}
        ${h.custom_header_text ? `<div style="font-size: 10px; font-weight: 600; color: #475569;">${h.custom_header_text}</div>` : ''}
        <div style="font-size: 9px; color: #475569; line-height: 1.3;">
          ${h.show_address && comp.address ? `<span>${comp.address}</span>` : ''}
          ${h.show_state && comp.state ? ` &bull; <span>State: ${comp.state}</span>` : ''}
          ${h.show_phone && comp.phone ? ` &bull; <span>Ph: ${comp.phone}</span>` : ''}
          ${h.show_email && comp.email ? ` &bull; <span>Email: ${comp.email}</span>` : ''}
        </div>
        <div style="font-size: 9px; color: #1e293b; font-weight: 700; margin-top: 2px;">
          ${h.show_gstin && comp.gstin ? `<span>GSTIN: ${comp.gstin}</span>` : ''}
          ${h.show_reg_details && comp.code ? ` &bull; <span>Reg/CIN: ${comp.code}</span>` : ''}
        </div>
      </div>
    `;

    let headerFlex = "";
    if (h.logo_position === "center" && logoHtml) {
      headerFlex = `
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px; border-bottom: 2px solid ${st.header_bg_color || '#1e40af'}; padding-bottom: 8px;">
          ${logoHtml}
          ${headerCompanyHtml}
        </div>
      `;
    } else if (h.logo_position === "right" && logoHtml) {
      headerFlex = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid ${st.header_bg_color || '#1e40af'}; padding-bottom: 8px;">
          ${headerCompanyHtml}
          ${logoHtml}
        </div>
      `;
    } else {
      headerFlex = `
        <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid ${st.header_bg_color || '#1e40af'}; padding-bottom: 8px;">
          <div style="display: flex; gap: 10px; align-items: center;">
            ${logoHtml}
            ${headerCompanyHtml}
          </div>
        </div>
      `;
    }

    // Party & Invoice Metadata Box
    const metaBoxHtml = `
      <div style="margin-top: 8px; border: 1px solid #cbd5e1; border-radius: 4px; background: #f8fafc; padding: 6px 10px; display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 9px;">
        <div>
          ${info.show_party_name ? `<div><b>${info.party_name_label || 'Billed To'}:</b> Supreme Retail Traders</div>` : ''}
          ${info.show_party_address ? `<div><b>Address:</b> 44 Market Street, West Commercial Zone</div>` : ''}
          ${info.show_party_gstin ? `<div><b>GSTIN:</b> 33AABCT9876Q1Z2</div>` : ''}
          ${info.show_party_state ? `<div><b>State & Code:</b> Tamil Nadu (33)</div>` : ''}
        </div>
        <div>
          ${info.show_voucher_no ? `<div><b>${info.voucher_no_label || 'Invoice No'}:</b> INV-2026-0042</div>` : ''}
          ${info.show_date ? `<div><b>${info.date_label || 'Date'}:</b> 16-11-2026</div>` : ''}
          ${info.show_due_date ? `<div><b>${info.due_date_label || 'Due Date'}:</b> 30-11-2026</div>` : ''}
          ${info.show_reference_no ? `<div><b>${info.reference_no_label || 'Ref No'}:</b> PO-88912</div>` : ''}
        </div>
      </div>
    `;

    // Calculate total percentage specified and normalize to exactly 100%
    const isA5 = (fmt === "a5");
    let totalPct = 0;
    const rawPcts = cols.map(c => {
      let p = parseFloat(c.width);
      if (isNaN(p) || p <= 0) p = 100 / (cols.length || 1);
      totalPct += p;
      return p;
    });
    const normCols = cols.map((c, i) => {
      const normPct = ((rawPcts[i] / (totalPct || 1)) * 100).toFixed(1) + "%";
      return { ...c, normWidth: normPct };
    });

    // Columns Table Header
    let tableHeadersHtml = "";
    normCols.forEach(c => {
      tableHeadersHtml += `<th style="text-align: ${c.align}; width: ${c.normWidth}; padding: ${isA5 ? '3px 3px' : '4px 5px'}; font-size: ${isA5 ? '7.5px' : '8.5px'}; border: 1px solid #cbd5e1; box-sizing: border-box; overflow-wrap: break-word; word-break: break-word;">${c.label || c.key}</th>`;
    });

    // Sample Table Rows
    const sampleRows = [
      { sl_no: "1", name: "High Speed Barcode Scanner", sku: "SCN-100", hsn: "8471", barcode: "8901234567890", description: "USB 2D Imager", qty: "2", unit: "Pcs", rate: "1250.00", discount: "50.00", taxable_amount: "2450.00", cgst: "220.50", sgst: "220.50", igst: "0.00", gst_rate: "18%", total: "2891.00" },
      { sl_no: "2", name: "Thermal Receipt Paper Roll (80mm)", sku: "PR-80M", hsn: "4811", barcode: "8909876543210", description: "BPA Free Roll", qty: "10", unit: "Roll", rate: "65.00", discount: "0.00", taxable_amount: "650.00", cgst: "39.00", sgst: "39.00", igst: "0.00", gst_rate: "12%", total: "728.00" }
    ];

    let tableRowsHtml = "";
    sampleRows.forEach(row => {
      tableRowsHtml += "<tr>";
      normCols.forEach(c => {
        tableRowsHtml += `<td style="text-align: ${c.align}; width: ${c.normWidth}; padding: ${isA5 ? '3px 3px' : '4px 5px'}; font-size: ${isA5 ? '7.5px' : '8.5px'}; border: 1px solid #cbd5e1; box-sizing: border-box; overflow-wrap: break-word; word-break: break-word;">${row[c.key] || '-'}</td>`;
      });
      tableRowsHtml += "</tr>";
    });

    // Totals Table
    let totalsRowsHtml = "";
    if (tot.show_subtotal) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>Subtotal:</b></td><td style="text-align: right; padding: 2px 4px; width: 80px; font-variant-numeric: tabular-nums;">₹ 3,100.00</td></tr>`;
    if (tot.show_discount_total) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>Discount:</b></td><td style="text-align: right; padding: 2px 4px; font-variant-numeric: tabular-nums;">-₹ 50.00</td></tr>`;
    if (tot.show_taxable_amount) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>Taxable Amount:</b></td><td style="text-align: right; padding: 2px 4px; font-variant-numeric: tabular-nums;">₹ 3,050.00</td></tr>`;
    if (tot.show_cgst_total) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>CGST:</b></td><td style="text-align: right; padding: 2px 4px; font-variant-numeric: tabular-nums;">₹ 259.50</td></tr>`;
    if (tot.show_sgst_total) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>SGST:</b></td><td style="text-align: right; padding: 2px 4px; font-variant-numeric: tabular-nums;">₹ 259.50</td></tr>`;
    if (tot.show_round_off) totalsRowsHtml += `<tr><td style="text-align: right; padding: 2px 4px;"><b>Round-Off:</b></td><td style="text-align: right; padding: 2px 4px; font-variant-numeric: tabular-nums;">+₹ 0.00</td></tr>`;
    if (tot.show_grand_total) totalsRowsHtml += `<tr style="border-top: 1px solid #047857; border-bottom: 2px solid #047857; color: #047857;"><td style="text-align: right; padding: 4px;"><b>GRAND TOTAL:</b></td><td style="text-align: right; padding: 4px; font-size: ${isA5 ? '10px' : '11px'}; font-weight: 800; font-variant-numeric: tabular-nums;">₹ 3,619.00</td></tr>`;
    if (tot.show_amount_in_words) totalsRowsHtml += `<tr><td colspan="2" style="text-align: right; font-size: ${isA5 ? '7px' : '8px'}; color: #64748b; padding-top: 2px; overflow-wrap: break-word;">Three Thousand Six Hundred Nineteen Only</td></tr>`;

    // Footer Table
    const footerHtml = `
      <div style="margin-top: auto; padding-top: 10px; border-top: 1px solid #cbd5e1; display: grid; grid-template-columns: 1fr 180px; gap: 14px; font-size: 8px; width: 100%; box-sizing: border-box;">
        <div style="min-width: 0; overflow-wrap: break-word;">
          ${ftr.show_terms && ftr.terms_and_conditions ? `
            <div style="margin-bottom: 4px;">
              <b>Terms & Conditions:</b><br/>
              <span style="white-space: pre-line; color: #475569;">${ftr.terms_and_conditions}</span>
            </div>
          ` : ''}
          ${ftr.show_bank_details ? `
            <div style="color: #334155;">
              <b>Bank Details:</b> ${ftr.bank_name || 'HDFC Bank'} | A/c: ${ftr.account_number || '50200012345678'} | IFSC: ${ftr.ifsc_code || 'HDFC0001234'} ${ftr.upi_id ? `| UPI: ${ftr.upi_id}` : ''}
            </div>
          ` : ''}
          ${ftr.show_customer_notes && ftr.customer_notes ? `
            <div style="font-style: italic; color: #64748b; margin-top: 4px;">${ftr.customer_notes}</div>
          ` : ''}
        </div>
        <div style="display: flex; flex-direction: column; align-items: flex-end; justify-content: flex-end; text-align: right;">
          ${ftr.show_company_seal ? `
            <div style="border: 1px dashed #94a3b8; border-radius: 4px; width: 60px; height: 35px; display: flex; align-items: center; justify-content: center; font-size: 7px; color: #94a3b8; margin-bottom: 4px;">SEAL</div>
          ` : ''}
          ${ftr.show_authorized_signatory ? `
            <div style="border-top: 1px solid #475569; width: 140px; padding-top: 2px; font-size: 9px; font-weight: 700; color: #1e293b;">${ftr.signatory_title || 'Authorized Signatory'}</div>
            <div style="font-size: 7px; color: #64748b;">For ${comp.company_name || 'ANTI MATRIX'}</div>
          ` : ''}
        </div>
      </div>
    `;

    canvas.innerHTML = `
      <div class="invoice-preview-sheet" style="
        width: ${sheetW}px;
        max-width: ${sheetW}px;
        min-height: ${sheetH}px;
        padding: ${mTop}px ${mRight}px ${mBottom}px ${mLeft}px;
        transform: scale(${zoom});
        box-sizing: border-box;
        overflow: hidden;
      ">
        ${headerFlex}
        ${info.show_title ? `<div style="text-align: center; font-size: ${isA5 ? '11px' : '13px'}; font-weight: 800; color: ${st.header_bg_color || '#1e40af'}; margin-top: 6px; letter-spacing: 0.5px;">${info.title.toUpperCase()}</div>` : ''}
        ${metaBoxHtml}

        <table style="width: 100%; border-collapse: collapse; margin-top: 8px; table-layout: fixed; box-sizing: border-box;">
          <thead>
            <tr style="background: ${st.header_bg_color || '#1e40af'}; color: ${st.header_text_color || '#ffffff'};">
              ${tableHeadersHtml}
            </tr>
          </thead>
          <tbody>
            ${tableRowsHtml}
          </tbody>
        </table>

        <div style="display: flex; justify-content: flex-end; margin-top: 8px; width: 100%; box-sizing: border-box;">
          <table style="font-size: ${isA5 ? '8px' : '9px'}; border-collapse: collapse; min-width: ${isA5 ? '180px' : '220px'}; box-sizing: border-box;">
            ${totalsRowsHtml}
          </table>
        </div>

        ${footerHtml}
      </div>
    `;
  },

  testPrintInvoice() {
    const mode = activeBillingMode || "traditional";
    try {
      if (this.currentPreviewFmt === "thermal") {
        if (window.backendBridge && typeof window.backendBridge.renderInvoiceThermal === "function") {
          const raw = window.backendBridge.renderInvoiceThermal(this.currentVoucherType, JSON.stringify({}), mode);
          const res = typeof raw === "string" ? JSON.parse(raw) : raw;
          if (res && res.success) {
            showNotification(`Thermal test receipt generated (${res.receipt_text ? res.receipt_text.length : 0} chars). Ready for printer!`, "success");
            return;
          }
        }
      } else {
        if (window.backendBridge && typeof window.backendBridge.renderInvoicePDF === "function") {
          const raw = window.backendBridge.renderInvoicePDF(this.currentVoucherType, this.currentPreviewFmt, JSON.stringify({}), mode);
          const res = typeof raw === "string" ? JSON.parse(raw) : raw;
          if (res && res.success) {
            showNotification(`Invoice PDF generated successfully at: ${res.file_path}`, "success");
            return;
          }
        }
      }
    } catch (e) {
      showNotification(`Test print error: ${e}`, "error");
    }
  }
};

window.BillLayoutConfigModule = BillLayoutConfigModule;
BillLayoutConfigModule.init();

// =============================================================
// PHASE 4: VOUCHER NUMBERING CONFIGURATION MODULE
// =============================================================
const VoucherNumberingConfigModule = {
  currentVoucherType: "sales_invoice",
  isDirty: false,
  config: null,
  status: null,

  init() {
    this.setupEventListeners();
  },

  setupEventListeners() {
    // Voucher Type Tabs
    const tabs = document.querySelectorAll(".btn-vch-tab[data-vch-type]");
    tabs.forEach(tab => {
      tab.addEventListener("click", () => {
        const vt = tab.dataset.vchType;
        if (vt && vt !== this.currentVoucherType) {
          this.switchVoucherType(vt);
        }
      });
    });

    // Form inputs change & input listeners
    const formInputIds = [
      "cfg-vch-enable-custom",
      "cfg-vch-series",
      "cfg-vch-reset-freq",
      "cfg-vch-prefix",
      "cfg-vch-suffix",
      "cfg-vch-start-num",
      "cfg-vch-padding",
      "cfg-vch-include-fy",
      "cfg-vch-fy-format",
      "cfg-vch-fy-sep",
      "cfg-vch-include-branch",
      "cfg-vch-branch-pos"
    ];

    formInputIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", () => this.markDirty());
        el.addEventListener("change", () => this.markDirty());
      }
    });

    // Action buttons
    const btnSave = document.getElementById("btn-vch-num-save");
    if (btnSave) {
      btnSave.addEventListener("click", () => this.saveConfiguration());
    }

    const btnReset = document.getElementById("btn-vch-num-reset");
    if (btnReset) {
      btnReset.addEventListener("click", () => this.resetToDefault());
    }
  },

  initScreen() {
    this.loadConfiguration(this.currentVoucherType);
  },

  switchVoucherType(vchType) {
    if (this.isDirty) {
      if (!confirm("You have unsaved voucher numbering changes. Switch without saving?")) {
        return;
      }
    }
    this.currentVoucherType = vchType;
    const tabs = document.querySelectorAll(".btn-vch-tab[data-vch-type]");
    tabs.forEach(t => {
      const active = t.dataset.vchType === vchType;
      t.classList.toggle("active", active);
      t.setAttribute("aria-selected", active ? "true" : "false");
    });
    this.loadConfiguration(vchType);
  },

  loadConfiguration(vchType) {
    try {
      const mode = activeBillingMode || "traditional";
      const bridge = window.backendBridge || window.backend;
      if (bridge && typeof bridge.getVoucherNumberingConfig === "function") {
        const raw = bridge.getVoucherNumberingConfig(vchType, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          this.config = res.data;
          this.populateForm(res.data);
          this.clearDirty();
        }
      }
      this.refreshStatus();
    } catch (e) {
      console.warn("Error loading voucher numbering config:", e);
    }
    this.updateLivePreview();
  },

  populateForm(cfg) {
    if (!cfg) return;
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val !== undefined && val !== null ? val : "";
    };
    const setChk = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = Boolean(val);
    };

    setChk("cfg-vch-enable-custom", cfg.is_custom_enabled);
    setVal("cfg-vch-series", cfg.series || "Main");
    setVal("cfg-vch-reset-freq", cfg.reset_frequency || "yearly");
    setVal("cfg-vch-prefix", cfg.prefix || "");
    setVal("cfg-vch-suffix", cfg.suffix || "");
    setVal("cfg-vch-start-num", cfg.start_number || 1);
    setVal("cfg-vch-padding", cfg.padding || 4);
    setChk("cfg-vch-include-fy", cfg.include_financial_year);
    setVal("cfg-vch-fy-format", cfg.fy_format || "YYYY-YY");
    setVal("cfg-vch-fy-sep", cfg.fy_separator !== undefined ? cfg.fy_separator : "/");
    setChk("cfg-vch-include-branch", cfg.include_branch_code);
    setVal("cfg-vch-branch-pos", cfg.branch_position || "prefix");
  },

  readFormData() {
    const getVal = (id, def = "") => {
      const el = document.getElementById(id);
      return el ? el.value : def;
    };
    const getChk = (id) => {
      const el = document.getElementById(id);
      return el ? el.checked : false;
    };

    return {
      voucher_type: this.currentVoucherType,
      is_custom_enabled: getChk("cfg-vch-enable-custom"),
      series: getVal("cfg-vch-series", "Main"),
      reset_frequency: getVal("cfg-vch-reset-freq", "yearly"),
      prefix: getVal("cfg-vch-prefix", ""),
      suffix: getVal("cfg-vch-suffix", ""),
      start_number: parseInt(getVal("cfg-vch-start-num", "1"), 10) || 1,
      padding: parseInt(getVal("cfg-vch-padding", "4"), 10) || 4,
      include_financial_year: getChk("cfg-vch-include-fy"),
      fy_format: getVal("cfg-vch-fy-format", "YYYY-YY"),
      fy_separator: getVal("cfg-vch-fy-sep", "/"),
      include_branch_code: getChk("cfg-vch-include-branch"),
      branch_position: getVal("cfg-vch-branch-pos", "prefix")
    };
  },

  markDirty() {
    this.isDirty = true;
    const ind = document.getElementById("vch-num-persistence-indicator");
    if (ind) {
      ind.textContent = "● Unsaved Changes";
      ind.style.color = "#f59e0b";
      ind.style.borderColor = "#f59e0b";
    }
    this.updateLivePreview();
  },

  clearDirty() {
    this.isDirty = false;
    const ind = document.getElementById("vch-num-persistence-indicator");
    if (ind) {
      ind.textContent = "● Saved";
      ind.style.color = "#10b981";
      ind.style.borderColor = "#10b981";
    }
  },

  refreshStatus() {
    try {
      const mode = activeBillingMode || "traditional";
      const bridge = window.backendBridge || window.backend;
      if (bridge && typeof bridge.getVoucherNumberingStatus === "function") {
        const raw = bridge.getVoucherNumberingStatus(this.currentVoucherType, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          const s = res.data;
          this.status = s;
          const elAlloc = document.getElementById("status-vch-last-allocated");
          if (elAlloc) elAlloc.textContent = s.current_allocated_number || "0";
          const elComm = document.getElementById("status-vch-total-committed");
          if (elComm) elComm.textContent = s.total_committed_vouchers || "0";
          const elFy = document.getElementById("status-vch-fy");
          if (elFy) elFy.textContent = s.financial_year || "2026-2027";
          const elBr = document.getElementById("status-vch-branch");
          if (elBr) elBr.textContent = s.branch_code || "BR01";
        }
      }
    } catch (e) {
      console.warn("Could not refresh numbering status:", e);
    }
  },

  updateLivePreview() {
    const data = this.readFormData();
    try {
      const mode = activeBillingMode || "traditional";
      const bridge = window.backendBridge || window.backend;
      if (bridge && typeof bridge.previewVoucherNumber === "function") {
        const raw = bridge.previewVoucherNumber(this.currentVoucherType, JSON.stringify(data), mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          const prev = res.data;
          this.renderPreview(prev, data);
          return;
        }
      }
    } catch (e) {
      console.warn("Preview RPC error, falling back to local preview:", e);
    }
    this.renderLocalPreview(data);
  },

  renderPreview(prev, data) {
    const disp = document.getElementById("vch-num-live-preview-display");
    if (disp) disp.textContent = prev.preview_number || "INV-0001";

    const p1 = document.getElementById("proj-vch-1");
    if (p1 && prev.projected_numbers && prev.projected_numbers[0]) p1.textContent = prev.projected_numbers[0];
    const p2 = document.getElementById("proj-vch-2");
    if (p2 && prev.projected_numbers && prev.projected_numbers[1]) p2.textContent = prev.projected_numbers[1];
    const p3 = document.getElementById("proj-vch-3");
    if (p3 && prev.projected_numbers && prev.projected_numbers[2]) p3.textContent = prev.projected_numbers[2];

    // Chips
    const chipP = document.getElementById("chip-vch-prefix");
    if (chipP) chipP.textContent = data.prefix || "(None)";
    const chipS = document.getElementById("chip-vch-seq");
    if (chipS) chipS.textContent = String(prev.sample_sequence || 1).padStart(data.padding || 4, "0");

    const chipWrapFy = document.getElementById("chip-wrap-fy");
    const chipFy = document.getElementById("chip-vch-fy");
    if (chipWrapFy && chipFy) {
      chipWrapFy.style.display = data.include_financial_year ? "inline-block" : "none";
      chipFy.textContent = prev.financial_year || "2026-27";
    }

    const chipWrapBr = document.getElementById("chip-wrap-br");
    const chipBr = document.getElementById("chip-vch-br");
    if (chipWrapBr && chipBr) {
      chipWrapBr.style.display = data.include_branch_code ? "inline-block" : "none";
      chipBr.textContent = prev.branch_code || "BR01";
    }

    // Validation box
    const valBox = document.getElementById("vch-num-validation-box");
    if (valBox) {
      if (prev.errors && prev.errors.length > 0) {
        valBox.style.display = "block";
        valBox.innerHTML = `⚠️ <strong>Validation Warnings:</strong><ul style="margin: 4px 0 0 16px; padding: 0;">${prev.errors.map(err => `<li>${err}</li>`).join("")}</ul>`;
      } else {
        valBox.style.display = "none";
        valBox.innerHTML = "";
      }
    }
  },

  renderLocalPreview(data) {
    const pad = data.padding || 4;
    const seq = String(data.start_number || 1).padStart(pad, "0");
    let preview = data.prefix ? `${data.prefix}${seq}` : seq;
    if (data.include_financial_year) preview = `${preview}/2026-27`;
    const disp = document.getElementById("vch-num-live-preview-display");
    if (disp) disp.textContent = preview;
  },

  saveConfiguration() {
    const data = this.readFormData();
    try {
      const mode = activeBillingMode || "traditional";
      const bridge = window.backendBridge || window.backend;
      if (bridge && typeof bridge.saveVoucherNumberingConfig === "function") {
        const raw = bridge.saveVoucherNumberingConfig(this.currentVoucherType, JSON.stringify(data), mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          showNotification(`Voucher numbering rules for ${this.currentVoucherType.replace('_', ' ').toUpperCase()} saved successfully.`, "success");
          this.clearDirty();
          this.refreshStatus();
          return;
        } else if (res && res.error) {
          showNotification(`Failed to save numbering configuration: ${res.error}`, "error");
          return;
        }
      }
    } catch (e) {
      showNotification(`Error saving voucher numbering: ${e}`, "error");
    }
  },

  resetToDefault() {
    if (!confirm(`Are you sure you want to reset voucher numbering rules for ${this.currentVoucherType.replace('_', ' ').toUpperCase()} to system factory defaults?`)) {
      return;
    }
    try {
      const mode = activeBillingMode || "traditional";
      const bridge = window.backendBridge || window.backend;
      if (bridge && typeof bridge.resetVoucherNumberingConfig === "function") {
        const raw = bridge.resetVoucherNumberingConfig(this.currentVoucherType, mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success) {
          showNotification(`Voucher numbering rules for ${this.currentVoucherType.replace('_', ' ').toUpperCase()} restored to factory defaults.`, "success");
          this.loadConfiguration(this.currentVoucherType);
          return;
        } else if (res && res.error) {
          showNotification(`Failed to reset: ${res.error}`, "error");
          return;
        }
      }
    } catch (e) {
      showNotification(`Error resetting voucher numbering: ${e}`, "error");
    }
  }
};

window.VoucherNumberingConfigModule = VoucherNumberingConfigModule;
VoucherNumberingConfigModule.init();

// ============================================================================
// ANTI-MATRIX BILLING V2 — PHASE 5: GST & TAX CONFIGURATION MODULE
// ============================================================================
const GstTaxConfigModule = {
  isDirty: false,
  currentConfig: null,

  init() {
    // Bind Save and Reset buttons
    const btnSave = document.getElementById("btn-gst-tax-save");
    if (btnSave) {
      btnSave.addEventListener("click", () => this.saveConfiguration());
    }

    const btnReset = document.getElementById("btn-gst-tax-reset");
    if (btnReset) {
      btnReset.addEventListener("click", () => this.resetToDefault());
    }

    const btnVerify = document.getElementById("btn-gst-verify-gstin");
    if (btnVerify) {
      btnVerify.addEventListener("click", () => this.verifyGstin());
    }

    const btnSandbox = document.getElementById("btn-gst-run-sandbox");
    if (btnSandbox) {
      btnSandbox.addEventListener("click", () => this.runSandboxTest());
    }

    // Cess checkbox toggle
    const chkCess = document.getElementById("cfg-gst-enable-cess");
    const inpCessRate = document.getElementById("cfg-gst-default-cess-rate");
    if (chkCess && inpCessRate) {
      chkCess.addEventListener("change", () => {
        inpCessRate.disabled = !chkCess.checked;
        if (!chkCess.checked) inpCessRate.value = "0.00";
        this.markDirty();
        this.runSandboxTest();
      });
    }

    // Track input dirty state across all controls
    const watchIds = [
      "cfg-gst-enabled", "cfg-gst-gstin", "cfg-gst-legal-name", "cfg-gst-state",
      "cfg-gst-reg-type", "cfg-gst-place-of-supply", "cfg-gst-default-rate",
      "cfg-gst-tax-mode", "cfg-gst-rounding-rule", "cfg-gst-prec-curr",
      "cfg-gst-prec-qty", "cfg-gst-hsn-mode", "cfg-gst-effective-date",
      "cfg-gst-show-hsn-summary", "cfg-gst-enable-rcm", "cfg-gst-default-cess-rate"
    ];

    watchIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        const evt = (el.type === "checkbox" || el.tagName === "SELECT") ? "change" : "input";
        el.addEventListener(evt, () => {
          this.markDirty();
          if (id === "cfg-gst-tax-mode" || id === "cfg-gst-rounding-rule" || id === "cfg-gst-state") {
            this.runSandboxTest();
          }
        });
        if (id === "cfg-gst-gstin") {
          el.addEventListener("input", () => {
            el.value = el.value.toUpperCase();
          });
        }
      }
    });

    // Sandbox live listeners
    ["sandbox-price", "sandbox-qty", "sandbox-tax-rate", "sandbox-customer-state"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", () => this.runSandboxTest());
        el.addEventListener("change", () => this.runSandboxTest());
      }
    });

    // Keyboard shortcut (Ctrl+S / Cmd+S)
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        const pane = document.getElementById("pane-gst-tax-config");
        if (pane && pane.style.display !== "none") {
          e.preventDefault();
          this.saveConfiguration();
        }
      }
    });
  },

  markDirty() {
    this.isDirty = true;
    const badge = document.getElementById("gst-tax-persistence-indicator");
    if (badge) {
      badge.textContent = "● Unsaved Changes";
      badge.style.color = "#f59e0b";
      badge.style.borderColor = "#f59e0b";
    }
  },

  clearDirty() {
    this.isDirty = false;
    const badge = document.getElementById("gst-tax-persistence-indicator");
    if (badge) {
      badge.textContent = "● Saved";
      badge.style.color = "#10b981";
      badge.style.borderColor = "#10b981";
    }
  },

  initScreen() {
    const scopeBadge = document.getElementById("gst-tax-scope-badge");
    const activeCompany = (typeof currentCompany !== "undefined" && currentCompany) ? currentCompany : { company_name: "Anti-Matrix HQ", company_code: "CORP01" };
    if (scopeBadge) {
      scopeBadge.textContent = `${activeCompany.company_name || "Company"} Scope`;
    }

    const effDateInput = document.getElementById("cfg-gst-effective-date");
    if (effDateInput && !effDateInput.value) {
      effDateInput.value = new Date().toISOString().split("T")[0];
    }

    this.loadConfiguration();
  },

  loadConfiguration() {
    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;
      let cfg = null;

      if (bridge && typeof bridge.getGstTaxConfig === "function") {
        const raw = bridge.getGstTaxConfig(mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success && res.data) {
          cfg = res.data;
        }
      }

      if (!cfg) {
        cfg = {
          is_gst_enabled: true,
          gstin: "33AAAPL9876C1Z2",
          legal_name: "ANTI-MATRIX RETAIL ENTERPRISE PRIVATE LIMITED",
          state: "Tamil Nadu (33)",
          state_code: "33",
          registration_type: "Regular",
          default_place_of_supply: "Tamil Nadu (33)",
          default_tax_mode: "exclusive",
          default_tax_rate: 18.00,
          enable_cess: false,
          default_cess_rate: 0.00,
          tax_rounding_rule: "nearest_rupee",
          decimal_precision_currency: 2,
          decimal_precision_qty: 3,
          hsn_enforcement_mode: "optional",
          show_hsn_summary: true,
          enable_rcm: false,
          effective_from: new Date().toISOString().split("T")[0]
        };
      }

      this.currentConfig = cfg;
      this.populateForm(cfg);
      this.clearDirty();
      this.runSandboxTest();
    } catch (e) {
      console.error("Failed to load GST tax config:", e);
      if (typeof showNotification === "function") {
        showNotification(`Error loading GST configuration: ${e}`, "error");
      }
    }
  },

  populateForm(cfg) {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val != null ? val : "";
    };
    const setChecked = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = !!val;
    };

    setChecked("cfg-gst-enabled", cfg.is_gst_enabled);
    setVal("cfg-gst-gstin", cfg.gstin || "");
    setVal("cfg-gst-legal-name", cfg.legal_name || "");
    setVal("cfg-gst-state", cfg.state || "");
    setVal("cfg-gst-reg-type", cfg.registration_type || "Regular");
    setVal("cfg-gst-place-of-supply", cfg.default_place_of_supply || cfg.state || "");
    setVal("cfg-gst-default-rate", parseFloat(cfg.default_tax_rate || 18.00).toFixed(2));
    setChecked("cfg-gst-enable-cess", cfg.enable_cess);

    const cessInp = document.getElementById("cfg-gst-default-cess-rate");
    if (cessInp) {
      cessInp.value = parseFloat(cfg.default_cess_rate || 0.00).toFixed(2);
      cessInp.disabled = !cfg.enable_cess;
    }

    setVal("cfg-gst-tax-mode", cfg.default_tax_mode || "exclusive");
    setVal("cfg-gst-rounding-rule", cfg.tax_rounding_rule || "nearest_rupee");
    setVal("cfg-gst-prec-curr", String(cfg.decimal_precision_currency != null ? cfg.decimal_precision_currency : 2));
    setVal("cfg-gst-prec-qty", String(cfg.decimal_precision_qty != null ? cfg.decimal_precision_qty : 3));
    setVal("cfg-gst-hsn-mode", cfg.hsn_enforcement_mode || "optional");

    if (cfg.effective_from) {
      setVal("cfg-gst-effective-date", String(cfg.effective_from).split("T")[0]);
    }

    setChecked("cfg-gst-show-hsn-summary", cfg.show_hsn_summary != null ? cfg.show_hsn_summary : true);
    setChecked("cfg-gst-enable-rcm", !!cfg.enable_rcm);
  },

  collectFormData() {
    const getVal = id => {
      const el = document.getElementById(id);
      return el ? el.value.trim() : "";
    };
    const getChecked = id => {
      const el = document.getElementById(id);
      return el ? el.checked : false;
    };

    const gstin = getVal("cfg-gst-gstin").toUpperCase();
    const stateStr = getVal("cfg-gst-state");
    let stateCode = "";
    const match = stateStr.match(/\((\d{2})\)/);
    if (match) {
      stateCode = match[1];
    } else if (gstin.length >= 2 && /^\d{2}$/.test(gstin.substring(0, 2))) {
      stateCode = gstin.substring(0, 2);
    }

    return {
      is_gst_enabled: getChecked("cfg-gst-enabled"),
      gstin: gstin,
      legal_name: getVal("cfg-gst-legal-name"),
      state: stateStr,
      state_code: stateCode,
      registration_type: getVal("cfg-gst-reg-type") || "Regular",
      default_place_of_supply: getVal("cfg-gst-place-of-supply") || stateStr,
      default_tax_mode: getVal("cfg-gst-tax-mode") || "exclusive",
      default_tax_rate: parseFloat(getVal("cfg-gst-default-rate")) || 18.00,
      supported_tax_rates: [0.00, 5.00, 12.00, 18.00, 28.00],
      enable_cess: getChecked("cfg-gst-enable-cess"),
      default_cess_rate: parseFloat(getVal("cfg-gst-default-cess-rate")) || 0.00,
      tax_rounding_rule: getVal("cfg-gst-rounding-rule") || "nearest_rupee",
      decimal_precision_currency: parseInt(getVal("cfg-gst-prec-curr")) || 2,
      decimal_precision_qty: parseInt(getVal("cfg-gst-prec-qty")) || 3,
      hsn_enforcement_mode: getVal("cfg-gst-hsn-mode") || "optional",
      show_hsn_summary: getChecked("cfg-gst-show-hsn-summary"),
      enable_rcm: getChecked("cfg-gst-enable-rcm"),
      effective_from: getVal("cfg-gst-effective-date") || new Date().toISOString().split("T")[0]
    };
  },

  verifyGstin() {
    const el = document.getElementById("cfg-gst-gstin");
    const msgEl = document.getElementById("gstin-validation-msg");
    const val = el ? el.value.trim().toUpperCase() : "";

    if (!val) {
      if (msgEl) {
        msgEl.textContent = "Please enter a 15-character GSTIN to verify.";
        msgEl.style.color = "#f59e0b";
      }
      return;
    }

    const bridge = window.backendBridge || window.backend;
    if (bridge && typeof bridge.validateGstin === "function") {
      try {
        const raw = bridge.validateGstin(val);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (msgEl) {
          if (res.valid) {
            msgEl.textContent = `✓ Valid GSTIN (State Code: ${res.state_code}, PAN: ${res.pan}, Entity: ${res.entity_number})`;
            msgEl.style.color = "#34d399";
          } else {
            msgEl.textContent = `✗ Invalid GSTIN: ${res.error}`;
            msgEl.style.color = "#f87171";
          }
        }
        return;
      } catch (e) {
        console.warn("Bridge GSTIN validation failed:", e);
      }
    }

    // Client fallback regex
    const gstinRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
    if (gstinRegex.test(val)) {
      if (msgEl) {
        msgEl.textContent = `✓ Valid GSTIN Structure (${val.substring(0, 2)})`;
        msgEl.style.color = "#34d399";
      }
    } else {
      if (msgEl) {
        msgEl.textContent = "✗ Invalid GSTIN format: Must be 15 chars (e.g. 33AAAPL9876C1Z2)";
        msgEl.style.color = "#f87171";
      }
    }
  },

  saveConfiguration() {
    const data = this.collectFormData();

    // If GST is enabled, validate GSTIN format
    if (data.is_gst_enabled && data.gstin) {
      const gstinRegex = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$/;
      if (!gstinRegex.test(data.gstin)) {
        if (typeof showNotification === "function") {
          showNotification("Invalid GSTIN format. Expected 15 characters (e.g. 33AAAPL9876C1Z2).", "error");
        }
        const msgEl = document.getElementById("gstin-validation-msg");
        if (msgEl) {
          msgEl.textContent = "✗ Invalid GSTIN format: Must match standard 15-character GST specification";
          msgEl.style.color = "#f87171";
        }
        return;
      }
    }

    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;

      if (bridge && typeof bridge.saveGstTaxConfig === "function") {
        const raw = bridge.saveGstTaxConfig(JSON.stringify(data), mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;

        if (res && res.success) {
          if (typeof showNotification === "function") {
            showNotification("GST & Tax Configuration saved successfully. Changes take effect prospectively.", "success");
          }
          this.currentConfig = res.data || data;
          this.clearDirty();
          this.runSandboxTest();
          return;
        } else if (res && res.error) {
          if (typeof showNotification === "function") {
            showNotification(`Failed to save GST configuration: ${res.error}`, "error");
          }
          return;
        }
      }

      // Offline / fallback save
      this.currentConfig = data;
      this.clearDirty();
      if (typeof showNotification === "function") {
        showNotification("GST & Tax Configuration saved locally.", "success");
      }
    } catch (e) {
      if (typeof showNotification === "function") {
        showNotification(`Error saving GST configuration: ${e}`, "error");
      }
    }
  },

  resetToDefault() {
    if (!confirm("Are you sure you want to restore standard GST factory defaults (18% default, standard 0/5/12/18/28% slabs, Round to nearest rupee)? Historical invoices will not be affected.")) {
      return;
    }

    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;

      if (bridge && typeof bridge.resetGstTaxConfig === "function") {
        const raw = bridge.resetGstTaxConfig(mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;

        if (res && res.success) {
          if (typeof showNotification === "function") {
            showNotification("GST & Tax Configuration restored to standard factory defaults.", "success");
          }
          this.loadConfiguration();
          return;
        } else if (res && res.error) {
          if (typeof showNotification === "function") {
            showNotification(`Failed to reset GST configuration: ${res.error}`, "error");
          }
          return;
        }
      }

      // Fallback reset
      this.loadConfiguration();
    } catch (e) {
      if (typeof showNotification === "function") {
        showNotification(`Error resetting GST configuration: ${e}`, "error");
      }
    }
  },

  runSandboxTest() {
    const price = parseFloat(document.getElementById("sandbox-price")?.value) || 0;
    const qty = parseFloat(document.getElementById("sandbox-qty")?.value) || 1;
    const rate = parseFloat(document.getElementById("sandbox-tax-rate")?.value) || 0;
    const custState = document.getElementById("sandbox-customer-state")?.value || "Tamil Nadu (33)";
    const taxMode = document.getElementById("cfg-gst-tax-mode")?.value || "exclusive";
    const roundingRule = document.getElementById("cfg-gst-rounding-rule")?.value || "nearest_rupee";
    const compState = document.getElementById("cfg-gst-state")?.value || "Tamil Nadu (33)";

    // Determine Intra vs Inter
    const compCode = compState.match(/\((\d{2})\)/)?.[1] || "33";
    const custCode = custState.match(/\((\d{2})\)/)?.[1] || "33";
    const isIntraState = compCode === custCode;

    let taxable = 0;
    let taxAmount = 0;
    const gross = price * qty;

    if (taxMode === "inclusive" && rate > 0) {
      taxable = Math.round((gross / (1 + rate / 100)) * 100) / 100;
      taxAmount = Math.round((gross - taxable) * 100) / 100;
    } else {
      taxable = Math.round(gross * 100) / 100;
      taxAmount = Math.round((taxable * (rate / 100)) * 100) / 100;
    }

    let cgst = 0;
    let sgst = 0;
    let igst = 0;

    if (isIntraState) {
      cgst = Math.round((taxAmount / 2) * 100) / 100;
      sgst = Math.round((taxAmount - cgst) * 100) / 100; // Zero penny discrepancy
    } else {
      igst = taxAmount;
    }

    const unroundedTotal = taxable + cgst + sgst + igst;
    let grandTotal = unroundedTotal;
    let roundOff = 0;

    if (roundingRule === "nearest_rupee") {
      grandTotal = Math.round(unroundedTotal);
      roundOff = Math.round((grandTotal - unroundedTotal) * 100) / 100;
    } else if (roundingRule === "two_decimals") {
      grandTotal = Math.round(unroundedTotal * 100) / 100;
      roundOff = 0;
    }

    // Update UI elements
    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt("sandbox-res-tax-type", isIntraState ? "Intra-state (CGST + SGST)" : "Inter-state (IGST)");
    setTxt("sandbox-res-taxable", `₹ ${taxable.toFixed(2)}`);

    const rowCgst = document.getElementById("sandbox-row-cgst");
    const rowSgst = document.getElementById("sandbox-row-sgst");
    const rowIgst = document.getElementById("sandbox-row-igst");

    if (isIntraState) {
      if (rowCgst) { rowCgst.style.display = "flex"; rowCgst.querySelector("span").textContent = `CGST (${(rate / 2).toFixed(1)}%):`; }
      if (rowSgst) { rowSgst.style.display = "flex"; rowSgst.querySelector("span").textContent = `SGST (${(rate / 2).toFixed(1)}%):`; }
      if (rowIgst) rowIgst.style.display = "none";
      setTxt("sandbox-res-cgst", `₹ ${cgst.toFixed(2)}`);
      setTxt("sandbox-res-sgst", `₹ ${sgst.toFixed(2)}`);
    } else {
      if (rowCgst) rowCgst.style.display = "none";
      if (rowSgst) rowSgst.style.display = "none";
      if (rowIgst) { rowIgst.style.display = "flex"; rowIgst.querySelector("span").textContent = `IGST (${rate.toFixed(1)}%):`; }
      setTxt("sandbox-res-igst", `₹ ${igst.toFixed(2)}`);
    }

    setTxt("sandbox-res-roundoff", `₹ ${roundOff >= 0 ? "+" : ""}${roundOff.toFixed(2)}`);
    setTxt("sandbox-res-grandtotal", `₹ ${grandTotal.toFixed(2)}`);
  }
};

window.GstTaxConfigModule = GstTaxConfigModule;
GstTaxConfigModule.init();

// ============================================================================
// ANTI-MATRIX BILLING V2 — PHASE 6: INVENTORY CONFIGURATION MODULE
// ============================================================================
const InventoryConfigModule = {
  isDirty: false,
  currentConfig: null,

  init() {
    // Bind Save and Reset buttons
    const btnSave = document.getElementById("btn-inventory-save");
    if (btnSave) {
      btnSave.addEventListener("click", () => this.saveConfiguration());
    }

    const btnReset = document.getElementById("btn-inventory-reset");
    if (btnReset) {
      btnReset.addEventListener("click", () => this.resetToDefault());
    }

    const btnSim = document.getElementById("btn-inv-run-simulator");
    if (btnSim) {
      btnSim.addEventListener("click", () => this.runStockSimulator());
    }

    // Track input dirty state across all controls
    const watchIds = [
      "cfg-inv-enable-tracking", "cfg-inv-default-uom", "cfg-inv-qty-precision",
      "cfg-inv-allow-fractional", "cfg-inv-default-type", "cfg-inv-barcode-symbology",
      "cfg-inv-auto-sku", "cfg-inv-allow-negative-stock", "cfg-inv-validate-availability",
      "cfg-inv-warning-behavior", "cfg-inv-min-stock-level", "cfg-inv-reorder-level",
      "cfg-inv-reorder-qty", "cfg-inv-max-stock-level", "cfg-inv-valuation-method",
      "cfg-inv-default-mat-centre", "cfg-inv-track-branch-stock", "cfg-inv-allow-transfers",
      "cfg-inv-enable-barcode", "cfg-inv-enable-batch", "cfg-inv-enable-expiry",
      "cfg-inv-link-hsn", "cfg-inv-enable-low-stock-alert", "cfg-inv-warn-on-low-stock",
      "cfg-inv-warn-on-negative-stock", "cfg-inv-warn-on-expiry", "cfg-inv-expiry-days"
    ];

    watchIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        const evt = (el.type === "checkbox" || el.tagName === "SELECT") ? "change" : "input";
        el.addEventListener(evt, () => {
          this.markDirty();
          if (id === "cfg-inv-allow-negative-stock" || id === "cfg-inv-min-stock-level" || id === "cfg-inv-reorder-level") {
            this.runStockSimulator();
          }
        });
      }
    });

    // Simulator live listeners
    ["sim-current-stock", "sim-current-wac", "sim-inward-qty", "sim-unit-cost", "sim-outward-qty"].forEach(id => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("input", () => this.runStockSimulator());
        el.addEventListener("change", () => this.runStockSimulator());
      }
    });

    // Keyboard shortcut (Ctrl+S / Cmd+S)
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        const pane = document.getElementById("pane-inventory-config");
        if (pane && pane.style.display !== "none") {
          e.preventDefault();
          this.saveConfiguration();
        }
      }
    });
  },

  markDirty() {
    this.isDirty = true;
    const badge = document.getElementById("inventory-persistence-indicator");
    if (badge) {
      badge.textContent = "● Unsaved Changes";
      badge.style.color = "#f59e0b";
      badge.style.borderColor = "#f59e0b";
    }
  },

  clearDirty() {
    this.isDirty = false;
    const badge = document.getElementById("inventory-persistence-indicator");
    if (badge) {
      badge.textContent = "● Saved";
      badge.style.color = "#10b981";
      badge.style.borderColor = "#10b981";
    }
  },

  initScreen() {
    const scopeBadge = document.getElementById("inventory-scope-badge");
    const activeCompany = (typeof currentCompany !== "undefined" && currentCompany) ? currentCompany : { company_name: "Anti-Matrix HQ", company_code: "CORP01" };
    if (scopeBadge) {
      scopeBadge.textContent = `${activeCompany.company_name || "Company"} Scope`;
    }

    this.loadConfiguration();
  },

  loadConfiguration() {
    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;
      let cfg = null;

      if (bridge && typeof bridge.getInventoryConfig === "function") {
        const raw = bridge.getInventoryConfig(mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;
        if (res && res.success && res.data) {
          cfg = res.data;
        }
      }

      if (!cfg) {
        cfg = {
          enable_inventory_tracking: true,
          default_uom: "Pcs.",
          qty_decimal_precision: 3,
          allow_fractional_qty: true,
          default_product_type: "Stockable",
          auto_generate_sku: true,
          barcode_symbology: "EAN-13",
          allow_negative_stock: false,
          validate_stock_on_sale: true,
          stock_warning_behavior: "warn_and_allow",
          low_stock_alert_enabled: true,
          default_min_stock_level: 10.0,
          default_reorder_level: 15.0,
          default_reorder_qty: 50.0,
          default_max_stock_level: 500.0,
          valuation_method: "weighted_average",
          default_material_centre: "Main Store",
          track_branch_stock: true,
          allow_inter_branch_transfer: true,
          enable_batch_tracking: false,
          enable_expiry_tracking: false,
          enable_barcode_tracking: true,
          link_hsn_sac: true,
          warn_on_low_stock: true,
          warn_on_negative_stock: true,
          warn_on_expiry: false,
          expiry_warning_days: 30
        };
      }

      this.currentConfig = cfg;
      this.populateForm(cfg);
      this.clearDirty();
      this.runStockSimulator();
    } catch (e) {
      console.error("Failed to load inventory config:", e);
      if (typeof showNotification === "function") {
        showNotification(`Error loading inventory configuration: ${e}`, "error");
      }
    }
  },

  populateForm(cfg) {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.value = val != null ? val : "";
    };
    const setChecked = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.checked = !!val;
    };

    setChecked("cfg-inv-enable-tracking", cfg.enable_inventory_tracking);
    setVal("cfg-inv-default-uom", cfg.default_uom || "Pcs.");
    setVal("cfg-inv-qty-precision", String(cfg.qty_decimal_precision != null ? cfg.qty_decimal_precision : 3));
    setChecked("cfg-inv-allow-fractional", cfg.allow_fractional_qty);
    setVal("cfg-inv-default-type", cfg.default_product_type || "Stockable");
    setChecked("cfg-inv-auto-sku", cfg.auto_generate_sku);
    setVal("cfg-inv-barcode-symbology", cfg.barcode_symbology || "EAN-13");

    setChecked("cfg-inv-allow-negative-stock", cfg.allow_negative_stock);
    setChecked("cfg-inv-validate-availability", cfg.validate_stock_on_sale);
    setVal("cfg-inv-warning-behavior", cfg.stock_warning_behavior || "warn_and_allow");
    setChecked("cfg-inv-low-stock-alert_enabled", cfg.low_stock_alert_enabled);

    setVal("cfg-inv-min-stock-level", parseFloat(cfg.default_min_stock_level || 10.0).toFixed(1));
    setVal("cfg-inv-reorder-level", parseFloat(cfg.default_reorder_level || 15.0).toFixed(1));
    setVal("cfg-inv-reorder-qty", parseFloat(cfg.default_reorder_qty || 50.0).toFixed(1));
    setVal("cfg-inv-max-stock-level", parseFloat(cfg.default_max_stock_level || 500.0).toFixed(1));

    setVal("cfg-inv-valuation-method", cfg.valuation_method || "weighted_average");
    setVal("cfg-inv-default-mat-centre", cfg.default_material_centre || "Main Store");
    setChecked("cfg-inv-track-branch-stock", cfg.track_branch_stock);
    setChecked("cfg-inv-allow-transfers", cfg.allow_inter_branch_transfer);

    setChecked("cfg-inv-enable-barcode", cfg.enable_barcode_tracking);
    setChecked("cfg-inv-enable-batch", cfg.enable_batch_tracking);
    setChecked("cfg-inv-enable-expiry", cfg.enable_expiry_tracking);
    setChecked("cfg-inv-link-hsn", cfg.link_hsn_sac);

    setChecked("cfg-inv-enable-low-stock-alert", cfg.low_stock_alert_enabled);
    setChecked("cfg-inv-warn-on-low-stock", cfg.warn_on_low_stock);
    setChecked("cfg-inv-warn-on-negative-stock", cfg.warn_on_negative_stock);
    setChecked("cfg-inv-warn-on-expiry", cfg.warn_on_expiry);
    setVal("cfg-inv-expiry-days", String(cfg.expiry_warning_days || 30));
  },

  collectFormData() {
    const getVal = id => {
      const el = document.getElementById(id);
      return el ? el.value.trim() : "";
    };
    const getChecked = id => {
      const el = document.getElementById(id);
      return el ? el.checked : false;
    };

    return {
      enable_inventory_tracking: getChecked("cfg-inv-enable-tracking"),
      default_uom: getVal("cfg-inv-default-uom") || "Pcs.",
      qty_decimal_precision: parseInt(getVal("cfg-inv-qty-precision")) || 3,
      allow_fractional_qty: getChecked("cfg-inv-allow-fractional"),
      default_product_type: getVal("cfg-inv-default-type") || "Stockable",
      auto_generate_sku: getChecked("cfg-inv-auto-sku"),
      barcode_symbology: getVal("cfg-inv-barcode-symbology") || "EAN-13",
      allow_negative_stock: getChecked("cfg-inv-allow-negative-stock"),
      validate_stock_on_sale: getChecked("cfg-inv-validate-availability"),
      stock_warning_behavior: getVal("cfg-inv-warning-behavior") || "warn_and_allow",
      low_stock_alert_enabled: getChecked("cfg-inv-enable-low-stock-alert"),
      default_min_stock_level: parseFloat(getVal("cfg-inv-min-stock-level")) || 10.0,
      default_reorder_level: parseFloat(getVal("cfg-inv-reorder-level")) || 15.0,
      default_reorder_qty: parseFloat(getVal("cfg-inv-reorder-qty")) || 50.0,
      default_max_stock_level: parseFloat(getVal("cfg-inv-max-stock-level")) || 500.0,
      valuation_method: getVal("cfg-inv-valuation-method") || "weighted_average",
      default_material_centre: getVal("cfg-inv-default-mat-centre") || "Main Store",
      track_branch_stock: getChecked("cfg-inv-track-branch-stock"),
      allow_inter_branch_transfer: getChecked("cfg-inv-allow-transfers"),
      enable_batch_tracking: getChecked("cfg-inv-enable-batch"),
      enable_expiry_tracking: getChecked("cfg-inv-enable-expiry"),
      enable_barcode_tracking: getChecked("cfg-inv-enable-barcode"),
      link_hsn_sac: getChecked("cfg-inv-link-hsn"),
      warn_on_low_stock: getChecked("cfg-inv-warn-on-low-stock"),
      warn_on_negative_stock: getChecked("cfg-inv-warn-on-negative-stock"),
      warn_on_expiry: getChecked("cfg-inv-warn-on-expiry"),
      expiry_warning_days: parseInt(getVal("cfg-inv-expiry-days")) || 30
    };
  },

  saveConfiguration() {
    const data = this.collectFormData();

    // Threshold consistency check
    if (data.default_reorder_level < data.default_min_stock_level) {
      if (typeof showNotification === "function") {
        showNotification("Validation error: Reorder level cannot be less than minimum stock level.", "error");
      }
      return;
    }
    if (data.default_max_stock_level < data.default_reorder_level) {
      if (typeof showNotification === "function") {
        showNotification("Validation error: Maximum stock level cannot be less than reorder level.", "error");
      }
      return;
    }

    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;

      if (bridge && typeof bridge.saveInventoryConfig === "function") {
        const raw = bridge.saveInventoryConfig(JSON.stringify(data), mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;

        if (res && res.success) {
          if (typeof showNotification === "function") {
            showNotification("Inventory & Stock Configuration saved successfully. Settings take effect immediately.", "success");
          }
          this.currentConfig = res.data || data;
          this.clearDirty();
          this.runStockSimulator();
          return;
        } else if (res && res.error) {
          if (typeof showNotification === "function") {
            showNotification(`Failed to save inventory configuration: ${res.error}`, "error");
          }
          return;
        }
      }

      // Offline / fallback save
      this.currentConfig = data;
      this.clearDirty();
      if (typeof showNotification === "function") {
        showNotification("Inventory Configuration saved locally.", "success");
      }
    } catch (e) {
      if (typeof showNotification === "function") {
        showNotification(`Error saving inventory configuration: ${e}`, "error");
      }
    }
  },

  resetToDefault() {
    if (!confirm("Are you sure you want to restore standard inventory factory defaults (Negative Stock Disabled, WAC valuation, 10 min stock, 15 reorder level)? Historical stock movements will not be affected.")) {
      return;
    }

    try {
      const mode = (typeof activeBillingMode !== "undefined" && activeBillingMode) ? activeBillingMode : "traditional";
      const bridge = window.backendBridge || window.backend;

      if (bridge && typeof bridge.resetInventoryConfig === "function") {
        const raw = bridge.resetInventoryConfig(mode);
        const res = typeof raw === "string" ? JSON.parse(raw) : raw;

        if (res && res.success) {
          if (typeof showNotification === "function") {
            showNotification("Inventory Configuration restored to standard factory defaults.", "success");
          }
          this.loadConfiguration();
          return;
        } else if (res && res.error) {
          if (typeof showNotification === "function") {
            showNotification(`Failed to reset inventory configuration: ${res.error}`, "error");
          }
          return;
        }
      }

      this.loadConfiguration();
    } catch (e) {
      if (typeof showNotification === "function") {
        showNotification(`Error resetting inventory configuration: ${e}`, "error");
      }
    }
  },

  runStockSimulator() {
    const curStock = parseFloat(document.getElementById("sim-current-stock")?.value) || 0.0;
    const curWac = parseFloat(document.getElementById("sim-current-wac")?.value) || 0.0;
    const inQty = parseFloat(document.getElementById("sim-inward-qty")?.value) || 0.0;
    const inCost = parseFloat(document.getElementById("sim-unit-cost")?.value) || 0.0;
    const outQty = parseFloat(document.getElementById("sim-outward-qty")?.value) || 0.0;
    const allowNegative = document.getElementById("cfg-inv-allow-negative-stock")?.checked || false;
    const minLevel = parseFloat(document.getElementById("cfg-inv-min-stock-level")?.value) || 10.0;
    const reorderLevel = parseFloat(document.getElementById("cfg-inv-reorder-level")?.value) || 15.0;
    const uom = document.getElementById("cfg-inv-default-uom")?.value || "Pcs.";

    const projectedStock = curStock + inQty - outQty;

    let policyStatus = "✓ Transaction Allowed";
    let policyColor = "#34d399";

    if (projectedStock < 0) {
      if (!allowNegative) {
        policyStatus = "✗ Blocked: Negative Stock Prohibited";
        policyColor = "#f87171";
      } else {
        policyStatus = "⚠️ Warning: Negative Stock Permitted";
        policyColor = "#f59e0b";
      }
    }

    let status = "OPTIMAL";
    let statusColor = "#34d399";
    if (projectedStock < 0) {
      status = "NEGATIVE_STOCK";
      statusColor = "#ef4444";
    } else if (projectedStock === 0) {
      status = "OUT_OF_STOCK";
      statusColor = "#f59e0b";
    } else if (projectedStock <= minLevel) {
      status = "LOW_STOCK";
      statusColor = "#f87171";
    } else if (projectedStock <= reorderLevel) {
      status = "REORDER_REQUIRED";
      statusColor = "#fbbf24";
    }

    // WAC update
    let newWac = curWac;
    if (inQty > 0 && inCost > 0) {
      const existingVal = Math.max(0, curStock) * curWac;
      const inwardVal = inQty * inCost;
      const totalPool = Math.max(0, curStock) + inQty;
      if (totalPool > 0) {
        newWac = Math.round(((existingVal + inwardVal) / totalPool) * 100) / 100;
      }
    }

    const valuation = Math.round(Math.max(0, projectedStock) * newWac * 100) / 100;

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    const polEl = document.getElementById("sim-res-policy-status");
    if (polEl) {
      polEl.textContent = policyStatus;
      polEl.style.color = policyColor;
    }

    setTxt("sim-res-projected-stock", `${projectedStock.toFixed(3)} ${uom}`);

    const statEl = document.getElementById("sim-res-stock-status");
    if (statEl) {
      statEl.textContent = status;
      statEl.style.color = statusColor;
    }

    setTxt("sim-res-wac-rate", `₹ ${newWac.toFixed(2)}`);
    setTxt("sim-res-valuation", `₹ ${valuation.toFixed(2)}`);
  }
};

window.InventoryConfigModule = InventoryConfigModule;
InventoryConfigModule.init();

function initPaperConfigScreen() {
  PaperConfigModule.initScreen();
}

window.PaperConfigModule = PaperConfigModule;
window.initPaperConfigScreen = initPaperConfigScreen;

PaperConfigModule.init();

ZoomController.init();
showScreen("view-login");
