# SOURCE_MAP — Quarterly Refresh Data Provenance

**Status:** feasibility research. No pipeline built.
**Date of investigation:** 2026-08-31.
**Reconciliation basis:** every mapping below was reconciled against the Q2 2026 figures in `ai_capex_forward_roic_analysis_v02_methodology.md` by fetching live from `data.sec.gov`.
**Next refresh target:** quarter ending ~2026-09-30 (`report_bucket` = CY2026Q3). Q2 2026 is already in the model.
**Machine-readable companion:** `pipeline/source_map.json`.

---

## 0. The finding that matters most

**The SEC `companyfacts` API is not sufficient, and its failure modes are silent.**

`companyfacts` and `companyconcept` return **only undimensioned facts**. Two of the five demand facts are tagged with dimensional qualifiers, so the API either returns the *wrong number* or *nothing at all*:

| Filer | What `companyfacts` returns for `us-gaap:RevenueRemainingPerformanceObligation` | What the model needs | Failure mode |
|---|---|---|---|
| MSFT | `684,000,000,000` (total company RPO) | `678,000,000,000` (commercial RPO) | **Silently wrong by $6.0B (0.9%)** — looks like a valid number |
| AMZN | *nothing* (no fact since 2020-06-30) | `496,000,000,000` | **Silently empty** — looks like "no data this quarter" |

Both figures **do** exist in XBRL — as `ix:nonFraction` elements in the filing's primary inline-XBRL document, carrying dimensional contexts. They are machine-readable, but only via a filing-level iXBRL parse, never via `companyfacts`.

Any fetcher must branch on the `access` field in `source_map.json`:
- `companyfacts` — safe to use the JSON API
- `inline_xbrl_dimensional` — must download and parse the primary document
- `not_in_xbrl` — human required

*All `data.sec.gov` requests require a descriptive `User-Agent` header.*

---

## 1. Per-company map

### Microsoft — CIK `0000789019`

| | |
|---|---|
| Fiscal year end | **June 30** |
| Calendar alignment | **Aligned.** Quarter-*end dates* coincide with calendar quarters; only the fiscal-year *label* is offset. |
| `report_bucket` CY2026Q2 → `fiscal_period` | **FY2026 Q4**, period end 2026-06-30, Form 10-K |
| `report_bucket` CY2026Q3 → `fiscal_period` | **FY2027 Q1**, period end 2026-09-30, Form 10-Q |
| Typical release timing | Late Jan / late Apr / late Jul / late Oct. 8-K (Item 2.02) and the 10-K/10-Q are filed the **same day**. |
| Latest: 10-K filed 2026-07-29 | <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm> |
| Latest: 8-K Ex-99.1 filed 2026-07-29 | <https://www.sec.gov/Archives/edgar/data/789019/000119312526323632/msft-ex99_1.htm> |
| IR | <https://www.microsoft.com/en-us/investor> · earnings: <https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast> · event/webcast: <https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4> |
| SEC filing index | <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019&type=10-&dateb=&owner=include&count=40> · <https://data.sec.gov/submissions/CIK0000789019.json> |

**(a) Demand fact — commercial RPO — `auto`, but `inline_xbrl_dimensional`**

- Tag: `us-gaap:RevenueRemainingPerformanceObligation`, unit USD, instant = period end
- **Required dimension:** `srt:MajorCustomersAxis` = `msft:CommercialCustomersMember`
- Derivation: single fact, no arithmetic. Verified context id in the FY2026 10-K: `C_1afb830c-dfb8-425d-9873-198df856bdce`
- **Verified: 678,000,000,000 = model's $678.0B ✅**
- Corroborated in prose in both the 10-K MD&A and the 8-K press release: *"Commercial remaining performance obligation increased 84% to $678 billion."*
- Precision: tagged to **whole billions**. Do not expect million-level precision.
- ⚠ `companyfacts` returns 684,000,000,000 (total RPO). See §0.
- Fragility: depends on a **company extension member** (`msft:CommercialCustomersMember`) that Microsoft controls and could rename without notice.

**(b) Capex fact — management capex including finance leases — `manual`**

> **NOT MACHINE-READABLE — sourced from the earnings call / webcast (CFO prepared remarks).**

