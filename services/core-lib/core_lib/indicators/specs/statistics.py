"""Registration list owned by the statistics category.

The category exists before its first registrations so the paired-series input
contract can land separately from the BETA and CORREL calculations that consume it.
"""

from core_lib.indicators.registry import IndicatorSpec

SPECS: tuple[IndicatorSpec, ...] = ()
