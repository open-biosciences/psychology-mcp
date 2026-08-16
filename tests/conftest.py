"""Shared pytest configuration.

Integration tests reach the LIVE Crossref and OpenAlex APIs. They are opt-in behind
`--run-integration` rather than merely marked, because a marker alone does not stop a bare
`pytest` from spending another service's rate budget as a side effect of running the suite.
"""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests that make live calls to Crossref and OpenAlex.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(reason="live API test; pass --run-integration to enable")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
