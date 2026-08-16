"""Integration-suite guard.

The live suite must run the way the deployment runs. `PSYCHOLOGY_MCP_CONTACT_EMAIL` is
what puts requests into the Crossref and OpenAlex **polite pools**; without it they fall
back to the anonymous pool, where Crossref documents a lower, unspecified limit.

Both still work — Tier 0 is keyless — which is exactly the danger: an unset variable
produces a green suite that silently measured different rate behaviour from production.
That happened. This guard makes it impossible to repeat.
"""

import os

import pytest

CONTACT_VAR = "PSYCHOLOGY_MCP_CONTACT_EMAIL"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get(CONTACT_VAR, "").strip():
        return
    skip = pytest.mark.skip(
        reason=(
            f"{CONTACT_VAR} is unset — the live suite would run against the ANONYMOUS "
            f"pool, not the polite pool the deployment uses. Run `cp .env.example .env`, "
            f"set the address, and export it."
        )
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
