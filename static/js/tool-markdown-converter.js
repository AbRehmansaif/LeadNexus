// ─────────────────────────────────────────────────────────────
//  Markdown ↔ HTML Converter Tool — Client Logic
//  Static file: static/js/tool-markdown-converter.js
// ─────────────────────────────────────────────────────────────

// ── FAQ Accordion ──────────────────────────────────────────────
function toggleFaq(id) {
  const item = document.getElementById(id);
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
  if (!isOpen) item.classList.add('open');
}

// ── State ──────────────────────────────────────────────────────
let currentMode = 'md2html'; // 'md2html' | 'html2md' | 'text2html' | 'text2md'
let previewVisible = false;

// ── Example content ────────────────────────────────────────────
const MARKDOWN_EXAMPLE = `# Welcome to LeadNexus Converter

This is a **bold statement** and this is *italic text*.

## Key Features

- ✅ Lightning fast conversion
- ✅ 100% private — runs in your browser
- ✅ Supports full Markdown spec

## Code Example

\`\`\`javascript
const result = convertMarkdown("# Hello");
console.log(result); // <h1>Hello</h1>
\`\`\`

## Table Support

| Feature | Supported |
|---------|-----------|
| Headings | ✅ Yes |
| Tables | ✅ Yes |
| Code Blocks | ✅ Yes |

> "The best tools are the ones that get out of your way." — LeadNexus

[Visit LeadNexus →](https://leadnexus.com)`;

const HTML_EXAMPLE = `<h1>Welcome to LeadNexus Converter</h1>
<p>This is a <strong>bold statement</strong> and this is <em>italic text</em>.</p>
<h2>Key Features</h2>
<ul>
  <li>✅ Lightning fast conversion</li>
  <li>✅ 100% private — runs in your browser</li>
  <li>✅ Supports full Markdown spec</li>
</ul>
<h2>Code Example</h2>
<pre><code>const result = convertMarkdown("# Hello");
console.log(result); // &lt;h1&gt;Hello&lt;/h1&gt;</code></pre>
<blockquote>
  <p>"The best tools are the ones that get out of your way." — LeadNexus</p>
</blockquote>
<p><a href="https://leadnexus.com">Visit LeadNexus →</a></p>`;

const TEXT_EXAMPLE = `LeadNexus: The B2B Growth Engine

LeadNexus helps sales teams find, engage, and close more deals with less effort. Whether you're sending cold emails or prospecting on LinkedIn, LeadNexus automates the heavy lifting.

KEY FEATURES

- Automated email outreach with smart follow-ups
- LinkedIn prospecting and lead discovery
- Real-time lead intelligence and scoring
- Built-in CRM for pipeline management
- A/B testing for subject lines and copy

HOW IT WORKS

1. Import or find leads using our prospecting tools
2. Build your outreach sequence with templates
3. Launch your campaign and track replies in real time
4. Close deals faster with AI-powered recommendations

Get started at https://leadnexus.com or email us at hello@leadnexus.com`;

// ── Mode Config ────────────────────────────────────────────────
const MODE_CONFIG = {
  md2html:   { inputLabel: 'Markdown Input',   outputLabel: 'HTML Output',     placeholder: 'Paste your Markdown here...\n\n# Hello World\nThis is **bold** and *italic* text.\n\n- Item one\n- Item two' },
  html2md:   { inputLabel: 'HTML Input',        outputLabel: 'Markdown Output', placeholder: 'Paste your HTML here...\n\n<h1>Hello World</h1>\n<p>This is <strong>bold</strong> text.</p>' },
  text2html: { inputLabel: 'Plain Text Input',  outputLabel: 'HTML Output',     placeholder: 'Paste plain text here...\n\nParagraphs separated by a blank line become <p> tags.\n\nBullet lists, numbered lists, URLs and email addresses are auto-detected.' },
  text2md:   { inputLabel: 'Plain Text Input',  outputLabel: 'Markdown Output', placeholder: 'Paste plain text here...\n\nParagraphs, lists, URLs and email addresses will be converted to proper Markdown syntax.' },
};

