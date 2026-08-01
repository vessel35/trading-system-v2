"""Verify the candlestick pattern foundation against the pattern standard.

The layer under test is §1 through §6 of `candlestick_pattern_calc_spec.md`: the
shared candle primitives, the seven scales, the prior-trend judgment, the output
contract, the warm-up formulas, and the spec and registry the patterns of §7 will
register into. The patterns themselves are not implemented yet.

Expected values are written out by hand from the standard rather than computed by
calling the code under test, so a formula and its check cannot drift together.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY, IndicatorSpec
from core_lib.patterns import outputs, primitives, scales, trend, warmup
from core_lib.patterns.registry import PatternRegistry, PatternSeries, PatternSpec, PatternState
from core_lib.series import SeriesSpec, SeriesState
from core_lib.types import Candle


def make_candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    open_time = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return Candle(
        symbol="BTCUSDT",
        exchange="BINANCE",
        timeframe="1h",
        open_time=open_time,
        close_time=open_time + timedelta(hours=1),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1000.0,
        quote_volume=None,
        trade_count=None,
    )


def flat_candle(index: int, price: float) -> Candle:
    """Return a bar whose four prices are equal, the §2.7 degenerate case."""
    return make_candle(index, open_price=price, high=price, low=price, close=price)


def midpoint_series(midpoints: Sequence[float]) -> list[Candle]:
    """Return bars whose high-low midpoints are exactly the given values.

    §3 feeds the trend average the high-low midpoint, so a test that wants to
    control that average has to control the midpoints and nothing else. Each bar
    spans two units around its midpoint and opens and closes on it.
    """
    return [
        make_candle(
            index,
            open_price=value,
            high=value + 1.0,
            low=value - 1.0,
            close=value,
        )
        for index, value in enumerate(midpoints)
    ]


# --- §1.1 through §1.3: primitives ------------------------------------------


def test_derived_quantities_follow_section_one_one() -> None:
    """Check the eight derived quantities on one asymmetric bar."""
    candle = make_candle(0, open_price=104.0, high=110.0, low=98.0, close=100.0)

    assert primitives.body(candle) == 4.0
    assert primitives.body_top(candle) == 104.0
    assert primitives.body_bottom(candle) == 100.0
    assert primitives.body_mid(candle) == 102.0
    assert primitives.upper_shadow(candle) == 6.0
    assert primitives.lower_shadow(candle) == 2.0
    assert primitives.candle_range(candle) == 12.0
    assert primitives.range_mid(candle) == 104.0


def test_range_decomposes_into_shadows_and_body() -> None:
    """Check §1.1's identity ``Range = US + Body + LS`` with all terms non-negative."""
    for candle in (
        make_candle(0, open_price=100.0, high=110.0, low=95.0, close=108.0),
        make_candle(1, open_price=108.0, high=109.0, low=90.0, close=91.0),
        make_candle(2, open_price=100.0, high=100.0, low=100.0, close=100.0),
    ):
        parts = (
            primitives.upper_shadow(candle),
            primitives.body(candle),
            primitives.lower_shadow(candle),
        )
        assert all(part >= 0.0 for part in parts)
        assert sum(parts) == pytest.approx(primitives.candle_range(candle))


def test_a_bar_that_closes_on_its_open_has_no_colour() -> None:
    """Check §1.2: ``C == O`` is neither white nor black."""
    white = make_candle(0, open_price=100.0, high=106.0, low=99.0, close=105.0)
    black = make_candle(1, open_price=105.0, high=106.0, low=99.0, close=100.0)
    colorless = make_candle(2, open_price=100.0, high=106.0, low=94.0, close=100.0)

    assert (primitives.is_white(white), primitives.is_black(white)) == (True, False)
    assert (primitives.is_white(black), primitives.is_black(black)) == (False, True)
    assert (primitives.is_white(colorless), primitives.is_black(colorless)) == (False, False)
    assert primitives.is_colorless(colorless)


