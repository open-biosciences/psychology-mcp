"""Tests for the resilient base client (AGE-576).

No network. Every upstream is an `httpx.MockTransport`, and every sleep is captured
rather than performed, so the suite asserts on the DELAYS CHOSEN without spending them.

The rules under test come from the constitution's Required Patterns ("read
`x-rate-limit-*` headers at runtime where published, rather than hardcoding") and
Forbidden Patterns ("unbounded concurrency -> 429 loops, IP bans"), and the header names
are the ones measured live in `03-crossref.md` §1.
"""

import asyncio

import httpx
import pytest

from psychology_mcp.clients.base import (
    AdaptiveGate,
    LiteratureClient,
    parse_interval,
    parse_retry_after,
)

pytestmark = pytest.mark.unit


class _Client(LiteratureClient):
    """A LiteratureClient wired to a mock transport instead of the network."""

    def __init__(self, handler, **kwargs):
        super().__init__(base_url="https://example.test", **kwargs)
        self._handler = handler

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                transport=httpx.MockTransport(self._handler),
            )
        return self._client


@pytest.fixture
def captured_sleeps(monkeypatch):
    """Capture asyncio.sleep durations instead of waiting them out."""
    sleeps: list[float] = []
    real_sleep = asyncio.sleep

    async def fake_sleep(delay, *args, **kwargs):
        sleeps.append(delay)
        return await real_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleeps


class TestIntervalParsing:
    """Crossref sends `x-rate-limit-interval: 1s` - a string with a unit, not a number."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("1s", 1.0), ("500ms", 0.5), ("2m", 120.0), ("1h", 3600.0), ("3", 3.0)],
    )
    def test_parses_measured_and_plausible_formats(self, raw, expected):
        assert parse_interval(raw) == pytest.approx(expected)

    @pytest.mark.parametrize("raw", ["", "soon", "1 fortnight", None])
    def test_unparseable_returns_none_rather_than_guessing(self, raw):
        """An unrecognised format must not silently widen the rate posture."""
        assert parse_interval(raw) is None


class TestRetryAfterParsing:
    def test_seconds_form(self):
        assert parse_retry_after("120") == 120.0

    def test_http_date_form_is_supported(self):
        """RFC 9110 permits a date; a client that only handles integers under-waits."""
        future = "Wed, 21 Oct 2099 07:28:00 GMT"
        value = parse_retry_after(future)
        assert value is not None and value > 0

    def test_past_date_clamps_to_zero_not_negative(self):
        assert parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT") == 0.0

    def test_absent_returns_none(self):
        assert parse_retry_after("") is None


class TestPostureIsLearnedNotHardcoded:
    """The constitution forbids hardcoding a connector's limit. Headers win."""

    async def test_adopts_crossref_measured_headers(self):
        gate = AdaptiveGate(min_interval=0.5, concurrency=2)
        await gate.observe(
            httpx.Headers(
                {
                    "x-rate-limit-limit": "3",
                    "x-rate-limit-interval": "1s",
                    "x-concurrency-limit": "3",
                }
            )
        )
        # 3 requests per 1s => one start every 1/3 s.
        assert gate.min_interval == pytest.approx(1 / 3)
        assert gate.concurrency == 3

    async def test_absent_headers_leave_posture_untouched(self):
        """Silence is not permission to speed up."""
        gate = AdaptiveGate(min_interval=2.5, concurrency=1)
        await gate.observe(httpx.Headers({}))
        assert gate.min_interval == 2.5
        assert gate.concurrency == 1

    async def test_a_tightened_limit_is_adopted_not_only_a_loosened_one(self):
        gate = AdaptiveGate(min_interval=0.1, concurrency=10)
        await gate.observe(
            httpx.Headers(
                {
                    "x-rate-limit-limit": "1",
                    "x-rate-limit-interval": "2s",
                    "x-concurrency-limit": "1",
                }
            )
        )
        assert gate.min_interval == pytest.approx(2.0)
        assert gate.concurrency == 1

    async def test_garbage_header_values_do_not_corrupt_the_posture(self):
        gate = AdaptiveGate(min_interval=0.5, concurrency=2)
        await gate.observe(
            httpx.Headers(
                {
                    "x-rate-limit-limit": "many",
                    "x-rate-limit-interval": "soon",
                    "x-concurrency-limit": "-4",
                }
            )
        )
        assert gate.min_interval == 0.5
        assert gate.concurrency == 2

    async def test_posture_is_adopted_from_a_429_response(self, captured_sleeps):
        """A 429 is when the server is most likely stating the real limit."""
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    429,
                    headers={
                        "x-rate-limit-limit": "3",
                        "x-rate-limit-interval": "1s",
                        "x-concurrency-limit": "3",
                    },
                )
            return httpx.Response(200, json={"ok": True})

        client = _Client(handler, min_interval=0.0, concurrency=8)
        assert await client.get_json("/works") == {"ok": True}
        assert client.gate.concurrency == 3
        assert client.gate.min_interval == pytest.approx(1 / 3)
        await client.close()