// ── Mode Switching ─────────────────────────────────────────────
function setMode(mode) {
  currentMode = mode;
  document.getElementById('inputArea').value  = '';
  document.getElementById('outputArea').value = '';
  document.getElementById('previewArea').innerHTML = '';
  ['modeMarkdownToHtml','modeHtmlToMarkdown','modeTextToHtml','modeTextToMarkdown'].forEach(id => {
    document.getElementById(id).classList.remove('active');
  });
  const idMap = { md2html:'modeMarkdownToHtml', html2md:'modeHtmlToMarkdown', text2html:'modeTextToHtml', text2md:'modeTextToMarkdown' };
  document.getElementById(idMap[mode]).classList.add('active');
  const cfg = MODE_CONFIG[mode];
  document.getElementById('inputLabel').textContent  = cfg.inputLabel;
  document.getElementById('outputLabel').textContent = cfg.outputLabel;
  document.getElementById('inputArea').placeholder   = cfg.placeholder;
  if (previewVisible && mode !== 'md2html' && mode !== 'text2html') togglePreview();
  if (window.lucide) lucide.createIcons();
}

// ── Convert ────────────────────────────────────────────────────
function convert() {
  const input = document.getElementById('inputArea').value.trim();
  if (!input) { showNotification('Please paste some content first!', 'warning'); return; }
  let output = '';
  if (currentMode === 'md2html') {
    output = markdownToHtml(input);
    if (previewVisible) {
      document.getElementById('previewArea').innerHTML = output;
      if (window.lucide) lucide.createIcons();
    }
  } else if (currentMode === 'html2md') {
    output = htmlToMarkdown(input);
  } else if (currentMode === 'text2html') {
    output = plainTextToHtml(input);
    if (previewVisible) {
      document.getElementById('previewArea').innerHTML = output;
      if (window.lucide) lucide.createIcons();
    }
  } else if (currentMode === 'text2md') {
    output = plainTextToMarkdown(input);
  }
  document.getElementById('outputArea').value = output;
}

// ── Markdown → HTML ────────────────────────────────────────────
function markdownToHtml(md) {
  marked.setOptions({ gfm: true, breaks: false, pedantic: false });
  return marked.parse(md);
}

// ── HTML → Markdown ────────────────────────────────────────────
function htmlToMarkdown(html) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, 'text/html');

  function processNode(node) {
    if (node.nodeType === Node.TEXT_NODE) return node.textContent;
    if (node.nodeType !== Node.ELEMENT_NODE) return '';
    const tag = node.tagName.toLowerCase();
    const children = Array.from(node.childNodes).map(processNode).join('');
    switch (tag) {
      case 'h1': return `# ${children}\n\n`;
      case 'h2': return `## ${children}\n\n`;
      case 'h3': return `### ${children}\n\n`;
      case 'h4': return `#### ${children}\n\n`;
      case 'h5': return `##### ${children}\n\n`;
      case 'h6': return `###### ${children}\n\n`;
      case 'p': return `${children}\n\n`;
      case 'strong': case 'b': return `**${children}**`;
      case 'em': case 'i': return `*${children}*`;
      case 'code':
        if (node.parentElement && node.parentElement.tagName.toLowerCase() === 'pre') return children;
        return `\`${children}\``;
      case 'pre': {
        const codeEl = node.querySelector('code');
        const langClass = codeEl ? (codeEl.className.match(/language-(\w+)/) || [])[1] || '' : '';
        const codeText = codeEl ? codeEl.textContent : children;
        return `\`\`\`${langClass}\n${codeText}\n\`\`\`\n\n`;
      }
      case 'blockquote':
        return children.split('\n').map(l => l ? `> ${l}` : '>').join('\n') + '\n\n';
      case 'br': return '\n';
      case 'hr': return '---\n\n';
      case 'a': return `[${children}](${node.getAttribute('href') || ''})`;
      case 'img': return `![${node.getAttribute('alt') || ''}](${node.getAttribute('src') || ''})`;
      case 'ul':
        return Array.from(node.children).map(li => {
          return `- ${Array.from(li.childNodes).map(processNode).join('').replace(/\n+$/, '')}`;
        }).join('\n') + '\n\n';
      case 'ol':
        return Array.from(node.children).map((li, i) => {
          return `${i + 1}. ${Array.from(li.childNodes).map(processNode).join('').replace(/\n+$/, '')}`;
        }).join('\n') + '\n\n';
      case 'li': return children;
      case 'table': {
        const rows = Array.from(node.querySelectorAll('tr'));
        if (!rows.length) return children;
        const header = Array.from(rows[0].querySelectorAll('th,td')).map(c => c.textContent.trim());
        let md = `| ${header.join(' | ')} |\n| ${header.map(() => '---').join(' | ')} |\n`;
        rows.slice(1).forEach(row => {
          const cells = Array.from(row.querySelectorAll('td')).map(c => c.textContent.trim());
          md += `| ${cells.join(' | ')} |\n`;
        });
        return md + '\n';
      }
      case 'thead': case 'tbody': case 'tr': case 'th': case 'td': return children;
      case 'div': case 'section': case 'article': case 'main': return children + '\n';
      case 'span': return children;
      default: return children;
    }
  }
  return processNode(doc.body).replace(/\n{3,}/g, '\n\n').trim();
}

