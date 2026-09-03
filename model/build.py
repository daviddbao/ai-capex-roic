"""Table assembly for the AI capex / forward ROIC model.

This is the only module that touches the filesystem. It reads the ``Inputs``
sheet of the workbook into plain records, then assembles the Trajectory and
Snapshot tables by calling the pure functions in :mod:`model.calc`.

Dollar columns are $B; shares, margins, WACC, ROIC and spreads are decimals;
``delta_spread_bps`` is basis points.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import openpyxl
import pandas as pd

from . import calc
from .calc import CapexView, CompanyInputs, ProxyBasis, Scenario

__all__ = [
    "WORKBOOK_PATH",
    "DATA_DIR",
    "TICKERS",
    "QUARTERS",
    "QUARTERS_PER_YEAR",
    "QuarterFact",
    "Assumptions",
    "load_inputs",
    "load_inputs_from_csv",
    "ordered_quarters",
    "build_trajectory",
    "build_snapshot",
    "build_all",
    "company_inputs",
    "trajectory_cell_map",
    "snapshot_cell_map",
    "cell_map",
]

WORKBOOK_PATH: Path = (
    Path(__file__).resolve().parents[1] / "ai_capex_forward_roic_analysis_v02.xlsx"
)

#: The living data layer. Unlike the workbook, this grows every quarter.
DATA_DIR: Path = Path(__file__).resolve().parents[1] / "data"

#: Company order as laid out in the workbook's presentation sheets.
TICKERS: tuple[str, ...] = ("MSFT", "GOOG", "AMZN", "ORCL", "META")

#: The five quarter buckets frozen into workbook v02, oldest first.
#:
#: This is the *workbook's* series, kept for parity tests only. Everything that
#: builds tables derives its quarter order from the facts it was handed via
#: :func:`ordered_quarters`, so the series grows without touching this constant.
QUARTERS: tuple[str, ...] = ("Q2 25", "Q3 25", "Q4 25", "Q1 26", "Q2 26")

#: Buckets per year, used to locate the year-over-year anchor.
QUARTERS_PER_YEAR: int = 4

#: Marker used in the workbook's ``Q`` column for the revenue-based branch.
_REVENUE_PROXY_MARKER = "quarterly revenue"


@dataclass(frozen=True)
class QuarterFact:
    """One company-quarter of SOURCED FACTS from the Inputs sheet."""

    ticker: str
    company: str
    quarter: str
    fiscal_period: str
    period_end: datetime | None
    fact_value_b: float
    fact_metric: str
    quarterly_capex_b: float
    capex_definition: str


@dataclass(frozen=True)
class Assumptions:
    """One company's ANALYST ASSUMPTIONS plus its annual capex denominator."""

    ticker: str
    proxy_label: str
    proxy_basis: ProxyBasis
    ai_share_of_fact: float
    rpo_duration_years: float | None
    ai_share_of_capex: float
    nopat_margin_bear: float
    nopat_margin_base: float
    nopat_margin_bull: float
    wacc: float
    wacc_sector: str
    annual_capex_guide_b: float
    plan_basis: str


def _proxy_basis_from_label(label: str, duration: float | None, ticker: str) -> ProxyBasis:
    """Derive the proxy branch from the workbook's own description, then check it.

    The revenue branch is identified by the label, not by a sentinel number:
    duration is genuinely inapplicable there, so the workbook leaves the cell
    empty on Inputs and prints "N/A" on Snapshot.
    """
    is_revenue = _REVENUE_PROXY_MARKER in label.lower()
    basis = ProxyBasis.REVENUE if is_revenue else ProxyBasis.RPO
    if basis is ProxyBasis.REVENUE and duration is not None:
        raise ValueError(f"{ticker}: revenue-based proxy must not carry a duration")
    if basis is ProxyBasis.RPO and duration is None:
        raise ValueError(f"{ticker}: RPO-based proxy requires a duration")
    return basis


