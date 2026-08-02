"""Verify §7.1 and §7.2 of the candlestick pattern standard, and what they rest on.

Seventeen sections are under test — the doji family and umbrella lines of §7.1 and
the body-and-shadow shapes of §7.2 — together with the two foundation pieces they
needed: §4.1's engulfment and containment relations and §1.4's upper-bound shadow
comparison.

Every expected value here is derived by hand from the standard. The candles are
built to sit on the thresholds the standard names, and the numbers that make them
do so are written out in each test, so a rule and its check cannot drift together.
The two execution paths are compared on every one of these hand-built series
rather than only on a generated one, because `run` — which nearly every test calls
— judges the batch path and the incremental path and refuses to return until they
agree.
"""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from math import isnan, sin

import pytest
from core_lib.indicators.registry import DEFAULT_REGISTRY
from core_lib.patterns import body_shadow, doji_umbrella, inequalities, outputs, primitives
from core_lib.patterns.judgment import PatternRule, PatternRuleState, judge_series
from core_lib.patterns.registry import PatternSpec, PatternState, PatternValue
from core_lib.patterns.specs import DEFAULT_PATTERN_REGISTRY
from core_lib.series import SeriesSpec, SeriesState
from core_lib.types import Candle

TREND_WARM_UP_BARS = 9
"""§3.2: the ten-period average first exists at index 9, so nine bars precede it."""


def make_candle(index: int, open_price: float, high: float, low: float, close: float) -> Candle:
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


Shape = tuple[float, float, float, float]
"""One bar as (open, high, low, close), the form every hand-built candle takes here."""


def background(midpoint: float, count: int = TREND_WARM_UP_BARS) -> list[Shape]:
    """Return filler bars whose high-low midpoint is exactly `midpoint`.

    §3 compares the pattern's first day against a ten-period average of the
    midpoint, so filler bars at a constant midpoint `M` put the average at
    `(9 * M + m) / 10` on the tenth bar, where `m` is the pattern bar's own
    midpoint. That resolves to: the trend is down when `m < M` and up when
    `m > M`, which is how every trend-requiring test below chooses its `M`.
    """
    return [(midpoint, midpoint + 1.0, midpoint - 1.0, midpoint)] * count


def series(shapes: Sequence[Shape]) -> list[Candle]:
    return [make_candle(index, *shape) for index, shape in enumerate(shapes)]


def assert_same_series(batch: Sequence[PatternValue], incremental: Sequence[PatternValue]) -> None:
    assert len(batch) == len(incremental)
    for index, (left, right) in enumerate(zip(batch, incremental, strict=True)):
        assert left.keys() == right.keys(), f"index {index}"
        for key in left:
            if isnan(left[key]):
                assert isnan(right[key]), f"index {index} key {key}"
            else:
                assert left[key] == right[key], f"index {index} key {key}"


def run(rule: PatternRule, shapes: Sequence[Shape]) -> list[PatternValue]:
    """Return the batch series after checking the incremental path matches it.

    Both paths are built from the same rule but not from each other, so running
    them side by side on every hand-built case is a real comparison rather than a
    restatement.
    """
    candles = series(shapes)
    batch = judge_series(rule, candles)
    state = PatternRuleState(rule)
    incremental = [state.update(candle) for candle in candles]
    assert_same_series(batch, incremental)
    return batch


def matched(rule: PatternRule, shapes: Sequence[Shape], index: int = -1) -> PatternValue:
    """Assert the pattern held on one bar and return that bar's four outputs."""
    values = run(rule, shapes)[index]
    assert values[rule.name] == outputs.MATCHED
    return values


def not_matched(rule: PatternRule, shapes: Sequence[Shape], index: int = -1) -> PatternValue:
    """Assert the pattern was judged on one bar and did not hold there."""
    values = run(rule, shapes)[index]
    assert values[rule.name] == outputs.NOT_MATCHED
    return values


# --- what the seventeen are, and what the registry says about them -----------

SECTION_MIN_HISTORY = {
    # §7.1, written out from each section's own `min_history` line rather than
    # recomputed: twelve trendless single bars at 1, four trend bars at 10, and
    # Shooting Star at 11 because its gap requirement makes it a two-bar pattern.
    "pat_doji": 1,
    "pat_long_legged_doji": 1,
    "pat_rickshaw_man": 1,
    "pat_dragonfly_doji": 1,
    "pat_gravestone_doji": 1,
    "pat_takuri": 1,
    "pat_hammer": 10,
    "pat_hanging_man": 10,
    "pat_inverted_hammer": 10,
    "pat_shooting_star": 11,
    "pat_spinning_top": 1,
    # §7.2.
    "pat_high_wave": 1,
    "pat_marubozu": 1,
    "pat_closing_marubozu": 1,
    "pat_belt_hold": 10,
    "pat_long_line": 1,
    "pat_short_line": 1,
}

REGISTERED_SPECS: tuple[PatternSpec, ...] = tuple(
    spec for spec in DEFAULT_PATTERN_REGISTRY.list() if spec.name in SECTION_MIN_HISTORY
)
"""The registered specs of §7.1 and §7.2, which is what this file makes claims about.

Every later group registers into the same registry, so a sweep over the whole of
it would pull in sections this file's series were never built for. Each group's
own test module holds the sweeps for its own sections; what stays shared is the
registry-wide claim below that no pattern name ever meets an indicator name.
"""


def test_the_registry_holds_the_seventeen_sections_of_seven_one_and_seven_two() -> None:
    """Check the registered catalog against §8.1's first two rows."""
    assert DEFAULT_PATTERN_REGISTRY.names() >= set(SECTION_MIN_HISTORY)
    assert len(REGISTERED_SPECS) == 17
    # No pattern takes a parameter, so an identity is its bare name.
    assert {spec.identifier for spec in REGISTERED_SPECS} == set(SECTION_MIN_HISTORY)


