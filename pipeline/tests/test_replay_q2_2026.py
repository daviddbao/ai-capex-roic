"""ACCEPTANCE TEST — replay the quarter ending June 2026.

The next real filing is not until late October 2026, so the pipeline is proved
by replay: run it against ``report_bucket`` CY2026Q2 and require that it
INDEPENDENTLY re-derives the ``Q2 26`` row already in ``data/facts.csv`` -- to
the dollar, for all nine machine-readable core facts -- and that it REFUSES the
five permanently-manual inputs rather than guessing them.

Nothing here reads a value from ``source_map.json``'s ``verified_q2_2026``
field. The expectations come from ``data/facts.csv`` (the model's own row), and
the actuals come from live SEC data. If they disagree, the test fails and the
expectation is not adjusted.
"""

from __future__ import annotations

import csv

import pytest

from pipeline import REPO_ROOT
from pipeline.edgar import companyfacts_units, pick_instant
from pipeline.extract import TICKERS

REPLAY_BUCKET = "CY2026Q2"
MODEL_PERIOD_KEY = "Q2 26"

#: The nine core facts that must be machine-readable. Microsoft's quarterly
#: capex is deliberately absent: it exists in no SEC filing.
MACHINE_READABLE_CORE = [
    ("MSFT", "demand_fact"),
    ("GOOG", "demand_fact"),
    ("GOOG", "capex_fact"),
    ("AMZN", "demand_fact"),
    ("AMZN", "capex_fact"),
    ("ORCL", "demand_fact"),
    ("ORCL", "capex_fact"),
    ("META", "demand_fact"),
    ("META", "capex_fact"),
]

#: The five inputs that must be REFUSED, never guessed.
PERMANENTLY_MANUAL = [
    ("MSFT", "capex_fact"),
    ("MSFT", "annual_denominator"),
    ("GOOG", "annual_denominator"),
    ("AMZN", "annual_denominator"),
    ("META", "annual_denominator"),
]

_COLUMN_FOR_FIELD = {
    "demand_fact": "rpo_backlog_or_revenue_usd_b",
    "capex_fact": "quarterly_capex_usd_b",
}


