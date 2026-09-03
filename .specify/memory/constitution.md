<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.0 → 1.6.1

v1.6.1 (2026-09-03) — PATCH. Principle VIII cited "platform ADR-007" at
`biosciences-mcp/docs/adr/accepted/`, where no such file existed (AGE-690). The platform
document now exists as `biosciences-mcp/docs/adr/proposed/adr-007-v0.1.md`, status
Proposed, drafted from this principle; the citation points at that path and says so. No
clause changes. Guidance Documents gains the same pointer.

First pass of the hand-authored document through `/speckit-constitution`, followed by a
review of the document AS A COMPLIANCE INSTRUMENT rather than as a statement of policy.
The prior versions were written directly and committed to `main` without review; the
source text is retained at `docs/constitution-v1.2.0-hand-authored.md`, marked historical.

A word-level diff of that input against this document confirmed **no clause was dropped**.
Every difference is a command-spelling correction, a pronoun clarification, or a
deliberate amendment reported below.

v1.6.0 (2026-08-16) — MINOR. Adds Principle VIII: Headerless Gateway Rate Resilience
(AGE-592), implementing platform ADR-007.

Written because a governance gap produced real cost: no document defined how a connector
must behave when an upstream throttles WITHOUT publishing a rate posture, so the behaviour
was rediscovered empirically against a live API — including several runs of the frozen
12-query benchmark, which CLAUDE.md forbids re-running casually.

The pattern was already present in the codebase and unread: `errors.py` recorded Semantic
Scholar's headerless 429, `base.py` implemented full-jitter backoff with Retry-After
precedence, `AdaptiveGate.observe` implemented absence-of-signal, and twelve
biosciences-mcp connectors carried the constants. VIII elevates what existed rather than
inventing policy.

Clause (b) is the one that is NOT a restatement: it forbids ratcheting `min_interval`
upward on a headerless 429 without a paired decay, because MEASURED the throttle is
stochastic rather than rate-proportional. The proposed remedy for (a) would have been a
new defect.

MINOR because it adds a principle and its Forbidden/Required rows without removing or
reversing any existing clause.

v1.5.0 (2026-08-15) — MINOR. Records the tracking-system deviation (AGE-581).

Governance gains a **Recorded Deviations** section. Linear sub-issues under AGE-552 are
the roadmap and task tracker, replacing the SpecKit CLI rituals, with Principle V's
specification-before-code discipline preserved as Auditor-set acceptance criteria and a
pre-merge audit gate. Wording supplied by the PM/Auditor and transcribed verbatim; the
reading note beneath it is added so a Constitution Check reports Principle V as SATISFIED
BY DEVIATION rather than silently passing a principle whose named commands were not run.

MINOR because it adds a section and changes how compliance against Principle V is
assessed, without removing or reversing any principle.

v1.4.0 (2026-08-15) — MINOR. Settles one of the two OPEN clauses.

- Principle IV: the slim-vs-`classification_basis` conflict with VII(b) is RESOLVED.
  `Work.slim()` carries `doi`/`title`/`venue_class` and omits the basis; slim is a triage
  projection and is never sufficient for an admissibility decision. Decided by the Tier-0
  specification and recorded in AGE-575; wording approved before transcription here.
  MINOR because it converts an explicitly unsettled clause into a binding rule, and adds
  an obligation on tools returning slim results to say so in their own description.

  VII(e) — whether the envelope carries a reachability field — REMAINS OPEN. It was not
  in scope for Tier 0.

v1.3.1 (2026-08-15) — PATCH. Removes dated build state from a governance document.

v1.3.0 put three expiring facts into the constitution: that `scaffold-fastmcp` was not
installed as of 2026-08-15, that `fastmcp inspect` reported 0 tools, and that the only
deterministic gates were ruff/pyright/25 tests. Each would become false without anyone
amending it — and this document's own premise is that restated facts go stale and then get
recited as fact. The RULES those passages carried are retained in full; the dated
observations move to `CLAUDE.md`, which tracks build state and is expected to churn.
No obligation changed, hence PATCH.

- Principle VI: keeps "this principle MUST name a skill this repo can actually invoke, at
  a stated version"; drops the 2026-08-15 installation status.
- Governance / partial-implementation: keeps "report checked / deferred / uncheckable" and
  "a named enforcement mechanism is a deferral until it has run"; drops the tool count and
  the gate inventory.

v1.3.0 (2026-08-15) — MINOR. Amended after a compliance review found that several
obligations could not be checked, and one governed a concept this repo does not define.

