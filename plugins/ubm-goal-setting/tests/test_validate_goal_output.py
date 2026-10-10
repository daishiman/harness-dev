"""validate-goal-output.py (C01) の保存前バリデーションテスト。

同梱 golden-sample-weekly.md を正本として PASS を確認し、各違反変異が FAIL する
ことを検証する (旧 validate-goal-output.sh の契約移植の等価性確認)。
"""
from __future__ import annotations

import json
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
        elif lbl == "今期やらないこと（明確に排除するもの）":
            parts += ["- 交流会に参加しない", "- 無料の勉強会をやらない", "- 新しい商品を作らない"]
        elif lbl == "今期の売上目標":
            parts.append(str(amount))
        elif lbl == "今期の売上以外の成果目標":
            parts += [
                "- 青木さん：提案の受諾1件　期日7/6",
                f"  → 売上貢献：{amount} × 1 = {amount}",
            ]
        elif lbl == "今期の行動目標（行動管理・優先順位付き）":
            parts += [
                f"### → 青木さん：提案の受諾（{amount}円）",
                "- [ ] 2026-07-06 までに青木さんへ提案を1件出す",
            ]
        else:
            parts.append("本文")
        parts.append("")
    if "今期の最重要数字" in anchors:
        parts += ["## 【今期の最重要数字】", "", anchors["今期の最重要数字"], ""]
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
    assert "層間比較: 比較3項目中 不一致0件" in r.stdout
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
    assert "層間比較: 比較3項目中 不一致1件" in r.stdout


def test_peer_zero_compared_is_distinguishable(tmp_path: Path):
    """比較対象が0件のときは「比較0項目」と印字し、不一致0件と区別できるようにする。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    peer = write(tmp_path, "peer-empty.txt", "## 【関係のない見出し】\n本文\n")
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "層間比較: 比較0項目中 不一致0件" in r.stdout
    assert "比較できる項目が1件もありませんでした" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def monthly_peer_text(sales: str, cumulative: str, key_number: str) -> str:
    """peer 側にだけ使う最小の月報本文（peer は検証対象ではなく値の取り出しのみ）。"""
    return "\n".join([
        "## 【1ヶ月の目標】 2026-08-31〜2026-09-27", "", "本文", "",
        "## 【今期の売上目標】", "", sales, "",
        "## 【今期の累計売上実績】", "", cumulative, "",
        "## 【今月の最重要数字】", "", key_number, "",
    ]) + "\n"


def test_peer_monthly_compares_three_items(tmp_path: Path):
    """月報 peer は従来どおり3項目（最重要数字も比較対象）。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK, ANCHOR_AMOUNT))
    peer = write(tmp_path, PEER_NAME,
                 monthly_peer_text("1,000,000", "630,000", "困りごとを解決した件数：6件"))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "層間比較: 比較3項目中 不一致0件" in r.stdout
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
    assert "SKIP: 最重要数字（週報の最重要数字は上位の内訳のため一致検査の対象外）" in r.stdout
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
    assert "SKIP: 最重要数字（週報の最重要数字は上位の内訳のため一致検査の対象外）" in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


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


# --- 逆算チェーン（売上 → 成果 → 行動）---


