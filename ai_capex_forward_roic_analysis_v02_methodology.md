# AI Capex / Forward ROIC Analysis v02 - Q2 2026 Roll-Forward

## What changed

`ai_capex_forward_roic_analysis_v02.xlsx` extends the filing-based trajectory through calendar Q2 2026 for Microsoft, Alphabet, Amazon, Oracle, and Meta. It retains Q2 2025, producing a five-quarter view and a genuine Q2-to-Q2 spread comparison rather than deleting the original base quarter.

Reported financial inputs and current capex denominators were refreshed. The original AI-attribution, duration, capex-share, NOPAT-margin, and Damodaran WACC assumptions were held constant so movements remain comparable with v01. Each sourced input is hyperlinked and has a cell note with the public URL, reported value, definition, derivation, and local filing path.

## Q2 2026 filing inputs

| Company | Latest public fact | Quarterly capex used | Latest annual denominator |
|---|---:|---:|---:|
| MSFT | $678.0B commercial RPO | $41.0B management capex | $175.0B CY2026 reported outlook |
| GOOG | $519.5B revenue backlog | $44.924B cash PP&E | $200.0B midpoint of $195B-$205B range |
| AMZN | $496.0B long-term commitments | $54.208B gross cash PP&E | $200.0B latest unchanged company plan |
| ORCL | $638.0B RPO | $16.493B cash capex | $55.663B FY2026 reported actual |
| META | $60.801B quarterly revenue | $31.078B including lease principal | $137.5B midpoint of $130B-$145B range |

