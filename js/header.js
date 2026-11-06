/**
 * ALPHA BILLING - Top Header System
 * Manages Page Title, Breadcrumbs, Company Selector, Branch Selector,
 * Global Search trigger, Notifications Tray, Zoom, and User Profile Menu.
 */

class HeaderManager {
  constructor() {
    this.activeDropdown = null;
    this.notifications = [
      { id: "notif-1", type: "warning", title: "Low Stock Alert", desc: "3 items are below minimum reorder levels", time: "10m ago", action: "low-stock" },
      { id: "notif-2", type: "success", title: "Daily Backup Created", desc: "Automated snapshot verified cleanly", time: "1h ago", action: "backup" },
      { id: "notif-3", type: "info", title: "GSTR-1 Summary Ready", desc: "Monthly tax reports ready for review", time: "3h ago", action: "reports" }
    ];
  }

  init() {
    this.populateHeaderIcons();
    this.bindContextDropdowns();
    this.bindNotifications();
    this.bindUserProfileMenu();
    this.bindZoomControls();
    this.bindMobileToggle();
    this.updateContextDisplays();

    // Listen to BusinessContext changes
    if (window.BusinessContext) {
      window.BusinessContext.on("context-changed", () => {
        this.updateContextDisplays();
      });
    }

    // Close any open dropdown on click outside
    document.addEventListener("click", (e) => {
      if (!e.target.closest(".context-selector-pill") && 
          !e.target.closest(".header-icon-btn") && 
          !e.target.closest(".header-user-btn") && 
          !e.target.closest(".alpha-dropdown-menu")) {
        this.closeAllDropdowns();
      }
    });
  }

  populateHeaderIcons() {
    const mobBtn = document.getElementById("btn-mobile-menu-toggle");
    if (mobBtn) mobBtn.innerHTML = window.getLucideIcon("menu", "", 18);

    const logoutBtn = document.getElementById("btn-sidebar-logout");
    if (logoutBtn) logoutBtn.innerHTML = window.getLucideIcon("logOut", "", 16);

    const compBtn = document.getElementById("btn-header-company");
    if (compBtn) {
      const iconEl = compBtn.querySelector(".context-icon");
      if (iconEl) iconEl.innerHTML = window.getLucideIcon("building", "", 15);
      const chevEl = compBtn.querySelector(".context-chevron");
      if (chevEl) chevEl.innerHTML = window.getLucideIcon("chevronDown", "", 13);
    }

    const branchBtn = document.getElementById("btn-header-branch");
    if (branchBtn) {
      const iconEl = branchBtn.querySelector(".context-icon");
      if (iconEl) iconEl.innerHTML = window.getLucideIcon("branch", "", 15);
      const chevEl = branchBtn.querySelector(".context-chevron");
      if (chevEl) chevEl.innerHTML = window.getLucideIcon("chevronDown", "", 13);
    }

    const searchBtn = document.getElementById("btn-trigger-global-search");
    if (searchBtn) {
      const iconWrap = searchBtn.querySelector(".search-icon-wrap");
      if (iconWrap) iconWrap.innerHTML = window.getLucideIcon("search", "", 15);
    }

    const notifBtn = document.getElementById("btn-header-notifications");
    if (notifBtn) {
      const iconWrap = notifBtn.querySelector(".notif-icon-wrap");
      if (iconWrap) iconWrap.innerHTML = window.getLucideIcon("bell", "", 16);
    }

    const settingsBtn = document.getElementById("btn-header-settings");
    if (settingsBtn) {
      settingsBtn.innerHTML = window.getLucideIcon("settings", "", 16);
      settingsBtn.addEventListener("click", () => {
        if (typeof window.openModal === "function") window.openModal("modal-config");
      });
    }

    const userBtn = document.getElementById("btn-header-user");
    if (userBtn) {
      const chevEl = userBtn.querySelector(".user-chevron");
      if (chevEl) chevEl.innerHTML = window.getLucideIcon("chevronDown", "", 12);
    }
  }

  updateContextDisplays() {
    if (!window.BusinessContext) return;
    const comp = window.BusinessContext.getActiveCompany();
    const branch = window.BusinessContext.getActiveBranch();

    const compValEl = document.getElementById("header-company-val");
    if (compValEl && comp) {
      compValEl.textContent = `${comp.name.substring(0, 24)}${comp.name.length > 24 ? "..." : ""} (${comp.code})`;
      compValEl.title = `${comp.name} [${comp.code}]`;
    }

    const branchValEl = document.getElementById("header-branch-val");
    if (branchValEl && branch) {
      branchValEl.textContent = branch.name;
      branchValEl.title = branch.name;
    }
  }

