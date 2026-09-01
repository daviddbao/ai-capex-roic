"""Produce a REVIEW PACKET for one company-quarter.

A packet is a proposal, never a commitment. It carries:

* every proposed field value and the automation tier it came from;
* for every sourced number, a **verbatim quoted snippet plus its source URL**,
  mirroring the cell-note convention already used in the workbook
  (``<TICKER> <bucket> - <metric>`` / ``Value:`` / ``Public source:`` /
  ``Evidence:`` / ``Local source:`` / ``Classification:``);
* every guard result, including the passes -- a reviewer needs to see what was
  checked, not only what broke;
* an explicit list of the fields a human must supply, with where to look;
* a content hash over the proposed values, which is what an approval binds to.

Output is written as Markdown (for a human) and JSON (for :mod:`pipeline.apply`),
plus a blank ``*.approval.json`` for the reviewer to fill in and sign.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import REPO_ROOT
from .archive import archive_extraction
from .dataio import existing_row, source_id_for
from .edgar import EdgarClient, FetchError
from .extract import TICKERS, ExtractedField, extract_company, load_source_map
from .guards import FAIL, GuardOutcome, NEEDS_HUMAN, run_guards

__all__ = [
    "PACKETS_DIR",
    "PACKET_SCHEMA_VERSION",
    "build_packet",
    "packet_content_hash",
    "render_markdown",
    "write_packet",
    "approval_template",
]

PACKETS_DIR: Path = REPO_ROOT / "pipeline" / "packets"
PACKET_SCHEMA_VERSION = "1.0"

#: The model consumes these three per company. Two of the five annual
#: denominators are not per-quarter facts but are re-confirmed each refresh.
_FIELD_TITLES = {
    "demand_fact": "Demand fact (RPO / backlog / revenue)",
    "capex_fact": "Quarterly capex",
    "annual_denominator": "Annual capex denominator",
}


def packet_content_hash(packet: Mapping[str, Any]) -> str:
    """SHA-256 over the PROPOSED VALUES only.

    An approval records this hash, so a signature binds to specific numbers.
    Re-drafting with a different value invalidates the signature; re-drafting
    with the same values keeps it valid, which is what makes the flow idempotent.
    """
    payload = {
        "schema": PACKET_SCHEMA_VERSION,
        "ticker": packet["ticker"],
        "report_bucket": packet["report_bucket"],
        "period_end": packet["period"]["period_end"],
        "values": {
            name: {
                "status": f["status"],
                "value_usd": f["value_usd"],
                "concepts": f["concepts"],
                "derivation": f["derivation"],
            }
            for name, f in sorted(packet["fields"].items())
        },
        "blocking_guards": sorted(packet["guards_summary"]["blocking_ids"]),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _cell_note(
    ticker: str,
    model_period_key: str,
    metric: str,
    field: ExtractedField,
    local_path: str = "",
    classification: str = "SEC filing",
) -> str:
    """A note in the workbook's own convention, for the reviewer to paste."""
    lines = [f"{ticker} {model_period_key} — {metric}"]
    if field.value_usd is not None:
        lines.append(f"Value: ${field.value_usd_b:,.3f}B")
    else:
        lines.append("Value: NOT SUPPLIED — human input required")
    lines.append(f"Public source: {field.source_url or field.human_source_url}")
    evidence = field.evidence_quote or field.derivation or field.human_instruction
    lines.append(f"Evidence: {evidence}")
    if local_path:
        lines.append(f"Local source: {local_path}")
    lines.append(f"Classification: {classification}")
    return "\n".join(lines)


