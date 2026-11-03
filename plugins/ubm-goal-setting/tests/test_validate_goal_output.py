"""validate-goal-output.py (C01) の保存前バリデーションテスト。

同梱 golden-sample-weekly.md を正本として PASS を確認し、各違反変異が FAIL する
ことを検証する (旧 validate-goal-output.sh の契約移植の等価性確認)。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "skills/run-ubm-goal-setting/scripts/validate-goal-output.py"
GOLDEN = PLUGIN_ROOT / "skills/run-ubm-goal-setting/assets/golden-sample-weekly.md"

WEEKLY_NAME = "UBM - 1-週報 2026-06-29〜2026-07-05.md"


def run(path: Path, type_: str, peers: list[Path] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(VALIDATE), "--file", str(path), "--type", type_]
    for p in peers or []:
        cmd += ["--peer", str(p)]
    return subprocess.run(cmd, capture_output=True, text=True)


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.fixture
def golden_text() -> str:
    return GOLDEN.read_text(encoding="utf-8")


MANAGED_ACTION_HEAD = "## 【今週の行動目標（行動管理・優先順位付き）】"


def managed_action_lines(text: str) -> list[str]:
    """管理用の行動目標セクションのチェックボックス行。手本の行の文言には依存しない。"""
    lines = text.split("\n")
    start = lines.index(MANAGED_ACTION_HEAD) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return [l for l in lines[start:end] if l.startswith("- [ ] ")]


def replace_first_managed_action(text: str, new_line: str) -> str:
    first = managed_action_lines(text)[0]
    return text.replace(first, new_line, 1)


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
            out.append("- [ ] 連絡：毎日頑張る　期日毎日")
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
    # 入力を読めないのは検査の FAIL (1) ではなく呼び出しの誤り (2)。validate-goal-linkage と揃える。
    r = run(tmp_path / "nope.md", "weekly")
    assert r.returncode == 2
    assert "Traceback" not in r.stderr


def test_invalid_type_usage(tmp_path: Path, golden_text: str):
    # 未知の種別は検査せず usage エラー（rc=2）で落とす。黙って既定種別へ寄せると、
    # 打ち間違えた種別で「PASS」が返り、別種別の必須見出しが検査されないまま通る。
    # `annual` は `yearly` の言い換えとして打ちそうな語だが、受理語ではない。
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(p), "--type", "annual"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


def test_yearly_type_is_accepted(tmp_path: Path, golden_text: str):
    # `yearly`（4層の最上位）は受理語。週報本文を渡しているので内容は FAIL するが、
    # それは rc=1（検査して落ちた）であって rc=2（種別を知らないので検査していない）
    # ではない。この2つを混ぜると、yearly の必須見出しが一度も当たらないまま
    # 「通らないのは種別が無いからだ」と読み違える。
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(p), "--type", "yearly"],
        capture_output=True, text=True,
    )
    assert r.returncode == 1, r.stdout
    assert "1年の目標" in r.stdout


def test_weekly_title_mismatch_fails(tmp_path: Path, golden_text: str):
    # 週報本文の「1週間の目標」を月報ラベルへ差し替え → --type weekly と不一致で FAIL
    text = golden_text.replace("## 【1週間の目標】", "## 【1ヶ月の目標】", 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1, r.stdout
    assert "1ヶ月の目標" in r.stdout


# --- 期報の種別取り違え検出 (quarterly=3ヶ月 / bimonthly=2ヶ月) ---

PERIOD_NAME = "UBM - 3-月報（３ヶ月） 2026-06-29〜2026-09-27.md"
INITIAL_MARKER = "初回（前回正本なし）"

PERIOD_REQUIRED = [
    "確認された情報", "今期の累計売上実績", "前期の売上目標", "前期の売上実績",
    "前期の売上目標と実績の差分", "前期の売上に対して未達を挽回するための行動",
    "前期の売上以外の成果目標", "前期の売上以外の成果実績",
    "前期の売上以外の成果に対して未達を挽回するための行動", "前期の売上以外の成果目標と実績の差分",
    "前期の行動目標（行動管理）", "前期の行動実績（行動管理）", "前期の行動目標と実績の差分",
    "前期の行動に対して未達を挽回するための行動", "今期の売上目標", "今期の売上以外の成果目標",
    "今期の行動目標（行動管理・優先順位付き）", "現在事業パートナー数", "現在のグリッドパートナー数",
    "今期やらないこと（明確に排除するもの）", "今期末の振り返りチェックリスト", "事業の柱",
]


def period_text(title_label: str, anchors: dict[str, str] | None = None,
                amount: int = 600000) -> str:
    """種別ラベルだけが異なる最小の期報本文。ラベル照合の分岐だけを固定する。

    `anchors` を渡すと該当見出しの本文をその値に差し替える (層間整合テスト用)。
    `amount` は成果目標の売上貢献額。売上目標・成果目標の式・行動目標グループ見出しの
    3か所へ同じ値を配る。逆算チェーンの突合 (C3) と見出し金額の一致 (C4b) は
    「3か所が同じ値であること」を要求するので、テスト側でもここを1つの変数に束ねて
    おかないと、片方だけ直したときに層間整合と無関係の FAIL でテストが落ちる。
    """
    anchors = anchors or {}
    parts = [f"## 【{title_label}】 2026-06-29〜2026-09-27", "", "本文", ""]
    for lbl in PERIOD_REQUIRED:
        parts.append(f"## 【{lbl}】")
        parts.append("")
        if lbl in anchors:
            parts.append(anchors[lbl])
        elif lbl.startswith("前期"):
            # 前回ブロックは初回（前回正本なし）。各欄にマーカー1行を置く（空欄は転記漏れで FAIL）。
            parts.append(f"- {INITIAL_MARKER}")
        elif lbl == "今期やらないこと（明確に排除するもの）":
            parts += ["- 交流会に参加しない", "- 無料の勉強会をやらない", "- 新しい商品を作らない"]
        elif lbl == "今期の売上目標":
            parts.append(str(amount))
        elif lbl == "今期の売上以外の成果目標":
            # 項目名（「：」より前）に個人名を入れない。対象の人は本文に書く。
            parts += [
                "- 提案の受諾：青木さんの受諾1件　期日7/6",
                f"  → 売上貢献：{amount} × 1 = {amount}",
            ]
        elif lbl == "今期の行動目標（行動管理・優先順位付き）":
            parts += [
                f"### → 提案の受諾：青木さんの受諾（{amount}円）",
                "- [ ] 提案：青木さんへ提案を1件出す　期日7/6",
            ]
        else:
            parts.append("本文")
        parts.append("")
    if "今期の最重要数字" in anchors:
        # 最重要数字は売上の1行（【今期の売上目標】の写し）と、その売上に至る件数で書く。
        # 売上目標を差し替えるテストでも写しがずれないよう、ここで同じ値から作る。
        target = anchors.get("今期の売上目標", str(amount)).replace(",", "")
        parts += ["## 【今期の最重要数字】", "", f"今期の売上目標：{target}",
                  anchors["今期の最重要数字"], ""]
    return "\n".join(parts) + "\n"


def test_quarterly_type_with_3month_label_passes(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標"))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout


def test_bimonthly_type_with_2month_label_passes(tmp_path: Path):
    # 旧2ヶ月期報を旧種別で再検証する経路は壊さない (読みの後方互換)
    p = write(tmp_path, PERIOD_NAME, period_text("2ヶ月の目標"))
    r = run(p, "bimonthly")
    assert r.returncode == 0, r.stdout


def test_quarterly_type_with_2month_label_fails(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("2ヶ月の目標"))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "ファイル側が旧種別" in r.stdout


def test_bimonthly_type_with_3month_label_fails(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標"))
    r = run(p, "bimonthly")
    assert r.returncode == 1, r.stdout
    assert "引数側が旧種別" in r.stdout


# --- 層間整合チェック (--peer) ---

ANCHORS_OK = {
    "今期の売上目標": "1,000,000",
    "今期の累計売上実績": "630,000",
    "今期の最重要数字": "困りごとを解決した件数：6件",
}
# ANCHORS_OK の売上目標に合わせた貢献額。逆算チェーン（売上貢献の合計 = 売上目標）を
# 満たしておく。ここが崩れると層間整合ではなくチェーン側の FAIL でテストが落ちる。
ANCHOR_AMOUNT = 1000000
PEER_NAME = "UBM - 2-月報（１ヶ月） 2026-08-31〜2026-09-27.md"


def test_peer_absent_keeps_current_behavior(tmp_path: Path):
    """--peer 未指定なら層間整合チェックは走らず、結果も従来どおり。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "層間整合チェック" not in r.stdout
    assert "層間比較" not in r.stdout


