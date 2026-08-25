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


def test_missing_phase_block_fails(tmp_path: Path, golden: str):
    text = golden.replace("## ◇【10→100】", "## ◇【その他】")
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "P01" in proc.stdout


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
    body = golden[start:end]
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
    """旧表記 `### 3ヶ月目標` だけで書かれた既存ジャーナルを骨格違反にしない。

    正本は `2ヶ月目標` だが、過去分を再検証したときに S01 で落ちると
    「書き換えないと検証できない」記録が生まれる。後方互換の受理はこの改名の
    主目的なので、golden 全体を旧表記へ倒した状態を PASS として固定する。
    """
    text = golden.replace("### 2ヶ月目標", "### 3ヶ月目標")
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout
    assert "PASS" in proc.stdout


def test_legacy_quarterly_heading_violation_names_the_written_heading(
    tmp_path: Path, golden: str
):
    """旧表記で書かれた節の違反メッセージは、実際に書かれていた見出し名で出す。

    `GOAL_SECTIONS` の要素はタプル (正本, 旧表記) なので、素朴に f-string へ
    埋めると「('2ヶ月目標', '3ヶ月目標') に…」という内部表現が利用者に漏れる。
    validate() の 367-376 がここを解決している。その分岐を固定する。
    """
    text = golden.replace("### 2ヶ月目標", "### 3ヶ月目標").replace(
        "- 期間：2026-06-29〜2026-08-30\n", ""
    )
    proc = run(write(tmp_path, text))
    assert proc.returncode == 1
    assert "G01: 3ヶ月目標 に「- 期間：」の行がありません" in proc.stdout
    # タプルを素朴に f-string へ埋める退行はここで落とす。
    assert "('2ヶ月目標'" not in proc.stdout


# --- 原理原則チェックシート (`# 原理原則 チェックシート`) ---------------------------------

# ネストしたサブ項目も設問なので先頭空白を許す (validator の CHECKBOX_RE と同形)。
CHECKBOX = re.compile(r"^\s*-\s*\[[ xX]\]")


def split_principle(golden: str) -> tuple[str, list[str]]:
    """golden を「チェックシートより前」と「設問セクションの列」へ割る。

    先頭要素は `# 原理原則 チェックシート` 直後の空行なので、設問は `sections[1:]` にあたる。
    """
    head, marker, tail = golden.partition("\n# 原理原則 チェックシート\n")
    assert marker, "golden-sample.md に # 原理原則 チェックシート が無い"
    return head, re.split(r"(?m)^(?=## ◇)", tail)


