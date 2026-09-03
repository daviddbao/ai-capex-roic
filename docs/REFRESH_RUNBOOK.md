# REFRESH_RUNBOOK — the quarterly procedure

**Companions:** `docs/SOURCE_MAP.md` (the spec), `docs/EARNINGS_CALENDAR.md` (when),
`docs/SCHEMA.md` (what the data layer means), `pipeline/source_map.json` (machine-readable spec).

**The one rule:** *this pipeline never appends a row unattended.* It fetches, drafts, and
argues its case; a named human approves. There is no `--approve` flag, deliberately — the
approval is a file you fill in and save.

---

## 0. Why it works this way

A `companyfacts`-only fetcher gets 7 of the 10 core facts right, **1 silently wrong and 1
silently missing**:

| Filer | `companyfacts` returns | The model needs | Failure mode |
|---|---|---|---|
| MSFT | `684,000,000,000` (total RPO) | `678,000,000,000` (**commercial** RPO) | wrong by $6.0B, looks valid |
| AMZN | *nothing since 2020* | `496,000,000,000` | reads as "no data this quarter" |

Both figures exist in XBRL, dimensioned, reachable only by parsing the filing's primary
inline-XBRL document. That is what `pipeline/edgar.py` does and why the `access` field in
`source_map.json` is load-bearing.

---

## 1. When to run — 8 windows a year

From `docs/EARNINGS_CALENDAR.md`. Microsoft's fiscal-year *label* is offset but its quarter
*end dates* coincide with calendar quarters. **Oracle is the only genuinely offset filer.**

| # | Window | Filers | Approx. dates |
|---|---|---|---|
| A1 | Q4 / annual | MSFT, GOOG, AMZN, META | late Jan → early Feb (~10 days) |
| A2 | Q1 | MSFT, GOOG, AMZN, META | late Apr → early May (~2 days) |
| A3 | Q2 | MSFT, GOOG, AMZN, META | Jul 22 → Aug 1 (~10 days) |
| A4 | Q3 | MSFT, GOOG, AMZN, META | late Oct (~3 days) |
| O1–O4 | Oracle | ORCL alone | ~Sep 9–15 · ~Dec 10–11 · ~Mar 10–11 · **~Jun 10–22** |

Each A-window needs roughly two polling passes: one at the leading edge (Alphabet is
consistently first; Microsoft files its 8-K and 10-K the same day) and one ~5 business days
later for Amazon, who is consistently last. A calendar bucket cannot be closed until Amazon's
10-Q lands, ~30 days after quarter end.

### The Oracle exception you will trip over

Oracle's 10-Q follows its 8-K by **1 day** — but at fiscal year end **the 10-K lagged the 8-K
by 12 days in 2026** (2026-06-10 → 2026-06-22; 7 days in 2025). **Oracle's RPO and capex facts
do not exist in XBRL until the 10-K arrives.** If you run the pipeline off Oracle's June 8-K
you will get guard `S2` FAIL — that is correct behaviour, not a bug. Wait for the 10-K.

Do not schedule this. Observed dates move by up to a week year over year. Poll instead:

```bash
python -m pipeline.edgar poll --since 2026-10-01
```

Fire the refresh for a company when a 10-Q/10-K appears whose `reportDate` equals the target
period end. The 8-K (Item 2.02) is an early warning only: its exhibit is untagged prose.

---

## 2. The procedure

All commands are run on demand from the repo root. Nothing here installs a scheduler.

### Step 1 — poll

```bash
python -m pipeline.edgar poll --since <YYYY-MM-DD>
```

Lists recent 10-K/10-Q/8-K filings per company. Proceed when the periodic filing for the
target period end is present.

### Step 2 — draft a review packet per company

```bash
python -m pipeline.draft CY2026Q3            # all five
python -m pipeline.draft CY2026Q3 ORCL       # or one at a time
```

For each company this:

1. resolves the period from the fiscal calendar and cross-checks it against `source_map.json`;
2. extracts each field according to its `automation_tier` and `access`;
3. runs every guard;
4. **snapshots the primary filing, the 8-K and Exhibit 99.1** to
   `01_sources/company_filings/<Company>/<accession>/` with SHA-256s;
