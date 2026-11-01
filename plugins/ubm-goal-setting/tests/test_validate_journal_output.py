"""validate-journal-output.py の保存前バリデーションテスト。

同梱 golden-sample.md を正本として PASS を確認し、骨格欠落・空セクション・日付不一致・
番号不一致・未置換プレースホルダの各変異が FAIL することを検証する。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
VALIDATE = PLUGIN_ROOT / "skills/run-ubm-journal/scripts/validate-journal-output.py"
GOLDEN = PLUGIN_ROOT / "skills/run-ubm-journal/assets/golden-sample.md"

GOLDEN_NAME = "2026-08-18.md"
GOLDEN_NUMBER = 389
GOLDEN_DATE = "2026-08-18"

# 四半期見出しの正本と後方互換表記。validator の QUARTERLY_HEADING と一致することを
# test_quarterly_heading_constants_track_validator が縛る (ここを直書きしたまま validator
# 側の正本が変わると、置換が空振りして併存 test が無内容に退化するため)。
CANONICAL_QUARTERLY = "### 3ヶ月目標"
LEGACY_QUARTERLY = "### 2ヶ月目標"


def run(path: Path, number: int | None = None, date: str | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(VALIDATE), "--file", str(path)]
    if number is not None:
        cmd += ["--expected-number", str(number)]
    if date is not None:
        cmd += ["--expected-date", date]
    return subprocess.run(cmd, capture_output=True, text=True)


def write(tmp_path: Path, text: str, name: str = GOLDEN_NAME) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _load_validator():
    """script を module として読み込む (純関数を直接検査するため)。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_validate_journal_output", VALIDATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def golden() -> str:
    return GOLDEN.read_text(encoding="utf-8")


def test_golden_sample_passes(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout


def test_bad_filename_fails(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden, name="journal.md"))
    assert proc.returncode == 1
    assert "F01" in proc.stdout


def test_heading_date_mismatch_fails(tmp_path: Path, golden: str):
    text = golden.replace("ジャーナル（2026-08-18）", "ジャーナル（2026-08-17）")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "F03" in proc.stdout


def test_number_mismatch_fails(tmp_path: Path, golden: str):
    proc = run(write(tmp_path, golden), 400, GOLDEN_DATE)
    assert proc.returncode == 1
    assert "F04" in proc.stdout


def test_missing_heading_fails(tmp_path: Path, golden: str):
    text = golden.replace("# No.389 - ジャーナル（2026-08-18）", "# ジャーナル")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "F02" in proc.stdout


def test_missing_required_section_fails(tmp_path: Path, golden: str):
    text = golden.replace("## 感謝", "## ありがとう")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "S01" in proc.stdout


def test_out_of_order_section_fails(tmp_path: Path, golden: str):
    # 【禁止事項】を【タスク】より後ろへ移すと順序違反
    text = golden.replace("## 【禁止事項】", "## __TMP__").replace("## 【タスク】", "## 【禁止事項】")
    text = text.replace("## __TMP__", "## 【タスク】")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "S01" in proc.stdout


def test_goal_missing_period_field_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 期間：2026-07-27〜2026-08-31\n", "")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G01" in proc.stdout


def test_goal_bad_period_format_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 期間：2026-07-27〜2026-08-31", "- 期間：7月末から8月末まで")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G02" in proc.stdout


def test_quarterly_heading_constants_track_validator():
    """test 側の見出し定数が validator の正本・後方互換表記と一致すること。"""
    module = _load_validator()
    assert module.QUARTERLY_HEADING[0] == CANONICAL_QUARTERLY.removeprefix("### ")
    assert LEGACY_QUARTERLY.removeprefix("### ") in module.QUARTERLY_HEADING[1:]


def test_legacy_two_month_heading_remains_valid(tmp_path: Path, golden: str):
    """既存ジャーナルの旧見出し (2ヶ月目標) は再検証で骨格違反にしない。

    正本は `3ヶ月目標` (QUARTERLY_HEADING の先頭)。旧表記で保存済みのジャーナルを
    後から検証し直しても骨格違反にならないことを、置換が実際に起きたことを
    確かめたうえで検査する (見出しが変わって置換が空振りすると、この test は
    「golden がそのまま通る」だけの無内容な test に退化するため)。
    """
    assert CANONICAL_QUARTERLY in golden
    text = golden.replace(CANONICAL_QUARTERLY, LEGACY_QUARTERLY, 1)
    assert LEGACY_QUARTERLY in text
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout


def test_canonical_quarterly_goal_wins_when_legacy_heading_also_exists(
    tmp_path: Path, golden: str
):
    """併存時に旧見出しの本文で満足して正本側の空値を見逃してはならない。

    旧表記の完成セクションを正本セクションより前に置き、正本の「- 目標：」だけを
    空にする。旧表記側を先に拾って PASS すると fail-open になるので、違反が
    正本の見出し名で報告されることを要求する。
    """
    assert CANONICAL_QUARTERLY in golden
    legacy_section = f"""{LEGACY_QUARTERLY}

- 期間：2026-06-29〜2026-08-30
- 残り：12日
- 目標：旧表記側には値がある。

"""
    text = golden.replace(
        f"{CANONICAL_QUARTERLY}\n", legacy_section + f"{CANONICAL_QUARTERLY}\n", 1
    )
    canonical_body = (
        "次回壁打ち（9/9・北原さん）までに、ティアマインドの支援が期待値6項目の合意文書の上で回り、"
        "青木さんの週1支援と合わせて毎月の固定費300,000に届く売上の形が見えている状態を作った。"
    )
    assert canonical_body in text
    text = text.replace(f"- 目標：{canonical_body}", "- 目標：", 1)
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1, proc.stdout
    assert "G03: 3ヶ月目標" in proc.stdout, proc.stdout


