"""Unit-suite guard: a `unit` test must never reach the network.

This exists because of a real, silent failure. The gateway's `search_works` calls Semantic
Scholar only when `is_configured` — which reads `S2_API_KEY` from the ENVIRONMENT. The
per-file `_reset_singletons` fixtures reset `_crossref` and `_openalex` but not
`_semanticscholar`, so the moment a key was present in the shell, eight tests that mock
Crossref and OpenAlex started making **live** Semantic Scholar calls and failing.

They passed for as long as they did only because no key existed. That is the same shape as
the AGE-586 contact-email bug: a suite that is green because the environment is empty, and
silently different once it is not. `pyproject.toml` marks `unit` as "no network"; this is
what makes that marker true rather than aspirational.

Deleting the variables rather than resetting the singleton is deliberate — the singleton is
rebuilt lazily from the environment, so clearing the environment is what actually holds.
"""

import pytest

from psychology_mcp.clients.semanticscholar import API_KEY_VARS
from psychology_mcp.servers import literature


@pytest.fixture(autouse=True)
def _no_credentials_in_unit_tests(monkeypatch: pytest.MonkeyPatch):
    """Unconfigure every credentialed connector, then reset the singletons that cache it."""
    for name in API_KEY_VARS:
        monkeypatch.delenv(name, raising=False)

    literature._semanticscholar = None
    literature._crossref = None
    literature._openalex = None
    yield
    literature._semanticscholar = None
    literature._crossref = None
    literature._openalex = None
