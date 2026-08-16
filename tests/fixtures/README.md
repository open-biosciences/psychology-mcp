# Golden fixtures

Verified-genuine API payloads captured during the Layer-1 discovery probe, vendored here
so the test suite is self-contained and never reaches the network.

| File | Source | Captured |
|---|---|---|
| `crossref-C1.json` | `GET https://api.crossref.org/works?query=...&rows=5` (benchmark control C1) | 2026-08-15 |
| `openalex-C1.json` | `GET https://api.openalex.org/works?search=...` (benchmark control C1) | 2026-08-15 |

Upstream: `open-biosciences-plugins/docs/research/connectors/probe/fixtures/`.

The Layer-1 fan-out protocol accepted a connector's work only when its recorded fixture was
a genuine API payload, so these are real responses rather than hand-written mocks. C1 is the
benchmark's **positive control** — Wiebe & Johnson 2016 on EFT — chosen to validate the
harness rather than to measure coverage.

Do not edit. Re-capture upstream and re-copy if a payload shape needs updating.