def build_packet(
    ticker: str,
    report_bucket: str,
    client: EdgarClient | None = None,
    source_map: Mapping[str, Any] | None = None,
    archive: bool = True,
    facts_csv: Any = None,
) -> dict[str, Any]:
    """Extract, guard, archive and assemble one company-quarter packet."""
    source_map = source_map or load_source_map()
    client = client or EdgarClient()
    extraction = extract_company(ticker, report_bucket, client=client, source_map=source_map)
    outcome: GuardOutcome = run_guards(
        extraction, client=client, source_map=source_map, facts_csv=facts_csv
    )

    archived: list[dict[str, Any]] = []
    archive_errors: list[str] = []
    if archive:
        try:
            archived = [a.to_dict() for a in archive_extraction(extraction, client=client)]
        except FetchError as exc:
            archive_errors.append(str(exc))

    local_by_url = {a["url"]: a["repo_relative_path"] for a in archived}
    period = extraction.period

    fields_payload: dict[str, Any] = {}
    manual_required: list[dict[str, Any]] = []
    for name, f in extraction.fields.items():
        payload = f.to_dict()
        payload["title"] = _FIELD_TITLES.get(name, name)
        payload["local_path_if_any"] = local_by_url.get(f.source_url, "")
        payload["cell_note"] = _cell_note(
            ticker,
            period.model_period_key,
            f.label,
            f,
            local_path=payload["local_path_if_any"],
            classification=(
                "SEC filing"
                if f.access != "not_in_xbrl"
                else "Official company disclosure (not in SEC XBRL)"
            ),
        )
        fields_payload[name] = payload
        if f.status == "refused_manual":
            manual_required.append(
                {
                    "field": name,
                    "title": payload["title"],
                    "label": f.label,
                    "why": f.human_instruction,
                    "where_to_look": f.human_source_url,
                    "value_on_file_last_refresh": f.model_q2_2026,
                    "xbrl_proxy_for_sanity_only": f.proxy_only,
                    "supply_as": f"approval.manual_values.{name}_usd_b",
                }
            )

    guards_summary = {
        "total": len(outcome.results),
        "pass": sum(1 for r in outcome.results if r.status == "PASS"),
        "fail": len(outcome.failures),
        "needs_human": len(outcome.needs_human),
        "info": sum(1 for r in outcome.results if r.status == "INFO"),
        "blocking_ids": sorted({r.id for r in outcome.results if r.blocking}),
    }

    from .dataio import FACTS_CSV

    try:
        already = existing_row(ticker, period.model_period_key, facts_csv or FACTS_CSV)
    except FileNotFoundError:
        already = None

    packet: dict[str, Any] = {
        "schema_version": PACKET_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ticker": ticker,
        "company": extraction.company_name,
        "cik": extraction.cik,
        "report_bucket": report_bucket,
        "model_period_key": period.model_period_key,
        "period": period.to_dict(),
        "periodic_filing": extraction.periodic_filing,
        "earnings_8k": extraction.earnings_8k,
        "exhibit_991_url": extraction.exhibit_991_url,
        "archived_sources": archived,
        "archive_errors": archive_errors,
        "fetch_errors": extraction.fetch_errors,
        "fields": fields_payload,
        "manual_required": manual_required,
        "guards": outcome.to_list(),
        "guards_summary": guards_summary,
        "already_on_file": already,
        "proposed_source_ids": {
            "fact": source_id_for(ticker, period.model_period_key, "FACT"),
            "capex": source_id_for(ticker, period.model_period_key, "CAPEX"),
        },
        "approval": {
            "status": "DRAFT — UNAPPROVED",
            "note": (
                "This packet is a PROPOSAL. Nothing is written to data/ until a reviewer fills in "
                "and saves the companion *.approval.json file. There is no CLI flag that approves "
                "a packet."
            ),
        },
    }
    packet["packet_sha256"] = packet_content_hash(packet)
    return packet


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _fmt_usd_b(value: float | None) -> str:
    return "—" if value is None else f"${value:,.3f}B"


