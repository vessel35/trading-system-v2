"""Environment-only collector settings."""

from __future__ import annotations

from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated live wiring; DSNs and keys are never given literal defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="COLLECTOR_",
        case_sensitive=False,
        extra="ignore",
    )

    config_db_url: SecretStr
    data_db_url: SecretStr
    binance_api_key: SecretStr = SecretStr("")
    binance_api_secret: SecretStr = SecretStr("")
    exchange: Literal["binance"] = "binance"
    timeframe: Literal["1m"] = "1m"
    symbol: str | None = None
    fetch_limit: Literal[2, 3] = 3
    poll_interval_seconds: Literal[60] = 60
    poll_buffer_seconds: Literal[2] = 2
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @field_validator("symbol", mode="before")
    @classmethod
    def empty_symbol_is_unset(cls, value: object) -> object:
        """Allow a blank optional environment variable without making it a seed."""

        return None if value == "" else value
