"""Track the Donchian Channel awaiting later registration."""

# §3.3 is now registered from `specs/volatility.py`, so nothing is awaiting
# registration here. The module stays until the follow-up catalogs are
# consolidated, because the coverage count in `test_indicator_registry.py`
# gathers this name alongside the other categories'.
FOLLOW_UP_INDICATORS: tuple[str, ...] = ()
