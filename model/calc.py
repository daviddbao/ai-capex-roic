"""Pure calculation kernel for the AI capex / forward ROIC model.

No file I/O, no module-level mutable state, no workbook awareness. Every
function here is a deterministic function of its arguments.

Units used throughout
--------------------
* Dollar amounts (``*_b`` suffix): billions of USD.
* Shares, margins, WACC, ROIC and spreads: decimal fractions (0.85 == 85%).
* Durations: years.
* Basis points: 1 ppt == 100 bps, so a decimal spread delta is scaled by 10000.

Fact vs assumption
------------------
Each function's docstring labels every argument as either a SOURCED FACT
(traceable to a filing or an official company statement) or an ANALYST
ASSUMPTION (chosen by the analyst and not disclosed by the company). The
distinction matters because the sensitivity helpers below only ever sweep
assumptions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable, Sequence

__all__ = [
    "ProxyBasis",
    "CapexView",
    "Scenario",
    "SweepParameter",
    "CompanyInputs",
    "ai_revenue_proxy_from_rpo",
    "ai_revenue_proxy_from_revenue",
    "ai_revenue_proxy",
    "ai_capex_trajectory",
    "ai_capex_snapshot",
    "ai_capex",
    "forward_roic",
    "spread",
    "basis_points",
    "nopat_margin_for_scenario",
    "scenario_result",
    "evaluate",
    "sensitivity_curve",
    "linspace",
]


class ProxyBasis(str, Enum):
    """How a company's AI revenue proxy is derived.

    ``RPO``     -- a contracted-backlog balance amortised over an assumed
                   duration (MSFT, GOOG, AMZN, ORCL).
    ``REVENUE`` -- a quarterly revenue line annualised and scaled by an
                   assumed AI attribution (META). No duration exists for this
                   basis; the workbook prints "N/A" in the duration row.
    """

    RPO = "rpo"
    REVENUE = "revenue"


class CapexView(str, Enum):
    """Which capital denominator the ROIC is measured against.

    ``TRAJECTORY`` -- the latest quarter's capex annualised (run-rate basis).
    ``SNAPSHOT``   -- the company's annual capex guide / midpoint / actual.
    """

    TRAJECTORY = "trajectory"
    SNAPSHOT = "snapshot"


class Scenario(str, Enum):
    """Scenario label. Scenarios differ ONLY in the NOPAT margin assumption."""

    BEAR = "bear"
    BASE = "base"
    BULL = "bull"


class SweepParameter(str, Enum):
    """Assumptions that :func:`sensitivity_curve` knows how to sweep."""

    RPO_DURATION_YEARS = "rpo_duration_years"
    AI_SHARE_OF_FACT = "ai_share_of_fact"
    AI_SHARE_OF_CAPEX = "ai_share_of_capex"
    NOPAT_MARGIN = "nopat_margin"


# ---------------------------------------------------------------------------
# AI revenue proxy
# ---------------------------------------------------------------------------


def ai_revenue_proxy_from_rpo(
    rpo_b: float,
    ai_share_of_rpo: float,
    rpo_duration_years: float,
) -> float:
    """Annualised AI revenue proxy for a backlog-based company, in $B.

    ``proxy = rpo_b * ai_share_of_rpo / rpo_duration_years``

    Straight-line amortisation of the AI-attributed slice of contracted
    backlog over its assumed weighted-average life.

    Args:
        rpo_b: SOURCED FACT. Remaining performance obligation / revenue
            backlog / long-term customer commitments, in $B.
        ai_share_of_rpo: ANALYST ASSUMPTION. Fraction of that balance
            attributed to AI, as a decimal. No issuer discloses this.
        rpo_duration_years: ANALYST ASSUMPTION. Weighted-average recognition
            period in years. Must be strictly positive.

    Raises:
        ValueError: if ``rpo_duration_years`` is not strictly positive.
    """
    if rpo_duration_years <= 0:
        raise ValueError(
            f"rpo_duration_years must be > 0 for an RPO-based proxy, got {rpo_duration_years!r}"
        )
    return rpo_b * ai_share_of_rpo / rpo_duration_years


def ai_revenue_proxy_from_revenue(
    quarterly_revenue_b: float,
    ai_share_of_revenue: float,
) -> float:
    """Annualised AI revenue proxy for a revenue-based company, in $B.

    ``proxy = quarterly_revenue_b * 4 * ai_share_of_revenue``

    Used where no contracted-backlog balance exists (META). There is no
    duration term at all on this branch -- the balance being amortised does
    not exist, so the workbook shows "N/A" rather than a number.

    Args:
        quarterly_revenue_b: SOURCED FACT. Total company revenue for the
            quarter, in $B.
        ai_share_of_revenue: ANALYST ASSUMPTION. Fraction of total revenue
            attributed to AI, as a decimal.
    """
    return quarterly_revenue_b * 4 * ai_share_of_revenue


def ai_revenue_proxy(
    fact_value_b: float,
    ai_share_of_fact: float,
    basis: ProxyBasis,
    rpo_duration_years: float | None = None,
) -> float:
    """Annualised AI revenue proxy in $B, dispatching on ``basis``.

    Args:
        fact_value_b: SOURCED FACT. RPO/backlog balance ($B) when
            ``basis`` is ``RPO``; quarterly revenue ($B) when ``REVENUE``.
        ai_share_of_fact: ANALYST ASSUMPTION. AI attribution, as a decimal.
        basis: model structure (not itself an estimate) -- which formula
            applies to this company.
        rpo_duration_years: ANALYST ASSUMPTION. Required and positive for
            ``RPO``; must be ``None`` for ``REVENUE``, where duration is
            genuinely not applicable rather than merely unknown.

    Raises:
        ValueError: if the duration argument does not match the basis.
    """
    basis = ProxyBasis(basis)
    if basis is ProxyBasis.RPO:
        if rpo_duration_years is None:
            raise ValueError("rpo_duration_years is required for an RPO-based proxy")
        return ai_revenue_proxy_from_rpo(fact_value_b, ai_share_of_fact, rpo_duration_years)
    if rpo_duration_years is not None:
        raise ValueError(
            "rpo_duration_years is not applicable to a revenue-based proxy; pass None"
        )
    return ai_revenue_proxy_from_revenue(fact_value_b, ai_share_of_fact)


# ---------------------------------------------------------------------------
# AI capex (the ROIC denominator)
# ---------------------------------------------------------------------------


def ai_capex_trajectory(quarterly_capex_b: float, ai_share_of_capex: float) -> float:
    """Annualised run-rate AI capex in $B.

    ``ai_capex = quarterly_capex_b * 4 * ai_share_of_capex``

    Args:
        quarterly_capex_b: SOURCED FACT. The quarter's capex on that
            company's own reported definition, in $B. Definitions are not
            uniform across the five companies (see README).
        ai_share_of_capex: ANALYST ASSUMPTION. Fraction of capex serving AI
            workloads, as a decimal.
    """
    return quarterly_capex_b * 4 * ai_share_of_capex


def ai_capex_snapshot(annual_capex_guide_b: float, ai_share_of_capex: float) -> float:
    """Annual-plan AI capex in $B.

    ``ai_capex = annual_capex_guide_b * ai_share_of_capex``

    Args:
        annual_capex_guide_b: SOURCED FACT (company guide, range midpoint, or
            latest reported full-year actual), in $B. Where it is a midpoint
            the midpoint itself is an analyst construction from a disclosed
            range.
        ai_share_of_capex: ANALYST ASSUMPTION. Fraction of capex serving AI
            workloads, as a decimal.
    """
    return annual_capex_guide_b * ai_share_of_capex


def ai_capex(
    view: CapexView,
    ai_share_of_capex: float,
    quarterly_capex_b: float | None = None,
    annual_capex_guide_b: float | None = None,
) -> float:
    """AI capex in $B for the requested view.

    Args:
        view: which denominator to use.
        ai_share_of_capex: ANALYST ASSUMPTION, decimal.
        quarterly_capex_b: SOURCED FACT, required for ``TRAJECTORY``.
        annual_capex_guide_b: SOURCED FACT, required for ``SNAPSHOT``.

    Raises:
        ValueError: if the required input for the chosen view is missing.
    """
    view = CapexView(view)
    if view is CapexView.TRAJECTORY:
        if quarterly_capex_b is None:
            raise ValueError("quarterly_capex_b is required for the trajectory view")
        return ai_capex_trajectory(quarterly_capex_b, ai_share_of_capex)
    if annual_capex_guide_b is None:
        raise ValueError("annual_capex_guide_b is required for the snapshot view")
    return ai_capex_snapshot(annual_capex_guide_b, ai_share_of_capex)


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------


def forward_roic(
    ai_revenue_proxy_b: float,
    nopat_margin: float,
    ai_capex_b: float,
) -> float:
    """Forward return on invested capital, as a decimal.

    ``roic = ai_revenue_proxy_b * nopat_margin / ai_capex_b``

    Args:
        ai_revenue_proxy_b: DERIVED from a sourced fact and assumptions,
            in $B (see :func:`ai_revenue_proxy`).
        nopat_margin: ANALYST ASSUMPTION. Net operating profit after tax as a
            fraction of the AI revenue proxy.
        ai_capex_b: DERIVED, in $B (see :func:`ai_capex`). Must be non-zero.

    Raises:
        ZeroDivisionError: if ``ai_capex_b`` is zero.
    """
    if ai_capex_b == 0:
        raise ZeroDivisionError("ai_capex_b must be non-zero to compute forward ROIC")
    return ai_revenue_proxy_b * nopat_margin / ai_capex_b


def spread(forward_roic_value: float, wacc: float) -> float:
    """Forward ROIC less WACC, as a decimal (i.e. percentage points / 100).

    Args:
        forward_roic_value: DERIVED, decimal.
        wacc: ANALYST-SELECTED BENCHMARK. Damodaran January 2026 U.S. sector
            average cost of capital, decimal. Not a company-specific WACC.
    """
    return forward_roic_value - wacc


def basis_points(spread_delta: float) -> float:
    """Convert a decimal spread difference to basis points (``delta * 10000``)."""
    return spread_delta * 10000


# ---------------------------------------------------------------------------
# Scenario helper
# ---------------------------------------------------------------------------


def nopat_margin_for_scenario(
    scenario: Scenario,
    nopat_margin_bear: float,
    nopat_margin_base: float,
    nopat_margin_bull: float,
) -> float:
    """Select the NOPAT margin for a scenario.

    Scenarios in this model differ ONLY in NOPAT margin; facts, AI shares,
    duration, capex and WACC are held constant across bear/base/bull.

    Args:
        scenario: which scenario to select.
        nopat_margin_bear: ANALYST ASSUMPTION, decimal.
        nopat_margin_base: ANALYST ASSUMPTION, decimal.
        nopat_margin_bull: ANALYST ASSUMPTION, decimal.
    """
    scenario = Scenario(scenario)
    return {
        Scenario.BEAR: nopat_margin_bear,
        Scenario.BASE: nopat_margin_base,
        Scenario.BULL: nopat_margin_bull,
    }[scenario]


# ---------------------------------------------------------------------------
# Company bundle + end-to-end evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompanyInputs:
    """Everything needed to evaluate one company for one quarter.

    Dollar fields are $B; shares, margins and WACC are decimals.

    Attributes:
        ticker: company identifier.
        proxy_basis: model structure -- RPO or REVENUE branch.
        fact_value_b: SOURCED FACT. RPO/backlog balance, or quarterly revenue
            when ``proxy_basis`` is ``REVENUE``.
        quarterly_capex_b: SOURCED FACT. The quarter's capex.
        annual_capex_guide_b: SOURCED FACT. Annual capex guide / midpoint /
            actual used by the snapshot view.
        ai_share_of_fact: ANALYST ASSUMPTION.
        rpo_duration_years: ANALYST ASSUMPTION; ``None`` on the revenue basis,
            where duration is not applicable.
        ai_share_of_capex: ANALYST ASSUMPTION.
        nopat_margin_bear / _base / _bull: ANALYST ASSUMPTIONS.
        wacc: ANALYST-SELECTED SECTOR BENCHMARK.
    """

    ticker: str
    proxy_basis: ProxyBasis
    fact_value_b: float
    quarterly_capex_b: float
    annual_capex_guide_b: float
    ai_share_of_fact: float
    rpo_duration_years: float | None
    ai_share_of_capex: float
    nopat_margin_bear: float
    nopat_margin_base: float
    nopat_margin_bull: float
    wacc: float

    def replace(self, **changes: Any) -> "CompanyInputs":
        """Return a copy with the named fields replaced."""
        unknown = set(changes) - set(self.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown CompanyInputs field(s): {sorted(unknown)}")
        data = asdict(self)
        data.update(changes)
        return CompanyInputs(**data)

    def to_dict(self) -> dict[str, Any]:
        """JSON-serialisable mapping of this bundle."""
        data = asdict(self)
        data["proxy_basis"] = ProxyBasis(self.proxy_basis).value
        return data


def scenario_result(
    inputs: CompanyInputs,
    view: CapexView = CapexView.TRAJECTORY,
    scenario: Scenario = Scenario.BASE,
) -> dict[str, Any]:
    """Evaluate one company under one view and one scenario.

    Returns a JSON-serialisable dict with keys ``ticker``, ``view``,
    ``scenario``, ``nopat_margin``, ``ai_revenue_proxy_b``, ``ai_capex_b``,
    ``forward_roic``, ``spread`` and ``spread_bps``.
    """
    view = CapexView(view)
    scenario = Scenario(scenario)
    margin = nopat_margin_for_scenario(
        scenario,
        inputs.nopat_margin_bear,
        inputs.nopat_margin_base,
        inputs.nopat_margin_bull,
    )
    proxy = ai_revenue_proxy(
        inputs.fact_value_b,
        inputs.ai_share_of_fact,
        inputs.proxy_basis,
        inputs.rpo_duration_years,
    )
    capex = ai_capex(
        view,
        inputs.ai_share_of_capex,
        quarterly_capex_b=inputs.quarterly_capex_b,
        annual_capex_guide_b=inputs.annual_capex_guide_b,
    )
    roic = forward_roic(proxy, margin, capex)
    spr = spread(roic, inputs.wacc)
    return {
        "ticker": inputs.ticker,
        "view": view.value,
        "scenario": scenario.value,
        "nopat_margin": margin,
        "ai_revenue_proxy_b": proxy,
        "ai_capex_b": capex,
        "forward_roic": roic,
        "spread": spr,
        "spread_bps": basis_points(spr),
    }


def evaluate(
    inputs: CompanyInputs,
    view: CapexView = CapexView.TRAJECTORY,
    scenarios: Iterable[Scenario] = (Scenario.BEAR, Scenario.BASE, Scenario.BULL),
) -> list[dict[str, Any]]:
    """Evaluate one company under one view across several scenarios."""
    return [scenario_result(inputs, view, s) for s in scenarios]


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


def linspace(start: float, stop: float, count: int) -> list[float]:
    """Inclusive evenly spaced values; a stdlib stand-in for ``numpy.linspace``."""
    if count < 2:
        raise ValueError("count must be >= 2")
    step = (stop - start) / (count - 1)
    return [start + step * i for i in range(count)]


def _apply_sweep(
    inputs: CompanyInputs, parameter: SweepParameter, value: float
) -> CompanyInputs:
    """Return a copy of ``inputs`` with ``parameter`` set to ``value``.

    NOPAT margin is swept by overriding all three scenario margins to the same
    value, so the caller's chosen scenario reads back exactly ``value``.
    """
    if parameter is SweepParameter.RPO_DURATION_YEARS:
        if ProxyBasis(inputs.proxy_basis) is ProxyBasis.REVENUE:
            raise ValueError(
                f"{inputs.ticker} uses a revenue-based proxy; RPO duration is not "
                "applicable and cannot be swept"
            )
        return inputs.replace(rpo_duration_years=value)
    if parameter is SweepParameter.AI_SHARE_OF_FACT:
        return inputs.replace(ai_share_of_fact=value)
    if parameter is SweepParameter.AI_SHARE_OF_CAPEX:
        return inputs.replace(ai_share_of_capex=value)
    return inputs.replace(
        nopat_margin_bear=value, nopat_margin_base=value, nopat_margin_bull=value
    )


def sensitivity_curve(
    inputs: CompanyInputs,
    parameter: SweepParameter | str,
    values: Sequence[float],
    view: CapexView = CapexView.TRAJECTORY,
    scenario: Scenario = Scenario.BASE,
) -> list[dict[str, Any]]:
    """Sweep one assumption and return the resulting spread curve.

    Args:
        inputs: the company's baseline inputs.
        parameter: which ANALYST ASSUMPTION to vary --
            ``"rpo_duration_years"`` (years), ``"ai_share_of_fact"``,
            ``"ai_share_of_capex"`` or ``"nopat_margin"`` (decimals).
            Sweeping duration on a revenue-based company raises ``ValueError``.
        values: the values to sweep, in the parameter's own units.
        view: capital denominator to hold fixed while sweeping.
        scenario: scenario to hold fixed. Ignored in effect when sweeping
            ``nopat_margin``, since that sweep overrides all three margins.

    Returns:
        A list of JSON-serialisable dicts, one per swept value, each with
        ``ticker``, ``view``, ``scenario``, ``parameter``, ``value``,
        ``ai_revenue_proxy_b``, ``ai_capex_b``, ``forward_roic``, ``wacc``,
        ``spread`` and ``spread_bps``. Ordered as ``values`` was given.
    """
    parameter = SweepParameter(parameter)
    view = CapexView(view)
    scenario = Scenario(scenario)
    curve: list[dict[str, Any]] = []
    for value in values:
        swept = _apply_sweep(inputs, parameter, value)
        point = scenario_result(swept, view, scenario)
        point["parameter"] = parameter.value
        point["value"] = value
        point["wacc"] = swept.wacc
        curve.append(point)
    return curve