def test_peer_matching_anchors_no_warning(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    peer = write(tmp_path, PEER_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_peer_mismatched_anchors_warns_but_rc_zero(tmp_path: Path):
    """値がズレても FAIL にしない (継承は作成時 pull のみで必ず1回ズレる系)。"""
    mine = dict(ANCHORS_OK, **{"今期の売上目標": "600,000"})
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", mine))
    peer = write(tmp_path, PEER_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout
    assert "WARN: 層間の値ズレ: 今期の売上目標 対象=600000" in r.stdout
    assert "peer(" + PEER_NAME + ")=1000000" in r.stdout
    assert "層間比較: 比較2項目中 不一致1件" in r.stdout


def test_peer_zero_compared_is_distinguishable(tmp_path: Path):
    """比較対象が0件のときは「比較0項目」と印字し、不一致0件と区別できるようにする。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    peer = write(tmp_path, "peer-empty.txt", "## 【関係のない見出し】\n本文\n")
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "層間比較: 比較0項目中 不一致0件" in r.stdout
    assert "比較できる項目が1件もありませんでした" in r.stdout
    assert "層間の値ズレ" not in r.stdout


KEY_NUMBER_SKIP = (
    "SKIP: 最重要数字（各層の売上とその内訳のため一致検査の対象外。"
    "1年の到達点は validate-cross-level.py で照合）"
)


def monthly_peer_text(sales: str, cumulative: str, key_number: str) -> str:
    """peer 側にだけ使う最小の月報本文（peer は検証対象ではなく値の取り出しのみ）。"""
    return "\n".join([
        "## 【1ヶ月の目標】 2026-08-31〜2026-09-27", "", "本文", "",
        "## 【今期の売上目標】", "", sales, "",
        "## 【今期の累計売上実績】", "", cumulative, "",
        "## 【今月の最重要数字】", "", key_number, "",
    ]) + "\n"


def test_peer_monthly_skips_key_number(tmp_path: Path):
    """月報 peer も最重要数字は比べない（金額2項目だけ）。

    月報の最重要数字は当月の売上（`今月の売上目標：`）とその内訳で、期報の値とは違うのが
    正しい（確定事項Q）。期報側と違う値を置いても WARN が出ないことで、比べていないことを固定する。
    """
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    peer = write(tmp_path, PEER_NAME,
                 monthly_peer_text("1,000,000", "630,000", "今月の売上目標：400000"))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert KEY_NUMBER_SKIP in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_peer_weekly_skips_key_number(tmp_path: Path, golden_text: str):
    """週報 peer の最重要数字は上位の内訳なので比較対象外（分母からも落ちる）。

    golden 週報の最重要数字は期報側と別物なので、除外していなければ必ず WARN が出る。
    ここが静かなことで誤検出の再発を止める。
    """
    anchors = dict(ANCHORS_OK, **{
        "今期の売上目標": "1,200,000",
        "今期の累計売上実績": "520,000",
    })
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", anchors, 1200000))
    peer = write(tmp_path, WEEKLY_NAME, golden_text)
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert KEY_NUMBER_SKIP in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_weekly_file_with_period_peer_skips_key_number(tmp_path: Path, golden_text: str):
    """--file 側が週報のときも同じく除外する（--type weekly を階層の正本にする）。"""
    anchors = dict(ANCHORS_OK, **{
        "今期の売上目標": "1,200,000",
        "今期の累計売上実績": "520,000",
    })
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    peer = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", anchors, 1200000))
    r = run(p, "weekly", [peer])
    assert r.returncode == 0, r.stdout
    assert KEY_NUMBER_SKIP in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def key_number_period(sales_line: str | None) -> str:
    """【今期の最重要数字】の売上の行だけを差し替えた期報（他は ANCHORS_OK のまま）。"""
    text = period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT)
    lines = text.split("\n")
    i = lines.index("今期の売上目標：1000000")
    if sales_line is None:
        del lines[i]
    else:
        lines[i] = sales_line
    return "\n".join(lines)


def test_key_number_sales_line_matches_target(tmp_path: Path):
    """期報の最重要数字にある売上の行が【今期の売上目標】と同じ値なら PASS（確定事項T）。"""
    p = write(tmp_path, PERIOD_NAME, key_number_period("今期の売上目標：1,000,000円"))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "PASS: 【今期の最重要数字】の売上の行が【今期の売上目標】と一致（1000000）" in r.stdout


def test_key_number_sales_line_mismatch_fails(tmp_path: Path):
    """写し間違い（売上目標 1000000 に対して 900000）を FAIL にする。"""
    p = write(tmp_path, PERIOD_NAME, key_number_period("今期の売上目標：900000"))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "`今期の売上目標：900000` が【今期の売上目標】の 1000000 と違う" in r.stdout


def test_key_number_without_sales_line_fails(tmp_path: Path):
    """節を置いたのに売上の行が無い（人数・件数だけ）なら FAIL にする。"""
    p = write(tmp_path, PERIOD_NAME, key_number_period(None))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "【今期の最重要数字】に `今期の売上目標：{金額}` の1行が無い" in r.stdout


def test_key_number_is_optional_in_quarterly(tmp_path: Path):
    """期報は最重要数字を置かなくてよい（任意。照合も警告もしない）。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", amount=ANCHOR_AMOUNT))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "最重要数字】が無い" not in r.stdout
    assert "最重要数字】の売上の行" not in r.stdout


def _validator_class():
    import importlib.util
    script = PLUGIN_ROOT / "skills/run-ubm-goal-setting/scripts/validate-goal-output.py"
    spec = importlib.util.spec_from_file_location("validate_goal_output_mod", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Validator


def test_monthly_key_number_sales_line(capsys):
    """月報は同じ照合をし、節そのものが無いときは WARN にとどめる（確定事項Q）。"""
    validator = _validator_class()
    base = ["## 【今月の売上目標】", "", "600000", ""]
    cases = [
        (["## 【今月の最重要数字】", "", "今月の売上目標：600000", "件数：3件", ""], 0, 0),
        (["## 【今月の最重要数字】", "", "今月の売上目標：500000", "件数：3件", ""], 1, 0),
        ([], 0, 1),
        # 行頭の記号は validate-cross-level.py と同じく読み飛ばす
        (["## 【今月の最重要数字】", "", "- 今月の売上目標：600000", ""], 0, 0),
        (["## 【今月の最重要数字】", "", "- [ ] 今月の売上目標：600000", ""], 0, 0),
        (["## 【今月の最重要数字】", "", "・今月の売上目標：500000", ""], 1, 0),
        # 節は在るが売上の行が無い
        (["## 【今月の最重要数字】", "", "件数：3件", ""], 1, 0),
    ]
    for key_number, errors, warnings in cases:
        v = validator("\n".join(base + key_number), "x.md", "month")
        v.check_key_number_sales_line()
        assert (v.errors, v.warnings) == (errors, warnings), capsys.readouterr().out


def test_key_number_sales_line_skips_week_and_year(capsys):
    """週報・1年は最重要数字の書き方が違うので、売上の行の照合をしない。"""
    validator = _validator_class()
    for kind, word in (("week", "今週"), ("year", "今年")):
        text = "\n".join([f"## 【{word}の最重要数字】", "", "- [ ] 件数：3件", ""])
        v = validator(text, "x.md", kind)
        v.check_key_number_sales_line()
        assert (v.errors, v.warnings) == (0, 0), capsys.readouterr().out


def test_peer_missing_file_errors(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    r = run(p, "quarterly", [tmp_path / "nope.md"])
    assert r.returncode == 2


def test_duplicate_heading_fails(tmp_path: Path, golden_text: str):
    # 既存見出しを複製 → 重複見出しで FAIL
    p = write(tmp_path, WEEKLY_NAME, golden_text + "\n## 【今週の判断基準】\n本文\n")
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "重複" in r.stdout


# --- 手本に依存しない最小の週報（逆算チェーン以降の検査の土台）---
#
# 手本（golden）は別レーンで書き換わる。文言を置換して作る変異テストを手本に載せると、
# 手本の文言が変わったときに置換が空振りし、検査していないのに通る（偽 PASS）。
# 文言に依存する変異はこの最小の週報に載せ、置換元が無ければ mutate() が落とす。

DEFAULT_ACTION_LINES = [
    "### → 提案の受諾：Bさんの受諾（100000円）",
    "- [ ] 診断実施：体験診断を実施する　期日6/30",
    "- [ ] 判断確認：判断の期日を確認する　期日7/3",
    "",
    "### → 月額顧問の成約：Aさんの成約（50000円）",
    "- [ ] 提案書提出：提案書を提出する　期日7/2",
]
DEFAULT_DATE_INDEX = [
    "- 6/30（火）：診断実施｜やらない：診断だけで提案をせずに終えること",
    "- 7/1（水）：なし｜やらない：返信のない相手への深追い",
    "- 7/2（木）：提案書提出",
    "- 7/3（金）：判断確認",
]
DEFAULT_RECOVERY = ["- 初回提案：診断当日の提示0件→1件（今回の行動目標「診断実施」で実行）"]

OUTCOME_A = "- 月額顧問の成約：Aさんの成約1件（初月分）　期日7/2"
OUTCOME_B = "- 提案の受諾：Bさんの受諾1件　期日7/3"
CONTRIB_A = "  → 売上貢献：50000 × 1 = 50000"
CONTRIB_B = "  → 売上貢献：100000 × 1 = 100000"
GROUP_A = "### → 月額顧問の成約：Aさんの成約（50000円）"
GROUP_B = "### → 提案の受諾：Bさんの受諾（100000円）"
ACTION_A = "- [ ] 提案書提出：提案書を提出する　期日7/2"
# 貢献0の中間成果2件（形1・形2）。足すと成果目標は4件で、うち0は2件（過半ではない）。
ZERO_OUTCOMES = [
    "- 説明日程の合意：Aさんの合意1件　期日6/30", "  → 売上貢献：0（月額顧問の成約を支える）", "",
    "- 体験診断の申込：新規の申込2件　期日7/5", "  → 売上貢献：0（7月の提案の受諾を支える）", "",
]


def weekly_text(revision: str | None = "- なし", prev_outcome_diff: list[str] | None = None,
                prev_action: list[str] | None = None, action_lines: list[str] | None = None,
                extra_outcomes: list[str] | None = None, extra: str = "",
                recovery: list[str] | None = None, date_index: list[str] | None = None) -> str:
    """検査を通る最小の週報本文。手本（golden）の書き換えと独立に、検査の契約だけを固定する。

    行動行は `- [ ] 項目名：何をする　期日{トークン}`。項目名（「：」より前）に個人名は入れない。
    前週ブロック12見出しは項目名で1対1に揃え、挽回は対応行、【今週の大きな到達ライン】は日付索引。
    `revision=None` なら【今週の見直し記録】を置かない。`recovery` は
    【前週の行動に対して未達を挽回するための行動】の行（`[]` なら空の欄）。`date_index=[]` なら
    【今週の大きな到達ライン】を置かない。
    """
    prev_outcome_diff = prev_outcome_diff or ["- 継続申込：±0件", "- 月額顧問の提案受諾：-1件"]
    prev_action = prev_action or ["- 個別メッセージ：個別メッセージを15件送る　期日6/26",
                                  "- 初回提案：Aさんへ初回提案を提示する　期日6/26"]
    action_lines = action_lines or DEFAULT_ACTION_LINES
    recovery = DEFAULT_RECOVERY if recovery is None else recovery
    date_index = DEFAULT_DATE_INDEX if date_index is None else date_index
    parts = [
        "## 【1週間の目標】2026-06-29〜2026-07-05", "本文", "",
        "## 【前週の売上目標】", "200000", "",
        "## 【前週の売上実績】", "150000", "",
        "## 【前週の売上目標と実績の差分】", "-50000", "",
        "## 【前週の売上に対して未達を挽回するための行動】",
        "- 月額顧問の提案受諾：提案書の提出0件→1件（今回の行動目標「提案書提出」で実行）", "",
        "## 【前週の売上以外の成果目標】",
        "- 継続申込：Bさんの体験診断からの継続申込1件　期日6/27", "  → 売上貢献：150000 × 1 = 150000", "",
        "- 月額顧問の提案受諾：Aさんの受諾1件　期日6/26", "  → 売上貢献：50000 × 1 = 50000", "",
        "## 【前週の売上以外の成果実績】", "- 継続申込：1件・完了6/27", "- 月額顧問の提案受諾：0件", "",
        "## 【前週の売上以外の成果目標と実績の差分】", *prev_outcome_diff, "",
        "## 【前週の売上以外の成果に対して未達を挽回するための行動】",
        "- 月額顧問の提案受諾：判断期日の確認0件→1件（今回の行動目標「判断確認」で実行）", "",
        "## 【前週の行動目標（行動管理）】", *prev_action, "",
        "## 【前週の行動実績（行動管理）】", "- 個別メッセージ：10件送った", "- 初回提案：0件だった", "",
        "## 【前週の行動目標と実績の差分】",
        "- 個別メッセージ：-5件（15件 → 10件）", "- 初回提案：-1件（1件 → 0件）", "",
        "## 【前週の行動に対して未達を挽回するための行動】", *recovery, "",
        "## 【現在のグリッドパートナー数】", "2", "",
        "## 【今週の最重要数字】", "- [ ] 今週の売上：150000", "- [ ] 提案の受諾・月額顧問の成約：2件", "",
        "## 【今週の売上目標】", "150000", "",
        "## 【今週の売上以外の成果目標】",
        OUTCOME_B, CONTRIB_B, "",
        OUTCOME_A, CONTRIB_A, "",
        *(extra_outcomes or []),
    ]
    if date_index:
        parts += ["## 【今週の大きな到達ライン】", *date_index, ""]
    parts += [MANAGED_ACTION_HEAD, *action_lines, ""]
    if revision is not None:
        parts += ["## 【今週の見直し記録】", revision, ""]
    parts += [
        "## 【習慣目標（仕組みで動く土台）】",
        *[f"- [ ] 習慣{n}を毎日チェックする" for n in range(1, 7)], "",
        "## 【今週の判断基準】", "- 次回の約束が増えたか", "",
    ]
    return "\n".join(parts) + "\n" + extra


def mutate(base: str, old: str, new: str) -> str:
    """`old` を `new` に置き換える。`old` がちょうど1か所に無ければ落とす。

    無いのに通すと置換の空振りで偽 PASS になり、2か所以上あると前週ブロックの転記行のような
    意図しない側を書き換える（前週と今週で同じ式が並ぶため）。
    """
    assert base.count(old) == 1, f"置換元が本文にちょうど1か所ありません（{base.count(old)} か所）: {old!r}"
    return base.replace(old, new, 1)


def with_contribution_a(new_line: str) -> str:
    """今週の成果目標「月額顧問の成約」の売上貢献の行だけを差し替える（前週ブロックに同じ式がある）。"""
    return mutate(weekly_text(), OUTCOME_A + "\n" + CONTRIB_A, OUTCOME_A + "\n" + new_line)


def drop_section(text: str, label: str) -> str:
    """`## 【{label}】` の見出しと本文（次の `## ` の手前まで）を取り除く。"""
    out, skipping, found = [], False, False
    for line in text.split("\n"):
        if line.startswith("## "):
            skipping = line == f"## 【{label}】"
            found = found or skipping
        if not skipping:
            out.append(line)
    assert found, label
    return "\n".join(out)


def previous_as_initial(text: str, word: str = "前週") -> str:
    """前回ブロックの各欄（`## 【{word}…】`）の本文を初回マーカー1行に置き換える。"""
    out, skipping = [], False
    for line in text.split("\n"):
        if line.startswith("## "):
            skipping = line.startswith(f"## 【{word}")
            out.append(line)
            if skipping:
                out += [f"- {INITIAL_MARKER}", ""]
            continue
        if not skipping:
            out.append(line)
    return "\n".join(out)


def test_minimal_weekly_passes(tmp_path: Path):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text()), "weekly")
    assert r.returncode == 0, r.stdout
    assert "前期間の項目一致" not in r.stdout
    assert "挽回の対応行 3 行を照合しました" in r.stdout
    assert "日付索引 4 行を照合しました" in r.stdout
    assert "行動目標 3 行の行末に期日あり" in r.stdout


# --- 逆算チェーン（売上 → 成果 → 行動）---


def test_outcome_without_sales_contribution_fails(tmp_path: Path):
    # 成果目標から「→ 売上貢献：<式>」の行を落とす → 成果と売上の線が引けていないので FAIL
    text = mutate(weekly_text(), OUTCOME_A + "\n" + CONTRIB_A, OUTCOME_A)
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "成果目標に「→ 売上貢献：<単価> × <件数> = <貢献額>」がありません" in r.stdout


def test_sales_contribution_arithmetic_mismatch_fails(tmp_path: Path):
    # 単価 × 件数 と貢献額が合わない → 誰も検算できない数字なので FAIL
    text = with_contribution_a("  → 売上貢献：50000 × 2 = 50000")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "売上貢献の式が合っていません" in r.stdout


def test_bare_contribution_amount_fails(tmp_path: Path):
    """裸の数字だけの貢献額は FAIL（検算できない数字を通さない）。

    式で書いた人だけが検算 FAIL を負い、根拠を出さなかった人が免除される
    非対称を防ぐための検査。
    """
    text = mutate(weekly_text(), CONTRIB_B, "  → 売上貢献：100000")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_contribution_with_parenthesized_basis_passes(tmp_path: Path):
    """単価 × 件数へ分解できない成果は、括弧の根拠で通る（式は必須ではない）。"""
    text = mutate(weekly_text(), CONTRIB_B, "  → 売上貢献：100000（値引き後の一括見積）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "売上貢献に式または括弧の根拠がありません" not in r.stdout


def test_contribution_with_empty_parenthesis_fails(tmp_path: Path):
    """中身の無い括弧は根拠ではない（形だけ通す抜け道を塞ぐ）。"""
    text = mutate(weekly_text(), CONTRIB_B, "  → 売上貢献：100000（）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_multi_month_contribution_fails(tmp_path: Path):
    """件数に期間単位が付いた式は FAIL（今週入らない金銭を今週の売上に立てない）。"""
    text = with_contribution_a("  → 売上貢献：50000 × 1ヶ月 = 50000")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "売上貢献の件数に期間単位「ヶ月」が付いています" in r.stdout
    assert "初月分だけを計上" in r.stdout


@pytest.mark.parametrize("unit", ["ヶ月", "ヵ月", "か月", "月", "年"])
def test_period_units_all_fail(tmp_path: Path, unit: str):
    text = with_contribution_a(f"  → 売上貢献：50000 × 1{unit} = 50000")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert f"期間単位「{unit}」" in r.stdout


@pytest.mark.parametrize("unit", ["件", "名", "回", "本"])
def test_count_units_pass(tmp_path: Path, unit: str):
    """件・名・回・本は今期間に確定する数え方なので通す。"""
    text = with_contribution_a(f"  → 売上貢献：50000 × 1{unit} = 50000")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "期間単位" not in r.stdout


def test_group_heading_amount_mismatch_fails(tmp_path: Path):
    """グループ見出しの金額が成果目標の貢献額と食い違ったら FAIL。"""
    text = mutate(weekly_text(), GROUP_A, "### → 月額顧問の成約：Aさんの成約（9999999円）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "行動目標グループの金額が成果目標の貢献額と違います" in r.stdout
    assert "見出し 9999999 / 成果目標「月額顧問の成約」50000" in r.stdout


def test_group_heading_amount_with_comma_passes(tmp_path: Path):
    """見出しの金額は `,` 区切りでも同じ値として扱う（表記差で落とさない）。"""
    text = mutate(weekly_text(), GROUP_A, "### → 月額顧問の成約：Aさんの成約（50,000円）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "行動目標グループの金額" not in r.stdout


def test_group_heading_without_amount_is_exempt(tmp_path: Path):
    """金額の無い見出しは検査対象外（成果に紐づかない免除グループ）。"""
    text = mutate(weekly_text(), GROUP_A, "### → 月額顧問の成約：Aさんの成約")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "行動目標グループの金額" not in r.stdout


def test_mostly_zero_contribution_warns(tmp_path: Path):
    # 貢献 0 が過半（4件中3件）→ 今期間の売上から逆算できていないので WARN
    text = mutate(weekly_text(extra_outcomes=ZERO_OUTCOMES), CONTRIB_B, "  → 売上貢献：0（8月計上・提案の受諾分）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert "売上貢献 0 の成果目標が 3/4 件です" in r.stdout


def test_zero_contribution_minority_does_not_warn(tmp_path: Path):
    # 4件中2件が 0（ちょうど半分）→ 過半ではないので WARN は出さない
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(extra_outcomes=ZERO_OUTCOMES)), "weekly")
    assert r.returncode == 0, r.stdout
    assert "売上貢献 0 の成果目標が" not in r.stdout


def test_zero_contribution_without_reason_fails(tmp_path: Path, golden_text: str):
    # 貢献 0 に括弧の根拠（何を支えるか／何月に計上するか）が無い → FAIL
    # 0 専用の検査ではなく、「式か括弧の根拠が要る」という一般規則で落ちる
    text = re.sub(r"(?m)^  → 売上貢献：0（[^）\n]*）$", "  → 売上貢献：0", golden_text, count=1)
    assert text != golden_text
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_execution_type_outcome_fails(tmp_path: Path):
    # 「実行した時点で達成になる目標」を成果目標に置く → FAIL
    text = mutate(weekly_text(), OUTCOME_A, "- 勉強会：月4回開催する　期日7/2")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "実行完了型" in r.stdout


def test_action_without_outcome_link_fails(tmp_path: Path):
    # 先頭のグループ見出しを落とす → 配下の行動がどの成果に属するか分からなくなり FAIL
    text = mutate(weekly_text(), GROUP_B + "\n", "")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "どの成果目標に属するか" in r.stdout


def test_action_dangling_outcome_reference_fails(tmp_path: Path):
    # グループ見出しが成果目標セクションに存在しない名前を指す → FAIL
    text = mutate(weekly_text(), GROUP_A, "### → 存在しない成果：Aさんの成約（50000円）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "実在しない成果目標" in r.stdout


def test_foundation_reference_is_exempt(tmp_path: Path):
    # （土台）／（関係維持）は成果への紐づけを免除される
    text = mutate(weekly_text(), GROUP_A, "### → （関係維持）")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert "実在しない成果目標" not in r.stdout
    assert "どの成果目標に属するか" not in r.stdout


# --- シンプルさゲート（件数・長さ・1項目1成果）---


def test_too_many_outcome_items_fails(tmp_path: Path):
    # 最小の週報の2件に4件足して6件にする（上限5件）→ FAIL
    extra = ZERO_OUTCOMES + [
        "- 見積の承諾：Dさんの承諾1件　期日7/4", "  → 売上貢献：0（8月計上・見積の承諾分）", "",
        "- 面談の設定：Eさんの面談1件　期日7/4", "  → 売上貢献：0（見積の承諾を支える）", "",
    ]
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(extra_outcomes=extra)), "weekly")
    assert r.returncode == 1
    assert "上限5件" in r.stdout


def test_long_outcome_item_fails(tmp_path: Path):
    # 成果目標1項目を50字超にする → FAIL
    text = mutate(weekly_text(), OUTCOME_B,
                  "- 提案の受諾：Bさんが体験診断を経たうえで提示した業務改善の提案内容に対する社内稟議を通した正式な受諾1件　期日7/3")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "長すぎ" in r.stdout


def test_outcome_item_with_multiple_results_fails(tmp_path: Path):
    # `・` で複数の成果を1項目に詰め込む → FAIL
    text = mutate(weekly_text(), OUTCOME_B, "- 提案の受諾：Bさんの単価合意1件・受諾1件　期日7/3")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1
    assert "1項目1成果に分ける" in r.stdout


def test_long_action_item_fails(tmp_path: Path, golden_text: str):
    # 行動目標1項目を60字超にする → FAIL
    text = replace_first_managed_action(
        golden_text,
        "- [ ] 提案書提出：Aさんへ月額顧問の提案書1件を提出し、契約条件と開始月と支払い方法をすり合わせたうえで先方の決裁の期日まで握る　期日7/2",
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "長すぎ" in r.stdout


def test_too_many_action_items_fails(tmp_path: Path, golden_text: str):
    # 手本の8件に1件足して9件にする（上限8件）→ FAIL
    first = managed_action_lines(golden_text)[0]
    text = golden_text.replace(first, first + "\n- [ ] 振り返り：週次の振り返りをする　期日7/3", 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "上限8件" in r.stdout


def test_submission_action_section_is_outside_group_checks(tmp_path: Path, golden_text: str):
    # 月報の提出用セクションの行動目標（`（提出）` 付き）はグループ見出しを持たない
    # 1行1行動の規定。所属の検査（C4/C5）と件数（S3）の対象から外れることを確かめる。
    flat = "".join(f"- 連絡{n}：事業者様へ連絡を{n}件出す　期日7/{n % 5 + 1}\n" for n in range(1, 10))
    head = "## 【今週の行動目標（行動管理・優先順位付き）】"
    assert head in golden_text
    text = golden_text.replace(head, "## 【今週の行動目標（提出）】\n" + flat + "\n" + head, 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "どの成果目標に属するか" not in r.stdout
    assert "行動目標 8 件（上限8件）" in r.stdout


# --- 行動行の期日（共通部品A の期日トークン）---


def test_action_without_number_or_person_name_is_not_warned(tmp_path: Path):
    # 行動行の合格基準は「何をする＋期日」。数値・人名・誰には必須にしない。
    text = weekly_text(action_lines=[
        "### → 提案の受諾：Bさんの受諾（100000円）",
        "- [ ] 診断実施：体験診断を実施する　期日今週",
        "- [ ] 判断確認：判断の期日を確認する　期日毎日",
        "",
        "### → 月額顧問の成約：Aさんの成約（50000円）",
        "- [ ] 提案書提出：提案書を提出する　期日7/2までに",
    ]).replace("Bさん", "提案先B").replace("Aさん", "提案先A")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "WARN: 数値のない行動目標" not in r.stdout
    assert "人の名前" not in r.stdout
    assert "期日のない行動目標" not in r.stdout


@pytest.mark.parametrize("deadline", [
    "期日7/2", "期日7/2（木）", "期日 2026-07-02", "期日金曜", "期日土曜日", "期日日曜",
    "期日毎日", "期日毎朝", "期日毎週", "期日毎週金曜", "期日今週", "期日7/2まで", "期日7/2までに",
])
def test_deadline_tokens_at_line_end_pass(tmp_path: Path, deadline: str):
    text = mutate(weekly_text(), ACTION_A, f"- [ ] 提案書提出：提案書を提出する　{deadline}")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "期日のない行動目標" not in r.stdout


@pytest.mark.parametrize("line", [
    "- [ ] 提案書提出：提案書を提出する　期日毎月",           # 月の中のいつかが決まらない
    "- [ ] 提案書提出：提案書を提出する　期日今月中",
    "- [ ] 提案書提出：提案書を提出する　期日までに",         # トークンが無い
    "- [ ] 提案書提出：期日7/2に提案書を提出する",            # 期日が行末に無い
    "- [ ] 提案書提出：提案書を提出する　期日7/2　決裁の後",  # 期日の後ろに本文が続く
    "- [ ] 提案書提出：提案書を7/2に提出する",                # 期日の語が無い
])
def test_deadline_missing_or_not_at_line_end_fails(tmp_path: Path, line: str):
    r = run(write(tmp_path, WEEKLY_NAME, mutate(weekly_text(), ACTION_A, line)), "weekly")
    assert r.returncode == 1, r.stdout
    assert "期日のない行動目標があります（行末を `期日` ＋" in r.stdout
    assert line in r.stdout


def test_this_week_token_is_weekly_only(tmp_path: Path):
    # `今週` は週報だけのトークン。期報で書くと、どの週かが決まらない。
    text = mutate(period_text("3ヶ月の目標"), "- [ ] 提案：青木さんへ提案を1件出す　期日7/6",
                  "- [ ] 提案：青木さんへ提案を1件出す　期日今週")
    r = run(write(tmp_path, PERIOD_NAME, text), "quarterly")
    assert r.returncode == 1, r.stdout
    assert "期日のない行動目標があります" in r.stdout


def test_managed_action_without_deadline_fails(tmp_path: Path):
    # 期日は合格基準の半分。管理用の側に期日の無い行を置けば FAIL。
    text = mutate(weekly_text(), GROUP_B, GROUP_B + "\n- [ ] 連絡：事業者様へ連絡を3件出す")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "期日のない行動目標があります" in r.stdout
    assert "連絡：事業者様へ連絡を3件出す" in r.stdout


def test_submission_action_section_without_deadline_fails(tmp_path: Path):
    # 提出用も管理用と同じ期日を必ず書く。期日の無い提出用の行は管理用と同じく FAIL にする。
    flat = "- 条件提示：単発を月額継続へ変える条件の1枚を提示する\n"
    text = mutate(weekly_text(), MANAGED_ACTION_HEAD, "## 【今週の行動目標（提出）】\n" + flat + "\n" + MANAGED_ACTION_HEAD)
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "期日のない行動目標があります" in r.stdout


def test_submission_action_section_with_dates_passes(tmp_path: Path):
    flat = "- 条件提示：単発を月額継続へ変える条件の1枚を提示する　期日7/2\n- 定例：論点を突き合わせる　期日毎週\n"
    text = mutate(weekly_text(), MANAGED_ACTION_HEAD, "## 【今週の行動目標（提出）】\n" + flat + "\n" + MANAGED_ACTION_HEAD)
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "期日のない行動目標" not in r.stdout


def test_previous_block_lines_are_outside_deadline_check(tmp_path: Path):
    # 前回ブロックは当時のまま転記するので、期日の検査を掛けない（習慣目標も同じ）。
    text = weekly_text(prev_action=["- 個別メッセージ：個別メッセージを15件送る", "- 初回提案：Aさんへ初回提案を提示する"])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "期日のない行動目標" not in r.stdout


def test_submission_action_section_still_rejects_spirit_words(tmp_path: Path):
    # 精神論は提出用でも許さない。
    flat = "- 連絡：事業者様への連絡を頑張る　期日7/2\n"
    text = mutate(weekly_text(), MANAGED_ACTION_HEAD, "## 【今週の行動目標（提出）】\n" + flat + "\n" + MANAGED_ACTION_HEAD)
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "精神論" in r.stdout


def test_thought_and_feeling_notes_under_action_warn(tmp_path: Path):
    # 【考え】【思い】の注記は依頼されたときだけ。既定の出力に紛れ込めば知らせる（rc は変えない）。
    text = mutate(weekly_text(), ACTION_A, ACTION_A + "\n      【考え】先に費用対効果の根拠をそろえる")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "WARN: 行動目標に【考え】【思い】の注記があります" in r.stdout
    plain = run(write(tmp_path, WEEKLY_NAME, weekly_text()), "weekly")
    assert "【考え】【思い】" not in plain.stdout


# --- 貢献0の括弧3形とグループ見出しの（0円）（共通部品B）---

ZERO_OUTCOME = "- 無料相談の申込：新規の申込2件　期日7/5"


@pytest.mark.parametrize("basis", [
    "0（提案の受諾を支える）",             # 形1: 同じ文書の直接成果を支える
    "0（9月の顧問契約の成約を支える）",    # 形2: 来期以降の直接成果を支える
    "0（8月計上・顧問契約の初月分）",      # 形3: 翌期に計上する直接成果
])
def test_zero_contribution_with_supporting_or_booking_basis_passes(tmp_path: Path, basis: str):
    text = weekly_text(extra_outcomes=[ZERO_OUTCOME, f"  → 売上貢献：{basis}", ""])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "売上貢献に式または括弧の根拠がありません" not in r.stdout
    assert "貢献0の括弧は3形だけです" not in r.stdout
    assert "貢献0の支える先" not in r.stdout


def test_zero_support_target_may_be_booked_outcome(tmp_path: Path):
    # 形3（翌期に計上する直接成果）も直接成果なので、形1の支える先にできる。
    text = weekly_text(extra_outcomes=[
        "- 顧問契約の成約：Cさんの成約1件　期日7/5", "  → 売上貢献：0（8月計上・顧問契約の初月分）", "",
        ZERO_OUTCOME, "  → 売上貢献：0（顧問契約の成約を支える）", "",
    ])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "貢献0の括弧 1 件の形を照合しました（直接成果 3 件）" in r.stdout


@pytest.mark.parametrize("basis,message", [
    ("0（無料相談の準備）", "貢献0の括弧は3形だけです"),
    ("0（来月の仕込み）", "貢献0の括弧は3形だけです"),
    ("0（13月計上・顧問契約の初月分）", "貢献0の括弧は3形だけです"),
    ("0（存在しない成果を支える）", "貢献0の支える先「存在しない成果」が同じ文書の直接成果"),
])
def test_zero_contribution_outside_three_forms_fails(tmp_path: Path, basis: str, message: str):
    text = weekly_text(extra_outcomes=[ZERO_OUTCOME, f"  → 売上貢献：{basis}", ""])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert message in r.stdout


def test_zero_support_target_must_be_direct_outcome(tmp_path: Path):
    # 貢献0の中間成果は支える先にできない（直接成果までつながらない）。
    text = weekly_text(extra_outcomes=[
        "- 説明日程の合意：Aさんの合意1件　期日6/30", "  → 売上貢献：0（7月の提案の受諾を支える）", "",
        ZERO_OUTCOME, "  → 売上貢献：0（説明日程の合意を支える）", "",
    ])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "貢献0の支える先「説明日程の合意」が同じ文書の直接成果" in r.stdout


def test_zero_contribution_message_shows_supporting_and_booking_examples(tmp_path: Path):
    text = weekly_text(extra_outcomes=[ZERO_OUTCOME, "  → 売上貢献：0", ""])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    message = next(l for l in r.stdout.splitlines() if "売上貢献に式または括弧の根拠がありません" in l)
    assert "`→ 売上貢献：0（無料相談を支える）`" in message
    assert "`→ 売上貢献：0（9月の顧問契約を支える）`" in message
    assert "`→ 売上貢献：0（8月計上・顧問契約の初月分）`" in message
    assert "見込み" not in message


@pytest.mark.parametrize("bracket,passes", [("（0円）", True), ("（0円・8月の仕込み）", False), ("（0円／来月分）", False)])
def test_zero_yen_group_heading_is_bare(tmp_path: Path, bracket: str, passes: bool):
    text = weekly_text(
        extra_outcomes=[ZERO_OUTCOME, "  → 売上貢献：0（提案の受諾を支える）", ""],
        action_lines=DEFAULT_ACTION_LINES + ["", f"### → 無料相談の申込：新規の申込{bracket}",
                                             "- [ ] 案内：無料相談の案内を送る　期日7/1"],
    )
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert (r.returncode == 0) is passes, r.stdout
    assert ("0円のグループ見出しは `（0円）` だけで書いてください" in r.stdout) is not passes


# --- 前回ブロック（12見出し・初回マーカー・空欄・挽回の対応行）---


@pytest.mark.parametrize("label", [
    "前週の売上目標", "前週の売上に対して未達を挽回するための行動",
    "前週の売上以外の成果に対して未達を挽回するための行動", "前週の行動に対して未達を挽回するための行動",
])
def test_weekly_previous_block_heading_is_required(tmp_path: Path, label: str):
    r = run(write(tmp_path, WEEKLY_NAME, drop_section(weekly_text(), label)), "weekly")
    assert r.returncode == 1, r.stdout
    assert f"必須見出し「## 【{label}】」がありません" in r.stdout


def test_weekly_previous_block_items_must_match_previous_goal(tmp_path: Path):
    # 前回ブロック（前週の目標→実績→差分）は月報・期報・1年と同じく項目名・順序が1対1。
    text = weekly_text(prev_outcome_diff=["- 継続申込：±0件", "- 月額顧問の提案受諾：-1件", "- 売上貢献：-50000"])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "前期間の項目一致: 【前週の売上以外の成果目標と実績の差分】の項目名・順序" in r.stdout


def test_weekly_previous_action_without_item_names_is_not_compared(tmp_path: Path):
    text = weekly_text(prev_action=["- 個別メッセージを15件送る", "- Aさんへ初回提案を提示する"])
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert "前期間の項目一致: 【前週の行動目標】は項目名のない旧形式のため未照合" in r.stdout


def test_initial_previous_block_passes_without_comparison(tmp_path: Path):
    # 初回は前回ブロックの各欄に `- 初回（前回正本なし）` の1行。照合を飛ばして PASS と表示する。
    text = previous_as_initial(weekly_text())
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 0, r.stdout
    assert "PASS: 前期間の項目一致: 【前週の売上以外の成果目標】は初回（前回正本なし）のため照合しない" in r.stdout
    assert "PASS: 前期間の項目一致: 【前週の行動目標】は初回（前回正本なし）のため照合しない" in r.stdout


def test_initial_target_with_transcribed_result_fails(tmp_path: Path):
    # 目標が初回なのに実績だけ項目がある → 前回ブロックの欄どうしが食い違う
    text = mutate(previous_as_initial(weekly_text()),
                  f"## 【前週の売上以外の成果実績】\n- {INITIAL_MARKER}",
                  "## 【前週の売上以外の成果実績】\n- 継続申込：1件")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "【前週の売上以外の成果目標】が初回なので【前週の売上以外の成果実績】も" in r.stdout


@pytest.mark.parametrize("old,new,message", [
    ("## 【前週の売上実績】\n150000\n", "## 【前週の売上実績】\n",
     "前回ブロック: 【前週の売上実績】が空です"),
    ("## 【前週の売上以外の成果実績】\n- 継続申込：1件・完了6/27\n- 月額顧問の提案受諾：0件\n",
     "## 【前週の売上以外の成果実績】\n", "前期間の項目一致: 【前週の売上以外の成果実績】が空です"),
    ("## 【前週の行動目標（行動管理）】\n- 個別メッセージ：個別メッセージを15件送る　期日6/26\n"
     "- 初回提案：Aさんへ初回提案を提示する　期日6/26\n",
     "## 【前週の行動目標（行動管理）】\n", "前期間の項目一致: 【前週の行動目標】が空です"),
])
def test_empty_previous_column_fails(tmp_path: Path, old: str, new: str, message: str):
    # 欄が空なのは転記漏れ。初回ならマーカーを置く（空のままでは初回か漏れかを区別できない）。
    r = run(write(tmp_path, WEEKLY_NAME, mutate(weekly_text(), old, new)), "weekly")
    assert r.returncode == 1, r.stdout
    assert message in r.stdout


def test_previous_result_column_missing_fails(tmp_path: Path):
    text = drop_section(weekly_text(), "前週の売上以外の成果実績")
    r = run(write(tmp_path, WEEKLY_NAME, text), "weekly")
    assert r.returncode == 1, r.stdout
    assert "【前週の売上以外の成果目標】に項目があるのに【前週の売上以外の成果実績】がありません" in r.stdout


@pytest.mark.parametrize("lines", [
    ["- なし"],
    [f"- {INITIAL_MARKER}"],
    # 要因分析の `###` 小見出し以下は対応行の検査対象外。
    DEFAULT_RECOVERY + ["", "### 要因分析", "- 先方の決裁が遅れた（期日6/26を2回延ばした）"],
])
def test_recovery_section_accepts_none_initial_and_analysis(tmp_path: Path, lines: list[str]):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(recovery=lines)), "weekly")
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("lines,message", [
    (["- 初回提案：診断当日の提示0件→1件（今回の行動目標「存在しない行動」で実行）"],
     "「存在しない行動」が今回の行動目標の項目名にありません"),
    (["- なし"] + DEFAULT_RECOVERY, "の `- なし` はほかの行と並べられません"),
    ([], "## 【前週の行動に対して未達を挽回するための行動】 が空です"),
    (["- 初回提案：期日6/26→期日7/1（今回の行動目標「診断実施」で実行）"], "期日は今回の行動目標の側にだけ書きます"),
    (["- 初回提案：Aさんへ初回提案を提示する　期日7/1"], "（今回の行動目標「{今回の項目名}」で実行）` か `- なし`"),
    (["- **初回提案** → 診断当日に提示する"], "（今回の行動目標「{今回の項目名}」で実行）` か `- なし`"),
])
def test_recovery_line_violations_fail(tmp_path: Path, lines: list[str], message: str):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(recovery=lines)), "weekly")
    assert r.returncode == 1, r.stdout
    assert message in r.stdout


@pytest.mark.parametrize("item,passes", [("提案", True), ("提案書", False)])
def test_recovery_line_is_checked_on_period_layer(tmp_path: Path, item: str, passes: bool):
    # 対応行は4層共通。期報でも今回の行動目標の項目名に実在することを見る。
    line = f"- 提案の受諾：提案0件→1件（今回の行動目標「{item}」で実行）"
    text = period_text("3ヶ月の目標", {"前期の売上に対して未達を挽回するための行動": line})
    r = run(write(tmp_path, PERIOD_NAME, text), "quarterly")
    assert (r.returncode == 0) is passes, r.stdout


# --- 見直し記録（共通部品E）---

REVISION_OK = "- 行動の見直し：提案書提出｜変更前：期日7/2｜変更後：期日7/3｜理由：先方の決裁日の変更｜上位への影響：なし"


def test_weekly_without_revision_record_heading_fails(tmp_path: Path):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(revision=None)), "weekly")
    assert r.returncode == 1, r.stdout
    assert "必須見出し「## 【今週の見直し記録】」がありません" in r.stdout


def test_weekly_revision_record_line_passes(tmp_path: Path):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(revision=REVISION_OK)), "weekly")
    assert r.returncode == 0, r.stdout
    assert "必須見出し「## 【今週の見直し記録】」" in r.stdout
    assert "PASS: 行動の見直し: 【今週の見直し記録】 の「提案書提出」" in r.stdout


