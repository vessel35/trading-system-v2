"""Build the candle series both sides of the pattern comparison are run over.

**Changing anything in this file invalidates every captured TA-Lib signal.** The signals in
`talib_signals.py` are the output of the sixty-one `CDL` functions on exactly the bars this
module produces, so a different series makes them the answers to a question nobody asked
any more. `series_fingerprint()` exists so that invalidation is detected rather than
assumed: the capture records the fingerprint of every series it read, and the suite refuses
signals whose fingerprint no longer matches. Editing the constants below therefore means
running the generator again, not adjusting a number until a test passes.

Why there is more than one series
---------------------------------

One series carries one market. The first version of this file built four thousand hourly
bars of a market that drifted up, flat, down, and flat again, and comparing against it left
eleven of the sixty-one patterns with no evidence at all: neither side matched them once,
so the comparison said nothing about them. That is what a single market does. Where gaps
are rare the eighteen gap patterns sleep; where every bar carries a full body the doji
family sleeps; where the drift never persists the forty-five trend-gated patterns are
judged against a direction that means little.

So the comparison now runs over a bundle of series, each one a different **market
character**. `REGIMES` below is that bundle, and every parameter in it is a statement about
the market: how far a bar travels from its open, how far the next bar opens away from the
previous close, how far the extremes run past the body, and whether the drift persists or
turns over. The first entry is the original four thousand bars, unchanged down to its seed,
so the values already captured and the silences already investigated against it stay valid.

The line this file may not cross
--------------------------------

**No regime may be shaped to make a pattern match.** A series built until a rule fires is a
series that proves the rule fires on it, which is worth nothing. The rule here is that a
regime is defined in the language of the market and nothing else: not one parameter was
chosen by reading a §2 threshold, a §3 period, a §7 rule, or a `TA_SetCandleSettings`
value, and none was adjusted after seeing what it made match. The seeds make the same
promise mechanically — every regime after the first draws its seed from its own name, so
there is no seed to shop for.

The same applies to coverage. How many patterns end up with evidence is a *result* to be
reported, never a target to build toward.

What each regime is
-------------------

`mixed_hourly` is the original series: an hourly market whose drift alternates between
rising, flat, falling, and flat again over long stretches, with a gap of half the size of a
bar's own move. It is kept exactly as it was.

`strong_uptrend` and `strong_downtrend` are markets whose drift never turns. Over the
series the price moves by about an order of magnitude, which is what a sustained advance or
decline looks like, and the two are mirror images across the same band of prices. §3 judges
the trend from the pattern's first bar against a ten-period average of the same quantity,
which is a fast test rather than a strong one, so no regime switches a trend gate off
outright; a drift that never turns leaves the first bar above its average far more often
than below it, and the mirrored pair does the same in the other direction.

`choppy_reversals` turns the drift over every four bars, well inside the ten-period average
§3 reads, so the trend behind any given shape is whatever the last few bars happened to do
rather than a direction the market committed to. It is worth saying what this does *not*
do: §3's test is fast enough that no regime makes it report one direction rarely. The
trending pair splits its judgments about 85 to 15, and every other regime — this one
included — sits near even. What separates them is persistence, not balance.

`frequent_gaps` is a market that is closed more than it is open and where the news arrives
while it is closed: the move between one close and the next open is twice the size of the
bar's own body and four times the reach of its shadows. A whole bar therefore often sits
clear of the previous bar's high-low range, which is the widest of the three gaps §1.3
distinguishes, and the narrower body gap is commoner still. Its bars are daily.

`quiet_small_bodies` is a listless market whose bars span a handful of ticks. The body is a
few ticks and the range not much more, so the tick the price is reported on stops being
invisible: bodies round onto zero, opens round onto previous closes, and the equality and
tolerance cases §2 defines stop being unreachable curiosities.

`wide_swings` is the opposite market, one that travels a long way inside the bar and closes
near where it opened, so the extremes run several times the body. That is what a session of
failed breakouts looks like from the outside.

Three properties shared by every regime
---------------------------------------

Each bar's open is drawn away from the previous close rather than set equal to it.
`tests/indicator_reference/series.py` opens every bar at the previous close, which is
harmless for indicators and fatal here: it makes a gap arithmetically impossible, and the
standard's §1.3 gap is a requirement of roughly a third of the catalog. Those patterns
could then never match on any series, and the comparison would report a defect that is
really an artifact of the input.

Nothing either standard reasons about is drawn directly. Four independent uniform variates
per bar become a gap, a close, and two extensions; body-to-range ratios, shadow multiples,
doji tolerances and trend states are all *consequences* of those draws, never inputs to
them.

Prices are rounded to a fixed tick, the way an exchange feed reports them. Exact equality
between two prices is then possible, which is what §4.1's boundary strength and §2.6's
`Equal` are about. Without a tick every comparison would be a strict inequality and the
boundary cases would never be exercised.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

from core_lib.types import Candle

PRICE_TICK = 0.01
"""The quantum every reported price is rounded to, in every regime.

