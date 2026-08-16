"""Live Semantic Scholar checks (AGE-590).

Populates the `semanticscholar` marker on the integration side. Until 2026-08-16 this
connector had **never been called live from this codebase** — AGE-588 shipped
fixture-verified only, because no key was present in `.env`.

Opt-in: `uv run pytest -m semanticscholar --run-integration -q`.

What these pin, and why each one needs the network to be honest:

- **The strict `/paper/{ID}` endpoint works.** `01-semantic-scholar.md` §5 recorded it as
  *documented but NOT verified live* — every Layer-1 probe call 429'd before a key was
  issued. The unit tests pin the request shape we send; only this pins that the API
  honours it. VERIFIED 2026-08-16.
- **The identifier crosswalk is real.** §3(a) claims DOI + PubMed id + corpus id + ISSN in
  one response, and that claim is why this connector is the triangulation source under
  ADR-001 §6.
- **The unique reach is real** — records with no DOI that no other roster connector sees.
- **Retraction stays UNKNOWN against the real API**, not merely against a fixture.

**THE SUITE FETCHES ONCE AND ASSERTS MANY TIMES, DELIBERATELY.** MEASURED 2026-08-16:
429s from this API are STOCHASTIC, not a sustained-rate signal — 8-call sweeps drew 4/8 at
2.5s spacing, 2/8 at 4.0s and 4/8 at 6.0s, and both endpoints throttle intermittently at
3.0s. Neither wider spacing nor a longer retry budget makes a 20-call suite reliable; the
only thing that does is making fewer calls. A per-test fetch here produced a different
random failure on every run, which is worse than useless — it teaches you to ignore red.

Skipped entirely when no key is configured. Unlike Tier 0 there is no keyless fallback —
the anonymous pool completed zero of twelve benchmark queries across ~1.5h — so an
unconfigured run here is a skip, never a silent downgrade.
"""

import asyncio
import time

import httpx
import pytest

from psychology_mcp.clients.semanticscholar import SemanticScholarClient
from psychology_mcp.models.work import ClassificationBasis, RetractionStatus

pytestmark = [pytest.mark.integration, pytest.mark.semanticscholar]

# The C1 control, the same record the Crossref and OpenAlex live suites use: Wiebe &
# Johnson 2016, EFT outcome review. Shared deliberately — a crosswalk claim is only
# checkable against a record the other connectors also resolve.
KNOWN_DOI = "10.1111/famp.12229"

# Q3 of the frozen benchmark. The only query in the set that Semantic Scholar answers and
# the Tier 0 connectors do not, and the source of the DOI-less records AGE-589 exists for.
UNIQUE_REACH_QUERY = "AEDP transformance"


@pytest.fixture(scope="module")
def live():
    """Every live call this module makes — three, in one event loop.

    Module-scoped and SYNCHRONOUS, driving a single `asyncio.run`. The project pins
    `asyncio_default_fixture_loop_scope = "function"`, so a module-scoped *async* fixture
    raises ScopeMismatch; this is the shape that works.
    """
    if not SemanticScholarClient().is_configured:
        pytest.skip(
            "No Semantic Scholar key configured. Set S2_API_KEY in .env — this connector "
            "has NO keyless fallback; the anonymous pool is unusable."
        )

    async def fetch():
        client = SemanticScholarClient()
        try:
            bare = await client.get_work(KNOWN_DOI)
            prefixed = await client.get_work(f"DOI:{KNOWN_DOI}")
            works, total = await client.search_works(UNIQUE_REACH_QUERY, limit=5)
            return {"bare": bare, "prefixed": prefixed, "works": works, "total": total}
        finally:
            await client.close()

    try:
        return asyncio.run(fetch())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code != 429:
            raise
        # ADR-001 classifies an exhausted upstream 429 as `RATE_LIMITED` — a DOCUMENTED
        # operational outcome with the remedy "retry with backoff", not a contract breach.
        # The tool surface already returns that envelope (`from_http_error`, pinned by
        # test_gateway_tools.py). This suite calls the client directly, one layer below,
        # where the same condition arrives as an exception.
        #
        # Treating it as a red test would report an upstream rate limit as a broken
        # contract. Skipping is safe ONLY because it is narrowed to 429: every other
        # status, and every assertion below, still fails loudly.
        pytest.skip(
            "Semantic Scholar returned 429 after the client's full retry budget. ADR-001 "
            "RATE_LIMITED — an upstream rate limit, not a contract failure. Retry shortly."
        )


