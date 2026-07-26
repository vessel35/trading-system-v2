"""Executable entry point for live confirmed-candle ingestion."""

from __future__ import annotations

import asyncio
import logging

from collector_service.core import Settings, build_runtime


async def _run(settings: Settings) -> None:
    runtime = build_runtime(settings)
    try:
        await runtime.collector.run()
    finally:
        await runtime.close()


def main() -> None:
    """Load environment settings and run until interrupted."""

    settings = Settings()  # type: ignore[call-arg]  # values come from the environment
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(_run(settings))
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("collector_stopped")


if __name__ == "__main__":
    main()
