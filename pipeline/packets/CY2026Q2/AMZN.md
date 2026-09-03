# Review packet — Amazon.com, Inc. (AMZN) — CY2026Q2

**Status: DRAFT — UNAPPROVED.** Nothing has been written to `data/`.

- Generated: `2026-09-01T00:07:03+00:00`
- Packet content hash: `6673a5888c6e5cfa28c47a1aeb9945f6c1aae24f7f239e48f6c79cd765dedb09`
- Model period key: `Q2 26` · issuer fiscal period: `Q2 2026`
- Period end: `2026-06-30` (calendar quarter end `2026-06-30`)
- Quarter start: `2026-04-01` · fiscal year start: `2026-01-01`
- Filing: **10-Q** `0001018724-26-000026` filed `2026-07-31` — <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm>
- Earnings 8-K: `0001018724-26-000024` filed `2026-07-30` — Exhibit 99.1 <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm>
- ⚠ A row for `AMZN Q2 26` is **already in `data/facts.csv`**. Applying this packet will be a no-op unless the values differ, in which case it is refused.

**Guards: 18 pass · 0 FAIL · 1 need a human · 1 info.**

## 1. Proposed values

| Field | Proposed | Tier | Access | Source |
|---|---|---|---|---|
| Demand fact (RPO / backlog / revenue) | $496.000B | `auto` | `inline_xbrl_dimensional` | <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm> |
| Quarterly capex | $54.208B | `auto` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm> |
| Annual capex denominator | **REFUSED — human required** | `manual` | `not_in_xbrl` | <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm> |

## 2. Evidence

### Demand fact (RPO / backlog / revenue) — Long-term customer commitments not yet recognized (AWS-linked RPO)

- Tier: `auto` · access: `inline_xbrl_dimensional` · status: `extracted`
- Proposed value: **$496.000B** (496,000,000,000 USD)
- Concepts: `us-gaap:RevenueRemainingPerformanceObligation`
- Derivation: inline-XBRL us-gaap:RevenueRemainingPerformanceObligation @ instant 2026-06-30 with dimensional context [us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis present], excluding contexts carrying srt:MajorCustomersAxis
- XBRL context: `c-46` · instant `2026-06-30` · explicit dimensions `{}` · typed dimensions `{'us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionStartDateAxis': '2026-07-01'}`

  > For contracts with original terms that exceed one year, those commitments not yet recognized were approximately $ 496 billion as of June 30, 2026.

  — <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm>
- Local snapshot: `01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm`
- Note: 2 fact(s) tagged us-gaap:RevenueRemainingPerformanceObligation in the primary document; 1 match the required dimensional context.
- Note: precision_note: Tagged rounded to whole billions and prefixed 'approximately'.
- Note: corroborating_prose: 10-Q: 'For contracts with original terms that exceed one year, those commitments not yet recognized were approximately $496 billion as of June 30, 2026. The weighted-average remaining life of our long-term contracts is 6.4 years.'

<details><summary>Cell note (workbook convention)</summary>

```
AMZN Q2 26 — Long-term customer commitments not yet recognized (AWS-linked RPO)
Value: $496.000B
Public source: https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm
Evidence: For contracts with original terms that exceed one year, those commitments not yet recognized were approximately $ 496 billion as of June 30, 2026.
Local source: 01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm
Classification: SEC filing
```

</details>

### Quarterly capex — GROSS cash purchases of property and equipment / productive assets

- Tier: `auto` · access: `companyfacts` · status: `extracted`
- Proposed value: **$54.208B** (54,208,000,000 USD)
- Concepts: `us-gaap:PaymentsToAcquireProductiveAssets`
- Derivation: companyfacts us-gaap:PaymentsToAcquireProductiveAssets for the standalone duration 2026-04-01 -> 2026-06-30

  > 74 2,641 (749) Net cash provided by (used in) operating activities 32,515 45,387 49,530 71,419 121,137 161,403 INVESTING ACTIVITIES: Purchases of property and equipment (32,183) (54,208) (57,202) (98,411) (107,656) (173,028) Proceeds from property and equipment sales and incentives 815 1,132 1,579 2,101 4,703 4,021 Acquisitions, net of cash acquired, non-marketab

  — <https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm>