def test_weekly_upper_allocation_record_passes(tmp_path: Path):
    record = ("- 上位配分の見直し：当月の売上目標｜上位計画：600000｜実行目標：650000"
              "｜理由：受注時期の変更｜上位への影響：翌月配分を見直す")
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(revision=record)), "weekly")
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("record,message", [
    ("- 行動の見直し：提案書提出｜変更前：期日7/2｜変更後：期日7/3｜上位への影響：なし",
     "「提案書提出」は変更前・変更後・理由・上位への影響を各1件、空欄なく"),
    ("- 行動の見直し：提案書提出｜変更前：期日7/2｜変更後：期日7/3｜理由：｜上位への影響：なし",
     "「提案書提出」は変更前・変更後・理由・上位への影響を各1件、空欄なく"),
    ("- 行動の見直し：存在しない行動｜変更前：期日7/2｜変更後：期日7/3｜理由：先方の都合｜上位への影響：なし",
     "「存在しない行動」が今回の行動目標の項目名にありません"),
    ("- 行動の見直し：提案書提出｜変更前：期日7/2｜変更後：期日 7/2｜理由：先方の都合｜上位への影響：なし",
     "「提案書提出」は変更前と変更後が同じ"),
    ("- 行動の見直し：｜変更前：期日7/2｜変更後：期日7/3｜理由：先方の都合｜上位への影響：なし", "に項目名がありません"),
    ("- 提案書提出の期日を7/3に変えた", "の行は `- なし` か `- 行動の見直し：…` か `- 上位配分の見直し：…`"),
    ("- なし\n" + REVISION_OK, "の `- なし` はほかの行と並べられません"),
    ("", "【今週の見直し記録】 が空です"),
    ("- 上位配分の見直し：当月の売上目標｜上位計画：600000｜実行目標：650000｜上位への影響：翌月配分を見直す",
     "上位配分の見直しは対象・上位計画・実行目標・理由・上位への影響を各1件"),
])
def test_weekly_revision_record_violations_fail(tmp_path: Path, record: str, message: str):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(revision=record)), "weekly")
    assert r.returncode == 1, r.stdout
    assert message in r.stdout


