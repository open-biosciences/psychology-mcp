"""Golden-fixture tests for the Tier-0 connectors and merger (AGE-577).

Every payload here is a REAL captured API response (`tests/fixtures/`, provenance in that
directory's README), not a hand-written mock. That distinction is the point: a mock
encodes what the author believed the API returns, and the Layer-1 probe exists precisely
because several such beliefs turned out to be wrong.

No network. Client-level tests use `httpx.MockTransport` fed from the fixtures.
"""

import json
from pathlib import Path

import httpx
import pytest

from psychology_mcp.clients import crossref as cr
from psychology_mcp.clients import openalex as oa
from psychology_mcp.merge import merge_works
from psychology_mcp.models.work import (
    ClassificationBasis,
    RetractionStatus,
    VenueClass,
    Work,
)

pytestmark = pytest.mark.unit

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture(scope="module")
def crossref_items() -> list[dict]:
    return _load("crossref-C1.json")["message"]["items"]


@pytest.fixture(scope="module")
def openalex_records() -> list[dict]:
    return _load("openalex-C1.json")["results"]


class TestFixturesAreRealPayloads:
    """Guard against a fixture being silently replaced by a hand-written stub."""

    def test_crossref_fixture_has_registry_envelope(self, crossref_items):
        assert len(crossref_items) == 5
        assert all("DOI" in item and "type" in item for item in crossref_items)

    def test_openalex_fixture_has_index_envelope(self, openalex_records):
        assert len(openalex_records) == 5
        assert all("is_retracted" in r and "type" in r for r in openalex_records)


class TestCrossrefClassification:
    """03-crossref.md §3.1 — the measured type -> venue-class table."""

    @pytest.mark.parametrize(
        ("raw_type", "expected"),
        [
            ("journal-article", VenueClass.PEER_REVIEWED_ARTICLE),
            ("book", VenueClass.BOOK),
            ("monograph", VenueClass.BOOK),
            ("book-chapter", VenueClass.BOOK_CHAPTER),
            ("reference-entry", VenueClass.BOOK_CHAPTER),
            ("posted-content", VenueClass.PREPRINT),
            ("report", VenueClass.GREY),
            ("dissertation", VenueClass.GREY),
        ],
    )
    def test_registered_types_map_with_registered_basis(self, raw_type, expected):
        venue, basis = cr.classify({"type": raw_type})
        assert venue is expected
        assert basis is ClassificationBasis.REGISTERED

    def test_dataset_is_not_classified(self):
        """§3.2: `dataset` is heterogeneous - the Q3 record was a clinical video catalogue.

        §8 warns a wrapper must not treat "has a DOI and a type" as proof of literature.
        """
        venue, basis = cr.classify({"type": "dataset"})
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE

    @pytest.mark.parametrize(
        "raw_type", ["standard", "other", "peer-review", "proceedings-article"]
    )
    def test_unmapped_types_fall_through_rather_than_guessing(self, raw_type):
        venue, basis = cr.classify({"type": raw_type})
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE

    def test_raw_type_survives_even_when_unclassifiable(self):
        """Constitution VII(b): flattening must not destroy what the API supplied."""
        work = cr.to_work({"type": "standard", "DOI": "10.1000/x"})
        assert work.venue_class is VenueClass.UNVERIFIED
        assert work.source_type == "standard"

    @pytest.mark.parametrize(
        "unresolvable",
        [VenueClass.GUIDELINE, VenueClass.INSTITUTE_PUBLICATION, VenueClass.COMMENTARY],
    )
    def test_never_asserts_the_three_layer4_classes(self, unresolvable, crossref_items):
        """Constitution VII(c): no connector vocabulary supports these."""
        assert unresolvable not in set(cr._TYPE_TO_VENUE.values())
        assert all(cr.to_work(i).venue_class is not unresolvable for i in crossref_items)

    def test_maps_the_real_fixture_items(self, crossref_items):
        works = [cr.to_work(item) for item in crossref_items]
        assert all(w.cross_references.doi for w in works)
        assert all(w.discovery_route == "crossref" for w in works)
        # C1 is Wiebe & Johnson 2016 on EFT; §3.1 records 3 of 5 as book-chapter.
        assert any(w.venue_class is VenueClass.BOOK_CHAPTER for w in works)

    def test_extracts_list_valued_fields(self, crossref_items):
        """Crossref returns title, container-title and ISSN as LISTS, not strings."""
        work = cr.to_work(crossref_items[0])
        assert isinstance(work.title, str)
        assert work.venue is None or isinstance(work.venue, str)


class TestCrossrefRetractionIsAffirmativeOnly:
    """03-crossref.md §3.4 and constitution VII(d)."""

    def test_update_to_retraction_is_detected(self):
        item = {
            "DOI": "10.1016/j.micpro.2020.103768",
            "update-to": [{"DOI": "10.1016/j.micpro.2020.103768", "type": "retraction"}],
        }
        assert cr.retraction_status(item) is RetractionStatus.RETRACTED

    def test_absence_is_unknown_never_not_retracted(self, crossref_items):
        """Silence is not a negative. Crossref reports retraction only in the affirmative."""
        assert cr.retraction_status({"DOI": "10.1000/x"}) is RetractionStatus.UNKNOWN
        statuses = {cr.to_work(i).retraction_status for i in crossref_items}
        assert RetractionStatus.NOT_RETRACTED not in statuses

    def test_an_unrelated_update_type_is_not_a_retraction(self):
        item = {"update-to": [{"type": "correction"}]}
        assert cr.retraction_status(item) is RetractionStatus.UNKNOWN


