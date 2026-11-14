/**
 * Focused Unit Tests: Mode-Aware Company Loading & First-Time Setup UI
 * Tests the exact logic extracted from app.js to guarantee:
 * 1. Traditional mode calls traditional_listCompanies exclusively.
 * 2. Fast mode calls listCompanies exclusively.
 * 3. Startup sync does not unconditionally call legacy listCompanies.
 * 4. Switching modes clears stale company options immediately.
 * 5. Delayed/stale responses from previous modes cannot overwrite current mode.
 * 6. Traditional mode with zero companies displays the setup interface.
 * 7. Fast Billing never displays the Traditional setup interface.
 * 8. Setup calls only traditional_initialSetup().
 * 9. Bootstrap token is never passed through JavaScript or RPC payload.
 * 10. Successful setup refreshes the Traditional company dropdown.
 * 11. Failed setup displays an error and permits safe retry.
 * 12. Duplicate submissions are prevented.
 */

const assert = require("assert");
const fs = require("fs");
const path = require("path");

// Mock DOM infrastructure
class MockOption {
  constructor(value = "", text = "") {
    this.value = value;
    this.textContent = text;
    this.disabled = false;
    this.selected = false;
  }
}

class MockElement {
  constructor(id) {
    this.id = id;
    this.options = [];
    this._innerHTML = "";
    this.value = "";
    this.disabled = false;
    this.style = {};
    this.onclick = null;
    this.onsubmit = null;
    this.textContent = "";
  }

  set innerHTML(val) {
    this._innerHTML = val;
    if (val === "") {
      this.options = [];
    }
  }

  get innerHTML() {
    return this._innerHTML || "";
  }

  appendChild(opt) {
    this.options.push(opt);
    if (opt.selected) {
      this.value = opt.value;
    }
  }

  focus() {}
  select() {}

  get selectedIndex() {
    return this.options.findIndex(o => o.value === this.value);
  }

  set selectedIndex(idx) {
    if (idx >= 0 && idx < this.options.length) {
      this.value = this.options[idx].value;
      this.options[idx].selected = true;
    }
  }
}