def test_empty_gratitude_fails(tmp_path: Path, golden: str):
    start = golden.index("## 感謝")
    end = golden.index("## 【禁止事項】")
    text = golden[:start] + "## 感謝\n\n" + golden[end:]
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "C02" in proc.stdout


def test_task_without_category_fails(tmp_path: Path, golden: str):
    text = golden.replace("### 【個人向けAIコンサル（生命線）】", "").replace("### 【記録・習慣】", "")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "C04" in proc.stdout


def test_empty_journal_subsection_fails(tmp_path: Path, golden: str):
    # 【行動のジャーナル】の「現状を確認する」小節を丸ごと空にする
    start = golden.index("### 現状を確認する")
    end = golden.index("### 効果性を評価する")
    text = golden[:start] + "### 現状を確認する\n\n" + golden[end:]
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "J02" in proc.stdout


def test_missing_journal_subsection_fails(tmp_path: Path, golden: str):
    text = golden.replace("### 効果性を評価する", "### 振り返り", 1)
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "J01" in proc.stdout or "S01" in proc.stdout


def test_unreplaced_placeholder_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 北原さん: 8/16のUBM兵庫支部会", "- [名前]: [感謝の内容] 8/16のUBM兵庫支部会")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "X01" in proc.stdout


def test_missing_file_fails_closed(tmp_path: Path):
    proc = run(tmp_path / "nope.md")
    assert proc.returncode == 2


# --- H01: 毎日固定の習慣がヒアリング・記録されたか -------------------------

HABITS = json.loads(
    (PLUGIN_ROOT / "skills/run-ubm-journal/references/daily-habits.json").read_text(
        encoding="utf-8"
    )
)["habits"]


def test_golden_sample_covers_every_daily_habit(golden: str):
    """見本が6習慣すべてに痕跡を持つ（H01 の基準線が実在することの担保）。"""
    missing = [h["id"] for h in HABITS if not any(k in golden for k in h["keywords"])]
    assert not missing, f"golden-sample に痕跡が無い習慣: {missing}"


@pytest.mark.parametrize("habit", HABITS, ids=[h["id"] for h in HABITS])
def test_missing_daily_habit_record_fails(tmp_path: Path, golden: str, habit: dict):
    """各習慣について、その痕跡を全て消すと H01 で FAIL する。"""
    text = golden
    for kw in habit["keywords"]:
        text = text.replace(kw, "＿")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "H01" in proc.stdout
    assert habit["label"] in proc.stdout


def test_daily_habits_json_is_wellformed():
    """正本の必須キーを固定する（キー名変更でスクリプト側が黙って壊れるのを防ぐ）。"""
    assert HABITS, "habits が空"
    for h in HABITS:
        for key in ("id", "label", "natural_question", "target_section", "unmet_signal", "keywords"):
            assert h.get(key), f"{h.get('id')}: {key} が空"
        assert isinstance(h["keywords"], list) and h["keywords"], f"{h['id']}: keywords が空"


# --- H01 が「本文のどこかに単語がある」で通る死んだ検査になっていないか ---

def _strip_section(text: str, heading: str, next_heading: str) -> str:
    """指定 H2 セクションの本文を空にする (見出しは残す)。"""
    start = text.index(heading) + len(heading)
    end = text.index(next_heading)
    return text[:start] + "\n\n" + text[end:]


def test_habit_keyword_outside_its_scope_does_not_satisfy_h01(tmp_path: Path, golden: str):
    """禁止事項や見出しにキーワードが常在するだけで PASS してはいけない。

    v1 の H01 は本文全体の substring 検索だったため、【行動のジャーナル】を空にしても
    禁止事項の定型行・H1 見出し・チェックシートの固定設問に単語が残り、
    Gridノート/ジャーナル/SNS の 3 件が発火しなかった。
    """
    text = _strip_section(golden, "## 【行動のジャーナル】", "## 【時間のジャーナル】")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    for label in ("Gridノートを書いた", "ジャーナルを書いた", "SNSに投稿した"):
        assert f"H01: 毎日の習慣「{label}」" in proc.stdout, proc.stdout


def test_video_habit_is_not_satisfied_by_the_prohibition_boilerplate(tmp_path: Path, golden: str):
    """【禁止事項】の『漫画・YouTubeへ逃げない』は記録ではなくテンプレの定型行。"""
    text = _strip_section(golden, "## 【時間のジャーナル】", "## 【お金のジャーナル】")
    proc = run(write(tmp_path, text))
    assert "YouTube" in text, "禁止事項側の定型行は残っている前提のテスト"
    assert "H01: 毎日の習慣「決められた時間以外に動画等を見なかった」" in proc.stdout, proc.stdout


def test_habit_without_search_scopes_is_reported():
    """scope 未宣言を素通しすると v1 の全文検索へ逆戻りする。

    repo 同梱の daily-habits.json は書き換えず、検査関数を直接叩いて確かめる。
    """
    mod = _load_validator()
    out = mod.check_daily_habits(
        ["## 【行動のジャーナル】", "- Gridノートを朝に書いた"],
        [{"id": "x", "label": "テスト習慣", "keywords": ["Gridノート"]}],
    )
    assert any(v.startswith("H02:") for v in out), out


