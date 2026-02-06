# MEPS Healthcare Cost Prediction: Multi-Stage Risk Modeling

## Project Overview

**Objective:** Predict Year 2 healthcare expenditure using Year 1 features, with a focus on identifying "Hidden Risers" — patients with low initial costs who experience sudden cost escalations.

**Data Source:** Medical Expenditure Panel Survey (MEPS) Panels 18-23 (2013-2019)

**Methodology:** Multi-Stage Supervised Learning with clinically interpretable latent risk factors

---

## Key Results Summary

| Metric | Best Model (XGBoost) | Interpretation |
|--------|---------------------|----------------|
| Macro F1 | 0.45 | Balanced performance across risk tiers |
| Weighted F1 | 0.70 | Strong overall prediction accuracy |
| ROC-AUC (OvR) | 0.78 | Good discrimination between risk classes |
| Shock Recall | ~35% | Captures 1/3 of high-cost patients |

**Top Predictive Features:**
1. `COST_Y1_ADJ` — Year 1 total expenditure (strongest signal)
2. `POLYPHARMACY_FLAG` — 5+ medications (high-risk indicator)
3. `CNT_TOTAL_CONDITIONS` — Medical complexity
4. `HAS_CNS_RX` — CNS medication use (mental health proxy)

---

## Repository Structure

```
healthcare_repo/
├── notebooks/                    # Main Analysis Pipeline
│   ├── 5.0_data_processing_v2_corrected.ipynb   # Data processing & feature engineering
│   ├── 5.1_modeling_stage1.ipynb                # Stage 1: Risk tier classification
│   └── 5.2_stage1_5_and_stage2_modeling.ipynb   # Stage 1.5 & Stage 2: Final models
├── data/
│   ├── external/                 # Reference documents & literature
│   └── processed_v2/             # Model-ready datasets (regenerated from raw)
├── reports/
│   ├── figures/                  # Generated visualizations
│   ├── tables/                   # Performance metrics & cluster profiles
│   └── multistage_architecture.html  # Interactive architecture diagram
├── src/
│   └── data/
│       └── parse_all_meps.py     # MEPS data parser (ASCII & SSP formats)
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## Workflow & Conclusions

### Stage 0: Data Processing (`5.0_data_processing_v2_corrected.ipynb`)

**Input:** Raw MEPS Longitudinal, Conditions, and Prescribed Medicines files

**Process:**
1. Load and merge 6 panels (2013-2019) with dynamic column mapping
2. Apply cohort filters (Age ≥ 18, exclude Year 1 cancer)
3. Engineer 40+ features including:
   - Inflation-adjusted costs (2025 baseline)
   - Chronic disease flags (diabetes, hypertension, cholesterol)
   - Medication patterns (polypharmacy, drug class indicators)
   - "Undiagnosed signals" (ill-defined condition codes)
4. Create target variables: `RISK_TIER` (Stable/Rising/Shock)
5. Cluster patients into "Care Phenotypes" (K-Means & DBSCAN)

**Conclusions:**
- **60,602 patients** retained after filtering
- **36% have polypharmacy** (≥5 unique medications) — a key risk signal
- **"Hidden Risers" (Jumpers)** show 3.4x higher diabetes prevalence vs stable patients
- **K=5 clusters** identified via Elbow method with silhouette validation

---

### Stage 1: Risk Tier Classification (`5.1_modeling_stage1.ipynb`)

**Task:** Multi-class prediction of `RISK_TIER` (0=Stable, 1=Rising, 2=Shock)

**Models Benchmarked:**
| Model | Macro F1 | Weighted F1 | ROC-AUC |
|-------|----------|-------------|---------|
| Logistic Regression | 0.38 | 0.65 | 0.72 |
| Random Forest | 0.43 | 0.68 | 0.76 |
| **XGBoost** | **0.45** | **0.70** | **0.78** |
| GradientBoosting | 0.44 | 0.69 | 0.77 |

**Conclusions:**
- **XGBoost selected** as best model (highest across all metrics)
- **Imbalanced classes** (Stable: 75%, Rising: 15%, Shock: 10%) addressed via class weights
- **SHAP analysis** shows Year 1 cost and medication complexity drive predictions
- **Latent risk scores** generated for Stage 2/3 use

---

### Stage 1.5: Intermediate Latent Factors (`5.2_stage1_5_and_stage2_modeling.ipynb`)

**Task:** Create clinically meaningful intermediate predictors that capture hidden risk dynamics

| Model | Output Variable | Clinical Meaning |
|-------|-----------------|------------------|
| **1.5A: Mental Health Trajectory** | `PROB_MH_DECLINE` | Probability of mental health deterioration |
| **1.5B: Healthcare Engagement** | `ENGAGEMENT_SCORE` | Proactive vs. crisis-driven care pattern |
| **1.5C: Undiagnosed Condition Risk** | `PROB_UNDIAGNOSED` | Risk of hidden condition ("Jumper" probability) |
| **1.5D: Cost Escalation Score** | `ESCALATION_SCORE` | Composite clinical risk indicator |

**Conclusions:**
- **Mental health decline** correlates strongly with future cost escalation
- **Crisis-mode patients** (high ER-to-office ratio) have 2.5x higher average Y2 costs
- **"Jumper" prediction** identifies patients appearing healthy but at risk of major events

---

### Stage 2: Final Expenditure Prediction (`5.2_stage1_5_and_stage2_modeling.ipynb`)

**Task:** Predict Year 2 healthcare expenditure using Tweedie Regression

**Model:** `TweedieRegressor` with log link and power parameter ∈ (1, 2)

**Why Tweedie?**
- Handles **zero-inflation** (many patients have very low costs)
- Handles **right-skewness** (few patients have extremely high costs)
- Single model replaces traditional two-part (hurdle) approaches

**Feature Set:**
| Type | Count | Examples |
|------|-------|----------|
| Original Features | 21 | `AGE_Y1`, `CHRONIC_COUNT`, `COST_Y1_ADJ` |
| Stage 1 Latent | 4 | `PROB_STABLE`, `PROB_RISING`, `PROB_SHOCK`, `LATENT_RISK_SCORE` |
| Stage 1.5 Latent | 5 | `PROB_MH_DECLINE`, `ENGAGEMENT_SCORE`, `PROB_UNDIAGNOSED`, `ESCALATION_SCORE` |
| **Total** | **30** | Combined feature matrix |

**Data Split:** Stratified by Panel (70% train / 20% validation / 10% test)

**Conclusions:**
- Adding latent factors improved MAE by ~8% over baseline
- Tweedie regression effectively handled the zero-inflated distribution
- Interpretable intermediate variables provide actionable clinical insights

---

## Quick Start

```bash
# 1. Setup environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run data processing (Stage 0)
jupyter notebook notebooks/5.0_data_processing_v2_corrected.ipynb

