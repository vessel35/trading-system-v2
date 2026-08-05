"""TA-Lib v0.7.1 raw candlestick output contract.

The direct ``TA_CDL*`` ports use TA-Lib's integer result as the source value.
They are not registered in the repository's four-key pattern registry until the
separate adapter stage decides how each raw integer maps to that older shape.
"""

import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from math import isnan
from types import MappingProxyType
from typing import Final

from core_lib.types import Candle

from .outputs import BOUNDARY_STRENGTH, FULL_STRENGTH, MATCHED, NOT_MATCHED, output_keys
from .registry import PatternSeries, PatternValue
from .talib_candles import CandleAverageState, CandleSettingType, candle_average_series

TALIB_SOURCE_VERSION: Final = "0.7.1"
"""The TA-Lib source edition used for direct candlestick ports and captures."""

TALIB_UNDERLYING_VERSION_PREFIX: Final = "0.7.1"
"""The expected C-library version token recorded by the Python wrapper."""

TALIB_CDL_PATTERN_COUNT: Final = 61
"""The number of TA-Lib ``CDL`` functions covered by the migration."""

TALIB_RAW_ZERO: Final = 0
TALIB_RAW_BOUNDARY_MAGNITUDE: Final = 80
TALIB_RAW_MATCH_MAGNITUDE: Final = 100
TALIB_RAW_CONFIRMATION_MAGNITUDE: Final = 200

TALIB_RAW_ALLOWED_VALUES: Final = frozenset(
    {
        -TALIB_RAW_CONFIRMATION_MAGNITUDE,
        -TALIB_RAW_MATCH_MAGNITUDE,
        -TALIB_RAW_BOUNDARY_MAGNITUDE,
        TALIB_RAW_ZERO,
        TALIB_RAW_BOUNDARY_MAGNITUDE,
        TALIB_RAW_MATCH_MAGNITUDE,
        TALIB_RAW_CONFIRMATION_MAGNITUDE,
    }
)
"""The source-allowed raw integer values for TA-Lib v0.7.1 ``CDL`` output."""

TALIB_DBL_MAX: Final = sys.float_info.max
"""The ``DBL_MAX`` value used by TA-Lib penetration parameter guards."""

TALIB_DEFAULT_PENETRATION_SENTINEL: Final = -4e37
"""TA-Lib's generated-code sentinel for an omitted optional penetration argument."""

TALIB_PENETRATION_DEFAULTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "CDLABANDONEDBABY": 0.3,
        "CDLDARKCLOUDCOVER": 0.5,
        "CDLEVENINGDOJISTAR": 0.3,
        "CDLEVENINGSTAR": 0.3,
        "CDLMATHOLD": 0.5,
        "CDLMORNINGDOJISTAR": 0.3,
        "CDLMORNINGSTAR": 0.3,
    }
)
"""TA-Lib v0.7.1 default penetration values, keyed by ``CDL`` function name."""

AverageKey = tuple[CandleSettingType, int]
AverageSeries = Mapping[AverageKey, Sequence[float | None]]
IntegerJudge = Callable[[Sequence[Candle], int, AverageSeries], int]

_CURRENT: Final = 0


@dataclass(frozen=True, slots=True)
class TalibRawPatternSpec:
    """One unregistered TA-Lib raw integer pattern contract."""

    name: str
    talib_function: str
    lookback: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must not be empty")
        if not self.talib_function.startswith("CDL"):
            raise ValueError("talib_function must be a TA-Lib CDL function name")
        if self.lookback < 0:
            raise ValueError("lookback must not be negative")

    @property
    def first_output_index(self) -> int:
        """Return the first bar index where TA-Lib can emit a meaningful integer."""
        return self.lookback

    @property
    def min_history(self) -> int:
        """Return the candle count required for the first meaningful output."""
        return self.lookback + 1

    def is_warmup_index(self, index: int) -> bool:
        """Return whether ``index`` belongs to the pre-lookback prefix."""
        if index < 0:
            raise ValueError("index must not be negative")
        return index < self.lookback


