"""既定の見た目 (aidd-agent-kit の jp-web-design) を写しどおりに保つテスト。

- 配色の正本は assets/css/vendor/standard-color-system.css (キットの写し)。出所とハッシュは vendor/SOURCE.json。
- board-tokens.css はキットに無い名前だけを持ち、キットの名前を書き換えない。
- 部品 (common.css、まとめの雛形、ボードの雛形、お手本) が使う var() は、どれも定義がある。
- カード縁の色帯と自作アイコンを使わない (jp-web-design SKILL.md の恒久ルール)。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from conftest import PLUGIN_ROOT, node_eval, run_script

CSS = PLUGIN_ROOT / "assets" / "css"
VENDOR = CSS / "vendor" / "standard-color-system.css"
BOARD_TOKENS = CSS / "board-tokens.css"
TEMPLATES = PLUGIN_ROOT / "assets" / "templates"
EXAMPLE_SRC = PLUGIN_ROOT / "examples" / "sample-haisha" / "打ち合わせ資料" / "_src"
KIT = PLUGIN_ROOT.parents[1] / "aidd-agent-kit"
KIT_SKILL = KIT / "skills" / "jp-web-design"

COMMENT = re.compile(r"/\*[\s\S]*?\*/")
DEFINED = re.compile(r"(?:^|[;{\s\"'])(--[A-Za-z0-9_-]+)\s*:")
USED = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)")
FONT = re.compile(r"^\s*(--font-(?:ui|display|mono|num)):\s*([^;]+);", re.M)
# 太い上と左の線、内側の影で描いた線。色帯になりうるもの
BAND = re.compile(r"border-(?:left|top)\s*:\s*(\d+)px\s+solid\s+([^;\"}]+)|inset\s+(\d+)px\s+0\s+0\s+([^;,\"}]+)")
# 色帯にならない線: 中立の線 (引用の印など) と、キットが許す選択の印 (ナビの選択線、表の選択行の左線)
NEUTRAL_OR_SELECTED = {
    "var(--book-line-strong)", "var(--line-strong)", "var(--border-control)", "transparent",
    "var(--nav-selected-indicator)", "var(--table-selected-indicator)", "var(--book-nav-on-mark)",
}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def defined(css: str) -> list[str]:
    """scripts/lib/palette.mjs の definedNames と同じ拾い方 (注釈の中は見ない)。HTML の style 属性も拾う。"""
    return DEFINED.findall(COMMENT.sub("", css))


def parts() -> list[Path]:
    """var() を使う部品。お手本の tokens.css は組み立てた結果なので除く。"""
    return [
        CSS / "common.css",
        *sorted(TEMPLATES.glob("*.html")),
        *sorted(p for p in EXAMPLE_SRC.glob("*.html")),
    ]


def test_vendor_matches_source_record() -> None:
    rc, out, err = run_script("extract-kit-palette", "--verify")
    assert rc == 0, (out, err)
    source = json.loads(read(CSS / "vendor" / "SOURCE.json"))
    assert source["kit_path"] == "skills/jp-web-design/assets/standard/standard-color-system.css"


@pytest.mark.skipif(not KIT_SKILL.is_dir(), reason="リポジトリに aidd-agent-kit が無い")
def test_vendor_matches_kit() -> None:
    rc, out, err = run_script("extract-kit-palette", "--kit", str(KIT), "--check")
    assert rc == 0, (out, err)


def test_board_tokens_leave_kit_names_alone() -> None:
    board, vendor = defined(read(BOARD_TOKENS)), set(defined(read(VENDOR)))
    assert sorted(set(board) & vendor) == [], "キットと同じ名前はキットの値を使う (board-tokens.css で決めない)"
    assert len(board) == len(set(board))


@pytest.mark.skipif(not KIT_SKILL.is_dir(), reason="リポジトリに aidd-agent-kit が無い")
def test_font_stacks_match_kit() -> None:
    assert dict(FONT.findall(read(BOARD_TOKENS))) == dict(FONT.findall(read(KIT_SKILL / "SKILL.md")))


def test_every_var_is_defined() -> None:
    known = set(defined(read(BOARD_TOKENS))) | set(defined(read(VENDOR)))
    missing = sorted(
        f"{path.relative_to(PLUGIN_ROOT).as_posix()}: {name}"
        for path in parts()
        for name in set(USED.findall(read(path))) - known - set(defined(read(path)))
    )
    assert missing == []


def test_no_card_bands_or_custom_icons() -> None:
    bands, icons = [], []
    for path in parts():
        text = COMMENT.sub("", read(path))
        rel = path.relative_to(PLUGIN_ROOT).as_posix()
        for m in BAND.finditer(text):
            width, color = (m[1], m[2]) if m[1] else (m[3], m[4])
            if int(width) >= 2 and color.strip() not in NEUTRAL_OR_SELECTED:
                bands.append(f"{rel}: {m[0]}")
        if re.search(r"\.ico\b|class=\"[^\"]*\bico\b", text):
            icons.append(rel)
    assert bands == [], "分類と状態の色はチップ・点・進捗バーで示す"
    assert icons == [], "アイコンを自作しない"


def test_example_tokens_are_composed_standard() -> None:
    composed = node_eval(
        'import { composeStandardTokens } from "./lib/palette.mjs";\n'
        "console.log(JSON.stringify(composeStandardTokens()));"
    )
    assert read(EXAMPLE_SRC / "tokens.css") == composed.replace("\r\n", "\n")
    assert composed.index(read(BOARD_TOKENS).splitlines()[0]) < composed.index("@standard-meta")


def test_overlay_goes_last_and_unknown_names_are_reported(tmp_path: Path) -> None:
    overlay = tmp_path / "案件の配色.css"
    overlay.write_text(":root { --p-brand-indigo: #0B5E4A; --p-brnad-teal: #000; }\n", encoding="utf-8")
    out = node_eval(
        'import { composeTokens, readOverlay, unknownOverlayNames } from "./lib/palette.mjs";\n'
        f"const o = readOverlay({json.dumps(str(overlay))});\n"
        "const css = composeTokens(o);\n"
        "console.log(JSON.stringify({ css, unknown: unknownOverlayNames(o.css) }));"
    )
    css = out["css"]
    assert css.rstrip().endswith(read(overlay).rstrip()), "上書きは最後に置く (同じ名前は後が勝つ)"
    assert "3. 案件の上書き: 案件の配色.css (sha256 " in css
    assert out["unknown"] == ["--p-brnad-teal"]
