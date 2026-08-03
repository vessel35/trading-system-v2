"""Turn the per-bar tallies into the findings the comparison exists to produce.

`comparison.py` decides what happened on each bar. This module answers the questions that
are worth asking of all of it at once, and each of the four has a matching field in
`divergence.py` that has to explain what it turns up:

Which patterns did neither side match anywhere in the bundle? Those rows produced no
evidence at all, and a comparison that says nothing about a pattern is the failure mode
adding regimes is meant to cure.

Which did TA-Lib match while we stayed silent everywhere? That is what an unreachable rule
looks like from outside.

Which did we match while TA-Lib stayed silent? The mirror, and a much weaker signal: §3's
trend gate and §2's denominator make us narrower nearly everywhere, so our matching alone
usually means the two sections simply do not describe the same shape.

Which produced a bar where both matched and each claimed the opposite direction? The
sharpest disagreement available, and the one that is easiest to leave sitting in an
unexamined integer.

**Agreement is a finding too.** A table that lists only where the two sides part company
records half of what was measured, and the half it drops is the half that would notice a
pattern quietly drifting away from a target it used to track bar for bar. So
`high_agreement_patterns` is reported beside the divergences and pinned in `divergence.py`
the same way.

Nothing here decides anything. Every function returns what the captured values say, and the
judgment about whether a finding is acceptable lives in the hand-written table next door.

Section numbers in this file are the candlestick pattern standard's,
`docs/references/candlestick_pattern_calc_spec.md`. The indicator standard numbers its
own sections separately and they do not correspond.
"""

from collections import Counter
from collections.abc import Mapping

from . import talib_signals
from .comparison import TALIB_BASE_MATCH_MAGNITUDE, Comparison, comparisons
from .divergence import TALIB_FUNCTIONS
from .series import REGIME_NAMES, REGIMES_BY_NAME


def _resolve(subject: Mapping[str, Comparison] | None) -> Mapping[str, Comparison]:
    return comparisons() if subject is None else subject


def patterns_matched_by_neither(
    subject: Mapping[str, Comparison] | None = None,
) -> tuple[str, ...]:
    """Return the patterns neither side matched on any regime.

    This is the list whose shrinking measures whether a regime was worth adding. A pattern
    on it has not been shown to agree or to disagree; it has not been examined.
    """
    resolved = _resolve(subject)
    return tuple(
        sorted(
            name
            for name, entry in resolved.items()
            if entry.our_matches == 0 and entry.talib_matches == 0
        )
    )


def patterns_only_talib_matched(
    subject: Mapping[str, Comparison] | None = None,
) -> tuple[str, ...]:
    """Return the patterns TA-Lib matched somewhere while we matched nowhere."""
    resolved = _resolve(subject)
    return tuple(
        sorted(
            name
            for name, entry in resolved.items()
            if entry.our_matches == 0 and entry.talib_matches > 0
        )
    )


def patterns_only_we_matched(
    subject: Mapping[str, Comparison] | None = None,
) -> tuple[str, ...]:
    """Return the patterns we matched somewhere while TA-Lib matched nowhere."""
    resolved = _resolve(subject)
    return tuple(
        sorted(
            name
            for name, entry in resolved.items()
            if entry.our_matches > 0 and entry.talib_matches == 0
        )
    )


def patterns_with_direction_conflicts(
    subject: Mapping[str, Comparison] | None = None,
) -> dict[str, int]:
    """Return how many bars each pattern contradicted TA-Lib's direction on.

    Only patterns with at least one such bar appear, so an empty result means the two sides
    never disagreed about a bearing on a bar they both matched.
    """
    resolved = _resolve(subject)
    return {
        name: entry.both_conflict
        for name, entry in sorted(resolved.items())
        if entry.both_conflict > 0
    }


def patterns_with_bundle_zero_overlap(
    subject: Mapping[str, Comparison] | None = None,
) -> tuple[str, ...]:
    """Return patterns where both sides matched somewhere but never the same event bar."""
    resolved = _resolve(subject)
    return tuple(sorted(name for name, entry in resolved.items() if entry.bundle_zero_overlap))


