"""Tool-surface tests for the Tier-0 gateway (AGE-578).

Covers the Fuzzy-to-Fact contract (ADR-001 §3), the error envelope mapping, and the two
behaviours that are easy to get quietly wrong: what happens to `total_count` on a merged
result, and what happens to retraction when the retraction source is down.

No network — the clients' `_client` is swapped for an `httpx.MockTransport`.
"""

import json
from pathlib import Path

import httpx
import pytest

from psychology_mcp.errors import from_http_error, from_transport_error
from psychology_mcp.models.envelopes import ErrorCode, ErrorEnvelope, PaginationEnvelope
from psychology_mcp.models.work import RetractionStatus, VenueClass
from psychology_mcp.servers import literature

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(autouse=True)
def _reset_singletons():
    """ADR-004 singletons persist across calls; reset them between tests."""
    literature._crossref = None
    literature._openalex = None
    yield
    literature._crossref = None
    literature._openalex = None


def _wire(crossref_handler=None, openalex_handler=None):
    """Point both module singletons at mock transports."""
    crossref = literature.get_crossref()
    openalex = literature.get_openalex()
    if crossref_handler is not None:
        crossref._client = httpx.AsyncClient(
            base_url=crossref.base_url, transport=httpx.MockTransport(crossref_handler)
        )
    if openalex_handler is not None:
        openalex._client = httpx.AsyncClient(
            base_url=openalex.base_url, transport=httpx.MockTransport(openalex_handler)
        )
    crossref.gate._min_interval = 0.0
    openalex.gate._min_interval = 0.0
    return crossref, openalex


def _ok_crossref(payload=None):
    body = payload or _load("crossref-C1.json")
    return lambda request: httpx.Response(200, json=body)


def _ok_openalex(payload=None):
    body = payload or _load("openalex-C1.json")
    return lambda request: httpx.Response(200, json=body)


class TestStrictToolGrammar:
    """Constitution II and R4 — the accepted identifier grammar, declared and enforced."""

    @pytest.mark.parametrize(
        "accepted",
        [
            "10.1111/famp.12229",
            "doi:10.1111/famp.12229",
            "https://doi.org/10.1111/famp.12229",
            "http://dx.doi.org/10.1111/famp.12229",
            "  10.1111/famp.12229  ",
        ],
    )
    def test_accepted_forms_normalise_to_a_bare_doi(self, accepted):
        assert literature.normalise_doi(accepted) == "10.1111/famp.12229"

    @pytest.mark.parametrize(
        "rejected",
        [
            "The Heroine's Journey",
            "Wiebe & Johnson 2016",
            "",
            "10.badprefix/x",
            "PMC12345",
            "W2409023364",
        ],
    )
    def test_non_identifiers_are_rejected(self, rejected):
        assert literature.normalise_doi(rejected) is None

    async def test_a_raw_string_returns_unresolved_entity(self):
        result = await literature.get_work.fn("The Heroine's Journey")
        assert isinstance(result, ErrorEnvelope)
        assert result.error.code is ErrorCode.UNRESOLVED_ENTITY
        assert result.error.invalid_input == "The Heroine's Journey"
        assert "search_works" in result.error.recovery_hint


