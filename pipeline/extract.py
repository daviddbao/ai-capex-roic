"""Per-company fact extraction driven by ``pipeline/source_map.json``.

Every field carries an ``automation_tier`` and the extractor honours it:

``auto``     -- a single verified XBRL fact, uniquely identified by
                concept + period + dimensional context. No arithmetic.
``derived``  -- arithmetic over verified tags. GOOG / ORCL / META tag
                YEAR-TO-DATE cash flows only, so a quarter must be produced by
                differencing against the prior period end. AMZN is the only
                filer tagging standalone 3-month durations; MSFT tags them in
                Q1-Q3 but not in Q4.
``manual``   -- the figure does not exist as an XBRL fact anywhere in the SEC
                filings. The extractor DOES NOT GUESS. It emits a refusal
                naming exactly what a human must find and where to look.

Access branching is equally load-bearing. ``companyfacts`` returns
undimensioned facts only; a field marked ``inline_xbrl_dimensional`` must be
read out of the filing's primary inline-XBRL document or it will come back
wrong (MSFT: $684B total RPO instead of $678B commercial) or empty (AMZN).
"""

from __future__ import annotations

import calendar
import json
import re
import sys
from dataclasses import dataclass, field as dc_field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import REPO_ROOT
from .edgar import (
    EdgarClient,
    FetchError,
    Filing,
    InlineXbrlDocument,
    companyfacts_units,
    pick_duration,
    pick_instant,
)

__all__ = [
    "SOURCE_MAP_PATH",
    "load_source_map",
    "Period",
    "resolve_period",
    "bucket_to_model_key",
    "model_key_to_bucket",
    "ExtractedField",
    "CompanyExtraction",
    "extract_company",
    "extract_all",
    "TICKERS",
]

SOURCE_MAP_PATH: Path = REPO_ROOT / "pipeline" / "source_map.json"

TICKERS: tuple[str, ...] = ("MSFT", "GOOG", "AMZN", "ORCL", "META")

#: The three fields the model consumes per company per refresh.
FIELDS: tuple[str, ...] = ("demand_fact", "capex_fact", "annual_denominator")

_BUCKET_RE = re.compile(r"^CY(\d{4})Q([1-4])$")
_MODEL_KEY_RE = re.compile(r"^Q([1-4])\s+(\d{2})$")


