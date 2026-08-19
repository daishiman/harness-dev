"""R22 C64 — 粒度のヒアリング (run-handout-build の R1-elicit)。

契約の出所は skill-brief-C01.json
responsibilities[R1-elicit].hearing_required_items_r22:
- items は detail_level / evidence_depth の 2 件
- required: false (無回答で停止しない)
- 既定値の出所は C23 granularity_defaults[doc_type]
- 無回答時は既定値を採用し provenance.<field>_source='preset-default' を立てて進む
- 2 フィールドを別々に聞かず 1 問へまとめる

R21 の必須 5 項目 (AC-C01-11) とは別ブロックに置く。同じブロックへ入れると
required: true が課され、『特にこだわりが無い』利用者を止めてしまう。
"""

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import contract_lib  # noqa: E402

SKILL_DIR = contract_lib.build_target_dir()
SKILL_MD = SKILL_DIR / "SKILL.md"

R22_BLOCK_KEY = "hearing_required_items_r22"
R22_FIELDS = ("detail_level", "evidence_depth")

C01_BRIEF = (
    contract_lib.repo_root()
    / "plugin-plans"
    / "guide-doc-generator"
    / "briefs"
    / "skill-brief-C01.json"
)


def brief_items(tc):
    """ブリーフ側の項目定義 (期待値の正本)。"""
    if not C01_BRIEF.is_file():
        tc.fail("ヒアリング項目の正本が読めない: {}".format(C01_BRIEF))
    data = json.loads(C01_BRIEF.read_text(encoding="utf-8"))
    for resp in data.get("responsibilities", []):
        block = resp.get(R22_BLOCK_KEY)
        if isinstance(block, dict):
            return {i.get("field"): i for i in block.get("items", []) if isinstance(i, dict)}
    tc.fail("skill-brief-C01.json に {} が無い".format(R22_BLOCK_KEY))


class R22HearingTestCase(unittest.TestCase):
    """SKILL.md の frontmatter / 本文を読む足場 (実装が無い間は failure)。"""

    def frontmatter_and_body(self):
        if not SKILL_MD.is_file():
            self.fail("C64 未達: SKILL.md が未実装 ({})".format(SKILL_MD))
        fm, body = contract_lib.split_frontmatter(SKILL_MD.read_text(encoding="utf-8"))
        if fm is None:
            self.fail("YAML frontmatter が無い: {}".format(SKILL_MD))
        return fm, body

    def r22_items(self):
        fm, _ = self.frontmatter_and_body()
        block = fm.get(R22_BLOCK_KEY)
        if isinstance(block, dict):
            items = block.get("items")
        else:
            items = block
        if not isinstance(items, list) or not items:
            self.fail(
                "frontmatter に {} の items が無い (R22 C64)".format(R22_BLOCK_KEY)
            )
        return {i.get("field"): i for i in items if isinstance(i, dict)}


