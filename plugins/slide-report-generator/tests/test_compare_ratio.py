"""SR-4-03 / V-001 の実行体（validate-compare-ratio.mjs）を固定する。

V-001 は 2026-08-14 まで、どの工程にも判定する実行体が無かった。この検査器が
その実行体になる。ここで固定するのは 3 点。

  1. 検査器が持つ 48% / 4% の写しが、正本（spec-registry.md の SR-4-03 行）から
     ずれていないこと。検査器に数値を書く以上、写しであることを機械で保証しないと
     検査器そのものが第 2 の正本になる
  2. 違反を検出できること（陰性対照）と、正しい deck を通すこと（陽性対照）
  3. 別クラス（code-compare-container / compare-panel--before）を巻き込まないこと。
     巻き込むと違反が水増しされ、読まれない警告になる
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CHECKER = PLUGIN_ROOT / "scripts" / "validate-compare-ratio.mjs"
REGISTRY = PLUGIN_ROOT / "references" / "spec-registry.md"


def _run(html: str, tmp_path: Path) -> subprocess.CompletedProcess:
    target = tmp_path / "deck.html"
    target.write_text(html, encoding="utf-8")
    return subprocess.run(
        ["node", str(CHECKER), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_expected_values_match_the_registry() -> None:
    """検査器の 48% / 4% は正本の写しである。"""
    row = next(
        line for line in REGISTRY.read_text(encoding="utf-8").splitlines()
        if line.startswith("| SR-4-03 ")
    )
    assert "48%" in row and "4%" in row, f"正本の SR-4-03 行から比率が消えている: {row}"

    source = CHECKER.read_text(encoding="utf-8")
    expect = re.search(r'const EXPECT = \{ gap: "([^"]+)", width: "([^"]+)" \}', source)
    assert expect, "EXPECT の書き方が変わった"
    gap, width = expect.group(1), expect.group(2)
    assert gap == "4%" and width == "48%", f"検査器の写しが正本とずれている: gap={gap} width={width}"


def test_self_test_passes() -> None:
    """自己診断が通ること。落ちていたら以下の対照も信用できない。"""
    got = subprocess.run(
        ["node", str(CHECKER), "--self-test"], capture_output=True, text=True, check=False
    )
    assert got.returncode == 0, got.stdout + got.stderr


def test_correct_ratio_passes(tmp_path: Path) -> None:
    """陽性対照。48/4/48 の deck は通る（常に赤い検査器と見分ける）。"""
    html = "<style>.compare-container { display: flex; gap: 4%; } .compare-panel { width: 48%; }</style>"
    got = _run(html, tmp_path)
    assert got.returncode == 0, got.stdout + got.stderr
    assert "違反なし" in got.stdout


def test_wrong_gap_fails(tmp_path: Path) -> None:
    """陰性対照。gap が rem で書かれていれば落ちる（LLM 経路で実際に出ている形）。"""
    html = "<style>.compare-container { display: flex; gap: 2rem; } .compare-panel { width: 48%; }</style>"
    got = _run(html, tmp_path)
    assert got.returncode == 1, got.stdout + got.stderr
    assert "2rem" in got.stdout


def test_missing_declaration_fails(tmp_path: Path) -> None:
    """比較レイアウトを使っていて比率の宣言が無いなら落ちる。

    既定値（gap 0 / width auto）で描かれるので 48/4/48 にはならない。
    「書いていないから検査対象なし」で緑にすると、規則が最も破られている形を
    見逃す（実測 27 deck 中 25 deck が panel の width を宣言していない）。
    """
    html = '<div class="compare-container"><div class="compare-panel">左</div></div>'
    got = _run(html, tmp_path)
    assert got.returncode == 1, got.stdout + got.stderr
    assert "宣言なし" in got.stdout


def test_unrelated_classes_are_not_dragged_in(tmp_path: Path) -> None:
    """別クラスを巻き込まない。

    - `code-compare-container` は別クラス（SR-4-03 の対象でない）
    - `.compare-panel h3 { gap: 1rem }` は子孫規則で、比較レイアウトの隙間ではない
    - `.compare-panel--before` は別クラス
    どれも実在の deck に出ている形で、巻き込むと違反が水増しされる。
    """
    html = (
        "<style>.compare-container { gap: 4%; } .compare-panel { width: 48%; }"
        " .compare-panel h3 { gap: 1rem; } .compare-panel--before { width: 30%; }</style>"
        '<div class="code-compare-container"><div class="code-compare-column">x</div></div>'
    )
    got = _run(html, tmp_path)
    assert got.returncode == 0, got.stdout + got.stderr
