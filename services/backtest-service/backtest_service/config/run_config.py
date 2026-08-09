"""Define validated run, data, cost, risk, sweep, indicator, and profile settings."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import MISSING as DATACLASS_MISSING
from dataclasses import fields as dataclass_fields
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal, Union, cast, get_type_hints

from core_lib.money_management import MoneyManagementBase, policy_settings
from core_lib.types import MarketType
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    create_model,
    field_validator,
    model_validator,
)
from trading_plugins import registered_money_management

from backtest_service.adapters.cost_model import BacktestCostModel

_LOGGER = logging.getLogger(__name__)
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


def _config_model_for(mode: str, policy_class: type[MoneyManagementBase]) -> type[BaseModel]:
    """Build one config model from a deployed policy's own dataclass fields.

    Only names, defaults, and types come from the dataclass. Range checks stay in
    the policy's ``__post_init__`` so one place owns what a value may be.

    The annotations are resolved through ``get_type_hints`` rather than read off
    ``field.type``. A plugin written with ``from __future__ import annotations``
    stores its types as strings, and handing a string to Pydantic leaves the model
    unfinished until something asks for its schema, which is far from the file
    that caused it.
    """
    settings = policy_settings(policy_class)
    if "mode" in settings:
        # ``mode`` is the discriminator the union is keyed on. A setting by that
        # name would overwrite it with the setting's own type, and the union then
        # refuses to assemble at all rather than dropping this one policy.
        raise ValueError(f"money-management policy {mode!r} may not declare a setting named 'mode'")
    hints = get_type_hints(policy_class)
    definitions: dict[str, Any] = {"mode": (Literal[mode], mode)}
    for field in dataclass_fields(cast("Any", policy_class)):
        if field.name not in settings:
            continue
        annotation = hints[field.name]
        if field.default is not DATACLASS_MISSING:
            definitions[field.name] = (annotation, field.default)
        elif field.default_factory is not DATACLASS_MISSING:
            # A factory default is still a default. Reading only ``field.default``
            # turned these into required fields, so a configuration the policy
            # factory accepts was refused by the run config and the API schema.
            definitions[field.name] = (annotation, Field(default_factory=field.default_factory))
        else:
            definitions[field.name] = (annotation, ...)
    model: type[BaseModel] = create_model(
        f"{policy_class.__name__}Config",
        __config__=ConfigDict(extra="forbid"),
        **definitions,
    )
    # Ask for the schema here. Pydantic defers this, so a type it cannot express
    # would otherwise surface while RunConfig itself is being assembled — outside
    # the isolation below, where it takes manual validation and OpenAPI down too.
    model.model_json_schema()
    return model


def _money_management_adapter(models: Sequence[type[BaseModel]]) -> TypeAdapter[Any]:
    """Build the runtime discriminated union for exactly these models."""
    return TypeAdapter(
        Annotated[
            Union[tuple(models)],  # noqa: UP007 - assembled from a runtime tuple
            Field(discriminator="mode"),
        ]
    )


def _schema_names(model: type[BaseModel]) -> frozenset[str]:
    """Return every component name one arm contributes to a JSON schema."""
    schema = model.model_json_schema()
    definitions = cast("Mapping[str, object]", schema.get("$defs", {}))
    return frozenset((model.__name__, *definitions))


def _referenced_schema(schema: Mapping[str, Any], mode: str) -> tuple[str, dict[str, Any]]:
    """Return one mode's discriminator target and recursively referenced definitions."""
    discriminator = cast("Mapping[str, Any]", schema["discriminator"])
    mapping = cast("Mapping[str, str]", discriminator["mapping"])
    target = mapping[mode]
    definitions = cast("Mapping[str, dict[str, Any]]", schema.get("$defs", {}))
    pending = [target]
    reachable: dict[str, dict[str, Any]] = {}
    while pending:
        reference = pending.pop()
        prefix = "#/$defs/"
        if not reference.startswith(prefix):
            raise ValueError(f"money-management mode {mode!r} has a non-local schema reference")
        name = reference.removeprefix(prefix)
        if name in reachable:
            continue
        component = definitions[name]
        reachable[name] = component

        def visit(value: object) -> None:
            if isinstance(value, Mapping):
                nested = value.get("$ref")
                if isinstance(nested, str):
                    pending.append(nested)
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)

        visit(component)
    return target, reachable


