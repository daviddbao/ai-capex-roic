# Review packet — Oracle Corporation (ORCL) — CY2026Q2

**Status: DRAFT — UNAPPROVED.** Nothing has been written to `data/`.

- Generated: `2026-09-01T00:07:05+00:00`
- Packet content hash: `057e4e9e8442cd1153a67b1f20da326c4ca9edf6f4d397beb9befed45580f1ea`
- Model period key: `Q2 26` · issuer fiscal period: `FY26 Q4`
- Period end: `2026-05-31` (calendar quarter end `2026-06-30`)
- Quarter start: `2026-03-01` · fiscal year start: `2025-06-01`
- Filing: **10-K** `0001193125-26-277521` filed `2026-06-22` — <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm>
- Earnings 8-K: `0001193125-26-265848` filed `2026-06-10` — Exhibit 99.1 <https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm>
- ⚠ A row for `ORCL Q2 26` is **already in `data/facts.csv`**. Applying this packet will be a no-op unless the values differ, in which case it is refused.

**Guards: 15 pass · 0 FAIL · 1 need a human · 3 info.**

## 1. Proposed values

| Field | Proposed | Tier | Access | Source |
|---|---|---|---|---|
| Demand fact (RPO / backlog / revenue) | $638.000B | `auto` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm> |
| Quarterly capex | $16.493B | `derived` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm> |
| Annual capex denominator | $55.663B | `auto` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm> |

## 2. Evidence

### Demand fact (RPO / backlog / revenue) — Remaining performance obligations (RPO)

- Tier: `auto` · access: `companyfacts` · status: `extracted`
- Proposed value: **$638.000B** (638,000,000,000 USD)
- Concepts: `us-gaap:RevenueRemainingPerformanceObligation`
- Derivation: companyfacts us-gaap:RevenueRemainingPerformanceObligation @ instant 2026-05-31 (undimensioned)

  > Remaining Performance Obligations from Contracts with Customers Remaining performance obligations were $638 billion and $138 billion as of May 31, 2026 and 2025, respectively.

  — <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm>
- Local snapshot: `01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm`
- Note: precision_note: Tagged to whole billions.
- Note: corroborating_prose: 8-K Exhibit 99.1: 'Remaining Performance Obligations, or RPO, ended the quarter at $638 billion, up 363% USD year-over-year and up $85 billion sequentially from the end of Q3.'

<details><summary>Cell note (workbook convention)</summary>

```
ORCL Q2 26 — Remaining performance obligations (RPO)
Value: $638.000B
Public source: https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm
Evidence: Remaining Performance Obligations from Contracts with Customers Remaining performance obligations were $638 billion and $138 billion as of May 31, 2026 and 2025, respectively.
Local source: 01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm
Classification: SEC filing
```

</details>

### Quarterly capex — GAAP cash capital expenditures

- Tier: `derived` · access: `companyfacts` · status: `extracted`
- Proposed value: **$16.493B** (16,493,000,000 USD)
- Concepts: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`
- Derivation: YTD differencing against 2025-06-01 -> 2026-02-28. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 55,663,000,000 - 39,170,000,000 = 16,493,000,000
- Verbatim quote: **none located** (see notes).

  Components:

  | role | concept | period | value | source |
  |---|---|---|---|---|
  | YTD current | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2025-06-01 → 2026-05-31 | 55,663,000,000 | 10-K 0001193125-26-277521 |
  | YTD prior | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2025-06-01 → 2026-02-28 | 39,170,000,000 | 10-Q 0001193125-26-101045 |

  > and $1.3 billion of net cash proceeds from our employee stock programs, partially offset by $55.7 billion of cash used for capital expenditures;

  — <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm>
- Local snapshot: `01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm`
- Note: No single sentence states this derived figure -- by construction, the filer publishes only the year-to-date components. See the per-component quotes and the derivation arithmetic.

<details><summary>Cell note (workbook convention)</summary>

```
ORCL Q2 26 — GAAP cash capital expenditures
Value: $16.493B
Public source: https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm
Evidence: YTD differencing against 2025-06-01 -> 2026-02-28. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 55,663,000,000 - 39,170,000,000 = 16,493,000,000
Local source: 01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm
Classification: SEC filing
```

</details>

### Annual capex denominator — FY2026 actual gross cash capex

- Tier: `auto` · access: `companyfacts` · status: `extracted`
- Proposed value: **$55.663B** (55,663,000,000 USD)
- Concepts: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`
- Derivation: companyfacts us-gaap:PaymentsToAcquirePropertyPlantAndEquipment for the standalone duration 2025-06-01 -> 2026-05-31

  > and $1.3 billion of net cash proceeds from our employee stock programs, partially offset by $55.7 billion of cash used for capital expenditures;

  — <https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm>
- Local snapshot: `01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm`

<details><summary>Cell note (workbook convention)</summary>

```
ORCL Q2 26 — FY2026 actual gross cash capex
Value: $55.663B
Public source: https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm
Evidence: and $1.3 billion of net cash proceeds from our employee stock programs, partially offset by $55.7 billion of cash used for capital expenditures;
Local source: 01_sources/company_filings/Oracle_Corporation/0001193125-26-277521/orcl-20260531.htm
Classification: SEC filing
```