class TestOpenAlexIdentifierExtraction:
    """The dossier's field table lists these as ids.pmid / ids.openalex - they are URLs."""

    def test_openalex_id_is_extracted_from_a_url(self, openalex_records):
        work = oa.to_work(openalex_records[0])
        assert work.cross_references.openalex_id == "W2409023364"

    def test_pmid_is_extracted_from_a_url_not_stored_raw(self, openalex_records):
        work = oa.to_work(openalex_records[0])
        assert work.cross_references.pmid == "27273169"

    def test_doi_resolver_prefix_is_stripped(self, openalex_records):
        work = oa.to_work(openalex_records[0])
        assert work.cross_references.doi == "10.1111/famp.12229"

    def test_issn_takes_the_canonical_value_from_a_list(self, openalex_records):
        """source.issn is a LIST; issn_l is the single canonical value."""
        work = oa.to_work(openalex_records[0])
        assert work.cross_references.issn == "0014-7370"


class TestOpenAlexClassification:
    """OpenAlex is an INDEX, so its basis is never `registered` (AGE-575 precedence)."""

    def test_article_in_a_journal_is_peer_reviewed_index_asserted(self, openalex_records):
        venue, basis = oa.classify(openalex_records[0])
        assert venue is VenueClass.PEER_REVIEWED_ARTICLE
        assert basis is ClassificationBasis.INDEX_ASSERTED

    def test_article_outside_a_journal_is_not_called_peer_reviewed(self):
        """A repository copy typed `article` must not be laundered into peer review.

        DEFENSIVE branch: no captured repository payload exercises it (see module docstring
        in clients/openalex.py).
        """
        record = {
            "type": "article",
            "primary_location": {"source": {"type": "repository", "display_name": "OSF"}},
        }
        venue, basis = oa.classify(record)
        assert venue is VenueClass.UNVERIFIED
        assert basis is ClassificationBasis.NONE

    def test_article_with_no_source_at_all_is_not_called_peer_reviewed(self):
        venue, _ = oa.classify({"type": "article"})
        assert venue is VenueClass.UNVERIFIED

    def test_never_returns_registered_basis(self, openalex_records):
        bases = {oa.to_work(r).classification_basis for r in openalex_records}
        assert ClassificationBasis.REGISTERED not in bases

    @pytest.mark.parametrize(
        ("raw_type", "expected"),
        [
            ("book", VenueClass.BOOK),
            ("book-chapter", VenueClass.BOOK_CHAPTER),
            ("preprint", VenueClass.PREPRINT),
            ("dissertation", VenueClass.GREY),
        ],
    )
    def test_unambiguous_types_map_directly(self, raw_type, expected):
        venue, basis = oa.classify({"type": raw_type})
        assert venue is expected
        assert basis is ClassificationBasis.INDEX_ASSERTED


class TestOpenAlexRetraction:
    def test_explicit_false_permits_not_retracted(self, openalex_records):
        """The only roster connector that answers in BOTH directions (VII(d))."""
        assert oa.retraction_status(openalex_records[0]) is RetractionStatus.NOT_RETRACTED

    def test_explicit_true_is_retracted(self):
        assert oa.retraction_status({"is_retracted": True}) is RetractionStatus.RETRACTED

    def test_missing_key_is_unknown_not_false(self):
        """12/12 present is a measurement, not a guarantee."""
        assert oa.retraction_status({}) is RetractionStatus.UNKNOWN


