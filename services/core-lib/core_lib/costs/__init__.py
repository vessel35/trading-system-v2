"""Define the four net-profit cost formula standards."""

from .fee import calc as calculate_fee
from .funding import is_boundary as is_funding_boundary
from .funding import settle as settle_funding
from .liquidation import is_triggered as is_liquidation_triggered
from .liquidation import price as liquidation_price
from .slippage import SlippageParams
from .slippage import apply as apply_slippage
from .slippage import effective_rate as effective_slippage_rate

__all__ = [
    "SlippageParams",
    "apply_slippage",
    "calculate_fee",
    "effective_slippage_rate",
    "is_funding_boundary",
    "is_liquidation_triggered",
    "liquidation_price",
    "settle_funding",
]
