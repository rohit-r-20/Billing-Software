/**
 * ALPHA BILLING - Primary Sidebar Navigation System
 * Functional Menu Hierarchy matching approved ERP standards:
 * 1. Company (Edit Company, Close Company)
 * 2. Administration (9 standard ERP entries)
 * 3. Transaction (13 standard financial & inventory entries)
 * 4. Display, 5. Printing, 6. Housekeeping, 7. Help, 8. Add-on
 */

const PRIMARY_NAV_CONFIG = [
  // 1. COMPANY (Exactly 2 entries)
  {
    id: "company",
    label: "Company",
    icon: "building",
    submenus: [
      { 
        id: "sub-comp-edit", 
        label: "Edit Company", 
        action: "edit-company", 
        icon: "edit3" 
      },
      { 
        id: "sub-comp-close", 
        label: "Close Company", 
        action: "close-company", 
        icon: "folderX" 
      }
    ]
  },

  // 2. ADMINISTRATION (Exactly 9 entries in exact order)
  {
    id: "administration",
    label: "Administration",
    icon: "shieldCheck",
    submenus: [
      { 
        id: "sub-admin-masters", 
        label: "Masters", 
        icon: "folderTree",
        action: "open-view",
        targetView: "view-items-list",
        expandable: true,
        children: [
          { id: "sub-admin-mast-accounts", label: "Account Master", action: "open-view", targetView: "view-add-account-master", icon: "wallet" },
          { id: "sub-admin-mast-items", label: "Item Master (Catalogue)", action: "open-view", targetView: "view-items-list", icon: "package" },
          { id: "sub-admin-mast-add-item", label: "Add Product SKU", action: "open-view", targetView: "view-add-item-master", icon: "plusCircle" },
          { id: "sub-admin-mast-suppliers", label: "Supplier Master", action: "open-view", targetView: "view-supplier-master", icon: "user" },
          { id: "sub-admin-mast-customers", label: "Customer Master", action: "open-view", targetView: "view-add-account-master", icon: "users" }
        ]
      },
      { 
        id: "sub-admin-configuration", 
        label: "Configuration", 
        icon: "settings", 
        action: "open-modal", 
        modalId: "modal-config" 
      },
      { 
        id: "sub-admin-users", 
        label: "Users", 
        icon: "users", 
        action: "placeholder", 
        info: "User Roles, Permissions & Security Manager" 
      },
      { 
        id: "sub-admin-mobile-app", 
        label: "Mobile App", 
        icon: "smartphone", 
        action: "open-modal", 
        modalId: "modal-mobile-scanner" 
      },
      { 
        id: "sub-admin-utilities", 
        label: "Utilities", 
        icon: "wrench", 
        action: "placeholder", 
        info: "System Maintenance, Audit & Database Diagnostics" 
      },
      { 
        id: "sub-admin-bulk-updates", 
        label: "Bulk Updates", 
        icon: "layers", 
        action: "placeholder", 
        info: "Bulk Master Pricing, Tax Rate & Stock Field Updates" 
      },
      { 
        id: "sub-admin-data-export-import", 
        label: "Data Export Import", 
        icon: "arrowUpDown", 
        action: "open-modal", 
        modalId: "modal-data-migration" 
      },
      { 
        id: "sub-admin-misc-data-entry", 
        label: "Miscellaneous Data Entry", 
        icon: "fileSpreadsheet", 
        action: "placeholder", 
        info: "Opening Balances & Miscellaneous Transaction Data Entry" 
      },
      { 
        id: "sub-admin-change-fin-year", 
        label: "Change Financial Year", 
        icon: "calendar", 
        action: "placeholder", 
        info: "Financial Year Shift & Annual Books Closing Manager" 
      }
    ]
  },

  // 3. TRANSACTION (Exactly 13 entries in exact order)
  {
    id: "transaction",
    label: "Transaction",
    icon: "arrowLeftRight",
    submenus: [
      { 
        id: "sub-tx-sales", 
        label: "Sales", 
        icon: "shoppingBag", 
        action: "open-view", 
        targetView: "view-sales-voucher",
        expandable: true,
        children: [
          { id: "sub-tx-sales-new", label: "New Tax Invoice", action: "open-view", targetView: "view-sales-voucher", icon: "fileText" },
          { id: "sub-tx-sales-pos", label: "Fast Billing (POS)", action: "open-view", targetView: "view-fast-billing", icon: "shoppingBag", badge: "POS" },
          { id: "sub-tx-sales-reg", label: "Sales Register", action: "open-view", targetView: "view-sales-list", icon: "fileText" }
        ]
      },
      { 
        id: "sub-tx-purchase", 
        label: "Purchase", 
        icon: "shoppingCart", 
        action: "open-view", 
        targetView: "view-purchase-entry",
        expandable: true,
        children: [
          { id: "sub-tx-pur-inward", label: "Purchase Entry (Inward)", action: "open-view", targetView: "view-purchase-entry", icon: "shoppingCart" },
          { id: "sub-tx-pur-reg", label: "Purchase Register", action: "open-view", targetView: "view-purchase-list", icon: "fileText" }
        ]
      },
      { 
        id: "sub-tx-sales-return", 
        label: "Sales Return (Cr. Note)", 
        icon: "rotateCcw", 
        action: "open-modal", 
        modalId: "modal-sales-return" 
      },
      { 
        id: "sub-tx-purchase-return", 
        label: "Purchase Return (Dr. Note)", 
        icon: "rotateCw", 
        action: "open-modal", 
        modalId: "modal-purchase-return" 
      },
      { 
        id: "sub-tx-payment", 
        label: "Payment", 
        icon: "creditCard", 
        action: "open-view", 
        targetView: "view-day-book", 
        info: "Vendor & Expense Payment Voucher" 
      },
      { 
        id: "sub-tx-receipt", 
        label: "Receipt", 
        icon: "wallet", 
        action: "open-view", 
        targetView: "view-day-book", 
        info: "Customer Collection & Receipt Voucher" 
      },
      { 
        id: "sub-tx-journal", 
        label: "Journal", 
        icon: "bookOpen", 
        action: "open-view", 
        targetView: "view-day-book", 
        info: "General Double-Entry Journal Adjustment Voucher" 
      },
      { 
        id: "sub-tx-contra", 
        label: "Contra", 
        icon: "arrowLeftRight", 
        action: "open-view", 
        targetView: "view-day-book", 
        info: "Cash Deposit / Withdrawal & Inter-Bank Contra Voucher" 
      },
      { 
        id: "sub-tx-dr-note-no-items", 
        label: "Dr. Note (w/o Items)", 
        icon: "fileMinus", 
        action: "placeholder", 
        info: "Debit Note Voucher without Inventory Items" 
      },
      { 
        id: "sub-tx-cr-note-no-items", 
        label: "Cr. Note (w/o Items)", 
        icon: "filePlus", 
        action: "placeholder", 
        info: "Credit Note Voucher without Inventory Items" 
      },
      { 
        id: "sub-tx-stock-transfer", 
        label: "Stock Transfer", 
        icon: "truck", 
        action: "open-view", 
        targetView: "view-stock-adjustments", 
        info: "Godown / Inter-Branch Stock Transfer" 
      },
      { 
        id: "sub-tx-stock-journal", 
        label: "Stock Journal", 
        icon: "clipboardCheck", 
        action: "open-view", 
        targetView: "view-stock-adjustments", 
        info: "Stock Journal & Physical Audit Inventory Reconciliation" 
      },
      { 
        id: "sub-tx-gst-misc", 
        label: "GST Misc. Utilities", 
        icon: "percent", 
        action: "open-modal", 
        modalId: "modal-reports", 
        info: "GST Returns & Tax Utility Tools" 
      }
    ]
  },

  // 4. DISPLAY (Unchanged)
  {
    id: "display",
    label: "Display",
    icon: "barChart3",
    submenus: [
      { id: "sub-disp-overview", label: "Operational Dashboard", action: "open-view", targetView: "view-dashboard", icon: "barChart3", isDefault: true },
      { id: "sub-disp-daybook", label: "Financial Day Book", action: "open-view", targetView: "view-day-book", icon: "bookOpen" },
      { id: "sub-disp-trial-balance", label: "Trial Balance (Double-Entry)", action: "open-view", targetView: "view-day-book", icon: "fileSpreadsheet" },
      { id: "sub-disp-stock", label: "Stock Valuation & WAC Status", action: "open-view", targetView: "view-stock-summary", icon: "package" },
      { id: "sub-disp-low-stock", label: "Low-Stock Alerts & Warnings", action: "open-modal", modalId: "modal-low-stock", icon: "bell" },
      { id: "sub-disp-gst", label: "GST Reports & Daily Summary", action: "open-modal", modalId: "modal-reports", icon: "percent" }
    ]
  },

  // 5. PRINTING (Unchanged)
  {
    id: "printing",
    label: "Printing",
    icon: "printer",
    submenus: [
      { id: "sub-print-settings", label: "Printer & Hardware Settings", action: "open-modal", modalId: "modal-thermal-preview", icon: "printer" },
      { id: "sub-print-thermal", label: "Thermal Receipt Designer (80mm/58mm)", action: "placeholder", info: "Thermal Receipt Format Setup", icon: "fileText" },
      { id: "sub-print-invoice", label: "Tax Invoice Template Designer", action: "placeholder", info: "A4 / A5 Document Layout Setup", icon: "fileText" },
      { id: "sub-print-barcode", label: "Barcode & Label Tag Generator", action: "placeholder", info: "Barcode Sheet Printer Utility", icon: "package" }
    ]
  },

  // 6. HOUSEKEEPING (Unchanged)
  {
    id: "housekeeping",
    label: "Housekeeping",
    icon: "database",
    submenus: [
      { id: "sub-hk-backup", label: "Backup & Restore Database", action: "open-modal", modalId: "modal-backup", icon: "database" },
      { id: "sub-hk-migration", label: "Data Migration (JSON Export / Import)", action: "open-modal", modalId: "modal-data-migration", icon: "arrowUpDown" },
      { id: "sub-hk-audit", label: "Security & Audit Trail Log", action: "placeholder", info: "System Event & Transaction Audit Log", icon: "fileText" },
      { id: "sub-hk-compact", label: "Database Maintenance & Compact", action: "placeholder", info: "SQLite Optimization & Indexing", icon: "wrench" }
    ]
  },

  // 7. HELP (Unchanged)
  {
    id: "help",
    label: "Help",
    icon: "helpCircle",
    submenus: [
      { id: "sub-help-shortcuts", label: "Keyboard Shortcuts Guide", action: "help-shortcuts", icon: "helpCircle" },
      { id: "sub-help-manual", label: "User Manual & Video Tutorials", action: "placeholder", info: "Alpha Billing ERP User Guide", icon: "bookOpen" },
      { id: "sub-help-zoom", label: "Display Scaling & Zoom Controls", action: "help-zoom", icon: "plusCircle" },
      { id: "sub-help-about", label: "About Alpha Billing ERP v2.5.0", action: "help-about", icon: "shieldCheck" }
    ]
  },

  // 8. ADD-ON (Unchanged)
  {
    id: "addon",
    label: "Add-on",
    icon: "blocks",
    submenus: [
      { id: "sub-add-mobile-scan", label: "Wi-Fi Mobile Barcode Scanner", action: "open-modal", modalId: "modal-mobile-scanner", icon: "smartphone" },
      { id: "sub-add-ocr", label: "Supplier Invoice Document OCR", action: "open-modal", modalId: "modal-ocr", icon: "fileText" },
      { id: "sub-add-cloud-sync", label: "Cloud Multi-Terminal Relay", action: "placeholder", info: "Real-time Multi-Device Sync Engine", icon: "blocks" }
    ]
  }
];

