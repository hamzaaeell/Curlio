"""
Token bucket rate limiter to keep Google requests within safe bounds.
Adds random jitter to avoid mechanical request patterns.
"""

import time
import random
import asyncio
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with jitter.

    At 2000 queries/day = ~1.39/min, we use a conservative 2/min max
    with random jitter between requests to look human.
    """

    def __init__(
        self,
        requests_per_minute: float = 2.0,
        jitter_seconds: float = 5.0,
    ):
        """
        Args:
            requests_per_minute: Max sustained request rate
            jitter_seconds:      Max random delay added on top of base interval
        """
        self.min_interval = 60.0 / requests_per_minute  # seconds between requests
        self.jitter = jitter_seconds
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until it's safe to make the next request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            base_wait = self.min_interval - elapsed

            # Add random jitter so requests don't look mechanical
            jitter = random.uniform(0, self.jitter)
            wait = max(0.0, base_wait) + jitter

            if wait > 0:
                logger.debug("Rate limiter waiting %.1fs (base=%.1fs, jitter=%.1fs)", wait, base_wait, jitter)
                await asyncio.sleep(wait)

            self._last_request_time = time.monotonic()


# Global rate limiter instance
# 2 req/min = safe for 2000/day with headroom
rate_limiter = RateLimiter(requests_per_minute=2.0, jitter_seconds=5.0)