class TestTheStrictEndpoint:
    """§5 was DOCUMENTED, not measured, until this suite existed."""

    def test_paper_by_doi_resolves(self, live):
        assert live["bare"].cross_references.doi == KNOWN_DOI
        assert live["bare"].title

    def test_the_doi_prefixed_form_resolves_to_the_same_record(self, live):
        """Both accepted grammars reach one record — `normalise_identifier` prefixes a
        bare DOI, and this proves the API agrees with that translation."""
        assert live["prefixed"].cross_references.doi == live["bare"].cross_references.doi

    async def test_a_non_identifier_is_refused_before_a_request_is_built(self):
        """Constitution II. No network: the point is that it never reaches one."""
        client = SemanticScholarClient(api_key="unused", min_interval=0.0)
        with pytest.raises(ValueError, match="not an accepted"):
            await client.get_work("A Review of the Research in Emotionally Focused Therapy")
        await client.close()


class TestTheCrosswalkIsReal:
    """§3(a) — the claim that makes this the triangulation source (ADR-001 §6)."""

    def test_doi_pmid_and_corpus_id_arrive_together(self, live):
        refs = live["bare"].cross_references
        assert refs.doi == KNOWN_DOI
        assert refs.pmid and refs.pmid.isdigit()
        assert refs.semantic_scholar_id

    def test_the_pmid_matches_the_record_the_other_connectors_resolve(self, live):
        """VERIFIED 2026-08-16: PubMed id 27273169 for the C1 control."""
        assert live["bare"].cross_references.pmid == "27273169"


class TestWhatItCannotSupply:
    def test_retraction_is_unknown_against_the_live_api(self, live):
        """VII(d) against the network, not a fixture. S2 has no retraction signal, and
        `unknown` must never be read as `not-retracted`."""
        assert live["bare"].retraction_status is RetractionStatus.UNKNOWN
        assert live["bare"].retraction_status is not RetractionStatus.NOT_RETRACTED

    def test_the_basis_is_never_registered(self, live):
        """S2 is an index. Only Crossref registers."""
        assert live["bare"].classification_basis is not ClassificationBasis.REGISTERED

    def test_no_searched_record_claims_the_registered_basis_either(self, live):
        assert all(
            w.classification_basis is not ClassificationBasis.REGISTERED for w in live["works"]
        )


class TestUniqueReach:
    """Why this connector is on the roster at all."""

    def test_the_aedp_query_returns_results(self, live):
        assert live["works"], "Q3 is the query only Semantic Scholar answers"

    def test_it_reaches_records_that_have_no_doi(self, live):
        """MEASURED 2026-08-16: 2 of 5. The case `index-asserted` and AGE-589's reserved
        slots both exist for — no other roster connector reaches these at all."""
        assert any(not w.cross_references.doi for w in live["works"])

    def test_a_doi_less_record_still_carries_an_identifier(self, live):
        """VII(b): unclassifiable is not unusable. A corpus id is what makes it fetchable."""
        doi_less = [w for w in live["works"] if not w.cross_references.doi]
        assert doi_less
        assert all(w.cross_references.semantic_scholar_id for w in doi_less)

    def test_a_metadata_free_record_is_not_dressed_up(self, live):
        """MEASURED: the DOI-less AEDP records carry publicationTypes, venue AND
        publicationVenue all null, so the AGE-590 fallback cannot reach them either.
        `unverified`/`none` is the correct answer, and asserting anything else is VII(c)."""
        for work in live["works"]:
            if work.classification_basis is ClassificationBasis.NONE:
                assert work.venue_class.value == "unverified"

    def test_total_count_is_never_treated_as_comparable(self, live):
        """Constitution III. MEASURED 2026-08-16: S2 reported ~2.47M for a query Crossref
        answers in the hundreds. Recorded so the number is never summed or ranked on."""
        assert live["total"] is None or live["total"] > 0


class TestRateDiscipline:
    """The gate, not the network. A live assertion here would be the flakiest in the repo
    for the least information — the stochastic-429 measurement is what made that clear."""

    def test_the_gate_spaces_calls_by_the_measured_interval(self):
        async def timed():
            client = SemanticScholarClient(api_key="unused")
            async with client.gate:
                pass
            start = time.monotonic()
            async with client.gate:
                pass
            elapsed = time.monotonic() - start
            await client.close()
            return elapsed

        assert asyncio.run(timed()) >= 2.0

    def test_the_retry_budget_survives_a_throttle_window(self):
        """429s are stochastic here, so surviving one is the retry budget's job, not the
        spacing's. The base default spends ~1.75s retrying — shorter than one window."""
        client = SemanticScholarClient(api_key="unused")
        assert client._max_attempts >= 5
        assert client._backoff_base >= 2.5