- Principle II: connector specs MUST now declare their accepted identifier grammar.
  Without it, "strict tools accept ONLY a resolved identifier" is unfalsifiable — nothing
  distinguishes a legitimate `CorpusId:` acceptance from a raw string slipping through.
- Principle IV: records the unreconciled tension with VII(b). The slim projection ships
  `venue_class` without `classification_basis`, while VII(b) argues the class is not
  interpretable without the basis. Recorded as OPEN, deliberately not resolved here — it
  is a design question for the Tier-0 specification.
- Principle V: `research.md` MUST record rejected alternatives with their evidence.
  Learned from comparing prior art: `biosciences-mcp` spec 003 §R1 rejected pure-REST for
  ChEMBL and recorded why, and that record is what stayed useful to downstream skill
  authors long after the build.
- Principle VI: flagged as unsatisfiable rather than silently dropped. As observed at the
  time, `scaffold-fastmcp` existed in two versions under `platform-skills/` and neither
  was installed here. (v1.3.1 moved that observation to `CLAUDE.md` and kept the rule.)
- Principle VII(d): adds a scoping rule. A feature whose acceptance criteria include
  retraction MUST include an always-reporting source in the same increment. This makes
  the measured "Crossref and OpenAlex are Tier 0 jointly" finding checkable at plan time
  instead of discoverable at implementation time.
- Principle VII(e): REWRITTEN. It governed "tier", which does not exist in this repo's
  schema — `Work` has no tier field, and the word appears in code only as connector
  ROSTER tiers, a different concept. Its real subject is the Layer-4 source-tier map. Its
  substance is preserved; the claim that the envelope carries reachability metadata is
  now marked OPEN, because DECISION.md §5.1a — the clause's own evidence base — calls it
  "a live design question for the Layer-2 program" rather than a settled rule.
- Governance: adds "Compliance on a partial implementation". A Constitution Check against
  a partial build MUST report checked / deferred / uncheckable rather than passing
  vacuously. Prompted by an observation recorded at the time: `fastmcp inspect
  fastmcp.json` reported 0 tools, so Principles II and IV bound nothing and a naive check
  would have passed trivially.

v1.2.1 (2026-08-15) — PATCH.
- Command references corrected throughout: `/speckit.specify` → `/speckit-specify`,
  `/plan` → `/speckit-plan`, `/implement` → `/speckit-implement`,
  `/speckit.analyze` → `/speckit-analyze`. VERIFIED: `.claude/skills/` installs ten
  hyphenated commands and no dotted ones, so Principle V and the Required Patterns
  enforcement column previously named commands that do not exist in this repo. The
  templates under `.specify/templates/` were checked and contain no dotted references —
  this file was the sole carrier.
- Principle VII: the "— NEW" marker removed from the heading. Its novelty is history and
  belongs in this report, not in a principle name.
- Rationale statements added to Principles III, IV, V and VI, which previously stated
  obligations without them. No obligation changed.
- Version line reformatted to the resolved template's exact form.

Modified principles: none renamed, none redefined. Principle VII heading text shortened.
Added sections: none.
Removed sections: none.

PRIOR HISTORY (retained verbatim in substance)

v1.2.0 (2026-08-15) — MINOR. Amended by measurement, per the amendment clause.
- Principle II: the "40% carry a registered type with no DOI" statistic came from a
  5-record fixture and did not survive the keyed 12-cell run (0 occurrences). Replaced
  with the measured figure: 3 of 12 records carry no DOI at all. Conclusion unchanged.
- Principle VII(b): adds the `none` case. Semantic Scholar's AEDP hit — the only one in
  the candidate set — carries no DOI, type or venue, which is why venue_class and
  classification_basis must be separate fields.

v1.1.0 (2026-08-15) — MINOR, two Required Patterns added:
- Source attribution where a licence demands it. Semantic Scholar's licence requires
  attribution or citation of "The Semantic Scholar Open Data Platform" in published
  material; verified on key issuance, previously recorded as unverified.
- Credentials from the environment, never from source. Reinforces the layer boundary:
  credentials belong to the API layer, not the plugin layer.

v1.0.0 (initial)

Derived from the Life Sciences MCP Constitution v1.1.0, which governs biosciences-mcp.
Principles I, IV, V, VI transfer with minimal change. Principle II (Fuzzy-to-Fact) needed
a literature-specific identifier story. Principle III (Schema Determinism) needed
substantial extension, because the Layer-1 discovery pass found that literature metadata
fails in ways biomedical entity metadata does not.

