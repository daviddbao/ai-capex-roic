# EARNINGS_CALENDAR — Refresh Trigger Dates

**Date of investigation:** 2026-08-31.
**Source of all observed dates:** SEC EDGAR submissions API — `https://data.sec.gov/submissions/CIK##########.json` (requires a descriptive `User-Agent`).
**Companion:** `docs/SOURCE_MAP.md`, `pipeline/source_map.json`.

---

## 1. Correction to a common assumption

It is natural to assume that because Microsoft's fiscal year ends in June and Oracle's in May, *both* report on a schedule offset from the calendar-year three. **That is not what the filings show.**

- **Microsoft's quarter-END dates coincide exactly with calendar quarters** (Sep 30 / Dec 31 / Mar 31 / Jun 30). Only the fiscal-year *label* is offset. Microsoft reports in the **same four windows** as Alphabet, Amazon and Meta — in fact it is usually the *first* of the four to file.
- **Oracle is the only genuinely offset filer.** Its quarters end Aug 31 / Nov 30 / Feb 28 / May 31 — one month before the calendar quarter — and it reports ~6 weeks ahead of the calendar-year cluster.

So the `report_bucket` vs `fiscal_period` distinction matters for **both** MSFT and ORCL, but the *scheduling* problem is Oracle's alone.

---

## 2. Observed filing dates

`8-K` = Item 2.02 earnings release (the first public appearance of the numbers).
`10-x` = the 10-Q or 10-K carrying the XBRL facts the pipeline actually consumes.

### Calendar-quarter filers (MSFT, GOOG, AMZN, META)

| Quarter end | MSFT 8-K / 10-x | GOOG 8-K / 10-x | AMZN 8-K / 10-x | META 8-K / 10-x |
|---|---|---|---|---|
| 2024-12-31 | 2025-01-29 / 01-29 | 2025-02-04 / 02-05 | 2025-02-06 / 02-07 | 2025-01-29 / 01-30 |
| 2025-03-31 | 2025-04-30 / 04-30 | 2025-04-24 / 04-25 | 2025-05-01 / 05-02 | 2025-04-30 / 05-01 |
| 2025-06-30 | 2025-07-30 / 07-30 | 2025-07-23 / 07-24 | 2025-07-31 / 08-01 | 2025-07-30 / 07-31 |
| 2025-09-30 | 2025-10-29 / 10-29 | 2025-10-29 / 10-30 | 2025-10-30 / 10-31 | 2025-10-29 / 10-30 |
| 2025-12-31 | 2026-01-28 / 01-28 | 2026-02-04 / 02-05 | 2026-02-05 / 02-06 | 2026-01-28 / 01-29 |
| 2026-03-31 | 2026-04-29 / 04-29 | 2026-04-29 / 04-30 | 2026-04-29 / 04-30 | 2026-04-29 / 04-30 |
| 2026-06-30 | 2026-07-29 / 07-29 | 2026-07-22 / 07-23 | 2026-07-30 / 07-31 | 2026-07-29 / 07-30 |

Patterns:
- **Microsoft files the 8-K and the 10-K/10-Q on the same day.** The other three file the 10-Q **one day after** the 8-K.
- **Alphabet is consistently first** (Jul 22–23 in 2026; Feb 4–5 at year end). **Amazon is consistently last.**
- The **Q4/annual window is the widest** — the 10-K cluster spreads across ~10 calendar days (2026-01-28 → 2026-02-06), because Alphabet and Amazon report ~a week later than Microsoft and Meta at year end.
- The **Q1 window is the tightest** — in 2026 all four filed the 8-K on the *same day*, 2026-04-29.

### Oracle (fiscal year ends May 31)

| Fiscal period | Quarter end | 8-K | 10-Q / 10-K | 8-K → filing gap |
|---|---|---|---|---|
| FY2025 Q3 | 2025-02-28 | 2025-03-10 | 2025-03-11 (10-Q) | 1 day |
| FY2025 Q4 | 2025-05-31 | 2025-06-11 | 2025-06-18 (10-K) | 7 days |
| FY2026 Q1 | 2025-08-31 | 2025-09-09 | 2025-09-10 (10-Q) | 1 day |
| FY2026 Q2 | 2025-11-30 | 2025-12-10 | 2025-12-11 (10-Q) | 1 day |
| FY2026 Q3 | 2026-02-28 | 2026-03-10 | 2026-03-11 (10-Q) | 1 day |
| FY2026 Q4 | 2026-05-31 | 2026-06-10 | **2026-06-22 (10-K)** | **12 days** |

Patterns:
- Oracle reports **~10 days after quarter end**, far faster than the calendar-year filers (~30 days).
- 10-Qs follow the 8-K by **1 day**, but the **10-K lagged by 12 days in 2026** (7 in 2025). A pipeline that waits for the 10-K after Oracle's June 8-K will idle for up to two weeks. Oracle's RPO and capex facts only become XBRL-available with that 10-K.

---

## 3. Distinct refresh trigger windows per year

**There are 8 distinct windows per year, in 2 families:**