def load_source_map(path: Path | str = SOURCE_MAP_PATH) -> dict[str, Any]:
    """Load the authoritative per-company mapping. This file is the spec."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Period arithmetic
# ---------------------------------------------------------------------------


def bucket_to_model_key(report_bucket: str) -> str:
    """``CY2026Q2`` -> ``Q2 26`` (the key ``data/facts.csv`` uses)."""
    m = _BUCKET_RE.match(report_bucket)
    if not m:
        raise ValueError(f"not a report bucket: {report_bucket!r}")
    year, quarter = m.group(1), m.group(2)
    return f"Q{quarter} {year[2:]}"


def model_key_to_bucket(model_key: str) -> str:
    """``Q2 26`` -> ``CY2026Q2``."""
    m = _MODEL_KEY_RE.match(model_key.strip())
    if not m:
        raise ValueError(f"not a model period key: {model_key!r}")
    quarter, yy = m.group(1), m.group(2)
    return f"CY20{yy}Q{quarter}"


def _end_of_month(year: int, month: int) -> date:
    while month > 12:
        year, month = year + 1, month - 12
    while month < 1:
        year, month = year - 1, month + 12
    return date(year, month, calendar.monthrange(year, month)[1])


def _add_months_to_month_end(anchor: date, months: int) -> date:
    return _end_of_month(anchor.year, anchor.month + months)


@dataclass(frozen=True)
class Period:
    """Every date the extraction needs for one company-quarter.

    ``period_end`` is the issuer's own period end, which is NOT the calendar
    quarter end for Oracle (trap T13): the CY2026Q2 bucket is Oracle's quarter
    ended 2026-05-31.
    """

    ticker: str
    report_bucket: str
    model_period_key: str
    calendar_quarter_end: str
    period_end: str
    prior_period_end: str
    quarter_start: str
    fiscal_year_start: str
    fiscal_quarter: int
    fiscal_year_label: str
    fiscal_period: str
    expected_form: str
    ytd_is_quarter: bool
    source_map_agrees: bool | None
    source_map_period_end: str | None

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def resolve_period(company: Mapping[str, Any], report_bucket: str, ticker: str) -> Period:
    """Compute every date for ``ticker`` in ``report_bucket`` from first principles.

    The result is cross-checked against ``report_bucket_map`` in
    ``source_map.json`` when that bucket is recorded there; a disagreement is
    surfaced (``source_map_agrees``) rather than silently resolved, because it
    would mean the spec has drifted from the filer's actual calendar.
    """
    m = _BUCKET_RE.match(report_bucket)
    if not m:
        raise ValueError(f"not a report bucket: {report_bucket!r}")
    year, quarter = int(m.group(1)), int(m.group(2))
    cal_quarter_end = _end_of_month(year, quarter * 3)

    offset = int(company.get("reporting_calendar_offset_months", 0))
    period_end = _add_months_to_month_end(cal_quarter_end, offset)
    prior_period_end = _add_months_to_month_end(period_end, -3)
    quarter_start = prior_period_end + timedelta(days=1)

    fye_month, fye_day = (int(x) for x in str(company["fiscal_year_end"]).split("-"))
    fy_end_this = date(period_end.year, fye_month, calendar.monthrange(period_end.year, fye_month)[1])
    if period_end > fy_end_this:
        fy_end = _end_of_month(period_end.year + 1, fye_month)
    else:
        fy_end = fy_end_this
    fy_start = _end_of_month(fy_end.year, fy_end.month - 11).replace(day=1)

    months_in = (period_end.year - fy_start.year) * 12 + (period_end.month - fy_start.month)
    fiscal_quarter = months_in // 3 + 1
    fiscal_year_label = f"FY{str(fy_end.year)[2:]}"

    if str(company.get("fye_mmdd")) == "1231":
        fiscal_period = f"Q{fiscal_quarter} {period_end.year}"
    else:
        fiscal_period = f"{fiscal_year_label} Q{fiscal_quarter}"

    expected_form = "10-K" if fiscal_quarter == 4 else "10-Q"

    mapped = (company.get("report_bucket_map") or {}).get(report_bucket)
    agrees: bool | None = None
    mapped_end: str | None = None
    if mapped:
        mapped_end = mapped.get("period_end")
        agrees = mapped_end == period_end.isoformat() and (
            mapped.get("form", expected_form) == expected_form
        )

    return Period(
        ticker=ticker,
        report_bucket=report_bucket,
        model_period_key=bucket_to_model_key(report_bucket),
        calendar_quarter_end=cal_quarter_end.isoformat(),
        period_end=period_end.isoformat(),
        prior_period_end=prior_period_end.isoformat(),
        quarter_start=quarter_start.isoformat(),
        fiscal_year_start=fy_start.isoformat(),
        fiscal_quarter=fiscal_quarter,
        fiscal_year_label=fiscal_year_label,
        fiscal_period=fiscal_period,
        expected_form=expected_form,
        ytd_is_quarter=fiscal_quarter == 1,
        source_map_agrees=agrees,
        source_map_period_end=mapped_end,
    )


# ---------------------------------------------------------------------------
# Prose evidence
# ---------------------------------------------------------------------------

_SCRIPT_RE = re.compile(r"<(script|style)\b.*?</\1>", re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t\r\f\v   ]+")
_ENTITY_RE = re.compile(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);")


def visible_text(html: str) -> str:
    """Best-effort plain text of a filing, for quoting corroborating prose."""
    import html as html_mod

    text = _SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    text = html_mod.unescape(text)
    text = text.replace(" ", " ").replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    text = _WS_RE.sub(" ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    return text


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.;])\s+")


def find_sentence(text: str, needles: Sequence[str], max_len: int = 420) -> str:
    """The first sentence containing every needle, verbatim. ``''`` if none.

    Returning an empty string is a real answer: the packet then records
    "no corroborating prose located" rather than inventing a quote.
    """
    lowered = [n.lower() for n in needles if n]
    if not lowered:
        return ""
    for chunk in text.split("\n"):
        for sentence in _SENTENCE_SPLIT_RE.split(chunk):
            s = sentence.strip()
            if not s or len(s) > max_len:
                continue
            low = s.lower()
            if all(n in low for n in lowered):
                return s
    return ""


def _number_variants(value_usd: float) -> list[str]:
    """String forms a filer might use for a USD amount, for prose matching.

    Any form with fewer than three digits is discarded: "$1.8" or "$54" match
    half the document and would produce a quote that is worse than none.
    """
    b = abs(value_usd) / 1e9
    m = abs(value_usd) / 1e6
    candidates: list[str] = []
    if m >= 100:
        candidates.append(f"{m:,.0f}")
    if b >= 1:
        candidates += [f"{b:,.1f}", f"{b:,.2f}", f"{b:,.3f}"]
    if b >= 100:
        candidates.append(f"{b:,.0f}")
    out: list[str] = []
    for c in candidates:
        if sum(ch.isdigit() for ch in c) >= 3 and c not in out:
            out.append(c)
    return out


def find_fragment(text: str, needles: Sequence[str], window: int = 180) -> str:
    """A verbatim window of text around the first needle, containing all needles.

    Used where the evidence is a financial-statement table row rather than a
    sentence -- e.g. Amazon's cash-flow line ``Purchases of property and
    equipment (32,183) (54,208)``. Still verbatim, just not a sentence.
    """
    if not needles:
        return ""
    low = text.lower()
    first = needles[0].lower()
    start = 0
    while True:
        idx = low.find(first, start)
        if idx < 0:
            return ""
        lo, hi = max(0, idx - window), min(len(text), idx + len(first) + window)
        chunk = text[lo:hi]
        if all(n.lower() in chunk.lower() for n in needles):
            return " ".join(chunk.split())
        start = idx + 1


# ---------------------------------------------------------------------------
# Extraction results
# ---------------------------------------------------------------------------


@dataclass
class ExtractedField:
    """One proposed field value -- or an explicit refusal to produce one."""

    ticker: str
    field: str
    label: str
    automation_tier: str
    access: str
    status: str  # extracted | refused_manual | error
    value_usd: float | None = None
    concepts: list[str] = dc_field(default_factory=list)
    derivation: str = ""
    components: list[dict[str, Any]] = dc_field(default_factory=list)
    context: dict[str, Any] | None = None
    source_url: str = ""
    source_sha256: str = ""
    evidence_quote: str = ""
    evidence_quote_source_url: str = ""
    human_instruction: str = ""
    human_source_url: str = ""
    proxy_only: dict[str, Any] | None = None
    model_q2_2026: float | None = None
    notes: list[str] = dc_field(default_factory=list)
    error: str = ""

    @property
    def value_usd_b(self) -> float | None:
        if self.value_usd is None:
            return None
        return round(self.value_usd / 1e9, 6)

    def to_dict(self) -> dict[str, Any]:
        data = {k: getattr(self, k) for k in self.__dataclass_fields__}
        data["value_usd_b"] = self.value_usd_b
        return data


@dataclass
class CompanyExtraction:
    """Everything extracted for one company-quarter, plus its provenance."""

    ticker: str
    company_name: str
    cik: str
    report_bucket: str
    period: Period
    periodic_filing: dict[str, Any] | None
    earnings_8k: dict[str, Any] | None
    exhibit_991_url: str
    fields: dict[str, ExtractedField]
    fetch_errors: list[str] = dc_field(default_factory=list)
    _primary_text: str = ""
    _exhibit_text: str = ""
    _ixbrl: InlineXbrlDocument | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "cik": self.cik,
            "report_bucket": self.report_bucket,
            "period": self.period.to_dict(),
            "periodic_filing": self.periodic_filing,
            "earnings_8k": self.earnings_8k,
            "exhibit_991_url": self.exhibit_991_url,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "fetch_errors": list(self.fetch_errors),
        }


# ---------------------------------------------------------------------------
# Filing discovery
# ---------------------------------------------------------------------------

_EX991_RE = re.compile(r"ex(?:hibit)?[-_]?99[-_.]?1", re.IGNORECASE)


def find_periodic_filing(
    client: EdgarClient, cik: str, period_end: str, expected_form: str
) -> Filing | None:
    """The 10-Q/10-K whose reportDate is the target period end."""
    return client.find_filing_for_period(cik, period_end, forms=("10-K", "10-Q"))


def find_earnings_8k(
    client: EdgarClient, cik: str, period_end: str, upper_bound: str | None = None
) -> Filing | None:
    """The Item 2.02 earnings 8-K for a period.

    8-K ``reportDate`` is the event date, not the period end, so selection is
    "the earliest Item 2.02 8-K filed after the period end". Oracle's annual
    8-K precedes its 10-K by up to 12 days; Microsoft files both the same day.
    """
    candidates = [
        f
        for f in client.filings(cik, forms=("8-K",))
        if "2.02" in (f.items or "") and f.filing_date > period_end
    ]
    if upper_bound:
        candidates = [f for f in candidates if f.filing_date <= upper_bound]
    if not candidates:
        return None
    return min(candidates, key=lambda f: f.filing_date)


def find_exhibit_991(client: EdgarClient, filing: Filing) -> str:
    """URL of a filing's Exhibit 99.1, or ``''`` when it has none."""
    try:
        index = client.filing_index_json(filing)
    except FetchError:
        return ""
    cik_int = int(filing.cik.lstrip("0") or "0")
    base = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{filing.accession.replace('-', '')}/"
    )
    for item in index.get("directory", {}).get("item", []):
        name = item.get("name", "")
        if name.lower().endswith((".htm", ".html")) and _EX991_RE.search(name):
            return base + name
    return ""