Principle VII is new to this document and has no biomedical counterpart. It is the one
principle written directly out of measured failure rather than inherited.

Every clause marked "MEASURED" is backed by the 49-cell Layer-1 benchmark in
open-biosciences-plugins → docs/research/connectors/. Clauses without that marker are
inherited or reasoned.

Templates Status (re-verified this pass, not carried forward on assertion):
- plan-template.md — `## Constitution Check` present at line 39, with Complexity Tracking
  for justified deviations at line 108. Compatible.
- spec-template.md — `## Requirements (mandatory)` present at line 81. Compatible.
- tasks-template.md — phase structure present (Setup / Foundational / per-story / Polish).
  Compatible.

Follow-up TODOs: None.
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
MEASURED, **3 of 12 Semantic Scholar top results carry no DOI at all**, and
`semantic_scholar_id` is the only identifier present on every record. A DOI-only strict
tool could not retrieve them — including the sole hit on AEDP transformance, which no
other connector reaches.

**Each connector's specification MUST declare its accepted identifier grammar** — the
exact prefixes and patterns its strict tool resolves. Without that declaration this
principle is unfalsifiable: nothing distinguishes a legitimate `CorpusId:` acceptance from
a raw string that slipped past validation, and `UNRESOLVED_ENTITY` can only be tested
against a grammar that has been written down.

*Amended in v1.2.0 by measurement. The v1.0.0 text cited "40% of the Semantic Scholar
sample carry a registered type and no DOI", extrapolated from a 5-record fixture before
the connector could be measured. The keyed 12-cell run found that shape **0 times** — the
real distribution is 8 with both, 1 with a DOI but no type, 3 with neither. The conclusion
stands; the statistic did not survive measurement, and the record of that is kept
deliberately.*

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

**Rationale:** A response shape that varies by connector forces per-source parsing on the
consumer and defeats the cross-reference agreement that ADR-001 §6 triangulation depends
on. Determinism is what makes two connectors' answers comparable at all — and the
`total_count` carve-out marks the one field where they are not.

### IV. Token Budgeting

- Batch and search tools MUST accept `slim=True`.
- The literature slim projection is **`doi`, `title`, `venue_class`** — an adaptation of
  ADR-001 §7's `id`/`name`/`score`, not an inheritance. An agent triaging literature needs
  **admissibility alongside relevance**; a score cannot distinguish a peer-reviewed
  article from a blog post.
- Default page size 50 (ADR-001 §5).

**Rationale:** Context is the binding constraint on an agent, so the projection decides
what survives truncation. Dropping `venue_class` from the slim form would push the
admissibility judgement onto the full record and, in practice, past the budget.

**SETTLED in v1.4.0** *(was OPEN; resolved by the Tier-0 specification, AGE-575).*

`Work.slim()` carries `doi`/`title`/`venue_class` and omits `classification_basis`. **Slim
is a triage projection and is never sufficient for an admissibility decision; a consumer
applying a basis policy MUST fetch the full record.**

This reconciles IV with VII(b) rather than overriding it. VII(b)'s objection was that a
class without its basis is not an admissibility warrant — which stands. The resolution is
that slim does not claim to be one: it answers "is this worth pulling?", not "may I cite
this?". A tool returning slim results MUST say so in its own description, so the
distinction reaches the agent rather than living only here.

### V. Specification-Before-Code

Non-trivial features follow `/speckit-specify` → `/speckit-plan` → human approval →
`/speckit-implement` (ADR-003).

**One cycle per connector, EXCEPT where a measured dependency makes one connector's
envelope untestable alone.** MEASURED: Crossref and OpenAlex are Tier 0 *jointly*, not
alternatively — Crossref is the sole source of registered `type`, OpenAlex the sole source
of standing `retraction_status`. A Crossref-only increment cannot state a testable
acceptance criterion for retraction. See VII(d).

**`research.md` MUST record rejected alternatives with their evidence**, not only the
option chosen. Prior art: `biosciences-mcp` spec 003 §R1 rejected pure-REST for ChEMBL
because its search required a complex query DSL, and recorded it — that record kept paying
out to downstream skill authors long after the build closed. A rejection without its
evidence gets re-litigated by whoever arrives next.

**Rationale:** Code before specification converts design questions into review debt, where
they are answered under worse conditions and by fewer people.

