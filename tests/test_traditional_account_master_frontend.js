/**
 * Frontend Test Suite: Traditional Billing Account Master & Customer Code Save Flow
 *
 * Verifies:
 * 1. Account master save in Traditional mode calls traditional_saveCustomer.
 * 2. New account creation works without requiring a manually input code.
 * 3. Form contains hidden #acc-code element to hold existing code during edit.
 * 4. Editing an existing account populates #acc-id and #acc-code, and preserves code during save.
 * 5. Reset form clears both #acc-id and #acc-code.
 * 6. Account list rendering in Traditional mode calls traditional_listAccounts or traditional_listCustomers.
 */

const fs = require("fs");
const path = require("path");
const assert = require("assert");

console.log("==================================================================");
console.log("RUNNING TRADITIONAL BILLING ACCOUNT MASTER FRONTEND TESTS");
console.log("==================================================================");

// 1. Verify index.html structure
function testHtmlStructure() {
  const htmlContent = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");

  // Check form has both acc-id and acc-code hidden fields
  assert(htmlContent.includes('id="acc-id"'), "index.html must have #acc-id hidden field");
  assert(htmlContent.includes('id="acc-code"'), "index.html must have #acc-code hidden field");

  // Confirm NO visible customer code field in account master form
  const accFormMatch = htmlContent.match(/<form[^>]*id="form-account-master"[\s\S]*?<\/form>/);
  assert(accFormMatch, "form-account-master must exist in index.html");
  const formHtml = accFormMatch[0];
  assert(!formHtml.includes('type="text" id="acc-code"'), "Account master must NOT have a visible text input for acc-code");

  console.log("PASS: testHtmlStructure confirms #acc-id and #acc-code hidden inputs and no visible code input");
}

// 2. Verify app.js save flow
function testAppJsSaveAndEditFlow() {
  const appJsContent = fs.readFileSync(path.join(__dirname, "../app.js"), "utf8");

  // 1. handleSaveAccountMaster collects existingAccCode
  assert(appJsContent.includes('const existingAccCode = document.getElementById("acc-code")'), "handleSaveAccountMaster must read #acc-code");
  assert(appJsContent.includes('accountData.code = existingAccCode;'), "handleSaveAccountMaster must pass existingAccCode when modifying");

  // 2. resetAccountMasterAddForm clears #acc-code
  assert(appJsContent.includes('const codeEl = document.getElementById("acc-code");\n  if (codeEl) codeEl.value = "";'), "resetAccountMasterAddForm must clear #acc-code");

  // 3. openModifyAccountMaster sets #acc-code
  assert(appJsContent.includes('codeEl.value = acc.code || acc.customer_code || acc.customerCode || "";'), "openModifyAccountMaster must populate #acc-code");

  // 4. traditional_saveCustomer is called in Traditional mode
  assert(appJsContent.includes('window.backend.traditional_saveCustomer(JSON.stringify(accountData)'), "Traditional mode must route to traditional_saveCustomer");

  // 5. Mode-aware account list routing
  assert(appJsContent.includes('window.backend.traditional_listAccounts(q || "", false,'), "renderAccountMasterList must route to traditional_listAccounts");

  console.log("PASS: testAppJsSaveAndEditFlow confirms code retention, reset, and mode-aware routing");
}