# --- 日付索引（【今週の大きな到達ライン】）---


def test_date_index_with_several_items_passes(tmp_path: Path):
    index = DEFAULT_DATE_INDEX + ["- 7/4（土）：診断実施、判断確認｜やらない：新規の営業連絡"]
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(date_index=index)), "weekly")
    assert r.returncode == 0, r.stdout
    assert "日付索引 5 行を照合しました" in r.stdout


@pytest.mark.parametrize("lines,message", [
    (["- [ ] 7/4（土）：診断実施"], "チェックボックスは付けません"),
    (["- 7/4（土）：診断実施", "  - 体験診断を実施する"], "は入れ子にしません"),
    (["- 7/4（土）：存在しない行動"], "「存在しない行動」が行動目標の項目名にありません"),
    (["- 7/4（土）：なし"], "行動の無い日は `- {M/D（曜）}：なし｜やらない：{内容}`"),
    (["- 7/4（土）：診断実施｜やらない："], "`｜やらない：` の後が空です"),
    (["- 7/4：診断実施"], "の行は `- {M/D（曜）}：{項目名}、{項目名}｜やらない：{内容}` で書いてください"),
    (["- 7/4（土） 体験診断を実施する"], "の行は `- {M/D（曜）}：{項目名}、{項目名}｜やらない：{内容}` で書いてください"),
])
def test_date_index_violations_fail(tmp_path: Path, lines: list[str], message: str):
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(date_index=DEFAULT_DATE_INDEX + lines)), "weekly")
    assert r.returncode == 1, r.stdout
    assert message in r.stdout


