import csv
import io
import os
import re
import json
import hashlib
import random
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.views.decorators.http import require_POST


# ─── Security Constants ───────────────────────────────────────────────────────
MAX_FILE_SIZE   = 10 * 1024 * 1024   # 10 MB per file
MAX_FILES       = 10                  # max files to merge at once
MAX_ROWS        = 500_000             # hard row cap after merge
MAX_COLUMNS     = 100                 # hard column cap
ALLOWED_MIME    = {
    'text/csv', 'text/plain', 'application/csv',
    'application/vnd.ms-excel',
}
EMAIL_RE   = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
DOMAIN_RE  = re.compile(r'(?:https?://)?(?:www\.)?([a-zA-Z0-9\-]+(?:\.[a-zA-Z]{2,})+)')


# ─── Pages ───────────────────────────────────────────────────────────────────

@login_required
def cleaner_page(request):
    """Landing page for the CSV Cleaner tool."""
    return render(request, 'csvtools/cleaner.html', {'active_page': 'tools'})


# ─── Preview uploaded files (returns column names + first 5 rows) ────────────

@login_required
@require_POST
def cleaner_preview(request):
    """
    Accepts up to MAX_FILES CSV uploads, merges them in-memory,
    applies an optional cleaning pipeline to a sample,
    and returns column names + first 10 processed rows.
    """
    rate_result = _rate_check(request.user.id, 'csv_preview', limit=40, window=60)
    if rate_result:
        return rate_result

    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'error': 'No files uploaded.'}, status=400)

    # Parse pipeline
    try:
        pipeline = json.loads(request.POST.get('pipeline', '[]'))
    except:
        pipeline = []

    merged_rows, fieldnames, error = _merge_files(files)
    if error:
        return JsonResponse({'error': error}, status=400)

    # Compute column statistics (on raw data for consistency)
    col_stats = {}
    for col in fieldnames:
        values = [r.get(col, '').strip() for r in merged_rows]
        non_empty = [v for v in values if v]
        unique = set(non_empty)
        email_count = sum(1 for v in non_empty if EMAIL_RE.match(v))
        
        numeric_count = 0
        phone_count = 0
        url_count = 0
        for v in non_empty:
            if v.replace('.', '', 1).isdigit(): numeric_count += 1
            if re.match(r'^\+?[\d\s\-\(\).]{7,}$', v) and sum(c.isdigit() for c in v) > 6: phone_count += 1
            if DOMAIN_RE.search(v): url_count += 1

        col_stats[col] = {
            'total': len(values), 'filled': len(non_empty), 'empty': len(values) - len(non_empty),
            'unique': len(unique), 'has_emails': email_count > 0, 'email_count': email_count,
            'numeric_count': numeric_count, 'phone_count': phone_count, 'url_count': url_count,
            'is_numeric': numeric_count > (len(non_empty) * 0.8) if non_empty else False,
            'is_pii': email_count > 0 or phone_count > 0,
        }

    # Apply pipeline to a preview sample (20 rows)
    preview_rows = merged_rows[:20]
    preview_fields = list(fieldnames)
    for op in pipeline:
        try:
            preview_rows, preview_fields = _apply_operation(op.get('type'), op, preview_rows, preview_fields)
        except:
            continue

    return JsonResponse({
        'success': True,
        'total_rows': len(merged_rows),
        'columns': preview_fields,
        'preview': preview_rows[:10],
        'col_stats': col_stats,
    })


# ─── Main Process Endpoint ────────────────────────────────────────────────────

