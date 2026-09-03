"""Period arithmetic and the inline-XBRL parser, tested without the network.

The period tests matter because the derivation SHAPE changes between quarters:
Oracle's fiscal Q1 year-to-date IS the quarter, Microsoft's fiscal Q4 has no
standalone quarterly column, and Oracle's period ends never coincide with a
calendar quarter end.
"""

from __future__ import annotations

import pytest

from pipeline.edgar import parse_inline_xbrl
from pipeline.extract import (
    bucket_to_model_key,
    find_fragment,
    find_sentence,
    load_source_map,
    model_key_to_bucket,
    resolve_period,
    visible_text,
)


@pytest.fixture(scope="module")
def companies():
    return load_source_map()["companies"]


# ---------------------------------------------------------------------------
# Bucket keys
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bucket,key", [("CY2026Q2", "Q2 26"), ("CY2026Q3", "Q3 26"), ("CY2025Q4", "Q4 25")]
)
def test_bucket_key_round_trip(bucket, key):
    assert bucket_to_model_key(bucket) == key
    assert model_key_to_bucket(key) == bucket


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ticker,bucket,period_end,fiscal_period,form,fiscal_quarter",
    [
        ("MSFT", "CY2026Q2", "2026-06-30", "FY26 Q4", "10-K", 4),
        ("MSFT", "CY2026Q3", "2026-09-30", "FY27 Q1", "10-Q", 1),
        ("GOOG", "CY2026Q3", "2026-09-30", "Q3 2026", "10-Q", 3),
        ("AMZN", "CY2026Q3", "2026-09-30", "Q3 2026", "10-Q", 3),
        ("ORCL", "CY2026Q2", "2026-05-31", "FY26 Q4", "10-K", 4),
        ("ORCL", "CY2026Q3", "2026-08-31", "FY27 Q1", "10-Q", 1),
        ("META", "CY2026Q3", "2026-09-30", "Q3 2026", "10-Q", 3),
    ],
)
def test_period_resolution(
    companies, ticker, bucket, period_end, fiscal_period, form, fiscal_quarter
):
    period = resolve_period(companies[ticker], bucket, ticker)
    assert period.period_end == period_end
    assert period.fiscal_period == fiscal_period
    assert period.expected_form == form
    assert period.fiscal_quarter == fiscal_quarter


def test_oracle_is_the_only_offset_filer(companies):
    for ticker in ("MSFT", "GOOG", "AMZN", "META"):
        period = resolve_period(companies[ticker], "CY2026Q3", ticker)
        assert period.period_end == period.calendar_quarter_end == "2026-09-30", ticker
    orcl = resolve_period(companies["ORCL"], "CY2026Q3", "ORCL")
    assert orcl.calendar_quarter_end == "2026-09-30"
    assert orcl.period_end == "2026-08-31"


@pytest.mark.parametrize(
    "ticker,bucket,ytd_is_quarter",
    [
        ("ORCL", "CY2026Q3", True),   # FY27 Q1: YTD IS the quarter, no differencing
        ("ORCL", "CY2026Q2", False),  # FY26 Q4: FY minus 9M
        ("GOOG", "CY2026Q1", True),   # calendar Q1
        ("GOOG", "CY2026Q3", False),
        ("MSFT", "CY2026Q3", True),   # FY27 Q1
    ],
)
def test_ytd_is_quarter_only_in_fiscal_q1(companies, ticker, bucket, ytd_is_quarter):
    assert resolve_period(companies[ticker], bucket, ticker).ytd_is_quarter is ytd_is_quarter


def test_fiscal_year_starts(companies):
    assert resolve_period(companies["ORCL"], "CY2026Q3", "ORCL").fiscal_year_start == "2026-06-01"
    assert resolve_period(companies["MSFT"], "CY2026Q3", "MSFT").fiscal_year_start == "2026-07-01"
    assert resolve_period(companies["GOOG"], "CY2026Q3", "GOOG").fiscal_year_start == "2026-01-01"


def test_resolution_agrees_with_the_pinned_spec_where_one_exists(companies):
    for ticker, company in companies.items():
        for bucket in company["report_bucket_map"]:
            period = resolve_period(company, bucket, ticker)
            assert period.source_map_agrees is True, (ticker, bucket, period)


def test_prior_period_end_is_a_month_end(companies):
    period = resolve_period(companies["ORCL"], "CY2026Q2", "ORCL")
    assert period.prior_period_end == "2026-02-28"
    assert period.quarter_start == "2026-03-01"


# ---------------------------------------------------------------------------
# Inline-XBRL parser
# ---------------------------------------------------------------------------

