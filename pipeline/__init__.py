"""Quarterly data-refresh pipeline for the AI capex / forward ROIC model.

Nothing in this package writes to ``data/`` except :mod:`pipeline.apply`, and
that module refuses to run without an explicitly signed-off review packet.

Modules
-------
edgar    -- SEC EDGAR client: submissions polling, companyfacts, and an
            inline-XBRL parser that can read DIMENSIONED facts.
extract  -- per-company fact extraction driven by ``source_map.json``.
guards   -- the 15 documented definitional traps, as executable checks.
draft    -- assembles a human-reviewable packet for one company-quarter.
apply    -- appends an APPROVED packet to ``data/``, idempotently.
archive  -- snapshots primary filings to ``01_sources/company_filings/``.
"""

from __future__ import annotations

__all__ = ["REPO_ROOT"]

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[1]
