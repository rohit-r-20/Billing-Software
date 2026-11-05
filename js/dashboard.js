/**
 * ALPHA BILLING - Dashboard View & Analytics Engine
 * Manages Welcome Section, 6 KPI Cards, 4 Analytics Charts,
 * Recent Activity Feeds, and Quick Actions.
 */

class DashboardManager {
  constructor() {
    this.chartPeriod = "7d";
    this.activeActivityTab = "invoices";
    this.isLiveMode = false;

    // Realistic Mock Business Datasets (clearly marked)
    this.mockData = {
      kpi: {
        todaySales: 48250.00,
        todaySalesCount: 34,
        todaySalesDelta: "+14.8%",
        todayPurchases: 24180.00,
        todayPurchasesCount: 5,
        todayPurchasesDelta: "-4.2%",
        stockValue: 482600.00,
        stockItemsCount: 142,
        lowStockCount: 3,
        receivables: 62400.00,
        receivablesOverdueCount: 8,
        payables: 38900.00,
        payablesDueCount: 4,
        todayExpenses: 3450.00,
        heldBills: 0
      },
      salesTrend: [
        { day: "Fri", label: "31 Oct", sales: 38400, purchases: 18200 },
        { day: "Sat", label: "01 Nov", sales: 52100, purchases: 22000 },
        { day: "Sun", label: "02 Nov", sales: 31200, purchases: 8400 },
        { day: "Mon", label: "03 Nov", sales: 44300, purchases: 19500 },
        { day: "Tue", label: "04 Nov", sales: 46800, purchases: 26100 },
        { day: "Wed", label: "05 Nov", sales: 48250, purchases: 24180 },
        { day: "Thu (Est)", label: "06 Nov", sales: 50400, purchases: 21000 }
      ],
      paymentSummary: [
        { method: "UPI / QR Code", amount: 21712.50, percent: 45, color: "#2563eb" },
        { method: "Cash in Counter", amount: 16887.50, percent: 35, color: "#10b981" },
        { method: "Debit / Credit Card", amount: 7237.50, percent: 15, color: "#f59e0b" },
        { method: "Customer Credit / Ledger", amount: 2412.50, percent: 5, color: "#8b5cf6" }
      ],
      recentInvoices: [
        { vchNo: "INV-2026-0842", party: "Walk-in Retail Customer", amount: 1450.00, mode: "UPI", status: "PAID", time: "11:22 AM" },
        { vchNo: "INV-2026-0841", party: "Sri Murugan Supermarket", amount: 12400.00, mode: "CASH", status: "PAID", time: "10:48 AM" },
        { vchNo: "INV-2026-0840", party: "Apex Trading Co.", amount: 8900.00, mode: "CARD", status: "PAID", time: "10:15 AM" },
        { vchNo: "INV-2026-0839", party: "Walk-in Retail Customer", amount: 620.00, mode: "CASH", status: "PAID", time: "09:40 AM" },
        { vchNo: "INV-2026-0838", party: "Lakshmi Stores", amount: 4880.00, mode: "CREDIT", status: "PENDING", time: "09:12 AM" }
      ],
      recentPurchases: [
        { vchNo: "PUR-2026-0194", supplier: "ITC Limited Distribution", amount: 14200.00, tax: 2556.00, status: "VERIFIED", time: "Today 10:30 AM" },
        { vchNo: "PUR-2026-0193", supplier: "Hindustan Unilever Ltd.", amount: 9980.00, tax: 1796.40, status: "VERIFIED", time: "Today 09:15 AM" },
        { vchNo: "PUR-2026-0192", supplier: "Dabur India Wholesale", amount: 18450.00, tax: 2214.00, status: "RECEIVED", time: "Yesterday" }
      ],
      recentPayments: [
        { vchNo: "RCP-2026-0412", party: "Sri Murugan Supermarket", amount: 12400.00, mode: "CASH", type: "COLLECTION", time: "10:48 AM" },
        { vchNo: "PAY-2026-0105", party: "Hindustan Unilever Ltd.", amount: 9980.00, mode: "NEFT", type: "PAYMENT", time: "09:30 AM" },
        { vchNo: "RCP-2026-0411", party: "Apex Trading Co.", amount: 8900.00, mode: "UPI", type: "COLLECTION", time: "10:15 AM" }
      ],
      stockAdjustments: [
        { item: "Odonil Room Air Freshener 50g", type: "DAMAGE", qty: "-2.000", reason: "Packaging damaged in transit", date: "Today" },
        { item: "Tata Salt 1kg Crystal Pure", type: "INTER-BRANCH", qty: "-25.000", reason: "Transferred to Retail Counter #1", date: "Today" },
        { item: "Fortune Sunlite Refined Oil 1L", type: "INSPECTION", qty: "+5.000", reason: "Physical audit excess found", date: "Yesterday" }
      ]
    };
  }

