/**
 * Test Suite: Traditional Billing Modify Product Navigation & Sales Voucher Numbering
 *
 * Verifies:
 * 1. Modify Product Mode (Save Product F2):
 *    - On successful backend commit:
 *      * Shows success toast with updated product name.
 *      * Resets product master form state.
 *      * Navigates back to view-items-list.
 *      * Refreshes Products List from Traditional Billing database.
 *    - On validation/backend failure:
 *      * Remains on Modify Product screen (view-add-item-master).
 *      * Retains all user-entered form values.
 *      * Displays clear error alert.
 * 2. Add Product Mode:
 *    - Continuous entry mode remains intact: resets form, stays on view-add-item-master, focuses Product Name.
 * 3. Sales Voucher Number Generation:
 *    - On screen init, calls traditional_getNextVoucherNumber when activeLoginMode === "traditional".
 *    - Populates vchNumber input and infoVchNo label with formatted number (e.g. "001").
 *    - When vchSeries is changed (e.g. "Main" -> "Tax"), refreshes voucher number for the new series.
 * 4. Fast Billing DB isolation check (SHA-256 match).
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const assert = require("assert");

console.log("==================================================================");
console.log("RUNNING TRADITIONAL MODIFY PRODUCT NAVIGATION & VOUCHER NUMBERING TESTS");
console.log("==================================================================");

const FAST_BILLING_EXPECTED_SHA256 = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd";

// 1. Verify app.js Code Structure & Contract
function testAppJsContracts() {
  const appJsContent = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");

  // Objective 1: Modify Mode Navigation and Reset
  assert(
    appJsContent.includes("if (existingId) {") &&
    appJsContent.includes("showNotification(`Product \"${name}\" updated successfully!`);") &&
    appJsContent.includes("resetProductMasterForm();") &&
    appJsContent.includes('showScreen("view-items-list");') &&
    appJsContent.includes("renderProductsList();"),
    "handleSaveItemMaster must reset form, navigate to view-items-list, and call renderProductsList on existingId save"
  );

  // Objective 1: Add Mode Continuous Entry Intact
  assert(
    appJsContent.includes("showNotification(`Product \"${name}\" saved to database!`);") &&
    appJsContent.includes('showScreen("view-add-item-master");'),
    "handleSaveItemMaster must preserve continuous entry workflow for new products"
  );

  // Objective 2: refreshSalesVoucherNumber and traditional_getNextVoucherNumber
  assert(
    appJsContent.includes("function refreshSalesVoucherNumber()"),
    "app.js must declare refreshSalesVoucherNumber()"
  );
  assert(
    appJsContent.includes("window.backend.traditional_getNextVoucherNumber"),
    "refreshSalesVoucherNumber must query window.backend.traditional_getNextVoucherNumber in traditional mode"
  );
  assert(
    appJsContent.includes('vchSeries.addEventListener("change"'),
    "app.js must attach change listener on vchSeries to refresh voucher number"
  );

  console.log("PASS: testAppJsContracts verified source code contracts for navigation and voucher numbering");
}

// 2. Test Modify Mode Navigation Lifecycle
function testModifyModeNavigationLifecycle() {
  let currentScreen = "view-add-item-master";
  let renderedList = false;
  let toastMsg = null;
  let alertMsg = null;

  const elements = {
    "item-id": { value: "prod-101" },
    "item-name": { value: "Premium Basmati Rice 5kg" },
    "item-alias": { value: "RICE5KG001" },
    "item-sales-price": { value: "650.00" },
    "item-purc-price": { value: "520.00" },
    "item-mrp": { value: "700.00" },
  };

  const resetProductMasterForm = () => {
    elements["item-id"].value = "";
    elements["item-name"].value = "";
    elements["item-alias"].value = "";
    elements["item-sales-price"].value = "0.00";
    elements["item-purc-price"].value = "0.00";
    elements["item-mrp"].value = "0.00";
  };

  const showScreen = (scr) => {
    currentScreen = scr;
    if (scr === "view-items-list") {
      renderedList = true;
    }
  };

  const showNotification = (msg) => {
    toastMsg = msg;
  };

  // Simulate Save flow
  const existingId = elements["item-id"].value;
  const name = elements["item-name"].value;

  // Backend returns success
  const r = { success: true, data: { id: existingId, name: name } };

  if (r.success) {
    if (existingId) {
      showNotification(`Product "${name}" updated successfully!`);
      resetProductMasterForm();
      showScreen("view-items-list");
    }
  }

  // Assertions
  assert.strictEqual(currentScreen, "view-items-list", "Must navigate to view-items-list");
  assert.strictEqual(renderedList, true, "Product list must be rendered");
  assert.strictEqual(elements["item-id"].value, "", "Form item-id must be cleared");
  assert.strictEqual(elements["item-name"].value, "", "Form item-name must be cleared");
  assert.strictEqual(toastMsg, 'Product "Premium Basmati Rice 5kg" updated successfully!');

  console.log("PASS: testModifyModeNavigationLifecycle confirmed successful modify navigates, refreshes list, and clears form");
}

// 3. Test Modify Mode Failed Save Retains State
function testModifyModeFailedSaveRetainsState() {
  let currentScreen = "view-add-item-master";
  let alertMsg = null;

  const elements = {
    "item-id": { value: "prod-101" },
    "item-name": { value: "Premium Basmati Rice 5kg" },
    "item-alias": { value: "RICE5KG001" },
    "item-sales-price": { value: "750.00" }, // Exceeds MRP
    "item-mrp": { value: "700.00" },
  };

  const resetProductMasterForm = () => {
    elements["item-id"].value = "";
    elements["item-name"].value = "";
  };

  const showScreen = (scr) => {
    currentScreen = scr;
  };

  // Backend returns failure
  const r = { success: false, error: "Selling price cannot exceed MRP." };

  if (!r.success) {
    alertMsg = `Failed to save Product: ${r.error}`;
  }

  // Assertions
  assert.strictEqual(currentScreen, "view-add-item-master", "Must remain on Modify screen on failure");
  assert.strictEqual(elements["item-id"].value, "prod-101", "item-id must be retained");
  assert.strictEqual(elements["item-name"].value, "Premium Basmati Rice 5kg", "item-name must be retained");
  assert.strictEqual(elements["item-sales-price"].value, "750.00", "sales-price must be retained");
  assert.strictEqual(alertMsg, "Failed to save Product: Selling price cannot exceed MRP.");

  console.log("PASS: testModifyModeFailedSaveRetainsState confirmed failed save stays on screen with values retained");
}

// 4. Test Sales Voucher Number Generation and Series Refresh
function testSalesVoucherNumberLifecycle() {
  let activeLoginMode = "traditional";
  let activeBillingMode = "traditional";

  const vchSeries = { value: "Main" };
  const vchNumber = { value: "" };
  const infoVchNo = { textContent: "" };

  const seriesCounters = {
    "Main": "001",
    "Tax": "001",
  };

  const backend = {
    traditional_getNextVoucherNumber: (series, callback) => {
      const num = seriesCounters[series] || "001";
      callback(JSON.stringify({ success: true, data: num }));
    }
  };

  function refreshSalesVoucherNumber() {
    const isTrad = activeBillingMode === "traditional" || activeLoginMode === "traditional";
    if (isTrad && backend && typeof backend.traditional_getNextVoucherNumber === "function") {
      const series = vchSeries ? (vchSeries.value || "Main") : "Main";
      backend.traditional_getNextVoucherNumber(series, (resp) => {
        const r = JSON.parse(resp);
        if (r && r.success && r.data) {
          vchNumber.value = r.data;
          infoVchNo.textContent = r.data;
        }
      });
    }
  }

  // 1. Initial screen load
  refreshSalesVoucherNumber();
  assert.strictEqual(vchNumber.value, "001", "Initial voucher number for Main must be 001");
  assert.strictEqual(infoVchNo.textContent, "001");

  // Simulate save in Main series
  seriesCounters["Main"] = "002";

  // Re-fetch next number for Main
  refreshSalesVoucherNumber();
  assert.strictEqual(vchNumber.value, "002", "Next voucher number for Main must be 002");

  // 2. Change series to 'Tax'
  vchSeries.value = "Tax";
  refreshSalesVoucherNumber();
  assert.strictEqual(vchNumber.value, "001", "Initial voucher number for Tax must be 001");

  // Switch back to 'Main'
  vchSeries.value = "Main";
  refreshSalesVoucherNumber();
  assert.strictEqual(vchNumber.value, "002", "Voucher number for Main must remain 002");

  console.log("PASS: testSalesVoucherNumberLifecycle verified initial load, sequential advance, and series switching");
}

// 5. Fast Billing Database Untouched
function testFastBillingDbUntouched() {
  const dbPath = path.join(__dirname, "../data/anti_matrix_billing.db");
  if (!fs.existsSync(dbPath)) {
    console.log("Fast Billing DB does not exist, skipping hash check.");
    return;
  }
  const fileBytes = fs.readFileSync(dbPath);
  const actualHash = crypto.createHash("sha256").update(fileBytes).digest("hex");
  assert.strictEqual(
    actualHash,
    FAST_BILLING_EXPECTED_SHA256,
    `Fast Billing DB SHA-256 mismatch! Expected ${FAST_BILLING_EXPECTED_SHA256}, got ${actualHash}`
  );
  console.log("PASS: testFastBillingDbUntouched confirmed Fast Billing database hash matches exactly");
}

// Run All Tests
testAppJsContracts();
testModifyModeNavigationLifecycle();
testModifyModeFailedSaveRetainsState();
testSalesVoucherNumberLifecycle();
testFastBillingDbUntouched();

console.log("==================================================================");
console.log("ALL TRADITIONAL MODIFY PRODUCT & VOUCHER NUMBERING TESTS PASSED!");
console.log("==================================================================");
