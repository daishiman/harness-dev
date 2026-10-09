"""run-ubm-challenge の「名前で引く依存」を固定する契約テスト。

SKILL.md・agents/challenge-advisor.md・references/question-map.md・agents/phase3-coordinator.md は、
互いを見出し名・項目ラベル・入力キー・ナレッジ ID で引いている。どれかの名前が変わると、読む側は
黙って空振りする (エラーにならない) ので、引かれる名前が実在することをここで縛る:
  - question-map の見出し5つと、欄ごとの項目ラベル4つ
  - question-map に出てくる北原レンズ ID が knowledge/*.json の entries[].id に実在する
  - question-map の「返し方」が指す phase3-coordinator.md の2節が実在する
  - 助言役 (advisor) の入力キー7つ (この順) が助言役の「入力」節にあり、SKILL.md の C1-C5 節にも出てくる
  - challenge-format.md に「各欄の合格条件」見出しがある (SKILL.md の C1-C5 と助言役が引く)
  - 保留の正本は question-map の「返し方」だけにあり、「戻りゲート」には置かない
読むだけで、どのファイルにも書かない。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = PLUGIN_ROOT / "skills/run-ubm-challenge"
SKILL_MD = SKILL_DIR / "SKILL.md"
QUESTION_MAP = SKILL_DIR / "references/question-map.md"
CHALLENGE_FORMAT = SKILL_DIR / "references/challenge-format.md"
ADVISOR = PLUGIN_ROOT / "agents/challenge-advisor.md"
PHASE3 = PLUGIN_ROOT / "agents/phase3-coordinator.md"
KNOWLEDGE_DIR = PLUGIN_ROOT / "knowledge"

# question-map の見出し。SKILL.md・助言役が名前で引くので変えない。
QUESTION_MAP_HEADINGS = (
    "## 原則",
    "## 返し方（phase3 との差分）",
    "## 欄ごとの問い",
    "## 戻りゲート",
    "## ナレッジ未収録",
)
# 欄ごとの項目ラベル。4-2〜4-5 は表で持つので対象外。
FIELD_LABELS = ("**問い**", "**確かめる**", "**切り口**", "**レンズ**")
FIELD_SECTIONS = ("1", "2", "3", "4-1", "5", "6")
# question-map の「返し方」が指す phase3-coordinator.md の節。
PHASE3_HEADINGS = ("ナレッジ活用原則", "品質基準（回答パターン別対応ルール）")
# 助言役の入力キー (この6つ・この順)。
ADVISOR_INPUT_KEYS = ("field", "answers", "confirmed", "depth", "lens_limit", "plugin_root", "knowledge_candidates")
LENS_ID_RE = re.compile(r"(?:AG|PR|MS|CP)-\d{3}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def section(text: str, heading_re: str) -> str:
    """heading_re に当たる見出し行から、同じか上の階層の次の見出しの手前までを返す。"""
    m = re.search(rf"^(#+) {heading_re}.*$", text, re.M)
    assert m, f"見出しがありません: {heading_re}"
    level = len(m.group(1))
    end = re.compile(rf"^#{{1,{level}}} ", re.M).search(text, m.end())
    return text[m.start():end.start() if end else len(text)]


def word_re(word: str) -> re.Pattern[str]:
    """英数の単語として1語で当たる正規表現。日本語の隣でも当たるよう \\b を使わない。"""
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(word)}(?![A-Za-z0-9_])")


def knowledge_ids() -> set[str]:
    ids: set[str] = set()
    for path in sorted(KNOWLEDGE_DIR.glob("*.json")):
        data = json.loads(read(path))
        if isinstance(data, dict) and isinstance(data.get("entries"), list):
            ids |= {e["id"] for e in data["entries"] if isinstance(e, dict) and "id" in e}
    return ids


# ---- question-map の見出しと項目ラベル -------------------------------------------------------


@pytest.mark.parametrize("heading", QUESTION_MAP_HEADINGS)
def test_question_map_has_heading(heading):
    lines = [line.rstrip() for line in read(QUESTION_MAP).splitlines()]
    assert heading in lines, f"question-map.md に見出し {heading!r} がありません"


@pytest.mark.parametrize("key", FIELD_SECTIONS)
def test_question_map_field_section_has_labels(key):
    body = section(read(QUESTION_MAP), rf"{re.escape(key)}\.")
    missing = [label for label in FIELD_LABELS if label not in body]
    assert not missing, f"question-map.md の欄 {key} に {missing} がありません"


def test_question_map_hold_rule_lives_only_in_return_style():
    """保留の正本は「返し方」の1か所。戻りゲート表に置くと2か所で食い違う。"""
    text = read(QUESTION_MAP)
    assert "保留" in section(text, "返し方"), "question-map.md の「返し方」に保留がありません"
    assert "保留" not in section(text, "戻りゲート"), "question-map.md の「戻りゲート」に保留が残っています"


# ---- challenge-format.md の見出し ------------------------------------------------------------


def test_challenge_format_has_field_pass_criteria_heading():
    lines = [line.rstrip() for line in read(CHALLENGE_FORMAT).splitlines()]
    assert "## 各欄の合格条件" in lines, "challenge-format.md に見出し '## 各欄の合格条件' がありません"


# ---- 北原レンズ ID ---------------------------------------------------------------------------


def test_question_map_lens_ids_exist_in_knowledge():
    used = set(LENS_ID_RE.findall(read(QUESTION_MAP)))
    assert used, "question-map.md に北原レンズ ID が1件もありません"
    unknown = sorted(used - knowledge_ids())
    assert not unknown, f"knowledge/*.json に無い ID: {unknown}"


# ---- phase3-coordinator.md の参照先 ----------------------------------------------------------


@pytest.mark.parametrize("heading", PHASE3_HEADINGS)
def test_phase3_coordinator_has_heading(heading):
    headings = [line for line in read(PHASE3).splitlines() if line.startswith("#")]
    assert any(heading in line for line in headings), f"phase3-coordinator.md に見出し {heading!r} がありません"


# ---- 助言役の入力キー ----------------------------------------------------------------------


def test_advisor_input_section_lists_keys_in_order():
    body = section(read(ADVISOR), "入力")
    keys = re.findall(r"^- `([a-z_]+)`", body, re.M)
    assert keys == list(ADVISOR_INPUT_KEYS)


def test_advisor_input_section_drops_singular_answer():
    body = section(read(ADVISOR), "入力")
    assert not word_re("answer").search(body), "advisor の入力節に旧キー answer が残っています"


@pytest.mark.parametrize("key", ADVISOR_INPUT_KEYS)
def test_skill_dialogue_section_passes_advisor_key(key):
    body = section(read(SKILL_MD), "C1-C5")
    assert word_re(key).search(body), f"SKILL.md の C1-C5 節に advisor の入力キー {key} がありません"
