"""Build the candle series both sides of the pattern comparison are run over.

**Changing anything in this file invalidates every captured TA-Lib signal.** The
signals in `talib_signals.py` are the output of the sixty-one `CDL` functions on
exactly the bars this module produces, so a different series makes them the
answers to a question nobody asked any more. `series_fingerprint()` exists so
that invalidation is detected rather than assumed: the capture records the
fingerprint of the series it read, and the suite refuses signals whose
fingerprint no longer matches. Editing the constants below therefore means
running the generator again, not adjusting a number until a test passes.

Why the series is built the way it is
-------------------------------------

The comparison is worthless if the bars were chosen to suit one of the two rule
sets. So no quantity either standard reasons about is drawn directly. The
generator draws four independent uniform variates per bar and turns them into a
gap, a close, and two wick extensions; body-to-range ratios, shadow multiples,
doji tolerances and trend states are all *consequences* of those draws, never
inputs to them. Nothing here reads a threshold from §2, a period from §3, or a
`TA_SetCandleSettings` value from TA-Lib.

Three properties of the construction matter enough to state, because each one
would otherwise silence a whole family of patterns and make its silence look
like an implementation defect:

Each bar's open is drawn away from the previous close rather than set equal to
it. `tests/indicator_reference/series.py` opens every bar at the previous close,
which is harmless for indicators and fatal here: it makes a gap arithmetically
impossible, and the standard's §1.3 gap is a requirement of roughly a third of
the catalog. Those patterns could then never match on any series, and the
comparison would report a defect that is really an artifact of the input.

The drift alternates between rising, flat, falling, and flat again over long
stretches. §3 judges the prior trend from a ten-period exponential moving
average of the range midpoint, so a series with no sustained direction would
starve the forty-five trend-requiring patterns of one of their two directions.
The stretches are long relative to that period and the cycle is symmetric, so
neither direction is favoured.

Prices are rounded to a fixed tick, the way an exchange feed reports them. Exact
equality between two prices is then possible, which is what §4.1's boundary
strength and §2.6's `Equal` are about. Without a tick every comparison would be
a strict inequality and the boundary cases would never be exercised.

Length is four thousand bars for one reason: rarity. A pattern that needs three
consecutive doji, or a five-bar window with a gap inside it, appears a handful of
times in a few thousand bars and not at all in a few hundred. Length buys those
patterns an opportunity without shaping a single bar in their favour, which is
the only kind of help this file is allowed to give.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from core_lib.types import Candle

BAR_COUNT = 4000
"""Bars in the comparison series.

Long enough that a five-bar pattern with a gap requirement gets a real chance,
short enough that computing all sixty-one patterns over it stays a few seconds.
"""

REGIME_LENGTH = 250
"""Bars per drift regime, sixteen regimes over the series.

Twenty-five times §3's ten-period moving average, so a regime is a trend the
standard's own trend test can see rather than a wobble it smooths away.
"""

PRICE_TICK = 0.01
"""The quantum every reported price is rounded to."""

_START = datetime(2026, 1, 1, tzinfo=UTC)
_BAR = timedelta(hours=1)
_INITIAL_PRICE = 100.0

# A linear congruential generator with the constants ANSI C names. It is written
# out rather than taken from `random` so the series depends on nothing but this
# file: a change to the standard library's generator would otherwise silently
# invalidate every captured signal, and the fingerprint would be the only thing
# left to notice it.
_LCG_MODULUS = 2**31
_LCG_MULTIPLIER = 1103515245
_LCG_INCREMENT = 12345
_LCG_SEED = 20260802

# Per-bar magnitudes, as fractions of price. The gap is deliberately of the same
# order as the bar's own move: smaller and gap patterns would starve, larger and
# the series would stop resembling an hourly feed.
_MOVE_SCALE = 0.004
_GAP_SCALE = 0.002
_WICK_SCALE = 0.004
_DRIFT_SCALE = 0.0006

_DRIFT_CYCLE = (1.0, 0.0, -1.0, 0.0)
"""Rising, flat, falling, flat — a cycle whose mean is zero by construction."""


class _Uniform:
    """Yield the same sequence of variates on every platform and every run."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def next(self) -> float:
        """Return the next variate in [0, 1)."""
        self._state = (_LCG_MULTIPLIER * self._state + _LCG_INCREMENT) % _LCG_MODULUS
        return self._state / _LCG_MODULUS

    def centered(self) -> float:
        """Return the next variate mapped onto [-1, 1)."""
        return self.next() * 2.0 - 1.0


def _to_tick(price: float) -> float:
    """Round a price to the reported tick."""
    return round(price / PRICE_TICK) * PRICE_TICK


def reference_candles(count: int = BAR_COUNT) -> list[Candle]:
    """Build the exact series the captured TA-Lib signals were produced from."""

    draw = _Uniform(_LCG_SEED)
    candles: list[Candle] = []
    previous_close = _INITIAL_PRICE
    for index in range(count):
        drift = _DRIFT_SCALE * _DRIFT_CYCLE[(index // REGIME_LENGTH) % len(_DRIFT_CYCLE)]
        open_price = previous_close * (1.0 + _GAP_SCALE * draw.centered())
        close = open_price * (1.0 + drift + _MOVE_SCALE * draw.centered())
        high = max(open_price, close) * (1.0 + _WICK_SCALE * draw.next())
        low = min(open_price, close) * (1.0 - _WICK_SCALE * draw.next())

        open_price, close = _to_tick(open_price), _to_tick(close)
        # Rounding can push a wick inside the body it was meant to enclose, so the
        # enclosing relation is restored after rounding rather than assumed from it.
        high = max(_to_tick(high), open_price, close)
        low = min(_to_tick(low), open_price, close)

        open_time = _START + index * _BAR
        candles.append(
            Candle(
                symbol="BTC/USDT:USDT",
                exchange="binance",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + _BAR,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=100.0 + (index % 13) * 5.0,
                quote_volume=None,
                trade_count=None,
            )
        )
        previous_close = close
    return candles


def series_fingerprint(candles: Sequence[Candle] | None = None) -> str:
    """Return a digest of the open, high, low, and close of every bar.

    Only the four prices go in. Nothing in a `CDL` function or in §7 reads the
    symbol, the timestamps, or the volume, so including them would make the
    fingerprint reject a series that is in fact the one the signals came from.
    """
    subject = reference_candles() if candles is None else candles
    digest = hashlib.sha256()
    for candle in subject:
        digest.update(
            f"{candle.open:.2f},{candle.high:.2f},{candle.low:.2f},{candle.close:.2f};".encode()
        )
    return digest.hexdigest()
