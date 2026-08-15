"""Models. Protocol types and domain types are kept separate per ADR-001 Section 9."""

from .cross_references import CrossReferences
from .envelopes import ErrorCode, ErrorDetail, ErrorEnvelope, Pagination, PaginationEnvelope
from .work import ClassificationBasis, RetractionStatus, VenueClass, Work

__all__ = [
    # Protocol types
    "CrossReferences",
    "ErrorCode",
    "ErrorDetail",
    "ErrorEnvelope",
    "Pagination",
    "PaginationEnvelope",
    # Domain types
    "ClassificationBasis",
    "RetractionStatus",
    "VenueClass",
    "Work",
]