5. writes `pipeline/packets/<bucket>/<TICKER>.md` (read this), `.json` (the machine copy) and
   `.approval.json` (blank; you fill it in).

The bucket key is calendar-based: `CY2026Q3` is the quarter ending 2026-09-30 for four filers
and Oracle's quarter ending **2026-08-31**. It maps to `Q3 26` in `data/facts.csv`.

Because Oracle reports ~6 weeks before the others, expect to run Oracle's draft in
mid-September and the other four in late October, then apply five packets into the same bucket.

### Step 3 — read the packet

Open the `.md`. Work top to bottom:

* **§1 Proposed values** — the numbers, each labelled with the tier it came from.
* **§2 Evidence** — for every sourced number, a *verbatim quoted snippet* and its URL, plus the
  XBRL context (dimensions included) and, for derived figures, the component arithmetic. This
  mirrors the cell-note convention already in the workbook; the packet renders a paste-ready
  cell note for each field.
* **§3 Guard results** — every check, passes included. You need to see what was checked.
* **§4 What a human must supply** — the fields the pipeline refuses to guess.

### Step 4 — do the human work

Five inputs are permanently manual (see §4 below). For each, read the source named in the
packet and write down the number *and where you read it*.

### Step 5 — sign the approval file

Open `pipeline/packets/<bucket>/<TICKER>.approval.json` and fill in:

| key | what to put |
|---|---|
| `reviewer` | your name. An approval names a person. |
| `reviewed_at` | ISO date. |
| `manual_values.<field>_usd_b` | the number you found, in $B. |
| `manual_value_sources.<field>_source_url` | where you found it. |
| `manual_value_evidence.<field>_quote` | what it said, verbatim. |
| `acknowledgements.<GUARD ID>` | **one sentence per blocking guard** saying what you checked. |
| `packet_sha256` | copy the packet's content hash (printed in the packet, and in `packet_sha256_expected_hint`). |
| `decision` | `APPROVED`. |

The content hash is computed over the **proposed values only**. Re-drafting with the same
numbers keeps your signature valid; re-drafting with different numbers invalidates it and you
must review again. A `FAIL` guard cannot be acknowledged — fix the cause and re-draft.

### Step 6 — apply

```bash
python -m pipeline.apply pipeline/packets/CY2026Q3/GOOG.json
```

This validates the approval, appends **one row** to `data/facts.csv` and the matching
`*-FACT` / `*-CAPEX` rows to `data/sources.csv`, then recomputes the model through
`model/calc.py` and prints a diff report showing how every company's spread moved and why.

Re-running is safe: an identical row already on file is a no-op. A row on file with
*different* values is refused — rewriting history is not an append.

### Step 7 — the assumptions follow-up

`apply.py` does **not** write `data/assumptions.csv`. That table holds the annual capex
denominators and the WACC selections, and per `docs/SCHEMA.md` §2 it is *versioned*: a changed
assumption must be appended as a **new row with a later `effective_from`**, never edited in
place. If an approved annual denominator differs from the one on file, the diff report says so;
append the row by hand and re-run the model.

---

## 3. What each guard means when it trips

Statuses: `FAIL` blocks outright · `NEEDS_HUMAN` blocks until acknowledged by id ·
`INFO` must be read · `PASS` is shown so you can see what was checked.

### Structural

| Id | Meaning when it trips | What to do |
|---|---|---|
| `S1` | The period resolved from the fiscal calendar contradicts `report_bucket_map` in the spec. | Do not proceed. Either the spec drifted or the filer changed its calendar. Fix `source_map.json`. |
| `S2` | No 10-Q/10-K with this `reportDate` exists yet. | Wait. For Oracle's fiscal Q4 this is the 12-day 8-K→10-K gap. |
| `S3` | Form is not the one expected for this fiscal quarter (10-K in fiscal Q4). | The derivation shape depends on this. Confirm before trusting a derived quarter. |
| `S4` | An extraction failed. | Read the message — it names the concept and the exact period it could not find. Never substitute a nearby value. |
| `S5` | A manual field was refused (normal), **or** a manual field was auto-populated (a bug). | Supply the value in the approval file. If it was auto-populated, that is a pipeline defect — stop. |
| `S6` | A fetch failed. | Re-run; if it persists, report it. Do not proceed on partial data. |
| `S7` | The pinned annual-denominator window is a superseded fiscal year. | Decide whether to roll the pin forward in `source_map.json`. This is a methodology choice. |

