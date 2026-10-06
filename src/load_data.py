"""Load raw CMS DE-SynPUF CSVs into a local SQLite database (staging layer)."""
import sqlite3

import pandas as pd

from . import config as C

IP_COLS = ["DESYNPUF_ID", "CLM_ID", "SEGMENT", "CLM_FROM_DT", "CLM_THRU_DT", "PRVDR_NUM", "CLM_PMT_AMT",
           "NCH_PRMRY_PYR_CLM_PD_AMT", "CLM_ADMSN_DT", "NCH_BENE_DSCHRG_DT", "CLM_UTLZTN_DAY_CNT", "CLM_DRG_CD",
           *[f"ICD9_DGNS_CD_{i}" for i in range(1, 11)]]
OP_COLS = ["DESYNPUF_ID", "CLM_ID", "SEGMENT", "CLM_FROM_DT", "CLM_THRU_DT", "PRVDR_NUM", "CLM_PMT_AMT",
           "NCH_PRMRY_PYR_CLM_PD_AMT", *[f"ICD9_DGNS_CD_{i}" for i in range(1, 11)],
           *[f"HCPCS_CD_{i}" for i in range(1, 6)]]


def _load_csv(con, path, table, usecols=None, extra=None, chunksize=200_000):
    n = 0
    for i, chunk in enumerate(pd.read_csv(path, usecols=usecols, dtype=str, chunksize=chunksize)):
        if extra:
            for k, v in extra.items():
                chunk[k] = v
        chunk.to_sql(table, con, if_exists="append", index=False)
        n += len(chunk)
    return n


def run():
    C.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if C.DB_PATH.exists():
        C.DB_PATH.unlink()
    con = sqlite3.connect(C.DB_PATH)
    counts = {}
    for yr in (2008, 2009, 2010):
        counts[f"bene_{yr}"] = _load_csv(con, C.RAW_DIR / C.FILES[f"bene_{yr}"], "stg_bene", extra={"FILE_YEAR": yr})
    counts["inpatient"] = _load_csv(con, C.RAW_DIR / C.FILES["inpatient"], "stg_ip", usecols=IP_COLS)
    counts["outpatient"] = _load_csv(con, C.RAW_DIR / C.FILES["outpatient"], "stg_op", usecols=OP_COLS)
    con.execute("CREATE INDEX ix_bene ON stg_bene(DESYNPUF_ID, FILE_YEAR)")
    con.execute("CREATE INDEX ix_ip ON stg_ip(DESYNPUF_ID)")
    con.execute("CREATE INDEX ix_op ON stg_op(DESYNPUF_ID)")
    con.commit()
    con.close()
    print("Loaded rows:", counts)
    return counts


if __name__ == "__main__":
    run()
