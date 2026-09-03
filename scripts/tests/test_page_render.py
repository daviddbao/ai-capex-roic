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
    assert page.locator(".led").count() == 5


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
    page.click("#src-GOOG-Q226-FACT .usedby a")
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
