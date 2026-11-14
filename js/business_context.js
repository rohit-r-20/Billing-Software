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

function isCanonicalUUID(id) {
  if (typeof id !== "string") return false;
  if (id.length !== 36 || id !== id.trim()) return false;
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
}

class BusinessContextManager {
  constructor() {
    this.AuthState = AuthState;
    this.authState = AuthState.UNAUTHENTICATED;
    this.isCanonicalUUID = isCanonicalUUID;
    this.listeners = new Map();

    // Companies catalog: populated exclusively from verified backend session or sanitized list
    this.companies = [];

    // Initial Authentication & Context State (Clean Startup: Not Authenticated)
    this.isAuthenticated = false;
    this.activeCompanyId = null;
    this.activeBranchId = null;
    this.currentUser = null;
  }

  init() {
    // Clean Startup: unauthenticated mode. Awaiting backend session restoration or user login.
    this.authState = AuthState.UNAUTHENTICATED;
    this.isAuthenticated = false;
    this.activeCompanyId = null;
    this.activeBranchId = null;
    this.currentUser = null;
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
    if (!sessionData || typeof sessionData !== "object") {
      console.error("[BusinessContext] setAuthenticatedSession rejected: sessionData must be an object.");
      this.clearAuthenticatedSession("invalid_session_contract");
      return false;
    }

    // 1. Strict Company Validation (fail-closed, canonical UUID required)
    const comp = sessionData.company;
    if (!comp || typeof comp !== "object" || !isCanonicalUUID(comp.id)) {
      console.error("[BusinessContext] setAuthenticatedSession rejected: Valid company context with canonical UUID is required.");
      this.clearAuthenticatedSession("invalid_company_context");
      return false;
    }

    // 2. Strict User Validation (fail-closed, canonical UUID and valid role required)
    const user = sessionData.user;
    if (!user || typeof user !== "object" || !isCanonicalUUID(user.id)) {
      console.error("[BusinessContext] setAuthenticatedSession rejected: Valid user context with user UUID is required.");
      this.clearAuthenticatedSession("invalid_user_context");
      return false;
    }

    if (!user.role || typeof user.role !== "string" || !user.role.trim()) {
      console.error("[BusinessContext] setAuthenticatedSession rejected: Valid user role is required.");
      this.clearAuthenticatedSession("invalid_user_role");
      return false;
    }

    // 3. Strict Branch Validation (fail-closed, canonical UUID required)
    const branch = sessionData.branch;
    if (!branch || typeof branch !== "object" || !isCanonicalUUID(branch.id)) {
      console.error("[BusinessContext] setAuthenticatedSession rejected: Valid branch context with branch UUID is required.");
      this.clearAuthenticatedSession("invalid_branch_context");
      return false;
    }

    this.authState = AuthState.AUTHENTICATED;
    this.isAuthenticated = true;

    // Dynamic User Identity
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
      id: user.id.trim(),
      username: (user.username || "").trim(),
      displayName: (user.displayName || user.username || "").trim(),
      role: user.role.trim(),
      avatarInitials: initials,
      status: "online"
    };

    // Dynamic Company Context
    const cleanComp = {
      id: comp.id.trim(),
      code: (comp.code || "").trim(),
      name: (comp.name || "").trim(),
      finYear: comp.finYear || comp.fin_year || "2026-2027",
      taxNo: comp.taxNo || comp.gstin || "",
      state: comp.state || "",
      branches: [branch]
    };

    this.companies = [cleanComp];
    this.activeCompanyId = cleanComp.id;

    // Dynamic Branch Context
    this.activeBranchId = branch.id.trim();

    // Legacy compatibility global reference
    window.activeCompany = {
      id: cleanComp.id,
      code: cleanComp.code,
      name: cleanComp.name,
      fin_year: cleanComp.finYear
    };

    console.log(`[BusinessContext] Authenticated: ${this.currentUser.displayName} (${this.currentUser.role}) @ ${cleanComp.name}`);
    this.emit("auth-state-changed", {
      state: this.authState,
      isAuthenticated: true,
      user: this.currentUser,
      company: cleanComp,
      branch: branch
    });
    this.emit("auth-changed", { 
      isAuthenticated: true, 
      user: this.currentUser, 
      company: cleanComp, 
      branch: branch 
    });
    this.emit("context-changed", { company: cleanComp, branch: branch });
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
