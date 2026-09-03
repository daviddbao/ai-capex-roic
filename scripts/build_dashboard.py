"""Regenerate the dashboard's embedded ``DATA`` block from ``data/`` + ``model/``.

The dashboard is a single self-contained page: no fetches, no build-time
templating of the markup. Only one region of it is machine-written --- the
``DATA`` object --- and this script is the only thing that writes it.

    Excel v02  --(534 parity tests)-->  model/calc.py
               --(this script)-------->  embedded expectations
               --(page self-check)---->  the JS the reader sees

What lands in the page
----------------------
``expected``
    The 260 frozen rows of ``data/expected_outputs.csv`` --- the workbook's own
    cached values, anchored to the workbook's five quarters forever.
``computed``
    The same shape of rows, but computed here by :mod:`model.calc` for **every**
    quarter in ``data/facts.csv``. This set grows when the data grows, so a
    sixth quarter arrives verified rather than merely rendered.
``sources``
    All of ``data/sources.csv``, keyed by ``source_id``. The page's derivation
    ledger renders every FACT as a link into this, and every entry links back to
    the figures it supports. A fact row citing an id that is not here, or a plan
    or WACC source of the wrong kind, aborts the build: an unsourced figure on
    this page is a defect, not a cosmetic gap.

Both sets are asserted by the page against its own JavaScript re-implementation
of the model, and reported separately, so a reader can see how much of the page
each one covers.

Before writing anything this script recomputes the 260 frozen rows itself and
refuses to emit a page whose Python model no longer reproduces the workbook.

Usage
-----
    python scripts/build_dashboard.py            # regenerate in place
    python scripts/build_dashboard.py --check    # fail if regeneration would change the file

Never writes to ``data/``, the workbook, or any part of the page outside the
generated markers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model import build  # noqa: E402  (after the repo-root path bootstrap)
from model.build import Assumptions, QuarterFact  # noqa: E402
from model.calc import ProxyBasis  # noqa: E402

__all__ = [
    "BEGIN_MARKER",
    "END_MARKER",
    "build_data",
    "render_block",
    "splice",
    "main",
]

REPO = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO / "data"
DEFAULT_PAGE = REPO / "dashboard" / "index.html"

BEGIN_MARKER = "/* ==== BEGIN GENERATED DATA — scripts/build_dashboard.py ==== */"
END_MARKER = "/* ==== END GENERATED DATA ==== */"

#: Comparison tolerance for the pre-write workbook parity gate.
PARITY_TOL = 1e-9

# ---------------------------------------------------------------------------
# Metric labels
#
# These strings are the join key between this script and the page's own
# recompute(). The page builds the same labels in JS; if either side drifts the
# self-check fails loudly on load, which is the intended behaviour.
# ---------------------------------------------------------------------------

#: Trajectory metric rows 2-6. Row 1 is per-company and derived from the workbook.
TRAJ_METRICS: tuple[tuple[str, str], ...] = (
    ("Quarterly Capex ($B)", "quarterly_capex_b"),
    ("Annualized AI Capex ($B)", "ai_capex_b"),
    ("Annualized AI Revenue Proxy ($B)", "ai_revenue_proxy_b"),
    ("Forward ROIC (Base)", "forward_roic"),
    ("Spread vs WACC (ppt)", "spread"),
)

RUNRATE_SPREAD_LABEL = "Spread {q} (run-rate basis, ppt)"
WORKBOOK_DELTA_LABEL = "Δ Spread {latest} vs {prior} (bps)"
QOQ_LABEL = "Δ Spread QoQ ({latest} vs {prior}, bps)"
YOY_LABEL = "Δ Spread YoY ({latest} vs {prior}, bps)"
BASELINE_LABEL = "Δ Spread vs baseline ({latest} vs {prior}, bps)"

_MONTHS = (
    "Jan.", "Feb.", "Mar.", "Apr.", "May.", "Jun.",
    "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.",
)


def _workbook_date(period_end) -> str:
    """The workbook's own date rendering, e.g. ``Jun. 30, 2026``."""
    return f"{_MONTHS[period_end.month - 1]} {period_end.day}, {period_end.year}"


