/* ═══════════════════════════════════════════════════════════
   DataScraper Pro — Frontend JavaScript
   ═══════════════════════════════════════════════════════════ */

// ── CSRF Token helper (for Django POST requests) ──────────
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let c of cookies) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrfToken = getCookie('csrftoken');

// ── API helper ────────────────────────────────────────────
async function apiCall(url, method = 'GET', body = null) {
    const opts = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken,
        },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(err.error || err.detail || JSON.stringify(err));
    }
    return res.json();
}

// ── Tab switching ─────────────────────────────────────────
function initTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabGroup = btn.closest('.tabs-container');
            const target = btn.dataset.tab;

            tabGroup.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            tabGroup.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            btn.classList.add('active');
            const content = tabGroup.querySelector(`#${target}`);
            if (content) content.classList.add('active');
        });
    });
}

// ── Loading overlay ───────────────────────────────────────
function showLoading(message = 'Processing...') {
    let overlay = document.getElementById('loadingOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'loadingOverlay';
        overlay.className = 'loading-overlay';
        overlay.innerHTML = `<div class="spinner"></div><p>${message}</p>`;
        document.body.appendChild(overlay);
    }
    overlay.querySelector('p').textContent = message;
    overlay.classList.add('show');
}

function hideLoading() {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) overlay.classList.remove('show');
}

// ── Website Scraper Form ──────────────────────────────────
function initWebsiteScraper() {
    const form = document.getElementById('websiteScraperForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const url = document.getElementById('websiteUrl').value.trim();
        const scrapeContact = document.getElementById('scrapeContact').checked;
        const maxPages = parseInt(document.getElementById('maxContactPages').value) || 3;

        if (!url) return;

        showLoading('Starting website scrape...');

        try {
            const job = await apiCall('/api/jobs/', 'POST', {
                url: url,
                scrape_contact: scrapeContact,
                max_contact_pages: maxPages,
            });

            showLoading('Scraping in progress...');
            pollWebsiteJob(job.id);
        } catch (err) {
            hideLoading();
            showNotification('Error: ' + err.message, 'error');
        }
    });
}

async function pollWebsiteJob(jobId) {
    const maxAttempts = 120;
    for (let i = 0; i < maxAttempts; i++) {
        try {
            const status = await apiCall(`/api/jobs/${jobId}/status/`);

            if (status.status === 'completed') {
                hideLoading();
                window.location.href = `/website-job/${jobId}/`;
                return;
            } else if (status.status === 'failed') {
                hideLoading();
                showNotification('Scrape failed: ' + (status.error_message || 'Unknown error'), 'error');
                return;
            }
        } catch (err) {
            // continue polling
        }
        await sleep(2000);
    }
    hideLoading();
    showNotification('Scrape timed out. Check the jobs list for status.', 'warning');
}

// ── LinkedIn Scraper Form ─────────────────────────────────
function initLinkedInScraper() {
    const form = document.getElementById('linkedinScraperForm');
    if (!form) return;

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const niche = document.getElementById('niche').value.trim();
        const maxProfiles = parseInt(document.getElementById('maxProfiles').value) || 50;
        const scrapeWebsites = document.getElementById('scrapeWebsites').checked;
        const headless = document.getElementById('headless').checked;
        const storedAccount = document.getElementById('storedAccount').value;

        if (!niche) return;

        showLoading('Starting LinkedIn scrape — Chrome is launching...');

        try {
            const job = await apiCall('/api/linkedin/jobs/', 'POST', {
                niche: niche,
                max_profiles: maxProfiles,
                scrape_websites: scrapeWebsites,
                headless: headless,
                account: storedAccount || null,
            });

            // Redirect to detail page which will poll
            window.location.href = `/linkedin-job/${job.id}/`;
        } catch (err) {
            hideLoading();
            showNotification('Error: ' + err.message, 'error');
        }
    });
}

