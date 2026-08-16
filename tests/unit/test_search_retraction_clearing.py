"""Second-pass retraction clearing on search results (AGE-580).

Exists because of a measured gap: Crossref and OpenAlex rank DISJOINT sets for the same
query, so the first-pass DOI join leaves most Crossref-sourced results with
`retraction_status: unknown`. This suite pins the fix AND the failure mode — the one place
where an optimisation could quietly turn "we did not check" into "it is fine".

No network.
"""

from urllib.parse import unquote

import httpx
import pytest

from psychology_mcp.clients.openalex import MAX_FILTER_VALUES, OpenAlexClient
from psychology_mcp.models.work import ClassificationBasis, RetractionStatus, VenueClass
from psychology_mcp.servers import literature

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_singletons():
    literature._crossref = None
    literature._openalex = None
    yield
    literature._crossref = None
    literature._openalex = None


def _oa_record(doi: str, retracted: bool = False) -> dict:
    return {
        "id": "https://openalex.org/W1",
        "ids": {"openalex": "https://openalex.org/W1", "doi": f"https://doi.org/{doi}"},
        "doi": f"https://doi.org/{doi}",
        "type": "article",
        "is_retracted": retracted,
        "primary_location": {"source": {"type": "journal", "display_name": "J"}},
    }


def _cr_item(doi: str) -> dict:
    return {"DOI": doi, "type": "book-chapter", "title": [f"Chapter {doi}"]}


class TestBatchResolver:
    async def test_resolves_many_dois_in_one_call(self):
        seen: list[str] = []

        def handler(request):
            seen.append(str(request.url))
            return httpx.Response(
                200, json={"results": [_oa_record("10.1/a"), _oa_record("10.1/b")]}
            )

        client = OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        found = await client.get_works_by_doi(["10.1/a", "10.1/b"])
        assert set(found) == {"10.1/a", "10.1/b"}
        assert len(seen) == 1, "a batch resolver that issues one call per DOI is not a batch"
        assert "filter=doi:10.1/a|10.1/b" in unquote(seen[0])
        await client.close()

    async def test_chunks_at_the_measured_cap(self):
        """MEASURED 2026-08-16: 101 values returns HTTP 400 from the live API."""
        calls: list[int] = []

        def handler(request):
            params = dict(request.url.params)
            calls.append(params["filter"].count("|") + 1)
            return httpx.Response(200, json={"results": []})

        client = OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        await client.get_works_by_doi([f"10.1/{i}" for i in range(MAX_FILTER_VALUES + 5)])
        assert len(calls) == 2
        assert max(calls) <= MAX_FILTER_VALUES
        await client.close()

    async def test_deduplicates_before_calling(self):
        calls: list[int] = []

        def handler(request):
            calls.append(dict(request.url.params)["filter"].count("|") + 1)
            return httpx.Response(200, json={"results": []})

        client = OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        await client.get_works_by_doi(["10.1/a", "10.1/a", "10.1/b"])
        assert calls == [2]
        await client.close()

    async def test_an_empty_request_makes_no_call_at_all(self):
        """The second guard behind the caller's early return.

        Found by mutation testing: removing `if not pending: return works` in the caller
        did NOT produce an extra HTTP call, because an empty DOI list yields no chunks
        here. The rate-budget protection is therefore redundant by design, and this test
        pins the inner half of it — otherwise a refactor could remove the outer guard and
        the suite would stay green while a future change made the inner one fire.
        """
        calls: list[str] = []

        def handler(request):
            calls.append(str(request.url))
            return httpx.Response(200, json={"results": []})

        client = OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        assert await client.get_works_by_doi([]) == {}
        assert calls == []
        await client.close()

    async def test_an_unknown_doi_is_absent_not_an_error(self):
        def handler(request):
            return httpx.Response(200, json={"results": []})

        client = OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        assert await client.get_works_by_doi(["10.9/nope"]) == {}
        await client.close()


def _wire(crossref_handler, openalex_handler):
    crossref = literature.get_crossref()
    openalex = literature.get_openalex()
    crossref._client = httpx.AsyncClient(
        base_url=crossref.base_url, transport=httpx.MockTransport(crossref_handler)
    )
    openalex._client = httpx.AsyncClient(
        base_url=openalex.base_url, transport=httpx.MockTransport(openalex_handler)
    )
    crossref.gate._min_interval = 0.0
    openalex.gate._min_interval = 0.0