def _accept_config_model(
    candidate: type[BaseModel],
    accepted: Sequence[type[BaseModel]],
) -> None:
    """Prove a candidate preserves the complete union that will actually be exposed."""
    existing_names = set().union(*(_schema_names(model) for model in accepted))
    collisions = existing_names & _schema_names(candidate)
    if collisions:
        raise ValueError(f"money-management schema component names collide: {sorted(collisions)}")

    before = _money_management_adapter(accepted).json_schema()
    complete = (*accepted, candidate)
    after = _money_management_adapter(complete).json_schema()
    after_mapping = cast(
        "Mapping[str, str]",
        cast("Mapping[str, object]", after["discriminator"])["mapping"],
    )
    for model in complete:
        mode = str(model.model_fields["mode"].default)
        expected = f"#/$defs/{model.__name__}"
        if after_mapping.get(mode) != expected:
            raise ValueError(f"money-management mode {mode!r} does not point to its own schema arm")
    for model in accepted:
        mode = str(model.model_fields["mode"].default)
        if _referenced_schema(before, mode) != _referenced_schema(after, mode):
            raise ValueError(f"money-management mode {mode!r} changed while adding another policy")


def _deployed_money_management_models(
    policies: Mapping[str, type[MoneyManagementBase]] | None = None,
) -> tuple[type[BaseModel], ...]:
    """Build a config model per deployed policy, skipping any that cannot form one.

    The two built-in models above are written by hand and stay that way, so the
    schema and error messages a client already sees do not move. A deployed policy
    gets a generated model instead of an edit here, which is what lets a new policy
    be configurable without touching this file.

    One policy is isolated from the rest. Letting a single bad deployment raise
    here would fail the import of this module, and with it manual validation and
    the OpenAPI document, for every run in the system.
    """
    registered = registered_money_management() if policies is None else policies
    generated: list[type[BaseModel]] = []
    for mode, policy_class in sorted(registered.items()):
        if mode in {"manual", "turtle"}:
            continue
        try:
            candidate = _config_model_for(mode, policy_class)
            _accept_config_model(
                candidate,
                (ManualMoneyManagementConfig, TurtleMoneyManagementConfig, *generated),
            )
            generated.append(candidate)
        except (Exception, SystemExit):  # noqa: BLE001 - one policy must not break the rest
            # ``SystemExit`` belongs here as much as an ordinary error: resolving
            # the annotations runs code the deployed file wrote, so a file that
            # exits from an annotation would end the process that imported it.
            _LOGGER.exception(
                "money-management mode %s cannot be selected in a run: its settings "
                "do not form a configuration schema",
                mode,
            )
    return tuple(generated)


_MONEY_MANAGEMENT_MODELS: Final[tuple[type[BaseModel], ...]] = (
    ManualMoneyManagementConfig,
    TurtleMoneyManagementConfig,
    *_deployed_money_management_models(),
)
_MONEY_MANAGEMENT_ADAPTER: Final = _money_management_adapter(_MONEY_MANAGEMENT_MODELS)

if TYPE_CHECKING:

    class DeployedMoneyManagementConfig(BaseModel):
        """The shape a checker sees for any policy deployed as a file.

        The real union is assembled at import time from what is deployed, and a
        checker cannot see it. Naming only the two built-in shapes made the
        checker's view narrower than run time: it read ``mode != "manual"`` as
        Turtle and approved an attribute a deployed policy does not have. This
        third arm carries only the discriminator, so such an access is refused.

        ``mode`` is deliberately ``str`` so code may compare it with any deployed
        id. Built-in fields are narrowed by ``isinstance`` instead of by a mode
        equality, because the deployed arm necessarily overlaps every string.
        """

        mode: str

    MoneyManagementConfig = Annotated[
        ManualMoneyManagementConfig | TurtleMoneyManagementConfig | DeployedMoneyManagementConfig,
        Field(discriminator="mode"),
    ]
else:
    MoneyManagementConfig = Annotated[
        Union[_MONEY_MANAGEMENT_MODELS],  # noqa: UP007 - assembled, not written out
        Field(discriminator="mode"),
    ]


SELECTABLE_MONEY_MANAGEMENT_MODES: Final[frozenset[str]] = frozenset(
    str(model.model_fields["mode"].default) for model in _MONEY_MANAGEMENT_MODELS
)
"""The modes a run may actually name.

A policy that is registered but whose settings do not form a configuration schema
is left out of the union above, and a run naming it is refused. Anything that
offers a choice reads this set, so a mode cannot be shown as selectable and then
rejected on submission.
"""


def validate_money_management_config(value: Mapping[str, object]) -> dict[str, object]:
    """Validate and normalize a projected default through the final runtime union."""
    validated = _MONEY_MANAGEMENT_ADAPTER.validate_python(dict(value))
    if not isinstance(validated, BaseModel):
        raise TypeError("money-management config did not resolve to a model")
    return cast("dict[str, object]", validated.model_dump())


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
