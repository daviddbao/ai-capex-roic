# Data layer schema

Canonical, version-controllable extraction of `ai_capex_forward_roic_analysis_v02.xlsx`
(5 sheets: `Trajectory`, `Snapshot`, `Inputs`, `Sources & Notes`, `Checks`).

The workbook is the **audit-of-record** and is never modified by this pipeline. Everything
here is produced by a read-only `openpyxl` pass (`data_only=False` for formulas, comments and
fills; `data_only=True` for cached values) run by `scripts/extract_workbook.py`. Re-running the
script regenerates every file in `data/` deterministically.

Workbook SHA-256: `b0f2f3284fd37ac50653366af1e82a402c0a3bab96ddb619f64a6682d99ddd52`

---

## 0. Conventions that apply to every file

### Units

| Convention | Meaning |
|---|---|
| `*_usd_b`, "($B)" | US dollars in **billions**. `678` means $678.0B. Never scaled, never rounded. |
| shares, margins, WACC, ROIC | **decimals**. `0.3` = 30%, `0.0934` = 9.34%. |
| spreads | **decimals** that the workbook *displays* as percentage points. `0.19842209469153516` is displayed as `19.8 ppt`. Multiply by 100 to get ppt. |
| `*_bps` | **basis points**. `234.70125804806895` = +235 bps. A decimal spread delta × 10,000. |
| durations | **years** (decimal). |
| dates | ISO `YYYY-MM-DD`. |

### Provenance classes

Every value in this data layer is one of:

* **FACT** — sourced from an SEC filing or an official company disclosure. Blue fill
  (`FFEAF2F8`) in the workbook, hyperlinked, and carrying a cell note with the reported value,
  definition, derivation and public URL.
* **ASSUMPTION** — analyst judgement, not disclosed by the company. Yellow fill (`FFFFF2CC`).
* **DERIVED** — computed by the workbook from facts and assumptions (formula cells).
* **LABEL** — descriptive text, headers, captions; no analytic content.

Encoding: all files are **UTF-8**, LF line endings, RFC-4180 quoting (`csv` module defaults).
Text fields contain Unicode (`×`, `÷`, `Δ`, `—`, en-dashes) and embedded newlines inside
quoted fields (notably `cell_notes.note_text`). On Windows, `sys.stdout.reconfigure(encoding='utf-8')`
before printing any of it.

### Numeric fidelity

Floats are written with Python `repr()`, i.e. the shortest string that round-trips to the exact
IEEE-754 double stored in the workbook. `float(value)` reproduces the cached cell bit-for-bit.
Nothing is rounded anywhere in `data/`.

---

## 1. `data/facts.csv` — filing facts, one row per company-quarter

25 rows (5 companies × 5 quarters), from `Inputs!A5:N29`. Every non-label column here is a
**FACT**.

| column | type | unit | class | meaning |
|---|---|---|---|---|
| `company` | string | — | LABEL | Registrant name (`Microsoft`, `Alphabet`, `Amazon`, `Oracle`, `Meta Platforms`). |
| `ticker` | string | — | LABEL | `MSFT` \| `GOOG` \| `AMZN` \| `ORCL` \| `META`. Join key. |
| `report_bucket` | string | — | LABEL | Calendar bucket used by the presentation sheets: `Q2 25`, `Q3 25`, `Q4 25`, `Q1 26`, `Q2 26`. **This is the model's period key**, not the issuer's own label. |
| `fiscal_period` | string | — | FACT | The issuer's own fiscal label (`FY26 Q4`, `Q2 2026`, …). MSFT and ORCL fiscal quarters do not align with the calendar bucket. |
| `period_end` | date `YYYY-MM-DD` | — | FACT | Balance-sheet / period end date as filed. ORCL ends Feb/May/Aug/Nov; the other four end Mar/Jun/Sep/Dec. |
| `rpo_backlog_or_revenue_usd_b` | float | $B | FACT | The headline disclosed quantity. **Not one metric** — see `fact_metric`. |
| `fact_metric` | string | — | FACT | What `rpo_backlog_or_revenue_usd_b` actually is (see comparability note below). |
| `quarterly_capex_usd_b` | float | $B | FACT | Capex for the quarter, on the issuer's own definition. |
| `capex_definition` | string | — | FACT | The exact capex definition for that company-quarter, including whether the quarter was derived from cumulative filing values. |
| `fact_source_url` | url | — | FACT | Public URL for the headline fact. Joins to `sources.url`. |
| `capex_source_url` | url | — | FACT | Public URL for the capex figure. |
| `evidence_derivation` | string | — | FACT | Free text: reported value, definition and, where the quarter was backed out of cumulative figures, the full arithmetic. |
| `fact_source_id` | string | — | key | Joins to `sources.source_id`, e.g. `MSFT-Q225-FACT`. |
| `capex_source_id` | string | — | key | Joins to `sources.source_id`, e.g. `MSFT-Q225-CAPEX`. |