def test_the_three_kinds_of_gap_are_not_the_same_measurement() -> None:
    """Check §1.3: body, high-low, and open gaps disagree on the same pair of bars."""
    previous = make_candle(0, open_price=100.0, high=112.0, low=99.0, close=106.0)
    # Opens above the previous close and its body clears the previous body, but
    # its low still sits inside the previous bar's high-low range.
    current = make_candle(1, open_price=107.0, high=115.0, low=104.0, close=113.0)

    assert primitives.gap_up_body(previous, current)
    assert primitives.gap_up_open(previous, current)
    assert not primitives.gap_up_range(previous, current)

    # Its body clears the previous body downward, but its high still reaches
    # back into the previous bar's high-low range.
    lower = make_candle(2, open_price=98.0, high=100.0, low=90.0, close=96.0)
    assert primitives.gap_down_body(previous, lower)
    assert primitives.gap_down_open(previous, lower)
    assert not primitives.gap_down_range(previous, lower)

    clear_of_the_range = make_candle(3, open_price=90.0, high=95.0, low=85.0, close=88.0)
    assert primitives.gap_down_range(previous, clear_of_the_range)


# --- §1.4 and §2.7: the two undefined bars ----------------------------------


def test_a_zero_body_bar_satisfies_a_shadow_multiple_when_the_shadow_is_positive() -> None:
    """Check §1.4's zero-body rule, the one that lets a dragonfly doji be a Takuri."""
    # Body 0, lower shadow 10, no upper shadow: the dragonfly doji §2.7 names.
    dragonfly = make_candle(0, open_price=110.0, high=110.0, low=100.0, close=110.0)
    assert primitives.body(dragonfly) == 0.0
    assert scales.long_lower_shadow(dragonfly)
    assert scales.long_lower_shadow(dragonfly, multiple=3.0)
    assert not scales.long_upper_shadow(dragonfly)

    # Both zero: the comparison fails, so a four-price bar is not "long-shadowed".
    assert not primitives.shadow_reaches_multiple(0.0, 0.0, 2.0)
    assert primitives.shadow_reaches_multiple(0.0001, 0.0, 2.0)


def test_a_degenerate_bar_leaves_every_range_denominated_scale_false() -> None:
    """Check §2.7: no scale reading the high-low range holds on a four-price bar.

    Answering False here rather than True is what stops a rule written as a
    negation — "not a long body" — from letting a degenerate bar into a match.
    """
    flat = flat_candle(0, 100.0)
    assert primitives.is_degenerate(flat)
    assert primitives.candle_range(flat) == 0.0

    assert not scales.long_body(flat)
    assert not scales.short_body(flat)
    assert not scales.doji(flat)
    assert not scales.no_upper_shadow(flat)
    assert not scales.no_lower_shadow(flat)
    assert not scales.equal(100.0, 100.0, flat)
    assert not scales.near(100.0, 100.0, flat)
    assert not scales.long_upper_shadow(flat)
    assert not scales.long_lower_shadow(flat)


def test_a_pattern_window_reports_whether_it_touches_a_degenerate_bar() -> None:
    """Check the §2.7 gate a pattern calls before judging its window."""
    normal = make_candle(0, open_price=100.0, high=106.0, low=94.0, close=104.0)
    assert not primitives.any_degenerate([normal, normal])
    assert primitives.any_degenerate([normal, flat_candle(1, 100.0), normal])
    assert not primitives.any_degenerate([])


# --- §2.1 through §2.6: the scales at their boundaries ----------------------


def test_long_and_short_body_leave_a_band_that_is_neither() -> None:
    """Check §2.1 and §2.2, including that both inequalities are strict.

    Range 12 throughout, so a long body needs more than 6.0 and a short body less
    than 4.0. Morris describes many days as belonging to neither category, and
    the band between the two thresholds is that description.
    """
    exactly_half = make_candle(0, open_price=100.0, high=106.0, low=94.0, close=106.0)
    assert primitives.body(exactly_half) == 6.0
    assert not scales.long_body(exactly_half)

    over_half = make_candle(1, open_price=99.0, high=106.0, low=94.0, close=106.0)
    assert primitives.body(over_half) == 7.0
    assert scales.long_body(over_half)

    exactly_a_third = make_candle(2, open_price=100.0, high=106.0, low=94.0, close=104.0)
    assert primitives.body(exactly_a_third) == 4.0
    assert not scales.short_body(exactly_a_third)

    under_a_third = make_candle(3, open_price=100.0, high=106.0, low=94.0, close=103.0)
    assert primitives.body(under_a_third) == 3.0
    assert scales.short_body(under_a_third)

    in_between = make_candle(4, open_price=100.0, high=106.0, low=94.0, close=105.0)
    assert primitives.body(in_between) == 5.0
    assert not scales.long_body(in_between)
    assert not scales.short_body(in_between)