def _num(value: float) -> str:
    """Full-precision, round-trippable text for an embedded numeric expectation."""
    return repr(float(value))


# ---------------------------------------------------------------------------
# Reading the living data layer
# ---------------------------------------------------------------------------


def _resolve_assumption_rows(
    assum_df: pd.DataFrame, newest_fact
) -> dict[str, pd.Series]:
    """Pick the applicable assumptions row per ticker, as :func:`load_inputs_from_csv` does.

    Only the *display* columns are read from here (company name, plan URL, the
    sourcing caveat); every modelled number still comes from the ``Assumptions``
    objects, and :func:`_check_assumption_rows` proves the two agree.
    """
    df = assum_df.assign(_eff=pd.to_datetime(assum_df["effective_from"])).sort_values("_eff")
    rows: dict[str, pd.Series] = {}
    for ticker, group in df.groupby("ticker", sort=False):
        applicable = group[group["_eff"] <= pd.Timestamp(newest_fact)]
        rows[str(ticker)] = (applicable if not applicable.empty else group).iloc[-1]
    return rows


def _check_assumption_rows(
    rows: Mapping[str, pd.Series], assumptions: Mapping[str, Assumptions]
) -> None:
    """Fail if the display row and the modelled bundle came from different versions."""
    for ticker, a in assumptions.items():
        row = rows[ticker]
        mismatches = []
        if float(row["ai_share_of_rpo_revenue"]) != a.ai_share_of_fact:
            mismatches.append("ai_share_of_rpo_revenue")
        if float(row["wacc"]) != a.wacc:
            mismatches.append("wacc")
        if float(row["annual_capex_guide_midpoint_actual_usd_b"]) != a.annual_capex_guide_b:
            mismatches.append("annual_capex_guide_midpoint_actual_usd_b")
        if str(row["ai_revenue_proxy"]) != a.proxy_label:
            mismatches.append("ai_revenue_proxy")
        if mismatches:
            raise SystemExit(
                f"assumptions.csv row selection disagrees with model.build for {ticker}: "
                + ", ".join(mismatches)
            )


def _row1_labels(expected_df: pd.DataFrame) -> dict[str, str]:
    """Per-company label of the trajectory's first row, taken from the workbook.

    Five of the six trajectory metrics are shared by every company; the sixth
    names that company's own fact ("Commercial RPO/Backlog ($B)" vs
    "Revenue (Quarter, $B)"). Deriving it keeps one source of truth.
    """
    shared = {label for label, _ in TRAJ_METRICS}
    labels: dict[str, str] = {}
    traj = expected_df[expected_df["view"] == "trajectory"]
    for ticker, group in traj.groupby("company", sort=False):
        own = sorted(set(group["metric"]) - shared)
        if len(own) != 1:
            raise SystemExit(
                f"cannot derive the row-1 label for {ticker}: candidates {own}"
            )
        labels[str(ticker)] = own[0]
    return labels


def _workbook_anchors(expected_df: pd.DataFrame) -> dict[str, str]:
    """The quarters the frozen workbook rows are pinned to, read off the file.

    The workbook's change row carries both anchors in its ``period`` --
    ``"Q2 25 to Q2 26"`` -- so neither has to be hardcoded here.
    """
    periods = [p for p in expected_df["period"].unique() if " to " in str(p)]
    if len(periods) != 1:
        raise SystemExit(f"expected exactly one change-row period, found {periods}")
    prior, latest = str(periods[0]).split(" to ")
    return {"base": prior, "latest": latest}


def _provenance_counts(data_dir: Path) -> dict[str, int]:
    """The workbook's own fill counts: sourced cells vs analyst cells."""
    prov = pd.read_csv(data_dir / "provenance.csv")
    counts = prov["fill_class"].value_counts()
    return {"factCells": int(counts.get("fact", 0)), "assumCells": int(counts.get("assumption", 0))}