def load_inputs(
    workbook_path: Path | str = WORKBOOK_PATH,
) -> tuple[list[QuarterFact], dict[str, Assumptions]]:
    """Read the ``Inputs`` sheet. Returns (facts, assumptions-by-ticker).

    The workbook is opened read-only and never written.
    """
    wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        ws = wb["Inputs"]
        rows = {
            n: values
            for n, values in enumerate(
                ws.iter_rows(min_row=1, max_row=29, max_col=29, values_only=True), start=1
            )
        }

        def cell(row: int, col: str) -> Any:
            idx = openpyxl.utils.column_index_from_string(col) - 1
            return rows[row][idx]

        facts: list[QuarterFact] = []
        for row in range(5, 30):  # 5 companies x 5 quarters
            facts.append(
                QuarterFact(
                    ticker=str(cell(row, "B")),
                    company=str(cell(row, "A")),
                    quarter=str(cell(row, "C")),
                    fiscal_period=str(cell(row, "D")),
                    period_end=cell(row, "E"),
                    fact_value_b=float(cell(row, "F")),
                    fact_metric=str(cell(row, "G")),
                    quarterly_capex_b=float(cell(row, "H")),
                    capex_definition=str(cell(row, "I")),
                )
            )

        assumptions: dict[str, Assumptions] = {}
        for row in range(5, 10):  # assumption block, one row per company
            ticker = str(cell(row, "P"))
            raw_duration = cell(row, "S")
            duration = None if raw_duration is None else float(raw_duration)
            label = str(cell(row, "Q"))
            assumptions[ticker] = Assumptions(
                ticker=ticker,
                proxy_label=label,
                proxy_basis=_proxy_basis_from_label(label, duration, ticker),
                ai_share_of_fact=float(cell(row, "R")),
                rpo_duration_years=duration,
                ai_share_of_capex=float(cell(row, "T")),
                nopat_margin_bear=float(cell(row, "U")),
                nopat_margin_base=float(cell(row, "V")),
                nopat_margin_bull=float(cell(row, "W")),
                wacc=float(cell(row, "X")),
                wacc_sector=str(cell(row, "Y")),
                annual_capex_guide_b=float(cell(row, "Z")),
                plan_basis=str(cell(row, "AA")),
            )
        return facts, assumptions
    finally:
        wb.close()


def load_inputs_from_csv(
    data_dir: Path | str = DATA_DIR,
) -> tuple[list[QuarterFact], dict[str, Assumptions]]:
    """Read the living data layer. Returns (facts, assumptions-by-ticker).

    This is the forward path: ``data/facts.csv`` gains a row per company each
    quarter, so the series it produces grows without any code change. The
    workbook loader (:func:`load_inputs`) stays pinned to the frozen v02 sheet
    and exists for parity testing.

    Where ``assumptions.csv`` carries several versioned rows for one ticker,
    the row with the latest ``effective_from`` not after the newest fact wins.
    """
    data_dir = Path(data_dir)
    facts_df = pd.read_csv(data_dir / "facts.csv")
    assum_df = pd.read_csv(data_dir / "assumptions.csv")

    facts = [
        QuarterFact(
            ticker=str(r.ticker),
            company=str(r.company),
            quarter=str(r.report_bucket),
            fiscal_period=str(r.fiscal_period),
            period_end=datetime.fromisoformat(str(r.period_end)),
            fact_value_b=float(r.rpo_backlog_or_revenue_usd_b),
            fact_metric=str(r.fact_metric),
            quarterly_capex_b=float(r.quarterly_capex_usd_b),
            capex_definition=str(r.capex_definition),
        )
        for r in facts_df.itertuples()
    ]

    newest_fact = max(f.period_end for f in facts)
    assum_df = assum_df.assign(
        _eff=pd.to_datetime(assum_df["effective_from"])
    ).sort_values("_eff")

    assumptions: dict[str, Assumptions] = {}
    for ticker, group in assum_df.groupby("ticker", sort=False):
        applicable = group[group["_eff"] <= pd.Timestamp(newest_fact)]
        row = (applicable if not applicable.empty else group).iloc[-1]
        raw_duration = row["rpo_duration_years"]
        duration = None if pd.isna(raw_duration) else float(raw_duration)
        label = str(row["ai_revenue_proxy"])
        assumptions[str(ticker)] = Assumptions(
            ticker=str(ticker),
            proxy_label=label,
            proxy_basis=_proxy_basis_from_label(label, duration, str(ticker)),
            ai_share_of_fact=float(row["ai_share_of_rpo_revenue"]),
            rpo_duration_years=duration,
            ai_share_of_capex=float(row["ai_share_of_capex"]),
            nopat_margin_bear=float(row["nopat_margin_bear"]),
            nopat_margin_base=float(row["nopat_margin_base"]),
            nopat_margin_bull=float(row["nopat_margin_bull"]),
            wacc=float(row["wacc"]),
            wacc_sector=str(row["damodaran_sector_date"]),
            annual_capex_guide_b=float(row["annual_capex_guide_midpoint_actual_usd_b"]),
            plan_basis=str(row["plan_basis"]),
        )
    return facts, assumptions


