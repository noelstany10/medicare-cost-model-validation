"""Unit tests for the validation metrics (run: pytest -q tests)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.validation import clf_metrics, decile_table, gini_norm, psi, reg_metrics  # noqa: E402

rng = np.random.default_rng(0)


def test_psi_identical_distribution_is_zero():
    x = rng.gamma(2, 1000, 5000)
    v, tbl = psi(x, x)
    assert abs(v) < 1e-9 and len(tbl) == 10


def test_psi_detects_shift():
    x = rng.normal(0, 1, 5000)
    assert psi(x, x + 1)[0] > 0.25


def test_gini_perfect_and_random():
    y = rng.gamma(1, 1000, 4000)
    assert abs(gini_norm(y, y) - 1) < 1e-9
    assert abs(gini_norm(y, rng.random(4000))) < 0.1


def test_reg_metrics_perfect_prediction():
    y = rng.gamma(1, 1000, 1000)
    m = reg_metrics(y, y)
    assert abs(m["R2"] - 1) < 1e-9 and abs(m["CPM"] - 1) < 1e-9 and abs(m["Predictive_ratio"] - 1) < 1e-9


def test_decile_table_balances():
    y, p = rng.gamma(1, 1000, 2000), rng.gamma(1, 1000, 2000)
    t = decile_table(y, p)
    assert t.n.sum() == 2000 and np.isclose(t.actual_sum.sum(), y.sum())


def test_clf_metrics_ranges():
    y = rng.integers(0, 2, 3000)
    p = np.clip(y * 0.3 + rng.random(3000) * 0.7, 0, 1)
    m = clf_metrics(y, p)
    assert 0.5 < m["AUC"] <= 1 and 0 <= m["KS"] <= 1 and m["Lift_top10"] > 1