@login_required
@require_POST
def cleaner_process(request):
    """
    Accepts CSV file(s) + a pipeline of cleaning operations (JSON).
    Applies operations in-order in memory and returns cleaned CSV as download.
    Nothing is stored to disk or database.

    Operations supported (passed as JSON in 'pipeline' field):
      - remove_blank_rows
      - remove_duplicates       { columns: [...] }
      - filter_columns          { keep: [...] }
      - remove_column           { column: "name" }
      - add_column              { name: "col", value: "default" }
      - sort_emails_first       { column: "email" }
      - sort_by_column          { column: "name", direction: "asc"|"desc" }
      - extract_domain          { source: "email"|"url", target: "domain" }
      - remove_invalid_emails   { column: "email" }
      - keep_only_domain        { column: "website" }
      - find_replace            { column: "x", find: "foo", replace: "bar" }
      - trim_whitespace
      - lowercase               { column: "name" }
      - uppercase               { column: "name" }
      - merge_columns           { columns: ["first", "last"], separator: " ", target: "full_name" }
      - rename_column           { column: "old_name", new_name: "new_name" }
      - remove_rows_containing  { column: "email", text: "spam" }
      - keep_rows_containing    { column: "email", text: "@gmail.com" }
    """
    rate_result = _rate_check(request.user.id, 'csv_process', limit=10, window=60)
    if rate_result:
        return rate_result

    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'error': 'No files uploaded.'}, status=400)

    # Parse pipeline
    try:
        pipeline = json.loads(request.POST.get('pipeline', '[]'))
    except (json.JSONDecodeError, Exception):
        return JsonResponse({'error': 'Invalid pipeline configuration.'}, status=400)

    # Merge uploaded files
    rows, fieldnames, error = _merge_files(files)
    if error:
        return JsonResponse({'error': error}, status=400)

    # Apply each operation in sequence
    for op in pipeline:
        op_type = op.get('type')
        try:
            rows, fieldnames = _apply_operation(op_type, op, rows, fieldnames)
        except Exception as e:
            return JsonResponse({'error': f'Operation "{op_type}" failed: {str(e)}'}, status=400)

    # Get custom filename (sanitized)
    raw_filename = request.POST.get('filename', 'cleaned_data').strip()
    # Sanitize: only allow alphanumeric, dashes, underscores, spaces
    safe_name = re.sub(r'[^\w\s\-\(\)]', '', raw_filename)[:100] or 'cleaned_data'
    filename = f'{safe_name}.csv'

    # Stream result as CSV download
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, '') for col in fieldnames})

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ─── File Merge Helper ────────────────────────────────────────────────────────

def _merge_files(files):
    """
    Validates and merges multiple CSV uploads into one list of dicts.
    Returns (rows, fieldnames, error_string_or_None).
    """
    if len(files) > MAX_FILES:
        return [], [], f'Too many files. Maximum {MAX_FILES} files per operation.'

    all_rows   = []
    all_fields = []   # union of all columns, preserving order

    for f in files:
        # Security checks
        raw_name = os.path.basename(f.name or '')
        if len(raw_name) > 255 or not re.match(r'^[\w\s\-\.\(\)]+$', raw_name):
            return [], [], f'Invalid filename: {raw_name}'
        if not raw_name.lower().endswith('.csv'):
            return [], [], f'Only .csv files are accepted. Got: {raw_name}'
        if f.size > MAX_FILE_SIZE:
            return [], [], f'"{raw_name}" is too large ({f.size // (1024*1024)} MB). Max is 10 MB.'
        mime = (f.content_type or '').split(';')[0].strip()
        if mime and mime not in ALLOWED_MIME:
            return [], [], f'"{raw_name}" has an invalid file type ({mime}).'

        # Decode
        try:
            try:
                content = f.read().decode('utf-8')
            except UnicodeDecodeError:
                f.seek(0)
                content = f.read().decode('latin-1')
        except Exception:
            return [], [], f'Could not read "{raw_name}".'

        # Parse
        try:
            reader = csv.DictReader(io.StringIO(content))
            file_rows = list(reader)
            file_fields = list(reader.fieldnames or [])
        except Exception:
            return [], [], f'Could not parse "{raw_name}" as CSV.'

        if len(file_fields) > MAX_COLUMNS:
            return [], [], f'"{raw_name}" has too many columns ({len(file_fields)}). Max is {MAX_COLUMNS}.'

        # Merge fields (union, preserve order)
        for col in file_fields:
            if col not in all_fields:
                all_fields.append(col)

        all_rows.extend(file_rows)

    if len(all_rows) > MAX_ROWS:
        return [], [], f'Total rows ({len(all_rows):,}) exceeds the {MAX_ROWS:,} row limit. Split your files.'

    return all_rows, all_fields, None


# ─── Operation Router ─────────────────────────────────────────────────────────

