"""Track Ehlers cycle indicators awaiting later registration."""

# §8.2's Center of Gravity Oscillator has left this list: its calculation is a plain
# weighted centroid with no phase pipeline behind it, so it is registered with the
# momentum category rather than waiting here. The three that remain are the ones §12
# holds back for want of the original author's constants.
FOLLOW_UP_INDICATORS = (
    "MAMA/FAMA",
    "Roofing Filter",
    "Sinewave/Instantaneous Trendline",
)
