"""Check indicator values against an outside implementation, not against ourselves.

The parity tests prove our two execution paths agree, and the relation tests prove
each indicator satisfies a property its standard section states separately. Neither
can catch a formula we transcribed wrongly in both paths. The calculation standard
carries no worked numbers of its own (its §12 defers them), so the values below come
from **TA-Lib 0.7.1**, which §13 of the standard names as a cross-check target.

The numbers were produced once, offline, in a throwaway environment and frozen here.
Nothing in this repository depends on TA-Lib at run time or in continuous integration;
regenerating them needs that environment again, and the generator is described in
`docs/roadmap-stage-3-0-plan.md`.

TA-Lib is a comparison, never a source. Where a value disagrees, the standard decides
who is wrong, and the two documented disagreements below are seed-window conventions
the standard itself describes rather than errors in either implementation.
"""

import math
from datetime import UTC, datetime, timedelta

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.types import Candle

SAMPLE_INDICES = (100, 200, 299)

# TA-Lib 0.7.1 over the series `reference_candles` builds below.
REFERENCE: dict[str, dict[int, float]] = {
    "EMA(period=9)": {100: 114.54475915444709, 200: 104.15248782563998, 299: 139.881793061695},
    "EMA(period=21)": {100: 118.4661916884445, 200: 101.73018752590491, 299: 130.8116157709897},
    "EMA(period=55)": {100: 119.00040346526784, 200: 107.48356798999689, 299: 120.93480737137257},
    "EMA(period=200)": {200: 114.62267045315066, 299: 116.82135764947657},
    "RSI(period=14)": {100: 39.03775391018262, 200: 68.81760894074445, 299: 86.16456410411202},
    "DEMA(period=21)": {100: 115.60911921449878, 200: 99.04014813313854, 299: 142.38341794759424},
    "CCI(period=20)": {100: -59.78940846427027, 200: 168.67297510556497, 299: 89.17019608473291},
    "A/D Line": {100: 612.8055609726664, 200: 1060.0240840685929, 299: 2281.663413045828},
    "Volume SMA(period=20)": {100: 130.0, 200: 126.25, 299: 133.75},
    "Bollinger Bands(multiplier=2.0,period=20).middle": {
        100: 122.36709457641125,
        200: 94.40787360648436,
        299: 127.34389233173165,
    },
    "Bollinger Bands(multiplier=2.0,period=20).upper": {
        100: 144.12910126270955,
        200: 114.22091638155808,
        299: 155.70673588042882,
    },
    "Bollinger Bands(multiplier=2.0,period=20).lower": {
        100: 100.60508789011293,
        200: 74.59483083141063,
        299: 98.98104878303448,
    },
    "Stochastic(period=14,smooth_period=3).percent_k": {
        100: 22.922432270572614,
        200: 94.41021271624996,
        299: 92.4036997995627,
    },
    "Stochastic(period=14,smooth_period=3).percent_d": {
        100: 16.81693187062552,
        200: 94.98993171268778,
        299: 94.5198296360486,
    },
    # Derived from TA-Lib's own bands with the §3.10 formulas, since TA-Lib
    # returns the three bands only.
    "Bollinger Bands(multiplier=2.0,period=20).percent_b": {
        100: 0.3115115882700029,
        200: 1.0428100055449034,
        299: 0.792549081776074,
    },
    "Bollinger Bands(multiplier=2.0,period=20).bandwidth": {
        100: 0.355683964902986,
        200: 0.4197328468102024,
        299: 0.4454527504909585,
    },
    # Tulip Indicators 0.4.0, also named by §13. TA-Lib has no Awesome Oscillator.
    "Awesome Oscillator(fast_period=5,slow_period=34)": {
        100: -11.999670053215588,
        200: 0.5021993216117951,
        299: 22.51620241873372,
    },
    "TEMA(period=21)": {
        100: 110.5316275392987,
        200: 103.44342539321069,
        299: 147.90149272889016,
    },
    # TA-Lib's PPO takes a moving-average type; §2.5 uses EMA, so matype=1.
    "PPO(fast_period=12,signal_period=9,slow_period=26).ppo": {
        100: -2.5366845796303528,
        200: -0.2650808063722667,
        299: 7.017926029894158,
    },
    "PPO(fast_period=12,signal_period=9,slow_period=26).signal": {
        100: -1.247947717943005,
        200: -4.3558678969393965,
        299: 5.97573734406127,
    },
    "PPO(fast_period=12,signal_period=9,slow_period=26).histogram": {
        100: -1.2887368616873478,
        200: 4.0907870905671295,
        299: 1.0421886858328886,
    },
    # ta 0.11.0 ChaikinMoneyFlowIndicator.
    "CMF(period=20)": {
        100: -0.18378324771896384,
        200: 0.1184521618242292,
        299: 0.3089552759865531,
    },
    "KAMA(period=10)": {
        100: 112.70229470734732,
        200: 110.77951322216872,
        299: 143.8303533700434,
    },
    "TRIX(period=15)": {
        100: -0.13458503111154485,
        200: -0.7196595662381178,
        299: 0.9286485247771648,
    },
    "Williams %R(period=14)": {
        100: -77.07756772942739,
        200: -5.589787283750039,
        299: -7.596300200437285,
    },
    "Ultimate Oscillator(long_period=28,medium_period=14,short_period=7)": {
        100: 50.227904778901134,
        200: 70.38564770040983,
        299: 64.86926324831096,
    },
    "Aroon(period=25).down": {100: 76.0, 200: 56.0, 299: 32.0},
    "Aroon(period=25).up": {100: 20.0, 200: 0.0, 299: 100.0},
    "Aroon(period=25).oscillator": {100: -56.0, 200: -56.0, 299: 68.0},
    "Parabolic SAR(maximum=0.2,step=0.02)": {
        100: 108.96711637478809,
        200: 95.11455805836829,
        299: 139.52708817671194,
    },
    # Tulip 0.4.0. TA-Lib smooths this one the way it smooths RSI, while §2.8
    # says explicitly that the sums stay unsmoothed, which is what Tulip does.
    "CMO(period=14)": {
        100: -72.26488188636644,
        200: 91.7609789744222,
        299: 96.33366898993499,
    },
    # TA-Lib's OBV starts the accumulation at the first candle's volume; §4.1
    # defines only the recursion, so the two differ by that constant. The
    # reference below has the offset removed, which still checks every step.
    "OBV": {100: 35.0, 200: 195.0, 299: 1740.0},
    # ta 0.11.0 KSTIndicator with the §2.24 parameter set.
    "KST.kst": {
        100: -15.584451285377055,
        200: -127.95894551008244,
        299: 259.51840423440854,
    },
    "KST.signal": {
        100: 75.413494699978,
        200: -228.39291569173233,
        299: 198.36969701978893,
    },
}

# Registered outputs that no available outside implementation covers. Listing them
# keeps the gap visible instead of letting it hide inside a passing suite.
UNCOMPARED: dict[str, str] = {
    "Accelerator Oscillator(fast_period=5,slow_period=34,smooth_period=5)": (
        "None of TA-Lib, Tulip, or ta implements it. Its inputs are covered: the "
        "Awesome Oscillator it subtracts from is compared against Tulip, and the "
        "rolling average it subtracts is a compared primitive."
    ),
    "SMI(long_period=25,period=13,short_period=13,signal_period=3).smi": (
        "None of the three implements the Stochastic Momentum Index, and §2.27 "
        "notes that platforms disagree on its parameters, so even a third-party "
        "value would need its parameter set restated before it could be compared."
    ),
    "SMI(long_period=25,period=13,short_period=13,signal_period=3).signal": (
        "Smoothing of an uncompared series; it inherits the gap above."
    ),
    "Fisher Transform(period=9).fisher": (
        "Tulip has a Fisher Transform, but its values drift further from ours the "
        "longer the series runs (2e-5, then 1e-3, then 7e-1), which is a different "
        "recursion rather than a different seed. §2.14 writes the smoothing and the "
        "clamp we implement, so the standard decides and the outside value is not "
        "usable as a reference here."
    ),
    "Fisher Transform(period=9).signal": ("The delayed value of an uncompared series."),
    "Elder Ray(period=13).bull_power": (
        "No available implementation. §9.3 subtracts a smoothed close from each "
        "extreme, and that smoothed close is the compared EMA."
    ),
    "Elder Ray(period=13).bear_power": ("As above, with the low instead of the high."),
    "Coppock Curve(long_period=14,short_period=11,smooth_period=10)": (
        "No available implementation. §2.25 is a weighted average of two rates of "
        "change, and both parts are compared primitives."
    ),
}

# Two series start from a different seed window than TA-Lib uses, so they converge
# instead of matching from the first value.
#
# ATR: §0.6 defines the first True Range as `H_0 - L_0` because there is no previous
# close, and §3.1 smooths from there. TA-Lib skips that first bar. The seeds differ,
# and Wilder smoothing forgets its seed geometrically.
#
# MACD: §2.4 subtracts two EMAs, each seeded by §0.3 at its own period. TA-Lib starts
# both averages together at the slow period instead, so its fast average has a shorter
# recursion behind it at the crossover point.
#
# Neither is a disagreement about the formula, and the gap below shows it closing.
# TSI joins them for the same reason: the `ta` library seeds its averages from the
# first observation, while §0.3 seeds from the period's simple average.
#
# Each entry carries the gap allowed at each sample point, loosest early and
# effectively closed at the end. A gap that fails to shrink is a real disagreement.
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {
    "ATR(period=14)": (
        {100: 5.158327444974086, 200: 6.200936691650489, 299: 5.280931651521358},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    "MACD(fast_period=12,signal_period=9,slow_period=26).macd": (
        {100: -3.0164352183961114, 200: -0.27195274827619187, 299: 8.999784744708393},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    "MACD(fast_period=12,signal_period=9,slow_period=26).signal": (
        {100: -1.466565769969698, 200: -4.423246005049017, 299: 7.432807556915248},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    "MACD(fast_period=12,signal_period=9,slow_period=26).histogram": (
        {100: -1.5498694484264135, 200: 4.151293256772825, 299: 1.566977187793145},
        {100: 1e-3, 200: 1e-6, 299: 1e-8},
    ),
    # ta 0.11.0; TA-Lib has no True Strength Index.
    "TSI(long_period=25,short_period=13)": (
        {100: -20.993702022418233, 200: -2.993467178933585, 299: 67.24009457384477},
        {100: 4e-1, 200: 1e-4, 299: 1e-7},
    ),
    # TA-Lib's ADOSC inherits its ATR-style seeding difference through the A/D
    # averages, so this one converges as well.
    "Chaikin Oscillator(fast_period=3,slow_period=10)": (
        {100: 0.7392424925909609, 200: 167.5528602118775, 299: 135.60824398604382},
        {100: 1e-5, 200: 1e-9, 299: 1e-9},
    ),
    "DMI(period=14).plus_di": (
        {100: 13.156990718429295, 200: 30.157413246696365, 299: 28.562937269215965},
        {100: 1e-2, 200: 1e-5, 299: 1e-8},
    ),
    "DMI(period=14).minus_di": (
        {100: 20.812833752708965, 200: 13.786118423716923, 299: 5.048650216175285},
        {100: 1e-2, 200: 1e-5, 299: 1e-8},
    ),
    "DMI(period=14).adx": (
        {100: 34.80316386849876, 200: 39.48336090910632, 299: 50.09187506981947},
        {100: 1e-1, 200: 1e-3, 299: 1e-6},
    ),
    # ADXR averages today's ADX with one from a period ago, so it carries the
    # seed difference twice and settles the slowest of the four.
    "DMI(period=14).adxr": (
        {100: 39.71081558037664, 200: 43.08908778158345, 299: 35.80714657054307},
        {100: 2.0, 200: 1.5, 299: 1.0},
    ),
    "Force Index(period=13)": (
        {100: -40.44860100473615, 200: 283.50551116115287, 299: 166.16610511712776},
        {100: 1e-3, 200: 1e-9, 299: 1e-9},
    ),
    "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14).percent_k": (
        {100: 23.584229569176472, 200: 100.0, 299: 96.49913220407035},
        {100: 1e-1, 200: 1e-6, 299: 1e-6},
    ),
    "Stochastic RSI(rsi_period=14,smooth_d=3,smooth_k=3,stochastic_period=14).percent_d": (
        {100: 14.84804215780516, 200: 100.0, 299: 98.76676684819944},
        {100: 1e-1, 200: 1e-6, 299: 1e-6},
    ),
}

# Below this the remaining gap is floating-point noise rather than a seed being
# forgotten, so the test stops demanding that it keep shrinking.
CONVERGENCE_NOISE_FLOOR = 1e-9


def reference_candles(count: int = 300) -> list[Candle]:
    """Build the exact series the frozen reference values were produced from."""

    candles: list[Candle] = []
    previous_close = 100.0
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for index in range(count):
        drift = math.sin(index / 5.0) * 3.0 + math.cos(index / 11.0) * 1.5
        close = previous_close + drift + (index % 7) * 0.25 - 0.75
        open_price = previous_close
        high = max(open_price, close) + 1.25 + (index % 3) * 0.4
        low = min(open_price, close) - 1.25 - (index % 5) * 0.3
        open_time = start + timedelta(hours=index)
        candles.append(
            Candle(
                symbol="BTC/USDT:USDT",
                exchange="binance",
                timeframe="1h",
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
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


def _computed_series() -> dict[str, list[float]]:
    """Return every registered series, flattening dict outputs to `name.key`."""

    candles = reference_candles()
    flattened: dict[str, list[float]] = {}
    for spec in DEFAULT_REGISTRY.list():
        series = spec.compute_vectorized(candles)
        if series and isinstance(series[0], dict):
            for key in series[0]:
                flattened[f"{spec.identifier}.{key}"] = [
                    float(value[key])  # type: ignore[index]
                    for value in series
                ]
        else:
            flattened[spec.identifier] = [float(value) for value in series]  # type: ignore[arg-type]
    return flattened


@pytest.mark.parametrize("name", sorted(REFERENCE))
def test_values_match_an_outside_implementation(name: str) -> None:
    """Our value equals TA-Lib's at every sampled point."""

    produced = _computed_series()[name]
    for index, expected in REFERENCE[name].items():
        assert produced[index] == pytest.approx(expected, rel=1e-9, abs=1e-9), (
            f"{name} at index {index}"
        )


@pytest.mark.parametrize("name", sorted(CONVERGING))
def test_seed_window_differences_converge_to_the_outside_implementation(name: str) -> None:
    """A different seed window may differ early, but the gap must close.

    A persistent gap would mean the formulas themselves disagree, which is what
    this shape of assertion separates from a seed that is merely forgotten at a
    geometric rate.
    """

    values, tolerance = CONVERGING[name]
    produced = _computed_series()[name]
    previous_gap = math.inf
    for index in SAMPLE_INDICES:
        gap = abs(produced[index] - values[index])
        assert gap <= tolerance[index], f"{name} at index {index} gap {gap}"
        if previous_gap > CONVERGENCE_NOISE_FLOOR:
            assert gap <= previous_gap, f"{name} gap grew at index {index}"
        previous_gap = gap


def test_every_registered_output_is_covered_by_the_outside_comparison() -> None:
    """No registered output may sit outside the comparison unnoticed.

    A new indicator that nobody compared would otherwise pass the suite on parity
    alone, which is the exact gap this file exists to close.
    """

    compared = set(REFERENCE) | set(CONVERGING) | set(UNCOMPARED)
    produced = set(_computed_series())
    assert produced - compared == set()
    assert set(UNCOMPARED) <= produced, "an uncompared entry no longer exists"
