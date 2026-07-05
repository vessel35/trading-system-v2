---
name: decimal-arithmetic-discipline
description: Apply this skill whenever code touches money, position size, price, fees, slippage, funding, or indicator values that drive a trading decision. Operationalizes CLAUDE.md §16 (gate G_CALC).
paths:
  - strategies/implementations/**/*.py
  - validation/recompute/**/*.py
  - configs/**.yaml
  - logs/calc_audit/**/*.jsonl
---

# Decimal Arithmetic Discipline Skill

This skill enforces CLAUDE.md §16 (gate G_CALC). The backtest-developer
agent and the validation-auditor agent both load this skill.

## 1. Native `float` is forbidden — for these values

| Domain | Required type | Why |
|---|---|---|
| Money, account balance, PnL | `nautilus_trader.model.objects.Money` or `decimal.Decimal` | binary float cannot represent 0.1 exactly; PnL summation accumulates error |
| Position size, order quantity | `nautilus_trader.model.objects.Quantity` or `Decimal` | size precision must match the exchange's `step_size` exactly |
| Price | `nautilus_trader.model.objects.Price` or `Decimal` | price must align to `tick_size`; float rounding produces invalid orders |
| Indicator output that **drives a trading decision** | `Decimal` | comparison against thresholds must be exact and reproducible |
| Fee, slippage, funding amounts | `Decimal` | summed across thousands of trades; error compounds |
| Tolerance values in tests | `Decimal` literal as a string | float-as-tolerance defeats the test |

### Permitted `float` cases

- Charting and visualization output only (never round-trip into a decision).
- Statistical metric computation (Sharpe, p-value) — these are statistics
  *over* PnL, not the PnL itself.
- Scientific functions (`numpy.log`, `scipy.stats`) — wrap with Decimal
  conversion at the boundary.

## 2. Construction rules

```python
from decimal import Decimal, getcontext, ROUND_HALF_EVEN

# Always use ROUND_HALF_EVEN (banker's rounding) — IEEE 754 standard
getcontext().rounding = ROUND_HALF_EVEN
getcontext().prec = 28  # 28 significant digits — overkill, deliberately

# ALWAYS construct Decimal from string, NEVER from float
fee_pct = Decimal("0.0004")      # GOOD
fee_pct = Decimal(0.0004)        # BAD: inherits float imprecision
fee_pct = Decimal(str(0.0004))   # OK as last resort, prefer the literal form
```

The rule "Decimal from string only" is enforced by linter in
`scripts/lint_artifact.py` for any file under `strategies/` and
`validation/recompute/`.

## 3. Quantize at the exchange precision

Every price and every quantity must be quantized to the exchange's
`tick_size` and `step_size` before submitting an order. The
NautilusTrader `InstrumentProvider` carries these values.

```python
def round_price(p: Decimal, tick: Decimal) -> Decimal:
    return (p / tick).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN) * tick

def round_qty(q: Decimal, step: Decimal) -> Decimal:
    # Floor toward zero for risk-safe sizing (never up-size unintentionally)
    return (q / step).to_integral_value(rounding="ROUND_FLOOR") * step
```

Note the asymmetry: `round_price` uses banker's rounding (price moves
both ways); `round_qty` floors (we never want to accidentally exceed the
sizing budget).

## 4. Calculation audit log

Every backtest emits one JSONL file:
`logs/calc_audit/H<NNN>_run<RUN_ID>.jsonl`.

Each line is one record:

```json
{
  "ts": "2026-05-15T14:22:08.123456Z",
  "kind": "indicator|fee|pnl|funding",
  "inputs": {"close": "65432.10", "n": "14"},
  "formula": "ATR(n=14) over high, low, close",
  "intermediate": {"tr_mean": "12.345"},
  "output": "12.345",
  "scale": "1e-8"
}
```

**Every numeric value is a JSON string**, never a JSON number. JSON
numbers parse as float in most readers; that defeats the audit.

