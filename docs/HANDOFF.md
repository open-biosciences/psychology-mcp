# Handoff — 2026-08-16

State of play for the next session. Written because context ran low mid-AGE-588, not
because work stopped cleanly.

## Branch state

| Branch | PR | State | Contains |
|---|---|---|---|
| `main` | — | AGE-590 branch open | Tier 0 + Semantic Scholar, live-verified |
| `feat/age-586-fastmcp-cloud-deployment` | #11 | **merged** | `docs/DEPLOYMENT.md`, env-var guard, wire-protocol verification |
| `feat/age-588-semanticscholar-client` | #12 | **merged** | Semantic Scholar connector |
| `feat/age-589-semantic-scholar-gateway-merge` | #13 | **merged** | reserved page slots for S2's unique reach |

**All three are merged as of 2026-08-16.**

`feat/age-588` was cut from `feat/age-586`, **not** from `main` — so #12 was a strict
superset of #11, and merging #12 alone would have landed all of AGE-586's work under
AGE-588's ticket. Both merged 2026-08-16.

*(Corrected 2026-08-16, AGE-590. This paragraph originally said the branches were cut from
`main` independently and that #588 lacked the `tests/integration/conftest.py` guard. Both
were wrong, and the branch lineage was the opposite of what was stated.)*

## AGE-588 — what is done

`f713ae6`. 226 unit tests, ruff clean, pyright 0, gateway reports 2 tools.
`pytest -m semanticscholar` → **58 tests**, a marker that had zero members since the first
commit.

- `clients/semanticscholar.py` — client, classification, identifier grammar, credentials
- `tests/unit/test_semanticscholar.py` — 58 golden-fixture tests
- `tests/fixtures/semantic-scholar-C1.json` — the **authenticated** C1 capture, vendored
- `servers/literature.py` — folded into `search_works`, key-gated

**The bug worth knowing about:** the first pass omitted `Preprint` from the type
precedence entirely. S2 tags records with several `publicationTypes` at once, so a
preprint arrives as `['JournalArticle', 'Preprint']` — resolving JournalArticle first
would have classified it `peer-reviewed-article`. That is VII(a) laundering, in the one
connector whose job is reaching records nothing else sees. Fixed: `Preprint` outranks every
other type in any order. Mutation-checked — removing that single line fails 7 tests.

## AGE-588 — what is NOT done

1. **No live verification.** `.env` contains **only** `PSYCHOLOGY_MCP_CONTACT_EMAIL`.
   There is **no S2 key in it**, so nothing about this connector has touched the live API.
   Everything above is fixture-verified only.
2. **No integration tests.** `tests/integration/` has no Semantic Scholar file. The live
   suite cannot exercise it until the key is present.
3. **The strict endpoint is unverified upstream.** `01-semantic-scholar.md` §5 records
   `/paper/{ID}` as *documented but not verified live* — every probe call 429'd before the
   key was issued. The tests pin the request shape we send, **not** that the API honours
   it. First live call is the real test.
4. **`merge.py` untouched.** The PM's scope asked for a 3-way merge there; I reused the
   existing `_merge_by_doi` instead, because that join already encodes the precedence S2
   needs — left side primary, so Crossref's `registered` is never displaced, and S2
   contributes no retraction. Deliberate, and a legitimate thing for the audit to reject.

## Blocking decisions

**1. The S2 key.** It is not in `.env`. It was also exposed in shell history and task logs
earlier in this session, so decide rotation *before* wiring it into a deployed server, not
after. Variable name: `S2_API_KEY` (matches `.env.example` and the probe adapter); the
client also accepts `SEMANTIC_SCHOLAR_API_KEY` and
`PSYCHOLOGY_MCP_SEMANTIC_SCHOLAR_API_KEY`.

**2. Commit `0124bd1`** still carries a credential-disclosure sentence in merged history.
Both repos are verifiably clean of key *values*, but that sentence goes public with the
history if the repo flips.

**3. AGE-587 ticket text is wrong.** It says `psychology-research/.mcp.json` holds
`{"mcpServers": {}}`. It holds the interim PubMed binding. See `docs/DEPLOYMENT.md`.

## Standing corrections from this session

Things I asserted and later had to retract — recorded so they are not re-asserted:

- **Semantic Scholar is committed Tier 1, never descoped.** I repeatedly wrote "Tier 1 and
  unbuilt — do not set `S2_API_KEY`", which read as exclusion. `DECISION.md` §1 says
  *wrap — condition discharged*; §5.4 is struck through as RESOLVED.
- **The live suite ran partly unconfigured.** `PSYCHOLOGY_MCP_CONTACT_EMAIL` was unset,
  so gateway-path tests measured the **anonymous** pool while per-connector tests used a
  hardcoded address. Both pools work because Tier 0 is keyless, so it stayed green and
  invisible. Fixed on PR #11 by a conftest guard that skips the suite when the variable is
  unset — that guard is the only thing preventing a repeat.
- **"FastMCP Cloud" is Prefect Horizon**, private repos are supported, and deployment
  auto-redeploys on push to `main`.
- **Env vars belong in the Horizon UI**, not `fastmcp.json` — `biosciences-mcp` is deployed,
  needs four variables, and declares zero.

## Next actions, in order

1. Merge PR #11 (after audit).
2. Open the AGE-588 PR from `feat/age-588-semanticscholar-client`.
3. Put the S2 key in `.env` (rotate first if that is the call), then write
   `tests/integration/test_live_semanticscholar.py` and verify the strict endpoint live.
4. AGE-586's one-time Horizon setup — four UI fields, values in `docs/DEPLOYMENT.md`.
5. AGE-587 once the URL exists.

Backlog: AGE-584 (weekly live CI — still blocked on the SSL failure in the Auditor's
environment), AGE-585 (collaboration doc, belongs in `biosciences-program`).


---

# AGE-590 addendum — 2026-08-16

## Semantic Scholar is live-verified

The connector was fixture-only when the section above was written. It is not any more.
`tests/integration/test_live_semanticscholar.py` exercises it against the real API, and
**the strict `/paper/{ID}` endpoint is verified** — `01-semantic-scholar.md` §5 had it as
*documented but not verified live*, because every Layer-1 probe call 429'd before a key
existed. The C1 control returns `{doi, pmid: 27273169, semantic_scholar_id, issn}` in one
response, which is the §3(a) crosswalk claim holding up.

Blocking decision 1 above is resolved: the key is in `.env`, gitignored.

## Measurements recorded against the dossier

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

## Still open

- **AGE-586's one-time Horizon setup.** `S2_API_KEY` must be set there too; the deployment
  now needs it, which was not true when `DEPLOYMENT.md` was first written.
- **Commit `0124bd1`** still carries the credential-disclosure sentence in merged history.
- **AGE-587** once the production URL exists.
- Backlog: AGE-584 (weekly live CI — note the stochastic-429 finding above before wiring
  this connector into a scheduled job), AGE-585 (collaboration doc).
