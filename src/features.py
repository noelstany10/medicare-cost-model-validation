"""Run the SQL feature-engineering layer and return the modelling dataset."""
import sqlite3

import numpy as np
import pandas as pd

from . import config as C

SQL_FILES = ["01_member_year.sql", "02_claims_features.sql", "03_model_dataset.sql"]


def build():
    con = sqlite3.connect(C.DB_PATH)
    for f in SQL_FILES:
        con.executescript((C.SQL_DIR / f).read_text())
        print(f"  ran {f}")
    con.commit()
    df = pd.read_sql("SELECT * FROM model_dataset", con)
    waterfall = pd.read_sql("SELECT * FROM population_waterfall ORDER BY feature_year, step", con)
    member_year = pd.read_sql("SELECT * FROM member_year", con)
    con.close()
    df["log_paid_total"] = np.log1p(df["paid_total"])
    for c in C.NUMERIC_FEATURES:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(float)
    return df, waterfall, member_year
