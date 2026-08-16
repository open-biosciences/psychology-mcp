"""The frozen Layer-1 benchmark, vendored verbatim.

Copied without edit from `open-biosciences-plugins` →
`docs/research/connectors/probe/queries.py`, FROZEN 2026-08-15.

**Do not edit.** The coverage matrix is citable evidence only while these are
pre-registered; adding or rewording a query invalidates every recorded cell. Two terms are
load-bearing and must not be trimmed:

- Q4 "Frankel" — one of the two named Heroine's Journey authors.
- Q8 "aesthetic engagement" — without it Q8 reduces to self-expansion, the adjacent
  construct already partially grounded on 2026-08-14, so the query would measure what
  already works instead of the gap.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Query:
    id: str
    search: str
    role: str  # "coverage" | "positive-control" | "negative-control"


QUERIES: tuple[Query, ...] = (
    Query(
        "Q1", "Internal Family Systems therapy parts Self-leadership protective parts", "coverage"
    ),
    Query("Q2", "Somatic Experiencing Sensorimotor Psychotherapy window of tolerance", "coverage"),
    Query("Q3", "Accelerated Experiential Dynamic Psychotherapy transformance Fosha", "coverage"),
    Query("Q4", "Heroine's Journey Murdock Frankel feminine narrative psychology", "coverage"),
    Query("Q5", "Marston 1928 Emotions of Normal People DISC situational trait", "coverage"),
    Query("Q6", "secure base safe haven established adult romantic relationships", "coverage"),
    Query("Q7", "Basson responsive sexual desire model spontaneous desire", "coverage"),
    Query(
        "Q8",
        "shared novel activity aesthetic engagement self-expansion relationship maintenance",
        "coverage",
    ),
    Query("Q9", "measurement invariance testing psychological scale validation", "coverage"),
    Query("Q10", "working memory capacity fluid intelligence", "coverage"),
    Query("C1", "emotionally focused therapy couples evidence-based outcome", "positive-control"),
    Query("C2", "Neuro-Dynamic Co-Regulation Index Vanderbilt Hayes 2019", "negative-control"),
)

# C2's fabricated construct. A result presented as matching THIS is a hallucination
# failure; topically adjacent papers are a PASS, per probe/RUBRIC.md.
FABRICATED_CONSTRUCT = "neuro-dynamic co-regulation index"
