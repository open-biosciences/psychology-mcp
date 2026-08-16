# Handoff — 2026-08-16

State of play for the next session. Written because context ran low mid-AGE-588, not
because work stopped cleanly.

## Branch state

| Branch | PR | State | Contains |
|---|---|---|---|
| `main` | — | `185e5d5` | Tier 0 complete: 168 unit + 87 live integration |
| `feat/age-586-fastmcp-cloud-deployment` | **#11 open** | ready for audit | `docs/DEPLOYMENT.md`, env-var guard, wire-protocol verification |
| `feat/age-588-semanticscholar-client` | **not opened yet** | `f713ae6` pushed | Semantic Scholar connector |

**Neither PR is merged.** #11 has been through several corrections; #588 has no PR yet.

Both branches are cut from `main` independently, so **#11 must merge first** — AGE-588's
branch does not contain the `tests/integration/conftest.py` guard, and merging in the
other order will look like the guard was reverted.

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