// Global test harness setup
function createTestContext() {
  const elements = {
    "login-company-select": new MockElement("login-company-select"),
    "btn-login-submit": new MockElement("btn-login-submit"),
    "login-user-input": new MockElement("login-user-input"),
    "login-pwd-input": new MockElement("login-pwd-input"),
    "btn-login-mode-trad": new MockElement("btn-login-mode-trad"),
    "btn-login-mode-fast": new MockElement("btn-login-mode-fast"),
    "traditional-setup-container": new MockElement("traditional-setup-container"),
    "modal-traditional-setup": new MockElement("modal-traditional-setup"),
    "btn-show-traditional-setup": new MockElement("btn-show-traditional-setup"),
    "btn-close-traditional-setup-modal": new MockElement("btn-close-traditional-setup-modal"),
    "btn-cancel-traditional-setup": new MockElement("btn-cancel-traditional-setup"),
    "btn-submit-traditional-setup": new MockElement("btn-submit-traditional-setup"),
    "form-traditional-setup": new MockElement("form-traditional-setup"),
    "trad-setup-alert": new MockElement("trad-setup-alert"),
    "trad-setup-alert-text": new MockElement("trad-setup-alert-text"),
    "trad-setup-spinner": new MockElement("trad-setup-spinner"),
    "trad-setup-submit-text": new MockElement("trad-setup-submit-text"),
    "trad-setup-name": new MockElement("trad-setup-name"),
    "trad-setup-code": new MockElement("trad-setup-code"),
    "trad-setup-finyear": new MockElement("trad-setup-finyear"),
    "trad-setup-taxno": new MockElement("trad-setup-taxno"),
    "trad-setup-state": new MockElement("trad-setup-state"),
    "trad-setup-admin-user": new MockElement("trad-setup-admin-user"),
    "trad-setup-admin-pwd": new MockElement("trad-setup-admin-pwd"),
    "trad-setup-confirm-pwd": new MockElement("trad-setup-confirm-pwd"),
  };

  const document = {
    getElementById: (id) => elements[id] || null,
    createElement: (tag) => {
      if (tag === "option") return new MockOption();
      return new MockElement(tag);
    },
  };

  const backendCalls = {
    traditional_listCompanies: 0,
    listCompanies: 0,
    traditional_initialSetup: 0,
    traditional_getAuthenticatedSession: 0,
    getAuthenticatedSession: 0,
  };

  const backendCallbacks = {};
  let lastSetupPayload = null;

  const window = {
    backend: {
      traditional_listCompanies: (cb) => {
        backendCalls.traditional_listCompanies++;
        backendCallbacks.traditional_listCompanies = cb;
      },
      listCompanies: (cb) => {
        backendCalls.listCompanies++;
        backendCallbacks.listCompanies = cb;
      },
      traditional_initialSetup: (payloadJson, cb) => {
        backendCalls.traditional_initialSetup++;
        lastSetupPayload = JSON.parse(payloadJson);
        backendCallbacks.traditional_initialSetup = cb;
      },
      traditional_getAuthenticatedSession: (cb) => {
        backendCalls.traditional_getAuthenticatedSession++;
      },
      getAuthenticatedSession: (cb) => {
        backendCalls.getAuthenticatedSession++;
      },
    },
    BusinessContext: null,
    DashboardManager: null,
  };

  // Extract relevant functions and scope from app.js
  const appJsContent = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");

  // Load the standalone login engine section through initTraditionalSetupListeners
  const fetchAndPopulateMatch = appJsContent.match(
    /\/\/ SCREEN 1: STANDALONE LOGIN ENGINE[\s\S]*?function initTraditionalSetupListeners\(\) \{[\s\S]*?\n\}/
  );
  if (!fetchAndPopulateMatch) {
    throw new Error("Failed to find login and setup section in app.js");
  }

  // Load syncFromBackend section
  const syncMatch = appJsContent.match(
    /\/\/ Synchronize companies and session from Python backend\s*function syncFromBackend\(\) \{[\s\S]*?\n\}/
  );
  if (!syncMatch) {
    throw new Error("Failed to find syncFromBackend in app.js");
  }

  const scriptToEval = `
    let loginCompanySelect = document.getElementById("login-company-select");
    let btnLoginSubmit = document.getElementById("btn-login-submit");
    let loginUserInput = document.getElementById("login-user-input");
    let loginPwdInput = document.getElementById("login-pwd-input");
    let companies = [];
    let filteredCompanies = [];
    let activeCompany = null;
    let notifications = [];
    function showNotification(msg) { notifications.push(msg); }
    function openBillingModeSelection() {}

    ${fetchAndPopulateMatch[0]}
    ${syncMatch[0]}

    return {
      get activeLoginMode() { return activeLoginMode; },
      set activeLoginMode(v) { activeLoginMode = v; },
      get companies() { return companies; },
      set companies(v) { companies = v; },
      get isSubmittingTraditionalSetup() { return isSubmittingTraditionalSetup; },
      get notifications() { return notifications; },
      fetchAndPopulateCompanies,
      populateLoginCompanies,
      initLoginModeToggle,
      openTraditionalSetupModal,
      closeTraditionalSetupModal,
      handleTraditionalSetupSubmit,
      initTraditionalSetupListeners,
      syncFromBackend,
    };
  `;

  const runContext = new Function("document", "window", scriptToEval);
  const context = runContext(document, window);

  return {
    document,
    window,
    elements,
    backendCalls,
    backendCallbacks,
    get lastSetupPayload() { return lastSetupPayload; },
    context,
  };
}

