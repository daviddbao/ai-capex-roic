"""Shared fixtures.

The extraction fixtures are session-scoped because each one parses five large
inline-XBRL documents. Responses come from the on-disk cache in
``pipeline/.cache`` when it is warm, so a re-run does not re-hit ``data.sec.gov``.
Set ``PIPELINE_OFFLINE=1`` to forbid network access entirely and fail on a cache
miss instead of fetching.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.edgar import EdgarClient  # noqa: E402
from pipeline.extract import TICKERS, extract_company, load_source_map  # noqa: E402

REPLAY_BUCKET = "CY2026Q2"


@pytest.fixture(scope="session")
def source_map() -> dict:
    return load_source_map()


@pytest.fixture(scope="session")
def client() -> EdgarClient:
    return EdgarClient(offline=os.environ.get("PIPELINE_OFFLINE") == "1")


@pytest.fixture(scope="session")
def replay_extractions(client, source_map) -> dict:
    """Every company extracted for the quarter ending June 2026."""
    return {
        ticker: extract_company(ticker, REPLAY_BUCKET, client=client, source_map=source_map)
        for ticker in TICKERS
    }
