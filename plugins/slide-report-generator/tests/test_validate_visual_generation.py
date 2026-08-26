"""生成則の検査器 (validate-visual-generation.py) を固定する。

この検査器の値は visual-generation-rules.md から実行時に読む。読めなくなったとき
既定値へ落ちて緑になる、写し (json ブロック) と正本 (散文) がズレたまま判定する、
という 2 つの壊れ方はどちらも「検査しているつもりで何も見ていない」状態になる。
落ちること自体をここで踏んでおく。
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = PLUGIN_ROOT / "scripts" / "validate-visual-generation.py"
RULES = PLUGIN_ROOT / "skills" / "run-slide-report-generate" / "references" / "visual-generation-rules.md"

# 規約どおりに組んだ面。第 1 位が一意 (6rem w700 反転) で 2 位を 1.60 以上引き離し、
# 役割 3 種の隣接比も満たし、反転ブロックがちょうど 1 個ある。
COMPLIANT_DECK = """<!doctype html><html><head><style>
:root { --fs-lead: 6rem; --fs-body: 2rem; }
.slider__item { background: #F7F6F3; }
.lead { font-size: var(--fs-lead); font-weight: 700; }
.body { font-size: var(--fs-body); font-weight: 400; }
.label { font-size: 1.6rem; font-weight: 400; }
.accent { background-color: #141412; color: #F7F6F3; }
</style></head><body>
<div class="slider__item">
  <div class="accent"><p class="lead" data-role="lead">見出し</p></div>
  <p class="body" data-role="body">本文である。</p>
  <p class="label" data-role="label">注記</p>
</div></body></html>"""

# 階層が無い面。同じ大きさ・同じ太さの見出しが 2 つあり、役割宣言も反転も無い。
# 既存 deck 54 本すべてがこの形で不合格になっている。
FLAT_DECK = """<!doctype html><html><head><style>
.slider__item { background: #F7F6F3; }
.h { font-size: 3rem; font-weight: 700; }
</style></head><body>
<div class="slider__item"><p class="h">見出しA</p><p class="h">見出しB</p></div>
</body></html>"""


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *args], capture_output=True, text=True, check=False
    )


def _deck(tmp_path: Path, name: str, html: str) -> Path:
    deck = tmp_path / name
    deck.mkdir(parents=True, exist_ok=True)
    (deck / "index.html").write_text(html, encoding="utf-8")
    return deck


def test_self_test_passes() -> None:
    """検査器そのものの自己テスト。緩めた閾値では満点が取れない作りにしてある。"""
    got = _run("--self-test")
    assert got.returncode == 0, got.stdout + got.stderr
    assert "PASS" in got.stdout
    assert "由来 json" in got.stdout  # 機械可読ブロック経由で読めている


def test_compliant_face_passes_and_flat_face_fails(tmp_path: Path) -> None:
    """陽性対照つき。常に赤い検査は「何を見ているか」を保証しない。"""
    ok = _run(str(_deck(tmp_path, "ok", COMPLIANT_DECK)), "--json")
    assert ok.returncode == 0, ok.stdout + ok.stderr

    flat = _run(str(_deck(tmp_path, "flat", FLAT_DECK)), "--json")
    assert flat.returncode == 1
    codes = {f["code"] for f in json.loads(flat.stdout)["decks"][0]["findings"]}
    assert {"VG01", "VG03", "VG06"} <= codes  # 同点・役割未宣言・反転なし


def test_rules_json_and_prose_must_agree(tmp_path: Path) -> None:
    """写し (json) と正本 (散文) がズレたら判定せずに落ちる。

    ズレを許すと json が第 2 の正本になり、「どちらが正しいか分からない」状態が
    再発する。落ちる先は exit 3 (判定不能) であって 0 ではない。
    """
    source = RULES.read_text(encoding="utf-8")
    assert '"intensity_ratio_min": 1.60' in source, "写しの錨が変わったらこの検査を追随させる"
    deck = str(_deck(tmp_path, "ok", COMPLIANT_DECK))

    skewed = tmp_path / "skewed.md"
    skewed.write_text(source.replace('"intensity_ratio_min": 1.60', '"intensity_ratio_min": 1.20'),
                      encoding="utf-8")
    got = _run("--rules", str(skewed), deck)
    assert got.returncode == 3
    assert "食い違う" in got.stderr
    assert "intensity_ratio_min" in got.stderr

    # 陽性対照。ズラしていない写しなら通常どおり判定へ進む。
    intact = tmp_path / "intact.md"
    intact.write_text(source, encoding="utf-8")
    got = _run("--rules", str(intact), deck)
    assert got.returncode == 0, got.stdout + got.stderr


def test_rules_unreadable_is_fail_closed(tmp_path: Path) -> None:
    """散文の錨が外れた / 規約が無い場合に、直値の既定値で走り出さない。"""
    deck = str(_deck(tmp_path, "ok", COMPLIANT_DECK))

    got = _run("--rules", str(tmp_path / "no-such-file.md"), deck)
    assert got.returncode == 3
    assert "読めない" in got.stderr

    broken = tmp_path / "broken.md"
    source = RULES.read_text(encoding="utf-8")
    broken.write_text(re.sub(r"```json\s*\n.*?\n```", "", source, flags=re.S)
                      .replace("W: font-weight", "W: 太さの係数"), encoding="utf-8")
    got = _run("--rules", str(broken), deck)
    assert got.returncode == 3
    assert "抽出できない" in got.stderr


def test_rules_json_block_is_singular() -> None:
    """写しは 1 つだけ。2 つ目の json ブロックは 2 つ目の正本になる。"""
    assert len(re.findall(r"```json", RULES.read_text(encoding="utf-8"))) == 1
