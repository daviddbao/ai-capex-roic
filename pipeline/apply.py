"""Append an APPROVED packet to ``data/``, idempotently, then diff the model.

Approval is an act, not a flag
------------------------------
There is deliberately **no ``--approve`` / ``--yes`` option**. A packet is
applied only if its companion ``*.approval.json`` is filled in and saved by a
named reviewer, and only if:

* ``decision`` is ``APPROVED`` and ``reviewer`` / ``reviewed_at`` are set;
* ``packet_sha256`` matches the packet's own content hash -- so the signature
  binds to the exact numbers that were reviewed, and re-drafting with a
  different value invalidates it;
* no guard is ``FAIL`` (a FAIL cannot be acknowledged away);
* every ``NEEDS_HUMAN`` guard has a non-empty acknowledgement sentence;
* every refused manual field has a value and a source URL.

Idempotence
-----------
Re-running is safe. If the company-quarter is already in ``data/facts.csv``
with the same values, nothing is written. If it is present with DIFFERENT
values, the run is refused -- rewriting history is a human decision, not an
append.

Scope
-----
This module writes ``data/facts.csv`` and ``data/sources.csv`` only.
``data/assumptions.csv`` holds the annual capex denominators and is the
*versioned* table: per ``docs/SCHEMA.md`` §2 a change there must be appended as
a new row with a later ``effective_from``, never edited in place. So an
approved annual denominator is reported here as a required follow-up rather
than written automatically.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .dataio import (
    ASSUMPTIONS_CSV,
    FACTS_COLUMNS,
    FACTS_CSV,
    SOURCES_COLUMNS,
    SOURCES_CSV,
    append_rows,
    read_csv,
    source_id_for,
)
from .draft import packet_content_hash
from .guards import FAIL, NEEDS_HUMAN

from model import calc
from model.build import QUARTERS_PER_YEAR
from model.calc import CapexView, CompanyInputs, ProxyBasis, Scenario

__all__ = [
    "ApprovalError",
    "validate_approval",
    "facts_row_from_packet",
    "sources_rows_from_packet",
    "apply_packet",
    "model_spreads",
    "render_diff_report",
]


class ApprovalError(RuntimeError):
    """The packet is not validly approved. Nothing is written."""


# ---------------------------------------------------------------------------
# Approval validation
# ---------------------------------------------------------------------------


def validate_approval(
    packet: Mapping[str, Any], approval: Mapping[str, Any]
) -> list[str]:
    """Return the list of reasons this packet may NOT be applied. Empty == OK."""
    problems: list[str] = []

    if str(approval.get("decision", "")).strip().upper() != "APPROVED":
        problems.append(
            f"approval.decision is {approval.get('decision')!r}, not 'APPROVED'. "
            "A packet is applied only by an explicit recorded decision."
        )
    if not str(approval.get("reviewer", "")).strip():
        problems.append("approval.reviewer is empty: an approval must name a person.")
    reviewed_at = str(approval.get("reviewed_at", "")).strip()
    if not reviewed_at:
        problems.append("approval.reviewed_at is empty.")
    else:
        try:
            date.fromisoformat(reviewed_at[:10])
        except ValueError:
            problems.append(f"approval.reviewed_at {reviewed_at!r} is not an ISO date.")

    recomputed = packet_content_hash(packet)
    signed = str(approval.get("packet_sha256", "")).strip()
    if not signed:
        problems.append(
            "approval.packet_sha256 is empty. Paste the packet's content hash so the "
            "approval binds to the exact values reviewed."
        )
    elif signed != recomputed:
        problems.append(
            f"approval.packet_sha256 {signed[:16]}... does not match the packet's content hash "
            f"{recomputed[:16]}.... The proposed values changed after the packet was signed. "
            "Re-review and re-sign."
        )
    if packet.get("packet_sha256") and packet["packet_sha256"] != recomputed:
        problems.append(
            "The packet file's stored packet_sha256 does not match its own content. "
            "The packet has been edited by hand; re-draft it."
        )

    guards = packet.get("guards", [])
    failures = [g for g in guards if g["status"] == FAIL]
    for g in failures:
        problems.append(
            f"guard {g['id']} FAILED and cannot be acknowledged away: {g['name']} — {g['message'][:220]}"
        )
    acknowledgements = approval.get("acknowledgements") or {}
    for g in guards:
        if g["status"] != NEEDS_HUMAN:
            continue
        text = str(acknowledgements.get(g["id"], "")).strip()
        if not text:
            problems.append(
                f"guard {g['id']} ({g['name']}) needs a human and has no acknowledgement in "
                "approval.acknowledgements."
            )

    manual_values = approval.get("manual_values") or {}
    manual_sources = approval.get("manual_value_sources") or {}
    for item in packet.get("manual_required", []):
        key = f"{item['field']}_usd_b"
        value = manual_values.get(key)
        if value is None or str(value).strip() == "":
            problems.append(
                f"manual field {item['field']} ({item['label']}) has no value in "
                f"approval.manual_values.{key}. The pipeline refuses to guess it."
            )
            continue
        try:
            float(value)
        except (TypeError, ValueError):
            problems.append(f"approval.manual_values.{key} = {value!r} is not a number.")
        if not str(manual_sources.get(f"{item['field']}_source_url", "")).strip():
            problems.append(
                f"manual field {item['field']} has no source URL in "
                f"approval.manual_value_sources.{item['field']}_source_url."
            )
    return problems


# ---------------------------------------------------------------------------
# Row construction
# ---------------------------------------------------------------------------


def _manual(approval: Mapping[str, Any], field: str, suffix: str = "_usd_b") -> Any:
    return (approval.get("manual_values") or {}).get(f"{field}{suffix}")


def _manual_source(approval: Mapping[str, Any], field: str) -> str:
    return str((approval.get("manual_value_sources") or {}).get(f"{field}_source_url", ""))


def _manual_quote(approval: Mapping[str, Any], field: str) -> str:
    return str((approval.get("manual_value_evidence") or {}).get(f"{field}_quote", ""))


def _round_b(value_usd: float) -> float:
    """USD -> $B at the precision ``data/facts.csv`` uses (no rounding noise)."""
    b = value_usd / 1e9
    return round(b, 6)


def facts_row_from_packet(
    packet: Mapping[str, Any], approval: Mapping[str, Any]
) -> dict[str, Any]:
    """The single ``data/facts.csv`` row this packet proposes."""
    fields = packet["fields"]
    demand = fields["demand_fact"]
    capex = fields["capex_fact"]
    key = packet["model_period_key"]

    if demand["status"] == "extracted":
        demand_value = _round_b(demand["value_usd"])
        demand_url = demand["source_url"]
        demand_evidence = demand["evidence_quote"] or demand["derivation"]
    else:
        demand_value = float(_manual(approval, "demand_fact"))
        demand_url = _manual_source(approval, "demand_fact")
        demand_evidence = _manual_quote(approval, "demand_fact")

    if capex["status"] == "extracted":
        capex_value = _round_b(capex["value_usd"])
        capex_url = capex["source_url"]
        capex_evidence = capex["evidence_quote"] or capex["derivation"]
    else:
        capex_value = float(_manual(approval, "capex_fact"))
        capex_url = _manual_source(approval, "capex_fact")
        capex_evidence = _manual_quote(approval, "capex_fact")

    evidence = (
        f"Fact: {demand_evidence} "
        f"[{demand['automation_tier']}/{demand['access']}; {demand['derivation'] or 'human-sourced'}] "
        f"Capex: {capex_evidence} "
        f"[{capex['automation_tier']}/{capex['access']}; {capex['derivation'] or 'human-sourced'}] "
        f"Approved by {approval.get('reviewer')} on {approval.get('reviewed_at')}; "
        f"packet {packet['packet_sha256'][:16]}."
    )

    return {
        "company": packet["company"].replace(", Inc.", "").replace(" Corporation", "").strip()
        or packet["company"],
        "ticker": packet["ticker"],
        "report_bucket": key,
        "fiscal_period": packet["period"]["fiscal_period"],
        "period_end": packet["period"]["period_end"],
        "rpo_backlog_or_revenue_usd_b": demand_value,
        "fact_metric": demand["label"],
        "quarterly_capex_usd_b": capex_value,
        "capex_definition": capex["label"],
        "fact_source_url": demand_url,
        "capex_source_url": capex_url,
        "evidence_derivation": evidence,
        "fact_source_id": source_id_for(packet["ticker"], key, "FACT"),
        "capex_source_id": source_id_for(packet["ticker"], key, "CAPEX"),
    }


def sources_rows_from_packet(
    packet: Mapping[str, Any], approval: Mapping[str, Any], facts_row: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """The two ``data/sources.csv`` ledger rows for this company-quarter."""
    key = packet["model_period_key"]
    period_label = f"{packet['period']['fiscal_period']} / {packet['period']['period_end']}"
    local_by_url = {a["url"]: a["repo_relative_path"] for a in packet.get("archived_sources", [])}
    rows = []
    for kind, field_name, value_col, url_col in (
        ("FACT", "demand_fact", "rpo_backlog_or_revenue_usd_b", "fact_source_url"),
        ("CAPEX", "capex_fact", "quarterly_capex_usd_b", "capex_source_url"),
    ):
        f = packet["fields"][field_name]
        url = facts_row[url_col]
        document = url.rsplit("/", 1)[-1] if url else ""
        rows.append(
            {
                "source_id": source_id_for(packet["ticker"], key, kind),
                "url": url,
                "company": packet["company"],
                "period": period_label,
                "kind": kind.lower(),
                "title_or_description": f"{document} — {f['label']}",
                "local_path_if_any": local_by_url.get(url, ""),
                "reported_value": facts_row[value_col],
                "classification": (
                    "SEC filing"
                    if f["access"] != "not_in_xbrl"
                    else "Official company disclosure (not in SEC XBRL)"
                ),
                "evidence_derivation": (
                    f["evidence_quote"] or _manual_quote(approval, field_name) or f["derivation"]
                ),
                "status": "Verified" if f["status"] == "extracted" else "Verified / human-sourced",
                "caveat": f["label"],
                "in_workbook_ledger": "no",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Model recompute + diff
# ---------------------------------------------------------------------------


def _quarter_sort_key(model_period_key: str) -> tuple[int, int]:
    quarter, yy = model_period_key.split()
    return (int(yy), int(quarter[1]))


def _company_inputs(
    fact_row: Mapping[str, str], assumption_row: Mapping[str, str]
) -> CompanyInputs:
    duration_raw = assumption_row.get("rpo_duration_years", "").strip()
    duration = float(duration_raw) if duration_raw else None
    basis = (
        ProxyBasis.REVENUE
        if "quarterly revenue" in assumption_row.get("ai_revenue_proxy", "").lower()
        else ProxyBasis.RPO
    )
    return CompanyInputs(
        ticker=fact_row["ticker"],
        proxy_basis=basis,
        fact_value_b=float(fact_row["rpo_backlog_or_revenue_usd_b"]),
        quarterly_capex_b=float(fact_row["quarterly_capex_usd_b"]),
        annual_capex_guide_b=float(assumption_row["annual_capex_guide_midpoint_actual_usd_b"]),
        ai_share_of_fact=float(assumption_row["ai_share_of_rpo_revenue"]),
        rpo_duration_years=duration if basis is ProxyBasis.RPO else None,
        ai_share_of_capex=float(assumption_row["ai_share_of_capex"]),
        nopat_margin_bear=float(assumption_row["nopat_margin_bear"]),
        nopat_margin_base=float(assumption_row["nopat_margin_base"]),
        nopat_margin_bull=float(assumption_row["nopat_margin_bull"]),
        wacc=float(assumption_row["wacc"]),
    )


def model_spreads(
    facts_csv: Path | str = FACTS_CSV, assumptions_csv: Path | str = ASSUMPTIONS_CSV
) -> dict[str, Any]:
    """Recompute the model from the DATA LAYER using ``model.calc``.

    ``model/build.py`` reads the workbook, which by design does not carry newly
    appended quarters; ``docs/SCHEMA.md`` makes the data layer the source of
    truth, so the recompute is driven from ``data/*.csv`` through the same pure
    calculation kernel that the workbook parity tests cover.
    """
    assumptions = {row["ticker"]: row for row in read_csv(assumptions_csv)}
    per_ticker: dict[str, dict[str, Any]] = {}
    for row in read_csv(facts_csv):
        ticker = row["ticker"]
        assumption = assumptions.get(ticker)
        if assumption is None:
            continue
        inputs = _company_inputs(row, assumption)
        trajectory = calc.scenario_result(inputs, CapexView.TRAJECTORY, Scenario.BASE)
        snapshot = calc.scenario_result(inputs, CapexView.SNAPSHOT, Scenario.BASE)
        per_ticker.setdefault(ticker, {"quarters": {}})["quarters"][row["report_bucket"]] = {
            "fact_value_b": inputs.fact_value_b,
            "quarterly_capex_b": inputs.quarterly_capex_b,
            "ai_revenue_proxy_b": trajectory["ai_revenue_proxy_b"],
            "ai_capex_b": trajectory["ai_capex_b"],
            "forward_roic": trajectory["forward_roic"],
            "spread": trajectory["spread"],
            "snapshot_spread": snapshot["spread"],
            "wacc": inputs.wacc,
        }
    for ticker, data in per_ticker.items():
        keys = sorted(data["quarters"], key=_quarter_sort_key)
        data["ordered_quarters"] = keys
        data["latest_quarter"] = keys[-1] if keys else None
        data["base_quarter"] = keys[0] if keys else None
        if not keys:
            continue

        latest = data["quarters"][keys[-1]]["spread"]
        data["latest_spread"] = latest

        # Three distinct comparisons, mirroring model.build.build_snapshot. The
        # versus-oldest and year-over-year reads coincide only while the series
        # is exactly QUARTERS_PER_YEAR + 1 long; they diverge on the next append.
        def anchor(back: int) -> str | None:
            index = len(keys) - 1 - back
            return keys[index] if index >= 0 else None

        yoy_quarter = anchor(QUARTERS_PER_YEAR)
        qoq_quarter = anchor(1)
        data["yoy_quarter"] = yoy_quarter
        data["qoq_quarter"] = qoq_quarter

        data["delta_spread_bps"] = calc.basis_points(
            latest - data["quarters"][keys[0]]["spread"]
        )
        data["delta_spread_yoy_bps"] = (
            calc.basis_points(latest - data["quarters"][yoy_quarter]["spread"])
            if yoy_quarter
            else None
        )
        data["delta_spread_qoq_bps"] = (
            calc.basis_points(latest - data["quarters"][qoq_quarter]["spread"])
            if qoq_quarter
            else None
        )
    return per_ticker


def render_diff_report(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    packet: Mapping[str, Any],
    approval: Mapping[str, Any],
    appended: bool,
) -> str:
    """Markdown diff showing how every company's spread moved, and why."""
    out: list[str] = []
    a = out.append
    a(f"# Refresh diff — {packet['ticker']} {packet['model_period_key']}")
    a("")
    a(f"- Applied at: `{datetime.now(timezone.utc).isoformat(timespec='seconds')}`")
    a(f"- Reviewer: **{approval.get('reviewer')}** on `{approval.get('reviewed_at')}`")
    a(f"- Packet hash: `{packet['packet_sha256']}`")
    a(f"- Row appended: **{'yes' if appended else 'no (already present, values identical)'}**")
    a("")
    a("Spreads are decimals; multiply by 100 for percentage points. Run-rate spread uses the "
      "quarter's capex annualised; the snapshot spread uses the annual capex denominator from "
      "`data/assumptions.csv`, which this pipeline does not modify.")
    a("")
    a("| Company | Latest quarter (before → after) | Run-rate spread before | after | Δ ppt | "
      "QoQ (bps) | YoY (bps) | vs baseline (bps) |")
    a("|---|---|---|---|---|---|---|---|")

    def bps_cell(data: Mapping[str, Any], key: str, quarter_key: str) -> str:
        """Signed bps plus the quarter it is measured against, or an explicit n/a."""
        value = data.get(key)
        if value is None:
            return "n/a"
        against = data.get(quarter_key)
        return f"{value:+,.1f}" + (f" *(vs {against})*" if against else "")

    for ticker in sorted(set(before) | set(after)):
        b = before.get(ticker, {})
        f = after.get(ticker, {})
        b_latest, f_latest = b.get("latest_quarter"), f.get("latest_quarter")
        b_spread, f_spread = b.get("latest_spread"), f.get("latest_spread")
        if b_spread is None or f_spread is None:
            a(f"| {ticker} | {b_latest} → {f_latest} | — | — | — | — | — | — |")
            continue
        delta_ppt = (f_spread - b_spread) * 100
        a(
            f"| {ticker} | {b_latest} → {f_latest} | {b_spread*100:,.2f} ppt | "
            f"{f_spread*100:,.2f} ppt | {delta_ppt:+,.2f} | "
            f"{bps_cell(f, 'delta_spread_qoq_bps', 'qoq_quarter')} | "
            f"{bps_cell(f, 'delta_spread_yoy_bps', 'yoy_quarter')} | "
            f"{bps_cell(f, 'delta_spread_bps', 'base_quarter')} |"
        )
    a("")
    a("QoQ and YoY roll forward with the series; the baseline column is measured against the "
      "oldest quarter on file and is fixed. All three are run-rate spreads.")
    a("")

    ticker = packet["ticker"]
    a("## Why this company moved")
    a("")
    f = after.get(ticker, {})
    b = before.get(ticker, {})
    if f.get("latest_quarter") and b.get("latest_quarter"):
        new = f["quarters"][f["latest_quarter"]]
        old = b["quarters"][b["latest_quarter"]]
        a(f"- Demand fact: {old['fact_value_b']:,.3f} → **{new['fact_value_b']:,.3f}** $B "
          f"({(new['fact_value_b']/old['fact_value_b'] - 1):+.1%})")
        a(f"- Quarterly capex: {old['quarterly_capex_b']:,.3f} → **{new['quarterly_capex_b']:,.3f}** $B "
          f"({(new['quarterly_capex_b']/old['quarterly_capex_b'] - 1):+.1%})")
        a(f"- Annualised AI revenue proxy: {old['ai_revenue_proxy_b']:,.3f} → "
          f"**{new['ai_revenue_proxy_b']:,.3f}** $B")
        a(f"- Annualised AI capex: {old['ai_capex_b']:,.3f} → **{new['ai_capex_b']:,.3f}** $B")
        a(f"- Forward ROIC (base): {old['forward_roic']*100:,.2f}% → **{new['forward_roic']*100:,.2f}%** "
          f"against a WACC of {new['wacc']*100:,.2f}%")
    a("")
    a("The other four companies move only if their own rows changed; assumptions are held constant "
      "by design so that period-over-period movements stay comparable.")
    a("")

    denominators = [i for i in packet.get("manual_required", []) if i["field"] == "annual_denominator"]
    if denominators:
        value = _manual(approval, "annual_denominator")
        a("## Required follow-up — `data/assumptions.csv`")
        a("")
        a(f"The approved annual capex denominator for {ticker} is **${float(value):,.3f}B** "
          f"(source: {_manual_source(approval, 'annual_denominator')}).")
        a("")
        a("`data/assumptions.csv` is the VERSIONED table: per `docs/SCHEMA.md` §2 a changed "
          "assumption must be appended as a NEW ROW with a later `effective_from`, never edited "
          "in place. This pipeline does not write that file. Append the row by hand if the "
          "denominator has changed, then re-run the model.")
        a("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


@dataclass
class ApplyResult:
    """Outcome of one apply run."""

    appended: bool
    reason: str
    facts_row: dict[str, Any]
    diff_report: str
    diff_report_path: Path | None


def _rows_equal(existing: Mapping[str, str], proposed: Mapping[str, Any]) -> list[str]:
    """Material differences between an on-file row and a proposed one."""
    material = (
        "period_end",
        "rpo_backlog_or_revenue_usd_b",
        "quarterly_capex_usd_b",
        "fiscal_period",
    )
    differences = []
    for column in material:
        old = str(existing.get(column, "")).strip()
        new = str(proposed.get(column, "")).strip()
        try:
            if abs(float(old) - float(new)) < 1e-9:
                continue
        except ValueError:
            if old == new:
                continue
        differences.append(f"{column}: on file {old!r}, packet proposes {new!r}")
    return differences


def apply_packet(
    packet_path: Path | str,
    approval_path: Path | str | None = None,
    facts_csv: Path | str = FACTS_CSV,
    sources_csv: Path | str = SOURCES_CSV,
    assumptions_csv: Path | str = ASSUMPTIONS_CSV,
    diff_dir: Path | str | None = None,
) -> ApplyResult:
    """Validate, append (idempotently), recompute, and write a diff report.

    Raises:
        ApprovalError: the packet is not validly approved, or the same
            company-quarter is already on file with different values.
    """
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    approval_path = Path(approval_path) if approval_path else packet_path.with_suffix(".approval.json")
    if not approval_path.exists():
        raise ApprovalError(
            f"No approval file at {approval_path}. A packet is applied only with a signed-off "
            "approval file; there is no flag that substitutes for one."
        )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))

    problems = validate_approval(packet, approval)
    if problems:
        raise ApprovalError(
            "Packet is NOT approved for application:\n  - " + "\n  - ".join(problems)
        )

    facts_row = facts_row_from_packet(packet, approval)
    before = model_spreads(facts_csv, assumptions_csv)

    existing = [
        row
        for row in read_csv(facts_csv)
        if row["ticker"] == facts_row["ticker"] and row["report_bucket"] == facts_row["report_bucket"]
    ]
    if existing:
        differences = _rows_equal(existing[0], facts_row)
        if differences:
            raise ApprovalError(
                f"{facts_row['ticker']} {facts_row['report_bucket']} is already in {facts_csv} with "
                "DIFFERENT values:\n  - " + "\n  - ".join(differences)
                + "\nAppending would duplicate the row and rewriting history is not an append. "
                "Resolve by hand."
            )
        appended, reason = False, "already on file with identical values — no-op (idempotent)"
    else:
        append_rows(facts_csv, [facts_row], FACTS_COLUMNS)
        existing_source_ids = {row["source_id"] for row in read_csv(sources_csv)}
        source_rows = [
            row
            for row in sources_rows_from_packet(packet, approval, facts_row)
            if row["source_id"] not in existing_source_ids
        ]
        if source_rows:
            append_rows(sources_csv, source_rows, SOURCES_COLUMNS)
        appended, reason = True, f"appended 1 fact row and {len(source_rows)} source row(s)"

    after = model_spreads(facts_csv, assumptions_csv)
    report = render_diff_report(before, after, packet, approval, appended)

    report_path: Path | None = None
    if diff_dir is not None:
        report_dir = Path(diff_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{packet['ticker']}-{packet['report_bucket']}-diff.md"
        report_path.write_text(report, encoding="utf-8")

    return ApplyResult(appended, reason, facts_row, report, report_path)


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    """``python -m pipeline.apply pipeline/packets/CY2026Q3/GOOG.json``."""
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv:
        print("usage: python -m pipeline.apply <packet.json> [approval.json]")
        return 2
    packet_path = Path(argv[0])
    approval_path = Path(argv[1]) if len(argv) > 1 else None
    try:
        result = apply_packet(
            packet_path,
            approval_path,
            diff_dir=packet_path.parent / "diffs",
        )
    except ApprovalError as exc:
        print(f"REFUSED — {exc}")
        return 1
    print(f"{result.reason}")
    if result.diff_report_path:
        print(f"diff report: {result.diff_report_path}")
    print()
    print(result.diff_report)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