### Comparability warning — `fact_metric` is not one metric

| ticker | `fact_metric` | proxy branch |
|---|---|---|
| MSFT | Commercial remaining performance obligation | RPO ÷ duration |
| GOOG | Revenue backlog / remaining performance obligations | RPO ÷ duration |
| AMZN | Long-term customer commitments, primarily AWS | RPO ÷ duration |
| ORCL | Remaining performance obligations | RPO ÷ duration |
| META | Quarterly revenue | revenue × 4 |

Alphabet's backlog definition expanded in Q1 2026 (and Q2 2026 Cloud backlog now includes TPU
system-sale agreements): Q1 26→Q2 26 is comparable with each other, but **2025 figures are on
the older definition**. Meta discloses no backlog at all, so the model substitutes annualized
total-company revenue — a different economic object from the other four.

### Comparability warning — capex definitions differ per company

**These capex figures are NOT directly comparable across companies.** Cross-company level
comparisons of capex, and therefore of forward ROIC and spread, are apples-to-oranges; only the
within-company time series is like-for-like (and only where `capex_definition` is stable).

| ticker | definition used | note |
|---|---|---|
| MSFT | Company/management-reported capex **including finance leases** (Q2 26: "including finance-lease commencement effects") | Not a GAAP cash-flow line; sourced from the official earnings call. |
| GOOG | **Cash purchases of property and equipment** (GAAP cash-flow line) | Q2 25, Q3 25, Q4 25 quarters derived by differencing cumulative year-to-date figures. |
| AMZN | **Cash payments to acquire productive assets** (SEC XBRL; Q2 26 uses the gross series) | Gross productive-asset cash payments — a broader base than pure PP&E. |
| ORCL | **Cash capital expenditures** (GAAP) | Q2 25, Q4 25, Q1 26 quarters derived from cumulative filing values. |
| META | **Company-defined capex including finance-lease principal payments** | Wider than the cash PP&E line; Q4 25 quarter derived (FY less nine months). |

`capex_definition` varies *within* a company across quarters too (wording changes, and derived
vs directly-reported quarters). Always read the per-row value, not the per-company summary.

---

## 2. `data/assumptions.csv` — analyst assumptions, one row per company-version

5 rows, from `Inputs!P5:AC9`. This is the **versioned** table: assumptions were deliberately
frozen across v01 → v02 so that movements stay comparable, so a future change must be **appended
as a new row with a later `effective_from`**, never edited in place. `(ticker, effective_from)`
is the primary key; the applicable row for a period is the one with the greatest
`effective_from` ≤ that period's `period_end`.

