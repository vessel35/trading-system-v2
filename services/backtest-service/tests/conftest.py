"""Keep acceptance marker behavior stable under either service's pytest config.

This module also owns the declared-gap scenarios. Live ``crypto_data`` is backfilled
to completeness, so no real window carries the missing candles the gap acceptance and
regression tests exist to verify. The helpers below withhold an explicitly declared
set of minutes from the production feed, in both the walked series and the independent
origin query, so the resulting gap accounting follows from the declaration rather than
from whatever the collector happened to have stored. They live here rather than in a
sibling module because this service configures ``--import-mode=importlib``, under which
test modules cannot import each other.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core_lib.ports import DataFeed
from core_lib.types import Candle

_MINUTE = timedelta(minutes=1)


def pytest_configure(config: pytest.Config) -> None:
    """Register acceptance when a multi-service run chooses core-lib as rootdir."""
    config.addinivalue_line(
        "markers",
        "acceptance: exercises the operator-assembled backtest against development data",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Deselect acceptance items unless the invocation explicitly requests them."""
    expression = config.option.markexpr
    selected = expression if isinstance(expression, str) else ""
    if "acceptance" in selected and "not acceptance" not in selected:
        return
    deselected = [item for item in items if item.get_closest_marker("acceptance") is not None]
    if not deselected:
        return
    items[:] = [item for item in items if item not in deselected]
    config.hook.pytest_deselected(items=deselected)


def absent_hours(*starts: datetime, hours: int) -> frozenset[datetime]:
    """Declare every minute of ``hours`` consecutive hour buckets from each start."""
    withheld: set[datetime] = set()
    for start in starts:
        _require_hour_aligned(start)
        for hour in range(hours):
            bucket = start + timedelta(hours=hour)
            withheld.update(bucket + offset * _MINUTE for offset in range(60))
    return frozenset(withheld)


def partial_hours(*starts: datetime, hours: int, minutes: int) -> frozenset[datetime]:
    """Declare the first ``minutes`` of ``hours`` consecutive hour buckets from each start.

    Leaving the rest of each bucket present keeps the bucket partial rather than
    absent, which is what separates ``partial_bucket_count`` from a normal gap.
    """
    if not 0 < minutes < 60:
        raise ValueError("a partial bucket must withhold between 1 and 59 minutes")
    withheld: set[datetime] = set()
    for start in starts:
        _require_hour_aligned(start)
        for hour in range(hours):
            bucket = start + timedelta(hours=hour)
            withheld.update(bucket + offset * _MINUTE for offset in range(minutes))
    return frozenset(withheld)


def _require_hour_aligned(moment: datetime) -> None:
    if moment.tzinfo is None or moment.utcoffset() != timedelta(0):
        raise ValueError("declared gap starts must be UTC")
    if moment.minute or moment.second or moment.microsecond:
        raise ValueError("declared gap starts must align to an hour bucket")


class DeclaredGapFeed(DataFeed):
    """Serve a real feed with one declared set of 1m open times withheld."""

    def __init__(self, inner: DataFeed, withheld: frozenset[datetime]) -> None:
        if not withheld:
            raise ValueError("a declared gap feed must withhold at least one minute")
        self._inner = inner
        self._withheld = withheld

    def candles(self, symbol: str, tf: str, up_to: datetime) -> list[Candle]:
        """Return the walked series without the declared minutes."""
        return [
            candle
            for candle in self._inner.candles(symbol, tf, up_to)
            if candle.open_time not in self._withheld
        ]

    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        """Withhold the same minutes from the independent origin query.

        The Engine compares this query against the walked series, so both sides
        must drop exactly the same declaration or the run fails origin validation.
        """
        origin = getattr(self._inner, "source_candles", None)
        if origin is None:
            raise TypeError("declared gap feed requires a feed with origin validation")
        return tuple(
            candle
            for candle in origin(symbol, range_start, range_end)
            if candle.open_time not in self._withheld
        )

    def funding(self, symbol: str, at: datetime) -> Decimal:
        """Delegate funding unchanged; declared gaps only remove candles."""
        return self._inner.funding(symbol, at)

    def mark_price(self, symbol: str, at: datetime) -> Decimal:
        """Delegate mark price unchanged; declared gaps only remove candles."""
        return self._inner.mark_price(symbol, at)


# One 48-hour absent block inside a 720-hour window: 672/720 coverage stays under the
# 0.95 gate and the 172_800s outage exceeds the 86_400s consecutive-gap gate.
COVERAGE_FAILURE_WITHHELD = absent_hours(datetime(2026, 5, 5, tzinfo=UTC), hours=48)
# Eight partial buckets in two runs of five and three hours: the longest omission is
# 5 * 3_600 = 18_000 seconds and no bucket loses its complete 1m origin.
NORMAL_GAP_WITHHELD = partial_hours(
    datetime(2025, 9, 10, tzinfo=UTC),
    hours=5,
    minutes=30,
) | partial_hours(datetime(2026, 1, 15, tzinfo=UTC), hours=3, minutes=30)
# Three fully absent five-hour blocks (15 normal-gap buckets, 900 missing minutes)
# plus four partial buckets that each keep 30 of their minutes.
MISSING_DATA_330D_WITHHELD = absent_hours(
    datetime(2025, 8, 15, 3, tzinfo=UTC),
    datetime(2025, 12, 1, 7, tzinfo=UTC),
    datetime(2026, 3, 20, 11, tzinfo=UTC),
    hours=5,
) | partial_hours(
    datetime(2025, 9, 5, 9, tzinfo=UTC),
    datetime(2025, 11, 11, 13, tzinfo=UTC),
    datetime(2026, 1, 23, 17, tzinfo=UTC),
    datetime(2026, 4, 9, 21, tzinfo=UTC),
    hours=1,
    minutes=30,
)

DeclaredGapDecorator = Callable[[DataFeed], DataFeed]


@pytest.fixture(scope="session")
def declared_gap_decorator() -> Callable[[frozenset[datetime]], DeclaredGapDecorator]:
    """Build a feed decorator that withholds one declared set of minutes."""

    def build(withheld: frozenset[datetime]) -> DeclaredGapDecorator:
        return lambda feed: DeclaredGapFeed(feed, withheld)

    return build


@pytest.fixture(scope="session")
def coverage_failure_withheld() -> frozenset[datetime]:
    """Declare the outage that must fail both coverage gates."""
    return COVERAGE_FAILURE_WITHHELD


@pytest.fixture(scope="session")
def normal_gap_withheld() -> frozenset[datetime]:
    """Declare the bounded partial buckets a long window must still tolerate."""
    return NORMAL_GAP_WITHHELD


@pytest.fixture(scope="session")
def missing_data_330d_withheld() -> frozenset[datetime]:
    """Declare the mixed absent and partial gaps of the long regression tier."""
    return MISSING_DATA_330D_WITHHELD
