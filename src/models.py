"""Model development: prospective cost model + high-cost claimant (HCC) classifier.

Benchmarks (actuarial practice)       Champion / challengers
- M0 Naive persistence (trended)      - M2 Tweedie GLM (log link, p=1.5)
- M1 Demographic manual rate          - M3 Gradient boosting (Poisson loss)  <- champion
                                      - C1 Logistic regression / C2 Gradient boosting classifier
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, TweedieRegressor
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import config as C

COST_COLS = ["paid_ip", "paid_op", "paid_car", "paid_total", "benres_total"]


def split(df):
    dev = df[df["year"] == C.DEV_FEATURE_YEAR].copy()
    oot = df[df["year"] == C.OOT_FEATURE_YEAR].copy()
    train, test = train_test_split(dev, test_size=C.TEST_SIZE, random_state=C.SEED)
    hcc_threshold = float(train[C.TARGET_COST].quantile(C.HIGH_COST_QUANTILE))
    for d in (train, test, oot):
        d[C.TARGET_HCC] = (d[C.TARGET_COST] >= hcc_threshold).astype(int)
    return train.copy(), test.copy(), oot.copy(), hcc_threshold


def age_band(a):
    return pd.cut(a, [0, 64, 69, 74, 79, 84, 200], labels=["<65", "65-69", "70-74", "75-79", "80-84", "85+"])


class NaivePersistence:
    """Prior-year cost x trend factor (trend estimated on train)."""
    name = "M0 Naive persistence"

    def fit(self, X, y):
        self.trend = y.sum() / max(X["paid_total"].sum(), 1)
        self.floor = y.mean() * 0.25   # members with zero prior cost still carry expected cost
        return self

    def predict(self, X):
        return np.maximum(X["paid_total"].values * self.trend, self.floor)


class DemographicRate:
    """Manual-rate style: mean cost by age band x sex x ESRD cell (credibility-weighted to grand mean)."""
    name = "M1 Demographic manual rate"

    def fit(self, X, y, k=200):
        d = pd.DataFrame({"ab": age_band(X["age"]).astype(str), "f": X["is_female"], "e": X["esrd"], "y": y})
        self.mu = d["y"].mean()
        g = d.groupby(["ab", "f", "e"])["y"].agg(["mean", "count"])
        z = g["count"] / (g["count"] + k)                       # Buhlmann-style credibility
        self.rates = (z * g["mean"] + (1 - z) * self.mu).to_dict()
        return self

    def predict(self, X):
        keys = zip(age_band(X["age"]).astype(str), X["is_female"], X["esrd"])
        return np.array([self.rates.get(k, self.mu) for k in keys])


def _log_costs(X):
    X = X.copy()
    for c in COST_COLS:
        if c in X:
            X[c] = np.log1p(X[c].clip(lower=0))
    return X


def make_glm():
    return make_pipeline(FunctionTransformer(_log_costs), StandardScaler(),
                         TweedieRegressor(power=1.5, link="log", alpha=0.01, max_iter=2000))


def make_gbm(seed=C.SEED, **kw):
    params = dict(loss="poisson", learning_rate=0.05, max_iter=600, max_leaf_nodes=15, min_samples_leaf=200,
                  l2_regularization=1.0, early_stopping=True, validation_fraction=0.15, n_iter_no_change=30,
                  random_state=seed)
    params.update(kw)
    return HistGradientBoostingRegressor(**params)


def make_logit():
    return make_pipeline(FunctionTransformer(_log_costs), StandardScaler(), LogisticRegression(max_iter=2000, C=0.5))


def make_gbm_clf(seed=C.SEED):
    return HistGradientBoostingClassifier(learning_rate=0.05, max_iter=500, max_leaf_nodes=31, min_samples_leaf=100,
                                          l2_regularization=1.0, early_stopping=True, validation_fraction=0.15,
                                          n_iter_no_change=30, random_state=seed)


def train_all(train):
    X, y, yb = train[C.NUMERIC_FEATURES], train[C.TARGET_COST], train[C.TARGET_HCC]
    reg = {
        "M0 Naive persistence": NaivePersistence().fit(X, y),
        "M1 Demographic manual rate": DemographicRate().fit(X, y),
        "M2 Tweedie GLM": make_glm().fit(X, y),
        "M3 Gradient boosting (champion)": make_gbm().fit(X, y),
    }
    clf = {
        "C1 Logistic regression": make_logit().fit(X, yb),
        "C2 Gradient boosting (champion)": make_gbm_clf().fit(X, yb),
    }
    return reg, clf


CHAMPION_REG = "M3 Gradient boosting (champion)"
CHAMPION_CLF = "C2 Gradient boosting (champion)"