def patterns_with_regime_zero_overlap(
    subject: Mapping[str, Comparison] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return per-regime zero-overlap findings whose expectation is at least one."""
    resolved = _resolve(subject)
    return {
        name: tuple(
            regime for regime in REGIME_NAMES if entry.by_regime[regime].regime_zero_overlap
        )
        for name, entry in sorted(resolved.items())
        if any(tally.regime_zero_overlap for tally in entry.by_regime.values())
    }


def patterns_with_material_overlap_deficit(
    subject: Mapping[str, Comparison] | None = None,
) -> tuple[str, ...]:
    """Return bundle rows where the overlap deficit exceeds sqrt(E)."""
    resolved = _resolve(subject)
    return tuple(sorted(name for name, entry in resolved.items() if entry.material_overlap_deficit))


def patterns_with_material_overlap_deficit_by_regime(
    subject: Mapping[str, Comparison] | None = None,
) -> dict[str, tuple[str, ...]]:
    """Return per-regime rows where the overlap deficit exceeds sqrt(E)."""
    resolved = _resolve(subject)
    return {
        name: tuple(
            regime for regime in REGIME_NAMES if entry.by_regime[regime].material_overlap_deficit
        )
        for name, entry in sorted(resolved.items())
        if any(tally.material_overlap_deficit for tally in entry.by_regime.values())
    }


def talib_non_base_magnitudes_by_pattern() -> dict[str, dict[int, int]]:
    """Return TA-Lib magnitudes other than ±100, keyed by pattern name."""
    pattern_by_function = {function: pattern for pattern, function in TALIB_FUNCTIONS.items()}
    counts: dict[str, Counter[int]] = {}
    for regime in REGIME_NAMES:
        for function, bars in talib_signals.SIGNALS[regime].items():
            pattern = pattern_by_function[function]
            for value in bars.values():
                if abs(value) != TALIB_BASE_MATCH_MAGNITUDE:
                    counts.setdefault(pattern, Counter())[value] += 1
    return {pattern: dict(values) for pattern, values in sorted(counts.items())}


def high_agreement_patterns(
    floor: float,
    subject: Mapping[str, Comparison] | None = None,
) -> frozenset[str]:
    """Return the patterns whose bars line up with TA-Lib's at or above `floor`.

    The ratio is `Comparison.bar_agreement`: of every bar either side matched, the fraction
    both matched. Patterns neither side matched are excluded rather than counted as zero,
    since no evidence and total disagreement are not the same fact.
    """
    resolved = _resolve(subject)
    return frozenset(
        name
        for name, entry in resolved.items()
        if entry.bar_agreement is not None and entry.bar_agreement >= floor
    )


def _ratio(value: float | None) -> str:
    return "     -" if value is None else f"{value:6.3f}"


def _quantity(value: float | None) -> str:
    return "       -" if value is None else f"{value:8.2f}"


def render_report(subject: Mapping[str, Comparison] | None = None) -> str:
    """Render the whole comparison as text, per regime and over the bundle."""
    resolved = _resolve(subject)
    lines: list[str] = []

    lines.append("TA-Lib candlestick comparison")
    lines.append("=" * 100)
    lines.append(
        f"TA-Lib {talib_signals.TALIB_VERSION} (C library "
        f"{talib_signals.TALIB_UNDERLYING_VERSION}), captured {talib_signals.CAPTURED_AT}"
    )
    lines.append("")
    lines.append("Regimes")
    lines.append("-" * 100)
    for regime_name in REGIME_NAMES:
        regime = REGIMES_BY_NAME[regime_name]
        lines.append(f"  {regime_name:<20} {regime.bar_count:>6} bars, {regime.timeframe}")
        lines.append(f"      {regime.character}")
    lines.append("")

    both = sum(1 for e in resolved.values() if e.our_matches > 0 and e.talib_matches > 0)
    only_theirs = patterns_only_talib_matched(resolved)
    only_ours = patterns_only_we_matched(resolved)
    nobody = patterns_matched_by_neither(resolved)
    bundle_zero = patterns_with_bundle_zero_overlap(resolved)
    regime_zero = patterns_with_regime_zero_overlap(resolved)
    material_deficit = patterns_with_material_overlap_deficit(resolved)
    material_deficit_by_regime = patterns_with_material_overlap_deficit_by_regime(resolved)
    non_base = talib_non_base_magnitudes_by_pattern()
    lines.append("Coverage over the bundle")
    lines.append("-" * 100)
    lines.append(f"  patterns both sides matched somewhere : {both}")
    lines.append(f"  patterns only TA-Lib matched          : {len(only_theirs)}")
    lines.append(f"  patterns only we matched              : {len(only_ours)}")
    lines.append(f"  patterns neither side matched         : {len(nobody)}")
    lines.append(f"  bundle zero-overlap findings          : {len(bundle_zero)}")
    lines.append(
        "  regime zero-overlap E>=1 findings     : "
        f"{sum(len(regimes) for regimes in regime_zero.values())}"
    )
    material_deficit_count = len(material_deficit) + sum(
        len(regimes) for regimes in material_deficit_by_regime.values()
    )
    lines.append(f"  material overlap-deficit findings     : {material_deficit_count}")
    lines.append(
        "  TA-Lib non-±100 magnitude bars        : "
        f"{sum(sum(values.values()) for values in non_base.values())}"
    )
    lines.append("")

    lines.append("Per pattern, over the bundle")
    lines.append("-" * 100)
    header = (
        f"  {'pattern':<28}{'CDL function':<22}{'ours':>7}{'talib':>7}"
        f"{'both':>7}{'other':>7}{'confl':>7}{'ovlp':>7}{'exp':>9}"
        f"{'bar':>7}{'dir':>7}"
    )
    lines.append(header)
    for name in sorted(resolved):
        entry = resolved[name]
        lines.append(
            f"  {name:<28}{entry.talib_function:<22}{entry.our_matches:>7}"
            f"{entry.talib_matches:>7}{entry.both_matched:>7}"
            f"{entry.same_bar_different_event:>7}{entry.both_conflict:>7}"
            f"{_ratio(entry.overlap_rate):>7}{_quantity(entry.overlap_expectation):>9}"
            f"{_ratio(entry.bar_agreement):>7}{_ratio(entry.direction_agreement):>7}"
        )
    lines.append("")

    lines.append("Per pattern, per regime")
    lines.append("-" * 100)
    for name in sorted(resolved):
        entry = resolved[name]
        lines.append(f"  {name} ({entry.talib_function})")
        for regime_name in REGIME_NAMES:
            tally = entry.by_regime[regime_name]
            lines.append(
                f"      {regime_name:<20}ours {tally.our_matches:>5}  "
                f"talib {tally.talib_matches:>5}  both {tally.both_matched:>5}  "
                f"other {tally.same_bar_different_event:>4}  conflict {tally.both_conflict:>4}  "
                f"ovlp {_ratio(tally.overlap_rate):>7}  "
                f"exp {_quantity(tally.overlap_expectation):>8}"
            )
    lines.append("")

    lines.append("Direction conflicts, by bar")
    lines.append("-" * 100)
    conflicts = patterns_with_direction_conflicts(resolved)
    if not conflicts:
        lines.append("  none")
    for name in conflicts:
        for regime_name, bars in resolved[name].conflict_bars_by_regime.items():
            lines.append(f"  {name:<28}{regime_name:<20}{list(bars)}")
    lines.append("")

    lines.append("Regime zero-overlap findings, E>=1")
    lines.append("-" * 100)
    if not regime_zero:
        lines.append("  none")
    for name, regimes in regime_zero.items():
        lines.append(f"  {name:<28}{', '.join(regimes)}")
    lines.append("")

    lines.append("Material overlap-deficit findings")
    lines.append("-" * 100)
    if not material_deficit and not material_deficit_by_regime:
        lines.append("  none")
    for name in material_deficit:
        lines.append(f"  {name:<28}bundle")
    for name, regimes in material_deficit_by_regime.items():
        lines.append(f"  {name:<28}{', '.join(regimes)}")
    lines.append("")

    lines.append("TA-Lib non-±100 magnitudes")
    lines.append("-" * 100)
    if not non_base:
        lines.append("  none")
    for name, values in non_base.items():
        total = sum(values.values())
        rendered = ", ".join(f"{value}: {count}" for value, count in sorted(values.items()))
        lines.append(f"  {name:<28}{total:>5} bars  ({rendered})")
    lines.append("")

    _append_list(lines, "Bundle zero-overlap findings", bundle_zero)
    _append_list(lines, "Patterns neither side matched anywhere", nobody)
    _append_list(lines, "Patterns only TA-Lib matched", only_theirs)
    _append_list(lines, "Patterns only we matched", only_ours)

    return "\n".join(lines)


def _append_list(lines: list[str], title: str, names: tuple[str, ...]) -> None:
    """Append one titled list of pattern names, saying so when it is empty."""
    lines.append(title)
    lines.append("-" * 100)
    if names:
        lines.extend(f"  {name}" for name in names)
    else:
        lines.append("  none")
    lines.append("")
