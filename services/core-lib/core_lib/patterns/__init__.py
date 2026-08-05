"""Provide the candlestick pattern layer defined by the pattern standard.

`docs/references/candlestick_pattern_calc_spec.md` owns the rules. This package
implements its foundation — the shared candle primitives of §1, the seven scales
of §2, the prior-trend judgment of §3, the engulfment and containment relations
of §4.1, the four-key output contract of §5, the warm-up formulas of §6 — and the
patterns of §7 that are registered so far.

Fifty-one of the sixty-one are here: §7.1's doji family and umbrella lines,
§7.2's body-and-shadow shapes, §7.3's two-bar patterns, and §7.4's three-bar
ones, in `doji_umbrella.py`, `body_shadow.py`, `two_candle.py`, and
`three_candle.py`. `judgment.py` holds what every pattern shares, so a section
module carries its numbered rules and nothing else. The remaining ten arrive as
one more module pair and change nothing in this one.

Patterns keep their own registry and never enter `DEFAULT_REGISTRY`, so the
indicator standard's count of 89 systems is not touched by anything here.
"""

from .inequalities import contain, engulf
from .judgment import (
    STANDARD_VERSION,
    Match,
    PatternRule,
    PatternRuleState,
    confirms_by_close_direction,
    judge_series,
    spec_for,
)
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
from .specs import DEFAULT_PATTERN_REGISTRY, build_default_pattern_registry
from .talib_raw import (
    TALIB_CDL_PATTERN_COUNT,
    TALIB_DBL_MAX,
    TALIB_DEFAULT_PENETRATION_SENTINEL,
    TALIB_PENETRATION_DEFAULTS,
    TALIB_RAW_ALLOWED_VALUES,
    TALIB_RAW_BOUNDARY_MAGNITUDE,
    TALIB_RAW_CONFIRMATION_MAGNITUDE,
    TALIB_RAW_MATCH_MAGNITUDE,
    TALIB_RAW_ZERO,
    TALIB_SOURCE_VERSION,
    TALIB_UNDERLYING_VERSION_PREFIX,
    TalibPatternPort,
    TalibRawPatternSpec,
    outputs_from_talib_integer,
    resolve_talib_penetration,
    sparse_talib_integer_signals,
    talib_integer_from_outputs,
    talib_penetration_default,
    talib_penetration_lookback,
    validate_talib_adapter_outputs,
    validate_talib_raw_integer_series,
    validate_talib_version_pin,
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
    "DEFAULT_PATTERN_REGISTRY",
    "DIRECTIONLESS",
    "DOWNTREND",
    "FULL_STRENGTH",
    "MATCHED",
    "NAME_PREFIX",
    "NOT_MATCHED",
    "NO_TREND",
    "STANDARD_VERSION",
    "TALIB_CDL_PATTERN_COUNT",
    "TALIB_DBL_MAX",
    "TALIB_DEFAULT_PENETRATION_SENTINEL",
    "TALIB_PENETRATION_DEFAULTS",
    "TALIB_RAW_ALLOWED_VALUES",
    "TALIB_RAW_BOUNDARY_MAGNITUDE",
    "TALIB_RAW_CONFIRMATION_MAGNITUDE",
    "TALIB_RAW_MATCH_MAGNITUDE",
    "TALIB_RAW_ZERO",
    "TALIB_SOURCE_VERSION",
    "TALIB_UNDERLYING_VERSION_PREFIX",
    "TREND_EMA_PERIOD",
    "UPTREND",
    "Match",
    "PatternRegistry",
    "PatternRule",
    "PatternRuleState",
    "PatternSeries",
    "PatternSpec",
    "PatternState",
    "PatternValue",
    "PriorTrendState",
    "TalibPatternPort",
    "TalibRawPatternSpec",
    "assert_pattern_name",
    "build_default_pattern_registry",
    "confirms_by_close_direction",
    "contain",
    "engulf",
    "judge_series",
    "match_outputs",
    "min_history_for",
    "no_match_outputs",
    "output_keys",
    "outputs_from_talib_integer",
    "prior_trend",
    "resolve_talib_penetration",
    "sparse_talib_integer_signals",
    "spec_for",
    "talib_integer_from_outputs",
    "talib_penetration_default",
    "talib_penetration_lookback",
    "trend_ema",
    "undetermined_outputs",
    "validate_talib_adapter_outputs",
    "validate_talib_raw_integer_series",
    "validate_talib_version_pin",
]
