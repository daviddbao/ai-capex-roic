"""Read/write helpers for the ``data/`` layer.

Reading is unrestricted. WRITING happens only through :mod:`pipeline.apply`,
and only with an approved packet -- nothing else in this package touches
``data/``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import REPO_ROOT

__all__ = [
    "DATA_DIR",
    "FACTS_CSV",
    "SOURCES_CSV",
    "ASSUMPTIONS_CSV",
    "FACTS_COLUMNS",
    "SOURCES_COLUMNS",
    "read_csv",
    "append_rows",
    "facts_by_ticker",
    "prior_row",
    "source_id_for",
]

DATA_DIR: Path = REPO_ROOT / "data"
FACTS_CSV: Path = DATA_DIR / "facts.csv"
SOURCES_CSV: Path = DATA_DIR / "sources.csv"
ASSUMPTIONS_CSV: Path = DATA_DIR / "assumptions.csv"

FACTS_COLUMNS: tuple[str, ...] = (
    "company",
    "ticker",
    "report_bucket",
    "fiscal_period",
    "period_end",
    "rpo_backlog_or_revenue_usd_b",
    "fact_metric",
    "quarterly_capex_usd_b",
    "capex_definition",
    "fact_source_url",
    "capex_source_url",
    "evidence_derivation",
    "fact_source_id",
    "capex_source_id",
)

SOURCES_COLUMNS: tuple[str, ...] = (
    "source_id",
    "url",
    "company",
    "period",
    "kind",
    "title_or_description",
    "local_path_if_any",
    "reported_value",
    "classification",
    "evidence_derivation",
    "status",
    "caveat",
    "in_workbook_ledger",
)


def read_csv(path: Path | str) -> list[dict[str, str]]:
    """Read a UTF-8 CSV into a list of dicts."""
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_rows(
    path: Path | str, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]
) -> None:
    """Append rows to an existing CSV, preserving its column order and encoding.

    LF line endings and RFC-4180 quoting, matching how ``data/`` was written.
    """
    path = Path(path)
    with open(path, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), lineterminator="\n")
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in columns})


def facts_by_ticker(path: Path | str = FACTS_CSV) -> dict[str, list[dict[str, str]]]:
    """Existing facts grouped by ticker, in file order."""
    out: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(path):
        out.setdefault(row["ticker"], []).append(row)
    return out


def prior_row(
    ticker: str, model_period_key: str, path: Path | str = FACTS_CSV
) -> dict[str, str] | None:
    """The row immediately preceding ``model_period_key`` for ``ticker``.

    Used for sequential-move sanity checks. Returns the last row on file when
    the target period is not yet present (the normal refresh case).
    """
    rows = facts_by_ticker(path).get(ticker, [])
    if not rows:
        return None
    for i, row in enumerate(rows):
        if row["report_bucket"] == model_period_key:
            return rows[i - 1] if i else None
    return rows[-1]


def existing_row(
    ticker: str, model_period_key: str, path: Path | str = FACTS_CSV
) -> dict[str, str] | None:
    """The row for exactly this company-quarter, if one is already on file."""
    for row in read_csv(path):
        if row["ticker"] == ticker and row["report_bucket"] == model_period_key:
            return row
    return None


def source_id_for(ticker: str, model_period_key: str, kind: str) -> str:
    """``MSFT``, ``Q2 26``, ``FACT`` -> ``MSFT-Q226-FACT`` (the ledger convention)."""
    compact = model_period_key.replace(" ", "")
    return f"{ticker}-{compact}-{kind.upper()}"
