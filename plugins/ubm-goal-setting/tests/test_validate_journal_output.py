"""validate-journal-output.py の保存前バリデーションテスト。

同梱 golden-sample.md を正本として PASS を確認し、骨格欠落・空セクション・日付不一致・
番号不一致・未置換プレースホルダの各変異が FAIL することを検証する。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "skills/run-ubm-journal/scripts/validate-journal-output.py"
GOLDEN = PLUGIN_ROOT / "skills/run-ubm-journal/assets/golden-sample.md"

GOLDEN_NAME = "2026-08-18.md"
GOLDEN_NUMBER = 389
GOLDEN_DATE = "2026-08-18"


def run(path: Path, number: int | None = None, date: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(VALIDATE), "--file", str(path)]
    if number is not None:
        cmd += ["--expected-number", str(number)]
    if date is not None:
        cmd += ["--expected-date", date]
    return subprocess.run(cmd, capture_output=True, text=True)


def write(tmp_path: Path, text: str, name: str = GOLDEN_NAME) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def golden() -> str:
    return GOLDEN.read_text(encoding="utf-8")


def test_golden_sample_passes(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout


def test_bad_filename_fails(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden, name="journal.md"))
    assert proc.returncode == 1
    assert "F01" in proc.stdout


def test_heading_date_mismatch_fails(tmp_path: Path, golden: str):
    text = golden.replace("ジャーナル（2026-08-18）", "ジャーナル（2026-08-17）")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "F03" in proc.stdout


def test_number_mismatch_fails(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden), 400, GOLDEN_DATE)
    assert proc.returncode == 1
    assert "F04" in proc.stdout


def test_missing_heading_fails(tmp_path: Path, golden: str):
    text = golden.replace("# No.389 - ジャーナル（2026-08-18）", "# ジャーナル")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "F02" in proc.stdout


def test_missing_required_section_fails(tmp_path: Path, golden: str):
    text = golden.replace("## 感謝", "## ありがとう")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "S01" in proc.stdout


def test_out_of_order_section_fails(tmp_path: Path, golden: str):
    # 【禁止事項】を【タスク】より後ろへ移すと順序違反
    text = golden.replace("## 【禁止事項】", "## __TMP__").replace("## 【タスク】", "## 【禁止事項】")
    text = text.replace("## __TMP__", "## 【タスク】")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "S01" in proc.stdout


def test_goal_missing_period_field_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 期間：2026-07-27〜2026-08-31\n", "")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G01" in proc.stdout


def test_goal_bad_period_format_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 期間：2026-07-27〜2026-08-31", "- 期間：7月末から8月末まで")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G02" in proc.stdout


def test_empty_gratitude_fails(tmp_path: Path, golden: str):
    start = golden.index("## 感謝")
    end = golden.index("## 【禁止事項】")
    text = golden[:start] + "## 感謝\n\n" + golden[end:]
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "C02" in proc.stdout


def test_task_without_category_fails(tmp_path: Path, golden: str):
    text = golden.replace("### 【個人向けAIコンサル（生命線）】", "").replace("### 【記録・習慣】", "")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "C04" in proc.stdout


def test_empty_journal_subsection_fails(tmp_path: Path, golden: str):
    # 【行動のジャーナル】の「現状を確認する」小節を丸ごと空にする
    start = golden.index("### 現状を確認する")
    end = golden.index("### 効果性を評価する")
    text = golden[:start] + "### 現状を確認する\n\n" + golden[end:]
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "J02" in proc.stdout


def test_missing_journal_subsection_fails(tmp_path: Path, golden: str):
    text = golden.replace("### 効果性を評価する", "### 振り返り", 1)
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "J01" in proc.stdout or "S01" in proc.stdout


def test_missing_phase_block_fails(tmp_path: Path, golden: str):
    text = golden.replace("## ◇【10→100】", "## ◇【その他】")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "P01" in proc.stdout


def test_unreplaced_placeholder_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 北原さん: 8/16のUBM兵庫支部会", "- [名前]: [感謝の内容] 8/16のUBM兵庫支部会")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "X01" in proc.stdout


def test_missing_file_fails_closed(tmp_path: Path):
    proc = run(tmp_path / "nope.md")
    assert proc.returncode == 2


# --- H01: 毎日固定の習慣がヒアリング・記録されたか -------------------------

HABITS = json.loads(
    (PLUGIN_ROOT / "skills/run-ubm-journal/references/daily-habits.json").read_text(
        encoding="utf-8"
    )
)["habits"]


def test_golden_sample_covers_every_daily_habit(golden: str):
    """見本が6習慣すべてに痕跡を持つ（H01 の基準線が実在することの担保）。"""
    missing = [h["id"] for h in HABITS if not any(k in golden for k in h["keywords"])]
    assert not missing, f"golden-sample に痕跡が無い習慣: {missing}"


@pytest.mark.parametrize("habit", HABITS, ids=[h["id"] for h in HABITS])
def test_missing_daily_habit_record_fails(tmp_path: Path, golden: str, habit: dict):
    """各習慣について、その痕跡を全て消すと H01 で FAIL する。"""
    text = golden
    for kw in habit["keywords"]:
        text = text.replace(kw, "＿")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "H01" in proc.stdout
    assert habit["label"] in proc.stdout


def test_daily_habits_json_is_wellformed():
    """正本の必須キーを固定する（キー名変更でスクリプト側が黙って壊れるのを防ぐ）。"""
    assert HABITS, "habits が空"
    for h in HABITS:
        for key in ("id", "label", "natural_question", "target_section", "unmet_signal", "keywords"):
            assert h.get(key), f"{h.get('id')}: {key} が空"
        assert isinstance(h["keywords"], list) and h["keywords"], f"{h['id']}: keywords が空"