- Local snapshot: `01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
AMZN Q2 26 — GROSS cash purchases of property and equipment / productive assets
Value: $54.208B
Public source: https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm
Evidence: 74 2,641 (749) Net cash provided by (used in) operating activities 32,515 45,387 49,530 71,419 121,137 161,403 INVESTING ACTIVITIES: Purchases of property and equipment (32,183) (54,208) (57,202) (98,411) (107,656) (173,028) Proceeds from property and equipment sales and incentives 815 1,132 1,579 2,101 4,703 4,021 Acquisitions, net of cash acquired, non-marketab
Local source: 01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm
Classification: SEC filing
```

</details>

### Annual capex denominator — FY2026 capital investment plan

- Tier: `manual` · access: `not_in_xbrl` · status: `refused_manual`
- Proposed value: **none. The pipeline refuses to guess this field.**
- HUMAN REQUIRED -- FY2026 capital investment plan. NOT MACHINE-READABLE - company plan stated on the earnings call. Verified absent from the 8-K Exhibit 99.1 press release, which contains no capital-expenditure outlook at all. Primary source: https://ir.aboutamazon.com/events/ Note: The methodology retains the latest filed company plan because Q2 2026 contained no replacement numeric figure. Beware: Amazon's Q2 2026 NET SALES were $200.6B - numerically near-identical to the $200B capex plan. Do not let a regex confuse them.
- Local snapshot: `01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
AMZN Q2 26 — FY2026 capital investment plan
Value: NOT SUPPLIED — human input required
Public source: https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm
Evidence: HUMAN REQUIRED -- FY2026 capital investment plan. NOT MACHINE-READABLE - company plan stated on the earnings call. Verified absent from the 8-K Exhibit 99.1 press release, which contains no capital-expenditure outlook at all. Primary source: https://ir.aboutamazon.com/events/ Note: The methodology retains the latest filed company plan because Q2 2026 contained no replacement numeric figure. Beware: Amazon's Q2 2026 NET SALES were $200.6B - numerically near-identical to the $200B capex plan. Do not let a regex confuse them.
Local source: 01_sources/company_filings/Amazon.com_Inc/0001018724-26-000026/amzn-20260630.htm
Classification: Official company disclosure (not in SEC XBRL)
```

</details>

## 3. Guard results

