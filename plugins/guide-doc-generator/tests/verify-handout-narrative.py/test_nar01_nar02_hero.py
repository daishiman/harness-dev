# -*- coding: utf-8 -*-
"""NAR-01 (冒頭 3 要素の描画) と NAR-02 (文言一致)。AC-C22-02 / AC-C22-03。"""

from __future__ import annotations

import unittest

from _support import (
    NarrativeGateTestCase, base_config, build_html, canonical_hero_field_order)

HERO_FIELDS = ("purpose", "background", "goal")


class TestNar01Presence(NarrativeGateTestCase):
    def test_pass_when_all_three_present_in_hero(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-01"]["status"])

    def test_ac02_goal_removed(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=1)

    def test_purpose_removed(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"purpose"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=1)

    def test_background_removed(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"background"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=1)

    def test_all_three_removed_counts_three(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields=set(HERO_FIELDS)))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=3)

    def test_duplicated_goal_is_violation(self):
        # 「ちょうど 1 個」なので 2 個以上も違反
        cfg = base_config()
        html = self.write_html(build_html(cfg, duplicate_hero_field={"goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=1)

    def test_duplicated_purpose_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, duplicate_hero_field={"purpose"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01", count=1)

    def test_empty_goal_text_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": ""}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_whitespace_only_goal_text_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": "  　 "}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_stderr_row_has_five_tab_fields(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        for row in self.stderr_rows(res, "NAR-01"):
            self.assertEqual(
                5, len(row), "FAIL<TAB>id<TAB>位置<TAB>値<TAB>理由 の 5 列\nrow=%r" % (row,)
            )

    def test_stderr_names_the_missing_field(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_hero_fields={"goal"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertTrue(
            any("goal" in "\t".join(r) for r in self.stderr_rows(res, "NAR-01")),
            "欠落した data-hb-field 値が stderr に出ること\nstderr=%r" % res.stderr,
        )


class TestNar01Position(NarrativeGateTestCase):
    def test_background_inside_first_section_is_violation(self):
        # violation_example そのもの: background が最初の section 内にある
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, omit_hero_fields={"background"}, hero_field_after_first_section=["background"])
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_goal_after_first_section_start_is_violation(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, omit_hero_fields={"goal"}, hero_field_after_first_section=["goal"])
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_reversed_order_is_violation(self):
        """正本の並びを逆にしたら落ちる。

        旧版はこの位置に「purpose → background → goal でなければ落ちる」を
        literal で書いていた。順序の正本は config 側 (opening.hero_card_fields
        .order) にあり、利用者要求 R3 でゴール先頭へ変わったので、ここでは
        「正本どおりか」だけを見る (script も fixture もテストも順序を持たない)。
        """
        cfg = base_config()
        reversed_order = list(reversed(canonical_hero_field_order()))
        html = self.write_html(build_html(cfg, hero_field_order=reversed_order))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_swapping_the_first_two_is_violation(self):
        cfg = base_config()
        order = canonical_hero_field_order()
        order[0], order[1] = order[1], order[0]
        html = self.write_html(build_html(cfg, hero_field_order=order))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-01")

    def test_canonical_order_passes(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, hero_field_order=canonical_hero_field_order()))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_goal_comes_first_in_the_canon(self):
        """利用者要求 R3 の受け皿。正本そのものを固定する。

        並び順の検査が正本から引けていても、正本が旧順序のままなら要求は
        満たされない。「ゴールが最初」はここでしか押さえられない。
        """
        self.assertEqual("goal", canonical_hero_field_order()[0])


class TestNar02TextMatch(NarrativeGateTestCase):
    def test_ac03_goal_text_altered(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": "業務で使えるようになる。"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)

    def test_ac03_stderr_shows_both_values(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": "業務で使えるようになる。"}))
        res = self.run_gate(html, self.write_config(cfg))
        blob = res.stderr
        self.assertIn("業務で使えるようになる。", blob, "HTML 側の値が stderr に出ること")
        self.assertIn(cfg["goal"], blob, "config 側の値が stderr に出ること")

    def test_purpose_text_altered(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"purpose": "目的です。"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)

    def test_background_text_altered(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"background": "背景です。"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)

    def test_all_three_altered_counts_three(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, hero_text_override={"purpose": "あ", "background": "い", "goal": "う"})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=3)

    def test_suffix_addition_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": cfg["goal"] + " (目標)"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)

    def test_punctuation_addition_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": cfg["goal"] + "。"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)


class TestNar02Normalization(NarrativeGateTestCase):
    """NFKC + 連続空白圧縮 + トリムだけを吸収し、それ以上は変形しない。"""

    def test_leading_and_trailing_whitespace_absorbed(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, hero_text_override={"goal": "\n    %s\n  " % cfg["goal"]}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_ideographic_space_run_absorbed(self):
        cfg = base_config()
        spaced = cfg["goal"].replace("、", "、　 ")
        expected = base_config()
        expected["goal"] = cfg["goal"].replace("、", "、 ")
        html = self.write_html(build_html(cfg, hero_text_override={"goal": spaced}))
        res = self.run_gate(html, self.write_config(expected))
        self.assert_gate_pass(res)

    def test_newline_and_tab_run_absorbed(self):
        cfg = base_config()
        folded = cfg["purpose"].replace("は", "は\n\t")
        expected = base_config()
        expected["purpose"] = cfg["purpose"].replace("は", "は ")
        html = self.write_html(build_html(cfg, hero_text_override={"purpose": folded}))
        res = self.run_gate(html, self.write_config(expected))
        self.assert_gate_pass(res)

    def test_nfkc_halfwidth_kana_absorbed(self):
        cfg = base_config()
        cfg["background"] = "ｸﾞﾙｰﾌﾟ全体へ展開する。"
        expected = base_config()
        expected["background"] = "グループ全体へ展開する。"
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(expected))
        self.assert_gate_pass(res)

    def test_punctuation_is_not_stripped_by_normalization(self):
        # 「これ以上の変形 (句読点除去など) は行わない」の固定
        cfg = base_config()
        stripped = cfg["goal"].replace("、", "").replace("。", "")
        html = self.write_html(build_html(cfg, hero_text_override={"goal": stripped}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-02", count=1)


class TestNoAnchorsAtAll(NarrativeGateTestCase):
    """failure_modes: 検査アンカーが 1 個も無い場合は exit 1 (PASS へ畳まない)。"""

    def test_exit_is_one_not_zero(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, strip_all_hb_fields=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(1, res.returncode, "アンカー不在は exit 1\nstdout=%s" % res.stdout)

    def test_stderr_lists_required_field_values(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, strip_all_hb_fields=True))
        res = self.run_gate(html, self.write_config(cfg))
        for name in ("purpose", "background", "goal", "section_goal"):
            self.assertIn(name, res.stderr, "必要な data-hb-field 値 %s を列挙すること" % name)


if __name__ == "__main__":
    unittest.main()