# ---------------------------------------------------------------------------
# The model rows -- every number below comes from model/calc.py via model/build.py
# ---------------------------------------------------------------------------


#: Columns carried out of ``data/sources.csv`` into the page, in payload order.
SOURCE_FIELDS: tuple[tuple[str, str], ...] = (
    ("url", "url"),
    ("kind", "kind"),
    ("title_or_description", "title"),
    ("local_path_if_any", "local"),
    ("reported_value", "reported"),
    ("classification", "classification"),
    ("evidence_derivation", "evidence"),
    ("status", "status"),
    ("caveat", "caveat"),
    ("company", "company"),
    ("period", "period"),
)


def source_ledger(data_dir: Path) -> dict[str, dict[str, Any]]:
    """``data/sources.csv`` as a lookup keyed by ``source_id``.

    This is the evidence side of the page: every FACT the ledger renders cites
    one of these ids, and the page links the figure to the entry and back. A
    blank ``local_path_if_any`` becomes ``None`` rather than the string "nan" —
    21 of the 62 sources have no preserved local copy, and the page has to say
    so rather than print a filename that does not exist.
    """
    df = pd.read_csv(data_dir / "sources.csv")
    ledger: dict[str, dict[str, Any]] = {}
    for row in df.itertuples():
        entry: dict[str, Any] = {}
        for column, key in SOURCE_FIELDS:
            value = getattr(row, column)
            if pd.isna(value):
                entry[key] = None
            elif key == "reported":
                entry[key] = float(value)
            else:
                entry[key] = str(value)
        ledger[str(row.source_id)] = entry
    return ledger


def _require_source(
    sources: Mapping[str, Mapping[str, Any]], source_id: str, ticker: str, kind: str
) -> str:
    """Assert a source id exists and is of the expected kind, then return it.

    The page renders every FACT as a link into the ledger. A missing id would
    silently degrade to an unsourced number, which is the one thing this page
    must never do — so it is a build failure instead.
    """
    entry = sources.get(source_id)
    if entry is None:
        raise SystemExit(
            f"{ticker}: data/sources.csv has no entry {source_id!r}. Every figure the "
            "page renders must cite a source row; refusing to write an unsourced page."
        )
    if entry["kind"] != kind:
        raise SystemExit(
            f"{source_id}: expected kind {kind!r} in data/sources.csv, found "
            f"{entry['kind']!r}."
        )
    return source_id