  init() {
    this.renderWelcome();
    this.renderKPIs();
    this.renderCharts();
    this.renderActivities();
    this.renderQuickActions();
    this.startLiveClock();

    // Listen to business context change to update context and KPIs
    if (window.BusinessContext) {
      window.BusinessContext.on("context-changed", () => {
        this.renderWelcome();
        this.renderKPIs();
      });
    }

    // Attempt to merge live DB totals if backend is available
    this.loadLiveBackendData();
  }

  startLiveClock() {
    const updateTime = () => {
      const now = new Date();
      const dateEl = document.getElementById("welcome-current-date");
      const timeEl = document.getElementById("welcome-current-time");
      
      if (dateEl) {
        const options = { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' };
        dateEl.textContent = now.toLocaleDateString("en-IN", options);
      }
      if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString("en-IN", { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
    };
    updateTime();
    setInterval(updateTime, 1000);
  }

  renderWelcome() {
    const hour = new Date().getHours();
    let greeting = "Good morning";
    if (hour >= 12 && hour < 17) greeting = "Good afternoon";
    else if (hour >= 17) greeting = "Good evening";

    const greetingHeading = document.getElementById("welcome-greeting-heading");
    if (greetingHeading) {
      const user = window.BusinessContext ? window.BusinessContext.getCurrentUser() : { displayName: "Admin" };
      greetingHeading.textContent = `${greeting}, ${user.displayName}`;
    }

    const comp = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    const branch = window.BusinessContext ? window.BusinessContext.getActiveBranch() : null;

    const ctxCompany = document.getElementById("welcome-ctx-company");
    if (ctxCompany && comp) ctxCompany.textContent = comp.name;

    const ctxBranch = document.getElementById("welcome-ctx-branch");
    if (ctxBranch && branch) ctxBranch.textContent = branch.name;

    const ctxYear = document.getElementById("welcome-ctx-year");
    if (ctxYear && comp) ctxYear.textContent = comp.finYear || "2026-2027";
  }

  renderKPIs() {
    // Populate KPI Icons
    const iconMap = [
      { id: "kpi-icon-sales", icon: "shoppingBag" },
      { id: "kpi-icon-purchases", icon: "shoppingCart" },
      { id: "kpi-icon-stock", icon: "package" },
      { id: "kpi-icon-receivables", icon: "wallet" },
      { id: "kpi-icon-payables", icon: "creditCard" },
      { id: "kpi-icon-expenses", icon: "fileText" }
    ];
    iconMap.forEach(m => {
      const el = document.getElementById(m.id);
      if (el && !el.hasChildNodes()) {
        el.innerHTML = window.getLucideIcon(m.icon, "", 16);
      }
    });

    const k = this.mockData.kpi;

    // 1. Today's Sales
    const salesEl = document.getElementById("dash-today-sales");
    if (salesEl) salesEl.textContent = `₹ ${k.todaySales.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    const salesCountEl = document.getElementById("dash-sales-count");
    if (salesCountEl) salesCountEl.textContent = `${k.todaySalesCount} Invoices`;
    const salesDeltaEl = document.getElementById("dash-sales-delta");
    if (salesDeltaEl) salesDeltaEl.textContent = k.todaySalesDelta;

    // 2. Today's Purchases
    const purEl = document.getElementById("dash-today-purchases");
    if (purEl) purEl.textContent = `₹ ${k.todayPurchases.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    const purCountEl = document.getElementById("dash-purchases-count");
    if (purCountEl) purCountEl.textContent = `${k.todayPurchasesCount} Bills`;
    const purDeltaEl = document.getElementById("dash-purchases-delta");
    if (purDeltaEl) purDeltaEl.textContent = k.todayPurchasesDelta;

    // 3. Total Stock Value
    const stockEl = document.getElementById("dash-total-stock-value");
    if (stockEl) stockEl.textContent = `₹ ${k.stockValue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    const stockCountEl = document.getElementById("dash-stock-count");
    if (stockCountEl) stockCountEl.textContent = `${k.stockItemsCount} Active SKUs`;
    
    // Compatibility ID for test suite: dash-low-stock
    const lowStockCompat = document.getElementById("dash-low-stock");
    if (lowStockCompat) lowStockCompat.textContent = `${k.lowStockCount} items`;

    // 4. Outstanding Receivables
    const recvEl = document.getElementById("dash-receivables");
    if (recvEl) recvEl.textContent = `₹ ${k.receivables.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    const recvCountEl = document.getElementById("dash-receivables-count");
    if (recvCountEl) recvCountEl.textContent = `${k.receivablesOverdueCount} Overdue`;

    // 5. Outstanding Payables
    const payEl = document.getElementById("dash-payables");
    if (payEl) payEl.textContent = `₹ ${k.payables.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
    const payCountEl = document.getElementById("dash-payables-count");
    if (payCountEl) payCountEl.textContent = `${k.payablesDueCount} Suppliers Due`;

    // 6. Today's Expenses
    const expEl = document.getElementById("dash-today-expenses");
    if (expEl) expEl.textContent = `₹ ${k.todayExpenses.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;

    // Compatibility ID for test suite: dash-held-bills
    const heldCompat = document.getElementById("dash-held-bills");
    if (heldCompat) heldCompat.textContent = `${k.heldBills} held`;
  }

  renderCharts() {
    this.renderSalesTrendChart();
    this.renderPaymentSummary();
    this.renderRevenueExpenseChart();
  }

  renderSalesTrendChart() {
    const container = document.getElementById("chart-sales-trend-container");
    if (!container) return;

    const data = this.mockData.salesTrend;
    const maxVal = Math.max(...data.map(d => Math.max(d.sales, d.purchases))) * 1.15;
    const chartHeight = 180;
    const chartWidth = 500;
    const paddingX = 40;
    const paddingY = 25;
    const usableW = chartWidth - paddingX * 2;
    const usableH = chartHeight - paddingY * 2;
    const barGroupW = usableW / data.length;
    const barW = Math.min(22, barGroupW * 0.38);

    let barsHtml = "";
    let gridHtml = "";

    // Horizontal Grid Lines & Y-Labels
    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const y = paddingY + (usableH / gridSteps) * i;
      const val = Math.round((maxVal - (maxVal / gridSteps) * i) / 1000);
      gridHtml += `
        <line x1="${paddingX}" y1="${y}" x2="${chartWidth - paddingX}" y2="${y}" class="chart-grid-line" />
        <text x="${paddingX - 8}" y="${y + 4}" text-anchor="end" class="chart-axis-label">₹${val}k</text>
      `;
    }

    // Bars for Sales & Purchases
    data.forEach((d, idx) => {
      const groupX = paddingX + idx * barGroupW + (barGroupW - barW * 2 - 4) / 2;
      
      // Sales Bar
      const salesH = (d.sales / maxVal) * usableH;
      const salesY = paddingY + (usableH - salesH);

      // Purchases Bar
      const purH = (d.purchases / maxVal) * usableH;
      const purY = paddingY + (usableH - purH);

      barsHtml += `
        <!-- Sales Bar -->
        <rect x="${groupX}" y="${salesY}" width="${barW}" height="${salesH}" rx="3" fill="#2563eb" class="chart-bar">
          <title>${d.label} Sales: ₹${d.sales.toLocaleString('en-IN')}</title>
        </rect>
        <!-- Purchase Bar -->
        <rect x="${groupX + barW + 4}" y="${purY}" width="${barW}" height="${purH}" rx="3" fill="#93c5fd" class="chart-bar">
          <title>${d.label} Purchases: ₹${d.purchases.toLocaleString('en-IN')}</title>
        </rect>
        <!-- X-Axis Label -->
        <text x="${groupX + barW + 2}" y="${chartHeight - 6}" text-anchor="middle" class="chart-axis-label">${d.day}</text>
      `;
    });

    container.innerHTML = `
      <svg class="alpha-svg-chart" viewBox="0 0 ${chartWidth} ${chartHeight}">
        ${gridHtml}
        ${barsHtml}
      </svg>
    `;
  }

  renderPaymentSummary() {
    const container = document.getElementById("chart-payment-summary-container");
    if (!container) return;

    let html = `<div class="payment-summary-box">`;
    this.mockData.paymentSummary.forEach(p => {
      html += `
        <div class="payment-progress-item">
          <div class="payment-item-header">
            <span class="payment-item-name">
              <span class="payment-method-dot" style="background-color: ${p.color};"></span>
              ${p.method}
            </span>
            <span class="payment-item-val">₹ ${p.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })} (${p.percent}%)</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${p.percent}%; background-color: ${p.color};"></div>
          </div>
        </div>
      `;
    });
    html += `</div>`;
    container.innerHTML = html;
  }

  renderRevenueExpenseChart() {
    const container = document.getElementById("chart-revenue-expense-container");
    if (!container) return;

    const data = [
      { month: "Aug", revenue: 840000, cost: 580000, expenses: 62000 },
      { month: "Sep", revenue: 920000, cost: 630000, expenses: 68000 },
      { month: "Oct", revenue: 1150000, cost: 790000, expenses: 74000 },
      { month: "Nov (Est)", revenue: 1220000, cost: 830000, expenses: 79000 }
    ];

    const maxVal = 1400000;
    const chartHeight = 180;
    const chartWidth = 500;
    const paddingX = 40;
    const paddingY = 25;
    const usableW = chartWidth - paddingX * 2;
    const usableH = chartHeight - paddingY * 2;
    const stepW = usableW / data.length;

    let gridHtml = "";
    for (let i = 0; i <= 3; i++) {
      const y = paddingY + (usableH / 3) * i;
      const v = Math.round((maxVal - (maxVal / 3) * i) / 100000);
      gridHtml += `
        <line x1="${paddingX}" y1="${y}" x2="${chartWidth - paddingX}" y2="${y}" class="chart-grid-line" />
        <text x="${paddingX - 8}" y="${y + 4}" text-anchor="end" class="chart-axis-label">₹${v}L</text>
      `;
    }

    let itemsHtml = "";
    data.forEach((d, idx) => {
      const cx = paddingX + idx * stepW + stepW / 2;
      const revH = (d.revenue / maxVal) * usableH;
      const revY = paddingY + (usableH - revH);
      const costH = (d.cost / maxVal) * usableH;
      const costY = paddingY + (usableH - costH);

      itemsHtml += `
        <rect x="${cx - 18}" y="${revY}" width="16" height="${revH}" rx="3" fill="#10b981" class="chart-bar">
          <title>${d.month} Gross Revenue: ₹${d.revenue.toLocaleString('en-IN')}</title>
        </rect>
        <rect x="${cx + 2}" y="${costY}" width="16" height="${costH}" rx="3" fill="#f59e0b" class="chart-bar">
          <title>${d.month} Cost of Sales: ₹${d.cost.toLocaleString('en-IN')}</title>
        </rect>
        <text x="${cx}" y="${chartHeight - 6}" text-anchor="middle" class="chart-axis-label">${d.month}</text>
      `;
    });

    container.innerHTML = `
      <svg class="alpha-svg-chart" viewBox="0 0 ${chartWidth} ${chartHeight}">
        ${gridHtml}
        ${itemsHtml}
      </svg>
    `;
  }

  renderActivities() {
    // 1. Invoices Table (dash-recent-sales-tbody)
    const salesTbody = document.getElementById("dash-recent-sales-tbody");
    if (salesTbody) {
      let html = "";
      this.mockData.recentInvoices.forEach(inv => {
        html += `
          <tr>
            <td><strong style="color:var(--alpha-brand-primary);">${inv.vchNo}</strong></td>
            <td>${inv.party}</td>
            <td class="table-amount">₹ ${inv.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
            <td><span class="status-pill status-pill-neutral">${inv.mode}</span></td>
            <td><span class="status-pill ${inv.status === 'PAID' ? 'status-pill-success' : 'status-pill-warning'}">${inv.status}</span></td>
            <td style="color:var(--alpha-text-muted);">${inv.time}</td>
          </tr>
        `;
      });
      salesTbody.innerHTML = html;
    }

    // 2. Purchases Table (dash-recent-purchases-tbody)
    const purTbody = document.getElementById("dash-recent-purchases-tbody");
    if (purTbody) {
      let html = "";
      this.mockData.recentPurchases.forEach(pur => {
        html += `
          <tr>
            <td><strong style="color:#7c3aed;">${pur.vchNo}</strong></td>
            <td>${pur.supplier}</td>
            <td class="table-amount">₹ ${pur.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
            <td style="color:var(--alpha-text-muted);">₹ ${pur.tax.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
            <td><span class="status-pill status-pill-success">${pur.status}</span></td>
            <td style="color:var(--alpha-text-muted);">${pur.time}</td>
          </tr>
        `;
      });
      purTbody.innerHTML = html;
    }

    // 3. Payments Table (dash-recent-payments-tbody)
    const payTbody = document.getElementById("dash-recent-payments-tbody");
    if (payTbody) {
      let html = "";
      this.mockData.recentPayments.forEach(p => {
        html += `
          <tr>
            <td><strong>${p.vchNo}</strong></td>
            <td>${p.party}</td>
            <td class="table-amount" style="color: ${p.type === 'COLLECTION' ? 'var(--alpha-success)' : 'var(--alpha-danger)'};">
              ${p.type === 'COLLECTION' ? '+' : '-'} ₹ ${p.amount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </td>
            <td><span class="status-pill status-pill-neutral">${p.mode}</span></td>
            <td><span class="status-pill ${p.type === 'COLLECTION' ? 'status-pill-info' : 'status-pill-warning'}">${p.type}</span></td>
            <td style="color:var(--alpha-text-muted);">${p.time}</td>
          </tr>
        `;
      });
      payTbody.innerHTML = html;
    }

    // 4. Stock Adjustments Table (dash-recent-stock-adjustments-tbody)
    const adjTbody = document.getElementById("dash-recent-stock-adjustments-tbody");
    if (adjTbody) {
      let html = "";
      this.mockData.stockAdjustments.forEach(adj => {
        html += `
          <tr>
            <td><strong>${adj.item}</strong></td>
            <td><span class="status-pill status-pill-warning">${adj.type}</span></td>
            <td class="table-amount" style="color: ${adj.qty.startsWith('-') ? 'var(--alpha-danger)' : 'var(--alpha-success)'};">${adj.qty}</td>
            <td style="color:var(--alpha-text-secondary);">${adj.reason}</td>
            <td style="color:var(--alpha-text-muted);">${adj.date}</td>
          </tr>
        `;
      });
      adjTbody.innerHTML = html;
    }

    // Activity Tabs Binding
    const tabBtns = document.querySelectorAll(".btn-activity-tab");
    tabBtns.forEach(btn => {
      btn.addEventListener("click", () => {
        const targetTab = btn.getAttribute("data-tab-target");
        tabBtns.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        document.querySelectorAll(".activity-tab-pane").forEach(pane => {
          pane.classList.remove("active");
        });
        const targetPane = document.getElementById(`tab-pane-${targetTab}`);
        if (targetPane) targetPane.classList.add("active");
      });
    });
  }

  renderQuickActions() {
    const quickActions = [
      { id: "dash-btn-pos", label: "Fast Billing (POS)", desc: "Quick barcode retail counter", action: () => window.showScreen("view-fast-billing"), icon: "shoppingBag" },
      { id: "dash-btn-sales-add", label: "New Sales Invoice", desc: "Detailed tax invoice entry", action: () => window.showScreen("view-sales-voucher"), icon: "fileText" },
      { id: "dash-btn-purchase-add", label: "Inward Purchase Entry", desc: "Record vendor supplier bill", action: () => window.showScreen("view-purchase-entry"), icon: "shoppingCart" },
      { id: "dash-btn-product-add", label: "Add Product SKU", desc: "Create new inventory item", action: () => window.showScreen("view-add-item-master"), icon: "plusCircle" },
      { id: "dash-btn-stock-view", label: "Stock Valuation", desc: "Real-time WAC status", action: () => window.showScreen("view-stock-summary"), icon: "package" },
      { id: "dash-btn-daybook", label: "Financial Day Book", desc: "Audit daily transactions", action: () => window.showScreen("view-day-book"), icon: "barChart3" }
    ];

    const container = document.getElementById("dashboard-quick-actions-panel");
    if (!container) return;

    let html = "";
    quickActions.forEach(qa => {
      const iconSvg = window.getLucideIcon(qa.icon, "", 18);
      html += `
        <button type="button" class="quick-action-tile" id="${qa.id}">
          <div class="tile-icon-box">${iconSvg}</div>
          <div>
            <div class="tile-label">${qa.label}</div>
            <div class="tile-desc">${qa.desc}</div>
          </div>
        </button>
      `;
    });

    container.innerHTML = html;

    quickActions.forEach(qa => {
      const el = document.getElementById(qa.id);
      if (el) el.addEventListener("click", () => qa.action());
    });
  }

  loadLiveBackendData() {
    if (!window.backend) return;

    const comp = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    const cid = comp ? (comp.id || comp.code) : "COMP0001";

    try {
      // 1. Inventory Dashboard
      if (typeof window.backend.getInventoryDashboard === "function") {
        const invResStr = window.backend.getInventoryDashboard(cid);
        const invRes = typeof invResStr === "string" ? JSON.parse(invResStr) : invResStr;
        if (invRes && invRes.success && invRes.data) {
          const inv = invRes.data;
          if (inv.total_stock_valuation > 0) {
            this.mockData.kpi.stockValue = inv.total_stock_valuation;
            this.mockData.kpi.stockItemsCount = inv.total_active_products;
            this.mockData.kpi.lowStockCount = inv.low_stock_count;
            this.isLiveMode = true;
          }
        }
      }

      // 2. Daily Sales
      if (typeof window.backend.getReport === "function") {
        const reportResStr = window.backend.getReport(cid, "daily_sales");
        const reportRes = typeof reportResStr === "string" ? JSON.parse(reportResStr) : reportResStr;
        if (reportRes && reportRes.success && Array.isArray(reportRes.data) && reportRes.data.length > 0) {
          const latestDay = reportRes.data[0];
          if (latestDay && latestDay.total_revenue > 0) {
            this.mockData.kpi.todaySales = latestDay.total_revenue;
            this.mockData.kpi.todaySalesCount = latestDay.total_bills;
            this.isLiveMode = true;
          }
        }
      }

      // Re-render KPIs if live data merged
      if (this.isLiveMode) {
        this.renderKPIs();
        const modeBadge = document.getElementById("business-data-mode-badge");
        if (modeBadge) {
          modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-success);"></span> Mode: Live Backend Connected`;
        }
      }
    } catch (err) {
      console.warn("Could not query backend dashboard data:", err);
    }
  }
}

window.DashboardManager = new DashboardManager();
window.renderOperationalDashboard = function() {
  if (window.DashboardManager) {
    window.DashboardManager.renderKPIs();
  }
};