### The 15 documented traps

| Id | Trap | Meaning when it trips |
|---|---|---|
| `T1` | Oracle's *net cash outlay* is not GAAP capex | The extracted figure matches a row from the press release's non-GAAP table (which deducts short-term capex financing and customer prepayments), or it did not come from `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`. The model uses **gross** ($55,663M FY2026, not $47,726M). |
| `T2` | Oracle's press-release capex table is **trailing-four-quarters** | Informational: the table was detected. FY26 Q3 reads 48,250 there while the 9-month XBRL YTD is 39,170. Never read a column of that table as a quarter. FAILs if the capex value appears to have come from that exhibit. |
| `T3` | Microsoft's outlook moved for accounting reasons | Always asks a human. Longer datacenter useful lives (15→25 years) shift future leases from finance to operating, cutting the metric without cutting investment. Any comparison across the change is mechanical, not economic. |
| `T4` | **Total RPO ≠ commercial RPO** | The most dangerous trap. FAILs if the selected fact lacks `srt:MajorCustomersAxis = msft:CommercialCustomersMember`, or if the value equals the undimensioned companyfacts total. Never accept $684B. |
| `T5` | Alphabet's backlog definition changed in Q1 2026 | Carries a `definition_version` flag. Asks a human if the definition language disappears or changes. Q1 26 onward are comparable with each other; Q4 25 → Q1 26 is not. |
| `T6` | Amazon gross vs net capex | FAILs if the value is not the filing's gross cash-flow line, i.e. if it is the MD&A's net "cash capital expenditures" ($53.076B vs the gross $54.208B), or if the wrong concept was used — Amazon tags both `PaymentsToAcquireProductiveAssets` (right) and `PaymentsToAcquirePropertyPlantAndEquipment` (wrong). |
| `T7` | Meta's guidance sentence carries the superseded range too | Always asks a human. One sentence contains `$130-145 billion` *and* `$125-145 billion`; the same paragraph carries a `$165-169 billion` **total expenses** range. Regex extraction is not good enough for a model input. |
| `T8` | A year-to-date figure is never a quarter | FAILs if a derived quarter equals one of its YTD components, if a derived quarter has no YTD components, or if a directly-tagged duration is not ~90 days. Amazon is the only filer tagging standalone 3-month cash-flow durations. |
| `T9` | The largest "commitments" number is not the backlog | FAILs if the demand fact equals a contractual/purchase-obligation figure — what the company *owes suppliers* (Alphabet $811.0B, Amazon $650.034B), the opposite direction from the revenue backlog. |
| `T10` | Amazon's RPO axis is a moving typed member | FAILs on a missing timing axis, on a context carrying `srt:MajorCustomersAxis` (that selects the $38B OpenAI-specific commitment), or on an empty result. Selection is by **axis presence**; the typed member is the day after period end and advances every quarter. |
| `T11` | Amazon's ~$200B capex plan vs its $200.6B net sales | FAILs if the supplied annual plan is within $1B of the quarter's net sales. The plan is not in the press release at all. |
| `T12` | "Including finance leases" means two different things | FAILs if Meta's formula uses ROU-asset additions or drops the finance-lease principal component, or if Microsoft's proxy uses Meta's concept. Meta adds `FinanceLeasePrincipalPayments` (cash); Microsoft's metric appears to add `RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability` (non-cash). |
| `T13` | Oracle's period ends are not calendar quarter ends | FAILs if Oracle resolves to a calendar quarter end, or if a calendar filer resolves to something else. INFO otherwise, restating the one-month mismatch that no automation removes. |
| `T14` | Oracle's RPO includes prepaid / customer-supplied hardware | Always asks a human. ~$75B of prepaid or customer-supplied GPUs reduces Oracle's own capital requirement. The number is machine-readable; its comparability is not. |
| `T15` | Precision is not uniform, and rounding is not error | PASSes with the tolerance for that specific fact. MSFT/AMZN/ORCL tag demand facts to whole billions, Alphabet to one decimal, cash-flow items to the million. A rounded press-release figure never overrides a more precise XBRL derivation (Meta: $31.08B printed, $31.078B derived — use the derivation). |

