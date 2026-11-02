#!/usr/bin/env python3
# /// script
# name: build-diagram-gallery
# version: 0.1.0
# purpose: 図解とHTML表現の実例を既存レンダラで再生成する
# inputs: argv --out <html> [--theme <name>]
# outputs: 明示した出力先または検査結果の標準出力
# requires-python: ">=3.10"
# dependencies: []
# contexts: [C]
# network: false
# write-scope: --out の明示パスのみ
# ///
"""登録済みの図解例を、実際の資料レンダラとテーマで単一HTMLへ再生成する。

入力: config/handout-diagrams.json / --out <HTML path>
出力: 明示された --out のみ。標準ライブラリ限定、ネットワーク不要。
用途: 見た目・開閉・拡大の確認。完成した業務資料のサンプルではない。
"""
import argparse
import html
import importlib.util
import json
from pathlib import Path


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_gallery(theme="pop"):
    root = Path(__file__).resolve().parent.parent
    catalog = json.loads((root / "config/handout-diagrams.json").read_text(encoding="utf-8"))
    render = load(root / "scripts/render-handout.py", "gallery_handout")
    diagram = load(root / "scripts/render-diagram-svg.py", "gallery_diagrams")
    ctx = {"diagram_module": diagram, "diagrams": 0, "doc_title": "図解の表現と読みやすさ", "section_heading": "図解例",
           "block_type_by_part": render.block_type_by_part_id(),
           "part_by_type": render.part_id_by_block_type(), "blocks_by_type": {}}
    painter = render.Renderer(ctx)
    sections, nav, pattern_media = [], [], {}
    for index, (pattern, entry) in enumerate(catalog["patterns"].items(), 1):
        title = html.escape(entry["title"])
        nav.append('<a class="nav-chip" href="#%s"><span class="chip-text">%s</span></a>' % (pattern, title))
        figure = painter.diagram(dict(entry["example"], type="diagram", id="example-"+pattern,
                                      title=entry["title"], pattern=pattern),
                                 [("data-hb-part", "DIAGRAM"), ("data-hb-part-id", "example-"+pattern)])
        pattern_media[pattern] = "HTML/CSS" if 'data-hb-diagram-renderer="html"' in figure else "SVG"
        disclosure = painter.accordion({"items": [{"summary": "この表現に渡すデータ", "body": entry["input"], "open": False}]}, [])
        sections.append('<section class="section-card" id="%s"><h2>%d. %s</h2>%s%s</section>' %
                        (pattern, index, title, figure, disclosure))
    for key, entry in catalog.get("html_examples", {}).items():
        title = html.escape(entry["title"])
        anchor = "html-" + key
        nav.append('<a class="nav-chip" href="#%s"><span class="chip-text">%s</span></a>' % (anchor, title))
        part = {"part": ctx["part_by_type"][entry["block_type"]], "id": anchor, "data": entry["example"]}
        body = painter.block(render.project_part(part, ctx))
        sections.append('<section class="section-card" id="%s" data-hb-gallery-medium="html">'
                        '<h2>%s</h2><p class="gallery-medium">HTML/CSSの既存部品で描画</p>'
                        '<div class="gallery-html-example">%s</div><p>%s</p></section>' %
                        (anchor, title, body, html.escape(entry["input"])))
    rows = []
    for entry in catalog["intents"]:
        links, media = [], []
        for pattern in entry["patterns"]:
            links.append('<a href="#%s">%s</a>' % (pattern, html.escape(catalog["patterns"][pattern]["title"])))
            if pattern_media[pattern] not in media:
                media.append(pattern_media[pattern])
        for key in entry.get("html_examples", []):
            links.append('<a href="#html-%s">%s</a>' % (key, html.escape(catalog["html_examples"][key]["title"])))
            if "HTML/CSS" not in media:
                media.append("HTML/CSS")
        route = "・".join(media) if media else "専用作図または既存部品の組合せ"
        examples = '<div class="candidate-examples">%s</div>' % "".join(links) if links else '<p class="candidate-no-example">内蔵の実例なし。専用作図で意味を保持します。</p>'
        note = entry.get("rendering_note")
        rendering = '<p class="candidate-rendering">描画：%s%s</p>' % (html.escape(route), "。" + html.escape(note) if note else "")
        rows.append('<tr><th scope="row">%s</th><td>%s%s</td><td>%s%s</td></tr>' %
                    (html.escape(entry["relation"]), html.escape(entry["forms"]), examples,
                     html.escape(entry["selection_note"]), rendering))
    sections.append('<section class="section-card" id="candidates"><h2>関係から表現を探す</h2>'
                    '<p>掲載例は候補集です。文章の主張と関係を先に確かめ、実例で見え方を確認します。</p>'
                    '<p class="candidate-scroll-hint">狭い画面では、この一覧の中を横にスクロールできます。</p>'
                    '<div class="table-wrap candidate-table-scroll" tabindex="0" role="region" aria-label="関係から表現を探す一覧（横スクロール対応）">'
                    '<table class="candidate-table"><colgroup><col class="candidate-relation"><col class="candidate-forms"><col class="candidate-condition"></colgroup>'
                    '<thead><tr><th scope="col">伝える関係</th>'
                    '<th scope="col">表現の候補</th><th scope="col">選ぶ条件</th></tr></thead>'
                    '<tbody>'+"".join(rows)+'</tbody></table></div></section>')
    gallery_css = """
.gallery-medium, .candidate-rendering, .candidate-no-example { color: var(--ink-muted); font-size: .875rem; }
.gallery-medium { margin: 0 0 14px; }
.gallery-html-example { padding: 16px; border: 1px solid var(--line); border-radius: 14px; background: var(--surface, #fff); }
.gallery-html-example .step-label { flex: 0 0 7em; font-weight: 600; }
.gallery-html-example .step-detail { min-width: 0; }
.candidate-table-scroll { min-width: 0; overscroll-behavior-inline: contain; }
.candidate-table { min-width: 640px; table-layout: fixed; }
.candidate-table .candidate-relation { width: 112px; }
.candidate-table .candidate-forms { width: 250px; }
.candidate-table .candidate-condition { width: auto; }
.candidate-examples { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 8px; }
.candidate-examples a { color: var(--pop-primary-deep); text-underline-offset: .2em; font-size: .875rem; }
.candidate-rendering, .candidate-no-example { margin: 8px 0 0; }
@media (max-width: 600px) {
  .gallery-html-example { padding: 12px; }
  .gallery-html-example .step-row { display: grid; grid-template-columns: 2em minmax(0,1fr); gap: 2px 8px; }
  .gallery-html-example .step-num { grid-row: span 2; }
  .gallery-html-example .step-detail { grid-column: 2; }
}
@media print {
  .candidate-table { min-width: 0; table-layout: auto; }
  .candidate-table-scroll { overflow: visible; }
  .candidate-table col { width: auto; }
  .candidate-scroll-hint { display: none; }
}
"""
    return ('<!doctype html>\n<html lang="ja"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>図解の表現と読みやすさ</title><style>'+render.build_css(render.load_theme_tokens(theme))+
            gallery_css+'</style></head><body><a class="skip-to-main" href="#handout-main">本文へ移動</a>'
            '<div class="page-shell"><header class="pop-header pop-header--sidebar">'
            '<p class="doc-title-bar">図解の表現と読みやすさ</p><nav class="navbar" aria-label="目次">'+"".join(nav)+
            '<a class="nav-chip" href="#candidates">関係から表現を探す</a></nav></header>'
            '<main class="wrap" id="handout-main"><div class="hero"><h1>文章の関係を、読める図へ</h1>'
            '<p>HTMLは図の種類ではなく、資料の出力形式・描画方法です。'
            '短い手順や比較はHTML/CSS、接続線や座標を追う図はSVG、専用の記法は描画済み素材を選べます。</p>'
            '<p><a href="#candidates">関係から表現を探し、実例へ進む</a></p>'
            '<p>以下の数値・日程は表現確認用の架空データです。</p></div>'+"".join(sections)+
            '</main></div><script>'+render.build_script()+'</script></body></html>\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--theme", default="pop", help="同梱テーマ名")
    args = parser.parse_args()
    args.out.write_text(build_gallery(args.theme), encoding="utf-8")
    print(str(args.out))


if __name__ == "__main__":
    main()
