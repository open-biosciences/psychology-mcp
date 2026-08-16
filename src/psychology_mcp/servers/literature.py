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
from psychology_mcp.errors import DOI_PATTERN, from_http_error, from_transport_error
from psychology_mcp.merge import merge_works
from psychology_mcp.models.envelopes import ErrorEnvelope, PaginationEnvelope
from psychology_mcp.models.work import Work

mcp: FastMCP = FastMCP(name="psychology-literature")

_CONTACT = os.environ.get("PSYCHOLOGY_MCP_CONTACT_EMAIL", "").strip()

_crossref: CrossrefClient | None = None
_openalex: OpenAlexClient | None = None

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

    merged = _merge_by_doi(crossref_works, openalex_works)[:limit]

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