Exhaustively verified absent from SEC filings:
- The FY2026 10-K parses to 1,565 inline-XBRL facts; **none** equals ~$41B, and the phrase *"capital expenditures including finance leases"* does not occur anywhere in the document.
- The 8-K Exhibit 99.1 press release contains **no** capex line beyond the GAAP cash-flow item `Additions to property and equipment (35,802)`.

Human source: <https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4>

*Optional XBRL proxy — use as a sanity check only, never as a substitute:*

```
proxy = (PaymentsToAcquirePropertyPlantAndEquipment[quarter])
      + (RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability[quarter])
```
For Q4 (10-K only, no quarterly column) each term is `FY − 9M`:
```
cash PP&E : 115,948 − 80,146 = 35,802   ← matches the press-release quarterly column exactly
FL ROU add:  24,608 − 19,486 =  5,122
proxy     =                    40,924   vs reported 41,000  → −76 ($0.076B, −0.19%)
```
**This is an approximation, not an identity.** Microsoft has never published a reconciliation between the management metric and these GAAP tags. Microsoft's IR event page states the $41B comprises ~$35.8B cash plus a finance-lease component; a secondary source puts that component at $5.6B, which does **not** sum to $41.0B on a $35.8B cash base. The composition is therefore **UNVERIFIED** and the proxy must not be trusted to the reported figure's precision.

Note also: in Q1–Q3 Microsoft **does** tag standalone 3-month cash-flow durations in its 10-Qs, so the proxy needs no differencing except in Q4.

**Annual denominator — CY2026 outlook ~$175.0B — `manual`.** Verified absent from both the 10-K and the 8-K.

---

### Alphabet — CIK `0001652044`

| | |
|---|---|
| Fiscal year end | **December 31** |
| Calendar alignment | Aligned; fiscal year = calendar year |
| `report_bucket` CY2026Q2 → `fiscal_period` | FY2026 Q2, period end 2026-06-30, Form 10-Q |
| `report_bucket` CY2026Q3 → `fiscal_period` | FY2026 Q3, period end 2026-09-30, Form 10-Q |
| Typical release timing | Early Feb / late Apr / **late Jul (earliest of the five)** / late Oct. 8-K one day before the 10-Q. |
| Latest: 10-Q filed 2026-07-23 | <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm> |
| Latest: 8-K Ex-99.1 filed 2026-07-22 | <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000066/googexhibit991q22026.htm> |
| IR | <https://abc.xyz/investor/> |
| SEC filing index | <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001652044&type=10-&dateb=&owner=include&count=40> · <https://data.sec.gov/submissions/CIK0001652044.json> |

**(a) Demand fact — revenue backlog — `auto` via `companyfacts`**

- Tag: `us-gaap:RevenueRemainingPerformanceObligation`, unit USD, instant = period end, **undimensioned**
- Derivation: single fact, no arithmetic
- **Verified: 519,500,000,000 = model's $519.5B ✅**
- Prose: *"As of June 30, 2026, we had $519.5 billion of remaining performance obligations ("revenue backlog"), of which $513.9 billion related to Google Cloud."*
- ⚠ A filing-level iXBRL parser will also see **513,900,000,000** (Google Cloud subset, segment-dimensioned). The model uses the **total**. `companyfacts` correctly returns only the total.

**(b) Capex fact — cash PP&E — `derived` via `companyfacts`**

- Tag: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`, unit USD, duration
- **Alphabet's 10-Q cash flow statement presents year-to-date columns only** — it never tags a standalone 3-month cash-flow duration.

```
capex[Q] = PaymentsToAcquirePropertyPlantAndEquipment[FY_start → period_end]
         − PaymentsToAcquirePropertyPlantAndEquipment[FY_start → prior_period_end]

