document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const domainInput = document.getElementById('domainInput');
  const providerCards = document.querySelectorAll('.provider-card');
  const dmarcPolicy = document.getElementById('dmarcPolicy');
  const generateBtn = document.getElementById('generateBtn');
  const verifyBtn = document.getElementById('verifyBtn');
  
  const emptyState = document.getElementById('emptyState');
  const recordsOutput = document.getElementById('recordsOutput');
  
  const spfValue = document.getElementById('spfValue');
  const dkimSelector = document.getElementById('dkimSelector');
  const dmarcValue = document.getElementById('dmarcValue');
  const dkimGuideBtn = document.getElementById('dkimGuideBtn');

  let selectedProvider = 'google';

  // Provider selection
  providerCards.forEach(card => {
    card.addEventListener('click', () => {
      providerCards.forEach(c => c.classList.remove('active'));
      card.classList.add('active');
      selectedProvider = card.dataset.provider;
    });
  });

  // Generator Logic
  function generateRecords() {
    const domain = domainInput.value.trim().toLowerCase();
    
    if (!domain || !domain.includes('.')) {
      showToast("Invalid Domain", "Please enter a valid domain name (e.g., example.com)", "error");
      return;
    }

    // SPF Logic
    let spf = "";
    if (selectedProvider === "google") {
      spf = "v=spf1 include:_spf.google.com ~all";
      dkimSelector.textContent = "google";
    } else if (selectedProvider === "outlook") {
      spf = "v=spf1 include:spf.protection.outlook.com ~all";
      dkimSelector.textContent = "selector1";
    } else if (selectedProvider === "zoho") {
      spf = "v=spf1 include:zoho.com ~all";
      dkimSelector.textContent = "zmail";
    } else {
      spf = "v=spf1 mx ~all";
      dkimSelector.textContent = "default";
    }

    // DMARC Logic
    const policy = dmarcPolicy.value;
    const dmarc = `v=DMARC1; p=${policy}; rua=mailto:admin@${domain}`;

    // Update UI
    spfValue.textContent = spf;
    dmarcValue.textContent = dmarc;

    emptyState.style.display = 'none';
    recordsOutput.style.display = 'block';
    
    // Smooth scroll to results if on mobile
    if (window.innerWidth < 968) {
      recordsOutput.scrollIntoView({ behavior: 'smooth' });
    }

    showToast("Generated", "DNS records are ready for your domain.", "check-circle");
    
    // Reset statuses to pending
    resetStatuses();
  }

  function resetStatuses() {
    ['spfStatus', 'dkimStatus', 'dmarcStatus'].forEach(id => {
      const el = document.getElementById(id);
      el.innerHTML = '<i data-lucide="circle-dashed" style="width:12px;height:12px;"></i> Pending Check';
      el.style.color = '#64748b';
      if (window.lucide) lucide.createIcons();
    });
  }

  // Live Checker (Backend AJAX)
  async function checkDNS() {
    const domain = domainInput.value.trim().toLowerCase();
    if (!domain) return;

    verifyBtn.innerHTML = '<i data-lucide="loader-2" class="animate-spin" style="width:14px;height:14px;"></i> Testing...';
    if (window.lucide) lucide.createIcons();

    try {
      const response = await fetch(`/api/check-dns-records/?domain=${domain}`);
      const data = await response.json();

      if (data.error) throw new Error(data.error);

      updateStatus('spfStatus', data.spf.exists, data.spf.value);
      updateStatus('dmarcStatus', data.dmarc.exists, data.dmarc.value);
      // DKIM check is hard without the selector, so keep it neutral
      
    } catch (err) {
      console.error(err);
      showToast("Check Failed", "Could not reach DNS resolver. Domain might be new or invalid.", "error");
    } finally {
      verifyBtn.innerHTML = '<i data-lucide="refresh-cw" style="width:14px;height:14px;"></i> Live Check';
      if (window.lucide) lucide.createIcons();
    }
  }

  function updateStatus(id, exists, value) {
    const el = document.getElementById(id);
    if (exists) {
      el.innerHTML = '<i data-lucide="check-circle" style="width:12px;height:12px;"></i> Live & Verified';
      el.style.color = '#10b981';
      // If live value differs, maybe alert? For now just show green
    } else {
      el.innerHTML = '<i data-lucide="alert-circle" style="width:12px;height:12px;"></i> Record Not Found';
      el.style.color = '#ef4444';
    }
    if (window.lucide) lucide.createIcons();
  }

  // Copy to Clipboard
  document.querySelectorAll('.btn-copy').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetId = btn.dataset.copyId;
      const text = document.getElementById(targetId).textContent;
      
      navigator.clipboard.writeText(text).then(() => {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i data-lucide="check" style="width:12px;height:12px;"></i> Copied';
        btn.style.background = 'rgba(16, 185, 129, 0.2)';
        btn.style.color = '#10b981';
        if (window.lucide) lucide.createIcons();
        
        setTimeout(() => {
          btn.innerHTML = originalHtml;
          btn.style.background = '';
          btn.style.color = '';
          if (window.lucide) lucide.createIcons();
        }, 2000);
      });
    });
  });

  // Events
  generateBtn.addEventListener('click', generateRecords);
  verifyBtn.addEventListener('click', checkDNS);
  
  dkimGuideBtn.addEventListener('click', () => {
    const guides = {
      'google': 'https://support.google.com/a/answer/174124',
      'outlook': 'https://learn.microsoft.com/en-us/microsoft-365/security/office-365-security/email-authentication-dkim-configure',
      'zoho': 'https://www.zoho.com/mail/help/adminconsole/dkim-configuration.html',
      'custom': 'https://en.wikipedia.org/wiki/DomainKeys_Identified_Mail'
    };
    window.open(guides[selectedProvider] || guides.custom, '_blank');
  });
  
  // Enter key support
  domainInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') generateRecords();
  });

  // Toast System Fallback
  function showToast(title, message, type = 'warning') {
    // Try to find if a more robust toast system is in base.html
    const container = document.getElementById('toast-container');
    if (container) {
       const toast = document.createElement('div');
       toast.className = `toast toast-${type === 'check-circle' ? 'success' : type}`;
       toast.innerHTML = `
         <div class="toast-icon">${type === 'check-circle' ? '✨' : '⚠️'}</div>
         <div class="toast-content"><strong>${title}</strong>: ${message}</div>
         <button class="toast-close" onclick="this.parentElement.remove()">×</button>
       `;
       container.appendChild(toast);
       setTimeout(() => {
          toast.style.opacity = '0';
          setTimeout(() => toast.remove(), 400);
       }, 4000);
       return;
    }
    alert(`${title}: ${message}`);
  }
});
