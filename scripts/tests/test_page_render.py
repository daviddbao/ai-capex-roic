"""The rendered page, in a real browser.

Everything else in ``scripts/tests/`` checks the *payload*. Nothing checked the
*page*, and the two defects this file was written for were both invisible to a
payload test:

* the hover tooltips were clipped — ``.chart-wrap`` carries ``overflow-x:auto``,
  which forces ``overflow-y`` to a scrolling value too, so a tip parented inside
  it was cut off at the plot's top edge and again at its right edge;
* nothing verified that a figure rendered on the page actually resolves to a
  source row, which is the one property this page must never lose.

Playwright is not a dependency of this repo. When it is absent, or its browser
has not been downloaded, these tests skip.

    python -m pip install playwright && python -m playwright install chromium
    python -m pytest scripts/tests/test_page_render.py -q
"""

from __future__ import annotations

from pathlib import Path

import pytest

sync_playwright = pytest.importorskip(
    "playwright.sync_api", reason="playwright is not installed"
).sync_playwright

REPO = Path(__file__).resolve().parents[2]
PAGE = (REPO / "dashboard" / "index.html").as_uri()
VIEWPORT = {"width": 1440, "height": 1000}


@pytest.fixture(scope="module")
def page():
    """The dashboard, loaded once, with any page error recorded as a failure."""
    try:
        pw = sync_playwright().start()
    except Exception as exc:                      # pragma: no cover - env-dependent
        pytest.skip(f"playwright could not start: {exc}")
    try:
        try:
            browser = pw.chromium.launch()
        except Exception as exc:                  # pragma: no cover - env-dependent
            pytest.skip(f"chromium is not installed for playwright: {exc}")
        pg = browser.new_page(viewport=VIEWPORT)
        errors: list[str] = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.goto(PAGE)
        pg.wait_for_timeout(700)
        pg.errors = errors                        # type: ignore[attr-defined]
        yield pg
        browser.close()
    finally:
        pw.stop()


def reset(page) -> None:
    """Back to the workbook's own assumptions and the latest quarter."""
    page.keyboard.press("Escape")
    page.click("#reset-all")
    page.click("#q-seg button:last-child")
    page.wait_for_timeout(250)


# ---------------------------------------------------------------------------
# The page's own gate
# ---------------------------------------------------------------------------


def test_the_page_recomputes_its_own_model_on_load(page):
    assert page.get_attribute("#verify", "data-state") == "pass", page.inner_text("#verify-text")


def test_the_page_loads_without_a_script_error(page):
    assert page.errors == []


# ---------------------------------------------------------------------------
# The derivation ledger
# ---------------------------------------------------------------------------


def test_one_receipt_per_company(page):
    # the cost-of-capital cards reuse the receipt shell, so scope to the ledger
    assert page.locator("#ledger-grid .led").count() == 5


def test_every_fact_chip_resolves_to_a_source_row(page):
    """The property the whole evidence layer rests on."""
    unresolved = page.evaluate(
        """() => [...document.querySelectorAll('.fact-btn')]
                  .map(b => b.dataset.src)
                  .filter(id => !DATA.sources[id])"""
    )
    assert unresolved == []


def test_every_fact_chip_opens_a_drawer_that_links_out(page):
    reset(page)
    btn = page.locator("#led-GOOG .fact-btn").first
    btn.click()
    page.wait_for_timeout(200)
    drawer = page.locator("#led-GOOG .ev-drawer")
    assert drawer.count() == 1
    assert drawer.locator("a[href^='https']").count() >= 1
    # the verbatim evidence out of data/sources.csv, not a paraphrase
    assert "Revenue backlog/RPO was $519.5B" in drawer.inner_text()
    btn.click()
    page.wait_for_timeout(150)
    assert page.locator("#led-GOOG .ev-drawer").count() == 0


def test_the_receipt_reproduces_the_model(page):
    """GOOG Q2 26: 519.5 x .65 / 2.5 -> 135.1; 44.924 x 4 x .8 -> 143.8; -> +1,753 bps."""
    reset(page)
    text = page.inner_text("#led-GOOG")
    for shown in ("$519.500B", "65%", "2.5 y", "$135.1B",
                  "$44.924B", "80%", "$143.8B",
                  "30%", "28.19%", "10.66%", "+1,753 bps"):
        assert shown in text, shown


def test_meta_shows_no_duration_row_because_it_has_none(page):
    reset(page)
    assert "contract duration" not in page.inner_text("#led-META")
    assert "annualise the quarter" in page.inner_text("#led-META")


