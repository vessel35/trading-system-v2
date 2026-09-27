"""Diagnostics that run the Engine without a database, for pre-deployment checks.

Everything here is a stand-in: a synthetic candle feed, an in-memory catalog that never claims
a determinism reference, and registration rows made from what discovery found. They exist so a
strategy can be run end to end before it is registered anywhere. Nothing operational imports
this package, and a test in ``tests/test_synthetic_dry_run.py`` keeps it that way.
"""
