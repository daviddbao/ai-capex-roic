# Review packet — Microsoft Corporation (MSFT) — CY2026Q2

**Status: DRAFT — UNAPPROVED.** Nothing has been written to `data/`.

- Generated: `2026-09-01T00:07:01+00:00`
- Packet content hash: `a50de5bb1f670500da1574d7c476fe8d649d5ad2e97426e5be9e72153cc0b260`
- Model period key: `Q2 26` · issuer fiscal period: `FY26 Q4`
- Period end: `2026-06-30` (calendar quarter end `2026-06-30`)
- Quarter start: `2026-04-01` · fiscal year start: `2025-07-01`
- Filing: **10-K** `0001193125-26-323660` filed `2026-07-29` — <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm>
- Earnings 8-K: `0001193125-26-323632` filed `2026-07-29` — Exhibit 99.1 <https://www.sec.gov/Archives/edgar/data/789019/000119312526323632/msft-ex99_1.htm>
- ⚠ A row for `MSFT Q2 26` is **already in `data/facts.csv`**. Applying this packet will be a no-op unless the values differ, in which case it is refused.

**Guards: 12 pass · 0 FAIL · 3 need a human · 0 info.**

## 1. Proposed values

| Field | Proposed | Tier | Access | Source |
|---|---|---|---|---|
| Demand fact (RPO / backlog / revenue) | $678.000B | `auto` | `inline_xbrl_dimensional` | <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm> |
| Quarterly capex | **REFUSED — human required** | `manual` | `not_in_xbrl` | <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm> |
| Annual capex denominator | **REFUSED — human required** | `manual` | `not_in_xbrl` | <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm> |

## 2. Evidence

### Demand fact (RPO / backlog / revenue) — Commercial remaining performance obligation

- Tier: `auto` · access: `inline_xbrl_dimensional` · status: `extracted`
- Proposed value: **$678.000B** (678,000,000,000 USD)
- Concepts: `us-gaap:RevenueRemainingPerformanceObligation`
- Derivation: inline-XBRL us-gaap:RevenueRemainingPerformanceObligation @ instant 2026-06-30 with dimensional context [srt:MajorCustomersAxis=msft:CommercialCustomersMember]
- XBRL context: `C_1afb830c-dfb8-425d-9873-198df856bdce` · instant `2026-06-30` · explicit dimensions `{'srt:MajorCustomersAxis': 'msft:CommercialCustomersMember'}` · typed dimensions `{}`

  > • Commercial remaining performance obligation increased 84% to $678 billion.

  — <https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm>
- Local snapshot: `01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm`
- Note: 2 fact(s) tagged us-gaap:RevenueRemainingPerformanceObligation in the primary document; 1 match the required dimensional context.
- Note: precision_note: Microsoft tags this rounded to whole billions (3 significant figures). Do not expect million-level precision.
- Note: corroborating_prose: 10-K MD&A: 'Commercial remaining performance obligation increased 84% to $678 billion.' Same sentence appears in the 8-K Exhibit 99.1 press release.

<details><summary>Cell note (workbook convention)</summary>

```
MSFT Q2 26 — Commercial remaining performance obligation
Value: $678.000B
Public source: https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm
Evidence: • Commercial remaining performance obligation increased 84% to $678 billion.
Local source: 01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm
Classification: SEC filing
```

</details>

### Quarterly capex — Company-reported capital expenditures INCLUDING finance leases (management metric)

- Tier: `manual` · access: `not_in_xbrl` · status: `refused_manual`
- Proposed value: **none. The pipeline refuses to guess this field.**
- HUMAN REQUIRED -- Company-reported capital expenditures INCLUDING finance leases (management metric). NOT MACHINE-READABLE - sourced from the FY2026 Q4 earnings call / webcast / CFO commentary. Exhaustively searched: the FY2026 10-K (1,565 inline-XBRL facts) contains no such figure and the phrase 'capital expenditures including finance leases' does not appear; the 8-K Exhibit 99.1 press release contains no capex line beyond the GAAP cash-flow 'Additions to property and equipment'. What to read: CFO prepared remarks - the sentence of form 'capital expenditures including finance leases were $X billion' Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4 Secondary source: https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast
- XBRL proxy (SANITY CHECK ONLY, **not** a value): $40.924B — us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 115,948,000,000 - 80,146,000,000 = 35,802,000,000 + us-gaap:RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability: 24,608,000,000 - 19,486,000,000 = 5,122,000,000
  - APPROXIMATION, NOT AN IDENTITY. Microsoft has never published a reconciliation between its management capex metric and these two GAAP tags. Microsoft's IR event page states the $41B comprises ~$35.8B cash plus a finance-lease component; one secondary source puts that component at $5.6B, which does not sum to $41.0B given a $35.8B cash base. The composition is therefore UNVERIFIED and the proxy must not be trusted to the reported figure's precision.
