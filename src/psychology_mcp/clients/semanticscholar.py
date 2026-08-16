"""Semantic Scholar connector — unique reach, and the DOI-less route (AGE-588).

`DECISION.md` §1 records this as **wrap — condition discharged**: the key was issued
2026-08-15, the frozen benchmark was re-run **authenticated**, and it measured
**5 hit / 4 partial / 1 miss — second only to Crossref**. It is committed Tier 1, not
optional.

What it uniquely brings (`01-semantic-scholar.md` §3, §8):

- **The richest identifier crosswalk in the candidate set** — DOI + PubMed id + a stable
  corpus id + ISSN in ONE response. No other probed connector supplies that crosswalk
  together, which is what makes it the triangulation source under ADR-001 §6.
- **The only route to DOI-less records.** §3(c): 2 of 5 sampled records carry a registered
  `publicationTypes` and NO DOI. That is precisely the case `ClassificationBasis`
  `INDEX_ASSERTED` was created for — the constitution's VII(b) argument is unreachable
  without this connector.
- **The only connector answering Q3** (AEDP transformance), returning Fosha's own work.

What it does NOT bring, and must never be asked for:

- **`publisher` is never supplied** — 0 of 5, null on every record (§3(b)). Venue classes
  defined by *who published* — `institute-publication` above all — are unreachable here.
- **No retraction signal at all.** `retraction_status` is therefore always `UNKNOWN`;
  constitution VII(d) forbids ever reading that silence as `not-retracted`.

Two operating constraints, both MEASURED and both tighter than the rest of the roster:

1. **1 request/second CUMULATIVE across all endpoints.** A 12-cell run at 1.2s spacing
   passed; a detail pass at 1.3s drew a 429 on its *second* call. **2.5s is the
   observed-safe interval** for sustained sequential use, and concurrency is 1 — the limit
   is cumulative, so parallelism buys nothing and costs 429s.
2. **The unauthenticated tier is unusable** — zero of twelve benchmark queries completed
   across three windows spanning ~1.5h, because the anonymous pool is shared globally and
   saturated by other people's traffic. There is no keyless fallback: without a key this
   connector does not function, unlike Tier 0 which is keyless by design.

**ATTRIBUTION IS A LICENCE OBLIGATION** (constitution Required Patterns): published
material using these results must credit Semantic Scholar or cite "The Semantic Scholar
Open Data Platform". It propagates to every downstream consumer of a grounded claim.
"""

import os
import re
from typing import Any

from ..models.cross_references import CrossReferences
from ..models.work import ClassificationBasis, RetractionStatus, VenueClass, Work
from .base import LiteratureClient

BASE_URL = "https://api.semanticscholar.org/graph/v1"

# Requested explicitly; the API returns only `paperId` and `title` otherwise.
FIELDS = (
    "paperId,title,year,authors,venue,publicationTypes,publicationVenue,externalIds,openAccessPdf"
)

# MEASURED (01-semantic-scholar.md §1): 1 req/s CUMULATIVE across all endpoints.
# 1.2s survived a 12-cell run; 1.3s drew a 429 on the second call of a detail pass.
# 2.5s is the observed-safe sustained interval. Concurrency is 1 because the limit is
# cumulative — parallel calls cannot help and reliably produce 429s.
SAFE_INTERVAL_SECONDS = 2.5

# The typed prefixes the strict endpoint documents. This is the multi-prefix grammar
# constitution II carves out — and the reason that carve-out exists at all.
# `01-semantic-scholar.md` §5: DOCUMENTED BUT NOT VERIFIED LIVE (every probe call 429'd
# before a key was issued). Treated as documented, not as measured.
ID_PREFIXES = ("DOI:", "CorpusId:", "PMID:", "ARXIV:", "MAG:")

# `.env.example` and the Layer-1 probe adapter both use S2_API_KEY, so it is the committed
# contract and is checked first. The longer spellings are accepted so a deployment
# configured under either name still works rather than silently running unauthenticated —
# which for this connector means not working at all.
API_KEY_VARS = (
    "S2_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "PSYCHOLOGY_MCP_SEMANTIC_SCHOLAR_API_KEY",
)


