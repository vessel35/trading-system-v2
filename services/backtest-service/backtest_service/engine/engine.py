"""Orchestrate deterministic candle ordering, fills, Evidence, and evaluation."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Final, Protocol, runtime_checkable

from core_lib import __version__ as CORE_LIB_VERSION
from core_lib.costs import (
    funding_boundaries_between,
    is_funding_boundary,
    liquidation_price,
    settle_funding,
)
from core_lib.eval import (
    DecisionResult,
    GateResult,
    MetricSet,
    check_integrity,
    compute,
    decide,
    judge,
    universal,
)
from core_lib.eval.metrics import daily_returns, trade_r_multiples
from core_lib.execution import (
    PositionBook,
    liquidation_fill,
    position_value,
    recompute,
    resolve_triggers,
    to_decimal,
)
from core_lib.indicators import DEFAULT_REGISTRY, IndicatorSpec
from core_lib.money_management import (
    AccountRiskSnapshot,
    MarketSnapshot,
    MoneyManagementError,
    MoneyManagementPolicy,
    RiskLimits,
    turtle_n_series,
)
from core_lib.patterns import (
    DEFAULT_PATTERN_REGISTRY,
    TALIB_FUNCTIONS,
    TALIB_SOURCE_VERSION,
    PatternSpec,
)
from core_lib.ports import Broker, CatalogStore, Clock, CostModel, DataFeed, EvidenceSink
from core_lib.series import SeriesSpec, SeriesState
from core_lib.series_resolution import (
    resolve_series_specs,
    series_key,
    series_specs_from_descriptors,
)
from core_lib.sizing import exposure_limit, wallet_pct_size
from core_lib.sizing import size as risk_size
from core_lib.strategy import AdapterManager, StrategyAdapter, StrategyConfig
from core_lib.types import (
    ZERO,
    Candle,
    DecisionAction,
    DecisionIntent,
    ExitReason,
    Fill,
    MarginType,
    MarketType,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
    PositionSide,
    Trade,
    TradingSignal,
    quantize_amount,
    quantize_percent,
    quantize_price,
)

from backtest_service import __version__ as BACKTEST_SERVICE_VERSION
from backtest_service.adapters.catalog_store import (
    DeterminismReference,
    normalized_config_hash,
)
from backtest_service.adapters.evidence_schema import (
    EVIDENCE_SCHEMA_VERSION,
    canonical_json,
    encode_eval_decision,
)
from backtest_service.adapters.evidence_sink import (
    EvidenceRecord,
    epoch_milliseconds,
)
from backtest_service.adapters.ohlcv_gaps import (
    OhlcvGapContract,
    build_ohlcv_gap_contract,
    timeframe_milliseconds,
)
from backtest_service.config import RunConfig

_RUN_ID = re.compile(r"^BT_[0-9]{8}_(?P<seq>[0-9]+)_(?P<name>[a-z0-9-]+)$")
MIN_DATA_COVERAGE_RATIO: Final = 0.95
MAX_CONSECUTIVE_GAP_SECONDS: Final = 86_400
# Deliberate design divergence: backtests use the same per-finalized-candle
# incremental path as live/paper.  This keeps look-ahead exclusion structural;
# the vectorized path remains the batch API and the independent parity oracle.
BACKTEST_INDICATOR_EXECUTION_MODE: Final = "incremental"


@runtime_checkable
class _ExecutionBroker(Protocol):
    def configure_execution(
        self,
        decision_candle: Candle,
        history: list[Candle],
        *,
        fill_timing: str = "next_bar",
        risk_budget: Decimal | None = None,
        available_margin: Decimal | None = None,
        leverage: int = 1,
    ) -> None:
        """Bind one next-bar matching context."""


@runtime_checkable
class _BoundEvidence(Protocol):
    @property
    def path(self) -> str | None:
        """Return the bound path."""

    @property
    def integrity_results(self) -> dict[str, bool]:
        """Return finalized integrity facts."""

    def bind(self, run_id: str) -> str:
        """Bind an issued run id."""

    def audit(self, *, require_eval_decision: bool = False) -> dict[str, bool]:
        """Audit persisted facts."""

    def set_eval_decision(self, eval_decision_json: str) -> None:
        """Store the canonical evaluation output."""

    def set_determinism_reference(
        self,
        *,
        catalog_config_matches: bool,
        catalog_source_matches: bool,
        same_config_run_exists: bool,
        same_schema_run_exists: bool,
        source_data_hash: str,
        evidence_schema_version: str,
        comparison_run_id: str | None,
        comparison_hash: str | None,
    ) -> None:
        """Bind a catalog-backed cross-run comparison."""

    def source_data_hash(self) -> str:
        """Return the comparison fingerprint of persisted source snapshots."""


@runtime_checkable
class _DeterminismCatalog(Protocol):
    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
        source_data_hash: str,
        evidence_schema_version: str,
    ) -> DeterminismReference:
        """Return current-config and previous-hash catalog facts."""


@runtime_checkable
class _OrphanReconciler(Protocol):
    def reconcile_orphaned(self) -> int:
        """Mark unfinished runs left by an earlier interrupted process."""


@runtime_checkable
class _FundingDiagnostics(Protocol):
    def funding_diagnostics(self) -> dict[str, int]:
        """Return cumulative funding and mark-price measurement counts."""


# Warm-up needs `required_warmup` confirmed buckets before the evaluation start, but
# missing candles mean a span of that many buckets can yield fewer. Reading a multiple
# of the span absorbs ordinary gaps; a run that still falls short releases the bound and
# re-reads, so the optimization can never cost warm-up coverage.
_WARMUP_SPAN_FACTOR = 4


@runtime_checkable
class _BoundedHistory(Protocol):
    def limit_history(self, floor: datetime | None) -> None:
        """Bound source reads below, or release the bound when given ``None``."""


@runtime_checkable
class _SourceOrigin(Protocol):
    def source_candles(
        self,
        symbol: str,
        range_start: datetime,
        range_end: datetime,
    ) -> tuple[Candle, ...]:
        """Return an independent query of bounded 1m source values."""


@dataclass(frozen=True, slots=True)
class RunResult:
    """The immutable result returned by one Engine run."""

    run_id: str
    evidence_path: str
    evidence_hash: str
    integrity_status: str
    metrics: MetricSet
    decision: DecisionResult
    r_multiples: tuple[float, ...] = ()
    period_returns: tuple[float, ...] = ()


@dataclass(slots=True)
class _PendingOrder:
    request: OrderRequest
    decision_id: int
    decision_candle: Candle
    feature_ts: int
    decision_ts: int
    exit_reason: ExitReason | None = None
    signal: TradingSignal | None = None
    candidate_id: int | None = None


@dataclass(slots=True)
class _ActiveTrade:
    trade_id: int
    entry_execution_id: int
    entry_fill: Fill
    signal: TradingSignal
    r0: Decimal | None
    candidate_id: int | None
    total_fee: Decimal
    slippage: Decimal
    funding: Decimal = field(default_factory=lambda: quantize_amount(ZERO))
    position_records: list[EvidenceRecord] = field(default_factory=list)
    funding_records: list[EvidenceRecord] = field(default_factory=list)
    settled_boundaries: set[datetime] = field(default_factory=set)
    entry_features: dict[str, object] = field(default_factory=dict)
    mae_features: dict[str, object] = field(default_factory=dict)
    mfe_features: dict[str, object] = field(default_factory=dict)
    mae_ts: datetime | None = None
    mfe_ts: datetime | None = None
    mae_r: Decimal | None = None
    mfe_r: Decimal | None = None
    mae_pnl: Decimal | None = None
    mfe_pnl: Decimal | None = None


class Engine:
    """Own the no-look-ahead order of port and core-lib calls for one run."""

    def __init__(
        self,
        feed: DataFeed,
        broker: Broker,
        clock: Clock,
        cost_model: CostModel,
        evidence: EvidenceSink,
        catalog: CatalogStore,
        manager: AdapterManager,
        *,
        prereg: Mapping[str, object],
        engine_version: str = BACKTEST_SERVICE_VERSION,
        core_lib_version: str = CORE_LIB_VERSION,
        thresholds: Mapping[str, float] | None = None,
    ) -> None:
        if not isinstance(broker, _ExecutionBroker):
            raise TypeError("Engine requires a Broker with configure_execution")
        if not isinstance(evidence, _BoundEvidence):
            raise TypeError("Engine requires an EvidenceSink with bind/audit lifecycle")
        if not isinstance(catalog, _DeterminismCatalog):
            raise TypeError("Engine requires a CatalogStore with determinism_reference")
        self.feed = feed
        self.broker = broker
        self.clock = clock
        self.cost_model = cost_model
        self.evidence = evidence
        self.catalog = catalog
        self.manager = manager
        self.prereg = dict(prereg)
        self.engine_version = engine_version
        self.core_lib_version = core_lib_version
        self.thresholds = dict(universal() if thresholds is None else thresholds)

        self.config: RunConfig | None = None
        self.pending: list[_PendingOrder] = []
        self._strategy: StrategyAdapter | None = None
        self._money_management: MoneyManagementPolicy | None = None
        self._history: list[Candle] = []
        self._preload: list[Candle] = []
        self._evaluation: list[Candle] = []
        self._confirmed: list[Candle] = []
        self._minute_history: list[Candle] = []
        self._indicator_specs: list[SeriesSpec] = []
        self._indicator_states: dict[str, SeriesState] = {}
        self._indicator_values: dict[str, object] = {}
        self._turtle_n_values: tuple[tuple[datetime, float], ...] = ()
        self._funding_rates: dict[datetime, tuple[Decimal, str]] = {}
        self._funding_diagnostics = {
            "exact_count": 0,
            "normalized_count": 0,
            "missing_count": 0,
            "mark_exact_count": 0,
            "mark_normalized_count": 0,
            "mark_missing_count": 0,
        }
        self._book = PositionBook()
        self._cash = quantize_amount(ZERO)
        self._equity_curve: list[tuple[datetime, Decimal]] = []
        self._trades: list[Trade] = []
        self._active_trade: _ActiveTrade | None = None
        self._stop_price: Decimal | None = None
        self._take_profit_price: Decimal | None = None
        self._run_id: str | None = None
        self._evidence_path: str | None = None
        self._run_meta: dict[str, object] = {}
        self._last_candle: Candle | None = None
        self._gap_stats: dict[str, int | float | bool] = {}
        self._strategy_gap_contract: OhlcvGapContract | None = None
        self._data_gap_exit_count = 0
        self._sequence = {
            "signal": 0,
            "decision": 0,
            "execution": 0,
            "trade": 0,
            "position": 0,
            "equity": 0,
            "candidate": 0,
            "tfs": 0,
            "settlement": 0,
            "indicator_snapshot": 0,
            "source_snapshot": 0,
        }

    def run(self, config: RunConfig) -> RunResult:
        """Resolve config, issue run_id, execute the candle loop, and finalize."""
        if isinstance(self.catalog, _OrphanReconciler):
            self.catalog.reconcile_orphaned()
        config.revalidate()
        if config.trigger_feed != "tf_candle":
            raise NotImplementedError("m1_subcandle trigger walk remains reserved")
        self.config = config
        self._cash = self._checked_cash(config.initial_capital, context="run initialization")
        runtime = self.manager.create_runtime(
            config.strategy_id,
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
            config.money_management.model_dump(),
        )
        self._strategy = runtime.strategy
        self._money_management = runtime.money_management
        self.manager.activate(config.strategy_id)
        metadata = self._strategy.get_metadata()
        if config.timeframe not in metadata.supported_timeframes:
            raise ValueError("strategy does not support the configured timeframe")
        resolved = StrategyConfig.resolve(
            self._strategy.get_parameter_schema(),
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
        )
        required_indicators = [
            *metadata.required_indicators,
            *self._strategy_timeframe_policy_indicators(),
        ]
        self._indicator_specs = resolve_series_specs(
            config.indicator_mode,
            required_indicators,
            config.explicit_indicators,
            DEFAULT_REGISTRY,
            DEFAULT_PATTERN_REGISTRY,
        )
        if config.indicator_mode == "explicit":
            required_ids = {
                spec.identifier
                for spec in series_specs_from_descriptors(
                    required_indicators,
                    DEFAULT_REGISTRY,
                    DEFAULT_PATTERN_REGISTRY,
                )
            }
            explicit_ids = {spec.identifier for spec in self._indicator_specs}
            missing_required = sorted(required_ids - explicit_ids)
            if missing_required:
                raise ValueError(
                    "explicit_indicators missing strategy-required indicators: "
                    + ", ".join(missing_required)
                )
        longest_indicator_history = max(spec.min_history for spec in self._indicator_specs)
        required_warmup = max(metadata.min_history, longest_indicator_history)

        self._history, available_preload = self._load_history(config, required_warmup)
        if len(available_preload) < required_warmup:
            raise ValueError(
                "insufficient warm-up history: "
                f"requires {required_warmup}, got {len(available_preload)}"
            )
        self._preload = available_preload[-required_warmup:]
        self._evaluation = [
            candle
            for candle in self._history
            if candle.open_time >= config.start and candle.close_time <= config.end
        ]
        if not self._evaluation:
            raise ValueError("evaluation period contains no confirmed candles")
        self._prepare_indicator_states()
        self._prepare_money_management_sources()
        self._prepare_funding_sources()

        profile = metadata.profile
        params_json = {
            **dict(resolved.params),
            "_money_management": self._money_management_evidence(),
        }
        profile_json = asdict(profile)
        self._run_meta = {
            "run_name": config.run_name,
            "strategy_id": config.strategy_id,
            "strategy_name": type(self._strategy).__name__,
            "strategy_version": str(getattr(type(self._strategy), "VERSION", "1.0.0")),
            "params_json": params_json,
            "resolved_indicators_json": [
                {
                    "name": spec.name,
                    "params": dict(spec.params),
                    "version": spec.version,
                }
                for spec in self._indicator_specs
            ]
            + self._daily_policy_indicator_evidence(),
            "params_schema_version": resolved.schema_version,
            "symbol": config.symbol,
            "exchange": config.exchange,
            "timeframe": config.timeframe,
            "market_type": config.market_type.upper(),
            "period_start": config.start,
            "period_end": config.end,
            "warmup_start": self._preload[0].open_time if self._preload else None,
            "warmup_candles": len(self._preload),
            "data_source": config.data_source,
            "indicator_mode": config.indicator_mode,
            "trigger_feed": config.trigger_feed,
            "fill_timing": config.fill_timing,
            "initial_capital": self._cash,
            "sizing_method": config.sizing_method,
            "risk_per_trade": config.risk_per_trade,
            "position_size_pct": config.position_size_pct,
            "framework_compliant": config.sizing_method == "risk_based",
            "cost_values_json": dict(config.cost_values),
            "seed": config.seed,
            "engine_version": self.engine_version,
            "core_lib_version": self.core_lib_version,
            "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
            "config_hash": "",
            "profile_ref": config.profile_ref,
            "strategy_profile_json": profile_json,
            "envelope_status_declared": profile.envelope_status,
            "sweep_id": self._sweep_value("sweep_id"),
            "fold_label": self._sweep_value("fold_label"),
        }
        self._run_meta["config_hash"] = normalized_config_hash(self._run_meta)
        self._run_id = self.catalog.register(self._run_meta)
        self._evidence_path = self.evidence.bind(self._run_id)
        self._record_local_run(profile_json)
        self._record_indicator_definitions()
        self._record_source_snapshots()
        self.catalog.save_prereg(self._catalog_prereg())

        self.preload()
        for index, candle in enumerate(self._evaluation):
            self._last_candle = candle
            self._move_clock(candle.open_time)
            self.step_open(candle)
            self._move_clock(candle.close_time)
            self.step_close(candle)
            if index + 1 < len(self._evaluation):
                next_candle = self._evaluation[index + 1]
                if next_candle.open_time != candle.close_time:
                    self._close_at_data_gap(candle)
                self._move_clock(next_candle.open_time)
        return self.finalize()

    def preload(self) -> list[Candle]:
        """Return warmed candles while structurally discarding all preload signals."""
        self._confirmed = list(self._preload)
        for state in self._indicator_states.values():
            state.seed(self._preload)
            if not state.warmed_up:
                raise ValueError("indicator state did not warm up after required preload")
        return list(self._preload)

    def step_open(self, candle: Candle) -> None:
        """Charge open boundary, execute orders, charge crossings, then trigger."""
        if self.clock.now() != candle.open_time:
            raise ValueError("Clock must be at candle.open_time during step_open")
        self._settle_at_boundary(candle.open_time)
        carried = list(self.pending)
        self.pending.clear()
        for pending in carried:
            if pending.decision_candle.close_time != candle.open_time:
                raise ValueError("pending order crossed a missing candle boundary")
            self.broker.configure_execution(
                pending.decision_candle,
                self._history,
                fill_timing=self._config().fill_timing,
                risk_budget=self._risk_budget(pending),
                available_margin=self._cash,
                leverage=self._leverage(pending.signal),
            )
            fill = self.broker.submit(pending.request)
            if pending.exit_reason is not None:
                fill = replace(fill, exit_reason=pending.exit_reason)
            if not (pending.feature_ts <= pending.decision_ts < epoch_milliseconds(fill.timestamp)):
                raise ValueError("feature_ts <= decision_ts < execution_ts was violated")
            self._apply_fill(
                fill,
                decision_id=pending.decision_id,
                signal=pending.signal,
                candidate_id=pending.candidate_id,
            )

        for boundary in funding_boundaries_between(
            candle.open_time,
            candle.close_time,
        ):
            self._settle_at_boundary(boundary)

        position = self._current_position()
        if position is not None:
            trigger = self.walk_triggers(position, [candle])
            if trigger is not None:
                self._track_excursions(candle, position)
                decision_id = self._next("decision")
                self.evidence.record(
                    EvidenceRecord(
                        "DECISION",
                        {
                            "decision_id": decision_id,
                            "decision_ts": candle.open_time,
                            "action": "exit",
                            "intended_side": position.side.name,
                            "intended_qty": float(position.quantity),
                            "framework_compliant": self._config().sizing_method == "risk_based",
                            "planned_execution_ts": candle.close_time,
                        },
                    )
                )
                self._apply_fill(trigger, decision_id=decision_id)

    def step_close(self, candle: Candle) -> None:
        """Record the confirmed grid, analyze it, and queue only next-bar orders."""
        if self.clock.now() != candle.close_time:
            raise ValueError("Clock must be at candle.close_time during step_close")
        if candle.close_time > self.clock.now():
            raise ValueError("Engine cannot confirm a future candle")
        self._confirmed.append(candle)
        self._update_indicators(candle)
        self._mark_grid(candle)
        signal = self._strategy_instance().analyze(
            {
                "candles": list(self._confirmed),
                "candle": candle,
                "symbol": self._config().symbol,
                "timeframe": self._config().timeframe,
                "market_type": self._config().market_type,
                "indicators": dict(self._indicator_values),
            },
            self._current_position(),
        )
        if signal is None:
            return
        if isinstance(signal, DecisionIntent):
            decision = signal
            if decision.action is DecisionAction.HOLD:
                return
            if decision.timestamp > candle.close_time:
                raise ValueError("strategy decision cannot be later than the confirmed candle")
            try:
                signal = self._managed_signal(candle, decision)
            except MoneyManagementError:
                side = (
                    PositionSide.LONG
                    if decision.action is DecisionAction.ENTER_LONG
                    else PositionSide.SHORT
                )
                self._record_blocked_candidate(candle, side, "money_management_rejected")
                return
        if signal.timestamp > candle.close_time:
            raise ValueError("strategy signal cannot be later than the confirmed candle")
        self._handle_signal(candle, signal)

    def walk_triggers(
        self,
        position: Position,
        subcandles: list[Candle],
    ) -> Fill | None:
        """Run the reserved interface in conservative TF-candle mode only."""
        if self._config().trigger_feed != "tf_candle":
            raise NotImplementedError("m1_subcandle trigger walk remains reserved")
        entry_time = None if self._active_trade is None else self._active_trade.entry_fill.timestamp
        return resolve_triggers(
            position,
            subcandles,
            self.cost_model,
            stop_price=self._stop_price,
            take_profit_price=self._take_profit_price,
            entry_time=entry_time,
        )

    def finalize(self) -> RunResult:
        """Close end-of-data positions, evaluate, finalize Evidence, and catalog it."""
        last = self._last_candle
        if last is None:
            raise RuntimeError("cannot finalize before the candle loop")
        position = self._current_position()
        if position is not None:
            terminal = Candle(
                symbol=last.symbol,
                exchange=last.exchange,
                timeframe=last.timeframe,
                open_time=last.close_time + timedelta(milliseconds=1),
                close_time=last.close_time
                + timedelta(milliseconds=1)
                + (last.close_time - last.open_time),
                open=last.close,
                high=last.close,
                low=last.close,
                close=last.close,
                volume=0.0,
                quote_volume=None,
                trade_count=None,
            )
            request = self._exit_request(position)
            self.broker.configure_execution(
                last,
                [last, terminal],
                fill_timing="next_bar",
                available_margin=self._cash,
                leverage=position.leverage,
            )
            fill = replace(
                self.broker.submit(request),
                exit_reason=ExitReason.END_OF_DATA,
            )
            self._apply_fill(fill, decision_id=None)

        final_equity = recompute(self._cash, self._current_position())
        terminal_ts = last.close_time + timedelta(milliseconds=1)
        self._equity_curve.append((terminal_ts, final_equity))
        self._record_terminal_equity(terminal_ts, final_equity)
        metrics = compute(self._trades, self._equity_curve)
        run_r_multiples = tuple(trade_r_multiples(self._trades))
        run_period_returns = tuple(daily_returns(self._equity_curve))
        preliminary_integrity = check_integrity(self.evidence.audit())
        coverage_failed = [
            name
            for name, failed in (
                (
                    "data_coverage_ratio",
                    float(self._gap_stats["data_coverage_ratio"]) < MIN_DATA_COVERAGE_RATIO,
                ),
                (
                    "max_consecutive_gap",
                    int(self._gap_stats["max_consecutive_gap_seconds"])
                    > MAX_CONSECUTIVE_GAP_SECONDS,
                ),
            )
            if failed
        ]
        if preliminary_integrity.passed and not coverage_failed:
            gate = judge(metrics, self.thresholds, self._strategy_instance().get_metadata().profile)
        elif preliminary_integrity.passed:
            gate = GateResult(
                passed=False,
                stage="A",
                failed=coverage_failed,
                verdict="not_promotable",
            )
        else:
            gate = GateResult(
                passed=False,
                stage="A",
                failed=list(preliminary_integrity.failed_checks),
                verdict="not_promotable",
            )
        observed = self._observed_metric(metrics)
        decision_inputs = {
            **self.prereg,
            "observed_value": observed,
            "edge_distinguishable": bool(self.prereg.get("edge_distinguishable", True)),
            "higher_is_better": bool(self.prereg.get("higher_is_better", True)),
        }
        if gate.passed:
            final_decision = decide(gate, decision_inputs)
        else:
            final_decision = DecisionResult(
                route="retest",
                rationale=f"hard gate failed: {', '.join(gate.failed)}",
            )
        self.evidence.set_eval_decision(
            encode_eval_decision(
                observed_value=observed,
                edge_distinguishable=bool(decision_inputs["edge_distinguishable"]),
                decision_route=final_decision.route,
                higher_is_better=bool(decision_inputs["higher_is_better"]),
            )
        )
        source_data_hash = self.evidence.source_data_hash()
        reference = self.catalog.determinism_reference(
            self._require_run_id(),
            str(self._run_meta["config_hash"]),
            source_data_hash,
            EVIDENCE_SCHEMA_VERSION,
        )
        self.evidence.set_determinism_reference(
            catalog_config_matches=reference.catalog_config_matches,
            catalog_source_matches=reference.catalog_source_matches,
            same_config_run_exists=reference.same_config_run_exists,
            same_schema_run_exists=reference.same_schema_run_exists,
            source_data_hash=source_data_hash,
            evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
            comparison_run_id=reference.comparison_run_id,
            comparison_hash=reference.comparison_hash,
        )
        evidence_hash = self.evidence.finalize(self._require_run_id())
        integrity = check_integrity(self.evidence.integrity_results)
        integrity_status = "passed" if integrity.passed else "diagnostic_only"
        self.catalog.upsert_summary(
            self._summary(
                metrics,
                gate,
                final_decision,
                evidence_hash,
                integrity_status,
                integrity.failed_checks,
                final_equity,
            )
        )
        return RunResult(
            run_id=self._require_run_id(),
            evidence_path=self._require_evidence_path(),
            evidence_hash=evidence_hash,
            integrity_status=integrity_status,
            metrics=metrics,
            decision=final_decision,
            r_multiples=run_r_multiples,
            period_returns=run_period_returns,
        )

    def _handle_signal(self, candle: Candle, signal: TradingSignal) -> None:
        position = self._current_position()
        intent, side = self._derive_intent(signal, position)
        signal_id = self._next("signal")
        self.evidence.record(
            EvidenceRecord(
                "SIGNAL",
                {
                    "signal_id": signal_id,
                    "decision_ts": candle.close_time,
                    "feature_ts": candle.close_time,
                    "candle_open_time": candle.open_time,
                    "candle_close_time": candle.close_time,
                    "symbol": signal.symbol,
                    "price": signal.price,
                    "confidence": signal.confidence,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "market_type": signal.market_type.value,
                    "leverage": signal.leverage,
                    "reason": signal.reason,
                    "metadata_json": signal.metadata,
                    "derived_intent": intent,
                    "derived_side": None if side is None else side.name,
                    "is_warmup": False,
                },
            )
        )
        decision_id = self._next("decision")
        next_candle = self._next_candle(candle)
        if next_candle is not None and next_candle.open_time != candle.close_time:
            next_candle = None
            missing_next_bar = True
        else:
            missing_next_bar = False
        planned = (
            None
            if next_candle is None
            else max(
                next_candle.open_time,
                candle.close_time + timedelta(milliseconds=1),
            )
        )

        if intent == "exit":
            if position is None or next_candle is None:
                self._record_skip_decision(
                    decision_id,
                    signal_id,
                    candle,
                    (
                        "no_position"
                        if position is None
                        else "next_candle_gap"
                        if missing_next_bar
                        else "end_of_data"
                    ),
                )
                return
            self._record_action_decision(
                decision_id,
                signal_id,
                candle,
                "exit",
                position.side,
                float(position.quantity),
                planned,
            )
            self.pending.append(
                _PendingOrder(
                    request=self._exit_request(position),
                    decision_id=decision_id,
                    decision_candle=candle,
                    feature_ts=epoch_milliseconds(candle.close_time),
                    decision_ts=epoch_milliseconds(candle.close_time),
                    exit_reason=ExitReason.SIGNAL_EXIT,
                    signal=signal,
                )
            )
            return

        if side is None:
            raise RuntimeError("entry and reversal signals require a derived side")
        if position is not None and position.side is side:
            self._record_skip_decision(
                decision_id,
                signal_id,
                candle,
                "pyramiding_disabled",
            )
            self._record_blocked_candidate(candle, side, "pyramiding_disabled")
            return
        quantity, stop_distance = self._size(signal)
        risk_fraction = self._config().risk_per_trade or 0.0
        within_limits = all(
            (
                exposure_limit.single_market([float(risk_fraction)], 0.01),
                exposure_limit.correlation_group([float(risk_fraction)], 0.01),
                exposure_limit.single_direction([float(risk_fraction)], 0.01),
            )
        )
        candidate_id = self._next("candidate")
        if not within_limits or next_candle is None:
            reason = (
                "exposure_limit"
                if not within_limits
                else "next_candle_gap"
                if missing_next_bar
                else "end_of_data"
            )
            self._record_skip_decision(decision_id, signal_id, candle, reason)
            self.evidence.record(
                EvidenceRecord(
                    "CANDIDATE_EVENT",
                    {
                        "candidate_id": candidate_id,
                        "ts": candle.close_time,
                        "symbol": signal.symbol,
                        "trigger_rule": signal.reason,
                        "passed_filters_json": [],
                        "blocked_by": reason,
                        "would_be_side": side.name,
                        "would_be_qty": to_decimal(quantity, quantizer=quantize_amount),
                        "realized": False,
                    },
                )
            )
            return
        self._record_action_decision(
            decision_id,
            signal_id,
            candle,
            "reverse" if position is not None else "enter",
            side,
            quantity,
            planned,
            signal=signal,
            stop_distance=stop_distance,
        )
        if position is not None:
            self.pending.append(
                _PendingOrder(
                    request=self._exit_request(position),
                    decision_id=decision_id,
                    decision_candle=candle,
                    feature_ts=epoch_milliseconds(candle.close_time),
                    decision_ts=epoch_milliseconds(candle.close_time),
                    exit_reason=ExitReason.REVERSAL,
                    signal=signal,
                )
            )
        self.pending.append(
            _PendingOrder(
                request=self._entry_request(signal, side, quantity),
                decision_id=decision_id,
                decision_candle=candle,
                feature_ts=epoch_milliseconds(candle.close_time),
                decision_ts=epoch_milliseconds(candle.close_time),
                signal=signal,
                candidate_id=candidate_id,
            )
        )

    def _close_at_data_gap(self, candle: Candle) -> None:
        """Close known exposure at the last confirmed price before an unknown span."""
        if self.pending:
            raise RuntimeError("orders must not remain pending across a data gap")
        position = self._current_position()
        if position is None:
            return
        execution_time = candle.close_time + timedelta(milliseconds=1)
        decision_id = self._next("decision")
        self.evidence.record(
            EvidenceRecord(
                "DECISION",
                {
                    "decision_id": decision_id,
                    "decision_ts": candle.close_time,
                    "action": "exit",
                    "intended_side": position.side.name,
                    "intended_qty": float(position.quantity),
                    "framework_compliant": (self._config().sizing_method == "risk_based"),
                    "planned_execution_ts": execution_time,
                },
            )
        )
        terminal = Candle(
            symbol=candle.symbol,
            exchange=candle.exchange,
            timeframe=candle.timeframe,
            open_time=execution_time,
            close_time=execution_time + (candle.close_time - candle.open_time),
            open=candle.close,
            high=candle.close,
            low=candle.close,
            close=candle.close,
            volume=0.0,
            quote_volume=None,
            trade_count=None,
        )
        self.broker.configure_execution(
            candle,
            [candle, terminal],
            fill_timing=self._config().fill_timing,
            available_margin=self._cash,
            leverage=position.leverage,
        )
        fill = replace(
            self.broker.submit(self._exit_request(position)),
            exit_reason=ExitReason.DATA_GAP,
        )
        self._apply_fill(fill, decision_id=decision_id)
        self._data_gap_exit_count += 1

    def _derive_intent(
        self,
        signal: TradingSignal,
        position: Position | None,
    ) -> tuple[str, PositionSide | None]:
        if signal.stop_loss is None and signal.take_profit is None:
            return "exit", None
        protection = signal.stop_loss if signal.stop_loss is not None else signal.take_profit
        assert protection is not None
        if protection == signal.price:
            raise ValueError("protection level cannot equal signal price")
        if signal.stop_loss is not None:
            side = PositionSide.LONG if protection < signal.price else PositionSide.SHORT
        else:
            side = PositionSide.LONG if protection > signal.price else PositionSide.SHORT
        intent = "reverse" if position is not None and position.side is not side else "enter"
        return intent, side

    def _size(self, signal: TradingSignal) -> tuple[float, float]:
        protection = signal.stop_loss if signal.stop_loss is not None else signal.take_profit
        if protection is None:
            raise ValueError("entry sizing requires a protection level")
        stop_distance = abs(signal.price - protection)
        if stop_distance <= 0.0:
            raise ValueError("entry sizing requires a positive stop distance")
        if self._config().sizing_method == "risk_based":
            money_management = signal.metadata.get("money_management")
            requested = (
                money_management.get("requested_quantity")
                if isinstance(money_management, Mapping)
                else None
            )
            if isinstance(requested, bool) or not isinstance(requested, float | int):
                risk = self._config().risk_per_trade
                assert risk is not None
                quantity = risk_size(risk, float(self._current_equity()), stop_distance)
            else:
                quantity = float(requested)
        else:
            pct = self._config().position_size_pct
            assert pct is not None
            notional = wallet_pct_size(float(self._cash), pct)
            quantity = notional / signal.price
        return quantity, stop_distance

    def _managed_signal(
        self,
        candle: Candle,
        decision: DecisionIntent,
    ) -> TradingSignal:
        policy = self._money_management
        if decision.action is DecisionAction.EXIT:
            return TradingSignal(
                symbol=decision.symbol,
                timestamp=decision.timestamp,
                confidence=decision.confidence,
                price=decision.reference_price,
                stop_loss=None,
                take_profit=None,
                market_type=self._market_type(),
                leverage=1,
                reason=decision.reason,
                metadata={
                    **dict(decision.metadata),
                    "decision_action": decision.action.value,
                    "money_management": self._money_management_evidence(),
                },
            )
        if policy is None:
            raise MoneyManagementError("strategy entry requires a money-management policy")
        volatility, volatility_name, volatility_timestamp = self._money_management_volatility(
            candle, policy
        )
        risk_per_trade = self._config().risk_per_trade or 0.01
        plan = policy.plan_entry(
            decision,
            MarketSnapshot(
                reference_price=decision.reference_price,
                volatility=volatility,
                volatility_name=volatility_name,
                volatility_timestamp=volatility_timestamp,
            ),
            AccountRiskSnapshot(
                equity=float(self._current_equity()),
                available_cash=float(self._cash),
                market_type=self._market_type(),
            ),
            RiskLimits(
                risk_per_trade=float(risk_per_trade),
                maintenance_margin_rate=float(self._maintenance_margin_rate()),
            ),
        )
        return TradingSignal(
            symbol=decision.symbol,
            timestamp=decision.timestamp,
            confidence=decision.confidence,
            price=decision.reference_price,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
            market_type=self._market_type(),
            leverage=plan.requested_leverage,
            reason=decision.reason,
            metadata={
                **dict(decision.metadata),
                "decision_action": decision.action.value,
                "money_management": {
                    **self._money_management_evidence(),
                    **dict(plan.diagnostics),
                    "requested_quantity": plan.requested_quantity,
                    "requested_leverage": plan.requested_leverage,
                    "initial_risk_amount": plan.initial_risk_amount,
                },
            },
        )

    def _money_management_volatility(
        self,
        candle: Candle,
        policy: MoneyManagementPolicy,
    ) -> tuple[float, str, datetime]:
        if policy.id == "manual":
            value = self._indicator_values.get("atr:period=14")
            if isinstance(value, bool) or not isinstance(value, float | int):
                raise MoneyManagementError("manual policy requires current ATR(14)")
            return float(value), "ATR(14)", candle.close_time
        if policy.id == "turtle":
            available = [item for item in self._turtle_n_values if item[0] <= candle.close_time]
            if not available:
                raise MoneyManagementError("turtle policy requires finalized daily N")
            timestamp, value = available[-1]
            return value, "TURTLE_N", timestamp
        raise MoneyManagementError(f"unsupported policy runtime: {policy.id!r}")

    def _entry_request(
        self,
        signal: TradingSignal,
        side: PositionSide,
        quantity: float,
    ) -> OrderRequest:
        return OrderRequest(
            symbol=signal.symbol,
            side=OrderSide.BUY if side is PositionSide.LONG else OrderSide.SELL,
            order_type=OrderType.MARKET,
            quantity=float(quantity),
            price=signal.price,
            stop_price=signal.stop_loss,
            market_type=signal.market_type,
            position_side=side,
            reduce_only=False,
            close_position=False,
            time_in_force="GTC",
        )

    def _exit_request(self, position: Position) -> OrderRequest:
        return OrderRequest(
            symbol=position.symbol,
            side=OrderSide.SELL if position.side is PositionSide.LONG else OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=float(position.quantity),
            price=None,
            stop_price=None,
            market_type=position.market_type,
            position_side=position.side,
            reduce_only=True,
            close_position=False,
            time_in_force="GTC",
        )

    def _apply_fill(
        self,
        fill: Fill,
        *,
        decision_id: int | None,
        signal: TradingSignal | None = None,
        candidate_id: int | None = None,
    ) -> None:
        position_before = self._current_position()
        projected_entry_cash: Decimal | None = None
        if not fill.reduce_only:
            leverage = self._leverage(signal)
            notional = quantize_amount(fill.price * fill.quantity)
            added_margin = (
                quantize_amount(notional / Decimal(leverage))
                if self._market_type() is MarketType.FUTURES
                else notional
            )
            projected_entry_cash = quantize_amount(self._cash - added_margin - fill.fee)
            if projected_entry_cash < ZERO:
                raise ValueError("entry margin plus fee exceeds available cash after truncation")
        execution_id = self._next("execution")
        self.evidence.record(
            EvidenceRecord(
                "EXECUTION",
                {
                    "execution_id": execution_id,
                    "decision_id": decision_id,
                    "order_id": fill.order_id,
                    "execution_ts": fill.timestamp,
                    "symbol": fill.symbol,
                    "side": fill.side.name,
                    "position_side": fill.position_side.name,
                    "order_type": "MARKET",
                    "reference_price": fill.reference_price,
                    "price": fill.price,
                    "quantity": fill.quantity,
                    "notional": quantize_amount(fill.price * fill.quantity),
                    "fee": fill.fee,
                    "slippage": fill.slippage,
                    "liquidity": fill.liquidity,
                    "reduce_only": fill.reduce_only,
                    "exit_reason": None if fill.exit_reason is None else fill.exit_reason.value,
                    "gap_filled": fill.gap_filled,
                    "qty_truncated": fill.qty_truncated,
                },
            )
        )
        if not fill.reduce_only:
            leverage = self._leverage(signal)
            before_margin = ZERO if position_before is None else position_before.margin
            self._book.apply(
                fill,
                leverage=leverage,
                margin_type=MarginType.ISOLATED,
                market_type=self._market_type(),
                liquidation_price=(
                    liquidation_price(
                        fill.price,
                        leverage,
                        self._maintenance_margin_rate(),
                        side=fill.position_side,
                    )
                    if self._market_type() is MarketType.FUTURES
                    else ZERO
                ),
            )
            position_after = self._current_position()
            assert position_after is not None
            added_margin = quantize_amount(position_after.margin - before_margin)
            actual_cash = quantize_amount(self._cash - added_margin - fill.fee)
            if projected_entry_cash is None or actual_cash != projected_entry_cash:
                raise RuntimeError("entry cash projection diverged from position accounting")
            self._cash = self._checked_cash(actual_cash, context="entry fill")
            if self._active_trade is None:
                if signal is None:
                    raise ValueError("entry fills require their originating signal")
                trade_id = self._next("trade")
                r0 = (
                    None
                    if signal.stop_loss is None
                    else quantize_amount(
                        abs(
                            fill.reference_price
                            - to_decimal(signal.stop_loss, quantizer=quantize_price)
                        )
                        * fill.quantity
                    )
                )
                self._active_trade = _ActiveTrade(
                    trade_id=trade_id,
                    entry_execution_id=execution_id,
                    entry_fill=fill,
                    signal=signal,
                    r0=r0,
                    candidate_id=candidate_id,
                    total_fee=fill.fee,
                    slippage=fill.slippage,
                    entry_features=dict(self._indicator_values),
                )
                self._stop_price = (
                    None
                    if signal.stop_loss is None
                    else to_decimal(signal.stop_loss, quantizer=quantize_price)
                )
                self._take_profit_price = (
                    None
                    if signal.take_profit is None
                    else to_decimal(signal.take_profit, quantizer=quantize_price)
                )
            else:
                self._active_trade.total_fee = quantize_amount(
                    self._active_trade.total_fee + fill.fee
                )
                self._active_trade.slippage = quantize_amount(
                    self._active_trade.slippage + fill.slippage
                )
            return

        if position_before is None or self._active_trade is None:
            raise ValueError("reduce-only fill requires an active position and trade")
        released_margin = quantize_amount(
            position_before.margin * fill.quantity / position_before.quantity
        )
        actual_delta = (
            fill.price - position_before.entry_price
            if position_before.side is PositionSide.LONG
            else position_before.entry_price - fill.price
        )
        actual_pnl = quantize_amount(actual_delta * fill.quantity)
        next_cash = self._checked_cash(
            self._cash + released_margin + actual_pnl - fill.fee,
            context=(
                "liquidation exit"
                if fill.exit_reason is ExitReason.LIQUIDATION
                else "position exit"
            ),
        )
        self._book.apply(fill)
        self._cash = next_cash
        active = self._active_trade
        active.total_fee = quantize_amount(active.total_fee + fill.fee)
        active.slippage = quantize_amount(active.slippage + fill.slippage)
        if self._current_position() is None:
            self._complete_trade(active, fill, execution_id)
            self._active_trade = None
            self._stop_price = None
            self._take_profit_price = None

    def _complete_trade(
        self,
        active: _ActiveTrade,
        exit_fill: Fill,
        exit_execution_id: int,
    ) -> None:
        side = active.entry_fill.position_side
        reference_delta = (
            exit_fill.reference_price - active.entry_fill.reference_price
            if side is PositionSide.LONG
            else active.entry_fill.reference_price - exit_fill.reference_price
        )
        gross = quantize_amount(reference_delta * exit_fill.quantity)
        penalty = quantize_amount(ZERO)
        net = quantize_amount(gross - active.total_fee - active.slippage - active.funding - penalty)
        basis = quantize_amount(active.entry_fill.reference_price * active.entry_fill.quantity)
        return_pct = quantize_percent(net / basis * Decimal("100"))
        exit_reason = exit_fill.exit_reason or ExitReason.SIGNAL_EXIT
        trade = Trade(
            source_type="backtest",
            symbol=exit_fill.symbol,
            side=active.entry_fill.side,
            market_type=self._market_type(),
            entry_price=active.entry_fill.reference_price,
            entry_quantity=active.entry_fill.quantity,
            entry_time=active.entry_fill.timestamp,
            exit_price=exit_fill.reference_price,
            exit_quantity=exit_fill.quantity,
            exit_time=exit_fill.timestamp,
            exit_reason=exit_reason,
            gross_pnl=gross,
            total_fee=active.total_fee,
            slippage=active.slippage,
            funding_cost=active.funding,
            liquidation_penalty=penalty,
            net_pnl=net,
            return_pct=return_pct,
            r0=active.r0,
            leverage=self._leverage(active.signal),
            liquidated=exit_reason is ExitReason.LIQUIDATION,
            wallet_id=None,
            backtest_run_id=self._require_run_id(),
            strategy_id=self._config().strategy_id,
            strategy_name=str(self._run_meta["strategy_name"]),
            hold_duration_seconds=int(
                (exit_fill.timestamp - active.entry_fill.timestamp).total_seconds()
            ),
            signal_confidence=active.signal.confidence,
            reason=active.signal.reason,
        )
        self._trades.append(trade)
        r_multiple = None if trade.r0 in {None, ZERO} else float(trade.net_pnl / trade.r0)
        self.evidence.record(
            EvidenceRecord(
                "TRADE",
                {
                    "trade_id": active.trade_id,
                    "backtest_run_id": self._require_run_id(),
                    "source_type": "backtest",
                    "symbol": trade.symbol,
                    "side": side.name,
                    "market_type": trade.market_type.name,
                    "entry_execution_id": active.entry_execution_id,
                    "exit_execution_id": exit_execution_id,
                    "entry_price": trade.entry_price,
                    "entry_quantity": trade.entry_quantity,
                    "entry_time": trade.entry_time,
                    "exit_price": trade.exit_price,
                    "exit_quantity": trade.exit_quantity,
                    "exit_time": trade.exit_time,
                    "exit_reason": trade.exit_reason.value,
                    "gross_pnl": trade.gross_pnl,
                    "total_fee": trade.total_fee,
                    "slippage": trade.slippage,
                    "liquidation_penalty": trade.liquidation_penalty,
                    "funding_cost": trade.funding_cost,
                    "net_pnl": trade.net_pnl,
                    "return_pct": float(trade.return_pct),
                    "r0": trade.r0,
                    "r_multiple": r_multiple,
                    "leverage": trade.leverage,
                    "liquidated": trade.liquidated,
                    "strategy_id": trade.strategy_id,
                    "strategy_name": trade.strategy_name,
                    "hold_duration_seconds": trade.hold_duration_seconds,
                    "signal_confidence": trade.signal_confidence,
                    "reason": trade.reason,
                },
            )
        )
        for record in active.position_records:
            self.evidence.record(record)
        for record in active.funding_records:
            self.evidence.record(record)
        if active.candidate_id is not None:
            self.evidence.record(
                EvidenceRecord(
                    "CANDIDATE_EVENT",
                    {
                        "candidate_id": active.candidate_id,
                        "ts": active.signal.timestamp,
                        "symbol": active.signal.symbol,
                        "trigger_rule": active.signal.reason,
                        "passed_filters_json": ["exposure_limit"],
                        "would_be_side": side.name,
                        "would_be_qty": active.entry_fill.quantity,
                        "realized": True,
                        "linked_trade_id": active.trade_id,
                    },
                )
            )
        exit_features = dict(self._indicator_values)
        feature_rows = (
            (
                "entry",
                active.entry_fill.timestamp,
                active.entry_features,
                None,
            ),
            ("exit", exit_fill.timestamp, exit_features, None),
            (
                "mae",
                active.mae_ts or active.entry_fill.timestamp,
                active.mae_features or active.entry_features,
                active.mae_r,
            ),
            (
                "mfe",
                active.mfe_ts or active.entry_fill.timestamp,
                active.mfe_features or active.entry_features,
                active.mfe_r,
            ),
        )
        for phase, timestamp, features, excursion_r in feature_rows:
            self.evidence.record(
                EvidenceRecord(
                    "TRADE_FEATURE_SNAPSHOT",
                    {
                        "tfs_id": self._next("tfs"),
                        "trade_id": active.trade_id,
                        "phase": phase,
                        "ts": timestamp,
                        "features_json": features,
                        "excursion_r": (None if excursion_r is None else float(excursion_r)),
                    },
                )
            )

    def _mark_grid(self, candle: Candle) -> None:
        position = self._current_position()
        mark = to_decimal(candle.close, quantizer=quantize_price)
        if position is not None:
            position.update_price(mark)
            self._track_excursions(candle, position)
        current_position_value = position_value(position)
        equity = recompute(self._cash, position)
        peak = max((value for _, value in self._equity_curve), default=equity)
        peak = max(peak, equity)
        drawdown = float(equity / peak - Decimal("1")) if peak > ZERO else 0.0
        self._sequence["position"] += 1
        position_record = self._position_record(
            self._sequence["position"],
            candle,
            position,
            mark,
        )
        if position is not None and self._active_trade is not None:
            self._active_trade.position_records.append(position_record)
        else:
            self.evidence.record(position_record)
        self._sequence["equity"] += 1
        self.evidence.record(
            EvidenceRecord(
                "PORTFOLIO_PNL",
                {
                    "equity_seq": self._sequence["equity"],
                    "ts": candle.close_time,
                    "cash_balance": self._cash,
                    "position_value": current_position_value,
                    "total_equity": equity,
                    "unrealized_pnl": ZERO if position is None else position.unrealized_pnl,
                    "fee_cum": sum((trade.total_fee for trade in self._trades), ZERO)
                    + (ZERO if self._active_trade is None else self._active_trade.total_fee),
                    "slippage_cum": sum((trade.slippage for trade in self._trades), ZERO)
                    + (ZERO if self._active_trade is None else self._active_trade.slippage),
                    "funding_cum": sum((trade.funding_cost for trade in self._trades), ZERO)
                    + (ZERO if self._active_trade is None else self._active_trade.funding),
                    "peak_equity": peak,
                    "drawdown_pct": drawdown,
                    "open_positions": int(position is not None),
                },
            )
        )
        self._equity_curve.append((candle.close_time, equity))

    def _record_terminal_equity(self, terminal_ts: datetime, final_equity: Decimal) -> None:
        """Persist the equity that remains after the run closes what it still held.

        Bar-by-bar equity is recorded while a position is still open, so it carries that
        position at its mark rather than at what closing it would return. The run then
        closes the position, and the summary reports the equity that followed. Without
        this row the stored curve stops one step short of that: its last value differs
        from the reported final equity by the cost of the closing fill, and anyone
        recomputing from Evidence disagrees with the summary by exactly that amount.
        """
        position = self._current_position()
        self._sequence["equity"] += 1
        peak = max((value for _, value in self._equity_curve), default=final_equity)
        drawdown = float(final_equity / peak - Decimal("1")) if peak > ZERO else 0.0
        self.evidence.record(
            EvidenceRecord(
                "PORTFOLIO_PNL",
                {
                    "equity_seq": self._sequence["equity"],
                    "ts": terminal_ts,
                    "cash_balance": self._cash,
                    "position_value": position_value(position),
                    "total_equity": final_equity,
                    "unrealized_pnl": ZERO if position is None else position.unrealized_pnl,
                    "fee_cum": sum((trade.total_fee for trade in self._trades), ZERO),
                    "slippage_cum": sum((trade.slippage for trade in self._trades), ZERO),
                    "funding_cum": sum((trade.funding_cost for trade in self._trades), ZERO),
                    "peak_equity": peak,
                    "drawdown_pct": drawdown,
                    "open_positions": int(position is not None),
                },
            )
        )

    def _position_record(
        self,
        sequence: int,
        candle: Candle,
        position: Position | None,
        mark: Decimal,
    ) -> EvidenceRecord:
        if position is None:
            return EvidenceRecord(
                "POSITION",
                {
                    "position_seq": sequence,
                    "ts": candle.close_time,
                    "symbol": candle.symbol,
                    "side": "BOTH",
                    "quantity": ZERO,
                    "average_price": ZERO,
                    "total_cost": ZERO,
                    "current_price": mark,
                    "mark_price": mark,
                    "unrealized_pnl": ZERO,
                    "leverage": 1,
                    "margin_type": "ISOLATED",
                    "margin": ZERO,
                    "funding_fee_total": ZERO,
                },
            )
        return EvidenceRecord(
            "POSITION",
            {
                "position_seq": sequence,
                "trade_id": None if self._active_trade is None else self._active_trade.trade_id,
                "ts": candle.close_time,
                "symbol": position.symbol,
                "side": position.side.name,
                "quantity": position.quantity,
                "average_price": position.average_price,
                "total_cost": position.total_cost,
                "current_price": position.current_price,
                "mark_price": position.mark_price,
                "unrealized_pnl": position.unrealized_pnl,
                "leverage": position.leverage,
                "margin_type": position.margin_type.name,
                "margin": position.margin,
                "entry_price": position.entry_price,
                "liquidation_price": (
                    None if position.liquidation_price <= ZERO else position.liquidation_price
                ),
                "funding_fee_total": position.funding_fee_total,
            },
        )

    def _settle_at_boundary(self, boundary: datetime) -> None:
        if self._market_type() is not MarketType.FUTURES or not is_funding_boundary(boundary):
            return
        position = self._current_position()
        active = self._active_trade
        if (
            position is None
            or active is None
            or active.entry_fill.timestamp >= boundary
            or boundary in active.settled_boundaries
        ):
            return
        cached = self._funding_rates.get(boundary)
        if cached is None:
            try:
                rate = self.feed.funding(position.symbol, boundary)
                source = "measured"
            except LookupError:
                rate = self.cost_model.funding_rate(boundary)
                source = "fallback"
            cached = (rate, source)
            self._funding_rates[boundary] = cached
        rate, source = cached
        price, price_source = self._funding_price(boundary)
        theoretical_cost = settle_funding(position, rate, price)
        funding = self._book.apply_funding(
            position,
            theoretical_cost,
            maintenance_margin_rate=self._maintenance_margin_rate(),
        )
        payment_amount = quantize_amount(-funding.applied_cost)
        theoretical_payment_amount = quantize_amount(-funding.theoretical_cost)
        active.funding = quantize_amount(active.funding + funding.applied_cost)
        active.settled_boundaries.add(boundary)
        active.funding_records.append(
            EvidenceRecord(
                "FUNDING_SETTLEMENT",
                {
                    "settlement_id": self._next("settlement"),
                    "trade_id": active.trade_id,
                    "settled_at": boundary,
                    "symbol": position.symbol,
                    "position_side": position.side.name,
                    "funding_rate": float(rate),
                    "rate_source": source,
                    "settle_price": price,
                    "settle_price_source": price_source,
                    "position_notional": quantize_amount(position.quantity * price),
                    "payment_amount": payment_amount,
                    "theoretical_payment_amount": theoretical_payment_amount,
                },
            )
        )
        if funding.exhausted:
            decision_id = self._next("decision")
            execution_time = boundary + timedelta(milliseconds=1)
            self.evidence.record(
                EvidenceRecord(
                    "DECISION",
                    {
                        "decision_id": decision_id,
                        "decision_ts": boundary,
                        "action": "exit",
                        "intended_side": position.side.name,
                        "intended_qty": float(position.quantity),
                        "framework_compliant": (self._config().sizing_method == "risk_based"),
                        "planned_execution_ts": execution_time,
                    },
                )
            )
            fill = liquidation_fill(
                position,
                price,
                execution_time,
                self.cost_model,
            )
            self._apply_fill(fill, decision_id=decision_id)

    def _funding_price(self, boundary: datetime) -> tuple[Decimal, str]:
        source = self._minute_history or self._history
        exact = next(
            (candle for candle in source if candle.open_time == boundary),
            None,
        )
        if exact is not None:
            return to_decimal(exact.open, quantizer=quantize_price), "boundary_open"
        previous = [candle for candle in source if candle.close_time <= boundary]
        if not previous:
            previous = [candle for candle in self._history if candle.open_time < boundary]
        if not previous:
            raise LookupError(f"no settlement price at or before {boundary.isoformat()}")
        return to_decimal(previous[-1].close, quantizer=quantize_price), "prev_close"

    def _load_history(
        self,
        config: RunConfig,
        required_warmup: int,
    ) -> tuple[list[Candle], list[Candle]]:
        """Read the candle series, preferring a warm-up-sized read over the whole table.

        The floor is an optimization only. When the bounded read cannot supply the warm-up
        the strategy declared, the bound is released and the series is read again, so the
        result is identical to an unbounded read in every case.
        """
        bounded = self.feed if isinstance(self.feed, _BoundedHistory) else None
        if bounded is not None:
            bounded.limit_history(config.start - self._warmup_span(config, required_warmup))
        history, preload = self._read_history(config)
        if bounded is not None and len(preload) < required_warmup:
            bounded.limit_history(None)
            history, preload = self._read_history(config)
        return history, preload

    def _warmup_span(self, config: RunConfig, required_warmup: int) -> timedelta:
        """Cover every declared history requirement, not just the strategy timeframe.

        The money-management policy may derive its own values from a coarser timeframe:
        a daily N over twenty days needs far more calendar history than the strategy's
        own warm-up on an intraday bar. Reading only the strategy's span leaves that
        series starved, and the shortfall surfaces later as a missing daily history
        rather than as a short read.
        """
        spans = [timeframe_milliseconds(config.timeframe) * required_warmup]
        policy = self._money_management
        if policy is not None:
            for requirement in policy.required_indicators():
                timeframe = (
                    config.timeframe
                    if requirement.timeframe == "strategy"
                    else requirement.timeframe
                )
                period = requirement.params.get("period")
                bars = period if isinstance(period, int) and not isinstance(period, bool) else 0
                spans.append(timeframe_milliseconds(timeframe) * max(bars, requirement.min_history))
        return timedelta(milliseconds=max(spans) * _WARMUP_SPAN_FACTOR)

    def _read_history(self, config: RunConfig) -> tuple[list[Candle], list[Candle]]:
        history = sorted(
            self.feed.candles(config.symbol, config.timeframe, config.end),
            key=lambda candle: candle.open_time,
        )
        if any(
            right.open_time <= left.open_time
            for left, right in zip(history, history[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must have strictly increasing open_time")
        return history, [candle for candle in history if candle.close_time <= config.start]

    def _prepare_indicator_states(self) -> None:
        self._indicator_states = {
            spec.identifier: spec.make_state() for spec in self._indicator_specs
        }

    def _strategy_timeframe_policy_indicators(self) -> list[dict[str, object]]:
        policy = self._money_management
        if policy is None:
            return []
        return [
            {"name": requirement.name, "params": dict(requirement.params)}
            for requirement in policy.required_indicators()
            if requirement.timeframe == "strategy"
        ]

    def _daily_policy_indicator_evidence(self) -> list[dict[str, object]]:
        policy = self._money_management
        if policy is None:
            return []
        return [
            {
                "name": requirement.name,
                "params": {
                    **dict(requirement.params),
                    "timeframe": requirement.timeframe,
                },
                "version": policy.version,
            }
            for requirement in policy.required_indicators()
            if requirement.timeframe == "1d"
        ]

    def _prepare_money_management_sources(self) -> None:
        policy = self._money_management
        if policy is None or policy.id != "turtle":
            self._turtle_n_values = ()
            return
        requirements = [
            item
            for item in policy.required_indicators()
            if item.name == "TURTLE_N" and item.timeframe == "1d"
        ]
        if len(requirements) != 1:
            raise ValueError("turtle policy must declare exactly one daily N requirement")
        period = requirements[0].params.get("period")
        if isinstance(period, bool) or not isinstance(period, int):
            raise TypeError("turtle N period must be an integer")
        self._turtle_n_values = self._turtle_n_from_daily(period)
        if not any(timestamp <= self._config().start for timestamp, _ in self._turtle_n_values):
            # The bounded read is an optimization; releasing it and reading again keeps
            # a short read from being reported as missing history.
            bounded = self.feed if isinstance(self.feed, _BoundedHistory) else None
            if bounded is not None:
                bounded.limit_history(None)
                self._turtle_n_values = self._turtle_n_from_daily(period)
        if not any(timestamp <= self._config().start for timestamp, _ in self._turtle_n_values):
            raise ValueError("insufficient finalized daily history for turtle N at run start")

    def _turtle_n_from_daily(self, period: int) -> tuple[tuple[datetime, float], ...]:
        daily = sorted(
            (
                candle
                for candle in self.feed.candles(
                    self._config().symbol,
                    "1d",
                    self._config().end,
                )
                if candle.close_time <= self._config().end
            ),
            key=lambda candle: candle.open_time,
        )
        return turtle_n_series(daily, period=period)

    def _money_management_evidence(self) -> dict[str, object]:
        policy = self._money_management
        if policy is None:
            return {
                "policy_id": "legacy_signal",
                "policy_version": "1.0.0",
                "config_schema_version": "1.0.0",
                "resolved_config": {},
            }
        return {
            "policy_id": policy.id,
            "policy_version": policy.version,
            "config_schema_version": "1.0.0",
            "resolved_config": dict(policy.resolved_config()),
        }

    def _prepare_funding_sources(self) -> None:
        if self._config().timeframe == "1m":
            self._minute_history = list(self._history)
        else:
            self._minute_history = sorted(
                self.feed.candles(
                    self._config().symbol,
                    "1m",
                    self._config().end,
                ),
                key=lambda candle: candle.open_time,
            )
        if self._market_type() is not MarketType.FUTURES:
            return
        diagnostics_feed = self.feed if isinstance(self.feed, _FundingDiagnostics) else None
        before = diagnostics_feed.funding_diagnostics() if diagnostics_feed is not None else None
        for boundary in funding_boundaries_between(
            self._config().start,
            self._config().end,
        ):
            try:
                rate = self.feed.funding(self._config().symbol, boundary)
                source = "measured"
            except LookupError:
                rate = self.cost_model.funding_rate(boundary)
                source = "fallback"
            self._funding_rates[boundary] = (rate, source)
        if before is not None:
            assert diagnostics_feed is not None
            after = diagnostics_feed.funding_diagnostics()
            self._funding_diagnostics = {
                name: after[name] - before[name] for name in self._funding_diagnostics
            }
            if any(value < 0 for value in self._funding_diagnostics.values()):
                raise RuntimeError("funding diagnostic counters moved backwards")
        else:
            fallback_count = sum(source == "fallback" for _, source in self._funding_rates.values())
            self._funding_diagnostics = {
                "exact_count": len(self._funding_rates) - fallback_count,
                "normalized_count": 0,
                "missing_count": fallback_count,
                "mark_exact_count": 0,
                "mark_normalized_count": 0,
                "mark_missing_count": 0,
            }

    def _record_indicator_definitions(self) -> None:
        for spec in self._indicator_specs:
            if isinstance(spec, IndicatorSpec):
                series_kind = "indicator"
                category = spec.category
                impl_note = spec.pinned_impl
                pinned_impl = bool(spec.pinned_impl)
            elif isinstance(spec, PatternSpec):
                series_kind = "pattern"
                category = "candlestick"
                impl_note = f"TA-Lib v{TALIB_SOURCE_VERSION} {TALIB_FUNCTIONS[spec.name]}"
                pinned_impl = True
            else:
                raise TypeError(f"unsupported series spec type: {type(spec).__name__}")
            if not category or not impl_note:
                raise ValueError(f"series metadata must not be empty: {spec.identifier}")
            self.evidence.record(
                EvidenceRecord(
                    "INDICATOR_DEFINITION",
                    {
                        "indicator_key": series_key(spec),
                        "indicator_name": spec.name,
                        "params_json": dict(spec.params),
                        "impl_version": spec.version,
                        "pinned_impl": pinned_impl,
                        "series_kind": series_kind,
                        "category": category,
                        "impl_note": impl_note,
                        "min_history": spec.min_history,
                        "computation_mode": BACKTEST_INDICATOR_EXECUTION_MODE,
                        "enabled_reason": self._config().indicator_mode,
                    },
                )
            )

    def _update_indicators(self, candle: Candle) -> None:
        values: dict[str, object] = {}
        for spec in self._indicator_specs:
            state = self._indicator_states[spec.identifier]
            value = state.update(candle)
            self._assert_finite_indicator(value, spec.identifier, spec.undefined_outputs)
            key = series_key(spec)
            values[key] = value
            recordable = self._recordable_indicator_value(value)
            self._sequence["indicator_snapshot"] += 1
            self.evidence.record(
                EvidenceRecord(
                    "INDICATOR_SNAPSHOT",
                    {
                        "snapshot_seq": self._sequence["indicator_snapshot"],
                        "indicator_key": key,
                        "feature_ts": candle.close_time,
                        "candle_open_time": candle.open_time,
                        "candle_close_time": candle.close_time,
                        "value": value if isinstance(value, float | int) else None,
                        "value_json": recordable if isinstance(recordable, Mapping) else None,
                        "is_warmup": False,
                    },
                )
            )
        self._indicator_values = values

    @staticmethod
    def _assert_finite_indicator(
        value: object,
        identifier: str,
        undefined_outputs: tuple[str, ...] = (),
    ) -> None:
        """Reject a non-finite indicator value the standard does not leave undefined.

        Most outputs must be finite once warm-up is over; a NaN there means a
        calculation went wrong and the run should stop rather than trade on it.
        A few outputs are undefined by the standard itself for degenerate windows
        (Bollinger %B when the band collapses, §3.10), and the registry names
        those. Forcing a number into them would put an invented value where the
        standard refuses to define one, so they are allowed through as NaN.
        """

        named = value.items() if isinstance(value, Mapping) else ((None, value),)
        for key, item in named:
            if isinstance(item, bool) or not isinstance(item, float | int):
                raise ValueError(f"indicator {identifier} emitted a non-numeric value")
            if math.isfinite(float(item)):
                continue
            if key is not None and key in undefined_outputs:
                continue
            raise ValueError(f"indicator {identifier} emitted a non-finite value")

    @staticmethod
    def _recordable_indicator_value(value: object) -> object:
        """Replace an undefined output with JSON null for the Evidence record.

        Canonical JSON has no representation for NaN, and null is what "no value
        here" means in JSON. The in-memory value handed to the strategy keeps its
        NaN so the strategy can see the same thing the indicator produced.
        """

        if not isinstance(value, Mapping):
            return value
        return {
            key: None
            if isinstance(item, float | int)
            and not isinstance(item, bool)
            and not math.isfinite(float(item))
            else item
            for key, item in value.items()
        }

    def _track_excursions(self, candle: Candle, position: Position) -> None:
        active = self._active_trade
        if active is None or candle.open_time <= active.entry_fill.timestamp:
            return
        entry = active.entry_fill.reference_price
        high = to_decimal(candle.high, quantizer=quantize_price)
        low = to_decimal(candle.low, quantizer=quantize_price)
        quantity = position.quantity
        if position.side is PositionSide.LONG:
            adverse = quantize_amount((low - entry) * quantity)
            favorable = quantize_amount((high - entry) * quantity)
        else:
            adverse = quantize_amount((entry - high) * quantity)
            favorable = quantize_amount((entry - low) * quantity)
        features = dict(self._indicator_values)
        if active.mae_pnl is None or adverse < active.mae_pnl:
            active.mae_pnl = adverse
            active.mae_ts = candle.close_time
            active.mae_features = features
            active.mae_r = (
                None if active.r0 in {None, ZERO} else quantize_amount(adverse / active.r0)
            )
        if active.mfe_pnl is None or favorable > active.mfe_pnl:
            active.mfe_pnl = favorable
            active.mfe_ts = candle.close_time
            active.mfe_features = features
            active.mfe_r = (
                None if active.r0 in {None, ZERO} else quantize_amount(favorable / active.r0)
            )

    def _record_local_run(self, profile_json: Mapping[str, object]) -> None:
        match = _RUN_ID.fullmatch(self._require_run_id())
        if match is None:
            raise ValueError("catalog returned a noncanonical run_id")
        config = self._config()
        prereg_json = {
            key: value
            for key, value in self.prereg.items()
            if key not in {"observed_value", "edge_distinguishable", "decision_route"}
        }
        self.evidence.record(
            EvidenceRecord(
                "BACKTEST_RUN_LOCAL",
                {
                    "run_seq": int(match.group("seq")),
                    "run_name": config.run_name,
                    "strategy_id": config.strategy_id,
                    "strategy_name": self._run_meta["strategy_name"],
                    "strategy_version": self._run_meta["strategy_version"],
                    "params_json": self._run_meta["params_json"],
                    "submitted_money_management_json": (
                        config.money_management.model_dump(exclude_unset=True)
                    ),
                    "money_management_json": self._money_management_evidence(),
                    "resolved_indicators_json": self._run_meta["resolved_indicators_json"],
                    "params_schema_version": self._run_meta["params_schema_version"],
                    "symbol": config.symbol,
                    "exchange": config.exchange,
                    "timeframe": config.timeframe,
                    "market_type": config.market_type,
                    "period_start": config.start,
                    "period_end": config.end,
                    "warmup_start": self._run_meta["warmup_start"],
                    "warmup_candles": self._run_meta["warmup_candles"],
                    "indicator_mode": config.indicator_mode,
                    "trigger_feed": config.trigger_feed,
                    "fill_timing": config.fill_timing,
                    "initial_capital": self._cash,
                    "sizing_method": config.sizing_method,
                    "risk_per_trade": config.risk_per_trade,
                    "position_size_pct": config.position_size_pct,
                    "framework_compliant": config.sizing_method == "risk_based",
                    "cost_values_json": dict(config.cost_values),
                    "data_quality_criteria_json": {
                        "min_coverage_ratio": MIN_DATA_COVERAGE_RATIO,
                        "max_consecutive_gap_seconds": MAX_CONSECUTIVE_GAP_SECONDS,
                    },
                    "seed": config.seed,
                    "engine_version": self.engine_version,
                    "core_lib_version": self.core_lib_version,
                    "config_hash": self._run_meta["config_hash"],
                    "profile_ref": config.profile_ref,
                    "strategy_profile_json": profile_json,
                    "envelope_status_declared": self._run_meta["envelope_status_declared"],
                    "prereg_json": prereg_json,
                    "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
                },
            )
        )

    def _record_source_snapshots(self) -> None:
        range_start = self._preload[0].open_time
        minute_candles = [
            candle
            for candle in self._minute_history
            if range_start <= candle.open_time and candle.close_time <= self._config().end
        ]
        if not minute_candles:
            raise ValueError("run has no 1m origin snapshot")
        origin_status, origin_count, origin_hash = self._validate_minute_origin(
            minute_candles, range_start
        )
        minute_contract = self._record_ohlcv_snapshot(
            minute_candles,
            timeframe="1m",
            range_start=range_start,
            origin_status=origin_status,
            origin_count=origin_count,
            origin_hash=origin_hash,
        )
        if self._config().timeframe == "1m":
            self._strategy_gap_contract = minute_contract
        else:
            strategy_candles = [
                candle
                for candle in self._history
                if range_start <= candle.open_time and candle.close_time <= self._config().end
            ]
            self._strategy_gap_contract = self._record_ohlcv_snapshot(
                strategy_candles,
                timeframe=self._config().timeframe,
                range_start=range_start,
                minute_gap_close_times=minute_contract.normal_gap_close_times,
                origin_status=origin_status,
                origin_count=origin_count,
                origin_hash=origin_hash,
            )
        self._set_gap_stats()
        self._record_funding_snapshot()

    def _record_funding_snapshot(self) -> None:
        """Record measured/fallback funding facts after OHLCV provenance."""
        if self._market_type() is MarketType.FUTURES:
            content = [
                {
                    "settled_at": epoch_milliseconds(boundary),
                    "funding_rate": rate,
                    "rate_source": source,
                }
                for boundary, (rate, source) in sorted(self._funding_rates.items())
            ]
            fallback_count = sum(source == "fallback" for _, source in self._funding_rates.values())
            if self._funding_diagnostics["missing_count"] != fallback_count:
                raise RuntimeError("funding fallback count diverged from feed diagnostics")
            note = (
                f"measured_exact={self._funding_diagnostics['exact_count']}; "
                "measured_jitter_normalized="
                f"{self._funding_diagnostics['normalized_count']}; "
                f"measured_missing={self._funding_diagnostics['missing_count']}; "
                f"mark_exact={self._funding_diagnostics['mark_exact_count']}; "
                "mark_jitter_normalized="
                f"{self._funding_diagnostics['mark_normalized_count']}; "
                f"mark_missing={self._funding_diagnostics['mark_missing_count']}; "
                "unobservable_boundaries="
                f"{self._gap_stats['unobservable_funding_boundary_count']}"
            )
            self._sequence["source_snapshot"] += 1
            self.evidence.record(
                EvidenceRecord(
                    "SOURCE_DATA_SNAPSHOT",
                    {
                        "snapshot_id": self._sequence["source_snapshot"],
                        "source_kind": "funding",
                        "source_ref": "crypto_data.funding_rates",
                        "symbol": self._config().symbol,
                        "exchange": self._config().exchange,
                        "timeframe": None,
                        "range_start": self._config().start,
                        "range_end": self._config().end,
                        "row_count": len(content),
                        "fallback_used": fallback_count > 0,
                        "fallback_count": fallback_count,
                        "note": note,
                        "content_hash": hashlib.sha256(
                            canonical_json(content).encode()
                        ).hexdigest(),
                    },
                )
            )

    def _record_ohlcv_snapshot(
        self,
        candles: list[Candle],
        *,
        timeframe: str,
        range_start: datetime,
        minute_gap_close_times: tuple[int, ...] | None = None,
        origin_status: str,
        origin_count: int,
        origin_hash: str,
    ) -> OhlcvGapContract:
        if not candles:
            raise ValueError("OHLCV snapshot cannot be empty")
        content = [
            {
                "open_time": epoch_milliseconds(candle.open_time),
                "close_time": epoch_milliseconds(candle.close_time),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in candles
        ]
        content_hash = hashlib.sha256(canonical_json(content).encode()).hexdigest()
        range_end = self._config().end
        gap_contract = build_ohlcv_gap_contract(
            candles,
            timeframe=timeframe,
            range_start=range_start,
            range_end=range_end,
            evaluation_start=self._config().start,
            evaluation_end=self._config().end,
            minute_gap_close_times=minute_gap_close_times,
            origin_validation_status=origin_status,
            origin_minute_row_count=origin_count,
            origin_timestamp_hash=origin_hash,
        )
        self._sequence["source_snapshot"] += 1
        self.evidence.record(
            EvidenceRecord(
                "SOURCE_DATA_SNAPSHOT",
                {
                    "snapshot_id": self._sequence["source_snapshot"],
                    "source_kind": "ohlcv",
                    "source_ref": self._config().data_source,
                    "symbol": self._config().symbol,
                    "exchange": self._config().exchange,
                    "timeframe": timeframe,
                    "resampled_from": "1m" if timeframe != "1m" else None,
                    "range_start": range_start,
                    "range_end": range_end,
                    "row_count": len(candles),
                    "gap_count": gap_contract.snapshot_gap_count,
                    "content_hash": content_hash,
                    "note": gap_contract.encode(),
                },
            )
        )
        return gap_contract

    def _validate_minute_origin(
        self,
        minute_candles: list[Candle],
        range_start: datetime,
    ) -> tuple[str, int, str]:
        """Validate 1m timestamps and values against a separate origin query."""
        origin_feed = self.feed if isinstance(self.feed, _SourceOrigin) else None
        if origin_feed is None:
            raise TypeError("OHLCV feed requires independent origin validation")
        observed = origin_feed.source_candles(
            self._config().symbol,
            range_start,
            self._config().end,
        )
        expected = tuple(minute_candles)
        if observed != expected:
            raise ValueError("1m OHLCV Evidence diverges from independent origin query")
        timestamp_hash = hashlib.sha256(
            canonical_json([epoch_milliseconds(candle.open_time) for candle in observed]).encode()
        ).hexdigest()
        return "verified", len(observed), timestamp_hash

    def _set_gap_stats(self) -> None:
        contract = self._strategy_gap_contract
        if contract is None:
            raise RuntimeError("strategy gap contract was not recorded")
        expected = int(
            (self._config().end - self._config().start).total_seconds()
            * 1_000
            / contract.timeframe_ms
        )
        missing = contract.evaluation_grid_gap_count
        longest = 0
        current = 0
        previous: int | None = None
        for close_time in contract.evaluation_grid_gap_close_times:
            if previous is not None and close_time == previous + contract.timeframe_ms:
                current += 1
            else:
                current = 1
            longest = max(longest, current)
            previous = close_time
        coverage = (expected - missing) / expected
        max_gap_seconds = longest * contract.timeframe_ms // 1_000
        passed = (
            coverage >= MIN_DATA_COVERAGE_RATIO and max_gap_seconds <= MAX_CONSECUTIVE_GAP_SECONDS
        )
        evaluation_gaps = set(contract.evaluation_grid_gap_close_times)
        self._gap_stats = {
            "expected_candle_count": expected,
            "observed_candle_count": expected - missing,
            "source_absent_gap_count": sum(
                self._config().start.timestamp() * 1_000
                < value
                <= self._config().end.timestamp() * 1_000
                for value in contract.normal_gap_close_times
            ),
            "partial_bucket_count": sum(
                self._config().start.timestamp() * 1_000
                < value
                <= self._config().end.timestamp() * 1_000
                for value in contract.partial_bucket_close_times
            ),
            "data_coverage_ratio": coverage,
            "max_consecutive_gap_bars": longest,
            "max_consecutive_gap_seconds": max_gap_seconds,
            "data_coverage_passed": passed,
            "unobservable_funding_boundary_count": sum(
                epoch_milliseconds(boundary) in evaluation_gaps
                and epoch_milliseconds(boundary) + contract.timeframe_ms in evaluation_gaps
                for boundary in funding_boundaries_between(
                    self._config().start,
                    self._config().end,
                )
            ),
        }

    def _catalog_prereg(self) -> dict[str, object]:
        config = self._config()
        return {
            "run_id": self._require_run_id(),
            "hypothesis": str(self.prereg.get("hypothesis", "unspecified hypothesis")),
            "weakness_addressed": self.prereg.get("weakness_addressed"),
            "primary_metric": str(self.prereg.get("primary_metric", "pf")),
            "success_criteria_json": {
                "threshold": self.prereg.get("success_threshold", 0.0),
                "higher_is_better": self.prereg.get("higher_is_better", True),
            },
            "failure_criteria_json": {
                "threshold": self.prereg.get("failure_threshold", 0.0),
            },
            "profile_update_declared": bool(self.prereg.get("profile_update_declared", False)),
            "related_finding_ref": self.prereg.get("related_finding_ref"),
            "declared_by": str(self.prereg.get("declared_by", "backtest-harness")),
            "declared_at": self.prereg.get("declared_at", config.start),
        }

    def _record_action_decision(
        self,
        decision_id: int,
        signal_id: int,
        candle: Candle,
        action: str,
        side: PositionSide,
        quantity: float,
        planned: object,
        *,
        signal: TradingSignal | None = None,
        stop_distance: float | None = None,
    ) -> None:
        self.evidence.record(
            EvidenceRecord(
                "DECISION",
                {
                    "decision_id": decision_id,
                    "signal_id": signal_id,
                    "decision_ts": candle.close_time,
                    "action": action,
                    "intended_side": side.name,
                    "intended_qty": quantity,
                    "stop_price": None if signal is None else signal.stop_loss,
                    "take_profit_price": None if signal is None else signal.take_profit,
                    "risk_amount": (None if stop_distance is None else stop_distance * quantity),
                    "stop_distance": stop_distance,
                    "sizing_method": self._config().sizing_method,
                    "framework_compliant": self._config().sizing_method == "risk_based",
                    "planned_execution_ts": planned,
                },
            )
        )

    def _record_skip_decision(
        self,
        decision_id: int,
        signal_id: int,
        candle: Candle,
        reason: str,
    ) -> None:
        self.evidence.record(
            EvidenceRecord(
                "DECISION",
                {
                    "decision_id": decision_id,
                    "signal_id": signal_id,
                    "decision_ts": candle.close_time,
                    "action": "skip",
                    "skip_reason": reason,
                    "framework_compliant": self._config().sizing_method == "risk_based",
                },
            )
        )

    def _record_blocked_candidate(
        self,
        candle: Candle,
        side: PositionSide,
        reason: str,
    ) -> None:
        self.evidence.record(
            EvidenceRecord(
                "CANDIDATE_EVENT",
                {
                    "candidate_id": self._next("candidate"),
                    "ts": candle.close_time,
                    "symbol": candle.symbol,
                    "trigger_rule": reason,
                    "passed_filters_json": [],
                    "blocked_by": reason,
                    "would_be_side": side.name,
                    "realized": False,
                },
            )
        )

    def _summary(
        self,
        metrics: MetricSet,
        gate: GateResult,
        decision: DecisionResult,
        evidence_hash: str,
        integrity_status: str,
        failed_checks: list[str],
        final_equity: Decimal,
    ) -> dict[str, object]:
        wins = sum(trade.net_pnl > ZERO for trade in self._trades)
        losses = sum(trade.net_pnl < ZERO for trade in self._trades)
        gross = sum((trade.gross_pnl for trade in self._trades), ZERO)
        fees = sum((trade.total_fee for trade in self._trades), ZERO)
        slippage = sum((trade.slippage for trade in self._trades), ZERO)
        funding = sum((trade.funding_cost for trade in self._trades), ZERO)
        penalties = sum((trade.liquidation_penalty for trade in self._trades), ZERO)
        net = quantize_amount(gross - fees - slippage - funding - penalties)
        profile = self._strategy_instance().get_metadata().profile
        metric_values = {
            name: self._finite_or_none(getattr(metrics, name))
            for name in (
                "pf",
                "sortino",
                "calmar_or_mar",
                "sqn",
                "ror",
                "sharpe",
                "win_rate",
                "payoff",
                "expectancy_r",
                "ulcer",
                "kelly",
            )
        }
        return {
            "run_id": self._require_run_id(),
            "trade_count": len(self._trades),
            "win_count": wins,
            "loss_count": losses,
            "r_excluded_count": sum(trade.r0 in {None, ZERO} for trade in self._trades),
            **metric_values,
            "mdd": (None if not math.isfinite(metrics.mdd) else abs(metrics.mdd)),
            "calmar_basis": "mar",
            "annualization": "daily_resample_sqrt365",
            "initial_capital": quantize_amount(self._config().initial_capital),
            "final_equity": final_equity,
            "net_pnl_total": net,
            "gross_pnl_total": gross,
            "total_fee": fees,
            "total_slippage": slippage,
            "total_funding": funding,
            "total_liquidation_penalty": penalties,
            **self._gap_stats,
            "data_gap_exit_count": self._data_gap_exit_count,
            "integrity_passed": integrity_status == "passed",
            "integrity_status": integrity_status,
            "integrity_failed_json": failed_checks,
            "gate_passed": gate.passed,
            "gate_stage": gate.stage,
            "gate_verdict": gate.verdict,
            "gate_failed_json": gate.failed,
            "envelope_result": "in_range" if gate.verdict == "pass" else "warning",
            "envelope_deviated_json": [],
            "decision_route": decision.route,
            "decision_rationale": decision.rationale,
            "evidence_hash": evidence_hash,
            "profile_status": profile.envelope_status,
        }

    def _observed_metric(self, metrics: MetricSet) -> float:
        name = str(self.prereg.get("primary_metric", "pf"))
        aliases = {"profit_factor": "pf", "calmar": "calmar_or_mar", "mar": "calmar_or_mar"}
        attribute = aliases.get(name, name)
        if not hasattr(metrics, attribute):
            raise ValueError(f"unsupported preregistered primary metric: {name}")
        value = float(getattr(metrics, attribute))
        return value if math.isfinite(value) else 0.0

    @staticmethod
    def _finite_or_none(value: float) -> float | None:
        return value if math.isfinite(value) else None

    def _risk_budget(self, pending: _PendingOrder) -> Decimal | None:
        if pending.request.reduce_only or self._config().sizing_method != "risk_based":
            return None
        risk = self._config().risk_per_trade
        assert risk is not None
        normalized_risk = to_decimal(risk, quantizer=quantize_amount)
        return quantize_amount(self._current_equity() * normalized_risk)

    def _maintenance_margin_rate(self) -> Decimal:
        params = self.cost_model.liq_params()
        value = params.get("maintenance_margin_rate")
        if not isinstance(value, Decimal):
            raise TypeError("liq_params.maintenance_margin_rate must be Decimal")
        if not ZERO <= value < Decimal("1"):
            raise ValueError("maintenance_margin_rate must be in [0, 1)")
        return value

    @staticmethod
    def _checked_cash(value: Decimal, *, context: str) -> Decimal:
        """Normalize every cash mutation and reject a negative balance atomically."""
        if not isinstance(value, Decimal):
            raise TypeError(f"{context} cash value must be Decimal")
        normalized = quantize_amount(value)
        if normalized < ZERO:
            raise ValueError(f"{context} would make cash negative")
        return normalized

    def _current_equity(self) -> Decimal:
        return recompute(self._cash, self._current_position())

    def _current_position(self) -> Position | None:
        long_position = self._book.get(self._config().symbol, PositionSide.LONG)
        short_position = self._book.get(self._config().symbol, PositionSide.SHORT)
        if long_position is not None and short_position is not None:
            raise ValueError("Engine supports one directional position at a time")
        return long_position or short_position

    def _market_type(self) -> MarketType:
        return MarketType(self._config().market_type)

    @staticmethod
    def _leverage(signal: TradingSignal | None) -> int:
        return 1 if signal is None or signal.leverage is None else signal.leverage

    def _next_candle(self, candle: Candle) -> Candle | None:
        try:
            index = self._history.index(candle)
        except ValueError as error:
            raise ValueError("decision candle is absent from Engine history") from error
        return self._history[index + 1] if index + 1 < len(self._history) else None

    def _move_clock(self, target: datetime) -> None:
        while self.clock.now() < target:
            self.clock.advance()
        if self.clock.now() != target:
            raise ValueError("Clock schedule does not contain the required candle instant")

    def _next(self, name: str) -> int:
        self._sequence[name] += 1
        return self._sequence[name]

    def _sweep_value(self, name: str) -> str | None:
        sweep = self._config().sweep
        value = None if sweep is None else sweep.get(name)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"sweep.{name} must be a string")
        return value

    def _config(self) -> RunConfig:
        if self.config is None:
            raise RuntimeError("Engine has no active RunConfig")
        return self.config

    def _strategy_instance(self) -> StrategyAdapter:
        if self._strategy is None:
            raise RuntimeError("Engine has no active StrategyAdapter")
        return self._strategy

    def _require_run_id(self) -> str:
        if self._run_id is None:
            raise RuntimeError("CatalogStore has not issued a run_id")
        return self._run_id

    def _require_evidence_path(self) -> str:
        if self._evidence_path is None:
            raise RuntimeError("EvidenceSink has not bound a file")
        return self._evidence_path


__all__ = ["Engine", "RunResult"]
