"""Tests for the Work domain type.

The rules under test are not stylistic — each was derived from a measured defect in
the Layer-1 discovery pass, and each is cited to where the evidence lives.
"""

import pytest

from psychology_mcp.models import (
    ClassificationBasis,
    CrossReferences,
    RetractionStatus,
    VenueClass,
    Work,
)

pytestmark = pytest.mark.unit


class TestDefaults:
    def test_unclassified_work_is_unverified_with_no_basis(self):
        w = Work()
        assert w.venue_class is VenueClass.UNVERIFIED
        assert w.classification_basis is ClassificationBasis.NONE

    def test_retraction_defaults_to_unknown_not_to_not_retracted(self):
        """UNKNOWN and NOT_RETRACTED are different claims. Silence is not a negative."""
        assert Work().retraction_status is RetractionStatus.UNKNOWN


class TestClassificationBasis:
    def test_type_without_a_doi_is_classifiable_as_index_asserted(self):
        """~11% of Europe PMC and 40% of the S2 sample: registered type, no DOI.

        The drafted design flattened these to unverified, discarding a type the API
        had already supplied.
        """
        w = Work(
            title="A review",
            source_type="review-article",
            venue_class=VenueClass.PEER_REVIEWED_ARTICLE,
            classification_basis=ClassificationBasis.INDEX_ASSERTED,
        )
        assert w.cross_references.doi is None
        assert w.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert w.classification_basis is ClassificationBasis.INDEX_ASSERTED

    def test_provenance_beats_a_doi_that_resolves_to_the_published_article(self):
        """A published PsyArXiv preprint's DOI is the JOURNAL article's DOI.

        Classifying from the DOI would launder a preprint into peer-reviewed standing.
        """
        w = Work(
            title="A preprint later published",
            cross_references=CrossReferences(doi="10.1038/s44271-026-00515-7"),
            source_type="journal-article",  # what the DOI resolves to
            venue_class=VenueClass.PREPRINT,  # what the record actually is
            classification_basis=ClassificationBasis.PROVENANCE,
            discovery_route="psyarxiv-osf",
        )
        assert w.venue_class is VenueClass.PREPRINT
        assert w.classification_basis is ClassificationBasis.PROVENANCE


class TestDiscoveryRouteIsNotTier:
    def test_discovery_route_is_recorded_but_independent_of_venue_class(self):
        """Axis B never contributes to Axis A. An index is not a peer-review warrant."""
        metaphor = Work(
            title="The Heroine's Journey in STEM education outreach",
            venue_class=VenueClass.PEER_REVIEWED_ARTICLE,
            classification_basis=ClassificationBasis.REGISTERED,
            discovery_route="openalex",
        )
        # A well-formed article that is entirely off-topic still classifies by what it IS.
        assert metaphor.venue_class is VenueClass.PEER_REVIEWED_ARTICLE
        assert metaphor.discovery_route == "openalex"


class TestUnresolvableClasses:
    @pytest.mark.parametrize(
        "unresolvable",
        [VenueClass.GUIDELINE, VenueClass.INSTITUTE_PUBLICATION, VenueClass.COMMENTARY],
    )
    def test_the_three_layer4_classes_exist_in_the_enum(self, unresolvable):
        """They are representable, but no connector's `type` can assert them.

        A server must reach them only via a consumer-side publisher heuristic; the enum
        carries them so Layer 4 has a vocabulary to write back into.
        """
        assert Work(venue_class=unresolvable).venue_class is unresolvable


class TestSlim:
    def test_slim_projection_is_doi_title_venue_class(self):
        """ADR-001 Section 7. Literature needs admissibility, not just a relevance score."""
        w = Work(
            title="Emotions of normal people.",
            cross_references=CrossReferences(doi="10.1037/13390-000"),
            venue_class=VenueClass.BOOK,
            classification_basis=ClassificationBasis.REGISTERED,
        )
        assert w.slim() == {
            "doi": "10.1037/13390-000",
            "title": "Emotions of normal people.",
            "venue_class": "book",
        }

    def test_slim_omits_classification_basis(self):
        """A consumer applying a basis policy needs the full record, not the projection."""
        assert "classification_basis" not in Work().slim()
