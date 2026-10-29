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

// DOM Elements - App Root & Zoom
const appRoot = document.getElementById("app-root");
const quickZoomLabel = document.getElementById("quick-zoom-label");
const quickZoomIn = document.getElementById("quick-zoom-in");
const quickZoomOut = document.getElementById("quick-zoom-out");
const menuZoomIn = document.getElementById("menu-zoom-in");
const menuZoomOut = document.getElementById("menu-zoom-out");
const menuZoomReset = document.getElementById("menu-zoom-reset");

// DOM Elements - Views
const viewCompanies = document.getElementById("view-companies");
const viewModeSelection = document.getElementById("view-mode-selection");
const viewDashboard = document.getElementById("view-dashboard");
const viewAddAccountMaster = document.getElementById("view-add-account-master");
const viewAddItemMaster = document.getElementById("view-add-item-master");
const viewSalesVoucher = document.getElementById("view-sales-voucher");
const viewSalesList = document.getElementById("view-sales-list");

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
const btnItemSave = document.getElementById("btn-item-save");
const btnItemQuit = document.getElementById("btn-item-quit");
const btnItemCloseTop = document.getElementById("btn-item-close-top");
const itemName = document.getElementById("item-name");

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
const viewFastBilling = document.getElementById("view-fast-billing");
const posBarcodeInput = document.getElementById("pos-barcode-input");
const posCartTbody = document.getElementById("pos-cart-tbody");
const posEmptyCartMsg = document.getElementById("pos-empty-cart-msg");
const posItemCount = document.getElementById("pos-item-count");
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

// POS State
let posCart = [];
let heldBills = [];
let lastCompletedVoucher = null;

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
  }
  document.documentElement.style.setProperty("--ui-scale", uiZoom);

  const percentage = Math.round(uiZoom * 100) + "%";
  if (quickZoomLabel) {
    quickZoomLabel.textContent = percentage;
  }

  localStorage.setItem("alpha_ui_zoom", uiZoom.toString());
  showNotification(`Interface Scale: ${percentage}`);
}

quickZoomIn.addEventListener("click", () => applyZoom(uiZoom + 0.05));
quickZoomOut.addEventListener("click", () => applyZoom(uiZoom - 0.05));
menuZoomIn.addEventListener("click", () => applyZoom(uiZoom + 0.05));
menuZoomOut.addEventListener("click", () => applyZoom(uiZoom - 0.05));
menuZoomReset.addEventListener("click", () => applyZoom(1.0));

