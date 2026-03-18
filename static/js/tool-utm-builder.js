document.addEventListener('DOMContentLoaded', () => {
    // Inputs
    const websiteUrl = document.getElementById('websiteUrl');
    const campaignSource = document.getElementById('campaignSource');
    const campaignMedium = document.getElementById('campaignMedium');
    const campaignName = document.getElementById('campaignName');
    const campaignTerm = document.getElementById('campaignTerm');
    const campaignContent = document.getElementById('campaignContent');

    // Outputs
    const generatedUrl = document.getElementById('generatedUrl');
    const copyBtn = document.getElementById('copyBtn');
    const clearBtn = document.getElementById('clearBtn');
    const historySection = document.getElementById('historySection');
    const historyBody = document.getElementById('historyBody');
    const noHistory = document.getElementById('noHistory');
    const clearHistoryBtn = document.getElementById('clearHistory');
    const conversionModal = document.getElementById('conversionModal');

    // Branding & Counter
    let copyCount = parseInt(localStorage.getItem('utm_copy_count') || '0');
    const previewSource = document.getElementById('previewSource');
    const previewMedium = document.getElementById('previewMedium');
    const previewName = document.getElementById('previewName');

    const inputs = [websiteUrl, campaignSource, campaignMedium, campaignName, campaignTerm, campaignContent];

    // Initialize History from LocalStorage
    let history = JSON.parse(localStorage.getItem('utm_builder_history') || '[]');

    function buildUtmUrl() {
        let baseUrl = websiteUrl.value.trim();
        if (!baseUrl) {
            generatedUrl.textContent = "Your generated link will appear here...";
            generatedUrl.style.color = "#64748b";
            previewSource.textContent = "---";
            previewMedium.textContent = "---";
            previewName.textContent = "---";
            return;
        }

        generatedUrl.style.color = "#e2e8f0";
        if (!baseUrl.startsWith('http://') && !baseUrl.startsWith('https://')) {
            baseUrl = 'https://' + baseUrl;
        }

        try {
            const urlObj = new URL(baseUrl);
            const params = new URLSearchParams(urlObj.search);

            if (campaignSource.value.trim()) params.set('utm_source', campaignSource.value.trim());
            if (campaignMedium.value.trim()) params.set('utm_medium', campaignMedium.value.trim());
            if (campaignName.value.trim()) params.set('utm_campaign', campaignName.value.trim());
            if (campaignTerm.value.trim()) params.set('utm_term', campaignTerm.value.trim());
            if (campaignContent.value.trim()) params.set('utm_content', campaignContent.value.trim());

            urlObj.search = params.toString();
            generatedUrl.textContent = urlObj.toString();
            
            previewSource.textContent = campaignSource.value.trim() || "---";
            previewMedium.textContent = campaignMedium.value.trim() || "---";
            previewName.textContent = campaignName.value.trim() || "---";

        } catch (e) {
            generatedUrl.textContent = "Please enter a valid URL.";
            generatedUrl.style.color = "#ef4444";
        }
    }

    function saveToHistory(url, name, source, medium) {
        // Prevent duplicate recent entries
        if (history.length > 0 && history[0].url === url) return;

        const entry = {
            id: Date.now(),
            url,
            name: name || 'Unnamed Campaign',
            source: source || 'N/A',
            medium: medium || 'N/A',
            date: new Date().toLocaleString(),
            clicks: Math.floor(Math.random() * 50) + 1 // Simulated visual data for SaaS feel
        };

        history.unshift(entry);
        if (history.length > 10) history.pop(); // Keep last 10
        localStorage.setItem('utm_builder_history', JSON.stringify(history));
        renderHistory();
    }

    function renderHistory() {
        if (history.length === 0) {
            historySection.style.display = 'none';
            noHistory.style.display = 'block';
            return;
        }

        historySection.style.display = 'block';
        noHistory.style.display = 'none';
        historyBody.innerHTML = '';

        history.forEach(item => {
            const row = document.createElement('tr');
            row.style.borderBottom = '1px solid rgba(255,255,255,0.03)';
            row.innerHTML = `
                <td style="padding: 16px 24px;">
                    <div style="color: #fff; font-weight: 700;">${item.name}</div>
                    <div style="font-size: 0.7rem; color: #64748b;">${item.date}</div>
                </td>
                <td style="padding: 16px 24px;">
                    <span style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;">${item.source}</span>
                    <span style="color: #64748b; margin: 0 4px;">/</span>
                    <span style="color: #cbd5e1;">${item.medium}</span>
                </td>
                <td style="padding: 16px 24px;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="background: rgba(239, 68, 68, 0.1); color: #ef4444; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700;">MANUAL</span>
                        <a href="/register/" style="color: #10b981; font-size: 0.7rem; font-weight: 800; text-decoration: none; display: flex; align-items: center; gap: 4px;">
                            <i data-lucide="zap" style="width: 10px; height: 10px;"></i>
                            Automate ROI
                        </a>
                    </div>
                </td>
                <td style="padding: 16px 24px; text-align: right;">
                    <div style="display: flex; justify-content: flex-end; gap: 8px;">
                        <button class="history-copy" data-url="${item.url}" style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #fff; padding: 6px; border-radius: 6px; cursor: pointer;">
                            <i data-lucide="copy" style="width: 14px; height: 14px;"></i>
                        </button>
                        <button class="history-del" data-id="${item.id}" style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); color: #ef4444; padding: 6px; border-radius: 6px; cursor: pointer;">
                            <i data-lucide="trash-2" style="width: 14px; height: 14px;"></i>
                        </button>
                    </div>
                </td>
            `;
            historyBody.appendChild(row);
        });

        // Re-init icons for new rows
        lucide.createIcons();

        // Attach listeners to new buttons
        document.querySelectorAll('.history-copy').forEach(btn => {
            btn.addEventListener('click', () => {
                navigator.clipboard.writeText(btn.getAttribute('data-url'));
                const icon = btn.querySelector('i');
                btn.innerHTML = '<i data-lucide="check" style="width:14px;height:14px;"></i>';
                btn.style.borderColor = '#10b981';
                btn.style.color = '#10b981';
                lucide.createIcons();
                setTimeout(() => {
                    btn.innerHTML = '<i data-lucide="copy" style="width:14px;height:14px;"></i>';
                    btn.style.borderColor = '';
                    btn.style.color = '';
                    lucide.createIcons();
                }, 2000);
            });
        });

        document.querySelectorAll('.history-del').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = parseInt(btn.getAttribute('data-id'));
                history = history.filter(h => h.id !== id);
                localStorage.setItem('utm_builder_history', JSON.stringify(history));
                renderHistory();
            });
        });
    }

    function copyToClipboard() {
        const urlToCopy = generatedUrl.textContent;
        if (!urlToCopy || urlToCopy.includes('will appear here') || urlToCopy.includes('valid URL')) {
            return;
        }

        navigator.clipboard.writeText(urlToCopy).then(() => {
            const originalHtml = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i data-lucide="check" style="width:16px;height:16px;"></i> Copied!';
            copyBtn.style.background = '#10b981';
            lucide.createIcons();
            
            // Increment & Trigger Modal
            copyCount++;
            localStorage.setItem('utm_copy_count', copyCount);
            if (copyCount === 3 || copyCount === 7 || copyCount === 12) {
                if(conversionModal) conversionModal.style.display = 'flex';
            }

            // Save to Analysis History
            saveToHistory(
                urlToCopy, 
                campaignName.value.trim(), 
                campaignSource.value.trim(), 
                campaignMedium.value.trim()
            );
            
            setTimeout(() => {
                copyBtn.innerHTML = originalHtml;
                copyBtn.style.background = '';
                lucide.createIcons();
            }, 2000);
        });
    }

    function clearInputs() {
        inputs.forEach(input => input.value = '');
        buildUtmUrl();
        previewSource.textContent = "---";
        previewMedium.textContent = "---";
        previewName.textContent = "---";
    }

    // Attach listeners
    inputs.forEach(input => {
        input.addEventListener('input', buildUtmUrl);
    });

    if (copyBtn) copyBtn.addEventListener('click', copyToClipboard);
    if (clearBtn) clearBtn.addEventListener('click', clearInputs);
    
    if (clearHistoryBtn) {
        clearHistoryBtn.addEventListener('click', () => {
            if (confirm('Clear all campaign history?')) {
                history = [];
                localStorage.setItem('utm_builder_history', JSON.stringify(history));
                renderHistory();
            }
        });
    }

    // Initial run
    buildUtmUrl();
    renderHistory();
});
