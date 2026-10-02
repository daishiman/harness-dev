"""references/plain-language.md の「言い換え表」が assets/data/plain-language.json と同じであることを確かめる。

正本は JSON。md の表は読む人のための写しなので、片方だけ直すとずれる。
"""
from __future__ import annotations

import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = PLUGIN_ROOT / "assets" / "data" / "plain-language.json"
MD_PATH = PLUGIN_ROOT / "references" / "plain-language.md"


def _md_rows() -> list[tuple[str, str, str]]:
    """「## 言い換え表」の見出しから次の見出しまでにある表の行を (語, 言い換え, level) で返す。"""
    rows: list[tuple[str, str, str]] = []
    inside = False
    for line in MD_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == "## 言い換え表"
            continue
        if not inside or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] in ("語", "---") or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append((cells[0], cells[1], cells[2]))
    return rows


def _json_rows() -> list[tuple[str, str, str]]:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    return [(t["term"], t["say"], t["level"]) for t in data["terms"]]


def test_md_table_matches_json() -> None:
    assert _md_rows() == _json_rows()


def test_json_terms_are_unique_and_levels_known() -> None:
    rows = _json_rows()
    terms = [term for term, _, _ in rows]
    assert len(terms) == len(set(terms))
    assert {level for _, _, level in rows} <= {"error", "warn"}


def test_bare_log_is_not_listed() -> None:
    # 「ログ」だけだと ログイン や カタログ に当たるので、複合語でだけ載せる
    assert "ログ" not in [term for term, _, _ in _json_rows()]
