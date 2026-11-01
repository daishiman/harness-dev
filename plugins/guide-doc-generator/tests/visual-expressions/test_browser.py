"""実表示で文字・接続・開閉を確認する。構文合格だけで可読と扱わない。"""
import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("visual_gallery", ROOT / "scripts/build-diagram-gallery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path_factory.mktemp("diagrams") / "gallery.html"
    path.write_text(module.build_gallery(), encoding="utf-8")
    with playwright.sync_playwright() as p:
        options = {"headless": True}
        if os.environ.get("HANDOUT_BROWSER"):
            options["executable_path"] = os.environ["HANDOUT_BROWSER"]
        elif not Path(p.chromium.executable_path).is_file():
            pytest.skip("表示確認用ブラウザがありません。HANDOUT_BROWSERに実在ブラウザを指定してください")
        browser = p.chromium.launch(**options)
        result = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        result.on("pageerror", lambda error: errors.append(str(error)))
        result.goto(path.as_uri())
        yield result
        assert not errors
        browser.close()


@pytest.mark.parametrize("width", [1440, 768, 375])
def test_labels_stay_legible_and_inside_figure_without_page_overflow(page, width):
    page.set_viewport_size({"width": width, "height": 1000})
    result = page.evaluate("""() => {
      const texts = [...document.querySelectorAll('.diagram svg text')];
      const htmlTexts = [...document.querySelectorAll('.diagram-metric *, .gallery-html-example *')]
        .filter(el => [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim()));
      return {
        overflow: document.documentElement.scrollWidth > innerWidth,
        smallest: Math.min(...texts.map(t => parseFloat(getComputedStyle(t).fontSize)*t.getScreenCTM().a),
                           ...htmlTexts.map(t => parseFloat(getComputedStyle(t).fontSize))),
        outside: texts.filter(t => { const b=t.getBBox(),v=t.ownerSVGElement.viewBox.baseVal;
          return b.x < -.5 || b.y < -.5 || b.x+b.width > v.width+.5 || b.y+b.height > v.height+.5;
        }).map(t=>t.textContent)
      };
    }""")
    assert not result["overflow"]
    assert result["smallest"] >= 13.9
    assert result["outside"] == []


@pytest.mark.parametrize("width", [1440, 768, 375])
def test_html_examples_wrap_without_clipping(page, width):
    page.set_viewport_size({"width": width, "height": 1000})
    result = page.evaluate("""() => [...document.querySelectorAll('.gallery-html-example')].map(box => {
      const bounds=box.getBoundingClientRect();
      return {id:box.closest('section').id, clipped:[...box.querySelectorAll('*')].filter(el=>{
        const b=el.getBoundingClientRect();
        if (!b.width || (b.left >= bounds.left-.5 && b.right <= bounds.right+.5)) return false;
        const region=el.closest('.table-wrap');
        if (!region || !box.contains(region)) return true;
        const r=region.getBoundingClientRect();
        return !(getComputedStyle(region).overflowX==='auto' && region.scrollWidth>region.clientWidth
          && r.left>=bounds.left-.5 && r.right<=bounds.right+.5);
      }).map(el=>el.textContent), scrollable:[...box.querySelectorAll('.table-wrap')]
        .filter(el=>el.scrollWidth>el.clientWidth).map(el=>({role:el.getAttribute('role'),
          tabIndex:el.tabIndex,name:el.getAttribute('aria-label'),
          rowHeader:el.querySelector('tbody th').getBoundingClientRect().width}))};
    })""")
    assert len(result) >= 3
    assert all(not item["clipped"] for item in result), result
    for item in result:
        for region in item["scrollable"]:
            assert region["role"] == "region" and region["tabIndex"] == 0
            assert region["name"] and region["rowHeader"] >= 100
    if width == 375:
        region = page.locator('#html-table .table-wrap')
        region.evaluate('(el)=>el.scrollLeft=0')
        region.focus()
        page.keyboard.press('ArrowRight')
        page.wait_for_function("document.querySelector('#html-table .table-wrap').scrollLeft>0")


def test_candidate_table_keeps_readable_columns_and_examples_on_narrow_screen(page):
    page.set_viewport_size({"width": 375, "height": 1000})
    result = page.evaluate("""() => {
      const region=document.querySelector('.candidate-table-scroll');
      return {pageOverflow:document.documentElement.scrollWidth>innerWidth,
              regionOverflow:region.scrollWidth>region.clientWidth,
              relationWidth:region.querySelector('tbody th').getBoundingClientRect().width,
              widestColumn:Math.max(...[...region.querySelectorAll('thead th')].map(th=>th.getBoundingClientRect().width)),
              viewportWidth:region.clientWidth,
              links:[...region.querySelectorAll('a')].map(a=>!!document.querySelector(a.getAttribute('href')))};
    }""")
    assert not result["pageOverflow"]
    assert result["regionOverflow"]
    assert result["relationWidth"] >= 100
    assert result["widestColumn"] <= result["viewportWidth"]
    assert result["links"] and all(result["links"])


def test_kpi_value_unit_and_caption_are_initially_visible_on_narrow_screen(page):
    page.set_viewport_size({"width": 375, "height": 1000})
    result = page.evaluate("""() => {
      const figure=document.querySelector('#bignumber figure');
      const bounds=figure.getBoundingClientRect();
      return {renderer:figure.dataset.hbDiagramRenderer,
              fields:['value','unit','caption'].map(name=>{
                const el=figure.querySelector('.diagram-metric-'+name),b=el.getBoundingClientRect();
                return {name,text:el.textContent,visible:b.left>=bounds.left-.5&&b.right<=bounds.right+.5};
              })};
    }""")
    assert result["renderer"] == "html"
    assert all(field["text"] and field["visible"] for field in result["fields"]), result


def test_details_work_with_keyboard_and_restore_after_print(page):
    summary = page.locator("summary").first
    summary.focus()
    page.keyboard.press("Enter")
    assert summary.evaluate("s=>s.parentElement.open")
    initially_open = page.locator("details[open]").count()
    page.evaluate("window.dispatchEvent(new Event('beforeprint'))")
    assert page.locator("details:not([open])").count() == 0
    page.evaluate("window.dispatchEvent(new Event('afterprint'))")
    assert page.locator("details[open]").count() == initially_open


def test_diagram_zoom_closes_with_escape_and_returns_focus(page):
    button = page.locator("#relationship .diagram-expand")
    button.focus()
    page.keyboard.press("Enter")
    assert page.locator("dialog[open]").count() == 1
    page.keyboard.press("Escape")
    assert page.locator("dialog[open]").count() == 0
    assert button.evaluate("b=>b===document.activeElement")


def test_gallery_rebuilds_byte_identically():
    spec = importlib.util.spec_from_file_location("repeat_gallery", ROOT / "scripts/build-diagram-gallery.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.build_gallery() == module.build_gallery()
