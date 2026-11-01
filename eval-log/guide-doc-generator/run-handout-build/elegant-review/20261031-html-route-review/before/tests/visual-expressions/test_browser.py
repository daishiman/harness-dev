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
      return {
        overflow: document.documentElement.scrollWidth > innerWidth,
        smallest: Math.min(...texts.map(t => parseFloat(getComputedStyle(t).fontSize)*t.getScreenCTM().a)),
        outside: texts.filter(t => { const b=t.getBBox(),v=t.ownerSVGElement.viewBox.baseVal;
          return b.x < -.5 || b.y < -.5 || b.x+b.width > v.width+.5 || b.y+b.height > v.height+.5;
        }).map(t=>t.textContent)
      };
    }""")
    assert not result["overflow"]
    assert result["smallest"] >= 13.9
    assert result["outside"] == []


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