def test_each_pattern_warms_up_where_its_own_section_says() -> None:
    """Check §6's two formulas against the per-section values, not against itself."""
    assert {spec.name: spec.min_history for spec in REGISTERED_SPECS} == SECTION_MIN_HISTORY
    # §8.3's distribution for these two groups: twelve at 1, four at 10, one at 11.
    counted = sorted(SECTION_MIN_HISTORY.values())
    assert counted.count(1) == 12
    assert counted.count(10) == 4
    assert counted.count(11) == 1


def test_a_pattern_name_never_collides_with_an_indicator_name() -> None:
    """Check decision G, which is why every pattern name carries the `pat_` prefix.

    The foundation already checks that no pattern reached the indicator registry.
    This is the other half: with patterns actually registered, the two name sets
    can now be compared and must not intersect.
    """
    indicator_names = {spec.name for spec in DEFAULT_REGISTRY.list()}
    pattern_names = DEFAULT_PATTERN_REGISTRY.names()

    assert pattern_names
    assert indicator_names.isdisjoint(pattern_names)
    assert all(name.startswith(outputs.NAME_PREFIX) for name in pattern_names)
    assert not any(name.startswith(outputs.NAME_PREFIX) for name in indicator_names)


def test_the_indicator_tally_is_untouched_by_this_change() -> None:
    """Check that registering seventeen patterns moved nothing in the other registry."""
    assert all(not spec.name.startswith(outputs.NAME_PREFIX) for spec in DEFAULT_REGISTRY.list())


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_a_registered_pattern_satisfies_the_shared_consumption_protocol(
    spec: PatternSpec,
) -> None:
    """Check that a real pattern — not only the foundation's stand-in — is consumable.

    The foundation proved the two spec *types* satisfy `SeriesSpec` using a
    fixture. This is the same claim about the specs the services would actually
    resolve, which is what the executors reach through.
    """
    consumable: SeriesSpec = spec
    assert isinstance(consumable, SeriesSpec)

    state: SeriesState = spec.make_state()
    assert isinstance(state, SeriesState)
    assert isinstance(state, PatternState)


# --- warm-up, the two paths, and degenerate bars, over every pattern ---------


def varied_shapes(count: int) -> list[Shape]:
    """Return a long series that carries every shape §7.1 and §7.2 name.

    The shapes below are the hand-built ones from the sections further down,
    cycled and shifted by a slow wave so the trend average moves under them.
    Without that drift every midpoint would equal its average and no
    trend-requiring pattern could ever match, which would leave the parity and
    warm-up checks running on nothing but non-matches.
    """
    catalog: tuple[Shape, ...] = (
        (100.0, 150.0, 50.0, 103.0),  # doji, long-legged, rickshaw man
        (150.0, 150.0, 50.0, 150.0),  # dragonfly doji with no body at all
        (50.0, 150.0, 50.0, 50.0),  # gravestone doji with no body at all
        (105.0, 112.0, 60.0, 110.0),  # the umbrella shape of Hammer/Hanging Man
        (57.0, 150.0, 50.0, 88.0),  # Inverted Hammer's narrow band
        # A high midpoint with a low close, which is what Shooting Star needs in
        # front of it: the midpoint carries the uptrend and the close leaves room
        # for the next bar to gap above it.
        (190.0, 200.0, 60.0, 62.0),
        (65.0, 150.0, 50.0, 55.0),  # Shooting Star's long-topped bar
        (100.0, 112.0, 93.0, 105.0),  # spinning top that is not a high wave
        (100.0, 120.0, 85.0, 105.0),  # high wave
        (100.0, 152.0, 98.0, 150.0),  # marubozu, and the bullish belt-hold
        (150.0, 152.0, 80.0, 100.0),  # black closing marubozu, bearish belt-hold
        (100.0, 170.0, 80.0, 150.0),  # long line with shadows on both ends
    )
    shapes: list[Shape] = []
    for index in range(count):
        drift = 100.0 + 30.0 * sin(index / 5.0)
        shapes.append(
            tuple(price + drift for price in catalog[index % len(catalog)])  # type: ignore[arg-type]
        )
    return shapes


VARIED = varied_shapes(240)


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_the_two_execution_paths_agree_bar_for_bar(spec: PatternSpec) -> None:
    """Check the batch oracle against the incremental state over a long series."""
    candles = series(VARIED)
    batch = spec.compute_vectorized(candles)
    state = spec.make_state()
    assert_same_series(batch, [state.update(candle) for candle in candles])


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_every_pattern_matches_somewhere_in_the_parity_series(spec: PatternSpec) -> None:
    """Check that the parity comparison is not comparing two series of non-matches."""
    candles = series(VARIED)
    values = spec.compute_vectorized(candles)
    assert any(value[spec.name] == outputs.MATCHED for value in values)


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_nan_stops_exactly_at_the_warm_up_boundary(spec: PatternSpec) -> None:
    """Check §5.3: NaN before `min_history - 1`, a finite number from there on.

    The boundary index is the interesting one. An off-by-one in either direction
    is the failure §6's derivation exists to prevent, and it can only be caught
    by looking at the two bars either side of it rather than at the series as a
    whole.
    """
    candles = series(VARIED)
    values = spec.compute_vectorized(candles)
    boundary = spec.min_history - 1

    for index in range(boundary):
        assert all(isnan(value) for value in values[index].values()), f"index {index}"
    assert all(not isnan(value) for value in values[boundary].values())
    assert all(not isnan(value) for later in values[boundary:] for value in later.values())


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_the_incremental_state_warms_up_where_its_spec_says(spec: PatternSpec) -> None:
    """Check the state's own warm-up flag against the spec the registry accepted."""
    state = spec.make_state()
    assert state.min_history == spec.min_history
    for index, candle in enumerate(series(VARIED)):
        state.update(candle)
        assert state.warmed_up == (index + 1 >= spec.min_history), f"index {index}"


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_seeding_a_state_reaches_the_same_place_replaying_does(spec: PatternSpec) -> None:
    """Check that `seed` is a replay and leaves no residue from an earlier one."""
    candles = series(VARIED)[:60]
    replayed = spec.make_state()
    for candle in candles:
        replayed.update(candle)

    seeded = spec.make_state()
    seeded.seed(candles)
    seeded.seed(candles)

    assert_same_series([replayed.current()], [seeded.current()])


