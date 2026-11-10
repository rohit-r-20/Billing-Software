/**
 * ALPHA BILLING - Multi-Business & Branch Context Management
 * Manages active Company, Branch, Financial Year, and User state.
 * Prevents cross-contamination between businesses.
 */

const AuthState = Object.freeze({
  UNAUTHENTICATED: "UNAUTHENTICATED",
  AUTHENTICATING: "AUTHENTICATING",
  AUTHENTICATED: "AUTHENTICATED",
  SESSION_EXPIRED: "SESSION_EXPIRED"
});

class BusinessContextManager {
  constructor() {
    this.AuthState = AuthState;
    this.authState = AuthState.UNAUTHENTICATED;
    this.listeners = new Map();

    // Default seeded companies
    this.companies = [
      {
        id: "COMP0001",
        code: "COMP0001",
        name: "ANTI MATRIX RETAIL & WHOLESALE",
        taxNo: "33AAAPL1234F1Z1",
        state: "Tamilnadu",
        finYear: "2026-2027",
        address: "142 Commercial Axis, Main Bazaar, Erode, Tamilnadu - 638001",
        branches: [
          { id: "BR-HQ", code: "HQ", name: "Main Branch (HQ)", isDefault: true },
          { id: "BR-W1", code: "WH1", name: "Central Godown / Warehouse", isDefault: false },
          { id: "BR-R1", code: "RT1", name: "Retail Storefront #1", isDefault: false }
        ]
      },
      {
        id: "COMP0002",
        code: "COMP0002",
        name: "ALPHA DISTRIBUTORS & LOGISTICS",
        taxNo: "33BBBPX5678G2Z3",
        state: "Tamilnadu",
        finYear: "2026-2027",
        address: "88 Logistics Boulevard, SIPCOT Phase 2, Coimbatore - 641014",
        branches: [
          { id: "BR-D1", code: "D1", name: "Primary Distribution Hub", isDefault: true },
          { id: "BR-D2", code: "D2", name: "Transit Hub South", isDefault: false }
        ]
      }
    ];

    // Restore any persisted updates
    try {
      const persisted = localStorage.getItem("alpha_custom_companies");
      if (persisted) {
        const parsed = JSON.parse(persisted);
        if (Array.isArray(parsed) && parsed.length > 0) {
          parsed.forEach(pc => {
            const ex = this.companies.find(c => c.id === pc.id || c.code === pc.code);
            if (ex) {
              Object.assign(ex, pc);
            } else {
              this.companies.push(pc);
            }
          });
        }
      }
    } catch (e) {
      console.warn("Could not parse persisted companies:", e);
    }

    // Initial Authentication & Context State (Clean Startup: Not Authenticated)
    this.isAuthenticated = false;
    this.activeCompanyId = null;
    this.activeBranchId = null;
    this.currentUser = null;
  }

  init() {
    // Sync company catalog with backend if available for company selection dropdown
    if (window.backend && typeof window.backend.listCompanies === "function") {
      try {
        const resStr = window.backend.listCompanies();
        const res = typeof resStr === "string" ? JSON.parse(resStr) : resStr;
        if (res && res.success && Array.isArray(res.data) && res.data.length > 0) {
          // Merge backend companies
          res.data.forEach(bc => {
            const existing = this.companies.find(c => c.id === bc.id || c.code === bc.code);
            if (!existing) {
              this.companies.push({
                id: bc.id,
                code: bc.code || bc.id,
                name: bc.name,
                taxNo: bc.taxNo || "",
                state: bc.state || "Tamilnadu",
                finYear: bc.finYear || "2026-2027",
                address: bc.address || "",
                branches: [
                  { id: `BR-${bc.code}-1`, code: "MAIN", name: "Main Branch (HQ)", isDefault: true }
                ]
              });
            }
          });
        }
      } catch (err) {
        console.warn("Could not sync companies from backend:", err);
      }
    }

    // Do NOT automatically activate company or user on startup before login
    console.log(`[BusinessContext] Initialized in unauthenticated mode. Awaiting user login.`);
  }

