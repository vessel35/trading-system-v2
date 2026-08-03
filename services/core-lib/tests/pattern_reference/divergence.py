"""State, by hand, how each of the sixty-one patterns is expected to relate to TA-Lib.

Why a hand-written table
------------------------

The indicator comparison could ask for equality: both sides compute the same number from
the same standard's formula, so a mismatch is an error in one of them. This comparison
cannot. §10.3 of the pattern standard says so outright — divergence is the expected
outcome — and the two structural reasons are decisions the standard took deliberately.

Decision A refused to inherit TA-Lib's `TA_SetCandleSettings` table, and §2 put every scale
over one denominator: the judged bar's own high-low range. TA-Lib measures the same English
words ("long body", "very short shadow") against a moving average of recent bars. The same
bar can therefore be a long body to one side and not to the other with neither side being
wrong, because they are not measuring the same thing.

Decision B made the prior trend part of the pattern rather than something a strategy
supplies, so §3 judges a ten-period exponential moving average of the range midpoint on the
pattern's first bar. Forty-five of the sixty-one carry that gate. TA-Lib mostly judges shape
alone, which means it can report a shape we refuse purely because the trend was absent.

So a table of expected equalities would be false before it was written. What is worth
pinning instead is *why* each pattern diverges, traced to the decision or the section it
comes from, so that the reason cannot quietly change into a different one. A note that said
only "differs from TA-Lib" would pin nothing.

The one thing this table can be wrong about
-------------------------------------------

`expected_silence` is the field that carries risk, and it is the point of the whole
package. A pattern TA-Lib matches repeatedly while we never match it once is what an
unreachable rule looks like from outside. Two sections were already found contradictory
enough that no bar could satisfy them, and an arithmetic sweep found those; a rule that is
satisfiable in principle but never reached on real-shaped data is invisible to that sweep
and visible here.

So silence is not excused by default. `expected_silence` stays `None` unless somebody has
looked at that specific pattern and written down what they found, and the suite fails on
any pattern TA-Lib matched, we did not, and nobody has explained. Filling this field to
make a test pass, rather than after an investigation, converts the only check that can find
an unreachable rule into a check that finds nothing.

The field is also checked in the other direction: a recorded silence for a pattern that
does match is stale, and stale is how a table stops describing the code it claims to
describe.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class Cause(StrEnum):
    """Why a pattern's judgment can differ from TA-Lib's on the same bar."""

    SCALE_DENOMINATOR = "scale-denominator"
    """§2 measures every scale against the judged bar's own high-low range.

    Decision A chose that denominator and refused TA-Lib's settings table, whose "long"
    and "short" are relative to an average of recent bars. Fifty-six patterns read at
    least one §2 scale and so inherit the difference.
    """

    PRIOR_TREND = "prior-trend"
    """§3 makes the trend part of the judgment, on the pattern's first bar.

    Decision B put it here rather than in a strategy, so forty-five patterns refuse a
    shape that arrives without the trend the source required. A comparison target that
    judges shape alone matches more bars for that reason alone.
    """

    SEPARATE_CONFIRMATION_KEY = "separate-confirmation-key"
    """§5.4 puts confirmation on the later bar it happens on, as its own key.

    Forty-three patterns are graded `Required` or `Suggested` in at least one direction.
    Our match bar and our confirmation bar are different bars on purpose; anything that
    folds the two into one output cannot line up with either key alone.
    """

    GAP_AS_THE_SOURCE_DEFINED_IT = "gap-as-the-source-defined-it"
    """Decision D kept each source's gap, and §2.8 read the unstated five as body gaps.

    Eighteen patterns require a gap. The standard did not widen a real-body gap into a
    high-low gap to make matches more frequent on a market that trades around the clock,
    and §7.5's frequency note is the acknowledged price of that.
    """

    SOURCE_READING = "source-reading"
    """The standard chose between conflicting or incomplete source readings.

    Decision C makes the narrower, more-conditioned reading normative. §10.1 lists the
    six places an ambiguous sentence was closed and §10.2 the five the standard found and
    corrected, and a handful of §7 sections record a choice between Morris and Nison in
    place. Sixteen patterns carry one.
    """

    NO_DIRECTION_CLAIMED = "no-direction-claimed"
    """§5.2's nine shape-only lines report `_dir` of zero even when they match.

    The sources name them as shapes, not as signals, so the bar's colour is left in the
    candle where a consumer can read it. TA-Lib signs those same functions by colour, so
    its sign and our `_dir` are not the same quantity.
    """

    THRESHOLD_IS_NOT_A_PARAMETER = "threshold-is-not-a-parameter"
    """§7 fixes the penetration depth from the source; TA-Lib takes it as an argument.

    Seven `CDL` functions accept `penetration`. The standard writes the depth into the
    rule because the source stated it, so there is no argument to align and the captured
    default is recorded as provenance rather than adopted.
    """


@dataclass(frozen=True, slots=True)
class Divergence:
    """One pattern's expected relation to its `CDL` counterpart, and the reason."""

    pattern: str
    talib_function: str
    causes: tuple[Cause, ...]
    note: str
    """Prose naming the decision or section the divergence comes from.

    It has to say what differs and why. "Differs from TA-Lib" restates the premise of the
    whole comparison and pins nothing.
    """

    expected_silence: str | None = None
    """Why this pattern is expected never to match on the comparison series.

    `None` means we expect it to match, and the suite treats silence against a matching
    TA-Lib as an unexplained finding. Anything else must be the result of an
    investigation, written so a reader can check it.
    """

    def __post_init__(self) -> None:
        if not self.causes:
            raise ValueError(f"{self.pattern} records no cause of divergence")
        if not self.note.strip():
            raise ValueError(f"{self.pattern} records no note")