def test_doji_allows_equality_at_three_percent_of_the_range() -> None:
    """Check §2.3: the inequality is non-strict because the source form reads "Maximum"."""
    # Range 100, so the threshold is a body of exactly 3.0.
    at_the_threshold = make_candle(0, open_price=100.0, high=150.0, low=50.0, close=103.0)
    assert primitives.body(at_the_threshold) == 3.0
    assert scales.doji(at_the_threshold)

    over_the_threshold = make_candle(1, open_price=100.0, high=150.0, low=50.0, close=104.0)
    assert not scales.doji(over_the_threshold)


def test_a_long_shadow_is_measured_against_the_body_not_the_range() -> None:
    """Check §2.4, the one scale whose denominator the sources fixed themselves."""
    # Body 2, lower shadow 4, upper shadow 1.
    candle = make_candle(0, open_price=104.0, high=107.0, low=98.0, close=102.0)
    assert (primitives.body(candle), primitives.lower_shadow(candle)) == (2.0, 4.0)

    assert scales.long_lower_shadow(candle)
    assert not scales.long_lower_shadow(candle, multiple=3.0)
    assert not scales.long_upper_shadow(candle)


def test_a_very_short_shadow_allows_equality_at_a_tenth_of_the_range() -> None:
    """Check §2.5, whose source phrasing reads "10% (or less)"."""
    # Range 100, upper shadow exactly 10, lower shadow 0.
    candle = make_candle(0, open_price=60.0, high=150.0, low=50.0, close=140.0)
    assert primitives.upper_shadow(candle) == 10.0
    assert scales.no_upper_shadow(candle)
    assert scales.no_lower_shadow(candle)

    longer = make_candle(1, open_price=60.0, high=150.0, low=50.0, close=139.0)
    assert primitives.upper_shadow(longer) == 11.0
    assert not scales.no_upper_shadow(longer)


def test_equal_and_near_use_different_tolerances_on_the_later_bar() -> None:
    """Check §2.6: "equal" is the doji tolerance and "near" is the shadow one."""
    # Range 100 on the later bar, so equal allows 3.0 and near allows 10.0.
    later = make_candle(1, open_price=100.0, high=150.0, low=50.0, close=110.0)

    assert scales.equal(100.0, 103.0, later)
    assert not scales.equal(100.0, 103.5, later)
    assert scales.near(100.0, 110.0, later)
    assert not scales.near(100.0, 110.5, later)


def test_similar_body_bounds_the_ratio_of_two_bodies_at_two() -> None:
    """Check §2.6's third relation, the one with no range denominator."""
    big = make_candle(0, open_price=100.0, high=112.0, low=98.0, close=110.0)
    half = make_candle(1, open_price=100.0, high=112.0, low=98.0, close=105.0)
    smaller = make_candle(2, open_price=100.0, high=112.0, low=98.0, close=104.0)

    assert primitives.body(big) == 10.0
    assert scales.similar_body(big, half)
    assert scales.similar_body(half, big)
    assert not scales.similar_body(big, smaller)


# --- §3: the prior trend ----------------------------------------------------


def test_the_trend_average_smooths_the_midpoint_and_not_the_close() -> None:
    """Check §3.1's input choice and §3.2's seeding in one series.

    The midpoints rise by 1 per bar while the closes sit on the midpoint, so the
    average of the first ten midpoints is 104.5 and that is the seed value at
    index 9. Indexes 0 to 8 have no value at all.
    """
    candles = midpoint_series([100.0 + index for index in range(14)])
    averages = trend.trend_ema(candles)

    assert all(isnan(value) for value in averages[:9])
    assert averages[9] == pytest.approx(104.5)
    # alpha = 2 / 11 and the midpoint at index 10 is 110, so the next value is
    # 104.5 + alpha * (110 - 104.5).
    assert averages[10] == pytest.approx(104.5 + (2.0 / 11.0) * (110.0 - 104.5))


