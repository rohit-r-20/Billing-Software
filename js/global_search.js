/**
 * ALPHA BILLING - Global Search (Ctrl+K) & Shortcuts Modal
 */

class GlobalSearchManager {
  constructor() {
    this.modalEl = null;
    this.inputEl = null;
    this.resultsEl = null;
    this.selectedIndex = 0;
    this.results = [];

    // Searchable items index
    this.searchIndex = [
      // Navigation & Screens
      { title: "Fast Billing (Retail POS)", category: "Transaction", action: () => window.showScreen("view-fast-billing"), icon: "shoppingBag" },
      { title: "New Sales Tax Invoice", category: "Transaction", action: () => window.showScreen("view-sales-voucher"), icon: "fileText" },
      { title: "Sales Invoices Register", category: "Transaction", action: () => window.showScreen("view-sales-list"), icon: "fileText" },
      { title: "Purchase Entry (Inward)", category: "Transaction", action: () => window.showScreen("view-purchase-entry"), icon: "shoppingCart" },
      { title: "Purchase Register", category: "Transaction", action: () => window.showScreen("view-purchase-list"), icon: "shoppingCart" },
      { title: "Financial Day Book", category: "Display", action: () => window.showScreen("view-day-book"), icon: "barChart3" },
      { title: "Double-Entry Trial Balance", category: "Display", action: () => window.showScreen("view-day-book"), icon: "barChart3" },
      { title: "Stock Valuation & WAC Summary", category: "Display", action: () => window.showScreen("view-stock-summary"), icon: "package" },
      { title: "Add New Product SKU", category: "Administration", action: () => window.showScreen("view-add-item-master"), icon: "plusCircle" },
      { title: "Products & Item Catalogue", category: "Administration", action: () => window.showScreen("view-items-list"), icon: "package" },
      { title: "Supplier Accounts Master", category: "Administration", action: () => window.showScreen("view-supplier-master"), icon: "user" },
      { title: "Backup & Restore Database", category: "Housekeeping", action: () => window.openModal("modal-backup"), icon: "database" },
      { title: "GST Reports & Daily Summary", category: "Display", action: () => window.openModal("modal-reports"), icon: "barChart3" },
      { title: "Low-Stock Alerts", category: "Display", action: () => window.openModal("modal-low-stock"), icon: "package" },
      { title: "Printer & Hardware Settings", category: "Printing", action: () => window.openModal("modal-thermal-preview"), icon: "printer" },
      { title: "Wi-Fi Mobile Barcode Scanner", category: "Add-on", action: () => window.openModal("modal-mobile-scanner"), icon: "blocks" },

      // Sample Data / Masters
      { title: "Odonil Room Air Freshener 50g Block", category: "Product SKU", action: () => window.showToast("Product: Odonil Room Air Freshener [BAR: 8901207001428]"), icon: "package" },
      { title: "Tata Salt 1kg Crystal Pure", category: "Product SKU", action: () => window.showToast("Product: Tata Salt 1kg [MRP: ₹28.00]"), icon: "package" },
      { title: "Fortune Sunlite Refined Sunflower Oil 1L", category: "Product SKU", action: () => window.showToast("Product: Fortune Sunflower Oil 1L [MRP: ₹145.00]"), icon: "package" },
      { title: "CASH Customer (Counter Walk-in)", category: "Customer Account", action: () => window.showToast("Account: CASH Sale"), icon: "wallet" }
    ];
  }