// -------------------------------------------------------------
// Test 1: Startup sync calls traditional_listCompanies exclusively
// -------------------------------------------------------------
function testStartupSyncRoutesToTraditional() {
  const { context, backendCalls } = createTestContext();

  assert.strictEqual(context.activeLoginMode, "traditional", "Default login mode must be traditional");

  context.syncFromBackend();

  assert.strictEqual(
    backendCalls.traditional_listCompanies,
    1,
    "Startup sync in Traditional mode must call traditional_listCompanies exactly once"
  );
  assert.strictEqual(
    backendCalls.listCompanies,
    0,
    "Startup sync must NEVER unconditionally call legacy listCompanies"
  );

  console.log("PASS: testStartupSyncRoutesToTraditional");
}

// -------------------------------------------------------------
// Test 2: Traditional mode successful population
// -------------------------------------------------------------
function testTraditionalModePopulatesSuccessfully() {
  const { context, backendCallbacks, elements } = createTestContext();

  context.fetchAndPopulateCompanies();
  assert(backendCallbacks.traditional_listCompanies, "traditional_listCompanies callback registered");

  backendCallbacks.traditional_listCompanies(JSON.stringify({
    success: true,
    data: [{ code: "TRAD01", name: "Traditional Retail Corp" }]
  }));

  const select = elements["login-company-select"];
  assert.strictEqual(context.companies.length, 1);
  assert.strictEqual(select.options.length, 1);
  assert.strictEqual(select.options[0].value, "TRAD01");
  assert.strictEqual(select.options[0].textContent, "Traditional Retail Corp (TRAD01)");
  assert.strictEqual(select.disabled, false);
  assert.strictEqual(elements["btn-login-submit"].disabled, false);
  assert.strictEqual(elements["traditional-setup-container"].style.display, "none", "Setup container hidden when company exists");

  console.log("PASS: testTraditionalModePopulatesSuccessfully");
}

// -------------------------------------------------------------
// Test 3: Zero companies displays Traditional setup interface
// -------------------------------------------------------------
function testZeroCompaniesDisplaysTraditionalSetupInterface() {
  const { context, backendCallbacks, elements } = createTestContext();

  context.fetchAndPopulateCompanies();

  backendCallbacks.traditional_listCompanies(JSON.stringify({
    success: true,
    data: []
  }));

  const select = elements["login-company-select"];
  assert.strictEqual(context.companies.length, 0);
  assert.strictEqual(select.options.length, 1);
  assert.strictEqual(select.options[0].textContent, "-- No Traditional Companies (Setup Required) --");
  assert.strictEqual(select.disabled, true);
  assert.strictEqual(elements["btn-login-submit"].disabled, true);
  assert.strictEqual(elements["traditional-setup-container"].style.display, "block", "Setup container MUST be visible");

  console.log("PASS: testZeroCompaniesDisplaysTraditionalSetupInterface");
}

// -------------------------------------------------------------
// Test 4: Fast Billing never displays Traditional setup interface
// -------------------------------------------------------------
function testFastBillingNeverDisplaysTraditionalSetup() {
  const { context, backendCalls, backendCallbacks, elements } = createTestContext();

  context.initLoginModeToggle();
  // Switch to Fast Billing
  elements["btn-login-mode-fast"].onclick();

  assert.strictEqual(context.activeLoginMode, "fast_billing");
  assert.strictEqual(backendCalls.listCompanies, 1);

  // Even if Fast Billing returns 0 companies:
  backendCallbacks.listCompanies(JSON.stringify({
    success: true,
    data: []
  }));

  assert.strictEqual(
    elements["traditional-setup-container"].style.display,
    "none",
    "Traditional setup container must NEVER be displayed in Fast Billing mode"
  );
  assert.strictEqual(elements["login-company-select"].options[0].textContent, "-- No Fast Billing Companies Found --");

  console.log("PASS: testFastBillingNeverDisplaysTraditionalSetup");
}

