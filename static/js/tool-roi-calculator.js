document.addEventListener('DOMContentLoaded', () => {
    // Inputs (Sanitize function)
    const val = (id) => {
        const el = document.getElementById(id);
        return el ? parseFloat(el.value) || 0 : 0;
    };

    // Elements
    const outROI = document.getElementById('outROI');
    const outROIBox = document.getElementById('outROIBox');
    const outCPL = document.getElementById('outCPL');
    const outEmails = document.getElementById('outEmails');
    const outRevenue = document.getElementById('outRevenue');
    const outSales = document.getElementById('outSales');
    const roiStatus = document.getElementById('roiStatus');
    const roiBar = document.getElementById('roiBar');

    const fEmails = document.getElementById('fEmails');
    const fOpens = document.getElementById('fOpens');
    const fReplies = document.getElementById('fReplies');
    const fMeetings = document.getElementById('fMeetings');
    const fSales = document.getElementById('fSales');

    const rOpen = document.getElementById('rOpen');
    const rReply = document.getElementById('rReply');
    const rBook = document.getElementById('rBook');
    const rClose = document.getElementById('rClose');

    // Chart.js init
    const ctx = document.getElementById('roiChart').getContext('2d');
    let roiChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Campaign Cost', 'Profit Margin'],
            datasets: [{
                data: [500, 1000],
                backgroundColor: ['rgba(239, 68, 68, 0.4)', 'rgba(16, 185, 129, 0.4)'],
                borderColor: ['rgba(239, 68, 68, 1)', 'rgba(16, 185, 129, 1)'],
                borderWidth: 2,
                borderRadius: 4,
                hoverOffset: 12
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#94a3b8', font: { weight: 'bold', size: 11 } } },
                tooltip: { backgroundColor: '#1e293b', titleColor: '#fff', bodyColor: '#94a3b8', borderWidth: 1, borderColor: 'rgba(255,255,255,0.1)' }
            },
            cutout: '75%'
        }
    });

    function updateCalculations(isExplicit = false) {
        // Fetch raw values
        const emails = val('totalEmails');
        const openRatePct = val('openRate');
        const replyRatePct = val('replyRate');
        const bookingRatePct = val('bookingRate');
        const closingRatePct = val('closingRate');
        const dealSize = val('avgDealSize');
        const cost = Math.max(0.01, val('campaignCost')); // Prevent division by zero

        // Intermediate Calculations
        const opens = Math.round(emails * (openRatePct / 100));
        const replies = Math.round(opens * (replyRatePct / 100));
        const meetings = Math.round(replies * (bookingRatePct / 100));
        const sales = Math.round(meetings * (closingRatePct / 100));
        
        const totalRevenue = sales * dealSize;
        const netProfit = Math.max(0, totalRevenue - cost);
        const roi = (totalRevenue - cost) / cost * 100;
        const cpl = cost / Math.max(1, replies);

        // Visual Feedback (Explicit Pulse)
        if (isExplicit) {
            const btn = document.getElementById('calcBtn');
            const icon = btn.querySelector('i');
            btn.innerHTML = '<i data-lucide="loader-2" class="spin"></i> Analyzing...';
            lucide.createIcons();
            
            [outROIBox, outCPL.parentElement].forEach(el => {
                el.classList.remove('update-pulse');
                void el.offsetWidth; // Trigger reflow
                el.classList.add('update-pulse');
            });

            setTimeout(() => {
                btn.innerHTML = '<i data-lucide="zap"></i> Calculate My ROI';
                lucide.createIcons();
            }, 600);
        }

        // DOM Updates
        if(outROI) outROI.textContent = roi.toFixed(0) + '%';
        if(outCPL) outCPL.textContent = '$' + cpl.toFixed(2);
        if(outEmails) outEmails.textContent = emails.toLocaleString();
        if(outRevenue) outRevenue.textContent = '$' + totalRevenue.toLocaleString();
        if(outSales) outSales.textContent = sales.toLocaleString();

        // Funnel Updates
        if(fEmails) fEmails.textContent = emails.toLocaleString();
        if(fOpens) fOpens.textContent = opens.toLocaleString();
        if(fReplies) fReplies.textContent = replies.toLocaleString();
        if(fMeetings) fMeetings.textContent = meetings.toLocaleString();
        if(fSales) fSales.textContent = sales.toLocaleString();

        if(rOpen) rOpen.textContent = openRatePct.toFixed(0) + '%';
        if(rReply) rReply.textContent = replyRatePct.toFixed(1) + '%';
        if(rBook) rBook.textContent = bookingRatePct.toFixed(0) + '%';
        if(rClose) rClose.textContent = closingRatePct.toFixed(0) + '%';

        // ROI Performance Status
        let status = 'Negative';
        let color = '#ef4444';
        let barW = 5;

        if (roi >= 300) { status = 'Excellent'; color = '#10b981'; barW = 100; }
        else if (roi >= 150) { status = 'Good'; color = '#34d399'; barW = 75; }
        else if (roi >= 50) { status = 'Moderate'; color = '#3b82f6'; barW = 45; }
        else if (roi > 0) { status = 'Low'; color = '#f59e0b'; barW = 20; }

        if(roiStatus) {
            roiStatus.textContent = status;
            roiStatus.style.color = color;
        }
        if(roiBar) {
            roiBar.style.width = barW + '%';
            roiBar.style.background = color;
        }

        // ROI Card Glow
        if(outROIBox) {
            if (roi > 0) {
                outROIBox.style.boxShadow = `0 10px 40px -10px ${color}44`;
                outROIBox.style.borderColor = `${color}44`;
            } else {
                outROIBox.style.boxShadow = 'none';
                outROIBox.style.borderColor = 'rgba(239, 68, 68, 0.2)';
            }
        }

        // Chart Update
        roiChart.data.datasets[0].data = [cost, Math.max(0, netProfit)];
        roiChart.update();
    }

    // Attach Listeners
    ['totalEmails', 'openRate', 'replyRate', 'bookingRate', 'closingRate', 'avgDealSize', 'campaignCost'].forEach(id => {
        const el = document.getElementById(id);
        if(el) el.addEventListener('input', () => updateCalculations(false));
    });

    const calcBtn = document.getElementById('calcBtn');
    if(calcBtn) calcBtn.addEventListener('click', () => updateCalculations(true));

    // Initial Trigger
    updateCalculations();
});
