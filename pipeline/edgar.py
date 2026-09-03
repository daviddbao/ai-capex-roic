"""SEC EDGAR client with a dimension-aware inline-XBRL parser.

Why this module exists at all
-----------------------------
The ``companyfacts`` summary API returns **undimensioned facts only**. Two of
the model's five demand facts are dimensioned, so a ``companyfacts``-only
fetcher gets 7 of 10 core facts right, **1 silently wrong** (MSFT: $684B total
RPO instead of $678B commercial RPO) and **1 silently missing** (AMZN: no RPO
fact at all since 2020). Both figures do exist in XBRL -- as ``ix:nonFraction``
elements in the filing's primary inline-XBRL document, carrying dimensional
contexts. Reading them requires a filing-level parse, which is what
:func:`parse_inline_xbrl` provides.

Design rules
------------
* Every request carries a descriptive ``User-Agent``; ``data.sec.gov`` rejects
  requests without one.
* Requests are rate-limited to well under SEC's 10 requests/second ceiling.
* Every raw response is cached to disk under ``pipeline/.cache/`` keyed by URL,
  so a re-run (and the replay test) does not re-hit SEC.
* Nothing here fabricates a value. A failed fetch raises :class:`FetchError`.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import REPO_ROOT

__all__ = [
    "USER_AGENT",
    "CACHE_DIR",
    "FetchError",
    "CachedResponse",
    "EdgarClient",
    "Context",
    "Fact",
    "InlineXbrlDocument",
    "parse_inline_xbrl",
    "Filing",
]

#: data.sec.gov requires a descriptive User-Agent naming the requester.
USER_AGENT = (
    "ai-capex-roic quarterly refresh pipeline (research; contact d4.t3st1ng@gmail.com)"
)

CACHE_DIR: Path = REPO_ROOT / "pipeline" / ".cache"

#: SEC's published ceiling is 10 requests/second. Stay comfortably under it.
_MIN_REQUEST_INTERVAL_S = 0.20
_MAX_RETRIES = 4
_RETRY_BACKOFF_S = (1.0, 3.0, 8.0, 20.0)


class FetchError(RuntimeError):
    """A network fetch failed. Never swallowed, never defaulted to a value."""


# ---------------------------------------------------------------------------
# HTTP + cache
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CachedResponse:
    """One cached HTTP response plus the metadata needed for an audit trail."""

    url: str
    path: Path
    body: bytes
    sha256: str
    fetched_at: str
    from_cache: bool

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))


def _cache_key(url: str) -> str:
    """Readable, collision-free cache filename for a URL."""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    tail = re.sub(r"[^A-Za-z0-9._-]+", "_", url.rsplit("/", 1)[-1])[:80] or "response"
    return f"{digest}__{tail}"


class EdgarClient:
    """Polite, disk-cached EDGAR client.

    Args:
        user_agent: descriptive UA string sent on every request.
        cache_dir: directory for cached raw responses.
        offline: when True, never touch the network -- a cache miss raises
            :class:`FetchError`. Used by the replay test so it is reproducible
            once the cache is warm.
        min_interval_s: minimum spacing between network requests.
    """

    def __init__(
        self,
        user_agent: str = USER_AGENT,
        cache_dir: Path | str = CACHE_DIR,
        offline: bool = False,
        min_interval_s: float = _MIN_REQUEST_INTERVAL_S,
    ) -> None:
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir)
        self.offline = offline
        self.min_interval_s = min_interval_s
        self._last_request_at = 0.0
        self.request_log: list[dict[str, Any]] = []

    # -- low level ---------------------------------------------------------

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_s:
            time.sleep(self.min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def get(self, url: str, refresh: bool = False) -> CachedResponse:
        """Fetch ``url``, serving from the disk cache when possible.

        Raises:
            FetchError: on any network failure, non-200 status, or on a cache
                miss while ``offline``. Callers must not substitute a value.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        key = _cache_key(url)
        body_path = self.cache_dir / key
        meta_path = self.cache_dir / f"{key}.meta.json"

        if not refresh and body_path.exists() and meta_path.exists():
            body = body_path.read_bytes()
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self.request_log.append({"url": url, "from_cache": True})
            return CachedResponse(
                url=url,
                path=body_path,
                body=body,
                sha256=meta.get("sha256", hashlib.sha256(body).hexdigest()),
                fetched_at=meta.get("fetched_at", ""),
                from_cache=True,
            )

        if self.offline:
            raise FetchError(
                f"offline=True and no cached response for {url}. "
                "Warm the cache with a networked run first; a value is never invented."
            )

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            self._throttle()
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Encoding": "gzip, deflate",
                    "Accept": "*/*",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read()
                    encoding = (response.headers.get("Content-Encoding") or "").lower()
                if encoding == "gzip":
                    import gzip

                    raw = gzip.decompress(raw)
                elif encoding == "deflate":
                    import zlib

                    raw = zlib.decompress(raw)
                break
            except Exception as exc:  # noqa: BLE001 - reported, never masked
                last_exc = exc
                if attempt == _MAX_RETRIES - 1:
                    raise FetchError(f"GET {url} failed after {_MAX_RETRIES} attempts: {exc!r}") from exc
                time.sleep(_RETRY_BACKOFF_S[attempt])
        else:  # pragma: no cover - defensive
            raise FetchError(f"GET {url} failed: {last_exc!r}")

        digest = hashlib.sha256(raw).hexdigest()
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        body_path.write_bytes(raw)
        meta_path.write_text(
            json.dumps(
                {
                    "url": url,
                    "sha256": digest,
                    "bytes": len(raw),
                    "fetched_at": fetched_at,
                    "user_agent": self.user_agent,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self.request_log.append({"url": url, "from_cache": False, "bytes": len(raw)})
        return CachedResponse(
            url=url,
            path=body_path,
            body=raw,
            sha256=digest,
            fetched_at=fetched_at,
            from_cache=False,
        )

    # -- EDGAR endpoints ---------------------------------------------------

    @staticmethod
    def submissions_url(cik: str) -> str:
        return f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json"

    @staticmethod
    def companyfacts_url(cik: str) -> str:
        return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json"

    def submissions(self, cik: str, refresh: bool = False) -> dict[str, Any]:
        """The EDGAR submissions index for one CIK."""
        return self.get(self.submissions_url(cik), refresh=refresh).json()

    def companyfacts(self, cik: str, refresh: bool = False) -> dict[str, Any]:
        """The companyfacts summary. UNDIMENSIONED FACTS ONLY -- see module docstring."""
        return self.get(self.companyfacts_url(cik), refresh=refresh).json()

    def filings(
        self,
        cik: str,
        forms: Sequence[str] = ("10-K", "10-Q", "8-K"),
        since: str | None = None,
        refresh: bool = False,
    ) -> list["Filing"]:
        """Filing index for a CIK, newest first.

        Args:
            cik: 10-digit or int-ish CIK.
            forms: form types to keep.
            since: ISO date; keep only filings filed on/after this date.
        """
        data = self.submissions(cik, refresh=refresh)
        recent = data.get("filings", {}).get("recent", {})
        out: list[Filing] = []
        cik_int = int(str(cik).lstrip("0") or "0")
        count = len(recent.get("accessionNumber", []))
        for i in range(count):
            form = recent["form"][i]
            if forms and form not in forms:
                continue
            filed = recent["filingDate"][i]
            if since and filed < since:
                continue
            accession = recent["accessionNumber"][i]
            accession_nodash = accession.replace("-", "")
            primary = recent.get("primaryDocument", [""] * count)[i]
            out.append(
                Filing(
                    cik=str(cik).zfill(10),
                    form=form,
                    accession=accession,
                    filing_date=filed,
                    report_date=recent.get("reportDate", [""] * count)[i],
                    items=recent.get("items", [""] * count)[i],
                    primary_document=primary,
                    primary_doc_url=(
                        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
                        f"{accession_nodash}/{primary}"
                    ),
                    filing_index_url=(
                        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
                        f"{accession_nodash}/{accession}-index.htm"
                    ),
                )
            )
        return out

    def find_filing_for_period(
        self,
        cik: str,
        period_end: str,
        forms: Sequence[str] = ("10-K", "10-Q"),
        refresh: bool = False,
    ) -> "Filing | None":
        """The periodic filing whose ``reportDate`` equals ``period_end``.

        This is the trigger condition recommended by ``docs/EARNINGS_CALENDAR.md``:
        fire the refresh when a 10-Q/10-K appears whose reportDate is the target
        period end. Returns None when the filing has not landed yet.
        """
        for filing in self.filings(cik, forms=forms, refresh=refresh):
            if filing.report_date == period_end:
                return filing
        return None

    def filing_index_json(self, filing: "Filing", refresh: bool = False) -> dict[str, Any]:
        """The ``index.json`` listing every document in a filing's folder."""
        cik_int = int(filing.cik.lstrip("0") or "0")
        url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
            f"{filing.accession.replace('-', '')}/index.json"
        )
        return self.get(url, refresh=refresh).json()

    def inline_xbrl(self, url: str, refresh: bool = False) -> "InlineXbrlDocument":
        """Download and parse a primary inline-XBRL document."""
        response = self.get(url, refresh=refresh)
        return parse_inline_xbrl(response.text, source_url=url, sha256=response.sha256)


@dataclass(frozen=True)
class Filing:
    """One EDGAR filing as seen from the submissions index."""

    cik: str
    form: str
    accession: str
    filing_date: str
    report_date: str
    items: str
    primary_document: str
    primary_doc_url: str
    filing_index_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cik": self.cik,
            "form": self.form,
            "accession": self.accession,
            "filing_date": self.filing_date,
            "report_date": self.report_date,
            "items": self.items,
            "primary_document": self.primary_document,
            "primary_doc_url": self.primary_doc_url,
            "filing_index_url": self.filing_index_url,
        }


# ---------------------------------------------------------------------------
# Inline XBRL parsing -- the part companyfacts cannot do
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Context:
    """An ``xbrli:context``: a period plus zero or more dimension members.

    ``explicit_dimensions`` maps e.g. ``srt:MajorCustomersAxis`` ->
    ``msft:CommercialCustomersMember``. ``typed_dimensions`` maps an axis to
    the text of its typed member, e.g. Amazon's
    ``...ExpectedTimingOfSatisfactionStartDateAxis`` -> ``2026-07-01``.
    """

    id: str
    instant: str | None = None
    start: str | None = None
    end: str | None = None
    explicit_dimensions: Mapping[str, str] = field(default_factory=dict)
    typed_dimensions: Mapping[str, str] = field(default_factory=dict)

    @property
    def is_undimensioned(self) -> bool:
        return not self.explicit_dimensions and not self.typed_dimensions

    @property
    def axes(self) -> set[str]:
        return set(self.explicit_dimensions) | set(self.typed_dimensions)

    @property
    def duration_days(self) -> int | None:
        if not (self.start and self.end):
            return None
        try:
            return (date.fromisoformat(self.end) - date.fromisoformat(self.start)).days
        except ValueError:
            return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instant": self.instant,
            "start": self.start,
            "end": self.end,
            "explicit_dimensions": dict(self.explicit_dimensions),
            "typed_dimensions": dict(self.typed_dimensions),
        }


