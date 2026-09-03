# AI capex — forward ROIC

Is the AI capital being spent by Microsoft, Alphabet, Amazon, Oracle and Meta earning more than
it costs? This repository answers that with a model where **every number is either taken from a
filing and linked to it, or is an analyst judgement and labelled as one** — and where the
distinction is enforced by tests rather than asserted in prose.

Five companies, five quarters (Q2 2025 → Q2 2026), one calculation engine, and a pipeline that
refuses to add a quarter unattended.

```
data/            the facts, the assumptions, and every source behind them
model/           the calculation engine — pure functions, no I/O
pipeline/        quarterly refresh: fetch → extract → guards → packet → human → apply
scripts/         renders the workbook and the dashboard from data/
dashboard/       a single self-contained HTML page that recomputes and checks itself on load
docs/            the schema, the source map, the refresh runbook, the earnings calendar
01_sources/      archived filings with SHA-256s
```

**789 tests pass.** `PIPELINE_OFFLINE=1 python -m pytest model/tests pipeline/tests scripts/tests -q`

---

## Where the idea came from

This started from a post by Satya Nadella on 30 July 2026:

> <https://x.com/satyanadella/status/2082640036949008570>

**I could not retrieve the post's text.** X returns HTTP 402 to unauthenticated requests, so what
follows is from search-result summaries and secondary press coverage, not from the post or the
underlying report. Treat this section as the weakest-sourced page in the repository — which is
precisely the standard the rest of it exists to avoid.

What appears to be the case: the post describes a "ROIC Intelligence App" that Nadella built from
a Morgan Stanley PDF by **Brian Nowak** on hyperscaler ROIC, using Copilot with a single prompt,
and mentioned on that day's Microsoft earnings call. The underlying research (Nowak, Byrd and
Wood, published 27 July 2026 per press coverage) built **three bottom-up unit-economics
frameworks** — hyperscaler GPU leasing, model APIs on owned infrastructure, and model APIs on
third-party infrastructure — reporting roughly **31%, 46% and 25%** ROIC respectively, an overall
**25–50%** long-run range, against a combined **$1.4T** of AI infrastructure investment.

### Does this model agree with that?

Partly, and the disagreement is the interesting half. Base-case forward ROIC at Q2 2026:

| | run-rate | annual plan | LTM denominator | inside 25–50%? |
|---|---|---|---|---|
| **MSFT** | 29.18% | 27.35% | 32.94% | yes, on all three |
| **GOOG** | 28.19% | 25.33% | 38.26% | yes, on all three |
| **ORCL** | 32.88% | 38.97% | 38.97% | yes, on all three |
| **AMZN** | 11.74% | 12.73% | 14.72% | **no — below on every basis** |
| **META** | 13.91% | 12.58% | 17.56% | **no — below on every basis** |

Amazon and Meta stay outside the band even at the bull margin (8.4–15.9% and 10.9–17.4%
respectively). Three of five land inside it.

**But the two models are not measuring the same thing, and this one is the weaker construction.**
Morgan Stanley's frameworks are bottom-up unit economics with an invested-capital denominator.
This model is top-down: a revenue *proxy* from disclosed backlog, over a single year of capex
*spending*. Its denominator is a flow, not a capital base net of depreciation — so read its
output as a return on the current rate of spend, not as a textbook ROIC. That limitation is
stated on every ROIC explanation in the dashboard, and it is the model's most load-bearing
caveat. Landing inside somebody else's band is not corroboration when the arithmetic differs.

