"""Tier-0 merger — combining Crossref classification with OpenAlex retraction (AGE-577).

Implements the field-level precedence rule recorded in AGE-575:

| Field | Primary | Why |
|---|---|---|
| `venue_class`, `classification_basis` | **Crossref** | sole source of registered types, ISBNs, book canon |
| `retraction_status` | **OpenAlex** | sole source of standing retraction status |
| `cross_references` | **union** | disagreements on a shared key are RECORDED, not overwritten |
| OpenAlex-only records | `index-asserted` | never `registered`; OpenAlex is an index, not a registration authority |

Two behaviours below go beyond the literal rule. Both are flagged rather than buried,
because a merger is exactly where a classification defect would ship silently.

1. **Crossref primary means "primary where Crossref actually classified."** When Crossref
   yields `UNVERIFIED`/`NONE` and OpenAlex has a real class, OpenAlex's is used. Strict
   Crossref-always-wins would discard a type the other API supplied, which constitution
   VII(b) forbids: flattening destroys data. Crossref still wins every contested case.

2. **`RETRACTED` from either connector wins.** OpenAlex is primary for retraction, but a
   Crossref `update-to` retraction block is publisher-asserted affirmative evidence, and
   `02-openalex.md` §3 records that OpenAlex's `true` case was NEVER OBSERVED in the
   benchmark — only the negative case, 12/12. Letting an unexercised `false` overwrite an
   observed `true` would present a retracted work as clean, which is the precise harm
   Principle VII exists to prevent. The asymmetry is deliberate and is the one place this
   module does not defer to the primary.
"""

from dataclasses import dataclass, field

from .models.cross_references import CrossReferences
from .models.work import ClassificationBasis, RetractionStatus, Work


@dataclass(frozen=True)
class FieldConflict:
    """A shared cross-reference key where the two connectors disagreed."""

    key: str
    crossref: str
    openalex: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return f"{self.key}: crossref={self.crossref!r} openalex={self.openalex!r}"


@dataclass(frozen=True)
class MergeResult:
    """The merged work, plus every disagreement observed while merging.

    Conflicts are carried HERE rather than on `Work` deliberately. The envelope's shape is
    a data contract; adding a field to it is a change that belongs to a spec, not to a
    merge function. Recording them alongside satisfies "recorded rather than overwritten"
    without quietly widening the contract.
    """

    work: Work
    conflicts: tuple[FieldConflict, ...] = field(default=())


def _merge_cross_references(
    crossref: CrossReferences, openalex: CrossReferences
) -> tuple[CrossReferences, tuple[FieldConflict, ...]]:
    """Union the two registries, preferring Crossref on a contested key and recording it."""
    left, right = crossref.populated(), openalex.populated()
    merged: dict[str, str] = dict(right)
    conflicts: list[FieldConflict] = []

    for key, value in left.items():
        other = right.get(key)
        if other is not None and other != value:
            conflicts.append(FieldConflict(key=key, crossref=value, openalex=other))
        merged[key] = value

    return CrossReferences(**merged), tuple(conflicts)


def merge_works(crossref: Work | None, openalex: Work | None) -> MergeResult:
    """Combine a Crossref and an OpenAlex view of the same work.

    Either side may be None — a work present in one index and not the other is normal, and
    the surviving record passes through unchanged rather than being downgraded.
    """
    if crossref is None and openalex is None:
        raise ValueError("merge_works requires at least one non-None work")
    if openalex is None:
        assert crossref is not None
        return MergeResult(work=crossref)
    if crossref is None:
        return MergeResult(work=openalex)

    references, conflicts = _merge_cross_references(
        crossref.cross_references, openalex.cross_references
    )

    # Axis A — Crossref primary, but only where Crossref actually classified. See note 1.
    if crossref.classification_basis is ClassificationBasis.NONE:
        venue_class = openalex.venue_class
        basis = openalex.classification_basis
    else:
        venue_class = crossref.venue_class
        basis = crossref.classification_basis

    # Retraction — OpenAlex primary, except that an affirmative RETRACTED always wins.
    # See note 2.
    if RetractionStatus.RETRACTED in (crossref.retraction_status, openalex.retraction_status):
        retraction = RetractionStatus.RETRACTED
    elif openalex.retraction_status is not RetractionStatus.UNKNOWN:
        retraction = openalex.retraction_status
    else:
        retraction = crossref.retraction_status

    return MergeResult(
        work=Work(
            cross_references=references,
            title=crossref.title or openalex.title,
            authors=crossref.authors or openalex.authors,
            year=crossref.year or openalex.year,
            venue_class=venue_class,
            classification_basis=basis,
            # The raw type that BACKS the chosen classification, not an arbitrary pick.
            source_type=(
                openalex.source_type
                if crossref.classification_basis is ClassificationBasis.NONE
                else crossref.source_type
            ),
            venue=crossref.venue or openalex.venue,
            publisher=crossref.publisher or openalex.publisher,
            retraction_status=retraction,
            # Crossref never returns an open-access status (03-crossref.md §3.3).
            oa_status=openalex.oa_status or crossref.oa_status,
            # Provenance only. Constitution VII: an index is a lookup vehicle, and this
            # field MUST NOT influence venue_class.
            discovery_route="crossref+openalex",
        ),
        conflicts=conflicts,
    )