@dataclass(frozen=True)
class Fact:
    """One ``ix:nonFraction`` fact, with its context resolved."""

    concept: str
    value: float
    raw_text: str
    scale: int
    sign: str
    decimals: str
    unit_ref: str
    context: Context
    source_url: str = ""

    @property
    def context_id(self) -> str:
        return self.context.id

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept": self.concept,
            "value": self.value,
            "raw_text": self.raw_text,
            "scale": self.scale,
            "sign": self.sign,
            "decimals": self.decimals,
            "unit_ref": self.unit_ref,
            "context": self.context.to_dict(),
            "source_url": self.source_url,
        }


_CONTEXT_RE = re.compile(
    r"<(?:[A-Za-z0-9_.-]+:)?context\b[^>]*\bid=\"([^\"]+)\"[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?context>",
    re.DOTALL | re.IGNORECASE,
)
_INSTANT_RE = re.compile(r"<(?:[A-Za-z0-9_.-]+:)?instant\b[^>]*>\s*([^<\s]+)\s*<", re.IGNORECASE)
_START_RE = re.compile(r"<(?:[A-Za-z0-9_.-]+:)?startDate\b[^>]*>\s*([^<\s]+)\s*<", re.IGNORECASE)
_END_RE = re.compile(r"<(?:[A-Za-z0-9_.-]+:)?endDate\b[^>]*>\s*([^<\s]+)\s*<", re.IGNORECASE)
_EXPLICIT_RE = re.compile(
    r"<(?:[A-Za-z0-9_.-]+:)?explicitMember\b[^>]*\bdimension=\"([^\"]+)\"[^>]*>\s*([^<]+?)\s*</",
    re.DOTALL | re.IGNORECASE,
)
_TYPED_RE = re.compile(
    r"<(?:[A-Za-z0-9_.-]+:)?typedMember\b[^>]*\bdimension=\"([^\"]+)\"[^>]*>(.*?)</(?:[A-Za-z0-9_.-]+:)?typedMember>",
    re.DOTALL | re.IGNORECASE,
)
_NONFRACTION_RE = re.compile(
    r"<ix:nonFraction\b(?P<attrs>[^>]*)>(?P<body>.*?)</ix:nonFraction>",
    re.DOTALL | re.IGNORECASE,
)
_ATTR_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_.:-]*)\s*=\s*\"([^\"]*)\"")
_TAG_RE = re.compile(r"<[^>]*>")