def model_rows(
    facts: Sequence[QuarterFact],
    assumptions: Mapping[str, Assumptions],
    row1: Mapping[str, str],
    latest_quarter: str,
    base_quarter: str,
) -> list[list[str]]:
    """Expectation rows for one choice of latest/baseline quarter.

    Row shape matches the embedded ``expected`` rows exactly::

        [company, period, view, metric, value, value_type]

    Anchors with too little history emit no row at all --- there is nothing to
    verify, and the page renders "n/a" rather than a number.
    """
    quarters = build.ordered_quarters(facts)
    traj = build.build_trajectory(facts, assumptions)
    snap = build.build_snapshot(
        facts, assumptions, latest_quarter=latest_quarter, base_quarter=base_quarter
    )
    base_rows = snap[snap["scenario"] == "base"].set_index("ticker")
    indexed = snap.set_index(["ticker", "scenario"])
    by_key = {(r.ticker, r.quarter): r for r in traj.itertuples()}

    out: list[list[str]] = []

    def add(company: str, period: str, view: str, metric: str, value: Any, kind: str) -> None:
        out.append(
            [company, period, view, metric, value if kind == "text" else _num(value), kind]
        )

    for ticker in build.TICKERS:
        for quarter in quarters:
            row = by_key[(ticker, quarter)]
            add(ticker, quarter, "trajectory", row1[ticker], row.fact_value_b, "number")
            for label, field in TRAJ_METRICS:
                add(ticker, quarter, "trajectory", label, getattr(row, field), "number")

    for ticker in build.TICKERS:
        b = base_rows.loc[ticker]
        q = latest_quarter
        duration = b["rpo_duration_years"]
        is_rpo = ProxyBasis(b["proxy_basis"]) is ProxyBasis.RPO

        add(ticker, q, "snapshot", "Latest Quarter",
            f'{b["fiscal_period"]} ({_workbook_date(b["period_end"])})', "text")
        add(ticker, q, "snapshot", "AI Revenue Source", b["proxy_label"], "text")
        add(ticker, q, "snapshot", "Total RPO/Backlog or Annualized Revenue ($B)",
            b["snapshot_fact_b"], "number")
        add(ticker, q, "snapshot", "AI Share % (assumption)", b["ai_share_of_fact"], "number")
        add(ticker, q, "snapshot", "AI-linked RPO/Revenue ($B)", b["ai_linked_b"], "number")
        add(ticker, q, "snapshot", "Annual Capex Guide / Midpoint / Actual ($B)",
            b["annual_capex_guide_b"], "number")
        add(ticker, q, "snapshot", "Plan Basis", b["plan_basis"], "text")
        add(ticker, q, "snapshot", "AI Share of Capex % (assumption)",
            b["ai_share_of_capex"], "number")
        add(ticker, q, "snapshot", "AI Capex ($B)", b["ai_capex_b"], "number")
        if is_rpo:
            add(ticker, q, "snapshot", "RPO Duration (years, assumption)", duration, "number")
        else:
            # Meta has no backlog to amortise. "N/A" is the workbook's own text,
            # and it is a different statement from an unknown number.
            add(ticker, q, "snapshot", "RPO Duration (years, assumption)", "N/A", "text")
        add(ticker, q, "snapshot", "Annualized AI Revenue Proxy ($B)",
            b["ai_revenue_proxy_b"], "number")
        add(ticker, q, "snapshot", "NOPAT Margin (Base)", b["nopat_margin"], "number")
        for name, scenario in (("Base", "base"), ("Bear", "bear"), ("Bull", "bull")):
            r = indexed.loc[(ticker, scenario)]
            add(ticker, q, "snapshot", f"Forward ROIC ({name})", r["forward_roic"], "number")
            add(ticker, q, "snapshot", f"Spread ({name}, ppt)", r["spread"], "number")
        add(ticker, q, "snapshot", "WACC (Damodaran sector, Jan. 2026)", b["wacc"], "number")

        # Run-rate anchor levels, then the three comparisons against them.
        add(ticker, q, "snapshot", RUNRATE_SPREAD_LABEL.format(q=q),
            b["spread_latest_runrate"], "number")
        add(ticker, base_quarter, "snapshot", RUNRATE_SPREAD_LABEL.format(q=base_quarter),
            b["spread_base_runrate"], "number")
        add(ticker, f"{base_quarter} to {q}", "snapshot",
            WORKBOOK_DELTA_LABEL.format(latest=q, prior=base_quarter),
            b["delta_spread_bps"], "number")

        add(ticker, q, "snapshot",
            BASELINE_LABEL.format(latest=q, prior=base_quarter),
            b["delta_spread_bps"], "number")
        for label, quarter_col, delta_col in (
            (QOQ_LABEL, "qoq_quarter", "delta_spread_qoq_bps"),
            (YOY_LABEL, "yoy_quarter", "delta_spread_yoy_bps"),
        ):
            prior = b[quarter_col]
            delta = b[delta_col]
            if prior is None or pd.isna(delta):
                continue  # no history for this anchor; the page renders "n/a"
            add(ticker, q, "snapshot", label.format(latest=q, prior=prior), delta, "number")

    return out


