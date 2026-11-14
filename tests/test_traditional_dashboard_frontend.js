/**
 * Automated Test Suite: Traditional Billing Dashboard Frontend (Zero Mock / Real Data Only)
 * Proves that:
 * 1. Empty backend responses render clean zero/unavailable states.
 * 2. Authenticated user and BR01 branch render without "Awaiting Authentication" inconsistency.
 * 3. RPC failures do not fall back to demo/mock data.
 * 4. No mock numbers (48250, 482600, 62400, 38900, 3450, 32.4%) exist in the DOM.
 */

const fs = require('fs');
const path = require('path');
const assert = require('assert');

// Simple DOM Mock
class MockElement {
  constructor(id, tag = 'div') {
    this.id = id;
    this.tagName = tag.toUpperCase();
    this.children = [];
    this._textContent = '';
    this._innerHTML = '';
    this.className = '';
    this.style = {};
    this.classList = {
      classes: new Set(),
      add: (c) => this.classList.classes.add(c),
      remove: (c) => this.classList.classes.delete(c),
      contains: (c) => this.classList.classes.has(c),
      toggle: (c, val) => val ? this.classList.classes.add(c) : this.classList.classes.delete(c)
    };
    this.listeners = {};
  }

  get textContent() {
    return this._textContent;
  }
  set textContent(val) {
    this._textContent = String(val);
    this._innerHTML = String(val);
  }

  get innerHTML() {
    return this._innerHTML;
  }
  set innerHTML(val) {
    this._innerHTML = String(val);
    this._textContent = String(val).replace(/<[^>]*>?/gm, '');
  }

  hasChildNodes() {
    return this.children.length > 0 || this._innerHTML.length > 0;
  }

  addEventListener(event, handler) {
    if (!this.listeners[event]) this.listeners[event] = [];
    this.listeners[event].push(handler);
  }

  click() {
    if (this.listeners['click']) {
      this.listeners['click'].forEach(fn => fn({ preventDefault: () => {} }));
    }
  }

  querySelector(selector) {
    return new MockElement('mock-sub');
  }

  querySelectorAll(selector) {
    return [];
  }
}

class MockDocument {
  constructor() {
    this.elements = new Map();
  }

  getElementById(id) {
    if (!this.elements.has(id)) {
      this.elements.set(id, new MockElement(id));
    }
    return this.elements.get(id);
  }

  querySelectorAll(selector) {
    return [];
  }

  createElement(tag) {
    return new MockElement('dynamic-' + Math.random(), tag);
  }
}

// Setup environment
const mockDoc = new MockDocument();
global.document = mockDoc;
global.window = {
  document: mockDoc,
  BusinessContext: null,
  backend: null,
  getLucideIcon: (name, cls, sz) => `<svg data-icon="${name}"></svg>`
};

// Load dashboard.js
const dashboardCode = fs.readFileSync(path.join(__dirname, '../js/dashboard.js'), 'utf8');
eval(dashboardCode);

const dm = global.window.DashboardManager;

console.log("==================================================================");
console.log("RUNNING TRADITIONAL DASHBOARD FRONTEND REAL-DATA TESTS");
console.log("==================================================================");

// TEST 1: Unauthenticated clear state
function testClearDashboard() {
  dm.clearDashboard();

  assert.strictEqual(mockDoc.getElementById("welcome-greeting-heading").textContent, "");
  assert.strictEqual(mockDoc.getElementById("welcome-ctx-company").textContent, "--");
  assert.strictEqual(mockDoc.getElementById("welcome-ctx-branch").textContent, "--");
  assert.ok(mockDoc.getElementById("business-data-mode-badge").innerHTML.includes("Awaiting Authentication"));

  assert.strictEqual(mockDoc.getElementById("dash-today-sales").textContent, "--");
  assert.strictEqual(mockDoc.getElementById("dash-today-purchases").textContent, "--");
  assert.strictEqual(mockDoc.getElementById("dash-total-stock-value").textContent, "--");
  assert.strictEqual(mockDoc.getElementById("dash-receivables").textContent, "Not available");
  assert.strictEqual(mockDoc.getElementById("dash-payables").textContent, "Not available");
  assert.strictEqual(mockDoc.getElementById("dash-gross-margin").textContent, "Gross Margin: Not available");

  console.log("PASS: testClearDashboard produces clean unauthenticated placeholders");
}

