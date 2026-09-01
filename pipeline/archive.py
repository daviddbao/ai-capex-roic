"""Snapshot primary filings to ``01_sources/company_filings/`` at fetch time.

Why
---
``data/sources.csv`` records a ``local_path_if_any`` for 41 of 62 sources, and
the methodology doc describes preserved local copies. **Those files do not
exist in this repository.** The audit trail is currently URLs only. SEC EDGAR
Archives URLs are durable, but IR pages, webcast pages and earnings slide decks
-- which are the sole source for four of the five annual denominators and for
Microsoft's quarterly capex -- rot. This module fixes that going forward.

Layout::

    01_sources/company_filings/<Company>/<accession>/<filename>
    01_sources/company_filings/<Company>/<accession>/MANIFEST.json
    01_sources/manifest.json          -- append-only index of every snapshot

Every snapshot records the URL, the SHA-256 of the bytes, the byte count and
the UTC fetch time, so a later reader can prove the local copy is the document
that was actually read.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from . import REPO_ROOT
from .edgar import EdgarClient, FetchError

__all__ = [
    "ARCHIVE_ROOT",
    "INDEX_PATH",
    "ArchivedFile",
    "archive_url",
    "archive_extraction",
    "relative_path",
]

ARCHIVE_ROOT: Path = REPO_ROOT / "01_sources" / "company_filings"
INDEX_PATH: Path = REPO_ROOT / "01_sources" / "manifest.json"

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    return _SAFE_RE.sub("_", name).strip("_") or "file"


@dataclass(frozen=True)
class ArchivedFile:
    """One preserved document."""

    url: str
    local_path: Path
    repo_relative_path: str
    sha256: str
    bytes: int
    fetched_at: str
    company: str
    accession: str
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "repo_relative_path": self.repo_relative_path,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "fetched_at": self.fetched_at,
            "company": self.company,
            "accession": self.accession,
            "role": self.role,
        }


def relative_path(path: Path) -> str:
    """Repo-relative POSIX path, matching the ``local_path_if_any`` convention."""
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def archive_url(
    url: str,
    company: str,
    accession: str,
    role: str = "primary_document",
    client: EdgarClient | None = None,
    archive_root: Path | str = ARCHIVE_ROOT,
    index_path: Path | str | None = INDEX_PATH,
) -> ArchivedFile:
    """Fetch ``url`` (via the cache) and write a permanent local copy.

    Raises:
        FetchError: the fetch failed. Nothing is written and nothing is faked.
    """
    client = client or EdgarClient()
    response = client.get(url)

    folder = Path(archive_root) / _safe(company) / _safe(accession or "misc")
    folder.mkdir(parents=True, exist_ok=True)
    filename = _safe(url.rsplit("/", 1)[-1] or "document.htm")
    destination = folder / filename
    destination.write_bytes(response.body)

    archived = ArchivedFile(
        url=url,
        local_path=destination,
        repo_relative_path=relative_path(destination),
        sha256=response.sha256,
        bytes=len(response.body),
        fetched_at=response.fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        company=company,
        accession=accession,
        role=role,
    )

    manifest_path = folder / "MANIFEST.json"
    manifest: dict[str, Any] = {"company": company, "accession": accession, "files": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [f for f in manifest.get("files", []) if f.get("url") != url]
    manifest["files"].append(archived.to_dict())
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if index_path is not None:
        index_file = Path(index_path)
        index_file.parent.mkdir(parents=True, exist_ok=True)
        index: dict[str, Any] = {"snapshots": []}
        if index_file.exists():
            index = json.loads(index_file.read_text(encoding="utf-8"))
        index["snapshots"] = [s for s in index.get("snapshots", []) if s.get("url") != url]
        index["snapshots"].append(archived.to_dict())
        index["updated"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        index_file.write_text(json.dumps(index, indent=2), encoding="utf-8")

    return archived


def archive_extraction(
    extraction: Any,
    client: EdgarClient | None = None,
    archive_root: Path | str = ARCHIVE_ROOT,
    index_path: Path | str | None = INDEX_PATH,
) -> list[ArchivedFile]:
    """Snapshot every primary source behind one company-quarter extraction.

    Covers the 10-Q/10-K primary inline-XBRL document, the earnings 8-K and its
    Exhibit 99.1. Failures are reported to the caller, never swallowed.
    """
    client = client or EdgarClient()
    out: list[ArchivedFile] = []
    company = extraction.company_name
    targets: list[tuple[str, str, str]] = []
    if extraction.periodic_filing:
        filing = extraction.periodic_filing
        targets.append((filing["primary_doc_url"], filing["accession"], f"{filing['form']} primary document"))
    if extraction.earnings_8k:
        eight_k = extraction.earnings_8k
        targets.append((eight_k["primary_doc_url"], eight_k["accession"], "8-K Item 2.02"))
        if extraction.exhibit_991_url:
            targets.append((extraction.exhibit_991_url, eight_k["accession"], "8-K Exhibit 99.1"))
    for url, accession, role in targets:
        if not url:
            continue
        out.append(
            archive_url(
                url,
                company=company,
                accession=accession,
                role=role,
                client=client,
                archive_root=archive_root,
                index_path=index_path,
            )
        )
    return out


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    """``python -m pipeline.archive CY2026Q2 [TICKER ...]``."""
    sys.stdout.reconfigure(encoding="utf-8")
    from .extract import TICKERS, extract_company, load_source_map

    bucket = argv[0] if argv else "CY2026Q2"
    tickers = argv[1:] or list(TICKERS)
    source_map = load_source_map()
    client = EdgarClient()
    for ticker in tickers:
        extraction = extract_company(ticker, bucket, client=client, source_map=source_map)
        try:
            files = archive_extraction(extraction, client=client)
        except FetchError as exc:
            print(f"{ticker}: ARCHIVE FAILED -- {exc}")
            continue
        print(f"{ticker}: archived {len(files)} document(s)")
        for f in files:
            print(f"    {f.role:24s} {f.bytes:>10,} bytes  {f.repo_relative_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