def _key_from_environment() -> str:
    for name in API_KEY_VARS:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def normalise_identifier(raw: str) -> str | None:
    """Return an identifier the strict endpoint accepts, or None if it is not one.

    This is Semantic Scholar's half of the accepted-identifier grammar constitution II
    requires each connector to declare — and the reason the multi-prefix carve-out exists
    at all, since S2 is the only roster connector reaching records that have no DOI.

    Accepted: an already-prefixed form (`DOI:`, `CorpusId:`, `PMID:`, `ARXIV:`, `MAG:`),
    a bare 40-hex paperId, or a bare DOI (which is prefixed for you).
    """
    if not raw:
        return None
    candidate = raw.strip()
    if any(candidate.upper().startswith(p.upper()) for p in ID_PREFIXES):
        return candidate
    if _PAPER_ID.match(candidate):
        return candidate
    if re.match(r"^10\.\d{4,9}/\S+$", candidate):
        return f"DOI:{candidate}"
    return None


_PAPER_ID = re.compile(r"^[0-9a-f]{40}$")

# publicationTypes is a LIST and records carry several at once (the C1 fixture has
# ['JournalArticle', 'ClinicalTrial']). Resolution is by precedence, most specific first.
# Semantic Scholar is an INDEX, never a registration authority, so every classification
# it yields is INDEX_ASSERTED — never REGISTERED.
_TYPE_PRECEDENCE: tuple[tuple[str, VenueClass], ...] = (
    # PREPRINT OUTRANKS EVERYTHING, and the order here is load-bearing.
    # S2 tags records with several types at once, so a preprint can arrive as
    # ['JournalArticle', 'Preprint']. Resolving JournalArticle first would classify it
    # `peer-reviewed-article` — laundering a preprint into standing it does not have,
    # which is precisely the failure constitution VII(a) exists to prevent. Once a record
    # says it is a preprint, nothing else it claims can outrank that.
    ("Preprint", VenueClass.PREPRINT),
    ("Book", VenueClass.BOOK),
    ("BookSection", VenueClass.BOOK_CHAPTER),
    ("JournalArticle", VenueClass.PEER_REVIEWED_ARTICLE),
    ("Review", VenueClass.PEER_REVIEWED_ARTICLE),
    ("Dataset", VenueClass.GREY),
    # Deliberately ABSENT: Editorial, LettersAndComments, News, Conference, Study,
    # ClinicalTrial, CaseReport, MetaAnalysis.
    #
    # Editorial and LettersAndComments look like `commentary`, and asserting that would
    # violate constitution VII(c) — no connector vocabulary supports it, and S2 supplies
    # no publisher to corroborate. They fall through to UNVERIFIED with the raw type
    # preserved, for a Layer-4 heuristic to judge.
)


def _first_type(record: dict[str, Any]) -> str | None:
    types = record.get("publicationTypes") or []
    return ",".join(str(t) for t in types) if types else None


def classify(record: dict[str, Any]) -> tuple[VenueClass, ClassificationBasis]:
    """Resolve venue class from `publicationTypes`, by precedence.

    **The DOI is irrelevant here, and that is the point.** §3(c) found 2 of 5 records with
    a registered type and no DOI. Under a DOI-first rule those are untierable even though
    the API told us what they are; constitution VII(b) exists to stop that, and this is the
    connector where the rule earns its keep.
    """
    types = record.get("publicationTypes") or []
    if not types:
        return VenueClass.UNVERIFIED, ClassificationBasis.NONE
    present = {str(t) for t in types}
    for name, venue_class in _TYPE_PRECEDENCE:
        if name in present:
            return venue_class, ClassificationBasis.INDEX_ASSERTED
    return VenueClass.UNVERIFIED, ClassificationBasis.NONE


def retraction_status(record: dict[str, Any]) -> RetractionStatus:
    """Always UNKNOWN. Semantic Scholar supplies no retraction signal (§3, 0 of 5).

    Constitution VII(d): silence is not a negative. This connector can never contribute
    `not-retracted`, and a work seen only here must not be reported as clean.
    """
    return RetractionStatus.UNKNOWN