# ---------------------------------------------------------------------------
# Field extraction strategies
# ---------------------------------------------------------------------------


def _fact_entry_note(entry: Mapping[str, Any], cik: str = "") -> dict[str, Any]:
    """One companyfacts entry, plus the URL of the filing it came from.

    A derived quarter can draw its two components from two DIFFERENT filings
    (the current 10-K and the prior 10-Q), so each component carries its own
    provenance rather than inheriting the packet's headline filing.
    """
    note = {
        "start": entry.get("start"),
        "end": entry.get("end"),
        "val": entry.get("val"),
        "form": entry.get("form"),
        "accn": entry.get("accn"),
        "filed": entry.get("filed"),
        "fy": entry.get("fy"),
        "fp": entry.get("fp"),
    }
    accn = entry.get("accn") or ""
    if cik and accn:
        cik_int = int(str(cik).lstrip("0") or "0")
        note["filing_url"] = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
            f"{accn.replace('-', '')}/{accn}-index.htm"
        )
    return note


def _extract_companyfacts_instant(
    client: EdgarClient, cik: str, spec: Mapping[str, Any], period: Period, out: ExtractedField
) -> None:
    concept = spec["concept"]
    facts = client.companyfacts(cik)
    entries = companyfacts_units(facts, concept, spec.get("unit", "USD"))
    matches = pick_instant(entries, period.period_end)
    out.concepts = [concept]
    out.derivation = (
        f"companyfacts {concept} @ instant {period.period_end} (undimensioned)"
    )
    if not matches:
        out.status = "error"
        out.error = (
            f"No undimensioned {concept} fact at instant {period.period_end} in companyfacts "
            f"for CIK {cik}. An ABSENT fact is never a zero and never a carry-forward -- "
            "a human must establish whether the filer changed tagging or the filing has not landed."
        )
        return
    # Prefer the entry from the most recent filing (restatements come last).
    entry = sorted(matches, key=lambda e: (e.get("filed") or "", e.get("accn") or ""))[-1]
    out.value_usd = float(entry["val"])
    out.components = [_fact_entry_note(entry, cik)]
    out.status = "extracted"


