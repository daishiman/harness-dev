"""validate-goal-output.py (C01) の保存前バリデーションテスト。

同梱 golden-sample-weekly.md を正本として PASS を確認し、各違反変異が FAIL する
ことを検証する (旧 validate-goal-output.sh の契約移植の等価性確認)。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "skills/run-ubm-goal-setting/scripts/validate-goal-output.py"
GOLDEN = PLUGIN_ROOT / "skills/run-ubm-goal-setting/assets/golden-sample-weekly.md"

WEEKLY_NAME = "UBM - 1-週報 2026-06-29〜2026-07-05.md"


def run(path: Path, type_: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(path), "--type", type_],
        capture_output=True, text=True,
    )


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def golden_text() -> str:
    return GOLDEN.read_text(encoding="utf-8")


def test_golden_sample_passes(tmp_path: Path, golden_text: str):
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout


def test_unexpanded_placeholder_fails(tmp_path: Path, golden_text: str):
    p = write(tmp_path, WEEKLY_NAME, golden_text + "\n残り: {{placeholder}}\n")
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "未展開テンプレート変数" in r.stdout


def test_zenkaku_digit_fails(tmp_path: Path, golden_text: str):
    p = write(tmp_path, WEEKLY_NAME, golden_text + "\n売上は１２３万円\n")
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "全角数字" in r.stdout


def test_missing_required_heading_fails(tmp_path: Path, golden_text: str):
    mutated = "\n".join(l for l in golden_text.split("\n") if not l.startswith("## 【今週の判断基準】"))
    p = write(tmp_path, WEEKLY_NAME, mutated)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "今週の判断基準" in r.stdout


def test_ng_expression_fails(tmp_path: Path, golden_text: str):
    lines = golden_text.split("\n")
    out = []
    for l in lines:
        out.append(l)
        if l.startswith("## 【今週の行動目標"):
            out.append("- [ ] 毎日頑張る")
    p = write(tmp_path, WEEKLY_NAME, "\n".join(out))
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "精神論" in r.stdout


def test_bad_filename_prefix_fails(tmp_path: Path, golden_text: str):
    p = write(tmp_path, "wrong-name.md", golden_text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "ファイル名" in r.stdout


def test_explicit_type_enforces_monthly_headings(tmp_path: Path, golden_text: str):
    # 週報内容を月報として検証 → 月報必須見出し欠落で FAIL (--type 明示契約の核)
    p = write(tmp_path, "UBM - 2-月報 2026-06-01〜2026-06-30.md", golden_text)
    r = run(p, "monthly")
    assert r.returncode == 1
    assert "1ヶ月の目標" in r.stdout


def test_missing_file_input_error(tmp_path: Path):
    r = run(tmp_path / "nope.md", "weekly")
    assert r.returncode == 1


def test_invalid_type_usage(tmp_path: Path, golden_text: str):
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(p), "--type", "yearly"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


def test_duplicate_heading_fails(tmp_path: Path, golden_text: str):
    # 既存見出しを複製 → 重複見出しで FAIL
    p = write(tmp_path, WEEKLY_NAME, golden_text + "\n## 【今週の判断基準】\n本文\n")
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "重複" in r.stdout