class SidebarNavigationManager {
  constructor() {
    this.sidebarEl = null;
    this.navContainerEl = null;
    this.flyoutEl = null;
    this.isCollapsed = localStorage.getItem("alpha_sidebar_collapsed") === "true";
    this.expandedSections = new Set(["display"]); // Default expanded section
    this.expandedSubgroups = new Set();
    this.activeSectionId = "display";
    this.activeSubmenuId = "sub-disp-overview";
  }

  init() {
    this.sidebarEl = document.getElementById("alpha-sidebar");
    this.navContainerEl = document.getElementById("alpha-sidebar-nav");
    
    // Create flyout tooltip container if not present
    this.ensureFlyoutContainer();

    // Render Navigation
    this.render();

    // Bind Collapse Toggle
    const toggleBtn = document.getElementById("btn-sidebar-toggle");
    if (toggleBtn) {
      toggleBtn.addEventListener("click", () => this.toggleCollapse());
    }

    // Apply initial collapse state
    if (this.isCollapsed && this.sidebarEl) {
      this.sidebarEl.classList.add("collapsed");
      this.updateToggleButtonIcon(true);
    }

    // Keyboard navigation
    this.bindKeyboardNavigation();
  }

  ensureFlyoutContainer() {
    let flyout = document.getElementById("sidebar-floating-flyout");
    if (!flyout) {
      flyout = document.createElement("div");
      flyout.id = "sidebar-floating-flyout";
      flyout.className = "sidebar-floating-flyout";
      document.body.appendChild(flyout);
    }
    this.flyoutEl = flyout;
  }