_TABLE: tuple[Divergence, ...] = (
    # §7.1 — the doji family and the umbrella lines.
    Divergence(
        pattern="pat_doji",
        talib_function="CDLDOJI",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "§2.3 calls a bar a doji when its body is at most three percent of that bar's own "
            "range, a value decision A took from inside the one-to-three percent band Morris "
            "reports as working well. A target that measures the body against recent bodies "
            "asks a different question of the same bar, and §5.2 additionally leaves `_dir` at "
            "zero where TA-Lib signs the function positive."
        ),
    ),
    Divergence(
        pattern="pat_long_legged_doji",
        talib_function="CDLLONGLEGGEDDOJI",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "Adds §2.4's long shadows to §2.3's doji, and those two scales do not share a "
            "denominator: the doji tolerance is a fraction of the range while the shadow "
            "multiple is against the body, because Nison and Morris both wrote the multiple "
            "that way. §2 kept the source's denominator rather than unifying it."
        ),
    ),
    Divergence(
        pattern="pat_rickshaw_man",
        talib_function="CDLRICKSHAWMAN",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "Adds §2.6's `Near` at ten percent of the range for a body sitting near the middle "
            "of the range. No source gives a number for 'near', so decision A set one and tied "
            "it to §2.5's very-short-shadow threshold to keep one sentence from being measured "
            "two ways."
        ),
    ),
    Divergence(
        pattern="pat_dragonfly_doji",
        talib_function="CDLDRAGONFLYDOJI",
        causes=(Cause.SCALE_DENOMINATOR,),
        note=(
            "Combines §2.3's doji with §2.5's ten-percent upper-shadow ceiling and §2.4's "
            "lower-shadow multiple. The ceiling is Morris's own worked example rather than a "
            "rule he stated, so decision A adopting it is a choice recorded in §2.5."
        ),
    ),
    Divergence(
        pattern="pat_gravestone_doji",
        talib_function="CDLGRAVESTONEDOJI",
        causes=(Cause.SCALE_DENOMINATOR,),
        note=(
            "The mirror of the dragonfly and it inherits the same two chosen values, §2.3's "
            "three percent and §2.5's ten percent."
        ),
    ),
    Divergence(
        pattern="pat_takuri",
        talib_function="CDLTAKURI",
        causes=(Cause.SCALE_DENOMINATOR,),
        note=(
            "Takes the dragonfly's rules and adds the three-times lower shadow Morris states "
            "outright. The value is the source's, but §2.7 is ours: a zero body satisfies a "
            "lower-bound shadow multiple, without which a dragonfly doji could not be a Takuri "
            "at all, which contradicts Morris placing Takuri inside that family."
        ),
    ),
    Divergence(
        pattern="pat_hammer",
        talib_function="CDLHAMMER",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "The shape is §2.2's short body with §2.5's upper-shadow ceiling and the source's "
            "two-times lower shadow, and §3 additionally requires the downtrend Morris's header "
            "demands. A shape-only target matches hammers inside a rise that we refuse."
        ),
    ),
    Divergence(
        pattern="pat_hanging_man",
        talib_function="CDLHANGINGMAN",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "Same shape as the hammer with §3's uptrend instead. §7.1.8 records the sources "
            "disagreeing on confirmation — Morris grades it `No`, Nison writes that a hanging "
            "man should be confirmed — and decision C took Nison, so our `_confirm` exists here "
            "and is measured against the body's low as §5.5 specifies."
        ),
    ),
    Divergence(
        pattern="pat_inverted_hammer",
        talib_function="CDLINVERTEDHAMMER",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§7.1.9 dropped Morris's 'usually no more than two times' upper bound on the upper "
            "shadow, reading 'usually' as a tendency rather than a requirement. That reading is "
            "why no pattern in §7 uses an upper-bound shadow comparison, and it widens this "
            "pattern relative to any target that enforces the bound."
        ),
    ),
    Divergence(
        pattern="pat_shooting_star",
        talib_function="CDLSHOOTINGSTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.SOURCE_READING,
        ),
        note=(
            "§7.1.10 records the sources splitting on the gap: Morris requires prices to gap "
            "open after an uptrend and Nison's glossary does not. Decision C took the "
            "more-conditioned Morris, which is why this is a two-bar pattern at all and why it "
            "matches strictly less often than a reading without the gap."
        ),
    ),
    Divergence(
        pattern="pat_spinning_top",
        talib_function="CDLSPINNINGTOP",
        causes=(Cause.SOURCE_READING, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "§7.1.11 deliberately does not apply §2.2's short body. Morris writes that the "
            "small body is what the shadow comparison already expresses, so the rule is the two "
            "strict shadow-versus-body inequalities and nothing else; those imply a body under "
            "a third of the range by the same arithmetic §2.2 was derived from. It is the one "
            "pattern whose body size is judged without a §2 scale."
        ),
    ),
    # §7.2 — body-and-shadow shapes.
    Divergence(
        pattern="pat_high_wave",
        talib_function="CDLHIGHWAVE",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.SOURCE_READING,
            Cause.NO_DIRECTION_CLAIMED,
        ),
        note=(
            "§10.2 records that the sources do not separate this from a spinning top — both are "
            "'a small body with long shadows' — so §7.2.1 drew the boundary with §2.2's short "
            "body and §2.4's long shadows. The boundary is ours, and where a target draws it "
            "elsewhere the two patterns trade bars between them."
        ),
    ),
    Divergence(
        pattern="pat_marubozu",
        talib_function="CDLMARUBOZU",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "A shaven bar is §2.1's long body with both of §2.5's shadow ceilings. Ten percent "
            "of the range is a tolerance, not zero, so the strictness of this pattern is exactly "
            "the value decision A chose in §2.5."
        ),
    ),
    Divergence(
        pattern="pat_closing_marubozu",
        talib_function="CDLCLOSINGMARUBOZU",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "Requires the ceiling only on the shadow the close sits against, so it inherits "
            "§2.5's chosen ten percent on one side while the other side is unconstrained."
        ),
    ),
    Divergence(
        pattern="pat_belt_hold",
        talib_function="CDLBELTHOLD",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.2 lists this among the four patterns whose bullish and bearish forms are not "
            "mirror images in the sources: the close condition appears only on the bullish "
            "side. The asymmetry is the sources' and the standard kept it, so an implementation "
            "that mirrors the two forms disagrees with us on one side only."
        ),
    ),
    Divergence(
        pattern="pat_long_line",
        talib_function="CDLLONGLINE",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "Nothing but §2.1: a body over half its bar's range. This is the cleanest place to "
            "see decision A's effect on its own, since a target comparing the body to an "
            "average of recent bodies calls a bar long in a quiet stretch that we do not."
        ),
    ),
    Divergence(
        pattern="pat_short_line",
        talib_function="CDLSHORTLINE",
        causes=(Cause.SCALE_DENOMINATOR, Cause.NO_DIRECTION_CLAIMED),
        note=(
            "Nothing but §2.2: a body under a third of its bar's range, a bound §2.2 derives "
            "from Morris's own spinning-top rule rather than assuming it is the complement of "
            "§2.1. The band between the two thresholds belongs to neither, which Morris's text "
            "says it should."
        ),
    ),
    # §7.3 — two-bar patterns and their equivalents.
    Divergence(
        pattern="pat_engulfing",
        talib_function="CDLENGULFING",
        causes=(
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "Reads no §2 scale at all — the rule is §4.1's engulfment plus two colours — so §3's "
            "trend is the only structural narrowing. §10.2 records that Morris's printed rule "
            "reverses which body engulfs which, which would make this a harami if transcribed "
            "faithfully; §7.3.1 corrected it against the same book's other three passages and "
            "Nison."
        ),
    ),
    Divergence(
        pattern="pat_harami",
        talib_function="CDLHARAMI",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Containment is structural but the first bar must be §2.1-long and the second "
            "§2.2-short, so both chosen thresholds sit inside the rule. The confirmation grade "
            "differs by direction, `No` bullish and `Required` bearish, and §5.5 computes "
            "`_confirm` only on the graded side."
        ),
    ),
    Divergence(
        pattern="pat_harami_cross",
        talib_function="CDLHARAMICROSS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.1 counts this among the six ambiguous places: the source's word 'range' can "
            "mean the body or the high-low range, and §7.3.3 fixed one reading. The second bar "
            "is a §2.3 doji, so the three-percent tolerance decides how often the cross form "
            "separates from the plain harami."
        ),
    ),
    Divergence(
        pattern="pat_doji_star",
        talib_function="CDLDOJISTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "A §2.1-long body, then a §2.3 doji gapped away from it in the direction the trend "
            "was going. The gap is a body gap under decision D, so a bar whose high-low ranges "
            "overlap can still qualify while a bar whose bodies touch cannot."
        ),
    ),
    Divergence(
        pattern="pat_piercing",
        talib_function="CDLPIERCING",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "The penetration depth is the source's own midpoint of the first body, written into "
            "§7.3.5 rather than exposed as a setting. TA-Lib's counterpart takes no argument "
            "here either, so the divergence is §2.1's long body and §3's downtrend."
        ),
    ),
    Divergence(
        pattern="pat_dark_cloud_cover",
        talib_function="CDLDARKCLOUDCOVER",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "The bearish mirror of piercing, and the one two-bar pattern whose `CDL` function "
            "takes `penetration`. §7.3.6 writes the midpoint into the rule because Nison states "
            "it, so there is no setting of ours for the captured default to correspond to."
        ),
    ),
    Divergence(
        pattern="pat_counterattack",
        talib_function="CDLCOUNTERATTACK",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Two §2.1-long bodies of opposite colour closing at the same price, where 'the same' "
            "is §2.6's `Equal` at three percent of the range. §2.6 records that Morris's much "
            "tighter one-in-a-thousand rule from the matching-high entry was not adopted, "
            "because he elsewhere directs that the doji tolerance be reused for equality."
        ),
        expected_silence=(
            "Investigated against the capture. TA-Lib matched four bars. Rules 2 and 3 refuse on "
            "all four because §2.1 makes a long body more than half of that same bar's range, "
            "while TA-Lib compares the body against an average of recent bodies; a bar with long "
            "shadows is long to TA-Lib and not to us. Rule 5 refuses on three of the four as "
            "well, since §2.6 reads 'the closes are equal' with the doji tolerance of three "
            "percent of the range. Two independent thresholds have to be met at once on two "
            "adjacent bars. Reachable: §7.3.7's matching case holds. "
        ),
    ),
    Divergence(
        pattern="pat_separating_lines",
        talib_function="CDLSEPARATINGLINES",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Two opposite-coloured bodies opening at the same price, so the whole pattern turns "
            "on §2.6's `Equal`. It is one of the four §2.6 names as effectively unmatchable had "
            "the tighter tolerance been chosen."
        ),
    ),
    Divergence(
        pattern="pat_kicking",
        talib_function="CDLKICKING",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Two marubozu of opposite colour with a gap between them, and §10.2 notes it is the "
            "only reversal pattern in Morris's ninety headers that does not require a trend. "
            "§2.8 read the unstated gap as a body gap, which §7.3.9 argues costs little here "
            "because a marubozu's body nearly fills its range."
        ),
    ),
    Divergence(
        pattern="pat_kicking_by_length",
        talib_function="CDLKICKINGBYLENGTH",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.SOURCE_READING,
        ),
        note=(
            "Kicking with the direction taken from the longer of the two candles. §10.1 counts "
            "'the longer side' among the ambiguous places and §7.3.10 read it as body length; "
            "the section also records that a tie is not a match, since inventing a direction "
            "would distort more than declining to report one. The pattern itself is TA-Lib's "
            "own, raised from a remark Morris reports without adopting."
        ),
    ),
    Divergence(
        pattern="pat_homing_pigeon",
        talib_function="CDLHOMINGPIGEON",
        causes=(Cause.SCALE_DENOMINATOR, Cause.PRIOR_TREND),
        note=(
            "A harami in one colour: a §2.1-long body containing a §2.2-short one, both black, "
            "after a downtrend. Graded `No` for confirmation, so §5.5 leaves `_confirm` at zero "
            "for every bar rather than computing a follow-up nobody asked for."
        ),
    ),
    Divergence(
        pattern="pat_matching_low",
        talib_function="CDLMATCHINGLOW",
        causes=(Cause.SCALE_DENOMINATOR, Cause.PRIOR_TREND),
        note=(
            "Two black bodies closing at the same price, again on §2.6's `Equal`. §2.6 records "
            "that this is the very entry Morris attaches his one-in-a-thousand tolerance to and "
            "that the standard did not generalise it."
        ),
    ),
    Divergence(
        pattern="pat_in_neck",
        talib_function="CDLINNECK",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.2 records that Nison defines thrusting only relatively — 'stronger than the "
            "in-neck pattern' — so neither line has a boundary until one is drawn. §7.3.13 drew "
            "it with §2.6's `Equal`, and §10.2 also lists the length requirement appearing on "
            "the bullish side only as one of the four genuine asymmetries."
        ),
    ),
    Divergence(
        pattern="pat_on_neck",
        talib_function="CDLONNECK",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "The second close meets the first bar's low, which is §2.6's `Equal` again, after a "
            "§2.1-long body. Graded `Required` bearish and `No` bullish, so `_confirm` exists on "
            "one side only."
        ),
    ),
    Divergence(
        pattern="pat_thrusting",
        talib_function="CDLTHRUSTING",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "The other half of the in-neck boundary §10.2 describes. Where the close lands "
            "between the first body's low and its midpoint decides which of the two patterns "
            "matches, so the two are complementary by construction and a target that sets the "
            "boundary elsewhere moves bars between them rather than losing them."
        ),
    ),
    Divergence(
        pattern="pat_stick_sandwich",
        talib_function="CDLSTICKSANDWICH",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "Two closes equal under §2.6 with an opposite-coloured bar between them. §10.2 lists "
            "it among the four asymmetric patterns: the bullish and bearish forms differ in "
            "structure and not merely in sign, so mirroring one to obtain the other produces a "
            "rule the sources do not state."
        ),
    ),
    # §7.4 — three-bar patterns.
    Divergence(
        pattern="pat_morning_star",
        talib_function="CDLMORNINGSTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "A §2.1-long body, a §2.2-short star gapped away, then a close back past the first "
            "body's midpoint. The midpoint is the source's and is written into §7.4.1, while "
            "the `CDL` function exposes the same depth as `penetration`; the captured default is "
            "recorded so a disagreement can be attributed, not so the rule can be retuned."
        ),
    ),
    Divergence(
        pattern="pat_evening_star",
        talib_function="CDLEVENINGSTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "The bearish mirror of the morning star and it inherits every one of its causes, "
            "including the fixed penetration depth."
        ),
    ),
    Divergence(
        pattern="pat_morning_doji_star",
        talib_function="CDLMORNINGDOJISTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "The morning star with §2.3's doji in the star position, so the three-percent "
            "tolerance decides how often this separates from the plain form. Requiring both a "
            "doji and a body gap makes it markedly rarer than its parent."
        ),
    ),
    Divergence(
        pattern="pat_evening_doji_star",
        talib_function="CDLEVENINGDOJISTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "The bearish mirror of the morning doji star, with the same doji tolerance and the "
            "same fixed penetration depth."
        ),
    ),
    Divergence(
        pattern="pat_abandoned_baby",
        talib_function="CDLABANDONEDBABY",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "The strictest gap requirement in the catalog: a doji isolated by a gap on both "
            "sides. Decision D accepted that a market trading around the clock produces these "
            "rarely rather than relaxing the gap, and §7.4.5 says so in place."
        ),
    ),
    Divergence(
        pattern="pat_tri_star",
        talib_function="CDLTRISTAR",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Three consecutive §2.3 doji with gaps between them, one of the five §2.8 read as "
            "body gaps. Three doji in a row is a compound rarity: whatever the tolerance, its "
            "third power governs how often this can appear at all."
        ),
        expected_silence=(
            "Investigated against the capture. TA-Lib matched nine bars and rule 2 refuses on all "
            "nine: not one of the three bars is a doji under §2.3's Body <= 0.03 * Range. TA- "
            "Lib's BodyDoji is a fraction of an average of recent ranges and is far looser, so it "
            "calls bars doji that carry several percent of their own range in body. Decision A "
            "fixed our figure from Morris's one-to-three percent rather than from TA-Lib's "
            "settings table, and requiring it of three consecutive bars cubes the rarity. The gap "
            "requirement refused only two of the nine, so the doji threshold is the whole story. "
            "Reachable: §7.4.6's matching case holds. "
        ),
    ),
    Divergence(
        pattern="pat_two_crows",
        talib_function="CDL2CROWS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "A §2.1-long white body, a black body gapped above it, then a black body closing "
            "inside the first. The gap is a body gap under decision D."
        ),
    ),
    Divergence(
        pattern="pat_upside_gap_two_crows",
        talib_function="CDLUPSIDEGAP2CROWS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Two crows with the additional requirement that the second black body engulf the "
            "first and the gap survive to the third bar, so it is strictly narrower than the "
            "pattern above and both are reported separately."
        ),
        expected_silence=(
            "Investigated against the capture. TA-Lib matched exactly one bar in four thousand, "
            "and on it rule 2 refuses: the first day's white body is not long under §2.1's same- "
            "bar denominator. One bar is too little to say anything about frequency, and the "
            "pattern is rare in TA-Lib's own reading too. Reachable: §7.4.8's matching case "
            "holds. "
        ),
    ),
    Divergence(
        pattern="pat_three_white_soldiers",
        talib_function="CDL3WHITESOLDIERS",
        causes=(Cause.SCALE_DENOMINATOR, Cause.PRIOR_TREND),
        note=(
            "Three consecutive §2.1-long white bodies each closing near its high under §2.5. "
            "Requiring three long bodies in a row makes this one of the places decision A's "
            "denominator matters most: a target measuring against recent bodies calls three "
            "ordinary bars long in a quiet stretch where §2.1 calls none of them long."
        ),
    ),
    Divergence(
        pattern="pat_three_black_crows",
        talib_function="CDL3BLACKCROWS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "The bearish mirror of the soldiers, with the same three-long-bodies-in-a-row "
            "sensitivity to §2.1 and §2.5."
        ),
    ),
    Divergence(
        pattern="pat_identical_three_crows",
        talib_function="CDLIDENTICAL3CROWS",
        causes=(Cause.SCALE_DENOMINATOR, Cause.PRIOR_TREND),
        note=(
            "The crows with each open equal to the previous close under §2.6. Adding an equality "
            "to three consecutive long bodies compounds two chosen values, and §2.6 names this "
            "pattern as one that would effectively never match under the tighter tolerance it "
            "declined."
        ),
    ),
    Divergence(
        pattern="pat_advance_block",
        talib_function="CDLADVANCEBLOCK",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Three white bodies that weaken, with §2.4's long upper shadows appearing on the "
            "later bars. The weakening is expressed as body comparisons between the bars rather "
            "than through a §2 scale, so the shadow threshold is the main chosen value here."
        ),
        expected_silence=(
            "Investigated against the capture. TA-Lib matched twenty bars, and on every one of "
            "them rule 4 is what refuses. §2.4 measures a long upper shadow as at least twice the "
            "body, while TA-Lib's ShadowLong is a fraction of an average of recent ranges, so on "
            "a bar with an ordinary body the two readings are nowhere near each other. §7.4.12 "
            "also drops any length requirement from rule 2, which leaves the three white bodies "
            "free to be large, and a large body is exactly what makes a body-relative shadow test "
            "hard to pass. The trend gate refused eight of the twenty as well. The section is "
            "reachable: its own matching case in test_pattern_three_candle.py holds, so this is "
            "strictness against neutral data rather than a rule no bar can satisfy. "
        ),
    ),
    Divergence(
        pattern="pat_stalled_pattern",
        talib_function="CDLSTALLEDPATTERN",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Two §2.1-long white bodies then a §2.2-short one riding near the previous close "
            "under §2.6's `Near`. Three chosen values decide it, which makes it one of the more "
            "sensitive entries in the table."
        ),
    ),
    Divergence(
        pattern="pat_three_stars_in_the_south",
        talib_function="CDL3STARSINSOUTH",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.1 counts this among the ambiguous places: the source's 'range' had to be read "
            "one way, and §7.4.14 closed it. The section is also one of the two an earlier "
            "arithmetic sweep found unsatisfiable as first written, which is exactly the failure "
            "mode this comparison exists to catch a second time from outside."
        ),
    ),
    Divergence(
        pattern="pat_three_inside",
        talib_function="CDL3INSIDE",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
        ),
        note=(
            "Inherits the harami's rules whole, including its §2.1 and §2.2 thresholds and its "
            "trend, and adds a third close beyond the second. Morris invented this pattern to "
            "improve the harami, and §7.4.16 quotes him refusing to let a confirmation pattern "
            "be looser than the pattern under it."
        ),
    ),
    Divergence(
        pattern="pat_three_outside",
        talib_function="CDL3OUTSIDE",
        causes=(Cause.PRIOR_TREND, Cause.SEPARATE_CONFIRMATION_KEY),
        note=(
            "Inherits the engulfing rules whole and so, like engulfing, reads no §2 scale. §3's "
            "trend and §5's confirmation key are the entire divergence, which makes this the "
            "cleanest place to observe the trend gate's effect with no threshold mixed in."
        ),
    ),
    Divergence(
        pattern="pat_unique_three_river",
        talib_function="CDLUNIQUE3RIVER",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.1 counts the source's 'below' among the six ambiguous places and §7.4.17 fixed "
            "one reading of it. The containment is structural but the first bar is §2.1-long and "
            "the third §2.2-short."
        ),
    ),
    Divergence(
        pattern="pat_concealing_baby_swallow",
        talib_function="CDLCONCEALBABYSWALL",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Four black bars with a §2.4 long upper shadow on the third and a gap §2.8 read as a "
            "body gap. Graded `No`, so no `_confirm` is computed. Four constrained bars in "
            "sequence make it among the rarest entries in the catalog."
        ),
    ),
    # §7.5 — four bars and up, and the gap-continuation family.
    Divergence(
        pattern="pat_three_line_strike",
        talib_function="CDL3LINESTRIKE",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.2 lists it among the four asymmetric patterns: the fourth bar is judged against "
            "the open in one direction and the high in the other. That is the sources' "
            "asymmetry, and an implementation that mirrors the bullish form to get the bearish "
            "one will disagree with us on one side while agreeing on the other."
        ),
    ),
    Divergence(
        pattern="pat_breakaway",
        talib_function="CDLBREAKAWAY",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Five bars: a §2.1-long body, a gap, three bars continuing, then a close back into "
            "the gap. The gap must survive across the middle of the window, so decision D's "
            "body-gap reading governs the whole pattern rather than one bar pair."
        ),
    ),
    Divergence(
        pattern="pat_ladder_bottom",
        talib_function="CDLLADDERBOTTOM",
        causes=(Cause.SCALE_DENOMINATOR, Cause.PRIOR_TREND),
        note=(
            "Five bars, and the only place in §7 where a §2 scale is used negated: rule 3 asks "
            "for a bar that does *not* have a very short upper shadow. §2.7 records that a "
            "degenerate bar must be excluded before the scales are read precisely because a "
            "false return would satisfy a negated rule instead of failing it."
        ),
        expected_silence=(
            "Investigated against the capture. TA-Lib matched two bars and two of our "
            "requirements refuse on both. First the trend: decision B gates this section on §3's "
            "ten-period average while TA-Lib judges shape alone, so it can report a ladder bottom "
            "with no decline behind it. Second rule 2, which wants three long black bodies in a "
            "row under §2.1's same-bar denominator. Two bars is thin evidence either way, and the "
            "section is reachable: §7.5.3's matching case holds. "
        ),
    ),
    Divergence(
        pattern="pat_mat_hold",
        talib_function="CDLMATHOLD",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
            Cause.THRESHOLD_IS_NOT_A_PARAMETER,
        ),
        note=(
            "A five-bar continuation with a gap and three §2.2-short bars holding above the "
            "first body. Its `CDL` function takes `penetration`; §7.5.4 writes the depth into "
            "the rule from the source, so the captured default has no counterpart of ours to "
            "align with."
        ),
    ),
    Divergence(
        pattern="pat_rise_fall_three_methods",
        talib_function="CDLRISEFALL3METHODS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.SOURCE_READING,
        ),
        note=(
            "§10.1 records two of the six ambiguous places here at once: how many small candles "
            "the middle may hold and what a 'strong day' is. Nison's range of two to five was "
            "adopted and the unbounded reading rejected, which is what makes the window finite "
            "at four to seven bars. A target that fixes the window at one length can only agree "
            "on instances of that length."
        ),
    ),
    Divergence(
        pattern="pat_gap_side_by_side_white",
        talib_function="CDLGAPSIDESIDEWHITE",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Two white bodies of similar size opening at the same price after a gap, so it "
            "depends on §2.6's `Equal` and on `SimilarBody`, whose half-of-the-larger rule "
            "decision A set because no source gives a number for 'about the same size'. §2.8 "
            "also read this pattern's gap as a body gap."
        ),
    ),
    Divergence(
        pattern="pat_tasuki_gap",
        talib_function="CDLTASUKIGAP",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "The size condition is Nison's own — the review record notes it was briefly "
            "mistaken for something TA-Lib added — and §2.6's `SimilarBody` is our number for "
            "it. The gap must survive the third bar, which decision D keeps as a body gap."
        ),
    ),
    Divergence(
        pattern="pat_gap_three_methods",
        talib_function="CDLXSIDEGAP3METHODS",
        causes=(
            Cause.SCALE_DENOMINATOR,
            Cause.PRIOR_TREND,
            Cause.SEPARATE_CONFIRMATION_KEY,
            Cause.GAP_AS_THE_SOURCE_DEFINED_IT,
        ),
        note=(
            "Two §2.1-long bodies separated by a gap and a third closing into it. The upside "
            "form is graded `No` and the downside `Required`, so `_confirm` is computed on one "
            "side only, as §5.5 specifies for direction-dependent grades."
        ),
    ),
    Divergence(
        pattern="pat_hikkake",
        talib_function="CDLHIKKAKE",
        causes=(Cause.SEPARATE_CONFIRMATION_KEY,),
        note=(
            "Not a candlestick pattern at all: Chesler works from highs and lows and states that "
            "the open-to-close body is ignored, so no §2 scale and no §3 trend apply. The "
            "divergence is entirely §5.4's placement of confirmation. Chesler gives both the "
            "content and a three-bar deadline, and the confirming bar is a later bar carrying "
            "`_confirm` alone, where the `CDL` function reports the confirmation by returning a "
            "magnitude of 200 on that bar."
        ),
    ),
    Divergence(
        pattern="pat_hikkake_modified",
        talib_function="CDLHIKKAKEMOD",
        causes=(Cause.SEPARATE_CONFIRMATION_KEY,),
        note=(
            "The basic pattern plus two requirements on the bar before the inside bar, one of "
            "which is an exact equality: the context bar closes at the very low of its range for "
            "the bullish form. §7.5.10 refuses to soften that into a near-equality, quoting "
            "Chesler's 'must', and records that the variant is therefore far rarer than the "
            "basic one."
        ),
        expected_silence=(
            "§7.5.10 predicted this before any comparison was run. Rule 2 demands the context "
            "bar's close equal its low exactly, with no tolerance, and rule 3 demands that bar's "
            "range be strictly smaller than its predecessor's, on top of the whole basic hikkake "
            "setup. On the comparison series the conjunction does not occur once in four "
            "thousand bars, and the section states that lowering the frequency is the accepted "
            "price of not altering the source. A tolerance here would be adopting TA-Lib's "
            "reading, which §10.3 forbids."
        ),
    ),
)