def _apply_operation(op_type, op, rows, fieldnames):
    """Dispatches an operation and returns (new_rows, new_fieldnames)."""

    if op_type == 'remove_blank_rows':
        rows = [r for r in rows if any(v.strip() for v in r.values())]

    elif op_type == 'remove_duplicates':
        cols = op.get('columns', fieldnames)
        seen = set()
        new_rows = []
        for r in rows:
            key = tuple(r.get(c, '').strip().lower() for c in cols)
            if key not in seen:
                seen.add(key)
                new_rows.append(r)
        rows = new_rows

    elif op_type == 'filter_columns':
        keep = op.get('keep', fieldnames)
        # Only keep columns that actually exist
        keep = [c for c in keep if c in fieldnames]
        rows = [{c: r.get(c, '') for c in keep} for r in rows]
        fieldnames = keep

    elif op_type == 'remove_column':
        col = op.get('column', '')
        if col in fieldnames:
            fieldnames = [c for c in fieldnames if c != col]
            rows = [{c: r.get(c, '') for c in fieldnames} for r in rows]

    elif op_type == 'add_column':
        col   = op.get('name', 'New Column')
        value = op.get('value', '')
        if col not in fieldnames:
            fieldnames = fieldnames + [col]
        rows = [{**r, col: r.get(col, value)} for r in rows]

    elif op_type == 'sort_emails_first':
        col = op.get('column', 'email')
        def has_email(r):
            v = r.get(col, '').strip()
            return 0 if EMAIL_RE.match(v) else 1
        rows = sorted(rows, key=has_email)

    elif op_type == 'sort_by_column':
        col       = op.get('column', '')
        direction = op.get('direction', 'asc')
        reverse   = (direction == 'desc')
        rows = sorted(rows, key=lambda r: r.get(col, '').lower(), reverse=reverse)

    elif op_type == 'extract_domain':
        source = op.get('source', 'email')
        target = op.get('target', 'domain')
        if target not in fieldnames:
            fieldnames = fieldnames + [target]
        new_rows = []
        for r in rows:
            val = r.get(source, '').strip()
            domain = ''
            if '@' in val:
                domain = val.split('@')[-1].strip().lower()
            else:
                m = DOMAIN_RE.search(val)
                if m:
                    domain = m.group(1).lower()
            new_rows.append({**r, target: domain})
        rows = new_rows

    elif op_type == 'remove_invalid_emails':
        col = op.get('column', 'email')
        rows = [r for r in rows if EMAIL_RE.match(r.get(col, '').strip())]

    elif op_type == 'keep_only_domain':
        col = op.get('column', 'website')
        new_rows = []
        for r in rows:
            val = r.get(col, '').strip()
            m = DOMAIN_RE.search(val)
            new_rows.append({**r, col: m.group(1).lower() if m else val})
        rows = new_rows

    elif op_type == 'find_replace':
        col     = op.get('column', '')
        find    = op.get('find', '')
        replace = op.get('replace', '')
        if col in fieldnames and find:
            rows = [{**r, col: r.get(col, '').replace(find, replace)} for r in rows]

    elif op_type == 'trim_whitespace':
        rows = [{c: v.strip() for c, v in r.items()} for r in rows]

    # ── New operations ─────────────────────────────────────────────────────

    elif op_type == 'lowercase':
        col = op.get('column', '')
        if col in fieldnames:
            rows = [{**r, col: r.get(col, '').lower()} for r in rows]

    elif op_type == 'uppercase':
        col = op.get('column', '')
        if col in fieldnames:
            rows = [{**r, col: r.get(col, '').upper()} for r in rows]

    elif op_type == 'merge_columns':
        cols      = op.get('columns', [])
        separator = op.get('separator', ' ')
        target    = op.get('target', 'merged')
        if target not in fieldnames:
            fieldnames = fieldnames + [target]
        new_rows = []
        for r in rows:
            merged_val = separator.join(r.get(c, '').strip() for c in cols if r.get(c, '').strip())
            new_rows.append({**r, target: merged_val})
        rows = new_rows

    elif op_type == 'rename_column':
        old_name = op.get('column', '')
        new_name = op.get('new_name', '').strip()
        if old_name in fieldnames and new_name and new_name not in fieldnames:
            fieldnames = [new_name if c == old_name else c for c in fieldnames]
            rows = [{(new_name if k == old_name else k): v for k, v in r.items()} for r in rows]

    elif op_type == 'remove_rows_containing':
        col  = op.get('column', '')
        text = op.get('text', '').lower()
        if col in fieldnames and text:
            rows = [r for r in rows if text not in r.get(col, '').lower()]

    elif op_type == 'keep_rows_containing':
        col  = op.get('column', '')
        text = op.get('text', '').lower()
        if col in fieldnames and text:
            rows = [r for r in rows if text in r.get(col, '').lower()]

    # ── Extended operations ────────────────────────────────────────────────

    elif op_type == 'titlecase':
        col = op.get('column', '')
        if col in fieldnames:
            rows = [{**r, col: r.get(col, '').title()} for r in rows]

    elif op_type == 'split_column':
        col       = op.get('column', '')
        delimiter = op.get('delimiter', ',')
        col_a     = op.get('col_a', (col + '_1'))
        col_b     = op.get('col_b', (col + '_2'))
        if col in fieldnames:
            for c in [col_a, col_b]:
                if c not in fieldnames:
                    fieldnames = fieldnames + [c]
            new_rows = []
            for r in rows:
                parts = r.get(col, '').split(delimiter, 1)
                new_rows.append({**r, col_a: parts[0].strip(), col_b: parts[1].strip() if len(parts) > 1 else ''})
            rows = new_rows

    elif op_type == 'number_rows':
        col   = op.get('column', '#')
        start = int(op.get('start', 1))
        if col not in fieldnames:
            fieldnames = [col] + fieldnames
        rows = [{**r, col: str(start + i)} for i, r in enumerate(rows)]

    elif op_type == 'remove_empty_columns':
        # Drop columns where every value is blank
        empty_cols = [c for c in fieldnames if all(not r.get(c, '').strip() for r in rows)]
        fieldnames = [c for c in fieldnames if c not in empty_cols]
        rows = [{c: r.get(c, '') for c in fieldnames} for r in rows]

    elif op_type == 'fill_empty':
        col   = op.get('column', '')
        value = op.get('value', '')
        if col in fieldnames:
            rows = [{**r, col: r.get(col, '').strip() or value} for r in rows]

    elif op_type == 'limit_rows':
        try:
            n = max(1, int(op.get('count', 1000)))
        except (ValueError, TypeError):
            n = 1000
        rows = rows[:n]

    elif op_type == 'remove_special_chars':
        col     = op.get('column', '')
        pattern = op.get('pattern', r'[^a-zA-Z0-9\s@._\-]')
        try:
            compiled = re.compile(pattern)
        except re.error:
            compiled = re.compile(r'[^a-zA-Z0-9\s@._\-]')
        if col in fieldnames:
            rows = [{**r, col: compiled.sub('', r.get(col, ''))} for r in rows]

    elif op_type == 'phone_normalize':
        col = op.get('column', '')
        fmt = op.get('format', 'digits')   # 'digits' | 'dashes' | 'international'
        if col in fieldnames:
            new_rows = []
            for r in rows:
                raw = r.get(col, '')
                digits = re.sub(r'\D', '', raw)
                if fmt == 'dashes' and len(digits) == 10:
                    val = f'{digits[:3]}-{digits[3:6]}-{digits[6:]}'
                elif fmt == 'international' and digits:
                    val = f'+{digits}'
                else:
                    val = digits
                new_rows.append({**r, col: val})
            rows = new_rows

    # ── Data Engineering operations ──────────────────────────────────────

    elif op_type == 'mask_pii':
        col = op.get('column', '')
        mode = op.get('mode', 'partial') # 'partial' | 'full'
        if col in fieldnames:
            new_rows = []
            for r in rows:
                val = r.get(col, '').strip()
                if not val:
                    new_rows.append(r)
                    continue
                if mode == 'full':
                    mask = '*' * 8
                else:
                    if '@' in val: # email
                        parts = val.split('@')
                        mask = parts[0][0] + '***@' + parts[1] if len(parts[0]) > 1 else '*@' + parts[1]
                    else: # phone or other
                        mask = val[:2] + '*' * (len(val)-4) + val[-2:] if len(val) > 4 else '*' * len(val)
                new_rows.append({**r, col: mask})
            rows = new_rows

    elif op_type == 'random_sample':
        count = int(op.get('count', 100))
        if len(rows) > count:
            rows = random.sample(rows, count)

    elif op_type == 'flag_outliers':
        col = op.get('column', '')
        target_col = op.get('target', 'is_outlier')
        threshold = float(op.get('threshold', 0))
        direction = op.get('direction', 'above') # 'above' | 'below'
        if target_col not in fieldnames:
            fieldnames = fieldnames + [target_col]
        new_rows = []
        for r in rows:
            try:
                val = float(re.sub(r'[^\d.]', '', r.get(col, '0')))
                is_outlier = (val > threshold) if direction == 'above' else (val < threshold)
            except:
                is_outlier = False
            new_rows.append({**r, target_col: 'TRUE' if is_outlier else 'FALSE'})
        rows = new_rows

    elif op_type == 'hash_column':
        col = op.get('column', '')
        algo = op.get('algo', 'sha256')
        if col in fieldnames:
            rows = [{**r, col: hashlib.new(algo, r.get(col, '').encode()).hexdigest()} for r in rows]

    elif op_type == 'case_when':
        # If Column A contains X, set Column B to Y
        col_a = op.get('if_column', '')
        match = op.get('match_text', '')
        col_b = op.get('then_column', '')
        set_val = op.get('set_value', '')
        if col_a in fieldnames and col_b in fieldnames:
            new_rows = []
            for r in rows:
                if match.lower() in r.get(col_a, '').lower():
                    new_rows.append({**r, col_b: set_val})
                else:
                    new_rows.append(r)
            rows = new_rows

    elif op_type == 'remove_html':
        col = op.get('column', '')
        if col in fieldnames:
            rows = [{**r, col: re.sub(r'<[^>]+>', '', r.get(col, ''))} for r in rows]

    elif op_type == 'json_extract':
        col = op.get('column', '')
        key = op.get('key', '')
        target = op.get('target', (col + '_' + key))
        if col in fieldnames and key:
            if target not in fieldnames:
                fieldnames = fieldnames + [target]
            new_rows = []
            for r in rows:
                try:
                    data = json.loads(r.get(col, '{}'))
                    val = str(data.get(key, ''))
                except:
                    val = ''
                new_rows.append({**r, target: val})
            rows = new_rows

    elif op_type == 'date_standardize':
        col = op.get('column', '')
        # Simple regex for common dates, very basic implementation
        # Real-world would use dateutil.parser but we're in a zero-dependency (almost) env
        if col in fieldnames:
            new_rows = []
            for r in rows:
                val = r.get(col, '').strip()
                # Try simple transformations
                val = val.replace('/', '-').replace(' ', 'T')
                new_rows.append({**r, col: val})
            rows = new_rows

    elif op_type == 'remove_url_params':
        col = op.get('column', '')
        if col in fieldnames:
            new_rows = []
            for r in rows:
                val = r.get(col, '')
                if '?' in val:
                    val = val.split('?')[0]
                new_rows.append({**r, col: val})
            rows = new_rows

    elif op_type == 'conditional_remove':
        # Remove if Column A contains X AND Column B contains Y
        col_a = op.get('col_a', '')
        text_a = op.get('text_a', '').lower()
        col_b = op.get('col_b', '')
        text_b = op.get('text_b', '').lower()
        if col_a in fieldnames and col_b in fieldnames:
            rows = [r for r in rows if not (text_a in r.get(col_a, '').lower() and text_b in r.get(col_b, '').lower())]

    else:
        raise ValueError(f'Unknown operation type: {op_type}')

    return rows, fieldnames


# ─── Rate Limiter ────────────────────────────────────────────────────────────

def _rate_check(user_id, action, limit=10, window=60):
    """Returns JsonResponse(429) if rate exceeded, else None."""
    key = f'csvtools_{action}_{user_id}'
    count = cache.get(key, 0)
    if count >= limit:
        return JsonResponse(
            {'error': 'Too many requests. Please wait a moment and try again.'},
            status=429
        )
    cache.set(key, count + 1, timeout=window)
    return None