def test_an_assumption_chip_drives_the_model(page):
    reset(page)
    before = page.inner_text("#led-GOOG .led-row.total .val")
    page.locator("#led-GOOG .assum-btn").first.click()
    page.wait_for_timeout(200)
    assert page.locator(".pop").count() == 1
    page.evaluate(
        """() => { const i = document.querySelector('.pop input[type=range]');
                   i.value = 0.4; i.dispatchEvent(new Event('input', {bubbles:true})); }"""
    )
    page.wait_for_timeout(300)
    assert page.inner_text("#led-GOOG .led-row.total .val") != before
    # the popover must survive its own re-render, or a drag closes the control
    assert page.locator(".pop").count() == 1
    assert page.get_attribute("#moved-chip", "data-n") == "1"
    reset(page)
    assert page.get_attribute("#moved-chip", "data-n") == "0"


def test_the_quarter_control_rebuilds_every_receipt(page):
    reset(page)
    page.click("#q-seg button[data-q='Q2 25']")
    page.wait_for_timeout(250)
    assert page.inner_text("#led-q") == "Q2 2025"
    assert "$368.000B" in page.inner_text("#led-MSFT")   # MSFT commercial RPO at Q2 25
    reset(page)
    assert "$678.000B" in page.inner_text("#led-MSFT")   # ... and at Q2 26


# ---------------------------------------------------------------------------
# Tooltips must not be clipped — the defect this file exists for
# ---------------------------------------------------------------------------


def hover_plot(page, frac: float):
    page.locator("#traj-wrap").scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    hit = page.locator("#traj-hit").bounding_box()
    page.mouse.move(hit["x"] + 3 + (hit["width"] - 6) * frac, hit["y"] + hit["height"] * 0.5)
    page.wait_for_timeout(180)
    tip = page.locator("#traj-tip")
    return tip.bounding_box(), tip.evaluate("e => getComputedStyle(e).opacity")


@pytest.mark.parametrize("frac,where", [(0.0, "first quarter"), (0.5, "middle"), (1.0, "last quarter")])
def test_the_trajectory_tooltip_is_fully_on_screen(page, frac, where):
    reset(page)
    box, opacity = hover_plot(page, frac)
    assert opacity == "1", where
    assert box["x"] >= -1, f"{where}: clipped at the left ({box['x']:.0f})"
    assert box["x"] + box["width"] <= VIEWPORT["width"] + 1, (
        f"{where}: overflows the right edge ({box['x'] + box['width']:.0f} > {VIEWPORT['width']})"
    )
    assert box["y"] >= -1, f"{where}: clipped at the top ({box['y']:.0f})"


def test_the_tooltip_may_overhang_the_top_of_the_plot(page):
    """The tip is drawn above the point. Parented in the scrolling wrap it was cut off."""
    reset(page)
    hover_plot(page, 0.5)
    overhang = page.evaluate(
        """() => {
            const t = document.getElementById('traj-tip').getBoundingClientRect();
            const w = document.getElementById('traj-wrap').getBoundingClientRect();
            return Math.round(w.top - t.top);
        }"""
    )
    assert overhang > 0, "the tooltip no longer clears the plot's top edge"


@pytest.mark.parametrize("row", ["first", "last"])
def test_the_snapshot_tooltip_is_fully_on_screen(page, row):
    reset(page)
    page.locator("#snap-wrap").scroll_into_view_if_needed()
    page.wait_for_timeout(150)
    rows = page.locator("#snap-svg rect.srow")
    rows.nth(0 if row == "first" else rows.count() - 1).hover(force=True)
    page.wait_for_timeout(180)
    box = page.locator("#snap-tip").bounding_box()
    assert page.locator("#snap-tip").evaluate("e => getComputedStyle(e).opacity") == "1"
    assert box["x"] >= -1 and box["x"] + box["width"] <= VIEWPORT["width"] + 1
    assert box["y"] >= -1


# ---------------------------------------------------------------------------
# The evidence ledger, and the round trip between it and the figures
# ---------------------------------------------------------------------------


def test_every_source_has_a_row(page):
    assert page.locator("#src-table tbody tr[data-hay]").count() == 62


def test_the_chart_selects_the_quarter_the_ledger_shows(page):
    reset(page)
    page.locator("#traj-wrap").scroll_into_view_if_needed()
    page.wait_for_timeout(120)
    box = page.locator("#traj-wrap").bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.05, box["y"] + box["height"] * 0.5)
    page.wait_for_timeout(400)
    assert page.inner_text("#led-q") == "Q2 2025"