  getAuthState() {
    return this.authState;
  }

  setAuthenticating() {
    this.authState = AuthState.AUTHENTICATING;
    this.emit("auth-state-changed", { state: this.authState });
  }

  isAuthenticatedSession() {
    return this.authState === AuthState.AUTHENTICATED && Boolean(this.currentUser && this.activeCompanyId);
  }

  setAuthenticatedSession(sessionData) {
    if (!sessionData) return false;

    this.authState = AuthState.AUTHENTICATED;
    this.isAuthenticated = true;

    // 1. Dynamic User Identity
    const user = sessionData.user || {};
    const rawName = (user.displayName || user.username || "").trim();
    const parts = rawName.split(/\s+/).filter(Boolean);
    let initials = "--";
    if (parts.length >= 2) {
      initials = (parts[0][0] + parts[1][0]).toUpperCase();
    } else if (parts.length === 1 && parts[0].length >= 2) {
      initials = parts[0].substring(0, 2).toUpperCase();
    } else if (parts.length === 1 && parts[0].length === 1) {
      initials = parts[0].toUpperCase();
    }

    this.currentUser = {
      id: user.id || user.userId || `usr-${Date.now()}`,
      username: user.username || "User",
      displayName: user.displayName || user.username || "User",
      role: user.role || "User",
      avatarInitials: initials,
      status: "online"
    };

    // 2. Dynamic Company Context
    const comp = sessionData.company || 
      this.companies.find(c => c.id === sessionData.companyId || c.code === sessionData.companyCode) || 
      this.companies[0];
    if (comp && !this.companies.some(c => c.id === comp.id || (c.code && comp.code && c.code === comp.code))) {
      this.companies.push(comp);
    }
    this.activeCompanyId = comp ? comp.id : null;

    // 3. Dynamic Branch Context
    const branch = sessionData.branch || (comp && comp.branches ? comp.branches[0] : null);
    if (comp && branch) {
      if (!Array.isArray(comp.branches)) comp.branches = [];
      if (!comp.branches.some(b => b.id === branch.id)) {
        comp.branches.push(branch);
      }
    }
    this.activeBranchId = branch ? branch.id : null;

    // Legacy compatibility global reference
    window.activeCompany = comp ? {
      id: comp.id,
      code: comp.code,
      name: comp.name,
      fin_year: comp.finYear
    } : null;

    console.log(`[BusinessContext] Authenticated: ${this.currentUser?.displayName || "User"} (${this.currentUser?.role || "User"}) @ ${comp ? comp.name : "N/A"}`);
    this.emit("auth-state-changed", {
      state: this.authState,
      isAuthenticated: true,
      user: this.currentUser,
      company: comp,
      branch: branch
    });
    this.emit("auth-changed", { 
      isAuthenticated: true, 
      user: this.currentUser, 
      company: comp, 
      branch: branch 
    });
    this.emit("context-changed", { company: comp, branch: branch });
    return true;
  }

  clearAuthenticatedSession(reason = "logout") {
    console.log(`[BusinessContext] Clearing authenticated session (reason: ${reason}).`);
    this.authState = (reason === "session_expired" || reason === AuthState.SESSION_EXPIRED) 
      ? AuthState.SESSION_EXPIRED 
      : AuthState.UNAUTHENTICATED;
    this.isAuthenticated = false;
    this.currentUser = null;
    this.activeCompanyId = null;
    this.activeBranchId = null;
    window.activeCompany = null;

    try {
      localStorage.removeItem("alpha_active_company_id");
      localStorage.removeItem("alpha_active_branch_id");
    } catch (e) {}

    this.emit("auth-state-changed", { 
      state: this.authState, 
      reason: reason, 
      isAuthenticated: false, 
      user: null, 
      company: null, 
      branch: null 
    });
    this.emit("auth-changed", { 
      isAuthenticated: false, 
      state: this.authState, 
      reason: reason, 
      user: null, 
      company: null, 
      branch: null 
    });
    this.emit("context-changed", { company: null, branch: null });
  }

  expireSession() {
    this.clearAuthenticatedSession("session_expired");
  }

