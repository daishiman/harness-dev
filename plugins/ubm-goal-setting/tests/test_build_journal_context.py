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


def test_principle_checklist_absent_does_not_borrow_phase_checklist(vault: Path):
    """前回に `# 原理原則 チェックシート` が無いとき、フェーズ別の中身を継承しない。

    `# フェーズ別 課題チェックシート` は「チェックシート」を部分一致で含むため、
    section_body の fallback に任せると本ブロックを持たない移行期のジャーナルから
    フェーズ別の中身が原理原則チェックシートとして流れ込む。どちらも `- [ ]` の塊なので
    取り違えても見た目では気づけない。空で返してテンプレート初期化へ倒す経路を固定する。
    """
    ctx = run(vault, "2026-08-18")
    prev = ctx["previous_journal"]
    assert prev["principle_checklist"] == ""
    assert "◇【0→1】" not in prev["principle_checklist"]
    assert any("principle-checklist.md" in w for w in ctx["warnings"]), ctx["warnings"]


def test_principle_checklist_inherited_when_present(vault: Path):
    """前回に `# 原理原則 チェックシート` があればその中身をそのまま継承する。"""
    prev_path = vault / "02_Configs/Daily/2026-08-17.md"
    prev_path.write_text(
        prev_path.read_text(encoding="utf-8")
        + "\n# 原理原則 チェックシート\n\n## ◇ 右肩上がりになっていますか？\n\n"
        "- [x] 会社（事業）の口座残高\n- [ ] 個人の口座残高\n",
        encoding="utf-8",
    )
    ctx = run(vault, "2026-08-18")
    body = ctx["previous_journal"]["principle_checklist"]
    assert "◇ 右肩上がりになっていますか？" in body
    assert "- [x] 会社（事業）の口座残高" in body
    assert "◇【0→1】" not in body
    assert not [w for w in ctx["warnings"] if "principle-checklist.md" in w], ctx["warnings"]


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
    assert proc.returncode == 2, "入力不備は sibling script と揃えて exit 2"


