"""Crossref connector — the classification source (AGE-577).

Crossref is the DOI registration agency for the majority of scholarly DOIs, which is why
`DECISION.md` §1 names it the **sole source of registered `type`, `isbn`, and book canon**
and why the envelope's classification axis depends on it.

Everything here is grounded in `03-crossref.md`, whose findings were measured live rather
than read from documentation:

- §3.1 — the observed `type` → venue-class table this module implements.
- §3.2 — Crossref anchors 5 of 9 venue classes. The other 4 are NOT resolvable from `type`
  and this module never asserts them (constitution VII(c)).
- §3.4 — retraction rides on `update-to[]` on the work's own record. Zero marginal
  requests. **Affirmative only**: silence is not a negative (constitution VII(d)).
- §5 — `GET /works/{doi}` returns `message` as a single work object, not a list. Verified
  live.
"""

import html
from typing import Any

from ..models.cross_references import CrossReferences
from ..models.work import ClassificationBasis, RetractionStatus, VenueClass, Work
from .base import LiteratureClient

BASE_URL = "https://api.crossref.org"

# From 03-crossref.md §3.1 (observed) and §3.2 (resolvable-from-type analysis).
# Types NOT listed here fall through to UNVERIFIED with `source_type` preserved, which is
# deliberate: constitution VII(b) forbids discarding what the API supplied, and VII(c)
# forbids asserting a class the vocabulary cannot support.
_TYPE_TO_VENUE: dict[str, VenueClass] = {
    "journal-article": VenueClass.PEER_REVIEWED_ARTICLE,
    "book": VenueClass.BOOK,
    "monograph": VenueClass.BOOK,
    "edited-book": VenueClass.BOOK,
    "book-chapter": VenueClass.BOOK_CHAPTER,
    # §3.1 records reference-entry -> book-chapter as a judgment call, medium confidence:
    # an encyclopedia entry has a container-title and functions as a chapter.
    "reference-entry": VenueClass.BOOK_CHAPTER,
    "book-part": VenueClass.BOOK_CHAPTER,
    "book-section": VenueClass.BOOK_CHAPTER,
    # Crossref's dedicated preprint/working-paper wrapper.
    "posted-content": VenueClass.PREPRINT,
    "report": VenueClass.GREY,
    "dissertation": VenueClass.GREY,
    # NOTE: `dataset` is deliberately ABSENT. §3.1 maps it to `grey` at LOW confidence and
    # §3.2 says it "could equally be argued unverified"; the Q3 record typed `dataset` was
    # a clinical-demonstration video catalogue, not scholarly literature. §8 warns a
    # wrapper "should not assume 'has a DOI and a type' is sufficient proof of citable
    # literature". Falling through to UNVERIFIED keeps `source_type` visible for a Layer-4
    # decision instead of asserting a class from a demonstrably heterogeneous type.
}


def _first(value: Any) -> str | None:
    """Crossref returns `title`, `container-title` and `ISSN` as LISTS."""
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def _text(value: Any) -> str | None:
    """First element of a Crossref list field, with HTML entities decoded.

    MEASURED by reading live output: Crossref titles arrive HTML-ESCAPED. A real Q1 result
    came back as `&gt;Finding and Befriending Parts`, and JATS markup (`<i>`, `<sub>`) shows
    up in titles too. Passing that through means an agent reads, quotes, and cites the raw
    entity - a defect invisible to any fixture test that only checks the field is a string.
    """
    raw = _first(value)
    return html.unescape(raw) if raw is not None else None


