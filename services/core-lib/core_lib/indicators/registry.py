"""Register indicator versions, implementations, and minimum history."""

import builtins
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from types import MappingProxyType
from typing import Protocol, runtime_checkable

from core_lib.types import Candle

from . import momentum, strength, systems, trend, volatility, volume
from .contracts import assert_finalized

IndicatorParam = bool | float | int | str
IndicatorValue = float | dict[str, float]
IndicatorSeries = Sequence[IndicatorValue]


@runtime_checkable
class IndicatorState(Protocol):
    """Structural contract for an incremental indicator implementation."""

    min_history: int

    @property
    def warmed_up(self) -> bool:
        """Return whether the state has enough candles for a valid value."""
        ...

    def seed(self, candles: Sequence[Candle]) -> None:
        """Reset and populate state from warm-up candles."""
        ...

    def update(self, candle: Candle) -> IndicatorValue:
        """Advance by one finalized candle."""
        ...

    def current(self) -> IndicatorValue:
        """Return the latest value or NaN-shaped warm-up value."""
        ...


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    """Immutable calculation identity and its two execution entry points."""

    name: str
    params: Mapping[str, IndicatorParam]
    version: str
    pinned_impl: str
    min_history: int
    category: str
    required_inputs: tuple[str, ...]
    _vectorized: Callable[[Sequence[Candle]], IndicatorSeries] = field(
        repr=False,
        compare=False,
    )
    _state_factory: Callable[[], IndicatorState] = field(repr=False, compare=False)
    undefined_outputs: tuple[str, ...] = ()
    """Output keys the standard itself leaves undefined for degenerate windows.

    Bollinger %B is the first case: §3.10 writes "분모 0 → 미정의" because a
    collapsed band has no relative position to report. An indicator must not
    invent a number where the standard declines to define one, so those keys may
    carry NaN after warm-up and every other key may not. Consumers read this list
    rather than guessing which NaN is legitimate.
    """

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("indicator name must not be empty")
        if self.min_history <= 0:
            raise ValueError("min_history must be positive")
        object.__setattr__(self, "params", MappingProxyType(dict(self.params)))
        object.__setattr__(self, "required_inputs", tuple(self.required_inputs))
        object.__setattr__(self, "undefined_outputs", tuple(self.undefined_outputs))
        if any(not isinstance(name, str) or not name for name in self.undefined_outputs):
            raise ValueError("undefined_outputs must name output keys")

    @property
    def identifier(self) -> str:
        """Return a stable name-plus-parameters registry identifier."""
        if not self.params:
            return self.name
        rendered = ",".join(f"{key}={value!r}" for key, value in sorted(self.params.items()))
        return f"{self.name}({rendered})"

    def compute_vectorized(self, candles: Sequence[Candle]) -> IndicatorSeries:
        """Compute the complete batch series."""
        return self._vectorized(candles)

    def make_state(self) -> IndicatorState:
        """Create a fresh incremental state with no shared execution data."""
        return self._state_factory()


RegistryKey = tuple[str, tuple[tuple[str, IndicatorParam], ...]]


