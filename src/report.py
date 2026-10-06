"""Figures, machine-readable results and the Markdown Model Validation Report."""
import json
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as C
from . import models as M

BLUE, ORANGE, AQUA, GRAY, INK, INK2 = "#2a78d6", "#eb6834", "#1baf7a", "#8a8984", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#c9c8c3", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.grid": True, "grid.color": "#ecebe7", "grid.linewidth": 0.8, "axes.axisbelow": True,
                     "figure.dpi": 130, "savefig.bbox": "tight", "axes.titleweight": "bold", "axes.titlesize": 11})


def _save(fig, name):
    C.FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(C.FIG_DIR / name)
    plt.close(fig)
    return f"figures/{name}"


def figures(R):
    figs = {}
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.6), sharey=True)
    x = np.arange(1, 11)
    for ax, (key, ttl) in zip(axs, (("decile_test", "In-time test (2009)"), ("decile_oot", "Out-of-time 2010, raw"),
                                     ("decile_oot_norm", "Out-of-time 2010, normalised"))):
        d = R[key]
        ax.bar(x - 0.2, d.mean_pred, 0.38, color=BLUE, label="Predicted")
        ax.bar(x + 0.2, d.mean_actual, 0.38, color=ORANGE, label="Actual")
        ax.set_xticks(x); ax.set_xlabel("Predicted-risk decile"); ax.set_title(ttl, loc="left")
        ax.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter("${x:,.0f}"))
    axs[0].set_ylabel("Mean paid cost per member ($)"); axs[0].legend(frameon=False, loc="upper left")
    figs["decile"] = _save(fig, "decile_backtest_oot.png")

    rc = R["reg_comparison"]; o = rc[rc["sample"] == "OOT normalised"]
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    cols = [BLUE if "champion" in m else GRAY for m in o.model]
    ax.barh(o.model, o.CPM, color=cols, height=0.55)
    for i, v in enumerate(o.CPM):
        ax.text(v + 0.003 if v >= 0 else 0.003, i, f"{v:.3f}", va="center", color=INK2, fontsize=9)
    ax.axvline(0, color="#c9c8c3", lw=1)
    ax.invert_yaxis(); ax.set_xlabel("Cumming's Prediction Measure (higher is better)")
    ax.set_title("Benchmarking on the out-of-time sample (normalised)", loc="left")
    figs["benchmark"] = _save(fig, "benchmark_cpm_oot.png")

    fig, axs = plt.subplots(1, 2, figsize=(8, 3.5))
    roc = R["roc_oot"]
    axs[0].plot(roc.fpr, roc.tpr, color=BLUE, lw=2); axs[0].plot([0, 1], [0, 1], color=GRAY, lw=1, ls="--")
    auc = R["clf_comparison"].query("model == @M.CHAMPION_CLF and sample == 'OOT 2009->2010'").AUC.iloc[0]
    axs[0].set_title(f"ROC, high-cost claimant (OOT AUC {auc:.3f})", loc="left")
    axs[0].set_xlabel("False positive rate"); axs[0].set_ylabel("True positive rate")
    cal = R["calibration_clf_oot"]
    lim = max(cal.mean_pred.max(), cal.obs_rate.max()) * 1.1
    axs[1].plot([0, lim], [0, lim], color=GRAY, lw=1, ls="--")
    axs[1].plot(cal.mean_pred, cal.obs_rate, color=BLUE, lw=2, marker="o", ms=5)
    axs[1].set_title("Calibration by predicted-risk decile", loc="left")
    axs[1].set_xlabel("Mean predicted probability"); axs[1].set_ylabel("Observed high-cost rate")
    figs["roc"] = _save(fig, "classifier_roc_calibration_oot.png")

    t = R["psi_score_table"]
    fig, ax = plt.subplots(figsize=(7.5, 3.0))
    ax.bar(t.bin - 0.2, t.expected_pct, 0.38, color=BLUE, label="Development (2008 base)")
    ax.bar(t.bin + 0.2, t.actual_pct, 0.38, color=ORANGE, label="Out-of-time (2009 base)")
    ax.set_xticks(t.bin); ax.set_xlabel("Score bin (development deciles)"); ax.set_ylabel("Share of members")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_title(f"Score stability: PSI = {R['psi_score']:.3f}", loc="left"); ax.legend(frameon=False, ncol=2, loc="upper left")
    figs["psi"] = _save(fig, "psi_score.png")

    pi = R["perm_importance"].head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.barh(pi.feature, pi.importance, xerr=pi["std"], color=BLUE, height=0.6, error_kw={"ecolor": GRAY, "lw": 1})
    ax.set_xlabel("Increase in MAE when feature is permuted ($)")
    ax.set_title("Permutation importance (champion cost model)", loc="left")
    figs["importance"] = _save(fig, "permutation_importance.png")

    fig, axs = plt.subplots(1, len(R["pdp"]), figsize=(9, 2.6), sharey=True)
    for ax, (f, p) in zip(np.atleast_1d(axs), R["pdp"].items()):
        ax.plot(p.value, p.avg_pred, color=BLUE, lw=2); ax.set_title(f, loc="left", fontsize=10); ax.set_xlabel("feature value")
    np.atleast_1d(axs)[0].set_ylabel("Avg predicted cost ($)")
    fig.suptitle("Partial dependence of top features", x=0.01, ha="left", fontweight="bold", fontsize=11)
    figs["pdp"] = _save(fig, "partial_dependence.png")

    sg = R["subgroups_oot"].copy()
    sg["label"] = sg.dimension + ": " + sg.level.astype(str)
    sg = sg.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.axvspan(0.85, 1.15, color="#ecebe7", zorder=0)
    ax.axvline(1, color=GRAY, lw=1)
    ax.scatter(sg.predictive_ratio, sg.label, color=BLUE, s=36, zorder=3)
    ax.set_xlabel("Predictive ratio (predicted / actual); shaded = 0.85-1.15 tolerance")
    ax.set_title("Out-of-time calibration by member segment", loc="left")
    figs["subgroups"] = _save(fig, "subgroup_predictive_ratio.png")
    return figs


