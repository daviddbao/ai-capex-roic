# `model/` — AI capex / forward ROIC calculation module

A pure-Python reimplementation of `ai_capex_forward_roic_analysis_v02.xlsx`,
verified cell-for-cell against the workbook's cached values.

| File | Role |
|---|---|
| `calc.py` | Pure functions. No I/O, no globals, no workbook awareness. |
| `build.py` | Reads the workbook's `Inputs` sheet, assembles the Trajectory and Snapshot tables as tidy DataFrames. All I/O lives here. |
| `tests/test_parity.py` | Every numeric `Trajectory` / `Snapshot` cell vs. this implementation. |
| `tests/test_checks.py` | The workbook's 135-row `Checks` sheet, ported. |

The workbook is opened read-only and never written.

## Running the tests

```bash
python -m pip install openpyxl pandas pytest
cd <repo root>          # the directory containing model/ and the .xlsx
python -m pytest model/tests -q
```

Expected: **534 passed**. That is 244 individual cell-parity assertions
(150 Trajectory cells, 94 Snapshot cells — every numeric cell on both sheets),
270 ported `Checks` assertions (135 at the sheet's own tolerance, 135 at a
tighter `rtol=1e-15`), plus structural and sensitivity tests.

Parity tolerance is `rtol=1e-12` with `abs=0.0`. This is deterministic
IEEE-754 arithmetic replayed in the same operation order as the Excel
formulas, so exact agreement is the expectation. **Do not loosen the
tolerance to make a failure pass** — a failure means the workbook and this
implementation genuinely disagree, and that is a finding to investigate.

## The model

```
AI revenue proxy (RPO basis, MSFT/GOOG/AMZN/ORCL)
    = rpo * ai_share_of_rpo / rpo_duration_years
AI revenue proxy (revenue basis, META — no duration exists)
    = quarterly_revenue * 4 * ai_share_of_revenue

AI capex, TRAJECTORY view = quarterly_capex * 4 * ai_share_of_capex
AI capex, SNAPSHOT   view = annual_capex_guide * ai_share_of_capex

forward_roic = ai_revenue_proxy * nopat_margin / ai_capex
spread       = forward_roic - wacc
```

Scenarios (bear / base / bull) change the NOPAT margin and nothing else.
Trajectory reports base only; Snapshot reports all three, plus the Q2 26 and
Q2 25 spreads on the **trajectory** (run-rate) basis and their delta in basis
points (`delta * 10000`).

Dollar amounts are $B; shares, margins, WACC, ROIC and spreads are decimals.

### `calc.py` public API

Enums: `ProxyBasis` (RPO / REVENUE), `CapexView` (TRAJECTORY / SNAPSHOT),
`Scenario` (BEAR / BASE / BULL), `SweepParameter`.

```python
ai_revenue_proxy_from_rpo(rpo_b, ai_share_of_rpo, rpo_duration_years)
ai_revenue_proxy_from_revenue(quarterly_revenue_b, ai_share_of_revenue)
ai_revenue_proxy(fact_value_b, ai_share_of_fact, basis, rpo_duration_years=None)
ai_capex_trajectory(quarterly_capex_b, ai_share_of_capex)
ai_capex_snapshot(annual_capex_guide_b, ai_share_of_capex)
ai_capex(view, ai_share_of_capex, quarterly_capex_b=None, annual_capex_guide_b=None)
forward_roic(ai_revenue_proxy_b, nopat_margin, ai_capex_b)
spread(forward_roic_value, wacc)
basis_points(spread_delta)
nopat_margin_for_scenario(scenario, bear, base, bull)      # scenario helper
scenario_result(inputs, view=TRAJECTORY, scenario=BASE)    # -> dict
evaluate(inputs, view=TRAJECTORY, scenarios=(BEAR, BASE, BULL))
sensitivity_curve(inputs, parameter, values, view=TRAJECTORY, scenario=BASE)
linspace(start, stop, count)
CompanyInputs(...)   # frozen dataclass; .replace(**changes), .to_dict()
```

