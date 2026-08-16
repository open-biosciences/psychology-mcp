"""Golden-fixture tests for the Semantic Scholar connector (AGE-588).

The fixture is the **authenticated** C1 capture from the Layer-1 probe — the run that
discharged the connector's condition and measured it 5 hit / 4 partial / 1 miss.

The rules under test are the ones that make this connector worth having, and the ones
that would silently break the envelope if they were wrong.
"""

import json
from pathlib import Path

import httpx
import pytest

from psychology_mcp.clients import semanticscholar as s2
from psychology_mcp.models.work import ClassificationBasis, RetractionStatus, VenueClass

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