Q2 2026:  80,598 − 35,674 = 44,924
Q3 2026:  PPE[2026-01-01→2026-09-30] − PPE[2026-01-01→2026-06-30]
```
- **Verified: 44,924,000,000 = model's $44.924B ✅**
- Q1 needs no differencing (YTD = quarter). Q4 = 10-K annual − Q3 10-Q 9-month YTD.
- Independent cross-check: the 8-K free-cash-flow reconciliation prints the four quarterly figures explicitly — `(23,953) (27,851) (35,674) (44,924)`.

**Annual denominator — FY2026 outlook $195–205B (midpoint $200.0B) — `manual`.** Verified absent from both the 10-Q and the 8-K press release; given on the earnings call only (raised from $180–190B at Q1 2026).

---

### Amazon — CIK `0001018724`

| | |
|---|---|
| Fiscal year end | **December 31** |
| Calendar alignment | Aligned; fiscal year = calendar year |
| `report_bucket` CY2026Q2 → `fiscal_period` | FY2026 Q2, period end 2026-06-30, Form 10-Q |
| `report_bucket` CY2026Q3 → `fiscal_period` | FY2026 Q3, period end 2026-09-30, Form 10-Q |
| Typical release timing | Early Feb / late Apr–early May / late Jul–early Aug / late Oct. **Latest filer of the calendar-year three.** 8-K one day before the 10-Q. |
| Latest: 10-Q filed 2026-07-31 | <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm> |
| Latest: 8-K Ex-99.1 filed 2026-07-30 | <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm> |
| IR | <https://ir.aboutamazon.com/> |
| SEC filing index | <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001018724&type=10-&dateb=&owner=include&count=40> · <https://data.sec.gov/submissions/CIK0001018724.json> |

**(a) Demand fact — long-term commitments / RPO — `auto`, but `inline_xbrl_dimensional`**

- Tag: `us-gaap:RevenueRemainingPerformanceObligation`, unit USD, instant = period end
- **Required typed dimension:** `us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis`
  - Typed member value for Q2 2026 was `2026-07-01` — **the day after period end. It changes every quarter.** Match on *axis presence*, never on a hardcoded date.
- **Forbidden dimension:** `srt:MajorCustomersAxis` — must be absent
- Verified context id: `c-46`
- **Verified: 496,000,000,000 = model's $496.0B ✅**
- Prose: *"For contracts with original terms that exceed one year, those commitments not yet recognized were approximately $496 billion as of June 30, 2026. The weighted-average remaining life of our long-term contracts is 6.4 years."*
- ⚠ `companyfacts` returns **nothing** for Amazon RPO after 2020-06-30. See §0.
- ⚠ Sibling fact in the same filing: **38,000,000,000** — the OpenAI-specific commitment, tagged `srt:MajorCustomersAxis` = `amzn:OpenAIGroupPBCMember`. Exclude it.

**(b) Capex fact — gross cash PP&E — `auto` via `companyfacts`**

- Tag: **`us-gaap:PaymentsToAcquireProductiveAssets`** (not the PPE tag — see trap T6), unit USD, duration
- **Amazon uniquely tags standalone 3-month cash-flow durations**, so no YTD differencing is needed in any quarter.
- **Verified: 54,208,000,000 for 2026-04-01 → 2026-06-30 = model's $54.208B ✅**
- Cross-check: 8-K cash flow statement, three-months-ended column — `Purchases of property and equipment (32,183) (54,208)`.

**Annual denominator — FY2026 plan ~$200.0B — `manual`.** Verified absent from the 8-K press release, which contains no capital-expenditure outlook at all.

---

### Oracle — CIK `0001341439`

| | |
|---|---|
| Fiscal year end | **May 31** |
| Calendar alignment | **OFFSET — the only genuinely offset filer.** Quarters end Aug / Nov / Feb / May, one month *before* the calendar quarter. |
| `report_bucket` CY2026Q2 → `fiscal_period` | **FY2026 Q4**, period end **2026-05-31** (Mar–May), Form 10-K |
| `report_bucket` CY2026Q3 → `fiscal_period` | **FY2027 Q1**, period end **2026-08-31** (Jun–Aug), Form 10-Q |
| Typical release timing | Mid-Sep / mid-Dec / mid-Mar / mid-Jun. 8-K then 10-Q **+1 day**; but at year end the 8-K → 10-K gap was **12 days** (2026-06-10 → 2026-06-22). |
| Latest: 10-K filed 2026-06-22 | <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm> |
| Latest: 8-K Ex-99.1 filed 2026-06-10 | <https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm> |
| Q4 FY26 slides | <https://s23.q4cdn.com/440135859/files/doc_financials/2026/q4/Q4-FY26-Oracle-Earnings-Slides.pdf> |
| IR | <https://investor.oracle.com/> |
| SEC filing index | <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001341439&type=10-&dateb=&owner=include&count=40> · <https://data.sec.gov/submissions/CIK0001341439.json> |

**(a) Demand fact — RPO — `auto` via `companyfacts`**

- Tag: `us-gaap:RevenueRemainingPerformanceObligation`, unit USD, instant = fiscal period end, **undimensioned**
- **Verified: 638,000,000,000 at instant 2026-05-31 = model's $638.0B ✅**
- Prose: *"Remaining Performance Obligations, or RPO, ended the quarter at $638 billion, up 363% USD year-over-year and up $85 billion sequentially from the end of Q3."*
- Note the instant is **2026-05-31**, not 2026-06-30. A fetcher keyed to calendar quarter ends will miss it.

**(b) Capex fact — GAAP cash capex — `derived` via `companyfacts`**

- Tag: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`, unit USD, duration
- Oracle's 10-Q cash flow statement presents **year-to-date columns only**. Fiscal year starts **June 1**.

