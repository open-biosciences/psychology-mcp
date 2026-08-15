"""The `Work` domain type — a scholarly item, classified.

A **domain type** (ADR-001 Section 9): may import protocol types; protocol types must
not import it.

Implements the literature envelope specified in
`open-biosciences-plugins` → `docs/research/connectors/06-literature-envelope.md`,
which was written from measured connector behaviour rather than from documentation.

Two rules here exist to fix defects the Layer-1 probe found in the drafted design, and
both are load-bearing — see `VenueClass` and `ClassificationBasis`.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from .cross_references import CrossReferences


class VenueClass(StrEnum):
    """Axis A — what the item IS.

    Resolved server-side from the item's own registered metadata, never from the URL or
    from the index that surfaced it. An index is a lookup vehicle, not a peer-review
    warrant: OpenAlex's top result for a Heroine's-Journey query was that phrase used as
    a STEM-education metaphor, and it is a perfectly well-formed journal article.

    THREE CLASSES ARE NOT RESOLVABLE from any connector's registered type — `GUIDELINE`,
    `INSTITUTE_PUBLICATION`, `COMMENTARY`. No source vocabulary has an entry for them.
    They are reachable only via a consumer-side publisher heuristic (Layer 4). A server
    MUST NOT assert them from `type` alone; emit `UNVERIFIED` with the publisher string
    intact and let the consumer decide.
    """

    PEER_REVIEWED_ARTICLE = "peer-reviewed-article"
    BOOK = "book"
    BOOK_CHAPTER = "book-chapter"
    INSTITUTE_PUBLICATION = "institute-publication"
    PREPRINT = "preprint"
    GUIDELINE = "guideline"
    GREY = "grey"
    COMMENTARY = "commentary"
    UNVERIFIED = "unverified"


class ClassificationBasis(StrEnum):
    """HOW the venue class was established.

    Exists because the drafted design flattened "no DOI" to `unverified`, discarding a
    type the API had already supplied. The probe showed that is a recurring class, not
    an edge case: ~11% of Europe PMC's sampled results and 40% of the Semantic Scholar
    sample carry a registered type with no DOI.

    Carrying the basis preserves the trust distinction a DOI-first rule was protecting
    WITHOUT destroying the data. Whether `INDEX_ASSERTED` is good enough for a given
    claim is consumer editorial policy, and belongs at Layer 4.
    """

    PROVENANCE = "provenance"
    """Established by the record's source, not its identifier. Beats DOI resolution.

    A published PsyArXiv preprint's `attributes.doi` holds the PUBLISHED article's DOI,
    so Crossref types it `journal-article`. A DOI-first order would classify a preprint
    as peer-reviewed — laundering it into peer-reviewed standing, the error direction
    that matters most.
    """

    REGISTERED = "registered"
    """From a DOI-resolved registered type — a registration authority's assertion."""

    INDEX_ASSERTED = "index-asserted"
    """From the connector's own type field, with no DOI — the index's assertion."""

    NONE = "none"
    """No basis. `venue_class` is `UNVERIFIED`."""


class RetractionStatus(StrEnum):
    """Retraction, with the asymmetry the connectors actually exhibit.

    OpenAlex answers "is this retracted?" ALWAYS (`is_retracted`, explicit boolean,
    12/12 in the benchmark). Crossref answers only in the AFFIRMATIVE, via `update-to[]`
    on works that are retracted. Europe PMC and Semantic Scholar never expose it.

    An absent Crossref signal is SILENCE, not a negative. `NOT_RETRACTED` may therefore
    only be set from a source that always reports the field.
    """

    RETRACTED = "retracted"
    NOT_RETRACTED = "not-retracted"
    UNKNOWN = "unknown"
    """No consulted source reports the field. NOT a synonym for not-retracted."""


class Work(BaseModel):
    """A scholarly item in the Agentic-Literature schema (ADR-001 Section 4)."""

    # Identity
    cross_references: CrossReferences = Field(
        default_factory=CrossReferences,
        description="Literature Key Registry — ADR-001 Section 4 mandates this object",
    )
    title: str | None = Field(default=None)
    authors: tuple[str, ...] = Field(default=())
    year: int | None = Field(default=None)

    # Axis A — what it is
    venue_class: VenueClass = Field(default=VenueClass.UNVERIFIED)
    classification_basis: ClassificationBasis = Field(default=ClassificationBasis.NONE)

    # Supporting metadata the classifier used
    source_type: str | None = Field(
        default=None, description="The connector's raw type string, before normalisation"
    )
    venue: str | None = Field(default=None)
    publisher: str | None = Field(
        default=None,
        description="Measured: OpenAlex 12/12, Crossref 12/12, Europe PMC 2/12, S2 never",
    )
    retraction_status: RetractionStatus = Field(default=RetractionStatus.UNKNOWN)
    oa_status: str | None = Field(default=None)

    # Axis B — how we found it. Provenance only; NEVER contributes to venue class or tier.
    discovery_route: str | None = Field(
        default=None,
        description="Connector that surfaced this record. Provenance and ADR-001 Section 6 "
        "triangulation only — must never influence venue_class.",
    )

    def slim(self) -> dict:
        """Slim projection per ADR-001 Section 7.

        ADR-001 specifies id/name/score for biomedical entities; literature needs its
        own triple. `doi`/`title`/`venue_class` lets an agent triage RELEVANCE and
        ADMISSIBILITY together — a score alone cannot distinguish a peer-reviewed
        article from a blog post, and the probe showed connectors readily return
        well-formed records that are the wrong KIND of thing.

        `classification_basis` is deliberately absent: a consumer applying a basis
        policy needs the full record.
        """
        return {
            "doi": self.cross_references.doi,
            "title": self.title,
            "venue_class": self.venue_class.value,
        }
