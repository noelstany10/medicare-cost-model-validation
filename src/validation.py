"""Independent model validation toolkit (SR 11-7 / model-risk-management style).

Covers: outcome analysis (in-time + out-of-time backtest), calibration (predictive ratios),
discrimination, stability (PSI/CSI), sensitivity & robustness, benchmarking, explainability,
fairness / disparity testing and leakage review. Each area produces evidence tables that
feed rule-based findings with severity ratings.
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.inspection import partial_dependence, permutation_importance
from sklearn.metrics import (brier_score_loss, mean_absolute_error, mean_squared_error, r2_score,
                             roc_auc_score, roc_curve)

from . import config as C
from . import models as M

RACE = {1: "White", 2: "Black", 3: "Other", 5: "Hispanic"}


# ---------------------------------------------------------------- metrics
def gini_norm(y, p):
    """Normalised Gini: how well predictions rank actual cost (1 = perfect ordering)."""
    def g(a, s):
        o = np.argsort(-s, kind="mergesort")
        a = np.asarray(a)[o]
        cum = np.cumsum(a) / a.sum()
        return cum.sum() / len(a) - (len(a) + 1) / (2 * len(a))
    return g(y, np.asarray(p)) / g(y, np.asarray(y, dtype=float))


def reg_metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    top = p >= np.quantile(p, 0.9)
    return {
        "R2": r2_score(y, p),
        "CPM": 1 - np.abs(y - p).sum() / np.abs(y - y.mean()).sum(),   # Cumming's Prediction Measure (SOA)
        "MAE": mean_absolute_error(y, p),
        "RMSE": float(np.sqrt(mean_squared_error(y, p))),
        "Predictive_ratio": p.sum() / y.sum(),
        "Gini": gini_norm(y, p),
        "Top10_cost_capture": y[top].sum() / y.sum(),
        "Mean_actual": y.mean(), "Mean_predicted": p.mean(),
    }


def hosmer_lemeshow(y, p, g=10):
    d = pd.DataFrame({"y": y, "p": p})
    d["g"] = pd.qcut(d["p"].rank(method="first"), g, labels=False)
    t = d.groupby("g").agg(o=("y", "sum"), e=("p", "sum"), n=("y", "size"))
    hl = (((t.o - t.e) ** 2) / (t.e * (1 - t.e / t.n))).sum()
    return float(hl), float(1 - stats.chi2.cdf(hl, g - 2))


def clf_metrics(y, p):
    y, p = np.asarray(y), np.asarray(p)
    fpr, tpr, _ = roc_curve(y, p)
    top = p >= np.quantile(p, 0.9)
    hl, hl_p = hosmer_lemeshow(y, p)
    return {
        "AUC": roc_auc_score(y, p), "Gini": 2 * roc_auc_score(y, p) - 1, "KS": float(np.max(tpr - fpr)),
        "Brier": brier_score_loss(y, p), "Precision_top10": y[top].mean(), "Recall_top10": y[top].sum() / y.sum(),
        "Lift_top10": y[top].mean() / y.mean(), "HL_stat": hl, "HL_pvalue": hl_p,
        "Event_rate": y.mean(), "Mean_pred_prob": p.mean(),
    }


def decile_table(y, p):
    d = pd.DataFrame({"actual": np.asarray(y, float), "pred": np.asarray(p, float)})
    d["decile"] = pd.qcut(d["pred"].rank(method="first"), 10, labels=range(1, 11)).astype(int)
    t = d.groupby("decile").agg(n=("actual", "size"), pred_sum=("pred", "sum"), actual_sum=("actual", "sum"))
    t["mean_pred"] = t.pred_sum / t.n
    t["mean_actual"] = t.actual_sum / t.n
    t["predictive_ratio"] = t.pred_sum / t.actual_sum
    return t.reset_index()


def psi(expected, actual, bins=10):
    e, a = np.asarray(expected, float), np.asarray(actual, float)
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf
    ep = np.histogram(e, edges)[0] / len(e)
    ap = np.histogram(a, edges)[0] / len(a)
    ep, ap = np.clip(ep, 1e-6, None), np.clip(ap, 1e-6, None)
    tbl = pd.DataFrame({"bin": range(1, len(ep) + 1), "lower": edges[:-1], "upper": edges[1:],
                        "expected_pct": ep, "actual_pct": ap})
    tbl["psi_contrib"] = (tbl.actual_pct - tbl.expected_pct) * np.log(tbl.actual_pct / tbl.expected_pct)
    return float(tbl.psi_contrib.sum()), tbl


def bootstrap_ci(y, p, fn, n=200, seed=C.SEED):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        try:
            vals.append(fn(y[i], p[i]))
        except ValueError:
            continue
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


# ---------------------------------------------------------------- validation run
def subgroup_table(df, pred, target=C.TARGET_COST):
    d = df.assign(pred=pred)
    d["age_band"] = M.age_band(d["age"]).astype(str)
    d["sex"] = np.where(d["is_female"] == 1, "Female", "Male")
    d["race"] = d["race_cd"].map(RACE).fillna("Unknown")
    d["esrd_status"] = np.where(d["esrd"] == 1, "ESRD", "Non-ESRD")
    d["chronic_band"] = pd.cut(d["n_chronic"], [-1, 0, 2, 4, 20], labels=["0", "1-2", "3-4", "5+"]).astype(str)
    d["prior_cost_band"] = pd.cut(d["paid_total"], [-1, 0, 1000, 5000, 20000, 1e12],
                                  labels=["$0", "$1-1k", "$1k-5k", "$5k-20k", "$20k+"]).astype(str)
    rows = []
    for dim in ["age_band", "sex", "race", "esrd_status", "chronic_band", "prior_cost_band"]:
        for lvl, g in d.groupby(dim):
            rows.append({"dimension": dim, "level": lvl, "n": len(g), "actual_mean": g[target].mean(),
                         "pred_mean": g["pred"].mean(), "predictive_ratio": g["pred"].sum() / max(g[target].sum(), 1)})
    return pd.DataFrame(rows)


def run(train, test, oot, reg, clf):
    F = C.NUMERIC_FEATURES
    R = {}

    # 1. Leakage / conceptual soundness checks
    forbidden = [c for c in F if c.startswith("target") or c in ("race_cd", "state_cd")]
    corr = train[F + [C.TARGET_COST]].corr(numeric_only=True)[C.TARGET_COST].drop(C.TARGET_COST)
    R["leakage"] = {"forbidden_features_in_model": forbidden,
                    "max_abs_corr_feature": corr.abs().idxmax(), "max_abs_corr": float(corr.abs().max())}

    # 2. Benchmarking: every model on test (in-time) and OOT
    comp = []
    preds = {}
    for name, m in reg.items():
        for split_name, d in (("Train", train), ("Test (in-time)", test), ("OOT 2009->2010", oot)):
            p = m.predict(d[F])
            preds[(name, split_name)] = p
            comp.append({"model": name, "sample": split_name, **reg_metrics(d[C.TARGET_COST], p)})
    R["reg_comparison"] = pd.DataFrame(comp)
    comp = []
    for name, m in clf.items():
        for split_name, d in (("Train", train), ("Test (in-time)", test), ("OOT 2009->2010", oot)):
            p = m.predict_proba(d[F])[:, 1]
            preds[(name, split_name)] = p
            comp.append({"model": name, "sample": split_name, **clf_metrics(d[C.TARGET_HCC], p)})
    R["clf_comparison"] = pd.DataFrame(comp)

    champ, champ_c = reg[M.CHAMPION_REG], clf[M.CHAMPION_CLF]
    p_test, p_oot = preds[(M.CHAMPION_REG, "Test (in-time)")], preds[(M.CHAMPION_REG, "OOT 2009->2010")]
    pc_test, pc_oot = preds[(M.CHAMPION_CLF, "Test (in-time)")], preds[(M.CHAMPION_CLF, "OOT 2009->2010")]
    R["preds"] = {"test": p_test, "oot": p_oot, "test_clf": pc_test, "oot_clf": pc_oot,
                  "glm_oot": preds[("M2 Tweedie GLM", "OOT 2009->2010")]}

    # 3. Outcome analysis: decile backtests + bootstrap CIs
    R["decile_test"] = decile_table(test[C.TARGET_COST], p_test)
    R["decile_oot"] = decile_table(oot[C.TARGET_COST], p_oot)
    R["ci"] = {
        "R2_oot": bootstrap_ci(oot[C.TARGET_COST].values, p_oot, r2_score),
        "CPM_oot": bootstrap_ci(oot[C.TARGET_COST].values, p_oot,
                                lambda y, p: 1 - np.abs(y - p).sum() / np.abs(y - y.mean()).sum()),
        "PR_oot": bootstrap_ci(oot[C.TARGET_COST].values, p_oot, lambda y, p: p.sum() / y.sum()),
        "AUC_oot": bootstrap_ci(oot[C.TARGET_HCC].values, pc_oot, roc_auc_score),
    }
    fpr, tpr, _ = roc_curve(oot[C.TARGET_HCC], pc_oot)
    idx = np.linspace(0, len(fpr) - 1, 200).astype(int)
    R["roc_oot"] = pd.DataFrame({"fpr": fpr[idx], "tpr": tpr[idx]})
    cal = pd.DataFrame({"y": oot[C.TARGET_HCC].values, "p": pc_oot})
    cal["bin"] = pd.qcut(cal.p.rank(method="first"), 10, labels=range(1, 11)).astype(int)
    R["calibration_clf_oot"] = cal.groupby("bin").agg(mean_pred=("p", "mean"), obs_rate=("y", "mean"), n=("y", "size")).reset_index()

    # 4. Stability: score PSI + feature CSI (dev test vs OOT)
    R["psi_score"], R["psi_score_table"] = psi(p_test, p_oot)
    csi = []
    for f in F:
        if train[f].nunique() > 1:
            v, _ = psi(test[f], oot[f])
            csi.append({"feature": f, "csi": v})
    R["csi"] = pd.DataFrame(csi).sort_values("csi", ascending=False)

    # 5. Subgroup calibration & fairness (race is NOT a model input)
    R["subgroups_oot"] = subgroup_table(oot, p_oot)
    fair = []
    d = oot.assign(p=pc_oot)
    for dim, col in (("race", "race_cd"), ("sex", "is_female")):
        for lvl, g in d.groupby(col):
            if g[C.TARGET_HCC].nunique() < 2:
                continue
            thr = np.quantile(pc_oot, 0.9)
            fair.append({"dimension": dim, "level": RACE.get(lvl, lvl) if dim == "race" else ("Female" if lvl == 1 else "Male"),
                         "n": len(g), "event_rate": g[C.TARGET_HCC].mean(), "AUC": roc_auc_score(g[C.TARGET_HCC], g.p),
                         "flag_rate_top10": (g.p >= thr).mean(),
                         "TPR_top10": ((g.p >= thr) & (g[C.TARGET_HCC] == 1)).sum() / max(g[C.TARGET_HCC].sum(), 1)})
    R["fairness_oot"] = pd.DataFrame(fair)

    # 6. Explainability
    rng = np.random.default_rng(C.SEED)
    sub = test.iloc[rng.choice(len(test), min(6000, len(test)), replace=False)]
    pi = permutation_importance(champ, sub[F], sub[C.TARGET_COST], n_repeats=3, random_state=C.SEED,
                                scoring="neg_mean_absolute_error")
    R["perm_importance"] = (pd.DataFrame({"feature": F, "importance": pi.importances_mean, "std": pi.importances_std})
                            .sort_values("importance", ascending=False).reset_index(drop=True))
    pdp = {}
    for f in R["perm_importance"].feature.head(4):
        r = partial_dependence(champ, sub[F], [F.index(f)], grid_resolution=20, kind="average")
        pdp[f] = pd.DataFrame({"value": r["grid_values"][0], "avg_pred": r["average"][0]})
    R["pdp"] = pdp

    # 7. Sensitivity & robustness
    sens = []
    base_mean = p_oot.mean()
    for shock in (-0.10, 0.10, 0.25):
        X = oot[F].copy()
        for c in M.COST_COLS:
            X[c] = X[c] * (1 + shock)
        X["log_paid_total"] = np.log1p(X["paid_total"])
        sens.append({"test": f"Prior-year costs {shock:+.0%}", "mean_pred_change": champ.predict(X).mean() / base_mean - 1})
    for f in ("n_chronic", "ip_admits"):
        X = oot[F].copy(); X[f] = X[f] + 1
        sens.append({"test": f"{f} +1 for all members", "mean_pred_change": champ.predict(X).mean() / base_mean - 1})
    R["sensitivity"] = pd.DataFrame(sens)

    # Monotonicity sanity: average prediction by chronic count should increase
    mono = oot.assign(p=p_oot).groupby(oot["n_chronic"].clip(upper=8))["p"].mean()
    R["monotonic_chronic"] = bool(np.all(np.diff(mono.values) > -0.02 * mono.mean()))
    R["mono_table"] = mono.reset_index().rename(columns={"n_chronic": "n_chronic_capped", "p": "mean_pred"})

    # Seed stability + hyper-parameter perturbation + feature ablation (retrain)
    rob = []
    for s in (1, 2, 3, 4, 5):
        m = M.make_gbm(seed=s).fit(train[F], train[C.TARGET_COST])
        rob.append({"test": f"Seed {s}", "group": "seed", **{k: v for k, v in reg_metrics(oot[C.TARGET_COST], m.predict(oot[F])).items() if k in ("R2", "CPM", "Predictive_ratio", "Gini")}})
    for kw, label in (({"learning_rate": 0.1}, "learning_rate=0.10"), ({"max_leaf_nodes": 15}, "max_leaf_nodes=15"),
                      ({"max_leaf_nodes": 63}, "max_leaf_nodes=63"), ({"loss": "squared_error"}, "loss=squared_error")):
        m = M.make_gbm(**kw).fit(train[F], train[C.TARGET_COST])
        rob.append({"test": label, "group": "hyperparameter", **{k: v for k, v in reg_metrics(oot[C.TARGET_COST], m.predict(oot[F])).items() if k in ("R2", "CPM", "Predictive_ratio", "Gini")}})
    groups = {"Drop prior-cost features": [c for c in F if c.startswith(("paid", "benres", "log_paid"))],
              "Drop claims-derived features": [c for c in F if c.startswith(("ip_", "op_", "er_", "n_providers", "n_distinct", "dx_"))],
              "Drop chronic-condition flags": [c for c in F if c.startswith("sp_") or c == "n_chronic"]}
    for label, drop in groups.items():
        keep = [c for c in F if c not in drop]
        m = M.make_gbm().fit(train[keep], train[C.TARGET_COST])
        rob.append({"test": label, "group": "ablation", **{k: v for k, v in reg_metrics(oot[C.TARGET_COST], m.predict(oot[keep])).items() if k in ("R2", "CPM", "Predictive_ratio", "Gini")}})
    R["robustness"] = pd.DataFrame(rob)
    return R


# ---------------------------------------------------------------- findings
def findings(R, dq):
    out = []
    rc = R["reg_comparison"].set_index(["model", "sample"])
    ch = M.CHAMPION_REG
    t, o = rc.loc[(ch, "Test (in-time)")], rc.loc[(ch, "OOT 2009->2010")]
    glm_o = rc.loc[("M2 Tweedie GLM", "OOT 2009->2010")]
    tr = rc.loc[(ch, "Train")]

    def add(area, sev, title, evidence, rec):
        out.append({"id": f"F-{len(out)+1:02d}", "area": area, "severity": sev, "finding": title,
                    "evidence": evidence, "recommendation": rec})

    for _, r in dq[dq.status.isin(["FAIL", "WARN"])].iterrows():
        add("Data quality", "Medium" if r.status == "FAIL" else "Low", f"{r.check_id}: {r.description}",
            f"Observed {r.observed:.4f} vs threshold {r.threshold}",
            "Document root cause with data owner; add exclusion or correction rule and monitor in production.")
    if abs(o.Predictive_ratio - 1) > 0.05:
        add("Outcome analysis", "High" if abs(o.Predictive_ratio - 1) > 0.10 else "Medium",
            "Aggregate out-of-time calibration outside +/-5% tolerance",
            f"OOT predictive ratio {o.Predictive_ratio:.3f} (in-time {t.Predictive_ratio:.3f}); "
            f"mean actual ${o.Mean_actual:,.0f} vs predicted ${o.Mean_predicted:,.0f}",
            "Introduce an explicit annual cost-trend / calibration factor refreshed each year before use in budgeting.")
    if t.R2 > 0 and (t.R2 - o.R2) / t.R2 > 0.15:
        add("Outcome analysis", "Medium", "Material out-of-time deterioration in explanatory power",
            f"R2 in-time {t.R2:.3f} vs OOT {o.R2:.3f}", "Investigate drivers (population shift, coding changes); consider re-training on pooled years.")
    if tr.R2 - t.R2 > 0.10:
        add("Conceptual soundness", "Medium", "Indication of over-fitting", f"R2 train {tr.R2:.3f} vs test {t.R2:.3f}",
            "Increase regularisation / min_samples_leaf; use cross-validated early stopping.")
    if R["psi_score"] > 0.10:
        add("Stability", "High" if R["psi_score"] > 0.25 else "Medium", "Score distribution shift between development and OOT",
            f"Score PSI = {R['psi_score']:.3f}", "Set PSI monitoring thresholds (0.10 / 0.25) with re-calibration trigger.")
    hi_csi = R["csi"][R["csi"].csi > 0.10]
    if len(hi_csi):
        add("Stability", "Medium" if hi_csi.csi.max() > 0.25 else "Low", "Feature distribution shift (CSI > 0.10)",
            ", ".join(f"{a}={b:.2f}" for a, b in hi_csi.head(5)[["feature", "csi"]].values),
            "Review whether shift is real (population/coding) or a data artefact; monitor quarterly.")
    sg = R["subgroups_oot"]
    bad = sg[(sg.n >= 500) & ((sg.predictive_ratio < 0.85) | (sg.predictive_ratio > 1.15))]
    if len(bad):
        add("Outcome analysis", "Medium", "Subgroup mis-calibration (predictive ratio outside 0.85-1.15)",
            "; ".join(f"{a}={b}: PR {c:.2f}" for a, b, c in bad[["dimension", "level", "predictive_ratio"]].head(6).values),
            "Add segment-level calibration or interaction terms; communicate known biases to model users.")
    fr = R["fairness_oot"]
    race = fr[fr.dimension == "race"]
    if len(race) > 1 and (race.AUC.max() - race.AUC.min() > 0.05):
        add("Fairness", "Medium", "Discrimination (AUC) differs materially across race groups",
            f"AUC range {race.AUC.min():.3f}-{race.AUC.max():.3f}", "Perform disparity review with compliance; consider group-aware calibration.")
    lift = o.CPM - glm_o.CPM
    if lift < 0.01:
        add("Benchmarking", "Low", "Champion complexity not clearly justified over interpretable GLM",
            f"OOT CPM champion {o.CPM:.3f} vs Tweedie GLM {glm_o.CPM:.3f}", "Consider GLM as production model or keep as permanent challenger.")
    seed = R["robustness"][R["robustness"].group == "seed"]
    if seed.R2.std() > 0.01:
        add("Robustness", "Low", "Results sensitive to random seed", f"Std of OOT R2 across seeds {seed.R2.std():.4f}",
            "Average multiple seeds or fix seed in production configuration.")
    if not R["monotonic_chronic"]:
        add("Conceptual soundness", "Medium", "Predicted cost not monotonic in chronic-condition count",
            "See monotonicity table", "Apply monotonic constraints on clinical burden features.")
    add("Conceptual soundness", "Low", "Synthetic data limits clinical credibility of relationships",
        "CMS DE-SynPUF perturbs and synthesises variables, weakening true clinical-cost associations; "
        "Carrier and Part D detail not used as features.",
        "Re-estimate and re-validate on production claims (with Carrier and PDE) before any business use.")
    add("Implementation", "Low", "Model monitoring plan required",
        "No production monitoring exists for this development model.",
        "Monthly: PSI/CSI, predictive ratio by segment, HCC precision@10%; annual full re-validation.")
    df = pd.DataFrame(out)
    sev = df.severity.value_counts()
    if sev.get("High", 0) >= 2:
        rating = "Unsatisfactory - not fit for use until High findings are remediated"
    elif sev.get("High", 0) == 1:
        rating = "Needs improvement - conditionally fit for use with compensating controls"
    elif sev.get("Medium", 0) > 0:
        rating = "Satisfactory with findings - fit for use; Medium findings to be remediated within 6 months"
    else:
        rating = "Satisfactory - fit for intended use"
    return df, rating