@pytest.mark.parametrize("spec", REGISTERED_SPECS, ids=lambda spec: spec.name)
def test_a_degenerate_bar_is_judged_and_not_matched(spec: PatternSpec) -> None:
    """Check §2.7 and §5.3 together: a four-price bar reports 0.0, never NaN.

    §2.7 asks for two defences and this exercises the second one. Each scale
    already answers False on such a bar, but a rule reading a scale negatively
    would take that False as a satisfied condition, so the pattern gates on the
    whole window before any condition is looked at.
    """
    shapes = list(VARIED[: spec.min_history + 4])
    shapes[-1] = (500.0, 500.0, 500.0, 500.0)
    candles = series(shapes)
    assert primitives.is_degenerate(candles[-1])

    values = spec.compute_vectorized(candles)[-1]
    assert values == {key: 0.0 for key in outputs.output_keys(spec.name)}


# --- §7.1.1 to §7.1.3: the doji, its long-legged form, and the rickshaw man ---
#
# Every bar in this block has a high-low range of exactly 100, so §2.3's doji
# tolerance is a body of 3.00 and §2.6's `Near` tolerance is 10.00.

DOJI_SHAPE: Shape = (100.0, 150.0, 50.0, 103.0)
"""Body 3.00 on a range of 100: exactly §2.3's threshold, which allows equality."""


def test_a_doji_is_a_body_no_larger_than_three_percent_of_the_range() -> None:
    """Check §7.1.1's single rule at the threshold and one cent past it."""
    values = matched(doji_umbrella.DOJI, [DOJI_SHAPE])
    assert values["pat_doji_dir"] == outputs.DIRECTIONLESS
    assert values["pat_doji_strength"] == outputs.FULL_STRENGTH
    assert values["pat_doji_confirm"] == outputs.NOT_MATCHED

    not_matched(doji_umbrella.DOJI, [(100.0, 150.0, 50.0, 104.0)])


def test_a_long_legged_doji_needs_both_shadows_to_reach_two_bodies() -> None:
    """Check §7.1.2's rule 2, which §7.1.1 does not ask for.

    The matching bar has shadows of 47.00 and 50.00 against a body of 3.00, and
    the rejected one is a doji whose upper shadow is 2.00 — under §2.4's multiple
    of two — because its body sits at the top of the range.
    """
    values = matched(doji_umbrella.LONG_LEGGED_DOJI, [DOJI_SHAPE])
    assert values["pat_long_legged_doji_dir"] == outputs.DIRECTIONLESS

    top_heavy: Shape = (100.0, 105.0, 1.0, 103.0)
    assert matched(doji_umbrella.DOJI, [top_heavy])["pat_doji"] == outputs.MATCHED
    not_matched(doji_umbrella.LONG_LEGGED_DOJI, [top_heavy])


def test_a_rickshaw_man_puts_the_body_in_the_middle_of_the_range() -> None:
    """Check §7.1.3's rule 2, the `Near` comparison §2.6 supplies the number for.

    The matching bar's body midpoint is 101.50 against a range midpoint of
    100.00, a gap of 1.50 inside the tolerance of 10.00. The rejected one is a
    long-legged doji whose body midpoint sits 31.00 away.
    """
    values = matched(doji_umbrella.RICKSHAW_MAN, [DOJI_SHAPE])
    assert values["pat_rickshaw_man_dir"] == outputs.DIRECTIONLESS

    high_bodied: Shape = (130.0, 150.0, 50.0, 132.0)
    assert matched(doji_umbrella.LONG_LEGGED_DOJI, [high_bodied])
    not_matched(doji_umbrella.RICKSHAW_MAN, [high_bodied])


# --- §7.1.4 to §7.1.6: the two one-sided dojis and Takuri --------------------

DRAGONFLY_SHAPE: Shape = (148.0, 150.0, 50.0, 150.0)
"""Body 2.00 at the top of a range of 100, upper shadow 0.00, lower shadow 98.00."""

GRAVESTONE_SHAPE: Shape = (50.0, 150.0, 50.0, 52.0)
"""The same bar upside down: body 2.00 at the bottom, upper shadow 98.00."""

BODYLESS_DRAGONFLY: Shape = (150.0, 150.0, 50.0, 150.0)
"""Open, high, and close all at 150: the no-body case §1.4's lower bound is for."""

BODYLESS_GRAVESTONE: Shape = (50.0, 150.0, 50.0, 50.0)
"""Open, low, and close all at 50: the no-body case §1.4's upper bound is for."""


def test_a_dragonfly_doji_opens_and_closes_at_the_high_and_points_up() -> None:
    """Check §7.1.4, including that §5.2 lets this doji carry a direction."""
    values = matched(doji_umbrella.DRAGONFLY_DOJI, [DRAGONFLY_SHAPE])
    assert values["pat_dragonfly_doji_dir"] == outputs.BULLISH

    # A doji with the body at the *bottom* fails rule 2's bare upper shadow.
    not_matched(doji_umbrella.DRAGONFLY_DOJI, [GRAVESTONE_SHAPE])


def test_a_gravestone_doji_opens_and_closes_at_the_low_and_points_down() -> None:
    """Check §7.1.5, the mirror of §7.1.4 with the opposite direction."""
    values = matched(doji_umbrella.GRAVESTONE_DOJI, [GRAVESTONE_SHAPE])
    assert values["pat_gravestone_doji_dir"] == outputs.BEARISH

    not_matched(doji_umbrella.GRAVESTONE_DOJI, [DRAGONFLY_SHAPE])


