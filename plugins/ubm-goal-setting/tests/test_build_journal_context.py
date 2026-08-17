"""build-journal-context.py の文脈解決テスト。

通し番号の +1 採番・同日再生成での番号維持・残日数計算・週報からの引き継ぎ・
期間ズレ検出の warnings を、合成 vault で検証する。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "skills/run-ubm-journal/scripts/build-journal-context.py"

JOURNAL_TEMPLATE = """---
tags:
  - review
---
# 人生の究極の目標

![[人生の究極の目的#🎯 究極の人生の目的]]

# No.{number} - ジャーナル（{date}）

## 人生の究極目的

- AIを思い通りに使いこなし、自分の時間を有益に過ごした人財を世界一輩出した。

## 目標

### 1年目標

- 期間：2025-06-25〜2026-06-29
- 残り：0日（期間終了）
- 目標：1年目標の本文。

### 3ヶ月目標

- 期間：2026-06-29〜2026-08-30
- 残り：12日
- 目標：3ヶ月目標の本文。

### 1ヶ月目標

- 期間：2026-07-27〜2026-08-31
- 残り：13日
- 目標：1ヶ月目標の本文。

### 1週間目標

- 期間：2026-08-10〜2026-08-16
- 残り：0日
- 目標：1週間目標の本文。

## 感謝

- 北原さん: ありがとうございました。

## 【禁止事項】

- 管理する場所を3つから増やさない
- 無償の相談対応を新規で受けない

## 【タスク】

### 【記録・習慣】

- 散歩の直後にジャーナルを作成する

## 【行動のジャーナル】

### 現状を確認する

- 事実。

### 効果性を評価する

- 解釈。

### 更に良くする方法はないか

- 打ち手。

## 【時間のジャーナル】

### 現状を確認する

- 事実。

### 効果性を評価する

- 解釈。

### 更に良くする方法はないか

- 打ち手。

## 【お金のジャーナル】

### 現状を確認する

- 事実。

### 効果性を評価する

- 解釈。

### 更に良くする方法はないか

- 打ち手。

# フェーズ別 課題チェックシート

## ◇【0→1】

- [x] セーフティーゾーンは整っていますか？

## ◇【1→10】

- [ ] マニュアル化はできていますか？

## ◇【10→100】

- [ ] フロント活動を活性化させ集客人数を増やせていますか？
"""

WEEKLY_REPORT = """## 【1週間の目標】2026-08-17〜2026-08-23
今週は前倒しの週。

---

## 【今週の最重要数字】
- [ ] 8/20 青木さんへ書面を提示する

---

## 【今週の大きな到達ライン】

- [ ] 8/18（月）：
	- [ ] 依頼アプリ制作を30分×1本で進める
	- [x] 散歩の直後にジャーナルを作成
- [ ] 8/19（火）：
	- [ ] 8/27勉強会のチラシを作成する

---

## 【今週の売上目標】
250,000

## 【今週の売上以外の成果目標】
- 青木さん：書面提示への返答1件　期日8/20

---

## 【習慣目標（仕組みで動く土台）】

### 1. Gridノートの直後に記録する
- [ ] Gridノートを閉じる前にObsidian Dailyを3行書く（毎日）

### 2. 30分単位で切り替える
- [ ] タスクは30分でセットし、鳴ったら次へ移る（毎日）

---

## 【今週の判断基準】
迷ったら「依頼アプリの稼働に効く行動か」で選ぶ。

---
"""

MONTHLY_REPORT = """## 【1ヶ月の目標】2026-08-01〜2026-08-31
8月の本文。
"""


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    daily = tmp_path / "02_Configs" / "Daily"
    goals = tmp_path / "05_Project" / "UBM" / "目標設定"
    daily.mkdir(parents=True)
    goals.mkdir(parents=True)
    (daily / "2026-08-16.md").write_text(
        JOURNAL_TEMPLATE.format(number=387, date="2026-08-16"), encoding="utf-8"
    )
    (daily / "2026-08-17.md").write_text(
        JOURNAL_TEMPLATE.format(number=388, date="2026-08-17"), encoding="utf-8"
    )
    (goals / "UBM - 1-週報 - 2026-08-17〜2026-08-23.md").write_text(WEEKLY_REPORT, encoding="utf-8")
    (goals / "UBM - 2-月報（１ヶ月） - 2026-08-01〜2026-08-31.md").write_text(
        MONTHLY_REPORT, encoding="utf-8"
    )
    return tmp_path


def run(vault: Path, date: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", str(vault), "--date", date],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_number_increments_from_previous(vault: Path):
    ctx = run(vault, "2026-08-18")
    assert ctx["journal_number"] == 389
    assert ctx["is_regeneration"] is False
    assert ctx["heading"] == "# No.389 - ジャーナル（2026-08-18）"


def test_number_is_preserved_on_regeneration(vault: Path):
    ctx = run(vault, "2026-08-17")
    assert ctx["journal_number"] == 388
    assert ctx["is_regeneration"] is True
    assert any("既に存在" in w for w in ctx["warnings"])


def test_output_path_matches_target_date(vault: Path):
    ctx = run(vault, "2026-08-18")
    assert ctx["output_path"].endswith("02_Configs/Daily/2026-08-18.md")


def test_previous_journal_inherits_purpose_and_checklist(vault: Path):
    ctx = run(vault, "2026-08-18")
    prev = ctx["previous_journal"]
    assert prev["number"] == 388
    assert prev["ultimate_purpose"] == [
        "AIを思い通りに使いこなし、自分の時間を有益に過ごした人財を世界一輩出した。"
    ]
    assert len(prev["prohibitions"]) == 2
    assert "◇【0→1】" in prev["phase_checklist"]


def test_days_remaining_uses_report_period(vault: Path):
    ctx = run(vault, "2026-08-18")
    weekly = ctx["goals"]["weekly"]
    assert weekly["period_start"] == "2026-08-17"
    assert weekly["period_end"] == "2026-08-23"
    assert weekly["days_remaining"] == 5
    assert weekly["expired"] is False
    assert weekly["source"] == "report"


def test_expired_goal_reports_overdue(vault: Path):
    ctx = run(vault, "2026-08-18")
    yearly = ctx["goals"]["yearly"]
    assert yearly["expired"] is True
    assert yearly["days_remaining"] == 0
    assert yearly["days_overdue"] == 50
    assert any("1年目標の期間が終了" in w for w in ctx["warnings"])


def test_period_drift_between_journal_and_report_warns(vault: Path):
    # 前回ジャーナルの週次期間は 〜2026-08-16、週報は 〜2026-08-23 → 目標本文の更新を促す
    ctx = run(vault, "2026-08-18")
    assert any("目標本文を新しい期間の内容へ更新" in w for w in ctx["warnings"])


def test_weekly_report_carries_day_tasks_and_habits(vault: Path):
    ctx = run(vault, "2026-08-18")
    weekly = ctx["weekly_report"]
    assert weekly["day_tasks"] == [
        "依頼アプリ制作を30分×1本で進める",
        "散歩の直後にジャーナルを作成",
    ]
    assert [g["title"] for g in weekly["habit_goals"]] == [
        "Gridノートの直後に記録する",
        "30分単位で切り替える",
    ]
    assert weekly["judgment_criteria"].startswith("迷ったら")
    assert "---" not in weekly["judgment_criteria"]


def test_horizontal_rule_is_not_parsed_as_bullet(vault: Path):
    ctx = run(vault, "2026-08-18")
    assert "--" not in ctx["weekly_report"]["key_numbers"]
    assert "--" not in ctx["weekly_report"]["outcome_goals"]


def test_missing_day_task_warns(vault: Path):
    ctx = run(vault, "2026-08-20")  # 週報に 8/20 の行は無い
    assert ctx["weekly_report"]["day_tasks"] == []
    assert any("当日タスクを引き継げませんでした" in w for w in ctx["warnings"])


def test_missing_vault_root_fails_closed(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", "", "--date", "2026-08-18"],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 1


def test_missing_daily_dir_fails_closed(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", str(tmp_path), "--date", "2026-08-18"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1


def test_daily_habits_are_always_included(vault: Path):
    """固定習慣は vault の状態に関わらず毎回 context へ載る（毎日確認する契約）。"""
    ctx = run(vault, "2026-08-18")
    ids = [h["id"] for h in ctx["daily_habits"]]
    assert ids == [
        "grid-note", "sleep-by-23", "stretch", "no-unplanned-video", "journal", "sns-post",
    ]
    for h in ctx["daily_habits"]:
        assert h["natural_question"]
        assert h["target_section"]
        assert h["keywords"]


def test_missing_previous_journal_warns_about_journal_habit(tmp_path: Path):
    """前日ジャーナルが無い = ジャーナル習慣が途切れているシグナルを warnings に出す。"""
    daily = tmp_path / "02_Configs" / "Daily"
    goals = tmp_path / "05_Project" / "UBM" / "目標設定"
    daily.mkdir(parents=True)
    goals.mkdir(parents=True)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", str(tmp_path), "--date", "2026-08-18"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    ctx = json.loads(proc.stdout)
    assert any("ジャーナル習慣が途切れ" in w for w in ctx["warnings"])