</details>

## 3. Guard results

| Status | Id | Check | Detail |
|---|---|---|---|
| `NEEDS_HUMAN` | T14 | Oracle's RPO includes prepaid / customer-supplied hardware | Oracle disclosed that most of its RPO increase came from large-scale AI contracts where the customer prepaid for the GPUs, or bought and supplied the GPUs to Oracle -- roughly $75B that reduces Oracle's own capital requirement. The RPO number is machine-readable; its comparability to Alphabet's or Microsoft's backlog is a judgement call that is not. Confirm whether the disclosure language chang... |
| `INFO` | T13 | Oracle period end is one month before the calendar quarter end | bucket CY2026Q2 (calendar quarter ending 2026-06-30) maps to Oracle's FY26 Q4 ending 2026-05-31. Every Oracle bucket carries a one-month timing mismatch against the other four that no automation removes. |
| `INFO` | T2 | Oracle's press-release capex table is TRAILING FOUR-QUARTERS, not quarterly | Detected heading: 'NET CASH OUTLAY FOR CAPITAL EXPENDITURES - TRAILING FOUR-QUARTERS (1) ($ in millions)'. Every column in that table is a TTM figure -- FY26 Q3 reads 48,250 while the 9-month XBRL year-to-date is 39,170. The quarter must come from XBRL YTD differencing and never from this table. |
| `INFO` | X1 | capex_fact: no quarterly cross-check column exists for this filer | Oracle publishes no quarterly capex column anywhere -- its press-release table is trailing-four-quarters (T2) and must not be read as a quarter. The absence of a corroborating figure is structural, not suspicious. The two year-to-date components are individually corroborated; the difference between them is arithmetic. Derivation: YTD differencing against 2025-06-01 -> 2026-02-28. us-gaap:Paymen... |
| `PASS` | R1 | demand_fact sequential move is within the plausible band | Q1 26 552.600$B -> Q2 26 638.000$B (+15.5%) |
| `PASS` | R2 | capex_fact sequential move is within the plausible band | Q1 26 18.635$B -> Q2 26 16.493$B (-11.5%) |
| `PASS` | S1 | Resolved period matches source_map.report_bucket_map | period_end 2026-05-31, FY26 Q4, form 10-K. |
| `PASS` | S2 | Periodic filing present | 10-K 0001193125-26-277521 filed 2026-06-22 for reportDate 2026-05-31. |
| `PASS` | S3 | Filing form matches the fiscal quarter | fiscal Q4 -> 10-K. |
| `PASS` | S4 | Extraction succeeded: demand_fact | 638.000 $B via auto/companyfacts. |
| `PASS` | S4 | Extraction succeeded: capex_fact | 16.493 $B via derived/companyfacts. |
| `PASS` | S4 | Extraction succeeded: annual_denominator | 55.663 $B via auto/companyfacts. |
| `PASS` | S6 | No fetch errors | All sources retrieved. |
| `PASS` | S7 | Annual denominator's pinned fiscal year is still the latest completed one | filed actual for the year ended 2026-05-31, 0 month(s) before this period end. |
| `PASS` | T1 | Oracle capex_fact is on the GROSS GAAP basis | 16.493$B from us-gaap:PaymentsToAcquirePropertyPlantAndEquipment; distinct from every figure on the 'Net Cash Outlay' and 'Less:' rows of the press release's non-GAAP table (net-outlay row values: 19,793M, 24,034M, 32,857M, 44,161M, 47,726M). |
| `PASS` | T1 | Oracle annual_denominator is on the GROSS GAAP basis | 55.663$B from us-gaap:PaymentsToAcquirePropertyPlantAndEquipment; distinct from every figure on the 'Net Cash Outlay' and 'Less:' rows of the press release's non-GAAP table (net-outlay row values: 19,793M, 24,034M, 32,857M, 44,161M, 47,726M). |
| `PASS` | T15 | demand_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 638.000$B; tolerance for this fact is +/-500.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: Remaining Performance Obligations from Contracts with Customers Remaining performance obligations were $638 billion and $138 billion as of ... |
| `PASS` | T8 | Quarter correctly derived by year-to-date differencing | YTD differencing against 2025-06-01 -> 2026-02-28. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 55,663,000,000 - 39,170,000,000 = 16,493,000,000 |
| `PASS` | T9 | Demand fact is distinct from purchase/contractual obligations | demand fact 638.0$B; obligation-side facts in the same filing: UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary 1.8$B |

## 4. What a human must supply

No manual fields for this company this quarter.
## 5. How to approve

1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.
2. Open the companion `*.approval.json`.
3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one `acknowledgements[<guard id>]` sentence for each blocking guard.
4. Copy this packet's content hash into `packet_sha256`: `057e4e9e8442cd1153a67b1f20da326c4ca9edf6f4d397beb9befed45580f1ea`
5. Set `decision` to `APPROVED`.
6. Run `python -m pipeline.apply <packet>.json`.

A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. Changing any proposed value changes the content hash and invalidates the signature.
