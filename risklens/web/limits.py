"""Request size caps and in-process rate limiting for the web UI.

RiskLens serves on 127.0.0.1 and is not deployed publicly, so this is
defensive posture rather than a load-shedding mechanism: the point is that
an oversized or runaway POST gets a clear 413/429 instead of being parsed
into memory or re-scored in a loop. Only mutating methods are guarded --
the marketing pages, questionnaire and static assets are untouched.

Deliberately dependency-light. The rate limiter is a per-client sliding
window held in a plain dict in this process, which is correct for a
single-user local tool and needs no Redis or external store; it resets
whenever the server restarts, and that is fine.

Limits are read from the environment on every request (mirroring how
`history.py` and `decisions.py` resolve their storage dirs) so a test or a
local run can override them without reimporting the app:

* `RISKLENS_MAX_REQUEST_BYTES`   -- body cap, default 512 KB; 0 disables
* `RISKLENS_RATE_LIMIT_REQUESTS` -- mutating requests per window per client,
                                    default 120; 0 disables
* `RISKLENS_RATE_LIMIT_WINDOW`   -- window length in seconds, default 60

Defaults are generous on purpose: 120 form submissions a minute is far
more than a human filling out a questionnaire will ever produce, so normal
use is never throttled. `reset_rate_limiter()` clears the shared state and
exists for per-test isolation.
"""

from __future__ import annotations

import os
import time
from collections import deque

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_REQUEST_BYTES = 512 * 1024
DEFAULT_RATE_LIMIT_REQUESTS = 120
DEFAULT_RATE_LIMIT_WINDOW = 60.0

# methods that can't carry a form submission, so aren't worth guarding
UNGUARDED_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

# ceiling on how many distinct clients the limiter tracks before it drops
# the ones whose windows have already expired
MAX_TRACKED_CLIENTS = 1024

TOO_LARGE_MESSAGE = (
    "Request body too large. The assessment form does not need a payload this "
    "big; if this was a real submission, trim the note fields and resubmit."
)
TOO_MANY_MESSAGE = (
    "Too many requests. RiskLens runs as a local single-user tool and rate "
    "limits form submissions as a precaution; wait a moment and resubmit."
)


def _int_env(name: str, default: int) -> int:
    """Non-negative integer from the environment, falling back to the default
    for a blank, unparsable or negative value rather than raising."""
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _float_env(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def max_request_bytes() -> int:
    return _int_env("RISKLENS_MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES)


def rate_limit_requests() -> int:
    return _int_env("RISKLENS_RATE_LIMIT_REQUESTS", DEFAULT_RATE_LIMIT_REQUESTS)


def rate_limit_window() -> float:
    return _float_env("RISKLENS_RATE_LIMIT_WINDOW", DEFAULT_RATE_LIMIT_WINDOW)


class _BodyTooLarge(Exception):
    """Raised by the counting receive wrapper when a body with no declared
    Content-Length streams past the cap."""


class RateLimiter:
    """Sliding-window request counter keyed by client identifier.

    `check()` takes the limit, window and current time as arguments instead
    of reading them itself, which keeps the window logic directly testable
    with an injected clock.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}

    def check(self, key: str, *, limit: int, window: float, now: float) -> float | None:
        """Records a request and returns None if it is allowed, or the seconds
        until the oldest hit falls out of the window if the limit is reached."""
        if limit <= 0:
            return None

        hits = self._hits.setdefault(key, deque())
        cutoff = now - window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= limit:
            return max(0.0, hits[0] + window - now)

        if len(self._hits) > MAX_TRACKED_CLIENTS:
            self._drop_expired(cutoff)
        hits.append(now)
        return None

    def _drop_expired(self, cutoff: float) -> None:
        for tracked, hits in list(self._hits.items()):
            if not hits or hits[-1] <= cutoff:
                del self._hits[tracked]

    def reset(self) -> None:
        self._hits.clear()


_limiter = RateLimiter()


def reset_rate_limiter() -> None:
    """Clears the shared limiter. Used by the test suite so one test's
    submissions never count against another's."""
    _limiter.reset()


def _client_key(scope: Scope) -> str:
    client = scope.get("client")
    return client[0] if client else "unknown"


def _declared_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


class RequestGuardMiddleware:
    """Rejects oversized bodies with 413 and over-limit clients with 429.

    Pure ASGI rather than `BaseHTTPMiddleware` so the request body can be
    counted as it streams without buffering it twice.
    """

    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter if limiter is not None else _limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in UNGUARDED_METHODS:
            await self.app(scope, receive, send)
            return

        cap = max_request_bytes()
        declared = _declared_length(scope)
        if cap and declared is not None and declared > cap:
            await PlainTextResponse(TOO_LARGE_MESSAGE, status_code=413)(scope, receive, send)
            return

        retry_after = self.limiter.check(
            _client_key(scope),
            limit=rate_limit_requests(),
            window=rate_limit_window(),
            now=time.monotonic(),
        )
        if retry_after is not None:
            response = PlainTextResponse(
                TOO_MANY_MESSAGE,
                status_code=429,
                headers={"Retry-After": str(max(1, int(retry_after) + 1))},
            )
            await response(scope, receive, send)
            return

        # a chunked body declares no length, so cap it as it arrives
        guarded_receive = receive if not cap else _counting_receive(receive, cap)
        started = False

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, guarded_receive, guarded_send)
        except _BodyTooLarge:
            if started:  # response already on the wire, nothing useful left to say
                raise
            await PlainTextResponse(TOO_LARGE_MESSAGE, status_code=413)(scope, receive, send)


def _counting_receive(receive: Receive, cap: int) -> Receive:
    seen = 0

    async def counted() -> Message:
        nonlocal seen
        message = await receive()
        if message["type"] == "http.request":
            seen += len(message.get("body", b""))
            if seen > cap:
                raise _BodyTooLarge
        return message

    return counted
