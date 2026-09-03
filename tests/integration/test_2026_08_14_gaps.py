"""Did the six 2026-08-14 gaps actually close? (AGE-583, deterministic half)

This is the outcome the whole project exists to produce. On 2026-08-14 a consumer run of
`psychology-evidence-builder` returned **six UNRESOLVED** research questions — not because
the literature does not exist, but because psychology had no Layer 2 to query. Source: an internal 2026-08-14 consumer run of `psychology-evidence-builder`;
record kept outside this repo (see AGE-583).

The six map one-to-one onto the frozen benchmark's first six coverage queries, which is not
a coincidence: the research spec records that Q1-Q8 were derived from that gap list.

| 2026-08-14 UNRESOLVED | Benchmark |
|---|---|
| IFS — parts, Self-led vs. protective | Q1 |
| Somatic Experiencing / Sensorimotor — window of tolerance | Q2 |
| AEDP transformance specifically | Q3 |
| Heroine's Journey (Murdock / Frankel) | Q4 |
| Marston DISC | Q5 |
| Secure base in established adult dyads (C14) | Q6 |

**What is asserted is CAPABILITY, not ranking.** "Q4 returns Murdock at rank 1" would be a
flake generator; "Q4 returns admissible, classified candidates" is the claim that
distinguishes today from 2026-08-14. Whether a given result is *relevant* is a judgement,
and automating that judgement is the LLM half of AGE-583.

Opt-in: `uv run pytest -m integration --run-integration -q`.
"""

import asyncio

import pytest

from psychology_mcp.models.envelopes import PaginationEnvelope
from psychology_mcp.models.work import ClassificationBasis, VenueClass
from psychology_mcp.servers import literature

from .queries import QUERIES

pytestmark = [pytest.mark.integration, pytest.mark.crossref, pytest.mark.openalex]

# query id -> the UNRESOLVED item it corresponds to, quoted from the run report.
GAPS = {
    "Q1": "IFS (parts, Self-led vs. protective)",
    "Q2": "Somatic Experiencing / Sensorimotor, window of tolerance",
    "Q3": "AEDP transformance specifically",
    "Q4": "Heroine's Journey (Murdock / Frankel)",
    "Q5": "Marston DISC",
    "Q6": "secure base in established adult dyads (C14)",
}


@pytest.fixture(scope="module")
def gap_results() -> dict[str, PaginationEnvelope]:
    """One live pass over the six, shared across assertions."""
    by_id = {q.id: q for q in QUERIES}

    async def run_all() -> dict[str, PaginationEnvelope]:
        out: dict[str, PaginationEnvelope] = {}
        try:
            for qid in GAPS:
                out[qid] = await literature.search_works.fn(by_id[qid].search, limit=5)
        finally:
            await literature.get_crossref().close()
            await literature.get_openalex().close()
        return out

    return asyncio.run(run_all())


@pytest.mark.parametrize("qid", list(GAPS), ids=lambda q: f"{q}-{GAPS[q][:28]}")
class TestTheSixGapsAreClosed:
    def test_returns_candidates_at_all(self, qid, gap_results):
        """On 2026-08-14 this was the failure: retrieval returned nothing usable."""
        assert gap_results[qid].items, f"{qid} ({GAPS[qid]}) still returns nothing"

    def test_at_least_one_candidate_is_classified(self, qid, gap_results):
        """A hit the consumer cannot tier is barely better than no hit.

        `unverified` results still survive as hits per VII(b) — but if EVERY result were
        unverified, the envelope would be delivering no admissibility signal and the gap
        would not really be closed.
        """
        classified = [
            w
            for w in gap_results[qid].items
            if w.venue_class is not VenueClass.UNVERIFIED
            and w.classification_basis is not ClassificationBasis.NONE
        ]
        assert classified, f"{qid} ({GAPS[qid]}) returns only unclassifiable candidates"

    def test_no_candidate_is_silently_mislabelled(self, qid, gap_results):
        """Classification honesty holds on exactly the queries that motivated it."""
        for work in gap_results[qid].items:
            assert work.venue_class not in {
                VenueClass.GUIDELINE,
                VenueClass.INSTITUTE_PUBLICATION,
                VenueClass.COMMENTARY,
            }


class TestTextIsAgentReady:
    """Found by reading live output rather than by any fixture assertion."""

    def test_titles_are_not_html_escaped(self, gap_results):
        """A live Q1 result arrived as `&gt;Finding and Befriending Parts`.

        Passed through raw, an agent reads, quotes and cites the entity. Every fixture test
        that only checked "title is a string" passed while this was broken.
        """
        for qid, envelope in gap_results.items():
            for work in envelope.items:
                assert "&gt;" not in (work.title or ""), f"{qid}: {work.title}"
                assert "&amp;" not in (work.title or ""), f"{qid}: {work.title}"
                assert "&lt;" not in (work.title or ""), f"{qid}: {work.title}"
