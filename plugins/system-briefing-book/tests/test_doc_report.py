"""lib/doc-report.mjs: 文書 (Markdown) を、まとめ HTML の中でカードや区切りを使ったレポートの形に描く。"""
from __future__ import annotations

import json
from html.parser import HTMLParser

import pytest

from conftest import node_eval


def test_every_table_rule_has_a_part() -> None:
    """validate が決めている表の列の並びは、どれも部品で描ける (片方だけ直すと素の表に戻るのを防ぐ)。"""
    shapes, rules = node_eval(
        'import { TABLE_SHAPES } from "./lib/doc-report.mjs";\n'
        'import * as v from "./validate-briefing-docs.mjs";\n'
        "const rules = [...Object.values(v.REQ_TABLES), v.HEARING_TABLE, v.SPEC_SCREEN_TABLE, v.SPEC_ITEM_TABLE,\n"
        "  v.SPEC_OPS_TABLE, v.SPEC_DATA_TABLE, v.SPEC_RULE_TABLE, v.SPEC_PLATFORM_TABLE, v.SPEC_ROLE_TABLE, v.CHANGES_TABLE];\n"
        "console.log(JSON.stringify([TABLE_SHAPES, rules]));"
    )
    known = {tuple(s) for s in shapes}
    assert [r for r in rules if tuple(r) not in known] == []


def test_known_table_becomes_part_and_unknown_stays_table() -> None:
    text = "\n".join([
        "# 要件定義書: 試し", "",
        "## 8. 用語", "", "| 用語 | 意味 |", "| --- | --- |", "| 記録票 | 1 日の配車を書く紙。F01 で読む |", "",
        "## 10. ほか", "", "| 列A | 列B |", "| --- | --- |", "| <script>x</script> | Q09 と 02 のボード |", "| 並び | 04・09 のボード、X04、06 のボード |", "",
    ])
    first, second = node_eval(
        'import { convertDoc, resolveRefs } from "./lib/doc-report.mjs";\n'
        f"const text = {json.dumps(text, ensure_ascii=False)};\n"
        'const run = () => { const d = convertDoc(text, "req", new Set()); return { ...d, body: resolveRefs(d.body, new Set(["req-f01", "b04"])) }; };\n'
        "console.log(JSON.stringify([run(), run()]));"
    )
    body = first["body"]
    assert first == second, "同じ文書からは同じ HTML"
    assert first["title"] == "要件定義書: 試し" and first["toc"] == [["req-8", "8. 用語"], ["req-10", "10. ほか"]]
    assert '<h3 id="req-8">用語</h3>' in body and '<dl class="d-terms">' in body, "知っている表は部品"
    assert body.count('<div class="tw"><table>') == 1, "知らない表は今までどおり横に送れる枠で包む"
    assert '<a class="ref" href="#req-f01">F01</a>' in body, "文の中の番号はリンク"
    assert '<span class="ref">Q09</span>' in body and '<span class="ref">02 のボード</span>' in body, "行き先が無いものは文字に戻す"
    assert '<a class="ref" href="#b04">04</a>・<span class="ref">09 のボード</span>' in body, "並びは 1 つずつ"
    assert 'X04、<span class="ref">06 のボード</span>' in body, "英字のあとの数字はボードの番号と見なさない"
    assert "<script>" not in body and "&lt;script&gt;" in body


def test_long_candidate_name_still_becomes_card() -> None:
    """8 章の候補の名前が 16 字を超えても、カードに描く (素の箇条書きに戻らない)。"""
    name = "取り込み先のシステムと毎晩自動でつなぐ"
    text = "\n".join([
        "# 仕様書: 試し", "", "## 8. 最初の版に入れないもの", "",
        f"- {name}: 書き出しの手間をなくす。", "  - 備え: 書き出した行に日時の印を付ける。", "  - 時期: その先", "",
    ])
    (doc,) = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        f"console.log(JSON.stringify([convertDoc({json.dumps(text, ensure_ascii=False)}, \"spec\", new Set())]));"
    )
    assert len(name) > 16
    assert '<article class="d-card d-future">' in doc["body"] and f'<p class="d-name">{name}</p>' in doc["body"]


class VisibleText(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.parts = []
        self.feed(html)

    def handle_data(self, data):
        self.parts.append(data)


def doc_body(text: str) -> str:
    return node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        f'console.log(JSON.stringify(convertDoc({json.dumps(text)}, "spec", new Set()).body));',
        timeout=5,
    )


