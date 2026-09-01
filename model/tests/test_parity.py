"""Cell-for-cell parity against the workbook's cached values.

Every numeric cell of the ``Trajectory`` and ``Snapshot`` sheets is compared
with the recomputation from :mod:`model.build`. Tolerance is ``rtol=1e-12``:
this is deterministic IEEE-754 arithmetic replayed in the same operation
order as the Excel formulas, not an estimate. A failure here means the
workbook and this implementation genuinely disagree -- do not loosen it.
"""

from __future__ import annotations

import math
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import openpyxl
import pytest

from model import build
from model.calc import CapexView, ProxyBasis, Scenario, basis_points

if hasattr(sys.stdout, "reconfigure"):  # Windows console is cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKBOOK: Path = build.WORKBOOK_PATH
RTOL = 1e-12


@lru_cache(maxsize=1)
def _cached_cells() -> dict[str, Any]:
    """Every non-empty cached cell of Trajectory and Snapshot, by address.

    Read once at collection time so the parametrised parity test can enumerate
    one case per cell.
    """
    wb = openpyxl.load_workbook(WORKBOOK, data_only=True)
    try:
        out: dict[str, Any] = {}
        for sheet in ("Trajectory", "Snapshot"):
            for row in wb[sheet].iter_rows():
                for cell in row:
                    if cell.value is not None:
                        out[f"{sheet}!{cell.coordinate}"] = cell.value
        return out
    finally:
        wb.close()


@pytest.fixture(scope="session")
def cached_values() -> dict[str, Any]:
    return _cached_cells()


@pytest.fixture(scope="session")
def recomputed() -> dict[str, float]:
    """Recomputed values keyed by the workbook address they correspond to."""
    trajectory, snapshot = build.build_all(WORKBOOK)
    return build.cell_map(trajectory, snapshot)


def _numeric_addresses(cached: dict[str, Any]) -> list[str]:
    return sorted(
        addr
        for addr, value in cached.items()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )


def test_workbook_is_present() -> None:
    assert WORKBOOK.exists(), f"workbook not found at {WORKBOOK}"


def test_every_numeric_cell_is_covered(
    cached_values: dict[str, Any], recomputed: dict[str, float]
) -> None:
    """No numeric presentation cell may go unchecked, and none may be invented."""
    cached_numeric = set(_numeric_addresses(cached_values))
    ours = set(recomputed)
    missing = sorted(cached_numeric - ours)
    extra = sorted(ours - cached_numeric)
    assert not missing, f"numeric workbook cells with no recomputation: {missing}"
    assert not extra, f"recomputed cells absent from the workbook: {extra}"


@pytest.mark.parametrize("address", _numeric_addresses(_cached_cells()))
def test_cell_parity(
    address: str, cached_values: dict[str, Any], recomputed: dict[str, float]
) -> None:
    """Each numeric Trajectory/Snapshot cell matches the recomputation."""
    expected = cached_values[address]
    assert address in recomputed, f"{address} has no recomputed counterpart"
    actual = recomputed[address]
    assert actual == pytest.approx(expected, rel=RTOL, abs=0.0), (
        f"{address}: workbook cached {expected!r}, recomputed {actual!r} "
        f"(abs diff {abs(actual - expected)!r})"
    )


def test_trajectory_grid_shape() -> None:
    """5 companies x 5 quarters, each with proxy, capex, ROIC and spread."""
    trajectory, _ = build.build_all(WORKBOOK)
    assert len(trajectory) == 25
    assert set(trajectory["ticker"]) == set(build.TICKERS)
    for column in ("ai_revenue_proxy_b", "ai_capex_b", "forward_roic", "spread"):
        assert trajectory[column].notna().all()
        assert trajectory[column].map(math.isfinite).all()


def test_snapshot_covers_all_three_scenarios() -> None:
    _, snapshot = build.build_all(WORKBOOK)
    assert len(snapshot) == 15
    for ticker in build.TICKERS:
        rows = snapshot[snapshot["ticker"] == ticker]
        assert set(rows["scenario"]) == {"bear", "base", "bull"}


def test_bear_base_bull_are_monotonic() -> None:
    """ROIC scales linearly with NOPAT margin, so bear <= base <= bull."""
    _, snapshot = build.build_all(WORKBOOK)
    for ticker in build.TICKERS:
        rows = snapshot[snapshot["ticker"] == ticker].set_index("scenario")
        assert rows.loc["bear", "forward_roic"] <= rows.loc["base", "forward_roic"]
        assert rows.loc["base", "forward_roic"] <= rows.loc["bull", "forward_roic"]


def test_meta_uses_the_revenue_branch_without_a_duration() -> None:
    """META's duration is absent, not a sentinel number."""
    _, assumptions = build.load_inputs(WORKBOOK)
    meta = assumptions["META"]
    assert meta.proxy_basis is ProxyBasis.REVENUE
    assert meta.rpo_duration_years is None
    for ticker in ("MSFT", "GOOG", "AMZN", "ORCL"):
        assert assumptions[ticker].proxy_basis is ProxyBasis.RPO
        assert assumptions[ticker].rpo_duration_years is not None


def test_delta_bps_is_the_runrate_q2_to_q2_change() -> None:
    """Snapshot row 27 is (Q2 26 - Q2 25) run-rate spread, in basis points."""
    trajectory, snapshot = build.build_all(WORKBOOK)
    for ticker in build.TICKERS:
        traj = trajectory[trajectory["ticker"] == ticker].set_index("quarter")
        row = snapshot[snapshot["ticker"] == ticker].iloc[0]
        expected = basis_points(
            traj.loc["Q2 26", "spread"] - traj.loc["Q2 25", "spread"]
        )
        assert row["delta_spread_bps"] == pytest.approx(expected, rel=RTOL, abs=0.0)


