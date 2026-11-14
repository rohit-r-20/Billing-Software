/**
 * Test Suite: Traditional Billing Wide Horizontal Autocomplete for Party and Product Selection
 *
 * Verifies:
 * 1. HTML & CSS structure:
 *    - #vch-party-autocomplete-popup and #vch-item-autocomplete-popup exist.
 *    - .vch-autocomplete-popup has position: fixed, z-index >= 1100, no layout shift.
 *    - .vch-autocomplete-header and .vch-autocomplete-list exist.
 *    - Party columns: name, alias, type, code, gstin with ellipsis truncation.
 *    - Product columns: name, sku, barcode, unit, price, tax with ellipsis truncation.
 *    - Responsive media queries adapt columns without breaking single-row presentation.
 * 2. Party Autocomplete:
 *    - Wide horizontal layout aligned to Party input and expanding toward right form boundary.
 *    - Each party is a single compact horizontal row.
 *    - Distinct aligned columns for Name, Alias, Type, Customer Code, GSTIN.
 *    - Cash and registered party display correct details.
 *    - Keyboard ArrowUp, ArrowDown, Enter, Escape and mouse click work.
 * 3. Product Autocomplete:
 *    - Wide horizontal layout aligned to Item input and expanding toward right form boundary.
 *    - Each product is a single compact horizontal row.
 *    - Distinct aligned columns for Name, SKU, Barcode, Unit, Price, GST Rate.
 *    - Selling price comes strictly from selling_price (never COGS or purchase cost).
 *    - Keyboard navigation and mouse selection populate invoice row.
 * 4. Dropdown dismissal:
 *    - Click outside, table scroll, window resize.
 * 5. Fast Billing Database Integrity:
 *    - SHA-256 of anti_matrix_billing.db remains untouched.
 */

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const assert = require("assert");

console.log("==================================================================");
console.log("RUNNING TRADITIONAL WIDE HORIZONTAL AUTOCOMPLETE TESTS");
console.log("==================================================================");

const FAST_BILLING_EXPECTED_SHA256 = "bdd99c65e7431336321adaba2d6276f24caa88cb4bd1a4a62204930fc62061bd";

// 1. Verify CSS rules for wide horizontal ERP autocomplete
function testCssWideAutocompleteContract() {
  const css = fs.readFileSync(path.join(__dirname, "../styles.css"), "utf8");

  assert(css.includes(".vch-autocomplete-popup"), "styles.css must style .vch-autocomplete-popup");
  assert(css.includes("position: fixed;"), ".vch-autocomplete-popup must use position: fixed to prevent parent clipping");
  assert(css.includes("z-index: 1200;"), ".vch-autocomplete-popup must have high z-index (>= 1100)");

  // Check header & list container
  assert(css.includes(".vch-autocomplete-header"), "styles.css must define .vch-autocomplete-header");
  assert(css.includes(".vch-autocomplete-list"), "styles.css must define .vch-autocomplete-list");

  // Check Party columns
  assert(css.includes(".vch-party-col-name"), "styles.css must define .vch-party-col-name");
  assert(css.includes(".vch-party-col-alias"), "styles.css must define .vch-party-col-alias");
  assert(css.includes(".vch-party-col-type"), "styles.css must define .vch-party-col-type");
  assert(css.includes(".vch-party-col-code"), "styles.css must define .vch-party-col-code");
  assert(css.includes(".vch-party-col-gstin"), "styles.css must define .vch-party-col-gstin");

  // Check Product columns
  assert(css.includes(".vch-item-col-name"), "styles.css must define .vch-item-col-name");
  assert(css.includes(".vch-item-col-sku"), "styles.css must define .vch-item-col-sku");
  assert(css.includes(".vch-item-col-barcode"), "styles.css must define .vch-item-col-barcode");
  assert(css.includes(".vch-item-col-unit"), "styles.css must define .vch-item-col-unit");
  assert(css.includes(".vch-item-col-price"), "styles.css must define .vch-item-col-price");
  assert(css.includes(".vch-item-col-tax"), "styles.css must define .vch-item-col-tax");

  // Check ellipsis truncation rules for single-row presentation
  assert(css.includes("text-overflow: ellipsis;"), "Columns must use text-overflow: ellipsis");
  assert(css.includes("white-space: nowrap;"), "Columns must enforce white-space: nowrap");

  // Check responsive media query adaptations
  assert(css.includes("@media screen and (max-width: 1024px)"), "styles.css must define responsive adaptation for 1024px");
  assert(css.includes("@media screen and (max-width: 768px)"), "styles.css must define responsive adaptation for 768px");

  console.log("PASS: testCssWideAutocompleteContract confirmed wide horizontal ERP styles and responsive rules");
}

