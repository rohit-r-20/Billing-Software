/**
 * ALPHA BILLING - Multi-Business & Branch Context Management
 * Manages active Company, Branch, Financial Year, and User state.
 * Prevents cross-contamination between businesses.
 */

class BusinessContextManager {
  constructor() {
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

    // Current State
    this.activeCompanyId = localStorage.getItem("alpha_active_company_id") || "COMP0001";
    this.activeBranchId = localStorage.getItem("alpha_active_branch_id") || "BR-HQ";
    this.currentUser = {
      username: "Admin",
      displayName: "Administrator",
      role: "Super Administrator",
      avatarInitials: "AD",
      status: "online"
    };
  }

  init() {
    // Sync with backend if available
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

    // Ensure active company exists
    if (!this.getActiveCompany()) {
      this.activeCompanyId = this.companies[0].id;
    }

    // Ensure active branch exists
    if (!this.getActiveBranch()) {
      const branches = this.getBranches();
      this.activeBranchId = branches.length > 0 ? branches[0].id : "DEFAULT";
    }

    console.log(`[BusinessContext] Active Company: ${this.getActiveCompany().name} | Branch: ${this.getActiveBranch() ? this.getActiveBranch().name : "None"}`);
  }

  getCompanies() {
    return [...this.companies];
  }

  getActiveCompany() {
    return this.companies.find(c => c.id === this.activeCompanyId) || this.companies[0];
  }

  setActiveCompany(companyId) {
    const target = this.companies.find(c => c.id === companyId || c.code === companyId);
    if (!target) {
      console.error(`[BusinessContext] Company not found: ${companyId}`);
      return false;
    }

    if (this.activeCompanyId !== target.id) {
      this.activeCompanyId = target.id;
      localStorage.setItem("alpha_active_company_id", target.id);

      // Default branch of new company
      const defaultBranch = (target.branches && target.branches.find(b => b.isDefault)) || (target.branches && target.branches[0]);
      this.activeBranchId = defaultBranch ? defaultBranch.id : "DEFAULT";
      localStorage.setItem("alpha_active_branch_id", this.activeBranchId);

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
    const branches = this.getBranches();
    return branches.find(b => b.id === this.activeBranchId) || branches[0] || null;
  }

  setActiveBranch(branchId) {
    const branches = this.getBranches();
    const target = branches.find(b => b.id === branchId || b.code === branchId);
    if (!target) {
      console.error(`[BusinessContext] Branch not found: ${branchId}`);
      return false;
    }

    if (this.activeBranchId !== target.id) {
      this.activeBranchId = target.id;
      localStorage.setItem("alpha_active_branch_id", target.id);
      this.emit("branch-changed", target);
      this.emit("context-changed", { company: this.getActiveCompany(), branch: target });
    }
    return true;
  }

  getCurrentUser() {
    return { ...this.currentUser };
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