_DOC = """
<html><body>
<xbrli:context id="C_total">
  <xbrli:entity><xbrli:identifier>0000789019</xbrli:identifier></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
</xbrli:context>
<xbrli:context id="C_commercial">
  <xbrli:entity><xbrli:identifier>0000789019</xbrli:identifier>
    <xbrli:segment>
      <xbrldi:explicitMember dimension="srt:MajorCustomersAxis">msft:CommercialCustomersMember</xbrldi:explicitMember>
    </xbrli:segment>
  </xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
</xbrli:context>
<xbrli:context id="C_typed">
  <xbrli:entity><xbrli:segment>
    <xbrldi:typedMember dimension="us-gaap:TimingAxis"><us-gaap:StartDate>2026-07-01</us-gaap:StartDate></xbrldi:typedMember>
  </xbrli:segment></xbrli:entity>
  <xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period>
</xbrli:context>
<xbrli:context id="C_duration">
  <xbrli:period><xbrli:startDate>2026-04-01</xbrli:startDate><xbrli:endDate>2026-06-30</xbrli:endDate></xbrli:period>
</xbrli:context>
<p>Total was
<ix:nonFraction name="us-gaap:RevenueRemainingPerformanceObligation" contextRef="C_total" unitRef="usd" scale="9" decimals="-9">684</ix:nonFraction>
and commercial was
<ix:nonFraction name="us-gaap:RevenueRemainingPerformanceObligation" contextRef="C_commercial" unitRef="usd" scale="9" decimals="-9">678</ix:nonFraction>
and typed was
<ix:nonFraction name="us-gaap:RevenueRemainingPerformanceObligation" contextRef="C_typed" unitRef="usd" scale="9">496</ix:nonFraction>.
Capex was
<ix:nonFraction name="us-gaap:PaymentsToAcquireProductiveAssets" contextRef="C_duration" unitRef="usd" scale="6" sign="-">54,208</ix:nonFraction>.
</p></body></html>
"""


def test_parser_resolves_dimensions_scale_and_sign():
    doc = parse_inline_xbrl(_DOC, source_url="http://example/doc.htm")
    assert len(doc.contexts) == 4
    values = {f.context.id: f.value for f in doc.by_concept("us-gaap:RevenueRemainingPerformanceObligation")}
    assert values == {
        "C_total": 684e9,
        "C_commercial": 678e9,
        "C_typed": 496e9,
    }
    capex = doc.by_concept("us-gaap:PaymentsToAcquireProductiveAssets")[0]
    assert capex.value == -54_208_000_000.0
    assert capex.context.duration_days == 90


def test_selection_by_required_explicit_dimension():
    doc = parse_inline_xbrl(_DOC)
    picked = doc.select(
        "us-gaap:RevenueRemainingPerformanceObligation",
        instant="2026-06-30",
        required_explicit_dimensions={"srt:MajorCustomersAxis": "msft:CommercialCustomersMember"},
    )
    assert [f.value for f in picked] == [678e9]


def test_selection_by_axis_presence_and_exclusion():
    doc = parse_inline_xbrl(_DOC)
    picked = doc.select(
        "us-gaap:RevenueRemainingPerformanceObligation",
        instant="2026-06-30",
        required_axes=["us-gaap:TimingAxis"],
        forbidden_axes=["srt:MajorCustomersAxis"],
    )
    assert [f.value for f in picked] == [496e9]
    assert picked[0].context.typed_dimensions["us-gaap:TimingAxis"] == "2026-07-01"


def test_must_be_undimensioned_excludes_every_dimensioned_fact():
    doc = parse_inline_xbrl(_DOC)
    picked = doc.select(
        "us-gaap:RevenueRemainingPerformanceObligation",
        instant="2026-06-30",
        must_be_undimensioned=True,
    )
    assert [f.value for f in picked] == [684e9]


def test_facts_with_an_unresolvable_context_are_skipped_not_guessed():
    doc = parse_inline_xbrl(
        '<ix:nonFraction name="us-gaap:Foo" contextRef="missing" scale="6">1,000</ix:nonFraction>'
    )
    assert doc.facts == []


# ---------------------------------------------------------------------------
# Evidence helpers
# ---------------------------------------------------------------------------


def test_visible_text_survives_entities_and_tags():
    text = visible_text("<p>Capital&nbsp;expenditures were&#160;$44.9&nbsp;billion.</p>")
    assert "Capital expenditures were $44.9 billion." in text


def test_find_sentence_requires_every_needle():
    text = "Revenue was $60.8 billion. Capital expenditures were $31.08 billion."
    assert find_sentence(text, ["31.08", "capital expenditures"]).startswith("Capital")
    assert find_sentence(text, ["31.08", "revenue"]) == ""


def test_find_fragment_windows_a_table_row():
    text = "INVESTING ACTIVITIES: Purchases of property and equipment (32,183) (54,208) Proceeds"
    fragment = find_fragment(text, ["54,208", "purchases of property and equipment"], window=60)
    assert "54,208" in fragment and "Purchases of property and equipment" in fragment