// TEST 2: Welcome banner resolves inconsistency
function testRenderWelcomeResolvesInconsistency() {
  global.window.BusinessContext = {
    isAuthenticatedSession: () => true,
    getActiveCompany: () => ({ id: 'c-1', code: 'COMP_ISO_2', name: 'Alpha Traditional Corp' }),
    getActiveBranch: () => ({ id: 'b-1', code: 'BR01', name: 'Main Branch' }),
    getCurrentUser: () => ({ id: 'u-1', username: 'ADMIN', displayName: 'System Administrator', role: 'Administrator' })
  };

  dm.renderWelcome();

  const heading = mockDoc.getElementById("welcome-greeting-heading").textContent;
  assert.ok(heading.includes("System Administrator"), "Greeting must show actual user display name");

  const badge = mockDoc.getElementById("business-data-mode-badge").innerHTML;
  assert.ok(!badge.includes("Awaiting Authentication"), "Badge MUST NOT say Awaiting Authentication when user is authenticated!");
  assert.ok(badge.includes("Traditional Billing (COMP_ISO_2 - BR01)"), "Badge must display authentic tenant code and BR01 branch");

  console.log("PASS: testRenderWelcomeResolvesInconsistency correctly eliminates 'Awaiting Authentication' conflict");
}

// TEST 3: Genuine empty database metrics rendering
function testRenderEmptyMetrics() {
  const emptyMetrics = {
    todaySales: 0.00,
    todaySalesDisplay: "₹ 0.00",
    todaySalesCount: 0,
    todaySalesDelta: "",
    todayPurchases: 0.00,
    todayPurchasesDisplay: "₹ 0.00",
    todayPurchasesCount: 0,
    todayPurchasesDelta: "",
    stockValue: 0.00,
    stockValueDisplay: "₹ 0.00",
    stockItemsCount: 0,
    lowStockCount: 0,
    receivables: null,
    receivablesDisplay: "Not available",
    receivablesOverdueCount: null,
    receivablesOverdueDisplay: "N/A",
    payables: null,
    payablesDisplay: "Not available",
    payablesDueCount: null,
    payablesDueDisplay: "N/A",
    todayExpenses: 0.00,
    todayExpensesDisplay: "₹ 0.00",
    heldBills: 0,
    grossMargin: null,
    grossMarginDisplay: "Not available",
    salesTrend: [],
    paymentSummary: [],
    revenueExpense: [],
    recentInvoices: [],
    recentPurchases: [],
    recentPayments: [],
    stockAdjustments: []
  };

  dm.dashboardData = emptyMetrics;
  dm.renderKPIs();
  dm.renderCharts();
  dm.renderActivities();

  assert.strictEqual(mockDoc.getElementById("dash-today-sales").textContent, "₹ 0.00");
  assert.strictEqual(mockDoc.getElementById("dash-sales-count").textContent, "0 Invoices");
  assert.strictEqual(mockDoc.getElementById("dash-today-purchases").textContent, "₹ 0.00");
  assert.strictEqual(mockDoc.getElementById("dash-purchases-count").textContent, "0 Bills");
  assert.strictEqual(mockDoc.getElementById("dash-total-stock-value").textContent, "₹ 0.00");
  assert.strictEqual(mockDoc.getElementById("dash-stock-count").textContent, "0 Active SKUs");
  assert.strictEqual(mockDoc.getElementById("dash-low-stock").textContent, "0 items low");

  assert.strictEqual(mockDoc.getElementById("dash-receivables").textContent, "Not available");
  assert.strictEqual(mockDoc.getElementById("dash-receivables-count").textContent, "N/A");
  assert.strictEqual(mockDoc.getElementById("dash-payables").textContent, "Not available");
  assert.strictEqual(mockDoc.getElementById("dash-payables-count").textContent, "N/A");

  assert.strictEqual(mockDoc.getElementById("dash-today-expenses").textContent, "₹ 0.00");
  assert.strictEqual(mockDoc.getElementById("dash-held-bills").textContent, "0 held bills");
  assert.strictEqual(mockDoc.getElementById("dash-gross-margin").textContent, "Gross Margin: Not available");

  // Verify chart empty states
  assert.ok(mockDoc.getElementById("chart-sales-trend-container").innerHTML.includes("No sales or procurement data yet"));
  assert.ok(mockDoc.getElementById("chart-payment-summary-container").innerHTML.includes("No payment data yet"));
  assert.ok(mockDoc.getElementById("chart-revenue-expense-container").innerHTML.includes("No financial comparison data yet"));

  // Verify activity tables empty states
  assert.ok(mockDoc.getElementById("dash-recent-sales-tbody").innerHTML.includes("No sales invoices recorded yet"));
  assert.ok(mockDoc.getElementById("dash-recent-purchases-tbody").innerHTML.includes("No inward purchases recorded yet"));
  assert.ok(mockDoc.getElementById("dash-recent-payments-tbody").innerHTML.includes("No collections or payments recorded yet"));
  assert.ok(mockDoc.getElementById("dash-recent-stock-adjustments-tbody").innerHTML.includes("No stock adjustments recorded yet"));

  console.log("PASS: testRenderEmptyMetrics renders clean ₹0.00, unavailable, and empty states");
}