def validate_talib_version_pin(
    talib_version: str | None,
    underlying_version: str | None,
) -> None:
    """Raise when a capture or runtime source is not TA-Lib v0.7.1."""
    if talib_version != TALIB_SOURCE_VERSION:
        raise ValueError(
            f"TA-Lib wrapper version must be {TALIB_SOURCE_VERSION}, got {talib_version!r}"
        )
    if underlying_version is None:
        raise ValueError("TA-Lib underlying C-library version must be recorded")
    underlying_token = underlying_version.split(maxsplit=1)[0]
    if underlying_token != TALIB_UNDERLYING_VERSION_PREFIX:
        raise ValueError(
            "TA-Lib underlying C-library version must begin with "
            f"{TALIB_UNDERLYING_VERSION_PREFIX}, got {underlying_version!r}"
        )


def talib_penetration_default(talib_function: str) -> float:
    """Return the TA-Lib v0.7.1 default penetration for one optional-argument pattern."""
    try:
        return TALIB_PENETRATION_DEFAULTS[talib_function]
    except KeyError as error:
        raise KeyError(f"{talib_function} has no TA-Lib penetration default") from error


def resolve_talib_penetration(
    talib_function: str,
    opt_in_penetration: float = TALIB_DEFAULT_PENETRATION_SENTINEL,
) -> float:
    """Return the effective TA-Lib penetration value or raise on the bad-param path."""
    if opt_in_penetration == TALIB_DEFAULT_PENETRATION_SENTINEL:
        return talib_penetration_default(talib_function)
    if opt_in_penetration < 0.0 or opt_in_penetration > TALIB_DBL_MAX:
        raise ValueError(f"{talib_function} penetration is outside TA-Lib bounds")
    return opt_in_penetration


def talib_penetration_lookback(
    talib_function: str,
    base_lookback: int,
    opt_in_penetration: float = TALIB_DEFAULT_PENETRATION_SENTINEL,
) -> int:
    """Return TA-Lib's optional-penetration lookback, including the ``-1`` error path."""
    if opt_in_penetration != TALIB_DEFAULT_PENETRATION_SENTINEL and (
        opt_in_penetration < 0.0 or opt_in_penetration > TALIB_DBL_MAX
    ):
        return -1
    return base_lookback


def validate_talib_raw_integer_series(
    spec: TalibRawPatternSpec,
    values: Sequence[int],
    *,
    candle_count: int | None = None,
) -> None:
    """Validate the aligned raw integer series for one TA-Lib ``CDL`` pattern.

    TA-Lib's Python wrapper returns one integer per input candle. The prefix before
    ``lookback`` is represented as zero, not NaN; callers distinguish warm-up by
    the spec's ``lookback`` or ``min_history``.
    """
    if candle_count is not None and len(values) != candle_count:
        raise ValueError(
            f"{spec.talib_function} produced {len(values)} values for {candle_count} candles"
        )
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{spec.talib_function} value at index {index} must be int")
        if value not in TALIB_RAW_ALLOWED_VALUES:
            raise ValueError(
                f"{spec.talib_function} value at index {index} is not a TA-Lib v0.7.1 "
                f"CDL raw integer: {value}"
            )
        if spec.is_warmup_index(index) and value != TALIB_RAW_ZERO:
            raise ValueError(
                f"{spec.talib_function} warm-up index {index} must be {TALIB_RAW_ZERO}, got {value}"
            )


def _avg(
    averages: AverageSeries,
    setting_type: CandleSettingType,
    index: int,
    *,
    offset: int = _CURRENT,
) -> float:
    value = averages[(setting_type, offset)][index]
    if value is None:
        raise ValueError(f"{setting_type.value} average is unavailable at index {index}")
    return value


