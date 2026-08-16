"""Golden-fixture tests for the Semantic Scholar connector (AGE-588).

The fixture is the **authenticated** C1 capture from the Layer-1 probe — the run that
discharged the connector's condition and measured it 5 hit / 4 partial / 1 miss.

The rules under test are the ones that make this connector worth having, and the ones
that would silently break the envelope if they were wrong.
"""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from psychology_mcp.clients import semanticscholar as s2
from psychology_mcp.models.cross_references import CrossReferences
from psychology_mcp.models.work import (
    ClassificationBasis,
    RetractionStatus,
    VenueClass,
    Work,
)
from psychology_mcp.servers.literature import _fold_in_semanticscholar, _reserved_slots

pytestmark = [pytest.mark.unit, pytest.mark.semanticscholar]

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="module")
def papers() -> list[dict]:
    return json.loads((FIXTURES / "semantic-scholar-C1.json").read_text())["data"]


class TestFixtureIsTheAuthenticatedCapture:
    def test_shape(self, papers):
        assert len(papers) == 5
        assert all("paperId" in p and "externalIds" in p for p in papers)


class TestIdentifierCrosswalk:
    """§3(a): the richest crosswalk in the candidate set — the triangulation source."""

    def test_doi_pmid_corpusid_and_issn_in_one_response(self, papers):
        work = s2.to_work(papers[0])
        refs = work.cross_references
        assert refs.doi == "10.1111/famp.12305"
        assert refs.pmid == "28870000"
        assert refs.semantic_scholar_id
        assert refs.issn

    def test_pmid_is_stored_bare_not_as_a_url(self, papers):
        """CROSS_REF_PATTERNS requires ^\\d+$ — S2 supplies it bare, unlike OpenAlex."""
        pmid = s2.to_work(papers[0]).cross_references.pmid
        assert pmid is not None and pmid.isdigit()

    def test_corpus_id_is_used_when_paper_id_is_not_40_hex(self):
        work = s2.to_work({"paperId": "short", "externalIds": {"CorpusId": 44674475}})
        assert work.cross_references.semantic_scholar_id == "44674475"

    def test_a_40_hex_paper_id_is_preferred(self):
        pid = "a" * 40
        work = s2.to_work({"paperId": pid, "externalIds": {"CorpusId": 1}})
        assert work.cross_references.semantic_scholar_id == pid

    def test_issn_list_is_reduced_to_one_value(self):
        work = s2.to_work({"publicationVenue": {"issn": ["0014-7370", "1545-5300"]}})
        assert work.cross_references.issn == "0014-7370"


class TestTheDoilessCase:
    """§3(c) — the reason this connector exists, and what VII(b) was written for."""

    def test_a_registered_type_with_no_doi_still_classifies(self):
        """2 of 5 sampled records are exactly this shape.

        A DOI-first rule leaves them untierable despite the API having said what they are.
        `index-asserted` is the basis that keeps them usable.
        """
        record = {"publicationTypes": ["Review"], "externalIds": {"CorpusId": 999}}
        work = s2.to_work(record)
        assert work.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert work.classification_basis is ClassificationBasis.INDEX_ASSERTED
        assert work.cross_references.doi is None
        assert work.cross_references.semantic_scholar_id == "999"

    def test_such_a_record_is_not_flattened_to_unverified(self):
        work = s2.to_work({"publicationTypes": ["JournalArticle"]})
        assert work.venue_class is not VenueClass.UNVERIFIED


