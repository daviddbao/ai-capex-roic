"""Approval gating, idempotence and the recompute diff.

Every test here works on a TEMPORARY COPY of ``data/``. Nothing in this file
writes to the real data layer.
"""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest

from pipeline import REPO_ROOT
from pipeline.apply import (
    ApprovalError,
    apply_packet,
    facts_row_from_packet,
    model_spreads,
    validate_approval,
)
from pipeline.draft import approval_template, build_packet, packet_content_hash

REPLAY_BUCKET = "CY2026Q2"


@pytest.fixture
def temp_data(tmp_path: Path) -> dict[str, Path]:
    """A throwaway copy of the data layer."""
    folder = tmp_path / "data"
    folder.mkdir()
    for name in ("facts.csv", "sources.csv", "assumptions.csv"):
        shutil.copy(REPO_ROOT / "data" / name, folder / name)
    return {
        "facts": folder / "facts.csv",
        "sources": folder / "sources.csv",
        "assumptions": folder / "assumptions.csv",
    }


@pytest.fixture(scope="session")
def goog_packet(client, source_map, tmp_path_factory) -> dict:
    """A real GOOG packet for the replayed quarter, archived nowhere."""
    return build_packet(
        "GOOG", REPLAY_BUCKET, client=client, source_map=source_map, archive=False
    )


@pytest.fixture(scope="session")
def msft_packet(client, source_map) -> dict:
    """Microsoft, whose quarterly capex is the one permanently manual core fact."""
    return build_packet(
        "MSFT", REPLAY_BUCKET, client=client, source_map=source_map, archive=False
    )


def _signed_approval(packet: dict, **overrides) -> dict:
    approval = approval_template(packet)
    approval["decision"] = "APPROVED"
    approval["reviewer"] = "A. Reviewer"
    approval["reviewed_at"] = "2026-08-31"
    approval["packet_sha256"] = packet["packet_sha256"]
    for key in approval["acknowledgements"]:
        approval["acknowledgements"][key] = "Read the filing; confirmed."
    for item in packet["manual_required"]:
        approval["manual_values"][f"{item['field']}_usd_b"] = 41.0
        approval["manual_value_sources"][f"{item['field']}_source_url"] = item["where_to_look"]
        approval["manual_value_evidence"][f"{item['field']}_quote"] = "CFO prepared remarks."
    approval.update(overrides)
    return approval


# ---------------------------------------------------------------------------
# The packet is a proposal, not a commitment
# ---------------------------------------------------------------------------


def test_a_freshly_drafted_packet_is_not_approved(goog_packet):
    assert goog_packet["approval"]["status"] == "DRAFT — UNAPPROVED"
    blank = approval_template(goog_packet)
    assert blank["decision"] == "PENDING"
    problems = validate_approval(goog_packet, blank)
    assert problems and any("not 'APPROVED'" in p for p in problems)


def test_approval_requires_a_named_reviewer_and_a_date(goog_packet):
    approval = _signed_approval(goog_packet, reviewer="", reviewed_at="")
    problems = validate_approval(goog_packet, approval)
    assert any("reviewer is empty" in p for p in problems)
    assert any("reviewed_at is empty" in p for p in problems)


def test_signature_binds_to_the_exact_values_reviewed(goog_packet):
    approval = _signed_approval(goog_packet)
    assert validate_approval(goog_packet, approval) == []

    changed = copy.deepcopy(goog_packet)
    changed["fields"]["capex_fact"]["value_usd"] = 44_000_000_000.0
    changed["packet_sha256"] = packet_content_hash(changed)
    problems = validate_approval(changed, approval)
    assert any("does not match the packet's content hash" in p for p in problems)


def test_a_hand_edited_packet_is_rejected(goog_packet):
    tampered = copy.deepcopy(goog_packet)
    tampered["fields"]["demand_fact"]["value_usd"] = 999_000_000_000.0
    approval = _signed_approval(goog_packet)
    problems = validate_approval(tampered, approval)
    assert any("edited by hand" in p for p in problems)


