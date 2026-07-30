"""Construct registered money-management policies from validated mappings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from .policies import (
    ManualMoneyManagement,
    MoneyManagementPolicy,
    TurtleMoneyManagement,
)


class MoneyManagementFactory:
    """Validate one mode-specific configuration and construct its policy."""

    @staticmethod
    def create(raw_config: Mapping[str, object]) -> MoneyManagementPolicy:
        mode = raw_config.get("mode", "manual")
        if mode == "manual":
            allowed = {"mode", "leverage", "reward_risk", "atr_stop_multiple"}
            _reject_extra(raw_config, allowed)
            return ManualMoneyManagement(
                leverage=_integer(raw_config.get("leverage", 1), "leverage"),
                reward_risk=_number(raw_config.get("reward_risk", 2.0), "reward_risk"),
                atr_stop_multiple=_number(
                    raw_config.get("atr_stop_multiple", 2.0),
                    "atr_stop_multiple",
                ),
            )
        if mode == "turtle":
            allowed = {
                "mode",
                "n_period",
                "n_timeframe",
                "stop_n_multiple",
                "leverage_cap",
            }
            _reject_extra(raw_config, allowed)
            timeframe = raw_config.get("n_timeframe", "1d")
            if not isinstance(timeframe, str):
                raise TypeError("n_timeframe must be a string")
            return TurtleMoneyManagement(
                n_period=_integer(raw_config.get("n_period", 20), "n_period"),
                n_timeframe=timeframe,
                stop_n_multiple=_number(
                    raw_config.get("stop_n_multiple", 2.0),
                    "stop_n_multiple",
                ),
                leverage_cap=_integer(
                    raw_config.get("leverage_cap", 10),
                    "leverage_cap",
                ),
            )
        raise ValueError(f"unsupported money-management mode: {mode!r}")


def _reject_extra(raw: Mapping[str, object], allowed: set[str]) -> None:
    extra = set(raw) - allowed
    if extra:
        raise ValueError(f"unexpected money-management parameters: {sorted(extra)}")


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, float | int):
        raise TypeError(f"{name} must be numeric")
    return float(value)


MONEY_MANAGEMENT_MODES: Final = ("manual", "turtle")
