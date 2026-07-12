"""check-upstream-pins.py の機能テスト (島D (iii): 引用の鮮度層)。

plugin 境界を跨ぐ契約級引用の sha256 pin 台帳 (references/upstream-pins.json) を検証する
決定論ゲートの被覆。drift/消失/standalone の検知ロジックは --self-test が内部 fixture で
固定するため、本テストは (a) self-test と実台帳の本走が CI cwd から exit0 (b) 台帳形式
違反と drift の exit code 契約、を薄く縛る。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_SKILL_DIR = Path(__file__).resolve().parents[1]
_SCRIPT = _SKILL_DIR / "scripts" / "check-upstream-pins.py"


def _run(*args: str) -> subprocess.CompletedProcess:
    """CI と同じ skill dir cwd から subprocess 実行する (cwd 依存の回帰も同時に検査)。"""
    return subprocess.run(
        [sys.executable, str(_SCRIPT), *args],
        cwd=str(_SKILL_DIR),
        capture_output=True,
        text=True,
    )


def test_self_test_green():
    """--self-test (drift/消失/一致/standalone の4象限内部 fixture) が exit0。"""
    result = _run("--self-test")
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_main_real_ledger_green():
    """実台帳 references/upstream-pins.json の本走が exit0 (in-repo で全 pin sha256 一致)。

    fail したら pin 対象 upstream が変質している — エラーメッセージの matrix_rows を再監査し、
    引用の追従修正と pin bump を同一変更で行うこと (テスト側の緩和は禁止)。
    """
    result = _run()
    assert result.returncode == 0, f"upstream pin drift (引用先の変質):\n{result.stderr}"
    assert "OK" in result.stdout


def test_main_missing_ledger_exit2(tmp_path):
    """台帳欠落は usage/台帳エラー (exit 2)。"""
    result = _run("--pins", str(tmp_path / "no-such.json"))
    assert result.returncode == 2
    assert "見つからない" in result.stderr


def test_main_drift_ledger_exit1(tmp_path, upstream_pins):
    """sha256 不一致 pin を持つ台帳は fail-closed (exit 1) + matrix_rows 再監査指示。"""
    ledger = tmp_path / "pins.json"
    ledger.write_text(json.dumps({"pins": [{
        # 実在ファイルを指し既知の壊れ sha を焼く (in-repo mode で必ず drift)
        "path": "plugins/plugin-dev-planner/skills/run-plugin-dev-plan/scripts/specfm.py",
        "sha256": "0" * 64,
        "verified_at": "2026-07-02",
        "matrix_rows": ["A1"],
    }]}, ensure_ascii=False), encoding="utf-8")
    result = _run("--pins", str(ledger))
    assert result.returncode == 1
    assert "pin drift" in result.stderr and "A1" in result.stderr


def test_ledger_shape_validation(tmp_path, upstream_pins):
    """load_ledger が必須キー欠落・matrix_rows 型不正・pins 空を検出する (module 単位)。"""
    bad = tmp_path / "pins.json"
    bad.write_text(json.dumps({"pins": [
        {"path": "x", "sha256": "y"},  # verified_at / matrix_rows 欠落
        {"path": "z", "sha256": "w", "verified_at": "2026-07-02", "matrix_rows": "A1"},  # list でない
    ]}), encoding="utf-8")
    _, errs = upstream_pins.load_ledger(bad)
    assert any("verified_at" in e for e in errs)
    assert any("matrix_rows" in e for e in errs)
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"pins": []}), encoding="utf-8")
    _, errs = upstream_pins.load_ledger(empty)
    assert any("pins[]" in e for e in errs)


def test_check_pins_standalone_discloses_verified_at(upstream_pins):
    """standalone (root=None) は fail でなく verified_at 開示 + exit0 (fail-open の明示)。"""
    pin = {"path": "doc/x.md", "sha256": "0" * 64, "verified_at": "2026-07-02", "matrix_rows": ["C1"]}
    code, errs, notes = upstream_pins.check_pins([pin], None)
    assert code == 0 and errs == []
    assert any("verified_at=2026-07-02" in n for n in notes)


def test_real_ledger_pins_cite_existing_matrix_rows(upstream_pins):
    """実台帳の matrix_rows が reflection.md の 46 行マトリクスに実在する行 ID を指す
    (pin drift 時の再監査指示が dead row を指さない)。"""
    import re

    ledger_path = _SKILL_DIR / "references" / "upstream-pins.json"
    pins, errs = upstream_pins.load_ledger(ledger_path)
    assert errs == [], errs
    reflection = _SKILL_DIR / "references" / "harness-creator-spec-reflection.md"
    row_ids = set(re.findall(r"^\|\s*([A-G]\d{1,2})\s*\|", reflection.read_text(encoding="utf-8"), re.M))
    assert row_ids, "reflection.md からマトリクス行 ID を抽出できない"
    missing = sorted({r for p in pins for r in p["matrix_rows"]} - row_ids)
    assert not missing, f"upstream-pins.json の matrix_rows がマトリクスに実在しない: {missing}"
