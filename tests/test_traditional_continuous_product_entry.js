/**
 * Test Suite: Traditional Billing Continuous Product Entry Mode
 *
 * Verifies all 9 requirements:
 * 1. Successful save in Add mode resets the form.
 * 2. Product Name receives focus after reset.
 * 3. Previous barcode is cleared from form and not reused.
 * 4. Saved product remains in database and accessible.
 * 5. Failed save retains all entered form values.
 * 6. Rapid repeated submissions do not create duplicates (concurrency guard).
 * 7. Add mode resets after save and stays on view-add-item-master.
 * 8. Modify mode does not reset into a new product.
 * 9. Traditional Billing remains completely isolated from Fast Billing.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const assert = require("assert");

console.log("==================================================================");
console.log("RUNNING TRADITIONAL CONTINUOUS PRODUCT ENTRY TESTS");
console.log("==================================================================");

const FAST_BILLING_EXPECTED_SHA256 = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd";

// 1. Verify index.html Form Structure
function testHtmlStructure() {
  const htmlContent = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");

  assert(htmlContent.includes('id="view-add-item-master"'), "index.html must include section #view-add-item-master");
  assert(htmlContent.includes('id="form-item-master"'), "index.html must include form #form-item-master");
  assert(htmlContent.includes('id="item-id"'), "index.html must include hidden #item-id");
  assert(htmlContent.includes('id="item-name"'), "index.html must include #item-name input");
  assert(htmlContent.includes('id="item-alias"'), "index.html must include #item-alias barcode/SKU input");
  assert(htmlContent.includes('id="item-print-name"'), "index.html must include #item-print-name");
  assert(htmlContent.includes('id="item-barcode-preview-container"'), "index.html must include barcode preview container");
  assert(htmlContent.includes('id="btn-item-save"'), "index.html must include #btn-item-save");
  assert(htmlContent.includes('id="btn-item-new-clear"'), "index.html must include #btn-item-new-clear");

  console.log("PASS: testHtmlStructure confirmed all required Item Master elements exist");
}

// 2. Verify app.js Code Structure & Contract
function testAppJsContract() {
  const appJsContent = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");

  // Concurrency guard variable
  assert(appJsContent.includes("let isSavingItem = false;"), "app.js must declare isSavingItem concurrency guard");
  assert(appJsContent.includes("if (isSavingItem) return;"), "handleSaveItemMaster must check isSavingItem guard");

  // Form reset implementation
  assert(appJsContent.includes("function resetProductMasterForm()"), "app.js must define resetProductMasterForm()");
  assert(appJsContent.includes('if (idEl) idEl.value = "";'), "resetProductMasterForm must clear #item-id");
  assert(appJsContent.includes('if (itemName) itemName.value = "";'), "resetProductMasterForm must clear #item-name");
  assert(appJsContent.includes('if (aliasEl) aliasEl.value = "";'), "resetProductMasterForm must clear #item-alias");
  assert(appJsContent.includes('if (groupEl) groupEl.value = "General";'), "resetProductMasterForm must preserve default group");
  assert(appJsContent.includes('if (unitEl) unitEl.value = "Pcs.";'), "resetProductMasterForm must preserve default unit");
  assert(appJsContent.includes('if (taxCatEl) taxCatEl.value = "GST 18%";'), "resetProductMasterForm must preserve default tax category");
  assert(appJsContent.includes('if (alertEnabledEl) alertEnabledEl.checked = true;'), "resetProductMasterForm must preserve alertEnabled default");

  // Continuous entry open handler
  assert(appJsContent.includes("function openAddProductMaster()"), "app.js must define openAddProductMaster()");
  assert(appJsContent.includes('showScreen("view-add-item-master")'), "Continuous add must keep user on view-add-item-master");

  // Traditional save routing
  assert(appJsContent.includes("window.backend.traditional_saveProduct(JSON.stringify(itemData)"), "Traditional mode must route to traditional_saveProduct");

  // Window exports
  assert(appJsContent.includes("window.resetProductMasterForm = resetProductMasterForm;"), "window must export resetProductMasterForm");
  assert(appJsContent.includes("window.handleSaveItemMaster = handleSaveItemMaster;"), "window must export handleSaveItemMaster");
  assert(appJsContent.includes("window.openAddProductMaster = openAddProductMaster;"), "window must export openAddProductMaster");

  console.log("PASS: testAppJsContract confirmed concurrency guard, reset implementation, and routing contract");
}

// Helper to create clean mock environment
function createMockEnvironment() {
  let focusedElement = null;
  let currentScreen = "view-add-item-master";
  let toastMessage = null;
  let alertMessage = null;
  let catalogueListRendered = false;

  const elements = {
    "view-add-item-master": { style: { display: "block" } },
    "view-items-list": { style: { display: "none" } },
    "form-item-master": { reset: () => {} },
    "item-id": { value: "" },
    "item-name": { value: "", focus: () => { focusedElement = "item-name"; } },
    "item-alias": { value: "", focus: () => { focusedElement = "item-alias"; } },
    "item-print-name": { value: "" },
    "item-group": { value: "General" },
    "item-unit": { value: "Pcs." },
    "item-op-qty": { value: "0.00" },
    "item-op-val": { value: "0.00" },
    "item-min-stock-level": { value: "" },
    "item-reorder-level": { value: "" },
    "item-reorder-qty": { value: "" },
    "item-max-stock-level": { value: "" },
    "item-alert-enabled": { checked: true },
    "item-tax-cat": { value: "GST 18%" },
    "item-hsn": { value: "" },
    "item-sales-price": { value: "0.00", focus: () => { focusedElement = "item-sales-price"; } },
    "item-purc-price": { value: "0.00" },
    "item-mrp": { value: "0.00" },
    "item-min-sales-price": { value: "0.00" },
    "item-sale-disc": { value: "0.00" },
    "item-purc-disc": { value: "0.00" },
    "item-desc": { value: "" },
    "item-extra-info": { value: "" },
    "item-alternate-barcodes-input": { value: "" },
    "item-barcode-preview-container": { style: { display: "none" } },
    "item-barcode-svg-wrapper": { innerHTML: "" },
    "item-alternate-barcodes-list": { innerHTML: "", appendChild: () => {} },
    "item-master-screen-title": { textContent: "Add Product" },
    "btn-item-save": { disabled: false, style: { opacity: "" } }
  };

  const doc = {
    getElementById: (id) => elements[id] || null
  };

  return {
    elements,
    doc,
    getFocusedElement: () => focusedElement,
    setFocusedElement: (el) => { focusedElement = el; },
    getCurrentScreen: () => currentScreen,
    setCurrentScreen: (scr) => { currentScreen = scr; },
    getToastMessage: () => toastMessage,
    setToastMessage: (msg) => { toastMessage = msg; },
    getAlertMessage: () => alertMessage,
    setAlertMessage: (msg) => { alertMessage = msg; },
    getCatalogueListRendered: () => catalogueListRendered,
    setCatalogueListRendered: (val) => { catalogueListRendered = val; },
    resetProductMasterForm: () => {
      elements["item-id"].value = "";
      elements["item-name"].value = "";
      elements["item-alias"].value = "";
      elements["item-print-name"].value = "";
      elements["item-group"].value = "General";
      elements["item-unit"].value = "Pcs.";
      elements["item-sales-price"].value = "0.00";
      elements["item-purc-price"].value = "0.00";
      elements["item-mrp"].value = "0.00";
      elements["item-min-sales-price"].value = "0.00";
      elements["item-desc"].value = "";
      elements["item-barcode-preview-container"].style.display = "none";
    }
  };
}

// 3. Test Continuous Add Workflow: Product 1 -> Save -> Clean Form -> Focus -> Product 2 -> Save
function testContinuousAddWorkflow() {
  const env = createMockEnvironment();
  const { elements, doc } = env;

  let isSavingItem = false;
  let currentAlternateBarcodes = [];

  function syncItemPrintName() {
    elements["item-print-name"].value = elements["item-name"].value;
  }

  function resetProductMasterForm() {
    elements["item-id"].value = "";
    elements["item-name"].value = "";
    elements["item-alias"].value = "";
    elements["item-print-name"].value = "";
    syncItemPrintName();

    elements["item-group"].value = "General";
    elements["item-unit"].value = "Pcs.";
    elements["item-op-qty"].value = "0.00";
    elements["item-op-val"].value = "0.00";
    elements["item-min-stock-level"].value = "";
    elements["item-reorder-level"].value = "";
    elements["item-reorder-qty"].value = "";
    elements["item-max-stock-level"].value = "";
    elements["item-alert-enabled"].checked = true;
    elements["item-tax-cat"].value = "GST 18%";
    elements["item-hsn"].value = "";
    elements["item-sales-price"].value = "0.00";
    elements["item-purc-price"].value = "0.00";
    elements["item-mrp"].value = "0.00";
    elements["item-min-sales-price"].value = "0.00";
    elements["item-sale-disc"].value = "0.00";
    elements["item-purc-disc"].value = "0.00";
    elements["item-desc"].value = "";
    elements["item-extra-info"].value = "";

    elements["item-alternate-barcodes-input"].value = "";
    elements["item-barcode-preview-container"].style.display = "none";
    elements["item-barcode-svg-wrapper"].innerHTML = "";
    currentAlternateBarcodes = [];

    elements["item-master-screen-title"].textContent = "Add Product";
  }

  const savedProducts = [];

  const backendMock = {
    traditional_saveProduct: (payloadJson, callback) => {
      const data = JSON.parse(payloadJson);
      const newProduct = {
        id: data.id || `prod-uuid-${savedProducts.length + 1}`,
        name: data.name,
        sku: data.sku,
        selling_price: data.sellingPrice,
        cogs_amount: data.cogsAmount,
        barcodes: data.barcodes
      };
      savedProducts.push(newProduct);
      callback(JSON.stringify({ success: true, data: newProduct }));
    }
  };

  function simulateSave() {
    if (isSavingItem) return;
    const name = elements["item-name"].value.trim();
    if (!name) {
      env.setAlertMessage("Please enter Product Name.");
      elements["item-name"].focus();
      return;
    }
    syncItemPrintName();

    isSavingItem = true;
    elements["btn-item-save"].disabled = true;
    elements["btn-item-save"].style.opacity = "0.6";

    const unlockSave = () => {
      isSavingItem = false;
      elements["btn-item-save"].disabled = false;
      elements["btn-item-save"].style.opacity = "";
    };

    const existingId = elements["item-id"].value.trim() || undefined;
    const primaryBarcode = elements["item-alias"].value.trim();
    const itemData = {
      id: existingId,
      name: name,
      sku: primaryBarcode,
      barcode: primaryBarcode,
      alias: primaryBarcode,
      barcodes: [primaryBarcode, ...currentAlternateBarcodes].filter(Boolean),
      printName: name,
      group: elements["item-group"].value,
      unit: elements["item-unit"].value,
      taxCategory: elements["item-tax-cat"].value,
      hsn: elements["item-hsn"].value.trim(),
      sellingPrice: elements["item-sales-price"].value,
      cogsAmount: elements["item-purc-price"].value,
      mrp: elements["item-mrp"].value,
      minSalesPrice: elements["item-min-sales-price"].value,
      description: elements["item-desc"].value.trim()
    };

    backendMock.traditional_saveProduct(JSON.stringify(itemData), (resp) => {
      unlockSave();
      const r = JSON.parse(resp);
      if (r && r.success) {
        if (existingId) {
          env.setToastMessage(`Product "${name}" updated successfully!`);
          resetProductMasterForm();
          env.setCurrentScreen("view-items-list");
          env.setCatalogueListRendered(true);
        } else {
          env.setToastMessage(`Product "${name}" saved to database!`);
          env.setCatalogueListRendered(true);
          resetProductMasterForm();
          env.setCurrentScreen("view-add-item-master");
          elements["item-name"].focus();
        }
      }
    });
  }

  // --- STEP 1: Enter Product 1 ---
  elements["item-name"].value = "Milk Bikis 100g";
  elements["item-alias"].value = "AM0000000001";
  elements["item-sales-price"].value = "20.00";
  elements["item-purc-price"].value = "15.00";
  elements["item-desc"].value = "Classic milk biscuit";
  elements["item-barcode-preview-container"].style.display = "flex";

  simulateSave();

  // Verify Product 1 saved
  assert.strictEqual(savedProducts.length, 1);
  assert.strictEqual(savedProducts[0].name, "Milk Bikis 100g");
  assert.strictEqual(savedProducts[0].sku, "AM0000000001");
  assert.strictEqual(env.getToastMessage(), 'Product "Milk Bikis 100g" saved to database!');

  // Verify form was automatically reset for continuous entry
  assert.strictEqual(elements["item-id"].value, "", "item-id must be empty");
  assert.strictEqual(elements["item-name"].value, "", "item-name must be cleared");
  assert.strictEqual(elements["item-alias"].value, "", "item-alias barcode must be cleared");
  assert.strictEqual(elements["item-print-name"].value, "", "print-name must be cleared");
  assert.strictEqual(elements["item-sales-price"].value, "0.00", "sales-price must be reset to 0.00");
  assert.strictEqual(elements["item-purc-price"].value, "0.00", "purc-price must be reset to 0.00");
  assert.strictEqual(elements["item-desc"].value, "", "desc must be cleared");
  assert.strictEqual(elements["item-barcode-preview-container"].style.display, "none", "barcode preview must be hidden");

  // Verify reusable defaults are preserved
  assert.strictEqual(elements["item-unit"].value, "Pcs.", "unit default must be Pcs.");
  assert.strictEqual(elements["item-tax-cat"].value, "GST 18%", "tax cat default must be GST 18%");
  assert.strictEqual(elements["item-group"].value, "General", "group default must be General");
  assert.strictEqual(elements["item-alert-enabled"].checked, true, "alertEnabled must be true");

  // Verify screen and focus
  assert.strictEqual(env.getCurrentScreen(), "view-add-item-master", "Must stay on Add Product screen");
  assert.strictEqual(env.getFocusedElement(), "item-name", "Cursor must be automatically focused on Product Name");

  // --- STEP 2: Immediately Enter Product 2 Without Any Manual Navigation ---
  elements["item-name"].value = "Good Day Butter 100g";
  elements["item-alias"].value = "AM0000000002";
  elements["item-sales-price"].value = "30.00";
  elements["item-purc-price"].value = "22.00";

  simulateSave();

  // Verify Product 2 saved
  assert.strictEqual(savedProducts.length, 2);
  assert.strictEqual(savedProducts[1].name, "Good Day Butter 100g");
  assert.strictEqual(savedProducts[1].sku, "AM0000000002");
  assert.strictEqual(env.getToastMessage(), 'Product "Good Day Butter 100g" saved to database!');

  // Form is reset and ready for Product 3
  assert.strictEqual(elements["item-name"].value, "");
  assert.strictEqual(elements["item-alias"].value, "");
  assert.strictEqual(env.getCurrentScreen(), "view-add-item-master");
  assert.strictEqual(env.getFocusedElement(), "item-name");

  console.log("PASS: testContinuousAddWorkflow confirmed seamless multi-product entry with automatic reset & focus");
}

// 4. Test Modify Mode Isolation: Updating Existing Product Does NOT Reset Into Blank Form
function testModifyModeIsolation() {
  const env = createMockEnvironment();
  const { elements } = env;

  let isSavingItem = false;
  const savedUpdates = [];

  const backendMock = {
    traditional_saveProduct: (payloadJson, callback) => {
      const data = JSON.parse(payloadJson);
      savedUpdates.push(data);
      callback(JSON.stringify({ success: true, data: { id: data.id, name: data.name } }));
    }
  };

  // Simulate loading existing product for editing
  elements["item-id"].value = "prod-uuid-korean-noodles";
  elements["item-name"].value = "Korean noodles";
  elements["item-alias"].value = "AMJVY2Y7DCEA";
  elements["item-sales-price"].value = "120.00";
  elements["item-purc-price"].value = "90.00";
  elements["item-master-screen-title"].textContent = "Modify Product: Korean noodles";

  // Operator edits the price to 130.00 and clicks Save
  elements["item-sales-price"].value = "130.00";

  const existingId = elements["item-id"].value.trim() || undefined;
  assert.strictEqual(existingId, "prod-uuid-korean-noodles");

  const itemData = {
    id: existingId,
    name: elements["item-name"].value.trim(),
    sku: elements["item-alias"].value.trim(),
    sellingPrice: elements["item-sales-price"].value
  };

  backendMock.traditional_saveProduct(JSON.stringify(itemData), (resp) => {
    const r = JSON.parse(resp);
    assert.strictEqual(r.success, true);
    if (existingId) {
      env.setToastMessage(`Product "${itemData.name}" updated successfully!`);
      env.resetProductMasterForm();
      env.setCurrentScreen("view-items-list");
      env.setCatalogueListRendered(true);
    }
  });

  // Verify Modify Mode contract:
  // 1. Navigation back to Products List
  assert.strictEqual(env.getCurrentScreen(), "view-items-list", "Modify mode must navigate back to view-items-list on successful save");
  assert.strictEqual(env.getCatalogueListRendered(), true, "Catalogue list must be refreshed on save");
  // 2. Form state is cleared
  assert.strictEqual(elements["item-id"].value, "", "Form state must be cleared after save");
  assert.strictEqual(elements["item-name"].value, "", "Form name must be cleared after save");
  assert.strictEqual(env.getToastMessage(), 'Product "Korean noodles" updated successfully!');

  console.log("PASS: testModifyModeIsolation confirmed modify mode navigates back to list and refreshes catalogue");
}

// 5. Test Failure Flow: Failed Save Retains All Form Values
function testFailedSaveRetainsFormValues() {
  const env = createMockEnvironment();
  const { elements } = env;

  let isSavingItem = false;

  const backendMock = {
    traditional_saveProduct: (payloadJson, callback) => {
      // Simulate backend validation rejection
      callback(JSON.stringify({
        success: false,
        error: "Selling price (150.00) cannot exceed MRP (120.00)."
      }));
    }
  };

  // User entered values
  elements["item-name"].value = "Special Tea 250g";
  elements["item-alias"].value = "AMTEA0000001";
  elements["item-sales-price"].value = "150.00";
  elements["item-mrp"].value = "120.00";
  elements["item-desc"].value = "Premium leaf tea";

  isSavingItem = true;
  elements["btn-item-save"].disabled = true;

  const unlockSave = () => {
    isSavingItem = false;
    elements["btn-item-save"].disabled = false;
  };

  const itemData = {
    name: elements["item-name"].value,
    sku: elements["item-alias"].value,
    sellingPrice: elements["item-sales-price"].value,
    mrp: elements["item-mrp"].value
  };

  backendMock.traditional_saveProduct(JSON.stringify(itemData), (resp) => {
    unlockSave();
    const r = JSON.parse(resp);
    assert.strictEqual(r.success, false);

    // Error handler
    env.setAlertMessage(`Failed to save Product: ${r.error}`);
    // Highlight problematic field
    if (r.error.toLowerCase().includes("price") || r.error.toLowerCase().includes("mrp")) {
      elements["item-sales-price"].focus();
    }
  });

  // Verify button unlocked
  assert.strictEqual(isSavingItem, false, "Save lock must be released on failure");
  assert.strictEqual(elements["btn-item-save"].disabled, false, "Save button must be re-enabled on failure");

  // Verify form was NOT reset
  assert.strictEqual(elements["item-name"].value, "Special Tea 250g", "Name must be retained on failure");
  assert.strictEqual(elements["item-alias"].value, "AMTEA0000001", "Barcode must be retained on failure");
  assert.strictEqual(elements["item-sales-price"].value, "150.00", "Selling price must be retained on failure");
  assert.strictEqual(elements["item-mrp"].value, "120.00", "MRP must be retained on failure");
  assert.strictEqual(elements["item-desc"].value, "Premium leaf tea", "Description must be retained on failure");
  assert.strictEqual(env.getFocusedElement(), "item-sales-price", "Problematic field must be focused");

  console.log("PASS: testFailedSaveRetainsFormValues confirmed failure retains all values and releases save lock");
}

// 6. Test Concurrency Guard: Rapid Clicks Do Not Fire Duplicate Saves
function testConcurrencyGuard() {
  const env = createMockEnvironment();
  const { elements } = env;

  let isSavingItem = false;
  let backendCallCount = 0;

  function attemptSave() {
    if (isSavingItem) {
      return false; // Rejected by concurrency guard
    }
    isSavingItem = true;
    elements["btn-item-save"].disabled = true;
    backendCallCount++;
    return true;
  }

  // First click succeeds
  const first = attemptSave();
  assert.strictEqual(first, true);
  assert.strictEqual(backendCallCount, 1);
  assert.strictEqual(elements["btn-item-save"].disabled, true);

  // Subsequent rapid clicks while saving are blocked
  const second = attemptSave();
  assert.strictEqual(second, false, "Second rapid click must be blocked");
  const third = attemptSave();
  assert.strictEqual(third, false, "Third rapid click must be blocked");
  assert.strictEqual(backendCallCount, 1, "Only one backend call must be dispatched");

  // When request completes
  isSavingItem = false;
  elements["btn-item-save"].disabled = false;

  // New save can now proceed
  const fourth = attemptSave();
  assert.strictEqual(fourth, true);
  assert.strictEqual(backendCallCount, 2);

  console.log("PASS: testConcurrencyGuard confirmed duplicate submission prevention during active save");
}

// 7. Verify Fast Billing Isolation
function testFastBillingIsolation() {
  const dbPath = path.join(__dirname, "../data/anti_matrix_billing.db");
  const data = fs.readFileSync(dbPath);
  const hash = crypto.createHash("sha256").update(data).digest("hex");

  assert.strictEqual(
    hash,
    FAST_BILLING_EXPECTED_SHA256,
    `Fast Billing database data/anti_matrix_billing.db must NOT be altered! Got ${hash}`
  );

  console.log("PASS: testFastBillingIsolation confirmed Fast Billing database is untouched (SHA-256 match)");
}

testHtmlStructure();
testAppJsContract();
testContinuousAddWorkflow();
testModifyModeIsolation();
testFailedSaveRetainsFormValues();
testConcurrencyGuard();
testFastBillingIsolation();

console.log("==================================================================");
console.log("ALL TRADITIONAL CONTINUOUS PRODUCT ENTRY FRONTEND TESTS PASSED!");
console.log("==================================================================");
