"""正本と写しをつなぐテスト。1 組 1 行で、どれが正本かを書く。

- 文書の見出しと表の列: 正本は assets/templates/*.md.tmpl と validate-briefing-docs.mjs の定数。写しは references/document-structure.md。
- 型の表示名: 正本は scripts/lib/briefing-files.mjs の TYPE_LABEL。写しは references/page-patterns.md の型の見出し。
- 検査のコード名: 正本は scripts/**/*.mjs。写しは references・agents・skills/*/references の md。
- ボードの CSS: 正本は assets/css (tokens.css は scripts/lib/palette.mjs が組み立てる)。写しは examples/sample-haisha/打ち合わせ資料/_src。
- ボードの大きさ: 正本は assets/data/quality-thresholds.json の board。写しは assets/css/common.css の .board。
- お手本の文書: 正本は validate-briefing-docs.mjs の検査。examples/sample-haisha はそれを通る。
- briefing.json の項目: 正本は schemas/briefing.schema.json (tests/test_briefing_schema.py が見る)。
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from conftest import PLUGIN_ROOT, SCRIPTS, node_eval, run_script

REFS = PLUGIN_ROOT / "references"
TEMPLATES = PLUGIN_ROOT / "assets" / "templates"
CSS = PLUGIN_ROOT / "assets" / "css"
EXAMPLE = PLUGIN_ROOT / "examples" / "sample-haisha"
EXAMPLE_OUT = EXAMPLE / "打ち合わせ資料"

HEADING = re.compile(r"^(#{1,3}) (.+?)\s*$", re.M)
SEPARATOR = re.compile(r"^\|\s*:?-{3,}")
# md に書いたコード名 (PNG-SIZE の形)。日付の書き方 YYYY-MM-DD はコード名ではない
CODE_NAME = re.compile(r"(?<![A-Za-z0-9_./-])([A-Z][A-Z0-9]+(?:-[A-Z][A-Z0-9]+)+)(?![A-Za-z0-9_-])")
NOT_CODES = {"YYYY-MM-DD"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def headings(text: str) -> list[tuple[int, str]]:
    """見出し (# から ### まで)。雛形の {{TITLE}} は document-structure.md の <タイトル> にそろえる。"""
    return [(len(m[1]), m[2].replace("{{TITLE}}", "<タイトル>")) for m in HEADING.finditer(text)]


def titles(items: list[tuple[int, str]], level: int) -> list[str]:
    return [title for lv, title in items if lv == level]


def cells(row: str) -> list[str]:
    """表の 1 行を列に分ける。\\| は列の区切りにしない。"""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


def md_tables(text: str) -> list[tuple[list[str], list[str]]]:
    """表の (見出し行, 1 列目) の一覧。"""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines[:-1]):
        if line.startswith("|") and SEPARATOR.match(lines[i + 1]):
            first = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                first.append(cells(row)[0])
            found.append((cells(line), first))
    return found


def doc_section(text: str, name: str) -> str:
    """document-structure.md の「## <文書名>」の節。コードブロックの中の ## では切らない。"""
    lines = text.splitlines()
    start = lines.index(f"## {name}") + 1
    fence = False
    for end in range(start, len(lines)):
        fence ^= lines[end].startswith("```")
        if not fence and lines[end].startswith("## "):
            return "\n".join(lines[start:end])
    return "\n".join(lines[start:])