// ── LinkedIn Job Polling (on detail page) ─────────────────
function initLinkedInJobPolling() {
    const progressEl = document.getElementById('jobProgress');
    if (!progressEl) return;

    const jobId = progressEl.dataset.jobId;
    const jobStatus = progressEl.dataset.jobStatus;

    if (jobStatus === 'pending' || jobStatus === 'running') {
        pollLinkedInJob(jobId);
    }
}

async function pollLinkedInJob(jobId) {
    const statusEl = document.getElementById('statusBadge');
    const progressBar = document.getElementById('progressBarFill');
    const progressText = document.getElementById('progressText');

    while (true) {
        try {
            const data = await apiCall(`/api/linkedin/jobs/${jobId}/status/`);

            // Update progress bar
            const pct = data.max_profiles > 0
                ? Math.round((data.progress / data.max_profiles) * 100)
                : 0;

            if (progressBar) progressBar.style.width = pct + '%';
            if (progressText) progressText.textContent = `${data.progress} / ${data.max_profiles} profiles (${pct}%)`;

            // Update status badge
            if (statusEl) {
                statusEl.className = `badge badge-${data.status}`;
                statusEl.innerHTML = `<span class="badge-dot"></span> ${data.status}`;
            }

            if (data.status === 'completed' || data.status === 'failed') {
                // Reload to show final results
                setTimeout(() => window.location.reload(), 1000);
                return;
            }
        } catch (err) {
            console.error('Poll error:', err);
        }
        await sleep(3000);
    }
}

// ── Delete Job ────────────────────────────────────────────
async function deleteWebsiteJob(jobId) {
    if (!confirm('Delete this job and its results?')) return;
    try {
        await fetch(`/api/jobs/${jobId}/delete/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken },
        });
        window.location.href = '/jobs/';
    } catch (err) {
        showNotification('Delete failed: ' + err.message, 'error');
    }
}

async function deleteLinkedInJob(jobId) {
    if (!confirm('Delete this job and all its scraped profiles?')) return;
    try {
        await fetch(`/api/linkedin/jobs/${jobId}/delete/`, {
            method: 'DELETE',
            headers: { 'X-CSRFToken': csrfToken },
        });
        window.location.href = '/jobs/';
    } catch (err) {
        showNotification('Delete failed: ' + err.message, 'error');
    }
}

// ── Notification Toast ────────────────────────────────────
function showNotification(message, type = 'info') {
    const container = document.getElementById('notificationContainer') || createNotifContainer();
    const notif = document.createElement('div');
    notif.className = `alert alert-${type} fade-in`;
    notif.innerHTML = `<span>${getNotifIcon(type)}</span> ${message}`;
    container.appendChild(notif);
    setTimeout(() => {
        notif.style.opacity = '0';
        notif.style.transform = 'translateX(100%)';
        setTimeout(() => notif.remove(), 300);
    }, 5000);
}

function createNotifContainer() {
    const c = document.createElement('div');
    c.id = 'notificationContainer';
    c.style.cssText = 'position:fixed; top:80px; right:20px; z-index:9999; display:flex; flex-direction:column; gap:8px; max-width:400px;';
    document.body.appendChild(c);
    return c;
}

function getNotifIcon(type) {
    const icons = {
        success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️',
    };
    return icons[type] || 'ℹ️';
}

// ── Utilities ─────────────────────────────────────────────
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Copied to clipboard!', 'success');
    });
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString();
}

// ── Init ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initWebsiteScraper();
    initLinkedInScraper();
    initLinkedInJobPolling();

    // Animate stat cards on scroll
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('slide-up');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.stat-card, .card, .action-card').forEach(el => {
        observer.observe(el);
    });

    // Auto-hide Django Toasts
    document.querySelectorAll('.toast').forEach(toast => {
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(50px)';
            setTimeout(() => toast.remove(), 500);
        }, 5000);
    });
});
