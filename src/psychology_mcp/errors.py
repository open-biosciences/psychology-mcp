"""Mapping upstream failures onto the canonical error envelope (AGE-578).

ADR-001 §8 fixes the error shape; `models/envelopes.py` already provides the constructors.
This module is the single place that decides WHICH constructor an upstream failure maps to,
so the two connectors cannot drift apart on error semantics.

Every envelope carries a `recovery_hint`, which exists so an agent can self-correct rather
than crash (ADR-001 §8).
"""

import httpx

from .models.envelopes import ErrorEnvelope

# The accepted identifier grammar for strict lookups (constitution II, R4).
# A DOI suffix is unconstrained by the DOI spec, so the pattern is deliberately permissive
# after the registrant prefix.
DOI_PATTERN = r"^10\.\d{4,9}/\S+$"


def from_http_error(source: str, exc: httpx.HTTPStatusError) -> ErrorEnvelope:
    """Map an upstream HTTP failure to the canonical envelope.

    `source` is named rather than hardcoded because the Layer-1 probe found connectors
    differ sharply here: Crossref publishes `x-rate-limit-*` headers, while Semantic
    Scholar's unauthenticated pool returned sustained 429 with no `Retry-After`.
    """
    status = exc.response.status_code
    if status == 429:
        retry_after = exc.response.headers.get("retry-after")
        seconds: int | None = None
        if retry_after and retry_after.strip().isdigit():
            seconds = int(retry_after.strip())
        return ErrorEnvelope.rate_limited(source, retry_after=seconds)
    if status == 404:
        return ErrorEnvelope.entity_not_found(str(exc.request.url))
    return ErrorEnvelope.upstream_error(source, status)


def from_transport_error(source: str, exc: httpx.TransportError) -> ErrorEnvelope:
    """Map a transport failure that survived the retry budget (AGE-576)."""
    return ErrorEnvelope.upstream_error(source, 503, detail=f"Transport failure: {exc!r}")
