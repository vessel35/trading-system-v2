"""Guard Broker adapters against bypassing the shared Decimal normalizer."""

import pytest


def test_broker_normalizer_conformance_scaffold() -> None:
    """Defer conformance until the M1 Broker placeholder gains submit behavior."""
    pytest.skip("Broker submit behavior is intentionally absent from the M1 scaffold")