class TestClassification:
    def test_basis_is_never_registered(self, papers):
        """S2 is an index, not a registration authority (AGE-575 precedence)."""
        assert all(
            s2.to_work(p).classification_basis is not ClassificationBasis.REGISTERED for p in papers
        )

    @pytest.mark.parametrize(
        ("types", "expected"),
        [
            (["JournalArticle"], VenueClass.PEER_REVIEWED_ARTICLE),
            (["Review"], VenueClass.PEER_REVIEWED_ARTICLE),
            (["Book"], VenueClass.BOOK),
            (["BookSection"], VenueClass.BOOK_CHAPTER),
            (["Dataset"], VenueClass.GREY),
        ],
    )
    def test_types_map_by_precedence(self, types, expected):
        assert s2.classify({"publicationTypes": types})[0] is expected

    def test_multiple_types_resolve_by_precedence_not_by_order(self):
        """The C1 fixture carries ['JournalArticle', 'ClinicalTrial'] on one record."""
        assert (
            s2.classify({"publicationTypes": ["ClinicalTrial", "JournalArticle"]})[0]
            is VenueClass.PEER_REVIEWED_ARTICLE
        )

    @pytest.mark.parametrize("raw", ["Editorial", "LettersAndComments", "News", "Conference"])
    def test_commentary_shaped_types_are_never_asserted(self, raw):
        """Constitution VII(c). `commentary` has no support in any connector vocabulary,
        and S2 supplies no publisher to corroborate it."""
        venue, basis = s2.classify({"publicationTypes": [raw]})
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE
        assert venue is not VenueClass.COMMENTARY

    def test_the_raw_type_survives_even_when_unclassified(self):
        work = s2.to_work({"publicationTypes": ["Editorial"]})
        assert work.venue_class is VenueClass.UNVERIFIED
        assert work.source_type == "Editorial"

    def test_no_types_means_no_basis(self):
        venue, basis = s2.classify({})
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE


class TestWhatItCannotSupply:
    def test_retraction_is_always_unknown(self, papers):
        """MEASURED 0/5 — no retraction signal exists. VII(d): silence is not a negative."""
        statuses = {s2.to_work(p).retraction_status for p in papers}
        assert statuses == {RetractionStatus.UNKNOWN}
        assert RetractionStatus.NOT_RETRACTED not in statuses

    def test_retraction_stays_unknown_even_for_a_fabricated_true(self):
        assert s2.retraction_status({"is_retracted": True}) is RetractionStatus.UNKNOWN

    def test_publisher_is_absent_on_every_fixture_record(self, papers):
        """MEASURED 0/5. `institute-publication` is unreachable from S2 metadata alone."""
        assert all(s2.to_work(p).publisher is None for p in papers)


class TestRateDiscipline:
    def test_starting_posture_is_the_measured_safe_interval(self):
        """1.3s drew a 429; 2.5s is the observed-safe sustained interval."""
        client = s2.SemanticScholarClient(api_key="k")
        assert client.gate.min_interval == s2.SAFE_INTERVAL_SECONDS
        assert client.gate.min_interval >= 2.5

    def test_concurrency_is_one_because_the_limit_is_cumulative(self):
        """1 req/s CUMULATIVE across all endpoints — parallelism buys nothing."""
        assert s2.SemanticScholarClient(api_key="k").gate.concurrency == 1

    def test_attempt_count_follows_the_platform_pattern(self):
        """Every biosciences-mcp connector uses MAX_RETRIES = 3 — four attempts including
        the first. This connector does NOT get a bespoke number."""
        assert s2.SemanticScholarClient(api_key="k")._max_attempts == 4

    def test_backoff_cap_matches_the_platform_max_backoff(self):
        """drugbank.py MAX_BACKOFF = 60.0, marked Constitution v1.1.0 MANDATORY."""
        assert s2.SemanticScholarClient(api_key="k")._backoff_cap == 60.0

    def test_backoff_base_is_declared_because_it_cannot_be_discovered(self):
        """The one deliberate divergence, and the reason for it.

        errors.py already records that S2 returns sustained 429 with NO `Retry-After`, so
        the Retry-After branch is inert and `AdaptiveGate.observe` receives nothing. Where
        Crossref's posture is discovered from `x-rate-limit-*` at runtime, this one must be
        declared — and the measured 1 req/s cumulative limit is what declares it.
        """
        client = s2.SemanticScholarClient(api_key="k")
        assert client._backoff_base == s2.SAFE_INTERVAL_SECONDS

    def test_the_adaptive_gate_never_speeds_up_on_silence(self, monkeypatch):
        """S2 sends no rate headers at all. Silence must not be read as permission —
        the same rule as constitution VII(d), applied to rate posture."""
        client = s2.SemanticScholarClient(api_key="k")
        before = client.gate.min_interval
        asyncio.run(client.gate.observe(httpx.Headers({"x-amzn-errortype": "TooManyRequests"})))
        assert client.gate.min_interval == before

    def test_it_is_far_slower_than_the_keyless_tier_0_connectors(self):
        from psychology_mcp.clients.crossref import CrossrefClient

        assert s2.SemanticScholarClient(api_key="k").gate.min_interval > (
            CrossrefClient().gate.min_interval
        )