def test_takuri_asks_for_three_bodies_of_lower_shadow_rather_than_two() -> None:
    """Check §7.1.6's own multiple, the one Morris states for this line."""
    values = matched(doji_umbrella.TAKURI, [DRAGONFLY_SHAPE])
    assert values["pat_takuri_dir"] == outputs.BULLISH

    not_matched(doji_umbrella.TAKURI, [GRAVESTONE_SHAPE])


def test_a_bodyless_dragonfly_doji_satisfies_every_lower_bound_it_meets() -> None:
    """Check §1.4's lower-bound rule where the standard says it matters.

    Morris defines Takuri as a kind of dragonfly doji, so a dragonfly doji with
    no body at all has to clear a shadow requirement stated as a multiple of a
    body that is zero. §1.4 rules that it does, and this is the bar it rules on:
    body 0.00, lower shadow 100.00.
    """
    assert primitives.body(series([BODYLESS_DRAGONFLY])[0]) == 0.0

    assert matched(doji_umbrella.DRAGONFLY_DOJI, [BODYLESS_DRAGONFLY])
    assert matched(doji_umbrella.TAKURI, [BODYLESS_DRAGONFLY])
    # §7.1.7's rule 4 is the same kind of lower bound, so the same bar clears
    # Hammer's shape once a downtrend is put in front of it. Its midpoint is
    # 100.00, so filler at 120.00 makes the trend down.
    assert matched(doji_umbrella.HAMMER, [*background(120.0), BODYLESS_DRAGONFLY])


def test_the_dragonfly_and_takuri_thresholds_admit_the_same_bars() -> None:
    """Record a consequence of §2.3 and §2.5 rather than a rule of §7.1.6.

    §7.1.4 asks for a lower shadow of at least two bodies and §7.1.6 for at least
    three, but both sit behind a doji body (at most 3% of the range) and a bare
    upper shadow (at most 10%). Those two leave the lower shadow at 87% of the
    range or more, which is already more than three bodies. So the larger
    multiple never rejects a bar the smaller one accepted, and the two sections
    match exactly the same candles.

    Nothing here is worked around: both sections are implemented as written. The
    test states the overlap so that a later change to §2.3 or §2.5 — the only way
    the two can come apart — shows up as this expectation failing.
    """
    candles = series(VARIED)
    dragonfly = judge_series(doji_umbrella.DRAGONFLY_DOJI, candles)
    takuri = judge_series(doji_umbrella.TAKURI, candles)

    assert [value["pat_dragonfly_doji"] for value in dragonfly] == [
        value["pat_takuri"] for value in takuri
    ]


# --- §7.1.7 to §7.1.9: the three umbrella patterns that need a trend ---------
#
# Each of these judges a single bar, so §3's comparison bar is the pattern bar
# itself and `background` decides the direction: filler above the pattern bar's
# midpoint makes a downtrend, filler below makes an uptrend.

UMBRELLA_SHAPE: Shape = (105.0, 112.0, 60.0, 110.0)
"""Body 5.00 in a range of 52.00, upper shadow 2.00, lower shadow 45.00.

Short body (under 17.33), bare upper shadow (at most 5.20), and a lower shadow
past two bodies (10.00). Its high-low midpoint is 86.00.
"""

INVERTED_HAMMER_SHAPE: Shape = (57.0, 150.0, 50.0, 88.0)
"""Body 31.00 in a range of 100, upper shadow 62.00 — exactly two bodies.

§7.1.9's rules leave a narrow band and this bar sits in it. Rule 2 caps the body
below a third of the range (33.33) while rule 3 caps the upper shadow at two
bodies, and with a lower shadow of at most a tenth of the range those two force
the body to at least 30.00. Its midpoint is 100.00.
"""


def test_a_hammer_is_the_umbrella_shape_after_a_downtrend() -> None:
    """Check §7.1.7's four rules, and that an uptrend rejects the same bar."""
    values = matched(doji_umbrella.HAMMER, [*background(100.0), UMBRELLA_SHAPE])
    assert values["pat_hammer_dir"] == outputs.BULLISH
    assert values["pat_hammer_strength"] == outputs.FULL_STRENGTH

    not_matched(doji_umbrella.HAMMER, [*background(80.0), UMBRELLA_SHAPE])


def test_a_hanging_man_is_the_same_shape_after_an_uptrend() -> None:
    """Check §7.1.8, which takes §7.1.7's rules 2 to 4 unchanged."""
    values = matched(doji_umbrella.HANGING_MAN, [*background(80.0), UMBRELLA_SHAPE])
    assert values["pat_hanging_man_dir"] == outputs.BEARISH

    not_matched(doji_umbrella.HANGING_MAN, [*background(100.0), UMBRELLA_SHAPE])


def test_a_midpoint_exactly_on_its_average_is_neither_trend() -> None:
    """Check §3.1's tie rule through a pattern rather than through the average.

    Filler at the pattern bar's own midpoint makes the ten-bar average equal to
    it, and §3 drops that case from both directions, so neither umbrella pattern
    holds however well the shape fits.
    """
    flat: Shape = (86.0, 87.0, 85.0, 86.0)
    shapes = [*[flat] * TREND_WARM_UP_BARS, UMBRELLA_SHAPE]

    not_matched(doji_umbrella.HAMMER, shapes)
    not_matched(doji_umbrella.HANGING_MAN, shapes)


