"""The pre-registered benchmark, run live against the tool surface (AGE-582).

Opt-in: `uv run pytest -m integration --run-integration -q`.

**These assert CONTRACT, not results.** Live indexes change ranking daily, so an assertion
like "Q4 returns Murdock at rank 1" would be a flake generator, not a test. What must hold
regardless of what the indexes decide today is the envelope's honesty:

- every work carries a `venue_class` AND a `classification_basis`
- nothing claims `not-retracted` unless the always-reporting source was actually consulted
- the three Layer-4 classes are never asserted
- `total_count` stays null on merged results
- the positive control returns something; the negative control never matches its fabricated
  construct

Coverage measurement is a different exercise, recorded in `00-coverage-matrix.md`. Re-running
the benchmark to CHANGE those recorded cells is an amendment-by-measurement act; this suite
only checks that the server behaves lawfully while answering them.
"""

import asyncio

import pytest

from psychology_mcp.models.envelopes import PaginationEnvelope
from psychology_mcp.models.work import ClassificationBasis, RetractionStatus, VenueClass
from psychology_mcp.servers import literature

from .queries import FABRICATED_CONSTRUCT, QUERIES

pytestmark = [pytest.mark.integration, pytest.mark.crossref, pytest.mark.openalex]

UNRESOLVABLE = {
    VenueClass.GUIDELINE,
    VenueClass.INSTITUTE_PUBLICATION,
    VenueClass.COMMENTARY,
}

COVERAGE = [q for q in QUERIES if q.role == "coverage"]


@pytest.fixture(scope="module")
def results() -> dict[str, PaginationEnvelope]:
    """Run all twelve queries ONCE and share the results across assertions.

    Per-test queries would multiply live traffic twelvefold for no additional signal.

    Deliberately a SYNC fixture driving one `asyncio.run`. A module-scoped async fixture
    raises ScopeMismatch against this project's function-scoped event loop
    (`asyncio_default_fixture_loop_scope = "function"`), and widening the loop scope to
    suit one test module is a worse trade than running the batch in a single loop here.
    """

    async def run_all() -> dict[str, PaginationEnvelope]:
        out: dict[str, PaginationEnvelope] = {}
        try:
            for query in QUERIES:
                out[query.id] = await literature.search_works.fn(query.search, limit=10)
        finally:
            await literature.get_crossref().close()
            await literature.get_openalex().close()
        return out

    return asyncio.run(run_all())


class TestEnvelopeHonesty:
    """The invariants that must hold whatever the indexes return today."""

    @pytest.mark.parametrize("query", COVERAGE, ids=lambda q: q.id)
    def test_every_work_carries_a_class_and_a_basis(self, query, results):
        for work in results[query.id].items:
            assert isinstance(work.venue_class, VenueClass)
            assert isinstance(work.classification_basis, ClassificationBasis)

    @pytest.mark.parametrize("query", COVERAGE, ids=lambda q: q.id)
    def test_unclassified_works_carry_no_basis_and_vice_versa(self, query, results):
        """`unverified` with a basis, or a real class with basis `none`, is incoherent."""
        for work in results[query.id].items:
            if work.venue_class is VenueClass.UNVERIFIED:
                assert work.classification_basis is ClassificationBasis.NONE
            else:
                assert work.classification_basis is not ClassificationBasis.NONE

    @pytest.mark.parametrize("query", COVERAGE, ids=lambda q: q.id)
    def test_never_asserts_a_layer4_class(self, query, results):
        """Constitution VII(c): no connector vocabulary supports these three."""
        for work in results[query.id].items:
            assert work.venue_class not in UNRESOLVABLE

    @pytest.mark.parametrize("query", COVERAGE, ids=lambda q: q.id)
    def test_not_retracted_only_ever_comes_from_openalex(self, query, results):
        """Constitution VII(d), end to end and live.

        Crossref reports retraction only in the affirmative, so a `not-retracted` on a
        record OpenAlex never saw would mean the server invented a negative from silence.
        """
        for work in results[query.id].items:
            if work.retraction_status is RetractionStatus.NOT_RETRACTED:
                assert "openalex" in (work.discovery_route or ""), (
                    f"{work.cross_references.doi} claims not-retracted but was only seen by "
                    f"{work.discovery_route}"
                )

    @pytest.mark.parametrize("query", COVERAGE, ids=lambda q: q.id)
    def test_total_count_is_null_on_merged_results(self, query, results):
        assert results[query.id].pagination.total_count is None


class TestControls:
    """C1 validates the harness. C2 is the hallucination check."""

    def test_c1_positive_control_returns_results(self, results):
        """A miss here is a BROKEN CLIENT, not a coverage gap - that is what C1 is for."""
        assert results["C1"].items, "positive control returned nothing: harness fault"

    def test_c2_never_matches_the_fabricated_construct(self, results):
        """Per probe/RUBRIC.md: adjacent papers are a PASS; a confident exact match FAILS.

        Token-relevance engines legitimately return work matching `co-regulation` or
        `index`. What must never happen is a result presented as THE fabricated construct.
        """
        offenders = [
            w.title
            for w in results["C2"].items
            if w.title and FABRICATED_CONSTRUCT in w.title.lower()
        ]
        assert not offenders, f"fabricated construct matched: {offenders}"


class TestRateAccounting:
    def test_crossref_posture_is_adopted_from_live_headers(self, results):
        """AGE-576 live: nothing is hardcoded, the server's own headers win.

        The starting posture is 0.5s spacing / 2 concurrent. Crossref publishes
        `x-rate-limit-*` on every response, so after twelve queries the gate must have
        moved off its defaults.
        """
        gate = literature.get_crossref().gate
        assert (gate.min_interval, gate.concurrency) != (0.5, 2), (
            "gate never adapted; either the headers vanished or observe() is not wired"
        )

    def test_openalex_credit_budget_is_observed(self, results):
        """AGE-582: OpenAlex publishes a daily CREDIT budget, not a rate."""
        client = literature.get_openalex()
        assert client.credits_limit is not None, "no x-ratelimit-limit seen"
        assert client.credits_remaining is not None
        assert 0 <= client.credits_remaining <= client.credits_limit

    def test_credits_do_not_leak_into_request_spacing(self, results):
        """A daily budget is not a rate. Shortening the interval cannot fix exhaustion."""
        client = literature.get_openalex()
        assert client.gate.min_interval < 1.0
