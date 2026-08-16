"""Per-connector live checks (AGE-582).

Populates the `crossref` and `openalex` markers, which were declared in `pyproject.toml`
from the start and had no members — the same "category with no members" shape the
constitution's partial-implementation rule exists to surface.

Opt-in: `uv run pytest -m crossref --run-integration -q`.

These pin the connector CONTRACTS that were verified by hand during discovery and would
otherwise only ever be re-verified by hand:

- Crossref `/works/{doi}` returns a single object, not a list (03-crossref.md §5)
- Crossref reports retraction affirmatively via `update-to[]` (§3.4)
- OpenAlex resolves a DOI via the `https://doi.org/` form
- OpenAlex batch-filters DOIs, and rejects more than the measured cap
"""

import os

import httpx
import pytest

from psychology_mcp.clients.crossref import CrossrefClient
from psychology_mcp.clients.openalex import MAX_FILTER_VALUES, OpenAlexClient
from psychology_mcp.models.work import ClassificationBasis, RetractionStatus, VenueClass

pytestmark = pytest.mark.integration

CONTACT = os.environ.get("PSYCHOLOGY_MCP_CONTACT_EMAIL", "")

# The C1 control: Wiebe & Johnson 2016, EFT outcome review.
KNOWN_DOI = "10.1111/famp.12229"

# The live retracted record located during Layer-1 discovery (03-crossref.md §3.4).
RETRACTED_DOI = "10.1016/j.micpro.2020.103768"


@pytest.fixture
async def crossref():
    client = CrossrefClient(contact_email=CONTACT)
    yield client
    await client.close()


@pytest.fixture
async def openalex():
    client = OpenAlexClient(contact_email=CONTACT)
    yield client
    await client.close()


@pytest.mark.crossref
class TestCrossrefLive:
    async def test_strict_lookup_returns_one_work_not_a_list(self, crossref):
        """03-crossref.md §5. Indexing into `items` here would raise, not silently pass."""
        work = await crossref.get_work(KNOWN_DOI)
        assert work.cross_references.doi == KNOWN_DOI
        assert work.title

    async def test_registered_type_yields_the_registered_basis(self, crossref):
        """Crossref is a registration authority; that is what `registered` means."""
        work = await crossref.get_work(KNOWN_DOI)
        assert work.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert work.classification_basis is ClassificationBasis.REGISTERED

    async def test_retraction_is_reported_affirmatively(self, crossref):
        work = await crossref.get_work(RETRACTED_DOI)
        assert work.retraction_status is RetractionStatus.RETRACTED

    async def test_a_clean_record_is_unknown_not_not_retracted(self, crossref):
        """Constitution VII(d) against the live API: Crossref never says 'not retracted'."""
        work = await crossref.get_work(KNOWN_DOI)
        assert work.retraction_status is RetractionStatus.UNKNOWN

    async def test_publishes_rate_headers_and_the_gate_adopts_them(self, crossref):
        await crossref.get_work(KNOWN_DOI)
        gate = crossref.gate
        assert gate.min_interval > 0
        assert gate.concurrency >= 1

    async def test_an_unknown_doi_404s_rather_than_returning_an_empty_work(self, crossref):
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await crossref.get_work("10.9999/definitely-not-a-real-doi-psychology-mcp")
        assert exc.value.response.status_code == 404


@pytest.mark.openalex
class TestOpenAlexLive:
    async def test_strict_lookup_via_the_doi_url_form(self, openalex):
        """The form this client ships was inferred from the dossier; this pins it."""
        work = await openalex.get_work(KNOWN_DOI)
        assert work.cross_references.doi == KNOWN_DOI

    async def test_identifiers_arrive_as_urls_and_are_extracted(self, openalex):
        """`ids.openalex` and `ids.pmid` are URLs, not bare ids - the registry needs bare."""
        work = await openalex.get_work(KNOWN_DOI)
        assert work.cross_references.openalex_id
        assert work.cross_references.openalex_id.startswith("W")
        assert "/" not in work.cross_references.openalex_id
        if work.cross_references.pmid:
            assert work.cross_references.pmid.isdigit()

    async def test_reports_retraction_in_both_directions(self, openalex):
        """The only roster connector that does, which is what permits NOT_RETRACTED."""
        clean = await openalex.get_work(KNOWN_DOI)
        retracted = await openalex.get_work(RETRACTED_DOI)
        assert clean.retraction_status is RetractionStatus.NOT_RETRACTED
        assert retracted.retraction_status is RetractionStatus.RETRACTED

    async def test_never_claims_the_registered_basis(self, openalex):
        """An index is not a registration authority (AGE-575 precedence)."""
        work = await openalex.get_work(KNOWN_DOI)
        assert work.classification_basis is not ClassificationBasis.REGISTERED

    async def test_batch_filter_resolves_several_dois_in_one_call(self, openalex):
        found = await openalex.get_works_by_doi([KNOWN_DOI, RETRACTED_DOI])
        assert set(found) == {KNOWN_DOI.lower(), RETRACTED_DOI.lower()}
        assert found[RETRACTED_DOI.lower()].retraction_status is RetractionStatus.RETRACTED

    async def test_the_measured_filter_cap_still_holds(self, openalex):
        """MEASURED 2026-08-16: 100 values OK, 101 -> HTTP 400.

        If this ever passes at 101, the cap moved and MAX_FILTER_VALUES should be re-measured
        rather than guessed.
        """
        too_many = "|".join(f"10.9999/probe.{i:05d}" for i in range(MAX_FILTER_VALUES + 1))
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await openalex.get_json("/works", params={"filter": f"doi:{too_many}", "per-page": 1})
        assert exc.value.response.status_code == 400

    async def test_publishes_a_credit_budget(self, openalex):
        await openalex.get_work(KNOWN_DOI)
        assert openalex.credits_limit is not None
        assert openalex.credits_remaining is not None
