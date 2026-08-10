"""Verify the single external strategy catalog row contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from core_lib.strategy import CATALOG_COLUMNS, catalog_row_entry


def _catalog_row() -> tuple[object, ...]:
    return (
        "probe",
        "Probe",
        "strategies.probe",
        "Probe",
        None,
        "1.0.0",
        ["1h"],
        [{"name": "ema", "params": {"period": 21}}],
        21,
        {"period": 21},
        True,
        False,
        datetime(2026, 1, 1, tzinfo=UTC),
        datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_catalog_row_entry_preserves_the_catalog_shape() -> None:
    entry = catalog_row_entry(_catalog_row())

    assert tuple(entry) == CATALOG_COLUMNS
    assert entry["strategy_id"] == "probe"
    assert entry["required_indicators_json"] == [{"name": "ema", "params": {"period": 21}}]
    assert entry["default_params_json"] == {"period": 21}


def test_catalog_row_entry_rejects_a_wrong_row_length() -> None:
    with pytest.raises(ValueError, match="unexpected row shape"):
        catalog_row_entry(_catalog_row()[:-1])


@pytest.mark.parametrize(
    ("index", "replacement", "message"),
    [
        (7, {}, "required_indicators_json must decode to a list"),
        (9, [], "default_params_json must decode to a dict"),
    ],
)
def test_catalog_row_entry_rejects_wrong_json_value_types(
    index: int,
    replacement: object,
    message: str,
) -> None:
    row = list(_catalog_row())
    row[index] = replacement

    with pytest.raises(TypeError, match=message):
        catalog_row_entry(row)