class IndicatorRegistry:
    """Own registered indicator specs and batch calculation selection."""

    def __init__(self) -> None:
        self._specs: dict[RegistryKey, IndicatorSpec] = {}

    @staticmethod
    def _key(name: str, params: Mapping[str, IndicatorParam]) -> RegistryKey:
        return name, tuple(sorted(params.items()))

    def get(self, name: str, params: Mapping[str, IndicatorParam]) -> IndicatorSpec:
        """Return the exact registered name-and-parameters spec."""
        try:
            return self._specs[self._key(name, params)]
        except KeyError as error:
            raise KeyError(f"indicator is not registered: {name} {dict(params)}") from error

    def register(self, spec: IndicatorSpec) -> None:
        """Register one immutable spec, rejecting an identity collision."""
        key = self._key(spec.name, spec.params)
        if key in self._specs:
            raise ValueError(f"indicator already registered: {spec.identifier}")
        self._specs[key] = spec

    def list(self) -> list[IndicatorSpec]:
        """Return all specs in deterministic identifier order."""
        return sorted(self._specs.values(), key=lambda spec: spec.identifier)

    def _matching_specs(self, requested: str) -> builtins.list[IndicatorSpec]:
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name == requested or spec.identifier == requested
        ]
        if not matches:
            raise KeyError(f"indicator is not registered: {requested}")
        return matches

    def _descriptor_spec(self, descriptor: Mapping[str, object]) -> IndicatorSpec:
        """Resolve one external name-and-parameters descriptor to its registry spec."""
        if set(descriptor) != {"name", "params"}:
            raise ValueError("indicator descriptor must contain exactly name and params")
        name = descriptor["name"]
        params = descriptor["params"]
        if not isinstance(name, str) or not isinstance(params, Mapping):
            raise TypeError("indicator descriptor name/params have invalid types")
        normalized_params = dict(params)
        if any(
            not isinstance(key, str) or not isinstance(value, bool | float | int | str)
            for key, value in normalized_params.items()
        ):
            raise TypeError("indicator params must use scalar registry values")
        matches = [
            spec
            for spec in self._specs.values()
            if spec.name.casefold() == name.casefold() and dict(spec.params) == normalized_params
        ]
        if len(matches) != 1:
            raise KeyError(f"indicator is not registered: {name} {normalized_params}")
        return matches[0]

    def specs_for(
        self,
        enabled_set: Collection[str],
    ) -> builtins.list[IndicatorSpec]:
        """Return the deterministic, de-duplicated specs named by an enabled set."""
        selected: dict[str, IndicatorSpec] = {}
        for requested in enabled_set:
            for spec in self._matching_specs(requested):
                selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

    def specs_from_descriptors(
        self,
        descriptors: Collection[Mapping[str, object]],
    ) -> builtins.list[IndicatorSpec]:
        """Resolve descriptors to deterministic, de-duplicated registry specs."""
        selected: dict[str, IndicatorSpec] = {}
        for descriptor in descriptors:
            spec = self._descriptor_spec(descriptor)
            selected[spec.identifier] = spec
        return [selected[identifier] for identifier in sorted(selected)]

    def compute_batch(
        self,
        candles: Sequence[Candle],
        enabled_set: set[str],
        *,
        decision_time: datetime | None = None,
        available_inputs: Collection[str] = (),
    ) -> dict[str, IndicatorSeries]:
        """Compute a batch/research series after finalized/history/input validation.

        The backtest engine deliberately uses incremental state updates so its
        look-ahead boundary stays structural. This batch path remains the
        independent parity oracle for those state implementations.
        """
        effective_decision_time = decision_time
        if effective_decision_time is None and candles:
            effective_decision_time = candles[-1].close_time
        if effective_decision_time is not None:
            for candle in candles:
                assert_finalized(candle, effective_decision_time)

        available = set(available_inputs)
        result: dict[str, IndicatorSeries] = {}
        for spec in self.specs_for(enabled_set):
            if not set(spec.required_inputs).issubset(available):
                continue
            if len(candles) < spec.min_history:
                raise ValueError(
                    f"{spec.identifier} requires {spec.min_history} candles, got {len(candles)}"
                )
            result[spec.identifier] = spec.compute_vectorized(candles)
        return result

    def resolve_enabled(
        self,
        mode: str,
        declared: Collection[str],
        explicit: Collection[str],
    ) -> set[str]:
        """Resolve auto, explicit, or all calculation selection."""
        if mode == "auto":
            resolved = set(declared)
        elif mode == "explicit":
            resolved = set(explicit)
        elif mode == "all":
            resolved = {spec.identifier for spec in self._specs.values()}
        else:
            raise ValueError("indicator mode must be auto, explicit, or all")
        for requested in resolved:
            self._matching_specs(requested)
        return resolved

    def resolve_specs(
        self,
        mode: str,
        declared: Collection[Mapping[str, object]],
        explicit: Collection[Mapping[str, object]],
    ) -> builtins.list[IndicatorSpec]:
        """Resolve external descriptors and calculation mode through one registry path."""
        declared_ids = {spec.identifier for spec in self.specs_from_descriptors(declared)}
        explicit_ids = {spec.identifier for spec in self.specs_from_descriptors(explicit)}
        enabled = self.resolve_enabled(mode, declared_ids, explicit_ids)
        specs = self.specs_for(enabled)
        if not specs:
            raise ValueError("an indicator selection must resolve at least one spec")
        return specs


