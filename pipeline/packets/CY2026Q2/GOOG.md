# Review packet — Alphabet Inc. (GOOG) — CY2026Q2

**Status: DRAFT — UNAPPROVED.** Nothing has been written to `data/`.

- Generated: `2026-09-01T00:07:02+00:00`
- Packet content hash: `de362e7e4d1b67207805b3289cf1a6ccb503b54e8ad51a0e36efeed840bceed1`
- Model period key: `Q2 26` · issuer fiscal period: `Q2 2026`
- Period end: `2026-06-30` (calendar quarter end `2026-06-30`)
- Quarter start: `2026-04-01` · fiscal year start: `2026-01-01`
- Filing: **10-Q** `0001652044-26-000071` filed `2026-07-23` — <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>
- Earnings 8-K: `0001652044-26-000066` filed `2026-07-22` — Exhibit 99.1 <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000066/googexhibit991q22026.htm>
- ⚠ A row for `GOOG Q2 26` is **already in `data/facts.csv`**. Applying this packet will be a no-op unless the values differ, in which case it is refused.

**Guards: 13 pass · 0 FAIL · 1 need a human · 1 info.**

## 1. Proposed values

| Field | Proposed | Tier | Access | Source |
|---|---|---|---|---|
| Demand fact (RPO / backlog / revenue) | $519.500B | `auto` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm> |
| Quarterly capex | $44.924B | `derived` | `companyfacts` | <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm> |
| Annual capex denominator | **REFUSED — human required** | `manual` | `not_in_xbrl` | <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm> |

## 2. Evidence

### Demand fact (RPO / backlog / revenue) — Revenue backlog (total remaining performance obligations)

- Tier: `auto` · access: `companyfacts` · status: `extracted`
- Proposed value: **$519.500B** (519,500,000,000 USD)
- Concepts: `us-gaap:RevenueRemainingPerformanceObligation`
- Derivation: companyfacts us-gaap:RevenueRemainingPerformanceObligation @ instant 2026-06-30 (undimensioned)

  > Revenue Backlog As of June 30, 2026, we had $ 519.5 billion of remaining performance obligations ("revenue backlog"), of which $ 513.9 billion related to Google Cloud.

  — <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>
- Local snapshot: `01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm`
- Note: precision_note: Tagged to one decimal place in billions.
- Note: definition_break: In Q1 2026 Alphabet elected to include contracts with an original expected term of one year or less. 2025 and earlier figures are on the OLD definition. See docs/SOURCE_MAP.md 'Definitional traps'.
- Note: corroborating_prose: 10-Q: 'As of June 30, 2026, we had $519.5 billion of remaining performance obligations ("revenue backlog"), of which $513.9 billion related to Google Cloud.'

<details><summary>Cell note (workbook convention)</summary>

```
GOOG Q2 26 — Revenue backlog (total remaining performance obligations)
Value: $519.500B
Public source: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm
Evidence: Revenue Backlog As of June 30, 2026, we had $ 519.5 billion of remaining performance obligations ("revenue backlog"), of which $ 513.9 billion related to Google Cloud.
Local source: 01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm
Classification: SEC filing
```

</details>

### Quarterly capex — Cash purchases of property and equipment

- Tier: `derived` · access: `companyfacts` · status: `extracted`
- Proposed value: **$44.924B** (44,924,000,000 USD)
- Concepts: `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`
- Derivation: YTD differencing against 2026-01-01 -> 2026-03-31. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 80,598,000,000 - 35,674,000,000 = 44,924,000,000

  > • Capital expenditures, which primarily reflected investments in technical infrastructure, were $44.9 billion for the three months ended June 30, 2026.

  — <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>

  Components:

  | role | concept | period | value | source |
  |---|---|---|---|---|
  | YTD current | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2026-01-01 → 2026-06-30 | 80,598,000,000 | 10-Q 0001652044-26-000071 |
  | YTD prior | `us-gaap:PaymentsToAcquirePropertyPlantAndEquipment` | 2026-01-01 → 2026-03-31 | 35,674,000,000 | 10-Q 0001652044-26-000048 |

  > During the six months ended June 30, 2025 and 2026, we spent $39.6 billion and $80.6 billion on capital expenditures, respectively.

  — <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm>

  > Quarter Ended TTM Q3 2025 Q4 2025 Q1 2026 Q2 2026 Q2 2026 Net cash provided by operating activities $ 48,414 $ 52,402 $ 45,790 $ 39,069 $ 185,675 Less: purchases of property and equipment (23,953) (27,851) (35,674) (44,924) (132,402) Free cash flow $ 24,461 $ 24,551 $ 10,116 $ (5,855) $ 53,273 Free cash flow: We define free cash flow as net cash provided by operating activities less capital expenditures.

  — <https://www.sec.gov/Archives/edgar/data/1652044/000165204426000066/googexhibit991q22026.htm>
- Local snapshot: `01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
GOOG Q2 26 — Cash purchases of property and equipment
Value: $44.924B
Public source: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm
Evidence: • Capital expenditures, which primarily reflected investments in technical infrastructure, were $44.9 billion for the three months ended June 30, 2026.
Local source: 01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm
Classification: SEC filing
```