### VI. Platform Skill Delegation

Use `scaffold-fastmcp` and the platform skills rather than hand-rolling server structure
(ADR-002).

**This principle MUST name a skill that a session in this repo can actually invoke, at a
stated version.** A scaffolding obligation pointing at an uninstalled or
ambiguously-versioned skill is unsatisfiable, and a dead obligation that everyone steps
around teaches that every obligation is optional. Where the named skill is not invocable
here, either install it and name the version, or amend this principle — do not leave it
standing and unmet. Whether it is currently invocable is build state, tracked in
`CLAUDE.md`, not here.

**Rationale:** Hand-rolled structure drifts from the platform's, and the drift is found
only when a consumer written against the platform's shape fails.

### VII. Classification Honesty (NON-NEGOTIABLE)

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
`unverified`. Flattening destroys data the API supplied.

MEASURED, the `none` case matters as much as `index-asserted`: Semantic Scholar's hit on
AEDP transformance — the only such hit in the candidate set — carries no DOI, no type and
no venue. **A hit with no classifiable metadata must survive as a hit.** If `venue_class`
and `classification_basis` were one field, the single most valuable result in the
benchmark would be indistinguishable from a failure to retrieve anything. Whether
`index-asserted` suffices for a given claim is **consumer editorial policy and MUST NOT be
decided here.**

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

**Scoping consequence (added v1.3.0).** A feature whose acceptance criteria include
retraction MUST include an always-reporting source in the same increment. An increment
built on Crossref alone can only ever emit `retracted` or `unknown`, so "retraction is
handled" would be untestable within it. This is what makes Crossref and OpenAlex Tier 0
jointly rather than sequentially, and it is checkable at `/speckit-plan` time.

**(e) Authority and accessibility are different facts.** *(Subject clarified in v1.3.0.)*
This clause governs the **Layer-4 source-tier map** — `psychology-research`'s
`source-tiers.yaml` — and NOT any field of this server's schema. `Work` has no tier field,
and "tier" appears in this codebase only as connector *roster* tiers, an unrelated concept.

A high-authority source that is structurally unreachable stays classified as high
authority and is marked unreachable. Deleting the entry destroys the knowledge that the
source is authoritative; presenting it as retrievable causes retrieval loops that cannot
succeed. MEASURED: `apa.org` is legitimately Tier 1 and reachable for APA's own published
guidance, while `psycnet.apa.org` is Tier-1 authority with **no query API at any access
level** — robots-disallowed, text-mining rights reserved (DECISION.md §5.1).

**OPEN — whether this server's envelope carries a reachability field is NOT settled here.**
DECISION.md §5.1a, this clause's own evidence base, calls that "a live design question for
the Layer-2 program" and offers two homes for it: envelope metadata, or comments in the
tier file. The obligation above binds Layer 4 today; the envelope question belongs to the
Tier-0 specification. The v1.2.0 text asserted a settled rule here, which its evidence did
not support.

**Rationale:** In a domain where output grounds clinical and dissertation claims, a
confidently wrong classification is worse than an honest `unverified`. Every clause above
is a specific way the obvious implementation gets it wrong.

### VIII. Headerless Gateway Rate Resilience

**A connector's rate posture is discovered where the upstream publishes one and declared
where it does not. Silence is never read as permission — in either direction.**