| column | type | unit | class | meaning |
|---|---|---|---|---|
| `ticker` | string | — | key | Joins to `facts.ticker`. |
| `company` | string | — | LABEL | Derived from `facts.csv` for readability; not present in the assumptions block of the workbook. |
| `effective_from` | date | — | key (added) | Earliest `period_end` this row covers, per company: `2025-06-30` for MSFT/GOOG/AMZN/META, `2025-05-31` for ORCL (May fiscal year end). **Not in the workbook** — added so assumption changes can be versioned rather than overwritten. |
| `model_version` | string | — | metadata (added) | `v02`. Constant for this extraction; distinguishes rows appended later. |
| `ai_revenue_proxy` | string | — | LABEL | The proxy formula in words, e.g. `Commercial RPO × assumed AI share ÷ assumed duration`. Determines which branch of the model applies (`÷ duration` vs `× 4`). |
| `ai_share_of_rpo_revenue` | float | decimal | **ASSUMPTION** | Fraction of the headline fact attributed to AI. MSFT 0.5, GOOG 0.65, AMZN 0.55, ORCL 0.85, META 0.2. |
| `rpo_duration_years` | float | years | **ASSUMPTION** | Straight-line recognition period for the backlog. MSFT 2.5, GOOG 2.5, AMZN 4, ORCL 5. **Empty for META** — META uses the revenue × 4 branch and has no duration. Disclosed durations differ: MSFT disclosed 2.3y, AMZN disclosed 6.4y; the model retains 2.5 and 4.0 for v01 comparability. AMZN is the largest identifiable duration sensitivity. |
| `ai_share_of_capex` | float | decimal | **ASSUMPTION** | Fraction of capex attributed to AI. MSFT 0.85, GOOG 0.8, AMZN 0.75, ORCL 0.9, META 0.9. |
| `nopat_margin_bear` | float | decimal | **ASSUMPTION** | Bear-case NOPAT margin on the AI revenue proxy. Snapshot only. |
| `nopat_margin_base` | float | decimal | **ASSUMPTION** | Base-case NOPAT margin. Used by **both** Trajectory and Snapshot. |
| `nopat_margin_bull` | float | decimal | **ASSUMPTION** | Bull-case NOPAT margin. Snapshot only. |
| `wacc` | float | decimal | FACT (published) / **ASSUMPTION (selection)** | Damodaran January 2026 U.S. industry-average cost of capital. The *number* is a published third-party datum (blue-filled in the workbook and hyperlinked); the *choice of sector* is analyst judgement, and an industry average is **not** a company-specific WACC. |
| `damodaran_sector_date` | string | — | **ASSUMPTION** | Which Damodaran sector row was selected, and its vintage. |
| `annual_capex_guide_midpoint_actual_usd_b` | float | $B | FACT (with analyst framing) | Snapshot denominator base. MSFT 175 (reported outlook), GOOG 200 (**midpoint** of $195–205B), AMZN 200 (latest unchanged plan), ORCL 55.663 (FY2026 **actual**, not a guide), META 137.5 (**midpoint** of $130–145B). Midpoint selection and the choice to use an actual are analyst decisions — read `plan_basis` and `source_assumption_caveat` before comparing across companies. |
| `plan_basis` | string | — | LABEL | One-line statement of what the denominator is. |
| `plan_source_url` | url | — | FACT | Public URL for the plan/guide/actual. Joins to `sources.url` (`*-PLAN`). |
| `source_assumption_caveat` | string | — | LABEL | Full caveat text, incl. Microsoft's useful-life/lease-classification driven outlook cut and Oracle's non-comparable $70B FY2027 *net cash outlay* guide. |

---

## 3. `data/sources.csv` — deduplicated source registry

62 rows, unique on `source_id`. Rows 1–60 are the workbook's own ledger (`Sources & Notes!A5:L64`);
2 rows are supplementary (see `in_workbook_ledger`).

| column | type | class | meaning |
|---|---|---|---|
| `source_id` | string | key | e.g. `MSFT-Q225-FACT`, `GOOG-Q226-CAPEX`, `ORCL-PLAN`, `META-WACC`. Joins from `facts.fact_source_id` / `facts.capex_source_id`. |
| `url` | url | FACT | Public URL (SEC EDGAR, company IR, or Damodaran). |
| `company` | string | LABEL | Registrant name. |
| `period` | string | LABEL | `<fiscal label> / <period end>`, e.g. `FY25 Q4 / 2025-06-30`; `Latest snapshot` for plan and WACC rows. |
| `kind` | enum | LABEL | `fact` (25) \| `capex` (26) \| `plan` (6) \| `wacc` (5). Derived from the `source_id` suffix. |
| `title_or_description` | string | LABEL | `<filing or disclosure> — <metric>`, e.g. `msft-20250630.htm — Commercial remaining performance obligation`. |
| `local_path_if_any` | path | LABEL | Repo-relative path to the preserved filing copy under `01_sources/company_filings/`. **That directory is not part of this repo**; the paths are recorded for audit continuity. Populated for 41 of 62 rows (the 20 quarterly filings for Q3 25 → Q2 26, plus the Oracle Q4 FY26 slides). Empty for all Q2 25 rows, all `*-PLAN` and all `*-WACC` rows. |
| `reported_value` | float | FACT | The value as recorded in the ledger, in $B for dollar rows and decimals for WACC rows. |
| `classification` | string | LABEL | The ledger's own classification, e.g. `SEC filing`, `Official company outlook`, `Damodaran industry data / analyst sector selection`. |
| `evidence_derivation` | string | FACT | Reported value and, where applicable, the derivation arithmetic. |
| `status` | string | LABEL | `Verified` \| `Verified / disclosed basis` \| `Cited in cell notes`. |
| `caveat` | string | LABEL | Per-source caveat. |
| `in_workbook_ledger` | enum | metadata (added) | `yes` for the 60 ledger rows; `no` for the 2 supplementary rows below. |