def test_scope_limits_the_search_range():
    """scope 外に同じ単語があっても記録ありとみなさない。"""
    mod = _load_validator()
    lines = [
        "## 【禁止事項】",
        "- 漫画・YouTubeへ逃げない",
        "## 【時間のジャーナル】",
        "- 就寝は23:40。",
    ]
    habit = {
        "id": "no-unplanned-video", "label": "動画", "target_section": "【時間のジャーナル】",
        "search_scopes": [{"heading": "【時間のジャーナル】", "level": 2}],
        "keywords": ["YouTube", "動画"],
    }
    assert mod.check_daily_habits(lines, [habit]), "禁止事項側の定型行で PASS してはいけない"
    lines[3] = "- 予定外のYouTube視聴が45分あった。"
    assert mod.check_daily_habits(lines, [habit]) == []


# --- 見出し照合が部分一致で正本逸脱を通していないか ---

@pytest.mark.parametrize("before,after", [
    ("## 目標", "## 今週の習慣目標"),
    ("## 感謝", "## 感謝したくないリスト"),
])
def test_renamed_heading_is_detected(tmp_path: Path, golden: str, before: str, after: str):
    text = golden.replace(before + "\n", after + "\n", 1)
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "S01" in proc.stdout, proc.stdout


# --- 「枠が埋まっている」検査が空値・波括弧プレースホルダを通していないか ---

def test_empty_goal_value_fails(tmp_path: Path, golden: str):
    text = golden.replace("- 目標：", "- 目標：\n<!--x-->", 1)
    # 1行目の `- 目標：` を値なしにする (直後行はコメントで箇条書きにしない)
    proc = run(write(tmp_path, text))
    assert "G03" in proc.stdout, proc.stdout


def test_curly_placeholder_is_detected(tmp_path: Path, golden: str):
    text = golden.replace("- 残り：", "- 残り：{days_remaining}日 —— ", 1)
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "X01" in proc.stdout, proc.stdout


def test_numbered_list_counts_as_content(tmp_path: Path, golden: str):
    """正当な番号付きリストを空扱いにして誤 FAIL させない。"""
    start = golden.index("## 感謝")
    end = golden.index("## 【禁止事項】")
    replaced = "## 感謝\n\n1. 北原さん: 打ち合わせの時間をいただきありがとうございました。\n\n"
    proc = run(write(tmp_path, golden[:start] + replaced + golden[end:]))
    assert "C02" not in proc.stdout, proc.stdout


# --- 正本が要求する frontmatter / transclusion ---

def test_missing_frontmatter_fails(tmp_path: Path, golden: str):
    text = golden.split("---\n", 2)[-1]
    proc = run(write(tmp_path, text))
    assert "Y01" in proc.stdout, proc.stdout


def test_missing_transclusion_fails(tmp_path: Path, golden: str):
    text = golden.replace("![[人生の究極の目的", "[[人生の究極の目的", 1)
    proc = run(write(tmp_path, text))
    assert "Y02" in proc.stdout, proc.stdout


# --- fail-open の回帰: 検査対象を取り違えていた 3 件 ---


def test_g02_does_not_accept_a_date_range_from_another_line(tmp_path: Path, golden: str):
    """G02 は「- 期間：」の値に掛かる。節全体に掛けると同節の別行で充足してしまう。

    実測で再現済みだった fail-open: 期間を「今週いっぱい」にしても、目標本文に
    日付範囲が 1 つあるだけで `PASS: 違反 0 件` exit 0 になっていた。
    """
    text = golden.replace(
        "- 期間：2026-07-27〜2026-08-31\n- 残り：13日\n- 目標：",
        "- 期間：今週いっぱい\n- 残り：13日\n- 目標：2026-07-27〜2026-08-31 の間に ",
        1,
    )
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1, proc.stdout
    assert "G02" in proc.stdout, proc.stdout


def test_y01_is_bound_to_the_tags_key(tmp_path: Path, golden: str):
    """`- review` という行の存在ではなく tags キーの値を見る。"""
    # 偽陰性: aliases 配下の `- review` では満たされない
    text = golden.replace("tags:\n  - review\n", "aliases:\n  - review\n", 1)
    proc = run(write(tmp_path, text))
    assert "Y01" in proc.stdout, proc.stdout


def test_y01_accepts_inline_tag_notation(tmp_path: Path, golden: str):
    """偽陽性: `tags: [review]` は YAML として同値なので FAIL にしない。"""
    text = golden.replace("tags:\n  - review\n", "tags: [review, daily]\n", 1)
    proc = run(write(tmp_path, text))
    assert "Y01" not in proc.stdout, proc.stdout


def test_h01_is_not_satisfied_by_an_html_comment(golden: str):
    """HTML コメントは Obsidian で表示されない = 記録ではない。

    生行を照合していた頃は、キーワードを並べたコメントを貼るだけで全習慣が通った。
    """
    mod = _load_validator()
    target = HABITS[0]
    keyword = target["keywords"][0]
    scope = target["search_scopes"][0]

    lines = golden.splitlines()
    body_start = next(
        i for i, l in enumerate(lines) if l.strip().startswith("#") and scope["heading"] in l
    )
    # 本文の実記録を消し、代わりに同じキーワードを HTML コメントで置く
    stripped = [l for l in lines if keyword not in l]
    stripped.insert(body_start + 1, f"<!-- {keyword} -->")
    out = mod.check_daily_habits(stripped, [target])
    assert any("H01" in e for e in out), out


def test_x01_does_not_flag_prose_braces(tmp_path: Path, golden: str):
    """`/invoice/{id}` のような正当な記述を未置換プレースホルダにしない。"""
    text = golden + "\n- API `/invoice/{id}` の疎通を確認した\n"
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert "X01" not in proc.stdout, proc.stdout


def test_x01_still_flags_template_placeholders(tmp_path: Path, golden: str):
    """正本テンプレの名前は引き続き検出する (限定した結果、検査が死んでいないこと)。"""
    text = golden + "\n- 残り {days_remaining} 日\n"
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert "X01" in proc.stdout, proc.stdout


