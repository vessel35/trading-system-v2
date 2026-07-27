"""Executable entry point for live and bounded source ingestion modes."""

from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from collector_service.application.observability import configure_logging
from collector_service.core import Settings, build_runtime

Mode = Literal["collect", "backfill", "funding-backfill"]


async def _run(
    settings: Settings,
    *,
    mode: Mode = "collect",
    start: datetime | None = None,
    end: datetime | None = None,
) -> None:
    runtime = build_runtime(settings)
    try:
        if mode == "collect":
            await runtime.collector.run()
        elif mode == "backfill":
            if start is None or end is None:
                raise ValueError("backfill mode requires start and end")
            await runtime.backfill.run(start=start, end=end)
        else:
            if start is None or end is None:
                raise ValueError("funding-backfill mode requires start and end")
            await runtime.funding_backfill.run(start=start, end=end)
    finally:
        await runtime.close()


def main(argv: Sequence[str] | None = None) -> None:
    """Select collect/backfill/funding-backfill and run the configured target."""

    parser = _argument_parser()
    arguments = parser.parse_args(argv)
    if arguments.mode != "collect" and (arguments.start is None or arguments.end is None):
        parser.error(f"{arguments.mode} requires --start and --end")
    if arguments.mode == "collect" and (arguments.start is not None or arguments.end is not None):
        parser.error("collect does not accept --start or --end")

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
            )
        )
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("collector_stopped")


def _argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Binance USD-M source collector")
    parser.add_argument(
        "mode",
        choices=("collect", "backfill", "funding-backfill"),
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
    return parser


def _utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("must include an explicit UTC offset")
    return parsed


if __name__ == "__main__":
    main()