def _strip_tags(fragment: str) -> str:
    return _TAG_RE.sub("", fragment)


def _parse_contexts(document: str) -> dict[str, Context]:
    contexts: dict[str, Context] = {}
    for match in _CONTEXT_RE.finditer(document):
        cid, body = match.group(1), match.group(2)
        instant = _INSTANT_RE.search(body)
        start = _START_RE.search(body)
        end = _END_RE.search(body)
        explicit = {
            axis.strip(): member.strip() for axis, member in _EXPLICIT_RE.findall(body)
        }
        typed = {}
        for axis, inner in _TYPED_RE.findall(body):
            typed[axis.strip()] = _strip_tags(inner).strip()
        contexts[cid] = Context(
            id=cid,
            instant=instant.group(1) if instant else None,
            start=start.group(1) if start else None,
            end=end.group(1) if end else None,
            explicit_dimensions=explicit,
            typed_dimensions=typed,
        )
    return contexts


def _to_number(text: str, scale: int, sign: str) -> float | None:
    cleaned = _strip_tags(text)
    cleaned = (
        cleaned.replace("&#160;", "")
        .replace("&nbsp;", "")
        .replace(" ", "")
        .replace(",", "")
        .replace("$", "")
        .replace("%", "")
        .strip()
    )
    if cleaned in {"", "-", "—", "–"}:
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    value *= 10**scale
    if sign == "-":
        value = -value
    return value


