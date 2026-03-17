// ─────────────────────────────────────────────────────────────
//  Excel to CSV Converter Tool — Client Logic
//  Static file: static/js/tool-excel-converter.js
// ─────────────────────────────────────────────────────────────

// ── FAQ Accordion ──────────────────────────────────────────────
function toggleFaq(id) {
  const item = document.getElementById(id);
  const isOpen = item.classList.contains('open');
  document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
  if (!isOpen) item.classList.add('open');
}

// ── State ──────────────────────────────────────────────────────
let uploadedFiles = []; // { file, workbook, outputData, outputExt, name, ext, status }

// ── Format Config ──────────────────────────────────────────────
const FORMAT_META = {
  csv:  { label: '.CSV',  ext: 'csv',  mime: 'text/csv',               btnLabel: 'Convert to CSV'  },
  tsv:  { label: '.TSV',  ext: 'tsv',  mime: 'text/tab-separated-values', btnLabel: 'Convert to TSV' },
  pipe: { label: '.TXT',  ext: 'txt',  mime: 'text/plain',              btnLabel: 'Convert to TXT (Pipe)' },
  json: { label: '.JSON', ext: 'json', mime: 'application/json',        btnLabel: 'Convert to JSON' },
  xlsx: { label: '.XLSX', ext: 'xlsx', mime: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', btnLabel: 'Convert to XLSX' },
};

const FORMAT_COLORS = {
  xlsx: '#34d399', xls: '#6ee7b7', csv: '#93c5fd',
  tsv: '#fcd34d', ods: '#a78bfa', txt: '#9ca3af',
};

const FORMAT_DESCRIPTION = {
  xlsx: 'Microsoft Excel Workbook',
  xls:  'Legacy Excel 97-2003',
  csv:  'Comma-Separated Values',
  tsv:  'Tab-Separated Values',
  ods:  'OpenDocument Spreadsheet',
  txt:  'Plain Text / Delimited',
};

// ── Drag & Drop ───────────────────────────────────────────────
const uploadArea = document.getElementById('uploadArea');
if (uploadArea) {
  uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); uploadArea.classList.add('dragover'); });
  uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
  });
}

// ── Output format change ───────────────────────────────────────
function onFormatChange() {
  const fmt = document.getElementById('outputFormatOpt').value;
  const meta = FORMAT_META[fmt];

  // Update button label
  document.getElementById('convertBtnLabel').textContent = meta.btnLabel;

  // Show/hide delimiter for text formats only
  const delimGroup = document.getElementById('delimiterGroup');
  const textFormats = ['csv', 'tsv', 'pipe'];
  delimGroup.style.display = textFormats.includes(fmt) ? 'block' : 'none';

  // Auto-set delimiter to match chosen format
  const delimSel = document.getElementById('delimiterOpt');
  if (fmt === 'csv')  delimSel.value = ',';
  if (fmt === 'tsv')  delimSel.value = '\t';
  if (fmt === 'pipe') delimSel.value = '|';

  // Re-render file list with updated "→ FORMAT" arrows
  renderFileList();
}

// ── File Handling ─────────────────────────────────────────────
function handleFiles(files) {
  if (!files || !files.length) return;
  Array.from(files).forEach(file => {
    const ext = file.name.split('.').pop().toLowerCase();
    const supported = ['xlsx', 'xls', 'csv', 'tsv', 'ods', 'txt'];
    if (!supported.includes(ext)) {
      showToast(`"${file.name}" is not a supported format.`, 'error');
      return;
    }
    uploadedFiles.push({ file, workbook: null, outputData: null, outputExt: null, name: file.name, ext, status: 'ready' });
  });
  renderFileList();
  loadWorkbooks();
  document.getElementById('optionsPanel').style.display = 'grid';
  document.getElementById('actionRow').style.display = 'flex';
  onFormatChange(); // sync button label & delimiter state
  if (window.lucide) lucide.createIcons();
}

