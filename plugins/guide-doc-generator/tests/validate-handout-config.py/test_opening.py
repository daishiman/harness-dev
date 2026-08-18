# -*- coding: utf-8 -*-
"""冒頭の置き方の検査 (W-HERO-LONG / W-OPENS-PROSE)。

判定基準の出所は config/handout-visual-policy.json#opening である。冒頭は
読み手が『自分に関係があるか』を決める場所であり、そこに段落が積まれると
判断する前に読むのをやめる。宣言は 1 行、中身はカードと図解、という順を固定する。
"""

import json
import unittest

from _harness import section, text_part
from test_visual_density import VisualDensityTestBase, diagram_part, table_part

VISUAL_POLICY_RELPATH = "config/handout-visual-policy.json"

LONG_PROSE = ("相談は2件あるが詰まっている場所は同じであり、どちらも毎日決まった作業に"
              "時間を取られ、その分だけ判断に回す時間が削られているという構図になっている。"
              "冒頭でこれだけの分量を読ませると、読み手は自分に関係があるかを判断する前に"
              "読むのをやめてしまう")


class OpeningTestBase(VisualDensityTestBase):

    def patch_opening(self, **attrs):
        path = self.root / VISUAL_POLICY_RELPATH
        policy = self.visual_policy()
        policy.setdefault("opening", {}).update(attrs)
        path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")


class TestHeroFields(OpeningTestBase):
    """文書冒頭の 3 要素は宣言であって説明ではない。"""

    def test_short_hero_emits_no_warning(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-HERO-LONG")

    def test_long_background_warns(self):
        cfg = self.visual_ok_config(background=LONG_PROSE)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-HERO-LONG", "/background")

    def test_long_purpose_warns(self):
        res, _ = self.validate(self.visual_ok_config(purpose=LONG_PROSE))
        self.assert_diag(res, "W-HERO-LONG", "/purpose")

    def test_long_goal_warns(self):
        res, _ = self.validate(self.visual_ok_config(goal=LONG_PROSE))
        self.assert_diag(res, "W-HERO-LONG", "/goal")

    def test_limits_come_from_canon(self):
        """上限を緩めれば警告は消える (script に埋まっていない)。"""
        self.patch_opening(hero_fields={"max_chars": {"background": 400}})
        res, _ = self.validate(self.visual_ok_config(background=LONG_PROSE))
        self.assert_no_diag(res, "W-HERO-LONG")

    def test_missing_canon_falls_back(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        res, _ = self.validate(self.visual_ok_config(background=LONG_PROSE))
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-HERO-LONG", "/background")


class TestHeroTotal(OpeningTestBase):
    """1 フィールドずつ短くても、短い行が積み上がれば冒頭は長くなる。"""

    # 1 件 60 字 (schema 上限は 80 字) を 8 件。個別の上限は 1 件も超えない
    PILED_UP = ["元データの列名と数式の引数構成をここに書き写しても読み手の判断には使われない%02d" % i
                for i in range(8)]

    def test_short_hero_emits_no_warning(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-HERO-HEAVY")

    def test_piled_up_short_lines_warn(self):
        """個別の上限 (W-HERO-LONG) をどれも超えていなくても総量で発火する。"""
        cfg = self.visual_ok_config(no_need_to_remember=self.PILED_UP)
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-HERO-LONG")
        self.assert_diag(res, "W-HERO-HEAVY", "/")

    def test_limit_comes_from_canon(self):
        """上限を緩めれば警告は消える (script に埋まっていない)。"""
        self.patch_opening(hero_total={"max_chars": 4000})
        res, _ = self.validate(self.visual_ok_config(no_need_to_remember=self.PILED_UP))
        self.assert_no_diag(res, "W-HERO-HEAVY")

    def test_counted_fields_come_from_canon(self):
        """数える対象も正本側が決める。対象から外せば同じ構成でも黙る。"""
        self.patch_opening(hero_total={"counted_fields": ["purpose", "background", "goal"]})
        res, _ = self.validate(self.visual_ok_config(no_need_to_remember=self.PILED_UP))
        self.assert_no_diag(res, "W-HERO-HEAVY")

    def test_missing_canon_falls_back(self):
        (self.root / VISUAL_POLICY_RELPATH).unlink()
        res, _ = self.validate(self.visual_ok_config(no_need_to_remember=self.PILED_UP))
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-HERO-HEAVY", "/")


class TestSectionOpening(OpeningTestBase):
    """節は形から始める。言いたいことは lead_line が 1 行で担う。"""

    def test_section_opening_with_visual_is_silent(self):
        res, _ = self.validate(self.visual_ok_config())
        self.assert_exit(res, 0)
        self.assert_no_diag(res, "W-OPENS-PROSE")

    def test_section_opening_with_text_warns(self):
        cfg = self.visual_ok_config()
        cfg["sections"][0]["parts"] = [
            text_part("intro-t1"), diagram_part("intro-d1")]
        res, _ = self.validate(cfg)
        self.assert_exit(res, 0)
        self.assert_diag(res, "W-OPENS-PROSE", "/sections/0/parts/0")

    def test_appendix_is_out_of_scope(self):
        """付録は読み手が必要なときだけ開く場所であり、冒頭の判断には関わらない。"""
        cfg = self.visual_ok_config()
        cfg["sections"].append(section(
            "notes", id="notes", role="appendix", ties_to=[],
            parts=[text_part("notes-t1"), table_part("notes-b1")]))
        res, _ = self.validate(cfg)
        self.assert_no_diag(res, "W-OPENS-PROSE")


if __name__ == "__main__":
    unittest.main()
