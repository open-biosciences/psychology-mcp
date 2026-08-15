<!--
SYNC IMPACT REPORT
==================
Version: 1.0.0 (initial)

Derived from the Life Sciences MCP Constitution v1.1.0, which governs biosciences-mcp.
Principles I, IV, V, VI transfer with minimal change. Principle II (Fuzzy-to-Fact) needed
a literature-specific identifier story. Principle III (Schema Determinism) needed
substantial extension, because the Layer-1 discovery pass found that literature metadata
fails in ways biomedical entity metadata does not.

Principle VII is NEW and has no biomedical counterpart. It is the one principle written
directly out of measured failure rather than inherited.

Every clause marked "MEASURED" is backed by the 49-cell Layer-1 benchmark in
open-biosciences-plugins → docs/research/connectors/. Clauses without that marker are
inherited or reasoned.

Templates Status:
- plan-template.md - Constitution Check section compatible
- spec-template.md - Requirements format compatible
- tasks-template.md - Phase structure compatible

Follow-up TODOs: None
-->

# Psychology MCP Constitution

Governs `psychology-mcp`, the Layer-2 literature gateway for the psychology, behavioural
and social-science half of the Open Biosciences platform.

Inherits ADRs 001–006 from `biosciences-mcp/docs/adr/accepted/`. Where this document and
an ADR conflict, the ADR wins and this document is amended.

## Core Principles

### I. Async-First Architecture (NON-NEGOTIABLE)

All network I/O MUST use async patterns. Synchronous blocking calls are forbidden in
async contexts.

- All roster connectors (Crossref, OpenAlex, Europe PMC, Semantic Scholar) are REST/JSON
  and MUST use native `httpx` async clients with connection pooling.
- **No `run_in_executor` exception currently applies.** No roster connector ships a
  synchronous SDK. If one is ever added, it inherits ADR-001 §2's batch-tool requirement.

**Rationale:** Agentic concurrency requires non-blocking I/O.

### II. Fuzzy-to-Fact Resolution Protocol

All work lookups MUST follow a bi-modal workflow.

- **Phase 1 (fuzzy):** `search_works(query)` accepts natural language, returns ranked
  candidates.
- **Phase 2 (strict):** `get_work(identifier)` accepts ONLY a resolved identifier. **The
  DOI is the CURIE.**
- A raw string passed to a strict tool MUST return `UNRESOLVED_ENTITY`.