function loadWorkbooks() {
  uploadedFiles.forEach((item, idx) => {
    if (item.workbook) return;
    item.status = 'processing';
    renderFileList();
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const wb = XLSX.read(data, { type: 'array' });
        uploadedFiles[idx].workbook = wb;
        uploadedFiles[idx].status = 'ready';
        renderFileList();
        if (idx === 0) renderPreview(wb);
      } catch(err) {
        uploadedFiles[idx].status = 'error';
        uploadedFiles[idx].error = err.message;
        renderFileList();
      }
    };
    reader.readAsArrayBuffer(item.file);
  });
}

// ── Preview ───────────────────────────────────────────────────
function renderPreview(wb) {
  const sheetName = wb.SheetNames[0];
  const ws = wb.Sheets[sheetName];
  const data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
  if (!data.length) return;

  const skipEmpty = document.getElementById('skipEmptyRows').checked;
  const filtered = skipEmpty ? data.filter(r => r.some(c => c !== '' && c !== null && c !== undefined)) : data;
  const maxCols = Math.max(...filtered.map(r => r.length));
  const header = filtered[0] || [];
  const rows = filtered.slice(1, 11);

  document.getElementById('previewThead').innerHTML =
    '<tr>' + header.map(h => `<th>${escHtml(String(h))}</th>`).join('') + '</tr>';
  document.getElementById('previewTbody').innerHTML =
    rows.map(row =>
      '<tr>' + Array.from({ length: maxCols }, (_, i) => `<td>${escHtml(String(row[i] ?? ''))}</td>`).join('') + '</tr>'
    ).join('');

  document.getElementById('previewMeta').textContent =
    `${filtered.length - 1} rows · ${maxCols} columns · ${wb.SheetNames.length} sheet(s) · Sheet: "${sheetName}"`;
  document.getElementById('previewWrap').style.display = 'block';
}