def _cross_references(record: dict[str, Any]) -> CrossReferences:
    ids = record.get("externalIds") or {}
    venue_obj = record.get("publicationVenue") or {}

    # semantic_scholar_id accepts a 40-hex paperId or a bare CorpusId digit string.
    paper_id = str(record.get("paperId") or "")
    corpus = ids.get("CorpusId")
    s2_id = paper_id if _PAPER_ID.match(paper_id) else (str(corpus) if corpus else None)

    issn = venue_obj.get("issn")
    if isinstance(issn, list):
        issn = issn[0] if issn else None

    pmcid = ids.get("PubMedCentral")
    return CrossReferences(
        doi=ids.get("DOI"),
        pmid=str(ids["PubMed"]) if ids.get("PubMed") else None,
        pmcid=str(pmcid) if pmcid else None,
        semantic_scholar_id=s2_id,
        arxiv_id=ids.get("ArXiv"),
        issn=issn,
    )


def to_work(record: dict[str, Any]) -> Work:
    """Map one Semantic Scholar paper into the literature envelope."""
    venue_class, basis = classify(record)
    venue_obj = record.get("publicationVenue") or {}
    return Work(
        cross_references=_cross_references(record),
        title=record.get("title"),
        authors=tuple(
            a["name"] for a in record.get("authors") or [] if isinstance(a, dict) and a.get("name")
        ),
        year=record.get("year"),
        venue_class=venue_class,
        classification_basis=basis,
        source_type=_first_type(record),
        venue=record.get("venue") or venue_obj.get("name"),
        # MEASURED 0/5 — S2 never supplies a publisher. Read anyway so the field is not
        # silently dropped if that ever changes.
        publisher=venue_obj.get("publisher"),
        retraction_status=retraction_status(record),
        oa_status=(record.get("openAccessPdf") or {}).get("status"),
        discovery_route="semanticscholar",
    )


class SemanticScholarClient(LiteratureClient):
    """Async Semantic Scholar client. **Credentialed — there is no keyless fallback.**

    The starting posture is deliberately the measured safe interval rather than the base
    default: this connector's limit is an order of magnitude tighter than Crossref's, and
    it is cumulative across endpoints, so concurrency is pinned to 1.
    """

    def __init__(self, api_key: str | None = None, **kwargs: Any) -> None:
        kwargs.setdefault("min_interval", SAFE_INTERVAL_SECONDS)
        kwargs.setdefault("concurrency", 1)
        super().__init__(base_url=BASE_URL, **kwargs)
        # Credentials from the environment, never from source (constitution Required
        # Patterns). `S2_API_KEY` is the name used by `.env.example` and by the Layer-1
        # probe adapter.
        self._api_key = (api_key if api_key is not None else _key_from_environment()).strip()

    @property
    def is_configured(self) -> bool:
        """Whether a key is present. Without one this connector cannot function.

        Callers should degrade rather than fail: Tier 0 is keyless and still serves.
        """
        return bool(self._api_key)

    async def _get_client(self) -> Any:
        client = await super()._get_client()
        if self._api_key:
            client.headers["x-api-key"] = self._api_key
        return client

    async def search_works(self, query: str, limit: int = 50) -> tuple[list[Work], int | None]:
        """Phase 1, fuzzy (ADR-001 §3).

        Returns the works and S2's `total`. That count is a WITHIN-CONNECTOR signal only —
        constitution III forbids comparing or summing it across connectors.
        """
        payload = await self.get_json(
            "/paper/search", params={"query": query, "limit": limit, "fields": FIELDS}
        )
        works = [to_work(record) for record in payload.get("data") or []]
        return works, payload.get("total")

    async def get_work(self, identifier: str) -> Work:
        """Phase 2, strict — accepts the documented typed prefixes.

        `01-semantic-scholar.md` §5 records the strict endpoint as **documented but not
        verified live**: every probe call returned 429 before the key was issued. Treat a
        failure here as an unverified-contract finding, not a client bug.
        """
        resolved = normalise_identifier(identifier)
        if resolved is None:
            raise ValueError(
                f"{identifier!r} is not an accepted Semantic Scholar identifier. "
                f"Use a bare DOI, a 40-hex paperId, or one of {', '.join(ID_PREFIXES)}"
            )
        return to_work(await self.get_json(f"/paper/{resolved}", params={"fields": FIELDS}))