def render_markdown(packet: Mapping[str, Any]) -> str:
    """Human-readable review packet."""
    p = packet
    period = p["period"]
    out: list[str] = []
    a = out.append

    a(f"# Review packet — {p['company']} ({p['ticker']}) — {p['report_bucket']}")
    a("")
    a(f"**Status: {p['approval']['status']}.** Nothing has been written to `data/`.")
    a("")
    a(f"- Generated: `{p['generated_at']}`")
    a(f"- Packet content hash: `{p['packet_sha256']}`")
    a(f"- Model period key: `{p['model_period_key']}` · issuer fiscal period: `{period['fiscal_period']}`")
    a(f"- Period end: `{period['period_end']}` (calendar quarter end `{period['calendar_quarter_end']}`)")
    a(f"- Quarter start: `{period['quarter_start']}` · fiscal year start: `{period['fiscal_year_start']}`")
    if p["periodic_filing"]:
        f = p["periodic_filing"]
        a(f"- Filing: **{f['form']}** `{f['accession']}` filed `{f['filing_date']}` — <{f['primary_doc_url']}>")
    else:
        a("- Filing: **NOT FOUND for this period end.**")
    if p["earnings_8k"]:
        a(f"- Earnings 8-K: `{p['earnings_8k']['accession']}` filed `{p['earnings_8k']['filing_date']}`"
          + (f" — Exhibit 99.1 <{p['exhibit_991_url']}>" if p["exhibit_991_url"] else ""))
    if p["already_on_file"]:
        a(f"- ⚠ A row for `{p['ticker']} {p['model_period_key']}` is **already in `data/facts.csv`**. "
          "Applying this packet will be a no-op unless the values differ, in which case it is refused.")
    a("")

    g = p["guards_summary"]
    a(f"**Guards: {g['pass']} pass · {g['fail']} FAIL · {g['needs_human']} need a human · {g['info']} info.**")
    a("")

    # --- proposed values -------------------------------------------------
    a("## 1. Proposed values")
    a("")
    a("| Field | Proposed | Tier | Access | Source |")
    a("|---|---|---|---|---|")
    for name, f in p["fields"].items():
        if f["status"] == "extracted":
            value = _fmt_usd_b(f["value_usd_b"])
        elif f["status"] == "refused_manual":
            value = "**REFUSED — human required**"
        else:
            value = "**ERROR**"
        source = f["source_url"] or f["human_source_url"]
        a(f"| {f['title']} | {value} | `{f['automation_tier']}` | `{f['access']}` | "
          f"{'<' + source + '>' if source else '—'} |")
    a("")

    # --- evidence --------------------------------------------------------
    a("## 2. Evidence")
    a("")
    for name, f in p["fields"].items():
        a(f"### {f['title']} — {f['label']}")
        a("")
        a(f"- Tier: `{f['automation_tier']}` · access: `{f['access']}` · status: `{f['status']}`")
        if f["status"] == "extracted":
            a(f"- Proposed value: **{_fmt_usd_b(f['value_usd_b'])}** ({f['value_usd']:,.0f} USD)")
            a(f"- Concepts: {', '.join('`' + c + '`' for c in f['concepts']) or '—'}")
            a(f"- Derivation: {f['derivation']}")
            if f["context"]:
                ctx = f["context"]
                a(f"- XBRL context: `{ctx['id']}` · instant `{ctx.get('instant')}` · "
                  f"explicit dimensions `{ctx.get('explicit_dimensions')}` · "
                  f"typed dimensions `{ctx.get('typed_dimensions')}`")
            if f["evidence_quote"]:
                a("")
                a(f"  > {f['evidence_quote']}")
                a("")
                a(f"  — <{f['evidence_quote_source_url']}>")
            else:
                a("- Verbatim quote: **none located** (see notes).")
            arithmetic = [c for c in f["components"] if "role" in c]
            if arithmetic:
                a("")
                a("  Components:")
                a("")
                a("  | role | concept | period | value | source |")
                a("  |---|---|---|---|---|")
                for c in arithmetic:
                    a(f"  | {c.get('role','')} | `{c.get('concept','')}` | "
                      f"{c.get('start','')} → {c.get('end','')} | {float(c.get('val',0)):,.0f} | "
                      f"{c.get('form','')} {c.get('accn','')} |")
                for c in arithmetic:
                    if c.get("evidence_quote"):
                        a("")
                        a(f"  > {c['evidence_quote']}")
                        a("")
                        a(f"  — <{c.get('evidence_quote_source_url','')}>")
        elif f["status"] == "refused_manual":
            a("- Proposed value: **none. The pipeline refuses to guess this field.**")
            a(f"- {f['human_instruction']}")
            if f.get("proxy_only") and f["proxy_only"].get("value_usd") is not None:
                proxy = f["proxy_only"]
                a(f"- XBRL proxy (SANITY CHECK ONLY, **not** a value): "
                  f"{_fmt_usd_b(proxy['value_usd']/1e9)} — {proxy['derivation']}")
                a(f"  - {proxy['status']}")
        else:
            a(f"- **ERROR:** {f['error']}")
        if f["local_path_if_any"]:
            a(f"- Local snapshot: `{f['local_path_if_any']}`")
        for note in f["notes"]:
            a(f"- Note: {note}")
        a("")
        a("<details><summary>Cell note (workbook convention)</summary>")
        a("")
        a("```")
        a(f["cell_note"])
        a("```")
        a("")
        a("</details>")
        a("")

    # --- guards ----------------------------------------------------------
    a("## 3. Guard results")
    a("")
    a("| Status | Id | Check | Detail |")
    a("|---|---|---|---|")
    order = {FAIL: 0, NEEDS_HUMAN: 1, "INFO": 2, "PASS": 3}
    for r in sorted(p["guards"], key=lambda r: (order.get(r["status"], 9), r["id"])):
        detail = r["message"].replace("|", "\\|").replace("\n", " ")
        if len(detail) > 400:
            detail = detail[:397] + "..."
        a(f"| `{r['status']}` | {r['id']} | {r['name']} | {detail} |")
    a("")

    # --- human to-do -----------------------------------------------------
    a("## 4. What a human must supply")
    a("")
    if not p["manual_required"]:
        a("No manual fields for this company this quarter.")
    for item in p["manual_required"]:
        a(f"### {item['title']} — {item['label']}")
        a("")
        a(f"- {item['why']}")
        if item["where_to_look"]:
            a(f"- Where to look: <{item['where_to_look']}>")
        if item["value_on_file_last_refresh"] is not None:
            a(f"- Value carried at the last refresh: {_fmt_usd_b(item['value_on_file_last_refresh']/1e9)}")
        proxy = item.get("xbrl_proxy_for_sanity_only") or {}
        if proxy.get("value_usd") is not None:
            a(f"- XBRL proxy for sanity only: {_fmt_usd_b(proxy['value_usd']/1e9)} "
              f"(`{proxy['derivation']}`). **Not a substitute.**")
        a(f"- Record it as `{item['supply_as']}` in the approval file.")
        a("")

    a("## 5. How to approve")
    a("")
    a("1. Read every `FAIL` and `NEEDS_HUMAN` row in §3 and resolve it.")
    a("2. Open the companion `*.approval.json`.")
    a("3. Fill in `reviewer`, `reviewed_at`, every entry under `manual_values`, and one "
      "`acknowledgements[<guard id>]` sentence for each blocking guard.")
    a(f"4. Copy this packet's content hash into `packet_sha256`: `{p['packet_sha256']}`")
    a("5. Set `decision` to `APPROVED`.")
    a("6. Run `python -m pipeline.apply <packet>.json`.")
    a("")
    a("A `FAIL` cannot be acknowledged away — fix the underlying problem and re-draft. "
      "Changing any proposed value changes the content hash and invalidates the signature.")
    a("")
    return "\n".join(out)


