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

4. Deploy. Typically under 60 seconds. Record the URL for AGE-587.

Dependencies are auto-detected from `pyproject.toml` — nothing to configure.

## Why there is nothing else to set

`fastmcp.json` now carries the only environment variable this server needs:

```json
"deployment": {
  "transport": "http",
  "log_level": "INFO",
  "env": { "PSYCHOLOGY_MCP_CONTACT_EMAIL": "dwbranson@gmail.com" }
}
```

`deployment.env` is a documented field ("Environment variables to set when running the
server") and is **verified working locally** — the server started from config alone and made
a successful polite-pool call with no shell export.

**The address is deliberately committed.** It is transmitted publicly in the `User-Agent`
on every Crossref and OpenAlex request, so this is not a disclosure — it is the same string
those services already see. It enters the polite pools (confirmed: `x-api-pool:
polite-single`). If you would rather it not sit in a repo that may go public, delete the
`env` block and set the variable in Horizon's UI instead; the cost is one extra setup step.

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

Neither declares `deployment.env`; both presumably set variables in the Horizon UI. The
`env` block here is the one deliberate divergence, and it exists because this server's only
variable is a non-secret contact address. (`hci-canon` differs more: it declares
`environment.dependencies` inline and `source.type: "filesystem"` because it has no
`pyproject.toml` — not applicable here.)

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
