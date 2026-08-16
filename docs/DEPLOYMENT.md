# Deploying the gateway (AGE-586)

The platform is **Prefect Horizon** (`horizon.prefect.io`) — what the ticket calls "FastMCP
Cloud". Built by the FastMCP team at Prefect; free personal tier. Deployed servers land at
`https://<server-name>.fastmcp.app/mcp`, which is why the old name persists in URLs.

**Setup is a one-time web step; after that it is automatic.** Horizon monitors the repo and
**redeploys on every push to `main`**. There is no `fastmcp deploy` CLI command — the CLI
ships `dev`, `inspect`, `install`, `project prepare`, `run`, `tasks`, `version`.

## The one-time setup

1. Sign in at [horizon.prefect.io](https://horizon.prefect.io) with GitHub and grant access
   to the `open-biosciences` org. **Private repos are supported** — no extra step.
2. Select `open-biosciences/psychology-mcp`.
3. Fill four fields:

   | Field | Value |
   |---|---|
   | **Server name** | `psychology-mcp` — this determines the URL |
   | **Description** | Scholarly literature retrieval for psychology, behavioural and social science |
   | **Entrypoint** | `src/psychology_mcp/servers/gateway.py:mcp` |
   | **Authentication** | Optional OAuth toggle — off is fine; Tier 0 serves public bibliographic metadata |

4. Set `PSYCHOLOGY_MCP_CONTACT_EMAIL` to a contact address — see Environment variables below.
5. Deploy. Typically under 60 seconds. Record the URL for AGE-587.

Dependencies are auto-detected from `pyproject.toml` — nothing to configure there.

## Dependencies: `pyproject.toml`, and no `requirements.txt`

Horizon auto-detects dependencies from **either** `requirements.txt` **or**
`pyproject.toml`. This repo needs no `requirements.txt`, and the evidence is a working
deployment rather than a reading of the docs:

| Server | `pyproject.toml` | `requirements.txt` | Layout | Deployed |
|---|---|---|---|---|
| `biosciences-mcp` | ✅ hatchling, `packages = ["src/biosciences_mcp"]` | **none** | src-layout package, **absolute imports** | ✅ |
| `biosciences-mcp-edge` | ✅ | **none** | same | ✅ |
| `hci-canon` | ✅ | ✅ (plus inline `environment.dependencies`) | flat `mcp/server.py` | ✅ |
| **`psychology-mcp`** | ✅ hatchling, `packages = ["src/psychology_mcp"]` | none | src-layout package, absolute imports | pending |

**This settles the one real packaging risk.** `servers/gateway.py` does
`from psychology_mcp.servers.literature import ...` — an absolute import that only resolves
if the *package itself* is installed, not merely its dependencies. `biosciences-mcp` has
exactly that shape and deploys, so `environment.project = "."` plus a hatchling
`[project]` is sufficient. `hci-canon` carries all three mechanisms at once; that is
belt-and-braces, not a requirement.

## Environment variables — the complete inventory

`.env.example` is the canonical list. **Two variables exist, and both are now set
locally** — `.env` is present and gitignored. Neither is set in Horizon yet; that is the
one-time UI step above.

*(Superseded 2026-08-16, AGE-590. An earlier revision said "neither is set anywhere today —
there is no `.env` in this repo". That was true when written and false by the time it
merged.)*

| Variable | Needed for this deployment? | Current state | Notes |
|---|---|---|---|
| `PSYCHOLOGY_MCP_CONTACT_EMAIL` | **Yes — set it in the Horizon UI** | **unset**; no `.env` exists | Puts requests in the Crossref and OpenAlex **polite pools**. Not a secret: it is transmitted in the `User-Agent` on every request |
| `S2_API_KEY` | **Yes — set it in the Horizon UI** | set locally in `.env` | Semantic Scholar is **committed Tier 1**, not optional: `DECISION.md` §1 records it as *"wrap — condition discharged"*, key issued 2026-08-15, frozen benchmark re-run **authenticated**, **5 hit / 4 partial / 1 miss — second only to Crossref**. `SemanticScholarClient` shipped in AGE-588 and is live-verified as of 2026-08-16, so the gateway reads this variable now. **It is a real secret** — unlike the contact address, it must never be committed |

**Tier 0 — Crossref and OpenAlex — is entirely keyless**, which is why the gateway serves
correctly with nothing configured, and why `search_works` degrades rather than fails when
Semantic Scholar is unconfigured. That is a graceful-degradation property, **not** an
argument for deploying without the key: Semantic Scholar is the only credentialed connector
on the roster, it is committed, and it shipped. **This server holds a real secret today.**

### Semantic Scholar — what the record already establishes

The validation is done; only the client is missing. Three constraints carry into the build
and the deployment:

- **Rate: 1 req/s CUMULATIVE across all endpoints.** MEASURED tighter than nominal — 1.3s
  spacing still drew a 429, so **2.5s is the observed-safe interval** for sustained
  sequential use. This is far tighter than Crossref's or OpenAlex's and needs its own
  starting posture.
- **Attribution is a hard licence obligation**, not a courtesy: published material using S2
  results must credit Semantic Scholar or cite "The Semantic Scholar Open Data Platform".
  It is already in the constitution's Required Patterns, and it **propagates to every
  downstream consumer of a grounded claim**.
- **The unauthenticated tier is unusable** — zero of twelve benchmark queries completed
  across three observation windows spanning ~1.5h. There is no keyless fallback; without
  the key the connector simply does not function.

It is also the connector that makes constitution II's multi-prefix carve-out real —
`CorpusId:`, `PMID:`, `ARXIV:` — and the only route to the DOI-less records the envelope's
`index-asserted` basis exists for.

### Local setup, before running the live suite

```bash
cp .env.example .env          # gitignored
# set PSYCHOLOGY_MCP_CONTACT_EMAIL to a real contact address
export PSYCHOLOGY_MCP_CONTACT_EMAIL="you@example.com"
uv run pytest -m integration --run-integration -q
```

The integration suite **skips with an explicit message** when the variable is unset. That
guard exists because of a real failure: the live suite previously ran green while the
variable was unset, which meant the gateway-path tests measured the **anonymous** pool
while being reported as the deployment's behaviour. A keyless API makes that failure
silent — both pools work, so nothing errors.

### Why the address is not in `fastmcp.json`

An earlier revision of this file put it in `deployment.env`. It has been removed, for three
reasons:

1. **Not the house pattern.** `biosciences-mcp` is deployed and needs four variables
   (`BIOGRID_API_KEY`, `NCBI_API_KEY`, `BIOSCIENCES_API_KEY`, `FASTMCP_CLOUD_ENDPOINT`);
   its `fastmcp.json` declares **zero** `env` entries, as does `biosciences-mcp-edge`'s.
   The platform, not the repo, is where variables live.
2. **Not confirmed to be read by Horizon.** It works for `fastmcp run` locally; Horizon's
   deployment page documents four UI fields and does not mention `fastmcp.json`.
3. **It is a personal address in a repo that may go public.** Committing it buys nothing
   the UI step doesn't already cover.

`fastmcp.json` is committed, so **no secret ever belongs in it.**

### Failure mode if the variable is missed

Graceful, not fatal. The gateway still serves; it drops to the anonymous pool, where
Crossref documents a lower, unspecified limit. Reduced throughput, not an outage — so this
is not a launch blocker, but it *is* a silent one, which is why the local guard exists.

## Verified ready — 2026-08-16

Exercised through the **MCP protocol over HTTP**, not in-process. Every prior test in this
repo ran in-process; this is the wire protocol a deployed gateway actually serves.

| Check | Result |
|---|---|
| Server binds and serves | `Uvicorn running`, endpoint at `/mcp` |
| MCP `initialize` handshake | `serverInfo.name: psychology-mcp`, instructions delivered |
| `tools/list` | `['search_works', 'get_work']` |
| `get_work("10.1111/famp.12229")` | `peer-reviewed-article` / `registered` / `not-retracted` |
| `search_works(slim=True)` | the `doi`/`title`/`venue_class` triple |
| `pagination.total_count` | `null` — constitution III holds over the wire |
| `get_work("not a doi")` | `UNRESOLVED_ENTITY` — strict-tool guard holds over the wire |

`POST /mcp/` with a trailing slash returns **307**; the endpoint is `/mcp`.

## House pattern

`fastmcp.json` matches the two already-deployed sibling servers structurally — same
`$schema`, `source.path`/`entrypoint`, `environment.python`/`project`,
`deployment.transport`/`log_level`:

- `biosciences-mcp/fastmcp.json`
- `biosciences-mcp-edge/fastmcp.json`

Neither declares `deployment.env` — and `biosciences-mcp` demonstrably needs four
variables, so the platform, not the file, is where they live. **This repo's `fastmcp.json`
declares none either**, so it matches the house pattern with no divergence.

*(Superseded 2026-08-16, AGE-590. An earlier revision called the `env` block "this repo's
one deliberate divergence"; that block was removed further up this same document, and the
sentence survived the edit.)*

`hci-canon` diverges further: `source.type: "filesystem"`, a flat `mcp/server.py` rather
than a package, and dependencies declared three ways at once (`pyproject.toml`,
`requirements.txt`, **and** inline `environment.dependencies`). It **does** have a
`pyproject.toml` — an earlier draft of this doc claimed otherwise and was wrong. Treat it
as a more defensive older pattern, not as a target to copy.

## AGE-587 — a correction to the ticket text

The ticket says `psychology-research/.mcp.json` holds `{"mcpServers": {}}`. **It does not.**
As of 2026-08-16 it holds the interim third-party binding from `DECISION.md` §4:

```json
{"mcpServers": {"pubmed": {"type": "http", "url": "https://pubmed.mcp.claude.com/mcp"}}}
```

So AGE-587 is an **add-or-replace against a live binding**. Two constraints from
`DECISION.md` §7.4 will bite:

- **Every entry needs `"type": "http"`.** An entry with a `url` and no `type` is read as
  stdio, skipped, and warned about.
- `psychology-research/` is mirrored downstream into `psychology-research-plugins` by
  `rsync --delete`. Author the change **upstream**; never hand-edit the mirror.

Whether the gateway replaces the PubMed binding or joins it is a roster decision.
`DECISION.md` §2 records the pattern as "the plugin declares the platform's first-party
gateway, and public third-party servers where they exist" — which suggests alongside.
