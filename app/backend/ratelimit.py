import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(self, max_calls: int, window_s: float, clock: Callable[[], float] = time.monotonic):
        self.max_calls = max_calls
        self.window_s = window_s
        self.clock = clock
        self._calls: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        now = self.clock()
        calls = self._calls[key]
        while calls and now - calls[0] >= self.window_s:
            calls.popleft()
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True