```
capex[Q] = PaymentsToAcquirePropertyPlantAndEquipment[FY_start → period_end]
         − PaymentsToAcquirePropertyPlantAndEquipment[FY_start → prior_period_end]

FY26 Q4 (CY2026Q2 bucket):  55,663 − 39,170 = 16,493
FY27 Q1 (CY2026Q3 bucket):  PPE[2026-06-01 → 2026-08-31] used DIRECTLY — Q1 YTD is the quarter
```
- **Verified: 16,493,000,000 = model's $16.493B ✅**

**Annual denominator — FY2026 actual $55.663B — `auto` ✅**

Uniquely among the five, Oracle's denominator is a **filed GAAP actual**, not an outlook: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` for 2025-06-01 → 2026-05-31 = **55,663,000,000**, verified. Fully automatable — but only because the methodology deliberately chose the completed actual over Oracle's non-comparable FY2027 guide (see trap T1).

---

### Meta — CIK `0001326801`

| | |
|---|---|
| Fiscal year end | **December 31** |
| Calendar alignment | Aligned; fiscal year = calendar year |
| `report_bucket` CY2026Q2 → `fiscal_period` | FY2026 Q2, period end 2026-06-30, Form 10-Q |
| `report_bucket` CY2026Q3 → `fiscal_period` | FY2026 Q3, period end 2026-09-30, Form 10-Q |
| Typical release timing | Late Jan / late Apr / late Jul / late Oct. 8-K one day before the 10-Q. |
| Latest: 10-Q filed 2026-07-30 | <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm> |
| Latest: 8-K Ex-99.1 filed 2026-07-29 | <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm> |
| IR | <https://investor.atmeta.com/> |
| SEC filing index | <https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001326801&type=10-&dateb=&owner=include&count=40> · <https://data.sec.gov/submissions/CIK0001326801.json> |

**(a) Demand fact — quarterly revenue — `auto` via `companyfacts`**

- Tag: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`, unit USD, duration = the quarter, undimensioned
- Meta tags standalone 3-month **income-statement** durations (unlike its cash-flow items), so no differencing.
- **Verified: 60,801,000,000 for 2026-04-01 → 2026-06-30 = model's $60.801B ✅**
- Meta discloses **no RPO** — confirmed: `us-gaap:RevenueRemainingPerformanceObligation` does not exist in Meta's company facts at all. This is why the model substitutes revenue. It is the easiest of the five to automate and the least comparable in substance: a realized flow, not a contracted stock.

**(b) Capex fact — capex including finance-lease principal — `derived` via `companyfacts`**

- Tags: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` + `us-gaap:FinanceLeasePrincipalPayments`, both USD, duration
- Meta's 10-Q cash flow statement presents **year-to-date columns only**, so **both** components need differencing.

```
capex[Q] = (PPE[FY_start → period_end] − PPE[FY_start → prior_period_end])
         + (FLP[FY_start → period_end] − FLP[FY_start → prior_period_end])

Q2 2026: (49,113 − 18,997) + (1,805 − 843)
       =  30,116           +    962        = 31,078
```
- **Verified: 31,078,000,000 = model's $31.078B ✅**
- Cross-check: 8-K press release — *"Capital expenditures, including principal payments on finance leases, were $31.08 billion."* The XBRL derivation is **more precise** than the rounded press-release figure.
- ⚠ Meta's definition uses finance-lease **principal payments** (`FinanceLeasePrincipalPayments`, a financing-activity cash outflow). Microsoft's management metric appears to use finance-lease **ROU asset additions** (`RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability`). **These are different concepts. Do not share one formula across the two companies.**