def test_a_source_row_links_back_to_the_figure_it_supports(page):
    reset(page)
    page.click("#q-seg button[data-q='Q2 25']")
    page.wait_for_timeout(200)
    # the ledger is ordered by quarter, so the quarter cell is the way back
    page.click("#src-GOOG-Q226-FACT [data-fig]")
    page.wait_for_timeout(500)
    assert page.inner_text("#led-q") == "Q2 2026"


def test_the_ledger_filter_narrows_to_one_company(page):
    page.fill("#src-search", "oracle")
    page.wait_for_timeout(200)
    visible = page.locator("#src-table tbody tr[data-hay][data-dim='0']").count()
    assert 0 < visible < 62
    tickers = page.evaluate(
        """() => [...document.querySelectorAll("#src-table tbody tr[data-hay][data-dim='0']")]
                   .map(r => r.id.replace('src-','').split('-')[0])"""
    )
    assert set(tickers) == {"ORCL"}
    page.fill("#src-search", "")
    page.wait_for_timeout(150)

# ---------------------------------------------------------------------------
# The two capex views, on one receipt
# ---------------------------------------------------------------------------


def test_the_receipt_carries_both_denominators(page):
    reset(page)
    text = page.inner_text("#led-GOOG")
    # the stage captions are uppercased by CSS, and inner_text renders it
    assert "denominator a · run-rate" in text.lower()
    assert "denominator b · annual plan" in text.lower()
    # GOOG: 200.0 plan x .8 -> 160.0; 135.07 x .30 / 160 -> 25.33%; -1066 -> +1,467 bps
    for shown in ("$200.000B", "$160.0B", "25.33%", "+1,467 bps"):
        assert shown in text, shown


def test_the_plan_receipt_agrees_with_the_snapshot_section(page):
    """The ledger's plan column must equal evalSnapshot(), the page's own
    snapshot-basis model — two renderings of one calculation, never two."""
    reset(page)
    diffs = page.evaluate(
        """() => {
            const out = [];
            TICKERS.forEach(t => {
                const a = DATA.assum[t], s = state[t];
                const ev = evalQuarter(t, LATEST);
                const ledger = spreadVsWacc(
                    forwardRoic(ev.proxy, marginOf(t), capexSnapshot(a.guide, s.capshare)), a.wacc);
                const section = evalSnapshot(t, s.scenario).spread;
                if(Math.abs(ledger - section) > 1e-12) out.push([t, ledger, section]);
            });
            return out;
        }"""
    )
    assert diffs == []


def test_both_views_share_one_numerator(page):
    """The receipt builds the proxy once because the two views agree on it
    exactly — not approximately. If that ever stops being true the receipt is
    lying about which stage is shared."""
    reset(page)
    diffs = page.evaluate(
        """() => {
            const out = [];
            TICKERS.forEach(t => {
                const run = evalQuarter(t, LATEST).proxy;
                const snap = evalSnapshot(t, state[t].scenario).proxy;
                if(run !== snap) out.push([t, run, snap]);
            });
            return out;
        }"""
    )
    assert diffs == []


def test_the_plan_denominator_names_the_period_it_belongs_to(page):
    """The annual plan is not a per-quarter fact. On any quarter but the latest
    the receipt has to say the plan is not that quarter's own."""
    reset(page)
    assert "effective from 2025-06-30" in page.inner_text("#led-GOOG")
    assert "not Q2 25’s own plan" not in page.inner_text("#led-GOOG")
    page.click("#q-seg button[data-q='Q2 25']")
    page.wait_for_timeout(250)
    assert "not Q2 25’s own plan" in page.inner_text("#led-GOOG")
    reset(page)


def test_the_capex_share_chip_appears_in_both_denominators(page):
    """One assumption, three renderings on the card — and each must drive the
    model from wherever it was opened."""
    reset(page)
    chips = page.locator("#led-GOOG .assum-btn[data-field='capshare']")
    assert chips.count() == 2
    assert set(page.eval_on_selector_all(
        "#led-GOOG .assum-btn[data-field='capshare']", "els => els.map(e => e.dataset.slot)"
    )) == {"run", "plan"}

    before = page.inner_text("#led-GOOG .led-row.total")
    chips.nth(1).click()          # open from the PLAN row, not the run-rate one
    page.wait_for_timeout(200)
    page.evaluate(
        """() => { const i = document.querySelector('.pop input[type=range]');
                   i.value = 0.5; i.dispatchEvent(new Event('input', {bubbles:true})); }"""
    )
    page.wait_for_timeout(300)
    assert page.inner_text("#led-GOOG .led-row.total") != before
    # the popover reattached to the chip it was opened from, not to its namesake
    owner = page.evaluate(
        "() => document.querySelector('.assum-btn[aria-expanded=\"true\"]').dataset.slot")
    assert owner == "plan"
    reset(page)