def approval_template(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Blank approval form for a reviewer to fill in and save."""
    blocking = [r for r in packet["guards"] if r["status"] in (FAIL, NEEDS_HUMAN)]
    return {
        "_instructions": [
            "This file IS the approval. There is no --approve flag.",
            "Fill in reviewer, reviewed_at, every manual_values entry, and one sentence for",
            "every guard id under acknowledgements. Then paste the packet's content hash into",
            "packet_sha256 and set decision to APPROVED.",
            "A FAIL guard cannot be acknowledged: fix it and re-draft the packet.",
        ],
        "packet_file": f"{packet['ticker']}.json",
        "ticker": packet["ticker"],
        "report_bucket": packet["report_bucket"],
        "decision": "PENDING",
        "reviewer": "",
        "reviewed_at": "",
        "packet_sha256": "",
        "packet_sha256_expected_hint": packet["packet_sha256"],
        "manual_values": {
            item["field"] + "_usd_b": None for item in packet["manual_required"]
        },
        "manual_value_sources": {
            item["field"] + "_source_url": item["where_to_look"] for item in packet["manual_required"]
        },
        "manual_value_evidence": {
            item["field"] + "_quote": "" for item in packet["manual_required"]
        },
        "acknowledgements": {r["id"]: "" for r in blocking},
        "acknowledgement_prompts": {
            r["id"]: f"[{r['status']}] {r['name']} — {r['message'][:300]}" for r in blocking
        },
    }


def write_packet(
    packet: Mapping[str, Any],
    packets_dir: Path | str = PACKETS_DIR,
) -> dict[str, Path]:
    """Write ``<bucket>/<TICKER>.{md,json}`` plus a blank approval form.

    An existing approval file is never overwritten -- re-drafting must not
    silently discard a reviewer's work, nor silently keep a signature that no
    longer matches the values.
    """
    folder = Path(packets_dir) / packet["report_bucket"]
    folder.mkdir(parents=True, exist_ok=True)
    json_path = folder / f"{packet['ticker']}.json"
    md_path = folder / f"{packet['ticker']}.md"
    approval_path = folder / f"{packet['ticker']}.approval.json"

    json_path.write_text(json.dumps(packet, indent=2, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(packet), encoding="utf-8")
    if not approval_path.exists():
        approval_path.write_text(
            json.dumps(approval_template(packet), indent=2), encoding="utf-8"
        )
    return {"json": json_path, "markdown": md_path, "approval": approval_path}


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - operator convenience
    """``python -m pipeline.draft CY2026Q3 [TICKER ...] [--no-archive]``."""
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in argv if not a.startswith("--")]
    archive = "--no-archive" not in argv
    bucket = args[0] if args else "CY2026Q3"
    tickers = args[1:] or list(TICKERS)
    source_map = load_source_map()
    client = EdgarClient()
    for ticker in tickers:
        packet = build_packet(
            ticker, bucket, client=client, source_map=source_map, archive=archive
        )
        paths = write_packet(packet)
        g = packet["guards_summary"]
        print(
            f"{ticker} {bucket}: {g['pass']} pass / {g['fail']} FAIL / {g['needs_human']} need a "
            f"human · {len(packet['manual_required'])} manual field(s) · hash {packet['packet_sha256'][:12]}"
        )
        print(f"    {paths['markdown']}")
        print(f"    {paths['approval']}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main(sys.argv[1:]))
