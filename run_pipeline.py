"""End-to-end pipeline: load -> SQL features -> data quality -> models -> validation -> report/Excel/dashboard.

Usage:
    python run_pipeline.py                 # real CMS DE-SynPUF files in data/raw (see scripts/download_synpuf.sh)
    python run_pipeline.py --synthetic     # generate a schema-identical test sample first (CI smoke test)
"""
import argparse
import json
import time
import warnings
from datetime import date

warnings.filterwarnings("ignore")

from src import config as C
from src import dashboard, data_quality, excel_workbook, features, load_data, models, report, validation


def main(synthetic=False):
    t0 = time.time()
    if synthetic:
        from tests.make_synthetic_sample import main as gen
        gen(20000, C.RAW_DIR)
    # Safety: never label generated test data as CMS data
    synthetic = synthetic or (C.RAW_DIR / ".SYNTHETIC_TEST_DATA").exists()
    missing = [f for f in C.FILES.values() if not (C.RAW_DIR / f).exists()]
    if missing:
        raise SystemExit(f"Missing raw files in {C.RAW_DIR}: {missing}\nRun scripts/download_synpuf.sh first.")

    print("[1/7] Loading raw CSVs to SQLite ...");      load_data.run()
    print("[2/7] SQL feature engineering ...");          df, waterfall, _ = features.build()
    print("[3/7] Data-quality tests ...");               dq, recon = data_quality.run()
    print("[4/7] Training models ...")
    train, test, oot, thr = models.split(df)
    reg, clf = models.train_all(train)
    print("[5/7] Independent validation ...");           R = validation.run(train, test, oot, reg, clf)
    R["recon"] = recon
    fnd, rating = validation.findings(R, dq)
    meta = {"data_source": ("SYNTHETIC TEST SAMPLE (schema-identical generator) - NOT CMS DATA" if synthetic
                            else "CMS 2008-2010 Data Entrepreneurs' Synthetic Public Use File (DE-SynPUF), Sample 1"),
            "synthetic": synthetic, "run_date": str(date.today()), "hcc_threshold": thr,
            "n_train": len(train), "n_test": len(test), "n_oot": len(oot),
            "n_negative_target_floored": df.attrs.get("n_negative_target", 0)}
    print("[6/7] Report, figures, results.json ...")
    figs = report.figures(R)
    res = report.results_json(R, dq, waterfall, fnd, rating, meta, recon)
    report.markdown(R, dq, recon, waterfall, fnd, rating, figs, meta)
    if not synthetic:
        report.update_readme(R, fnd, rating, meta)
    print("[7/7] Excel workbook + dashboard ...")
    excel_workbook.build(R, dq, fnd, rating, oot, meta)
    dashboard.build(res)
    print(f"Done in {time.time() - t0:.0f}s. Rating: {rating}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    main(ap.parse_args().synthetic)
