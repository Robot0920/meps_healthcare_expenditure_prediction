import os
import nbformat
from nbconvert import HTMLExporter
import markdown
from pathlib import Path

# Configuration
PROJ_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = PROJ_ROOT / 'notebooks'
REPORTS_DIR = PROJ_ROOT / 'reports'
README_PATH = PROJ_ROOT / 'README.md'
OUTPUT_FILE = REPORTS_DIR / 'full_project_report.html'

def convert_readme_to_html(path):
    if not path.exists():
        return "<h1>README not found</h1>"
    
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    # Convert Markdown to HTML
    html_content = markdown.markdown(text, extensions=['extra', 'codehilite'])
    return f"<div class='readme-section'>{html_content}</div>"

def convert_notebook_to_html(path):
    print(f"Processing notebook: {path.name}...")
    with open(path, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    
    # Use HTMLExporter with basic template to avoid full <html><html> nesting
    html_exporter = HTMLExporter()
    html_exporter.template_name = 'classic' # or 'lab'
    
    # We want to embed this, so we might need to strip some parts or use BasicHTMLExporter
    # But HTMLExporter gives better styling. We'll extract the body content later if needed.
    # For simplicity in this script, we'll keep the styling but wrap it in a div.
    
    (body, resources) = html_exporter.from_notebook_node(nb)
    return f"<div class='notebook-section' id='{path.stem}'><h2>Notebook: {path.name}</h2><hr>{body}</div>"

def generate_report():
    print("Starting Report Generation...")
    
    # 1. Header & CSS
    html_head = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Healthcare Risk Analytics Project Report</title>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 0; background-color: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
            .toc { background: #e9ecef; padding: 20px; border-radius: 5px; margin-bottom: 30px; }
            .toc h3 { margin-top: 0; }
            .toc ul { list-style: none; padding-left: 0; }
            .toc li { margin-bottom: 10px; }
            .readme-section { background: #fff; padding: 20px; border: 1px solid #ddd; margin-bottom: 40px; }
            .notebook-section { margin-bottom: 50px; border-top: 5px solid #007bff; padding-top: 20px; }
            pre { background: #f8f9fa; padding: 15px; border-radius: 4px; overflow-x: auto; }
            h1, h2, h3 { color: #2c3e50; }
            img { max-width: 100%; height: auto; }
        </style>
    </head>
    <body>
    <div class="container">
        <h1>Healthcare Latent Risk Project - Full Report</h1>
        <p>Generated automatically from source repository.</p>
    """

    # 2. Table of Contents
    toc_html = "<div class='toc'><h3>Table of Contents</h3><ul>"
    toc_html += "<li><a href='#readme'>1. Project Overview (README)</a></li>"
    
    notebooks = sorted([p for p in NOTEBOOKS_DIR.glob('*.ipynb') if not p.name.startswith('.')])
    for i, nb in enumerate(notebooks):
        toc_html += f"<li><a href='#{nb.stem}'>{i+2}. {nb.name}</a></li>"
    toc_html += "</ul></div>"

    content_html = ""

    # 3. Add README
    print("Converting README...")
    content_html += "<div id='readme'><h2>1. Project Overview</h2>"
    content_html += convert_readme_to_html(README_PATH)
    content_html += "</div>"

    # 4. Add Notebooks
    for nb in notebooks:
        content_html += convert_notebook_to_html(nb)

    # 5. Footer
    html_foot = """
    </div>
    </body>
    </html>
    """

    # Write File
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(html_head + toc_html + content_html + html_foot)
    
    print(f"Report generated successfully at: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()
