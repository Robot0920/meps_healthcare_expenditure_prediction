from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from scripts import build_decision_dashboard as dashboard


st.set_page_config(
    page_title="MEPS Healthcare Cost Decision Dashboard",
    page_icon=":bar_chart:",
    layout="wide",
)

REPO_ROOT = Path(__file__).resolve().parent
TABLES_DIR = REPO_ROOT / "reports" / "tables"
DATA_DIR = REPO_ROOT / "data" / "processed_v2"

PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "lasso2d",
        "select2d",
        "autoScale2d",
        "hoverCompareCartesian",
        "toggleSpikelines",
    ],
}

STRATEGY_LABELS = {
    "Global_Direct": "Global direct",
    "Y1Level_Direct": "Level-split direct",
    "Global_DirectPlusDirectionSignal": "Global + direction",
    "Y1Level_DirectPlusDirectionSignal": "Level-split + direction",
}

STRATEGY_METRICS = {
    "MAE": {
        "label": "MAE",
        "title": "Stage 2 Strategy Comparison by MAE",
        "subtitle": "Held-out Year 2 dollar error",
        "higher_is_better": False,
        "formatter": dashboard.fmt_currency,
        "accent": "#1f6f78",
        "muted": "#a9bac4",
    },
    "R2_log": {
        "label": "R2 log",
        "title": "Stage 2 Strategy Comparison by R2 log",
        "subtitle": "Fit on the log-spend target",
        "higher_is_better": True,
        "formatter": dashboard.fmt_num,
        "accent": "#275f83",
        "muted": "#aec4d7",
    },
    "WMAPE": {
        "label": "WMAPE",
        "title": "Stage 2 Strategy Comparison by WMAPE",
        "subtitle": "Weighted percentage error",
        "higher_is_better": False,
        "formatter": dashboard.fmt_num,
        "accent": "#b7791f",
        "muted": "#d9c39d",
    },
    "Direction_F1_Macro": {
        "label": "Direction macro-F1",
        "title": "Stage 2 Strategy Comparison by Direction macro-F1",
        "subtitle": "How well the strategy aligns with worsening direction",
        "higher_is_better": True,
        "formatter": dashboard.fmt_num,
        "accent": "#6c5b9a",
        "muted": "#c7bfdc",
    },
    "Escalate_Recall": {
        "label": "Escalate recall",
        "title": "Stage 2 Strategy Comparison by Escalate recall",
        "subtitle": "Sensitivity for worsening members",
        "higher_is_better": True,
        "formatter": dashboard.fmt_num,
        "accent": "#a54834",
        "muted": "#deb3ab",
    },
}

ACTION_ITEMS = [
    {
        "title": "Flag low-cost members with heavy pharmacy burden",
        "why": (
            "High TOTAL_RX_COST_Y1, high CNT_RX_Y1, and polypharmacy were "
            "concentrated among future jumpers even before total spending "
            "looked alarming."
        ),
        "action": (
            "Use pharmacist review or chronic-care outreach earlier instead of "
            "waiting for the total cost signal to catch up."
        ),
    },
    {
        "title": "Treat refill disruption as a deterioration signal",
        "why": (
            "High RX_GAP_RATIO and long RX_TRAILING_GAP align with worsening "
            "rather than with well-managed chronic persistence."
        ),
        "action": (
            "Use refill-gap alerts for adherence outreach and care coordination, "
            "especially before the next review cycle."
        ),
    },
    {
        "title": "Prioritize high-cost patients with acute instability",
        "why": (
            "The largest dollar error remained in patients who were already "
            "expensive and then escalated, especially when acute or inpatient "
            "use was present."
        ),
        "action": (
            "Use the dashboard to direct post-discharge follow-up and high-touch "
            "case management to that segment first."
        ),
    },
    {
        "title": "Use the model for prioritization, not exact budgeting",
        "why": (
            "The direct model is useful for ranking and sensitivity planning, "
            "but the hardest escalators still carry large absolute error."
        ),
        "action": (
            "Do not treat predicted dollars as fixed patient-level budgets; use "
            "them as signals for review intensity and resource allocation."
        ),
    },
]


