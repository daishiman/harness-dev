# -*- coding: utf-8 -*-
"""NAR-08 (R21 C48 の描画面): 付録の隔離と運営連絡の混入。AC-C22-R21-48。"""

from __future__ import annotations

import unittest

from _support import NarrativeGateTestCase, base_config, build_html

MAIN_IDS = ["s1", "s2", "s3", "s4", "s5", "s6"]


class TestNar08Baseline(NarrativeGateTestCase):
    def test_pass_when_appendix_comes_last(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("PASS", self.summary(res)["NAR-08"]["status"])

    def test_checked_counts_appendix_sections(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assertEqual("1", self.summary(res)["NAR-08"]["checked"])


class TestNar08DocumentOrder(NarrativeGateTestCase):
    def test_appendix_before_main_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_order=["s1", "s2", "s7"] + ["s3", "s4", "s5", "s6"]))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_appendix_first_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_order=["s7"] + MAIN_IDS))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_stderr_names_the_appendix_section(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_order=["s7"] + MAIN_IDS))
        res = self.run_gate(html, self.write_config(cfg))
        self.assertTrue(
            any("s7" in "\t".join(r) for r in self.stderr_rows(res, "NAR-08")),
            "stderr=%r" % res.stderr,
        )


class TestNar08SectionRoleAttribute(NarrativeGateTestCase):
    def test_missing_data_hb_section_role_on_appendix(self):
        cfg = base_config()
        html = build_html(cfg).replace(' data-hb-section-role="appendix"', "", 1)
        res = self.run_gate(self.write_html(html), self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_appendix_rendered_with_main_role_attribute(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, section_role_attr={"s7": "main"}))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)


class TestNar08NavOrder(NarrativeGateTestCase):
    def test_appendix_before_main_in_nav_is_violation(self):
        cfg = base_config()
        html = self.write_html(build_html(cfg, nav_order=["s7"] + MAIN_IDS))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_nav_order_matching_document_order_passes(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)


class TestNar08Logistics(NarrativeGateTestCase):
    """AC-C22-R21-48: section_kind=logistics が role=main で描画されたら違反。"""

    def test_logistics_as_main_at_third_position(self):
        cfg = base_config()
        cfg["sections"][6]["role"] = "main"
        html = self.write_html(
            build_html(cfg, section_order=["s1", "s2", "s7", "s3", "s4", "s5", "s6"])
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_logistics_as_main_at_last_position_is_still_violation(self):
        # 位置ではなく role が main であること自体が違反
        cfg = base_config()
        cfg["sections"][6]["role"] = "main"
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=1)

    def test_logistics_as_appendix_passes(self):
        html, cfg = self.write_pair()
        res = self.run_gate(html, cfg)
        self.assert_gate_pass(res)

    def test_two_appendix_sections_both_last_passes(self):
        cfg = base_config()
        cfg["sections"].append(
            {
                "id": "s8",
                "title": "参考リンク",
                "goal": "読み終えたら、後で読む先が分かる。",
                "role": "appendix",
                "section_kind": "sources",
                "ties_to": "goal",
                "duration": "5分",
            }
        )
        html = self.write_html(build_html(cfg))
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_pass(res)

    def test_main_after_two_appendix_is_violation(self):
        cfg = base_config()
        cfg["sections"].append(
            {
                "id": "s8",
                "title": "参考リンク",
                "goal": "読み終えたら、後で読む先が分かる。",
                "role": "appendix",
                "section_kind": "sources",
                "ties_to": "goal",
                "duration": "5分",
            }
        )
        html = self.write_html(
            build_html(cfg, section_order=["s1", "s7", "s8", "s2", "s3", "s4", "s5", "s6"])
        )
        res = self.run_gate(html, self.write_config(cfg))
        self.assert_gate_fail(res, "NAR-08", count=2)


if __name__ == "__main__":
    unittest.main()
