import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.core.config import get_settings


class SlidingWindowRateLimiter:
    """In-memory sliding window rate limiter (safe for single-instance/dev and tests)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int = 60) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait before retrying.",
            )
        bucket.append(now)

    def reset(self) -> None:
        self._hits.clear()


rate_limiter = SlidingWindowRateLimiter()


async def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing per-client-IP request rate limits."""
    settings = get_settings()
    client_host = request.client.host if request.client else "unknown"
    rate_limiter.check(
        key=f"ip:{client_host}",
        limit=settings.RATE_LIMIT_REQUESTS_PER_MINUTE,
        window_seconds=60,
    )