def test_the_trend_is_judged_on_the_pattern_first_day_not_the_judged_bar() -> None:
    """Check §3.1's comparison bar by making the two disagree.

    The midpoints climb for eleven bars and then collapse, so at index 11 the
    current bar is far below its average while the bar before it is above. A
    one-bar pattern judged at 11 must see a downtrend and a two-bar pattern
    judged at the same index must see an uptrend, because they read different
    bars.
    """
    candles = midpoint_series([100.0 + index for index in range(11)] + [50.0])

    single_bar = trend.prior_trend(candles, 1)
    two_bar = trend.prior_trend(candles, 2)

    assert single_bar[11] == trend.DOWNTREND
    assert two_bar[11] == trend.UPTREND


def test_the_trend_queue_makes_the_incremental_path_agree_with_the_batch_path() -> None:
    """Check §3.3's queue by running both paths over the same series."""
    candles = midpoint_series(
        [100.0, 101.0, 99.0, 103.0, 98.0, 105.0, 97.0, 108.0, 96.0, 110.0, 95.0, 112.0, 94.0]
    )
    for bar_count in (1, 2, 3, 5):
        expected = trend.prior_trend(candles, bar_count)
        state = trend.PriorTrendState(bar_count)
        observed = [state.update(candle) for candle in candles]
        assert len(observed) == len(expected)
        for index, (seen, want) in enumerate(zip(observed, expected, strict=True)):
            assert isnan(seen) == isnan(want), f"bar_count={bar_count} index={index}"
            if not isnan(want):
                assert seen == want, f"bar_count={bar_count} index={index}"


def test_a_first_day_midpoint_exactly_on_its_average_is_neither_direction() -> None:
    """Check §3.1's equality rule, which drops the tie from both directions."""
    # A flat series makes every midpoint equal to the seeded average.
    candles = midpoint_series([100.0] * 12)
    directions = trend.prior_trend(candles, 1)

    assert directions[9] == trend.NO_TREND
    assert directions[11] == trend.NO_TREND
    state = trend.PriorTrendState(1)
    state.seed(candles)
    assert not state.uptrend()
    assert not state.downtrend()


def test_the_trend_state_warms_up_exactly_where_section_six_says() -> None:
    """Check that the state turns warm on the bar §6's formula names, not before."""
    candles = midpoint_series([100.0 + index for index in range(20)])
    for bar_count in (1, 2, 3, 4, 5):
        state = trend.PriorTrendState(bar_count)
        first_warm: int | None = None
        for index, candle in enumerate(candles):
            state.update(candle)
            if state.warmed_up:
                first_warm = index
                break
        # Hand-derived: the first day sits at bar_count - 1 behind, and the
        # average first exists at index 9, so the judged bar is 9 + bar_count - 1.
        assert first_warm == 9 + bar_count - 1
        assert state.min_history == first_warm + 1


def test_the_trend_state_seeds_to_the_same_place_a_replay_reaches() -> None:
    """Check that seeding is a replay of updates and leaves no residue."""
    candles = midpoint_series([100.0 + index for index in range(15)])
    replayed = trend.PriorTrendState(3)
    for candle in candles:
        replayed.update(candle)

    seeded = trend.PriorTrendState(3)
    seeded.seed(candles)
    seeded.seed(candles)

    assert seeded.warmed_up == replayed.warmed_up
    assert seeded.current() == replayed.current()
    assert seeded.first_day_average() == pytest.approx(replayed.first_day_average())


def test_the_trend_rejects_a_span_of_zero_bars() -> None:
    with pytest.raises(ValueError, match="bar_count must be positive"):
        trend.PriorTrendState(0)
    with pytest.raises(ValueError, match="bar_count must be positive"):
        trend.prior_trend([], 0)


# --- §5: the output contract ------------------------------------------------


def test_the_four_keys_are_named_off_the_pattern_name() -> None:
    """Check §5.1's key naming."""
    assert outputs.output_keys("pat_hammer") == (
        "pat_hammer",
        "pat_hammer_dir",
        "pat_hammer_strength",
        "pat_hammer_confirm",
    )


@pytest.mark.parametrize(
    "name",
    ["hammer", "Pat_Hammer", "pat_", "pat_hammer_", "pat__hammer", "pat_hammer_dir"],
)
def test_a_name_that_breaks_the_naming_rule_is_rejected(name: str) -> None:
    """Check §5.1, plus the collision a name ending in a reserved suffix would cause."""
    with pytest.raises(ValueError):
        outputs.assert_pattern_name(name)