def company_inputs(
    fact: QuarterFact, assumptions: Mapping[str, Assumptions]
) -> CompanyInputs:
    """Bundle one company-quarter into a :class:`~model.calc.CompanyInputs`."""
    a = assumptions[fact.ticker]
    return CompanyInputs(
        ticker=fact.ticker,
        proxy_basis=a.proxy_basis,
        fact_value_b=fact.fact_value_b,
        quarterly_capex_b=fact.quarterly_capex_b,
        annual_capex_guide_b=a.annual_capex_guide_b,
        ai_share_of_fact=a.ai_share_of_fact,
        rpo_duration_years=a.rpo_duration_years,
        ai_share_of_capex=a.ai_share_of_capex,
        nopat_margin_bear=a.nopat_margin_bear,
        nopat_margin_base=a.nopat_margin_base,
        nopat_margin_bull=a.nopat_margin_bull,
        wacc=a.wacc,
    )


def ordered_quarters(facts: Iterable[QuarterFact]) -> tuple[str, ...]:
    """Quarter buckets in chronological order, derived from the facts themselves.

    The series **grows forever**: appending a quarter widens the trajectory and
    nothing is ever dropped. Order comes from each bucket's earliest
    ``period_end`` rather than a hardcoded list, because fiscal calendars differ
    -- Oracle's quarters end a month before the calendar-aligned four, so
    sorting bucket labels lexically would be wrong.
    """
    first_end: dict[str, datetime] = {}
    seen: set[str] = set()
    for fact in facts:
        seen.add(fact.quarter)
        if fact.period_end is None:
            continue
        current = first_end.get(fact.quarter)
        if current is None or fact.period_end < current:
            first_end[fact.quarter] = fact.period_end
    undated = seen - set(first_end)
    if undated:
        raise ValueError(
            "cannot order quarter buckets without a period_end: "
            + ", ".join(sorted(undated))
        )
    return tuple(sorted(first_end, key=lambda q: first_end[q]))


def _ordered_facts(facts: Iterable[QuarterFact]) -> list[QuarterFact]:
    """Facts in presentation order: company block, then quarter."""
    facts = list(facts)
    quarters = ordered_quarters(facts)
    ticker_order = {t: i for i, t in enumerate(TICKERS)}
    quarter_order = {q: i for i, q in enumerate(quarters)}
    return sorted(
        facts,
        key=lambda f: (
            ticker_order.get(f.ticker, len(ticker_order)),
            quarter_order[f.quarter],
        ),
    )