// ── Convert ────────────────────────────────────────────────────
function convertAllFiles() {
  const btn = document.getElementById('convertBtn');
  btn.disabled = true;
  btn.innerHTML = `<i data-lucide="loader" style="width:18px;height:18px;"></i> Converting...`;
  if (window.lucide) lucide.createIcons();

  const fmt = document.getElementById('outputFormatOpt').value;
  const skipEmpty = document.getElementById('skipEmptyRows').checked;
  const quoteFields = document.getElementById('quoteFields').checked;
  const sheetMode = document.getElementById('sheetOpt').value;
  const meta = FORMAT_META[fmt];

  // Resolve delimiter
  let delimiter = ',';
  if (fmt === 'tsv')  delimiter = '\t';
  else if (fmt === 'pipe') delimiter = '|';
  else if (['csv'].includes(fmt)) delimiter = document.getElementById('delimiterOpt').value;

  setTimeout(() => {
    uploadedFiles.forEach((item, idx) => {
      if (!item.workbook) {
        uploadedFiles[idx].status = 'error';
        uploadedFiles[idx].error = 'File not loaded yet';
        return;
      }
      try {
        const sheetsToProcess = sheetMode === 'all' ? item.workbook.SheetNames : [item.workbook.SheetNames[0]];

        if (fmt === 'xlsx') {
          const newWb = XLSX.utils.book_new();
          sheetsToProcess.forEach(sName => {
            const ws = item.workbook.Sheets[sName];
            XLSX.utils.book_append_sheet(newWb, ws, sName);
          });
          const wbout = XLSX.write(newWb, { bookType: 'xlsx', type: 'array' });
          uploadedFiles[idx].outputData = new Blob([wbout], { type: meta.mime });
          uploadedFiles[idx].isBinary = true;

        } else if (fmt === 'json') {
          const parts = sheetsToProcess.map(sName => {
            const ws = item.workbook.Sheets[sName];
            let rows = XLSX.utils.sheet_to_json(ws, { defval: '' });
            if (skipEmpty) rows = rows.filter(r => Object.values(r).some(v => v !== ''));
            return rows;
          });
          const combined = parts.length === 1 ? parts[0] : parts.reduce((a,b) => [...a, ...b], []);
          uploadedFiles[idx].outputData = JSON.stringify(combined, null, 2);
          uploadedFiles[idx].isBinary = false;

        } else {
          // CSV / TSV / Pipe text output
          const textParts = sheetsToProcess.map(sName => {
            const ws = item.workbook.Sheets[sName];
            let data = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
            if (skipEmpty) data = data.filter(r => r.some(c => c !== '' && c !== null && c !== undefined));
            return data.map(row => row.map(cell => {
              let val = String(cell ?? '');
              if (quoteFields || val.includes(delimiter) || val.includes('"') || val.includes('\n')) {
                val = '"' + val.replace(/"/g, '""') + '"';
              }
              return val;
            }).join(delimiter)).join('\n');
          });
          uploadedFiles[idx].outputData = textParts.join('\n\n--- SHEET BREAK ---\n\n');
          uploadedFiles[idx].isBinary = false;
        }

        uploadedFiles[idx].outputExt = meta.ext;
        uploadedFiles[idx].outputMime = meta.mime;
        uploadedFiles[idx].status = 'success';

      } catch(err) {
        uploadedFiles[idx].status = 'error';
        uploadedFiles[idx].error = err.message;
      }
    });

    renderFileList();
    btn.disabled = false;
    const doneLabel = `<i data-lucide="check-circle" style="width:18px;height:18px;"></i> <span id="convertBtnLabel">Done! Convert Again</span>`;
    btn.innerHTML = doneLabel;
    if (window.lucide) lucide.createIcons();

    const successCount = uploadedFiles.filter(f => f.status === 'success').length;
    if (successCount > 1) document.getElementById('zipBtn').style.display = 'inline-flex';

    setTimeout(() => {
      onFormatChange(); // reset label
      btn.disabled = false;
      const lbl = FORMAT_META[document.getElementById('outputFormatOpt').value].btnLabel;
      btn.innerHTML = `<i data-lucide="refresh-cw" style="width:18px;height:18px;"></i> <span id="convertBtnLabel">${lbl}</span>`;
      if (window.lucide) lucide.createIcons();
    }, 3000);
  }, 50);
}

// ── Download ───────────────────────────────────────────────
function downloadFile(idx) {
  const item = uploadedFiles[idx];
  if (!item || !item.outputData) return;
  const baseName = item.name.replace(/\.[^/.]+$/, '');
  let blob;
  if (item.isBinary) {
    blob = item.outputData;
  } else {
    blob = new Blob([item.outputData], { type: item.outputMime + ';charset=utf-8;' });
  }
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `${baseName}.${item.outputExt}`;
  a.click();
  URL.revokeObjectURL(a.href);
}

function downloadCSV(idx) { downloadFile(idx); }

async function downloadAllAsZip() {
  const successes = uploadedFiles.filter(f => f.outputData);
  successes.forEach((_, i) => {
    const realIdx = uploadedFiles.indexOf(successes[i]);
    setTimeout(() => downloadFile(realIdx), i * 450);
  });
  showToast(`Downloading ${successes.length} converted file(s)...`, 'success');
}

// ── Render File List ─────────────────────────────────────────
function renderFileList() {
  const container = document.getElementById('fileList');
  if (!uploadedFiles.length) { container.innerHTML = ''; return; }

  const fmt = document.getElementById('outputFormatOpt') ? document.getElementById('outputFormatOpt').value : 'csv';
  const outMeta = FORMAT_META[fmt] || FORMAT_META.csv;

  container.innerHTML = uploadedFiles.map((item, idx) => {
    const statusMap = {
      ready: 'Ready', processing: 'Parsing...', success: 'Converted ✓', error: `Error: ${item.error || 'Unknown'}`
    };
    const sizeKb = (item.file.size / 1024).toFixed(1);
    const dotColor = FORMAT_COLORS[item.ext] || '#9ca3af';
    const fmtDesc = FORMAT_DESCRIPTION[item.ext] || item.ext.toUpperCase();
    const sheetInfo = item.workbook ? ` · ${item.workbook.SheetNames.length} sheet(s)` : '';
    
    const formatBadge = `
      <div style="display:flex;align-items:center;gap:5px;margin-top:3px;flex-wrap:wrap;">
        <span style="display:inline-flex;align-items:center;gap:4px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);border-radius:6px;padding:2px 8px;font-size:.7rem;font-weight:700;color:${dotColor};">
          <span style="width:6px;height:6px;border-radius:50%;background:${dotColor};display:inline-block;"></span>
          .${item.ext.toUpperCase()}
        </span>
        <span style="font-size:.7rem;color:var(--text-muted);">${fmtDesc}${sheetInfo}</span>
        ${item.status !== 'success' ? `
          <span style="font-size:.7rem;color:var(--text-muted);">→</span>
          <span style="display:inline-flex;align-items:center;gap:4px;background:rgba(124,58,237,.1);border:1px solid rgba(124,58,237,.25);border-radius:6px;padding:2px 8px;font-size:.7rem;font-weight:700;color:#a78bfa;">
            ${outMeta.label}
          </span>
        ` : `
          <span style="font-size:.7rem;color:var(--text-muted);">→</span>
          <span style="display:inline-flex;align-items:center;gap:4px;background:rgba(16,185,129,.1);border:1px solid rgba(16,185,129,.3);border-radius:6px;padding:2px 8px;font-size:.7rem;font-weight:700;color:#34d399;">
            .${(item.outputExt||'csv').toUpperCase()} ready
          </span>
        `}
      </div>`;

    return `<div class="file-item ${item.status}">
      <div class="file-icon ${item.ext}">${item.ext.toUpperCase()}</div>
      <div class="file-info">
        <div class="file-name">${escHtml(item.name)}</div>
        <div class="file-meta">${sizeKb} KB${formatBadge}</div>
      </div>
      <span class="file-status ${item.status}">${statusMap[item.status] || item.status}</span>
      ${item.status === 'success' ? `<button class="file-download-btn" onclick="downloadFile(${idx})">⬇ Download ${(item.outputExt||'csv').toUpperCase()}</button>` : ''}
      <button class="file-remove-btn" onclick="removeFile(${idx})">✕</button>
    </div>`;
  }).join('');
}

function removeFile(idx) {
  uploadedFiles.splice(idx, 1);
  renderFileList();
  if (!uploadedFiles.length) {
    document.getElementById('optionsPanel').style.display = 'none';
    document.getElementById('actionRow').style.display = 'none';
    document.getElementById('previewWrap').style.display = 'none';
  }
}

function clearAll() {
  uploadedFiles = [];
  const fileInput = document.getElementById('fileInput');
  if (fileInput) fileInput.value = '';
  renderFileList();
  document.getElementById('optionsPanel').style.display = 'none';
  document.getElementById('actionRow').style.display = 'none';
  document.getElementById('previewWrap').style.display = 'none';
  document.getElementById('zipBtn').style.display = 'none';
}

// ── Utilities ──────────────────────────────────────────────────
function escHtml(str) {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function showToast(msg, type) {
  const colors = { success: '#34d399', error: '#f87171', warning: '#fcd34d' };
  const n = document.createElement('div');
  n.style.cssText = `position:fixed;bottom:24px;right:24px;background:var(--bg-secondary);border:1px solid ${colors[type]||'var(--border)'};color:var(--text-primary);padding:12px 20px;border-radius:10px;font-size:.87rem;font-weight:600;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.4);`;
  n.textContent = msg;
  document.body.appendChild(n);
  setTimeout(() => n.remove(), 3000);
}

// ── Init ────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  if (window.lucide) lucide.createIcons();
  const outputFormatOpt = document.getElementById('outputFormatOpt');
  if (outputFormatOpt) onFormatChange();
});