def test_warm_up_is_the_only_place_nan_appears() -> None:
    """Check §5.3: NaN means "cannot judge yet" and 0.0 means "judged, did not hold"."""
    undetermined = outputs.undetermined_outputs("pat_hammer")
    assert len(undetermined) == 4
    assert all(isnan(value) for value in undetermined.values())

    rejected = outputs.no_match_outputs("pat_hammer")
    assert rejected == {
        "pat_hammer": 0.0,
        "pat_hammer_dir": 0.0,
        "pat_hammer_strength": 0.0,
        "pat_hammer_confirm": 0.0,
    }


def test_a_confirmation_can_land_on_a_bar_that_did_not_match() -> None:
    """Check §5.4: the confirming bar is later than the matching bar.

    Writing the confirmation back onto the pattern bar would make the value at
    index `t` depend on a candle after `t`, which the alignment rule forbids.
    """
    matched = outputs.match_outputs("pat_hanging_man", direction=outputs.BEARISH)
    assert matched["pat_hanging_man"] == 1.0
    assert matched["pat_hanging_man_dir"] == -1.0
    assert matched["pat_hanging_man_confirm"] == 0.0

    later = outputs.no_match_outputs("pat_hanging_man", confirmed=True)
    assert later["pat_hanging_man"] == 0.0
    assert later["pat_hanging_man_confirm"] == 1.0


def test_a_directionless_pattern_reports_zero_direction_when_it_matches() -> None:
    """Check §5.2: the nine shape-only candle lines carry no direction."""
    matched = outputs.match_outputs("pat_spinning_top", direction=outputs.DIRECTIONLESS)
    assert matched["pat_spinning_top"] == 1.0
    assert matched["pat_spinning_top_dir"] == 0.0


def test_boundary_strength_is_the_only_value_besides_full() -> None:
    """Check §5.6: half strength marks an engulfment with one end exactly equal."""
    boundary = outputs.match_outputs(
        "pat_engulfing",
        direction=outputs.BULLISH,
        strength=outputs.BOUNDARY_STRENGTH,
    )
    assert boundary["pat_engulfing_strength"] == 0.5

    with pytest.raises(ValueError, match="strength must be one of"):
        outputs.match_outputs("pat_engulfing", direction=outputs.BULLISH, strength=0.75)
    with pytest.raises(ValueError, match="direction must be one of"):
        outputs.match_outputs("pat_engulfing", direction=2.0)


# --- §6: min_history --------------------------------------------------------


@pytest.mark.parametrize(
    ("bar_count", "requires_trend", "expected"),
    [
        # Hand-derived from §6's two formulas and cross-checked against the
        # per-pattern values §8.3 tabulates.
        (1, False, 1),  # the twelve trendless single-bar candle lines
        (2, False, 2),  # Kicking and Kicking by Length
        (3, False, 3),  # Hikkake
        (4, False, 4),  # Modified Hikkake
        (1, True, 10),  # Hammer, Hanging Man, Inverted Hammer, Belt-hold
        (2, True, 11),  # Shooting Star and the two-bar trend patterns
        (3, True, 12),  # the three-bar trend patterns
        (4, True, 13),  # Three-Line Strike, Concealing Baby Swallow
        (5, True, 14),  # Breakaway, Ladder Bottom, Mat Hold
    ],
)
def test_min_history_follows_the_two_formulas(
    bar_count: int,
    requires_trend: bool,
    expected: int,
) -> None:
    """Check §6 against values derived by hand, not by re-running the formula."""
    assert warmup.min_history_for(bar_count, requires_trend=requires_trend) == expected


def test_min_history_rejects_a_span_of_zero_bars() -> None:
    with pytest.raises(ValueError, match="bar_count must be positive"):
        warmup.min_history_for(0, requires_trend=False)


def test_a_trend_pattern_needs_nine_more_bars_than_its_shape_alone() -> None:
    """Check that the two formulas differ by exactly the average's warm-up."""
    for bar_count in range(1, 8):
        shape_only = warmup.min_history_for(bar_count, requires_trend=False)
        with_trend = warmup.min_history_for(bar_count, requires_trend=True)
        assert with_trend - shape_only == 9


# --- the spec, the registry, and the shared protocol ------------------------