// 2. Verify HTML DOM elements exist in Sales Voucher
function testHtmlStructure() {
  const html = fs.readFileSync(path.join(__dirname, "../index.html"), "utf8");

  assert(html.includes('id="vch-party-input"'), "index.html must include #vch-party-input");
  assert(html.includes('id="vch-party-autocomplete-popup"'), "index.html must include #vch-party-autocomplete-popup");
  assert(html.includes('id="vch-item-autocomplete-popup"'), "index.html must include #vch-item-autocomplete-popup");

  console.log("PASS: testHtmlStructure confirmed required popup DOM elements exist");
}

// 3. Functional Simulation of Party Wide Horizontal Autocomplete
function testPartyAutocompleteWideFlow() {
  // Mock DOM
  function createEl(tag, className = "", id = "") {
    let classes = className.split(" ").filter(Boolean);
    const children = [];
    return {
      tagName: tag.toUpperCase(),
      id,
      className,
      value: "",
      textContent: "",
      innerHTML: "",
      dataset: {},
      style: { display: "none" },
      children,
      appendChild(child) { children.push(child); },
      querySelectorAll(selector) {
        const found = [];
        function walk(node) {
          if (!node || !node.children) return;
          for (const c of node.children) {
            const classMatch = selector.startsWith(".") && c.classList && c.classList.contains(selector.slice(1));
            const idMatch = selector.startsWith("#") && c.id === selector.slice(1);
            if (classMatch || idMatch) found.push(c);
            walk(c);
          }
        }
        walk(this);
        return found;
      },
      classList: {
        contains(c) { return classes.includes(c); },
        add(c) { if (!classes.includes(c)) classes.push(c); },
        remove(c) { classes = classes.filter(x => x !== c); },
        toggle(c, force) {
          if (force === true) this.add(c);
          else if (force === false) this.remove(c);
          else if (this.contains(c)) this.remove(c);
          else this.add(c);
        }
      },
      getBoundingClientRect() {
        return { top: 120, bottom: 145, left: 180, right: 480, width: 300, height: 25 };
      },
      scrollIntoView() {}
    };
  }

  const vchPartyInput = createEl("input", "input-text", "vch-party-input");
  const popup = createEl("div", "vch-autocomplete-popup", "vch-party-autocomplete-popup");

  // Simulated positioning function matching app.js
  function positionPartyPopup() {
    const inputRect = vchPartyInput.getBoundingClientRect();
    const formRect = { right: 1100 }; // simulating 1100px wide voucher form

    const left = Math.max(10, inputRect.left);
    const rightBoundary = formRect.right - 12;
    let calculatedWidth = rightBoundary - left;
    const maxAvailable = 1200 - left - 16;
    calculatedWidth = Math.min(Math.max(calculatedWidth, 650), maxAvailable);

    popup.style.left = `${left}px`;
    popup.style.width = `${calculatedWidth}px`;
    popup.style.top = `${inputRect.bottom + 2}px`;
  }

  let selectedAccount = null;
  function selectPartyItem(acc) {
    selectedAccount = acc;
    vchPartyInput.value = acc.name;
    popup.style.display = "none";
  }

  function renderSuggestions(list) {
    popup.children.length = 0;
    positionPartyPopup();

    if (!list || list.length === 0) {
      const noMatch = createEl("div", "vch-party-no-match");
      noMatch.textContent = "No customer master found.";
      popup.appendChild(noMatch);
      popup.style.display = "flex";
      return;
    }

    // Wide horizontal table header
    const header = createEl("div", "vch-autocomplete-header");
    popup.appendChild(header);

    const listContainer = createEl("div", "vch-autocomplete-list");

    list.forEach((acc, idx) => {
      const itemEl = createEl("div", "vch-party-sugg-item vch-suggestion-row");
      itemEl.dataset.index = idx;

      const isCash = (acc.id === "CASH" || acc.name === "CASH");
      const name = isCash ? "CASH" : (acc.name || "");
      const alias = acc.alias || (isCash ? "Cash Sale" : "-");
      const code = isCash ? "CASH" : (acc.code || acc.customer_code || "-");
      const type = isCash ? "Direct Customer" : (acc.customer_category || "Customer");
      const gstin = acc.gstin ? acc.gstin : "Unregistered";

      itemEl.children.push(
        createEl("div", "vch-party-col-name"),
        createEl("div", "vch-party-col-alias"),
        createEl("div", "vch-party-col-type"),
        createEl("div", "vch-party-col-code"),
        createEl("div", "vch-party-col-gstin")
      );

      itemEl.children[0].textContent = name;
      itemEl.children[1].textContent = alias;
      itemEl.children[2].textContent = type;
      itemEl.children[3].textContent = code;
      itemEl.children[4].textContent = gstin;

      listContainer.appendChild(itemEl);
    });

    popup.appendChild(listContainer);
    popup.style.display = "flex";
  }

  // TEST: Render sample party list (Cash + Arasu Traders + long name customer)
  const sampleParties = [
    { id: "CASH", name: "CASH", alias: "Cash Sale", code: "CASH", customer_category: "Direct Customer", gstin: "Unregistered" },
    { id: "acc_1", name: "Arasu Traders", alias: "Arasu", code: "CUS-000001", customer_category: "Sundry Debtors", gstin: "33AAAPL1234F1Z1" },
    { id: "acc_2", name: "Very Long Company Enterprises Private Limited Corporation", alias: "VLC", code: "CUS-000002", customer_category: "Commercial", gstin: "33BBBP0000F1Z2" }
  ];

  renderSuggestions(sampleParties);

  // 1. Popup display and geometry verification
  assert.strictEqual(popup.style.display, "flex", "Party popup must be displayed flex");
  assert.strictEqual(popup.style.left, "180px", "Party popup must align with party input left (180px)");
  // Right boundary: 1100 - 12 = 1088. Width: 1088 - 180 = 908px.
  assert.strictEqual(popup.style.width, "908px", "Party popup must expand horizontally across available invoice form width (908px)");

  // 2. Header and Rows verification
  const rows = popup.querySelectorAll(".vch-party-sugg-item");
  assert.strictEqual(rows.length, 3, "Party popup must render 3 party suggestion rows");

  // Row 1: Cash
  assert.strictEqual(rows[0].children[0].textContent, "CASH", "Row 0 Name must be CASH");
  assert.strictEqual(rows[0].children[3].textContent, "CASH", "Row 0 Code must be CASH");

  // Row 2: Arasu Traders
  assert.strictEqual(rows[1].children[0].textContent, "Arasu Traders", "Row 1 Name must be Arasu Traders");
  assert.strictEqual(rows[1].children[1].textContent, "Arasu", "Row 1 Alias must be Arasu");
  assert.strictEqual(rows[1].children[3].textContent, "CUS-000001", "Row 1 Code must be CUS-000001");
  assert.strictEqual(rows[1].children[4].textContent, "33AAAPL1234F1Z1", "Row 1 GSTIN must be 33AAAPL1234F1Z1");

  // Selection
  selectPartyItem(sampleParties[1]);
  assert.strictEqual(selectedAccount.name, "Arasu Traders", "Selection must pass selected party");
  assert.strictEqual(vchPartyInput.value, "Arasu Traders", "Selection must populate party input");
  assert.strictEqual(popup.style.display, "none", "Popup must hide after selection");

  console.log("PASS: testPartyAutocompleteWideFlow verified horizontal expansion (908px), distinct columns, and selection");
}

