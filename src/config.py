"""Central configuration for the Medicare cost model & validation pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DB_PATH = ROOT / "data" / "synpuf.sqlite"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
REPORT_DIR = ROOT / "reports"
FIG_DIR = REPORT_DIR / "figures"
DOCS_DIR = ROOT / "docs"
EXCEL_DIR = ROOT / "excel"

SEED = 2024

FILES = {
    "bene_2008": "DE1_0_2008_Beneficiary_Summary_File_Sample_1.csv",
    "bene_2009": "DE1_0_2009_Beneficiary_Summary_File_Sample_1.csv",
    "bene_2010": "DE1_0_2010_Beneficiary_Summary_File_Sample_1.csv",
    "inpatient": "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv",
    "outpatient": "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv",
}

# Development window: features 2008 -> target 2009 (70/30 random in-time split)
# Out-of-time (OOT) backtest: features 2009 -> target 2010
DEV_FEATURE_YEAR = 2008
OOT_FEATURE_YEAR = 2009
TEST_SIZE = 0.30

# High-cost claimant (HCC) definition: top X% of next-year paid cost in the dev year
HIGH_COST_QUANTILE = 0.90

CHRONIC_FLAGS = ["SP_ALZHDMTA", "SP_CHF", "SP_CHRNKIDN", "SP_CNCR", "SP_COPD", "SP_DEPRESSN",
                 "SP_DIABETES", "SP_ISCHMCHT", "SP_OSTEOPRS", "SP_RA_OA", "SP_STRKETIA"]

# Model features. Race is intentionally EXCLUDED from the model and used only
# for fairness / disparity testing in validation.
NUMERIC_FEATURES = [
    "age", "is_female", "esrd", "part_a_mos", "part_b_mos", "hmo_mos", "part_d_mos",
    *[c.lower() for c in CHRONIC_FLAGS], "n_chronic",
    "paid_ip", "paid_op", "paid_car", "paid_total", "benres_total", "log_paid_total",
    "ip_admits", "ip_days", "ip_readmit_30d", "op_visits", "er_visits", "n_providers", "n_distinct_dx",
    "dx_diabetes", "dx_chf", "dx_copd", "dx_ckd", "dx_esrd", "dx_cancer", "dx_ami_ihd", "dx_stroke",
    "dx_dementia", "dx_depression", "dx_hypertension", "dx_afib",
]
CATEGORICAL_FEATURES = []  # state kept out of the champion to avoid geography proxies; see validation report

TARGET_COST = "target_paid"
TARGET_HCC = "target_high_cost"