**Identifiers other than the DOI are permitted where a connector supports them** —
Semantic Scholar accepts `CorpusId:`, `PMID:`, `ARXIV:`, `MAG:`. This is not a weakening:
MEASURED, a substantial minority of records carry a registered type and no DOI (~11% of
Europe PMC's sample, 40% of the Semantic Scholar sample), and a DOI-only strict tool
would be unable to retrieve them at all.

**Rationale:** Prevents hallucinated citations — the failure mode with the worst
consequences in this domain.

### III. Schema Determinism (NON-NEGOTIABLE)

- Every work response MUST carry a `cross_references` object conforming to the Literature
  Key Registry. Keys with no value are OMITTED, never null.
- All list tools MUST use the Canonical Pagination Envelope; all errors the Canonical
  Error Envelope (ADR-001 §8, adopted verbatim).
- Protocol types MUST NOT import domain types (ADR-001 §9).
- **`pagination.total_count` is a WITHIN-CONNECTOR signal only.** MEASURED: connector
  result counts differ by three orders of magnitude for identical queries (OpenAlex min 7;
  Crossref min 469,967) because they mean different things by a count. A gateway MUST NOT
  sum, compare, or rank on `total_count` across connectors.

### IV. Token Budgeting

- Batch and search tools MUST accept `slim=True`.
- The literature slim projection is **`doi`, `title`, `venue_class`** — an adaptation of
  ADR-001 §7's `id`/`name`/`score`, not an inheritance. An agent triaging literature needs
  **admissibility alongside relevance**; a score cannot distinguish a peer-reviewed
  article from a blog post.
- Default page size 50 (ADR-001 §5).

### V. Specification-Before-Code

Non-trivial features follow `/speckit.specify` → `/plan` → human approval → `/implement`
(ADR-003). Each connector server gets its own cycle.

### VI. Platform Skill Delegation

Use `scaffold-fastmcp` and the platform skills rather than hand-rolling server structure
(ADR-002).

### VII. Classification Honesty (NON-NEGOTIABLE) — NEW

**The server reports what an item IS and how that was established. It does not assert
what it cannot know, and it does not silently discard what a source told it.**

This principle has no biomedical counterpart. It exists because the Layer-1 pass found
three distinct ways a naive literature classifier produces confident falsehoods.

**(a) Provenance beats identifier resolution.**
MEASURED: a published PsyArXiv preprint's `attributes.doi` holds the *published journal
article's* DOI, so Crossref types it `journal-article`. A DOI-first classifier labels a
preprint `peer-reviewed-article` — **laundering it into standing it does not have**. A
record surfaced by a repository connector, or carrying a preprint source marker, is a
preprint regardless of what its DOI resolves to.

**(b) Every classification carries its basis.**
`classification_basis` ∈ {`provenance`, `registered`, `index-asserted`, `none`}. A record
with a registered type and no DOI is classified `index-asserted` — NOT flattened to
`unverified`. Flattening destroys data the API supplied. Whether `index-asserted` suffices
for a given claim is **consumer editorial policy and MUST NOT be decided here.**

**(c) Three venue classes MUST NOT be asserted from `type`.**
MEASURED: `guideline`, `institute-publication` and `commentary` have no entry in any of
the four connector type vocabularies. A server MUST emit `unverified` with the publisher
string intact and leave these to a consumer-side heuristic. `institute-publication` is the
consequential one — it is defined by *who published*, not what type it is.

**(d) Absence of a signal is not a negative signal.**
MEASURED: OpenAlex reports retraction status always (explicit boolean); Crossref reports
it ONLY in the affirmative; Europe PMC and Semantic Scholar never. Therefore
`retraction_status: not-retracted` MAY only be set from a source that always reports the
field. A record sourced only from Crossref, Europe PMC or Semantic Scholar is `unknown`.
**`unknown` MUST NOT be rendered, defaulted, or summarised as `not-retracted`.**

**(e) A tier records authority, not accessibility.**
A high-authority source that is structurally unreachable stays classified as high
authority and is marked unreachable. Deleting it destroys the knowledge that it is
authoritative; presenting it as retrievable causes retrieval loops that cannot succeed.

**Rationale:** In a domain where output grounds clinical and dissertation claims, a
confidently wrong classification is worse than an honest `unverified`. Every clause above
is a specific way the obvious implementation gets it wrong.

## Forbidden Patterns

| Pattern | Violation | Why Forbidden |
|---|---|---|
| Synchronous blocking in async | `requests.get()` in an async function | Blocks event loop |
| Hardcoded credentials | API keys in source | Security risk |
| Raw strings to strict tools | `get_work("Heroine's Journey")` | Hallucination risk |
| Null cross-references | `"pmid": null` | Token waste; omit the key |
| Skip specification | Code before spec for non-trivial features | Review debt |
| Bypass Platform Skills | Manual scaffolding when a skill exists | Architectural drift |
| Deep JSON nesting | Nested envelope-in-envelope responses | Agent parsing difficulty |
| Unbounded concurrency | `asyncio.gather` over ids without rate limiting | 429 loops, IP bans |
| **Classifying from the discovery route** | `venue_class` influenced by which connector found it | An index is a lookup vehicle, not a peer-review warrant |
| **Cross-connector count comparison** | Ranking or summing `total_count` across sources | MEASURED: three orders of magnitude apart |
| **Asserting an unresolvable class** | `venue_class: institute-publication` from `type` | No connector vocabulary supports it |
| **Defaulting `unknown` to `not-retracted`** | Treating an absent retraction signal as a negative | Silence is not a negative |

## Required Patterns

| Pattern | Applies To | Enforcement |
|---|---|---|
| Canonical Pagination Envelope | All list tools | `/speckit.analyze` |
| Canonical Error Envelope | All error responses | `/speckit.analyze` |
| Cross-reference validation | All registry values | Runtime validation |
| Human approval gate | All non-trivial implementations | `/plan` → approval → `/implement` |
| Async httpx clients | All API wrappers | Code review |
| `slim=True` support | All batch and search tools | Contract tests |
| Per-connector rate limiting | All clients | MEASURED limits differ by orders of magnitude — a shared default is wrong for most. Read `x-rate-limit-*` headers at runtime where published, rather than hardcoding |
| **`classification_basis` on every classified work** | All work responses | Contract tests |
| **Polite-pool contact header** | Crossref, OpenAlex | Both grant materially better throughput for a contact address |

## Governance

This constitution supersedes ad-hoc practice for `psychology-mcp`. It does not supersede
the platform ADRs, which it inherits.

### Amendment Process

1. Propose the amendment with its rationale and, where the claim is empirical, its
   evidence.
2. Bump the version: MAJOR for a removed or reversed principle, MINOR for a new principle
   or materially expanded guidance, PATCH for clarification.
3. Record the change in the Sync Impact Report at the head of this file.
4. Verify the templates still satisfy the Constitution Check.

**Empirical clauses may be amended by measurement.** Any clause marked MEASURED rests on
the Layer-1 benchmark; a later run that contradicts it is grounds for amendment, and the
frozen 12-query benchmark exists so such a run is directly comparable.

### Compliance

- `/speckit.plan` MUST include a Constitution Check against these principles.
- A violation MUST be either fixed or recorded as an explicit, justified deviation in the
  plan's Complexity Tracking section.
- Principle VII violations are **blocking**. A classification defect ships silent and is
  discovered only when someone checks a citation.

### Guidance Documents

- ADRs 001–006: `biosciences-mcp/docs/adr/accepted/`
- Their application here: `docs/adr/README.md`
- Evidence for every MEASURED clause: `open-biosciences-plugins` →
  `docs/research/connectors/` (five dossiers, coverage matrix, envelope design, and
  `probe/CONTROLLER-NOTES.md`)

**Version:** 1.0.0 | **Ratified:** 2026-08-15 | **Last Amended:** 2026-08-15
