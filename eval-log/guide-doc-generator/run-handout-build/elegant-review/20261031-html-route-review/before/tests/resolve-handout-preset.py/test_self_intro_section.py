"""self-intro — 話し手の自己紹介を既定で持つプリセット (利用者指定 2026-09-04)。

section_kind 語彙と部品 id はここで再定義せず、C12 の handout-sections.json と
C11 の handout-parts.json に実在することを先に照合してから preset へ要求する。
"""

import json
import unittest

import _harness as H

SELF_INTRO_KIND = "self-intro"
# ライフ表の器 (時期 / そのとき何をしていたか の 2 列) と、外部 URL を持つ唯一の部品。
LIFE_TABLE_PART = "B05"
CONTACT_LINK_PART = "B18"
# self-intro を required=true で持つ用途。lecture と onboarding は話し手が誰かで
# 中身の重みが変わるため必須、他は任意枠。
REQUIRED_PURPOSES = ("lecture", "onboarding")


def _catalog(test):
    return json.loads(H.require_file(test, H.SECTIONS_FILE, "C12").read_text(encoding="utf-8"))


class SelfIntroVocabularyTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def test_kind_exists_in_sections_catalog(self):
        known = {k["slug"] for k in _catalog(self)["section_kinds"]}
        self.assertIn(SELF_INTRO_KIND, known, "section_kind 正本に self-intro が無い")

    def test_kind_declares_first_main_placement(self):
        """位置は role では縛れないため placement=first-main を持つ。"""
        kind = next(k for k in _catalog(self)["section_kinds"] if k["slug"] == SELF_INTRO_KIND)
        self.assertEqual("first-main", kind.get("placement"), kind)
        self.assertEqual("main", kind.get("required_role"), kind)

    def test_life_table_row_cap_is_data_driven(self):
        """年表の行数上限は script でなく catalog が持つ。"""
        kind = next(k for k in _catalog(self)["section_kinds"] if k["slug"] == SELF_INTRO_KIND)
        self.assertIsInstance(kind.get("max_items"), int, kind)
        self.assertGreater(kind["max_items"], 0, kind)

    def test_recommended_parts_exist_in_parts_catalog(self):
        """B05 / B18 が部品カタログに実在する (存在しない id を推奨しない)。"""
        parts = json.loads(H.require_file(self, H.PARTS_FILE, "C11").read_text(encoding="utf-8"))
        known = {p["id"] for p in parts["parts"]}
        for part in (LIFE_TABLE_PART, CONTACT_LINK_PART):
            with self.subTest(part=part):
                self.assertIn(part, known, "handout-parts.json に無い部品を推奨している")


class SelfIntroPresetTest(unittest.TestCase):
    def setUp(self):
        H.require_script(self)

    def _payload(self, purpose):
        proc = H.run(["--purpose", purpose])
        self.assertEqual(0, proc.returncode, H.describe(proc))
        return json.loads(H.out_text(proc))

    def test_required_purposes_open_with_self_intro(self):
        """必須の用途では section_order の先頭が self-intro である。"""
        for purpose in REQUIRED_PURPOSES:
            with self.subTest(purpose=purpose):
                order = self._payload(purpose)["section_order"]
                self.assertEqual(SELF_INTRO_KIND, order[0]["section_kind"], order[0])
                self.assertTrue(order[0]["required"], order[0])

    def test_self_intro_recommends_life_table_and_contact_link(self):
        """どの用途でも器は B05 (ライフ表) と B18 (連絡先リンク) を推奨する。"""
        for purpose, preset in H.presets(self).items():
            sections = [s for s in preset["section_order"]
                        if s.get("section_kind") == SELF_INTRO_KIND]
            for section in sections:
                with self.subTest(purpose=purpose, section=section["id"]):
                    self.assertIn(LIFE_TABLE_PART, section["recommended_parts"], section)
                    self.assertIn(CONTACT_LINK_PART, section["recommended_parts"], section)

    def test_self_intro_appears_at_most_once_per_preset(self):
        """自己紹介は資料に 1 回。2 箇所に出ると読み手はどちらが本体か決められない。"""
        for purpose, preset in H.presets(self).items():
            count = sum(1 for s in preset["section_order"]
                        if s.get("section_kind") == SELF_INTRO_KIND)
            with self.subTest(purpose=purpose):
                self.assertLessEqual(count, 1, preset["section_order"])

    def test_presentation_order_variants_keep_self_intro_first(self):
        """提示順を切り替えても自己紹介は先頭に残る (順列制約と両立させる)。"""
        for purpose, preset in H.presets(self).items():
            has_self_intro = any(s.get("section_kind") == SELF_INTRO_KIND
                                 for s in preset["section_order"])
            for name, order in (preset.get("presentation_order_variants") or {}).items():
                with self.subTest(purpose=purpose, variant=name):
                    if has_self_intro:
                        self.assertEqual("self-intro", order[0], order)
                    else:
                        self.assertNotIn("self-intro", order, order)


if __name__ == "__main__":
    unittest.main()
