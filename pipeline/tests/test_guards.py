"""Every guard must FAIL LOUDLY when its trap is actually sprung.

A guard that only ever passes on good data proves nothing. Each test here
takes a real extraction, tampers with it in exactly the way the corresponding
trap in ``docs/SOURCE_MAP.md`` §3 describes, and asserts the guard blocks.
"""

from __future__ import annotations

import copy
import dataclasses

import pytest

from pipeline.guards import (
    FAIL,
    INFO,
    NEEDS_HUMAN,
    PASS,
    SEQUENTIAL_MOVE_THRESHOLDS,
    run_guards,
)


def _tamper(extractions, ticker, field, **changes):
    """A deep copy of one extraction with one field mutated."""
    extraction = copy.deepcopy(extractions[ticker])
    target = extraction.fields[field]
    for key, value in changes.items():
        setattr(target, key, value)
    return extraction


def _by_id(outcome, guard_id):
    return [r for r in outcome.results if r.id == guard_id]


def _statuses(outcome, guard_id):
    return {r.status for r in _by_id(outcome, guard_id)}


# ---------------------------------------------------------------------------
# T4 -- Microsoft total RPO vs commercial RPO
# ---------------------------------------------------------------------------


def test_t4_fails_when_msft_rpo_falls_back_to_the_undimensioned_total(
    replay_extractions, client, source_map
):
    """The single most dangerous trap: $684B looks entirely plausible."""
    tampered = _tamper(
        replay_extractions,
        "MSFT",
        "demand_fact",
        value_usd=684_000_000_000.0,
        context={
            "id": "C_ca004a37-7abb-4b0e-8638-a7c6b14ebb45",
            "instant": "2026-06-30",
            "start": None,
            "end": None,
            "explicit_dimensions": {},
            "typed_dimensions": {},
        },
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T4")
    assert any("commercial" in r.message.lower() for r in _by_id(outcome, "T4"))


def test_t4_fails_when_the_selection_returns_the_same_value_as_companyfacts(
    replay_extractions, client, source_map
):
    """Even with the right dimension, matching the total means the selector broke."""
    tampered = copy.deepcopy(replay_extractions["MSFT"])
    tampered.fields["demand_fact"].value_usd = 684_000_000_000.0
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T4")


def test_t4_passes_on_the_real_extraction(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["MSFT"], client=client, source_map=source_map)
    assert _statuses(outcome, "T4") == {PASS}


# ---------------------------------------------------------------------------
# T10 -- Amazon's RPO axis
# ---------------------------------------------------------------------------


def test_t10_fails_when_amzn_rpo_comes_back_empty(replay_extractions, client, source_map):
    """companyfacts returns nothing; an empty result is not 'no data'."""
    tampered = _tamper(
        replay_extractions, "AMZN", "demand_fact",
        status="error", value_usd=None, context=None,
        error="No fact at instant 2026-06-30 in companyfacts",
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T10")
    assert any("never be treated as zero" in r.message for r in _by_id(outcome, "T10"))


def test_t10_fails_when_the_customer_specific_sibling_is_selected(
    replay_extractions, client, source_map
):
    tampered = _tamper(
        replay_extractions, "AMZN", "demand_fact",
        value_usd=38_000_000_000.0,
        context={
            "id": "c-47",
            "instant": "2026-06-30",
            "start": None,
            "end": None,
            "explicit_dimensions": {"srt:MajorCustomersAxis": "amzn:OpenAIGroupPBCMember"},
            "typed_dimensions": {
                "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis": "2026-07-01"
            },
        },
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T10")


def test_t10_fails_when_the_timing_axis_is_missing(replay_extractions, client, source_map):
    tampered = _tamper(
        replay_extractions, "AMZN", "demand_fact",
        context={
            "id": "c-1", "instant": "2026-06-30", "start": None, "end": None,
            "explicit_dimensions": {}, "typed_dimensions": {},
        },
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T10")


# ---------------------------------------------------------------------------
# T1 / T2 -- Oracle net cash outlay and the TTM table
# ---------------------------------------------------------------------------


def test_t1_fails_on_oracles_net_cash_outlay_figure(replay_extractions, client, source_map):
    """$47,726M FY2026 net outlay must never stand in for $55,663M gross capex."""
    tampered = _tamper(
        replay_extractions, "ORCL", "annual_denominator", value_usd=47_726_000_000.0
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    failures = [r for r in _by_id(outcome, "T1") if r.status == FAIL]
    assert failures, [r.status for r in _by_id(outcome, "T1")]
    assert "NET CASH OUTLAY" in failures[0].message.upper()


def test_t1_fails_when_oracle_capex_is_not_from_the_gaap_tag(
    replay_extractions, client, source_map
):
    tampered = _tamper(
        replay_extractions, "ORCL", "capex_fact", concepts=["press-release:CapitalExpenditures"]
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T1")


def test_t1_passes_on_the_real_gross_figures(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["ORCL"], client=client, source_map=source_map)
    assert _statuses(outcome, "T1") == {PASS}


def test_t2_detects_the_trailing_four_quarters_table(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["ORCL"], client=client, source_map=source_map)
    t2 = _by_id(outcome, "T2")
    assert t2 and "TRAILING FOUR-QUARTERS" in t2[0].message.upper()
    assert "48,250" in t2[0].message or "48250" in t2[0].message.replace(",", "")


# ---------------------------------------------------------------------------
# T6 -- Amazon gross vs net
# ---------------------------------------------------------------------------


def test_t6_fails_on_amazons_net_cash_capex(replay_extractions, client, source_map):
    """$53.076B is Amazon's own MD&A figure -- and the wrong one for this model."""
    tampered = _tamper(replay_extractions, "AMZN", "capex_fact", value_usd=53_076_000_000.0)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    failures = [r for r in _by_id(outcome, "T6") if r.status == FAIL]
    assert failures
    assert "GROSS" in failures[0].message


def test_t6_fails_on_the_more_familiar_ppe_concept(replay_extractions, client, source_map):
    tampered = _tamper(
        replay_extractions, "AMZN", "capex_fact",
        concepts=["us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"],
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T6")


def test_t6_passes_and_quantifies_the_gross_net_gap(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["AMZN"], client=client, source_map=source_map)
    passes = [r for r in _by_id(outcome, "T6") if r.status == PASS]
    assert len(passes) == 2
    gap = [r for r in passes if "net_usd" in r.evidence][0]
    assert gap.evidence["gross_usd"] == 54_208_000_000
    assert round(gap.evidence["net_usd"]) == 53_076_000_000


# ---------------------------------------------------------------------------
# T7 -- Meta's dual-range guidance sentence
# ---------------------------------------------------------------------------


def test_t7_detects_both_the_current_and_the_superseded_range(
    replay_extractions, client, source_map
):
    outcome = run_guards(replay_extractions["META"], client=client, source_map=source_map)
    t7 = _by_id(outcome, "T7")
    assert t7 and t7[0].status == NEEDS_HUMAN
    ranges = t7[0].evidence["capex_ranges"]
    assert [("130", "145"), ("125", "145")] == [tuple(r) for r in ranges], ranges
    assert [("165", "169")] == [tuple(r) for r in t7[0].evidence["expense_ranges"]]


# ---------------------------------------------------------------------------
# T8 -- a year-to-date figure is never a quarter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker,ytd_value", [("GOOG", 80_598_000_000.0), ("ORCL", 55_663_000_000.0)])
def test_t8_fails_when_a_ytd_figure_is_emitted_as_a_quarter(
    ticker, ytd_value, replay_extractions, client, source_map
):
    tampered = _tamper(replay_extractions, ticker, "capex_fact", value_usd=ytd_value)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T8")


def test_t8_fails_when_a_directly_tagged_duration_is_not_a_quarter(
    replay_extractions, client, source_map
):
    tampered = copy.deepcopy(replay_extractions["AMZN"])
    tampered.fields["capex_fact"].components = [
        {"start": "2026-01-01", "end": "2026-06-30", "val": 98_411_000_000.0}
    ]
    tampered.fields["capex_fact"].value_usd = 98_411_000_000.0
    outcome = run_guards(tampered, client=client, source_map=source_map)
    failures = [r for r in _by_id(outcome, "T8") if r.status == FAIL]
    assert failures and "180 days" in failures[0].message


# ---------------------------------------------------------------------------
# T9 / T11 -- the wrong big number
# ---------------------------------------------------------------------------


def test_t9_fails_when_the_demand_fact_is_a_contractual_obligation(
    replay_extractions, client, source_map
):
    """Amazon's us-gaap:ContractualObligation is $650B -- what Amazon OWES."""
    doc = replay_extractions["AMZN"]._ixbrl
    obligations = [
        f.value
        for f in doc.by_concept("us-gaap:ContractualObligation")
        if f.context.instant == "2026-06-30"
    ]
    assert obligations, "expected a contractual-obligation fact in Amazon's 10-Q"
    tampered = _tamper(replay_extractions, "AMZN", "demand_fact", value_usd=obligations[0])
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T9")


def test_t11_fails_when_amazons_capex_plan_is_actually_its_net_sales(
    replay_extractions, client, source_map
):
    tampered = _tamper(
        replay_extractions, "AMZN", "annual_denominator",
        status="extracted", value_usd=200_600_000_000.0,
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T11")


# ---------------------------------------------------------------------------
# T12 -- MSFT and META mean different things by "including finance leases"
# ---------------------------------------------------------------------------


def test_t12_fails_if_metas_formula_uses_microsofts_finance_lease_concept(
    replay_extractions, client, source_map
):
    tampered = _tamper(
        replay_extractions, "META", "capex_fact",
        concepts=[
            "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
            "us-gaap:RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability",
        ],
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T12")


def test_t12_fails_if_metas_finance_lease_component_is_dropped(
    replay_extractions, client, source_map
):
    tampered = _tamper(
        replay_extractions, "META", "capex_fact",
        concepts=["us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"],
    )
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T12")


# ---------------------------------------------------------------------------
# T13 -- Oracle's period ends
# ---------------------------------------------------------------------------


def test_t13_fails_if_oracle_is_queried_at_a_calendar_quarter_end(
    replay_extractions, client, source_map
):
    extraction = copy.deepcopy(replay_extractions["ORCL"])
    extraction.period = dataclasses.replace(extraction.period, period_end="2026-06-30")
    outcome = run_guards(extraction, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "T13")


def test_t13_flags_oracles_one_month_timing_mismatch(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["ORCL"], client=client, source_map=source_map)
    t13 = _by_id(outcome, "T13")
    assert t13[0].status == INFO and "one-month timing mismatch" in t13[0].message


# ---------------------------------------------------------------------------
# T3 / T5 / T14 -- comparability language the pipeline can flag but not resolve
# ---------------------------------------------------------------------------


def test_t3_always_asks_a_human_about_microsofts_outlook(
    replay_extractions, client, source_map
):
    outcome = run_guards(replay_extractions["MSFT"], client=client, source_map=source_map)
    t3 = _by_id(outcome, "T3")
    assert t3 and t3[0].status == NEEDS_HUMAN and "useful lives" in t3[0].message


def test_t5_detects_alphabets_expanded_backlog_definition(
    replay_extractions, client, source_map
):
    outcome = run_guards(replay_extractions["GOOG"], client=client, source_map=source_map)
    t5 = _by_id(outcome, "T5")
    assert t5 and t5[0].evidence["definition_version"] == "2026-expanded"


def test_t5_asks_a_human_when_the_definition_language_disappears(
    replay_extractions, client, source_map
):
    extraction = copy.deepcopy(replay_extractions["GOOG"])
    extraction._primary_text = "no such language here"
    extraction._exhibit_text = ""
    outcome = run_guards(extraction, client=client, source_map=source_map)
    assert NEEDS_HUMAN in _statuses(outcome, "T5")


def test_t14_flags_oracles_prepaid_hardware_comparability(
    replay_extractions, client, source_map
):
    outcome = run_guards(replay_extractions["ORCL"], client=client, source_map=source_map)
    t14 = _by_id(outcome, "T14")
    assert t14 and t14[0].status == NEEDS_HUMAN and "prepaid" in t14[0].message.lower()


# ---------------------------------------------------------------------------
# R1 / R2 -- sequential-move sanity
# ---------------------------------------------------------------------------


def test_r2_needs_a_human_for_metas_57pct_capex_jump(
    replay_extractions, client, source_map
):
    """This one fires on the REAL data, which is the point of the check."""
    outcome = run_guards(replay_extractions["META"], client=client, source_map=source_map)
    r2 = _by_id(outcome, "R2")
    assert r2 and r2[0].status == NEEDS_HUMAN
    assert r2[0].evidence["ratio"] > 1 + SEQUENTIAL_MOVE_THRESHOLDS["capex_fact"]["needs_human_pct"]


def test_r2_fails_on_an_implausible_capex_jump(replay_extractions, client, source_map):
    tampered = _tamper(replay_extractions, "GOOG", "capex_fact", value_usd=400_000_000_000.0)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "R2")


def test_r1_fails_on_an_implausible_demand_collapse(replay_extractions, client, source_map):
    tampered = _tamper(replay_extractions, "GOOG", "demand_fact", value_usd=5_000_000_000.0)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "R1")


def test_r3_fails_on_an_absurd_magnitude(replay_extractions, client, source_map):
    tampered = _tamper(replay_extractions, "GOOG", "demand_fact", value_usd=519.5)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "R3")


# ---------------------------------------------------------------------------
# Structural guards
# ---------------------------------------------------------------------------


def test_s2_fails_when_the_filing_has_not_landed(replay_extractions, client, source_map):
    extraction = copy.deepcopy(replay_extractions["ORCL"])
    extraction.periodic_filing = None
    outcome = run_guards(extraction, client=client, source_map=source_map)
    failures = [r for r in _by_id(outcome, "S2") if r.status == FAIL]
    assert failures and "12 days" in failures[0].message


def test_s1_fails_when_the_resolved_period_contradicts_the_spec(
    replay_extractions, client, source_map
):
    extraction = copy.deepcopy(replay_extractions["MSFT"])
    extraction.period = dataclasses.replace(extraction.period, source_map_agrees=False)
    outcome = run_guards(extraction, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "S1")


def test_s5_blocks_on_every_refused_manual_field(replay_extractions, client, source_map):
    outcome = run_guards(replay_extractions["MSFT"], client=client, source_map=source_map)
    s5 = _by_id(outcome, "S5")
    assert len(s5) == 2 and all(r.status == NEEDS_HUMAN for r in s5)


def test_s5_fails_if_a_manual_field_is_ever_auto_populated(
    replay_extractions, client, source_map
):
    tampered = _tamper(replay_extractions, "MSFT", "capex_fact", value_usd=41_000_000_000.0)
    outcome = run_guards(tampered, client=client, source_map=source_map)
    assert FAIL in _statuses(outcome, "S5")


def test_no_guard_fails_on_the_real_quarter(replay_extractions, client, source_map):
    """The replay must be clean: blocking items are human confirmations, not errors."""
    for ticker, extraction in replay_extractions.items():
        outcome = run_guards(extraction, client=client, source_map=source_map)
        assert not outcome.failures, (
            ticker,
            [(r.id, r.name, r.message[:160]) for r in outcome.failures],
        )
