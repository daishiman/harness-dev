#!/usr/bin/env python3
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
    ctx = {"diagram_module": diagram, "diagrams": 0, "doc_title": "図解の表現と読みやすさ", "section_heading": "図解例"}
    painter = render.Renderer(ctx)
    sections, nav = [], []
    for index, (pattern, entry) in enumerate(catalog["patterns"].items(), 1):
        title = html.escape(entry["title"])
        nav.append('<a class="nav-chip" href="#%s"><span class="chip-text">%s</span></a>' % (pattern, title))
        figure = painter.diagram(dict(entry["example"], type="diagram", id="example-"+pattern,
                                      title=entry["title"], pattern=pattern),
                                 [("data-hb-part", "DIAGRAM"), ("data-hb-part-id", "example-"+pattern)])
        disclosure = painter.accordion({"items": [{"summary": "この表現に渡すデータ", "body": entry["input"], "open": False}]}, [])
        sections.append('<section class="section-card" id="%s"><h2>%d. %s</h2>%s%s</section>' %
                        (pattern, index, title, figure, disclosure))
    intents = "".join('<tr><th scope="row">%s</th><td>%s</td><td>%s</td></tr>' %
                      tuple(html.escape(entry[key]) for key in ("relation", "forms", "selection_note"))
                      for entry in catalog["intents"])
    sections.append('<section class="section-card" id="candidates"><h2>関係から表現を探す</h2>'
                    '<p>掲載例は候補集です。文章の主張と関係を先に確かめ、必要なら分図や専用作図を選びます。</p>'
                    '<div class="table-wrap"><table><thead><tr><th scope="col">伝える関係</th>'
                    '<th scope="col">表現の候補</th><th scope="col">選ぶ条件</th></tr></thead>'
                    '<tbody>'+intents+'</tbody></table></div></section>')
    return ('<!doctype html>\n<html lang="ja"><head><meta charset="UTF-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>図解の表現と読みやすさ</title><style>'+render.build_css(render.load_theme_tokens(theme))+
            '</style></head><body><a class="skip-to-main" href="#handout-main">本文へ移動</a>'
            '<div class="page-shell"><header class="pop-header pop-header--sidebar">'
            '<p class="doc-title-bar">図解の表現と読みやすさ</p><nav class="navbar" aria-label="目次">'+"".join(nav)+
            '<a class="nav-chip" href="#candidates">関係から表現を探す</a></nav></header>'
            '<main class="wrap" id="handout-main"><div class="hero"><h1>文章の関係を、読める図へ</h1>'
            '<p>図を眺めて関係を掴み、必要な説明だけを開きます。図は拡大して読めます。</p>'
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
