#!/usr/bin/env python3
"""validate-cross-level.py の受け入れテスト。

実行（cwd はプラグインルート）:
    <pytest が入っているインタプリタ> -m pytest tests/test_validate_cross_level.py -q

インタプリタのパスは固定しない。環境ごとに pytest の入っている先が違う。ただし
**回す前に `-m pytest --version` が rc=0 を返すことを確かめる。** pytest を持たない
インタプリタでも `-m pytest` は rc=1 を返し、それは「テストが落ちた」ではなく
「実行できなかった」の値なので、確かめずに回すと両者の区別が付かなくなる。

このテストが固定している契約:

- rc=0（照合して不一致0件）と rc=3（1件も抽出できず何も判定していない）が別物であること
- 抽出不可を「不一致0件」に吸収しないこと（抽出不可があれば rc=1）
- 分母（照合対象 N 件）を必ず出すこと。「不一致0件」だけでは検査したことにならない
- 【仮置き事項】【確定済み・解消済みの記録】の中の値を現在値として拾わないこと
- --weekly 省略で2ファイルでも動くこと
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "skills/run-ubm-goal-setting/scripts/validate-cross-level.py"

Q_NAME = "UBM - 3-月報（３ヶ月） - 2026-10-01〜2026-12-31.md"
M_NAME = "UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25.md"
W_NAME = "UBM - 1-週報 - 2026-09-28〜2026-10-04.md"


def quarterly(
    period_sales: str = "2,320,000",
    month_sales: str = "10月600,000・11月700,000・12月1,000,000",
    consult: str = "無料相談の延べ回数120回：10月56回・11月32回・12月32回",
    first_meet: str = "無料相談の1回目に会う実人数78名：10月30名・11月24名・12月24名",
    cumulative: str = "月額継続コンサルの新規成約9件　累積は10月4件・11月6件・12月9件",
    partners: str = "7",
    grid: str = "0",
    sparring: str = "2026-10-09",
    extra: str = "",
    outcome_body: str | None = None,
) -> str:
    outcome = outcome_body if outcome_body is not None else "\n".join(
        [f"- {consult}", f"- {first_meet}", f"- {cumulative}"]
    )
    return "\n".join([
        "# UBM - 3-月報（３ヶ月） - 2026-10-01〜2026-12-31",
        "",
        "## 【今期の売上目標】",
        period_sales,
        "",
        "## 【今期の売上以外の成果目標】",
        outcome,
        "",
        "## 【現在事業パートナー数】",
        partners,
        "",
        "## 【現在のグリッドパートナー数】",
        grid,
        "",
        "## 【次回の壁打ち予定日】",
        sparring,
        "",
        "## 【事業計画書数値】",
        f"- 月別の売上目標：{month_sales}",
        "",
        extra,
        "",
    ])


def monthly(
    period_sales: str = "2,320,000",
    month_sales_body: str = "600,000",
    key_number: str = (
        "無料相談を実施した実人数：30名（延べ回数56回以上）　"
        "そこから月額継続コンサルへつながった件数：4件"
    ),
    partners: str = "7",
    grid: str = "0",
    sparring: str = "2026-10-09",
    extra: str = "",
) -> str:
    return "\n".join([
        "# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25",
        "",
        "## 【今期の売上目標】",
        period_sales,
        "",
        "## 【今月の売上目標】",
        month_sales_body,
        "",
        "## 【今月の最重要数字】",
        key_number,
        "",
        "## 【現在事業パートナー数】",
        partners,
        "",
        "## 【現在のグリッドパートナー数】",
        grid,
        "",
        "## 【次回の壁打ち予定日】",
        sparring,
        "",
        extra,
        "",
    ])


def weekly(
    period_sales: str = "2,320,000",
    week_note: str = "（※ 600,000 ÷ 28日 × 7日 ＝ 150,000）",
    week_sales: str = "150,000",
    partners: str = "7",
    grid: str = "0",
    sparring: str = "2026-10-09",
) -> str:
    return "\n".join([
        "# UBM - 1-週報 - 2026-09-28〜2026-10-04",
        "",
        "## 【今期の売上目標】",
        "（※ 期報からの継承。ここを直すときは期報を先に直す）",
        period_sales,
        "",
        "## 【今週の売上目標】",
        week_note,
        week_sales,
        "",
        "## 【現在事業パートナー数】",
        partners,
        "",
        "## 【現在のグリッドパートナー数】",
        grid,
        "",
        "## 【次回の壁打ち予定日】",
        sparring,
        "",
    ])


def write_set(tmp_path: Path, q: str | None, m: str | None, w: str | None) -> dict:
    out = {}
    for key, name, text in (("q", Q_NAME, q), ("m", M_NAME, m), ("w", W_NAME, w)):
        if text is None:
            continue
        p = tmp_path / name
        p.write_text(text, encoding="utf-8")
        out[key] = p
    return out


def run(paths: dict, *extra: str) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if "q" in paths:
        cmd += ["--quarterly", str(paths["q"])]
    if "m" in paths:
        cmd += ["--monthly", str(paths["m"])]
    if "w" in paths:
        cmd += ["--weekly", str(paths["w"])]
    cmd += list(extra)
    return subprocess.run(cmd, capture_output=True, text=True)


def run_default(tmp_path: Path, **kw) -> subprocess.CompletedProcess:
    paths = write_set(
        tmp_path,
        kw.pop("q", quarterly()),
        kw.pop("m", monthly()),
        kw.pop("w", weekly()),
    )
    return run(paths, *kw.pop("extra", []))


# --- rc=0: 三層一致 ---

def test_all_three_match_is_rc0(tmp_path: Path):
    r = run_default(tmp_path)
    assert r.returncode == 0, r.stdout
    assert "STATUS: PASS" in r.stdout


def test_rc0_prints_denominator(tmp_path: Path):
    r = run_default(tmp_path)
    assert "照合対象 8 件中 不一致 0 件（抽出不可 0 件）" in r.stdout


def test_rc0_shows_all_three_values_side_by_side(tmp_path: Path):
    r = run_default(tmp_path)
    assert "[OK] 今期の売上目標" in r.stdout
    for ja in ("期報=2320000", "月報=2320000", "週報=2320000"):
        assert ja in r.stdout, r.stdout


def test_comma_and_bare_number_are_equal(tmp_path: Path):
    # 2,320,000 と 2320000 は同値として扱う
    r = run_default(tmp_path, m=monthly(period_sales="2320000"))
    assert r.returncode == 0, r.stdout


def test_target_month_is_end_month_of_monthly_period(tmp_path: Path):
    # 2026-09-28〜2026-10-25 の当月は 10 月（最終月曜起点のため）
    r = run_default(tmp_path)
    assert "対象月: 10月" in r.stdout


# --- rc=1: 不一致 ---

def test_monthly_sales_diverging_from_quarterly_breakdown_is_rc1(tmp_path: Path):
    r = run_default(tmp_path, m=monthly(month_sales_body="500,000"))
    assert r.returncode == 1, r.stdout
    assert "[NG] 当月の売上目標" in r.stdout
    assert "不一致のアンカー: 当月の売上目標" in r.stdout
    assert "照合対象 8 件中 不一致 1 件（抽出不可 0 件）" in r.stdout
    assert "STATUS: FAIL" in r.stdout


def test_quarterly_breakdown_change_not_followed_is_rc1(tmp_path: Path):
    # 期報の月別内訳だけ直して月報に追随させていない形
    r = run_default(
        tmp_path,
        q=quarterly(month_sales="10月700,000・11月700,000・12月1,000,000"),
    )
    assert r.returncode == 1, r.stdout
    assert "当月の売上目標" in r.stdout


def test_sparring_date_mismatch_is_rc1(tmp_path: Path):
    r = run_default(tmp_path, q=quarterly(sparring="2026-10-09"), m=monthly(sparring="2027-03-25"))
    assert r.returncode == 1, r.stdout
    assert "[NG] 次回の壁打ち予定日" in r.stdout


def test_consult_count_mismatch_names_the_anchor(tmp_path: Path):
    r = run_default(
        tmp_path,
        m=monthly(key_number="無料相談を実施した実人数：30名（延べ回数40回以上）　件数：4件"),
    )
    assert r.returncode == 1, r.stdout
    assert "無料相談の延べ回数" in r.stdout


def test_weekly_divergence_is_detected(tmp_path: Path):
    r = run_default(tmp_path, w=weekly(period_sales="2,300,000"))
    assert r.returncode == 1, r.stdout
    assert "今期の売上目標" in r.stdout


# --- 抽出不可は不一致と別枠。ただし rc=1 にする ---

def test_unextractable_anchor_is_listed_separately_and_rc1(tmp_path: Path):
    # 週報の日割り根拠行を落とす → 当月の売上目標が週報で抽出不可
    r = run_default(tmp_path, w=weekly(week_note="（※ 期報からの継承）"))
    assert r.returncode == 1, r.stdout
    assert "[抽出不可] 当月の売上目標" in r.stdout
    assert "抽出不可のアンカー: 当月の売上目標" in r.stdout
    assert "照合対象 8 件中 不一致 0 件（抽出不可 1 件）" in r.stdout


def test_zenkaku_digit_is_unextractable_not_mismatch(tmp_path: Path):
    r = run_default(tmp_path, m=monthly(month_sales_body="６００，０００"))
    assert r.returncode == 1, r.stdout
    assert "[抽出不可] 当月の売上目標" in r.stdout
    assert "全角数字" in r.stdout


# --- rc=3: 抽出0件。rc=1 と混ぜない ---

def test_no_anchor_headings_is_rc3(tmp_path: Path):
    empty = "# UBM - 3-月報（３ヶ月） - 2026-10-01〜2026-12-31\n\n## 【前書き】\n本文のみ\n"
    empty_m = "# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25\n\n## 【前書き】\n本文のみ\n"
    paths = write_set(tmp_path, empty, empty_m, None)
    r = run(paths)
    assert r.returncode == 3, r.stdout
    assert "STATUS: NO_TARGET" in r.stdout
    assert "何も判定していない" in r.stdout


def test_rc3_is_not_rc1(tmp_path: Path):
    # 抽出0件（rc=3）と不一致あり（rc=1）が同じ値にならないことを明示的に固定する
    empty = "# UBM - 3-月報（３ヶ月） - 2026-10-01〜2026-12-31\n\n## 【前書き】\n本文\n"
    empty_m = "# UBM - 2-月報（１ヶ月） - 2026-09-28〜2026-10-25\n\n## 【前書き】\n本文\n"
    rc_zero_extraction = run(write_set(tmp_path, empty, empty_m, None)).returncode
    rc_mismatch = run_default(tmp_path, m=monthly(month_sales_body="500,000")).returncode
    assert rc_zero_extraction == 3
    assert rc_mismatch == 1
    assert rc_zero_extraction != rc_mismatch


# --- rc=2: 引数・入力不正 ---

def test_quarterly_only_is_rc2(tmp_path: Path):
    paths = write_set(tmp_path, quarterly(), None, None)
    r = run(paths)
    assert r.returncode == 2, r.stdout + r.stderr


def test_no_args_is_rc2():
    r = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 2


def test_missing_file_is_rc2(tmp_path: Path):
    paths = write_set(tmp_path, quarterly(), monthly(), None)
    paths["w"] = tmp_path / "nope.md"
    r = run(paths)
    assert r.returncode == 2, r.stdout


def test_out_of_range_month_is_rc2(tmp_path: Path):
    r = run_default(tmp_path, extra=["--month", "13"])
    assert r.returncode == 2, r.stdout


# --- 除外節: 経緯の記述を現在値として拾わない ---

def test_kariiki_section_value_is_not_picked_up(tmp_path: Path):
    # 【今月の売上目標】の中に仮置きの小見出しが先に来る形。500,000 を拾うと不一致になる
    m = monthly(month_sales_body="\n".join([
        "### 【今月の仮置き事項（確定が必要）】",
        "500,000",
        "### 【確定値】",
        "600,000",
    ]))
    r = run_default(tmp_path, m=m)
    assert r.returncode == 0, r.stdout
    assert "月報=600000" in r.stdout


def test_resolved_record_section_value_is_not_picked_up(tmp_path: Path):
    # 【今期の売上以外の成果目標】の中に確定済み・解消済みの記録が先に来る形
    q = quarterly(outcome_body="\n".join([
        "### 【確定済み・解消済みの記録】",
        "- 無料相談の延べ回数90回：10月40回・11月25回・12月25回",
        "### 【今期の確定値】",
        "- 無料相談の延べ回数120回：10月56回・11月32回・12月32回",
        "- 無料相談の1回目に会う実人数78名：10月30名・11月24名・12月24名",
        "- 月額継続コンサルの新規成約9件　累積は10月4件・11月6件・12月9件",
    ]))
    r = run_default(tmp_path, q=q)
    assert r.returncode == 0, r.stdout
    assert "期報=56" in r.stdout


def test_conflict_section_is_excluded(tmp_path: Path):
    q = quarterly(extra="\n".join([
        "## 【北原さんマインド正本との衝突】",
        "- 今期の売上目標は以前 1,200,000 で置いていた",
        "- 次回の壁打ち予定日は 2026-09-11 だった",
    ]))
    r = run_default(tmp_path, q=q)
    assert r.returncode == 0, r.stdout


def test_html_comment_in_anchor_section_is_ignored(tmp_path: Path):
    m = monthly(month_sales_body="<!--\n500,000\n-->\n600,000")
    r = run_default(tmp_path, m=m)
    assert r.returncode == 0, r.stdout
    assert "月報=600000" in r.stdout


# --- --weekly 省略 ---

def test_weekly_omitted_works_with_two_files(tmp_path: Path):
    paths = write_set(tmp_path, quarterly(), monthly(), None)
    r = run(paths)
    assert r.returncode == 0, r.stdout
    assert "週報: （未指定）" in r.stdout
    assert "照合対象 8 件中 不一致 0 件（抽出不可 0 件）" in r.stdout


def test_weekly_omitted_still_detects_monthly_divergence(tmp_path: Path):
    paths = write_set(tmp_path, quarterly(), monthly(month_sales_body="500,000"), None)
    r = run(paths)
    assert r.returncode == 1, r.stdout


# --- トレーラ（測定時刻と引数） ---

def test_trailer_has_measured_at_and_args(tmp_path: Path):
    r = run_default(tmp_path)
    assert "MEASURED_AT: " in r.stdout
    assert "ARGS: " in r.stdout
    # 数を人に渡すときは測定時刻と引数を添える（どのフィルタで測ったかが残らないと
    # 「照合対象0件」と「全部落ちた」が区別できない）
    measured = [l for l in r.stdout.split("\n") if l.startswith("MEASURED_AT: ")][0]
    assert "T" in measured and ("+" in measured or "Z" in measured)


def test_month_override_changes_target(tmp_path: Path):
    # --month 11 なら期報の11月分（700,000）と月報の600,000が不一致になる
    r = run_default(tmp_path, extra=["--month", "11"])
    assert r.returncode == 1, r.stdout
    assert "対象月: 11月" in r.stdout
    assert "当月の売上目標" in r.stdout


def test_month_1_does_not_pick_up_november(tmp_path: Path):
    # 1月の照合で「11月700,000」の「1月700,000」を拾わない。拾うと 700,000 と月報の
    # 600,000 を比べて、正しく書けている期報を不一致にする。
    q = quarterly(
        month_sales="11月700,000・12月1,000,000・1月600,000",
        consult="無料相談の延べ回数120回：11月32回・12月32回・1月56回",
        first_meet="無料相談の1回目に会う実人数78名：11月24名・12月24名・1月30名",
        cumulative="月額継続コンサルの新規成約9件　累積は11月6件・12月9件・1月4件",
    )
    r = run_default(tmp_path, q=q, extra=["--month", "1"])
    assert r.returncode == 0, r.stdout
    assert "[OK] 当月の売上目標  期報=600000" in r.stdout


# --- rc=2: UTF-8 で読めない入力 ---

def test_non_utf8_input_is_rc2_without_traceback(tmp_path: Path):
    paths = write_set(tmp_path, quarterly(), None, weekly())
    paths["m"] = tmp_path / M_NAME
    paths["m"].write_bytes(monthly().encode("shift_jis"))
    r = run(paths)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "月報 を UTF-8 として読めません" in r.stdout
    assert "Traceback" not in r.stderr


# --- 1年層（--yearly）: 1年目標の到達点を期報・月報が書き写しているか ---

Y_NAME = "UBM - 4-年報（１年） - 2026-10-01〜2027-09-30.md"
YEARLY_NOTE = "（※ 1年層からの継承　月間売上到達点：{sales}　継続コンサル人数：{count}）"


def yearly(sales: str = "1,500,000", count: str = "10") -> str:
    return "\n".join([
        "# UBM - 4-年報（１年） - 2026-10-01〜2027-09-30",
        "",
        "## 【今年の最重要数字】",
        f"- 月間売上到達点：{sales}",
        f"- 継続コンサル人数：{count}",
        "",
    ])


def run_with_yearly(tmp_path: Path, y: str, q_note: str, m_note: str) -> subprocess.CompletedProcess:
    q = quarterly(outcome_body="\n".join([
        "- 無料相談の延べ回数120回：10月56回・11月32回・12月32回",
        "- 無料相談の1回目に会う実人数78名：10月30名・11月24名・12月24名",
        "- 月額継続コンサルの新規成約9件　累積は10月4件・11月6件・12月9件",
        q_note,
    ]))
    m = monthly(key_number=(
        "無料相談を実施した実人数：30名（延べ回数56回以上）　"
        "そこから月額継続コンサルへつながった件数：4件\n" + m_note
    ))
    paths = write_set(tmp_path, q, m, weekly())
    yp = tmp_path / Y_NAME
    yp.write_text(y, encoding="utf-8")
    return run(paths, "--yearly", str(yp))


def test_yearly_anchors_match_is_rc0_with_10_targets(tmp_path: Path):
    note = YEARLY_NOTE.format(sales="1,500,000", count="10")
    r = run_with_yearly(tmp_path, yearly(), note, note)
    assert r.returncode == 0, r.stdout
    assert "照合対象 10 件中 不一致 0 件（抽出不可 0 件）" in r.stdout
    assert "[OK] 1年後の月間売上到達点  1年目標=1500000" in r.stdout
    assert "[OK] 1年後の月額継続コンサル人数  1年目標=10" in r.stdout
    assert "[未照合]" not in r.stdout


def test_yearly_anchor_not_followed_by_monthly_is_rc1(tmp_path: Path):
    # 1年目標の到達点を直したのに月報の注記が古いまま → 下位層の分母が黙ってずれる。
    r = run_with_yearly(
        tmp_path, yearly(sales="1,800,000"),
        YEARLY_NOTE.format(sales="1,800,000", count="10"),
        YEARLY_NOTE.format(sales="1,500,000", count="10"),
    )
    assert r.returncode == 1, r.stdout
    assert "[NG] 1年後の月間売上到達点" in r.stdout
    assert "不一致のアンカー: 1年後の月間売上到達点" in r.stdout


def test_yearly_note_missing_in_quarterly_is_unextractable(tmp_path: Path):
    note = YEARLY_NOTE.format(sales="1,500,000", count="10")
    r = run_with_yearly(tmp_path, yearly(), "", note)
    assert r.returncode == 1, r.stdout
    assert "[抽出不可] 1年後の月間売上到達点" in r.stdout


def test_without_yearly_the_yearly_anchors_are_listed_as_not_compared(tmp_path: Path):
    # --yearly を渡さなければ1年層の2アンカーは照合せず、分母にも数えず、そのことを明記する。
    r = run_default(tmp_path)
    assert r.returncode == 0, r.stdout
    assert "[未照合] 1年後の月間売上到達点（1年目標が未指定のため照合していない）" in r.stdout
    assert "照合対象 8 件中" in r.stdout
    assert "未照合のアンカー 2 件" in r.stdout
