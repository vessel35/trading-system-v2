"""Settings keep the live contract fixed and credentials opaque."""

from __future__ import annotations

import pytest
from collector_service.core.config import Settings
from pydantic import ValidationError


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "config_db_url": "postgresql://config",
        "data_db_url": "postgresql://data",
    }
    values.update(overrides)
    return Settings.model_validate(values)


def test_required_dsns_are_secret_and_optional_symbol_is_not_a_seed() -> None:
    configured = settings(symbol="")
    assert configured.symbol is None
    assert "postgresql://config" not in repr(configured)
    assert configured.timeframe == "1m"
    assert configured.poll_interval_seconds == 60
    assert configured.poll_buffer_seconds == 2


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("exchange", "upbit"),
        ("timeframe", "5m"),
        ("fetch_limit", 100),
        ("poll_interval_seconds", 30),
        ("poll_buffer_seconds", 0),
    ],
)
def test_live_contract_cannot_be_configured_out_of_scope(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        settings(**{field: value})