def test_y02_is_not_satisfied_by_an_html_comment(tmp_path: Path, golden: str):
    """コメント内の transclusion は Obsidian で埋め込まれない。H01 と同じ基準で見る。"""
    mod = _load_validator()
    m = mod.TRANSCLUSION_RE.search(golden)
    assert m, "golden から究極目的の transclusion が消えた"
    text = golden.replace(m.group(0), f"<!-- {m.group(0)} -->", 1)
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert "Y02" in proc.stdout, proc.stdout


def test_habit_schema_problems_are_input_errors():
    """label 欠落・keywords が文字列は「破損 = exit 2」契約の対象。

    keywords を文字列にすると 1 文字ずつ照合され、'G' がどこかに当たるだけで
    H01 が無条件 PASS になる (SSOT 破損時の fail-open)。
    """
    mod = _load_validator()
    ok = {
        "id": "x", "label": "習慣", "target_section": "節",
        "keywords": ["Grid"], "search_scopes": [{"level": 2, "heading": "節"}],
    }
    assert mod.habit_schema_problems(ok, 0) == []
    assert mod.habit_schema_problems({**ok, "label": ""}, 0)
    assert mod.habit_schema_problems({**ok, "keywords": "Grid"}, 0)
    assert mod.habit_schema_problems({**ok, "search_scopes": [{"level": 2}]}, 0)
    # search_scopes 未宣言は H02 で報告する設計なので、読み込み時には落とさない
    assert mod.habit_schema_problems({k: v for k, v in ok.items() if k != "search_scopes"}, 0) == []


def test_y01_accepts_zero_indent_block_notation():
    """`tags:` の次行にゼロインデントの `- review` は YAML として妥当。FAIL にしない。"""
    mod = _load_validator()
    assert mod.has_review_tag("tags:\n- review\n- daily") is True
    assert mod.has_review_tag("tags:\n- daily\nauthor: x") is False
    # aliases 配下の `- review` を tags と取り違えないこと (偽陰性の回帰)
    assert mod.has_review_tag("aliases:\n- review\ntags:\n- daily") is False


def test_g02_requires_hyphen_separated_dates(tmp_path: Path, golden: str):
    """検査が文書 (output-format.md) より緩いと、直した人に何も返らない。"""
    text = golden.replace("- 期間：2026-07-27〜2026-08-31", "- 期間：2026/07/27〜2026/08/31")
    proc = run(write(tmp_path, text))
    assert "G02" in proc.stdout, proc.stdout


def test_string_level_in_search_scopes_is_an_input_error():
    """`"level": "2"` は section_lines の `lv == level` を常に偽にする。

    記録が正しく書かれた本文が H01 で FAIL し、利用者は本文を直しても直らない。
    heading 欠落と同じく「読めない設定」として exit 2 側で原因を名指しする。
    """
    mod = _load_validator()
    ok = {
        "id": "x", "label": "習慣", "target_section": "節",
        "keywords": ["Grid"], "search_scopes": [{"level": 2, "heading": "節"}],
    }
    assert mod.habit_schema_problems({**ok, "search_scopes": [{"level": "2", "heading": "節"}]}, 0)
    assert mod.habit_schema_problems({**ok, "search_scopes": [{"level": 0, "heading": "節"}]}, 0)
    # level 省略は既定 2 として妥当 (実データの大半がこの形)
    assert mod.habit_schema_problems({**ok, "search_scopes": [{"heading": "節"}]}, 0) == []


def test_brace_placeholders_cover_output_format():
    """正本テンプレが使う `{...}` は全て X01 の検査対象であること。

    コードのコメントは「output-format.md と対で管理する」と宣言していたが、
    導入時点で `{名前}` が漏れており、`- {名前}: 手伝ってくれた` が exit 0 で
    通っていた (部分置換の取りこぼし)。約束を人手の注意力に預けた結果なので、
    ここで機械的に固定する。逆方向 (タプル側の過剰登録) は無害なので許す。
    """
    mod = _load_validator()
    fmt = (
        Path(mod.__file__).resolve().parents[1] / "references" / "output-format.md"
    ).read_text(encoding="utf-8")
    used = set(re.findall(r"\{([^{}\n]+)\}", fmt))
    missing = used - set(mod.BRACE_PLACEHOLDERS)
    assert not missing, f"output-format.md の {missing} が BRACE_PLACEHOLDERS に未登録"


def test_x01_flags_the_gratitude_name_placeholder():
    """`{名前}` だけが残った部分未置換を取りこぼさない。"""
    mod = _load_validator()
    assert mod.PLACEHOLDER_RE.search("- {名前}: 手伝ってくれた")


def test_y02_is_not_satisfied_by_a_fenced_code_block():
    """コードフェンス内の transclusion は Obsidian が埋め込まない。

    HTML コメントと同じ「書いてはあるが表示されない」クラス。生テキスト照合だと
    「究極目的が表示されている」という Y02 の判定根拠が成立しないまま PASS する。
    """
    mod = _load_validator()
    fenced = "```\n![[人生の究極の目的]]\n```\n"
    assert mod.TRANSCLUSION_RE.search(fenced)          # 生テキストには在る
    assert not mod.TRANSCLUSION_RE.search(mod.visible_text(fenced))
    # 素の transclusion は当然そのまま残る
    assert mod.TRANSCLUSION_RE.search(mod.visible_text("![[人生の究極の目的]]\n"))


