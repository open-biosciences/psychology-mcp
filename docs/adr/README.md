# ADRs — inherited, with literature adaptations

`psychology-mcp` **inherits** the platform ADRs rather than restating them. The
authoritative copies live in:

```
/home/donbr/open-biosciences/biosciences-mcp/docs/adr/accepted/
```

Do not fork them here. Where literature required something the biomedical instance does
not specify, the adaptation is recorded below and implemented in code — it is not a new
ADR unless and until the platform accepts one.

| ADR | Mandate | How it applies here |
|---|---|---|
| **001 §2** Hybrid client | Strict async `httpx` for modern APIs; `run_in_executor` only for legacy sync SDKs, which must then expose batch tools | **No exception needed.** All roster candidates are REST/JSON. `clients/base.py` is async throughout |
| **001 §3** Fuzzy-to-Fact | Phase 1 natural language → ranked candidates; Phase 2 accepts **only** resolved CURIEs; raw string → `UNRESOLVED_ENTITY` | `search_works(query)` → `get_work(doi)`. **The DOI is the CURIE.** Semantic Scholar additionally accepts `CorpusId:`, `PMID:`, `ARXIV:` — useful for records that carry a type but no DOI |
| **001 §4** Agentic Biolink | Every entity response carries `cross_references` per a Key Registry | Vocabulary is bibliographic, not Biolink. See `models/cross_references.py` — nine keys, availability **measured** across 49 cells |
| **001 §5** Tool/Resource bifurcation | Tools return JSON capped at 50; Resources return raw text via custom URI schemes | Full text is a Resource (`work://fulltext/{doi}`), not a Tool payload |
| **001 §6** Triangulation | Verify high-stakes assertions across `cross_references` | Two connectors agreeing on a DOI is a triangulation success. Single-source provenance is a recorded weakness, carried in `Work.discovery_route` |
| **001 §7** Token budgeting | Batch tools **must** accept `slim=True`; page size 50 | **Adapted.** ADR-001's triple is `id`/`name`/`score`; literature uses **`doi`/`title`/`venue_class`** so an agent can triage relevance *and admissibility* together — a score cannot distinguish an article from a blog post |
| **001 §8** Canonical envelopes | Exact pagination and error shapes | **Adopted verbatim** in `models/envelopes.py`. One documented caveat: `total_count` is a within-connector signal — the discovery pass measured three orders of magnitude between connectors, so it must never be compared or summed across them |
| **001 §9** Shared vs domain types | Protocol types must not import domain types | `CrossReferences` and the envelopes are protocol; `Work`, `VenueClass`, `ClassificationBasis` are domain |
| **002** Platform skills | `scaffold-fastmcp` over manual coding | Per-connector servers use the platform skill |
| **003** SpecKit SDLC | `/speckit.specify` → `/plan` → `/tasks` → `/implement` | One cycle per connector, in the Layer-1 build order: Crossref + OpenAlex, then Europe PMC |
| **004** Lifecycle | Module-level singleton; `@mcp.on_event` **FORBIDDEN** | `servers/gateway.py` |
| **005** Git worktrees | Worktrees for parallelising 3+ servers | Applies once more than two connectors are built concurrently. Phase 0 first: the registry must name all connectors up front so no two agents share a write |
| **006** Single-writer package | Split into a `clients/` package | `clients/base.py` is FROZEN; one module per connector |
| **007** Gateway rate resilience | Full-jitter backoff on platform constants; headerless-throttle handling; absence-of-signal rate posture | **Adopted, with one measured divergence.** See adaptation 5 below and constitution Principle VIII |

## Adaptations that are NOT in any ADR

Recorded here so a future reader does not mistake them for platform policy:

1. **`classification_basis`** — no biomedical analogue. Exists because "registered type
   present, DOI absent" is ~11% of Europe PMC's sampled results and 40% of Semantic
   Scholar's, and the alternative discards data the API supplied.
2. **Provenance-beats-DOI** — a published preprint's DOI resolves to the journal article,
   so DOI-first classification launders preprints into peer-reviewed standing.
3. **Three unresolvable venue classes** — `guideline`, `institute-publication`,
   `commentary` have no source type in any connector vocabulary. The server does not
   assert them; a Layer-4 publisher heuristic does.
4. **Asymmetric retraction semantics** — OpenAlex reports the field always; Crossref only
   in the affirmative. `unknown` is therefore distinct from `not-retracted`.
5. **Declared rather than discovered rate posture, for one connector.** ADR-007 mandates
   reading `x-rate-limit-*` at runtime. Crossref does publish them — and MEASURED, its
   polite-pool limit moved 3 → 10 req/s inside 24 hours, which is what makes the runtime
   read worth having. **Semantic Scholar publishes nothing**: a 429 carries only
   `x-amzn-errortype: TooManyRequestsException`, with no `Retry-After` and no
   `x-rate-limit-*`, so `AdaptiveGate.observe` receives nothing and the Retry-After branch
   is inert. Its interval is therefore DECLARED from measurement
   (`SAFE_INTERVAL_SECONDS = 2.5`), and `backoff_base` is the single constant that
   diverges from the platform set. Attempt count and `MAX_BACKOFF` do not diverge.

   The obvious remedy — stepping `min_interval` up on a headerless 429 — is **rejected
   here on evidence**: MEASURED, those 429s are stochastic rather than rate-proportional
   (8-call sweeps drew 4/8 at 2.5s spacing, 2/8 at 4.0s, 4/8 at 6.0s), so a step-up rule
   climbs on noise with nothing to relax it. Constitution VIII(b) records the rejection.
   Recorded here in case the platform later mandates step-up: this connector needs a
   paired decay, or an exemption.

Evidence for 1–4: `open-biosciences-plugins` →
`docs/research/connectors/` (five dossiers, coverage matrix, envelope design, and
`probe/CONTROLLER-NOTES.md`). Evidence for 5: AGE-590 measurements, recorded in
`docs/HANDOFF.md` and in `clients/semanticscholar.py`.