An exchange's tick does not change because the market went quiet, so this is shared. What
changes between regimes is the price the tick is a fraction of, which is why the two trend
regimes are placed at opposite ends of the same band rather than both starting at par.
"""

_START = datetime(2026, 1, 1, tzinfo=UTC)

# A linear congruential generator with the constants ANSI C names. It is written out rather
# than taken from `random` so the series depend on nothing but this file: a change to the
# standard library's generator would otherwise silently invalidate every captured signal,
# and the fingerprint would be the only thing left to notice it.
_LCG_MODULUS = 2**31
_LCG_MULTIPLIER = 1103515245
_LCG_INCREMENT = 12345

_TIMEFRAME_DURATIONS: Mapping[str, timedelta] = MappingProxyType(
    {"1h": timedelta(hours=1), "1d": timedelta(days=1)}
)

_HISTORICAL_SEEDS: Mapping[str, int] = MappingProxyType({"mixed_hourly": 20260802})
"""Seeds that predate the rule below and are kept so a capture stays valid.

`mixed_hourly` was captured with this seed and its silences were investigated against those
exact bars. Re-deriving it from its name would move every bar and throw that work away for
no gain.
"""


def _seed_for(name: str) -> int:
    """Return the regime's seed, derived from its own name unless history fixes it.

    Deriving the seed from the name is what makes "no seed was shopped for" a checkable
    statement rather than a promise. Changing a regime's seed means changing what the
    regime is called, which is not something anybody does quietly to get a pattern to fire.
    """
    if name in _HISTORICAL_SEEDS:
        return _HISTORICAL_SEEDS[name]
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % _LCG_MODULUS


@dataclass(frozen=True, slots=True)
class Regime:
    """One market's character, expressed as the quantities a bar is drawn from."""

    name: str

    character: str
    """What market this is, in the market's own language.

    It may not name a pattern, a §2 threshold, or a `CDL` function. A regime described by
    what it makes match is a regime that was built to make it match.
    """

    timeframe: str
    bar_count: int

    initial_price: float
    """Where the series starts.

    It matters because `PRICE_TICK` is absolute: the same market at four hundred and at
    thirty is quantized differently, and the trending regimes are placed so that neither
    ends up far outside the band the others live in.
    """

    drift_cycle: tuple[float, ...]
    """The multipliers `drift_scale` cycles through, one entry per stretch."""

    stretch: int
    """Bars per entry of `drift_cycle`.

    Long against §3's ten-period average means a drift the trend test can see; short
    against it means a direction that has turned over before the average notices.
    """

    drift_scale: float
    """The per-bar drift, as a fraction of price, at a cycle entry of one."""

    move_scale: float
    """How far the close travels from the open, as a fraction of price.

    This is what a bar's body is made of, before the tick rounds it.
    """

    gap_scale: float
    """How far the next bar opens away from this bar's close, as a fraction of price."""

    wick_scale: float
    """How far the extremes run past the body, as a fraction of price."""

    @property
    def seed(self) -> int:
        """Return the seed this regime is drawn with."""
        return _seed_for(self.name)

    @property
    def bar_duration(self) -> timedelta:
        """Return one bar's length, which `Candle` validates against the timeframe."""
        return _TIMEFRAME_DURATIONS[self.timeframe]


