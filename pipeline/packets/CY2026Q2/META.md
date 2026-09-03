# Review packet — Meta Platforms, Inc. (META) — CY2026Q2

**Status: DRAFT — UNAPPROVED.** Nothing has been written to `data/`.

- Generated: `2026-09-01T00:07:07+00:00`
- Packet content hash: `7dc269a6fc3a31b45724e5287d7ede9cc7edb32854dbc0df9fe6197ef61d69ef`
- Model period key: `Q2 26` · issuer fiscal period: `Q2 2026`
- Period end: `2026-06-30` (calendar quarter end `2026-06-30`)
- Quarter start: `2026-04-01` · fiscal year start: `2026-01-01`
- Filing: **10-Q** `0001628280-26-050705` filed `2026-07-30` — <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm>
- Earnings 8-K: `0001628280-26-050596` filed `2026-07-29` — Exhibit 99.1 <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm>
- ⚠ A row for `META Q2 26` is **already in `data/facts.csv`**. Applying this packet will be a no-op unless the values differ, in which case it is refused.

**Guards: 13 pass · 0 FAIL · 3 need a human · 0 info.**

## 1. Proposed values

| Field | Proposed | Tier | Access | Source |
|---|---|---|---|---|
| Demand fact (RPO / backlog / revenue) | $60.801B | `auto` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm> |
| Quarterly capex | $31.078B | `derived` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm> |
| Annual capex denominator | **REFUSED — human required** | `manual` | `not_in_xbrl` | <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm> |

## 2. Evidence

### Demand fact (RPO / backlog / revenue) — Quarterly revenue

- Tier: `auto` · access: `companyfacts` · status: `extracted`
- Proposed value: **$60.801B** (60,801,000,000 USD)
- Concepts: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`
- Derivation: companyfacts us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax for the standalone duration 2026-04-01 -> 2026-06-30

  > Total revenue for the second quarter of 2026 was $60.80 billion, an increase of 28% compared to the second quarter of 2025, due to an increase in advertising revenue.

  — <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm>
- Local snapshot: `01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
META Q2 26 — Quarterly revenue
Value: $60.801B
Public source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm
Evidence: Total revenue for the second quarter of 2026 was $60.80 billion, an increase of 28% compared to the second quarter of 2025, due to an increase in advertising revenue.
Local source: 01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm
Classification: SEC filing
```

</details>

### Quarterly capex — Capital expenditures INCLUDING principal payments on finance leases

- Tier: `derived` · access: `companyfacts` · status: `extracted`
- Proposed value: **$31.078B** (31,078,000,000 USD)
- Concepts: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`, `us-gaap:FinanceLeasePrincipalPayments`
- Derivation: YTD differencing against 2026-01-01 -> 2026-03-31. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 49,113,000,000 - 18,997,000,000 = 30,116,000,000; us-gaap:FinanceLeasePrincipalPayments: 1,805,000,000 - 843,000,000 = 962,000,000

  > • Capital expenditures – Capital expenditures, including principal payments on finance leases, were $31.08 billion.

  — <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm>

  Components:

  | role | concept | period | value | source |
  |---|---|---|---|---|
  | YTD current | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2026-01-01 → 2026-06-30 | 49,113,000,000 | 10-Q 0001628280-26-050705 |
  | YTD prior | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2026-01-01 → 2026-03-31 | 18,997,000,000 | 10-Q 0001628280-26-028526 |
  | YTD current | `us-gaap:FinanceLeasePrincipalPayments` | 2026-01-01 → 2026-06-30 | 1,805,000,000 | 10-Q 0001628280-26-050705 |
  | YTD prior | `us-gaap:FinanceLeasePrincipalPayments` | 2026-01-01 → 2026-03-31 | 843,000,000 | 10-Q 0001628280-26-028526 |

  > Cash Used in Investing Activities Cash used in investing activities during the six months ended June 30, 2026 mostly consisted of $49.11 billion of purchases of property and equipment as we continued to invest in servers, data centers, and network infrastructure, and $31.56 billion of net purchases of marketable securities.

  — <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm>

  > operating activities $ 31,862 $ 25,561 $ 64,088 $ 49,587 Purchases of property and equipment (30,116) (16,538) (49,113) (29,479) Principal payments on finance leases (962) (474) (1,805) (1,225) Free cash flow $ 784 $ 8,549 $ 13,170 $ 18,883 9

  — <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm>