def test_an_inverted_hammer_does_not_bound_its_upper_shadow_from_above() -> None:
    """Check that Morris's "usually" upper bound is not enforced (§7.1.9).

    Morris writes the upper shadow is "usually no more than two times" the body.
    §7.1.9 reads that as a tendency, not a requirement, the same way §7.3.14
    reads Nison's "(usually a small one)", so a shadow past two bodies still
    matches. Enforcing it would confine the body to between 30% and 33.3% of the
    range and leave the pattern all but unreachable, and it would contradict
    Nison, who describes the line by its *long* upper shadow.
    """
    values = matched(doji_umbrella.INVERTED_HAMMER, [*background(120.0), INVERTED_HAMMER_SHAPE])
    assert values["pat_inverted_hammer_dir"] == outputs.BULLISH

    past_two_bodies: Shape = (57.0, 150.1, 50.0, 88.0)
    assert matched(doji_umbrella.INVERTED_HAMMER, [*background(120.0), past_two_bodies])


def test_an_inverted_hammer_still_ends_up_with_a_long_upper_shadow() -> None:
    """Check that the long upper shadow is implied rather than asked for.

    A short body under a third of the range and a lower shadow under a tenth of
    it leave the upper shadow at least 56.7% of the range, which is why §7.1.9
    can drop Morris's bound and still describe the line Nison describes.
    """
    shape: Shape = (57.0, 150.1, 50.0, 88.0)
    open_, high, low, close = shape
    candle_range = high - low
    upper = high - max(open_, close)
    assert upper / candle_range >= 0.567


def test_a_gravestone_doji_in_a_downtrend_is_also_an_inverted_hammer() -> None:
    """Check the overlap §7.1.9 accepts and explains.

    A doji body is a short body, so once Morris's upper bound is read as a
    tendency a bodyless gravestone shape in a downtrend satisfies what is left of
    §7.1.9. The section records that this agrees with the sources rather than
    breaking them: Nison separates the inverted hammer from the shooting star by
    preceding trend alone, and Morris notes a gravestone at a low can read
    bullish. The two patterns carry opposite directions, which is what lets a
    consumer tell them apart on the same bar.
    """
    downtrend = [*background(120.0), BODYLESS_GRAVESTONE]

    inverted = matched(doji_umbrella.INVERTED_HAMMER, downtrend)
    gravestone = matched(doji_umbrella.GRAVESTONE_DOJI, downtrend)
    assert inverted["pat_inverted_hammer_dir"] == outputs.BULLISH
    assert gravestone["pat_gravestone_doji_dir"] == outputs.BEARISH


def test_the_inverted_hammer_band_is_bounded_from_both_sides() -> None:
    """Check that §7.1.9's rules 2 and 3 pull against each other, as written.

    Rule 2 wants a small body and rule 3 wants an upper shadow no larger than two
    of them, so a bar with the textbook look — a tiny body under a very long top
    — fails rule 3 rather than passing. The bar below has a body of 3.00 and an
    upper shadow of 47.00, and it is rejected.
    """
    tiny_bodied: Shape = (100.0, 150.0, 50.0, 103.0)
    not_matched(doji_umbrella.INVERTED_HAMMER, [*background(120.0), tiny_bodied])


# --- §7.1.10: the one two-bar section in this group -------------------------

SHOOTING_STAR_SHAPE: Shape = (65.0, 150.0, 50.0, 55.0)
"""Body 10.00 in a range of 100, upper shadow 85.00, lower shadow 5.00.

Short body, bare lower shadow (at most 10.00), and an upper shadow past three
bodies (30.00). It opens at 65.00, above the previous bar's close.
"""

STAR_PRIOR_BAR: Shape = (60.0, 62.0, 58.0, 60.0)
"""The bar the gap is measured against, closing at 60.00 with a midpoint of 60.00."""


def test_a_shooting_star_needs_the_previous_bar_for_its_gap() -> None:
    """Check §7.1.10, whose span is two bars because the gap needs one to measure.

    The trend is read on the first of the two, so the filler sits at 50.00 and
    the prior bar's midpoint of 60.00 is above the average of 51.00. The star
    then opens at 65.00 against a previous close of 60.00, which is §1.3's plain
    open gap — the kind Morris's wording fixes, since he writes only that prices
    gap open.
    """
    shapes = [*background(50.0), STAR_PRIOR_BAR, SHOOTING_STAR_SHAPE]
    values = matched(doji_umbrella.SHOOTING_STAR, shapes)
    assert values["pat_shooting_star_dir"] == outputs.BEARISH

    # Opening at the previous close instead of above it removes the gap alone.
    no_gap: Shape = (60.0, 145.0, 45.0, 50.0)
    not_matched(doji_umbrella.SHOOTING_STAR, [*background(50.0), STAR_PRIOR_BAR, no_gap])


def test_a_shooting_star_reads_the_trend_on_the_first_of_its_two_bars() -> None:
    """Check §3.1's comparison bar where a pattern spans more than one bar.

    Filler at 70.00 leaves the prior bar's midpoint of 60.00 below the average,
    so the trend is down and the pattern cannot hold however well the star is
    shaped. Judging the trend on the star itself instead would read a different
    bar and could reach the opposite answer.
    """
    shapes = [*background(70.0), STAR_PRIOR_BAR, SHOOTING_STAR_SHAPE]
    not_matched(doji_umbrella.SHOOTING_STAR, shapes)


# --- §7.1.11 and §7.2.1: the two that the standard had to separate -----------

SPINNING_TOP_SHAPE: Shape = (100.0, 112.0, 93.0, 105.0)
"""Body 5.00 with shadows of 7.00 — longer than the body, but under two of them."""

HIGH_WAVE_SHAPE: Shape = (100.0, 120.0, 85.0, 105.0)
"""Body 5.00 with shadows of 15.00, which is past §2.4's multiple of two."""


def test_a_spinning_top_only_needs_shadows_longer_than_its_body() -> None:
    """Check §7.1.11's strict comparison, written out rather than routed to §2.2.

    §2.2's short-body threshold was derived from this very rule, so asking for it
    as well would apply one condition twice. The bar below has shadows of 7.00
    against a body of 5.00 and holds; equal shadows and body would not, because
    the source reads "greater than".
    """
    values = matched(doji_umbrella.SPINNING_TOP, [SPINNING_TOP_SHAPE])
    assert values["pat_spinning_top_dir"] == outputs.DIRECTIONLESS

    equal_to_the_body: Shape = (100.0, 110.0, 95.0, 105.0)
    not_matched(doji_umbrella.SPINNING_TOP, [equal_to_the_body])