def test_a_failing_guard_cannot_be_acknowledged_away(goog_packet):
    packet = copy.deepcopy(goog_packet)
    packet["guards"].append(
        {
            "id": "T4",
            "name": "invented failure",
            "ticker": "GOOG",
            "field": "demand_fact",
            "status": "FAIL",
            "message": "boom",
            "evidence": {},
        }
    )
    packet["guards_summary"]["blocking_ids"] = sorted(
        set(packet["guards_summary"]["blocking_ids"]) | {"T4"}
    )
    packet["packet_sha256"] = packet_content_hash(packet)
    approval = _signed_approval(packet)
    approval["acknowledgements"]["T4"] = "I looked at it, it's fine"
    problems = validate_approval(packet, approval)
    assert any("cannot be acknowledged away" in p for p in problems)


def test_every_needs_human_guard_requires_its_own_sentence(goog_packet):
    approval = _signed_approval(goog_packet)
    first = next(iter(approval["acknowledgements"]))
    approval["acknowledgements"][first] = "   "
    problems = validate_approval(goog_packet, approval)
    assert any(first in p and "no acknowledgement" in p for p in problems)


def test_manual_fields_must_be_supplied_with_a_source(msft_packet):
    assert {i["field"] for i in msft_packet["manual_required"]} == {
        "capex_fact",
        "annual_denominator",
    }
    approval = _signed_approval(msft_packet)
    approval["manual_values"]["capex_fact_usd_b"] = None
    problems = validate_approval(msft_packet, approval)
    assert any("refuses to guess" in p for p in problems)

    approval = _signed_approval(msft_packet)
    approval["manual_value_sources"]["capex_fact_source_url"] = ""
    problems = validate_approval(msft_packet, approval)
    assert any("no source URL" in p for p in problems)


# ---------------------------------------------------------------------------
# Applying
# ---------------------------------------------------------------------------


def _write(tmp_path: Path, packet: dict, approval: dict) -> Path:
    packet_path = tmp_path / f"{packet['ticker']}.json"
    packet_path.write_text(json.dumps(packet, indent=2, default=str), encoding="utf-8")
    (tmp_path / f"{packet['ticker']}.approval.json").write_text(
        json.dumps(approval, indent=2), encoding="utf-8"
    )
    return packet_path


def test_apply_refuses_without_an_approval_file(tmp_path, goog_packet, temp_data):
    packet_path = tmp_path / "GOOG.json"
    packet_path.write_text(json.dumps(goog_packet, default=str), encoding="utf-8")
    with pytest.raises(ApprovalError, match="No approval file"):
        apply_packet(
            packet_path,
            facts_csv=temp_data["facts"],
            sources_csv=temp_data["sources"],
            assumptions_csv=temp_data["assumptions"],
        )


def test_apply_is_a_noop_when_the_row_is_already_on_file(tmp_path, goog_packet, temp_data):
    """The replayed quarter is already in facts.csv; re-applying must not duplicate it."""
    packet_path = _write(tmp_path, goog_packet, _signed_approval(goog_packet))
    before = temp_data["facts"].read_text(encoding="utf-8")
    result = apply_packet(
        packet_path,
        facts_csv=temp_data["facts"],
        sources_csv=temp_data["sources"],
        assumptions_csv=temp_data["assumptions"],
    )
    assert result.appended is False
    assert "idempotent" in result.reason
    assert temp_data["facts"].read_text(encoding="utf-8") == before


def test_apply_refuses_to_rewrite_an_existing_row_with_different_values(
    tmp_path, goog_packet, temp_data
):
    packet = copy.deepcopy(goog_packet)
    packet["fields"]["capex_fact"]["value_usd"] = 44_000_000_000.0
    packet["packet_sha256"] = packet_content_hash(packet)
    packet_path = _write(tmp_path, packet, _signed_approval(packet))
    with pytest.raises(ApprovalError, match="DIFFERENT values"):
        apply_packet(
            packet_path,
            facts_csv=temp_data["facts"],
            sources_csv=temp_data["sources"],
            assumptions_csv=temp_data["assumptions"],
        )


