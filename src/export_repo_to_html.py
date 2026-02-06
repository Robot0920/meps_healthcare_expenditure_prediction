#!/usr/bin/env python3
"""
Export entire repository to a single HTML file for review.
Excludes data directories.

Usage:
    python src/export_repo_to_html.py

Output:
    reports/full_project_report.html
"""

import json
import csv
import re
import html
import base64
from pathlib import Path
from datetime import datetime


ROOT = Path(__file__).parent.parent
REPORT_DIR = ROOT / 'reports'
REPORT_DIR.mkdir(exist_ok=True)


# --- Markdown to HTML ---

def md_inline(text: str) -> str:
    """Process inline markdown: bold, italic, code, links."""
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


def md_table(rows: list) -> str:
    """Convert markdown table rows to HTML table."""
    if not rows:
        return ''
    parts = ['<table class="data-table">']
    for i, line in enumerate(rows):
        cells = [c.strip() for c in line.split('|') if c.strip()]
        tag = 'th' if i == 0 else 'td'
        if i == 0:
            parts.append('<thead>')
        if i == 1:
            parts.append('<tbody>')
        parts.append('<tr>' + ''.join(f'<{tag}>{md_inline(c)}</{tag}>' for c in cells) + '</tr>')
        if i == 0:
            parts.append('</thead>')
    parts.append('</tbody></table>')
    return '\n'.join(parts)


def md_to_html(text: str) -> str:
    """Convert markdown to HTML."""
    lines = text.split('\n')
    out = []
    table_buf = []
    in_code = False

    def flush_table():
        if table_buf:
            out.append(md_table(table_buf))
            table_buf.clear()

    for line in lines:
        s = line.strip()

        # Code fence
        if s.startswith('```'):
            flush_table()
            if in_code:
                out.append('</code></pre>')
                in_code = False
            else:
                lang = s[3:] or 'text'
                out.append(f'<pre class="code-block"><code class="language-{lang}">')
                in_code = True
            continue
        if in_code:
            out.append(html.escape(line))
            continue

        # Table row
        if '|' in s and not s.startswith('#') and not re.match(r'^[\|\s\-:]+$', s):
            table_buf.append(s)
            continue
        if re.match(r'^[\|\s\-:]+$', s):
            continue  # separator

        flush_table()

        # Headers
        for lvl in range(6, 0, -1):
            if s.startswith('#' * lvl + ' '):
                out.append(f'<h{lvl}>{md_inline(s[lvl+1:])}</h{lvl}>')
                break
        else:
            if re.match(r'^[\-\*_]{3,}$', s):
                out.append('<hr>')
            elif re.match(r'^[\-\*]\s', s):
                out.append(f'<li>{md_inline(s[2:])}</li>')
            elif re.match(r'^\d+\.\s', s):
                out.append(f'<li>{md_inline(re.sub(r"^\\d+\\.\\s", "", s))}</li>')
            elif not s:
                out.append('<br>')
            else:
                out.append(f'<p>{md_inline(s)}</p>')

    flush_table()
    return '\n'.join(out)


# --- Notebook to HTML ---

def notebook_to_html(path: Path) -> str:
    """Convert Jupyter notebook to HTML, including outputs and images."""
    with open(path, 'r', encoding='utf-8') as f:
        nb = json.load(f)

    parts = []
    for cell in nb.get('cells', []):
        ct = cell.get('cell_type', '')
        src = ''.join(cell.get('source', []))

        if ct == 'markdown':
            parts.append(f'<div class="cell markdown-cell">{md_to_html(src)}</div>')

        elif ct == 'code':
            code = f'<pre class="code-cell"><code>{html.escape(src)}</code></pre>'
            out_parts = []
            for o in cell.get('outputs', []):
                ot = o.get('output_type', '')
                if ot == 'stream':
                    t = ''.join(o.get('text', []))
                    out_parts.append(f'<pre class="output">{html.escape(t)}</pre>')
                elif ot in ('execute_result', 'display_data'):
                    d = o.get('data', {})
                    if 'text/html' in d:
                        out_parts.append(''.join(d['text/html']))
                    elif 'text/plain' in d:
                        out_parts.append(f'<pre class="output">{html.escape("".join(d["text/plain"]))}</pre>')
                    if 'image/png' in d:
                        out_parts.append(f'<img src="data:image/png;base64,{d["image/png"]}" class="nb-img">')
                elif ot == 'error':
                    tb = re.sub(r'\x1b\[[0-9;]*m', '', '\n'.join(o.get('traceback', [])))
                    out_parts.append(f'<pre class="error">{html.escape(tb)}</pre>')
            parts.append(f'<div class="cell code-cell">{code}{"".join(out_parts)}</div>')

    return '\n'.join(parts)


