"""The dashboard build step: a safe splice, an honest gate, and coverage that grows.

These tests exercise ``scripts/build_dashboard.py`` against a *copy* of the data
layer. Nothing here writes to ``data/``, the workbook, or the published page.

The property that matters most is the last group: when a sixth quarter lands in
``facts.csv``, the embedded expectation set must grow to cover it. A quarter that
is rendered but never verified is exactly the failure this build step exists to
prevent.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[2]

_spec = importlib.util.spec_from_file_location(
    "build_dashboard", REPO / "scripts" / "build_dashboard.py"
)
bd = importlib.util.module_from_spec(_spec)
sys.modules["build_dashboard"] = bd
_spec.loader.exec_module(bd)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sandbox(tmp_path: Path) -> Path:
    """A throwaway copy of ``data/`` plus the current page."""
    shutil.copytree(REPO / "data", tmp_path / "data")
    shutil.copy(REPO / "dashboard" / "index.html", tmp_path / "index.html")
    return tmp_path


def append_quarter(data_dir: Path, bucket: str, end: str, orcl_end: str) -> None:
    """Append one synthetic quarter for every company to a *copied* facts.csv."""
    facts = pd.read_csv(data_dir / "facts.csv")
    quarters = facts.groupby("report_bucket")["period_end"].min().sort_values()
    latest = facts[facts["report_bucket"] == quarters.index[-1]].copy()
    latest["report_bucket"] = bucket
    latest["fiscal_period"] = bucket + " (synthetic)"
    # Oracle closes a month before the other four; keep that offset.
    latest["period_end"] = latest["ticker"].map(lambda t: orcl_end if t == "ORCL" else end)
    latest["rpo_backlog_or_revenue_usd_b"] *= 1.05
    latest["quarterly_capex_usd_b"] *= 1.10
    latest["evidence_derivation"] = "SYNTHETIC — test fixture, not a filing."
    pd.concat([facts, latest], ignore_index=True).to_csv(
        data_dir / "facts.csv", index=False, encoding="utf-8"
    )


def regenerate(sandbox: Path) -> str:
    data = bd.build_data(sandbox / "data")
    page = (sandbox / "index.html").read_text(encoding="utf-8")
    out = bd.splice(page, bd.render_block(data))
    (sandbox / "index.html").write_text(out, encoding="utf-8", newline="\n")
    return out


def rows_of(data, key, view=None):
    rows = data[key]
    return [r for r in rows if view is None or r[2] == view]


# ---------------------------------------------------------------------------
# The splice
# ---------------------------------------------------------------------------


def test_the_shipped_page_is_already_up_to_date():
    """`--check` in CI: the committed page matches the committed data."""
    data = bd.build_data()
    page = (REPO / "dashboard" / "index.html").read_text(encoding="utf-8")
    assert bd.splice(page, bd.render_block(data)) == page


def test_regeneration_is_idempotent(sandbox: Path):
    first = regenerate(sandbox)
    second = regenerate(sandbox)
    assert first == second


def test_splice_touches_nothing_outside_the_markers(sandbox: Path):
    before = (sandbox / "index.html").read_text(encoding="utf-8")
    after = regenerate(sandbox)
    for text in (before, after):
        assert text.count(bd.BEGIN_MARKER) == 1
        assert text.count(bd.END_MARKER) == 1
    head = lambda t: t[: t.index(bd.BEGIN_MARKER)]  # noqa: E731
    tail = lambda t: t[t.index(bd.END_MARKER) + len(bd.END_MARKER) :]  # noqa: E731
    assert head(before) == head(after)
    assert tail(before) == tail(after)
    # The CSS, the markup and every hand-written function survive untouched.
    assert "<title>AI Capex Forward ROIC</title>" in head(after)
    assert "function renderAnchors()" in tail(after)


def test_a_page_without_markers_is_refused():
    with pytest.raises(SystemExit, match="markers"):
        bd.splice("<title>no markers here</title>", "block")


def test_generated_block_is_valid_json_after_the_assignment(sandbox: Path):
    import json

    block = bd.render_block(bd.build_data(sandbox / "data"))
    body = block[block.index("const DATA = ") + len("const DATA = ") : block.rindex("};") + 1]
    assert set(json.loads(body)) == {
        "tickers", "quartersPerYear", "row1Label", "provenance",
        "workbook", "facts", "assum", "sources", "expected", "computed",
    }


# ---------------------------------------------------------------------------
# The gate: the frozen workbook rows must still recompute
# ---------------------------------------------------------------------------


def test_workbook_rows_recompute_from_calc():
    data_dir = REPO / "data"
    facts, assumptions = bd.build.load_inputs_from_csv(data_dir)
    expected = pd.read_csv(data_dir / "expected_outputs.csv", keep_default_na=False)
    rows = bd.model_rows(
        facts, assumptions, bd._row1_labels(expected),
        *[bd._workbook_anchors(expected)[k] for k in ("latest", "base")],
    )
    assert bd.verify_workbook(expected, rows) == []
    assert len(expected) == 260


def test_a_broken_model_refuses_to_write_a_page(sandbox: Path):
    """Silent drift is the one thing this script must never ship."""
    assum = pd.read_csv(sandbox / "data" / "assumptions.csv")
    assum.loc[assum["ticker"] == "ORCL", "wacc"] = 0.5
    assum.to_csv(sandbox / "data" / "assumptions.csv", index=False, encoding="utf-8")
    with pytest.raises(SystemExit, match="workbook parity broke"):
        bd.build_data(sandbox / "data")


# ---------------------------------------------------------------------------
# Coverage grows with the data
# ---------------------------------------------------------------------------


def test_computed_covers_every_quarter_on_file(sandbox: Path):
    data = bd.build_data(sandbox / "data")
    buckets = {r[1] for r in data["facts"]}
    traj = rows_of(data, "computed", "trajectory")
    for ticker in data["tickers"]:
        covered = {r[1] for r in traj if r[0] == ticker}
        assert covered == buckets
    # Six metric rows per company-quarter, exactly as the workbook laid them out.
    assert len(traj) == len(data["tickers"]) * len(buckets) * 6


def test_the_frozen_set_stays_260_while_the_computed_set_grows(sandbox: Path):
    before = bd.build_data(sandbox / "data")
    append_quarter(sandbox / "data", "Q3 26", "2026-09-30", "2026-08-31")
    after = bd.build_data(sandbox / "data")

    assert len(before["expected"]) == len(after["expected"]) == 260
    assert len(after["facts"]) == len(before["facts"]) + 5
    # One more quarter = 5 companies x 6 trajectory metrics of new coverage.
    assert len(after["computed"]) == len(before["computed"]) + 30


def test_anchors_roll_forward_but_the_baseline_does_not(sandbox: Path):
    append_quarter(sandbox / "data", "Q3 26", "2026-09-30", "2026-08-31")
    data = bd.build_data(sandbox / "data")
    metrics = {r[3] for r in data["computed"] if r[0] == "MSFT" and r[2] == "snapshot"}

    assert bd.QOQ_LABEL.format(latest="Q3 26", prior="Q2 26") in metrics
    assert bd.YOY_LABEL.format(latest="Q3 26", prior="Q3 25") in metrics
    assert bd.BASELINE_LABEL.format(latest="Q3 26", prior="Q2 25") in metrics
    # The workbook's own anchor pair is untouched by the new quarter.
    assert data["workbook"] == {"base": "Q2 25", "latest": "Q2 26"}


def test_quarter_order_is_chronological_not_lexical(sandbox: Path):
    append_quarter(sandbox / "data", "Q3 26", "2026-09-30", "2026-08-31")
    data = bd.build_data(sandbox / "data")
    msft = [r for r in data["facts"] if r[0] == "MSFT"]
    buckets = [r[1] for r in msft]
    assert buckets == ["Q2 25", "Q3 25", "Q4 25", "Q1 26", "Q2 26", "Q3 26"]
    assert buckets != sorted(buckets)  # "Q1 26" sorts before "Q2 25"
    assert [r[3] for r in msft] == sorted(r[3] for r in msft)
    # Oracle's bucket ends a month earlier and still lands in the same bucket.
    orcl = {r[1]: r[3] for r in data["facts"] if r[0] == "ORCL"}
    assert orcl["Q3 26"] < {r[1]: r[3] for r in msft}["Q3 26"]


def test_an_anchor_without_history_emits_no_row_at_all(sandbox: Path):
    """Two quarters have no year-ago anchor. Nothing is invented for it."""
    facts, assumptions = bd.build.load_inputs_from_csv(sandbox / "data")
    two = [f for f in facts if f.quarter in ("Q2 25", "Q3 25")]
    expected = pd.read_csv(
        sandbox / "data" / "expected_outputs.csv", keep_default_na=False
    )
    rows = bd.model_rows(two, assumptions, bd._row1_labels(expected), "Q3 25", "Q2 25")
    metrics = {r[3] for r in rows if r[0] == "MSFT" and r[2] == "snapshot"}

    assert not [m for m in metrics if m.startswith("Δ Spread YoY")]
    assert bd.QOQ_LABEL.format(latest="Q3 25", prior="Q2 25") in metrics


# ---------------------------------------------------------------------------
# The payload the page relies on
# ---------------------------------------------------------------------------


def test_row1_labels_come_from_the_workbook_not_a_hardcoded_map():
    data = bd.build_data()
    assert data["row1Label"]["META"] == "Revenue (Quarter, $B)"
    assert data["row1Label"]["MSFT"] == "Commercial RPO/Backlog ($B)"


def test_meta_carries_no_duration_anywhere_in_the_payload():
    data = bd.build_data()
    assert data["assum"]["META"]["dur"] is None
    duration = [
        r for r in data["computed"]
        if r[0] == "META" and r[3] == "RPO Duration (years, assumption)"
    ]
    assert [r[4:] for r in duration] == [["N/A", "text"]]


def test_expected_and_computed_share_one_row_shape():
    data = bd.build_data()
    for key in ("expected", "computed"):
        for row in data[key]:
            assert len(row) == 6
            assert row[2] in ("trajectory", "snapshot")
            assert row[5] in ("number", "text")
            if row[5] == "number":
                float(row[4])  # round-trippable for the page's parseFloat


# ---------------------------------------------------------------------------
# The evidence ledger: no figure on the page is allowed to be unsourced
# ---------------------------------------------------------------------------


def test_every_source_row_reaches_the_page():
    data = bd.build_data(REPO / "data")
    on_file = pd.read_csv(REPO / "data" / "sources.csv")
    assert set(data["sources"]) == set(on_file.source_id)
    assert len(data["sources"]) == 62


def test_every_fact_row_cites_two_sources_that_exist(sandbox: Path):
    data = bd.build_data(sandbox / "data")
    sources = data["sources"]
    for row in data["facts"]:
        fact_id, capex_id = row[11], row[12]
        assert sources[fact_id]["kind"] == "fact", row[:2]
        assert sources[capex_id]["kind"] == "capex", row[:2]


def test_every_company_cites_a_plan_and_a_wacc_source():
    data = bd.build_data(REPO / "data")
    for ticker, a in data["assum"].items():
        assert data["sources"][a["planSource"]]["kind"] == "plan", ticker
        assert data["sources"][a["waccSource"]]["kind"] == "wacc", ticker


def test_a_fact_row_citing_an_unknown_source_refuses_to_build(sandbox: Path):
    """An unsourced figure is a build failure, not a quietly bare number."""
    facts = sandbox / "data" / "facts.csv"
    df = pd.read_csv(facts)
    df.loc[0, "fact_source_id"] = "GOOG-Q999-FACT"
    df.to_csv(facts, index=False)
    with pytest.raises(SystemExit, match="GOOG-Q999-FACT"):
        bd.build_data(sandbox / "data")


def test_a_source_of_the_wrong_kind_refuses_to_build(sandbox: Path):
    srcs = sandbox / "data" / "sources.csv"
    df = pd.read_csv(srcs)
    df.loc[df.source_id == "MSFT-WACC", "kind"] = "plan"
    df.to_csv(srcs, index=False)
    with pytest.raises(SystemExit, match="expected kind 'wacc'"):
        bd.build_data(sandbox / "data")


def test_a_blank_local_path_is_null_not_the_string_nan():
    """21 of the 62 sources have no preserved copy. The page has to say so."""
    sources = bd.build_data(REPO / "data")["sources"]
    locals_ = [s["local"] for s in sources.values()]
    assert None in locals_
    assert not any(isinstance(v, str) and v.lower() == "nan" for v in locals_)
    assert sum(v is None for v in locals_) == 21


def test_a_new_quarter_without_source_rows_is_refused(sandbox: Path):
    """A quarter appended to facts.csv whose sources never landed is refused.

    ``pipeline.apply`` appends the fact row and the matching ``*-FACT`` /
    ``*-CAPEX`` source rows together. If only the first half arrives, the page
    would render a new quarter whose blue figures link nowhere — so the build
    stops instead. (The synthetic quarter used by the tests above copies the
    previous quarter's ids, which is why it builds; a real one would not.)
    """
    append_quarter(sandbox / "data", "Q3 26", "2026-09-30", "2026-08-31")
    facts = sandbox / "data" / "facts.csv"
    df = pd.read_csv(facts)
    new_rows = df["report_bucket"] == "Q3 26"
    df.loc[new_rows, "fact_source_id"] = df.loc[new_rows, "ticker"] + "-Q326-FACT"
    df.loc[new_rows, "capex_source_id"] = df.loc[new_rows, "ticker"] + "-Q326-CAPEX"
    df.to_csv(facts, index=False)
    with pytest.raises(SystemExit, match="MSFT-Q326-FACT"):
        bd.build_data(sandbox / "data")
