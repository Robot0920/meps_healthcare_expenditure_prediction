from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import nbformat
from nbconvert import HTMLExporter


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
OUTPUT_HTML = REPORTS_DIR / "module 10 weekly report.html"
TEMP_NOTEBOOK = REPORTS_DIR / "_module10_weekly_report.ipynb"

NOTEBOOKS = [
    ("5.0 Data Processing", REPO_ROOT / "notebooks" / "5.0_data_processing_v2_corrected.ipynb"),
    ("5.1 Stage 1 Modeling", REPO_ROOT / "notebooks" / "5.1_modeling_stage1.ipynb"),
    ("5.2 Stage 1.5 and Stage 2 Modeling", REPO_ROOT / "notebooks" / "5.2_stage1_5_and_stage2_modeling.ipynb"),
]


def load_notebook(path: Path):
    with path.open() as f:
        return nbformat.read(f, as_version=4)


def build_combined_notebook():
    cells = [
        nbformat.v4.new_markdown_cell(
            "# Module 10 Weekly Report\n\n"
            "Combined export of the latest executed notebooks:\n\n"
            "1. `5.0_data_processing_v2_corrected.ipynb`\n"
            "2. `5.1_modeling_stage1.ipynb`\n"
            "3. `5.2_stage1_5_and_stage2_modeling.ipynb`\n"
        )
    ]

    for title, path in NOTEBOOKS:
        nb = load_notebook(path)
        cells.append(
            nbformat.v4.new_markdown_cell(
                f"# {title}\n\nSource notebook: `{path.name}`"
            )
        )
        for cell in nb.cells:
            cells.append(deepcopy(cell))

    combined = nbformat.v4.new_notebook(
        cells=cells,
        metadata={
            "title": "Module 10 Weekly Report",
            "authors": [{"name": "Codex"}],
            "language_info": {"name": "python"},
        },
    )
    return combined


def export_html(combined_nb):
    TEMP_NOTEBOOK.write_text(nbformat.writes(combined_nb))

    exporter = HTMLExporter()
    exporter.exclude_input_prompt = True
    exporter.exclude_output_prompt = True
    exporter.template_name = "lab"

    body, _ = exporter.from_notebook_node(combined_nb)
    OUTPUT_HTML.write_text(body, encoding="utf-8")


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    combined_nb = build_combined_notebook()
    export_html(combined_nb)
    print(f"Combined HTML written to: {OUTPUT_HTML}")
    print(f"Temporary combined notebook written to: {TEMP_NOTEBOOK}")


if __name__ == "__main__":
    main()
