"""Unified psychology-mcp gateway.

Per ADR-004, lifecycle uses the module-level singleton pattern.
`@mcp.on_event` is FORBIDDEN.

No connector servers are mounted yet. The Layer-1 discovery pass established the
build order (Crossref + OpenAlex jointly as Tier 0, then Europe PMC); each arrives
via its own /speckit.specify per ADR-003.
"""

from fastmcp import FastMCP

mcp: FastMCP = FastMCP(
    name="psychology-mcp",
    instructions=(
        "Scholarly literature retrieval for psychology, behavioural and social science. "
        "Two-phase per ADR-001 Section 3: search_works accepts natural language and returns "
        "ranked candidates; get_work accepts ONLY a resolved identifier. Every work carries a "
        "venue_class (what it is) and a classification_basis (how that was established). "
        "Note that pagination.total_count is a within-connector signal and must never be "
        "compared across connectors."
    ),
)
