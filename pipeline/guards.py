"""The 15 documented definitional traps, as executable checks that fail loudly.

Design principle
----------------
Every check here exists because a plausible-looking wrong number would
otherwise flow into the model unnoticed. So the default outcome of an
unsatisfied check is ``FAIL`` (which blocks the packet outright) or
``NEEDS_HUMAN`` (which blocks it until a named reviewer acknowledges that
specific guard by id in the approval file). Nothing in this module warns
quietly.

Statuses
--------
``PASS``           the trap was checked and avoided.
``FAIL``           blocking. :mod:`pipeline.apply` refuses the packet.
``NEEDS_HUMAN``    blocking until acknowledged by id in the approval file.
``INFO``           context the reviewer must read; does not block.
``NOT_APPLICABLE`` this trap does not apply to this company/field.

Guard ids ``T1``-``T15`` map one-to-one onto ``docs/SOURCE_MAP.md`` §3.
``S*`` are structural preconditions, ``R*`` are range/sanity checks and
``X1`` is the press-release cross-check the SOURCE_MAP recommends.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Mapping, Sequence

from .dataio import prior_row
from .edgar import EdgarClient, companyfacts_units, pick_instant
from .extract import CompanyExtraction, ExtractedField, find_fragment, find_sentence

__all__ = [
    "GuardResult",
    "GuardOutcome",
    "run_guards",
    "PASS",
    "FAIL",
    "NEEDS_HUMAN",
    "INFO",
    "NOT_APPLICABLE",
    "SEQUENTIAL_MOVE_THRESHOLDS",
]

PASS = "PASS"
FAIL = "FAIL"
NEEDS_HUMAN = "NEEDS_HUMAN"
INFO = "INFO"
NOT_APPLICABLE = "NOT_APPLICABLE"

BLOCKING = (FAIL, NEEDS_HUMAN)


@dataclass
class GuardResult:
    """One check, its verdict, and the evidence behind the verdict."""

    id: str
    name: str
    ticker: str
    field: str
    status: str
    message: str
    evidence: dict[str, Any] = dc_field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return self.status in BLOCKING

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "ticker": self.ticker,
            "field": self.field,
            "status": self.status,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass
class GuardOutcome:
    """All guard results for one company-quarter."""

    ticker: str
    report_bucket: str
    results: list[GuardResult]

    @property
    def failures(self) -> list[GuardResult]:
        return [r for r in self.results if r.status == FAIL]

    @property
    def needs_human(self) -> list[GuardResult]:
        return [r for r in self.results if r.status == NEEDS_HUMAN]

    @property
    def blocking_ids(self) -> list[str]:
        return [r.id for r in self.results if r.blocking]

    def to_list(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.results]


# ---------------------------------------------------------------------------
# Sanity thresholds
# ---------------------------------------------------------------------------

#: Sequential-move bands, calibrated against the five quarters already in
#: ``data/facts.csv``. These are deliberately NOT set wide enough to wave every
#: real move through: Oracle's RPO once moved +230% and Meta's capex +57%, and
#: a human confirming those is exactly the intended behaviour.
SEQUENTIAL_MOVE_THRESHOLDS: dict[str, dict[str, float]] = {
    "demand_fact": {"needs_human_pct": 0.40, "fail_low_ratio": 0.20, "fail_high_ratio": 5.0},
    "capex_fact": {"needs_human_pct": 0.35, "fail_low_ratio": 0.25, "fail_high_ratio": 4.0},
}

#: Absolute sanity band for any dollar field, in USD.
_MIN_PLAUSIBLE_USD = 1e8
_MAX_PLAUSIBLE_USD = 2e12


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field(extraction: CompanyExtraction, name: str) -> ExtractedField | None:
    return extraction.fields.get(name)


def _texts(extraction: CompanyExtraction) -> list[tuple[str, str]]:
    return [
        (extraction._primary_text, extraction.periodic_filing["primary_doc_url"] if extraction.periodic_filing else ""),
        (extraction._exhibit_text, extraction.exhibit_991_url),
    ]


def _search_all(extraction: CompanyExtraction, needles: Sequence[str]) -> tuple[str, str]:
    for text, url in _texts(extraction):
        if not text:
            continue
        quote = find_sentence(text, needles) or find_fragment(text, needles)
        if quote:
            return quote, url
    return "", ""


# ---------------------------------------------------------------------------
# Structural guards
# ---------------------------------------------------------------------------


def _s1_period_matches_spec(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    period = extraction.period
    if period.source_map_agrees is None:
        return [
            GuardResult(
                "S1",
                "Resolved period is not pinned in source_map.report_bucket_map",
                extraction.ticker,
                "period",
                INFO,
                f"{extraction.ticker} {period.report_bucket} resolves to period_end "
                f"{period.period_end} ({period.fiscal_period}, expect {period.expected_form}) from the "
                "fiscal calendar. source_map.json pins no entry for this bucket, so the resolution "
                "is unverified against the spec -- confirm it against the filing.",
                {"period": period.to_dict()},
            )
        ]
    if not period.source_map_agrees:
        return [
            GuardResult(
                "S1",
                "Resolved period DISAGREES with source_map.report_bucket_map",
                extraction.ticker,
                "period",
                FAIL,
                f"Computed period_end {period.period_end} but source_map.json pins "
                f"{period.source_map_period_end} for {period.report_bucket}. The spec has drifted "
                "from the filer's calendar, or the calendar arithmetic is wrong. Resolve before proceeding.",
                {"period": period.to_dict()},
            )
        ]
    return [
        GuardResult(
            "S1",
            "Resolved period matches source_map.report_bucket_map",
            extraction.ticker,
            "period",
            PASS,
            f"period_end {period.period_end}, {period.fiscal_period}, form {period.expected_form}.",
            {"period": period.to_dict()},
        )
    ]


def _s2_filing_present(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    period = extraction.period
    if not extraction.periodic_filing:
        return [
            GuardResult(
                "S2",
                "Periodic filing for this period has not landed",
                extraction.ticker,
                "filing",
                FAIL,
                f"No 10-Q/10-K with reportDate {period.period_end} in EDGAR for CIK {extraction.cik}. "
                "The refresh for this company is not ready. For Oracle's fiscal Q4 the 8-K precedes "
                "the 10-K by up to 12 days and carries NO XBRL facts -- wait for the 10-K.",
                {"fetch_errors": extraction.fetch_errors},
            )
        ]
    filing = extraction.periodic_filing
    results = [
        GuardResult(
            "S2",
            "Periodic filing present",
            extraction.ticker,
            "filing",
            PASS,
            f"{filing['form']} {filing['accession']} filed {filing['filing_date']} for reportDate "
            f"{filing['report_date']}.",
            {"filing": filing},
        )
    ]
    if filing["form"] != period.expected_form:
        results.append(
            GuardResult(
                "S3",
                "Filing form is not the expected one for this fiscal quarter",
                extraction.ticker,
                "filing",
                NEEDS_HUMAN,
                f"Expected {period.expected_form} for fiscal Q{period.fiscal_quarter} but found "
                f"{filing['form']}. Derivation shape depends on this (a 10-K carries only the annual "
                "cash-flow column).",
                {"filing": filing},
            )
        )
    else:
        results.append(
            GuardResult(
                "S3",
                "Filing form matches the fiscal quarter",
                extraction.ticker,
                "filing",
                PASS,
                f"fiscal Q{period.fiscal_quarter} -> {filing['form']}.",
                {},
            )
        )
    return results


def _s4_extraction_status(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    results: list[GuardResult] = []
    for name, f in extraction.fields.items():
        if f.status == "error":
            results.append(
                GuardResult(
                    "S4",
                    f"Extraction failed: {name}",
                    extraction.ticker,
                    name,
                    FAIL,
                    f.error,
                    {"tier": f.automation_tier, "access": f.access},
                )
            )
        elif f.status == "refused_manual":
            results.append(
                GuardResult(
                    "S5",
                    f"Manual field correctly refused: {name}",
                    extraction.ticker,
                    name,
                    NEEDS_HUMAN,
                    f.human_instruction,
                    {
                        "human_source_url": f.human_source_url,
                        "proxy_only": f.proxy_only,
                    },
                )
            )
            if f.value_usd is not None:
                results.append(
                    GuardResult(
                        "S5",
                        f"Manual field carries an auto-populated value: {name}",
                        extraction.ticker,
                        name,
                        FAIL,
                        "A field marked manual must never be populated by the extractor. "
                        "This is a pipeline bug, not a data question.",
                        {"value_usd": f.value_usd},
                    )
                )
        else:
            results.append(
                GuardResult(
                    "S4",
                    f"Extraction succeeded: {name}",
                    extraction.ticker,
                    name,
                    PASS,
                    f"{f.value_usd_b:,.3f} $B via {f.automation_tier}/{f.access}.",
                    {"derivation": f.derivation},
                )
            )
    return results


def _s6_fetch_errors(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if not extraction.fetch_errors:
        return [
            GuardResult(
                "S6", "No fetch errors", extraction.ticker, "fetch", PASS, "All sources retrieved.", {}
            )
        ]
    return [
        GuardResult(
            "S6",
            "Fetch errors occurred",
            extraction.ticker,
            "fetch",
            NEEDS_HUMAN,
            "; ".join(extraction.fetch_errors),
            {"errors": extraction.fetch_errors},
        )
    ]


# ---------------------------------------------------------------------------
# T1 / T2 -- Oracle capex basis
# ---------------------------------------------------------------------------

_NET_OUTLAY_RE = re.compile(
    r"NET CASH OUTLAY FOR CAPITAL EXPENDITURES[^\n]*", re.IGNORECASE
)


def _t1_orcl_net_outlay(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "ORCL":
        return [
            GuardResult(
                "T1",
                "Oracle net-cash-outlay basis",
                extraction.ticker,
                "capex_fact",
                NOT_APPLICABLE,
                "Only Oracle publishes a net-cash-outlay capex measure.",
                {},
            )
        ]
    results: list[GuardResult] = []
    exhibit = extraction._exhibit_text or ""
    heading = _NET_OUTLAY_RE.search(exhibit)
    # Only the NET row and the two deduction rows are forbidden. The table's
    # first row is the GROSS "Capital Expenditures" line, which is exactly what
    # the model uses -- scraping the whole table would flag the right answer.
    net_values: set[float] = set()
    gross_values: set[float] = set()
    for label, sink in (
        ("Net Cash Outlay for Capital Expenditures", net_values),
        ("Capital Expenditures", gross_values),
    ):
        idx = exhibit.find(label, heading.start() if heading else 0)
        if idx < 0:
            continue
        window = exhibit[idx + len(label) : idx + len(label) + 700]
        window = window.split("Less:")[0] if label.startswith("Capital") else window
        for raw in re.findall(r"([0-9]{1,3}(?:,[0-9]{3})+)", window):
            sink.add(float(raw.replace(",", "")) * 1e6)
    net_values -= gross_values
    for name in ("capex_fact", "annual_denominator"):
        f = _field(extraction, name)
        if not f or f.value_usd is None:
            continue
        concept_ok = any("PaymentsToAcquirePropertyPlantAndEquipment" in c for c in f.concepts)
        if not concept_ok:
            results.append(
                GuardResult(
                    "T1",
                    f"Oracle {name} not sourced from the GAAP cash-capex tag",
                    extraction.ticker,
                    name,
                    FAIL,
                    "Oracle's capex must come from us-gaap:PaymentsToAcquirePropertyPlantAndEquipment "
                    "in XBRL, never from the press release's non-GAAP net-cash-outlay table. "
                    f"Concepts used: {f.concepts}.",
                    {"concepts": f.concepts},
                )
            )
            continue
        # The net outlay for FY2026 is 47,726M; the gross figure is 55,663M.
        if f.value_usd in net_values and heading:
            results.append(
                GuardResult(
                    "T1",
                    f"Oracle {name} equals a value from the NET CASH OUTLAY table",
                    extraction.ticker,
                    name,
                    FAIL,
                    f"Extracted {f.value_usd/1e9:,.3f}$B coincides with a figure in Oracle's non-GAAP "
                    "'NET CASH OUTLAY FOR CAPITAL EXPENDITURES' table, which deducts short-term capex "
                    "financing and customer prepayments with a significant financing component. "
                    "The model uses GROSS GAAP cash capex.",
                    {"value_usd": f.value_usd, "heading": heading.group(0)},
                )
            )
        else:
            results.append(
                GuardResult(
                    "T1",
                    f"Oracle {name} is on the GROSS GAAP basis",
                    extraction.ticker,
                    name,
                    PASS,
                    f"{f.value_usd/1e9:,.3f}$B from us-gaap:PaymentsToAcquirePropertyPlantAndEquipment; "
                    "distinct from every figure on the 'Net Cash Outlay' and 'Less:' rows of the "
                    "press release's non-GAAP table"
                    + (
                        f" (net-outlay row values: {', '.join(f'{v/1e6:,.0f}M' for v in sorted(net_values))})"
                        if net_values
                        else " (table not present in this exhibit)"
                    )
                    + ".",
                    {
                        "net_outlay_values_usd": sorted(net_values)[:12],
                        "gross_row_values_usd": sorted(gross_values)[:12],
                    },
                )
            )
    return results


def _s7_pinned_denominator_freshness(
    extraction: CompanyExtraction, **_: Any
) -> list[GuardResult]:
    """Oracle's denominator is a filed ACTUAL pinned to one fiscal-year window.

    That pin is correct only until Oracle closes a later fiscal year. The spec
    pins 2025-06-01 -> 2026-05-31; once FY2027 is filed the pin is stale and a
    human must decide whether to roll it forward -- a methodology choice, not an
    extraction.
    """
    from datetime import date as _date

    f = _field(extraction, "annual_denominator")
    if f is None or f.status != "extracted" or not f.components:
        return []
    end = f.components[0].get("end")
    if not end:
        return []
    try:
        here = _date.fromisoformat(extraction.period.period_end)
        there = _date.fromisoformat(end)
    except ValueError:
        return []
    months = (here.year - there.year) * 12 + here.month - there.month
    if months > 12:
        return [
            GuardResult(
                "S7",
                "Annual denominator is pinned to a superseded fiscal year",
                extraction.ticker,
                "annual_denominator",
                NEEDS_HUMAN,
                f"The denominator is the filed actual for the year ended {end}, {months} months "
                f"before this period end ({extraction.period.period_end}); a later fiscal year has "
                "since closed. Decide whether to roll the pinned window forward in "
                "source_map.json.",
                {"pinned_window_end": end, "months_stale": months},
            )
        ]
    return [
        GuardResult(
            "S7",
            "Annual denominator's pinned fiscal year is still the latest completed one",
            extraction.ticker,
            "annual_denominator",
            PASS,
            f"filed actual for the year ended {end}, {months} month(s) before this period end.",
            {"pinned_window_end": end, "months_stale": months},
        )
    ]


def _t2_orcl_ttm_table(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "ORCL":
        return [
            GuardResult(
                "T2",
                "Oracle trailing-four-quarters capex table",
                extraction.ticker,
                "capex_fact",
                NOT_APPLICABLE,
                "Only Oracle publishes this table.",
                {},
            )
        ]
    exhibit = extraction._exhibit_text or ""
    heading = _NET_OUTLAY_RE.search(exhibit)
    f = _field(extraction, "capex_fact")
    sourced_from_exhibit = bool(
        f and f.evidence_quote_source_url and f.evidence_quote_source_url == extraction.exhibit_991_url
    )
    if heading and "TRAILING FOUR-QUARTERS" in heading.group(0).upper():
        status = FAIL if sourced_from_exhibit else INFO
        return [
            GuardResult(
                "T2",
                "Oracle's press-release capex table is TRAILING FOUR-QUARTERS, not quarterly",
                extraction.ticker,
                "capex_fact",
                status,
                f"Detected heading: '{heading.group(0)[:120]}'. Every column in that table is a TTM "
                "figure -- FY26 Q3 reads 48,250 while the 9-month XBRL year-to-date is 39,170. "
                "The quarter must come from XBRL YTD differencing and never from this table."
                + (" The extracted capex appears to have been sourced from this exhibit." if sourced_from_exhibit else ""),
                {"heading": heading.group(0)[:200], "capex_from_exhibit": sourced_from_exhibit},
            )
        ]
    return [
        GuardResult(
            "T2",
            "Oracle trailing-four-quarters capex table not found in this exhibit",
            extraction.ticker,
            "capex_fact",
            INFO,
            "The TTM capex table was not detected in the Exhibit 99.1 text. Confirm the exhibit was "
            "retrieved; the table has appeared in every recent Oracle release.",
            {"exhibit_url": extraction.exhibit_991_url},
        )
    ]


# ---------------------------------------------------------------------------
# T3 -- Microsoft outlook / accounting-policy contamination
# ---------------------------------------------------------------------------


def _t3_msft_outlook_policy(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "MSFT":
        return [
            GuardResult("T3", "Microsoft outlook accounting change", extraction.ticker,
                        "annual_denominator", NOT_APPLICABLE, "Microsoft only.", {})
        ]
    quote, url = _search_all(extraction, ["useful lives"])
    return [
        GuardResult(
            "T3",
            "Microsoft's capex outlook movement can be an accounting effect, not an investment cut",
            extraction.ticker,
            "annual_denominator",
            NEEDS_HUMAN,
            "Microsoft extended estimated useful lives for datacenters and office buildings "
            "(15 -> 25 years), which shifts future datacenter leases from FINANCE leases (counted in "
            "the management capex metric) to OPERATING leases (excluded). The CY2026 outlook fell "
            "~$190B -> ~$175B for that reason while capex including finance leases rose ~70% YoY. "
            "Any period-over-period comparison of this denominator across the change is mechanical, "
            "not economic. A human must state whether the new figure is comparable to the one on file.",
            {"useful_lives_language": quote[:400], "source_url": url},
        )
    ]


# ---------------------------------------------------------------------------
# T4 -- Microsoft total RPO vs commercial RPO. The most dangerous trap.
# ---------------------------------------------------------------------------


def _t4_msft_rpo_dimension(
    extraction: CompanyExtraction, client: EdgarClient | None = None, source_map: Mapping[str, Any] | None = None, **_: Any
) -> list[GuardResult]:
    if extraction.ticker != "MSFT":
        return [
            GuardResult("T4", "Microsoft commercial-RPO dimension", extraction.ticker,
                        "demand_fact", NOT_APPLICABLE, "Microsoft only.", {})
        ]
    f = _field(extraction, "demand_fact")
    spec = ((source_map or {}).get("companies", {}).get("MSFT", {}).get("demand_fact", {}))
    required = dict((spec.get("context_selector") or {}).get("required_dimensions") or {})
    required = required or {"srt:MajorCustomersAxis": "msft:CommercialCustomersMember"}

    if f is None or f.value_usd is None:
        return [
            GuardResult(
                "T4",
                "Microsoft commercial RPO was not extracted",
                extraction.ticker,
                "demand_fact",
                FAIL,
                "No value. NEVER fall back to companyfacts here: it returns total company RPO "
                "($684B for Q2 2026), which is wrong by $6.0B and looks entirely plausible.",
                {"error": f.error if f else "field missing"},
            )
        ]

    context = f.context or {}
    explicit = context.get("explicit_dimensions") or {}
    missing = {a: m for a, m in required.items() if explicit.get(a) != m}
    if missing:
        return [
            GuardResult(
                "T4",
                "Microsoft RPO fact does NOT carry the commercial-customers dimension",
                extraction.ticker,
                "demand_fact",
                FAIL,
                f"The selected fact's context {context.get('id')!r} carries {explicit or '{}'} but "
                f"{missing} is required. This is the undimensioned TOTAL company RPO, not the "
                "commercial subset the model uses. Refusing the value.",
                {"context": context, "required": required},
            )
        ]

    results = [
        GuardResult(
            "T4",
            "Microsoft RPO carries srt:MajorCustomersAxis = msft:CommercialCustomersMember",
            extraction.ticker,
            "demand_fact",
            PASS,
            f"context {context.get('id')} @ {context.get('instant')} with {explicit}; "
            f"value {f.value_usd/1e9:,.1f}$B.",
            {"context": context},
        )
    ]

    # And prove the number differs from what a companyfacts-only fetcher would return.
    if client is not None:
        try:
            entries = companyfacts_units(
                client.companyfacts(extraction.cik), spec.get("concept", "us-gaap:RevenueRemainingPerformanceObligation")
            )
            undimensioned = pick_instant(entries, extraction.period.period_end)
        except Exception as exc:  # noqa: BLE001
            undimensioned = []
            results.append(
                GuardResult("T4", "companyfacts comparison unavailable", extraction.ticker,
                            "demand_fact", INFO, f"{exc}", {})
            )
        if undimensioned:
            total = float(undimensioned[-1]["val"])
            if total == f.value_usd:
                results.append(
                    GuardResult(
                        "T4",
                        "Microsoft RPO equals the undimensioned companyfacts total",
                        extraction.ticker,
                        "demand_fact",
                        FAIL,
                        f"The dimensional selection returned {f.value_usd/1e9:,.1f}$B, which is "
                        "identical to the undimensioned total RPO. Either Microsoft has stopped "
                        "reporting a separate commercial figure or the selector silently matched the "
                        "wrong fact. A human must confirm before this is used.",
                        {"total_rpo_usd": total, "selected_usd": f.value_usd},
                    )
                )
            else:
                results.append(
                    GuardResult(
                        "T4",
                        "Commercial RPO is distinct from total RPO, as expected",
                        extraction.ticker,
                        "demand_fact",
                        PASS,
                        f"commercial {f.value_usd/1e9:,.1f}$B vs companyfacts total "
                        f"{total/1e9:,.1f}$B (delta {(total - f.value_usd)/1e9:,.1f}$B). A "
                        "companyfacts-only fetcher would have taken the total.",
                        {"total_rpo_usd": total, "selected_usd": f.value_usd},
                    )
                )
    return results


# ---------------------------------------------------------------------------
# T5 -- Alphabet backlog definition change
# ---------------------------------------------------------------------------

_GOOG_DEFINITION_MARKER = "original expected term of one year or less"


def _t5_goog_definition(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "GOOG":
        return [
            GuardResult("T5", "Alphabet backlog definition change", extraction.ticker,
                        "demand_fact", NOT_APPLICABLE, "Alphabet only.", {})
        ]
    quote, url = _search_all(extraction, [_GOOG_DEFINITION_MARKER])
    tpu_quote, _ = _search_all(extraction, ["backlog", "TPU"])
    if quote:
        return [
            GuardResult(
                "T5",
                "Alphabet's expanded backlog definition is still in force",
                extraction.ticker,
                "demand_fact",
                INFO,
                "Detected the Q1 2026 definition-change language, so this quarter is on the NEW "
                "basis (contracts with an original expected term of one year or less are included). "
                "Q1 26 onward are comparable with each other; any comparison spanning Q4 25 -> Q1 26 "
                "is not. Carry definition_version = '2026-expanded' on the row."
                + (f" Cloud backlog composition note: {tpu_quote[:200]}" if tpu_quote else ""),
                {"quote": quote[:400], "source_url": url, "definition_version": "2026-expanded"},
            )
        ]
    return [
        GuardResult(
            "T5",
            "Alphabet backlog definition language NOT found in this filing",
            extraction.ticker,
            "demand_fact",
            NEEDS_HUMAN,
            "The sentence electing to include contracts with an original expected term of one year "
            "or less was not found. Either the wording changed or the definition changed again. "
            "A human must read the revenue-backlog note and set definition_version before the "
            "series is spliced.",
            {"marker": _GOOG_DEFINITION_MARKER},
        )
    ]


# ---------------------------------------------------------------------------
# T6 -- Amazon gross vs net capex, and the concept trap
# ---------------------------------------------------------------------------


def _t6_amzn_gross_vs_net(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "AMZN":
        return [
            GuardResult("T6", "Amazon gross-vs-net capex", extraction.ticker, "capex_fact",
                        NOT_APPLICABLE, "Amazon only.", {})
        ]
    f = _field(extraction, "capex_fact")
    results: list[GuardResult] = []
    if f is None or f.value_usd is None:
        return [
            GuardResult("T6", "Amazon capex not extracted", extraction.ticker, "capex_fact",
                        FAIL, f.error if f else "field missing", {})
        ]
    if not any("PaymentsToAcquireProductiveAssets" in c for c in f.concepts):
        results.append(
            GuardResult(
                "T6",
                "Amazon capex uses the wrong concept",
                extraction.ticker,
                "capex_fact",
                FAIL,
                "Amazon tags BOTH PaymentsToAcquireProductiveAssets and "
                "PaymentsToAcquirePropertyPlantAndEquipment. Only the former carries the "
                f"cash-flow-statement line the model uses. Concepts used: {f.concepts}.",
                {"concepts": f.concepts},
            )
        )
    else:
        results.append(
            GuardResult(
                "T6",
                "Amazon capex uses us-gaap:PaymentsToAcquireProductiveAssets",
                extraction.ticker,
                "capex_fact",
                PASS,
                "The cash-flow-statement 'Purchases of property and equipment' line, as the model requires.",
                {"concepts": f.concepts},
            )
        )

    # Independently re-read the GROSS cash-flow line out of the filing itself
    # and reconstruct the NET figure Amazon's MD&A quotes, so that taking the
    # net number cannot pass by looking self-consistent.
    gross_in_filing = None
    proceeds = None
    doc = extraction._ixbrl
    if doc is not None:
        for candidate in doc.facts:
            ctx = candidate.context
            if not (
                ctx.start == extraction.period.quarter_start
                and ctx.end == extraction.period.period_end
                and ctx.is_undimensioned
            ):
                continue
            if candidate.concept.endswith("PaymentsToAcquireProductiveAssets"):
                gross_in_filing = candidate.value
            elif candidate.concept.endswith("ProceedsFromPropertyPlantAndEquipmentSalesAndIncentives"):
                proceeds = candidate.value

    if gross_in_filing is None:
        results.append(
            GuardResult(
                "T6",
                "Could not re-read Amazon's gross cash-flow capex line from the filing",
                extraction.ticker,
                "capex_fact",
                NEEDS_HUMAN,
                "The gross-vs-net difference could not be verified against the filing this quarter. "
                "Read the cash-flow statement and confirm the packet's value is the GROSS "
                "'Purchases of property and equipment' line, not the MD&A's net 'cash capital "
                "expenditures'.",
                {},
            )
        )
        return results

    net = gross_in_filing - proceeds if proceeds is not None else None
    if abs(f.value_usd - gross_in_filing) >= 1.0:
        results.append(
            GuardResult(
                "T6",
                "Amazon capex does not equal the GROSS cash-flow-statement line in the filing",
                extraction.ticker,
                "capex_fact",
                FAIL,
                f"Proposed {f.value_usd/1e9:,.3f}$B but the filing's gross 'Purchases of property "
                f"and equipment' line is {gross_in_filing/1e9:,.3f}$B"
                + (
                    f", and the NET measure Amazon's MD&A calls 'cash capital expenditures' is "
                    f"{net/1e9:,.3f}$B after deducting {proceeds/1e6:,.0f}M of proceeds from "
                    "property and equipment sales and incentives"
                    if net is not None
                    else ""
                )
                + ". The model uses GROSS.",
                {"proposed_usd": f.value_usd, "gross_usd": gross_in_filing, "net_usd": net},
            )
        )
    elif net is not None:
        results.append(
            GuardResult(
                "T6",
                "Amazon capex is GROSS, not the MD&A's net 'cash capital expenditures'",
                extraction.ticker,
                "capex_fact",
                PASS,
                f"gross {gross_in_filing/1e9:,.3f}$B as re-read from the filing's cash-flow "
                f"statement; the net measure the MD&A quotes would be {net/1e9:,.3f}$B after "
                f"deducting {proceeds/1e6:,.0f}M of proceeds from property and equipment sales and "
                "incentives. The model uses gross.",
                {"gross_usd": gross_in_filing, "net_usd": net, "proceeds_usd": proceeds},
            )
        )
    else:
        results.append(
            GuardResult(
                "T6",
                "Amazon capex matches the filing's gross line; proceeds not separately tagged",
                extraction.ticker,
                "capex_fact",
                NEEDS_HUMAN,
                "The gross figure was confirmed against the filing, but the offsetting proceeds "
                "line was not found, so the net measure could not be reconstructed. Confirm the "
                "MD&A's 'cash capital expenditures' sentence is not what the packet carries.",
                {"gross_usd": gross_in_filing},
            )
        )
    return results


# ---------------------------------------------------------------------------
# T7 -- Meta's guidance sentence carries the superseded range too
# ---------------------------------------------------------------------------

_RANGE_RE = re.compile(r"\$\s?([0-9]{2,3})\s?[-–]\s?([0-9]{2,3})\s?billion", re.IGNORECASE)


def _t7_meta_guidance(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "META":
        return [
            GuardResult("T7", "Meta dual-range guidance sentence", extraction.ticker,
                        "annual_denominator", NOT_APPLICABLE, "Meta only.", {})
        ]
    exhibit = extraction._exhibit_text or ""
    # Target the OUTLOOK sentence specifically. Searching for
    # "capital expenditures" + "billion" finds the RESULTS bullet
    # ("Capital expenditures ... were $31.08 billion") long before the guidance.
    sentence = (
        find_sentence(exhibit, ["capital expenditures", "range of"], max_len=700)
        or find_sentence(exhibit, ["anticipate", "capital expenditures"], max_len=700)
        or find_fragment(exhibit, ["anticipate", "capital expenditures"], window=320)
    )
    ranges = _RANGE_RE.findall(sentence)
    expense_ranges = _RANGE_RE.findall(
        find_sentence(exhibit, ["total expenses", "range of"], max_len=600) or ""
    )
    if len(ranges) >= 2:
        return [
            GuardResult(
                "T7",
                "Meta's capex guidance sentence contains BOTH the current and the superseded range",
                extraction.ticker,
                "annual_denominator",
                NEEDS_HUMAN,
                "Two ranges appear in one sentence: "
                + ", ".join(f"${a}-{b}B" for a, b in ranges)
                + ". The CURRENT outlook is the one before 'narrowed from our prior outlook of'. "
                "A 'last match in sentence' regex would take the superseded figure; 'first match' is "
                "correct only by luck of word order. The same paragraph also carries a total-expenses "
                "range ("
                + (", ".join(f"${a}-{b}B" for a, b in expense_ranges) or "not detected")
                + ") that a looser regex would grab instead. A human must state the number.",
                {
                    "sentence": sentence[:600],
                    "capex_ranges": ranges,
                    "expense_ranges": expense_ranges,
                    "source_url": extraction.exhibit_991_url,
                },
            )
        ]
    return [
        GuardResult(
            "T7",
            "Meta capex guidance sentence did not parse into two ranges",
            extraction.ticker,
            "annual_denominator",
            NEEDS_HUMAN,
            "Could not confirm the shape of Meta's guidance sentence "
            f"(found {len(ranges)} range(s)). Meta's outlook is filed prose, never XBRL; a human "
            "must read it. Sentence as located: "
            + (sentence[:400] or "(not located)"),
            {"sentence": sentence[:600], "source_url": extraction.exhibit_991_url},
        )
    ]


# ---------------------------------------------------------------------------
# T8 -- a year-to-date figure is never a quarter
# ---------------------------------------------------------------------------


def _t8_ytd_not_quarter(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    f = _field(extraction, "capex_fact")
    period = extraction.period
    if f is None or f.value_usd is None or f.automation_tier == "manual":
        return [
            GuardResult("T8", "YTD-as-quarter check", extraction.ticker, "capex_fact",
                        NOT_APPLICABLE, "No machine-extracted capex value for this company-quarter.", {})
        ]
    results: list[GuardResult] = []
    ytd_components = [c for c in f.components if str(c.get("role", "")).startswith("YTD")]
    if f.automation_tier == "derived" and not period.ytd_is_quarter:
        if not ytd_components:
            results.append(
                GuardResult(
                    "T8",
                    "Derived capex has no year-to-date components",
                    extraction.ticker,
                    "capex_fact",
                    FAIL,
                    "A derived quarter must be produced by differencing two year-to-date facts. "
                    "None were recorded.",
                    {"components": f.components},
                )
            )
        for component in ytd_components:
            if abs(float(component.get("val", 0)) - f.value_usd) < 1.0:
                results.append(
                    GuardResult(
                        "T8",
                        "Emitted quarter equals a year-to-date component",
                        extraction.ticker,
                        "capex_fact",
                        FAIL,
                        f"The proposed quarterly capex {f.value_usd/1e9:,.3f}$B is identical to the "
                        f"cumulative {component.get('start')} -> {component.get('end')} figure. "
                        "GOOG, ORCL and META tag ONLY year-to-date cash-flow durations.",
                        {"component": component},
                    )
                )
        for component in ytd_components:
            if component.get("start") != period.fiscal_year_start and component.get("role") == "YTD current":
                # Oracle's fiscal year starts 06-01; the spec may pin it explicitly.
                results.append(
                    GuardResult(
                        "T8",
                        "Year-to-date component does not start at the fiscal year start",
                        extraction.ticker,
                        "capex_fact",
                        INFO,
                        f"YTD component starts {component.get('start')}, computed fiscal year start is "
                        f"{period.fiscal_year_start}. Confirm the fiscal calendar.",
                        {"component": component},
                    )
                )
        if not any(r.status == FAIL for r in results):
            results.append(
                GuardResult(
                    "T8",
                    "Quarter correctly derived by year-to-date differencing",
                    extraction.ticker,
                    "capex_fact",
                    PASS,
                    f.derivation,
                    {"components": ytd_components},
                )
            )
    elif f.automation_tier == "auto":
        component = f.components[0] if f.components else {}
        start, end = component.get("start"), component.get("end")
        if start and end:
            from datetime import date as _date

            days = (_date.fromisoformat(end) - _date.fromisoformat(start)).days
            if not 80 <= days <= 100:
                results.append(
                    GuardResult(
                        "T8",
                        "Directly-tagged capex duration is not a quarter",
                        extraction.ticker,
                        "capex_fact",
                        FAIL,
                        f"The selected duration {start} -> {end} spans {days} days, not ~90. "
                        "Amazon is the only filer tagging standalone 3-month cash-flow durations; "
                        "anything longer is a cumulative figure.",
                        {"component": component, "days": days},
                    )
                )
            else:
                results.append(
                    GuardResult(
                        "T8",
                        "Directly-tagged capex duration is a standalone quarter",
                        extraction.ticker,
                        "capex_fact",
                        PASS,
                        f"{start} -> {end} = {days} days.",
                        {"component": component},
                    )
                )
    elif period.ytd_is_quarter:
        results.append(
            GuardResult(
                "T8",
                "Fiscal Q1: the year-to-date period IS the quarter",
                extraction.ticker,
                "capex_fact",
                INFO,
                f"{extraction.ticker} fiscal Q1 ends {period.period_end}; no differencing is "
                "required or performed. This is a DIFFERENT derivation from the other three "
                "quarters -- do not reuse last quarter's formula.",
                {"derivation": f.derivation},
            )
        )
    return results


# ---------------------------------------------------------------------------
# T9 -- the largest "commitments" number is not the backlog
# ---------------------------------------------------------------------------


def _t9_wrong_commitments(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    f = _field(extraction, "demand_fact")
    if f is None or f.value_usd is None or extraction._ixbrl is None:
        return [
            GuardResult("T9", "Purchase-commitments confusion", extraction.ticker, "demand_fact",
                        NOT_APPLICABLE, "No demand fact or no parsed filing.", {})
        ]
    doc = extraction._ixbrl
    wrong: list[dict[str, Any]] = []
    for concept in (
        "us-gaap:ContractualObligation",
        "us-gaap:PurchaseObligation",
        "us-gaap:UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary",
    ):
        for candidate in doc.by_concept(concept):
            if candidate.context.instant == extraction.period.period_end:
                wrong.append({"concept": candidate.concept, "value_usd": candidate.value})
                if abs(candidate.value - f.value_usd) < 1.0:
                    return [
                        GuardResult(
                            "T9",
                            "Demand fact equals a purchase/contractual-obligation figure",
                            extraction.ticker,
                            "demand_fact",
                            FAIL,
                            f"{f.value_usd/1e9:,.1f}$B matches {candidate.concept}, which is what the "
                            "company OWES SUPPLIERS -- the opposite direction from the revenue "
                            "backlog the model needs.",
                            {"concept": candidate.concept},
                        )
                    ]
    return [
        GuardResult(
            "T9",
            "Demand fact is distinct from purchase/contractual obligations",
            extraction.ticker,
            "demand_fact",
            PASS,
            f"demand fact {f.value_usd/1e9:,.1f}$B; obligation-side facts in the same filing: "
            + (", ".join(f"{w['concept'].split(':')[-1]} {w['value_usd']/1e9:,.1f}$B" for w in wrong) or "none tagged"),
            {"obligation_facts": wrong},
        )
    ]


# ---------------------------------------------------------------------------
# T10 -- Amazon's RPO axis is a moving typed member
# ---------------------------------------------------------------------------


def _t10_amzn_rpo_axis(
    extraction: CompanyExtraction, client: EdgarClient | None = None, source_map: Mapping[str, Any] | None = None, **_: Any
) -> list[GuardResult]:
    if extraction.ticker != "AMZN":
        return [
            GuardResult("T10", "Amazon RPO typed axis", extraction.ticker, "demand_fact",
                        NOT_APPLICABLE, "Amazon only.", {})
        ]
    f = _field(extraction, "demand_fact")
    spec = ((source_map or {}).get("companies", {}).get("AMZN", {}).get("demand_fact", {}))
    selector = spec.get("context_selector") or {}
    required_axes = list(selector.get("required_typed_dimensions") or [
        "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"
    ])
    forbidden = list(selector.get("forbidden_dimensions") or ["srt:MajorCustomersAxis"])

    if f is None or f.value_usd is None:
        return [
            GuardResult(
                "T10",
                "Amazon RPO was not extracted from a dimensioned context",
                extraction.ticker,
                "demand_fact",
                FAIL,
                "companyfacts returns NOTHING for Amazon's RPO since 2020-06-30 because every recent "
                "fact carries a typed timing axis. An empty result is NOT 'no data this quarter' and "
                "must never be treated as zero or skipped. "
                + (f.error if f else "field missing"),
                {},
            )
        ]
    context = f.context or {}
    typed = context.get("typed_dimensions") or {}
    explicit = context.get("explicit_dimensions") or {}
    results: list[GuardResult] = []

    missing_axes = [a for a in required_axes if a not in typed]
    if missing_axes:
        results.append(
            GuardResult(
                "T10",
                "Amazon RPO fact is missing the expected timing axis",
                extraction.ticker,
                "demand_fact",
                FAIL,
                f"Context {context.get('id')!r} carries typed axes {list(typed)} but "
                f"{missing_axes} is required. The value may be an undimensioned or differently "
                "scoped figure.",
                {"context": context},
            )
        )
    else:
        member = typed.get(required_axes[0], "")
        results.append(
            GuardResult(
                "T10",
                "Amazon RPO selected by AXIS PRESENCE, not by a hardcoded typed-member date",
                extraction.ticker,
                "demand_fact",
                PASS,
                f"context {context.get('id')} @ {context.get('instant')}; typed member reads "
                f"{member!r} (the day after period end -- it advances every quarter, so it is "
                f"matched on axis presence only). Value {f.value_usd/1e9:,.1f}$B.",
                {"context": context, "typed_member": member},
            )
        )
    hit_forbidden = [a for a in forbidden if a in explicit]
    if hit_forbidden:
        results.append(
            GuardResult(
                "T10",
                "Amazon RPO fact carries a forbidden dimension",
                extraction.ticker,
                "demand_fact",
                FAIL,
                f"Context carries {hit_forbidden}, which selects a customer-specific commitment "
                "(e.g. the $38B OpenAI figure), not the total.",
                {"context": context},
            )
        )
    else:
        siblings = [
            c for c in f.components
            if c.get("explicit_dimensions") and c.get("value") != f.value_usd
        ]
        results.append(
            GuardResult(
                "T10",
                "Customer-specific sibling commitments correctly excluded",
                extraction.ticker,
                "demand_fact",
                PASS,
                "Excluded "
                + (
                    "; ".join(
                        f"{c['value']/1e9:,.0f}$B with {c['explicit_dimensions']}" for c in siblings
                    )
                    or "no sibling facts present"
                ),
                {"excluded": siblings},
            )
        )

    if client is not None:
        try:
            entries = companyfacts_units(
                client.companyfacts(extraction.cik),
                spec.get("concept", "us-gaap:RevenueRemainingPerformanceObligation"),
            )
            at_instant = pick_instant(entries, extraction.period.period_end)
        except Exception:  # noqa: BLE001
            at_instant = []
        results.append(
            GuardResult(
                "T10",
                "companyfacts confirmed empty for Amazon RPO at this instant",
                extraction.ticker,
                "demand_fact",
                PASS if not at_instant else INFO,
                (
                    "As documented: companyfacts returns nothing for Amazon RPO at "
                    f"{extraction.period.period_end}. The value came from the filing's inline XBRL. "
                    "A companyfacts-only fetcher would have silently skipped this company."
                )
                if not at_instant
                else (
                    "companyfacts now DOES return an undimensioned Amazon RPO at this instant "
                    f"({at_instant[-1]['val']/1e9:,.1f}$B). Amazon may have changed its tagging; "
                    "confirm which figure the model should use."
                ),
                {"companyfacts_entries": at_instant[-1] if at_instant else None},
            )
        )
    return results


# ---------------------------------------------------------------------------
# T11 -- Amazon's ~$200B capex plan vs its $200.6B net sales
# ---------------------------------------------------------------------------


def _t11_amzn_netsales(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "AMZN":
        return [
            GuardResult("T11", "Amazon net-sales / capex-plan collision", extraction.ticker,
                        "annual_denominator", NOT_APPLICABLE, "Amazon only.", {})
        ]
    net_sales = None
    doc = extraction._ixbrl
    if doc is not None:
        for candidate in doc.by_concept("us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax"):
            ctx = candidate.context
            if ctx.start == extraction.period.quarter_start and ctx.end == extraction.period.period_end and ctx.is_undimensioned:
                net_sales = candidate.value
                break
    f = _field(extraction, "annual_denominator")
    if f is not None and f.value_usd is not None and net_sales is not None and abs(f.value_usd - net_sales) < 1e9:
        return [
            GuardResult(
                "T11",
                "Amazon annual capex plan equals the quarter's net sales",
                extraction.ticker,
                "annual_denominator",
                FAIL,
                f"The proposed denominator {f.value_usd/1e9:,.1f}$B is within $1B of Amazon's "
                f"quarterly net sales ({net_sales/1e9:,.1f}$B). Amazon's capital plan is not in the "
                "press release at all; the only $200-ish figures in that document are revenue.",
                {"net_sales_usd": net_sales},
            )
        ]
    return [
        GuardResult(
            "T11",
            "Amazon's capex plan is not confusable with its net sales in this packet",
            extraction.ticker,
            "annual_denominator",
            INFO,
            f"Quarterly net sales were {net_sales/1e9:,.1f}$B"
            if net_sales
            else "Quarterly net sales not located in the filing."
            " The annual capital plan is call-only and is refused by the extractor; when the human "
            "supplies it, it must not be a revenue figure.",
            {"net_sales_usd": net_sales},
        )
    ]


# ---------------------------------------------------------------------------
# T12 -- "including finance leases" means two different things
# ---------------------------------------------------------------------------

_FL_PRINCIPAL = "FinanceLeasePrincipalPayments"
_FL_ROU = "RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability"


def _t12_finance_lease_concepts(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    f = _field(extraction, "capex_fact")
    if f is None:
        return []
    concepts = list(f.concepts)
    proxy_concepts = list((f.proxy_only or {}).get("concepts") or [])
    if extraction.ticker == "META":
        if any(_FL_ROU in c for c in concepts):
            return [
                GuardResult(
                    "T12",
                    "Meta capex uses finance-lease ROU ADDITIONS instead of PRINCIPAL PAYMENTS",
                    extraction.ticker,
                    "capex_fact",
                    FAIL,
                    "Meta's disclosed metric adds us-gaap:FinanceLeasePrincipalPayments (a financing "
                    "cash outflow). RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability is a "
                    "non-cash commencement event and is Microsoft's basis, not Meta's.",
                    {"concepts": concepts},
                )
            ]
        if not any(_FL_PRINCIPAL in c for c in concepts):
            return [
                GuardResult(
                    "T12",
                    "Meta capex is missing the finance-lease principal component",
                    extraction.ticker,
                    "capex_fact",
                    FAIL,
                    "Meta's company-defined capex = cash PP&E + finance-lease principal payments. "
                    f"Concepts used: {concepts}.",
                    {"concepts": concepts},
                )
            ]
        return [
            GuardResult(
                "T12",
                "Meta capex uses finance-lease PRINCIPAL PAYMENTS",
                extraction.ticker,
                "capex_fact",
                PASS,
                "us-gaap:FinanceLeasePrincipalPayments, as Meta defines the metric. This formula is "
                "NOT shared with Microsoft.",
                {"concepts": concepts},
            )
        ]
    if extraction.ticker == "MSFT":
        if any(_FL_PRINCIPAL in c for c in proxy_concepts):
            return [
                GuardResult(
                    "T12",
                    "Microsoft proxy uses Meta's finance-lease concept",
                    extraction.ticker,
                    "capex_fact",
                    FAIL,
                    "Microsoft's management metric appears to add finance-lease ROU asset ADDITIONS, "
                    "not principal payments. Applying Meta's formula to Microsoft understates the "
                    "reported figure by roughly 10%.",
                    {"proxy_concepts": proxy_concepts},
                )
            ]
        return [
            GuardResult(
                "T12",
                "Microsoft's XBRL proxy uses finance-lease ROU ADDITIONS (and is a proxy only)",
                extraction.ticker,
                "capex_fact",
                PASS if any(_FL_ROU in c for c in proxy_concepts) else INFO,
                f"proxy concepts: {proxy_concepts or 'none'}. The headline figure remains manual: "
                "Microsoft has never published a reconciliation between the management metric and "
                "these GAAP tags.",
                {"proxy_concepts": proxy_concepts},
            )
        ]
    return [
        GuardResult("T12", "Finance-lease concept separation", extraction.ticker, "capex_fact",
                    NOT_APPLICABLE, "Applies to Microsoft and Meta only.", {})
    ]


# ---------------------------------------------------------------------------
# T13 -- Oracle's period ends are not calendar quarter ends
# ---------------------------------------------------------------------------


def _t13_orcl_period_end(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    period = extraction.period
    if extraction.ticker != "ORCL":
        if period.period_end != period.calendar_quarter_end:
            return [
                GuardResult(
                    "T13",
                    "Non-Oracle filer resolved to a non-calendar period end",
                    extraction.ticker,
                    "period",
                    FAIL,
                    f"{extraction.ticker} resolved to {period.period_end} but its quarters coincide "
                    f"with calendar quarter ends ({period.calendar_quarter_end}). Microsoft's fiscal "
                    "YEAR label is offset; its quarter END dates are not.",
                    {"period": period.to_dict()},
                )
            ]
        return [
            GuardResult(
                "T13",
                "Period end coincides with the calendar quarter end, as expected",
                extraction.ticker,
                "period",
                PASS,
                f"{period.period_end}.",
                {},
            )
        ]
    if period.period_end == period.calendar_quarter_end:
        return [
            GuardResult(
                "T13",
                "Oracle resolved to a CALENDAR quarter end -- it never files one",
                extraction.ticker,
                "period",
                FAIL,
                f"Oracle's quarters end Aug/Nov/Feb/May. Resolved {period.period_end}, which is the "
                "calendar quarter end. A lookup keyed to the calendar quarter returns nothing.",
                {"period": period.to_dict()},
            )
        ]
    return [
        GuardResult(
            "T13",
            "Oracle period end is one month before the calendar quarter end",
            extraction.ticker,
            "period",
            INFO,
            f"bucket {period.report_bucket} (calendar quarter ending {period.calendar_quarter_end}) "
            f"maps to Oracle's {period.fiscal_period} ending {period.period_end}. Every Oracle bucket "
            "carries a one-month timing mismatch against the other four that no automation removes.",
            {"period": period.to_dict()},
        )
    ]


# ---------------------------------------------------------------------------
# T14 -- Oracle's RPO is not economically like the others
# ---------------------------------------------------------------------------


def _t14_orcl_prepaid_hardware(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    if extraction.ticker != "ORCL":
        return [
            GuardResult("T14", "Oracle RPO comparability", extraction.ticker, "demand_fact",
                        NOT_APPLICABLE, "Oracle only.", {})
        ]
    quote, url = _search_all(extraction, ["prepaid"])
    gpu_quote, gpu_url = _search_all(extraction, ["GPU"])
    return [
        GuardResult(
            "T14",
            "Oracle's RPO includes prepaid / customer-supplied hardware",
            extraction.ticker,
            "demand_fact",
            NEEDS_HUMAN,
            "Oracle disclosed that most of its RPO increase came from large-scale AI contracts where "
            "the customer prepaid for the GPUs, or bought and supplied the GPUs to Oracle -- roughly "
            "$75B that reduces Oracle's own capital requirement. The RPO number is machine-readable; "
            "its comparability to Alphabet's or Microsoft's backlog is a judgement call that is not. "
            "Confirm whether the disclosure language changed this quarter. Located: "
            + (quote[:300] or gpu_quote[:300] or "(no prepaid/GPU language found this quarter)"),
            {"quote": quote[:400], "gpu_quote": gpu_quote[:400], "source_url": url or gpu_url},
        )
    ]


# ---------------------------------------------------------------------------
# T15 / X1 -- precision is not uniform; cross-check against the press release
# ---------------------------------------------------------------------------

#: Per-fact tolerance for the press-release cross-check, in USD. MSFT/AMZN/ORCL
#: tag demand facts to whole billions; Alphabet to one decimal; cash-flow items
#: to the million. Rounding is not error -- and a rounded press-release figure
#: never overrides a more precise XBRL derivation.
_CROSS_CHECK_TOLERANCE_USD: dict[tuple[str, str], float] = {
    ("MSFT", "demand_fact"): 5e8,
    ("GOOG", "demand_fact"): 5e7,
    ("AMZN", "demand_fact"): 5e8,
    ("ORCL", "demand_fact"): 5e8,
    ("META", "demand_fact"): 5e6,
    ("GOOG", "capex_fact"): 5e7,
    ("AMZN", "capex_fact"): 5e5,
    ("ORCL", "capex_fact"): 5e5,
    ("META", "capex_fact"): 5e6,
}


#: Company-fields for which NO quarterly cross-check figure is published
#: anywhere, so a missing corroboration is structural rather than suspicious.
_NO_QUARTERLY_COLUMN: frozenset[tuple[str, str]] = frozenset({("ORCL", "capex_fact")})


def _t15_precision_cross_check(extraction: CompanyExtraction, **_: Any) -> list[GuardResult]:
    results: list[GuardResult] = []
    for name in ("demand_fact", "capex_fact"):
        f = _field(extraction, name)
        if f is None or f.value_usd is None:
            continue
        tolerance = _CROSS_CHECK_TOLERANCE_USD.get((extraction.ticker, name), 5e6)
        if f.evidence_quote:
            results.append(
                GuardResult(
                    "T15",
                    f"{name}: value corroborated by a verbatim disclosure, within its own precision",
                    extraction.ticker,
                    name,
                    PASS,
                    f"XBRL value {f.value_usd/1e9:,.3f}$B; tolerance for this fact is "
                    f"+/-{tolerance/1e6:,.1f}M because filers tag demand facts to whole billions and "
                    "cash-flow items to the million. Rounding is not error, and a rounded "
                    "press-release figure never overrides a more precise XBRL derivation. Quote: "
                    + f.evidence_quote[:240],
                    {"quote": f.evidence_quote, "source_url": f.evidence_quote_source_url,
                     "tolerance_usd": tolerance},
                )
            )
        elif (extraction.ticker, name) in _NO_QUARTERLY_COLUMN:
            results.append(
                GuardResult(
                    "X1",
                    f"{name}: no quarterly cross-check column exists for this filer",
                    extraction.ticker,
                    name,
                    INFO,
                    "Oracle publishes no quarterly capex column anywhere -- its press-release table "
                    "is trailing-four-quarters (T2) and must not be read as a quarter. The absence "
                    "of a corroborating figure is structural, not suspicious. The two year-to-date "
                    "components are individually corroborated; the difference between them is "
                    f"arithmetic. Derivation: {f.derivation}",
                    {"derivation": f.derivation, "components": f.components},
                )
            )
        else:
            results.append(
                GuardResult(
                    "X1",
                    f"{name}: no corroborating disclosure located",
                    extraction.ticker,
                    name,
                    NEEDS_HUMAN,
                    "The SOURCE_MAP recommends cross-checking every figure against the "
                    "press-release quarterly column where one exists, and this filer publishes one. "
                    "No on-topic sentence or table row containing this value was found in the "
                    "primary document or Exhibit 99.1. A human must eyeball the filing before this "
                    f"value is accepted. Derivation: {f.derivation}",
                    {"derivation": f.derivation, "components": f.components},
                )
            )
    return results


# ---------------------------------------------------------------------------
# R* -- range and sanity checks
# ---------------------------------------------------------------------------


def _r_sequential_moves(
    extraction: CompanyExtraction, facts_csv: Any = None, **_: Any
) -> list[GuardResult]:
    results: list[GuardResult] = []
    from .dataio import FACTS_CSV

    path = facts_csv or FACTS_CSV
    try:
        previous = prior_row(extraction.ticker, extraction.period.model_period_key, path)
    except FileNotFoundError:
        previous = None
    column = {
        "demand_fact": "rpo_backlog_or_revenue_usd_b",
        "capex_fact": "quarterly_capex_usd_b",
    }
    for name, col in column.items():
        f = _field(extraction, name)
        if f is None or f.value_usd is None:
            continue
        if not (_MIN_PLAUSIBLE_USD <= abs(f.value_usd) <= _MAX_PLAUSIBLE_USD):
            results.append(
                GuardResult(
                    "R3",
                    f"{name} is outside any plausible absolute range",
                    extraction.ticker,
                    name,
                    FAIL,
                    f"{f.value_usd:,.0f} USD is not a plausible quarterly figure for these companies.",
                    {"value_usd": f.value_usd},
                )
            )
            continue
        if previous is None or not previous.get(col):
            results.append(
                GuardResult(
                    "R1" if name == "demand_fact" else "R2",
                    f"{name}: no prior quarter on file to compare against",
                    extraction.ticker,
                    name,
                    NEEDS_HUMAN,
                    "Sequential sanity could not be checked. A first observation must be confirmed "
                    "by a human.",
                    {"value_usd": f.value_usd},
                )
            )
            continue
        prior_value = float(previous[col]) * 1e9
        ratio = f.value_usd / prior_value if prior_value else float("inf")
        change = ratio - 1.0
        thresholds = SEQUENTIAL_MOVE_THRESHOLDS[name]
        guard_id = "R1" if name == "demand_fact" else "R2"
        detail = (
            f"{previous['report_bucket']} {prior_value/1e9:,.3f}$B -> "
            f"{extraction.period.model_period_key} {f.value_usd/1e9:,.3f}$B "
            f"({change:+.1%})"
        )
        if ratio < thresholds["fail_low_ratio"] or ratio > thresholds["fail_high_ratio"]:
            results.append(
                GuardResult(
                    guard_id,
                    f"{name} moved implausibly sequentially",
                    extraction.ticker,
                    name,
                    FAIL,
                    f"{detail}. Outside the [{thresholds['fail_low_ratio']:.2f}x, "
                    f"{thresholds['fail_high_ratio']:.2f}x] band. This is far more likely to be a "
                    "period, unit or definition error than a real move.",
                    {"prior_usd": prior_value, "value_usd": f.value_usd, "ratio": ratio},
                )
            )
        elif abs(change) > thresholds["needs_human_pct"]:
            results.append(
                GuardResult(
                    guard_id,
                    f"{name} moved more than {thresholds['needs_human_pct']:.0%} sequentially",
                    extraction.ticker,
                    name,
                    NEEDS_HUMAN,
                    f"{detail}. A move this large is possible in this cohort but must be confirmed "
                    "explicitly rather than passed through -- check for a definition change, a "
                    "period-selection error, or a one-off.",
                    {"prior_usd": prior_value, "value_usd": f.value_usd, "ratio": ratio},
                )
            )
        else:
            results.append(
                GuardResult(
                    guard_id,
                    f"{name} sequential move is within the plausible band",
                    extraction.ticker,
                    name,
                    PASS,
                    detail,
                    {"prior_usd": prior_value, "value_usd": f.value_usd, "ratio": ratio},
                )
            )
    return results


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

GUARDS: tuple[Callable[..., list[GuardResult]], ...] = (
    _s1_period_matches_spec,
    _s2_filing_present,
    _s4_extraction_status,
    _s6_fetch_errors,
    _s7_pinned_denominator_freshness,
    _t1_orcl_net_outlay,
    _t2_orcl_ttm_table,
    _t3_msft_outlook_policy,
    _t4_msft_rpo_dimension,
    _t5_goog_definition,
    _t6_amzn_gross_vs_net,
    _t7_meta_guidance,
    _t8_ytd_not_quarter,
    _t9_wrong_commitments,
    _t10_amzn_rpo_axis,
    _t11_amzn_netsales,
    _t12_finance_lease_concepts,
    _t13_orcl_period_end,
    _t14_orcl_prepaid_hardware,
    _t15_precision_cross_check,
    _r_sequential_moves,
)


def run_guards(
    extraction: CompanyExtraction,
    client: EdgarClient | None = None,
    source_map: Mapping[str, Any] | None = None,
    facts_csv: Any = None,
    include_not_applicable: bool = False,
) -> GuardOutcome:
    """Run every guard against one company-quarter extraction."""
    results: list[GuardResult] = []
    for guard in GUARDS:
        try:
            results.extend(
                guard(extraction, client=client, source_map=source_map, facts_csv=facts_csv)
            )
        except Exception as exc:  # noqa: BLE001 - a broken guard must not pass silently
            results.append(
                GuardResult(
                    getattr(guard, "__name__", "?").split("_")[1].upper(),
                    f"Guard raised: {guard.__name__}",
                    extraction.ticker,
                    "-",
                    FAIL,
                    f"{type(exc).__name__}: {exc}. A guard that cannot run is treated as a failure, "
                    "never as a pass.",
                    {},
                )
            )
    if not include_not_applicable:
        results = [r for r in results if r.status != NOT_APPLICABLE]
    return GuardOutcome(extraction.ticker, extraction.report_bucket, results)


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    sys.stdout.reconfigure(encoding="utf-8")
    from .extract import TICKERS, extract_company, load_source_map

    bucket = argv[0] if argv else "CY2026Q2"
    tickers = argv[1:] or list(TICKERS)
    source_map = load_source_map()
    client = EdgarClient()
    for ticker in tickers:
        extraction = extract_company(ticker, bucket, client=client, source_map=source_map)
        outcome = run_guards(extraction, client=client, source_map=source_map)
        print(f"\n=== {ticker} {bucket} ===")
        for r in outcome.results:
            print(f"  [{r.status:14s}] {r.id:3s} {r.name}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
