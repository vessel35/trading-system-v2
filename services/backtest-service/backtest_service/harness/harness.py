"""Orchestrate deterministic multi-run overfitting defenses around Engine."""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from statistics import NormalDist
from typing import Protocol, runtime_checkable

from core_lib.ports import CatalogStore

from backtest_service.config import RunConfig
from backtest_service.engine.engine import Engine, RunResult

EngineFactory = Callable[[], Engine]

OOS_DEGRADATION_LIMIT = 0.50
PSR_MINIMUM = 0.95
RUIN_DRAWDOWN = 0.60
RISK_FRACTION = 0.01


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("a quantile requires at least one value")
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _finite_metric(value: float) -> float:
    return value if math.isfinite(value) else 0.0


@runtime_checkable
class _OrphanReconciler(Protocol):
    def reconcile_orphaned(self) -> int:
        """Mark unfinished registered runs before a multi-run operation."""


class Harness:
    """Create run sets and apply deterministic cross-run validation gates."""

    def __init__(
        self,
        catalog: CatalogStore,
        engine_factory: EngineFactory,
        *,
        seed: int = 0,
    ) -> None:
        self.catalog = catalog
        self._engine_factory = engine_factory
        self._seed = seed
        self._trial_count = 1

    def is_oos(self, config: RunConfig, split: float) -> dict[str, object]:
        """Run disjoint in-sample/out-of-sample periods and gate degradation."""
        if not 0.0 < split < 1.0:
            raise ValueError("split must be strictly between zero and one")
        boundary = config.start + (config.end - config.start) * split
        if boundary <= config.start or boundary >= config.end:
            raise ValueError("split produced an empty validation period")
        in_sample = self._segment_config(config, config.start, boundary, "is")
        out_of_sample = self._segment_config(config, boundary, config.end, "oos")
        in_result, out_result = self.sweep([in_sample, out_of_sample])
        in_score = _finite_metric(in_result.metrics.pf)
        out_score = _finite_metric(out_result.metrics.pf)
        degradation = (
            max(0.0, (in_score - out_score) / abs(in_score))
            if in_score != 0.0
            else (0.0 if out_score >= 0.0 else 1.0)
        )
        return {
            "representative_run_id": out_result.run_id,
            "in_sample_run_id": in_result.run_id,
            "out_of_sample_run_id": out_result.run_id,
            "split": split,
            "boundary": boundary.isoformat(),
            "metric": "pf",
            "in_sample_value": in_score,
            "out_of_sample_value": out_score,
            "oos_degradation": degradation,
            "passed": degradation < OOS_DEGRADATION_LIMIT,
        }

    def walk_forward(self, config: RunConfig, folds: int) -> dict[str, object]:
        """Run chronological non-overlapping folds and apply the OOS gate per fold."""
        if folds < 2:
            raise ValueError("walk-forward requires at least two folds")
        duration = config.end - config.start
        if duration.total_seconds() < folds / 1_000:
            raise ValueError("period is too short for millisecond-separated folds")
        boundaries = [
            config.start + duration * (index / folds) for index in range(folds)
        ] + [config.end]
        configs = [
            self._segment_config(
                config,
                boundaries[index],
                boundaries[index + 1],
                f"wf-{index + 1}",
            )
            for index in range(folds)
        ]
        results = self.sweep(configs)
        scores = [_finite_metric(result.metrics.pf) for result in results]
        degradations = [
            (
                max(0.0, (previous - current) / abs(previous))
                if previous != 0.0
                else (0.0 if current >= 0.0 else 1.0)
            )
            for previous, current in zip(scores, scores[1:], strict=False)
        ]
        fold_evidence = [
            {
                "fold": index + 1,
                "run_id": result.run_id,
                "start": configs[index].start.isoformat(),
                "end": configs[index].end.isoformat(),
                "pf": scores[index],
            }
            for index, result in enumerate(results)
        ]
        return {
            "representative_run_id": results[-1].run_id,
            "folds": fold_evidence,
            "degradations": degradations,
            "maximum_degradation": max(degradations, default=0.0),
            "passed": all(value < OOS_DEGRADATION_LIMIT for value in degradations),
        }

    def monte_carlo(
        self,
        r_multiples: list[float],
        iters: int,
    ) -> dict[str, object]:
        """Bootstrap terminal R and ruin probability with a fixed local seed."""
        if not r_multiples:
            raise ValueError("r_multiples must not be empty")
        if iters <= 0:
            raise ValueError("iters must be positive")
        if any(not math.isfinite(value) for value in r_multiples):
            raise ValueError("r_multiples must be finite")
        generator = random.Random(self._seed)
        terminal_r: list[float] = []
        ruin_count = 0
        for _ in range(iters):
            equity = 1.0
            peak = equity
            total_r = 0.0
            ruined = False
            for _ in r_multiples:
                outcome = generator.choice(r_multiples)
                total_r += outcome
                equity *= max(0.0, 1.0 + outcome * RISK_FRACTION)
                peak = max(peak, equity)
                if equity <= peak * (1.0 - RUIN_DRAWDOWN):
                    ruined = True
            terminal_r.append(total_r)
            ruin_count += int(ruined)
        ruin_probability = ruin_count / iters
        return {
            "iterations": iters,
            "seed": self._seed,
            "terminal_r_p05": _quantile(terminal_r, 0.05),
            "terminal_r_p95": _quantile(terminal_r, 0.95),
            "ruin_probability": ruin_probability,
            "passed": ruin_probability < 0.001,
        }

    def psr(self, returns: list[float]) -> float:
        """Return zero-benchmark PSR with a sweep-size Bonferroni correction."""
        if len(returns) < 3:
            raise ValueError("PSR requires at least three returns")
        if any(not math.isfinite(value) for value in returns):
            raise ValueError("returns must be finite")
        mean = statistics.fmean(returns)
        standard_deviation = statistics.stdev(returns)
        if standard_deviation == 0.0:
            return 1.0 if mean > 0.0 else 0.0
        sharpe = mean / standard_deviation
        count = len(returns)
        centered = [(value - mean) / standard_deviation for value in returns]
        skew = sum(value**3 for value in centered) / count
        kurtosis = sum(value**4 for value in centered) / count
        variance_adjustment = (
            1.0
            - skew * sharpe
            + ((kurtosis - 1.0) / 4.0) * sharpe * sharpe
        )
        if variance_adjustment <= 0.0:
            raise ValueError("PSR variance adjustment is not positive")
        statistic = sharpe * math.sqrt(count - 1) / math.sqrt(variance_adjustment)
        raw_probability = NormalDist().cdf(statistic)
        return max(0.0, 1.0 - self._trial_count * (1.0 - raw_probability))

    def sweep(self, configs: list[RunConfig]) -> list[RunResult]:
        """Run each configuration through a fresh Engine and catalog-issued id."""
        if not configs:
            raise ValueError("sweep configs must not be empty")
        if isinstance(self.catalog, _OrphanReconciler):
            self.catalog.reconcile_orphaned()
        self._trial_count = len(configs)
        return [self._engine_factory().run(config) for config in configs]

    @staticmethod
    def overfit_gate(*, degradation: float, psr: float) -> dict[str, object]:
        """Apply the design-standard cross-run OOS and PSR thresholds."""
        if not 0.0 <= degradation:
            raise ValueError("degradation must be nonnegative")
        if not 0.0 <= psr <= 1.0:
            raise ValueError("psr must be between zero and one")
        failed: list[str] = []
        if degradation >= OOS_DEGRADATION_LIMIT:
            failed.append("oos_degradation")
        if psr < PSR_MINIMUM:
            failed.append("psr")
        return {
            "passed": not failed,
            "failed": failed,
            "oos_degradation_limit": OOS_DEGRADATION_LIMIT,
            "psr_minimum": PSR_MINIMUM,
        }

    @staticmethod
    def _segment_config(
        config: RunConfig,
        start: datetime,
        end: datetime,
        label: str,
    ) -> RunConfig:
        if end - start < timedelta(milliseconds=1):
            raise ValueError("run segment must span at least one millisecond")
        base_name = config.run_name[: max(1, 23 - len(label))].rstrip("-")
        payload = config.model_dump()
        payload.update(
            {
                "run_name": f"{base_name}-{label}",
                "start": start,
                "end": end,
                "sweep": {
                    **({} if config.sweep is None else config.sweep),
                    "fold_label": label,
                },
            }
        )
        return RunConfig.model_validate(payload)


__all__ = [
    "EngineFactory",
    "Harness",
    "OOS_DEGRADATION_LIMIT",
    "PSR_MINIMUM",
]