  init() {
    this.modalEl = document.getElementById("modal-global-search");
    this.inputEl = document.getElementById("input-global-search");
    this.resultsEl = document.getElementById("global-search-results");

    // Search Trigger Button in Header
    const triggerBtn = document.getElementById("btn-trigger-global-search");
    if (triggerBtn) {
      triggerBtn.addEventListener("click", () => this.open());
    }

    // Close Button in Modal
    const closeBtn = document.getElementById("btn-close-global-search");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => this.close());
    }

    // Click on Backdrop to close
    if (this.modalEl) {
      this.modalEl.addEventListener("click", (e) => {
        if (e.target === this.modalEl) this.close();
      });
    }

    // Input typing filter
    if (this.inputEl) {
      this.inputEl.addEventListener("input", (e) => this.filter(e.target.value));
      this.inputEl.addEventListener("keydown", (e) => this.handleKeydown(e));
    }

    // Global Keybinding Ctrl+K or Cmd+K or "/"
    document.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        this.open();
      } else if (e.key === "Escape" && this.isOpen()) {
        this.close();
      }
    });
  }

  isOpen() {
    return this.modalEl && this.modalEl.classList.contains("active");
  }

  open() {
    if (!this.modalEl) return;
    this.modalEl.classList.add("active");
    if (this.inputEl) {
      this.inputEl.value = "";
      this.inputEl.focus();
    }
    this.filter("");
  }

  close() {
    if (!this.modalEl) return;
    this.modalEl.classList.remove("active");
  }

  filter(query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) {
      this.results = this.searchIndex.slice(0, 8);
    } else {
      this.results = this.searchIndex.filter(item => 
        item.title.toLowerCase().includes(q) || 
        item.category.toLowerCase().includes(q)
      ).slice(0, 10);
    }

    this.selectedIndex = 0;
    this.renderResults();
  }

  renderResults() {
    if (!this.resultsEl) return;
    this.resultsEl.innerHTML = "";

    if (this.results.length === 0) {
      this.resultsEl.innerHTML = `
        <div class="alpha-empty-state" style="padding: 24px 10px;">
          <div class="empty-state-title">No matching results found</div>
          <div class="empty-state-desc">Try searching for "POS", "Invoice", "Stock", or "Backup".</div>
        </div>
      `;
      return;
    }

    // Group by category
    const groups = {};
    this.results.forEach((r, idx) => {
      if (!groups[r.category]) groups[r.category] = [];
      groups[r.category].push({ ...r, index: idx });
    });

    Object.keys(groups).forEach(cat => {
      const titleEl = document.createElement("div");
      titleEl.className = "search-result-group-title";
      titleEl.textContent = cat;
      this.resultsEl.appendChild(titleEl);

      groups[cat].forEach(item => {
        const itemBtn = document.createElement("button");
        itemBtn.type = "button";
        itemBtn.className = `search-result-item ${item.index === this.selectedIndex ? 'highlighted' : ''}`;
        
        const iconSvg = window.getLucideIcon(item.icon || "fileText", "search-result-icon", 16);
        itemBtn.innerHTML = `
          ${iconSvg}
          <span style="flex:1;">${item.title}</span>
          <span class="status-pill status-pill-neutral" style="font-size:10px;">Jump &rarr;</span>
        `;

        itemBtn.addEventListener("click", () => {
          this.close();
          item.action();
        });

        itemBtn.addEventListener("mouseenter", () => {
          this.selectedIndex = item.index;
          this.updateHighlight();
        });

        this.resultsEl.appendChild(itemBtn);
      });
    });
  }

  handleKeydown(e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (this.results.length > 0) {
        this.selectedIndex = (this.selectedIndex + 1) % this.results.length;
        this.updateHighlight();
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (this.results.length > 0) {
        this.selectedIndex = (this.selectedIndex - 1 + this.results.length) % this.results.length;
        this.updateHighlight();
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (this.results[this.selectedIndex]) {
        this.close();
        this.results[this.selectedIndex].action();
      }
    }
  }

  updateHighlight() {
    if (!this.resultsEl) return;
    const items = this.resultsEl.querySelectorAll(".search-result-item");
    items.forEach((el, idx) => {
      el.classList.toggle("highlighted", idx === this.selectedIndex);
    });
  }

  openShortcutsHelp() {
    this.open();
    if (this.inputEl) {
      this.inputEl.value = "Shortcuts";
      this.filter("shortcuts");
    }
    window.showToast("Shortcuts: Ctrl+K (Search), Ctrl+B (Toggle Sidebar), F1 (Product Search), Esc (Close/Back)");
  }
}

window.GlobalSearchManager = new GlobalSearchManager();

