from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "reports"
TABLES_DIR = REPORTS_DIR / "tables"
DATA_DIR = REPO_ROOT / "data" / "processed_v2"

OUTPUT_DASHBOARD = REPORTS_DIR / "MEPS_Healthcare_Cost_Decision_Dashboard.html"
OUTPUT_CODE_HTML = REPORTS_DIR / "code for dashboard.html"

COST_BIN_LABELS = {0: "Low", 1: "Moderate", 2: "High", 3: "Very High", 4: "Extreme"}


def fmt_int(x: int) -> str:
    return f"{int(x):,}"


def fmt_currency(x: float, digits: int = 0) -> str:
    return f"${x:,.{digits}f}"


def fmt_num(x: float, digits: int = 3) -> str:
    return f"{x:.{digits}f}"


def fmt_pct(x: float, digits: int = 1) -> str:
    return f"{100 * x:.{digits}f}%"


def cost_bin_label(value: int) -> str:
    return COST_BIN_LABELS.get(int(value), f"Bin {int(value)}")


def plot_div(fig: go.Figure, include_js: bool = False) -> str:
    return pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs="inline" if include_js else False,
        config={
            "displaylogo": False,
            "responsive": True,
            "modeBarButtonsToRemove": [
                "lasso2d",
                "select2d",
                "autoScale2d",
                "hoverCompareCartesian",
                "toggleSpikelines",
            ],
        },
    )


def metric_card(label: str, value: str, note: str, tone: str = "default", compact: bool = False) -> str:
    compact_class = " compact" if compact else ""
    return f"""
    <article class="metric-card tone-{tone}{compact_class}">
      <div class="metric-label">{html.escape(label)}</div>
      <div class="metric-value">{html.escape(value)}</div>
      <div class="metric-note">{html.escape(note)}</div>
    </article>
    """


def info_chip(label: str, value: str) -> str:
    return f"""
    <div class="info-chip">
      <span class="chip-label">{html.escape(label)}</span>
      <span class="chip-value">{html.escape(value)}</span>
    </div>
    """


def render_table(
    df: pd.DataFrame,
    table_id: str,
    decision_filter_col: str | None = None,
) -> str:
    head = "".join(f"<th>{html.escape(str(col))}</th>" for col in df.columns)
    rows = []
    for _, row in df.iterrows():
        attrs = []
        if decision_filter_col:
            attrs.append(f"data-filter='{html.escape(str(row[decision_filter_col]).lower())}'")
        cells = "".join(f"<td>{html.escape(str(value))}</td>" for value in row.tolist())
        rows.append(f"<tr {' '.join(attrs)}>{cells}</tr>")
    return f"""
    <div class="table-shell">
      <div class="table-scroll">
        <table class="dashboard-table" id="{html.escape(table_id)}">
          <thead><tr>{head}</tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """


