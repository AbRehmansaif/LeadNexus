window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }

  // ── Elements ──────────────────────────────────────────────
  const targetVolumeSlider = document.getElementById('targetVolume');
  const targetVolumeVal = document.getElementById('targetVolumeVal');
  const emailProviderSelect = document.getElementById('emailProvider');
  const domainReputationSelect = document.getElementById('domainReputation');
  const strategyBtns = document.querySelectorAll('.strategy-btn');
  const calculateBtn = document.getElementById('calculateBtn');
  const downloadCsvBtn = document.getElementById('downloadCsvBtn');
  const downloadPdfBtn = document.getElementById('downloadPdfBtn');
  
  const emptyState = document.getElementById('emptyState');
  const scheduleResults = document.getElementById('scheduleResults');
  const scheduleTableBody = document.getElementById('scheduleTableBody');
  const inboxTableBody = document.getElementById('inboxTableBody');
  
  const daysToTargetEl = document.getElementById('daysToTarget');
  const startingVolEl = document.getElementById('startingVol');
  const dailyIncEl = document.getElementById('dailyInc');
  const reqInboxesEl = document.getElementById('reqInboxes');
  const delivScoreVal = document.getElementById('delivScoreVal');

  // ── State ─────────────────────────────────────────────────
  let selectedStrategy = 'recommended';
  let generatedData = [];
  let chartInstance = null;

  // ── Event Listeners ───────────────────────────────────────
  targetVolumeSlider.addEventListener('input', (e) => {
    targetVolumeVal.textContent = `${e.target.value} emails/day`;
  });

  // AI Strategy Recommendation
  if (domainReputationSelect) {
    domainReputationSelect.addEventListener('change', (e) => {
      strategyBtns.forEach(b => b.classList.remove('active'));
      const val = e.target.value;
      if (val === 'new') {
        selectedStrategy = 'conservative';
        document.querySelector('[data-strategy="conservative"]').classList.add('active');
        showToast("Strategy Updated", "Auto-selected Conservative strategy for brand new domain.", "check-circle");
      } else if (val === 'aged') {
        selectedStrategy = 'aggressive';
        document.querySelector('[data-strategy="aggressive"]').classList.add('active');
        showToast("Strategy Updated", "Auto-selected Aggressive strategy for aged domain.", "check-circle");
      } else {
        selectedStrategy = 'recommended';
        document.querySelector('[data-strategy="recommended"]').classList.add('active');
      }
    });
  }

  strategyBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      strategyBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedStrategy = btn.getAttribute('data-strategy');
    });
  });

  calculateBtn.addEventListener('click', generateSchedule);
  downloadCsvBtn.addEventListener('click', downloadCsv);
  if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener('click', downloadPdf);
  }

  // ── Logic ─────────────────────────────────────────────────
  function generateSchedule() {
    const targetVolume = parseInt(targetVolumeSlider.value);
    
    if (!targetVolume || targetVolume < 1) {
      showToast("Invalid Input", "Please configure a target volume greater than 0.", "error");
      return;
    }

    const domainReputation = domainReputationSelect.value;
    
    const providerLimits = {
      gmail: 50,
      outlook: 40,
      smtp: 100
    };
    const selectedProvider = emailProviderSelect ? emailProviderSelect.value : 'gmail';
    const providerLimit = providerLimits[selectedProvider] || 50;
    
    let startVol = 2;
    let increment = 2;
    
    // 1. Establish Baselines Based on Domain Reputation
    if (domainReputation === 'new') {
      startVol = 2;
    } else if (domainReputation === 'aged') {
      startVol = 5;
    } else if (domainReputation === 'recovering') {
      startVol = 1;
    }

    // 2. Adjust Increments Based on Strategy
    if (selectedStrategy === 'conservative') {
      increment = domainReputation === 'aged' ? 2 : 1;
    } else if (selectedStrategy === 'recommended') {
      if (domainReputation === 'new') increment = 2;
      if (domainReputation === 'aged') increment = 3;
      if (domainReputation === 'recovering') increment = 1; // force conservative
    } else if (selectedStrategy === 'aggressive') {
      if (domainReputation === 'new') increment = 4;
      if (domainReputation === 'aged') increment = 5;
      if (domainReputation === 'recovering') increment = 2; // too risky, cap it
    }

    if (increment > 3 && domainReputation === 'new') {
      showToast("High Spam Risk", "A daily increment over 3 on a brand new domain can quickly trigger Google/Outlook spam filters. Proceed with extreme caution.", "warning");
    }

    // 3. Generate Schedule Array
    generatedData = [];
    let currentVol = startVol;
    let day = 1;

    while (currentVol < targetVolume) {
      let progress = currentVol / targetVolume;
      let warmupPercent;
      
      if (progress < 0.2) warmupPercent = 1;
      else if (progress < 0.5) warmupPercent = 0.7;
      else if (progress < 0.8) warmupPercent = 0.5;
      else warmupPercent = 0.3;
      
      let warmupEmails = Math.max(1, Math.floor(currentVol * warmupPercent));
      
      let statusHtml = '';
      if (domainReputation === 'recovering') {
        statusHtml = `<span class="status-badge status-recovering">Recovering</span>`;
      } else {
        statusHtml = `<span class="status-badge status-warming">Warming Up</span>`;
      }

      generatedData.push({
        day: day,
        warmupEmails: warmupEmails,
        totalEmails: currentVol,
        statusHtml: statusHtml,
        statusText: domainReputation === 'recovering' ? 'Recovering' : 'Warming Up'
      });

      // Daily Cap
      let maxDailyIncrease = Math.ceil(currentVol * 0.3);
      let safeIncrement = Math.min(increment, maxDailyIncrease);
      currentVol += Math.max(safeIncrement, 1);
      day++;
      
      // Safety break to prevent infinite loops if something goes wrong
      if (day > 365) break; 
    }

    // Add final day
    let finalWarmup = Math.max(3, Math.floor(targetVolume * 0.3)); // maintain 30% warmup indefinitely
    generatedData.push({
      day: day,
      warmupEmails: finalWarmup,
      totalEmails: targetVolume,
      statusHtml: `<span class="status-badge status-ready"><i data-lucide="check-circle" style="width:12px;height:12px;"></i> Ready</span>`,
      statusText: 'Ready'
    });

    let deliverabilityScore = 100;
    if (increment > 3) deliverabilityScore -= 20;
    if (domainReputation === 'recovering') deliverabilityScore -= 30;

    renderResults(startVol, increment, day, {
      limit: providerLimit,
      score: deliverabilityScore,
      finalWarmup: finalWarmup,
      targetVolume: targetVolume
    });
  }

  function renderResults(startVol, increment, totalDays, meta) {
    emptyState.style.display = 'none';
    scheduleResults.style.display = 'block';
    downloadCsvBtn.style.display = 'inline-flex';
    if (downloadPdfBtn) downloadPdfBtn.style.display = 'inline-flex';

    daysToTargetEl.textContent = totalDays;
    startingVolEl.textContent = startVol;
    dailyIncEl.textContent = `+${increment}/day`;
    
    // Multi-inbox logic check
    const requiredBoxes = Math.ceil(meta.targetVolume / meta.limit);
    reqInboxesEl.textContent = requiredBoxes;
    
    // Deliverability Score Output
    if (delivScoreVal) {
      delivScoreVal.textContent = `${meta.score}/100`;
      delivScoreVal.style.color = meta.score > 80 ? '#10b981' : (meta.score > 60 ? '#f59e0b' : '#ef4444');
    }

    // Render Multi-Inbox Table
    if (inboxTableBody) {
      let inboxesHtml = '';
      for (let i = 1; i <= requiredBoxes; i++) {
        let boxTotal = Math.floor(meta.targetVolume / requiredBoxes);
        if (i === requiredBoxes) boxTotal += meta.targetVolume % requiredBoxes;
        
        let boxWarmup = Math.floor(meta.finalWarmup / requiredBoxes);
        if (i === requiredBoxes) boxWarmup += meta.finalWarmup % requiredBoxes;
        
        let boxCold = boxTotal - boxWarmup;
        
        inboxesHtml += `<tr>
          <td class="val-bold">Inbox 0${i}</td>
          <td>${boxWarmup}</td>
          <td>${boxCold}</td>
          <td class="val-bold" style="color:#a78bfa;">${boxTotal}</td>
        </tr>`;
      }
      inboxTableBody.innerHTML = inboxesHtml;
    }

    // Render Table
    scheduleTableBody.innerHTML = generatedData.map(row => `
      <tr>
        <td class="val-bold">Day ${row.day}</td>
        <td>${row.warmupEmails} emails</td>
        <td class="val-bold">${row.totalEmails} emails</td>
        <td>${row.statusHtml}</td>
      </tr>
    `).join('');

    // Render Chart
    const ctx = document.getElementById('warmupChart');
    if (ctx && window.Chart) {
      if (chartInstance && typeof chartInstance.destroy === 'function') {
        chartInstance.destroy();
      }
      
      const labels = generatedData.map(r => `Day ${r.day}`);
      const totalData = generatedData.map(r => r.totalEmails);
      const warmupData = generatedData.map(r => r.warmupEmails);

      chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'Total Sends',
              data: totalData,
              borderColor: '#a78bfa',
              backgroundColor: 'rgba(167, 139, 250, 0.15)',
              borderWidth: 2,
              fill: true,
              tension: 0.3
            },
            {
              label: 'Warm-up Portion',
              data: warmupData,
              borderColor: '#10b981',
              backgroundColor: 'transparent',
              borderWidth: 2,
              borderDash: [5, 5],
              fill: false,
              tension: 0.3
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'index',
            intersect: false,
          },
          plugins: {
            legend: {
              labels: { color: 'rgba(255,255,255,0.7)', font: { size: 11 } }
            },
            tooltip: {
              backgroundColor: 'rgba(15, 23, 42, 0.9)',
              titleColor: '#fff',
              bodyColor: '#cbd5e1',
              borderColor: 'rgba(255,255,255,0.1)',
              borderWidth: 1
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
              ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } }
            },
            y: {
              grid: { color: 'rgba(255,255,255,0.05)', drawBorder: false },
              ticks: { color: 'rgba(255,255,255,0.5)', font: { size: 10 } }
            }
          }
        }
      });
    }

    if (window.lucide) {
      lucide.createIcons();
    }
  }

  function downloadCsv() {
    if (generatedData.length === 0) return;
    
    let csvContent = "";
    csvContent += "Day,Warm-up Emails,Total Emails,Status\n";
    
    generatedData.forEach(row => {
      csvContent += `${row.day},${row.warmupEmails},${row.totalEmails},${row.statusText}\n`;
    });
    
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", "LeadNexus_Warmup_Schedule.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

function downloadPdf() {
  if (!window.html2pdf) {
    alert("PDF library loading... try again.");
    return;
  }

  const websiteUrl = "https://leadnexus.difusionseo.com/";
  const navbarLogo = document.querySelector('.brand-logo-img');
  const logoSrc = navbarLogo?.src || `${websiteUrl}static/logo.png`;

  const wrapper = document.createElement('div');
  wrapper.style.position = 'fixed';
  wrapper.style.left = '-9999px';
  wrapper.style.top = '0';

  const container = document.createElement('div');
  container.style.width = '800px';
  container.style.background = '#ffffff';
  container.style.color = '#0f172a';
  container.style.fontFamily = 'Inter, sans-serif';
  container.style.padding = '40px 60px';
  container.style.lineHeight = '1.6';

  wrapper.appendChild(container);
  document.body.appendChild(wrapper);

  // HEADER
  const header = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:30px;">
      <div>
        <img src="${logoSrc}" style="height:100px;" />
        <div style="font-size:13px; color:#64748b; margin-top:6px;">
          AI Powered Email Warm Up Strategy Report
        </div>
      </div>
      <div style="text-align:right; font-size:12px; color:#64748b;">
        <div><b>Ref:</b> LN-${Math.floor(Date.now()/1000).toString(16).toUpperCase()}</div>
        <div>${new Date().toLocaleDateString()}</div>
        <div style="margin-top:6px; color:#7c3aed; font-weight:600;">
          leadnexus.difusionseo.com
        </div>
      </div>
    </div>
  `;

  // HERO MESSAGE
  const hero = `
    <div style="margin-bottom:25px; padding:18px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;">
      <div style="font-size:14px;">
        This strategy is generated by <b>LeadNexus</b> to help you safely scale your cold email outreach while maintaining high deliverability.
      </div>
    </div>
  `;

  // SAFE SUMMARY
  function getSafeText(el) {
    return el ? el.textContent : 'N/A';
  }

  const summary = `
    <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:25px;">
      ${[
        ['Days to Target', getSafeText(daysToTargetEl)],
        ['Starting Volume', getSafeText(startingVolEl)],
        ['Daily Increase', getSafeText(dailyIncEl)],
        ['Required Inboxes', getSafeText(reqInboxesEl)]
      ].map(i => `
        <div style="border:1px solid #e2e8f0; border-radius:8px; padding:12px; text-align:center;">
          <div style="font-size:11px; color:#64748b;">${i[0]}</div>
          <div style="font-size:18px; font-weight:700;">${i[1]}</div>
        </div>
      `).join('')}
    </div>
  `;

  // CHART
  const canvas = document.getElementById('warmupChart');
  const chartImg = canvas ? canvas.toDataURL("image/png") : '';

  const chart = `
    <div style="margin-bottom:30px;">
      <h3 style="margin-bottom:5px;">Growth Projection</h3>
      <div style="font-size:12px; color:#64748b; margin-bottom:8px;">
        Gradual ramp-up ensures inbox placement and avoids spam filters.
      </div>
      ${chartImg ? `<img src="${chartImg}" style="width:100%; border:1px solid #e2e8f0; border-radius:6px;" />` : '<p style="color:red;">Chart not available</p>'}
    </div>
  `;

  // CLEAN TABLE FUNCTION
  function cleanTable(html) {
    return html
      .replace(/<thead>/g, '<thead style="background:#f8fafc;">')
      .replace(/<tr>/g, '<tr style="border-bottom:1px solid #e2e8f0;">')
      .replace(/<td/g, '<td style="padding:8px; font-size:12px;"')
      .replace(/<th/g, '<th style="padding:8px; font-size:12px; text-align:left;"');
  }

  // INBOX TABLE
  const inboxRows = document.getElementById('inboxTableBody')?.innerHTML || '<tr><td colspan="4">No data available</td></tr>';
  const inboxTable = `
    <div style="margin-bottom:30px;">
      <h3>Inbox Distribution Plan</h3>
      <div style="font-size:12px; color:#64748b; margin-bottom:8px;">
        Distributing across inboxes protects sender reputation.
      </div>
      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr>
            <th>Inbox</th>
            <th>Warmup</th>
            <th>Cold Emails</th>
            <th>Total</th>
          </tr>
        </thead>
        <tbody>
          ${cleanTable(inboxRows)}
        </tbody>
      </table>
    </div>
  `;

  // SCHEDULE TABLE
  const scheduleRows = document.getElementById('scheduleTableBody')?.innerHTML || '<tr><td colspan="4">No schedule data</td></tr>';
  const schedule = `
    <div style="margin-bottom:30px;">
      <h3>Daily Sending Schedule</h3>
      <table style="width:100%; border-collapse:collapse;">
        <thead>
          <tr>
            <th>Day</th>
            <th>Warmup</th>
            <th>Total</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${cleanTable(scheduleRows)}
        </tbody>
      </table>
    </div>
  `;

  // MARKETING CTA
  const cta = `
    <div style="margin-top:35px; padding:25px; background:linear-gradient(135deg,#7c3aed,#a78bfa); color:#fff; border-radius:12px;">
      <div style="font-size:18px; font-weight:700; margin-bottom:10px;">
        Scale Your Outreach with LeadNexus
      </div>
      <div style="font-size:13px; line-height:1.6;">
        Stop manual warm-ups and risky sending.<br><br>
        <b>Use LeadNexus to:</b><br>
        • Automatically warm up your email accounts<br>
        • Send cold emails safely with AI strategies<br>
        • Manage multiple inboxes at scale<br>
        • Improve deliverability & avoid spam folders<br><br>
        👉 Start now: <b>leadnexus.difusionseo.com</b>
      </div>
    </div>
  `;

  // FOOTER
  const footer = `
    <div style="margin-top:40px; text-align:center; font-size:11px; color:#94a3b8;">
      © ${new Date().getFullYear()} LeadNexus — B2B Email Infrastructure Platform
    </div>
  `;

  container.innerHTML = header + hero + summary + chart + inboxTable + schedule + cta + footer;

  const opt = {
    margin: 0.3,
    filename: 'LeadNexus_Premium_Report.pdf',
    image: { type: 'jpeg', quality: 1 },
    html2canvas: { scale: 2, useCORS: true },
    jsPDF: { unit: 'in', format: 'letter' }
  };

  html2pdf()
    .set(opt)
    .from(container)
    .outputPdf('blob')
    .then((pdfBlob) => {
      const url = URL.createObjectURL(pdfBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'LeadNexus_Premium_Report.pdf';
      link.click();

      URL.revokeObjectURL(url);
      document.body.removeChild(wrapper);
    })
    .catch(() => {
      document.body.removeChild(wrapper);
      alert("PDF generation failed");
    });
}

  // ── Custom Toast Notification System ──────────────────────
  function showToast(title, message, type = 'warning') {
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.position = 'fixed';
      container.style.top = '24px';
      container.style.right = '24px';
      container.style.display = 'flex';
      container.style.flexDirection = 'column';
      container.style.gap = '12px';
      container.style.zIndex = '9999';
      document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const borderColor = type === 'warning' ? '#f59e0b' : (type === 'error' ? '#ef4444' : '#10b981');
    const iconName = type === 'warning' ? 'alert-triangle' : (type === 'error' ? 'x-circle' : 'check-circle');
    
    toast.style.background = '#1e293b';
    toast.style.border = '1px solid rgba(255,255,255,0.05)';
    toast.style.borderLeft = `4px solid ${borderColor}`;
    toast.style.color = '#f8fafc';
    toast.style.padding = '16px';
    toast.style.borderRadius = '8px';
    toast.style.boxShadow = '0 10px 25px -5px rgba(0,0,0,0.5)';
    toast.style.display = 'flex';
    toast.style.alignItems = 'flex-start';
    toast.style.gap = '14px';
    toast.style.width = '340px';
    toast.style.transform = 'translateX(120%)';
    toast.style.opacity = '0';
    toast.style.transition = 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
    
    toast.innerHTML = `
      <i data-lucide="${iconName}" style="width:20px;height:20px;color:${borderColor};flex-shrink:0;margin-top:2px;"></i>
      <div style="display:flex; flex-direction:column; gap:6px; flex: 1;">
        <div style="font-weight:700; font-size:0.95rem; color:#f8fafc;">${title}</div>
        <div style="font-size:0.85rem; color:#cbd5e1; line-height:1.5;">${message}</div>
      </div>
      <button class="toast-close-btn" style="background:none;border:none;color:#64748b;cursor:pointer;flex-shrink:0;padding:0;margin-left:auto;display:flex;align-items:center;justify-content:center;transition:color 0.2s;">
        <i data-lucide="x" style="width:16px;height:16px;"></i>
      </button>
    `;

    // Close logic
    const closeBtn = toast.querySelector('.toast-close-btn');
    closeBtn.addEventListener('click', () => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateX(120%)';
      setTimeout(() => toast.remove(), 400);
    });

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    // Trigger animation
    requestAnimationFrame(() => {
      setTimeout(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
      }, 50);
    });

    // Auto remove
    setTimeout(() => {
      if(document.body.contains(toast)) {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(() => { if(document.body.contains(toast)) toast.remove() }, 400);
      }
    }, 6000);
  }
});