**Annual denominator — FY2026 outlook $130–145B (midpoint $137.5B) — `manual` (prose in an SEC-filed 8-K).** Unlike MSFT/GOOG/AMZN, Meta's outlook *is* in a filed document, but as untagged text. See trap T7.

---

## 2. Automation tier summary

| Company | (a) Demand fact | Tier | Access | (b) Capex fact | Tier | Access |
|---|---|---|---|---|---|---|
| MSFT | Commercial RPO $678B | `auto` | **iXBRL dimensional** | Mgmt capex incl. finance leases $41.0B | **`manual`** | not in XBRL |
| GOOG | Revenue backlog $519.5B | `auto` | companyfacts | Cash PP&E $44.924B | `derived` | companyfacts |
| AMZN | Commitments/RPO $496B | `auto` | **iXBRL dimensional** | Gross cash PP&E $54.208B | `auto` | companyfacts |
| ORCL | RPO $638B | `auto` | companyfacts | Cash capex $16.493B | `derived` | companyfacts |
| META | Quarterly revenue $60.801B | `auto` | companyfacts | Capex incl. FL principal $31.078B | `derived` | companyfacts |

**Core facts: 6 `auto`, 3 `derived`, 1 `manual` — 9 of 10 machine-readable.**

Annual denominators (a third input the methodology also requires): **1 `auto` (ORCL), 4 `manual`.**

---

## 3. Definitional traps the automation must not fall into

Each entry states what a naive scraper would grab and why it would be wrong.

### T1 — Oracle: "net cash outlay for capex" is not GAAP capex
**Naive grab:** search Oracle's earnings release or slides for "capital expenditures", take the headline number → **$47,726M** (FY2026 net cash outlay) or the **~$70B** FY2027 guide.
**Why wrong:** Oracle's press release carries a non-GAAP table, *"NET CASH OUTLAY FOR CAPITAL EXPENDITURES — TRAILING FOUR-QUARTERS"*, which deducts short-term capex financing and customer prepayments with a significant financing component:
```
FY2026:  Capital Expenditures            (55,663)
         Less: short-term financing         3,345
         Less: customer prepayments         4,592
         Net Cash Outlay for Capex       (47,726)
```
The model uses **GAAP gross cash capex, $55,663M**. The ~$70B FY2027 guide is on the *net outlay* basis and is not interchangeable with it — which is exactly why the methodology uses the completed FY2026 actual instead of carrying a guide forward.
Sources: <https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm> · <https://s23.q4cdn.com/440135859/files/doc_financials/2026/q4/Q4-FY26-Oracle-Earnings-Slides.pdf>

### T2 — Oracle: the press-release capex table is trailing-four-quarters, not quarterly or YTD
**Naive grab:** read the Q1/Q2/Q3 column of Oracle's capex table as that quarter's spend.
**Why wrong:** the table is explicitly TTM. FY26 Q3 shows **48,250**, whereas the 9-month YTD in XBRL is **39,170** (48,250 = 39,170 + (21,215 − 12,135)). Only the Q4 column coincides with the fiscal year. Take capex from XBRL and difference the YTD figures; never read this table.
Source: <https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm>

### T3 — Microsoft: the CY2026 outlook fell from ~$190B to ~$175B for accounting reasons, not less investment
**Naive grab:** treat the $15B reduction as a capex cut and let the model's snapshot spread improve.
**Why wrong:** Microsoft extended estimated useful lives for datacenters and office buildings (15 → 25 years), which shifts more future datacenter leases from **finance** leases to **operating** leases. Finance leases count in the management capex metric; operating leases do not. Underlying investment did not fall — in the same quarter, capex including finance leases rose ~70% YoY to $41.0B. Any period-over-period comparison of Microsoft's annual denominator across this change is mechanical, not economic.
Sources: <https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4> · <https://www.cnbc.com/2026/04/29/microsoft-msft-q3-earnings-report-2026.html> (prior $190B) · <https://www.benzinga.com/markets/tech/26/07/60808802/microsofts-15-billion-capex-cut-isnt-a-cut-at-all>