def test_weekly_project_tasks_fail(tmp_path: Path):
    # 週報の実行管理は行動目標＋日付索引の1方式。【プロジェクト別タスク】は出力しない。
    extra = ("\n## 【プロジェクト別タスク】\n### 月額顧問の案件\n- 先方担当者: Aさん\n"
             "- [ ] 提案書提出：提案書を提出する　期日7/2\n")
    r = run(write(tmp_path, WEEKLY_NAME, weekly_text(extra=extra)), "weekly")
    assert r.returncode == 1, r.stdout
    assert "週報にプロジェクト別タスクが含まれています" in r.stdout


def test_goal_action_language_profile_keeps_legacy_compatibility():
    import importlib.util
    policy_script = Path(__file__).resolve().parents[1] / "skills/run-ubm-goal-setting/scripts/validate-goal-output.py"
    spec = importlib.util.spec_from_file_location("goal_language_policy", policy_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for phrase in ["頑張る", "意識する", "気をつける", "心がける", "努力する"]:
        assert module.GOAL_SPIRIT_RE.search(phrase)
    for phrase in ["なるべく", "できるだけ"]:
        assert module.GOAL_SPIRIT_RE.search(phrase) is None


# --- 入力を読めないとき・語彙契約が壊れているときの終了コード ---

def test_unreadable_inputs_exit_2_without_traceback(tmp_path: Path, golden_text: str):
    # 入力を読めないのは検査の FAIL (1) ではない。ディレクトリや非 UTF-8 も 2 にする。
    good = write(tmp_path, WEEKLY_NAME, golden_text)
    folder = tmp_path / "folder.md"
    folder.mkdir()
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"\xff\xfe\x00broken")
    for file_, peers in [(folder, []), (binary, []), (good, [binary]), (good, [folder])]:
        r = run(file_, "weekly", peers)
        assert r.returncode == 2, (file_, peers, r.stdout, r.stderr)
        assert "Traceback" not in r.stderr
        assert "ERROR:" in r.stderr