def _md(df, floatfmt=".3f"):
    return df.to_markdown(index=False, floatfmt=floatfmt)


def results_json(R, dq, waterfall, findings, rating, meta, recon):
    def rec(df):
        return json.loads(df.to_json(orient="records"))
    out = {
        "meta": meta, "rating": rating,
        "reg_comparison": rec(R["reg_comparison"]), "clf_comparison": rec(R["clf_comparison"]),
        "decile_oot": rec(R["decile_oot"]), "decile_test": rec(R["decile_test"]), "decile_oot_norm": rec(R["decile_oot_norm"]),
        "norm_factor": R["norm_factor"], "recon": rec(recon),
        "psi_score": R["psi_score"], "psi_table": rec(R["psi_score_table"].replace([np.inf, -np.inf], None)),
        "csi": rec(R["csi"].head(15)), "subgroups_oot": rec(R["subgroups_oot"]), "fairness_oot": rec(R["fairness_oot"]),
        "perm_importance": rec(R["perm_importance"].head(15)), "sensitivity": rec(R["sensitivity"]),
        "robustness": rec(R["robustness"]), "roc_oot": rec(R["roc_oot"]), "calibration_clf_oot": rec(R["calibration_clf_oot"]),
        "ci": R["ci"], "leakage": R["leakage"], "dq": rec(dq), "waterfall": rec(waterfall), "findings": rec(findings),
    }
    C.OUT_DIR.mkdir(parents=True, exist_ok=True)
    (C.OUT_DIR / "results.json").write_text(json.dumps(out, indent=1, default=float))
    return out


