"""Tier-0 literature server — the Fuzzy-to-Fact tool surface (AGE-578).

Two tools, per ADR-001 §3:

- `search_works(query)` — Phase 1, fuzzy. Natural language in, ranked candidates out.
- `get_work(doi)` — Phase 2, strict. A resolved DOI only; anything else is
  `UNRESOLVED_ENTITY`.

Both query **Crossref and OpenAlex jointly** and merge, because neither alone makes the
envelope implementable: Crossref is the sole source of registered `type`, OpenAlex the sole
source of standing `retraction_status` (`DECISION.md` §1, constitution VII(d)).

ADR-004 lifecycle: module-level singletons. `@mcp.on_event` is FORBIDDEN.
"""

import asyncio
import os
import re
from typing import Any

import httpx
from fastmcp import FastMCP

# ABSOLUTE imports, deliberately: fastmcp.json loads the gateway BY PATH, so a module
# using relative imports raises "attempted relative import with no known parent" at start-up.
# biosciences-mcp's gateway uses absolute imports for the same reason.
from psychology_mcp.clients.crossref import CrossrefClient
from psychology_mcp.clients.openalex import OpenAlexClient
from psychology_mcp.clients.semanticscholar import SemanticScholarClient
from psychology_mcp.errors import DOI_PATTERN, from_http_error, from_transport_error
from psychology_mcp.merge import merge_works
from psychology_mcp.models.envelopes import ErrorEnvelope, PaginationEnvelope
from psychology_mcp.models.work import RetractionStatus, Work

mcp: FastMCP = FastMCP(name="psychology-literature")

_CONTACT = os.environ.get("PSYCHOLOGY_MCP_CONTACT_EMAIL", "").strip()

_crossref: CrossrefClient | None = None
_openalex: OpenAlexClient | None = None
_semanticscholar: SemanticScholarClient | None = None

# Accepted identifier grammar for the strict tool (constitution II / R4). A bare DOI is
# canonical; the two common decorated forms are normalised rather than rejected, because
# rejecting a `https://doi.org/...` string an agent copied from a search result would be
# pedantry, not safety. Anything else is UNRESOLVED_ENTITY.
_DOI_RE = re.compile(DOI_PATTERN)
_DOI_DECORATION = re.compile(r"^\s*(?:doi:|https?://(?:dx\.)?doi\.org/)", re.IGNORECASE)


def get_crossref() -> CrossrefClient:
    """Module-level singleton (ADR-004)."""
    global _crossref
    if _crossref is None:
        _crossref = CrossrefClient(contact_email=_CONTACT)
    return _crossref


def get_openalex() -> OpenAlexClient:
    """Module-level singleton (ADR-004)."""
    global _openalex
    if _openalex is None:
        _openalex = OpenAlexClient(contact_email=_CONTACT)
    return _openalex


def get_semanticscholar() -> SemanticScholarClient:
    """Module-level singleton (ADR-004).

    Tier 1 and CREDENTIALED. Unlike Crossref and OpenAlex there is no keyless fallback —
    the unauthenticated pool completed zero of twelve benchmark queries across ~1.5h. The
    client reports `is_configured`; callers degrade rather than fail, because Tier 0 still
    serves without it.
    """
    global _semanticscholar
    if _semanticscholar is None:
        _semanticscholar = SemanticScholarClient()
    return _semanticscholar


def normalise_doi(raw: str) -> str | None:
    """Return the bare DOI, or None if the input is not one.

    Accepts `10.x/y`, `doi:10.x/y`, `https://doi.org/10.x/y`. Rejects everything else,
    including a title or an author name — that is Phase 1's job.
    """
    if not raw:
        return None
    candidate = _DOI_DECORATION.sub("", raw).strip()
    return candidate if _DOI_RE.match(candidate) else None


def _merge_by_doi(crossref_works: list[Work], openalex_works: list[Work]) -> list[Work]:
    """Join two result sets on DOI, preserving Crossref's ranking.

    A work present in only one index passes through unchanged rather than being dropped or
    downgraded — constitution VII(b): a hit with no counterpart is still a hit.
    """
    by_doi = {w.cross_references.doi: w for w in openalex_works if w.cross_references.doi}
    merged: list[Work] = []
    matched: set[str] = set()

    for work in crossref_works:
        doi = work.cross_references.doi
        counterpart = by_doi.get(doi) if doi else None
        if counterpart is not None and doi is not None:
            matched.add(doi)
            merged.append(merge_works(work, counterpart).work)
        else:
            merged.append(work)

    merged.extend(
        w
        for w in openalex_works
        if not w.cross_references.doi or w.cross_references.doi not in matched
    )
    return merged