def _example_state() -> PatternState:
    return _ExampleState()


class _ExampleState:
    """A stand-in state used to exercise the spec and registry wiring.

    `min_history` is a constructor argument rather than a constant because the
    registry now refuses a spec whose state disagrees with it about warm-up, and
    a fixture that hardcoded one number could only ever match one shape of spec.
    """

    def __init__(self, min_history: int = 10) -> None:
        self.min_history = min_history
        self._seen = 0

    @property
    def warmed_up(self) -> bool:
        return self._seen >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        self._seen = 0
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> dict[str, float]:
        self._seen += 1
        return self.current()

    def current(self) -> dict[str, float]:
        if not self.warmed_up:
            return outputs.undetermined_outputs("pat_example")
        return outputs.no_match_outputs("pat_example")


def _example_vectorized(candles: Sequence[Candle]) -> PatternSeries:
    state = _ExampleState()
    return [state.update(candle) for candle in candles]


def make_spec(name: str = "pat_example", **overrides: object) -> PatternSpec:
    fields: dict[str, object] = {
        "name": name,
        "params": {},
        "version": "1.0.0",
        "bar_count": 1,
        "requires_trend": True,
        "_vectorized": _example_vectorized,
        "_state_factory": _example_state,
    }
    fields.update(overrides)
    if "_state_factory" not in overrides:
        # Keep the stand-in state agreeing with whatever shape the spec takes.
        expected = warmup.min_history_for(
            int(fields["bar_count"]),  # type: ignore[call-overload]
            requires_trend=bool(fields["requires_trend"]),
        )
        fields["_state_factory"] = lambda: _ExampleState(expected)
    return PatternSpec(**fields)  # type: ignore[arg-type]


def test_the_spec_derives_min_history_instead_of_declaring_it() -> None:
    """Check that §6's formula cannot be contradicted by a registration."""
    assert make_spec(bar_count=3, requires_trend=True).min_history == 12
    assert make_spec(bar_count=3, requires_trend=False).min_history == 3


def test_registration_rejects_a_state_that_disagrees_about_warm_up() -> None:
    """Check that spec and state cannot declare different warm-up lengths.

    The spec's number decides how much history a run fetches and the state's
    number decides when it reports itself warmed up. They live in different
    places, so a drift between them shows up much later as a first valid bar
    that is off by exactly the difference. Registration is the last moment where
    both are visible, so it is where the disagreement has to be refused.
    """

    class _DriftingState(_ExampleState):
        def __init__(self) -> None:
            super().__init__()
            self.min_history = 11

    spec = make_spec(bar_count=1, requires_trend=True, _state_factory=_DriftingState)
    assert spec.min_history == 10

    registry = PatternRegistry()
    with pytest.raises(ValueError, match="min_history"):
        registry.register(spec)


def test_registration_accepts_a_state_that_agrees_about_warm_up() -> None:
    registry = PatternRegistry()
    registry.register(make_spec(bar_count=1, requires_trend=True))
    assert registry.names() == {"pat_example"}


def test_the_spec_identifier_folds_in_its_parameters() -> None:
    assert make_spec().identifier == "pat_example"
    assert make_spec(params={"n": 3}).identifier == "pat_example(n=3)"


def test_the_spec_rejects_a_malformed_identity() -> None:
    with pytest.raises(ValueError):
        make_spec(name="example")
    with pytest.raises(ValueError, match="version must not be empty"):
        make_spec(version="")
    with pytest.raises(ValueError, match="bar_count must be positive"):
        make_spec(bar_count=0)


def test_the_spec_params_cannot_be_mutated_after_registration() -> None:
    spec = make_spec(params={"n": 3})
    with pytest.raises(TypeError):
        spec.params["n"] = 4  # type: ignore[index]


def test_patterns_declare_no_undefined_outputs() -> None:
    """Check §5.3's consequence: after warm-up every one of the four keys is finite."""
    assert make_spec().undefined_outputs == ()


