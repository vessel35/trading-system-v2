"""Empty reference table for the statistics category before its first registrations."""

IDENTIFIERS: frozenset[str] = frozenset()
NAMES: frozenset[str] = frozenset()
STANDARD_SYSTEMS = 0
UNDEFINED_OUTPUTS: dict[str, tuple[str, ...]] = {}
REFERENCE: dict[str, dict[int, float]] = {}
CONVERGING: dict[str, tuple[dict[int, float], dict[int, float]]] = {}
UNCOMPARED: dict[str, str] = {}