- Local snapshot: `01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
MSFT Q2 26 — Company-reported capital expenditures INCLUDING finance leases (management metric)
Value: NOT SUPPLIED — human input required
Public source: https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm
Evidence: HUMAN REQUIRED -- Company-reported capital expenditures INCLUDING finance leases (management metric). NOT MACHINE-READABLE - sourced from the FY2026 Q4 earnings call / webcast / CFO commentary. Exhaustively searched: the FY2026 10-K (1,565 inline-XBRL facts) contains no such figure and the phrase 'capital expenditures including finance leases' does not appear; the 8-K Exhibit 99.1 press release contains no capex line beyond the GAAP cash-flow 'Additions to property and equipment'. What to read: CFO prepared remarks - the sentence of form 'capital expenditures including finance leases were $X billion' Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4 Secondary source: https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast
Local source: 01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm
Classification: Official company disclosure (not in SEC XBRL)
```

</details>

### Annual capex denominator — CY2026 capital expenditure outlook

- Tier: `manual` · access: `not_in_xbrl` · status: `refused_manual`
- Proposed value: **none. The pipeline refuses to guess this field.**
- HUMAN REQUIRED -- CY2026 capital expenditure outlook. NOT MACHINE-READABLE - forward-looking outlook given verbally on the earnings call. Verified absent from both the 10-K and the 8-K Exhibit 99.1 press release. Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4
- Local snapshot: `01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm`

<details><summary>Cell note (workbook convention)</summary>

```
MSFT Q2 26 — CY2026 capital expenditure outlook
Value: NOT SUPPLIED — human input required
Public source: https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm
Evidence: HUMAN REQUIRED -- CY2026 capital expenditure outlook. NOT MACHINE-READABLE - forward-looking outlook given verbally on the earnings call. Verified absent from both the 10-K and the 8-K Exhibit 99.1 press release. Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4
Local source: 01_sources/company_filings/Microsoft_Corporation/0001193125-26-323660/msft-20260630.htm
Classification: Official company disclosure (not in SEC XBRL)
```

</details>

## 3. Guard results

