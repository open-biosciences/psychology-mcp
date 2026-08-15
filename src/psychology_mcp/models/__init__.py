"""Models. Protocol types and domain types are kept separate per ADR-001 Section 9."""

from .cross_references import CrossReferences
from .envelopes import ErrorCode, ErrorDetail, ErrorEnvelope, Pagination, PaginationEnvelope
from .work import ClassificationBasis, RetractionStatus, VenueClass, Work

# Protocol types (ADR-001 §9): CrossReferences, ErrorCode, ErrorDetail, ErrorEnvelope,
#   Pagination, PaginationEnvelope — importable by any model, must not import a domain type.
# Domain types: ClassificationBasis, RetractionStatus, VenueClass, Work.
__all__ = [
    "ClassificationBasis",
    "CrossReferences",
    "ErrorCode",
    "ErrorDetail",
    "ErrorEnvelope",
    "Pagination",
    "PaginationEnvelope",
    "RetractionStatus",
    "VenueClass",
    "Work",
]
