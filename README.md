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
3.  **Two-Stage Modeling Strategy:**
    *   **Stage 1:** Auxiliary Logistic Model to generate an unbiased `PROB_LATENT_RISK` score (Out-of-Fold prediction).
    *   **Stage 2:** Adjusted Linear Model integrating the Latent Score, achieving **72.3% Recall**, significantly outperforming black-box baselines (XGBoost Recall ~30%).
4.  **Actionable Insights:** Delivered a fully clear, interpretable model where "Latent Risk" serves as a major verified predictor (Coef: 3.67).

---

## 📂 Repository Structure
```
healthcare_repo/
├── data/
│   ├── raw/            # Original MEPS ASCII and Parquet files
│   └── processed/      # Cleaned panel_wide_cleaned.parquet ready for modeling
├── notebooks/          # Core Analysis Logic
│   ├── 1.0_initial_setup.ipynb                  # Environment & Raw Data Check
│   ├── 2.0_feature_engineering_and_data_prep.ipynb  # Deep Dives, Clustering & Feature Creation
│   └── 3.0_risk_modeling_with_latent_factors.ipynb  # Two-Stage Modeling & Validation
├── reports/            # Generated Assets for Reporting
│   ├── figures/        # Professional plots (ROC, Calibration, Clusters)
│   └── tables/         # CSV exports of coefficients and performance metrics
├── src/                # Support Scripts
│   └── data/           # ingest_meps.py (Review this for data download logic)
├── methodology_interactive.html # Interactive Guide to the Data Feature Pyramid Methodology
├── requirements.txt    # Python dependencies
└── README.md           # Project Documentation
```

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
*   **Sensitivity Win:** The Latent-Adjusted Model captures **72%** of future high-cost patients, compared to only **30%** by standard XGBoost.
*   **Strong Signal:** The engineered `PROB_LATENT_RISK` feature has a coefficient of **3.67**, making it the strongest single predictor of future risk after controlling for age and disease history.

##  Future Directions
*   **Ensemble Stacking:** Combining the precision of XGBoost with the high recall of the Linear Model.
*   **Time-Series Deep Learning:** Utilizing LSTM/RNNs on granular medication purchase sequences (using raw MEPS event files) to model trajectory dynamics.

---
**Author:** Group 5 Capstone Team
**License:** MIT