def _as_map(rows: Iterable[Sequence[str]]) -> dict[tuple[str, str, str, str], tuple[str, str]]:
    return {(r[0], r[1], r[2], r[3]): (r[4], r[5]) for r in rows}


def verify_workbook(
    expected_df: pd.DataFrame, rows: Sequence[Sequence[str]]
) -> list[str]:
    """Recompute the frozen workbook rows here, before the page ever sees them."""
    got = _as_map(rows)
    failures: list[str] = []
    for r in expected_df.itertuples():
        key = (str(r.company), str(r.period), str(r.view), str(r.metric))
        if key not in got:
            failures.append(f"{key} — not produced by model/calc.py")
            continue
        mine, kind = got[key]
        if str(r.value_type) == "number":
            want = float(r.value)
            if abs(float(mine) - want) > PARITY_TOL * max(1.0, abs(want)):
                failures.append(f"{key} — model {mine}, workbook {want}")
        elif str(mine) != str(r.value):
            failures.append(f'{key} — model "{mine}", workbook "{r.value}"')
    return failures


# ---------------------------------------------------------------------------
# Payload assembly
# ---------------------------------------------------------------------------


def build_data(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, Any]:
    """Assemble the whole embedded ``DATA`` payload from the living data layer."""
    facts, assumptions = build.load_inputs_from_csv(data_dir)
    facts_df = pd.read_csv(data_dir / "facts.csv")
    assum_df = pd.read_csv(data_dir / "assumptions.csv")
    # keep_default_na: META's duration cell is the literal text "N/A", not a blank.
    expected_df = pd.read_csv(data_dir / "expected_outputs.csv", keep_default_na=False)

    quarters = build.ordered_quarters(facts)
    newest = max(f.period_end for f in facts)
    rows = _resolve_assumption_rows(assum_df, newest)
    _check_assumption_rows(rows, assumptions)

    row1 = _row1_labels(expected_df)
    wb = _workbook_anchors(expected_df)

    # Gate: the frozen workbook rows must still recompute from model/calc.py.
    workbook_model = model_rows(facts, assumptions, row1, wb["latest"], wb["base"])
    failures = verify_workbook(expected_df, workbook_model)
    if failures:
        raise SystemExit(
            "workbook parity broke — refusing to write a page with unverifiable numbers:\n  "
            + "\n  ".join(failures[:20])
            + (f"\n  … and {len(failures) - 20} more" if len(failures) > 20 else "")
        )

    computed = model_rows(facts, assumptions, row1, quarters[-1], quarters[0])

    sources = source_ledger(data_dir)

    facts_by_key = {(r.ticker, r.report_bucket): r for r in facts_df.itertuples()}
    fact_rows = []
    for ticker in build.TICKERS:
        for quarter in quarters:
            r = facts_by_key[(ticker, quarter)]
            _require_source(sources, str(r.fact_source_id), ticker, "fact")
            _require_source(sources, str(r.capex_source_id), ticker, "capex")
            fact_rows.append([
                str(r.ticker),
                str(r.report_bucket),
                str(r.fiscal_period),
                str(r.period_end),
                float(r.rpo_backlog_or_revenue_usd_b),
                str(r.fact_metric),
                float(r.quarterly_capex_usd_b),
                str(r.capex_definition),
                str(r.fact_source_url),
                str(r.capex_source_url),
                str(r.evidence_derivation),
                str(r.fact_source_id),
                str(r.capex_source_id),
            ])

    assum_payload: dict[str, Any] = {}
    for ticker in build.TICKERS:
        a = assumptions[ticker]
        row = rows[ticker]
        assum_payload[ticker] = {
            "company": str(row["company"]),
            "proxy": a.proxy_label,
            "share": a.ai_share_of_fact,
            "dur": a.rpo_duration_years,
            "capshare": a.ai_share_of_capex,
            "bear": a.nopat_margin_bear,
            "base": a.nopat_margin_base,
            "bull": a.nopat_margin_bull,
            "wacc": a.wacc,
            "sector": a.wacc_sector,
            "guide": a.annual_capex_guide_b,
            "planBasis": a.plan_basis,
            "planUrl": str(row["plan_source_url"]),
            # The date this assumptions row became effective. The annual denominator
            # is not a per-quarter fact, so the receipt names the period it belongs
            # to rather than let a reader take it for the selected quarter's.
            "planFrom": str(row["effective_from"]),
            "planSource": _require_source(sources, f"{ticker}-PLAN", ticker, "plan"),
            "waccSource": _require_source(sources, f"{ticker}-WACC", ticker, "wacc"),
            "caveat": str(row["source_assumption_caveat"]),
        }

    return {
        "tickers": list(build.TICKERS),
        "quartersPerYear": build.QUARTERS_PER_YEAR,
        "row1Label": {t: row1[t] for t in build.TICKERS},
        "provenance": _provenance_counts(data_dir),
        "workbook": wb,
        "facts": fact_rows,
        "assum": assum_payload,
        "sources": sources,
        "expected": [
            [str(r.company), str(r.period), str(r.view), str(r.metric),
             str(r.value), str(r.value_type)]
            for r in expected_df.itertuples()
        ],
        "computed": computed,
    }


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_block(data: Mapping[str, Any]) -> str:
    """Render the generated region, markers included.

    Array-of-array payloads get one row per line so a regeneration diffs as the
    rows that actually changed rather than as one 60 KB line.
    """
    parts = [
        BEGIN_MARKER,
        "/* Rows: facts [ticker,bucket,fiscal,period_end,fact,metric,capex,capexDef,",
        "   factUrl,capexUrl,evidence]; expected/computed [company,period,view,metric,",
        "   value,type]. `expected` is the workbook's frozen cache; `computed` is",
        "   model/calc.py run over every quarter on file. Regenerate, never hand-edit. */",
        "const DATA = {",
    ]
    keys = list(data)
    for i, key in enumerate(keys):
        tail = "" if i == len(keys) - 1 else ","
        value = data[key]
        if key in ("facts", "expected", "computed"):
            parts.append(f'"{key}":[')
            for j, row in enumerate(value):
                parts.append(_dumps(row) + ("" if j == len(value) - 1 else ","))
            parts.append("]" + tail)
        else:
            parts.append(f'"{key}":{_dumps(value)}{tail}')
    parts.append("};")
    parts.append(END_MARKER)
    return "\n".join(parts)