def _expected_row(ticker: str) -> dict[str, str]:
    with open(REPO_ROOT / "data" / "facts.csv", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["ticker"] == ticker and row["report_bucket"] == MODEL_PERIOD_KEY:
                return row
    raise AssertionError(f"no {ticker} {MODEL_PERIOD_KEY} row in data/facts.csv")


def _expected_usd(ticker: str, field: str) -> int:
    return round(float(_expected_row(ticker)[_COLUMN_FOR_FIELD[field]]) * 1e9)


# ---------------------------------------------------------------------------
# The nine machine-readable core facts, to the dollar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker,field", MACHINE_READABLE_CORE)
def test_core_fact_reproduces_the_existing_row_to_the_dollar(
    ticker, field, replay_extractions
):
    extracted = replay_extractions[ticker].fields[field]
    assert extracted.status == "extracted", (
        f"{ticker}.{field} did not extract: {extracted.error or extracted.human_instruction}"
    )
    assert round(extracted.value_usd) == _expected_usd(ticker, field), (
        f"{ticker}.{field}: pipeline derived {extracted.value_usd:,.0f} USD but "
        f"data/facts.csv holds {_expected_usd(ticker, field):,.0f} USD. "
        f"Derivation was: {extracted.derivation}"
    )


def test_all_nine_core_facts_are_machine_readable(replay_extractions):
    extracted = [
        (t, f)
        for t, f in MACHINE_READABLE_CORE
        if replay_extractions[t].fields[f].status == "extracted"
    ]
    assert len(extracted) == 9, f"only {len(extracted)}/9 core facts extracted: {extracted}"


def test_period_and_fiscal_labels_match_the_existing_row(replay_extractions):
    for ticker in TICKERS:
        period = replay_extractions[ticker].period
        row = _expected_row(ticker)
        assert period.period_end == row["period_end"], ticker
        assert period.fiscal_period == row["fiscal_period"], ticker
        assert period.model_period_key == MODEL_PERIOD_KEY, ticker


# ---------------------------------------------------------------------------
# The two dimensional facts -- the whole reason this pipeline exists
# ---------------------------------------------------------------------------


def test_msft_resolves_to_678B_and_not_684B(replay_extractions, client):
    field = replay_extractions["MSFT"].fields["demand_fact"]
    assert field.value_usd == 678_000_000_000, field.value_usd
    assert field.value_usd != 684_000_000_000

    context = field.context or {}
    assert (
        context.get("explicit_dimensions", {}).get("srt:MajorCustomersAxis")
        == "msft:CommercialCustomersMember"
    ), context

    # And prove the trap is real: companyfacts alone returns the wrong number.
    entries = companyfacts_units(
        client.companyfacts("0000789019"), "us-gaap:RevenueRemainingPerformanceObligation"
    )
    undimensioned = pick_instant(entries, "2026-06-30")
    assert undimensioned, "expected companyfacts to return a total-RPO fact"
    assert float(undimensioned[-1]["val"]) == 684_000_000_000, (
        "companyfacts no longer returns the total-RPO trap value; re-verify the mapping"
    )


def test_amzn_resolves_to_496B_and_companyfacts_is_empty(replay_extractions, client):
    field = replay_extractions["AMZN"].fields["demand_fact"]
    assert field.value_usd == 496_000_000_000, field.value_usd
    assert field.status == "extracted"

    context = field.context or {}
    typed = context.get("typed_dimensions", {})
    assert (
        "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"
        in typed
    ), context
    assert "srt:MajorCustomersAxis" not in context.get("explicit_dimensions", {}), context

    # The sibling customer-specific commitment must have been seen and excluded.
    siblings = [c for c in field.components if c.get("explicit_dimensions")]
    assert siblings, "expected to see the customer-specific sibling fact in the filing"
    assert all(c["value"] != field.value_usd for c in siblings)

    # And prove the trap: companyfacts returns nothing at this instant.
    entries = companyfacts_units(
        client.companyfacts("0001018724"), "us-gaap:RevenueRemainingPerformanceObligation"
    )
    assert pick_instant(entries, "2026-06-30") == [], (
        "companyfacts now returns an Amazon RPO fact; the access mapping needs re-verifying"
    )


def test_amzn_typed_member_is_matched_by_axis_presence_not_a_hardcoded_date(
    replay_extractions,
):
    field = replay_extractions["AMZN"].fields["demand_fact"]
    member = (field.context or {}).get("typed_dimensions", {}).get(
        "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis"
    )
    assert member == "2026-07-01", member
    assert "2026-07-01" not in field.derivation, (
        "the derivation must select on axis presence; the typed member advances every quarter"
    )


# ---------------------------------------------------------------------------
# The five permanently-manual inputs must be refused, not guessed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker,field", PERMANENTLY_MANUAL)
def test_manual_field_is_refused_with_an_actionable_instruction(
    ticker, field, replay_extractions
):
    extracted = replay_extractions[ticker].fields[field]
    assert extracted.status == "refused_manual", (
        f"{ticker}.{field} should be refused but is {extracted.status} "
        f"with value {extracted.value_usd!r}"
    )
    assert extracted.value_usd is None, "a refused field must carry no value"
    assert extracted.automation_tier == "manual"
    assert extracted.access == "not_in_xbrl"
    assert "HUMAN REQUIRED" in extracted.human_instruction
    assert extracted.human_source_url.startswith("http"), extracted.human_source_url


def test_exactly_five_inputs_are_refused(replay_extractions):
    refused = [
        (t, name)
        for t in TICKERS
        for name, f in replay_extractions[t].fields.items()
        if f.status == "refused_manual"
    ]
    assert sorted(refused) == sorted(PERMANENTLY_MANUAL), refused


def test_msft_capex_proxy_is_offered_as_a_sanity_check_and_not_as_a_value(
    replay_extractions,
):
    field = replay_extractions["MSFT"].fields["capex_fact"]
    assert field.value_usd is None
    proxy = field.proxy_only
    assert proxy is not None and proxy["is_a_value"] is False
    # FY minus 9M for both terms, because Q4 has no standalone quarterly column.
    assert proxy["value_usd"] == 40_924_000_000, proxy
    reported = _expected_usd("MSFT", "capex_fact")
    assert reported == 41_000_000_000
    assert proxy["value_usd"] != reported, (
        "the proxy must not be mistaken for the reported management metric"
    )


def test_orcl_annual_denominator_is_the_one_automatable_denominator(replay_extractions):
    field = replay_extractions["ORCL"].fields["annual_denominator"]
    assert field.status == "extracted"
    assert field.value_usd == 55_663_000_000, field.value_usd
    assert field.automation_tier == "auto"
    for ticker in ("MSFT", "GOOG", "AMZN", "META"):
        assert replay_extractions[ticker].fields["annual_denominator"].status == "refused_manual"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_every_extracted_fact_carries_a_source_url_and_a_derivation(replay_extractions):
    for ticker in TICKERS:
        for name, field in replay_extractions[ticker].fields.items():
            if field.status != "extracted":
                continue
            assert field.source_url.startswith("http"), f"{ticker}.{name}"
            assert field.derivation, f"{ticker}.{name}"


def test_derived_capex_shows_its_arithmetic(replay_extractions):
    """GOOG, ORCL and META tag year-to-date cash flows only."""
    for ticker, expected_concept_count in (("GOOG", 1), ("ORCL", 1), ("META", 2)):
        field = replay_extractions[ticker].fields["capex_fact"]
        assert field.automation_tier == "derived", ticker
        assert len(field.concepts) == expected_concept_count, ticker
        ytd = [c for c in field.components if str(c.get("role", "")).startswith("YTD")]
        assert len(ytd) == expected_concept_count * 2, (ticker, ytd)
        for component in ytd:
            assert component["val"] != field.value_usd, (
                f"{ticker}: a year-to-date component equals the emitted quarter"
            )


def test_filings_match_the_accessions_recorded_in_the_source_map(
    replay_extractions, source_map
):
    for ticker in TICKERS:
        recorded = source_map["companies"][ticker]["latest_filing"]
        found = replay_extractions[ticker].periodic_filing
        assert found is not None, ticker
        assert found["accession"] == recorded["accession"], (
            f"{ticker}: EDGAR returned {found['accession']} for reportDate "
            f"{found['report_date']}, source_map records {recorded['accession']}"
        )