REGIMES: tuple[Regime, ...] = (
    Regime(
        name="mixed_hourly",
        character=(
            "An hourly market with no settled direction: it drifts up for a long stretch, "
            "goes nowhere, drifts down for as long, and goes nowhere again. A bar opens "
            "away from the previous close by about half of what it then travels, and its "
            "extremes reach past the body by about as much as the body itself."
        ),
        timeframe="1h",
        bar_count=4000,
        initial_price=100.0,
        drift_cycle=(1.0, 0.0, -1.0, 0.0),
        stretch=250,
        drift_scale=0.0006,
        move_scale=0.004,
        gap_scale=0.002,
        wick_scale=0.004,
    ),
    Regime(
        name="strong_uptrend",
        character=(
            "A market in a sustained advance that never gives the trend back. Every bar "
            "carries an upward drift of about a fifth of what it travels on its own, so "
            "the advance is visible over ten bars and still leaves room for down bars, and "
            "the price ends the series about an order of magnitude above where it began."
        ),
        timeframe="1h",
        bar_count=3000,
        initial_price=30.0,
        drift_cycle=(1.0,),
        stretch=3000,
        drift_scale=0.0008,
        move_scale=0.004,
        gap_scale=0.002,
        wick_scale=0.004,
    ),
    Regime(
        name="strong_downtrend",
        character=(
            "The mirror of the advance, over the same band of prices: a decline of the "
            "same per-bar size that never turns, beginning where the advance ends and "
            "ending where it began. Running the two together means neither direction is "
            "the one that was only ever seen in a market moving the other way."
        ),
        timeframe="1h",
        bar_count=3000,
        initial_price=330.0,
        drift_cycle=(-1.0,),
        stretch=3000,
        drift_scale=0.0008,
        move_scale=0.004,
        gap_scale=0.002,
        wick_scale=0.004,
    ),
    Regime(
        name="choppy_reversals",
        character=(
            "A market that changes its mind every four bars. The drift is three times the "
            "size of the drift in the trending regimes but it turns over long before a "
            "direction has had time to establish itself, so a shape arrives with whatever "
            "the last few bars happened to leave behind rather than with a trend."
        ),
        timeframe="1h",
        bar_count=3000,
        initial_price=100.0,
        drift_cycle=(1.0, -1.0),
        stretch=4,
        drift_scale=0.0025,
        move_scale=0.004,
        gap_scale=0.002,
        wick_scale=0.004,
    ),
    Regime(
        name="frequent_gaps",
        character=(
            "A daily market that is closed far more than it is open, and whose news "
            "arrives while it is closed. The move from one close to the next open is twice "
            "the size of the session's own body and four times the reach of its extremes, "
            "so a whole bar often sits clear of the previous bar's high-low range. The "
            "drift alternates over stretches of sixty bars, long enough for a direction to "
            "establish itself in both signs before it turns."
        ),
        timeframe="1d",
        bar_count=3000,
        initial_price=100.0,
        drift_cycle=(1.0, 0.0, -1.0, 0.0),
        stretch=60,
        drift_scale=0.0008,
        move_scale=0.003,
        gap_scale=0.006,
        wick_scale=0.0015,
    ),
    Regime(
        name="quiet_small_bodies",
        character=(
            "A listless market whose bars span a handful of ticks. The close ends within "
            "about four ticks of the open and the extremes add another six, so the tick "
            "the feed reports on is no longer invisible: bodies round onto zero, and a bar "
            "opens two ticks from the previous close rather than a hundred. The drift is "
            "small enough that the market goes nowhere over the whole series."
        ),
        timeframe="1h",
        bar_count=3000,
        initial_price=100.0,
        drift_cycle=(1.0, 0.0, -1.0, 0.0),
        stretch=150,
        drift_scale=0.00008,
        move_scale=0.0004,
        gap_scale=0.0002,
        wick_scale=0.0006,
    ),
    Regime(
        name="wide_swings",
        character=(
            "A market that travels a long way inside the bar and closes near where it "
            "opened. The extremes run four times as far past the body as the body itself "
            "covers, which is what a session of failed breakouts leaves behind, and the "
            "drift alternates over stretches of a hundred bars."
        ),
        timeframe="1h",
        bar_count=3000,
        initial_price=100.0,
        drift_cycle=(1.0, 0.0, -1.0, 0.0),
        stretch=100,
        drift_scale=0.001,
        move_scale=0.004,
        gap_scale=0.002,
        wick_scale=0.016,
    ),
)
"""Every market the comparison is run over.

Seven regimes, of which the first is the original series. The order is the order they are
reported in and nothing depends on it.
"""