Implements platform **ADR-007** (*Gateway Rate Resilience, Full-Jitter Backoff, and
Headerless Throttle Handling*), which exists as
[`biosciences-mcp/docs/adr/proposed/adr-007-v0.1.md`](https://github.com/open-biosciences/biosciences-mcp/blob/main/docs/adr/proposed/adr-007-v0.1.md)
— status **Proposed** (AGE-690), drafted 2026-09-02 from this principle and its measurements.
This principle binds the psychology instance; the platform document binds the suite once
accepted. Where the two differ, ADR-007 governs and the divergence belongs in
`docs/adr/README.md`, not here.

**(a) Discovered where published; declared where not.**
MEASURED: Crossref publishes `x-rate-limit-limit` / `x-rate-limit-interval`, and its polite-pool
limit moved 3 → 10 req/s inside 24 hours — which is why the posture is read at runtime rather
than hardcoded. Semantic Scholar publishes nothing: a 429 carries only
`x-amzn-errortype: TooManyRequestsException`, with **no `Retry-After` and no `x-rate-limit-*`**.
A connector whose upstream is silent MUST declare its interval from measurement, and MUST say
in the code where the number came from.

**(b) Silence is not permission to speed up, and a throttle is not proof to slow down.**
Absent rate headers leave the posture unchanged — the same rule as VII(d), applied to rate
rather than retraction. The converse binds equally: a headerless 429 MUST NOT ratchet
`min_interval` upward on its own. MEASURED: Semantic Scholar's 429s are **stochastic, not
rate-proportional** — 8-call sweeps drew 4/8 at 2.5s spacing, 2/8 at 4.0s and 4/8 at 6.0s.
A step-up rule fed by that signal climbs on noise with nothing to relax it again. Any adaptive
step-up MUST be paired with an explicit decay and MUST be justified against a measurement
showing the throttle actually tracks the rate.

**(c) Retry constants are the platform's, and divergence is named.**
Full-jitter exponential backoff — `uniform(0, min(base * 2**n, cap))` — with `Retry-After`
taking precedence where it exists. The platform constants are `MAX_RETRIES = 3` (four attempts
including the first), `BACKOFF_FACTOR = 2.0`, `MAX_BACKOFF = 60.0`. A connector MAY diverge on
`backoff_base` **only** where the upstream cannot tell it when to retry, and MUST record the
measurement that set it. Inventing a bespoke attempt count is a violation.

**(d) An exhausted throttle is reported, never swallowed into a silent result.**
Per ADR-001's error table, an upstream 429 surviving the retry budget is `RATE_LIMITED` with
the remedy "retry with backoff". A tool MUST NOT return an empty or partial page that is
indistinguishable from "nothing matched". Where a connector is **additive** and its loss is a
documented degradation — as Semantic Scholar's is, and OpenAlex's is for classification — the
degradation is permitted, but the always-reporting obligations of VII(d) still bind: nothing
learned from a call that did not happen may be asserted.

**(e) A live suite minimises calls; it does not merely space them.**
MEASURED: a per-test fetch against a stochastically throttling upstream failed on a different
random test every run, which is worse than a red suite because it teaches readers to ignore
red. Live integration suites MUST use module-scoped single-fetch fixtures — fetch once, assert
many — and MUST skip on retry-budget exhaustion **narrowed to 429 alone**, so every other
status still fails loudly. Spacing queries further apart is not a substitute; it does not work
against a throttle that is not rate-proportional.

**Rationale:** The failure this prevents is not an outage — it is a suite that is green because
the environment is empty, or a connector that looks reliable until a key exists. Both have
happened here. Every clause is a measurement, and (b) exists specifically because the obvious
remedy for (a) is wrong.

## Forbidden Patterns

| Pattern | Violation | Why Forbidden |
| --- | --- | --- |
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
| **Bespoke retry constants** | A connector inventing its own attempt count instead of the platform's `MAX_RETRIES = 3` | Divergence hides which behaviour is policy and which is a guess (VIII(c)) |
| **Ratcheting `min_interval` on a headerless 429** | Stepping the interval up with no published rate signal and no decay | MEASURED: the throttle is stochastic, so the rule climbs on noise (VIII(b)) |
| **Spacing a live suite instead of shrinking it** | Adding inter-query delays to fix a stochastically throttling upstream | Does not work, and produces a differently-flaky suite each run (VIII(e)) |

## Required Patterns

| Pattern | Applies To | Enforcement |
| --- | --- | --- |
| Canonical Pagination Envelope | All list tools | `/speckit-analyze` |
| Canonical Error Envelope | All error responses | `/speckit-analyze` |
| Cross-reference validation | All registry values | Runtime validation |
| Human approval gate | All non-trivial implementations | `/speckit-plan` → approval → `/speckit-implement` |
| Async httpx clients | All API wrappers | Code review |
| `slim=True` support | All batch and search tools | Contract tests |
| Per-connector rate limiting | All clients | MEASURED limits differ by orders of magnitude — a shared default is wrong for most. Read `x-rate-limit-*` headers at runtime where published; where the upstream publishes nothing, DECLARE the interval from measurement and record where the number came from (VIII(a)) |
| **Full-jitter backoff on the platform constants** | All clients | `uniform(0, min(base * 2**n, cap))`, `Retry-After` first. `MAX_RETRIES = 3`, `BACKOFF_FACTOR = 2.0`, `MAX_BACKOFF = 60.0`. `backoff_base` MAY diverge only where the upstream cannot say when to retry (VIII(c)) |
| **Module-scoped single-fetch live fixtures** | All live integration suites | Fetch once, assert many; skip on retry exhaustion narrowed to 429 alone (VIII(e)) |
| **`classification_basis` on every classified work** | All work responses | Contract tests |
| **Polite-pool contact header** | Crossref, OpenAlex | Both grant materially better throughput for a contact address |
| **Source attribution where a licence requires it** | Semantic Scholar, PubMed, and any connector whose terms demand it | **Semantic Scholar's licence requires attribution or citation of "The Semantic Scholar Open Data Platform" in any published material using its results** (verified 2026-08-15 on key issuance). PubMed's connector already imposes DOI links. These are hard obligations, not courtesies, and they propagate to every downstream consumer of a grounded claim |
| **Credentials from the environment, never from source** | All keyed clients | `.env` is gitignored; `.env.example` carries placeholders only. Credentials belong to this layer — a plugin declares servers by URL and reaches keys via `${VAR}`, `headersHelper` or `userConfig`, and never holds one |

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

- `/speckit-plan` MUST include a Constitution Check against these principles.
- A violation MUST be either fixed or recorded as an explicit, justified deviation in the
  plan's Complexity Tracking section.
- Principle VII violations are **blocking**. A classification defect ships silent and is
  discovered only when someone checks a citation.

### Recorded Deviations

- **Tracking System Deviation**: Per repository decision (2026-08-15), Linear sub-issues
  (`AGE-575`..`AGE-578` under parent `AGE-552`) serve as the feature roadmap and task
  tracking mechanism, replacing SpecKit CLI script rituals while preserving Principle V's
  specification-before-code design discipline and strict audit gates.

  *Reading note:* Principle V and ADR-003 still name the SpecKit commands. Under this
  deviation those name the **discipline**, not the tooling — acceptance criteria are set
  by the Auditor before implementation begins, and every increment is audited against this
  document before merge. A Constitution Check therefore reports Principle V as
  **satisfied by deviation**, not as violated and not as passed unexamined.

### Compliance on a partial implementation

A Constitution Check run against a partial build MUST report each obligation as
**checked**, **deferred** (it binds a component not yet built), or **uncheckable** (no
mechanism exists to test it) — never as a blanket pass. Most obligations here attach to
tools, so while few or none are built a naive check passes vacuously. **A vacuous pass is
worse than a recorded deferral**, because it teaches every later reader that the gate is
decorative. Which obligations are deferred at any given moment is build state, tracked in
`CLAUDE.md`, not here.

An enforcement mechanism named in the Required Patterns table is a **deferral until it has
actually run**, and MUST be reported as one. "Contract tests" names a category, not a
guarantee that the category has members.

Where an obligation CAN be made deterministic, it SHOULD be rather than left to review.
Two standing candidates:

1. **Protocol types must not import domain types (III)** — statically checkable, and
   guarded only by docstrings.
2. **Principle VII's classification rules** — the Layer-1 probe fixtures at
   `open-biosciences-plugins/docs/research/connectors/probe/fixtures/` are verified genuine
   API payloads and can pin VII(a), (c) and (d) as golden tests. A model test can only
   assert the vocabulary is *able* to represent the right answer; a fixture asserts that a
   classifier *chooses* it.

### Guidance Documents

- ADRs 001–006: [`biosciences-mcp/docs/adr/accepted/`](https://github.com/open-biosciences/biosciences-mcp/blob/main/docs/adr/accepted/)
- ADR-007 (Proposed): [`biosciences-mcp/docs/adr/proposed/adr-007-v0.1.md`](https://github.com/open-biosciences/biosciences-mcp/blob/main/docs/adr/proposed/adr-007-v0.1.md)
- Their application here: `docs/adr/README.md`
- Evidence for every MEASURED clause: `open-biosciences-plugins` →
  `docs/research/connectors/` (five dossiers, coverage matrix, envelope design, and
  `probe/CONTROLLER-NOTES.md`)
- `research.md` format precedent: `biosciences-mcp/specs/*/research.md` — numbered
  resolved unknowns, each **Question / Decision / Rationale / Alternatives Considered /
  References**. This is the shape Principle V's rejected-alternatives rule expects
- Constraint-injection precedent: `lifesciences-research/docs/speckit-standard-prompt-v2.md`.
  It prevents specification drift by citing ADRs directly in the `/speckit-specify` prompt.
  **A psychology variant MUST also inject constitution clauses**, because Principle VII has
  no ADR behind it and would otherwise drift out of every spec

**Version**: 1.6.1 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-09-03
