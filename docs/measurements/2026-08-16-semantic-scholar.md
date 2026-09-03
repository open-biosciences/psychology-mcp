# Semantic Scholar — measurements against the dossier (2026-08-16)

> Preserved from the 2026-08-16 session handoff when that file was retired (it was a one-time
> handoff between two sessions; everything else in it was done or Linear-owned). Cited by
> `docs/adr/README.md` as the evidence for finding 5 (AGE-590). The §3(c) measurement is
> also recorded in `src/psychology_mcp/clients/semanticscholar.py`.

Two claims in `01-semantic-scholar.md` did not reproduce. Recorded, not silently patched —
these are `MEASURED` clauses and the constitution amends by measurement.

**§3(c) — "2 of 5 sampled records carry a registered `publicationTypes` and NO DOI."**
Re-run 2026-08-16 on the same AEDP query, the two DOI-less records carry
`publicationTypes: null`, `venue: ""` **and** `publicationVenue: null`. Nothing about their
class is knowable from this connector.

This matters because §3(c) is the evidence base for `ClassificationBasis.INDEX_ASSERTED`
being *reachable* on DOI-less records. The basis is still right — it is what lets a
DOI-less record with a type stay usable — but on this query no such record appeared. They
emit `unverified`/`none`, which is VII(b) working, not a gap. **It also means the AGE-590
venue fallback cannot rescue them**, and scoping it as the fix for `unverified` DOI-less
results would have been wrong.

**§1 — "2.5s is the observed-safe sustained interval."** Not sufficient. 8-call sweeps drew
4/8 429s at 2.5s spacing, 2/8 at 4.0s and 4/8 at 6.0s; both endpoints throttle
intermittently at 3.0s. The 429s are **stochastic**, not a smooth rate — wider spacing does
not monotonically help. `errors.py:26` already recorded the underlying cause (sustained 429
with no `Retry-After`), which is where this should have been read rather than re-measured.

Consequence for the client: `AdaptiveGate.observe` receives **nothing** from this API — a
429 carries only `x-amzn-errortype: TooManyRequestsException`, no `Retry-After`, no
`x-rate-limit-*`. Where Crossref's posture is discovered at runtime, this one must be
declared. Retry constants follow the platform pattern (`MAX_RETRIES = 3` ⇒ 4 attempts,
`MAX_BACKOFF = 60.0`); only `backoff_base` is set from the measured limit, and that is the
single deliberate divergence.

Consequence for tests: a live suite here must **fetch once and assert many times**. A
per-test fetch failed on a different random test every run. ADR-001 classifies an exhausted
429 as `RATE_LIMITED` — a documented operational outcome, not a contract breach — so the
module fixture skips on 429 **and only on 429**.