def test_a_high_wave_is_a_spinning_top_with_shadows_twice_as_long() -> None:
    """Check §7.2.1's boundary against §7.1.11, and the nesting it creates.

    The two are described identically in the sources, so the standard separated
    them by the multiple: longer than the body for one, at least two bodies for
    the other. Anything matching §7.2.1 therefore matches §7.1.11 as well.
    """
    assert matched(body_shadow.HIGH_WAVE, [HIGH_WAVE_SHAPE])
    assert matched(doji_umbrella.SPINNING_TOP, [HIGH_WAVE_SHAPE])

    not_matched(body_shadow.HIGH_WAVE, [SPINNING_TOP_SHAPE])
    assert matched(doji_umbrella.SPINNING_TOP, [SPINNING_TOP_SHAPE])


# --- §7.2.2 to §7.2.6: the remaining shapes ---------------------------------

MARUBOZU_SHAPE: Shape = (100.0, 152.0, 98.0, 150.0)
"""Body 50.00 in a range of 54.00 with shadows of 2.00 on both ends.

Long (over 27.00) and both shadows inside §2.5's tenth of the range (5.40).
"""

WHITE_CLOSING_MARUBOZU: Shape = (100.0, 152.0, 80.0, 150.0)
"""White, body 50.00 in a range of 72.00: bare at the close (2.00), not at the open."""

BLACK_CLOSING_MARUBOZU: Shape = (150.0, 170.0, 98.0, 100.0)
"""Black, the same body: bare at the close, which for a black bar is the low end."""


def test_a_marubozu_is_a_long_body_with_neither_shadow() -> None:
    """Check §7.2.2, whose "no shadow" is §2.5's very short shadow by §4.2."""
    values = matched(body_shadow.MARUBOZU, [MARUBOZU_SHAPE])
    assert values["pat_marubozu_dir"] == outputs.DIRECTIONLESS

    not_matched(body_shadow.MARUBOZU, [WHITE_CLOSING_MARUBOZU])


def test_a_closing_marubozu_asks_only_about_the_end_it_closes_on() -> None:
    """Check §7.2.3, the one section here whose condition depends on the colour."""
    assert matched(body_shadow.CLOSING_MARUBOZU, [WHITE_CLOSING_MARUBOZU])
    assert matched(body_shadow.CLOSING_MARUBOZU, [BLACK_CLOSING_MARUBOZU])

    # A white bar bare at the *open* end is an opening marubozu, which §7.2.3
    # does not cover: TA-Lib has no function for it and the standard has no
    # section for it either.
    white_bare_at_the_open: Shape = (100.0, 170.0, 98.0, 150.0)
    not_matched(body_shadow.CLOSING_MARUBOZU, [white_bare_at_the_open])


def test_a_long_line_asks_for_a_long_body_and_nothing_else() -> None:
    """Check §7.2.5, and that no shadow requirement crept in from TA-Lib.

    The bar below has shadows of 20.00 on both ends — far past §2.5 — and still
    holds, because Morris's Long Days passage says nothing about shadows.
    """
    long_with_shadows: Shape = (100.0, 170.0, 80.0, 150.0)
    values = matched(body_shadow.LONG_LINE, [long_with_shadows])
    assert values["pat_long_line_dir"] == outputs.DIRECTIONLESS

    # Body 27.00 against a range of 54.00 is exactly half, and §2.1 is strict.
    exactly_half: Shape = (100.0, 152.0, 98.0, 127.0)
    not_matched(body_shadow.LONG_LINE, [exactly_half])


def test_a_short_line_is_the_same_measurement_with_a_maximum() -> None:
    """Check §7.2.6 at §2.2's threshold, which is strict for the same reason."""
    assert matched(body_shadow.SHORT_LINE, [SPINNING_TOP_SHAPE])

    # Body 18.00 against a range of 54.00 is exactly a third.
    exactly_a_third: Shape = (100.0, 152.0, 98.0, 118.0)
    not_matched(body_shadow.SHORT_LINE, [exactly_a_third])


def test_a_belt_hold_opens_at_the_extreme_of_its_own_range() -> None:
    """Check §7.2.4's two sides, each after the trend its side requires."""
    bullish = matched(body_shadow.BELT_HOLD, [*background(150.0), MARUBOZU_SHAPE])
    assert bullish["pat_belt_hold_dir"] == outputs.BULLISH

    bearish_shape: Shape = (150.0, 152.0, 80.0, 100.0)
    bearish = matched(body_shadow.BELT_HOLD, [*background(100.0), bearish_shape])
    assert bearish["pat_belt_hold_dir"] == outputs.BEARISH

    # The bullish side after an uptrend, and the bearish side after a downtrend,
    # are both rejected on the trend alone.
    not_matched(body_shadow.BELT_HOLD, [*background(100.0), MARUBOZU_SHAPE])
    not_matched(body_shadow.BELT_HOLD, [*background(150.0), bearish_shape])


def test_the_two_sides_of_belt_hold_are_not_mirror_images() -> None:
    """Check §7.2.4's asymmetry, which comes from the sources and not from us.

    The bearish bar just tested carries a lower shadow of 20.00 and still holds,
    because Nison never says where a bearish belt-hold closes. Its mirror — a
    white bar with an upper shadow of 20.00 — is rejected, because on the bullish
    side he does say: at or near the session high.
    """
    mirrored_bullish: Shape = (100.0, 170.0, 98.0, 150.0)
    not_matched(body_shadow.BELT_HOLD, [*background(150.0), mirrored_bullish])


