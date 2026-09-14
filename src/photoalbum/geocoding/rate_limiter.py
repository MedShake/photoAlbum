from __future__ import annotations

import time
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        minimum_interval_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if minimum_interval_seconds < 0:
            raise ValueError(
                "Minimum interval cannot be negative."
            )

        self._minimum_interval_seconds = (
            minimum_interval_seconds
        )
        self._clock = clock
        self._sleeper = sleeper
        self._last_request_time: float | None = None

    def wait(self) -> None:
        now = self._clock()

        if self._last_request_time is not None:
            elapsed = now - self._last_request_time

            remaining = (
                self._minimum_interval_seconds - elapsed
            )

            if remaining > 0:
                self._sleeper(remaining)

        self._last_request_time = self._clock()