def build_trajectory(
    facts: Sequence[QuarterFact], assumptions: Mapping[str, Assumptions]
) -> pd.DataFrame:
    """Tidy Trajectory table: one row per company-quarter, BASE scenario only.

    Columns: ticker, quarter, quarter_index, fiscal_period, period_end,
    fact_metric, fact_value_b, quarterly_capex_b, ai_capex_b,
    ai_revenue_proxy_b, scenario, nopat_margin, forward_roic, spread, wacc.
    """
    ordered = _ordered_facts(facts)
    quarter_index = {q: i for i, q in enumerate(ordered_quarters(ordered))}
    records: list[dict[str, Any]] = []
    for fact in ordered:
        ci = company_inputs(fact, assumptions)
        result = calc.scenario_result(ci, CapexView.TRAJECTORY, Scenario.BASE)
        records.append(
            {
                "ticker": fact.ticker,
                "quarter": fact.quarter,
                "quarter_index": quarter_index[fact.quarter],
                "fiscal_period": fact.fiscal_period,
                "period_end": fact.period_end,
                "fact_metric": fact.fact_metric,
                "fact_value_b": fact.fact_value_b,
                "quarterly_capex_b": fact.quarterly_capex_b,
                "ai_capex_b": result["ai_capex_b"],
                "ai_revenue_proxy_b": result["ai_revenue_proxy_b"],
                "scenario": result["scenario"],
                "nopat_margin": result["nopat_margin"],
                "forward_roic": result["forward_roic"],
                "wacc": ci.wacc,
                "spread": result["spread"],
            }
        )
    return pd.DataFrame.from_records(records)


