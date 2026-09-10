"""V_DEFINITIONS の desc を正本から切り詰めないことを固定する。

desc はレポートと未検査ブロックへそのまま出るので、切り詰めた写しが第 2 の正本
として読まれる。実例: SR-4-08「図解はインライン SVG2 で描画」の空白を落として
"図解はインラインSVG2描画" と書いた結果、「SVG」「2 描画」と切れて数量に読まれ、
実行体の無い規則として保留され続けた（実際は SVG 仕様のバージョン 2 のこと）。

この種の誤読は「英字の直後に数字」で機械的に見つかる。確立した綴り（HTML 要素の
h2、紙サイズの A4）だけを許可し、それ以外を落とす。新しい許可語を足すときは、
それが「正本にもその綴りで書かれている」ことを確かめてから足すこと。
"""

from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = PLUGIN_ROOT / "vendor" / "scripts" / "validate-structure.js"

DESC = re.compile(r'"(V-\d+)":\s*\{[^}]*desc:\s*"([^"]*)"')
LETTER_THEN_DIGIT = re.compile(r"[A-Za-z]\d")

# 正本にもこの綴りで書かれているもの。
ALLOWED = ("h2", "h3", "A4")


def _descs() -> list[tuple[str, str]]:
    source = VALIDATOR.read_text(encoding="utf-8")
    found = DESC.findall(source)
    assert len(found) > 30, f"desc がほとんど取れていない: {len(found)} 件"
    return found


def test_desc_has_no_unspaced_letter_digit() -> None:
    offenders = []
    for vid, desc in _descs():
        for hit in LETTER_THEN_DIGIT.findall(desc):
            if any(hit in allowed for allowed in ALLOWED):
                continue
            offenders.append((vid, desc, hit))
    assert not offenders, (
        "desc に「英字の直後に数字」がある。正本の空白を落としていないか確認すること"
        f"（SVG2 -> 「2 描画」の誤読の再発）: {offenders}"
    )


def test_v029_desc_is_spaced() -> None:
    """陰性対照だけだと「常に通る実装」と区別できないので、直した実例を名指しで固定する。"""
    descs = dict(_descs())
    assert "SVG2" not in descs["V-029"], "版番号つきの旧 desc へ戻さない"
    assert "svg" in descs["V-029"]


def test_guard_catches_the_original_defect() -> None:
    """陽性対照。壊れた綴りを与えたら実際に検出できること。"""
    hits = [h for h in LETTER_THEN_DIGIT.findall("図解はインラインSVG2描画")
            if not any(h in a for a in ALLOWED)]
    assert hits == ["G2"]