@st.cache_data(show_spinner=False)
def load_dashboard_data() -> dict[str, pd.DataFrame]:
    return {
        "analytic": pd.read_parquet(DATA_DIR / "model_ready_stage2.parquet"),
        "stage1": pd.read_csv(TABLES_DIR / "stage1_experiment_results.csv"),
        "stage2_strategy": pd.read_csv(TABLES_DIR / "stage2_direct_strategy_comparison.csv")
        .sort_values("MAE")
        .reset_index(drop=True),
        "direction": pd.read_csv(TABLES_DIR / "stage2_direction_model_performance.csv"),
        "level_perf": pd.read_csv(TABLES_DIR / "stage2_direct_level_performance.csv"),
        "direction_perf": pd.read_csv(TABLES_DIR / "stage2_direct_direction_group_performance.csv"),
        "feature_importance": pd.read_csv(TABLES_DIR / "stage2_direct_feature_importance.csv"),
        "feature_screen": pd.read_csv(TABLES_DIR / "stage2_feature_screening.csv"),
        "ablation": pd.read_csv(TABLES_DIR / "stage2_direct_ablation.csv"),
    }


def inject_styles() -> None:
    st.markdown(
        """
        <style>
          :root {
            --navy: #173b4d;
            --teal: #1f6f78;
            --steel: #4f88a8;
            --gold: #b7791f;
            --paper: #ffffff;
            --muted: #5b6d79;
            --line: #d9e3ea;
            --success: #2d7d60;
            --warning: #b7791f;
            --danger: #a54834;
          }

          .stApp {
            background:
              radial-gradient(circle at top left, rgba(31, 111, 120, 0.08), transparent 26%),
              linear-gradient(180deg, #f7fafc 0%, #f3eee6 100%);
          }

          .block-container {
            max-width: 1320px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
          }

          [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #f9fbfc 0%, #f4efe7 100%);
            border-right: 1px solid rgba(23, 59, 77, 0.08);
          }

          .hero-banner {
            position: relative;
            overflow: hidden;
            background: linear-gradient(135deg, #173b4d 0%, #24506b 55%, #1f6f78 100%);
            border-radius: 30px;
            padding: 2rem 2.2rem;
            color: white;
            box-shadow: 0 18px 42px rgba(23, 59, 77, 0.08);
            margin-bottom: 1rem;
          }

          .hero-banner::after {
            content: "";
            position: absolute;
            right: -120px;
            bottom: -140px;
            width: 320px;
            height: 320px;
            background: radial-gradient(circle, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0) 72%);
          }

          .hero-grid {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.7fr);
            gap: 1.2rem;
            align-items: end;
          }

          .eyebrow {
            display: inline-flex;
            align-items: center;
            gap: 0.6rem;
            padding: 0.45rem 0.8rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.16);
            font-size: 0.84rem;
            margin-bottom: 1rem;
          }

          .hero-title {
            color: white;
            font-size: clamp(2.1rem, 3vw, 3.2rem);
            line-height: 1.02;
            margin: 0 0 0.8rem;
          }

          .hero-body {
            color: rgba(255, 255, 255, 0.9);
            font-size: 1rem;
            line-height: 1.65;
            max-width: 760px;
            margin: 0;
          }

          .chip-stack {
            display: grid;
            gap: 0.7rem;
          }

          .info-chip {
            display: flex;
            justify-content: space-between;
            gap: 0.8rem;
            padding: 0.8rem 0.95rem;
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.15);
          }

          .chip-label {
            color: rgba(255, 255, 255, 0.74);
            font-size: 0.82rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
          }

          .chip-value {
            color: white;
            font-weight: 700;
            text-align: right;
          }

          .metric-card {
            min-height: 136px;
            padding: 1rem;
            border-radius: 20px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, #f8fbfd 100%);
            border: 1px solid var(--line);
            border-top: 4px solid transparent;
            box-shadow: 0 16px 34px rgba(23, 59, 77, 0.05);
            margin: 0.25rem 0 0.75rem;
          }

          .metric-card.success { border-top-color: var(--success); }
          .metric-card.warning { border-top-color: var(--warning); }
          .metric-card.danger { border-top-color: var(--danger); }

          .metric-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin-bottom: 0.6rem;
          }

          .metric-value {
            font-size: clamp(1.45rem, 2.2vw, 1.85rem);
            font-weight: 800;
            color: var(--navy);
            line-height: 1.08;
            margin-bottom: 0.5rem;
          }

          .metric-note {
            color: var(--muted);
            line-height: 1.55;
          }

          .section-kicker {
            display: inline-block;
            margin-bottom: 0.35rem;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--teal);
            font-weight: 800;
          }

          .section-title {
            color: var(--navy);
            margin: 0 0 0.45rem;
            font-size: clamp(1.6rem, 2.3vw, 2rem);
            line-height: 1.08;
          }

          .section-body {
            color: var(--muted);
            line-height: 1.7;
            max-width: 820px;
            margin: 0 0 0.6rem;
          }

          .narrative-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(23, 59, 77, 0.08);
            border-radius: 22px;
            padding: 1.1rem 1.15rem;
            box-shadow: 0 16px 34px rgba(23, 59, 77, 0.05);
          }

          .narrative-card h3 {
            color: var(--navy);
            margin: 0 0 0.7rem;
            font-size: 1.08rem;
          }

          .narrative-card p {
            color: var(--muted);
            line-height: 1.65;
            margin: 0 0 0.7rem;
          }

          .footer-note {
            color: var(--muted);
            line-height: 1.65;
            margin-top: 0.4rem;
          }

          @media (max-width: 960px) {
            .hero-grid {
              grid-template-columns: 1fr;
            }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_info_chip(label: str, value: str) -> str:
    return (
        "<div class='info-chip'>"
        f"<span class='chip-label'>{html.escape(label)}</span>"
        f"<span class='chip-value'>{html.escape(value)}</span>"
        "</div>"
    )


def render_metric_card(label: str, value: str, note: str, tone: str = "default") -> str:
    tone_class = tone if tone in {"success", "warning", "danger"} else ""
    return (
        f"<div class='metric-card {tone_class}'>"
        f"<div class='metric-label'>{html.escape(label)}</div>"
        f"<div class='metric-value'>{html.escape(value)}</div>"
        f"<div class='metric-note'>{html.escape(note)}</div>"
        "</div>"
    )


def render_section_header(kicker: str, title: str, body: str) -> None:
    st.markdown(
        (
            f"<div class='section-kicker'>{html.escape(kicker)}</div>"
            f"<h2 class='section-title'>{html.escape(title)}</h2>"
            f"<p class='section-body'>{html.escape(body)}</p>"
        ),
        unsafe_allow_html=True,
    )


def render_narrative_card(title: str, paragraphs: list[str]) -> None:
    body = "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)
    st.markdown(
        f"<div class='narrative-card'><h3>{html.escape(title)}</h3>{body}</div>",
        unsafe_allow_html=True,
    )


def build_strategy_metric_figure(stage2_strategy: pd.DataFrame, metric_key: str) -> go.Figure:
    spec = STRATEGY_METRICS[metric_key]
    chart_df = stage2_strategy.copy()
    chart_df["PlotLabel"] = chart_df["Strategy"].map(STRATEGY_LABELS).fillna(chart_df["Strategy"])
    chart_df = chart_df.sort_values(metric_key, ascending=not spec["higher_is_better"]).reset_index(drop=True)
    colors = [spec["accent"]] + [spec["muted"]] * (len(chart_df) - 1)

    fig = go.Figure(
        data=go.Bar(
            x=chart_df["PlotLabel"],
            y=chart_df[metric_key],
            marker_color=colors,
            text=[spec["formatter"](float(value)) for value in chart_df[metric_key]],
            textposition="outside",
            cliponaxis=False,
            customdata=np.stack(
                [
                    chart_df["Strategy"],
                    chart_df["FeatureCount"],
                    chart_df["Direction_F1_Macro"],
                    chart_df["Escalate_Recall"],
                ],
                axis=1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b>"
                f"<br>{spec['label']}: %{{text}}"
                "<br>Features: %{customdata[1]:,.0f}"
                "<br>Direction macro-F1: %{customdata[2]:.3f}"
                "<br>Escalate recall: %{customdata[3]:.3f}"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=spec["title"],
        margin=dict(l=20, r=20, t=70, b=44),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color="#173b4d"),
        height=430,
    )
    fig.add_annotation(
        x=1,
        y=1.12,
        xref="paper",
        yref="paper",
        showarrow=False,
        text="Higher is better" if spec["higher_is_better"] else "Lower is better",
        font=dict(color="#5a6d78", size=12),
    )
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(title=spec["subtitle"], gridcolor="#dbe5ea", automargin=True)
    return fig


def prepare_tables(
    stage1: pd.DataFrame,
    stage2_strategy: pd.DataFrame,
    feature_screen: pd.DataFrame,
    hardest_level: pd.Series,
    hardest_direction: pd.Series,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    stage1_table = stage1[
        ["Experiment", "F1_Macro_10Class", "Direction_F1_Macro", "Low_Jumper_Recall", "High_Escalate_Recall"]
    ].copy()
    stage1_table["F1_Macro_10Class"] = stage1_table["F1_Macro_10Class"].map(lambda x: dashboard.fmt_num(float(x)))
    stage1_table["Direction_F1_Macro"] = stage1_table["Direction_F1_Macro"].map(lambda x: dashboard.fmt_num(float(x)))
    stage1_table["Low_Jumper_Recall"] = stage1_table["Low_Jumper_Recall"].map(lambda x: dashboard.fmt_num(float(x)))
    stage1_table["High_Escalate_Recall"] = stage1_table["High_Escalate_Recall"].map(lambda x: dashboard.fmt_num(float(x)))
    stage1_table.columns = ["Policy", "10-class F1", "Direction F1", "Low_Jumper rec.", "High_Esc. rec."]

    strategy_table = stage2_strategy[
        ["Strategy", "FeatureCount", "MAE", "R2_log", "WMAPE", "MAE_vs_Best"]
    ].copy()
    strategy_table["Strategy"] = strategy_table["Strategy"].map(STRATEGY_LABELS).fillna(strategy_table["Strategy"])
    strategy_table["FeatureCount"] = strategy_table["FeatureCount"].map(lambda x: dashboard.fmt_int(int(x)))
    strategy_table["MAE"] = strategy_table["MAE"].map(lambda x: dashboard.fmt_currency(float(x)))
    strategy_table["R2_log"] = strategy_table["R2_log"].map(lambda x: dashboard.fmt_num(float(x)))
    strategy_table["WMAPE"] = strategy_table["WMAPE"].map(lambda x: dashboard.fmt_num(float(x)))
    strategy_table["MAE_vs_Best"] = strategy_table["MAE_vs_Best"].map(lambda x: dashboard.fmt_currency(float(x)))
    strategy_table.columns = ["Strategy", "Features", "MAE", "R2 log", "WMAPE", "Extra MAE"]

    challenge_table = pd.DataFrame(
        [
            {
                "Challenge segment": f"Y1 level {int(hardest_level['Y1_LEVEL'])}",
                "N": dashboard.fmt_int(int(hardest_level["N"])),
                "Mean actual cost": dashboard.fmt_currency(float(hardest_level["Mean_Actual_Cost"])),
                "MAE": dashboard.fmt_currency(float(hardest_level["MAE"])),
                "Interpretation": "High-cost persistence remains hardest to forecast cleanly.",
            },
            {
                "Challenge segment": str(hardest_direction["ActualDirection"]),
                "N": dashboard.fmt_int(int(hardest_direction["N"])),
                "Mean actual cost": dashboard.fmt_currency(float(hardest_direction["Mean_Actual_Cost"])),
                "MAE": dashboard.fmt_currency(float(hardest_direction["MAE"])),
                "Interpretation": "True worsening patients still absorb the largest dollar error.",
            },
        ]
    )

    feature_screen_table = feature_screen[
        ["Feature", "Decision", "Corr_Y2_Cost", "Corr_Delta", "ClinicalRationale"]
    ].copy()
    feature_screen_table["Corr_Y2_Cost"] = feature_screen_table["Corr_Y2_Cost"].map(
        lambda x: dashboard.fmt_num(float(x), 3)
    )
    feature_screen_table["Corr_Delta"] = feature_screen_table["Corr_Delta"].map(
        lambda x: dashboard.fmt_num(float(x), 3)
    )
    feature_screen_table.columns = ["Feature", "Decision", "Cost corr.", "Delta corr.", "Healthcare meaning"]

    return stage1_table, strategy_table, challenge_table, feature_screen_table


def main() -> None:
    inject_styles()
    data = load_dashboard_data()

    analytic = data["analytic"]
    stage1 = data["stage1"]
    stage2_strategy = data["stage2_strategy"]
    direction = data["direction"]
    level_perf = data["level_perf"]
    direction_perf = data["direction_perf"]
    feature_importance = data["feature_importance"]
    feature_screen = data["feature_screen"]
    ablation = data["ablation"]

    total_n = len(analytic)
    train_n = int((analytic["PANEL"] <= 21).sum())
    val_n = int((analytic["PANEL"] == 22).sum())
    test_n = int((analytic["PANEL"] == 23).sum())

    direction_mix = pd.Series(
        np.where(
            analytic["DELTA_BIN"] < 0,
            "Improve",
            np.where(analytic["DELTA_BIN"] == 0, "Stable", "Escalate"),
        )
    ).value_counts()
    direction_mix = direction_mix.reindex(["Improve", "Stable", "Escalate"], fill_value=0)

    best_strategy = stage2_strategy.iloc[0]
    direction_row = direction.iloc[0]
    hardest_level = level_perf.sort_values("MAE", ascending=False).iloc[0]
    hardest_direction = direction_perf.sort_values("MAE", ascending=False).iloc[0]
    best_stage1 = stage1.sort_values("F1_Macro_10Class", ascending=False).iloc[0]

    stage1_table, strategy_table, challenge_table, feature_screen_table = prepare_tables(
        stage1,
        stage2_strategy,
        feature_screen,
        hardest_level,
        hardest_direction,
    )

    metric_options = {spec["label"]: key for key, spec in STRATEGY_METRICS.items()}

    with st.sidebar:
        st.markdown("## Dashboard Controls")
        selected_metric_label = st.selectbox(
            "Stage 2 comparison metric",
            list(metric_options.keys()),
            index=0,
        )
        selected_metric = metric_options[selected_metric_label]
        feature_filter = st.selectbox("Feature screening filter", ["All", "Keep", "Drop"], index=0)
        st.markdown("## Snapshot")
        st.metric("Cost MAE", dashboard.fmt_currency(float(best_strategy["MAE"])))
        st.metric("Direction macro-F1", dashboard.fmt_num(float(direction_row["F1_Macro"])))
        st.metric("Escalate recall", dashboard.fmt_num(float(direction_row["Escalate_Recall"])))
        st.caption("Data sources: reports/tables/*.csv and data/processed_v2/model_ready_stage2.parquet")

    direction_mix_label = (
        f"I {dashboard.fmt_pct(direction_mix['Improve'] / total_n)}  "
        f"S {dashboard.fmt_pct(direction_mix['Stable'] / total_n)}  "
        f"E {dashboard.fmt_pct(direction_mix['Escalate'] / total_n)}"
    )
    hero_html = f"""
    <section class="hero-banner">
      <div class="hero-grid">
        <div>
          <div class="eyebrow">MEPS Panels 18-23</div>
          <h1 class="hero-title">Decision Dashboard for Year 2 Cost and Worsening Risk</h1>
          <p class="hero-body">
            Streamlit version of the MEPS decision dashboard for cost forecasting,
            worsening-direction risk, and operational feature screening. The workflow is
            strongest as a prioritization system rather than a patient-level pricing engine.
          </p>
        </div>
        <div class="chip-stack">
          {render_info_chip("Panels", "18-23")}
          {render_info_chip("Train / Val / Test", f"{dashboard.fmt_int(train_n)} / {dashboard.fmt_int(val_n)} / {dashboard.fmt_int(test_n)}")}
          {render_info_chip("Selected strategy", STRATEGY_LABELS.get(str(best_strategy["Strategy"]), str(best_strategy["Strategy"])))}
          {render_info_chip("Direction mix", direction_mix_label)}
        </div>
      </div>
    </section>
    """
    st.markdown(hero_html, unsafe_allow_html=True)

    hero_metrics = [
        ("Analytic cohort", dashboard.fmt_int(total_n), "Adults across pooled MEPS panels 18-23", "default"),
        (
            "Selected cost strategy",
            STRATEGY_LABELS.get(str(best_strategy["Strategy"]), str(best_strategy["Strategy"])),
            "Lowest held-out dollar error",
            "success",
        ),
        ("Cost MAE", dashboard.fmt_currency(float(best_strategy["MAE"])), "Held-out Year 2 expenditure error", "default"),
        (
            "Direction macro-F1",
            dashboard.fmt_num(float(direction_row["F1_Macro"])),
            "Standalone Improve / Stable / Escalate model",
            "default",
        ),
        (
            "Escalate recall",
            dashboard.fmt_num(float(direction_row["Escalate_Recall"])),
            "Sensitivity for worsening cases",
            "warning",
        ),
        (
            "Hardest segment",
            f"Y1 level {int(hardest_level['Y1_LEVEL'])}",
            f"MAE {dashboard.fmt_currency(float(hardest_level['MAE']))}",
            "danger",
        ),
    ]

    for start in range(0, len(hero_metrics), 3):
        cols = st.columns(3)
        for col, (label, value, note, tone) in zip(cols, hero_metrics[start : start + 3]):
            with col:
                st.markdown(render_metric_card(label, value, note, tone), unsafe_allow_html=True)

    st.divider()
    render_section_header(
        "Executive summary",
        "Use the workflow for prioritization, not hard routing",
        (
            "The current design estimates next-year cost directly, predicts worsening "
            "direction separately, and keeps Stage 1 as a diagnostic layer instead of "
            "a hard gate for downstream model routing."
        ),
    )
    summary_left, summary_right = st.columns([1.35, 0.65], gap="large")
    with summary_left:
        render_narrative_card(
            "What changed in the final operating model",
            [
                (
                    "Stage 1 still adds value for understanding worsening risk, but the "
                    "ten-class routing trade-off remained too unstable for clean expert "
                    "assignment."
                ),
                (
                    "The simplest direct cost strategy delivered the best held-out MAE, "
                    "so extra routing complexity and extra direction signal were not worth it."
                ),
                (
                    "Operationally, the dashboard is best suited to triage, review "
                    "prioritization, and budget sensitivity work."
                ),
            ],
        )
    with summary_right:
        render_narrative_card(
            "Operational recommendation",
            [
                f"Best Stage 1 policy 10-class macro-F1: {dashboard.fmt_num(float(best_stage1['F1_Macro_10Class']))}.",
                f"Best Stage 2 MAE: {dashboard.fmt_currency(float(best_strategy['MAE']))}.",
                (
                    "Keep the direction model alongside the cost model so worsening risk "
                    "stays visible even when spend remains modest."
                ),
            ],
        )

    st.divider()
    render_section_header(
        "Notebook 5.0",
        "Risk landscape",
        (
            "The cohort is dominated by persistence, but the operational challenge is "
            "upward movement from apparently modest starting points."
        ),
    )
    st.plotly_chart(
        dashboard.build_transition_heatmap(analytic),
        use_container_width=True,
        config=PLOTLY_CONFIG,
    )
    st.caption(
        "Decision reading: low- and moderate-cost members do not all remain low risk. "
        "Keep worsening risk visible as a separate planning problem instead of treating it "
        "as a by-product of current spend."
    )

    st.divider()
    render_section_header(
        "Notebook 5.1",
        "Stage 1 is diagnostic, not routing",
        (
            "The scatter below shows the trade-off between overall class balance and "
            "sensitivity to true escalators. Bubble size reflects Low_Jumper recall."
        ),
    )
    stage1_left, stage1_right = st.columns([1.35, 0.95], gap="large")
    with stage1_left:
        st.plotly_chart(
            dashboard.build_stage1_tradeoff(stage1),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    with stage1_right:
        render_narrative_card(
            "How to read Stage 1",
            [
                (
                    "Stage 1 ranked worsening risk and amplified rare-event lift, but it "
                    "did not separate all ten trajectory classes cleanly enough to decide "
                    "which downstream expert should own a patient."
                ),
                (
                    "That is why the final design keeps Stage 1 for explanation and review "
                    "queues instead of using it as the default routing gate."
                ),
            ],
        )
        st.dataframe(stage1_table, use_container_width=True, hide_index=True)
    st.caption(
        f"Best Stage 1 policy reached 10-class macro-F1 "
        f"{dashboard.fmt_num(float(best_stage1['F1_Macro_10Class']))}, "
        "but the rare-event trade-offs remained too unstable for hard routing."
    )

    st.divider()
    render_section_header(
        "Notebook 5.2",
        "Selected operating model",
        (
            "The direct cost model and the standalone direction model remain separate "
            "because they answer different healthcare questions."
        ),
    )
    stage2_left, stage2_right = st.columns([1.3, 0.7], gap="large")
    with stage2_left:
        st.plotly_chart(
            build_strategy_metric_figure(stage2_strategy, selected_metric),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    with stage2_right:
        direction_cards = [
            ("Accuracy", dashboard.fmt_num(float(direction_row["Accuracy"])), "Direction model"),
            ("Improve recall", dashboard.fmt_num(float(direction_row["Improve_Recall"])), "Best captured"),
            ("Stable recall", dashboard.fmt_num(float(direction_row["Stable_Recall"])), "Most ambiguous"),
            ("Escalate recall", dashboard.fmt_num(float(direction_row["Escalate_Recall"])), "Priority worsening"),
        ]
        for start in range(0, len(direction_cards), 2):
            cols = st.columns(2)
            for col, (label, value, note) in zip(cols, direction_cards[start : start + 2]):
                with col:
                    tone = "warning" if label == "Escalate recall" else "default"
                    st.markdown(render_metric_card(label, value, note, tone), unsafe_allow_html=True)
    st.dataframe(strategy_table, use_container_width=True, hide_index=True)
    st.caption(
        "Decision reading: the simplest direct cost strategy retained the best dollar "
        "error. Adding subgroup routing or extra direction signal did not justify the "
        "extra complexity."
    )

    st.divider()
    render_section_header(
        "Residual diagnostics",
        "Where the model still struggles",
        (
            "The remaining miss is concentrated in already expensive members and in "
            "true escalators. Those segments deserve higher-touch review."
        ),
    )
    segments_left, segments_right = st.columns([1.3, 0.7], gap="large")
    with segments_left:
        st.plotly_chart(
            dashboard.build_segment_figure(level_perf, direction_perf),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    with segments_right:
        st.dataframe(challenge_table, use_container_width=True, hide_index=True)

    st.divider()
    render_section_header(
        "Feature logic",
        "Signals that survived screening",
        (
            "The selected model is still anchored by Year 1 spend, but the next strongest "
            "predictors are clinically interpretable and operationally meaningful."
        ),
    )
    feature_cols = st.columns(2, gap="large")
    with feature_cols[0]:
        st.plotly_chart(
            dashboard.build_feature_importance_figure(feature_importance),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )
    with feature_cols[1]:
        st.plotly_chart(
            dashboard.build_ablation_figure(ablation),
            use_container_width=True,
            config=PLOTLY_CONFIG,
        )

    filtered_feature_table = feature_screen_table.copy()
    if feature_filter != "All":
        filtered_feature_table = filtered_feature_table[filtered_feature_table["Decision"] == feature_filter]

    render_narrative_card(
        "Feature screening",
        [
            (
                "The point of screening was not to maximize feature count, but to keep "
                "only signals with distinct clinical meaning."
            ),
            (
                f"Current filter: {feature_filter}. The table below shows the retained "
                "and dropped engineered features with their cost and delta correlations."
            ),
        ],
    )
    st.dataframe(filtered_feature_table, use_container_width=True, hide_index=True)
    st.caption(
        "Decision reading: refill disruption and care-pattern features help explain "
        "deterioration, but they do not justify fragmenting the cost model into many "
        "subgroup-specific paths."
    )

    st.divider()
    render_section_header(
        "Action priorities",
        "What teams can do with this now",
        (
            "These actions follow directly from the notebook evidence and turn the "
            "dashboard into a care-management prioritization tool."
        ),
    )
    for item in ACTION_ITEMS:
        with st.expander(item["title"]):
            st.markdown(f"**Why it matters**: {item['why']}")
            st.markdown(f"**Recommended action**: {item['action']}")
    st.caption(
        "The dashboard is most appropriate for triage, review prioritization, and "
        "budget sensitivity work. It should not be treated as an exact patient-level "
        "pricing engine."
    )


if __name__ == "__main__":
    main()