| Status | Id | Check | Detail |
|---|---|---|---|
| `NEEDS_HUMAN` | S5 | Manual field correctly refused: annual_denominator | HUMAN REQUIRED -- FY2026 capital investment plan. NOT MACHINE-READABLE - company plan stated on the earnings call. Verified absent from the 8-K Exhibit 99.1 press release, which contains no capital-expenditure outlook at all. Primary source: https://ir.aboutamazon.com/events/ Note: The methodology retains the latest filed company plan because Q2 2026 contained no replacement numeric figure. Bew... |
| `INFO` | T11 | Amazon's capex plan is not confusable with its net sales in this packet | Quarterly net sales were 200.6$B |
| `PASS` | R1 | demand_fact sequential move is within the plausible band | Q1 26 364.000$B -> Q2 26 496.000$B (+36.3%) |
| `PASS` | R2 | capex_fact sequential move is within the plausible band | Q1 26 44.203$B -> Q2 26 54.208$B (+22.6%) |
| `PASS` | S1 | Resolved period matches source_map.report_bucket_map | period_end 2026-06-30, Q2 2026, form 10-Q. |
| `PASS` | S2 | Periodic filing present | 10-Q 0001018724-26-000026 filed 2026-07-31 for reportDate 2026-06-30. |
| `PASS` | S3 | Filing form matches the fiscal quarter | fiscal Q2 -> 10-Q. |
| `PASS` | S4 | Extraction succeeded: demand_fact | 496.000 $B via auto/inline_xbrl_dimensional. |
| `PASS` | S4 | Extraction succeeded: capex_fact | 54.208 $B via auto/companyfacts. |
| `PASS` | S6 | No fetch errors | All sources retrieved. |
| `PASS` | T10 | Amazon RPO selected by AXIS PRESENCE, not by a hardcoded typed-member date | context c-46 @ 2026-06-30; typed member reads '2026-07-01' (the day after period end -- it advances every quarter, so it is matched on axis presence only). Value 496.0$B. |
| `PASS` | T10 | Customer-specific sibling commitments correctly excluded | Excluded 38$B with {'srt:MajorCustomersAxis': 'amzn:OpenAIGroupPBCMember'} |
| `PASS` | T10 | companyfacts confirmed empty for Amazon RPO at this instant | As documented: companyfacts returns nothing for Amazon RPO at 2026-06-30. The value came from the filing's inline XBRL. A companyfacts-only fetcher would have silently skipped this company. |
| `PASS` | T13 | Period end coincides with the calendar quarter end, as expected | 2026-06-30. |
| `PASS` | T15 | demand_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 496.000$B; tolerance for this fact is +/-500.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: For contracts with original terms that exceed one year, those commitments not yet recognized were approximately $ 496 billion as of June 30... |
| `PASS` | T15 | capex_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 54.208$B; tolerance for this fact is +/-0.5M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: 74 2,641 (749) Net cash provided by (used in) operating activities 32,515 45,387 49,530 71,419 121,137 161,403 INVESTING ACTIVITIES: Purchases... |
| `PASS` | T6 | Amazon capex uses us-gaap:PaymentsToAcquireProductiveAssets | The cash-flow-statement 'Purchases of property and equipment' line, as the model requires. |
| `PASS` | T6 | Amazon capex is GROSS, not the MD&A's net 'cash capital expenditures' | gross 54.208$B as re-read from the filing's cash-flow statement; the net measure the MD&A quotes would be 53.076$B after deducting 1,132M of proceeds from property and equipment sales and incentives. The model uses gross. |
| `PASS` | T8 | Directly-tagged capex duration is a standalone quarter | 2026-04-01 -> 2026-06-30 = 90 days. |
| `PASS` | T9 | Demand fact is distinct from purchase/contractual obligations | demand fact 496.0$B; obligation-side facts in the same filing: ContractualObligation 650.0$B, UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary 11.7$B, UnrecordedUnconditionalPurchaseObligationBalanceOnFirstAnniversary 33.0$B |

## 4. What a human must supply

### Annual capex denominator — FY2026 capital investment plan

- HUMAN REQUIRED -- FY2026 capital investment plan. NOT MACHINE-READABLE - company plan stated on the earnings call. Verified absent from the 8-K Exhibit 99.1 press release, which contains no capital-expenditure outlook at all. Primary source: https://ir.aboutamazon.com/events/ Note: The methodology retains the latest filed company plan because Q2 2026 contained no replacement numeric figure. Beware: Amazon's Q2 2026 NET SALES were $200.6B - numerically near-identical to the $200B capex plan. Do not let a regex confuse them.
- Where to look: <https://ir.aboutamazon.com/events/>
- Value carried at the last refresh: $200.000B
- Record it as `approval.manual_values.annual_denominator_usd_b` in the approval file.

## 5. How to approve

1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.
2. Open the companion `*.approval.json`.
3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one `acknowledgements[<guard id>]` sentence for each blocking guard.
4. Copy this packet's content hash into `packet_sha256`: `6673a5888c6e5cfa28c47a1aeb9945f6c1aae24f7f239e48f6c79cd765dedb09`
5. Set `decision` to `APPROVED`.
6. Run `python -m pipeline.apply <packet>.json`.

A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. Changing any proposed value changes the content hash and invalidates the signature.
