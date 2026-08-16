"""Base client for all scholarly-literature API clients.

Mirrors `biosciences_mcp.clients.base` (ADR-001 Section 2: strict async httpx with
connection pooling; ADR-006: single-writer clients/ package so parallel per-connector
work never shares a file).

Status: FROZEN ONCE CONNECTOR WORK BEGINS. The freeze exists so that parallel
per-connector implementation never shares a write (ADR-006). No connector exists yet, so
AGE-576 lands the resilience layer here first, deliberately: every connector inherits it,
and adding it after connectors are in flight is exactly the shared write the freeze
forbids.

Two deliberate additions over the biosciences base:

1. The polite-pool contact header. Crossref and OpenAlex both grant materially better
   throughput when a contact address is supplied in the User-Agent, and the Layer-1 probe
   ran both keyless at ~6.6 req/s with zero 429s on that basis.
2. Runtime rate discipline (AGE-576). Limits are LEARNED FROM RESPONSE HEADERS rather
   than hardcoded. The constitution's Required Patterns mandate reading `x-rate-limit-*`
   at runtime "rather than hardcoding", and `03-crossref.md` §8 records the observed
   3 req/s as "runtime state, not a documented contractual guarantee — Crossref can and
   does vary polite-pool allowances."
"""

import asyncio
import datetime
import email.utils
import os
import random
import re
from typing import Any

import httpx

_CONTACT = os.environ.get("PSYCHOLOGY_MCP_CONTACT_EMAIL", "").strip()

USER_AGENT = "psychology-mcp/0.1.0 (+https://github.com/open-biosciences)" + (
    f" mailto:{_CONTACT}" if _CONTACT else ""
)

# Header names are MEASURED, not assumed. Every Crossref response in the Layer-1 probe
# carried these three (03-crossref.md §1, verified live 2026-08-15).
_H_RATE_LIMIT = "x-rate-limit-limit"
_H_RATE_INTERVAL = "x-rate-limit-interval"
_H_CONCURRENCY = "x-concurrency-limit"

_INTERVAL_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


def parse_interval(raw: str) -> float | None:
    """Parse an interval header such as `1s`, `500ms`, `2m` into seconds.

    Crossref sends `x-rate-limit-interval: 1s` — a STRING with a unit suffix, not a
    number. Returns None when the value cannot be parsed, so an unrecognised format
    leaves the current posture untouched rather than widening it.
    """
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)?\s*", raw or "")
    if not match:
        return None
    value = float(match.group(1))
    return value * _INTERVAL_UNITS[match.group(2) or "s"]


def parse_retry_after(raw: str) -> float | None:
    """Parse a `Retry-After` header, which may be seconds OR an HTTP date (RFC 9110)."""
    if not raw:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    try:
        parsed = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    now = datetime.datetime.now(datetime.UTC) if parsed.tzinfo else datetime.datetime.now()
    return max(0.0, (parsed - now).total_seconds())


class AdaptiveGate:
    """Admission control for outbound requests, adjustable at runtime.

    Enforces two independent limits:

    - `concurrency` — how many requests may be in flight at once (`x-concurrency-limit`).
    - `min_interval` — minimum spacing between request STARTS, derived from
      `x-rate-limit-limit` / `x-rate-limit-interval`.

    Built on a Condition rather than a Semaphore because the limits change: a semaphore's
    size is fixed at construction, and the whole point of AGE-576 is that the server tells
    us the limit after the first response. Raising or lowering `concurrency` here takes
    effect on the next admission.
    """

    def __init__(self, min_interval: float, concurrency: int) -> None:
        if concurrency < 1:
            raise ValueError("concurrency must be >= 1")
        if min_interval < 0:
            raise ValueError("min_interval must be >= 0")
        self._min_interval = min_interval
        self._concurrency = concurrency
        self._in_flight = 0
        self._last_start: float | None = None
        self._cond = asyncio.Condition()

    @property
    def min_interval(self) -> float:
        return self._min_interval

    @property
    def concurrency(self) -> int:
        return self._concurrency

    async def observe(self, headers: httpx.Headers) -> None:
        """Adopt whatever rate posture the server just declared.

        Absent headers leave the current posture unchanged — silence is not permission to
        speed up. This mirrors the constitution's rule that an absent signal is not a
        negative signal.
        """
        rate = headers.get(_H_RATE_LIMIT)
        interval = headers.get(_H_RATE_INTERVAL)
        concurrency = headers.get(_H_CONCURRENCY)

        async with self._cond:
            if rate and interval:
                try:
                    permitted = int(rate)
                except ValueError:
                    permitted = 0
                window = parse_interval(interval)
                if permitted > 0 and window is not None and window > 0:
                    self._min_interval = window / permitted
            if concurrency:
                try:
                    limit = int(concurrency)
                except ValueError:
                    limit = 0
                if limit > 0 and limit != self._concurrency:
                    self._concurrency = limit
                    self._cond.notify_all()

    async def __aenter__(self) -> "AdaptiveGate":
        async with self._cond:
            while self._in_flight >= self._concurrency:
                await self._cond.wait()
            if self._min_interval > 0 and self._last_start is not None:
                elapsed = asyncio.get_running_loop().time() - self._last_start
                if elapsed < self._min_interval:
                    # Sleeping while holding the lock is deliberate: request STARTS must
                    # be spaced, so no other caller may be admitted during the gap.
                    await asyncio.sleep(self._min_interval - elapsed)
            self._last_start = asyncio.get_running_loop().time()
            self._in_flight += 1
        return self

    async def __aexit__(self, *_exc: object) -> None:
        async with self._cond:
            self._in_flight -= 1
            self._cond.notify()


