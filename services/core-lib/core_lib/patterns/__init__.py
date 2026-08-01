"""Provide the candlestick pattern layer defined by the pattern standard.

`docs/references/candlestick_pattern_calc_spec.md` owns the rules. This package
implements its foundation: the shared candle primitives of §1, the seven scales
of §2, the prior-trend judgment of §3, the four-key output contract of §5, the
warm-up formulas of §6, and the spec and registry the sixty-one patterns of §7
register into.

The patterns themselves are not here yet. This layer is what they will be built
out of, and it is deliberately a separate changeset from them so a regression can
be traced to one or the other.
"""

from .outputs import (
    BEARISH,
    BOUNDARY_STRENGTH,
    BULLISH,
    DIRECTIONLESS,
    FULL_STRENGTH,
    MATCHED,
    NAME_PREFIX,
    NOT_MATCHED,
    assert_pattern_name,
    match_outputs,
    no_match_outputs,
    output_keys,
    undetermined_outputs,
)
from .registry import (
    PatternRegistry,
    PatternSeries,
    PatternSpec,
    PatternState,
    PatternValue,
)
from .trend import (
    DOWNTREND,
    NO_TREND,
    TREND_EMA_PERIOD,
    UPTREND,
    PriorTrendState,
    prior_trend,
    trend_ema,
)
from .warmup import min_history_for

__all__ = [
    "BEARISH",
    "BOUNDARY_STRENGTH",
    "BULLISH",
    "DIRECTIONLESS",
    "DOWNTREND",
    "FULL_STRENGTH",
    "MATCHED",
    "NAME_PREFIX",
    "NOT_MATCHED",
    "NO_TREND",
    "TREND_EMA_PERIOD",
    "UPTREND",
    "PatternRegistry",
    "PatternSeries",
    "PatternSpec",
    "PatternState",
    "PatternValue",
    "PriorTrendState",
    "assert_pattern_name",
    "match_outputs",
    "min_history_for",
    "no_match_outputs",
    "output_keys",
    "prior_trend",
    "trend_ema",
    "undetermined_outputs",
]
