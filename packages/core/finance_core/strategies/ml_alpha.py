"""ML-based alpha signal generation — feature engineering + GradientBoosting."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from finance_core.strategies.base import (
    Signal,
    SignalDirection,
    Strategy,
    ema,
    rsi,
    sma,
)

logger = logging.getLogger(__name__)


def _build_features(prices: pd.Series) -> pd.DataFrame:
    """Engineer features from a price series for ML prediction."""
    df = pd.DataFrame({"close": prices})

    df["ret_1d"] = df["close"].pct_change(1)
    df["ret_5d"] = df["close"].pct_change(5)
    df["ret_10d"] = df["close"].pct_change(10)
    df["ret_20d"] = df["close"].pct_change(20)

    df["vol_5d"] = df["ret_1d"].rolling(5).std()
    df["vol_10d"] = df["ret_1d"].rolling(10).std()
    df["vol_20d"] = df["ret_1d"].rolling(20).std()

    df["rsi_14"] = rsi(df["close"], 14)

    sma_10 = sma(df["close"], 10)
    sma_20 = sma(df["close"], 20)
    sma_50 = sma(df["close"], 50)

    df["price_to_sma10"] = df["close"] / sma_10 - 1
    df["price_to_sma20"] = df["close"] / sma_20 - 1
    df["price_to_sma50"] = df["close"] / sma_50 - 1

    df["sma10_sma20"] = sma_10 / sma_20 - 1

    ema_12 = ema(df["close"], 12)
    ema_26 = ema(df["close"], 26)
    df["macd_norm"] = (ema_12 - ema_26) / df["close"]

    high_20 = df["close"].rolling(20).max()
    low_20 = df["close"].rolling(20).min()
    df["channel_pos"] = (df["close"] - low_20) / (high_20 - low_20 + 1e-10)

    df["skew_20d"] = df["ret_1d"].rolling(20).skew()
    df["kurt_20d"] = df["ret_1d"].rolling(20).kurt()

    return df


class MLAlphaStrategy(Strategy):
    def __init__(
        self,
        retrain_every: int = 50,
        min_train_samples: int = 60,
        confidence_threshold: float = 0.6,
        n_estimators: int = 100,
        max_depth: int = 4,
    ) -> None:
        self.retrain_every = retrain_every
        self.min_train_samples = min_train_samples
        self.confidence_threshold = confidence_threshold
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self._models: dict[str, Any] = {}
        self._ticks_since_train: dict[str, int] = {}
        self._last_train_metrics: dict[str, dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "ml_alpha"

    @property
    def description(self) -> str:
        return (
            f"GradientBoosting classifier ({self.n_estimators} trees, "
            f"depth {self.max_depth}) with rolling retrain"
        )

    @property
    def required_history(self) -> int:
        return max(80, self.min_train_samples + 30)

    def get_config(self) -> dict[str, Any]:
        return {
            "retrain_every": self.retrain_every,
            "min_train_samples": self.min_train_samples,
            "confidence_threshold": self.confidence_threshold,
            "n_estimators": self.n_estimators,
            "max_depth": self.max_depth,
            "trained_symbols": list(self._models.keys()),
        }

    def export_diagnostics(self) -> dict[str, Any]:
        """Per-symbol sklearn models: feature importances and column order (MCP / API)."""
        symbols: dict[str, Any] = {}
        for sym, (model, cols) in self._models.items():
            imp = model.feature_importances_
            symbols[sym] = {
                "feature_names": list(cols),
                "feature_importances": {
                    c: round(float(v), 6) for c, v in zip(cols, imp, strict=False)
                },
                "top_5_by_importance": [
                    {"feature": str(a), "importance": round(float(b), 6)}
                    for a, b in sorted(
                        zip(cols, imp, strict=False),
                        key=lambda x: x[1],
                        reverse=True,
                    )[:5]
                ],
                "holdout_metrics": self._last_train_metrics.get(sym),
            }
        return {
            "strategy": self.name,
            "config": self.get_config(),
            "feature_definitions": self._feature_cols(),
            "trained_symbols_detail": symbols,
            "methodology": {
                "split": "time_ordered_80_20",
                "holdout": "most_recent_20pct_bars",
                "note": (
                    "Train on earliest 80% of rows, report accuracy / Brier / ROC-AUC "
                    "on the latest 20% (chronological — not i.i.d. CV)."
                ),
            },
        }

    def _feature_cols(self) -> list[str]:
        return [
            "ret_1d", "ret_5d", "ret_10d", "ret_20d",
            "vol_5d", "vol_10d", "vol_20d",
            "rsi_14", "price_to_sma10", "price_to_sma20", "price_to_sma50",
            "sma10_sma20", "macd_norm", "channel_pos",
            "skew_20d", "kurt_20d",
        ]

    def _train(self, sym: str, prices: pd.Series) -> bool:
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score

        features = _build_features(prices)
        features["target"] = (features["close"].shift(-1) > features["close"]).astype(int)
        features = features.dropna()

        cols = self._feature_cols()
        available = [c for c in cols if c in features.columns]
        if len(features) < self.min_train_samples or len(available) < 5:
            return False

        X = features[available].values
        y = features["target"].values

        split = int(len(X) * 0.8)
        if split < 10 or split >= len(X):
            return False
        X_train, y_train = X[:split], y[:split]
        X_val, y_val = X[split:], y[split:]

        if len(np.unique(y_train)) < 2:
            return False

        model = GradientBoostingClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        )
        model.fit(X_train, y_train)

        metrics: dict[str, Any] = {
            "train_rows": int(split),
            "holdout_rows": int(len(y_val)),
        }
        if len(y_val) > 0:
            proba_val = model.predict_proba(X_val)
            pos_col = min(1, proba_val.shape[1] - 1)
            p_up = proba_val[:, pos_col]
            pred = model.predict(X_val)
            metrics["holdout_accuracy"] = round(float(accuracy_score(y_val, pred)), 6)
            metrics["holdout_brier"] = round(float(brier_score_loss(y_val, p_up)), 6)
            if len(np.unique(y_val)) >= 2:
                try:
                    metrics["holdout_roc_auc"] = round(
                        float(roc_auc_score(y_val, p_up)), 6,
                    )
                except ValueError:
                    metrics["holdout_roc_auc"] = None
            else:
                metrics["holdout_roc_auc"] = None
        self._last_train_metrics[sym] = metrics

        self._models[sym] = (model, available)
        self._ticks_since_train[sym] = 0
        logger.info(
            "ML model trained for %s (train=%d holdout=%d brier=%s)",
            sym,
            split,
            len(y_val),
            metrics.get("holdout_brier"),
        )
        return True

    def generate_signals(self, prices: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        for sym in prices.columns:
            series = prices[sym].dropna()
            if len(series) < self.required_history:
                continue

            ticks = self._ticks_since_train.get(sym, self.retrain_every)
            if sym not in self._models or ticks >= self.retrain_every:
                if not self._train(sym, series):
                    continue

            self._ticks_since_train[sym] = ticks + 1
            model, feature_cols = self._models[sym]

            features = _build_features(series)
            features = features.dropna()
            if features.empty:
                continue

            available = [c for c in feature_cols if c in features.columns]
            if len(available) < len(feature_cols):
                continue

            latest = features[available].iloc[[-1]].values
            try:
                proba = model.predict_proba(latest)[0]
            except Exception:
                continue

            prob_up = proba[1] if len(proba) > 1 else proba[0]
            prob_down = 1 - prob_up

            importances = dict(zip(
                feature_cols,
                [round(float(v), 4) for v in model.feature_importances_],
            ))
            top_features = sorted(
                importances.items(), key=lambda x: x[1], reverse=True,
            )[:5]

            if prob_up > self.confidence_threshold:
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.LONG,
                    strength=round(prob_up, 4),
                    strategy_name=self.name,
                    metadata={
                        "prob_up": round(prob_up, 4),
                        "prob_down": round(prob_down, 4),
                        "top_features": dict(top_features),
                        "model_type": "GradientBoosting",
                    },
                ))
            elif prob_down > self.confidence_threshold:
                signals.append(Signal(
                    symbol=sym,
                    direction=SignalDirection.SHORT,
                    strength=round(prob_down, 4),
                    strategy_name=self.name,
                    metadata={
                        "prob_up": round(prob_up, 4),
                        "prob_down": round(prob_down, 4),
                        "top_features": dict(top_features),
                        "model_type": "GradientBoosting",
                    },
                ))

        return signals
