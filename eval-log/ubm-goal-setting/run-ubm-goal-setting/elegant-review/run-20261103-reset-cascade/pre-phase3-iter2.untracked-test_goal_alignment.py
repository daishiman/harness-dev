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
            section("前月の行動実績（行動管理）", "- 知人へ連絡を6件送った"))
    validator = alignment(text)
    assert validator.errors == 0
    assert "未照合" in capsys.readouterr().out


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


def test_concise_monthly_cli_keeps_all_items_without_project_details(tmp_path):
    """実際のCLI経路で、旧件数制約と詳細タスク強制へ戻らないことを確認。"""
    current = chain_text("今月")
    extra = {
        "確認された情報": "- 対象期間：2026-06-01〜2026-06-30",
        "今期の売上目標": "180000",
        "今期の累計売上実績": "10000",
        "前月の売上目標": "40000",
        "前月の売上実績": "30000",
        "前月の売上目標と実績の差分": "-10000",
        "前月の売上に対して未達を挽回するための行動": "- 個別打診：知人へ日程候補を12件送る　期日6/10",
        "前月の売上以外の成果目標": "- 初回面談：12人",
        "前月の売上以外の成果実績": "- 初回面談：8人",
        "前月の売上以外の成果目標と実績の差分": "- 初回面談：-4人",
        "前月の売上以外の成果に対して未達を挽回するための行動": "- 日程候補：知人へ個別に送る　期日6/10",
        "前月の行動目標（行動管理）": "- 個別打診：知人へ12件送る",
        "前月の行動実績（行動管理）": "- 個別打診：知人へ8件送付",
        "前月の行動目標と実績の差分": "- 個別打診：-4件",
        "前月の行動に対して未達を挽回するための行動": "- 個別打診：知人へ12件送る　期日6/10",
        "現在事業パートナー数": "2",
        "現在のグリッドパートナー数": "3",
        "今月やらないこと（明確に排除するもの）": "- 新商品追加\n- 新規媒体追加\n- 無目的な参加",
        "今月末の振り返りチェックリスト": "- [ ] 項目ごとに実績を記録する",
    }
    text = ("---\nmonthly_action_style: concise\n---\n"
            "## 【1ヶ月の目標】2026-06-01〜2026-06-30\n\n" + current +
            "".join(section(label, body) for label, body in extra.items()))
    path = tmp_path / "UBM - 2-月報 2026-06-01〜2026-06-30.md"
    path.write_text(text, encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--file", str(path), "--type", "monthly"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout
    assert "STATUS: PASS" in result.stdout
    # frontmatterで明示しない既存の詳細モードの契約は維持する。
    path.write_text(text.replace("monthly_action_style: concise", "monthly_action_style: detailed"), encoding="utf-8")
    result = subprocess.run([sys.executable, str(SCRIPT), "--file", str(path), "--type", "monthly"],
                            capture_output=True, text=True)
    assert result.returncode == 1
    assert "プロジェクト別タスク" in result.stdout