def _sandbox_validator(tmp_path: Path, policy) -> Path:
    root = tmp_path / "plugin"
    script = root / VALIDATE.relative_to(PLUGIN_ROOT)
    script.parent.mkdir(parents=True)
    script.write_text(VALIDATE.read_text(encoding="utf-8"), encoding="utf-8")
    if policy is not None:
        (root / "references").mkdir()
        (root / "references/action-language-policy.json").write_text(
            json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    return script


@pytest.mark.parametrize("policy", [None, {"goal_exact_phrases": []}])
def test_help_works_without_action_policy(tmp_path: Path, policy):
    script = _sandbox_validator(tmp_path, policy)
    r = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "--file" in r.stdout


def test_whitespace_only_phrase_in_policy_is_rejected(tmp_path: Path, golden_text: str):
    # 空白1字の語を受け入れると、空白を含む行すべてが精神論として FAIL になる。
    script = _sandbox_validator(tmp_path, {"goal_exact_phrases": ["頑張る", " "]})
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = subprocess.run([sys.executable, str(script), "--file", str(p), "--type", "weekly"],
                       capture_output=True, text=True)
    assert r.returncode == 2, r.stdout
    assert "語彙契約" in r.stderr
    assert "Traceback" not in r.stderr


# --- 「やらないこと」の表の数え方 ---

NOT_DOING = "今期やらないこと（明確に排除するもの）"


def test_not_doing_counts_table_rows_not_lines_minus_two(tmp_path: Path):
    # 表が2つ（見出し行＋区切り行＋1行ずつ）なら項目は2つ。「表の行数 - 2」だと 4 と数えて通してしまう。
    two_tables = "\n".join([
        "| やらないこと | 理由 |", "|---|---|", "| 交流会に参加しない | 時間 |", "",
        "| やらないこと | 理由 |", "| :--- | ---: |", "| 新しい商品を作らない | 集中 |",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: two_tables}))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "「やらないこと」が2項目です" in r.stdout