def build_snapshot(
    facts: Sequence[QuarterFact],
    assumptions: Mapping[str, Assumptions],
    latest_quarter: str | None = None,
    base_quarter: str | None = None,
) -> pd.DataFrame:
    """Tidy Snapshot table: one row per (company, scenario) for the latest quarter.

    The snapshot ROIC uses the annual capex denominator. The run-rate columns
    come from the TRAJECTORY view and are constant across the three scenario
    rows of a company, matching the workbook, whose change row is computed from
    base-scenario run-rate spreads only.

    Three comparisons are reported against the latest quarter, all on the
    run-rate basis:

    ``delta_spread_yoy_bps``
        Versus the same quarter one year earlier (four buckets back). This
        rolls forward as the series grows, preserving the seasonal like-for-like
        read.
    ``delta_spread_qoq_bps``
        Versus the immediately preceding quarter -- the "sequential change" the
        methodology document reports but the workbook never computed.
    ``delta_spread_bps``
        Versus ``base_quarter``, the permanent baseline (default: the oldest
        quarter on file). Retained because it is the workbook's own row 27.

    Any anchor with too little history is ``None`` rather than a fabricated
    number, so the columns are nullable by design.
    """
    facts = list(facts)
    quarters = ordered_quarters(facts)
    if latest_quarter is None:
        latest_quarter = quarters[-1]
    if base_quarter is None:
        base_quarter = quarters[0]
    if latest_quarter not in quarters:
        raise ValueError(f"latest_quarter {latest_quarter!r} is not in the facts")
    if base_quarter not in quarters:
        raise ValueError(f"base_quarter {base_quarter!r} is not in the facts")

    latest_idx = quarters.index(latest_quarter)
    yoy_idx = latest_idx - QUARTERS_PER_YEAR
    qoq_idx = latest_idx - 1
    yoy_quarter = quarters[yoy_idx] if yoy_idx >= 0 else None
    qoq_quarter = quarters[qoq_idx] if qoq_idx >= 0 else None

    by_key = {(f.ticker, f.quarter): f for f in facts}

    def run_rate(ticker: str, quarter: str | None) -> float | None:
        """Base-scenario run-rate spread for one company-quarter."""
        if quarter is None:
            return None
        ci = company_inputs(by_key[(ticker, quarter)], assumptions)
        return calc.scenario_result(ci, CapexView.TRAJECTORY, Scenario.BASE)["spread"]

    def delta_bps_or_none(latest: float, prior: float | None) -> float | None:
        return None if prior is None else calc.basis_points(latest - prior)

    records: list[dict[str, Any]] = []
    for ticker in TICKERS:
        latest = by_key[(ticker, latest_quarter)]
        a = assumptions[ticker]
        ci_latest = company_inputs(latest, assumptions)

        run_rate_latest = calc.scenario_result(
            ci_latest, CapexView.TRAJECTORY, Scenario.BASE
        )["spread"]
        run_rate_earliest = run_rate(ticker, base_quarter)
        run_rate_yoy = run_rate(ticker, yoy_quarter)
        run_rate_qoq = run_rate(ticker, qoq_quarter)

        delta_bps = calc.basis_points(run_rate_latest - run_rate_earliest)
        delta_yoy_bps = delta_bps_or_none(run_rate_latest, run_rate_yoy)
        delta_qoq_bps = delta_bps_or_none(run_rate_latest, run_rate_qoq)

        # Display intermediate: the AI-attributed balance before amortisation.
        snapshot_fact_b = (
            latest.fact_value_b
            if a.proxy_basis is ProxyBasis.RPO
            else latest.fact_value_b * 4
        )
        ai_linked_b = snapshot_fact_b * a.ai_share_of_fact

        for scenario in (Scenario.BASE, Scenario.BEAR, Scenario.BULL):
            result = calc.scenario_result(ci_latest, CapexView.SNAPSHOT, scenario)
            records.append(
                {
                    "ticker": ticker,
                    "quarter": latest_quarter,
                    "fiscal_period": latest.fiscal_period,
                    "period_end": latest.period_end,
                    "proxy_basis": ProxyBasis(a.proxy_basis).value,
                    "proxy_label": a.proxy_label,
                    "snapshot_fact_b": snapshot_fact_b,
                    "ai_share_of_fact": a.ai_share_of_fact,
                    "ai_linked_b": ai_linked_b,
                    "annual_capex_guide_b": a.annual_capex_guide_b,
                    "plan_basis": a.plan_basis,
                    "ai_share_of_capex": a.ai_share_of_capex,
                    "ai_capex_b": result["ai_capex_b"],
                    "rpo_duration_years": a.rpo_duration_years,
                    "ai_revenue_proxy_b": result["ai_revenue_proxy_b"],
                    "scenario": result["scenario"],
                    "nopat_margin": result["nopat_margin"],
                    "forward_roic": result["forward_roic"],
                    "wacc": a.wacc,
                    "spread": result["spread"],
                    "spread_latest_runrate": run_rate_latest,
                    "spread_base_runrate": run_rate_earliest,
                    "delta_spread_bps": delta_bps,
                    "yoy_quarter": yoy_quarter,
                    "spread_yoy_runrate": run_rate_yoy,
                    "delta_spread_yoy_bps": delta_yoy_bps,
                    "qoq_quarter": qoq_quarter,
                    "spread_qoq_runrate": run_rate_qoq,
                    "delta_spread_qoq_bps": delta_qoq_bps,
                }
            )
    return pd.DataFrame.from_records(records)