# --- §5.4 and §5.5: where a confirmation is written -------------------------


def test_a_confirmation_lands_on_the_bar_after_the_match() -> None:
    """Check §5.4 on the pattern the general rule of §5.5 applies to.

    The hammer bar closes at 110.00 and the bar after it closes at 120.00, so the
    confirmation belongs to that later bar. Writing it back onto the hammer would
    make the value at index `t` depend on a candle after `t`.
    """
    following: Shape = (110.0, 125.0, 108.0, 120.0)
    values = run(doji_umbrella.HAMMER, [*background(100.0), UMBRELLA_SHAPE, following])

    assert values[-2]["pat_hammer"] == outputs.MATCHED
    assert values[-2]["pat_hammer_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hammer"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hammer_confirm"] == outputs.MATCHED


def test_one_bar_can_both_match_and_confirm_the_bar_before_it() -> None:
    """Check that §5.4 separates the two keys without making them exclusive.

    The filler sits at 200.00 so both umbrella bars are well below their average
    and both match. The second closes at 120.00, above the first bar's 110.00, so
    it confirms the first while matching in its own right. Reading `_confirm` as
    "the pattern did not hold here" would misread this bar.
    """
    second_umbrella: Shape = (115.0, 122.0, 70.0, 120.0)
    values = run(doji_umbrella.HAMMER, [*background(200.0), UMBRELLA_SHAPE, second_umbrella])

    assert values[-2]["pat_hammer"] == outputs.MATCHED
    assert values[-2]["pat_hammer_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hammer"] == outputs.MATCHED
    assert values[-1]["pat_hammer_confirm"] == outputs.MATCHED


def test_a_degenerate_bar_cannot_confirm_the_match_before_it() -> None:
    """Check §5.5's degenerate-confirmation rule against §2.7's reason for it.

    The bar after the hammer has all four prices at 120.00, above the hammer's
    110.00 close, so the plain close comparison of §5.5 would confirm. §2.7 treats
    such a bar as a data error or a bar that never traded and keeps it out of a
    judgment, and §5.5 extends that to the confirming bar: a bar we refuse to
    judge on cannot be trusted to confirm either. The confirming bar sits outside
    the judgment window, so neither of §2.7's two guards reaches it.
    """
    degenerate: Shape = (120.0, 120.0, 120.0, 120.0)
    values = run(doji_umbrella.HAMMER, [*background(100.0), UMBRELLA_SHAPE, degenerate])

    assert values[-2]["pat_hammer"] == outputs.MATCHED
    assert values[-1]["pat_hammer_confirm"] == outputs.NOT_MATCHED


def test_the_same_bar_confirms_once_it_is_no_longer_degenerate() -> None:
    """Pin that the rule above turns on degeneracy alone, not on the close.

    This bar closes at the same 120.00 as the one before, and its high is one cent
    away, so the only thing that changed is that the range is no longer zero.
    """
    barely_alive: Shape = (120.0, 120.01, 120.0, 120.0)
    values = run(doji_umbrella.HAMMER, [*background(100.0), UMBRELLA_SHAPE, barely_alive])

    assert values[-2]["pat_hammer"] == outputs.MATCHED
    assert values[-1]["pat_hammer_confirm"] == outputs.MATCHED


def test_a_confirmation_that_does_not_arrive_leaves_the_key_at_zero() -> None:
    """Check §5.5's one-bar deadline: a later move does not confirm retroactively."""
    lower: Shape = (110.0, 112.0, 100.0, 105.0)
    much_higher: Shape = (105.0, 200.0, 104.0, 190.0)
    values = run(doji_umbrella.HAMMER, [*background(100.0), UMBRELLA_SHAPE, lower, much_higher])

    assert values[-3]["pat_hammer"] == outputs.MATCHED
    assert values[-2]["pat_hammer_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_hammer_confirm"] == outputs.NOT_MATCHED


def test_hanging_man_and_inverted_hammer_use_the_conditions_their_sources_give() -> None:
    """Check §5.5's table: these two are confirmed against the body, not the close.

    A hanging man is confirmed by a close below the body's lower end, 105.00
    here, so a close at 106.00 — lower than the pattern bar's close of 110.00 and
    enough for the general rule — is not enough for this one. An inverted hammer
    is confirmed by a close above the body's upper end, 88.00, and the same
    contrast holds there.
    """
    below_the_close: Shape = (110.0, 111.0, 105.5, 106.0)
    values = run(doji_umbrella.HANGING_MAN, [*background(80.0), UMBRELLA_SHAPE, below_the_close])
    assert values[-2]["pat_hanging_man"] == outputs.MATCHED
    assert values[-1]["pat_hanging_man_confirm"] == outputs.NOT_MATCHED

    below_the_body: Shape = (110.0, 111.0, 100.0, 104.0)
    values = run(doji_umbrella.HANGING_MAN, [*background(80.0), UMBRELLA_SHAPE, below_the_body])
    assert values[-1]["pat_hanging_man_confirm"] == outputs.MATCHED

    inside_the_body: Shape = (88.0, 89.0, 80.0, 87.0)
    values = run(
        doji_umbrella.INVERTED_HAMMER,
        [*background(120.0), INVERTED_HAMMER_SHAPE, inside_the_body],
    )
    assert values[-2]["pat_inverted_hammer"] == outputs.MATCHED
    assert values[-1]["pat_inverted_hammer_confirm"] == outputs.NOT_MATCHED

    above_the_body: Shape = (88.0, 95.0, 87.0, 94.0)
    values = run(
        doji_umbrella.INVERTED_HAMMER,
        [*background(120.0), INVERTED_HAMMER_SHAPE, above_the_body],
    )
    assert values[-1]["pat_inverted_hammer_confirm"] == outputs.MATCHED


def test_belt_hold_is_confirmed_in_whichever_direction_it_matched() -> None:
    """Check §5.5's general rule where one key carries both sides of a pattern."""
    higher: Shape = (150.0, 160.0, 149.0, 158.0)
    values = run(body_shadow.BELT_HOLD, [*background(150.0), MARUBOZU_SHAPE, higher])
    assert values[-2]["pat_belt_hold_dir"] == outputs.BULLISH
    assert values[-1]["pat_belt_hold_confirm"] == outputs.MATCHED

    bearish_shape: Shape = (150.0, 152.0, 80.0, 100.0)
    values = run(body_shadow.BELT_HOLD, [*background(100.0), bearish_shape, higher])
    assert values[-2]["pat_belt_hold_dir"] == outputs.BEARISH
    # The following bar closes at 158.00, above the pattern bar's 100.00, so a
    # bearish match is not confirmed by it.
    assert values[-1]["pat_belt_hold_confirm"] == outputs.NOT_MATCHED


def test_the_patterns_without_a_confirmation_grade_never_raise_the_key() -> None:
    """Check that only the five sections with a grade write the fourth key.

    §5.1 keeps the key on every pattern, but §7.1 and §7.2 give twelve of the
    seventeen no confirmation at all, and those twelve must leave it at 0.0 for
    the whole series rather than borrowing the general rule of §5.5.
    """
    confirming = {
        "pat_hammer",
        "pat_hanging_man",
        "pat_inverted_hammer",
        "pat_shooting_star",
        "pat_belt_hold",
    }
    candles = series(VARIED)
    for spec in REGISTERED_SPECS:
        if spec.name in confirming:
            continue
        key = f"{spec.name}_confirm"
        values = spec.compute_vectorized(candles)[spec.min_history - 1 :]
        assert all(value[key] == outputs.NOT_MATCHED for value in values), spec.name


def test_a_shooting_star_is_confirmed_by_a_lower_close() -> None:
    """Check §5.5's general rule on the fifth confirming pattern of this group.

    The star closes at 55.00, so the bar after it confirms by closing lower and
    does not confirm by closing higher.
    """
    shapes = [*background(50.0), STAR_PRIOR_BAR, SHOOTING_STAR_SHAPE]

    lower: Shape = (55.0, 56.0, 40.0, 45.0)
    values = run(doji_umbrella.SHOOTING_STAR, [*shapes, lower])
    assert values[-2]["pat_shooting_star"] == outputs.MATCHED
    assert values[-2]["pat_shooting_star_confirm"] == outputs.NOT_MATCHED
    assert values[-1]["pat_shooting_star_confirm"] == outputs.MATCHED

    higher: Shape = (55.0, 70.0, 54.0, 65.0)
    values = run(doji_umbrella.SHOOTING_STAR, [*shapes, higher])
    assert values[-1]["pat_shooting_star_confirm"] == outputs.NOT_MATCHED


# --- §4.1: the relation the foundation was missing --------------------------


def bodies(first: tuple[float, float], second: tuple[float, float]) -> tuple[Candle, Candle]:
    """Return two bars whose real bodies span the given (open, close) pairs."""
    return (
        make_candle(0, first[0], max(first) + 5.0, min(first) - 5.0, first[1]),
        make_candle(1, second[0], max(second) + 5.0, min(second) - 5.0, second[1]),
    )


def test_an_engulfment_may_share_one_body_end_but_not_both() -> None:
    """Check §4.1, the only place the sources fixed an inequality's strictness.

    Morris allows either the tops or the bottoms of the two bodies to be equal
    and excludes only both at once, so both comparisons are non-strict and one
    exclusion carries the whole rule.
    """
    previous, current = bodies((105.0, 100.0), (99.0, 106.0))
    assert inequalities.engulf(previous, current)

    shared_bottom = bodies((105.0, 100.0), (100.0, 106.0))
    assert inequalities.engulf(*shared_bottom)

    shared_top = bodies((105.0, 100.0), (99.0, 105.0))
    assert inequalities.engulf(*shared_top)

    identical = bodies((105.0, 100.0), (100.0, 105.0))
    assert not inequalities.engulf(*identical)

    inside = bodies((105.0, 100.0), (101.0, 104.0))
    assert not inequalities.engulf(*inside)


def test_containment_is_the_same_relation_read_the_other_way_round() -> None:
    """Check §4.1's second form, which Harami uses and Engulfing's rule mirrors."""
    previous, current = bodies((110.0, 100.0), (102.0, 108.0))
    assert inequalities.contain(previous, current)
    assert not inequalities.engulf(previous, current)

    shared_top = bodies((110.0, 100.0), (102.0, 110.0))
    assert inequalities.contain(*shared_top)

    identical = bodies((110.0, 100.0), (100.0, 110.0))
    assert not inequalities.contain(*identical)

    outside = bodies((110.0, 100.0), (99.0, 111.0))
    assert not inequalities.contain(*outside)


# --- §1.4: the upper-bound half of the shadow comparison --------------------


def test_the_two_shadow_comparisons_answer_a_bodyless_bar_differently() -> None:
    """Check §1.4's split, stated on the numbers rather than through a pattern.

    A positive shadow against a zero body satisfies a lower bound and fails an
    upper one. A zero shadow against a zero body fails both.
    """
    assert primitives.shadow_reaches_multiple(10.0, 0.0, 2.0)
    assert not primitives.shadow_within_multiple(10.0, 0.0, 2.0)

    assert not primitives.shadow_reaches_multiple(0.0, 0.0, 2.0)
    assert not primitives.shadow_within_multiple(0.0, 0.0, 2.0)

    # With a body present both are ordinary comparisons that allow equality.
    assert primitives.shadow_within_multiple(20.0, 10.0, 2.0)
    assert not primitives.shadow_within_multiple(20.1, 10.0, 2.0)
    assert primitives.shadow_reaches_multiple(20.0, 10.0, 2.0)
    assert not primitives.shadow_reaches_multiple(19.9, 10.0, 2.0)