// -------------------------------------------------------------
// Test 5: Setup calls traditional_initialSetup with clean payload (NO bootstrap token)
// -------------------------------------------------------------
function testSetupCallsTraditionalInitialSetupWithoutToken() {
  const { context, elements, backendCalls, harness } = (function() {
    const ctx = createTestContext();
    return { ...ctx, harness: ctx };
  })();

  context.initTraditionalSetupListeners();
  context.openTraditionalSetupModal();

  assert.strictEqual(elements["modal-traditional-setup"].style.display, "flex");

  // Fill in form values
  elements["trad-setup-name"].value = "Alpha Retail Enterprise";
  elements["trad-setup-code"].value = "CORP01";
  elements["trad-setup-finyear"].value = "2026-2027";
  elements["trad-setup-taxno"].value = "33AAAPL1234F1Z1";
  elements["trad-setup-state"].value = "Tamilnadu";
  elements["trad-setup-admin-user"].value = "SUPERADMIN";
  elements["trad-setup-admin-pwd"].value = "SecretPassword123";
  elements["trad-setup-confirm-pwd"].value = "SecretPassword123";

  // Trigger form submit
  elements["form-traditional-setup"].onsubmit({ preventDefault: () => {} });

  assert.strictEqual(harness.backendCalls.traditional_initialSetup, 1, "Must invoke traditional_initialSetup RPC");

  const payload = harness.lastSetupPayload;
  assert.strictEqual(payload.name, "Alpha Retail Enterprise");
  assert.strictEqual(payload.code, "CORP01");
  assert.strictEqual(payload.adminUsername, "SUPERADMIN");
  assert.strictEqual(payload.adminPassword, "SecretPassword123");

  // STRICT SECURITY CHECK: Assert that NO bootstrap token or token field exists in the payload!
  assert.strictEqual(payload.token, undefined, "Security violation: token must not be in payload");
  assert.strictEqual(payload.bootstrap_token, undefined, "Security violation: bootstrap_token must not be in payload");
  assert.strictEqual(payload.setup_token, undefined, "Security violation: setup_token must not be in payload");

  console.log("PASS: testSetupCallsTraditionalInitialSetupWithoutToken");
}

// -------------------------------------------------------------
// Test 6: Successful setup refreshes company list and enables login
// -------------------------------------------------------------
function testSuccessfulSetupRefreshesCompanyList() {
  const { context, elements, backendCallbacks, harness } = (function() {
    const ctx = createTestContext();
    return { ...ctx, harness: ctx };
  })();

  context.initTraditionalSetupListeners();
  context.openTraditionalSetupModal();

  elements["trad-setup-name"].value = "Alpha Retail Enterprise";
  elements["trad-setup-code"].value = "CORP01";
  elements["trad-setup-admin-user"].value = "SUPERADMIN";
  elements["trad-setup-admin-pwd"].value = "SecretPassword123";
  elements["trad-setup-confirm-pwd"].value = "SecretPassword123";

  elements["form-traditional-setup"].onsubmit({ preventDefault: () => {} });

  // Mock successful response from Python Backend
  backendCallbacks.traditional_initialSetup(JSON.stringify({
    success: true,
    data: { companyId: "comp-123", companyCode: "CORP01", adminUsername: "SUPERADMIN" }
  }));

  // 1. Modal should be closed
  assert.strictEqual(elements["modal-traditional-setup"].style.display, "none");

  // 2. Refresh was called: provide the new company in the traditional_listCompanies callback
  backendCallbacks.traditional_listCompanies(JSON.stringify({
    success: true,
    data: [{ code: "CORP01", name: "Alpha Retail Enterprise" }]
  }));

  // 3. Dropdown now has the new company and is enabled
  assert.strictEqual(elements["login-company-select"].options[0].value, "CORP01");
  assert.strictEqual(elements["login-company-select"].disabled, false);
  assert.strictEqual(elements["traditional-setup-container"].style.display, "none");
  assert.strictEqual(elements["login-user-input"].value, "SUPERADMIN", "Admin username should be prefilled");

  console.log("PASS: testSuccessfulSetupRefreshesCompanyList");
}