# 3. Run risk tier modeling (Stage 1)
jupyter notebook notebooks/5.1_modeling_stage1.ipynb

# 4. Run intermediate factors & final model (Stage 1.5 + Stage 2)
jupyter notebook notebooks/5.2_stage1_5_and_stage2_modeling.ipynb

# 5. Export to HTML (optional)
python src/export_repo_to_html.py
```

---

## Data Sources

**MEPS Files Used:**
| Type | File IDs | Description |
|------|----------|-------------|
| Longitudinal | h172, h183, h193, h202, h210, h217 | Panel Y1→Y2 tracking |
| Conditions | h162, h170, h180, h190, h199, h207 | Medical diagnoses |
| Prescribed Medicines | h160a, h168a, h178a, h188a, h197a, h206a | Medication records |

**Download:** https://meps.ahrq.gov/mepsweb/data_stats/download_data_files.jsp

---

## References

1. Obermeyer et al. (2019). "Dissecting racial bias in an algorithm used to manage the health of populations." *Science*.
2. Faraji et al. (2024). "Using double-hurdle model to understand predictors of health care expenditures." *Cost Effectiveness and Resource Allocation*. DOI: 10.1186/s12962-024-00521-8
3. Zhu et al. (2022). "An interpretable stacking ensemble learning framework for healthcare expenditure prediction." *Frontiers in Pharmacology*. DOI: 10.3389/fphar.2022.975855
4. Jørgensen, B. (1987). "Exponential dispersion models." *JRSS Series B*.
5. MEPS documentation: https://meps.ahrq.gov/mepsweb/data_stats/data_documentation.jsp
6. Multum Lexicon drug classification: https://www.cerner.com/solutions/drug-database

---

*Last updated: January 2026*