### Range and cross-check

| Id | Meaning when it trips |
|---|---|
| `R1` | The demand fact moved >40% sequentially (asks a human) or outside a 0.2×–5× band (FAILs). Oracle's RPO once moved +230%, so a large move is possible — but it gets confirmed, not waved through. |
| `R2` | Quarterly capex moved >35% sequentially (asks a human) or outside a 0.25×–4× band (FAILs). **This fires on Meta in the replayed quarter (+56.6%), correctly.** |
| `R3` | The value is outside any plausible absolute magnitude — almost always a unit or period error. |
| `X1` | No corroborating disclosure was located for a filer that publishes a quarterly cross-check column. Read the filing yourself. (Oracle publishes no quarterly capex column at all, so its absence is INFO, not a block.) |

---

## 4. The five inputs a human must always supply

These are refused by design. `python -m pipeline.extract <bucket>` prints them as `REFUSED`,
and the packet names the source for each.

1. **Microsoft's quarterly management capex (`$41.0B` at Q2 2026).** Exists in no SEC filing.
   The FY2026 10-K parses to 1,565 inline-XBRL facts and none of them is this number; the
   phrase "capital expenditures including finance leases" does not occur. Source: the FY26 Q4
   earnings call / webcast, CFO prepared remarks.
   *The packet shows an XBRL proxy (`$40.924B` = cash PP&E + finance-lease ROU additions, each
   as FY − 9M). It lands 0.19% away. It is a sanity check, not a value: Microsoft has never
   published a reconciliation and the composition is unverified.*
   **This one field alone prevents a fully unattended refresh.**
2. **Microsoft's CY2026 capex outlook (`~$175B`).** Call-only, and its movement is contaminated
   by the useful-life change (T3).
3. **Alphabet's FY2026 capex range (`$195–205B`, midpoint used).** Call-only; absent from both
   the 10-Q and the 8-K.
4. **Amazon's FY2026 capital plan (`~$200B`).** Call-only. The methodology is already carrying a
   figure forward because Q2 2026 produced no replacement — a staleness judgement no scraper
   can make. Beware T11.
5. **Meta's FY2026 capex range (`$130–145B`, midpoint used).** Present in a filed 8-K, but as
   untagged prose in a sentence that also contains the superseded range (T7).

Beyond these, three judgement calls are *not fields at all* but will break the model if
automated away, and the pipeline can only flag them: the **duration assumptions** (Amazon
disclosed 6.4 years against a retained 4.0 — the methodology's largest identified sensitivity;
Microsoft disclosed 2.3 against a retained 2.5), the **AI-attribution shares**, and whether a
definition change (T5) or an accounting-policy change (T3) has broken comparability.

---

## 5. Validation — replay

The pipeline is proved by replay, not by waiting for a filing:

```bash
python -m pytest pipeline/tests -q
```

`pipeline/tests/test_replay_q2_2026.py` runs the whole extraction against the quarter ending
June 2026 and requires it to independently re-derive the `Q2 26` row already in
`data/facts.csv` — to the dollar, for all nine machine-readable core facts — with MSFT
resolving to $678.0B (not $684B) and AMZN to $496B (not empty), and with the five manual inputs
refused rather than guessed. `test_guards.py` sprinkles each documented trap into a real
extraction and requires the corresponding guard to block.

Expectations are read from `data/facts.csv`, never from `source_map.json`'s recorded values, so
the test cannot pass by agreeing with itself.