REGIMES_BY_NAME: Mapping[str, Regime] = MappingProxyType(
    {regime.name: regime for regime in REGIMES}
)

REGIME_NAMES: tuple[str, ...] = tuple(regime.name for regime in REGIMES)

TOTAL_BAR_COUNT: int = sum(regime.bar_count for regime in REGIMES)


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


def build_candles(regime: Regime) -> list[Candle]:
    """Build one regime's bars.

    The four draws happen in a fixed order — the gap, the close, the upper extension, the
    lower extension — because the order is part of what the fingerprint pins. Reordering
    them would produce a different market from the same parameters and quietly invalidate
    every captured signal for the regime.
    """

    draw = _Uniform(regime.seed)
    bar = regime.bar_duration
    candles: list[Candle] = []
    previous_close = regime.initial_price
    for index in range(regime.bar_count):
        cycle_position = (index // regime.stretch) % len(regime.drift_cycle)
        drift = regime.drift_scale * regime.drift_cycle[cycle_position]
        open_price = previous_close * (1.0 + regime.gap_scale * draw.centered())
        close = open_price * (1.0 + drift + regime.move_scale * draw.centered())
        high = max(open_price, close) * (1.0 + regime.wick_scale * draw.next())
        low = min(open_price, close) * (1.0 - regime.wick_scale * draw.next())

        open_price, close = _to_tick(open_price), _to_tick(close)
        # Rounding can push an extreme inside the body it was meant to enclose, so the
        # enclosing relation is restored after rounding rather than assumed from it.
        high = max(_to_tick(high), open_price, close)
        low = min(_to_tick(low), open_price, close)

        open_time = _START + index * bar
        candles.append(
            Candle(
                symbol="BTC/USDT:USDT",
                exchange="binance",
                timeframe=regime.timeframe,
                open_time=open_time,
                close_time=open_time + bar,
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


def candles_for(regime_name: str) -> list[Candle]:
    """Return one regime's bars, built once and reused.

    Twenty-one thousand validated candles across the bundle is the second most expensive
    thing in this package after computing sixty-one patterns over them, and every caller
    wants the same bars.
    """
    if regime_name not in _CANDLE_CACHE:
        _CANDLE_CACHE[regime_name] = build_candles(REGIMES_BY_NAME[regime_name])
    return _CANDLE_CACHE[regime_name]


_CANDLE_CACHE: dict[str, list[Candle]] = {}


def series_fingerprint(candles: Sequence[Candle]) -> str:
    """Return a digest of the open, high, low, and close of every bar.

    Only the four prices go in. Nothing in a `CDL` function or in §7 reads the symbol, the
    timestamps, or the volume, so including them would make the fingerprint reject a series
    that is in fact the one the signals came from.
    """
    digest = hashlib.sha256()
    for candle in candles:
        digest.update(
            f"{candle.open:.2f},{candle.high:.2f},{candle.low:.2f},{candle.close:.2f};".encode()
        )
    return digest.hexdigest()


def fingerprints() -> dict[str, str]:
    """Return every regime's fingerprint, keyed by regime name."""
    return {name: series_fingerprint(candles_for(name)) for name in REGIME_NAMES}