@pytest.mark.parametrize("indent", ["", " ", "  ", "   ", "    ", "        ", "\t", " \t"])
@pytest.mark.parametrize("marker", ["-", "3.", "4)"])
def test_list_indentation_terminates_and_preserves_children(indent, marker):
    body = doc_body(f"{indent}{marker} 親条件\n{indent}    - 子条件\n{indent}{marker} 次条件")
    assert all(word in body for word in ["親条件", "子条件", "次条件"])
    if marker != "-":
        assert f'start="{marker[0]}"' in body


@pytest.mark.parametrize("text", ["-", "    -", "\t-", "  2.", "-\n  - 条件"])
def test_empty_list_items_terminate(text):
    body = doc_body(text)
    assert "<li>" in body
    if "条件" in text:
        assert "条件" in body


@pytest.mark.parametrize("child", [
    "    - 保持期限: 30日",
    "\n    保持期限: 30日",
    "\n    ```text\n    保持期限: 30日\n    ```",
    "    1. 保持期限: 30日",
])
def test_candidate_keeps_nested_conditions_and_blocks(child):
    body = doc_body(f"- 候補: 自動化\n  - 備え: 記録\n{child}\n  - 時期: 次の版")
    text = "".join(VisibleText(body).parts)
    assert all(word in text for word in ["候補", "自動化", "備え", "記録", "保持期限: 30日", "時期", "次の版"])
    assert 'class="d-card d-future"' not in body
    if "```" in child:
        assert "<pre><code" in body


@pytest.mark.parametrize("count,unit", [("2", "人"), ("0", "人"), ("2〜3名（繁忙期5名）", "役割"),
                                         ("約10人", "役割"), ("1,000", "役割"), ("未定", "役割"),
                                         ("9007199254740992", "役割")])
def test_population_keeps_original_and_only_sums_exact_integers(count, unit):
    body = doc_body("|使う人|人数|端末|主にすること|\n|---|---|---|---|\n"
                    f"|配車|{count}|PC|確認|\n\n"
                    "|画面番号|画面名|使う人|端末|ひとことで|\n|---|---|---|---|---|\n|S01|一覧|配車|PC|確認|")
    assert f'<p class="d-count">{count}</p>' in body
    expected = count if unit == "人" else "1"
    assert f'<span>使う人</span><b>{expected}</b><small>{unit}</small>' in body


@pytest.mark.parametrize("screen", ["S01（管理者のみ）", "S01とS02（参照専用）", "XS01", "S01, S02"])
def test_screen_annotations_and_boundaries_preserved(screen):
    body = doc_body(f"|番号|できること|画面|最初の版|\n|---|---|---|---|\n|F01|確認|{screen}|○|")
    assert screen in "".join(VisibleText(body).parts)
    if screen == "XS01":
        assert 'href="#spec-s01"' not in body


@pytest.mark.parametrize("title", ["仕様書: 配車: 第2版", "仕様書：配車：夜間便", "仕様書：配車: 夜間便"])
def test_title_keeps_everything_after_first_colon(title):
    body = doc_body(f"# {title}")
    assert title[4:].strip() in "".join(VisibleText(body).parts)


def test_unknown_table_preserves_alignment_and_escaped_pipe():
    body = doc_body("|左|中央|右|\n|:---|:---:|---:|\n|a\\|b|中心|100|")
    assert all(f'text-align:{a}' in body for a in ["left", "center", "right"])
    assert "a|b" in body


def test_image_hook_is_optional_and_propagates_through_renderers():
    text = """# 文書
本文 ![本文図](body.png)

- 通常項目 ![項目図](list.png)
  - 子 ![子図](child.png)

|用語|意味|
|---|---|
|図|![表図](table.png)|

> ![引用図](quote.png)

**![太字図](bold.png "題")**
"""
    hooked, fallback, calls, inline = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        'import { renderInline } from "./lib/markdown-lite.mjs";\n'
        f'const text = {json.dumps(text)};\n'
        'const calls = []; const hooks = {image: (alt, src) => {calls.push([alt, src]); return `<img alt="${alt}" src="${src}" />`;}};\n'
        'const hooked = convertDoc(text, "spec", new Set(), hooks).body;\n'
        'const fallback = convertDoc(text, "spec", new Set()).body;\n'
        'console.log(JSON.stringify([hooked, fallback, calls, renderInline("![<図>](x)", {image: () => null})]));'
    )
    assert hooked.count("<img ") == 6
    assert len(calls) == 6 and ["太字図", "bold.png"] in calls
    assert "<img " not in fallback and "本文図" in fallback
    assert inline == "&lt;図&gt;"


