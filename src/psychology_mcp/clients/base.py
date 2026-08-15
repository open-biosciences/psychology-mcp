"""Base client for all scholarly-literature API clients.

Mirrors `biosciences_mcp.clients.base` (ADR-001 Section 2: strict async httpx with
connection pooling; ADR-006: single-writer clients/ package so parallel per-connector
work never shares a file).

Status: FROZEN — do not modify during parallel per-connector implementation.

One deliberate addition over the biosciences base: the polite-pool contact header.
Crossref and OpenAlex both grant materially better throughput when a contact address is
supplied in the User-Agent, and the Layer-1 probe ran both keyless at ~6.6 req/s with
zero 429s on that basis.
"""

import os
from typing import Any

import httpx

_CONTACT = os.environ.get("PSYCHOLOGY_MCP_CONTACT_EMAIL", "").strip()

USER_AGENT = "psychology-mcp/0.1.0 (+https://github.com/open-biosciences)" + (
    f" mailto:{_CONTACT}" if _CONTACT else ""
)


class LiteratureClient:
    """Base async HTTP client for scholarly literature APIs.

    Provides connection pooling and common HTTP functionality.
    Subclasses implement API-specific logic and their own rate discipline —
    the probe measured limits differing by two orders of magnitude between
    connectors, so a shared default would be wrong for most of them.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        max_connections: int = 10,
    ) -> None:
        """Initialize the client.

        Args:
            base_url: Base URL for the API.
            timeout: Read timeout in seconds.
            max_connections: Maximum concurrent connections.
        """
        self.base_url = base_url.rstrip("/")
        self._client: httpx.AsyncClient | None = None
        self._timeout = timeout
        self._max_connections = max_connections

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the async HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            limits = httpx.Limits(
                max_connections=self._max_connections,
                max_keepalive_connections=self._max_connections,
            )
            timeout = httpx.Timeout(
                connect=5.0,
                read=self._timeout,
                write=10.0,
                pool=5.0,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=timeout,
                limits=limits,
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
            )
        return self._client

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a JSON document. Raises httpx.HTTPStatusError on a non-2xx response."""
        client = await self._get_client()
        response = await client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