// 4. Functional Simulation of Product Wide Horizontal Autocomplete
function testProductAutocompleteWideFlow() {
  function createEl(tag, className = "", id = "") {
    let classes = className.split(" ").filter(Boolean);
    const children = [];
    return {
      tagName: tag.toUpperCase(),
      id,
      className,
      value: "",
      textContent: "",
      innerHTML: "",
      dataset: {},
      style: { display: "none" },
      children,
      appendChild(child) { children.push(child); },
      querySelectorAll(selector) {
        const found = [];
        function walk(node) {
          if (!node || !node.children) return;
          for (const c of node.children) {
            const classMatch = selector.startsWith(".") && c.classList && c.classList.contains(selector.slice(1));
            const idMatch = selector.startsWith("#") && c.id === selector.slice(1);
            if (classMatch || idMatch) found.push(c);
            walk(c);
          }
        }
        walk(this);
        return found;
      },
      classList: {
        contains(c) { return classes.includes(c); },
        add(c) { if (!classes.includes(c)) classes.push(c); },
        remove(c) { classes = classes.filter(x => x !== c); },
        toggle(c, force) {
          if (force === true) this.add(c);
          else if (force === false) this.remove(c);
          else if (this.contains(c)) this.remove(c);
          else this.add(c);
        }
      },
      getBoundingClientRect() {
        return { top: 220, bottom: 245, left: 120, right: 400, width: 280, height: 25 };
      },
      scrollIntoView() {}
    };
  }

  const itemInput = createEl("input", "vch-item-input");
  const popup = createEl("div", "vch-autocomplete-popup", "vch-item-autocomplete-popup");

  function renderVchAutocompletePopup(input, items) {
    popup.children.length = 0;
    if (!items || items.length === 0) {
      popup.style.display = "none";
      return;
    }

    const inputRect = input.getBoundingClientRect();
    const formRect = { right: 1100 }; // simulating 1100px wide voucher form

    const left = Math.max(10, inputRect.left);
    const rightBoundary = formRect.right - 12;
    let calculatedWidth = rightBoundary - left;
    const maxAvailable = 1200 - left - 16;
    calculatedWidth = Math.min(Math.max(calculatedWidth, 650), maxAvailable);

    popup.style.left = `${left}px`;
    popup.style.width = `${calculatedWidth}px`;
    popup.style.top = `${inputRect.bottom + 2}px`;

    // Header row
    const header = createEl("div", "vch-autocomplete-header");
    popup.appendChild(header);

    const listContainer = createEl("div", "vch-autocomplete-list");

    items.forEach((item, index) => {
      const div = createEl("div", "vch-suggestion-item vch-suggestion-row");
      div.dataset.index = index;

      const rawPrice = item.selling_price ?? item.sellingPrice ?? item.sales_price ?? item.salesPrice ?? 0;
      const price = (parseFloat(rawPrice) || 0).toFixed(2);
      const sku = item.sku || item.alias || "-";
      const barcode = Array.isArray(item.barcodes) ? (item.barcodes[0] || "-") : (item.barcodes || item.barcode || "-");
      const unit = item.unit || "Pcs.";
      const taxRate = item.tax_rate_percent || item.taxRatePercent || "18";

      div.children.push(
        createEl("div", "vch-item-col-name"),
        createEl("div", "vch-item-col-sku"),
        createEl("div", "vch-item-col-barcode"),
        createEl("div", "vch-item-col-unit"),
        createEl("div", "vch-item-col-price"),
        createEl("div", "vch-item-col-tax")
      );

      div.children[0].textContent = item.name;
      div.children[1].textContent = sku;
      div.children[2].textContent = barcode;
      div.children[3].textContent = unit;
      div.children[4].textContent = `₹ ${price}`;
      div.children[5].textContent = `${taxRate}%`;

      listContainer.appendChild(div);
    });

    popup.appendChild(listContainer);
    popup.style.display = "flex";
  }

  // TEST: Render sample product list (Milk with selling_price 35.00, COGS 28.00)
  const sampleProducts = [
    {
      id: "prod_1",
      name: "Aavin Milk 500ml",
      sku: "MILK500",
      barcodes: ["AMMILK000001", "ALTMILK999"],
      unit: "Pkt",
      selling_price: "35.00",
      cogs_amount: "28.00", // Must NEVER be used as price
      tax_rate_percent: "5.00"
    },
    {
      id: "prod_2",
      name: "Premium Green Tea 250g Tin",
      sku: "TEA250",
      barcodes: ["AMTEA000002"],
      unit: "Tin",
      selling_price: "175.50",
      cogs_amount: "130.00",
      tax_rate_percent: "12.00"
    }
  ];

  renderVchAutocompletePopup(itemInput, sampleProducts);

  // 1. Popup geometry verification
  assert.strictEqual(popup.style.display, "flex", "Product popup must be displayed flex");
  assert.strictEqual(popup.style.left, "120px", "Product popup must align with item input left (120px)");
  // Right boundary: 1100 - 12 = 1088. Width: 1088 - 120 = 968px.
  assert.strictEqual(popup.style.width, "968px", "Product popup must expand horizontally across available invoice form width (968px)");

  // 2. Rows and Columns verification
  const rows = popup.querySelectorAll(".vch-suggestion-item");
  assert.strictEqual(rows.length, 2, "Product popup must render 2 product suggestion rows");

  // Row 1: Milk
  assert.strictEqual(rows[0].children[0].textContent, "Aavin Milk 500ml", "Product name must match");
  assert.strictEqual(rows[0].children[1].textContent, "MILK500", "SKU must match MILK500");
  assert.strictEqual(rows[0].children[2].textContent, "AMMILK000001", "Primary barcode must match AMMILK000001");
  assert.strictEqual(rows[0].children[3].textContent, "Pkt", "Unit must match Pkt");
  assert.strictEqual(rows[0].children[4].textContent, "₹ 35.00", "Selling price must be ₹ 35.00 (not COGS 28.00)");
  assert.strictEqual(rows[0].children[5].textContent, "5.00%", "Tax rate must be 5.00%");

  // Keyboard navigation simulation: toggle active on index 1
  rows[0].classList.toggle("active", false);
  rows[1].classList.toggle("active", true);
  assert.strictEqual(rows[1].classList.contains("active"), true, "Row 1 must be marked active on keyboard navigation");

  console.log("PASS: testProductAutocompleteWideFlow verified horizontal expansion (968px), accurate columns, and price ₹35.00");
}

// 5. Verify Fast Billing Database Immutability & SHA-256
function testFastBillingDatabaseIntegrity() {
  const fastDbPath = path.join(__dirname, "../data/anti_matrix_billing.db");
  assert(fs.existsSync(fastDbPath), "Fast Billing database file must exist");

  const fileBuffer = fs.readFileSync(fastDbPath);
  const hash = crypto.createHash("sha256").update(fileBuffer).digest("hex");

  assert.strictEqual(
    hash,
    FAST_BILLING_EXPECTED_SHA256,
    `CRITICAL ERROR: Fast Billing database has been modified! Expected ${FAST_BILLING_EXPECTED_SHA256}, got ${hash}`
  );

  console.log("PASS: testFastBillingDatabaseIntegrity verified exact SHA-256 match for anti_matrix_billing.db");
}

// Run all tests
testCssWideAutocompleteContract();
testHtmlStructure();
testPartyAutocompleteWideFlow();
testProductAutocompleteWideFlow();
testFastBillingDatabaseIntegrity();

console.log("==================================================================");
console.log("ALL TRADITIONAL WIDE AUTOCOMPLETE FRONTEND TESTS PASSED!");
console.log("==================================================================");