Sources for this section, all secondary:
[search result](https://x.com/satyanadella/status/2082640036949008570) ·
[Seeking Alpha](https://seekingalpha.com/news/4619614-amazon-google-microsofts-extreme-ai-capex-plans-still-equate-to-strong-returns-ms) ·
[TradingView](https://www.tradingview.com/news/stocktwits:8049d74a2094b:0-amzn-googl-msft-ai-capex-plans-why-morgan-stanley-says-the-spending-will-pay-off/) ·
[BigGo Finance](https://finance.biggo.com/news/212a6131-57b2-49c8-8ccf-20a27bcac88d)

**If you have the post text or the report, paste it in** — the alignment check above deserves to
be run against the primary source rather than against press paraphrase.

---

## The model

```
AI revenue proxy   = backlog × AI share ÷ contract duration        (MSFT, GOOG, AMZN, ORCL)
                   = quarterly revenue × 4 × AI attribution        (META — no backlog exists)

AI capex           = quarterly capex × 4 × AI share of capex       run-rate view
                   = annual capex plan × AI share of capex         annual-plan view
                   = LTM capex × AI share of capex                 trailing view

forward ROIC       = AI revenue proxy × NOPAT margin ÷ AI capex
spread             = forward ROIC − WACC
```

The two capex views **share a numerator exactly** — only the denominator differs — which is why
the dashboard builds the proxy once and runs both denominators against it.

Scenarios (bear / base / bull) change the NOPAT margin and nothing else.

### What is a fact and what is not

| | count | |
|---|---|---|
| **Facts** | 25 company-quarters × 2 | Backlog/RPO and quarterly capex, from filings, each linked |
| | 5 | Annual capex denominators |
| | 5 | WACC (Damodaran January 2026 sector averages — published, but the *sector choice* is judgement) |
| | 1 | Microsoft's disclosed OpenAI revenue (see below) |
| **Assumptions** | 5 × 4 | AI share of backlog, contract duration, AI share of capex, NOPAT margin |
| **Sources** | 63 | Every one of them, in `data/sources.csv`. **12** have a preserved copy verified against its SHA-256; 32 record a path that was never backfilled and say so; 19 never claimed one |

Five inputs are **permanently manual** and the pipeline refuses to guess them — Microsoft's
quarterly management capex and CY2026 outlook, Alphabet's and Meta's capex ranges, and Amazon's
capital plan. All five are call-only or untagged prose. See `docs/REFRESH_RUNBOOK.md` §4.

---

## The dashboard

`dashboard/index.html` — one self-contained file, no server, no fetches. Open it.

It **recomputes the entire model in the browser on load** and checks itself against 535
independently verified reference values covering every company and every quarter. If it
disagrees by more than one part in a billion it shows a red alarm and hides the numbers instead
of rendering figures it cannot stand behind.

- **The numbers** — quarterly trajectory, latest-quarter snapshot, and the disclosed inputs.
  Every blue figure links to the document it came from. The trajectory view carries QoQ, YoY and
  LTM columns.
- **Return against cost of capital** — the same numbers drawn, toggling forward ROIC / WACC /
  spread.
- **How each spread is built** — one receipt per company for the selected quarter: filed figures,
  analyst choices, and the arithmetic between, with both capex denominators.
- **Cost of capital** — the sector WACC the model uses, beside a bottom-up WACC built on the page
  from declared inputs. Switch the toggle and it drives every spread.
- **Assumptions** — all twenty judgements in one grid.
- **Evidence ledger** — all 63 sources, ordered by quarter, linked to and from the figures, each
  marked *archived* (a preserved copy, hash-verified), *not kept*, or *none*.
- **What this model cannot tell you** — the caveats.

### Click any computed number

Every derived value on the page — 170 of them — opens the arithmetic that produced it: the
formula, then each operand tagged **disclosed** / **assumed** / **computed** / **definition**.
Disclosed operands link to the filing. Assumed operands open the control that sets them. Computed
operands are themselves clickable, so a spread opens into ROIC, which opens into the revenue
proxy, which opens into the backlog fact and its 10-Q.

Each explanation recomputes its own result from its own operands, and the page asserts on load
that every one of them reproduces the number it explains. An explanation that has drifted from
the calculation alarms exactly like a model mismatch — it is a defect, not a cosmetic issue.

---

## The refresh pipeline

**One rule: it never appends a row unattended.** It fetches, drafts and argues its case; a named
human approves by filling in and saving a file. There is no `--approve` flag, deliberately.

```bash
python -m pipeline.edgar poll --since 2026-09-08   # what has been filed
python -m pipeline.draft   CY2026Q3                # packets + archive  <- normal entry point
# ... read the packet, do the human work, sign the .approval.json ...
python -m pipeline.apply pipeline/packets/CY2026Q3/GOOG.json
python scripts/build_workbook.py                   # render build/*.xlsx
python scripts/build_dashboard.py                  # refresh the page
```

A `companyfacts`-only fetcher gets 7 of the 10 core facts right, **one silently wrong and one
silently missing** — Microsoft's *total* RPO instead of commercial ($684B for $678B), and nothing
at all for Amazon since 2020. Both correct figures exist in XBRL but only dimensionally, reachable
by parsing the filing's primary inline-XBRL document. That is why the pipeline exists.

### The guards

23 guard functions emitting 27 ids: structural preconditions (`S1`–`S7`), range and cross-checks
(`R1`, `R3`, `X1`), and **17 documented traps** (`T1`–`T17`) — each an executable check that
blocks rather than warns. A few of them:

- **`T4`** — Microsoft's total RPO is not its commercial RPO. Distinguished only by dimension.
- **`T6`** — Amazon tags both a right and a wrong capex concept.
- **`T8`** — a year-to-date figure is never a quarter.
- **`T9`** — the largest "commitments" number is what the company owes *suppliers*, the opposite
  direction from a revenue backlog.
- **`T10`** — Amazon's RPO axis is a typed member that advances every quarter. Match on axis
  presence, never on the date.
- **`T16`** / **`T17`** — see below.

The pipeline is proved by **replay**: `pipeline/tests/test_replay_q2_2026.py` runs the whole
extraction against the quarter ending June 2026 and requires it to independently re-derive the
row already in `data/facts.csv`, to the dollar, with the five manual inputs *refused* rather than
guessed. Expectations are read from `facts.csv`, never from the spec's own recorded values, so the
test cannot pass by agreeing with itself.

---

## The one audited AI revenue figure

Microsoft's FY2026 10-K:

> In accordance with ASC 850, we are disclosing revenue and accounts receivable balances from
> transactions with OpenAI. For fiscal year 2026, we recorded revenue from commercial arrangements
> with OpenAI, inclusive of revenue-sharing payments, of **$24.1 billion**, and accounts
> receivable from OpenAI as of June 30, 2026 was **$6.0 billion**.

This is the only audited AI-linked revenue number any of the five publishes, and it exists only
because Microsoft's ~25% equity-method stake makes OpenAI a related party — compelled by the
accounting for the stake, not chosen as AI reporting.

It **feeds no model input**. It is carried as a disclosed floor against which to read the proxy,
and the gap is the point: the proxy is $678.0B × 50% ÷ 2.5y = **$135.6B**, which is **5.6×** the
disclosed figure. Read the other way, the model implicitly claims Microsoft earns roughly
**$111B of AI revenue from customers who are not OpenAI** — now a checkable claim rather than an
unfalsifiable one.

Two guards keep it honest:

- **`T16`** — the figure is tagged with the *same* us-gaap concept as total revenue. Undimensioned
  that concept returns **$331,839M**, 13.8× too large and entirely plausible-looking. FAILs
  without the investee axis, and always asks a human about the substantive error: it is one
  counterparty, never a substitute for the proxy.
- **`T17`** — the mirror image. Amazon names a $38.0B OpenAI commitment expanded by $100.0B over
  8 years and an Anthropic collaboration expanded by more than $100.0B over 10 years, and discloses
  **no revenue from either**, because its stakes are not equity-method. Larger named exposure,
  zero disclosure. Never read the silence as evidence.

---

## Known weaknesses

Properties of the model, not of this implementation. Every one is surfaced in the dashboard.

1. **The denominator is a capex flow, not invested capital.** No accumulated base, no
   depreciation. This is a return on the current rate of spend.
2. **Amazon's 4.0-year duration is the largest single sensitivity.** Amazon disclosed **6.4 years**
   at June 30, 2026. On its own number Amazon's run-rate spread goes from **+447 bps to +7 bps** —
   the conclusion "Amazon earns above its cost of capital" does not survive the company's own
   disclosure.
3. **Oracle's 85% AI attribution and 5-year duration are unverified.** Oracle reports company-wide
   RPO and discloses neither. Cutting the share to 50% moves its spread from +2,505 to +1,151 bps.
   Oracle also disclosed ~$75B of prepaid or customer-supplied hardware that the capex denominator
   does not reflect.
4. **Microsoft's improved plan-basis spread is partly a lease-classification artefact.** Longer
   datacenter useful lives shifted future leases out of its capex metric. The denominator shrank;
   the spending did not.
5. **Capex is defined differently by each company.** Five definitions in one denominator. Levels
   are not comparable across companies — only each company's own series over time.
6. **WACC is a sector average**, not a company cost of capital. Build your own on the page.
7. **Meta has no backlog at all.** Its proxy annualises one quarter of total revenue times a 20%
   AI attribution Meta does not report.
8. **Alphabet's backlog definition changed in Q1 2026.** The series has a comparability break,
   marked on the chart.

---

## Getting started

```bash
python -m pip install openpyxl pandas pytest
PIPELINE_OFFLINE=1 python -m pytest model/tests pipeline/tests scripts/tests -q
```

Then open `dashboard/index.html`.

The browser tests need Playwright and are skipped without it:

```bash
python -m pip install playwright && python -m playwright install chromium
python -m pytest scripts/tests/test_page_render.py -q
```

`ai_capex_forward_roic_analysis_v02.xlsx` is the frozen reference and is never written by anything
here; `scripts/build_workbook.py` renders a fresh one into `build/`. Raw SEC responses are cached
under `pipeline/.cache/`, and `PIPELINE_OFFLINE=1` forbids the network entirely.

---

*Not investment advice. The numbers are as good as the assumptions, and the page is built so you
can see exactly which is which.*