- Local snapshot: `01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
META Q2 26 — Capital expenditures INCLUDING principal payments on finance leases
Value: $31.078B
Public source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm
Evidence: • Capital expenditures – Capital expenditures, including principal payments on finance leases, were $31.08 billion.
Local source: 01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm
Classification: SEC filing
```

</details>

### Annual capex denominator — FY2026 capital expenditure outlook range midpoint

- Tier: `manual` · access: `not_in_xbrl` · status: `refused_manual`
- Proposed value: **none. The pipeline refuses to guess this field.**
- HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE AS XBRL, but it IS present as prose in the SEC-filed 8-K Exhibit 99.1 (unlike MSFT/GOOG/AMZN, whose outlooks are call-only). It is untagged text, so extraction is regex-fragile. Where: 8-K Exhibit 99.1, CFO Outlook section: 'We anticipate 2026 capital expenditures, including principal payments on finance leases, to be in the range of $130-145 billion, narrowed from our prior outlook of $125-145 billion.' Primary source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm WATCH OUT: The SAME SENTENCE contains the PRIOR outlook ($125-145 billion). A naive 'first range after the phrase capital expenditures' regex is only correct by luck of word order; a 'last range in the sentence' regex would grab the superseded figure.
- Local snapshot: `01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
META Q2 26 — FY2026 capital expenditure outlook range midpoint
Value: NOT SUPPLIED — human input required
Public source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm
Evidence: HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE AS XBRL, but it IS present as prose in the SEC-filed 8-K Exhibit 99.1 (unlike MSFT/GOOG/AMZN, whose outlooks are call-only). It is untagged text, so extraction is regex-fragile. Where: 8-K Exhibit 99.1, CFO Outlook section: 'We anticipate 2026 capital expenditures, including principal payments on finance leases, to be in the range of $130-145 billion, narrowed from our prior outlook of $125-145 billion.' Primary source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm WATCH OUT: The SAME SENTENCE contains the PRIOR outlook ($125-145 billion). A naive 'first range after the phrase capital expenditures' regex is only correct by luck of word order; a 'last range in the sentence' regex would grab the superseded figure.
Local source: 01_sources/company_filings/Meta_Platforms_Inc/0001628280-26-050705/meta-20260630.htm
Classification: Official company disclosure (not in SEC XBRL)
```

</details>

## 3. Guard results

