"""Tests for the Literature Key Registry (ADR-001 Appendix A analogue)."""

import pytest

from psychology_mcp.models import CrossReferences

pytestmark = pytest.mark.unit


class TestNormalisation:
    def test_doi_resolver_prefix_is_stripped(self):
        """OpenAlex returns https://doi.org/10.x; the registry stores the bare form."""
        assert CrossReferences(doi="https://doi.org/10.1111/famp.12305").doi == "10.1111/famp.12305"

    def test_bare_doi_is_left_alone(self):
        assert CrossReferences(doi="10.1111/famp.12305").doi == "10.1111/famp.12305"

    def test_pmcid_is_prefixed_when_bare(self):
        """Europe PMC returns PMC1234567, but a bare digit string must not become ambiguous."""
        assert CrossReferences(pmcid="1234567").pmcid == "PMC1234567"
        assert CrossReferences(pmcid="PMC1234567").pmcid == "PMC1234567"


class TestNullHandling:
    def test_absent_keys_are_omitted_not_nulled(self):
        """ADR-001 Appendix A: keys are omitted if no value exists."""
        refs = CrossReferences(doi="10.1111/famp.12305", pmid="28870000")
        assert refs.populated() == {"doi": "10.1111/famp.12305", "pmid": "28870000"}

    def test_empty_registry_populates_to_nothing(self):
        assert CrossReferences().populated() == {}

    def test_empty_string_is_treated_as_absent(self):
        assert CrossReferences(doi="").populated() == {}


class TestRegistryCompleteness:
    def test_all_nine_measured_keys_are_present(self):
        """The registry is fixed by 06-literature-envelope.md Section 5."""
        expected = {
            "doi",
            "pmid",
            "pmcid",
            "openalex_id",
            "semantic_scholar_id",
            "arxiv_id",
            "osf_id",
            "issn",
            "isbn",
        }
        assert set(CrossReferences.model_fields) == expected

    def test_unexercised_keys_are_retained(self):
        """arxiv_id and osf_id were never returned by any connector in the benchmark.

        Unexercised is not absent — OSF returned no results at all, so its own
        identifier was never observed. They stay in the registry.
        """
        refs = CrossReferences(arxiv_id="2301.00001", osf_id="f38rv_v1")
        assert refs.populated() == {"arxiv_id": "2301.00001", "osf_id": "f38rv_v1"}