# --- Helpers ---

def img_to_base64(path: Path) -> str:
    mime = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif'}
    with open(path, 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    return f'<img src="data:{mime.get(path.suffix.lower(), "image/png")};base64,{data}" class="nb-img">'


def py_to_html(path: Path) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f'<pre class="python-code"><code>{html.escape(f.read())}</code></pre>'


# --- Main ---

CSS = '''
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       line-height: 1.6; max-width: 1200px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
.section { background: white; border-radius: 8px; padding: 30px; margin: 20px 0;
           box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
h2 { color: #34495e; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }
h3 { color: #7f8c8d; }
table { border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 14px; }
th, td { border: 1px solid #ddd; padding: 10px 12px; text-align: left; }
th { background: #3498db; color: white; font-weight: 600; }
tr:nth-child(even) { background: #f9f9f9; }
tr:hover { background: #e8f4fc; }
.data-table { box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-radius: 4px; overflow: hidden; }
.data-table th { background: #2c3e50; }
code { background: #f4f4f4; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
pre { background: #282c34; color: #abb2bf; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 13px; }
pre code { background: none; color: inherit; padding: 0; }
.cell { margin: 15px 0; padding: 10px; border-left: 3px solid #ddd; }
.markdown-cell { border-left-color: #3498db; background: #f8f9fa; padding: 15px; }
.code-cell { border-left-color: #27ae60; }
.code-cell pre.code-cell { margin-bottom: 10px; }
.output { background: #f4f4f4; color: #333; border-left: 2px solid #95a5a6; margin: 5px 0; font-size: 12px; }
.error { background: #fdf2f2; color: #c0392b; border-left: 2px solid #e74c3c; }
.nb-img { max-width: 100%; height: auto; display: block; margin: 10px 0; }
.toc { background: #ecf0f1; padding: 20px; border-radius: 8px; }
.toc a { color: #3498db; text-decoration: none; }
.toc a:hover { text-decoration: underline; }
.toc ol { line-height: 2; }
.figure-gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; }
.figure-item { text-align: center; }
.figure-item img { border: 1px solid #ddd; border-radius: 4px; max-width: 100%; }
.timestamp { color: #95a5a6; font-size: 0.9em; }
.alert { padding: 15px; border-radius: 4px; margin: 15px 0; }
.alert-info { background: #d1ecf1; border-left: 4px solid #0c5460; color: #0c5460; }
'''


def main():
    print("Exporting repository to HTML...")
    out_path = REPORT_DIR / 'full_project_report.html'

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    sections = []

    # --- Header ---
    sections.append(f'''
    <div class="section">
        <h1>MEPS Healthcare Cost Prediction</h1>
        <h2>Multi-Stage Risk Modeling Report</h2>
        <p class="timestamp">Generated: {now}</p>
    </div>''')

    # --- TOC ---
    sections.append('''
    <div class="section toc">
        <h2>Table of Contents</h2>
        <ol>
            <li><a href="#readme">Project Overview (README)</a></li>
            <li><a href="#nb-50">Data Processing (5.0)</a></li>
            <li><a href="#nb-51">Stage 1 Modeling (5.1)</a></li>
            <li><a href="#nb-52">Stage 1.5 &amp; Stage 2 Modeling (5.2)</a></li>
            <li><a href="#figures">Generated Figures</a></li>
            <li><a href="#tables">Performance Tables</a></li>
            <li><a href="#source">Source Code</a></li>
        </ol>
    </div>''')

    # --- 1. README ---
    print("  [1/7] README")
    readme = ROOT / 'README.md'
    if readme.exists():
        sections.append(f'''
    <div class="section" id="readme">
        <h2>1. Project Overview</h2>
        {md_to_html(readme.read_text(encoding="utf-8"))}
    </div>''')

    # --- 2-4. Notebooks ---
    notebooks = [
        ('nb-50', '2. Data Processing & Feature Engineering', '5.0_data_processing_v2_corrected.ipynb'),
        ('nb-51', '3. Stage 1: Risk Tier Classification', '5.1_modeling_stage1.ipynb'),
        ('nb-52', '4. Stage 1.5 & Stage 2: Latent Factors + Tweedie Regression', '5.2_stage1_5_and_stage2_modeling.ipynb'),
    ]
    for idx, (anchor, title, fname) in enumerate(notebooks, 2):
        nb_path = ROOT / 'notebooks' / fname
        print(f"  [{idx}/7] {fname}")
        if nb_path.exists():
            nb_html = notebook_to_html(nb_path)
            sections.append(f'''
    <div class="section" id="{anchor}">
        <h2>{title}</h2>
        <div class="alert alert-info"><strong>Notebook:</strong> {fname}</div>
        {nb_html}
    </div>''')

    # --- 5. Figures ---
    print("  [5/7] Figures")
    fig_dir = REPORT_DIR / 'figures'
    if fig_dir.exists():
        items = []
        for p in sorted(fig_dir.glob('*.png')):
            try:
                items.append(f'<div class="figure-item">{img_to_base64(p)}'
                             f'<p><strong>{p.stem.replace("_", " ").title()}</strong></p></div>')
            except Exception as e:
                print(f"    Warning: {p.name}: {e}")
        if items:
            sections.append(f'''
    <div class="section" id="figures">
        <h2>5. Generated Figures</h2>
        <div class="figure-gallery">{"".join(items)}</div>
    </div>''')

    # --- 6. Tables ---
    print("  [6/7] Tables")
    tbl_dir = REPORT_DIR / 'tables'
    if tbl_dir.exists():
        items = []
        for cp in sorted(tbl_dir.glob('*.csv')):
            try:
                with open(cp, 'r') as f:
                    rows = list(csv.reader(f))
                if rows:
                    hdr = rows[0]
                    t = '<table><thead><tr>' + ''.join(f'<th>{html.escape(h)}</th>' for h in hdr)
                    t += '</tr></thead><tbody>'
                    for r in rows[1:30]:
                        t += '<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in r) + '</tr>'
                    t += '</tbody></table>'
                    items.append(f'<h3>{cp.stem.replace("_", " ").title()}</h3>{t}')
            except Exception as e:
                print(f"    Warning: {cp.name}: {e}")
        if items:
            sections.append(f'''
    <div class="section" id="tables">
        <h2>6. Performance Tables</h2>
        {"".join(items)}
    </div>''')

    # --- 7. Source code ---
    print("  [7/7] Source code")
    src_dir = ROOT / 'src' / 'data'
    code_items = []
    for py in sorted(src_dir.glob('*.py')):
        if py.name == '__init__.py':
            continue
        code_items.append(f'<h3>{py.name}</h3>{py_to_html(py)}')
    # Also include the export script itself
    export_script = ROOT / 'src' / 'export_repo_to_html.py'
    if export_script.exists():
        code_items.append(f'<h3>{export_script.name}</h3>{py_to_html(export_script)}')

    if code_items:
        sections.append(f'''
    <div class="section" id="source">
        <h2>7. Source Code</h2>
        {"".join(code_items)}
    </div>''')

    # --- Footer ---
    sections.append(f'''
    <div class="section">
        <p class="timestamp">End of Report - Generated {now}</p>
    </div>''')

    # --- Assemble ---
    full = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MEPS Healthcare Cost Prediction - Full Report</title>
    <style>{CSS}</style>
</head>
<body>
{"".join(sections)}
</body>
</html>'''

    out_path.write_text(full, encoding='utf-8')
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"\nDone! Saved to: {out_path}")
    print(f"File size: {size_mb:.1f} MB")
    return out_path


if __name__ == '__main__':
    main()