def outputs_from_talib_integer(name: str, value: int) -> PatternValue:
    """Map one source-allowed TA-Lib raw integer to the adapter's four-key output."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"TA-Lib pattern value for {name} must be int")
    if value not in TALIB_RAW_ALLOWED_VALUES:
        raise ValueError(f"unsupported TA-Lib pattern raw integer for {name}: {value}")

    match_key, direction_key, strength_key, confirm_key = output_keys(name)
    if value == 0:
        return {
            match_key: NOT_MATCHED,
            direction_key: NOT_MATCHED,
            strength_key: NOT_MATCHED,
            confirm_key: NOT_MATCHED,
        }

    direction = 1.0 if value > 0 else -1.0
    magnitude = abs(value)
    if magnitude == 200:
        return {
            match_key: NOT_MATCHED,
            direction_key: direction,
            strength_key: NOT_MATCHED,
            confirm_key: MATCHED,
        }
    if magnitude == 100:
        strength = FULL_STRENGTH
    elif magnitude == 80:
        strength = BOUNDARY_STRENGTH
    else:
        raise ValueError(f"unsupported TA-Lib pattern magnitude for {name}: {value}")
    return {
        match_key: MATCHED,
        direction_key: direction,
        strength_key: strength,
        confirm_key: NOT_MATCHED,
    }


def _undetermined_outputs(name: str) -> PatternValue:
    match_key, direction_key, strength_key, confirm_key = output_keys(name)
    undetermined = float("nan")
    return {
        match_key: undetermined,
        direction_key: undetermined,
        strength_key: undetermined,
        confirm_key: undetermined,
    }


def _talib_adapter_numbers(
    name: str,
    value: Mapping[str, float],
) -> tuple[float, float, float, float]:
    match_key, direction_key, strength_key, confirm_key = output_keys(name)
    return (
        value[match_key],
        value[direction_key],
        value[strength_key],
        value[confirm_key],
    )


def validate_talib_adapter_outputs(name: str, value: Mapping[str, float]) -> None:
    """Raise unless a four-key output is a TA-Lib adapter shape or warm-up row."""
    matched, direction, strength, confirmed = _talib_adapter_numbers(name, value)
    for number in (matched, direction, strength, confirmed):
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise TypeError(f"TA-Lib adapter output for {name} must contain numeric floats")
    nan_flags = tuple(isnan(number) for number in (matched, direction, strength, confirmed))
    if all(nan_flags):
        return
    if any(nan_flags):
        raise ValueError(f"TA-Lib adapter output for {name} is partially NaN")

    if (
        matched == NOT_MATCHED
        and direction == NOT_MATCHED
        and strength == NOT_MATCHED
        and confirmed == NOT_MATCHED
    ):
        return

    signed_direction = direction in (1.0, -1.0)
    if (
        matched == MATCHED
        and signed_direction
        and strength in (FULL_STRENGTH, BOUNDARY_STRENGTH)
        and confirmed == NOT_MATCHED
    ):
        return

    if (
        matched == NOT_MATCHED
        and signed_direction
        and strength == NOT_MATCHED
        and confirmed == MATCHED
    ):
        return

    if matched == MATCHED and confirmed == MATCHED:
        raise ValueError(f"TA-Lib adapter output for {name} cannot match and confirm together")
    if matched == MATCHED and direction == NOT_MATCHED:
        raise ValueError(f"TA-Lib matched output for {name} must carry direction")
    if confirmed == MATCHED and direction == NOT_MATCHED:
        raise ValueError(f"TA-Lib confirmation output for {name} must carry direction")

    raise ValueError(
        f"unsupported TA-Lib adapter output shape for {name}: "
        f"matched={matched}, direction={direction}, strength={strength}, confirmed={confirmed}"
    )


def talib_integer_from_outputs(name: str, value: Mapping[str, float]) -> int | None:
    """Rebuild TA-Lib's integer signal from a direct port's four-key output."""
    validate_talib_adapter_outputs(name, value)
    matched, direction, strength, confirmed = _talib_adapter_numbers(name, value)
    if all(isnan(number) for number in (matched, direction, strength, confirmed)):
        return None

    sign = 1 if direction == 1.0 else -1
    if confirmed == MATCHED:
        return sign * TALIB_RAW_CONFIRMATION_MAGNITUDE
    if matched != MATCHED:
        return TALIB_RAW_ZERO
    if strength == FULL_STRENGTH:
        return sign * TALIB_RAW_MATCH_MAGNITUDE
    if strength == BOUNDARY_STRENGTH:
        return sign * TALIB_RAW_BOUNDARY_MAGNITUDE
    raise AssertionError(f"validated TA-Lib adapter strength is unreachable: {strength}")


def sparse_talib_integer_signals(
    name: str,
    series: Sequence[Mapping[str, float]],
) -> dict[int, int]:
    """Return the sparse non-zero signal table used by the captured TA-Lib fixtures."""
    signals: dict[int, int] = {}
    for index, value in enumerate(series):
        integer = talib_integer_from_outputs(name, value)
        if integer:
            signals[index] = integer
    return signals


@dataclass(frozen=True, slots=True)
class TalibPatternPort(TalibRawPatternSpec):
    """One unregistered TA-Lib ``CDL`` port with its own lookback and average offsets."""

    average_keys: tuple[AverageKey, ...]
    _judge: IntegerJudge

    def make_state(self) -> "TalibPatternState":
        """Create a fresh incremental state for this direct TA-Lib port."""
        return TalibPatternState(
            name=self.name,
            lookback=self.lookback,
            average_keys=self.average_keys,
            judge=self._judge,
        )

    def compute_integers(self, candles: Sequence[Candle]) -> list[int]:
        """Return TA-Lib integer outputs aligned to input candle indexes."""
        averages = {
            key: candle_average_series(key[0], candles, target_offset=key[1])
            for key in self.average_keys
        }
        values = [0] * len(candles)
        for index in range(self.lookback, len(candles)):
            values[index] = self._judge(candles, index, averages)
        validate_talib_raw_integer_series(self, values, candle_count=len(candles))
        return values

    def compute_vectorized(self, candles: Sequence[Candle]) -> PatternSeries:
        """Return the repository four-key pattern outputs aligned to candles."""
        integers = self.compute_integers(candles)
        values: list[PatternValue] = []
        for index, integer in enumerate(integers):
            if index < self.lookback:
                values.append(_undetermined_outputs(self.name))
            else:
                values.append(outputs_from_talib_integer(self.name, integer))
        return values


@dataclass(slots=True)
class TalibPatternState:
    """Incrementally run one stateless TA-Lib ``CDL`` port."""

    name: str
    lookback: int
    average_keys: tuple[AverageKey, ...]
    judge: IntegerJudge
    min_history: int = field(init=False)
    _seen: int = field(init=False, default=0, repr=False)
    _candles: list[Candle] = field(init=False, repr=False)
    _average_states: dict[AverageKey, CandleAverageState] = field(init=False, repr=False)
    _averages: dict[AverageKey, list[float | None]] = field(init=False, repr=False)
    _current_integer: int | None = field(init=False, default=None, repr=False)
    _current: PatternValue = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.lookback < 0:
            raise ValueError("lookback must not be negative")
        self.min_history = self.lookback + 1
        self._candles = []
        self._average_states = {
            key: CandleAverageState(key[0], target_offset=key[1]) for key in self.average_keys
        }
        self._averages = {key: [] for key in self.average_keys}
        self._current = _undetermined_outputs(self.name)

    @property
    def warmed_up(self) -> bool:
        """Return whether this state has reached TA-Lib's first output index."""
        return self._seen >= self.min_history

    def reset(self) -> None:
        """Clear candle and candle-average state."""
        self._seen = 0
        self._candles.clear()
        for state in self._average_states.values():
            state.reset()
        for values in self._averages.values():
            values.clear()
        self._current_integer = None
        self._current = _undetermined_outputs(self.name)

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and replay prior candles in order."""
        self.reset()
        for candle in candles:
            self.update(candle)

    def update(self, candle: Candle) -> PatternValue:
        """Advance by one confirmed candle and return the four-key output."""
        integer = self.update_integer(candle)
        self._current = (
            _undetermined_outputs(self.name)
            if integer is None
            else outputs_from_talib_integer(self.name, integer)
        )
        return self._current

    def update_integer(self, candle: Candle) -> int | None:
        """Advance by one candle and return the raw integer, or ``None`` during warm-up."""
        index = self._seen
        self._seen += 1
        self._candles.append(candle)
        for key, state in self._average_states.items():
            self._averages[key].append(state.update(candle))

        if index < self.lookback:
            self._current_integer = None
            return self._current_integer
        self._current_integer = self.judge(self._candles, index, self._averages)
        return self._current_integer

    def current(self) -> PatternValue:
        """Return the latest four-key output, NaN-shaped while still warming up."""
        return self._current

    def current_integer(self) -> int | None:
        """Return the latest raw integer, or ``None`` while still warming up."""
        return self._current_integer


__all__ = [
    "AverageKey",
    "AverageSeries",
    "IntegerJudge",
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
    "TalibPatternPort",
    "TalibPatternState",
    "TalibRawPatternSpec",
    "outputs_from_talib_integer",
    "resolve_talib_penetration",
    "sparse_talib_integer_signals",
    "talib_integer_from_outputs",
    "talib_penetration_default",
    "talib_penetration_lookback",
    "validate_talib_raw_integer_series",
    "validate_talib_adapter_outputs",
    "validate_talib_version_pin",
]
