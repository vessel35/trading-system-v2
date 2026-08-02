"""Turn one §7 judgment rule into the two execution paths a pattern spec needs.

Every section of §7 has the same shape. It fixes how many bars the pattern spans,
says whether §3's prior trend is part of the judgment, lists numbered conditions
over that window, and — for the patterns whose sources ask for it — states what
the following bar must do to confirm. Everything around that list is identical
across all sixty-one: §2.7's degenerate gate runs before any condition is looked
at, §5.1's four keys carry the verdict, §5.3 keeps NaN inside the warm-up window,
and §5.4 places a confirmation on the bar it happened on instead of writing it
back onto the bar that matched.

So a pattern is a `PatternRule` here — a name, a span, a trend requirement, the
judgment, and a confirmation rule when the standard gives one — and this module
supplies everything around it exactly once. Sixty-one hand-written state classes
would each be a chance to get the surroundings wrong in a different way.

The two paths are built from the same rule but not from each other. The batch
path judges each index from a slice of the series; the incremental path judges
from a `deque` it advances one confirmed candle at a time. Neither calls the
other, so `test_pattern_single_candle.py` comparing them is a real check rather
than a tautology.
"""

from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from functools import partial

from core_lib.indicators.primitives import NAN
from core_lib.types import Candle

from .outputs import (
    BEARISH,
    BULLISH,
    FULL_STRENGTH,
    match_outputs,
    no_match_outputs,
    undetermined_outputs,
)
from .primitives import any_degenerate, is_degenerate
from .registry import PatternSpec, PatternValue
from .trend import PriorTrendState, prior_trend
from .warmup import min_history_for

STANDARD_VERSION = "1.0.0"
"""The edition of `candlestick_pattern_calc_spec.md` these rules were written against."""


@dataclass(frozen=True, slots=True)
class Match:
    """One bar's verdict when a pattern held there.

    `direction` is §5.1's second key and `strength` its third. Strength is full
    unless §5.6's one boundary case applies, which is an engulfment or a
    containment with exactly one body end coinciding, so a rule that cannot
    reach that case leaves the default alone.
    """

    direction: float
    strength: float = FULL_STRENGTH


Judge = Callable[[Sequence[Candle], float], Match | None]
"""Judge one window: the bars the pattern spans and the §3 trend, oldest bar first.

The window carries exactly `bar_count` candles and its last entry is the bar the
verdict lands on. The trend is `UPTREND`, `DOWNTREND`, or `NO_TREND` when the
rule asks for one and NaN when it does not, so a rule that reads the trend
without declaring it compares against NaN and never matches.
"""

Confirm = Callable[[Sequence[Candle], float, Candle], bool]
"""Ask whether the bar after a match confirms it (§5.5).

Takes the matched window, the direction that match reported, and the following
bar. §5.5 sets the deadline at one bar for every pattern except the two Hikkake
sections, whose sources give three.
"""


@dataclass(frozen=True, slots=True)
class PatternRule:
    """One §7 section, reduced to what both execution paths need from it."""

    name: str
    bar_count: int
    requires_trend: bool
    judge: Judge
    confirm: Confirm | None = None

    @property
    def min_history(self) -> int:
        """Return §6's warm-up length for this rule."""
        return min_history_for(self.bar_count, requires_trend=self.requires_trend)


def confirms_by_close_direction(
    window: Sequence[Candle],
    direction: float,
    following: Candle,
) -> bool:
    """Apply §5.5's general confirmation: the next close moves the pattern's way.

    The standard settles on this form for every pattern whose sources graded
    confirmation without saying what it is. Hanging Man and Inverted Hammer are
    not among them — their sources name the condition — so those two sections
    carry their own rule instead of calling this.
    """
    last_close = window[-1].close
    if direction == BULLISH:
        return following.close > last_close
    if direction == BEARISH:
        return following.close < last_close
    return False


def _confirms_when_graded(
    graded: float,
    window: Sequence[Candle],
    direction: float,
    following: Candle,
) -> bool:
    """Apply §5.5's general rule on the one side of a section a source graded.

    Morris grades the two sides of a section separately and marks one of them
    `No` in sixteen sections of §7. §5.5 rules that a `No` side computes no
    confirmation, so a match on that side leaves the key at 0.0 while the graded
    side goes on to the ordinary close comparison.

    Written as a plain function taking the graded direction first so each rule
    can bind it with `partial`, which keeps the graded side visible at the
    definition rather than hidden in a closure.
    """
    if direction != graded:
        return False
    return confirms_by_close_direction(window, direction, following)


CONFIRMS_BEARISH_SIDE_ONLY: Confirm = partial(_confirms_when_graded, BEARISH)
"""§5.5 for a section graded on its bearish side and `No` on its bullish side.

Every asymmetrically graded section in §7 is graded this way round, so there is
no bullish-only counterpart to name. `_confirms_when_graded` still takes the
graded side as a parameter, so one appears the moment a section needs it.
"""