### T4 — Microsoft: total RPO ≠ commercial RPO
**Naive grab:** `companyconcept/CIK0000789019/us-gaap/RevenueRemainingPerformanceObligation` → **$684B**.
**Why wrong:** that is *total company* RPO. The model uses *commercial* RPO, **$678B**, which is a separate dimensioned fact (`srt:MajorCustomersAxis` = `msft:CommercialCustomersMember`). The $6.0B gap is small enough to pass a range check and large enough to matter. This is the single most dangerous trap in the set because it fails silently.
Source: <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm>

### T5 — Alphabet: the backlog definition changed in Q1 2026
**Naive grab:** build a time series of `RevenueRemainingPerformanceObligation` and read the jump from $242.8B (Q4 2025) to $467.6B (Q1 2026) to $519.5B (Q2 2026) as pure demand growth.
**Why wrong:** the 10-Q states *"In the first quarter of 2026, we elected to change our reporting of revenue backlog to also include contracts with an original expected term of one year or less."* Q1 2026 onward is on the new definition; 2025 and earlier are not. Alphabet also now sells **TPU systems** as product sales within Cloud, so the backlog composition has shifted toward hardware sale agreements. **Q1-to-Q2 2026 is comparable; any comparison spanning Q4 2025 → Q1 2026 is not.** The pipeline should carry a per-quarter `definition_version` flag rather than silently splicing the series.
Source: <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>

### T6 — Amazon: gross vs net capex, in the same document
**Naive grab:** search Amazon's 10-Q for "capital expenditures" → *"Cash capital expenditures were $31.4 billion and $53.1 billion during Q2 2025 and Q2 2026"* → **$53.1B**.
**Why wrong:** Amazon's MD&A "cash capital expenditures" is **net** of *"Proceeds from property and equipment sales and incentives"* ($1,132M in Q2 2026): 54,208 − 1,132 = 53,076 ≈ $53.1B. The model uses **gross, $54.208B**, the cash-flow-statement line. Amazon's free-cash-flow reconciliation is also on the net basis. Additionally, the right tag is **`us-gaap:PaymentsToAcquireProductiveAssets`**, not the more familiar `PaymentsToAcquirePropertyPlantAndEquipment` — Amazon tags **both**, and only the former carries the cash-flow-statement value.
Source: <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm>

### T7 — Meta: the guidance sentence contains the superseded range too
**Naive grab:** regex a `$X-Y billion` range near "capital expenditures" in Meta's 8-K.
**Why wrong:** the sentence is *"We anticipate 2026 capital expenditures, including principal payments on finance leases, to be in the range of **$130-145 billion**, narrowed from our prior outlook of **$125-145 billion**."* Both ranges sit in one sentence. "First match" is correct only by luck of word order; "last match in sentence" grabs the superseded figure. The same paragraph also contains a $165–169B **total expenses** range, which a looser regex would capture instead.
Source: <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm>

### T8 — Every YTD cash-flow filer: never read a cumulative figure as a quarter
**Naive grab:** pull `PaymentsToAcquirePropertyPlantAndEquipment` for the latest period and call it the quarter.
**Why wrong:** GOOG, ORCL and META tag **only year-to-date** cash-flow durations. Alphabet's latest Q2 2026 figure is **80,598** (6 months), not 44,924. Amazon is the only filer that tags standalone 3-month cash-flow durations; Microsoft tags them in Q1–Q3 but not Q4. A fetcher must inspect the `start`/`end` pair on every duration fact and never assume the newest fact is a quarter.

### T9 — Alphabet: $811.0B purchase commitments is not the backlog
**Naive grab:** the largest "commitments" number in Alphabet's 10-Q → **$811.0 billion**.
**Why wrong:** that is Alphabet's *purchase commitments and other contractual obligations* — what Alphabet owes suppliers (technical infrastructure, content licenses, energy take-or-pay), the opposite direction of the revenue backlog the model needs ($519.5B). Similarly, Amazon's `us-gaap:ContractualObligation` = **$650.034B** at 2026-06-30 is total contractual obligations including debt and leases, **not** the $496B customer commitment figure.
Source: <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>

### T10 — Amazon: the RPO axis member is a moving date
**Naive grab:** hardcode the typed-member value `2026-07-01` when selecting Amazon's RPO fact.
**Why wrong:** the typed member on `RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis` is the day *after* period end and advances every quarter (Q3 2026 will be `2026-10-01`). Match on **axis presence**, and exclude any context carrying `srt:MajorCustomersAxis` (which selects the $38B OpenAI-specific commitment instead).

