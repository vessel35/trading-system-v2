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

Two of those surroundings are wider than one bar and one number. §5.5 sets the
confirmation deadline at one bar for fifty-nine sections and at three for the two
Hikkake sections, so a rule carries its deadline and both paths keep a match open
until it is confirmed or the deadline runs out. And §7.5.5 admits a span of four
to seven bars rather than a fixed one, so a rule may carry a longest span as well
as the shortest; both paths then try the admissible spans shortest first and take
the first that holds, which is §7.5.5's own rule for not matching twice on one
bar. Every other section leaves both fields at their defaults and sees exactly
the behaviour it saw before they existed.

The two paths are built from the same rule but not from each other. The batch
path judges each index from a slice of the series; the incremental path judges
from a `deque` it advances one confirmed candle at a time. Neither calls the
other, so `test_pattern_single_candle.py` comparing them is a real check rather
than a tautology.

Section numbers in this module are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections import deque
from collections.abc import Callable, Mapping, Sequence
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

The window carries one of the rule's admissible spans — `bar_count` candles for
every section but §7.5.5, which is offered four to seven in turn — and its last
entry is always the bar the verdict lands on. The trend is `UPTREND`,
`DOWNTREND`, or `NO_TREND` when the rule asks for one and NaN when it does not,
so a rule that reads the trend without declaring it compares against NaN and
never matches. §3.1 judges the trend on the window's *first* bar, so a rule
offered several spans receives the trend belonging to the span it is being asked
about, not one shared figure.
"""

Confirm = Callable[[Sequence[Candle], float, Candle], bool]
"""Ask whether a later bar confirms a match (§5.5).

Takes the matched window, the direction that match reported, and the candidate
bar. The candidate is the bar immediately after the match for every pattern
except the two Hikkake sections, where `confirm_within_bars` opens the question
on each of the three bars following the match until one of them answers yes.
"""


@dataclass(frozen=True, slots=True)
class PatternRule:
    """One §7 section, reduced to what both execution paths need from it."""

    name: str
    bar_count: int
    requires_trend: bool
    judge: Judge
    confirm: Confirm | None = None

    confirm_within_bars: int = 1
    """§5.5's deadline, counted in bars after the match.

    One for fifty-nine sections, because §5.5 sets the general deadline there.
    Three for §7.5.9 and §7.5.10, where Chesler gives the figure himself. §6
    keeps this out of `min_history` in either case: a confirmation is a later
    event on a later bar, not a longer warm-up.

    Inside the deadline the confirmation lands on the *first* bar that satisfies
    the rule, and a degenerate bar (§5.5, §2.7) cannot be that bar while still
    spending one of the bars allowed.
    """

    longest_bar_count: int | None = None
    """The longest span the section admits, when it admits more than one.

    None means the span is fixed at `bar_count`, which is every section but
    §7.5.5 Rising/Falling Three Methods. There `bar_count` is the shortest form —
    `n = 2`, four bars — and this is the longest, `n = 5` at seven. §6 derives the
    warm-up from the shortest deliberately, so the first bar able to hold the
    shortest form is not made to wait for the bar where all five could be judged.
    """

    def __post_init__(self) -> None:
        if self.confirm_within_bars < 1:
            raise ValueError("confirm_within_bars must be at least one bar")
        if self.longest_bar_count is not None and self.longest_bar_count < self.bar_count:
            raise ValueError("longest_bar_count must not be shorter than bar_count")

    @property
    def min_history(self) -> int:
        """Return §6's warm-up length for this rule."""
        return min_history_for(self.bar_count, requires_trend=self.requires_trend)

    @property
    def spans(self) -> tuple[int, ...]:
        """Return the admissible spans, shortest first.

        A single span for sixty sections. For §7.5.5, the five spans `n = 2`
        through `n = 5` produce, in the order that section's own convention asks
        them to be tried: the smallest `n` that holds is the one adopted, so no
        bar reports the pattern twice.
        """
        longest = self.bar_count if self.longest_bar_count is None else self.longest_bar_count
        return tuple(range(self.bar_count, longest + 1))


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


@dataclass(frozen=True, slots=True)
class _Judged:
    """A match together with the window it was found on.

    The window travels with the match because a confirmation is asked about it
    later, on a different bar, and because §7.5.5's window is not always the same
    length as the next section's. Recomputing the slice at confirmation time
    would have to guess which span matched.
    """

    match: Match
    window: tuple[Candle, ...]


