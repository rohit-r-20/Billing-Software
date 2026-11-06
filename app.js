// =============================================================
// ALPHA BILLING SOFTWARE - COMPLETE APPLICATION ENGINE
// =============================================================

// Default seed company: ANTI MATRIX as the first company
const DEFAULT_COMPANIES = [
  {
    id: "COMP0001",
    name: "ANTI MATRIX",
    code: "COMP0001",
    finYear: "2026-2027 (1 Yr)",
    taxNo: "33AAAPL1234F1Z1",
    state: "Tamilnadu",
    username: "A",
    password: "a"
  }
];

// App State
let companies = loadCompanies();
let filteredCompanies = [...companies];
let selectedIndex = 0;
let activeCompany = null;
let currentPendingCompany = null;
let currentScreen = "view-companies"; // view-companies | view-dashboard | view-add-account-master | view-add-item-master | view-sales-voucher | view-sales-list
let uiZoom = parseFloat(localStorage.getItem("alpha_ui_zoom") || "1.0");

// Dual Billing Mode & Tabs State
let activeBillingMode = "traditional"; // "traditional" | "fast_billing"
let openTabs = new Set(["traditional"]);
let lastTraditionalScreen = "view-dashboard";
let lastFastBillingScreen = "view-fast-billing";
let isSavingPosSale = false;
let currentPrintVchId = null;
let currentPrintVchData = null;
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
  try {
    const saved = localStorage.getItem("alpha_companies");
    if (saved) {
      const parsed = JSON.parse(saved);
      // Ensure old companies (BHAVANI TRADERS) are deleted and ANTI MATRIX is primary
      const hasAntiMatrix = parsed.some((c) => c.name.toUpperCase().includes("ANTI MATRIX"));
      const hasOldBhavani = parsed.some((c) => c.name.toUpperCase().includes("BHAVANI"));
      if (hasOldBhavani && !hasAntiMatrix) {
        localStorage.setItem("alpha_companies", JSON.stringify(DEFAULT_COMPANIES));
        return [...DEFAULT_COMPANIES];
      }
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (e) {
    console.error("Error reading companies:", e);
  }
  localStorage.setItem("alpha_companies", JSON.stringify(DEFAULT_COMPANIES));
  return [...DEFAULT_COMPANIES];
}

function saveCompanies() {
  try {
    localStorage.setItem("alpha_companies", JSON.stringify(companies));
  } catch (e) {
    console.error("Error saving companies:", e);
  }
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
// ZOOM / FONT & ELEMENT RESIZING ENGINE
// =============================================================
function applyZoom(newScale) {
  // Clamp scale between 0.75 and 1.50
  uiZoom = Math.min(Math.max(newScale, 0.75), 1.5);
  uiZoom = Math.round(uiZoom * 100) / 100;

  if (appRoot) {
    appRoot.style.zoom = uiZoom;
    appRoot.style.width = `calc(100vw / ${uiZoom})`;
    appRoot.style.height = `calc(100vh / ${uiZoom})`;
    appRoot.style.maxWidth = `calc(100vw / ${uiZoom})`;
    appRoot.style.maxHeight = `calc(100vh / ${uiZoom})`;
  }
  document.documentElement.style.setProperty("--ui-scale", uiZoom);

  const percentage = Math.round(uiZoom * 100) + "%";
  if (quickZoomLabel) {
    quickZoomLabel.textContent = percentage;
  }

  localStorage.setItem("alpha_ui_zoom", uiZoom.toString());
  showNotification(`Interface Scale: ${percentage}`);
}

window.addEventListener("resize", () => {
  if (appRoot && uiZoom) {
    appRoot.style.width = `calc(100vw / ${uiZoom})`;
    appRoot.style.height = `calc(100vh / ${uiZoom})`;
    appRoot.style.maxWidth = `calc(100vw / ${uiZoom})`;
    appRoot.style.maxHeight = `calc(100vh / ${uiZoom})`;
  }
});

if (quickZoomIn) quickZoomIn.addEventListener("click", () => applyZoom(uiZoom + 0.05));
if (quickZoomOut) quickZoomOut.addEventListener("click", () => applyZoom(uiZoom - 0.05));
if (menuZoomIn) menuZoomIn.addEventListener("click", () => applyZoom(uiZoom + 0.05));
if (menuZoomOut) menuZoomOut.addEventListener("click", () => applyZoom(uiZoom - 0.05));
if (menuZoomReset) menuZoomReset.addEventListener("click", () => applyZoom(1.0));

// =============================================================
// SCREEN VIEW ROUTER
// =============================================================
function showScreen(screenId) {
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
    viewDayBook
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
    if (isStandalone) {
      appTabsBar.style.display = "none";
    } else {
      appTabsBar.style.display = "flex";
      updateAppTabsDisplay(isFastBilling ? "fast_billing" : "traditional");
    }
  }

  // Manage Sidebar: Fast Billing cashier workspace hides sidebar for distraction-free 100% width
  const alphaSidebar = document.getElementById("alpha-sidebar");
  if (alphaSidebar) {
    if (isStandalone || isFastBilling) {
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
    "view-companies": { title: "List of Companies", bc: "Alpha Billing &rsaquo; Company &rsaquo; <strong>Switch Company</strong>" },
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
    "view-day-book": "btn-nav-daybook"
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
    initSalesVoucherScreen();
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
function populateLoginCompanies() {
  if (!loginCompanySelect) return;
  const currentVal = loginCompanySelect.value;
  loginCompanySelect.innerHTML = "";

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
  const companyCode = loginCompanySelect ? loginCompanySelect.value : (companies[0] ? companies[0].code : "COMP0001");
  const username = (loginUserInput ? loginUserInput.value : "").trim();
  const password = loginPwdInput ? loginPwdInput.value : "";

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

  if (window.backend && window.backend.authenticateUser) {
    window.backend.authenticateUser(companyCode, username, password, (resp) => {
      setLoginLoading(false);
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          activeCompany = res.data;
          if (loginPwdInput) loginPwdInput.value = "";
          openBillingModeSelection(activeCompany);
        } else {
          showLoginAlert(res.error || "Invalid User ID or Password. Please try again.");
          if (loginPwdInput) {
            loginPwdInput.select();
            loginPwdInput.focus();
          }
        }
      } catch (e) {
        showLoginAlert("Authentication error: " + e.message);
      }
    });
  } else if (window.backend && window.backend.authenticateCompany) {
    window.backend.authenticateCompany(companyCode, password, (resp) => {
      setLoginLoading(false);
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          activeCompany = res.data;
          if (loginPwdInput) loginPwdInput.value = "";
          openBillingModeSelection(activeCompany);
        } else {
          showLoginAlert(res.error || "Invalid User ID or Password. Please try again.");
          if (loginPwdInput) {
            loginPwdInput.select();
            loginPwdInput.focus();
          }
        }
      } catch (e) {
        showLoginAlert("Authentication error: " + e.message);
      }
    });
  } else {
    // Browser local fallback
    setTimeout(() => {
      setLoginLoading(false);
      const comp = companies.find((c) => c.code === companyCode) || companies[0];
      if (comp) {
        const expectedUser = comp.username || "A";
        const expectedPass = comp.password || "a";
        const matchUser = username.toUpperCase() === expectedUser.toUpperCase();
        const matchPass = password === expectedPass || (expectedPass === "a" && password === "a");
        if (matchUser && matchPass) {
          activeCompany = comp;
          if (loginPwdInput) loginPwdInput.value = "";
          openBillingModeSelection(activeCompany);
        } else {
          showLoginAlert("Invalid User ID or Password. Please try again.");
          if (loginPwdInput) {
            loginPwdInput.select();
            loginPwdInput.focus();
          }
        }
      } else {
        showLoginAlert("Selected company not found. Please select a valid company.");
      }
    }, 150);
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
    loginUserInput.value = comp.username || "A";
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
  activeCompany = null;
  if (loginPwdInput) loginPwdInput.value = "";
  hideLoginAlert();
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
  if (modeCompanyName) modeCompanyName.textContent = activeCompany.name;
  if (modeBranchName) modeBranchName.textContent = activeCompany.branch || "Main Branch";
  if (modeUserName) modeUserName.textContent = `${activeCompany.username || "A"} (Administrator)`;
  if (modeFyName) modeFyName.textContent = (activeCompany.finYear || "2026-27").split(" ")[0];
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
  fetchCustomerCategoryDiscounts();
  checkLowStockAlerts(true);
  showNotification(`Traditional Billing: ${activeCompany.name}`);
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

function openFastBillingPrint(vchId, vchData = null) {
  currentPrintVchId = vchId;
  currentPrintVchData = vchData;
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

  // If full details not passed, fetch from backend
  if (!currentPrintVchData || !currentPrintVchData.items) {
    const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
    if (window.backend && window.backend.getVoucherDetails && vchId) {
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
    if (posPrintVchNo) posPrintVchNo.textContent = currentPrintVchData.vch_no || "POS-001";
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
  posInvoicePreviewSheet.className = `pos-invoice-sheet sheet-${format}`;

  if (format === "thermal-80" || format === "thermal-58") {
    renderThermalReceiptPreview(posInvoicePreviewSheet, comp, vch, format);
  } else if (format === "a4" || format === "a5") {
    renderTaxInvoiceSheetPreview(posInvoicePreviewSheet, comp, vch, format);
  } else {
    // Custom dimensions
    const w = document.getElementById("custom-paper-width") ? document.getElementById("custom-paper-width").value : "80";
    posInvoicePreviewSheet.style.width = `${w}mm`;
    renderThermalReceiptPreview(posInvoicePreviewSheet, comp, vch, "thermal-80");
  }
}

function renderThermalReceiptPreview(container, comp, vch, format) {
  const is58 = format === "thermal-58";
  const items = vch.items || [];
  const vchNo = vch.vch_no || "POS-001";
  const dateStr = vch.vch_date || new Date().toLocaleDateString("en-IN");
  const timeStr = vch.created_at ? vch.created_at.substring(11, 16) : new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  const party = vch.party_name || "CASH";
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
    const price = parseFloat(it.price || 0).toFixed(2);
    const total = parseFloat(it.line_total || it.amount || (qty * price)).toFixed(2);
    if (is58) {
      return `
        <tr>
          <td colspan="3">${escapeHtml(name)}</td>
        </tr>
        <tr>
          <td style="padding-left: 8px;">${qty} ${unit}</td>
          <td style="text-align: right;">@ ₹${price}</td>
          <td style="text-align: right; font-weight: 700;">₹${total}</td>
        </tr>
      `;
    }
    return `
      <tr>
        <td>${escapeHtml(name)}</td>
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
          ${is58 ? `<tr><th>Item</th><th style="text-align:right;">Qty/Rate</th><th style="text-align:right;">Total</th></tr>` :
                   `<tr><th>Item</th><th style="text-align:center;">Qty</th><th style="text-align:right;">Price</th><th style="text-align:right;">Total</th></tr>`}
        </thead>
        <tbody>
          ${itemsHtml || '<tr><td colspan="4" style="text-align:center; padding:10px;">No items</td></tr>'}
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
      <div class="t-divider"></div>
      <div class="t-center t-sub" style="margin-top: 6px;">*** THANK YOU FOR SHOPPING! ***</div>
      <div class="t-center t-sub">Goods once sold cannot be returned.</div>
      <div class="t-center t-sub" style="font-size: 9px; color: #666; margin-top: 4px;">Powered by Alpha Billing ERP</div>
    </div>
  `;
}

function renderTaxInvoiceSheetPreview(container, comp, vch, format) {
  const isA5 = format === "a5";
  const items = vch.items || [];
  const vchNo = vch.vch_no || "POS-001";
  const dateStr = vch.vch_date || new Date().toLocaleDateString("en-IN");
  const party = vch.party_name || "CASH";
  const subtotal = parseFloat(vch.subtotal || 0).toFixed(2);
  const cgst = parseFloat(vch.cgst_amount || 0).toFixed(2);
  const sgst = parseFloat(vch.sgst_amount || 0).toFixed(2);
  const igst = parseFloat(vch.igst_amount || 0).toFixed(2);
  const roundOff = parseFloat(vch.round_off || 0).toFixed(2);
  const grandTotal = parseFloat(vch.grand_total || 0).toFixed(2);
  const payMethod = vch.payment_method || "CASH";
  const discTotal = parseFloat(vch.discount_total || 0);

  let itemsHtml = items.map((it, idx) => {
    const name = it.item_name || it.name || "Item";
    const qty = parseFloat(it.qty || 0);
    const unit = it.unit || "Pcs.";
    const price = parseFloat(it.price || 0).toFixed(2);
    const taxRate = parseFloat(it.tax_rate || 18);
    const discPct = parseFloat(it.discount_percent || 0);
    const total = parseFloat(it.line_total || it.amount || (qty * price)).toFixed(2);

    return `
      <tr>
        <td style="text-align: center;">${idx + 1}</td>
        <td><strong>${escapeHtml(name)}</strong></td>
        <td style="text-align: center;">${qty} ${unit}</td>
        <td style="text-align: right;">₹ ${price}</td>
        <td style="text-align: center;">${discPct > 0 ? `${discPct}%` : '-'}</td>
        <td style="text-align: center;">${taxRate}%</td>
        <td style="text-align: right; font-weight: 700;">₹ ${total}</td>
      </tr>
    `;
  }).join("");

  container.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 14px; font-size: ${isA5 ? '11px' : '12px'};">
      <!-- Invoice Header -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #1e3a8a; padding-bottom: 12px;">
        <div>
          <h1 style="margin: 0; font-size: ${isA5 ? '16px' : '20px'}; color: #1e3a8a; font-weight: 900;">${escapeHtml(comp.name)}</h1>
          <div style="color: #475569; margin-top: 4px;">State: ${escapeHtml(comp.state || "Tamilnadu")} | Reg. Business Entity</div>
          <div style="color: #1e293b; font-weight: 700; margin-top: 2px;">GSTIN: ${escapeHtml(comp.taxNo || "N/A")}</div>
        </div>
        <div style="text-align: right;">
          <span style="display: inline-block; background: #1e3a8a; color: #fff; padding: 4px 14px; font-weight: 800; font-size: ${isA5 ? '11px' : '13px'}; border-radius: 4px;">TAX INVOICE</span>
          <div style="margin-top: 6px; font-weight: 700;">Invoice No: <span style="color: #047857;">${escapeHtml(vchNo)}</span></div>
          <div style="color: #64748b;">Date: ${escapeHtml(dateStr)}</div>
        </div>
      </div>

      <!-- Bill To & Details -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; background: #f8fafc; padding: 10px; border-radius: 6px; border: 1px solid #e2e8f0;">
        <div>
          <div style="font-weight: 700; color: #64748b; font-size: 10px; text-transform: uppercase;">Billed To Customer:</div>
          <div style="font-size: 13px; font-weight: 800; color: #0f172a; margin-top: 2px;">${escapeHtml(party)}</div>
          <div style="color: #475569; font-size: 11px;">Payment Method: <strong>${escapeHtml(payMethod)}</strong></div>
        </div>
        <div style="text-align: right;">
          <div style="font-weight: 700; color: #64748b; font-size: 10px; text-transform: uppercase;">Counter Details:</div>
          <div style="color: #0f172a; font-weight: 600;">Cashier: ${escapeHtml(comp.username || "Admin")}</div>
          <div style="color: #64748b; font-size: 11px;">Place of Supply: ${escapeHtml(comp.state || "Tamilnadu")}</div>
        </div>
      </div>

      <!-- Table of items -->
      <table style="width: 100%; border-collapse: collapse; margin-top: 6px;">
        <thead>
          <tr style="background: #1e40af; color: #ffffff; font-size: 11px;">
            <th style="padding: 6px 8px; width: 30px; text-align: center;">#</th>
            <th style="padding: 6px 8px; text-align: left;">Item Description</th>
            <th style="padding: 6px 8px; width: 70px; text-align: center;">Qty</th>
            <th style="padding: 6px 8px; width: 80px; text-align: right;">Price</th>
            <th style="padding: 6px 8px; width: 60px; text-align: center;">Disc</th>
            <th style="padding: 6px 8px; width: 60px; text-align: center;">Tax %</th>
            <th style="padding: 6px 8px; width: 90px; text-align: right;">Amount</th>
          </tr>
        </thead>
        <tbody style="border-bottom: 1px solid #cbd5e1;">
          ${itemsHtml || '<tr><td colspan="7" style="text-align:center; padding:16px;">No items</td></tr>'}
        </tbody>
      </table>

      <!-- Totals Grid -->
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-top: 10px;">
        <div style="max-width: 50%; font-size: 10px; color: #64748b;">
          <strong>Terms &amp; Conditions:</strong><br />
          1. Goods once sold will not be taken back or exchanged.<br />
          2. All disputes are subject to local jurisdiction.<br />
          3. This is a computer-generated tax invoice.
        </div>
        <div style="width: 220px; display: flex; flex-direction: column; gap: 4px;">
          <div style="display: flex; justify-content: space-between;"><span>Taxable Subtotal:</span><span>₹ ${subtotal}</span></div>
          ${discTotal > 0 ? `<div style="display: flex; justify-content: space-between; color: #047857;"><span>Discount:</span><span>- ₹ ${discTotal.toFixed(2)}</span></div>` : ""}
          ${parseFloat(cgst) > 0 ? `<div style="display: flex; justify-content: space-between;"><span>CGST:</span><span>₹ ${cgst}</span></div>` : ""}
          ${parseFloat(sgst) > 0 ? `<div style="display: flex; justify-content: space-between;"><span>SGST:</span><span>₹ ${sgst}</span></div>` : ""}
          ${parseFloat(igst) > 0 ? `<div style="display: flex; justify-content: space-between;"><span>IGST:</span><span>₹ ${igst}</span></div>` : ""}
          ${parseFloat(roundOff) !== 0 ? `<div style="display: flex; justify-content: space-between;"><span>Round Off:</span><span>₹ ${roundOff}</span></div>` : ""}
          <div style="display: flex; justify-content: space-between; font-size: 14px; font-weight: 900; color: #047857; border-top: 2px solid #047857; padding-top: 6px; margin-top: 4px;">
            <span>GRAND TOTAL:</span><span>₹ ${grandTotal}</span>
          </div>
        </div>
      </div>

      <!-- Signature Box -->
      <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: ${isA5 ? '16px' : '36px'};">
        <div style="font-size: 10px; color: #94a3b8;">E. &amp; O.E.</div>
        <div style="text-align: center; border-top: 1px dashed #64748b; width: 180px; padding-top: 6px; font-size: 11px; font-weight: 700;">
          Authorized Signatory<br />
          <span style="font-size: 9px; color: #64748b; font-weight: normal;">For ${escapeHtml(comp.name)}</span>
        </div>
      </div>
    </div>
  `;
}

function triggerInvoicePrint() {
  if (!currentPrintVchId && (!currentPrintVchData || !currentPrintVchData.vch_no)) {
    showNotification("No invoice loaded to print.");
    return;
  }
  const copiesInput = document.getElementById("pos-print-copies");
  const copies = parseInt(copiesInput ? copiesInput.value : 1) || 1;
  const printerSelect = document.getElementById("pos-printer-select");
  const printerName = printerSelect ? printerSelect.value : "Default Printer";
  const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
  const vchId = currentPrintVchId || (currentPrintVchData ? currentPrintVchData.id : "");

  if (printStatusMsg) {
    printStatusMsg.style.display = "block";
    printStatusMsg.className = "print-status-box info";
    printStatusMsg.textContent = `Printing ${copies} cop${copies === 1 ? 'y' : 'ies'} to ${printerName}...`;
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
      printStatusMsg.textContent = `✅ Successfully printed ${copies} cop${copies === 1 ? 'y' : 'ies'} of Bill #${currentPrintVchData ? currentPrintVchData.vch_no : 'POS-001'} to ${printerName}.`;
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

function openAddAccountMaster() {
  if (formAccountMaster) formAccountMaster.reset();
  const idEl = document.getElementById("acc-id");
  if (idEl) idEl.value = "";
  const titleEl = document.getElementById("account-master-screen-title");
  if (titleEl) titleEl.textContent = "Add Account Master";
  showScreen("view-add-account-master");
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
    const stateEl = document.getElementById("acc-state");
    if (stateEl) stateEl.value = acc.state || "Tamilnadu";
    const dealerEl = document.getElementById("acc-dealer-type");
    if (dealerEl) dealerEl.value = acc.dealer_type || acc.dealerType || "Unregistered";
    const catEl = document.getElementById("acc-customer-category");
    if (catEl) catEl.value = acc.customer_category || acc.customerCategory || "Direct Customer";
    if (accGstin) accGstin.value = acc.gstin || "";
    const mobEl = document.getElementById("acc-mobile");
    if (mobEl) mobEl.value = acc.mobile || "";
    const bankNameEl = document.getElementById("acc-bank-name");
    if (bankNameEl) bankNameEl.value = acc.bank_name || acc.bankName || "";
    const bankAccEl = document.getElementById("acc-bank-acc");
    if (bankAccEl) bankAccEl.value = acc.bank_acc || acc.bankAcc || "";
    const ifscEl = document.getElementById("acc-bank-ifsc");
    if (ifscEl) ifscEl.value = acc.ifsc || "";
    const titleEl = document.getElementById("account-master-screen-title");
    if (titleEl) titleEl.textContent = `Modify Account Master: ${acc.name}`;
    showScreen("view-add-account-master");
  };

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
      const matchG = !g || acc.account_group === g || acc.group === g;
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
      tr.innerHTML = `
        <td style="text-align: center; color: #64748b;">${idx + 1}</td>
        <td><strong>${escapeHtml(acc.name)}</strong></td>
        <td><span class="badge-category">${escapeHtml(acc.account_group || acc.group || "Sundry Debtors")}</span></td>
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
  const name = accName.value.trim();
  if (!name) {
    alert("Please enter Account Name.");
    accName.focus();
    return;
  }

  const custCategory = document.getElementById("acc-customer-category") ? document.getElementById("acc-customer-category").value : "Direct Customer";
  const existingAccId = document.getElementById("acc-id") ? document.getElementById("acc-id").value : "";

  const accountData = {
    name: name,
    alias: document.getElementById("acc-alias").value.trim(),
    printName: document.getElementById("acc-print-name").value.trim(),
    group: document.getElementById("acc-group").value,
    customerCategory: custCategory,
    customer_category: custCategory,
    opBal: document.getElementById("acc-op-bal").value,
    opType: document.getElementById("acc-op-type").value,
    address: [
      document.getElementById("acc-addr1").value.trim(),
      document.getElementById("acc-addr2").value.trim()
    ].filter(Boolean).join(", "),
    state: document.getElementById("acc-state").value.trim(),
    dealerType: document.getElementById("acc-dealer-type").value,
    gstin: accGstin.value.trim().toUpperCase(),
    mobile: document.getElementById("acc-mobile").value.trim(),
    bankName: document.getElementById("acc-bank-name").value.trim(),
    bankAcc: document.getElementById("acc-bank-acc").value.trim(),
    ifsc: document.getElementById("acc-bank-ifsc").value.trim().toUpperCase(),
    createdAt: new Date().toISOString()
  };
  if (existingAccId) {
    accountData.id = existingAccId;
  }

  if (activeCompany) {
    if (window.backend) {
      window.backend.saveAccount(activeCompany.id, JSON.stringify(accountData), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
            showNotification(existingAccId ? `Account "${name}" modified successfully!` : `Account "${name}" saved to database!`);
          }
        } catch (e) {}
      });
    }
    const key = `alpha_accounts_${activeCompany.code}`;
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(key) || "[]");
    } catch (e) {}
    const existingIdx = list.findIndex(a => (existingAccId && a.id === existingAccId) || a.name === name);
    if (existingIdx !== -1) {
      list[existingIdx] = accountData;
    } else {
      list.push(accountData);
    }
    localStorage.setItem(key, JSON.stringify(list));
  }

  showNotification(existingAccId ? `Account Master "${name}" updated!` : `Account Master "${name}" saved!`);
  formAccountMaster.reset();
  const idEl = document.getElementById("acc-id");
  if (idEl) idEl.value = "";
  const titleEl = document.getElementById("account-master-screen-title");
  if (titleEl) titleEl.textContent = "Add Account Master";
  showScreen("view-account-list");
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
// ITEM MASTER & PRODUCTS CATALOGUE MANAGEMENT
// =============================================================

function resetProductMasterForm() {
  if (formItemMaster) formItemMaster.reset();
  const idEl = document.getElementById("item-id");
  if (idEl) idEl.value = "";
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
  const titleEl = document.getElementById("item-master-screen-title");
  if (titleEl) titleEl.textContent = "Add Product";
}

function loadProductForEditing(itemId) {
  fetchItemById(itemId, (item) => {
    if (!item) {
      alert("Product not found.");
      return;
    }
    const idEl = document.getElementById("item-id");
    if (idEl) idEl.value = item.id || "";
    
    if (itemName) itemName.value = item.name || "";
    const aliasEl = document.getElementById("item-alias");
    if (aliasEl) aliasEl.value = item.barcodes || item.alias || "";
    const printEl = document.getElementById("item-print-name");
    if (printEl) printEl.value = item.print_name || item.printName || item.name || "";
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
    if (salesPriceEl) salesPriceEl.value = item.sales_price ?? item.salesPrice ?? 0;
    const purcPriceEl = document.getElementById("item-purc-price");
    if (purcPriceEl) purcPriceEl.value = item.purc_price ?? item.purcPrice ?? 0;
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
  });
}

function handleSaveItemMaster() {
  const name = itemName.value.trim();
  if (!name) {
    alert("Please enter Product Name.");
    itemName.focus();
    return;
  }

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

  const itemData = {
    id: existingId,
    name: name,
    alias: document.getElementById("item-alias").value.trim(),
    printName: document.getElementById("item-print-name").value.trim(),
    print_name: document.getElementById("item-print-name").value.trim(),
    group: document.getElementById("item-group").value,
    item_group: document.getElementById("item-group").value,
    unit: document.getElementById("item-unit").value,
    opStockQty: document.getElementById("item-op-qty").value,
    op_stock_qty: document.getElementById("item-op-qty").value,
    opStockVal: document.getElementById("item-op-val").value,
    op_stock_val: document.getElementById("item-op-val").value,
    taxCategory: document.getElementById("item-tax-cat").value,
    tax_category: document.getElementById("item-tax-cat").value,
    hsn: document.getElementById("item-hsn").value.trim(),
    salesPrice: document.getElementById("item-sales-price").value,
    sales_price: document.getElementById("item-sales-price").value,
    purcPrice: document.getElementById("item-purc-price").value,
    purc_price: document.getElementById("item-purc-price").value,
    mrp: document.getElementById("item-mrp").value,
    minSalesPrice: document.getElementById("item-min-sales-price").value,
    min_sales_price: document.getElementById("item-min-sales-price").value,
    description: document.getElementById("item-desc").value.trim(),
    min_stock_alert_level: parsedMinStock,
    min_stock_level: parsedMinStock,
    reorder_level: parsedReorder,
    reorder_qty: parsedReorderQty,
    max_stock_level: parsedMaxStock,
    alert_enabled: alertEnabled,
    updatedAt: new Date().toISOString()
  };

  if (activeCompany) {
    if (window.backend) {
      window.backend.saveItem(activeCompany.id, JSON.stringify(itemData), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
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

  showNotification(`Product "${name}" ${existingId ? 'updated' : 'saved'}!`);
  resetProductMasterForm();
  showScreen("view-items-list");
}

function fetchAllItems(query, callback) {
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
    (it.alias && it.alias.toUpperCase().includes(q)) ||
    (it.group && it.group.toUpperCase().includes(q))
  );
  callback(filtered);
}

function fetchItemById(itemId, callback) {
  if (window.backend && activeCompany) {
    window.backend.getItemById(activeCompany.id, itemId, (resp) => {
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

      const price = parseFloat(it.sales_price ?? it.salesPrice ?? 0).toFixed(2);
      const stock = parseFloat(it.current_stock ?? it.op_stock_qty ?? it.opStockQty ?? 0);
      const barcode = it.barcodes || it.alias || "-";
      const group = it.item_group || it.group || "General";
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

// Initialize Sales Billing Screen
function initSalesVoucherScreen() {
  const nextNo = getNextVoucherNumber();
  vchNumber.value = nextNo;
  infoVchNo.textContent = nextNo;

  // Set today's date
  const now = new Date();
  const dd = String(now.getDate()).padStart(2, "0");
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const yyyy = now.getFullYear();
  vchDate.value = `${dd}-${mm}-${yyyy}`;

  const days = ["(Sun)", "(Mon)", "(Tue)", "(Wed)", "(Thu)", "(Fri)", "(Sat)"];
  vchDayLabel.textContent = days[now.getDay()];

  // Reset inputs
  vchPartyInput.value = "CASH";
  vchNarration.value = "";
  updateVoucherPartyCategory();

  // Populate Party autocomplete list from Account Masters
  partyDatalist.innerHTML = "";
  const optCash = document.createElement("option");
  optCash.value = "CASH";
  partyDatalist.appendChild(optCash);

  if (activeCompany) {
    const key = `alpha_accounts_${activeCompany.code}`;
    const accounts = JSON.parse(localStorage.getItem(key) || "[]");
    accounts.forEach((acc) => {
      const opt = document.createElement("option");
      opt.value = acc.name;
      opt.label = `${acc.group} | GST: ${acc.gstin || "N/A"}`;
      partyDatalist.appendChild(opt);
    });
  }

  // Render 11 item rows
  renderVoucherItemRows();
  recalculateVoucherTotals();
  vchPartyInput.focus();
}

function populateVoucherRowWithItem(rowNum, item) {
  const rowInput = vchItemsTbody.querySelector(`.vch-item-input[data-row="${rowNum}"]`);
  const unitEl = vchItemsTbody.querySelector(`.vch-unit-input[data-row="${rowNum}"]`);
  const priceEl = vchItemsTbody.querySelector(`.vch-price-input[data-row="${rowNum}"]`);
  const qtyEl = vchItemsTbody.querySelector(`.vch-qty-input[data-row="${rowNum}"]`);

  if (rowInput) {
    rowInput.value = item.name || "";
    rowInput.dataset.itemId = item.id || "";
  }
  if (unitEl && item.unit) unitEl.value = item.unit;
  const price = parseFloat(item.sales_price ?? item.salesPrice ?? 0);
  if (priceEl && price > 0) priceEl.value = price.toFixed(2);

  if (qtyEl && (!qtyEl.value || parseFloat(qtyEl.value) <= 0)) {
    qtyEl.value = "1";
  }

  calcRowAmount(rowNum);
  recalculateVoucherTotals();

  if (vchItemInfo) {
    vchItemInfo.innerHTML = `
      Product: <strong>${escapeHtml(item.name)}</strong><br/>
      Category: ${escapeHtml(item.item_group || item.group || "General")} | Unit: ${escapeHtml(item.unit || "Pcs.")}<br/>
      Price: ₹${price.toFixed(2)} | Tax Cat: ${escapeHtml(item.tax_category || item.taxCategory || "GST 18%")}
    `;
  }

  showNotification(`Selected ${item.name}`);
  if (qtyEl) {
    qtyEl.focus();
    qtyEl.select();
  }
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
    if (!vchItemAutocompletePopup || vchItemAutocompletePopup.style.display === "none") {
      if (e.key === "F1") {
        e.preventDefault();
        openProductSearchModal("VOUCHER", row);
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      activeVchSuggestionIndex = (activeVchSuggestionIndex + 1) % currentVchSuggestions.length;
      highlightVchSuggestion(activeVchSuggestionIndex);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      activeVchSuggestionIndex = (activeVchSuggestionIndex - 1 + currentVchSuggestions.length) % currentVchSuggestions.length;
      highlightVchSuggestion(activeVchSuggestionIndex);
    } else if (e.key === "Enter" && activeVchSuggestionIndex >= 0) {
      e.preventDefault();
      e.stopPropagation();
      const chosen = currentVchSuggestions[activeVchSuggestionIndex];
      populateVoucherRowWithItem(row, chosen);
      hideVchAutocompletePopup();
    } else if (e.key === "Escape") {
      hideVchAutocompletePopup();
    }
  });
}

function renderVchAutocompletePopup(input, items, row) {
  if (!vchItemAutocompletePopup) return;
  vchItemAutocompletePopup.innerHTML = "";

  const rect = input.getBoundingClientRect();
  const parentEl = input.closest(".vch-table-wrapper") || document.body;
  const parentRect = parentEl.getBoundingClientRect();

  vchItemAutocompletePopup.style.top = `${rect.bottom - parentRect.top + 2}px`;
  vchItemAutocompletePopup.style.left = `${rect.left - parentRect.left}px`;
  vchItemAutocompletePopup.style.width = "420px";

  items.forEach((item, index) => {
    const div = document.createElement("div");
    div.className = "vch-suggestion-item";
    div.dataset.index = index;

    const price = parseFloat(item.sales_price ?? item.salesPrice ?? 0).toFixed(2);
    const barcode = item.barcodes || item.alias || "";

    div.innerHTML = `
      <div>
        <div class="vch-sugg-name">${escapeHtml(item.name)}</div>
        <div class="vch-sugg-code">${barcode ? `Barcode: ${escapeHtml(barcode)} | ` : ""}${escapeHtml(item.unit || "Pcs.")}</div>
      </div>
      <div class="vch-sugg-price">₹ ${price}</div>
    `;

    div.addEventListener("mousedown", (e) => {
      e.preventDefault();
      populateVoucherRowWithItem(row, item);
      hideVchAutocompletePopup();
    });

    vchItemAutocompletePopup.appendChild(div);
  });

  vchItemAutocompletePopup.style.display = "block";
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

// Render 11 item rows into billing table
function renderVoucherItemRows() {
  vchItemsTbody.innerHTML = "";

  for (let i = 1; i <= 11; i++) {
    const tr = document.createElement("tr");
    tr.dataset.row = i;

    tr.innerHTML = `
      <td class="col-vch-sn">${i}</td>
      <td class="col-vch-item">
        <input type="text" class="vch-item-input" data-row="${i}" placeholder="${i === 1 ? 'Type or select product (F1 to search)' : ''}" autocomplete="off" />
      </td>
      <td class="col-vch-qty">
        <input type="number" step="1" min="0" class="vch-qty-input" data-row="${i}" placeholder="0" />
      </td>
      <td class="col-vch-unit">
        <input type="text" class="vch-unit-input" data-row="${i}" value="Pcs." />
      </td>
      <td class="col-vch-price">
        <input type="number" step="0.01" min="0" class="vch-price-input" data-row="${i}" placeholder="0.00" />
      </td>
      <td class="col-vch-amount">
        <input type="text" class="vch-amount-input" data-row="${i}" value="0.00" readonly style="font-weight: 700; color: #1e40af;" />
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

  // Attach autocomplete & selection listeners
  vchItemsTbody.querySelectorAll(".vch-item-input").forEach((input) => {
    const row = input.dataset.row;
    setupVoucherAutocomplete(input, row);

    input.addEventListener("focus", (e) => {
      const val = e.target.value.trim();
      if (val) {
        vchItemInfo.textContent = `Selected Product: ${val}`;
      }
    });

    input.addEventListener("change", (e) => {
      const val = e.target.value.trim().toUpperCase();
      if (!val) return;
      fetchAllItems(val, (items) => {
        const matched = items.find((it) => it.name.toUpperCase() === val || (it.alias && it.alias.toUpperCase() === val));
        if (matched) {
          populateVoucherRowWithItem(row, matched);
        }
      });
    });
  });
}

function updateVoucherPartyCategory() {
  if (!vchPartyInput) return;
  const partyName = vchPartyInput.value.trim().toUpperCase();
  const badgeEl = document.getElementById("vch-party-category-badge");
  if (!badgeEl) return;

  if (!partyName || partyName === "CASH" || partyName === "CASH SALE") {
    activeVoucherCustomerCategory = "Direct Customer";
    const discPct = cachedCategoryDiscounts["Direct Customer"] || 0.0;
    badgeEl.textContent = `Direct (${discPct}%)`;
    badgeEl.className = "vch-party-category-badge direct";
    badgeEl.style.display = "inline-flex";
    return;
  }

  const foundAcc = cachedAccountsList.find(a => (a.name || "").toUpperCase() === partyName);
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
  const gross = qty * price;

  const catRate = cachedCategoryDiscounts[activeVoucherCustomerCategory] || 0.0;
  const discAmt = Math.round(gross * (catRate / 100) * 100) / 100;
  const netAmt = Math.max(0, gross - discAmt);

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
      igst = (subtotal * taxRate) / 100;
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
      cgst = (subtotal * halfRate) / 100;
      sgst = (subtotal * halfRate) / 100;

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

  const rawTotal = subtotal + cgst + sgst + igst;
  const roundedTotal = Math.round(rawTotal);
  const roundDiff = (roundedTotal - rawTotal);
  sundryRoundAmt.textContent = (roundDiff >= 0 ? "+" : "") + roundDiff.toFixed(2);

  vchGrandTotal.textContent = `₹ ${roundedTotal.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
}

vchSaleType.addEventListener("change", recalculateVoucherTotals);
btnApplyTax.addEventListener("click", () => {
  recalculateVoucherTotals();
  showNotification("Tax & Bill Sundry recalculated.");
});

// Save Sales Voucher
function handleSaveSalesVoucher() {
  const party = vchPartyInput.value.trim();
  if (!party) {
    alert("Please enter or select a Party / Customer Name.");
    vchPartyInput.focus();
    return;
  }

  // Ensure voucher number is unique
  let currentNo = vchNumber.value.trim();
  if (!currentNo) currentNo = getNextVoucherNumber();

  if (isVoucherNumberUsed(currentNo)) {
    const freshNo = getNextVoucherNumber();
    alert(`Voucher number ${currentNo} is already used in a previous bill.\nUpdating to next unique voucher number: ${freshNo}`);
    vchNumber.value = freshNo;
    currentNo = freshNo;
  }

  // Collect items
  const items = [];
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

    if (name && (qty > 0 || price > 0)) {
      items.push({ 
        sn: row, 
        name, 
        qty, 
        unit: unitEl.value, 
        price, 
        amount,
        item_id: nameEl.dataset.itemId || undefined
      });
    }
  });

  if (items.length === 0) {
    alert("Please add at least one item with quantity and price.");
    return;
  }

  const subtotal = parseFloat(vchSubtotalVal.textContent) || 0;
  const grandTotal = vchGrandTotal.textContent.replace("₹", "").trim();

  const voucherRecord = {
    vchNo: currentNo,
    series: vchSeries.value,
    date: vchDate.value,
    saleType: vchSaleType.value,
    party: party,
    matCentre: vchMatCentre.value,
    narration: vchNarration.value.trim(),
    items: items,
    subtotal: subtotal,
    grandTotal: grandTotal,
    createdAt: new Date().toISOString()
  };

  if (window.backend && activeCompany) {
    const payload = {
      party_name: party,
      customer_category: activeVoucherCustomerCategory || "Direct Customer",
      sale_type: vchSaleType.value,
      payment_method: "CASH",
      series: vchSeries.value,
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

    if (isSalesModifyMode && currentModifySaleVchId) {
      window.backend.modifySaleInvoice(activeCompany.id, currentModifySaleVchId, JSON.stringify(payload), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) {
            showNotification(`Sales Bill #${currentNo} modified successfully! Inventory and accounts reconciled.`);
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
      return;
    }

    window.backend.createSaleInvoice(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          lastCompletedVoucher = r.data.vch_no;
          checkLowStockAlerts(false);
        }
      } catch (e) {}
    });
  }

  saveSalesVoucherRecord(voucherRecord);
  showNotification(`Sales Bill #${currentNo} saved successfully!`);

  // Prompt or prepare next sequential bill
  if (confirm(`Bill #${currentNo} saved!\nCreate next bill (#${getNextVoucherNumber()})?`)) {
    initSalesVoucherScreen();
  } else {
    showScreen("view-sales-list");
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
    if (vchPartyInput) vchPartyInput.value = vch.party_name || "CASH";
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
        nameEl.value = it ? (it.name || "") : "";
        nameEl.dataset.itemId = it ? (it.item_id || "") : "";
      }
      if (qtyEl) qtyEl.value = it ? (it.qty || "") : "";
      if (unitEl) unitEl.value = it ? (it.unit || "Pcs.") : "Pcs.";
      if (priceEl) priceEl.value = it ? (it.price || "") : "";
      if (amtEl) amtEl.value = it ? (it.line_total || it.amount || "") : "";
    }
    recalculateVoucherTotals();
    showScreen("view-sales-voucher");
  };

  if (window.backend && window.backend.listVouchers) {
    window.backend.listVouchers(activeCompany.id, (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success && Array.isArray(r.data)) {
          const found = r.data.find(v => v.id === vchId || v.vch_no === vchId);
          loadInvoice(found);
          return;
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
            tr.title = "Double-click to modify invoice";
            tr.innerHTML = `
              <td style="font-weight: 800; color: #1e40af;">${escapeHtml(bill.vch_no)}</td>
              <td>${escapeHtml(bill.vch_date)}</td>
              <td style="font-weight: 700;">${escapeHtml(bill.party_name)}</td>
              <td>${escapeHtml(bill.sale_type)}</td>
              <td>${((bill.grand_total || 0) - (bill.subtotal || 0)).toFixed(2)}</td>
              <td style="font-weight: 800; color: #047857;">₹ ${(bill.grand_total || 0).toFixed(2)}</td>
            `;
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
        <td colspan="6" style="text-align: center; color: #64748b; padding: 24px;">
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
    `;
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

    if (window.backend && window.backend.listAccounts) {
      window.backend.listAccounts(activeCompany.id, (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success && Array.isArray(r.data)) {
            cachedAccountsList = r.data;
            populateOptions(r.data.filter(a => a.account_group === "Sundry Debtors" || a.group === "Sundry Debtors" || !a.account_group));
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

// Synchronize companies and accounts from Python SQLite backend
function syncFromBackend() {
  if (!window.backend) return;
  window.backend.listCompanies((resp) => {
    try {
      const r = JSON.parse(resp);
      if (r.success && Array.isArray(r.data) && r.data.length > 0) {
        companies = r.data;
        filteredCompanies = [...companies];
        renderCompanyTable();
        showNotification("Connected to persistent SQLite database.");
      }
    } catch (e) {
      console.error("Backend sync error:", e);
    }
  });
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
if (menuAddItemMaster) menuAddItemMaster.addEventListener("click", () => {
  resetProductMasterForm();
  showScreen("view-add-item-master");
});
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

// Item Master (Add / Edit Product)
btnItemSave.addEventListener("click", handleSaveItemMaster);
btnItemQuit.addEventListener("click", () => showScreen("view-items-list"));
btnItemCloseTop.addEventListener("click", () => showScreen("view-dashboard"));
if (btnItemNewClear) btnItemNewClear.addEventListener("click", resetProductMasterForm);
if (btnItemOpenList) btnItemOpenList.addEventListener("click", openProductsListView);
if (btnItemViewListBottom) btnItemViewListBottom.addEventListener("click", openProductsListView);
if (btnItemBackList) btnItemBackList.addEventListener("click", openProductsListView);

// Products List (Catalogue View)
if (btnItemsListAdd) btnItemsListAdd.addEventListener("click", () => {
  resetProductMasterForm();
  showScreen("view-add-item-master");
});
if (btnItemsListAddBottom) btnItemsListAddBottom.addEventListener("click", () => {
  resetProductMasterForm();
  showScreen("view-add-item-master");
});
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
    const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
    const vchId = currentPrintVchId || (currentPrintVchData ? currentPrintVchData.id : "");
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
if (btnPrintScreenNewBill) {
  btnPrintScreenNewBill.addEventListener("click", () => openFastBillingNewBill());
}
if (btnPrintNextBill) {
  btnPrintNextBill.addEventListener("click", () => openFastBillingNewBill());
}
if (btnPosPrintBack) {
  btnPosPrintBack.addEventListener("click", () => openFastBillingNewBill());
}
if (btnPosPrintClose) {
  btnPosPrintClose.addEventListener("click", () => openFastBillingNewBill());
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

      const price = parseFloat(it.sales_price ?? it.salesPrice ?? 0).toFixed(2);
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
      const compId = (activeCompany ? (activeCompany.id || activeCompany.code) : "") || "COMP0001";
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

    const price = parseFloat(item.sales_price ?? item.salesPrice ?? 0).toFixed(2);
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
  // Zoom hotkeys: Ctrl/Cmd + Plus/Minus
  if ((e.ctrlKey || e.metaKey) && (e.key === "+" || e.key === "=")) {
    e.preventDefault();
    applyZoom(uiZoom + 0.05);
    return;
  }
  if ((e.ctrlKey || e.metaKey) && (e.key === "-" || e.key === "_")) {
    e.preventDefault();
    applyZoom(uiZoom - 0.05);
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key === "0") {
    e.preventDefault();
    applyZoom(1.0);
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
    if (e.key === "F4") {
      e.preventDefault();
      openFastBillingNewBill();
    } else if (e.key === "Enter" || (e.ctrlKey && (e.key === "p" || e.key === "P"))) {
      e.preventDefault();
      triggerInvoicePrint();
    } else if (e.key === "Escape") {
      e.preventDefault();
      openFastBillingNewBill();
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
              <td style="text-align: center;">
                <button type="button" class="btn-classic pur-modify-btn" data-id="${vch.id}" style="padding: 2px 8px; font-size: 11px; margin-right: 4px;">Modify</button>
                <button type="button" class="btn-classic pur-view-btn" data-id="${vch.id}" style="padding: 2px 8px; font-size: 11px;">View</button>
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
        const vch = r.data;
        let msg = `PURCHASE VOUCHER: ${vch.vch_no}\n`;
        msg += `Supplier: ${vch.supplier_name}\n`;
        msg += `Supplier Bill: ${vch.supplier_invoice_no} (${vch.supplier_invoice_date})\n`;
        msg += `Date: ${vch.voucher_date}\n\nITEMS:\n`;
        (vch.items || []).forEach((it, i) => {
          msg += `${i+1}. ${it.name} | Qty: ${it.quantity} ${it.unit || ''} | Rate: ₹${it.purchase_price} | Tax: ₹${it.tax_amount} | Total: ₹${it.total_amount}\n`;
        });
        msg += `\nSubtotal: ₹${vch.subtotal}\n`;
        msg += `CGST: ₹${vch.cgst_amount} | SGST: ₹${vch.sgst_amount} | Round Off: ₹${vch.round_off}\n`;
        msg += `GRAND TOTAL: ₹${vch.grand_total}\n`;
        msg += `Payment Mode: ${vch.payment_mode || 'CREDIT'}\n`;
        alert(msg);
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
    { id: "btn-nav-add-product", action: () => showScreen("view-add-item-master") },
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
    { id: "dash-btn-product-add", action: () => showScreen("view-add-item-master") },
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

if (!window.activeCompany) {
  window.activeCompany = {
    id: "COMP0001",
    code: "COMP0001",
    name: "ANTI MATRIX RETAIL & WHOLESALE",
    fin_year: "2026-2027"
  };
}

renderCompanyTable();
populateLoginCompanies();
updateSystemClock();
setInterval(updateSystemClock, 10000);
setupPosBarcodeAutocomplete();
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

// Global Exports
window.renderSelectAccountModifyModal = renderSelectAccountModifyModal;
window.renderSelectItemModifyModal = renderSelectItemModifyModal;
window.renderSelectSalesModifyModal = renderSelectSalesModifyModal;
window.renderSelectPurchaseModifyModal = renderSelectPurchaseModifyModal;
window.openAddAccountMaster = openAddAccountMaster;
window.openModifyAccountMaster = openModifyAccountMaster;
window.openModifySaleInvoice = openModifySaleInvoice;
window.openModifyPurchaseVoucher = openModifyPurchaseVoucher;
window.renderAccountMasterList = renderAccountMasterList;

setupEnterpriseErpEventListeners();
setupCompanyAndPlaceholderModalListeners();
setupThreeOptionWorkflowListeners();
setupSidebarAndDashboardNav();
initCascadingSubmenuPositioning();
applyZoom(uiZoom);
showScreen("view-dashboard");