Producer rule: the line is emitted **before** the value is used
downstream. The validation-auditor reads the JSONL and recomputes each
record using the reference implementation under
`validation/recompute/<kind>.py`.

## 5. Reference implementation contract

Every indicator that influences a trading decision needs a reference
implementation. The reference is Decimal-only, has a unit test, and
lives under `validation/recompute/<indicator>.py`.

```python
# validation/recompute/atr.py
from decimal import Decimal
from typing import Iterable

def true_range(high: Decimal, low: Decimal, prev_close: Decimal) -> Decimal:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))

def atr(highs: Iterable[Decimal], lows: Iterable[Decimal],
        closes: Iterable[Decimal], n: int) -> list[Decimal]:
    """Wilder's smoothing of true range. Decimal-only. Returns list aligned to closes index."""
    trs = []
    out: list[Decimal] = []
    prev_close = None
    for h, l, c in zip(highs, lows, closes):
        if prev_close is None:
            trs.append(h - l)
        else:
            trs.append(true_range(h, l, prev_close))
        prev_close = c
        if len(trs) < n:
            out.append(Decimal("NaN"))
        elif len(trs) == n:
            out.append(sum(trs[-n:]) / Decimal(n))
        else:
            out.append((out[-1] * Decimal(n - 1) + trs[-1]) / Decimal(n))
    return out
```

Every reference function has a unit test under
`tests/recompute/test_<indicator>.py` with at least one fixed-value
case and one property-based case (Hypothesis library).

## 6. Tolerance

| Domain | Tolerance |
|---|---|
| Indicator price scale | `1e-8` |
| Trade PnL | `1e-8` USDT |
| Fee, slippage, funding totals | **exact** (zero tolerance) — these are arithmetic sums, not approximations |

```python
def assert_close(a: Decimal, b: Decimal, tol: Decimal = Decimal("1e-8")) -> None:
    assert abs(a - b) <= tol, f"divergence {a - b} exceeds {tol}"
```

A failing tolerance is a `[FAILURE]` at G_CALC. The auditor records the
divergence and the producer is sent back to fix the reference or the
production code.

## 7. Common pitfalls — automatic FAIL at lint

| Pattern | Why it fails |
|---|---|
| `Decimal(some_float)` | inherits float imprecision into Decimal |
| `pnl + fee_float` | mixes Decimal and float, raises silently in some paths |
| `json.dumps({"price": Decimal(...)})` | defaults to `TypeError`; the wrong fix is `default=float` (destroys precision); the right fix is `default=str` |
| `round(x, 2)` on Decimal | `round` returns float in Python 3.10; use `.quantize(Decimal("0.01"))` |
| `numpy` arithmetic on Decimal arrays | numpy elementwise ops fall back to object dtype with float promotion — produce a Python list comprehension instead |

## 8. JSON serialization

```python
import json
from decimal import Decimal

def decimal_dumps(obj) -> str:
    """Decimal -> string, always, no scientific notation surprises."""
    return json.dumps(obj, default=lambda o: format(o, "f") if isinstance(o, Decimal) else None)
```

`format(o, "f")` avoids `Decimal("1E-8")` becoming `"1E-8"` in JSON. The
output is `"0.00000001"`. The reader uses `Decimal(s)` to reconstruct.

## 9. Acceptance checklist (paste into the PR description)

- [ ] No `float` constants in money / price / size / fee / funding code paths
- [ ] All `Decimal` constructed from string literals
- [ ] `getcontext().rounding = ROUND_HALF_EVEN` set at module init
- [ ] Price rounded with `ROUND_HALF_EVEN` at tick; quantity floored at step
- [ ] Calculation audit log emitted with all numbers as strings
- [ ] Reference implementation present for every decision-driving indicator
- [ ] Unit tests cover fixed-value and property-based cases
- [ ] Tolerance constants are themselves Decimal literals

## Related skills

- `quant-backtest` — the backtest path that consumes these values
- `statistical-validation` — metrics computed *over* PnL
- `python` — language-level decimal / typing conventions
