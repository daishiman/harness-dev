"""配色の単一正本 (ボードとまとめは役割だけを読む) と、利用者向け名称の回帰検査。標準カラーの出典との一致は test_palette.py。"""
from __future__ import annotations

import re
from conftest import PLUGIN_ROOT

CSS = PLUGIN_ROOT / "assets" / "css"
# 退いた名前は、このテスト自身にも字のままでは書かない。ひらがな・Hiragino (フォント) は別の言葉なので当てない
RETIRED = re.compile("\u5e73\u8cc0|\u3072\u3089\u304c(?!\u306a)|\u3072\u3089\u304c\u306a-design|hira" + "ga(?!na)", re.I)


def uncomment(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def declarations(text: str) -> dict[str, str]:
    return {
        name: " ".join(value.split()).lower()
        for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;{}]+);", uncomment(text))
    }


def test_book_and_boards_use_semantic_tokens_without_second_palette() -> None:
    tokens = declarations("\n".join((CSS / name).read_text(encoding="utf-8") for name in ("board-tokens.css", "vendor/standard-color-system.css")))
    consumers = [CSS / "common.css", PLUGIN_ROOT / "assets/templates/book.html"]
    consumers.extend(sorted((PLUGIN_ROOT / "assets/templates").glob("board-*.html")))
    for path in consumers:
        text = uncomment(path.read_text(encoding="utf-8"))
        styles = text if path.suffix == ".css" else "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I))
        assert not re.search(r"#[0-9a-f]{3,8}\b|\b(?:rgb|rgba|hsl|hsla)\s*\(", styles, re.I), path
        used = set(re.findall(r"var\(\s*(--[\w-]+)", styles))
        assert not any(name.startswith("--p-") for name in used), path
        assert used <= tokens.keys() | declarations(styles).keys(), (path, sorted(used - tokens.keys() - declarations(styles).keys()))
        if path.name == "book.html":
            assert "--book-" not in styles, "同じ役割の別名と色fallbackをまとめ側に増やさない"


def test_active_plugin_has_no_retired_design_names() -> None:
    # 過去の評価記録は走査しない。
    retired = RETIRED
    suffixes = {".md", ".mjs", ".json", ".yaml", ".yml", ".html", ".css", ".tmpl"}
    roots = [PLUGIN_ROOT / part for part in ("assets", "references", "scripts", "skills", "schemas", "agents", "examples")]
    paths = [PLUGIN_ROOT / "README.md", PLUGIN_ROOT / "setup.md"]
    for directory in roots:
        paths.extend(p for p in directory.rglob("*") if p.is_file() and p.suffix in suffixes and "_check" not in p.parts)
    found = []
    for path in paths:
        if retired.search(path.relative_to(PLUGIN_ROOT).as_posix()) or retired.search(path.read_text(encoding="utf-8")):
            found.append(path.relative_to(PLUGIN_ROOT).as_posix())
    assert found == []
