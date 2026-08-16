"""OpenAlex connector — the retraction source (AGE-577).

`DECISION.md` §1 names OpenAlex the **sole source of standing `retraction_status`**, and
that is its load-bearing role here. `02-openalex.md` §3 measured `is_retracted` present as
an explicit boolean on 12/12 records — never absent, never null — which is what makes
`NOT_RETRACTED` sayable at all under constitution VII(d).

Three payload details below came from reading the raw fixture, not from the dossier's
field table, and each breaks a plausible implementation:

1. `ids.pmid` is a URL (`https://pubmed.ncbi.nlm.nih.gov/27273169`), not a bare number.
2. `ids.openalex` is a URL (`https://openalex.org/W2409023364`), not a bare `W…` id.
3. `primary_location.source.issn` is a LIST; `issn_l` is the single canonical value.

OpenAlex is an INDEX, not a registration authority, so every classification it yields is
`INDEX_ASSERTED` and never `REGISTERED` — the precedence rule recorded in AGE-575.
"""

import re
from typing import Any

from ..models.cross_references import CrossReferences
from ..models.work import ClassificationBasis, RetractionStatus, VenueClass, Work
from .base import LiteratureClient

BASE_URL = "https://api.openalex.org"

_OPENALEX_ID = re.compile(r"(W\d+)")
_TRAILING_DIGITS = re.compile(r"(\d+)\s*$")

# OpenAlex's `type` vocabulary is COARSER than Crossref's. `article` in particular does not
# distinguish a peer-reviewed journal article from an institutional-repository copy —
# 02-openalex.md §3 records Q3 as a repository record typed `article` with no DOI. Mapping
# `article` straight to peer-reviewed-article would assert peer review OpenAlex never
# claimed, which is the laundering constitution VII(a) exists to prevent. So `article` is
# resolved against the SOURCE type instead; see `classify`.
_TYPE_TO_VENUE: dict[str, VenueClass] = {
    "book": VenueClass.BOOK,
    "book-chapter": VenueClass.BOOK_CHAPTER,
    "preprint": VenueClass.PREPRINT,
    "posted-content": VenueClass.PREPRINT,
    "dissertation": VenueClass.GREY,
    "report": VenueClass.GREY,
    "dataset": VenueClass.GREY,
}


def _source(record: dict[str, Any]) -> dict[str, Any]:
    return ((record.get("primary_location") or {}).get("source") or {}) or {}


def classify(record: dict[str, Any]) -> tuple[VenueClass, ClassificationBasis]:
    """Resolve venue class from OpenAlex's type, corroborated by the source type.

    `type: article` + `primary_location.source.type: journal` is treated as a
    peer-reviewed article. That corroboration is what makes the call honest: the work type
    alone is ambiguous, but a work OpenAlex places in a journal is a journal article by
    OpenAlex's own account.

    MEASURED: all five records in the C1 fixture are `article` in a `journal` source, so
    the positive branch is fixture-verified. The negative branch — `article` in a
    non-journal source resolving to `UNVERIFIED` — is DEFENSIVE and has not been exercised
    against a captured repository payload. Recorded rather than overstated.

    Basis is always `INDEX_ASSERTED`: OpenAlex is an index, not a registration authority.
    """
    raw_type = record.get("type")
    if not raw_type:
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE

    if raw_type == "article":
        if _source(record).get("type") == "journal":
            return VenueClass.PEER_REVIEWED_ARTICLE, ClassificationBasis.INDEX_ASSERTED
        # An article-shaped record that OpenAlex does not place in a journal. The raw type
        # survives on Work.source_type; we simply decline to call it peer-reviewed.
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE

    venue = _TYPE_TO_VENUE.get(raw_type)
    if venue is None:
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE
    return venue, ClassificationBasis.INDEX_ASSERTED


def retraction_status(record: dict[str, Any]) -> RetractionStatus:
    """Read `is_retracted`, which OpenAlex reports as an explicit boolean.

    This is the only connector in the roster that answers "is this retracted?" in BOTH
    directions, which is what permits `NOT_RETRACTED` under constitution VII(d). A missing
    key still yields `UNKNOWN` — the measurement was 12/12 present, not a guarantee.
    """
    value = record.get("is_retracted")
    if value is True:
        return RetractionStatus.RETRACTED
    if value is False:
        return RetractionStatus.NOT_RETRACTED
    return RetractionStatus.UNKNOWN


def _cross_references(record: dict[str, Any]) -> CrossReferences:
    ids = record.get("ids") or {}
    source = _source(record)

    openalex_raw = ids.get("openalex") or record.get("id") or ""
    openalex_match = _OPENALEX_ID.search(str(openalex_raw))

    pmid_match = _TRAILING_DIGITS.search(str(ids.get("pmid") or ""))

    issn_list = source.get("issn") or []
    issn = source.get("issn_l") or (issn_list[0] if issn_list else None)

    return CrossReferences(
        doi=ids.get("doi") or record.get("doi"),
        pmid=pmid_match.group(1) if pmid_match else None,
        pmcid=(str(ids["pmcid"]).rsplit("/", 1)[-1] if ids.get("pmcid") else None),
        openalex_id=openalex_match.group(1) if openalex_match else None,
        issn=issn,
    )


def to_work(record: dict[str, Any]) -> Work:
    """Map one OpenAlex work record into the literature envelope."""
    venue_class, basis = classify(record)
    source = _source(record)
    return Work(
        cross_references=_cross_references(record),
        title=record.get("display_name") or record.get("title"),
        authors=tuple(
            a["author"]["display_name"]
            for a in record.get("authorships") or []
            if (a.get("author") or {}).get("display_name")
        ),
        year=record.get("publication_year"),
        venue_class=venue_class,
        classification_basis=basis,
        source_type=record.get("type"),
        venue=source.get("display_name"),
        publisher=source.get("host_organization_name"),
        retraction_status=retraction_status(record),
        oa_status=(record.get("open_access") or {}).get("oa_status"),
        discovery_route="openalex",
    )


class OpenAlexClient(LiteratureClient):
    """Async OpenAlex client.

    Keyless. The polite pool is entered via a `mailto` parameter, exactly as with Crossref.
    Rate posture is adopted from response headers where OpenAlex publishes them (AGE-576);
    nothing is hardcoded.
    """

    def __init__(self, contact_email: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("min_interval", 0.2)
        kwargs.setdefault("concurrency", 4)
        super().__init__(base_url=BASE_URL, **kwargs)
        self._contact = (contact_email or "").strip()

    def _params(self, extra: dict[str, Any]) -> dict[str, Any]:
        params = dict(extra)
        if self._contact:
            params["mailto"] = self._contact
        return params

    async def search_works(self, query: str, per_page: int = 50) -> tuple[list[Work], int | None]:
        """Phase 1, fuzzy (ADR-001 §3).

        The returned count is `meta.count` — a WITHIN-CONNECTOR signal only. Constitution
        III: never compare or sum it across connectors, which measured three orders of
        magnitude apart for identical queries.
        """
        payload = await self.get_json(
            "/works", params=self._params({"search": query, "per-page": per_page})
        )
        works = [to_work(record) for record in payload.get("results") or []]
        return works, (payload.get("meta") or {}).get("count")

    async def get_work(self, doi: str) -> Work:
        """Phase 2, strict. OpenAlex resolves a DOI directly via the `https://doi.org/` form."""
        return to_work(
            await self.get_json(f"/works/https://doi.org/{doi}", params=self._params({}))
        )