| Status | Id | Check | Detail |
|---|---|---|---|
| `NEEDS_HUMAN` | R2 | capex_fact moved more than 35% sequentially | Q1 26 19.840$B -> Q2 26 31.078$B (+56.6%). A move this large is possible in this cohort but must be confirmed explicitly rather than passed through -- check for a definition change, a period-selection error, or a one-off. |
| `NEEDS_HUMAN` | S5 | Manual field correctly refused: annual_denominator | HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE AS XBRL, but it IS present as prose in the SEC-filed 8-K Exhibit 99.1 (unlike MSFT/GOOG/AMZN, whose outlooks are call-only). It is untagged text, so extraction is regex-fragile. Where: 8-K Exhibit 99.1, CFO Outlook section: 'We anticipate 2026 capital expenditures, including principal payments on finance l... |
| `NEEDS_HUMAN` | T7 | Meta's capex guidance sentence contains BOTH the current and the superseded range | Two ranges appear in one sentence: $130-145B, $125-145B. The CURRENT outlook is the one before 'narrowed from our prior outlook of'. A 'last match in sentence' regex would take the superseded figure; 'first match' is correct only by luck of word order. The same paragraph also carries a total-expenses range ($165-169B) that a looser regex would grab instead. A human must state the number. |
| `PASS` | R1 | demand_fact sequential move is within the plausible band | Q1 26 56.311$B -> Q2 26 60.801$B (+8.0%) |
| `PASS` | S1 | Resolved period matches source_map.report_bucket_map | period_end 2026-06-30, Q2 2026, form 10-Q. |
| `PASS` | S2 | Periodic filing present | 10-Q 0001628280-26-050705 filed 2026-07-30 for reportDate 2026-06-30. |
| `PASS` | S3 | Filing form matches the fiscal quarter | fiscal Q2 -> 10-Q. |
| `PASS` | S4 | Extraction succeeded: demand_fact | 60.801 $B via auto/companyfacts. |
| `PASS` | S4 | Extraction succeeded: capex_fact | 31.078 $B via derived/companyfacts. |
| `PASS` | S6 | No fetch errors | All sources retrieved. |
| `PASS` | T12 | Meta capex uses finance-lease PRINCIPAL PAYMENTS | us-gaap:FinanceLeasePrincipalPayments, as Meta defines the metric. This formula is NOT shared with Microsoft. |
| `PASS` | T13 | Period end coincides with the calendar quarter end, as expected | 2026-06-30. |
| `PASS` | T15 | demand_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 60.801$B; tolerance for this fact is +/-5.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: Total revenue for the second quarter of 2026 was $60.80 billion, an increase of 28% compared to the second quarter of 2025, due to an increase... |
| `PASS` | T15 | capex_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 31.078$B; tolerance for this fact is +/-5.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: • Capital expenditures – Capital expenditures, including principal payments on finance leases, were $31.08 billion. |
| `PASS` | T8 | Quarter correctly derived by year-to-date differencing | YTD differencing against 2026-01-01 -> 2026-03-31. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 49,113,000,000 - 18,997,000,000 = 30,116,000,000; us-gaap:FinanceLeasePrincipalPayments: 1,805,000,000 - 843,000,000 = 962,000,000 |
| `PASS` | T9 | Demand fact is distinct from purchase/contractual obligations | demand fact 60.8$B; obligation-side facts in the same filing: ContractualObligation 349.3$B |

## 4. What a human must supply

### Annual capex denominator — FY2026 capital expenditure outlook range midpoint

- HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE AS XBRL, but it IS present as prose in the SEC-filed 8-K Exhibit 99.1 (unlike MSFT/GOOG/AMZN, whose outlooks are call-only). It is untagged text, so extraction is regex-fragile. Where: 8-K Exhibit 99.1, CFO Outlook section: 'We anticipate 2026 capital expenditures, including principal payments on finance leases, to be in the range of $130-145 billion, narrowed from our prior outlook of $125-145 billion.' Primary source: https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm WATCH OUT: The SAME SENTENCE contains the PRIOR outlook ($125-145 billion). A naive 'first range after the phrase capital expenditures' regex is only correct by luck of word order; a 'last range in the sentence' regex would grab the superseded figure.
- Where to look: <https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm>
- Value carried at the last refresh: $137.500B
- Record it as `approval.manual_values.annual_denominator_usd_b` in the approval file.

## 5. How to approve

1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.
2. Open the companion `*.approval.json`.
3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one `acknowledgements[<guard id>]` sentence for each blocking guard.
4. Copy this packet's content hash into `packet_sha256`: `7dc269a6fc3a31b45724e5287d7ede9cc7edb32854dbc0df9fe6197ef61d69ef`
5. Set `decision` to `APPROVED`.
6. Run `python -m pipeline.apply <packet>.json`.

A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. Changing any proposed value changes the content hash and invalidates the signature.