class TestSearchIsJointAndMerged:
    async def test_returns_the_union_of_both_connectors(self):
        """MEASURED: for the identical C1 query the two connectors return DISJOINT sets.

        Crossref's top 5 are book chapters (10.4324/, 10.1037/); OpenAlex's are journal
        articles (10.1111/). DOI overlap is ZERO. So a merged search is in practice a
        union of single-sourced records, not a set of two-source merges — every item still
        survives, per VII(b), but few get their retraction cleared.

        The joint design pays off on `get_work`, where both connectors are asked about the
        SAME DOI. Improving search-side coverage means resolving Crossref's DOIs against
        OpenAlex as a second step; that is a separate piece of work, not a silent addition.
        """
        _wire(_ok_crossref(), _ok_openalex())
        result = await literature.search_works.fn("emotionally focused therapy")
        assert isinstance(result, PaginationEnvelope)
        routes = {w.discovery_route for w in result.items}
        assert "crossref" in routes
        assert "openalex" in routes

    async def test_merges_when_a_doi_appears_in_both(self):
        """The join itself works; the C1 fixtures simply never exercise it."""
        doi = "10.1111/famp.12229"
        crossref_payload = {
            "message": {
                "total-results": 1,
                "items": [{"DOI": doi, "type": "journal-article", "title": ["Shared work"]}],
            }
        }
        openalex_payload = {
            "meta": {"count": 1},
            "results": [
                {
                    "id": "https://openalex.org/W1",
                    "ids": {"openalex": "https://openalex.org/W1", "doi": f"https://doi.org/{doi}"},
                    "doi": f"https://doi.org/{doi}",
                    "type": "article",
                    "is_retracted": False,
                    "primary_location": {"source": {"type": "journal", "display_name": "Fam Proc"}},
                }
            ],
        }
        _wire(_ok_crossref(crossref_payload), _ok_openalex(openalex_payload))
        result = await literature.search_works.fn("shared")
        assert len(result.items) == 1
        merged = result.items[0]
        assert merged.discovery_route == "crossref+openalex"
        # Crossref classifies, OpenAlex clears retraction.
        assert merged.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert merged.retraction_status is RetractionStatus.NOT_RETRACTED
        assert merged.cross_references.openalex_id == "W1"

    async def test_total_count_is_null_on_a_merged_result(self):
        """Constitution III: the two counts are not comparable, so no honest single total.

        The Layer-1 benchmark measured three orders of magnitude between connectors for
        identical queries. Reporting either one alone would misrepresent the merged set.
        """
        _wire(_ok_crossref(), _ok_openalex())
        result = await literature.search_works.fn("eft")
        assert result.pagination.total_count is None

    async def test_slim_returns_the_triage_triple_only(self):
        """v1.4.0: slim carries doi/title/venue_class and omits classification_basis."""
        _wire(_ok_crossref(), _ok_openalex())
        result = await literature.search_works.fn("eft", slim=True)
        assert all(set(item) == {"doi", "title", "venue_class"} for item in result.items)

    async def test_limit_is_capped_at_the_adr_page_size(self):
        _wire(_ok_crossref(), _ok_openalex())
        result = await literature.search_works.fn("eft", limit=500)
        assert result.pagination.page_size == 50


class TestDegradationPreservesHonesty:
    async def test_openalex_failure_degrades_rather_than_fails(self):
        """Crossref carries classification; OpenAlex only clears retraction."""

        def openalex_down(request):
            return httpx.Response(503)

        _wire(_ok_crossref(), openalex_down)
        result = await literature.search_works.fn("eft")
        assert isinstance(result, PaginationEnvelope)
        assert result.items

    async def test_retraction_is_unknown_not_not_retracted_when_openalex_is_down(self):
        """Constitution VII(d) — the whole point. Silence must not become a negative."""

        def openalex_down(request):
            return httpx.Response(503)

        _wire(_ok_crossref(), openalex_down)
        result = await literature.search_works.fn("eft")
        statuses = {w.retraction_status for w in result.items}
        assert statuses == {RetractionStatus.UNKNOWN}
        assert RetractionStatus.NOT_RETRACTED not in statuses

    async def test_crossref_failure_is_a_real_failure(self):
        """Without the classification source there is nothing to classify from."""

        def crossref_down(request):
            return httpx.Response(500)

        _wire(crossref_down, _ok_openalex())
        result = await literature.search_works.fn("eft")
        assert isinstance(result, ErrorEnvelope)
        assert result.error.code is ErrorCode.UPSTREAM_ERROR


class TestGetWorkMerges:
    async def test_merges_both_sources(self):
        item = _load("crossref-C1.json")["message"]["items"][0]
        record = _load("openalex-C1.json")["results"][0]
        _wire(
            lambda request: httpx.Response(200, json={"message": item}),
            lambda request: httpx.Response(200, json=record),
        )
        work = await literature.get_work.fn("10.1111/famp.12229")
        assert work.discovery_route == "crossref+openalex"
        assert work.retraction_status is RetractionStatus.NOT_RETRACTED

    async def test_a_work_missing_from_openalex_still_resolves(self):
        item = _load("crossref-C1.json")["message"]["items"][0]
        _wire(
            lambda request: httpx.Response(200, json={"message": item}),
            lambda request: httpx.Response(404),
        )
        work = await literature.get_work.fn("10.1111/famp.12229")
        assert work.discovery_route == "crossref"
        assert work.retraction_status is RetractionStatus.UNKNOWN

    async def test_missing_from_both_is_entity_not_found(self):
        _wire(
            lambda request: httpx.Response(404),
            lambda request: httpx.Response(404),
        )
        result = await literature.get_work.fn("10.9999/nope")
        assert isinstance(result, ErrorEnvelope)
        assert result.error.code is ErrorCode.ENTITY_NOT_FOUND