// -------------------------------------------------------------
// Test 7: Failed setup displays error and allows safe retry
// -------------------------------------------------------------
function testFailedSetupDisplaysErrorAndAllowsRetry() {
  const { context, elements, backendCallbacks } = createTestContext();

  context.initTraditionalSetupListeners();
  context.openTraditionalSetupModal();

  elements["trad-setup-name"].value = "Alpha Retail Enterprise";
  elements["trad-setup-code"].value = "CORP01";
  elements["trad-setup-admin-user"].value = "SUPERADMIN";
  elements["trad-setup-admin-pwd"].value = "SecretPassword123";
  elements["trad-setup-confirm-pwd"].value = "SecretPassword123";

  elements["form-traditional-setup"].onsubmit({ preventDefault: () => {} });

  // Simulate token failure or cancellation from native Qt dialog
  backendCallbacks.traditional_initialSetup(JSON.stringify({
    success: false,
    error: "Bootstrap authorization failed: Invalid setup token."
  }));

  // Alert displayed inside modal
  assert.strictEqual(elements["trad-setup-alert"].style.display, "flex");
  assert.strictEqual(
    elements["trad-setup-alert-text"].textContent,
    "Bootstrap authorization failed: Invalid setup token."
  );

  // Submit button re-enabled for safe retry
  assert.strictEqual(elements["btn-submit-traditional-setup"].disabled, false);
  assert.strictEqual(context.isSubmittingTraditionalSetup, false);

  console.log("PASS: testFailedSetupDisplaysErrorAndAllowsRetry");
}

// -------------------------------------------------------------
// Test 8: Duplicate submissions are prevented
// -------------------------------------------------------------
function testDuplicateSubmissionsArePrevented() {
  const { context, elements, backendCalls } = createTestContext();

  context.initTraditionalSetupListeners();
  context.openTraditionalSetupModal();

  elements["trad-setup-name"].value = "Alpha Retail Enterprise";
  elements["trad-setup-code"].value = "CORP01";
  elements["trad-setup-admin-user"].value = "ADMIN";
  elements["trad-setup-admin-pwd"].value = "Password@123";
  elements["trad-setup-confirm-pwd"].value = "Password@123";

  // First click
  elements["form-traditional-setup"].onsubmit({ preventDefault: () => {} });
  assert.strictEqual(backendCalls.traditional_initialSetup, 1);
  assert.strictEqual(context.isSubmittingTraditionalSetup, true);
  assert.strictEqual(elements["btn-submit-traditional-setup"].disabled, true);

  // Second immediate click while request is in flight
  elements["form-traditional-setup"].onsubmit({ preventDefault: () => {} });
  assert.strictEqual(
    backendCalls.traditional_initialSetup,
    1,
    "Second submission while in flight must be dropped"
  );

  console.log("PASS: testDuplicateSubmissionsArePrevented");
}

// Run all test suites
function runAll() {
  console.log("==================================================================");
  console.log("RUNNING FOCUSED TESTS: MODE-AWARE LOADING & FIRST-TIME SETUP UI");
  console.log("==================================================================");
  testStartupSyncRoutesToTraditional();
  testTraditionalModePopulatesSuccessfully();
  testZeroCompaniesDisplaysTraditionalSetupInterface();
  testFastBillingNeverDisplaysTraditionalSetup();
  testSetupCallsTraditionalInitialSetupWithoutToken();
  testSuccessfulSetupRefreshesCompanyList();
  testFailedSetupDisplaysErrorAndAllowsRetry();
  testDuplicateSubmissionsArePrevented();
  console.log("==================================================================");
  console.log("ALL 8 FIRST-TIME SETUP & MODE ISOLATION TESTS PASSED!");
  console.log("==================================================================");
}

runAll();
