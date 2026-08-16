# Deploying the gateway (AGE-586)

Pre-deployment verification and the checklist for the human step. **The deploy itself is a
web-UI flow** — there is no `fastmcp deploy` command; the CLI ships `dev`, `inspect`,
`install`, `project prepare`, `run`, `tasks`, `version`. Connecting the repo, setting
environment variables, and obtaining the production URL all happen in the FastMCP Cloud
dashboard under an account this repo has no credentials for.

## Verified ready — 2026-08-16

Run against `fastmcp run fastmcp.json --port 8199`, exercised through the **MCP protocol
over HTTP**, not in-process:

| Check | Result |
|---|---|
| Server binds and serves | `Uvicorn running`, endpoint at `/mcp` |
| MCP `initialize` handshake | `serverInfo.name: psychology-mcp`, instructions delivered |
| `tools/list` | `['search_works', 'get_work']` |
| `get_work("10.1111/famp.12229")` | `peer-reviewed-article` / `registered` / `not-retracted` |
| `search_works(slim=True)` | returns the `doi`/`title`/`venue_class` triple |
| `pagination.total_count` | `null` — constitution III holds over the wire |
| `get_work("not a doi")` | `UNRESOLVED_ENTITY` — strict-tool guard holds over the wire |

Note `POST /mcp/` (trailing slash) returns **307**; the endpoint is `/mcp`. Worth knowing
before debugging a client that follows redirects poorly.

## Configuration the deploy needs

`fastmcp.json` is complete and needs no edit:

```json
{"source": {"path": "src/psychology_mcp/servers/gateway.py", "entrypoint": "mcp"},
 "environment": {"python": ">=3.11", "project": "."},
 "deployment": {"transport": "http", "log_level": "INFO"}}
```

**Environment variables:**

| Variable | Required? | Why |
|---|---|---|
| `PSYCHOLOGY_MCP_CONTACT_EMAIL` | Strongly recommended | Enters the Crossref and OpenAlex polite pools. Without it the gateway still works, but at the anonymous pool's lower, unspecified limit. Crossref's response headers confirmed `x-api-pool: polite-single` when set |
| `S2_API_KEY` | **No** — not yet | Semantic Scholar is Tier 1 and unbuilt. Do not set it on this deployment |

**No credentials are required to run Tier 0.** Crossref and OpenAlex are keyless. That is a
deliberate property worth preserving — see the no-paid-per-token-APIs policy.

## The human step

1. Connect the repo in the FastMCP Cloud dashboard. **The repo is private**, so the GitHub
   connection needs access granted to the `open-biosciences` org — the most likely place
   for this to stall.
2. Set `PSYCHOLOGY_MCP_CONTACT_EMAIL`.
3. Deploy; record the production URL.
4. Smoke-test the deployed URL with the same handshake used above, then hand the URL to
   AGE-587.

## AGE-587 — a correction to the ticket text

The ticket says `psychology-research/.mcp.json` holds `{"mcpServers": {}}`. **It does not.**
As of 2026-08-16 it holds the interim third-party binding from `DECISION.md` §4:

```json
{"mcpServers": {"pubmed": {"type": "http", "url": "https://pubmed.mcp.claude.com/mcp"}}}
```

So AGE-587 is an **add-or-replace against a live binding**, not a fill-in-the-blank. Two
constraints from `DECISION.md` §7.4 that will bite:

- **Every entry needs `"type": "http"`.** An entry with a `url` and no `type` is read as
  stdio, skipped, and warned about.
- `psychology-research/` is mirrored downstream into `psychology-research-plugins` by
  `rsync --delete`. Author the change **upstream** and let it reach the mirror by that
  sync; never hand-edit the mirror.

Whether the deployed gateway *replaces* the PubMed binding or sits alongside it is a
roster decision — `DECISION.md` §2 records the pattern as "the plugin declares the
platform's first-party gateway, and public third-party servers where they exist," which
suggests alongside.