class TestErrorEnvelopeMapping:
    def test_429_maps_to_rate_limited_with_retry_after(self):
        request = httpx.Request("GET", "https://api.crossref.org/works")
        response = httpx.Response(429, headers={"retry-after": "12"}, request=request)
        envelope = from_http_error(
            "Crossref", httpx.HTTPStatusError("429", request=request, response=response)
        )
        assert envelope.error.code is ErrorCode.RATE_LIMITED
        assert "12 seconds" in envelope.error.recovery_hint

    def test_429_without_retry_after_still_maps(self):
        """Measured: Semantic Scholar's pool returned sustained 429 with no Retry-After."""
        request = httpx.Request("GET", "https://api.semanticscholar.org/x")
        response = httpx.Response(429, request=request)
        envelope = from_http_error(
            "Semantic Scholar", httpx.HTTPStatusError("429", request=request, response=response)
        )
        assert envelope.error.code is ErrorCode.RATE_LIMITED

    def test_5xx_maps_to_upstream_error(self):
        request = httpx.Request("GET", "https://api.crossref.org/works")
        response = httpx.Response(502, request=request)
        envelope = from_http_error(
            "Crossref", httpx.HTTPStatusError("502", request=request, response=response)
        )
        assert envelope.error.code is ErrorCode.UPSTREAM_ERROR

    def test_transport_failure_maps_to_upstream_error(self):
        envelope = from_transport_error("OpenAlex", httpx.ConnectError("boom"))
        assert envelope.error.code is ErrorCode.UPSTREAM_ERROR

    def test_every_envelope_carries_an_actionable_recovery_hint(self):
        """ADR-001 §8: the hint is what lets an agent self-correct instead of crashing."""
        request = httpx.Request("GET", "https://api.crossref.org/works")
        envelopes = [
            ErrorEnvelope.unresolved_entity("a title"),
            ErrorEnvelope.entity_not_found("10.1/x"),
            from_http_error(
                "Crossref",
                httpx.HTTPStatusError(
                    "500", request=request, response=httpx.Response(500, request=request)
                ),
            ),
        ]
        assert all(e.error.recovery_hint.strip() for e in envelopes)
        assert all(e.success is False for e in envelopes)


class TestAgentFacingContract:
    def test_gateway_instructions_warn_about_total_count_and_unknown(self):
        from psychology_mcp.servers.gateway import mcp as gateway

        text = gateway.instructions or ""
        assert "total_count" in text
        assert "not-retracted" in text

    def test_slim_description_states_it_is_triage_only(self):
        """v1.4.0 obliges a tool returning slim results to say so in its own description."""
        doc = literature.search_works.fn.__doc__ or ""
        assert "TRIAGE" in doc.upper()
        assert "admissibility" in doc

    def test_strict_tool_documents_its_accepted_grammar(self):
        """Constitution II / R4 — the grammar must be declared, not just enforced."""
        doc = literature.get_work.fn.__doc__ or ""
        assert "10.x/y" in doc
        assert "UNRESOLVED_ENTITY" in doc

    def test_the_three_layer4_classes_never_reach_an_agent(self):
        unresolvable = {
            VenueClass.GUIDELINE,
            VenueClass.INSTITUTE_PUBLICATION,
            VenueClass.COMMENTARY,
        }
        from psychology_mcp.clients import crossref as cr
        from psychology_mcp.clients import openalex as oa

        assert not (set(cr._TYPE_TO_VENUE.values()) & unresolvable)
        assert not (set(oa._TYPE_TO_VENUE.values()) & unresolvable)