| # | Window | Filers | Approx. dates | Spread |
|---|---|---|---|---|
| A1 | Q4 / annual | MSFT, GOOG, AMZN, META | late Jan → early Feb | ~10 days |
| A2 | Q1 | MSFT, GOOG, AMZN, META | late Apr → early May | ~2 days |
| A3 | Q2 | MSFT, GOOG, AMZN, META | Jul 22 → Aug 1 | ~10 days |
| A4 | Q3 | MSFT, GOOG, AMZN, META | late Oct | ~3 days |
| O1 | ORCL FY Q1 | ORCL | ~Sep 9–15 | 1–2 days |
| O2 | ORCL FY Q2 | ORCL | ~Dec 10–11 | 1–2 days |
| O3 | ORCL FY Q3 | ORCL | ~Mar 10–11 | 1–2 days |
| O4 | ORCL FY Q4 (annual) | ORCL | ~Jun 10–22 | up to 12 days |

**Practical scheduling consequence:** each of the four A-windows needs roughly **two polling passes** (one at the leading edge for Microsoft/Meta/Alphabet, one ~5 business days later for Amazon and the year-end 10-Ks) rather than a single fixed date. Oracle's four windows are single-filer and tight, except O4.

**Net: ~8 trigger events, ~12 polling passes per year.** Because Oracle's O1 and the A4 window are ~6 weeks apart, a *complete* five-company snapshot for any calendar-quarter bucket is only available after the **last** filer in that bucket files — which is Amazon, ~30 days after calendar quarter end.

---

## 4. The next refresh — `report_bucket` CY2026Q3

Quarter ending ~2026-09-30. Everything below is **forward-looking and therefore UNVERIFIED** except where noted; dates are extrapolated from the observed pattern above.

| Company | `fiscal_period` | Period end | Expected 8-K | Expected 10-x | Basis |
|---|---|---|---|---|---|
| **ORCL** | **FY2027 Q1** | **2026-08-31** | **~2026-09-14** | ~2026-09-15 (10-Q) | Third-party earnings calendars report Sep 14, 2026, after close. **UNVERIFIED against a primary source** — Oracle typically confirms ~2 weeks ahead. Consistent with the observed FY26 Q1 date of 2025-09-09. |
| GOOG | FY2026 Q3 | 2026-09-30 | ~2026-10-27/28 | +1 day | 2025 analog: 8-K 10-29, 10-Q 10-30 |
| META | FY2026 Q3 | 2026-09-30 | ~2026-10-28 | +1 day | 2025 analog: 8-K 10-29, 10-Q 10-30 |
| MSFT | **FY2027 Q1** | 2026-09-30 | ~2026-10-28 | same day | 2025 analog: 8-K 10-29, 10-Q 10-29 |
| AMZN | FY2026 Q3 | 2026-09-30 | ~2026-10-29 | +1 day | 2025 analog: 8-K 10-30, 10-Q 10-31 |

**Two trigger events for this refresh: one in mid-September (Oracle alone), one in late October (the other four).** The bucket cannot be closed until Amazon's 10-Q lands, ~2026-10-30.

### Period-selection notes for this specific refresh

Derivation changes materially between quarters — do not reuse the Q2 formulas:

| Company | Capex derivation for CY2026Q3 | Change vs Q2 |
|---|---|---|
| MSFT | proxy = `PaymentsToAcquirePropertyPlantAndEquipment[2026-07-01→2026-09-30]` + `RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability[same]`, **used directly** | Q2 needed `FY − 9M` because only the 10-K existed. FY27 Q1 YTD **is** the quarter. (The headline figure remains `manual` regardless.) |
| GOOG | `PPE[2026-01-01→2026-09-30] − PPE[2026-01-01→2026-06-30]` | same shape, shifted |
| AMZN | `PaymentsToAcquireProductiveAssets[2026-07-01→2026-09-30]`, **direct** | unchanged — Amazon tags standalone quarters |
| ORCL | `PPE[2026-06-01→2026-08-31]`, **used directly** | Q2 needed `FY − 9M`. **FY27 Q1 YTD is the quarter — no differencing.** |
| META | `(PPE[1/1→9/30] − PPE[1/1→6/30]) + (FLP[1/1→9/30] − FLP[1/1→6/30])` | same shape, shifted |

Demand-fact instants: **2026-09-30** for MSFT, GOOG, AMZN, META; **2026-08-31** for ORCL. Amazon's typed-axis member will read **`2026-10-01`**, not `2026-07-01` — match on axis presence, never on the date (see trap T10 in `SOURCE_MAP.md`).

---

## 5. Recommended trigger mechanism

Do not schedule on fixed calendar dates — the observed dates move by up to a week year over year. **Poll the submissions API instead:**

```
https://data.sec.gov/submissions/CIK<10-digit>.json
```

Fire the refresh for a company when `filings.recent` contains a `10-Q`/`10-K` whose `reportDate` equals the target period end. Use the 8-K (Item 2.02) as an *early warning* only — the 8-K exhibit is untagged prose and, for Oracle's annual filing, the XBRL facts do not exist until the 10-K arrives up to 12 days later.

Poll windows: daily from **Sep 7** (Oracle) and daily from **Oct 20 through Nov 5** (the other four). `companyfacts` is refreshed when the filing is indexed, typically the same day.