class LiteratureClient:
    """Base async HTTP client for scholarly literature APIs.

    Provides connection pooling, runtime-adaptive rate discipline, and retry with
    exponential backoff plus full jitter on throttling and transient server errors.

    Subclasses supply a STARTING posture only. The constructor defaults are deliberately
    conservative because the Layer-1 probe measured connector limits differing by two
    orders of magnitude, so a shared default would be wrong for most; the server's own
    headers supersede whatever is passed here on the first response that carries them.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_connections: int = 10,
        min_interval: float = 0.5,
        concurrency: int = 2,
        max_attempts: int = 4,
        backoff_base: float = 0.5,
        backoff_cap: float = 30.0,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the API.
            timeout: Read timeout in seconds.
            max_connections: Maximum pooled connections.
            min_interval: Starting minimum spacing between request starts, in seconds.
            concurrency: Starting maximum in-flight requests.
            max_attempts: Total attempts per request, including the first.
            backoff_base: Base delay for exponential backoff, in seconds.
            backoff_cap: Upper bound on a single backoff sleep, in seconds.
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._max_connections = max_connections
        self._max_attempts = max_attempts
        self._backoff_base = backoff_base
        self._backoff_cap = backoff_cap
        self._gate = AdaptiveGate(min_interval=min_interval, concurrency=concurrency)

    @property
    def gate(self) -> AdaptiveGate:
        """The admission gate, exposed so tests and subclasses can inspect the posture."""
        return self._gate

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_connections,
            )
            timeout = httpx.Timeout(
                connect=5.0,
                read=self._timeout,
                write=10.0,
                pool=5.0,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                limits=limits,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
        return self._client

    def _backoff_delay(self, attempt: int, retry_after: float | None) -> float:
        """Full-jitter exponential backoff, with `Retry-After` taking precedence.

        Full jitter (`uniform(0, base * 2**n)`) rather than equal jitter: when several
        agent sessions are throttled by the same upstream at the same moment, a
        deterministic or narrowly-jittered delay reconverges them into a second
        simultaneous burst.
        """
        if retry_after is not None:
            return min(retry_after, self._backoff_cap)
        ceiling = min(self._backoff_base * (2**attempt), self._backoff_cap)
        # Jitter only - not a cryptographic use.
        return random.uniform(0, ceiling)

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a JSON document, honouring runtime rate limits and retrying transients.

        Retries on 429 and 5xx (see RETRYABLE_STATUS) and on transport errors. A 4xx that
        is not 429 is not retried — it will not become correct by being repeated.

        Raises:
            httpx.HTTPStatusError: on a non-2xx response after attempts are exhausted.
            httpx.TransportError: on a transport failure after attempts are exhausted.
        """
        client = await self._get_client()
        last_exc: Exception | None = None

        for attempt in range(self._max_attempts):
            try:
                async with self._gate:
                    response = await client.get(path, params=params)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt == self._max_attempts - 1:
                    raise
                await asyncio.sleep(self._backoff_delay(attempt, None))
                continue

            # Adopt the declared posture even on an error response — a 429 is precisely
            # when the server is most likely to be telling us the real limit.
            await self._gate.observe(response.headers)
            self._on_response(response)

            if response.status_code in RETRYABLE_STATUS and attempt < self._max_attempts - 1:
                retry_after = parse_retry_after(response.headers.get("retry-after", ""))
                await asyncio.sleep(self._backoff_delay(attempt, retry_after))
                continue

            response.raise_for_status()
            return response.json()

        if last_exc is not None:  # pragma: no cover - defensive
            raise last_exc
        raise RuntimeError("unreachable: retry loop exited without result")  # pragma: no cover

    def _on_response(self, response: httpx.Response) -> None:
        """Hook for connector-specific response observation. Default: no-op.

        Exists because rate accounting is not uniform across the roster. The gate handles
        the `x-rate-limit-*` spacing scheme; OpenAlex instead publishes a daily CREDIT
        budget (`x-ratelimit-remaining`), which is a different quantity and must not be
        folded into request spacing.
        """

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