// =============================================================
// SCREEN VIEW ROUTER
// =============================================================
function showScreen(screenId) {
  currentScreen = screenId;
  const allViews = [
    viewCompanies,
    viewModeSelection,
    viewDashboard,
    viewAddAccountMaster,
    viewAddItemMaster,
    viewSalesVoucher,
    viewSalesList,
    viewFastBilling
  ];

  allViews.forEach((view) => {
    if (view) {
      view.classList.toggle("active", view.id === screenId);
    }
  });

  if (screenId === "view-companies") {
    searchInput.focus();
    renderCompanyTable();
  } else if (screenId === "view-mode-selection") {
    renderModeSelection();
  } else if (screenId === "view-add-account-master") {
    accName.focus();
  } else if (screenId === "view-add-item-master") {
    itemName.focus();
  } else if (screenId === "view-sales-voucher") {
    initSalesVoucherScreen();
  } else if (screenId === "view-sales-list") {
    renderSalesRegister();
  } else if (screenId === "view-fast-billing") {
    initFastBillingScreen();
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
// LOGIN DIALOG
// =============================================================
function openLoginModalForSelected() {
  if (filteredCompanies.length === 0) return;
  const comp = filteredCompanies[selectedIndex];
  currentPendingCompany = comp;

  loginUsername.value = comp.username || "A";
  loginPassword.value = "";
  loginErrorMsg.textContent = "";

  modalLogin.classList.add("show");
  setTimeout(() => loginPassword.focus(), 50);
}

function closeLoginModal() {
  modalLogin.classList.remove("show");
  currentPendingCompany = null;
  if (currentScreen === "view-companies") {
    searchInput.focus();
  }
}

function handleLoginSubmit() {
  if (!currentPendingCompany) return;

  const enteredPass = loginPassword.value;
  const correctPass = currentPendingCompany.password || "";

  const isValid =
    enteredPass === correctPass ||
    (correctPass === "" && (enteredPass === "" || enteredPass === "a" || enteredPass === "admin")) ||
    (correctPass === "a" && (enteredPass === "a" || enteredPass === ""));

  if (isValid) {
    loginErrorMsg.textContent = "";
    activeCompany = currentPendingCompany;
    closeLoginModal();
    openBillingModeSelection(activeCompany);
  } else {
    loginErrorMsg.textContent = "Invalid password! Try again.";
    loginPassword.select();
    loginPassword.focus();
  }
}

// =============================================================
// DUAL BILLING MODE SELECTION
// =============================================================
function openBillingModeSelection(comp) {
  activeCompany = comp;
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

function openFastBillingPos() {
  if (!activeCompany) return;
  if (posHeaderCompany) posHeaderCompany.textContent = activeCompany.name;
  if (posHeaderBranch) posHeaderBranch.textContent = "Branch: Main Branch | Reg: 01";
  if (posHeaderCashier) posHeaderCashier.textContent = `${activeCompany.username || "A"}`;
  showScreen("view-fast-billing");
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

// =============================================================
// COMPANY DASHBOARD
// =============================================================
function enterCompanyDashboard(comp) {
  dashboardWatermark.textContent = `${comp.name} (F.Y. ${comp.finYear})`;
  statusCompName.textContent = `${comp.name} (${comp.code})`;
  statusFy.textContent = comp.finYear.split(" ")[0] || "2026-27";
  statusGstin.textContent = comp.taxNo || "N/A";
  statusUser.textContent = comp.username || "A";
  statusState.textContent = comp.state || "Tamilnadu";
  dashboardBreadcrumb.textContent = `Transactions -> Sales -> Add (Billing)`;

  showScreen("view-dashboard");
  showNotification(`Billing & Accounting: ${comp.name}`);
}

function closeCompany() {
  activeCompany = null;
  showScreen("view-companies");
  showNotification("Company closed.");
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

  saveCompanyConfig(activeCompany.code, config);
  closeConfigurationModal();
  showNotification("Configuration saved successfully!");
}

// =============================================================
// ACCOUNT MASTER
// =============================================================
function handleSaveAccountMaster() {
  const name = accName.value.trim();
  if (!name) {
    alert("Please enter Account Name.");
    accName.focus();
    return;
  }

  const accountData = {
    name: name,
    alias: document.getElementById("acc-alias").value.trim(),
    printName: document.getElementById("acc-print-name").value.trim(),
    group: document.getElementById("acc-group").value,
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

  if (activeCompany) {
    if (window.backend) {
      window.backend.saveAccount(activeCompany.id, JSON.stringify(accountData), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) showNotification(`Account "${name}" saved to database!`);
        } catch (e) {}
      });
    }
    const key = `alpha_accounts_${activeCompany.code}`;
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(key) || "[]");
    } catch (e) {}
    list.push(accountData);
    localStorage.setItem(key, JSON.stringify(list));
  }

  showNotification(`Account Master "${name}" saved!`);
  formAccountMaster.reset();
  showScreen("view-dashboard");
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
// ITEM MASTER
// =============================================================
function handleSaveItemMaster() {
  const name = itemName.value.trim();
  if (!name) {
    alert("Please enter Item Name.");
    itemName.focus();
    return;
  }

  const itemData = {
    name: name,
    alias: document.getElementById("item-alias").value.trim(),
    printName: document.getElementById("item-print-name").value.trim(),
    group: document.getElementById("item-group").value,
    unit: document.getElementById("item-unit").value,
    opStockQty: document.getElementById("item-op-qty").value,
    opStockVal: document.getElementById("item-op-val").value,
    taxCategory: document.getElementById("item-tax-cat").value,
    hsn: document.getElementById("item-hsn").value.trim(),
    salesPrice: document.getElementById("item-sales-price").value,
    purcPrice: document.getElementById("item-purc-price").value,
    mrp: document.getElementById("item-mrp").value,
    minSalesPrice: document.getElementById("item-min-sales-price").value,
    description: document.getElementById("item-desc").value.trim(),
    createdAt: new Date().toISOString()
  };

  if (activeCompany) {
    if (window.backend) {
      window.backend.saveItem(activeCompany.id, JSON.stringify(itemData), (resp) => {
        try {
          const r = JSON.parse(resp);
          if (r.success) showNotification(`Item "${name}" saved to database!`);
        } catch (e) {}
      });
    }
    const key = `alpha_items_${activeCompany.code}`;
    let list = [];
    try {
      list = JSON.parse(localStorage.getItem(key) || "[]");
    } catch (e) {}
    list.push(itemData);
    localStorage.setItem(key, JSON.stringify(list));
  }

  showNotification(`Item Master "${name}" saved!`);
  formItemMaster.reset();
  showScreen("view-dashboard");
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

// Render 11 item rows into billing table
function renderVoucherItemRows() {
  vchItemsTbody.innerHTML = "";

  // Load items from Item Master for autocomplete
  let savedItems = [];
  if (activeCompany) {
    savedItems = JSON.parse(localStorage.getItem(`alpha_items_${activeCompany.code}`) || "[]");
  }

  for (let i = 1; i <= 11; i++) {
    const tr = document.createElement("tr");
    tr.dataset.row = i;

    tr.innerHTML = `
      <td class="col-vch-sn">${i}</td>
      <td class="col-vch-item">
        <input type="text" class="vch-item-input" data-row="${i}" placeholder="${i === 1 ? 'Type or select item name' : ''}" />
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

  // Autocomplete / Item info inspection
  vchItemsTbody.querySelectorAll(".vch-item-input").forEach((input) => {
    input.addEventListener("change", (e) => {
      const val = e.target.value.trim().toUpperCase();
      const matched = savedItems.find((it) => it.name.toUpperCase() === val);
      if (matched) {
        const row = e.target.dataset.row;
        const unitEl = vchItemsTbody.querySelector(`.vch-unit-input[data-row="${row}"]`);
        const priceEl = vchItemsTbody.querySelector(`.vch-price-input[data-row="${row}"]`);
        if (unitEl && matched.unit) unitEl.value = matched.unit;
        if (priceEl && matched.salesPrice && parseFloat(matched.salesPrice) > 0) {
          priceEl.value = matched.salesPrice;
          calcRowAmount(row);
          recalculateVoucherTotals();
        }
        vchItemInfo.innerHTML = `
          Item: <strong>${matched.name}</strong><br/>
          Tax Cat: ${matched.taxCategory || 'GST 18%'}<br/>
          MRP: ₹${matched.mrp || '0.00'} | Min Price: ₹${matched.minSalesPrice || '0.00'}
        `;
      }
    });

    input.addEventListener("focus", (e) => {
      const val = e.target.value.trim();
      if (val) {
        vchItemInfo.textContent = `Selected Item: ${val}`;
      }
    });
  });
}

function calcRowAmount(row) {
  const qtyEl = vchItemsTbody.querySelector(`.vch-qty-input[data-row="${row}"]`);
  const priceEl = vchItemsTbody.querySelector(`.vch-price-input[data-row="${row}"]`);
  const amtEl = vchItemsTbody.querySelector(`.vch-amount-input[data-row="${row}"]`);

  const qty = parseFloat(qtyEl.value) || 0;
  const price = parseFloat(priceEl.value) || 0;
  const total = qty * price;
  amtEl.value = total.toFixed(2);
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
      items.push({ sn: row, name, qty, unit: unitEl.value, price, amount });
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
      sale_type: vchSaleType.value,
      payment_method: "CASH",
      series: vchSeries.value,
      vch_date: vchDate.value,
      narration: vchNarration.value.trim(),
      items: items.map((it) => ({
        name: it.name,
        qty: it.qty,
        unit: it.unit,
        price: it.price,
        line_total: it.amount
      }))
    };
    window.backend.createSaleInvoice(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const r = JSON.parse(resp);
        if (r.success) {
          lastCompletedVoucher = r.data.vch_no;
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
            tr.innerHTML = `
              <td style="font-weight: 800; color: #1e40af;">${escapeHtml(bill.vch_no)}</td>
              <td>${escapeHtml(bill.vch_date)}</td>
              <td style="font-weight: 700;">${escapeHtml(bill.party_name)}</td>
              <td>${escapeHtml(bill.sale_type)}</td>
              <td>${((bill.grand_total || 0) - (bill.subtotal || 0)).toFixed(2)}</td>
              <td style="font-weight: 800; color: #047857;">₹ ${(bill.grand_total || 0).toFixed(2)}</td>
            `;
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

btnNewBillFromList.addEventListener("click", () => showScreen("view-sales-voucher"));
btnCloseSalesList.addEventListener("click", () => showScreen("view-dashboard"));
btnSalesListClose.addEventListener("click", () => showScreen("view-dashboard"));

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

  if (posCart.length === 0) {
    if (posEmptyCartMsg) posEmptyCartMsg.style.display = "block";
    updatePosTotals();
    return;
  }

  if (posEmptyCartMsg) posEmptyCartMsg.style.display = "none";

  posCart.forEach((item, idx) => {
    const tr = document.createElement("tr");
    const lineTotal = item.qty * item.price;
    const taxAmt = (lineTotal * (item.taxRate || 0)) / 100;

    tr.innerHTML = `
      <td style="text-align: center; color: #64748b;">${idx + 1}</td>
      <td style="font-family: monospace; font-weight: 700; color: #1e40af;">${escapeHtml(item.barcode || "-")}</td>
      <td style="font-weight: 700;">${escapeHtml(item.name)}</td>
      <td style="text-align: right;">
        <input type="number" step="0.001" min="0.001" class="pos-cart-qty-input" data-index="${idx}" value="${item.qty}" />
      </td>
      <td style="color: #64748b;">${escapeHtml(item.unit || "Pcs.")}</td>
      <td style="text-align: right; font-weight: 600;">₹ ${item.price.toFixed(2)}</td>
      <td style="text-align: center; color: #047857; font-weight: 700;">${item.taxRate || 0}%</td>
      <td style="text-align: right; font-weight: 800; color: #047857;">₹ ${(lineTotal + taxAmt).toFixed(2)}</td>
      <td style="text-align: center;">
        <button type="button" class="pos-cart-btn-del" data-index="${idx}" title="Remove Item">&times;</button>
      </td>
    `;
    posCartTbody.appendChild(tr);
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

function updatePosTotals() {
  let subtotal = 0;
  let taxTotal = 0;
  let totalQty = 0;

  posCart.forEach((it) => {
    const lineVal = it.qty * it.price;
    const lineTax = (lineVal * (it.taxRate || 0)) / 100;
    subtotal += lineVal;
    taxTotal += lineTax;
    totalQty += it.qty;
  });

  const rawTotal = subtotal + taxTotal;
  const rounded = Math.round(rawTotal);
  const roundDiff = rounded - rawTotal;

  if (posItemCount) posItemCount.textContent = `${posCart.length} items (${totalQty.toFixed(2)} qty)`;
  if (posSubtotal) posSubtotal.textContent = `₹ ${subtotal.toFixed(2)}`;
  if (posTaxTotal) posTaxTotal.textContent = `₹ ${taxTotal.toFixed(2)}`;
  if (posRoundOff) posRoundOff.textContent = (roundDiff >= 0 ? "+" : "") + roundDiff.toFixed(2);
  if (posPayableAmount) posPayableAmount.textContent = `₹ ${rounded.toFixed(2)}`;
}

// POS Barcode Scanner Handler
function handleBarcodeScan(barcodeStr) {
  const code = (barcodeStr || "").trim();
  if (!code) return;

  if (window.backend && activeCompany) {
    window.backend.findByBarcode(activeCompany.id, code, (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success && res.data) {
          addItemToPosCart(res.data);
        } else {
          showNotification(`⚠️ Barcode "${code}" not found! Press F1 to search.`);
        }
      } catch (e) {
        searchLocalItemsForBarcode(code);
      }
    });
  } else {
    searchLocalItemsForBarcode(code);
  }
}

function searchLocalItemsForBarcode(code) {
  const codeUpper = code.toUpperCase();
  let savedItems = [];
  if (activeCompany) {
    savedItems = JSON.parse(localStorage.getItem(`alpha_items_${activeCompany.code}`) || "[]");
  }
  const matched = savedItems.find(
    (it) => (it.alias && it.alias.toUpperCase() === codeUpper) || (it.name && it.name.toUpperCase() === codeUpper)
  );

  if (matched) {
    addItemToPosCart({
      id: matched.name,
      name: matched.name,
      alias: matched.alias || code,
      sales_price: parseFloat(matched.salesPrice) || 0.0,
      unit: matched.unit || "Pcs.",
      tax_category: matched.taxCategory || "GST 18%"
    });
  } else {
    showNotification(`⚠️ Item "${code}" not registered. Press F1 to search.`);
  }
}

function addItemToPosCart(itemData) {
  const existingIdx = posCart.findIndex(
    (it) => (it.id && it.id === itemData.id) || (it.name.toUpperCase() === itemData.name.toUpperCase())
  );

  let taxRate = 18.0;
  const taxCat = itemData.tax_category || itemData.taxCategory || "";
  if (taxCat.includes("28%")) taxRate = 28.0;
  else if (taxCat.includes("12%")) taxRate = 12.0;
  else if (taxCat.includes("5%")) taxRate = 5.0;
  else if (taxCat.includes("0%") || taxCat.includes("Exempt")) taxRate = 0.0;

  if (existingIdx !== -1) {
    posCart[existingIdx].qty += 1;
    showNotification(`Added +1 to ${itemData.name} (Qty: ${posCart[existingIdx].qty})`);
  } else {
    posCart.push({
      id: itemData.id || itemData.name,
      name: itemData.name,
      barcode: itemData.matched_barcode || itemData.alias || "",
      qty: 1.0,
      unit: itemData.unit || "Pcs.",
      price: parseFloat(itemData.sales_price || itemData.salesPrice) || 0.0,
      taxRate: taxRate
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

  let subtotal = 0;
  let taxTotal = 0;
  posCart.forEach((it) => {
    const lineVal = it.qty * it.price;
    subtotal += lineVal;
    taxTotal += (lineVal * (it.taxRate || 0)) / 100;
  });
  const grandTotal = Math.round(subtotal + taxTotal);

  if (method === "CASH") {
    modalCashDueVal.textContent = `₹ ${grandTotal.toFixed(2)}`;
    posCashTendered.value = grandTotal;
    modalCashChangeVal.textContent = "₹ 0.00";
    modalPosCash.classList.add("show");
    setTimeout(() => {
      posCashTendered.focus();
      posCashTendered.select();
    }, 50);
  } else if (method === "UPI") {
    if (confirm(`Confirm UPI payment received of ₹ ${grandTotal.toFixed(2)}?`)) {
      finalizePosSale("UPI", grandTotal, 0);
    }
  } else if (method === "CARD") {
    if (confirm(`Confirm Card transaction of ₹ ${grandTotal.toFixed(2)} on POS terminal?`)) {
      finalizePosSale("CARD", grandTotal, 0);
    }
  } else {
    finalizePosSale("SPLIT", grandTotal, 0);
  }
}

function finalizePosSale(method, amountPaid, changeDue) {
  if (posCart.length === 0) return;

  const vchNum = posVchNo.textContent.trim() || getNextVoucherNumber();
  const now = new Date();
  const dateStr = `${String(now.getDate()).padStart(2, "0")}-${String(now.getMonth() + 1).padStart(2, "0")}-${now.getFullYear()}`;

  const itemsPayload = posCart.map((it, idx) => ({
    id: it.id,
    sn: idx + 1,
    name: it.name,
    qty: it.qty,
    unit: it.unit,
    price: it.price,
    tax_rate: it.taxRate,
    line_total: it.qty * it.price + ((it.qty * it.price * it.taxRate) / 100)
  }));

  const payload = {
    party_name: "CASH",
    sale_type: "L/GST-18%",
    payment_method: method,
    items: itemsPayload,
    vch_date: dateStr,
    narration: `POS Checkout (${method})`
  };

  if (window.backend && activeCompany) {
    window.backend.createSaleInvoice(activeCompany.id, JSON.stringify(payload), (resp) => {
      try {
        const res = JSON.parse(resp);
        if (res.success) {
          lastCompletedVoucher = res.data.vch_no;
          showNotification(`Sale #${res.data.vch_no} completed successfully!`);
          // Display Thermal Receipt
          showReceiptModal(res.data.voucher_id);
          posCart = [];
          renderPosCart();
          initFastBillingScreen();
        } else {
          alert(`Checkout failed: ${res.error}`);
        }
      } catch (e) {
        alert(`Checkout error: ${e}`);
      }
    });
  } else {
    // Local fallback
    const voucherRecord = {
      vchNo: vchNum,
      series: "POS",
      date: dateStr,
      saleType: "L/GST-18%",
      party: "CASH",
      matCentre: "Main Store",
      narration: `POS (${method})`,
      items: posCart.map((it, i) => ({ sn: i + 1, name: it.name, qty: it.qty, unit: it.unit, price: it.price, amount: it.qty * it.price })),
      subtotal: parseFloat(posSubtotal.textContent.replace("₹", "")),
      grandTotal: posPayableAmount.textContent.replace("₹", "").trim(),
      createdAt: new Date().toISOString()
    };
    saveSalesVoucherRecord(voucherRecord);
    showNotification(`Sale #${vchNum} completed successfully!`);
    posCart = [];
    renderPosCart();
    initFastBillingScreen();
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
searchInput.addEventListener("input", filterCompanies);
chkFinYear.addEventListener("change", renderCompanyTable);
chkTaxNo.addEventListener("change", renderCompanyTable);

btnSelect.addEventListener("click", openLoginModalForSelected);
btnQuit.addEventListener("click", () => {
  if (confirm("Are you sure you want to quit Alpha Billing Software?")) {
    window.close();
  }
});
btnCreateCompanyModal.addEventListener("click", openCreateCompanyModal);

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

// Dashboard Menu Events
menuCloseCompany.addEventListener("click", closeCompany);
menuEditCompany.addEventListener("click", () => {
  if (activeCompany) alert(`Editing details for ${activeCompany.name}`);
});
menuNewCompany.addEventListener("click", openCreateCompanyModal);
menuAddAccountMaster.addEventListener("click", () => showScreen("view-add-account-master"));
menuAddItemMaster.addEventListener("click", () => showScreen("view-add-item-master"));
menuConfigFeatures.addEventListener("click", openConfigurationModal);
menuConfigVoucherSeries.addEventListener("click", openConfigurationModal);
menuSalesAdd.addEventListener("click", () => showScreen("view-sales-voucher"));
menuSalesList.addEventListener("click", () => showScreen("view-sales-list"));
menuDisplayBills.addEventListener("click", () => showScreen("view-sales-list"));

menuChangePassword.addEventListener("click", () => {
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

// Item Master
btnItemSave.addEventListener("click", handleSaveItemMaster);
btnItemQuit.addEventListener("click", () => showScreen("view-dashboard"));
btnItemCloseTop.addEventListener("click", () => showScreen("view-dashboard"));

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
  btnModeLogout.addEventListener("click", () => closeCompany());
}
if (menuSwitchMode) {
  menuSwitchMode.addEventListener("click", () => showScreen("view-mode-selection"));
}
if (barSwitchMode) {
  barSwitchMode.addEventListener("click", () => showScreen("view-mode-selection"));
}

// Fast Billing Header Navigation
if (menuFastBilling) menuFastBilling.addEventListener("click", () => openFastBillingPos());
if (btnPosBackMode) {
  btnPosBackMode.addEventListener("click", () => navigateAwayFromPos("view-mode-selection"));
}
if (btnPosClose) {
  btnPosClose.addEventListener("click", () => navigateAwayFromPos("view-mode-selection"));
}
if (btnPosLogout) {
  btnPosLogout.addEventListener("click", () => {
    if (posCart.length > 0) {
      if (!confirm("You have active items in your POS cart. Exit anyway and discard current cart?")) {
        return;
      }
      posCart = [];
    }
    closeCompany();
  });
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
    const q = prompt("Enter product name, SKU or barcode to search:");
    if (q) handleBarcodeScan(q);
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

if (posBarcodeInput) {
  posBarcodeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleBarcodeScan(posBarcodeInput.value.trim());
      posBarcodeInput.value = "";
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

if (btnPosSearchItem) {
  btnPosSearchItem.addEventListener("click", () => {
    const q = prompt("Enter product name, SKU or barcode to search:");
    if (q) handleBarcodeScan(q);
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
      btnTriggerBackup.textContent = "⚡ Create Local Backup";
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
    if (migrationStatusMsg) migrationStatusMsg.textContent = `✓ Exported data for ${activeCompany.name} to JSON file.`;
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

  // View-specific hotkeys
  if (currentScreen === "view-companies") {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex(selectedIndex + 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex(selectedIndex - 1);
    } else if (e.key === "Enter") {
      e.preventDefault();
      openLoginModalForSelected();
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
      closeCompany();
    }
  } else if (currentScreen === "view-sales-voucher") {
    if (e.key === "F2") {
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
      if (btnPosBarNewSale) btnPosBarNewSale.click();
    } else if (e.key === "F7") {
      e.preventDefault();
      if (btnPosBarReprint) btnPosBarReprint.click();
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
  } else if (currentScreen === "view-add-account-master") {
    if (e.key === "F2") {
      e.preventDefault();
      handleSaveAccountMaster();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-add-item-master") {
    if (e.key === "F2") {
      e.preventDefault();
      handleSaveItemMaster();
    } else if (e.key === "Escape") {
      e.preventDefault();
      showScreen("view-dashboard");
    }
  } else if (currentScreen === "view-sales-list") {
    if (e.key === "Escape") {
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

// Startup
renderCompanyTable();
updateSystemClock();
setInterval(updateSystemClock, 10000);
applyZoom(uiZoom);
showScreen("view-companies");