Two sources are cited **only inside cell notes** and have no row in the workbook's ledger. They
are recorded here with synthetic ids so the registry is complete, and flagged so nobody mistakes
them for ledger entries:

* `ORCL-FY25Q3-10Q-DERIV` — `orcl-20250228.htm`, the nine-month cumulative capex ($12.135B) used
  to derive Oracle's Q2 25 quarter capex ($21.215B − $12.135B = $9.080B).
* `ORCL-Q4FY26-SLIDES` — Oracle's official Q4 FY26 earnings slides, which guide to ~$70B FY2027
  **net cash outlay** for capex. Explicitly **rejected** as the snapshot denominator because it
  is a non-GAAP measure netting capex financing and customer prepayments.

---

## 4. `data/cell_notes.csv` and `data/hyperlinks.csv` — the audit trail

### `data/cell_notes.csv` — 455 rows, every cell comment in the workbook

All 455 are URL-bearing. This is the audit trail: each note carries the reported value, its
definition, the derivation and the public URL for the cell it is attached to. Distribution:
`Trajectory` 150, `Snapshot` 100, `Inputs` 145, `Sources & Notes` 60, `Checks` 0.

| column | type | meaning |
|---|---|---|
| `sheet` | string | Worksheet name (`Sources & Notes` contains an ampersand). |
| `cell` | string | A1-style reference. |
| `row` | int | Row number (convenience). |
| `column` | string | Column letter (convenience). |
| `author` | string | Comment author (`Codex` throughout). |
| `note_text` | string | **Full** note text, `\n`-separated inside a quoted CSV field. Typical shape: `<TICKER> <bucket> — <metric>` / `Value: $X.XXXB` / `Public source: <url>` / `Evidence: …` / `Local source: 01_sources/…` (when preserved) / `Classification: …`. |

### `data/hyperlinks.csv` — 240 rows, every clickable hyperlink

Distribution: `Inputs` 115, `Sources & Notes` 60, `Trajectory` 50, `Snapshot` 15, `Checks` 0.
35 distinct targets.

| column | type | meaning |
|---|---|---|
| `sheet`, `cell`, `row`, `column` | | Location, as above. |
| `cell_text` | string | The **cached displayed value** of the cell (a number for linked fact cells, the URL itself on the ledger sheet). |
| `display` | string | The OOXML `display` attribute where present (empty for 115 links whose display text is the cell value). |
| `target` | url | Link destination. Never empty. |
| `location` | string | In-workbook anchor, if any (all empty here). |
| `tooltip` | string | Hyperlink tooltip, if any (all empty here). |

---

## 5. `data/provenance.csv` — the fact/assumption boundary of `Inputs`

451 rows: every cell in `Inputs!A1:AC29` that carries a value or a fill. This preserves the
workbook's colour coding outside Excel.

| column | type | meaning |
|---|---|---|
| `sheet` | string | Always `Inputs`. |
| `cell`, `row`, `column` | | Location. |
| `header` | string | The `Inputs` row-4 header governing that column (empty for rows 1–4). |
| `fill_rgb` | string | ARGB fill, e.g. `FFEAF2F8`. Empty when the cell has no fill. |
| `fill_name` | string | Human name: `light blue`, `light yellow`, `dark blue header`, `light grey banner`. |
| `fill_class` | enum | `fact` \| `assumption` \| `other`. Rows 1–4 (titles, banner, headers) are forced to `other` regardless of fill. |
| `has_value` | 0/1 | Whether the cell holds a value. |
| `value_preview` | string | First 200 characters of the cell value. Truncated on purpose — the authoritative values live in `facts.csv` / `assumptions.csv`. |

**Counts: 115 `fact` cells, 30 `assumption` cells, 306 `other`.**