def test_the_registry_offers_the_two_entry_points_the_services_call() -> None:
    """Check `resolve_specs` and `specs_from_descriptors`, the two consumer paths."""
    registry = PatternRegistry()
    hammer = make_spec("pat_hammer")
    doji = make_spec("pat_doji", requires_trend=False)
    registry.register(hammer)
    registry.register(doji)

    descriptors = [{"name": "pat_hammer", "params": {}}]
    assert registry.specs_from_descriptors(descriptors) == [hammer]
    assert registry.resolve_specs("auto", descriptors, []) == [hammer]
    assert registry.resolve_specs("explicit", [], descriptors) == [hammer]
    assert registry.resolve_specs("all", [], []) == [doji, hammer]
    assert registry.names() == {"pat_hammer", "pat_doji"}


def test_the_registry_resolves_an_empty_selection_to_nothing() -> None:
    """Check the one deliberate difference from the indicator registry.

    A run that selects no indicator is a mistake and that registry raises. A
    strategy that asks for no pattern is ordinary, so this one returns an empty
    list instead.
    """
    assert PatternRegistry().resolve_specs("auto", [], []) == []


def test_the_registry_rejects_a_duplicate_identity() -> None:
    registry = PatternRegistry()
    registry.register(make_spec("pat_hammer"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(make_spec("pat_hammer"))


def test_the_registry_rejects_an_unregistered_or_malformed_descriptor() -> None:
    registry = PatternRegistry()
    registry.register(make_spec("pat_hammer"))

    with pytest.raises(KeyError):
        registry.specs_from_descriptors([{"name": "pat_doji", "params": {}}])
    with pytest.raises(ValueError, match="exactly name and params"):
        registry.specs_from_descriptors([{"name": "pat_hammer"}])
    with pytest.raises(ValueError, match="mode must be"):
        registry.resolve_enabled("everything", [], [])


def test_the_batch_path_refuses_a_series_shorter_than_the_warm_up() -> None:
    registry = PatternRegistry()
    registry.register(make_spec("pat_hammer"))
    candles = midpoint_series([100.0 + index for index in range(4)])

    with pytest.raises(ValueError, match="requires 10 candles, got 4"):
        registry.compute_batch(candles, {"pat_hammer"})


def test_the_batch_path_refuses_an_unfinalized_candle() -> None:
    """Check that the pattern batch path enforces the same confirmed-candle rule."""
    registry = PatternRegistry()
    registry.register(make_spec("pat_hammer"))
    candles = midpoint_series([100.0 + index for index in range(12)])

    with pytest.raises(Exception, match="after decision time"):
        registry.compute_batch(candles, {"pat_hammer"}, decision_time=candles[0].open_time)


def test_both_spec_types_satisfy_the_shared_consumption_protocol() -> None:
    """Check the claim placement D rests on: one executor reads both spec types.

    The assignments are the static half of the check — mypy rejects the module if
    either type is missing a member — and the isinstance calls are the runtime
    half.
    """
    indicator: IndicatorSpec = DEFAULT_REGISTRY.list()[0]
    pattern = make_spec()

    from_indicator: SeriesSpec = indicator
    from_pattern: SeriesSpec = pattern
    assert isinstance(from_indicator, SeriesSpec)
    assert isinstance(from_pattern, SeriesSpec)

    indicator_state: SeriesState = indicator.make_state()
    pattern_state: SeriesState = pattern.make_state()
    assert isinstance(indicator_state, SeriesState)
    assert isinstance(pattern_state, SeriesState)


def _declared_members(protocol: type) -> set[str]:
    """Return the members a protocol declares, without its machinery attributes."""
    return {name for name in vars(protocol) if not name.startswith("_")}


def test_the_shared_protocol_carries_only_what_the_services_read() -> None:
    """Check that the batch path and `current()` stayed out of the consumption protocol.

    They are verification members: core-lib's tests and `compute_batch` use them
    and neither service does. Letting them into the protocol would claim a
    consumer requirement that the survey of both services did not find.
    """
    assert _declared_members(SeriesSpec) == {
        "identifier",
        "name",
        "params",
        "version",
        "min_history",
        "undefined_outputs",
        "make_state",
    }
    assert _declared_members(SeriesState) == {"seed", "warmed_up", "update"}
    assert not hasattr(SeriesSpec, "compute_vectorized")
    assert not hasattr(SeriesState, "current")


def test_patterns_stay_out_of_the_indicator_registry() -> None:
    """Check that this package did not move the indicator standard's tally."""
    registered = {spec.name for spec in DEFAULT_REGISTRY.list()}
    assert all(not name.startswith(outputs.NAME_PREFIX) for name in registered)