### T11 — Amazon: $200.6B net sales vs the ~$200B capex plan
**Naive grab:** a regex for "$200" near Amazon capex language.
**Why wrong:** Amazon's Q2 2026 **net sales** were $200.6B — numerically adjacent to the $200B annual capex plan the model carries. The capex plan is not in the press release at all; the only $200-ish figures in that document are revenue.
Source: <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm>

### T12 — MSFT vs META: "including finance leases" means two different things
**Naive grab:** apply one "cash PP&E + finance leases" formula to both companies.
**Why wrong:** Meta's disclosed metric adds finance-lease **principal payments** (`FinanceLeasePrincipalPayments` — a financing cash outflow, $962M in Q2 2026). Microsoft's metric appears to add finance-lease **ROU asset additions** (`RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability` — a non-cash commencement event, $5,122M in Q4 FY26). Using Meta's formula on Microsoft would give 35,802 + 922 = **36,724**, understating the reported $41.0B by ~10%.

### T13 — Oracle: period ends do not match calendar quarter ends
**Naive grab:** query Oracle's RPO at instant `2026-06-30` because the bucket is "Q2 2026".
**Why wrong:** Oracle's fact sits at **2026-05-31**. Querying the calendar quarter end returns nothing. Every Oracle lookup must use the fiscal period end from `report_bucket_map`, and every Oracle bucket carries a one-month timing mismatch against the other four that no amount of automation removes.

### T14 — Prepaid and customer-supplied hardware inflates Oracle's RPO relative to its own capital need
**Naive grab:** treat Oracle's $638B RPO as economically equivalent to Alphabet's or Microsoft's backlog.
**Why wrong:** Oracle disclosed that *"Most of the RPO increase in both Q3 and Q4 were large scale AI contracts where the customer prepaid Oracle for the purchase of the GPUs, or the customer bought and supplied the GPUs to Oracle."* The methodology notes ~$75B of prepaid or customer-supplied hardware reduces Oracle's own capital requirement. The RPO number is machine-readable; its comparability to the other four is a judgement call that is not.
Source: <https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm>

### T15 — Precision is not uniform, and rounding is not error
**Naive grab:** a reconciliation test that requires exact equality across all facts.
**Why wrong:** MSFT ($678B), AMZN ("approximately $496 billion") and ORCL ($638B) tag their demand facts to **whole billions**; Alphabet tags to one decimal ($519.5B). Cash-flow items are tagged to the million. A tolerance check must be per-fact, not global. Conversely, do not "improve" a figure by taking a more precise-looking number from elsewhere — Meta's press release says $31.08B while the XBRL derivation gives $31.078B, and the derivation is the better value.

### T16 — A related-party revenue disclosure is one counterparty, not AI revenue
**Naive grab:** treating Microsoft's disclosed OpenAI revenue as "Microsoft's AI revenue", or pulling `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax` without its dimension.
**The disclosure:** Microsoft's FY2026 10-K states that it "recorded revenue from commercial arrangements with OpenAI, inclusive of revenue-sharing payments, of **$24.1 billion**, and accounts receivable from OpenAI as of June 30, 2026 was **$6.0 billion**." It appears only because Microsoft's ~25% as-converted stake makes OpenAI an equity-method related party under ASC 850 — it is compelled by the accounting for the stake, not chosen as AI reporting. It is annual and appears in the 10-K only.
**Why wrong, twice.** *Mechanically:* the axis is the whole disclosure. That us-gaap concept is the **same one Microsoft uses for total revenue**; undimensioned it returns **$331,839M** for FY2026, 13.8× too large and entirely plausible-looking. Select on `srt:ScheduleOfEquityMethodInvestmentEquityMethodInvesteeNameAxis = msft:OpenAIGlobalLlcMember` or refuse. This is T4's failure mode on a different fact. *Substantively:* it covers **one counterparty**. It excludes Copilot, Foundry and Azure AI sold to every other customer, so it is a **floor** on Microsoft's AI revenue — never a substitute for the AI revenue proxy, never a replacement for the demand fact. The guard FAILs on the mechanical error and always asks a human about the substantive one.
**What it is good for:** the model's Q2 2026 proxy is $678.0B × 50% ÷ 2.5y = **$135.6B**, which is **5.6×** the disclosed figure. Read the other way, the model implicitly claims Microsoft earns roughly **$111B of AI revenue from customers who are not OpenAI**. That is now checkable rather than unfalsifiable, and it is the only audited AI-linked revenue anchor anywhere in this model.