def test_outcome_without_sales_contribution_fails(tmp_path: Path, golden_text: str):
    # 成果目標から「→ 売上貢献：<式>」の行を落とす → 成果と売上の線が引けていないので FAIL
    text = golden_text.replace(
        "- Aさん：月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1 = 50000",
        "- Aさん：月額顧問の成約1件（初月分）　期日7/2",
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献" in r.stdout


def test_sales_contribution_arithmetic_mismatch_fails(tmp_path: Path, golden_text: str):
    # 単価 × 件数 と貢献額が合わない → 誰も検算できない数字なので FAIL
    text = golden_text.replace(
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1 = 50000",
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 2 = 50000",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献の式が合っていません" in r.stdout


def test_zero_contribution_without_reason_fails(tmp_path: Path, golden_text: str):
    # 貢献 0 に「いつ・いくらになるか」が無い → FAIL
    # 0 専用の検査ではなく、「式か括弧の根拠が要る」という一般規則で落ちる
    text = golden_text.replace(
        "  → 売上貢献：0（8月に 200000 の見込み）",
        "  → 売上貢献：0",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_bare_contribution_amount_fails(tmp_path: Path, golden_text: str):
    """裸の数字だけの貢献額は FAIL（検算できない数字を通さない）。

    式で書いた人だけが検算 FAIL を負い、根拠を出さなかった人が免除される
    非対称を防ぐための検査。
    """
    text = golden_text.replace(
        "  → 売上貢献：100000 × 1 = 100000",
        "  → 売上貢献：100000",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_contribution_with_parenthesized_basis_passes(tmp_path: Path, golden_text: str):
    """単価 × 件数へ分解できない成果は、括弧の根拠で通る（式は必須ではない）。"""
    text = golden_text.replace(
        "  → 売上貢献：100000 × 1 = 100000",
        "  → 売上貢献：100000（値引き後の一括見積）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "売上貢献に式または括弧の根拠がありません" not in r.stdout


def test_contribution_with_empty_parenthesis_fails(tmp_path: Path, golden_text: str):
    """中身の無い括弧は根拠ではない（形だけ通す抜け道を塞ぐ）。"""
    text = golden_text.replace(
        "  → 売上貢献：100000 × 1 = 100000",
        "  → 売上貢献：100000（）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献に式または括弧の根拠がありません" in r.stdout


def test_multi_month_contribution_fails(tmp_path: Path, golden_text: str):
    """件数に期間単位が付いた式は FAIL（今週入らない金銭を今週の売上に立てない）。"""
    text = golden_text.replace(
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1 = 50000",
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1ヶ月 = 50000",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "売上貢献の件数に期間単位「ヶ月」が付いています" in r.stdout
    assert "初月分だけを計上" in r.stdout


@pytest.mark.parametrize("unit", ["ヶ月", "ヵ月", "か月", "月", "年"])
def test_period_units_all_fail(tmp_path: Path, golden_text: str, unit: str):
    text = golden_text.replace(
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1 = 50000",
        f"月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1{unit} = 50000",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert f"期間単位「{unit}」" in r.stdout


@pytest.mark.parametrize("unit", ["件", "名", "回", "本"])
def test_count_units_pass(tmp_path: Path, golden_text: str, unit: str):
    """件・名・回・本は今期間に確定する数え方なので通す。"""
    text = golden_text.replace(
        "月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1 = 50000",
        f"月額顧問の成約1件（初月分）　期日7/2\n  → 売上貢献：50000 × 1{unit} = 50000",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "期間単位" not in r.stdout


def test_group_heading_amount_mismatch_fails(tmp_path: Path, golden_text: str):
    """グループ見出しの金額が成果目標の貢献額と食い違ったら FAIL。"""
    text = golden_text.replace(
        "### → Aさん：月額顧問の成約（50000円）",
        "### → Aさん：月額顧問の成約（9999999円）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "行動目標グループの金額が成果目標の貢献額と違います" in r.stdout
    assert "見出し 9999999 / 成果目標「Aさん」50000" in r.stdout


def test_group_heading_amount_with_comma_passes(tmp_path: Path, golden_text: str):
    """見出しの金額は `,` 区切りでも同じ値として扱う（表記差で落とさない）。"""
    text = golden_text.replace(
        "### → Aさん：月額顧問の成約（50000円）",
        "### → Aさん：月額顧問の成約（50,000円）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "行動目標グループの金額" not in r.stdout


def test_group_heading_without_amount_is_exempt(tmp_path: Path, golden_text: str):
    """金額の無い見出しは検査対象外（成果に紐づかない免除グループ）。"""
    text = golden_text.replace(
        "### → Aさん：月額顧問の成約（50000円）",
        "### → Aさん：月額顧問の成約",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "行動目標グループの金額" not in r.stdout


def test_mostly_zero_contribution_warns(tmp_path: Path, golden_text: str):
    # 貢献 0 が過半（4件中3件）→ 今期間の売上から逆算できていないので WARN
    text = golden_text.replace(
        "  → 売上貢献：100000 × 1 = 100000",
        "  → 売上貢献：0（8月に 100000 の見込み）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert "売上貢献 0 の成果目標が 3/4 件です" in r.stdout


def test_zero_contribution_minority_does_not_warn(tmp_path: Path, golden_text: str):
    # golden は 4件中2件が 0（ちょうど半分）→ 過半ではないので WARN は出さない
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = run(p, "weekly")
    assert "売上貢献 0 の成果目標が" not in r.stdout


def test_execution_type_outcome_fails(tmp_path: Path, golden_text: str):
    # 「実行した時点で達成になる目標」を成果目標に置く → FAIL
    text = golden_text.replace(
        "- Aさん：月額顧問の成約1件（初月分）　期日7/2",
        "- 勉強会：月4回開催する　期日7/2",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "実行完了型" in r.stdout


def test_action_without_outcome_link_fails(tmp_path: Path, golden_text: str):
    # 先頭のグループ見出しを落とす → 配下の行動がどの成果に属するか分からなくなり FAIL
    text = golden_text.replace("### → Bさん：提案の受諾（100000円）\n", "", 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "どの成果目標に属するか" in r.stdout


def test_action_dangling_outcome_reference_fails(tmp_path: Path, golden_text: str):
    # グループ見出しが成果目標セクションに存在しない名前を指す → FAIL
    text = golden_text.replace(
        "### → Aさん：月額顧問の成約（50000円）",
        "### → 存在しない成果：月額顧問の成約（50000円）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "実在しない成果目標" in r.stdout


def test_foundation_reference_is_exempt(tmp_path: Path, golden_text: str):
    # （土台）／（関係維持）は成果への紐づけを免除される
    text = golden_text.replace(
        "### → Aさん：月額顧問の成約（50000円）",
        "### → （関係維持）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert "実在しない成果目標" not in r.stdout


# --- シンプルさゲート（件数・長さ・1項目1成果）---


def test_too_many_outcome_items_fails(tmp_path: Path, golden_text: str):
    # 成果目標を6件にする（上限5件）→ FAIL
    text = golden_text.replace(
        "- Cさん：7月勉強会の開催枠の確保1件　期日7/1\n"
        "  → 売上貢献：0（8月に 200000 の見込み）",
        "- Cさん：7月勉強会の開催枠の確保1件　期日7/1\n"
        "  → 売上貢献：0（8月に 200000 の見込み）\n\n"
        "- Dさん：見積の承諾1件　期日7/4\n"
        "  → 売上貢献：0（7月後半に 100000 の見込み）\n\n"
        "- Eさん：面談の設定1件　期日7/4\n"
        "  → 売上貢献：0（7月後半に 100000 の見込み）",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "上限5件" in r.stdout


def test_long_outcome_item_fails(tmp_path: Path, golden_text: str):
    # 成果目標1項目を50字超にする → FAIL
    text = golden_text.replace(
        "- Bさん：提案の受諾1件　期日7/3",
        "- Bさん：体験診断を経たうえで提示した業務改善の提案内容に対する社内稟議を通した正式な受諾1件　期日7/3",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "長すぎ" in r.stdout


def test_outcome_item_with_multiple_results_fails(tmp_path: Path, golden_text: str):
    # `・` で複数の成果を1項目に詰め込む → FAIL
    text = golden_text.replace(
        "- Bさん：提案の受諾1件　期日7/3",
        "- Bさん：単価合意1件・提案の受諾1件　期日7/3",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "1項目1成果に分ける" in r.stdout


def test_long_action_item_fails(tmp_path: Path, golden_text: str):
    # 行動目標1項目を60字超にする → FAIL
    text = golden_text.replace(
        "- [ ] 提案書を提出する　期日7/2",
        "- [ ] 木曜までにAさんへ月額顧問の提案書1件を提出し、契約条件と開始月と支払い方法をすり合わせたうえで先方の決裁の期日まで握る　期日7/2",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "長すぎ" in r.stdout


def test_too_many_action_items_fails(tmp_path: Path, golden_text: str):
    # 行動目標を9件にする（上限8件）→ FAIL
    text = golden_text.replace(
        "- [ ] 習慣目標の3カテゴリを毎日チェックする　期日毎日",
        "- [ ] 習慣目標の3カテゴリを毎日チェックする　期日毎日\n"
        "- [ ] 週次の振り返りをする　期日7/3",
        1,
    )
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "上限8件" in r.stdout


def test_submission_action_section_is_outside_group_checks(tmp_path: Path, golden_text: str):
    # 月報の提出用セクションの行動目標（`（提出）` 付き）はグループ見出しを持たない
    # 1行1行動の規定。所属の検査（C4/C5）と件数（S3）の対象から外れることを確かめる。
    flat = "".join(f"- 事業者様へ連絡を{n}件出す　期日7/{n % 5 + 1}\n" for n in range(1, 10))
    head = "## 【今週の行動目標（行動管理・優先順位付き）】"
    assert head in golden_text
    text = golden_text.replace(head, "## 【今週の行動目標（提出）】\n" + flat + "\n" + head, 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "どの成果目標に属するか" not in r.stdout
    assert "行動目標 8 件（上限8件）" in r.stdout


def test_submission_action_section_is_outside_date_and_number_checks(
    tmp_path: Path, golden_text: str
):
    # 提出用は期日を書かない箇条書きの規定（期日と内訳は管理用の側に置く）。規定どおりの
    # ファイルが「数値のない行動目標」「期日のない行動目標」の WARN を出さないことを固定する。
    flat = "・既存の単発を月額継続へ変える条件の1枚を提示する\n・毎週の定例で論点を突き合わせる\n"
    head = "## 【今週の行動目標（行動管理・優先順位付き）】"
    assert head in golden_text
    text = golden_text.replace(head, "## 【今週の行動目標（提出）】\n" + flat + "\n" + head, 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 0, r.stdout
    assert "期日のない行動目標" not in r.stdout
    assert "数値のない行動目標" not in r.stdout


def test_managed_action_section_still_warns_on_missing_date(
    tmp_path: Path, golden_text: str
):
    # 上の除外が「検査そのものを殺した」のではないことの対照。管理用の側に期日の無い行を
    # 置けば WARN は出る。これが無いと、提出用を外した結果として管理用の期日落ちも
    # 見逃す形になっていても、どちらのテストも通ってしまう。
    head = "## 【今週の行動目標（行動管理・優先順位付き）】"
    text = golden_text.replace(head, head + "\n- 期日を書いていない行動を3件出す", 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert "期日のない行動目標" in r.stdout


def test_submission_action_section_still_rejects_spirit_words(
    tmp_path: Path, golden_text: str
):
    # 精神論は提出用でも許さない。NG表現だけは提出用・管理用の両方を対象に残している。
    flat = "・事業者様への連絡を頑張る\n"
    head = "## 【今週の行動目標（行動管理・優先順位付き）】"
    text = golden_text.replace(head, "## 【今週の行動目標（提出）】\n" + flat + "\n" + head, 1)
    p = write(tmp_path, WEEKLY_NAME, text)
    r = run(p, "weekly")
    assert r.returncode == 1, r.stdout
    assert "精神論" in r.stdout


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
