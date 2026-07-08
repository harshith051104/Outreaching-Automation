"""
Simple in-memory rate limiting middleware.

Limits requests per IP address per minute based on the
RATE_LIMIT_PER_MINUTE setting. Returns 429 Too Many Requests
when the limit is exceeded.
"""

import time
from collections import defaultdict
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.config.settings import settings


class RateLimiter:
    """
    Thread-safe sliding-window rate limiter.

    Tracks request timestamps per client IP and enforces a maximum
    number of requests within a rolling one-minute window.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, client_ip: str) -> bool:
        """Return True if the client is within the rate limit, False otherwise."""
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            self._requests[client_ip] = [
                ts for ts in self._requests[client_ip] if ts > window_start
            ]

            if len(self._requests[client_ip]) >= self.max_requests:
                return False

            self._requests[client_ip].append(now)
            return True

    def get_retry_after(self, client_ip: str) -> int:
        """Return seconds until the client can make another request."""
        with self._lock:
            timestamps = sorted(self._requests.get(client_ip, []))
            if not timestamps:
                return 0
            oldest = timestamps[0]
            return max(1, int(self.window_seconds - (time.time() - oldest)))


_rate_limiter = RateLimiter(
    max_requests=getattr(settings, "RATE_LIMIT_PER_MINUTE", 60),
    window_seconds=60,
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that enforces per-IP rate limiting.

    Skips rate limiting for health checks and tracking endpoints
    (which need to respond quickly without auth).
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json") or path.startswith(
            ("/api/track/open", "/api/track/click")
        ):
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        if not _rate_limiter.is_allowed(client_ip):
            retry_after = _rate_limiter.get_retry_after(client_ip)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please slow down.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        """Extract the real client IP, checking X-Forwarded-For if behind a proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"