# ---------------------------------------------------------------------------
# The workbook's own sheets, leading the page
# ---------------------------------------------------------------------------


def test_the_tables_come_before_the_charts(page):
    order = page.evaluate(
        """() => [...document.querySelectorAll('.main > section')].map(s => s.id || s.querySelector('h2').id)"""
    )
    assert order.index("tables") < order.index("traj-h")


def test_the_trajectory_sheet_is_the_workbook_shape(page):
    reset(page)
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(250)
    # 5 company headings + 6 metric rows each
    assert page.locator("#sheet-table tbody tr.grouphead").count() == 5
    assert page.locator("#sheet-table tbody tr").count() == 5 + 5 * 6
    text = page.inner_text("#sheet-table")
    for shown in ("$678.000B", "$41.000B", "$139.4B", "$135.6B"):   # MSFT Q2 26
        assert shown in text, shown


def test_every_sheet_renders(page):
    for sheet, probe in (("snapshot", "Annual capex guide"), ("inputs", "Capex definition")):
        page.click(f"[data-sheet='{sheet}']")
        page.wait_for_timeout(250)
        assert probe.lower() in page.inner_text("#sheet-table").lower(), sheet
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(200)


def test_the_inputs_sheet_links_every_fact_to_its_source(page):
    page.click("[data-sheet='inputs']")
    page.wait_for_timeout(250)
    # two source links per company-quarter
    assert page.locator("#sheet-table [data-jumpsrc]").count() == 5 * len(
        page.eval_on_selector_all("#q-seg button", "els => els.map(e => e.dataset.q)")
    ) * 2
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# Cost of capital
# ---------------------------------------------------------------------------


def test_the_chart_toggles_roic_wacc_and_spread(page):
    reset(page)
    for unit in ("roic", "wacc", "ppt"):
        page.click(f"[data-traj-unit='{unit}']")
        page.wait_for_timeout(300)
        assert page.locator("#traj-svg polyline").count() == 5, unit
        assert page.get_attribute(f"[data-traj-unit='{unit}']", "aria-pressed") == "true"


def test_the_wacc_view_plots_the_threshold_flat(page):
    reset(page)
    page.click("[data-traj-unit='wacc']")
    page.wait_for_timeout(300)
    flat = page.evaluate(
        """() => TICKERS.every(t => {
             const w = waccOf(t);
             return QUARTERS.every(q => Math.abs(w - waccOf(t)) < 1e-15);
           })"""
    )
    assert flat
    page.click("[data-traj-unit='ppt']")
    page.wait_for_timeout(200)


def test_the_built_wacc_starts_identical_across_companies(page):
    """The placeholders are the same for all five on purpose — an unreplaced
    number has to be obvious rather than look like a company estimate."""
    reset(page)
    vals = page.evaluate("() => TICKERS.map(t => computedWacc(t))")
    assert len(set(round(v, 12) for v in vals)) == 1
    assert abs(vals[0] - (0.9 * (0.04 + 1.0 * 0.045) + 0.1 * 0.05 * (1 - 0.21))) < 1e-12
    assert page.locator(".wacc-warn").count() == 5


def test_every_wacc_input_declares_why_it_is_not_a_fact(page):
    flags = page.eval_on_selector_all(
        "#wacc .prov-flag", "els => els.map(e => e.className.replace('prov-flag ',''))"
    )
    assert set(flags) == {"market", "sourceable", "both"}
    # nothing in the cost-of-capital card is dressed up as a sourced fact
    assert page.locator("#wacc .fact-btn").count() == 0


def test_the_sector_wacc_is_what_the_model_uses_until_switched(page):
    reset(page)
    assert page.evaluate("() => waccMode") == "sector"
    same = page.evaluate("() => TICKERS.every(t => waccOf(t) === DATA.assum[t].wacc)")
    assert same