def test_missing_daily_dir_fails_closed(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--vault-root", str(tmp_path), "--date", "2026-08-18"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2, "入力不備は sibling script と揃えて exit 2"


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


# --- existing_file: Write による実データ消失の防止 (C-1 回帰) ---
#
# ジャーナルは journal-composer が Write で全置換する。対象パスに別日の内容が
# 入ったまま書くと利用者の記録がそのまま消える。実 vault の 2026-08-17.md には
# 見出し `# No.388 - ジャーナル（2026-08-16）` の 27KB が存在し、無引数実行で
# 消える状態だった。以下はその経路を塞いだままにするための固定。

def test_new_file_is_writable(vault: Path):
    ctx = run(vault, "2026-08-18")
    assert ctx["existing_file"]["write_mode"] == "new"


def test_same_day_regeneration_is_writable(vault: Path):
    """ファイル日付と見出し日付が一致していれば同じ日の作り直し。"""
    ctx = run(vault, "2026-08-17")
    assert ctx["existing_file"]["write_mode"] == "regenerate"
    assert ctx["existing_file"]["number"] == 388


def test_other_days_content_blocks_the_write(vault: Path):
    """ファイル日付と見出し日付がズレていたら別日の記録。上書きさせない。"""
    daily = vault / "02_Configs" / "Daily"
    (daily / "2026-08-19.md").write_text(
        JOURNAL_TEMPLATE.format(number=389, date="2026-08-18"), encoding="utf-8"
    )
    ctx = run(vault, "2026-08-19")
    existing = ctx["existing_file"]
    assert existing["write_mode"] == "blocked"
    assert existing["heading_date"] == "2026-08-18"
    assert any("別日" in w for w in ctx["warnings"]), ctx["warnings"]


def test_unrecognized_content_blocks_the_write(vault: Path):
    """見出しを読めないファイルは中身を判別できない。判別不能は遮断側へ倒す。"""
    daily = vault / "02_Configs" / "Daily"
    (daily / "2026-08-20.md").write_text("# No.149 - ジャーナル\n\n手書きのメモ\n", encoding="utf-8")
    ctx = run(vault, "2026-08-20")
    assert ctx["existing_file"]["write_mode"] == "blocked"
    assert ctx["existing_file"]["heading_date"] is None


def test_blocked_file_does_not_reuse_the_other_days_number(vault: Path):
    """blocked は別日の記録。その番号を継ぐと通番が重複する。

    「上書きせず停止せよ」と「番号を維持して更新扱い」を同時に出す自己矛盾を防ぐ。
    """
    daily = vault / "02_Configs" / "Daily"
    (daily / "2026-08-19.md").write_text(
        JOURNAL_TEMPLATE.format(number=389, date="2026-08-18"), encoding="utf-8"
    )
    ctx = run(vault, "2026-08-19")
    assert ctx["existing_file"]["write_mode"] == "blocked"
    assert ctx["is_regeneration"] is False
    assert ctx["journal_number"] == 390, "別日の No.389 を継がず最大値+1 で採番する"
    assert not any("番号を維持" in w for w in ctx["warnings"]), ctx["warnings"]


def test_goal_body_keeps_colons(vault: Path):
    """目標本文の半角コロン (時刻・URL) を区切りと誤認して先頭を落とさない。"""
    daily = vault / "02_Configs" / "Daily"
    text = JOURNAL_TEMPLATE.format(number=388, date="2026-08-17")
    text = text.replace(
        "- 目標：1週間目標の本文。",
        "- 目標：毎日22:00までに退勤し https://example.com/plan を更新する",
    )
    (daily / "2026-08-17.md").write_text(text, encoding="utf-8")
    ctx = run(vault, "2026-08-18")
    goal = ctx["previous_journal"]["goals"]["weekly"]["goal"]
    assert goal == "毎日22:00までに退勤し https://example.com/plan を更新する"


def _weekly_with_lines(vault: Path, lines: str) -> None:
    """週報の【今週の大きな到達ライン】ブロックだけ差し替える。"""
    report = vault / "05_Project" / "UBM" / "目標設定" / "UBM - 1-週報 - 2026-08-17〜2026-08-23.md"
    text = report.read_text(encoding="utf-8")
    before, _, rest = text.partition("## 【今週の大きな到達ライン】\n")
    _, sep, after = rest.partition("\n---\n")
    report.write_text(f"{before}## 【今週の大きな到達ライン】\n{lines}{sep}{after}", encoding="utf-8")


def test_day_heading_without_parens_is_not_absorbed_into_previous_day(vault: Path):
    """「- 8/19 火曜」形式を見出しと認識しないと 8/18 のタスクへ silent に混入する。"""
    _weekly_with_lines(vault, "\n".join([
        "",
        "- [ ] 8/18（月）：",
        "\t- [ ] 18日の本来タスク",
        "- [ ] 8/19 火曜",
        "\t- [ ] 19日のタスク",
        "",
    ]))
    ctx = run(vault, "2026-08-18")
    assert ctx["weekly_report"]["day_tasks"] == ["18日の本来タスク"]
    assert run(vault, "2026-08-19")["weekly_report"]["day_tasks"] == ["19日のタスク"]


def test_day_like_line_that_is_not_a_heading_warns(vault: Path):
    """見出しか子タスクか決めきれない行は子タスク扱いにするが、黙らせない。"""
    _weekly_with_lines(vault, "\n".join([
        "",
        "- [ ] 8/18（月）：",
        "\t- [ ] 8/25 の資料を先に作る",
        "",
    ]))
    ctx = run(vault, "2026-08-18")
    assert ctx["weekly_report"]["day_tasks"] == ["8/25 の資料を先に作る"]
    assert any("判別できない行" in w for w in ctx["warnings"]), ctx["warnings"]


def test_weekday_word_in_task_text_is_not_a_day_heading(vault: Path):
    """「8/27 日程調整」の『日』を曜日と誤読して以降を吸い込まない。"""
    _weekly_with_lines(vault, "\n".join([
        "",
        "- [ ] 8/18（月）：",
        "\t- [ ] 8/27 日程調整する",
        "\t- [ ] 18日の別タスク",
        "",
    ]))
    ctx = run(vault, "2026-08-18")
    assert ctx["weekly_report"]["day_tasks"] == ["8/27 日程調整する", "18日の別タスク"]


def test_days_overdue_key_is_always_present(vault: Path):
    """キー集合が expired の有無で変わると消費側が `in` 判定と値判定で割れる。"""
    goals = run(vault, "2026-08-18")["goals"]
    assert set(goals) == {"yearly", "quarterly", "monthly", "weekly"}
    for key, entry in goals.items():
        assert "days_overdue" in entry, key
    assert goals["yearly"]["expired"] is True and goals["yearly"]["days_overdue"] > 0
    assert goals["monthly"]["expired"] is False and goals["monthly"]["days_overdue"] == 0


def test_non_utf8_daily_file_does_not_crash(vault: Path):
    """Daily に非 UTF-8 の .md が 1 つあるだけで traceback にしない。"""
    (vault / "02_Configs" / "Daily" / "2026-08-10.md").write_bytes(
        "# No.380 - ジャーナル（2026-08-10）\n日本語".encode("cp932")
    )
    ctx = run(vault, "2026-08-18")
    assert ctx["journal_number"] >= 1


def test_blocked_file_without_heading_reports_undeterminable(vault: Path):
    """見出しが無いファイルは「別日 (None)」ではなく判別不能として報告する。"""
    (vault / "02_Configs" / "Daily" / "2026-08-18.md").write_text("走り書き\n", encoding="utf-8")
    ctx = run(vault, "2026-08-18")
    assert ctx["existing_file"]["write_mode"] == "blocked"
    assert any("判別できない内容" in w for w in ctx["warnings"]), ctx["warnings"]
    assert not any("別日 (None)" in w for w in ctx["warnings"]), ctx["warnings"]


# --- 他日のタスク混入 / 見出し取り違えの回帰 ---


def _mod():
    """純関数を直接叩くため script を module として読む。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_build_journal_context", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DAY_FORMATS = """## 今週の大きな到達ライン

- 8/18（月）
- 月曜のタスクA
**8/19（火）**
- 火曜のタスクB
* 8/20（水）：水曜の同一行タスク
2026/8/21（木）：木曜の同一行タスク
- 8/22（金）
* 金曜のタスクC
8.23（土）
- 土曜のタスクD
"""


@pytest.mark.parametrize(
    "day,expected",
    [
        (18, ["月曜のタスクA"]),
        (19, ["火曜のタスクB"]),      # `**8/19（火）**` 太字
        (20, ["水曜の同一行タスク"]),  # `*` 箇条書き + 見出しと同じ行に本文
        (21, ["木曜の同一行タスク"]),  # 年つき
        (22, ["金曜のタスクC"]),      # `*` 箇条書きの子タスク
        (23, ["土曜のタスクD"]),      # `8.19` ドット区切り
    ],
)
def test_day_heading_format_variants_do_not_merge_days(day: int, expected: list[str]):
    """日付見出しの書式ゆれを見出しと認識できないと、他日のタスクが今日へ黙って混ざる。

    修正前は `-` と `/` の決め打ちだったため、これらの行がすべて子タスク扱いになり
    直前の見出し (= 対象日) へ吸い込まれた。警告も出なかった。
    """
    from datetime import date

    tasks, _ = _mod().extract_day_tasks(DAY_FORMATS, date(2026, 8, day))
    assert tasks == expected


def test_day_tasks_respect_the_year_when_written():
    """covers_target=false の別年レポートから M/D 一致だけで拾わない。"""
    from datetime import date

    mod = _mod()
    text = "## 今週の大きな到達ライン\n2025/8/19（火）：去年のタスク\n"
    assert mod.extract_day_tasks(text, date(2026, 8, 19)) == ([], [])
    assert mod.extract_day_tasks(text, date(2025, 8, 19))[0] == ["去年のタスク"]


def test_section_body_prefers_exact_heading_over_retrospective():
    """`### 1年目標` を探して `### 1年目標の振り返り` を掴むと先週の結果が目標になる。"""
    mod = _mod()
    text = "## 1年目標の振り返り\n- 目標：去年の結果\n\n## 1年目標\n- 目標：今期の目標\n"
    assert "今期の目標" in mod.section_body(text, "1年目標")
    # 振り返り節しか無いときは掴まない (空を返して未解決を未解決のまま残す)
    assert mod.section_body("## 1年目標の振り返り\n- 目標：去年の結果\n", "1年目標") == ""


def test_has_value_requires_the_goal_text():
    """期間だけでは「引き継げた」と言えない。source=previous_journal が空目標になる。"""
    mod = _mod()
    assert mod.has_value({"period_start": "2026-01-01", "period_end": "2026-12-31"}) is False
    assert mod.has_value({"goal": "  "}) is False
    assert mod.has_value({"goal": "売上250,000"}) is True


def test_daily_habits_non_object_is_exit_2(vault: Path, tmp_path: Path, monkeypatch):
    """top-level が JSON 配列だと .get が AttributeError になり exit 1 + traceback だった。"""
    import shutil

    sandbox = tmp_path / "sandbox"
    shutil.copytree(SCRIPT.parent.parent, sandbox)
    (sandbox / "references" / "daily-habits.json").write_text("[]", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / SCRIPT.name), "--date", "2026-08-18"],
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "UBM_VAULT_ROOT": str(vault)},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr


def test_decimals_and_times_are_not_day_headings():
    """`- 2.0：リリース` を 2/0 の見出しにすると以降のタスクが warning なしで消える。"""
    from datetime import date

    mod = _mod()
    text = (
        "## 今週の大きな到達ライン\n"
        "- 8/19（火）：\n"
        "- タスク1\n"
        "- 2.0：リリースする\n"
        "- 9.30：朝会に出る\n"
        "- タスク2\n"
    )
    tasks, _ = mod.extract_day_tasks(text, date(2026, 8, 19))
    assert tasks == ["タスク1", "2.0：リリースする", "9.30：朝会に出る", "タスク2"]
    # `.` 区切りでも曜日注記があれば日付。時刻・小数と切り分けられていること。
    dotted = "## 今週の大きな到達ライン\n- 8.19（火）：\n- 火曜タスク\n- 8.20（水）：\n- 水曜タスク\n"
    assert mod.extract_day_tasks(dotted, date(2026, 8, 19))[0] == ["火曜タスク"]


def test_japanese_day_heading_is_recognised():
    """`- 8月19日（水）：` は最も自然な和文表記。見出しにできないと別日が混入する。"""
    from datetime import date

    mod = _mod()
    text = (
        "## 今週の大きな到達ライン\n"
        "- 8月18日（火）：\n"
        "- 火曜タスク\n"
        "- 8月19日（水）：\n"
        "- 水曜タスク\n"
    )
    assert mod.extract_day_tasks(text, date(2026, 8, 18))[0] == ["火曜タスク"]
    assert mod.extract_day_tasks(text, date(2026, 8, 19))[0] == ["水曜タスク"]


def test_parenthetical_review_word_does_not_blank_the_section():
    """`（週次レビューで使う）` の補足まで振り返り扱いすると判断基準が無警告で空になる。"""
    mod = _mod()
    text = "## 今週の判断基準（週次レビューで使う）\n- 迷ったら短い方\n"
    assert "迷ったら短い方" in mod.section_body(text, "今週の判断基準")
    # 芯そのものが振り返りの節は従来どおり除外する
    assert mod.section_body("## 今週の判断基準の振り返り\n- 先週の結果\n", "今週の判断基準") == ""


def test_bracketed_heading_matches_exactly():
    """実データの見出しは `## 【今週の判断基準】`。装飾で完全一致を落とすと部分一致頼みになる。"""
    mod = _mod()
    text = "## 【今週の判断基準】の振り返り\n- 先週\n\n## 【今週の判断基準】\n- 今週\n"
    assert mod.section_body(text, "今週の判断基準").strip() == "- 今週"


def test_report_alone_does_not_claim_a_resolved_goal(vault: Path):
    """レポートは期間しか供給しない。goal 空で source=report は未解決を隠す。"""
    daily = vault / "02_Configs" / "Daily"
    # 前回ジャーナルの 1週間目標から目標本文だけを抜く (期間はレポートが供給する)
    path = daily / "2026-08-17.md"
    text = path.read_text(encoding="utf-8")
    lines = []
    in_weekly = False
    for line in text.splitlines():
        if line.startswith("### ") :
            in_weekly = "1週間目標" in line
        if in_weekly and line.lstrip().startswith("- 目標："):
            lines.append("- 目標：")
            continue
        lines.append(line)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ctx = run(vault, "2026-08-18")
    assert ctx["goals"]["weekly"]["goal"].strip() == ""
    assert ctx["goals"]["weekly"]["source"] == "unresolved"
    # 期間はレポートから解決できているので残日数は出るが、未解決は黙らせない
    assert ctx["goals"]["weekly"]["period_end"] == "2026-08-23"
    assert any("weekly" in w for w in ctx["warnings"]), ctx["warnings"]


def test_habit_without_label_is_exit_2(vault: Path, tmp_path: Path):
    """SKILL.md が編集を誘導している SSOT。KeyError で exit 1 にせず exit 2 を守る。"""
    import json as _json
    import os
    import shutil

    sandbox = tmp_path / "sandbox-label"
    shutil.copytree(SCRIPT.parent.parent, sandbox)
    path = sandbox / "references" / "daily-habits.json"
    data = _json.loads(path.read_text(encoding="utf-8"))
    del data["habits"][0]["label"]
    path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / SCRIPT.name), "--date", "2026-08-18"],
        capture_output=True,
        text=True,
        env={**dict(os.environ), "UBM_VAULT_ROOT": str(vault)},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr


def test_habit_without_target_section_is_exit_2(vault: Path, tmp_path: Path):
    """検査の契約を validate 側と揃える。

    Phase0 が素通しすると、利用者は 5〜10 分の対話を終えた Phase5 で初めて
    daily-habits.json の破損を知る。検知は最初のゲートで済ませる。
    """
    import json as _json
    import os
    import shutil

    sandbox = tmp_path / "sandbox-target-section"
    shutil.copytree(SCRIPT.parent.parent, sandbox)
    path = sandbox / "references" / "daily-habits.json"
    data = _json.loads(path.read_text(encoding="utf-8"))
    del data["habits"][0]["target_section"]
    path.write_text(_json.dumps(data, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / SCRIPT.name), "--date", "2026-08-18"],
        capture_output=True,
        text=True,
        env={**dict(os.environ), "UBM_VAULT_ROOT": str(vault)},
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "target_section" in proc.stderr, proc.stderr


def test_parenthesised_retrospective_heading_is_reported():
    """括弧内に振り返り語がある見出しを黙って採用しない。

    `### 1年目標（2025年度の振り返り）` は除外語判定 (括弧を除いた芯に掛ける) を
    すり抜けて採用される。採用そのものは残すが、過去データへ入れ替わった可能性を
    warnings で人が気づけるようにする — これが除外語を細くし続けない構造的な解。
    """
    mod = _mod()
    text = "### 1年目標（2025年度の振り返り）\n- 期間：2025-01-01〜2025-12-31\n- 目標：旧年度の目標\n"
    notes: list[str] = []
    body = mod.section_body(text, "1年目標", level="###", notes=notes)
    assert "旧年度の目標" in body
    assert notes and "1年目標（2025年度の振り返り）" in notes[0], notes


def test_canonical_habit_goal_heading_is_not_a_partial_match(vault: Path):
    """週報の正式名 `## 【習慣目標（仕組みで動く土台）】` で警告を出さない。

    正式名は run-ubm-goal-setting が週報の必須セクションとして検査している表記なので、
    毎回必ず現れる。これを部分一致 fallback 経由で拾うと「別の期の内容では」という
    警告が全実行で立ち、本当に確認が要る warning が埋もれる。
    """
    ctx = run(vault, "2026-08-18")
    assert ctx["weekly_report"]["habit_goals"], ctx["weekly_report"]
    assert not [w for w in ctx["warnings"] if "習慣目標" in w], ctx["warnings"]


def test_alternate_goal_spelling_does_not_warn(vault: Path):
    """正本は `### 2ヶ月目標`。fixture の `### 3ヶ月目標` は旧表記で、読み取りだけ通る。

    片方だけ在るのが正常なので、解決できた側について warning を立ててはいけない。
    """
    ctx = run(vault, "2026-08-18")
    assert ctx["goals"]["quarterly"]["goal"], ctx["goals"]["quarterly"]
    assert not [w for w in ctx["warnings"] if "2ヶ月目標" in w], ctx["warnings"]


def test_unresolved_goal_layer_still_warns():
    """別表記の保留は「どの表記でも解決しなかった」ときまで黙らせない。"""
    mod = _mod()
    notes: list[str] = []
    goals = mod.extract_journal_goals("### 1週間目標\n- 目標：あ\n", notes=notes)
    assert "quarterly" not in goals
    assert [n for n in notes if "3ヶ月目標" in n], notes


def test_retrospective_only_heading_still_reports_after_buffering():
    """振り返り節しか無い階層は、保留経路を通っても除外メモが外へ出る。"""
    mod = _mod()
    notes: list[str] = []
    goals = mod.extract_journal_goals("### 3ヶ月目標の振り返り\n- 目標：先期の結果\n", notes=notes)
    assert "quarterly" not in goals
    assert [n for n in notes if "振り返り節と判定して除外" in n], notes
