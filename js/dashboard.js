/**
 * ALPHA BILLING - Dashboard View & Analytics Engine
 * Manages Welcome Section, 6 KPI Cards, Analytics Charts,
 * Recent Activity Feeds, and Quick Actions.
 * Exclusively backed by genuine Traditional Billing database records.
 * Zero mock, demo, or fallback figures.
 */

class DashboardManager {
  constructor() {
    this.chartPeriod = "7d";
    this.activeActivityTab = "invoices";
    this.isLiveMode = false;
    this.dashboardData = null;
    this.clockInterval = null;
  }

  init() {
    this.clearDashboard();

    // Listen to authentication & context events
    if (window.BusinessContext) {
      window.BusinessContext.on("auth-state-changed", (data) => {
        if (data && data.state === "AUTHENTICATED") {
          this.initForSession();
        } else {
          this.clearDashboard();
        }
      });
      window.BusinessContext.on("context-changed", () => {
        if (window.BusinessContext.isAuthenticatedSession()) {
          this.renderWelcome();
          this.loadLiveBackendData();
        }
      });
    }

    // Refresh button binding
    const refreshBtn = document.getElementById("dash-btn-refresh-overview");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", () => {
        if (window.BusinessContext && window.BusinessContext.isAuthenticatedSession()) {
          this.loadLiveBackendData();
        }
      });
    }

    if (window.BusinessContext && window.BusinessContext.isAuthenticatedSession()) {
      this.initForSession();
    }
  }

  initForSession() {
    if (!window.BusinessContext || !window.BusinessContext.isAuthenticatedSession()) {
      this.clearDashboard();
      return;
    }
    this.renderWelcome();
    this.renderKPIs();
    this.renderCharts();
    this.renderActivities();
    this.renderQuickActions();
    this.startLiveClock();
    this.loadLiveBackendData();
  }

  stopLiveClock() {
    if (this.clockInterval) {
      clearInterval(this.clockInterval);
      this.clockInterval = null;
    }
  }

  clearDashboard() {
    this.stopLiveClock();
    this.isLiveMode = false;
    this.dashboardData = null;

    const greetingHeading = document.getElementById("welcome-greeting-heading");
    if (greetingHeading) greetingHeading.textContent = "";

    const ctxCompany = document.getElementById("welcome-ctx-company");
    if (ctxCompany) ctxCompany.textContent = "--";

    const ctxBranch = document.getElementById("welcome-ctx-branch");
    if (ctxBranch) ctxBranch.textContent = "--";

    const ctxYear = document.getElementById("welcome-ctx-year");
    if (ctxYear) ctxYear.textContent = "--";

    const modeBadge = document.getElementById("business-data-mode-badge");
    if (modeBadge) {
      modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-text-muted);"></span> Awaiting Authentication`;
    }

    const dateEl = document.getElementById("welcome-current-date");
    if (dateEl) dateEl.textContent = "--";
    const timeEl = document.getElementById("welcome-current-time");
    if (timeEl) timeEl.textContent = "--";

    // Clear KPI display elements
    const kpiZeroFields = [
      "dash-today-sales", "dash-today-purchases", "dash-total-stock-value", "dash-today-expenses"
    ];
    kpiZeroFields.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = "--";
    });

    const kpiUnavailableFields = [
      "dash-receivables", "dash-payables"
    ];
    kpiUnavailableFields.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = "Not available";
    });

    const kpiCountFields = [
      { id: "dash-sales-count", text: "0 Invoices" },
      { id: "dash-sales-delta", text: "" },
      { id: "dash-purchases-count", text: "0 Bills" },
      { id: "dash-purchases-delta", text: "" },
      { id: "dash-stock-count", text: "0 Active SKUs" },
      { id: "dash-low-stock", text: "0 items low" },
      { id: "dash-receivables-count", text: "N/A" },
      { id: "dash-payables-count", text: "N/A" },
      { id: "dash-held-bills", text: "0 held bills" },
    ];
    kpiCountFields.forEach(f => {
      const el = document.getElementById(f.id);
      if (el) el.textContent = f.text;
    });

    const marginBadge = document.getElementById("dash-gross-margin");
    if (marginBadge) {
      marginBadge.textContent = "Gross Margin: Not available";
      marginBadge.className = "status-pill status-pill-neutral";
    }

    this.renderCharts();
    this.renderActivities();
  }

  startLiveClock() {
    this.stopLiveClock();
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
    this.clockInterval = setInterval(updateTime, 1000);
  }

  renderWelcome() {
    const comp = window.BusinessContext ? window.BusinessContext.getActiveCompany() : null;
    const branch = window.BusinessContext ? window.BusinessContext.getActiveBranch() : null;
    const user = window.BusinessContext ? window.BusinessContext.getCurrentUser() : null;

    const hour = new Date().getHours();
    let greeting = "Good morning";
    if (hour >= 12 && hour < 17) greeting = "Good afternoon";
    else if (hour >= 17) greeting = "Good evening";

    const greetingHeading = document.getElementById("welcome-greeting-heading");
    if (greetingHeading) {
      greetingHeading.textContent = user ? `${greeting}, ${user.displayName || user.username}` : "";
    }

    const ctxCompany = document.getElementById("welcome-ctx-company");
    if (ctxCompany) ctxCompany.textContent = comp ? `${comp.name} (${comp.code})` : "--";

    const ctxBranch = document.getElementById("welcome-ctx-branch");
    if (ctxBranch) ctxBranch.textContent = branch ? `${branch.name} (${branch.code || 'BR01'})` : "--";

    const ctxYear = document.getElementById("welcome-ctx-year");
    if (ctxYear) ctxYear.textContent = comp ? (comp.finYear || comp.fin_year || "2026-2027") : "--";

    const modeBadge = document.getElementById("business-data-mode-badge");
    if (modeBadge && comp) {
      const branchCode = branch ? (branch.code || "BR01") : "BR01";
      modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-brand-primary);"></span> Traditional Billing (${comp.code} - ${branchCode})`;
    }
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
      if (el && !el.hasChildNodes() && typeof window.getLucideIcon === "function") {
        el.innerHTML = window.getLucideIcon(m.icon, "", 16);
      }
    });

    const d = this.dashboardData;

    // 1. Today's Sales
    const salesEl = document.getElementById("dash-today-sales");
    if (salesEl) {
      const val = d && typeof d.todaySales === "number" ? d.todaySales : 0.00;
      salesEl.textContent = `₹ ${val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    const salesCountEl = document.getElementById("dash-sales-count");
    if (salesCountEl) {
      const cnt = d && typeof d.todaySalesCount === "number" ? d.todaySalesCount : 0;
      salesCountEl.textContent = `${cnt} Invoices`;
    }
    const salesDeltaEl = document.getElementById("dash-sales-delta");
    if (salesDeltaEl) {
      salesDeltaEl.textContent = d && d.todaySalesDelta ? d.todaySalesDelta : "";
      if (!d || !d.todaySalesDelta) salesDeltaEl.style.display = "none";
      else salesDeltaEl.style.display = "";
    }

    // 2. Today's Purchases
    const purEl = document.getElementById("dash-today-purchases");
    if (purEl) {
      const val = d && typeof d.todayPurchases === "number" ? d.todayPurchases : 0.00;
      purEl.textContent = `₹ ${val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    const purCountEl = document.getElementById("dash-purchases-count");
    if (purCountEl) {
      const cnt = d && typeof d.todayPurchasesCount === "number" ? d.todayPurchasesCount : 0;
      purCountEl.textContent = `${cnt} Bills`;
    }
    const purDeltaEl = document.getElementById("dash-purchases-delta");
    if (purDeltaEl) {
      purDeltaEl.textContent = d && d.todayPurchasesDelta ? d.todayPurchasesDelta : "";
      if (!d || !d.todayPurchasesDelta) purDeltaEl.style.display = "none";
      else purDeltaEl.style.display = "";
    }

    // 3. Total Stock Value
    const stockEl = document.getElementById("dash-total-stock-value");
    if (stockEl) {
      if (d && d.stockValue !== null && d.stockValue !== undefined) {
        stockEl.textContent = `₹ ${Number(d.stockValue).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      } else {
        stockEl.textContent = `₹ 0.00`;
      }
    }
    const stockCountEl = document.getElementById("dash-stock-count");
    if (stockCountEl) {
      const cnt = d && typeof d.stockItemsCount === "number" ? d.stockItemsCount : 0;
      stockCountEl.textContent = `${cnt} Active SKUs`;
    }
    const lowStockCompat = document.getElementById("dash-low-stock");
    if (lowStockCompat) {
      const cnt = d && typeof d.lowStockCount === "number" ? d.lowStockCount : 0;
      lowStockCompat.textContent = `${cnt} items low`;
    }

    // 4. Outstanding Receivables
    const recvEl = document.getElementById("dash-receivables");
    if (recvEl) {
      if (d && d.receivables !== null && d.receivables !== undefined) {
        recvEl.textContent = `₹ ${Number(d.receivables).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      } else {
        recvEl.textContent = "Not available";
      }
    }
    const recvCountEl = document.getElementById("dash-receivables-count");
    if (recvCountEl) {
      if (d && d.receivablesOverdueCount !== null && d.receivablesOverdueCount !== undefined) {
        recvCountEl.textContent = `${d.receivablesOverdueCount} Overdue`;
      } else {
        recvCountEl.textContent = "N/A";
      }
    }
    const recvBadge = document.getElementById("dash-receivables-badge");
    if (recvBadge) {
      recvBadge.textContent = "N/A";
    }

    // 5. Outstanding Payables
    const payEl = document.getElementById("dash-payables");
    if (payEl) {
      if (d && d.payables !== null && d.payables !== undefined) {
        payEl.textContent = `₹ ${Number(d.payables).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      } else {
        payEl.textContent = "Not available";
      }
    }
    const payCountEl = document.getElementById("dash-payables-count");
    if (payCountEl) {
      if (d && d.payablesDueCount !== null && d.payablesDueCount !== undefined) {
        payCountEl.textContent = `${d.payablesDueCount} Suppliers Due`;
      } else {
        payCountEl.textContent = "N/A";
      }
    }
    const payBadge = document.getElementById("dash-payables-badge");
    if (payBadge) {
      payBadge.textContent = "N/A";
    }

    // 6. Today's Expenses
    const expEl = document.getElementById("dash-today-expenses");
    if (expEl) {
      const val = d && typeof d.todayExpenses === "number" ? d.todayExpenses : 0.00;
      expEl.textContent = `₹ ${val.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    const heldCompat = document.getElementById("dash-held-bills");
    if (heldCompat) {
      const cnt = d && typeof d.heldBills === "number" ? d.heldBills : 0;
      heldCompat.textContent = `${cnt} held bills`;
    }

    // Gross Margin pill
    const marginBadge = document.getElementById("dash-gross-margin");
    if (marginBadge) {
      if (d && d.grossMargin !== null && d.grossMargin !== undefined) {
        marginBadge.textContent = `Gross Margin: ${d.grossMargin}%`;
        marginBadge.className = "status-pill status-pill-success";
      } else {
        marginBadge.textContent = "Gross Margin: Not available";
        marginBadge.className = "status-pill status-pill-neutral";
      }
    }
  }

  renderCharts() {
    this.renderSalesTrendChart();
    this.renderPaymentSummary();
    this.renderRevenueExpenseChart();
  }

  renderSalesTrendChart() {
    const container = document.getElementById("chart-sales-trend-container");
    if (!container) return;

    const data = this.dashboardData && Array.isArray(this.dashboardData.salesTrend)
      ? this.dashboardData.salesTrend
      : [];

    if (data.length === 0) {
      container.innerHTML = `
        <div class="chart-empty-state" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:180px; color:var(--alpha-text-muted); font-size:13px; text-align:center;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4; margin-bottom:8px;"><path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/></svg>
          <span>No sales or procurement data yet</span>
        </div>
      `;
      return;
    }

    const maxVal = Math.max(...data.map(d => Math.max(d.sales || 0, d.purchases || 0)), 1000) * 1.15;
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

    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const y = paddingY + (usableH / gridSteps) * i;
      const val = Math.round((maxVal - (maxVal / gridSteps) * i) / 1000);
      gridHtml += `
        <line x1="${paddingX}" y1="${y}" x2="${chartWidth - paddingX}" y2="${y}" class="chart-grid-line" />
        <text x="${paddingX - 8}" y="${y + 4}" text-anchor="end" class="chart-axis-label">₹${val}k</text>
      `;
    }

    data.forEach((d, idx) => {
      const groupX = paddingX + idx * barGroupW + (barGroupW - barW * 2 - 4) / 2;
      const salesH = ((d.sales || 0) / maxVal) * usableH;
      const salesY = paddingY + (usableH - salesH);
      const purH = ((d.purchases || 0) / maxVal) * usableH;
      const purY = paddingY + (usableH - purH);

      barsHtml += `
        <rect x="${groupX}" y="${salesY}" width="${barW}" height="${salesH}" rx="3" fill="#2563eb" class="chart-bar">
          <title>${d.label || d.day} Sales: ₹${(d.sales || 0).toLocaleString('en-IN')}</title>
        </rect>
        <rect x="${groupX + barW + 4}" y="${purY}" width="${barW}" height="${purH}" rx="3" fill="#93c5fd" class="chart-bar">
          <title>${d.label || d.day} Purchases: ₹${(d.purchases || 0).toLocaleString('en-IN')}</title>
        </rect>
        <text x="${groupX + barW + 2}" y="${chartHeight - 6}" text-anchor="middle" class="chart-axis-label">${d.day || ''}</text>
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

    const data = this.dashboardData && Array.isArray(this.dashboardData.paymentSummary)
      ? this.dashboardData.paymentSummary
      : [];

    if (data.length === 0) {
      container.innerHTML = `
        <div class="chart-empty-state" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:180px; color:var(--alpha-text-muted); font-size:13px; text-align:center;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4; margin-bottom:8px;"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>
          <span>No payment data yet</span>
        </div>
      `;
      return;
    }

    let html = `<div class="payment-summary-box">`;
    data.forEach(p => {
      html += `
        <div class="payment-progress-item">
          <div class="payment-item-header">
            <span class="payment-item-name">
              <span class="payment-method-dot" style="background-color: ${p.color || '#6b7280'};"></span>
              ${p.method}
            </span>
            <span class="payment-item-val">₹ ${(p.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })} (${p.percent || 0}%)</span>
          </div>
          <div class="progress-track">
            <div class="progress-fill" style="width: ${p.percent || 0}%; background-color: ${p.color || '#6b7280'};"></div>
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

    const data = this.dashboardData && Array.isArray(this.dashboardData.revenueExpense)
      ? this.dashboardData.revenueExpense
      : [];

    if (data.length === 0) {
      container.innerHTML = `
        <div class="chart-empty-state" style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:180px; color:var(--alpha-text-muted); font-size:13px; text-align:center;">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="opacity:0.4; margin-bottom:8px;"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          <span>No financial comparison data yet</span>
        </div>
      `;
      return;
    }

    const maxVal = Math.max(...data.map(d => Math.max(d.revenue || 0, d.cost || 0)), 100000) * 1.15;
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
      const revH = ((d.revenue || 0) / maxVal) * usableH;
      const revY = paddingY + (usableH - revH);
      const costH = ((d.cost || 0) / maxVal) * usableH;
      const costY = paddingY + (usableH - costH);

      itemsHtml += `
        <rect x="${cx - 18}" y="${revY}" width="16" height="${revH}" rx="3" fill="#10b981" class="chart-bar">
          <title>${d.month} Gross Revenue: ₹${(d.revenue || 0).toLocaleString('en-IN')}</title>
        </rect>
        <rect x="${cx + 2}" y="${costY}" width="16" height="${costH}" rx="3" fill="#f59e0b" class="chart-bar">
          <title>${d.month} Cost of Sales: ₹${(d.cost || 0).toLocaleString('en-IN')}</title>
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
    const d = this.dashboardData;

    // 1. Invoices Table
    const salesTbody = document.getElementById("dash-recent-sales-tbody");
    if (salesTbody) {
      const invoices = d && Array.isArray(d.recentInvoices) ? d.recentInvoices : [];
      if (invoices.length === 0) {
        salesTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--alpha-text-muted);">No sales invoices recorded yet</td></tr>`;
      } else {
        let html = "";
        invoices.forEach(inv => {
          html += `
            <tr>
              <td><strong style="color:var(--alpha-brand-primary);">${inv.vchNo}</strong></td>
              <td>${inv.party}</td>
              <td class="table-amount">₹ ${(inv.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
              <td><span class="status-pill status-pill-neutral">${inv.mode || 'CASH'}</span></td>
              <td><span class="status-pill ${inv.status === 'PAID' ? 'status-pill-success' : 'status-pill-warning'}">${inv.status || 'PAID'}</span></td>
              <td style="color:var(--alpha-text-muted);">${inv.time || ''}</td>
            </tr>
          `;
        });
        salesTbody.innerHTML = html;
      }
    }

    // 2. Purchases Table
    const purTbody = document.getElementById("dash-recent-purchases-tbody");
    if (purTbody) {
      const purchases = d && Array.isArray(d.recentPurchases) ? d.recentPurchases : [];
      if (purchases.length === 0) {
        purTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--alpha-text-muted);">No inward purchases recorded yet</td></tr>`;
      } else {
        let html = "";
        purchases.forEach(pur => {
          html += `
            <tr>
              <td><strong style="color:#7c3aed;">${pur.vchNo}</strong></td>
              <td>${pur.supplier}</td>
              <td class="table-amount">₹ ${(pur.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
              <td style="color:var(--alpha-text-muted);">₹ ${(pur.tax || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td>
              <td><span class="status-pill status-pill-success">${pur.status || 'VERIFIED'}</span></td>
              <td style="color:var(--alpha-text-muted);">${pur.time || ''}</td>
            </tr>
          `;
        });
        purTbody.innerHTML = html;
      }
    }

    // 3. Payments Table
    const payTbody = document.getElementById("dash-recent-payments-tbody");
    if (payTbody) {
      const payments = d && Array.isArray(d.recentPayments) ? d.recentPayments : [];
      if (payments.length === 0) {
        payTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--alpha-text-muted);">No collections or payments recorded yet</td></tr>`;
      } else {
        let html = "";
        payments.forEach(p => {
          html += `
            <tr>
              <td><strong>${p.vchNo}</strong></td>
              <td>${p.party}</td>
              <td class="table-amount" style="color: ${p.type === 'COLLECTION' ? 'var(--alpha-success)' : 'var(--alpha-danger)'};">
                ${p.type === 'COLLECTION' ? '+' : '-'} ₹ ${(p.amount || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </td>
              <td><span class="status-pill status-pill-neutral">${p.mode || 'CASH'}</span></td>
              <td><span class="status-pill ${p.type === 'COLLECTION' ? 'status-pill-info' : 'status-pill-warning'}">${p.type}</span></td>
              <td style="color:var(--alpha-text-muted);">${p.time || ''}</td>
            </tr>
          `;
        });
        payTbody.innerHTML = html;
      }
    }

    // 4. Stock Adjustments Table
    const adjTbody = document.getElementById("dash-recent-stock-adjustments-tbody");
    if (adjTbody) {
      const adjs = d && Array.isArray(d.stockAdjustments) ? d.stockAdjustments : [];
      if (adjs.length === 0) {
        adjTbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--alpha-text-muted);">No stock adjustments recorded yet</td></tr>`;
      } else {
        let html = "";
        adjs.forEach(adj => {
          html += `
            <tr>
              <td><strong>${adj.item}</strong></td>
              <td><span class="status-pill status-pill-warning">${adj.type}</span></td>
              <td class="table-amount" style="color: ${String(adj.qty).startsWith('-') ? 'var(--alpha-danger)' : 'var(--alpha-success)'};">${adj.qty}</td>
              <td style="color:var(--alpha-text-secondary);">${adj.reason}</td>
              <td style="color:var(--alpha-text-muted);">${adj.date}</td>
            </tr>
          `;
        });
        adjTbody.innerHTML = html;
      }
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
      const iconSvg = typeof window.getLucideIcon === "function" ? window.getLucideIcon(qa.icon, "", 18) : "";
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
    if (!window.BusinessContext || !window.BusinessContext.isAuthenticatedSession()) {
      return;
    }

    const comp = window.BusinessContext.getActiveCompany();
    const branch = window.BusinessContext.getActiveBranch();
    if (!comp) return;

    // Traditional Billing dedicated dashboard RPC
    if (typeof window.backend.traditional_getDashboardMetrics === "function") {
      window.backend.traditional_getDashboardMetrics((resp) => {
        try {
          const res = typeof resp === "string" ? JSON.parse(resp) : resp;
          if (res && res.success && res.data) {
            this.dashboardData = res.data;
            this.isLiveMode = true;
            this.renderKPIs();
            this.renderCharts();
            this.renderActivities();

            const modeBadge = document.getElementById("business-data-mode-badge");
            if (modeBadge) {
              const bCode = branch ? (branch.code || "BR01") : "BR01";
              modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-success);"></span> Mode: Traditional Database Connected (${comp.code} - ${bCode})`;
            }
          } else {
            console.warn("Failed to load traditional dashboard data:", res ? res.error : "Unknown error");
            this.isLiveMode = false;
            const modeBadge = document.getElementById("business-data-mode-badge");
            if (modeBadge) {
              modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-danger);"></span> Error: ${res ? res.error : "Dashboard unavailable"}`;
            }
            this.renderKPIs();
            this.renderCharts();
            this.renderActivities();
          }
        } catch (err) {
          console.error("Error parsing traditional dashboard data:", err);
          this.isLiveMode = false;
          const modeBadge = document.getElementById("business-data-mode-badge");
          if (modeBadge) {
            modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-danger);"></span> Error loading dashboard`;
          }
          this.renderKPIs();
          this.renderCharts();
          this.renderActivities();
        }
      });
      return;
    }

    // Fail closed if backend RPC is not available
    console.warn("traditional_getDashboardMetrics RPC is not available on backend bridge.");
    this.isLiveMode = false;
    const modeBadge = document.getElementById("business-data-mode-badge");
    if (modeBadge) {
      modeBadge.innerHTML = `<span class="mode-pulse-dot" style="background-color: var(--alpha-danger);"></span> Bridge RPC Unavailable`;
    }
    this.renderKPIs();
    this.renderCharts();
    this.renderActivities();
  }
}

window.DashboardManager = new DashboardManager();
window.renderOperationalDashboard = function() {
  if (window.DashboardManager) {
    window.DashboardManager.renderKPIs();
    if (window.BusinessContext && window.BusinessContext.isAuthenticatedSession()) {
      window.DashboardManager.loadLiveBackendData();
    }
  }
};