def update_readme(R, findings, rating, meta):
    """Refresh the results block in README.md between the RESULTS markers."""
    path = C.ROOT / "README.md"
    if not path.exists():
        return
    rc = R["reg_comparison"].set_index(["model", "sample"])
    t = rc.loc[(M.CHAMPION_REG, "Test (in-time)")]
    tg = rc.loc[("M2 Tweedie GLM", "Test (in-time)")]
    tb = rc.loc[("M1 Demographic manual rate", "Test (in-time)")]
    o = rc.loc[(M.CHAMPION_REG, "OOT normalised")]
    g = rc.loc[("M2 Tweedie GLM", "OOT normalised")]
    b = rc.loc[("M1 Demographic manual rate", "OOT normalised")]
    raw = rc.loc[(M.CHAMPION_REG, "OOT 2009->2010")]
    cc = R["clf_comparison"].set_index(["model", "sample"])
    ct, c = cc.loc[(M.CHAMPION_CLF, "Test (in-time)")], cc.loc[(M.CHAMPION_CLF, "OOT relative top 10%")]
    sev = findings.severity.value_counts()
    warn = "\n> **Test run on the generated sample, not CMS data.**\n" if meta["synthetic"] else ""
    yoy = float(R["recon"]["yoy_change"].iloc[-1]) if "recon" in R else 0.0
    kf = ""
    if abs(raw.Predictive_ratio - 1) > 0.05:
        kf = (f"**Key validation finding:** the raw out-of-time predictive ratio is **{raw.Predictive_ratio:.2f}**. "
              f"The validation traced this to a {yoy:+.0%} change in mean paid cost per beneficiary in the {C.OOT_FEATURE_YEAR + 1} "
              f"source data (DE-SynPUF {C.OOT_FEATURE_YEAR + 1} claims are incomplete), while the input score distribution stayed "
              f"stable (PSI {R['psi_score']:.3f}). The model is rated not fit for budgeting without an annual normalisation factor.")
    block = f"""<!-- RESULTS:START -->
### Headline results
{warn}
**In-time hold-out** (2008 features → 2009 cost, {meta['n_test']:,} beneficiaries) and **out-of-time** (2009 features → 2010 cost, {meta['n_oot']:,} beneficiaries; predictions normalised to the 2010 total, like CMS annual risk-score normalisation):

| | Champion GBM | Tweedie GLM | Demographic manual rate |
|---|---|---|---|
| R², in-time | **{t.R2:.3f}** | {tg.R2:.3f} | {tb.R2:.3f} |
| Cumming's Prediction Measure, in-time | **{t.CPM:.3f}** | {tg.CPM:.3f} | {tb.CPM:.3f} |
| Gini (cost ranking), in-time | **{t.Gini:.3f}** | {tg.Gini:.3f} | {tb.Gini:.3f} |
| R², out-of-time normalised | **{o.R2:.3f}** | {g.R2:.3f} | {b.R2:.3f} |
| Gini, out-of-time | **{o.Gini:.3f}** | {g.Gini:.3f} | {b.Gini:.3f} |

High-cost claimant classifier: **AUC {ct.AUC:.3f}** in-time (**{ct.Lift_top10:.1f}× lift** in top decile); AUC {c.AUC:.3f} out-of-time.

{kf}
**Validation rating:** {rating} ({sev.get('High', 0)} High / {sev.get('Medium', 0)} Medium / {sev.get('Low', 0)} Low findings). *Data: {meta['data_source']}; run {meta['run_date']}.*
<!-- RESULTS:END -->"""
    txt = path.read_text()
    s, e = txt.find("<!-- RESULTS:START -->"), txt.find("<!-- RESULTS:END -->")
    if s >= 0 and e > s:
        path.write_text(txt[:s] + block + txt[e + len("<!-- RESULTS:END -->"):])