  bindContextDropdowns() {
    // 1. Company Selector
    const compBtn = document.getElementById("btn-header-company");
    const compMenu = document.getElementById("dropdown-header-company");
    if (compBtn && compMenu) {
      compBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleDropdown(compMenu, () => this.renderCompanyDropdownList(compMenu));
      });
    }

    // 2. Branch Selector
    const branchBtn = document.getElementById("btn-header-branch");
    const branchMenu = document.getElementById("dropdown-header-branch");
    if (branchBtn && branchMenu) {
      branchBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleDropdown(branchMenu, () => this.renderBranchDropdownList(branchMenu));
      });
    }
  }

  renderCompanyDropdownList(menuEl) {
    if (!window.BusinessContext) return;
    const companies = window.BusinessContext.getCompanies();
    const active = window.BusinessContext.getActiveCompany();

    let html = `
      <div class="dropdown-header-title">Active Company / Entity</div>
      <div style="padding: 4px 6px 6px;">
        <input type="text" id="input-dropdown-filter-company" placeholder="Search company..." style="width:100%; padding: 6px 10px; font-size:12px; border:1px solid var(--alpha-border-default); border-radius:4px; outline:none;" />
      </div>
      <div id="company-dropdown-scroll" style="max-height: 200px; overflow-y:auto; display:flex; flex-direction:column; gap:2px;">
    `;

    companies.forEach(c => {
      const isSel = active && active.id === c.id;
      html += `
        <button type="button" class="dropdown-item-btn ${isSel ? 'selected' : ''}" data-company-id="${c.id}">
          <span style="font-weight:700; color:var(--alpha-brand-primary);">${c.code}</span>
          <div style="display:flex; flex-direction:column; min-width:0;">
            <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis; font-weight:${isSel ? '700':'500'};">${c.name}</span>
            <span style="font-size:10.5px; color:var(--alpha-text-muted);">GSTIN: ${c.taxNo || 'Unregistered'}</span>
          </div>
          ${isSel ? '<span style="margin-left:auto; color:var(--alpha-brand-primary); font-weight:bold;">&check;</span>' : ''}
        </button>
      `;
    });

    html += `
      </div>
      <div class="dropdown-divider"></div>
      <button type="button" class="dropdown-item-btn" id="btn-dropdown-new-company" style="color:var(--alpha-brand-primary); font-weight:600;">
        <span>+ Add New Company</span>
      </button>
    `;

    menuEl.innerHTML = html;

    // Bind item selection
    menuEl.querySelectorAll("[data-company-id]").forEach(btn => {
      btn.addEventListener("click", () => {
        const cid = btn.getAttribute("data-company-id");
        window.BusinessContext.setActiveCompany(cid);
        this.closeAllDropdowns();
        window.showToast(`Switched active context to ${window.BusinessContext.getActiveCompany().name}`);
      });
    });

    // Filter search
    const filterInput = menuEl.querySelector("#input-dropdown-filter-company");
    if (filterInput) {
      filterInput.addEventListener("input", (e) => {
        const q = e.target.value.toLowerCase();
        menuEl.querySelectorAll("[data-company-id]").forEach(btn => {
          const txt = btn.textContent.toLowerCase();
          btn.style.display = txt.includes(q) ? "flex" : "none";
        });
      });
      setTimeout(() => filterInput.focus(), 50);
    }

    // New Company Modal trigger
    const newCompBtn = menuEl.querySelector("#btn-dropdown-new-company");
    if (newCompBtn) {
      newCompBtn.addEventListener("click", () => {
        this.closeAllDropdowns();
        if (typeof window.openModal === "function") window.openModal("modal-create-company");
      });
    }
  }

  renderBranchDropdownList(menuEl) {
    if (!window.BusinessContext) return;
    const branches = window.BusinessContext.getBranches();
    const activeBranch = window.BusinessContext.getActiveBranch();

    let html = `
      <div class="dropdown-header-title">Select Operational Branch / Godown</div>
      <div style="max-height: 200px; overflow-y:auto; display:flex; flex-direction:column; gap:2px;">
    `;

    if (branches.length === 0) {
      html += `<div style="padding:10px; font-size:12px; color:var(--alpha-text-muted);">No secondary branches configured.</div>`;
    } else {
      branches.forEach(b => {
        const isSel = activeBranch && activeBranch.id === b.id;
        html += `
          <button type="button" class="dropdown-item-btn ${isSel ? 'selected' : ''}" data-branch-id="${b.id}">
            <span style="font-weight:700; color:var(--alpha-text-muted); font-size:11px;">${b.code}</span>
            <span>${b.name}</span>
            ${b.isDefault ? '<span class="status-pill status-pill-neutral" style="margin-left:auto; font-size:9.5px;">Default</span>' : ''}
            ${isSel ? '<span style="margin-left:auto; color:var(--alpha-brand-primary); font-weight:bold;">&check;</span>' : ''}
          </button>
        `;
      });
    }

    html += `</div>`;
    menuEl.innerHTML = html;

    menuEl.querySelectorAll("[data-branch-id]").forEach(btn => {
      btn.addEventListener("click", () => {
        const bid = btn.getAttribute("data-branch-id");
        window.BusinessContext.setActiveBranch(bid);
        this.closeAllDropdowns();
        window.showToast(`Switched operational branch to ${window.BusinessContext.getActiveBranch().name}`);
      });
    });
  }

  bindNotifications() {
    const notifBtn = document.getElementById("btn-header-notifications");
    const notifMenu = document.getElementById("dropdown-header-notifications");
    if (!notifBtn || !notifMenu) return;

    notifBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleDropdown(notifMenu, () => this.renderNotificationsList(notifMenu));
    });
  }

  renderNotificationsList(menuEl) {
    let html = `
      <div class="card-header-clean" style="padding: 10px 14px;">
        <span class="card-title" style="font-size:13px;">Notifications</span>
        <span class="status-pill status-pill-info">${this.notifications.length} Unread</span>
      </div>
      <div style="max-height: 280px; overflow-y:auto; display:flex; flex-direction:column;">
    `;

    this.notifications.forEach(n => {
      let iconColor = "var(--alpha-brand-primary)";
      if (n.type === "warning") iconColor = "var(--alpha-warning)";
      if (n.type === "success") iconColor = "var(--alpha-success)";

      html += `
        <div class="dropdown-item-btn" style="flex-direction:column; align-items:flex-start; gap:3px; padding:10px 14px; border-bottom:1px solid var(--alpha-border-subtle); cursor:pointer;" data-notif-action="${n.action}">
          <div style="display:flex; align-items:center; justify-content:space-between; width:100%;">
            <strong style="font-size:12.5px; color:${iconColor};">${n.title}</strong>
            <span style="font-size:10.5px; color:var(--alpha-text-muted);">${n.time}</span>
          </div>
          <span style="font-size:12px; color:var(--alpha-text-secondary);">${n.desc}</span>
        </div>
      `;
    });

    html += `
      </div>
      <div style="padding: 8px 12px; text-align:center; border-top:1px solid var(--alpha-border-default);">
        <button type="button" class="btn-alpha btn-alpha-subtle btn-alpha-sm" id="btn-clear-notifs" style="width:100%;">Mark All as Read</button>
      </div>
    `;

    menuEl.innerHTML = html;

    menuEl.querySelectorAll("[data-notif-action]").forEach(el => {
      el.addEventListener("click", () => {
        const act = el.getAttribute("data-notif-action");
        this.closeAllDropdowns();
        if (act === "low-stock" && typeof window.openModal === "function") window.openModal("modal-low-stock");
        else if (act === "backup" && typeof window.openModal === "function") window.openModal("modal-backup");
        else if (act === "reports" && typeof window.openModal === "function") window.openModal("modal-reports");
      });
    });

    const clearBtn = menuEl.querySelector("#btn-clear-notifs");
    if (clearBtn) {
      clearBtn.addEventListener("click", () => {
        this.notifications = [];
        const badge = document.getElementById("header-notif-badge");
        if (badge) badge.style.display = "none";
        this.closeAllDropdowns();
        window.showToast("All notifications cleared.");
      });
    }
  }

  bindUserProfileMenu() {
    const userBtn = document.getElementById("btn-header-user");
    const userMenu = document.getElementById("dropdown-header-user");
    if (!userBtn || !userMenu) return;

    userBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this.toggleDropdown(userMenu, () => {
        userMenu.innerHTML = `
          <div style="padding: 10px 14px; border-bottom: 1px solid var(--alpha-border-default);">
            <div style="font-size: 13.5px; font-weight: 700; color: var(--alpha-text-primary);">Administrator</div>
            <div style="font-size: 11px; color: var(--alpha-text-muted);">admin@alphabilling.local</div>
            <span class="status-pill status-pill-success" style="margin-top: 6px;">Super Admin</span>
          </div>
          <button type="button" class="dropdown-item-btn" id="btn-user-settings">
            <span>Settings & Preferences</span>
          </button>
          <button type="button" class="dropdown-item-btn" id="btn-user-shortcuts">
            <span>Keyboard Shortcuts (F1-F12)</span>
          </button>
          <div class="dropdown-divider"></div>
          <button type="button" class="dropdown-item-btn" id="btn-user-logout" style="color:var(--alpha-danger);">
            <span>Sign Out Session</span>
          </button>
        `;

        userMenu.querySelector("#btn-user-settings")?.addEventListener("click", () => {
          this.closeAllDropdowns();
          if (typeof window.openModal === "function") window.openModal("modal-config");
        });

        userMenu.querySelector("#btn-user-shortcuts")?.addEventListener("click", () => {
          this.closeAllDropdowns();
          if (window.GlobalSearchManager) window.GlobalSearchManager.openShortcutsHelp();
        });

        userMenu.querySelector("#btn-user-logout")?.addEventListener("click", () => {
          this.closeAllDropdowns();
          window.showToast("Signing out of Alpha Billing...");
          setTimeout(() => {
            if (typeof window.showScreen === "function") window.showScreen("view-login");
          }, 400);
        });
      });
    });
  }

  bindZoomControls() {
    if (window.ZoomController && typeof window.ZoomController.bindControls === "function") {
      window.ZoomController.bindControls();
    } else {
      const zoomInBtn = document.getElementById("btn-zoom-in");
      const zoomOutBtn = document.getElementById("btn-zoom-out");
      if (zoomInBtn && !zoomInBtn.dataset.zoomBound) {
        zoomInBtn.dataset.zoomBound = "true";
        zoomInBtn.addEventListener("click", () => {
          if (window.ZoomController) {
            window.ZoomController.zoomIn();
          } else if (typeof window.applyZoom === "function") {
            const cur = typeof window.uiZoom !== "undefined" ? window.uiZoom : (parseFloat(localStorage.getItem("alpha_ui_zoom") || "1.0"));
            window.applyZoom(Math.round((cur + 0.10) * 10) / 10);
          }
        });
      }
      if (zoomOutBtn && !zoomOutBtn.dataset.zoomBound) {
        zoomOutBtn.dataset.zoomBound = "true";
        zoomOutBtn.addEventListener("click", () => {
          if (window.ZoomController) {
            window.ZoomController.zoomOut();
          } else if (typeof window.applyZoom === "function") {
            const cur = typeof window.uiZoom !== "undefined" ? window.uiZoom : (parseFloat(localStorage.getItem("alpha_ui_zoom") || "1.0"));
            window.applyZoom(Math.round((cur - 0.10) * 10) / 10);
          }
        });
      }
    }
  }

  bindMobileToggle() {
    const mobBtn = document.getElementById("btn-mobile-menu-toggle");
    const sidebar = document.getElementById("alpha-sidebar");
    const backdrop = document.getElementById("alpha-backdrop");

    if (mobBtn && sidebar) {
      mobBtn.addEventListener("click", () => {
        sidebar.classList.toggle("mobile-open");
        if (backdrop) backdrop.classList.toggle("active", sidebar.classList.contains("mobile-open"));
      });
    }

    if (backdrop && sidebar) {
      backdrop.addEventListener("click", () => {
        sidebar.classList.remove("mobile-open");
        backdrop.classList.remove("active");
      });
    }
  }

  toggleDropdown(menuEl, renderFn) {
    const isOpen = menuEl.classList.contains("active");
    this.closeAllDropdowns();
    if (!isOpen) {
      if (typeof renderFn === "function") renderFn();
      menuEl.classList.add("active");
      this.activeDropdown = menuEl;
    }
  }

  closeAllDropdowns() {
    document.querySelectorAll(".alpha-dropdown-menu").forEach(m => m.classList.remove("active"));
    this.activeDropdown = null;
  }

  openCompanySwitcher() {
    const compBtn = document.getElementById("btn-header-company");
    if (compBtn) compBtn.click();
  }

  openBranchSwitcher() {
    const branchBtn = document.getElementById("btn-header-branch");
    if (branchBtn) branchBtn.click();
  }
}

window.HeaderManager = new HeaderManager();