def test_principle_checklist_block_is_required(tmp_path: Path, golden: str):
    """`# 原理原則 チェックシート` ブロックごと落ちたら S01 で落とす。

    「毎回丸ごと出す」が利用者の要求なので、ブロック不在は骨格違反として扱う。
    """
    head, _ = split_principle(golden)
    proc = run(write(tmp_path, head), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert "S01" in proc.stdout
    assert "# 原理原則 チェックシート" in proc.stdout


def test_principle_checklist_excerpt_fails_per_missing_section(tmp_path: Path, golden: str):
    """設問を抜粋したチェックシートを PASS にしない。

    「1 つでもあれば可」にすると、3 設問だけ書いたチェックシートが通り、
    毎回丸ごと出すという要求が検査を素通りして空洞化する。欠落は 1 件 1 行で出す。
    """
    head, sections = split_principle(golden)
    text = head + "\n# 原理原則 チェックシート\n" + "".join(sections[:4])  # 先頭3設問だけ残す
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("K01:") == 8, proc.stdout
    assert "K01: チェックシートに「## ◇支出は前回から下げられましたか…」の設問がありません" in proc.stdout


def test_principle_checklist_checkbox_is_required_per_section(tmp_path: Path, golden: str):
    """チェックボックスの有無は設問セクション単位で見る。

    ブロック全体から 1 行でも見つかれば可にすると、1 設問だけ埋まっていて残り 10 設問が
    見出しだけ、という状態を通す (P02 と同じ形の fail-open)。空にした 10 設問すべてが
    K02 で挙がることを固定する。
    """
    head, sections = split_principle(golden)
    stripped = [sections[0], sections[1]] + [
        re.sub(r"(?m)^\s*-\s*\[[ xX]\].*\n", "", s) for s in sections[2:]
    ]
    text = head + "\n# 原理原則 チェックシート\n" + "".join(stripped)
    proc = run(write(tmp_path, text), GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 1
    assert proc.stdout.count("K02:") == 10, proc.stdout
    assert proc.stdout.count("K01:") == 0, proc.stdout


def principle_headings(text: str) -> list[str]:
    """`# 原理原則 チェックシート` 配下の H2 設問見出しを出現順で返す。"""
    _, _, tail = text.partition("\n# 原理原則 チェックシート\n")
    return [l.strip() for l in tail.splitlines() if l.strip().startswith("## ◇")]


def test_principle_sections_stay_in_sync_across_the_four_sources(golden: str):
    """設問の正本が 4 箇所に分散しているので、ズレをテストで落とす。

    正本テンプレート (principle-checklist.md) / Few-shot (golden-sample.md) /
    人間向け骨格 (output-format.md) / 機械検査キー (PRINCIPLE_SECTIONS) の 4 つが
    同じ 11 設問を指していなければならない。1 箇所だけ直す変更は必ず起きるので、
    「実測で確認した」ではなく検査として固定する。
    """
    skill = PLUGIN_ROOT / "skills/run-ubm-journal"
    template = (skill / "references/principle-checklist.md").read_text(encoding="utf-8")
    fmt = (skill / "references/output-format.md").read_text(encoding="utf-8")
    source = (skill / "scripts/validate-journal-output.py").read_text(encoding="utf-8")

    headings = principle_headings(golden)
    assert len(headings) == 11, headings
    assert principle_headings(template) == headings
    assert principle_headings(fmt) == headings

    block = re.search(r"PRINCIPLE_SECTIONS = \[(.*?)\n\]", source, re.S)
    assert block, "PRINCIPLE_SECTIONS が見つからない"
    keys = re.findall(r'"([^"]+)"', block.group(1))
    assert len(keys) == len(headings)
    # 各キーは 1 つの設問だけに一致すること。複数に当たると K01 が別の設問の存在で
    # 満たされ、欠落を検出できなくなる。
    for key in keys:
        assert sum(key in h for h in headings) == 1, key


def test_principle_checklist_template_and_golden_have_same_questions(golden: str):
    """テンプレートと golden で設問本文（チェックボックス行）が一致する。

    見出しだけ揃えても設問が抜ければ意味がない。チェック状態 (`[ ]` / `[x]`) の
    違いは正常なので、そこだけ正規化してから比べる。
    """
    template = (
        PLUGIN_ROOT / "skills/run-ubm-journal/references/principle-checklist.md"
    ).read_text(encoding="utf-8")

    def questions(text: str) -> list[str]:
        _, _, tail = text.partition("\n# 原理原則 チェックシート\n")
        return [
            re.sub(r"\[[ xX]\]", "[ ]", l.rstrip())
            for l in tail.splitlines()
            if CHECKBOX.match(l)
        ]

    assert questions(golden) == questions(template)
    assert len(questions(golden)) == 56


def test_principle_checklist_has_no_horizontal_rule(golden: str):
    """`# 原理原則 チェックシート` 本文に水平線を置かない。

    build-journal-context の section_body は `---` をセクション終端として扱うため、
    区切り線を書くと翌日の継承がそこで打ち切られ、以降の設問が静かに消える。
    """
    _, _, tail = golden.partition("\n# 原理原則 チェックシート\n")
    assert not [l for l in tail.splitlines() if l.strip() == "---"], tail


def test_principle_checklist_nested_checkbox_counts(tmp_path: Path, golden: str):
    """インデントされたサブ項目**だけ**の設問も K02 を満たす。

    golden をそのまま通すだけでは、この主張は固定できない。「（1）」の設問は
    ネストした項目とトップレベルの項目を両方持つため、先頭空白を許さない正規表現へ
    退行させても K02 はトップレベル側で満たされてしまう。ネスト以外を取り除いた
    設問を作り、それが PASS することで初めて `^\\s*-` の `\\s*` を固定できる。
    """
    head, sections = split_principle(golden)
    target = "歴史の共有ができていますか？（1）"
    rebuilt = []
    for sec in sections:
        if target in sec:
            # トップレベルのチェックボックス行だけ落とし、ネストした項目を残す。
            sec = re.sub(r"(?m)^-\s*\[[ xX]\].*\n", "", sec)
            assert re.search(r"(?m)^\s+-\s*\[[ xX]\]", sec), sec
            assert not re.search(r"(?m)^-\s*\[[ xX]\]", sec), sec
        rebuilt.append(sec)
    proc = run(write(tmp_path, head + "\n# 原理原則 チェックシート\n" + "".join(rebuilt)),
               GOLDEN_NUMBER, GOLDEN_DATE)
    assert proc.returncode == 0, proc.stdout