def test_h01_treats_a_fenced_block_as_not_a_record():
    """フェンス内だけの記録は H01 で「ありません」と言う (意図した fail-closed 側の誤り)。

    Y02 は「Obsidian が埋め込まない」ことを根拠にフェンスを外すが、H01 では同じ根拠が
    使えない (フェンスの中身は読者に見える)。それでも外すのは、フェンスに入るのが
    その日の記録ではなく貼り付けたテンプレ・例・コマンドだからで、そこを数えると
    H01 が v1 の死んだ検査へ戻る。副作用として素の記録より厳しく出るので、
    偶然そうなっているのではなく決めた挙動であることをここで固定する。
    """
    mod = _load_validator()
    habit = {
        "id": "grid-note", "label": "Gridノートを書いた",
        "target_section": "【行動のジャーナル】現状を確認する",
        "keywords": ["Gridノート"],
        "search_scopes": [{"heading": "【行動のジャーナル】", "level": 2}],
    }

    def h01(body: str) -> list[str]:
        return mod.check_daily_habits(
            f"## 【行動のジャーナル】\n{body}\n## 次\n".splitlines(), [habit]
        )

    assert h01("- 22:10 に Gridノートを書いた。") == []
    assert h01("> 22:10 に Gridノートを書いた。") == []  # 引用は記録として数える
    assert h01("```\n- 22:10 に Gridノートを書いた。\n```")
    assert h01("<!-- Gridノートを書いた -->")


def test_legacy_quarterly_heading_still_passes(tmp_path: Path, golden: str):
    """旧表記 `### 2ヶ月目標` だけで書かれた既存ジャーナルを骨格違反にしない。

    正本は `3ヶ月目標` だが、過去分を再検証したときに S01 で落ちると
    「書き換えないと検証できない」記録が生まれる。後方互換の受理はこの改名の
    主目的なので、golden 全体を旧表記へ倒した状態を PASS として固定する。
    """
    text = golden.replace("### 3ヶ月目標", "### 2ヶ月目標")
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout


def test_legacy_quarterly_heading_violation_names_the_written_heading(
    tmp_path: Path, golden: str
):
    """旧表記で書かれた節の違反メッセージは、実際に書かれていた見出し名で出す。

    `GOAL_SECTIONS` の要素はタプル (正本, 旧表記) なので、素朴に f-string へ
    埋めると「('3ヶ月目標', '2ヶ月目標') に…」という内部表現が利用者に漏れる。
    validate() の 367-376 がここを解決している。その分岐を固定する。
    """
    text = golden.replace("### 3ヶ月目標", "### 2ヶ月目標").replace(
        "- 期間：2026-06-29〜2026-09-27\n", ""
    )
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G01: 2ヶ月目標 に「- 期間：」の行がありません" in proc.stdout
    # タプルを素朴に f-string へ埋める退行はここで落とす。
    assert "('3ヶ月目標'" not in proc.stdout


def test_legacy_quarterly_heading_is_noticed_even_though_it_passes(
    tmp_path: Path, golden: str
):
    """旧表記を受理はするが黙らない。PASS したまま正本への書き換えを促す。

    受理だけして無言だと、「前回ジャーナルを継承して今日の分を書く」運用の中で
    旧表記が自己複製し続け、正本へ寄る契機が来ない (自己複製の指摘が smell の実体)。
    """
    text = golden.replace("### 3ヶ月目標", "### 2ヶ月目標")
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "NOTICE: D01" in proc.stdout
    # 「今どれが書かれていて、何に直すのか」の両方が読めること。
    assert "「2ヶ月目標」" in proc.stdout and "「3ヶ月目標」" in proc.stdout