  getCompanies() {
    return [...this.companies];
  }

  getActiveCompany() {
    if (!this.isAuthenticated || !this.activeCompanyId) return null;
    return this.companies.find(c => c.id === this.activeCompanyId) || null;
  }

  setActiveCompany(companyId) {
    if (!this.isAuthenticated) {
      console.warn("[BusinessContext] Cannot switch company while unauthenticated.");
      return false;
    }
    const target = this.companies.find(c => c.id === companyId || c.code === companyId);
    if (!target) {
      console.error(`[BusinessContext] Company not found: ${companyId}`);
      return false;
    }

    if (this.activeCompanyId !== target.id) {
      this.activeCompanyId = target.id;

      // Default branch of new company
      const defaultBranch = (target.branches && target.branches.find(b => b.isDefault)) || (target.branches && target.branches[0]);
      this.activeBranchId = defaultBranch ? defaultBranch.id : "DEFAULT";

      // Also set global legacy compatibility activeCompany
      window.activeCompany = {
        id: target.id,
        code: target.code,
        name: target.name,
        fin_year: target.finYear
      };

      this.emit("company-changed", target);
      this.emit("context-changed", { company: target, branch: this.getActiveBranch() });
    }
    return true;
  }

  updateCompanyDetails(companyId, details) {
    const comp = this.companies.find(c => c.id === companyId || c.code === companyId);
    if (!comp) {
      console.error(`[BusinessContext] Cannot update, company not found: ${companyId}`);
      return false;
    }

    if (details.name) comp.name = details.name.trim();
    if (details.taxNo !== undefined) comp.taxNo = details.taxNo.trim();
    if (details.state) comp.state = details.state.trim();
    if (details.finYear) comp.finYear = details.finYear.trim();
    if (details.address !== undefined) comp.address = details.address.trim();

    // If active company, update global legacy reference as well
    if (this.activeCompanyId === comp.id) {
      window.activeCompany = {
        id: comp.id,
        code: comp.code,
        name: comp.name,
        fin_year: comp.finYear
      };
    }

    // Persist to localStorage
    try {
      localStorage.setItem("alpha_custom_companies", JSON.stringify(this.companies));
    } catch (e) {
      console.warn("Could not persist company updates:", e);
    }

    this.emit("company-changed", comp);
    this.emit("context-changed", { company: comp, branch: this.getActiveBranch() });
    return true;
  }

  closeActiveCompanySession() {
    const closedComp = this.getActiveCompany();
    console.log(`[BusinessContext] Closing active company session for: ${closedComp ? closedComp.name : "None"}`);
    this.emit("company-closed", closedComp);
    return true;
  }

  getBranches() {
    const comp = this.getActiveCompany();
    return comp && comp.branches ? [...comp.branches] : [];
  }

  getActiveBranch() {
    if (!this.isAuthenticated || !this.activeBranchId) return null;
    const branches = this.getBranches();
    return branches.find(b => b.id === this.activeBranchId) || branches[0] || null;
  }

  setActiveBranch(branchId) {
    if (!this.isAuthenticated) {
      console.warn("[BusinessContext] Cannot switch branch while unauthenticated.");
      return false;
    }
    const branches = this.getBranches();
    const target = branches.find(b => b.id === branchId || b.code === branchId);
    if (!target) {
      console.error(`[BusinessContext] Branch not found: ${branchId}`);
      return false;
    }

    if (this.activeBranchId !== target.id) {
      this.activeBranchId = target.id;
      this.emit("branch-changed", target);
      this.emit("context-changed", { company: this.getActiveCompany(), branch: target });
    }
    return true;
  }

  getCurrentUser() {
    return this.isAuthenticated && this.currentUser ? { ...this.currentUser } : null;
  }

  // Event Subscription
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  emit(event, payload) {
    const cbs = this.listeners.get(event);
    if (cbs) {
      cbs.forEach(cb => {
        try { cb(payload); } catch (e) { console.error(`Error in ${event} listener:`, e); }
      });
    }
  }
}

window.BusinessContext = new BusinessContextManager();
