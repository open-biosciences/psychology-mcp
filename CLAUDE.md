# CLAUDE.md — psychology-mcp session entry point

Orientation for a Claude Code session started **in this directory**. Deliberately thin:
it points at the operative documents rather than restating them, because restated rules
go stale and then get recited as fact.

## What this repo is

**Layer 2** for the psychology half of the Open Biosciences platform — FastMCP wrappers
for scholarly literature APIs. The counterpart to `biosciences-mcp`, which `bio-research`
declares.

```
Layer 1  SpecKit discovery      ADRs 001–006 · research.md → spec.md → plan.md → tasks.md
Layer 2  FastMCP implementation biosciences-mcp  ·  psychology-mcp  ← THIS REPO
Layer 3  Plugin manifest        open-biosciences-plugins/*/.mcp.json → the gateway URL
Layer 4  Skills                 bio-research/* · psychology-research/* · consumers
```

**Status: Tier 0 complete (Crossref + OpenAlex jointly, 147 tests green, 2 gateway tools
mounted).** `search_works` and `get_work` are live on the gateway, backed by a
runtime-adaptive rate limiter, the two connectors, and the retraction merger.

Next: Tier 1 (Europe PMC, then Semantic Scholar) mounts **behind the same two tools**, not
as new tool pairs. Open work is tracked in Linear — see **Process** below.

## Read these before designing anything

| Document | Why |
| --- | --- |
| **`.specify/memory/constitution.md`** | **Read first.** Principle VII (Classification Honesty) is NON-NEGOTIABLE and its violations are **blocking**. Clauses marked `MEASURED` rest on evidence and may be amended *by measurement* — v1.2.0 exists because one was contradicted. Clauses marked **`OPEN`** are deliberately unsettled and the Tier-0 spec must settle them |
| `docs/adr/README.md` | ADRs 001–006 are **inherited** from `biosciences-mcp/docs/adr/accepted/`, not forked. Lists the four adaptations that are *not* platform policy |
| `open-biosciences-plugins` → `docs/research/connectors/` | The evidence base. `DECISION.md` for the roster, `06-literature-envelope.md` for the response contract, five dossiers, and `probe/CONTROLLER-NOTES.md` for cross-connector findings |
| `open-biosciences-plugins` → `docs/superpowers/` (`specs/` and `plans/`, dated 2026-08-15) | The Layer-1 spec and plan that **produced** that evidence. Reads as a SpecKit spec already; its Appendix C errata is worth the five minutes |
| `lifesciences-research/docs/speckit-standard-prompt-v2.md` | The constraint-injection pattern. Its "Anti-Patterns" table is the short version of why loose specify prompts fail |
| `biosciences-mcp/specs/003-chembl-mcp-server/research.md` | The `research.md` format, and §R1 is the exemplar of a **recorded rejection** (pure-REST rejected for ChEMBL, with reasons) |

## Build order — settled by measurement, not preference

| Tier | Connector | Why |
| --- | --- | --- |
| **0** | **Crossref + OpenAlex, jointly** | Crossref **classifies** (sole source of registered `type`, `isbn`, book canon, historical primaries). OpenAlex **clears retraction** (sole standing `retraction_status`). Neither alone makes the envelope implementable |
| 1 | Europe PMC | Additive; sole source of `pmcid` |
| 1 | Semantic Scholar | Unique reach — only connector answering AEDP transformance, only route to DOI-less records. **Credentialed**; 1 req/s cumulative |
| — | PsyArXiv/OSF | Not scheduled — substring filter, not an index |
| — | APA PsycNET | **Removed** — no query API at any access level |

**Tier 0 is one feature, not two specs.** Crossref is the P1 user story and the MVP —
`03-crossref.md` §3 has the `type` → venue-class mapping, and §5 records `get_work(doi)`
verified live. But an increment built on Crossref alone can only ever emit `retracted` or
`unknown`, so it cannot state a testable acceptance criterion for retraction (constitution
VII(d)). Splitting Tier 0 into two specs buys parallelism and pays for it with a
half-testable envelope.

**Do not copy the biosciences decomposition.** All 13 biosciences APIs are one-entity,
one-CURIE, `search_X`/`get_X` — which is why a fill-in-the-blank prompt template worked
there. Here all four connectors return the **same** entity (`Work`) keyed by the **same**
identifier (DOI); what differs is which facet each authoritatively supplies. One spec per
connector would produce four servers answering the same question differently.

## Working conventions

- **Branch + PR for everything.** The first six commits went straight to `main`, including
  both constitution versions. That was wrong — the constitution is the artifact that most
  needed review and got none. Don't repeat it.
- **SpecKit is upstream v0.16.4**, pinned to the release tag (not `main`, which is a dev
  build). **Invoke with a hyphen: `/speckit-specify`, not `/speckit.specify`.**
  `biosciences-mcp` still runs a January vintage with the dot syntax — the two repos are on
  different generations. The constitution's own command references were corrected in v1.2.1;
  `docs/adr/README.md` still carries dotted spellings and is the last file that does.
