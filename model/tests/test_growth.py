"""The trajectory grows forever; the YoY and QoQ anchors roll with it.

These tests exist because the original workbook computed exactly one change
row -- "delta Spread Q2 26 vs Q2 25" -- which happened to be BOTH the
year-over-year comparison and the versus-oldest-quarter comparison, because the
series was exactly five quarters long. Those two readings diverge the moment a
sixth quarter is appended. Everything here pins down which is which.
"""

from __future__ import annotations

import copy
from datetime import datetime

import pytest

from model import build
from model.build import (
    QUARTERS_PER_YEAR,
    QuarterFact,
    build_snapshot,
    build_trajectory,
    load_inputs,
    ordered_quarters,
)


@pytest.fixture(scope="module")
def workbook_inputs():
    return load_inputs()


def _extend(facts, assumptions, bucket: str, period_end: datetime, *, capex_mult=1.0):
    """Append a synthetic quarter for every company, one bucket past the last."""
    out = list(facts)
    latest = ordered_quarters(facts)[-1]
    for fact in [f for f in facts if f.quarter == latest]:
        out.append(
            QuarterFact(
                ticker=fact.ticker,
                company=fact.company,
                quarter=bucket,
                fiscal_period=f"{bucket} (synthetic)",
                # Preserve each filer's own month offset; Oracle is a month early.
                period_end=period_end.replace(day=28)
                if fact.ticker == "ORCL"
                else period_end,
                fact_value_b=fact.fact_value_b * 1.05,
                fact_metric=fact.fact_metric,
                quarterly_capex_b=fact.quarterly_capex_b * capex_mult,
                capex_definition=fact.capex_definition,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


def test_quarter_order_is_derived_not_hardcoded(workbook_inputs):
    facts, _ = workbook_inputs
    assert ordered_quarters(facts) == ("Q2 25", "Q3 25", "Q4 25", "Q1 26", "Q2 26")


def test_quarter_order_is_chronological_not_lexical(workbook_inputs):
    """"Q1 26" sorts before "Q2 25" lexically but comes after it in time."""
    facts, _ = workbook_inputs
    quarters = ordered_quarters(facts)
    assert quarters.index("Q2 25") < quarters.index("Q1 26")
    assert sorted(quarters) != list(quarters)


def test_oracles_earlier_period_end_does_not_reorder_buckets(workbook_inputs):
    """Oracle's quarters end a month before the other four; buckets still align."""
    facts, _ = workbook_inputs
    orcl = {f.quarter: f.period_end for f in facts if f.ticker == "ORCL"}
    msft = {f.quarter: f.period_end for f in facts if f.ticker == "MSFT"}
    assert orcl["Q2 26"] < msft["Q2 26"]
    assert ordered_quarters(facts)[-1] == "Q2 26"


def test_quarter_without_period_end_is_refused(workbook_inputs):
    facts, _ = workbook_inputs
    broken = list(facts) + [
        QuarterFact(
            ticker="MSFT",
            company="Microsoft",
            quarter="Q3 26",
            fiscal_period="FY27 Q1",
            period_end=None,
            fact_value_b=700.0,
            fact_metric="Commercial RPO",
            quarterly_capex_b=42.0,
            capex_definition="x",
        )
    ]
    with pytest.raises(ValueError, match="period_end"):
        ordered_quarters(broken)


# ---------------------------------------------------------------------------
# Growth
# ---------------------------------------------------------------------------


def test_trajectory_grows_and_drops_nothing(workbook_inputs):
    facts, assumptions = workbook_inputs
    grown = _extend(facts, assumptions, "Q3 26", datetime(2026, 9, 30))

    before = build_trajectory(facts, assumptions)
    after = build_trajectory(grown, assumptions)

    assert len(before) == 25
    assert len(after) == 30
    assert ordered_quarters(grown)[-1] == "Q3 26"
    # The original five quarters survive unchanged -- nothing rolls off.
    assert set(before["quarter"]) < set(after["quarter"])
    merged = after.merge(before, on=["ticker", "quarter"], suffixes=("", "_before"))
    assert len(merged) == 25
    assert merged["spread"].equals(merged["spread_before"])


def test_quarter_index_stays_contiguous_after_growth(workbook_inputs):
    facts, assumptions = workbook_inputs
    grown = _extend(facts, assumptions, "Q3 26", datetime(2026, 9, 30))
    traj = build_trajectory(grown, assumptions)
    for ticker in build.TICKERS:
        idx = sorted(traj[traj["ticker"] == ticker]["quarter_index"])
        assert idx == list(range(6))


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------


def test_at_five_quarters_yoy_equals_the_workbook_change_row(workbook_inputs):
    """The workbook's one change row is the YoY read; this must not shift."""
    facts, assumptions = workbook_inputs
    snap = build_snapshot(facts, assumptions)
    for row in snap.itertuples():
        assert row.yoy_quarter == "Q2 25"
        assert row.delta_spread_yoy_bps == pytest.approx(row.delta_spread_bps)


def test_qoq_matches_the_methodology_documents_sequential_change(workbook_inputs):
    """The doc publishes a sequential change the workbook never computed."""
    facts, assumptions = workbook_inputs
    snap = build_snapshot(facts, assumptions).drop_duplicates("ticker")
    published_ppt = {  # methodology doc, "Sequential spread change"
        "MSFT": -5.5,
        "GOOG": -3.8,
        "AMZN": +1.2,
        "ORCL": +7.7,
        "META": -6.3,
    }
    for row in snap.itertuples():
        assert row.qoq_quarter == "Q1 26"
        assert row.delta_spread_qoq_bps / 100 == pytest.approx(
            published_ppt[row.ticker], abs=0.05
        )


def test_yoy_rolls_forward_but_baseline_stays_put(workbook_inputs):
    """After a sixth quarter: YoY moves to Q3 25, the permanent baseline does not."""
    facts, assumptions = workbook_inputs
    grown = _extend(facts, assumptions, "Q3 26", datetime(2026, 9, 30))
    snap = build_snapshot(grown, assumptions)
    for row in snap.itertuples():
        assert row.quarter == "Q3 26"
        assert row.yoy_quarter == "Q3 25"  # rolled
        assert row.qoq_quarter == "Q2 26"  # rolled
    # The versus-oldest baseline is still the original base quarter.
    reference = build_snapshot(grown, assumptions, base_quarter="Q2 25")
    assert reference["spread_base_runrate"].equals(snap["spread_base_runrate"])


def test_yoy_is_four_buckets_back_not_the_series_start(workbook_inputs):
    facts, assumptions = workbook_inputs
    grown = facts
    for i, (bucket, end) in enumerate(
        [("Q3 26", datetime(2026, 9, 30)), ("Q4 26", datetime(2026, 12, 31))]
    ):
        grown = _extend(grown, assumptions, bucket, end)
    quarters = ordered_quarters(grown)
    snap = build_snapshot(grown, assumptions)
    expected = quarters[quarters.index("Q4 26") - QUARTERS_PER_YEAR]
    assert expected == "Q4 25"
    for row in snap.itertuples():
        assert row.yoy_quarter == "Q4 25"
        assert row.spread_yoy_runrate != row.spread_base_runrate


def test_anchors_are_none_when_history_is_too_short(workbook_inputs):
    """A short series reports no anchor rather than inventing a comparison."""
    facts, assumptions = workbook_inputs
    two = [f for f in facts if f.quarter in ("Q2 25", "Q3 25")]
    snap = build_snapshot(two, assumptions)
    for row in snap.itertuples():
        assert row.yoy_quarter is None
        assert row.spread_yoy_runrate is None
        assert row.delta_spread_yoy_bps is None
        assert row.qoq_quarter == "Q2 25"
        assert row.delta_spread_qoq_bps is not None


def test_qoq_reacts_to_the_newest_quarter_only(workbook_inputs):
    """A capex jump in the new quarter moves QoQ; YoY moves by the same amount."""
    facts, assumptions = workbook_inputs
    grown = _extend(facts, assumptions, "Q3 26", datetime(2026, 9, 30), capex_mult=2.0)
    snap = build_snapshot(grown, assumptions).drop_duplicates("ticker")
    for row in snap.itertuples():
        # Doubling capex halves the run-rate ROIC, so the spread must fall.
        assert row.delta_spread_qoq_bps < 0


# ---------------------------------------------------------------------------
# The CSV path produces the same model as the workbook path
# ---------------------------------------------------------------------------


def test_csv_layer_reproduces_the_workbook_model(workbook_inputs):
    wb_facts, wb_assum = workbook_inputs
    csv_facts, csv_assum = build.load_inputs_from_csv()

    assert len(csv_facts) == len(wb_facts) == 25
    assert ordered_quarters(csv_facts) == ordered_quarters(wb_facts)

    wb_traj = build_trajectory(wb_facts, wb_assum).sort_values(["ticker", "quarter"])
    csv_traj = build_trajectory(csv_facts, csv_assum).sort_values(["ticker", "quarter"])
    for column in ("ai_capex_b", "ai_revenue_proxy_b", "forward_roic", "spread"):
        assert csv_traj[column].to_numpy() == pytest.approx(
            wb_traj[column].to_numpy(), rel=1e-12, abs=0.0
        )

    wb_snap = build_snapshot(wb_facts, wb_assum).sort_values(["ticker", "scenario"])
    csv_snap = build_snapshot(csv_facts, csv_assum).sort_values(["ticker", "scenario"])
    for column in ("forward_roic", "spread", "delta_spread_yoy_bps"):
        assert csv_snap[column].to_numpy() == pytest.approx(
            wb_snap[column].to_numpy(), rel=1e-12, abs=0.0
        )


def test_csv_assumptions_pick_the_latest_applicable_version():
    """Versioned assumption rows must resolve to one row per ticker."""
    _, assumptions = build.load_inputs_from_csv()
    assert set(assumptions) == set(build.TICKERS)
    assert assumptions["AMZN"].rpo_duration_years == 4.0  # v02 value, not disclosed 6.4
    assert assumptions["META"].rpo_duration_years is None