def build_all(
    workbook_path: Path | str = WORKBOOK_PATH,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load inputs and return ``(trajectory_df, snapshot_df)``."""
    facts, assumptions = load_inputs(workbook_path)
    return build_trajectory(facts, assumptions), build_snapshot(facts, assumptions)


# ---------------------------------------------------------------------------
# Workbook layout mirrors (used by the parity and Checks tests)
# ---------------------------------------------------------------------------

#: Trajectory block anchor row per company; each block spans 6 metric rows.
_TRAJ_BLOCK_START: dict[str, int] = {t: 5 + 7 * i for i, t in enumerate(TICKERS)}

#: Metric-row offset inside a Trajectory block -> DataFrame column.
_TRAJ_ROW_FIELD: dict[int, str] = {
    0: "fact_value_b",
    1: "quarterly_capex_b",
    2: "ai_capex_b",
    3: "ai_revenue_proxy_b",
    4: "forward_roic",
    5: "spread",
}

#: Trajectory quarter -> column letter.
_TRAJ_QUARTER_COL: dict[str, str] = dict(zip(QUARTERS, "CDEFG"))

#: Snapshot ticker -> column letter.
_SNAP_TICKER_COL: dict[str, str] = dict(zip(TICKERS, "BCDEF"))

#: Snapshot row -> (DataFrame column, scenario whose row carries it).
_SNAP_ROW_FIELD: dict[int, tuple[str, Scenario]] = {
    6: ("snapshot_fact_b", Scenario.BASE),
    7: ("ai_share_of_fact", Scenario.BASE),
    8: ("ai_linked_b", Scenario.BASE),
    9: ("annual_capex_guide_b", Scenario.BASE),
    11: ("ai_share_of_capex", Scenario.BASE),
    12: ("ai_capex_b", Scenario.BASE),
    13: ("rpo_duration_years", Scenario.BASE),
    14: ("ai_revenue_proxy_b", Scenario.BASE),
    15: ("nopat_margin", Scenario.BASE),
    17: ("forward_roic", Scenario.BASE),
    18: ("wacc", Scenario.BASE),
    19: ("spread", Scenario.BASE),
    20: ("forward_roic", Scenario.BEAR),
    21: ("spread", Scenario.BEAR),
    22: ("forward_roic", Scenario.BULL),
    23: ("spread", Scenario.BULL),
    25: ("spread_latest_runrate", Scenario.BASE),
    26: ("spread_base_runrate", Scenario.BASE),
    27: ("delta_spread_bps", Scenario.BASE),
}


def trajectory_cell_map(trajectory: pd.DataFrame) -> dict[str, float]:
    """Map ``"Trajectory!C7"``-style addresses to recomputed numeric values."""
    out: dict[str, float] = {}
    for row in trajectory.itertuples():
        start = _TRAJ_BLOCK_START[row.ticker]
        col = _TRAJ_QUARTER_COL[row.quarter]
        for offset, field in _TRAJ_ROW_FIELD.items():
            out[f"Trajectory!{col}{start + offset}"] = float(getattr(row, field))
    return out


def snapshot_cell_map(snapshot: pd.DataFrame) -> dict[str, float]:
    """Map ``"Snapshot!B17"``-style addresses to recomputed numeric values.

    Non-numeric workbook cells (META's ``"N/A"`` duration, the label rows) are
    omitted deliberately: there is no number to compare.
    """
    out: dict[str, float] = {}
    indexed = snapshot.set_index(["ticker", "scenario"])
    for ticker in TICKERS:
        col = _SNAP_TICKER_COL[ticker]
        for wb_row, (field, scenario) in _SNAP_ROW_FIELD.items():
            value = indexed.loc[(ticker, Scenario(scenario).value), field]
            if value is None or (isinstance(value, float) and pd.isna(value)):
                continue  # e.g. META duration -> "N/A" in the workbook
            out[f"Snapshot!{col}{wb_row}"] = float(value)
    return out


def cell_map(trajectory: pd.DataFrame, snapshot: pd.DataFrame) -> dict[str, float]:
    """Combined address -> recomputed value map for both presentation sheets."""
    return {**trajectory_cell_map(trajectory), **snapshot_cell_map(snapshot)}


def _main() -> None:  # pragma: no cover - convenience entry point
    sys.stdout.reconfigure(encoding="utf-8")
    trajectory, snapshot = build_all()
    with pd.option_context("display.width", 200, "display.max_columns", 50):
        print("TRAJECTORY")
        print(trajectory.to_string(index=False))
        print()
        print("SNAPSHOT")
        print(snapshot.to_string(index=False))


if __name__ == "__main__":  # pragma: no cover
    _main()