def build_transition_heatmap(analytic: pd.DataFrame) -> go.Figure:
    share = pd.crosstab(analytic["Y1_BIN"], analytic["Y2_BIN"], normalize="index") * 100
    counts = pd.crosstab(analytic["Y1_BIN"], analytic["Y2_BIN"])
    y_labels = [cost_bin_label(x) for x in share.index]
    x_labels = [cost_bin_label(x) for x in share.columns]
    hover = []
    for y in share.index:
        hover_row = []
        for x in share.columns:
            hover_row.append(
                f"Y1 {cost_bin_label(y)} → Y2 {cost_bin_label(x)}"
                f"<br>Share: {share.loc[y, x]:.1f}%"
                f"<br>N: {counts.loc[y, x]:,}"
            )
        hover.append(hover_row)

    fig = go.Figure(
        data=go.Heatmap(
            z=share.values,
            x=x_labels,
            y=y_labels,
            colorscale=[
                [0.0, "#eef4f6"],
                [0.25, "#a5c9ca"],
                [0.5, "#5d8f99"],
                [0.75, "#2f6473"],
                [1.0, "#173b4d"],
            ],
            text=np.vectorize(lambda x: f"{x:.1f}%")(share.values),
            texttemplate="%{text}",
            hoverinfo="text",
            hovertext=hover,
            colorbar=dict(title="Row share (%)"),
        )
    )
    fig.update_layout(
        title="Year 1 to Year 2 Cost-Bin Transition",
        margin=dict(l=20, r=20, t=60, b=30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        height=420,
    )
    fig.update_xaxes(title="Year 2 cost bin")
    fig.update_yaxes(title="Year 1 cost bin", autorange="reversed")
    return fig


def build_stage1_tradeoff(stage1: pd.DataFrame) -> go.Figure:
    actionable_map = {True: "#2d7d60", False: "#bd6c27"}
    colors = [actionable_map[bool(v)] for v in stage1["Operationally_Actionable"]]
    sizes = 22 + 65 * stage1["Low_Jumper_Recall"].astype(float)
    fig = go.Figure(
        data=go.Scatter(
            x=stage1["F1_Macro_10Class"],
            y=stage1["High_Escalate_Recall"],
            mode="markers+text",
            text=stage1["Experiment"],
            textposition="top center",
            marker=dict(size=sizes, color=colors, line=dict(width=1.5, color="#ffffff"), opacity=0.92),
            customdata=np.stack(
                [
                    stage1["Direction_F1_Macro"],
                    stage1["Low_Jumper_Recall"],
                    stage1["OperationalUse"],
                ],
                axis=1,
            ),
            hovertemplate=(
                "<b>%{text}</b>"
                "<br>10-class F1: %{x:.3f}"
                "<br>High_Escalate recall: %{y:.3f}"
                "<br>Direction F1: %{customdata[0]:.3f}"
                "<br>Low_Jumper recall: %{customdata[1]:.3f}"
                "<br>Use: %{customdata[2]}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title="Stage 1 Trade-off: Overall Balance vs Escalation Sensitivity",
        margin=dict(l=20, r=20, t=60, b=30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        height=420,
    )
    fig.update_xaxes(title="10-class macro-F1", gridcolor="#dbe5ea")
    fig.update_yaxes(title="High_Escalate recall", range=[0, 1], gridcolor="#dbe5ea")
    return fig


def build_strategy_figure(stage2: pd.DataFrame) -> go.Figure:
    label_map = {
        "Global_Direct": "Global direct",
        "Y1Level_Direct": "Level-split direct",
        "Global_DirectPlusDirectionSignal": "Global + direction",
        "Y1Level_DirectPlusDirectionSignal": "Level-split + direction",
    }
    stage2 = stage2.copy()
    stage2["PlotLabel"] = stage2["Strategy"].map(label_map).fillna(stage2["Strategy"])
    metric_specs = [
        ("MAE", "Cost strategy metric: MAE", "#1f6f78", False, lambda s: fmt_currency(s)),
        ("R2_log", "Cost strategy metric: R2 log", "#275f83", True, lambda s: fmt_num(s)),
        ("WMAPE", "Cost strategy metric: WMAPE", "#9a6a1c", False, lambda s: fmt_num(s)),
        ("Direction_F1_Macro", "Cost strategy metric: Direction macro-F1", "#6c5b9a", True, lambda s: fmt_num(s)),
        ("Escalate_Recall", "Cost strategy metric: Escalate recall", "#a54834", True, lambda s: fmt_num(s)),
    ]

    fig = go.Figure()
    for idx, (metric, title, color, _, formatter) in enumerate(metric_specs):
        fig.add_trace(
            go.Bar(
                x=stage2["PlotLabel"],
                y=stage2[metric],
                marker_color=color,
                text=[formatter(v) for v in stage2[metric]],
                textposition="outside",
                cliponaxis=False,
                visible=(idx == 0),
                customdata=stage2["Strategy"],
                hovertemplate=f"<b>%{{customdata}}</b><br>{metric}: %{{text}}<extra></extra>",
            )
        )

    buttons = []
    for idx, (_, title, _, higher_is_better, _) in enumerate(metric_specs):
        visible = [False] * len(metric_specs)
        visible[idx] = True
        buttons.append(
            dict(
                label=title.split(":")[1].strip(),
                method="update",
                args=[
                    {"visible": visible},
                    {
                        "title": title,
                        "yaxis": {"title": "Metric value", "autorange": True},
                        "annotations": [
                            dict(
                                x=1,
                                y=1.12,
                                xref="paper",
                                yref="paper",
                                showarrow=False,
                                text="Higher is better" if higher_is_better else "Lower is better",
                                font=dict(color="#5a6d78", size=12),
                            )
                        ],
                    },
                ],
            )
        )

    fig.update_layout(
        title=metric_specs[0][1],
        updatemenus=[
            dict(
                type="dropdown",
                direction="down",
                x=0.02,
                y=1.18,
                xanchor="left",
                yanchor="top",
                showactive=True,
                buttons=buttons,
                bgcolor="#f8fbfd",
                bordercolor="#d3dde4",
                font=dict(size=12),
                pad=dict(r=6, t=4, b=4, l=6),
            )
        ],
        annotations=[
            dict(
                x=1,
                y=1.13,
                xref="paper",
                yref="paper",
                showarrow=False,
                text="Lower is better",
                font=dict(color="#5a6d78", size=12),
            )
        ],
        margin=dict(l=20, r=20, t=96, b=46),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        height=460,
    )
    fig.update_yaxes(gridcolor="#dbe5ea", automargin=True)
    fig.update_xaxes(tickangle=0, automargin=True)
    return fig


def build_segment_figure(level_perf: pd.DataFrame, direction_perf: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE by Known Year 1 Level", "MAE by Actual Direction"),
        horizontal_spacing=0.12,
    )
    fig.add_trace(
        go.Bar(
            x=[f"Level {int(v)}" for v in level_perf["Y1_LEVEL"]],
            y=level_perf["MAE"],
            marker_color=["#7aa7c7", "#4f88a8", "#1f607c"],
            text=[fmt_currency(v) for v in level_perf["MAE"]],
            textposition="outside",
            customdata=np.stack([level_perf["N"], level_perf["Mean_Actual_Cost"]], axis=1),
            hovertemplate="<b>%{x}</b><br>MAE: %{text}<br>N: %{customdata[0]:,.0f}<br>Mean actual cost: $%{customdata[1]:,.0f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=direction_perf["ActualDirection"],
            y=direction_perf["MAE"],
            marker_color=["#5aa469", "#d4a373", "#c75146"],
            text=[fmt_currency(v) for v in direction_perf["MAE"]],
            textposition="outside",
            customdata=np.stack([direction_perf["N"], direction_perf["Mean_Actual_Cost"]], axis=1),
            hovertemplate="<b>%{x}</b><br>MAE: %{text}<br>N: %{customdata[0]:,.0f}<br>Mean actual cost: $%{customdata[1]:,.0f}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        title="Where the Remaining Error Concentrates",
        margin=dict(l=20, r=20, t=70, b=40),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        showlegend=False,
        height=430,
    )
    fig.update_yaxes(title="MAE ($)", gridcolor="#dbe5ea", automargin=True)
    fig.update_xaxes(automargin=True)
    return fig


def build_feature_importance_figure(feature_importance: pd.DataFrame) -> go.Figure:
    meaning = {
        "LOG_COST_Y1": "Nonlinear prior-year spend signal.",
        "COST_Y1_ADJ": "Raw prior-year cost anchor.",
        "CNT_TOTAL_CONDITIONS": "Recorded disease burden.",
        "INSCOV_Y1": "Coverage and access context.",
        "UTIL_RX_Y1": "Refill intensity.",
        "CNT_RX_Y1": "Medication complexity.",
        "TOTAL_RX_COST_Y1": "Therapy intensity.",
        "COST_PER_CONDITION": "Spend intensity beyond condition count.",
    }
    top = feature_importance.head(10).copy().sort_values("Importance")
    fig = go.Figure(
        data=go.Bar(
            x=top["Importance"],
            y=top["Feature"],
            orientation="h",
            marker_color="#1f6f78",
            customdata=[meaning.get(x, "Predictive contribution within the selected direct model.") for x in top["Feature"]],
            hovertemplate="<b>%{y}</b><br>Importance: %{x:.3f}<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Top Predictors in the Selected Direct Cost Model",
        margin=dict(l=28, r=20, t=60, b=30),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        height=430,
    )
    fig.update_xaxes(title="Importance", gridcolor="#dbe5ea", automargin=True)
    fig.update_yaxes(automargin=True)
    return fig


def build_ablation_figure(ablation: pd.DataFrame) -> go.Figure:
    ablation = ablation.copy()
    ablation["MAE_Gain_vs_Base"] = ablation["MAE_Gain_vs_Base"].astype(float)
    ablation["Direction_F1_Gain_vs_Base"] = ablation["Direction_F1_Gain_vs_Base"].astype(float)
    ablation["ShortLabel"] = ["Base", "Direct feat.", "Care/Rx feat.", "Y1 split"]
    fig = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=("MAE Improvement vs Base", "Direction F1 Improvement vs Base"),
        horizontal_spacing=0.14,
    )
    fig.add_trace(
        go.Bar(
            x=ablation["ShortLabel"],
            y=ablation["MAE_Gain_vs_Base"],
            marker_color=["#aab7bf", "#2d7d60", "#c77d2a", "#a54834"],
            text=[fmt_currency(v) for v in ablation["MAE_Gain_vs_Base"]],
            textposition="outside",
            cliponaxis=False,
            customdata=ablation["Model"],
            hovertemplate="<b>%{customdata}</b><br>MAE gain vs base: %{text}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            x=ablation["ShortLabel"],
            y=ablation["Direction_F1_Gain_vs_Base"],
            marker_color=["#aab7bf", "#275f83", "#5b8f61", "#a54834"],
            text=[fmt_num(v, 3) for v in ablation["Direction_F1_Gain_vs_Base"]],
            textposition="outside",
            cliponaxis=False,
            customdata=ablation["Model"],
            hovertemplate="<b>%{customdata}</b><br>Direction F1 gain vs base: %{text}<extra></extra>",
        ),
        row=1,
        col=2,
    )
    fig.update_layout(
        title="Ablation: What Added Value and What Added Complexity",
        margin=dict(l=20, r=20, t=70, b=46),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        showlegend=False,
        height=430,
    )
    fig.update_yaxes(gridcolor="#dbe5ea", automargin=True)
    fig.update_xaxes(automargin=True)
    return fig


def feature_screen_table(feature_screen: pd.DataFrame) -> str:
    table_df = feature_screen[
        ["Feature", "Decision", "Corr_Y2_Cost", "Corr_Delta", "ClinicalRationale"]
    ].copy()
    table_df["Corr_Y2_Cost"] = table_df["Corr_Y2_Cost"].map(lambda x: fmt_num(float(x), 3))
    table_df["Corr_Delta"] = table_df["Corr_Delta"].map(lambda x: fmt_num(float(x), 3))
    table_df.columns = ["Feature", "Decision", "Cost corr.", "Delta corr.", "Healthcare meaning"]

    head = "".join(f"<th>{html.escape(str(col))}</th>" for col in table_df.columns)
    rows = []
    for _, row in table_df.iterrows():
        decision = str(row["Decision"]).lower()
        decision_badge = f"<span class='decision-badge {decision}'>{html.escape(str(row['Decision']))}</span>"
        cells = []
        for col in table_df.columns:
            value = decision_badge if col == "Decision" else html.escape(str(row[col]))
            cells.append(f"<td>{value}</td>")
        rows.append(f"<tr data-feature-filter='{decision}'>{''.join(cells)}</tr>")
    return f"""
    <div class="table-controls">
      <button class="filter-btn active" data-target="feature-screen" data-value="all">All</button>
      <button class="filter-btn" data-target="feature-screen" data-value="keep">Keep</button>
      <button class="filter-btn" data-target="feature-screen" data-value="drop">Drop</button>
    </div>
    <div class="table-shell">
      <div class="table-scroll">
        <table class="dashboard-table" id="feature-screen">
          <thead><tr>{head}</tr></thead>
          <tbody>{''.join(rows)}</tbody>
        </table>
      </div>
    </div>
    """


def action_cards() -> str:
    cards = [
        (
            "Flag low-cost members with heavy pharmacy burden",
            "High TOTAL_RX_COST_Y1, high CNT_RX_Y1, and polypharmacy were concentrated among future jumpers even before total spending looked alarming.",
            "Use pharmacist review or chronic-care outreach earlier instead of waiting for the total cost signal to catch up.",
        ),
        (
            "Treat refill disruption as a deterioration signal",
            "High RX_GAP_RATIO and long RX_TRAILING_GAP align with worsening rather than with well-managed chronic persistence.",
            "Use refill-gap alerts for adherence outreach and care coordination, especially before the next review cycle.",
        ),
        (
            "Prioritize high-cost patients with acute instability",
            "The largest dollar error remained in patients who were already expensive and then escalated, especially when acute or inpatient use was present.",
            "Use the dashboard to direct post-discharge follow-up and high-touch case management to that segment first.",
        ),
        (
            "Use the model for prioritization, not exact budgeting",
            "The direct model is useful for ranking and sensitivity planning, but the hardest escalators still carry large absolute error.",
            "Do not treat predicted dollars as fixed patient-level budgets; use them as signals for review intensity and resource allocation.",
        ),
    ]
    rendered = []
    for idx, (title, why, action) in enumerate(cards, start=1):
        rendered.append(
            f"""
            <article class="accordion-card">
              <button class="accordion-trigger" data-accordion="card-{idx}">
                <span>{html.escape(title)}</span>
                <span class="accordion-plus">+</span>
              </button>
              <div class="accordion-body" id="card-{idx}">
                <p><strong>Why it matters:</strong> {html.escape(why)}</p>
                <p><strong>Recommended action:</strong> {html.escape(action)}</p>
              </div>
            </article>
            """
        )
    return "".join(rendered)


def export_code_html(source_path: Path, output_path: Path) -> None:
    code = source_path.read_text(encoding="utf-8")
    try:
        from pygments import highlight
        from pygments.formatters import HtmlFormatter
        from pygments.lexers import PythonLexer

        formatter = HtmlFormatter(style="friendly", full=False, linenos=True, cssclass="codehilite")
        highlighted = highlight(code, PythonLexer(), formatter)
        style = formatter.get_style_defs(".codehilite")
    except Exception:
        highlighted = f"<pre>{html.escape(code)}</pre>"
        style = """
        body { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; background: #f7f9fb; color: #18232f; }
        pre { white-space: pre-wrap; word-break: break-word; line-height: 1.5; font-size: 13px; }
        """

    output_path.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Code for Dashboard</title>
  <style>
    body {{
      margin: 0;
      background: #f4f7fa;
      color: #173b4d;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
    }}
    .shell {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      background: linear-gradient(135deg, #173b4d 0%, #1f6f78 100%);
      color: white;
      border-radius: 24px;
      padding: 26px 28px;
      margin-bottom: 20px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 2rem;
    }}
    p {{
      margin: 0;
      line-height: 1.6;
      color: rgba(255,255,255,0.88);
    }}
    .code-wrap {{
      background: white;
      border: 1px solid #d8e1e8;
      border-radius: 20px;
      padding: 20px;
      overflow: auto;
      box-shadow: 0 18px 40px rgba(23, 59, 77, 0.08);
    }}
    {style}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <h1>Code for Dashboard</h1>
      <p>Python source used to build the interactive MEPS healthcare decision dashboard.</p>
    </section>
    <section class="code-wrap">{highlighted}</section>
  </div>
</body>
</html>
""",
        encoding="utf-8",
    )


def build_dashboard_html() -> str:
    analytic = pd.read_parquet(DATA_DIR / "model_ready_stage2.parquet")
    stage1 = pd.read_csv(TABLES_DIR / "stage1_experiment_results.csv")
    stage2_strategy = pd.read_csv(TABLES_DIR / "stage2_direct_strategy_comparison.csv").sort_values("MAE").reset_index(drop=True)
    direction = pd.read_csv(TABLES_DIR / "stage2_direction_model_performance.csv")
    level_perf = pd.read_csv(TABLES_DIR / "stage2_direct_level_performance.csv")
    direction_perf = pd.read_csv(TABLES_DIR / "stage2_direct_direction_group_performance.csv")
    feature_importance = pd.read_csv(TABLES_DIR / "stage2_direct_feature_importance.csv")
    feature_screen = pd.read_csv(TABLES_DIR / "stage2_feature_screening.csv")
    ablation = pd.read_csv(TABLES_DIR / "stage2_direct_ablation.csv")

    total_n = len(analytic)
    train_n = int((analytic["PANEL"] <= 21).sum())
    val_n = int((analytic["PANEL"] == 22).sum())
    test_n = int((analytic["PANEL"] == 23).sum())
    direction_mix = pd.Series(
        np.where(analytic["DELTA_BIN"] < 0, "Improve", np.where(analytic["DELTA_BIN"] == 0, "Stable", "Escalate"))
    ).value_counts()

    best_strategy = stage2_strategy.iloc[0]
    direction_row = direction.iloc[0]
    hardest_level = level_perf.sort_values("MAE", ascending=False).iloc[0]
    hardest_direction = direction_perf.sort_values("MAE", ascending=False).iloc[0]
    best_stage1 = stage1.sort_values("F1_Macro_10Class", ascending=False).iloc[0]

    strategy_table = stage2_strategy[
        ["Strategy", "FeatureCount", "MAE", "R2_log", "WMAPE", "MAE_vs_Best"]
    ].copy()
    strategy_table["FeatureCount"] = strategy_table["FeatureCount"].map(lambda x: fmt_int(int(x)))
    strategy_table["MAE"] = strategy_table["MAE"].map(lambda x: fmt_currency(float(x)))
    strategy_table["R2_log"] = strategy_table["R2_log"].map(lambda x: fmt_num(float(x)))
    strategy_table["WMAPE"] = strategy_table["WMAPE"].map(lambda x: fmt_num(float(x)))
    strategy_table["MAE_vs_Best"] = strategy_table["MAE_vs_Best"].map(lambda x: fmt_currency(float(x)))
    strategy_table.columns = ["Strategy", "Features", "MAE", "R2 log", "WMAPE", "Extra MAE"]

    stage1_table = stage1[
        ["Experiment", "F1_Macro_10Class", "Direction_F1_Macro", "Low_Jumper_Recall", "High_Escalate_Recall"]
    ].copy()
    stage1_table["F1_Macro_10Class"] = stage1_table["F1_Macro_10Class"].map(lambda x: fmt_num(float(x)))
    stage1_table["Direction_F1_Macro"] = stage1_table["Direction_F1_Macro"].map(lambda x: fmt_num(float(x)))
    stage1_table["Low_Jumper_Recall"] = stage1_table["Low_Jumper_Recall"].map(lambda x: fmt_num(float(x)))
    stage1_table["High_Escalate_Recall"] = stage1_table["High_Escalate_Recall"].map(lambda x: fmt_num(float(x)))
    stage1_table.columns = ["Policy", "10-class F1", "Direction F1", "Low_Jumper rec.", "High_Esc. rec."]

    challenge_table = pd.DataFrame(
        [
            (
                f"Y1 level {int(hardest_level['Y1_LEVEL'])}",
                fmt_int(int(hardest_level["N"])),
                fmt_currency(float(hardest_level["Mean_Actual_Cost"])),
                fmt_currency(float(hardest_level["MAE"])),
                "High-cost persistence remains hardest to forecast cleanly.",
            ),
            (
                str(hardest_direction["ActualDirection"]),
                fmt_int(int(hardest_direction["N"])),
                fmt_currency(float(hardest_direction["Mean_Actual_Cost"])),
                fmt_currency(float(hardest_direction["MAE"])),
                "True worsening patients still absorb the largest dollar error.",
            ),
        ],
        columns=["Challenge segment", "N", "Mean actual cost", "MAE", "Interpretation"],
    )

    transition_div = plot_div(build_transition_heatmap(analytic), include_js=True)
    stage1_div = plot_div(build_stage1_tradeoff(stage1))
    strategy_div = plot_div(build_strategy_figure(stage2_strategy))
    segment_div = plot_div(build_segment_figure(level_perf, direction_perf))
    feature_div = plot_div(build_feature_importance_figure(feature_importance))
    ablation_div = plot_div(build_ablation_figure(ablation))

    hero_cards = "".join(
        [
            metric_card("Analytic cohort", fmt_int(total_n), "Adults across pooled MEPS panels 18-23"),
            metric_card("Selected cost strategy", str(best_strategy["Strategy"]), "Lowest held-out dollar error", "success"),
            metric_card("Cost MAE", fmt_currency(float(best_strategy["MAE"])), "Held-out Year 2 expenditure error"),
            metric_card("Direction macro-F1", fmt_num(float(direction_row["F1_Macro"])), "Standalone Improve / Stable / Escalate model"),
            metric_card("Escalate recall", fmt_num(float(direction_row["Escalate_Recall"])), "Sensitivity for worsening cases", "warning"),
            metric_card(
                "Hardest segment",
                f"Y1 level {int(hardest_level['Y1_LEVEL'])}",
                f"MAE {fmt_currency(float(hardest_level['MAE']))}",
                "danger",
            ),
        ]
    )

    hero_chips = "".join(
        [
            info_chip("Panels", "18-23"),
            info_chip("Train / Val / Test", f"{fmt_int(train_n)} / {fmt_int(val_n)} / {fmt_int(test_n)}"),
            info_chip(
                "Direction mix",
                f"I {fmt_pct(direction_mix['Improve'] / total_n)} · S {fmt_pct(direction_mix['Stable'] / total_n)} · E {fmt_pct(direction_mix['Escalate'] / total_n)}",
            ),
        ]
    )

    direction_cards = "".join(
        [
            metric_card("Accuracy", fmt_num(float(direction_row["Accuracy"])), "Direction model", compact=True),
            metric_card("Improve recall", fmt_num(float(direction_row["Improve_Recall"])), "Best captured", compact=True),
            metric_card("Stable recall", fmt_num(float(direction_row["Stable_Recall"])), "Most ambiguous", compact=True),
            metric_card("Escalate recall", fmt_num(float(direction_row["Escalate_Recall"])), "Priority worsening", "warning", compact=True),
        ]
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>MEPS Healthcare Cost Decision Dashboard</title>
  <style>
    :root {{
      --navy: #173b4d;
      --teal: #1f6f78;
      --steel: #4f88a8;
      --gold: #b7791f;
      --sand: #f5f1ea;
      --paper: #ffffff;
      --line: #d9e3ea;
      --ink: #18232f;
      --muted: #5b6d79;
      --success: #2d7d60;
      --warning: #b7791f;
      --danger: #a54834;
      --shadow: 0 18px 42px rgba(23, 59, 77, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; overflow-x: hidden; }}
    body {{
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(31,111,120,0.08), transparent 26%),
        linear-gradient(180deg, #f7fafc 0%, #f3eee6 100%);
      overflow-x: hidden;
    }}
    h1, h2, h3, h4 {{
      margin: 0;
      color: var(--navy);
      font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
      letter-spacing: -0.02em;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }}
    .shell {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px 20px 48px;
      width: 100%;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      background: linear-gradient(135deg, #173b4d 0%, #24506b 55%, #1f6f78 100%);
      border-radius: 30px;
      padding: 34px 36px;
      color: white;
      box-shadow: var(--shadow);
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -120px;
      bottom: -140px;
      width: 320px;
      height: 320px;
      background: radial-gradient(circle, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0) 72%);
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,0.12);
      border: 1px solid rgba(255,255,255,0.16);
      font-size: 0.84rem;
      margin-bottom: 16px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
      gap: 24px;
      align-items: end;
    }}
    .hero-copy h1 {{
      color: white;
      font-size: clamp(2.1rem, 3vw, 3.2rem);
      margin-bottom: 14px;
      line-height: 1.03;
    }}
    .hero-copy p {{
      color: rgba(255,255,255,0.9);
      font-size: 1rem;
      max-width: 760px;
    }}
    .chip-stack {{
      display: grid;
      gap: 10px;
    }}
    .info-chip {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 12px 14px;
      border-radius: 16px;
      background: rgba(255,255,255,0.1);
      border: 1px solid rgba(255,255,255,0.15);
    }}
    .chip-label {{
      color: rgba(255,255,255,0.76);
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .chip-value {{
      color: white;
      font-weight: 700;
      text-align: right;
    }}
    .quick-nav {{
      position: sticky;
      top: 0;
      z-index: 20;
      margin: 18px 0 26px;
      padding: 12px;
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      border-radius: 18px;
      background: rgba(255,255,255,0.84);
      border: 1px solid rgba(23,59,77,0.08);
      backdrop-filter: blur(10px);
      box-shadow: 0 10px 26px rgba(23,59,77,0.06);
    }}
    .quick-nav a {{
      text-decoration: none;
      color: var(--navy);
      font-size: 0.92rem;
      padding: 8px 12px;
      border-radius: 999px;
      background: #f8fbfd;
      border: 1px solid var(--line);
    }}
    .section {{
      margin-top: 24px;
      background: rgba(255,255,255,0.88);
      border: 1px solid rgba(23,59,77,0.08);
      border-radius: 26px;
      padding: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .section-head {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: end;
      margin-bottom: 18px;
    }}
    .section-head p {{
      max-width: 820px;
    }}
    .section-kicker {{
      display: inline-block;
      margin-bottom: 8px;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--teal);
      font-weight: 800;
    }}
    .section h2 {{
      font-size: 1.9rem;
      margin-bottom: 8px;
    }}
    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 14px;
    }}
    .metric-grid-compact {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      min-width: 0;
    }}
    .metric-card {{
      min-height: 136px;
      padding: 16px;
      border-radius: 20px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fbfd 100%);
      border: 1px solid var(--line);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      min-width: 0;
      overflow: hidden;
    }}
    .metric-card.compact {{
      min-height: 118px;
      padding: 14px;
    }}
    .tone-success {{ border-top: 4px solid var(--success); }}
    .tone-warning {{ border-top: 4px solid var(--warning); }}
    .tone-danger {{ border-top: 4px solid var(--danger); }}
    .metric-label {{
      font-size: 0.82rem;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .metric-value {{
      font-size: clamp(1.55rem, 2.3vw, 1.72rem);
      font-weight: 800;
      color: var(--navy);
      line-height: 1.08;
      overflow-wrap: anywhere;
    }}
    .metric-note {{
      font-size: 0.94rem;
      color: var(--muted);
      overflow-wrap: anywhere;
    }}
    .split {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 0.95fr);
      gap: 18px;
      min-width: 0;
    }}
    .stack {{
      display: grid;
      gap: 18px;
      min-width: 0;
    }}
    .card {{
      background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 18px;
      min-width: 0;
      overflow: hidden;
    }}
    .card h3 {{
      font-size: 1.2rem;
      margin-bottom: 10px;
    }}
    .card p + p {{
      margin-top: 10px;
    }}
    .chart-card {{
      padding: 16px;
      min-width: 0;
      overflow: hidden;
    }}
    .chart-card .plotly-graph-div {{
      width: 100% !important;
      min-width: 0 !important;
    }}
    .js-plotly-plot, .plot-container {{
      width: 100% !important;
      min-width: 0 !important;
    }}
    .table-shell {{
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: white;
      min-width: 0;
    }}
    .table-scroll {{
      overflow: auto;
      max-width: 100%;
    }}
    .dashboard-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.9rem;
      min-width: 0;
      table-layout: auto;
    }}
    .dashboard-table th {{
      background: #eef4f7;
      color: var(--navy);
      text-align: left;
      padding: 10px 12px;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    .dashboard-table td {{
      padding: 10px 12px;
      border-top: 1px solid #ecf1f4;
      vertical-align: top;
      color: var(--ink);
      overflow-wrap: anywhere;
      word-break: break-word;
    }}
    .dashboard-table tr:hover td {{
      background: #f7fbfd;
    }}
    .table-controls {{
      display: flex;
      gap: 8px;
      margin-bottom: 10px;
      flex-wrap: wrap;
    }}
    .filter-btn {{
      border: 1px solid var(--line);
      background: white;
      color: var(--navy);
      border-radius: 999px;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 0.9rem;
    }}
    .filter-btn.active {{
      background: var(--navy);
      color: white;
      border-color: var(--navy);
    }}
    .decision-badge {{
      display: inline-flex;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 700;
    }}
    .decision-badge.keep {{
      background: rgba(45,125,96,0.12);
      color: var(--success);
    }}
    .decision-badge.drop {{
      background: rgba(165,72,52,0.12);
      color: var(--danger);
    }}
    .action-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      min-width: 0;
    }}
    .accordion-card {{
      border: 1px solid var(--line);
      border-radius: 20px;
      background: white;
      overflow: hidden;
    }}
    .accordion-trigger {{
      width: 100%;
      border: 0;
      background: transparent;
      color: var(--navy);
      text-align: left;
      padding: 16px 18px;
      display: flex;
      justify-content: space-between;
      gap: 14px;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
    }}
    .accordion-plus {{
      color: var(--teal);
      font-size: 1.2rem;
    }}
    .accordion-body {{
      display: none;
      padding: 0 18px 18px;
      border-top: 1px solid #edf1f4;
    }}
    .accordion-body.open {{
      display: block;
    }}
    .footer-note {{
      margin-top: 14px;
      font-size: 0.9rem;
      color: var(--muted);
    }}
    @media (max-width: 1180px) {{
      .metric-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .metric-grid-compact {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .split {{ grid-template-columns: 1fr; }}
      .action-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-width: 780px) {{
      .shell {{ padding: 16px; }}
      .hero {{ padding: 24px; }}
      .hero-grid {{ grid-template-columns: 1fr; }}
      .metric-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .metric-grid-compact {{ grid-template-columns: 1fr; }}
      .section {{ padding: 18px; }}
      .dashboard-table {{ min-width: 520px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="eyebrow">Interactive dashboard · MEPS healthcare expenditure prediction</div>
      <div class="hero-grid">
        <div class="hero-copy">
          <h1>Decision Dashboard for Year 2 Cost and Worsening Risk</h1>
          <p>This dashboard translates the latest notebook outputs into an interactive decision view. It is built for prioritization: where risk is concentrated, which model structure held up best, and which healthcare signals are actionable before Year 2 spending fully escalates.</p>
        </div>
        <div class="chip-stack">{hero_chips}</div>
      </div>
    </section>

    <nav class="quick-nav">
      <a href="#summary">Summary</a>
      <a href="#risk">Risk Landscape</a>
      <a href="#stage1">Stage 1</a>
      <a href="#stage2">Stage 2</a>
      <a href="#segments">Challenge Segments</a>
      <a href="#features">Features</a>
      <a href="#actions">Actions</a>
    </nav>

    <section class="section" id="summary">
      <div class="section-head">
        <div>
          <span class="section-kicker">Executive summary</span>
          <h2>What the final workflow supports</h2>
          <p>The current workflow is strongest as a prioritization system. It estimates next-year cost directly, predicts worsening direction separately, and keeps Stage 1 as a diagnostic layer rather than as a hard routing gate.</p>
        </div>
      </div>
      <div class="metric-grid">{hero_cards}</div>
    </section>

    <section class="section" id="risk">
      <div class="section-head">
        <div>
          <span class="section-kicker">Notebook 5.0</span>
          <h2>Risk landscape</h2>
          <p>The cohort is dominated by persistence, but the meaningful challenge is upward movement from apparently modest starting points. Hover over the heatmap to inspect transition shares and counts.</p>
        </div>
      </div>
      <div class="card chart-card">{transition_div}</div>
      <p class="footer-note">Decision reading: low and moderate baseline-cost members do not all remain low risk. The dashboard keeps this transition structure visible so care managers can treat worsening as a separate planning problem, not just a by-product of high current spend.</p>
    </section>

    <section class="section" id="stage1">
      <div class="section-head">
        <div>
          <span class="section-kicker">Notebook 5.1</span>
          <h2>Stage 1 is diagnostic, not routing</h2>
          <p>The interactive scatter shows the trade-off between overall class balance and sensitivity to true escalators. Bubble size reflects Low_Jumper recall. The best overall Stage 1 policy reached 10-class macro-F1 {fmt_num(float(best_stage1["F1_Macro_10Class"]))}, but the rare-event trade-offs remained too unstable for hard routing.</p>
        </div>
      </div>
      <div class="split">
        <div class="card chart-card">{stage1_div}</div>
        <div class="stack">
          <div class="card">
            <h3>How to read Stage 1</h3>
            <p>Stage 1 did add value: it ranked worsening risk and amplified rare-event lift. What it did not do reliably enough was separate all ten trajectory classes cleanly enough to decide which downstream expert should own a patient.</p>
            <p>That is why the final design keeps Stage 1 for risk explanation and review queues, not for routing the Stage 2 cost model.</p>
          </div>
          {render_table(stage1_table, "stage1-table")}
        </div>
      </div>
    </section>

    <section class="section" id="stage2">
      <div class="section-head">
        <div>
          <span class="section-kicker">Notebook 5.2</span>
          <h2>Selected operating model</h2>
          <p>The direct cost model and the standalone direction model are shown separately because they solve different healthcare questions. Use the buttons above the chart to switch the metric used to compare cost strategies.</p>
        </div>
      </div>
      <div class="split">
        <div class="card chart-card">{strategy_div}</div>
        <div class="stack">
          <div class="metric-grid-compact">{direction_cards}</div>
          {render_table(strategy_table, "strategy-table")}
        </div>
      </div>
      <p class="footer-note">Decision reading: the simplest direct cost strategy retained the best dollar error. Adding subgroup routing or extra direction signal did not justify the extra complexity.</p>
    </section>

    <section class="section" id="segments">
      <div class="section-head">
        <div>
          <span class="section-kicker">Residual diagnostics</span>
          <h2>Where the model still struggles</h2>
          <p>The remaining miss is concentrated in already expensive members and in true escalators. This is the part of the portfolio that needs higher-touch operational review.</p>
        </div>
      </div>
      <div class="split">
        <div class="card chart-card">{segment_div}</div>
        {render_table(challenge_table, "challenge-table")}
      </div>
    </section>

    <section class="section" id="features">
      <div class="section-head">
        <div>
          <span class="section-kicker">Feature logic</span>
          <h2>Signals that survived screening</h2>
          <p>The selected model is still anchored by Year 1 spend, but the next strongest predictors are clinically interpretable: disease burden, refill intensity, medication complexity, therapy intensity, and spending intensity relative to condition count.</p>
        </div>
      </div>
      <div class="split">
        <div class="stack">
          <div class="card chart-card">{feature_div}</div>
          <div class="card chart-card">{ablation_div}</div>
        </div>
        <div class="stack">
          <div class="card">
            <h3>Feature screening</h3>
            <p>Use the filter buttons to switch between retained and dropped engineered features. The point of screening was not to maximize feature count, but to keep only signals with distinct clinical meaning.</p>
            {feature_screen_table(feature_screen)}
          </div>
        </div>
      </div>
      <p class="footer-note">Decision reading: refill disruption and care-pattern features help explain deterioration, but they do not justify fragmenting the cost model into many subgroup-specific paths.</p>
    </section>

    <section class="section" id="actions">
      <div class="section-head">
        <div>
          <span class="section-kicker">Action priorities</span>
          <h2>What teams can do with this now</h2>
          <p>These actions follow directly from the notebook evidence. Open each card for the reasoning and the practical implication.</p>
        </div>
      </div>
      <div class="action-grid">{action_cards()}</div>
      <p class="footer-note">The dashboard is most appropriate for triage, review prioritization, and budget sensitivity work. It should not be treated as an exact patient-level pricing engine.</p>
    </section>
  </div>

  <script>
    document.querySelectorAll('.filter-btn').forEach((button) => {{
      button.addEventListener('click', () => {{
        const target = button.dataset.target;
        const value = button.dataset.value;
        document.querySelectorAll(`.filter-btn[data-target="${{target}}"]`).forEach((btn) => btn.classList.remove('active'));
        button.classList.add('active');
        document.querySelectorAll(`#${{target}} tbody tr`).forEach((row) => {{
          const rowValue = row.dataset.featureFilter;
          row.style.display = value === 'all' || rowValue === value ? '' : 'none';
        }});
      }});
    }});

    document.querySelectorAll('.accordion-trigger').forEach((button) => {{
      button.addEventListener('click', () => {{
        const body = button.parentElement.querySelector('.accordion-body');
        const plus = button.querySelector('.accordion-plus');
        const open = body.classList.toggle('open');
        plus.textContent = open ? '−' : '+';
      }});
    }});
  </script>
</body>
</html>
"""
    return html_doc


def main() -> None:
    OUTPUT_DASHBOARD.write_text(build_dashboard_html(), encoding="utf-8")
    export_code_html(Path(__file__), OUTPUT_CODE_HTML)
    print(f"Wrote {OUTPUT_DASHBOARD}")
    print(f"Wrote {OUTPUT_CODE_HTML}")


if __name__ == "__main__":
    main()
