# MEPS Healthcare Cost & Opioid Risk Predictive System

## 📌 Project Overview
**Title:** The Hidden Cost of Minds: Predicting 'Financial Toxicity' in Mental Health & Opioid Comorbidities
**Scope:** Senior Data Science Capstone / XN Project for ALY6980
**Data Source:** Medical Expenditure Panel Survey (MEPS) Longitudinal Data [2001-2023]

### 🎯 Objective
This project aims to uncover the hidden financial multiplier effect of mental health comorbidities and opioid usage on general healthcare expenditure.
By utilizing **Fixed-Width ASCII Micro-data**, this project simulates a legacy system migration environment common in Banking and Insurance sectors.

**Key Deliverables:**
1.  **Automated ETL Pipeline:** Parsing legacy ASCII data into modern Parquet/SQL formats.
2.  **Risk Stratification Model:** Predicting High-Cost Claimants (Top 10% spenders).
3.  **Explainable AI (XAI):** SHAP analysis of mental health impact on physical injury recovery costs.
4.  **Interactive Dashboard:** Streamlit/Dash app for Case Manager decision support.

---

## 📂 Repository Structure
```
heathcare_repo/
├── data/
│   ├── raw/            # Original MEPS ASCII (.dat) and Codebooks (.txt)
│   ├── processed/      # Cleaned Parquet/CSV files ready for modeling
│   └── external/       # Documentation and PDF reports
├── notebooks/          # Jupyter Notebooks for EDA and prototyping
├── src/                # Source code (The "Product")
│   ├── data/           # ETL Scripts (Ingestion & ASCII Parsing)
│   ├── features/       # Feature Engineering logic
│   ├── models/         # Training and Inference scripts
│   └── visualization/  # Dashboard code
├── requirements.txt    # Python dependencies
└── README.md           # Project Documentation
```

## 🚀 Quick Start

### 1. Environment Setup
```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### 2. Data Ingestion
This project uses a custom scraping pipeline to fetch ASCII data from the AHRQ MEPS website.
```bash
# Run the ingestion script (Requires internet connection)
python src/data/ingest_meps.py
```

### 3. Parsing Legacy ASCII Files
Convert the raw `.dat` files into usable Pandas DataFrames.
```bash
python src/data/parse_ascii.py
```

---

## 🏗 Modeling Strategy
*   **Target:** `Total_Expenditure` (Regression) & `High_Cost_Flag` (Classification)
*   **Exclusion Criteria:** Patients with Cancer diagnosis codes (per project requirement).
*   **Key Features:** Charlson Comorbidity Index, Opioid Prescription Count, ER Utilization History.