class TestMergerPrecedence:
    """The field-level rule approved and recorded in AGE-575."""

    def _pair(self, **kw):
        crossref = Work(
            cross_references=cr.CrossReferences(doi="10.1/x"),
            venue_class=kw.get("cr_venue", VenueClass.BOOK_CHAPTER),
            classification_basis=kw.get("cr_basis", ClassificationBasis.REGISTERED),
            source_type=kw.get("cr_type", "book-chapter"),
            retraction_status=kw.get("cr_retr", RetractionStatus.UNKNOWN),
            discovery_route="crossref",
        )
        openalex = Work(
            cross_references=oa.CrossReferences(doi="10.1/x", openalex_id="W1"),
            venue_class=kw.get("oa_venue", VenueClass.PEER_REVIEWED_ARTICLE),
            classification_basis=kw.get("oa_basis", ClassificationBasis.INDEX_ASSERTED),
            source_type=kw.get("oa_type", "article"),
            retraction_status=kw.get("oa_retr", RetractionStatus.NOT_RETRACTED),
            discovery_route="openalex",
        )
        return crossref, openalex

    def test_crossref_wins_classification(self):
        result = merge_works(*self._pair())
        assert result.work.venue_class is VenueClass.BOOK_CHAPTER
        assert result.work.classification_basis is ClassificationBasis.REGISTERED
        assert result.work.source_type == "book-chapter"

    def test_openalex_wins_retraction(self):
        result = merge_works(*self._pair())
        assert result.work.retraction_status is RetractionStatus.NOT_RETRACTED

    def test_crossref_retraction_is_never_overwritten_by_openalex(self):
        """Deliberate departure from 'OpenAlex primary'.

        OpenAlex's `true` case was never observed in the benchmark; presenting a
        publisher-asserted retraction as clean is the exact harm VII prevents.
        """
        result = merge_works(
            *self._pair(cr_retr=RetractionStatus.RETRACTED, oa_retr=RetractionStatus.NOT_RETRACTED)
        )
        assert result.work.retraction_status is RetractionStatus.RETRACTED

    def test_openalex_classifies_when_crossref_has_no_basis(self):
        """Crossref primary means primary where it actually classified (VII(b))."""
        result = merge_works(
            *self._pair(
                cr_venue=VenueClass.UNVERIFIED,
                cr_basis=ClassificationBasis.NONE,
                cr_type="standard",
            )
        )
        assert result.work.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert result.work.classification_basis is ClassificationBasis.INDEX_ASSERTED
        assert result.work.source_type == "article"

    def test_cross_references_are_unioned(self):
        result = merge_works(*self._pair())
        assert result.work.cross_references.doi == "10.1/x"
        assert result.work.cross_references.openalex_id == "W1"

    def test_a_shared_key_disagreement_is_recorded_not_silently_dropped(self):
        crossref, openalex = self._pair()
        openalex.cross_references.doi = "10.1/DIFFERENT"
        result = merge_works(crossref, openalex)
        assert result.work.cross_references.doi == "10.1/x"
        assert [c.key for c in result.conflicts] == ["doi"]
        assert result.conflicts[0].openalex == "10.1/DIFFERENT"

    def test_discovery_route_records_both_and_does_not_affect_class(self):
        result = merge_works(*self._pair())
        assert result.work.discovery_route == "crossref+openalex"
        assert result.work.venue_class is VenueClass.BOOK_CHAPTER

    def test_a_single_sided_record_survives_unchanged(self):
        crossref, openalex = self._pair()
        assert merge_works(crossref, None).work is crossref
        assert merge_works(None, openalex).work is openalex

    def test_two_missing_sides_is_an_error_not_an_empty_work(self):
        with pytest.raises(ValueError):
            merge_works(None, None)

    def test_merging_the_real_fixtures_end_to_end(self, crossref_items, openalex_records):
        merged = merge_works(cr.to_work(crossref_items[0]), oa.to_work(openalex_records[0]))
        assert merged.work.discovery_route == "crossref+openalex"
        assert merged.work.retraction_status is RetractionStatus.NOT_RETRACTED
        assert merged.work.classification_basis is not ClassificationBasis.NONE


class TestClientsOverMockTransport:
    """Fuzzy-to-Fact shapes (ADR-001 §3), driven by the captured payloads."""

    async def test_crossref_search_returns_works_and_a_within_connector_count(
        self, crossref_items
    ):
        payload = _load("crossref-C1.json")

        def handler(request):
            assert "/works" in request.url.path
            return httpx.Response(200, json=payload)

        client = cr.CrossrefClient(contact_email="a@b.test", min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=cr.BASE_URL, transport=httpx.MockTransport(handler)
        )
        works, total = await client.search_works("emotionally focused therapy")
        assert len(works) == len(crossref_items)
        assert total == payload["message"]["total-results"]
        await client.close()

    async def test_crossref_strict_lookup_reads_a_single_object_not_a_list(self):
        """§5: /works/{doi} returns `message` as one work object."""
        item = _load("crossref-C1.json")["message"]["items"][0]

        def handler(request):
            return httpx.Response(200, json={"status": "ok", "message": item})

        client = cr.CrossrefClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=cr.BASE_URL, transport=httpx.MockTransport(handler)
        )
        work = await client.get_work(item["DOI"])
        assert work.cross_references.doi == item["DOI"]
        await client.close()

    async def test_polite_pool_mailto_is_sent_when_configured(self):
        seen: dict[str, str] = {}

        def handler(request):
            seen.update(dict(request.url.params))
            return httpx.Response(200, json={"message": {"items": []}})

        client = cr.CrossrefClient(contact_email="who@example.test", min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=cr.BASE_URL, transport=httpx.MockTransport(handler)
        )
        await client.search_works("x")
        assert seen.get("mailto") == "who@example.test"
        await client.close()

    async def test_openalex_search_maps_records(self, openalex_records):
        payload = _load("openalex-C1.json")

        def handler(request):
            return httpx.Response(200, json=payload)

        client = oa.OpenAlexClient(min_interval=0.0)
        client._client = httpx.AsyncClient(
            base_url=oa.BASE_URL, transport=httpx.MockTransport(handler)
        )
        works, count = await client.search_works("eft couples")
        assert len(works) == len(openalex_records)
        assert count == payload["meta"]["count"]
        assert works[0].cross_references.openalex_id == "W2409023364"
        await client.close()
