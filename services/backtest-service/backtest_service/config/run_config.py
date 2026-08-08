"""Define validated run, data, cost, risk, sweep, indicator, and profile settings."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import MISSING as DATACLASS_MISSING
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Union, cast

from core_lib.money_management import policy_settings
from core_lib.types import MarketType
from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator
from trading_plugins import registered_money_management

from backtest_service.adapters.cost_model import BacktestCostModel

_RUN_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_STRATEGY_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TIMEFRAME_PATTERN = re.compile(r"^[1-9]\d*[mhd]$")


class ManualMoneyManagementConfig(BaseModel):
    """Legacy-compatible explicit ATR protection and leverage settings."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["manual"] = "manual"
    leverage: int = Field(default=1, ge=1, le=100)
    reward_risk: float = Field(default=2.0, ge=0.1, le=10.0)
    atr_stop_multiple: float = Field(default=2.0, ge=0.1, le=10.0)


class TurtleMoneyManagementConfig(BaseModel):
    """Turtle-derived daily-N money management under the global risk cap."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["turtle"] = "turtle"
    n_period: int = Field(default=20, ge=2, le=200)
    n_timeframe: Literal["1d"] = "1d"
    stop_n_multiple: float = Field(default=2.0, ge=0.1, le=10.0)
    leverage_cap: int = Field(default=10, ge=1, le=100)


def _deployed_money_management_models() -> tuple[type[BaseModel], ...]:
    """Build one config model per deployed policy, from the policy's own fields.

    The two built-in models above are written by hand and stay that way, so the
    schema and error messages a client already sees do not move. A deployed policy
    gets a generated model instead of an edit here, which is what lets a new policy
    be configurable without touching this file.

    Only names, defaults, and types come from the dataclass. Range checks stay in
    the policy's ``__post_init__`` so one place owns what a value may be.
    """
    generated: list[type[BaseModel]] = []
    for mode, policy_class in sorted(registered_money_management().items()):
        if mode in {"manual", "turtle"}:
            continue
        settings = policy_settings(policy_class)
        definitions: dict[str, Any] = {"mode": (Literal[mode], mode)}
        for field in dataclass_fields(cast("Any", policy_class)):
            if field.name not in settings:
                continue
            has_default = field.default is not DATACLASS_MISSING
            definitions[field.name] = (field.type, field.default if has_default else ...)
        generated.append(
            create_model(
                f"{policy_class.__name__}Config",
                __config__=ConfigDict(extra="forbid"),
                **definitions,
            )
        )
    return tuple(generated)


_MONEY_MANAGEMENT_MODELS: Final = (
    ManualMoneyManagementConfig,
    TurtleMoneyManagementConfig,
    *_deployed_money_management_models(),
)

if TYPE_CHECKING:
    # A type checker cannot see a union assembled at import time. It reads the two
    # built-in shapes, which is what the rest of the service is written against;
    # the runtime alias below is the one that also accepts deployed policies.
    MoneyManagementConfig = Annotated[
        ManualMoneyManagementConfig | TurtleMoneyManagementConfig,
        Field(discriminator="mode"),
    ]
else:
    MoneyManagementConfig = Annotated[
        Union[_MONEY_MANAGEMENT_MODELS],  # noqa: UP007 - assembled, not written out
        Field(discriminator="mode"),
    ]


class RunConfig(BaseModel):
    """A fully validated deterministic backtest-run configuration."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    run_name: str = Field(min_length=1, max_length=128)
    strategy_id: str = Field(min_length=1, max_length=80)
    params: dict[str, object] = Field(default_factory=dict)
    symbol: str = Field(min_length=1, max_length=30)
    exchange: str = Field(min_length=1, max_length=20)
    timeframe: str = Field(min_length=2, max_length=10)
    market_type: Literal["spot", "futures"]
    data_source: str = Field(min_length=1)
    start: datetime
    end: datetime
    initial_capital: Decimal = Field(gt=0)
    seed: int = 0
    sizing_method: Literal["risk_based", "pct"] = "risk_based"
    risk_per_trade: float | None = None
    position_size_pct: float | None = None
    cost_values: dict[str, Decimal] = Field(default_factory=dict)
    indicator_mode: Literal["auto", "explicit", "all"] = "auto"
    explicit_indicators: list[dict[str, object]] = Field(default_factory=list)
    trigger_feed: Literal["tf_candle", "m1_subcandle"] = "tf_candle"
    fill_timing: Literal["immediate", "next_bar"] = "next_bar"
    profile_ref: str = Field(min_length=1)
    money_management: MoneyManagementConfig = Field(default_factory=ManualMoneyManagementConfig)
    sweep: dict[str, object] | None = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_legacy_money_management(cls, value: Any) -> Any:
        """Map stored Vessel money fields to the explicit manual policy."""
        if not isinstance(value, Mapping) or "money_management" in value:
            return value
        normalized = dict(value)
        if normalized.get("strategy_id") != "vessel-reference":
            return normalized
        params = normalized.get("params")
        legacy = dict(params) if isinstance(params, Mapping) else {}
        normalized["money_management"] = {
            "mode": "manual",
            "leverage": legacy.get("leverage", 1),
            "reward_risk": legacy.get("reward_risk", 2.0),
            "atr_stop_multiple": legacy.get("atr_stop_multiple", 2.0),
        }
        return normalized

    @field_validator("run_name")
    @classmethod
    def _validate_run_name(cls, value: str) -> str:
        if _RUN_NAME_PATTERN.fullmatch(value) is None:
            raise ValueError("run_name must contain only filename-safe characters")
        return value

    @field_validator("strategy_id")
    @classmethod
    def _validate_strategy_id(cls, value: str) -> str:
        if _STRATEGY_ID_PATTERN.fullmatch(value) is None:
            raise ValueError("strategy_id must be lowercase kebab-case")
        return value

    @field_validator("timeframe")
    @classmethod
    def _validate_timeframe(cls, value: str) -> str:
        if _TIMEFRAME_PATTERN.fullmatch(value) is None:
            raise ValueError("timeframe must be a positive minute, hour, or day interval")
        return value

    @field_validator("start", "end")
    @classmethod
    def _normalize_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("run timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("explicit_indicators")
    @classmethod
    def _validate_explicit_indicators(
        cls,
        value: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        for index, item in enumerate(value):
            if set(item) != {"name", "params"}:
                raise ValueError(
                    f"explicit_indicators[{index}] must contain exactly name and params"
                )
            name = item["name"]
            params = item["params"]
            if not isinstance(name, str) or not name:
                raise ValueError(f"explicit_indicators[{index}].name must be non-empty")
            if not isinstance(params, dict) or any(not isinstance(key, str) for key in params):
                raise ValueError(
                    f"explicit_indicators[{index}].params must be a string-keyed mapping"
                )
            normalized.append({"name": name, "params": dict(params)})
        return normalized

    @model_validator(mode="after")
    def _validate_contract(self) -> RunConfig:
        if self.start >= self.end:
            raise ValueError("start must be earlier than end")
        if self.fill_timing != "next_bar":
            raise ValueError("backtest RunConfig supports next_bar fill_timing only")
        if self.trigger_feed == "m1_subcandle":
            raise NotImplementedError(
                "m1_subcandle is reserved; this scope supports tf_candle only"
            )
        if self.indicator_mode == "explicit" and not self.explicit_indicators:
            raise ValueError("explicit indicator_mode requires explicit_indicators")
        if self.indicator_mode != "explicit" and self.explicit_indicators:
            raise ValueError("explicit_indicators may be set only when indicator_mode is explicit")
        if self.sizing_method == "risk_based":
            if self.position_size_pct is not None:
                raise ValueError("risk_based sizing requires position_size_pct to be absent")
            if self.risk_per_trade is None:
                self.risk_per_trade = 0.01
            if not 0.0 < self.risk_per_trade <= 0.01:
                raise ValueError("risk_per_trade must be in (0, 0.01]")
        else:
            if self.risk_per_trade is not None:
                raise ValueError("pct sizing requires risk_per_trade to be absent")
            if self.position_size_pct is None or not 0.0 < self.position_size_pct <= 1.0:
                raise ValueError("position_size_pct must be in (0, 1] for pct sizing")
        if self.money_management.mode == "turtle" and self.sizing_method != "risk_based":
            raise ValueError("turtle money management requires risk_based sizing")
        BacktestCostModel(
            self.cost_values,
            market_type=MarketType(self.market_type),
        )
        return self

    def revalidate(self) -> None:
        """Re-run field and cross-field validation for an existing instance."""
        type(self).model_validate(self.model_dump())

    def selection(self) -> dict[str, object]:
        """Return only the values consumed by the core Adapter Manager."""
        return {
            "strategy_id": self.strategy_id,
            "params": dict(self.params),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
        }
