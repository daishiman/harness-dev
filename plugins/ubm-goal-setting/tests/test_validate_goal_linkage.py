#!/usr/bin/env python3
"""validate-goal-linkage.py の受け入れテスト.

実行（cwd はプラグインルート）:
    <pytest が入っているインタプリタ> -m pytest tests/test_validate_goal_linkage.py -q

インタプリタのパスは固定しない。環境ごとに pytest の入っている先が違う。ただし
**回す前に `-m pytest --version` が rc=0 を返すことを確かめる。** pytest を持たない
インタプリタでも `-m pytest` は rc=1 を返し、それは「テストが落ちた」ではなく
「実行できなかった」の値なので、確かめずに回すと両者の区別が付かなくなる。

rc の意味を固定するのが目的。特に **rc=0（検査して未解決0件）と rc=3（分母0で
何も判定していない）が別物であること** を落とさないこと。

所属は `### → 成果目標名：要約（金額円）` のグループ見出しから読む。照合規則
（成果目標のキーの切り出し・空白を落とした完全一致）は validate-goal-output.py と
共用しているので、validator と判定が食い違わないことも固定する。

免除は `（土台）`／`（関係維持）` の2つだけ。ほかの括弧名・CLI での個別免除は無い。
免除が広がると、免除名を1つ足すだけで検査が通る状態を作れてしまう。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _PLUGIN_ROOT / "skills" / "run-ubm-goal-setting" / "scripts"
_SCRIPT = _SCRIPTS / "validate-goal-linkage.py"
_VALIDATE = _SCRIPTS / "validate-goal-output.py"
_GOLDEN = _PLUGIN_ROOT / "skills" / "run-ubm-goal-setting" / "assets" / "golden-sample-weekly.md"


def _load():
    spec = importlib.util.spec_from_file_location("validate_goal_linkage", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


vgl = _load()


HEAD_OUTCOME = "## 【今月の売上以外の成果目標】"
HEAD_ACTION = "## 【今月の行動目標（行動管理・優先順位付き）】"
MONTHLY_NAME = "UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25.md"


def _doc(outcomes: list[str], action_body: str) -> str:
    """成果目標（1項目=2行）と、行動目標セクションの本文をそのまま並べる。"""
    lines = ["# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25", ""]
    lines.append(HEAD_OUTCOME)
    for o in outcomes:
        lines += [f"- {o}", "  → 売上貢献：0（継続の見込み）", ""]
    lines.append(HEAD_ACTION)
    lines.append(action_body.rstrip("\n"))
    lines.append("")
    return "\n".join(lines)


def _rc(text: str) -> int:
    rc, _ = vgl.verify(text)
    return rc


def _out(text: str) -> str:
    _, lines = vgl.verify(text)
    return "\n".join(lines)


OK_OUTCOMES = ["継続コンサル：成約3件　期日10/25"]
OK_ACTIONS = (
    "### → 継続コンサル：成約3件（0円・継続の見込み）\n"
    "- [ ] 4回目の場で条件を提示する　期日10/22\n"
)


# --- rc=0: グループ見出しで両方向がそろっている ---

def test_all_resolved_is_rc0():
    assert _rc(_doc(OK_OUTCOMES, OK_ACTIONS)) == 0


def test_rc0_prints_denominators():
    out = _out(_doc(OK_OUTCOMES, OK_ACTIONS))
    assert "照合対象 1 件中 未解決 0 件" in out
    assert "照合対象 1 件中 支える行動なし 0 件" in out
    assert "STATUS: PASS" in out


def test_golden_sample_is_rc0():
    assert vgl.main(["--file", str(_GOLDEN)]) == 0


def test_every_action_in_group_counts_toward_denominator():
    text = _doc(
        OK_OUTCOMES,
        "### → 継続コンサル：成約3件（0円・継続の見込み）\n"
        "- [ ] 日程を打診する　期日10/8\n"
        "- [ ] 状況を聞く　期日10/15\n"
        "      【考え】先に困りごとを聞かないと条件が合わない\n"
        "- [ ] 条件を提示する　期日10/22\n",
    )
    out = _out(text)
    assert _rc(text) == 0
    assert "行動目標の項目数: 3（グループ見出し 3 / 行内注記 0 / 所属不明 0）" in out


# --- rc=1: forward の切れ（見出しが成果目標に無い名前を指す） ---

def test_forward_break_is_rc1():
    text = _doc(
        OK_OUTCOMES,
        "### → 継続相談：成約3件（0円）\n"
        "- [ ] 条件を提示する　期日10/22\n",
    )
    assert _rc(text) == 1
    out = _out(text)
    assert "参照「継続相談」" in out
    assert "成果目標「継続コンサル」を支える行動目標が1件もありません" in out


def test_one_character_difference_is_detected():
    """参照が成果目標キーの部分文字列になる1文字違いを落とす（部分一致では通る入力）。"""
    text = _doc(
        ["継続コンサル会：成約3件　期日10/25"],
        "### → 継続コンサル：成約3件（0円）\n- [ ] 条件を提示する　期日10/22\n",
    )
    assert _rc(text) == 1
    assert "参照「継続コンサル」" in _out(text)


def test_whitespace_difference_is_tolerated():
    """空白の差だけは同じ名前として扱う（validator の _ref_matches_key と同じ）。"""
    text = _doc(
        ["継続 コンサル：成約3件　期日10/25"],
        "### → 継続コンサル：成約3件（0円）\n- [ ] 条件を提示する　期日10/22\n",
    )
    assert _rc(text) == 0


# --- rc=1: backward の切れ（支える行動が無い成果目標）。validator の C6 は WARN ---

def test_backward_break_is_rc1():
    text = _doc(OK_OUTCOMES + ["勉強会：参加申込5名　期日10/17"], OK_ACTIONS)
    assert _rc(text) == 1
    assert "成果目標「勉強会」を支える行動目標が1件もありません" in _out(text)


def test_backward_break_is_only_warn_in_validator(tmp_path):
    """同じ入力で validator は C6 を WARN に留める。linkage が FAIL に上げる分担を固定する。"""
    golden = _GOLDEN.read_text(encoding="utf-8")
    text = golden.replace(
        "### → Cさん：7月勉強会の開催枠の確保（0円・8月の仕込み）\n"
        "- [ ] 7月の開催枠を確認する　期日7/1\n"
        "      【思い】商工会経由は信頼が高く、母集団を広げられる\n",
        "",
        1,
    )
    assert text != golden
    p = tmp_path / "UBM - 1-週報 2026-06-29〜2026-07-05.md"
    p.write_text(text, encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(_VALIDATE), "--file", str(p), "--type", "weekly"],
        capture_output=True, text=True,
    )
    assert "WARN: 成果目標「Cさん」を支える行動目標がありません" in r.stdout
    assert vgl.main(["--file", str(p)]) == 1


# --- 所属の読み方 ---

def test_action_without_group_or_inline_is_rc1():
    text = _doc(OK_OUTCOMES, "- [ ] 条件を提示する　期日10/22\n" + OK_ACTIONS)
    assert _rc(text) == 1
    assert "どの成果目標に属するか分かりません" in _out(text)


def test_inline_colon_notation_is_read_but_warned():
    """見出しの無い旧ファイルは行内の `→ 支える成果目標：` で読む（validator と同じフォールバック）。"""
    text = _doc(
        OK_OUTCOMES,
        "- [ ] 条件を提示する　期日10/22\n"
        "      → 支える成果目標：継続コンサル\n",
    )
    assert _rc(text) == 0
    assert "行内注記「→ 支える成果目標：XXX」で所属を書いた行動目標が 1 件" in _out(text)


def test_legacy_bracket_notation_is_rejected_with_hint():
    """ローカル版のカギ括弧記法は受理しない。validator の C4 と同じく所属不明として落とす。"""
    text = _doc(
        OK_OUTCOMES,
        "- [ ] 条件を提示する　期日10/22　→ 支える成果目標「継続コンサル」\n",
    )
    assert _rc(text) == 1
    assert "カギ括弧の行内注記" in _out(text)


def test_group_heading_wins_over_inline_note():
    text = _doc(
        OK_OUTCOMES,
        "### → 継続コンサル：成約3件（0円）\n"
        "- [ ] 条件を提示する　期日10/22\n"
        "      → 支える成果目標：存在しない成果\n",
    )
    assert _rc(text) == 0


def test_multiple_references_in_one_group_is_rc1():
    """1つの行動が複数の成果目標を指す `・` 区切りを落とす（OUTPUT_012）。"""
    text = _doc(
        OK_OUTCOMES + ["勉強会：参加申込5名　期日10/17"],
        "### → 継続コンサル・勉強会：まとめて（0円）\n- [ ] 案内を出す　期日10/10\n",
    )
    assert _rc(text) == 1
    assert "成果目標を 2 件参照しています" in _out(text)


# --- 免除は2つの括弧名だけ ---

@pytest.mark.parametrize("name", ["（土台）", "（関係維持）", "(土台)"])
def test_two_exempt_groups_are_allowed(name: str):
    text = _doc(
        OK_OUTCOMES,
        OK_ACTIONS + f"\n### → {name}\n- [ ] 習慣目標を毎日チェックする　期日 毎日\n",
    )
    out = _out(text)
    assert _rc(text) == 0
    assert "免除グループの行動: 1 件" in out


def test_other_paren_name_is_not_exempt():
    text = _doc(
        OK_OUTCOMES,
        OK_ACTIONS + "\n### → （準備）\n- [ ] 名簿を作る　期日10/3\n",
    )
    assert _rc(text) == 1
    assert "括弧名「（準備）」は免除されません" in _out(text)


def test_exempt_only_file_without_outcomes_is_rc3():
    text = _doc([], "### → （土台）\n- [ ] 習慣目標を毎日チェックする　期日 毎日\n")
    assert _rc(text) == 3


def test_verify_takes_no_allow_argument():
    import inspect
    assert list(inspect.signature(vgl.verify).parameters) == ["text"]


def test_allow_option_is_rejected_by_cli(tmp_path):
    p = tmp_path / "ok.md"
    p.write_text(_doc(OK_OUTCOMES, OK_ACTIONS), encoding="utf-8")
    assert vgl.main(["--file", str(p)]) == 0
    assert vgl.main(["--file", str(p), "--allow", "土台づくり"]) == 2


# --- rc=3: 分母0 ---

def test_no_sections_is_rc3_not_rc0():
    text = "# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25\n\n## 【今月の売上目標】\n\n500000円\n"
    assert _rc(text) == 3
    assert "NO_TARGET" in _out(text)


def test_empty_sections_is_rc3():
    assert _rc(_doc([], "")) == 3


# --- セクション境界 ---

def test_achievement_and_diff_sections_are_out_of_scope():
    text = _doc(OK_OUTCOMES, OK_ACTIONS) + (
        "\n## 【前月の行動実績】\n- 提案を1件出した\n"
        "\n## 【前月の行動目標と実績の差分】\n- -2件\n"
    )
    assert _rc(text) == 0


@pytest.mark.parametrize("period", ["週", "期"])
def test_weekly_and_quarterly_headings_are_recognised(period: str):
    text = (
        f"## 【今{period}の売上以外の成果目標】\n"
        "- 継続コンサル：成約3件　期日10/25\n  → 売上貢献：0（継続の見込み）\n\n"
        f"## 【今{period}の行動目標（行動管理・優先順位付き）】\n" + OK_ACTIONS
    )
    assert _rc(text) == 0


def test_weekly_file_does_not_pick_period_anchor_sections():
    """週報の中の期アンカー（今期）の節を、今週の照合対象に混ぜない。"""
    text = (
        "## 【今期の売上以外の成果目標】\n"
        "- 期の成果：成約9件　期日9/27\n  → 売上貢献：0（期の見込み）\n\n"
        "## 【今週の売上以外の成果目標】\n"
        "- 継続コンサル：成約3件　期日10/25\n  → 売上貢献：0（継続の見込み）\n\n"
        "## 【今週の行動目標（行動管理・優先順位付き）】\n" + OK_ACTIONS
    )
    assert _rc(text) == 0


def test_note_lines_are_not_counted_as_items():
    text = _doc(
        OK_OUTCOMES,
        "（※ 実行する順番は期日の早い順に読む）\n" + OK_ACTIONS,
    )
    out = _out(text)
    assert _rc(text) == 0
    assert "行動目標の項目数: 1" in out


# --- CLI ---

def test_main_rc2_on_missing_file(tmp_path):
    assert vgl.main(["--file", str(tmp_path / "nope.md")]) == 2


def test_main_rc2_on_missing_required_arg():
    assert vgl.main([]) == 2


def test_main_help_is_rc0():
    assert vgl.main(["--help"]) == 0


def test_main_prints_args_and_measured_at(tmp_path, capsys):
    p = tmp_path / MONTHLY_NAME
    p.write_text(_doc(OK_OUTCOMES, OK_ACTIONS), encoding="utf-8")
    rc = vgl.main(["--file", str(p)])
    captured = capsys.readouterr().out
    assert rc == 0
    assert "MEASURED_AT: " in captured
    assert "ARGS: --file " in captured


def test_main_worst_rc_across_files(tmp_path):
    ok = tmp_path / "ok.md"
    ok.write_text(_doc(OK_OUTCOMES, OK_ACTIONS), encoding="utf-8")
    bad = tmp_path / "bad.md"
    bad.write_text(
        _doc(OK_OUTCOMES, "### → 別の成果：x（0円）\n- [ ] 提示する　期日10/22\n"),
        encoding="utf-8",
    )
    assert vgl.main(["--file", str(ok), "--file", str(bad)]) == 1


def test_rc2_still_prints_measured_at_and_args(tmp_path, capsys):
    assert vgl.main(["--file", str(tmp_path / "nope.md")]) == 2
    captured = capsys.readouterr().out
    assert "MEASURED_AT: " in captured
    assert "ARGS: --file " in captured


# --- 1ファイル2セクション構成（月報） ---

def _two_section_doc(detail_action_body: str, *, with_detail: bool = True,
                     detail_label: str = "# 管理用（詳細）") -> str:
    lines = ["# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25", ""]
    lines += ["# 北原さん提出用（シンプル）", ""]
    lines += [
        "## 【今月の売上以外の成果目標（提出）】",
        "- 有料コンサル：成約3件　期日10/25",
        "  → 売上貢献：50000 × 3 = 150000",
        "",
        "## 【今月の行動目標（提出）】",
        "- 有料コンサルの条件を12件提示する　期日10/22",
        "",
    ]
    if with_detail:
        lines += [detail_label, ""]
        lines += [
            HEAD_OUTCOME,
            "- 有料コンサル：成約3件　期日10/25",
            "  → 売上貢献：50000 × 3 = 150000",
            "",
            HEAD_ACTION,
            detail_action_body.rstrip("\n"),
            "",
        ]
    return "\n".join(lines)


DETAIL_OK = "### → 有料コンサル：成約3件（150000円）\n- [ ] 4回目の場で条件を提示する　期日10/22\n"


def test_split_groups_returns_one_group_without_group_headings():
    groups = vgl.split_groups(_doc(OK_OUTCOMES, OK_ACTIONS))
    assert len(groups) == 1
    assert groups[0][0] == ""


def test_split_groups_splits_submission_and_detail():
    groups = vgl.split_groups(_two_section_doc(DETAIL_OK))
    assert [label for label, _ in groups] == ["北原さん提出用（シンプル）", "管理用（詳細）"]
    assert "管理用" not in groups[0][1]
    assert "（提出）" not in groups[1][1]


def test_submission_suffixed_headings_are_out_of_scope():
    """提出用の見出しだけを渡すと分母0（rc=3）になる（見出しの側で対象外）。"""
    text = (
        "## 【今月の売上以外の成果目標（提出）】\n"
        "- 有料コンサル：成約3件　期日10/25\n  → 売上貢献：50000 × 3 = 150000\n\n"
        "## 【今月の行動目標（提出）】\n"
        "- 有料コンサルの条件を12件提示する　期日10/22\n"
    )
    assert _rc(text) == 3


def test_two_sections_detail_resolved_is_rc0(tmp_path, capsys):
    p = tmp_path / MONTHLY_NAME
    p.write_text(_two_section_doc(DETAIL_OK), encoding="utf-8")
    assert vgl.main(["--file", str(p)]) == 0
    assert "SKIP: 提出用セクションは照合対象外" in capsys.readouterr().out


def test_detail_break_is_still_rc1_in_two_section_file(tmp_path):
    p = tmp_path / MONTHLY_NAME
    p.write_text(
        _two_section_doc("### → 有料相談：成約3件（150000円）\n- [ ] 条件を提示する　期日10/22\n"),
        encoding="utf-8",
    )
    assert vgl.main(["--file", str(p)]) == 1


def test_submission_only_file_is_rc3_not_rc0(tmp_path, capsys):
    p = tmp_path / MONTHLY_NAME
    p.write_text(_two_section_doc("", with_detail=False), encoding="utf-8")
    assert vgl.main(["--file", str(p)]) == 3
    assert "照合を実施したグループ 0 件" in capsys.readouterr().out


def test_group_label_typo_is_detected(tmp_path):
    p = tmp_path / MONTHLY_NAME
    p.write_text(_two_section_doc(DETAIL_OK, detail_label="# 詳細（管理用）"), encoding="utf-8")
    assert vgl.main(["--file", str(p)]) == 1


def test_group_label_issues_lists_only_the_deviating_heading():
    good = "# 北原さん提出用（シンプル）\n# 管理用（詳細）\n"
    bad = "# 北原さん提出用（シンプル）\n# 詳細（管理用）\n"
    assert vgl.group_label_issues(good) == []
    assert vgl.group_label_issues(bad) == ["# 詳細（管理用）"]


def test_title_heading_is_not_treated_as_group_label():
    assert vgl.group_label_issues("# UBM - 1-週報 - 2026-09-28〜2026-10-04\n") == []


# --- 規則の共用（二重実装しない） ---

def test_rules_are_shared_with_validator():
    """一致判定とキーの切り出しは validator の実装そのものを使う。"""
    assert vgl.Validator._ref_matches_key("継続 コンサル", "継続コンサル")
    assert not vgl.Validator._ref_matches_key("継続", "継続コンサル")
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "validate-goal-output.py" in src
    assert "def _outcome_key" not in src
    assert "def _ref_matches_key" not in src


def test_no_emoji_in_script_source():
    src = _SCRIPT.read_text(encoding="utf-8")
    for ch in src:
        assert not (0x1F300 <= ord(ch) <= 0x1FAFF), ch
        assert ord(ch) not in (0x2705, 0x274C, 0x2B50), ch


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