META's missing duration is modelled as `rpo_duration_years=None` on the
`ProxyBasis.REVENUE` branch, never as a sentinel number. Passing a duration on
the revenue branch, or omitting one on the RPO branch, raises `ValueError`.

### Sensitivity helper

```python
from model import build, calc

facts, assumptions = build.load_inputs()
fact = next(f for f in facts if f.ticker == "AMZN" and f.quarter == "Q2 26")
inputs = build.company_inputs(fact, assumptions)

curve = calc.sensitivity_curve(inputs, "rpo_duration_years", calc.linspace(3, 7, 9))
```

Returns a list of plain JSON-serialisable dicts, one per swept value, ordered
as given: `ticker`, `view`, `scenario`, `parameter`, `value`, `nopat_margin`,
`ai_revenue_proxy_b`, `ai_capex_b`, `forward_roic`, `wacc`, `spread`,
`spread_bps`. Sweepable parameters are `rpo_duration_years`,
`ai_share_of_fact`, `ai_share_of_capex` and `nopat_margin` — all analyst
assumptions, never sourced facts. Sweeping duration on META raises
`ValueError`, because duration is not applicable to that branch.

## Known weaknesses

These are properties of the model itself, not of this implementation. Every
one of them is inherited faithfully from the workbook.

**1. Amazon's 4.0-year duration assumption is the largest single sensitivity.**
Amazon disclosed a 6.4-year weighted-average remaining contract life at
June 30, 2026. The model retains 4.0 years for comparability with v01. Because
the proxy divides by duration, the shorter assumption materially accelerates
recognised revenue and overstates returns. Swapping in the disclosed 6.4 years
takes AMZN's Q2 26 run-rate spread from **+447 bps to +7 bps** (snapshot basis:
+546 bps to +69 bps) — the conclusion "Amazon earns above its cost of capital"
does not survive the company's own disclosure.

**2. Oracle's 85% AI attribution and 5-year duration are unverified.** Oracle
reports company-wide RPO. It does not disclose that 85% of it is AI-linked,
nor that recognition is straight-line over five years. Both numbers are
analyst choices, and Oracle shows the largest modelled spread of the five.
Cutting the AI share to 50% moves the Q2 26 run-rate spread from +2,505 bps to
+1,151 bps; stretching duration to 7 years moves it to +1,566 bps. Oracle also
disclosed that $75B of prepaid or customer-supplied hardware reduces its own
capital requirement, which the capex denominator does not reflect.

**3. Microsoft's improved snapshot spread is partly a lease-classification
artefact.** The snapshot spread rose because the reported CY2026 capex
outlook fell to roughly $175B from roughly $190B. Management attributed that
reduction to longer datacenter useful lives shifting future leases from
finance leases (included in Microsoft's capex metric) to operating leases
(excluded from it), and said underlying investment expectations were
unchanged. The denominator shrank; the spending did not. Read the trajectory
view, which uses quarterly capex, alongside it.

**4. Further caveats carried from the methodology doc.**
- Microsoft disclosed a 2.3-year commercial-RPO duration including OpenAI; the
  model retains 2.5 years (using 2.3 would raise the Q2 26 run-rate spread from
  +1,984 bps to +2,238 bps).
- Alphabet's backlog definition expanded in Q1 2026 and Q2 Cloud backlog now
  includes TPU system-sale agreements, so 2025 figures sit on an older
  definition — the series has a comparability break.
- Capex definitions are not uniform: Microsoft uses management capex including
  finance-lease commencement effects, Alphabet and Oracle use cash PP&E/capex,
  Amazon uses gross productive-asset cash payments, Meta includes finance-lease
  principal. Cross-company capex comparisons are approximate.
- Annual denominators mix kinds: Alphabet and Meta are analyst midpoints of
  disclosed ranges, Oracle is a completed FY2026 actual (its FY2027 guide is a
  non-comparable net-cash-outlay measure), Amazon is a carried-forward plan
  with no Q2 replacement.
- WACC values are Damodaran January 2026 U.S. *sector* averages, not
  company-specific costs of capital.
- Meta has no backlog at all: its proxy annualises a single quarter of total
  company revenue times a 20% AI attribution that Meta does not report.