def test_source_chip_notes_survive():
    body = doc_body("|番号|質問|回答|出どころ|\n|---|---|---|---|\n|H01|確認|回答|未定: 承認待ち、要望: 夜間のみ、例: 月末|")
    assert all(word in body for word in ["承認待ち", "夜間のみ", "月末"])


def test_ordered_labeled_items_keep_start_number_and_order():
    body = doc_body("7. H01: 最初の確認\n8. H02: 次の確認")
    assert 'start="7"' in body and 'counter-reset: st 6' in body
    assert body.index("最初の確認") < body.index("次の確認")


def test_fence_inside_candidate_keeps_different_markers_as_code():
    body = doc_body("- 候補: 自動化\n  - 備え: 記録\n\n    ````text\n    ```\n\n    保持期限: 30日\n    ````\n  - 時期: 次の版")
    assert "保持期限: 30日" in body and "<pre><code" in body
    assert 'd-future' not in body


def test_deep_list_keeps_content_and_terminates():
    body = doc_body("\n".join("  " * i + f"- 条件{i}" for i in range(40)))
    assert all(f"条件{i}" in body for i in range(40))


@pytest.mark.parametrize("syntax,definition", [
    ("![説明][図ID]", '[図ID]: figure.png "図の題名"'),
    ("![図][]", "[図]: <assets/参考 図.png> '題名'"),
    ("![図]", "[図]: figure.png"),
    ("![説明][  Fig   ID ]", "[fig id]: figure.png"),
])
def test_reference_images_use_same_hook_across_sections(syntax, definition):
    markdown = f"# 文書\n\n## 1 内容\n{syntax}\n\n## 2 定義\n{definition}"
    results = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        'import { renderMarkdown } from "./lib/markdown-lite.mjs";\n'
        f'const text = {json.dumps(markdown)};\n'
        'console.log(JSON.stringify([renderMarkdown, (text,hooks) => convertDoc(text,"spec",new Set(),hooks).body].map(render => {\n'
        'const calls = []; const html = render(text, {image: (alt,src) => { calls.push([alt,src]); return "<img />"; }}); return [html,calls];})));'
    )
    expected_src = "assets/参考 図.png" if "<assets" in definition else "figure.png"
    for html, calls in results:
        assert len(calls) == 1 and calls[0][1] == expected_src
        assert "<img />" in html and definition not in html


def test_reference_definitions_ignore_code_and_first_definition_wins():
    text = """```md
[図]: bad-fenced.png
```
~~~md
[図]: bad-tilde.png
~~~
    [図]: bad-indented.png

![図]
[図]: first.png
[図]: second.png
"""
    html, calls = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        f'const text = {json.dumps(text)}; const calls = [];\n'
        'const html = convertDoc(text,"spec",new Set(),{image:(alt,src)=>{calls.push([alt,src]);return "<img />";}}).body;\n'
        'console.log(JSON.stringify([html,calls]));'
    )
    assert calls == [["図", "first.png"]]
    assert all(name in html for name in ["bad-fenced.png", "bad-tilde.png", "bad-indented.png"])
    assert "second.png" not in html


def test_unresolved_reference_images_keep_alt_and_notify_without_changing_prose():
    text = "![説明][missing] ![省略][] ![短縮] [注意] [通常のリンク][target]\n\n[target]: https://example.test"
    html, missing, calls = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        f'const text = {json.dumps(text)}; const missing = [], calls = [];\n'
        'const html = convertDoc(text,"spec",new Set(),{image:(...args)=>calls.push(args),imageReferenceMissing:(...args)=>missing.push(args)}).body;\n'
        'console.log(JSON.stringify([html,missing,calls]));'
    )
    assert calls == []
    assert missing == [["説明", "missing"], ["省略", "省略"], ["短縮", "短縮"]]
    assert "説明 省略 短縮 [注意] 通常のリンク" in "".join(VisibleText(html).parts)


def test_reference_images_in_table_and_nested_list_and_code():
    text = """|用語|意味|
|---|---|
|図|![表][image]|

- 項目
  - ![子][image]

`![コード][image]`

[image]: figure.png
"""
    html, calls = node_eval(
        'import { convertDoc } from "./lib/doc-report.mjs";\n'
        f'const text = {json.dumps(text)}; const calls = [];\n'
        'const html = convertDoc(text,"spec",new Set(),{image:(alt,src)=>{calls.push([alt,src]);return "<img />";}}).body;\n'
        'console.log(JSON.stringify([html,calls]));'
    )
    assert calls == [["表", "figure.png"], ["子", "figure.png"]]
    assert '<code>![コード][image]</code>' in html
