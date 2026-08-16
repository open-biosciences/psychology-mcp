"""Tests for the canonical envelopes (ADR-001 Section 8)."""

import pytest

from psychology_mcp.models import ErrorCode, ErrorEnvelope, PaginationEnvelope

pytestmark = pytest.mark.unit


class TestErrorEnvelope:
    def test_unresolved_entity_carries_a_recovery_hint(self):
        """ADR-001 Section 8: recovery_hint is what lets an agent self-heal."""
        env = ErrorEnvelope.unresolved_entity("Heroine's Journey")
        assert env.success is False
        assert env.error.code is ErrorCode.UNRESOLVED_ENTITY
        assert env.error.invalid_input == "Heroine's Journey"
        assert "search_works" in env.error.recovery_hint

    def test_rate_limited_names_the_source(self):
        """Connectors differ sharply: Crossref publishes headers, S2 429s with no Retry-After."""
        env = ErrorEnvelope.rate_limited("Semantic Scholar")
        assert env.error.code is ErrorCode.RATE_LIMITED
        assert "Semantic Scholar" in env.error.message

    def test_rate_limited_uses_retry_after_when_known(self):
        assert (
            "20 seconds"
            in ErrorEnvelope.rate_limited("Crossref", retry_after=20).error.recovery_hint
        )

    def test_upstream_error_names_the_source_and_status(self):
        env = ErrorEnvelope.upstream_error("Europe PMC", 504)
        assert env.error.code is ErrorCode.UPSTREAM_ERROR
        assert "Europe PMC" in env.error.message and "504" in env.error.message


class TestPaginationEnvelope:
    def test_defaults_to_page_size_50(self):
        """ADR-001 Section 5: tools capped at 50 items."""
        assert PaginationEnvelope.create(items=[]).pagination.page_size == 50

    def test_null_cursor_means_end_of_results(self):
        assert PaginationEnvelope.create(items=[1, 2]).pagination.cursor is None

    def test_total_count_is_optional(self):
        """Not every connector reports a total, and the ones that do are not comparable."""
        assert PaginationEnvelope.create(items=[], total_count=None).pagination.total_count is None
        assert (
            PaginationEnvelope.create(items=[], total_count=16523).pagination.total_count == 16523
        )