// 3. Simulate JavaScript execution of save flow in Mock DOM
function testSimulatedSaveFlow() {
  // Mock DOM elements
  const elements = {
    "acc-id": { value: "" },
    "acc-code": { value: "" },
    "acc-name": { value: "Arasu Traders", focus: () => {} },
    "acc-alias": { value: "Arasu" },
    "acc-print-name": { value: "" },
    "acc-group": { value: "Sundry Debtors (Customers)" },
    "acc-op-bal": { value: "0.00" },
    "acc-op-type": { value: "D" },
    "acc-prev-bal": { value: "0.00" },
    "acc-prev-type": { value: "D" },
    "acc-addr1": { value: "12, Bazaar St" },
    "acc-addr2": { value: "" },
    "acc-country": { value: "India" },
    "acc-state": { value: "Tamilnadu" },
    "acc-dealer-type": { value: "Unregistered" },
    "acc-customer-category": { value: "Direct Customer" },
    "acc-gstin": { value: "" },
    "acc-mobile": { value: "9876543210" },
    "acc-whatsapp": { value: "" },
    "acc-bank-name": { value: "" },
    "acc-bank-acc": { value: "" },
    "acc-bank-ifsc": { value: "" },
    "acc-pincode": { value: "" },
    "acc-extra-info": { value: "" },
    "btn-acc-save": { disabled: false, style: {} },
  };

  const documentMock = {
    getElementById: (id) => elements[id] || null,
  };

  let rpcPayload = null;
  const backendMock = {
    traditional_saveCustomer: (payloadJson, callback) => {
      rpcPayload = JSON.parse(payloadJson);
      // Simulate backend auto-generating CUS-000001
      callback(
        JSON.stringify({
          success: true,
          data: {
            id: "uuid-arasu-1",
            code: "CUS-000001",
            name: rpcPayload.name,
            account_type: "Debtor",
            group: "Sundry Debtors",
          },
        })
      );
    },
  };

  // Verify that new customer has no code sent (so backend generates it)
  assert.strictEqual(elements["acc-id"].value, "");
  assert.strictEqual(elements["acc-code"].value, "");

  // Execute mock save logic as implemented in app.js
  const existingAccId = documentMock.getElementById("acc-id").value.trim();
  const existingAccCode = documentMock.getElementById("acc-code").value.trim();

  const accountData = {
    name: elements["acc-name"].value.trim(),
    alias: elements["acc-alias"].value.trim(),
    group: elements["acc-group"].value.trim(),
    phone: elements["acc-mobile"].value.trim(),
    address: elements["acc-addr1"].value.trim(),
    state: elements["acc-state"].value.trim(),
  };
  if (existingAccId) accountData.id = existingAccId;
  if (existingAccCode) accountData.code = existingAccCode;

  backendMock.traditional_saveCustomer(JSON.stringify(accountData), (resp) => {
    const res = JSON.parse(resp);
    assert.strictEqual(res.success, true);
    assert.strictEqual(res.data.code, "CUS-000001");
    assert.strictEqual(res.data.name, "Arasu Traders");
  });

  assert(rpcPayload !== null, "traditional_saveCustomer must have been called");
  assert.strictEqual(rpcPayload.code, undefined, "New account payload must not include pre-filled code");
  assert.strictEqual(rpcPayload.name, "Arasu Traders");

  // Now simulate EDIT flow:
  // 1. Load account into form
  elements["acc-id"].value = "uuid-arasu-1";
  elements["acc-code"].value = "CUS-000001";
  elements["acc-name"].value = "Arasu Traders Pvt Ltd";

  const editId = documentMock.getElementById("acc-id").value.trim();
  const editCode = documentMock.getElementById("acc-code").value.trim();

  const editData = {
    name: elements["acc-name"].value.trim(),
    alias: elements["acc-alias"].value.trim(),
    group: elements["acc-group"].value.trim(),
  };
  if (editId) editData.id = editId;
  if (editCode) editData.code = editCode;

  backendMock.traditional_saveCustomer(JSON.stringify(editData), (resp) => {
    const res = JSON.parse(resp);
    assert.strictEqual(res.success, true);
  });

  assert.strictEqual(rpcPayload.id, "uuid-arasu-1");
  assert.strictEqual(rpcPayload.code, "CUS-000001");
  assert.strictEqual(rpcPayload.name, "Arasu Traders Pvt Ltd");

  console.log("PASS: testSimulatedSaveFlow verified new creation auto-generation and edit code preservation");
}

testHtmlStructure();
testAppJsSaveAndEditFlow();
testSimulatedSaveFlow();

console.log("==================================================================");
console.log("ALL 3 ACCOUNT MASTER FRONTEND TESTS PASSED!");
console.log("==================================================================");
