"""Verify the shared Decimal precision contract."""

from decimal import Decimal
from typing import cast

import pytest
from core_lib.types import money


def test_precision_constants_match_the_design() -> None:
    assert money.ZERO == Decimal("0")
    assert money.ONE_HUNDRED == Decimal("100")
    assert money.Q_PRICE == Decimal("0.00000001")
    assert money.Q_AMOUNT == Decimal("0.00000001")
    assert money.Q_PERCENT == Decimal("0.01")
    assert money.Q_RATIO == Decimal("0.0001")
    assert money.Q_FEE_RATE == Decimal("0.0001")


def test_quantizers_use_round_half_even_at_each_precision() -> None:
    assert money.quantize_price(Decimal("1.000000005")) == Decimal("1.00000000")
    assert money.quantize_amount(Decimal("1.000000015")) == Decimal("1.00000002")
    assert money.quantize_percent(Decimal("1.005")) == Decimal("1.00")
    assert money.quantize_ratio(Decimal("1.00005")) == Decimal("1.0000")
    assert money.quantize_fee_rate(Decimal("0.00015")) == Decimal("0.0002")


def test_quantizers_reject_values_that_skipped_the_decimal_gateway() -> None:
    with pytest.raises(TypeError, match="Decimal"):
        money.quantize_price(cast(Decimal, 1.25))


def test_funding_rate_has_no_lossy_quantizer() -> None:
    assert not hasattr(money, "quantize_funding_rate")