| Status | Id | Check | Detail |
|---|---|---|---|
| `NEEDS_HUMAN` | S5 | Manual field correctly refused: capex_fact | HUMAN REQUIRED -- Company-reported capital expenditures INCLUDING finance leases (management metric). NOT MACHINE-READABLE - sourced from the FY2026 Q4 earnings call / webcast / CFO commentary. Exhaustively searched: the FY2026 10-K (1,565 inline-XBRL facts) contains no such figure and the phrase 'capital expenditures including finance leases' does not appear; the 8-K Exhibit 99.1 press release... |
| `NEEDS_HUMAN` | S5 | Manual field correctly refused: annual_denominator | HUMAN REQUIRED -- CY2026 capital expenditure outlook. NOT MACHINE-READABLE - forward-looking outlook given verbally on the earnings call. Verified absent from both the 10-K and the 8-K Exhibit 99.1 press release. Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4 |
| `NEEDS_HUMAN` | T3 | Microsoft's capex outlook movement can be an accounting effect, not an investment cut | Microsoft extended estimated useful lives for datacenters and office buildings (15 -> 25 years), which shifts future datacenter leases from FINANCE leases (counted in the management capex metric) to OPERATING leases (excluded). The CY2026 outlook fell ~$190B -> ~$175B for that reason while capex including finance leases rose ~70% YoY. Any period-over-period comparison of this denominator across... |
| `PASS` | R1 | demand_fact sequential move is within the plausible band | Q1 26 627.000$B -> Q2 26 678.000$B (+8.1%) |
| `PASS` | S1 | Resolved period matches source_map.report_bucket_map | period_end 2026-06-30, FY26 Q4, form 10-K. |
| `PASS` | S2 | Periodic filing present | 10-K 0001193125-26-323660 filed 2026-07-29 for reportDate 2026-06-30. |
| `PASS` | S3 | Filing form matches the fiscal quarter | fiscal Q4 -> 10-K. |
| `PASS` | S4 | Extraction succeeded: demand_fact | 678.000 $B via auto/inline_xbrl_dimensional. |
| `PASS` | S6 | No fetch errors | All sources retrieved. |
| `PASS` | T12 | Microsoft's XBRL proxy uses finance-lease ROU ADDITIONS (and is a proxy only) | proxy concepts: ['us-gaap:PaymentsToAcquirePropertyPlantAndEquipment', 'us-gaap:RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability']. The headline figure remains manual: Microsoft has never published a reconciliation between the management metric and these GAAP tags. |
| `PASS` | T13 | Period end coincides with the calendar quarter end, as expected | 2026-06-30. |
| `PASS` | T15 | demand_fact: value corroborated by a verbatim disclosure, within its own precision | XBRL value 678.000$B; tolerance for this fact is +/-500.0M because filers tag demand facts to whole billions and cash-flow items to the million. Rounding is not error, and a rounded press-release figure never overrides a more precise XBRL derivation. Quote: • Commercial remaining performance obligation increased 84% to $678 billion. |
| `PASS` | T4 | Microsoft RPO carries srt:MajorCustomersAxis = msft:CommercialCustomersMember | context C_1afb830c-dfb8-425d-9873-198df856bdce @ 2026-06-30 with {'srt:MajorCustomersAxis': 'msft:CommercialCustomersMember'}; value 678.0$B. |
| `PASS` | T4 | Commercial RPO is distinct from total RPO, as expected | commercial 678.0$B vs companyfacts total 684.0$B (delta 6.0$B). A companyfacts-only fetcher would have taken the total. |
| `PASS` | T9 | Demand fact is distinct from purchase/contractual obligations | demand fact 678.0$B; obligation-side facts in the same filing: none tagged |

## 4. What a human must supply

### Quarterly capex — Company-reported capital expenditures INCLUDING finance leases (management metric)

- HUMAN REQUIRED -- Company-reported capital expenditures INCLUDING finance leases (management metric). NOT MACHINE-READABLE - sourced from the FY2026 Q4 earnings call / webcast / CFO commentary. Exhaustively searched: the FY2026 10-K (1,565 inline-XBRL facts) contains no such figure and the phrase 'capital expenditures including finance leases' does not appear; the 8-K Exhibit 99.1 press release contains no capex line beyond the GAAP cash-flow 'Additions to property and equipment'. What to read: CFO prepared remarks - the sentence of form 'capital expenditures including finance leases were $X billion' Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4 Secondary source: https://www.microsoft.com/en-us/investor/earnings/fy-2026-q4/press-release-webcast
- Where to look: <https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4>
- Value carried at the last refresh: $41.000B
- XBRL proxy for sanity only: $40.924B (`us-gaap:PaymentsToAcquirePropertyPlantAndEquipment: 115,948,000,000 - 80,146,000,000 = 35,802,000,000 + us-gaap:RightOfUseAssetObtainedInExchangeForFinanceLeaseLiability: 24,608,000,000 - 19,486,000,000 = 5,122,000,000`). **Not a substitute.**
- Record it as `approval.manual_values.capex_fact_usd_b` in the approval file.

### Annual capex denominator — CY2026 capital expenditure outlook

- HUMAN REQUIRED -- CY2026 capital expenditure outlook. NOT MACHINE-READABLE - forward-looking outlook given verbally on the earnings call. Verified absent from both the 10-K and the 8-K Exhibit 99.1 press release. Primary source: https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4
- Where to look: <https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4>
- Value carried at the last refresh: $175.000B
- Record it as `approval.manual_values.annual_denominator_usd_b` in the approval file.

## 5. How to approve

1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.
2. Open the companion `*.approval.json`.
3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one `acknowledgements[<guard id>]` sentence for each blocking guard.
4. Copy this packet's content hash into `packet_sha256`: `a50de5bb1f670500da1574d7c476fe8d649d5ad2e97426e5be9e72153cc0b260`
5. Set `decision` to `APPROVED`.
6. Run `python -m pipeline.apply <packet>.json`.

A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. Changing any proposed value changes the content hash and invalidates the signature.