def test_canonical_heading_emits_no_notice(tmp_path: Path, golden: str):
    """正本どおりのジャーナルには通知を出さない (常時 NOTICE は無視されて死ぬ)。"""
    proc = run(write(tmp_path, golden), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "NOTICE" not in proc.stdout


def test_deprecation_notice_survives_a_failing_run(tmp_path: Path, golden: str):
    """違反があっても通知は出す。

    FAIL のとき黙ると、違反を直して再実行し PASS した瞬間にしか旧表記に気づけない。
    通知が一番効くのは「今まさにこのファイルを直している」周回のほうなので、
    そこで消えるのは通知経路として本末転倒になる。
    """
    text = golden.replace("### 3ヶ月目標", "### 2ヶ月目標").replace(
        "- 期間：2026-06-29〜2026-09-27\n", ""
    )
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "NOTICE: D01" in proc.stdout


def _with_both_quarterly_headings(golden: str, canonical_body: str) -> str:
    """正本 `### 3ヶ月目標` の手前に完全な旧表記 `### 2ヶ月目標` 節を差し込む。

    「移行途中で両方書いてしまった」異常系。本文の出現順は 2ヶ月 → 3ヶ月になる。
    """
    legacy = (
        "### 2ヶ月目標\n"
        "- 期間：2026-06-29〜2026-08-30\n"
        "- 残り：5日\n"
        "- 目標：旧表記の節に書かれた本文。\n"
    )
    # 正本節は「中身ごと」差し替える。golden の本文を残したまま前置きすると、
    # 期間行が居座って何を検査しているのか分からないテストになる。
    replaced, count = re.subn(
        r"### 3ヶ月目標\n.*?(?=^### )",
        legacy + "### 3ヶ月目標\n" + canonical_body,
        golden,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert count == 1, "golden の `### 3ヶ月目標` 節を特定できなかった"
    return replaced


def test_both_quarterly_headings_validates_the_canonical_section(
    tmp_path: Path, golden: str
):
    """3ヶ月・2ヶ月が併存したら、検査対象は必ず正本の `3ヶ月目標` 節にする。

    body を本文の出現順で、ラベルを候補順で別々に決めていた頃は、旧表記が手前にあると
    「2ヶ月節の中身を 3ヶ月目標として報告する」ラベル錯誤が起きた。正本節の期間行だけを
    壊したとき、ラベルが `3ヶ月目標` で出ることをもって「正本を見ている」ことを固定する。
    """
    text = _with_both_quarterly_headings(golden, "- 残り：5日\n- 目標：正本の本文。\n")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G01: 3ヶ月目標 に「- 期間：」の行がありません" in proc.stdout
    # 旧表記節は完全なので、そちらを見ていれば違反は 1 件も出ない。
    # 見るのは違反行 (`  - `) だけ。旧表記が併存する以上 D01 の NOTICE は出るのが正しく、
    # stdout 全体で判定すると通知経路と検査対象の話が混ざる。
    violation_lines = [l for l in proc.stdout.splitlines() if l.startswith("  - ")]
    assert not [l for l in violation_lines if "2ヶ月目標" in l], violation_lines


def test_empty_canonical_section_is_not_saved_by_a_complete_legacy_section(
    tmp_path: Path, golden: str
):
    """正本節が空なら、手前に完全な旧表記節があっても PASS させない (fail-open 回帰)。

    旧表記の受理は「過去分を再検証できる」ための後方互換であって、正本が空のまま
    出荷できる抜け道ではない。本文の出現順に任せると exit 0 になっていた。
    """
    text = _with_both_quarterly_headings(golden, "")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "3ヶ月目標" in proc.stdout


# --- チェックシート①②③ (`# チェックシート` から下) -----------------------------------------

# ネストしたサブ項目も項目なので先頭空白を許す (validator の CHECKBOX_RE と同形)。
CHECKBOX = re.compile(r"^\s*-\s*\[[ xX]\]")
CHECKLIST_TEMPLATE = PLUGIN_ROOT / "skills/run-ubm-journal/references/principle-checklist.md"
BUSINESS_PHASE = "# ① 事業フェーズチェックシート（UBM）"
LIFE_FUNDS = "# ② 人生資金チェックシート"
UBM_CHECK = "# ③ チェックシート（UBM）"
SHEETS = (BUSINESS_PHASE, LIFE_FUNDS, UBM_CHECK)
LEGACY_SHEETS = ("# フェーズ別 課題チェックシート", "# 原理原則 チェックシート")


def template_block() -> str:
    """principle-checklist.md の「テンプレート（未チェック状態）」のフェンスの中身。"""
    text = CHECKLIST_TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"^```markdown\n(.*?)^```\s*$", text, re.M | re.S)
    assert m, "principle-checklist.md に ```markdown のテンプレートが無い"
    return m.group(1)


def golden_block(golden: str) -> str:
    """golden の `# チェックシート` の直前の `---` から末尾まで。"""
    i = golden.index("---\n# チェックシート\n")
    return golden[i:]


def split_sheet(text: str, heading: str) -> tuple[str, str, str]:
    """text を「シートより前」「シートの本体 (見出し行を含む)」「シートより後」に割る。

    本体の終わりは次の H1 かフェンスの閉じ。シートの間の `---` は本体の末尾に残る。
    """
    start = text.index(f"\n{heading}\n") + 1
    m = re.compile(r"(?m)^(?:# |```)").search(text, start + len(heading))
    end = m.start() if m else len(text)
    return text[:start], text[start:end], text[end:]


def sub_sheet(golden: str, heading: str, edit) -> str:
    """golden の 1 シートだけを edit(本体) で置き換えた全文を返す。"""
    head, body, tail = split_sheet(golden, heading)
    new = edit(body)
    assert new != body, f"{heading} の変異が空振りした"
    return head + new + tail


def h3_headings(text: str, heading: str) -> list[str]:
    """1 シートの H3 見出しを出現順で返す。"""
    _, body, _ = split_sheet(text, heading)
    return [l.strip() for l in body.splitlines() if l.startswith("### ")]


def drop_checkboxes(body: str) -> str:
    return re.sub(r"(?m)^\s*-\s*\[[ xX]\].*\n", "", body)


def test_checklist_root_is_required(tmp_path: Path, golden: str):
    """`# チェックシート` から下がまるごと落ちたら、親見出しと 3 シートを S01 で 1 件ずつ挙げる。

    「毎回丸ごと出す」が利用者の要求なので、ブロック不在は骨格違反として扱う。
    """
    text = golden[: golden.index("---\n# チェックシート\n")]
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("S01:") == 4, proc.stdout
    for heading in ("# チェックシート",) + SHEETS:
        assert f"S01: 必須見出しが見つからないか順序が不正です: {heading}" in proc.stdout


@pytest.mark.parametrize("heading", SHEETS)
def test_each_sheet_is_required(tmp_path: Path, golden: str, heading: str):
    """3 シートのどれか 1 つだけ落としても S01 で止める。"""
    text = sub_sheet(golden, heading, lambda body: "")
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert f"S01: 必須見出しが見つからないか順序が不正です: {heading}" in proc.stdout


@pytest.mark.parametrize("legacy", LEGACY_SHEETS)
def test_legacy_sheet_left_behind_fails(tmp_path: Path, golden: str, legacy: str):
    """新しい①②③と一緒に差し替え前の旧ブロックが残っていたら S02 で止める。

    両方あると、次回の build がどちらを継承するのかを決められない。新しい形は
    揃っているので S01 は出ず、S02 だけで落ちることを固定する。
    """
    text = golden.rstrip("\n") + f"\n\n{legacy}\n\n## ◇ 右肩上がりになっていますか？\n- [x] 個人の口座残高\n"
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("S02:") == 1, proc.stdout
    assert f"差し替え前のチェックシート「{legacy}」が残っています" in proc.stdout
    assert "S01:" not in proc.stdout, proc.stdout


def test_legacy_only_journal_fails(tmp_path: Path, golden: str):
    """旧形式だけのジャーナル (2026-10-29 までの形) は S01 と S02 の両方で落ちる。"""
    head = golden[: golden.index("---\n# チェックシート\n")]
    text = head + "".join(
        f"{legacy}\n\n## ◇ 右肩上がりになっていますか？\n- [ ] 個人の口座残高\n\n" for legacy in LEGACY_SHEETS
    )
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert "S01:" in proc.stdout, proc.stdout
    assert proc.stdout.count("S02:") == 2, proc.stdout


def test_business_phase_missing_section_fails(tmp_path: Path, golden: str):
    """①のフェーズ・テストの見出しが欠けたら、欠けた分だけ P01 を出す。"""
    def edit(body: str) -> str:
        body = body.replace("### ★ 10 → 100 テスト", "### ★ その他のテスト")
        return body.replace("### 1 → 10 フェーズ", "### 次のフェーズ")

    proc = run(write(tmp_path, sub_sheet(golden, BUSINESS_PHASE, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("P01:") == 2, proc.stdout
    assert "P01: 事業フェーズチェックシートに「### ★ 10 → 100 テスト…」がありません" in proc.stdout


def test_business_phase_checkbox_is_required_per_section(tmp_path: Path, golden: str):
    """チェックボックスの有無は H3 ごとに見る。

    シート全体から 1 行でも見つかれば可にすると、0 → 1 フェーズだけ埋まっていて
    残りが見出しだけ、という状態を通す。空にした 5 節すべてが P02 で挙がることを固定する。
    """
    def edit(body: str) -> str:
        i = body.index("### ★ 0 → 1 テスト")
        return body[:i] + drop_checkboxes(body[i:])

    proc = run(write(tmp_path, sub_sheet(golden, BUSINESS_PHASE, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("P02:") == 5, proc.stdout
    assert proc.stdout.count("P01:") == 0, proc.stdout


def test_life_funds_missing_section_fails(tmp_path: Path, golden: str):
    edit = lambda body: body.replace("### 振り返りチェック\n", "")
    proc = run(write(tmp_path, sub_sheet(golden, LIFE_FUNDS, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("M01:") == 1, proc.stdout
    assert "M01: 人生資金チェックシートに「### 振り返りチェック…」がありません" in proc.stdout


def test_life_funds_checkbox_is_required_per_section(tmp_path: Path, golden: str):
    """②は冒頭の 2 行 (今の生活費・今の収入額) と H3 の 3 節を別々に見る。"""
    proc = run(write(tmp_path, sub_sheet(golden, LIFE_FUNDS, drop_checkboxes)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("M02:") == 4, proc.stdout
    assert "M02: 人生資金チェックシートの冒頭（今の生活費・今の収入額）にチェックボックス行がありません" in proc.stdout
    assert proc.stdout.count("M01:") == 0, proc.stdout
    assert proc.stdout.count("M03:") == 0, proc.stdout


def test_life_funds_table_is_required(tmp_path: Path, golden: str):
    """④の見直し項目の表を落としたら M03。見出しとチェック行が残っていても記入欄が消える。"""
    edit = lambda body: re.sub(r"(?m)^\|.*\n", "", body)
    proc = run(write(tmp_path, sub_sheet(golden, LIFE_FUNDS, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("M03:") == 1, proc.stdout
    assert proc.stdout.count("M02:") == 0, proc.stdout


def test_ubm_checklist_excerpt_fails_per_missing_section(tmp_path: Path, golden: str):
    """設問を抜粋した③を PASS にしない。

    「1 つでもあれば可」にすると、3 設問だけ書いたシートが通り、毎回丸ごと出すという
    要求が検査を素通りして空洞化する。欠落は 1 件 1 行で出す。
    """
    def edit(body: str) -> str:
        parts = re.split(r"(?m)^(?=### ◇)", body)
        return "".join(parts[:4])  # 見出しの部分と先頭 3 設問だけ残す

    proc = run(write(tmp_path, sub_sheet(golden, UBM_CHECK, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("K01:") == 8, proc.stdout
    assert "K01: チェックシート（UBM）に「### ◇ 支出は前回から下げられましたか…」の設問がありません" in proc.stdout


def test_ubm_checklist_checkbox_is_required_per_section(tmp_path: Path, golden: str):
    """空にした 9 設問すべてが K02 で挙がる (P02 と同じ形の fail-open を塞ぐ)。"""
    def edit(body: str) -> str:
        parts = re.split(r"(?m)^(?=### ◇)", body)
        return "".join(parts[:3] + [drop_checkboxes(p) for p in parts[3:]])

    proc = run(write(tmp_path, sub_sheet(golden, UBM_CHECK, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("K02:") == 9, proc.stdout
    assert proc.stdout.count("K01:") == 0, proc.stdout


def test_ubm_checklist_nested_checkbox_counts(tmp_path: Path, golden: str):
    """インデントされたサブ項目**だけ**の設問も K02 を満たす。

    golden をそのまま通すだけでは、この主張は固定できない。「歴史の共有」の設問は
    ネストした項目とトップレベルの項目を両方持つため、先頭空白を許さない正規表現へ
    退行させても K02 はトップレベル側で満たされてしまう。ネスト以外を取り除いた
    設問を作り、それが PASS することで初めて `^\\s*-` の `\\s*` を固定できる。
    """
    target = "決めた括りの人が増え、歴史の共有ができていますか"

    def edit(body: str) -> str:
        parts = re.split(r"(?m)^(?=### ◇)", body)
        out = []
        for part in parts:
            if target in part:
                part = re.sub(r"(?m)^-\s*\[[ xX]\].*\n", "", part)
                assert re.search(r"(?m)^\s+-\s*\[[ xX]\]", part), part
                assert not re.search(r"(?m)^-\s*\[[ xX]\]", part), part
            out.append(part)
        return "".join(out)

    proc = run(write(tmp_path, sub_sheet(golden, UBM_CHECK, edit)), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout


def test_checklist_sections_stay_in_sync_across_the_four_sources(golden: str):
    """見出しの正本が 4 箇所に分散しているので、ズレをテストで落とす。

    正本テンプレート (principle-checklist.md) / Few-shot (golden-sample.md) /
    人間向け骨格 (output-format.md) / 機械検査キー (validator の 3 つの定数) が
    同じ H3 を指していなければならない。1 箇所だけ直す変更は必ず起きるので、
    「実測で確認した」ではなく検査として固定する。
    """
    mod = _load_validator()
    template = template_block()
    fmt = (PLUGIN_ROOT / "skills/run-ubm-journal/references/output-format.md").read_text(encoding="utf-8")

    assert mod.BUSINESS_PHASE_HEADING == BUSINESS_PHASE[2:]
    assert mod.LIFE_FUNDS_HEADING == LIFE_FUNDS[2:]
    assert mod.UBM_CHECKLIST_HEADING == UBM_CHECK[2:]
    assert mod.LEGACY_CHECKLIST_HEADINGS == tuple(h[2:] for h in LEGACY_SHEETS)
    assert mod.LIFE_FUNDS_TABLE_SECTION in mod.LIFE_FUNDS_SECTIONS

    for heading, keys, count in (
        (BUSINESS_PHASE, mod.BUSINESS_PHASE_SECTIONS, 6),
        (LIFE_FUNDS, mod.LIFE_FUNDS_SECTIONS, 3),
        (UBM_CHECK, mod.UBM_CHECK_SECTIONS, 11),
    ):
        expected = h3_headings(template, heading)
        assert len(expected) == count, expected
        assert h3_headings(golden, heading) == expected
        assert h3_headings(fmt, heading) == expected
        assert len(keys) == count
        # 各キーは 1 つの見出しだけに一致すること。複数に当たると、別の見出しの存在で
        # P01/M01/K01 が満たされ、欠落を検出できなくなる。
        for key in keys:
            assert sum(key in h for h in expected) == 1, key


def test_checklist_template_and_golden_have_same_items(golden: str):
    """テンプレートと golden で、チェック状態を除いた全文が一致する。

    見出しだけ揃えても項目・注記・②の表が抜ければ意味がない。チェック状態
    (`[ ]` / `[x]`) の違いは正常なので、そこだけ空欄に戻してから比べる。
    """
    template = template_block().rstrip("\n")
    block = golden_block(golden).rstrip("\n")
    assert re.search(r"(?m)^\s*-\s*\[[xX]\]", block), "golden にチェック済みの項目が無い"
    assert re.sub(r"(?m)^(\s*-\s*\[)[xX](\])", r"\1 \2", block) == template
    assert len([l for l in template.splitlines() if CHECKBOX.match(l)]) == 115


def test_checklist_template_has_no_emoji():
    """出力に絵文字を使わない決まりに合わせ、出典の「振り返りチェック」の頭の電球の絵文字を外してある。

    ★ (U+2605) は出典どおり残すので、範囲は絵文字の面だけに絞る。
    """
    template = template_block()
    assert "\U0001F4A1" not in template
    assert not re.search("[\U0001F300-\U0001FAFF\uFE0F]", template)


# --- 引数・daily-habits.json の不正は exit 2 (ジャーナルの違反 exit 1 と取り違えない) ---

@pytest.mark.parametrize("flag, value", [
    ("--expected-date", "abc"),
    ("--expected-date", "2026-8-18"),
    ("--expected-date", "2026-02-30"),
    ("--expected-number", "-5"),
    ("--expected-number", "0"),
    ("--expected-number", "x"),
])
def test_invalid_expected_args_exit_2(tmp_path: Path, golden: str, flag: str, value: str):
    proc = subprocess.run(
        [sys.executable, str(VALIDATE), "--file", str(write(tmp_path, golden)), flag, value],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr
    assert "F04" not in proc.stdout and "F05" not in proc.stdout


@pytest.mark.parametrize("breakage", ["directory", "non_utf8"])
def test_unreadable_daily_habits_is_exit_2(tmp_path: Path, golden: str, breakage: str):
    import shutil

    sandbox = tmp_path / "skill"
    shutil.copytree(VALIDATE.parent.parent, sandbox)
    path = sandbox / "references" / "daily-habits.json"
    path.unlink()
    if breakage == "directory":
        path.mkdir()
    else:
        path.write_bytes(b"\xff\xfe{")
    proc = subprocess.run(
        [sys.executable, str(sandbox / "scripts" / VALIDATE.name), "--file", str(write(tmp_path, golden))],
        capture_output=True, text=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr


# --- 字下げしたコードフェンス ---

def test_y02_is_not_satisfied_by_an_indented_fence(tmp_path: Path, golden: str):
    """箇条書きの中で字下げしたフェンスも Obsidian は埋め込まない。行頭のフェンスと同じに扱う。"""
    mod = _load_validator()
    indented = "- メモ\n  ```\n  ![[人生の究極の目的]]\n  ```\n"
    assert not mod.TRANSCLUSION_RE.search(mod.visible_text(indented))
    line = "![[人生の究極の目的#🎯 究極の人生の目的]]"
    assert line in golden
    text = golden.replace(line, "- 究極目的\n  ```\n  " + line + "\n  ```", 1)
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1, proc.stdout
    assert "Y02" in proc.stdout, proc.stdout
