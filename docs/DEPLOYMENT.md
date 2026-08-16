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

## Environment variables — set them in the Horizon UI

**The UI is authoritative. `fastmcp.json` is not confirmed to be read by Horizon.**

The evidence: `biosciences-mcp` is deployed and needs `BIOGRID_API_KEY`, `NCBI_API_KEY`,
`BIOSCIENCES_API_KEY`, and `FASTMCP_CLOUD_ENDPOINT`. Its `fastmcp.json` declares **zero**
`env` entries — as does `biosciences-mcp-edge`'s. Those variables are therefore set in the
platform, not in the repo. Horizon's own deployment page documents four UI fields and does
not mention `fastmcp.json` at all.

`fastmcp.json` here does carry the variable:

```json
"deployment": { ..., "env": { "PSYCHOLOGY_MCP_CONTACT_EMAIL": "dwbranson@gmail.com" } }
```

That is **verified working for `fastmcp run` locally** — the server started from config
alone and completed a polite-pool call with no shell export. Treat it as documentation of
the requirement and as configuration for local or non-Horizon runs. **Set the variable in
the Horizon UI as well**; do not assume the file covers it.

**The failure mode is graceful, not fatal.** Without the variable the gateway still serves
— it drops from the polite pool to the anonymous pool, where Crossref documents a lower,
unspecified limit. You would see reduced throughput, not an outage. That is worth knowing
before anyone treats this as a launch blocker.

**Secrets must never go in `fastmcp.json`** — it is committed. This block is only
defensible because a contact address is not a secret; it is already transmitted publicly in
the `User-Agent` on every Crossref and OpenAlex request. `biosciences-mcp` keeps its real
API keys in the UI for exactly this reason. If you would rather the address not sit in a
repo that may go public, delete the `env` block — the UI step is needed regardless.

**Do NOT set `S2_API_KEY`.** Semantic Scholar is Tier 1 and unbuilt. Tier 0 — Crossref and
OpenAlex — is entirely keyless, and that property is worth preserving.

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
variables, so the platform, not the file, is where they live. The `env` block here is this
repo's one deliberate divergence from the house pattern.

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
