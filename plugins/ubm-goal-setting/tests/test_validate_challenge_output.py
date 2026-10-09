"""validate-challenge-output.py の保存前後バリデーションテスト。

同梱 golden-sample.md を正本として合格 (PASS) を確認し、骨格・挑戦・リスク回避・行うこと・定期報告・
プレースホルダ・ファイル名の各変異が不合格 (FAIL) になることを検証する。あわせて references/challenge-format.md の
骨格と違反コード表が検査スクリプトの定数・出力コードと一致することを縛る。

構造の変異テストは check_money_reason を空リストに差し替えて実行する。構造の判定がお金の理由の
合格基準 (M01) に左右されないことを確かめるためで、M01 自体は専用のテストで検査する。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-challenge"
VALIDATE = SKILL_DIR / "scripts/validate-challenge-output.py"
GOLDEN = SKILL_DIR / "examples/golden-sample.md"
FORMAT_DOC = SKILL_DIR / "references/challenge-format.md"

GOLDEN_NAME = "UBM - 挑戦宣言 - 2026-10-08.md"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(VALIDATE), *args], capture_output=True, text=True)


def write(tmp_path: Path, text: str, name: str = GOLDEN_NAME) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _load_validator():
    """スクリプトをモジュールとして読み込む (純関数を直接検査するため)。

    dataclass が文字列化された注釈を解決するときに sys.modules からモジュールを引くので、
    exec の前に登録しておく。
    """
    name = "_validate_challenge_output"
    spec = importlib.util.spec_from_file_location(name, VALIDATE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


V = _load_validator()


@pytest.fixture
def golden() -> str:
    return GOLDEN.read_text(encoding="utf-8")


@pytest.fixture
def structural_codes(monkeypatch):
    """お金の理由の判定を外して、構造の違反コードだけを返す。"""
    monkeypatch.setattr(V, "check_money_reason", lambda text: [])

    def _codes(text: str, filename: str | None = GOLDEN_NAME) -> list[str]:
        return [item.code for item in V.validate(text, filename)]

    return _codes


def replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, f"golden に {old!r} が1回だけ出てくる前提が崩れています"
    return text.replace(old, new)


# ---- 正本との一致 ----------------------------------------------------------------------------


def _skeleton_lines() -> list[str]:
    doc = FORMAT_DOC.read_text(encoding="utf-8")
    m = re.search(r"## 骨格.*?```text\n(.*?)```", doc, re.S)
    assert m, "challenge-format.md に骨格の text ブロックがありません"
    return [line.strip() for line in m.group(1).splitlines() if line.strip()]


def test_format_doc_skeleton_matches_validator_constants():
    lines = _skeleton_lines()
    expected = [
        V.TITLE,
        *V.SECTION_HEADINGS,
        *V.CHALLENGE_NOTES,
        *V.RISK_REASONS,
        V.CLOSING_LINE,
    ]
    for item in expected:
        assert item in lines, f"骨格に {item!r} がありません"
    order = [lines.index(item) for item in (V.TITLE, *V.SECTION_HEADINGS)]
    assert order == sorted(order)
    reasons = [lines.index(item) for item in V.RISK_REASONS]
    assert reasons == sorted(reasons)
    assert lines.index(V.SECTION_RISK) < reasons[0] < reasons[-1] < lines.index(V.SECTION_ACTIONS)


def test_format_doc_violation_codes_match_validator_output():
    doc = FORMAT_DOC.read_text(encoding="utf-8")
    table = doc.split("## 違反コード", 1)[1]
    documented = set(re.findall(r"^\| ([A-Z]\d{2}) \|", table, re.M))
    emitted = set(re.findall(r'Violation\("([A-Z]\d{2})"', VALIDATE.read_text(encoding="utf-8")))
    assert documented == emitted


# ---- 見本 (golden) と CLI ---------------------------------------------------------------------------


def test_golden_passes(tmp_path, golden):
    r = run("--file", str(write(tmp_path, golden)))
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.startswith("PASS")


def test_golden_is_structurally_clean(structural_codes, golden):
    assert structural_codes(golden) == []


def test_missing_file_exits_2(tmp_path):
    r = run("--file", str(tmp_path / "nope.md"))
    assert r.returncode == 2


def test_missing_argument_exits_2():
    assert run().returncode == 2


# ---- 構造の変異 ------------------------------------------------------------------------------

MUTATIONS = [
    ("F01", "【挑戦宣言と企画】\n", "挑戦宣言\n"),
    ("F02", "●目標を追うために定期の報告はどのタイミングで行いますか？\n", ""),
    ("F03", "個人も組織も家庭すらも、富が右肩上がりに積み上がる世界を、全ての知人に届ける。\n", ""),
    ("F04", "challenge_date: 2026-12-12", "challenge_date: 2026/12/12"),
    ("F04", "declared_on: 2026-10-08", "declared_on: 2026-02-30"),
    ("C01", "100人のセミナーイベントを12月12日に開催する。", "100人のセミナーイベントを冬に開催する。"),
    ("C02", "100人のセミナーイベントを12月12日に開催する。", "大規模なセミナーイベントを12月12日に開催する。"),
    ("C03", "※ズームなら基本100人以上\n", ""),
    ("D01", "12月12日に開催する", "12月13日に開催する"),
    ("G01", "・個別相談 30件\n・運営メンバーからの引き上げ 10件", "・個別相談をたくさん\n・運営メンバーからの引き上げを数件"),
    ("R01", "・家族が崩れない理由\n", ""),
    ("R02", "生活リズムは崩さない。もともとスケジュールを少なくしていた所に入れたので、稼働量は変わらない。\n", ""),
    ("A01", "5.小規模Zoomでも、開催前に個別相談を獲得する\n", ""),
    ("A01", "5.小規模Zoomでも、開催前に個別相談を獲得する\n", "5.小規模Zoomでも、開催前に個別相談を獲得する\n6.毎日ブログを書く\n"),
    ("A02", "上記行うことで必ず達成します。\n", ""),
    ("S01", "2.個別相談をセミナー開催前から受け付ける", "2.個別相談をできるだけ多く受け付ける"),
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "定期的に集客数の経過を報告します。"),
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "12月15日に報告します。"),  # 1回きりの日付
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "来月1日に報告します。"),  # 1回きりの日付
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "12月15日に面談の結果を報告します。"),  # 面談は場の言い方だけ
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "12月15日に1回、集客数を報告します。"),  # 日付の一部
    ("P01", "週1回、月曜9時にLINEで集客数の経過を報告します。", "12月 15日に1回、集客数を報告します。"),  # 月と日の間の空白
    ("X01", "・個別相談 30件", "・個別相談 ◯件"),
    ("X01", "個人も組織も家庭すらも、富が右肩上がりに積み上がる世界を、全ての知人に届ける。", "<目的本文>"),
]


@pytest.mark.parametrize("code,old,new", MUTATIONS, ids=[f"{c}-{i}" for i, (c, _, _) in enumerate(MUTATIONS)])
def test_mutation_is_detected(structural_codes, golden, code, old, new):
    assert code in structural_codes(replace_once(golden, old, new))


def test_section_order_swap_is_f02(structural_codes, golden):
    purpose, goal = V.SECTION_PURPOSE, V.SECTION_GOAL
    swapped = golden.replace(purpose, "\0").replace(goal, purpose).replace("\0", goal)
    assert "F02" in structural_codes(swapped)


def test_risk_reason_order_swap_is_r01(structural_codes, golden):
    health, trust = V.RISK_REASONS[0], V.RISK_REASONS[1]
    swapped = golden.replace(health, "\0").replace(trust, health).replace("\0", trust)
    assert "R01" in structural_codes(swapped)


def test_challenge_date_before_declared_on_is_d01(structural_codes, golden):
    text = replace_once(golden, "challenge_date: 2026-12-12", "challenge_date: 2026-10-01")
    text = replace_once(text, "12月12日に開催する", "10月1日に開催する")
    assert structural_codes(text) == ["D01"]


def test_iso_date_in_challenge_body_is_accepted(structural_codes, golden):
    text = replace_once(golden, "12月12日に開催する", "2026-12-12に開催する")
    assert structural_codes(text) == []


def test_filename_date_mismatch_is_n01(structural_codes, golden):
    assert structural_codes(golden, "UBM - 挑戦宣言 - 2026-10-09.md") == ["N01"]


def test_non_canonical_filename_skips_n01(structural_codes, golden):
    assert structural_codes(golden, "golden-sample.md") == []


def test_action_continuation_line_joins_previous_item(structural_codes, golden):
    text = replace_once(golden, "3.YouTubeを毎日発信し、", "3.YouTubeを毎日発信し、\n")
    assert structural_codes(text) == []


def test_goal_with_full_width_digits_is_accepted(structural_codes, golden):
    """G01 は全角数字も数値として数える (C01/C02 と同じ)。"""
    text = replace_once(
        golden, "・個別相談 30件\n・運営メンバーからの引き上げ 10件", "・個別相談３０件\n・運営メンバーからの引き上げ１０件"
    )
    assert structural_codes(text) == []


# 頻度の言い方。タイミング (曜日・時刻) の語を含めず、頻度だけで P01 に合格することを確かめる。
# 「月報で」「定例で」「面談で」は question-map の切り口① (すでに続いている定期の場)。
REPORTS_ACCEPTED = [
    ("frequency-only", "週1回、集客数の経過を報告します。"),
    ("weekly-timing", "毎週月曜9時に集客数の経過を報告します。"),
    ("timing-only", "月曜9時に集客数の経過を報告します。"),
    ("week-1-de", "週1で集客数の経過を報告します。"),
    ("week-kanji-kai", "週一回、集客数の経過を報告します。"),
    ("week-ni-ichido", "週に一度、集客数の経過を報告します。"),
    ("1-week-ni-1-kai", "1週間に1回、集客数の経過を報告します。"),
    ("2-weeks-ni-1-kai", "2週間に1回、集客数の経過を報告します。"),
    ("3-months-ni-1-do", "3ヶ月に1度、集客数の経過を報告します。"),
    ("kakugetsu", "隔月で集客数の経過を報告します。"),
    ("kakushu", "隔週で集客数の経過を報告します。"),
    ("shuji", "週次で集客数の経過を報告します。"),
    ("getsuji", "月次で集客数の経過を報告します。"),
    ("geppo", "月報で集客数の経過を報告します。"),
    ("shuho", "週報で集客数の経過を報告します。"),
    ("teirei", "定例で集客数の経過を報告します。"),
    ("mendan", "面談で集客数の経過を報告します。"),
    ("maishu", "毎週、集客数の経過を報告します。"),
    ("month-2-kai", "月2回、集客数の経過を報告します。"),
    ("3-days-goto", "3日ごとに集客数の経過を報告します。"),
    ("1-day-ni-1-kai", "1日に1回、集客数の経過を報告します。"),
    ("maitsuki-mendan-de", "毎月の面談で集客数の経過を報告します。"),
]


@pytest.mark.parametrize("report", [r for _, r in REPORTS_ACCEPTED], ids=[i for i, _ in REPORTS_ACCEPTED])
def test_report_needs_only_frequency_or_timing(structural_codes, golden, report):
    """P01 は頻度かタイミング (曜日・時刻) のどちらかで合格。報告先は対話で聞くだけで検査しない。"""
    text = replace_once(golden, "週1回、月曜9時にLINEで集客数の経過を報告します。", report)
    assert structural_codes(text) == []


# ---- 精神論の語 (S01) ------------------------------------------------------------------------
# challenge-format.md の違反コード表 S01 行に挙がる例と、run-ubm-goal-setting の NG 表現
# (references/data-contract.md の検査 #7) の5語を、終止形で書いても不合格になることを固定する。
# 語幹が「意識し」だけだと「意識する」を拾わない、という取りこぼしを止めるため。

GOAL_SPIRIT_WORDS = ("頑張る", "意識する", "気をつける", "心がける", "努力する")


def _format_spirit_examples() -> list[str]:
    """challenge-format.md の S01 行「（頑張る・意識する・気をつける 等）」から例の語を取り出す。"""
    doc = FORMAT_DOC.read_text(encoding="utf-8")
    m = re.search(r"^\| S01 \|[^（\n]*（([^）\n]*?)\s*等）", doc, re.M)
    return [word for word in m.group(1).split("・") if word] if m else []


SPIRIT_WORDS = tuple(dict.fromkeys((*_format_spirit_examples(), *GOAL_SPIRIT_WORDS)))


def test_format_doc_lists_spirit_examples():
    assert _format_spirit_examples(), "challenge-format.md の S01 行に精神論の語の例がありません"


@pytest.mark.parametrize("word", SPIRIT_WORDS)
def test_spirit_word_in_action_is_s01(structural_codes, golden, word):
    text = replace_once(
        golden, "2.個別相談をセミナー開催前から受け付ける", f"2.個別相談をセミナー開催前から受け付けるよう{word}"
    )
    assert "S01" in structural_codes(text)


# ---- お金の補助関数 --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token,yen",
    [("100万円", 1_000_000), ("3万", 30_000), ("50,000円", 50_000), ("2.5万円", 25_000), ("1億", 100_000_000), ("円", None)],
)
def test_parse_yen(token, yen):
    assert V.parse_yen(token) == yen


def test_find_products_reads_golden_breakdown(golden):
    products = V.find_products(golden)
    assert [(p.unit_yen, p.count, p.total_yen) for p in products] == [(30_000, 30, 900_000), (50_000, 10, 500_000)]
    assert all(p.consistent for p in products)


def test_find_products_flags_count_written_in_man():
    """例文原文の誤記「5万×10万で50万円」は件数 10万として読み、計算不一致になる。"""
    [product] = V.find_products("VIP先行予約は5万×10万で50万円")
    assert product.count == 100_000
    assert not product.consistent


def test_find_sums_reads_golden_total(golden):
    [total] = V.find_sums(golden)
    assert total.terms_yen == (1_000_000, 900_000, 500_000)
    assert total.total_yen == 2_400_000
    assert total.consistent


# ---- お金の理由 (M01) ------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "会場は自宅スタジオで、1円も費用がかからない。",
        "会場費は0円。登壇者も無償。",
        "スポンサーのブース出展で100万円を回収済み。",
        "有料運営メンバーは3万円×30人で90万円を入金済み。",
        "12月12日開催予定。スポンサーで100万円を回収済み。",  # 開催予定はお金の見込みではない
        "目標300万円のうち、スポンサーで100万円を回収済み。",  # 目標額は見込みと読まない
        "スポンサーで100万円を回収しています。",
        "有料運営メンバーは3万円×30人で90万円を回収できている。",
        "スポンサーの協賛100万円が確定した。",
        "スポンサーの協賛100万円（確定）を会場費に充てる。",
        "スポンサーで100万円を回収済み。自己負担はゼロ。",  # 自己負担が無いことを言う文は自己負担と読まない
        "会場は無料で、自分で払うものはない。",
        "会場は無料。自分で払う必要はない。",
        "会場費は自分で払わず、スポンサーが持つ。会場は無料。",
        "費用はかからないということです。",  # 肯定の「ということ」を否定と読まない
        "会場は無料。自分で払う費用は一切ありません。",
        "会場は無料。自己負担は一切なし。",
        "会場は無料。自分で払うことはない。",
        "会場は無料。自分で払わなくていい。",
        # 立替えは同じ文の後ろで回収済みなら自分で払う費用と読まない
        "立替えた分は回収済み。スポンサーで100万円を回収済み。",
        "会場費30万円は立替えたが、スポンサーから30万円を回収済み。",
    ],
)
def test_money_reason_accepts_zero_cost_or_collected_amount(text):
    assert V.check_money_reason(text) == []


@pytest.mark.parametrize(
    "text,fragment",
    [
        ("スポンサーを探しています。", "回収済み"),
        ("参加費100円で集める。", "回収済み"),  # 100円 の末尾の 0円 を費用ゼロと読まない
        # 否定形を回収済みと読まない
        ("会場費30万円はまだ回収できていません。", "回収済み"),
        ("参加費3万円×10人＝30万円は確定していない。", "回収済み"),
        ("スポンサーの100万円は回収できず、会場費は自分で払う。", "回収済み"),
        ("協賛金100万円は回収していない。", "回収済み"),
        ("協賛金100万円は未確定。", "回収済み"),
        # 条件形を回収済みと読まない
        ("スポンサーの100万円は回収できれば会場費に充てる。", "回収済み"),
        ("協賛30万円は確定次第、会場費に充てる。", "回収済み"),
        ("協賛30万円は確定できれば会場費に充てる。", "回収済み"),
        # 確定は完了形だけを回収済みと読む
        ("協賛30万円は確定予定で会場費に充てる。", "回収済み"),
        ("協賛30万円は確定前だが会場費に充てる。", "回収済み"),
        ("協賛は確定待ち。会場費はスポンサーが持つ。", "回収済み"),
        # 費用ゼロの否定と、一部だけ無料で残りを自分で払う形を費用ゼロと読まない
        ("会場は無料ではない。", "回収済み"),
        ("会場費は無料でない。", "回収済み"),
        ("費用はかからない、ということはない。", "回収済み"),
        ("無料ではない。会場費30万円を自分で払う。", "自分で払う"),
        ("会場費はかかっていないが、講師料30万円は自分で払う。", "自分で払う"),
        ("費用は1円もかからないわけではなく、会場費30万円を自分で負担する。", "自分で払う"),
        # 離れた「ない」「ゼロ」は自分で払う費用の否定と読まない。言い換えも拾う
        ("会場費は無料。講師料は自分で払うしかない。", "自分で払う"),
        ("会場費は無料。講師料10万円を自分で払い、交通費はない。", "自分で払う"),
        ("会場費は無料。講師料10万円は自分で払うが、ゼロにはならない。", "自分で払う"),
        ("会場費は無料。講師料10万円は私が負担する。", "自分で払う"),
        ("会場費は無料。講師料は自分持ち。", "自分で払う"),
        ("会場は無料。講師料10万円は私が立て替える。", "自分で払う"),
        ("講師料10万円は自分で払い、会場費30万円はスポンサーから回収済み。", "自分で払う"),
        # 義務の言い方を否定と読まない
        ("会場は無料。講師料10万円は自分で払わないといけない。", "自分で払う"),
        ("会場は無料。講師料は自分で払わなくてはならない。", "自分で払う"),
        ("会場は無料。講師料は自分で負担しないといけない。", "自分で払う"),
        ("スポンサーから協賛を回収済み。", "確定した金額"),
        ("スポンサーで100万円を回収済み。物販で30万円の売上見込み。", "見込み・予定"),
        ("スポンサーで100万円を回収済み。物販で30万円を入金予定。", "見込み・予定"),
        ("会場は無償提供で費用ゼロ。物販の売上見込み5万円。", "見込み・予定"),  # 費用ゼロでも見込みの額は書かない
        # 回収済みと同じ欄に混ざった未確定の額を数えない
        ("スポンサーで100万円を回収済み。物販の30万円は未確定。", "未確定"),
        ("スポンサーで100万円を回収済み。\n会場費30万円はまだ入金されていない。", "未確定"),
        ("VIP先行予約は5万×10万で50万円を決済済み。", "計算が合いません"),
        ("100万円を回収済み。90万円を入金済み。100万円＋90万円で200万円が確定。", "計算が合いません"),
    ],
)
def test_money_reason_rejects(text, fragment):
    problems = V.check_money_reason(text)
    assert any(fragment in p for p in problems), problems


def test_money_miscalculation_fails_end_to_end(tmp_path, golden):
    text = replace_once(golden, "5万円×10人で50万円", "5万円×10万で50万円")
    r = run("--file", str(write(tmp_path, text)))
    assert r.returncode == 1
    assert "[M01]" in r.stdout