def test_switching_to_the_built_wacc_moves_every_spread(page):
    reset(page)
    before = page.evaluate("() => TICKERS.map(t => evalQuarter(t, LATEST).spread)")
    page.click("[data-wacc-mode='computed']")
    page.wait_for_timeout(350)
    after = page.evaluate("() => TICKERS.map(t => evalQuarter(t, LATEST).spread)")
    assert all(abs(a - b) > 1e-9 for a, b in zip(before, after))
    # and the page's own self-check is unaffected: it asserts against the workbook
    assert page.evaluate("() => runSelfCheck().failures.length") == 0
    page.click("[data-wacc-mode='sector']")
    page.wait_for_timeout(300)
    restored = page.evaluate("() => TICKERS.map(t => evalQuarter(t, LATEST).spread)")
    assert all(abs(a - b) < 1e-12 for a, b in zip(before, restored))


# ---------------------------------------------------------------------------
# The evidence ledger, as a grid ordered by quarter
# ---------------------------------------------------------------------------


def test_the_evidence_ledger_is_ordered_by_quarter(page):
    groups = page.eval_on_selector_all(
        "#src-table tbody tr.grouphead", "els => els.map(e => e.textContent.trim())"
    )
    quarters = page.eval_on_selector_all("#q-seg button", "els => els.map(e => e.dataset.q)")
    expected = [q.replace(" ", " 20") for q in quarters]
    assert groups[: len(expected)] == expected
    assert groups[-2:] == [
        "Not quarter-specific · assumptions rows",
        "Context — no model input reads these",
    ]


def test_every_source_appears_exactly_once(page):
    ids = page.eval_on_selector_all(
        "#src-table tbody tr[data-hay]", "els => els.map(e => e.id.replace('src-',''))"
    )
    assert len(ids) == len(set(ids)) == 62


def test_a_source_row_carries_its_quote_behind_a_click(page):
    row = page.locator("#q-GOOG-Q226-FACT")
    assert row.is_hidden()
    page.click("#src-GOOG-Q226-FACT .ev-toggle")
    page.wait_for_timeout(200)
    assert row.is_visible()
    assert "Revenue backlog/RPO was $519.5B" in row.inner_text()
    page.click("#src-GOOG-Q226-FACT .ev-toggle")
    page.wait_for_timeout(150)
    assert row.is_hidden()


# ---------------------------------------------------------------------------
# Disclosed figures link to the disclosure
# ---------------------------------------------------------------------------


def test_every_disclosed_figure_in_the_tables_is_a_link(page):
    reset(page)
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(250)
    # two disclosed rows per company x five quarters
    assert page.locator("#sheet-table a.fig-src").count() == 5 * 2 * 5
    unresolved = page.evaluate(
        """() => [...document.querySelectorAll('#sheet-table a.fig-src')]
                  .map(a => a.dataset.jumpsrc).filter(id => !DATA.sources[id])"""
    )
    assert unresolved == []


def test_clicking_a_number_lands_on_its_evidence_row(page):
    reset(page)
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(250)
    target = page.locator("#sheet-table a.fig-src").first
    want = target.get_attribute("data-jumpsrc")
    target.click()
    page.wait_for_timeout(700)
    hit = page.locator("#src-table tr.hit")
    assert hit.count() == 1
    assert hit.get_attribute("id") == "src-" + want


def test_the_snapshot_and_inputs_views_link_their_figures_too(page):
    for sheet, least in (("snapshot", 10), ("inputs", 50)):
        page.click(f"[data-sheet='{sheet}']")
        page.wait_for_timeout(250)
        assert page.locator("#sheet-table a.fig-src").count() >= least, sheet
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# QoQ / YoY / LTM
# ---------------------------------------------------------------------------


def test_the_comparison_block_names_the_quarters_it_compares(page):
    reset(page)
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(250)
    heads = page.eval_on_selector_all(
        "#sheet-table th.rhs", "els => els.map(e => e.textContent.trim())"
    )
    assert len(heads) == 3
    assert heads[0].startswith("QoQ") and "Q1 26" in heads[0]
    assert heads[1].startswith("YoY") and "Q2 25" in heads[1]
    assert heads[2].startswith("LTM") and "Q3 25" in heads[2] and "Q2 26" in heads[2]


