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

**Status: scaffolded, no connector servers built.** The protocol layer is implemented, and
the constitution has now been through `/speckit-constitution` (v1.3.0). The next work is
**`research.md` for the Tier-0 feature**, then `/speckit-specify`.

**The starting move is not `/speckit-specify`.** An earlier session treated it as one,
substituted its own process for SpecKit, and the artifacts had to be redone. See
**Process** below.

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

## Process — how the next feature gets built

```
/speckit-constitution   ✅ done — v1.3.0, hand-authored text was INPUT not output
research.md             ← YOU ARE HERE. An index, not new research
/speckit-specify        Tier 0: Crossref (P1) + OpenAlex (P2), one feature
/speckit-clarify → /speckit-plan → /speckit-tasks → /speckit-analyze → /speckit-implement
```

**`research.md` is an indexing job, not a research job.** The evidence already exists and
is stronger than the precedent it's conforming to: a pre-registered 12-query benchmark,
60 recorded cells, positive and negative controls, live-verified strict lookup. What it
lacks is the *format* `/speckit-plan` consumes — `biosciences-mcp/specs/*/research.md` uses
numbered resolved unknowns, each **Question / Decision / Rationale / Alternatives
Considered / References**. Write ~a dozen R-entries that **cite** the dossiers rather than
restate them:

| R | Question | Source |
| --- | --- | --- |
| R1 | Connector roster and build order | `DECISION.md` §1 |
| R2 | Venue-class resolution order | `06-literature-envelope.md`, `03-crossref.md` §3.1 |
| R3 | Retraction asymmetry, and its per-DOI cost | `03-crossref.md` §3.4 |
| R4 | **Accepted identifier grammar per connector** | **unwritten — see constitution II** |
| R5 | Rate limits (`x-concurrency-limit: 3`, observed not contractual) | `03-crossref.md` §6 |
| R6 | No batch endpoint; N calls to resolve a DOI list | `03-crossref.md` §6 |
| R7 | Three unresolvable venue classes | `DECISION.md` §5.2 |

R4 falling out as genuinely missing is the format doing real work. **Do not re-run the
benchmark** — it is frozen so that a later run is comparable, and re-running it is an
amendment-by-measurement act, not a research act.

**Acceptance criteria are already written and pre-registered.** The 12-query benchmark was
built to be "the acceptance suite for the Layer-2 build" (research spec §4), C2 included as
a hallucination check. The user-facing outcome is measured too: six questions returned
`UNRESOLVED` on 2026-08-14 because psychology had no Layer 2. "Those six now resolve,
carrying `venue_class` and `classification_basis`" beats "implement Crossref tools".

**Use constraint injection for `/speckit-specify`.** Prior art:
`lifesciences-research/docs/speckit-standard-prompt-v2.md` — citing ADRs inside the specify
prompt is what stops "build a Crossref wrapper" from forgetting Fuzzy-to-Fact. The
psychology variant **must also inject constitution clauses**: Principle VII has no ADR
behind it and will otherwise drift straight out of the spec.

**Promote `probe/fixtures/*.json` into `tests/`.** They are verified-genuine API payloads
(the Layer-1 fan-out accepted work only on artefact verification, never on agent report).
As golden fixtures they turn Principle VII from review-enforced into test-enforced — today's
model tests can only assert the vocabulary *can represent* the right answer, not that a
classifier *chooses* it.

## Commands

```bash
uv sync --extra dev                       # REQUIRED FIRST — see the trap below
uv run pytest tests -q                    # full suite (25 unit tests, ~0.1s)
uv run pytest -m unit -q                  # by marker: unit | integration | e2e
uv run pytest -m crossref -q              # per-connector markers: crossref | openalex |
                                          #   europepmc | semanticscholar
uv run pytest tests/unit/test_work.py -q -k retraction   # one file / one test
uv run ruff check . && uv run ruff format .
uv run pyright                            # currently 0 errors — keep it there
uv run fastmcp inspect fastmcp.json       # gateway surface; today reports 0 tools
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

**Decisions blocking the Tier-0 spec:**

- **Principle VI is currently unsatisfiable.** It mandates `scaffold-fastmcp`; the skill
  lives at `platform-skills/.claude/commands/` in **two versions** (v1 and `-v2`) and
  neither is installed in this repo's `.claude/skills/`. Install one and name it in the
  constitution, or amend VI. The v2 workflow's "scaffold first" step depends on this.
  *(The constitution states the rule — it must name an invocable skill at a stated version
  — and deliberately does not carry this status, which goes stale. This line is the status.)*
- **Two constitution clauses are marked `OPEN`** and the Tier-0 spec is where they get
  settled: the slim-vs-`classification_basis` conflict (IV ↔ VII(b)), and whether the
  envelope carries a reachability field (VII(e), inherited from `DECISION.md` §5.1a).
- **R4 — accepted identifier grammar per connector — is unwritten.** Constitution II now
  requires each connector spec to declare it; nothing declares it yet.

**Compliance status — what a Constitution Check must report today.** The constitution
requires checked / deferred / uncheckable, never a blanket pass; this is the current
inventory, and it lives here because it churns.

- `fastmcp inspect fastmcp.json` reports **0 tools**, so Principles II and IV bind nothing
  yet. **Deferred** — not passing.
- The only deterministic gates are `ruff`, `pyright` and 25 unit tests. Every Required
  Pattern whose enforcement column reads "contract tests" is **deferred**; that category
  has no members yet.
- **Checked today:** envelope shapes, `cross_references` omit-not-null, and VII(a)/(b)/(d)
  at model level.
- **Uncheckable today:** the protocol↛domain import rule (guarded by docstrings only), and
  whether any classifier *chooses* correctly — there is no classifier yet.

**Standing:**

- **Gemini/Antigravity review** of the constitution (now v1.3.1) and
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
