"""Track conditional market-breadth indicators awaiting input channels."""

FOLLOW_UP_INDICATORS = (
    "McClellan Oscillator",
    "McClellan Summation Index",
    "TRIN/Arms",
)

REQUIRED_INPUTS = {
    "McClellan Oscillator": ("advances", "declines"),
    "McClellan Summation Index": ("advances", "declines"),
    "TRIN/Arms": ("advances", "declines", "advance_volume", "decline_volume"),
}
