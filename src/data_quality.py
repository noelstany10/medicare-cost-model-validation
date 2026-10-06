"""Independent data-quality testing on the staged CMS DE-SynPUF tables.

Each check returns: check id, category, description, observed value, threshold, status.
Status: PASS / WARN / FAIL. Results feed the validation report and Excel workbook.
"""
import sqlite3

import pandas as pd

from . import config as C


def _q(con, sql):
    return con.execute(sql).fetchone()[0]


def run():
    con = sqlite3.connect(C.DB_PATH)
    checks = []

    def add(cid, cat, desc, value, thr, kind="max"):
        if value is None:
            value = 0.0
        if kind == "max":
            status = "PASS" if value <= thr else ("WARN" if value <= thr * 5 else "FAIL")
        elif kind == "min":
            status = "PASS" if value >= thr else ("WARN" if value >= thr * 0.8 else "FAIL")
        else:
            status = "INFO"
        checks.append({"check_id": cid, "category": cat, "description": desc,
                       "observed": round(float(value), 4), "threshold": thr, "rule": kind, "status": status})

    # --- Completeness / uniqueness
    for yr in (2008, 2009, 2010):
        n = _q(con, f"SELECT COUNT(*) FROM stg_bene WHERE FILE_YEAR={yr}")
        add(f"DQ-0{yr-2007}", "Volume", f"Beneficiary records in {yr} summary file", n, 0, "info")
    dup = _q(con, "SELECT COUNT(*) FROM (SELECT DESYNPUF_ID, FILE_YEAR FROM stg_bene GROUP BY 1,2 HAVING COUNT(*)>1)")
    add("DQ-04", "Uniqueness", "Duplicate beneficiary-year keys", dup, 0)
    dup_ip = _q(con, "SELECT COUNT(*) FROM (SELECT CLM_ID, SEGMENT FROM stg_ip GROUP BY 1,2 HAVING COUNT(*)>1)")
    add("DQ-05", "Uniqueness", "Duplicate inpatient claim keys (CLM_ID+SEGMENT)", dup_ip, 0)
    dup_op = _q(con, "SELECT COUNT(*) FROM (SELECT CLM_ID, SEGMENT FROM stg_op GROUP BY 1,2 HAVING COUNT(*)>1)")
    add("DQ-06", "Uniqueness", "Duplicate outpatient claim keys (CLM_ID+SEGMENT)", dup_op, 0)

    # --- Validity
    miss_birth = _q(con, "SELECT AVG(BENE_BIRTH_DT IS NULL OR BENE_BIRTH_DT='') FROM stg_bene")
    add("DQ-07", "Completeness", "Share of beneficiaries missing birth date", miss_birth, 0.0)
    bad_age = _q(con, "SELECT AVG((FILE_YEAR - CAST(substr(BENE_BIRTH_DT,1,4) AS INT)) NOT BETWEEN 18 AND 110) FROM stg_bene")
    add("DQ-08", "Validity", "Share with implausible age (<18 or >110)", bad_age, 0.001)
    neg = _q(con, """SELECT AVG(CAST(MEDREIMB_IP AS REAL)<0 OR CAST(MEDREIMB_OP AS REAL)<0 OR CAST(MEDREIMB_CAR AS REAL)<0)
                     FROM stg_bene""")
    add("DQ-09", "Validity", "Share of bene-years with negative Medicare reimbursement", neg, 0.001)
    neg_clm = _q(con, "SELECT AVG(CAST(CLM_PMT_AMT AS REAL) < 0) FROM stg_ip")
    add("DQ-10", "Validity", "Share of inpatient claims with negative payment", neg_clm, 0.001)
    bad_dt = _q(con, "SELECT AVG(CAST(CLM_THRU_DT AS INT) < CAST(CLM_FROM_DT AS INT)) FROM stg_ip WHERE CLM_FROM_DT<>''")
    add("DQ-11", "Validity", "Share of inpatient claims with through-date before from-date", bad_dt, 0.001)
    miss_from = _q(con, "SELECT AVG(CLM_FROM_DT IS NULL OR CLM_FROM_DT='') FROM stg_op")
    add("DQ-12", "Completeness", "Share of outpatient claims missing service from-date", miss_from, 0.01)
    out_win = _q(con, "SELECT AVG(substr(CLM_FROM_DT,1,4) NOT IN ('2008','2009','2010')) FROM stg_ip WHERE CLM_FROM_DT<>''")
    add("DQ-13", "Validity", "Share of inpatient claims outside 2008-2010 window", out_win, 0.01)
    miss_dx = _q(con, "SELECT AVG(ICD9_DGNS_CD_1 IS NULL OR ICD9_DGNS_CD_1='') FROM stg_op")
    add("DQ-14", "Completeness", "Share of outpatient claims missing principal diagnosis", miss_dx, 0.02)

    # --- Referential integrity / consistency
    orphan = _q(con, """SELECT AVG(b.DESYNPUF_ID IS NULL) FROM (SELECT DISTINCT DESYNPUF_ID FROM stg_ip) c
                        LEFT JOIN (SELECT DISTINCT DESYNPUF_ID FROM stg_bene) b USING(DESYNPUF_ID)""")
    add("DQ-15", "Integrity", "Share of inpatient claimants not found in any beneficiary file", orphan, 0.001)
    post_death = _q(con, """SELECT AVG(CAST(i.CLM_FROM_DT AS INT) > CAST(b.BENE_DEATH_DT AS INT))
                            FROM stg_ip i JOIN stg_bene b ON b.DESYNPUF_ID=i.DESYNPUF_ID
                             AND b.FILE_YEAR = CAST(substr(i.CLM_FROM_DT,1,4) AS INT)
                            WHERE b.BENE_DEATH_DT IS NOT NULL AND b.BENE_DEATH_DT<>''""")
    add("DQ-16", "Consistency", "Share of inpatient claims (decedents) dated after death", post_death, 0.01)
    # Reconciliation: claim-level IP payments vs. summary-file MEDREIMB_IP
    recon = pd.read_sql("""
        WITH c AS (SELECT DESYNPUF_ID, CAST(substr(CLM_FROM_DT,1,4) AS INT) yr, SUM(CAST(CLM_PMT_AMT AS REAL)) amt
                   FROM stg_ip WHERE CLM_FROM_DT<>'' GROUP BY 1,2)
        SELECT b.FILE_YEAR yr, SUM(CAST(b.MEDREIMB_IP AS REAL)) summary_ip, SUM(COALESCE(c.amt,0)) claims_ip
        FROM stg_bene b LEFT JOIN c ON c.DESYNPUF_ID=b.DESYNPUF_ID AND c.yr=b.FILE_YEAR GROUP BY 1""", con)
    recon["ratio_claims_to_summary"] = recon["claims_ip"] / recon["summary_ip"]
    gap = float((recon["ratio_claims_to_summary"] - 1).abs().max())
    add("DQ-17", "Reconciliation", "Max |IP claims total / summary MEDREIMB_IP - 1| across years", gap, 0.05)
    # Completeness / trend: mean Medicare paid per beneficiary by year (a large drop signals claims run-out issues)
    pm = pd.read_sql("""SELECT FILE_YEAR yr, AVG(CAST(MEDREIMB_IP AS REAL)+CAST(MEDREIMB_OP AS REAL)+CAST(MEDREIMB_CAR AS REAL)) mean_paid
                        FROM stg_bene GROUP BY 1 ORDER BY 1""", con)
    pm["yoy_change"] = pm["mean_paid"].pct_change()
    recon = recon.merge(pm, on="yr", how="left")
    add("DQ-18", "Completeness", "Max |year-over-year change| in mean Medicare paid per beneficiary",
        float(pm["yoy_change"].abs().max()), 0.05)
    con.close()
    return pd.DataFrame(checks), recon


if __name__ == "__main__":
    dq, recon = run()
    print(dq.to_string()); print(recon)