def judge_series(rule: PatternRule, candles: Sequence[Candle]) -> list[PatternValue]:
    """Compute the whole batch series for one rule.

    Judgment and placement are two passes on purpose. §5.4 puts a confirmation on
    a later bar than the match it confirms, so the second pass reads the first
    pass a few indexes back — and only backwards, which is the property that
    keeps a value at index `t` free of anything after `t`.
    """
    spans = rule.spans
    trends = _trends_by_span(rule, candles, spans)
    verdicts = [_judge_at(rule, candles, index, spans, trends) for index in range(len(candles))]

    values: list[PatternValue] = []
    for index in range(len(candles)):
        if index + 1 < rule.min_history:
            values.append(undetermined_outputs(rule.name))
            continue
        confirmed = _confirms_an_earlier_match(rule, candles, index, verdicts)
        values.append(_outputs(rule, verdicts[index], confirmed=confirmed))
    return values


def _trends_by_span(
    rule: PatternRule,
    candles: Sequence[Candle],
    spans: Sequence[int],
) -> Mapping[int, Sequence[float]]:
    """Return §3's trend series for each span the rule admits.

    §3.1 reads the trend on the pattern's first day, which sits `span - 1` bars
    behind the judged bar, so a rule offered several spans needs one series per
    span rather than one series shared. The mapping holds a single entry for
    every section but §7.5.5, and is empty when the rule reads no trend at all.
    """
    if not rule.requires_trend:
        return {}
    return {span: prior_trend(candles, span) for span in spans}


def _judge_at(
    rule: PatternRule,
    candles: Sequence[Candle],
    index: int,
    spans: Sequence[int],
    trends: Mapping[int, Sequence[float]],
) -> _Judged | None:
    if index + 1 < rule.min_history:
        return None
    for span in spans:
        start = index - span + 1
        if start < 0:
            break
        window = candles[start : index + 1]
        # §2.7 wants this gate before the conditions, not only inside the scales: a
        # rule using a scale negatively would read a degenerate bar's False as a
        # satisfied condition. It is applied per span, because a bar too old to
        # enter the shortest window is not part of that form's judgment.
        if any_degenerate(window):
            continue
        trend = trends[span][index] if rule.requires_trend else NAN
        match = rule.judge(window, trend)
        if match is not None:
            return _Judged(match, tuple(window))
    return None


def _confirms_an_earlier_match(
    rule: PatternRule,
    candles: Sequence[Candle],
    index: int,
    verdicts: Sequence[_Judged | None],
) -> bool:
    """Return whether this bar confirms a match still inside its deadline (§5.5, §5.4).

    The deadline is one bar for fifty-nine sections, where this reduces to the
    previous bar and nothing else. Where it is three, the confirmation belongs to
    the first bar that satisfies the rule, so a match already confirmed earlier is
    skipped rather than confirmed a second time.
    """
    if rule.confirm is None:
        return False
    for offset in range(1, rule.confirm_within_bars + 1):
        matched_at = index - offset
        if matched_at < 0:
            break
        judged = verdicts[matched_at]
        if judged is None:
            continue
        already = range(matched_at + 1, index)
        if any(_confirmation_holds(rule, judged, candles[earlier]) for earlier in already):
            continue
        if _confirmation_holds(rule, judged, candles[index]):
            return True
    return False


def _confirmation_holds(rule: PatternRule, judged: _Judged, candle: Candle) -> bool:
    """Return whether one candidate bar confirms one match.

    A degenerate bar answers no whatever the rule would have said. §5.5 refuses a
    confirmation from a bar §2.7 will not judge on, and says why: the exclusion
    rests on the bar being untrustworthy rather than on a scale being undefined,
    so neither of §2.7's own two guards reaches this bar.
    """
    if rule.confirm is None or is_degenerate(candle):
        return False
    return rule.confirm(judged.window, judged.match.direction, candle)


def _outputs(rule: PatternRule, judged: _Judged | None, *, confirmed: bool) -> PatternValue:
    if judged is None:
        return no_match_outputs(rule.name, confirmed=confirmed)
    return match_outputs(
        rule.name,
        direction=judged.match.direction,
        strength=judged.match.strength,
        confirmed=confirmed,
    )