def _year(item: dict[str, Any]) -> int | None:
    """Extract a publication year from Crossref's nested `date-parts` structure."""
    for key in ("issued", "published", "published-print", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            try:
                return int(parts[0][0])
            except (TypeError, ValueError):
                continue
    return None


def _authors(item: dict[str, Any]) -> tuple[str, ...]:
    names = []
    for author in item.get("author") or []:
        given, family = author.get("given"), author.get("family")
        full = " ".join(p for p in (given, family) if p) or author.get("name")
        if full:
            names.append(full)
    return tuple(names)


def classify(item: dict[str, Any]) -> tuple[VenueClass, ClassificationBasis]:
    """Resolve venue class from Crossref's own registered `type`.

    Crossref is a registration authority, so a type it reports is `REGISTERED` — the
    strongest basis in the vocabulary. An unmapped or absent type yields `UNVERIFIED`
    with basis `NONE`; the raw string survives on `Work.source_type` regardless.
    """
    raw_type = item.get("type")
    if not raw_type:
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE
    venue = _TYPE_TO_VENUE.get(raw_type)
    if venue is None:
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE
    return venue, ClassificationBasis.REGISTERED


def retraction_status(item: dict[str, Any]) -> RetractionStatus:
    """Read retraction from `update-to[]` — AFFIRMATIVE ONLY.

    03-crossref.md §3.4: the retraction notice is a self-referencing block attached to the
    retracted work's own record; `type: "retraction"` is the operative signal. Crossref
    reports retraction only when it is true, so an absent block is SILENCE.

    Constitution VII(d): `NOT_RETRACTED` may only be set from a source that always reports
    the field. Crossref is not such a source, so this function can return `RETRACTED` or
    `UNKNOWN` and never `NOT_RETRACTED`.
    """
    for update in item.get("update-to") or []:
        if "retract" in str(update.get("type", "")).lower():
            return RetractionStatus.RETRACTED
    return RetractionStatus.UNKNOWN


def to_work(item: dict[str, Any]) -> Work:
    """Map one Crossref work record into the literature envelope."""
    venue_class, basis = classify(item)
    return Work(
        cross_references=CrossReferences(
            doi=item.get("DOI"),
            isbn=_first(item.get("ISBN")),
            issn=_first(item.get("ISSN")),
        ),
        title=_text(item.get("title")),
        authors=_authors(item),
        year=_year(item),
        venue_class=venue_class,
        classification_basis=basis,
        source_type=item.get("type"),
        venue=_text(item.get("container-title")),
        publisher=html.unescape(item["publisher"]) if item.get("publisher") else None,
        retraction_status=retraction_status(item),
        discovery_route="crossref",
    )


class CrossrefClient(LiteratureClient):
    """Async Crossref client.

    Starting posture is conservative and gets superseded by the server's own
    `x-rate-limit-*` headers on the first response (AGE-576). Nothing here hardcodes the
    3 req/s observed during discovery — §8 records that as runtime state, not a guarantee.
    """

    def __init__(self, contact_email: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("min_interval", 0.5)
        kwargs.setdefault("concurrency", 2)
        super().__init__(base_url=BASE_URL, **kwargs)
        self._contact = (contact_email or "").strip()

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        """Add the polite-pool `mailto` parameter when a contact address is configured."""
        params = dict(extra)
        if self._contact:
            params["mailto"] = self._contact
        return params

    async def search_works(self, query: str, rows: int = 50) -> tuple[list[Work], int | None]:
        """Phase 1, fuzzy: natural language in, ranked candidates out (ADR-001 §3).

        Returns the works and Crossref's `total-results`. That count is a WITHIN-CONNECTOR
        signal only — constitution III forbids comparing or summing it across connectors.
        """
        payload = await self.get_json("/works", params=self._params({"query": query, "rows": rows}))
        message = payload.get("message") or {}
        works = [to_work(item) for item in message.get("items") or []]
        return works, message.get("total-results")

    async def get_work(self, doi: str) -> Work:
        """Phase 2, strict: a resolved DOI only. The DOI is the CURIE (constitution II).

        03-crossref.md §5: `/works/{doi}` returns `message` as a single work object, not a
        list — verified live, and the reason this does not index into `items`.
        """
        payload = await self.get_json(f"/works/{doi}", params=self._params({}))
        return to_work(payload.get("message") or {})