@pytest.mark.parametrize(
    "ticker,quarter,view,expected_proxy,expected_capex,expected_roic",
    [
        ("MSFT", "Q2 26", CapexView.TRAJECTORY, 135.6, 139.4, 0.29182209469153514),
        ("MSFT", "Q2 26", CapexView.SNAPSHOT, 135.6, 148.75, 0.27347899159663863),
        ("META", "Q2 26", CapexView.TRAJECTORY, 48.6408, 111.8808, 0.13912177960829744),
    ],
)
def test_hand_worked_examples(
    ticker: str,
    quarter: str,
    view: CapexView,
    expected_proxy: float,
    expected_capex: float,
    expected_roic: float,
) -> None:
    """The examples verified by hand against the workbook."""
    from model import calc

    facts, assumptions = build.load_inputs(WORKBOOK)
    fact = next(f for f in facts if f.ticker == ticker and f.quarter == quarter)
    result = calc.scenario_result(
        build.company_inputs(fact, assumptions), view, Scenario.BASE
    )
    assert result["ai_revenue_proxy_b"] == pytest.approx(expected_proxy, rel=RTOL, abs=0.0)
    assert result["ai_capex_b"] == pytest.approx(expected_capex, rel=RTOL, abs=0.0)
    assert result["forward_roic"] == expected_roic  # bit-exact


def test_msft_q2_26_spread_is_bit_exact() -> None:
    from model import calc

    facts, assumptions = build.load_inputs(WORKBOOK)
    fact = next(f for f in facts if f.ticker == "MSFT" and f.quarter == "Q2 26")
    result = calc.scenario_result(
        build.company_inputs(fact, assumptions), CapexView.TRAJECTORY, Scenario.BASE
    )
    assert result["spread"] == 0.19842209469153516


# ---------------------------------------------------------------------------
# Sensitivity helper
# ---------------------------------------------------------------------------


def _inputs_for(ticker: str, quarter: str = "Q2 26"):
    facts, assumptions = build.load_inputs(WORKBOOK)
    fact = next(f for f in facts if f.ticker == ticker and f.quarter == quarter)
    return build.company_inputs(fact, assumptions)


def test_sensitivity_curve_reproduces_the_baseline_at_the_baseline_value() -> None:
    from model import calc

    inputs = _inputs_for("AMZN")
    curve = calc.sensitivity_curve(
        inputs, "rpo_duration_years", [inputs.rpo_duration_years]
    )
    assert len(curve) == 1
    assert curve[0]["spread"] == 0.044724242424242444  # Trajectory!G24


def test_amzn_duration_is_the_largest_stated_sensitivity() -> None:
    """4.0 assumed vs 6.4 disclosed: the run-rate spread all but vanishes.

    Amazon disclosed a 6.4-year weighted-average remaining contract life at
    June 30, 2026; the model retains 4.0 years. Swapping in the disclosed
    figure takes the Q2 26 run-rate spread from +447 bps to +7 bps -- still
    positive, but no longer distinguishable from the cost of capital.
    """
    from model import calc

    inputs = _inputs_for("AMZN")
    assert inputs.rpo_duration_years == 4.0
    assumed, disclosed = calc.sensitivity_curve(
        inputs, "rpo_duration_years", [4.0, 6.4]
    )
    assert assumed["spread_bps"] == pytest.approx(447.24, abs=0.01)
    assert disclosed["spread_bps"] == pytest.approx(6.90, abs=0.01)
    assert disclosed["spread_bps"] < 10 < assumed["spread_bps"]


def test_sweeping_duration_on_meta_is_rejected() -> None:
    from model import calc

    with pytest.raises(ValueError, match="revenue-based proxy"):
        calc.sensitivity_curve(_inputs_for("META"), "rpo_duration_years", [3.0, 4.0])


def test_nopat_sweep_reads_back_the_swept_margin() -> None:
    from model import calc

    curve = calc.sensitivity_curve(
        _inputs_for("MSFT"), "nopat_margin", calc.linspace(0.2, 0.4, 5)
    )
    assert [point["nopat_margin"] for point in curve] == pytest.approx(
        [0.2, 0.25, 0.30, 0.35, 0.4]
    )
    spreads = [point["spread"] for point in curve]
    assert spreads == sorted(spreads)


def test_sensitivity_points_are_json_serialisable() -> None:
    import json

    from model import calc

    curve = calc.sensitivity_curve(
        _inputs_for("ORCL"),
        calc.SweepParameter.AI_SHARE_OF_FACT,
        calc.linspace(0.5, 1.0, 6),
        view=CapexView.SNAPSHOT,
        scenario=Scenario.BEAR,
    )
    payload = json.dumps(curve)
    assert json.loads(payload)[0]["parameter"] == "ai_share_of_fact"
    assert {"ticker", "view", "scenario", "value", "spread", "spread_bps", "wacc"} <= set(
        curve[0]
    )


def test_company_inputs_are_serialisable_and_immutable() -> None:
    import json

    inputs = _inputs_for("META")
    payload = json.loads(json.dumps(inputs.to_dict()))
    assert payload["rpo_duration_years"] is None
    assert payload["proxy_basis"] == "revenue"
    with pytest.raises(Exception):
        inputs.fact_value_b = 1.0  # frozen dataclass
    with pytest.raises(ValueError, match="unknown CompanyInputs field"):
        inputs.replace(not_a_field=1.0)