def _extract_companyfacts_duration_direct(
    client: EdgarClient, cik: str, spec: Mapping[str, Any], period: Period, out: ExtractedField
) -> None:
    concept = spec["concept"]
    selector = spec.get("context_selector", {}) or {}
    start = selector.get("start")
    end = selector.get("end")
    if not start or start.startswith("<"):
        start = period.quarter_start
    if not end or end.startswith("<"):
        end = period.period_end
    facts = client.companyfacts(cik)
    entries = companyfacts_units(facts, concept, spec.get("unit", "USD"))
    matches = pick_duration(entries, start, end)
    out.concepts = [concept]
    out.derivation = f"companyfacts {concept} for the standalone duration {start} -> {end}"
    if not matches:
        out.status = "error"
        out.error = (
            f"No {concept} fact for the exact duration {start} -> {end} in companyfacts for "
            f"CIK {cik}. Do NOT substitute the newest duration: for every filer except Amazon "
            "the newest cash-flow duration is a year-to-date figure, not a quarter (trap T8)."
        )
        return
    entry = sorted(matches, key=lambda e: (e.get("filed") or "", e.get("accn") or ""))[-1]
    out.value_usd = float(entry["val"])
    out.components = [_fact_entry_note(entry, cik)]
    out.status = "extracted"


def _ytd_value(
    client: EdgarClient, cik: str, concept: str, start: str, end: str, unit: str = "USD"
) -> tuple[float | None, dict[str, Any] | None, str]:
    entries = companyfacts_units(client.companyfacts(cik), concept, unit)
    matches = pick_duration(entries, start, end)
    if not matches:
        return None, None, (
            f"no {concept} fact for {start} -> {end}"
        )
    entry = sorted(matches, key=lambda e: (e.get("filed") or "", e.get("accn") or ""))[-1]
    return float(entry["val"]), _fact_entry_note(entry, cik), ""