// ── Plain Text → HTML ──────────────────────────────────────────
function plainTextToHtml(text) {
  function autoLink(s) {
    s = s.replace(/(https?:\/\/[^\s<>"']+)/g, '<a href="$1">$1</a>');
    s = s.replace(/\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b/g, '<a href="mailto:$1">$1</a>');
    return s;
  }
  function isBulletBlock(lines) { return lines.filter(l => l.trim()).every(l => /^[\-\*•]\s+/.test(l.trim())); }
  function isOrderedBlock(lines) { return lines.filter(l => l.trim()).every(l => /^\d+[.):]\s+/.test(l.trim())); }

  const blocks = text.split(/\n{2,}/);
  return blocks.map(block => {
    const lines = block.split('\n');
    const nonEmpty = lines.filter(l => l.trim());
    if (!nonEmpty.length) return '';
    if (isBulletBlock(lines)) {
      const items = nonEmpty.map(l => `  <li>${autoLink(l.replace(/^[\-\*•]\s+/, '').trim())}</li>`);
      return `<ul>\n${items.join('\n')}\n</ul>`;
    }
    if (isOrderedBlock(lines)) {
      const items = nonEmpty.map(l => `  <li>${autoLink(l.replace(/^\d+[.):]\s+/, '').trim())}</li>`);
      return `<ol>\n${items.join('\n')}\n</ol>`;
    }
    if (nonEmpty.length === 1) {
      const line = nonEmpty[0].trim();
      if (line.length >= 3 && line.length <= 72 && line === line.toUpperCase() && /[A-Z]/.test(line)) {
        return `<h2>${line}</h2>`;
      }
      return `<p>${autoLink(line)}</p>`;
    }
    const avgLen = nonEmpty.reduce((s, l) => s + l.trim().length, 0) / nonEmpty.length;
    const hasShortLines = nonEmpty.some(l => l.trim().length < 40);
    if (!hasShortLines && avgLen > 60) {
      return `<p>${autoLink(nonEmpty.map(l => l.trim()).join(' '))}</p>`;
    }
    return `<p>${nonEmpty.map(l => autoLink(l.trim())).join('<br>\n')}</p>`;
  }).filter(Boolean).join('\n\n');
}

// ── Plain Text → Markdown ──────────────────────────────────────
function plainTextToMarkdown(text) {
  function autoLinkMd(s) {
    s = s.replace(/(https?:\/\/[^\s]+)/g, '[$1]($1)');
    s = s.replace(/\b([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b/g, '[$1](mailto:$1)');
    return s;
  }
  function isBulletBlock(lines) { return lines.filter(l => l.trim()).every(l => /^[\-\*•]\s+/.test(l.trim())); }
  function isOrderedBlock(lines) { return lines.filter(l => l.trim()).every(l => /^\d+[.):]\s+/.test(l.trim())); }

  const blocks = text.split(/\n{2,}/);
  return blocks.map(block => {
    const lines = block.split('\n');
    const nonEmpty = lines.filter(l => l.trim());
    if (!nonEmpty.length) return '';
    if (isBulletBlock(lines)) {
      return nonEmpty.map(l => `- ${autoLinkMd(l.replace(/^[\-\*•]\s+/, '').trim())}`).join('\n');
    }
    if (isOrderedBlock(lines)) {
      return nonEmpty.map((l, i) => `${i + 1}. ${autoLinkMd(l.replace(/^\d+[.):]\s+/, '').trim())}`).join('\n');
    }
    if (nonEmpty.length === 1) {
      const line = nonEmpty[0].trim();
      if (line.length >= 3 && line.length <= 72 && line === line.toUpperCase() && /[A-Z]/.test(line)) return `## ${line}`;
      return autoLinkMd(line);
    }
    const avgLen = nonEmpty.reduce((s, l) => s + l.trim().length, 0) / nonEmpty.length;
    const hasShortLines = nonEmpty.some(l => l.trim().length < 40);
    if (!hasShortLines && avgLen > 60) return autoLinkMd(nonEmpty.map(l => l.trim()).join(' '));
    return nonEmpty.map(l => autoLinkMd(l.trim())).join('  \n');
  }).filter(Boolean).join('\n\n');
}

// ── Swap Panels ────────────────────────────────────────────────
function swapPanels() {
  const outputVal = document.getElementById('outputArea').value;
  const inputVal  = document.getElementById('inputArea').value;
  document.getElementById('inputArea').value  = outputVal || inputVal;
  document.getElementById('outputArea').value = '';
  const flipMap = { md2html: 'html2md', html2md: 'md2html', text2html: 'md2html', text2md: 'md2html' };
  setMode(flipMap[currentMode] || 'md2html');
  if (outputVal) convert();
}

// ── Preview Toggle ─────────────────────────────────────────────
function togglePreview() {
  const panel = document.getElementById('previewPanel');
  const btn = document.getElementById('showPreviewBtn');
  const toggleBtn = document.getElementById('previewToggleBtn');
  previewVisible = !previewVisible;
  panel.style.display = previewVisible ? 'flex' : 'none';
  panel.style.flexDirection = 'column';
  btn.innerHTML = `<i data-lucide="${previewVisible ? 'eye-off' : 'eye'}" style="width:16px;height:16px;"></i> ${previewVisible ? 'Hide Preview' : 'Preview HTML'}`;
  toggleBtn.textContent = previewVisible ? 'Hide Preview' : 'Show Preview';
  if (previewVisible && (currentMode === 'md2html' || currentMode === 'text2html')) {
    const outputVal = document.getElementById('outputArea').value;
    if (outputVal) document.getElementById('previewArea').innerHTML = outputVal;
  }
  if (window.lucide) lucide.createIcons();
}

// ── Utilities ──────────────────────────────────────────────────
function clearInput() {
  document.getElementById('inputArea').value  = '';
  document.getElementById('outputArea').value = '';
  document.getElementById('previewArea').innerHTML = '';
}

function pasteExample() {
  const exMap = { md2html: MARKDOWN_EXAMPLE, html2md: HTML_EXAMPLE, text2html: TEXT_EXAMPLE, text2md: TEXT_EXAMPLE };
  document.getElementById('inputArea').value = exMap[currentMode] || MARKDOWN_EXAMPLE;
  convert();
}

function copyOutput(btn) {
  const text = document.getElementById('outputArea').value;
  if (!text) { showNotification('Nothing to copy yet!', 'warning'); return; }
  navigator.clipboard.writeText(text).then(() => {
    btn.textContent = 'Copied!';
    btn.classList.add('copied');
    setTimeout(() => { btn.textContent = 'Copy'; btn.classList.remove('copied'); }, 2000);
  });
}

function downloadOutput() {
  const text = document.getElementById('outputArea').value;
  if (!text) { showNotification('Nothing to download yet!', 'warning'); return; }
  const extMap = { md2html: 'html', html2md: 'md', text2html: 'html', text2md: 'md' };
  const ext = extMap[currentMode] || 'txt';
  const blob = new Blob([text], { type: 'text/plain' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `converted.${ext}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function showNotification(msg) {
  const n = document.createElement('div');
  n.style.cssText = `position:fixed;bottom:24px;right:24px;background:var(--bg-secondary);border:1px solid var(--border);color:var(--text-primary);padding:12px 20px;border-radius:10px;font-size:.87rem;font-weight:600;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.4);`;
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 2500);
}

// ── Init ────────────────────────────────────────────────────────
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') convert();
});
window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
});