* `fact` (blue `FFEAF2F8`), 115 = `F`, `H`, `J`, `K` × rows 5–29 (100: the headline fact, the
  quarterly capex and their two source URLs) + `X`, `Z`, `AB` × rows 5–9 (15: WACC, annual capex
  denominator, plan URL).
* `assumption` (yellow `FFFFF2CC`), 30 = `R`, `S`, `T`, `U`, `V`, `W` × rows 5–9 (AI share of
  RPO/revenue, RPO duration, AI share of capex, and the three NOPAT margins). Note `S9`
  (META duration) is yellow-filled but **empty** — META has no duration assumption.
* Unfilled-but-meaningful columns are `other` by construction: `A`–`E` and `G`, `I`, `L`–`N`
  (labels, definitions, evidence, source ids) and `Q`, `Y`, `AA`, `AC` (proxy wording, sector
  label, plan basis, caveat).

The same colour language is used on the presentation sheets but is **not** extracted here (the
deliverable is scoped to `Inputs`, and the banner cell `Trajectory!A2` is yellow purely as
chrome). For reference: `Trajectory` blue = the 50 fact-linked cells (`C5:G6` per company block);
`Snapshot` blue = rows 6/9/18 (fact rows), yellow = rows 7/11/13/15 (assumption rows),
`FFD9E2F3` = the two section-divider rows 16 and 24.

---

## 6. `data/formulas.csv` — raw formula strings

249 rows: `Trajectory` 150 + `Snapshot` 99. (The workbook has 519 formulas in total; the
remaining 270 are the paired `Checks` formulas, which are test scaffolding, not model logic.)

| column | type | meaning |
|---|---|---|
| `sheet` | string | `Trajectory` \| `Snapshot`. |
| `cell`, `row`, `column` | | Location. |
| `formula` | string | The raw formula, leading `=` included, e.g. `=C8*Inputs!$V$5/C7`. |
| `cached_value` | string | The cached result at full precision, for convenience. |