@dataclass
class InlineXbrlDocument:
    """Parsed inline-XBRL document: every numeric fact with its full context.

    This is the object that makes MSFT's commercial RPO and AMZN's RPO
    reachable at all.
    """

    source_url: str
    sha256: str
    contexts: dict[str, Context]
    facts: list[Fact]

    def by_concept(self, concept: str) -> list[Fact]:
        """All facts for a concept, in document order. Concept is ``prefix:Name``."""
        wanted = concept.split(":")[-1].lower()
        prefix = concept.split(":")[0].lower() if ":" in concept else None
        out = []
        for fact in self.facts:
            parts = fact.concept.split(":")
            name = parts[-1].lower()
            fact_prefix = parts[0].lower() if len(parts) > 1 else None
            if name != wanted:
                continue
            if prefix and fact_prefix and prefix != fact_prefix:
                continue
            out.append(fact)
        return out

    def select(
        self,
        concept: str,
        instant: str | None = None,
        start: str | None = None,
        end: str | None = None,
        required_explicit_dimensions: Mapping[str, str] | None = None,
        required_axes: Iterable[str] = (),
        forbidden_axes: Iterable[str] = (),
        must_be_undimensioned: bool = False,
    ) -> list[Fact]:
        """Facts matching a concept + period + dimensional predicate.

        Dimensional selection is by **axis presence**, never by a hardcoded
        typed-member value: Amazon's timing-axis member is the day after period
        end and moves every quarter (trap T10).
        """
        required_explicit = dict(required_explicit_dimensions or {})
        required_axes = set(required_axes)
        forbidden_axes = set(forbidden_axes)
        out: list[Fact] = []
        for fact in self.by_concept(concept):
            ctx = fact.context
            if instant is not None and ctx.instant != instant:
                continue
            if start is not None and ctx.start != start:
                continue
            if end is not None and ctx.end != end:
                continue
            if must_be_undimensioned and not ctx.is_undimensioned:
                continue
            if any(ctx.explicit_dimensions.get(a) != m for a, m in required_explicit.items()):
                continue
            if not required_axes <= ctx.axes:
                continue
            if forbidden_axes & ctx.axes:
                continue
            out.append(fact)
        return out


