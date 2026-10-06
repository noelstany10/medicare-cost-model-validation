# Medicare Prospective Cost Model & Independent Model Validation

[![Model validation pipeline](https://github.com/noelstany10/medicare-cost-model-validation/actions/workflows/pipeline.yml/badge.svg)](https://github.com/noelstany10/medicare-cost-model-validation/actions/workflows/pipeline.yml)

**Live dashboard:** https://noelstany10.github.io/medicare-cost-model-validation/ ·
**Validation report:** [`reports/Model_Validation_Report.md`](reports/Model_Validation_Report.md) ·
**Excel workbook:** [`excel/Model_Validation_Workbook.xlsx`](excel/Model_Validation_Workbook.xlsx)

This project builds a healthcare cost forecasting model and independently validates it, following the model risk management practice used by US health insurers and consultancies (SR 11-7 style: conceptual soundness, outcome analysis, ongoing monitoring).

* **Business question:** what will each Medicare beneficiary cost next year, and who is likely to become a high-cost claimant?
* **Data:** [CMS 2008–2010 Data Entrepreneurs' Synthetic Public Use File (DE-SynPUF), Sample 1](https://www.cms.gov/data-research/statistics-trends-and-reports/medicare-claims-synthetic-public-use-files/cms-2008-2010-data-entrepreneurs-synthetic-public-use-file-de-synpuf/de10-sample-1). It contains Medicare beneficiary summary files plus inpatient and outpatient claims for roughly 116,000 synthetic beneficiaries.
* **Stack:** SQL (SQLite) · Python (pandas, scikit-learn, SciPy, matplotlib) · Excel (formulas, conditional formatting, charts, Excel Tables) · GitHub Actions CI · GitHub Pages dashboard.

<!-- RESULTS:START -->
*Results appear here after the GitHub Actions pipeline runs on the CMS data.*
<!-- RESULTS:END -->

## What the project does

```
CMS DE-SynPUF CSVs ──► SQLite staging ──► SQL feature layer ──► model dataset (beneficiary-year)
                                           │  member_year, ip_util, 30-day readmits,
                                           │  ED visits, ICD-9 condition categories
                                           ▼
             Development: 2008 features → 2009 cost (70/30 split)    Out-of-time: 2009 features → 2010 cost
                                           │
              ┌────────────────────────────┴────────────────────────────┐
              ▼                                                         ▼
   MODEL DEVELOPMENT (1st line)                         INDEPENDENT VALIDATION (2nd line)
   M0 Trended persistence (benchmark)                   • 17 data-quality tests incl. claim↔summary reconciliation
   M1 Credibility-weighted demographic manual rate      • Leakage & conceptual-soundness review
   M2 Tweedie GLM (log link, p = 1.5)                   • Benchmarking vs actuarial & GLM challengers
   M3 Poisson gradient boosting  ◄ champion             • R², Cumming's Prediction Measure, predictive ratios, Gini
   C1 Logistic regression / C2 GBM classifier           • Decile backtests (in-time & out-of-time), bootstrap CIs
      for high-cost claimants (top 10%)                 • AUC, KS, lift, Brier, Hosmer-Lemeshow
                                                        • PSI / CSI stability · sensitivity shocks · seed,
                                                          hyper-parameter and feature-ablation re-fits
                                                        • Permutation importance, partial dependence
                                                        • Segment calibration & race/sex disparity testing
                                                        • Severity-rated findings, overall rating, monitoring plan
              │                                                         │
              └──────────► Markdown report · Excel workbook · HTML dashboard ◄──┘
```

## Repository layout

| Path | Contents |
|---|---|
| `sql/01_member_year.sql` | Beneficiary-year table: demographics, coverage months, 11 chronic-condition flags, cost by setting |
| `sql/02_claims_features.sql` | Inpatient stays, 30-day readmissions (window function), outpatient/ED visits, ICD-9 unpivot and condition categories |
| `sql/03_model_dataset.sql` | Prospective t → t+1 dataset with an auditable population waterfall |
| `src/models.py` | Benchmarks, Tweedie GLM, gradient boosting cost model and high-cost classifiers |
| `src/validation.py` | Validation toolkit: metrics, backtests, PSI/CSI, sensitivity, fairness, rule-based findings |
| `src/data_quality.py` | Data-quality and reconciliation tests |
| `src/report.py`, `src/excel_workbook.py`, `src/dashboard.py` | Report, Excel workbook and dashboard generators |
| `tests/` | Unit tests for the metrics, plus a schema-identical sample generator used for the CI smoke test |
| `.github/workflows/pipeline.yml` | CI: tests → download CMS data → full run → commit results |

## Excel workbook

`excel/Model_Validation_Workbook.xlsx` is built so a reviewer can audit every number in Excel:

* **Decile_Backtest:** `SUMIFS`/`COUNTIFS` over the scored members, with predictive ratios, a cumulative cost-capture curve and a chart.
* **PSI_Stability:** PSI calculated cell by cell as `(A% − E%) × LN(A% / E%)`, with a traffic-light assessment.
* **Segment_Calibration:** editable tolerance inputs drive `BREACH`/`OK` formulas.
* **Pivot_Analysis:** an age × sex predictive-ratio cross-tab with a risk-decile filter dropdown.
* **Scored_Members:** the out-of-time member-level scores as an Excel Table (`tblScored`), ready for PivotTables.
* **Findings:** a remediation tracker with a status dropdown.

## Run it yourself

```bash
pip install -r requirements.txt
bash scripts/download_synpuf.sh        # downloads ~80 MB of zips from CMS into data/raw
python run_pipeline.py                 # about 5–10 minutes
# no CMS access? a quick test on a generated sample with the same schema:
python run_pipeline.py --synthetic
```

## Limitations

DE-SynPUF is synthetic. CMS perturbed and imputed the values to protect privacy, which weakens real clinical-cost relationships. Expect lower R² than production risk models (for example CMS-HCC prospective R² of about 0.12 on real claims). The project's focus is the modelling and validation methodology, not the absolute accuracy.