class TestCredentialHandling:
    def test_reports_unconfigured_without_a_key(self, monkeypatch):
        monkeypatch.delenv("S2_API_KEY", raising=False)
        assert s2.SemanticScholarClient().is_configured is False

    def test_reads_the_key_from_the_environment(self, monkeypatch):
        """Constitution: credentials from the environment, never from source."""
        monkeypatch.setenv("S2_API_KEY", "s2k-from-env")
        assert s2.SemanticScholarClient().is_configured is True

    def test_no_key_is_hardcoded_anywhere_in_the_module(self):
        source = Path(s2.__file__).read_text()
        assert "s2k-" not in source

    async def test_the_key_is_sent_as_the_x_api_key_header(self):
        seen: dict[str, str] = {}

        def handler(request):
            seen.update(request.headers)
            return httpx.Response(200, json={"total": 0, "data": []})

        client = s2.SemanticScholarClient(api_key="s2k-test", min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        await client.search_works("x")
        assert seen.get("x-api-key") == "s2k-test"
        await client.close()

    async def test_no_header_is_sent_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("S2_API_KEY", raising=False)
        seen: dict[str, str] = {}

        def handler(request):
            seen.update(request.headers)
            return httpx.Response(200, json={"total": 0, "data": []})

        client = s2.SemanticScholarClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        await client.search_works("x")
        assert "x-api-key" not in seen
        await client.close()


class TestRequestShape:
    async def test_search_requests_the_fields_it_needs(self):
        seen: dict[str, str] = {}

        def handler(request):
            seen.update(dict(request.url.params))
            return httpx.Response(
                200, json=json.loads((FIXTURES / "semantic-scholar-C1.json").read_text())
            )

        client = s2.SemanticScholarClient(api_key="k", min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        works, total = await client.search_works("emotionally focused therapy")
        # Without an explicit fields list the API returns only paperId and title.
        for required in ("externalIds", "publicationTypes", "publicationVenue"):
            assert required in seen["fields"]
        assert len(works) == 5
        assert total is not None
        await client.close()

    async def test_strict_lookup_accepts_the_documented_typed_prefixes(self):
        """Constitution II's multi-prefix carve-out — this is the connector it exists for.

        §5 records the strict endpoint as DOCUMENTED BUT NOT VERIFIED LIVE (every probe
        call 429'd pre-key), so this pins the request shape, not the upstream contract.
        """
        seen: list[str] = []

        def handler(request):
            seen.append(request.url.path)
            return httpx.Response(200, json={"paperId": "a" * 40, "publicationTypes": ["Review"]})

        client = s2.SemanticScholarClient(api_key="k", min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=client.base_url, transport=httpx.MockTransport(handler)
        )
        for prefix in s2.ID_PREFIXES:
            await client.get_work(f"{prefix}X")
        assert [p.split("/paper/")[-1] for p in seen] == [f"{p}X" for p in s2.ID_PREFIXES]
        await client.close()


class TestPreprintIsNeverLaundered:
    """Constitution VII(a). The order of `_TYPE_PRECEDENCE` is load-bearing.

    S2 tags records with several types at once, so a preprint can arrive as
    `['JournalArticle', 'Preprint']`. Resolving JournalArticle first would classify it
    `peer-reviewed-article` — laundering it into standing it does not have.
    """

    def test_a_bare_preprint_classifies_as_preprint(self):
        assert s2.classify({"publicationTypes": ["Preprint"]})[0] is VenueClass.PREPRINT

    @pytest.mark.parametrize(
        "types",
        [
            ["JournalArticle", "Preprint"],
            ["Preprint", "JournalArticle"],
            ["Review", "Preprint"],
            ["Preprint", "Book"],
            ["JournalArticle", "Preprint", "Review"],
        ],
    )
    def test_preprint_outranks_every_other_type_in_any_order(self, types):
        venue, basis = s2.classify({"publicationTypes": types})
        assert venue is VenueClass.PREPRINT, f"{types} laundered into {venue.value}"
        assert venue is not VenueClass.PEER_REVIEWED_ARTICLE
        assert basis is ClassificationBasis.INDEX_ASSERTED

    def test_the_raw_type_list_is_preserved_for_audit(self):
        work = s2.to_work({"publicationTypes": ["JournalArticle", "Preprint"]})
        assert work.venue_class is VenueClass.PREPRINT
        assert "Preprint" in (work.source_type or "")
        assert "JournalArticle" in (work.source_type or "")


class TestAcceptedIdentifierGrammar:
    """Constitution II / R4 — S2 is the connector the multi-prefix carve-out exists for."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("10.1111/famp.12305", "DOI:10.1111/famp.12305"),
            ("DOI:10.1111/famp.12305", "DOI:10.1111/famp.12305"),
            ("CorpusId:44674475", "CorpusId:44674475"),
            ("PMID:28870000", "PMID:28870000"),
            ("ARXIV:2101.00001", "ARXIV:2101.00001"),
            ("MAG:2751133296", "MAG:2751133296"),
            ("a" * 40, "a" * 40),
        ],
    )
    def test_accepted_forms(self, raw, expected):
        assert s2.normalise_identifier(raw) == expected

    @pytest.mark.parametrize(
        "rejected", ["The Heroine's Journey", "", "not-an-id", "10.badprefix/x", "W2409023364"]
    )
    def test_rejected_forms(self, rejected):
        assert s2.normalise_identifier(rejected) is None

    async def test_get_work_refuses_a_non_identifier_rather_than_building_a_bad_url(self):
        client = s2.SemanticScholarClient(api_key="k", min_interval=0.0)
        with pytest.raises(ValueError, match="not an accepted"):
            await client.get_work("The Heroine's Journey")
        await client.close()


class TestKeyVariableAliases:
    @pytest.mark.parametrize("var", s2.API_KEY_VARS)
    def test_each_documented_variable_name_is_honoured(self, var, monkeypatch):
        for name in s2.API_KEY_VARS:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv(var, "s2k-alias")
        assert s2.SemanticScholarClient().is_configured is True

    def test_s2_api_key_is_the_committed_contract_and_wins(self, monkeypatch):
        """`.env.example` and the Layer-1 probe adapter both use S2_API_KEY."""
        assert s2.API_KEY_VARS[0] == "S2_API_KEY"


def _tier0(doi: str) -> Work:
    """A Crossref-shaped result: has a DOI, classified from registered metadata."""
    return Work(
        cross_references=CrossReferences(doi=doi),
        title=f"Tier 0 {doi}",
        venue_class=VenueClass.PEER_REVIEWED_ARTICLE,
        classification_basis=ClassificationBasis.REGISTERED,
        retraction_status=RetractionStatus.NOT_RETRACTED,
    )


def _s2(doi: str | None, corpus: str = "1") -> Work:
    """A Semantic Scholar result. `doi=None` is the unique-reach case."""
    return Work(
        cross_references=CrossReferences(doi=doi, semantic_scholar_id=corpus),
        title=f"S2 {doi or 'doi-less ' + corpus}",
        venue_class=VenueClass.UNVERIFIED,
        classification_basis=ClassificationBasis.NONE,
        retraction_status=RetractionStatus.UNKNOWN,
    )


class TestReservedSlots:
    """AGE-589: how much of a page Semantic Scholar may claim."""

    @pytest.mark.parametrize(
        ("limit", "expected"),
        [(1, 0), (2, 1), (5, 1), (10, 2), (25, 5), (50, 10)],
    )
    def test_one_slot_in_five(self, limit, expected):
        assert _reserved_slots(limit) == expected

    def test_a_single_result_page_belongs_to_tier_0(self):
        """Crossref carries the classification axis; at limit=1 it is the only honest answer."""
        assert _reserved_slots(1) == 0

    def test_reservation_never_consumes_the_whole_page(self):
        for limit in range(1, 51):
            assert _reserved_slots(limit) < limit


class TestSingletonsSurviveTruncation:
    """The defect AGE-589 fixed: appending to the tail is deleting.

    MEASURED 2026-08-16 — `search_works("AEDP transformance", limit=10)` returned ZERO
    DOI-less records through the gateway while the client returned two, because Crossref
    filled all ten slots and the singletons were appended past the cut.
    """

    def test_doi_less_records_survive_a_full_tier_0_page(self):
        base = [_tier0(f"10.1/{i}") for i in range(10)]
        s2_works = [_s2(None, "c1"), _s2(None, "c2"), _s2("10.9/x")]

        out = _fold_in_semanticscholar(base, s2_works, limit=10)

        assert len(out) == 10
        doi_less = [w for w in out if not w.cross_references.doi]
        assert len(doi_less) == 2, "the unique reach must not be truncated away"

    def test_the_regression_shape_exactly(self):
        """Tail-append + truncate would yield zero. Pin the number, not just >0."""
        base = [_tier0(f"10.1/{i}") for i in range(50)]
        out = _fold_in_semanticscholar(base, [_s2(None, "c1")], limit=50)
        assert sum(1 for w in out if not w.cross_references.doi) == 1

    def test_tier_0_keeps_the_majority_of_the_page(self):
        base = [_tier0(f"10.1/{i}") for i in range(10)]
        s2_works = [_s2(None, f"c{i}") for i in range(10)]

        out = _fold_in_semanticscholar(base, s2_works, limit=10)

        assert len(out) == 10
        assert sum(1 for w in out if w.cross_references.doi) == 8
        assert sum(1 for w in out if not w.cross_references.doi) == 2

    def test_doi_less_records_outrank_s2_records_that_have_a_doi(self):
        """No other connector can reach a DOI-less record; a DOI-bearing one they might."""
        base = [_tier0(f"10.1/{i}") for i in range(10)]
        s2_works = [_s2("10.9/a"), _s2("10.9/b"), _s2(None, "c1")]

        out = _fold_in_semanticscholar(base, s2_works, limit=10)

        assert any(not w.cross_references.doi for w in out)

    def test_a_short_tier_0_page_is_backfilled_not_left_short(self):
        base = [_tier0("10.1/only")]
        s2_works = [_s2(None, f"c{i}") for i in range(20)]

        out = _fold_in_semanticscholar(base, s2_works, limit=10)

        assert len(out) == 10, "reserved slots must not cap a page Tier 0 could not fill"

    def test_nothing_is_dropped_when_the_page_is_not_contested(self):
        base = [_tier0("10.1/a")]
        s2_works = [_s2(None, "c1"), _s2("10.9/b")]

        out = _fold_in_semanticscholar(base, s2_works, limit=10)

        assert len(out) == 3

    def test_output_never_exceeds_the_limit(self):
        base = [_tier0(f"10.1/{i}") for i in range(50)]
        s2_works = [_s2(None, f"c{i}") for i in range(50)]
        for limit in (1, 2, 5, 10, 50):
            assert len(_fold_in_semanticscholar(base, s2_works, limit)) == limit


class TestFoldingNeverDisplacesClassification:
    """VII(a)/VII(b): S2's `index-asserted` must never overwrite Crossref's `registered`."""

    def test_a_shared_doi_merges_without_downgrading_the_basis(self):
        base = [_tier0("10.1/shared")]
        out = _fold_in_semanticscholar(base, [_s2("10.1/shared")], limit=10)

        assert len(out) == 1, "a shared DOI is one work, not two"
        assert out[0].classification_basis is ClassificationBasis.REGISTERED
        assert out[0].venue_class is VenueClass.PEER_REVIEWED_ARTICLE

    def test_s2_never_supplies_a_retraction_verdict(self):
        base = [_tier0("10.1/shared")]
        out = _fold_in_semanticscholar(base, [_s2("10.1/shared")], limit=10)
        assert out[0].retraction_status is RetractionStatus.NOT_RETRACTED

    def test_a_doi_less_singleton_keeps_unknown_retraction(self):
        """VII(d): S2 has no retraction signal, and silence is never `not-retracted`."""
        out = _fold_in_semanticscholar([], [_s2(None, "c1")], limit=10)
        assert out[0].retraction_status is RetractionStatus.UNKNOWN

    def test_tier_0_ranking_order_is_preserved(self):
        base = [_tier0(f"10.1/{i}") for i in range(10)]
        out = _fold_in_semanticscholar(base, [_s2(None, "c1")], limit=10)
        kept = [w.cross_references.doi for w in out if w.cross_references.doi]
        assert kept == [f"10.1/{i}" for i in range(len(kept))]

    def test_no_semantic_scholar_results_changes_nothing(self):
        base = [_tier0(f"10.1/{i}") for i in range(10)]
        assert _fold_in_semanticscholar(base, [], limit=10) == base


class TestVenueTypeFallback:
    """AGE-590: `publicationVenue.type` when `publicationTypes` is absent.

    MEASURED 2026-08-16 on the AEDP query — 4 of 5 records carry `publicationTypes: null`,
    and one of those ("Transforming emotional suffering into flourishing", Counselling
    Psychology Quarterly) carries `publicationVenue.type: "journal"`. It was emitting
    `unverified` while the index had said where it appeared.
    """

    def test_journal_venue_classifies_when_no_types_are_supplied(self):
        venue, basis = s2.classify({"publicationVenue": {"type": "journal"}})
        assert venue is VenueClass.PEER_REVIEWED_ARTICLE
        assert basis is ClassificationBasis.INDEX_ASSERTED

    def test_the_measured_record_shape_now_classifies(self):
        record = {
            "title": "Transforming emotional suffering into flourishing",
            "publicationTypes": None,
            "venue": "Counselling Psychology Quarterly",
            "publicationVenue": {"type": "journal"},
            "externalIds": {"DOI": "10.1080/09515070.2019.1642852"},
        }
        work = s2.to_work(record)
        assert work.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert work.classification_basis is ClassificationBasis.INDEX_ASSERTED

    def test_basis_is_index_asserted_never_registered(self):
        """S2 remains an index, not a registration authority — a weaker signal cannot
        produce a stronger basis."""
        _, basis = s2.classify({"publicationVenue": {"type": "journal"}})
        assert basis is not ClassificationBasis.REGISTERED

    def test_the_venue_signal_is_recorded_in_source_type(self):
        """VII(b): the basis must be interpretable. Without this, a venue-derived class is
        indistinguishable from a type-derived one."""
        work = s2.to_work({"publicationVenue": {"type": "journal"}})
        assert work.source_type == "publicationVenue.type=journal"

    def test_case_and_whitespace_are_tolerated(self):
        assert (
            s2.classify({"publicationVenue": {"type": " Journal "}})[0]
            is VenueClass.PEER_REVIEWED_ARTICLE
        )

    @pytest.mark.parametrize("venue_type", ["conference", "book", "bookSeries", "", None])
    def test_unmapped_venue_types_are_never_asserted(self, venue_type):
        """VII(c). A venue's type is not the record's type: a record in a book venue is
        more likely a chapter than a book, and guessing is asserting."""
        venue, basis = s2.classify({"publicationVenue": {"type": venue_type}})
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE


class TestTypesAlwaysOutrankTheVenue:
    def test_publication_types_win_when_both_are_present(self):
        record = {
            "publicationTypes": ["Book"],
            "publicationVenue": {"type": "journal"},
        }
        assert s2.classify(record)[0] is VenueClass.BOOK

    def test_a_preprint_in_a_journal_venue_stays_a_preprint(self):
        """VII(a) laundering, by the other route. The published version's venue must not
        promote the preprint record."""
        record = {
            "publicationTypes": ["Preprint", "JournalArticle"],
            "publicationVenue": {"type": "journal"},
        }
        assert s2.classify(record)[0] is VenueClass.PREPRINT

    @pytest.mark.parametrize("raw", ["Editorial", "LettersAndComments", "News", "Conference"])
    def test_a_refused_type_is_not_upgraded_by_the_venue(self, raw):
        """A record S2 explicitly typed as something we refuse to classify must not be
        promoted by the weaker signal — that would route around VII(c)."""
        record = {"publicationTypes": [raw], "publicationVenue": {"type": "journal"}}
        venue, basis = s2.classify(record)
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE


class TestProvenanceBeatsVenue:
    """Constitution VII(a), finding 1 — applied to the venue signal rather than the DOI."""

    def test_an_arxiv_record_in_a_journal_venue_is_a_preprint(self):
        record = {
            "publicationVenue": {"type": "journal"},
            "externalIds": {"ArXiv": "2301.00001", "DOI": "10.1/published"},
        }
        venue, basis = s2.classify(record)
        assert venue is VenueClass.PREPRINT
        assert basis is ClassificationBasis.INDEX_ASSERTED

    def test_it_is_never_laundered_into_peer_reviewed(self):
        record = {
            "publicationVenue": {"type": "journal"},
            "externalIds": {"ArXiv": "2301.00001"},
        }
        assert s2.classify(record)[0] is not VenueClass.PEER_REVIEWED_ARTICLE

    def test_the_provenance_signal_is_recorded(self):
        work = s2.to_work({"externalIds": {"ArXiv": "2301.00001"}})
        assert work.source_type == "externalIds.ArXiv"

    def test_an_explicit_type_still_wins_over_provenance(self):
        """`publicationTypes` is the strongest signal; this path is only for its absence."""
        record = {"publicationTypes": ["Book"], "externalIds": {"ArXiv": "2301.00001"}}
        assert s2.classify(record)[0] is VenueClass.BOOK


class TestTheFallbackDoesNotRescueTheDoilessRecords:
    """MEASURED 2026-08-16 — and the reason this is recorded rather than fixed.

    Both DOI-less AEDP records carry `publicationTypes`, `venue` AND `publicationVenue` all
    null. Nothing about their class is knowable from this connector, and `unverified` /
    `none` is the correct answer under VII, not a gap to close.
    """

    @pytest.mark.parametrize(
        "record",
        [
            {"title": "AEDP: Transformance In Action", "externalIds": {"CorpusId": 1}},
            {"title": "Transformance : The AEDP", "externalIds": {"CorpusId": 2}},
        ],
    )
    def test_a_metadata_free_record_stays_unverified(self, record):
        work = s2.to_work(record)
        assert work.venue_class is VenueClass.UNVERIFIED
        assert work.classification_basis is ClassificationBasis.NONE

    def test_it_still_survives_as_a_hit(self):
        """VII(b) — the whole point. Unclassifiable is not the same as not found."""
        work = s2.to_work(
            {"title": "AEDP: Transformance In Action", "externalIds": {"CorpusId": 1}}
        )
        assert work.title == "AEDP: Transformance In Action"
        assert work.cross_references.semantic_scholar_id == "1"
