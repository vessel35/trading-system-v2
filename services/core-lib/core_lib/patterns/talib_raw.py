"""TA-Lib v0.7.1 raw candlestick output contract.

The direct ``TA_CDL*`` ports use TA-Lib's integer result as the source value.
They are not registered in the repository's four-key pattern registry until the
separate adapter stage decides how each raw integer maps to that older shape.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

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
"""The raw integer values observed and accepted for TA-Lib v0.7.1 ``CDL`` output."""


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


__all__ = [
    "TALIB_CDL_PATTERN_COUNT",
    "TALIB_RAW_ALLOWED_VALUES",
    "TALIB_RAW_BOUNDARY_MAGNITUDE",
    "TALIB_RAW_CONFIRMATION_MAGNITUDE",
    "TALIB_RAW_MATCH_MAGNITUDE",
    "TALIB_RAW_ZERO",
    "TALIB_SOURCE_VERSION",
    "TALIB_UNDERLYING_VERSION_PREFIX",
    "TalibRawPatternSpec",
    "validate_talib_raw_integer_series",
    "validate_talib_version_pin",
]