def test_apply_appends_exactly_one_row_and_is_idempotent(tmp_path, goog_packet, temp_data):
    """Move the packet to a period not yet on file, then apply it twice."""
    packet = copy.deepcopy(goog_packet)
    packet["model_period_key"] = "Q3 26"
    packet["report_bucket"] = "CY2026Q3"
    packet["period"] = dict(packet["period"], period_end="2026-09-30", fiscal_period="Q3 2026")
    packet["packet_sha256"] = packet_content_hash(packet)
    packet_path = _write(tmp_path, packet, _signed_approval(packet))

    lines_before = temp_data["facts"].read_text(encoding="utf-8").count("\n")
    first = apply_packet(
        packet_path,
        facts_csv=temp_data["facts"],
        sources_csv=temp_data["sources"],
        assumptions_csv=temp_data["assumptions"],
    )
    assert first.appended is True
    assert temp_data["facts"].read_text(encoding="utf-8").count("\n") == lines_before + 1

    second = apply_packet(
        packet_path,
        facts_csv=temp_data["facts"],
        sources_csv=temp_data["sources"],
        assumptions_csv=temp_data["assumptions"],
    )
    assert second.appended is False
    assert temp_data["facts"].read_text(encoding="utf-8").count("\n") == lines_before + 1


def test_apply_emits_a_diff_report_covering_every_company(tmp_path, goog_packet, temp_data):
    packet = copy.deepcopy(goog_packet)
    packet["model_period_key"] = "Q3 26"
    packet["report_bucket"] = "CY2026Q3"
    packet["period"] = dict(packet["period"], period_end="2026-09-30", fiscal_period="Q3 2026")
    packet["packet_sha256"] = packet_content_hash(packet)
    packet_path = _write(tmp_path, packet, _signed_approval(packet))
    result = apply_packet(
        packet_path,
        facts_csv=temp_data["facts"],
        sources_csv=temp_data["sources"],
        assumptions_csv=temp_data["assumptions"],
        diff_dir=tmp_path / "diffs",
    )
    report = result.diff_report
    for ticker in ("MSFT", "GOOG", "AMZN", "ORCL", "META"):
        assert ticker in report
    assert "Q2 26 → Q3 26" in report
    assert "Why this company moved" in report
    assert result.diff_report_path is not None and result.diff_report_path.exists()


def test_apply_writes_nothing_when_approval_is_invalid(tmp_path, goog_packet, temp_data):
    packet = copy.deepcopy(goog_packet)
    packet["model_period_key"] = "Q3 26"
    packet["report_bucket"] = "CY2026Q3"
    packet["period"] = dict(packet["period"], period_end="2026-09-30")
    packet["packet_sha256"] = packet_content_hash(packet)
    approval = _signed_approval(packet)
    approval["decision"] = "PENDING"
    packet_path = _write(tmp_path, packet, approval)
    before_facts = temp_data["facts"].read_text(encoding="utf-8")
    before_sources = temp_data["sources"].read_text(encoding="utf-8")
    with pytest.raises(ApprovalError):
        apply_packet(
            packet_path,
            facts_csv=temp_data["facts"],
            sources_csv=temp_data["sources"],
            assumptions_csv=temp_data["assumptions"],
        )
    assert temp_data["facts"].read_text(encoding="utf-8") == before_facts
    assert temp_data["sources"].read_text(encoding="utf-8") == before_sources


# ---------------------------------------------------------------------------
# The recompute must agree with the workbook's own cached outputs
# ---------------------------------------------------------------------------


def test_recompute_reproduces_the_workbooks_cached_spreads():
    """Reusing model.calc must reproduce data/expected_outputs.csv exactly."""
    import csv

    spreads = model_spreads()
    with open(REPO_ROOT / "data" / "expected_outputs.csv", encoding="utf-8", newline="") as handle:
        rows = [
            r
            for r in csv.DictReader(handle)
            if r["view"] == "trajectory" and r["metric"] == "Spread vs WACC (ppt)"
        ]
    assert rows
    for row in rows:
        computed = spreads[row["company"]]["quarters"][row["period"]]["spread"]
        assert computed == pytest.approx(float(row["value"]), abs=1e-12), row


def test_facts_row_shape_matches_the_schema(goog_packet):
    from pipeline.dataio import FACTS_COLUMNS

    row = facts_row_from_packet(goog_packet, _signed_approval(goog_packet))
    assert set(row) == set(FACTS_COLUMNS)
    assert row["report_bucket"] == "Q2 26"
    assert row["fact_source_id"] == "GOOG-Q226-FACT"
    assert row["capex_source_id"] == "GOOG-Q226-CAPEX"
    assert row["rpo_backlog_or_revenue_usd_b"] == 519.5
    assert row["quarterly_capex_usd_b"] == 44.924