def test_document_headings_and_tables() -> None:
    r = node_eval(
        'import * as validate from "./validate-briefing-docs.mjs";\n'
        'import { DOC_TEMPLATES } from "./build-briefing-scaffold.mjs";\n'
        "console.log(JSON.stringify({ ...validate, DOC_TEMPLATES }));"
    )
    expected = {
        "hearing.md.tmpl": (r["HEARING_H2"], []),
        "requirements.md.tmpl": (r["REQ_H2"], [h for hs in r["REQ_H3"].values() for h in hs]),
        "spec.md.tmpl": (r["SPEC_H2"], r["SPEC_RULES_H3"] + r["SPEC_OPS_H3"]),
        "changes.md.tmpl": ([], []),
    }
    validate_tables = [r["HEARING_TABLE"], *r["REQ_TABLES"].values(), r["SPEC_SCREEN_TABLE"], r["SPEC_ITEM_TABLE"],
                       r["SPEC_OPS_TABLE"], r["SPEC_DATA_TABLE"], r["SPEC_RULE_TABLE"], r["SPEC_PLATFORM_TABLE"],
                       r["SPEC_ROLE_TABLE"], r["CHANGES_TABLE"]]
    structure = read(REFS / "document-structure.md")
    assert sorted(expected) == sorted(tmpl for tmpl, _ in r["DOC_TEMPLATES"])
    for tmpl, doc in r["DOC_TEMPLATES"]:
        text = read(TEMPLATES / tmpl)
        tmpl_heads = headings(text)
        h2, h3 = expected[tmpl]
        assert (titles(tmpl_heads, 2), titles(tmpl_heads, 3)) == (h2, h3), f"{tmpl} と validate の見出し"
        for header, _ in md_tables(text):
            assert header in validate_tables, f"{tmpl} の表 {header} を validate が知らない"
        # document-structure.md: 1 行目の形と、骨組みの見出し (書く人が埋める <...> の見出しは除く)
        section = doc_section(structure, doc)
        title = f"# {titles(tmpl_heads, 1)[0]}"
        assert title in section, f"document-structure.md の「## {doc}」に {title} がありません"
        if not h2:
            continue
        block = re.search(r"```markdown\n(.*?)```", section, re.S)
        assert block, f"document-structure.md の「## {doc}」に骨組みがありません"
        skeleton = [(lv, t) for lv, t in headings(block[1]) if lv == 1 or "<" not in t]
        assert skeleton == tmpl_heads, f"document-structure.md の「## {doc}」と {tmpl} の見出し"
    written = [cells(span.replace("\\|", "|")) for span in re.findall(r"`(\\?\|[^`]*\|)`", structure)]
    written += [header for header, _ in md_tables(structure)]
    for header in validate_tables:
        assert header in written, f"document-structure.md に表 {header} がありません"
    spec_tables = md_tables(read(TEMPLATES / "spec.md.tmpl"))
    assert [first for header, first in spec_tables if header == r["SPEC_PLATFORM_TABLE"]] == [r["SPEC_PLATFORM_ITEMS"]]


def test_type_labels_match_page_patterns() -> None:
    labels = node_eval(
        'import { TYPE_LABEL } from "./lib/briefing-files.mjs";\n'
        "console.log(JSON.stringify(TYPE_LABEL));"
    )
    found = re.findall(r"^### (\S+) (.+?)\s*$", read(REFS / "page-patterns.md"), re.M)
    assert [(t, label) for t, label in found if t in labels] == list(labels.items())


def test_code_names_in_docs_exist_in_scripts() -> None:
    scripts = "\n".join(read(p) for p in sorted(SCRIPTS.rglob("*.mjs")))
    defined = set(re.findall(r"""["']([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)["']""", scripts))
    docs = [*REFS.glob("*.md"), *(PLUGIN_ROOT / "agents").glob("*.md"), *(PLUGIN_ROOT / "skills").glob("*/references/*.md")]
    unknown = sorted(
        f"{doc.relative_to(PLUGIN_ROOT).as_posix()}: {code}"
        for doc in docs
        for code in set(CODE_NAME.findall(read(doc))) - NOT_CODES - defined
    )
    assert unknown == []


def test_example_css_and_board_size() -> None:
    assert json.loads(read(EXAMPLE_OUT / "briefing.json"))["palette"] == "standard", "お手本は既定の配色で作る"
    assert (EXAMPLE_OUT / "_src" / "common.css").read_bytes() == (CSS / "common.css").read_bytes()
    # tokens.css が組み立てどおりかは tests/test_palette.py が見る
    # render-board-png.mjs は描くたびに大きさを確かめる。ここではブラウザが無くても 1 回だけ見る
    board = json.loads(read(PLUGIN_ROOT / "assets" / "data" / "quality-thresholds.json"))["board"]
    rule = re.search(r"^\.board\s*\{([^}]*)\}", read(CSS / "common.css"), re.M)[1]
    size = [int(re.search(rf"(?<![\w-]){key}:\s*(\d+)px", rule)[1]) for key in ("width", "height")]
    assert size == [board["width"], board["height"]]


def test_example_passes_validate(tmp_path: Path) -> None:
    copy = tmp_path / EXAMPLE.name
    shutil.copytree(EXAMPLE, copy)  # validate は _check/docs.json を書くので、お手本そのものには流さない
    rc, out, err = run_script("validate-briefing-docs", "--dir", str(copy / EXAMPLE_OUT.name), "--stage", "all")
    assert rc == 0, (out, err)
    assert out["warnings"] == [], "お手本は warn も 0 にする"
    assert json.loads(read(EXAMPLE_OUT / "briefing.json"))["data_policy"] == "masked", "お手本は架空なので伏せる側で作る"
