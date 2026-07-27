"""Executable entry point for live and bounded source ingestion modes."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from service_commons.observability import configure_logging

from collector_service.core import Settings, build_runtime

Mode = Literal["collect", "backfill", "funding-backfill", "refresh-aggregates"]


async def _run(
    settings: Settings,
    *,
    mode: Mode = "collect",
    start: datetime | None = None,
    end: datetime | None = None,
    timeframes: Sequence[str] | None = None,
) -> None:
    runtime = build_runtime(settings)
    try:
        if mode == "collect":
            await runtime.collector.run()
        elif mode == "backfill":
            if start is None or end is None:
                raise ValueError("backfill mode requires start and end")
            await runtime.backfill.run(start=start, end=end)
        elif mode == "funding-backfill":
            if start is None or end is None:
                raise ValueError("funding-backfill mode requires start and end")
            await runtime.funding_backfill.run(start=start, end=end)
        else:
            if start is None or end is None:
                raise ValueError("refresh-aggregates mode requires start and end")
            await runtime.aggregate_refresh.run(
                start=start,
                end=end,
                timeframes=timeframes,
            )
    finally:
        await runtime.close()


def main(argv: Sequence[str] | None = None) -> None:
    """Select one collection or maintenance mode and run the configured target."""

    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    if arguments.mode != "collect" and (arguments.start is None or arguments.end is None):
        parser.error(f"{arguments.mode} requires --start and --end")
    if arguments.mode == "collect" and (arguments.start is not None or arguments.end is not None):
        parser.error("collect does not accept --start or --end")
    if arguments.mode != "refresh-aggregates" and arguments.timeframes is not None:
        parser.error("--timeframes is accepted only by refresh-aggregates")

    settings_arguments = {}
    if arguments.symbol is not None:
        settings_arguments["symbol"] = arguments.symbol
    settings = Settings(**settings_arguments)
    configure_logging(getattr(logging, settings.log_level))
    try:
        asyncio.run(
            _run(
                settings,
                mode=arguments.mode,
                start=arguments.start,
                end=arguments.end,
                timeframes=arguments.timeframes,
            )
        )
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("collector_stopped")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binance USD-M source collector")
    parser.add_argument(
        "mode",
        choices=("collect", "backfill", "funding-backfill", "refresh-aggregates"),
        nargs="?",
        default="collect",
    )
    parser.add_argument(
        "--start",
        type=_utc_datetime,
        help="inclusive ISO-8601 range start with an explicit UTC offset",
    )
    parser.add_argument(
        "--end",
        type=_utc_datetime,
        help="exclusive ISO-8601 range end with an explicit UTC offset",
    )
    parser.add_argument(
        "--symbol",
        help="optional CCXT symbol selector, for example ETH/USDT:USDT",
    )
    parser.add_argument(
        "--timeframes",
        type=_comma_separated_timeframes,
        help="comma-separated aggregate timeframes (default: 5m,15m,1h,4h,1d)",
    )
    return parser


def _utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("must include an explicit UTC offset")
    return parsed


def _comma_separated_timeframes(value: str) -> tuple[str, ...]:
    timeframes = tuple(part.strip() for part in value.split(","))
    if not timeframes or any(not timeframe for timeframe in timeframes):
        raise argparse.ArgumentTypeError("must be a comma-separated list of timeframes")
    return timeframes


if __name__ == "__main__":
    main()