The model in six lines (per company block, `Inputs` row `n` = the company's assumption row):

```
annualized_ai_capex   = quarterly_capex * 4 * T[n]                  # AI share of capex
annualized_ai_revenue = fact * R[n] / S[n]                          # RPO branch (MSFT/GOOG/AMZN/ORCL)
annualized_ai_revenue = fact * 4 * R[n]                             # revenue branch (META)
forward_roic          = annualized_ai_revenue * V[n] / annualized_ai_capex
spread                = forward_roic - X[n]                         # WACC
delta_bps             = (spread_Q2_26 - spread_Q2_25) * 10000
```

The Snapshot swaps the capex denominator for `annual_capex_guide * ai_share_of_capex` and runs
the same ROIC line with `U` (bear), `V` (base) and `W` (bull).

---

## 7. `data/expected_outputs.csv` — parity target

260 rows of cached computed values, tidy. **This is the parity target** for a Python
reimplementation: full float precision, nothing rounded, taken from `data_only=True`.

| column | type | meaning |
|---|---|---|
| `company` | string | Ticker. |
| `period` | string | `Q2 25` … `Q2 26`; `Q2 25 to Q2 26` for the delta row. |
| `view` | enum | `trajectory` (150 rows) \| `snapshot` (110 rows). |
| `scenario` | enum | `base` \| `bear` \| `bull` \| `n/a`. `n/a` marks scenario-independent rows (input levels, AI capex, WACC, the run-rate spreads and the bps delta). |
| `metric` | string | The workbook's own row label, verbatim, e.g. `Forward ROIC (Base)`, `Spread vs WACC (ppt)`, `Annualized AI Revenue Proxy ($B)`. Labels differ per company in the trajectory view's first row (`Commercial RPO/Backlog ($B)` vs `Revenue (Quarter, $B)` etc.). |
| `value` | float or string | Cached value. Round-trippable via `float()` when `value_type == 'number'`. |
| `value_type` | enum | `number` (244 rows) \| `text` (16 rows). The text rows are `Latest Quarter`, `AI Revenue Source` and `Plan Basis` (5 each) plus `META` `RPO Duration (years, assumption)` = `N/A`. |

Scenario distribution: `n/a` 175, `base` 65, `bear` 10, `bull` 10.

Row structure — trajectory: 5 companies × 6 metric rows × 5 quarters = 150. Snapshot: 5 companies
× 22 metric rows = 110 (`Snapshot!A4:A23` excluding the section-divider row 16, plus rows 25–27).

Units reminder for this file: `Spread …` and `Forward ROIC …` values are **decimals**
(`0.19842209469153516` displays as `19.8 ppt`); `Δ Spread Q2 26 vs Q2 25 (bps)` is already in
**basis points** (`234.70125804806895`).

---

## 8. Reconciliation against the methodology doc

All four counts claimed in `ai_capex_forward_roic_analysis_v02_methodology.md` reproduce exactly:

| claim | measured | |
|---|---|---|
| 519 formulas | 519 (Trajectory 150, Snapshot 99, Checks 270) | ✓ |
| 455 URL-bearing comments | 455 comments, 455 of them URL-bearing | ✓ |
| 240 clickable hyperlinks | 240 | ✓ |
| 135 independent numerical checks passed | 135 rows, 135 `PASS`, 0 `FAIL` | ✓ |

The doc's Q2 2026 filing-input table and Q2 model-output table both tie to `facts.csv`,
`assumptions.csv` and `expected_outputs.csv` at displayed precision, and the trajectory ROIC for
all five companies recomputes from `facts.csv` + `assumptions.csv` to a delta of exactly 0.0.

---

## 8. `data/disclosed_counterparty_revenue.csv` — the one audited AI-linked revenue figure

1 row. A **different grain** from `facts.csv`, which is why it is a separate table rather than
four mostly-empty columns: this is **annual** rather than quarterly, **counterparty-specific**
rather than company-wide, and exists for **one filer**. Putting it in `facts.csv` would have
implied all three were otherwise.

Microsoft's FY2026 10-K:

> In accordance with ASC 850, we are disclosing revenue and accounts receivable balances from
> transactions with OpenAI. For fiscal year 2026, we recorded revenue from commercial
> arrangements with OpenAI, inclusive of revenue-sharing payments, of **$24.1 billion**, and
> accounts receivable from OpenAI as of June 30, 2026 was **$6.0 billion**.

| column | type | unit | class | meaning |
|---|---|---|---|---|
| `ticker` / `company` | string | — | LABEL | `MSFT` / `Microsoft`. Join key. |
| `fiscal_period` | string | — | LABEL | `FY2026`. |
| `period_start` / `period_end` | date | ISO | FACT | `2025-07-01` → `2026-06-30`. Microsoft's fiscal year ends June 30, so this coincides exactly with a trailing-twelve-month window ending at the model's latest quarter. |
| `period_months` | int | months | FACT | `12`. **Never a quarter** — see `T8`. |
| `counterparty` | string | — | LABEL | `OpenAI`. |
| `counterparty_member` | string | — | FACT | `msft:OpenAIGlobalLlcMember`, the XBRL member that identifies it. |
| `revenue_usd_b` | float | $B | **FACT** | `24.1`. Audited, trailing, disclosed. |
| `receivable_usd_b` | float | $B | **FACT** | `6.0` at `receivable_instant`. |
| `xbrl_concept` | string | — | FACT | `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` — **the same concept as total revenue**. |
| `xbrl_axis` | string | — | FACT | `srt:ScheduleOfEquityMethodInvestmentEquityMethodInvesteeNameAxis`. The axis is the whole disclosure: undimensioned, the concept returns $331,839M. |
| `disclosure_basis` | string | — | LABEL | `ASC 850 related-party disclosure`. |
| `why_it_exists` | string | — | LABEL | It is compelled by the accounting for a ~25% equity-method stake, not chosen as AI reporting. |
| `covers` / `excludes` | string | — | LABEL | What the number is and — load-bearing — what it is not. |
| `source_id` | string | — | FACT | `MSFT-FY26-OPENAI-REV` into `sources.csv`. |

### What it is for

**It feeds no model input.** It is carried as a disclosed cross-check on the AI revenue proxy, and
the gap between them is the point. At Q2 2026 the proxy is $678.0B × 50% ÷ 2.5y = **$135.6B**,
which is **5.6×** the $24.1B disclosed. Read the other way, the model implicitly asserts that
Microsoft earns roughly **$111B of AI revenue from customers who are not OpenAI** — a claim that
is now checkable rather than unfalsifiable.

It is not a substitute for the proxy, and `T16` blocks any refresh that treats it as one. `T17`
blocks the mirror-image error of reading the other four filers' silence as evidence.
