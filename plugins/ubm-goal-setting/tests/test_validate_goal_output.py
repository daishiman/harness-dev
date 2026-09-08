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
    r = run(tmp_path / "nope.md", "weekly")
    assert r.returncode == 1


def test_invalid_type_usage(tmp_path: Path, golden_text: str):
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    r = subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(p), "--type", "yearly"],
        capture_output=True, text=True,
    )
    assert r.returncode == 2


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


def period_text(title_label: str, anchors: dict[str, str] | None = None) -> str:
    """種別ラベルだけが異なる最小の期報本文。ラベル照合の分岐だけを固定する。

    `anchors` を渡すと該当見出しの本文をその値に差し替える (層間整合テスト用)。
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
        elif lbl == "今期の行動目標（行動管理・優先順位付き）":
            parts += ["- [ ] 2026-07-06 までに青木さんへ提案を1件出す"]
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
PEER_NAME = "UBM - 2-月報（１ヶ月） 2026-08-31〜2026-09-27.md"


def test_peer_absent_keeps_current_behavior(tmp_path: Path):
    """--peer 未指定なら層間整合チェックは走らず、結果も従来どおり。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
    r = run(p, "quarterly")
    assert r.returncode == 0, r.stdout
    assert "層間整合チェック" not in r.stdout
    assert "層間比較" not in r.stdout


def test_peer_matching_anchors_no_warning(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
    peer = write(tmp_path, PEER_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "層間比較: 比較3項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_peer_mismatched_anchors_warns_but_rc_zero(tmp_path: Path):
    """値がズレても FAIL にしない (継承は作成時 pull のみで必ず1回ズレる系)。"""
    mine = dict(ANCHORS_OK, **{"今期の売上目標": "600,000"})
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", mine))
    peer = write(tmp_path, PEER_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout
    assert "WARN: 層間の値ズレ: 今期の売上目標 対象=600000" in r.stdout
    assert "peer(" + PEER_NAME + ")=1000000" in r.stdout
    assert "層間比較: 比較3項目中 不一致1件" in r.stdout


def test_peer_zero_compared_is_distinguishable(tmp_path: Path):
    """比較対象が0件のときは「比較0項目」と印字し、不一致0件と区別できるようにする。"""
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
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
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
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
    anchors = dict(ANCHORS_OK, **{"今期の売上目標": "1,200,000", "今期の累計売上実績": "520,000"})
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", anchors))
    peer = write(tmp_path, WEEKLY_NAME, golden_text)
    r = run(p, "quarterly", [peer])
    assert r.returncode == 0, r.stdout
    assert "SKIP: 最重要数字（週報の最重要数字は上位の内訳のため一致検査の対象外）" in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_weekly_file_with_period_peer_skips_key_number(tmp_path: Path, golden_text: str):
    """--file 側が週報のときも同じく除外する（--type weekly を階層の正本にする）。"""
    anchors = dict(ANCHORS_OK, **{"今期の売上目標": "1,200,000", "今期の累計売上実績": "520,000"})
    p = write(tmp_path, WEEKLY_NAME, golden_text)
    peer = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", anchors))
    r = run(p, "weekly", [peer])
    assert r.returncode == 0, r.stdout
    assert "SKIP: 最重要数字（週報の最重要数字は上位の内訳のため一致検査の対象外）" in r.stdout
    assert "層間比較: 比較2項目中 不一致0件" in r.stdout
    assert "層間の値ズレ" not in r.stdout


def test_peer_missing_file_errors(tmp_path: Path):
    p = write(tmp_path, PERIOD_NAME, period_text("3ヶ月の目標", ANCHORS_OK))
    r = run(p, "quarterly", [tmp_path / "nope.md"])
    assert r.returncode == 1


def test_duplicate_heading_fails(tmp_path: Path, golden_text: str):
    # 既存見出しを複製 → 重複見出しで FAIL
    p = write(tmp_path, WEEKLY_NAME, golden_text + "\n## 【今週の判断基準】\n本文\n")
    r = run(p, "weekly")
    assert r.returncode == 1
    assert "重複" in r.stdout