- **Credentials from the environment, never source.** `.env` is gitignored; `.env.example`
  carries placeholders. Credentials belong to this layer — a plugin declares servers by URL
  and reaches keys via `${VAR}`, `headersHelper` or `userConfig`, and never holds one.

## Process — how features are tracked and built

```
Linear Tracking        AGE-552 Sub-Issues (AGE-575 .. AGE-578)
Feature Branches       feat/age-xxx-... (direct implementation + unit/scenario tests)
Audit & Review         PM/Auditor reviews commits against the constitution
Linear Sign-off        PM updates Linear state upon PR merge
```

**Role Division:**

- **Implementer**: Creates clean feature branches, writes code/docs, implements
  unit/scenario tests.
- **PM & Auditor**: Maintains Linear issue states, defines acceptance criteria, audits code
  against `.specify/memory/constitution.md`, and signs off on Linear issues upon PR merge.

This replaces the SpecKit CLI rituals. The deviation is **recorded in the constitution**
under Governance → Recorded Deviations; specification-before-code survives as the Auditor's
acceptance criteria, set before implementation starts.

What has actually been run, with dates and commits: `docs/speckit-process-record.md` (AGE-699).

### Two things from the Layer-1 pass that still bind

Kept because Tier 1 (Europe PMC, Semantic Scholar) will need them, not as process:

- **The 12-query benchmark is the acceptance suite**, pre-registered and frozen (research
  spec §4), with C2 as a hallucination check. **Do not re-run it casually** — it is frozen
  so a later run is comparable, which makes re-running it an amendment-by-measurement act.
  The user-facing outcome is measured too: six questions returned `UNRESOLVED` on
  2026-08-14 because psychology had no Layer 2.
- **`probe/fixtures/*.json` are verified-genuine payloads**, not mocks — the Layer-1 fan-out
  accepted a connector's work only on artefact verification. Two are already vendored into
  `tests/fixtures/`; vendor the rest the same way when a connector needs them, with
  provenance. They are what makes Principle VII test-enforced rather than review-enforced.

## Commands

```bash
uv sync --extra dev                       # REQUIRED FIRST — see the trap below
uv run pytest tests -q                    # full suite (147 unit tests, ~6s)
uv run pytest -m unit -q                  # by marker: unit | integration | e2e
uv run pytest -m crossref -q              # per-connector markers: crossref | openalex |
                                          #   europepmc | semanticscholar
uv run pytest tests/unit/test_work.py -q -k retraction   # one file / one test
uv run ruff check . && uv run ruff format .
uv run pyright                            # currently 0 errors — keep it there
uv run fastmcp inspect fastmcp.json       # gateway surface; catches path-load failures
                                          #   the test suite cannot see (see AGE-579)
uv run fastmcp dev fastmcp.json           # gateway + MCP Inspector
```

**The trap:** `pytest` is only in the `dev` extra. Without `uv sync --extra dev`, `uv run
pytest` silently falls through to a `pytest` on `PATH` running **system Python 3.10**, and
every test module dies at `ModuleNotFoundError: No module named 'psychology_mcp'`. That
reads like broken code and is an unsynced environment. `uv run python` resolves to `.venv`
correctly either way, which is what makes it confusing.

Markers are declared in `pyproject.toml`; the per-connector ones are pre-registered for
servers that do not exist yet, so `-m crossref` selecting nothing is expected, not a fault.

## Code architecture

Four files, and the constraint between them is the whole design (ADR-001 §9):

```
src/psychology_mcp/
├── models/
│   ├── envelopes.py         PROTOCOL — Pagination/Error, verbatim from biosciences-mcp
│   ├── cross_references.py  PROTOCOL — Literature Key Registry, 9 keys
│   └── work.py              DOMAIN   — Work, VenueClass, ClassificationBasis
├── clients/base.py          FROZEN   — async httpx + pooling + polite-pool User-Agent
└── servers/gateway.py       the fastmcp.json entrypoint (`mcp` singleton)
```

- **Protocol types must never import a domain type.** `work.py` imports
  `cross_references.py`; the reverse is a violation. This is what keeps the envelope
  reusable across the platform rather than forked per domain.
- **`clients/base.py` is frozen** so parallel per-connector work never shares a write
  (ADR-006). A connector subclasses `LiteratureClient` and brings **its own rate
  discipline** — measured limits differ by two orders of magnitude, so there is
  deliberately no shared default.
- **`gateway.py` is a module-level singleton.** `@mcp.on_event` is forbidden (ADR-004).
  `fastmcp.json` points at `servers/gateway.py:mcp`; a new connector is *mounted* there,
  and the gateway's `instructions=` string is agent-facing contract text — the
  `total_count` warning in it is load-bearing, not decoration.
- **Two independent fields, never merged:** `venue_class` (what it is) and
  `classification_basis` (how we know). Collapsing them is the defect the probe found —
  see finding 2 below.
- **`Work.slim()` omits the basis, and that is an OPEN conflict, not a settled design.**
  Constitution IV now records it: the projection ships `venue_class` without the basis,
  while VII(b) argues the class is not interpretable without it. Both are pinned by tests
  (`test_slim_omits_classification_basis`). The Tier-0 spec has to settle it — fourth slim
  field, or slim is explicitly triage-only. Don't quietly pick one in code.

## Findings that will bite if you forget them

Each cost a measurement to learn. All are in the constitution; repeated here because they
are the ones an implementer walks into.

1. **Provenance beats DOI resolution.** A published preprint's `attributes.doi` is the
   *journal article's* DOI. Classifying from the DOI **launders a preprint into
   peer-reviewed standing**.
2. **A hit with no classifiable metadata must survive as a hit.** Semantic Scholar's AEDP
   result — the only one in the candidate set — carries no DOI, no type, no venue. If
   `venue_class` and `classification_basis` were one field, the most valuable result in the
   benchmark would be indistinguishable from retrieving nothing.
3. **Absence of a signal is not a negative signal.** Crossref reports retraction *only in
   the affirmative*. `unknown` MUST NOT render as `not-retracted`.
4. **`total_count` is not comparable across connectors** — three orders of magnitude apart
   for identical queries. Never sum, compare, or rank on it.
5. **Three venue classes are unresolvable from any connector** — `guideline`,
   `institute-publication`, `commentary`. Emit `unverified` with the publisher string and
   leave them to Layer 4. Do not assert what no vocabulary supports.
6. **Cache the classification, re-verify the retraction.** Registration metadata is
   effectively immutable; `retraction_status` must never be cached — a work becoming
   retracted after you cached it is the event the field exists to report.

## Open items

**Open decisions:**

- **Principle VI is currently unsatisfiable.** It mandates `scaffold-fastmcp`; the skill
  lives at `platform-skills/.claude/commands/` in **two versions** (v1 and `-v2`) and
  neither is installed in this repo's `.claude/skills/`. Install one and name it in the
  constitution, or amend VI. *(The constitution states the rule — it must name an invocable
  skill at a stated version — and deliberately does not carry this status, which goes
  stale. This line is the status.)*
- **VII(e) remains `OPEN`** — whether the envelope carries a reachability field, inherited
  from `DECISION.md` §5.1a. Not in Tier-0 scope. IV ↔ VII(b) was settled in v1.4.0.

**Compliance status — what a Constitution Check must report today.** The constitution
requires checked / deferred / uncheckable, never a blanket pass; this is the current
inventory, and it lives here because it churns.

- **Checked:** async-first (I); the identifier grammar and `UNRESOLVED_ENTITY` (II, and R4
  is now declared in `servers/literature.py`); envelope shapes and `cross_references`
  omit-not-null (III); `slim=True` and the triage triple (IV); VII(a)–(d) at both model and
  classifier level, via golden fixtures.
- **Satisfied by deviation:** V — see Governance → Recorded Deviations.
- **Deferred:** VI, until a scaffold skill is invocable here. `total_count` non-comparison
  (III) is enforced for the merged path only; a single-connector tool could still expose one.
- **Uncheckable:** the protocol↛domain import rule, still guarded by docstrings only. Making
  it a lint rule or a test remains the cheapest available win.
- **Gates that actually run:** `ruff`, `pyright`, 147 tests. `fastmcp inspect` is not yet in
  CI (AGE-579) — and it caught a start-up failure the whole suite passed through.

**Standing:**

- **Gemini/Antigravity review** of the constitution and
  `06-literature-envelope.md` is wanted before the Tier-0 spec depends on them. Precedent:
  `lifesciences-research/docs/antigravity-validation/`.
- **Batch endpoints:** Crossref has **no** native multi-DOI batch endpoint (verified,
  `03-crossref.md` §6) — a DOI list costs N calls under `x-concurrency-limit: 3`. OpenAlex
  has `filter=ids.openalex:ID1|ID2`. **Europe PMC is still unverified**, and batch is the
  only way to beat Semantic Scholar's per-call budget.
- **Not yet registered** in `open-biosciences.code-workspace` or the Wave 2 table in
  `biosciences-program/README.md`. That waits until a server builds.
- Repo is **private**; making it public would restore branch-protection availability.

## Where to look for what

- "What are the rules?" → `.specify/memory/constitution.md`
- "Which connector, and why?" → `open-biosciences-plugins` → `docs/research/connectors/DECISION.md`
- "What shape does a response take?" → `06-literature-envelope.md`, implemented in `src/psychology_mcp/models/`
- "What did the benchmark actually measure?" → `00-coverage-matrix.md` (60 cells) and the five dossiers
- "Why is this rule here?" → `probe/CONTROLLER-NOTES.md` — cross-connector findings no single dossier could see
- "What process do I follow?" → **Process** above; the format precedent is `biosciences-mcp/specs/*/research.md`
- "Has someone already rejected this option?" → `DECISION.md` §5 and each dossier's §8. PsycNET and PsyArXiv/OSF are *tested* rejections, not assumptions — don't re-litigate them without new evidence
