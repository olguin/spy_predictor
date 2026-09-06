"""Deterministic rolling-window pacing for external data requests."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class PacingController:
    def __init__(
        self,
        minimum_spacing_seconds: float,
        maximum_requests: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.minimum_spacing_seconds = minimum_spacing_seconds
        self.maximum_requests = maximum_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self.sleeper = sleeper
        self._request_times: deque[float] = deque()

    def wait(self) -> None:
        while True:
            now = self.clock()
            while (
                self._request_times
                and now - self._request_times[0] >= self.window_seconds
            ):
                self._request_times.popleft()
            waits = [0.0]
            if self._request_times:
                waits.append(
                    self.minimum_spacing_seconds - (now - self._request_times[-1])
                )
            if len(self._request_times) >= self.maximum_requests:
                waits.append(
                    self.window_seconds - (now - self._request_times[0])
                )
            required_wait = max(waits)
            if required_wait <= 0:
                self._request_times.append(self.clock())
                return
            self.sleeper(required_wait)