def _extract_companyfacts_derived_ytd(
    client: EdgarClient, cik: str, spec: Mapping[str, Any], period: Period, out: ExtractedField
) -> None:
    """Quarter = YTD(period_end) - YTD(prior_period_end), summed over concepts.

    Skipped in fiscal Q1, where the year-to-date period IS the quarter.
    """
    concepts = list(spec.get("concepts") or ([spec["concept"]] if spec.get("concept") else []))
    fy_start = spec.get("fiscal_year_start")
    if fy_start:
        month, day = (int(x) for x in str(fy_start).split("-"))
        anchor = date.fromisoformat(period.fiscal_year_start)
        ytd_start = date(anchor.year, month, day).isoformat()
    else:
        ytd_start = period.fiscal_year_start

    out.concepts = concepts
    total = 0.0
    parts: list[str] = []
    problems: list[str] = []
    for concept in concepts:
        current, current_note, err = _ytd_value(client, cik, concept, ytd_start, period.period_end)
        if err:
            problems.append(err)
            continue
        if period.ytd_is_quarter:
            out.components.append({"concept": concept, "role": "quarter (fiscal Q1 YTD == quarter)", **(current_note or {})})
            total += float(current or 0.0)
            parts.append(f"{concept}[{ytd_start}->{period.period_end}] = {current:,.0f}")
            continue
        prior, prior_note, err2 = _ytd_value(
            client, cik, concept, ytd_start, period.prior_period_end
        )
        if err2:
            problems.append(err2)
            continue
        out.components.append({"concept": concept, "role": "YTD current", **(current_note or {})})
        out.components.append({"concept": concept, "role": "YTD prior", **(prior_note or {})})
        total += float(current) - float(prior)
        parts.append(
            f"{concept}: {current:,.0f} - {prior:,.0f} = {float(current) - float(prior):,.0f}"
        )

    if period.ytd_is_quarter:
        out.derivation = (
            f"fiscal Q1: year-to-date period {ytd_start} -> {period.period_end} IS the quarter, "
            "no differencing. " + "; ".join(parts)
        )
    else:
        out.derivation = (
            f"YTD differencing against {ytd_start} -> {period.prior_period_end}. " + "; ".join(parts)
        )

    if problems:
        out.status = "error"
        out.error = (
            "YTD differencing could not be completed: "
            + "; ".join(problems)
            + ". Refusing to emit a partial sum -- a missing component would understate the quarter."
        )
        return
    out.value_usd = total
    out.status = "extracted"


def _extract_inline_dimensional(
    client: EdgarClient,
    spec: Mapping[str, Any],
    period: Period,
    primary_doc_url: str,
    out: ExtractedField,
    doc: InlineXbrlDocument,
) -> None:
    """The case ``companyfacts`` cannot serve: a dimensioned fact.

    Selection is by axis PRESENCE plus required explicit members, never by a
    typed-member value (Amazon's moves every quarter -- trap T10).
    """
    concept = spec["concept"]
    selector = spec.get("context_selector", {}) or {}
    required_explicit = dict(selector.get("required_dimensions") or {})
    required_axes = list(selector.get("required_typed_dimensions") or [])
    forbidden = list(selector.get("forbidden_dimensions") or [])

    out.concepts = [concept]
    out.source_url = primary_doc_url
    out.source_sha256 = doc.sha256

    matches = doc.select(
        concept,
        instant=period.period_end if spec.get("period_type") == "instant" else None,
        start=None if spec.get("period_type") == "instant" else period.quarter_start,
        end=None if spec.get("period_type") == "instant" else period.period_end,
        required_explicit_dimensions=required_explicit,
        required_axes=required_axes,
        forbidden_axes=forbidden,
    )
    all_for_concept = doc.by_concept(concept)
    out.notes.append(
        f"{len(all_for_concept)} fact(s) tagged {concept} in the primary document; "
        f"{len(matches)} match the required dimensional context."
    )
    describe = []
    for f in all_for_concept:
        describe.append(
            {
                "value": f.value,
                "context_id": f.context.id,
                "instant": f.context.instant,
                "start": f.context.start,
                "end": f.context.end,
                "explicit_dimensions": dict(f.context.explicit_dimensions),
                "typed_dimensions": dict(f.context.typed_dimensions),
            }
        )
    out.components = describe

    dim_desc = ", ".join(
        [f"{a}={m}" for a, m in required_explicit.items()] + [f"{a} present" for a in required_axes]
    )
    out.derivation = (
        f"inline-XBRL {concept} @ instant {period.period_end} with dimensional context "
        f"[{dim_desc}]"
        + (f", excluding contexts carrying {', '.join(forbidden)}" if forbidden else "")
    )

    if not matches:
        out.status = "error"
        out.error = (
            f"No {concept} fact with the required dimensional context "
            f"[{dim_desc}] at {period.period_end} in {primary_doc_url}. "
            "REFUSING to fall back to the undimensioned value -- that is precisely the "
            "silent failure this pipeline exists to prevent. The filer may have renamed a "
            "company extension member; a human must re-establish the selector."
        )
        return
    if len(matches) > 1:
        distinct = {f.value for f in matches}
        if len(distinct) > 1:
            out.status = "error"
            out.error = (
                f"{len(matches)} facts match the dimensional selector with DIFFERENT values "
                f"{sorted(distinct)}. The selector is no longer unique; a human must resolve it."
            )
            return
    chosen = matches[0]
    out.value_usd = chosen.value
    out.context = chosen.context.to_dict()
    out.status = "extracted"


