"""Define standardized performance metric formulas and annualization."""

import math
import random
import statistics
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from core_lib.types import Trade

ANNUALIZATION_DAYS = 365
MIN_SQN_TRADES = 30
MAX_SQN_TRADES = 100
ROR_SEED = 0
ROR_ITERATIONS = 10_000
ROR_RISK_FRACTION = 0.01
ROR_DRAWDOWN = 0.60

type EquityValue = float | Decimal
type EquitySeries = (
    Mapping[datetime, EquityValue] | Sequence[tuple[datetime, EquityValue]]
)


@dataclass(frozen=True, slots=True)
class MetricSet:
    """A single run's net performance facts."""

    pf: float
    sortino: float
    calmar_or_mar: float
    sqn: float
    mdd: float
    ror: float
    sharpe: float
    win_rate: float
    payoff: float
    expectancy_r: float
    ulcer: float
    kelly: float
    trade_count: int


def _as_points(series: EquitySeries) -> list[tuple[datetime, float]]:
    raw_points = series.items() if isinstance(series, Mapping) else series
    points: list[tuple[datetime, float]] = []
    for timestamp, raw_value in raw_points:
        if not isinstance(timestamp, datetime):
            raise TypeError("equity timestamps must be datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("equity timestamps must be timezone-aware")
        timestamp = timestamp.astimezone(UTC)
        value = float(raw_value)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError("equity values must be finite and positive")
        points.append((timestamp, value))
    if not points:
        raise ValueError("equity series must not be empty")
    return sorted(points, key=lambda point: point[0])


def _daily_points(series: EquitySeries) -> list[tuple[datetime, float]]:
    last_by_day: dict[object, tuple[datetime, float]] = {}
    for point in _as_points(series):
        last_by_day[point[0].date()] = point
    return sorted(last_by_day.values(), key=lambda point: point[0])


def _returns(points: Sequence[tuple[datetime, float]]) -> list[float]:
    return [
        current_value / previous_value - 1.0
        for (_, previous_value), (_, current_value) in zip(
            points,
            points[1:],
            strict=False,
        )
    ]


def _sample_std(values: Sequence[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else math.nan


def _ratio(numerator: float, denominator: float) -> float:
    if math.isnan(numerator) or math.isnan(denominator):
        return math.nan
    if denominator == 0.0:
        if numerator > 0.0:
            return math.inf
        if numerator < 0.0:
            return -math.inf
        return math.nan
    return numerator / denominator


def annualize(series: EquitySeries) -> float:
    """Return annualized Sharpe after daily last-value resampling with sqrt(365)."""
    daily_returns = _returns(_daily_points(series))
    standard_deviation = _sample_std(daily_returns)
    return math.sqrt(ANNUALIZATION_DAYS) * _ratio(
        statistics.fmean(daily_returns) if daily_returns else math.nan,
        standard_deviation,
    )


def _sortino(daily_returns: Sequence[float], target: float = 0.0) -> float:
    if not daily_returns:
        return math.nan
    downside_deviation = math.sqrt(
        sum(min(0.0, value - target) ** 2 for value in daily_returns)
        / len(daily_returns)
    )
    return math.sqrt(ANNUALIZATION_DAYS) * _ratio(
        statistics.fmean(daily_returns) - target,
        downside_deviation,
    )


def _drawdown_metrics(points: Sequence[tuple[datetime, float]]) -> tuple[float, float]:
    running_max = -math.inf
    drawdowns: list[float] = []
    for _, value in points:
        running_max = max(running_max, value)
        drawdowns.append(value / running_max - 1.0)
    mdd = min(drawdowns)
    ulcer = math.sqrt(statistics.fmean((100.0 * value) ** 2 for value in drawdowns))
    return mdd, ulcer


def _three_year_cutoff(timestamp: datetime) -> datetime:
    try:
        return timestamp.replace(year=timestamp.year - 3)
    except ValueError:
        return timestamp.replace(year=timestamp.year - 3, day=28)


def _cagr(points: Sequence[tuple[datetime, float]]) -> float:
    elapsed_seconds = (points[-1][0] - points[0][0]).total_seconds()
    if elapsed_seconds <= 0.0:
        return math.nan
    years = elapsed_seconds / (ANNUALIZATION_DAYS * 24 * 60 * 60)
    return math.pow(points[-1][1] / points[0][1], 1.0 / years) - 1.0


def _calmar_or_mar(points: Sequence[tuple[datetime, float]]) -> float:
    cutoff = _three_year_cutoff(points[-1][0])
    measured = [point for point in points if point[0] >= cutoff]
    if points[0][0] > cutoff:
        measured = list(points)
    cagr = _cagr(measured)
    mdd, _ = _drawdown_metrics(measured)
    return _ratio(cagr, abs(mdd))


def _r_multiples(trades: Sequence[Trade]) -> list[float]:
    return [
        float(trade.net_pnl / trade.r0)
        for trade in trades
        if trade.r0 is not None and trade.r0 > 0
    ]


def risk_of_ruin(
    r_multiples: Sequence[float],
    *,
    iterations: int = ROR_ITERATIONS,
    seed: int = ROR_SEED,
    risk_fraction: float = ROR_RISK_FRACTION,
    ruin_drawdown: float = ROR_DRAWDOWN,
) -> float:
    """Estimate ruin by fixed-seed bootstrap over the empirical R distribution."""
    if not r_multiples:
        return math.nan
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not 0.0 < risk_fraction <= 0.01:
        raise ValueError("risk_fraction must be in (0, 0.01]")
    if not 0.0 < ruin_drawdown < 1.0:
        raise ValueError("ruin_drawdown must be in (0, 1)")
    if any(not math.isfinite(value) for value in r_multiples):
        raise ValueError("R-multiples must be finite")

    generator = random.Random(seed)
    ruin_count = 0
    for _ in range(iterations):
        equity = 1.0
        peak = equity
        ruined = False
        for _ in r_multiples:
            outcome = generator.choice(r_multiples)
            equity *= max(0.0, 1.0 + outcome * risk_fraction)
            peak = max(peak, equity)
            if equity <= peak * (1.0 - ruin_drawdown):
                ruined = True
                break
        ruin_count += int(ruined)
    return ruin_count / iterations


def compute(trades: list[Trade], equity: EquitySeries) -> MetricSet:
    """Compute the design-standard net metrics for one run."""
    points = _as_points(equity)
    daily_points = _daily_points(equity)
    daily_returns = _returns(daily_points)
    net_results = [float(trade.net_pnl) for trade in trades]
    wins = [value for value in net_results if value > 0.0]
    losses = [abs(value) for value in net_results if value < 0.0]
    trade_count = len(trades)
    win_rate = len(wins) / trade_count if trade_count else math.nan
    average_win = statistics.fmean(wins) if wins else 0.0
    average_loss = statistics.fmean(losses) if losses else 0.0
    payoff = _ratio(average_win, average_loss)
    pf = _ratio(sum(wins), sum(losses))

    r_multiples = _r_multiples(trades)
    positive_r = [value for value in r_multiples if value > 0.0]
    negative_r = [abs(value) for value in r_multiples if value < 0.0]
    r_count = len(r_multiples)
    r_win_rate = len(positive_r) / r_count if r_count else math.nan
    r_average_win = statistics.fmean(positive_r) if positive_r else 0.0
    r_average_loss = statistics.fmean(negative_r) if negative_r else 0.0
    expectancy_r = (
        r_win_rate * r_average_win - (1.0 - r_win_rate) * r_average_loss
        if r_count
        else math.nan
    )
    r_std = _sample_std(r_multiples)
    sqn = (
        math.sqrt(min(r_count, MAX_SQN_TRADES))
        * _ratio(statistics.fmean(r_multiples), r_std)
        if r_count >= MIN_SQN_TRADES
        else math.nan
    )
    kelly = (
        win_rate - (1.0 - win_rate) / payoff
        if trade_count and payoff not in {0.0, -math.inf}
        else math.nan
    )
    mdd, ulcer = _drawdown_metrics(points)
    return MetricSet(
        pf=pf,
        sortino=_sortino(daily_returns),
        calmar_or_mar=_calmar_or_mar(points),
        sqn=sqn,
        mdd=mdd,
        ror=risk_of_ruin(r_multiples),
        sharpe=annualize(equity),
        win_rate=win_rate,
        payoff=payoff,
        expectancy_r=expectancy_r,
        ulcer=ulcer,
        kelly=kelly,
        trade_count=trade_count,
    )
