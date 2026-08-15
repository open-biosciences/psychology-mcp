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

**Status: scaffolded, no connector servers built.** The protocol layer is implemented; the
next work is `/speckit-specify` for Crossref.

## Read these before designing anything

| Document | Why |
|---|---|
| **`.specify/memory/constitution.md`** | **Read first.** Principle VII (Classification Honesty) is NON-NEGOTIABLE and its violations are **blocking**. Clauses marked `MEASURED` rest on evidence and may be amended *by measurement* — v1.2.0 exists because one was contradicted |
| `docs/adr/README.md` | ADRs 001–006 are **inherited** from `biosciences-mcp/docs/adr/accepted/`, not forked. Lists the four adaptations that are *not* platform policy |
| `open-biosciences-plugins` → `docs/research/connectors/` | The evidence base. `DECISION.md` for the roster, `06-literature-envelope.md` for the response contract, five dossiers, and `probe/CONTROLLER-NOTES.md` for cross-connector findings |

## Build order — settled by measurement, not preference

| Tier | Connector | Why |
|---|---|---|
| **0** | **Crossref + OpenAlex, jointly** | Crossref **classifies** (sole source of registered `type`, `isbn`, book canon, historical primaries). OpenAlex **clears retraction** (sole standing `retraction_status`). Neither alone makes the envelope implementable |
| 1 | Europe PMC | Additive; sole source of `pmcid` |
| 1 | Semantic Scholar | Unique reach — only connector answering AEDP transformance, only route to DOI-less records. **Credentialed**; 1 req/s cumulative |
| — | PsyArXiv/OSF | Not scheduled — substring filter, not an index |
| — | APA PsycNET | **Removed** — no query API at any access level |

**Start with Crossref.** The envelope's classification axis depends on it before anything
else can be built against it. `03-crossref.md` §3 has the `type` → venue-class mapping.

## Working conventions

- **Branch + PR for everything.** The first six commits went straight to `main`, including
  both constitution versions. That was wrong — the constitution is the artifact that most
  needed review and got none. Don't repeat it.
- **SpecKit is upstream v0.16.4**, pinned to the release tag (not `main`, which is a dev
  build). **Invoke with a hyphen: `/speckit-specify`, not `/speckit.specify`.**
  `biosciences-mcp` still runs a January vintage with the dot syntax — the two repos are on
  different generations.
- **Tests:** `uv run pytest tests -q` · **Lint:** `uv run ruff check .`
- **Credentials from the environment, never source.** `.env` is gitignored; `.env.example`
  carries placeholders. Credentials belong to this layer — a plugin declares servers by URL
  and reaches keys via `${VAR}`, `headersHelper` or `userConfig`, and never holds one.

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

- **The Semantic Scholar API key needs rotating.** It was exposed inline in shell commands
  during a session and is in shell history and task logs.
- **Gemini/Antigravity review** of the constitution and `06-literature-envelope.md` is
  wanted before the Crossref spec depends on them. Precedent:
  `lifesciences-research/docs/antigravity-validation/`.
- **Batch endpoints unverified** for Crossref, OpenAlex, Europe PMC — worth a cheap pass,
  since batch is the only way to beat Semantic Scholar's per-call budget.
- **Not yet registered** in `open-biosciences.code-workspace` or the Wave 2 table in
  `biosciences-program/README.md`. That waits until a server builds.
- Repo is **private**; making it public would restore branch-protection availability.

## Where to look for what

- "What are the rules?" → `.specify/memory/constitution.md`
- "Which connector, and why?" → `open-biosciences-plugins` → `docs/research/connectors/DECISION.md`
- "What shape does a response take?" → `06-literature-envelope.md`, implemented in `src/psychology_mcp/models/`
- "What did the benchmark actually measure?" → `00-coverage-matrix.md` (60 cells) and the five dossiers
- "Why is this rule here?" → `probe/CONTROLLER-NOTES.md` — cross-connector findings no single dossier could see