  render() {
    if (!this.navContainerEl) return;
    this.navContainerEl.innerHTML = "";

    PRIMARY_NAV_CONFIG.forEach(sec => {
      const sectionItem = document.createElement("div");
      sectionItem.className = `nav-section-item ${this.activeSectionId === sec.id ? "active" : ""} ${this.expandedSections.has(sec.id) ? "expanded" : ""}`;
      sectionItem.id = `nav-sec-${sec.id}`;
      sectionItem.dataset.sectionId = sec.id;

      // Parent Section Button
      const parentBtn = document.createElement("button");
      parentBtn.type = "button";
      parentBtn.className = "nav-parent-btn";
      parentBtn.id = `btn-sec-${sec.id}`;
      parentBtn.setAttribute("aria-expanded", this.expandedSections.has(sec.id) ? "true" : "false");
      parentBtn.setAttribute("tabindex", "0");

      const iconHtml = window.getLucideIcon(sec.icon, "nav-icon");
      const arrowHtml = window.getLucideIcon("chevronRight", "nav-arrow");

      parentBtn.innerHTML = `
        <span class="nav-icon">${iconHtml}</span>
        <span class="nav-label">${sec.label}</span>
        <span class="nav-arrow">${arrowHtml}</span>
      `;

      // Click: Toggle Expand/Collapse accordion
      parentBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (this.isCollapsed) {
          this.setCollapsed(false);
          this.expandSection(sec.id);
        } else {
          this.toggleSection(sec.id);
        }
      });

      // Hover for collapsed flyout tooltip
      parentBtn.addEventListener("mouseenter", () => {
        if (this.isCollapsed) {
          this.showCollapsedFlyout(sec, parentBtn);
        }
      });

      parentBtn.addEventListener("mouseleave", () => {
        if (this.isCollapsed) {
          this.scheduleHideFlyout();
        }
      });

      // Submenu Container
      const submenuList = document.createElement("div");
      submenuList.className = "nav-submenu-list";
      submenuList.id = `submenu-${sec.id}`;

      sec.submenus.forEach(sub => {
        const hasChildren = Array.isArray(sub.children) && sub.children.length > 0;
        
        // Wrap each top-level submenu entry inside a .nav-sub-item wrapper
        const subItemWrapper = document.createElement("div");
        subItemWrapper.className = `nav-sub-item ${hasChildren ? "nav-sub-group" : ""}`;
        if (hasChildren && this.expandedSubgroups.has(sub.id)) {
          subItemWrapper.classList.add("expanded");
        }

        const subBtn = document.createElement("button");
        subBtn.type = "button";
        subBtn.className = `nav-sub-btn ${this.activeSubmenuId === sub.id ? "active" : ""}`;
        subBtn.id = sub.compatId || sub.id;
        subBtn.dataset.subId = sub.id;
        subBtn.dataset.sectionId = sec.id;
        subBtn.setAttribute("tabindex", "0");

        const subIconHtml = sub.icon ? window.getLucideIcon(sub.icon, "nav-sub-icon", 14) : "";
        let badgeHtml = "";
        if (sub.badge) {
          badgeHtml = `<span class="nav-sub-badge">${sub.badge}</span>`;
        }
        let expandChevronHtml = "";
        if (hasChildren) {
          expandChevronHtml = `<span class="nav-sub-expand-icon">${window.getLucideIcon("chevronRight", "", 12)}</span>`;
        }

        subBtn.innerHTML = `
          <span class="nav-sub-icon">${subIconHtml}</span>
          <span class="nav-sub-label">${sub.label}</span>
          ${badgeHtml}
          ${expandChevronHtml}
        `;

        subBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          if (hasChildren) {
            // Toggle expandable child items
            const isExp = subItemWrapper.classList.toggle("expanded");
            if (isExp) this.expandedSubgroups.add(sub.id);
            else this.expandedSubgroups.delete(sub.id);
          }
          this.selectSubmenu(sec.id, sub);
        });

        subItemWrapper.appendChild(subBtn);

        // Render expandable nested child items if present
        if (hasChildren) {
          const childrenList = document.createElement("div");
          childrenList.className = "nav-sub-children-list";
          
          sub.children.forEach(child => {
            const childBtn = document.createElement("button");
            childBtn.type = "button";
            childBtn.className = `nav-child-sub-btn ${this.activeSubmenuId === child.id ? "active" : ""}`;
            childBtn.id = child.id;
            childBtn.dataset.subId = child.id;
            childBtn.dataset.parentId = sub.id;
            childBtn.dataset.sectionId = sec.id;

            const childIconHtml = child.icon ? window.getLucideIcon(child.icon, "nav-sub-icon", 12) : "";
            childBtn.innerHTML = `
              <span class="nav-sub-icon" style="width:14px; height:14px;">${childIconHtml}</span>
              <span class="nav-sub-label">${child.label}</span>
              ${child.badge ? `<span class="nav-sub-badge">${child.badge}</span>` : ""}
            `;

            childBtn.addEventListener("click", (e) => {
              e.stopPropagation();
              this.selectSubmenu(sec.id, child);
            });

            childrenList.appendChild(childBtn);
          });

          subItemWrapper.appendChild(childrenList);
        }

        submenuList.appendChild(subItemWrapper);
      });

      sectionItem.appendChild(parentBtn);
      sectionItem.appendChild(submenuList);
      this.navContainerEl.appendChild(sectionItem);
    });
  }

  toggleSection(sectionId) {
    if (this.expandedSections.has(sectionId)) {
      this.expandedSections.delete(sectionId);
    } else {
      this.expandedSections.add(sectionId);
    }
    this.updateSectionDOM(sectionId);
  }

  expandSection(sectionId) {
    this.expandedSections.add(sectionId);
    this.updateSectionDOM(sectionId);
  }

  updateSectionDOM(sectionId) {
    const item = document.getElementById(`nav-sec-${sectionId}`);
    if (item) {
      const isExp = this.expandedSections.has(sectionId);
      item.classList.toggle("expanded", isExp);
      const btn = item.querySelector(".nav-parent-btn");
      if (btn) btn.setAttribute("aria-expanded", isExp ? "true" : "false");
    }
  }

  selectSubmenu(sectionId, sub) {
    this.activeSectionId = sectionId;
    this.activeSubmenuId = sub.id;

    // Update active highlight classes
    document.querySelectorAll(".nav-section-item").forEach(el => el.classList.remove("active"));
    const secEl = document.getElementById(`nav-sec-${sectionId}`);
    if (secEl) secEl.classList.add("active");

    document.querySelectorAll(".nav-sub-btn, .nav-child-sub-btn").forEach(el => el.classList.remove("active"));
    const activeSubBtn = document.querySelector(`[data-sub-id="${sub.id}"]`);
    if (activeSubBtn) activeSubBtn.classList.add("active");

    // Close mobile drawer if open
    this.closeMobileDrawer();

    // Route action
    this.executeAction(sub);
  }

  executeAction(sub) {
    console.log(`[Navigation] Action triggered:`, sub);

    if (sub.action === "open-view") {
      if (typeof window.showScreen === "function") {
        window.showScreen(sub.targetView);
      } else {
        console.warn(`showScreen not found, target: ${sub.targetView}`);
      }
      this.updateBreadcrumb(sub.label);
    } else if (sub.action === "open-modal") {
      if (typeof window.openModal === "function") {
        window.openModal(sub.modalId);
      } else {
        const modal = document.getElementById(sub.modalId);
        if (modal) modal.style.display = "flex";
      }
      this.updateBreadcrumb(sub.label);
    } else if (sub.action === "edit-company") {
      this.openEditCompanyModal();
    } else if (sub.action === "close-company") {
      this.openCloseCompanyConfirmModal();
    } else if (sub.action === "help-shortcuts") {
      if (window.GlobalSearchManager) window.GlobalSearchManager.openShortcutsHelp();
    } else if (sub.action === "help-zoom") {
      if (typeof window.showToast === "function") window.showToast("Use '+' or '-' in the top header to adjust interface zoom.");
    } else if (sub.action === "help-about") {
      if (typeof window.showToast === "function") window.showToast("Alpha Billing ERP v2.5.0 — Cloud Business Management Suite");
    } else if (sub.action === "placeholder") {
      this.openPlaceholderModal(sub);
    }
  }

  openEditCompanyModal() {
    const modal = document.getElementById("modal-edit-company");
    if (!modal) return;

    const comp = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    if (comp) {
      const nameInput = document.getElementById("edit-comp-name");
      const codeInput = document.getElementById("edit-comp-code");
      const finyearInput = document.getElementById("edit-comp-finyear");
      const gstinInput = document.getElementById("edit-comp-gstin");
      const stateInput = document.getElementById("edit-comp-state");
      const addrInput = document.getElementById("edit-comp-address");

      if (nameInput) nameInput.value = comp.name || "";
      if (codeInput) codeInput.value = comp.code || comp.id || "";
      if (finyearInput) finyearInput.value = comp.finYear || "2026-2027";
      if (gstinInput) gstinInput.value = comp.taxNo || "";
      if (stateInput) stateInput.value = comp.state || "Tamilnadu";
      if (addrInput) addrInput.value = comp.address || "";
    }

    modal.classList.add("show");
    modal.style.display = "flex";
  }

  openCloseCompanyConfirmModal() {
    const modal = document.getElementById("modal-close-company-confirm");
    if (!modal) return;

    const comp = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    const nameEl = document.getElementById("close-company-name-display");
    if (nameEl && comp) {
      nameEl.textContent = comp.name;
    }

    modal.classList.add("show");
    modal.style.display = "flex";
  }

  openPlaceholderModal(sub) {
    const modal = document.getElementById("modal-feature-placeholder");
    if (modal) {
      const titleEl = document.getElementById("placeholder-modal-title");
      const headEl = document.getElementById("placeholder-modal-heading");
      const descEl = document.getElementById("placeholder-modal-desc");
      const iconEl = document.getElementById("placeholder-modal-icon");

      if (titleEl) titleEl.textContent = sub.label;
      if (headEl) headEl.textContent = sub.label;
      if (descEl) descEl.textContent = sub.info || `${sub.label} is scheduled in the Alpha Billing enterprise module roadmap. The navigation architecture has been safely initialized.`;
      if (iconEl && sub.icon) {
        iconEl.innerHTML = window.getLucideIcon(sub.icon, "", 28);
      }

      modal.classList.add("show");
      modal.style.display = "flex";
    }

    if (typeof window.showToast === "function") {
      window.showToast(`${sub.label}: Module framework initialized.`);
    }
  }

  updateBreadcrumb(subLabel) {
    const breadcrumbEl = document.getElementById("dashboard-breadcrumb");
    if (breadcrumbEl) {
      breadcrumbEl.innerHTML = `Alpha Billing &rsaquo; ${this.activeSectionId.toUpperCase()} &rsaquo; <strong>${subLabel}</strong>`;
    }
  }

  toggleCollapse() {
    this.setCollapsed(!this.isCollapsed);
  }

  setCollapsed(collapsed) {
    this.isCollapsed = collapsed;
    localStorage.setItem("alpha_sidebar_collapsed", collapsed ? "true" : "false");

    if (this.sidebarEl) {
      this.sidebarEl.classList.toggle("collapsed", collapsed);
    }
    this.updateToggleButtonIcon(collapsed);

    if (collapsed && this.flyoutEl) {
      this.flyoutEl.style.display = "none";
    }
  }

  updateToggleButtonIcon(collapsed) {
    const toggleBtn = document.getElementById("btn-sidebar-toggle");
    if (toggleBtn) {
      toggleBtn.innerHTML = collapsed 
        ? window.getLucideIcon("panelLeftOpen", "toggle-icon", 16)
        : window.getLucideIcon("panelLeftClose", "toggle-icon", 16);
      toggleBtn.title = collapsed ? "Expand Sidebar (Ctrl+B)" : "Collapse Sidebar (Ctrl+B)";
    }
  }

  showCollapsedFlyout(section, parentBtn) {
    if (!this.flyoutEl) return;
    const rect = parentBtn.getBoundingClientRect();
    
    let html = `<div class="flyout-header">${section.label}</div>`;
    section.submenus.forEach(sub => {
      const iconHtml = sub.icon ? window.getLucideIcon(sub.icon, "", 14) : "";
      html += `
        <button type="button" class="dropdown-item-btn ${this.activeSubmenuId === sub.id ? 'selected' : ''}" data-flyout-sub="${sub.id}">
          <span style="display:flex; align-items:center; gap:8px;">
            ${iconHtml}
            <span>${sub.label}</span>
          </span>
          ${sub.badge ? `<span class="status-pill status-pill-neutral" style="margin-left:auto;">${sub.badge}</span>` : ''}
        </button>
      `;
    });

    this.flyoutEl.innerHTML = html;
    this.flyoutEl.style.top = `${rect.top}px`;
    this.flyoutEl.style.display = "flex";

    // Bind clicks
    this.flyoutEl.querySelectorAll("[data-flyout-sub]").forEach(btn => {
      btn.addEventListener("click", () => {
        const subId = btn.getAttribute("data-flyout-sub");
        const sub = section.submenus.find(s => s.id === subId);
        if (sub) {
          this.selectSubmenu(section.id, sub);
          this.flyoutEl.style.display = "none";
        }
      });
    });

    this.flyoutEl.onmouseenter = () => clearTimeout(this.hideFlyoutTimer);
    this.flyoutEl.onmouseleave = () => this.scheduleHideFlyout();
  }

  scheduleHideFlyout() {
    this.hideFlyoutTimer = setTimeout(() => {
      if (this.flyoutEl) this.flyoutEl.style.display = "none";
    }, 200);
  }

  closeMobileDrawer() {
    if (this.sidebarEl) this.sidebarEl.classList.remove("mobile-open");
    const backdrop = document.getElementById("alpha-backdrop");
    if (backdrop) backdrop.classList.remove("active");
  }

  bindKeyboardNavigation() {
    document.addEventListener("keydown", (e) => {
      // Toggle sidebar shortcut: Ctrl+B
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        this.toggleCollapse();
      }
    });
  }
}

window.SidebarNavigation = new SidebarNavigationManager();