# MEASURED 2026-08-16 (AGE-589): Crossref alone fills every slot for a normal query, so
# appending Semantic Scholar's singletons to the tail and then truncating to `limit` deleted
# 100% of them. `search_works("AEDP transformance", limit=10)` surfaced ZERO DOI-less records
# while the client, called directly, returned two. The unique reach this connector was
# committed for was structurally unreachable through the tool.
#
# One slot in five, so S2 can never flood a page it did not rank.
S2_RESERVED_FRACTION = 5


def _reserved_slots(limit: int) -> int:
    """Slots held back from the Tier-0 ranking for records only Semantic Scholar reaches.

    Never the whole page: Crossref carries the classification axis and is the P1 story, so
    at least one slot always belongs to the Tier-0 ranking. At `limit=1` this is zero, and
    the single result is the Tier-0 top hit.
    """
    if limit <= 1:
        return 0
    return max(1, min(limit // S2_RESERVED_FRACTION, limit - 1))


def _fold_in_semanticscholar(base: list[Work], s2_works: list[Work], limit: int) -> list[Work]:
    """Join Semantic Scholar onto the Tier-0 ranking, reserving slots for its unique reach.

    Two different things happen here and conflating them is what AGE-589 was:

    - A DOI on both sides is a **merge**. `base` stays primary, so Crossref's `registered`
      classification is never displaced by S2's `index-asserted` one, and S2 — which has no
      retraction signal at all — cannot touch that axis either.
    - A record only S2 holds is unique **reach**. Appending it to the tail is equivalent to
      deleting it, because the tail is exactly what `[:limit]` removes.
    """
    by_doi = {w.cross_references.doi: w for w in s2_works if w.cross_references.doi}
    matched: set[str] = set()
    joined: list[Work] = []

    for work in base:
        doi = work.cross_references.doi
        counterpart = by_doi.get(doi) if doi else None
        if counterpart is not None and doi is not None:
            matched.add(doi)
            joined.append(merge_works(work, counterpart).work)
        else:
            joined.append(work)

    # S2-only records, in S2's own rank order. DOI-less first: those are the ones no other
    # connector on the roster can reach at all, and the reason this connector is committed.
    # `sorted` is stable, so S2's ranking survives within each group.
    singletons = sorted(
        (
            w
            for w in s2_works
            if not w.cross_references.doi or w.cross_references.doi not in matched
        ),
        key=lambda w: w.cross_references.doi is not None,
    )

    if len(joined) + len(singletons) <= limit:
        return joined + singletons  # nothing is competing for slots

    reserved = min(_reserved_slots(limit), len(singletons))
    head = joined[: max(0, limit - reserved)]
    # Backfill: a short Tier-0 page must not leave reserved slots empty.
    return head + singletons[: limit - len(head)]


async def _clear_retractions(works: list[Work]) -> list[Work]:
    """Second pass: resolve still-unknown retraction status against OpenAlex (AGE-580).

    MEASURED: Crossref and OpenAlex rank DISJOINT sets for the same query — for the C1
    control, DOI overlap was zero. So the first-pass join leaves most Crossref-sourced
    results with `retraction_status: unknown`, and the joint design's whole point goes
    unrealised on the search path.

    This costs ONE extra call per search, not N: OpenAlex's `filter=doi:A|B|...` takes up
    to 100 values, and search is capped at 50.

    Failure DEGRADES. If the second pass fails, `unknown` stands. It is never upgraded to
    `not-retracted` on the strength of a call that did not happen — constitution VII(d),
    and the single most dangerous shortcut available in this file.
    """
    pending: dict[str, int] = {}
    for index, work in enumerate(works):
        doi = work.cross_references.doi
        if doi and work.retraction_status is RetractionStatus.UNKNOWN:
            pending.setdefault(doi.lower(), index)

    if not pending:
        return works

    try:
        resolved = await get_openalex().get_works_by_doi(list(pending))
    except (httpx.HTTPStatusError, httpx.TransportError):
        return works

    updated = list(works)
    for doi, index in pending.items():
        counterpart = resolved.get(doi)
        if counterpart is not None:
            # Crossref stays primary for classification; this only fills the retraction
            # axis, because merge_works defers to the side that actually classified.
            updated[index] = merge_works(updated[index], counterpart).work
    return updated


@mcp.tool
async def search_works(
    query: str,
    limit: int = 50,
    slim: bool = False,
) -> PaginationEnvelope[Work] | PaginationEnvelope[dict[str, Any]] | ErrorEnvelope:
    """Phase 1 (fuzzy): find scholarly works from a natural-language query.

    Queries Crossref and OpenAlex concurrently and merges on DOI. Every returned work
    carries `venue_class` (what it is) and `classification_basis` (how that was
    established) — read both; a class without its basis is not an admissibility warrant.

    Args:
        query: Natural language. Titles, topics, author names all work.
        limit: Maximum items per connector, capped at 50 per ADR-001 §5.
        slim: If true, return only `doi`/`title`/`venue_class` per work. Slim is a TRIAGE
            projection and is never sufficient for an admissibility decision — a consumer
            applying a `classification_basis` policy must fetch the full record.

    Returns:
        PaginationEnvelope of works, or ErrorEnvelope on failure.

        `pagination.total_count` is deliberately **null**. The two connectors' counts are
        not comparable — the Layer-1 benchmark measured three orders of magnitude between
        them for identical queries — so a merged result has no honest single total, and
        constitution III forbids summing or comparing them. Absence here is a correctness
        decision, not a gap.
    """
    limit = max(1, min(limit, 50))
    crossref, openalex = get_crossref(), get_openalex()

    results = await asyncio.gather(
        crossref.search_works(query, rows=limit),
        openalex.search_works(query, per_page=limit),
        return_exceptions=True,
    )
    crossref_result, openalex_result = results

    # Crossref carries the classification axis; without it there is nothing to classify
    # from, so its failure is the caller's failure.
    if isinstance(crossref_result, BaseException):
        return _as_error("Crossref", crossref_result)

    crossref_works, _crossref_total = crossref_result

    # OpenAlex failing is a DEGRADATION, not a failure: results survive with
    # retraction_status `unknown`, which is exactly what that value is for. Reporting
    # `not-retracted` here instead would be the VII(d) violation.
    openalex_works: list[Work] = []
    if not isinstance(openalex_result, BaseException):
        openalex_works, _openalex_total = openalex_result

    merged = _merge_by_doi(crossref_works, openalex_works)

    # Tier 1, additive. `_fold_in_semanticscholar` keeps the left side primary — Crossref's
    # `registered` classification is never displaced by S2's `index-asserted` one, and S2
    # contributes no retraction signal at all — while RESERVING slots for the records only
    # S2 reaches. It does not reuse `_merge_by_doi`: that join appends singletons to the
    # tail, and the tail is what `[:limit]` deletes (AGE-589).
    #
    # Skipped silently when unconfigured: this is the one credentialed connector, and Tier 0
    # must keep serving without it.
    semanticscholar = get_semanticscholar()
    if semanticscholar.is_configured:
        try:
            s2_works, _s2_total = await semanticscholar.search_works(query, limit=limit)
            merged = _fold_in_semanticscholar(merged, s2_works, limit)
        except (httpx.HTTPStatusError, httpx.TransportError):
            pass

    merged = merged[:limit]
    merged = await _clear_retractions(merged)

    if slim:
        return PaginationEnvelope.create(
            items=[w.slim() for w in merged], total_count=None, page_size=limit
        )
    return PaginationEnvelope.create(items=merged, total_count=None, page_size=limit)


@mcp.tool
async def get_work(doi: str) -> Work | ErrorEnvelope:
    """Phase 2 (strict): retrieve one work by resolved DOI.

    **The DOI is the CURIE** (constitution II). Accepted grammar: a bare `10.x/y`, or the
    `doi:` / `https://doi.org/` decorated forms, which are normalised. A title, an author
    name, or any other free text returns `UNRESOLVED_ENTITY` — call `search_works` first.

    Args:
        doi: A resolved DOI.

    Returns:
        The merged Work — Crossref for classification, OpenAlex for retraction — or an
        ErrorEnvelope. `retraction_status` is never cached and is re-read on every call: a
        work becoming retracted after a cache was populated is the event the field exists
        to report.
    """
    resolved = normalise_doi(doi)
    if resolved is None:
        return ErrorEnvelope.unresolved_entity(doi)

    crossref_result, openalex_result = await asyncio.gather(
        get_crossref().get_work(resolved),
        get_openalex().get_work(resolved),
        return_exceptions=True,
    )

    crossref_work = None if isinstance(crossref_result, BaseException) else crossref_result
    openalex_work = None if isinstance(openalex_result, BaseException) else openalex_result

    if crossref_work is None and openalex_work is None:
        # Both failed. A 404 from both is a genuine miss; anything else is upstream.
        crossref_exc = crossref_result if isinstance(crossref_result, BaseException) else None
        openalex_exc = openalex_result if isinstance(openalex_result, BaseException) else None
        if (
            isinstance(crossref_exc, httpx.HTTPStatusError)
            and crossref_exc.response.status_code == 404
        ):
            return ErrorEnvelope.entity_not_found(resolved)
        return _as_error("Crossref", crossref_exc or openalex_exc)

    return merge_works(crossref_work, openalex_work).work


def _as_error(source: str, exc: BaseException | None) -> ErrorEnvelope:
    if isinstance(exc, httpx.HTTPStatusError):
        return from_http_error(source, exc)
    if isinstance(exc, httpx.TransportError):
        return from_transport_error(source, exc)
    return ErrorEnvelope.upstream_error(source, 500, detail=repr(exc))