def judge_series(rule: PatternRule, candles: Sequence[Candle]) -> list[PatternValue]:
    """Compute the whole batch series for one rule.

    Judgment and placement are two passes on purpose. §5.4 puts a confirmation on
    a later bar than the match it confirms, so the second pass reads the first
    pass one index back — and only backwards, which is the property that keeps a
    value at index `t` free of anything after `t`.
    """
    trends = prior_trend(candles, rule.bar_count) if rule.requires_trend else [NAN] * len(candles)
    verdicts = [_judge_at(rule, candles, index, trends) for index in range(len(candles))]

    values: list[PatternValue] = []
    for index in range(len(candles)):
        if index + 1 < rule.min_history:
            values.append(undetermined_outputs(rule.name))
            continue
        confirmed = _confirms_previous(rule, candles, index, verdicts)
        values.append(_outputs(rule, verdicts[index], confirmed=confirmed))
    return values


def _judge_at(
    rule: PatternRule,
    candles: Sequence[Candle],
    index: int,
    trends: Sequence[float],
) -> Match | None:
    if index + 1 < rule.min_history:
        return None
    window = candles[index - rule.bar_count + 1 : index + 1]
    # §2.7 wants this gate before the conditions, not only inside the scales: a
    # rule using a scale negatively would read a degenerate bar's False as a
    # satisfied condition.
    if any_degenerate(window):
        return None
    return rule.judge(window, trends[index])


def _confirms_previous(
    rule: PatternRule,
    candles: Sequence[Candle],
    index: int,
    verdicts: Sequence[Match | None],
) -> bool:
    """Return whether this bar confirms the match on the bar before it (§5.5, §5.4)."""
    if rule.confirm is None or index == 0:
        return False
    previous = verdicts[index - 1]
    if previous is None:
        return False
    if is_degenerate(candles[index]):
        return False
    window = candles[index - rule.bar_count : index]
    return rule.confirm(window, previous.direction, candles[index])


def _outputs(rule: PatternRule, verdict: Match | None, *, confirmed: bool) -> PatternValue:
    if verdict is None:
        return no_match_outputs(rule.name, confirmed=confirmed)
    return match_outputs(
        rule.name,
        direction=verdict.direction,
        strength=verdict.strength,
        confirmed=confirmed,
    )


@dataclass(slots=True)
class PatternRuleState:
    """Judge one rule incrementally, one confirmed candle at a time.

    The state is the window of bars the pattern spans, the trend judgment when
    the rule asks for one, and a single pending slot holding the previous bar's
    match. That slot is what §5.5's one-bar deadline amounts to: it is read on
    the next candle and cleared whatever the answer, so nothing accumulates.

    Both the storage and the work per candle are bounded by `bar_count`, which a
    pattern's definition fixes and no registered parameter can grow.
    """

    rule: PatternRule
    min_history: int = field(init=False)
    _seen: int = field(init=False, default=0, repr=False)
    _window: deque[Candle] = field(init=False, repr=False)
    _trend: PriorTrendState | None = field(init=False, repr=False)
    _pending: tuple[tuple[Candle, ...], float] | None = field(init=False, repr=False)
    _current: PatternValue = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.min_history = self.rule.min_history
        self._window = deque(maxlen=self.rule.bar_count)
        self._trend = PriorTrendState(self.rule.bar_count) if self.rule.requires_trend else None
        self._pending = None
        self._current = undetermined_outputs(self.rule.name)

    def reset(self) -> None:
        """Drop the window, the trend, and any pending confirmation."""
        self._seen = 0
        self._window.clear()
        if self._trend is not None:
            self._trend.reset()
        self._pending = None
        self._current = undetermined_outputs(self.rule.name)

    @property
    def warmed_up(self) -> bool:
        """Return whether §6's warm-up length has been reached."""
        return self._seen >= self.min_history

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and replay warm-up candles one at a time."""
        self.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PatternValue:
        """Advance by exactly one confirmed candle and return this bar's four outputs."""
        self._seen += 1
        self._window.append(candle)
        trend = self._trend.update(candle) if self._trend is not None else NAN

        # The pending slot is read before it is overwritten: it holds the match
        # on the previous bar, and this bar is the one that may confirm it.
        confirmed = self._confirms_pending(candle)
        self._pending = None

        if not self.warmed_up:
            self._current = undetermined_outputs(self.rule.name)
            return self._current

        window = tuple(self._window)
        verdict = None if any_degenerate(window) else self.rule.judge(window, trend)
        if verdict is not None and self.rule.confirm is not None:
            self._pending = (window, verdict.direction)
        self._current = _outputs(self.rule, verdict, confirmed=confirmed)
        return self._current

    def current(self) -> PatternValue:
        """Return the latest four outputs, NaN-shaped while still warming up."""
        return self._current

    def _confirms_pending(self, candle: Candle) -> bool:
        if self._pending is None or self.rule.confirm is None:
            return False
        if is_degenerate(candle):
            return False
        window, direction = self._pending
        return self.rule.confirm(window, direction, candle)


def spec_for(rule: PatternRule) -> PatternSpec:
    """Build the registered spec for one rule, wiring both execution paths.

    Span and trend requirement reach the spec from the rule itself, so §6's
    warm-up length is derived from the same two numbers the judgment uses. That
    is what makes the agreement `PatternRegistry.register` checks structural
    rather than a matter of two declarations being kept in step by hand.
    """
    return PatternSpec(
        name=rule.name,
        params={},
        version=STANDARD_VERSION,
        bar_count=rule.bar_count,
        requires_trend=rule.requires_trend,
        _vectorized=partial(judge_series, rule),
        _state_factory=partial(PatternRuleState, rule),
    )