@dataclass(slots=True)
class _Pending:
    """A match waiting for confirmation, and how many bars it may still wait."""

    window: tuple[Candle, ...]
    direction: float
    bars_left: int


@dataclass(slots=True)
class PatternRuleState:
    """Judge one rule incrementally, one confirmed candle at a time.

    The state is the window of bars the pattern spans, the trend judgment when
    the rule asks for one, and the matches still waiting to be confirmed. A match
    enters that list with §5.5's deadline in bars and leaves it the moment a bar
    confirms it or the deadline runs out, so at a one-bar deadline the list holds
    at most the previous bar's match and behaves exactly as a single slot did.

    Both the storage and the work per candle are bounded by the rule's longest
    span, which a pattern's definition fixes and no registered parameter can
    grow. §7.5.5 is the one section where that longest span is not `bar_count`,
    and it keeps seven bars where its warm-up is counted from four.
    """

    rule: PatternRule
    min_history: int = field(init=False)
    _spans: tuple[int, ...] = field(init=False, repr=False)
    _seen: int = field(init=False, default=0, repr=False)
    _window: deque[Candle] = field(init=False, repr=False)
    _trends: tuple[PriorTrendState, ...] = field(init=False, repr=False)
    _pending: list[_Pending] = field(init=False, repr=False)
    _current: PatternValue = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.min_history = self.rule.min_history
        self._spans = self.rule.spans
        self._window = deque(maxlen=self._spans[-1])
        # One trend state per span, because §3.1 reads the trend on the window's
        # first bar and each span puts that bar somewhere else. They advance on
        # the same candle and agree on the average; what differs is how far back
        # each one looks, which is the whole of the difference §3.3 describes.
        self._trends = (
            tuple(PriorTrendState(span) for span in self._spans) if self.rule.requires_trend else ()
        )
        self._pending = []
        self._current = undetermined_outputs(self.rule.name)

    def reset(self) -> None:
        """Drop the window, the trend, and any pending confirmation."""
        self._seen = 0
        self._window.clear()
        for trend in self._trends:
            trend.reset()
        self._pending = []
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
        trends = tuple(trend.update(candle) for trend in self._trends)

        # The pending matches are read before this bar's own match joins them:
        # they were made on earlier bars, and this is a bar that may confirm one.
        confirmed = self._advance_pending(candle)

        if not self.warmed_up:
            self._current = undetermined_outputs(self.rule.name)
            return self._current

        judged = self._judge(trends)
        if judged is not None and self.rule.confirm is not None:
            self._pending.append(
                _Pending(judged.window, judged.match.direction, self.rule.confirm_within_bars)
            )
        self._current = _outputs(self.rule, judged, confirmed=confirmed)
        return self._current

    def current(self) -> PatternValue:
        """Return the latest four outputs, NaN-shaped while still warming up."""
        return self._current

    def _judge(self, trends: Sequence[float]) -> _Judged | None:
        """Judge the admissible spans shortest first and report the first that holds."""
        bars = tuple(self._window)
        for position, span in enumerate(self._spans):
            if len(bars) < span:
                break
            window = bars[len(bars) - span :]
            if any_degenerate(window):
                continue
            trend = trends[position] if self._trends else NAN
            match = self.rule.judge(window, trend)
            if match is not None:
                return _Judged(match, window)
        return None

    def _advance_pending(self, candle: Candle) -> bool:
        """Confirm what this bar confirms and drop what has run out of bars.

        A match leaves the list on the first bar that satisfies the rule, which is
        how §5.5's "inside the deadline" reads: the confirmation is one event, not
        one per remaining bar. A degenerate bar confirms nothing and still spends
        one of the bars allowed, because the deadline is counted in bars.
        """
        if not self._pending or self.rule.confirm is None:
            return False
        confirmed = False
        degenerate = is_degenerate(candle)
        still_waiting: list[_Pending] = []
        for pending in self._pending:
            if not degenerate and self.rule.confirm(pending.window, pending.direction, candle):
                confirmed = True
                continue
            pending.bars_left -= 1
            if pending.bars_left > 0:
                still_waiting.append(pending)
        self._pending = still_waiting
        return confirmed


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
