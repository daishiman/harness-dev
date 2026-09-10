# -*- coding: utf-8 -*-
"""NAR-05 (nav のゴール参照) と NAR-06 (全体→セクションの連鎖表)。

AC-C22-08 / AC-C22-09 / AC-C22-10 と failure_modes (nav 不在)。
"""

from __future__ import annotations

import json
import unittest

from _support import NarrativeGateTestCase, base_config, build_html


class TestNar05NavGoalReference(NarrativeGateTestCase):
    def test_pass_when_every_anchor_has_matching_goal(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-05"]["status"])

    def test_checked_count_equals_anchor_count(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("7", self.summary(res)["NAR-05"]["checked"])

    def test_ac08_anchor_without_any_goal_attribute(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, nav_omit_attrs={"s1"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05", count=1)

    def test_two_anchors_without_goal_attribute_counts_two(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, nav_omit_attrs={"s1", "s4"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05", count=2)

    def test_ac09_nav_goal_and_title_disagree(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, nav_mismatch={"s1": {"title": "導入セクション"}})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05", count=1)

    def test_ac09_partial_match_is_not_pass(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, nav_mismatch={"s2": {"data-hb-nav-goal": "違うゴール。"}})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assertNotEqual(0, res.returncode, "片方一致では PASS にしない")
        self.assertGreaterEqual(self.violations(res, "NAR-05"), 1)

    def test_both_attributes_wrong(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, nav_mismatch={"s2": {"data-hb-nav-goal": "違う。", "title": "違う。"}})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05", count=1)

    def test_empty_nav_goal_value(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, nav_mismatch={"s3": {"data-hb-nav-goal": "", "title": ""}})
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05", count=1)

    def test_title_only_still_requires_match(self):
        # data-hb-nav-goal / title いずれかで可 (open_question は P03 未確定)
        cfg = base_config()
        html = self.write_html(build_html(cfg, nav_only_title=set()))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_href_pointing_to_unknown_section(self):
        cfg = base_config()
        html = build_html(cfg).replace('href="#s6"', 'href="#s99"', 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-05")

    def test_whitespace_difference_in_nav_goal_is_absorbed(self):
        cfg = base_config()
        goal = cfg["sections"][0]["goal"]
        html = build_html(cfg).replace(
            'data-hb-nav-goal="%s"' % goal, 'data-hb-nav-goal="  %s  "' % goal, 1
        ).replace('title="%s"' % goal, 'title="  %s  "' % goal, 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_stderr_row_names_the_section(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, nav_omit_attrs={"s4"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertTrue(
            any("s4" in "\t".join(r) for r in self.stderr_rows(res, "NAR-05")),
            "stderr=%r" % res.stderr,
        )


class TestNar05NavAbsent(NarrativeGateTestCase):
    """failure_modes: nav が無い HTML は checked=0 の PASS にしない。"""

    def test_exit_one(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_nav=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual(1, res.returncode, "sticky nav 不在は exit 1\nstdout=%s" % res.stdout)

    def test_nar05_is_fail_not_pass(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_nav=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertEqual("FAIL", self.summary(res)["NAR-05"]["status"])

    def test_reason_mentions_nav_absence(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_nav=True))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertGreaterEqual(len(self.stderr_rows(res, "NAR-05")), 1)


class TestNar06Chain(NarrativeGateTestCase):
    def test_pass_when_id_sets_match(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-06"]["status"])

    def test_ac10_section_missing_from_html(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_sections={"s6"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-06", count=1)

    def test_ac10_report_contains_chain_table(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_sections={"s6"}))
        report = self.tmpdir / "r.json"
        self.run_gate(html, self.write_config(cfg), json_report=report)
        blob = report.read_text(encoding="utf-8")
        for sec in cfg["sections"]:
            self.assertIn(sec["id"], blob, "対応表に %s が無い" % sec["id"])

    def test_chain_table_is_emitted_even_on_pass(self):
        html, cfg = self.write_pair()
        report = self.tmpdir / "r.json"
        self.run_gate(html, cfg, json_report=report)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertIn(
            "s7", json.dumps(data, ensure_ascii=False), "PASS 時も対応表を必ず出力する"
        )

    def test_extra_section_in_html_only(self):
        cfg = base_config()
        html = self.write_html(
            build_html(cfg, extra_html_sections=[{"id": "s99", "title": "余分", "role": "main"}])
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-06", count=1)

    def test_config_side_empty_goal_counts_in_nar06(self):
        cfg = base_config()
        cfg["sections"][2]["goal"] = ""
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertGreaterEqual(self.violations(res, "NAR-06"), 1)

    def test_two_missing_sections_counts_two(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, omit_sections={"s5", "s6"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-06", count=2)

    def test_hero_id_is_not_counted_as_section(self):
        # <section> タグかつ id を持つものだけを対象にする
        cfg = base_config()
        html = build_html(cfg).replace('<div class="pop-hero"', '<div id="hero" class="pop-hero"', 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_footer_div_with_id_is_not_counted(self):
        cfg = base_config()
        html = build_html(cfg).replace("</body>", '<div id="footer">脚注</div>\n</body>', 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_section_without_id_is_not_counted(self):
        cfg = base_config()
        html = build_html(cfg).replace("</body>", "<section>id なしの飾り</section>\n</body>", 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_pass(res)


if __name__ == "__main__":
    unittest.main()