def test_not_doing_table_with_three_rows_passes(tmp_path: Path):
    table = "\n".join([
        "| やらないこと | 理由 |", "|---|---|",
        "| 交流会に参加しない | 時間 |", "| 無料の勉強会をやらない | 集中 |", "| 新しい商品を作らない | 集中 |",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "「やらないこと」3項目" in r.stdout


def test_not_doing_table_with_short_separator_is_not_counted(tmp_path: Path):
    # GFM の区切り行はハイフン1個以上。`|--|` を区切り行と見ないと、見出し行と区切り行を
    # データ行として数え、2項目しか無い表を4項目として通してしまう。
    table = "\n".join([
        "| やらないこと | 理由 |", "|--|:-:|",
        "| 交流会に参加しない | 時間 |", "| 新しい商品を作らない | 集中 |",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "「やらないこと」が2項目です" in r.stdout


def test_not_doing_separator_without_trailing_pipe_is_not_counted(tmp_path: Path):
    # GFM では区切り行の末尾の `|` を省ける。`|---|---` を区切り行と見ないと、見出し行と
    # 区切り行もデータ行と数え、1項目しか無い表を3項目として通してしまう（偽 PASS）。
    table = "\n".join([
        "| やらないこと | 理由 |", "|---|---",
        "| 交流会に参加しない | 時間 |",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 1, r.stdout
    assert "「やらないこと」が1項目です" in r.stdout


@pytest.mark.parametrize("separator, row_end", [("---|---|", " |"), ("---|---", "")])
def test_not_doing_table_without_leading_pipe_counts_three_rows(
    tmp_path: Path, separator: str, row_end: str
):
    # GFM では行の先頭の `|` も省ける。先頭が `|` の行だけを表の行と見ると、データが3行あっても
    # 0項目と数えて落としてしまう（偽 FAIL）。
    table = "\n".join([
        f"やらないこと | 理由{row_end}", separator,
        f"交流会に参加しない | 時間{row_end}",
        f"無料の勉強会をやらない | 集中{row_end}",
        f"新しい商品を作らない | 集中{row_end}",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "「やらないこと」3項目" in r.stdout


def test_not_doing_table_cells_starting_with_hash_are_counted(tmp_path: Path):
    # 先頭の `|` を省いた表で、セルが `#1` のように `#` で始まっても見出しではない。
    # `#` 1文字で表を閉じると、3行あっても0項目と数えて落としてしまう（偽 FAIL）。
    table = "\n".join([
        "番号と内容 | 理由", "---|---",
        "#1 交流会に参加しない | 時間",
        "#2 無料の勉強会をやらない | 集中",
        "#3 新しい商品を作らない | 集中",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "「やらないこと」3項目" in r.stdout


def test_not_doing_heading_after_table_closes_it(tmp_path: Path):
    # `### ` の見出しは `|` を含んでも表の行ではない。表を閉じて見出しの項目として1つだけ数える
    # （表の行としても数えると 4 になる）。
    table = "\n".join([
        "やらないこと | 理由", "---|---",
        "交流会に参加しない | 時間",
        "新しい商品を作らない | 集中",
        "### 無料の勉強会をやらない | 集中",
    ])
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", {NOT_DOING: table}))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "「やらないこと」3項目" in r.stdout


# --- 1年目標（yearly）が通る形 ---

YEARLY_NAME = "UBM - 4-年報（１年） 2026-10-01〜2027-09-30.md"


def yearly_text(key_number: str = "- 月間売上到達点：1500000\n- 継続コンサル人数：10") -> str:
    """期報の最小本文の期間語を「今年/前年」に置き換え、【今年の最重要数字】を足した1年目標。

    1年層は期報と同じ骨格（validate-goal-output.py の kind=year）なので、骨格を別に
    書かずに期報から作る。別に書くと、期報の必須見出しが増えたときに片方だけ古くなる。
    """
    text = period_text("1年の目標").replace("2026-06-29〜2026-09-27", "2026-10-01〜2027-09-30")
    text = text.replace("今期", "今年").replace("前期", "前年")
    return text + f"## 【今年の最重要数字】\n\n{key_number}\n"


def test_yearly_minimal_document_passes(tmp_path: Path):
    p = write(tmp_path, YEARLY_NAME, yearly_text())
    r = run(p, "yearly")
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout


def test_yearly_without_key_number_fails(tmp_path: Path):
    # 【今年の最重要数字】は下位3層の分母の起点なので必須。無ければ rc=1。
    text = yearly_text().split("## 【今年の最重要数字】")[0]
    p = write(tmp_path, YEARLY_NAME, text)
    r = run(p, "yearly")
    assert r.returncode == 1, r.stdout
    assert "今年の最重要数字" in r.stdout


def test_yearly_with_project_tasks_fails(tmp_path: Path):
    text = yearly_text() + "\n## 【プロジェクト別タスク】\n\n- [ ] [青木さん] [提案] 提案書を出す\n"
    p = write(tmp_path, YEARLY_NAME, text)
    r = run(p, "yearly")
    assert r.returncode == 1, r.stdout
    assert "1年目標にプロジェクト別タスクが含まれています" in r.stdout


def test_yearly_with_utf8_bom_passes(tmp_path: Path):
    # BOM 付き UTF-8 でも1行目のタイトル見出しを読めること。BOM が残ると「## 【1年の目標】」が
    # 行頭に来ず、必須タイトル見出しが無いと誤って FAIL する（validate-cross-level.py は通す）。
    p = tmp_path / YEARLY_NAME
    p.write_text(yearly_text(), encoding="utf-8-sig")
    assert p.read_bytes().startswith(b"\xef\xbb\xbf")
    r = run(p, "yearly")
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout
