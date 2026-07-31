"""Registration list owned by the volume category."""

from functools import partial

from core_lib.indicators import volume
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="A/D Line",
        params={},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.2 (H=L keeps the multiplier at 0)",
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.ad_line,
        _state_factory=volume.ADLineState,
    ),
    IndicatorSpec(
        name="Chaikin Oscillator",
        params={"fast_period": 3, "slow_period": 10},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.3 (EMA(ADL,3) - EMA(ADL,10))",
        min_history=10,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.chaikin_oscillator, fast_period=3, slow_period=10),
        _state_factory=partial(
            volume.ChaikinOscillatorState,
            fast_period=3,
            slow_period=10,
        ),
    ),
    IndicatorSpec(
        name="CMF",
        params={"period": 20},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.4 (money flow volume over volume)",
        min_history=20,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.cmf, period=20),
        _state_factory=partial(volume.CMFState, period=20),
    ),
    IndicatorSpec(
        name="OBV",
        params={},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.1 (signed volume accumulation)",
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.obv,
        _state_factory=volume.OBVState,
    ),
    IndicatorSpec(
        name="Force Index",
        params={"period": 13},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §4.6 (EMA of price change times volume)",
        min_history=14,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.force_index, period=13),
        _state_factory=partial(volume.ForceIndexState, period=13),
    ),
    IndicatorSpec(
        name="Money Flow Index",
        params={"period": 14},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §4.5 (typical-price money flow over 14 candles; "
            "§0.11's RSI-family answer of 100 covers an empty negative side). "
            "Written out in full because §6.4's Market Facilitation Index shares the short form."
        ),
        min_history=15,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.money_flow_index, period=14),
        _state_factory=partial(volume.MoneyFlowIndexState, period=14),
    ),
    IndicatorSpec(
        name="Ease of Movement",
        params={"period": 14, "scale": 100_000_000},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §4.7 (median-price move per unit of volume, "
            "smoothed over 14 candles). The section leaves the box-ratio scale as an example "
            "rather than a fixed number, so the example value 100000000 is registered here "
            "where the choice stays visible."
        ),
        min_history=15,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.ease_of_movement, period=14, scale=100_000_000),
        _state_factory=partial(volume.EaseOfMovementState, period=14, scale=100_000_000),
    ),
    IndicatorSpec(
        name="Klinger Volume Oscillator",
        params={"short_period": 34, "long_period": 55, "signal_period": 13},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §4.8 (EMA(VF,34) - EMA(VF,55), signal EMA(13)). "
            "§12 records that implementations disagree over the cm initialization and the "
            "absolute value in the Volume Force; the section's own text is adopted on both. "
            "The first transition has no earlier trend, so §4.8's else branch applies and cm "
            "starts at dm_{t-1} + dm_t, and the absolute value stays around 2*(dm/cm) - 1 with "
            "the trend sign applied outside it. Variants that seed cm from a single range or "
            "drop the absolute value are not followed. Tulip Indicators 0.4.0 turns out to "
            "initialize cm the same way, which supports the reading but is not what decided "
            "it: §4.8's own else branch is."
        ),
        min_history=68,
        category="volume",
        required_inputs=(),
        _vectorized=partial(
            volume.klinger_volume_oscillator,
            short_period=34,
            long_period=55,
            signal_period=13,
        ),
        _state_factory=partial(
            volume.KlingerVolumeOscillatorState,
            short_period=34,
            long_period=55,
            signal_period=13,
        ),
    ),
    IndicatorSpec(
        name="Negative Volume Index",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §4.9 (compounds the close change only where "
            "volume fell, seeded at 1000)"
        ),
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.negative_volume_index,
        _state_factory=partial(volume.VolumeIndexState, on_rising_volume=False),
    ),
    IndicatorSpec(
        name="Positive Volume Index",
        params={},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §4.10 (compounds the close change only where "
            "volume rose, seeded at 1000)"
        ),
        min_history=1,
        category="volume",
        required_inputs=(),
        _vectorized=volume.positive_volume_index,
        _state_factory=partial(volume.VolumeIndexState, on_rising_volume=True),
    ),
    IndicatorSpec(
        name="Volume SMA",
        params={"period": 20},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §0.2 (volume input)",
        min_history=20,
        category="volume",
        required_inputs=(),
        _vectorized=partial(volume.volume_sma, period=20),
        _state_factory=partial(volume.VolumeSMAState, period=20),
    ),
)
