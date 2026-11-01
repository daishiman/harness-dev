"""単純KPIと専用図表の表示経路を、元データを失わず確認する。"""
import base64
import importlib.util
import html
import json
import os
from pathlib import Path
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "scripts" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def painter():
    module = load("render-handout")
    return module.Renderer({"diagram_module": load("render-diagram-svg"), "diagrams": 0,
                            "section_heading": "確認", "doc_title": "資料", "assets": {}, "embedded_bytes": 0})


def metric():
    return {"type": "diagram", "id": "metric", "pattern": "bignumber", "title": "回答までの時間",
            "value": "3", "unit": "分", "caption": "回答までの時間", "sub": "表現確認用の例"}


def test_metric_is_responsive_html_and_keeps_source_markers():
    output = painter().diagram(metric(), [("data-hb-part", "DIAGRAM")])
    assert 'data-hb-diagram-renderer="html"' in output
    assert 'class="diagram-metric-value"' in output
    assert 'class="diagram-metric-unit"' in output
    assert 'class="diagram-metric-caption"' in output
    assert 'data-hb-diagram-data=' in output
    assert '<svg' not in output


def test_html_metric_is_real_content_and_empty_or_tampered_metric_is_rejected():
    checker = load("verify-handout-selfcontained")
    output = painter().diagram(metric(), [("data-hb-part", "DIAGRAM")])
    _, errors = checker._detect_sc09(checker.Document(output))
    assert not errors
    for changed in [output.replace('>3</span>', '></span>'),
                    output.replace('>3</span>', '>4</span>'),
                    output.replace('>分</span>', '>時間</span>'),
                    '<figure data-hb-part="DIAGRAM" data-hb-diagram-renderer="html"><p>図</p></figure>']:
        _, errors = checker._detect_sc09(checker.Document(changed))
        assert errors


def test_metric_description_reaches_accessibility_without_visible_duplication():
    checker = load("verify-handout-selfcontained")
    spec = dict(metric(), unit="営業日", caption="回答まで",
                description='土日祝を除く「受付日」の翌日から数える。<翌日> & "受付"を確認。')
    output = painter().diagram(spec, [("data-hb-part", "DIAGRAM")])
    doc = checker.Document(output)
    figure = next(node for node in doc.elements if node.tag == "figure")
    assert figure.attrs.get("aria-description") == spec["description"]
    assert spec["description"] not in figure.visible_text()
    _, errors = checker._detect_sc09(doc)
    assert not errors
    encoded = html.escape(spec["description"], quote=True)
    for changed in [output.replace(' aria-description="'+encoded+'"', ''),
                    output.replace('aria-description="'+encoded+'"', 'aria-description="暦日で数える"')]:
        _, errors = checker._detect_sc09(checker.Document(changed))
        assert errors


@pytest.mark.parametrize("description", [None, "", "   "])
def test_metric_without_description_does_not_invent_aria_text(description):
    checker = load("verify-handout-selfcontained")
    spec = metric()
    if description is not None:
        spec["description"] = description
    output = painter().diagram(spec, [("data-hb-part", "DIAGRAM")])
    assert "aria-description=" not in output
    _, errors = checker._detect_sc09(checker.Document(output))
    assert not errors
    invented = output.replace('<figure ', '<figure aria-description="元データにない説明" ', 1)
    _, errors = checker._detect_sc09(checker.Document(invented))
    assert errors


def test_specialized_figure_uses_shared_keyboard_zoom_without_changing_photo():
    renderer = painter()
    uri = 'data:image/svg+xml,%3Csvg%20viewBox%3D%220%200%201200%20700%22%3E%3C%2Fsvg%3E'
    renderer.ctx["assets"]["chart"] = {"data_uri": uri, "role": "figure", "alt": "担当の関係", "caption": "担当の受け渡し"}
    chart = renderer.image({"asset_id": "chart"}, [])
    assert 'asset--figure' in chart and 'diagram-viewport' in chart
    assert 'class="diagram-expand"' in chart and 'tabindex="0"' in chart
    assert 'width: 1200px' in chart
    disabled = renderer.image({"asset_id": "chart", "lightbox": False}, [])
    assert 'diagram-viewport' in disabled and 'diagram-expand' not in disabled
    renderer.ctx["assets"]["chart"]["role"] = "photo"
    photo = renderer.image({"asset_id": "chart"}, [])
    assert 'asset--figure' not in photo and 'diagram-expand' not in photo


def test_native_svg_diagram_remains_the_same_format():
    output = painter().diagram({"type": "diagram", "id": "flow", "pattern": "flow", "title": "依頼の順序",
                                "steps": [{"label": "依頼"}, {"label": "結果"}]}, [])
    assert '<svg' in output and 'diagram-viewport' in output


def test_qr_svg_uses_display_width_instead_of_module_count():
    """QRのviewBoxはセル数であり、CSSの表示幅ではない。"""
    renderer = painter()
    for size in ('140', '200px'):
        source = '<svg xmlns="http://www.w3.org/2000/svg" width="{}" viewBox="0 0 37 37"/>'.format(size)
        uri = 'data:image/svg+xml;base64,' + base64.b64encode(source.encode()).decode()
        renderer.ctx['assets']['qr'] = {'data_uri': uri, 'role': 'figure', 'alt': '申し込み用QR'}
        output = renderer.image({'asset_id': 'qr'}, [])
        assert 'width: {}px'.format(size.replace('px', '')) in output
        assert 'width: 37px' not in output


def test_figure_zoom_keeps_natural_width_and_keyboard_focus(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    render = load("render-handout")
    renderer = painter()
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400"><rect width="1200" height="400" fill="white"/><text x="20" y="40" font-size="16">担当間の受け渡し</text></svg>'
    renderer.ctx["assets"]["chart"] = {"data_uri": "data:image/svg+xml," + urllib.parse.quote(svg),
                                        "role": "figure", "alt": "担当間の受け渡し", "caption": "受け渡しの流れ"}
    output = renderer.image({"asset_id": "chart"}, [])
    html = ('<!doctype html><html lang="ja"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<style>'+render.build_css(render.load_theme_tokens("pop"))+'</style><body><main class="wrap">'+output+
            '</main><script>'+render.build_script()+'</script></body></html>')
    path = tmp_path / "figure.html"; path.write_text(html, encoding="utf-8")
    with playwright.sync_playwright() as p:
        options = {"headless": True}
        if os.environ.get("HANDOUT_BROWSER"):
            options["executable_path"] = os.environ["HANDOUT_BROWSER"]
        elif not Path(p.chromium.executable_path).is_file():
            pytest.skip("表示確認用ブラウザがありません")
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 375, "height": 900}); page.goto(path.as_uri())
        assert page.locator('.diagram-image').evaluate("el=>el.getBoundingClientRect().width") == 1200
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        button = page.locator('.diagram-expand'); button.focus(); page.keyboard.press('Enter')
        assert page.locator('dialog[open]').count() == 1
        assert page.locator('dialog .diagram-image').evaluate("el=>el.getBoundingClientRect().width") == 1200
        assert page.locator('dialog .diagram-viewport').evaluate("el=>el.scrollWidth>el.clientWidth")
        page.keyboard.press('Escape')
        assert page.locator('dialog[open]').count() == 0
        assert button.evaluate("el=>el===document.activeElement")
        browser.close()
