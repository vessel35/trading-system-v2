"""Canonical tests for shared wall-clock polling alignment."""

from __future__ import annotations

import inspect

import pytest
from service_commons.polling import seconds_until_next_poll


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (0.0, 2.0),
        (1.25, 0.75),
        (2.0, 60.0),
        (15.0, 47.0),
        (59.5, 2.5),
        (60.0, 2.0),
    ],
)
def test_default_polling_boundaries(now: float, expected: float) -> None:
    assert seconds_until_next_poll(now) == expected


def test_custom_polling_period_boundary() -> None:
    assert (
        seconds_until_next_poll(
            12.0,
            poll_interval_seconds=10,
            poll_buffer_seconds=3,
        )
        == 1.0
    )


@pytest.mark.parametrize(
    ("interval", "buffer", "message"),
    [
        (0, 0, "positive"),
        (60, -1, "within"),
        (60, 60, "within"),
    ],
)
def test_polling_rejects_invalid_configuration(
    interval: int,
    buffer: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        seconds_until_next_poll(
            0.0,
            poll_interval_seconds=interval,
            poll_buffer_seconds=buffer,
        )


def test_polling_signature_and_defaults_are_stable() -> None:
    signature = inspect.signature(seconds_until_next_poll)

    assert tuple(signature.parameters) == (
        "now",
        "poll_interval_seconds",
        "poll_buffer_seconds",
    )
    assert signature.parameters["now"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert signature.parameters["poll_interval_seconds"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["poll_interval_seconds"].default == 60
    assert signature.parameters["poll_buffer_seconds"].kind is inspect.Parameter.KEYWORD_ONLY
    assert signature.parameters["poll_buffer_seconds"].default == 2
