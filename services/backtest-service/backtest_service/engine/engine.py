"""Orchestrate deterministic candle ordering, fills, Evidence, and evaluation."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Protocol, runtime_checkable

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
from core_lib.execution import (
    PositionBook,
    liquidation_fill,
    position_value,
    recompute,
    resolve_triggers,
    to_decimal,
)
from core_lib.indicators import DEFAULT_REGISTRY, IndicatorSpec, IndicatorState
from core_lib.ports import Broker, CatalogStore, Clock, CostModel, DataFeed, EvidenceSink
from core_lib.sizing import exposure_limit, wallet_pct_size
from core_lib.sizing import size as risk_size
from core_lib.strategy import AdapterManager, StrategyAdapter, StrategyConfig
from core_lib.types import (
    ZERO,
    Candle,
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
from backtest_service.config import RunConfig

_RUN_ID = re.compile(r"^BT_[0-9]{8}_(?P<seq>[0-9]+)_(?P<name>[a-z0-9-]+)$")


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
        comparison_run_id: str | None,
        comparison_hash: str | None,
    ) -> None:
        """Bind a catalog-backed cross-run comparison."""


@runtime_checkable
class _DeterminismCatalog(Protocol):
    def determinism_reference(
        self,
        run_id: str,
        config_hash: str,
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


@dataclass(frozen=True, slots=True)
class RunResult:
    """The immutable result returned by one Engine run."""

    run_id: str
    evidence_path: str
    evidence_hash: str
    integrity_status: str
    metrics: MetricSet
    decision: DecisionResult


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
        engine_version: str = "1.1.0",
        core_lib_version: str = "0.2.0",
        thresholds: Mapping[str, float] | None = None,
    ) -> None:
        if not isinstance(broker, _ExecutionBroker):
            raise TypeError("Engine requires a Broker with configure_execution")
        if not isinstance(evidence, _BoundEvidence):
            raise TypeError("Engine requires an EvidenceSink with bind/audit lifecycle")
        if not isinstance(catalog, _DeterminismCatalog):
            raise TypeError(
                "Engine requires a CatalogStore with determinism_reference"
            )
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
        self._history: list[Candle] = []
        self._preload: list[Candle] = []
        self._evaluation: list[Candle] = []
        self._confirmed: list[Candle] = []
        self._minute_history: list[Candle] = []
        self._indicator_specs: list[IndicatorSpec] = []
        self._indicator_states: dict[str, IndicatorState] = {}
        self._indicator_values: dict[str, object] = {}
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
        self._strategy = self.manager.create(
            config.strategy_id,
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
        )
        self.manager.activate(config.strategy_id)
        metadata = self._strategy.get_metadata()
        if config.timeframe not in metadata.supported_timeframes:
            raise ValueError("strategy does not support the configured timeframe")
        resolved = StrategyConfig.resolve(
            self._strategy.get_parameter_schema(),
            {"strategy_id": config.strategy_id, "params": dict(config.params)},
        )
        self._indicator_specs = self._resolve_indicator_specs(
            metadata.required_indicators,
            config,
        )
        longest_indicator_history = max(
            spec.min_history for spec in self._indicator_specs
        )
        required_warmup = max(metadata.min_history, longest_indicator_history)

        self._history = sorted(
            self.feed.candles(config.symbol, config.timeframe, config.end),
            key=lambda candle: candle.open_time,
        )
        if any(
            right.open_time <= left.open_time
            for left, right in zip(self._history, self._history[1:], strict=False)
        ):
            raise ValueError("DataFeed candles must have strictly increasing open_time")
        available_preload = [
            candle for candle in self._history if candle.close_time <= config.start
        ]
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
        self._prepare_funding_sources()

        profile = metadata.profile
        params_json = dict(resolved.params)
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
            ],
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
                self._move_clock(self._evaluation[index + 1].open_time)
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
        entry_time = (
            None if self._active_trade is None else self._active_trade.entry_fill.timestamp
        )
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
                close_time=last.close_time + timedelta(milliseconds=1)
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
        metrics = compute(self._trades, self._equity_curve)
        preliminary_integrity = check_integrity(self.evidence.audit())
        if preliminary_integrity.passed:
            gate = judge(metrics, self.thresholds, self._strategy_instance().get_metadata().profile)
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
        reference = self.catalog.determinism_reference(
            self._require_run_id(),
            str(self._run_meta["config_hash"]),
        )
        self.evidence.set_determinism_reference(
            catalog_config_matches=reference.catalog_config_matches,
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
                    "no_position" if position is None else "end_of_data",
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
            reason = "exposure_limit" if not within_limits else "end_of_data"
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
            risk = self._config().risk_per_trade
            assert risk is not None
            quantity = risk_size(risk, float(self._current_equity()), stop_distance)
        else:
            pct = self._config().position_size_pct
            assert pct is not None
            notional = wallet_pct_size(float(self._cash), pct)
            quantity = notional / signal.price
        return quantity, stop_distance

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
            projected_entry_cash = quantize_amount(
                self._cash - added_margin - fill.fee
            )
            if projected_entry_cash < ZERO:
                raise ValueError(
                    "entry margin plus fee exceeds available cash after truncation"
                )
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
        net = quantize_amount(
            gross - active.total_fee - active.slippage - active.funding - penalty
        )
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
                        "excursion_r": (
                            None if excursion_r is None else float(excursion_r)
                        ),
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
        if (
            self._market_type() is not MarketType.FUTURES
            or not is_funding_boundary(boundary)
        ):
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
                        "framework_compliant": (
                            self._config().sizing_method == "risk_based"
                        ),
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

    def _resolve_indicator_specs(
        self,
        declared: list[dict[str, object]],
        config: RunConfig,
    ) -> list[IndicatorSpec]:
        declared_specs = [self._indicator_spec(item) for item in declared]
        explicit_specs = [
            self._indicator_spec(item) for item in config.explicit_indicators
        ]
        declared_ids = {spec.identifier for spec in declared_specs}
        explicit_ids = {spec.identifier for spec in explicit_specs}
        if config.indicator_mode == "auto":
            selected = declared_specs
        elif config.indicator_mode == "explicit":
            if not declared_ids.issubset(explicit_ids):
                missing = sorted(declared_ids - explicit_ids)
                raise ValueError(
                    "explicit_indicators must include every strategy-required indicator: "
                    f"{missing}"
                )
            selected = explicit_specs
        else:
            selected = DEFAULT_REGISTRY.list()
        unique = {spec.identifier: spec for spec in selected}
        if not unique:
            raise ValueError("a backtest run must resolve at least one indicator")
        return [unique[key] for key in sorted(unique)]

    @staticmethod
    def _indicator_spec(descriptor: Mapping[str, object]) -> IndicatorSpec:
        if set(descriptor) != {"name", "params"}:
            raise ValueError("indicator descriptor must contain exactly name and params")
        name = descriptor["name"]
        params = descriptor["params"]
        if not isinstance(name, str) or not isinstance(params, Mapping):
            raise TypeError("indicator descriptor name/params have invalid types")
        normalized_params = dict(params)
        if any(
            not isinstance(key, str)
            or not isinstance(value, bool | float | int | str)
            for key, value in normalized_params.items()
        ):
            raise TypeError("indicator params must use scalar registry values")
        matches = [
            spec
            for spec in DEFAULT_REGISTRY.list()
            if spec.name.casefold() == name.casefold()
            and dict(spec.params) == normalized_params
        ]
        if len(matches) != 1:
            raise KeyError(f"indicator is not registered: {name} {normalized_params}")
        return matches[0]

    def _prepare_indicator_states(self) -> None:
        self._indicator_states = {
            spec.identifier: spec.make_state() for spec in self._indicator_specs
        }

    def _prepare_funding_sources(self) -> None:
        if self._market_type() is not MarketType.FUTURES:
            return
        diagnostics_feed = (
            self.feed if isinstance(self.feed, _FundingDiagnostics) else None
        )
        before = (
            diagnostics_feed.funding_diagnostics()
            if diagnostics_feed is not None
            else None
        )
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
                name: after[name] - before[name]
                for name in self._funding_diagnostics
            }
            if any(value < 0 for value in self._funding_diagnostics.values()):
                raise RuntimeError("funding diagnostic counters moved backwards")
        else:
            fallback_count = sum(
                source == "fallback" for _, source in self._funding_rates.values()
            )
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
            self.evidence.record(
                EvidenceRecord(
                    "INDICATOR_DEFINITION",
                    {
                        "indicator_key": self._indicator_key(spec),
                        "indicator_name": spec.name,
                        "params_json": dict(spec.params),
                        "impl_version": spec.version,
                        "pinned_impl": True,
                        "min_history": spec.min_history,
                        "computation_mode": "incremental",
                        "enabled_reason": self._config().indicator_mode,
                    },
                )
            )

    def _update_indicators(self, candle: Candle) -> None:
        values: dict[str, object] = {}
        for spec in self._indicator_specs:
            state = self._indicator_states[spec.identifier]
            value = state.update(candle)
            self._assert_finite_indicator(value, spec.identifier)
            key = self._indicator_key(spec)
            values[key] = value
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
                        "value_json": value if isinstance(value, Mapping) else None,
                        "is_warmup": False,
                    },
                )
            )
        self._indicator_values = values

    @staticmethod
    def _assert_finite_indicator(value: object, identifier: str) -> None:
        scalars = value.values() if isinstance(value, Mapping) else (value,)
        if any(
            isinstance(item, bool)
            or not isinstance(item, float | int)
            or not math.isfinite(float(item))
            for item in scalars
        ):
            raise ValueError(f"indicator {identifier} emitted a non-finite value")

    @staticmethod
    def _indicator_key(spec: IndicatorSpec) -> str:
        name = re.sub(r"[^a-z0-9]+", "_", spec.name.casefold()).strip("_")
        params = ",".join(
            f"{key}={Engine._indicator_param(value)}"
            for key, value in sorted(spec.params.items())
        )
        return name if not params else f"{name}:{params}"

    @staticmethod
    def _indicator_param(value: object) -> str:
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value)

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
                None
                if active.r0 in {None, ZERO}
                else quantize_amount(adverse / active.r0)
            )
        if active.mfe_pnl is None or favorable > active.mfe_pnl:
            active.mfe_pnl = favorable
            active.mfe_ts = candle.close_time
            active.mfe_features = features
            active.mfe_r = (
                None
                if active.r0 in {None, ZERO}
                else quantize_amount(favorable / active.r0)
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
                    "resolved_indicators_json": self._run_meta[
                        "resolved_indicators_json"
                    ],
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
        self._record_ohlcv_snapshot(
            self._history,
            timeframe=self._config().timeframe,
        )
        if (
            self._minute_history
            and self._config().timeframe != "1m"
        ):
            self._record_ohlcv_snapshot(self._minute_history, timeframe="1m")
        if self._market_type() is MarketType.FUTURES:
            content = [
                {
                    "settled_at": epoch_milliseconds(boundary),
                    "funding_rate": rate,
                    "rate_source": source,
                }
                for boundary, (rate, source) in sorted(self._funding_rates.items())
            ]
            fallback_count = sum(
                source == "fallback" for _, source in self._funding_rates.values()
            )
            if self._funding_diagnostics["missing_count"] != fallback_count:
                raise RuntimeError(
                    "funding fallback count diverged from feed diagnostics"
                )
            note = (
                f"measured_exact={self._funding_diagnostics['exact_count']}; "
                "measured_jitter_normalized="
                f"{self._funding_diagnostics['normalized_count']}; "
                f"measured_missing={self._funding_diagnostics['missing_count']}; "
                f"mark_exact={self._funding_diagnostics['mark_exact_count']}; "
                "mark_jitter_normalized="
                f"{self._funding_diagnostics['mark_normalized_count']}; "
                f"mark_missing={self._funding_diagnostics['mark_missing_count']}"
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
    ) -> None:
        if not candles:
            return
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
                    "range_start": candles[0].open_time,
                    "range_end": candles[-1].close_time,
                    "row_count": len(candles),
                    "content_hash": content_hash,
                },
            )
        )

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
            "profile_update_declared": bool(
                self.prereg.get("profile_update_declared", False)
            ),
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
                    "risk_amount": (
                        None
                        if stop_distance is None
                        else stop_distance * quantity
                    ),
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
            "mdd": (
                None if not math.isfinite(metrics.mdd) else abs(metrics.mdd)
            ),
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
