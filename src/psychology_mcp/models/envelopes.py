"""Canonical envelope models per ADR-001 Section 8.

Adopted verbatim in structure from `biosciences_mcp.models.envelopes` — these are
**protocol types** (ADR-001 Section 9) and must not be re-specified per domain. Only
the literature-specific error constructors differ.

- PaginationEnvelope: list/search operations
- ErrorEnvelope: all error responses
"""

from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorCode(StrEnum):
    """Standard error codes from ADR-001 Appendix B."""

    UNRESOLVED_ENTITY = "UNRESOLVED_ENTITY"
    ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
    AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"
    RATE_LIMITED = "RATE_LIMITED"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"
    INVALID_CROSS_REFERENCE = "INVALID_CROSS_REFERENCE"


class ErrorDetail(BaseModel):
    """Error detail object within ErrorEnvelope."""

    code: ErrorCode = Field(description="Error code from registry")
    message: str = Field(description="Human-readable error message")
    recovery_hint: str = Field(description="Agent-actionable guidance for recovery")
    invalid_input: str | None = Field(default=None, description="The input that caused the error")


class ErrorEnvelope(BaseModel):
    """Canonical error envelope per ADR-001 Section 8.

    The recovery_hint field enables agent self-correction rather than a crash.
    """

    success: bool = Field(default=False, description="Always false for errors")
    error: ErrorDetail = Field(description="Error details with recovery hint")

    @classmethod
    def unresolved_entity(cls, invalid_input: str) -> "ErrorEnvelope":
        """Raw string passed to a strict tool. ADR-001 Section 3: the DOI is the CURIE."""
        return cls(
            error=ErrorDetail(
                code=ErrorCode.UNRESOLVED_ENTITY,
                message=f"The input '{invalid_input}' is not a resolved identifier.",
                recovery_hint="Call search_works to resolve a DOI first.",
                invalid_input=invalid_input,
            )
        )

    @classmethod
    def entity_not_found(cls, identifier: str) -> "ErrorEnvelope":
        """Well-formed identifier with no matching record."""
        return cls(
            error=ErrorDetail(
                code=ErrorCode.ENTITY_NOT_FOUND,
                message=f"No work found for identifier '{identifier}'.",
                recovery_hint="Verify the DOI, or search for the work by title.",
                invalid_input=identifier,
            )
        )

    @classmethod
    def rate_limited(cls, source: str, retry_after: int | None = None) -> "ErrorEnvelope":
        """Upstream throttling.

        Named `source` rather than hardcoded: the Layer-1 probe found connectors differ
        sharply here — Crossref publishes x-rate-limit-* headers, while Semantic
        Scholar's unauthenticated pool returned sustained 429 with no Retry-After.
        """
        hint = f"{source} is throttling. Retry after a few seconds."
        if retry_after:
            hint = f"{source} is throttling. Retry after {retry_after} seconds."
        return cls(
            error=ErrorDetail(
                code=ErrorCode.RATE_LIMITED,
                message=f"{source} rate limit exceeded.",
                recovery_hint=hint,
            )
        )

    @classmethod
    def upstream_error(
        cls, source: str, status_code: int, detail: str | None = None
    ) -> "ErrorEnvelope":
        """Upstream API failure."""
        message = f"{source} returned error {status_code}."
        if detail:
            message = f"{message} {detail}"
        return cls(
            error=ErrorDetail(
                code=ErrorCode.UPSTREAM_ERROR,
                message=message,
                recovery_hint=f"{source} may be temporarily unavailable. Retry later.",
            )
        )


class Pagination(BaseModel):
    """Pagination metadata within PaginationEnvelope.

    NOTE on `total_count`: connector result counts are NOT comparable across sources.
    The Layer-1 coverage matrix measured three orders of magnitude between them
    (OpenAlex min 7, Crossref min 469,967) because Crossref's `query=` is a loose OR
    over the whole registry while OpenAlex's `search=` is full-text over an indexed
    corpus. A gateway must never sum, compare, or rank on this field across connectors.
    """

    cursor: str | None = Field(default=None, description="Opaque cursor for next page; null = end")
    total_count: int | None = Field(
        default=None,
        description="Total items if known. WITHIN-CONNECTOR signal only — never comparable across connectors.",
    )
    page_size: int = Field(default=50, description="Items per page")


class PaginationEnvelope(BaseModel, Generic[T]):
    """Canonical pagination envelope per ADR-001 Section 8."""

    items: list[T] = Field(description="Data payload")
    pagination: Pagination = Field(description="Pagination metadata")

    @classmethod
    def create(
        cls,
        items: list[T],
        cursor: str | None = None,
        total_count: int | None = None,
        page_size: int = 50,
    ) -> "PaginationEnvelope[T]":
        """Create a pagination envelope with the given items and metadata."""
        return cls(
            items=items,
            pagination=Pagination(
                cursor=cursor,
                total_count=total_count,
                page_size=page_size,
            ),
        )
