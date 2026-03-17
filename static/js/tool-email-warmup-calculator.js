window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) {
    lucide.createIcons();
  }

  // ── Elements ──────────────────────────────────────────────
  const targetVolumeSlider = document.getElementById('targetVolume');
  const targetVolumeVal = document.getElementById('targetVolumeVal');
  const domainReputationSelect = document.getElementById('domainReputation');
  const strategyBtns = document.querySelectorAll('.strategy-btn');
  const calculateBtn = document.getElementById('calculateBtn');
  const downloadCsvBtn = document.getElementById('downloadCsvBtn');
  
  const emptyState = document.getElementById('emptyState');
  const scheduleResults = document.getElementById('scheduleResults');
  const scheduleTableBody = document.getElementById('scheduleTableBody');
  
  const daysToTargetEl = document.getElementById('daysToTarget');
  const startingVolEl = document.getElementById('startingVol');
  const dailyIncEl = document.getElementById('dailyInc');

  // ── State ─────────────────────────────────────────────────
  let selectedStrategy = 'recommended';
  let generatedData = [];

  // ── Event Listeners ───────────────────────────────────────
  targetVolumeSlider.addEventListener('input', (e) => {
    targetVolumeVal.textContent = `${e.target.value} emails/day`;
  });

  strategyBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      strategyBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedStrategy = btn.getAttribute('data-strategy');
    });
  });

  calculateBtn.addEventListener('click', generateSchedule);
  downloadCsvBtn.addEventListener('click', downloadCsv);

  // ── Logic ─────────────────────────────────────────────────
  function generateSchedule() {
    const targetVolume = parseInt(targetVolumeSlider.value);
    const domainReputation = domainReputationSelect.value;
    
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

    // 3. Generate Schedule Array
    generatedData = [];
    let currentVol = startVol;
    let day = 1;

    while (currentVol < targetVolume) {
      // For the first few days, warmup percentage is 100%
      // As volume climbs, warmup percentage drops to maintain ~30-40% at max capacity
      let warmupPercent = 1.0;
      if (currentVol > 10) warmupPercent = 0.8;
      if (currentVol > 20) warmupPercent = 0.5;
      if (currentVol >= targetVolume * 0.8) warmupPercent = 0.3; // Ramping down to long-term safe percentage
      
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

      currentVol += increment;
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

    renderResults(startVol, increment, day);
  }

  function renderResults(startVol, increment, totalDays) {
    emptyState.style.display = 'none';
    scheduleResults.style.display = 'block';
    downloadCsvBtn.style.display = 'inline-flex';

    daysToTargetEl.textContent = totalDays;
    startingVolEl.textContent = startVol;
    dailyIncEl.textContent = `+${increment}/day`;

    // Render Table
    scheduleTableBody.innerHTML = generatedData.map(row => `
      <tr>
        <td class="val-bold">Day ${row.day}</td>
        <td>${row.warmupEmails} emails</td>
        <td class="val-bold">${row.totalEmails} emails</td>
        <td>${row.statusHtml}</td>
      </tr>
    `).join('');

    if (window.lucide) {
      lucide.createIcons();
    }
  }

  function downloadCsv() {
    if (generatedData.length === 0) return;
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Day,Warm-up Emails,Total Emails,Status\n";
    
    generatedData.forEach(row => {
      csvContent += `${row.day},${row.warmupEmails},${row.totalEmails},${row.statusText}\n`;
    });
    
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "LeadNexus_Warmup_Schedule.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
});