DIVERGENCES: Mapping[str, Divergence] = MappingProxyType({entry.pattern: entry for entry in _TABLE})

CAUSE_COVERAGE: Mapping[Cause, int] = MappingProxyType(
    {
        Cause.SCALE_DENOMINATOR: 56,
        Cause.PRIOR_TREND: 45,
        Cause.SEPARATE_CONFIRMATION_KEY: 43,
        Cause.GAP_AS_THE_SOURCE_DEFINED_IT: 18,
        Cause.SOURCE_READING: 16,
        Cause.NO_DIRECTION_CLAIMED: 9,
        Cause.THRESHOLD_IS_NOT_A_PARAMETER: 7,
    }
)
"""How many patterns each cause is expected to cover.

The same numbers are written into the `Cause` members' own docstrings, where prose can go
stale without anything noticing. Restating them once as data lets the suite compare the
claim against the table, so adding a cause to a row and forgetting the sentence that counts
it fails instead of leaving two answers in the file.
"""

TALIB_FUNCTIONS: Mapping[str, str] = MappingProxyType(
    {entry.pattern: entry.talib_function for entry in _TABLE}
)
"""Which `CDL` function each pattern is compared against.

The generator reads this to decide what to call, so the mapping is stated once. §7's
section headings are where each pair comes from.
"""