Raw SEC responses are cached under `pipeline/.cache/` so a re-run does not re-hit
`data.sec.gov`. Set `PIPELINE_OFFLINE=1` to forbid the network entirely and fail on a cache
miss instead of fetching.

---

## 6. Operational notes

* **User-Agent.** `data.sec.gov` requires a descriptive one; it is set in `pipeline/edgar.py`.
  Requests are spaced to stay well under SEC's 10/second ceiling.
* **Windows console.** Filing text contains characters cp1252 cannot encode. Every entry point
  calls `sys.stdout.reconfigure(encoding='utf-8')`; do the same in anything you add.
* **Archiving.** `data/sources.csv` records `local_path_if_any` for 41 of 62 sources and the
  methodology describes preserved copies — *those files did not exist*. From now on every
  drafted packet snapshots its primary sources to `01_sources/company_filings/` with SHA-256s
  and a manifest. Historic filings are not backfilled; EDGAR Archives URLs are durable, but IR
  and slide-deck URLs are not, and those are exactly the sources for the five manual inputs.
  **Consider saving the earnings call transcript or slides by hand alongside each packet.**
* **No scheduler.** Everything is on demand, by design.
* **The workbook.** `ai_capex_forward_roic_analysis_v02.xlsx` is the frozen audit-of-record and
  is never written by this pipeline or by anything else. A fresh workbook is *rendered* from the
  data layer into `build/` — see §7.

---

## 7. Regenerating the workbook

After an approved append lands in `data/facts.csv`, render a new workbook:

```bash
python scripts/build_workbook.py
```

It reads `data/`, computes through `model/calc.py`, and writes
`build/ai_capex_forward_roic_analysis_v03_<N>q_through_<latest>.xlsx` — e.g.
`..._v03_5q_through_Q2-26.xlsx`. Nothing else is touched. The script re-hashes
`ai_capex_forward_roic_analysis_v02.xlsx` before and after the run and aborts if it moved; it
also refuses outright to write to that path.

### What the generated workbook is

**Values only.** Every number is computed in Python and written as a literal. There is not one
Excel formula in the file, and there must never be one: `model/calc.py` is the single
calculation engine, and a formula that recomputes the model would put the model in two places.
`test_no_sheet_carries_a_model_formula` enforces this.

The `Checks` sheet still exists and still carries 27 checks per company, but in a values-only
workbook there is nothing for Excel to recompute, so it is rendered as values with a literal
`PASS`/`FAIL`: **Expected** is the number `model/calc.py` produced, **Workbook Value** is read
back out of the rendered cell. That catches a mis-placed or mis-typed render — the failure mode
a values-only sheet actually has. It is deliberately *not* an arithmetic re-derivation. A `FAIL`
aborts the build.

### What rolls forward automatically

| Thing | Behaviour |
|---|---|
| `Trajectory` columns | One per quarter in `facts.csv`, ordered by `period_end` via `model.build.ordered_quarters`. Grows forever; nothing rolls off. |
| `Inputs` rows | 5 companies × N quarters. Appending a quarter shifts every block below Microsoft's down by one row. |
| `Snapshot` YoY anchor | Four buckets back from the latest quarter. Rolls. |
| `Snapshot` QoQ anchor | The immediately preceding quarter. Rolls. |
| `Snapshot` baseline anchor | `--baseline-quarter`, default the oldest quarter on file. **Fixed.** |
| `Checks` rows | `5 × (4·N + 9)`; the YoY/QoQ checks are skipped, not faked, when the anchor does not exist. |
| Caveat bullet 2 | States the live quarter count. |

An anchor that does not exist yet (fewer than five quarters for YoY, one for QoQ) renders as
`n/a` with a label that says so. It is never a fabricated number.

The three `Snapshot` change rows are labelled with the quarters they compare, so which is which
is unambiguous:

```
25  Spread Q2 26 (run-rate basis, ppt)
26  Spread Q2 25 (run-rate basis, ppt) — YoY anchor
27  Spread Q1 26 (run-rate basis, ppt) — QoQ anchor
28  Spread Q2 25 (run-rate basis, ppt) — baseline anchor
29  Δ Spread Q2 26 vs Q2 25 (YoY, bps)
30  Δ Spread Q2 26 vs Q1 26 (QoQ, bps)
31  Δ Spread Q2 26 vs Q2 25 (baseline, bps)
```

v02 had only rows 25–27, with row 26/27 being the baseline pair; those moved to 28/31 and took
their cell notes with them.

### The audit trail

Cell notes and hyperlinks are keyed **semantically** — `(ticker, quarter, column)` — not by
address, precisely because appending a quarter moves rows on `Inputs`. For a cell that existed
in v02 the note is carried over verbatim. For a cell that did not (a new quarter), the note is
produced by rewriting *that same company's* v02 note line for line with the new quarter's own
URL, value and evidence, taken from `facts.csv` and `sources.csv`. Nothing is invented: if a
line is not one of `Value:` / `Public source:` / `Evidence:` / `Local source:` / `Fact source:`
/ `Capex source:` / `Contextual public filing:` / `Formula:`, it is copied unchanged.

**So a new quarter's rows are only as good as its `sources.csv` entries.** If `pipeline.apply`
appends a fact row without the matching `*-FACT` / `*-CAPEX` source rows, the new cells get a
note with an empty `Evidence:` line. Check the source ledger grew too.

### Verifying a regeneration

```bash
python -m pytest scripts/tests/test_build_workbook.py -q
```

43 tests. The load-bearing one is `test_expected_output_matches_v02`: all 260 cached values in
`data/expected_outputs.csv` — the numbers Excel itself computed in v02 — must come back out of
the regenerated workbook at `rtol=1e-12`. **If it fails, that is a real finding about the
renderer or the model. Do not adjust the expectation to fit the output.** The suite also
asserts all 455 v02 cell notes, all 240 hyperlinks and the 115 fact / 30 assumption fill classes
survive, and appends a synthetic sixth quarter to a *copy* of `data/` to prove the trajectory
widens, nothing is dropped and the anchors roll.

Output is byte-stable: document properties, `dcterms:modified` and every zip entry timestamp are
pinned, so the same `data/` always produces the same SHA-256. Two runs that disagree mean the
data changed.

### Known cosmetic divergences from v02

Three strings differ from the frozen workbook, all because v02's prose asserts something that a
growing sheet makes false. They are the only text changes:

* `Trajectory!A2` — "only the change **row**" → "change **rows**".
* `Sources & Notes` caveat 2 — "Five quarters are shown so the change row is a true Q2 2025-to-Q2
  2026 comparison" → the live quarter count and the three comparisons.
* `Sources & Notes` caveat 7 — "only the Q2-to-Q2 change row is basis points" → "the change rows".

Also carried over deliberately: v02 sets an explicit width only on the *first* quarter column of
`Trajectory`, leaving the rest at Excel's default. The renderer reproduces that rather than
silently improving it.

---

## 7a. Regenerating the dashboard

`dashboard/index.html` is a single self-contained page. Only one region of it is
machine-written — the embedded `DATA` object — and `scripts/build_dashboard.py` is the only
thing that writes it:

```bash
python scripts/build_dashboard.py            # regenerate in place
python scripts/build_dashboard.py --check    # fail if regeneration would change the file
```

Before writing, the script recomputes all 260 frozen workbook rows through `model/calc.py` and
refuses to emit a page whose model no longer reproduces the workbook. The page then re-asserts
the whole model in JavaScript on load and shows a red alarm instead of numbers if it disagrees.

### What the page shows, in order

| Section | What it is |
|---|---|
| **The numbers** | Three views of the model — quarterly trajectory, latest-quarter snapshot, and the disclosed inputs themselves. This is what the page leads with. Every disclosed figure is a link to its row in the evidence ledger; the trajectory view carries a QoQ / YoY / LTM block on the right. |
| **Return against cost of capital** | The same numbers drawn, toggling between forward ROIC, WACC and the spread between them. |
| **How each spread is built** | One receipt per company for the selected quarter: the filed figures, the analyst choices, and the arithmetic. Both capex denominators — run-rate and annual plan — against a shared numerator. |
| **Cost of capital** | The Damodaran sector WACC the model uses, beside a bottom-up WACC built on the page. See below. |
| **Assumptions** | Every analyst judgement in one grid. |
| **Evidence ledger** | All 62 sources, ordered by quarter, each linked to and from the figures it supports. |

