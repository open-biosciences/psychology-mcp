"""Unified psychology-mcp gateway.

Per ADR-004, lifecycle uses the module-level singleton pattern.
`@mcp.on_event` is FORBIDDEN.

Tier 0 (Crossref + OpenAlex, jointly) is mounted as one literature server rather than one
server per connector. That is not a shortcut: all roster connectors return the SAME entity
(`Work`) keyed by the SAME identifier (the DOI), and what differs is which facet each one
authoritatively supplies. Crossref classifies, OpenAlex clears retraction, and neither
alone makes the envelope implementable (`DECISION.md` §1).

Europe PMC and Semantic Scholar (Tier 1) will mount here as additional sources behind the
same two tools, not as additional tool pairs.
"""

from fastmcp import FastMCP

# ABSOLUTE import: fastmcp.json loads this file BY PATH, and a relative import raises
# "attempted relative import with no known parent" at start-up.
from psychology_mcp.servers.literature import mcp as literature_mcp

mcp: FastMCP = FastMCP(
    name="psychology-mcp",
    instructions=(
        "Scholarly literature retrieval for psychology, behavioural and social science. "
        "Two-phase per ADR-001 Section 3: search_works accepts natural language and returns "
        "ranked candidates; get_work accepts ONLY a resolved identifier. Every work carries a "
        "venue_class (what it is) and a classification_basis (how that was established) — read "
        "both, because a class without its basis is not an admissibility warrant. "
        "retraction_status 'unknown' means no consulted source reported the field; it is NOT a "
        "synonym for not-retracted. "
        "Note that pagination.total_count is a within-connector signal and must never be "
        "compared across connectors; on merged results it is null by design."
    ),
)

mcp.mount(literature_mcp)
