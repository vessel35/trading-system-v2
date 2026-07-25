---
name: ml-strategy
description: Apply this skill when designing or implementing a machine-learning predictive trading strategy on OHLCV data — feature engineering from price/volume, walk-forward training to avoid look-ahead leakage, label construction, model choice (RandomForest / GradientBoosting / LogisticRegression), and mapping model output to a position signal. Use it for the feature/signal layer that feeds the NautilusTrader backtest; it does not replace the engine.
paths:
  - strategies/implementations/**/*.py
  - strategies/rules/**/*.md
---

# ML Strategy Skill

A disciplined template for ML-predictive signals on OHLCV bars. The hard part of ML for
trading is not the model — it is avoiding leakage and overfitting. This skill is the
**feature and signal layer**: pure functions that produce a position signal which the
NautilusTrader strategy in `quant-backtest` then trades (next-bar-open fill, Decimal
sizing). It does not run live and does not bypass the engine.

Feature math (returns, z-scores, indicator values used only to *decide*) may be `float`.
The moment a model output becomes a position size or order, it crosses into
`decimal-arithmetic-discipline`.

## 1. The leakage discipline (most important)

Every guard here maps to a `quant-backtest` §2 REJECT trigger. Get these wrong and the
backtest is fantasy.

1. **Walk-forward only.** Train on history, predict forward, roll. k-fold shuffle CV is
   forbidden on time series (see `statistical-validation` §3).
2. **Fit the scaler on the training window only.** Fitting `StandardScaler` on all data
   leaks test-set distribution into training.
3. **Features use data up to bar t-1; the label is the forward return.** Building a feature
   from bar t's close and predicting bar t's move is leakage.
4. **Sanitize inf/NaN** before they reach the model; never `bfill` a feature.

## 2. Feature engineering (pure function)

```python
import numpy as np
import pandas as pd

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """No I/O, no global state, no future access. Deterministic given df.
    All features guarded against divide-by-zero and sanitized to NaN (never inf)."""
    c, v = df["close"], df["volume"]
    ret = c.pct_change()
    f = pd.DataFrame(index=df.index)
    f["f_ret_5"]    = c.pct_change(5)
    f["f_ret_20"]   = c.pct_change(20)
    f["f_vol_20"]   = ret.rolling(20).std()
    f["f_ma_ratio"] = c / c.rolling(20).mean()
    f["f_vol_rat"]  = v / v.rolling(20).mean()

    delta = c.diff()                      # RSI(14), guard loss==0
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    f["f_rsi_14"] = 100 - 100 / (1 + rs)

    ma20, sd20 = c.rolling(20).mean(), c.rolling(20).std()   # Bollinger position
    width = ((ma20 + 2*sd20) - (ma20 - 2*sd20)).replace(0, np.nan)
    f["f_bb_pos"] = (c - (ma20 - 2*sd20)) / width
    f["f_skew_20"] = ret.rolling(20).skew()

    return f.replace([np.inf, -np.inf], np.nan)   # NaN handled by walk-forward
```

This is exactly the `quant-backtest` §8 pure-function contract; a NautilusTrader
`Indicator` production path still needs this reference under `validation/recompute/`.

## 3. Label construction

```python
# Positive class = next-N-bar return > 0. shift(-N) is the LABEL (allowed); never a feature.
labels = (df["close"].pct_change(N).shift(-N) > 0).astype(int)
```

The forward shift is legitimate on the label only. It must never appear in `build_features`.

## 4. Walk-forward training

```python
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

def walk_forward_predict(features, labels, min_train=252, retrain_freq=20,
                         model_type="random_forest", window="expanding", sliding=504):
    """Returns a signal Series in [-1, 1], no NaN. Trains only on past data."""
    pred = pd.Series(0.0, index=features.index)
    model = scaler = None
    for i in range(min_train, len(features)):
        if model is None or (i - min_train) % retrain_freq == 0:
            start = max(0, i - sliding) if window == "sliding" else 0
            X, y = features.iloc[start:i].values, labels.iloc[start:i].values
            ok = ~(np.isnan(X).any(axis=1) | np.isnan(y))
            X, y = X[ok], y[ok]
            if len(X) < 50:
                continue
            scaler = StandardScaler().fit(X)        # fit on TRAIN only
            X = scaler.transform(X)
            model = _make_model(model_type).fit(X, y)
        xt = features.iloc[i:i+1].values
        if np.isnan(xt).any():
            continue
        xt = scaler.transform(xt)
        prob = model.predict_proba(xt)[0, 1] if hasattr(model, "predict_proba") else None
        pred.iloc[i] = (prob * 2 - 1) if prob is not None else float(model.predict(xt)[0])
    return pred.fillna(0.0).clip(-1.0, 1.0)
```

`_make_model` returns `RandomForestClassifier(n_estimators=100, max_depth=5)`,
`GradientBoostingClassifier(max_depth=3, learning_rate=0.05)`, or
`LogisticRegression(C=1.0)` — all with a pinned `random_state`.

## 5. Model choice

| Model | Strength | Weakness | Use when |
|---|---|---|---|
| RandomForest | hard to overfit, gives feature importance | weaker on trend features | default first choice |
| GradientBoosting | high accuracy, nonlinear | overfits easily, slow | enough data + tuning experience |
| LogisticRegression | fast, interpretable, robust | linear only | fast baseline, few features |

## 6. Signal → position

The `[-1, 1]` output is a target position fraction: `+1` full long, `-1` full short, `0`
flat. The NautilusTrader strategy converts that to a Decimal order size under the risk
policy — the ML layer never computes notional itself.

## 7. Overfitting guards

- Keep `max_depth` 3–5 and feature count < 15.
- Class imbalance in trending regimes (up:down 7:3) biases the model — use
  `class_weight="balanced"`.
- Run the `statistical-validation` shuffle ablation: shuffle the labels and confirm the
  Sharpe collapses. If a model "predicts" shuffled labels, it is leaking.
- Report walk-forward per-fold metrics, not a single in-sample fit.

## Acceptance checklist

- [ ] Walk-forward only; no shuffled k-fold
- [ ] Scaler fit on the training window only
- [ ] Features use data ≤ t-1; forward shift appears on the label only
- [ ] inf/NaN sanitized; no `bfill` on features
- [ ] Shuffle ablation passes (edge dies on shuffled labels)
- [ ] Signal→size conversion is Decimal in the strategy, not float in the ML layer

## Related skills

- `quant-backtest` — the engine, anti-lookahead REJECT triggers, pure-function contract
- `statistical-validation` — walk-forward CV, shuffle ablation, overfitting checks
- `decimal-arithmetic-discipline` — Decimal sizing once the signal becomes an order
- `python` — language conventions

---
*Adapted from HKUDS/Vibe-Trading (`ml-strategy`, MIT). See `skills/ATTRIBUTIONS.md`.*