def _refuse_manual(spec: Mapping[str, Any], out: ExtractedField) -> None:
    """Emit a refusal that names exactly what a human must find, and where."""
    human_source = spec.get("human_source")
    if isinstance(human_source, Mapping):
        url = human_source.get("primary", "")
        what = human_source.get("what_to_read", "")
        secondary = human_source.get("secondary", "")
    else:
        url = human_source or ""
        what = ""
        secondary = ""
    out.status = "refused_manual"
    out.human_source_url = url
    parts = [
        f"HUMAN REQUIRED -- {out.label}.",
        spec.get("not_machine_readable_reason", "Not present as an XBRL fact in any SEC filing."),
    ]
    if what:
        parts.append(f"What to read: {what}")
    if spec.get("prose_location"):
        parts.append(f"Where: {spec['prose_location']}")
    if url:
        parts.append(f"Primary source: {url}")
    if secondary:
        parts.append(f"Secondary source: {secondary}")
    if spec.get("regex_trap"):
        parts.append(f"WATCH OUT: {spec['regex_trap']}")
    if spec.get("note"):
        parts.append(f"Note: {spec['note']}")
    out.human_instruction = " ".join(parts)


def _msft_capex_proxy(
    client: EdgarClient, cik: str, spec: Mapping[str, Any], period: Period
) -> dict[str, Any]:
    """Microsoft's XBRL proxy -- a SANITY CHECK, never a value.

    ``cash PP&E + finance-lease ROU asset additions``. Microsoft has never
    published a reconciliation between this and its management capex metric.
    In fiscal Q1-Q3 Microsoft tags standalone 3-month durations; in Q4 only the
    10-K annual figure exists, so each term is ``FY - 9M``.
    """
    proxy_spec = spec.get("best_xbrl_proxy") or {}
    concepts = list(proxy_spec.get("concepts") or [])
    result: dict[str, Any] = {
        "is_a_value": False,
        "status": proxy_spec.get("status", ""),
        "use_only_as": proxy_spec.get("use_only_as", ""),
        "concepts": concepts,
        "components": [],
        "value_usd": None,
        "derivation": "",
    }
    total = 0.0
    parts: list[str] = []
    for concept in concepts:
        if period.fiscal_quarter == 4:
            fy, fy_note, err = _ytd_value(
                client, cik, concept, period.fiscal_year_start, period.period_end
            )
            nine, nine_note, err2 = _ytd_value(
                client, cik, concept, period.fiscal_year_start, period.prior_period_end
            )
            if err or err2:
                result["derivation"] = f"proxy unavailable: {err or err2}"
                result["value_usd"] = None
                return result
            total += fy - nine
            parts.append(f"{concept}: {fy:,.0f} - {nine:,.0f} = {fy - nine:,.0f}")
            result["components"] += [
                {"concept": concept, "role": "FY", **(fy_note or {})},
                {"concept": concept, "role": "9M", **(nine_note or {})},
            ]
        else:
            val, note, err = _ytd_value(
                client, cik, concept, period.quarter_start, period.period_end
            )
            if err:
                result["derivation"] = f"proxy unavailable: {err}"
                result["value_usd"] = None
                return result
            total += val
            parts.append(f"{concept}[{period.quarter_start}->{period.period_end}] = {val:,.0f}")
            result["components"].append({"concept": concept, "role": "quarter", **(note or {})})
    result["value_usd"] = total
    result["derivation"] = " + ".join(parts)
    return result


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


#: Topical keywords, most specific first, used to keep a quoted snippet on
#: subject. A number alone is never enough -- "$519.5" appears in unrelated
#: tables, and quoting one of those as evidence would be worse than no quote.
_FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "demand_fact": (
        "commercial remaining performance obligation",
        "commitments not yet recognized",
        "remaining performance obligation",
        "revenue backlog",
        "performance obligation",
        "total revenue",
        "revenue",
    ),
    "capex_fact": (
        "capital expenditures, including principal payments on finance leases",
        "capital expenditures including finance leases",
        "purchases of property and equipment",
        "additions to property and equipment",
        "cash used for capital expenditures",
        "capital expenditure",
        "property and equipment",
    ),
    "annual_denominator": (
        "cash used for capital expenditures",
        "capital expenditure",
        "capex",
    ),
}


