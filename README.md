# psychology-mcp 🧠

> Layer 2 for the psychology half of the Open Biosciences platform — FastMCP wrappers for
> scholarly literature APIs, returning works that carry **what they are** and **how we know**.

**Status: scaffolded. No connector servers built yet.**

---

## Why this exists

The `psychology-research` plugin shipped with `.mcp.json` as `{"mcpServers": {}}` — not
because connectors were never chosen, but because **the psychology half of the platform
had no Layer 2**. `bio-research` points at `biosciences-mcp`, its own deployed gateway.
Psychology had nothing to point at.

```
Layer 1  SpecKit discovery      ADRs 001–006 · research.md → spec.md → plan.md → tasks.md
Layer 2  FastMCP implementation biosciences-mcp  ·  psychology-mcp  ← THIS REPO
Layer 3  Plugin manifest        open-biosciences-plugins/*/.mcp.json → the gateway URL
Layer 4  Skills                 bio-research/* · psychology-research/* · consumers
```

## What Layer-1 discovery established

A frozen 12-query benchmark was run against five candidate APIs — 49 recorded cells, every
figure counted from the records rather than from any summary. Full evidence:
`open-biosciences-plugins` → `docs/research/connectors/`.

| Connector | Coverage (Q1–Q10) | Roster |
|---|---|---|
| **Crossref** | 8 hit / 2 partial / 0 miss | **Tier 0** — classifies |
| **OpenAlex** | 2 / 5 / 3 | **Tier 0** — clears retraction |
| **Europe PMC** | 2 / 2 / 6 | Tier 1 |
| **Semantic Scholar** | *not measured* (429) | Tier 2, conditional |
| PsyArXiv/OSF | 0 / 0 / 10 | not scheduled — not an index |
| APA PsycNET | — | **removed** — no query API at any access level |

**Crossref and OpenAlex are Tier 0 jointly, not alternatives.** Crossref is the only
connector reaching book canon and historical primaries — it returned Murdock's *The
Heroine's Journey* and Marston's *Emotions of normal people.* (1928) — and is the sole
source of `isbn` and of registered `type`. OpenAlex is the only source of standing
`retraction_status`. Build only one and the envelope is crippled in a specific,
predictable way.

## The envelope

Every `Work` carries two things the drafted design would have conflated:

- **`venue_class`** — what the item *is*, from its own registered metadata. Never from the
  URL, never from the index that surfaced it.
- **`classification_basis`** — *how* that was established: `provenance` / `registered` /
  `index-asserted` / `none`.

Two rules exist because the probe found the naive alternative fails:

**Provenance beats DOI resolution.** A published PsyArXiv preprint's DOI is the *journal
article's* DOI, so a DOI-first rule classifies a preprint as peer-reviewed — laundering it
into standing it does not have.

**Type without a DOI is still type.** ~11% of Europe PMC's sample and 40% of Semantic
Scholar's carry a registered type and no DOI. Flattening those to `unverified` discards
data the API already gave us. `classification_basis` keeps the trust distinction without
the loss.

Three classes — `guideline`, `institute-publication`, `commentary` — are **not resolvable
from any connector's type vocabulary** and are left to a consumer-side publisher
heuristic. The server does not assert what it cannot know.

Design: `docs/research/connectors/06-literature-envelope.md` in `open-biosciences-plugins`.

## Layout

```
src/psychology_mcp/
├── clients/     one module per connector (ADR-006 single-writer package)
│   └── base.py  async httpx + pooling (FROZEN)
├── models/
│   ├── envelopes.py         ADR-001 §8 — protocol types, adopted verbatim
│   ├── cross_references.py  Literature Key Registry — protocol type
│   └── work.py              domain type: venue_class, classification_basis
└── servers/
    └── gateway.py           unified gateway (ADR-004 singleton; @mcp.on_event FORBIDDEN)
```

## Development

```bash
uv sync --extra dev
uv run pytest tests -q
uv run ruff check .
```

Set `PSYCHOLOGY_MCP_CONTACT_EMAIL` to enter the Crossref and OpenAlex polite pools —
both grant materially better throughput for a contact address, and both ran keyless at
~6.6 req/s with zero 429s during discovery.

## Governance

Inherits ADRs 001–006 from `biosciences-mcp/docs/adr/accepted/`. See `docs/adr/README.md`
for how each applies, and where literature required an adaptation rather than an
inheritance.

## License

MIT. Data returned by each API remains subject to its provider's terms; this repo wraps
public APIs and redistributes nothing.