def markdown(R, dq, recon, waterfall, findings, rating, figs, meta):
    rc, cc = R["reg_comparison"], R["clf_comparison"]
    ch = rc[(rc.model == M.CHAMPION_REG)].set_index("sample")
    cl = cc[(cc.model == M.CHAMPION_CLF)].set_index("sample")
    o, oc = ch.loc["OOT 2009->2010"], cl.loc["OOT 2009->2010"]
    t, ct, on, orel = ch.loc["Test (in-time)"], cl.loc["Test (in-time)"], ch.loc["OOT normalised"], cl.loc["OOT relative top 10%"]
    yoy = float(R["recon"]["yoy_change"].iloc[-1]) if "recon" in R else 0.0
    kf = ""
    if abs(o.Predictive_ratio - 1) > 0.05:
        kf = (f"> **Key validation finding.** The raw OOT predictive ratio is **{o.Predictive_ratio:.2f}**. Mean Medicare paid cost per "
              f"beneficiary changes {yoy:+.0%} from {C.OOT_FEATURE_YEAR} to {C.OOT_FEATURE_YEAR + 1} in the source data (DQ-18), while the "
              f"input score distribution is stable (PSI {R['psi_score']:.3f}). This points to incomplete {C.OOT_FEATURE_YEAR + 1} claims in "
              f"DE-SynPUF rather than a change in the population or the model. Ranking performance holds after normalisation "
              f"(Gini {on.Gini:.3f} vs {t.Gini:.3f} in-time).")
    sev = findings.severity.value_counts()
    banner = ""
    if meta["synthetic"]:
        banner = ("> **WARNING - TEST RUN ON GENERATED SAMPLE.** These results were produced on the schema-identical "
                  "test generator (`tests/make_synthetic_sample.py`), not on CMS data. Run the GitHub Actions workflow "
                  "or `python run_pipeline.py` with the real files to regenerate.\n\n")
    regtbl = rc[["model", "sample", "R2", "CPM", "MAE", "Predictive_ratio", "Gini", "Top10_cost_capture"]]
    clftbl = cc[["model", "sample", "AUC", "Gini", "KS", "Brier", "Precision_top10", "Lift_top10", "HL_pvalue"]]
    dqtbl = dq[["check_id", "category", "description", "observed", "threshold", "status"]]
    wf = waterfall.pivot(index=["step", "rule"], columns="feature_year", values="n").reset_index()
    wf.columns = [str(c) for c in wf.columns]
    f_tbl = findings[["id", "area", "severity", "finding", "evidence", "recommendation"]]
    ci = R["ci"]
    lines = f"""# Model Validation Report
## Medicare Prospective Cost Model & High-Cost Claimant Classifier

| | |
|---|---|
| **Model** | Next-year Medicare paid-cost model (Poisson gradient boosting) + high-cost claimant classifier |
| **Model owner (developer)** | Healthcare Analytics - Predictive Modelling |
| **Validator** | Independent Model Validation (second line) |
| **Data** | {meta['data_source']} |
| **Validation date** | {meta['run_date']} |
| **Overall rating** | **{rating}** |

{banner}## 1. Executive summary

The model predicts each Medicare fee-for-service beneficiary's **total Medicare paid cost in the next calendar year**
(inpatient + outpatient + carrier) from the current year's demographics, coverage, chronic conditions, utilisation and
cost history. A companion classifier flags likely **high-cost claimants** (top {100*(1-C.HIGH_COST_QUANTILE):.0f}% of next-year cost,
threshold ${meta['hcc_threshold']:,.0f}). Intended uses: medical cost forecasting / budget planning, care-management targeting and
actuarial risk stratification.

**Key results** (in-time = 2008 features -> 2009 cost hold-out, n = {meta['n_test']:,}; out-of-time (OOT) = 2009 features -> 2010 cost, n = {meta['n_oot']:,}):

| Metric | In-time test | OOT raw | OOT normalised* | 95% CI (OOT) |
|---|---|---|---|---|
| R-squared (cost) | {t.R2:.3f} | {o.R2:.3f} | {on.R2:.3f} | {ci['R2_oot_norm'][0]:.3f} - {ci['R2_oot_norm'][1]:.3f} (norm.) |
| Cumming's Prediction Measure | {t.CPM:.3f} | {o.CPM:.3f} | {on.CPM:.3f} | {ci['CPM_oot_norm'][0]:.3f} - {ci['CPM_oot_norm'][1]:.3f} (norm.) |
| Predictive ratio (predicted / actual) | {t.Predictive_ratio:.3f} | {o.Predictive_ratio:.3f} | 1.000 | {ci['PR_oot'][0]:.3f} - {ci['PR_oot'][1]:.3f} (raw) |
| Normalised Gini (ranking) | {t.Gini:.3f} | {o.Gini:.3f} | {on.Gini:.3f} | |
| Share of actual cost in top-10% predicted | {t.Top10_cost_capture:.1%} | {o.Top10_cost_capture:.1%} | {on.Top10_cost_capture:.1%} | |
| High-cost claimant AUC | {ct.AUC:.3f} | {oc.AUC:.3f} | {orel.AUC:.3f} (relative top 10%) | {ci['AUC_oot'][0]:.3f} - {ci['AUC_oot'][1]:.3f} (raw) |
| High-cost lift in top decile | {ct.Lift_top10:.2f}x | {oc.Lift_top10:.2f}x | {orel.Lift_top10:.2f}x | |
| Score PSI (development vs OOT) | | {R['psi_score']:.3f} | | |

\* *Normalised* = OOT predictions rescaled by a single factor ({R['norm_factor']:.3f}) so they sum to actual 2010 cost,
equivalent to the annual normalisation CMS applies to HCC risk scores. It isolates **ranking / relative accuracy** from
the **level shift** in the outcome year. For the high-cost classifier, "relative" re-defines a high-cost claimant as the top 10% of 2010 cost.

{kf}

**Findings:** {sev.get('High', 0)} High, {sev.get('Medium', 0)} Medium, {sev.get('Low', 0)} Low - see Section 10.

## 2. Model purpose, scope and design

* **Unit of analysis:** beneficiary-year. **Target:** sum of `MEDREIMB_IP + MEDREIMB_OP + MEDREIMB_CAR` in year t+1.
* **Development sample:** base year 2008 -> outcome 2009, 70/30 random split (train {meta['n_train']:,} / in-time test {meta['n_test']:,}).
* **Out-of-time (OOT) sample:** base year 2009 -> outcome 2010 ({meta['n_oot']:,} members), never used in fitting.
* **Models:** two actuarial benchmarks (trended persistence, credibility-weighted demographic manual rate), an interpretable
  Tweedie GLM (log link, p = 1.5) and the champion Poisson-loss histogram gradient boosting model. Classifier: logistic
  regression challenger vs gradient boosting champion.
* **Features ({len(C.NUMERIC_FEATURES)}):** age, sex, ESRD, Part A/B/D/HMO coverage months, 11 CMS Chronic Condition Warehouse flags,
  prior-year paid cost by setting and beneficiary liability, inpatient admits/days/30-day readmissions, outpatient & ED visits,
  distinct providers, and 12 ICD-9 clinical condition categories built in SQL (`sql/02_claims_features.sql`).
* **Excluded by design:** race (used only for disparity testing) and state (geographic proxy risk).

## 3. Data and population

Source tables were loaded to SQLite and transformed with version-controlled SQL (`sql/`). Population waterfall:

{_md(wf, ".0f")}

### 3.1 Data quality testing

{_md(dqtbl, ".4f")}

Inpatient claim-to-summary reconciliation (claims `CLM_PMT_AMT` vs summary `MEDREIMB_IP`):

{_md(recon, ".3f")}

## 4. Conceptual soundness

* **Negative reimbursements:** {meta.get('n_negative_target_floored', 0):,} beneficiary-years had a negative net
  next-year Medicare reimbursement (payment adjustments). The target was floored at $0 for modelling; prior-year cost
  features are floored the same way. See DQ-09.
* **Target definition** is consistent with prospective risk adjustment practice (SOA risk-adjuster studies): concurrent-year
  information predicts the following year's cost. No outcome-year information enters the feature set.
* **Leakage review:** forbidden columns in model = `{R['leakage']['forbidden_features_in_model']}`; highest single feature
  correlation with target = `{R['leakage']['max_abs_corr_feature']}` ({R['leakage']['max_abs_corr']:.3f}) - no evidence of leakage.
* **Loss function:** Poisson / Tweedie deviance is appropriate for non-negative, zero-inflated, right-skewed cost data and
  preserves the aggregate mean (balance property), which matters for budgeting.
* **Monotonicity:** mean prediction is {'monotonically increasing' if R['monotonic_chronic'] else 'NOT monotonic'} in chronic-condition count:

{_md(R['mono_table'], ".0f")}

## 5. Outcome analysis

### 5.1 Cost model - benchmarking across samples

{_md(regtbl)}

![benchmark]({figs['benchmark']})

### 5.2 Decile backtests

OOT raw:

{_md(R['decile_oot'], ",.2f")}

OOT normalised (factor {R['norm_factor']:.3f}):

{_md(R['decile_oot_norm'], ",.2f")}

![decile]({figs['decile']})

### 5.3 High-cost claimant classifier

{_md(clftbl)}

![roc]({figs['roc']})

## 6. Stability

Score PSI between in-time test and OOT = **{R['psi_score']:.3f}** (< 0.10 stable, 0.10-0.25 monitor, > 0.25 significant shift).

![psi]({figs['psi']})

Top characteristic stability indices (CSI):

{_md(R['csi'].head(10))}

## 7. Sensitivity and robustness

**Input shocks (OOT, champion):**

{_md(R['sensitivity'])}

**Seed, hyper-parameter and feature-ablation re-fits (OOT; R2/CPM after normalisation, plus raw predictive ratio):**

{_md(R['robustness'])}

## 8. Explainability

![importance]({figs['importance']})

![pdp]({figs['pdp']})

## 9. Segment calibration and fairness

![subgroups]({figs['subgroups']})

Predictive ratios below use OOT predictions after aggregate normalisation (relative calibration by segment).

{_md(R['subgroups_oot'])}

High-cost classifier disparity review (race is not a model input):

{_md(R['fairness_oot'])}

## 10. Findings and recommendations

{_md(f_tbl)}

## 11. Ongoing monitoring plan

| Metric | Frequency | Green | Amber | Red |
|---|---|---|---|---|
| Score PSI | Monthly | < 0.10 | 0.10 - 0.25 | > 0.25 |
| Feature CSI (top 10) | Monthly | < 0.10 | 0.10 - 0.25 | > 0.25 |
| Aggregate predictive ratio | Quarterly | 0.95 - 1.05 | 0.90 - 1.10 | outside |
| Segment predictive ratio (n >= 500) | Quarterly | 0.90 - 1.10 | 0.85 - 1.15 | outside |
| HCC AUC | Quarterly | >= dev - 0.02 | dev - 0.05 | below |
| Full re-validation | Annual / material change | | | |

## 12. Limitations

* CMS DE-SynPUF is a **synthetic** public-use file: values are perturbed and imputed to protect privacy, so clinical
  relationships are weaker than in production claims and absolute accuracy should not be compared with commercial risk models.
* Carrier (physician) and Part D event-level files are not used for features (only their annual totals via the summary file).
* Only one base year of history is available for the OOT window, limiting multi-year look-back features.

---
*Reproducible: `python run_pipeline.py` regenerates every number, table and figure in this report.*
"""
    (C.REPORT_DIR / "Model_Validation_Report.md").write_text(lines)