def _reads_like_prose(quote: str) -> bool:
    """Cheap discriminator between a sentence and a scraped table row."""
    if len(quote) < 40 or len(quote) > 400:
        return False
    if quote.count("$") > 3:
        return False
    digits = sum(ch.isdigit() for ch in quote)
    return digits <= len(quote) * 0.30


def _best_quote(
    value_usd: float,
    field_name: str,
    sources: Sequence[tuple[str, str]],
) -> tuple[str, str]:
    """Best verbatim snippet containing this value AND a topical keyword.

    Prose is preferred over a table fragment; among prose, the most specific
    keyword wins. Returns ``('', '')`` when nothing on-topic is found -- an
    honest blank beats a plausible-looking quote about something else.
    """
    keywords = _FIELD_KEYWORDS.get(field_name, ())
    variants = _number_variants(value_usd)
    candidates: list[tuple[int, int, int, str, str]] = []
    for rank, keyword in enumerate(keywords):
        for text, url in sources:
            if not text:
                continue
            for variant in variants:
                for shape_base, quote in (
                    (0, find_sentence(text, [variant, keyword])),
                    (2, find_fragment(text, [variant, keyword])),
                ):
                    if not quote:
                        continue
                    shape = shape_base + (0 if _reads_like_prose(quote) else 1)
                    candidates.append((shape, rank, len(quote), quote, url))
    if not candidates:
        return "", ""
    candidates.sort(key=lambda c: (c[0], c[1], c[2]))
    return candidates[0][3], candidates[0][4]


def _attach_evidence(
    out: ExtractedField,
    primary_text: str,
    primary_url: str,
    exhibit_text: str,
    exhibit_url: str,
) -> None:
    """Attach verbatim quoted snippets + URLs, mirroring the workbook cell notes.

    For a ``derived`` field the headline number does not appear anywhere in the
    filing -- only its components do -- so each component is quoted too and the
    arithmetic is carried in ``derivation``.
    """
    if out.value_usd is None:
        return
    sources = [(primary_text, primary_url), (exhibit_text, exhibit_url)]
    quote, url = _best_quote(out.value_usd, out.field, sources)
    out.evidence_quote, out.evidence_quote_source_url = quote, url

    for component in out.components:
        # Only arithmetic components get their own quote. The candidate list
        # attached to a dimensional selection includes facts we deliberately
        # REJECTED (Amazon's $38B OpenAI sibling); quoting those would mislead.
        if "role" not in component:
            continue
        val = component.get("val", component.get("value"))
        if val is None:
            continue
        c_quote, c_url = _best_quote(float(val), out.field, sources)
        if c_quote:
            component["evidence_quote"] = c_quote
            component["evidence_quote_source_url"] = c_url

    if not quote:
        if out.automation_tier == "derived":
            out.notes.append(
                "No single sentence states this derived figure -- by construction, the filer "
                "publishes only the year-to-date components. See the per-component quotes and "
                "the derivation arithmetic."
            )
        else:
            out.notes.append(
                "No corroborating prose sentence located in the primary document or the 8-K "
                "exhibit. The XBRL fact stands on its own; the reviewer must eyeball the filing."
            )


