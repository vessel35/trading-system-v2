"""Collector domain entities and ports."""

from .models import Candle, CandleGap, FundingRate, Symbol, detect_gaps
from .ports import (
    CandleRepository,
    ExchangeClient,
    FundingExchangeClient,
    FundingRepository,
    HistoricalExchangeClient,
    SymbolRepository,
)

__all__ = [
    "Candle",
    "CandleGap",
    "CandleRepository",
    "ExchangeClient",
    "FundingExchangeClient",
    "FundingRate",
    "FundingRepository",
    "HistoricalExchangeClient",
    "Symbol",
    "SymbolRepository",
    "detect_gaps",
]
