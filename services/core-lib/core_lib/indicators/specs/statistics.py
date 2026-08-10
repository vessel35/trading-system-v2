"""Registration list owned by the statistics category."""

from functools import partial

from core_lib.indicators import statistics
from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = (
    IndicatorSpec(
        name="BETA",
        params={"period": 5},
        version="1.0.0",
        pinned_impl=(
            "technical_indicators_calc_spec.md §9.7.1 "
            "(TA-Lib 0.7.1 arithmetic; reference returns are X and primary returns are Y)"
        ),
        min_history=6,
        category="statistics",
        required_inputs=(),
        _vectorized=statistics.paired_vectorized_requires_reference,
        _state_factory=partial(statistics.BetaState, period=5),
        needs_reference_series=True,
    ),
    IndicatorSpec(
        name="CORREL",
        params={"period": 30},
        version="1.0.0",
        pinned_impl="technical_indicators_calc_spec.md §9.7.2 (TA-Lib 0.7.1 arithmetic)",
        min_history=30,
        category="statistics",
        required_inputs=(),
        _vectorized=statistics.paired_vectorized_requires_reference,
        _state_factory=partial(statistics.CorrelState, period=30),
        needs_reference_series=True,
    ),
)