def extract_company(
    ticker: str,
    report_bucket: str,
    client: EdgarClient | None = None,
    source_map: Mapping[str, Any] | None = None,
) -> CompanyExtraction:
    """Extract all three model inputs for one company-quarter."""
    source_map = source_map or load_source_map()
    client = client or EdgarClient()
    company = source_map["companies"][ticker]
    cik = company["cik"]
    period = resolve_period(company, report_bucket, ticker)

    fetch_errors: list[str] = []
    filing: Filing | None = None
    try:
        filing = find_periodic_filing(client, cik, period.period_end, period.expected_form)
    except FetchError as exc:
        fetch_errors.append(f"submissions index: {exc}")

    primary_url = filing.primary_doc_url if filing else ""
    if not filing:
        recorded = company.get("latest_filing", {})
        if recorded.get("period_end") == period.period_end:
            primary_url = recorded.get("primary_doc_url", "")
            fetch_errors.append(
                "No 10-Q/10-K with this reportDate found in the submissions index; falling back "
                "to the primary document URL recorded in source_map.json for this same period end."
            )
        else:
            fetch_errors.append(
                f"No 10-Q/10-K with reportDate {period.period_end} has been filed yet for {ticker}. "
                "The refresh for this company is not ready."
            )

    doc: InlineXbrlDocument | None = None
    primary_text = ""
    if primary_url:
        try:
            response = client.get(primary_url)
            doc = client.inline_xbrl(primary_url)
            primary_text = visible_text(response.text)
        except FetchError as exc:
            fetch_errors.append(f"primary document {primary_url}: {exc}")

    eight_k: Filing | None = None
    exhibit_url = ""
    exhibit_text = ""
    try:
        eight_k = find_earnings_8k(client, cik, period.period_end)
        if eight_k:
            exhibit_url = find_exhibit_991(client, eight_k)
    except FetchError as exc:
        fetch_errors.append(f"earnings 8-K lookup: {exc}")
    if exhibit_url:
        try:
            exhibit_text = visible_text(client.get(exhibit_url).text)
        except FetchError as exc:
            fetch_errors.append(f"8-K exhibit {exhibit_url}: {exc}")

    fields: dict[str, ExtractedField] = {}
    for field_name in FIELDS:
        spec = company.get(field_name)
        if not spec:
            continue
        out = ExtractedField(
            ticker=ticker,
            field=field_name,
            label=spec.get("label", field_name),
            automation_tier=spec.get("automation_tier", "manual"),
            access=spec.get("access", "not_in_xbrl"),
            status="error",
            model_q2_2026=spec.get("model_q2_2026", spec.get("model_value")),
            source_url=primary_url,
            source_sha256=doc.sha256 if doc else "",
        )
        try:
            if out.automation_tier == "manual" or out.access == "not_in_xbrl":
                _refuse_manual(spec, out)
                if field_name == "capex_fact" and spec.get("best_xbrl_proxy"):
                    out.proxy_only = _msft_capex_proxy(client, cik, spec, period)
            elif out.access == "inline_xbrl_dimensional":
                if doc is None:
                    out.status = "error"
                    out.error = (
                        "This fact is only reachable by parsing the filing's inline XBRL, and the "
                        "primary document could not be fetched. companyfacts is NOT an acceptable "
                        "substitute here."
                    )
                else:
                    _extract_inline_dimensional(client, spec, period, primary_url, out, doc)
            elif out.automation_tier == "derived":
                _extract_companyfacts_derived_ytd(client, cik, spec, period, out)
            elif spec.get("period_type") == "instant":
                _extract_companyfacts_instant(client, cik, spec, period, out)
            else:
                _extract_companyfacts_duration_direct(client, cik, spec, period, out)
        except FetchError as exc:
            out.status = "error"
            out.error = f"fetch failed: {exc}"
        except Exception as exc:  # noqa: BLE001 - surfaced, never silently swallowed
            out.status = "error"
            out.error = f"{type(exc).__name__}: {exc}"

        _attach_evidence(out, primary_text, primary_url, exhibit_text, exhibit_url)
        if not out.source_url:
            out.source_url = primary_url
        for key in ("precision_note", "definition_break", "corroborating_prose"):
            if spec.get(key):
                out.notes.append(f"{key}: {spec[key]}")
        fields[field_name] = out

    return CompanyExtraction(
        ticker=ticker,
        company_name=company["name"],
        cik=cik,
        report_bucket=report_bucket,
        period=period,
        periodic_filing=filing.to_dict() if filing else None,
        earnings_8k=eight_k.to_dict() if eight_k else None,
        exhibit_991_url=exhibit_url,
        fields=fields,
        fetch_errors=fetch_errors,
        _primary_text=primary_text,
        _exhibit_text=exhibit_text,
        _ixbrl=doc,
    )


def extract_all(
    report_bucket: str,
    client: EdgarClient | None = None,
    source_map: Mapping[str, Any] | None = None,
    tickers: Iterable[str] = TICKERS,
) -> dict[str, CompanyExtraction]:
    """Extract every company for one bucket."""
    source_map = source_map or load_source_map()
    client = client or EdgarClient()
    return {
        t: extract_company(t, report_bucket, client=client, source_map=source_map)
        for t in tickers
    }


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    sys.stdout.reconfigure(encoding="utf-8")
    bucket = argv[0] if argv else "CY2026Q2"
    tickers = argv[1:] or list(TICKERS)
    results = extract_all(bucket, tickers=tickers)
    for ticker, extraction in results.items():
        print(f"\n=== {ticker} {bucket} ({extraction.period.fiscal_period}, end {extraction.period.period_end}) ===")
        for name, f in extraction.fields.items():
            if f.status == "extracted":
                print(f"  {name:20s} {f.value_usd_b:>12,.3f} $B  [{f.automation_tier}/{f.access}]")
            elif f.status == "refused_manual":
                print(f"  {name:20s} {'REFUSED':>12s}      [manual] {f.human_instruction[:90]}...")
            else:
                print(f"  {name:20s} {'ERROR':>12s}      {f.error[:110]}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