class TestSecondPassOnSearch:
    """The measured gap: Crossref-only hits used to come back with retraction unknown."""

    def _openalex_two_phase(self, retracted: bool, calls: list[str]):
        """Search returns a disjoint set; the batch filter resolves Crossref's DOIs."""

        def handler(request):
            params = dict(request.url.params)
            if "filter" in params:
                calls.append("batch")
                return httpx.Response(
                    200, json={"results": [_oa_record("10.4324/only-in-crossref", retracted)]}
                )
            calls.append("search")
            return httpx.Response(200, json={"meta": {"count": 1}, "results": []})

        return handler

    async def test_unknown_becomes_resolved_after_the_second_pass(self):
        calls: list[str] = []
        _wire(
            lambda r: httpx.Response(
                200,
                json={
                    "message": {"total-results": 1, "items": [_cr_item("10.4324/only-in-crossref")]}
                },
            ),
            self._openalex_two_phase(retracted=False, calls=calls),
        )
        result = await literature.search_works.fn("eft")
        assert calls == ["search", "batch"]
        assert result.items[0].retraction_status is RetractionStatus.NOT_RETRACTED

    async def test_a_retracted_crossref_only_hit_is_now_flagged(self):
        """The payoff: a retracted work that search would previously have reported as unknown."""
        calls: list[str] = []
        _wire(
            lambda r: httpx.Response(
                200,
                json={
                    "message": {"total-results": 1, "items": [_cr_item("10.4324/only-in-crossref")]}
                },
            ),
            self._openalex_two_phase(retracted=True, calls=calls),
        )
        result = await literature.search_works.fn("eft")
        assert result.items[0].retraction_status is RetractionStatus.RETRACTED

    async def test_classification_is_untouched_by_the_second_pass(self):
        """Crossref stays primary on Axis A. The second pass fills retraction only."""
        calls: list[str] = []
        _wire(
            lambda r: httpx.Response(
                200,
                json={
                    "message": {"total-results": 1, "items": [_cr_item("10.4324/only-in-crossref")]}
                },
            ),
            self._openalex_two_phase(retracted=False, calls=calls),
        )
        result = await literature.search_works.fn("eft")
        work = result.items[0]
        assert work.venue_class is VenueClass.BOOK_CHAPTER
        assert work.classification_basis is ClassificationBasis.REGISTERED

    async def test_no_second_call_when_nothing_is_unknown(self):
        """An optimisation that always fires is a rate-budget leak."""
        calls: list[str] = []

        def openalex(request):
            params = dict(request.url.params)
            calls.append("batch" if "filter" in params else "search")
            return httpx.Response(
                200,
                json={"meta": {"count": 1}, "results": [_oa_record("10.1/shared")]},
            )

        _wire(
            lambda r: httpx.Response(
                200, json={"message": {"total-results": 1, "items": [_cr_item("10.1/shared")]}}
            ),
            openalex,
        )
        result = await literature.search_works.fn("eft")
        assert calls == ["search"], "second pass fired with nothing left to resolve"
        assert result.items[0].retraction_status is RetractionStatus.NOT_RETRACTED


class TestSecondPassFailureIsHonest:
    """The dangerous shortcut this ticket could have introduced."""

    @pytest.mark.parametrize("failure", [httpx.Response(503), httpx.Response(429)])
    async def test_a_failed_second_pass_leaves_unknown_standing(self, failure):
        """Constitution VII(d): never upgrade to not-retracted on a call that did not succeed."""

        def openalex(request):
            if "filter" in dict(request.url.params):
                return failure
            return httpx.Response(200, json={"meta": {"count": 0}, "results": []})

        _wire(
            lambda r: httpx.Response(
                200, json={"message": {"total-results": 1, "items": [_cr_item("10.4324/x")]}}
            ),
            openalex,
        )
        result = await literature.search_works.fn("eft")
        assert result.items[0].retraction_status is RetractionStatus.UNKNOWN

    async def test_a_doi_the_index_does_not_know_stays_unknown(self):
        """Absence from the batch response is not evidence of anything."""

        def openalex(request):
            if "filter" in dict(request.url.params):
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"meta": {"count": 0}, "results": []})

        _wire(
            lambda r: httpx.Response(
                200, json={"message": {"total-results": 1, "items": [_cr_item("10.4324/x")]}}
            ),
            openalex,
        )
        result = await literature.search_works.fn("eft")
        assert result.items[0].retraction_status is RetractionStatus.UNKNOWN

    async def test_a_transport_failure_also_leaves_unknown_standing(self):
        def openalex(request):
            if "filter" in dict(request.url.params):
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, json={"meta": {"count": 0}, "results": []})

        _wire(
            lambda r: httpx.Response(
                200, json={"message": {"total-results": 1, "items": [_cr_item("10.4324/x")]}}
            ),
            openalex,
        )
        result = await literature.search_works.fn("eft")
        assert result.items[0].retraction_status is RetractionStatus.UNKNOWN
