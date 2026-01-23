# MEPS Healthcare Cost & Latent Risk Predictive System

## 📌 Project Overview
**Title:** Identifying Latent High-Cost Risk: A Two-Stage Modeling Approach

**Data Source:** Medical Expenditure Panel Survey (MEPS) Longitudinal Data [Panels 18-23, Years 2013-2019]

### 🎯 Objective
This project moves beyond standard actuarial models by identifying "Hidden Risers"—patients with historically low spending who experience a sudden, severe escalation in care needs. We implement a **Two-Stage Latent Risk Model** that leverages auxiliary behavioral signals to enhance the prediction of future high-cost events.

**Key Achievements:**
1.  **Data Pipeline:** Integrated 6 years of MEPS longitudinal data, adjusted for inflation (2025 CPI), and harmonized complex medical coding features.
2.  **Advanced Feature Engineering:**
    *   **"Care Phenotypes":** K-Means clustering identified 4 distinct utilization styles (e.g., "Crisis Management" vs. "Routine Care").
    *   **Behavioral Ratios:** Operationalized precursors like `RATIO_ER_OFFICE` and `UTIL_RX` intensity.
3.  **Two-Stage Modeling Strategy:** Adopting an **Imbalance-Aware** framework, we prioritized **PR-AUC (Precision-Recall)** over misleading calibration metrics like Accuracy.
    *   **Stage 1:** Auxiliary Logistic Model to generate an unbiased `PROB_LATENT_RISK` score (Out-of-Fold prediction).
    *   **Stage 2:** Adjusted Linear Model integrating the Latent Score, successfully demonstrating lift in identifying rare "Hidden Riser" events compared to standard "Black Box" approaches.
4.  **Actionable Insights:** Delivered a fully clear, interpretable model where "Latent Risk" serves as a major verified predictor.

---

## 📂 Repository Structure
```
healthcare_repo/
├── data/
│   ├── raw/            # Original MEPS ASCII and Parquet files
│   └── processed/      # Cleaned panel_wide_cleaned.parquet ready for modeling
├── notebooks/          # Core Analysis Logic
│   ├── 2.0_feature_engineering_and_data_prep.ipynb  # Deep Dives, Clustering & Feature Creation
│   └── 3.0_risk_modeling_with_latent_factors.ipynb  # Two-Stage Modeling & Validation (PR-AUC Focus)
├── reports/            # Generated Assets for Reporting
│   ├── figures/        # Professional plots (PR Curves, Calibration, Clusters)
│   ├── tables/         # CSV exports of coefficients and performance metrics
│   ├── methodology_interactive.html # Interactive Guide to the Data Feature Pyramid Methodology
│   └── full_project_report.html     # 📄 Complete Project Export (Auto-generated)
├── src/                # Support Scripts
│   ├── data/           # ingest_meps.py (Review this for data download logic)
│   └── export_repo_to_html.py # Script to compile entire repo into single HTML
├── requirements.txt    # Python dependencies
└── README.md           # Project Documentation
```

> **Project Management Note:** The entire repository status, including code execution results and documentation, can be auto-compiled into a single view using `python src/export_repo_to_html.py`.

##  Quick Start

### 1. Environment Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the Analysis
The project logic is encapsulated in sequential Jupyter Notebooks:

1.  **Feature Engineering (`notebooks/2.0_...`)**:
    *   Loads raw panels.
    *   Performs "Deep Dive" comparisons (Jumpers vs. Stable).
    *   Runs K-Means Clustering for Care Phenotypes.
    *   Saves `panel_wide_cleaned.parquet` and exploratory plots.

2.  **Risk Modeling (`notebooks/3.0_...`)**:
    *   Loads cleaned data.
    *   Trains Auxiliary Model for `LATENT_EVENT`.
    *   Computes Out-of-Fold `PROB_LATENT_RISK` scores.
    *   Trains and compares Baseline, Adjusted, and XGBoost models.
    *   Exports final performance metrics and ROC curves.

##  Key Results
*   **Imbalance Management:** Shifted evaluation framework from specific Accuracy/ROC (which are biased by the 85% healthy population) to **Precision-Recall (PR) Curves**.
*   **Methodology Validation:** The **Latent-Adjusted Model** demonstrates superior stability and interpretability in identifying "Hidden Risers." By explicitly modeling the "Propensity for Risk" (Stage 1), we achieve a model that balances sensitivity with clinical precision better than unadjusted baselines.
*   **Strong Signal:** The engineered `PROB_LATENT_RISK` feature consistently appears as a top-ranked coefficient, validating the hypothesis that "Risk" is a latent variable composed of multimorbidity and behavioral patterns.

## 🧠 Methodological Discussion

### 1. The Accuracy Paradox & Precision-Recall
In healthcare cost prediction, "High Risk" patients often comprise <10-15% of the population. A standard model predicting "Everyone is Healthy" achieves ~90% accuracy but has **zero clinical value**.
*   **Our Approach:** We explicitly reject Accuracy and ROC-AUC (which can be inflated by True Negatives).
*   **Success Metric:** We optimize for **PR-AUC (Precision-Recall)**. A PR-AUC score significantly above the baseline prevalence (e.g., 0.35 vs 0.15) represents a massive **Lift in Efficiency**—meaning interventions guided by this model are >2x more effective than random screening.

### 2. The "Sensitivity vs. Precision" Trade-off
We adopt a **Recall-First (Cost-Sensitive)** strategy.
*   **Business Logic:** The cost of *missing* a high-risk patient (False Negative → Unmanaged Catastrophic Event) far exceeds the cost of a preventative intervention for a stable patient (False Positive).
*   **Literature Context:** Following **Obermeyer et al. (Science, 2019)**, we recognize that "False Positives" in our model often represent **"Vulnerable but Lucky"** patients—those with high latent risk who simply did not manifest an acute event due to stochasticity. Identifying these patients is a feature, not a bug, of preventive analytics.

##  Future Directions
*   **Ensemble Stacking:** Combining the precision of XGBoost with the high recall of the Linear Model.
*   **Time-Series Deep Learning:** Utilizing LSTM/RNNs on granular medication purchase sequences (using raw MEPS event files) to model trajectory dynamics.

---

