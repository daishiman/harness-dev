"""項目の脱落と、数量・単位・期限の取り違えの回帰テスト。データは架空。"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = (Path(__file__).resolve().parents[1] /
          "skills/run-ubm-goal-setting/scripts/validate-goal-output.py")
spec = importlib.util.spec_from_file_location("goal_output_alignment", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Validator = module.Validator


def section(label: str, body: str) -> str:
    return f"## 【{label}】\n{body}\n\n"


def alignment(text: str):
    validator = Validator(text, "UBM - 2-月報 2026-06-01〜2026-06-30.md", "month")
    validator.check_report_alignment()
    return validator


@pytest.mark.parametrize("submitted", [
    "- 初回面談：11人　期日5/30",  # 人数と期日の月を入れ替えても同じ数字の集合
    "- 初回面談：5社　期日11/30",   # 数は同じでも単位が違う
    "- 初回面談：5人　期日11/29",
    "- 初回面談：6人　期日11/30",
])
def test_submission_quantity_unit_and_deadline_mismatch_fails(submitted):
    text = (section("今月の売上以外の成果目標", "- 初回面談：5人　期日11/30") +
            section("今月の売上以外の成果目標（提出）", submitted))
    assert alignment(text).errors > 0


@pytest.mark.parametrize("family", ["売上以外の成果", "行動"])
@pytest.mark.parametrize("actual", [
    "- 個別相談：確認中",
    "- 紹介：確認中\n- 個別相談：確認中",
    "- 個別相談：確認中\n- 紹介依頼：確認中",
])
def test_previous_goal_result_item_loss_or_order_change_fails(family, actual):
    target_label = f"前月の{family}目標" + ("（行動管理）" if family == "行動" else "")
    result_label = f"前月の{family}実績" + ("（行動管理）" if family == "行動" else "")
    text = (section(target_label, "- 個別相談：12件\n- 紹介：3件") +
            section(result_label, actual) +
            section(f"前月の{family}目標と実績の差分", "- 個別相談：確認中\n- 紹介：確認中"))
    assert alignment(text).errors > 0


def test_unknown_results_remain_per_item_without_assuming_zero():
    text = (section("前月の売上以外の成果目標", "- 初回面談：12人\n- 紹介者：3人") +
            section("前月の売上以外の成果実績", "- 初回面談：確認中\n- 紹介者：確認中") +
            section("前月の売上以外の成果目標と実績の差分", "- 初回面談：確認中\n- 紹介者：確認中"))
    assert alignment(text).errors == 0


# 前回ブロック（前回の目標→実績→差分）の項目一致は週報・月報・期報・1年で共通。
@pytest.mark.parametrize("kind,previous", [("week", "前週"), ("period", "前期"), ("year", "前年")])
@pytest.mark.parametrize("family", ["売上以外の成果", "行動"])
def test_other_layers_previous_items_use_same_history_check(kind, previous, family):
    text = (section(f"{previous}の{family}目標", "- 面談：12人\n- 紹介：3人") +
            section(f"{previous}の{family}実績", "- 面談：確認中\n- 紹介：確認中") +
            section(f"{previous}の{family}目標と実績の差分", "- 面談：確認中\n- 紹介：確認中"))
    validator = Validator(text, "example.md", kind)
    validator.check_report_alignment()
    assert validator.errors == 0
    validator = Validator(text.replace("- 紹介：確認中", "", 1), "example.md", kind)
    validator.check_report_alignment()
    assert validator.errors > 0


def test_legacy_unlabelled_items_are_reported_unchecked(capsys):
    text = (section("前月の行動目標（行動管理）", "- 知人へ連絡を12件送る") +
            section("前月の行動実績（行動管理）", "- 知人へ連絡を6件送った") +
            section("前月の行動目標と実績の差分", "- 知人へ連絡を-6件"))
    validator = alignment(text)
    assert validator.errors == 0
    assert "未照合" in capsys.readouterr().out


# 目標欄に項目があるのに実績・差分の欄が無いと、項目ごとの対応が取れない（旧形式でも同じ）。
# 提出用は差分の欄を持たない既定テンプレートなので、提出用の差分だけは求めない。
PREVIOUS_OUTCOME_TARGET = "- 初回面談：12人　期日5/30"
PREVIOUS_OUTCOME_RESULT = "- 初回面談：8人"


@pytest.mark.parametrize("missing", ["前月の売上以外の成果実績", "前月の売上以外の成果目標と実績の差分"])
def test_managed_previous_family_requires_result_and_diff_columns(missing, capsys):
    columns = {
        "前月の売上以外の成果目標": PREVIOUS_OUTCOME_TARGET,
        "前月の売上以外の成果実績": PREVIOUS_OUTCOME_RESULT,
        "前月の売上以外の成果目標と実績の差分": "- 初回面談：-4人",
    }
    del columns[missing]
    validator = alignment("".join(section(label, body) for label, body in columns.items()))
    assert validator.errors > 0
    assert f"【{missing}】がありません" in capsys.readouterr().out


def test_submission_previous_family_does_not_require_diff_column(capsys):
    text = (section("前月の売上以外の成果目標", PREVIOUS_OUTCOME_TARGET) +
            section("前月の売上以外の成果実績", PREVIOUS_OUTCOME_RESULT) +
            section("前月の売上以外の成果目標と実績の差分", "- 初回面談：-4人") +
            section("前月の売上以外の成果目標（提出）", PREVIOUS_OUTCOME_TARGET) +
            section("前月の売上以外の成果実績（提出）", PREVIOUS_OUTCOME_RESULT))
    assert alignment(text).errors == 0
    assert "がありません" not in capsys.readouterr().out
    # 提出用でも実績の欄は要る（差分だけが免除）。
    text = (section("前月の売上以外の成果目標（提出）", PREVIOUS_OUTCOME_TARGET) +
            section("前月の売上以外の成果目標と実績の差分（提出）", "- 初回面談：-4人"))
    assert alignment(text).errors > 0
    assert "【前月の売上以外の成果実績（提出）】がありません" in capsys.readouterr().out


def test_submission_actions_allow_group_order_but_keep_values():
    text = (section("今月の行動目標（行動管理・優先順位付き）",
                    "### → 契約：受諾（40000円）\n- [ ] 提案：候補2社へ条件を示す　期日6/20\n"
                    "### → 初回面談：参加（0円）\n- [ ] 個別打診：知人12人へ連絡する　期日6/10") +
            section("今月の行動目標（提出）",
                    "- 個別打診：知人12人へ連絡する　期日6/10\n- 提案：候補2社へ条件を示す　期日6/20"))
    assert alignment(text).errors == 0


def test_unlabelled_submission_action_is_not_claimed_synced(capsys):
    text = (section("今月の行動目標（行動管理・優先順位付き）", "- 知人12人へ連絡する　期日6/10") +
            section("今月の行動目標（提出）", "- 別の人12人へ連絡する　期日6/10"))
    assert alignment(text).errors == 0
    assert "未照合" in capsys.readouterr().out


@pytest.mark.parametrize("detail_side", ["managed", "submitted"])
@pytest.mark.parametrize("submitted_total,expected_errors", [(135000, 0), (136000, 1)])
def test_sales_total_is_compared_when_breakdown_is_only_on_one_side(detail_side, submitted_total, expected_errors):
    managed, submitted = "135000", str(submitted_total)
    breakdown = "\n- 継続支援：80000\n- 単発研修：55000"
    if detail_side == "managed":
        managed += breakdown
    else:
        submitted += breakdown
    text = (section("今月の売上目標", managed) +
            section("今月の売上目標（提出）", submitted))
    assert alignment(text).errors == expected_errors


@pytest.mark.parametrize("submitted_fee,expected_errors", [(55000, 0), (54000, 1)])
def test_sales_breakdown_is_compared_when_both_sides_have_it(submitted_fee, expected_errors):
    managed = "135000\n- 継続支援：80000\n- 単発研修：55000"
    submitted = f"135000\n- 継続支援：80000\n- 単発研修：{submitted_fee}"
    text = (section("今月の売上目標", managed) +
            section("今月の売上目標（提出）", submitted))
    assert alignment(text).errors == expected_errors


# 確定事項G: 提出用は管理用の射影（チェックボックス・グループ見出し・`→ 売上貢献` の2行目・
# 本文の個人名を外したもの）。提出用の成果目標に売上貢献の行が無くても、連鎖の検査は
# 管理用だけを見るので FAIL にしない。提出用との照合は項目名・数量・単位・期日で行う。
MONTH_NAME = "UBM - 2-月報 2026-06-01〜2026-06-30.md"
MANAGED_MONTH = (
    section("今月の売上目標", "150000") +
    section("今月の売上以外の成果目標",
            "- 提案の受諾：Bさんの受諾1件　期日6/20\n  → 売上貢献：100000 × 1 = 100000\n\n"
            "- 月額顧問の成約：Aさんの成約1件（初月分）　期日6/25\n  → 売上貢献：50000 × 1 = 50000\n\n"
            "- 説明日程の合意：Aさんの合意1件　期日6/10\n  → 売上貢献：0（月額顧問の成約を支える）") +
    section("今月の行動目標（行動管理・優先順位付き）",
            "### → 提案の受諾：Bさんの受諾（100000円）\n- [ ] 提案：Bさんへ条件を示す　期日6/15\n\n"
            "### → 月額顧問の成約：Aさんの成約（50000円）\n- [ ] 提案書：Aさんへ提出する　期日6/22\n\n"
            "### → 説明日程の合意：Aさんの合意（0円）\n- [ ] 説明日程：Aさんへ打診する　期日6/8")
)
SUBMITTED_MONTH = (
    section("今月の売上目標（提出）", "150000") +
    section("今月の売上以外の成果目標（提出）",
            "- 提案の受諾：受諾1件　期日6/20\n- 月額顧問の成約：成約1件（初月分）　期日6/25\n"
            "- 説明日程の合意：合意1件　期日6/10") +
    section("今月の行動目標（提出）",
            "- 提案：条件を示す　期日6/15\n- 提案書：提出する　期日6/22\n- 説明日程：打診する　期日6/8")
)


def test_submission_projection_is_outside_contribution_check(capsys):
    validator = Validator(MANAGED_MONTH + SUBMITTED_MONTH, MONTH_NAME, "month")
    validator.check_goal_chain()
    validator.check_report_alignment()
    assert validator.errors == 0, capsys.readouterr().out
    # 管理用の売上貢献の行が欠ければ、同じ検査は FAIL する（免除は提出用だけ）。
    broken = MANAGED_MONTH.replace("\n  → 売上貢献：50000 × 1 = 50000", "", 1)
    validator = Validator(broken + SUBMITTED_MONTH, MONTH_NAME, "month")
    validator.check_goal_chain()
    assert validator.errors > 0
    assert "月額顧問の成約" in capsys.readouterr().out


def test_submission_projection_keeps_quantity_and_deadline():
    # 個人名を外すのは射影の範囲内。数量・期日を変えるのは射影ではない。
    changed = SUBMITTED_MONTH.replace("- 提案の受諾：受諾1件　期日6/20", "- 提案の受諾：受諾2件　期日6/20", 1)
    assert changed != SUBMITTED_MONTH
    assert alignment(MANAGED_MONTH + changed).errors > 0


# 軌道修正記録（共通部品E）: 月報は管理用【確認された情報】の `行動の見直し：` 行を検査する。
MONTH_REVISION = "- 行動の見直し：提案書｜変更前：期日6/18｜変更後：期日6/22｜理由：先方の会議が6/22に移った｜上位への影響：なし"


def monthly_revision(line: str) -> Validator:
    text = section("確認された情報", "- 対象期間：2026-06-01〜2026-06-30\n" + line) + MANAGED_MONTH
    validator = Validator(text, MONTH_NAME, "month")
    validator.check_revision_records()
    return validator


def test_monthly_revision_record_passes(capsys):
    assert monthly_revision(MONTH_REVISION).errors == 0
    assert "PASS: 行動の見直し: ## 【確認された情報】 の「提案書」" in capsys.readouterr().out


@pytest.mark.parametrize("line,message", [
    (MONTH_REVISION.replace("行動の見直し：提案書｜", "行動の見直し：存在しない行動｜"), "今回の行動目標の項目名にありません"),
    (MONTH_REVISION.replace("変更後：期日6/22", "変更後：期日6/18"), "変更前と変更後が同じ"),
    (MONTH_REVISION.replace("｜理由：先方の会議が6/22に移った", ""), "空欄なく書いてください"),
    (MONTH_REVISION.replace("理由：先方の会議が6/22に移った", "理由："), "空欄なく書いてください"),
])
def test_monthly_revision_record_violations_fail(line, message, capsys):
    assert line != MONTH_REVISION
    assert monthly_revision(line).errors > 0
    assert message in capsys.readouterr().out


# 日付索引（確定事項H）: 月報の【今月の日別タスク】は【プロジェクト別タスク】か
# 管理用の行動目標に実在する項目名だけを引く。チェックボックスは付けない。
MONTH_PROJECTS = section(
    "プロジェクト別タスク",
    "### 月額顧問の案件\n- 先方担当者: Aさん\n- [ ] 見積：見積書を送る　期日6/12")


def monthly_date_index(*lines: str) -> Validator:
    text = MANAGED_MONTH + MONTH_PROJECTS + section("今月の日別タスク", "\n".join(lines))
    validator = Validator(text, MONTH_NAME, "month")
    validator.check_date_index()
    return validator


def test_monthly_date_index_accepts_project_and_action_names(capsys):
    validator = monthly_date_index("- 6/8（月）：説明日程",
                                   "- 6/12（金）：見積、提案｜やらない：新規媒体の検討",
                                   "- 6/13（土）：なし｜やらない：作業の持ち越し")
    assert validator.errors == 0
    assert "日付索引 3 行を照合しました" in capsys.readouterr().out


@pytest.mark.parametrize("line,message", [
    ("- 6/12（金）：見積、存在しない作業", "「存在しない作業」が行動目標の項目名にありません"),
    ("- [ ] 6/12（金）：見積", "チェックボックスは付けません"),
    ("- 6/12：見積", "で書いてください"),
    ("- 6/13（土）：なし", "なし｜やらない"),
])
def test_monthly_date_index_violations_fail(line, message, capsys):
    assert monthly_date_index("- 6/8（月）：説明日程", line).errors > 0
    assert message in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["week", "period", "year"])
def test_monthly_flag_does_not_affect_other_types(kind):
    text = "---\nmonthly_action_style: concise\n---\n"
    assert not Validator(text, "example.md", kind).concise_monthly


def test_monthly_flag_is_only_read_from_frontmatter():
    assert not Validator("monthly_action_style: concise\n", "example.md", "month").concise_monthly
    assert Validator("---\nmonthly_action_style: concise\n---\n", "example.md", "month").concise_monthly


def chain_text(word: str, count: int = 6) -> str:
    outcomes = []
    actions = []
    for i in range(count):
        outcomes.append(f"- 支援{i}：受諾1件　期日6/30\n  → 売上貢献：10000 × 1 = 10000")
        actions.append(f"### → 支援{i}：受諾（10000円）\n- [ ] 条件{i}：相手へ提案する　期日6/20")
    actions.extend(["- [ ] 日程確認：候補へ連絡する　期日6/21"] * 3)
    return (section(f"{word}の売上目標", str(count * 10000)) +
            section(f"{word}の売上以外の成果目標", "\n\n".join(outcomes)) +
            section(f"{word}の行動目標（行動管理・優先順位付き）", "\n".join(actions)))


@pytest.mark.parametrize("kind,word", [("month", "今月"), ("period", "今期"), ("year", "今年")])
def test_long_horizon_count_limits_warn_without_dropping_items(kind, word, capsys):
    validator = Validator(chain_text(word), "example.md", kind)
    validator.check_goal_chain()
    assert validator.errors == 0
    output = capsys.readouterr().out
    assert "WARN" in output and "6件" in output and "9件" in output


def test_weekly_count_limits_remain_errors():
    validator = Validator(chain_text("今週"), "example.md", "week")
    validator.check_goal_chain()
    assert validator.errors >= 2


@pytest.mark.parametrize("kind,word", [("month", "今月"), ("period", "今期"), ("year", "今年")])
@pytest.mark.parametrize("old,new,error", [
    ("10000 × 1 = 10000", "10000 × 2 = 10000", "売上貢献の式"),
    ("60000", "70000", "貢献合計"),
    ("### → 支援0：", "### → 存在しない成果：", "実在しない成果目標"),
])
def test_long_horizon_relaxation_keeps_sales_and_link_checks(kind, word, old, new, error, capsys):
    validator = Validator(chain_text(word).replace(old, new, 1), "example.md", kind)
    validator.check_goal_chain()
    assert validator.errors > 0
    assert error in capsys.readouterr().out


def monthly_cli_text(style: str, projects: str = "") -> str:
    """CLI 経路で PASS する月報（前回ブロックの挽回は対応行・確定事項I）。"""
    current = chain_text("今月")
    extra = {
        "確認された情報": "- 対象期間：2026-06-01〜2026-06-30",
        "今期の売上目標": "180000",
        "今期の累計売上実績": "10000",
        "前月の売上目標": "40000",
        "前月の売上実績": "30000",
        "前月の売上目標と実績の差分": "-10000",
        "前月の売上に対して未達を挽回するための行動": "- 初回面談：面談8人→12人（今回の行動目標「日程確認」で実行）",
        "前月の売上以外の成果目標": "- 初回面談：12人",
        "前月の売上以外の成果実績": "- 初回面談：8人",
        "前月の売上以外の成果目標と実績の差分": "- 初回面談：-4人",
        "前月の売上以外の成果に対して未達を挽回するための行動": "- 初回面談：日程候補の送付8件→12件（今回の行動目標「日程確認」で実行）",
        "前月の行動目標（行動管理）": "- 個別打診：知人へ12件送る",
        "前月の行動実績（行動管理）": "- 個別打診：知人へ8件送付",
        "前月の行動目標と実績の差分": "- 個別打診：-4件",
        "前月の行動に対して未達を挽回するための行動": "- 個別打診：8件→12件（今回の行動目標「条件0」で実行）",
        "現在事業パートナー数": "2",
        "現在のグリッドパートナー数": "3",
        "今月やらないこと（明確に排除するもの）": "- 新商品追加\n- 新規媒体追加\n- 無目的な参加",
        "今月末の振り返りチェックリスト": "- [ ] 項目ごとに実績を記録する",
    }
    return (f"---\nmonthly_action_style: {style}\n---\n"
            "## 【1ヶ月の目標】2026-06-01〜2026-06-30\n\n" + current +
            "".join(section(label, body) for label, body in extra.items()) + projects)


def run_monthly_cli(tmp_path, text: str) -> subprocess.CompletedProcess:
    path = tmp_path / MONTH_NAME
    path.write_text(text, encoding="utf-8")
    return subprocess.run([sys.executable, str(SCRIPT), "--file", str(path), "--type", "monthly"],
                          capture_output=True, text=True)


def test_concise_monthly_cli_keeps_all_items_without_project_details(tmp_path):
    """実際のCLI経路で、旧件数制約と詳細タスク強制へ戻らないことを確認。"""
    result = run_monthly_cli(tmp_path, monthly_cli_text("concise"))
    assert result.returncode == 0, result.stdout
    assert "STATUS: PASS" in result.stdout
    assert "挽回の対応行 3 行を照合しました" in result.stdout
    # frontmatterで明示しない既存の詳細モードの契約は維持する。
    result = run_monthly_cli(tmp_path, monthly_cli_text("detailed"))
    assert result.returncode == 1
    assert "月報にプロジェクト別タスクがありません" in result.stdout


# 確定事項H: 月報の【プロジェクト別タスク】は共通部品A の管理用書式
# `### {案件名}` ＋ `- 先方担当者: {名前}` ＋ `- [ ] {項目名}：{何をする}　期日{トークン}`。
PROJECT_TASK = "- [ ] 条件0：相手へ提案する　期日6/20"


def project_section(task_line: str) -> str:
    return section("プロジェクト別タスク", f"### 月額顧問の案件\n- 先方担当者: Aさん\n{task_line}")


def test_detailed_monthly_cli_accepts_project_task_format(tmp_path):
    result = run_monthly_cli(tmp_path, monthly_cli_text("detailed", project_section(PROJECT_TASK)))
    assert result.returncode == 0, result.stdout
    assert "PASS: プロジェクト別タスクが '- [ ] {項目名}：{何をする}　期日{トークン}' 形式" in result.stdout


@pytest.mark.parametrize("task_line", [
    "- [ ] [6/20] [Aさん] 提案書を出す",       # 廃止した `[期日] [提出先・宛先]` 書式
    "- [ ] 条件0：相手へ提案する　期日今週",    # `今週` は週報だけのトークン
    "- [ ] 条件0：相手へ提案する　期日今月中",  # `今月中` はトークンではない
    "- [ ] 相手へ提案する　期日6/20",           # 項目名が無い
])
def test_detailed_monthly_cli_rejects_other_project_task_formats(tmp_path, task_line):
    result = run_monthly_cli(tmp_path, monthly_cli_text("detailed", project_section(task_line)))
    assert result.returncode == 1
    assert "プロジェクト別タスクは '- [ ] {項目名}：{何をする}　期日{トークン}' で書いてください" in result.stdout