def parse_inline_xbrl(
    document: str, source_url: str = "", sha256: str = ""
) -> InlineXbrlDocument:
    """Parse an inline-XBRL primary document into contexts and numeric facts.

    Deliberately regex-based rather than XML-based: EDGAR primary documents are
    large HTML files that are not reliably well-formed XML, and the namespace
    prefix for the context elements varies between filers (``xbrli:``, ``xbrl:``,
    bare ``context``). What must be exact is the *contextRef -> dimensions*
    resolution, which is what the model's correctness turns on.
    """
    contexts = _parse_contexts(document)
    facts: list[Fact] = []
    for match in _NONFRACTION_RE.finditer(document):
        attrs = dict(_ATTR_RE.findall(match.group("attrs")))
        concept = attrs.get("name", "")
        context_ref = attrs.get("contextRef") or attrs.get("contextref") or ""
        context = contexts.get(context_ref)
        if context is None:
            # A fact whose context we cannot resolve is unusable: we would not
            # know its period or its dimensions. Skip rather than guess.
            continue
        scale = int(attrs.get("scale", "0") or 0)
        sign = attrs.get("sign", "")
        value = _to_number(match.group("body"), scale, sign)
        if value is None:
            continue
        facts.append(
            Fact(
                concept=concept,
                value=value,
                raw_text=_strip_tags(match.group("body")).strip()[:64],
                scale=scale,
                sign=sign,
                decimals=attrs.get("decimals", ""),
                unit_ref=attrs.get("unitRef") or attrs.get("unitref") or "",
                context=context,
                source_url=source_url,
            )
        )
    return InlineXbrlDocument(
        source_url=source_url, sha256=sha256, contexts=contexts, facts=facts
    )


# ---------------------------------------------------------------------------
# companyfacts helpers
# ---------------------------------------------------------------------------


def companyfacts_units(
    facts: Mapping[str, Any], concept: str, unit: str = "USD"
) -> list[dict[str, Any]]:
    """All unit entries for ``concept`` from a companyfacts payload.

    ``concept`` is ``taxonomy:Name`` e.g. ``us-gaap:PaymentsToAcquireProductiveAssets``.
    Returns [] when the concept is absent -- an ABSENCE, which callers must
    treat as a hard failure rather than as a zero (the Amazon RPO trap).
    """
    taxonomy, _, name = concept.partition(":")
    if not name:
        taxonomy, name = "us-gaap", concept
    return list(facts.get("facts", {}).get(taxonomy, {}).get(name, {}).get("units", {}).get(unit, []))


def pick_duration(
    entries: Sequence[Mapping[str, Any]], start: str, end: str
) -> list[dict[str, Any]]:
    """companyfacts entries whose start AND end match exactly.

    Never "the latest fact": GOOG/ORCL/META tag only year-to-date durations, so
    the newest entry is a cumulative figure, not a quarter (trap T8).
    """
    return [dict(e) for e in entries if e.get("start") == start and e.get("end") == end]


def pick_instant(entries: Sequence[Mapping[str, Any]], instant: str) -> list[dict[str, Any]]:
    """companyfacts entries at an exact instant."""
    return [dict(e) for e in entries if e.get("end") == instant and "start" not in e]


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    """``python -m pipeline.edgar poll [--since YYYY-MM-DD]`` -- filing check."""
    sys.stdout.reconfigure(encoding="utf-8")
    from .extract import load_source_map

    source_map = load_source_map()
    client = EdgarClient()
    since = None
    if "--since" in argv:
        since = argv[argv.index("--since") + 1]
    for ticker, company in source_map["companies"].items():
        print(f"\n=== {ticker} ({company['cik']}) ===")
        for filing in client.filings(company["cik"], since=since)[:6]:
            print(
                f"  {filing.form:6s} report={filing.report_date} filed={filing.filing_date} "
                f"{filing.accession}"
            )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