RSI_MIN_HISTORY = 15


def build_default_registry() -> IndicatorRegistry:
    """Build the first-strategy coverage registry pinned to the authority spec."""
    registry = IndicatorRegistry()
    for period in (9, 21, 55, 200):
        registry.register(
            IndicatorSpec(
                name="EMA",
                params={"period": period},
                version="1.0.0",
                pinned_impl="technical_indicators_calc_spec.md §0.3 (SMA seed, recursive)",
                min_history=period,
                category="trend",
                required_inputs=(),
                _vectorized=partial(trend.ema, period=period),
                _state_factory=partial(trend.EMAState, period=period),
            )
        )
    registry.register(
        IndicatorSpec(
            name="RSI",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.1 + §0.5 (Wilder RMA)",
            min_history=15,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.rsi, period=14),
            _state_factory=partial(momentum.RSIState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Stochastic",
            params={"period": 14, "smooth_period": 3},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.2 "
                "(fast %K/%D; flat range keeps previous, initially 50)"
            ),
            min_history=16,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.stochastic, period=14, smooth_period=3),
            _state_factory=partial(momentum.StochasticState, period=14, smooth_period=3),
        )
    )
    registry.register(
        IndicatorSpec(
            name="ATR",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §3.1 + §0.6 + §0.5",
            min_history=14,
            category="volatility",
            required_inputs=(),
            _vectorized=partial(volatility.atr, period=14),
            _state_factory=partial(volatility.ATRState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Bollinger Bands",
            params={"period": 20, "multiplier": 2.0},
            version="1.0.1",
            pinned_impl=(
                "technical_indicators_calc_spec.md §3.10 + §0.7 "
                "(population stdev, rolling Welford moments)"
            ),
            min_history=20,
            category="volatility",
            required_inputs=(),
            _vectorized=partial(
                volatility.bollinger_bands,
                period=20,
                multiplier=2.0,
            ),
            _state_factory=partial(
                volatility.BollingerBandsState,
                period=20,
                multiplier=2.0,
            ),
            # §3.10: "%B ... 분모 0 → 미정의". A flat window collapses the band,
            # and the standard declines to name a substitute, so %B stays NaN
            # there instead of being given an invented number.
            undefined_outputs=("percent_b",),
        )
    )
    registry.register(
        IndicatorSpec(
            name="DEMA",
            params={"period": 21},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §1.1 (2*EMA1 - EMA2)",
            min_history=41,
            category="trend",
            required_inputs=(),
            _vectorized=partial(trend.dema, period=21),
            _state_factory=partial(trend.DEMAState, period=21),
        )
    )
    registry.register(
        IndicatorSpec(
            name="MACD",
            params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.4 (12/26/9, EMA of MACD)",
            min_history=34,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.macd,
                fast_period=12,
                slow_period=26,
                signal_period=9,
            ),
            _state_factory=partial(
                momentum.MACDState,
                fast_period=12,
                slow_period=26,
                signal_period=9,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="TSI",
            params={"long_period": 25, "short_period": 13},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.7 (double-smoothed momentum)",
            min_history=38,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.tsi, long_period=25, short_period=13),
            _state_factory=partial(momentum.TSIState, long_period=25, short_period=13),
        )
    )
    registry.register(
        IndicatorSpec(
            name="CCI",
            params={"period": 20},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.10 (0.015 * mean deviation)",
            min_history=20,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.cci, period=20),
            _state_factory=partial(momentum.CCIState, period=20),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Awesome Oscillator",
            params={"fast_period": 5, "slow_period": 34},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.12 (SMA of HL2, 5 and 34)",
            min_history=34,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.awesome_oscillator, fast_period=5, slow_period=34),
            _state_factory=partial(
                momentum.AwesomeOscillatorState,
                fast_period=5,
                slow_period=34,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="A/D Line",
            params={},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §4.2 (H=L keeps the multiplier at 0)",
            min_history=1,
            category="volume",
            required_inputs=(),
            _vectorized=volume.ad_line,
            _state_factory=volume.ADLineState,
        )
    )
    registry.register(
        IndicatorSpec(
            name="TEMA",
            params={"period": 21},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §1.2 (3*E1 - 3*E2 + E3)",
            min_history=61,
            category="trend",
            required_inputs=(),
            _vectorized=partial(trend.tema, period=21),
            _state_factory=partial(trend.TEMAState, period=21),
        )
    )
    registry.register(
        IndicatorSpec(
            name="PPO",
            params={"fast_period": 12, "slow_period": 26, "signal_period": 9},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.5 (MACD scaled by the slow EMA)",
            min_history=34,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.ppo,
                fast_period=12,
                slow_period=26,
                signal_period=9,
            ),
            _state_factory=partial(
                momentum.PPOState,
                fast_period=12,
                slow_period=26,
                signal_period=9,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="SMI",
            params={
                "period": 13,
                "long_period": 25,
                "short_period": 13,
                "signal_period": 3,
            },
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.27 "
                "(Blau 13/25/13 with a 3-period signal; the section asks the set to be stated)"
            ),
            min_history=51,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.smi,
                period=13,
                long_period=25,
                short_period=13,
                signal_period=3,
            ),
            _state_factory=partial(
                momentum.SMIState,
                period=13,
                long_period=25,
                short_period=13,
                signal_period=3,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Accelerator Oscillator",
            params={"fast_period": 5, "slow_period": 34, "smooth_period": 5},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.13 (AO - SMA(AO, 5))",
            min_history=38,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.accelerator_oscillator,
                fast_period=5,
                slow_period=34,
                smooth_period=5,
            ),
            _state_factory=partial(
                momentum.AcceleratorOscillatorState,
                fast_period=5,
                slow_period=34,
                smooth_period=5,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Chaikin Oscillator",
            params={"fast_period": 3, "slow_period": 10},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §4.3 (EMA(ADL,3) - EMA(ADL,10))",
            min_history=10,
            category="volume",
            required_inputs=(),
            _vectorized=partial(volume.chaikin_oscillator, fast_period=3, slow_period=10),
            _state_factory=partial(
                volume.ChaikinOscillatorState,
                fast_period=3,
                slow_period=10,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="CMF",
            params={"period": 20},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §4.4 (money flow volume over volume)",
            min_history=20,
            category="volume",
            required_inputs=(),
            _vectorized=partial(volume.cmf, period=20),
            _state_factory=partial(volume.CMFState, period=20),
        )
    )
    registry.register(
        IndicatorSpec(
            name="KAMA",
            params={"period": 10},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §1.7 (efficiency ratio, 2/30 constants)"
            ),
            min_history=11,
            category="trend",
            required_inputs=(),
            _vectorized=partial(trend.kama, period=10),
            _state_factory=partial(trend.KAMAState, period=10),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Stochastic RSI",
            params={
                "rsi_period": 14,
                "stochastic_period": 14,
                "smooth_k": 3,
                "smooth_d": 3,
            },
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.3 (stochastic of RSI, 3/3 smoothing)"
            ),
            min_history=RSI_MIN_HISTORY + 14 + 3 + 3 - 3,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.stochastic_rsi,
                rsi_period=14,
                stochastic_period=14,
                smooth_k=3,
                smooth_d=3,
            ),
            _state_factory=partial(
                momentum.StochasticRSIState,
                rsi_period=14,
                stochastic_period=14,
                smooth_k=3,
                smooth_d=3,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="TRIX",
            params={"period": 15},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.6 (triple EMA, TA-Lib 100x scale)",
            min_history=44,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.trix, period=15),
            _state_factory=partial(momentum.TRIXState, period=15),
        )
    )
    registry.register(
        IndicatorSpec(
            name="CMO",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.8 (unsmoothed sums)",
            min_history=15,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.cmo, period=14),
            _state_factory=partial(momentum.CMOState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Williams %R",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.9 (stochastic read from the high)",
            min_history=14,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.williams_r, period=14),
            _state_factory=partial(momentum.WilliamsRState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Ultimate Oscillator",
            params={"short_period": 7, "medium_period": 14, "long_period": 28},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.11 (7/14/28 weighted 4:2:1)",
            min_history=29,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.ultimate_oscillator,
                short_period=7,
                medium_period=14,
                long_period=28,
            ),
            _state_factory=partial(
                momentum.UltimateOscillatorState,
                short_period=7,
                medium_period=14,
                long_period=28,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Fisher Transform",
            params={"period": 9},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.14 "
                "(n=9 of the 9-10 the section allows; clamped at 0.999)"
            ),
            min_history=10,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(momentum.fisher_transform, period=9),
            _state_factory=partial(momentum.FisherTransformState, period=9),
        )
    )
    registry.register(
        IndicatorSpec(
            name="KST",
            params={},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §2.24 (four weighted rate-of-change legs)"
            ),
            min_history=53,
            category="momentum",
            required_inputs=(),
            _vectorized=momentum.kst,
            _state_factory=momentum.KSTState,
        )
    )
    registry.register(
        IndicatorSpec(
            name="Coppock Curve",
            params={"long_period": 14, "short_period": 11, "smooth_period": 10},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §2.25 (WMA of two rates of change)",
            min_history=24,
            category="momentum",
            required_inputs=(),
            _vectorized=partial(
                momentum.coppock_curve,
                long_period=14,
                short_period=11,
                smooth_period=10,
            ),
            _state_factory=partial(
                momentum.CoppockCurveState,
                long_period=14,
                short_period=11,
                smooth_period=10,
            ),
        )
    )
    registry.register(
        IndicatorSpec(
            name="OBV",
            params={},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §4.1 (signed volume accumulation)",
            min_history=1,
            category="volume",
            required_inputs=(),
            _vectorized=volume.obv,
            _state_factory=volume.OBVState,
        )
    )
    registry.register(
        IndicatorSpec(
            name="Force Index",
            params={"period": 13},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §4.6 (EMA of price change times volume)"
            ),
            min_history=14,
            category="volume",
            required_inputs=(),
            _vectorized=partial(volume.force_index, period=13),
            _state_factory=partial(volume.ForceIndexState, period=13),
        )
    )
    registry.register(
        IndicatorSpec(
            name="DMI",
            params={"period": 14},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §5.1 (+DI, -DI, ADX, ADXR)",
            min_history=42,
            category="strength",
            required_inputs=(),
            _vectorized=partial(strength.dmi, period=14),
            _state_factory=partial(strength.DMIState, period=14),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Aroon",
            params={"period": 25},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §5.3 (age of the window extremes)",
            min_history=26,
            category="strength",
            required_inputs=(),
            _vectorized=partial(strength.aroon, period=25),
            _state_factory=partial(strength.AroonState, period=25),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Elder Ray",
            params={"period": 13},
            version="1.0.0",
            pinned_impl=(
                "technical_indicators_calc_spec.md §9.3 (extremes against a smoothed close)"
            ),
            min_history=13,
            category="systems",
            required_inputs=(),
            _vectorized=partial(systems.elder_ray, period=13),
            _state_factory=partial(systems.ElderRayState, period=13),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Parabolic SAR",
            params={"step": 0.02, "maximum": 0.2},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §9.1 (0.02 step to a 0.20 cap)",
            min_history=2,
            category="systems",
            required_inputs=(),
            _vectorized=partial(systems.parabolic_sar, step=0.02, maximum=0.2),
            _state_factory=partial(systems.ParabolicSARState, step=0.02, maximum=0.2),
        )
    )
    registry.register(
        IndicatorSpec(
            name="Volume SMA",
            params={"period": 20},
            version="1.0.0",
            pinned_impl="technical_indicators_calc_spec.md §0.2 (volume input)",
            min_history=20,
            category="volume",
            required_inputs=(),
            _vectorized=partial(volume.volume_sma, period=20),
            _state_factory=partial(volume.VolumeSMAState, period=20),
        )
    )
    return registry


DEFAULT_REGISTRY = build_default_registry()