class TestConcurrencyIsBounded:
    async def test_never_exceeds_the_declared_concurrency_limit(self):
        peak = {"now": 0, "max": 0}

        async def worker(gate):
            async with gate:
                peak["now"] += 1
                peak["max"] = max(peak["max"], peak["now"])
                await asyncio.sleep(0)
                peak["now"] -= 1

        gate = AdaptiveGate(min_interval=0.0, concurrency=3)
        await asyncio.gather(*(worker(gate) for _ in range(20)))
        assert peak["max"] <= 3

    async def test_rejects_a_nonsensical_starting_posture(self):
        with pytest.raises(ValueError):
            AdaptiveGate(min_interval=0.0, concurrency=0)


class TestRetryBehaviour:
    @pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
    async def test_retries_throttling_and_transient_server_errors(
        self, status, captured_sleeps
    ):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(status)
            return httpx.Response(200, json={"recovered": True})

        client = _Client(handler, min_interval=0.0)
        assert await client.get_json("/works") == {"recovered": True}
        assert calls["n"] == 2
        assert len(captured_sleeps) == 1
        await client.close()

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    async def test_does_not_retry_a_client_error(self, status, captured_sleeps):
        """A malformed DOI does not become valid by being asked again."""
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(status)

        client = _Client(handler, min_interval=0.0)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_json("/works/not-a-doi")
        assert calls["n"] == 1
        assert captured_sleeps == []
        await client.close()

    async def test_gives_up_after_max_attempts_and_raises(self, captured_sleeps):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            return httpx.Response(503)

        client = _Client(handler, min_interval=0.0, max_attempts=3)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_json("/works")
        assert calls["n"] == 3
        assert len(captured_sleeps) == 2
        await client.close()

    async def test_retries_transport_errors_then_succeeds(self, captured_sleeps):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, json={"ok": True})

        client = _Client(handler, min_interval=0.0)
        assert await client.get_json("/works") == {"ok": True}
        assert calls["n"] == 2
        await client.close()

    async def test_retry_after_seconds_takes_precedence_over_jitter(self, captured_sleeps):
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"retry-after": "7"})
            return httpx.Response(200, json={"ok": True})

        client = _Client(handler, min_interval=0.0, backoff_cap=30.0)
        await client.get_json("/works")
        assert captured_sleeps == [7.0]
        await client.close()

    async def test_retry_after_is_clamped_by_the_backoff_cap(self, captured_sleeps):
        """A hostile or mistaken upstream must not park an agent for an hour."""
        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"retry-after": "3600"})
            return httpx.Response(200, json={"ok": True})

        client = _Client(handler, min_interval=0.0, backoff_cap=30.0)
        await client.get_json("/works")
        assert captured_sleeps == [30.0]
        await client.close()

    async def test_backoff_grows_and_stays_within_the_cap(self, captured_sleeps):
        def handler(request):
            return httpx.Response(503)

        client = _Client(
            handler, min_interval=0.0, max_attempts=5, backoff_base=1.0, backoff_cap=8.0
        )
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_json("/works")
        assert len(captured_sleeps) == 4
        assert all(0.0 <= d <= 8.0 for d in captured_sleeps)
        await client.close()

    async def test_backoff_is_jittered_not_deterministic(self, captured_sleeps):
        """Identical deterministic delays reconverge throttled sessions into one burst.

        Compares the delay chosen at the SAME attempt index across independent clients.
        Comparing delays across attempts within one client proves nothing — exponential
        growth alone makes those differ even with jitter removed.
        """

        def handler(request):
            return httpx.Response(503)

        first_delays: list[float] = []
        for _ in range(8):
            captured_sleeps.clear()
            client = _Client(
                handler, min_interval=0.0, max_attempts=2, backoff_base=2.0, backoff_cap=60.0
            )
            with pytest.raises(httpx.HTTPStatusError):
                await client.get_json("/works")
            await client.close()
            first_delays.append(captured_sleeps[0])

        assert len(set(first_delays)) > 1, "attempt-0 delay is identical every run: no jitter"


class TestAsyncDiscipline:
    async def test_no_blocking_sleep_is_used(self, monkeypatch, captured_sleeps):
        """Principle I: synchronous blocking calls are forbidden in async contexts."""
        import time as _time

        def explode(_seconds):  # pragma: no cover - only runs on violation
            raise AssertionError("time.sleep() in an async client blocks the event loop")

        monkeypatch.setattr(_time, "sleep", explode)

        calls = {"n": 0}

        def handler(request):
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(429, headers={"retry-after": "1"})
            return httpx.Response(200, json={"ok": True})

        client = _Client(handler, min_interval=0.05)
        assert await client.get_json("/works") == {"ok": True}
        await client.close()