PENETRATION_FUNCTIONS: frozenset[str] = frozenset(
    entry.talib_function for entry in _TABLE if Cause.THRESHOLD_IS_NOT_A_PARAMETER in entry.causes
)
"""The `CDL` functions this table claims take a `penetration` argument.

Claimed here and checked against the capture rather than asserted: once
`talib_signals.FUNCTION_PARAMETERS` exists, the suite compares the two, so a wrong claim
about the library's surface fails instead of sitting in a comment.
"""


def _reject_a_pattern_listed_twice() -> None:
    """Refuse the same pattern appearing in two rows of the table.

    Building the mapping above would keep only the later row, so a duplicated pattern
    would silently discard whichever set of causes was written first.
    """
    seen: set[str] = set()
    duplicated: list[str] = []
    for entry in _TABLE:
        if entry.pattern in seen:
            duplicated.append(entry.pattern)
        seen.add(entry.pattern)
    if duplicated:
        raise ValueError(f"the divergence table lists twice: {sorted(set(duplicated))}")


def _reject_a_function_listed_twice() -> None:
    """Refuse two patterns compared against the same `CDL` function.

    The catalog is one-to-one with TA-Lib's by construction — §10.1 records that as the
    reason the scope is sixty-one — so a repeated function name means a row was copied
    and its target not updated.
    """
    counted: dict[str, str] = {}
    collisions = []
    for entry in _TABLE:
        owner = counted.setdefault(entry.talib_function, entry.pattern)
        if owner != entry.pattern:
            collisions.append(f"{entry.talib_function} is claimed by {owner} and {entry.pattern}")
    if collisions:
        raise ValueError("; ".join(collisions))


_reject_a_pattern_listed_twice()
_reject_a_function_listed_twice()