</details>

### Annual capex denominator — FY2026 capital expenditure outlook range midpoint

- Tier: `manual` · access: `not_in_xbrl` · status: `refused_manual`
- Proposed value: **none. The pipeline refuses to guess this field.**
- HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE - given on the earnings call. Verified absent from both the 10-Q and the 8-K Exhibit 99.1 press release (the strings '195' and '205' as guidance do not appear). Primary source: https://abc.xyz/investor/events/ Note: Raised from $180-190B at Q1 2026. The model uses the midpoint.
- Local snapshot: `01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
GOOG Q2 26 — FY2026 capital expenditure outlook range midpoint
Value: NOT SUPPLIED — human input required
Public source: https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm
Evidence: HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE - given on the earnings call. Verified absent from both the 10-Q and the 8-K Exhibit 99.1 press release (the strings '195' and '205' as guidance do not appear). Primary source: https://abc.xyz/investor/events/ Note: Raised from $180-190B at Q1 2026. The model uses the midpoint.
Local source: 01_sources/company_filings/Alphabet_Inc/0001652044-26-000071/goog-20260630.htm
Classification: Official company disclosure (not in SEC XBRL)
```

</details>

## 3. Guard results

| Status | Id | Check | Detail |
|---|---|---|---|
| `NEEDS_HUMAN` | S5 | Manual field correctly refused: annual_denominator | HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE - given on the earnings call. Verified absent from both the 10-Q and the 8-K Exhibit 99.1 press release (the strings '195' and '205' as guidance do not appear). Primary source: https://abc.xyz/investor/events/ Note: Raised from $180-190B at Q1 2026. The model uses the midpoint. |
| `INFO` | T5 | Alphabet's expanded backlog definition is still in force | Detected the Q1 2026 definition-change language, so this quarter is on the NEW basis (contracts with an original expected term of one year or less are included). Q1 26 onward are comparable with each other; any comparison spanning Q4 25 -> Q1 26 is not. Carry definition_version = '2026-expanded' on the row. |
| `PASS` | R1 | demand_fact sequential move is within the plausible band | Q1 26 467.600$B -> Q2 26 519.500$B (+11.1%) |
| `PASS` | R2 | capex_fact sequential move is within the plausible band | Q1 26 35.674$B -> Q2 26 44.924$B (+25.9%) |
| `PASS` | S1 | Resolved period matches source_map.report_bucket_map | period_end 2026-06-30, Q2 2026, form 10-Q. |
| `PASS` | S2 | Periodic filing present | 10-Q 0001652044-26-000071 filed 2026-07-23 for reportDate 2026-06-30. |
| `PASS` | S3 | Filing form matches the fiscal quarter | fiscal Q2 -> 10-Q. |
| `PASS` | S4 | Extraction succeeded: demand_fact | 519.500 $B via auto/companyfacts. |
| `PASS` | S4 | Extraction succeeded: capex_fact | 44.924 $B via derived/companyfacts. |
| `PASS` | S6 | No fetch errors | All sources retrieved. |
| `PASS` | T13 | Period end coincides with the calendar quarter end, as expected | 2026-06-30. |
| `PASS` | T15 | demand_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 519.500$B; tolerance for this fact is +/-50.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: Revenue Backlog As of June 30, 2026, we had $ 519.5 billion of remaining performance obligations ("revenue backlog"), of which $ 513.9 billi... |
| `PASS` | T15 | capex_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 44.924$B; tolerance for this fact is +/-50.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: • Capital expenditures, which primarily reflected investments in technical infrastructure, were $44.9 billion for the three months ended June... |
| `PASS` | T8 | Quarter correctly derived by year-to-date differencing | YTD differencing against 2026-01-01 -> 2026-03-31. us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 80,598,000,000 - 35,674,000,000 = 44,924,000,000 |
| `PASS` | T9 | Demand fact is distinct from purchase/contractual obligations | demand fact 519.5$B; obligation-side facts in the same filing: none tagged |

## 4. What a human must supply

### Annual capex denominator — FY2026 capital expenditure outlook range midpoint

- HUMAN REQUIRED -- FY2026 capital expenditure outlook range midpoint. NOT MACHINE-READABLE - given on the earnings call. Verified absent from both the 10-Q and the 8-K Exhibit 99.1 press release (the strings '195' and '205' as guidance do not appear). Primary source: https://abc.xyz/investor/events/ Note: Raised from $180-190B at Q1 2026. The model uses the midpoint.
- Where to look: <https://abc.xyz/investor/events/>
- Value carried at the last refresh: $200.000B
- Record it as `approval.manual_values.annual_denominator_usd_b` in the approval file.

## 5. How to approve

1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.
2. Open the companion `*.approval.json`.
3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one `acknowledgements[<guard id>]` sentence for each blocking guard.
4. Copy this packet's content hash into `packet_sha256`: `de362e7e4d1b67207805b3289cf1a6ccb503b54e8ad51a0e36efeed840bceed1`
5. Set `decision` to `APPROVED`.
6. Run `python -m pipeline.apply <packet>.json`.

A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. Changing any proposed value changes the content hash and invalidates the signature.
