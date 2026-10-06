"""
Generate a SMALL, schema-identical stand-in for CMS DE-SynPUF Sample 1.

Purpose: unit/integration testing of the pipeline (and offline development)
without downloading ~1 GB of CMS files. The column names, codes and file names
match the official DE-SynPUF layout (CMS DE-SynPUF Data Users Guide), so the
exact same SQL + Python runs on both.

NOTE: results in reports/ are produced by the GitHub Actions workflow on the
REAL CMS DE-SynPUF Sample 1 data, not on this generator's output.

Usage:  python tests/make_synthetic_sample.py --n 20000 --out data/raw
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

CC = ["SP_ALZHDMTA", "SP_CHF", "SP_CHRNKIDN", "SP_CNCR", "SP_COPD", "SP_DEPRESSN",
      "SP_DIABETES", "SP_ISCHMCHT", "SP_OSTEOPRS", "SP_RA_OA", "SP_STRKETIA"]
CC_PREV = [0.20, 0.28, 0.17, 0.07, 0.14, 0.21, 0.38, 0.43, 0.17, 0.15, 0.04]
CC_DX = {"SP_ALZHDMTA": ["3310", "2900"], "SP_CHF": ["4280", "4281"], "SP_CHRNKIDN": ["5853", "5859"],
         "SP_CNCR": ["1749", "1629", "185"], "SP_COPD": ["496", "4912"], "SP_DEPRESSN": ["311", "29620"],
         "SP_DIABETES": ["25000", "25002"], "SP_ISCHMCHT": ["41401", "4148"], "SP_OSTEOPRS": ["73300"],
         "SP_RA_OA": ["7140", "7151"], "SP_STRKETIA": ["43491", "4359"]}
FILLER_DX = ["4019", "2724", "V5869", "78650", "7295", "53081", "2449", "V5861", "4011", "42731"]


def bene_year(rng, base, year, cc_state, cost_state):
    n = len(base["id"])
    df = pd.DataFrame({"DESYNPUF_ID": base["id"]})
    df["BENE_BIRTH_DT"] = base["birth"]
    death = np.where(base["death_year"] == year, year * 10000 + rng.integers(1, 13, n) * 100 + 15, np.nan)
    df["BENE_DEATH_DT"] = pd.array(np.where(np.isnan(death), pd.NA, death), dtype="Int64")
    df["BENE_SEX_IDENT_CD"] = base["sex"]
    df["BENE_RACE_CD"] = base["race"]
    df["BENE_ESRD_IND"] = np.where(base["esrd"], "Y", "0")
    df["SP_STATE_CODE"] = base["state"]
    df["BENE_COUNTY_CD"] = rng.integers(1, 999, n)
    mons = np.where(rng.random(n) < 0.9, 12, rng.integers(1, 12, n))
    df["BENE_HI_CVRAGE_TOT_MONS"] = mons
    df["BENE_SMI_CVRAGE_TOT_MONS"] = np.minimum(mons, np.where(rng.random(n) < 0.92, 12, rng.integers(0, 12, n)))
    df["BENE_HMO_CVRAGE_TOT_MONS"] = np.where(rng.random(n) < 0.15, rng.integers(1, 13, n), 0)
    df["PLAN_CVRG_MOS_NUM"] = np.where(rng.random(n) < 0.6, 12, 0)
    for j, c in enumerate(CC):
        df[c] = np.where(cc_state[:, j], 1, 2)
    ncc = cc_state.sum(1)
    age = year - base["birth"] // 10000
    mu = np.exp(5.6 + 0.33 * ncc + 0.012 * (age - 70) + 1.1 * base["esrd"] + 0.45 * cost_state)
    has_ip = rng.random(n) < 1 / (1 + np.exp(-(-3.4 + 0.42 * ncc + 0.9 * base["esrd"] + 0.3 * cost_state)))
    ip = np.where(has_ip, np.round(rng.gamma(1.5, 7000 * (1 + 0.15 * ncc)) / 10) * 10, 0)
    op = np.where(rng.random(n) < 0.75, np.round(rng.gamma(0.9, mu * 0.6) / 10) * 10, 0)
    car = np.where(rng.random(n) < 0.85, np.round(rng.gamma(1.1, mu * 0.9) / 10) * 10, 0)
    df["MEDREIMB_IP"], df["BENRES_IP"], df["PPPYMT_IP"] = ip, np.where(ip > 0, 1068, 0), np.where(rng.random(n) < 0.03, ip * 0.1, 0)
    df["MEDREIMB_OP"], df["BENRES_OP"], df["PPPYMT_OP"] = op, np.round(op * 0.25), 0
    df["MEDREIMB_CAR"], df["BENRES_CAR"], df["PPPYMT_CAR"] = car, np.round(car * 0.27), 0
    return df, has_ip, ip, op


def claims(rng, ids, year, cc_state, n_claims, amounts, kind):
    rows = []
    for i in np.where(n_claims > 0)[0]:
        k = int(n_claims[i])
        split = rng.dirichlet(np.ones(k)) * amounts[i] if amounts[i] > 0 else np.zeros(k)
        conds = [c for j, c in enumerate(CC) if cc_state[i, j]]
        for s in range(k):
            m = int(rng.integers(1, 13)); d = int(rng.integers(1, 25))
            frm = year * 10000 + m * 100 + d
            los = int(rng.integers(1, 9)) if kind == "IP" else 0
            thru = frm + los
            dx = [rng.choice(CC_DX[c]) for c in conds][:4] + list(rng.choice(FILLER_DX, 6))
            r = {"DESYNPUF_ID": ids[i], "CLM_ID": f"{kind}{year}{i:07d}{s:02d}", "SEGMENT": 1,
                 "CLM_FROM_DT": frm, "CLM_THRU_DT": thru, "PRVDR_NUM": f"{rng.integers(10000, 99999)}",
                 "CLM_PMT_AMT": round(float(split[s]), -1), "NCH_PRMRY_PYR_CLM_PD_AMT": 0,
                 "AT_PHYSN_NPI": rng.integers(1e9, 9e9), "OP_PHYSN_NPI": pd.NA, "OT_PHYSN_NPI": pd.NA}
            if kind == "IP":
                r.update({"CLM_ADMSN_DT": frm, "ADMTNG_ICD9_DGNS_CD": dx[0], "CLM_PASS_THRU_PER_DIEM_AMT": 0,
                          "NCH_BENE_IP_DDCTBL_AMT": 1068, "NCH_BENE_PTA_COINSRNC_LBLTY_AM": 0,
                          "NCH_BENE_BLOOD_DDCTBL_LBLTY_AM": 0, "CLM_UTLZTN_DAY_CNT": los,
                          "NCH_BENE_DSCHRG_DT": thru, "CLM_DRG_CD": f"{rng.integers(1, 999):03d}"})
            else:
                r.update({"NCH_BENE_BLOOD_DDCTBL_LBLTY_AM": 0})
            for j in range(10):
                r[f"ICD9_DGNS_CD_{j+1}"] = dx[j] if j < len(dx) else pd.NA
            for j in range(6):
                r[f"ICD9_PRCDR_CD_{j+1}"] = pd.NA
            if kind == "OP":
                r.update({"NCH_BENE_PTB_DDCTBL_AMT": 0, "NCH_BENE_PTB_COINSRNC_AMT": 0, "ADMTNG_ICD9_DGNS_CD": pd.NA})
            er = kind == "OP" and rng.random() < 0.08
            for j in range(45):
                r[f"HCPCS_CD_{j+1}"] = ("99284" if er else "99213") if j == 0 else pd.NA
            rows.append(r)
    return rows


def main(n, out, seed=42):
    rng = np.random.default_rng(seed)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    ids = np.array([f"{x:016X}" for x in rng.integers(0, 2**62, n)])
    by = rng.integers(1910, 1944, n)
    base = {"id": ids, "birth": by * 10000 + rng.integers(1, 13, n) * 100 + 1,
            "sex": rng.choice([1, 2], n, p=[0.45, 0.55]), "race": rng.choice([1, 2, 3, 5], n, p=[.83, .1, .02, .05]),
            "esrd": rng.random(n) < 0.07, "state": rng.integers(1, 55, n)}
    base["death_year"] = np.where(rng.random(n) < 0.05, rng.choice([2008, 2009, 2010], n), 0)
    cc_state = rng.random((n, len(CC))) < np.array(CC_PREV)
    cost_state = rng.normal(0, 1, n)
    alive = np.ones(n, bool)
    ip_rows, op_rows = [], []
    for year in (2008, 2009, 2010):
        sel = alive.copy()
        sub = {k: v[sel] for k, v in base.items()}
        df, has_ip, ip, op = bene_year(rng, sub, year, cc_state[sel], cost_state[sel])
        df.to_csv(out / f"DE1_0_{year}_Beneficiary_Summary_File_Sample_1.csv", index=False)
        n_ip = np.where(has_ip, rng.integers(1, 4, sel.sum()), 0)
        n_op = np.where(op > 0, rng.poisson(3, sel.sum()) + 1, 0)
        ip_rows += claims(rng, sub["id"], year, cc_state[sel], n_ip, ip, "IP")
        op_rows += claims(rng, sub["id"], year, cc_state[sel], n_op, op, "OP")
        # evolve: new chronic conditions, cost persistence, deaths
        cc_state = cc_state | (rng.random(cc_state.shape) < 0.04)
        cost_state = 0.7 * cost_state + rng.normal(0, 0.7, n)
        alive &= ~(base["death_year"] == year)
    pd.DataFrame(ip_rows).to_csv(out / "DE1_0_2008_to_2010_Inpatient_Claims_Sample_1.csv", index=False)
    pd.DataFrame(op_rows).to_csv(out / "DE1_0_2008_to_2010_Outpatient_Claims_Sample_1.csv", index=False)
    (out / ".SYNTHETIC_TEST_DATA").write_text("Files in this folder were generated by tests/make_synthetic_sample.py\n")
    print(f"Synthetic test sample written to {out}: {n} benes, {len(ip_rows)} IP, {len(op_rows)} OP claims")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--out", default="data/raw")
    a = ap.parse_args()
    main(a.n, a.out)