// TEST 4: Backend RPC failure handling - no fallback to demo figures
function testRpcFailureHandling() {
  global.window.backend = {
    traditional_getDashboardMetrics: (cb) => {
      cb(JSON.stringify({ success: false, error: "Database offline" }));
    }
  };

  dm.loadLiveBackendData();

  const badge = mockDoc.getElementById("business-data-mode-badge").innerHTML;
  assert.ok(badge.includes("Error: Database offline"), "Badge must display error message upon RPC failure");

  // Ensure mock data was NOT loaded
  assert.notStrictEqual(mockDoc.getElementById("dash-today-sales").textContent, "₹ 48,250.00");
  assert.notStrictEqual(mockDoc.getElementById("dash-total-stock-value").textContent, "₹ 4,82,600.00");
  assert.notStrictEqual(mockDoc.getElementById("dash-receivables").textContent, "₹ 62,400.00");
  assert.notStrictEqual(mockDoc.getElementById("dash-payables").textContent, "₹ 38,900.00");
  assert.notStrictEqual(mockDoc.getElementById("dash-today-expenses").textContent, "₹ 3,450.00");

  console.log("PASS: testRpcFailureHandling fails cleanly without demo-data fallback");
}

// TEST 5: Zero Banned Mock Numbers anywhere in the rendered elements
function testNoBannedMockValues() {
  const allHtml = Array.from(mockDoc.elements.values()).map(el => el.innerHTML).join(" ");
  const banned = ["48250", "482600", "62400", "38900", "3450", "32.4%", "21712.50", "16887.50"];
  for (const b of banned) {
    assert.ok(!allHtml.includes(b), `Banned mock value ${b} was detected in frontend DOM output!`);
  }
  console.log("PASS: testNoBannedMockValues confirms zero mock figures present in DOM");
}

// Run tests
testClearDashboard();
testRenderWelcomeResolvesInconsistency();
testRenderEmptyMetrics();
testRpcFailureHandling();
testNoBannedMockValues();

console.log("==================================================================");
console.log("ALL 5 TRADITIONAL DASHBOARD FRONTEND TESTS PASSED!");
console.log("==================================================================");