### T17 — The absence of that disclosure elsewhere is an accounting artifact
**Naive read:** "Only Microsoft has real AI revenue; the others disclose none."
**Why wrong:** Amazon's Q2 2026 10-Q names a **$38.0B OpenAI commitment expanded by $100.0B over 8 years** and an **Anthropic collaboration expanded by more than $100.0B over 10 years** — larger named counterparty exposure than Microsoft's — and reports **no revenue** from either. Not because there is none, but because its stakes are convertible notes and nonvoting preferred carried at fair value rather than equity-method holdings, so neither counterparty is a related party and nothing is compelled. Alphabet names Anthropic once and holds no equity-method AI investee; Oracle states the ASC 850 rule but has no material one; Meta has no such investment at all. The guard is INFO on all four. **Never read the silence as evidence, and never rank an unquantified exposure against a quantified one as though the difference were commercial rather than accounting.**

---

## 4. Bottom line — how much of the refresh can be automated

**Blunt verdict: 9 of the 10 core facts (90%) can be refreshed without a human reading a filing — but only with a fetcher that parses inline XBRL, not one that calls `companyfacts` alone. A `companyfacts`-only pipeline gets 7 of 10 right, 1 silently wrong, and 1 silently missing, which is worse than useless.**

Counting the annual denominators the model also consumes, the honest figure is **10 of 15 inputs (67%)**.

**Always machine-readable (8 facts, high confidence — all reconciled to the cent against Q2 2026):**
- GOOG backlog, ORCL RPO, META revenue, AMZN gross capex — single `companyfacts` lookups
- GOOG capex, ORCL capex, META capex — deterministic YTD differencing over verified tags
- ORCL annual denominator — a filed GAAP actual

**Machine-readable but requires filing-level iXBRL parsing (2 facts):**
- MSFT commercial RPO, AMZN commitments/RPO. Deterministic once implemented, but each depends on a **company extension member or typed axis the filer controls** (`msft:CommercialCustomersMember`, `amzn:OpenAIGroupPBCMember`) and could be renamed or restructured without notice. These need an assertion that the selected fact exists and a hard failure — never a fallback to the undimensioned value — if it does not.

**Will always need human judgement (5 inputs):**
1. **Microsoft's quarterly management capex ($41.0B).** It exists in no SEC filing. The best XBRL proxy lands $76M (0.19%) away this quarter, but the identity is unpublished and its composition is unverified. **This one field alone prevents a fully unattended refresh.**
2. **Microsoft's CY2026 capex outlook (~$175B).** Call-only, and its movement is contaminated by accounting-policy changes (T3) that require a human to interpret.
3. **Alphabet's FY2026 capex range ($195–205B).** Call-only; absent from both the 10-Q and the 8-K.
4. **Amazon's FY2026 capital plan (~$200B).** Call-only; the methodology is already carrying a stale figure forward because Q2 2026 produced no replacement — a staleness decision no scraper can make.
5. **Meta's FY2026 capex range ($130–145B).** In a filed 8-K but as untagged prose, in a sentence that also contains the superseded range. Regex-extractable at ~90% confidence; that is not good enough for a model input, so treat it as human-confirmed.

**Judgement calls that are not "fields" at all but will break the model if automated away:** the duration assumptions (Amazon disclosed 6.4 years while the model retains 4.0 — the methodology's own largest identified sensitivity; Microsoft disclosed 2.3 years against a retained 2.5), the AI-attribution shares, and whether a definition change (T5) or an accounting-policy change (T3) has broken comparability with the prior quarter. A refresh bot can *flag* these — e.g. by diffing the disclosed weighted-average life and the backlog-definition language quarter over quarter — but cannot resolve them.

**Recommended architecture:** automate the 9 core facts with hard reconciliation assertions (every derived figure cross-checked against the press-release quarterly column where one exists — GOOG, AMZN, MSFT cash PP&E and META all publish one), then block the refresh on a short human checklist covering the five manual inputs plus a diff of the definitional language in T3/T5/T14. That is roughly **five numbers and three paragraphs of reading per quarter**, down from all fifteen.
