"""Verify the eight abstract environment boundaries and their exact surfaces."""

import inspect

from core_lib.ports import (
    Broker,
    CatalogStore,
    Clock,
    CostModel,
    DataFeed,
    EvidenceSink,
    MoneyManagementRegistry,
    StrategyRegistry,
)


def test_all_eight_ports_are_abstract_with_the_standard_methods() -> None:
    expected = {
        DataFeed: {"candles", "funding", "mark_price"},
        Broker: {"submit", "open_orders", "cancel"},
        Clock: {"now", "advance"},
        CostModel: {"fee", "slippage", "funding_rate", "liq_params"},
        EvidenceSink: {"record", "finalize"},
        CatalogStore: {
            "save_prereg",
            "register",
            "upsert_summary",
            "record_harness_aggregate",
        },
        MoneyManagementRegistry: {"get", "list"},
        StrategyRegistry: {"get", "list", "register"},
    }
    assert len(expected) == 8
    for port, methods in expected.items():
        assert inspect.isabstract(port)
        assert port.__abstractmethods__ == methods