def splice(page: str, block: str) -> str:
    """Replace the marked region of ``page`` with ``block``. Idempotent."""
    start = page.find(BEGIN_MARKER)
    end = page.find(END_MARKER)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(
            "generated-data markers not found in the page; expected\n"
            f"  {BEGIN_MARKER}\n  {END_MARKER}"
        )
    return page[:start] + block + page[end + len(END_MARKER):]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--page", type=Path, default=DEFAULT_PAGE)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if regeneration would change the page",
    )
    args = parser.parse_args(argv)

    data = build_data(args.data_dir)
    page = args.page.read_text(encoding="utf-8")
    updated = splice(page, render_block(data))

    quarters = sorted({row[1] for row in data["facts"]},
                      key=lambda q: min(r[3] for r in data["facts"] if r[1] == q))
    print(f"quarters      {len(quarters)}: {', '.join(quarters)}")
    print(f"facts         {len(data['facts'])} company-quarters")
    print(f"expected      {len(data['expected'])} frozen workbook rows "
          f"(anchored {data['workbook']['base']} → {data['workbook']['latest']})")
    print(f"computed      {len(data['computed'])} rows from model/calc.py")

    if args.check:
        if updated != page:
            print("CHECK FAILED: the page is out of date; run without --check")
            return 1
        print("check         page is up to date")
        return 0

    if updated == page:
        print(f"unchanged     {args.page}")
        return 0
    args.page.write_text(updated, encoding="utf-8", newline="\n")
    print(f"wrote         {args.page}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
