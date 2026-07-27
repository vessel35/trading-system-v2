"""Wall-clock polling alignment helpers."""

from __future__ import annotations


def seconds_until_next_poll(
    now: float,
    *,
    poll_interval_seconds: int = 60,
    poll_buffer_seconds: int = 2,
) -> float:
    """Align polling to a wall-clock period boundary plus a close buffer."""

    if poll_interval_seconds <= 0:
        raise ValueError("poll interval must be positive")
    if not 0 <= poll_buffer_seconds < poll_interval_seconds:
        raise ValueError("poll buffer must be within the polling interval")
    seconds_into_period = now % poll_interval_seconds
    if seconds_into_period < poll_buffer_seconds:
        return poll_buffer_seconds - seconds_into_period
    return poll_interval_seconds - seconds_into_period + poll_buffer_seconds
