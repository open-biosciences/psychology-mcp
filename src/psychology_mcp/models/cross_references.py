"""Literature Key Registry — the bibliographic analogue of ADR-001 Appendix A.

A **protocol type** (ADR-001 Section 9): importable by any model, and it must NOT
import a domain type.

Key availability below is **measured**, from the Layer-1 discovery pass
(`open-biosciences-plugins` → `docs/research/connectors/00-coverage-matrix.md` Section 7),
not taken from vendor documentation.
"""

import re

from pydantic import BaseModel, Field, field_validator

# Patterns are deliberately permissive where the identifier space is genuinely open.
# A DOI suffix, in particular, is unconstrained by the DOI spec.
CROSS_REF_PATTERNS = {
    "doi": re.compile(r"^10\.\d{4,9}/\S+$"),
    "pmid": re.compile(r"^\d+$"),
    "pmcid": re.compile(r"^PMC\d+$"),
    "openalex_id": re.compile(r"^W\d+$"),
    "semantic_scholar_id": re.compile(r"^[0-9a-f]{40}$|^\d+$"),
    "arxiv_id": re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$|^[a-z-]+(\.[A-Z]{2})?/\d{7}$"),
    "osf_id": re.compile(r"^[a-z0-9]{5}(_v\d+)?$"),
    "issn": re.compile(r"^\d{4}-\d{3}[\dXx]$"),
    "isbn": re.compile(r"^(?:\d[- ]?){9}[\dXx]$|^(?:\d[- ]?){12}\d$"),
}


class CrossReferences(BaseModel):
    """External identifiers for a work.

    Keys are omitted when no value exists — never null, never empty string
    (ADR-001 Appendix A null-handling policy).

    Measured availability across the 49-cell Layer-1 benchmark:

    | key                 | sole source        | notes                          |
    |---------------------|--------------------|--------------------------------|
    | doi                 | —                  | Crossref 12/12, OpenAlex 11/12  |
    | pmid                | —                  | OpenAlex 7/12, Europe PMC 6/12  |
    | pmcid               | **Europe PMC**     | 7/12                            |
    | openalex_id         | **OpenAlex**       | 12/12                           |
    | semantic_scholar_id | **Semantic Scholar** | 1/1 (coverage unmeasured)     |
    | isbn                | **Crossref**       | 6/12 — the book-canon connector |
    | issn                | —                  | OpenAlex 11/12                  |
    | arxiv_id            | —                  | **never observed**              |
    | osf_id              | —                  | **never observed**              |

    `arxiv_id` and `osf_id` remain in the registry: they were unexercised by the
    benchmark (OSF returned no results at all), which is not evidence of absence.
    """

    doi: str | None = Field(default=None, description="DOI, bare form (10.xxxx/yyyy)")
    pmid: str | None = Field(default=None, description="PubMed ID")
    pmcid: str | None = Field(default=None, description="PubMed Central ID (PMC…)")
    openalex_id: str | None = Field(default=None, description="OpenAlex work ID (W…)")
    semantic_scholar_id: str | None = Field(default=None, description="S2 paperId or CorpusId")
    arxiv_id: str | None = Field(default=None, description="arXiv identifier")
    osf_id: str | None = Field(default=None, description="OSF preprint identifier")
    issn: str | None = Field(default=None, description="ISSN of the containing serial")
    isbn: str | None = Field(default=None, description="ISBN of the containing book")

    @field_validator("doi", mode="before")
    @classmethod
    def _normalise_doi(cls, v: str | None) -> str | None:
        """Strip a resolver prefix. OpenAlex returns https://doi.org/10.x; we store 10.x."""
        if not v:
            return None
        return v.rsplit("doi.org/", 1)[-1].strip()

    @field_validator("pmcid", mode="before")
    @classmethod
    def _normalise_pmcid(cls, v: str | None) -> str | None:
        """Europe PMC returns PMC1234567; accept a bare digit string too."""
        if not v:
            return None
        v = str(v).strip()
        return v if v.upper().startswith("PMC") else f"PMC{v}"

    def populated(self) -> dict[str, str]:
        """Return only the keys that actually resolved, per the null-handling policy."""
        return {k: v for k, v in self.model_dump().items() if v}