Oracle did not disclose a comparable numeric FY2027 gross-capex guide in its filed June results release. Its [official Q4 slides](https://s23.q4cdn.com/440135859/files/doc_financials/2026/q4/Q4-FY26-Oracle-Earnings-Slides.pdf) guide to approximately $70B of FY2027 **net cash outlay for capex**, which deducts capex financing and customer prepayments and is not interchangeable with GAAP gross cash capex. The snapshot therefore uses the latest completed FY2026 gross-capex actual rather than carrying forward the expired $50B FY2026 outlook.

## Q2 model outputs under unchanged assumptions

| Company | Q2 trajectory forward ROIC | Q2 trajectory spread | Sequential spread change | Q2 2025-to-Q2 2026 change | Latest-denominator base spread |
|---|---:|---:|---:|---:|---:|
| MSFT | 29.2% | 19.8 ppt | -5.5 ppt | +235 bps | 18.0 ppt |
| GOOG | 28.2% | 17.5 ppt | -3.8 ppt | +1,644 bps | 14.7 ppt |
| AMZN | 11.7% | 4.5 ppt | +1.2 ppt | +397 bps | 5.5 ppt |
| ORCL | 32.9% | 25.1 ppt | +7.7 ppt | +1,998 bps | 31.1 ppt |
| META | 13.9% | 3.3 ppt | -6.3 ppt | -595 bps | 1.9 ppt |

The displayed outputs are percentage-point spreads. Only the Q2-to-Q2 change is expressed in basis points.

## Decision-relevant interpretation

- Microsoft's Q2 run-rate spread fell as quarterly capex rose to $41B. Its snapshot spread increased because the reported annual capex outlook fell to about $175B. Management explicitly attributed that reduction to datacenter useful-life and lease-classification changes, not lower underlying investment. The snapshot improvement is therefore partly mechanical.
- Alphabet's backlog reached $519.5B, but quarterly capex also rose to $44.924B and the full-year range increased to $195B-$205B. The Q2 run-rate spread fell sequentially even though it remains substantially above Q2 2025.
- Amazon's commitments rose to $496B and quarterly gross cash PP&E reached $54.208B. Its disclosed weighted-average contract life rose to 6.4 years. Retaining the model's four-year assumption materially accelerates the revenue proxy and overstates returns relative to a 6.4-year straight-line heuristic.
- Oracle's RPO rose to $638B while Q4 cash capex moderated to $16.493B. Oracle also disclosed that $75B of prepaid or customer-supplied hardware within large AI contracts reduces its own capital requirement. The modeled spread therefore improved sharply, but the five-year RPO duration and 85% AI attribution remain assumptions.
- Meta's revenue rose to $60.801B, but company-defined quarterly capex increased to $31.078B. The run-rate spread fell below Q2 2025, while the guide-based base case remains modestly above WACC and the bear case remains below WACC.

## Comparability and assumption controls

- **Microsoft duration:** disclosed weighted-average commercial-RPO duration including OpenAI was 2.3 years; the model retains 2.5 years for consistency.
- **Amazon duration:** disclosed weighted-average remaining contract life was 6.4 years; the model retains 4.0 years for consistency. This is the largest identifiable duration sensitivity.
- **Alphabet backlog:** the Q1 2026 definition expansion remains in effect, and Q2 Cloud backlog now includes TPU system-sale agreements. Q1-to-Q2 is comparable, but 2025 figures are on the older definition.
- **Capex definitions:** Microsoft uses management capex including finance-lease commencement effects; Alphabet and Oracle use cash PP&E/capex; Amazon uses gross productive-asset cash payments; Meta includes finance-lease principal.
- **Annual denominators:** Alphabet and Meta use explicitly labeled range midpoints; Oracle uses actual FY2026 gross capex because its FY2027 outlook is a non-comparable net-cash-outlay measure; Amazon retains the latest filed company plan because Q2 contained no replacement numeric figure.
- **WACC:** the January 2026 Damodaran sector averages are unchanged. They are analyst-selected industry benchmarks, not company-specific WACCs.

## Primary Q2 sources

- Microsoft: [FY2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/789019/000119312526323660/msft-20260630.htm) and [official FY2026 Q4 earnings call](https://www.microsoft.com/en-us/investor/events/fy-2026/earnings-fy-2026-q4)
- Alphabet: [Q2 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1652044/000165204426000071/goog-20260630.htm), [official earnings release](https://s206.q4cdn.com/479360582/files/doc_financials/2026/q2/2026q2-alphabet-earnings-release.pdf), and [official earnings call](https://abc.xyz/investor/events/event-details/2026/2026-Q2-Earnings-Call-2026-GgTAq7Is0z/default.aspx)
- Amazon: [Q2 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000026/amzn-20260630.htm) and [SEC-filed earnings release](https://www.sec.gov/Archives/edgar/data/1018724/000101872426000024/amzn-20260630xex991.htm)
- Oracle: [FY2026 Form 10-K](https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/orcl-20260531.htm), [SEC-filed FY2026 results release](https://www.sec.gov/Archives/edgar/data/1341439/000119312526265848/orcl-ex99_1.htm), and [official Q4 earnings slides](https://s23.q4cdn.com/440135859/files/doc_financials/2026/q4/Q4-FY26-Oracle-Earnings-Slides.pdf)
- Meta: [Q2 2026 Form 10-Q](https://www.sec.gov/Archives/edgar/data/1326801/000162828026050705/meta-20260630.htm) and [SEC-filed earnings release](https://www.sec.gov/Archives/edgar/data/1326801/000162828026050596/meta-06302026xexhibit991.htm)
- WACC: [Damodaran industry cost-of-capital table](https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/wacc.html)

Local copies of the five primary Q2 filings, the Oracle/Meta filed releases, and Oracle's Q4 earnings slides are preserved under `01_sources/company_filings/`.

## Validation

- OOXML ZIP integrity, expected sheet order, and absence of external workbook links passed.
- 519 formulas, 455 URL-bearing comments, and 240 clickable hyperlinks were counted.
- 135 independent numerical checks passed across all five quarters, the snapshot scenarios, and the Q2-to-Q2 changes.
- Independently evaluated formula caches were stored for data-only audit readers.
- Both presentation sheets were rendered and visually inspected for values, labels, units, clipping, conditional formatting, and source-note indicators.
- The workbook is a standard macro-free `.xlsx`. The managed Office environment still does not support a reliable hidden Excel automation save/reopen test, so no such claim is made.
