"""ML alpha: holdout metrics and diagnostics shape."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from finance_core.strategies.ml_alpha import MLAlphaStrategy


@pytest.fixture
def long_price_frame() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 200
    walk = 100 + np.cumsum(rng.normal(0, 0.5, n))
    return pd.DataFrame({"LAB": walk})


def test_train_records_time_ordered_holdout_metrics(long_price_frame: pd.DataFrame) -> None:
    strat = MLAlphaStrategy(retrain_every=999, min_train_samples=60)
    strat.generate_signals(long_price_frame)
    assert "LAB" in strat._models
    m = strat._last_train_metrics["LAB"]
    assert m["train_rows"] >= 10
    assert m["holdout_rows"] >= 1
    assert "holdout_accuracy" in m
    assert "holdout_brier" in m
    assert "holdout_roc_auc" in m


def test_export_diagnostics_includes_methodology(long_price_frame: pd.DataFrame) -> None:
    strat = MLAlphaStrategy(retrain_every=999, min_train_samples=60)
    strat.generate_signals(long_price_frame)
    d = strat.export_diagnostics()
    assert d["strategy"] == "ml_alpha"
    assert d["methodology"]["split"] == "time_ordered_80_20"
    detail = d["trained_symbols_detail"]["LAB"]
    assert detail["holdout_metrics"] is not None
