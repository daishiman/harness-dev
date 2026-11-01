# -*- coding: utf-8 -*-
"""NAR-03 (セクション冒頭のゴール) と NAR-04 (常時表示)。

AC-C22-04 / AC-C22-05 / AC-C22-06 / AC-C22-07。
"""

from __future__ import annotations

import unittest

from _support import NarrativeGateTestCase, base_config, build_html


class TestNar03Presence(NarrativeGateTestCase):
    def test_pass_when_all_sections_have_goal_at_top(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-03"]["status"])

    def test_checked_count_equals_section_count(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("7", self.summary(res)["NAR-03"]["checked"])

    def test_missing_section_goal_element(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_section_goal={"s3"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_duplicated_section_goal_element(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_duplicated={"s3"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_two_sections_missing_counts_two(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_section_goal={"s3", "s5"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=2)

    def test_stderr_carries_section_id(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_section_goal={"s3"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertTrue(
            any("s3" in "\t".join(r) for r in self.stderr_rows(res, "NAR-03")),
            "違反行に section_id が出ること\nstderr=%r" % res.stderr,
        )


class TestNar03Position(NarrativeGateTestCase):
    def test_ac04_goal_at_section_tail(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_at_end={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_ac04_reason_mentions_not_at_top(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_at_end={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        rows = self.stderr_rows(res, "NAR-03")
        self.assertTrue(rows, "NAR-03 の違反行が無い")
        self.assertTrue(
            any("s2" in "\t".join(r) for r in rows), "section_id つきで出ること"
        )

    def test_goal_after_lead_line_is_violation(self):
        # lead_line より前であることが冒頭の定義
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_at_end={"s4"}, include_lead_line=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_goal_before_concrete_part_passes_without_lead_line(self):
        # lead-line の存在は本ゲートでは要求しない (C18 LANG-04 の責務)
        html, cfg = self.write_pair(include_lead_line=False)
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)

    def test_goal_after_concrete_part_is_violation_without_lead_line(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, include_lead_line=False, section_goal_at_end={"s5"})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_goal_after_section_label_is_allowed(self):
        # section-label / 見出しより後ろは許される
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)


class TestNar03TextMatch(NarrativeGateTestCase):
    def test_altered_section_goal_text(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg))
        cfg2 = base_config()
        cfg2["sections"][1]["goal"] = "別のゴール文言。"
        res = self.run_gate(html, self.write_config(cfg2))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_whitespace_only_section_goal_in_html(self):
        cfg = base_config()
        cfg["sections"][2]["goal"] = "   "
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03")

    def test_formatting_difference_does_not_fail(self):
        # failure_modes: 改行やインデント混入は正規化して比較する
        cfg = base_config()
        html = build_html(cfg).replace(
            '<p class="goal-chip" data-hb-field="section_goal">',
            '<p class="goal-chip" data-hb-field="section_goal">\n      ',
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


class TestNar03ConfigSideEmptyGoal(NarrativeGateTestCase):
    """AC-C22-05: config 側の goal 空文字も本ゲートが独立に FAIL にする。"""

    def test_empty_string_goal_in_config(self):
        cfg = base_config()
        cfg["sections"][3]["goal"] = ""
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-03", count=1)

    def test_missing_goal_key_in_config(self):
        cfg = base_config()
        cfg["sections"][3].pop("goal")
        html = self.write_html(build_html(base_config()))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(1, res.returncode, "goal 欠落は exit 1 (検査は成立する)")
        self.assertGreaterEqual(self.violations(res, "NAR-03"), 1)

    def test_empty_goal_is_not_silently_passed(self):
        cfg = base_config()
        cfg["sections"][3]["goal"] = ""
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertNotEqual(0, res.returncode, "C12 の責務だからと PASS へ畳まない")


class TestNar04AlwaysVisible(NarrativeGateTestCase):
    def test_pass_on_visible_goal_chip(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-04"]["status"])

    def test_ac06_details_wrapper(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_in_details={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_hidden_attribute(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_hidden_attr={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_aria_hidden_true(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_aria_hidden={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_inline_style_display_none(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_goal_inline_none={"s2"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_inline_style_visibility_hidden(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            '<p class="goal-chip" data-hb-field="section_goal">%s</p>' % cfg["sections"][1]["goal"],
            '<p class="goal-chip" data-hb-field="section_goal" style="visibility:hidden">%s</p>'
            % cfg["sections"][1]["goal"],
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_ancestor_hidden_attribute(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            '<p class="goal-chip" data-hb-field="section_goal">%s</p>' % cfg["sections"][1]["goal"],
            '<div hidden><p class="goal-chip" data-hb-field="section_goal">%s</p></div>'
            % cfg["sections"][1]["goal"],
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_ancestor_aria_hidden(self):
        cfg = base_config()
        html = build_html(cfg).replace(
            '<p class="goal-chip" data-hb-field="section_goal">%s</p>' % cfg["sections"][1]["goal"],
            '<div aria-hidden="true"><p class="goal-chip" data-hb-field="section_goal">%s</p></div>'
            % cfg["sections"][1]["goal"],
        )
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04", count=1)

    def test_stylesheet_class_display_none(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, css_hidden_goal_chip=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04")

    def test_stylesheet_attribute_selector_display_none(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, extra_css='[data-hb-field="section_goal"]{display:none}')
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04")

    def test_stylesheet_visibility_hidden(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, extra_css=".goal-chip{visibility:hidden}"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-04")

    def test_ac07_media_print_display_none_is_not_a_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, css_print_hidden_goal_chip=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_ac07_media_screen_block_is_also_excluded(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, extra_css="@media screen{.goal-chip{display:none}}"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_unrelated_class_display_none_is_not_a_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, extra_css=".section-label-print{display:none}"))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)


if __name__ == "__main__":
    unittest.main()