### LTM is not four times the latest quarter

The trajectory view's LTM column sums the last four quarters rather than annualising the latest
one, because for capex ramping this hard the two differ materially — Alphabet's Q2 26 quarter
annualises to $179.7B against $132.4B actually spent in the year to that date. A demand fact is
only summable when it is a flow: backlog and RPO are point-in-time balances, so those cells read
`balance` and the LTM proxy for those four filers is the run-rate proxy unchanged, with only the
denominator becoming trailing. Meta's demand fact is quarterly revenue, so its numerator *is* a
true trailing sum. `test_ltm_refuses_to_sum_a_point_in_time_balance` pins that distinction.

### The page names no file, script or format

`test_no_visible_text_reveals_how_the_page_is_built` asserts that no body text, tooltip, label or
aria-label on the rendered page contains "workbook", ".xlsx", "calc.py", "extract.py",
"pipeline/", "scripts/", "01_sources", "data layer", "csv" or "python". The page is meant to read
as its own analysis rather than as a description of the machinery behind it. The integrity signal
survives the de-jargoning — the verification chip still states how many reference values were
matched — and `test_the_verification_chip_still_says_what_it_checked` holds it to that. **If you
add prose to the page, keep it in the reader's language.**
| **What this model cannot tell you** | The caveats, carried from the methodology doc. |

### The cost-of-capital card is not sourced, by construction

The model's WACC is a Damodaran sector average, which is a published figure and is treated as a
fact. The card also builds a WACC from the ground up — CAPM cost of equity, after-tax cost of
debt, weighted by capital structure — and **every input to it is declared, not sourced.** The
data layer holds filing facts for backlog and capex and nothing else: no debt, no tax rate, no
share count, no market data. Each input is flagged with why it is not a fact:

* **sourceable** — it is in the archived filings and could become a guarded fact through
  `pipeline/extract.py`: total debt, interest expense, effective tax rate, shares outstanding.
* **market input** — it exists in no filing at all and needs a market data feed: risk-free rate,
  equity risk premium, beta, share price.

Defaults are identical across all five companies on purpose, so an unreplaced placeholder is
obvious rather than looking like a company estimate. The built figure does not reach the model
unless the reader switches the toggle, and the page's own self-check always runs on the sector
figures regardless.

**The page carries `data/sources.csv` and links every disclosed figure to it.** Each fact row
in `data/facts.csv` cites a `*-FACT` and a `*-CAPEX` source id, and each company cites a
`*-PLAN` and a `*-WACC` id; the build **aborts** if any of them is missing or is of the wrong
kind. So the §7 warning applies here with teeth: if `pipeline.apply` appends a fact row without
the matching source rows, the dashboard build fails rather than rendering a blue number that
links nowhere. Check the source ledger grew.

---

## 8. Quick reference

```bash
python -m pipeline.edgar poll --since 2026-10-01     # what has been filed
python -m pipeline.extract CY2026Q3                  # values only, no packet
python -m pipeline.guards  CY2026Q3                  # guard verdicts only
python -m pipeline.draft   CY2026Q3                  # packets + archive  <- normal entry point
python -m pipeline.archive CY2026Q3                  # snapshot filings only
# ... fill in and save pipeline/packets/CY2026Q3/<TICKER>.approval.json ...
python -m pipeline.apply pipeline/packets/CY2026Q3/GOOG.json
python -m pytest pipeline/tests -q                   # replay validation
python scripts/build_workbook.py                     # render build/*.xlsx from data/
python -m pytest scripts/tests/test_build_workbook.py -q   # verify the render
python scripts/build_dashboard.py                    # refresh dashboard/index.html
python scripts/build_dashboard.py --check            # fail if the page is stale
```