class HearingItemsDeclaredTest(R22HearingTestCase):
    """C64: 両フィールドを提示すること。"""

    def test_both_fields_are_declared(self):
        self.assertEqual(set(R22_FIELDS), set(self.r22_items()))

    def test_each_item_has_a_japanese_question(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                item = items.get(field)
                self.assertIsNotNone(item, "{} が宣言されていない".format(field))
                self.assertTrue(
                    str(item.get("question_ja") or "").strip(),
                    "{} の question_ja が空".format(field),
                )

    def test_questions_expose_the_full_value_range(self):
        """3 択であることが質問文から分かること (選ばせる相手は利用者)。"""
        expected = brief_items(self)
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                question = str(items.get(field, {}).get("question_ja") or "")
                self.assertEqual(
                    str(expected[field].get("question_ja") or ""),
                    question,
                    "質問文がブリーフの定義と一致しない",
                )

    def test_default_source_points_at_c23(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                source = str(items.get(field, {}).get("default_source") or "")
                self.assertIn("granularity_defaults", source)
                self.assertIn(field, source)

    def test_checked_by_points_at_the_downstream_gates(self):
        items = self.r22_items()
        self.assertIn("C12", str(items.get("detail_level", {}).get("checked_by") or ""))
        self.assertIn("NAR-09", str(items.get("detail_level", {}).get("checked_by") or ""))
        self.assertIn("NAR-10", str(items.get("evidence_depth", {}).get("checked_by") or ""))


class NoAnswerDoesNotStopTest(R22HearingTestCase):
    """C64: 無回答時は既定を採用して停止しない。"""

    def test_required_is_false(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                self.assertIs(
                    False,
                    items.get(field, {}).get("required"),
                    "{} を必須回答にしてはならない (既定が常に存在する)".format(field),
                )

    def test_on_no_answer_adopts_the_preset_default(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                text = str(items.get(field, {}).get("on_no_answer") or "")
                self.assertTrue(text.strip(), "{} の on_no_answer が空".format(field))
                self.assertIn("preset-default", text)
                self.assertIn("{}_source".format(field), text)

    def test_no_answer_does_not_reask_or_block(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                text = str(items.get(field, {}).get("on_no_answer") or "")
                self.assertIn("既定", text, "既定値を採用する旨が無い")
                for blocking in ("中断", "エラー", "再質問する", "回答を待つ"):
                    self.assertNotIn(
                        blocking, text, "無回答で止まる挙動が宣言されている: %s" % blocking
                    )

    def test_body_declares_the_non_blocking_behaviour(self):
        _, body = self.frontmatter_and_body()
        self.assertIn(
            R22_BLOCK_KEY,
            body,
            "本文が R22 のヒアリング項目に言及していない",
        )
        self.assertIn(
            "granularity_defaults",
            body,
            "既定値の出所 (C23 granularity_defaults) が本文に無い",
        )


class SingleQuestionTest(R22HearingTestCase):
    """C64: 2 フィールドを別々に聞かず 1 問へまとめる。"""

    def test_items_declare_a_shared_elicitation_form(self):
        fm, _ = self.frontmatter_and_body()
        block = fm.get(R22_BLOCK_KEY)
        self.assertIsInstance(
            block, dict, "elicitation_form を持てる形 (mapping) で宣言すること"
        )
        form = str(block.get("elicitation_form") or "")
        self.assertTrue(form.strip(), "elicitation_form が無い")
        self.assertIn("1 問", form, "2 軸を 1 問へまとめる旨が宣言されていない")


class SeparateFromRequiredItemsTest(R22HearingTestCase):
    """C64: R21 の必須 5 項目の集合を汚さない (AC-C01-11 と両立させる)。"""

    def test_r21_block_keeps_exactly_the_five_required_fields(self):
        fm, _ = self.frontmatter_and_body()
        block = fm.get("hearing_required_items_r21")
        items = block.get("items") if isinstance(block, dict) else block
        fields = {i.get("field") for i in (items or []) if isinstance(i, dict)}
        self.assertEqual(set(contract_lib.REQUIRED_HEARING_FIELDS), fields)

    def test_granularity_fields_are_not_in_the_r21_block(self):
        fm, _ = self.frontmatter_and_body()
        block = fm.get("hearing_required_items_r21")
        items = block.get("items") if isinstance(block, dict) else block
        fields = {i.get("field") for i in (items or []) if isinstance(i, dict)}
        for field in R22_FIELDS:
            with self.subTest(field=field):
                self.assertNotIn(field, fields)


class DefaultsAreResolvedAtRuntimeTest(R22HearingTestCase):
    """C64: 既定値は doc_type 確定後に C23 から引く (skill 側へ表を持たない)。"""

    def test_item_default_source_is_a_lookup_not_a_value(self):
        items = self.r22_items()
        for field in R22_FIELDS:
            with self.subTest(field=field):
                source = str(items.get(field, {}).get("default_source") or "")
                self.assertIn("[doc_type]", source, "doc_type を鍵とした参照になっていない")

    def test_script_refs_include_the_preset_resolver(self):
        fm, _ = self.frontmatter_and_body()
        refs = [str(x) for x in (fm.get("script_refs") or [])]
        self.assertTrue(
            any("resolve-handout-preset.py" in ref for ref in refs),
            "既定値の解決先 (C23) が script_refs に無い",
        )


if __name__ == "__main__":
    unittest.main()
