"""Collector-owned continuous aggregate definitions."""

AGGREGATE_VIEWS: dict[str, str] = {
    "5m": "public.ohlcv_futures_5m",
    "15m": "public.ohlcv_futures_15m",
    "1h": "public.ohlcv_futures_1h",
    "4h": "public.ohlcv_futures_4h",
    "1d": "public.ohlcv_futures_1d",
}