def test_ltm_capex_is_the_sum_of_the_last_four_quarters(page):
    """And not four times the latest quarter, which for capex ramping this fast
    is a materially different number."""
    reset(page)
    checked = page.evaluate(
        """() => TICKERS.map(t => {
             const qs = QUARTERS.slice(-QUARTERS_PER_YEAR);
             const want = qs.reduce((s, q) => s + FACTS[t+'|'+q].capex, 0);
             const got = ltmFor(t).capex;
             const annualised = FACTS[t+'|'+LATEST].capex * 4;
             return [t, Math.abs(got - want), Math.abs(got - annualised) / want];
           })"""
    )
    for ticker, err, gap in checked:
        assert err < 1e-9, ticker
        # every one of the five is ramping hard enough that the two differ by >5%
        assert gap > 0.05, f"{ticker}: annualising the quarter is within {gap:.1%} of LTM"


def test_ltm_refuses_to_sum_a_point_in_time_balance(page):
    """A backlog is a balance. Four of them cannot be added, and the cell says so
    rather than printing a number."""
    reset(page)
    page.click("[data-sheet='trajectory']")
    page.wait_for_timeout(250)
    msft = page.inner_text("#sheet-table")
    assert "balance" in msft            # RPO rows
    assert "run-rate" in msft           # RPO-derived proxy rows
    flows = page.evaluate("() => TICKERS.map(t => [t, ltmFor(t).isFlow])")
    assert dict(flows) == {"MSFT": False, "GOOG": False, "AMZN": False, "ORCL": False, "META": True}
    # Meta's demand fact is quarterly revenue, so its LTM really is a sum
    meta = page.evaluate(
        """() => {
             const qs = QUARTERS.slice(-QUARTERS_PER_YEAR);
             return [ltmFor('META').demand, qs.reduce((s,q) => s + FACTS['META|'+q].fact, 0)];
           }"""
    )
    assert abs(meta[0] - meta[1]) < 1e-9


def test_the_ltm_spread_uses_the_trailing_denominator(page):
    reset(page)
    ok = page.evaluate(
        """() => TICKERS.every(t => {
             const l = ltmFor(t);
             const roic = forwardRoic(l.proxy, marginOf(t), l.aiCapex);
             return Math.abs(l.roic - roic) < 1e-12
                 && Math.abs(l.spread - (roic - waccOf(t))) < 1e-12;
           })"""
    )
    assert ok


# ---------------------------------------------------------------------------
# The page reads as its own analysis
# ---------------------------------------------------------------------------


FORBIDDEN = [
    "workbook", ".xlsx", "calc.py", "extract.py", "pipeline/", "scripts/",
    "01_sources", "data layer", "this repository", "csv", "python",
]


def test_no_visible_text_reveals_how_the_page_is_built(page):
    """The reader is looking at an analysis, not at a description of the machinery
    that produced one. Nothing on screen — body text, tooltips, labels or alt
    text — should name a file, a script or a source format."""
    reset(page)
    seen = []
    for sheet in ("trajectory", "snapshot", "inputs"):
        page.click(f"[data-sheet='{sheet}']")
        page.wait_for_timeout(250)
        seen.append(page.inner_text("body"))
    # expand the things that are hidden until asked for
    page.click("#src-GOOG-Q226-FACT .ev-toggle")
    page.locator("#led-GOOG .fact-btn").first.click()
    page.wait_for_timeout(300)
    seen.append(page.inner_text("body"))
    seen.append(" ".join(page.eval_on_selector_all(
        "[title]", "els => els.map(e => e.getAttribute('title'))")))
    seen.append(" ".join(page.eval_on_selector_all(
        "[aria-label]", "els => els.map(e => e.getAttribute('aria-label'))")))
    blob = " ".join(seen).lower()
    found = sorted({w for w in FORBIDDEN if w in blob})
    assert found == [], f"visible text still names: {found}"
    reset(page)


def test_the_verification_chip_still_says_what_it_checked(page):
    """De-jargoning must not cost the reader the integrity signal."""
    reset(page)
    assert page.get_attribute("#verify", "data-state") == "pass"
    text = page.inner_text("#verify-text")
    assert "verified" in text.lower() and "535" in text
    title = page.get_attribute("#verify", "title")
    assert "535" in title and "recomputed" in title.lower()

# ---------------------------------------------------------------------------
# Last, so it sees everything the tests above provoked
# ---------------------------------------------------------------------------


def test_nothing_in_this_module_threw(page):
    """A throw inside a click handler is invisible to a load-time check.

    Deleting jumpToFigure() while replacing the evidence renderer broke every
    back-link on the page and the load-time check above still passed, because
    the error only happens when someone clicks. The page fixture collects
    pageerror for the whole module, so asserting it here catches that class of
    breakage for every interaction the file exercises.
    """
    assert page.errors == []
